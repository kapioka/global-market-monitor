from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project.config_loader import load_config
from project.risk_line_calibration_report import build_risk_line_backtest_from_config
from project.risk_line_model_selection import build_risk_line_model_selection


REPORT_JSON = "risk_line_model_selection.json"
REPORT_MD = "risk_line_model_selection.md"


def write_risk_line_model_selection_report(config_path: str | Path, sample_only: bool = False) -> tuple[Path, Path]:
    config = load_config(config_path)
    reports_dir = Path(config["paths"]["reports_dir"])
    reports_dir.mkdir(parents=True, exist_ok=True)
    selection = build_risk_line_model_selection_from_config(config, sample_only=sample_only)
    json_path = reports_dir / REPORT_JSON
    md_path = reports_dir / REPORT_MD
    json_path.write_text(json.dumps(selection, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_risk_line_model_selection_markdown(selection), encoding="utf-8")
    return json_path, md_path


def build_risk_line_model_selection_from_config(config: dict[str, Any], sample_only: bool = False) -> dict[str, Any]:
    backtest = build_risk_line_backtest_from_config(config, sample_only=sample_only)
    selection = build_risk_line_model_selection(backtest)
    selection["data_source"] = backtest.get("data_source")
    selection["warnings"] = backtest.get("warnings", [])
    return selection


def render_risk_line_model_selection_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Risk Line Model Selection",
        "",
        f"- データソース: {report.get('data_source', '-')}",
        f"- 対象指標数: {report.get('indicator_count', 0)}",
        f"- 対象ターゲット: {', '.join(report.get('targets', [])) or '-'}",
        f"- adopt: {report.get('decision_counts', {}).get('adopt', 0)}",
        f"- review: {report.get('decision_counts', {}).get('review', 0)}",
        f"- reject: {report.get('decision_counts', {}).get('reject', 0)}",
        f"- 警告: {', '.join(report.get('warnings', [])) if report.get('warnings') else 'なし'}",
    ]
    for ticker, payload in report.get("indicators", {}).items():
        lines.extend([
            "",
            f"## {ticker}",
            f"- ファミリー: {payload.get('family', '-')}",
            f"- adverse_direction: {payload.get('adverse_direction', '-')}",
        ])
        for target, summary in payload.get("targets", {}).items():
            model = summary.get("selected_model") or {}
            metrics = summary.get("metrics") or {}
            lines.extend([
                "",
                f"### {target}",
                f"- decision: {summary.get('decision', '-')}",
                f"- reason: {summary.get('reason', '-')}",
                f"- feature: {model.get('feature', '-')}",
                f"- threshold: {model.get('threshold', '-')}",
                f"- quantile: {model.get('quantile', '-')}",
                f"- full_f1: {metrics.get('full_f1', '-')}",
                f"- split_f1: {metrics.get('split_f1', '-')}",
                f"- walk_forward_f1: {metrics.get('walk_forward_f1', '-')}",
                f"- precision: {metrics.get('precision', '-')}",
                f"- recall: {metrics.get('recall', '-')}",
            ])
    return "\n".join(lines) + "\n"
