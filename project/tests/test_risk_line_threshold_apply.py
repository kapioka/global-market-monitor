from __future__ import annotations

from pathlib import Path
import shutil
import uuid

from project.risk_line_threshold_apply import apply_proposed_thresholds


TEST_TMP_ROOT = Path(__file__).resolve().parents[2] / ".tmp" / "pytest" / "manual" / "threshold_apply"


def test_apply_proposed_thresholds_writes_log(monkeypatch):
    base = TEST_TMP_ROOT / uuid.uuid4().hex
    reports_dir = base / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    active_path = base / "risk_line_thresholds_active.json"
    proposed_path = base / "risk_line_thresholds_proposed.json"
    active_path.write_text(
        """{
  "schema_version": 1,
  "threshold_set": {"version": "active-v1", "status": "active"},
  "indicators": {"SPY": {"weight": 1.0, "thresholds": {"warning": {"feature": "drawdown_13w", "threshold": -0.02, "direction": "lower"}}}}
}
""",
        encoding="utf-8",
    )
    proposed_path.write_text(
        """{
  "schema_version": 1,
  "threshold_set": {"version": "proposed-v1", "status": "proposed", "source_report": "test"},
  "indicators": {"SPY": {"weight": 1.0, "thresholds": {"warning": {"feature": "drawdown_13w", "threshold": -0.03, "direction": "lower", "decision": "fallback_review"}}}}
}
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("project.risk_line_threshold_apply.ACTIVE_THRESHOLDS_PATH", active_path)
    monkeypatch.setattr("project.risk_line_threshold_apply.PROPOSED_THRESHOLDS_PATH", proposed_path)
    monkeypatch.setattr("project.risk_line_threshold_store.ACTIVE_THRESHOLDS_PATH", active_path)
    monkeypatch.setattr("project.risk_line_threshold_store.PROPOSED_THRESHOLDS_PATH", proposed_path)

    try:
        result = apply_proposed_thresholds(reports_dir, tickers=["SPY"])
        assert "applied" in result
        assert result["reason"] in {"no_material_changes", "applied_selected_proposed_thresholds", "no_applicable_thresholds"}
        if result["applied"]:
            assert result["active_version_before"] != result["active_version_after"]
        else:
            assert result["active_version_before"] == result["active_version_after"]
        assert (Path(reports_dir) / "risk_line_threshold_apply_log.json").exists()
    finally:
        shutil.rmtree(base, ignore_errors=True)
