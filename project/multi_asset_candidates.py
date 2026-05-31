from __future__ import annotations

from typing import Any

from project.multi_asset_signal_model import build_multi_asset_signal


DISCLAIMER = "これは買い推奨ではなく、現在の市場状態を資産クラス別に整理したものです。外貨建て資産は為替の影響を受けます。"

ASSET_CLASS_LABELS = {
    "equity": "株式候補",
    "gold": "守り候補",
    "bond": "債券候補",
    "cash": "現金待機",
}

ROLE_LABELS = {
    "growth": "成長を取りに行く候補",
    "defensive": "不安定時の守り候補",
    "diversification": "金利低下・リスク回避時の確認候補",
    "wait": "条件がそろうまで待つ選択",
}


def build_multi_asset_candidates(report_inputs: dict[str, Any]) -> dict[str, Any]:
    asset_compare = report_inputs.get("asset_compare") or []
    asset_map = report_inputs.get("asset_map") or {}
    availability_map = report_inputs.get("availability_map") or {}
    investment_candidates = report_inputs.get("investment_candidates") or {}
    inflation_monitor = report_inputs.get("inflation_monitor") or []
    credit_monitor = report_inputs.get("credit_monitor") or []
    acquisition_log = report_inputs.get("acquisition_log") or []
    reliability = report_inputs.get("data_reliability") or {}
    risk_lines = report_inputs.get("risk_lines") or {}
    availability_map = _merge_acquisition_availability(availability_map, acquisition_log)

    rows = [
        _equity_candidate(asset_compare, asset_map, availability_map, investment_candidates),
        _gold_candidate(asset_compare, asset_map, availability_map, inflation_monitor, acquisition_log),
        _bond_candidate(asset_compare, asset_map, availability_map, credit_monitor, acquisition_log, risk_lines),
        _cash_candidate(reliability, risk_lines),
    ]

    return {
        "title": "資産クラス別の確認候補",
        "summary": "株式・ゴールド・債券・現金待機を、同じ買い候補度に混ぜず役割別に整理します。",
        "disclaimer": DISCLAIMER,
        "affects_final_action": False,
        "affects_buy_readiness_score": False,
        "candidates": rows,
        "inventory": _build_inventory(asset_map, availability_map, asset_compare, inflation_monitor, credit_monitor),
    }


def _equity_candidate(
    asset_compare: list[dict[str, Any]],
    asset_map: dict[str, Any],
    availability_map: dict[str, Any],
    investment_candidates: dict[str, Any],
) -> dict[str, Any]:
    preferred = investment_candidates.get("preferred_asset_class") or _find_asset(asset_compare, {"US_Stocks", "Intl_Stocks"})
    symbol = str((preferred or {}).get("ticker") or asset_map.get("US_Stocks") or "SPY")
    available = _is_available(symbol, availability_map) or preferred is not None
    status = (
        "candidate"
        if preferred and investment_candidates.get("tier") in {"priority", "watch"}
        else "watch" if available else "not_available"
    )
    return _candidate(
        asset_class="equity",
        symbol=symbol,
        display_name=str((preferred or {}).get("ticker_name_ja") or "米国株式ETF"),
        role="growth",
        status=status,
        reason="既存の資産比較または投資候補で株式の相対状況を確認します。",
        caution="株式は値動きが大きく、既存の最終判断を上書きしません。",
        source_data_available=available,
        metrics=_metrics_from(preferred),
    )


def _gold_candidate(
    asset_compare: list[dict[str, Any]],
    asset_map: dict[str, Any],
    availability_map: dict[str, Any],
    inflation_monitor: list[dict[str, Any]],
    acquisition_log: list[dict[str, Any]],
) -> dict[str, Any]:
    preferred = _find_asset(asset_compare, {"Gold"})
    monitor_row = _find_monitor(inflation_monitor, {"GC=F", "GLD", "IAU"})
    acquisition_row = _find_acquisition(acquisition_log, {"GC=F", "GLD", "IAU"})
    symbol = str(
        (preferred or {}).get("ticker")
        or asset_map.get("Gold")
        or (monitor_row or {}).get("ticker")
        or _acquisition_symbol(acquisition_row)
        or "GLD"
    )
    available = _is_available(symbol, availability_map) or preferred is not None or monitor_row is not None
    signal = build_multi_asset_signal(
        {
            "asset_class": "gold",
            "symbol": symbol,
            "display_name": str(
                (preferred or monitor_row or {}).get("ticker_name_ja") or _acquisition_name(acquisition_row) or "ゴールド"
            ),
            "source_data_available": available,
            "expected_role": "defensive",
            "expected_reason_category": "defensive_context" if available else "insufficient_data",
            "expected_missing_data_representation": "none" if available else "source_data_unavailable",
        }
    )
    return _candidate(
        asset_class="gold",
        symbol=signal["symbol"],
        display_name=signal["display_name"],
        role=signal["role"],
        status=signal["status"],
        reason="株式と同じ買い候補度ではなく、不安定時の守り候補として確認します。",
        caution="外貨建てまたは先物由来の指標は為替や商品価格の影響を受けます。",
        source_data_available=signal["source_data_available"],
        metrics=_metrics_from(preferred or monitor_row),
        signal=signal,
    )


def _bond_candidate(
    asset_compare: list[dict[str, Any]],
    asset_map: dict[str, Any],
    availability_map: dict[str, Any],
    credit_monitor: list[dict[str, Any]],
    acquisition_log: list[dict[str, Any]],
    risk_lines: dict[str, Any],
) -> dict[str, Any]:
    preferred = _find_asset(asset_compare, {"Bonds", "Inflation_Bonds"})
    monitor_row = _find_monitor(credit_monitor, {"LQD", "HYG", "AGG", "BND", "TLT", "IEF", "SHY", "BIL"})
    acquisition_row = _find_acquisition(acquisition_log, {"LQD", "HYG", "AGG", "BND", "TLT", "IEF", "SHY", "BIL", "TIP"})
    symbol = str(
        (preferred or {}).get("ticker")
        or asset_map.get("Bonds")
        or asset_map.get("Inflation_Bonds")
        or (monitor_row or {}).get("ticker")
        or _acquisition_symbol(acquisition_row)
        or "AGG"
    )
    available = _is_available(symbol, availability_map) or preferred is not None or monitor_row is not None
    risk_stage = str(risk_lines.get("stage_key") or "")
    signal = build_multi_asset_signal(
        {
            "asset_class": "bond",
            "symbol": symbol,
            "display_name": str(
                (preferred or monitor_row or {}).get("ticker_name_ja") or _acquisition_name(acquisition_row) or "米国債券ETF"
            ),
            "source_data_available": available,
            "expected_role": "diversification",
            "expected_reason_category": "rate_sensitive_context" if available else "insufficient_data",
            "expected_missing_data_representation": "none" if available else "source_data_unavailable",
        }
    )
    status = signal["status"] if risk_stage not in {"extreme_danger_line_reached", "danger_line_reached"} else "informational"
    return _candidate(
        asset_class="bond",
        symbol=signal["symbol"],
        display_name=signal["display_name"],
        role=signal["role"],
        status=status,
        reason="金利低下やリスク回避の局面で確認する分散候補として扱います。",
        caution="債券ETFも金利変動と為替の影響を受け、株式候補とは別枠で見ます。",
        source_data_available=signal["source_data_available"],
        metrics=_metrics_from(preferred or monitor_row),
        signal={**signal, "status": status},
    )


def _cash_candidate(reliability: dict[str, Any], risk_lines: dict[str, Any]) -> dict[str, Any]:
    decision_allowed = bool(reliability.get("decision_allowed", False))
    risk_stage = str(risk_lines.get("stage_key") or "")
    signal = build_multi_asset_signal(
        {
            "asset_class": "cash",
            "symbol": "CASH",
            "display_name": "現金待機",
            "source_data_available": True,
            "expected_role": "wait",
            "expected_reason_category": "wait_context",
            "expected_missing_data_representation": "not_market_ticker",
        }
    )
    status = signal["status"] if (not decision_allowed or risk_stage in {"danger_line_reached", "extreme_danger_line_reached"}) else "informational"
    return _candidate(
        asset_class="cash",
        symbol=signal["symbol"],
        display_name=signal["display_name"],
        role=signal["role"],
        status=status,
        reason="条件がそろうまで待つ選択肢として表示します。",
        caution="機会損失はあり得ますが、無理に資産候補へ振り分けません。",
        source_data_available=signal["source_data_available"],
        metrics={},
        signal={**signal, "status": status},
    )


def _candidate(
    *,
    asset_class: str,
    symbol: str,
    display_name: str,
    role: str,
    status: str,
    reason: str,
    caution: str,
    source_data_available: bool,
    metrics: dict[str, Any],
    signal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "asset_class": asset_class,
        "asset_class_label": ASSET_CLASS_LABELS[asset_class],
        "symbol": symbol,
        "display_name": display_name,
        "role": role,
        "role_label": ROLE_LABELS[role],
        "status": status,
        "reason": reason,
        "caution": caution,
        "source_data_available": source_data_available,
        "metrics": metrics,
    }
    if signal:
        row.update(
            {
                "reason_category": signal["reason_category"],
                "caution_required": signal["caution_required"],
                "must_not_affect_final_action": signal["must_not_affect_final_action"],
                "must_not_affect_buy_readiness_score": signal["must_not_affect_buy_readiness_score"],
            }
        )
    return row


def _build_inventory(
    asset_map: dict[str, Any],
    availability_map: dict[str, Any],
    asset_compare: list[dict[str, Any]],
    inflation_monitor: list[dict[str, Any]],
    credit_monitor: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    known_symbols = {str(value) for value in asset_map.values()}
    known_symbols.update(str(row.get("ticker")) for row in asset_compare if row.get("ticker"))
    known_symbols.update(str(row.get("ticker")) for row in inflation_monitor + credit_monitor if row.get("ticker"))
    inventory = []
    for symbol in sorted(known_symbols):
        inventory.append(
            {
                "symbol": symbol,
                "source_data_available": _is_available(symbol, availability_map)
                or any(str(row.get("ticker")) == symbol for row in asset_compare + inflation_monitor + credit_monitor),
                "status": (availability_map.get(symbol) or {}).get("status", "derived_or_not_logged"),
            }
        )
    return inventory


def _find_asset(asset_compare: list[dict[str, Any]], asset_classes: set[str]) -> dict[str, Any] | None:
    for row in asset_compare:
        if row.get("asset_class") in asset_classes:
            return row
    return None


def _find_monitor(rows: list[dict[str, Any]], symbols: set[str]) -> dict[str, Any] | None:
    for row in rows:
        if row.get("ticker") in symbols:
            return row
    return None


def _find_acquisition(rows: list[dict[str, Any]], symbols: set[str]) -> dict[str, Any] | None:
    for row in rows:
        used = str(row.get("used_ticker") or "")
        requested = str(row.get("requested_ticker") or "")
        if used in symbols or requested in symbols:
            return row
    return None


def _acquisition_symbol(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    return str(row.get("used_ticker") or row.get("requested_ticker") or "") or None


def _acquisition_name(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    return str(row.get("used_ticker_name_ja") or row.get("requested_ticker_name_ja") or "") or None


def _merge_acquisition_availability(
    availability_map: dict[str, Any],
    acquisition_log: list[dict[str, Any]],
) -> dict[str, Any]:
    if not acquisition_log:
        return availability_map
    merged = dict(availability_map)
    for row in acquisition_log:
        symbol = _acquisition_symbol(row)
        if not symbol or symbol in merged:
            continue
        merged[symbol] = {"status": row.get("status")}
    return merged


def _is_available(symbol: str, availability_map: dict[str, Any]) -> bool:
    row = availability_map.get(symbol) or {}
    return row.get("status") not in {None, "unavailable", "sample_fallback"}


def _metrics_from(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    metric_keys = ("momentum_12w", "change_4w", "change_12w", "annualized_volatility", "max_drawdown", "zscore", "signal_label")
    return {key: row.get(key) for key in metric_keys if key in row}
