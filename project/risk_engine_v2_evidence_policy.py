from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

POLICY_VERSION = "risk_engine_v2_evidence_policy.v1"
ENGINE_SCHEMA_VERSION = "2.0"


def build_evidence_policy(*, generated_at: str | None = None) -> dict[str, Any]:
    policy = {
        "policy_version": POLICY_VERSION,
        "engine_schema_version": ENGINE_SCHEMA_VERSION,
        "generated_at": generated_at or datetime.now(UTC).isoformat(timespec="seconds"),
        "primary_domain_groups": [
            {
                "domain_id": "credit",
                "all_of": ["FRED:BAMLH0A0HYM2", "FRED:BAMLC0A0CM"],
                "any_of": [],
                "description": "US credit primary evidence requires both HY and IG OAS.",
            },
            {
                "domain_id": "rates",
                "all_of": ["FRED:DFII10", "FRED:T10YIE"],
                "any_of": [["FRED:T10Y2Y", "FRED:T10Y3M"]],
                "description": "Rates primary evidence requires real yield, breakeven, and one approved curve spread.",
            },
            {
                "domain_id": "usd_funding",
                "all_of": [],
                "any_of": [["FRED:NFCI"]],
                "description": "Funding conditions primary evidence requires NFCI or approved equivalent.",
            },
        ],
        "series": {
            "FRED:BAMLH0A0HYM2": _series_policy("fred", "weekly", 10, 52),
            "FRED:BAMLC0A0CM": _series_policy("fred", "weekly", 10, 52),
            "FRED:DFII10": _series_policy("fred", "business_daily", 10, 52),
            "FRED:T10YIE": _series_policy("fred", "business_daily", 10, 52),
            "FRED:T10Y2Y": _series_policy("fred", "business_daily", 10, 52),
            "FRED:T10Y3M": _series_policy("fred", "business_daily", 10, 52),
            "FRED:NFCI": _series_policy("fred", "weekly", 10, 52),
        },
        "disqualifying_quality_flags": [
            "source_unavailable",
            "stale",
            "insufficient_history",
            "future_observation_excluded",
            "same_observation_comparison",
        ],
        "outcome_maturity": {
            "primary_horizon": "13w",
            "horizon_days": 91,
            "allowed_states": ["mature", "pending", "missing_benchmark_data", "invalid_alignment", "quality_rejected"],
        },
        "quiet_outcome_definition": {
            "requires_mature_outcome": True,
            "max_material_drawdown_4w": -0.08,
            "max_material_drawdown_13w": -0.08,
            "min_material_return_13w": -0.05,
        },
        "performance_denominator_policy": {
            "include_only_mature_quality_valid": True,
            "exclude_pending": True,
            "exclude_missing_benchmark": True,
            "exclude_invalid_alignment": True,
            "minimum_mature_holdout_episodes": 5,
        },
    }
    policy["policy_hash"] = policy_hash(policy)
    return policy


def policy_hash(policy: dict[str, Any]) -> str:
    payload = {key: value for key, value in policy.items() if key not in {"policy_hash", "generated_at"}}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _series_policy(source_type: str, expected_frequency: str, freshness_tolerance_days: int, minimum_history: int) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "expected_frequency": expected_frequency,
        "freshness_tolerance_calendar_days": freshness_tolerance_days,
        "minimum_history": minimum_history,
        "vintage_revision_status": "latest_observation_not_vintage_locked",
        "primary_or_fallback": "primary",
    }
