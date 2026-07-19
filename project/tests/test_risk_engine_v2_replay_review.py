from __future__ import annotations

from project.risk_engine_v2_replay_review import build_risk_engine_v2_replay_review, render_risk_engine_v2_replay_review_markdown


def _case(
    date: str,
    candidate: str,
    confirmed: str,
    r4: float | None,
    r13: float | None,
    dd4: float | None,
    dd13: float | None,
    status: str = "ok",
    drawdown_path_13w: list[dict] | None = None,
) -> dict:
    return {
        "date": date,
        "domain_candidate_stage": candidate,
        "domain_confirmed_stage": confirmed,
        "legacy_stage": "normal",
        "oil_status": "normal",
        "outcome": {
            "status": status,
            "forward_returns": {"4w": r4, "13w": r13},
            "max_drawdowns": {"4w": dd4, "13w": dd13},
            "drawdown_paths": {"13w": drawdown_path_13w or []},
        },
    }


def test_replay_review_classifies_mutually_exclusive_episodes():
    payload = {
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "cases": [
            _case("2026-01-01", "warning", "warning", 0.02, 0.08, -0.02, -0.03),
            _case("2026-05-01", "danger", "danger", -0.03, -0.06, -0.09, -0.12),
            _case("2026-09-01", "normal", "normal", -0.04, -0.07, -0.09, -0.09),
            _case("2027-01-01", "warning", "normal", -0.01, -0.07, -0.08, -0.08),
            _case("2027-05-01", "warning", "warning", -0.001, -0.001, -0.01, -0.02),
            _case("2027-09-01", "warning", "warning", 0.01, None, -0.01, None),
        ],
    }

    review = build_risk_engine_v2_replay_review(payload)
    markdown = render_risk_engine_v2_replay_review_markdown(review)

    assert review["status"] == "ok"
    assert review["review_level"] == "event"
    assert review["affects_final_action"] is False
    assert review["promotion_gate"]["promotion_allowed"] is False
    assert review["legacy_episode_review"]["counts"] == {
        "protective": 1,
        "over_warning": 1,
        "ambiguous": 1,
        "missed_risk": 1,
        "late_confirmation": 1,
        "insufficient_outcome": 1,
    }
    assert sum(review["counts"].values()) == review["episode_count"]
    assert review["legacy_episode_review"]["case_evidence"][-1]["classification"] == "insufficient_outcome"
    assert review["old_episode_count"] == 6
    assert review["unmapped_old_episode_count"] == 2
    assert review["diagnostic_segment_counts"]["candidate_only"] == 1
    assert "review_level: event" in markdown
    assert "## Promotion Gate" in markdown
    assert "promotion_allowed: False" in markdown


def test_missing_13w_outcome_never_becomes_over_warning():
    payload = {
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "cases": [
            _case("2026-01-01", "warning", "warning", 0.03, None, -0.01, None),
        ],
    }

    review = build_risk_engine_v2_replay_review(payload)

    assert review["legacy_episode_review"]["counts"]["insufficient_outcome"] == 1
    assert review["legacy_episode_review"]["counts"]["over_warning"] == 0


def test_repeated_dates_in_one_outcome_window_count_as_one_episode():
    payload = {
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "cases": [
            _case("2026-01-01", "warning", "warning", 0.02, 0.08, -0.02, -0.03),
            _case("2026-01-15", "danger", "danger", 0.01, 0.04, -0.02, -0.04),
        ],
    }

    review = build_risk_engine_v2_replay_review(payload)

    legacy = review["legacy_episode_review"]
    assert legacy["counts"]["over_warning"] == 1
    assert legacy["episode_count"] == 1
    assert legacy["episodes"][0]["case_count"] == 2
    assert legacy["episodes"][0]["case_dates"] == ["2026-01-01", "2026-01-15"]
    assert legacy["episodes"][0]["signal_end_date"] == "2026-01-15"
    assert legacy["episodes"][0]["outcome_due_date"] == "2026-04-16"


def test_small_negative_return_alone_is_ambiguous_not_protective():
    payload = {
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "cases": [
            _case("2026-01-01", "warning", "warning", -0.001, -0.001, -0.01, -0.02),
        ],
    }

    review = build_risk_engine_v2_replay_review(payload)

    assert review["legacy_episode_review"]["counts"]["ambiguous"] == 1
    assert review["legacy_episode_review"]["counts"]["protective"] == 0


def test_newest_episode_without_complete_horizon_is_pending_not_mature():
    payload = {
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "reconstruction": {"end_date": "2026-02-01"},
        "cases": [
            _case("2026-01-15", "warning", "warning", 0.01, None, -0.01, None, status="insufficient_forward_prices"),
        ],
    }

    review = build_risk_engine_v2_replay_review(payload)
    episode = review["legacy_episode_review"]["episodes"][0]

    assert episode["outcome_maturity_status"] == "pending"
    assert episode["performance_evaluable"] is False
    assert episode["outcome_due_date"] == "2026-04-16"
    assert episode["outcome_observed_through"] == "2026-02-01"
    assert review["legacy_episode_review"]["episode_maturity"]["pending_episode_count"] == 1
    assert review["legacy_episode_review"]["episode_maturity"]["performance_denominator"] == 0


def test_missing_benchmark_after_due_date_is_not_pending_success():
    payload = {
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "reconstruction": {"end_date": "2026-06-01"},
        "cases": [
            _case("2026-01-15", "warning", "warning", 0.01, None, -0.01, None, status="insufficient_forward_prices"),
        ],
    }

    review = build_risk_engine_v2_replay_review(payload)

    assert review["legacy_episode_review"]["episodes"][0]["outcome_maturity_status"] == "missing_benchmark_data"
    assert review["legacy_episode_review"]["episode_maturity"]["missing_benchmark_data_episode_count"] == 1


def test_episode_metrics_use_crossing_dates_not_episode_duration():
    payload = {
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "reconstruction": {"end_date": "2026-06-01"},
        "cases": [
            _case(
                "2026-01-01",
                "warning",
                "warning",
                -0.02,
                -0.06,
                -0.04,
                -0.1,
                drawdown_path_13w=[
                    {"date": "2026-01-01", "price": 100.0, "drawdown_from_anchor": 0.0},
                    {"date": "2026-01-15", "price": 91.0, "drawdown_from_anchor": -0.09},
                    {"date": "2026-04-02", "price": 90.0, "drawdown_from_anchor": -0.1},
                ],
            ),
        ],
    }

    review = build_risk_engine_v2_replay_review(payload)
    episode = review["legacy_episode_review"]["episodes"][0]

    assert episode["first_material_drawdown_crossing_date"] == "2026-01-15"
    assert episode["candidate_lead_time_days"] == 14
    assert episode["confirmed_lead_time_days"] == 14
    assert episode["confirmation_delay_calendar_days"] == 0
    assert episode["confirmation_delay_calendar_days"] != 91


def test_quiet_outcome_requires_explicit_benign_mature_outcome():
    quiet_payload = {
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "reconstruction": {"end_date": "2026-06-01"},
        "cases": [_case("2026-01-01", "warning", "warning", 0.01, 0.02, -0.01, -0.02)],
    }
    adverse_payload = {
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "reconstruction": {"end_date": "2026-06-01"},
        "cases": [_case("2026-01-01", "warning", "warning", -0.01, -0.06, -0.01, -0.09)],
    }

    quiet_review = build_risk_engine_v2_replay_review(quiet_payload)
    adverse_review = build_risk_engine_v2_replay_review(adverse_payload)

    assert quiet_review["legacy_episode_review"]["episodes"][0]["quiet_outcome"] is True
    assert adverse_review["legacy_episode_review"]["episodes"][0]["quiet_outcome"] is False
