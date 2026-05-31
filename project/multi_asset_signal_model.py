from __future__ import annotations

from typing import Any


CAUTION = "これは買い推奨ではなく、現在の市場状態を資産クラス別に整理したものです。外貨建て資産は為替の影響を受けます。"

ALLOWED_STATUSES = {"informational", "watch", "unavailable", "wait"}
AVAILABLE_STATUS_BY_CLASS = {
    "gold": "watch",
    "bond": "watch",
    "cash": "wait",
}
MISSING_STATUS_BY_CLASS = {
    "gold": "unavailable",
    "bond": "unavailable",
    "cash": "wait",
    "multi_asset": "informational",
}
DEFAULT_ROLE_BY_CLASS = {
    "gold": "defensive",
    "bond": "diversification",
    "cash": "wait",
    "multi_asset": "mixed_review",
}
DEFAULT_REASON_BY_CLASS = {
    "gold": "defensive_context",
    "bond": "rate_sensitive_context",
    "cash": "wait_context",
    "multi_asset": "partial_data_context",
}


def build_multi_asset_signal(case: dict[str, Any]) -> dict[str, Any]:
    """Build a display-only prototype signal from a v0.8.23 fixture-style case."""
    asset_class = str(case.get("asset_class") or "multi_asset")
    source_available = bool(case.get("source_data_available", False))
    status = _status_for(asset_class, source_available, str(case.get("expected_missing_data_representation") or ""))

    return {
        "asset_class": asset_class,
        "symbol": str(case.get("symbol") or "-"),
        "display_name": str(case.get("display_name") or case.get("symbol") or "-"),
        "source_data_available": source_available,
        "status": status,
        "role": str(case.get("expected_role") or DEFAULT_ROLE_BY_CLASS.get(asset_class, "informational")),
        "reason_category": str(case.get("expected_reason_category") or DEFAULT_REASON_BY_CLASS.get(asset_class, "partial_data_context")),
        "caution_required": True,
        "caution": CAUTION,
        "must_not_affect_final_action": True,
        "must_not_affect_buy_readiness_score": True,
    }


def build_multi_asset_signals(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [build_multi_asset_signal(case) for case in cases]


def _status_for(asset_class: str, source_available: bool, missing_representation: str) -> str:
    if asset_class == "cash":
        return "wait"
    if missing_representation == "partial_data_only":
        return "informational"
    if source_available:
        return AVAILABLE_STATUS_BY_CLASS.get(asset_class, "informational")
    return MISSING_STATUS_BY_CLASS.get(asset_class, "unavailable")
