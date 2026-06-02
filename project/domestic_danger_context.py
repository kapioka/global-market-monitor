from __future__ import annotations

from typing import Any

FORBIDDEN_COPY = ("買うべき", "今が買い", "安全", "利益が出る", "確実", "推奨銘柄")


def build_domestic_danger_context(report_inputs: dict[str, Any]) -> dict[str, Any]:
    candidates = ((report_inputs.get("multi_asset_candidates") or {}).get("candidates")) or []
    japan_risk = report_inputs.get("japan_risk") or {}
    macro_context = report_inputs.get("japan_resident_context") or {}
    acquisition_log = report_inputs.get("acquisition_log") or []

    watch_items: list[dict[str, Any]] = []
    limitations: list[str] = []
    reasons: list[str] = []

    _add_domestic_candidate_items(watch_items, candidates)
    _add_fx_items(watch_items, reasons, limitations, japan_risk)
    _add_macro_items(watch_items, reasons, limitations, macro_context)
    _add_acquisition_fallback_items(watch_items, acquisition_log)

    level = _domestic_level(watch_items, limitations)
    payload = {
        "title": "国内文脈の補助危険確認",
        "domestic_danger_level": level,
        "domestic_danger_reasons": _dedupe(reasons) or ["国内文脈は補助確認として表示し、既存の危険ライン判定を上書きしません。"],
        "domestic_watch_items": watch_items,
        "domestic_data_limitations": _dedupe(limitations),
        "uses_domestic_values": bool(watch_items),
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
        severity = _severity_from_components(asset_class, domestic_rate, fx, trend, str(row.get("status") or ""))
        reason = _candidate_reason(asset_class, domestic_rate, fx, trend)
        watch_items.append(
            {
                "group": _group_label(asset_class, symbol),
                "name": row.get("display_name") or row.get("asset_class_label") or symbol,
                "symbol": symbol,
                "status": row.get("status", "informational"),
                "level": severity,
                "reason": reason,
                "caution": row.get("caution") or _default_caution(asset_class),
                "source": "multi_asset_candidates",
            }
        )


def _add_fx_items(
    watch_items: list[dict[str, Any]],
    reasons: list[str],
    limitations: list[str],
    japan_risk: dict[str, Any],
) -> None:
    usd_jpy = japan_risk.get("usd_jpy") or {}
    if not usd_jpy:
        limitations.append("USDJPY=X が未取得のため、外貨建て資産の円換算影響は限定的にしか確認できません。")
        return
    change_4w = _number(usd_jpy.get("change_4w"))
    level = "watch"
    if change_4w is not None and abs(change_4w) >= 0.04:
        level = "caution"
    elif change_4w is None:
        level = "unavailable"
    watch_items.append(
        {
            "group": "為替確認",
            "name": usd_jpy.get("ticker_name_ja") or "米ドル円",
            "symbol": usd_jpy.get("ticker") or "USDJPY=X",
            "status": "ok" if change_4w is not None else "unavailable",
            "level": level,
            "reason": "外貨建て資産の円換算影響を確認します。円高時は円建て評価の下押し、円安時も為替リスクとして扱います。",
            "caution": "外貨建て資産は為替の影響を受けます。",
            "source": "japan_risk",
        }
    )
    reasons.append("USDJPY=X は国内文脈の補助危険確認に使われます。")


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
        level = "caution" if jgb_10y is not None and jgb_10y >= 1.5 else "watch"
        watch_items.append(
            {
                "group": "国内金利・国内インフレ",
                "name": "MOF JGB yield curve",
                "symbol": "JGB_YIELD_CURVE",
                "status": "ok",
                "level": level,
                "reason": _jgb_reason(jgb),
                "caution": "JGB利回り上昇時は、円建て長期債・国内REITに注意します。",
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
                    "name": label,
                    "symbol": key,
                    "status": status,
                    "level": "watch",
                    "reason": f"{label} は国内文脈の補助確認に使われます。",
                    "caution": "この表示は資産クラス別の確認用であり、売買指示ではありません。",
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
                "name": row.get("used_ticker_name_ja") or row.get("requested_ticker_name_ja") or name,
                "symbol": symbol,
                "status": status,
                "level": "watch" if status == "ok" else "unavailable",
                "reason": f"{group}の補助確認系列として表示します。",
                "caution": _fallback_caution(group),
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


def _severity_from_components(asset_class: str, domestic_rate: float | None, fx: float | None, trend: float | None, status: str) -> str:
    if status in {"unavailable", "not_available", "missing"}:
        return "unavailable"
    if asset_class in {"bond_jpy", "reit_jp"} and domestic_rate is not None and domestic_rate < 0:
        return "caution"
    if fx is not None and abs(fx) >= 8:
        return "watch"
    if trend is not None and trend < -8:
        return "watch"
    return "watch"


def _candidate_reason(asset_class: str, domestic_rate: float | None, fx: float | None, trend: float | None) -> str:
    if asset_class == "bond_jpy":
        return "円建て債券は国内金利上昇時に価格下落リスクがあるため、国内金利文脈で補助確認します。"
    if asset_class == "reit_jp":
        return "国内REITは金利上昇と国内不動産文脈の影響を受けるため、米国REITとは分けて確認します。"
    if asset_class == "jp_equity":
        return "国内株式は外貨建て株式とは分け、日本株確認として補助表示します。"
    if asset_class == "gold":
        return "円建て金は金価格と為替の文脈を分けて補助確認します。"
    return f"国内文脈の補助確認です。国内金利={domestic_rate} / 為替={fx} / trend={trend}"


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


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _guard_copy(payload: dict[str, Any]) -> None:
    rendered = str(payload)
    for phrase in FORBIDDEN_COPY:
        if phrase in rendered:
            raise ValueError(f"forbidden advice phrase in domestic danger context: {phrase}")
