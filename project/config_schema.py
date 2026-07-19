from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

REQUIRED_SECTIONS = ("app", "paths", "data", "tickers", "thresholds", "weights")
KNOWN_TOP_LEVEL_KEYS = {
    "schema_version",
    "app",
    "paths",
    "data",
    "tickers",
    "thresholds",
    "weights",
    "scheduler",
    "startup",
    "risk_line_recalibration",
    "japan_risk",
    "sector_vector_analysis",
    "hindenburg_omen",
    "risk_engine_v2",
}
CRITICAL_TICKERS = {"ACWI", "SPY", "^VIX", "HYG", "LQD", "USDJPY=X"}


class ConfigValidationError(ValueError):
    pass


def validate_config(config: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(config, Mapping):
        raise ConfigValidationError("config root must be a mapping. Fix config.yaml so the top level is key/value sections.")

    if "schema_version" not in config:
        errors.append("schema_version is missing. Add `schema_version: 1` at the top level of config.yaml.")

    for section in REQUIRED_SECTIONS:
        if section not in config:
            errors.append(f"{section} section is missing. Add top-level `{section}:` to config.yaml.")
        elif not isinstance(config.get(section), Mapping):
            errors.append(f"{section} section must be a mapping. Fix `{section}:` in config.yaml.")

    for key in config:
        if key not in KNOWN_TOP_LEVEL_KEYS:
            warnings.append(f"unknown top-level key `{key}` is present. Keep it only if downstream code intentionally uses it.")

    if isinstance(config.get("paths"), Mapping):
        for key, value in config["paths"].items():
            try:
                Path(value)
            except TypeError:
                errors.append(f"paths.{key} must be a string or Path-like value. Fix `paths.{key}` in config.yaml.")

    if isinstance(config.get("thresholds"), Mapping):
        for key, value in config["thresholds"].items():
            if not isinstance(value, int | float):
                errors.append(f"thresholds.{key} must be numeric. Fix `thresholds.{key}` in config.yaml.")
        buy = config["thresholds"].get("spot_score_buy")
        watch = config["thresholds"].get("spot_score_watch")
        if isinstance(buy, int | float) and isinstance(watch, int | float) and buy <= watch:
            errors.append("thresholds.spot_score_buy must be greater than thresholds.spot_score_watch.")

    if isinstance(config.get("weights"), Mapping):
        total_weight = 0.0
        for key, value in config["weights"].items():
            if not isinstance(value, int | float):
                errors.append(f"weights.{key} must be numeric and non-negative. Fix `weights.{key}` in config.yaml.")
                continue
            if value < 0:
                errors.append(f"weights.{key} must be 0 or greater. Fix `weights.{key}` in config.yaml.")
            total_weight += float(value)
        if total_weight <= 0:
            errors.append("weights total must be greater than 0. Increase at least one value in `weights:`.")

    if isinstance(config.get("tickers"), Mapping):
        defined = _defined_tickers(config["tickers"])
        missing = sorted(CRITICAL_TICKERS - defined)
        if missing:
            errors.append(
                "critical tickers are missing from `tickers`: "
                + ", ".join(missing)
                + ". Add them to the relevant ticker group in config.yaml."
            )

    if "risk_engine_v2" in config:
        _validate_risk_engine_v2(config["risk_engine_v2"], errors)

    if errors:
        raise ConfigValidationError("Invalid config.yaml:\n- " + "\n- ".join(errors))
    return warnings


def _defined_tickers(ticker_sections: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    for section in ticker_sections.values():
        if isinstance(section, Mapping):
            values.update(str(value) for value in section.values())
    return values


def _validate_risk_engine_v2(section: Any, errors: list[str]) -> None:
    if not isinstance(section, Mapping):
        errors.append("risk_engine_v2 section must be a mapping. Fix `risk_engine_v2:` in config.yaml.")
        return
    mode = section.get("mode", "shadow")
    if mode not in {"legacy", "shadow", "domain_v2"}:
        errors.append("risk_engine_v2.mode must be one of legacy, shadow, domain_v2.")
    minimum_coverage = section.get("minimum_eligible_domain_coverage", 0.75)
    if not isinstance(minimum_coverage, int | float) or not 0 < float(minimum_coverage) <= 1:
        errors.append("risk_engine_v2.minimum_eligible_domain_coverage must be > 0 and <= 1.")
    weights = section.get("domain_weights")
    if isinstance(weights, Mapping):
        total = 0.0
        for key, value in weights.items():
            if not isinstance(value, int | float):
                errors.append(f"risk_engine_v2.domain_weights.{key} must be numeric.")
                continue
            if value < 0:
                errors.append(f"risk_engine_v2.domain_weights.{key} must be 0 or greater.")
            total += float(value)
        if abs(total - 1.0) > 0.0001:
            errors.append("risk_engine_v2.domain_weights must sum to 1.0.")
    freshness = section.get("freshness_limits_calendar_days")
    if freshness is not None and not isinstance(freshness, Mapping):
        errors.append("risk_engine_v2.freshness_limits_calendar_days must be a mapping.")
    elif isinstance(freshness, Mapping):
        for key, value in freshness.items():
            if not isinstance(value, int) or value < 0:
                errors.append(f"risk_engine_v2.freshness_limits_calendar_days.{key} must be a non-negative integer.")
    persistence = section.get("persistence")
    if persistence is not None and not isinstance(persistence, Mapping):
        errors.append("risk_engine_v2.persistence must be a mapping.")
    elif isinstance(persistence, Mapping):
        for key in (
            "warning_entry_observations",
            "warning_entry_window",
            "danger_entry_consecutive",
            "exit_consecutive",
            "expected_cadence_days",
            "max_gap_days",
        ):
            value = persistence.get(key)
            if value is not None and (not isinstance(value, int) or value <= 0):
                errors.append(f"risk_engine_v2.persistence.{key} must be a positive integer.")
