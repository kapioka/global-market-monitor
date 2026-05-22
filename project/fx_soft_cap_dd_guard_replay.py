from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project.fx_conditional_soft_cap_replay import _candidate_row
from project.fx_soft_cap_dd_guard import GUARD_NAMES, evaluate_dd_guard
from project.fx_soft_cap_historical_replay import _adoption_decision


def build_fx_soft_cap_dd_guard_replay(
    soft_cap_replay: dict[str, Any],
    conditional_replay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cases = list(soft_cap_replay.get("cases") or [])
    base_worst = ((soft_cap_replay.get("return_summary") or {}).get("13w") or {}).get("worst_max_drawdown")
    rows = [
        _row("current", []),
        _row("fx_soft_cap", cases, base_cases=cases, base_worst_dd=base_worst),
    ]
    best_conditional = _best_conditional_name(conditional_replay or {})
    if best_conditional and best_conditional != "-":
        rows.append(_conditional_reference_row(best_conditional, conditional_replay or {}, base_worst))
    rows.extend(_row(guard, _guarded_cases(cases, guard), base_cases=cases, base_worst_dd=base_worst) for guard in GUARD_NAMES)
    best = _best_guard(rows)
    return {
        "status": "ok",
        "policy_status": "diagnostic_only",
        "best_guard": best.get("candidate", "-"),
        "adoption_decision": best.get("adoption_decision", "hold"),
        "affects_final_action": False,
        "base_worst_dd_13w": base_worst,
        "best_worst_dd_13w": ((best.get("return_summary") or {}).get("13w") or {}).get("worst_max_drawdown"),
        "candidates": rows,
    }


def write_fx_soft_cap_dd_guard_replay(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "fx_soft_cap_dd_guard_replay.json"
    markdown_path = reports_path / "fx_soft_cap_dd_guard_replay.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_fx_soft_cap_dd_guard_replay_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_fx_soft_cap_dd_guard_replay_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# fx_soft_cap DD guard replay",
        "",
        f"- status: {payload.get('status')}",
        f"- policy_status: {payload.get('policy_status')}",
        f"- best guard: {payload.get('best_guard')}",
        f"- adoption_decision: {payload.get('adoption_decision')}",
        f"- affects final action: {payload.get('affects_final_action')}",
        f"- worst DD improvement: {_fmt(payload.get('base_worst_dd_13w'))} -> {_fmt(payload.get('best_worst_dd_13w'))}",
        "",
        "## candidates",
    ]
    for row in payload.get("candidates", []):
        ret13 = (row.get("return_summary") or {}).get("13w", {})
        ret26 = (row.get("return_summary") or {}).get("26w", {})
        lines.append(
            "- {name}: count={count} / overblocked={over} / correctly_blocked={blocked} / promising={promising} / 13w={ret} / excess={excess} / 26w={ret26} / worstDD={dd} / excluded_deep_dd={excluded} / missed_good={missed} / decision={decision}".format(
                name=row.get("candidate", "-"),
                count=row.get("buy_candidate_count", 0),
                over=row.get("overblocked_by_current_count", 0),
                blocked=row.get("correctly_blocked_count", 0),
                promising=row.get("promising_candidate_count", 0),
                ret=_fmt(ret13.get("mean_return")),
                excess=_fmt(ret13.get("mean_excess_return")),
                ret26=_fmt(ret26.get("mean_return")),
                dd=_fmt(ret13.get("worst_max_drawdown")),
                excluded=row.get("excluded_deep_dd_count", 0),
                missed=row.get("missed_good_candidate_count", 0),
                decision=row.get("adoption_decision", "hold"),
            )
        )
    return "\n".join(lines) + "\n"


def run_fx_soft_cap_dd_guard_replay(
    replay_json: str | Path = "project/reports/fx_soft_cap_historical_replay.json",
    conditional_replay_json: str | Path = "project/reports/fx_conditional_soft_cap_replay.json",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    replay_path = Path(replay_json)
    if not replay_path.exists():
        return {"status": "missing_replay", "replay_json": str(replay_path)}
    conditional_path = Path(conditional_replay_json)
    conditional = json.loads(conditional_path.read_text(encoding="utf-8")) if conditional_path.exists() else {}
    payload = build_fx_soft_cap_dd_guard_replay(json.loads(replay_path.read_text(encoding="utf-8")), conditional)
    json_path, markdown_path = write_fx_soft_cap_dd_guard_replay(payload, reports_dir)
    return {
        "status": payload["status"],
        "best_guard": payload["best_guard"],
        "adoption_decision": payload["adoption_decision"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _guarded_cases(cases: list[dict[str, Any]], guard: str) -> list[dict[str, Any]]:
    return [case for case in cases if evaluate_dd_guard(case, guard)["passes"]]


def _row(candidate: str, cases: list[dict[str, Any]], base_cases: list[dict[str, Any]] | None = None, base_worst_dd: float | None = None) -> dict[str, Any]:
    row = _candidate_row(candidate, cases, base_cases=base_cases or [])
    row["excluded_deep_dd_count"] = _excluded_deep_dd_count(base_cases or [], cases, base_worst_dd)
    row["missed_good_candidate_count"] = sum(1 for case in (base_cases or []) if case not in cases and case.get("classification") == "overblocked_by_current")
    row["adoption_decision"] = _guard_decision(row)
    return row


def _conditional_reference_row(candidate: str, payload: dict[str, Any], base_worst_dd: float | None) -> dict[str, Any]:
    for row in payload.get("candidates", []):
        if row.get("candidate") == candidate:
            result = dict(row)
            result["candidate"] = f"conditional:{candidate}"
            result["excluded_deep_dd_count"] = 0
            result["missed_good_candidate_count"] = row.get("missed_candidate_count", 0)
            result["adoption_decision"] = _guard_decision(result, base_worst_dd)
            return result
    return _row(f"conditional:{candidate}", [], base_worst_dd=base_worst_dd)


def _best_conditional_name(payload: dict[str, Any]) -> str:
    return str(payload.get("best_candidate") or "-")


def _best_guard(rows: list[dict[str, Any]]) -> dict[str, Any]:
    viable = [row for row in rows if row.get("candidate") not in {"current", "fx_soft_cap"} and int(row.get("buy_candidate_count", 0) or 0) > 0]
    if not viable:
        return {"candidate": "-", "adoption_decision": "hold", "return_summary": {}}
    return sorted(
        viable,
        key=lambda row: (
            _worst_dd(row) or -1.0,
            -int(row.get("correctly_blocked_count", 0) or 0),
            int(row.get("overblocked_by_current_count", 0) or 0),
            -int(row.get("missed_good_candidate_count", 0) or 0),
        ),
        reverse=True,
    )[0]


def _excluded_deep_dd_count(base_cases: list[dict[str, Any]], kept_cases: list[dict[str, Any]], base_worst_dd: float | None) -> int:
    if base_worst_dd is None:
        return 0
    return sum(1 for case in base_cases if case not in kept_cases and _metric(case, "max_drawdowns", "13w") == base_worst_dd)


def _guard_decision(row: dict[str, Any], base_worst_dd: float | None = None) -> str:
    ret13 = (row.get("return_summary") or {}).get("13w", {})
    summary = {"classification_counts": _counts_from_row(row), "return_summary": row.get("return_summary", {})}
    base_decision = _adoption_decision(summary)
    if base_decision == "adopt_candidate":
        return "candidate_for_future_adoption"
    if int(ret13.get("count") or 0) < 20:
        return "hold"
    worst = ret13.get("worst_max_drawdown")
    if base_worst_dd is not None and worst is not None and float(worst) <= float(base_worst_dd):
        return "hold"
    return "hold"


def _counts_from_row(row: dict[str, Any]) -> dict[str, int]:
    return {
        "promising_candidate": int(row.get("promising_candidate_count", 0) or 0),
        "overblocked_by_current": int(row.get("overblocked_by_current_count", 0) or 0),
        "correctly_blocked": int(row.get("correctly_blocked_count", 0) or 0),
        "inconclusive": int(row.get("inconclusive_count", 0) or 0),
    }


def _metric(case: dict[str, Any], bucket: str, horizon: str) -> float | None:
    value = (case.get(bucket) or {}).get(horizon)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _worst_dd(row: dict[str, Any]) -> float | None:
    value = ((row.get("return_summary") or {}).get("13w") or {}).get("worst_max_drawdown")
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
    parser = argparse.ArgumentParser(description="Compare fx_soft_cap DD guard candidates.")
    parser.add_argument("--replay-json", default="project/reports/fx_soft_cap_historical_replay.json")
    parser.add_argument("--conditional-replay-json", default="project/reports/fx_conditional_soft_cap_replay.json")
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run_fx_soft_cap_dd_guard_replay(args.replay_json, args.conditional_replay_json, args.reports_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
