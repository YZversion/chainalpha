"""T+1、涨跌停不可成交、止损/止盈/移动止损执行测试。"""

from datetime import date

import pytest
from engine.execution import (
    Position,
    can_buy_at,
    can_sell_at,
    first_take_profit_shares,
    process_day_exits,
)
from engine.rules import load_rules
from synth import bar

LOT = 100
D0 = date(2020, 1, 21)


@pytest.fixture(scope="module")
def rules():
    return load_rules()


def make_position(shares=200, entry=10.0, stop=9.5):
    return Position(
        symbol="600000",
        setup_id="contrary_strength",
        theme_id="theme_a",
        shares=shares,
        entry_date=D0,
        entry_price=entry,
        support_price=stop,
        stop_loss_price=stop,
    )


class TestFillConstraints:
    def test_buy_at_limit_up_unfillable(self):
        b = bar(0, 10.8, prev_close=10.0, high=11.0)  # 涨停价 11.0
        assert not can_buy_at(b, 11.0).fillable
        assert can_buy_at(b, 11.0).reason == "limit_up_unfillable"
        assert can_buy_at(b, 10.5).fillable

    def test_sell_at_limit_down_unfillable(self):
        b = bar(0, 9.2, prev_close=10.0, low=9.0)  # 跌停价 9.0
        assert not can_sell_at(b, 9.0).fillable
        assert can_sell_at(b, 9.0).reason == "limit_down_unfillable"
        assert can_sell_at(b, 9.5).fillable

    def test_suspended_blocks_both_sides(self):
        b = bar(0, 10.0, suspended=True)
        assert can_buy_at(b, 10.0).reason == "suspended"
        assert can_sell_at(b, 10.0).reason == "suspended"

    def test_missing_limit_price_conservatively_unfillable(self):
        b = bar(0, 10.0, limit_up=None, limit_down=None)
        # synth.bar 会自动填 limit 价，这里显式构造缺失
        from engine.bars import DailyBar

        raw = DailyBar(
            symbol="600000",
            trade_date=b.trade_date,
            open=10.0,
            high=10.2,
            low=9.9,
            close=10.0,
            prev_close=10.0,
            volume=100.0,
            limit_up_price=None,
            limit_down_price=None,
        )
        assert can_buy_at(raw, 10.0).reason == "missing_limit_up_price"
        assert can_sell_at(raw, 10.0).reason == "missing_limit_down_price"


class TestPositionInvariants:
    def test_t_plus_1(self):
        pos = make_position()
        assert not pos.can_sell_on(D0)
        assert pos.can_sell_on(date(2020, 1, 22))

    def test_stop_must_be_below_entry(self):
        with pytest.raises(ValueError):
            make_position(stop=10.5)

    def test_r_multiple_take_profit_price(self):
        pos = make_position(entry=10.0, stop=9.0)
        assert pos.first_take_profit_price == pytest.approx(11.0)

    def test_trailing_stop_never_moves_down(self):
        pos = make_position()
        pos.raise_trailing_stop(9.8)
        pos.raise_trailing_stop(9.6)  # 更低的前日低点不得下移止损
        assert pos.trailing_stop == pytest.approx(9.8)
        pos.raise_trailing_stop(10.1)
        assert pos.trailing_stop == pytest.approx(10.1)
        assert pos.effective_stop() == pytest.approx(10.1)


class TestDayExits:
    def test_stop_detected_on_entry_day_no_same_day_sell(self, rules):
        pos = make_position()
        b = bar(20, 9.4, prev_close=10.0, open_=10.0, high=10.0, low=9.4)  # D0 当天击穿止损
        result = process_day_exits(pos, b, [], rules, LOT)
        assert result.events == []  # T+1：当日不可卖出
        assert len(result.pending_orders) == 1  # 但止损已挂到次日开盘
        assert result.pending_orders[0].reason == "stop_loss_next_open"

    def test_pending_stop_fills_next_open(self, rules):
        pos = make_position()
        day0 = bar(20, 9.4, prev_close=10.0, open_=10.0, high=10.0, low=9.4)
        pending = process_day_exits(pos, day0, [], rules, LOT).pending_orders
        day1 = bar(21, 9.2, prev_close=9.4, open_=9.3, high=9.4, low=9.1)
        result = process_day_exits(pos, day1, pending, rules, LOT)
        assert len(result.events) == 1
        event = result.events[0]
        assert event.reason == "stop_loss_next_open"
        assert event.price == pytest.approx(9.3)  # 次日开盘价成交
        assert event.shares == 200

    def test_limit_down_open_retries_until_filled(self, rules):
        pos = make_position()
        day0 = bar(20, 9.4, prev_close=10.0, open_=10.0, high=10.0, low=9.4)
        pending = process_day_exits(pos, day0, [], rules, LOT).pending_orders
        # 次日开盘一字跌停（prev_close 9.4 → 跌停 8.46）
        day1 = bar(21, 8.46, prev_close=9.4, open_=8.46, high=8.46, low=8.46)
        result1 = process_day_exits(pos, day1, pending, rules, LOT)
        assert result1.events == []
        assert len(result1.limit_unfilled) == 1
        assert result1.pending_orders[0].attempts == 1
        # 第三日打开跌停，正常成交
        day2 = bar(22, 8.2, prev_close=8.46, open_=8.3, high=8.5, low=8.1)
        result2 = process_day_exits(pos, day2, result1.pending_orders, rules, LOT)
        assert len(result2.events) == 1
        assert result2.events[0].price == pytest.approx(8.3)

    def test_no_duplicate_stop_order_while_pending(self, rules):
        pos = make_position()
        day0 = bar(20, 9.4, prev_close=10.0, open_=10.0, high=10.0, low=9.4)
        pending = process_day_exits(pos, day0, [], rules, LOT).pending_orders
        # 次日跌停未成交且当日低点仍低于止损：不得重复挂单
        day1 = bar(21, 8.46, prev_close=9.4, open_=8.46, high=8.46, low=8.46)
        result = process_day_exits(pos, day1, pending, rules, LOT)
        assert len(result.pending_orders) == 1

    def test_first_take_profit_half_after_t1(self, rules):
        pos = make_position(shares=200, entry=10.0, stop=9.5)  # R=0.5 → TP 10.5
        day1 = bar(21, 10.6, prev_close=10.0, open_=10.1, high=10.7, low=10.0)
        result = process_day_exits(pos, day1, [], rules, LOT)
        assert len(result.events) == 1
        event = result.events[0]
        assert event.reason == "first_take_profit_half"
        assert event.shares == 100  # 200 股的一半，整手
        assert event.price == pytest.approx(10.5)
        assert pos.first_take_profit_done

    def test_take_profit_blocked_on_entry_day(self, rules):
        pos = make_position(shares=200, entry=10.0, stop=9.5)
        day0 = bar(20, 10.6, prev_close=10.0, open_=10.1, high=10.7, low=10.0)
        result = process_day_exits(pos, day0, [], rules, LOT)
        assert result.events == []
        assert not pos.first_take_profit_done

    def test_one_lot_position_skips_partial_tp(self, rules):
        pos = make_position(shares=100, entry=10.0, stop=9.5)
        assert first_take_profit_shares(pos, rules, LOT) == 0
        day1 = bar(21, 10.6, prev_close=10.0, open_=10.1, high=10.7, low=10.0)
        result = process_day_exits(pos, day1, [], rules, LOT)
        assert result.events == []  # 半仓不足一手 → 不部分止盈

    def test_trailing_stop_triggers_exit_order(self, rules):
        pos = make_position(shares=200, entry=10.0, stop=9.5)
        pos.first_take_profit_done = True
        pos.raise_trailing_stop(10.2)  # 前日低点抬高后
        day = bar(22, 10.1, prev_close=10.4, open_=10.3, high=10.4, low=10.1)
        result = process_day_exits(pos, day, [], rules, LOT)
        assert len(result.pending_orders) == 1
        assert result.pending_orders[0].reason == "trailing_stop"
