from __future__ import annotations

from typing import Any

from project.japan_resident_asset_context import (
    DATA_SOURCE_CONTRACT,
    JAPAN_RESIDENT_TAXONOMY,
    build_japan_resident_context_signal,
)
from project.multi_asset_signal_model import build_multi_asset_signal

DISCLAIMER = (
    "これは買い推奨ではなく、現在の市場状態を資産クラス別に整理したものです。"
    "円建て資産と外貨建て資産では、為替や金利の影響が異なります。"
)

ASSET_CLASS_LABELS = {
    "equity": "株式候補",
    "gold": "守り候補",
    "bond": "債券候補",
    "bond_jpy": "円建て債券候補",
    "jp_equity": "日本株候補",
    "reit_jp": "国内REIT候補",
    "cash": "現金待機",
}

ROLE_LABELS = {
    "growth": "成長を取りに行く候補",
    "defensive": "不安定時の守り候補",
    "diversification": "金利低下・リスク回避時の確認候補",
    "jpy_defensive": "円建て守り候補",
    "jp_growth": "日本株の確認候補",
    "real_asset_income": "国内不動産・利回り確認",
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
    japan_risk = report_inputs.get("japan_risk") or {}
    japan_tickers = report_inputs.get("japan_tickers") or {}
    japan_resident_context = report_inputs.get("japan_resident_context") or {}
    availability_map = _merge_acquisition_availability(availability_map, acquisition_log)
    context = _japan_resident_context(japan_risk, japan_resident_context, risk_lines)

    rows = [
        _equity_candidate(asset_compare, asset_map, availability_map, investment_candidates),
        _gold_candidate(asset_compare, asset_map, availability_map, inflation_monitor, acquisition_log, japan_tickers, context),
        _bond_candidate(asset_compare, asset_map, availability_map, credit_monitor, acquisition_log, risk_lines, context),
        _jpy_bond_candidate(asset_compare, availability_map, acquisition_log, japan_tickers, context),
        _jp_equity_candidate(asset_compare, availability_map, acquisition_log, japan_tickers, context),
        _jp_reit_candidate(asset_compare, availability_map, acquisition_log, japan_tickers, context),
        _cash_candidate(reliability, risk_lines, context),
    ]

    return {
        "title": "資産クラス別の確認候補",
        "summary": "株式・ゴールド・外債・円建て債券・日本株・国内REIT・現金待機を、同じ買い候補度に混ぜず役割別に整理します。",
        "disclaimer": DISCLAIMER,
        "affects_final_action": False,
        "affects_buy_readiness_score": False,
        "candidates": rows,
        "japan_resident_taxonomy": JAPAN_RESIDENT_TAXONOMY,
        "japan_resident_data_contract": DATA_SOURCE_CONTRACT,
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
    japan_tickers: dict[str, Any],
    context: dict[str, Any],
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
    jpy_gold_symbol = str(japan_tickers.get("gold_jpy_proxy") or "")
    jpy_gold_row = _find_acquisition(acquisition_log, {jpy_gold_symbol} if jpy_gold_symbol else set())
    jpy_gold_available = bool(jpy_gold_symbol and _is_available(jpy_gold_symbol, availability_map)) or _acquisition_has_series(jpy_gold_row)
    context_symbol = jpy_gold_symbol if jpy_gold_available else symbol
    signal = build_multi_asset_signal(
        {
            "asset_class": "gold",
            "symbol": symbol,
            "display_name": str((preferred or monitor_row or {}).get("ticker_name_ja") or _acquisition_name(acquisition_row) or "ゴールド"),
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
        context_signal=build_japan_resident_context_signal(
            {
                "asset_class": "gold_jpy_proxy",
                "source_data_available": jpy_gold_available or signal["source_data_available"],
                "source_status": _source_status(context_symbol, availability_map, jpy_gold_available or signal["source_data_available"]),
                "metrics": _metrics_from(preferred or monitor_row),
            },
            context,
        ),
    )


def _bond_candidate(
    asset_compare: list[dict[str, Any]],
    asset_map: dict[str, Any],
    availability_map: dict[str, Any],
    credit_monitor: list[dict[str, Any]],
    acquisition_log: list[dict[str, Any]],
    risk_lines: dict[str, Any],
    context: dict[str, Any],
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
        context_signal=build_japan_resident_context_signal(
            {
                "asset_class": "foreign_bond",
                "source_data_available": signal["source_data_available"],
                "source_status": _source_status(symbol, availability_map, signal["source_data_available"]),
                "metrics": _metrics_from(preferred or monitor_row),
            },
            context,
        ),
    )


def _jpy_bond_candidate(
    asset_compare: list[dict[str, Any]],
    availability_map: dict[str, Any],
    acquisition_log: list[dict[str, Any]],
    japan_tickers: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    preferred = _find_asset(asset_compare, {"Japan_Bonds", "JGB", "JPY_Bonds"})
    configured_symbol = str(japan_tickers.get("jpy_bond_intermediate") or "2510.T")
    acquisition_row = _find_acquisition(acquisition_log, {configured_symbol, "2510.T", "2511.T", "JGB"})
    symbol = str((preferred or {}).get("ticker") or _acquisition_symbol(acquisition_row) or configured_symbol)
    metrics = _metrics_from(preferred)
    available = _is_available(symbol, availability_map) or preferred is not None or _acquisition_has_series(acquisition_row)
    context_signal = build_japan_resident_context_signal(
        {
            "asset_class": "bond_jpy_intermediate",
            "source_data_available": available,
            "source_status": _source_status(symbol, availability_map, available),
            "metrics": metrics,
        },
        context,
    )
    return _candidate(
        asset_class="bond_jpy",
        symbol=symbol,
        display_name=str((preferred or {}).get("ticker_name_ja") or _acquisition_name(acquisition_row) or "円建て債券確認"),
        role="jpy_defensive",
        status=context_signal["status"],
        reason="国内金利と円建て資産の確認用です。既存の買い判断とは別枠で表示します。",
        caution="円建て債券も金利上昇時に価格が下がることがあります。",
        source_data_available=available,
        metrics=metrics,
        context_signal=context_signal,
    )


def _jp_equity_candidate(
    asset_compare: list[dict[str, Any]],
    availability_map: dict[str, Any],
    acquisition_log: list[dict[str, Any]],
    japan_tickers: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    preferred = _find_asset(asset_compare, {"Japan_Stocks", "TOPIX", "Nikkei"})
    topix_symbol = str(japan_tickers.get("topix_proxy") or "1306.T")
    acquisition_row = _find_acquisition(acquisition_log, {topix_symbol, "1306.T", "1321.T"})
    symbol = str((preferred or {}).get("ticker") or _acquisition_symbol(acquisition_row) or topix_symbol)
    metrics = _metrics_from(preferred)
    available = _is_available(symbol, availability_map) or preferred is not None or _acquisition_has_series(acquisition_row)
    context_signal = build_japan_resident_context_signal(
        {
            "asset_class": "equity_jp_topix",
            "source_data_available": available,
            "source_status": _source_status(symbol, availability_map, available),
            "metrics": metrics,
        },
        context,
    )
    return _candidate(
        asset_class="jp_equity",
        symbol=symbol,
        display_name=str((preferred or {}).get("ticker_name_ja") or _acquisition_name(acquisition_row) or "日本株確認"),
        role="jp_growth",
        status=context_signal["status"],
        reason="日本株を外貨建て株式と分けて確認するための表示専用候補です。",
        caution="日本株も市場全体の下落や個別指数の偏りを受けます。",
        source_data_available=available,
        metrics=metrics,
        context_signal=context_signal,
    )


def _jp_reit_candidate(
    asset_compare: list[dict[str, Any]],
    availability_map: dict[str, Any],
    acquisition_log: list[dict[str, Any]],
    japan_tickers: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    preferred = _find_asset(asset_compare, {"Japan_REIT", "J_REIT"})
    configured_symbol = str(japan_tickers.get("jp_reit_proxy") or "1343.T")
    acquisition_row = _find_acquisition(acquisition_log, {configured_symbol, "1343.T", "1488.T", "JREIT"})
    symbol = str((preferred or {}).get("ticker") or _acquisition_symbol(acquisition_row) or configured_symbol)
    metrics = _metrics_from(preferred)
    available = _is_available(symbol, availability_map) or preferred is not None or _acquisition_has_series(acquisition_row)
    context_signal = build_japan_resident_context_signal(
        {
            "asset_class": "reit_jp",
            "source_data_available": available,
            "source_status": _source_status(symbol, availability_map, available),
            "metrics": metrics,
        },
        context,
    )
    return _candidate(
        asset_class="reit_jp",
        symbol=symbol,
        display_name=str((preferred or {}).get("ticker_name_ja") or _acquisition_name(acquisition_row) or "国内REIT確認"),
        role="real_asset_income",
        status=context_signal["status"],
        reason="国内REITを株式・債券とは別の不動産関連候補として確認します。",
        caution="REITは金利上昇や不動産市況の影響を受けます。",
        source_data_available=available,
        metrics=metrics,
        context_signal=context_signal,
    )


def _cash_candidate(reliability: dict[str, Any], risk_lines: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
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
    status = (
        signal["status"]
        if (not decision_allowed or risk_stage in {"danger_line_reached", "extreme_danger_line_reached"})
        else "informational"
    )
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
        context_signal=build_japan_resident_context_signal(
            {
                "asset_class": "cash",
                "source_data_available": True,
                "source_status": "ok",
                "metrics": {},
            },
            context,
        ),
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
    context_signal: dict[str, Any] | None = None,
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
    if context_signal:
        row.setdefault("reason_category", context_signal["reason_category"])
        row.setdefault("caution_required", context_signal["caution_required"])
        row.setdefault("must_not_affect_final_action", context_signal["must_not_affect_final_action"])
        row.setdefault(
            "must_not_affect_buy_readiness_score",
            context_signal["must_not_affect_buy_readiness_score"],
        )
        row.update(
            {
                "japan_resident_context_score": context_signal["context_score"],
                "japan_resident_context_status": context_signal["status"],
                "japan_resident_context_components": context_signal["components"],
                "japan_resident_reason_category": context_signal["reason_category"],
                "japan_resident_caution_required": context_signal["caution_required"],
                "japan_resident_caution": context_signal["caution"],
                "japan_resident_taxonomy": context_signal["taxonomy"],
                "japan_resident_must_not_affect_final_action": context_signal["must_not_affect_final_action"],
                "japan_resident_must_not_affect_buy_readiness_score": context_signal["must_not_affect_buy_readiness_score"],
            }
        )
    return row


def _japan_resident_context(
    japan_risk: dict[str, Any],
    japan_resident_context: dict[str, Any],
    risk_lines: dict[str, Any],
) -> dict[str, Any]:
    return {
        "japan_risk": japan_risk,
        "jgb_yields": japan_resident_context.get("jgb_yields") or {},
        "inflation": japan_resident_context.get("inflation") or {},
        "credit": japan_resident_context.get("credit") or {},
        "risk_lines": risk_lines,
    }


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


def _acquisition_has_series(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    return row.get("status") not in {None, "unavailable", "failed", "partial"}


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
    return row.get("status") not in {None, "unavailable", "sample_fallback", "failed", "partial"}


def _source_status(symbol: str, availability_map: dict[str, Any], available: bool) -> str:
    row = availability_map.get(symbol) or {}
    status = row.get("status")
    if status:
        return str(status)
    return "ok" if available else "missing"


def _metrics_from(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {}
    metric_keys = ("momentum_12w", "change_4w", "change_12w", "annualized_volatility", "max_drawdown", "zscore", "signal_label")
    return {key: row.get(key) for key in metric_keys if key in row}
