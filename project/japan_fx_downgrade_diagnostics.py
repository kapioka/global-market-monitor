from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from project.buy_window_case_study import _empty_metrics, _forward_metrics, _load_price_points, _normalize_prices
from project.buy_window_diagnostics import load_raw_history_entries

FX_FLAGS = {"japan_fx_risk_moderate", "japan_fx_risk_high", "foreign_asset_fx_headwind", "foreign_asset_fx_dependency"}


def build_japan_fx_downgrade_diagnostics(
    history_entries: list[dict[str, Any]],
    price_points: list[dict[str, Any]],
    benchmark_price_points: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    prices = _normalize_prices(price_points)
    benchmark_prices = _normalize_prices(benchmark_price_points or price_points)
    cases: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    for entry in history_entries:
        fx = _fx_context(entry)
        counters.update(fx["counter_keys"])
        if not fx["is_fx_downgrade"]:
            continue
        generated_at = _parse_datetime(entry.get("generated_at"))
        metrics = _forward_metrics(generated_at, prices, benchmark_prices) if generated_at else _empty_metrics()
        cases.append(_case_row(entry, fx, metrics))
    return {
        "status": "ok",
        "total_history_count": len(history_entries),
        "japan_fx_risk_moderate_count": counters.get("japan_fx_risk_moderate", 0),
        "japan_fx_risk_high_count": counters.get("japan_fx_risk_high", 0),
        "foreign_asset_fx_headwind_count": counters.get("foreign_asset_fx_headwind", 0),
        "raw_buy_window_downgraded_by_fx_count": counters.get("raw_buy_window_downgraded_by_fx", 0),
        "raw_buy_candidate_downgraded_by_fx_count": counters.get("raw_buy_candidate_downgraded_by_fx", 0),
        "classification_counts": dict(Counter(case["classification"] for case in cases)),
        "cases": cases,
    }


def write_japan_fx_downgrade_diagnostics(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "japan_fx_downgrade_diagnostics.json"
    markdown_path = reports_path / "japan_fx_downgrade_diagnostics.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_japan_fx_downgrade_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_japan_fx_downgrade_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# japan fx downgrade diagnostics",
        "",
        f"- status: {payload.get('status')}",
        f"- total history count: {payload.get('total_history_count', 0)}",
        f"- japan_fx_risk_moderate: {payload.get('japan_fx_risk_moderate_count', 0)}",
        f"- japan_fx_risk_high: {payload.get('japan_fx_risk_high_count', 0)}",
        f"- foreign_asset_fx_headwind: {payload.get('foreign_asset_fx_headwind_count', 0)}",
        f"- raw buy_window downgraded by FX: {payload.get('raw_buy_window_downgraded_by_fx_count', 0)}",
        f"- raw buy_candidate downgraded by FX: {payload.get('raw_buy_candidate_downgraded_by_fx_count', 0)}",
        f"- classification counts: {payload.get('classification_counts', {})}",
        "",
    ]
    cases = payload.get("cases") or []
    if not cases:
        lines.append("FX による raw buy_window / buy_candidate 降格ケースはありません。")
        return "\n".join(lines) + "\n"
    for case in cases:
        lines.extend(
            [
                f"## {case.get('generated_at', '-')}",
                f"- transition: {case.get('action_layer_transition', '-')}",
                f"- classification: {case.get('classification', '-')}",
                f"- fx level: {case.get('japan_risk', {}).get('level', '-')}",
                f"- fx flags: {', '.join(case.get('fx_flags', [])) or '-'}",
                f"- risk stage: {case.get('risk_stage', '-')}",
                f"- 4w: return={_fmt(case.get('forward_returns', {}).get('4w'))} / excess={_fmt(case.get('excess_returns', {}).get('4w'))} / dd={_fmt(case.get('max_drawdowns', {}).get('4w'))}",
                f"- 13w: return={_fmt(case.get('forward_returns', {}).get('13w'))} / excess={_fmt(case.get('excess_returns', {}).get('13w'))} / dd={_fmt(case.get('max_drawdowns', {}).get('13w'))}",
                f"- 26w: return={_fmt(case.get('forward_returns', {}).get('26w'))} / excess={_fmt(case.get('excess_returns', {}).get('26w'))} / dd={_fmt(case.get('max_drawdowns', {}).get('26w'))}",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def run_japan_fx_downgrade_diagnostics(
    history_dir: str | Path = "project/reports/history",
    price_points_json: str | Path = "project/reports/validation_prices.json",
    reports_dir: str | Path = "project/reports",
    benchmark_price_points_json: str | Path | None = None,
) -> dict[str, Any]:
    price_path = Path(price_points_json)
    if not price_path.exists():
        return {"status": "missing_price_points", "price_points_json": str(price_path)}
    benchmark_path = Path(benchmark_price_points_json) if benchmark_price_points_json else None
    payload = build_japan_fx_downgrade_diagnostics(
        load_raw_history_entries(history_dir),
        _load_price_points(price_path),
        _load_price_points(benchmark_path) if benchmark_path and benchmark_path.exists() else None,
    )
    json_path, markdown_path = write_japan_fx_downgrade_diagnostics(payload, reports_dir)
    return {
        "status": payload["status"],
        "history_count": payload["total_history_count"],
        "case_count": len(payload["cases"]),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def _fx_context(entry: dict[str, Any]) -> dict[str, Any]:
    spot = entry.get("spot_signal") or {}
    decision = spot.get("action_decision") or {}
    layers = spot.get("action_layers") or {}
    blocker = spot.get("blocker_assessment") or {}
    japan_risk = entry.get("japan_risk") or {}
    market_raw = str(
        layers.get("market_raw_action")
        or decision.get("market_raw_action")
        or decision.get("raw_action")
        or spot.get("legacy_action")
        or spot.get("action")
        or "wait"
    )
    risk_adjusted = str(layers.get("risk_adjusted_action") or decision.get("risk_adjusted_action") or decision.get("raw_action") or spot.get("action") or "wait")
    final = str(layers.get("final_action") or decision.get("final_action") or decision.get("action") or spot.get("action") or "wait")
    flags = set(str(flag) for flag in blocker.get("flags", [])) | set(str(flag) for flag in japan_risk.get("flags", []))
    level = str(japan_risk.get("level", ""))
    if level == "moderate":
        flags.add("japan_fx_risk_moderate")
    if level == "high":
        flags.add("japan_fx_risk_high")
    is_fx = bool(flags & FX_FLAGS)
    is_downgrade = is_fx and market_raw in {"buy_window", "buy_candidate"} and final != market_raw
    counter_keys = [flag for flag in flags if flag in FX_FLAGS]
    if is_downgrade and market_raw == "buy_window":
        counter_keys.append("raw_buy_window_downgraded_by_fx")
    if is_downgrade and market_raw == "buy_candidate":
        counter_keys.append("raw_buy_candidate_downgraded_by_fx")
    return {
        "market_raw_action": market_raw,
        "risk_adjusted_action": risk_adjusted,
        "final_action": final,
        "fx_flags": sorted(flags & FX_FLAGS),
        "is_fx_downgrade": is_downgrade,
        "counter_keys": counter_keys,
    }


def _case_row(entry: dict[str, Any], fx: dict[str, Any], metrics: dict[str, dict[str, float | None]]) -> dict[str, Any]:
    return {
        "generated_at": entry.get("generated_at"),
        "source_history": entry.get("_source_file"),
        "market_raw_action": fx["market_raw_action"],
        "risk_adjusted_action": fx["risk_adjusted_action"],
        "final_action": fx["final_action"],
        "action_layer_transition": f"{fx['market_raw_action']}->{fx['risk_adjusted_action']}->{fx['final_action']}",
        "fx_flags": fx["fx_flags"],
        "japan_risk": entry.get("japan_risk") or {},
        "risk_stage": (entry.get("risk_lines") or {}).get("stage_key"),
        "forward_returns": metrics["forward_returns"],
        "benchmark_returns": metrics["benchmark_returns"],
        "excess_returns": metrics["excess_returns"],
        "max_drawdowns": metrics["max_drawdowns"],
        "classification": _classify(metrics),
    }


def _classify(metrics: dict[str, dict[str, float | None]]) -> str:
    returns = metrics.get("forward_returns", {})
    excess = metrics.get("excess_returns", {})
    drawdowns = metrics.get("max_drawdowns", {})
    if all(returns.get(horizon) is None for horizon in ("4w", "13w", "26w")):
        return "inconclusive"
    return_13w = returns.get("13w")
    excess_13w = excess.get("13w")
    dd_13w = drawdowns.get("13w")
    if (return_13w is not None and return_13w <= -0.03) or (dd_13w is not None and dd_13w <= -0.08):
        return "beneficial_downgrade"
    if (
        return_13w is not None
        and return_13w >= 0.03
        and (excess_13w is None or excess_13w >= 0.0)
        and (dd_13w is None or dd_13w > -0.05)
    ):
        return "overblocked"
    return "inconclusive"


def _parse_datetime(value: Any) -> Any:
    from datetime import datetime

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
    parser = argparse.ArgumentParser(description="Build Japan FX downgrade diagnostics.")
    parser.add_argument("--history-dir", default="project/reports/history")
    parser.add_argument("--price-points-json", default="project/reports/validation_prices.json")
    parser.add_argument("--benchmark-price-points-json", default=None)
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        json.dumps(
            run_japan_fx_downgrade_diagnostics(
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
