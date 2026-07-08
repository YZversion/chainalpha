"""非完整可执行回测循环单测（合成面板，不依赖 AkShare）。"""

from datetime import timedelta

from backtest.loop import run_degraded_backtest
from engine.bars import DailyBar
from engine.costs import CostModel
from ingestion.limits import derive_limit_prices
from synth import BASE_DATE


def _daily_panel(symbols: list[str], n: int = 30) -> dict[str, list[DailyBar]]:
    panel: dict[str, list[DailyBar]] = {}
    for sym in symbols:
        bars: list[DailyBar] = []
        prev = 10.0
        for i in range(n):
            d = BASE_DATE + timedelta(days=i)
            limits = derive_limit_prices(prev, sym, is_st=False)
            close = 10.0 + (i % 5) * 0.1
            bars.append(
                DailyBar(
                    symbol=sym,
                    trade_date=d,
                    open=prev,
                    high=max(prev, close) * 1.01,
                    low=min(prev, close) * 0.99,
                    close=close,
                    prev_close=prev,
                    volume=1000.0 + i * 10,
                    limit_up_price=limits.limit_up_price,
                    limit_down_price=limits.limit_down_price,
                )
            )
            prev = close
        panel[sym] = bars
    return panel


class TestDegradedBacktest:
    def test_blocks_entries_without_intraday_breadth(self):
        cost = CostModel.load_stock()
        panel = _daily_panel(["600000", "000001"], n=40)
        result = run_degraded_backtest(
            panel,
            split="train",
            cost_model=cost,
            ingest_note="synthetic",
        )
        assert result.title == "非完整可执行回测"
        assert len(result.trades) == 0
        assert result.entries_blocked_breadth >= 0
        assert "intraday_breadth" in result.degraded_notes[0]

    def test_runs_on_empty_panel(self):
        cost = CostModel.load_stock()
        result = run_degraded_backtest(
            {},
            split="validation",
            cost_model=cost,
            ingest_note="empty",
        )
        assert result.trading_days == 0
        assert result.final_equity == cost.initial_account
