from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from project.action_validation import (
    HORIZONS_DAYS,
    _forward_return,
    _max_drawdown_between,
    _normalize_prices,
    _price_at_or_after,
)
from project.config_loader import load_config
from project.oil_context import attach_oil_context_to_rows, build_oil_context
from project.risk_domain_state import apply_risk_domain_persistence
from project.risk_domains import evaluate_risk_domains
from project.risk_engine_v2_contract import attach_shadow_diagnostic_contract


def build_risk_engine_v2_replay(
    history_entries: list[dict[str, Any]],
    config: dict[str, Any],
    price_points: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    state: dict[str, Any] = {"schema_version": "2.0", "domains": {}, "global": {}}
    settings = config.get("risk_engine_v2", {}) if isinstance(config, dict) else {}
    for entry in sorted(history_entries, key=lambda item: str(item.get("generated_at", ""))):
        risk_monitor = list(entry.get("risk_monitor") or [])
        if not risk_monitor:
            cases.append(_unavailable_case(entry, "risk_monitor missing"))
            continue
        oil_context = build_oil_context(risk_monitor, settings=settings)
        risk_monitor = attach_oil_context_to_rows(risk_monitor, oil_context)
        domains = evaluate_risk_domains(
            stress_monitor=risk_monitor,
            credit_monitor=list(entry.get("credit_monitor") or []),
            inflation_monitor=list(entry.get("inflation_monitor") or []),
            config=config,
        )
        domains, state = apply_risk_domain_persistence(
            domains,
            previous_state=state,
            settings=settings,
            generated_at=str(entry.get("generated_at", "")) or None,
        )
        case = _case(entry, oil_context, domains)
        case["outcome"] = _outcome_for_case(case, price_points or [])
        cases.append(case)
    summary = _summary(cases)
    outcome_summary = _outcome_summary(cases)
    summary["outcome_summary"] = outcome_summary
    payload = {
        "status": "ok" if cases else "missing_history",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "replay_type": "risk_engine_v2_shadow",
        "summary": summary,
        "decision": _decision(summary, outcome_summary),
        "cases": cases,
    }
    return attach_shadow_diagnostic_contract(payload, artifact_type="replay")


def render_risk_engine_v2_replay_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    decision = payload.get("decision", {})
    outcome_summary = summary.get("outcome_summary") or {}
    lines = [
        "# risk_engine_v2 replay",
        "",
        "This replay is diagnostic only. It does not change final_action or buy_readiness_score.",
        "",
        "## Summary",
        "",
        f"- status: {payload.get('status', '-')}",
        f"- policy_status: {payload.get('policy_status', '-')}",
        f"- total_cases: {summary.get('total_cases', 0)}",
        f"- strict_available_cases: {summary.get('strict_available_cases', 0)}",
        f"- domain_stage_counts: {summary.get('domain_stage_counts', {})}",
        f"- confirmed_stage_counts: {summary.get('confirmed_stage_counts', {})}",
        f"- legacy_stage_counts: {summary.get('legacy_stage_counts', {})}",
        f"- legacy_domain_stage_divergence_count: {summary.get('legacy_domain_stage_divergence_count', 0)}",
        f"- oil_status_counts: {summary.get('oil_status_counts', {})}",
        f"- oil_reference_only_count: {summary.get('oil_reference_only_count', 0)}",
        f"- outcome_status: {outcome_summary.get('status', '-')}",
        f"- outcome_case_status_counts: {outcome_summary.get('case_status_counts', {})}",
        f"- outcome_usable_cases: {outcome_summary.get('usable_cases', 0)}",
        "",
        "## Decision",
        "",
        f"- promotion_allowed: {decision.get('promotion_allowed', False)}",
        f"- reason: {decision.get('reason', '-')}",
        "",
        "## Recent cases",
        "",
    ]
    for case in list(payload.get("cases") or [])[-10:]:
        lines.append(
            "- {date}: legacy={legacy} / candidate={candidate} / confirmed={confirmed} / oil={oil} / strict={strict}".format(
                date=case.get("date", "-"),
                legacy=case.get("legacy_stage", "-"),
                candidate=case.get("domain_candidate_stage", "-"),
                confirmed=case.get("domain_confirmed_stage", "-"),
                oil=case.get("oil_status", "-"),
                strict=case.get("strict_judgement_available", False),
            )
        )
    return "\n".join(lines) + "\n"


def write_risk_engine_v2_replay(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "risk_engine_v2_replay.json"
    markdown_path = reports_path / "risk_engine_v2_replay.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_risk_engine_v2_replay_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def run_risk_engine_v2_replay(
    config_path: str | Path = "project/config.yaml",
    history_dir: str | Path | None = None,
    reports_dir: str | Path | None = None,
    price_points_json: str | Path | None = None,
    max_history: int | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    reports_path = Path(reports_dir or config["paths"]["reports_dir"])
    history_path = Path(history_dir or (reports_path / "history"))
    entries = _load_history_entries(history_path)
    if max_history is not None:
        entries = entries[-max_history:]
    price_path = Path(price_points_json) if price_points_json else reports_path / "validation_prices.json"
    price_points = _load_price_points(price_path)
    payload = build_risk_engine_v2_replay(entries, config, price_points=price_points)
    json_path, markdown_path = write_risk_engine_v2_replay(payload, reports_path)
    return {
        "status": payload.get("status"),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "total_cases": payload.get("summary", {}).get("total_cases", 0),
        "policy_status": payload.get("policy_status"),
        "affects_final_action": payload.get("affects_final_action"),
        "decision": payload.get("decision", {}),
        "price_points_json": str(price_path),
        "outcome_status": payload.get("summary", {}).get("outcome_summary", {}).get("status"),
    }


def _case(entry: dict[str, Any], oil_context: dict[str, Any], domains: dict[str, Any]) -> dict[str, Any]:
    generated_at = str(entry.get("generated_at", ""))
    legacy = entry.get("risk_lines", {}) if isinstance(entry.get("risk_lines"), dict) else {}
    return {
        "date": generated_at[:10],
        "generated_at": generated_at,
        "source_history": entry.get("_source_file"),
        "final_action": ((entry.get("buy_decision_card") or {}).get("final_action") or (entry.get("spot_signal") or {}).get("action")),
        "legacy_stage": legacy.get("stage_key", "normal"),
        "legacy_composite_score": legacy.get("composite_risk_score"),
        "domain_candidate_stage": domains.get("candidate_stage"),
        "domain_confirmed_stage": domains.get("confirmed_stage"),
        "domain_composite_score": domains.get("composite_domain_score"),
        "domain_persistence_entry_rule": domains.get("entry_rule"),
        "domain_persistence_gap_reset": domains.get("gap_reset", False),
        "domain_persistence_gap_days": domains.get("gap_days"),
        "domain_persistence_episode_id": domains.get("episode_id"),
        "strict_judgement_available": domains.get("strict_judgement_available", False),
        "eligible_domain_coverage": domains.get("eligible_domain_coverage"),
        "independent_stressed_domain_count": domains.get("independent_stressed_domain_count", 0),
        "oil_status": oil_context.get("overall_status"),
        "oil_inflation_pressure_score": oil_context.get("inflation_pressure_score"),
        "oil_demand_collapse_score": oil_context.get("demand_collapse_score"),
        "oil_risk_signal_allowed": oil_context.get("risk_signal_allowed", False),
        "quality_flags": _domain_quality_flags(domains),
        "limitations": list(domains.get("limitations") or []),
        "primary_coverage": entry.get("primary_coverage") or (entry.get("reconstruction") or {}).get("primary_coverage") or {},
        "domain_evidence_schema_version": "risk_engine_v2.domain_evidence.v1",
        "domain_evidence": _domain_evidence(
            domains, entry.get("primary_coverage") or (entry.get("reconstruction") or {}).get("primary_coverage") or {}
        ),
        "global_policy_evidence": _global_policy_evidence(domains),
    }


def _unavailable_case(entry: dict[str, Any], reason: str) -> dict[str, Any]:
    generated_at = str(entry.get("generated_at", ""))
    return {
        "date": generated_at[:10],
        "generated_at": generated_at,
        "source_history": entry.get("_source_file"),
        "status": "unavailable",
        "reason": reason,
        "legacy_stage": (entry.get("risk_lines") or {}).get("stage_key", "normal"),
        "domain_candidate_stage": "unavailable",
        "domain_confirmed_stage": "unavailable",
        "strict_judgement_available": False,
        "oil_status": "unavailable",
        "oil_risk_signal_allowed": False,
    }


def _summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [case for case in cases if case.get("domain_candidate_stage") not in {None, "unavailable"}]
    divergence = [case for case in eligible if _normalize_legacy_stage(case.get("legacy_stage")) != case.get("domain_confirmed_stage")]
    return {
        "total_cases": len(cases),
        "eligible_cases": len(eligible),
        "strict_available_cases": sum(1 for case in cases if case.get("strict_judgement_available")),
        "persistence_gap_reset_count": sum(1 for case in cases if case.get("domain_persistence_gap_reset")),
        "persistence_gap_reset_rate": (
            round(sum(1 for case in cases if case.get("domain_persistence_gap_reset")) / len(cases), 6) if cases else 0.0
        ),
        "domain_stage_counts": dict(Counter(str(case.get("domain_candidate_stage", "unavailable")) for case in cases)),
        "confirmed_stage_counts": dict(Counter(str(case.get("domain_confirmed_stage", "unavailable")) for case in cases)),
        "legacy_stage_counts": dict(Counter(str(case.get("legacy_stage", "normal")) for case in cases)),
        "legacy_domain_stage_divergence_count": len(divergence),
        "oil_status_counts": dict(Counter(str(case.get("oil_status", "unavailable")) for case in cases)),
        "oil_reference_only_count": sum(1 for case in cases if not case.get("oil_risk_signal_allowed", False)),
        "final_action_counts": dict(Counter(str(case.get("final_action", "-")) for case in cases)),
    }


def _decision(summary: dict[str, Any], outcome_summary: dict[str, Any] | None = None) -> dict[str, Any]:
    total = int(summary.get("total_cases", 0) or 0)
    strict = int(summary.get("strict_available_cases", 0) or 0)
    outcome_summary = outcome_summary or {}
    if total < 30:
        return {
            "promotion_allowed": False,
            "reason": "insufficient replay history for promotion; keep risk_engine_v2 diagnostic-only",
            "minimum_cases": 30,
            "observed_cases": total,
        }
    if outcome_summary.get("status") != "ok":
        return {
            "promotion_allowed": False,
            "reason": "forward outcome evidence is missing; keep diagnostic-only",
            "outcome_status": outcome_summary.get("status", "missing"),
        }
    if strict / total < 0.8:
        return {
            "promotion_allowed": False,
            "reason": "strict judgement coverage is below 80%; keep diagnostic-only",
            "strict_available_cases": strict,
            "total_cases": total,
        }
    return {
        "promotion_allowed": False,
        "reason": "stage replay exists, but outcome/forward-return calibration is still required before promotion",
        "strict_available_cases": strict,
        "total_cases": total,
    }


def _outcome_for_case(case: dict[str, Any], price_points: list[dict[str, Any]]) -> dict[str, Any]:
    if not price_points:
        return {"status": "missing_price_points", "forward_returns": {}, "max_drawdowns": {}}
    try:
        from datetime import datetime

        generated_at = datetime.fromisoformat(str(case.get("generated_at")))
    except (TypeError, ValueError):
        return {"status": "invalid_case_date", "forward_returns": {}, "max_drawdowns": {}}
    prices = _normalize_prices(price_points)
    current_price = _price_at_or_after(prices, generated_at)
    if current_price is None:
        return {"status": "unaligned_price", "forward_returns": {}, "max_drawdowns": {}}
    forward_returns: dict[str, float | None] = {}
    max_drawdowns: dict[str, float | None] = {}
    drawdown_paths: dict[str, list[dict[str, Any]]] = {}
    for label, days in HORIZONS_DAYS.items():
        future_price = _price_at_or_after(prices, generated_at, offset_days=days)
        forward_returns[label] = _forward_return(current_price["price"], future_price["price"]) if future_price else None
        max_drawdowns[label] = _max_drawdown_between(prices, current_price["date"], future_price["date"]) if future_price else None
        drawdown_paths[label] = (
            _drawdown_path_between(prices, current_price["date"], future_price["date"], current_price["price"]) if future_price else []
        )
    status = "ok" if any(value is not None for value in forward_returns.values()) else "insufficient_forward_prices"
    return {
        "status": status,
        "current_price_date": current_price["date"].date().isoformat(),
        "current_price": current_price["price"],
        "forward_returns": forward_returns,
        "max_drawdowns": max_drawdowns,
        "drawdown_paths": drawdown_paths,
    }


def _drawdown_path_between(prices: list[dict[str, Any]], start: Any, end: Any, anchor_price: float) -> list[dict[str, Any]]:
    path: list[dict[str, Any]] = []
    for point in prices:
        point_date = point["date"]
        if point_date < start or point_date > end:
            continue
        price = float(point["price"])
        path.append(
            {
                "date": point_date.date().isoformat(),
                "price": price,
                "drawdown_from_anchor": round((price / anchor_price) - 1.0, 6) if anchor_price else None,
            }
        )
    return path


def _outcome_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    usable = [case for case in cases if (case.get("outcome") or {}).get("status") == "ok"]
    if not usable:
        statuses = Counter(str((case.get("outcome") or {}).get("status", "missing")) for case in cases)
        return {"status": "missing_outcomes", "case_status_counts": dict(statuses), "horizons": {}}
    by_bucket = {
        "confirmed_warning_or_higher": [
            case for case in usable if str(case.get("domain_confirmed_stage")) in {"warning", "danger", "extreme"}
        ],
        "confirmed_normal": [case for case in usable if str(case.get("domain_confirmed_stage")) == "normal"],
        "oil_demand_watch_or_stress": [case for case in usable if str(case.get("oil_status")) in {"demand_watch", "demand_stress"}],
    }
    return {
        "status": "ok",
        "usable_cases": len(usable),
        "case_status_counts": dict(Counter(str((case.get("outcome") or {}).get("status", "missing")) for case in cases)),
        "buckets": {name: _bucket_outcomes(rows) for name, rows in by_bucket.items()},
    }


def _bucket_outcomes(cases: list[dict[str, Any]]) -> dict[str, Any]:
    horizons: dict[str, Any] = {}
    for horizon in HORIZONS_DAYS:
        returns = [
            float(value) for case in cases if (value := ((case.get("outcome") or {}).get("forward_returns") or {}).get(horizon)) is not None
        ]
        drawdowns = [
            float(value) for case in cases if (value := ((case.get("outcome") or {}).get("max_drawdowns") or {}).get(horizon)) is not None
        ]
        horizons[horizon] = {
            "count": len(returns),
            "mean_return": round(sum(returns) / len(returns), 6) if returns else None,
            "negative_rate": round(sum(1 for value in returns if value < 0) / len(returns), 6) if returns else None,
            "worst_max_drawdown": min(drawdowns) if drawdowns else None,
        }
    return {"case_count": len(cases), "horizons": horizons}


def _normalize_legacy_stage(stage: Any) -> str:
    text = str(stage or "normal")
    if text in {"normal", "none"}:
        return "normal"
    if "extreme" in text:
        return "extreme"
    if "danger" in text or "credit_spillover" in text:
        return "danger"
    if "caution" in text or "warning" in text:
        return "warning"
    return "warning"


def _domain_quality_flags(domains: dict[str, Any]) -> list[str]:
    flags: set[str] = set()
    for domain in domains.get("domains") or []:
        flags.update(str(flag) for flag in domain.get("quality_flags", []) or [])
    return sorted(flags)


def _domain_evidence(domains: dict[str, Any], primary_coverage: dict[str, Any]) -> list[dict[str, Any]]:
    series_entries = primary_coverage.get("series") if isinstance(primary_coverage, dict) else {}
    series_entries = series_entries if isinstance(series_entries, dict) else {}
    rows: list[dict[str, Any]] = []
    for domain in domains.get("domains") or []:
        if not isinstance(domain, dict):
            continue
        domain_id = str(domain.get("domain_id") or "")
        primary_inputs = [str(item) for item in domain.get("primary_inputs", []) or []]
        fallback_inputs = [str(item) for item in domain.get("fallback_inputs", []) or []]
        evidence_rows = list(domain.get("evidence") or [])
        input_observations = _input_observations(evidence_rows, series_entries)
        contributed = bool(domain.get("stage_eligible")) and str(domain.get("candidate_stage") or domain.get("stage")) != "normal"
        suppressed = str(domain.get("candidate_stage") or domain.get("stage")) != "normal" and not contributed
        rows.append(
            {
                "domain_id": domain_id,
                "score_0_100": domain.get("score_0_100"),
                "candidate_stage": domain.get("candidate_stage") or domain.get("stage"),
                "confirmed_stage": domain.get("confirmed_stage") or domain.get("stage"),
                "stage_eligibility": bool(domain.get("stage_eligible", False)),
                "primary_fallback_status": _primary_fallback_status(primary_inputs, fallback_inputs, input_observations, domain),
                "primary_inputs_used": [item for item in primary_inputs if item in input_observations],
                "fallback_inputs_used": [item for item in fallback_inputs if item in input_observations],
                "input_observation_dates": {ticker: row.get("observation_date") for ticker, row in input_observations.items()},
                "input_freshness": {ticker: row.get("freshness_status") for ticker, row in input_observations.items()},
                "confidence": domain.get("confidence"),
                "quality_flags": list(domain.get("quality_flags") or []),
                "reasons": _domain_reasons(domain),
                "limitations": list(domain.get("limitations") or []),
                "contributed_to_global_candidate": contributed,
                "contribution_type": "stressed_domain" if contributed else "none",
                "suppressed_contribution": suppressed,
                "suppression_reason": _suppression_reason(domain, contributed),
            }
        )
    return rows


def _input_observations(evidence_rows: list[Any], series_entries: dict[str, Any]) -> dict[str, dict[str, Any]]:
    observations: dict[str, dict[str, Any]] = {}
    for row in evidence_rows:
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "")
        if not ticker:
            continue
        raw_metadata = row.get("observation_metadata")
        metadata: dict[str, Any] = raw_metadata if isinstance(raw_metadata, dict) else {}
        raw_series = series_entries.get(ticker)
        series: dict[str, Any] = raw_series if isinstance(raw_series, dict) else {}
        observations[ticker] = {
            "observation_date": metadata.get("latest_observation_date") or series.get("observation_date"),
            "freshness_status": series.get("freshness_status") or ("fresh" if "stale" not in row.get("quality_flags", []) else "stale"),
        }
    return observations


def _primary_fallback_status(
    primary_inputs: list[str],
    fallback_inputs: list[str],
    input_observations: dict[str, dict[str, Any]],
    domain: dict[str, Any],
) -> str:
    if str(domain.get("confidence")) == "fallback":
        return "fallback"
    if any(ticker in input_observations for ticker in primary_inputs):
        return "primary"
    if any(ticker in input_observations for ticker in fallback_inputs):
        return "fallback"
    return "unavailable"


def _domain_reasons(domain: dict[str, Any]) -> list[str]:
    reasons = []
    if domain.get("stage_eligible"):
        reasons.append("stage eligible")
    else:
        reasons.append("stage ineligible")
    if domain.get("confidence"):
        reasons.append(f"confidence={domain.get('confidence')}")
    if domain.get("freshness"):
        reasons.append(f"freshness={domain.get('freshness')}")
    return reasons


def _suppression_reason(domain: dict[str, Any], contributed: bool) -> str | None:
    if contributed:
        return None
    if not domain.get("stage_eligible"):
        return "stage ineligible due to quality or coverage"
    if str(domain.get("candidate_stage") or domain.get("stage")) == "normal":
        return None
    return "not counted by global policy"


def _global_policy_evidence(domains: dict[str, Any]) -> dict[str, Any]:
    raw_policy = domains.get("global_stage_policy")
    policy: dict[str, Any] = raw_policy if isinstance(raw_policy, dict) else {}
    qualifying = [
        str(domain.get("domain_id"))
        for domain in domains.get("domains") or []
        if isinstance(domain, dict)
        and domain.get("stage_eligible")
        and str(domain.get("candidate_stage") or domain.get("stage")) != "normal"
    ]
    return {
        "composite_domain_score": domains.get("composite_domain_score"),
        "independent_stressed_domain_count": domains.get("independent_stressed_domain_count", 0),
        "qualifying_stressed_domains": qualifying,
        "critical_combination_result": list(domains.get("critical_combinations") or []),
        "shock_override_result": policy.get("shock_override"),
        "eligible_coverage": domains.get("eligible_domain_coverage"),
        "candidate_stage": domains.get("candidate_stage"),
        "candidate_stage_reason": list(policy.get("reasons") or []),
        "global_policy_caps": list(policy.get("caps") or []),
        "persistence_entry_result": domains.get("entry_rule"),
        "persistence_exit_result": domains.get("exit_rule"),
        "previous_confirmed_stage": domains.get("previous_confirmed_stage"),
        "resulting_confirmed_stage": domains.get("confirmed_stage"),
    }


def _load_history_entries(history_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not history_dir.exists():
        return entries
    for path in sorted(history_dir.glob("report_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            payload["_source_file"] = path.name
            entries.append(payload)
    return entries


def _load_price_points(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, dict):
        points = payload.get("prices", [])
        return list(points) if isinstance(points, list) else []
    return list(payload) if isinstance(payload, list) else []


def main() -> None:
    parser = argparse.ArgumentParser(description="Run diagnostic risk_engine_v2 replay from saved report history.")
    parser.add_argument("--config", default="project/config.yaml")
    parser.add_argument("--history-dir", default=None)
    parser.add_argument("--reports-dir", default=None)
    parser.add_argument("--price-points-json", default=None)
    parser.add_argument("--max-history", type=int, default=None)
    args = parser.parse_args()
    print(
        json.dumps(
            run_risk_engine_v2_replay(
                config_path=args.config,
                history_dir=args.history_dir,
                reports_dir=args.reports_dir,
                price_points_json=args.price_points_json,
                max_history=args.max_history,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
