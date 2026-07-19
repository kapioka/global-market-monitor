from __future__ import annotations

from project.risk_engine_v2_retention_reconciliation import build_retention_reconciliation


def _case(date: str) -> dict:
    return {
        "date": date,
        "domain_candidate_stage": "normal",
        "domain_confirmed_stage": "normal",
        "domain_evidence": [{"domain_id": "equity"}],
    }


def _weekly(date: str) -> dict:
    return {
        "record_id": f"week:{date}",
        "date": date,
        "candidate_stage": "normal",
        "confirmed_stage": "normal",
        "provenance_present": True,
        "freshness_present": True,
        "quality_flags": [],
        "primary_coverage_status": "primary_strict",
    }


def test_retention_reconciliation_passes_zero_loss_fixture() -> None:
    payload = build_retention_reconciliation(
        {"replay_type": "risk_engine_v2_reconstructed_shadow", "cases": [_case("2026-01-01")]},
        {
            "weekly_timeline": [_weekly("2026-01-01")],
            "events": [{"event_id": "event-1", "weekly_timeline_record_ids": ["week:2026-01-01"]}],
        },
    )

    assert payload["status"] == "pass"
    assert all(value == 0 for value in payload["loss_counts"].values())


def test_retention_reconciliation_fails_deliberate_weekly_loss() -> None:
    payload = build_retention_reconciliation(
        {"replay_type": "risk_engine_v2_reconstructed_shadow", "cases": [_case("2026-01-01")]},
        {"weekly_timeline": [], "events": []},
    )

    assert payload["status"] == "fail"
    assert payload["loss_counts"]["weekly_date_loss"] == 1
