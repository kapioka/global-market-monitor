from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import ParserError

MANUAL_SOURCE_PATH = Path("project/manual_sources/hindenburg_breadth.csv")
REQUIRED_COLUMNS = {"date", "new_highs", "new_lows", "advancers", "decliners"}
DEFAULT_THRESHOLD_PCT = 2.8
DEFAULT_ACTIVE_WINDOW_DAYS = 30


@dataclass(frozen=True)
class DailySignal:
    date: date
    triggered: bool
    criteria: dict[str, dict[str, Any]]
    new_highs_pct: float | None
    new_lows_pct: float | None
    mcclellan_oscillator: float | None
    index_trend: str
    source_note: str | None = None


def parse_hindenburg_breadth_csv(path: str | Path = MANUAL_SOURCE_PATH) -> dict[str, Any]:
    source_path = Path(path)
    if not source_path.exists():
        return {
            "status": "manual_file_missing",
            "frame": None,
            "source_kind": "local_manual_file",
            "source_path": str(source_path),
            "limitations": ["手動CSV未設定: project/manual_sources/hindenburg_breadth.csv"],
        }
    try:
        frame = pd.read_csv(source_path)
    except (ParserError, UnicodeDecodeError, OSError, ValueError) as exc:
        return {
            "status": "parse_error",
            "frame": None,
            "source_kind": "local_manual_file",
            "source_path": str(source_path),
            "limitations": [f"CSV解析エラー: {type(exc).__name__}"],
        }

    normalized = {_normalize_column(column): column for column in frame.columns}
    missing = sorted(REQUIRED_COLUMNS - set(normalized))
    if missing:
        return {
            "status": "parse_error",
            "frame": None,
            "source_kind": "local_manual_file",
            "source_path": str(source_path),
            "limitations": [f"必須列不足: {', '.join(missing)}"],
        }

    renamed = frame.rename(columns={original: normalized_name for normalized_name, original in normalized.items()})
    renamed["date"] = pd.to_datetime(renamed["date"], errors="coerce")
    renamed = renamed.dropna(subset=["date"]).sort_values("date")
    if renamed.empty:
        return {
            "status": "parse_error",
            "frame": None,
            "source_kind": "local_manual_file",
            "source_path": str(source_path),
            "limitations": ["有効なdate行がありません。"],
        }
    return {
        "status": "ok",
        "frame": renamed.reset_index(drop=True),
        "source_kind": "local_manual_file",
        "source_path": str(source_path),
        "limitations": [],
    }


def compute_hindenburg_daily_signals(
    frame: pd.DataFrame,
    *,
    threshold_pct: float = DEFAULT_THRESHOLD_PCT,
    enforce_high_low_balance: bool = True,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, row in frame.iterrows():
        signal = _compute_daily_signal(
            row,
            frame=frame,
            row_index=index,
            threshold_pct=threshold_pct,
            enforce_high_low_balance=enforce_high_low_balance,
        )
        rows.append(_daily_signal_payload(signal))
    return rows


def summarize_hindenburg_periods(trigger_dates: list[str], *, active_window_days: int = DEFAULT_ACTIVE_WINDOW_DAYS) -> list[dict[str, Any]]:
    parsed: list[date] = []
    for value in trigger_dates:
        parsed_date = _parse_date(value)
        if parsed_date is not None:
            parsed.append(parsed_date)
    parsed = sorted(parsed)
    periods: list[dict[str, Any]] = []
    for trigger_date in parsed:
        active_until = trigger_date + timedelta(days=active_window_days)
        previous_end = _parse_date(periods[-1]["period_end"]) if periods else None
        if previous_end is None or trigger_date > previous_end:
            periods.append(
                {
                    "period_start": trigger_date.isoformat(),
                    "period_end": active_until.isoformat(),
                    "trigger_day_count": 1,
                    "latest_trigger_date": trigger_date.isoformat(),
                }
            )
            continue
        periods[-1]["period_end"] = max(previous_end, active_until).isoformat()
        periods[-1]["trigger_day_count"] = int(periods[-1]["trigger_day_count"]) + 1
        periods[-1]["latest_trigger_date"] = trigger_date.isoformat()
    return periods


def build_hindenburg_omen_context(
    *,
    manual_csv_path: str | Path = MANUAL_SOURCE_PATH,
    active_window_days: int = DEFAULT_ACTIVE_WINDOW_DAYS,
    threshold_pct: float = DEFAULT_THRESHOLD_PCT,
) -> dict[str, Any]:
    parsed = parse_hindenburg_breadth_csv(manual_csv_path)
    base = {
        "status": parsed["status"],
        "current_signal": "unavailable",
        "current_signal_level": "unavailable",
        "is_currently_active": False,
        "latest_date": None,
        "latest_trigger_date": None,
        "active_until": None,
        "active_window_days": active_window_days,
        "trigger_dates": [],
        "active_periods": [],
        "latest_period": None,
        "criteria_latest": {},
        "criteria_passed": [],
        "criteria_failed": [],
        "criteria_unknown": [],
        "new_highs_pct": None,
        "new_lows_pct": None,
        "threshold_pct": threshold_pct,
        "mcclellan_oscillator": None,
        "index_trend": "unknown",
        "source_kind": parsed["source_kind"],
        "source_path": parsed["source_path"],
        "limitations": parsed["limitations"],
        "daily_signals": [],
        "must_not_affect_final_action": True,
        "must_not_affect_buy_readiness_score": True,
    }
    frame = parsed.get("frame")
    if frame is None:
        return base

    daily_signals = compute_hindenburg_daily_signals(frame, threshold_pct=threshold_pct)
    if not daily_signals:
        return {**base, "status": "insufficient_history", "limitations": [*base["limitations"], "有効な市場幅行がありません。"]}

    latest = daily_signals[-1]
    trigger_dates = [row["date"] for row in daily_signals if row["triggered"]]
    active_periods = summarize_hindenburg_periods(trigger_dates, active_window_days=active_window_days)
    latest_period = active_periods[-1] if active_periods else None
    latest_date = _parse_date(latest["date"])
    latest_trigger_date = _parse_date(trigger_dates[-1]) if trigger_dates else None
    active_until = latest_trigger_date + timedelta(days=active_window_days) if latest_trigger_date else None
    is_active = bool(latest_date and active_until and latest_date <= active_until)
    unknown = _criteria_names(latest["criteria"], "unknown")
    current_signal = "not_triggered"
    if latest["triggered"]:
        current_signal = "triggered_today"
    elif is_active:
        current_signal = "active"
    elif unknown:
        current_signal = "unconfirmed"
    return {
        **base,
        "status": _context_status(parsed["status"], daily_signals),
        "current_signal": current_signal,
        "current_signal_level": _signal_level(current_signal),
        "is_currently_active": is_active,
        "latest_date": latest["date"],
        "latest_trigger_date": latest_trigger_date.isoformat() if latest_trigger_date else None,
        "active_until": active_until.isoformat() if active_until else None,
        "trigger_dates": trigger_dates,
        "active_periods": active_periods,
        "latest_period": latest_period,
        "criteria_latest": latest["criteria"],
        "criteria_passed": _criteria_names(latest["criteria"], "passed"),
        "criteria_failed": _criteria_names(latest["criteria"], "failed"),
        "criteria_unknown": unknown,
        "new_highs_pct": latest["new_highs_pct"],
        "new_lows_pct": latest["new_lows_pct"],
        "mcclellan_oscillator": latest["mcclellan_oscillator"],
        "index_trend": latest["index_trend"],
        "limitations": [*base["limitations"], *_data_limitations(latest)],
        "daily_signals": daily_signals,
    }


def _compute_daily_signal(
    row: pd.Series,
    *,
    frame: pd.DataFrame,
    row_index: int,
    threshold_pct: float,
    enforce_high_low_balance: bool,
) -> DailySignal:
    total_issues = _total_issues(row)
    highs_pct = _pct(_number(row.get("new_highs")), total_issues)
    lows_pct = _pct(_number(row.get("new_lows")), total_issues)
    mcclellan = _number(row.get("mcclellan_oscillator"))
    uptrend = _uptrend_criterion(row, frame=frame, row_index=row_index)
    criteria = {
        "uptrend": uptrend,
        "new_highs_threshold": _criterion(highs_pct is not None and highs_pct >= threshold_pct, highs_pct is not None),
        "new_lows_threshold": _criterion(lows_pct is not None and lows_pct >= threshold_pct, lows_pct is not None),
        "negative_mcclellan": _criterion(mcclellan is not None and mcclellan < 0, mcclellan is not None),
        "high_low_balance": _high_low_balance_criterion(row, enabled=enforce_high_low_balance),
    }
    triggered = all(item["state"] == "passed" for item in criteria.values())
    return DailySignal(
        date=pd.Timestamp(row["date"]).date(),
        triggered=triggered,
        criteria=criteria,
        new_highs_pct=highs_pct,
        new_lows_pct=lows_pct,
        mcclellan_oscillator=mcclellan,
        index_trend=str(uptrend.get("detail", "unknown")),
        source_note=str(row.get("source_note")) if row.get("source_note") is not None and not pd.isna(row.get("source_note")) else None,
    )


def _uptrend_criterion(row: pd.Series, *, frame: pd.DataFrame, row_index: int) -> dict[str, Any]:
    explicit = _bool_value(row.get("index_above_50d"))
    if explicit is not None:
        return {"state": "passed" if explicit else "failed", "detail": "index_above_50d"}
    current = _number(row.get("nyse_index"))
    reference = _number(row.get("index_50d_ago"))
    if current is not None and reference is not None:
        return {"state": "passed" if current > reference else "failed", "detail": "index_vs_50d_ago"}
    if current is not None and row_index >= 49:
        window = frame.iloc[row_index - 49 : row_index + 1]
        values = pd.to_numeric(window.get("nyse_index"), errors="coerce").dropna()
        if len(values) >= 50:
            moving_average = float(values.mean())
            return {"state": "passed" if current > moving_average else "failed", "detail": "index_above_50d_ma"}
    return {"state": "unknown", "detail": "uptrend_data_missing"}


def _high_low_balance_criterion(row: pd.Series, *, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return {"state": "passed", "detail": "disabled"}
    highs = _number(row.get("new_highs"))
    lows = _number(row.get("new_lows"))
    if highs is None or lows is None or lows <= 0:
        return {"state": "unknown", "detail": "high_low_balance_data_missing"}
    return {"state": "passed" if highs <= lows * 2 else "failed", "detail": "high_count_not_more_than_2x_low_count"}


def _daily_signal_payload(signal: DailySignal) -> dict[str, Any]:
    return {
        "date": signal.date.isoformat(),
        "triggered": signal.triggered,
        "criteria": signal.criteria,
        "criteria_summary": _criteria_summary(signal.criteria),
        "new_highs_pct": signal.new_highs_pct,
        "new_lows_pct": signal.new_lows_pct,
        "mcclellan_oscillator": signal.mcclellan_oscillator,
        "index_trend": signal.index_trend,
        "source_note": signal.source_note,
    }


def _criteria_summary(criteria: dict[str, dict[str, Any]]) -> str:
    passed = len(_criteria_names(criteria, "passed"))
    failed = len(_criteria_names(criteria, "failed"))
    unknown = len(_criteria_names(criteria, "unknown"))
    return f"passed={passed} / failed={failed} / unknown={unknown}"


def _criteria_names(criteria: dict[str, dict[str, Any]], state: str) -> list[str]:
    return [name for name, result in criteria.items() if result.get("state") == state]


def _data_limitations(latest: dict[str, Any]) -> list[str]:
    limitations: list[str] = []
    if latest.get("criteria_unknown"):
        limitations.append("判定条件に不明項目があります。")
    unknown = _criteria_names(latest.get("criteria") or {}, "unknown")
    if unknown:
        limitations.append("不明条件: " + ", ".join(unknown))
    return limitations


def _context_status(parse_status: str, daily_signals: list[dict[str, Any]]) -> str:
    if parse_status != "ok":
        return parse_status
    if not daily_signals:
        return "insufficient_history"
    if _criteria_names(daily_signals[-1].get("criteria") or {}, "unknown"):
        return "partial"
    return "ok"


def _signal_level(signal: str) -> str:
    if signal in {"triggered_today", "active"}:
        return "active"
    if signal == "unconfirmed":
        return "notice"
    if signal == "not_triggered":
        return "normal"
    return "unavailable"


def _criterion(passed: bool, known: bool) -> dict[str, Any]:
    if not known:
        return {"state": "unknown"}
    return {"state": "passed" if passed else "failed"}


def _total_issues(row: pd.Series) -> float | None:
    explicit = _number(row.get("total_issues"))
    if explicit and explicit > 0:
        return explicit
    advancers = _number(row.get("advancers"))
    decliners = _number(row.get("decliners"))
    if advancers is None or decliners is None:
        return None
    total = advancers + decliners
    return total if total > 0 else None


def _pct(value: float | None, denominator: float | None) -> float | None:
    if value is None or denominator is None or denominator <= 0:
        return None
    return value / denominator * 100


def _number(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _bool_value(value: Any) -> bool | None:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "above"}:
        return True
    if text in {"false", "0", "no", "n", "below"}:
        return False
    return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _normalize_column(column: Any) -> str:
    return str(column).strip().lower().replace(" ", "_").replace("-", "_")
