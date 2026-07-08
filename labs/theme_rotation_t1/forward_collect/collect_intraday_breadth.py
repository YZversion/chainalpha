"""前向采集盘中全市场快照（archive only，不生成信号）。"""

from __future__ import annotations

import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

import argparse  # noqa: E402
from datetime import datetime  # noqa: E402

from forward_collect._common import archive_dir, import_akshare, write_meta  # noqa: E402


def _advancers_ratio(df) -> dict[str, float | int] | None:
    pct_col = "涨跌幅" if "涨跌幅" in df.columns else None
    if pct_col is None:
        return None
    valid = df[pct_col].astype(float, errors="ignore")
    valid = valid.dropna()
    if valid.empty:
        return None
    adv = int((valid > 0).sum())
    total = int(valid.shape[0])
    return {
        "advancers": adv,
        "decliners": int((valid < 0).sum()),
        "flat": int((valid == 0).sum()),
        "tradable_like_count": total,
        "advancers_ratio": adv / total,
    }


def collect(label: str) -> int:
    ak = import_akshare()
    out_dir = archive_dir("intraday_breadth")
    now = datetime.now()
    errors: list[str] = []
    stats: dict[str, object] | None = None

    try:
        df = ak.stock_zh_a_spot_em()
        if df is not None and not df.empty:
            path = out_dir / f"spot_{now.strftime('%Y%m%d_%H%M%S')}.csv"
            df.to_csv(path, index=False, encoding="utf-8")
            stats = _advancers_ratio(df)
        else:
            errors.append("empty snapshot")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{type(exc).__name__}: {exc}")

    status = "OK" if stats else "ERROR"
    write_meta(
        out_dir,
        kind="intraday_breadth",
        status=status,
        decision_label=label,
        snapshot_time=now.isoformat(timespec="seconds"),
        breadth_stats=stats,
        errors=errors,
    )
    print(f"intraday_breadth archive={out_dir} status={status} stats={stats}")
    return 0 if stats else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Forward-archive intraday breadth snapshot")
    parser.add_argument(
        "--label",
        default=datetime.now().strftime("%H:%M"),
        help="Decision-time label e.g. 10:40 or 14:40",
    )
    args = parser.parse_args()
    raise SystemExit(collect(args.label))


if __name__ == "__main__":
    main()
