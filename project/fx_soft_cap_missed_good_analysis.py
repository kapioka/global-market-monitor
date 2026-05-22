from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from project.fx_soft_cap_dd_guard import evaluate_dd_guard


def build_fx_soft_cap_missed_good_analysis(soft_cap_replay: dict[str, Any], guard_name: str = "combined_dd_guard") -> dict[str, Any]:
    cases = list(soft_cap_replay.get("cases") or [])
    missed = [case for case in cases if case.get("classification") == "overblocked_by_current" and not evaluate_dd_guard(case, guard_name)["passes"]]
    worst = min(cases, key=lambda case: _metric(case, "max_drawdowns", "13w") or 0.0) if cases else {}
    rows = [_row(case, guard_name, worst) for case in missed]
    return {
        "status": "ok",
        "policy_status": "diagnostic_only",
        "guard_name": guard_name,
        "missed_good_count": len(rows),
        "guard_reason_counts": dict(Counter(reason for row in rows for reason in row.get("guard_reasons", []))),
        "worst_dd_reference": _row(worst, guard_name, worst) if worst else {},
        "cases": rows,
    }


def write_fx_soft_cap_missed_good_analysis(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "fx_soft_cap_missed_good_analysis.json"
    markdown_path = reports_path / "fx_soft_cap_missed_good_analysis.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_fx_soft_cap_missed_good_analysis_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_fx_soft_cap_missed_good_analysis_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# fx_soft_cap missed_good analysis",
        "",
        f"- status: {payload.get('status')}",
        f"- policy_status: {payload.get('policy_status')}",
        f"- guard: {payload.get('guard_name')}",
        f"- missed_good count: {payload.get('missed_good_count', 0)}",
        f"- guard reasons: {payload.get('guard_reason_counts', {})}",
        "",
        "## cases",
    ]
    for case in payload.get("cases", []):
        lines.append(
            "- {date}: reasons={reasons} / 13w={ret} / excess={excess} / DD={dd} / rel={rel} / VIX={vix} / credit={credit} / USDJPY={fx}".format(
                date=case.get("generated_at", "-"),
                reasons=", ".join(case.get("guard_reasons", [])) or "-",
                ret=_fmt(case.get("return_13w")),
                excess=_fmt(case.get("excess_return_13w")),
                dd=_fmt(case.get("max_drawdown_13w")),
                rel=_fmt(case.get("acwi_spy_relative_strength")),
                vix=_fmt(case.get("vix_level"), pct=False),
                credit=_fmt(case.get("credit_proxy")),
                fx=_fmt(case.get("usdjpy_change")),
            )
        )
    return "\n".join(lines) + "\n"


def run_fx_soft_cap_missed_good_analysis(
    replay_json: str | Path = "project/reports/fx_soft_cap_historical_replay.json",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    replay_path = Path(replay_json)
    if not replay_path.exists():
        return {"status": "missing_replay", "replay_json": str(replay_path)}
    payload = build_fx_soft_cap_missed_good_analysis(json.loads(replay_path.read_text(encoding="utf-8")))
    json_path, markdown_path = write_fx_soft_cap_missed_good_analysis(payload, reports_dir)
    return {
        "status": payload["status"],
        "missed_good_count": payload["missed_good_count"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _row(case: dict[str, Any], guard_name: str, worst: dict[str, Any]) -> dict[str, Any]:
    features = case.get("feature_snapshot") or {}
    guard = evaluate_dd_guard(case, guard_name)
    return {
        "generated_at": case.get("date") or case.get("generated_at"),
        "original_fx_soft_cap_action": case.get("fx_soft_cap_action"),
        "combined_dd_guard_action": guard.get("action"),
        "excluded_by_guard": not bool(guard.get("passes")),
        "guard_reasons": guard.get("blocked_reasons", []),
        "return_13w": _metric(case, "forward_returns", "13w"),
        "excess_return_13w": _metric(case, "excess_returns", "13w"),
        "max_drawdown_13w": _metric(case, "max_drawdowns", "13w"),
        "return_26w": _metric(case, "forward_returns", "26w"),
        "risk_stage": case.get("risk_stage"),
        "reliability_level": case.get("reliability_level"),
        "market_raw_action": case.get("market_raw_action"),
        "score": case.get("score"),
        "score_band": case.get("score_band"),
        "recovery_evidence": case.get("recovery_evidence", {}),
        "blocker_flags": case.get("blocker_flags", []),
        "fx_flags": case.get("fx_flags", []),
        "acwi_spy_relative_strength": _num(features.get("acwi_spy_relative_13w")),
        "usdjpy_change": _num(features.get("usdjpy_change_4w")),
        "vix_level": _num(features.get("vix_level")),
        "vix_change": _num(features.get("vix_change_4w")),
        "credit_proxy": _num(features.get("hyg_lqd_ratio_return_4w")),
        "rates_proxy": _num(features.get("tnx_change_4w")),
        "oil_family_change": _num(features.get("oil_family_return_4w")),
        "difference_from_worst_case": _difference_from_worst(case, worst),
    }


def _difference_from_worst(case: dict[str, Any], worst: dict[str, Any]) -> list[str]:
    result: list[str] = []
    features = case.get("feature_snapshot") or {}
    worst_features = worst.get("feature_snapshot") or {}
    if (_num(features.get("acwi_spy_relative_13w")) or 0.0) > (_num(worst_features.get("acwi_spy_relative_13w")) or 0.0):
        result.append("relative_trend_less_bad")
    if "foreign_asset_fx_headwind" not in (case.get("fx_flags") or []):
        result.append("no_foreign_asset_fx_headwind")
    if (_metric(case, "max_drawdowns", "13w") or 0.0) > (_metric(worst, "max_drawdowns", "13w") or 0.0):
        result.append("shallower_13w_drawdown")
    return result


def _metric(case: dict[str, Any], bucket: str, horizon: str) -> float | None:
    return _num((case.get(bucket) or {}).get(horizon))


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value: Any, pct: bool = True) -> str:
    if value is None:
        return "-"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.2%}" if pct else f"{number:.2f}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze missed good cases from fx_soft_cap DD guard.")
    parser.add_argument("--replay-json", default="project/reports/fx_soft_cap_historical_replay.json")
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run_fx_soft_cap_missed_good_analysis(args.replay_json, args.reports_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
