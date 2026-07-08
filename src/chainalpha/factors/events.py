"""事件型因子信号定义（规则写死，先验 Edge，不优化参数）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

# --- 固定参数（文档化；验证无 Edge 则删信号，不调参） ---

VOLUME_MA_WINDOW = 20
VOLUME_SPIKE_RATIO = 2.0  # 成交量 > 20 日均量 × 2
UPPER_SHADOW_RANGE_RATIO = 0.5  # 上影线 / 全日振幅
UPPER_SHADOW_BODY_RATIO = 2.0  # 上影线 / 实体
LIMIT_UP_LOOKBACK_DAYS = 20  # 近一月（约 20 交易日）
LIMIT_UP_PCT_MAIN = 0.095  # 主板涨停近似阈值（不含 ST/科创板差异，保守）


@dataclass(frozen=True)
class SignalSpec:
    name: str
    description: str
    fn: Callable[[pd.DataFrame], pd.Series]


def _per_symbol(group: pd.DataFrame, fn: Callable[[pd.DataFrame], pd.Series]) -> pd.Series:
    return fn(group)


def apply_signal(panel: pd.DataFrame, spec: SignalSpec) -> pd.Series:
    """返回与 panel 行对齐的 bool Series（MultiIndex 保持行序）。"""
    if panel.empty:
        return pd.Series(dtype=bool)
    parts = [
        _per_symbol(g, spec.fn)
        for _, g in panel.groupby("symbol", sort=False)
    ]
    return pd.concat(parts).sort_index()


def volume_spike_long_upper_shadow(df: pd.DataFrame) -> pd.Series:
    """放量长上影：上影显著 + 成交量显著高于近期均值。"""
    high = df["high"]
    low = df["low"]
    open_ = df["open"]
    close = df["close"]
    volume = df["volume"]

    price_range = (high - low).replace(0, np.nan)
    upper_shadow = high - np.maximum(open_, close)
    body = (close - open_).abs()

    long_upper = (upper_shadow / price_range >= UPPER_SHADOW_RANGE_RATIO) & (
        (body <= 0) | (upper_shadow >= UPPER_SHADOW_BODY_RATIO * body)
    )

    vol_ma = volume.rolling(VOLUME_MA_WINDOW, min_periods=VOLUME_MA_WINDOW).mean()
    heavy_volume = volume > (vol_ma * VOLUME_SPIKE_RATIO)

    return (long_upper & heavy_volume).fillna(False)


def limit_up_in_past_month(df: pd.DataFrame) -> pd.Series:
    """近一月（20 交易日）内出现过涨停（收盘价涨幅 ≥ 9.5%）。"""
    prev_close = df["close"].shift(1)
    daily_ret = df["close"] / prev_close - 1.0
    is_limit_up = daily_ret >= LIMIT_UP_PCT_MAIN
    had_limit_up = (
        is_limit_up.rolling(LIMIT_UP_LOOKBACK_DAYS, min_periods=1).max().astype(bool)
    )
    return had_limit_up.fillna(False)


SIGNAL_REGISTRY: dict[str, SignalSpec] = {
    "volume_spike_long_upper_shadow": SignalSpec(
        name="volume_spike_long_upper_shadow",
        description=(
            f"放量长上影：上影/振幅≥{UPPER_SHADOW_RANGE_RATIO} 且上影≥{UPPER_SHADOW_BODY_RATIO}×实体，"
            f"成交量>{VOLUME_MA_WINDOW}日均量×{VOLUME_SPIKE_RATIO}"
        ),
        fn=volume_spike_long_upper_shadow,
    ),
    "limit_up_in_past_month": SignalSpec(
        name="limit_up_in_past_month",
        description=(
            f"近{LIMIT_UP_LOOKBACK_DAYS}交易日出现过涨停（日涨幅≥{LIMIT_UP_PCT_MAIN:.1%}）"
        ),
        fn=limit_up_in_past_month,
    ),
}


def list_signals() -> list[str]:
    return list(SIGNAL_REGISTRY.keys())


def get_signal(name: str) -> SignalSpec:
    if name not in SIGNAL_REGISTRY:
        msg = f"Unknown signal: {name}. Available: {list_signals()}"
        raise KeyError(msg)
    return SIGNAL_REGISTRY[name]
