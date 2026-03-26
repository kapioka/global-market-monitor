from __future__ import annotations

from math import ceil
from typing import Any, Mapping


DEFAULT_STRUCTURE_CONFIG: dict[str, float] = {
    "broad_count_threshold": 4,
    "narrow_leadership_max_count": 2,
    "peakout_warning_count": 3,
    "energy_dominance_rank_max": 1,
    "energy_dominance_active_max": 2,
    "dispersion_low_threshold": 0.34,
    "dispersion_high_threshold": 0.5,
    "broad_watch_ratio_threshold": 0.45,
    "broad_promising_ratio_threshold": 0.22,
    "narrow_promising_ratio_threshold": 0.22,
    "dominance_active_ratio_max": 0.25,
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
        return _payload(
            "Noisy / Unclear",
            "有効なセクター候補データがありません。",
            rows,
            False,
            None,
            0.0,
            merged,
        )

    thresholds = _scaled_thresholds(len(rows), merged)
    promising = [row for row in rows if row["candidate_label"] == "有望"]
    watch_or_better = [row for row in rows if row["candidate_label"] in {"有望", "監視"}]
    peakout = [row for row in rows if row["candidate_label"] == "失速警戒"]
    defensive_active = [row for row in watch_or_better if row["ticker"] in DEFENSIVE_SECTORS]
    cyclical_active = [row for row in watch_or_better if row["ticker"] in CYCLICAL_SECTORS]
    dispersion_score = _dispersion_score(rows, watch_or_better)
    dominant_sector = _detect_dominant_sector(rows, watch_or_better, dispersion_score, merged, thresholds)
    dominance_strength = _dominance_strength(rows, watch_or_better, dominant_sector, dispersion_score, merged, thresholds)
    energy_dominance = dominant_sector == "XLE"

    label = "Noisy / Unclear"
    reason = "方向感の揃った改善シグナルがまだ不足しています。"

    if len(peakout) >= int(merged["peakout_warning_count"]):
        label = "Peakout Risk"
        reason = "失速警戒セクターが増えており、内部の伸びが鈍化しています。"
    elif _has_cross_group_breadth(defensive_active, cyclical_active) and len(watch_or_better) >= thresholds["broad_watch_min"] and len(promising) >= thresholds["broad_promising_min"] and dispersion_score >= float(merged["dispersion_high_threshold"]):
        label = "Broad Improvement"
        reason = "複数セクターで改善が広がっており、内部の裾野が広がっています。"
    elif len(cyclical_active) >= 3 and len(defensive_active) <= 1:
        label = "Cyclical Recovery"
        reason = "景気敏感セクター中心に改善が広がり、回復初期に近い構図です。"
    elif len(defensive_active) >= 3 and len(cyclical_active) <= 2:
        label = "Defensive Rotation"
        reason = "ディフェンシブセクター優位で、守りへの資金移動が目立ちます。"
    elif 0 < len(promising) <= thresholds["narrow_promising_max"] and dispersion_score <= float(merged["dispersion_low_threshold"]):
        label = "Narrow Leadership"
        reason = "一部セクターだけが先行しており、改善の広がりは限定的です。"

    if regime:
        normalized = str(regime).strip().lower()
        if label == "Broad Improvement" and normalized in {"risk_off", "credit_stress", "inflation_shock"}:
            reason = f"{reason} ただし現レジーム {regime} との整合には注意が必要です。"
        if label == "Defensive Rotation" and normalized in {"early_recovery", "risk_on"}:
            reason = f"{reason} ただし現レジーム {regime} と比べるとやや慎重な内部構造です。"

    return _payload(label, reason, rows, energy_dominance, dominant_sector, dominance_strength, dispersion_score, merged)


def _normalize_entry(ticker: str, payload: Any) -> dict[str, Any]:
    if isinstance(payload, Mapping):
        return {
            "ticker": str(payload.get("ticker", ticker)),
            "candidate_label": str(payload.get("candidate_label", payload.get("label", "様子見"))),
            "rank": int(payload.get("rank", 999) or 999),
            "acceleration_state": str(payload.get("acceleration_state", "stable") or "stable"),
        }
    return {
        "ticker": str(ticker),
        "candidate_label": str(payload),
        "rank": 999,
        "acceleration_state": "stable",
    }


def _dispersion_score(rows: list[dict[str, Any]], watch_or_better: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return round(len(watch_or_better) / len(rows), 4)


def _scaled_thresholds(total_count: int, merged: Mapping[str, float]) -> dict[str, int]:
    return {
        "broad_watch_min": _scaled_min_count(total_count, int(merged["broad_count_threshold"]), float(merged["broad_watch_ratio_threshold"])),
        "broad_promising_min": _scaled_min_count(total_count, 2, float(merged["broad_promising_ratio_threshold"])),
        "narrow_promising_max": _scaled_max_count(total_count, int(merged["narrow_leadership_max_count"]), float(merged["narrow_promising_ratio_threshold"])),
        "dominance_active_max": _scaled_max_count(total_count, int(merged["energy_dominance_active_max"]), float(merged["dominance_active_ratio_max"])),
    }


def _scaled_min_count(total_count: int, absolute_threshold: int, ratio_threshold: float) -> int:
    if total_count <= 0:
        return max(1, absolute_threshold)
    ratio_count = max(1, ceil(total_count * ratio_threshold))
    return min(absolute_threshold, ratio_count)


def _scaled_max_count(total_count: int, absolute_threshold: int, ratio_threshold: float) -> int:
    if total_count <= 0:
        return max(1, absolute_threshold)
    ratio_count = max(1, ceil(total_count * ratio_threshold))
    return min(total_count, max(absolute_threshold, ratio_count))


def _detect_dominant_sector(
    rows: list[dict[str, Any]],
    watch_or_better: list[dict[str, Any]],
    dispersion_score: float,
    merged: Mapping[str, float],
    thresholds: Mapping[str, int],
) -> str | None:
    active_count = len(watch_or_better)
    if active_count > int(thresholds["dominance_active_max"]):
        return None
    dominance_dispersion_cap = max(float(merged["dispersion_low_threshold"]), int(thresholds["dominance_active_max"]) / max(1, len(rows)))
    if dispersion_score > dominance_dispersion_cap:
        return None
    ranked_active = sorted(
        [row for row in watch_or_better if int(row.get("rank", 999) or 999) <= int(merged["energy_dominance_rank_max"])],
        key=lambda row: int(row.get("rank", 999) or 999),
    )
    if not ranked_active:
        return None
    return str(ranked_active[0].get("ticker"))


def _dominance_strength(
    rows: list[dict[str, Any]],
    watch_or_better: list[dict[str, Any]],
    dominant_sector: str | None,
    dispersion_score: float,
    merged: Mapping[str, float],
    thresholds: Mapping[str, int],
) -> str | None:
    if dominant_sector is None:
        return None
    active_count = len(watch_or_better)
    total_count = max(1, len(rows))
    dominant_row = next((row for row in watch_or_better if str(row.get("ticker")) == dominant_sector), None)
    dominant_rank = int((dominant_row or {}).get("rank", 999) or 999)
    low_dispersion = float(merged["dispersion_low_threshold"])
    if active_count <= 1 and dominant_rank <= int(merged["energy_dominance_rank_max"]) and dispersion_score <= low_dispersion:
        return "strong"
    if active_count <= max(1, int(thresholds["dominance_active_max"]) - 1) and dispersion_score <= low_dispersion + (1.0 / total_count):
        return "medium"
    return "weak"


def _breadth_state(
    rows: list[dict[str, Any]],
    watch_or_better: list[dict[str, Any]],
    dispersion_score: float,
    merged: Mapping[str, float],
) -> str:
    thresholds = _scaled_thresholds(len(rows), merged)
    if len(watch_or_better) >= thresholds["broad_watch_min"] and dispersion_score >= float(merged["dispersion_high_threshold"]):
        return "broad"
    if dispersion_score <= float(merged["dispersion_low_threshold"]):
        return "narrow"
    return "mixed"


def _has_cross_group_breadth(defensive_active: list[dict[str, Any]], cyclical_active: list[dict[str, Any]]) -> bool:
    return bool(defensive_active) and bool(cyclical_active)


def _leadership_state(
    dominant_sector: str | None,
    energy_dominance: bool,
    defensive_active: list[dict[str, Any]],
    cyclical_active: list[dict[str, Any]],
) -> str:
    if energy_dominance:
        return "energy-led"
    if dominant_sector:
        return f"single-sector:{dominant_sector}"
    if len(defensive_active) >= 3 and len(cyclical_active) <= 2:
        return "defensive"
    if len(cyclical_active) >= 3 and len(defensive_active) <= 1:
        return "cyclical"
    return "balanced"


def _stability_state(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "unclear"
    accelerating = sum(1 for row in rows if row["acceleration_state"] == "accelerating")
    decelerating = sum(1 for row in rows if row["acceleration_state"] == "decelerating")
    if decelerating >= max(2, accelerating + 1):
        return "decelerating"
    if accelerating >= max(2, decelerating + 1):
        return "accelerating"
    return "stable"


def _payload(
    label: str,
    reason: str,
    rows: list[dict[str, Any]],
    energy_dominance: bool,
    dominant_sector: str | None,
    dominance_strength: str | None,
    dispersion_score: float,
    merged: Mapping[str, float],
) -> dict[str, Any]:
    watch_or_better = [row for row in rows if row["candidate_label"] in {"有望", "監視"}]
    defensive_active = [row for row in watch_or_better if row["ticker"] in DEFENSIVE_SECTORS]
    cyclical_active = [row for row in watch_or_better if row["ticker"] in CYCLICAL_SECTORS]
    structure = {
        "breadth": _breadth_state(rows, watch_or_better, dispersion_score, merged),
        "leadership": _leadership_state(dominant_sector, energy_dominance, defensive_active, cyclical_active),
        "stability": _stability_state(rows),
    }
    return {
        "structure_label": label,
        "reason": reason,
        "structure": structure,
        "energy_dominance": energy_dominance,
        "dominant_sector": dominant_sector,
        "dominance_strength": dominance_strength,
        "single_sector_dominance": dominant_sector is not None,
        "dispersion_score": round(dispersion_score, 4),
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
