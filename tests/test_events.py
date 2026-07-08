"""合成 K 线：信号定义单元测试。"""

from __future__ import annotations

import pandas as pd

from chainalpha.factors.bars import normalize_ohlcv
from chainalpha.factors.events import (
    limit_up_in_past_month,
    volume_spike_long_upper_shadow,
)


def _make_bars(rows: list[dict], symbol: str = "000001") -> pd.DataFrame:
    base = pd.DataFrame(rows)
    base["symbol"] = symbol
    return normalize_ohlcv(base)


class TestVolumeSpikeLongUpperShadow:
    def test_detects_spike_and_long_upper_shadow(self) -> None:
        # 19 日打底成交量，第 20 日放量长上影
        rows = []
        for i in range(19):
            rows.append(
                {
                    "trade_date": f"2024-01-{i + 1:02d}",
                    "open": 10.0,
                    "high": 10.2,
                    "low": 9.8,
                    "close": 10.0,
                    "volume": 1000.0,
                }
            )
        rows.append(
            {
                "trade_date": "2024-01-20",
                "open": 10.0,
                "high": 12.0,  # 长上影
                "low": 9.9,
                "close": 10.1,  # 小阳线
                "volume": 5000.0,  # 5x 均量
            }
        )
        df = _make_bars(rows)
        mask = volume_spike_long_upper_shadow(df)
        assert bool(mask.iloc[-1]) is True
        assert mask.iloc[:-1].sum() == 0

    def test_normal_bar_not_triggered(self) -> None:
        rows = [
            {
                "trade_date": f"2024-02-{i:02d}",
                "open": 10.0,
                "high": 10.1,
                "low": 9.9,
                "close": 10.0,
                "volume": 1000.0,
            }
            for i in range(1, 25)
        ]
        df = _make_bars(rows)
        mask = volume_spike_long_upper_shadow(df)
        assert mask.sum() == 0


class TestLimitUpInPastMonth:
    def test_detects_recent_limit_up(self) -> None:
        rows = []
        for i in range(25):
            close = 10.0
            if i == 20:
                close = 11.0  # +10% from 10
            rows.append(
                {
                    "trade_date": f"2024-03-{i + 1:02d}",
                    "open": 10.0,
                    "high": 11.0 if i == 20 else 10.2,
                    "low": 9.8,
                    "close": close,
                    "volume": 1000.0,
                }
            )
        df = _make_bars(rows)
        mask = limit_up_in_past_month(df)
        # 涨停日后 20 日内应为 True
        assert bool(mask.iloc[-1]) is True
