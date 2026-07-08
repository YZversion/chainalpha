"""执行约束与出场规则：T+1、涨跌停不可成交、止损/止盈/移动止损。

保守撮合假设（data_requirements.md）：
- 触及涨停买入、跌停卖出一律按不可成交处理（无盘口排队数据）
- limit 价缺失时无法判定 → 不可成交（mark_missing 的保守面）
- 止损在盘中触发后于次一交易日开盘卖出；开盘跌停/停牌则顺延重试
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from .bars import DailyBar

_PRICE_EPS = 1e-6


@dataclass
class FillCheck:
    fillable: bool
    reason: str | None = None


def can_buy_at(bar: DailyBar, price: float) -> FillCheck:
    if bar.suspended:
        return FillCheck(False, "suspended")
    if bar.limit_up_price is None:
        return FillCheck(False, "missing_limit_up_price")
    if price >= bar.limit_up_price - _PRICE_EPS:
        return FillCheck(False, "limit_up_unfillable")
    return FillCheck(True)


def can_sell_at(bar: DailyBar, price: float) -> FillCheck:
    if bar.suspended:
        return FillCheck(False, "suspended")
    if bar.limit_down_price is None:
        return FillCheck(False, "missing_limit_down_price")
    if price <= bar.limit_down_price + _PRICE_EPS:
        return FillCheck(False, "limit_down_unfillable")
    return FillCheck(True)


@dataclass
class Position:
    symbol: str
    setup_id: str
    theme_id: str
    shares: int
    entry_date: date
    entry_price: float
    support_price: float
    stop_loss_price: float
    first_take_profit_done: bool = False
    trailing_stop: float | None = None

    def __post_init__(self) -> None:
        # 买入时支撑与止损必须锁死；此处仅校验合法性，不允许后续下移
        if self.stop_loss_price >= self.entry_price:
            raise ValueError("stop_loss_price must be below entry_price")

    def can_sell_on(self, trade_date: date) -> bool:
        """T+1：买入当日不可卖出。"""
        return trade_date > self.entry_date

    @property
    def r_value(self) -> float:
        return self.entry_price - self.stop_loss_price

    @property
    def first_take_profit_price(self) -> float:
        return self.entry_price + self.r_value

    def raise_trailing_stop(self, reference_low: float) -> None:
        """移动止损参照前一日最低价，只升不降。"""
        if self.trailing_stop is None or reference_low > self.trailing_stop:
            self.trailing_stop = reference_low

    def effective_stop(self) -> float:
        if self.trailing_stop is not None:
            return max(self.stop_loss_price, self.trailing_stop)
        return self.stop_loss_price


@dataclass
class ExitOrder:
    """止损触发后挂到次日开盘的卖出指令；跌停/停牌未成交则顺延。"""

    symbol: str
    shares: int
    reason: str
    created_date: date
    attempts: int = 0


@dataclass
class ExitEvent:
    symbol: str
    shares: int
    reason: str
    price: float
    trade_date: date


@dataclass
class DayExitResult:
    events: list[ExitEvent] = field(default_factory=list)
    pending_orders: list[ExitOrder] = field(default_factory=list)
    limit_unfilled: list[ExitOrder] = field(default_factory=list)


def first_take_profit_shares(position: Position, rules: dict[str, Any], lot_size: int) -> int:
    """首次止盈卖出一半，向下取整到整手；不足一手则不部分止盈。"""
    fraction = float(rules["exit"]["take_profit"]["first_take_profit_fraction"])
    lots = int(position.shares * fraction) // lot_size
    return lots * lot_size


def process_day_exits(
    position: Position,
    bar: DailyBar,
    pending_orders: list[ExitOrder],
    rules: dict[str, Any],
    lot_size: int,
) -> DayExitResult:
    """单持仓单日出场处理（日频粒度；分时卖出信号需分钟数据，另行实现）。

    顺序：1) 处理挂单（次日开盘止损）；2) 首次止盈（受 T+1 限制）；
    3) 盘中触及有效止损 → 生成次日开盘卖出挂单（检测不受 T+1 限制，
       因为实际卖出发生在次一交易日）。
    """
    result = DayExitResult()
    remaining = position.shares

    for order in pending_orders:
        check = can_sell_at(bar, bar.open)
        if check.fillable and position.can_sell_on(bar.trade_date):
            result.events.append(
                ExitEvent(order.symbol, order.shares, order.reason, bar.open, bar.trade_date)
            )
            remaining -= order.shares
        else:
            order.attempts += 1
            result.limit_unfilled.append(order)
            result.pending_orders.append(order)

    if remaining <= 0:
        return result

    can_sell_today = position.can_sell_on(bar.trade_date)

    if (
        can_sell_today
        and not position.first_take_profit_done
        and bar.high >= position.first_take_profit_price
    ):
        tp_shares = first_take_profit_shares(position, rules, lot_size)
        tp_shares = min(tp_shares, remaining)
        if tp_shares > 0:
            check = can_sell_at(bar, position.first_take_profit_price)
            if check.fillable:
                result.events.append(
                    ExitEvent(
                        position.symbol,
                        tp_shares,
                        "first_take_profit_half",
                        position.first_take_profit_price,
                        bar.trade_date,
                    )
                )
                position.first_take_profit_done = True
                remaining -= tp_shares

    already_pending = bool(result.pending_orders)
    if (
        remaining > 0
        and not already_pending
        and bar.low <= position.effective_stop() + _PRICE_EPS
    ):
        reason = "trailing_stop" if position.trailing_stop is not None else "stop_loss_next_open"
        result.pending_orders.append(
            ExitOrder(position.symbol, remaining, reason, bar.trade_date)
        )

    return result
