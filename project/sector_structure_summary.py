from __future__ import annotations

from typing import Any, Mapping


DEFAULT_STRUCTURE_CONFIG: dict[str, float] = {
    "broad_count_threshold": 4,
    "narrow_leadership_max_count": 2,
    "peakout_warning_count": 3,
}

DEFENSIVE_SECTORS = {"XLP", "XLU", "XLV"}
CYCLICAL_SECTORS = {"XLK", "XLF", "XLE", "XLI", "XLY", "XLB"}


def summarize_sector_structure(
    candidate_map: Mapping[str, Any],
    regime: str | None = None,
    config: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Summarize sector candidate labels into a single internal structure label."""

    merged = _merge_config(config)
    rows = [_normalize_entry(ticker, payload) for ticker, payload in candidate_map.items()]
    if not rows:
        return _payload("Noisy / Unclear", "有効なセクター候補データがありません。", rows)

    promising = [row for row in rows if row["candidate_label"] == "有望"]
    watch_or_better = [row for row in rows if row["candidate_label"] in {"有望", "監視"}]
    peakout = [row for row in rows if row["candidate_label"] == "失速警戒"]
    defensive_active = [row for row in watch_or_better if row["ticker"] in DEFENSIVE_SECTORS]
    cyclical_active = [row for row in watch_or_better if row["ticker"] in CYCLICAL_SECTORS]

    label = "Noisy / Unclear"
    reason = "方向感の揃った改善シグナルがまだ不足しています。"

    if len(peakout) >= int(merged["peakout_warning_count"]):
        label = "Peakout Risk"
        reason = "失速警戒セクターが増えており、内部の伸びが鈍化しています。"
    elif len(watch_or_better) >= int(merged["broad_count_threshold"]) and len(promising) >= 2:
        label = "Broad Improvement"
        reason = "複数セクターで改善が広がっており、内部の裾野が広がっています。"
    elif len(cyclical_active) >= 3 and len(defensive_active) <= 1:
        label = "Cyclical Recovery"
        reason = "景気敏感セクター中心に改善が広がり、回復初期に近い構図です。"
    elif len(defensive_active) >= 3 and len(cyclical_active) <= 2:
        label = "Defensive Rotation"
        reason = "ディフェンシブセクター優位で、守りへの資金移動が目立ちます。"
    elif 0 < len(promising) <= int(merged["narrow_leadership_max_count"]):
        label = "Narrow Leadership"
        reason = "一部セクターだけが先行しており、改善の広がりは限定的です。"

    if regime:
        normalized = str(regime).strip().lower()
        if label == "Broad Improvement" and normalized in {"risk_off", "credit_stress", "inflation_shock"}:
            reason = f"{reason} ただし現レジーム {regime} との整合には注意が必要です。"
        if label == "Defensive Rotation" and normalized in {"early_recovery", "risk_on"}:
            reason = f"{reason} ただし現レジーム {regime} と比べるとやや慎重な内部構造です。"

    return _payload(label, reason, rows)


def _normalize_entry(ticker: str, payload: Any) -> dict[str, str]:
    if isinstance(payload, Mapping):
        return {
            "ticker": str(payload.get("ticker", ticker)),
            "candidate_label": str(payload.get("candidate_label", payload.get("label", "様子見"))),
        }
    return {
        "ticker": str(ticker),
        "candidate_label": str(payload),
    }


def _payload(label: str, reason: str, rows: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "structure_label": label,
        "reason": reason,
        "counts": {
            "promising": sum(1 for row in rows if row["candidate_label"] == "有望"),
            "watch": sum(1 for row in rows if row["candidate_label"] == "監視"),
            "wait": sum(1 for row in rows if row["candidate_label"] == "様子見"),
            "peakout": sum(1 for row in rows if row["candidate_label"] == "失速警戒"),
        },
    }


def _merge_config(config: Mapping[str, float] | None) -> dict[str, float]:
    merged = dict(DEFAULT_STRUCTURE_CONFIG)
    if config:
        merged.update({key: float(value) for key, value in config.items()})
    return merged
