"""批量运行因子事件研究并输出报告。"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from chainalpha.factors.event_study import EventStudyResult, KillCriteria, run_event_study
from chainalpha.factors.events import get_signal
from chainalpha.factors.forward_return import DEFAULT_HORIZONS

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "factor_screening.yaml"
REPORTS_DIR = ROOT / "reports"


def load_screening_config(path: Path | None = None) -> dict:
    cfg_path = path or CONFIG_PATH
    with cfg_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def kill_criteria_from_config(cfg: dict) -> KillCriteria:
    k = cfg.get("kill_criteria", {})
    return KillCriteria(
        min_signal_count=int(k.get("min_signal_count", 30)),
        primary_horizon=int(k.get("primary_horizon", 5)),
        delete_if_mean_below=float(k.get("delete_if_mean_below", 0.0)),
        delete_if_excess_below=float(k.get("delete_if_excess_below", 0.001)),
        strong_delete_if_mean_below=float(k.get("strong_delete_if_mean_below", -0.005)),
    )


def run_all_signals(
    panel,
    config: dict | None = None,
    *,
    signal_names: list[str] | None = None,
) -> list[EventStudyResult]:
    cfg = config or load_screening_config()
    dr = cfg["date_range"]
    horizons = tuple(cfg.get("horizons", list(DEFAULT_HORIZONS)))
    criteria = kill_criteria_from_config(cfg)
    seed = int(cfg.get("random_seed", 42))
    names: list[str] = signal_names if signal_names is not None else cfg.get("signals", [])

    results: list[EventStudyResult] = []
    for name in names:
        spec = get_signal(name)
        results.append(
            run_event_study(
                panel,
                spec,
                start_date=dr["start"],
                end_date=dr["end"],
                horizons=horizons,
                criteria=criteria,
                random_seed=seed,
            )
        )
    return results

def render_markdown(results: list[EventStudyResult]) -> str:
    if not results:
        return "# 因子筛选报告\n\n[MISSING] 无结果\n"

    lines = [
        "# 因子事件研究报告",
        "",
        f"> 窗口：{results[0].start_date} ~ {results[0].end_date}",
        "> 方法：信号日 forward return vs 同规模随机对照；无 Edge → DELETE",
        "",
        "## 汇总",
        "",
        "| 信号 | 样本数 | 5日均收益 | 5日超额 | 结论 |",
        "|------|--------|-----------|---------|------|",
    ]
    for r in results:
        h5 = next((h for h in r.horizon_stats if h.horizon == 5), None)
        mean5 = f"{h5.signal_mean:.2%}" if h5 else "N/A"
        exc5 = f"{h5.excess:.2%}" if h5 else "N/A"
        lines.append(
            f"| {r.signal_name} | {r.signal_count} | {mean5} | {exc5} | **{r.verdict}** |"
        )

    for r in results:
        lines.extend(["", f"## {r.signal_name}", "", f"_{r.signal_description}_", ""])
        lines.append(f"**结论**：{r.verdict} — {r.verdict_reason}")
        lines.append("")
        lines.append("| 持有期 | 信号均值 | 随机均值 | 超额 | 中位数 | t | p |")
        lines.append("|--------|----------|----------|------|--------|---|---|")
        for h in r.horizon_stats:
            lines.append(
                f"| {h.horizon}日 | {h.signal_mean:.2%} | {h.random_mean:.2%} | "
                f"{h.excess:.2%} | {h.signal_median:.2%} | "
                f"{h.t_stat:.2f} | {h.p_value:.3f} |"
            )

    lines.append("")
    lines.append("---")
    lines.append("*仅供研究，不构成投资建议。样本不足时结论为 INSUFFICIENT_SAMPLE。*")
    return "\n".join(lines)


def write_report(
    results: list[EventStudyResult],
    *,
    reports_dir: Path | None = None,
    stem: str = "factor_screening",
) -> tuple[Path, Path]:
    out_dir = reports_dir or REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{stem}.md"
    json_path = out_dir / f"{stem}.json"

    md_path.write_text(render_markdown(results), encoding="utf-8")
    payload = [r.to_dict() for r in results]
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path, json_path
