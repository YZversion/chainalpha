"""HTML rendering for theme_rotation_t1 run reports."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .artifacts import (
    LoadedArtifacts,
    MoneySummary,
    count_reason_codes,
    latest_setup_stats_rows,
    setup_stats_history,
    summarize_money,
    timeline_events,
)
from .charts import bar_chart_signed, line_chart, sparkline, stacked_verdict_bars

CSS = """
:root {
  --bg: #f8fafc;
  --card: #ffffff;
  --text: #0f172a;
  --muted: #64748b;
  --border: #e2e8f0;
  --red: #dc2626;
  --green: #16a34a;
  --amber: #f59e0b;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
}
.watermark {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 9999;
  font-size: 3rem;
  font-weight: 800;
  color: rgba(220, 38, 38, 0.12);
  transform: rotate(-24deg);
  text-align: center;
  line-height: 1.2;
}
.banner-degraded {
  background: var(--red);
  color: #fff;
  padding: 12px 20px;
  font-weight: 700;
  text-align: center;
}
.banner-missing {
  background: var(--amber);
  color: #111;
  padding: 8px 20px;
  font-weight: 600;
}
header {
  background: var(--card);
  border-bottom: 1px solid var(--border);
  padding: 20px 24px;
}
header h1 { margin: 0 0 4px; font-size: 1.5rem; }
header .meta { color: var(--muted); font-size: 0.9rem; }
.missing-list { color: var(--red); font-weight: 600; }
main { max-width: 1100px; margin: 0 auto; padding: 20px 24px 48px; }
section {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 20px;
}
section h2 {
  margin: 0 0 16px;
  font-size: 1.1rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--muted);
}
.kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.kpi {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  background: #fafafa;
}
.kpi .label { font-size: 0.75rem; color: var(--muted); text-transform: uppercase; }
.kpi .value { font-size: 1.4rem; font-weight: 700; margin-top: 4px; }
.pos { color: var(--green); }
.neg { color: var(--red); }
.chart { display: block; max-width: 100%; height: auto; margin: 8px 0; }
.chart-title { font-size: 11px; fill: #334155; font-weight: 600; }
.chart-axis { font-size: 10px; fill: #64748b; }
.chart-legend { font-size: 10px; fill: #64748b; }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
th, td {
  border-bottom: 1px solid var(--border);
  padding: 6px 8px;
  text-align: left;
}
th { background: #f1f5f9; font-weight: 600; }
.setup-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}
.setup-card {
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  background: #fafafa;
}
.setup-card h3 {
  margin: 0 0 8px;
  font-size: 0.85rem;
  word-break: break-all;
}
.setup-card.disabled { border-color: var(--red); }
.missing-panel {
  padding: 24px;
  text-align: center;
  color: var(--muted);
  font-weight: 700;
  border: 2px dashed var(--border);
  border-radius: 8px;
}
.index-table a { color: #2563eb; text-decoration: none; }
.index-table a:hover { text-decoration: underline; }
"""


def _fmt_money(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}¥{v:,.0f}"


def _fmt_pct(v: float) -> str:
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.2f}%"


def _pnl_class(v: float) -> str:
    return "pos" if v >= 0 else "neg"


def _missing_panel(name: str) -> str:
    return f'<div class="missing-panel">MISSING — {name}</div>'


def _decision_stacked_data(art: LoadedArtifacts) -> tuple[list[str], list[int], list[int], list[int]]:
    by_date: dict[str, dict[str, int]] = defaultdict(lambda: {"entered": 0, "blocked": 0, "unfilled": 0})
    for row in art.decision_log:
        d = row["date"]
        v = row["verdict"]
        if v in by_date[d]:
            by_date[d][v] += 1
    dates = sorted(by_date.keys())
    entered = [by_date[d]["entered"] for d in dates]
    blocked = [by_date[d]["blocked"] for d in dates]
    unfilled = [by_date[d]["unfilled"] for d in dates]
    return dates, entered, blocked, unfilled


def _render_money(art: LoadedArtifacts, summary: MoneySummary | None) -> str:
    if not art.equity_curve or summary is None:
        return _missing_panel("equity_curve.csv / money summary")

    dates = [r["date"] for r in art.equity_curve]
    equities = [float(r["equity"]) for r in art.equity_curve]
    daily_pnl = [float(r["daily_net_pnl"]) for r in art.equity_curve]
    drawdowns = [float(r["drawdown_pct"]) for r in art.equity_curve]
    events = timeline_events(art)

    kpis = f"""
    <div class="kpi-row">
      <div class="kpi"><div class="label">Net PnL</div><div class="value {_pnl_class(summary.net_pnl)}">{_fmt_money(summary.net_pnl)}</div></div>
      <div class="kpi"><div class="label">Return</div><div class="value {_pnl_class(summary.return_pct)}">{_fmt_pct(summary.return_pct)}</div></div>
      <div class="kpi"><div class="label">Max Drawdown</div><div class="value neg">{summary.max_drawdown_pct:.2f}%</div></div>
      <div class="kpi"><div class="label">Total Friction</div><div class="value">{_fmt_money(summary.total_friction)}</div></div>
      <div class="kpi"><div class="label">Friction % of Account</div><div class="value">{summary.friction_pct:.2f}%</div></div>
    </div>
    """
    charts = (
        line_chart(dates, equities, title="Equity curve", events=events)
        + bar_chart_signed(dates, daily_pnl, title="Daily net PnL")
        + line_chart(dates, drawdowns, title="Drawdown %", stroke="#dc2626", y_format=".2f")
    )
    return kpis + charts


def _render_decisions(art: LoadedArtifacts) -> str:
    if not art.decision_log:
        return _missing_panel("decision_log.csv")

    dates, entered, blocked, unfilled = _decision_stacked_data(art)
    stacked = stacked_verdict_bars(dates, entered, blocked, unfilled)

    reasons = count_reason_codes(art.decision_log)
    reason_rows = "".join(
        f"<tr><td>{code}</td><td>{cnt}</td></tr>" for code, cnt in reasons.items()
    )
    reason_table = f"""
    <h3>Reason breakdown (non-entered)</h3>
    <table><thead><tr><th>Reason code</th><th>Count</th></tr></thead>
    <tbody>{reason_rows or '<tr><td colspan="2">—</td></tr>'}</tbody></table>
  """

    trade_rows = []
    for row in sorted(art.trade_log, key=lambda r: (r.get("entry_date", ""), r.get("symbol", ""))):
        net = row.get("net_pnl", "")
        net_f = float(net) if net and net.lower() not in ("", "null", "none") else 0.0
        cls = _pnl_class(net_f)
        trade_rows.append(
            "<tr>"
            f"<td>{row.get('setup_id', '')}</td>"
            f"<td>{row.get('symbol', '')}</td>"
            f"<td>{row.get('entry_date', '')}</td>"
            f"<td>{row.get('exit_date', '') or '—'}</td>"
            f"<td>{row.get('exit_reason', '') or '—'}</td>"
            f'<td class="{cls}">{net if net else "—"}</td>'
            "</tr>"
        )
    trade_table = f"""
    <h3>Trades</h3>
    <table><thead><tr>
      <th>setup_id</th><th>symbol</th><th>entry</th><th>exit</th><th>exit_reason</th><th>net_pnl</th>
    </tr></thead>
    <tbody>{''.join(trade_rows) or '<tr><td colspan="6">—</td></tr>'}</tbody></table>
  """
    return stacked + reason_table + trade_table


def _render_setups(art: LoadedArtifacts) -> str:
    if not art.setup_stats:
        return _missing_panel("setup_stats.csv")

    latest = latest_setup_stats_rows(art.setup_stats)
    cards = []
    for sid in sorted(latest.keys()):
        row = latest[sid]
        disabled = row.get("disabled", "").lower() in ("true", "1", "yes")
        hist = setup_stats_history(art.setup_stats, sid)
        roll_vals = []
        for h in hist:
            v = h.get("rolling_30_expectancy_pct", "")
            if v and v.lower() not in ("", "null", "none"):
                roll_vals.append(float(v))
        spark = sparkline(roll_vals, threshold=0.0)
        card_cls = "setup-card disabled" if disabled else "setup-card"
        cards.append(
            f'<div class="{card_cls}">'
            f"<h3>{sid}</h3>"
            f"<div>sample: {row.get('sample_count', '—')}</div>"
            f"<div>win rate: {float(row.get('win_rate', 0)) * 100:.1f}%</div>"
            f"<div>expectancy: {row.get('expectancy_pct', '—')}%</div>"
            f"<div>rolling-30: {spark}</div>"
            f"</div>"
        )
    return f'<div class="setup-grid">{"".join(cards)}</div>'


def _render_costs(art: LoadedArtifacts) -> str:
    if not art.trade_log:
        return _missing_panel("trade_log.csv")

    commission = stamp = slippage = 0.0
    limit_unfilled = 0
    for row in art.trade_log:
        for col, acc in (("commission", "c"), ("stamp_tax", "s"), ("slippage", "p")):
            val = row.get(col, "")
            if val and val.lower() not in ("", "null", "none"):
                amt = float(val)
                if col == "commission":
                    commission += amt
                elif col == "stamp_tax":
                    stamp += amt
                else:
                    slippage += amt
        flag = row.get("limit_unfilled_flag", "").lower()
        if flag in ("true", "1", "yes"):
            limit_unfilled += 1

    initial = art.initial_account
    rows = [
        ("Commission", commission),
        ("Stamp tax", stamp),
        ("Slippage", slippage),
    ]
    body = "".join(
        f"<tr><td>{name}</td><td>¥{amt:,.2f}</td><td>{(amt / initial * 100) if initial else 0:.3f}%</td></tr>"
        for name, amt in rows
    )
    return f"""
    <table>
      <thead><tr><th>Cost type</th><th>Total ¥</th><th>% of account</th></tr></thead>
      <tbody>{body}</tbody>
    </table>
    <h3>Limit-up / limit-down unfilled</h3>
    <p>Count: <strong>{limit_unfilled}</strong> trades flagged <code>limit_unfilled_flag</code></p>
  """


def render_report_html(art: LoadedArtifacts) -> str:
    summary = summarize_money(art)
    meta = art.meta or {}
    sample = meta.get("sample_window") or {}
    missing_fields = meta.get("missing_fields") or []
    missing_files = art.missing_files

    banners = []
    if art.data_grade == "daily_degraded_research_only":
        banners.append(
            '<div class="banner-degraded">daily_degraded_research_only — NOT execution-grade; daily-bar approximation only</div>'
        )
    if missing_files:
        banners.append(
            f'<div class="banner-missing">Missing artifacts: {", ".join(missing_files)}</div>'
        )

    watermark = ""
    if art.is_synthetic:
        watermark = '<div class="watermark">SYNTHETIC DATA — NOT A RESULT</div>'

    missing_str = ", ".join(missing_fields) if missing_fields else "none"
    header = f"""
    <header>
      <h1>theme_rotation_t1 — {art.tag}</h1>
      <div class="meta">
        Run dir: {art.run_dir.name} · data_grade: <strong>{art.data_grade}</strong><br>
        Sample: {sample.get('start', '—')} → {sample.get('end', '—')} ·
        git: {meta.get('git_commit', '—')} · rules hash: {meta.get('rules_yaml_sha256', '—')[:12]}…
      </div>
      <div class="meta missing-list">[MISSING] fields: {missing_str}</div>
    </header>
    """

    sections = [
        ("Money", _render_money(art, summary)),
        ("Decisions", _render_decisions(art)),
        ("Setups", _render_setups(art)),
        ("Costs", _render_costs(art)),
    ]
    body = "".join(f"<section><h2>{title}</h2>{content}</section>" for title, content in sections)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>theme_rotation_t1 report — {art.tag}</title>
  <style>{CSS}</style>
</head>
<body>
{watermark}
{''.join(banners)}
{header}
<main>{body}</main>
</body>
</html>
"""


def render_index_html(run_summaries: list[dict[str, Any]]) -> str:
    rows = []
    for s in run_summaries:
        grade = s.get("data_grade", "—")
        grade_cls = ' style="color:var(--red);font-weight:700"' if grade == "daily_degraded_research_only" else ""
        net = s.get("net_pnl")
        net_cls = _pnl_class(net) if net is not None else ""
        net_str = _fmt_money(net) if net is not None else "—"
        link = s.get("report_href", "#")
        rows.append(
            f"<tr>"
            f'<td><a href="{link}">{s.get("tag", "—")}</a></td>'
            f'<td>{s.get("run_date", "—")}</td>'
            f'<td{grade_cls}>{grade}</td>'
            f'<td class="{net_cls}">{net_str}</td>'
            f'<td>{s.get("max_dd", "—")}</td>'
            f'<td>{s.get("trade_count", "—")}</td>'
            f'<td>{s.get("friction_pct", "—")}</td>'
            f"</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>theme_rotation_t1 — runs index</title>
  <style>{CSS}</style>
</head>
<body>
<header>
  <h1>theme_rotation_t1 — All Runs</h1>
  <div class="meta">Newest first. Click tag to open report.html.</div>
</header>
<main>
  <section>
    <table class="index-table">
      <thead><tr>
        <th>Tag</th><th>Date</th><th>data_grade</th><th>Net PnL</th><th>Max DD</th><th>Trades</th><th>Friction %</th>
      </tr></thead>
      <tbody>{''.join(rows) or '<tr><td colspan="7">No runs found</td></tr>'}</tbody>
    </table>
  </section>
</main>
</body>
</html>
"""


def write_report(run_dir: Path) -> Path:
    from .artifacts import load_run_artifacts

    art = load_run_artifacts(run_dir)
    html = render_report_html(art)
    out = run_dir / "report.html"
    out.write_text(html, encoding="utf-8")
    return out


def write_index(runs_root: Path | None = None) -> Path:
    from .artifacts import RUNS_ROOT, discover_run_dirs, load_run_artifacts, summarize_money

    root = runs_root or RUNS_ROOT
    summaries: list[dict[str, Any]] = []
    for run_dir in discover_run_dirs(root):
        art = load_run_artifacts(run_dir)
        money = summarize_money(art)
        meta = art.meta or {}
        ts = meta.get("run_timestamp_utc") or run_dir.name.split("_")[0]
        summaries.append(
            {
                "tag": art.tag,
                "run_date": ts,
                "data_grade": art.data_grade,
                "net_pnl": money.net_pnl if money else None,
                "max_dd": f"{money.max_drawdown_pct:.2f}%" if money else "—",
                "trade_count": len(art.trade_log),
                "friction_pct": f"{money.friction_pct:.2f}%" if money else "—",
                "report_href": f"{run_dir.name}/report.html",
            }
        )

    html = render_index_html(summaries)
    out = root.parent / "runs_index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
