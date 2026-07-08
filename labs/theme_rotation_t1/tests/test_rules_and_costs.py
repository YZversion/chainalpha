"""rules.yaml 加载（MISSING 哨兵）与 config/costs.yaml 成本模型测试。"""

import pytest
from engine.costs import CostModel
from engine.rules import MISSING, is_missing, load_rules


@pytest.fixture(scope="module")
def rules():
    return load_rules()


@pytest.fixture(scope="module")
def cost_model():
    return CostModel.load_stock()


class TestRulesLoading:
    def test_missing_sentinel_preserved(self, rules):
        sizing = rules["position_sizing"]
        assert is_missing(sizing["tolerated_account_drawdown_pct"])
        assert is_missing(sizing["overnight_gap_risk_pct"]["default"])

    def test_missing_is_falsy_singleton(self):
        assert not MISSING
        assert repr(MISSING) == "[MISSING]"

    def test_frozen_key_values(self, rules):
        assert rules["account"]["initial_account"] == 100000
        assert rules["account"]["lot_size"] == 100
        assert rules["market_state"]["buy_advancers_ratio_min"] == 0.60
        assert rules["cooldown"]["losing_days_clear_all"] == 3
        assert rules["validation"]["min_trades_per_setup_for_normal_size"] == 30


class TestCostModel:
    def test_parameters_match_config(self, cost_model):
        assert cost_model.commission_rate == 0.00025
        assert cost_model.commission_min == 5
        assert cost_model.stamp_tax_rate == 0.0005
        assert cost_model.slippage_rate == 0.0015
        assert cost_model.lot_size == 100
        assert cost_model.initial_account == 100000

    def test_minimum_5_yuan_commission_small_trade(self, cost_model):
        # 100 股 * 10 元 ≈ 1000 元：按万 2.5 只有 0.25 元，必须收 5 元
        costs = cost_model.buy_costs(10.0, 100)
        assert costs.commission == 5

    def test_rate_commission_large_trade(self, cost_model):
        # 4000 股 * 10 元 ≈ 40000 元：万 2.5 约 10 元，超过 5 元下限
        costs = cost_model.buy_costs(10.0, 4000)
        assert costs.commission == pytest.approx(costs.notional * 0.00025)
        assert costs.commission > 5

    def test_stamp_tax_sell_only(self, cost_model):
        buy = cost_model.buy_costs(10.0, 1000)
        sell = cost_model.sell_costs(10.0, 1000)
        assert buy.stamp_tax == 0
        assert sell.stamp_tax == pytest.approx(sell.notional * 0.0005)

    def test_slippage_adverse_both_sides(self, cost_model):
        buy = cost_model.buy_costs(10.0, 1000)
        sell = cost_model.sell_costs(10.0, 1000)
        assert buy.fill_price == pytest.approx(10.0 * 1.0015)
        assert sell.fill_price == pytest.approx(10.0 * 0.9985)
        assert buy.slippage_cash == pytest.approx(0.015 * 1000)
        assert sell.slippage_cash == pytest.approx(0.015 * 1000)

    def test_cash_flows_include_all_frictions(self, cost_model):
        outflow = cost_model.buy_cash_outflow(10.0, 1000)
        inflow = cost_model.sell_cash_inflow(10.0, 1000)
        buy = cost_model.buy_costs(10.0, 1000)
        sell = cost_model.sell_costs(10.0, 1000)
        assert outflow == pytest.approx(buy.notional + buy.commission)
        assert inflow == pytest.approx(sell.notional - sell.commission - sell.stamp_tax)
        # 一买一卖的往返摩擦必须为正且可核对
        assert outflow - inflow == pytest.approx(
            buy.total_friction + sell.total_friction, rel=1e-9
        )
