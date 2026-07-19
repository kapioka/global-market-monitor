from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd


DEFAULT_FRESHNESS_MAX_BUSINESS_DAYS = 2


def build_report_data_provenance(
    prices: pd.DataFrame,
    *,
    generated_at: str,
    fetch_diagnostics: dict[str, Any] | None = None,
    data_source: str = "-",
    as_of_date: date | None = None,
    freshness_max_business_days: int = DEFAULT_FRESHNESS_MAX_BUSINESS_DAYS,
) -> dict[str, Any]:
    summary = dict((fetch_diagnostics or {}).get("summary") or {})
    latest = _latest_observation_date(prices)
    evaluation = as_of_date.isoformat() if as_of_date else _date_part(generated_at)
    mode_label = str(summary.get("data_mode_label") or _mode_label(data_source, summary, as_of_date))
    live_fetch_performed = bool(summary.get("live_fetch_performed", _live_fetch_performed(summary, data_source)))
    age_business_days = _business_day_age(latest, evaluation)
    freshness_status, stale_reason = _freshness_status(age_business_days, freshness_max_business_days, latest)
    if mode_label == "サンプルデータ":
        freshness_status = "sample"
        stale_reason = "実市場データではありません"
    return {
        "data_mode_label": mode_label,
        "execution_mode": summary.get("execution_mode") or ("replay_as_of" if as_of_date else "normal"),
        "evaluation_date": evaluation,
        "price_basis_date": latest,
        "latest_observation_date": latest,
        "retrieved_at": summary.get("snapshot_observed_at") or summary.get("retrieved_at"),
        "cache_observed_at": summary.get("snapshot_observed_at"),
        "source_kind": "cache_snapshot" if summary.get("snapshot_observed_at") else str(data_source),
        "live_fetch_performed": live_fetch_performed,
        "live_fetch_label": "ライブ更新あり" if live_fetch_performed else "ライブ更新なし",
        "age_business_days": age_business_days,
        "freshness_status": freshness_status,
        "freshness_label": _freshness_label(freshness_status),
        "stale_reason": stale_reason,
        "freshness_max_business_days": freshness_max_business_days,
        "snapshot_prices_path": summary.get("snapshot_prices_path"),
        "snapshot_metadata_path": summary.get("snapshot_metadata_path"),
    }


def _latest_observation_date(prices: pd.DataFrame) -> str | None:
    if prices.empty:
        return None
    usable = prices.dropna(how="all")
    if usable.empty:
        return None
    value = usable.index.max()
    if hasattr(value, "date"):
        return value.date().isoformat()
    return str(value)[:10]


def _date_part(value: str) -> str:
    try:
        return datetime.fromisoformat(str(value)).date().isoformat()
    except ValueError:
        return str(value)[:10]


def _business_day_age(latest: str | None, evaluation: str | None) -> int | None:
    if not latest or not evaluation:
        return None
    start = pd.Timestamp(latest).date()
    end = pd.Timestamp(evaluation).date()
    if end <= start:
        return 0
    return max(len(pd.bdate_range(start=start, end=end)) - 1, 0)


def _freshness_status(age_business_days: int | None, max_business_days: int, latest: str | None) -> tuple[str, str | None]:
    if latest is None:
        return "unavailable", "価格基準日が取得できません"
    if age_business_days is None:
        return "unknown", "鮮度を算出できません"
    if age_business_days > max_business_days:
        return "stale", f"営業日で{age_business_days}日経過"
    return "fresh", None


def _freshness_label(status: str) -> str:
    return {
        "fresh": "営業日基準で正常",
        "stale": "期限超過",
        "sample": "実市場データではありません",
        "unavailable": "未取得",
        "unknown": "確認中",
    }.get(status, status)


def _mode_label(data_source: str, summary: dict[str, Any], as_of_date: date | None) -> str:
    if as_of_date is not None:
        return "過去時点再生"
    if str(data_source) == "sample" or summary.get("sample_fallback_count"):
        return "サンプルデータ"
    if summary.get("snapshot_observed_at"):
        return "キャッシュ使用"
    return "ライブ取得"


def _live_fetch_performed(summary: dict[str, Any], data_source: str) -> bool:
    if summary.get("snapshot_observed_at"):
        return False
    if summary.get("network_access") == "not_used_when_cache_available":
        return False
    return str(data_source) not in {"sample", "snapshot"}
