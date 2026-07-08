"""市场状态门槛、买入时间窗、事件风险过滤测试。"""

from datetime import time

import pytest
from engine.filters import (
    EventRiskInputs,
    entry_window_allows,
    event_risk_filter,
    market_state_allows_buy,
)
from engine.rules import load_rules


@pytest.fixture(scope="module")
def rules():
    return load_rules()


CLEAN_INPUTS = EventRiskInputs(
    days_to_next_unlock=90,
    has_announced_unfinished_reduction=False,
    days_since_inquiry_or_regulatory_letter=120,
    is_st_or_risk_warning=False,
    listing_age_days=800,
)


class TestMarketState:
    def test_breadth_above_min_allows(self, rules):
        assert market_state_allows_buy(0.65, rules).passed

    def test_breadth_below_min_blocks(self, rules):
        decision = market_state_allows_buy(0.55, rules)
        assert not decision.passed
        assert "breadth_below_min" in decision.reasons

    def test_missing_breadth_no_trade(self, rules):
        decision = market_state_allows_buy(None, rules)
        assert not decision.passed
        assert "missing:intraday_breadth" in decision.reasons

    def test_exact_threshold_allows(self, rules):
        assert market_state_allows_buy(0.60, rules).passed


class TestEntryWindow:
    @pytest.mark.parametrize(
        ("hour", "minute", "allowed"),
        [
            (9, 45, True),
            (10, 40, True),   # 边界含
            (10, 41, False),
            (13, 0, False),
            (14, 39, False),
            (14, 40, True),   # 边界含
            (14, 55, True),
        ],
    )
    def test_windows(self, rules, hour, minute, allowed):
        assert entry_window_allows(time(hour, minute), rules).passed is allowed


class TestEventRiskFilter:
    def test_clean_inputs_pass(self, rules):
        assert event_risk_filter(CLEAN_INPUTS, rules).passed

    def test_unlock_within_30d_excluded(self, rules):
        inputs = EventRiskInputs(
            days_to_next_unlock=10,
            has_announced_unfinished_reduction=False,
            days_since_inquiry_or_regulatory_letter=120,
            is_st_or_risk_warning=False,
            listing_age_days=800,
        )
        decision = event_risk_filter(inputs, rules)
        assert not decision.passed
        assert "unlock_within_30d" in decision.reasons

    def test_unlock_at_31d_passes(self, rules):
        inputs = EventRiskInputs(
            days_to_next_unlock=31,
            has_announced_unfinished_reduction=False,
            days_since_inquiry_or_regulatory_letter=120,
            is_st_or_risk_warning=False,
            listing_age_days=800,
        )
        assert event_risk_filter(inputs, rules).passed

    def test_unfinished_reduction_excluded(self, rules):
        inputs = EventRiskInputs(
            days_to_next_unlock=90,
            has_announced_unfinished_reduction=True,
            days_since_inquiry_or_regulatory_letter=120,
            is_st_or_risk_warning=False,
            listing_age_days=800,
        )
        decision = event_risk_filter(inputs, rules)
        assert not decision.passed
        assert "announced_unfinished_reduction" in decision.reasons

    def test_recent_letter_excluded(self, rules):
        inputs = EventRiskInputs(
            days_to_next_unlock=90,
            has_announced_unfinished_reduction=False,
            days_since_inquiry_or_regulatory_letter=5,
            is_st_or_risk_warning=False,
            listing_age_days=800,
        )
        decision = event_risk_filter(inputs, rules)
        assert not decision.passed
        assert "inquiry_or_regulatory_letter_within_30d" in decision.reasons

    def test_st_excluded(self, rules):
        inputs = EventRiskInputs(
            days_to_next_unlock=90,
            has_announced_unfinished_reduction=False,
            days_since_inquiry_or_regulatory_letter=120,
            is_st_or_risk_warning=True,
            listing_age_days=800,
        )
        decision = event_risk_filter(inputs, rules)
        assert not decision.passed
        assert "st_or_risk_warning" in decision.reasons

    def test_young_listing_excluded(self, rules):
        inputs = EventRiskInputs(
            days_to_next_unlock=90,
            has_announced_unfinished_reduction=False,
            days_since_inquiry_or_regulatory_letter=120,
            is_st_or_risk_warning=False,
            listing_age_days=200,
        )
        decision = event_risk_filter(inputs, rules)
        assert not decision.passed
        assert "listing_age_below_365d" in decision.reasons

    def test_missing_fields_excluded_conservatively(self, rules):
        inputs = EventRiskInputs(
            days_to_next_unlock=None,
            has_announced_unfinished_reduction=None,
            days_since_inquiry_or_regulatory_letter=None,
            is_st_or_risk_warning=None,
            listing_age_days=None,
        )
        decision = event_risk_filter(inputs, rules)
        assert not decision.passed
        assert len([r for r in decision.reasons if r.startswith("missing:")]) == 5
