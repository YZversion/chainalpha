"""日频 OHLCV 接入：AkShare → parquet 缓存；失败标 [MISSING]。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pandas as pd
from engine.bars import DailyBar
from ingestion.akshare_client import call_df
from ingestion.limits import derive_limit_prices

WORKSPACE = Path(__file__).resolve().parents[3]
CACHE_ROOT = WORKSPACE / "data" / "raw" / "labs" / "theme_rotation_t1" / "daily_csv"

PROBE_FALLBACK_SYMBOLS = ["000001", "600519", "300750", "688981", "837006"]


@dataclass
class IngestReport:
    symbols_requested: int = 0
    symbols_loaded: int = 0
    symbols_failed: list[str] = field(default_factory=list)
    rows_total: int = 0
    source: str = "akshare:stock_zh_a_hist"
    cache_dir: str = ""


def _normalize_symbol(code: str) -> str:
    return code.split(".")[0].zfill(6)


def _parse_trade_date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def _df_to_bars(df: pd.DataFrame, symbol: str) -> list[DailyBar]:
    if df.empty:
        return []
    col_date = "日期"
    bars: list[DailyBar] = []
    prev_close: float | None = None
    sym = _normalize_symbol(symbol)

    for _, row in df.sort_values(col_date).iterrows():
        close = float(row["收盘"])
        if prev_close is None:
            pct = float(row.get("涨跌幅", 0) or 0)
            prev_close = close / (1 + pct / 100.0) if pct else close
        open_ = float(row["开盘"])
        high = float(row["最高"])
        low = float(row["最低"])
        volume = float(row["成交量"])
        limits = derive_limit_prices(prev_close, sym, is_st=None)
        suspended = volume <= 0
        bars.append(
            DailyBar(
                symbol=sym,
                trade_date=_parse_trade_date(row[col_date]),
                open=open_,
                high=high,
                low=low,
                close=close,
                prev_close=prev_close,
                volume=volume,
                limit_up_price=limits.limit_up_price,
                limit_down_price=limits.limit_down_price,
                suspended=suspended,
            )
        )
        prev_close = close
    return bars


def fetch_symbol_daily(
    symbol: str,
    start: str,
    end: str,
    *,
    use_cache: bool = True,
) -> tuple[list[DailyBar], str | None]:
    """拉取单票日线；成功返回 bars，失败返回空列表与错误信息。"""
    sym = _normalize_symbol(symbol)
    cache_path = CACHE_ROOT / f"{sym}.csv"
    if use_cache and cache_path.exists():
        df = pd.read_csv(cache_path, encoding="utf-8")
        bars = _df_to_bars(df, sym)
        return [
            b for b in bars if start <= b.trade_date.strftime("%Y%m%d") <= end
        ], None

    df = call_df(
        "stock_zh_a_hist",
        symbol=sym,
        period="daily",
        start_date=start,
        end_date=end,
        adjust="",
        timeout=25,
    )
    if df is None or df.empty:
        return [], "fetch_failed_or_empty"

    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    df.to_csv(cache_path, index=False, encoding="utf-8")
    return _df_to_bars(df, sym), None


def load_universe_symbols() -> tuple[list[str], str]:
    """尝试全 A 代码列表；失败时缩小到 probe 样本并标注 reduced_scope。"""
    df = call_df("stock_info_a_code_name")
    if df is not None and not df.empty:
        code_col = "code" if "code" in df.columns else df.columns[0]
        symbols = [_normalize_symbol(str(c)) for c in df[code_col].tolist()]
        return symbols, "full_universe"
    return list(PROBE_FALLBACK_SYMBOLS), "reduced_probe_symbols"


def ingest_daily_panel(
    symbols: list[str],
    start: str,
    end: str,
    *,
    max_symbols: int | None = None,
) -> tuple[dict[str, list[DailyBar]], IngestReport]:
    """批量接入日线面板；逐票失败不中断。"""
    report = IngestReport(
        symbols_requested=len(symbols),
        cache_dir=str(CACHE_ROOT.relative_to(WORKSPACE)),
    )
    if max_symbols is not None:
        symbols = symbols[:max_symbols]

    panel: dict[str, list[DailyBar]] = {}
    for sym in symbols:
        bars, err = fetch_symbol_daily(sym, start, end)
        if err:
            report.symbols_failed.append(sym)
            continue
        in_range = [
            b
            for b in bars
            if start <= b.trade_date.strftime("%Y%m%d") <= end
        ]
        if in_range:
            panel[sym] = in_range
            report.symbols_loaded += 1
            report.rows_total += len(in_range)

    return panel, report
