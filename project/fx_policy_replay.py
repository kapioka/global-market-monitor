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

CANDIDATES = ("current", "fx_note_only", "fx_soft_cap", "fx_high_only_block")
TARGET_CASE_DATE = "2026-05-07T07:30:00"


def build_fx_policy_replay(
    history_entries: list[dict[str, Any]],
    price_points: list[dict[str, Any]],
    thresholds: dict[str, Any] | None = None,
    benchmark_price_points: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    prices = _normalize_prices(price_points)
    benchmark_prices = _normalize_prices(benchmark_price_points or price_points)
    candidate_rows = [_candidate_summary(candidate, history_entries, prices, benchmark_prices) for candidate in CANDIDATES]
    target = _target_case(history_entries, prices, benchmark_prices)
    near_miss = build_buy_candidate_near_miss(history_entries, thresholds or {})
    near_miss_effect = _near_miss_effect(near_miss.get("top_near_miss_cases", []))
    return {
        "status": "ok",
        "policy": "diagnostic_only_current_policy_unchanged",
        "total_history_count": len(history_entries),
        "candidates": candidate_rows,
        "target_case": target,
        "near_miss_effect": near_miss_effect,
    }


def write_fx_policy_replay(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "fx_policy_replay.json"
    markdown_path = reports_path / "fx_policy_replay.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_fx_policy_replay_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_fx_policy_replay_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# FX policy replay",
        "",
        f"- status: {payload.get('status')}",
        f"- policy: {payload.get('policy')}",
        f"- total history count: {payload.get('total_history_count', 0)}",
        "",
        "| candidate | final buy_window | final buy_candidate | FX buy_window downgrade | FX candidate block | overblocked | beneficial | inconclusive |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload.get("candidates", []):
        lines.append(
            "| {label} | {bw} | {bc} | {downgrade} | {blocked} | {over} | {beneficial} | {inconclusive} |".format(
                label=row.get("candidate"),
                bw=row.get("final_buy_window_count", 0),
                bc=row.get("final_buy_candidate_count", 0),
                downgrade=row.get("buy_window_downgraded_by_fx_count", 0),
                blocked=row.get("buy_candidate_blocked_by_fx_count", 0),
                over=row.get("classification_counts", {}).get("overblocked", 0),
                beneficial=row.get("classification_counts", {}).get("beneficial_fx_downgrade", 0),
                inconclusive=row.get("classification_counts", {}).get("inconclusive", 0),
            )
        )
    target = payload.get("target_case") or {}
    lines.extend(["", "## 2026-05-07 case"])
    for candidate, row in (target.get("candidate_actions") or {}).items():
        lines.append(f"- {candidate}: {row.get('final_action')} / note={row.get('execution_note') or '-'}")
    lines.extend(
        [
            "",
            "## buy_candidate near-miss effect",
            f"- near_miss_count: {(payload.get('near_miss_effect') or {}).get('near_miss_count', 0)}",
            f"- converted_to_buy_candidate_by_fx_note_only: {(payload.get('near_miss_effect') or {}).get('converted_to_buy_candidate_by_fx_note_only', 0)}",
            f"- converted_to_buy_candidate_by_fx_soft_cap: {(payload.get('near_miss_effect') or {}).get('converted_to_buy_candidate_by_fx_soft_cap', 0)}",
            f"- still_blocked_count: {(payload.get('near_miss_effect') or {}).get('still_blocked_count', 0)}",
            f"- top_remaining_missing_conditions: {(payload.get('near_miss_effect') or {}).get('top_remaining_missing_conditions', {})}",
            "",
            "This replay is diagnostic only. Current final action policy is unchanged.",
        ]
    )
    return "\n".join(lines) + "\n"


def run_fx_policy_replay(
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
    payload = build_fx_policy_replay(
        load_raw_history_entries(history_dir),
        _load_price_points(price_path),
        config.get("thresholds", {}),
        _load_price_points(benchmark_path) if benchmark_path and benchmark_path.exists() else None,
    )
    json_path, markdown_path = write_fx_policy_replay(payload, reports_dir)
    return {"status": payload["status"], "json_path": str(json_path), "markdown_path": str(markdown_path)}


def _candidate_summary(candidate: str, entries: list[dict[str, Any]], prices: list[dict[str, Any]], benchmark_prices: list[dict[str, Any]]) -> dict[str, Any]:
    final_counts: Counter[str] = Counter()
    classifications: Counter[str] = Counter()
    buy_window_downgraded = 0
    buy_candidate_blocked = 0
    metrics_rows = []
    for entry in entries:
        raw = _raw_action(entry)
        current_final = _current_final_action(entry)
        classification = classify_fx_policy(entry.get("japan_risk") or {}, (entry.get("spot_signal") or {}).get("blocker_assessment") or {})
        final = current_final if candidate == "current" else apply_fx_policy_candidate(raw, classification, candidate)["final_action"]
        final_counts[final] += 1
        if classification["fx_policy_classification"] != "none" and raw == "buy_window" and final != "buy_window":
            buy_window_downgraded += 1
            classifications[_classify_entry(entry, prices, benchmark_prices)] += 1
        if classification["fx_policy_classification"] != "none" and raw == "buy_candidate" and final != "buy_candidate":
            buy_candidate_blocked += 1
        if raw in {"buy_window", "buy_candidate"}:
            metrics_rows.append(_metrics_for_entry(entry, prices, benchmark_prices))
    return {
        "candidate": candidate,
        "raw_buy_window_count": sum(1 for entry in entries if _raw_action(entry) == "buy_window"),
        "raw_buy_candidate_count": sum(1 for entry in entries if _raw_action(entry) == "buy_candidate"),
        "final_buy_window_count": final_counts.get("buy_window", 0),
        "final_buy_candidate_count": final_counts.get("buy_candidate", 0),
        "buy_window_downgraded_by_fx_count": buy_window_downgraded,
        "buy_candidate_blocked_by_fx_count": buy_candidate_blocked,
        "classification_counts": dict(classifications),
        "return_summary": _return_summary(metrics_rows),
    }


def _target_case(entries: list[dict[str, Any]], prices: list[dict[str, Any]], benchmark_prices: list[dict[str, Any]]) -> dict[str, Any]:
    entry = next((item for item in entries if str(item.get("generated_at")) == TARGET_CASE_DATE), None)
    if not entry:
        return {"status": "missing", "generated_at": TARGET_CASE_DATE}
    raw = _raw_action(entry)
    current = _current_final_action(entry)
    classification = classify_fx_policy(entry.get("japan_risk") or {}, (entry.get("spot_signal") or {}).get("blocker_assessment") or {})
    candidate_actions = {}
    for candidate in CANDIDATES:
        result = {"final_action": current, "execution_note": classification.get("fx_execution_note", "")}
        if candidate != "current":
            result = apply_fx_policy_candidate(raw, classification, candidate)
        candidate_actions[candidate] = result
    return {
        "status": "ok",
        "generated_at": TARGET_CASE_DATE,
        "raw_action": raw,
        "current_final_action": current,
        "fx_policy_classification": classification,
        "candidate_actions": candidate_actions,
        "future_metrics": _metrics_for_entry(entry, prices, benchmark_prices),
        "classification": _classify_entry(entry, prices, benchmark_prices),
    }


def _near_miss_effect(cases: list[dict[str, Any]]) -> dict[str, Any]:
    converted_note = 0
    converted_soft = 0
    still_blocked = 0
    remaining: Counter[str] = Counter()
    for case in cases:
        missing = set(case.get("missing_conditions", []))
        without_fx = missing - {"japan_fx_risk_caution"}
        if not without_fx:
            converted_note += 1
            converted_soft += 1
        elif without_fx == {"score_below_candidate"}:
            still_blocked += 1
            remaining.update(without_fx)
        else:
            still_blocked += 1
            remaining.update(without_fx)
    return {
        "near_miss_count": len(cases),
        "converted_to_buy_candidate_by_fx_note_only": converted_note,
        "converted_to_buy_candidate_by_fx_soft_cap": converted_soft,
        "still_blocked_count": still_blocked,
        "top_remaining_missing_conditions": dict(remaining),
    }


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


def _classify_entry(entry: dict[str, Any], prices: list[dict[str, Any]], benchmark_prices: list[dict[str, Any]]) -> str:
    metrics = _metrics_for_entry(entry, prices, benchmark_prices)
    returns = metrics.get("forward_returns", {})
    excess = metrics.get("excess_returns", {})
    drawdowns = metrics.get("max_drawdowns", {})
    if all(returns.get(horizon) is None for horizon in ("4w", "13w", "26w")):
        return "inconclusive"
    return_13w = returns.get("13w")
    excess_13w = excess.get("13w")
    dd_13w = drawdowns.get("13w")
    if (return_13w is not None and return_13w <= -0.03) or (dd_13w is not None and dd_13w <= -0.08):
        return "beneficial_fx_downgrade"
    if return_13w is not None and return_13w >= 0.03 and (excess_13w is None or excess_13w >= 0.0) and (dd_13w is None or dd_13w > -0.05):
        return "overblocked"
    return "inconclusive"


def _return_summary(rows: list[dict[str, dict[str, float | None]]]) -> dict[str, Any]:
    result = {}
    for horizon in ("4w", "13w", "26w"):
        returns = [float(value) for row in rows if (value := row["forward_returns"].get(horizon)) is not None]
        excess = [float(value) for row in rows if (value := row["excess_returns"].get(horizon)) is not None]
        drawdowns = [float(value) for row in rows if (value := row["max_drawdowns"].get(horizon)) is not None]
        result[horizon] = {
            "count": len(returns),
            "mean_return": round(sum(returns) / len(returns), 6) if returns else None,
            "mean_excess_return": round(sum(excess) / len(excess), 6) if excess else None,
            "worst_max_drawdown": min(drawdowns) if drawdowns else None,
        }
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay diagnostic FX policy candidates without changing current policy.")
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
            run_fx_policy_replay(
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
