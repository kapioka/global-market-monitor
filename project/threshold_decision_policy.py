from __future__ import annotations

from typing import Any


def build_threshold_usage(
    certainty: dict[str, Any],
    proposed_metadata: dict[str, Any] | None = None,
    rule_certification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    proposed = certainty.get("proposed", {})
    candidate = certainty.get("candidate_v2", {})
    certified_sets = []
    blocking_reasons = [
        "Proposed/candidate thresholds lack completed forward-return evidence and overblock watch cases.",
    ]
    if _is_certified(candidate):
        certified_sets.append("candidate_v2")
        blocking_reasons = []
    return {
        "operational_set": "active",
        "diagnostic_sets": ["proposed", "candidate_v2"],
        "certified_sets": certified_sets,
        "proposed_status": "hold" if not _is_certified(proposed) else "certified",
        "candidate_v2_status": "diagnostic_only" if not _is_certified(candidate) else "certified",
        "affects_final_action": "partial" if certified_sets else False,
        "certification_reasons": [] if not certified_sets else ["candidate_v2 passed certification policy"],
        "blocking_reasons": blocking_reasons,
        "active_thresholds_changed": False,
        "proposed_metadata_counts": (proposed_metadata or {}).get("counts", {}),
        "eligible_for_final_action": False,
        "eligible_for_future_final_action": bool((rule_certification or {}).get("certified_rules")),
        "currently_affects_final_action": False,
    }


def _is_certified(certainty_row: dict[str, Any]) -> bool:
    return certainty_row.get("level") in {"high", "medium"} and not certainty_row.get("blocking_reasons")
