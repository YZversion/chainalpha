"""风控状态机：连亏冷却 + setup/系统滚动期望停用。

冷却语义（rules.yaml `cooldown` 节，实现口径写死如下，回测复用同一实现）：
- 连续 2 个亏损日 → 减半仓（REDUCE_HALF）
- 连续 3 个亏损日 → 清仓（CLEAR_ALL），进入 3 个交易日冷却
- 冷却期内禁止新开仓；冷却天数走完后，需连续 2 个宽度达标日才恢复
- 恢复后的首个开仓日仓位系数 1/3，此后回到正常
- 非亏损日（当日盈亏 >= 0）重置连亏计数
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any


class CooldownAction(Enum):
    NONE = "none"
    REDUCE_HALF = "reduce_half"
    CLEAR_ALL = "clear_all"


class CooldownPhase(Enum):
    NORMAL = "normal"
    COOLDOWN = "cooldown"
    AWAIT_BREADTH = "await_breadth"
    RESUME_FIRST_ENTRY = "resume_first_entry"


@dataclass
class CooldownTracker:
    losing_days_reduce_half: int
    losing_days_clear_all: int
    cooldown_trading_days: int
    resume_breadth_days: int
    first_entry_fraction: float

    losing_streak: int = 0
    cooldown_days_left: int = 0
    breadth_streak: int = 0
    phase: CooldownPhase = CooldownPhase.NORMAL

    @classmethod
    def from_rules(cls, rules: dict[str, Any]) -> CooldownTracker:
        cfg = rules["cooldown"]
        sizing = rules["position_sizing"]
        return cls(
            losing_days_reduce_half=int(cfg["losing_days_reduce_half"]),
            losing_days_clear_all=int(cfg["losing_days_clear_all"]),
            cooldown_trading_days=int(cfg["clear_all_cooldown_trading_days"]),
            resume_breadth_days=int(cfg["resume_requires_consecutive_breadth_days"]),
            first_entry_fraction=float(sizing["first_day_after_cooldown_position_fraction"]),
        )

    def on_day_close(self, *, day_pnl: float, breadth_ok: bool) -> CooldownAction:
        """每个交易日收盘后调用一次，返回需要执行的动作。"""
        if self.phase in (CooldownPhase.NORMAL, CooldownPhase.RESUME_FIRST_ENTRY):
            if day_pnl < 0:
                self.losing_streak += 1
            else:
                self.losing_streak = 0
            if self.losing_streak >= self.losing_days_clear_all:
                self.losing_streak = 0
                self.breadth_streak = 0
                self.phase = CooldownPhase.COOLDOWN
                self.cooldown_days_left = self.cooldown_trading_days
                return CooldownAction.CLEAR_ALL
            if self.losing_streak == self.losing_days_reduce_half:
                return CooldownAction.REDUCE_HALF
            return CooldownAction.NONE

        if self.phase == CooldownPhase.COOLDOWN:
            self.cooldown_days_left -= 1
            if self.cooldown_days_left <= 0:
                self.phase = CooldownPhase.AWAIT_BREADTH
                self.breadth_streak = 0
            return CooldownAction.NONE

        # AWAIT_BREADTH
        self.breadth_streak = self.breadth_streak + 1 if breadth_ok else 0
        if self.breadth_streak >= self.resume_breadth_days:
            self.phase = CooldownPhase.RESUME_FIRST_ENTRY
        return CooldownAction.NONE

    def entries_allowed(self) -> bool:
        return self.phase in (CooldownPhase.NORMAL, CooldownPhase.RESUME_FIRST_ENTRY)

    def entry_fraction(self) -> float:
        if self.phase is CooldownPhase.RESUME_FIRST_ENTRY:
            return self.first_entry_fraction
        return 1.0

    def on_entry_taken(self) -> None:
        if self.phase is CooldownPhase.RESUME_FIRST_ENTRY:
            self.phase = CooldownPhase.NORMAL


class ExpectancyTracker:
    """滚动 N 笔净期望（net_pnl_pct）；期望 <= 阈值即停用。

    样本不足 window 笔时不停用（rules.yaml 另以 one_lot_only 限制仓位）。
    """

    def __init__(self, window: int, threshold: float = 0.0) -> None:
        self.window = int(window)
        self.threshold = float(threshold)
        self._trades: deque[float] = deque(maxlen=self.window)
        self._total_count = 0

    @classmethod
    def for_setup(cls, rules: dict[str, Any]) -> ExpectancyTracker:
        cfg = rules["validation"]
        return cls(cfg["setup_disable_rolling_trades"], cfg["setup_disable_expectancy_threshold"])

    @classmethod
    def for_system(cls, rules: dict[str, Any]) -> ExpectancyTracker:
        cfg = rules["validation"]
        return cls(cfg["system_disable_rolling_trades"], cfg["system_disable_expectancy_threshold"])

    def record(self, net_pnl_pct: float) -> None:
        self._trades.append(float(net_pnl_pct))
        self._total_count += 1

    @property
    def sample_count(self) -> int:
        return self._total_count

    def rolling_expectancy(self) -> float | None:
        if len(self._trades) < self.window:
            return None
        return sum(self._trades) / len(self._trades)

    @property
    def should_disable(self) -> bool:
        expectancy = self.rolling_expectancy()
        return expectancy is not None and expectancy <= self.threshold
