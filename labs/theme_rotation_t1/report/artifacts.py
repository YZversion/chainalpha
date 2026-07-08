"""Load and validate theme_rotation_t1 run artifacts (read-only)."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

LAB_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = LAB_ROOT / "schemas"
REPO_ROOT = LAB_ROOT.parent.parent
RUNS_ROOT = REPO_ROOT / "data" / "backtest" / "theme_rotation_t1" / "runs"

REQUIRED_FILES = (
    "run_meta.json",
    "equity_curve.csv",
    "trade_log.csv",
    "decision_log.csv",
    "setup_stats.csv",
)

DECISION_LOG_COLUMNS = ("date", "symbol", "setup_id", "verdict", "reason_code")
EQUITY_CURVE_COLUMNS = (
    "date",
    "equity",
    "cash",
    "invested",
    "daily_net_pnl",
    "drawdown_pct",
)
VERDICTS = frozenset({"entered", "blocked", "unfilled"})


@dataclass
class LoadedArtifacts:
    run_dir: Path
    meta: dict[str, Any] | None = None
    equity_curve: list[dict[str, str]] = field(default_factory=list)
    trade_log: list[dict[str, str]] = field(default_factory=list)
    decision_log: list[dict[str, str]] = field(default_factory=list)
    setup_stats: list[dict[str, str]] = field(default_factory=list)
    missing_files: list[str] = field(default_factory=list)
    load_errors: list[str] = field(default_factory=list)

    @property
    def tag(self) -> str:
        if self.meta and "tag" in self.meta:
            return str(self.meta["tag"])
        return self.run_dir.name

    @property
    def is_synthetic(self) -> bool:
        return self.tag == "synthetic_demo"

    @property
    def data_grade(self) -> str:
        if self.meta and "data_grade" in self.meta:
            return str(self.meta["data_grade"])
        return "[MISSING]"

    @property
    def initial_account(self) -> float:
        if self.meta:
            costs = self.meta.get("cost_parameters") or {}
            if "initial_account" in costs:
                return float(costs["initial_account"])
        return 100_000.0


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _load_yaml_schema(name: str) -> dict[str, Any]:
    with (SCHEMA_DIR / name).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def validate_trade_log(rows: list[dict[str, str]]) -> list[str]:
    schema = _load_yaml_schema("trade_log.schema.yaml")
    required = list(schema["required_fields"].keys())
    errors: list[str] = []
    if not rows:
        errors.append("trade_log: no rows")
        return errors
    cols = set(rows[0].keys())
    for col in required:
        if col not in cols:
            errors.append(f"trade_log: missing column {col}")
    allowed_setup = set(schema["required_fields"]["setup_id"]["allowed"])
    allowed_exit = set(schema["required_fields"]["exit_reason"]["allowed"])
    for i, row in enumerate(rows):
        sid = row.get("setup_id", "")
        if sid and sid not in allowed_setup:
            errors.append(f"trade_log row {i}: invalid setup_id {sid!r}")
        er = row.get("exit_reason", "")
        if er and er not in allowed_exit and er.lower() not in ("", "null", "none"):
            errors.append(f"trade_log row {i}: invalid exit_reason {er!r}")
    return errors


def validate_setup_stats(rows: list[dict[str, str]]) -> list[str]:
    schema = _load_yaml_schema("setup_stats.schema.yaml")
    required = list(schema["required_fields"].keys())
    errors: list[str] = []
    if not rows:
        errors.append("setup_stats: no rows")
        return errors
    cols = set(rows[0].keys())
    for col in required:
        if col not in cols:
            errors.append(f"setup_stats: missing column {col}")
    allowed_setup = set(schema["required_fields"]["setup_id"]["allowed"])
    for i, row in enumerate(rows):
        sid = row.get("setup_id", "")
        if sid and sid not in allowed_setup:
            errors.append(f"setup_stats row {i}: invalid setup_id {sid!r}")
    return errors


def validate_decision_log(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    if not rows:
        errors.append("decision_log: no rows")
        return errors
    cols = set(rows[0].keys())
    for col in DECISION_LOG_COLUMNS:
        if col not in cols:
            errors.append(f"decision_log: missing column {col}")
    for i, row in enumerate(rows):
        v = row.get("verdict", "")
        if v not in VERDICTS:
            errors.append(f"decision_log row {i}: invalid verdict {v!r}")
    return errors


def validate_equity_curve(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    if not rows:
        errors.append("equity_curve: no rows")
        return errors
    cols = set(rows[0].keys())
    for col in EQUITY_CURVE_COLUMNS:
        if col not in cols:
            errors.append(f"equity_curve: missing column {col}")
    return errors


def load_run_artifacts(run_dir: Path) -> LoadedArtifacts:
    run_dir = Path(run_dir).resolve()
    art = LoadedArtifacts(run_dir=run_dir)

    meta_path = run_dir / "run_meta.json"
    if meta_path.is_file():
        try:
            with meta_path.open(encoding="utf-8") as fh:
                art.meta = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            art.load_errors.append(f"run_meta.json: {exc}")
    else:
        art.missing_files.append("run_meta.json")

    for fname, attr, validator in (
        ("equity_curve.csv", "equity_curve", validate_equity_curve),
        ("trade_log.csv", "trade_log", validate_trade_log),
        ("decision_log.csv", "decision_log", validate_decision_log),
        ("setup_stats.csv", "setup_stats", validate_setup_stats),
    ):
        path = run_dir / fname
        if not path.is_file():
            art.missing_files.append(fname)
            continue
        try:
            rows = _read_csv(path)
            setattr(art, attr, rows)
            art.load_errors.extend(validator(rows))
        except OSError as exc:
            art.load_errors.append(f"{fname}: {exc}")

    return art


def discover_run_dirs(runs_root: Path | None = None) -> list[Path]:
    root = runs_root or RUNS_ROOT
    if not root.is_dir():
        return []
    dirs = [p for p in root.iterdir() if p.is_dir()]
    dirs.sort(key=lambda p: p.name, reverse=True)
    return dirs


@dataclass
class MoneySummary:
    initial_account: float
    final_equity: float
    net_pnl: float
    return_pct: float
    max_drawdown_pct: float
    total_friction: float
    friction_pct: float


def summarize_money(art: LoadedArtifacts) -> MoneySummary | None:
    if not art.equity_curve:
        return None
    initial = art.initial_account
    equities = [float(r["equity"]) for r in art.equity_curve]
    drawdowns = [float(r["drawdown_pct"]) for r in art.equity_curve]
    final = equities[-1]
    net_pnl = final - initial
    return_pct = (net_pnl / initial) * 100.0 if initial else 0.0
    max_dd = max(drawdowns) if drawdowns else 0.0

    total_friction = 0.0
    for row in art.trade_log:
        for col in ("commission", "stamp_tax", "slippage"):
            val = row.get(col, "")
            if val and val.lower() not in ("", "null", "none"):
                total_friction += float(val)

    friction_pct = (total_friction / initial) * 100.0 if initial else 0.0
    return MoneySummary(
        initial_account=initial,
        final_equity=final,
        net_pnl=net_pnl,
        return_pct=return_pct,
        max_drawdown_pct=max_dd,
        total_friction=total_friction,
        friction_pct=friction_pct,
    )


def count_verdicts(decision_log: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {"entered": 0, "blocked": 0, "unfilled": 0}
    for row in decision_log:
        v = row.get("verdict", "")
        if v in counts:
            counts[v] += 1
    return counts


def count_reason_codes(decision_log: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in decision_log:
        if row.get("verdict") == "entered":
            continue
        code = (row.get("reason_code") or "").strip() or "(empty)"
        counts[code] = counts.get(code, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def latest_setup_stats_rows(setup_stats: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    by_setup: dict[str, dict[str, str]] = {}
    for row in setup_stats:
        sid = row["setup_id"]
        prev = by_setup.get(sid)
        if prev is None or row["asof_date"] > prev["asof_date"]:
            by_setup[sid] = row
    return by_setup


def setup_stats_history(
    setup_stats: list[dict[str, str]], setup_id: str
) -> list[dict[str, str]]:
    rows = [r for r in setup_stats if r["setup_id"] == setup_id]
    rows.sort(key=lambda r: r["asof_date"])
    return rows


def timeline_events(art: LoadedArtifacts) -> list[dict[str, str]]:
    events: list[dict[str, str]] = []
    for row in art.decision_log:
        code = (row.get("reason_code") or "").strip()
        if row.get("verdict") == "blocked" and "cooldown" in code:
            events.append(
                {
                    "date": row["date"],
                    "kind": "cooldown",
                    "label": f"cooldown: {row['symbol']}",
                }
            )
    for row in art.trade_log:
        if row.get("exit_reason") == "setup_disabled":
            events.append(
                {
                    "date": row.get("exit_date") or row.get("entry_date", ""),
                    "kind": "setup_disabled",
                    "label": f"setup_disabled: {row['symbol']}",
                }
            )
        elif row.get("exit_reason") == "system_disabled":
            events.append(
                {
                    "date": row.get("exit_date") or row.get("entry_date", ""),
                    "kind": "system_disabled",
                    "label": f"system_disabled: {row['symbol']}",
                }
            )
    for row in art.setup_stats:
        if row.get("disabled", "").lower() in ("true", "1", "yes"):
            events.append(
                {
                    "date": row["asof_date"],
                    "kind": "setup_disabled",
                    "label": f"disabled: {row['setup_id']}",
                }
            )
    events.sort(key=lambda e: e["date"])
    return events
