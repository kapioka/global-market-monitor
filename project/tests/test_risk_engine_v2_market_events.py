from __future__ import annotations

from project.risk_engine_v2_market_events import build_market_event_review


def _case(date: str, price: float, candidate: str = "normal", confirmed: str = "normal", dd13: float | None = None) -> dict:
    return {
        "date": date,
        "generated_at": f"{date}T07:30:00",
        "domain_candidate_stage": candidate,
        "domain_confirmed_stage": confirmed,
        "domain_persistence_episode_id": "global:0",
        "domain_persistence_entry_rule": "test",
        "domain_persistence_gap_reset": False,
        "primary_coverage": {"coverage_status": "primary_strict", "primary_strict_available": True},
        "domain_evidence": [{"domain_id": "equity", "quality_flags": ["valid"]}],
        "global_policy_evidence": {"resulting_confirmed_stage": confirmed},
        "quality_flags": ["valid"],
        "outcome": {
            "status": "ok",
            "current_price_date": date,
            "current_price": price,
            "forward_returns": {"13w": -0.01},
            "max_drawdowns": {"4w": dd13 if dd13 is not None else -0.01, "13w": dd13 if dd13 is not None else -0.01},
        },
    }


def test_material_drawdown_event_is_built_before_classification_changes() -> None:
    replay = {
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "cases": [
            _case("2026-01-01", 100.0, "warning", "warning"),
            _case("2026-01-08", 96.0, "normal", "normal"),
            _case("2026-01-15", 91.0, "normal", "normal", -0.09),
            _case("2026-01-22", 89.0, "warning", "normal", -0.11),
            _case("2026-01-29", 94.0, "warning", "warning", -0.11),
            _case("2026-05-01", 101.0, "normal", "normal"),
        ],
    }
    old_review = {
        "episodes": [
            {"episode_id": "episode-0001", "classification": "protective", "case_dates": ["2026-01-01"]},
            {"episode_id": "episode-0002", "classification": "missed_risk", "case_dates": ["2026-01-15"]},
            {"episode_id": "episode-0003", "classification": "late_confirmation", "case_dates": ["2026-01-22"]},
            {"episode_id": "episode-0004", "classification": "protective", "case_dates": ["2026-01-29"]},
        ]
    }

    review = build_market_event_review(replay, old_review)
    material = [event for event in review["events"] if event["event_type"] == "material_drawdown"]

    assert len(material) == 1
    assert material[0]["first_material_crossing_date"] == "2026-01-15"
    assert material[0]["primary_classification"] == "late_confirmation"
    assert "stale_warning_reset_before_crossing" in material[0]["secondary_attributes"]
    assert review["integrity"]["duplicate_material_crossing_count"] == 0
    assert review["unmapped_old_episode_count"] == 0
    assert {row["new_event_id"] for row in review["old_episode_event_mapping"]} == {material[0]["event_id"]}


def test_recovered_drawdown_can_create_second_material_event() -> None:
    replay = {
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "cases": [
            _case("2026-01-01", 100.0),
            _case("2026-01-08", 91.0, dd13=-0.09),
            _case("2026-05-01", 101.0),
            _case("2026-06-01", 92.0, dd13=-0.09),
            _case("2026-10-01", 102.0),
        ],
    }

    review = build_market_event_review(replay)

    assert [event["event_type"] for event in review["events"]] == ["material_drawdown", "material_drawdown"]
    assert review["integrity"]["duplicate_material_crossing_count"] == 0


def test_alert_only_event_does_not_duplicate_material_event_owned_signal() -> None:
    replay = {
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "cases": [
            _case("2026-01-01", 100.0, "warning", "warning"),
            _case("2026-01-08", 91.0, "warning", "warning", -0.09),
            _case("2026-05-01", 101.0, "normal", "normal"),
            _case("2026-06-01", 102.0, "warning", "warning"),
            _case("2026-10-01", 103.0, "normal", "normal"),
        ],
    }

    review = build_market_event_review(replay)

    assert [event["event_type"] for event in review["events"]] == ["material_drawdown", "alert_only"]
    assert review["integrity"]["duplicate_weekly_owner_count"] == 0


def test_event_review_preserves_weekly_timeline_records() -> None:
    replay = {"replay_type": "risk_engine_v2_reconstructed_shadow", "cases": [_case("2026-01-01", 100.0), _case("2026-01-08", 101.0)]}

    review = build_market_event_review(replay)

    assert review["weekly_timeline_count"] == 2
    assert review["weekly_timeline"][0]["record_id"] == "week:2026-01-01"
    assert review["integrity"]["unowned_weekly_record_count"] == 2


def test_unrecovered_material_event_owns_later_signals_through_latest_observation() -> None:
    replay = {
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "cases": [
            _case("2026-04-03", 100.0),
            _case("2026-04-17", 91.0, dd13=-0.09),
            _case("2026-05-15", 88.0, "warning", "warning", dd13=-0.12),
            _case("2026-06-12", 89.0, "danger", "danger", dd13=-0.12),
        ],
        "reconstruction": {"end_date": "2026-06-12"},
    }

    review = build_market_event_review(replay)
    material = [event for event in review["events"] if event["event_type"] == "material_drawdown"]

    assert len(material) == 1
    assert material[0]["maximum_drawdown_date"] == "2026-05-15"
    assert material[0]["event_end_date"] == "2026-06-12"
    assert material[0]["recovery_status"] == "unrecovered"
    assert review["integrity"]["alert_only_inside_unrecovered_drawdown_count"] == 0
    assert not [event for event in review["events"] if event["event_type"] == "alert_only"]


def test_candidate_only_segment_is_diagnostic_not_alert_event() -> None:
    replay = {
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "cases": [
            _case("2026-01-01", 100.0, "warning", "normal"),
            _case("2026-01-08", 101.0, "danger", "normal"),
            _case("2026-01-15", 102.0, "normal", "normal"),
        ],
    }

    review = build_market_event_review(replay)

    assert review["events"] == []
    assert review["diagnostic_segment_counts"]["candidate_only"] == 1
    assert review["diagnostic_segments"][0]["performance_evaluable"] is False
