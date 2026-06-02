from __future__ import annotations

from typing import Any

CONTEXT_CAUTION = (
    "円建て資産と外貨建て資産では、為替の影響が異なります。"
    "債券は金利上昇時に価格が下がることがあります。"
    "この表示は資産クラス別の確認用であり、売買指示ではありません。"
)

JAPAN_RESIDENT_TAXONOMY: dict[str, dict[str, Any]] = {
    "bond_jpy_government": {"group": "domestic_bonds", "role": "jpy_defensive", "jpy_relevance": "jpy_denominated"},
    "bond_jpy_short": {"group": "domestic_bonds", "role": "jpy_defensive", "jpy_relevance": "jpy_denominated"},
    "bond_jpy_intermediate": {"group": "domestic_bonds", "role": "jpy_defensive", "jpy_relevance": "jpy_denominated"},
    "bond_jpy_long": {"group": "domestic_bonds", "role": "duration_sensitive", "jpy_relevance": "jpy_denominated"},
    "jgb_yield_curve": {"group": "domestic_rates", "fields": ["jgb_2y", "jgb_5y", "jgb_10y", "jgb_20y", "jgb_30y"]},
    "fx_usdjpy": {"group": "fx", "fields": ["usdjpy_change_4w", "usdjpy_change_12w", "jpy_strength_label"]},
    "equity_jp_topix": {"group": "japanese_equities", "role": "jp_growth", "jpy_relevance": "jpy_denominated"},
    "equity_jp_nikkei": {"group": "japanese_equities", "role": "jp_growth", "jpy_relevance": "jpy_denominated"},
    "equity_jp_broad": {"group": "japanese_equities", "role": "jp_growth", "jpy_relevance": "jpy_denominated"},
    "jp_inflation": {"group": "domestic_macro", "fields": ["jp_cpi_yoy", "jp_core_cpi_yoy", "jp_cpi_trend"]},
    "jp_policy_rate": {"group": "domestic_macro", "fields": ["boj_policy_rate", "boj_call_rate", "domestic_rate_context"]},
    "reit_jp": {"group": "japanese_reit", "role": "real_asset_income", "jpy_relevance": "jpy_denominated"},
    "gold_usd": {"group": "gold", "role": "defensive", "jpy_relevance": "foreign_with_fx_context"},
    "gold_jpy_proxy": {"group": "gold", "role": "jpy_gold_proxy", "jpy_relevance": "jpy_proxy"},
    "foreign_bond": {"group": "foreign_bonds", "role": "diversification", "jpy_relevance": "foreign_with_fx_context"},
}

DATA_SOURCE_CONTRACT: dict[str, list[str]] = {
    "domestic_jpy_bonds": ["asset_compare", "acquisition_log", "optional configured tickers"],
    "jgb_yield_curve": ["japan_resident_context.jgb_yields", "optional official macro adapter", "fixture adapter contract"],
    "fx_currency_context": ["japan_risk.usd_jpy", "USDJPY=X acquisition log", "optional EURJPY=X acquisition log"],
    "japanese_equities": [
        "asset_compare",
        "config.tickers.japan.topix_proxy",
        "config.tickers.japan.nikkei_proxy",
        "acquisition_log",
    ],
    "japan_inflation_rates": ["japan_resident_context.inflation", "optional official macro adapter", "fixture adapter contract"],
    "boj_domestic_rates": ["japan_resident_context.domestic_rates", "optional official macro adapter", "fixture adapter contract"],
    "japanese_reit": ["asset_compare", "config.tickers.japan.jp_reit_proxy", "acquisition_log"],
    "gold_jpy_proxy": [
        "asset_compare Gold",
        "inflation_monitor GC=F",
        "japan_risk.usd_jpy",
        "config.tickers.japan.gold_jpy_proxy",
    ],
}


def build_japan_resident_context_signal(asset: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}
    asset_class = str(asset.get("asset_class") or "multi_asset")
    source_status = str(asset.get("source_status") or ("ok" if asset.get("source_data_available") else "missing"))
    source_available = bool(asset.get("source_data_available")) and source_status not in {"missing", "failed", "unavailable"}
    partial = source_status in {"partial", "sample_fallback"}
    taxonomy = JAPAN_RESIDENT_TAXONOMY.get(asset_class, {})

    gate_status = _gate_status(source_status, source_available, asset_class)
    components = _components(asset, context, taxonomy, gate_status, partial)
    raw_score = sum(components.values())
    score = max(0, min(100, raw_score))
    status = _status_from_score(score, gate_status, asset_class)

    return {
        "asset_class": asset_class,
        "context_score": score,
        "status": status,
        "components": components,
        "reason_category": _reason_category(asset_class, taxonomy, gate_status),
        "caution_required": _caution_required(asset, context, taxonomy, gate_status),
        "caution": CONTEXT_CAUTION,
        "taxonomy": taxonomy,
        "data_contract": DATA_SOURCE_CONTRACT,
        "must_not_affect_final_action": True,
        "must_not_affect_buy_readiness_score": True,
    }


def _gate_status(source_status: str, source_available: bool, asset_class: str) -> str:
    if asset_class == "cash":
        return "wait"
    if source_status in {"missing", "failed", "unavailable"} or not source_available:
        return "unavailable"
    if source_status in {"partial", "sample_fallback"}:
        return "informational"
    return "scorable"


def _components(
    asset: dict[str, Any],
    context: dict[str, Any],
    taxonomy: dict[str, Any],
    gate_status: str,
    partial: bool,
) -> dict[str, int]:
    return {
        "data_quality": _data_quality_component(gate_status, partial),
        "jpy_relevance": _jpy_relevance_component(asset, context, taxonomy),
        "trend": _trend_component(asset),
        "domestic_rate": _domestic_rate_component(asset, context, taxonomy),
        "fx": _fx_component(asset, context, taxonomy),
        "inflation": _inflation_component(asset, context, taxonomy),
        "credit": _credit_component(asset, context, taxonomy),
        "market_risk": _market_risk_component(asset, context, taxonomy),
    }


def _data_quality_component(gate_status: str, partial: bool) -> int:
    if gate_status == "unavailable":
        return 0
    if partial:
        return 8
    if gate_status == "informational":
        return 5
    return 20


def _jpy_relevance_component(asset: dict[str, Any], context: dict[str, Any], taxonomy: dict[str, Any]) -> int:
    relevance = str(asset.get("jpy_relevance") or taxonomy.get("jpy_relevance") or "")
    fx_available = bool((context.get("japan_risk") or {}).get("available"))
    if relevance == "jpy_denominated":
        return 15
    if relevance == "jpy_proxy":
        return 12
    if relevance == "foreign_with_fx_context":
        return 8 if fx_available else 3
    return 0


def _trend_component(asset: dict[str, Any]) -> int:
    metrics = asset.get("metrics") or {}
    trend = _first_number(metrics, "momentum_12w", "change_12w", "change_4w")
    drawdown = _number(metrics.get("max_drawdown"))
    if trend is None:
        return 0
    score = 8 if trend > 0 else -8 if trend < -0.08 else -3 if trend < 0 else 0
    if drawdown is not None and drawdown < -0.2:
        score -= 7
    return max(-15, min(15, score))


def _domestic_rate_component(asset: dict[str, Any], context: dict[str, Any], taxonomy: dict[str, Any]) -> int:
    group = str(taxonomy.get("group") or "")
    rate = context.get("jgb_yields") or {}
    change = _number(rate.get("jgb_10y_change_4w"))
    jgb_10y = _number(rate.get("jgb_10y"))
    domestic_context = str((context.get("domestic_rates") or {}).get("domestic_rate_context") or "")
    if change is None:
        if jgb_10y is not None and jgb_10y >= 1.5:
            return -6 if group in {"domestic_bonds", "japanese_reit"} else 0
        if jgb_10y is not None and jgb_10y <= 0.5:
            return 3 if group == "domestic_bonds" else 0
        if domestic_context in {"rising", "high"}:
            return -8 if group in {"domestic_bonds", "japanese_reit"} else 5 if asset.get("asset_class") == "cash" else 0
        if domestic_context in {"falling", "stable"}:
            return 4 if group == "domestic_bonds" else 0
        return 0
    if change < 0:
        return 10 if group == "domestic_bonds" else 5 if group == "japanese_reit" else 0
    if change > 0:
        return -10 if group in {"domestic_bonds", "japanese_reit"} else 5 if asset.get("asset_class") == "cash" else 0
    return 0


def _fx_component(asset: dict[str, Any], context: dict[str, Any], taxonomy: dict[str, Any]) -> int:
    relevance = str(asset.get("jpy_relevance") or taxonomy.get("jpy_relevance") or "")
    japan_risk = context.get("japan_risk") or {}
    usd_jpy = japan_risk.get("usd_jpy") or {}
    fx_change = _number(usd_jpy.get("change_4w"))
    if relevance.startswith("foreign") and fx_change is None:
        return -8
    if fx_change is None:
        return 0
    if relevance.startswith("foreign"):
        return 5 if fx_change > 0 else -8 if fx_change < 0 else 0
    if relevance in {"jpy_denominated", "jpy_proxy"}:
        return 3 if fx_change < 0 else -3 if fx_change > 0.05 else 0
    return 0


def _inflation_component(asset: dict[str, Any], context: dict[str, Any], taxonomy: dict[str, Any]) -> int:
    trend = str((context.get("inflation") or {}).get("jp_cpi_trend") or "")
    group = str(taxonomy.get("group") or "")
    if not trend:
        return 0
    if trend in {"rising", "high"}:
        if group == "gold":
            return 8
        if group == "domestic_bonds":
            return -6
        if asset.get("asset_class") == "cash":
            return -5
    if trend in {"falling", "stable"} and group == "domestic_bonds":
        return 4
    return 0


def _credit_component(asset: dict[str, Any], context: dict[str, Any], taxonomy: dict[str, Any]) -> int:
    credit = str((context.get("credit") or {}).get("stress") or "")
    group = str(taxonomy.get("group") or "")
    if credit == "high":
        if group == "foreign_bonds":
            return -10
        if group in {"domestic_bonds", "gold"} or asset.get("asset_class") == "cash":
            return 5
    if credit == "low" and group == "foreign_bonds":
        return 5
    return 0


def _market_risk_component(asset: dict[str, Any], context: dict[str, Any], taxonomy: dict[str, Any]) -> int:
    stage = str((context.get("risk_lines") or {}).get("stage_key") or "")
    group = str(taxonomy.get("group") or "")
    if stage in {"danger_line_reached", "extreme_danger_line_reached"}:
        if asset.get("asset_class") == "cash" or group in {"domestic_bonds", "gold"}:
            return 8
        if group in {"japanese_equities", "japanese_reit"}:
            return -8
    return 0


def _status_from_score(score: int, gate_status: str, asset_class: str) -> str:
    if asset_class == "cash":
        return "wait" if gate_status == "wait" else "informational"
    if gate_status == "unavailable":
        return "unavailable"
    if gate_status == "informational" or score < 50:
        return "informational"
    return "watch"


def _reason_category(asset_class: str, taxonomy: dict[str, Any], gate_status: str) -> str:
    if gate_status == "unavailable":
        return "insufficient_data"
    if asset_class == "cash":
        return "wait_context"
    group = str(taxonomy.get("group") or "")
    return {
        "domestic_bonds": "jpy_rate_context",
        "foreign_bonds": "rate_sensitive_context",
        "fx": "fx_context",
        "japanese_equities": "jp_equity_context",
        "japanese_reit": "jp_reit_context",
        "gold": "defensive_context",
    }.get(group, "partial_data_context")


def _caution_required(asset: dict[str, Any], context: dict[str, Any], taxonomy: dict[str, Any], gate_status: str) -> bool:
    if gate_status != "scorable":
        return True
    relevance = str(asset.get("jpy_relevance") or taxonomy.get("jpy_relevance") or "")
    group = str(taxonomy.get("group") or "")
    if relevance.startswith("foreign") and not bool((context.get("japan_risk") or {}).get("available")):
        return True
    return group in {"domestic_bonds", "foreign_bonds", "japanese_reit", "gold"}


def _first_number(mapping: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _number(mapping.get(key))
        if value is not None:
            return value
    return None


def _number(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
