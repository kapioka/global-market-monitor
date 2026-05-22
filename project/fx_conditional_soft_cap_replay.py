from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from project.fx_conditional_soft_cap import CANDIDATE_NAMES, evaluate_conditional_fx_soft_cap
from project.fx_soft_cap_historical_replay import _adoption_decision, _return_summary


def build_fx_conditional_soft_cap_replay(soft_cap_replay: dict[str, Any]) -> dict[str, Any]:
    cases = list(soft_cap_replay.get("cases") or [])
    candidates = [_baseline_row("current", []), _candidate_row("fx_soft_cap", cases)]
    candidates.extend(_candidate_row(candidate, _filtered_cases(cases, candidate), base_cases=cases) for candidate in CANDIDATE_NAMES)
    best = _best_candidate(candidates)
    return {
        "status": "ok",
        "policy_status": "diagnostic_only",
        "best_candidate": best.get("candidate", "-"),
        "adoption_decision": best.get("adoption_decision", "hold"),
        "affects_final_action": False,
        "total_soft_cap_cases": len(cases),
        "candidates": candidates,
    }


def write_fx_conditional_soft_cap_replay(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "fx_conditional_soft_cap_replay.json"
    markdown_path = reports_path / "fx_conditional_soft_cap_replay.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_fx_conditional_soft_cap_replay_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_fx_conditional_soft_cap_replay_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# conditional fx_soft_cap replay",
        "",
        f"- status: {payload.get('status')}",
        f"- policy_status: {payload.get('policy_status')}",
        f"- best candidate: {payload.get('best_candidate')}",
        f"- adoption_decision: {payload.get('adoption_decision')}",
        f"- affects final action: {payload.get('affects_final_action')}",
        "",
        "## candidates",
    ]
    for row in payload.get("candidates", []):
        returns_13w = (row.get("return_summary") or {}).get("13w", {})
        returns_26w = (row.get("return_summary") or {}).get("26w", {})
        lines.append(
            "- {name}: count={count} / overblocked={over} / correctly_blocked={blocked} / promising={promising} / 13w={ret13} / excess={excess13} / 26w={ret26} / worstDD={dd} / decision={decision}".format(
                name=row.get("candidate", "-"),
                count=row.get("buy_candidate_count", 0),
                over=row.get("overblocked_by_current_count", 0),
                blocked=row.get("correctly_blocked_count", 0),
                promising=row.get("promising_candidate_count", 0),
                ret13=_fmt(returns_13w.get("mean_return")),
                excess13=_fmt(returns_13w.get("mean_excess_return")),
                ret26=_fmt(returns_26w.get("mean_return")),
                dd=_fmt(returns_13w.get("worst_max_drawdown")),
                decision=row.get("adoption_decision", "hold"),
            )
        )
    return "\n".join(lines) + "\n"


def run_fx_conditional_soft_cap_replay(
    replay_json: str | Path = "project/reports/fx_soft_cap_historical_replay.json",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    replay_path = Path(replay_json)
    if not replay_path.exists():
        return {"status": "missing_replay", "replay_json": str(replay_path)}
    payload = build_fx_conditional_soft_cap_replay(json.loads(replay_path.read_text(encoding="utf-8")))
    json_path, markdown_path = write_fx_conditional_soft_cap_replay(payload, reports_dir)
    return {
        "status": payload["status"],
        "best_candidate": payload["best_candidate"],
        "adoption_decision": payload["adoption_decision"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _filtered_cases(cases: list[dict[str, Any]], candidate: str) -> list[dict[str, Any]]:
    return [case for case in cases if evaluate_conditional_fx_soft_cap(case, candidate)["applies"]]


def _baseline_row(candidate: str, cases: list[dict[str, Any]]) -> dict[str, Any]:
    return _candidate_row(candidate, cases, base_cases=[])


def _candidate_row(candidate: str, cases: list[dict[str, Any]], base_cases: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    base_cases = base_cases if base_cases is not None else cases
    classifications = _classification_counts(cases)
    summary = {"classification_counts": classifications, "return_summary": _return_summary(cases)}
    missed = [case for case in base_cases if case not in cases and case.get("classification") == "overblocked_by_current"]
    return {
        "candidate": candidate,
        "buy_candidate_count": len(cases),
        "current_watch_to_candidate_buy_candidate_count": len(cases),
        "correctly_blocked_count": classifications.get("correctly_blocked", 0),
        "overblocked_by_current_count": classifications.get("overblocked_by_current", 0),
        "promising_candidate_count": classifications.get("promising_candidate", 0),
        "inconclusive_count": classifications.get("inconclusive", 0),
        "false_candidate_count": classifications.get("correctly_blocked", 0),
        "missed_candidate_count": len(missed),
        "return_summary": summary["return_summary"],
        "adoption_decision": _adoption_decision(summary),
    }


def _classification_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    result = {"promising_candidate": 0, "overblocked_by_current": 0, "correctly_blocked": 0, "inconclusive": 0}
    for case in cases:
        key = str(case.get("classification", "inconclusive"))
        result[key] = result.get(key, 0) + 1
    return result


def _best_candidate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    viable = [row for row in rows if row.get("candidate") not in {"current", "fx_soft_cap"} and row.get("buy_candidate_count", 0) > 0]
    if not viable:
        return {"candidate": "-", "adoption_decision": "hold"}
    return sorted(
        viable,
        key=lambda row: (
            -int(row.get("correctly_blocked_count", 0)),
            int(row.get("overblocked_by_current_count", 0)),
            int(row.get("promising_candidate_count", 0)),
        ),
        reverse=True,
    )[0]


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare conditional fx_soft_cap diagnostic candidates.")
    parser.add_argument("--replay-json", default="project/reports/fx_soft_cap_historical_replay.json")
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run_fx_conditional_soft_cap_replay(args.replay_json, args.reports_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
