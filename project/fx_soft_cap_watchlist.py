from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from project.buy_window_case_study import _load_price_points
from project.buy_window_diagnostics import load_raw_history_entries
from project.config_loader import load_config
from project.fx_conditional_soft_cap import CANDIDATE_NAMES, evaluate_all_conditional_candidates
from project.fx_soft_cap_case_study import build_fx_soft_cap_case_study
from project.market_regime_classifier import classify_market_regime
from project.regime_aware_fx_policy import REGIME_AWARE_CANDIDATES, evaluate_all_regime_aware_fx_policies

HORIZONS_DAYS = {"4w": 28, "13w": 91, "26w": 182}


def build_fx_soft_cap_watchlist(
    history_entries: list[dict[str, Any]],
    price_points: list[dict[str, Any]],
    thresholds: dict[str, Any] | None = None,
    benchmark_price_points: list[dict[str, Any]] | None = None,
    historical_replay: dict[str, Any] | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    case_study = build_fx_soft_cap_case_study(history_entries, price_points, thresholds, benchmark_price_points)
    cases = [_watchlist_row(case, today, historical_replay or {}) for case in case_study.get("cases", [])]
    ready = sum(1 for case in cases if case["review_status"] in {"ready_for_review", "reviewed"})
    waiting = len(cases) - ready
    conditional_summary = _conditional_summary(cases)
    regime_summary = _regime_aware_summary(cases)
    return {
        "status": "ok",
        "policy_status": "diagnostic_only",
        "adoption_decision": "hold",
        "tracked_case_count": len(cases),
        "ready_for_review_count": ready,
        "waiting_future_data_count": waiting,
        "historical_similarity": _historical_similarity_summary(historical_replay or {}),
        "conditional_fx_soft_cap": conditional_summary,
        "regime_aware_fx_policy": regime_summary,
        "cases": cases,
    }


def write_fx_soft_cap_watchlist(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "fx_soft_cap_watchlist.json"
    markdown_path = reports_path / "fx_soft_cap_watchlist.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_fx_soft_cap_watchlist_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_fx_soft_cap_watchlist_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# fx_soft_cap watchlist",
        "",
        f"- status: {payload.get('status')}",
        f"- policy_status: {payload.get('policy_status')}",
        f"- adoption_decision: {payload.get('adoption_decision')}",
        f"- tracked cases: {payload.get('tracked_case_count', 0)}",
        f"- ready for review: {payload.get('ready_for_review_count', 0)}",
        f"- waiting future data: {payload.get('waiting_future_data_count', 0)}",
        f"- similar historical cases: {(payload.get('historical_similarity') or {}).get('similar_historical_case_count', 0)}",
        f"- conditional combined_conservative applicable: {(payload.get('conditional_fx_soft_cap') or {}).get('combined_conservative_applicable_count', 0)}",
        f"- regime-aware best applicable: {(payload.get('regime_aware_fx_policy') or {}).get('best_candidate', '-')}",
        "",
        "## cases",
    ]
    for case in payload.get("cases", []):
        lines.append(
            "- {date}: {current}->{soft} / status={status} / next={next_date} / class={classification} / 4w={s4} / 13w={s13} / 26w={s26} / similar={similar}".format(
                date=case.get("generated_at", "-"),
                current=case.get("current_final_action", "-"),
                soft=case.get("fx_soft_cap_action", "-"),
                status=case.get("review_status", "-"),
                next_date=case.get("next_review_date", "-"),
                classification=case.get("classification", "-"),
                s4=case.get("4w_return_status", "-"),
                s13=case.get("13w_return_status", "-"),
                s26=case.get("26w_return_status", "-"),
                similar=case.get("similar_historical_case_count", 0),
            )
        )
    if not payload.get("cases"):
        lines.append("- no tracked cases")
    return "\n".join(lines) + "\n"


def run_fx_soft_cap_watchlist(
    history_dir: str | Path = "project/reports/history",
    price_points_json: str | Path = "project/reports/validation_prices.json",
    reports_dir: str | Path = "project/reports",
    config_path: str | Path = "project/config.yaml",
    benchmark_price_points_json: str | Path | None = None,
    historical_replay_json: str | Path = "project/reports/fx_soft_cap_historical_replay.json",
) -> dict[str, Any]:
    price_path = Path(price_points_json)
    if not price_path.exists():
        return {"status": "missing_price_points", "price_points_json": str(price_path)}
    benchmark_path = Path(benchmark_price_points_json) if benchmark_price_points_json else None
    config = load_config(config_path)
    payload = build_fx_soft_cap_watchlist(
        load_raw_history_entries(history_dir),
        _load_price_points(price_path),
        config.get("thresholds", {}),
        _load_price_points(benchmark_path) if benchmark_path and benchmark_path.exists() else None,
        _load_historical_replay(historical_replay_json),
    )
    json_path, markdown_path = write_fx_soft_cap_watchlist(payload, reports_dir)
    return {
        "status": payload["status"],
        "tracked_case_count": payload["tracked_case_count"],
        "waiting_future_data_count": payload["waiting_future_data_count"],
        "adoption_decision": payload["adoption_decision"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _watchlist_row(case: dict[str, Any], today: date, historical_replay: dict[str, Any]) -> dict[str, Any]:
    generated = _parse_date(case.get("generated_at"))
    statuses = {horizon: _return_status(case, horizon) for horizon in HORIZONS_DAYS}
    similar = _similarity_for_case(case, historical_replay)
    conditional = evaluate_all_conditional_candidates(case)
    regime = classify_market_regime(case)
    regime_aware = evaluate_all_regime_aware_fx_policies(case)
    return {
        "generated_at": case.get("generated_at"),
        "current_final_action": case.get("current_final_action"),
        "fx_soft_cap_action": case.get("fx_soft_cap_action"),
        "fx_flags": case.get("fx_flags", []),
        "risk_stage": case.get("risk_stage"),
        "reliability_level": case.get("reliability_level"),
        "score": case.get("score"),
        "recovery_evidence": case.get("recovery_evidence", {}),
        "4w_return_status": statuses["4w"],
        "13w_return_status": statuses["13w"],
        "26w_return_status": statuses["26w"],
        "classification": case.get("classification", "inconclusive"),
        "classification_reasons": case.get("classification_reasons", []),
        "next_review_date": _next_review_date(generated, statuses, today),
        "review_status": _review_status(statuses),
        "similar_historical_case_count": similar["similar_historical_case_count"],
        "similar_case_mean_13w_excess_return": similar["similar_case_mean_13w_excess_return"],
        "similar_case_worst_dd": similar["similar_case_worst_dd"],
        "similarity_note": similar["similarity_note"],
        "conditional_candidates": conditional,
        "detected_regime": regime.get("regime", "uncertain"),
        "regime_reasons": regime.get("regime_reasons", []),
        "regime_aware_candidate_actions": regime_aware,
        "best_diagnostic_candidate": _best_regime_aware_candidate(regime_aware),
        "still_blocked_reason": _still_blocked_reason(regime_aware),
    }


def _conditional_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "tracked_case_count": len(cases),
        "fx_soft_cap_applicable_count": len(cases),
        "still_blocked_count": 0,
        "reason_distribution": {},
    }
    blocked_reasons: dict[str, int] = {}
    for candidate in CANDIDATE_NAMES:
        applicable = 0
        for case in cases:
            evaluation = (case.get("conditional_candidates") or {}).get(candidate) or {}
            if evaluation.get("applies"):
                applicable += 1
            else:
                for reason in evaluation.get("failed_conditions", [])[:3]:
                    blocked_reasons[str(reason)] = blocked_reasons.get(str(reason), 0) + 1
        result[f"{candidate}_applicable_count"] = applicable
    result["still_blocked_count"] = sum(1 for case in cases if not any(row.get("applies") for row in (case.get("conditional_candidates") or {}).values()))
    result["reason_distribution"] = blocked_reasons
    return result


def _regime_aware_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    regime_counts: dict[str, int] = {}
    result: dict[str, Any] = {
        "tracked_case_count": len(cases),
        "adoption_decision": "hold",
        "candidate_applicable_count": {},
        "regime_counts": regime_counts,
    }
    for case in cases:
        regime = str(case.get("detected_regime", "uncertain"))
        regime_counts[regime] = regime_counts.get(regime, 0) + 1
    best = "-"
    best_count = -1
    for candidate in REGIME_AWARE_CANDIDATES:
        count = sum(1 for case in cases if ((case.get("regime_aware_candidate_actions") or {}).get(candidate) or {}).get("applies"))
        result["candidate_applicable_count"][candidate] = count
        if count > best_count:
            best = candidate
            best_count = count
    result["best_candidate"] = best
    result["normal_recovery_cases"] = regime_counts.get("normal", 0) + regime_counts.get("recovery", 0)
    result["stress_cases"] = sum(regime_counts.get(key, 0) for key in ("rate_shock", "risk_off", "credit_stress", "crash_or_drawdown"))
    return result


def _best_regime_aware_candidate(evaluations: dict[str, dict[str, Any]]) -> str:
    for candidate in REGIME_AWARE_CANDIDATES:
        if (evaluations.get(candidate) or {}).get("applies"):
            return candidate
    return "-"


def _still_blocked_reason(evaluations: dict[str, dict[str, Any]]) -> str | None:
    if any(row.get("applies") for row in evaluations.values()):
        return None
    reasons = [str(row.get("block_reason")) for row in evaluations.values() if row.get("block_reason")]
    return reasons[0] if reasons else "no_regime_aware_candidate_applies"


def _load_historical_replay(path: str | Path) -> dict[str, Any]:
    return _load_json(path)


def _load_json(path: str | Path) -> dict[str, Any]:
    replay_path = Path(path)
    if not replay_path.exists():
        return {}
    try:
        return json.loads(replay_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _historical_similarity_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {"status": "not_available", "similar_historical_case_count": 0}
    return {
        "status": payload.get("status", "ok"),
        "similar_historical_case_count": payload.get("fx_soft_cap_buy_candidate_count", 0),
        "mean_13w_excess_return": ((payload.get("return_summary") or {}).get("13w") or {}).get("mean_excess_return"),
        "worst_13w_max_drawdown": ((payload.get("return_summary") or {}).get("13w") or {}).get("worst_max_drawdown"),
    }


def _similarity_for_case(case: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    cases = payload.get("cases") or []
    if not cases:
        return {
            "similar_historical_case_count": 0,
            "similar_case_mean_13w_excess_return": None,
            "similar_case_worst_dd": None,
            "similarity_note": "insufficient_similar_history",
        }
    flags = set(case.get("fx_flags") or [])
    risk_stage = case.get("risk_stage")
    matched = [
        item
        for item in cases
        if flags.intersection(set(item.get("fx_flags") or [])) and (risk_stage in {None, item.get("risk_stage")} or item.get("risk_stage") is None)
    ]
    if not matched:
        return {
            "similar_historical_case_count": 0,
            "similar_case_mean_13w_excess_return": None,
            "similar_case_worst_dd": None,
            "similarity_note": "insufficient_similar_history",
        }
    excess = [float(value) for item in matched if (value := (item.get("excess_returns") or {}).get("13w")) is not None]
    drawdowns = [float(value) for item in matched if (value := (item.get("max_drawdowns") or {}).get("13w")) is not None]
    return {
        "similar_historical_case_count": len(matched),
        "similar_case_mean_13w_excess_return": round(sum(excess) / len(excess), 6) if excess else None,
        "similar_case_worst_dd": min(drawdowns) if drawdowns else None,
        "similarity_note": "matched_by_fx_flags",
    }


def _return_status(case: dict[str, Any], horizon: str) -> str:
    return "available" if (case.get("forward_returns") or {}).get(horizon) is not None else "missing"


def _review_status(statuses: dict[str, str]) -> str:
    if statuses["26w"] == "available":
        return "ready_for_review"
    if statuses["13w"] == "available":
        return "waiting_26w"
    if statuses["4w"] == "available":
        return "waiting_13w"
    return "waiting_4w"


def _next_review_date(generated: date | None, statuses: dict[str, str], today: date) -> str:
    if generated is None:
        return today.isoformat()
    if statuses["4w"] == "missing":
        return (generated + timedelta(days=HORIZONS_DAYS["4w"])).isoformat()
    if statuses["13w"] == "missing":
        return (generated + timedelta(days=HORIZONS_DAYS["13w"])).isoformat()
    if statuses["26w"] == "missing":
        return (generated + timedelta(days=HORIZONS_DAYS["26w"])).isoformat()
    return today.isoformat()


def _parse_date(value: Any) -> date | None:
    try:
        return datetime.fromisoformat(str(value)).date()
    except (TypeError, ValueError):
        return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build fx_soft_cap diagnostic watchlist.")
    parser.add_argument("--history-dir", default="project/reports/history")
    parser.add_argument("--price-points-json", default="project/reports/validation_prices.json")
    parser.add_argument("--benchmark-price-points-json", default=None)
    parser.add_argument("--reports-dir", default="project/reports")
    parser.add_argument("--config", default="project/config.yaml")
    parser.add_argument("--historical-replay-json", default="project/reports/fx_soft_cap_historical_replay.json")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        json.dumps(
            run_fx_soft_cap_watchlist(
                args.history_dir,
                args.price_points_json,
                args.reports_dir,
                args.config,
                args.benchmark_price_points_json,
                args.historical_replay_json,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
