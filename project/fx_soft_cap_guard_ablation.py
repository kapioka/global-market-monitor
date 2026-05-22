from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project.fx_conditional_soft_cap_replay import _candidate_row
from project.fx_soft_cap_dd_guard import evaluate_dd_guard

ABLATION_NAMES = (
    "combined_dd_guard",
    "without_equity_trend_guard",
    "without_volatility_guard",
    "without_credit_guard",
    "without_drawdown_context_guard",
    "without_recovery_guard",
    "relaxed_equity_trend_guard",
    "relaxed_drawdown_guard",
)


def build_fx_soft_cap_guard_ablation(soft_cap_replay: dict[str, Any]) -> dict[str, Any]:
    cases = list(soft_cap_replay.get("cases") or [])
    rows = [_row(name, _filtered_cases(cases, name), cases) for name in ABLATION_NAMES]
    best = _best_balanced(rows)
    return {
        "status": "ok",
        "policy_status": "diagnostic_only",
        "best_balanced_candidate": best.get("candidate", "-"),
        "adoption_decision": best.get("adoption_decision", "hold"),
        "affects_final_action": False,
        "base_case_count": len(cases),
        "candidates": rows,
    }


def write_fx_soft_cap_guard_ablation(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "fx_soft_cap_guard_ablation.json"
    markdown_path = reports_path / "fx_soft_cap_guard_ablation.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_fx_soft_cap_guard_ablation_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_fx_soft_cap_guard_ablation_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# fx_soft_cap guard ablation",
        "",
        f"- status: {payload.get('status')}",
        f"- policy_status: {payload.get('policy_status')}",
        f"- best balanced candidate: {payload.get('best_balanced_candidate')}",
        f"- adoption_decision: {payload.get('adoption_decision')}",
        f"- affects final action: {payload.get('affects_final_action')}",
        "",
        "## candidates",
    ]
    for row in payload.get("candidates", []):
        ret13 = (row.get("return_summary") or {}).get("13w", {})
        lines.append(
            "- {name}: count={count} / overblocked={over} / correctly_blocked={blocked} / promising={promising} / missed_good={missed} / 13w_excess={excess} / worstDD={dd} / decision={decision}".format(
                name=row.get("candidate", "-"),
                count=row.get("buy_candidate_count", 0),
                over=row.get("overblocked_by_current_count", 0),
                blocked=row.get("correctly_blocked_count", 0),
                promising=row.get("promising_candidate_count", 0),
                missed=row.get("missed_good_candidate_count", 0),
                excess=_fmt(ret13.get("mean_excess_return")),
                dd=_fmt(ret13.get("worst_max_drawdown")),
                decision=row.get("adoption_decision", "hold"),
            )
        )
    return "\n".join(lines) + "\n"


def run_fx_soft_cap_guard_ablation(
    replay_json: str | Path = "project/reports/fx_soft_cap_historical_replay.json",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    replay_path = Path(replay_json)
    if not replay_path.exists():
        return {"status": "missing_replay", "replay_json": str(replay_path)}
    payload = build_fx_soft_cap_guard_ablation(json.loads(replay_path.read_text(encoding="utf-8")))
    json_path, markdown_path = write_fx_soft_cap_guard_ablation(payload, reports_dir)
    return {
        "status": payload["status"],
        "best_balanced_candidate": payload["best_balanced_candidate"],
        "adoption_decision": payload["adoption_decision"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def guard_ablation_passes(case: dict[str, Any], candidate: str) -> bool:
    checks = _checks(case)
    if candidate == "combined_dd_guard":
        return bool(evaluate_dd_guard(case, "combined_dd_guard")["passes"])
    if candidate == "without_equity_trend_guard":
        return checks["volatility_ok"] and checks["credit_ok"] and checks["drawdown_context_ok"] and checks["recovery_context_ok"] and checks["fx_headwind_ok"]
    if candidate == "without_volatility_guard":
        return checks["equity_trend_ok"] and checks["credit_ok"] and checks["drawdown_context_ok"] and checks["recovery_context_ok"] and checks["fx_headwind_ok"]
    if candidate == "without_credit_guard":
        return checks["equity_trend_ok"] and checks["volatility_ok"] and checks["drawdown_context_ok"] and checks["recovery_context_ok"] and checks["fx_headwind_ok"]
    if candidate == "without_drawdown_context_guard":
        return checks["equity_trend_ok"] and checks["volatility_ok"] and checks["credit_ok"] and checks["recovery_context_ok"] and checks["fx_headwind_ok"]
    if candidate == "without_recovery_guard":
        return checks["equity_trend_ok"] and checks["volatility_ok"] and checks["credit_ok"] and checks["drawdown_context_ok"] and checks["fx_headwind_ok"]
    if candidate == "relaxed_equity_trend_guard":
        return checks["relaxed_equity_trend_ok"] and checks["volatility_ok"] and checks["credit_ok"] and checks["drawdown_context_ok"] and checks["recovery_context_ok"] and checks["fx_headwind_ok"]
    if candidate == "relaxed_drawdown_guard":
        return checks["equity_trend_ok"] and checks["volatility_ok"] and checks["credit_ok"] and checks["relaxed_drawdown_context_ok"] and checks["recovery_context_ok"] and checks["fx_headwind_ok"]
    raise ValueError(f"unknown guard ablation candidate: {candidate}")


def _filtered_cases(cases: list[dict[str, Any]], candidate: str) -> list[dict[str, Any]]:
    return [case for case in cases if guard_ablation_passes(case, candidate)]


def _row(candidate: str, cases: list[dict[str, Any]], base_cases: list[dict[str, Any]]) -> dict[str, Any]:
    row = _candidate_row(candidate, cases, base_cases=base_cases)
    row["missed_good_candidate_count"] = row.get("missed_candidate_count", 0)
    row["adoption_decision"] = "hold"
    return row


def _checks(case: dict[str, Any]) -> dict[str, bool]:
    features = case.get("feature_snapshot") or {}
    fx_flags = set(case.get("fx_flags", []) or [])
    equity = _num(features.get("acwi_spy_relative_13w"))
    vix_level = _num(features.get("vix_level"))
    vix_change = _num(features.get("vix_change_4w"))
    credit = _num(features.get("hyg_lqd_ratio_return_4w"))
    current_dd = _num(features.get("acwi_drawdown_13w"))
    acwi_4w = _num(features.get("acwi_return_4w"))
    acwi_13w = _num(features.get("acwi_return_13w"))
    return {
        "equity_trend_ok": equity is None or equity >= -0.01,
        "relaxed_equity_trend_ok": equity is None or equity >= -0.025,
        "volatility_ok": (vix_level is None or vix_level < 25.0) and (vix_change is None or vix_change < 0.15),
        "credit_ok": credit is None or credit >= -0.01,
        "drawdown_context_ok": (current_dd is None or current_dd > -0.03) and (acwi_4w is None or acwi_4w >= 0.0),
        "relaxed_drawdown_context_ok": (current_dd is None or current_dd > -0.04) and (acwi_4w is None or acwi_4w >= -0.02),
        "recovery_context_ok": acwi_13w is None or acwi_13w >= 0.04,
        "fx_headwind_ok": "foreign_asset_fx_headwind" not in fx_flags or (equity is not None and equity >= 0.0),
    }


def _best_balanced(rows: list[dict[str, Any]]) -> dict[str, Any]:
    viable = [row for row in rows if int(row.get("buy_candidate_count", 0) or 0) > 0]
    if not viable:
        return {"candidate": "-", "adoption_decision": "hold"}
    return sorted(
        viable,
        key=lambda row: (
            _worst_dd(row) or -1.0,
            -int(row.get("missed_good_candidate_count", 0) or 0),
            -int(row.get("correctly_blocked_count", 0) or 0),
            int(row.get("overblocked_by_current_count", 0) or 0),
        ),
        reverse=True,
    )[0]


def _worst_dd(row: dict[str, Any]) -> float | None:
    value = ((row.get("return_summary") or {}).get("13w") or {}).get("worst_max_drawdown")
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
    parser = argparse.ArgumentParser(description="Run fx_soft_cap DD guard ablation.")
    parser.add_argument("--replay-json", default="project/reports/fx_soft_cap_historical_replay.json")
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run_fx_soft_cap_guard_ablation(args.replay_json, args.reports_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
