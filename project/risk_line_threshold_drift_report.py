from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project.config_loader import load_config
from project.risk_line_reality_check_report import _fetch_prices
from project.risk_line_threshold_store import ACTIVE_THRESHOLDS_PATH, load_threshold_payload
from project.stress_monitor import build_stress_monitor, default_risk_indicator_map


REPORT_JSON = "risk_line_threshold_drift.json"
REPORT_MD = "risk_line_threshold_drift.md"


def write_risk_line_threshold_drift_report(config_path: str | Path, sample_only: bool = False) -> tuple[Path, Path]:
    config = load_config(config_path)
    reports_dir = Path(config["paths"]["reports_dir"])
    reports_dir.mkdir(parents=True, exist_ok=True)
    report = build_risk_line_threshold_drift_report(config, sample_only=sample_only)
    json_path = reports_dir / REPORT_JSON
    md_path = reports_dir / REPORT_MD
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_risk_line_threshold_drift_markdown(report), encoding="utf-8")
    return json_path, md_path


def build_risk_line_threshold_drift_report(config: dict[str, Any], sample_only: bool = False) -> dict[str, Any]:
    prices = _fetch_prices(config, sample_only=sample_only)
    payload = load_threshold_payload(ACTIVE_THRESHOLDS_PATH)
    indicators = payload.get("indicators", {})
    monitor_rows = build_stress_monitor(
        prices,
        default_risk_indicator_map(config),
        config["data"].get("monitor_windows_weeks", {"short": 1, "medium": 4, "long": 12}),
        int(config["data"].get("zscore_window_weeks", 52)),
        threshold_definitions=indicators,
    )
    by_ticker = {row["ticker"]: row for row in monitor_rows}
    drift_rows = []
    for ticker, indicator in indicators.items():
        for stage, rule in (indicator.get("thresholds") or {}).items():
            series_report = _drift_for_rule(prices, ticker, rule, config)
            latest = by_ticker.get(ticker)
            drift_rows.append(
                {
                    "ticker": ticker,
                    "stage": stage,
                    "feature": rule.get("feature"),
                    "threshold": rule.get("threshold"),
                    "direction": rule.get("direction"),
                    **series_report,
                    "current_line_level": latest.get("line_level") if latest else None,
                }
            )
    return {
        "active_version": payload.get("threshold_set", {}).get("version"),
        "generated_at": payload.get("threshold_set", {}).get("generated_at"),
        "summary": _build_drift_summary(drift_rows),
        "drift_rows": drift_rows,
    }


def load_risk_line_threshold_drift_snapshot(reports_dir: str | Path) -> dict[str, Any] | None:
    path = Path(reports_dir) / REPORT_JSON
    if not path.exists():
        return None
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return {
        "active_version": report.get("active_version"),
        "generated_at": report.get("generated_at"),
        "summary": report.get("summary") or _build_drift_summary(report.get("drift_rows", [])),
    }


def render_risk_line_threshold_drift_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary") or _build_drift_summary(report.get("drift_rows", []))
    lines = [
        "# Risk Line Threshold Drift",
        "",
        f"- active_version: {report.get('active_version', '-')}",
        f"- generated_at: {report.get('generated_at', '-')}",
        f"- summary: stable={summary.get('stable_count', 0)} / watch={summary.get('watch_count', 0)} / review={summary.get('review_count', 0)} / unavailable={summary.get('unavailable_count', 0)}",
        f"- review_targets: {', '.join(summary.get('review_targets', [])) or '-'}",
        f"- watch_targets: {', '.join(summary.get('watch_targets', [])) or '-'}",
    ]
    for row in report.get("drift_rows", []):
        lines.extend([
            "",
            f"## {row.get('ticker')} / {row.get('stage')}",
            f"- feature: {row.get('feature')} / threshold: {row.get('threshold')} / direction: {row.get('direction')}",
            f"- recent_hit_rate_26w: {row.get('recent_hit_rate_26w')}",
            f"- history_hit_rate: {row.get('history_hit_rate')}",
            f"- drift_gap: {row.get('drift_gap')}",
            f"- drift_status: {row.get('drift_status')}",
            f"- current_line_level: {row.get('current_line_level')}",
        ])
    return "\n".join(lines) + "\n"


def _drift_for_rule(prices, ticker: str, rule: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    from project.stress_monitor import _build_feature_values as build_feature_values

    if ticker == "HYG/LQD":
        series = (prices["HYG"].astype(float) / prices["LQD"].astype(float)).dropna()
    else:
        series = prices[ticker].astype(float)
    features = build_feature_values(
        series.dropna(),
        config["data"].get("monitor_windows_weeks", {"short": 1, "medium": 4, "long": 12}),
        int(config["data"].get("zscore_window_weeks", 52)),
    )
    feature_series = features.get("_series", {}).get(rule.get("feature"))
    if feature_series is None or feature_series.dropna().empty:
        return {"recent_hit_rate_26w": None, "history_hit_rate": None, "drift_gap": None, "drift_status": "unavailable"}
    series_clean = feature_series.dropna()
    if str(rule.get("direction")) == "lower":
        hits = series_clean <= float(rule.get("threshold"))
    else:
        hits = series_clean >= float(rule.get("threshold"))
    history_rate = float(hits.mean()) if len(hits) else 0.0
    recent_hits = hits.tail(26)
    recent_rate = float(recent_hits.mean()) if len(recent_hits) else history_rate
    gap = recent_rate - history_rate
    status = "stable"
    if abs(gap) >= 0.2:
        status = "review"
    elif abs(gap) >= 0.1:
        status = "watch"
    return {
        "recent_hit_rate_26w": round(recent_rate, 4),
        "history_hit_rate": round(history_rate, 4),
        "drift_gap": round(gap, 4),
        "drift_status": status,
    }


def _build_drift_summary(drift_rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "stable_count": 0,
        "watch_count": 0,
        "review_count": 0,
        "unavailable_count": 0,
        "watch_targets": [],
        "review_targets": [],
    }
    for row in drift_rows:
        status = str(row.get("drift_status") or "unavailable")
        label = f"{row.get('ticker')}:{row.get('stage')}"
        if status == "review":
            summary["review_count"] += 1
            summary["review_targets"].append(label)
        elif status == "watch":
            summary["watch_count"] += 1
            summary["watch_targets"].append(label)
        elif status == "stable":
            summary["stable_count"] += 1
        else:
            summary["unavailable_count"] += 1
    return summary
