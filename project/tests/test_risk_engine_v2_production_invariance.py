from __future__ import annotations

from copy import deepcopy

from project.risk_engine_v2_production_invariance import build_production_invariance_report


def _replay(stage: str = "normal") -> dict:
    return {
        "replay_type": "risk_engine_v2_reconstructed_shadow",
        "reconstruction": {"market_snapshot": {"sha256": "same-snapshot-sha256"}},
        "cases": [
            {
                "date": "2026-01-01",
                "domain_candidate_stage": stage,
                "domain_confirmed_stage": stage,
                "domain_persistence_episode_id": "global:0",
                "domain_persistence_entry_rule": "entry",
                "domain_persistence_gap_reset": False,
                "buy_decision_card": {"final_action": "hold"},
            }
        ],
    }


def test_production_invariance_passes_for_identical_weekly_fields() -> None:
    payload = build_production_invariance_report(_replay(), _replay())

    assert payload["status"] == "pass"
    assert payload["compared_weekly_count"] == 1
    assert sum(payload["mismatched_count_per_field"].values()) == 0


def test_production_invariance_fails_on_stage_mismatch() -> None:
    baseline = _replay("normal")
    post = deepcopy(baseline)
    post["cases"][0]["domain_confirmed_stage"] = "warning"

    payload = build_production_invariance_report(baseline, post)

    assert payload["status"] == "fail"
    assert payload["mismatched_count_per_field"]["domain_confirmed_stage"] == 1


def test_production_invariance_accepts_append_only_new_weeks() -> None:
    baseline = _replay()
    post = deepcopy(baseline)
    post["cases"].append(
        {
            "date": "2026-01-08",
            "domain_candidate_stage": "warning",
            "domain_confirmed_stage": "normal",
            "domain_persistence_episode_id": "global:1",
            "domain_persistence_entry_rule": "awaiting_entry",
            "domain_persistence_gap_reset": False,
            "buy_decision_card": {"final_action": "hold"},
        }
    )

    payload = build_production_invariance_report(baseline, post)

    assert payload["status"] == "pass"
    assert payload["append_only_extension"] is True
    assert payload["appended_post_dates"] == ["2026-01-08"]
    assert payload["missing_baseline_dates"] == []


def test_production_invariance_rejects_removed_baseline_week() -> None:
    baseline = _replay()
    post = deepcopy(baseline)
    post["cases"] = []

    payload = build_production_invariance_report(baseline, post)

    assert payload["status"] == "fail"
    assert payload["missing_baseline_dates"] == ["2026-01-01"]


def test_production_invariance_rejects_inserted_historical_week() -> None:
    baseline = _replay()
    post = deepcopy(baseline)
    inserted = deepcopy(post["cases"][0])
    inserted["date"] = "2025-12-25"
    post["cases"].insert(0, inserted)

    payload = build_production_invariance_report(baseline, post)

    assert payload["status"] == "fail"
    assert payload["non_append_post_dates"] == ["2025-12-25"]


def test_production_invariance_rejects_different_market_snapshots() -> None:
    baseline = _replay()
    post = deepcopy(baseline)
    post["reconstruction"]["market_snapshot"]["sha256"] = "different-snapshot-sha256"

    payload = build_production_invariance_report(baseline, post)

    assert payload["status"] == "fail"
    assert payload["same_market_snapshot"] is False
    assert payload["market_snapshot_comparison"] == {
        "status": "mismatch",
        "baseline_sha256": "same-snapshot-sha256",
        "post_sha256": "different-snapshot-sha256",
    }
    assert sum(payload["mismatched_count_per_field"].values()) == 0


def test_production_invariance_rejects_missing_market_snapshot_provenance() -> None:
    baseline = _replay()
    post = deepcopy(baseline)
    del baseline["reconstruction"]["market_snapshot"]

    payload = build_production_invariance_report(baseline, post)

    assert payload["status"] == "fail"
    assert payload["market_snapshot_comparison"]["status"] == "missing_baseline"
