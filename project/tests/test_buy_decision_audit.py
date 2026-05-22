from __future__ import annotations

import json
from pathlib import Path

from project.buy_decision_audit import build_buy_decision_audit, run_buy_decision_audit


def _report() -> dict:
    return {
        "generated_at": "2026-05-22T07:30:00",
        "spot_signal": {
            "action": "watch",
            "action_layers": {"market_raw_action": "buy_window", "risk_adjusted_action": "watch", "final_action": "watch"},
            "recovery_evidence": {"grade": "confirmed"},
            "blocker_assessment": {"level": "caution", "flags": ["foreign_asset_fx_headwind"]},
        },
        "japan_risk": {"flags": ["foreign_asset_fx_headwind"]},
        "risk_lines": {"stage_key": "normal"},
        "data_reliability": {"level": "high", "decision_allowed": True},
        "score": {"total_score": 0.7},
    }


def test_buy_decision_audit_builds_payload() -> None:
    payload = build_buy_decision_audit(_report())

    assert payload["status"] == "ok"
    assert payload["affects_final_action"] is False
    assert payload["buy_decision_card"]["primary_blocker"] == "fx_risk"
    assert payload["why_not_buy_window"]


def test_buy_decision_audit_writes_reports(tmp_path: Path) -> None:
    report_path = tmp_path / "report_summary.json"
    report_path.write_text(json.dumps(_report()), encoding="utf-8")

    result = run_buy_decision_audit(report_path, tmp_path)

    assert result["status"] == "ok"
    assert (tmp_path / "buy_decision_audit.json").exists()
    assert (tmp_path / "buy_decision_audit.md").exists()
