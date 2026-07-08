# theme_rotation_t1 — Run Artifact Contract

Every backtest run writes **one directory**:

```
data/backtest/theme_rotation_t1/runs/<UTC timestamp>_<tag>/
```

Example: `data/backtest/theme_rotation_t1/runs/20260708_040000_synthetic_demo/`

The report generator (`make_report.py`) is **read-only** over these files. It never re-derives strategy decisions or PnL.

---

## Required files

| File | Format | Purpose |
| --- | --- | --- |
| `run_meta.json` | JSON | Run provenance, sample window, data grade, `[MISSING]` fields, cost parameters |
| `equity_curve.csv` | CSV | Daily account state and drawdown |
| `trade_log.csv` | CSV | Closed and open trades — **must conform to** `schemas/trade_log.schema.yaml` |
| `decision_log.csv` | CSV | Every candidate every day (one row each) |
| `setup_stats.csv` | CSV | Per-setup rolling stats — **must conform to** `schemas/setup_stats.schema.yaml` |

Optional generated output (written by `make_report.py`, not the backtest):

| File | Purpose |
| --- | --- |
| `report.html` | Self-contained run dashboard |

Index output (written by `make_report.py --index`):

| File | Location |
| --- | --- |
| `runs_index.html` | `data/backtest/theme_rotation_t1/runs_index.html` |

---

## `run_meta.json`

```json
{
  "tag": "string — run label; synthetic demos must use synthetic_demo",
  "run_timestamp_utc": "YYYYMMDD_HHMMSS",
  "git_commit": "string — short SHA or [MISSING]",
  "rules_yaml_sha256": "string — hex digest of rules.yaml at run time",
  "sample_window": {
    "start": "YYYY-MM-DD",
    "end": "YYYY-MM-DD"
  },
  "data_coverage": {
    "bars": "daily | minute | synthetic | [MISSING]",
    "minute": true
  },
  "missing_fields": ["list of field names marked [MISSING] at run time"],
  "cost_parameters": {
    "initial_account": 100000,
    "commission_rate": 0.00025,
    "commission_min": 5,
    "stamp_tax_rate": 0.0005,
    "slippage_rate": 0.0015
  },
  "data_grade": "full_executable | daily_degraded_research_only"
}
```

### `data_grade`

| Value | Meaning |
| --- | --- |
| `full_executable` | Minute data + T+1 + limit rules + real costs — suitable for Go/No-Go |
| `daily_degraded_research_only` | Daily-bar approximation only — **not** execution-grade; report shows RED banner |

---

## `equity_curve.csv`

One row per trading day, sorted ascending by `date`.

| Column | Type | Description |
| --- | --- | --- |
| `date` | date | Trading calendar date |
| `equity` | number | Total account value (cash + mark-to-market positions) |
| `cash` | number | Free cash |
| `invested` | number | Market value of open positions |
| `daily_net_pnl` | number | Net PnL for the day (after costs) |
| `drawdown_pct` | number | Drawdown from running peak equity, 0–100 scale |

Report aggregates (net PnL, return %, max drawdown) are computed **only** from this file and `run_meta.json` `cost_parameters.initial_account`.

---

## `trade_log.csv`

Must include **all** `required_fields` from `schemas/trade_log.schema.yaml` exactly (column names and semantics).

Key columns used by the report:

- `setup_id`, `symbol`, `entry_date`, `exit_date`, `exit_reason`
- `gross_pnl`, `net_pnl`, `net_pnl_pct`
- `commission`, `stamp_tax`, `slippage`
- `limit_unfilled_flag`

---

## `decision_log.csv`

**Every candidate every day**, one row each.

| Column | Type | Description |
| --- | --- | --- |
| `date` | date | Decision date |
| `symbol` | string | Candidate symbol |
| `setup_id` | string | Setup that generated the candidate |
| `verdict` | enum | `entered` \| `blocked` \| `unfilled` |
| `reason_code` | string | Empty when `entered`; otherwise machine reason (e.g. `cooldown`, `breadth_below_min`, `limit_up_unfillable`) |

Used for: stacked verdict bars, reason breakdown, cooldown / block timeline markers.

---

## `setup_stats.csv`

Must conform to `schemas/setup_stats.schema.yaml`.

Typically one row per `(asof_date, setup_id)`. The report uses the **latest** `asof_date` per setup for summary cards and the full history per setup for rolling-30 expectancy sparklines.

---

## Synthetic / demo runs

Fixture and demo runs:

- `tag` **must** be `synthetic_demo`
- `report.html` shows watermark: **SYNTHETIC DATA — NOT A RESULT**
- May still use either `data_grade`; degraded grade additionally shows RED banner

---

## Missing artifacts

If a required file is absent, the report renders a visible **MISSING** placeholder for that panel. No silent fallback or fabricated values.

---

*Contract version 1 — theme_rotation_t1 lab. Read-only reporting; backtest engine is authoritative for all numbers.*
