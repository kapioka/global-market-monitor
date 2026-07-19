from __future__ import annotations

from typing import Any


CONFIRMING_STAGES = {"warning", "danger", "extreme"}
QUALITY_BLOCKERS = {
    "source_unavailable",
    "stale",
    "insufficient_history",
    "same_observation_comparison",
    "comparison_unavailable",
    "suspicious_discontinuity",
}


def build_oil_context(
    stress_monitor: list[dict[str, Any]],
    *,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    by_ticker = {str(row.get("ticker")): row for row in stress_monitor}
    oil_rows = [row for row in (by_ticker.get("CL=F"), by_ticker.get("BZ=F")) if row]
    if not oil_rows:
        return _unavailable("oil price inputs are unavailable")

    oil_settings = (settings or {}).get("oil", {}) if isinstance(settings, dict) else {}
    inflation_threshold = float(oil_settings.get("inflation_shock_return_4w", 0.08) or 0.08)
    demand_threshold = float(oil_settings.get("demand_collapse_return_4w", -0.12) or -0.12)
    quality_flags = _quality_flags(oil_rows)
    limitations = _limitations(oil_rows)
    risk_signal_allowed = not bool(quality_flags.intersection(QUALITY_BLOCKERS))

    oil_returns = [value for row in oil_rows if (value := _return_4w(row)) is not None]
    best_up = max(oil_returns) if oil_returns else None
    worst_down = min(oil_returns) if oil_returns else None
    inflation_pressure = _positive_score(best_up, inflation_threshold)
    oil_decline_pressure = _negative_score(worst_down, demand_threshold)
    equity_confirmation = _is_confirming(by_ticker.get("SPY")) or _negative_return(by_ticker.get("SPY"))
    credit_confirmation = _is_confirming(by_ticker.get("FRED:BAMLH0A0HYM2")) or _is_confirming(by_ticker.get("FRED:BAMLC0A0CM")) or _is_confirming(by_ticker.get("HYG/LQD"))
    dollar_confirmation = _is_confirming(by_ticker.get("DX-Y.NYB"))
    rates_or_breakeven_confirmation = _is_confirming(by_ticker.get("^TNX")) or _is_confirming(by_ticker.get("FRED:T10YIE"))

    inflation_confirmations = sum([rates_or_breakeven_confirmation, dollar_confirmation])
    demand_confirmations = sum([equity_confirmation, credit_confirmation, dollar_confirmation])
    demand_score = oil_decline_pressure * (0.4 + 0.3 * int(equity_confirmation) + 0.3 * int(credit_confirmation) + 0.1 * int(dollar_confirmation))
    demand_score = min(demand_score, 100.0)
    status = _overall_status(
        risk_signal_allowed=risk_signal_allowed,
        inflation_pressure=inflation_pressure,
        oil_decline_pressure=oil_decline_pressure,
        demand_score=demand_score,
        inflation_confirmations=inflation_confirmations,
        demand_confirmations=demand_confirmations,
    )
    reason = _reason(
        status=status,
        risk_signal_allowed=risk_signal_allowed,
        inflation_pressure=inflation_pressure,
        oil_decline_pressure=oil_decline_pressure,
        equity_confirmation=equity_confirmation,
        credit_confirmation=credit_confirmation,
        dollar_confirmation=dollar_confirmation,
        rates_or_breakeven_confirmation=rates_or_breakeven_confirmation,
    )
    if oil_decline_pressure > 0 and demand_confirmations < 2:
        limitations.append("原油下落単独では需要崩壊シグナルにせず、株式と信用の確認を待ちます")
    if not risk_signal_allowed:
        limitations.append("データ品質フラグにより原油リスクシグナルから除外しています")

    return {
        "status": "ok",
        "overall_status": status,
        "inflation_pressure_score": round(inflation_pressure, 1) if risk_signal_allowed else None,
        "demand_collapse_score": round(demand_score, 1) if risk_signal_allowed else None,
        "oil_decline_pressure_score": round(oil_decline_pressure, 1) if risk_signal_allowed else None,
        "wti_return_5d": _return_value(by_ticker.get("CL=F"), "change_1w"),
        "wti_return_20d": _return_value(by_ticker.get("CL=F"), "change_4w"),
        "wti_return_60d": _return_value(by_ticker.get("CL=F"), "change_12w"),
        "brent_return_20d": _return_value(by_ticker.get("BZ=F"), "change_4w"),
        "breakeven_change": _return_value(by_ticker.get("FRED:T10YIE"), "change_4w"),
        "equity_confirmation": equity_confirmation,
        "credit_confirmation": credit_confirmation,
        "dollar_confirmation": dollar_confirmation,
        "inflation_confirmation": rates_or_breakeven_confirmation,
        "risk_signal_allowed": risk_signal_allowed,
        "data_quality": "valid" if risk_signal_allowed else "reference_only",
        "quality_flags": sorted(quality_flags) or ["valid"],
        "limitations": sorted(set(limitations)),
        "reason": reason,
        "oil_tickers": [row.get("ticker") for row in oil_rows],
    }


def attach_oil_context_to_rows(rows: list[dict[str, Any]], oil_context: dict[str, Any]) -> list[dict[str, Any]]:
    attached: list[dict[str, Any]] = []
    for row in rows:
        if row.get("ticker") in {"CL=F", "BZ=F"}:
            enriched = dict(row)
            enriched["oil_context"] = oil_context
            attached.append(enriched)
        else:
            attached.append(row)
    return attached


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "status": "unavailable",
        "overall_status": "unavailable",
        "inflation_pressure_score": None,
        "demand_collapse_score": None,
        "oil_decline_pressure_score": None,
        "risk_signal_allowed": False,
        "data_quality": "unavailable",
        "quality_flags": ["source_unavailable"],
        "limitations": [reason],
        "reason": reason,
        "oil_tickers": [],
    }


def _overall_status(
    *,
    risk_signal_allowed: bool,
    inflation_pressure: float,
    oil_decline_pressure: float,
    demand_score: float,
    inflation_confirmations: int,
    demand_confirmations: int,
) -> str:
    if not risk_signal_allowed:
        return "unavailable"
    if inflation_pressure >= 70 and inflation_confirmations >= 1:
        return "inflation_stress"
    if demand_score >= 70 and demand_confirmations >= 2:
        return "demand_stress"
    if inflation_pressure >= 40 and inflation_confirmations >= 1:
        return "inflation_watch"
    if oil_decline_pressure >= 40 and demand_confirmations >= 2:
        return "demand_watch"
    return "normal"


def _reason(
    *,
    status: str,
    risk_signal_allowed: bool,
    inflation_pressure: float,
    oil_decline_pressure: float,
    equity_confirmation: bool,
    credit_confirmation: bool,
    dollar_confirmation: bool,
    rates_or_breakeven_confirmation: bool,
) -> str:
    if not risk_signal_allowed:
        return "原油先物はデータ品質上の制約があるため、危険方向シグナルには使わず参考表示にしています。"
    if status.startswith("inflation"):
        confirmations = _confirmation_text(
            [
                ("金利または期待インフレ", rates_or_breakeven_confirmation),
                ("ドル", dollar_confirmation),
            ]
        )
        return f"原油上昇に加えて {confirmations} が確認されるため、インフレ方向の原油ストレスとして扱います。"
    if status.startswith("demand"):
        confirmations = _confirmation_text(
            [
                ("株式", equity_confirmation),
                ("信用", credit_confirmation),
                ("ドル", dollar_confirmation),
            ]
        )
        return f"原油下落に加えて {confirmations} が確認されるため、需要減速方向の原油ストレスとして扱います。"
    if oil_decline_pressure > 0:
        return "原油は下落方向の圧力がありますが、株式・信用市場の同時悪化が揃っていないため、需要崩壊シグナルにはしていません。"
    if inflation_pressure > 0:
        return "原油上昇方向の圧力はありますが、金利・期待インフレなどの確認材料が限定的なため、インフレショックにはしていません。"
    return "原油上昇によるインフレ圧力、原油急落による需要減速圧力ともに確認条件を満たしていません。"


def _confirmation_text(items: list[tuple[str, bool]]) -> str:
    confirmed = [name for name, flag in items if flag]
    return "・".join(confirmed) if confirmed else "確認材料なし"


def _return_4w(row: dict[str, Any] | None) -> float | None:
    return _return_value(row, "change_4w")


def _return_value(row: dict[str, Any] | None, key: str) -> float | None:
    if not row:
        return None
    value = row.get(key)
    if isinstance(value, int | float):
        return float(value)
    return None


def _positive_score(value: float | None, threshold: float) -> float:
    if value is None or threshold <= 0:
        return 0.0
    return min(max(value, 0.0) / threshold, 1.5) / 1.5 * 100.0


def _negative_score(value: float | None, threshold: float) -> float:
    if value is None or threshold >= 0:
        return 0.0
    return min(max(abs(min(value, 0.0)), 0.0) / abs(threshold), 1.5) / 1.5 * 100.0


def _is_confirming(row: dict[str, Any] | None) -> bool:
    return bool(row and str(row.get("line_level")) in CONFIRMING_STAGES and row.get("stage_eligible", True))


def _negative_return(row: dict[str, Any] | None) -> bool:
    if row is None:
        return False
    value = _return_value(row, "change_4w")
    return value is not None and value <= -0.05 and bool(row.get("stage_eligible", True))


def _quality_flags(rows: list[dict[str, Any]]) -> set[str]:
    flags: set[str] = set()
    for row in rows:
        flags.update(str(flag) for flag in row.get("quality_flags", []) or [])
    return flags


def _limitations(rows: list[dict[str, Any]]) -> list[str]:
    limitations: list[str] = []
    for row in rows:
        limitations.extend(str(item) for item in row.get("limitations", []) or [])
    return limitations
