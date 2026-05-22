from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from project.buy_window_diagnostics import load_raw_history_entries
from project.config_loader import load_config


def build_buy_candidate_near_miss(
    history_entries: list[dict[str, Any]],
    thresholds: dict[str, Any] | None = None,
) -> dict[str, Any]:
    thresholds = thresholds or {}
    watch = float(thresholds.get("spot_score_watch", 0.45))
    buy = float(thresholds.get("spot_score_buy", 0.65))
    candidate_floor = watch + ((buy - watch) * 0.6)
    near_floor = candidate_floor - 0.05
    cases = []
    missing_counter: Counter[str] = Counter()
    blocker_counter: Counter[str] = Counter()
    recovery_counter: Counter[str] = Counter()
    risk_counter: Counter[str] = Counter()
    reliability_counter: Counter[str] = Counter()

    for entry in history_entries:
        row = _evaluate_case(entry, candidate_floor, near_floor)
        if not row["is_near_miss"]:
            continue
        cases.append(row)
        missing_counter.update(row["missing_conditions"])
        blocker_counter.update([row["blocker_level"]])
        recovery_counter.update([row["recovery_grade"]])
        risk_counter.update([row["risk_stage"]])
        reliability_counter.update([row["reliability_level"]])

    cases.sort(key=lambda item: (len(item["missing_conditions"]), item["score_gap_to_candidate"]))
    return {
        "status": "ok",
        "total_history_count": len(history_entries),
        "candidate_floor": round(candidate_floor, 4),
        "near_floor": round(near_floor, 4),
        "near_miss_count": len(cases),
        "missing_condition_counts": dict(missing_counter),
        "blocker_distribution": dict(blocker_counter),
        "recovery_evidence_distribution": dict(recovery_counter),
        "risk_stage_distribution": dict(risk_counter),
        "reliability_distribution": dict(reliability_counter),
        "top_near_miss_cases": cases[:10],
    }


def write_buy_candidate_near_miss(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "buy_candidate_near_miss.json"
    markdown_path = reports_path / "buy_candidate_near_miss.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_buy_candidate_near_miss_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_buy_candidate_near_miss_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# buy_candidate near-miss diagnostics",
        "",
        f"- status: {payload.get('status')}",
        f"- total history count: {payload.get('total_history_count', 0)}",
        f"- candidate floor: {payload.get('candidate_floor')}",
        f"- near floor: {payload.get('near_floor')}",
        f"- near_miss_count: {payload.get('near_miss_count', 0)}",
        f"- missing_condition_counts: {payload.get('missing_condition_counts', {})}",
        "",
        "## top near-miss cases",
    ]
    cases = payload.get("top_near_miss_cases") or []
    if not cases:
        lines.append("- near-miss cases were not found")
        return "\n".join(lines) + "\n"
    for case in cases:
        lines.append(
            "- {date}: score_gap={gap} / missing={missing} / recovery={recovery} / blocker={blocker} / risk={risk} / reliability={reliability}".format(
                date=case.get("generated_at", "-"),
                gap=case.get("score_gap_to_candidate", "-"),
                missing=", ".join(case.get("missing_conditions", [])) or "-",
                recovery=case.get("recovery_grade", "-"),
                blocker=case.get("blocker_level", "-"),
                risk=case.get("risk_stage", "-"),
                reliability=case.get("reliability_level", "-"),
            )
        )
    return "\n".join(lines) + "\n"


def run_buy_candidate_near_miss(
    history_dir: str | Path = "project/reports/history",
    reports_dir: str | Path = "project/reports",
    config_path: str | Path = "project/config.yaml",
) -> dict[str, Any]:
    config = load_config(config_path)
    payload = build_buy_candidate_near_miss(load_raw_history_entries(history_dir), config.get("thresholds", {}))
    json_path, markdown_path = write_buy_candidate_near_miss(payload, reports_dir)
    return {
        "status": payload["status"],
        "history_count": payload["total_history_count"],
        "near_miss_count": payload["near_miss_count"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _evaluate_case(entry: dict[str, Any], candidate_floor: float, near_floor: float) -> dict[str, Any]:
    spot = entry.get("spot_signal") or {}
    decision = spot.get("action_decision") or {}
    layers = spot.get("action_layers") or {}
    final = str(layers.get("final_action") or decision.get("final_action") or decision.get("action") or spot.get("action") or "wait")
    score = _as_float(spot.get("adjusted_score", (entry.get("score") or {}).get("total_score")))
    recovery = spot.get("recovery_evidence") or {}
    blocker = spot.get("blocker_assessment") or {}
    risk_lines = entry.get("risk_lines") or {}
    reliability = entry.get("data_reliability") or {}

    score_ok = score is not None and score >= candidate_floor
    score_near = score is not None and score >= near_floor
    recovery_ok = str(recovery.get("grade", "")).lower() in {"building", "confirmed"}
    blocker_ok = str(blocker.get("level", "none")) == "none"
    risk_ok = str(risk_lines.get("stage_key", "normal")) not in {"danger_line_reached", "extreme_danger_line_reached", "data_unavailable"}
    reliability_ok = str(reliability.get("level", "high")) in {"high", "medium"} and reliability.get("max_action") not in {"wait", "diagnostic_only"}
    missing = []
    if not score_ok:
        missing.append("score_below_candidate")
    if not recovery_ok:
        missing.append("recovery_evidence_weak")
    if not blocker_ok:
        missing.append(_blocker_missing_condition(blocker))
    if not risk_ok:
        missing.append("risk_stage_too_high")
    if not reliability_ok:
        missing.append("reliability_insufficient")
    is_near_miss = final not in {"buy_candidate", "buy_window"} and score_near and 1 <= len(set(missing)) <= 2
    return {
        "generated_at": entry.get("generated_at"),
        "source_history": entry.get("_source_file"),
        "is_near_miss": is_near_miss,
        "missing_conditions": sorted(set(missing)),
        "score": score,
        "score_gap_to_candidate": round(max(candidate_floor - (score or 0.0), 0.0), 4) if score is not None else None,
        "blocker_level": str(blocker.get("level", "none")),
        "blocker_flags": list(blocker.get("flags", [])),
        "recovery_grade": str(recovery.get("grade", "unknown")),
        "recovery_score": recovery.get("score"),
        "risk_stage": str(risk_lines.get("stage_key", "normal")),
        "reliability_level": str(reliability.get("level", "high")),
        "final_action": final,
    }


def _blocker_missing_condition(blocker: dict[str, Any]) -> str:
    flags = {str(flag) for flag in blocker.get("flags", [])}
    if flags.intersection({"japan_fx_risk_moderate", "japan_fx_risk_high", "foreign_asset_fx_headwind", "foreign_asset_fx_dependency"}):
        return "japan_fx_risk_caution"
    if str(blocker.get("level")) == "block":
        return "blocker_block"
    return "blocker_caution"


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build buy_candidate near-miss diagnostics.")
    parser.add_argument("--history-dir", default="project/reports/history")
    parser.add_argument("--reports-dir", default="project/reports")
    parser.add_argument("--config", default="project/config.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run_buy_candidate_near_miss(args.history_dir, args.reports_dir, args.config), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
