from __future__ import annotations

import logging
from pathlib import Path

from project.report_runtime import ACTUAL_SMOKE_PERSISTENCE_POLICY, persist_report


def test_actual_smoke_policy_prevents_history_and_risk_state_persistence(tmp_path, monkeypatch) -> None:
    reports_dir = tmp_path / "reports"
    sample_dir = tmp_path / "sample"
    reports_dir.mkdir()
    sample_dir.mkdir()
    history_dir = reports_dir / "history"
    history_dir.mkdir()
    history_json = history_dir / "report_2026-06-22_120000.json"

    def fake_write_reports(report, reports_dir, sample_output_dir):
        reports_path = Path(reports_dir)
        history_path = reports_path / "history"
        md = reports_path / "report.md"
        html = reports_path / "report.html"
        hmd = history_path / "report_2026-06-22_120000.md"
        hhtml = history_path / "report_2026-06-22_120000.html"
        for path in (md, html, hmd, hhtml):
            path.write_text("temporary report", encoding="utf-8")
        return md, html, hmd, hhtml, history_json

    risk_state_calls: list[object] = []
    monkeypatch.setattr("project.report_runtime.write_reports", fake_write_reports)
    monkeypatch.setattr("project.report_runtime.write_dashboard", lambda reports_dir: Path(reports_dir) / "dashboard.html")
    monkeypatch.setattr("project.report_runtime.write_risk_domain_state", lambda path, state: risk_state_calls.append((path, state)))

    report = {
        "data_reliability": {"decision_allowed": True},
        "risk_engine_state": {"will_persist": True, "path": str(tmp_path / "risk_state.json"), "next_state": {"stage": "normal"}},
    }
    persist_report(
        report,
        {"reports_dir": str(reports_dir), "sample_output_dir": str(sample_dir)},
        logging.getLogger("test"),
        persistence_policy=ACTUAL_SMOKE_PERSISTENCE_POLICY,
    )

    assert (reports_dir / "report.md").exists()
    assert (reports_dir / "report_summary.json").exists()
    assert not history_json.exists()
    assert not risk_state_calls
