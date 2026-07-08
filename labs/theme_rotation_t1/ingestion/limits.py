"""涨跌停价规则推导（cross-check only，非行情源字段）。

A 股涨跌幅限制按板块规则从昨收推导；ST 状态缺失时不猜测，使用主板默认 10%
并在元数据中标注 `st_status=[MISSING]`。结果用于引擎 `limit_up_price` / `limit_down_price`
字段，推导逻辑与 `source_matrix.yaml` 中 derived 候选一致。
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class LimitDerivation:
    limit_up_price: float
    limit_down_price: float
    limit_pct: float
    st_status: str  # "known_false" | "[MISSING]"


def _round_price(price: float) -> float:
    return round(price, 2)


def board_limit_pct(symbol: str, *, is_st: bool | None = None) -> float:
    """板块涨跌幅限制；ST 已知时 5%，未知时不单独假设 ST。"""
    if is_st is True:
        return 0.05
    code = symbol.split(".")[0] if "." in symbol else symbol
    if code.startswith("688") or code.startswith("300"):
        return 0.20
    if code.startswith("8") or code.startswith("4"):
        return 0.30
    return 0.10


def derive_limit_prices(
    prev_close: float,
    symbol: str,
    *,
    is_st: bool | None = None,
) -> LimitDerivation:
    if prev_close <= 0:
        raise ValueError("prev_close must be positive")
    pct = board_limit_pct(symbol, is_st=is_st)
    up = _round_price(prev_close * (1 + pct))
    down = _round_price(prev_close * (1 - pct))
    st_status = "known_false" if is_st is False else ("known_true" if is_st else "[MISSING]")
    return LimitDerivation(
        limit_up_price=up,
        limit_down_price=down,
        limit_pct=pct,
        st_status=st_status,
    )


def price_tick_ok(price: float) -> bool:
    """简单校验价格是否为常见 A 股价档（0.01）。"""
    return math.isfinite(price) and abs(price * 100 - round(price * 100)) < 1e-6
