from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PromotionGateCriteria:
    minimum_total_cases: int = 100
    minimum_primary_strict_cases: int = 80
    minimum_episode_count: int = 30

    def to_dict(self) -> dict[str, int]:
        return {
            "minimum_total_cases": self.minimum_total_cases,
            "minimum_primary_strict_cases": self.minimum_primary_strict_cases,
            "minimum_episode_count": self.minimum_episode_count,
        }


def evaluate_risk_engine_v2_promotion_gate(
    replay_payload: dict[str, Any],
    review_payload: dict[str, Any],
    *,
    holdout_payload: dict[str, Any] | None = None,
    criteria: PromotionGateCriteria | None = None,
) -> dict[str, Any]:
    gate_criteria = criteria or PromotionGateCriteria()
    raw_replay_summary = replay_payload.get("summary")
    raw_review_counts = review_payload.get("counts")
    replay_summary: dict[str, Any] = raw_replay_summary if isinstance(raw_replay_summary, dict) else {}
    review_counts: dict[str, Any] = raw_review_counts if isinstance(raw_review_counts, dict) else {}
    blockers: list[str] = []
    warnings: list[str] = []

    total_cases = int(replay_summary.get("total_cases", review_payload.get("case_count", 0)) or 0)
    primary_strict_cases = int(replay_summary.get("primary_strict_available_cases", 0) or 0)
    strict_primary_available = bool(replay_summary.get("strict_primary_available", False))
    episode_count = int(review_payload.get("episode_count", 0) or 0)
    insufficient_outcomes = int(review_counts.get("insufficient_outcome", 0) or 0)
    raw_episode_maturity = review_payload.get("episode_maturity")
    episode_maturity: dict[str, Any] = raw_episode_maturity if isinstance(raw_episode_maturity, dict) else {}
    pending_episodes = int(episode_maturity.get("pending_episode_count", 0) or 0)
    performance_denominator = int(episode_maturity.get("performance_denominator", episode_count) or 0)

    if replay_payload.get("policy_status") not in {None, "diagnostic_only_not_promoted"}:
        blockers.append("replay policy is not diagnostic-only")
    if review_payload.get("policy_status") != "diagnostic_only_not_promoted":
        blockers.append("review policy is not diagnostic-only")
    if replay_payload.get("affects_final_action") is not False and replay_payload.get("affects_final_action") is not None:
        blockers.append("replay claims final_action impact")
    if review_payload.get("affects_final_action") is not False:
        blockers.append("review claims final_action impact")
    if not strict_primary_available:
        blockers.append("strict primary official-series replay is unavailable")
    if total_cases < gate_criteria.minimum_total_cases:
        blockers.append(f"total replay cases below minimum: {total_cases}/{gate_criteria.minimum_total_cases}")
    if primary_strict_cases < gate_criteria.minimum_primary_strict_cases:
        blockers.append(f"primary strict cases below minimum: {primary_strict_cases}/{gate_criteria.minimum_primary_strict_cases}")
    if episode_count < gate_criteria.minimum_episode_count:
        blockers.append(f"episode count below minimum: {episode_count}/{gate_criteria.minimum_episode_count}")
    holdout_status = _holdout_status(holdout_payload)
    if holdout_payload is None:
        blockers.append("holdout validation has not been run")
    elif holdout_status != "accepted":
        blockers.append(f"holdout validation is not accepted: {holdout_status}")
    if insufficient_outcomes:
        warnings.append(f"episodes with insufficient outcome evidence: {insufficient_outcomes}")
    if pending_episodes:
        warnings.append(f"pending outcome episodes excluded from performance evidence: {pending_episodes}")
    if not blockers:
        blockers.append("manual approval is required before promotion")

    return {
        "status": "blocked" if blockers else "ready_for_manual_review",
        "promotion_allowed": False,
        "policy_status": "diagnostic_only_not_promoted",
        "criteria": gate_criteria.to_dict(),
        "observed": {
            "total_cases": total_cases,
            "strict_primary_available": strict_primary_available,
            "primary_strict_available_cases": primary_strict_cases,
            "episode_count": episode_count,
            "performance_denominator": performance_denominator,
            "pending_outcome_episodes": pending_episodes,
            "insufficient_outcome_episodes": insufficient_outcomes,
            "holdout_status": holdout_status,
        },
        "blockers": blockers,
        "warnings": warnings,
        "reason": blockers[0] if blockers else "manual review required before any promotion",
    }


def _holdout_status(holdout_payload: dict[str, Any] | None) -> str:
    if holdout_payload is None:
        return "not_run"
    if holdout_payload.get("policy_status") != "diagnostic_only_not_promoted":
        return "invalid_policy_status"
    if holdout_payload.get("affects_final_action") is not False:
        return "claims_final_action_impact"
    decision = holdout_payload.get("decision")
    if isinstance(decision, dict) and decision.get("promotion_allowed") is not False:
        return "claims_promotion_allowed"
    return str((holdout_payload.get("holdout") or {}).get("status") or holdout_payload.get("status") or "unknown")
