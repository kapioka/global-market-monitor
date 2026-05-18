from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any


def write_action_validation_report(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "action_validation.json"
    markdown_path = reports_path / "action_validation.md"
    summary_json_path = reports_path / "action_validation_summary.json"
    summary_csv_path = reports_path / "action_validation_summary.csv"
    summary_markdown_path = reports_path / "action_validation_summary.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_action_validation_markdown(payload), encoding="utf-8")
    summary_json_path.write_text(json.dumps(_summary_payload(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    summary_csv_path.write_text(render_action_validation_csv(payload), encoding="utf-8")
    summary_markdown_path.write_text(render_action_validation_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_action_validation_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# action validation",
        "",
        f"- status: {payload.get('status', '-')}",
        f"- benchmark_source: {payload.get('benchmark_source', '-')}",
    ]
    if payload.get("reason"):
        lines.append(f"- reason: {payload.get('reason')}")
    lines.extend(["", "## action summary"])
    summary = payload.get("action_summary", {})
    if not summary:
        lines.append("- insufficient data")
    for action, item in summary.items():
        lines.append(f"- {action}: count={item.get('count', 0)} / reliability_capped={item.get('reliability_capped_count', 0)}")
        horizons = item.get("horizons", {})
        for horizon, horizon_item in horizons.items():
            lines.append(
                f"  - {horizon}: count={horizon_item.get('count', 0)} / mean={_format_return(horizon_item.get('mean_return'))} / median={_format_return(horizon_item.get('median_return'))} / win_rate={_format_return(horizon_item.get('win_rate'))} / excess_mean={_format_return(horizon_item.get('mean_excess_return'))} / excess_win_rate={_format_return(horizon_item.get('excess_win_rate'))} / max_dd={_format_return(horizon_item.get('worst_max_drawdown'))}"
            )
    diagnostics = payload.get("diagnostics", {})
    if diagnostics:
        lines.extend(
            [
                "",
                "## diagnostics",
                f"- buy_window_negative_rate_13w: {_format_return(diagnostics.get('buy_window_negative_rate_13w'))}",
                f"- wait_missed_rally_rate_13w: {_format_return(diagnostics.get('wait_missed_rally_rate_13w'))}",
                f"- watch_to_buy_window_promotion_rate: {_format_return(diagnostics.get('watch_to_buy_window_promotion_rate'))}",
            ]
        )
    lines.extend(["", "## cases"])
    for case in payload.get("cases", [])[:20]:
        returns = case.get("forward_returns", {})
        drawdowns = case.get("max_drawdowns", {})
        lines.append(
            f"- {case.get('date', '-')}: {case.get('action', '-')} / 4w={_format_return(returns.get('4w'))} / 13w={_format_return(returns.get('13w'))} / 26w={_format_return(returns.get('26w'))} / 52w={_format_return(returns.get('52w'))} / 13w_dd={_format_return(drawdowns.get('13w'))}"
        )
    if not payload.get("cases"):
        lines.append("- no aligned cases")
    return "\n".join(lines) + "\n"


def render_action_validation_csv(payload: dict[str, Any]) -> str:
    output = io.StringIO()
    fieldnames = [
        "action",
        "horizon",
        "count",
        "mean_return",
        "median_return",
        "win_rate",
        "negative_rate",
        "max_loss",
        "max_gain",
        "mean_max_drawdown",
        "worst_max_drawdown",
        "mean_excess_return",
        "median_excess_return",
        "worst_excess_return",
        "excess_win_rate",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for action, item in payload.get("action_summary", {}).items():
        for horizon, horizon_item in item.get("horizons", {}).items():
            row = {"action": action, "horizon": horizon}
            row.update({field: horizon_item.get(field) for field in fieldnames if field not in {"action", "horizon"}})
            writer.writerow(row)
    return output.getvalue()


def _summary_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": payload.get("status"),
        "reason": payload.get("reason"),
        "benchmark_source": payload.get("benchmark_source"),
        "action_summary": payload.get("action_summary", {}),
        "diagnostics": payload.get("diagnostics", {}),
    }


def _format_return(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2%}"
    except (TypeError, ValueError):
        return str(value)
