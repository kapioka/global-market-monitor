from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_buy_window_calibration(
    replay_diff: dict[str, Any] | None = None,
    candidate_comparison: dict[str, Any] | None = None,
    action_validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    replay_diff = replay_diff or {}
    candidate_comparison = candidate_comparison or {}
    action_validation = action_validation or {}
    rows = []
    baseline_counts = ((replay_diff.get("summary") or {}).get("active_action_counts") or {}) or _counts_from_validation(action_validation)
    rows.append(_candidate_row("active", baseline_counts, _metrics_for_label(replay_diff, "active"), baseline_counts))
    proposed_counts = ((replay_diff.get("summary") or {}).get("proposed_action_counts") or {})
    if proposed_counts:
        rows.append(_candidate_row("proposed_thresholds_review", proposed_counts, _metrics_for_label(replay_diff, "proposed"), baseline_counts))
    for candidate in candidate_comparison.get("candidates", []) or []:
        label = str(candidate.get("label", "candidate"))
        if label in {"active", "proposed"}:
            continue
        rows.append(_candidate_row(label, candidate.get("action_counts") or {}, candidate.get("metrics") or {}, baseline_counts))
    if not rows:
        rows.append(_candidate_row("active", baseline_counts, {}, baseline_counts))
    return {
        "status": "ok",
        "policy": "calibration_only_no_active_threshold_change",
        "candidates": rows,
        "summary": {
            "candidate_count": len(rows),
            "adopt_count": sum(1 for row in rows if row["decision"] == "adopt"),
            "hold_count": sum(1 for row in rows if row["decision"] == "hold"),
            "reject_count": sum(1 for row in rows if row["decision"] == "reject"),
        },
    }


def write_buy_window_calibration(payload: dict[str, Any], reports_dir: str | Path) -> tuple[Path, Path]:
    reports_path = Path(reports_dir)
    reports_path.mkdir(parents=True, exist_ok=True)
    json_path = reports_path / "buy_window_calibration.json"
    markdown_path = reports_path / "buy_window_calibration.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_buy_window_calibration_markdown(payload), encoding="utf-8")
    return json_path, markdown_path


def render_buy_window_calibration_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# buy_window calibration review",
        "",
        f"- status: {payload.get('status')}",
        f"- policy: {payload.get('policy')}",
        "",
        "| candidate | decision | buy_window | buy_candidate | 13w excess | 26w excess | worst max DD | false buy_window | missed good window | reason |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload.get("candidates", []):
        lines.append(
            "| {label} | {decision} | {buy_window} | {buy_candidate} | {ex13} | {ex26} | {dd} | {false_buy} | {missed} | {reason} |".format(
                label=row.get("label"),
                decision=row.get("decision"),
                buy_window=row.get("buy_window_count", 0),
                buy_candidate=row.get("buy_candidate_count", 0),
                ex13=_fmt(row.get("mean_excess_return_13w")),
                ex26=_fmt(row.get("mean_excess_return_26w")),
                dd=_fmt(row.get("worst_max_drawdown")),
                false_buy=_fmt_count(row.get("false_buy_window_count")),
                missed=_fmt_count(row.get("missed_good_window_count")),
                reason=row.get("reason", "-"),
            )
        )
    lines.append("")
    lines.append("active/proposed threshold JSON はこのレポートでは変更しません。")
    return "\n".join(lines) + "\n"


def run_buy_window_calibration(reports_dir: str | Path = "project/reports") -> dict[str, Any]:
    reports_path = Path(reports_dir)
    payload = build_buy_window_calibration(
        replay_diff=_load_json_or_empty(reports_path / "threshold_historical_replay_diff.json"),
        candidate_comparison=_load_json_or_empty(reports_path / "threshold_candidate_comparison.json"),
        action_validation=_load_json_or_empty(reports_path / "action_validation_summary.json"),
    )
    json_path, markdown_path = write_buy_window_calibration(payload, reports_path)
    return {"status": payload["status"], "json_path": str(json_path), "markdown_path": str(markdown_path)}


def _candidate_row(label: str, counts: dict[str, Any], metrics: dict[str, Any], baseline_counts: dict[str, Any]) -> dict[str, Any]:
    buy_window_count = int(counts.get("buy_window", 0) or 0)
    buy_candidate_count = int(counts.get("buy_candidate", 0) or 0)
    baseline_buy_window_count = int(baseline_counts.get("buy_window", 0) or 0)
    buy_window_metrics = metrics.get("buy_window", {}).get("horizons", {}) if isinstance(metrics.get("buy_window"), dict) else {}
    h13 = buy_window_metrics.get("13w", {})
    h26 = buy_window_metrics.get("26w", {})
    worst_dd = _worst_drawdown(metrics)
    decision = "hold"
    reasons = ["evidence_insufficient"]
    if label != "active" and buy_window_count == 0 and buy_candidate_count == 0:
        decision = "reject"
        reasons = ["no_buy_signal_added"]
    elif label != "active" and buy_window_count > baseline_buy_window_count:
        decision = "hold"
        reasons = ["buy_window_increased_requires_return_and_drawdown_review"]
    return {
        "label": label,
        "decision": decision,
        "decision_reasons": reasons,
        "reason": ", ".join(reasons),
        "buy_window_count": buy_window_count,
        "buy_candidate_count": buy_candidate_count,
        "mean_excess_return_13w": h13.get("mean_excess_return"),
        "mean_excess_return_26w": h26.get("mean_excess_return"),
        "worst_max_drawdown": worst_dd,
        "false_buy_window_count": _false_buy_window_count(metrics),
        "missed_good_window_count": None,
    }


def _counts_from_validation(payload: dict[str, Any]) -> dict[str, Any]:
    return {action: item.get("count", 0) for action, item in (payload.get("action_summary") or {}).items()}


def _metrics_for_label(replay_diff: dict[str, Any], label: str) -> dict[str, Any]:
    return (((replay_diff.get("summary") or {}).get("metrics") or {}).get(label) or {})


def _worst_drawdown(metrics: dict[str, Any]) -> float | None:
    values = []
    for action_payload in metrics.values():
        for horizon in (action_payload.get("horizons") or {}).values():
            value = horizon.get("worst_max_drawdown")
            if value is not None:
                values.append(float(value))
    return min(values) if values else None


def _false_buy_window_count(metrics: dict[str, Any]) -> int | None:
    buy_window = metrics.get("buy_window")
    if not isinstance(buy_window, dict):
        return None
    horizon = (buy_window.get("horizons") or {}).get("13w") or {}
    count = horizon.get("count")
    negative_rate = horizon.get("negative_rate")
    if count is None or negative_rate is None:
        return None
    return round(int(count) * float(negative_rate))


def _load_json_or_empty(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _fmt(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_count(value: Any) -> str:
    return "-" if value is None else str(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build buy_window calibration review without changing active thresholds.")
    parser.add_argument("--reports-dir", default="project/reports")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run_buy_window_calibration(args.reports_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
