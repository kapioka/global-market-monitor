from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

from project.buy_window_diagnostics import load_raw_history_entries

HORIZONS_DAYS = {"4w": 28, "13w": 91, "26w": 182}


def build_buy_window_case_study(
    history_entries: list[dict[str, Any]],
    price_points: list[dict[str, Any]],
    benchmark_price_points: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    prices = _normalize_prices(price_points)
    benchmark_prices = _normalize_prices(benchmark_price_points or price_points)
    cases = []
    for entry in history_entries:
        spot = entry.get("spot_signal") or {}
        decision = spot.get("action_decision") or {}
        layers = spot.get("action_layers") or {}
        market_raw = str(
            layers.get("market_raw_action")
            or decision.get("market_raw_action")
            or decision.get("raw_action")
            or spot.get("legacy_action")
            or spot.get("action")
            or ""
        )
        final = str(layers.get("final_action") or decision.get("final_action") or decision.get("action") or spot.get("action") or "")
        if market_raw != "buy_window" or final == "buy_window":
            continue
        generated_at = _parse_datetime(entry.get("generated_at"))
        returns = _forward_metrics(generated_at, prices, benchmark_prices) if generated_at else _empty_metrics()
        cases.append(_case_row(entry, market_raw, final, returns))
    return {
        "status": "ok",
        "total_history_count": len(history_entries),
        "case_count": len(cases),
        "cases": cases,
        "classification_counts": _classification_counts(cases),
    }


def write_buy_window_case_study(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "buy_window_case_study.json"
    markdown_path = reports_path / "buy_window_case_study.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_buy_window_case_study_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_buy_window_case_study_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# buy_window case study",
        "",
        f"- status: {payload.get('status')}",
        f"- total history count: {payload.get('total_history_count', 0)}",
        f"- case count: {payload.get('case_count', 0)}",
        f"- classification counts: {payload.get('classification_counts', {})}",
        "",
    ]
    cases = payload.get("cases") or []
    if not cases:
        lines.append("raw buy_window から final で降格されたケースはありません。")
        return "\n".join(lines) + "\n"
    for case in cases:
        lines.extend(
            [
                f"## {case.get('generated_at', '-')}",
                f"- transition: {case.get('action_layer_transition', '-')}",
                f"- classification: {case.get('classification', '-')}",
                f"- reliability: {case.get('data_reliability', {}).get('level', '-')} / {', '.join(case.get('reliability_policy_reasons', [])) or '-'}",
                f"- risk stage: {case.get('risk_lines', {}).get('stage_key', '-')}",
                f"- recovery: {case.get('recovery_evidence', {}).get('grade', '-')} / {case.get('recovery_evidence', {}).get('score', '-')}",
                f"- blocker: {case.get('blocker_assessment', {}).get('level', '-')} / {', '.join(case.get('blocker_assessment', {}).get('primary_reasons', [])) or '-'}",
                f"- 4w: return={_fmt(case.get('forward_returns', {}).get('4w'))} / excess={_fmt(case.get('excess_returns', {}).get('4w'))} / dd={_fmt(case.get('max_drawdowns', {}).get('4w'))}",
                f"- 13w: return={_fmt(case.get('forward_returns', {}).get('13w'))} / excess={_fmt(case.get('excess_returns', {}).get('13w'))} / dd={_fmt(case.get('max_drawdowns', {}).get('13w'))}",
                f"- 26w: return={_fmt(case.get('forward_returns', {}).get('26w'))} / excess={_fmt(case.get('excess_returns', {}).get('26w'))} / dd={_fmt(case.get('max_drawdowns', {}).get('26w'))}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def run_buy_window_case_study(
    history_dir: str | Path = "project/reports/history",
    price_points_json: str | Path = "project/reports/validation_prices.json",
    reports_dir: str | Path = "project/reports",
    benchmark_price_points_json: str | Path | None = None,
) -> dict[str, Any]:
    price_path = Path(price_points_json)
    if not price_path.exists():
        return {"status": "missing_price_points", "price_points_json": str(price_path)}
    benchmark_path = Path(benchmark_price_points_json) if benchmark_price_points_json else None
    entries = load_raw_history_entries(history_dir)
    payload = build_buy_window_case_study(
        entries,
        _load_price_points(price_path),
        _load_price_points(benchmark_path) if benchmark_path and benchmark_path.exists() else None,
    )
    json_path, markdown_path = write_buy_window_case_study(payload, reports_dir)
    return {
        "status": payload["status"],
        "history_count": len(entries),
        "case_count": payload["case_count"],
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _case_row(entry: dict[str, Any], market_raw: str, final: str, metrics: dict[str, dict[str, float | None]]) -> dict[str, Any]:
    spot = entry.get("spot_signal") or {}
    decision = spot.get("action_decision") or {}
    layers = spot.get("action_layers") or {}
    risk_adjusted = str(
        layers.get("risk_adjusted_action")
        or decision.get("risk_adjusted_action")
        or decision.get("raw_action")
        or spot.get("action")
        or final
        or ""
    )
    return {
        "generated_at": entry.get("generated_at"),
        "source_history": entry.get("_source_file"),
        "market_raw_action": market_raw,
        "risk_adjusted_action": risk_adjusted,
        "final_action": final,
        "action_layer_transition": f"{market_raw}->{risk_adjusted}->{final}",
        "layer_reasons": (layers.get("layer_reasons") or decision.get("layer_reasons") or {}),
        "reliability_policy_reasons": decision.get("policy_reasons") or decision.get("cap_reason") or [],
        "risk_lines": {
            "stage_key": (entry.get("risk_lines") or {}).get("stage_key"),
            "stage_label": (entry.get("risk_lines") or {}).get("stage_label"),
            "decision_level": (entry.get("risk_lines") or {}).get("decision_level"),
            "trigger_path": (entry.get("risk_lines") or {}).get("trigger_path", []),
        },
        "data_reliability": entry.get("data_reliability") or {},
        "recovery_evidence": spot.get("recovery_evidence") or {},
        "blocker_assessment": spot.get("blocker_assessment") or {},
        "forward_returns": metrics["forward_returns"],
        "benchmark_returns": metrics["benchmark_returns"],
        "excess_returns": metrics["excess_returns"],
        "max_drawdowns": metrics["max_drawdowns"],
        "classification": _classify_case(metrics),
    }


def _forward_metrics(
    generated_at: datetime,
    prices: list[dict[str, Any]],
    benchmark_prices: list[dict[str, Any]],
) -> dict[str, dict[str, float | None]]:
    current = _price_at_or_after(prices, generated_at)
    current_benchmark = _price_at_or_after(benchmark_prices, generated_at)
    if not current:
        return _empty_metrics()
    forward_returns: dict[str, float | None] = {}
    benchmark_returns: dict[str, float | None] = {}
    excess_returns: dict[str, float | None] = {}
    max_drawdowns: dict[str, float | None] = {}
    for label, days in HORIZONS_DAYS.items():
        future = _price_at_or_after(prices, generated_at, offset_days=days)
        future_benchmark = _price_at_or_after(benchmark_prices, generated_at, offset_days=days)
        forward = _forward_return(current["price"], future["price"]) if future else None
        benchmark = _forward_return(current_benchmark["price"], future_benchmark["price"]) if current_benchmark and future_benchmark else None
        forward_returns[label] = forward
        benchmark_returns[label] = benchmark
        excess_returns[label] = round(forward - benchmark, 6) if forward is not None and benchmark is not None else None
        max_drawdowns[label] = _max_drawdown_between(prices, current["date"], future["date"]) if future else None
    return {
        "forward_returns": forward_returns,
        "benchmark_returns": benchmark_returns,
        "excess_returns": excess_returns,
        "max_drawdowns": max_drawdowns,
    }


def _classify_case(metrics: dict[str, dict[str, float | None]]) -> str:
    returns = metrics.get("forward_returns", {})
    excess = metrics.get("excess_returns", {})
    drawdowns = metrics.get("max_drawdowns", {})
    if all(returns.get(horizon) is None for horizon in HORIZONS_DAYS):
        return "inconclusive"
    return_13w = returns.get("13w")
    excess_13w = excess.get("13w")
    dd_13w = drawdowns.get("13w")
    if (return_13w is not None and return_13w <= -0.03) or (dd_13w is not None and dd_13w <= -0.08):
        return "beneficial_block"
    if (
        return_13w is not None
        and return_13w >= 0.03
        and (excess_13w is None or excess_13w >= 0.0)
        and (dd_13w is None or dd_13w > -0.05)
    ):
        return "overblocked"
    return "inconclusive"


def _classification_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    result = {"beneficial_block": 0, "overblocked": 0, "inconclusive": 0}
    for case in cases:
        key = str(case.get("classification", "inconclusive"))
        result[key] = result.get(key, 0) + 1
    return result


def _normalize_prices(price_points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for point in price_points:
        try:
            normalized.append({"date": datetime.fromisoformat(str(point["date"])), "price": float(point["price"])})
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(normalized, key=lambda item: item["date"])


def _price_at_or_after(prices: list[dict[str, Any]], date_value: datetime, offset_days: int = 0) -> dict[str, Any] | None:
    target_date = datetime.combine(date_value.date(), time.min) + timedelta(days=offset_days)
    target = target_date.timestamp()
    for point in prices:
        if point["date"].timestamp() >= target:
            return point
    return None


def _forward_return(current: float, future: float) -> float | None:
    if current == 0:
        return None
    return round((future / current) - 1.0, 6)


def _max_drawdown_between(prices: list[dict[str, Any]], start_date: datetime, end_date: datetime) -> float | None:
    window = [point["price"] for point in prices if start_date.timestamp() <= point["date"].timestamp() <= end_date.timestamp()]
    if not window:
        return None
    peak = window[0]
    max_drawdown = 0.0
    for price in window:
        peak = max(peak, price)
        if peak:
            max_drawdown = min(max_drawdown, (price / peak) - 1.0)
    return round(max_drawdown, 6)


def _empty_metrics() -> dict[str, dict[str, float | None]]:
    return {
        "forward_returns": {horizon: None for horizon in HORIZONS_DAYS},
        "benchmark_returns": {horizon: None for horizon in HORIZONS_DAYS},
        "excess_returns": {horizon: None for horizon in HORIZONS_DAYS},
        "max_drawdowns": {horizon: None for horizon in HORIZONS_DAYS},
    }


def _load_price_points(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("prices"), list):
        return payload["prices"]
    raise ValueError("price points JSON must be a list or an object with a prices list")


def _parse_datetime(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value))
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
    parser = argparse.ArgumentParser(description="Build case study for raw buy_window cases downgraded before final action.")
    parser.add_argument("--history-dir", default="project/reports/history")
    parser.add_argument("--price-points-json", default="project/reports/validation_prices.json")
    parser.add_argument("--benchmark-price-points-json", default=None)
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        json.dumps(
            run_buy_window_case_study(
                args.history_dir,
                args.price_points_json,
                args.reports_dir,
                args.benchmark_price_points_json,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
