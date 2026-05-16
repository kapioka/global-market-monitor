from __future__ import annotations

from collections import defaultdict
from typing import Any

from project.threshold_metadata import threshold_family

CRITICAL_FAMILIES = {"credit", "volatility", "rates", "equity"}


def apply_candidate_v2_policy(risk_lines: dict[str, Any], previous_stage: str = "normal") -> dict[str, Any]:
    result = dict(risk_lines)
    family_levels = family_severity(result.get("indicators", []))
    reasons: list[str] = []
    if result.get("stage_key") == "extreme_danger_line_reached" and not allows_extreme(family_levels, result, previous_stage):
        result["stage_key"] = "danger_line_reached"
        result["stage_label"] = "危険ライン到達"
        result["penalty_hint"] = min(float(result.get("penalty_hint", 0.08) or 0.08), 0.08)
        result["decision_summary"] = "candidate_v2 policy reduced unsupported extreme stage to danger."
        reasons.append("candidate_v2_multi_family_or_jump_guard")
    result["candidate_v2"] = {
        "family_levels": family_levels,
        "policy_reasons": reasons,
        "diagnostic_only": True,
    }
    return result


def family_severity(indicators: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {"warning": 0, "danger": 0, "extreme": 0, "tickers": []})
    for row in indicators:
        ticker = str(row.get("ticker", ""))
        family = threshold_family(ticker)
        level = str(row.get("line_level", "normal"))
        if level in {"warning", "danger", "extreme"}:
            grouped[family][level] = min(1, int(grouped[family][level]) + 1)
            grouped[family]["tickers"].append(ticker)
    return dict(grouped)


def allows_extreme(family_levels: dict[str, dict[str, Any]], risk_lines: dict[str, Any], previous_stage: str = "normal") -> bool:
    critical_extreme = [
        family for family, levels in family_levels.items() if family in CRITICAL_FAMILIES and int(levels.get("extreme", 0)) > 0
    ]
    critical_danger = [
        family for family, levels in family_levels.items() if family in CRITICAL_FAMILIES and int(levels.get("danger", 0)) > 0
    ]
    family_count = sum(
        1
        for levels in family_levels.values()
        if int(levels.get("warning", 0)) or int(levels.get("danger", 0)) or int(levels.get("extreme", 0))
    )
    score = float(risk_lines.get("composite_risk_score", 0.0) or 0.0)
    if previous_stage == "normal" and len(critical_extreme) < 2 and family_count < 3 and score < 85:
        return False
    if len(critical_extreme) >= 2:
        return True
    if len(critical_extreme) >= 1 and len(set(critical_danger + critical_extreme)) >= 2:
        return True
    return score >= 85 and family_count >= 2
