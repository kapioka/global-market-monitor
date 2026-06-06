from __future__ import annotations

from typing import Any

LEVEL_ORDER = {"unavailable": 0, "normal": 1, "watch": 2, "caution": 3, "block": 4}
FORBIDDEN_COPY = ("買うべき", "今が買い", "安全", "利益が出る", "確実", "推奨銘柄")


def build_japan_resident_integrated_risk_context(report_inputs: dict[str, Any]) -> dict[str, Any]:
    risk_lines = report_inputs.get("risk_lines") or {}
    confidence_audit = report_inputs.get("risk_line_confidence_audit") or {}
    domestic_context = report_inputs.get("domestic_danger_context") or {}
    japan_risk = report_inputs.get("japan_risk") or {}
    macro_context = report_inputs.get("japan_resident_context") or {}

    global_level = _global_risk_level(risk_lines)
    domestic_level = _normalize_level(domestic_context.get("domestic_asset_level", domestic_context.get("domestic_danger_level")))
    fx_level = _fx_risk_level(japan_risk, domestic_context)
    rate_level = _rate_risk_level(domestic_context, macro_context)
    inflation_quality = _inflation_data_quality(macro_context)
    combined_level = _combined_level(global_level, domestic_level, fx_level, rate_level)

    payload = {
        "title": "日本在住者向け統合リスク文脈",
        "status": "display_only",
        "global_risk_level": global_level,
        "domestic_risk_level": domestic_level,
        "fx_risk_level": fx_level,
        "rate_risk_level": rate_level,
        "inflation_data_quality": inflation_quality,
        "combined_context_level": combined_level,
        "primary_reasons": _primary_reasons(risk_lines, confidence_audit, domestic_context, japan_risk),
        "watch_items": _watch_items(risk_lines, confidence_audit, domestic_context, japan_risk, macro_context),
        "data_limitations": _data_limitations(risk_lines, domestic_context, macro_context),
        "source_sections": [
            "risk_lines",
            "risk_line_confidence_audit",
            "domestic_danger_context",
            "japan_risk",
            "japan_resident_context",
            "domestic_market_metrics",
        ],
        "must_not_affect_final_action": True,
        "must_not_affect_buy_readiness_score": True,
        "policy_status": "supplemental_display_only",
        "caveat": "これは国内・国外・為替・金利・データ制約を並べる補助表示であり、投資判断ロジックを変更しません。",
    }
    _guard_copy(payload)
    return payload


def _global_risk_level(risk_lines: dict[str, Any]) -> str:
    stage = str(risk_lines.get("stage_key") or "").lower()
    label = str(risk_lines.get("stage_label") or "").lower()
    if stage in {"extreme_danger_line_reached", "danger_line_reached"} or "非常に危険" in label:
        return "block"
    if stage in {"credit_spillover_initial", "caution"} or "危険" in label:
        return "caution"
    if risk_lines.get("strict_missing_indicators") or risk_lines.get("missing_indicators"):
        return "unavailable"
    if stage in {"normal", "recovering", ""}:
        return "normal"
    return "watch"


def _fx_risk_level(japan_risk: dict[str, Any], domestic_context: dict[str, Any]) -> str:
    japan_level = _normalize_fx_level(japan_risk)
    levels = [japan_level]
    if domestic_context.get("domestic_fx_level") is not None:
        levels.append(_normalize_level(domestic_context.get("domestic_fx_level")))
    levels.extend(
        _normalize_level(row.get("level")) for row in domestic_context.get("domestic_watch_items", []) if row.get("asset_group") == "fx"
    )
    return _max_level(levels)


def _rate_risk_level(domestic_context: dict[str, Any], macro_context: dict[str, Any]) -> str:
    if domestic_context.get("domestic_macro_level") is not None:
        return _normalize_level(domestic_context.get("domestic_macro_level"))
    levels = [
        _normalize_level(row.get("level"))
        for row in domestic_context.get("domestic_watch_items", [])
        if row.get("asset_group") in {"bond_jpy", "jpy_bond", "reit_jp", "jp_reit", "jgb_yield_curve", "boj_domestic_short_rate"}
    ]
    if not levels and not (macro_context.get("jgb_yields") or {}):
        return "unavailable"
    return _max_level(levels or ["normal"])


def _inflation_data_quality(macro_context: dict[str, Any]) -> str:
    sources = macro_context.get("macro_sources") or {}
    cpi_status = str((sources.get("japan_cpi") or {}).get("status") or "unavailable")
    boj_status = str((sources.get("boj_domestic_short_rate") or {}).get("status") or "unavailable")
    statuses = {cpi_status, boj_status}
    if statuses & {"ok", "partial"}:
        return "partial" if statuses - {"ok", "partial"} else "available"
    return "unavailable"


def _combined_level(*levels: str) -> str:
    normalized = [_normalize_level(level) for level in levels if _normalize_level(level) != "unavailable"]
    if not normalized:
        return "unavailable"
    top = _max_level(normalized)
    return "caution" if top == "block" else top


def _primary_reasons(
    risk_lines: dict[str, Any],
    confidence_audit: dict[str, Any],
    domestic_context: dict[str, Any],
    japan_risk: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if risk_lines.get("summary"):
        reasons.append(f"米国・グローバル危険ライン: {risk_lines.get('summary')}")
    if confidence_audit.get("monitoring_scope_label"):
        reasons.append(f"監視範囲: {confidence_audit.get('monitoring_scope_label')}")
    for reason in domestic_context.get("domestic_danger_reasons", [])[:2]:
        reasons.append(f"国内文脈: {reason}")
    if japan_risk.get("summary"):
        reasons.append(f"為替文脈: {japan_risk.get('summary')}")
    return _dedupe(reasons) or ["統合リスク文脈は補助表示として作成され、既存判定を上書きしません。"]


def _watch_items(
    risk_lines: dict[str, Any],
    confidence_audit: dict[str, Any],
    domestic_context: dict[str, Any],
    japan_risk: dict[str, Any],
    macro_context: dict[str, Any],
) -> list[dict[str, str]]:
    items = [
        {
            "group": "米国・グローバル",
            "level": _global_risk_level(risk_lines),
            "summary": str(risk_lines.get("stage_label") or risk_lines.get("summary") or "危険ライン確認"),
            "source": "risk_lines",
        },
        {
            "group": "DXY / 円建てFXの役割分離",
            "level": "normal",
            "summary": _dxy_jpy_fx_summary(confidence_audit),
            "source": "risk_line_confidence_audit",
        },
    ]
    for row in domestic_context.get("domestic_watch_items", [])[:6]:
        items.append(
            {
                "group": str(row.get("group") or "国内文脈"),
                "level": _normalize_level(row.get("level")),
                "summary": f"{row.get('name', row.get('label', '-'))}: {row.get('reason', '-')}",
                "source": str(row.get("source") or "domestic_danger_context"),
            }
        )
    if japan_risk.get("summary"):
        items.append(
            {
                "group": "為替文脈",
                "level": _fx_risk_level(japan_risk, domestic_context),
                "summary": str(japan_risk.get("summary")),
                "source": "japan_risk",
            }
        )
    if _inflation_data_quality(macro_context) != "available":
        items.append(
            {
                "group": "国内インフレ・国内金利データ",
                "level": "unavailable",
                "summary": "CPI / BOJ / JGB の取得制約はリスク値ではなくデータ制約として表示します。",
                "source": "japan_resident_context",
            }
        )
    return items


def _data_limitations(
    risk_lines: dict[str, Any],
    domestic_context: dict[str, Any],
    macro_context: dict[str, Any],
) -> list[str]:
    limitations: list[str] = []
    for key in ("strict_missing_indicators", "missing_indicators"):
        missing = risk_lines.get(key) or []
        if missing:
            limitations.append(f"危険ライン不足指標: {', '.join(str(item) for item in missing)}")
    limitations.extend(str(item) for item in domestic_context.get("domestic_data_limitations", []))
    sources = macro_context.get("macro_sources") or {}
    for key, label in (("japan_cpi", "CPI"), ("boj_domestic_short_rate", "BOJ短期金利")):
        status = str((sources.get(key) or {}).get("status") or "unavailable")
        if status not in {"ok", "partial"}:
            limitations.append(f"{label}: {status}")
    if not (macro_context.get("jgb_yields") or {}):
        limitations.append("MOF JGB利回り: unavailable")
    return _dedupe(limitations)


def _dxy_jpy_fx_summary(confidence_audit: dict[str, Any]) -> str:
    dxy = (confidence_audit.get("dxy_role") or {}).get("label") or "DXY はグローバルのドル高ストレス確認です。"
    jpy = (confidence_audit.get("jpy_fx_role") or {}).get("label") or "USDJPY/EURJPY は日本円で見た為替文脈です。"
    return f"{dxy} / {jpy}"


def _normalize_level(level: Any) -> str:
    value = str(level or "unavailable").lower()
    if value in {"block", "high", "danger", "extreme", "extreme_danger"}:
        return "block"
    if value in {"caution", "medium", "moderate", "review"}:
        return "caution"
    if value in {"watch", "low", "weak"}:
        return "watch"
    if value in {"normal", "ok", "stable", "none"}:
        return "normal"
    return "unavailable"


def _normalize_fx_level(japan_risk: dict[str, Any]) -> str:
    summary = str(japan_risk.get("summary") or "")
    raw = str(japan_risk.get("level") or "unavailable").lower()
    if "中立" in summary and raw in {"moderate", "medium", "review", "normal", "ok", "stable"}:
        return "normal"
    if raw in {"neutral", "low", "normal", "ok", "stable", "none"}:
        return "normal"
    if raw in {"moderate", "medium", "review", "watch", "weak"}:
        return "watch"
    if raw in {"high", "caution", "danger"}:
        return "caution"
    if raw in {"block", "extreme", "extreme_danger"}:
        return "block"
    return "unavailable"


def _max_level(levels: list[str]) -> str:
    return max((_normalize_level(level) for level in levels), key=lambda level: LEVEL_ORDER.get(level, 0), default="unavailable")


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _guard_copy(payload: dict[str, Any]) -> None:
    rendered = str(payload)
    for phrase in FORBIDDEN_COPY:
        if phrase in rendered:
            raise ValueError(f"forbidden advice phrase in japan resident integrated context: {phrase}")
