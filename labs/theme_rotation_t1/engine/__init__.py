"""theme_rotation_t1 规则引擎（研究用，不生成自动下单）。

只实现 rules.yaml 冻结规则的可测试逻辑；数据接入与回测撮合循环
在数据审计通过后另行实现。所有 [MISSING] 参数保留为 MISSING 哨兵，
不允许静默默认值。
"""

from .rules import MISSING, is_missing, load_rules

__all__ = ["MISSING", "is_missing", "load_rules"]
