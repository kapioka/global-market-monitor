from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


BLOCKER_KEYS = (
    "score_below_buy_threshold",
    "reliability_policy_cap",
    "risk_line_block",
    "credit_stress",
    "inflation_shock",
    "japan_fx_risk",
    "recovery_evidence_weak",
    "data_quality_low",
    "insufficient_history",
    "unknown",
)


def build_buy_window_diagnostics(
    history_entries: list[dict[str, Any]],
    action_validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw_counts: Counter[str] = Counter()
    risk_counts: Counter[str] = Counter()
    final_counts: Counter[str] = Counter()
    blockers: Counter[str] = Counter()
    cases: list[dict[str, Any]] = []

    for entry in history_entries:
        spot = entry.get("spot_signal") or {}
        decision = spot.get("action_decision") or {}
        layers = spot.get("action_layers") or {}
        market_raw = str(layers.get("market_raw_action") or decision.get("market_raw_action") or decision.get("raw_action") or spot.get("legacy_action") or spot.get("action") or "wait")
        risk_adjusted = str(layers.get("risk_adjusted_action") or decision.get("risk_adjusted_action") or decision.get("raw_action") or spot.get("action") or "wait")
        final = str(layers.get("final_action") or decision.get("final_action") or decision.get("action") or spot.get("action") or "wait")
        raw_counts[market_raw] += 1
        risk_counts[risk_adjusted] += 1
        final_counts[final] += 1
        reasons = classify_buy_window_blockers(entry, market_raw, risk_adjusted, final)
        blockers.update(reasons)
        cases.append(
            {
                "generated_at": entry.get("generated_at"),
                "market_raw_action": market_raw,
                "risk_adjusted_action": risk_adjusted,
                "final_action": final,
                "blockers": reasons,
                "recovery_grade": ((spot.get("recovery_evidence") or {}).get("grade")),
                "risk_stage": ((entry.get("risk_lines") or {}).get("stage_key")),
                "reliability_level": ((entry.get("data_reliability") or {}).get("level")),
            }
        )

    total = len(history_entries)
    raw_buy_window = raw_counts.get("buy_window", 0)
    final_buy_window = final_counts.get("buy_window", 0)
    summary_reasons = _zero_reason_summary(total, raw_buy_window, final_buy_window, blockers)
    return {
        "status": "ok" if total else "no_history",
        "total_history_count": total,
        "raw_action_counts": dict(raw_counts),
        "risk_adjusted_action_counts": dict(risk_counts),
        "final_action_counts": dict(final_counts),
        "raw_buy_window_count": raw_buy_window,
        "final_buy_window_count": final_buy_window,
        "raw_buy_window_to_watch_count": sum(1 for case in cases if case["market_raw_action"] == "buy_window" and case["final_action"] == "watch"),
        "raw_buy_window_to_wait_count": sum(1 for case in cases if case["market_raw_action"] == "buy_window" and case["final_action"] == "wait"),
        "raw_buy_candidate_count": raw_counts.get("buy_candidate", 0),
        "risk_adjusted_buy_candidate_count": risk_counts.get("buy_candidate", 0),
        "final_buy_candidate_count": final_counts.get("buy_candidate", 0),
        "buy_candidate_to_buy_window_transition_count": _transition_count(cases, "buy_candidate", "buy_window"),
        "buy_candidate_to_wait_downgrade_count": _transition_count(cases, "buy_candidate", "wait"),
        "buy_candidate_performance": _buy_candidate_performance(action_validation or {}),
        "blocker_counts": {key: blockers.get(key, 0) for key in BLOCKER_KEYS},
        "buy_window_zero_reason_summary": summary_reasons,
        "cases": cases,
    }


def classify_buy_window_blockers(
    entry: dict[str, Any],
    market_raw: str,
    risk_adjusted: str,
    final: str,
) -> list[str]:
    reasons: list[str] = []
    spot = entry.get("spot_signal") or {}
    reliability = entry.get("data_reliability") or {}
    risk_lines = entry.get("risk_lines") or {}
    regime = entry.get("regime") or {}
    recovery = spot.get("recovery_evidence") or {}
    blocker = spot.get("blocker_assessment") or {}
    score = spot.get("adjusted_score", (entry.get("score") or {}).get("total_score"))

    if market_raw not in {"buy_window", "buy_candidate"}:
        reasons.append("score_below_buy_threshold")
    if str(recovery.get("grade", "")).lower() in {"weak", "guarded", ""}:
        reasons.append("recovery_evidence_weak")
    if bool((spot.get("action_decision") or {}).get("reliability_cap_applied")) or final != risk_adjusted:
        reasons.append("reliability_policy_cap")
    if str(reliability.get("level", "")).lower() in {"low", "diagnostic"} or reliability.get("max_action") in {"wait", "watch", "diagnostic_only"}:
        reasons.append("data_quality_low")
    if str(risk_lines.get("decision_level", blocker.get("level", ""))) == "block" or str(risk_lines.get("stage_key", "")) in {
        "danger_line_reached",
        "extreme_danger_line_reached",
    }:
        reasons.append("risk_line_block")
    if "credit_stress" in str(regime.get("credit_regime_flag", "")) or any("credit" in str(flag) for flag in blocker.get("flags", [])):
        reasons.append("credit_stress")
    if "inflation_shock" in str(regime.get("inflation_regime_flag", "")) or str(regime.get("regime_label", "")) == "inflation_shock":
        reasons.append("inflation_shock")
    if any("japan_fx_risk" in str(flag) for flag in blocker.get("flags", [])):
        reasons.append("japan_fx_risk")
    if score is None:
        reasons.append("insufficient_history")
    return sorted(set(reasons or ["unknown"]))


def write_buy_window_diagnostics(
    payload: dict[str, Any],
    reports_dir: str | Path,
) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "buy_window_diagnostics.json"
    markdown_path = reports_path / "buy_window_diagnostics.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_buy_window_diagnostics_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_buy_window_diagnostics_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# buy_window sparsity diagnostics",
        "",
        f"- status: {payload.get('status')}",
        f"- total history count: {payload.get('total_history_count', 0)}",
        f"- raw buy_window: {payload.get('raw_buy_window_count', 0)}",
        f"- final buy_window: {payload.get('final_buy_window_count', 0)}",
        f"- raw buy_candidate: {payload.get('raw_buy_candidate_count', 0)}",
        f"- risk adjusted buy_candidate: {payload.get('risk_adjusted_buy_candidate_count', 0)}",
        f"- final buy_candidate: {payload.get('final_buy_candidate_count', 0)}",
        f"- buy_candidate -> buy_window: {payload.get('buy_candidate_to_buy_window_transition_count', 0)}",
        f"- buy_candidate -> wait: {payload.get('buy_candidate_to_wait_downgrade_count', 0)}",
        "",
        "## action counts",
        f"- market raw: {payload.get('raw_action_counts', {})}",
        f"- risk adjusted: {payload.get('risk_adjusted_action_counts', {})}",
        f"- final: {payload.get('final_action_counts', {})}",
        "",
        "## blockers",
    ]
    blockers = payload.get("blocker_counts") or {}
    for key in BLOCKER_KEYS:
        lines.append(f"- {key}: {blockers.get(key, 0)}")
    performance = payload.get("buy_candidate_performance") or {}
    lines.extend(["", "## buy_candidate performance"])
    lines.append(f"- count: {performance.get('count', 0)}")
    for horizon in ("4w", "13w", "26w"):
        item = (performance.get("horizons") or {}).get(horizon, {})
        lines.append(
            f"- {horizon}: return={item.get('mean_return', '-')} / excess={item.get('mean_excess_return', '-')} / max_dd={item.get('worst_max_drawdown', '-')}"
        )
    lines.extend(["", "## zero reason summary"])
    for reason in payload.get("buy_window_zero_reason_summary", []):
        lines.append(f"- {reason}")
    return "\n".join(lines) + "\n"


def load_raw_history_entries(history_dir: str | Path) -> list[dict[str, Any]]:
    history_path = Path(history_dir)
    if not history_path.exists():
        return []
    entries = []
    for path in sorted(history_path.glob("report_*.json")):
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        entry["_source_file"] = str(path)
        entries.append(entry)
    return entries


def _zero_reason_summary(total: int, raw_buy_window: int, final_buy_window: int, blockers: Counter[str]) -> list[str]:
    if total == 0:
        return ["insufficient_history: 履歴がないため buy_window の疎さは評価できません。"]
    if final_buy_window > 0:
        return ["final_buy_window_present: 最終 buy_window は0件ではありません。"]
    if raw_buy_window > 0:
        return ["raw_buy_window_capped: 市場シグナルは出ていますが、final action までに降格されています。"]
    top = blockers.most_common(3)
    if not top:
        return ["unknown: raw buy_window が出ていませんが主因を特定できません。"]
    return [f"{key}: {count}件" for key, count in top]


def _transition_count(cases: list[dict[str, Any]], source: str, target: str) -> int:
    count = 0
    for index, case in enumerate(cases):
        if case.get("final_action") != source:
            continue
        following = cases[index + 1 :]
        if following and following[0].get("final_action") == target:
            count += 1
    return count


def _buy_candidate_performance(action_validation: dict[str, Any]) -> dict[str, Any]:
    summary = action_validation.get("action_summary") or {}
    payload = summary.get("buy_candidate") or {"count": 0, "horizons": {}}
    return {
        "count": int(payload.get("count", 0) or 0),
        "horizons": payload.get("horizons", {}),
    }


def run_buy_window_diagnostics(
    history_dir: str | Path = "project/reports/history",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    entries = load_raw_history_entries(history_dir)
    payload = build_buy_window_diagnostics(entries, _load_json_or_empty(Path(reports_dir) / "action_validation_summary.json"))
    json_path, markdown_path = write_buy_window_diagnostics(payload, reports_dir)
    return {
        "status": payload.get("status"),
        "history_count": len(entries),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build buy_window sparsity diagnostics from report history.")
    parser.add_argument("--history-dir", default="project/reports/history")
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run_buy_window_diagnostics(args.history_dir, args.reports_dir), ensure_ascii=False, indent=2))
    return 0


def _load_json_or_empty(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())
