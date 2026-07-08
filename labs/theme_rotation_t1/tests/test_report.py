"""Report generator tests — artifact validation, aggregation, index."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from report.artifacts import (
    count_reason_codes,
    count_verdicts,
    discover_run_dirs,
    load_run_artifacts,
    summarize_money,
    validate_decision_log,
    validate_equity_curve,
    validate_setup_stats,
    validate_trade_log,
)
from report.html_render import render_index_html, render_report_html, write_index, write_report

FIXTURE_RUN = Path(__file__).resolve().parent / "fixtures" / "synthetic_demo_run"
MAKE_REPORT = Path(__file__).resolve().parents[1] / "report" / "make_report.py"


@pytest.fixture(scope="module")
def loaded_fixture():
    return load_run_artifacts(FIXTURE_RUN)


class TestArtifactSchemaValidation:
    def test_trade_log_valid(self, loaded_fixture):
        assert loaded_fixture.load_errors == []

    def test_setup_stats_valid(self, loaded_fixture):
        errs = validate_setup_stats(loaded_fixture.setup_stats)
        assert errs == []

    def test_decision_log_valid(self, loaded_fixture):
        errs = validate_decision_log(loaded_fixture.decision_log)
        assert errs == []

    def test_equity_curve_valid(self, loaded_fixture):
        errs = validate_equity_curve(loaded_fixture.equity_curve)
        assert errs == []

    def test_trade_log_detects_bad_setup(self):
        rows = [{"setup_id": "not_a_setup"}]
        assert any("invalid setup_id" in e for e in validate_trade_log(rows))


class TestAggregationMath:
    def test_net_pnl_from_equity_curve(self, loaded_fixture):
        summary = summarize_money(loaded_fixture)
        assert summary is not None
        assert summary.initial_account == 100_000
        assert summary.final_equity == pytest.approx(97_880.0)
        assert summary.net_pnl == pytest.approx(-2_120.0)
        assert summary.return_pct == pytest.approx(-2.12, rel=1e-3)

    def test_max_drawdown_from_equity_curve(self, loaded_fixture):
        summary = summarize_money(loaded_fixture)
        assert summary is not None
        assert summary.max_drawdown_pct == pytest.approx(2.24, rel=1e-3)

    def test_friction_from_trade_log(self, loaded_fixture):
        summary = summarize_money(loaded_fixture)
        assert summary is not None
        expected = 0.0
        for row in loaded_fixture.trade_log:
            for col in ("commission", "stamp_tax", "slippage"):
                val = row.get(col, "")
                if val and val.lower() not in ("", "null", "none"):
                    expected += float(val)
        assert summary.total_friction == pytest.approx(expected)
        assert summary.friction_pct == pytest.approx(expected / 100_000 * 100)


class TestReasonCodeCounting:
    def test_verdict_counts(self, loaded_fixture):
        counts = count_verdicts(loaded_fixture.decision_log)
        assert counts["entered"] == 6
        assert counts["blocked"] == 10
        assert counts["unfilled"] == 4

    def test_reason_code_counts(self, loaded_fixture):
        reasons = count_reason_codes(loaded_fixture.decision_log)
        assert reasons["cooldown"] == 4
        assert reasons["breadth_below_min"] == 4
        assert reasons["limit_up_unfillable"] == 3
        assert reasons["missing:intraday_breadth"] == 1


class TestReportGeneration:
    def test_render_report_html(self, loaded_fixture):
        html = render_report_html(loaded_fixture)
        assert "SYNTHETIC DATA — NOT A RESULT" in html
        assert "daily_degraded_research_only" in html
        assert "banner-degraded" in html
        assert "[MISSING] fields: days_to_next_unlock, intraday_breadth" in html
        assert "<svg" in html
        assert "http://" not in html.lower()
        assert "https://" not in html.lower()

    def test_write_report_cli(self, tmp_path):
        run_dir = tmp_path / "demo_run"
        shutil.copytree(FIXTURE_RUN, run_dir)
        out = write_report(run_dir)
        assert out.is_file()
        text = out.read_text(encoding="utf-8")
        assert "SYNTHETIC DATA — NOT A RESULT" in text

    def test_make_report_subprocess(self, tmp_path):
        run_dir = tmp_path / "cli_run"
        shutil.copytree(FIXTURE_RUN, run_dir)
        proc = subprocess.run(
            [sys.executable, str(MAKE_REPORT), str(run_dir)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert proc.returncode == 0
        assert (run_dir / "report.html").is_file()


class TestIndexSorting:
    def test_discover_run_dirs_newest_first(self, tmp_path):
        runs = tmp_path / "runs"
        runs.mkdir()
        (runs / "20200101_000000_old").mkdir()
        (runs / "20260201_000000_new").mkdir()
        (runs / "20250101_000000_mid").mkdir()
        found = discover_run_dirs(runs)
        assert [p.name for p in found] == [
            "20260201_000000_new",
            "20250101_000000_mid",
            "20200101_000000_old",
        ]

    def test_index_rows_newest_first(self, tmp_path):
        runs = tmp_path / "runs"
        for name in ("20200101_000000_a", "20260201_000000_c", "20250101_000000_b"):
            d = runs / name
            d.mkdir(parents=True)
            shutil.copytree(FIXTURE_RUN, d, dirs_exist_ok=True)
            meta_path = d / "run_meta.json"
            meta = meta_path.read_text(encoding="utf-8")
            meta = meta.replace("20260708_040000", name.split("_")[0] + "_120000")
            meta_path.write_text(meta, encoding="utf-8")

        out = write_index(runs)
        html = out.read_text(encoding="utf-8")
        tags = re.findall(r"<tr><td><a href=", html)
        assert len(tags) == 3
        c_pos = html.index("20260201_000000_c")
        b_pos = html.index("20250101_000000_b")
        a_pos = html.index("20200101_000000_a")
        assert c_pos < b_pos < a_pos

    def test_render_index_no_external_urls(self):
        html = render_index_html(
            [
                {
                    "tag": "t",
                    "run_date": "d",
                    "data_grade": "full_executable",
                    "net_pnl": 0,
                    "max_dd": "0%",
                    "trade_count": 0,
                    "friction_pct": "0%",
                    "report_href": "x/report.html",
                }
            ]
        )
        assert "https://" not in html.lower()
