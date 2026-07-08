"""四个 setup 的候选检测器（rules.yaml `setups` 节）。

约定：`bars` 按时间升序，末位为信号日（t-1，买入决策前一交易日），
只使用信号日及之前的数据；盘中买入门槛由 filters.market_state_allows_buy
在决策时点另行判定。

检测器只回答"是否构成候选"，不产生仓位或订单。
数据不足 / limit 价缺失时不触发，并在 missing 里显式记录。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .bars import DailyBar, closed_at_limit_up, volume_baseline

SETUP_RECENT_LIMIT_UP_OR_DOUBLE_VOLUME = "recent_limit_up_or_double_volume"
SETUP_VOLUME_LONG_UPPER_SHADOW = "volume_long_upper_shadow"
SETUP_FIRST_TO_SECOND_LIMIT_UP = "first_to_second_limit_up"
SETUP_CONTRARY_STRENGTH = "contrary_strength"


@dataclass
class SetupSignal:
    setup_id: str
    triggered: bool
    reasons: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def _cfg(rules: dict[str, Any], setup_id: str) -> dict[str, Any]:
    return rules["setups"][setup_id]


def detect_recent_limit_up_or_double_volume(
    bars: list[DailyBar], rules: dict[str, Any]
) -> SetupSignal:
    """近 20 日出现过涨停，或信号日量 >= 前 20 日均量 2 倍（OR 语义）。"""
    cfg = _cfg(rules, SETUP_RECENT_LIMIT_UP_OR_DOUBLE_VOLUME)
    signal = SetupSignal(SETUP_RECENT_LIMIT_UP_OR_DOUBLE_VOLUME, False)
    lookback = int(cfg["has_limit_up_lookback_days"])
    if len(bars) < lookback + 1:
        signal.missing.append("insufficient_history")
        return signal

    window = bars[-lookback:]
    limit_flags = [closed_at_limit_up(b) for b in window]
    has_limit_up = any(flag is True for flag in limit_flags)
    if not has_limit_up and any(flag is None for flag in limit_flags):
        signal.missing.append("limit_up_price")

    baseline = volume_baseline(bars, lookback)
    double_volume = False
    if baseline is None:
        signal.missing.append("volume_baseline")
    else:
        double_volume = bars[-1].volume >= float(cfg["volume_multiple_min"]) * baseline

    if has_limit_up:
        signal.reasons.append("recent_limit_up")
    if double_volume:
        signal.reasons.append("double_volume")
    signal.triggered = has_limit_up or double_volume
    return signal


def detect_volume_long_upper_shadow(bars: list[DailyBar], rules: dict[str, Any]) -> SetupSignal:
    """放量长上影：量 >= 1.5x 基准，上影 >= 昨收 5%，上影/振幅 >= 0.5。"""
    cfg = _cfg(rules, SETUP_VOLUME_LONG_UPPER_SHADOW)
    signal = SetupSignal(SETUP_VOLUME_LONG_UPPER_SHADOW, False)
    bar = bars[-1]

    bar_range = bar.high - bar.low
    if bar_range <= 0:
        signal.reasons.append("zero_range_skip")
        return signal

    baseline = volume_baseline(bars)
    if baseline is None:
        signal.missing.append("volume_baseline")
        return signal

    upper_shadow = bar.high - max(bar.open, bar.close)
    volume_ok = bar.volume >= float(cfg["volume_multiple_min"]) * baseline
    shadow_pct_ok = upper_shadow / bar.prev_close >= float(cfg["upper_shadow_pct_min"])
    shadow_range_ok = upper_shadow / bar_range >= float(cfg["upper_shadow_to_range_min"])

    signal.triggered = volume_ok and shadow_pct_ok and shadow_range_ok
    if signal.triggered:
        signal.reasons.append("volume_long_upper_shadow")
    return signal


def detect_first_to_second_limit_up(
    bars: list[DailyBar],
    rules: dict[str, Any],
    free_float_mcap_percentile: float | None,
) -> SetupSignal:
    """一进二：信号日首板涨停、此前 20 日无涨停、流通市值分位 <= 30%。

    买入日约束（价格高于昨收、涨停无排队数据不可成交）在执行层判定。
    """
    cfg = _cfg(rules, SETUP_FIRST_TO_SECOND_LIMIT_UP)
    signal = SetupSignal(SETUP_FIRST_TO_SECOND_LIMIT_UP, False)
    lookback = int(rules["setup_common"]["lookback_trading_days"])
    if len(bars) < lookback + 1:
        signal.missing.append("insufficient_history")
        return signal

    signal_day_limit_up = closed_at_limit_up(bars[-1])
    if signal_day_limit_up is None:
        signal.missing.append("limit_up_price")
        return signal
    if not signal_day_limit_up:
        return signal

    prior_flags = [closed_at_limit_up(b) for b in bars[-(lookback + 1) : -1]]
    if any(flag is None for flag in prior_flags):
        signal.missing.append("limit_up_price_history")
        return signal
    prior_limit_ups = sum(1 for flag in prior_flags if flag)
    if prior_limit_ups > int(cfg["previous_20_days_limit_up_count_max"]):
        return signal

    if free_float_mcap_percentile is None:
        signal.missing.append("free_float_market_cap_percentile")
        return signal
    if free_float_mcap_percentile > float(cfg["free_float_market_cap_percentile_max"]):
        return signal

    signal.triggered = True
    signal.reasons.append("first_limit_up_small_cap")
    return signal


def detect_contrary_strength(
    bars: list[DailyBar],
    rules: dict[str, Any],
    prev_day_advancers_ratio: float | None,
) -> SetupSignal:
    """弱市逆势强势股：昨日全市场上涨占比 <= 40% 时，个股放量收阳 >= 3%。"""
    cfg = _cfg(rules, SETUP_CONTRARY_STRENGTH)
    signal = SetupSignal(SETUP_CONTRARY_STRENGTH, False)
    bar = bars[-1]

    if prev_day_advancers_ratio is None:
        signal.missing.append("prev_day_advancers_ratio")
        return signal
    if prev_day_advancers_ratio > float(cfg["previous_day_advancers_ratio_max"]):
        return signal

    baseline = volume_baseline(bars)
    if baseline is None:
        signal.missing.append("volume_baseline")
        return signal

    return_ok = bar.pct_change >= float(cfg["previous_day_stock_return_min"])
    close_above_open = bar.close > bar.open
    volume_ok = bar.volume >= float(cfg["volume_multiple_min"]) * baseline

    signal.triggered = return_ok and close_above_open and volume_ok
    if signal.triggered:
        signal.reasons.append("contrary_strength")
    return signal
