"""前向采集概念板块成份股快照（archive only，不生成信号）。"""

from __future__ import annotations

import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

import argparse  # noqa: E402
from datetime import datetime  # noqa: E402

from forward_collect._common import archive_dir, import_akshare, write_meta  # noqa: E402


def collect(max_concepts: int = 5) -> int:
    ak = import_akshare()
    out_dir = archive_dir("concept_constituents")
    errors: list[str] = []
    saved = 0

    try:
        concepts = ak.stock_board_concept_name_em()
        if concepts is None or concepts.empty:
            errors.append("concept list empty")
        else:
            concepts.to_csv(out_dir / "concept_list.csv", index=False, encoding="utf-8")
            saved += 1
            name_col = "板块名称" if "板块名称" in concepts.columns else concepts.columns[1]
            for _, row in concepts.head(max_concepts).iterrows():
                concept = str(row[name_col])
                try:
                    cons = ak.stock_board_concept_cons_em(symbol=concept)
                    if cons is not None and not cons.empty:
                        safe = "".join(c if c.isalnum() else "_" for c in concept)[:40]
                        cons.to_csv(
                            out_dir / f"cons_{safe}.csv",
                            index=False,
                            encoding="utf-8",
                        )
                        saved += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"{concept}: {type(exc).__name__}: {exc}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"concept list: {type(exc).__name__}: {exc}")

    status = "OK" if saved > 1 else "ERROR"
    write_meta(
        out_dir,
        kind="concept_constituents",
        status=status,
        archived_at=datetime.now().isoformat(timespec="seconds"),
        saved_files=saved,
        errors=errors[:20],
        note="current snapshot only; not historical as-of constituents",
    )
    print(f"concept_constituents archive={out_dir} saved={saved} errors={len(errors)}")
    return 0 if saved > 1 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Forward-archive concept board snapshots")
    parser.add_argument("--max-concepts", type=int, default=5)
    args = parser.parse_args()
    raise SystemExit(collect(args.max_concepts))


if __name__ == "__main__":
    main()
