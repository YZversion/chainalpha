"""日频行情数据结构。

涨跌停判断必须用未复权价格与显式涨跌停价字段
（rules.yaml: limit_price_required / adjusted_price_limit_detection_policy=mark_missing）。
limit 价缺失时返回 None（无法判定），由调用方按保守策略处理。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DailyBar:
    symbol: str
    trade_date: date
    open: float
    high: float
    low: float
    close: float
    prev_close: float
    volume: float
    limit_up_price: float | None = None
    limit_down_price: float | None = None
    suspended: bool = False

    @property
    def pct_change(self) -> float:
        return self.close / self.prev_close - 1.0


_PRICE_EPS = 1e-6


def closed_at_limit_up(bar: DailyBar) -> bool | None:
    """收盘涨停；limit 价缺失返回 None。"""
    if bar.limit_up_price is None:
        return None
    return bar.close >= bar.limit_up_price - _PRICE_EPS


def touched_limit_up(bar: DailyBar) -> bool | None:
    if bar.limit_up_price is None:
        return None
    return bar.high >= bar.limit_up_price - _PRICE_EPS


def volume_baseline(bars: list[DailyBar], lookback: int = 20) -> float | None:
    """信号日前 lookback 个交易日的均量（不含信号日）。

    bars 按时间升序、末位为信号日。历史不足返回 None。
    """
    previous = bars[-(lookback + 1) : -1]
    if len(previous) < lookback:
        return None
    return sum(b.volume for b in previous) / lookback
