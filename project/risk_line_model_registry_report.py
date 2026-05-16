from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from project.config_loader import load_config
from project.risk_line_model_registry import build_risk_line_model_registry
from project.risk_line_model_selection_report import build_risk_line_model_selection_from_config


REPORT_JSON = "risk_line_model_registry.json"
REPORT_MD = "risk_line_model_registry.md"


def write_risk_line_model_registry_report(config_path: str | Path, sample_only: bool = False) -> tuple[Path, Path]:
    config = load_config(config_path)
    reports_dir = Path(config["paths"]["reports_dir"])
    reports_dir.mkdir(parents=True, exist_ok=True)
    registry = build_risk_line_model_registry_from_config(config, sample_only=sample_only)
    json_path = reports_dir / REPORT_JSON
    md_path = reports_dir / REPORT_MD
    json_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_risk_line_model_registry_markdown(registry), encoding="utf-8")
    return json_path, md_path


def build_risk_line_model_registry_from_config(config: dict[str, Any], sample_only: bool = False) -> dict[str, Any]:
    selection = build_risk_line_model_selection_from_config(config, sample_only=sample_only)
    return build_risk_line_model_registry(selection)


def render_risk_line_model_registry_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Risk Line Model Registry",
        "",
        f"- データソース: {report.get('data_source', '-')}",
        f"- 対象指標数: {report.get('indicator_count', 0)}",
        f"- live 指標数: {report.get('live_indicator_count', 0)}",
        f"- decision_counts: adopt={report.get('decision_counts', {}).get('adopt', 0)}, review={report.get('decision_counts', {}).get('review', 0)}, reject={report.get('decision_counts', {}).get('reject', 0)}",
        f"- stage_coverage: warning={report.get('stage_coverage', {}).get('warning_target', 0)}, danger={report.get('stage_coverage', {}).get('danger_target', 0)}, extreme={report.get('stage_coverage', {}).get('extreme_target', 0)}",
        f"- 警告: {', '.join(report.get('warnings', [])) if report.get('warnings') else 'なし'}",
    ]
    lines.extend(_render_bucket("Live Models", report.get("live_models", {})))
    lines.extend(_render_bucket("Review Queue", report.get("review_queue", {})))
    lines.extend(_render_bucket("Rejected Targets", report.get("rejected_targets", {})))
    return "\n".join(lines) + "\n"


def _render_bucket(title: str, bucket: dict[str, Any]) -> list[str]:
    lines = ["", f"## {title}"]
    if not bucket:
        lines.append("- なし")
        return lines
    for ticker, payload in bucket.items():
        lines.extend([
            "",
            f"### {ticker}",
            f"- ファミリー: {payload.get('family', '-')}",
            f"- adverse_direction: {payload.get('adverse_direction', '-')}",
        ])
        for target, summary in payload.get("targets", {}).items():
            model = summary.get("selected_model") or {}
            metrics = summary.get("metrics") or {}
            lines.extend([
                f"- {target}: {summary.get('decision', '-')} / {summary.get('reason', '-')}",
                f"  feature={model.get('feature', '-')} threshold={model.get('threshold', '-')} split_f1={metrics.get('split_f1', '-')} walk_f1={metrics.get('walk_forward_f1', '-')}",
            ])
    return lines
