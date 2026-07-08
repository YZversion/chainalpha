"""pytest bootstrap：让 lab 内测试能 import engine，并接入临时依赖目录。"""

import sys
from pathlib import Path

TMP_PKGS = Path(r"C:\tmp\chainalpha_akshare_pkgs")
if TMP_PKGS.exists() and str(TMP_PKGS) not in sys.path:
    sys.path.insert(0, str(TMP_PKGS))

LAB_ROOT = Path(__file__).resolve().parent
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))
