# 因子事件研究 — 报告模板

> **窗口**：2020-01-01 ~ 2025-12-31（`config/factor_screening.yaml`）
> **原则**：先验 Edge，不调参；无统计优势 → **DELETE**，不进入组合

## 如何运行

```powershell
conda activate chainalpha
cd D:\projects\chainalpha   # 或本仓库路径
$env:PYTHONPATH="src"

# ① 全市场下载（断点续传，约 5000 只 × 0.35s，数小时；需稳定网络）
python scripts/download_universe.py --all-market --start 2020-01-01 --end 2025-12-31

# ② 只跑「放量长上影」事件研究（读缓存或边下边算）
python scripts/run_factor_screening.py --all-market --cache-only --signal volume_spike_long_upper_shadow

# ③ 一条命令：下载 + 研究（首次全市场）
python scripts/run_factor_screening.py --all-market --signal volume_spike_long_upper_shadow --delay 0.35

# 探针 / 调试
python scripts/run_factor_screening.py --symbols 000001 600519 --signal volume_spike_long_upper_shadow
python scripts/run_factor_screening.py --all-market --limit 50 --signal volume_spike_long_upper_shadow
```

产出：
- 缓存 `data/raw/factor_screening/daily_parquet/*.parquet`
- Universe `data/raw/factor_screening/universe.json`
- 报告 `reports/factor_screening_volume_spike_long_upper_shadow.md`

---

## 汇总表（运行后自动填充）

| 信号 | 样本数 N | 3日均 | 5日均 | 10日均 | 5日超额 vs 随机 | 结论 |
|------|----------|-------|-------|--------|-----------------|------|
| volume_spike_long_upper_shadow | | | | | | KEEP / DELETE |
| limit_up_in_past_month | | | | | | KEEP / DELETE |

---

## Kill 标准（写死）

| 条件 | 动作 |
|------|------|
| 5 日均收益 ≤ -0.5% | **DELETE**（如你举的 -0.8% 案例） |
| 5 日均收益 < 0 且超额 < 0.1% | **DELETE** |
| 样本数 < 30 | **INSUFFICIENT_SAMPLE**（扩大 universe 后重跑） |
| 5 日均 ≥ 0 且超额 ≥ 0.1% | **KEEP**（进入下一阶段 IC/换手验证） |

---

## 单信号明细（复制节）

### {signal_name}

- **定义**：{description}
- **样本数**：
- **3 / 5 / 10 日平均收益**：
- **随机对照 5 日**：
- **超额**：
- **牛/熊/震荡子样本**：[MISSING] 待接入 benchmark 指数
- **结论**：DELETE / KEEP

---

## 待增信号（验证队列）

- [ ] 逆势股（需定义 + 牛熊分环境）
- [ ] 涨跌家数阈值（如 3000 家上涨）
- [ ] 供应链传导类（altdata 就绪后）

---

*DELETE 的信号从 `config/factor_screening.yaml` 的 `signals` 列表移除，不写进模型。*
