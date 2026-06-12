from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.errors import ParserError

from project.hindenburg_provider import (
    ProviderAttempt,
    ProviderResult,
    acquire_builtin_provider_chain,
    acquire_configured_static_csv,
    resolve_hindenburg_data_dir,
    sanitize_provider_attempts,
)
from project.hindenburg_store import (
    DEFINITION_VERSION,
    SCHEMA_VERSION,
    auto_attempt_eligible,
    connect_hindenburg_store,
    history_progress,
    load_provider_history_frame,
    manual_retry_eligible,
    mark_update_failed,
    record_auto_attempt,
    update_store_with_signals,
)

MANUAL_SOURCE_PATH = Path("project/manual_sources/hindenburg_breadth.csv")
AUTO_CSV_URL_ENV = "HINDENBURG_BREADTH_CSV_URL"
REQUIRED_COLUMNS = {"date", "new_highs", "new_lows", "advancers", "decliners"}
DEFAULT_THRESHOLD_PCT = 2.8
DEFAULT_ACTIVE_WINDOW_DAYS = 30
STALE_DATA_DAYS = 7
MANUAL_RETRY_COOLDOWN_MINUTES = 30
SAMPLE_MARKER = "EXAMPLE_DO_NOT_IMPORT"


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
    return _parse_hindenburg_breadth_frame(frame, source_kind="local_manual_file", source_path=str(source_path))


def build_manual_daily_record_frame(
    *,
    market_date: str | date,
    new_highs: int | str,
    new_lows: int | str,
    advancers: int | str,
    decliners: int | str,
    total_issues: int | str | None = None,
    nyse_index: float | str | None = None,
    index_50d_ago: float | str | None = None,
    mcclellan_oscillator: float | str | None = None,
    source_note: str | None = None,
) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": market_date,
                "new_highs": new_highs,
                "new_lows": new_lows,
                "advancers": advancers,
                "decliners": decliners,
                "total_issues": total_issues,
                "nyse_index": nyse_index,
                "index_50d_ago": index_50d_ago,
                "mcclellan_oscillator": mcclellan_oscillator,
                "source_note": source_note or "manual_daily_input",
            }
        ]
    )


def import_hindenburg_manual_record(
    *,
    market_date: str | date,
    new_highs: int | str,
    new_lows: int | str,
    advancers: int | str,
    decliners: int | str,
    total_issues: int | str | None = None,
    nyse_index: float | str | None = None,
    index_50d_ago: float | str | None = None,
    mcclellan_oscillator: float | str | None = None,
    source_note: str | None = None,
    db_path: str | Path | None = None,
    as_of_date: date | str | None = None,
    threshold_pct: float = DEFAULT_THRESHOLD_PCT,
) -> dict[str, Any]:
    frame = build_manual_daily_record_frame(
        market_date=market_date,
        new_highs=new_highs,
        new_lows=new_lows,
        advancers=advancers,
        decliners=decliners,
        total_issues=total_issues,
        nyse_index=nyse_index,
        index_50d_ago=index_50d_ago,
        mcclellan_oscillator=mcclellan_oscillator,
        source_note=source_note,
    )
    return build_hindenburg_omen_context(
        manual_csv_path=Path("__manual_daily_input_not_used__.csv"),
        manual_input_frame=frame,
        auto_fetch=False,
        db_path=db_path,
        as_of_date=as_of_date or market_date,
        threshold_pct=threshold_pct,
    )


def parse_hindenburg_breadth_auto_csv(source: str | Path) -> dict[str, Any]:
    source_text = str(source).strip()
    if not source_text:
        return {
            "status": "auto_source_not_configured",
            "frame": None,
            "source_kind": "auto_csv",
            "source_path": "",
            "limitations": [f"自動取得CSV未設定: {AUTO_CSV_URL_ENV} または config.hindenburg_omen.auto_csv_url"],
        }
    provider_result = acquire_configured_static_csv(source_text)
    if provider_result.status not in {"ok", "cache_fallback"} or not provider_result.source_path:
        return {
            "status": "auto_fetch_error",
            "frame": None,
            "source_kind": "auto_csv",
            "source_path": provider_result.source_label or "",
            "limitations": list(provider_result.limitations) or ["利用者指定CSVの取得に失敗しました。"],
            "provider_attempts": sanitize_provider_attempts(provider_result.attempts),
            "failure_code": provider_result.failure_code,
        }
    try:
        frame = pd.read_csv(provider_result.source_path)
    except (ParserError, UnicodeDecodeError, OSError, ValueError) as exc:
        return {
            "status": "auto_fetch_error",
            "frame": None,
            "source_kind": "auto_csv",
            "source_path": provider_result.source_label or "",
            "limitations": [f"自動取得CSV解析エラー: {type(exc).__name__}"],
            "provider_attempts": sanitize_provider_attempts(provider_result.attempts),
            "failure_code": "PARSE_ERROR",
        }
    parsed = _parse_hindenburg_breadth_frame(frame, source_kind="auto_csv", source_path=provider_result.source_label or "")
    parsed["provider_attempts"] = sanitize_provider_attempts(provider_result.attempts)
    parsed["provider_id"] = provider_result.provider_id
    return parsed


def _parse_hindenburg_breadth_frame(frame: pd.DataFrame, *, source_kind: str, source_path: str) -> dict[str, Any]:

    normalized = {_normalize_column(column): column for column in frame.columns}
    if len(normalized) != len(frame.columns):
        return {
            "status": "parse_error",
            "frame": None,
            "source_kind": source_kind,
            "source_path": source_path,
            "limitations": ["正規化後に同名となる列が複数あります。"],
        }
    missing = sorted(REQUIRED_COLUMNS - set(normalized))
    if missing:
        return {
            "status": "parse_error",
            "frame": None,
            "source_kind": source_kind,
            "source_path": source_path,
            "limitations": [f"必須列不足: {', '.join(missing)}"],
        }

    renamed = frame.rename(columns={original: normalized_name for normalized_name, original in normalized.items()})
    if "source_note" in renamed.columns and renamed["source_note"].astype(str).str.contains(SAMPLE_MARKER, na=False).any():
        return {
            "status": "parse_error",
            "frame": None,
            "source_kind": source_kind,
            "source_path": source_path,
            "limitations": ["CSVテンプレートのサンプル行は本番観測として取り込めません。"],
            "failure_code": "TEMPLATE_SAMPLE_ROW",
        }
    renamed["date"] = pd.to_datetime(renamed["date"], errors="coerce")
    if renamed["date"].isna().any():
        return {
            "status": "parse_error",
            "frame": None,
            "source_kind": source_kind,
            "source_path": source_path,
            "limitations": ["date列に解析できない値があります。"],
        }
    validation = _validate_breadth_frame(renamed)
    if validation["fatal"]:
        return {
            "status": "parse_error",
            "frame": None,
            "source_kind": source_kind,
            "source_path": source_path,
            "limitations": validation["limitations"],
        }
    renamed = renamed.sort_values("date")
    if renamed.empty:
        return {
            "status": "parse_error",
            "frame": None,
            "source_kind": source_kind,
            "source_path": source_path,
            "limitations": ["有効なdate行がありません。"],
        }
    renamed, derived_limitations = _derive_mcclellan_oscillator(renamed)
    return {
        "status": "ok",
        "frame": renamed.reset_index(drop=True),
        "source_kind": source_kind,
        "source_path": source_path,
        "limitations": [*validation["limitations"], *derived_limitations],
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
    manual_input_frame: pd.DataFrame | None = None,
    auto_csv_url: str | Path | None = None,
    auto_fetch: bool = True,
    experimental_builtin_auto_fetch: bool = True,
    manual_provider_retry: bool = False,
    db_path: str | Path | None = None,
    provider_priority: list[str] | None = None,
    active_window_days: int = DEFAULT_ACTIVE_WINDOW_DAYS,
    threshold_pct: float = DEFAULT_THRESHOLD_PCT,
    as_of_date: date | str | None = None,
) -> dict[str, Any]:
    effective_as_of_date = _coerce_date(as_of_date) or date.today()
    conn = connect_hindenburg_store(db_path)
    expected_session_date = _expected_completed_us_session(effective_as_of_date).isoformat()
    if manual_input_frame is not None:
        parsed = _parse_hindenburg_breadth_frame(manual_input_frame, source_kind="manual_daily_input", source_path="manual_daily_input")
    else:
        parsed = parse_hindenburg_breadth_csv(manual_csv_path)
    provider_attempts: list[dict[str, Any]] = []
    provider_id = _provider_identity("manual_daily_input" if manual_input_frame is not None else "local_manual_file", str(manual_csv_path))
    source_label = "手入力" if manual_input_frame is not None else str(manual_csv_path)
    automatic_attempt_policy: dict[str, Any] = {
        "experimental": True,
        "expected_completed_us_market_session": expected_session_date,
        "attempted": False,
        "eligible": False,
        "reason": "NOT_NEEDED",
        "label": "自動取得・実験的",
    }
    if parsed["status"] == "manual_file_missing" and auto_fetch:
        auto_source = _resolve_auto_csv_source(auto_csv_url)
        if auto_source:
            provider_result = acquire_configured_static_csv(auto_source, cache_dir=resolve_hindenburg_data_dir() / "cache")
            provider_attempts.extend(sanitize_provider_attempts(provider_result.attempts))
            if provider_result.status in {"ok", "cache_fallback"} and provider_result.source_path:
                try:
                    frame = pd.read_csv(provider_result.source_path)
                except (ParserError, UnicodeDecodeError, OSError, ValueError):
                    parsed = {
                        "status": "auto_fetch_error",
                        "frame": None,
                        "source_kind": "auto_csv",
                        "source_path": provider_result.source_label or "",
                        "limitations": ["自動取得CSV解析エラー: CSVを解析できません。"],
                        "failure_code": "PARSE_ERROR",
                    }
                else:
                    parsed = _parse_hindenburg_breadth_frame(frame, source_kind="auto_csv", source_path=provider_result.source_label or "")
                    provider_id = _provider_identity(provider_result.provider_id, provider_result.source_label or "configured_static_csv")
                    source_label = provider_result.source_label or "Configured static CSV"
            else:
                parsed = {
                    "status": "auto_fetch_error",
                    "frame": None,
                    "source_kind": "auto_csv",
                    "source_path": provider_result.source_label or "",
                    "limitations": list(provider_result.limitations) or ["利用者指定CSVの取得に失敗しました。"],
                    "failure_code": provider_result.failure_code,
                }
        else:
            eligibility = (
                manual_retry_eligible(conn)
                if manual_provider_retry
                else auto_attempt_eligible(conn, expected_session_date, enabled=experimental_builtin_auto_fetch)
            )
            automatic_attempt_policy = {
                **automatic_attempt_policy,
                "eligible": bool(eligibility.get("eligible")),
                "reason": str(eligibility.get("reason") or "-"),
                "last_attempt_market_date": (eligibility.get("policy") or {}).get("last_attempt_market_date"),
                "last_attempt_result": (eligibility.get("policy") or {}).get("last_attempt_result"),
                "manual_retry": manual_provider_retry,
            }
            if eligibility.get("eligible"):
                builtin_result = acquire_builtin_provider_chain(
                    provider_priority=provider_priority,
                    last_successful_provider=(eligibility.get("policy") or {}).get("last_successful_provider"),
                )
                provider_attempts.extend(sanitize_provider_attempts(builtin_result.attempts))
                automatic_attempt_policy["attempted"] = True
                automatic_attempt_policy["attempt_result"] = builtin_result.status
                manual_retry_after = None
                if manual_provider_retry:
                    manual_retry_after = (datetime.now(UTC) + timedelta(minutes=MANUAL_RETRY_COOLDOWN_MINUTES)).isoformat(timespec="seconds")
                record_auto_attempt(
                    conn,
                    market_date=expected_session_date,
                    result=builtin_result.status,
                    provider_attempts=provider_attempts,
                    successful_provider=builtin_result.provider_id if builtin_result.status == "ok" else None,
                    manual_retry_after=manual_retry_after,
                )
            else:
                policy = eligibility.get("policy") or {}
                builtin_result = _stored_policy_provider_result(policy)
                provider_attempts.extend(sanitize_provider_attempts(builtin_result.attempts))
            if builtin_result.status == "ok" and builtin_result.source_path:
                try:
                    frame = pd.read_csv(builtin_result.source_path)
                except (ParserError, UnicodeDecodeError, OSError, ValueError):
                    parsed = {
                        "status": "auto_fetch_error",
                        "frame": None,
                        "source_kind": "builtin_provider_chain",
                        "source_path": builtin_result.source_label or "",
                        "limitations": ["built-in provider CSV解析エラー: CSVを解析できません。"],
                        "failure_code": "PARSE_ERROR",
                    }
                else:
                    parsed = _parse_hindenburg_breadth_frame(
                        frame,
                        source_kind="builtin_provider_chain",
                        source_path=builtin_result.source_label or "",
                    )
                    parsed["provider_id"] = builtin_result.provider_id
                    provider_id = _provider_identity(builtin_result.provider_id, builtin_result.source_label or builtin_result.provider_id)
                    source_label = builtin_result.source_label or builtin_result.provider_label
                    automatic_attempt_policy["accepted_record"] = True
            elif builtin_result.status == "failed":
                parsed = {
                    "status": "data_unavailable",
                    "frame": None,
                    "source_kind": "builtin_provider_chain",
                    "source_path": "",
                    "limitations": list(builtin_result.limitations),
                    "failure_code": builtin_result.failure_code,
                }
    progress = history_progress(conn, provider_id=provider_id)
    base = {
        "status": parsed["status"],
        "state": _state_for_parse_status(parsed["status"]),
        "current_signal": "unavailable",
        "current_signal_level": "unavailable",
        "is_currently_active": False,
        "is_active_as_of_latest_data": False,
        "stale_data": False,
        "data_latest_date": None,
        "as_of_date": effective_as_of_date.isoformat(),
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
        "definition_version": DEFINITION_VERSION,
        "schema_version": SCHEMA_VERSION,
        "failure_code": parsed.get("failure_code"),
        "last_update_attempt_at": None,
        "last_successful_update_at": None,
        "is_previous_confirmed_result": False,
        "history_complete": False,
        "provider_id": provider_id,
        "provider_label": source_label,
        "provider_attempts": provider_attempts,
        "providers_attempted_count": len(provider_attempts),
        "confirmed_market_date": None,
        "source_timestamp": None,
        "coverage_pct": None,
        "automatic_acquisition": {
            **automatic_attempt_policy,
            "success_label": bool(automatic_attempt_policy.get("accepted_record")),
        },
        "experimental_builtin_provider": True,
        "history_progress": progress,
        "stored_valid_record_count": progress["stored_valid_record_count"],
        "minimum_required_record_count": progress["minimum_required_record_count"],
        "history_progress_label": progress["history_progress_label"],
        "daily_signals": [],
        "must_not_affect_final_action": True,
        "must_not_affect_buy_readiness_score": True,
    }
    frame = parsed.get("frame")
    if frame is not None and parsed.get("source_kind") in {"manual_daily_input", "builtin_provider_chain"}:
        history_frame = load_provider_history_frame(conn, provider_id=provider_id)
        if not history_frame.empty:
            frame = pd.concat([history_frame.dropna(axis=1, how="all"), frame.dropna(axis=1, how="all")], ignore_index=True)
            parsed = _parse_hindenburg_breadth_frame(frame, source_kind=str(parsed["source_kind"]), source_path=str(parsed["source_path"]))
            frame = parsed.get("frame")
    if frame is None:
        failure = mark_update_failed(
            conn,
            state=base["state"],
            failure_code=str(parsed.get("failure_code") or parsed["status"]),
            provider_attempts=provider_attempts,
        )
        if failure.context:
            result = {**failure.context, "state": failure.state, "failure_code": failure.failure_code}
            conn.close()
            return result
        conn.close()
        return base

    daily_signals = compute_hindenburg_daily_signals(frame, threshold_pct=threshold_pct)
    if not daily_signals:
        context = {**base, "status": "insufficient_history", "state": "INSUFFICIENT_HISTORY", "limitations": [*base["limitations"], "有効な市場幅行がありません。"]}
        mark_update_failed(conn, state="INSUFFICIENT_HISTORY", failure_code="NO_DAILY_SIGNALS", provider_attempts=provider_attempts)
        conn.close()
        return context

    latest = daily_signals[-1]
    trigger_dates = [row["date"] for row in daily_signals if row["triggered"]]
    active_periods = summarize_hindenburg_periods(trigger_dates, active_window_days=active_window_days)
    latest_period = active_periods[-1] if active_periods else None
    latest_date = _parse_date(latest["date"])
    latest_trigger_date = _parse_date(trigger_dates[-1]) if trigger_dates else None
    active_until = latest_trigger_date + timedelta(days=active_window_days) if latest_trigger_date else None
    is_active_as_of_latest_data = bool(latest_date and active_until and latest_date <= active_until)
    is_currently_active = bool(active_until and effective_as_of_date <= active_until)
    stale_data = bool(latest_date and (effective_as_of_date - latest_date).days > STALE_DATA_DAYS)
    unknown = _criteria_names(latest["criteria"], "unknown")
    current_signal = "not_triggered"
    if stale_data:
        current_signal = "unconfirmed"
    elif latest["triggered"] and latest_date == effective_as_of_date:
        current_signal = "triggered_today"
    elif is_currently_active:
        current_signal = "active"
    elif unknown:
        current_signal = "unconfirmed"
    limitations = [*base["limitations"], *_data_limitations(latest)]
    if stale_data:
        limitations.append(f"市場幅CSVの最新日が古いため、現在の点灯状態は判定できません。最新日: {latest['date']}")
    context = {
        **base,
        "status": _context_status(parsed["status"], daily_signals),
        "state": "STALE" if stale_data else ("INSUFFICIENT_HISTORY" if unknown else "CONFIRMED"),
        "current_signal": current_signal,
        "current_signal_level": _signal_level(current_signal),
        "is_currently_active": bool(not stale_data and is_currently_active),
        "is_active_as_of_latest_data": is_active_as_of_latest_data,
        "stale_data": stale_data,
        "data_latest_date": latest["date"],
        "as_of_date": effective_as_of_date.isoformat(),
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
        "limitations": limitations,
        "confirmed_market_date": latest["date"],
        "daily_signals": daily_signals,
    }
    store_result = update_store_with_signals(
        conn,
        parsed=parsed,
        daily_signals=daily_signals,
        context=context,
        provider_id=provider_id,
        source_label=source_label,
        state=str(context["state"]),
        provider_attempts=provider_attempts,
    )
    if store_result.context:
        result = _with_history_progress(store_result.context, conn, provider_id)
        conn.close()
        return result
    result = _with_history_progress(context, conn, provider_id)
    conn.close()
    return result


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


def _validate_breadth_frame(frame: pd.DataFrame) -> dict[str, Any]:
    limitations: list[str] = []
    fatal = False
    numeric_columns = ["new_highs", "new_lows", "advancers", "decliners"]
    optional_numeric_columns = ["mcclellan_oscillator", "nyse_index", "total_issues", "index_50d_ago"]
    for row_number, row in frame.iterrows():
        values: dict[str, float | None] = {}
        for column in numeric_columns:
            value = _number(row.get(column))
            values[column] = value
            if value is None:
                limitations.append(f"{row_number + 1}行目 {column} が数値ではありません。")
                fatal = True
            elif value < 0:
                limitations.append(f"{row_number + 1}行目 {column} が負の値です。")
                fatal = True
            elif not float(value).is_integer():
                limitations.append(f"{row_number + 1}行目 {column} が整数ではありません。")
                fatal = True
        for column in optional_numeric_columns:
            if column not in frame.columns or not _has_value(row.get(column)):
                continue
            value = _number(row.get(column))
            values[column] = value
            if value is None:
                limitations.append(f"{row_number + 1}行目 {column} が数値ではありません。")
                fatal = True
            elif column in {"nyse_index", "total_issues"} and value <= 0:
                limitations.append(f"{row_number + 1}行目 {column} が正の値ではありません。")
                fatal = True
        advancers = values.get("advancers")
        decliners = values.get("decliners")
        total_breadth = None if advancers is None or decliners is None else advancers + decliners
        if total_breadth is not None and total_breadth <= 0:
            limitations.append(f"{row_number + 1}行目 advancers+decliners が0以下です。")
            fatal = True
        total_issues = values.get("total_issues")
        if total_issues is not None:
            highs = values.get("new_highs")
            lows = values.get("new_lows")
            if highs is not None and highs > total_issues:
                limitations.append(f"{row_number + 1}行目 new_highs が total_issues を超えています。")
                fatal = True
            if lows is not None and lows > total_issues:
                limitations.append(f"{row_number + 1}行目 new_lows が total_issues を超えています。")
                fatal = True
            if total_breadth is not None and total_breadth > total_issues:
                limitations.append(f"{row_number + 1}行目 advancers+decliners が total_issues を超えています。")
    return {"fatal": fatal, "limitations": limitations}


def _derive_mcclellan_oscillator(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    if len(frame) < 39:
        return frame, ["McClellan Oscillatorの内部算出には39営業日以上のadvancers/decliners履歴が必要です。"]
    enriched = frame.copy()
    advancers = pd.to_numeric(enriched["advancers"], errors="coerce")
    decliners = pd.to_numeric(enriched["decliners"], errors="coerce")
    net_advances = advancers - decliners
    derived = net_advances.ewm(span=19, adjust=False, min_periods=19).mean() - net_advances.ewm(
        span=39,
        adjust=False,
        min_periods=39,
    ).mean()
    if "mcclellan_oscillator" not in enriched.columns:
        enriched["mcclellan_oscillator"] = derived
        return enriched, ["McClellan Oscillatorはadvancers/declinersから内部算出しています。"]
    existing = pd.to_numeric(enriched["mcclellan_oscillator"], errors="coerce")
    enriched["mcclellan_oscillator"] = existing.fillna(derived)
    if existing.isna().any():
        return enriched, ["欠損したMcClellan Oscillatorはadvancers/declinersから内部算出しています。"]
    return enriched, []


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


def _stored_policy_provider_result(policy: dict[str, Any]) -> ProviderResult:
    attempts = tuple(
        ProviderAttempt(
            provider_id=str(item.get("provider_id") or "builtin_provider_chain"),
            provider_label=str(item.get("provider_label") or item.get("provider_id") or "Built-in provider chain"),
            status=str(item.get("status") or "skipped"),
            failure_code=item.get("failure_code"),
            source_label=item.get("source_label"),
            limitations=tuple(str(value) for value in item.get("limitations", [])),
        )
        for item in policy.get("provider_attempts", [])
    )
    return ProviderResult(
        status="failed",
        provider_id="builtin_provider_chain",
        provider_label="Built-in provider chain",
        failure_code="AUTO_ATTEMPT_ALREADY_RECORDED",
        attempts=attempts,
        limitations=("同一市場セッションでは自動取得を再試行しません。",),
    )


def _with_history_progress(context: dict[str, Any], conn: Any, provider_id: str) -> dict[str, Any]:
    progress = history_progress(conn, provider_id=provider_id)
    return {
        **context,
        "history_progress": progress,
        "stored_valid_record_count": progress["stored_valid_record_count"],
        "minimum_required_record_count": progress["minimum_required_record_count"],
        "history_progress_label": progress["history_progress_label"],
        "history_complete": progress["history_complete"] and context.get("state") == "CONFIRMED",
    }


def _expected_completed_us_session(as_of: date) -> date:
    candidate = as_of - timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def _state_for_parse_status(parse_status: str) -> str:
    if parse_status in {"manual_file_missing", "auto_source_not_configured", "data_unavailable"}:
        return "UNINITIALIZED"
    if parse_status in {"parse_error"}:
        return "INVALID_DATA"
    if parse_status in {"auto_fetch_error"}:
        return "UPDATE_FAILED"
    return "UPDATE_FAILED"


def _resolve_auto_csv_source(auto_csv_url: str | Path | None) -> str | None:
    if auto_csv_url is not None and str(auto_csv_url).strip():
        return str(auto_csv_url).strip()
    env_value = os.getenv(AUTO_CSV_URL_ENV, "").strip()
    return env_value or None


def _provider_identity(provider_id: str, source_label: str) -> str:
    digest = hashlib.sha256(source_label.encode("utf-8")).hexdigest()[:12]
    return f"{provider_id}:{digest}"


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


def _has_value(value: Any) -> bool:
    if value is None or pd.isna(value):
        return False
    return str(value).strip() != ""


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


def _coerce_date(value: date | str | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return _parse_date(str(value))


def _normalize_column(column: Any) -> str:
    return str(column).strip().lower().replace(" ", "_").replace("-", "_")
