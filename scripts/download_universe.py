#!/usr/bin/env python3
"""仅下载全市场日线 parquet（断点续传），不跑因子研究。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from loguru import logger

from chainalpha.ingest.akshare_panel import (
    DEFAULT_DELAY_SEC,
    download_universe,
    get_all_a_share_symbols,
    load_symbols_from_file,
)

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="全 A 股日线 parquet 下载（qlib AkShare 同款 universe）")
    p.add_argument("--start", default="2020-01-01")
    p.add_argument("--end", default="2025-12-31")
    p.add_argument("--all-market", action="store_true")
    p.add_argument("--symbol-file", type=Path, default=None)
    p.add_argument("--symbols", nargs="*")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--delay", type=float, default=DEFAULT_DELAY_SEC)
    p.add_argument("--max-workers", type=int, default=1)
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--refresh-universe", action="store_true")
    p.add_argument(
        "--report",
        type=Path,
        default=ROOT / "reports" / "download_universe.json",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.symbol_file:
        symbols = load_symbols_from_file(args.symbol_file)
    elif args.symbols:
        symbols = args.symbols
    elif args.all_market:
        symbols = get_all_a_share_symbols(refresh=args.refresh_universe)
    else:
        logger.error("Specify --all-market, --symbol-file, or --symbols")
        return

    report = download_universe(
        symbols,
        args.start,
        args.end,
        use_cache=not args.no_cache,
        delay_sec=args.delay,
        max_workers=args.max_workers,
        limit=args.limit,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Done: {} | report {}", report.to_dict(), args.report)


if __name__ == "__main__":
    main()
