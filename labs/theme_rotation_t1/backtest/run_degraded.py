"""运行非完整可执行回测 CLI。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

TMP_PKGS = Path(r"C:\tmp\chainalpha_akshare_pkgs")
if TMP_PKGS.exists() and str(TMP_PKGS) not in sys.path:
    sys.path.insert(0, str(TMP_PKGS))

from backtest.loop import run_degraded_backtest  # noqa: E402
from backtest.report import write_backtest_report  # noqa: E402
from engine.costs import CostModel  # noqa: E402
from ingestion.daily_bars import ingest_daily_panel, load_universe_symbols  # noqa: E402

WORKSPACE = LAB_ROOT.parents[1]
REPORT_PATH = WORKSPACE / "reports" / "lab_theme_rotation_t1.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="theme_rotation_t1 degraded daily backtest")
    parser.add_argument("--max-symbols", type=int, default=50)
    parser.add_argument("--splits", default="train,validation")
    args = parser.parse_args()

    symbols, universe_note = load_universe_symbols()
    start = "20180101"
    end = "20231231"
    panel, ingest = ingest_daily_panel(
        symbols, start, end, max_symbols=args.max_symbols
    )
    ingest_note = (
        f"universe={universe_note}; loaded={ingest.symbols_loaded}/"
        f"{ingest.symbols_requested}; failed={len(ingest.symbols_failed)}; "
        f"rows={ingest.rows_total}"
    )
    if ingest.symbols_loaded == 0:
        ingest_note += "; daily_ohlcv=[MISSING] (AkShare fetch failed — network)"

    cost = CostModel.load_stock()
    results = []
    for split in [s.strip() for s in args.splits.split(",") if s.strip()]:
        results.append(
            run_degraded_backtest(
                panel, split=split, cost_model=cost, ingest_note=ingest_note
            )
        )

    summary_path = LAB_ROOT / "backtest" / "last_run_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "run_date": date.today().isoformat(),
                "ingest": ingest.__dict__,
                "results": [
                    {
                        "split": r.split,
                        "trading_days": r.trading_days,
                        "setup_signal_counts": r.setup_signal_counts,
                        "entries_blocked_breadth": r.entries_blocked_breadth,
                        "trades": len(r.trades),
                        "final_equity": r.final_equity,
                    }
                    for r in results
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_backtest_report(results, ingest=ingest, universe_note=universe_note, path=REPORT_PATH)
    print(f"report={REPORT_PATH}")
    print(f"summary={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
