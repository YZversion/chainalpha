# theme_rotation_t1 数据审计报告

状态：AkShare-only 小样本 probe 已执行。

本报告只记录公开数据源可得性，不构成投资建议。

## 1. 数据源口径

- 主数据源：AkShare
- AkShare 版本：`1.18.64`
- Python：`3.11.9`
- Probe 时间：`2026-07-08 11:29:11`
- 原始样例目录：`data\raw\labs\theme_rotation_t1\akshare_probe\20260708_112911`
- 禁用：Tushare、券商 API、非公开数据、手工事后补标签
- 输出原则：拿不到或无法证明 as-of 的字段标 `[MISSING]`
- 复测记录：2026-07-08 11:29 第二次全量 probe，结论与首次一致；错误类型为 ReadTimeout / ConnectionReset / SSLError，属网络不稳定，**不能**解读为字段永久不存在

## 2. 结论摘要

| 字段 | Probe 结论 | 是否可用于完整历史回测 |
| --- | --- | --- |
| daily_ohlcv | ERROR | 待二次核验 |
| minute_bars | ERROR | 否 |
| intraday_breadth | ERROR | 否 |
| limit_prices | MISSING | 否 |
| historical_st_status | ERROR | 否/待定 |
| delisting_history | ERROR | 否/待定 |
| unlock_events | PARTIAL | 待定 |
| shareholder_reduction | ERROR | 否/待定 |
| inquiry_or_regulatory_letters | ERROR | 待定 |
| asof_theme_labels | ERROR | 否 |
| listing_date | ERROR | 待定 |

## 3. 派生检查

无

## 4. 接口执行明细

| 字段 | 接口 | 状态 | 行数 | 列数 | 样例文件 | 错误 |
| --- | --- | --- | --- | --- | --- | --- |
| listing_date | stock_info_a_code_name | ERROR | 0 | 0 |  | ReadTimeout: HTTPSConnectionPool(host='query.sse.com.cn', port=443): Read timed out. (read timeout=20) |
| daily_ohlcv | stock_zh_a_hist:000001 | ERROR | 0 | 0 |  | ReadTimeout: HTTPSConnectionPool(host='push2his.eastmoney.com', port=443): Read timed out. (read timeout=20) |
| daily_ohlcv | stock_zh_a_hist:600519 | ERROR | 0 | 0 |  | ReadTimeout: HTTPSConnectionPool(host='push2his.eastmoney.com', port=443): Read timed out. (read timeout=20) |
| daily_ohlcv | stock_zh_a_hist:300750 | ERROR | 0 | 0 |  | ReadTimeout: HTTPSConnectionPool(host='push2his.eastmoney.com', port=443): Read timed out. (read timeout=20) |
| daily_ohlcv | stock_zh_a_hist:688981 | ERROR | 0 | 0 |  | ReadTimeout: HTTPSConnectionPool(host='push2his.eastmoney.com', port=443): Read timed out. (read timeout=20) |
| daily_ohlcv | stock_zh_a_hist:837006 | ERROR | 0 | 0 |  | ReadTimeout: HTTPSConnectionPool(host='push2his.eastmoney.com', port=443): Read timed out. (read timeout=20) |
| minute_bars | stock_zh_a_hist_min_em:000001:5m | ERROR | 0 | 0 |  | ConnectionError: ('Connection aborted.', ConnectionResetError(10054, '远程主机强迫关闭了一个现有的连接。', None, 10054, None)) |
| intraday_breadth | stock_zh_a_spot_em | ERROR | 0 | 0 |  | TimeoutExpired after 35s |
| limit_prices | stock_zt_pool_em | MISSING | 0 | 0 |  | 20260708: ReadTimeout: HTTPSConnectionPool(host='push2ex.eastmoney.com', port=443): Read timed out. (read timeout=20); 20260707: ReadTimeout: HTTPSConnectionPool(host='push2ex.eastmoney.com', port=443): Read timed out. (read timeout=20); 20260706: ReadTimeout: HTTPSConnectionPool(host='push2ex.eastmoney.com', port=443): Read timed out. (read timeout=20) |
| limit_prices | stock_zt_pool_dtgc_em | MISSING | 0 | 0 |  | 20260708: ReadTimeout: HTTPSConnectionPool(host='push2ex.eastmoney.com', port=443): Read timed out. (read timeout=20); 20260707: ReadTimeout: HTTPSConnectionPool(host='push2ex.eastmoney.com', port=443): Read timed out. (read timeout=20); 20260706: ReadTimeout: HTTPSConnectionPool(host='push2ex.eastmoney.com', port=443): Read timed out. (read timeout=20) |
| historical_st_status | stock_zh_a_st_em | ERROR | 0 | 0 |  | TimeoutExpired after 35s |
| historical_st_status | stock_info_change_name:000503 | ERROR | 0 | 0 |  | ReadTimeout: HTTPSConnectionPool(host='vip.stock.finance.sina.com.cn', port=443): Read timed out. (read timeout=20) |
| historical_st_status | stock_info_sz_change_name:简称变更 | ERROR | 0 | 0 |  | ReadTimeout: HTTPSConnectionPool(host='www.szse.cn', port=443): Read timed out. (read timeout=20) |
| delisting_history | stock_staq_net_stop | ERROR | 0 | 0 |  | ReadTimeout: HTTPSConnectionPool(host='5.push2.eastmoney.com', port=443): Read timed out. (read timeout=20) |
| delisting_history | stock_zh_a_stop_em | ERROR | 0 | 0 |  | TimeoutExpired after 35s |
| unlock_events | stock_restricted_release_queue_sina:600000 | ERROR | 0 | 0 |  | ReadTimeout: HTTPSConnectionPool(host='vip.stock.finance.sina.com.cn', port=443): Read timed out. (read timeout=20) |
| unlock_events | stock_restricted_release_detail_em | PARTIAL | 311 | 12 | data\raw\labs\theme_rotation_t1\akshare_probe\20260708_112911\unlock_events__stock_restricted_release_detail_em.csv |  |
| shareholder_reduction | stock_ggcg_em:全部 | ERROR | 0 | 0 |  | TimeoutExpired after 35s |
| inquiry_or_regulatory_letters | stock_individual_notice_report:000001:全部 | ERROR | 0 | 0 |  | ReadTimeout: HTTPSConnectionPool(host='np-anotice-stock.eastmoney.com', port=443): Read timed out. (read timeout=20) |
| asof_theme_labels | stock_board_concept_name_em | ERROR | 0 | 0 |  | TimeoutExpired after 35s |
| asof_theme_labels | stock_board_concept_cons_em:融资融券 | ERROR | 0 | 0 |  | TimeoutExpired after 35s |
| listing_date | stock_ipo_info:000001 | ERROR | 0 | 0 |  | ReadTimeout: HTTPSConnectionPool(host='vip.stock.finance.sina.com.cn', port=443): Read timed out. (read timeout=20) |
| listing_date | stock_ipo_info:600519 | ERROR | 0 | 0 |  | ReadTimeout: HTTPSConnectionPool(host='vip.stock.finance.sina.com.cn', port=443): Read timed out. (read timeout=20) |
| listing_date | stock_ipo_info:688981 | ERROR | 0 | 0 |  | ReadTimeout: HTTPSConnectionPool(host='vip.stock.finance.sina.com.cn', port=443): Read timed out. (read timeout=20) |

## 5. 字段审计记录

### listing_date / `stock_info_a_code_name`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：A-share code/name list only; listing date still needs stock_ipo_info per symbol.
- 错误：`ReadTimeout: HTTPSConnectionPool(host='query.sse.com.cn', port=443): Read timed out. (read timeout=20)`

```json
[]
```

### daily_ohlcv / `stock_zh_a_hist:000001`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Unadjusted daily OHLCV sample; use raw prices for limit checks.
- 错误：`ReadTimeout: HTTPSConnectionPool(host='push2his.eastmoney.com', port=443): Read timed out. (read timeout=20)`

```json
[]
```

### daily_ohlcv / `stock_zh_a_hist:600519`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Unadjusted daily OHLCV sample; use raw prices for limit checks.
- 错误：`ReadTimeout: HTTPSConnectionPool(host='push2his.eastmoney.com', port=443): Read timed out. (read timeout=20)`

```json
[]
```

### daily_ohlcv / `stock_zh_a_hist:300750`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Unadjusted daily OHLCV sample; use raw prices for limit checks.
- 错误：`ReadTimeout: HTTPSConnectionPool(host='push2his.eastmoney.com', port=443): Read timed out. (read timeout=20)`

```json
[]
```

### daily_ohlcv / `stock_zh_a_hist:688981`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Unadjusted daily OHLCV sample; use raw prices for limit checks.
- 错误：`ReadTimeout: HTTPSConnectionPool(host='push2his.eastmoney.com', port=443): Read timed out. (read timeout=20)`

```json
[]
```

### daily_ohlcv / `stock_zh_a_hist:837006`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Unadjusted daily OHLCV sample; use raw prices for limit checks.
- 错误：`ReadTimeout: HTTPSConnectionPool(host='push2his.eastmoney.com', port=443): Read timed out. (read timeout=20)`

```json
[]
```

### minute_bars / `stock_zh_a_hist_min_em:000001:5m`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Probe requests 30 calendar days; coverage must be inspected before historical backtest.
- 错误：`ConnectionError: ('Connection aborted.', ConnectionResetError(10054, '远程主机强迫关闭了一个现有的连接。', None, 10054, None))`

```json
[]
```

### intraday_breadth / `stock_zh_a_spot_em`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Current full-market snapshot only; historical decision-time breadth needs forward archive.
- 错误：`TimeoutExpired after 35s`

```json
[]
```

### limit_prices / `stock_zt_pool_em`

- 状态：`MISSING`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Limit-up pool only; not full-market daily limit prices.; No non-empty result in recent date candidates.
- 错误：`20260708: ReadTimeout: HTTPSConnectionPool(host='push2ex.eastmoney.com', port=443): Read timed out. (read timeout=20); 20260707: ReadTimeout: HTTPSConnectionPool(host='push2ex.eastmoney.com', port=443): Read timed out. (read timeout=20); 20260706: ReadTimeout: HTTPSConnectionPool(host='push2ex.eastmoney.com', port=443): Read timed out. (read timeout=20)`

```json
[]
```

### limit_prices / `stock_zt_pool_dtgc_em`

- 状态：`MISSING`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Limit-down pool only; not full-market daily limit prices.; No non-empty result in recent date candidates.
- 错误：`20260708: ReadTimeout: HTTPSConnectionPool(host='push2ex.eastmoney.com', port=443): Read timed out. (read timeout=20); 20260707: ReadTimeout: HTTPSConnectionPool(host='push2ex.eastmoney.com', port=443): Read timed out. (read timeout=20); 20260706: ReadTimeout: HTTPSConnectionPool(host='push2ex.eastmoney.com', port=443): Read timed out. (read timeout=20)`

```json
[]
```

### historical_st_status / `stock_zh_a_st_em`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Current risk-warning board only; not historical ST intervals.
- 错误：`TimeoutExpired after 35s`

```json
[]
```

### historical_st_status / `stock_info_change_name:000503`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Sina previous-name list has names but no effective dates.
- 错误：`ReadTimeout: HTTPSConnectionPool(host='vip.stock.finance.sina.com.cn', port=443): Read timed out. (read timeout=20)`

```json
[]
```

### historical_st_status / `stock_info_sz_change_name:简称变更`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：SZSE name-change history has dates but does not cover Shanghai/Beijing markets.
- 错误：`ReadTimeout: HTTPSConnectionPool(host='www.szse.cn', port=443): Read timed out. (read timeout=20)`

```json
[]
```

### delisting_history / `stock_staq_net_stop`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Delisted/STAQ/NET list; still needs merge with historical tradeable universe.
- 错误：`ReadTimeout: HTTPSConnectionPool(host='5.push2.eastmoney.com', port=443): Read timed out. (read timeout=20)`

```json
[]
```

### delisting_history / `stock_zh_a_stop_em`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Current delisted-board quote/list; not sufficient alone for survivor-bias-free backtest.
- 错误：`TimeoutExpired after 35s`

```json
[]
```

### unlock_events / `stock_restricted_release_queue_sina:600000`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Per-symbol unlock queue includes announcement date in AkShare docs and sample if returned.
- 错误：`ReadTimeout: HTTPSConnectionPool(host='vip.stock.finance.sina.com.cn', port=443): Read timed out. (read timeout=20)`

```json
[]
```

### unlock_events / `stock_restricted_release_detail_em`

- 状态：`PARTIAL`
- 行数：`311`
- 字段：`序号, 股票代码, 股票简称, 解禁时间, 限售股类型, 解禁数量, 实际解禁数量, 实际解禁市值, 占解禁前流通市值比例, 解禁前一交易日收盘价, 解禁前20日涨跌幅, 解禁后20日涨跌幅`
- 样例文件：`data\raw\labs\theme_rotation_t1\akshare_probe\20260708_112911\unlock_events__stock_restricted_release_detail_em.csv`
- 备注：Market-wide unlock detail can help candidate filtering but may include post-event performance fields.
- 错误：无

```json
[
  {
    "序号": 1,
    "股票代码": "300992",
    "股票简称": "泰福泵业",
    "解禁时间": "2026-06-08",
    "限售股类型": "股权激励限售股份",
    "解禁数量": 592000.0,
    "实际解禁数量": 592000.0,
    "实际解禁市值": 15267680.0,
    "占解禁前流通市值比例": 0.007580412102,
    "解禁前一交易日收盘价": 25.79,
    "解禁前20日涨跌幅": -14.6529563,
    "解禁后20日涨跌幅": 0.60240964
  },
  {
    "序号": 2,
    "股票代码": "920729",
    "股票简称": "永顺生物",
    "解禁时间": "2026-06-08",
    "限售股类型": "股权激励限售股份",
    "解禁数量": 1408000.0,
    "实际解禁数量": 697000.0,
    "实际解禁市值": 5067190.0,
    "占解禁前流通市值比例": 0.008990991349,
    "解禁前一交易日收盘价": 7.27,
    "解禁前20日涨跌幅": -9.55334988,
    "解禁后20日涨跌幅": -7.75734215
  }
]
```

### shareholder_reduction / `stock_ggcg_em:全部`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Shareholder increase/decrease records; cannot prove announced-but-unfinished reduction without pairing plan/completion announcements.
- 错误：`TimeoutExpired after 35s`

```json
[]
```

### inquiry_or_regulatory_letters / `stock_individual_notice_report:000001:全部`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Announcement titles can be keyword-filtered; coverage of exchange letters must be manually sampled.
- 错误：`ReadTimeout: HTTPSConnectionPool(host='np-anotice-stock.eastmoney.com', port=443): Read timed out. (read timeout=20)`

```json
[]
```

### asof_theme_labels / `stock_board_concept_name_em`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Current concept list only.
- 错误：`TimeoutExpired after 35s`

```json
[]
```

### asof_theme_labels / `stock_board_concept_cons_em:融资融券`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Current concept constituents only; not historical as-of constituents.
- 错误：`TimeoutExpired after 35s`

```json
[]
```

### listing_date / `stock_ipo_info:000001`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Per-symbol IPO info may include listing date; coverage for all symbols must be tested.
- 错误：`ReadTimeout: HTTPSConnectionPool(host='vip.stock.finance.sina.com.cn', port=443): Read timed out. (read timeout=20)`

```json
[]
```

### listing_date / `stock_ipo_info:600519`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Per-symbol IPO info may include listing date; coverage for all symbols must be tested.
- 错误：`ReadTimeout: HTTPSConnectionPool(host='vip.stock.finance.sina.com.cn', port=443): Read timed out. (read timeout=20)`

```json
[]
```

### listing_date / `stock_ipo_info:688981`

- 状态：`ERROR`
- 行数：`0`
- 字段：``
- 样例文件：`[MISSING]`
- 备注：Per-symbol IPO info may include listing date; coverage for all symbols must be tested.
- 错误：`ReadTimeout: HTTPSConnectionPool(host='vip.stock.finance.sina.com.cn', port=443): Read timed out. (read timeout=20)`

```json
[]
```

## 6. Go/No-Go

当前 Go/No-Go：`NO-GO for full historical executable backtest`。

原因：

- 分钟线和盘中上涨家数若只能通过当前/近期快照获得，不能回填历史决策时点。
- 涨跌停价目前只能通过涨跌停池和规则推导做部分验证，缺少 AkShare 已确认的全市场每日涨跌停价字段。
- 当前概念成份股不是历史 as-of 成份股，不能直接用于历史题材相关性约束。

允许继续做：

- 日频降级研究。
- 近期 smoke test。
- 从今天开始前向采集分钟线、盘中宽度和概念成份股快照。
