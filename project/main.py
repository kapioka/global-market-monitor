from __future__ import annotations

import argparse
import json
import re
import sys
import webbrowser
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from project.analogue_search import find_analogues
from project.alerts import build_alerts
from project.asset_compare import compare_asset_classes
from project.config_loader import load_config
from project.credit_monitor import build_credit_monitor
from project.cycle_analysis import analyze_cycle
from project.data_fetcher import FetchResult, fetch_market_data
from project.history_dashboard import write_dashboard
from project.inflation_monitor import build_inflation_monitor
from project.investment_candidates import build_investment_candidates
from project.preprocess import compute_returns, preprocess_prices
from project.recovery_candidates import build_recovery_candidates
from project.regime_leading_candidates import build_regime_leading_candidates
from project.regime_analysis import analyze_market_regime
from project.report_generator import write_reports
from project.runtime import ensure_directories, setup_logging
from project.scheduler import run_scheduler
from project.scoring import score_market
from project.sector_rotation import analyze_sector_rotation
from project.spot_signal import evaluate_spot_signal

HISTORY_FILENAME_RE = re.compile(r"report_(\d{4}-\d{2}-\d{2})_\d{6}\.json$")


def default_config_path() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        bundle_dir = Path(getattr(sys, "_MEIPASS", exe_dir))
        for candidate in (
            exe_dir / "project" / "config.yaml",
            exe_dir / "_internal" / "project" / "config.yaml",
            bundle_dir / "project" / "config.yaml",
        ):
            if candidate.exists():
                return candidate
        return exe_dir / "project" / "config.yaml"
    return Path(__file__).resolve().parent / "config.yaml"


def open_dashboard_file(dashboard_path: str | Path) -> bool:
    path = Path(dashboard_path).resolve()
    try:
        return webbrowser.open(path.as_uri())
    except Exception:
        return False


def collect_tickers(config: dict[str, Any]) -> list[str]:
    ticker_groups = config["tickers"]
    tickers: list[str] = []
    for mapping in ticker_groups.values():
        tickers.extend(mapping.values())
    deduped: list[str] = []
    for ticker in tickers:
        if ticker not in deduped:
            deduped.append(ticker)
    return deduped


def fetch_market_snapshot(
    config: dict[str, Any],
    logger: Any,
    sample_only: bool = False,
    interval_override: str | None = None,
) -> FetchResult:
    tickers = collect_tickers(config)
    return fetch_market_data(
        tickers=tickers,
        period_years=config["data"]["period_years"],
        interval=interval_override or config["data"]["interval"],
        logger=logger,
        use_sample_on_failure=True if sample_only else config["data"]["use_sample_on_failure"],
        cache_dir=config["paths"]["cache_dir"],
        force_sample=sample_only,
    )


def generated_at_for_date(config: dict[str, Any], as_of_date: date | None) -> str:
    if as_of_date is None:
        return datetime.now().isoformat(timespec="seconds")
    scheduler_config = config.get("scheduler", {})
    hour = int(scheduler_config.get("hour", 7))
    minute = int(scheduler_config.get("minute", 30))
    return datetime.combine(as_of_date, time(hour=hour, minute=minute)).isoformat(timespec="seconds")


def existing_history_dates(reports_dir: str | Path) -> set[date]:
    history_dir = Path(reports_dir) / "history"
    if not history_dir.exists():
        return set()

    dates: set[date] = set()
    for file_path in history_dir.glob("report_*.json"):
        match = HISTORY_FILENAME_RE.match(file_path.name)
        if match:
            dates.add(date.fromisoformat(match.group(1)))
    return dates


def compute_backfill_dates(
    reports_dir: str | Path,
    today: date,
    max_backfill_days: int,
) -> list[date]:
    if max_backfill_days <= 0:
        return []

    existing = existing_history_dates(reports_dir)
    yesterday = today - timedelta(days=1)
    window_start = today - timedelta(days=max_backfill_days)
    if yesterday < window_start:
        return []

    missing: list[date] = []
    cursor = window_start
    while cursor <= yesterday:
        if cursor not in existing:
            missing.append(cursor)
        cursor += timedelta(days=1)
    return missing


def resample_weekly_closes(prices: Any) -> Any:
    if prices.empty:
        return prices
    weekly = prices.resample("W-FRI").last().dropna(how="all")
    return weekly.ffill()


def build_report(
    config: dict[str, Any],
    fetch: FetchResult,
    as_of_date: date | None = None,
    resample_weekly: bool = False,
) -> dict[str, Any]:
    prices = fetch.prices
    if as_of_date is not None and not prices.empty:
        cutoff = datetime.combine(as_of_date, time.max)
        prices = prices.loc[prices.index <= cutoff]
    if resample_weekly:
        prices = resample_weekly_closes(prices)

    prices, preprocessing_warnings = preprocess_prices(
        prices, config["data"]["min_history_points"]
    )
    returns = compute_returns(prices)
    availability_map = {entry.get("requested_ticker"): entry for entry in fetch.acquisition_log}

    credit_monitor = build_credit_monitor(
        prices,
        config["tickers"].get("credit", {}),
        config["data"].get("monitor_windows_weeks", {"short": 1, "medium": 4, "long": 12}),
        int(config["data"].get("zscore_window_weeks", 52)),
    )
    inflation_monitor = build_inflation_monitor(
        prices,
        config["tickers"].get("inflation", {}),
        config["data"].get("monitor_windows_weeks", {"short": 1, "medium": 4, "long": 12}),
        int(config["data"].get("zscore_window_weeks", 52)),
    )
    usable_credit_monitor = _filter_live_monitor_rows(credit_monitor, availability_map)
    usable_inflation_monitor = _filter_live_monitor_rows(inflation_monitor, availability_map)
    reliability = _assess_data_reliability(config, fetch)
    regime = analyze_market_regime(prices, returns, usable_credit_monitor, usable_inflation_monitor, config["thresholds"])
    cycle_ticker = regime["benchmark"]
    cycle = analyze_cycle(prices[cycle_ticker])
    score = score_market(regime, cycle, usable_credit_monitor, config["weights"], config["thresholds"])
    sector_rotation = analyze_sector_rotation(prices, config["tickers"]["sector_etfs"])
    asset_compare = compare_asset_classes(prices, config["tickers"]["asset_classes"])
    spot_signal = evaluate_spot_signal(score, regime, cycle, usable_credit_monitor, usable_inflation_monitor, config["thresholds"])
    alerts = build_alerts(regime, spot_signal, usable_credit_monitor, usable_inflation_monitor)
    analogues = find_analogues(
        prices[cycle_ticker], max_results=config["data"]["max_analogue_results"]
    )

    warnings = fetch.warnings + preprocessing_warnings
    if not reliability["decision_allowed"]:
        regime = _guarded_regime(regime, reliability)
        cycle = _guarded_cycle(cycle)
        score = _guarded_score(score)
        spot_signal = _guarded_spot_signal(reliability)
        alerts = [_data_quality_alert(reliability)]
        sector_rotation = {"table": [], "chart": {}}
        asset_compare = []
        analogues = []
        warnings.append(reliability["reason"])
    investment_candidates = build_investment_candidates(
        {
            "regime": regime,
            "spot_signal": spot_signal,
            "data_reliability": reliability,
            "alerts": alerts,
            "asset_compare": asset_compare,
            "sector_rotation": sector_rotation,
        }
    )
    recovery_candidates = build_recovery_candidates(
        prices=prices,
        asset_map=config["tickers"]["asset_classes"],
        sector_map=config["tickers"]["sector_etfs"],
        availability_map=availability_map,
        regime=regime,
        cycle=cycle,
        reliability=reliability,
        alerts=alerts,
    )
    regime_leading_candidates = build_regime_leading_candidates(
        prices=prices,
        sector_map=config["tickers"]["sector_etfs"],
        region_map=config["tickers"].get("global_equities", {}),
        asset_map=config["tickers"].get("asset_classes", {}),
        sector_rotation=sector_rotation,
        availability_map=availability_map,
        regime=regime,
        reliability=reliability,
        alerts=alerts,
    )
    return {
        "title": config["app"]["report_title"],
        "generated_at": generated_at_for_date(config, as_of_date),
        "data_source": fetch.source,
        "runtime_context": _runtime_context(),
        "fetch_diagnostics": fetch.diagnostics,
        "data_reliability": reliability,
        "regime": regime,
        "cycle": cycle,
        "score": score,
        "sector_rotation": sector_rotation,
        "asset_compare": asset_compare,
        "credit_monitor": usable_credit_monitor,
        "inflation_monitor": usable_inflation_monitor,
        "spot_signal": spot_signal,
        "investment_candidates": investment_candidates,
        "recovery_candidates": recovery_candidates,
        "regime_leading_candidates": regime_leading_candidates,
        "alerts": alerts,
        "analogues": analogues,
        "warnings": warnings,
        "data_availability": fetch.acquisition_log,
    }


def _runtime_context() -> dict[str, Any]:
    executable = Path(sys.executable).resolve()
    return {
        "is_frozen": bool(getattr(sys, "frozen", False)),
        "python_executable": str(executable),
        "working_directory": str(Path.cwd().resolve()),
    }


def _filter_live_monitor_rows(rows: list[dict[str, Any]], availability_map: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    live_statuses = {"ok", "proxy_fallback"}
    filtered: list[dict[str, Any]] = []
    for row in rows:
        entry = availability_map.get(row.get("ticker"))
        if entry is None or entry.get("status") in live_statuses:
            filtered.append(row)
    return filtered


def _assess_data_reliability(config: dict[str, Any], fetch: FetchResult) -> dict[str, Any]:
    summary = fetch.diagnostics.get("summary", {})
    total = int(summary.get("requested_count", len(fetch.acquisition_log)) or len(fetch.acquisition_log) or 0)
    live_ok = sum(1 for item in fetch.acquisition_log if item.get("status") in {"ok", "proxy_fallback"})
    sample_count = int(summary.get("sample_fallback_count", 0))
    unavailable_count = int(summary.get("unavailable_count", 0))
    live_ratio = round((live_ok / total), 4) if total else 0.0
    critical_tickers = _critical_tickers(config)
    critical_failures = [
        item.get("requested_ticker", "-")
        for item in fetch.acquisition_log
        if item.get("requested_ticker") in critical_tickers and item.get("status") in {"sample_fallback", "unavailable"}
    ]
    decision_allowed = not critical_failures and live_ratio >= 0.75
    if decision_allowed:
        level = "high" if sample_count == 0 and unavailable_count == 0 and fetch.source in {"yfinance", "mixed"} else "medium"
        reason = "重要系列の live 取得は概ね維持できているため、通常の判定ロジックを継続します。"
    else:
        level = "low"
        if critical_failures:
            reason = f"重要系列の live 取得に失敗したため、通常の判定ロジックを保留しました。対象: {', '.join(critical_failures)}"
        else:
            reason = f"live 取得率が不足しているため、通常の判定ロジックを保留しました。取得率: {live_ratio:.0%}"
    return {
        "level": level,
        "decision_allowed": decision_allowed,
        "live_ratio": live_ratio,
        "critical_failures": critical_failures,
        "reason": reason,
    }


def _critical_tickers(config: dict[str, Any]) -> set[str]:
    critical = {"ACWI", "HYG", "LQD", "CL=F", "DX-Y.NYB", "GC=F"}
    global_equities = list(config.get("tickers", {}).get("global_equities", {}).values())
    if global_equities:
        critical.add(global_equities[0])
    return critical


def _guarded_regime(regime: dict[str, Any], reliability: dict[str, Any]) -> dict[str, Any]:
    guarded = dict(regime)
    guarded["regime_label"] = "data_unavailable"
    guarded["regime_score"] = None
    guarded["credit_regime_flag"] = "neutral"
    guarded["inflation_regime_flag"] = "neutral"
    guarded["guard_reason"] = reliability["reason"]
    return guarded


def _guarded_cycle(cycle: dict[str, Any]) -> dict[str, Any]:
    guarded = dict(cycle)
    guarded["phase_label"] = "insufficient_data"
    guarded["phase_angle_deg"] = None
    return guarded


def _guarded_score(score: dict[str, Any]) -> dict[str, Any]:
    guarded = dict(score)
    guarded["raw_total_score"] = score.get("total_score")
    guarded["total_score"] = None
    return guarded


def _guarded_spot_signal(reliability: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": "wait",
        "score": None,
        "adjusted_score": None,
        "regime_penalty": None,
        "risk_off_relief_applied": False,
        "credit_stress_score": None,
        "credit_summary": "重要系列の live 取得不足により、信用判定は保留しています。",
        "second_leg_risk": "high",
        "data_guard_applied": True,
        "rationale": [
            "重要系列の live 取得が不足したため、通常の投資判断ロジックは保留しました。",
            reliability["reason"],
            "sample 代替データを使った強気・弱気の判定は行っていません。",
        ],
    }


def _data_quality_alert(reliability: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "data_quality_hold",
        "category": "market",
        "severity": "high",
        "title": "データ不足のため判定保留",
        "message": reliability["reason"],
        "evidence": reliability.get("critical_failures", []),
        "source_flags": [reliability.get("level", "low")],
    }


def persist_report(
    report: dict[str, Any],
    paths: dict[str, Any],
    logger: Any,
    open_dashboard: bool = False,
    persist_history: bool = True,
) -> dict[str, Any]:
    markdown_path, html_path, history_markdown_path, history_html_path, history_json_path = write_reports(
        report,
        reports_dir=paths["reports_dir"],
        sample_output_dir=paths["sample_output_dir"],
    )

    logger.info("Report written to %s and %s", markdown_path, html_path)
    summary_path = Path(paths["reports_dir"]) / "report_summary.json"
    summary_json = json.dumps(report, ensure_ascii=False, indent=2)
    summary_path.write_text(summary_json, encoding="utf-8")
    if persist_history and _should_persist_history(report):
        history_json_path.write_text(summary_json, encoding="utf-8")
        logger.info("History written to %s, %s and %s", history_markdown_path, history_html_path, history_json_path)
    else:
        _remove_report_files(history_markdown_path, history_html_path, history_json_path)
        logger.info("Skipped history persistence for this run due to non-live or non-decision-safe context.")
    _prune_history_directory(Path(paths["reports_dir"]) / "history", logger)
    dashboard_path = write_dashboard(paths["reports_dir"])
    logger.info("Dashboard written to %s", dashboard_path)
    if open_dashboard:
        opened = open_dashboard_file(dashboard_path)
        if opened:
            logger.info("Dashboard opened in default browser: %s", dashboard_path)
        else:
            logger.warning("Failed to open dashboard in default browser: %s", dashboard_path)
    return report


def run_monitor(
    config_path: str | Path,
    sample_only: bool = False,
    open_dashboard: bool = False,
    as_of_date: date | None = None,
    fetch_result: FetchResult | None = None,
    resample_weekly: bool = False,
) -> dict[str, Any]:
    config = load_config(config_path)
    paths = config["paths"]
    ensure_directories(
        [
            paths["logs_dir"],
            paths["reports_dir"],
            paths["sample_output_dir"],
            paths["cache_dir"],
        ]
    )
    logger = setup_logging(paths["logs_dir"], config["app"]["log_level"])
    logger.info("Run started (sample_only=%s, as_of_date=%s, resample_weekly=%s).", sample_only, as_of_date, resample_weekly)
    logger.info("Stage 1/3: fetching market snapshot.")
    fetch = fetch_result or fetch_market_snapshot(config, logger, sample_only=sample_only)
    logger.info("Stage 2/3: building report payload.")
    report = build_report(config, fetch, as_of_date=as_of_date, resample_weekly=resample_weekly)
    logger.info("Stage 3/3: writing reports and dashboard.")
    return persist_report(report, paths, logger, open_dashboard=open_dashboard, persist_history=not sample_only)


def run_with_backfill(
    config_path: str | Path,
    sample_only: bool = False,
    open_dashboard: bool = False,
) -> dict[str, Any]:
    config = load_config(config_path)
    paths = config["paths"]
    ensure_directories(
        [
            paths["logs_dir"],
            paths["reports_dir"],
            paths["sample_output_dir"],
            paths["cache_dir"],
        ]
    )
    logger = setup_logging(paths["logs_dir"], config["app"]["log_level"])
    logger.info("Run with backfill started (sample_only=%s).", sample_only)
    startup_config = config.get("startup", {})
    max_backfill_days = int(startup_config.get("max_backfill_days", 14))
    backfill_dates = compute_backfill_dates(paths["reports_dir"], date.today(), max_backfill_days)
    logger.info("Stage 1/4: fetching daily market snapshot for backfill and latest run.")
    fetch = fetch_market_snapshot(config, logger, sample_only=sample_only, interval_override="1d")

    logger.info("Stage 2/4: processing %d backfill day(s).", len(backfill_dates))
    for missing_date in backfill_dates:
        logger.info("Backfilling missing report for %s using actual daily closes", missing_date.isoformat())
        report = build_report(config, fetch, as_of_date=missing_date, resample_weekly=True)
        persist_report(report, paths, logger, open_dashboard=False, persist_history=not sample_only)

    logger.info("Stage 3/4: building latest weekly report.")
    latest_report = build_report(config, fetch, as_of_date=None, resample_weekly=True)
    logger.info("Stage 4/4: writing latest reports and dashboard.")
    return persist_report(latest_report, paths, logger, open_dashboard=open_dashboard, persist_history=not sample_only)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Global market monitor")
    parser.add_argument(
        "--config",
        default=str(default_config_path()),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--sample-only",
        action="store_true",
        help="Force synthetic data instead of remote fetch.",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run once and keep the daily scheduler active using config scheduler settings.",
    )
    return parser


def _should_persist_history(report: dict[str, Any]) -> bool:
    reliability = report.get("data_reliability", {})
    return bool(reliability.get("decision_allowed", False))


def _remove_report_files(*paths: Path) -> None:
    for path in paths:
        try:
            if path.exists():
                path.unlink()
        except FileNotFoundError:
            continue


def _prune_history_directory(history_dir: Path, logger: Any) -> None:
    if not history_dir.exists():
        return

    grouped: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
    for json_path in history_dir.glob("report_*.json"):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Skipping unreadable history file %s: %s", json_path, exc)
            continue
        if not _should_persist_history(data):
            _remove_report_bundle(json_path)
            continue
        generated_at = str(data.get("generated_at", ""))
        day_key = generated_at[:10] if len(generated_at) >= 10 else json_path.stem[:10]
        grouped.setdefault(day_key, []).append((json_path, data))

    for day_entries in grouped.values():
        keep_json, _ = max(day_entries, key=lambda item: str(item[1].get("generated_at", item[0].stem)))
        for json_path, _ in day_entries:
            if json_path != keep_json:
                _remove_report_bundle(json_path)


def _remove_report_bundle(json_path: Path) -> None:
    stem = json_path.stem
    _remove_report_files(
        json_path,
        json_path.with_suffix(".md"),
        json_path.with_suffix(".html"),
    )


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    scheduler_config = config["scheduler"]

    if args.schedule or scheduler_config.get("enabled", False):
        run_scheduler(
            job=lambda: run_monitor(config_path=args.config, sample_only=args.sample_only),
            hour=scheduler_config["hour"],
            minute=scheduler_config["minute"],
            run_immediately=True,
        )
        return

    run_with_backfill(config_path=args.config, sample_only=args.sample_only, open_dashboard=True)


if __name__ == "__main__":
    main()


