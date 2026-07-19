from __future__ import annotations

from copy import deepcopy
from typing import Any

DIAGNOSTIC_POLICY_STATUS = "diagnostic_only_not_promoted"


def attach_shadow_diagnostic_contract(payload: dict[str, Any], *, artifact_type: str) -> dict[str, Any]:
    """Attach and enforce the risk_engine_v2 shadow-mode output contract."""
    updated = deepcopy(payload)
    violations = _shadow_diagnostic_violations(updated, artifact_type=artifact_type)
    if violations:
        raise ValueError("risk_engine_v2 shadow diagnostic contract violation: " + "; ".join(violations))
    updated["contract"] = {
        "status": "pass",
        "artifact_type": artifact_type,
        "policy_status": DIAGNOSTIC_POLICY_STATUS,
        "affects_final_action": False,
        "promotion_allowed": False,
    }
    return updated


def _shadow_diagnostic_violations(payload: dict[str, Any], *, artifact_type: str) -> list[str]:
    violations: list[str] = []
    if payload.get("policy_status") != DIAGNOSTIC_POLICY_STATUS:
        violations.append("policy_status must be diagnostic_only_not_promoted")
    if payload.get("affects_final_action") is not False:
        violations.append("affects_final_action must be false")
    decision = payload.get("decision")
    if isinstance(decision, dict) and decision.get("promotion_allowed") is not False:
        violations.append("decision.promotion_allowed must be false")
    replay_type = str(payload.get("replay_type") or payload.get("source_replay_type") or "")
    if artifact_type in {"replay", "reconstructed_replay", "review", "holdout_validation"} and replay_type and not replay_type.endswith(
        "_shadow"
    ):
        violations.append("replay type must remain shadow")
    if artifact_type == "reconstructed_replay":
        reconstruction = payload.get("reconstruction")
        if not isinstance(reconstruction, dict) or reconstruction.get("history_files_modified") is not False:
            violations.append("reconstructed replay must not modify saved history files")
    return violations
