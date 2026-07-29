from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import json
import math
import os
import shutil
import statistics
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from project.risk_engine_v2_artifact_freshness import inspect_risk_engine_v2_artifact_freshness
from project.risk_engine_v2_contract import DIAGNOSTIC_POLICY_STATUS, attach_shadow_diagnostic_contract

SCHEMA_VERSION = "risk_engine_v2.episode_chronicle.v1"
IMPLEMENTATION_VERSION = "risk_engine_v2.episode_chronicle.implementation.v3"
PAGE_FILENAME = "risk_engine_v2_episode_chronicle.html"
JSON_FILENAME = "risk_engine_v2_episode_chronicle.json"
LOCK_FILENAME = ".risk_engine_v2_episode_chronicle.lock"

SOURCE_FILES = {
    "reconstructed_replay": "risk_engine_v2_reconstructed_replay.json",
    "replay_review": "risk_engine_v2_replay_review.json",
    "holdout_validation": "risk_engine_v2_holdout_validation.json",
    "retention_reconciliation": "risk_engine_v2_retention_reconciliation.json",
    "official_series_regeneration_comparison": "risk_engine_v2_official_series_regeneration_comparison.json",
}

EVENT_TYPE_LABELS = {
    "material_drawdown": "市場急落",
    "alert_only": "警戒局面",
}
CLASSIFICATION_LABELS = {
    "protective": "防御に成功",
    "over_warning": "過剰警戒",
    "late_confirmation": "確認が遅延",
    "missed_risk": "リスクを捕捉できず",
    "ambiguous": "評価保留",
    "insufficient_outcome": "結果待ち",
}
MATURITY_LABELS = {
    "mature": "成熟済み",
    "pending": "進行中",
    "quality_rejected": "品質上限",
    "missing_benchmark_data": "価格不足",
    "invalid_alignment": "整合性不足",
}
MARKER_LABELS = {
    "candidate_warning": "警戒開始",
    "confirmed_warning": "警戒確認",
    "confirmed_danger": "危険",
    "material_crossing": "重大下落",
    "maximum_drawdown": "最大下落",
    "recovery": "回復",
    "outcome_due": "評価期限",
}

STAGE_RANK = {"normal": 0, "warning": 1, "danger": 2, "extreme": 3}
CONFIDENCE_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3}
DOMAIN_LABELS = {
    "equity": "株式",
    "equity_volatility": "株式ボラティリティ",
    "bond_volatility": "債券ボラティリティ",
    "credit": "信用市場",
    "rates": "金利",
    "usd_funding": "ドル資金調達",
    "commodity_inflation": "商品・インフレ",
}
SERIES_LABELS = {
    "ACWI": "ACWI",
    "SPY": "S&P 500",
    "^VIX": "VIX",
    "^MOVE": "MOVE",
    "^TNX": "米10年金利",
    "DX-Y.NYB": "ドル指数",
    "HYG": "ハイイールド債",
    "LQD": "投資適格社債",
    "CL=F": "WTI原油",
    "BZ=F": "ブレント原油",
    "FRED:BAMLH0A0HYM2": "米HY OAS",
    "FRED:BAMLC0A0CM": "米社債OAS",
    "FRED:DFII10": "米10年実質金利",
    "FRED:T10YIE": "米10年期待インフレ",
    "FRED:T10Y2Y": "米10年-2年金利差",
    "FRED:T10Y3M": "米10年-3か月金利差",
    "FRED:NFCI": "金融環境指数",
}
SERIES_UNITS = {
    "^VIX": "index",
    "^MOVE": "index",
    "^TNX": "%",
    "DX-Y.NYB": "index",
    "CL=F": "USD",
    "BZ=F": "USD",
    "FRED:BAMLH0A0HYM2": "%",
    "FRED:BAMLC0A0CM": "%",
    "FRED:DFII10": "%",
    "FRED:T10YIE": "%",
    "FRED:T10Y2Y": "%",
    "FRED:T10Y3M": "%",
    "FRED:NFCI": "index",
}
DOMAIN_CONTEXT_PROXIES = {"commodity_inflation": ["CL=F", "BZ=F"]}
MAX_CONTEXT_SERIES = 4
MAX_TOTAL_SERIES = 5
ALIGNMENT_MAX_AGE_DAYS = 10


class ChronicleBuildError(ValueError):
    pass


class ChronicleBusyError(ChronicleBuildError):
    pass


def build_risk_engine_v2_episode_chronicle(
    replay_payload: dict[str, Any],
    review_payload: dict[str, Any],
    holdout_payload: dict[str, Any],
    *,
    source_artifacts: list[dict[str, Any]],
    source_fingerprint: str,
    generated_at: str,
    market_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _require_shadow_contract(replay_payload, "reconstructed_replay")
    _require_shadow_contract(review_payload, "replay_review")
    _require_shadow_contract(holdout_payload, "holdout_validation")

    events = review_payload.get("events") or review_payload.get("episodes")
    if not isinstance(events, list) or not events:
        raise ChronicleBuildError("replay review must contain at least one event")
    weekly = _dict_rows(review_payload.get("weekly_timeline"), "replay review weekly_timeline")
    cases = _dict_rows(replay_payload.get("cases"), "reconstructed replay cases")
    weekly_by_id = _unique_map(weekly, "record_id", "weekly record")
    cases_by_date = _unique_map(cases, "date", "reconstructed case")
    split_by_event = _split_map(holdout_payload)
    price_by_date = _canonical_price_map(cases)
    reconstruction = replay_payload.get("reconstruction")
    if not isinstance(reconstruction, dict):
        raise ChronicleBuildError("reconstructed replay reconstruction metadata is missing")
    replay_benchmark = _required_text(reconstruction, "benchmark_ticker")

    normalized: list[dict[str, Any]] = []
    seen_event_ids: set[str] = set()
    for raw_event in events:
        if not isinstance(raw_event, dict):
            raise ChronicleBuildError("replay review event must be an object")
        event_id = _required_text(raw_event, "event_id")
        if event_id in seen_event_ids:
            raise ChronicleBuildError(f"duplicate event_id: {event_id}")
        seen_event_ids.add(event_id)
        split_info = split_by_event.get(event_id)
        if split_info is None:
            raise ChronicleBuildError(f"event has no holdout split ownership: {event_id}")
        if str(raw_event.get("benchmark_id") or "") != replay_benchmark:
            raise ChronicleBuildError(f"event benchmark does not match reconstructed replay: {event_id}")
        normalized.append(
            _normalize_episode(
                raw_event,
                split_info=split_info,
                weekly_by_id=weekly_by_id,
                cases_by_date=cases_by_date,
                price_by_date=price_by_date,
                market_snapshot=market_snapshot,
            )
        )

    normalized.sort(key=lambda row: (str(row["dates"]["anchor"]), str(row["event_id"])), reverse=True)
    maturity_counts = _counts(row["maturity"]["status"] for row in normalized)
    classification_counts = _counts(row["classification"]["status"] for row in normalized)
    event_type_counts = _counts(row["event_type"]["status"] for row in normalized)
    latest = normalized[0]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "implementation_version": IMPLEMENTATION_VERSION,
        "generation_id": source_fingerprint[:16],
        "generated_at": generated_at,
        "status": "ready",
        "freshness_status": "current",
        "policy_status": DIAGNOSTIC_POLICY_STATUS,
        "affects_final_action": False,
        "promotion_allowed": False,
        "source_fingerprint": source_fingerprint,
        "source_generation_assurance": {
            "status": "bounded_semantic_reconciliation",
            "exact_replay_case_hash_required": True,
            "review_and_holdout_counts_reconciled": True,
            "limitation": "current review and holdout artifacts do not expose one shared evidence-chain generation ID",
        },
        "source_artifacts": source_artifacts,
        "page_filename": PAGE_FILENAME,
        "summary": {
            "episode_count": len(normalized),
            "mature_count": maturity_counts.get("mature", 0),
            "pending_count": maturity_counts.get("pending", 0),
            "maturity_counts": maturity_counts,
            "classification_counts": classification_counts,
            "event_type_counts": event_type_counts,
            "latest_event_id": latest["event_id"],
            "latest_event_title": latest["title"],
            "latest_event_date": latest["dates"]["anchor"],
        },
        "episodes": normalized,
        "decision": {
            "promotion_allowed": False,
            "reason": "episode chronicle is a diagnostic-only historical presentation",
        },
    }
    return attach_shadow_diagnostic_contract(payload, artifact_type="episode_chronicle")


def run_risk_engine_v2_episode_chronicle(
    reports_dir: str | Path = "project/reports",
    config_path: str | Path = "project/config.yaml",
    *,
    as_of: str | date | datetime | None = None,
    max_age_days: int = 3,
) -> dict[str, Any]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    as_of_value = as_of or date.today()
    with _generation_lock(reports_path / LOCK_FILENAME):
        sources, source_artifacts, fingerprint, market_snapshot = _load_publication_sources(
            reports_path,
            config_path=Path(config_path),
            as_of=as_of_value,
            max_age_days=max_age_days,
        )
        json_path = reports_path / JSON_FILENAME
        html_path = reports_path / PAGE_FILENAME
        if _is_current_ready_output(json_path, html_path, fingerprint):
            return {
                "status": "no_change",
                "source_fingerprint": fingerprint,
                "json_path": str(json_path),
                "html_path": str(html_path),
            }

        generated_at = datetime.now(tz=UTC).isoformat()
        payload = build_risk_engine_v2_episode_chronicle(
            sources["reconstructed_replay"],
            sources["replay_review"],
            sources["holdout_validation"],
            source_artifacts=source_artifacts,
            source_fingerprint=fingerprint,
            generated_at=generated_at,
            market_snapshot=market_snapshot,
        )
        from project.risk_engine_v2_episode_chronicle_renderer import render_episode_chronicle_html

        html_text = render_episode_chronicle_html(payload)
        json_text = json.dumps(payload, ensure_ascii=False, indent=2)
        _validate_publication_pair(payload, json_text, html_text)
        _publish_pair_atomically(json_path=json_path, html_path=html_path, json_text=json_text, html_text=html_text)
        return {
            "status": "generated",
            "source_fingerprint": fingerprint,
            "episode_count": payload["summary"]["episode_count"],
            "json_path": str(json_path),
            "html_path": str(html_path),
        }


def _normalize_episode(
    event: dict[str, Any],
    *,
    split_info: dict[str, Any],
    weekly_by_id: dict[str, dict[str, Any]],
    cases_by_date: dict[str, dict[str, Any]],
    price_by_date: dict[str, float],
    market_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    event_id = _required_text(event, "event_id")
    record_ids = event.get("weekly_timeline_record_ids")
    if not isinstance(record_ids, list) or not record_ids:
        raise ChronicleBuildError(f"event has no weekly record references: {event_id}")
    records: list[dict[str, Any]] = []
    for raw_id in record_ids:
        record_id = str(raw_id)
        record = weekly_by_id.get(record_id)
        if record is None:
            raise ChronicleBuildError(f"event references unknown weekly record: {event_id} -> {record_id}")
        records.append(record)
    records.sort(key=lambda row: str(row.get("date") or ""))
    record_dates = [_required_text(row, "date") for row in records]
    if len(record_dates) != len(set(record_dates)):
        raise ChronicleBuildError(f"event contains duplicate weekly dates: {event_id}")
    for record in records:
        day = _required_text(record, "date")
        case = cases_by_date.get(day)
        if case is None:
            raise ChronicleBuildError(f"event weekly record has no reconstructed case: {event_id} -> {day}")
        if record.get("candidate_stage") != case.get("domain_candidate_stage"):
            raise ChronicleBuildError(f"candidate stage mismatch: {event_id} -> {day}")
        if record.get("confirmed_stage") != case.get("domain_confirmed_stage"):
            raise ChronicleBuildError(f"confirmed stage mismatch: {event_id} -> {day}")

    window_start, window_end = _display_window(event, record_dates, sorted(price_by_date))
    chart_dates = [day for day in sorted(price_by_date) if window_start <= day <= window_end]
    if not chart_dates:
        raise ChronicleBuildError(f"event has no benchmark chart points: {event_id}")
    stage_by_date = {str(row["date"]): row for row in records}
    peak_value = _number_or_none(event.get("peak_value"))
    chart_points: list[dict[str, Any]] = []
    for day in chart_dates:
        record = stage_by_date.get(day)
        case = cases_by_date.get(day)
        price = price_by_date[day]
        chart_points.append(
            {
                "date": day,
                "benchmark_price": round(price, 6),
                "drawdown": round(price / peak_value - 1.0, 6) if peak_value and peak_value > 0 else None,
                "candidate_stage": (record or {}).get("candidate_stage") or (case or {}).get("domain_candidate_stage"),
                "confirmed_stage": (record or {}).get("confirmed_stage") or (case or {}).get("domain_confirmed_stage"),
                "coverage_status": (record or {}).get("primary_coverage_status") or (case or {}).get("primary_coverage"),
                "quality_flags": list((record or {}).get("quality_flags") or (case or {}).get("quality_flags") or []),
            }
        )

    context_selection, comparison_series = _build_comparison_series(
        event=event,
        chart_points=chart_points,
        record_dates=record_dates,
        cases_by_date=cases_by_date,
        market_snapshot=market_snapshot,
    )

    markers = _markers(event, chart_dates)
    narrative = [_narrative_entry(event_id, marker) for marker in markers]
    event_type = _required_text(event, "event_type")
    classification = str(event.get("primary_classification") or event.get("classification") or "ambiguous")
    maturity = str(event.get("maturity_status") or event.get("outcome_maturity_status") or "pending")
    anchor = _required_text(event, "event_anchor_date")
    title = f"{_japanese_date(anchor)} — {EVENT_TYPE_LABELS.get(event_type, event_type)}"
    maximum_drawdown = _number_or_none(event.get("maximum_drawdown"))
    lead_time = event.get("confirmed_lead_time_days")
    coverage_statuses = [str(value) for value in event.get("primary_coverage_statuses") or []]
    quality_flags = [str(value) for value in event.get("quality_flags") or []]
    return {
        "event_id": event_id,
        "title": title,
        "event_type": {"status": event_type, "label": EVENT_TYPE_LABELS.get(event_type, event_type)},
        "benchmark": {
            "id": event.get("benchmark_id") or "unknown",
            "source": event.get("benchmark_source") or "reconstructed_replay_outcome_prices",
            "quality": event.get("benchmark_quality") or "unknown",
        },
        "policy": {"version": event.get("policy_version"), "hash": event.get("policy_hash")},
        "split": split_info,
        "classification": {"status": classification, "label": CLASSIFICATION_LABELS.get(classification, classification)},
        "maturity": {
            "status": maturity,
            "label": MATURITY_LABELS.get(maturity, maturity),
            "performance_evaluable": event.get("performance_evaluable") is True,
        },
        "dates": {
            "anchor": anchor,
            "start": event.get("start_date"),
            "end": event.get("event_end_date") or event.get("end_date"),
            "ownership_end": event.get("ownership_end_date"),
            "observed_through": event.get("observed_through_date") or event.get("outcome_observed_through"),
            "outcome_due": event.get("outcome_due_date"),
            "recovery": event.get("recovery_date"),
            "display_start": window_start,
            "display_end": window_end,
        },
        "chart_points": chart_points,
        "context_series_selection": context_selection,
        "comparison_series": comparison_series,
        "markers": markers,
        "evaluation": {
            "status": classification,
            "label": CLASSIFICATION_LABELS.get(classification, classification),
            "comment": _evaluation_comment(classification, maturity),
            "lead_time_days": int(lead_time) if isinstance(lead_time, int | float) else None,
            "maximum_drawdown": round(maximum_drawdown, 6) if maximum_drawdown is not None else None,
            "official_series_coverage": _coverage_summary(coverage_statuses),
            "data_quality": "good" if not quality_flags else "limited",
            "limitations": quality_flags,
        },
        "narrative": narrative,
        "provenance": {
            "weekly_record_ids": [str(value) for value in record_ids],
            "weekly_record_count": len(record_ids),
            "policy_hash": event.get("policy_hash"),
            "coverage_statuses": coverage_statuses,
            "market_snapshot_sha256": (market_snapshot or {}).get("sha256"),
        },
    }


def _build_comparison_series(
    *,
    event: dict[str, Any],
    chart_points: list[dict[str, Any]],
    record_dates: list[str],
    cases_by_date: dict[str, dict[str, Any]],
    market_snapshot: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    benchmark = _benchmark_comparison_series(event, chart_points)
    anchor = _required_text(event, "event_anchor_date")
    eligible_dates = [day for day in record_dates if day <= anchor]
    if not eligible_dates:
        raise ChronicleBuildError(f"event has no point-in-time selection case: {event.get('event_id')}")
    selection_date = max(eligible_dates)
    selection_case = cases_by_date.get(selection_date)
    if selection_case is None:
        raise ChronicleBuildError(f"event selection case is missing: {event.get('event_id')} -> {selection_date}")
    case_generated_at = selection_case.get("generated_at")
    if not isinstance(case_generated_at, str) or case_generated_at[:10] > selection_date:
        raise ChronicleBuildError(f"event selection case is not point-in-time safe: {event.get('event_id')} -> {selection_date}")

    selection = {
        "status": "benchmark_only",
        "policy_version": "risk_engine_v2.episode_context_series.v1",
        "selection_date": selection_date,
        "selection_cutoff": "latest_reconstructed_weekly_case_on_or_before_event_anchor",
        "uses_future_outcome_for_selection": False,
        "max_context_series": MAX_CONTEXT_SERIES,
        "max_total_series": MAX_TOTAL_SERIES,
        "selected_context_count": 0,
        "omissions": [],
    }
    if not isinstance(market_snapshot, dict):
        selection["reason"] = "verified market snapshot is unavailable"
        return selection, [benchmark]

    snapshot_series = market_snapshot.get("series")
    if not isinstance(snapshot_series, dict):
        selection["reason"] = "verified market snapshot series are unavailable"
        return selection, [benchmark]

    domain_rows = selection_case.get("domain_evidence")
    if not isinstance(domain_rows, list):
        selection["reason"] = "selection case domain evidence is unavailable"
        return selection, [benchmark]

    candidates: list[dict[str, Any]] = []
    omissions: list[dict[str, str]] = []
    chart_dates = [str(point["date"]) for point in chart_points]
    cutoff_dates = [day for day in chart_dates if day <= selection_date]
    for row in domain_rows:
        if not isinstance(row, dict):
            continue
        domain_id = str(row.get("domain_id") or "unknown")
        if domain_id == "equity":
            omissions.append({"domain_id": domain_id, "reason": "represented_by_acwi_benchmark"})
            continue
        if row.get("contributed_to_global_candidate") is not True:
            continue
        if row.get("stage_eligibility") is not True or row.get("suppressed_contribution") is True:
            omissions.append({"domain_id": domain_id, "reason": "contribution_not_eligible"})
            continue

        primary_inputs = _text_list(row.get("primary_inputs_used"))
        fallback_inputs = _text_list(row.get("fallback_inputs_used"))
        declared_status = str(row.get("primary_fallback_status") or "")
        if primary_inputs and declared_status == "primary":
            input_ids = primary_inputs
            source_status = "primary"
            evidence_basis = "explicit_primary_input"
        elif fallback_inputs and declared_status == "fallback":
            input_ids = fallback_inputs
            source_status = "fallback"
            evidence_basis = "explicit_fallback_input"
        else:
            input_ids = list(DOMAIN_CONTEXT_PROXIES.get(domain_id, []))
            source_status = "context_proxy"
            evidence_basis = "declared_domain_context_proxy"
        if not input_ids:
            omissions.append({"domain_id": domain_id, "reason": "no_raw_series_identifier"})
            continue

        viable: list[tuple[float, str]] = []
        for series_id in input_ids:
            if series_id == str(event.get("benchmark_id") or "ACWI"):
                continue
            points = snapshot_series.get(series_id)
            if not isinstance(points, list):
                continue
            recorded_dates = row.get("input_observation_dates")
            recorded_day = recorded_dates.get(series_id) if isinstance(recorded_dates, dict) else None
            if source_status != "context_proxy" and (
                not isinstance(recorded_day, str) or recorded_day > selection_date
            ):
                continue
            if _aligned_observation(points, selection_date) is None:
                continue
            abnormality = _point_in_time_abnormality(points, selection_date)
            viable.append((abnormality, series_id))
        if not viable:
            omissions.append({"domain_id": domain_id, "reason": "series_missing_from_verified_snapshot"})
            continue
        viable.sort(key=lambda item: (-item[0], item[1]))
        abnormality, series_id = viable[0]
        comparison = _context_comparison_series(
            series_id=series_id,
            domain_id=domain_id,
            domain_row=row,
            source_status=source_status,
            evidence_basis=evidence_basis,
            selection_date=selection_date,
            chart_dates=chart_dates,
            cutoff_dates=cutoff_dates,
            snapshot_points=snapshot_series[series_id],
            abnormality=abnormality,
        )
        if comparison is None:
            omissions.append({"domain_id": domain_id, "reason": "insufficient_aligned_chart_coverage"})
            continue
        candidates.append(comparison)

    candidates.sort(
        key=lambda item: (
            -STAGE_RANK.get(str(item["candidate_stage"]), 0),
            -float(item["domain_score"]),
            -CONFIDENCE_RANK.get(str(item["confidence"]), 0),
            -float(item["point_in_time_abnormality"]),
            str(item["domain_id"]),
            str(item["series_id"]),
        )
    )
    selected: list[dict[str, Any]] = []
    selected_domains: set[str] = set()
    selected_series: set[str] = {str(event.get("benchmark_id") or "ACWI")}
    for candidate in candidates:
        domain_id = str(candidate["domain_id"])
        series_id = str(candidate["series_id"])
        if domain_id in selected_domains:
            omissions.append({"domain_id": domain_id, "reason": "duplicate_domain"})
            continue
        if series_id in selected_series:
            omissions.append({"domain_id": domain_id, "reason": "duplicate_series"})
            continue
        if len(selected) >= MAX_CONTEXT_SERIES:
            omissions.append({"domain_id": domain_id, "reason": "maximum_series_limit"})
            continue
        selected.append(candidate)
        selected_domains.add(domain_id)
        selected_series.add(series_id)
    for rank, item in enumerate(selected, start=1):
        item["selection_rank"] = rank
    selection.update(
        {
            "status": "selected" if selected else "benchmark_only",
            "selected_context_count": len(selected),
            "reason": "point-in-time contributing domains ranked without future outcome data",
            "omissions": omissions,
        }
    )
    return selection, [benchmark, *selected]


def _benchmark_comparison_series(event: dict[str, Any], chart_points: list[dict[str, Any]]) -> dict[str, Any]:
    baseline = float(chart_points[0]["benchmark_price"])
    points = [
        {
            "date": str(point["date"]),
            "observation_date": str(point["date"]),
            "raw_value": float(point["benchmark_price"]),
            "indexed_value": round(float(point["benchmark_price"]) / baseline * 100.0, 6),
        }
        for point in chart_points
    ]
    return {
        "series_id": str(event.get("benchmark_id") or "ACWI"),
        "label": SERIES_LABELS.get(str(event.get("benchmark_id") or "ACWI"), "ACWI"),
        "domain_id": "benchmark",
        "domain_label": "グローバル株式",
        "is_benchmark": True,
        "source_status": "benchmark",
        "evidence_basis": "canonical_reconstructed_benchmark",
        "selection_rank": 0,
        "normalization_method": "ratio_index_start_100",
        "baseline_date": str(chart_points[0]["date"]),
        "baseline_value": round(baseline, 6),
        "raw_unit": "price",
        "coverage_ratio": 1.0,
        "points": points,
    }


def _context_comparison_series(
    *,
    series_id: str,
    domain_id: str,
    domain_row: dict[str, Any],
    source_status: str,
    evidence_basis: str,
    selection_date: str,
    chart_dates: list[str],
    cutoff_dates: list[str],
    snapshot_points: list[Any],
    abnormality: float,
) -> dict[str, Any] | None:
    aligned: list[dict[str, Any]] = []
    for day in chart_dates:
        observation = _aligned_observation(snapshot_points, day)
        aligned.append(
            {
                "date": day,
                "observation_date": observation[0] if observation else None,
                "raw_value": round(observation[1], 6) if observation else None,
            }
        )
    cutoff_set = set(cutoff_dates)
    cutoff_valid = [point for point in aligned if point["date"] in cutoff_set and point["raw_value"] is not None]
    minimum = max(1, math.ceil(len(cutoff_dates) * 0.6))
    if not cutoff_dates or len(cutoff_valid) < minimum:
        return None
    baseline_point = cutoff_valid[0]
    baseline = float(baseline_point["raw_value"])
    if baseline > 0:
        method = "ratio_index_start_100"
        for point in aligned:
            raw_value = point["raw_value"]
            point["indexed_value"] = round(float(raw_value) / baseline * 100.0, 6) if raw_value is not None else None
    else:
        history = _historical_values(snapshot_points, selection_date, limit=52)
        scale = statistics.pstdev(history) if len(history) >= 2 else 0.0
        if not math.isfinite(scale) or scale <= 1e-12:
            return None
        method = "standardized_delta_start_100"
        for point in aligned:
            raw_value = point["raw_value"]
            point["indexed_value"] = (
                round(100.0 + ((float(raw_value) - baseline) / scale) * 10.0, 6) if raw_value is not None else None
            )
    return {
        "series_id": series_id,
        "label": SERIES_LABELS.get(series_id, series_id),
        "domain_id": domain_id,
        "domain_label": DOMAIN_LABELS.get(domain_id, domain_id),
        "is_benchmark": False,
        "source_status": source_status,
        "evidence_basis": evidence_basis,
        "selection_rank": None,
        "selection_date": selection_date,
        "selection_reason": "警戒判定に寄与した独立ドメインの当時入力",
        "domain_score": round(float(domain_row.get("score_0_100") or 0.0), 4),
        "candidate_stage": str(domain_row.get("candidate_stage") or "normal"),
        "confirmed_stage": str(domain_row.get("confirmed_stage") or "normal"),
        "confidence": str(domain_row.get("confidence") or "none"),
        "point_in_time_abnormality": round(abnormality, 6),
        "normalization_method": method,
        "baseline_date": str(baseline_point["date"]),
        "baseline_value": round(baseline, 6),
        "raw_unit": SERIES_UNITS.get(series_id, "value"),
        "selection_coverage_ratio": round(len(cutoff_valid) / len(cutoff_dates), 6),
        "display_coverage_ratio": round(sum(point["raw_value"] is not None for point in aligned) / len(chart_dates), 6),
        "points": aligned,
    }


def _point_in_time_abnormality(points: list[Any], selection_date: str) -> float:
    history = _historical_values(points, selection_date, limit=52)
    if len(history) < 8:
        return 0.0
    current = history[-1]
    baseline = history[:-1]
    spread = statistics.pstdev(baseline)
    if not math.isfinite(spread) or spread <= 1e-12:
        return 0.0
    return round(abs(current - statistics.mean(baseline)) / spread, 6)


def _historical_values(points: list[Any], cutoff: str, *, limit: int) -> list[float]:
    values = [
        float(point[1])
        for point in points
        if isinstance(point, list | tuple)
        and len(point) == 2
        and str(point[0]) <= cutoff
        and _is_finite_number(point[1])
    ]
    return values[-limit:]


def _aligned_observation(points: list[Any], target_day: str) -> tuple[str, float] | None:
    valid = [
        (str(point[0]), float(point[1]))
        for point in points
        if isinstance(point, list | tuple) and len(point) == 2 and isinstance(point[0], str) and _is_finite_number(point[1])
    ]
    if not valid:
        return None
    days = [point[0] for point in valid]
    index = bisect.bisect_right(days, target_day) - 1
    if index < 0:
        return None
    observed_day, value = valid[index]
    age = (date.fromisoformat(target_day) - date.fromisoformat(observed_day)).days
    if age < 0 or age > ALIGNMENT_MAX_AGE_DAYS:
        return None
    return observed_day, value


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item]


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, int | float):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return False
    return math.isfinite(float(value))


def _display_window(event: dict[str, Any], record_dates: list[str], price_dates: list[str]) -> tuple[str, str]:
    start_candidates = _valid_dates(
        [
            event.get("event_anchor_date"),
            event.get("weekly_timeline_start"),
            event.get("peak_date"),
            event.get("drawdown_onset_date"),
            event.get("first_candidate_warning_date"),
            event.get("first_confirmed_warning_date"),
            event.get("first_confirmed_danger_date"),
            *record_dates,
        ]
    )
    maturity = str(event.get("maturity_status") or event.get("outcome_maturity_status") or "pending")
    end_values = [
        event.get("event_end_date"),
        event.get("end_date"),
        event.get("ownership_end_date"),
        event.get("recovery_date"),
        event.get("outcome_due_date"),
        *record_dates,
    ]
    if maturity == "pending":
        end_values.extend([event.get("observed_through_date"), event.get("outcome_observed_through")])
    end_candidates = _valid_dates(end_values)
    if not start_candidates or not end_candidates or not price_dates:
        raise ChronicleBuildError("event display window cannot be derived")
    raw_start = min(start_candidates)
    raw_end = max(end_candidates)
    in_range = [day for day in price_dates if raw_start <= day <= raw_end]
    if not in_range:
        raise ChronicleBuildError("event display window has no official benchmark observations")
    first_index = price_dates.index(in_range[0])
    last_index = price_dates.index(in_range[-1])
    return price_dates[max(0, first_index - 2)], price_dates[min(len(price_dates) - 1, last_index + 2)]


def _markers(event: dict[str, Any], chart_dates: list[str]) -> list[dict[str, Any]]:
    candidates = [
        ("candidate_warning", event.get("first_candidate_warning_date"), None, "candidate"),
        ("confirmed_warning", event.get("first_confirmed_warning_date"), None, "confirmed"),
        ("confirmed_danger", event.get("first_confirmed_danger_date"), None, "confirmed"),
        ("material_crossing", event.get("first_material_crossing_date"), event.get("crossing_value"), "outcome"),
        ("maximum_drawdown", event.get("maximum_drawdown_date"), event.get("maximum_drawdown"), "outcome"),
        ("recovery", event.get("recovery_date"), None, "outcome"),
        ("outcome_due", event.get("outcome_due_date"), None, "outcome"),
    ]
    result: list[dict[str, Any]] = []
    event_id = _required_text(event, "event_id")
    for kind, raw_date, value, stage in candidates:
        if not isinstance(raw_date, str) or raw_date not in chart_dates:
            continue
        result.append(
            {
                "marker_id": f"{event_id}:{kind}",
                "date": raw_date,
                "kind": kind,
                "label": MARKER_LABELS[kind],
                "stage": stage,
                "value": _number_or_none(value),
                "narrative_id": f"{event_id}:narrative:{kind}",
            }
        )
    result.sort(key=lambda marker: (marker["date"], marker["kind"]))
    return result


def _narrative_entry(event_id: str, marker: dict[str, Any]) -> dict[str, Any]:
    kind = str(marker["kind"])
    label = str(marker["label"])
    descriptions = {
        "candidate_warning": "候補段階で警戒条件が観測されました。",
        "confirmed_warning": "確認条件が揃い、警戒局面として記録されました。",
        "confirmed_danger": "確認済みの危険段階へ進みました。",
        "material_crossing": "ベンチマークが重大下落の基準を通過しました。",
        "maximum_drawdown": "このエピソードで最も深い下落を記録しました。",
        "recovery": "記録された回復条件を満たしました。",
        "outcome_due": "評価期間の期限に達しました。",
    }
    return {
        "narrative_id": f"{event_id}:narrative:{kind}",
        "marker_id": marker["marker_id"],
        "date": marker["date"],
        "label": label,
        "text": descriptions[kind],
        "stage": marker["stage"],
    }


def _canonical_price_map(cases: list[dict[str, Any]]) -> dict[str, float]:
    prices: dict[str, float] = {}
    for case in cases:
        outcome = case.get("outcome")
        if not isinstance(outcome, dict):
            continue
        current_date = outcome.get("current_price_date") or case.get("date")
        current_price = _number_or_none(outcome.get("current_price"))
        if current_date != case.get("date"):
            raise ChronicleBuildError(f"current_price_date does not match reconstructed case date: {case.get('date')}")
        if isinstance(current_date, str) and current_price is not None:
            _merge_price(prices, current_date, current_price)
        drawdown_paths = outcome.get("drawdown_paths")
        if not isinstance(drawdown_paths, dict):
            continue
        for path in drawdown_paths.values():
            if not isinstance(path, list):
                continue
            for point in path:
                if not isinstance(point, dict):
                    continue
                point_date = point.get("date")
                point_price = _number_or_none(point.get("price"))
                if isinstance(point_date, str) and point_price is not None:
                    _merge_price(prices, point_date, point_price)
    if not prices:
        raise ChronicleBuildError("reconstructed replay contains no benchmark price path")
    return prices


def _merge_price(prices: dict[str, float], day: str, value: float) -> None:
    existing = prices.get(day)
    if existing is not None and abs(existing - value) > 1e-6:
        raise ChronicleBuildError(f"conflicting benchmark price for {day}: {existing} != {value}")
    prices[day] = value


def _split_map(holdout_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    splits = holdout_payload.get("splits")
    if not isinstance(splits, dict):
        raise ChronicleBuildError("holdout validation splits are missing")
    result: dict[str, dict[str, Any]] = {}
    for split_name in ("train", "validation", "holdout"):
        split = splits.get(split_name)
        if not isinstance(split, dict):
            raise ChronicleBuildError(f"holdout split is missing: {split_name}")
        rows = split.get("events") or split.get("episodes") or []
        excluded = split.get("excluded_events") or []
        for row, excluded_flag in [*((item, False) for item in rows), *((item, True) for item in excluded)]:
            if not isinstance(row, dict):
                raise ChronicleBuildError(f"invalid event in split: {split_name}")
            event_id = _required_text(row, "event_id")
            owner_name = str(row.get("split") or split_name) if excluded_flag else split_name
            ownership = {
                "name": owner_name,
                "excluded": excluded_flag,
                "exclusion_reason": row.get("exclusion_reason") if excluded_flag else None,
                "performance_status": row.get("performance_status"),
            }
            if event_id in result:
                if result[event_id] == ownership and excluded_flag:
                    continue
                raise ChronicleBuildError(f"event belongs to multiple splits: {event_id}")
            result[event_id] = ownership
    return result


def _load_publication_sources(
    reports_path: Path,
    *,
    config_path: Path,
    as_of: str | date | datetime,
    max_age_days: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], str, dict[str, Any]]:
    freshness = inspect_risk_engine_v2_artifact_freshness(
        reports_dir=reports_path,
        config_path=config_path,
        as_of=as_of,
        max_age_days=max_age_days,
    )
    if (freshness.get("source_contract") or {}).get("status") != "shadow_contract":
        raise ChronicleBuildError("risk_engine_v2 source mode is not shadow")
    if (freshness.get("artifact_consistency") or {}).get("status") != "consistent":
        raise ChronicleBuildError("artifact freshness reconciliation is not consistent")
    snapshot_status = (freshness.get("artifact_snapshot") or {}).get("status")
    if snapshot_status != "current":
        if snapshot_status == "historical":
            raise ChronicleBuildError("入力成果物が更新期限を超えています")
        raise ChronicleBuildError(f"入力成果物の鮮度状態が更新条件を満たしません（状態: {snapshot_status}）")

    sources: dict[str, dict[str, Any]] = {}
    source_artifacts: list[dict[str, Any]] = []
    fingerprint_rows: list[dict[str, str]] = []
    for name, filename in SOURCE_FILES.items():
        path = reports_path / filename
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ChronicleBuildError(f"source artifact is malformed: {filename}: {error}") from error
        if not isinstance(payload, dict):
            raise ChronicleBuildError(f"source artifact root must be an object: {filename}")
        _require_shadow_contract(payload, name)
        sources[name] = payload
        fingerprint_rows.append({"name": filename, "sha256": digest})
        source_artifacts.append(
            {
                "name": name,
                "path": str(path),
                "sha256": digest,
                "schema_version": payload.get("schema_version"),
                "status": payload.get("status"),
            }
        )

    retention = sources["retention_reconciliation"]
    if retention.get("status") != "pass" or retention.get("completeness_status") != "complete":
        raise ChronicleBuildError("retention reconciliation publication gate did not pass")
    comparison = sources["official_series_regeneration_comparison"]
    reconciliation = comparison.get("cross_artifact_reconciliation")
    if comparison.get("status") != "pass" or not isinstance(reconciliation, dict) or reconciliation.get("status") != "pass":
        raise ChronicleBuildError("official-series regeneration comparison publication gate did not pass")
    _validate_comparison_against_sources(sources)
    market_snapshot = _load_verified_market_snapshot(sources["reconstructed_replay"], config_path)
    fingerprint_rows.append({"name": "market_snapshot", "sha256": market_snapshot["sha256"]})
    source_artifacts.append(
        {
            "name": "market_snapshot",
            "path": market_snapshot["path"],
            "sha256": market_snapshot["sha256"],
            "schema_version": "csv.date_indexed_series.v1",
            "status": "loaded",
            "row_count": market_snapshot["row_count"],
            "series_count": len(market_snapshot["series"]),
        }
    )
    fingerprint = hashlib.sha256(json.dumps(fingerprint_rows, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return sources, source_artifacts, fingerprint, market_snapshot


def _load_verified_market_snapshot(replay_payload: dict[str, Any], config_path: Path) -> dict[str, Any]:
    reconstruction = replay_payload.get("reconstruction")
    if not isinstance(reconstruction, dict):
        raise ChronicleBuildError("reconstructed replay reconstruction metadata is missing")
    metadata = reconstruction.get("market_snapshot")
    if not isinstance(metadata, dict) or metadata.get("loaded") is not True:
        raise ChronicleBuildError("reconstructed replay market snapshot provenance is missing")
    expected_sha = metadata.get("sha256")
    if not isinstance(expected_sha, str) or len(expected_sha) != 64:
        raise ChronicleBuildError("reconstructed replay market snapshot SHA256 is missing")

    workspace_root = config_path.resolve().parent.parent
    requested = metadata.get("requested_path")
    candidates: list[Path] = []
    if isinstance(requested, str) and requested:
        requested_path = Path(requested)
        candidates.append(requested_path if requested_path.is_absolute() else workspace_root / requested_path)
    for field in ("resolved_path", "path"):
        value = metadata.get(field)
        if isinstance(value, str) and value:
            candidates.append(Path(value))
    snapshot_path: Path | None = None
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            continue
        if not resolved.is_relative_to(workspace_root):
            continue
        snapshot_path = resolved
        break
    if snapshot_path is None:
        raise ChronicleBuildError("market snapshot path is missing or outside the workspace")

    raw = snapshot_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha:
        raise ChronicleBuildError("market snapshot SHA256 does not match reconstructed replay provenance")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ChronicleBuildError(f"market snapshot is not UTF-8 CSV: {exc}") from exc
    reader = csv.DictReader(text.splitlines())
    if not reader.fieldnames:
        raise ChronicleBuildError("market snapshot CSV header is missing")
    date_field = reader.fieldnames[0]
    series: dict[str, list[list[Any]]] = {name: [] for name in reader.fieldnames[1:] if name}
    row_count = 0
    previous_day: str | None = None
    for row in reader:
        raw_day = row.get(date_field)
        if not isinstance(raw_day, str) or not raw_day:
            continue
        try:
            date.fromisoformat(raw_day)
        except ValueError as exc:
            raise ChronicleBuildError(f"market snapshot contains an invalid date: {raw_day}") from exc
        if previous_day is not None and raw_day <= previous_day:
            raise ChronicleBuildError("market snapshot dates must be strictly increasing and unique")
        previous_day = raw_day
        row_count += 1
        for series_id in series:
            raw_value = row.get(series_id)
            if raw_value in {None, ""}:
                continue
            if not _is_finite_number(raw_value):
                raise ChronicleBuildError(f"market snapshot contains a non-finite value: {series_id} -> {raw_day}")
            series[series_id].append([raw_day, float(str(raw_value))])
    if row_count == 0 or "ACWI" not in series or not series["ACWI"]:
        raise ChronicleBuildError("market snapshot contains no usable ACWI observations")
    return {
        "path": str(snapshot_path),
        "sha256": digest,
        "row_count": row_count,
        "series": series,
    }


def _require_shadow_contract(payload: dict[str, Any], artifact_name: str) -> None:
    decision = payload.get("decision")
    contract = payload.get("contract")
    promotion = decision.get("promotion_allowed") if isinstance(decision, dict) else None
    if payload.get("policy_status") != DIAGNOSTIC_POLICY_STATUS:
        raise ChronicleBuildError(f"{artifact_name} policy_status is not diagnostic-only")
    if payload.get("affects_final_action") is not False:
        raise ChronicleBuildError(f"{artifact_name} affects_final_action is not false")
    if promotion is not False:
        raise ChronicleBuildError(f"{artifact_name} promotion_allowed is not false")
    if isinstance(contract, dict) and contract.get("status") != "pass":
        raise ChronicleBuildError(f"{artifact_name} shadow contract did not pass")


def _validate_publication_pair(payload: dict[str, Any], json_text: str, html_text: str) -> None:
    parsed = json.loads(json_text)
    if parsed.get("schema_version") != SCHEMA_VERSION or parsed.get("status") != "ready":
        raise ChronicleBuildError("generated chronicle JSON did not pass schema identity checks")
    generation_id = str(payload["generation_id"])
    if f'data-generation-id="{generation_id}"' not in html_text:
        raise ChronicleBuildError("generated chronicle HTML does not contain the matching generation_id")
    lowered = html_text.lower()
    forbidden = ("https://", "http://", "//cdn.", "@import url")
    if any(value in lowered for value in forbidden):
        raise ChronicleBuildError("generated chronicle HTML contains a network dependency")


def _publish_pair_atomically(*, json_path: Path, html_path: Path, json_text: str, html_text: str) -> None:
    json_temp = _write_temp(json_path.parent, json_text, ".json.tmp")
    html_temp = _write_temp(html_path.parent, html_text, ".html.tmp")
    json_backup = _backup_if_present(json_path)
    html_backup = _backup_if_present(html_path)
    html_replaced = False
    json_replaced = False
    try:
        os.replace(html_temp, html_path)
        html_replaced = True
        os.replace(json_temp, json_path)
        json_replaced = True
    except Exception:
        _restore_backup(json_path, json_backup, json_replaced)
        json_backup = None
        _restore_backup(html_path, html_backup, html_replaced)
        html_backup = None
        raise
    finally:
        for path in (json_temp, html_temp, json_backup, html_backup):
            if path is not None:
                Path(path).unlink(missing_ok=True)


def _write_temp(directory: Path, text: str, suffix: str) -> str:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory, suffix=suffix, delete=False) as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        return handle.name


def _backup_if_present(path: Path) -> str | None:
    if not path.exists():
        return None
    descriptor, backup_name = tempfile.mkstemp(dir=path.parent, suffix=f"{path.suffix}.bak")
    os.close(descriptor)
    shutil.copy2(path, backup_name)
    return backup_name


def _restore_backup(path: Path, backup: str | None, replaced: bool) -> None:
    if backup is not None:
        os.replace(backup, path)
    elif replaced:
        path.unlink(missing_ok=True)


def _validate_comparison_against_sources(sources: dict[str, dict[str, Any]]) -> None:
    replay = sources["reconstructed_replay"]
    review = sources["replay_review"]
    holdout = sources["holdout_validation"]
    comparison = sources["official_series_regeneration_comparison"]
    compared_replay = (comparison.get("replay") or {}).get("after") or {}
    compared_review = (comparison.get("review") or {}).get("after") or {}
    compared_holdout = (comparison.get("holdout") or {}).get("after") or {}
    production_invariance = comparison.get("production_invariance")
    source_change = comparison.get("source_change")
    if not isinstance(production_invariance, dict) or production_invariance.get("status") != "pass":
        raise ChronicleBuildError("comparison production invariance did not pass")
    if production_invariance.get("same_market_snapshot") is not True:
        raise ChronicleBuildError("comparison does not prove the same market snapshot")
    if not isinstance(source_change, dict):
        raise ChronicleBuildError("comparison source change evidence is missing")
    before_store = source_change.get("before")
    after_store = source_change.get("after")
    if not isinstance(before_store, dict) or before_store.get("loaded") is not True:
        raise ChronicleBuildError("comparison before official-series store was not loaded")
    if not isinstance(after_store, dict) or after_store.get("loaded") is not True:
        raise ChronicleBuildError("comparison after official-series store was not loaded")
    current_replay_hash = hashlib.sha256(
        json.dumps(replay.get("cases") or [], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if compared_replay.get("replay_hash") != current_replay_hash:
        raise ChronicleBuildError("comparison replay hash does not match the current replay")
    events = review.get("events") or review.get("episodes") or []
    if compared_review.get("weekly_timeline_count") != len(review.get("weekly_timeline") or []):
        raise ChronicleBuildError("comparison review timeline count does not match current review")
    if compared_review.get("episode_count") != len(events):
        raise ChronicleBuildError("comparison review event count does not match current review")
    holdout_count = (holdout.get("holdout") or {}).get("case_count")
    if compared_holdout.get("holdout_weekly_case_count") != holdout_count:
        raise ChronicleBuildError("comparison holdout count does not match current holdout")


@contextmanager
def _generation_lock(path: Path) -> Iterator[None]:
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise ChronicleBusyError(f"chronicle generator is already active: {path}") from error
    try:
        os.write(descriptor, f"pid={os.getpid()}\n".encode())
        os.close(descriptor)
        descriptor = -1
        yield
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        path.unlink(missing_ok=True)


def _is_current_ready_output(json_path: Path, html_path: Path, fingerprint: str) -> bool:
    if not json_path.exists() or not html_path.exists():
        return False
    try:
        json_text = json_path.read_text(encoding="utf-8")
        html_text = html_path.read_text(encoding="utf-8")
        payload = json.loads(json_text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    identity_matches = (
        isinstance(payload, dict)
        and payload.get("schema_version") == SCHEMA_VERSION
        and payload.get("implementation_version") == IMPLEMENTATION_VERSION
        and payload.get("status") == "ready"
        and payload.get("freshness_status") == "current"
        and payload.get("promotion_allowed") is False
        and payload.get("source_fingerprint") == fingerprint
        and payload.get("page_filename") == PAGE_FILENAME
    )
    if not identity_matches:
        return False
    try:
        _require_shadow_contract(payload, "episode_chronicle")
        _validate_publication_pair(payload, json_text, html_text)
    except (ChronicleBuildError, KeyError, TypeError, ValueError):
        return False
    return True


def _dict_rows(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ChronicleBuildError(f"{label} must be a list")
    if any(not isinstance(row, dict) for row in value):
        raise ChronicleBuildError(f"{label} must contain only objects")
    return list(value)


def _unique_map(rows: list[dict[str, Any]], field: str, label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _required_text(row, field)
        if key in result:
            raise ChronicleBuildError(f"duplicate {label} {field}: {key}")
        result[key] = row
    return result


def _required_text(row: dict[str, Any], field: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value:
        raise ChronicleBuildError(f"required field is missing: {field}")
    return value


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _valid_dates(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        try:
            date.fromisoformat(value[:10])
        except ValueError:
            continue
        result.append(value[:10])
    return result


def _counts(values: Iterator[str] | Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        key = str(value)
        result[key] = result.get(key, 0) + 1
    return result


def _coverage_summary(statuses: list[str]) -> str:
    if not statuses:
        return "unknown"
    return "complete" if all(value in {"primary", "primary_available", "available"} for value in statuses) else "limited"


def _evaluation_comment(classification: str, maturity: str) -> str:
    if maturity == "pending":
        return "このエピソードは進行中です。評価期間が満了するまで確定評価には含めません。"
    comments = {
        "protective": "警戒段階が重大下落より前に確認され、防御行動の余地が記録されました。",
        "over_warning": "警戒は発生しましたが、評価期間内に重大下落へ進みませんでした。",
        "late_confirmation": "警戒候補は観測されましたが、確認段階への移行が遅れました。",
        "missed_risk": "重大下落に対して十分な警戒確認が記録されませんでした。",
        "ambiguous": "データまたは局面の重なりにより単一の評価へ確定できません。",
        "insufficient_outcome": "評価期間が不足しているため確定評価を保留します。",
    }
    return comments.get(classification, "記録された証拠に基づく診断評価です。")


def _japanese_date(value: str) -> str:
    parsed = date.fromisoformat(value[:10])
    return f"{parsed.year}年{parsed.month}月{parsed.day}日"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the read-only risk_engine_v2 episode chronicle.")
    parser.add_argument("--reports-dir", default="project/reports")
    parser.add_argument("--config", default="project/config.yaml")
    parser.add_argument("--as-of", default=date.today().isoformat())
    parser.add_argument("--max-age-days", type=int, default=3)
    args = parser.parse_args()
    print(
        json.dumps(
            run_risk_engine_v2_episode_chronicle(
                reports_dir=args.reports_dir,
                config_path=args.config,
                as_of=args.as_of,
                max_age_days=args.max_age_days,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
