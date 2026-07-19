from __future__ import annotations

import json
from pathlib import Path

from project.pipeline import load_risk_engine_v2_holdout_validation_summary
from project.report_generator import render_developer_diagnostics_markdown
from project.risk_engine_v2_holdout_validation import (
    HoldoutSplitCriteria,
    build_risk_engine_v2_holdout_validation,
    render_risk_engine_v2_holdout_validation_markdown,
    run_risk_engine_v2_holdout_validation,
)


def _episode(index: int, classification: str = "ambiguous") -> dict:
    return {
        "episode_id": f"episode-{index:04d}",
        "classification": classification,
        "start_date": f"2026-{index:02d}-01",
        "end_date": f"2026-{index:02d}-28",
        "case_count": 2,
    }


def _pending_episode(index: int, classification: str = "insufficient_outcome") -> dict:
    episode = _episode(index, classification)
    episode.update(
        {
            "outcome_due_date": "2027-12-31",
            "outcome_observed_through": "2027-10-01",
            "outcome_maturity_status": "pending",
            "performance_evaluable": False,
            "pending_reason": "outcome horizon has not completed",
        }
    )
    return episode


def _replay(strict_primary_available: bool = True) -> dict:
    return {
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "summary": {
            "total_cases": 120,
            "strict_primary_available": strict_primary_available,
            "primary_strict_available_cases": 100 if strict_primary_available else 0,
            "persistence_gap_reset_rate": 0.0,
        },
        "reconstruction": {
            "cadence": {
                "engine_evaluation_cadence": "canonical_weekly",
                "persistence_expected_cadence": "canonical_weekly",
                "case_sampling_stride": 4,
                "episode_merge_gap": "outcome_horizon_window",
                "outcome_horizons": ["4w", "13w", "26w"],
                "stride_semantics": "case_sampling_only_not_persistence_update",
            }
        },
        "cases": [],
    }


def _review() -> dict:
    episodes = [_episode(index, "protective" if index % 3 == 0 else "ambiguous") for index in range(1, 11)]
    return {
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "source_replay_type": "risk_engine_v2_reconstructed_shadow",
        "case_count": 120,
        "episode_count": len(episodes),
        "counts": {"insufficient_outcome": 0},
        "episodes": episodes,
    }


def test_holdout_validation_splits_chronologically_and_keeps_shadow_contract() -> None:
    payload = build_risk_engine_v2_holdout_validation(
        _replay(strict_primary_available=True),
        _review(),
        criteria=HoldoutSplitCriteria(minimum_holdout_episodes=2),
    )
    markdown = render_risk_engine_v2_holdout_validation_markdown(payload)

    assert payload["policy_status"] == "diagnostic_only_not_promoted"
    assert payload["affects_final_action"] is False
    assert payload["holdout"]["status"] == "blocked_strict_primary_unavailable"
    assert payload["holdout"]["split_status"] == "ready"
    assert payload["holdout"]["evidence_status"] == "blocked_strict_primary_unavailable"
    assert payload["holdout"]["performance_status"] == "accepted"
    assert payload["splits"]["train"]["episode_count"] == 0
    assert payload["splits"]["validation"]["episode_count"] == 0
    assert payload["splits"]["holdout"]["episode_count"] == 10
    assert payload["split_policy"]["validation_start_date"] == "2024-03-15"
    assert payload["split_policy"]["holdout_start_date"] == "2025-05-23"
    assert "episode count below minimum: 10/30" in payload["promotion_gate"]["blockers"]
    assert "holdout validation is not accepted: blocked_strict_primary_unavailable" in payload["promotion_gate"]["blockers"]
    assert "holdout_status: blocked_strict_primary_unavailable" in markdown
    assert "performance_status: accepted" in markdown


def test_holdout_validation_blocks_when_strict_primary_replay_is_unavailable() -> None:
    payload = build_risk_engine_v2_holdout_validation(
        _replay(strict_primary_available=False),
        _review(),
        criteria=HoldoutSplitCriteria(minimum_holdout_episodes=2),
    )

    assert payload["holdout"]["status"] == "blocked_strict_primary_unavailable"
    assert payload["holdout"]["evidence_status"] == "blocked_strict_primary_unavailable"
    assert "holdout validation is not accepted: blocked_strict_primary_unavailable" in payload["promotion_gate"]["blockers"]
    assert payload["promotion_gate"]["promotion_allowed"] is False


def test_holdout_validation_rejects_performance_when_missed_risk_is_present() -> None:
    review = _review()
    review["episodes"][8]["classification"] = "missed_risk"

    payload = build_risk_engine_v2_holdout_validation(
        _replay(strict_primary_available=True),
        review,
        criteria=HoldoutSplitCriteria(minimum_holdout_episodes=2),
    )

    assert payload["holdout"]["split_status"] == "ready"
    assert payload["holdout"]["evidence_status"] == "blocked_strict_primary_unavailable"
    assert payload["holdout"]["performance_status"] == "rejected"
    assert payload["holdout"]["status"] == "blocked_strict_primary_unavailable"
    assert "severe missed-risk rate exceeds frozen criterion" in payload["holdout"]["performance"]["blockers"]


def test_pending_holdout_episode_is_excluded_from_performance_denominator() -> None:
    review = _review()
    review["episodes"][8] = _pending_episode(9)
    review["episodes"][9] = _pending_episode(10)

    payload = build_risk_engine_v2_holdout_validation(
        _replay(strict_primary_available=True),
        review,
        criteria=HoldoutSplitCriteria(minimum_holdout_episodes=2),
    )

    assert payload["holdout"]["maturity"]["pending_episode_count"] == 2
    assert payload["holdout"]["performance_denominator"] == 8
    assert payload["holdout"]["performance_status"] == "accepted"
    assert payload["holdout"]["status"] == "blocked_strict_primary_unavailable"
    assert "severe missed-risk rate exceeds frozen criterion" not in payload["holdout"]["performance"]["blockers"]


def test_missing_benchmark_holdout_episode_blocks_invalid_evidence() -> None:
    review = _review()
    review["episodes"][8].update(
        {
            "outcome_maturity_status": "missing_benchmark_data",
            "performance_evaluable": False,
        }
    )

    payload = build_risk_engine_v2_holdout_validation(
        _replay(strict_primary_available=True),
        review,
        criteria=HoldoutSplitCriteria(minimum_holdout_episodes=1),
    )

    assert payload["holdout"]["performance_status"] == "blocked_invalid_evidence"
    assert payload["holdout"]["status"] == "blocked_strict_primary_unavailable"
    assert "invalid or missing benchmark evidence episodes present in holdout" in payload["holdout"]["performance"]["blockers"]


def test_holdout_metrics_use_corrected_episode_fields_and_deduped_timeline() -> None:
    review = _review()
    review["episodes"][8].update(
        {
            "classification": "protective",
            "outcome_maturity_status": "mature",
            "performance_evaluable": True,
            "confirmation_status": "confirmed",
            "confirmation_delay_calendar_days": 7,
            "confirmation_delay_observations": 1,
            "first_material_drawdown_crossing_date": "2026-09-15",
            "candidate_lead_time_days": 14,
            "confirmed_lead_time_days": 7,
            "confirmed_lead_time_status": "calculated",
            "quiet_outcome": False,
            "cases": [
                {"date": "2026-09-01", "confirmed_stage": "warning", "max_drawdown_13w": -0.1},
                {"date": "2026-09-01", "confirmed_stage": "warning", "max_drawdown_13w": -0.1},
                {"date": "2026-09-08", "confirmed_stage": "danger", "max_drawdown_13w": -0.12},
            ],
        }
    )
    review["episodes"][9].update(
        {
            "classification": "over_warning",
            "outcome_maturity_status": "mature",
            "performance_evaluable": True,
            "confirmation_status": "confirmed",
            "confirmation_delay_calendar_days": 0,
            "confirmation_delay_observations": 0,
            "quiet_outcome": True,
            "confirmed_stages": ["danger"],
            "cases": [{"date": "2026-10-01", "confirmed_stage": "danger", "max_drawdown_13w": -0.01}],
        }
    )

    payload = build_risk_engine_v2_holdout_validation(
        _replay(strict_primary_available=True),
        review,
        criteria=HoldoutSplitCriteria(minimum_holdout_episodes=2),
    )
    metrics = payload["holdout"]["performance"]["metrics"]

    assert metrics["confirmation_delay"]["median_days"] == 3.5
    assert metrics["lead_time"]["confirmed_lead_time_median_days"] == 7.0
    assert metrics["warning_danger_time_in_state"]["unique_weekly_observations"] == 3
    assert metrics["quiet_period_alert_burden"]["mature_quiet_episode_count"] == 1
    assert metrics["quiet_period_alert_burden"]["quiet_danger_or_higher_episode_count"] == 1


def test_holdout_validation_purges_previous_split_overlap() -> None:
    review = _review()
    review["episodes"][7]["end_date"] = "2026-09-15"

    payload = build_risk_engine_v2_holdout_validation(
        _replay(strict_primary_available=True),
        review,
        criteria=HoldoutSplitCriteria(minimum_holdout_episodes=2),
    )

    assert payload["split_policy"]["type"] == "fixed_calendar_date_purged_event_time_split"
    assert payload["splits"]["holdout"]["episode_count"] == 10


def test_holdout_validation_writes_and_loads_developer_summary(tmp_path: Path) -> None:
    replay_path = tmp_path / "risk_engine_v2_reconstructed_replay.json"
    review_path = tmp_path / "risk_engine_v2_replay_review.json"
    reports_dir = tmp_path / "reports"
    replay_path.write_text(json.dumps(_replay(strict_primary_available=True)), encoding="utf-8")
    review_path.write_text(json.dumps(_review()), encoding="utf-8")

    result = run_risk_engine_v2_holdout_validation(replay_path, review_path, reports_dir)
    summary = load_risk_engine_v2_holdout_validation_summary(reports_dir)
    markdown = render_developer_diagnostics_markdown(
        {
            "title": "Test",
            "generated_at": "2026-01-01T07:30:00",
            "risk_engine_v2_holdout_validation": summary,
        }
    )

    assert result["status"] == "ok"
    assert summary["holdout_status"] == "blocked_strict_primary_unavailable"
    assert summary["affects_final_action"] is False
    assert "risk_engine_v2 holdout validation" in markdown
    assert "holdout_status: blocked_strict_primary_unavailable" in markdown
