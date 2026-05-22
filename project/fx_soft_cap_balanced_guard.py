from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project.fx_conditional_soft_cap_replay import _candidate_row


def evaluate_balanced_dd_guard(case: dict[str, Any]) -> dict[str, Any]:
    features = case.get("feature_snapshot") or {}
    fx_flags = set(case.get("fx_flags", []) or [])
    equity = _num(features.get("acwi_spy_relative_13w"))
    vix_level = _num(features.get("vix_level"))
    vix_change = _num(features.get("vix_change_4w"))
    credit = _num(features.get("hyg_lqd_ratio_return_4w"))
    current_dd = _num(features.get("acwi_drawdown_13w"))
    acwi_4w = _num(features.get("acwi_return_4w"))
    acwi_13w = _num(features.get("acwi_return_13w"))
    checks = {
        "not_extreme_equity_underperformance": equity is None or equity >= -0.025,
        "headwind_not_with_underperformance": "foreign_asset_fx_headwind" not in fx_flags or (equity is not None and equity >= -0.005),
        "no_volatility_shock": (vix_level is None or vix_level < 25.0) and (vix_change is None or vix_change < 0.25),
        "no_credit_shock": credit is None or credit >= -0.01,
        "drawdown_context_not_bad": (current_dd is None or current_dd > -0.04) and (acwi_4w is None or acwi_4w >= -0.02),
        "recovery_context_ok": acwi_13w is None or acwi_13w >= 0.035,
    }
    passed = all(checks.values())
    return {
        "candidate": "balanced_dd_guard",
        "passes": passed,
        "action": "buy_candidate" if passed else str(case.get("current_final_action", "watch")),
        "blocked_reasons": [name for name, value in checks.items() if not value],
        "affects_final_action": False,
        "policy_status": "diagnostic_only",
    }


def build_fx_soft_cap_balanced_guard(
    soft_cap_replay: dict[str, Any],
    dd_guard_replay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cases = list(soft_cap_replay.get("cases") or [])
    balanced_cases = [case for case in cases if evaluate_balanced_dd_guard(case)["passes"]]
    rows = [
        _candidate_row("fx_soft_cap", cases, base_cases=cases),
        _combined_reference(dd_guard_replay or {}),
        _candidate_row("balanced_dd_guard", balanced_cases, base_cases=cases),
    ]
    return {
        "status": "ok",
        "policy_status": "diagnostic_only",
        "balanced_candidate": "balanced_dd_guard",
        "adoption_decision": _balanced_decision(rows),
        "affects_final_action": False,
        "candidates": rows,
    }


def write_fx_soft_cap_balanced_guard(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "fx_soft_cap_balanced_guard.json"
    markdown_path = reports_path / "fx_soft_cap_balanced_guard.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_fx_soft_cap_balanced_guard_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_fx_soft_cap_balanced_guard_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# fx_soft_cap balanced guard",
        "",
        f"- status: {payload.get('status')}",
        f"- policy_status: {payload.get('policy_status')}",
        f"- balanced candidate: {payload.get('balanced_candidate')}",
        f"- adoption_decision: {payload.get('adoption_decision')}",
        f"- affects final action: {payload.get('affects_final_action')}",
        "",
        "## candidates",
    ]
    for row in payload.get("candidates", []):
        ret13 = (row.get("return_summary") or {}).get("13w", {})
        lines.append(
            "- {name}: count={count} / overblocked={over} / correctly_blocked={blocked} / missed_good={missed} / 13w_excess={excess} / worstDD={dd}".format(
                name=row.get("candidate", "-"),
                count=row.get("buy_candidate_count", 0),
                over=row.get("overblocked_by_current_count", 0),
                blocked=row.get("correctly_blocked_count", 0),
                missed=row.get("missed_candidate_count", row.get("missed_good_candidate_count", 0)),
                excess=_fmt(ret13.get("mean_excess_return")),
                dd=_fmt(ret13.get("worst_max_drawdown")),
            )
        )
    return "\n".join(lines) + "\n"


def run_fx_soft_cap_balanced_guard(
    replay_json: str | Path = "project/reports/fx_soft_cap_historical_replay.json",
    dd_guard_replay_json: str | Path = "project/reports/fx_soft_cap_dd_guard_replay.json",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    replay_path = Path(replay_json)
    if not replay_path.exists():
        return {"status": "missing_replay", "replay_json": str(replay_path)}
    dd_guard_path = Path(dd_guard_replay_json)
    dd_guard = json.loads(dd_guard_path.read_text(encoding="utf-8")) if dd_guard_path.exists() else {}
    payload = build_fx_soft_cap_balanced_guard(json.loads(replay_path.read_text(encoding="utf-8")), dd_guard)
    json_path, markdown_path = write_fx_soft_cap_balanced_guard(payload, reports_dir)
    return {
        "status": payload["status"],
        "balanced_candidate": payload["balanced_candidate"],
        "adoption_decision": payload["adoption_decision"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _combined_reference(payload: dict[str, Any]) -> dict[str, Any]:
    for row in payload.get("candidates", []):
        if row.get("candidate") == "combined_dd_guard":
            return dict(row)
    return {"candidate": "combined_dd_guard", "buy_candidate_count": 0, "return_summary": {}}


def _balanced_decision(rows: list[dict[str, Any]]) -> str:
    fx = rows[0]
    combined = rows[1]
    balanced = rows[2]
    fx_worst = _worst_dd(fx)
    balanced_worst = _worst_dd(balanced)
    fx_excess = _mean_excess_13w(fx)
    balanced_excess = _mean_excess_13w(balanced)
    if int(balanced.get("buy_candidate_count", 0) or 0) < 20:
        return "hold"
    if fx_worst is None or balanced_worst is None or balanced_worst <= fx_worst:
        return "hold"
    if fx_excess is not None and balanced_excess is not None and balanced_excess < fx_excess:
        return "hold"
    if int(balanced.get("correctly_blocked_count", 0) or 0) > int(combined.get("correctly_blocked_count", 0) or 0) + 2:
        return "hold"
    return "candidate_for_future_adoption"


def _worst_dd(row: dict[str, Any]) -> float | None:
    value = ((row.get("return_summary") or {}).get("13w") or {}).get("worst_max_drawdown")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean_excess_13w(row: dict[str, Any]) -> float | None:
    value = ((row.get("return_summary") or {}).get("13w") or {}).get("mean_excess_return")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare balanced fx_soft_cap DD guard.")
    parser.add_argument("--replay-json", default="project/reports/fx_soft_cap_historical_replay.json")
    parser.add_argument("--dd-guard-replay-json", default="project/reports/fx_soft_cap_dd_guard_replay.json")
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run_fx_soft_cap_balanced_guard(args.replay_json, args.dd_guard_replay_json, args.reports_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
