from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project.config_loader import load_config


SCENARIOS: dict[str, dict[str, float]] = {
    "current": {},
    "lighter": {
        "penalty_transition": 0.02,
        "penalty_risk_off": 0.06,
        "penalty_risk_off_relief": 0.02,
        "penalty_risk_off_relief_score_min": 0.47,
        "penalty_credit_stress_moderate": 0.1,
        "penalty_credit_stress_severe": 0.14,
        "penalty_credit_stress": 0.14,
        "penalty_inflation_shock_oil_only": 0.05,
        "penalty_inflation_shock_broad": 0.08,
        "penalty_inflation_shock": 0.08,
        "penalty_stagflation_warning": 0.16,
    },
    "heavier": {
        "penalty_transition": 0.04,
        "penalty_risk_off": 0.1,
        "penalty_risk_off_relief": 0.04,
        "penalty_risk_off_relief_score_min": 0.52,
        "penalty_credit_stress_moderate": 0.18,
        "penalty_credit_stress_severe": 0.22,
        "penalty_credit_stress": 0.22,
        "penalty_inflation_shock_oil_only": 0.1,
        "penalty_inflation_shock_broad": 0.15,
        "penalty_inflation_shock": 0.15,
        "penalty_stagflation_warning": 0.24,
    },
}


def build_penalty_calibration_report(config_path: str | Path) -> dict[str, Any]:
    config = load_config(config_path)
    history_dir = Path(config["paths"]["reports_dir"]) / "history"
    history_entries = _load_history_entries(history_dir)
    deduped_entries = _dedupe_entries_by_day(history_entries)
    thresholds = config["thresholds"]

    return {
        "history_count": len(history_entries),
        "deduped_history_count": len(deduped_entries),
        "datasets": {
            "all_history": _summarize_dataset(history_entries, thresholds),
            "daily_latest": _summarize_dataset(deduped_entries, thresholds),
        },
        "baseline_thresholds": {
            key: thresholds.get(key)
            for key in [
                "spot_score_buy",
                "spot_score_watch",
                "penalty_transition",
                "penalty_risk_off",
                "penalty_risk_off_relief",
                "penalty_risk_off_relief_score_min",
                "penalty_credit_stress_moderate",
                "penalty_credit_stress_severe",
                "penalty_credit_stress",
                "penalty_inflation_shock_oil_only",
                "penalty_inflation_shock_broad",
                "penalty_inflation_shock",
                "penalty_stagflation_warning",
            ]
        },
    }


def write_penalty_calibration_report(config_path: str | Path) -> tuple[Path, Path]:
    config = load_config(config_path)
    reports_dir = Path(config["paths"]["reports_dir"])
    report = build_penalty_calibration_report(config_path)
    json_path = reports_dir / "penalty_calibration.json"
    md_path = reports_dir / "penalty_calibration.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_penalty_calibration_markdown(report), encoding="utf-8")
    return json_path, md_path


def render_penalty_calibration_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Penalty Calibration",
        "",
        f"- 対象履歴件数: {report['history_count']}",
        f"- 日次圧縮後件数: {report['deduped_history_count']}",
        "",
        "## 基準しきい値",
    ]
    for key, value in report["baseline_thresholds"].items():
        lines.append(f"- {key}: {value}")

    for dataset_name, dataset in report["datasets"].items():
        lines.extend(["", f"## {dataset_name}", f"- 件数: {dataset['count']}"])
        for scenario_name, summary in dataset["scenarios"].items():
            lines.extend(
                [
                    "",
                    f"### {scenario_name}",
                    f"- buy_window: {summary['action_counts']['buy_window']}",
                    f"- watch: {summary['action_counts']['watch']}",
                    f"- wait: {summary['action_counts']['wait']}",
                    f"- 平均合成スコア: {summary['average_total_score']}",
                    f"- 平均判定用スコア: {summary['average_adjusted_score']}",
                    f"- 平均レジーム減点: {summary['average_penalty']}",
                    "- レジーム別件数:",
                ]
            )
            for regime_label, count in summary["regime_counts"].items():
                lines.append(f"  - {regime_label}: {count}")
            relief_cases = summary.get("risk_off_relief_cases", [])
            if relief_cases:
                lines.append("- risk_off 救済ケース:")
                for case in relief_cases:
                    lines.append(
                        f"  - {case['generated_at']}: total={case['total_score']} / penalty={case['penalty']} / adjusted={case['adjusted_score']} / action={case['action']}"
                    )
    return "\n".join(lines) + "\n"


def _load_history_entries(history_dir: Path) -> list[dict[str, Any]]:
    if not history_dir.exists():
        return []
    entries: list[dict[str, Any]] = []
    for file_path in sorted(history_dir.glob("report_*.json")):
        entries.append(json.loads(file_path.read_text(encoding="utf-8")))
    return entries


def _dedupe_entries_by_day(history_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_day: dict[str, dict[str, Any]] = {}
    for entry in history_entries:
        generated_at = str(entry.get("generated_at", ""))
        day_key = generated_at[:10]
        if not day_key:
            continue
        current = by_day.get(day_key)
        if current is None or generated_at > str(current.get("generated_at", "")):
            by_day[day_key] = entry
    return [by_day[key] for key in sorted(by_day)]


def _summarize_dataset(history_entries: list[dict[str, Any]], thresholds: dict[str, float]) -> dict[str, Any]:
    scenario_summaries: dict[str, Any] = {}
    for name, overrides in SCENARIOS.items():
        effective_thresholds = dict(thresholds)
        effective_thresholds.update(overrides)
        scenario_summaries[name] = _summarize_scenario(history_entries, effective_thresholds)
    return {
        "count": len(history_entries),
        "scenarios": scenario_summaries,
    }


def _summarize_scenario(history_entries: list[dict[str, Any]], thresholds: dict[str, float]) -> dict[str, Any]:
    action_counts = {"buy_window": 0, "watch": 0, "wait": 0}
    regime_counts: dict[str, int] = {}
    total_scores: list[float] = []
    adjusted_scores: list[float] = []
    penalties: list[float] = []
    risk_off_relief_cases: list[dict[str, Any]] = []

    for entry in history_entries:
        generated_at = str(entry.get("generated_at", ""))
        total_score = float(entry.get("score", {}).get("total_score", 0.0) or 0.0)
        regime = entry.get("regime", {})
        regime_label = str(regime.get("regime_label", "unknown"))
        penalty = _regime_penalty(regime, total_score, thresholds)
        adjusted_score = max(total_score - penalty, 0.0)
        action = _action_for_adjusted_score(adjusted_score, regime_label, thresholds)

        total_scores.append(total_score)
        adjusted_scores.append(adjusted_score)
        penalties.append(penalty)
        action_counts[action] = action_counts.get(action, 0) + 1
        regime_counts[regime_label] = regime_counts.get(regime_label, 0) + 1
        if _is_risk_off_relief_case(regime_label, total_score, thresholds):
            risk_off_relief_cases.append(
                {
                    "generated_at": generated_at,
                    "total_score": round(total_score, 4),
                    "penalty": round(penalty, 4),
                    "adjusted_score": round(adjusted_score, 4),
                    "action": action,
                }
            )

    return {
        "action_counts": action_counts,
        "regime_counts": regime_counts,
        "average_total_score": round(_average(total_scores), 4),
        "average_adjusted_score": round(_average(adjusted_scores), 4),
        "average_penalty": round(_average(penalties), 4),
        "risk_off_relief_cases": risk_off_relief_cases,
    }


def _regime_penalty(regime: dict[str, Any], total_score: float, thresholds: dict[str, float]) -> float:
    regime_label = str(regime.get("regime_label", ""))
    credit_flag = str(regime.get("credit_regime_flag", ""))
    inflation_flag = str(regime.get("inflation_regime_flag", ""))
    if _is_risk_off_relief_case(regime_label, total_score, thresholds):
        return float(thresholds.get("penalty_risk_off_relief", 0.02))
    if credit_flag == "credit_stress_severe":
        return float(thresholds.get("penalty_credit_stress_severe", thresholds.get("penalty_credit_stress", 0.18)))
    if credit_flag == "credit_stress_moderate":
        return float(thresholds.get("penalty_credit_stress_moderate", thresholds.get("penalty_credit_stress", 0.18)))
    if inflation_flag == "inflation_shock_broad":
        return float(thresholds.get("penalty_inflation_shock_broad", thresholds.get("penalty_inflation_shock", 0.12)))
    if inflation_flag == "inflation_shock_oil_only":
        return float(thresholds.get("penalty_inflation_shock_oil_only", thresholds.get("penalty_inflation_shock", 0.12)))
    penalties = {
        "credit_stress": thresholds.get("penalty_credit_stress", 0.18),
        "inflation_shock": thresholds.get("penalty_inflation_shock", 0.12),
        "stagflation_warning": thresholds.get("penalty_stagflation_warning", 0.2),
        "risk_off": thresholds.get("penalty_risk_off", 0.08),
        "early_recovery": 0.0,
        "transition": thresholds.get("penalty_transition", 0.03),
        "risk_on": 0.0,
    }
    return float(penalties.get(regime_label, 0.0))


def _is_risk_off_relief_case(regime_label: str, total_score: float, thresholds: dict[str, float]) -> bool:
    return regime_label == "risk_off" and total_score >= thresholds.get("penalty_risk_off_relief_score_min", 0.47)


def _action_for_adjusted_score(adjusted_score: float, regime_label: str, thresholds: dict[str, float]) -> str:
    if adjusted_score >= thresholds["spot_score_buy"] and regime_label not in {"risk_off", "credit_stress", "stagflation_warning"}:
        return "buy_window"
    if adjusted_score >= thresholds["spot_score_watch"]:
        return "watch"
    return "wait"


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
