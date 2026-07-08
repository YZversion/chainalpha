"""AkShare 客户端封装（重试 + 超时）；失败返回 None，不伪造数据。"""

from __future__ import annotations

import socket
import sys
import time
from pathlib import Path
from typing import Any

TMP_AKSHARE_PATH = Path(r"C:\tmp\chainalpha_akshare_pkgs")
if TMP_AKSHARE_PATH.exists() and str(TMP_AKSHARE_PATH) not in sys.path:
    sys.path.insert(0, str(TMP_AKSHARE_PATH))

import pandas as pd  # noqa: E402

HTTP_TIMEOUT_SECONDS = 25
socket.setdefaulttimeout(HTTP_TIMEOUT_SECONDS)


def get_akshare():
    import akshare as ak  # noqa: PLC0415

    return ak


def call_df(
    fn_name: str,
    *,
    retries: int = 2,
    retry_sleep: float = 1.5,
    **kwargs: Any,
) -> pd.DataFrame | None:
    """调用 AkShare 函数；全部失败返回 None。"""
    ak = get_akshare()
    fn = getattr(ak, fn_name)
    for attempt in range(retries + 1):
        try:
            df = fn(**kwargs)
            if isinstance(df, pd.DataFrame):
                return df
        except Exception:  # noqa: BLE001
            pass
        if attempt < retries:
            time.sleep(retry_sleep)
    return None
