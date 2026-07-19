from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from project.config_loader import load_config
from project.risk_engine_v2_contract import attach_shadow_diagnostic_contract
from project.risk_engine_v2_evidence_policy import build_evidence_policy
from project.risk_engine_v2_official_series import load_official_series_csv, merge_official_series, official_series_tickers
from project.risk_engine_v2_primary_coverage import evaluate_case_primary_coverage, summarize_primary_coverage
from project.risk_engine_v2_replay import build_risk_engine_v2_replay, render_risk_engine_v2_replay_markdown
from project.risk_engine_v2_replay_schedule import canonical_weekly_prices, limit_cases_across_period, select_calendar_spaced_dates
from project.risk_line_threshold_store import load_threshold_definitions
from project.risk_lines import evaluate_risk_lines
from project.stress_monitor import (
    LEVEL_LABELS,
    _build_feature_values,
    _price_type_for_ticker,
    _stress_state_for_row,
    default_risk_indicator_map,
)
from project.ticker_labels import ticker_label_ja

REPO_ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_SERIES_ENV_VAR = "RISK_ENGINE_V2_OFFICIAL_SERIES_CSV"
DEFAULT_OFFICIAL_SERIES_CSV = REPO_ROOT / "project" / "reports" / "risk_engine_v2_official_series.csv"


@dataclass(frozen=True)
class OfficialSeriesSource:
    requested_path: str
    resolved_path: Path
    selection_origin: str
    explicit: bool


@dataclass(frozen=True)
class ReplayCadenceConfig:
    engine_evaluation_cadence: str = "canonical_weekly"
    persistence_expected_cadence: str = "canonical_weekly"
    case_sampling_stride: int = 4
    episode_merge_gap: str = "outcome_horizon_window"
    outcome_horizons: tuple[str, ...] = ("4w", "13w", "26w")

    def to_dict(self) -> dict[str, Any]:
        return {
            "engine_evaluation_cadence": self.engine_evaluation_cadence,
            "persistence_expected_cadence": self.persistence_expected_cadence,
            "case_sampling_stride": self.case_sampling_stride,
            "episode_merge_gap": self.episode_merge_gap,
            "outcome_horizons": list(self.outcome_horizons),
            "stride_semantics": "case_sampling_only_not_persistence_update",
        }


def build_reconstructed_history_entries(
    prices: pd.DataFrame,
    config: dict[str, Any],
    *,
    start_date: str | None = None,
    end_date: str | None = None,
    stride_weeks: int = 4,
    max_cases: int | None = None,
) -> list[dict[str, Any]]:
    clean = canonical_weekly_prices(_normalize_prices_frame(prices))
    if clean.empty:
        return []
    data_settings = config.get("data", {}) if isinstance(config, dict) else {}
    windows = data_settings.get("monitor_windows_weeks", {"short": 1, "medium": 4, "long": 12})
    zscore_window = int(data_settings.get("zscore_window_weeks", 52) or 52)
    minimum_history = max(int(windows.get("long", 12)), zscore_window)
    lookback_rows = max(minimum_history * 3, 160)
    indicator_map = _reconstructed_indicator_map(config)
    dates = _eligible_replay_dates(
        clean,
        indicator_map=indicator_map,
        minimum_history=minimum_history,
        start_date=start_date,
        end_date=end_date,
    )
    coverage = _coverage_summary(clean, config)
    cadence = ReplayCadenceConfig(case_sampling_stride=max(1, int(stride_weeks or 1)))
    evidence_policy = build_evidence_policy(generated_at="1970-01-01T00:00:00+00:00")
    precomputed_monitor = _precompute_replay_stress_monitor(clean, indicator_map, windows, zscore_window)
    entries: list[dict[str, Any]] = []
    sampled_dates = set(
        limit_cases_across_period(select_calendar_spaced_dates(dates, stride_weeks=cadence.case_sampling_stride), max_cases)
    )
    for case_index, evaluation_date in enumerate(dates):
        stress_monitor = precomputed_monitor.get(evaluation_date, [])
        primary_coverage = evaluate_case_primary_coverage(clean, evaluation_date, policy=evidence_policy)
        risk_lines = evaluate_risk_lines(
            regime={},
            cycle={},
            credit_monitor=[],
            inflation_monitor=[],
            stress_monitor=stress_monitor,
        )
        entries.append(
            {
                "date": evaluation_date.date().isoformat(),
                "generated_at": f"{evaluation_date.date().isoformat()}T07:30:00",
                "_source_file": "reconstructed_market_snapshot",
                "reconstruction": {
                    "source": "market_snapshot_prices",
                    "frequency": "canonical_weekly",
                    "calibration_pack_frequency": "weekly",
                    "point_in_time": True,
                    "latest_price_date": evaluation_date.date().isoformat(),
                    "minimum_history": minimum_history,
                    "lookback_rows": lookback_rows,
                    "engine_evaluation_cadence": cadence.engine_evaluation_cadence,
                    "persistence_expected_cadence": cadence.persistence_expected_cadence,
                    "case_sampling_stride": cadence.case_sampling_stride,
                    "case_sampling_selected": evaluation_date in sampled_dates,
                    "timeline_index": case_index,
                    "strict_primary_available": coverage["strict_primary_available"],
                    "fallback_replay_available": coverage["fallback_replay_available"],
                    "primary_domain_coverage": coverage["primary_domain_coverage"],
                    "fallback_domain_coverage": coverage["fallback_domain_coverage"],
                    "primary_coverage": primary_coverage,
                },
                "primary_coverage": primary_coverage,
                "risk_monitor": stress_monitor,
                "credit_monitor": [],
                "inflation_monitor": [],
                "risk_lines": {
                    "stage_key": risk_lines.get("stage_key", "normal"),
                    "composite_risk_score": risk_lines.get("composite_risk_score"),
                },
                "buy_decision_card": {"final_action": "diagnostic_reconstruction"},
            }
        )
    return entries


def build_reconstructed_risk_engine_v2_replay(
    prices: pd.DataFrame,
    config: dict[str, Any],
    *,
    benchmark_ticker: str = "ACWI",
    start_date: str | None = None,
    end_date: str | None = None,
    stride_weeks: int = 4,
    max_cases: int | None = None,
) -> dict[str, Any]:
    clean = canonical_weekly_prices(_normalize_prices_frame(prices))
    entries = build_reconstructed_history_entries(
        clean,
        config,
        start_date=start_date,
        end_date=end_date,
        stride_weeks=stride_weeks,
        max_cases=max_cases,
    )
    price_points = _price_points_for_benchmark(clean, benchmark_ticker)
    payload = build_risk_engine_v2_replay(entries, config, price_points=price_points)
    coverage = _coverage_summary(clean, config)
    primary_coverage_summary = summarize_primary_coverage(list(payload.get("cases") or []))
    cadence = ReplayCadenceConfig(case_sampling_stride=max(1, int(stride_weeks or 1)))
    sampled_case_count = sum(1 for entry in entries if (entry.get("reconstruction") or {}).get("case_sampling_selected"))
    if isinstance(payload.get("summary"), dict):
        fallback_strict_cases = int(payload["summary"].get("strict_available_cases", 0) or 0)
        primary_strict_cases = int(primary_coverage_summary.get("primary_strict_available_cases", 0) or 0)
        payload["summary"]["strict_primary_available"] = primary_strict_cases > 0
        payload["summary"]["primary_strict_available_cases"] = primary_strict_cases
        payload["summary"]["fallback_strict_available_cases"] = fallback_strict_cases
        payload["summary"]["fallback_replay_available"] = coverage["fallback_replay_available"]
        payload["summary"]["primary_domain_coverage"] = primary_coverage_summary.get("average_primary_domain_coverage", 0.0)
        payload["summary"]["primary_coverage_summary"] = primary_coverage_summary
        payload["summary"]["fallback_domain_coverage"] = coverage["fallback_domain_coverage"]
        payload["summary"]["timeline_case_count"] = len(entries)
        payload["summary"]["sampled_case_count"] = sampled_case_count
    if isinstance(payload.get("decision"), dict):
        primary_strict_cases = int(primary_coverage_summary.get("primary_strict_available_cases", 0) or 0)
        payload["decision"]["strict_primary_available"] = primary_strict_cases > 0
        payload["decision"]["primary_strict_available_cases"] = primary_strict_cases
    payload["replay_type"] = "risk_engine_v2_reconstructed_shadow"
    payload["reconstruction"] = {
        "status": "ok" if entries else "missing_reconstructed_cases",
        "source": "market_snapshot_prices",
        "frequency": "canonical_weekly",
        "calibration_pack_frequency": "weekly",
        "benchmark_ticker": benchmark_ticker,
        "start_date": entries[0]["date"] if entries else None,
        "end_date": entries[-1]["date"] if entries else None,
        "stride_weeks": stride_weeks,
        "cadence": cadence.to_dict(),
        "case_count": len(entries),
        "timeline_case_count": len(entries),
        "sampled_case_count": sampled_case_count,
        "point_in_time": True,
        "history_files_modified": False,
        "strict_primary_available": bool(primary_coverage_summary.get("primary_strict_available_cases", 0)),
        "fallback_replay_available": coverage["fallback_replay_available"],
        "primary_domain_coverage": primary_coverage_summary.get("average_primary_domain_coverage", 0.0),
        "primary_coverage_summary": primary_coverage_summary,
        "fallback_domain_coverage": coverage["fallback_domain_coverage"],
        "primary_missing_series": coverage["primary_missing_series"],
        "limitations": [
            "diagnostic reconstruction from cached prices, not original saved report payloads",
            "weekly calibration is applied only after canonical weekly resampling",
            "non-price official macro series are only included when present in the cached price table",
            "fallback-only reconstructed cases are not strict primary promotion evidence",
        ],
    }
    return attach_shadow_diagnostic_contract(payload, artifact_type="reconstructed_replay")


def run_reconstructed_risk_engine_v2_replay(
    *,
    input_prices: str | Path = "project/cache/market_snapshots/market_snapshot_2026-06-20_210709.csv",
    config_path: str | Path = "project/config.yaml",
    reports_dir: str | Path = "project/reports",
    benchmark_ticker: str = "ACWI",
    start_date: str | None = "2018-01-01",
    end_date: str | None = None,
    stride_weeks: int = 4,
    max_cases: int | None = None,
    official_series_csv: str | Path | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    reports_path = Path(reports_dir)
    prices = _read_prices(input_prices)
    market_snapshot_inventory = _market_snapshot_inventory(input_prices, prices)
    official_source = _select_official_series_source(official_series_csv, config)
    official_store_loaded = official_source.resolved_path.exists()
    if not official_store_loaded:
        raise FileNotFoundError(
            "risk_engine_v2 canonical official-series CSV is required but does not exist: "
            f"requested={official_source.requested_path} resolved={official_source.resolved_path} "
            f"selection_origin={official_source.selection_origin}"
        )
    try:
        official_prices = load_official_series_csv(official_source.resolved_path)
    except Exception as exc:
        raise ValueError(
            "risk_engine_v2 canonical official-series CSV could not be read: "
            f"requested={official_source.requested_path} resolved={official_source.resolved_path} "
            f"selection_origin={official_source.selection_origin} error={exc}"
        ) from exc
    _validate_official_series_store(official_source, config, official_prices)
    prices = merge_official_series(prices, official_prices)
    official_store_inventory = _official_store_inventory(official_source, config, official_prices)
    payload = build_reconstructed_risk_engine_v2_replay(
        prices,
        config,
        benchmark_ticker=benchmark_ticker,
        start_date=start_date,
        end_date=end_date,
        stride_weeks=stride_weeks,
        max_cases=max_cases,
    )
    if isinstance(payload.get("reconstruction"), dict):
        payload["reconstruction"]["market_snapshot"] = market_snapshot_inventory
        payload["reconstruction"]["official_series_store"] = official_store_inventory
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "risk_engine_v2_reconstructed_replay.json"
    markdown_path = reports_path / "risk_engine_v2_reconstructed_replay.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_reconstructed_markdown(payload), encoding="utf-8")
    summary = payload.get("summary", {})
    outcome = summary.get("outcome_summary", {}) if isinstance(summary, dict) else {}
    return {
        "status": payload.get("status"),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "total_cases": summary.get("total_cases", 0) if isinstance(summary, dict) else 0,
        "outcome_status": outcome.get("status"),
        "outcome_usable_cases": outcome.get("usable_cases", 0),
        "policy_status": payload.get("policy_status"),
        "affects_final_action": payload.get("affects_final_action"),
        "decision": payload.get("decision", {}),
        "reconstruction": payload.get("reconstruction", {}),
    }


def _render_reconstructed_markdown(payload: dict[str, Any]) -> str:
    reconstruction = payload.get("reconstruction", {})
    lines = [
        "# risk_engine_v2 reconstructed replay",
        "",
        "This replay is diagnostic only and is reconstructed from cached price history.",
        "It does not modify saved report history, final_action, or buy_readiness_score.",
        "",
        "## Reconstruction",
        "",
        f"- status: {reconstruction.get('status', '-')}",
        f"- source: {reconstruction.get('source', '-')}",
        f"- frequency: {reconstruction.get('frequency', '-')}",
        f"- calibration_pack_frequency: {reconstruction.get('calibration_pack_frequency', '-')}",
        f"- benchmark_ticker: {reconstruction.get('benchmark_ticker', '-')}",
        f"- case_count: {reconstruction.get('case_count', 0)}",
        f"- start_date: {reconstruction.get('start_date', '-')}",
        f"- end_date: {reconstruction.get('end_date', '-')}",
        f"- stride_weeks: {reconstruction.get('stride_weeks', '-')}",
        f"- point_in_time: {reconstruction.get('point_in_time', False)}",
        f"- history_files_modified: {reconstruction.get('history_files_modified', False)}",
        f"- strict_primary_available: {reconstruction.get('strict_primary_available', False)}",
        f"- fallback_replay_available: {reconstruction.get('fallback_replay_available', False)}",
        f"- primary_domain_coverage: {reconstruction.get('primary_domain_coverage', 0)}",
        f"- fallback_domain_coverage: {reconstruction.get('fallback_domain_coverage', 0)}",
        f"- primary_missing_series: {reconstruction.get('primary_missing_series', [])}",
        f"- market_snapshot: {reconstruction.get('market_snapshot', {})}",
        f"- official_series_store: {reconstruction.get('official_series_store', {})}",
        f"- limitations: {reconstruction.get('limitations', [])}",
        "",
    ]
    lines.append(render_risk_engine_v2_replay_markdown(payload))
    return "\n".join(lines)


def _select_official_series_source(official_series_csv: str | Path | None, config: dict[str, Any]) -> OfficialSeriesSource:
    if official_series_csv:
        return _official_source_from_path(official_series_csv, "cli_explicit", explicit=True)
    env_value = os.environ.get(OFFICIAL_SERIES_ENV_VAR)
    if env_value:
        return _official_source_from_path(env_value, f"env:{OFFICIAL_SERIES_ENV_VAR}", explicit=True)
    settings = config.get("risk_engine_v2", {}) if isinstance(config, dict) else {}
    config_value = settings.get("official_series_csv") if isinstance(settings, dict) else None
    if config_value:
        return _official_source_from_path(str(config_value), "config:risk_engine_v2.official_series_csv", explicit=True)
    return _official_source_from_path(DEFAULT_OFFICIAL_SERIES_CSV, "repository_default", explicit=False)


def _official_source_from_path(path: str | Path, selection_origin: str, *, explicit: bool) -> OfficialSeriesSource:
    requested = str(path)
    raw_path = Path(path)
    resolved = raw_path if raw_path.is_absolute() else REPO_ROOT / raw_path
    return OfficialSeriesSource(
        requested_path=requested,
        resolved_path=resolved.resolve(strict=False),
        selection_origin=selection_origin,
        explicit=explicit,
    )


def _official_store_inventory(
    source: OfficialSeriesSource,
    config: dict[str, Any],
    official_prices: pd.DataFrame | None,
) -> dict[str, Any]:
    exists = source.resolved_path.exists()
    required = official_series_tickers(config)
    inventory: dict[str, Any] = {
        "loaded": official_prices is not None and exists,
        "exists": exists,
        "requested_path": source.requested_path,
        "resolved_path": str(source.resolved_path),
        "path": str(source.resolved_path),
        "selection_origin": source.selection_origin,
        "explicit": source.explicit,
        "sha256": _sha256_file(source.resolved_path) if exists else None,
        "row_count": int(len(official_prices)) if official_prices is not None else 0,
        "columns": list(official_prices.columns) if official_prices is not None else [],
        "required_series": required,
        "required_series_presence": {
            ticker: bool(official_prices is not None and ticker in official_prices.columns) for ticker in required
        },
        "series_inventory": {},
        "vintage_status": "non_vintage_latest_observation_store",
    }
    if official_prices is None:
        return inventory
    duplicate_dates = int(official_prices.index.duplicated().sum())
    for ticker in required:
        if ticker not in official_prices.columns:
            inventory["series_inventory"][ticker] = {
                "present": False,
                "observation_count": 0,
                "null_count": None,
                "min_observation_date": None,
                "max_observation_date": None,
                "duplicate_date_count": duplicate_dates,
            }
            continue
        series = pd.to_numeric(official_prices[ticker], errors="coerce")
        valid = series.dropna()
        inventory["series_inventory"][ticker] = {
            "present": True,
            "observation_count": int(valid.size),
            "null_count": int(series.isna().sum()),
            "min_observation_date": _date_string(valid.index.min()) if not valid.empty else None,
            "max_observation_date": _date_string(valid.index.max()) if not valid.empty else None,
            "duplicate_date_count": duplicate_dates,
        }
    return inventory


def _market_snapshot_inventory(path: str | Path, prices: pd.DataFrame) -> dict[str, Any]:
    requested_path = str(path)
    raw_path = Path(path)
    resolved_path = raw_path if raw_path.is_absolute() else REPO_ROOT / raw_path
    resolved_path = resolved_path.resolve(strict=False)
    normalized = _normalize_prices_frame(prices)
    return {
        "loaded": True,
        "requested_path": requested_path,
        "resolved_path": str(resolved_path),
        "path": str(resolved_path),
        "sha256": _sha256_file(resolved_path),
        "row_count": len(normalized),
        "columns": list(normalized.columns),
        "min_observation_date": _date_string(normalized.index.min()) if not normalized.empty else None,
        "max_observation_date": _date_string(normalized.index.max()) if not normalized.empty else None,
        "duplicate_date_count": int(prices.index.duplicated(keep=False).sum()),
    }


def _validate_official_series_store(source: OfficialSeriesSource, config: dict[str, Any], official_prices: pd.DataFrame) -> None:
    required = official_series_tickers(config)
    missing = [ticker for ticker in required if ticker not in official_prices.columns]
    empty = [
        ticker
        for ticker in required
        if ticker in official_prices.columns and pd.to_numeric(official_prices[ticker], errors="coerce").dropna().empty
    ]
    if official_prices.empty or missing or empty:
        raise ValueError(
            "risk_engine_v2 canonical official-series CSV does not satisfy the required schema: "
            f"requested={source.requested_path} resolved={source.resolved_path} selection_origin={source.selection_origin} "
            f"required_series={required} missing_series={missing} empty_series={empty} row_count={len(official_prices)}"
        )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _date_string(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).date().isoformat()


def _eligible_replay_dates(
    prices: pd.DataFrame,
    *,
    indicator_map: dict[str, str],
    minimum_history: int,
    start_date: str | None,
    end_date: str | None,
) -> list[pd.Timestamp]:
    required = [ticker for ticker in dict.fromkeys(indicator_map.values()) if ticker in prices.columns]
    if not required:
        return []
    availability = prices[required].notna().sum(axis=1)
    min_required = max(1, min(6, len(required)))
    candidates = list(prices.index[availability >= min_required])
    if start_date:
        start_ts = pd.Timestamp(start_date)
        candidates = [date for date in candidates if date >= start_ts]
    if end_date:
        end_ts = pd.Timestamp(end_date)
        candidates = [date for date in candidates if date <= end_ts]
    candidates = [date for date in candidates if len(prices.loc[:date]) >= minimum_history]
    return sorted(candidates)


def _coverage_summary(prices: pd.DataFrame, config: dict[str, Any]) -> dict[str, Any]:
    settings = config.get("risk_engine_v2", {}) if isinstance(config, dict) else {}
    official = settings.get("official_series", {}) if isinstance(settings, dict) else {}
    official_tickers = [str(value) for value in official.values() if value]
    present_official = [ticker for ticker in official_tickers if ticker in prices.columns and prices[ticker].notna().any()]
    missing_official = [ticker for ticker in official_tickers if ticker not in present_official]
    indicator_map = default_risk_indicator_map(config)
    fallback_tickers = [
        ticker for ticker in dict.fromkeys(indicator_map.values()) if ticker in prices.columns and prices[ticker].notna().any()
    ]
    primary_coverage = round(len(present_official) / len(official_tickers), 6) if official_tickers else 0.0
    fallback_coverage = round(len(fallback_tickers) / max(1, len(dict.fromkeys(indicator_map.values()))), 6)
    return {
        "strict_primary_available": bool(official_tickers and len(present_official) == len(official_tickers)),
        "fallback_replay_available": bool(fallback_tickers),
        "primary_domain_coverage": primary_coverage,
        "fallback_domain_coverage": fallback_coverage,
        "primary_present_series": present_official,
        "primary_missing_series": missing_official,
    }


def _reconstructed_indicator_map(config: dict[str, Any]) -> dict[str, str]:
    return default_risk_indicator_map(config)


def _price_points_for_benchmark(prices: pd.DataFrame, ticker: str) -> list[dict[str, Any]]:
    if ticker not in prices.columns:
        return []
    series = prices[ticker].dropna().astype(float)
    return [{"date": index.date().isoformat(), "price": float(value)} for index, value in series.items()]


def _normalize_prices_frame(prices: pd.DataFrame) -> pd.DataFrame:
    clean = prices.copy()
    clean.index = pd.to_datetime(clean.index, errors="coerce").tz_localize(None)
    clean = clean[clean.index.notna()]
    clean = clean.sort_index()
    clean = clean[~clean.index.duplicated(keep="last")]
    return clean.apply(pd.to_numeric, errors="coerce")


def _read_prices(path: str | Path) -> pd.DataFrame:
    input_path = Path(path)
    frame = pd.read_csv(input_path, index_col=0)
    frame.index.name = "date"
    return frame


def _precompute_replay_stress_monitor(
    prices: pd.DataFrame,
    indicator_map: dict[str, str],
    windows: dict[str, int],
    zscore_window: int,
) -> dict[pd.Timestamp, list[dict[str, Any]]]:
    definitions = load_threshold_definitions()
    minimum_history = max(int(windows.get("long", 12)), int(zscore_window))
    feature_cache: dict[str, dict[str, Any]] = {}
    for ticker in dict.fromkeys(indicator_map.values()):
        if ticker not in prices.columns:
            continue
        series = prices[ticker].dropna().astype(float)
        if series.empty:
            continue
        feature_cache[ticker] = _build_feature_values(series, ticker, windows, zscore_window)

    monitor_by_date: dict[pd.Timestamp, list[dict[str, Any]]] = {}
    for evaluation_date in prices.index:
        rows: list[dict[str, Any]] = []
        for ticker in dict.fromkeys(indicator_map.values()):
            if ticker not in feature_cache:
                continue
            row = _precomputed_monitor_row(
                ticker=ticker,
                evaluation_date=pd.Timestamp(evaluation_date),
                features_cache=feature_cache[ticker],
                minimum_history=minimum_history,
                definitions=definitions,
            )
            if row is not None:
                rows.append(row)
        monitor_by_date[pd.Timestamp(evaluation_date)] = rows
    return monitor_by_date


def _precomputed_monitor_row(
    *,
    ticker: str,
    evaluation_date: pd.Timestamp,
    features_cache: dict[str, Any],
    minimum_history: int,
    definitions: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    raw_series_map = features_cache.get("_series")
    series_map: dict[str, Any] = raw_series_map if isinstance(raw_series_map, dict) else {}
    current_series = series_map.get("current")
    if current_series is None:
        return None
    usable = current_series.loc[:evaluation_date].dropna()
    if usable.empty:
        return None
    features: dict[str, Any] = {}
    truncated_series: dict[str, pd.Series] = {}
    for name, values in series_map.items():
        if not isinstance(values, pd.Series):
            continue
        truncated = values.loc[:evaluation_date]
        truncated_series[name] = truncated
        valid = truncated.dropna()
        features[name] = float(valid.iloc[-1]) if not valid.empty else float("nan")
    features["current"] = float(usable.iloc[-1])
    features["_series"] = truncated_series
    stress_state = _stress_state_for_row(ticker, features, definitions)
    latest_date = pd.Timestamp(usable.index[-1])
    stage_eligible = len(usable) >= minimum_history
    metadata = {
        "source_kind": "market_snapshot",
        "price_type": _price_type_for_ticker(ticker),
        "latest_observation_date": latest_date.date().isoformat(),
        "evaluation_date": evaluation_date.date().isoformat(),
        "history_length": len(usable),
        "freshness_status": "fresh",
        "quality_flags": [] if stage_eligible else ["insufficient_history"],
        "stage_eligible": stage_eligible,
        "corroborative_eligible": stage_eligible,
        "limitations": [] if stage_eligible else ["insufficient history for replay threshold evaluation"],
    }
    return {
        "ticker": ticker,
        "ticker_name_ja": ticker_label_ja(ticker),
        "current": round(float(features["current"]), 4),
        "change_1w": round(float(features.get("change_1w", float("nan"))), 4),
        "change_4w": round(float(features.get("change_4w", float("nan"))), 4),
        "change_12w": round(float(features.get("change_12w", float("nan"))), 4),
        "zscore": round(float(features.get("level_zscore", float("nan"))), 4),
        "recent_values": [round(float(value), 4) for value in usable.tail(5).tolist()],
        "signal_label": stress_state["signal_label"],
        "line_level": stress_state["line_level"],
        "line_level_label": LEVEL_LABELS[stress_state["line_level"]],
        "line_reason": stress_state["line_reason"],
        "threshold_evidence": stress_state["threshold_evidence"],
        "diagnostic_rule_hits": stress_state["diagnostic_rule_hits"],
        "accepted_rule": stress_state["accepted_rule"],
        "warning_line": stress_state["warning_line"],
        "danger_line": stress_state["danger_line"],
        "extreme_line": stress_state["extreme_line"],
        "recent_warning_hits": stress_state["recent_warning_hits"],
        "recent_danger_hits": stress_state["recent_danger_hits"],
        "recent_extreme_hits": stress_state["recent_extreme_hits"],
        "weight": stress_state["weight"],
        "pressure_score": round(stress_state["pressure_score"], 4),
        "health_score": round(1.0 - stress_state["pressure_score"], 4),
        "observation_metadata": metadata,
        "comparison_observation_dates": {},
        "quality_flags": metadata["quality_flags"],
        "stage_eligible": metadata["stage_eligible"],
        "corroborative_eligible": metadata["corroborative_eligible"],
        "limitations": metadata["limitations"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reconstructed diagnostic risk_engine_v2 replay from cached price history.")
    parser.add_argument("--input-prices", default="project/cache/market_snapshots/market_snapshot_2026-06-20_210709.csv")
    parser.add_argument("--config", default="project/config.yaml")
    parser.add_argument("--reports-dir", default="project/reports")
    parser.add_argument("--benchmark-ticker", default="ACWI")
    parser.add_argument("--start-date", default="2018-01-01")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--stride-weeks", type=int, default=4)
    parser.add_argument("--max-cases", type=int, default=None)
    parser.add_argument("--official-series-csv", default=None)
    args = parser.parse_args()
    print(
        json.dumps(
            run_reconstructed_risk_engine_v2_replay(
                input_prices=args.input_prices,
                config_path=args.config,
                reports_dir=args.reports_dir,
                benchmark_ticker=args.benchmark_ticker,
                start_date=args.start_date,
                end_date=args.end_date,
                stride_weeks=args.stride_weeks,
                max_cases=args.max_cases,
                official_series_csv=args.official_series_csv,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
