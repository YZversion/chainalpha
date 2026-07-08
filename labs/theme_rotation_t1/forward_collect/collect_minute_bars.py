"""前向采集 5 分钟 K 线（archive only，不生成信号）。"""

from __future__ import annotations

import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

import argparse  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402

from forward_collect._common import archive_dir, import_akshare, write_meta  # noqa: E402


def collect(symbols: list[str], lookback_days: int = 5) -> int:
    ak = import_akshare()
    out_dir = archive_dir("minute_bars")
    end = datetime.now()
    start = end - timedelta(days=lookback_days)
    errors: list[str] = []
    saved = 0

    for symbol in symbols:
        try:
            df = ak.stock_zh_a_hist_min_em(
                symbol=symbol,
                start_date=start.strftime("%Y-%m-%d %H:%M:%S"),
                end_date=end.strftime("%Y-%m-%d %H:%M:%S"),
                period="5",
                adjust="",
            )
            if df is not None and not df.empty:
                path = out_dir / f"{symbol}_5m.csv"
                df.to_csv(path, index=False, encoding="utf-8")
                saved += 1
            else:
                errors.append(f"{symbol}: empty")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{symbol}: {type(exc).__name__}: {exc}")

    status = "OK" if saved else "ERROR"
    write_meta(
        out_dir,
        kind="minute_bars",
        status=status,
        symbols=symbols,
        saved_count=saved,
        errors=errors[:20],
    )
    print(f"minute_bars archive={out_dir} saved={saved} errors={len(errors)}")
    return 0 if saved else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Forward-archive 5m bars via AkShare")
    parser.add_argument(
        "--symbols",
        default="000001,600519",
        help="Comma-separated symbols",
    )
    parser.add_argument("--lookback-days", type=int, default=5)
    args = parser.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    raise SystemExit(collect(symbols, args.lookback_days))


if __name__ == "__main__":
    main()
