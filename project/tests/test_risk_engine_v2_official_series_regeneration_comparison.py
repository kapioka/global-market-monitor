from __future__ import annotations

from project.risk_engine_v2_official_series_regeneration_comparison import build_official_series_regeneration_comparison


def _contract(**payload: object) -> dict[str, object]:
    return {
        "status": "ok",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "decision": {"promotion_allowed": False},
        **payload,
    }


def test_official_series_regeneration_comparison_accepts_loaded_to_loaded_with_all_gates() -> None:
    before = {
        "status": "ok",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "decision": {"promotion_allowed": False},
        "reconstruction": {
            "official_series_store": {
                "loaded": True,
                "exists": True,
                "requested_path": "project/reports/risk_engine_v2_official_series_before.csv",
                "resolved_path": "project/reports/risk_engine_v2_official_series_before.csv",
                "sha256": "before-sha",
                "row_count": 9,
            }
        },
        "summary": {"total_cases": 2, "timeline_case_count": 2},
        "cases": [{"date": "2024-01-05"}, {"date": "2024-01-12"}],
    }
    after = {
        "status": "ok",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "decision": {"promotion_allowed": False},
        "reconstruction": {
            "official_series_store": {
                "loaded": True,
                "exists": True,
                "requested_path": "project/reports/risk_engine_v2_official_series.csv",
                "resolved_path": "project/reports/risk_engine_v2_official_series.csv",
                "sha256": "abc",
                "row_count": 10,
            }
        },
        "summary": {"total_cases": 2, "timeline_case_count": 2, "primary_strict_available_cases": 1},
        "cases": [{"date": "2024-01-05"}, {"date": "2024-01-12"}],
    }

    payload = build_official_series_regeneration_comparison(
        before,
        after,
        after_review=_contract(weekly_timeline=[{"date": "2024-01-05"}, {"date": "2024-01-12"}]),
        after_holdout=_contract(holdout_weekly_case_count=1),
        after_audit=_contract(
            holdout_weekly_case_count=1,
            replay_vs_holdout_reconciliation={
                "coverage_state_mismatch_count": 0,
                "coverage_field_loss_count": 0,
                "subset_recomputation_mismatch_count": 0,
            },
        ),
        production_invariance={
            "overall": "pass",
            "same_market_snapshot": True,
            "market_snapshot_comparison": {"status": "match"},
            "compared_weekly_count": 2,
        },
    )

    assert payload["status"] == "pass"
    assert payload["source_change"]["changed"] is True
    assert payload["decision"]["promotion_allowed"] is False
    assert payload["cross_artifact_reconciliation"]["review_matches_replay"] is True
    assert payload["cross_artifact_reconciliation"]["audit_matches_holdout"] is True
    assert payload["cross_artifact_reconciliation"]["status"] == "pass"
    assert payload["production_invariance"]["same_market_snapshot"] is True


def test_official_series_regeneration_comparison_rejects_unproven_same_snapshot() -> None:
    before = {"reconstruction": {"official_series_store": {"loaded": True, "exists": True}}}
    after = {"reconstruction": {"official_series_store": {"loaded": True, "exists": True}}}

    invariance_cases: list[dict[str, object] | None] = [
        {"overall": "pass"},
        {"overall": "pass", "same_market_snapshot": False},
        None,
    ]
    for invariance in invariance_cases:
        payload = build_official_series_regeneration_comparison(
            before,
            after,
            production_invariance=invariance,
        )

        assert payload["status"] == "review_required"


def test_official_series_regeneration_comparison_requires_cross_artifact_reconciliation() -> None:
    replay = _contract(
        reconstruction={"official_series_store": {"loaded": True, "exists": True}},
        cases=[{"date": "2024-01-05"}],
    )
    invariance = {"overall": "pass", "same_market_snapshot": True}

    missing_artifacts = build_official_series_regeneration_comparison(
        replay,
        replay,
        production_invariance=invariance,
    )
    mismatched_artifacts = build_official_series_regeneration_comparison(
        replay,
        replay,
        after_review=_contract(weekly_timeline=[]),
        after_holdout=_contract(holdout_weekly_case_count=1),
        after_audit=_contract(
            holdout_weekly_case_count=1,
            replay_vs_holdout_reconciliation={
                "coverage_state_mismatch_count": 1,
                "coverage_field_loss_count": 0,
                "subset_recomputation_mismatch_count": 0,
            },
        ),
        production_invariance=invariance,
    )

    assert missing_artifacts["status"] == "review_required"
    assert missing_artifacts["cross_artifact_reconciliation"]["status"] == "fail"
    assert mismatched_artifacts["status"] == "review_required"
    assert mismatched_artifacts["cross_artifact_reconciliation"]["status"] == "fail"


def test_official_series_regeneration_comparison_rejects_unsafe_artifact_contract() -> None:
    replay = _contract(
        reconstruction={"official_series_store": {"loaded": True, "exists": True}},
        cases=[{"date": "2024-01-05"}],
    )
    unsafe_review = _contract(weekly_timeline=[{"date": "2024-01-05"}])
    unsafe_review["affects_final_action"] = True

    payload = build_official_series_regeneration_comparison(
        replay,
        replay,
        after_review=unsafe_review,
        after_holdout=_contract(holdout_weekly_case_count=1),
        after_audit=_contract(
            holdout_weekly_case_count=1,
            replay_vs_holdout_reconciliation={
                "coverage_state_mismatch_count": 0,
                "coverage_field_loss_count": 0,
                "subset_recomputation_mismatch_count": 0,
            },
        ),
        production_invariance={"overall": "pass", "same_market_snapshot": True},
    )

    assert payload["status"] == "review_required"
    assert payload["cross_artifact_reconciliation"]["artifact_contracts_valid"] is False
