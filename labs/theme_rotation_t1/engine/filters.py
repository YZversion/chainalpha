"""市场状态门槛、买入时间窗、事件风险过滤。

缺失字段按 rules.yaml 的保守策略处理：
- 盘中宽度缺失 → 不交易（mark_missing_no_trade）
- 事件字段缺失 → 排除并记录 missing（exclude_or_mark_missing）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from typing import Any


@dataclass
class FilterDecision:
    passed: bool
    reasons: list[str] = field(default_factory=list)


def _parse_hhmm(text: str) -> time:
    hour, minute = text.split(":")
    return time(int(hour), int(minute))


def market_state_allows_buy(
    advancers_ratio: float | None, rules: dict[str, Any]
) -> FilterDecision:
    """盘中上涨家数占比 >= 60% 才允许买入；缺失快照 → 不交易。"""
    cfg = rules["market_state"]
    if advancers_ratio is None:
        return FilterDecision(False, ["missing:intraday_breadth"])
    if advancers_ratio < float(cfg["buy_advancers_ratio_min"]):
        return FilterDecision(False, ["breadth_below_min"])
    return FilterDecision(True)


def entry_window_allows(decision_time: time, rules: dict[str, Any]) -> FilterDecision:
    """买入时间必须在 10:40 前（含）或 14:40 后（含）。"""
    cfg = rules["market_state"]["decision_times"]
    morning_latest = _parse_hhmm(cfg["morning_latest"])
    afternoon_earliest = _parse_hhmm(cfg["afternoon_earliest"])
    if decision_time <= morning_latest or decision_time >= afternoon_earliest:
        return FilterDecision(True)
    return FilterDecision(False, ["outside_entry_window"])


@dataclass(frozen=True)
class EventRiskInputs:
    """全部取自公开公告/披露数据；未知字段传 None。"""

    days_to_next_unlock: int | None
    has_announced_unfinished_reduction: bool | None
    days_since_inquiry_or_regulatory_letter: int | None
    is_st_or_risk_warning: bool | None
    listing_age_days: int | None


def event_risk_filter(inputs: EventRiskInputs, rules: dict[str, Any]) -> FilterDecision:
    cfg = rules["event_risk_filter"]
    reasons: list[str] = []

    if inputs.days_to_next_unlock is None:
        reasons.append("missing:days_to_next_unlock")
    elif 0 <= inputs.days_to_next_unlock <= int(cfg["unlock_within_days"]):
        reasons.append("unlock_within_30d")

    if inputs.has_announced_unfinished_reduction is None:
        reasons.append("missing:announced_unfinished_reduction")
    elif inputs.has_announced_unfinished_reduction and cfg[
        "exclude_announced_unfinished_share_reduction"
    ]:
        reasons.append("announced_unfinished_reduction")

    if inputs.days_since_inquiry_or_regulatory_letter is None:
        reasons.append("missing:inquiry_or_regulatory_letter")
    elif 0 <= inputs.days_since_inquiry_or_regulatory_letter <= int(
        cfg["inquiry_or_regulatory_letter_within_days"]
    ):
        reasons.append("inquiry_or_regulatory_letter_within_30d")

    if inputs.is_st_or_risk_warning is None:
        reasons.append("missing:st_or_risk_warning")
    elif inputs.is_st_or_risk_warning and cfg["exclude_st_or_risk_warning"]:
        reasons.append("st_or_risk_warning")

    if inputs.listing_age_days is None:
        reasons.append("missing:listing_age_days")
    elif inputs.listing_age_days < int(cfg["min_listing_age_days"]):
        reasons.append("listing_age_below_365d")

    return FilterDecision(not reasons, reasons)
