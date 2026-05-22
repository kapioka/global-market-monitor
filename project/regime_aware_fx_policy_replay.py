from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project.fx_conditional_soft_cap_replay import _candidate_row
from project.fx_soft_cap_dd_guard import evaluate_dd_guard
from project.fx_soft_cap_guard_ablation import guard_ablation_passes
from project.fx_soft_cap_historical_replay import _read_table, build_fx_soft_cap_historical_replay
from project.market_regime_classifier import classify_market_regime
from project.regime_aware_fx_policy import REGIME_AWARE_CANDIDATES, evaluate_regime_aware_fx_policy

REPLAY_CANDIDATES = (
    "current",
    "fx_soft_cap",
    "combined_dd_guard",
    "without_equity_trend_guard",
    *REGIME_AWARE_CANDIDATES,
)


def build_regime_aware_fx_policy_replay(features_path: str | Path) -> dict[str, Any]:
    features = _read_table(Path(features_path))
    base = build_fx_soft_cap_historical_replay(features)
    cases = [_case_with_regime(case) for case in list(base.get("cases") or [])]
    rows = [_row(candidate, _candidate_cases(cases, candidate), cases) for candidate in REPLAY_CANDIDATES]
    best = _best_candidate(rows)
    return {
        "status": "ok",
        "policy_status": "diagnostic_only",
        "affects_final_action": False,
        "replay_start": features.index.min().date().isoformat() if not features.empty else None,
        "replay_end": features.index.max().date().isoformat() if not features.empty else None,
        "usable_weeks": int(base.get("total_replay_weeks", 0) or 0),
        "best_candidate": best.get("candidate", "-"),
        "adoption_decision": _adoption_decision(best, rows),
        "candidates": rows,
        "regime_breakdown": _regime_breakdown(cases),
    }


def write_regime_aware_fx_policy_replay(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "regime_aware_fx_policy_replay.json"
    markdown_path = reports_path / "regime_aware_fx_policy_replay.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_regime_aware_fx_policy_replay_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_regime_aware_fx_policy_replay_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# regime-aware FX policy replay",
        "",
        f"- status: {payload.get('status')}",
        f"- policy_status: {payload.get('policy_status')}",
        f"- replay range: {payload.get('replay_start') or '-'} to {payload.get('replay_end') or '-'}",
        f"- usable weeks: {payload.get('usable_weeks', 0)}",
        f"- best candidate: {payload.get('best_candidate')}",
        f"- adoption_decision: {payload.get('adoption_decision')}",
        f"- affects final action: {payload.get('affects_final_action')}",
        "",
        "## candidates",
    ]
    for row in payload.get("candidates", []):
        lines.append(_candidate_line(row))
    lines.extend(["", "## regime breakdown"])
    for regime, rows in (payload.get("regime_breakdown") or {}).items():
        lines.append(f"### {regime}")
        for row in rows:
            lines.append(_candidate_line(row))
    return "\n".join(lines) + "\n"


def run_regime_aware_fx_policy_replay(
    features_path: str | Path = "project/cache/historical_features_long.csv",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    path = Path(features_path)
    if not path.exists():
        return {"status": "missing_features", "features_path": str(path)}
    payload = build_regime_aware_fx_policy_replay(path)
    json_path, markdown_path = write_regime_aware_fx_policy_replay(payload, reports_dir)
    return {
        "status": payload["status"],
        "best_candidate": payload["best_candidate"],
        "adoption_decision": payload["adoption_decision"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _case_with_regime(case: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(case)
    enriched["market_regime"] = classify_market_regime(enriched)
    return enriched


def _candidate_cases(cases: list[dict[str, Any]], candidate: str) -> list[dict[str, Any]]:
    if candidate == "current":
        return []
    if candidate == "fx_soft_cap":
        return cases
    if candidate == "combined_dd_guard":
        return [case for case in cases if evaluate_dd_guard(case, "combined_dd_guard")["passes"]]
    if candidate == "without_equity_trend_guard":
        return [case for case in cases if guard_ablation_passes(case, "without_equity_trend_guard")]
    if candidate in REGIME_AWARE_CANDIDATES:
        return [case for case in cases if evaluate_regime_aware_fx_policy(case, candidate)["applies"]]
    raise ValueError(f"unknown replay candidate: {candidate}")


def _row(candidate: str, cases: list[dict[str, Any]], base_cases: list[dict[str, Any]]) -> dict[str, Any]:
    row = _candidate_row(candidate, cases, base_cases=base_cases)
    row["missed_good_candidate_count"] = row.get("missed_candidate_count", 0)
    row["adoption_decision"] = "hold"
    return row


def _regime_breakdown(cases: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    regimes = sorted({str((case.get("market_regime") or {}).get("regime", "uncertain")) for case in cases})
    return {
        regime: [_row(candidate, _candidate_cases([case for case in cases if (case.get("market_regime") or {}).get("regime") == regime], candidate), [case for case in cases if (case.get("market_regime") or {}).get("regime") == regime]) for candidate in REPLAY_CANDIDATES]
        for regime in regimes
    }


def _best_candidate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    viable = [row for row in rows if row.get("candidate") not in {"current", "fx_soft_cap"} and int(row.get("buy_candidate_count", 0) or 0) > 0]
    if not viable:
        return {"candidate": "-", "adoption_decision": "hold"}
    return sorted(
        viable,
        key=lambda row: (
            _worst_dd(row) or -1.0,
            _mean_excess(row) or -1.0,
            -int(row.get("correctly_blocked_count", 0) or 0),
            int(row.get("overblocked_by_current_count", 0) or 0),
            -int(row.get("missed_good_candidate_count", 0) or 0),
        ),
        reverse=True,
    )[0]


def _adoption_decision(best: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    if not best or best.get("candidate") in {None, "-"}:
        return "hold"
    fx = next((row for row in rows if row.get("candidate") == "fx_soft_cap"), {})
    if int(best.get("buy_candidate_count", 0) or 0) < 20:
        return "hold"
    if (_worst_dd(best) is None) or (_worst_dd(fx) is not None and float(_worst_dd(best) or 0.0) <= float(_worst_dd(fx) or 0.0)):
        return "hold"
    if (_mean_excess(best) or 0.0) < 0.0:
        return "hold"
    if (_mean_excess(best, "26w") or 0.0) < 0.0:
        return "hold"
    if int(best.get("correctly_blocked_count", 0) or 0) > max(2, int(fx.get("correctly_blocked_count", 0) or 0) // 2):
        return "hold"
    return "candidate_for_future_adoption"


def _candidate_line(row: dict[str, Any]) -> str:
    ret13 = (row.get("return_summary") or {}).get("13w", {})
    ret26 = (row.get("return_summary") or {}).get("26w", {})
    return "- {name}: count={count} / overblocked={over} / correctly_blocked={blocked} / promising={promising} / missed_good={missed} / 13w_excess={ex13} / 13w_worstDD={dd13} / 26w_excess={ex26} / 26w_worstDD={dd26} / decision={decision}".format(
        name=row.get("candidate", "-"),
        count=row.get("buy_candidate_count", 0),
        over=row.get("overblocked_by_current_count", 0),
        blocked=row.get("correctly_blocked_count", 0),
        promising=row.get("promising_candidate_count", 0),
        missed=row.get("missed_good_candidate_count", row.get("missed_candidate_count", 0)),
        ex13=_fmt(ret13.get("mean_excess_return")),
        dd13=_fmt(ret13.get("worst_max_drawdown")),
        ex26=_fmt(ret26.get("mean_excess_return")),
        dd26=_fmt(ret26.get("worst_max_drawdown")),
        decision=row.get("adoption_decision", "hold"),
    )


def _worst_dd(row: dict[str, Any], horizon: str = "13w") -> float | None:
    value = ((row.get("return_summary") or {}).get(horizon) or {}).get("worst_max_drawdown")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mean_excess(row: dict[str, Any], horizon: str = "13w") -> float | None:
    value = ((row.get("return_summary") or {}).get(horizon) or {}).get("mean_excess_return")
    if value is None:
        return None
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
    parser = argparse.ArgumentParser(description="Replay regime-aware FX policy candidates.")
    parser.add_argument("--features", default="project/cache/historical_features_long.csv")
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run_regime_aware_fx_policy_replay(args.features, args.reports_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
