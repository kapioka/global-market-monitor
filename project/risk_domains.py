from __future__ import annotations

from collections.abc import Sequence
from typing import Any

DOMAIN_ORDER = (
    "equity",
    "equity_volatility",
    "bond_volatility",
    "credit",
    "rates",
    "usd_funding",
    "commodity_inflation",
)

STAGE_RANK = {"normal": 0, "warning": 1, "danger": 2, "extreme": 3}
RANK_STAGE = {value: key for key, value in STAGE_RANK.items()}


def evaluate_risk_domains(
    *,
    stress_monitor: list[dict[str, Any]],
    credit_monitor: list[dict[str, Any]] | None = None,
    inflation_monitor: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
    available_series: set[str] | None = None,
) -> dict[str, Any]:
    settings = (config or {}).get("risk_engine_v2", {}) if isinstance(config, dict) else {}
    weights = dict(settings.get("domain_weights") or _default_domain_weights())
    by_ticker = {str(row.get("ticker")): row for row in stress_monitor}
    by_inflation = {str(row.get("ticker")): row for row in (inflation_monitor or [])}
    by_credit = {str(row.get("ticker")): row for row in (credit_monitor or [])}

    domains = [
        _single_input_domain("equity", [by_ticker.get("SPY")], primary=["SPY"]),
        _single_input_domain("equity_volatility", [by_ticker.get("^VIX")], primary=["^VIX"]),
        _single_input_domain("bond_volatility", [by_ticker.get("^MOVE")], primary=["^MOVE"]),
        _credit_domain(by_ticker, by_credit, available_series or set()),
        _rates_domain(by_ticker),
        _single_input_domain(
            "usd_funding",
            [by_ticker.get("DX-Y.NYB"), by_ticker.get("FRED:NFCI"), by_ticker.get("FRED:ANFCI")],
            primary=["DX-Y.NYB"],
            fallback=["FRED:NFCI", "FRED:ANFCI"],
        ),
        _commodity_domain(by_ticker),
    ]
    domain_map = {domain["domain_id"]: domain for domain in domains}
    corroboration = _gold_corroboration(by_ticker, by_inflation, domain_map)
    eligible = [domain for domain in domains if domain["stage_eligible"]]
    coverage = len(eligible) / len(domains) if domains else 0.0
    composite = _composite_score(domains, weights)
    stressed = [domain for domain in domains if STAGE_RANK.get(str(domain.get("stage")), 0) >= 1 and domain["stage_eligible"]]
    critical = _critical_combinations(domain_map)
    minimum_coverage = float(settings.get("minimum_eligible_domain_coverage", 0.75) or 0.75)
    strict_available = coverage >= minimum_coverage
    global_policy = _global_stage_policy(
        domains,
        composite_score=composite,
        critical=critical,
        settings=settings,
        strict_available=strict_available,
    )
    candidate_rank = int(global_policy["rank"])
    return {
        "schema_version": "2.0",
        "engine_mode": str(settings.get("mode", "shadow") or "shadow"),
        "stage": RANK_STAGE[candidate_rank],
        "candidate_stage": RANK_STAGE[candidate_rank],
        "confirmed_stage": RANK_STAGE[candidate_rank],
        "composite_domain_score": round(composite, 1) if composite is not None else None,
        "eligible_domain_coverage": round(coverage, 4),
        "strict_judgement_available": strict_available,
        "independent_stressed_domain_count": len(stressed),
        "critical_combinations": critical["matches"],
        "global_stage_policy": global_policy,
        "domains": domains,
        "corroborative_evidence": corroboration,
        "limitations": [] if strict_available else ["minimum eligible domain coverage not met"],
    }


def _single_input_domain(
    domain_id: str,
    rows: Sequence[dict[str, Any] | None],
    *,
    primary: list[str],
    fallback: list[str] | None = None,
) -> dict[str, Any]:
    present = [row for row in rows if row]
    if not present:
        return _missing_domain(domain_id, primary=primary, fallback=fallback or [])
    strongest = max(present, key=lambda row: (_stage_rank(row), float(row.get("pressure_score", 0.0) or 0.0)))
    return _domain_payload(
        domain_id,
        score=_domain_score(present),
        stage=str(strongest.get("line_level", "normal")),
        primary_inputs=primary,
        fallback_inputs=fallback or [],
        evidence=_evidence_rows(present),
        confidence=_confidence(present),
        quality_flags=_quality_flags(present),
        limitations=_limitations(present),
    )


def _credit_domain(
    by_ticker: dict[str, dict[str, Any]],
    by_credit: dict[str, dict[str, Any]],
    available_series: set[str],
) -> dict[str, Any]:
    official_oas = ["FRED:BAMLH0A0HYM2", "FRED:BAMLC0A0CM"]
    primary_rows = [by_ticker.get(ticker) for ticker in official_oas]
    primary_present = [row for row in primary_rows if row]
    if primary_present:
        return _single_input_domain("credit", primary_present, primary=official_oas)
    proxy_rows = [by_ticker.get("HYG/LQD") or by_credit.get("HYG/LQD")]
    proxy_present = [row for row in proxy_rows if row]
    if not proxy_present:
        return _missing_domain("credit", primary=official_oas, fallback=["HYG/LQD", "HYG", "LQD"])
    payload = _single_input_domain("credit", proxy_present, primary=official_oas, fallback=["HYG/LQD"])
    payload["confidence"] = "fallback"
    available_official_oas = [ticker for ticker in official_oas if ticker in available_series]
    payload["official_series_availability"] = {
        "available": available_official_oas,
        "missing": [ticker for ticker in official_oas if ticker not in available_series],
        "stage_scored": False,
        "usage": "diagnostic_coverage_only",
    }
    if available_official_oas:
        payload["limitations"].append("official OAS available for diagnostic coverage but not stage-scored; HYG/LQD is the stage proxy")
    else:
        payload["limitations"].append("official OAS unavailable; HYG/LQD is a proxy fallback")
    return payload


def _rates_domain(by_ticker: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return _single_input_domain(
        "rates",
        [
            by_ticker.get("^TNX"),
            by_ticker.get("FRED:DFII10"),
            by_ticker.get("FRED:T10YIE"),
            by_ticker.get("FRED:T10Y2Y"),
            by_ticker.get("FRED:T10Y3M"),
        ],
        primary=["^TNX", "FRED:DFII10", "FRED:T10YIE", "FRED:T10Y2Y"],
        fallback=["FRED:T10Y3M"],
    )


def _commodity_domain(by_ticker: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = [by_ticker.get("CL=F"), by_ticker.get("BZ=F")]
    context = next((row.get("oil_context") for row in rows if row and isinstance(row.get("oil_context"), dict)), None)
    if context:
        payload = _domain_payload(
            "commodity_inflation",
            score=max(
                float(context.get("inflation_pressure_score") or 0.0),
                float(context.get("demand_collapse_score") or 0.0),
            ),
            stage=_stage_from_oil_status(str(context.get("overall_status", "normal"))),
            primary_inputs=["CL=F", "BZ=F"],
            fallback_inputs=[],
            evidence=[
                {
                    "ticker": "oil_context",
                    "stage": str(context.get("overall_status", "normal")),
                    "score_0_100": max(
                        float(context.get("inflation_pressure_score") or 0.0),
                        float(context.get("demand_collapse_score") or 0.0),
                    ),
                    "quality_flags": context.get("quality_flags", ["valid"]),
                    "stage_eligible": bool(context.get("risk_signal_allowed", False)),
                    "inflation_pressure_score": context.get("inflation_pressure_score"),
                    "demand_collapse_score": context.get("demand_collapse_score"),
                    "reason": context.get("reason"),
                }
            ],
            confidence="high" if context.get("risk_signal_allowed") else "low",
            quality_flags=list(context.get("quality_flags", ["valid"])),
            limitations=list(context.get("limitations", [])),
        )
        if any(rows) and len([row for row in rows if row]) > 1:
            payload["limitations"].append("WTI and Brent are capped into one commodity domain vote")
        return payload
    payload = _single_input_domain("commodity_inflation", rows, primary=["CL=F", "BZ=F"])
    if any(rows) and len([row for row in rows if row]) > 1:
        payload["limitations"].append("WTI and Brent are capped into one commodity domain vote")
    return payload


def _stage_from_oil_status(status: str) -> str:
    if status in {"inflation_stress", "demand_stress"}:
        return "danger"
    if status in {"inflation_watch", "demand_watch"}:
        return "warning"
    return "normal"


def _gold_corroboration(
    by_ticker: dict[str, dict[str, Any]],
    by_inflation: dict[str, dict[str, Any]],
    domain_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    gold = by_ticker.get("GC=F") or by_inflation.get("GC=F") or by_ticker.get("GLD") or by_inflation.get("GLD")
    if not gold:
        return []
    gold_return = _first_number(gold, ["return_1w", "change_1w", "return_4w", "change_4w"])
    spy = by_ticker.get("SPY")
    equity_return = _first_number(spy or {}, ["return_1w", "change_1w", "return_4w", "change_4w"])
    rows: list[dict[str, Any]] = []
    if gold_return is not None and gold_return > 0:
        rows.append({"type": "gold_momentum", "stage_effect": "none", "gold_return": gold_return})
    if gold_return is not None and equity_return is not None and gold_return > 0 and equity_return < 0:
        supporting = [
            domain_id
            for domain_id in ("equity_volatility", "credit", "rates")
            if STAGE_RANK.get(str(domain_map.get(domain_id, {}).get("stage")), 0) >= 1
        ]
        if supporting:
            rows.append(
                {
                    "type": "gold_defensive_confirmation",
                    "stage_effect": "corroborative_only",
                    "gold_return": gold_return,
                    "equity_return": equity_return,
                    "supporting_domains": supporting,
                }
            )
    commodity = domain_map.get("commodity_inflation", {})
    if gold_return is not None and gold_return > 0 and STAGE_RANK.get(str(commodity.get("stage")), 0) >= 1:
        rows.append(
            {
                "type": "gold_inflation_confirmation",
                "stage_effect": "corroborative_only",
                "gold_return": gold_return,
                "supporting_domains": ["commodity_inflation"],
            }
        )
    return rows


def _domain_payload(
    domain_id: str,
    *,
    score: float,
    stage: str,
    primary_inputs: list[str],
    fallback_inputs: list[str],
    evidence: list[dict[str, Any]],
    confidence: str,
    quality_flags: list[str],
    limitations: list[str],
) -> dict[str, Any]:
    stage_eligible = not any(flag in {"stale", "source_unavailable", "diagnostic_only"} for flag in quality_flags)
    if not stage_eligible:
        stage = "normal"
    return {
        "domain_id": domain_id,
        "score_0_100": round(score, 1),
        "stage": stage,
        "candidate_stage": stage,
        "confirmed_stage": stage,
        "primary_inputs": primary_inputs,
        "fallback_inputs": fallback_inputs,
        "evidence": evidence,
        "freshness": _freshness_from_flags(quality_flags),
        "confidence": confidence,
        "quality_flags": quality_flags or ["valid"],
        "stage_eligible": stage_eligible,
        "corroborative_evidence": [],
        "limitations": limitations,
        "persistence_count": None,
        "entry_rule": "not_applied_yet",
        "exit_rule": "not_applied_yet",
        "stage_changed": False,
        "previous_stage": None,
    }


def _missing_domain(domain_id: str, *, primary: list[str], fallback: list[str]) -> dict[str, Any]:
    return _domain_payload(
        domain_id,
        score=0.0,
        stage="normal",
        primary_inputs=primary,
        fallback_inputs=fallback,
        evidence=[],
        confidence="none",
        quality_flags=["source_unavailable"],
        limitations=["no eligible domain inputs"],
    )


def _domain_score(rows: list[dict[str, Any]]) -> float:
    return max(float(row.get("pressure_score", 0.0) or 0.0) * 100.0 for row in rows)


def _evidence_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "ticker": row.get("ticker"),
            "stage": row.get("line_level", "normal"),
            "score_0_100": round(float(row.get("pressure_score", 0.0) or 0.0) * 100.0, 1),
            "quality_flags": row.get("quality_flags", ["valid"]),
            "stage_eligible": row.get("stage_eligible", True),
            "observation_metadata": row.get("observation_metadata", {}),
        }
        for row in rows
    ]


def _quality_flags(rows: list[dict[str, Any]]) -> list[str]:
    flags: list[str] = []
    for row in rows:
        flags.extend(str(flag) for flag in row.get("quality_flags", []) or [])
    return sorted(set(flags))


def _limitations(rows: list[dict[str, Any]]) -> list[str]:
    limitations: list[str] = []
    for row in rows:
        limitations.extend(str(item) for item in row.get("limitations", []) or [])
    return sorted(set(limitations))


def _confidence(rows: list[dict[str, Any]]) -> str:
    flags = set(_quality_flags(rows))
    if flags.intersection({"stale", "source_unavailable"}):
        return "low"
    if flags.intersection({"partial", "insufficient_history", "fallback_review"}):
        return "medium"
    return "high"


def _freshness_from_flags(flags: list[str]) -> str:
    if "stale" in flags:
        return "stale"
    if "source_unavailable" in flags:
        return "unavailable"
    return "fresh"


def _stage_rank(row: dict[str, Any]) -> int:
    return STAGE_RANK.get(str(row.get("line_level", "normal")), 0)


def _composite_score(domains: list[dict[str, Any]], weights: dict[str, float]) -> float | None:
    total_weight = 0.0
    weighted = 0.0
    for domain in domains:
        if not domain.get("stage_eligible"):
            continue
        domain_id = str(domain.get("domain_id"))
        weight = float(weights.get(domain_id, 0.0) or 0.0)
        total_weight += weight
        weighted += weight * float(domain.get("score_0_100", 0.0) or 0.0)
    if total_weight <= 0:
        return None
    return weighted / total_weight


def _rank_from_composite(score: float | None) -> int:
    if score is None:
        return 0
    if score >= 80:
        return 3
    if score >= 62:
        return 2
    if score >= 35:
        return 1
    return 0


def _global_stage_policy(
    domains: list[dict[str, Any]],
    *,
    composite_score: float | None,
    critical: dict[str, Any],
    settings: dict[str, Any],
    strict_available: bool,
) -> dict[str, Any]:
    policy_settings = settings.get("global_stage_policy") or {}
    eligible_stressed = [
        domain
        for domain in domains
        if domain.get("stage_eligible") and STAGE_RANK.get(str(domain.get("stage", "normal")), 0) >= STAGE_RANK["warning"]
    ]
    nonfallback_stressed = [domain for domain in eligible_stressed if str(domain.get("confidence")) != "fallback"]
    max_domain_rank = max((STAGE_RANK.get(str(domain.get("stage", "normal")), 0) for domain in eligible_stressed), default=0)
    nonfallback_max_rank = max((STAGE_RANK.get(str(domain.get("stage", "normal")), 0) for domain in nonfallback_stressed), default=0)
    composite_rank = _rank_from_composite(composite_score)
    critical_rank = int(critical.get("rank", 0) or 0)
    shock = _shock_override(domains, policy_settings)
    rank = 0
    reasons: list[str] = []
    if eligible_stressed or composite_rank >= STAGE_RANK["warning"]:
        rank = STAGE_RANK["warning"]
        reasons.append("warning requires at least one stressed domain or composite warning")
    if len(nonfallback_stressed) >= 2 and (
        nonfallback_max_rank >= STAGE_RANK["danger"] or composite_rank >= STAGE_RANK["danger"] or critical_rank >= STAGE_RANK["warning"]
    ):
        rank = max(rank, STAGE_RANK["danger"])
        reasons.append("danger requires at least two non-fallback stressed domains plus danger/composite/critical evidence")
    if len(nonfallback_stressed) >= 3 and nonfallback_max_rank >= STAGE_RANK["extreme"] and composite_rank >= STAGE_RANK["danger"]:
        rank = max(rank, STAGE_RANK["extreme"])
        reasons.append("extreme requires at least three non-fallback stressed domains and high composite stress")
    if shock["rank"] > rank:
        rank = int(shock["rank"])
        reasons.append(f"validated shock override: {shock['reason']}")
    caps: list[str] = []
    if len(eligible_stressed) < 2 and shock["rank"] == 0:
        rank = min(rank, STAGE_RANK["warning"])
        caps.append("single stressed domain capped at warning")
    if eligible_stressed and not nonfallback_stressed:
        rank = min(rank, STAGE_RANK["warning"])
        caps.append("fallback-only stressed evidence capped at warning")
    elif rank >= STAGE_RANK["extreme"] and any(str(domain.get("confidence")) == "fallback" for domain in eligible_stressed):
        rank = STAGE_RANK["danger"]
        caps.append("fallback-supported evidence cannot independently produce extreme")
    if not strict_available:
        rank = min(rank, STAGE_RANK["warning"])
        caps.append("insufficient eligible coverage capped at warning")
    return {
        "rank": rank,
        "stage": RANK_STAGE[rank],
        "independent_stressed_domain_count": len(eligible_stressed),
        "nonfallback_stressed_domain_count": len(nonfallback_stressed),
        "max_domain_rank": max_domain_rank,
        "nonfallback_max_domain_rank": nonfallback_max_rank,
        "composite_rank": composite_rank,
        "critical_rank": critical_rank,
        "shock_override": shock,
        "caps": caps,
        "reasons": reasons or ["no global stress evidence"],
    }


def _shock_override(domains: list[dict[str, Any]], policy_settings: dict[str, Any]) -> dict[str, Any]:
    overrides = policy_settings.get("shock_overrides") or []
    for override in overrides:
        if not bool(override.get("enabled", False)):
            continue
        domain_id = str(override.get("domain_id") or "")
        required_stage = str(override.get("domain_stage_at_least") or "extreme")
        global_stage = str(override.get("global_stage") or "danger")
        reason = str(override.get("reason") or f"{domain_id}:{required_stage}")
        domain = next((item for item in domains if item.get("domain_id") == domain_id), None)
        if not domain or not domain.get("stage_eligible") or str(domain.get("confidence")) == "fallback":
            continue
        if STAGE_RANK.get(str(domain.get("stage", "normal")), 0) >= STAGE_RANK.get(required_stage, 3):
            return {"rank": STAGE_RANK.get(global_stage, 2), "stage": global_stage, "reason": reason}
    return {"rank": 0, "stage": "normal", "reason": None}


def _critical_combinations(domain_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    matches: list[str] = []
    if (
        _at_least(domain_map, "credit", "warning")
        and _at_least(domain_map, "equity_volatility", "warning")
        and _at_least(domain_map, "equity", "warning")
    ):
        matches.append("credit+equity_volatility+equity")
    if _at_least(domain_map, "rates", "warning") and (
        _at_least(domain_map, "equity", "warning") or _at_least(domain_map, "credit", "warning")
    ):
        matches.append("rates+equity_or_credit")
    if (
        _at_least(domain_map, "bond_volatility", "warning")
        and _at_least(domain_map, "rates", "warning")
        and _at_least(domain_map, "credit", "warning")
    ):
        matches.append("bond_volatility+rates+credit")
    rank = 1 if matches else 0
    return {"matches": matches, "rank": rank}


def _at_least(domain_map: dict[str, dict[str, Any]], domain_id: str, stage: str) -> bool:
    return STAGE_RANK.get(str(domain_map.get(domain_id, {}).get("stage")), 0) >= STAGE_RANK[stage]


def _first_number(row: dict[str, Any], names: list[str]) -> float | None:
    for name in names:
        value = row.get(name)
        if isinstance(value, int | float):
            return float(value)
    return None


def _default_domain_weights() -> dict[str, float]:
    return {
        "equity": 0.16,
        "equity_volatility": 0.14,
        "bond_volatility": 0.10,
        "credit": 0.20,
        "rates": 0.16,
        "usd_funding": 0.10,
        "commodity_inflation": 0.14,
    }
