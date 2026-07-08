"""加载冻结的 rules.yaml。

`[MISSING]` 字段转换为 MISSING 哨兵对象，禁止静默默认；
使用方必须显式处理（跳过交易或由调用方注入经过审计的参数）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

LAB_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = LAB_ROOT / "rules.yaml"


class _Missing:
    _instance: _Missing | None = None

    def __new__(cls) -> _Missing:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "[MISSING]"

    def __bool__(self) -> bool:
        return False


MISSING = _Missing()


def is_missing(value: Any) -> bool:
    return value is MISSING


def _convert(node: Any) -> Any:
    if isinstance(node, dict):
        return {key: _convert(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_convert(item) for item in node]
    if node == "[MISSING]":
        return MISSING
    return node


def load_rules(path: Path = RULES_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return _convert(raw)
