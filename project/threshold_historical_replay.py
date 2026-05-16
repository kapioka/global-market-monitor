# mypy: ignore-errors

from __future__ import annotations

import argparse
import json
from collections import Counter
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from project.action_validation import build_action_validation
from project.config_loader import load_config
from project.pipeline import resample_weekly_closes
from project.risk_line_threshold_store import ACTIVE_THRESHOLDS_PATH, PROPOSED_THRESHOLDS_PATH
from project.risk_lines import evaluate_risk_lines
from project.spot_signal import evaluate_spot_signal
from project.stress_monitor import build_stress_monitor, default_risk_indicator_map

PROPOSED_CANDIDATES = (
    "stage_limited",
    "multi_confirm_extreme",
    "ignore_fallback_extreme",
    "candidate_v2_combined",
)


def run_threshold_historical_replay(
    config_path: str | Path = "project/config.yaml",
    active_thresholds_path: str | Path = ACTIVE_THRESHOLDS_PATH,
    proposed_thresholds_path: str | Path = PROPOSED_THRESHOLDS_PATH,
    prices_csv: str | Path | None = None,
    reports_dir: str | Path | None = None,
) -> dict[str, Any]:
    config = load_config(config_path)
    reports_path = Path(reports_dir or config["paths"]["reports_dir"])
    price_points_path = reports_path / "validation_prices.json"
    if not price_points_path.exists():
        return {
            "status": "missing_price_points",
            "message": "validation price file is missing. Run python -m project.validation_price_export first.",
            "price_points_json": str(price_points_path),
        }
    history_dir = reports_path / "history"
    if not history_dir.exists() or not list(history_dir.glob("report_*.json")):
        return {
            "status": "missing_history",
            "message": "historical report JSON files are missing. Run python project/main.py --sample-only or a live scheduled run first.",
            "history_dir": str(history_dir),
        }
    market_snapshot_path = Path(prices_csv) if prices_csv else _latest_market_snapshot_or_none(Path(config["paths"]["cache_dir"]))
    if market_snapshot_path is None:
        return {
            "status": "missing_market_snapshot",
            "message": "market snapshot CSV is missing. Run python project/main.py --sample-only or a live data fetch first.",
            "market_snapshot_dir": str(Path(config["paths"]["cache_dir"]) / "market_snapshots"),
        }
    history_entries = _load_history_entries(history_dir)
    if not history_entries:
        return {
            "status": "missing_history",
            "message": "historical report JSON files could not be loaded.",
            "history_dir": str(history_dir),
        }
    price_points = _load_price_points(price_points_path)
    prices = _load_prices(market_snapshot_path)

    active_payload = _load_json(active_thresholds_path)
    proposed_payload = _load_json(proposed_thresholds_path)

    active = _run_set("active", config, prices, history_entries, price_points, active_payload)
    proposed = _run_set("proposed", config, prices, history_entries, price_points, proposed_payload)
    candidates = _derive_candidate_sets(proposed, proposed_payload)
    diff = _build_diff(active, proposed)
    candidate_comparison = _build_candidate_comparison(active, proposed, candidates)
    changed_cases = _build_changed_case_diagnostics(active, proposed)

    reports_path.mkdir(parents=True, exist_ok=True)
    active_path = reports_path / "threshold_historical_replay_active.json"
    proposed_path = reports_path / "threshold_historical_replay_proposed.json"
    diff_path = reports_path / "threshold_historical_replay_diff.json"
    candidate_path = reports_path / "threshold_candidate_comparison.json"
    changed_cases_path = reports_path / "threshold_changed_cases.json"
    changed_cases_md_path = reports_path / "threshold_changed_cases.md"
    active_path.write_text(json.dumps(active, ensure_ascii=False, indent=2), encoding="utf-8")
    proposed_path.write_text(json.dumps(proposed, ensure_ascii=False, indent=2), encoding="utf-8")
    diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    candidate_path.write_text(json.dumps(candidate_comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    changed_cases_path.write_text(json.dumps(changed_cases, ensure_ascii=False, indent=2), encoding="utf-8")
    changed_cases_md_path.write_text(_render_changed_cases_markdown(changed_cases), encoding="utf-8")
    return {
        "status": "ok",
        "active_path": str(active_path),
        "proposed_path": str(proposed_path),
        "diff_path": str(diff_path),
        "candidate_path": str(candidate_path),
        "changed_cases_path": str(changed_cases_path),
        "decision": diff["decision"],
        "total_history_count": diff["summary"]["total_history_count"],
        "final_action_changed_count": diff["summary"]["final_action_changed_count"],
        "risk_stage_changed_count": diff["summary"]["risk_stage_changed_count"],
    }


def _run_set(
    label: str,
    config: dict[str, Any],
    prices: pd.DataFrame,
    history_entries: list[dict[str, Any]],
    price_points: list[dict[str, Any]],
    threshold_payload: dict[str, Any],
    candidate: str | None = None,
) -> dict[str, Any]:
    cases = []
    replay_entries = []
    for entry in history_entries:
        generated_at = datetime.fromisoformat(str(entry["generated_at"]))
        report = _replay_report(config, prices, entry, generated_at, threshold_payload, candidate=candidate)
        action = _final_action(report)
        risk_lines = report.get("risk_lines", {})
        case = {
            "date": generated_at.date().isoformat(),
            "source_history": entry.get("_source_file"),
            "final_action": action,
            "original_action": _original_action(report),
            "risk_stage_key": risk_lines.get("stage_key", "normal"),
            "risk_stage_label": risk_lines.get("stage_label", "-"),
            "risk_decision_level": risk_lines.get("decision_level", "none"),
            "warning_count": risk_lines.get("warning_count", 0),
            "danger_count": risk_lines.get("danger_count", 0),
            "extreme_count": risk_lines.get("extreme_count", 0),
            "composite_risk_score": risk_lines.get("composite_risk_score"),
            "danger_lines": risk_lines.get("danger_lines", []),
            "extreme_lines": risk_lines.get("extreme_lines", []),
            "indicators": _compact_indicators(risk_lines.get("indicators", [])),
            "candidate_adjustments": risk_lines.get("candidate_adjustments", []),
            "policy_reasons": ((report.get("spot_signal") or {}).get("action_decision") or {}).get("policy_reasons", []),
        }
        cases.append(case)
        replay_entries.append(_history_entry_for_validation(report, generated_at))

    validation = build_action_validation(replay_entries, price_points)
    return {
        "label": label,
        "threshold_set": threshold_payload.get("threshold_set", {}),
        "total_history_count": len(history_entries),
        "replayed_count": len(cases),
        "action_counts": dict(Counter(case["final_action"] for case in cases)),
        "risk_stage_counts": dict(Counter(case["risk_stage_key"] for case in cases)),
        "validation": validation,
        "cases": cases,
    }


def _replay_report(
    config: dict[str, Any],
    prices: pd.DataFrame,
    history_entry: dict[str, Any],
    generated_at: datetime,
    threshold_payload: dict[str, Any],
    candidate: str | None = None,
) -> dict[str, Any]:
    cutoff = generated_at.replace(hour=23, minute=59, second=59, microsecond=999999)
    weekly_prices = resample_weekly_closes(prices.loc[prices.index <= cutoff])
    risk_monitor = build_stress_monitor(
        weekly_prices,
        default_risk_indicator_map(config),
        config["data"].get("monitor_windows_weeks", {"short": 1, "medium": 4, "long": 12}),
        int(config["data"].get("zscore_window_weeks", 52)),
        threshold_definitions=threshold_payload.get("indicators", {}),
    )
    regime = history_entry.get("regime", {})
    cycle = history_entry.get("cycle", {})
    credit_monitor = history_entry.get("credit_monitor", [])
    inflation_monitor = history_entry.get("inflation_monitor", [])
    risk_lines = evaluate_risk_lines(regime, cycle, credit_monitor, inflation_monitor, risk_monitor)
    risk_lines = _apply_candidate_policy(risk_lines, threshold_payload, candidate)
    spot_signal = evaluate_spot_signal(
        history_entry.get("score", {"total_score": 0.5}),
        regime,
        cycle,
        credit_monitor,
        inflation_monitor,
        config["thresholds"],
        risk_lines=risk_lines,
        sector_rotation=history_entry.get("sector_rotation", {}),
        sector_config=config.get("sector_vector_analysis", {}),
        recovery_evidence=(history_entry.get("spot_signal") or {}).get("recovery_evidence"),
        japan_risk=history_entry.get("japan_risk", {}),
        japan_risk_config=config.get("japan_risk", {}),
        reliability_policy=history_entry.get("data_reliability", {}),
    )
    return {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "data_reliability": history_entry.get("data_reliability", {}),
        "regime": regime,
        "cycle": cycle,
        "score": history_entry.get("score", {}),
        "risk_lines": risk_lines,
        "spot_signal": spot_signal,
    }


def _apply_candidate_policy(risk_lines: dict[str, Any], threshold_payload: dict[str, Any], candidate: str | None) -> dict[str, Any]:
    if not candidate:
        return risk_lines
    adjusted = deepcopy(risk_lines)
    adjustments: list[str] = []
    if candidate == "stage_limited":
        if adjusted.get("stage_key") == "extreme_danger_line_reached" and not _clear_extreme_exception(adjusted):
            _set_stage(adjusted, "danger_line_reached")
            adjustments.append("limited_extreme_to_danger_without_clear_exception")
    elif candidate == "multi_confirm_extreme":
        if adjusted.get("stage_key") == "extreme_danger_line_reached" and not _multi_confirmed_extreme(adjusted):
            _set_stage(adjusted, "danger_line_reached")
            adjustments.append("downgraded_extreme_without_multi_confirmation")
    elif candidate == "ignore_fallback_extreme":
        fallback_extreme_tickers = _fallback_extreme_tickers(threshold_payload)
        extreme_indicators = [
            row
            for row in adjusted.get("indicators", [])
            if row.get("line_level") == "extreme" and row.get("ticker") in fallback_extreme_tickers
        ]
        if adjusted.get("stage_key") == "extreme_danger_line_reached" and extreme_indicators:
            adjusted["extreme_count"] = max(0, int(adjusted.get("extreme_count", 0) or 0) - len(extreme_indicators))
            adjusted["extreme_lines"] = [
                line
                for line in adjusted.get("extreme_lines", [])
                if all(str(row.get("ticker_name_ja", row.get("ticker"))) not in str(line) for row in extreme_indicators)
            ]
            if int(adjusted.get("extreme_count", 0) or 0) < 2 and float(adjusted.get("composite_risk_score", 0.0) or 0.0) < 78:
                _set_stage(adjusted, "danger_line_reached")
            adjustments.append("ignored_fallback_review_extreme_for_stage")
    else:
        raise ValueError(f"unknown threshold replay candidate: {candidate}")
    adjusted["candidate"] = candidate
    adjusted["candidate_adjustments"] = adjustments
    return adjusted


def _set_stage(risk_lines: dict[str, Any], stage_key: str) -> None:
    labels = {
        "normal": "通常",
        "caution": "警戒",
        "credit_spillover_initial": "信用波及初期",
        "danger_line_reached": "危険ライン到達",
        "extreme_danger_line_reached": "非常に危険ライン到達",
    }
    penalties = {
        "normal": 0.0,
        "caution": 0.02,
        "credit_spillover_initial": 0.04,
        "danger_line_reached": 0.08,
        "extreme_danger_line_reached": 0.14,
    }
    risk_lines["stage_key"] = stage_key
    risk_lines["stage_label"] = labels.get(stage_key, stage_key)
    risk_lines["penalty_hint"] = penalties.get(stage_key, 0.0)
    if stage_key == "danger_line_reached":
        risk_lines["decision_level"] = "block"
        risk_lines["decision_summary"] = "候補ポリシーにより extreme から danger に抑制しましたが、市場ストレスは強い状態です。"


def _clear_extreme_exception(risk_lines: dict[str, Any]) -> bool:
    if int(risk_lines.get("extreme_count", 0) or 0) >= 2:
        return True
    if float(risk_lines.get("composite_risk_score", 0.0) or 0.0) >= 85:
        return True
    flags = set(risk_lines.get("decision_flags", []))
    return bool({"credit_stress_severe", "vix_danger", "move_danger", "credit_ratio_danger"}.issubset(flags))


def _multi_confirmed_extreme(risk_lines: dict[str, Any]) -> bool:
    if int(risk_lines.get("extreme_count", 0) or 0) >= 2:
        return True
    if int(risk_lines.get("danger_count", 0) or 0) >= 4 and float(risk_lines.get("composite_risk_score", 0.0) or 0.0) >= 70:
        return True
    flags = set(risk_lines.get("decision_flags", []))
    return bool(
        flags.intersection({"vix_danger", "move_danger", "credit_ratio_danger"}) and int(risk_lines.get("warning_count", 0) or 0) >= 3
    )


def _fallback_extreme_tickers(threshold_payload: dict[str, Any]) -> set[str]:
    tickers = set()
    for ticker, payload in (threshold_payload.get("indicators") or {}).items():
        rule = ((payload or {}).get("thresholds") or {}).get("extreme") or {}
        if rule.get("decision") == "fallback_review" or rule.get("selection_mode") == "fallback_review":
            tickers.add(str(ticker))
    return tickers


def _build_diff(active: dict[str, Any], proposed: dict[str, Any]) -> dict[str, Any]:
    active_by_date = {case["date"]: case for case in active["cases"]}
    proposed_by_date = {case["date"]: case for case in proposed["cases"]}
    dates = sorted(set(active_by_date) & set(proposed_by_date))
    action_changes = []
    risk_stage_changes = []
    prevented_bad_buy_window = []
    missed_good_buy_window = []
    increased_wait = []

    active_case_returns = _validation_cases_by_date(active.get("validation", {}))
    proposed_case_returns = _validation_cases_by_date(proposed.get("validation", {}))

    for date_value in dates:
        active_case = active_by_date[date_value]
        proposed_case = proposed_by_date[date_value]
        if active_case["final_action"] != proposed_case["final_action"]:
            row = {
                "date": date_value,
                "active_action": active_case["final_action"],
                "proposed_action": proposed_case["final_action"],
                "active_stage": active_case["risk_stage_key"],
                "proposed_stage": proposed_case["risk_stage_key"],
                "active_13w_return": (active_case_returns.get(date_value) or {}).get("forward_returns", {}).get("13w"),
                "proposed_13w_return": (proposed_case_returns.get(date_value) or {}).get("forward_returns", {}).get("13w"),
            }
            action_changes.append(row)
            active_13w = row["active_13w_return"]
            if (
                active_case["final_action"] == "buy_window"
                and proposed_case["final_action"] != "buy_window"
                and active_13w is not None
                and active_13w < 0
            ):
                prevented_bad_buy_window.append(row)
            if (
                active_case["final_action"] == "buy_window"
                and proposed_case["final_action"] != "buy_window"
                and active_13w is not None
                and active_13w > 0.05
            ):
                missed_good_buy_window.append(row)
            if active_case["final_action"] != "wait" and proposed_case["final_action"] == "wait":
                increased_wait.append(row)
        if active_case["risk_stage_key"] != proposed_case["risk_stage_key"]:
            risk_stage_changes.append(
                {
                    "date": date_value,
                    "active_stage": active_case["risk_stage_key"],
                    "proposed_stage": proposed_case["risk_stage_key"],
                    "active_action": active_case["final_action"],
                    "proposed_action": proposed_case["final_action"],
                }
            )

    summary = {
        "total_history_count": len(dates),
        "active_action_counts": active["action_counts"],
        "proposed_action_counts": proposed["action_counts"],
        "active_risk_stage_counts": active["risk_stage_counts"],
        "proposed_risk_stage_counts": proposed["risk_stage_counts"],
        "final_action_changed_count": len(action_changes),
        "risk_stage_changed_count": len(risk_stage_changes),
        "cases_where_proposed_prevented_bad_buy_window": len(prevented_bad_buy_window),
        "cases_where_proposed_missed_good_buy_window": len(missed_good_buy_window),
        "cases_where_proposed_increased_wait": len(increased_wait),
        "metrics": {
            "active": _metrics_from_validation(active.get("validation", {})),
            "proposed": _metrics_from_validation(proposed.get("validation", {})),
        },
    }
    decision = _decision(summary)
    return {
        "status": "ok",
        "decision": decision,
        "summary": summary,
        "action_changes": action_changes,
        "risk_stage_changes": risk_stage_changes,
        "prevented_bad_buy_window_cases": prevented_bad_buy_window,
        "missed_good_buy_window_cases": missed_good_buy_window,
        "increased_wait_cases": increased_wait,
    }


def _build_candidate_comparison(active: dict[str, Any], proposed: dict[str, Any], candidates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    rows = [_candidate_summary_row(active, active), _candidate_summary_row(proposed, active)]
    rows.extend(_candidate_summary_row(payload, active) for payload in candidates.values())
    return {"status": "ok", "baseline": "active", "candidates": rows}


def _derive_candidate_sets(proposed: dict[str, Any], threshold_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {candidate: _derive_candidate_set(proposed, threshold_payload, candidate) for candidate in PROPOSED_CANDIDATES}


def _derive_candidate_set(proposed: dict[str, Any], threshold_payload: dict[str, Any], candidate: str) -> dict[str, Any]:
    cases = []
    for case in proposed.get("cases", []):
        candidate_case = deepcopy(case)
        candidate_case["candidate_adjustments"] = []
        _apply_candidate_to_case(candidate_case, threshold_payload, candidate)
        cases.append(candidate_case)
    return {
        "label": candidate,
        "threshold_set": proposed.get("threshold_set", {}),
        "total_history_count": proposed.get("total_history_count", 0),
        "replayed_count": len(cases),
        "action_counts": dict(Counter(case["final_action"] for case in cases)),
        "risk_stage_counts": dict(Counter(case["risk_stage_key"] for case in cases)),
        "validation": proposed.get("validation", {}),
        "cases": cases,
    }


def _apply_candidate_to_case(case: dict[str, Any], threshold_payload: dict[str, Any], candidate: str) -> None:
    if case.get("risk_stage_key") != "extreme_danger_line_reached":
        return
    extreme_count = int(case.get("extreme_count", 0) or 0)
    danger_count = int(case.get("danger_count", 0) or 0)
    score = float(case.get("composite_risk_score", 0.0) or 0.0)
    if candidate == "stage_limited":
        if not (extreme_count >= 2 or score >= 85):
            _set_case_stage(case, "danger_line_reached", "limited_extreme_to_danger_without_clear_exception")
    elif candidate == "multi_confirm_extreme":
        if not (extreme_count >= 2 or (danger_count >= 4 and score >= 70)):
            _set_case_stage(case, "danger_line_reached", "downgraded_extreme_without_multi_confirmation")
    elif candidate == "ignore_fallback_extreme":
        fallback_tickers = _fallback_extreme_tickers(threshold_payload)
        fallback_extreme_count = sum(
            1 for row in case.get("indicators", []) if row.get("line_level") == "extreme" and row.get("ticker") in fallback_tickers
        )
        adjusted_extreme_count = max(0, extreme_count - fallback_extreme_count)
        case["extreme_count"] = adjusted_extreme_count
        if adjusted_extreme_count < 2 and score < 78:
            _set_case_stage(case, "danger_line_reached", "ignored_fallback_review_extreme_for_stage")
    elif candidate == "candidate_v2_combined":
        _apply_candidate_to_case(case, threshold_payload, "ignore_fallback_extreme")
        _apply_candidate_to_case(case, threshold_payload, "multi_confirm_extreme")
        _apply_candidate_to_case(case, threshold_payload, "stage_limited")


def _set_case_stage(case: dict[str, Any], stage_key: str, reason: str) -> None:
    case["risk_stage_key"] = stage_key
    case["risk_stage_label"] = "危険ライン到達" if stage_key == "danger_line_reached" else stage_key
    case.setdefault("candidate_adjustments", []).append(reason)


def _candidate_summary_row(payload: dict[str, Any], active: dict[str, Any]) -> dict[str, Any]:
    diff = _build_diff(active, payload)
    return {
        "label": payload["label"],
        "action_counts": payload.get("action_counts", {}),
        "risk_stage_counts": payload.get("risk_stage_counts", {}),
        "final_action_changed_count_vs_active": diff["summary"]["final_action_changed_count"],
        "risk_stage_changed_count_vs_active": diff["summary"]["risk_stage_changed_count"],
        "increased_wait_count_vs_active": diff["summary"]["cases_where_proposed_increased_wait"],
        "prevented_bad_buy_window_count_vs_active": diff["summary"]["cases_where_proposed_prevented_bad_buy_window"],
        "missed_good_buy_window_count_vs_active": diff["summary"]["cases_where_proposed_missed_good_buy_window"],
        "metrics": diff["summary"]["metrics"].get("proposed", {}),
    }


def _build_changed_case_diagnostics(active: dict[str, Any], proposed: dict[str, Any]) -> dict[str, Any]:
    active_by_date = {case["date"]: case for case in active["cases"]}
    proposed_by_date = {case["date"]: case for case in proposed["cases"]}
    active_returns = _validation_cases_by_date(active.get("validation", {}))
    changed = []
    for date_value in sorted(set(active_by_date) & set(proposed_by_date)):
        active_case = active_by_date[date_value]
        proposed_case = proposed_by_date[date_value]
        if (
            active_case["final_action"] == proposed_case["final_action"]
            and active_case["risk_stage_key"] == proposed_case["risk_stage_key"]
        ):
            continue
        validation_case = active_returns.get(date_value, {})
        changed.append(
            {
                "date": date_value,
                "history_file": proposed_case.get("source_history"),
                "active": _case_diagnostic(active_case),
                "proposed": _case_diagnostic(proposed_case),
                "contributing_indicators": _contributing_indicators(active_case, proposed_case),
                "forward_returns": validation_case.get("forward_returns", {}),
                "max_drawdowns": validation_case.get("max_drawdowns", {}),
                "classification": _changed_case_classification(validation_case),
            }
        )
    return {"status": "ok", "changed_count": len(changed), "cases": changed}


def _case_diagnostic(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "final_action": case.get("final_action"),
        "risk_stage": case.get("risk_stage_key"),
        "composite_risk_score": case.get("composite_risk_score"),
        "danger_count": case.get("danger_count"),
        "extreme_count": case.get("extreme_count"),
        "danger_lines": case.get("danger_lines", []),
        "extreme_lines": case.get("extreme_lines", []),
    }


def _contributing_indicators(active_case: dict[str, Any], proposed_case: dict[str, Any]) -> list[dict[str, Any]]:
    active_by_ticker = {row["ticker"]: row for row in active_case.get("indicators", [])}
    rows = []
    for proposed_row in proposed_case.get("indicators", []):
        ticker = proposed_row["ticker"]
        active_row = active_by_ticker.get(ticker, {})
        if active_row.get("line_level") == proposed_row.get("line_level") and active_row.get("line_reason") == proposed_row.get(
            "line_reason"
        ):
            continue
        rows.append(
            {
                "ticker": ticker,
                "name": proposed_row.get("ticker_name_ja", ticker),
                "active_level": active_row.get("line_level", "missing"),
                "proposed_level": proposed_row.get("line_level"),
                "active_reason": active_row.get("line_reason"),
                "proposed_reason": proposed_row.get("line_reason"),
                "active_pressure_score": active_row.get("pressure_score"),
                "proposed_pressure_score": proposed_row.get("pressure_score"),
            }
        )
    return rows


def _changed_case_classification(validation_case: dict[str, Any]) -> str:
    returns = validation_case.get("forward_returns", {})
    drawdowns = validation_case.get("max_drawdowns", {})
    four_week_return = returns.get("4w")
    four_week_dd = drawdowns.get("4w")
    if four_week_return is None and all(value is None for value in returns.values()):
        return "inconclusive"
    if (four_week_return is not None and four_week_return < -0.03) or (four_week_dd is not None and four_week_dd < -0.08):
        return "beneficial_block"
    if four_week_return is not None and four_week_return > 0.03 and (four_week_dd is None or four_week_dd > -0.05):
        return "overblocked"
    return "inconclusive"


def _render_changed_cases_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# threshold changed cases",
        "",
        f"- status: `{payload.get('status')}`",
        f"- changed_count: {payload.get('changed_count', 0)}",
        "",
        "| date | active | proposed | active score | proposed score | proposed danger/extreme | classification | top contributors |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for case in payload.get("cases", []):
        active = case["active"]
        proposed = case["proposed"]
        contributors = ", ".join(
            f"{row['ticker']} {row.get('active_level')}->{row.get('proposed_level')}" for row in case.get("contributing_indicators", [])[:4]
        )
        lines.append(
            "| {date} | {active_action}/{active_stage} | {proposed_action}/{proposed_stage} | {active_score} | {proposed_score} | {danger}/{extreme} | `{classification}` | {contributors} |".format(
                date=case["date"],
                active_action=active["final_action"],
                active_stage=active["risk_stage"],
                proposed_action=proposed["final_action"],
                proposed_stage=proposed["risk_stage"],
                active_score=active["composite_risk_score"],
                proposed_score=proposed["composite_risk_score"],
                danger=proposed["danger_count"],
                extreme=proposed["extreme_count"],
                classification=case["classification"],
                contributors=contributors or "-",
            )
        )
    return "\n".join(lines) + "\n"


def _decision(summary: dict[str, Any]) -> str:
    proposed_counts = summary.get("proposed_action_counts", {})
    total = max(int(summary.get("total_history_count", 0)), 1)
    proposed_wait_ratio = int(proposed_counts.get("wait", 0)) / total
    if int(proposed_counts.get("buy_window", 0)) == 0:
        return "hold"
    if proposed_wait_ratio > 0.85:
        return "reject"
    if summary.get("cases_where_proposed_missed_good_buy_window", 0):
        return "hold"
    return "hold"


def _metrics_from_validation(validation: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for action, payload in (validation.get("action_summary") or {}).items():
        result[action] = {"count": payload.get("count"), "horizons": payload.get("horizons", {})}
    return result


def _validation_cases_by_date(validation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {case.get("date"): case for case in validation.get("cases", []) if case.get("date")}


def _history_entry_for_validation(report: dict[str, Any], generated_at: datetime) -> dict[str, Any]:
    entry = deepcopy(report)
    entry["generated_at"] = generated_at.isoformat(timespec="seconds")
    return entry


def _compact_indicators(indicators: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "ticker": row.get("ticker"),
            "ticker_name_ja": row.get("ticker_name_ja"),
            "line_level": row.get("line_level"),
            "line_reason": row.get("line_reason"),
            "pressure_score": row.get("pressure_score"),
            "warning_line": row.get("warning_line"),
            "danger_line": row.get("danger_line"),
            "extreme_line": row.get("extreme_line"),
        }
        for row in indicators
    ]


def _load_prices(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, index_col=0, parse_dates=True)
    frame.index = pd.to_datetime(frame.index)
    return frame.sort_index()


def _latest_market_snapshot(cache_dir: Path) -> Path:
    candidates = sorted((cache_dir / "market_snapshots").glob("market_snapshot_*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(f"market snapshot CSV is missing under {cache_dir / 'market_snapshots'}")
    return candidates[0]


def _latest_market_snapshot_or_none(cache_dir: Path) -> Path | None:
    candidates = sorted((cache_dir / "market_snapshots").glob("market_snapshot_*.csv"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        return None
    return candidates[0]


def _load_history_entries(history_dir: Path) -> list[dict[str, Any]]:
    entries = []
    for path in sorted(history_dir.glob("report_*.json")):
        try:
            payload = _load_json(path)
        except json.JSONDecodeError:
            continue
        if not payload.get("generated_at"):
            continue
        payload["_source_file"] = path.name
        entries.append(payload)
    return entries


def _load_price_points(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if isinstance(payload, list):
        return payload
    return payload.get("prices", payload.get("price_points", []))


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _final_action(report: dict[str, Any]) -> str:
    spot = report.get("spot_signal") or {}
    decision = spot.get("action_decision") or {}
    return str(decision.get("final_action") or decision.get("action") or spot.get("action") or "")


def _original_action(report: dict[str, Any]) -> str:
    spot = report.get("spot_signal") or {}
    decision = spot.get("action_decision") or {}
    return str(decision.get("original_action") or spot.get("action") or "")


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay historical reports with active/proposed risk-line thresholds.")
    parser.add_argument("--config", default="project/config.yaml")
    parser.add_argument("--active-thresholds", default=str(ACTIVE_THRESHOLDS_PATH))
    parser.add_argument("--proposed-thresholds", default=str(PROPOSED_THRESHOLDS_PATH))
    parser.add_argument("--prices-csv", default=None)
    parser.add_argument("--reports-dir", default=None)
    args = parser.parse_args()
    result = run_threshold_historical_replay(
        config_path=args.config,
        active_thresholds_path=args.active_thresholds,
        proposed_thresholds_path=args.proposed_thresholds,
        prices_csv=args.prices_csv,
        reports_dir=args.reports_dir,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
