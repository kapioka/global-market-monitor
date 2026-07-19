from __future__ import annotations

import json

from project.risk_domain_state import apply_risk_domain_persistence, load_risk_domain_state, write_risk_domain_state


def _payload(stage: str, *, eligible: bool = True) -> dict:
    return {
        "schema_version": "2.0",
        "stage": stage,
        "candidate_stage": stage,
        "confirmed_stage": stage,
        "domains": [
            {
                "domain_id": "credit",
                "stage": stage,
                "candidate_stage": stage,
                "confirmed_stage": stage,
                "stage_eligible": eligible,
            }
        ],
    }


def test_warning_requires_two_observations_before_confirmation():
    first, first_state = apply_risk_domain_persistence(_payload("warning"), generated_at="2026-01-01T07:30:00")
    second, _ = apply_risk_domain_persistence(
        _payload("warning"),
        previous_state=first_state,
        generated_at="2026-01-02T07:30:00",
    )

    assert first["candidate_stage"] == "warning"
    assert first["confirmed_stage"] == "normal"
    assert first["domains"][0]["entry_rule"] == "awaiting_2_of_3_warning_or_higher"
    assert second["confirmed_stage"] == "warning"
    assert second["domains"][0]["entry_rule"] == "2_of_3_warning_or_higher"


def test_danger_requires_consecutive_observations_and_exit_requires_confirmation():
    warning, warning_state = apply_risk_domain_persistence(_payload("warning"), generated_at="2026-01-01T07:30:00")
    warning2, warning2_state = apply_risk_domain_persistence(
        _payload("warning"),
        previous_state=warning_state,
        generated_at="2026-01-02T07:30:00",
    )
    first_danger, danger_state = apply_risk_domain_persistence(
        _payload("danger"),
        previous_state=warning2_state,
        generated_at="2026-01-03T07:30:00",
    )
    confirmed_danger, confirmed_danger_state = apply_risk_domain_persistence(
        _payload("danger"),
        previous_state=danger_state,
        generated_at="2026-01-04T07:30:00",
    )
    first_exit, exit_state = apply_risk_domain_persistence(
        _payload("normal"),
        previous_state=confirmed_danger_state,
        generated_at="2026-01-05T07:30:00",
    )
    confirmed_exit, _ = apply_risk_domain_persistence(
        _payload("normal"),
        previous_state=exit_state,
        generated_at="2026-01-06T07:30:00",
    )

    assert warning["confirmed_stage"] == "normal"
    assert warning2["confirmed_stage"] == "warning"
    assert first_danger["confirmed_stage"] == "warning"
    assert confirmed_danger["confirmed_stage"] == "danger"
    assert first_exit["confirmed_stage"] == "danger"
    assert confirmed_exit["confirmed_stage"] == "normal"


def test_ineligible_domain_does_not_advance_or_exit_state():
    previous = {
        "schema_version": "2.0",
        "domains": {"credit": {"confirmed_stage": "danger", "observations": ["danger", "danger"]}},
        "global": {"confirmed_stage": "danger"},
    }

    result, next_state = apply_risk_domain_persistence(
        _payload("normal", eligible=False),
        previous_state=previous,
        generated_at="2026-01-07T07:30:00",
    )

    assert result["confirmed_stage"] == "danger"
    assert result["domains"][0]["entry_rule"] == "not_evaluable_no_state_change"
    assert [item["stage"] for item in next_state["domains"]["credit"]["observations"]] == ["danger", "danger"]


def test_state_round_trip(tmp_path):
    path = tmp_path / "risk_engine_v2_state.json"
    state = {"schema_version": "2.0", "domains": {"credit": {"confirmed_stage": "warning"}}, "global": {}}

    write_risk_domain_state(path, state)

    assert json.loads(path.read_text(encoding="utf-8")) == state
    assert load_risk_domain_state(path)["domains"]["credit"]["confirmed_stage"] == "warning"


def test_excessive_gap_resets_stale_domain_state_before_entry():
    previous = {
        "schema_version": "2.0",
        "domains": {
            "credit": {
                "candidate_stage": "danger",
                "confirmed_stage": "danger",
                "observations": [
                    {"stage": "danger", "observed_at": "2026-01-01T07:30:00"},
                    {"stage": "danger", "observed_at": "2026-01-02T07:30:00"},
                ],
                "updated_at": "2026-01-02T07:30:00",
            }
        },
        "global": {"confirmed_stage": "danger"},
    }

    result, next_state = apply_risk_domain_persistence(
        _payload("danger"),
        previous_state=previous,
        generated_at="2026-02-15T07:30:00",
    )

    domain = result["domains"][0]
    assert domain["gap_reset"] is True
    assert domain["confirmed_stage"] == "normal"
    assert domain["entry_rule"] == "awaiting_2_consecutive_danger_or_higher"
    assert len(next_state["domains"]["credit"]["observations"]) == 1


def test_stale_confirmed_danger_clears_without_waiting_for_exit_count():
    previous = {
        "schema_version": "2.0",
        "domains": {
            "credit": {
                "candidate_stage": "danger",
                "confirmed_stage": "danger",
                "observations": [{"stage": "danger", "observed_at": "2026-01-02T07:30:00"}],
                "updated_at": "2026-01-02T07:30:00",
            }
        },
        "global": {
            "candidate_stage": "danger",
            "confirmed_stage": "danger",
            "observations": [{"stage": "danger", "observed_at": "2026-01-02T07:30:00"}],
            "updated_at": "2026-01-02T07:30:00",
        },
    }

    result, _ = apply_risk_domain_persistence(
        _payload("normal"),
        previous_state=previous,
        generated_at="2026-02-15T07:30:00",
    )

    assert result["domains"][0]["confirmed_stage"] == "normal"
    assert result["confirmed_stage"] == "normal"
    assert result["gap_reset"] is True


def test_global_persistence_uses_global_candidate_not_max_domain_confirmed():
    payload = _payload("normal")
    payload["candidate_stage"] = "warning"
    payload["stage"] = "warning"
    payload["confirmed_stage"] = "warning"
    payload["domains"][0]["candidate_stage"] = "normal"
    payload["domains"][0]["stage"] = "normal"
    payload["domains"][0]["confirmed_stage"] = "normal"
    previous = {
        "schema_version": "2.1",
        "domains": {
            "credit": {
                "candidate_stage": "danger",
                "confirmed_stage": "danger",
                "observations": [
                    {"stage": "danger", "observed_at": "2026-01-01T07:30:00"},
                    {"stage": "danger", "observed_at": "2026-01-02T07:30:00"},
                ],
            }
        },
        "global": {
            "candidate_stage": "warning",
            "confirmed_stage": "normal",
            "observations": [{"stage": "warning", "observed_at": "2026-01-01T07:30:00"}],
        },
    }

    result, next_state = apply_risk_domain_persistence(
        payload,
        previous_state=previous,
        generated_at="2026-01-02T07:30:00",
    )

    assert result["domains"][0]["confirmed_stage"] == "danger"
    assert result["candidate_stage"] == "warning"
    assert result["confirmed_stage"] == "warning"
    assert next_state["global"]["confirmed_stage"] == "warning"


def test_legacy_string_observations_are_migrated():
    previous = {
        "schema_version": "2.0",
        "domains": {"credit": {"confirmed_stage": "normal", "observations": ["warning"]}},
        "global": {"confirmed_stage": "normal", "observations": ["warning"]},
    }

    result, next_state = apply_risk_domain_persistence(
        _payload("warning"),
        previous_state=previous,
        generated_at="2026-01-02T07:30:00",
    )

    assert result["confirmed_stage"] == "warning"
    assert next_state["schema_version"] == "2.1"
    assert [item["stage"] for item in next_state["domains"]["credit"]["observations"]] == ["warning", "warning"]
