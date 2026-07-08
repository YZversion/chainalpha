#!/usr/bin/env python
"""Generate self-contained HTML reports for theme_rotation_t1 backtest runs.

Usage:
  python make_report.py <run_dir>          # writes report.html inside run_dir
  python make_report.py --index            # writes runs_index.html
  python make_report.py --index --runs-root <path>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPORT_ROOT = Path(__file__).resolve().parent
LAB_ROOT = REPORT_ROOT.parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from report.html_render import write_index, write_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="theme_rotation_t1 report generator")
    parser.add_argument("run_dir", nargs="?", help="Path to a single run artifact directory")
    parser.add_argument("--index", action="store_true", help="Build runs_index.html for all runs")
    parser.add_argument(
        "--runs-root",
        type=Path,
        default=None,
        help="Override runs root (default: data/backtest/theme_rotation_t1/runs)",
    )
    args = parser.parse_args(argv)

    if args.index:
        out = write_index(args.runs_root)
        print(f"Wrote {out}")
        return 0

    if not args.run_dir:
        parser.error("run_dir is required unless --index is set")

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"ERROR: not a directory: {run_dir}", file=sys.stderr)
        return 1

    out = write_report(run_dir)
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
