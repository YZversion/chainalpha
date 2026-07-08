#!/usr/bin/env python3
"""运行 2020–2025 因子事件研究（全市场 / 探针 / 缓存）。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from loguru import logger

from chainalpha.factors.screening import load_screening_config, run_all_signals, write_report
from chainalpha.ingest.akshare_panel import (
    DEFAULT_DELAY_SEC,
    DEFAULT_PROBE_SYMBOLS,
    load_all_market_panel,
    load_panel,
    load_panel_from_cache,
    load_symbols_from_file,
)

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="因子事件研究：信号 vs 随机，无 Edge 则删")
    p.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "factor_screening.yaml",
        help="筛选配置 yaml",
    )
    p.add_argument(
        "--symbols",
        nargs="*",
        help="股票代码列表；默认用探针样本",
    )
    p.add_argument(
        "--symbol-file",
        type=Path,
        default=None,
        help="每行一个股票代码的文本文件（跳过 universe 自动发现）",
    )
    p.add_argument(
        "--all-market",
        action="store_true",
        help="全 A 股 universe（qlib AkShare collector 同款发现逻辑）",
    )
    p.add_argument(
        "--signal",
        action="append",
        dest="signals",
        help="只跑指定信号（可重复）；默认跑 config 中全部",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="限制下载/加载股票数（调试）；全市场勿设",
    )
    p.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SEC,
        help="AkShare 请求间隔秒数",
    )
    p.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="并发下载线程数（默认 1 防封）",
    )
    p.add_argument(
        "--cache-only",
        action="store_true",
        help="仅从 parquet 缓存读取，不联网",
    )
    p.add_argument(
        "--no-download",
        action="store_true",
        help="不拉新数据，只读已有 parquet",
    )
    p.add_argument(
        "--no-cache",
        action="store_true",
        help="拉取时忽略已有 parquet 强制重下",
    )
    p.add_argument(
        "--report-stem",
        default="factor_screening",
        help="报告文件名前缀",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_screening_config(args.config)
    dr = cfg["date_range"]
    use_cache = not args.no_cache

    if args.cache_only or args.no_download:
        panel = load_panel_from_cache(start_date=dr["start"], end_date=dr["end"])
        report_meta = {"mode": "cache_only", "rows": len(panel)}
        logger.info("Loaded {} rows from cache", len(panel))
    elif args.symbol_file:
        symbols = load_symbols_from_file(args.symbol_file)
        if args.limit is not None:
            symbols = symbols[: args.limit]
        panel, report = load_panel(
            symbols,
            dr["start"],
            dr["end"],
            use_cache=use_cache,
            delay_sec=args.delay,
            max_workers=args.max_workers,
            download=not args.no_download,
        )
        report_meta = report.to_dict()
        logger.info(
            "Symbol-file: loaded {}/{} symbols, {} rows",
            report.symbols_loaded,
            report.symbols_requested,
            report.rows,
        )
    elif args.all_market:
        panel, report = load_all_market_panel(
            dr["start"],
            dr["end"],
            use_cache=use_cache,
            delay_sec=args.delay,
            max_workers=args.max_workers,
            limit=args.limit,
            download=not args.no_download,
        )
        report_meta = report.to_dict()
        logger.info(
            "All-market: loaded {}/{} symbols, {} rows, cache_skip={}, failed={}, {:.0f}s",
            report.symbols_loaded,
            report.symbols_requested,
            report.rows,
            report.symbols_skipped_cache,
            len(report.symbols_failed),
            report.elapsed_sec,
        )
    else:
        symbols = args.symbols or cfg.get("universe") or list(DEFAULT_PROBE_SYMBOLS)
        panel, report = load_panel(
            symbols,
            dr["start"],
            dr["end"],
            use_cache=use_cache,
            delay_sec=args.delay,
            max_workers=args.max_workers,
            limit=args.limit,
            download=not args.no_download,
        )
        report_meta = report.to_dict()
        logger.info(
            "Loaded {}/{} symbols, {} rows; failed: {}",
            report.symbols_loaded,
            report.symbols_requested,
            report.rows,
            report.symbols_failed,
        )

    if panel.empty:
        logger.error("[MISSING] panel empty — 先拉数据或检查缓存")
        return

    signal_names = args.signals
    results = run_all_signals(panel, cfg, signal_names=signal_names)
    stem = args.report_stem
    if args.all_market and signal_names and len(signal_names) == 1:
        stem = f"{stem}_{signal_names[0]}"

    md_path, json_path = write_report(results, stem=stem)
    meta_path = md_path.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(report_meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Report: {} | {}", md_path, json_path)

    for r in results:
        logger.info("{} → {} ({})", r.signal_name, r.verdict, r.verdict_reason)


if __name__ == "__main__":
    main()
