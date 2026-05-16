from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project.config_loader import load_config
from project.data_fetcher import fetch_market_data
from project.risk_line_backtest import build_risk_line_backtest_report
from project.risk_line_label_builder import RiskLabelConfig
from project.stress_monitor import default_risk_indicator_map


REPORT_JSON = "risk_line_model_backtest.json"
REPORT_MD = "risk_line_model_backtest.md"


def write_risk_line_backtest_report(config_path: str | Path, sample_only: bool = False) -> tuple[Path, Path]:
    config = load_config(config_path)
    reports_dir = Path(config["paths"]["reports_dir"])
    reports_dir.mkdir(parents=True, exist_ok=True)
    report = build_risk_line_backtest_from_config(config, sample_only=sample_only)
    json_path = reports_dir / REPORT_JSON
    md_path = reports_dir / REPORT_MD
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_risk_line_backtest_markdown(report), encoding="utf-8")
    return json_path, md_path


def build_risk_line_backtest_from_config(config: dict[str, Any], sample_only: bool = False) -> dict[str, Any]:
    tickers = _collect_required_tickers(config)
    fetch = fetch_market_data(
        tickers=tickers,
        period_years=int(config["data"]["period_years"]),
        interval=str(config["data"]["interval"]),
        logger=_NullLogger(),
        use_sample_on_failure=True,
        cache_dir=config["paths"].get("cache_dir"),
        force_sample=sample_only,
    )
    prices = fetch.prices.sort_index()
    report = build_risk_line_backtest_report(prices, label_config=RiskLabelConfig())
    report["data_source"] = fetch.source
    report["warnings"] = list(fetch.warnings)
    report["acquisition_log"] = fetch.acquisition_log
    report["rows"] = len(prices)
    report["columns"] = list(prices.columns)
    return report


def render_risk_line_backtest_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Risk Line Model Backtest",
        "",
        f"- データソース: {report.get('data_source', '-')}",
        f"- 対象行数: {report.get('rows', 0)}",
        f"- 対象指標数: {report.get('indicator_count', 0)}",
        f"- 対象ターゲット: {', '.join(report.get('targets', [])) or '-'}",
    ]
    warnings = report.get("warnings", [])
    lines.append(f"- 警告: {', '.join(warnings) if warnings else 'なし'}")

    for ticker, payload in report.get("indicators", {}).items():
        lines.extend([
            "",
            f"## {ticker}",
            f"- ファミリー: {payload.get('family', '-')}",
            f"- adverse_direction: {payload.get('adverse_direction', '-')}",
            f"- 行数: {payload.get('rows', 0)}",
        ])
        for target, summary in payload.get("targets", {}).items():
            best = summary.get("best")
            split_summary = summary.get("time_splits", {})
            walk_forward = summary.get("walk_forward", {})
            lines.extend([
                "",
                f"### {target}",
                f"- 候補数: {summary.get('candidate_count', 0)}",
            ])
            if not best:
                lines.append("- best: なし")
                continue
            lines.extend([
                f"- best feature: {best.get('feature', '-')}",
                f"- threshold: {best.get('threshold', '-')}",
                f"- quantile: {best.get('quantile', '-')}",
                f"- precision: {best.get('precision', '-')}",
                f"- recall: {best.get('recall', '-')}",
                f"- f1: {best.get('f1', '-')}",
                f"- false_positive_rate: {best.get('false_positive_rate', '-')}",
                f"- average_lead_weeks: {best.get('average_lead_weeks', '-')}",
                f"- split_count: {split_summary.get('split_count', 0)} / avg_test_f1: {split_summary.get('average_test_f1', '-')}",
                f"- walk_forward_windows: {walk_forward.get('window_count', 0)} / avg_test_f1: {walk_forward.get('average_test_f1', '-')}",
            ])
    return "\n".join(lines) + "\n"


def _collect_required_tickers(config: dict[str, Any]) -> list[str]:
    risk_map = default_risk_indicator_map(config)
    ordered_aliases = ["SPY", "HYG", "LQD", "VIX", "MOVE", "WTI", "Brent", "DXY", "US10Y"]
    deduped: list[str] = []
    for alias in ordered_aliases:
        ticker = risk_map.get(alias)
        if ticker and ticker not in deduped:
            deduped.append(ticker)
    return deduped


class _NullLogger:
    def debug(self, *args: Any, **kwargs: Any) -> None:
        return None

    def info(self, *args: Any, **kwargs: Any) -> None:
        return None

    def warning(self, *args: Any, **kwargs: Any) -> None:
        return None
