from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime, time, timedelta
from statistics import median
from typing import Any

HORIZONS_DAYS = {
    "4w": 28,
    "13w": 91,
    "26w": 182,
    "52w": 364,
}
RALLY_THRESHOLD = 0.05
KNOWN_ACTIONS = ("wait", "watch", "buy_candidate", "buy_window")


def build_action_validation(
    history_entries: Iterable[dict[str, Any]],
    price_points: Iterable[dict[str, Any]],
    benchmark_price_points: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    entries = _normalize_history(history_entries)
    prices = _normalize_prices(price_points)
    benchmark_prices = _normalize_prices(benchmark_price_points or price_points)
    benchmark_source = "external" if benchmark_price_points is not None else "target_price_series"
    if not entries or len(prices) < 2:
        return {
            "status": "insufficient_data",
            "reason": "history or price data is insufficient",
            "benchmark_source": benchmark_source,
            "action_summary": {},
            "cases": [],
        }

    cases: list[dict[str, Any]] = []
    for entry in entries:
        current_price = _price_at_or_after(prices, entry["date"])
        if current_price is None:
            continue
        forward_returns = {}
        max_drawdowns = {}
        benchmark_returns = {}
        excess_returns = {}
        current_benchmark_price = _price_at_or_after(benchmark_prices, entry["date"])
        for label, days in HORIZONS_DAYS.items():
            future_price = _price_at_or_after(prices, entry["date"], offset_days=days)
            forward_return = _forward_return(current_price["price"], future_price["price"]) if future_price else None
            future_benchmark_price = _price_at_or_after(benchmark_prices, entry["date"], offset_days=days)
            benchmark_return = (
                _forward_return(current_benchmark_price["price"], future_benchmark_price["price"])
                if current_benchmark_price and future_benchmark_price
                else None
            )
            forward_returns[label] = forward_return
            benchmark_returns[label] = benchmark_return
            excess_returns[label] = (
                round(forward_return - benchmark_return, 6) if forward_return is not None and benchmark_return is not None else None
            )
            max_drawdowns[label] = _max_drawdown_between(prices, current_price["date"], future_price["date"]) if future_price else None
        cases.append(
            {
                "date": entry["date"].date().isoformat(),
                "action": entry["action"],
                "reliability_level": entry.get("reliability_level", "-"),
                "reliability_capped": entry.get("reliability_capped", False),
                "forward_returns": forward_returns,
                "benchmark_returns": benchmark_returns,
                "excess_returns": excess_returns,
                "max_drawdowns": max_drawdowns,
            }
        )

    if not cases:
        return {
            "status": "insufficient_data",
            "reason": "no history entries could be aligned with price data",
            "benchmark_source": benchmark_source,
            "action_summary": {},
            "cases": [],
        }

    return {
        "status": "ok",
        "benchmark_source": benchmark_source,
        "action_summary": _summarize_cases(cases),
        "diagnostics": _build_diagnostics(cases),
        "cases": cases,
    }


def _normalize_history(history_entries: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for entry in history_entries:
        generated_at = entry.get("generated_at")
        if not generated_at:
            continue
        try:
            stamp = datetime.fromisoformat(str(generated_at))
        except ValueError:
            continue
        spot_signal = entry.get("spot_signal", {})
        action_decision = spot_signal.get("action_decision", {})
        action = str(action_decision.get("action", spot_signal.get("action", "")) or "")
        if not action or action == "diagnostic_only":
            continue
        reliability = entry.get("data_reliability", {})
        if reliability.get("max_action") == "diagnostic_only":
            continue
        normalized.append(
            {
                "date": stamp,
                "action": action,
                "reliability_level": reliability.get("level", "-"),
                "reliability_capped": bool(action_decision.get("reliability_cap_applied", False)),
            }
        )
    return sorted(normalized, key=lambda item: item["date"])


def _normalize_prices(price_points: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for point in price_points:
        try:
            stamp = datetime.fromisoformat(str(point["date"]))
            price = float(point["price"])
        except (KeyError, TypeError, ValueError):
            continue
        normalized.append({"date": stamp, "price": price})
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


def _summarize_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    by_action: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_action[case["action"]].append(case)

    summary = {}
    for action in sorted(set(KNOWN_ACTIONS).union(by_action)):
        action_cases = by_action.get(action, [])
        horizon_summary = {}
        for horizon in HORIZONS_DAYS:
            values = [case["forward_returns"][horizon] for case in action_cases if case["forward_returns"].get(horizon) is not None]
            excess_values = [case["excess_returns"][horizon] for case in action_cases if case["excess_returns"].get(horizon) is not None]
            drawdowns = [case["max_drawdowns"][horizon] for case in action_cases if case["max_drawdowns"].get(horizon) is not None]
            horizon_summary[horizon] = {
                "count": len(values),
                "mean_return": round(sum(values) / len(values), 6) if values else None,
                "median_return": round(median(values), 6) if values else None,
                "win_rate": round(sum(1 for value in values if value > 0) / len(values), 6) if values else None,
                "negative_rate": round(sum(1 for value in values if value < 0) / len(values), 6) if values else None,
                "max_loss": min(values) if values else None,
                "max_gain": max(values) if values else None,
                "mean_max_drawdown": round(sum(drawdowns) / len(drawdowns), 6) if drawdowns else None,
                "worst_max_drawdown": min(drawdowns) if drawdowns else None,
                "mean_excess_return": round(sum(excess_values) / len(excess_values), 6) if excess_values else None,
                "median_excess_return": round(median(excess_values), 6) if excess_values else None,
                "worst_excess_return": min(excess_values) if excess_values else None,
                "excess_win_rate": round(sum(1 for value in excess_values if value > 0) / len(excess_values), 6) if excess_values else None,
            }
        summary[action] = {
            "count": len(action_cases),
            "reliability_capped_count": sum(1 for case in action_cases if case.get("reliability_capped")),
            "horizons": horizon_summary,
        }
    return summary


def _build_diagnostics(cases: list[dict[str, Any]]) -> dict[str, Any]:
    buy_window_13w = _returns_for_action(cases, "buy_window", "13w")
    buy_candidate_13w = _returns_for_action(cases, "buy_candidate", "13w")
    wait_13w = _returns_for_action(cases, "wait", "13w")
    watch_cases = [case for case in cases if case["action"] == "watch"]
    buy_candidate_cases = [case for case in cases if case["action"] == "buy_candidate"]
    watch_promotions = 0
    candidate_promotions = 0
    candidate_fallbacks = 0
    for index, case in enumerate(cases):
        if case["action"] != "watch":
            pass
        elif (following := cases[index + 1 :]) and following[0]["action"] in {"buy_candidate", "buy_window"}:
            watch_promotions += 1
        if case["action"] != "buy_candidate":
            continue
        following = cases[index + 1 :]
        if following and following[0]["action"] == "buy_window":
            candidate_promotions += 1
        if following and following[0]["action"] == "wait":
            candidate_fallbacks += 1

    return {
        "buy_window_negative_rate_13w": _rate(buy_window_13w, lambda value: value < 0),
        "buy_candidate_negative_rate_13w": _rate(buy_candidate_13w, lambda value: value < 0),
        "buy_candidate_false_positive_rate_13w": _rate(buy_candidate_13w, lambda value: value < 0),
        "wait_missed_rally_rate_13w": _rate(wait_13w, lambda value: value >= RALLY_THRESHOLD),
        "watch_to_buy_window_promotion_rate": round(watch_promotions / len(watch_cases), 6) if watch_cases else None,
        "buy_candidate_to_buy_window_transition_count": candidate_promotions,
        "buy_candidate_to_wait_fallback_count": candidate_fallbacks,
        "buy_candidate_count": len(buy_candidate_cases),
        "watch_count": len(watch_cases),
    }


def _returns_for_action(cases: list[dict[str, Any]], action: str, horizon: str) -> list[float]:
    return [
        case["forward_returns"][horizon] for case in cases if case["action"] == action and case["forward_returns"].get(horizon) is not None
    ]


def _rate(values: list[float], predicate: Any) -> float | None:
    if not values:
        return None
    return round(sum(1 for value in values if predicate(value)) / len(values), 6)
