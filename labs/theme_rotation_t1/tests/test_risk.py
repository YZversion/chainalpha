"""连亏冷却状态机与滚动期望停用测试。"""

import pytest
from engine.risk import CooldownAction, CooldownPhase, CooldownTracker, ExpectancyTracker
from engine.rules import load_rules


@pytest.fixture(scope="module")
def rules():
    return load_rules()


@pytest.fixture()
def tracker(rules):
    return CooldownTracker.from_rules(rules)


class TestCooldown:
    def test_two_losing_days_reduce_half(self, tracker):
        assert tracker.on_day_close(day_pnl=-100, breadth_ok=True) is CooldownAction.NONE
        assert tracker.on_day_close(day_pnl=-50, breadth_ok=True) is CooldownAction.REDUCE_HALF

    def test_three_losing_days_clear_all_and_block_entries(self, tracker):
        tracker.on_day_close(day_pnl=-100, breadth_ok=True)
        tracker.on_day_close(day_pnl=-100, breadth_ok=True)
        action = tracker.on_day_close(day_pnl=-100, breadth_ok=True)
        assert action is CooldownAction.CLEAR_ALL
        assert not tracker.entries_allowed()

    def test_winning_day_resets_streak(self, tracker):
        tracker.on_day_close(day_pnl=-100, breadth_ok=True)
        tracker.on_day_close(day_pnl=200, breadth_ok=True)
        tracker.on_day_close(day_pnl=-100, breadth_ok=True)
        action = tracker.on_day_close(day_pnl=-100, breadth_ok=True)
        assert action is CooldownAction.REDUCE_HALF  # 重新累计到 2，而不是 3

    def _enter_cooldown(self, tracker):
        for _ in range(3):
            tracker.on_day_close(day_pnl=-100, breadth_ok=True)

    def test_full_recovery_sequence(self, tracker):
        self._enter_cooldown(tracker)
        # 冷却 3 个交易日：期间禁止开仓
        for _ in range(3):
            assert not tracker.entries_allowed()
            tracker.on_day_close(day_pnl=0, breadth_ok=True)
        # 冷却结束仍需连续 2 个宽度达标日
        assert tracker.phase is CooldownPhase.AWAIT_BREADTH
        assert not tracker.entries_allowed()
        tracker.on_day_close(day_pnl=0, breadth_ok=True)
        assert not tracker.entries_allowed()
        tracker.on_day_close(day_pnl=0, breadth_ok=True)
        # 恢复后首个开仓日仓位 1/3
        assert tracker.entries_allowed()
        assert tracker.entry_fraction() == pytest.approx(1 / 3, rel=1e-6)
        tracker.on_entry_taken()
        assert tracker.phase is CooldownPhase.NORMAL
        assert tracker.entry_fraction() == 1.0

    def test_breadth_break_resets_resume_streak(self, tracker):
        self._enter_cooldown(tracker)
        for _ in range(3):
            tracker.on_day_close(day_pnl=0, breadth_ok=True)
        tracker.on_day_close(day_pnl=0, breadth_ok=True)   # 达标 1 天
        tracker.on_day_close(day_pnl=0, breadth_ok=False)  # 中断 → 清零
        tracker.on_day_close(day_pnl=0, breadth_ok=True)
        assert not tracker.entries_allowed()
        tracker.on_day_close(day_pnl=0, breadth_ok=True)
        assert tracker.entries_allowed()


class TestExpectancyDisable:
    def test_setup_disable_after_30_negative_trades(self, rules):
        tracker = ExpectancyTracker.for_setup(rules)
        for _ in range(29):
            tracker.record(-0.01)
        assert not tracker.should_disable  # 不足 30 笔不停用
        tracker.record(-0.01)
        assert tracker.should_disable

    def test_positive_expectancy_not_disabled(self, rules):
        tracker = ExpectancyTracker.for_setup(rules)
        for _ in range(30):
            tracker.record(0.01)
        assert not tracker.should_disable

    def test_zero_expectancy_disables(self, rules):
        tracker = ExpectancyTracker.for_setup(rules)
        for _ in range(15):
            tracker.record(0.01)
        for _ in range(15):
            tracker.record(-0.01)
        assert tracker.rolling_expectancy() == pytest.approx(0.0)
        assert tracker.should_disable  # 阈值为 <= 0

    def test_rolling_window_recovers(self, rules):
        tracker = ExpectancyTracker.for_setup(rules)
        for _ in range(30):
            tracker.record(-0.02)
        assert tracker.should_disable
        for _ in range(30):
            tracker.record(0.02)
        assert not tracker.should_disable  # 最近 30 笔全部盈利

    def test_system_uses_60_trade_window(self, rules):
        tracker = ExpectancyTracker.for_system(rules)
        for _ in range(59):
            tracker.record(-0.01)
        assert not tracker.should_disable
        tracker.record(-0.01)
        assert tracker.should_disable
