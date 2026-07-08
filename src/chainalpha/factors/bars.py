"""K 线列名规范化与基础工具。"""

from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = ("symbol", "trade_date", "open", "high", "low", "close", "volume")

_AKSHARE_RENAME = {
    "日期": "trade_date",
    "开盘": "open",
    "最高": "high",
    "最低": "low",
    "收盘": "close",
    "成交量": "volume",
}


def normalize_ohlcv(df: pd.DataFrame, symbol: str | None = None) -> pd.DataFrame:
    """将 AkShare 中文列或英文列统一为 REQUIRED_COLUMNS。"""
    out = df.copy()
    out = out.rename(columns={k: v for k, v in _AKSHARE_RENAME.items() if k in out.columns})
    if symbol is not None and "symbol" not in out.columns:
        out["symbol"] = symbol.zfill(6)
    missing = [c for c in REQUIRED_COLUMNS if c not in out.columns]
    if missing:
        msg = f"OHLCV missing columns: {missing}"
        raise ValueError(msg)
    out["trade_date"] = pd.to_datetime(out["trade_date"]).dt.normalize()
    for col in ("open", "high", "low", "close", "volume"):
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=list(REQUIRED_COLUMNS))
    out = out.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    return out[list(REQUIRED_COLUMNS)]


def panel_from_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame(columns=list(REQUIRED_COLUMNS))
    return pd.concat(frames, ignore_index=True)
