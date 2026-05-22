from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from project.buy_candidate_near_miss import build_buy_candidate_near_miss
from project.buy_window_case_study import _empty_metrics, _forward_metrics, _load_price_points, _normalize_prices
from project.buy_window_diagnostics import load_raw_history_entries
from project.config_loader import load_config
from project.fx_risk_policy import apply_fx_policy_candidate, classify_fx_policy

HORIZONS = ("4w", "13w", "26w")


def build_fx_soft_cap_case_study(
    history_entries: list[dict[str, Any]],
    price_points: list[dict[str, Any]],
    thresholds: dict[str, Any] | None = None,
    benchmark_price_points: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    prices = _normalize_prices(price_points)
    benchmark_prices = _normalize_prices(benchmark_price_points or price_points)
    cases = []
    for entry in history_entries:
        row = _case_row(entry, prices, benchmark_prices)
        if row is not None:
            cases.append(row)
    near_miss = build_buy_candidate_near_miss(history_entries, thresholds or {})
    seen_dates = {str(case.get("generated_at")) for case in cases}
    near_miss_cases = []
    for case in near_miss.get("top_near_miss_cases", []):
        if set(case.get("missing_conditions", [])) != {"japan_fx_risk_caution"}:
            continue
        if str(case.get("generated_at")) in seen_dates:
            continue
        near_miss_cases.append(_near_miss_row(case))
    all_cases = cases + near_miss_cases
    summary = _summary(all_cases)
    return {
        "status": "ok",
        "policy_status": "diagnostic_only",
        "adoption_decision": "hold",
        "total_history_count": len(history_entries),
        "fx_soft_cap_buy_candidate_count": summary["fx_soft_cap_buy_candidate_count"],
        "current_watch_to_fx_soft_cap_buy_candidate_count": summary["current_watch_to_fx_soft_cap_buy_candidate_count"],
        "future_data_available_count": summary["future_data_available_count"],
        "waiting_future_data_count": summary["waiting_future_data_count"],
        "classification_counts": summary["classification_counts"],
        "return_summary": summary["return_summary"],
        "cases": all_cases,
    }


def write_fx_soft_cap_case_study(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "fx_soft_cap_case_study.json"
    markdown_path = reports_path / "fx_soft_cap_case_study.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_fx_soft_cap_case_study_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_fx_soft_cap_case_study_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# fx_soft_cap case study",
        "",
        f"- status: {payload.get('status')}",
        f"- policy_status: {payload.get('policy_status')}",
        f"- adoption_decision: {payload.get('adoption_decision')}",
        f"- total history count: {payload.get('total_history_count', 0)}",
        f"- fx_soft_cap buy_candidate count: {payload.get('fx_soft_cap_buy_candidate_count', 0)}",
        f"- current watch -> fx_soft_cap buy_candidate: {payload.get('current_watch_to_fx_soft_cap_buy_candidate_count', 0)}",
        f"- future data available count: {payload.get('future_data_available_count', 0)}",
        f"- waiting future data count: {payload.get('waiting_future_data_count', 0)}",
        f"- classification counts: {payload.get('classification_counts', {})}",
        "",
        "## cases",
    ]
    for case in payload.get("cases", [])[:20]:
        lines.append(
            "- {date}: {current}->{soft} / raw={raw} / class={classification} / missing={missing} / fx={flags} / 13w={ret}".format(
                date=case.get("generated_at", "-"),
                current=case.get("current_final_action", "-"),
                soft=case.get("fx_soft_cap_action", "-"),
                raw=case.get("raw_action", "-"),
                classification=case.get("classification", "-"),
                missing=", ".join(case.get("missing_conditions", [])) or "-",
                flags=", ".join(case.get("fx_flags", [])) or "-",
                ret=_fmt(case.get("forward_returns", {}).get("13w")),
            )
        )
    if not payload.get("cases"):
        lines.append("- no fx_soft_cap cases")
    return "\n".join(lines) + "\n"


def run_fx_soft_cap_case_study(
    history_dir: str | Path = "project/reports/history",
    price_points_json: str | Path = "project/reports/validation_prices.json",
    reports_dir: str | Path = "project/reports",
    config_path: str | Path = "project/config.yaml",
    benchmark_price_points_json: str | Path | None = None,
) -> dict[str, Any]:
    price_path = Path(price_points_json)
    if not price_path.exists():
        return {"status": "missing_price_points", "price_points_json": str(price_path)}
    benchmark_path = Path(benchmark_price_points_json) if benchmark_price_points_json else None
    config = load_config(config_path)
    payload = build_fx_soft_cap_case_study(
        load_raw_history_entries(history_dir),
        _load_price_points(price_path),
        config.get("thresholds", {}),
        _load_price_points(benchmark_path) if benchmark_path and benchmark_path.exists() else None,
    )
    json_path, markdown_path = write_fx_soft_cap_case_study(payload, reports_dir)
    return {
        "status": payload["status"],
        "case_count": len(payload["cases"]),
        "adoption_decision": payload["adoption_decision"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _case_row(entry: dict[str, Any], prices: list[dict[str, Any]], benchmark_prices: list[dict[str, Any]]) -> dict[str, Any] | None:
    raw = _raw_action(entry)
    current = _current_final_action(entry)
    spot = entry.get("spot_signal") or {}
    classification = classify_fx_policy(entry.get("japan_risk") or {}, spot.get("blocker_assessment") or {})
    soft = apply_fx_policy_candidate(raw, classification, "fx_soft_cap")
    if soft["final_action"] != "buy_candidate" or current == "buy_candidate":
        return None
    metrics = _metrics_for_entry(entry, prices, benchmark_prices)
    return _base_case(entry, raw, current, soft["final_action"], classification, metrics, [])


def _near_miss_row(case: dict[str, Any]) -> dict[str, Any]:
    metrics = _empty_metrics()
    return {
        "generated_at": case.get("generated_at"),
        "source_history": case.get("source_history"),
        "raw_action": case.get("final_action", "watch"),
        "risk_adjusted_action": case.get("final_action", "watch"),
        "current_final_action": case.get("final_action", "watch"),
        "fx_soft_cap_action": "buy_candidate",
        "fx_flags": [flag for flag in case.get("blocker_flags", []) if "fx" in str(flag) or "japan" in str(flag)],
        "risk_stage": case.get("risk_stage"),
        "reliability_level": case.get("reliability_level"),
        "score": case.get("score"),
        "recovery_evidence": {"grade": case.get("recovery_grade"), "score": case.get("recovery_score")},
        "forward_returns": metrics["forward_returns"],
        "benchmark_returns": metrics["benchmark_returns"],
        "excess_returns": metrics["excess_returns"],
        "max_drawdowns": metrics["max_drawdowns"],
        "classification": "inconclusive",
        "classification_reasons": ["missing_4w", "missing_13w", "missing_26w"],
        "missing_conditions": case.get("missing_conditions", []),
        "case_source": "near_miss",
    }


def _base_case(
    entry: dict[str, Any],
    raw: str,
    current: str,
    soft_action: str,
    classification: dict[str, Any],
    metrics: dict[str, dict[str, float | None]],
    missing_conditions: list[str],
) -> dict[str, Any]:
    spot = entry.get("spot_signal") or {}
    return {
        "generated_at": entry.get("generated_at"),
        "source_history": entry.get("_source_file"),
        "raw_action": raw,
        "risk_adjusted_action": (spot.get("action_decision") or {}).get("risk_adjusted_action", spot.get("action")),
        "current_final_action": current,
        "fx_soft_cap_action": soft_action,
        "fx_flags": classification.get("flags", []),
        "risk_stage": (entry.get("risk_lines") or {}).get("stage_key"),
        "reliability_level": (entry.get("data_reliability") or {}).get("level"),
        "score": spot.get("adjusted_score", (entry.get("score") or {}).get("total_score")),
        "recovery_evidence": spot.get("recovery_evidence") or {},
        "forward_returns": metrics["forward_returns"],
        "benchmark_returns": metrics["benchmark_returns"],
        "excess_returns": metrics["excess_returns"],
        "max_drawdowns": metrics["max_drawdowns"],
        "classification": _classify(metrics),
        "classification_reasons": _classification_reasons(metrics),
        "missing_conditions": missing_conditions,
        "case_source": "fx_policy",
    }


def _summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    classifications = Counter(str(case.get("classification", "inconclusive")) for case in cases)
    return {
        "fx_soft_cap_buy_candidate_count": sum(1 for case in cases if case.get("fx_soft_cap_action") == "buy_candidate"),
        "current_watch_to_fx_soft_cap_buy_candidate_count": sum(
            1 for case in cases if case.get("current_final_action") == "watch" and case.get("fx_soft_cap_action") == "buy_candidate"
        ),
        "future_data_available_count": sum(1 for case in cases if any(value is not None for value in (case.get("forward_returns") or {}).values())),
        "waiting_future_data_count": sum(1 for case in cases if str(case.get("classification")) == "inconclusive"),
        "classification_counts": dict(classifications),
        "return_summary": _return_summary(cases),
    }


def _classify(metrics: dict[str, dict[str, float | None]]) -> str:
    returns = metrics.get("forward_returns", {})
    excess = metrics.get("excess_returns", {})
    drawdowns = metrics.get("max_drawdowns", {})
    if all(returns.get(horizon) is None for horizon in HORIZONS):
        return "inconclusive"
    return_13w = returns.get("13w")
    excess_13w = excess.get("13w")
    dd_13w = drawdowns.get("13w")
    if return_13w is None and returns.get("26w") is None:
        ret_4w = returns.get("4w")
        dd_4w = drawdowns.get("4w")
        if ret_4w is not None and ret_4w > 0.02 and (dd_4w is None or dd_4w > -0.04):
            return "promising_candidate"
        return "inconclusive"
    if (return_13w is not None and return_13w <= -0.03) or (dd_13w is not None and dd_13w <= -0.08):
        return "correctly_blocked"
    if return_13w is not None and return_13w >= 0.03 and (excess_13w is None or excess_13w >= 0.0) and (dd_13w is None or dd_13w > -0.05):
        return "overblocked_by_current"
    return "promising_candidate"


def _classification_reasons(metrics: dict[str, dict[str, float | None]]) -> list[str]:
    returns = metrics.get("forward_returns", {})
    missing = [f"missing_{horizon}" for horizon in HORIZONS if returns.get(horizon) is None]
    return missing or ["future_data_available"]


def _return_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for horizon in ("4w", "13w", "26w"):
        returns = [float(value) for case in cases if (value := (case.get("forward_returns") or {}).get(horizon)) is not None]
        excess = [float(value) for case in cases if (value := (case.get("excess_returns") or {}).get(horizon)) is not None]
        drawdowns = [float(value) for case in cases if (value := (case.get("max_drawdowns") or {}).get(horizon)) is not None]
        result[horizon] = {
            "count": len(returns),
            "mean_return": round(sum(returns) / len(returns), 6) if returns else None,
            "mean_excess_return": round(sum(excess) / len(excess), 6) if excess else None,
            "worst_max_drawdown": min(drawdowns) if drawdowns else None,
        }
    return result


def _raw_action(entry: dict[str, Any]) -> str:
    spot = entry.get("spot_signal") or {}
    decision = spot.get("action_decision") or {}
    layers = spot.get("action_layers") or {}
    return str(layers.get("market_raw_action") or decision.get("market_raw_action") or decision.get("raw_action") or spot.get("legacy_action") or spot.get("action") or "wait")


def _current_final_action(entry: dict[str, Any]) -> str:
    spot = entry.get("spot_signal") or {}
    decision = spot.get("action_decision") or {}
    layers = spot.get("action_layers") or {}
    return str(layers.get("final_action") or decision.get("final_action") or decision.get("action") or spot.get("action") or "wait")


def _metrics_for_entry(entry: dict[str, Any], prices: list[dict[str, Any]], benchmark_prices: list[dict[str, Any]]) -> dict[str, dict[str, float | None]]:
    from datetime import datetime

    try:
        generated_at = datetime.fromisoformat(str(entry.get("generated_at")))
    except (TypeError, ValueError):
        return _empty_metrics()
    return _forward_metrics(generated_at, prices, benchmark_prices)


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build fx_soft_cap diagnostic case study.")
    parser.add_argument("--history-dir", default="project/reports/history")
    parser.add_argument("--price-points-json", default="project/reports/validation_prices.json")
    parser.add_argument("--benchmark-price-points-json", default=None)
    parser.add_argument("--reports-dir", default="project/reports")
    parser.add_argument("--config", default="project/config.yaml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        json.dumps(
            run_fx_soft_cap_case_study(
                args.history_dir,
                args.price_points_json,
                args.reports_dir,
                args.config,
                args.benchmark_price_points_json,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
