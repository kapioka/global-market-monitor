from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_fx_soft_cap_drawdown_analysis(
    soft_cap_replay: dict[str, Any],
    conditional_replay: dict[str, Any] | None = None,
    limit: int = 12,
) -> dict[str, Any]:
    cases = list(soft_cap_replay.get("cases") or [])
    worst_cases = sorted(cases, key=lambda case: _metric(case, "max_drawdowns", "13w") or 0.0)[:limit]
    correctly_blocked = [case for case in cases if case.get("classification") == "correctly_blocked"]
    overblocked = [case for case in cases if case.get("classification") == "overblocked_by_current"]
    return {
        "status": "ok",
        "policy_status": "diagnostic_only",
        "worst_case": _analysis_row(worst_cases[0], "fx_soft_cap") if worst_cases else None,
        "worst_cases": [_analysis_row(case, "fx_soft_cap") for case in worst_cases],
        "correctly_blocked_summary": _group_summary(correctly_blocked),
        "overblocked_by_current_summary": _group_summary(overblocked),
        "conditional_reference": _conditional_reference(conditional_replay or {}),
    }


def write_fx_soft_cap_drawdown_analysis(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "fx_soft_cap_drawdown_analysis.json"
    markdown_path = reports_path / "fx_soft_cap_drawdown_analysis.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_fx_soft_cap_drawdown_analysis_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_fx_soft_cap_drawdown_analysis_markdown(payload: dict[str, Any]) -> str:
    worst = payload.get("worst_case") or {}
    lines = [
        "# fx_soft_cap drawdown analysis",
        "",
        f"- status: {payload.get('status')}",
        f"- policy_status: {payload.get('policy_status')}",
        f"- worst case: {worst.get('generated_at', '-')} / DD13w={_fmt(worst.get('max_drawdown_13w'))}",
        f"- classification: {worst.get('classification', '-')}",
        f"- reason: {worst.get('reason_summary', '-')}",
        "",
        "## worst cases",
    ]
    for case in payload.get("worst_cases", []):
        lines.append(
            "- {date}: {candidate} / class={classification} / DD13w={dd} / return13w={ret} / excess13w={excess} / VIX={vix} / credit={credit} / rel_trend={trend} / fx={fx}".format(
                date=case.get("generated_at", "-"),
                candidate=case.get("candidate_name", "-"),
                classification=case.get("classification", "-"),
                dd=_fmt(case.get("max_drawdown_13w")),
                ret=_fmt(case.get("forward_return_13w")),
                excess=_fmt(case.get("excess_return_13w")),
                vix=_fmt(case.get("vix_level"), pct=False),
                credit=_fmt(case.get("credit_proxy"), pct=True),
                trend=_fmt(case.get("equity_trend"), pct=True),
                fx=", ".join(case.get("fx_flags", [])) or "-",
            )
        )
    lines.extend(
        [
            "",
            "## correctly_blocked vs overblocked",
            f"- correctly_blocked: {payload.get('correctly_blocked_summary', {})}",
            f"- overblocked_by_current: {payload.get('overblocked_by_current_summary', {})}",
            "",
            "## conditional reference",
            f"- {payload.get('conditional_reference', {})}",
        ]
    )
    return "\n".join(lines) + "\n"


def run_fx_soft_cap_drawdown_analysis(
    replay_json: str | Path = "project/reports/fx_soft_cap_historical_replay.json",
    conditional_replay_json: str | Path = "project/reports/fx_conditional_soft_cap_replay.json",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    replay_path = Path(replay_json)
    if not replay_path.exists():
        return {"status": "missing_replay", "replay_json": str(replay_path)}
    conditional_path = Path(conditional_replay_json)
    conditional = json.loads(conditional_path.read_text(encoding="utf-8")) if conditional_path.exists() else {}
    payload = build_fx_soft_cap_drawdown_analysis(json.loads(replay_path.read_text(encoding="utf-8")), conditional)
    json_path, markdown_path = write_fx_soft_cap_drawdown_analysis(payload, reports_dir)
    worst = payload.get("worst_case") or {}
    return {
        "status": payload["status"],
        "worst_case_date": worst.get("generated_at"),
        "worst_drawdown_13w": worst.get("max_drawdown_13w"),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _analysis_row(case: dict[str, Any], candidate_name: str) -> dict[str, Any]:
    features = case.get("feature_snapshot") or {}
    return {
        "generated_at": case.get("date") or case.get("generated_at"),
        "candidate_name": candidate_name,
        "classification": case.get("classification"),
        "max_drawdown_13w": _metric(case, "max_drawdowns", "13w"),
        "forward_return_13w": _metric(case, "forward_returns", "13w"),
        "excess_return_13w": _metric(case, "excess_returns", "13w"),
        "risk_stage": case.get("risk_stage"),
        "reliability_level": case.get("reliability_level"),
        "market_raw_action": case.get("market_raw_action"),
        "current_final_action": case.get("current_final_action"),
        "candidate_action": case.get("fx_soft_cap_action"),
        "score": case.get("score"),
        "score_band": case.get("score_band"),
        "recovery_evidence": case.get("recovery_evidence", {}),
        "blocker_flags": case.get("blocker_flags", []),
        "fx_flags": case.get("fx_flags", []),
        "vix_level": _num(features.get("vix_level")),
        "vix_change": _num(features.get("vix_change_4w")),
        "credit_proxy": _num(features.get("hyg_lqd_ratio_return_4w")),
        "rates_proxy": _num(features.get("tnx_change_4w")),
        "equity_trend": _num(features.get("acwi_spy_relative_13w")),
        "usdjpy_change": _num(features.get("usdjpy_change_4w")),
        "oil_family_change": _num(features.get("oil_family_return_4w")),
        "current_drawdown": _num(features.get("acwi_drawdown_13w")),
        "trigger_path": case.get("trigger_path", []),
        "reason_summary": _reason_summary(case),
    }


def _group_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    drawdowns_13w = [value for value in (_metric(case, "max_drawdowns", "13w") for case in cases) if value is not None]
    return {
        "count": len(cases),
        "worst_dd_13w": min(drawdowns_13w, default=None),
        "mean_excess_13w": _mean([_metric(case, "excess_returns", "13w") for case in cases]),
        "median_vix": _median_feature(cases, "vix_level"),
        "median_credit_proxy": _median_feature(cases, "hyg_lqd_ratio_return_4w"),
        "median_equity_trend": _median_feature(cases, "acwi_spy_relative_13w"),
        "median_usdjpy_change": _median_feature(cases, "usdjpy_change_4w"),
    }


def _conditional_reference(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "best_candidate": payload.get("best_candidate", "-"),
        "adoption_decision": payload.get("adoption_decision", "hold"),
        "affects_final_action": payload.get("affects_final_action", False),
    }


def _reason_summary(case: dict[str, Any]) -> str:
    features = case.get("feature_snapshot") or {}
    reasons: list[str] = []
    if (_num(features.get("acwi_spy_relative_13w")) or 0.0) < -0.01:
        reasons.append("ACWI underperformed SPY")
    if "foreign_asset_fx_headwind" in (case.get("fx_flags") or []):
        reasons.append("foreign_asset_fx_headwind")
    if (_num(features.get("vix_change_4w")) or 0.0) > 0.15:
        reasons.append("VIX rising")
    if (_num(features.get("oil_family_return_4w")) or 0.0) > 0.10:
        reasons.append("oil shock")
    return ", ".join(reasons) or "no single dominant pre-signal"


def _metric(case: dict[str, Any], bucket: str, horizon: str) -> float | None:
    return _num((case.get(bucket) or {}).get(horizon))


def _median_feature(cases: list[dict[str, Any]], feature: str) -> float | None:
    values = sorted(value for case in cases if (value := _num((case.get("feature_snapshot") or {}).get(feature))) is not None)
    if not values:
        return None
    middle = len(values) // 2
    if len(values) % 2:
        return round(values[middle], 6)
    return round((values[middle - 1] + values[middle]) / 2, 6)


def _mean(values: list[float | None]) -> float | None:
    clean = [value for value in values if value is not None]
    return round(sum(clean) / len(clean), 6) if clean else None


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
    parser = argparse.ArgumentParser(description="Analyze deep drawdown cases in fx_soft_cap replay.")
    parser.add_argument("--replay-json", default="project/reports/fx_soft_cap_historical_replay.json")
    parser.add_argument("--conditional-replay-json", default="project/reports/fx_conditional_soft_cap_replay.json")
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        json.dumps(
            run_fx_soft_cap_drawdown_analysis(args.replay_json, args.conditional_replay_json, args.reports_dir),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
