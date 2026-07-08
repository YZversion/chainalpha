# theme_rotation_t1 — 非完整可执行回测

> 仅供学习研究，不构成投资建议。

报告日期：2026-07-08

## 1. 数据覆盖与 [MISSING] 字段

- 数据源：AkShare `stock_zh_a_hist`（未复权日线）
- 标的范围：`reduced_probe_symbols`（请求 5，成功 0）
- 缓存目录：`data\raw\labs\theme_rotation_t1\daily_csv`
- 接入行数：0

| 字段 | 状态 | 说明 |
| --- | --- | --- |
| daily_ohlcv | [MISSING] | 网络失败时无数据 |
| intraday_breadth | [MISSING] | 无历史决策时点快照；买入门槛阻断 |
| minute_bars | [MISSING] | 无历史分钟线 |
| limit_prices | 推导 | 昨收+板块规则；ST 状态 [MISSING] |
| free_float_market_cap | [MISSING] | 一进二 setup 无法完整验证 |
| theme_id (as-of) | [MISSING] | 相关性保守计数 |
| event_risk 全字段 | [MISSING] | 保守排除 |
| tolerated_account_drawdown_pct | [MISSING] | rules.yaml 未冻结 |

## 2. 样本切分

- 训练/规则冻结：2018-01-01 – 2021-12-31
- 验证：2022-01-01 – 2023-12-31
- 最终 holdout：`[MISSING]`（未运行）
- 主项目 OOS 2024–2026.06：**未触碰**

## 3. 参数版本

- `rules.yaml` / `strategy_spec.md`：未修改（draft_unvalidated）
- 成本：`config/costs.yaml`（account=100000, lot=100, 佣金万2.5/最低5元/印花税0.05%/滑点0.15%）

## 4. 全系统绩效（降级口径）

### train

- 交易日数：0
- 期末权益：100,000.00（+0.00%）
- 成交笔数：0
- 涨跌停未成交事件：0
- 买入被盘中宽度阻断：0
- 买入被仓位参数阻断：0
- 买入被事件过滤阻断：0

### validation

- 交易日数：0
- 期末权益：100,000.00（+0.00%）
- 成交笔数：0
- 涨跌停未成交事件：0
- 买入被盘中宽度阻断：0
- 买入被仓位参数阻断：0
- 买入被事件过滤阻断：0

## 5. setup 分项（信号扫描，非成交）

### train

- 无触发（数据不足或样本为空）

### validation

- 无触发（数据不足或样本为空）

## 6. 成本与敏感性

- 本次无成交，摩擦成本占比 N/A
- 完整可执行回测需分钟数据 + 盘中宽度 + 冻结仓位参数后方可评估

## 7. 涨跌停未成交影响

- train：0 次
- validation：0 次

## 8. 冷却期与停用

- 无成交样本，滚动期望停用规则未触发

## 9. 降级说明

- intraday_breadth=[MISSING]: 买入门槛按 mark_missing_no_trade，不产生新仓
- tolerated_account_drawdown_pct=[MISSING]: 仓位公式跳过 (missing_param)
- 无分钟数据: 不验证 10:40/14:40 买点与分时卖出
- limit_prices: 由昨收+板块规则推导，ST 状态 [MISSING]
- theme_id=[MISSING]: 相关性约束保守计数
- 事件风险字段 [MISSING]: 保守排除全部候选

## 10. Go/No-Go 结论

**NO-GO**（不得进入实盘或模拟加仓）

理由：

1. 非完整可执行回测：缺分钟线、缺盘中上涨家数、缺历史 as-of 题材标签。
2. 本次 AkShare 日线接入失败（网络）。
3. `rules.yaml` 仓位参数 `tolerated_account_drawdown_pct` 仍为 [MISSING]。
4. 未满足 backtest_protocol.md 完整可执行回测与净期望 > 0 等全部门槛。

建议：

- 稳定网络下复跑 `probe_akshare.py` 与日线接入；
- 启动 `forward_collect/` 脚本积累分钟线、盘中宽度、概念成份快照；
- 冻结缺失仓位参数后再做可执行回测。

本报告仅供学习研究，不构成投资建议。