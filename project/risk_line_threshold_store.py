from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from project.threshold_metadata import rule_metadata


PROJECT_DIR = Path(__file__).resolve().parent
ACTIVE_THRESHOLDS_PATH = PROJECT_DIR / "risk_line_thresholds_active.json"
PROPOSED_THRESHOLDS_PATH = PROJECT_DIR / "risk_line_thresholds_proposed.json"


DEFAULT_ACTIVE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "SPY": {
        "weight": 1.15,
        "thresholds": {
            "warning": {"feature": "drawdown_13w", "threshold": -0.024156, "direction": "lower"},
        },
    },
    "HYG": {
        "weight": 1.05,
        "thresholds": {
            "warning": {"feature": "drawdown_13w", "threshold": -0.009923, "direction": "lower"},
            "danger": {"feature": "drawdown_13w", "threshold": -0.021683, "direction": "lower"},
        },
    },
    "LQD": {
        "weight": 0.85,
        "thresholds": {
            "warning": {"feature": "drawdown_13w", "threshold": -0.021276, "direction": "lower"},
        },
    },
    "HYG/LQD": {
        "weight": 1.3,
        "thresholds": {
            "warning": {"feature": "level_percentile", "threshold": 0.548077, "direction": "lower"},
            "danger": {"feature": "level_percentile", "threshold": 0.076923, "direction": "lower"},
        },
    },
    "^VIX": {
        "weight": 1.2,
        "thresholds": {
            "warning": {"feature": "level_zscore", "threshold": 0.289384, "direction": "higher"},
            "danger": {"feature": "level_percentile", "threshold": 0.875, "direction": "higher"},
        },
    },
    "^MOVE": {
        "weight": 1.2,
        "thresholds": {
            "warning": {"feature": "roc_8w", "threshold": 0.082386, "direction": "higher"},
        },
    },
    "CL=F": {"weight": 0.9, "thresholds": {}},
    "BZ=F": {
        "weight": 1.0,
        "thresholds": {
            "warning": {"feature": "roc_z_1w", "threshold": 0.56631, "direction": "higher"},
        },
    },
    "DX-Y.NYB": {
        "weight": 0.85,
        "thresholds": {
            "warning": {"feature": "level_percentile", "threshold": 0.781731, "direction": "higher"},
            "danger": {"feature": "level_percentile", "threshold": 0.903846, "direction": "higher"},
        },
    },
    "^TNX": {
        "weight": 1.05,
        "thresholds": {
            "warning": {"feature": "level_percentile", "threshold": 0.875, "direction": "higher"},
        },
    },
}


def default_active_threshold_payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "threshold_set": {
            "name": "risk-line-active",
            "version": "2026-04-05-active-v1",
            "status": "active",
            "generated_at": "2026-04-05T00:00:00+09:00",
            "source_report": "bootstrap_from_reality_checked_thresholds",
            "notes": "Reality-checked adopt thresholds only. Review/reject stages are excluded from live use.",
        },
        "indicators": deepcopy(DEFAULT_ACTIVE_DEFINITIONS),
    }


def default_proposed_threshold_payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "threshold_set": {
            "name": "risk-line-proposed",
            "version": "draft-empty",
            "status": "proposed",
            "generated_at": None,
            "source_report": None,
            "notes": "No proposed thresholds yet.",
        },
        "indicators": {},
    }


def ensure_threshold_files() -> None:
    if not ACTIVE_THRESHOLDS_PATH.exists():
        write_threshold_payload(ACTIVE_THRESHOLDS_PATH, default_active_threshold_payload())
    if not PROPOSED_THRESHOLDS_PATH.exists():
        write_threshold_payload(PROPOSED_THRESHOLDS_PATH, default_proposed_threshold_payload())


def load_threshold_payload(path: str | Path | None = None) -> dict[str, Any]:
    ensure_threshold_files()
    target = Path(path) if path else ACTIVE_THRESHOLDS_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def load_threshold_definitions(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    payload = load_threshold_payload(path)
    indicators = payload.get("indicators")
    if isinstance(indicators, dict):
        return indicators
    return deepcopy(DEFAULT_ACTIVE_DEFINITIONS)


def write_threshold_payload(path: str | Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def build_threshold_payload_from_reality_check(report: dict[str, Any], status: str = "proposed") -> dict[str, Any]:
    stamp = datetime.now().astimezone().isoformat(timespec="seconds")
    indicators: dict[str, Any] = {}
    for ticker, payload in report.get("indicators", {}).items():
        thresholds: dict[str, Any] = {}
        for stage, summary in payload.get("targets", {}).items():
            model = summary.get("selected_model") or {}
            actual = summary.get("actual_value_check") or {}
            if not model.get("feature"):
                continue
            thresholds[_stage_name(stage)] = {
                "feature": model.get("feature"),
                "threshold": model.get("threshold"),
                "direction": payload.get("adverse_direction"),
                "decision": summary.get("decision"),
                "selection_mode": summary.get("selection_mode", summary.get("decision")),
                "coverage_forced": bool(summary.get("coverage_forced", False)),
                "reason": summary.get("reason"),
                "backtest_metrics": summary.get("metrics") or {},
                "actual_value_check": actual,
                "raw_value_reference": summary.get("raw_value_reference") or [],
                "frequency_profile": summary.get("frequency_profile") or {},
            }
            thresholds[_stage_name(stage)]["metadata"] = rule_metadata(
                ticker,
                _stage_name(stage),
                thresholds[_stage_name(stage)],
                stamp,
            )
        indicators[ticker] = {
            "weight": DEFAULT_ACTIVE_DEFINITIONS.get(ticker, {}).get("weight", 1.0),
            "ordering_checks": payload.get("ordering_checks") or [],
            "thresholds": thresholds,
        }
    return {
        "schema_version": 1,
        "threshold_set": {
            "name": f"risk-line-{status}",
            "version": datetime.now().strftime("%Y-%m-%d-%H%M%S"),
            "status": status,
            "generated_at": stamp,
            "source_report": "risk_line_reality_checked_thresholds",
            "notes": "Generated from the latest reality-checked threshold report with full stage coverage. Manual approval required before live apply.",
        },
        "indicators": indicators,
    }


def build_threshold_diff(active_payload: dict[str, Any], proposed_payload: dict[str, Any]) -> dict[str, Any]:
    tickers = sorted(set(active_payload.get("indicators", {})) | set(proposed_payload.get("indicators", {})))
    changes: list[dict[str, Any]] = []
    summary = {"added": 0, "removed": 0, "changed": 0, "unchanged": 0}
    for ticker in tickers:
        active_thresholds = (active_payload.get("indicators", {}).get(ticker) or {}).get("thresholds", {})
        proposed_thresholds = (proposed_payload.get("indicators", {}).get(ticker) or {}).get("thresholds", {})
        for stage in sorted(set(active_thresholds) | set(proposed_thresholds)):
            active_rule = active_thresholds.get(stage)
            proposed_rule = proposed_thresholds.get(stage)
            change_type = _change_type(active_rule, proposed_rule)
            summary[change_type] = summary.get(change_type, 0) + 1
            changes.append(
                {
                    "ticker": ticker,
                    "stage": stage,
                    "change_type": change_type,
                    "active": active_rule,
                    "proposed": proposed_rule,
                }
            )
    return {
        "active_version": active_payload.get("threshold_set", {}).get("version"),
        "proposed_version": proposed_payload.get("threshold_set", {}).get("version"),
        "summary": summary,
        "changes": changes,
    }


def _change_type(active_rule: dict[str, Any] | None, proposed_rule: dict[str, Any] | None) -> str:
    if active_rule is None and proposed_rule is not None:
        return "added"
    if active_rule is not None and proposed_rule is None:
        return "removed"
    if _normalized_rule(active_rule) == _normalized_rule(proposed_rule):
        return "unchanged"
    return "changed"


def _normalized_rule(rule: dict[str, Any] | None) -> dict[str, Any] | None:
    if not rule:
        return None
    return {
        "feature": rule.get("feature"),
        "threshold": rule.get("threshold"),
        "direction": rule.get("direction"),
    }


def _stage_name(target_name: str) -> str:
    return target_name.replace("_target", "")
