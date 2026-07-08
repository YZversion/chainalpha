# theme_rotation_t1 lab

本 lab 用于验证“情绪驱动的题材轮动 + T+1 约束”短线策略。

它是隔离研究包，不接入当前 `plan.md` 主线模型，不生成自动下单代码，不触碰主项目 Phase 4 的正式样本外窗口。只有在完成数据审计、规则单测、真实成本回测和报告后，才允许讨论是否进入主线。

## 当前状态

- 状态：规则冻结草案，尚未回测
- 账户假设：沿用主项目 `account=100000`
- 成本假设：沿用 `config/costs.yaml` 的股票成本模型
- 交易约束：T+1、整手 100 股、涨跌停无法成交
- 执行边界：只做研究验证与人工执行记录 schema，不写自动下单
- 数据源口径：AkShare-only；拿不到的字段标 `[MISSING]`，不再用 Tushare 补洞

## 文件说明

| 文件 | 用途 |
| --- | --- |
| `strategy_spec.md` | 把口头策略转成可代码化规则 |
| `rules.yaml` | 机器可读规则参数，含 `[MISSING]` 字段 |
| `data_requirements.md` | Qlib/外部公开数据接入前的数据清单 |
| `data_audit_plan.md` | 数据可得性审计流程与判定标准 |
| `source_matrix.yaml` | 字段级候选数据源矩阵 |
| `backtest_protocol.md` | 回测、样本切分、撮合、统计验证协议 |
| `schemas/trade_log.schema.yaml` | 每笔交易归档字段 |
| `schemas/setup_stats.schema.yaml` | setup 级统计字段 |

## 使用顺序

1. 按 `data_audit_plan.md` 审计 `source_matrix.yaml` 中每个字段。
2. 补齐 `data_requirements.md` 中所有必需数据，拿不到的字段标 `[MISSING]`。
3. 按 `strategy_spec.md` 和 `rules.yaml` 写规则引擎，先用合成数据做 pytest。
4. 接真实数据回测，撮合必须包含 T+1、涨跌停不可成交、佣金、印花税、滑点。
5. 输出 `reports/lab_theme_rotation_t1.md`，无论结果好坏如实记录。

本 lab 仅供学习研究，不构成投资建议。
