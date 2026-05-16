from __future__ import annotations

import shutil
from pathlib import Path

from project.report_generator import write_reports


WORK_DIR = Path(__file__).resolve().parents[1] / "test_output_history"


def test_write_reports_creates_history_files():
    if WORK_DIR.exists():
        shutil.rmtree(WORK_DIR)
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    report = {
        "title": "Test Report",
        "generated_at": "2026-03-19T21:20:30",
        "data_source": "sample",
        "regime": {
            "regime_label": "risk_on",
            "trend_strength": 30.0,
            "momentum_12w": 0.12,
            "max_drawdown": -0.05,
        },
        "cycle": {"phase_label": "upswing", "phase_angle_deg": 10},
        "score": {"total_score": 0.7},
        "spot_signal": {"action": "buy_window", "second_leg_risk": "low"},
        "sector_rotation": {"table": []},
        "asset_compare": [],
        "analogues": [],
        "warnings": [],
        "data_availability": [],
    }
    latest_md, latest_html, history_md, history_html, history_json = write_reports(
        report,
        reports_dir=WORK_DIR / "reports",
        sample_output_dir=WORK_DIR / "sample_output",
    )
    assert latest_md.exists()
    assert latest_html.exists()
    assert (latest_html.parent / "supplement_dashboard.html").exists()
    assert (WORK_DIR / "sample_output" / "supplement_dashboard_sample.html").exists()
    assert history_md.exists()
    assert history_html.exists()
    assert history_json.parent.name == "history"
    assert history_md.name == "report_2026-03-19_212030.md"
