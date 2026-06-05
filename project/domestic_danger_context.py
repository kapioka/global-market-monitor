from __future__ import annotations

from typing import Any

FORBIDDEN_COPY = ("買うべき", "今が買い", "安全", "利益が出る", "確実", "推奨銘柄")

WEAK_4W_CHANGE = -4.0
WEAK_12W_CHANGE = -8.0
WEAK_DRAWDOWN = -12.0
SHARP_4W_CHANGE = -8.0
SHARP_DRAWDOWN = -20.0
JGB_PRESSURE_10Y = 1.5
FX_WATCH_MOVE = 2.0
FX_CAUTION_MOVE = 4.0


def build_domestic_danger_context(report_inputs: dict[str, Any]) -> dict[str, Any]:
    candidates = ((report_inputs.get("multi_asset_candidates") or {}).get("candidates")) or []
    japan_risk = report_inputs.get("japan_risk") or {}
    macro_context = report_inputs.get("japan_resident_context") or {}
    acquisition_log = report_inputs.get("acquisition_log") or []
    market_metrics = (report_inputs.get("domestic_market_metrics") or {}).get("by_symbol") or {}

    watch_items: list[dict[str, Any]] = []
    limitations: list[str] = []
    reasons: list[str] = []

    _add_domestic_candidate_items(watch_items, candidates)
    _add_domestic_metric_items(watch_items, market_metrics)
    _add_fx_items(watch_items, reasons, limitations, japan_risk, market_metrics)
    _add_macro_items(watch_items, reasons, limitations, macro_context)
    _add_acquisition_fallback_items(watch_items, acquisition_log)

    level = _domestic_level(watch_items, limitations)
    payload = {
        "title": "国内文脈の補助危険確認",
        "domestic_danger_level": level,
        "domestic_danger_reasons": _dedupe(reasons) or ["国内文脈は補助確認として表示し、既存の危険ライン判定を上書きしません。"],
        "domestic_watch_items": watch_items,
        "domestic_data_limitations": _dedupe(limitations),
        "domestic_metric_summary": _domestic_metric_summary(watch_items),
        "uses_domestic_values": any(item.get("metrics_used") for item in watch_items),
        "uses_domestic_price_metrics": any(item.get("source") == "domestic_market_metrics" and item.get("metrics_used") for item in watch_items),
        "uses_domestic_macro_values": any(item.get("source") == "official_japan_macro" and item.get("metrics_used") for item in watch_items),
        "uses_only_fallback_or_limitations": bool(watch_items) and not any(item.get("metrics_used") for item in watch_items),
        "must_not_affect_final_action": True,
        "must_not_affect_buy_readiness_score": True,
        "policy_status": "supplemental_display_only",
        "caveat": "これは買い推奨ではなく、現在の市場状態を資産クラス別に整理したものです。",
    }
    _guard_copy(payload)
    return payload


def _add_domestic_candidate_items(watch_items: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> None:
    for row in candidates:
        asset_class = str(row.get("asset_class") or "")
        if asset_class not in {"jp_equity", "bond_jpy", "reit_jp", "gold"}:
            continue
        symbol = str(row.get("symbol") or "-")
        if asset_class == "gold" and symbol not in {"1540.T", "GLD", "GC=F"}:
            continue
        components = row.get("japan_resident_context_components") or {}
        domestic_rate = _number(components.get("domestic_rate"))
        fx = _number(components.get("fx"))
        trend = _number(components.get("trend"))
        metrics = dict(row.get("metrics") or {})
        metrics.setdefault("symbol", symbol)
        severity = _severity_from_components(asset_class, domestic_rate, fx, trend, str(row.get("status") or ""), metrics)
        reason = _candidate_reason(asset_class, domestic_rate, fx, trend, metrics)
        metric_limitations = _metric_limitations(metrics)
        watch_items.append(
            {
                "group": _group_label(asset_class, symbol),
                "asset_group": asset_class,
                "label": row.get("display_name") or row.get("asset_class_label") or symbol,
                "name": row.get("display_name") or row.get("asset_class_label") or symbol,
                "symbol": symbol,
                "status": row.get("status", "informational"),
                "source_status": row.get("status", "informational"),
                "level": severity,
                "reason": reason,
                "caution": row.get("caution") or _default_caution(asset_class),
                "metrics": _metric_summary(metrics),
                "metrics_used": _metrics_used(metrics),
                "limitations": metric_limitations,
                "source": "multi_asset_candidates",
            }
        )


def _add_domestic_metric_items(watch_items: list[dict[str, Any]], market_metrics: dict[str, dict[str, Any]]) -> None:
    existing = {str(item.get("symbol")) for item in watch_items}
    for symbol in ("1306.T", "1321.T", "2510.T", "1343.T", "1540.T"):
        metrics = market_metrics.get(symbol) or {}
        if not metrics or symbol in existing:
            continue
        asset_class = _metric_asset_class(symbol, metrics)
        severity = _severity_from_components(asset_class, None, None, None, str(metrics.get("source_status") or ""), metrics)
        watch_items.append(
            {
                "group": _group_label(asset_class, symbol),
                "asset_group": asset_class,
                "label": metrics.get("display_name") or symbol,
                "name": metrics.get("display_name") or symbol,
                "symbol": symbol,
                "status": "informational" if metrics.get("is_available") else "unavailable",
                "source_status": metrics.get("source_status") or "unavailable",
                "level": severity,
                "reason": _candidate_reason(asset_class, None, None, None, metrics),
                "caution": _default_caution(asset_class),
                "metrics": _metric_summary(metrics),
                "metrics_used": _metrics_used(metrics),
                "limitations": _metric_limitations(metrics),
                "source": "domestic_market_metrics",
            }
        )


def _add_fx_items(
    watch_items: list[dict[str, Any]],
    reasons: list[str],
    limitations: list[str],
    japan_risk: dict[str, Any],
    market_metrics: dict[str, dict[str, Any]],
) -> None:
    usd_jpy = japan_risk.get("usd_jpy") or {}
    usd_jpy_metric = market_metrics.get("USDJPY=X") or {}
    if not usd_jpy and not usd_jpy_metric:
        limitations.append("USDJPY=X が未取得のため、外貨建て資産の円換算影響は限定的にしか確認できません。")
    change_4w = _number(usd_jpy.get("change_4w"))
    if change_4w is not None:
        change_4w = _fraction_to_percent(change_4w)
    else:
        change_4w = _number(usd_jpy_metric.get("change_4w"))
    level = "normal"
    if change_4w is not None and abs(change_4w) >= FX_CAUTION_MOVE:
        level = "caution"
    elif change_4w is not None and abs(change_4w) >= FX_WATCH_MOVE:
        level = "watch"
    elif change_4w is None:
        level = "unavailable"
    if usd_jpy or usd_jpy_metric:
        watch_items.append(
            {
                "group": "為替確認",
                "asset_group": "fx",
                "label": usd_jpy.get("ticker_name_ja") or usd_jpy_metric.get("display_name") or "米ドル円",
                "name": usd_jpy.get("ticker_name_ja") or usd_jpy_metric.get("display_name") or "米ドル円",
                "symbol": usd_jpy.get("ticker") or "USDJPY=X",
                "status": "ok" if change_4w is not None else "unavailable",
                "source_status": usd_jpy_metric.get("source_status") or ("ok" if change_4w is not None else "unavailable"),
                "level": level,
                "reason": "USDJPY=X の実変化で外貨建て資産の円換算影響を確認します。",
                "caution": "外貨建て資産は為替の影響を受けます。",
                "metrics": _metric_summary(usd_jpy_metric),
                "metrics_used": _metrics_used(usd_jpy_metric),
                "limitations": _metric_limitations(usd_jpy_metric),
                "source": "japan_risk" if usd_jpy else "domestic_market_metrics",
            }
        )
        reasons.append("USDJPY=X は国内文脈の補助危険確認に使われます。")
    eur_jpy_metric = market_metrics.get("EURJPY=X") or {}
    if eur_jpy_metric:
        eur_change_4w = _number(eur_jpy_metric.get("change_4w"))
        eur_level = (
            "caution"
            if eur_change_4w is not None and abs(eur_change_4w) >= FX_CAUTION_MOVE
            else "watch" if eur_change_4w is not None and abs(eur_change_4w) >= FX_WATCH_MOVE else "normal"
        )
        watch_items.append(
            {
                "group": "為替確認",
                "asset_group": "fx",
                "label": eur_jpy_metric.get("display_name") or "ユーロ円",
                "name": eur_jpy_metric.get("display_name") or "ユーロ円",
                "symbol": "EURJPY=X",
                "status": "ok" if eur_jpy_metric.get("is_available") else "unavailable",
                "source_status": eur_jpy_metric.get("source_status") or "unavailable",
                "level": eur_level,
                "reason": "EURJPY=X の実変化で外貨建て資産の円換算影響を補助確認します。",
                "caution": "外貨建て資産は為替の影響を受けます。",
                "metrics": _metric_summary(eur_jpy_metric),
                "metrics_used": _metrics_used(eur_jpy_metric),
                "limitations": _metric_limitations(eur_jpy_metric),
                "source": "domestic_market_metrics",
            }
        )


def _add_macro_items(
    watch_items: list[dict[str, Any]],
    reasons: list[str],
    limitations: list[str],
    macro_context: dict[str, Any],
) -> None:
    sources = macro_context.get("macro_sources") or {}
    jgb = macro_context.get("jgb_yields") or {}
    jgb_10y = _number(jgb.get("jgb_10y"))
    if jgb:
        level = "watch" if jgb_10y is not None and jgb_10y >= JGB_PRESSURE_10Y else "normal"
        watch_items.append(
            {
                "group": "国内金利・国内インフレ",
                "asset_group": "jgb_yield_curve",
                "label": "MOF JGB yield curve",
                "name": "MOF JGB yield curve",
                "symbol": "JGB_YIELD_CURVE",
                "status": "ok",
                "source_status": "ok",
                "level": level,
                "reason": _jgb_reason(jgb),
                "caution": "JGB利回り上昇時は、円建て長期債・国内REITに注意します。",
                "metrics": _jgb_reason(jgb),
                "metrics_used": {
                    key: jgb.get(key)
                    for key in (
                        "jgb_2y",
                        "jgb_5y",
                        "jgb_10y",
                        "jgb_20y",
                        "jgb_30y",
                        "jgb_curve_10y_2y",
                        "jgb_curve_30y_10y",
                    )
                    if jgb.get(key) is not None
                },
                "limitations": [],
                "source": "official_japan_macro",
            }
        )
        reasons.append("MOF JGB利回りは国内金利の補助危険確認に使われます。")
    else:
        limitations.append("MOF JGB利回りが未取得のため、国内金利の補助判断は限定的です。")

    for key, label, filename in (
        ("japan_cpi", "CPI", "japan_cpi.csv"),
        ("boj_domestic_short_rate", "BOJ短期金利", "boj_short_rate.csv"),
    ):
        source = sources.get(key) or {}
        status = str(source.get("status") or "unavailable")
        if status in {"ok", "partial"}:
            watch_items.append(
                {
                    "group": "国内金利・国内インフレ",
                    "asset_group": key,
                    "label": label,
                    "name": label,
                    "symbol": key,
                    "status": status,
                    "source_status": status,
                    "level": "normal",
                    "reason": f"{label} は国内文脈の補助確認に使われます。",
                    "caution": "この表示は資産クラス別の確認用であり、売買指示ではありません。",
                    "metrics": "補助マクロ系列あり",
                    "metrics_used": {},
                    "limitations": [],
                    "source": "official_japan_macro",
                }
            )
        else:
            limitations.append(f"{label} は {status} のため、{filename} または安定した公開系列がない限り補助危険値として扱いません。")


def _add_acquisition_fallback_items(watch_items: list[dict[str, Any]], acquisition_log: list[dict[str, Any]]) -> None:
    wanted = {
        "1306.T": ("国内株式", "TOPIX proxy"),
        "1321.T": ("国内株式", "Nikkei 225 proxy"),
        "2510.T": ("円建て債券", "JPY bond proxy"),
        "1343.T": ("国内REIT", "Japan REIT proxy"),
        "1540.T": ("円建て金", "Gold JPY proxy"),
        "EURJPY=X": ("為替確認", "ユーロ円"),
    }
    existing = {str(item.get("symbol")) for item in watch_items}
    for row in acquisition_log:
        symbol = str(row.get("used_ticker") or row.get("requested_ticker") or "")
        if symbol not in wanted or symbol in existing:
            continue
        group, name = wanted[symbol]
        status = str(row.get("status") or "unavailable")
        watch_items.append(
            {
                "group": group,
                "asset_group": _fallback_asset_group(symbol),
                "label": row.get("used_ticker_name_ja") or row.get("requested_ticker_name_ja") or name,
                "name": row.get("used_ticker_name_ja") or row.get("requested_ticker_name_ja") or name,
                "symbol": symbol,
                "status": status,
                "source_status": status,
                "level": "normal" if status == "ok" else "unavailable",
                "reason": f"{group}の補助確認系列として表示します。取得状況だけでは注意判定にしません。",
                "caution": _fallback_caution(group),
                "metrics": "価格メトリクス未接続",
                "metrics_used": {},
                "limitations": ["price_metrics_missing"],
                "source": "data_availability",
            }
        )


def _domestic_level(watch_items: list[dict[str, Any]], limitations: list[str]) -> str:
    levels = {str(item.get("level")) for item in watch_items}
    if "caution" in levels:
        return "caution"
    if "watch" in levels:
        return "watch"
    if limitations:
        return "unavailable"
    return "normal"


def _severity_from_components(
    asset_class: str,
    domestic_rate: float | None,
    fx: float | None,
    trend: float | None,
    status: str,
    metrics: dict[str, Any],
) -> str:
    if status in {"unavailable", "not_available", "missing"}:
        return "unavailable"
    if metrics and metrics.get("risk_signal_allowed") is False:
        return "unavailable"
    weak_price = _weak_price_metrics(metrics)
    sharp_price = _sharp_price_metrics(metrics)
    if asset_class == "jp_equity":
        if sharp_price:
            return "caution"
        if weak_price or (trend is not None and trend < -8):
            return "watch"
        return "normal"
    if asset_class == "bond_jpy":
        if domestic_rate is not None and domestic_rate < 0 and weak_price:
            return "caution"
        if domestic_rate is not None and domestic_rate < 0 or weak_price:
            return "watch"
        return "normal"
    if asset_class == "reit_jp":
        if domestic_rate is not None and domestic_rate < 0 and weak_price:
            return "caution"
        if domestic_rate is not None and domestic_rate < 0 or weak_price:
            return "watch"
        return "normal"
    if asset_class == "gold":
        if sharp_price or str(metrics.get("volatility_label") or "") == "elevated":
            return "caution"
        if weak_price:
            return "watch"
        return "normal"
    if fx is not None and abs(fx) >= 8:
        return "watch"
    if trend is not None and trend < -8:
        return "watch"
    return "normal"


def _candidate_reason(asset_class: str, domestic_rate: float | None, fx: float | None, trend: float | None, metrics: dict[str, Any]) -> str:
    metric_text = _metric_summary(metrics)
    if asset_class == "bond_jpy":
        return f"円建て債券は国内金利と価格推移を分けて補助確認します。指標: {metric_text}"
    if asset_class == "reit_jp":
        return f"国内REITは金利上昇と価格推移を米国REITとは分けて確認します。指標: {metric_text}"
    if asset_class == "jp_equity":
        return f"国内株式は外貨建て株式とは分け、日本株確認として補助表示します。指標: {metric_text}"
    if asset_class == "gold":
        symbol = str(metrics.get("symbol") or "")
        if symbol == "1540.T":
            return f"円建て金proxyとして、円ベースの金価格文脈を確認します。指標: {metric_text}"
        return f"外貨建て・USD建て金価格の参照系列として確認します。円建て金proxyとは別枠です。指標: {metric_text}"
    return f"国内文脈の補助確認です。国内金利={domestic_rate} / 為替={fx} / trend={trend}"


def _weak_price_metrics(metrics: dict[str, Any]) -> bool:
    change_4w = _number(metrics.get("change_4w"))
    change_12w = _number(metrics.get("change_12w") or metrics.get("momentum_12w"))
    drawdown = _number(metrics.get("max_drawdown"))
    trend_label = str(metrics.get("trend_label") or "")
    return (
        (change_4w is not None and change_4w <= WEAK_4W_CHANGE)
        or (change_12w is not None and change_12w <= WEAK_12W_CHANGE)
        or (drawdown is not None and drawdown <= WEAK_DRAWDOWN)
        or trend_label in {"weakening", "falling"}
    )


def _sharp_price_metrics(metrics: dict[str, Any]) -> bool:
    change_4w = _number(metrics.get("change_4w"))
    drawdown = _number(metrics.get("max_drawdown"))
    return (change_4w is not None and change_4w <= SHARP_4W_CHANGE) or (drawdown is not None and drawdown <= SHARP_DRAWDOWN)


def _metric_summary(metrics: dict[str, Any]) -> str:
    if not metrics:
        return "利用可能な表示指標なし"
    parts = []
    for key, label in (
        ("current_value", "現在値"),
        ("change_4w", "4週"),
        ("change_12w", "12週"),
        ("trend_label", "傾向"),
        ("max_drawdown_12w", "12週DD"),
        ("max_drawdown_26w", "26週DD"),
        ("max_drawdown_full", "全期間DD"),
    ):
        value = metrics.get(key)
        if value is not None:
            parts.append(f"{label}={value}")
    limitations = metrics.get("limitations")
    if limitations:
        parts.append(f"制約={','.join(str(item) for item in limitations)}")
    return " / ".join(parts) if parts else "利用可能な表示指標なし"


def _metrics_used(metrics: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "current_value",
        "change_1w",
        "change_4w",
        "change_12w",
        "momentum_12w",
        "max_drawdown",
        "max_drawdown_12w",
        "max_drawdown_26w",
        "max_drawdown_full",
        "zscore",
        "trend_label",
    )
    return {key: metrics.get(key) for key in keys if metrics.get(key) is not None}


def _metric_limitations(metrics: dict[str, Any]) -> list[str]:
    if not _metrics_used(metrics):
        return ["price_metrics_missing"]
    limitations = metrics.get("limitations") or []
    if isinstance(limitations, list):
        return [str(item) for item in limitations]
    return [str(limitations)]


def _domestic_metric_summary(watch_items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "item_count": len(watch_items),
        "level_counts": {
            level: sum(1 for item in watch_items if item.get("level") == level) for level in ("normal", "watch", "caution", "unavailable")
        },
        "metrics_available_count": sum(1 for item in watch_items if item.get("metrics_used")),
        "price_metrics_count": sum(1 for item in watch_items if item.get("source") == "domestic_market_metrics" and item.get("metrics_used")),
        "macro_metrics_count": sum(1 for item in watch_items if item.get("source") == "official_japan_macro" and item.get("metrics_used")),
        "fallback_or_limitation_count": sum(1 for item in watch_items if not item.get("metrics_used")),
        "limitations_count": sum(1 for item in watch_items if item.get("limitations")),
    }


def _fallback_asset_group(symbol: str) -> str:
    return {
        "1306.T": "jp_equity",
        "1321.T": "jp_equity",
        "2510.T": "jpy_bond",
        "1343.T": "jp_reit",
        "1540.T": "gold_jpy",
        "EURJPY=X": "fx",
    }.get(symbol, "domestic_context")


def _metric_asset_class(symbol: str, metrics: dict[str, Any]) -> str:
    raw = str(metrics.get("asset_group") or "")
    if raw == "jpy_bond":
        return "bond_jpy"
    if raw == "jp_reit":
        return "reit_jp"
    if raw == "gold_jpy":
        return "gold"
    if raw:
        return raw
    return _fallback_asset_group(symbol)


def _group_label(asset_class: str, symbol: str) -> str:
    if asset_class == "jp_equity":
        return "国内株式"
    if asset_class == "bond_jpy":
        return "円建て債券"
    if asset_class == "reit_jp":
        return "国内REIT"
    if asset_class == "gold" and symbol == "1540.T":
        return "円建て金"
    if asset_class == "gold":
        return "外貨建て金"
    return "国内文脈"


def _default_caution(asset_class: str) -> str:
    if asset_class in {"bond_jpy", "reit_jp"}:
        return "債券は金利上昇時に価格が下がることがあります。"
    if asset_class == "gold":
        return "円建て資産と外貨建て資産では、為替の影響が異なります。"
    return "この表示は資産クラス別の確認用であり、売買指示ではありません。"


def _fallback_caution(group: str) -> str:
    if group in {"円建て債券", "国内REIT"}:
        return "債券は金利上昇時に価格が下がることがあります。"
    if group in {"為替確認", "円建て金"}:
        return "円建て資産と外貨建て資産では、為替の影響が異なります。"
    return "この表示は資産クラス別の確認用であり、売買指示ではありません。"


def _jgb_reason(jgb: dict[str, Any]) -> str:
    parts = []
    for key, label in (
        ("jgb_2y", "2Y"),
        ("jgb_5y", "5Y"),
        ("jgb_10y", "10Y"),
        ("jgb_20y", "20Y"),
        ("jgb_30y", "30Y"),
        ("jgb_curve_10y_2y", "10Y-2Y"),
        ("jgb_curve_30y_10y", "30Y-10Y"),
    ):
        value = jgb.get(key)
        if value is not None:
            parts.append(f"{label}={value}")
    return "JGB利回り: " + (", ".join(parts) if parts else "取得値なし")


def _number(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fraction_to_percent(value: float | None) -> float | None:
    if value is None:
        return None
    return value * 100


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _guard_copy(payload: dict[str, Any]) -> None:
    rendered = str(payload)
    for phrase in FORBIDDEN_COPY:
        if phrase in rendered:
            raise ValueError(f"forbidden advice phrase in domestic danger context: {phrase}")
