from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

CLASSIFICATIONS = ("promising_candidate", "overblocked_by_current", "correctly_blocked", "inconclusive")
NUMERIC_FEATURES = (
    "acwi_return_13w",
    "acwi_spy_relative_13w",
    "hyg_lqd_ratio_return_4w",
    "usdjpy_change_4w",
    "usdjpy_change_13w",
    "vix_level",
    "vix_change_4w",
    "tnx_change_4w",
    "oil_family_return_4w",
    "acwi_drawdown_13w",
)


def build_fx_soft_cap_outcome_analysis(replay_payload: dict[str, Any]) -> dict[str, Any]:
    cases = list(replay_payload.get("cases") or [])
    groups = {classification: [case for case in cases if case.get("classification") == classification] for classification in CLASSIFICATIONS}
    by_classification = {classification: _group_summary(group) for classification, group in groups.items()}
    return {
        "status": "ok",
        "policy_status": "diagnostic_only",
        "total_case_count": len(cases),
        "classification_counts": dict(Counter(str(case.get("classification", "inconclusive")) for case in cases)),
        "by_classification": by_classification,
        "conditional_policy_hints": _policy_hints(by_classification),
    }


def write_fx_soft_cap_outcome_analysis(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "fx_soft_cap_outcome_analysis.json"
    markdown_path = reports_path / "fx_soft_cap_outcome_analysis.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_fx_soft_cap_outcome_analysis_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_fx_soft_cap_outcome_analysis_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# fx_soft_cap outcome analysis",
        "",
        f"- status: {payload.get('status')}",
        f"- policy_status: {payload.get('policy_status')}",
        f"- total cases: {payload.get('total_case_count', 0)}",
        f"- classification counts: {payload.get('classification_counts', {})}",
        "",
        "## by classification",
    ]
    for classification, summary in (payload.get("by_classification") or {}).items():
        lines.extend(
            [
                f"### {classification}",
                f"- count: {summary.get('count', 0)}",
                f"- risk_stage: {summary.get('risk_stage_distribution', {})}",
                f"- reliability: {summary.get('reliability_distribution', {})}",
                f"- score_band: {summary.get('score_band_distribution', {})}",
                f"- fx_flags: {summary.get('fx_flag_distribution', {})}",
                f"- 13w excess: {summary.get('excess_return_13w', {})}",
                f"- 13w maxDD: {summary.get('max_drawdown_13w', {})}",
                f"- feature medians: {summary.get('feature_medians', {})}",
                "",
            ]
        )
    lines.append("## hints")
    for hint in payload.get("conditional_policy_hints", []):
        lines.append(f"- {hint}")
    return "\n".join(lines) + "\n"


def run_fx_soft_cap_outcome_analysis(
    replay_json: str | Path = "project/reports/fx_soft_cap_historical_replay.json",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    replay_path = Path(replay_json)
    if not replay_path.exists():
        return {"status": "missing_replay", "replay_json": str(replay_path)}
    payload = build_fx_soft_cap_outcome_analysis(json.loads(replay_path.read_text(encoding="utf-8")))
    json_path, markdown_path = write_fx_soft_cap_outcome_analysis(payload, reports_dir)
    return {
        "status": payload["status"],
        "total_case_count": payload["total_case_count"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _group_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(cases),
        "risk_stage_distribution": _count_key(cases, "risk_stage"),
        "reliability_distribution": _count_key(cases, "reliability_level"),
        "score_band_distribution": _count_key(cases, "score_band"),
        "recovery_evidence_distribution": _recovery_distribution(cases),
        "fx_flag_distribution": _flag_distribution(cases, "fx_flags"),
        "blocker_flag_distribution": _flag_distribution(cases, "blocker_flags"),
        "excess_return_13w": _metric_distribution(cases, "excess_returns", "13w"),
        "max_drawdown_13w": _metric_distribution(cases, "max_drawdowns", "13w"),
        "feature_medians": _feature_medians(cases),
    }


def _count_key(cases: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(Counter(str(case.get(key, "-")) for case in cases))


def _recovery_distribution(cases: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str((case.get("recovery_evidence") or {}).get("grade", "-")) for case in cases))


def _flag_distribution(cases: list[dict[str, Any]], key: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for case in cases:
        for flag in case.get(key, []) or []:
            counter[str(flag)] += 1
    return dict(counter)


def _metric_distribution(cases: list[dict[str, Any]], bucket: str, horizon: str) -> dict[str, Any]:
    values = [float(value) for case in cases if (value := (case.get(bucket) or {}).get(horizon)) is not None]
    if not values:
        return {"count": 0, "mean": None, "median": None, "min": None, "max": None}
    return {
        "count": len(values),
        "mean": round(sum(values) / len(values), 6),
        "median": round(float(median(values)), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
    }


def _feature_medians(cases: list[dict[str, Any]]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for feature in NUMERIC_FEATURES:
        values = [float(value) for case in cases if (value := (case.get("feature_snapshot") or {}).get(feature)) is not None]
        result[feature] = round(float(median(values)), 6) if values else None
    return result


def _policy_hints(by_classification: dict[str, Any]) -> list[str]:
    blocked = by_classification.get("correctly_blocked", {})
    overblocked = by_classification.get("overblocked_by_current", {})
    hints = ["keep fx_soft_cap diagnostic-only until conditional replay is stronger"]
    blocked_features = blocked.get("feature_medians") or {}
    over_features = overblocked.get("feature_medians") or {}
    if (blocked_features.get("vix_level") or 0) > (over_features.get("vix_level") or 0):
        hints.append("VIX level may help separate correctly_blocked cases")
    if (blocked_features.get("hyg_lqd_ratio_return_4w") or 0) < (over_features.get("hyg_lqd_ratio_return_4w") or 0):
        hints.append("credit proxy deterioration may help filter weak candidates")
    if abs(blocked_features.get("usdjpy_change_4w") or 0) > abs(over_features.get("usdjpy_change_4w") or 0):
        hints.append("USDJPY shock threshold may be useful")
    return hints


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze fx_soft_cap historical replay outcomes.")
    parser.add_argument("--replay-json", default="project/reports/fx_soft_cap_historical_replay.json")
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run_fx_soft_cap_outcome_analysis(args.replay_json, args.reports_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
