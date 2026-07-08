"""非完整可执行回测主循环：复用 engine/ 规则，不重新实现策略逻辑。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from engine.bars import DailyBar
from engine.costs import CostModel
from engine.execution import (
    ExitOrder,
    Position,
    can_buy_at,
    process_day_exits,
)
from engine.filters import (
    EventRiskInputs,
    event_risk_filter,
    market_state_allows_buy,
)
from engine.portfolio import (
    MISSING_THEME_ID,
    OpenPosition,
    correlation_allows,
    position_caps_allow,
    risk_position_cash_cap,
    size_position,
    slice_cash,
)
from engine.risk import CooldownTracker, ExpectancyTracker
from engine.rules import is_missing, load_rules
from engine.setups import (
    SETUP_CONTRARY_STRENGTH,
    SETUP_FIRST_TO_SECOND_LIMIT_UP,
    SETUP_RECENT_LIMIT_UP_OR_DOUBLE_VOLUME,
    SETUP_VOLUME_LONG_UPPER_SHADOW,
    detect_contrary_strength,
    detect_first_to_second_limit_up,
    detect_recent_limit_up_or_double_volume,
    detect_volume_long_upper_shadow,
)

SETUP_IDS = [
    SETUP_RECENT_LIMIT_UP_OR_DOUBLE_VOLUME,
    SETUP_VOLUME_LONG_UPPER_SHADOW,
    SETUP_FIRST_TO_SECOND_LIMIT_UP,
    SETUP_CONTRARY_STRENGTH,
]

TRAIN_START = date(2018, 1, 1)
TRAIN_END = date(2021, 12, 31)
VAL_START = date(2022, 1, 1)
VAL_END = date(2023, 12, 31)


@dataclass
class TradeRecord:
    symbol: str
    setup_id: str
    entry_date: date
    exit_date: date | None
    entry_price: float
    exit_price: float | None
    shares: int
    net_pnl: float
    net_pnl_pct: float
    commission: float
    stamp_tax: float
    slippage: float
    hold_days: int
    limit_unfilled: bool
    skip_reason: str | None = None


@dataclass
class BacktestResult:
    title: str
    split: str
    trading_days: int
    setup_signal_counts: dict[str, int]
    setup_missing_counts: dict[str, int]
    entries_attempted: int
    entries_blocked_breadth: int
    entries_blocked_sizing: int
    entries_blocked_event: int
    entries_blocked_correlation: int
    entries_blocked_caps: int
    entries_blocked_fill: int
    trades: list[TradeRecord]
    limit_unfilled_events: int
    final_equity: float
    ingest_note: str
    degraded_notes: list[str] = field(default_factory=list)


def _period_label(d: date) -> str | None:
    if TRAIN_START <= d <= TRAIN_END:
        return "train"
    if VAL_START <= d <= VAL_END:
        return "validation"
    return None


def _eod_advancers_ratio(bars_today: dict[str, DailyBar]) -> float | None:
    """收盘上涨家数占比（仅用于 contrary_strength 信号日检测，非盘中买入门槛）。"""
    if not bars_today:
        return None
    ups = 0
    total = 0
    for bar in bars_today.values():
        if bar.suspended or bar.prev_close <= 0:
            continue
        total += 1
        if bar.close > bar.prev_close:
            ups += 1
    if total == 0:
        return None
    return ups / total


def _bars_history(
    panel: dict[str, list[DailyBar]], sym: str, as_of: date, n: int
) -> list[DailyBar] | None:
    series = panel.get(sym)
    if not series:
        return None
    hist = [b for b in series if b.trade_date <= as_of]
    if len(hist) < n:
        return None
    return hist[-n:]


@dataclass
class SetupScanHit:
    symbol: str
    setup_id: str
    triggered: bool
    missing: list[str]


def scan_setups(
    panel: dict[str, list[DailyBar]],
    signal_date: date,
    rules: dict[str, Any],
    prev_advancers: float | None,
) -> list[SetupScanHit]:
    """扫描信号日 setup 触发与缺失字段。"""
    out: list[SetupScanHit] = []
    for sym in panel:
        bars = _bars_history(panel, sym, signal_date, 21)
        if bars is None:
            continue
        checks = [
            detect_recent_limit_up_or_double_volume(bars, rules),
            detect_volume_long_upper_shadow(bars, rules),
            detect_first_to_second_limit_up(bars, rules, free_float_mcap_percentile=None),
            detect_contrary_strength(bars, rules, prev_advancers),
        ]
        for sig in checks:
            if sig.triggered or sig.missing:
                out.append(
                    SetupScanHit(sym, sig.setup_id, sig.triggered, list(sig.missing))
                )
    return out


def run_degraded_backtest(
    panel: dict[str, list[DailyBar]],
    *,
    split: str,
    cost_model: CostModel,
    ingest_note: str,
) -> BacktestResult:
    """日频降级回测：盘中宽度 [MISSING] → 按规则不买入；仓位参数 [MISSING] → 跳过 sizing。"""
    rules = load_rules()
    title = "非完整可执行回测"

    if split == "train":
        d0, d1 = TRAIN_START, TRAIN_END
    elif split == "validation":
        d0, d1 = VAL_START, VAL_END
    else:
        raise ValueError(f"unknown split: {split}")

    all_dates = sorted(
        {
            b.trade_date
            for series in panel.values()
            for b in series
            if d0 <= b.trade_date <= d1
        }
    )

    cash = float(cost_model.initial_account)
    positions: dict[str, Position] = {}
    pending: dict[str, list[ExitOrder]] = defaultdict(list)
    open_meta: dict[str, OpenPosition] = {}
    cooldown = CooldownTracker.from_rules(rules)
    system_exp = ExpectancyTracker.for_system(rules)

    setup_signals: dict[str, int] = defaultdict(int)
    setup_missing: dict[str, int] = defaultdict(int)
    trades: list[TradeRecord] = []
    blocked = defaultdict(int)
    limit_unfilled = 0

    degraded = [
        "intraday_breadth=[MISSING]: 买入门槛按 mark_missing_no_trade，不产生新仓",
        "tolerated_account_drawdown_pct=[MISSING]: 仓位公式跳过 (missing_param)",
        "无分钟数据: 不验证 10:40/14:40 买点与分时卖出",
        "limit_prices: 由昨收+板块规则推导，ST 状态 [MISSING]",
        "theme_id=[MISSING]: 相关性约束保守计数",
        "事件风险字段 [MISSING]: 保守排除全部候选",
    ]

    prev_advancers: float | None = None
    n_slices = int(rules["position_sizing"]["slices_min"])

    for trade_date in all_dates:
        bars_today = {
            sym: next(b for b in series if b.trade_date == trade_date)
            for sym, series in panel.items()
            if any(b.trade_date == trade_date for b in series)
        }
        eod_ratio = _eod_advancers_ratio(bars_today)

        day_start_equity = cash + sum(
            open_meta[s].market_value for s in open_meta
        )

        # --- exits ---
        for sym in list(positions.keys()):
            bar = bars_today.get(sym)
            if bar is None:
                continue
            pos = positions[sym]
            if pos.first_take_profit_done and trade_date > pos.entry_date:
                prev_bar = _bars_history(panel, sym, trade_date, 2)
                if prev_bar and len(prev_bar) >= 2:
                    pos.raise_trailing_stop(prev_bar[-2].low)
            result = process_day_exits(
                pos, bar, pending[sym], rules, cost_model.lot_size
            )
            limit_unfilled += len(result.limit_unfilled)
            pending[sym] = result.pending_orders
            for evt in result.events:
                proceeds = cost_model.sell_cash_inflow(evt.price, evt.shares)
                cash += proceeds
                pos.shares -= evt.shares
                if pos.shares <= 0:
                    del positions[sym]
                    del open_meta[sym]
                    pending.pop(sym, None)
                else:
                    open_meta[sym] = OpenPosition(
                        sym, pos.setup_id, pos.theme_id,
                        market_value=pos.shares * bar.close,
                    )

        # --- signal scan (signal day = previous trading day) ---
        idx = all_dates.index(trade_date)
        if idx > 0:
            signal_date = all_dates[idx - 1]
            candidates = scan_setups(panel, signal_date, rules, prev_advancers)
            for hit in candidates:
                if hit.missing:
                    setup_missing[hit.setup_id] += 1
                if not hit.triggered:
                    continue
                setup_signals[hit.setup_id] += 1

                if not cooldown.entries_allowed() or system_exp.should_disable:
                    continue

                breadth = market_state_allows_buy(None, rules)
                if not breadth.passed:
                    blocked["breadth"] += 1
                    continue

                bar = bars_today.get(hit.symbol)
                if bar is None:
                    continue

                evt = EventRiskInputs(None, None, None, None, None)
                evf = event_risk_filter(evt, rules)
                if not evf.passed:
                    blocked["event"] += 1
                    continue

                corr = correlation_allows(
                    list(open_meta.values()), hit.setup_id, MISSING_THEME_ID, rules
                )
                if not corr.passed:
                    blocked["correlation"] += 1
                    continue

                equity = cash + sum(m.market_value for m in open_meta.values())
                gap = rules["position_sizing"]["overnight_gap_risk_pct"]["default"]
                cap = risk_position_cash_cap(
                    equity,
                    rules["position_sizing"]["tolerated_account_drawdown_pct"],
                    gap,
                )
                slice_amt = slice_cash(equity, n_slices, rules)
                cash_cap = slice_amt if is_missing(cap) else min(slice_amt, float(cap))
                sizing = size_position(
                    bar.open,
                    cash_cap,
                    cost_model,
                    one_lot_only=True,
                    entry_fraction=cooldown.entry_fraction(),
                )
                if sizing.skipped:
                    blocked["sizing"] += 1
                    continue

                buy_check = can_buy_at(bar, bar.open)
                if not buy_check.fillable:
                    blocked["fill"] += 1
                    continue

                caps = position_caps_allow(
                    equity,
                    sum(m.market_value for m in open_meta.values()),
                    sizing.cash_required,
                    rules,
                )
                if not caps.passed:
                    blocked["caps"] += 1
                    continue

                blocked["unexpected_path"] += 1

        day_end_equity = cash + sum(
            open_meta[s].market_value for s in open_meta
        )
        day_pnl = day_end_equity - day_start_equity
        breadth_ok = eod_ratio is not None and eod_ratio >= float(
            rules["market_state"]["buy_advancers_ratio_min"]
        )
        cooldown.on_day_close(day_pnl=day_pnl, breadth_ok=breadth_ok)
        prev_advancers = eod_ratio

    final_equity = cash + sum(m.market_value for m in open_meta.values())

    return BacktestResult(
        title=title,
        split=split,
        trading_days=len(all_dates),
        setup_signal_counts=dict(setup_signals),
        setup_missing_counts=dict(setup_missing),
        entries_attempted=sum(blocked.values()),
        entries_blocked_breadth=blocked["breadth"],
        entries_blocked_sizing=blocked["sizing"],
        entries_blocked_event=blocked["event"],
        entries_blocked_correlation=blocked["correlation"],
        entries_blocked_caps=blocked["caps"],
        entries_blocked_fill=blocked["fill"],
        trades=trades,
        limit_unfilled_events=limit_unfilled,
        final_equity=final_equity,
        ingest_note=ingest_note,
        degraded_notes=degraded,
    )
