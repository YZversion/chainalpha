"""Small AkShare data availability probe for the theme_rotation_t1 lab.

This script audits fields only. It does not generate signals, positions, or orders.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[2]
TMP_AKSHARE_PATH = Path(r"C:\tmp\chainalpha_akshare_pkgs")
if TMP_AKSHARE_PATH.exists():
    sys.path.insert(0, str(TMP_AKSHARE_PATH))

try:
    import akshare as ak
    import pandas as pd
    import requests
except ImportError as exc:  # pragma: no cover - environment guard
    raise SystemExit(
        "AkShare/Pandas is not importable. Install with: "
        r"python -m pip install akshare pandas -t C:\tmp\chainalpha_akshare_pkgs"
    ) from exc


HTTP_TIMEOUT_SECONDS = 20
PER_CALL_TIMEOUT_SECONDS = 35
socket.setdefaulttimeout(HTTP_TIMEOUT_SECONDS)

_ORIGINAL_REQUEST = requests.sessions.Session.request


def _request_with_default_timeout(self: requests.Session, method: str, url: str, **kwargs: Any):
    kwargs.setdefault("timeout", HTTP_TIMEOUT_SECONDS)
    return _ORIGINAL_REQUEST(self, method, url, **kwargs)


requests.sessions.Session.request = _request_with_default_timeout


OUTPUT_ROOT = WORKSPACE / "data" / "raw" / "labs" / "theme_rotation_t1" / "akshare_probe"
REPORT_PATH = WORKSPACE / "reports" / "lab_theme_rotation_t1_data_audit.md"


@dataclass
class ProbeResult:
    field: str
    api: str
    status: str
    rows: int = 0
    columns: list[str] = field(default_factory=list)
    output_file: str | None = None
    sample: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    error: str | None = None
    elapsed_seconds: float = 0.0


def _safe_filename(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in name)


def _clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _records(df: pd.DataFrame, n: int = 3) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in df.head(n).to_dict(orient="records"):
        records.append({str(k): _clean_value(v) for k, v in row.items()})
    return records


def _save_df(df: pd.DataFrame, out_dir: Path, name: str) -> str:
    out_path = out_dir / f"{_safe_filename(name)}.csv"
    df.to_csv(out_path, index=False, encoding="utf-8")
    return str(out_path.relative_to(WORKSPACE))


def _call_df(
    *,
    field: str,
    api: str,
    fn: Callable[..., pd.DataFrame],
    out_dir: Path,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    status_if_nonempty: str = "CANDIDATE_NEEDS_LOCAL_PROBE",
    notes: list[str] | None = None,
    save_name: str | None = None,
) -> ProbeResult:
    start = time.perf_counter()
    kwargs = kwargs or {}
    notes = notes or []
    print(f"[probe] start {field} / {api}", flush=True)
    try:
        df = fn(*args, **kwargs)
        elapsed = time.perf_counter() - start
        if not isinstance(df, pd.DataFrame):
            return ProbeResult(
                field=field,
                api=api,
                status="ERROR",
                notes=notes,
                error=f"Expected pandas.DataFrame, got {type(df).__name__}",
                elapsed_seconds=elapsed,
            )
        output_file = None
        if not df.empty:
            output_file = _save_df(df, out_dir, save_name or f"{field}__{api}")
        result = ProbeResult(
            field=field,
            api=api,
            status=status_if_nonempty if not df.empty else "MISSING",
            rows=len(df),
            columns=[str(col) for col in df.columns],
            output_file=output_file,
            sample=_records(df),
            notes=notes,
            elapsed_seconds=elapsed,
        )
        print(
            f"[probe] done {field} / {api}: {result.status} rows={result.rows}",
            flush=True,
        )
        return result
    except Exception as exc:  # noqa: BLE001 - this is an audit script
        result = ProbeResult(
            field=field,
            api=api,
            status="ERROR",
            notes=notes,
            error=f"{type(exc).__name__}: {exc}",
            elapsed_seconds=time.perf_counter() - start,
        )
        print(f"[probe] error {field} / {api}: {result.error}", flush=True)
        return result


def _result_from_json(path: Path) -> ProbeResult:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ProbeResult(**data)


def _call_df_isolated(
    *,
    field: str,
    api: str,
    fn_name: str,
    out_dir: Path,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    status_if_nonempty: str = "CANDIDATE_NEEDS_LOCAL_PROBE",
    notes: list[str] | None = None,
    save_name: str | None = None,
) -> ProbeResult:
    task_dir = out_dir / "_tasks"
    task_dir.mkdir(parents=True, exist_ok=True)
    task_id = _safe_filename(api)
    task_path = task_dir / f"{task_id}.task.json"
    result_path = task_dir / f"{task_id}.result.json"
    task = {
        "field": field,
        "api": api,
        "fn_name": fn_name,
        "args": list(args),
        "kwargs": kwargs or {},
        "status_if_nonempty": status_if_nonempty,
        "notes": notes or [],
        "save_name": save_name,
        "out_dir": str(out_dir),
        "result_path": str(result_path),
    }
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[probe-parent] start {field} / {api}", flush=True)
    try:
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--single", str(task_path)],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=PER_CALL_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"[probe-parent] timeout {field} / {api}", flush=True)
        return ProbeResult(
            field=field,
            api=api,
            status="ERROR",
            notes=notes or [],
            error=f"TimeoutExpired after {PER_CALL_TIMEOUT_SECONDS}s",
            elapsed_seconds=PER_CALL_TIMEOUT_SECONDS,
        )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        print(f"[probe-parent] child error {field} / {api}: {stderr or stdout}", flush=True)
        return ProbeResult(
            field=field,
            api=api,
            status="ERROR",
            notes=notes or [],
            error=(stderr or stdout or f"child exited {completed.returncode}")[:1000],
        )
    if not result_path.exists():
        print(f"[probe-parent] missing child result {field} / {api}", flush=True)
        return ProbeResult(
            field=field,
            api=api,
            status="ERROR",
            notes=notes or [],
            error="Child completed but did not write result JSON.",
        )
    result = _result_from_json(result_path)
    print(f"[probe-parent] done {field} / {api}: {result.status} rows={result.rows}", flush=True)
    return result


def _run_single_task(task_path: Path) -> None:
    task = json.loads(task_path.read_text(encoding="utf-8"))
    fn = getattr(ak, task["fn_name"])
    result = _call_df(
        field=task["field"],
        api=task["api"],
        fn=fn,
        out_dir=Path(task["out_dir"]),
        args=tuple(task.get("args") or ()),
        kwargs=task.get("kwargs") or {},
        status_if_nonempty=task["status_if_nonempty"],
        notes=task.get("notes") or [],
        save_name=task.get("save_name"),
    )
    Path(task["result_path"]).write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _date_candidates(today: datetime, days: int = 14) -> list[str]:
    return [(today - timedelta(days=offset)).strftime("%Y%m%d") for offset in range(days)]


def _first_nonempty_by_date(
    *,
    field: str,
    api: str,
    fn: Callable[..., pd.DataFrame],
    out_dir: Path,
    dates: list[str],
    notes: list[str],
) -> ProbeResult:
    errors: list[str] = []
    for date in dates:
        result = _call_df(
            field=field,
            api=api,
            fn=fn,
            out_dir=out_dir,
            kwargs={"date": date},
            status_if_nonempty="PARTIAL",
            notes=[*notes, f"first non-empty date probe candidate: {date}"],
            save_name=f"{field}__{api}__{date}",
        )
        if result.status != "MISSING" and result.status != "ERROR":
            return result
        if result.error:
            errors.append(f"{date}: {result.error}")
    return ProbeResult(
        field=field,
        api=api,
        status="MISSING",
        notes=[*notes, "No non-empty result in recent date candidates."],
        error="; ".join(errors[:3]) if errors else None,
    )


def _first_nonempty_by_date_isolated(
    *,
    field: str,
    api: str,
    fn_name: str,
    out_dir: Path,
    dates: list[str],
    notes: list[str],
) -> ProbeResult:
    errors: list[str] = []
    for date in dates:
        result = _call_df_isolated(
            field=field,
            api=f"{api}:{date}",
            fn_name=fn_name,
            out_dir=out_dir,
            kwargs={"date": date},
            status_if_nonempty="PARTIAL",
            notes=[*notes, f"first non-empty date probe candidate: {date}"],
            save_name=f"{field}__{api}__{date}",
        )
        if result.status != "MISSING" and result.status != "ERROR":
            return result
        if result.error:
            errors.append(f"{date}: {result.error}")
    return ProbeResult(
        field=field,
        api=api,
        status="MISSING",
        notes=[*notes, "No non-empty result in recent date candidates."],
        error="; ".join(errors[:3]) if errors else None,
    )


def _append_derived_notes(results: list[ProbeResult]) -> dict[str, Any]:
    derived: dict[str, Any] = {}

    spot = next((r for r in results if r.field == "intraday_breadth"), None)
    if spot and spot.output_file:
        df = pd.read_csv(WORKSPACE / spot.output_file)
        pct_col = "涨跌幅" if "涨跌幅" in df.columns else None
        code_col = "代码" if "代码" in df.columns else None
        if pct_col:
            valid = pd.to_numeric(df[pct_col], errors="coerce").dropna()
            if not valid.empty:
                derived["advancers_ratio_current_snapshot"] = {
                    "advancers": int((valid > 0).sum()),
                    "decliners": int((valid < 0).sum()),
                    "flat": int((valid == 0).sum()),
                    "tradable_like_count": int(valid.shape[0]),
                    "ratio": float((valid > 0).sum() / valid.shape[0]),
                    "note": "Current snapshot only; not historical decision-time breadth.",
                }
        if code_col:
            derived["spot_code_count"] = int(df[code_col].nunique())

    return derived


def _field_summary(results: list[ProbeResult]) -> list[dict[str, str]]:
    by_field: dict[str, list[ProbeResult]] = {}
    for result in results:
        by_field.setdefault(result.field, []).append(result)

    summary: list[dict[str, str]] = []
    order = [
        "daily_ohlcv",
        "minute_bars",
        "intraday_breadth",
        "limit_prices",
        "historical_st_status",
        "delisting_history",
        "unlock_events",
        "shareholder_reduction",
        "inquiry_or_regulatory_letters",
        "asof_theme_labels",
        "listing_date",
    ]
    for field in order:
        items = by_field.get(field, [])
        statuses = {item.status for item in items}
        if not items:
            status = "MISSING"
        elif "OK" in statuses:
            status = "OK"
        elif "PARTIAL" in statuses:
            status = "PARTIAL"
        elif "CANDIDATE_NEEDS_LOCAL_PROBE" in statuses:
            status = "CANDIDATE_NEEDS_LOCAL_PROBE"
        elif "ERROR" in statuses:
            status = "ERROR"
        else:
            status = "MISSING"

        full_backtest = {
            "daily_ohlcv": "待二次核验",
            "minute_bars": "否",
            "intraday_breadth": "否",
            "limit_prices": "否",
            "historical_st_status": "否/待定",
            "delisting_history": "否/待定",
            "unlock_events": "待定",
            "shareholder_reduction": "否/待定",
            "inquiry_or_regulatory_letters": "待定",
            "asof_theme_labels": "否",
            "listing_date": "待定",
        }.get(field, "待定")
        summary.append({"field": field, "status": status, "full_backtest": full_backtest})
    return summary


def _md_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        values = [str(row.get(col, "")).replace("\n", " ") for col in columns]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _write_report(
    *,
    results: list[ProbeResult],
    derived: dict[str, Any],
    out_dir: Path,
    run_started_at: str,
) -> None:
    summary_rows = [
        {
            "字段": item["field"],
            "Probe 结论": item["status"],
            "是否可用于完整历史回测": item["full_backtest"],
        }
        for item in _field_summary(results)
    ]
    detail_rows = [
        {
            "字段": result.field,
            "接口": result.api,
            "状态": result.status,
            "行数": result.rows,
            "列数": len(result.columns),
            "样例文件": result.output_file or "",
            "错误": result.error or "",
        }
        for result in results
    ]

    derived_lines = "无"
    if derived:
        derived_lines = "\n".join(
            f"- `{key}`: `{json.dumps(value, ensure_ascii=False)}`"
            for key, value in derived.items()
        )

    sample_sections: list[str] = []
    for result in results:
        sample = json.dumps(result.sample[:2], ensure_ascii=False, indent=2)
        notes = "; ".join(result.notes)
        sample_sections.append(
            "\n".join(
                [
                    f"### {result.field} / `{result.api}`",
                    "",
                    f"- 状态：`{result.status}`",
                    f"- 行数：`{result.rows}`",
                    f"- 字段：`{', '.join(result.columns[:20])}`",
                    f"- 样例文件：`{result.output_file or '[MISSING]'}`",
                    f"- 备注：{notes or '无'}",
                    f"- 错误：`{result.error}`" if result.error else "- 错误：无",
                    "",
                    "```json",
                    sample,
                    "```",
                ]
            )
        )
    sample_sections_text = "\n\n".join(sample_sections)

    content = f"""# theme_rotation_t1 数据审计报告

状态：AkShare-only 小样本 probe 已执行。

本报告只记录公开数据源可得性，不构成投资建议。

## 1. 数据源口径

- 主数据源：AkShare
- AkShare 版本：`{getattr(ak, "__version__", "unknown")}`
- Python：`{sys.version.split()[0]}`
- Probe 时间：`{run_started_at}`
- 原始样例目录：`{out_dir.relative_to(WORKSPACE)}`
- 禁用：Tushare、券商 API、非公开数据、手工事后补标签
- 输出原则：拿不到或无法证明 as-of 的字段标 `[MISSING]`

## 2. 结论摘要

{_md_table(summary_rows, ["字段", "Probe 结论", "是否可用于完整历史回测"])}

## 3. 派生检查

{derived_lines}

## 4. 接口执行明细

{_md_table(detail_rows, ["字段", "接口", "状态", "行数", "列数", "样例文件", "错误"])}

## 5. 字段审计记录

{sample_sections_text}

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
"""
    REPORT_PATH.write_text(content, encoding="utf-8")


def main() -> None:
    run_started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = datetime.now()
    out_dir = OUTPUT_ROOT / today.strftime("%Y%m%d_%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)

    sample_symbols = ["000001", "600519", "300750", "688981", "837006"]
    start_daily = (today - timedelta(days=90)).strftime("%Y%m%d")
    end_daily = today.strftime("%Y%m%d")
    start_minute = (today - timedelta(days=30)).strftime("%Y-%m-%d 09:30:00")
    end_minute = today.strftime("%Y-%m-%d 15:00:00")
    dates = _date_candidates(today)

    results: list[ProbeResult] = []

    results.append(
        _call_df_isolated(
            field="listing_date",
            api="stock_info_a_code_name",
            fn_name="stock_info_a_code_name",
            out_dir=out_dir,
            status_if_nonempty="PARTIAL",
            notes=["A-share code/name list only; listing date still needs stock_ipo_info per symbol."],
        )
    )

    for symbol in sample_symbols:
        results.append(
            _call_df_isolated(
                field="daily_ohlcv",
                api=f"stock_zh_a_hist:{symbol}",
                fn_name="stock_zh_a_hist",
                out_dir=out_dir,
                kwargs={
                    "symbol": symbol,
                    "period": "daily",
                    "start_date": start_daily,
                    "end_date": end_daily,
                    "adjust": "",
                    "timeout": HTTP_TIMEOUT_SECONDS,
                },
                status_if_nonempty="OK",
                notes=["Unadjusted daily OHLCV sample; use raw prices for limit checks."],
            )
        )

    results.append(
        _call_df_isolated(
            field="minute_bars",
            api="stock_zh_a_hist_min_em:000001:5m",
            fn_name="stock_zh_a_hist_min_em",
            out_dir=out_dir,
            kwargs={
                "symbol": "000001",
                "start_date": start_minute,
                "end_date": end_minute,
                "period": "5",
                "adjust": "",
            },
            status_if_nonempty="PARTIAL",
            notes=["Probe requests 30 calendar days; coverage must be inspected before historical backtest."],
        )
    )

    results.append(
        _call_df_isolated(
            field="intraday_breadth",
            api="stock_zh_a_spot_em",
            fn_name="stock_zh_a_spot_em",
            out_dir=out_dir,
            status_if_nonempty="PARTIAL",
            notes=["Current full-market snapshot only; historical decision-time breadth needs forward archive."],
        )
    )

    results.append(
        _first_nonempty_by_date_isolated(
            field="limit_prices",
            api="stock_zt_pool_em",
            fn_name="stock_zt_pool_em",
            out_dir=out_dir,
            dates=dates,
            notes=["Limit-up pool only; not full-market daily limit prices."],
        )
    )
    results.append(
        _first_nonempty_by_date_isolated(
            field="limit_prices",
            api="stock_zt_pool_dtgc_em",
            fn_name="stock_zt_pool_dtgc_em",
            out_dir=out_dir,
            dates=dates,
            notes=["Limit-down pool only; not full-market daily limit prices."],
        )
    )

    results.append(
        _call_df_isolated(
            field="historical_st_status",
            api="stock_zh_a_st_em",
            fn_name="stock_zh_a_st_em",
            out_dir=out_dir,
            status_if_nonempty="PARTIAL",
            notes=["Current risk-warning board only; not historical ST intervals."],
        )
    )
    results.append(
        _call_df_isolated(
            field="historical_st_status",
            api="stock_info_change_name:000503",
            fn_name="stock_info_change_name",
            out_dir=out_dir,
            kwargs={"symbol": "000503"},
            status_if_nonempty="PARTIAL",
            notes=["Sina previous-name list has names but no effective dates."],
        )
    )
    results.append(
        _call_df_isolated(
            field="historical_st_status",
            api="stock_info_sz_change_name:简称变更",
            fn_name="stock_info_sz_change_name",
            out_dir=out_dir,
            kwargs={"symbol": "简称变更"},
            status_if_nonempty="PARTIAL",
            notes=["SZSE name-change history has dates but does not cover Shanghai/Beijing markets."],
        )
    )

    results.append(
        _call_df_isolated(
            field="delisting_history",
            api="stock_staq_net_stop",
            fn_name="stock_staq_net_stop",
            out_dir=out_dir,
            status_if_nonempty="PARTIAL",
            notes=["Delisted/STAQ/NET list; still needs merge with historical tradeable universe."],
        )
    )
    results.append(
        _call_df_isolated(
            field="delisting_history",
            api="stock_zh_a_stop_em",
            fn_name="stock_zh_a_stop_em",
            out_dir=out_dir,
            status_if_nonempty="PARTIAL",
            notes=["Current delisted-board quote/list; not sufficient alone for survivor-bias-free backtest."],
        )
    )

    results.append(
        _call_df_isolated(
            field="unlock_events",
            api="stock_restricted_release_queue_sina:600000",
            fn_name="stock_restricted_release_queue_sina",
            out_dir=out_dir,
            kwargs={"symbol": "600000"},
            status_if_nonempty="OK",
            notes=["Per-symbol unlock queue includes announcement date in AkShare docs and sample if returned."],
        )
    )

    if hasattr(ak, "stock_restricted_release_detail_em"):
        results.append(
            _call_df_isolated(
                field="unlock_events",
                api="stock_restricted_release_detail_em",
                fn_name="stock_restricted_release_detail_em",
                out_dir=out_dir,
                kwargs={
                    "start_date": (today - timedelta(days=30)).strftime("%Y%m%d"),
                    "end_date": (today + timedelta(days=30)).strftime("%Y%m%d"),
                },
                status_if_nonempty="PARTIAL",
                notes=["Market-wide unlock detail can help candidate filtering but may include post-event performance fields."],
            )
        )

    results.append(
        _call_df_isolated(
            field="shareholder_reduction",
            api="stock_ggcg_em:全部",
            fn_name="stock_ggcg_em",
            out_dir=out_dir,
            kwargs={"symbol": "全部"},
            status_if_nonempty="PARTIAL",
            notes=["Shareholder increase/decrease records; cannot prove announced-but-unfinished reduction without pairing plan/completion announcements."],
        )
    )

    results.append(
        _call_df_isolated(
            field="inquiry_or_regulatory_letters",
            api="stock_individual_notice_report:000001:全部",
            fn_name="stock_individual_notice_report",
            out_dir=out_dir,
            kwargs={
                "security": "000001",
                "symbol": "全部",
                "begin_date": (today - timedelta(days=365)).strftime("%Y%m%d"),
                "end_date": today.strftime("%Y%m%d"),
            },
            status_if_nonempty="CANDIDATE_NEEDS_LOCAL_PROBE",
            notes=["Announcement titles can be keyword-filtered; coverage of exchange letters must be manually sampled."],
        )
    )

    results.append(
        _call_df_isolated(
            field="asof_theme_labels",
            api="stock_board_concept_name_em",
            fn_name="stock_board_concept_name_em",
            out_dir=out_dir,
            status_if_nonempty="PARTIAL",
            notes=["Current concept list only."],
        )
    )
    results.append(
        _call_df_isolated(
            field="asof_theme_labels",
            api="stock_board_concept_cons_em:融资融券",
            fn_name="stock_board_concept_cons_em",
            out_dir=out_dir,
            kwargs={"symbol": "融资融券"},
            status_if_nonempty="PARTIAL",
            notes=["Current concept constituents only; not historical as-of constituents."],
        )
    )

    for symbol in ["000001", "600519", "688981"]:
        if hasattr(ak, "stock_ipo_info"):
            results.append(
                _call_df_isolated(
                    field="listing_date",
                    api=f"stock_ipo_info:{symbol}",
                    fn_name="stock_ipo_info",
                    out_dir=out_dir,
                    kwargs={"stock": symbol},
                    status_if_nonempty="CANDIDATE_NEEDS_LOCAL_PROBE",
                    notes=["Per-symbol IPO info may include listing date; coverage for all symbols must be tested."],
                )
            )

    derived = _append_derived_notes(results)
    summary_path = out_dir / "probe_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "run_started_at": run_started_at,
                "akshare_version": getattr(ak, "__version__", "unknown"),
                "results": [asdict(result) for result in results],
                "derived": derived,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _write_report(results=results, derived=derived, out_dir=out_dir, run_started_at=run_started_at)

    print(f"probe_summary={summary_path}")
    print(f"report={REPORT_PATH}")
    print(f"results={len(results)}")


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--single":
        _run_single_task(Path(sys.argv[2]))
    else:
        main()
