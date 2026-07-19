from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from project.history_dashboard import write_dashboard
from project.report_generator import write_reports
from project.risk_domain_state import write_risk_domain_state


OpenDashboardFn = Callable[[str | Path], bool]


@dataclass(frozen=True)
class PersistencePolicy:
    persist_reports: bool = True
    persist_summary: bool = True
    persist_history: bool = True
    persist_risk_state: bool = True
    prune_history: bool = True
    write_dashboard: bool = True
    policy_name: str = "normal"


NORMAL_PERSISTENCE_POLICY = PersistencePolicy()
ACTUAL_SMOKE_PERSISTENCE_POLICY = PersistencePolicy(
    persist_reports=True,
    persist_summary=True,
    persist_history=False,
    persist_risk_state=False,
    prune_history=False,
    write_dashboard=True,
    policy_name="actual_smoke_non_persistent",
)


def persist_report(
    report: dict[str, Any],
    paths: dict[str, Any],
    logger: Any,
    open_dashboard: bool = False,
    persist_history: bool = True,
    history_slot: tuple[int, int] | None = None,
    open_dashboard_file_fn: OpenDashboardFn | None = None,
    persistence_policy: PersistencePolicy | None = None,
) -> dict[str, Any]:
    policy = persistence_policy or NORMAL_PERSISTENCE_POLICY
    if not policy.persist_reports:
        logger.info("Skipped report persistence due to policy=%s.", policy.policy_name)
        return report
    markdown_path, html_path, history_markdown_path, history_html_path, history_json_path = write_reports(
        report,
        reports_dir=paths["reports_dir"],
        sample_output_dir=paths["sample_output_dir"],
    )

    logger.info("Report written to %s and %s", markdown_path, html_path)
    summary_path = Path(paths["reports_dir"]) / "report_summary.json"
    summary_json = json.dumps(report, ensure_ascii=False, indent=2)
    if policy.persist_summary:
        summary_path.write_text(summary_json, encoding="utf-8")
    if policy.persist_history and persist_history and should_persist_history(report):
        history_json_path.write_text(summary_json, encoding="utf-8")
        if policy.persist_risk_state:
            persist_risk_engine_state(report, logger)
        else:
            logger.info("Skipped risk engine v2 state persistence due to policy=%s.", policy.policy_name)
        logger.info("History written to %s, %s and %s", history_markdown_path, history_html_path, history_json_path)
    else:
        remove_report_files(history_markdown_path, history_html_path, history_json_path)
        logger.info("Skipped history persistence for this run due to non-live or non-decision-safe context.")
    if policy.prune_history:
        prune_history_directory(Path(paths["reports_dir"]) / "history", logger, history_slot=history_slot)
    if policy.write_dashboard:
        dashboard_path = write_dashboard(paths["reports_dir"])
        logger.info("Dashboard written to %s", dashboard_path)
    if open_dashboard and open_dashboard_file_fn is not None:
        opened = open_dashboard_file_fn(html_path)
        if opened:
            logger.info("Latest report opened in default browser: %s", html_path)
        else:
            logger.warning("Failed to open latest report in default browser: %s", html_path)
    return report


def persist_risk_engine_state(report: dict[str, Any], logger: Any) -> None:
    state_info = report.get("risk_engine_state", {})
    if not isinstance(state_info, dict) or not state_info.get("will_persist"):
        return
    path = state_info.get("path")
    next_state = state_info.get("next_state")
    if not path or not isinstance(next_state, dict):
        return
    written = write_risk_domain_state(path, next_state)
    logger.info("Risk engine v2 state written to %s", written)


def should_persist_history(report: dict[str, Any]) -> bool:
    reliability = report.get("data_reliability", {})
    return bool(reliability.get("decision_allowed", False))


def remove_report_files(*paths: Path) -> None:
    for path in paths:
        try:
            if path.exists():
                path.unlink()
        except FileNotFoundError:
            continue


def prune_history_directory(history_dir: Path, logger: Any, history_slot: tuple[int, int] | None = None) -> None:
    if not history_dir.exists():
        return

    grouped: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
    for json_path in history_dir.glob("report_*.json"):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Skipping unreadable history file %s: %s", json_path, exc)
            continue
        if not should_persist_history(data):
            remove_report_bundle(json_path)
            continue
        generated_at = str(data.get("generated_at", ""))
        day_key = generated_at[:10] if len(generated_at) >= 10 else json_path.stem[:10]
        grouped.setdefault(day_key, []).append((json_path, data))

    for day_entries in grouped.values():
        keep_json, _ = select_history_entry_to_keep(day_entries, history_slot)
        for json_path, _ in day_entries:
            if json_path != keep_json:
                remove_report_bundle(json_path)


def select_history_entry_to_keep(
    day_entries: list[tuple[Path, dict[str, Any]]],
    history_slot: tuple[int, int] | None,
) -> tuple[Path, dict[str, Any]]:
    if history_slot is not None:
        target_hour, target_minute = history_slot
        canonical_entries = [
            item for item in day_entries
            if generated_at_matches_slot(str(item[1].get("generated_at", "")), target_hour, target_minute)
        ]
        if canonical_entries:
            return max(canonical_entries, key=lambda item: str(item[1].get("generated_at", item[0].stem)))
    return max(day_entries, key=lambda item: str(item[1].get("generated_at", item[0].stem)))


def generated_at_matches_slot(generated_at: str, hour: int, minute: int) -> bool:
    try:
        stamp = datetime.fromisoformat(generated_at)
    except ValueError:
        return False
    return stamp.hour == hour and stamp.minute == minute


def remove_report_bundle(json_path: Path) -> None:
    remove_report_files(
        json_path,
        json_path.with_suffix(".md"),
        json_path.with_suffix(".html"),
    )
