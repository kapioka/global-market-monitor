from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project.config_loader import load_config
from project.risk_line_calibration_report import build_risk_line_backtest_from_config
from project.risk_line_reality_check import build_reality_checked_thresholds
from project.risk_line_label_builder import RiskLabelConfig
from project.data_fetcher import fetch_market_data
from project.stress_monitor import default_risk_indicator_map


REPORT_JSON = "risk_line_reality_checked_thresholds.json"
REPORT_MD = "risk_line_reality_checked_thresholds.md"


def write_risk_line_reality_checked_report(config_path: str | Path, sample_only: bool = False) -> tuple[Path, Path]:
    config = load_config(config_path)
    reports_dir = Path(config["paths"]["reports_dir"])
    reports_dir.mkdir(parents=True, exist_ok=True)
    report = build_risk_line_reality_checked_report_from_config(config, sample_only=sample_only)
    json_path = reports_dir / REPORT_JSON
    md_path = reports_dir / REPORT_MD
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_risk_line_reality_checked_markdown(report), encoding="utf-8")
    return json_path, md_path


def build_risk_line_reality_checked_report_from_config(config: dict[str, Any], sample_only: bool = False) -> dict[str, Any]:
    backtest = build_risk_line_backtest_from_config(config, sample_only=sample_only)
    prices = _fetch_prices(config, sample_only=sample_only)
    report = build_reality_checked_thresholds(prices, backtest, label_config=RiskLabelConfig())
    report["data_source"] = backtest.get("data_source")
    report["warnings"] = backtest.get("warnings", [])
    return report


def render_risk_line_reality_checked_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Risk Line Reality-Checked Thresholds",
        "",
        f"- データソース: {report.get('data_source', '-')}",
        f"- 対象指標数: {report.get('indicator_count', 0)}",
        f"- adopt: {report.get('decision_counts', {}).get('adopt', 0)}",
        f"- fallback_review: {report.get('decision_counts', {}).get('fallback_review', 0)}",
        f"- fallback_guarded: {report.get('decision_counts', {}).get('fallback_guarded', 0)}",
        f"- 警告: {', '.join(report.get('warnings', [])) if report.get('warnings') else 'なし'}",
    ]
    for ticker, payload in report.get("indicators", {}).items():
        lines.extend(["", f"## {ticker}", f"- ファミリー: {payload.get('family', '-')}", f"- adverse_direction: {payload.get('adverse_direction', '-')}" ])
        for target, summary in payload.get("targets", {}).items():
            model = summary.get("selected_model") or {}
            metrics = summary.get("metrics") or {}
            actual = summary.get("actual_value_check") or {}
            lines.extend([
                "",
                f"### {target}",
                f"- decision: {summary.get('decision', '-')}",
                f"- selection_mode: {summary.get('selection_mode', '-')}",
                f"- coverage_forced: {summary.get('coverage_forced', False)}",
                f"- reason: {summary.get('reason', '-')}",
                f"- feature: {model.get('feature', '-')}",
                f"- threshold: {model.get('threshold', '-')}",
                f"- quantile: {model.get('quantile', '-')}",
                f"- full_f1: {metrics.get('full_f1', '-')}",
                f"- precision: {metrics.get('precision', '-')}",
                f"- false_positive_rate: {metrics.get('false_positive_rate', '-')}",
                f"- actual_check_status: {actual.get('status', '-')}",
                f"- actual_check_reasons: {', '.join(actual.get('reasons', [])) if actual.get('reasons') else 'なし'}",
                f"- frequency_profile: predicted={summary.get('frequency_profile', {}).get('predicted_count', '-')} / coverage={summary.get('frequency_profile', {}).get('coverage', '-')} / true_positive={summary.get('frequency_profile', {}).get('true_positive_count', '-')}",
            ])
            for anchor in actual.get("anchors", []):
                lines.append(
                    f"- anchor {anchor.get('metric')}: median={anchor.get('true_positive_median')} p25={anchor.get('true_positive_p25')} p75={anchor.get('true_positive_p75')} hist_pct={anchor.get('historical_percentile')} severity={anchor.get('severity_score')}"
                )
    return "\n".join(lines) + "\n"


def _fetch_prices(config: dict[str, Any], sample_only: bool = False):
    risk_map = default_risk_indicator_map(config)
    ordered_aliases = ["SPY", "HYG", "LQD", "VIX", "MOVE", "WTI", "Brent", "DXY", "US10Y"]
    tickers: list[str] = []
    for alias in ordered_aliases:
        ticker = risk_map.get(alias)
        if ticker and ticker not in tickers:
            tickers.append(ticker)
    fetch = fetch_market_data(
        tickers=tickers,
        period_years=int(config["data"]["period_years"]),
        interval=str(config["data"]["interval"]),
        logger=_NullLogger(),
        use_sample_on_failure=True,
        cache_dir=config["paths"].get("cache_dir"),
        force_sample=sample_only,
    )
    return fetch.prices.sort_index()


class _NullLogger:
    def debug(self, *args: Any, **kwargs: Any) -> None:
        return None

    def info(self, *args: Any, **kwargs: Any) -> None:
        return None

    def warning(self, *args: Any, **kwargs: Any) -> None:
        return None
