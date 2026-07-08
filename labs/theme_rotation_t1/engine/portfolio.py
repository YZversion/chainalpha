"""仓位分配：风险预算公式、份额切分、整手、相关性与总仓位约束。

rules.yaml 中 tolerated_account_drawdown_pct 与 overnight_gap_risk_pct.default
当前为 [MISSING]：本模块不提供默认值，参数缺失时直接返回 skip，
原因记为 missing_param。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .costs import CostModel
from .filters import FilterDecision
from .rules import MISSING, is_missing

MISSING_THEME_ID = "[MISSING]"


@dataclass(frozen=True)
class SizingDecision:
    shares: int
    cash_required: float
    skipped: bool
    reason: str | None = None


def risk_position_cash_cap(
    equity: float,
    tolerated_account_drawdown_pct: float | Any,
    overnight_gap_risk_pct: float | Any,
) -> float | Any:
    """公式：equity * tolerated_dd / gap_risk。任一参数缺失返回 MISSING。"""
    if is_missing(tolerated_account_drawdown_pct) or tolerated_account_drawdown_pct is None:
        return MISSING
    if is_missing(overnight_gap_risk_pct) or overnight_gap_risk_pct is None:
        return MISSING
    return equity * float(tolerated_account_drawdown_pct) / float(overnight_gap_risk_pct)


def slice_cash(equity: float, n_slices: int, rules: dict[str, Any]) -> float:
    cfg = rules["position_sizing"]
    if not int(cfg["slices_min"]) <= n_slices <= int(cfg["slices_max"]):
        raise ValueError(
            f"n_slices={n_slices} outside [{cfg['slices_min']}, {cfg['slices_max']}]"
        )
    return equity / n_slices


def size_position(
    price: float,
    cash_cap: float | Any,
    cost_model: CostModel,
    *,
    one_lot_only: bool = False,
    entry_fraction: float = 1.0,
) -> SizingDecision:
    """按现金上限计算整手股数（含滑点与佣金后的现金需求不得超上限）。

    - cash_cap 为 MISSING → skip（missing_param）
    - 一手都买不起 → skip（one_lot_exceeds_risk_cap，政策 skip_trade）
    - one_lot_only：样本不足 30 笔的 setup 只允许一手
    - entry_fraction：冷却期恢复首日 1/3 仓位等场景
    """
    if is_missing(cash_cap) or cash_cap is None:
        return SizingDecision(0, 0.0, True, "missing_param")

    effective_cap = float(cash_cap) * entry_fraction
    lot = cost_model.lot_size
    fill = cost_model.buy_fill_price(price)
    if fill <= 0:
        return SizingDecision(0, 0.0, True, "invalid_price")

    lots = math.floor(effective_cap / (fill * lot))
    if one_lot_only:
        lots = min(lots, 1)
    while lots > 0:
        shares = lots * lot
        cash_required = cost_model.buy_cash_outflow(price, shares)
        if cash_required <= effective_cap:
            return SizingDecision(shares, cash_required, False)
        lots -= 1
    return SizingDecision(0, 0.0, True, "one_lot_exceeds_risk_cap")


@dataclass(frozen=True)
class OpenPosition:
    symbol: str
    setup_id: str
    theme_id: str
    market_value: float = 0.0


def correlation_allows(
    open_positions: list[OpenPosition],
    setup_id: str,
    theme_id: str,
    rules: dict[str, Any],
) -> FilterDecision:
    """同 setup 最多 3 只、同题材最多 2 只。

    题材缺失记为 [MISSING]，所有缺失题材共享同一桶（保守处理：
    无法证明不同题材就当作同题材计数）。
    """
    cfg = rules["correlation_limits"]
    reasons: list[str] = []

    same_setup = sum(1 for p in open_positions if p.setup_id == setup_id)
    if same_setup >= int(cfg["max_positions_per_setup"]):
        reasons.append("max_positions_per_setup")

    same_theme = sum(1 for p in open_positions if p.theme_id == theme_id)
    if same_theme >= int(cfg["max_positions_per_theme"]):
        reasons.append("max_positions_per_theme")

    return FilterDecision(not reasons, reasons)


def position_caps_allow(
    equity: float,
    invested_market_value: float,
    new_position_cash: float,
    rules: dict[str, Any],
) -> FilterDecision:
    """总仓位 <= 85%，现金 >= 15%。"""
    cfg = rules["account"]
    reasons: list[str] = []
    after_invested = invested_market_value + new_position_cash
    if after_invested > equity * float(cfg["total_position_max_pct"]):
        reasons.append("total_position_above_max")
    if (equity - after_invested) < equity * float(cfg["cash_min_pct"]):
        reasons.append("cash_below_min")
    return FilterDecision(not reasons, reasons)
