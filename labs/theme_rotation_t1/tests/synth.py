"""合成日线数据工厂（仅用于规则单测，不代表任何真实行情）。"""

from __future__ import annotations

from datetime import date, timedelta

from engine.bars import DailyBar

BASE_DATE = date(2020, 1, 1)


def bar(
    i: int,
    close: float,
    *,
    open_: float | None = None,
    high: float | None = None,
    low: float | None = None,
    prev_close: float | None = None,
    volume: float = 100.0,
    limit_up: float | None = None,
    limit_down: float | None = None,
    suspended: bool = False,
    symbol: str = "600000",
) -> DailyBar:
    prev_close = prev_close if prev_close is not None else close
    open_ = open_ if open_ is not None else prev_close
    high = high if high is not None else max(open_, close)
    low = low if low is not None else min(open_, close)
    return DailyBar(
        symbol=symbol,
        trade_date=BASE_DATE + timedelta(days=i),
        open=open_,
        high=high,
        low=low,
        close=close,
        prev_close=prev_close,
        volume=volume,
        limit_up_price=limit_up if limit_up is not None else round(prev_close * 1.1, 2),
        limit_down_price=limit_down if limit_down is not None else round(prev_close * 0.9, 2),
        suspended=suspended,
    )


def flat_history(n: int = 21, close: float = 10.0, volume: float = 100.0) -> list[DailyBar]:
    """n 根横盘小实体 K 线，均量 volume，无涨停。"""
    return [bar(i, close, volume=volume) for i in range(n)]
