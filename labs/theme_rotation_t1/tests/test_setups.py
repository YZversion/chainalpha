"""四个 setup 检测器的合成数据测试。"""

import pytest
from engine.rules import load_rules
from engine.setups import (
    detect_contrary_strength,
    detect_first_to_second_limit_up,
    detect_recent_limit_up_or_double_volume,
    detect_volume_long_upper_shadow,
)
from synth import bar, flat_history


@pytest.fixture(scope="module")
def rules():
    return load_rules()


class TestRecentLimitUpOrDoubleVolume:
    def test_double_volume_triggers(self, rules):
        bars = flat_history(21)
        bars[-1] = bar(20, 10.0, volume=250.0)  # 基准均量 100，2.5 倍
        signal = detect_recent_limit_up_or_double_volume(bars, rules)
        assert signal.triggered
        assert "double_volume" in signal.reasons

    def test_recent_limit_up_triggers(self, rules):
        bars = flat_history(21)
        # 窗口内一根收盘涨停（prev_close 10 → 涨停价 11，收盘 11）
        bars[15] = bar(15, 11.0, prev_close=10.0, open_=10.2, high=11.0, low=10.1)
        signal = detect_recent_limit_up_or_double_volume(bars, rules)
        assert signal.triggered
        assert "recent_limit_up" in signal.reasons

    def test_flat_no_trigger(self, rules):
        bars = flat_history(21)
        bars[-1] = bar(20, 10.0, volume=150.0)  # 1.5 倍不足 2 倍
        signal = detect_recent_limit_up_or_double_volume(bars, rules)
        assert not signal.triggered

    def test_insufficient_history_marks_missing(self, rules):
        signal = detect_recent_limit_up_or_double_volume(flat_history(10), rules)
        assert not signal.triggered
        assert "insufficient_history" in signal.missing


class TestVolumeLongUpperShadow:
    def test_triggers(self, rules):
        bars = flat_history(21)
        # 上影 0.9（9% > 5%），上影/振幅 0.9/1.1 ≈ 0.82 > 0.5，量 1.6 倍
        bars[-1] = bar(20, 10.1, open_=10.0, high=11.0, low=9.9, volume=160.0)
        signal = detect_volume_long_upper_shadow(bars, rules)
        assert signal.triggered

    def test_zero_range_skipped(self, rules):
        bars = flat_history(21)
        bars[-1] = bar(20, 10.0, open_=10.0, high=10.0, low=10.0, volume=300.0)
        signal = detect_volume_long_upper_shadow(bars, rules)
        assert not signal.triggered
        assert "zero_range_skip" in signal.reasons

    def test_volume_too_low(self, rules):
        bars = flat_history(21)
        bars[-1] = bar(20, 10.1, open_=10.0, high=11.0, low=9.9, volume=120.0)
        assert not detect_volume_long_upper_shadow(bars, rules).triggered

    def test_shadow_too_short(self, rules):
        bars = flat_history(21)
        # 上影 0.4（4% < 5%）
        bars[-1] = bar(20, 10.5, open_=10.0, high=10.9, low=9.9, volume=200.0)
        assert not detect_volume_long_upper_shadow(bars, rules).triggered


class TestFirstToSecondLimitUp:
    def _first_board_bars(self):
        bars = flat_history(21)
        bars[-1] = bar(20, 11.0, prev_close=10.0, open_=10.2, high=11.0, low=10.1)
        return bars

    def test_triggers_for_small_cap(self, rules):
        signal = detect_first_to_second_limit_up(
            self._first_board_bars(), rules, free_float_mcap_percentile=0.20
        )
        assert signal.triggered

    def test_large_cap_rejected(self, rules):
        signal = detect_first_to_second_limit_up(
            self._first_board_bars(), rules, free_float_mcap_percentile=0.50
        )
        assert not signal.triggered

    def test_missing_mcap_percentile(self, rules):
        signal = detect_first_to_second_limit_up(
            self._first_board_bars(), rules, free_float_mcap_percentile=None
        )
        assert not signal.triggered
        assert "free_float_market_cap_percentile" in signal.missing

    def test_prior_limit_up_disqualifies(self, rules):
        bars = self._first_board_bars()
        bars[10] = bar(10, 11.0, prev_close=10.0, open_=10.1, high=11.0, low=10.0)
        signal = detect_first_to_second_limit_up(bars, rules, free_float_mcap_percentile=0.20)
        assert not signal.triggered

    def test_no_limit_up_no_signal(self, rules):
        signal = detect_first_to_second_limit_up(
            flat_history(21), rules, free_float_mcap_percentile=0.20
        )
        assert not signal.triggered


class TestContraryStrength:
    def _strong_bar_history(self):
        bars = flat_history(21)
        # 弱市中放量收阳 +4%
        bars[-1] = bar(20, 10.4, prev_close=10.0, open_=10.0, high=10.5, low=9.95, volume=160.0)
        return bars

    def test_triggers_in_weak_market(self, rules):
        signal = detect_contrary_strength(
            self._strong_bar_history(), rules, prev_day_advancers_ratio=0.35
        )
        assert signal.triggered

    def test_not_weak_market(self, rules):
        signal = detect_contrary_strength(
            self._strong_bar_history(), rules, prev_day_advancers_ratio=0.55
        )
        assert not signal.triggered

    def test_missing_breadth(self, rules):
        signal = detect_contrary_strength(
            self._strong_bar_history(), rules, prev_day_advancers_ratio=None
        )
        assert not signal.triggered
        assert "prev_day_advancers_ratio" in signal.missing

    def test_close_below_open_rejected(self, rules):
        bars = flat_history(21)
        # 涨幅够但收盘低于开盘（冲高回落）
        bars[-1] = bar(20, 10.4, prev_close=10.0, open_=10.6, high=10.7, low=10.0, volume=160.0)
        signal = detect_contrary_strength(bars, rules, prev_day_advancers_ratio=0.35)
        assert not signal.triggered

    def test_return_below_3pct_rejected(self, rules):
        bars = flat_history(21)
        bars[-1] = bar(20, 10.2, prev_close=10.0, open_=10.0, high=10.3, low=9.95, volume=160.0)
        signal = detect_contrary_strength(bars, rules, prev_day_advancers_ratio=0.35)
        assert not signal.triggered
