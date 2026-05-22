from __future__ import annotations

from typing import Any

from project.action_schema import action_rank

NOTE_ONLY_FLAGS = {"japan_fx_risk_caution", "foreign_asset_fx_dependency"}
SOFT_CAP_FLAGS = {"foreign_asset_fx_headwind", "japan_fx_risk_moderate"}
HARD_CAP_FLAGS = {"japan_fx_risk_high", "fx_shock"}


def classify_fx_policy(japan_risk: dict[str, Any] | None, blocker_assessment: dict[str, Any] | None = None) -> dict[str, Any]:
    flags = _collect_fx_flags(japan_risk, blocker_assessment)
    severity = "none"
    cap = "buy_window"
    affects = False
    if flags & HARD_CAP_FLAGS:
        severity = "hard_cap"
        cap = "watch"
        affects = True
    elif flags & SOFT_CAP_FLAGS:
        severity = "soft_cap"
        cap = "buy_candidate"
        affects = True
    elif flags & NOTE_ONLY_FLAGS:
        severity = "note_only"
    note = _execution_note(severity, flags)
    return {
        "fx_policy_classification": severity,
        "fx_action_cap": cap,
        "fx_execution_note": note,
        "affects_final_action": affects,
        "flags": sorted(flags),
    }


def apply_fx_policy_candidate(action: str, classification: dict[str, Any], candidate: str) -> dict[str, Any]:
    severity = str(classification.get("fx_policy_classification", "none"))
    flags = set(str(flag) for flag in classification.get("flags", []))
    final = action
    note = classification.get("fx_execution_note", "")
    if candidate == "current":
        return {"final_action": action, "execution_note": note, "changed": False}
    if candidate == "fx_note_only":
        return {"final_action": action, "execution_note": note, "changed": False}
    if candidate == "fx_soft_cap":
        if severity == "hard_cap":
            final = _cap_action(action, "watch")
        elif severity == "soft_cap":
            final = _cap_action(action, "buy_candidate")
    elif candidate == "fx_high_only_block":
        if flags & HARD_CAP_FLAGS:
            final = _cap_action(action, "watch")
    else:
        raise ValueError(f"unknown FX policy candidate: {candidate}")
    return {"final_action": final, "execution_note": note, "changed": final != action}


def _collect_fx_flags(japan_risk: dict[str, Any] | None, blocker_assessment: dict[str, Any] | None) -> set[str]:
    flags = set(str(flag) for flag in (japan_risk or {}).get("flags", []))
    flags.update(str(flag) for flag in (blocker_assessment or {}).get("flags", []))
    level = str((japan_risk or {}).get("level", ""))
    if level == "moderate":
        flags.add("japan_fx_risk_moderate")
    if level == "high":
        flags.add("japan_fx_risk_high")
    return flags & (NOTE_ONLY_FLAGS | SOFT_CAP_FLAGS | HARD_CAP_FLAGS)


def _cap_action(action: str, cap: str) -> str:
    return cap if action_rank(action) > action_rank(cap) else action


def _execution_note(severity: str, flags: set[str]) -> str:
    if severity == "hard_cap":
        return "FX risk is high; keep buy_candidate/buy_window capped to watch or below."
    if severity == "soft_cap":
        return "FX headwind is present; treat buy_window as staged buy_candidate until yen impact is clearer."
    if severity == "note_only":
        return "FX caution is present; keep action but use smaller, staged execution and confirm yen impact."
    return ""
