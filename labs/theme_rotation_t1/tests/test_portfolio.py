"""仓位分配、整手约束、相关性与总仓位约束测试。"""

import pytest
from engine.costs import CostModel
from engine.portfolio import (
    MISSING_THEME_ID,
    OpenPosition,
    correlation_allows,
    position_caps_allow,
    risk_position_cash_cap,
    size_position,
    slice_cash,
)
from engine.rules import MISSING, is_missing, load_rules


@pytest.fixture(scope="module")
def rules():
    return load_rules()


@pytest.fixture(scope="module")
def cost_model():
    return CostModel.load_stock()


class TestRiskCashCap:
    def test_formula(self):
        # 100000 * 1% 容忍回撤 / 20% 隔夜跳空风险 = 5000
        assert risk_position_cash_cap(100000, 0.01, 0.20) == pytest.approx(5000)

    def test_missing_params_stay_missing(self, rules):
        sizing = rules["position_sizing"]
        cap = risk_position_cash_cap(
            100000,
            sizing["tolerated_account_drawdown_pct"],  # rules.yaml 中为 [MISSING]
            0.20,
        )
        assert is_missing(cap)
        assert is_missing(risk_position_cash_cap(100000, 0.01, None))


class TestSliceCash:
    def test_valid_slices(self, rules):
        assert slice_cash(100000, 5, rules) == pytest.approx(20000)
        assert slice_cash(100000, 10, rules) == pytest.approx(10000)

    @pytest.mark.parametrize("n", [4, 11, 0])
    def test_out_of_range_raises(self, rules, n):
        with pytest.raises(ValueError):
            slice_cash(100000, n, rules)


class TestSizePosition:
    def test_whole_lots_only(self, cost_model):
        decision = size_position(10.0, 5000, cost_model)
        assert not decision.skipped
        assert decision.shares == 400  # 4 手，含滑点后一手 ≈ 1001.5 元
        assert decision.shares % 100 == 0
        assert decision.cash_required <= 5000

    def test_one_lot_exceeds_cap_skips(self, cost_model):
        # 一手 150 元股票 ≈ 15022 元 > 5000 元风险上限 → skip_trade
        decision = size_position(150.0, 5000, cost_model)
        assert decision.skipped
        assert decision.reason == "one_lot_exceeds_risk_cap"
        assert decision.shares == 0

    def test_commission_pushes_over_cap_drops_a_lot(self, cost_model):
        # 上限刚好卡在一手名义金额与佣金之间：1001.5 < 1003 < 1006.5
        decision = size_position(10.0, 1003, cost_model)
        assert decision.skipped
        assert decision.reason == "one_lot_exceeds_risk_cap"

    def test_one_lot_only_for_insufficient_sample(self, cost_model):
        decision = size_position(10.0, 5000, cost_model, one_lot_only=True)
        assert not decision.skipped
        assert decision.shares == 100

    def test_entry_fraction_after_cooldown(self, cost_model):
        # 5000 * 1/3 ≈ 1666 → 只能 1 手
        decision = size_position(10.0, 5000, cost_model, entry_fraction=1 / 3)
        assert not decision.skipped
        assert decision.shares == 100

    def test_missing_cap_skips(self, cost_model):
        decision = size_position(10.0, MISSING, cost_model)
        assert decision.skipped
        assert decision.reason == "missing_param"


class TestCorrelationLimits:
    def test_same_setup_limit_3(self, rules):
        positions = [
            OpenPosition("600001", "contrary_strength", "theme_a"),
            OpenPosition("600002", "contrary_strength", "theme_b"),
            OpenPosition("600003", "contrary_strength", "theme_c"),
        ]
        decision = correlation_allows(positions, "contrary_strength", "theme_d", rules)
        assert not decision.passed
        assert "max_positions_per_setup" in decision.reasons

    def test_same_theme_limit_2(self, rules):
        positions = [
            OpenPosition("600001", "contrary_strength", "theme_a"),
            OpenPosition("600002", "volume_long_upper_shadow", "theme_a"),
        ]
        decision = correlation_allows(
            positions, "first_to_second_limit_up", "theme_a", rules
        )
        assert not decision.passed
        assert "max_positions_per_theme" in decision.reasons

    def test_below_limits_allowed(self, rules):
        positions = [
            OpenPosition("600001", "contrary_strength", "theme_a"),
            OpenPosition("600002", "volume_long_upper_shadow", "theme_b"),
        ]
        decision = correlation_allows(positions, "contrary_strength", "theme_c", rules)
        assert decision.passed

    def test_missing_theme_shares_one_bucket(self, rules):
        # 无法证明不同题材 → 缺失题材共享同一桶，最多 2 只
        positions = [
            OpenPosition("600001", "contrary_strength", MISSING_THEME_ID),
            OpenPosition("600002", "volume_long_upper_shadow", MISSING_THEME_ID),
        ]
        decision = correlation_allows(
            positions, "first_to_second_limit_up", MISSING_THEME_ID, rules
        )
        assert not decision.passed
        assert "max_positions_per_theme" in decision.reasons


class TestPositionCaps:
    def test_within_caps(self, rules):
        assert position_caps_allow(100000, 70000, 10000, rules).passed

    def test_total_position_above_85pct(self, rules):
        decision = position_caps_allow(100000, 80000, 6000, rules)
        assert not decision.passed
        assert "total_position_above_max" in decision.reasons
        assert "cash_below_min" in decision.reasons

    def test_exact_85pct_allowed(self, rules):
        assert position_caps_allow(100000, 80000, 5000, rules).passed
