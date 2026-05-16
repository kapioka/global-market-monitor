from __future__ import annotations

from typing import Any, Mapping


def build_decision_attribution(
    spot_signal: Mapping[str, Any],
    risk_lines: Mapping[str, Any] | None,
    reliability: Mapping[str, Any],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    recovery = spot_signal.get("recovery_evidence", {})
    blocker = spot_signal.get("blocker_assessment", {})
    action_decision = spot_signal.get("action_decision", {})

    recovery_grade = str(recovery.get("grade", "weak"))
    recovery_score = float(recovery.get("score", 0.0) or 0.0)
    if recovery_grade in {"building", "confirmed"}:
        entries.append(
            {
                "source": "recovery_evidence",
                "effect": "promote",
                "strength": round(recovery_score, 4),
                "reason": f"recovery_{recovery_grade}",
            }
        )

    blocker_level = str(blocker.get("level", "none"))
    if blocker_level in {"caution", "block"}:
        entries.append(
            {
                "source": "blocker_assessment",
                "effect": "block" if blocker_level == "block" else "caution",
                "strength": 1.0 if blocker_level == "block" else 0.5,
                "reason": blocker_level,
            }
        )

    risk_lines = risk_lines or {}
    stage_key = str(risk_lines.get("stage_key", "normal"))
    if stage_key not in {"normal", ""}:
        entries.append(
            {
                "source": "risk_lines",
                "effect": "block" if stage_key in {"danger_line_reached", "extreme_danger_line_reached"} else "caution",
                "strength": round(float(risk_lines.get("penalty_hint", 0.0) or 0.0), 4),
                "reason": stage_key,
            }
        )

    if action_decision.get("reliability_cap_applied"):
        cap_reasons = action_decision.get("cap_reason", []) or reliability.get("blocking_reasons", []) or reliability.get("degrade_reasons", [])
        entries.append(
            {
                "source": "reliability_policy",
                "effect": "cap",
                "strength": 1.0,
                "reason": ",".join(str(reason) for reason in cap_reasons) or str(reliability.get("reason_code", "reliability_cap")),
            }
        )

    return entries
