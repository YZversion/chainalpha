"""前向采集公共工具：仅归档原始数据，不生成信号或订单。"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

TMP_AKSHARE_PATH = Path(r"C:\tmp\chainalpha_akshare_pkgs")
if TMP_AKSHARE_PATH.exists() and str(TMP_AKSHARE_PATH) not in sys.path:
    sys.path.insert(0, str(TMP_AKSHARE_PATH))

WORKSPACE = Path(__file__).resolve().parents[3]
LAB_ROOT = Path(__file__).resolve().parents[1]
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))
ARCHIVE_ROOT = WORKSPACE / "data" / "raw" / "labs" / "theme_rotation_t1" / "forward_archive"


def archive_dir(kind: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ARCHIVE_ROOT / kind / stamp
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_meta(out_dir: Path, *, kind: str, status: str, **extra: object) -> None:
    meta = {
        "kind": kind,
        "status": status,
        "archived_at": datetime.now().isoformat(timespec="seconds"),
        **extra,
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def import_akshare():
    try:
        import akshare as ak  # noqa: PLC0415
    except ImportError as exc:
        raise SystemExit(
            "AkShare not importable. Install to C:\\tmp\\chainalpha_akshare_pkgs first."
        ) from exc
    return ak
