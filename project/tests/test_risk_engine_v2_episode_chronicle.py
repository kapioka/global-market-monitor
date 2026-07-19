from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

from project.risk_engine_v2_episode_chronicle import (
    SCHEMA_VERSION,
    ChronicleBuildError,
    ChronicleBusyError,
    _generation_lock,
    _is_current_ready_output,
    _load_verified_market_snapshot,
    _publish_pair_atomically,
    build_risk_engine_v2_episode_chronicle,
)
from project.risk_engine_v2_episode_chronicle_renderer import render_episode_chronicle_html


def _shadow_root(**values: object) -> dict[str, object]:
    return {
        "status": "ok",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "decision": {"promotion_allowed": False},
        **values,
    }


def _fixture() -> tuple[dict, dict, dict]:
    dates = ["2020-01-03", "2020-01-10", "2020-01-17", "2020-01-24", "2020-01-31", "2020-02-07"]
    stages = ["normal", "warning", "danger", "danger", "normal", "normal"]
    prices = [100.0, 98.0, 88.0, 75.0, 82.0, 91.0]
    cases = []
    weekly = []
    for day, stage, price in zip(dates, stages, prices, strict=True):
        record_id = f"week:{day}"
        weekly.append(
            {
                "record_id": record_id,
                "date": day,
                "candidate_stage": stage,
                "confirmed_stage": stage,
                "primary_coverage_status": "primary_available",
                "quality_flags": [],
            }
        )
        cases.append(
            {
                "date": day,
                "generated_at": f"{day}T07:30:00",
                "domain_candidate_stage": stage,
                "domain_confirmed_stage": stage,
                "primary_coverage": "primary_available",
                "quality_flags": [],
                "outcome": {
                    "current_price_date": day,
                    "current_price": price,
                    "drawdown_paths": {"4w": [{"date": day, "price": price, "drawdown_from_anchor": 0.0}]},
                },
            }
        )

    definitions = [
        ("event-material", "material_drawdown", "protective", "mature", dates[0:4]),
        ("event-alert", "alert_only", "over_warning", "mature", dates[1:3]),
        ("event-pending", "alert_only", "insufficient_outcome", "pending", dates[3:5]),
        ("event-quality", "alert_only", "ambiguous", "quality_rejected", dates[4:6]),
    ]
    events = []
    for event_id, event_type, classification, maturity, owned_dates in definitions:
        events.append(
            {
                "event_id": event_id,
                "event_type": event_type,
                "event_anchor_date": owned_dates[0],
                "start_date": owned_dates[0],
                "end_date": owned_dates[-1],
                "event_end_date": owned_dates[-1],
                "ownership_end_date": owned_dates[-1],
                "observed_through_date": owned_dates[-1],
                "outcome_due_date": owned_dates[-1],
                "weekly_timeline_start": owned_dates[0],
                "weekly_timeline_end": owned_dates[-1],
                "weekly_timeline_record_ids": [f"week:{day}" for day in owned_dates],
                "benchmark_id": "ACWI",
                "benchmark_source": "fixture",
                "benchmark_quality": "official",
                "peak_date": dates[0],
                "peak_value": 100.0,
                "first_candidate_warning_date": owned_dates[0],
                "first_confirmed_warning_date": owned_dates[0],
                "first_confirmed_danger_date": owned_dates[1] if len(owned_dates) > 1 else None,
                "first_material_crossing_date": owned_dates[-1] if event_type == "material_drawdown" else None,
                "maximum_drawdown": -0.25 if event_type == "material_drawdown" else -0.05,
                "maximum_drawdown_date": owned_dates[-1],
                "recovery_date": None,
                "policy_version": "fixture-v1",
                "policy_hash": "fixture-hash",
                "primary_coverage_statuses": ["primary_available"],
                "quality_flags": ["fixture_limit"] if maturity == "quality_rejected" else [],
                "maturity_status": maturity,
                "performance_evaluable": maturity == "mature",
                "primary_classification": classification,
                "classification": classification,
                "confirmed_lead_time_days": 14 if classification == "protective" else None,
            }
        )

    replay = _shadow_root(
        replay_type="reconstructed_history_shadow",
        reconstruction={"benchmark_ticker": "ACWI", "history_files_modified": False},
        cases=cases,
    )
    review = _shadow_root(source_replay_type="reconstructed_history_shadow", events=events, weekly_timeline=weekly)
    holdout = _shadow_root(
        source_replay_type="reconstructed_history_shadow",
        splits={
            "train": {"events": [events[0]], "excluded_events": []},
            "validation": {"events": [events[1]], "excluded_events": []},
            "holdout": {
                "events": [events[2]],
                "excluded_events": [{**events[3], "exclusion_reason": "boundary_overlap"}],
            },
        },
    )
    return replay, review, holdout


def _build() -> dict:
    replay, review, holdout = _fixture()
    return build_risk_engine_v2_episode_chronicle(
        replay,
        review,
        holdout,
        source_artifacts=[{"name": "fixture", "sha256": "abc"}],
        source_fingerprint="a" * 64,
        generated_at="2026-07-19T00:00:00+00:00",
    )


def _dynamic_fixture() -> tuple[dict, dict, dict, dict]:
    replay, review, holdout = _fixture()
    selection_case = replay["cases"][0]
    selection_case["domain_evidence"] = []
    specifications = [
        ("equity", "SPY", 99.0, "warning"),
        ("equity_volatility", "^VIX", 98.0, "danger"),
        ("bond_volatility", "^MOVE", 90.0, "warning"),
        ("rates", "^TNX", 80.0, "warning"),
        ("usd_funding", "DX-Y.NYB", 70.0, "warning"),
        ("credit", "HYG", 60.0, "warning"),
    ]
    for domain_id, series_id, score, stage in specifications:
        selection_case["domain_evidence"].append(
            {
                "domain_id": domain_id,
                "score_0_100": score,
                "candidate_stage": stage,
                "confirmed_stage": stage,
                "stage_eligibility": True,
                "primary_fallback_status": "primary",
                "primary_inputs_used": [series_id],
                "fallback_inputs_used": [],
                "input_observation_dates": {series_id: "2020-01-03"},
                "confidence": "high",
                "contributed_to_global_candidate": True,
                "suppressed_contribution": False,
            }
        )
    dates = ["2019-12-20", "2019-12-27", "2020-01-03", "2020-01-10", "2020-01-17", "2020-01-24", "2020-01-31", "2020-02-07"]
    series = {
        series_id: [[day, base + index] for index, day in enumerate(dates)]
        for series_id, base in [("ACWI", 100.0), ("SPY", 200.0), ("^VIX", 15.0), ("^MOVE", 70.0), ("^TNX", 2.0), ("DX-Y.NYB", 95.0), ("HYG", 85.0)]
    }
    return replay, review, holdout, {"sha256": "f" * 64, "series": series}


def _build_dynamic(snapshot: dict) -> dict:
    replay, review, holdout, _ = _dynamic_fixture()
    return build_risk_engine_v2_episode_chronicle(
        replay,
        review,
        holdout,
        source_artifacts=[{"name": "fixture", "sha256": "abc"}],
        source_fingerprint="f" * 64,
        generated_at="2026-07-19T00:00:00+00:00",
        market_snapshot=snapshot,
    )


def test_builds_contract_fixture_with_all_episode_states() -> None:
    payload = _build()

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["status"] == "ready"
    assert payload["policy_status"] == "diagnostic_only_not_promoted"
    assert payload["affects_final_action"] is False
    assert payload["promotion_allowed"] is False
    assert payload["decision"]["promotion_allowed"] is False
    assert payload["summary"]["episode_count"] == 4
    assert payload["summary"]["mature_count"] == 2
    assert payload["summary"]["pending_count"] == 1
    assert {row["split"]["name"] for row in payload["episodes"]} == {"train", "validation", "holdout"}
    excluded = next(row for row in payload["episodes"] if row["event_id"] == "event-quality")
    assert excluded["split"] == {"name": "holdout", "excluded": True, "exclusion_reason": "boundary_overlap", "performance_status": None}
    material = next(row for row in payload["episodes"] if row["event_id"] == "event-material")
    assert material["dates"]["display_end"] == "2020-02-07"
    assert payload["source_generation_assurance"]["status"] == "bounded_semantic_reconciliation"


def test_dynamic_context_series_are_point_in_time_ranked_capped_and_non_causal() -> None:
    replay, review, holdout, snapshot = _dynamic_fixture()
    payload = build_risk_engine_v2_episode_chronicle(
        replay,
        review,
        holdout,
        source_artifacts=[],
        source_fingerprint="f" * 64,
        generated_at="2026-07-19T00:00:00+00:00",
        market_snapshot=snapshot,
    )
    episode = next(row for row in payload["episodes"] if row["event_id"] == "event-material")
    selected = episode["comparison_series"]

    assert selected[0]["series_id"] == "ACWI"
    assert selected[0]["is_benchmark"] is True
    assert len(selected) == 5
    assert [row["series_id"] for row in selected[1:]] == ["^VIX", "^MOVE", "^TNX", "DX-Y.NYB"]
    assert len({row["domain_id"] for row in selected[1:]}) == 4
    assert episode["context_series_selection"]["uses_future_outcome_for_selection"] is False
    assert all(row["selection_date"] <= episode["dates"]["anchor"] for row in selected[1:])
    assert all(row["selection_reason"] == "警戒判定に寄与した独立ドメインの当時入力" for row in selected[1:])

    changed = deepcopy(snapshot)
    for series_id in ("^VIX", "^MOVE", "^TNX", "DX-Y.NYB", "HYG"):
        for point in changed["series"][series_id]:
            if point[0] > "2020-01-03":
                point[1] *= 1000
    changed_payload = build_risk_engine_v2_episode_chronicle(
        replay,
        review,
        holdout,
        source_artifacts=[],
        source_fingerprint="f" * 64,
        generated_at="2026-07-19T00:00:00+00:00",
        market_snapshot=changed,
    )
    changed_episode = next(row for row in changed_payload["episodes"] if row["event_id"] == "event-material")
    def contract(row: dict) -> tuple:
        return row["series_id"], row["selection_rank"], row["baseline_date"], row["baseline_value"]

    assert [contract(row) for row in changed_episode["comparison_series"][1:]] == [contract(row) for row in selected[1:]]


def test_rejects_selection_case_generated_after_its_selection_date() -> None:
    replay, review, holdout = _fixture()
    replay["cases"][0]["generated_at"] = "2020-01-04T00:00:00"

    with pytest.raises(ChronicleBuildError, match="not point-in-time safe"):
        build_risk_engine_v2_episode_chronicle(
            replay,
            review,
            holdout,
            source_artifacts=[],
            source_fingerprint="f" * 64,
            generated_at="2026-07-19T00:00:00+00:00",
        )


def test_negative_context_baseline_uses_cutoff_only_standardized_scale() -> None:
    replay, review, holdout, snapshot = _dynamic_fixture()
    usd = next(row for row in replay["cases"][0]["domain_evidence"] if row["domain_id"] == "usd_funding")
    usd.update(
        {
            "score_0_100": 100.0,
            "primary_inputs_used": ["FRED:NFCI"],
            "input_observation_dates": {"FRED:NFCI": "2020-01-03"},
        }
    )
    snapshot["series"]["FRED:NFCI"] = [
        ["2019-12-20", -0.8],
        ["2019-12-27", -0.4],
        ["2020-01-03", -0.1],
        ["2020-01-10", 50.0],
        ["2020-01-17", 100.0],
    ]
    payload = build_risk_engine_v2_episode_chronicle(
        replay,
        review,
        holdout,
        source_artifacts=[],
        source_fingerprint="f" * 64,
        generated_at="2026-07-19T00:00:00+00:00",
        market_snapshot=snapshot,
    )
    episode = next(row for row in payload["episodes"] if row["event_id"] == "event-material")
    series = next(row for row in episode["comparison_series"] if row["series_id"] == "FRED:NFCI")

    assert series["normalization_method"] == "standardized_delta_start_100"
    assert series["baseline_date"] == "2020-01-03"
    assert series["baseline_value"] == -0.1


def test_snapshot_loader_verifies_sha_and_rejects_non_monotonic_dates(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    project = workspace / "project"
    cache = project / "cache"
    cache.mkdir(parents=True)
    config_path = project / "config.yaml"
    csv_path = cache / "snapshot.csv"
    csv_bytes = b"date,ACWI,^VIX\n2020-01-03,100,20\n2020-01-10,101,21\n"
    csv_path.write_bytes(csv_bytes)
    replay = {
        "reconstruction": {
            "market_snapshot": {
                "loaded": True,
                "requested_path": "project/cache/snapshot.csv",
                "sha256": hashlib.sha256(csv_bytes).hexdigest(),
            }
        }
    }

    loaded = _load_verified_market_snapshot(replay, config_path)
    assert loaded["series"]["ACWI"] == [["2020-01-03", 100.0], ["2020-01-10", 101.0]]

    duplicate_bytes = b"date,ACWI\n2020-01-03,100\n2020-01-03,101\n"
    csv_path.write_bytes(duplicate_bytes)
    replay["reconstruction"]["market_snapshot"]["sha256"] = hashlib.sha256(duplicate_bytes).hexdigest()
    with pytest.raises(ChronicleBuildError, match="strictly increasing"):
        _load_verified_market_snapshot(replay, config_path)


def test_rejects_stage_mismatch_between_review_and_reconstructed_case() -> None:
    replay, review, holdout = _fixture()
    replay["cases"][1]["domain_confirmed_stage"] = "normal"

    with pytest.raises(ChronicleBuildError, match="confirmed stage mismatch"):
        build_risk_engine_v2_episode_chronicle(
            replay,
            review,
            holdout,
            source_artifacts=[],
            source_fingerprint="b" * 64,
            generated_at="2026-07-19T00:00:00+00:00",
        )


def test_rejects_unknown_or_duplicate_event_ownership() -> None:
    replay, review, holdout = _fixture()
    unknown = deepcopy(holdout)
    unknown["splits"]["holdout"]["excluded_events"] = []
    with pytest.raises(ChronicleBuildError, match="no holdout split ownership"):
        build_risk_engine_v2_episode_chronicle(
            replay,
            review,
            unknown,
            source_artifacts=[],
            source_fingerprint="c" * 64,
            generated_at="2026-07-19T00:00:00+00:00",
        )

    duplicate = deepcopy(holdout)
    duplicate["splits"]["validation"]["events"].append(review["events"][0])
    with pytest.raises(ChronicleBuildError, match="multiple splits"):
        build_risk_engine_v2_episode_chronicle(
            replay,
            review,
            duplicate,
            source_artifacts=[],
            source_fingerprint="d" * 64,
            generated_at="2026-07-19T00:00:00+00:00",
        )


def test_rejects_conflicting_price_for_same_date() -> None:
    replay, review, holdout = _fixture()
    replay["cases"][0]["outcome"]["drawdown_paths"]["13w"] = [{"date": "2020-01-10", "price": 999.0, "drawdown_from_anchor": 0.0}]
    with pytest.raises(ChronicleBuildError, match="conflicting benchmark price"):
        build_risk_engine_v2_episode_chronicle(
            replay,
            review,
            holdout,
            source_artifacts=[],
            source_fingerprint="e" * 64,
            generated_at="2026-07-19T00:00:00+00:00",
        )


def test_atomic_pair_restores_previous_files_when_second_replace_fails(tmp_path, monkeypatch) -> None:
    json_path = tmp_path / "chronicle.json"
    html_path = tmp_path / "chronicle.html"
    json_path.write_text("old-json", encoding="utf-8")
    html_path.write_text("old-html", encoding="utf-8")
    real_replace = __import__("os").replace
    calls = 0

    def fail_second_replace(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected replace failure")
        return real_replace(source, destination)

    monkeypatch.setattr("project.risk_engine_v2_episode_chronicle.os.replace", fail_second_replace)
    with pytest.raises(OSError, match="injected replace failure"):
        _publish_pair_atomically(
            json_path=json_path,
            html_path=html_path,
            json_text="new-json",
            html_text="new-html",
        )

    assert json_path.read_text(encoding="utf-8") == "old-json"
    assert html_path.read_text(encoding="utf-8") == "old-html"


def test_existing_lock_is_reported_busy_without_removing_other_owner_lock(tmp_path) -> None:
    lock_path = tmp_path / ".risk_engine_v2_episode_chronicle.lock"
    lock_path.write_text("pid=123\n", encoding="utf-8")

    with pytest.raises(ChronicleBusyError, match="already active"):
        with _generation_lock(lock_path):
            raise AssertionError("lock must not be acquired")

    assert lock_path.read_text(encoding="utf-8") == "pid=123\n"


def test_no_change_requires_the_existing_pair_to_pass_full_contract(tmp_path) -> None:
    payload = _build()
    json_path = tmp_path / "risk_engine_v2_episode_chronicle.json"
    html_path = tmp_path / "risk_engine_v2_episode_chronicle.html"
    json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    html_path.write_text(render_episode_chronicle_html(payload), encoding="utf-8")

    assert _is_current_ready_output(json_path, html_path, "a" * 64) is True

    payload["policy_status"] = "promoted"
    json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    assert _is_current_ready_output(json_path, html_path, "a" * 64) is False

    payload["policy_status"] = "diagnostic_only_not_promoted"
    json_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    html_path.write_text("<!doctype html><html></html>", encoding="utf-8")
    assert _is_current_ready_output(json_path, html_path, "a" * 64) is False
