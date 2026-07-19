from __future__ import annotations

import pandas as pd

from project.risk_engine_v2_evidence_policy import build_evidence_policy
from project.risk_engine_v2_holdout_primary_coverage_audit import build_holdout_primary_coverage_audit


def _required_series() -> list[str]:
    policy = build_evidence_policy(generated_at="1970-01-01T00:00:00+00:00")
    series: list[str] = []
    for group in policy.get("primary_domain_groups", []) or []:
        for item in group.get("all_of", []) or []:
            if str(item) not in series:
                series.append(str(item))
        for alternatives in group.get("any_of", []) or []:
            for item in alternatives:
                if str(item) not in series:
                    series.append(str(item))
    return series


def _case(date: str, status: str) -> dict:
    series_entries = {}
    for index, series_id in enumerate(_required_series()):
        is_unavailable = status == "unavailable" and index == 0
        series_entries[series_id] = {
            "observation_date": None if is_unavailable else date,
            "age_calendar_days": None if is_unavailable else 0,
            "age_business_days": None if is_unavailable else 0,
            "history_count": 0 if is_unavailable else 60,
            "freshness_status": "missing" if is_unavailable else "fresh",
            "quality_flags": ["source_unavailable"] if is_unavailable else [],
            "point_in_time_eligible": not is_unavailable,
            "vintage_revision_status": "latest_observation_not_vintage_locked",
        }
    return {
        "date": date,
        "primary_coverage": {
            "coverage_status": status,
            "primary_strict_available": status == "primary_strict",
            "primary_missing_series": [] if status != "unavailable" else ["FRED:BAMLH0A0HYM2"],
            "series": series_entries,
        },
    }


def _payload(status: str) -> tuple[dict, dict, dict]:
    replay = {"replay_type": "risk_engine_v2_reconstructed_shadow", "cases": [_case("2026-01-02", status)]}
    review = {
        "weekly_timeline": [
            {
                "record_id": "week:2026-01-02",
                "date": "2026-01-02",
                "primary_coverage_status": status,
                "primary_strict_available": status == "primary_strict",
            }
        ]
    }
    holdout = {
        "split_policy": {"validation_start_date": "2024-03-15", "holdout_start_date": "2025-05-23"},
        "splits": {
            "holdout": {
                "events": [
                    {
                        "event_id": "event-1",
                        "event_type": "alert_only",
                        "event_anchor_date": "2026-01-02",
                        "weekly_timeline_record_ids": ["week:2026-01-02"],
                    }
                ]
            }
        },
    }
    return replay, review, holdout


def _store(path) -> None:
    frame = pd.DataFrame(index=pd.to_datetime(["2025-01-03", "2026-01-02"]))
    for series_id in _required_series():
        frame[series_id] = [1.0, 2.0]
    frame.to_csv(path)


def test_audit_preserves_strict_state_for_identical_record(tmp_path) -> None:
    replay, review, holdout = _payload("primary_strict")
    store = tmp_path / "official.csv"
    _store(store)
    payload = build_holdout_primary_coverage_audit(
        replay,
        review,
        holdout,
        selected_store_path=store,
        default_store_path=store,
    )

    assert payload["holdout_weekly_case_count"] == 1
    assert payload["weekly_coverage_counts"]["primary_strict"] == 1
    assert payload["reason_code_counts"] == {}
    assert all(not row["reason_codes"] for row in payload["matrix_rows"])
    assert all(row["series_level_reason_codes"] == "" for row in payload["matrix_rows"])
    assert payload["first_failing_stage_by_series"] == {series_id: None for series_id in _required_series()}
    assert payload["root_causes"] == []
    assert payload["data_gap_exists"] is False
    assert payload["replay_vs_holdout_reconciliation"]["coverage_state_mismatch_count"] == 0


def test_audit_preserves_partial_state_for_identical_record(tmp_path) -> None:
    replay, review, holdout = _payload("primary_partial")
    store = tmp_path / "official.csv"
    _store(store)
    payload = build_holdout_primary_coverage_audit(
        replay,
        review,
        holdout,
        selected_store_path=store,
        default_store_path=store,
    )

    assert payload["weekly_coverage_counts"]["primary_partial"] == 1
    assert payload["reason_code_counts"] == {}
    assert all("unknown_reason" not in row["reason_codes"] for row in payload["matrix_rows"])
    assert payload["root_causes"] == []
    assert payload["replay_vs_holdout_reconciliation"]["coverage_state_mismatch_count"] == 0


def test_audit_reports_missing_store_reason_codes(tmp_path) -> None:
    replay, review, holdout = _payload("unavailable")
    payload = build_holdout_primary_coverage_audit(
        replay,
        review,
        holdout,
        selected_store_path=tmp_path / "missing.csv",
        default_store_path=tmp_path / "missing_default.csv",
    )

    assert payload["audit_row_count"] == payload["holdout_weekly_case_count"] * payload["required_primary_series_count"]
    assert payload["reason_code_counts"]["series_not_in_store"] == 1
    assert payload["reason_code_counts"]["strict_requirement_not_met"] >= 1
    assert payload["root_causes"][0]["category"] == "run_source_store_absent"


def test_audit_unknown_reason_only_for_unexplained_failure(tmp_path) -> None:
    replay, review, holdout = _payload("unavailable")
    store = tmp_path / "official.csv"
    _store(store)
    first_series = _required_series()[0]
    replay["cases"][0]["primary_coverage"]["series"][first_series] = {
        "observation_date": "2026-01-02",
        "age_calendar_days": 0,
        "age_business_days": 0,
        "history_count": 60,
        "freshness_status": "fresh",
        "quality_flags": [],
        "point_in_time_eligible": False,
        "vintage_revision_status": "latest_observation_not_vintage_locked",
    }

    payload = build_holdout_primary_coverage_audit(
        replay,
        review,
        holdout,
        selected_store_path=store,
        default_store_path=store,
    )

    rows_with_unknown = [row for row in payload["matrix_rows"] if "unknown_reason" in row["reason_codes"]]
    assert len(rows_with_unknown) == 1
    assert rows_with_unknown[0]["configured_series_id"] == first_series
    assert payload["reason_code_counts"]["unknown_reason"] == 1


def test_audit_root_cause_targets_only_unavailable_subset(tmp_path) -> None:
    replay_strict, review_strict, holdout = _payload("primary_strict")
    replay_unavailable, review_unavailable, _ = _payload("unavailable")
    replay_unavailable["cases"][0]["date"] = "2026-01-09"
    review_unavailable["weekly_timeline"][0]["record_id"] = "week:2026-01-09"
    review_unavailable["weekly_timeline"][0]["date"] = "2026-01-09"
    holdout["splits"]["holdout"]["events"][0]["weekly_timeline_record_ids"] = ["week:2026-01-02", "week:2026-01-09"]
    replay = {"replay_type": "risk_engine_v2_reconstructed_shadow", "cases": replay_strict["cases"] + replay_unavailable["cases"]}
    review = {"weekly_timeline": review_strict["weekly_timeline"] + review_unavailable["weekly_timeline"]}

    payload = build_holdout_primary_coverage_audit(
        replay,
        review,
        holdout,
        selected_store_path=tmp_path / "missing.csv",
        default_store_path=tmp_path / "missing_default.csv",
    )

    assert payload["weekly_coverage_counts"]["primary_strict"] == 1
    assert payload["weekly_coverage_counts"]["unavailable"] == 1
    assert payload["root_causes"][0]["affected_week_count"] == 1
    assert payload["root_causes"][0]["affected_weeks"] == ["week:2026-01-09"]
    assert "week:2026-01-02" not in payload["root_causes"][0]["affected_weeks"]
