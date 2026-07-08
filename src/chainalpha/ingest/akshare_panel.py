"""AkShare 日线拉取 → panel parquet（因子筛选用）。

对齐 microsoft/qlib `scripts/data_collector/akshare/collector.py` 的 universe 发现与
`stock_zh_a_hist` 拉取逻辑；落地为 chainalpha parquet 缓存，供 event_study 使用。
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
from loguru import logger

from chainalpha.factors.bars import normalize_ohlcv, panel_from_frames

ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = ROOT / "data" / "raw" / "factor_screening" / "daily_parquet"
CSV_CACHE_DIR = ROOT / "data" / "raw" / "factor_screening" / "daily_csv"
UNIVERSE_PATH = ROOT / "data" / "raw" / "factor_screening" / "universe.json"

# qlib AkShare collector：排除 B 股
_B_PREFIXES = ("900", "200")

DEFAULT_PROBE_SYMBOLS = (
    "000001",
    "000002",
    "600000",
    "600519",
    "300750",
    "688981",
)

# AkShare 限流：全市场默认单线程 + delay
DEFAULT_DELAY_SEC = 0.35
DEFAULT_MAX_WORKERS = 1


@dataclass
class LoadReport:
    symbols_requested: int = 0
    symbols_loaded: int = 0
    symbols_failed: list[str] = field(default_factory=list)
    symbols_skipped_cache: int = 0
    rows: int = 0
    cache_dir: str = ""
    universe_size: int = 0
    elapsed_sec: float = 0.0

    def to_dict(self) -> dict:
        return {
            "symbols_requested": self.symbols_requested,
            "symbols_loaded": self.symbols_loaded,
            "symbols_failed": self.symbols_failed,
            "symbols_skipped_cache": self.symbols_skipped_cache,
            "rows": self.rows,
            "cache_dir": self.cache_dir,
            "universe_size": self.universe_size,
            "elapsed_sec": round(self.elapsed_sec, 2),
        }


def qlib_to_raw(symbol: str) -> str:
    """SH600519 / SZ000001 → 600519 / 000001。"""
    sym = symbol.strip().upper()
    for prefix in ("SH", "SZ"):
        if sym.startswith(prefix):
            return sym[len(prefix) :].zfill(6)
    return sym.zfill(6)


def symbol_to_qlib(symbol: str) -> str:
    """000001 → SZ000001；600519 → SH600519。"""
    sym = qlib_to_raw(symbol)
    if sym.startswith("6"):
        return f"SH{sym}"
    return f"SZ{sym}"


def get_all_a_share_symbols(*, refresh: bool = False) -> list[str]:
    """全 A 股代码列表（排除 B 股），逻辑同 qlib AKShareCollector。"""
    if UNIVERSE_PATH.is_file() and not refresh:
        payload = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
        return payload["symbols"]

    import akshare as ak

    last_err: Exception | None = None
    for attempt in range(3):
        try:
            df = ak.stock_info_a_code_name()
            symbols = _symbols_from_code_name_df(df)
            _write_universe(symbols)
            return symbols
        except Exception as exc:
            last_err = exc
            logger.warning("stock_info_a_code_name attempt {} failed: {}", attempt + 1, exc)
            time.sleep(1.5 * (attempt + 1))

    logger.warning("Falling back to stock_zh_a_spot_em for universe discovery")
    try:
        spot = ak.stock_zh_a_spot_em()
        code_col = "代码" if "代码" in spot.columns else "code"
        codes = spot[code_col].astype(str).str.zfill(6)
        symbols = sorted({c for c in codes if not c.startswith(_B_PREFIXES)})
        _write_universe(symbols)
        return symbols
    except Exception as exc:
        msg = f"Universe discovery failed: {last_err}; fallback: {exc}"
        raise RuntimeError(msg) from exc


def _symbols_from_code_name_df(df: pd.DataFrame) -> list[str]:
    code_col = "code" if "code" in df.columns else "代码"
    codes = df[code_col].astype(str).str.zfill(6)
    return sorted({c for c in codes if not c.startswith(_B_PREFIXES)})


def _write_universe(symbols: list[str]) -> None:
    UNIVERSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    UNIVERSE_PATH.write_text(
        json.dumps(
            {
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "count": len(symbols),
                "symbols": symbols,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    logger.info("Discovered {} A-share symbols (excl. B-shares)", len(symbols))


def load_symbols_from_file(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return sorted({qlib_to_raw(line.strip()) for line in lines if line.strip()})


def _fetch_symbol_hist(
    symbol: str,
    start_date: str,
    end_date: str,
    *,
    adjust: str = "hfq",
    max_retries: int = 3,
) -> pd.DataFrame:
    import akshare as ak

    sym = qlib_to_raw(symbol)
    last_err: Exception | None = None
    for attempt in range(max_retries):
        try:
            df = ak.stock_zh_a_hist(
                symbol=sym,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust=adjust,
            )
            return normalize_ohlcv(df, symbol=sym)
        except Exception as exc:
            last_err = exc
            wait = 2.0 * (attempt + 1)
            logger.warning("fetch {} attempt {} failed: {} (retry in {:.0f}s)", sym, attempt + 1, exc, wait)
            time.sleep(wait)
    if last_err is not None:
        raise last_err
    return pd.DataFrame()


def _parquet_path(symbol: str, cache_dir: Path) -> Path:
    return cache_dir / f"{qlib_to_raw(symbol)}.parquet"


def _csv_path(symbol: str, cache_dir: Path) -> Path:
    return cache_dir / f"{qlib_to_raw(symbol)}.csv"


def load_symbol(
    symbol: str,
    start_date: str,
    end_date: str,
    *,
    use_cache: bool = True,
    cache_dir: Path | None = None,
    adjust: str = "hfq",
    delay_sec: float = 0.0,
) -> pd.DataFrame:
    cache_root = cache_dir or CACHE_DIR
    cache_root.mkdir(parents=True, exist_ok=True)
    sym = qlib_to_raw(symbol)
    cache_path = _parquet_path(sym, cache_root)

    if use_cache and cache_path.is_file():
        df = pd.read_parquet(cache_path)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        return df

    if delay_sec > 0:
        time.sleep(delay_sec)

    df = _fetch_symbol_hist(sym, start_date, end_date, adjust=adjust)
    if use_cache and not df.empty:
        df.to_parquet(cache_path, index=False)
    return df


def _download_one(
    symbol: str,
    start_date: str,
    end_date: str,
    *,
    use_cache: bool,
    parquet_dir: Path,
    adjust: str,
    delay_sec: float,
) -> tuple[str, bool, str | None]:
    sym = qlib_to_raw(symbol)
    path = _parquet_path(sym, parquet_dir)
    if use_cache and path.is_file():
        return sym, True, "cached"

    try:
        if delay_sec > 0:
            time.sleep(delay_sec)
        df = _fetch_symbol_hist(sym, start_date, end_date, adjust=adjust)
        if df.empty:
            return sym, False, "empty"
        df.to_parquet(path, index=False)
        return sym, True, None
    except Exception as exc:
        return sym, False, str(exc)


def download_universe(
    symbols: list[str],
    start_date: str,
    end_date: str,
    *,
    use_cache: bool = True,
    cache_dir: Path | None = None,
    adjust: str = "hfq",
    delay_sec: float = DEFAULT_DELAY_SEC,
    max_workers: int = DEFAULT_MAX_WORKERS,
    limit: int | None = None,
) -> LoadReport:
    """批量下载全市场（或子集）至 parquet，支持断点续传（已有文件跳过）。"""
    t0 = time.perf_counter()
    cache_root = cache_dir or CACHE_DIR
    cache_root.mkdir(parents=True, exist_ok=True)

    todo = [qlib_to_raw(s) for s in symbols]
    if limit is not None:
        todo = todo[:limit]

    report = LoadReport(
        symbols_requested=len(todo),
        cache_dir=str(cache_root),
        universe_size=len(symbols),
    )

    try:
        from tqdm import tqdm
    except ImportError:
        tqdm = None  # type: ignore[assignment]

    def _run_batch(batch: list[str]) -> None:
        if max_workers <= 1:
            iterator = batch
            if tqdm:
                iterator = tqdm(batch, desc="download", unit="sym")
            for sym in iterator:
                s, ok, reason = _download_one(
                    sym,
                    start_date,
                    end_date,
                    use_cache=use_cache,
                    parquet_dir=cache_root,
                    adjust=adjust,
                    delay_sec=delay_sec,
                )
                if ok and reason == "cached":
                    report.symbols_skipped_cache += 1
                    report.symbols_loaded += 1
                elif ok:
                    report.symbols_loaded += 1
                else:
                    report.symbols_failed.append(s)
            return

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(
                    _download_one,
                    sym,
                    start_date,
                    end_date,
                    use_cache=use_cache,
                    parquet_dir=cache_root,
                    adjust=adjust,
                    delay_sec=delay_sec,
                ): sym
                for sym in batch
            }
            completed = as_completed(futures)
            if tqdm:
                completed = tqdm(completed, total=len(futures), desc="download", unit="sym")
            for fut in completed:
                s, ok, reason = fut.result()
                if ok and reason == "cached":
                    report.symbols_skipped_cache += 1
                    report.symbols_loaded += 1
                elif ok:
                    report.symbols_loaded += 1
                else:
                    report.symbols_failed.append(s)

    _run_batch(todo)
    report.elapsed_sec = time.perf_counter() - t0
    return report


def load_panel(
    symbols: list[str],
    start_date: str,
    end_date: str,
    *,
    use_cache: bool = True,
    cache_dir: Path | None = None,
    adjust: str = "hfq",
    delay_sec: float = 0.0,
    download: bool = True,
    max_workers: int = DEFAULT_MAX_WORKERS,
    limit: int | None = None,
) -> tuple[pd.DataFrame, LoadReport]:
    """加载 panel：可选先 download_universe，再读 parquet 合并。"""
    if download:
        dl_report = download_universe(
            symbols,
            start_date,
            end_date,
            use_cache=use_cache,
            cache_dir=cache_dir,
            adjust=adjust,
            delay_sec=delay_sec,
            max_workers=max_workers,
            limit=limit,
        )
    else:
        dl_report = LoadReport(symbols_requested=len(symbols), cache_dir=str(cache_dir or CACHE_DIR))

    sym_list = [qlib_to_raw(s) for s in symbols]
    if limit is not None:
        sym_list = sym_list[:limit]

    frames: list[pd.DataFrame] = []
    for sym in sym_list:
        path = _parquet_path(sym, cache_dir or CACHE_DIR)
        if not path.is_file():
            if sym not in dl_report.symbols_failed:
                dl_report.symbols_failed.append(sym)
            continue
        try:
            df = pd.read_parquet(path)
            df["trade_date"] = pd.to_datetime(df["trade_date"])
            start_ts = pd.Timestamp(start_date)
            end_ts = pd.Timestamp(end_date)
            df = df[(df["trade_date"] >= start_ts) & (df["trade_date"] <= end_ts)]
            if df.empty:
                continue
            frames.append(df)
        except Exception:
            dl_report.symbols_failed.append(sym)

    panel = panel_from_frames(frames)
    dl_report.rows = len(panel)
    return panel, dl_report


def load_all_market_panel(
    start_date: str,
    end_date: str,
    *,
    use_cache: bool = True,
    cache_dir: Path | None = None,
    adjust: str = "hfq",
    delay_sec: float = DEFAULT_DELAY_SEC,
    max_workers: int = DEFAULT_MAX_WORKERS,
    limit: int | None = None,
    refresh_universe: bool = False,
    download: bool = True,
) -> tuple[pd.DataFrame, LoadReport]:
    """发现全 A 股 universe 并加载 2020–2025（或自定义）panel。"""
    symbols = get_all_a_share_symbols(refresh=refresh_universe)
    panel, report = load_panel(
        symbols,
        start_date,
        end_date,
        use_cache=use_cache,
        cache_dir=cache_dir,
        adjust=adjust,
        delay_sec=delay_sec,
        download=download,
        max_workers=max_workers,
        limit=limit,
    )
    report.universe_size = len(symbols)
    return panel, report


def load_panel_from_cache(
    cache_dir: Path | None = None,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    """从已缓存 parquet 目录加载 panel（离线复现）。"""
    root = cache_dir or CACHE_DIR
    if not root.is_dir():
        return pd.DataFrame()
    frames: list[pd.DataFrame] = []
    for path in sorted(root.glob("*.parquet")):
        df = pd.read_parquet(path)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        if start_date is not None:
            df = df[df["trade_date"] >= pd.Timestamp(start_date)]
        if end_date is not None:
            df = df[df["trade_date"] <= pd.Timestamp(end_date)]
        if not df.empty:
            frames.append(df)
    return panel_from_frames(frames)


def try_run_qlib_akshare_collector(
    source_dir: Path,
    start_date: str,
    end_date: str,
    *,
    adjust: str = "hfq",
    delay: float = 0.5,
    limit_nums: int | None = None,
) -> bool:
    """若本机 qlib 源码含 akshare collector，则委托其 download_data（可选）。"""
    try:
        import qlib  # noqa: F401
    except ImportError:
        return False

    import subprocess
    import sys

    qlib_pkg = Path(sys.modules["qlib"].__file__).resolve().parent
    candidates = [
        qlib_pkg.parent / "scripts" / "data_collector" / "akshare" / "collector.py",
        ROOT / "vendor" / "qlib" / "scripts" / "data_collector" / "akshare" / "collector.py",
    ]
    collector = next((p for p in candidates if p.is_file()), None)
    if collector is None:
        return False

    source_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(collector),
        "download_data",
        "--source_dir",
        str(source_dir),
        "--start",
        start_date,
        "--end",
        end_date,
        "--delay",
        str(delay),
        "--adjust",
        adjust,
    ]
    if limit_nums is not None:
        cmd.extend(["--limit_nums", str(limit_nums)])
    subprocess.run(cmd, check=True)
    return True
