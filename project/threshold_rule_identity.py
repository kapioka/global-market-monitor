from __future__ import annotations

from typing import Any

from project.threshold_metadata import rule_metadata, threshold_family


def build_rule_id(indicator: str, threshold_type: str) -> str:
    return f"{indicator}:{threshold_type}"


def split_rule_id(rule_id: str) -> tuple[str, str]:
    indicator, separator, threshold_type = rule_id.rpartition(":")
    if not separator or not indicator or not threshold_type:
        raise ValueError(f"invalid threshold rule_id: {rule_id}")
    return indicator, threshold_type


def build_rule_identity(
    indicator: str,
    threshold_type: str,
    *,
    active_rule: dict[str, Any] | None = None,
    proposed_rule: dict[str, Any] | None = None,
    candidate_rule: dict[str, Any] | None = None,
) -> dict[str, Any]:
    source_rule = proposed_rule or active_rule or candidate_rule or {}
    metadata = dict(source_rule.get("metadata") or rule_metadata(indicator, threshold_type, source_rule))
    return {
        "rule_id": build_rule_id(indicator, threshold_type),
        "indicator": indicator,
        "threshold_type": threshold_type,
        "family": metadata.get("family") or threshold_family(indicator),
        "source": metadata.get("source", "not_evaluable"),
        "confidence": metadata.get("confidence", "not_evaluable"),
        "value": source_rule.get("threshold"),
        "active_value": (active_rule or {}).get("threshold"),
        "proposed_value": (proposed_rule or {}).get("threshold"),
        "candidate_value": (candidate_rule or {}).get("threshold"),
        "metadata": metadata,
    }


def identities_from_payloads(
    *,
    active_payload: dict[str, Any] | None = None,
    proposed_payload: dict[str, Any] | None = None,
    candidate_payload: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    active_indicators = (active_payload or {}).get("indicators") or {}
    proposed_indicators = (proposed_payload or {}).get("indicators") or {}
    candidate_indicators = (candidate_payload or {}).get("indicators") or {}
    keys: set[tuple[str, str]] = set()
    for indicators in (active_indicators, proposed_indicators, candidate_indicators):
        for indicator, item in indicators.items():
            for threshold_type in (item or {}).get("thresholds") or {}:
                keys.add((str(indicator), str(threshold_type)))
    rows = []
    for indicator, threshold_type in sorted(keys):
        active_rule = ((active_indicators.get(indicator) or {}).get("thresholds") or {}).get(threshold_type)
        proposed_rule = ((proposed_indicators.get(indicator) or {}).get("thresholds") or {}).get(threshold_type)
        candidate_rule = ((candidate_indicators.get(indicator) or {}).get("thresholds") or {}).get(threshold_type)
        rows.append(
            build_rule_identity(
                indicator,
                threshold_type,
                active_rule=active_rule,
                proposed_rule=proposed_rule,
                candidate_rule=candidate_rule,
            )
        )
    return rows
