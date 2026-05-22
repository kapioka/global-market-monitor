from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_fx_soft_cap_regime_analysis(long_range_replay: dict[str, Any]) -> dict[str, Any]:
    regimes = long_range_replay.get("regime_breakdown") or {}
    candidate_names = _candidate_names(regimes)
    stability = [_candidate_stability(name, regimes) for name in candidate_names]
    best = _best_stable_candidate(stability)
    return {
        "status": "ok",
        "policy_status": "diagnostic_only",
        "affects_final_action": False,
        "source_replay_start": long_range_replay.get("replay_start"),
        "source_replay_end": long_range_replay.get("replay_end"),
        "best_candidate": best.get("candidate", "-"),
        "adoption_decision": _decision(best),
        "regimes": regimes,
        "candidate_stability": stability,
    }


def write_fx_soft_cap_regime_analysis(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "fx_soft_cap_regime_analysis.json"
    markdown_path = reports_path / "fx_soft_cap_regime_analysis.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_fx_soft_cap_regime_analysis_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_fx_soft_cap_regime_analysis_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# fx_soft_cap regime analysis",
        "",
        f"- status: {payload.get('status')}",
        f"- policy_status: {payload.get('policy_status')}",
        f"- source range: {payload.get('source_replay_start') or '-'} to {payload.get('source_replay_end') or '-'}",
        f"- best candidate: {payload.get('best_candidate')}",
        f"- adoption_decision: {payload.get('adoption_decision')}",
        f"- affects final action: {payload.get('affects_final_action')}",
        "",
        "## candidate stability",
    ]
    for item in payload.get("candidate_stability", []):
        lines.append(
            "- {name}: regimes_with_cases={with_cases}/{total} / negative_excess_regimes={neg} / deep_dd_regimes={dd} / total_correctly_blocked={blocked} / total_missed_good={missed} / decision={decision}".format(
                name=item.get("candidate", "-"),
                with_cases=item.get("regimes_with_cases", 0),
                total=item.get("total_regimes", 0),
                neg=item.get("negative_excess_regimes", 0),
                dd=item.get("deep_dd_regimes", 0),
                blocked=item.get("total_correctly_blocked", 0),
                missed=item.get("total_missed_good", 0),
                decision=item.get("decision", "hold"),
            )
        )
    lines.extend(["", "## regimes"])
    for regime, rows in (payload.get("regimes") or {}).items():
        lines.append(f"### {regime}")
        for row in rows:
            ret13 = (row.get("return_summary") or {}).get("13w", {})
            ret26 = (row.get("return_summary") or {}).get("26w", {})
            lines.append(
                "- {name}: count={count} / overblocked={over} / correctly_blocked={blocked} / missed_good={missed} / 13w_excess={ex13} / 26w_excess={ex26} / worstDD={dd}".format(
                    name=row.get("candidate", "-"),
                    count=row.get("buy_candidate_count", 0),
                    over=row.get("overblocked_by_current_count", 0),
                    blocked=row.get("correctly_blocked_count", 0),
                    missed=row.get("missed_good_candidate_count", row.get("missed_candidate_count", 0)),
                    ex13=_fmt(ret13.get("mean_excess_return")),
                    ex26=_fmt(ret26.get("mean_excess_return")),
                    dd=_fmt(ret13.get("worst_max_drawdown")),
                )
            )
    return "\n".join(lines) + "\n"


def run_fx_soft_cap_regime_analysis(
    long_range_replay_json: str | Path = "project/reports/fx_soft_cap_long_range_guard_replay.json",
    reports_dir: str | Path = "project/reports",
) -> dict[str, Any]:
    path = Path(long_range_replay_json)
    if not path.exists():
        return {"status": "missing_long_range_replay", "long_range_replay_json": str(path)}
    payload = build_fx_soft_cap_regime_analysis(json.loads(path.read_text(encoding="utf-8")))
    json_path, markdown_path = write_fx_soft_cap_regime_analysis(payload, reports_dir)
    return {
        "status": payload["status"],
        "best_candidate": payload["best_candidate"],
        "adoption_decision": payload["adoption_decision"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _candidate_names(regimes: dict[str, list[dict[str, Any]]]) -> list[str]:
    names: list[str] = []
    for rows in regimes.values():
        for row in rows:
            name = str(row.get("candidate", "-"))
            if name not in names:
                names.append(name)
    return names


def _candidate_stability(candidate: str, regimes: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for regime_rows in regimes.values():
        row = _find_candidate(regime_rows, candidate)
        if row:
            rows.append(row)
    with_cases = [row for row in rows if int(row.get("buy_candidate_count", 0) or 0) > 0]
    negative_excess = sum(1 for row in with_cases if _is_negative_excess(row))
    deep_dd = sum(1 for row in with_cases if _is_deep_dd(row))
    total_blocked = sum(int(row.get("correctly_blocked_count", 0) or 0) for row in with_cases)
    total_missed = sum(int(row.get("missed_good_candidate_count", row.get("missed_candidate_count", 0)) or 0) for row in with_cases)
    result = {
        "candidate": candidate,
        "total_regimes": len(regimes),
        "regimes_with_cases": len(with_cases),
        "negative_excess_regimes": negative_excess,
        "deep_dd_regimes": deep_dd,
        "total_correctly_blocked": total_blocked,
        "total_missed_good": total_missed,
    }
    result["decision"] = _candidate_decision(result)
    return result


def _find_candidate(rows: list[dict[str, Any]], candidate: str) -> dict[str, Any] | None:
    return next((row for row in rows if row.get("candidate") == candidate), None)


def _best_stable_candidate(stability: list[dict[str, Any]]) -> dict[str, Any]:
    viable = [row for row in stability if row.get("candidate") not in {"current", "fx_soft_cap"}]
    if not viable:
        return {"candidate": "-", "decision": "hold"}
    return sorted(
        viable,
        key=lambda row: (
            -int(row.get("deep_dd_regimes", 0) or 0),
            -int(row.get("negative_excess_regimes", 0) or 0),
            int(row.get("regimes_with_cases", 0) or 0),
            -int(row.get("total_correctly_blocked", 0) or 0),
            -int(row.get("total_missed_good", 0) or 0),
        ),
        reverse=True,
    )[0]


def _decision(best: dict[str, Any]) -> str:
    if not best or best.get("candidate") in {None, "-"}:
        return "hold"
    return str(best.get("decision") or "hold")


def _candidate_decision(row: dict[str, Any]) -> str:
    if int(row.get("regimes_with_cases", 0) or 0) < 2:
        return "hold"
    if int(row.get("deep_dd_regimes", 0) or 0) > 0:
        return "hold"
    if int(row.get("negative_excess_regimes", 0) or 0) > 1:
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


def _mean_excess(row: dict[str, Any]) -> float | None:
    value = ((row.get("return_summary") or {}).get("13w") or {}).get("mean_excess_return")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_negative_excess(row: dict[str, Any]) -> bool:
    value = _mean_excess(row)
    return value is not None and value < 0.0


def _is_deep_dd(row: dict[str, Any]) -> bool:
    value = _worst_dd(row)
    return value is not None and value <= -0.10


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze long-range fx_soft_cap candidates by regime.")
    parser.add_argument("--long-range-replay-json", default="project/reports/fx_soft_cap_long_range_guard_replay.json")
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run_fx_soft_cap_regime_analysis(args.long_range_replay_json, args.reports_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
