from __future__ import annotations

import argparse
import sys
import webbrowser
from datetime import date
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from project.backfill import compute_backfill_dates, existing_history_files_for_date, history_slot_time
from project.config_loader import load_config
from project.data_fetcher import FetchResult
from project.pipeline import build_report, collect_tickers, fetch_market_snapshot
from project.report_runtime import persist_report, should_persist_history
from project.runtime import console_spinner, ensure_directories, setup_logging
from project.scheduler import run_scheduler
from project.snapshot_store import (
    fetch_snapshot_observed_at,
    load_fetch_snapshot,
    load_latest_fetch_snapshot,
    save_fetch_snapshot,
    snapshot_exists_for_slot,
)
from project.risk_line_review_status import run_periodic_risk_line_maintenance_with_progress


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
    target_history_slot = history_slot_time(config)
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
    logger.info("Stage 0/3: refreshing risk-line drift/recalibration maintenance.")
    with console_spinner("threshold maintenance"):
        maintenance = run_periodic_risk_line_maintenance_with_progress(
            config_path,
            sample_only=sample_only,
            progress_callback=lambda event: logger.info(
                "Threshold maintenance %s: %s (%.3fs).",
                event.get("stage", "-"),
                event.get("message", "-"),
                float(event.get("elapsed_seconds", 0.0) or 0.0),
            ),
        )
    logger.info("Stage 1/3: fetching market snapshot.")
    with console_spinner("market data fetch"):
        fetch = fetch_result or fetch_market_snapshot(config, logger, sample_only=sample_only)
    if not sample_only and fetch_result is None:
        save_fetch_snapshot(fetch, paths["cache_dir"], fetch_snapshot_observed_at(), logger)
    logger.info("Stage 2/3: building report payload.")
    with console_spinner("building report"):
        report = build_report(
            config, fetch, as_of_date=as_of_date, resample_weekly=resample_weekly, maintenance_summary=maintenance.get("maintenance")
        )
    logger.info("Stage 3/3: writing reports and dashboard.")
    return persist_report(
        report,
        paths,
        logger,
        open_dashboard=open_dashboard,
        persist_history=not sample_only,
        history_slot=target_history_slot,
        open_dashboard_file_fn=open_dashboard_file,
    )


def run_with_backfill(
    config_path: str | Path,
    sample_only: bool = False,
    open_dashboard: bool = False,
) -> dict[str, Any]:
    config = load_config(config_path)
    paths = config["paths"]
    target_history_slot = history_slot_time(config)
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
    backfill_dates = compute_backfill_dates(config, paths["reports_dir"], date.today(), max_backfill_days)
    logger.info("Stage 0/4: refreshing risk-line drift/recalibration maintenance.")
    with console_spinner("threshold maintenance"):
        maintenance = run_periodic_risk_line_maintenance_with_progress(
            config_path,
            sample_only=sample_only,
            progress_callback=lambda event: logger.info(
                "Threshold maintenance %s: %s (%.3fs).",
                event.get("stage", "-"),
                event.get("message", "-"),
                float(event.get("elapsed_seconds", 0.0) or 0.0),
            ),
        )
    logger.info("Stage 1/4: fetching daily market snapshot for backfill and latest run.")
    with console_spinner("market data fetch"):
        fetch = fetch_market_snapshot(config, logger, sample_only=sample_only, interval_override="1d")
    if not sample_only:
        save_fetch_snapshot(fetch, paths["cache_dir"], fetch_snapshot_observed_at(), logger)

    logger.info("Stage 2/4: processing %d backfill day(s).", len(backfill_dates))
    for missing_date in backfill_dates:
        existing_history = existing_history_files_for_date(paths["reports_dir"], missing_date)
        existing_names = [path.name for path in existing_history]
        snapshot_fetch = None
        alignment_source = "daily_fallback"
        if snapshot_exists_for_slot(paths["cache_dir"], missing_date, target_history_slot):
            snapshot_fetch = load_fetch_snapshot(paths["cache_dir"], missing_date, target_history_slot)
            if snapshot_fetch is not None:
                alignment_source = "saved_canonical_snapshot"
        if snapshot_fetch is not None:
            logger.info(
                "Backfilling %s from saved canonical snapshot %02d:%02d",
                missing_date.isoformat(),
                target_history_slot[0],
                target_history_slot[1],
            )
        else:
            logger.info("Backfilling missing report for %s using actual daily closes", missing_date.isoformat())
        if existing_names:
            logger.info(
                "Replacing non-canonical history for %s. Existing entries: %s. Target slot: %02d:%02d. Source: %s",
                missing_date.isoformat(),
                ", ".join(existing_names),
                target_history_slot[0],
                target_history_slot[1],
                alignment_source,
            )
        with console_spinner(f"building report for {missing_date.isoformat()}"):
            report = build_report(
                config,
                snapshot_fetch or fetch,
                as_of_date=missing_date,
                resample_weekly=True,
                maintenance_summary=maintenance.get("maintenance"),
                history_alignment={
                    "target_date": missing_date.isoformat(),
                    "target_slot": f"{target_history_slot[0]:02d}:{target_history_slot[1]:02d}",
                    "rebuild_trigger": "missing_canonical_slot",
                    "replaced_history_entries": existing_names,
                    "source": alignment_source,
                },
            )
        persist_report(
            report,
            paths,
            logger,
            open_dashboard=False,
            persist_history=not sample_only,
            history_slot=target_history_slot,
            open_dashboard_file_fn=open_dashboard_file,
        )

    logger.info("Stage 3/4: building latest weekly report.")
    with console_spinner("building latest weekly report"):
        latest_report = build_report(
            config, fetch, as_of_date=None, resample_weekly=True, maintenance_summary=maintenance.get("maintenance")
        )
    logger.info("Stage 4/4: writing latest reports and dashboard.")
    return persist_report(
        latest_report,
        paths,
        logger,
        open_dashboard=open_dashboard,
        persist_history=not sample_only,
        history_slot=target_history_slot,
        open_dashboard_file_fn=open_dashboard_file,
    )


def run_actual_smoke(config_path: str | Path, open_dashboard: bool = False) -> dict[str, Any]:
    config = load_config(config_path)
    paths = config["paths"]
    ensure_directories([paths["logs_dir"], paths["reports_dir"], paths["sample_output_dir"], paths["cache_dir"]])
    logger = setup_logging(paths["logs_dir"], config["app"]["log_level"])
    cached_fetch = load_latest_fetch_snapshot(paths["cache_dir"])
    if cached_fetch is not None:
        logger.info("Actual-data smoke using latest acquired snapshot from cache (source=%s).", cached_fetch.source)
    else:
        logger.info("Actual-data smoke found no acquired snapshot in cache; attempting the normal remote fetch path.")
    try:
        return run_monitor(
            config_path=config_path,
            sample_only=False,
            open_dashboard=open_dashboard,
            fetch_result=cached_fetch,
            resample_weekly=True,
        )
    except Exception as exc:
        logger.error("Actual-data smoke failed while using cached acquired data or attempting remote fetch: %s", exc)
        raise


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
        "--actual-smoke",
        action="store_true",
        help="Run an optional actual-data smoke check: reuse the latest acquired cache snapshot, or attempt normal fetch if absent.",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run once and keep the daily scheduler active using config scheduler settings.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_config(args.config)
    scheduler_config = config["scheduler"]

    if args.actual_smoke:
        if args.sample_only or args.schedule:
            raise SystemExit("--actual-smoke cannot be combined with --sample-only or --schedule.")
        run_actual_smoke(config_path=args.config, open_dashboard=True)
        return

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
