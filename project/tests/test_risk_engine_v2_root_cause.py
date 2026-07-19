from __future__ import annotations

from project.risk_engine_v2_root_cause import build_risk_engine_v2_root_cause_report, render_risk_engine_v2_root_cause_markdown


def _replay_case(date: str, candidate: str = "normal", confirmed: str = "normal") -> dict:
    return {
        "date": date,
        "domain_candidate_stage": candidate,
        "domain_confirmed_stage": confirmed,
        "primary_coverage": {
            "coverage_status": "primary_partial",
            "primary_strict_available": False,
            "missing_primary_groups": ["credit"],
            "primary_missing_series": ["FRED:BAMLH0A0HYM2"],
            "primary_stale_series": [],
            "primary_history_insufficient_series": [],
        },
        "global_policy_evidence": {
            "candidate_stage": candidate,
            "resulting_confirmed_stage": confirmed,
            "qualifying_stressed_domains": ["credit"] if candidate == "normal" else [],
        },
        "domain_evidence": [
            {
                "domain_id": "credit",
                "candidate_stage": "warning",
                "stage_eligibility": True,
                "primary_fallback_status": "fallback",
                "quality_flags": ["source_unavailable"],
                "contributed_to_global_candidate": candidate == "normal",
                "suppressed_contribution": candidate == "normal",
                "suppression_reason": "not counted by global policy",
            }
        ],
    }


def _episode(classification: str = "missed_risk") -> dict:
    return {
        "episode_id": "episode-0001",
        "classification": classification,
        "start_date": "2026-01-01",
        "end_date": "2026-01-01",
        "signal_start_date": "2026-01-01",
        "signal_end_date": "2026-01-01",
        "case_dates": ["2026-01-01"],
        "outcome_maturity_status": "mature",
        "first_material_drawdown_crossing_date": "2026-01-15",
        "first_candidate_stress_date": None,
        "first_confirmed_stress_date": None,
        "confirmation_status": "candidate_never_stressed",
        "confirmed_lead_time_days": None,
        "cases": [
            {
                "date": "2026-01-01",
                "material_adverse_outcome": True,
                "drawdown_path_13w": [{"date": "2026-01-15", "drawdown_from_anchor": -0.09}],
            }
        ],
    }


def test_root_cause_report_includes_all_missed_risk_episodes_and_evidence_codes() -> None:
    payload = build_risk_engine_v2_root_cause_report(
        {"replay_type": "risk_engine_v2_reconstructed_shadow", "cases": [_replay_case("2026-01-01")]},
        {"episodes": [_episode()]},
    )
    markdown = render_risk_engine_v2_root_cause_markdown(payload)

    assert payload["status"] == "ok"
    assert payload["policy_status"] == "diagnostic_only_not_promoted"
    assert payload["affects_final_action"] is False
    assert payload["target_episode_count"] == 1
    assert "data_unavailable" in payload["episodes"][0]["cause_codes"]
    assert "domain_feature_not_triggered" in payload["episodes"][0]["cause_codes"]
    assert "global_policy_suppressed" in payload["episodes"][0]["cause_codes"]
    assert payload["episodes"][0]["coverage_timeline"][0]["primary_missing_series"] == ["FRED:BAMLH0A0HYM2"]
    assert "episode-0001" in markdown


def test_root_cause_report_marks_candidate_unconfirmed_as_persistence_delay() -> None:
    episode = _episode("late_confirmation")
    episode["first_candidate_stress_date"] = "2026-01-01"
    episode["confirmation_status"] = "not_confirmed_within_horizon"

    payload = build_risk_engine_v2_root_cause_report(
        {"replay_type": "risk_engine_v2_reconstructed_shadow", "cases": [_replay_case("2026-01-01", candidate="warning")]},
        {"episodes": [episode]},
    )

    assert "persistence_delayed" in payload["episodes"][0]["cause_codes"]
    assert payload["episodes"][0]["remediation_category"] == "data_quality_or_primary_coverage_review"


def test_root_cause_report_never_emits_empty_cause_codes() -> None:
    payload = build_risk_engine_v2_root_cause_report(
        {"replay_type": "risk_engine_v2_reconstructed_shadow", "cases": []},
        {"episodes": [_episode("ambiguous")]},
    )

    assert payload["episodes"][0]["cause_codes"] == ["undetermined"]
