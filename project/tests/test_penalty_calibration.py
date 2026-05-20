from __future__ import annotations

import json
from pathlib import Path
import shutil
import uuid

from project.penalty_calibration import build_penalty_calibration_report, render_penalty_calibration_markdown


TEST_TMP_ROOT = Path(__file__).resolve().parents[2] / ".tmp" / "pytest" / "manual" / "penalty_calibration"


def make_test_dir(name: str) -> Path:
    path = TEST_TMP_ROOT / f"{name}_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_build_penalty_calibration_report_summarizes_history():
    tmp_path = make_test_dir("penalty_calibration")
    reports_dir = tmp_path / "project" / "reports" / "history"
    reports_dir.mkdir(parents=True, exist_ok=True)
    config_path = tmp_path / "project" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        """
schema_version: 1
app:
  report_title: Test
paths:
  reports_dir: project/reports
data:
  period_years: 10
tickers:
  global_equities:
    ACWI: ACWI
    SPY: SPY
  credit:
    HYG: HYG
    LQD: LQD
  risk_indicators:
    VIX: ^VIX
  japan:
    usd_jpy: USDJPY=X
thresholds:
  spot_score_buy: 0.65
  spot_score_watch: 0.45
  penalty_transition: 0.03
  penalty_risk_off: 0.08
  penalty_risk_off_relief: 0.02
  penalty_risk_off_relief_score_min: 0.48
  penalty_credit_stress_moderate: 0.14
  penalty_credit_stress_severe: 0.18
  penalty_credit_stress: 0.18
  penalty_inflation_shock_oil_only: 0.06
  penalty_inflation_shock_broad: 0.12
  penalty_inflation_shock: 0.12
  penalty_stagflation_warning: 0.2
weights:
  trend: 1.0
""".strip(),
        encoding="utf-8",
    )
    sample = {
        "generated_at": "2026-03-20T07:00:00",
        "regime": {"regime_label": "risk_off"},
        "score": {"total_score": 0.49},
    }
    (reports_dir / "report_2026-03-20_070000.json").write_text(json.dumps(sample), encoding="utf-8")

    try:
        report = build_penalty_calibration_report(config_path)

        assert report["history_count"] == 1
        assert report["deduped_history_count"] == 1
        assert report["datasets"]["all_history"]["scenarios"]["current"]["action_counts"]["watch"] == 1
        assert report["datasets"]["all_history"]["scenarios"]["current"]["average_penalty"] == 0.02
        assert len(report["datasets"]["all_history"]["scenarios"]["current"]["risk_off_relief_cases"]) == 1
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_render_penalty_calibration_markdown_contains_scenarios():
    report = {
        "history_count": 2,
        "deduped_history_count": 1,
        "baseline_thresholds": {"spot_score_buy": 0.65},
        "datasets": {
            "all_history": {
                "count": 2,
                "scenarios": {
                    "current": {
                        "action_counts": {"buy_window": 1, "watch": 1, "wait": 0},
                        "regime_counts": {"risk_on": 1, "inflation_shock": 1},
                        "average_total_score": 0.6,
                        "average_adjusted_score": 0.54,
                        "average_penalty": 0.06,
                        "risk_off_relief_cases": [
                            {"generated_at": "2026-03-20T07:00:00", "total_score": 0.49, "penalty": 0.02, "adjusted_score": 0.47, "action": "watch"}
                        ],
                    }
                },
            },
            "daily_latest": {
                "count": 1,
                "scenarios": {
                    "current": {
                        "action_counts": {"buy_window": 1, "watch": 0, "wait": 0},
                        "regime_counts": {"risk_on": 1},
                        "average_total_score": 0.6,
                        "average_adjusted_score": 0.6,
                        "average_penalty": 0.0,
                        "risk_off_relief_cases": [],
                    }
                },
            },
        },
    }
    text = render_penalty_calibration_markdown(report)
    assert "Penalty Calibration" in text
    assert "## all_history" in text
    assert "### current" in text
    assert "buy_window: 1" in text
    assert "risk_off 救済ケース" in text
