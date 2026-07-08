# 数据需求

本 lab 不允许用假数据跑通 pipeline。缺字段时标 `[MISSING]`，并在报告里说明该实验不可用于实盘判断。

## 1. 行情数据

必需字段：

| 字段 | 频率 | 用途 | 缺失处理 |
| --- | --- | --- | --- |
| raw open/high/low/close | 日频 | 涨跌停、止损、止盈、撮合 | `[MISSING]` |
| adjusted open/high/low/close | 日频 | 收益统计、复权校验 | `[MISSING]` |
| volume/amount | 日频 | 倍量、放量上影 | `[MISSING]` |
| prev_close | 日频 | 涨跌幅、涨跌停 | `[MISSING]` |
| limit_up_price/limit_down_price | 日频 | 涨跌停不可成交 | `[MISSING]` |
| suspended/tradable flag | 日频 | 全市场分母、不可交易过滤 | `[MISSING]` |
| 1min 或 5min OHLCV | 分钟 | 10:40/14:40 买点、VWAP、分时卖出 | `[MISSING]` |
| intraday VWAP 或可计算字段 | 分钟 | 均价线卖出信号 | `[MISSING]` |

注意：

- 涨跌停必须用未复权价格或行情源字段判断。
- 无盘口排队数据时，触及涨停买入或跌停卖出按不可成交处理，这是保守假设。

## 2. 全市场状态数据

必需字段：

| 字段 | 频率 | 用途 | 缺失处理 |
| --- | --- | --- | --- |
| 全 A 可交易股票列表 | 日频/盘中 | 上涨家数分母 | `[MISSING]` |
| 每只票相对昨收涨跌 | 盘中快照 | 买入门槛 | `[MISSING]` |
| 收盘上涨家数占比 | 日频 | 逆势股候选与复盘 | `[MISSING]` |
| 全市场成交额 | 日频 | 极端缩量市识别 | `[MISSING]` |

盘中买入门槛不得用收盘后数据替代。若只有收盘上涨家数，只能做候选研究，不能宣称完成可执行回测。

## 3. 标的与市值数据

必需字段：

| 字段 | 频率 | 用途 | 缺失处理 |
| --- | --- | --- | --- |
| listing_date | 静态/as-of | 上市满 1 年过滤 | `[MISSING]` |
| delisting_date | 静态/as-of | 幸存者偏差控制 | `[MISSING]` |
| free_float_market_cap | 日频或月频 as-of | 一进二后 30% 市值分位 | `[MISSING]` |
| total_market_cap | 日频或月频 as-of | 辅助审计 | `[MISSING]` |
| ST/risk warning history | 日频 as-of | 风险警示过滤 | `[MISSING]` |

市值分位必须按当时可见的全市场横截面计算。

## 4. 事件风险数据

所有来源必须是公开数据。

必需字段：

| 字段 | 生效日期 | 用途 | 缺失处理 |
| --- | --- | --- | --- |
| unlock_date/share_unlock_amount | 公告日与解禁日 | 30 日内解禁过滤 | `[MISSING]` |
| shareholder_reduction_announcement_date | 公告日 | 已公告减持过滤 | `[MISSING]` |
| shareholder_reduction_completion_date | 公告日 | 判断减持是否实施完毕 | `[MISSING]` |
| inquiry_letter_date | 公告/披露日 | 问询函过滤 | `[MISSING]` |
| regulatory_letter_date | 公告/披露日 | 监管函过滤 | `[MISSING]` |
| source_url | 原始公告链接 | 可审计性 | `[MISSING]` |

事件风险字段不能用报告期日期或事后整理日期代替公告/披露日期。

## 5. 题材标签数据

必需字段：

| 字段 | 频率 | 用途 | 缺失处理 |
| --- | --- | --- | --- |
| theme_id | as-of | 同题材最多 2 只 | `[MISSING]` |
| theme_name | as-of | 复盘可读性 | `[MISSING]` |
| theme_effective_date | 日期 | 防前视偏差 | `[MISSING]` |
| source_url | 链接 | 公开可审计 | `[MISSING]` |

若题材标签只能事后人工归类，该字段必须标为研究标签，不能用于买入日前的回测决策。

## 6. 成本与约束

沿用 `config/costs.yaml`：

- 股票佣金万 2.5
- 最低 5 元佣金
- 卖出印花税 0.05%
- 滑点 0.15%
- T+1
- 涨跌停约束开启

若 lab 后续使用更高滑点做敏感性分析，只能更保守，不能低于主配置。
