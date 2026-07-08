"""事件研究：forward return 与留/删判定。"""

from __future__ import annotations

import pandas as pd

from chainalpha.factors.event_study import KillCriteria, judge_verdict, run_event_study
from chainalpha.factors.events import SIGNAL_REGISTRY
from chainalpha.factors.forward_return import add_forward_returns


def _synthetic_panel(n_days: int = 80, symbol: str = "000001") -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=n_days, freq="B")
    close = pd.Series(10.0 + pd.Series(range(n_days)).astype(float) * 0.01)
    return pd.DataFrame(
        {
            "symbol": symbol,
            "trade_date": dates,
            "open": close - 0.05,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": 1000.0,
        }
    )


class TestForwardReturn:
    def test_forward_return_horizons(self) -> None:
        panel = _synthetic_panel(30)
        out = add_forward_returns(panel, horizons=(3, 5))
        assert "fwd_ret_3" in out.columns
        assert "fwd_ret_5" in out.columns
        # 单调上涨，forward return 应为正
        valid = out.dropna(subset=["fwd_ret_5"])
        assert (valid["fwd_ret_5"] > 0).all()


class TestEventStudy:
    def test_run_event_study_insufficient_on_tiny_sample(self) -> None:
        panel = _synthetic_panel(25)
        spec = SIGNAL_REGISTRY["volume_spike_long_upper_shadow"]
        result = run_event_study(
            panel,
            spec,
            start_date="2024-01-01",
            end_date="2024-03-31",
            criteria=KillCriteria(min_signal_count=100),
        )
        assert result.verdict == "INSUFFICIENT_SAMPLE"

    def test_judge_delete_on_negative_edge(self) -> None:
        from chainalpha.factors.event_study import HorizonStats

        stats = [
            HorizonStats(
                horizon=5,
                signal_mean=-0.008,
                random_mean=0.001,
                excess=-0.009,
                signal_median=-0.007,
                signal_count=500,
                t_stat=-2.0,
                p_value=0.04,
            )
        ]
        verdict, reason = judge_verdict(stats, KillCriteria())
        assert verdict == "DELETE"
        assert "-0.80%" in reason or "无 Edge" in reason or "≤" in reason
