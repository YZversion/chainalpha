"""信号日后 forward return 计算。"""

from __future__ import annotations

import pandas as pd

DEFAULT_HORIZONS = (3, 5, 10)


def add_forward_returns(
    panel: pd.DataFrame,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> pd.DataFrame:
    """按 symbol 分组，为每行添加 fwd_ret_{h} 列（收盘价收益，不含成本）。"""
    if panel.empty:
        out = panel.copy()
        for h in horizons:
            out[f"fwd_ret_{h}"] = pd.Series(dtype=float)
        return out

    parts: list[pd.DataFrame] = []
    for _, g in panel.groupby("symbol", sort=False):
        chunk = g.sort_values("trade_date").copy()
        for h in horizons:
            chunk[f"fwd_ret_{h}"] = chunk["close"].shift(-h) / chunk["close"] - 1.0
        parts.append(chunk)
    return pd.concat(parts, ignore_index=True)


def extract_signal_returns(
    panel_with_fwd: pd.DataFrame,
    signal_mask: pd.Series,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> pd.DataFrame:
    """提取信号日为 True 的行的未来收益。"""
    aligned = panel_with_fwd.loc[signal_mask.fillna(False)]
    cols = ["symbol", "trade_date", *[f"fwd_ret_{h}" for h in horizons]]
    return aligned[cols].copy()


def mean_forward_returns(
    signal_returns: pd.DataFrame,
    horizons: tuple[int, ...] = DEFAULT_HORIZONS,
) -> dict[int, float]:
    result: dict[int, float] = {}
    for h in horizons:
        col = f"fwd_ret_{h}"
        if col not in signal_returns.columns or signal_returns.empty:
            result[h] = float("nan")
            continue
        result[h] = float(signal_returns[col].mean())
    return result
