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

    if errors:
        raise ConfigValidationError("Invalid config.yaml:\n- " + "\n- ".join(errors))
    return warnings


def _defined_tickers(ticker_sections: Mapping[str, Any]) -> set[str]:
    values: set[str] = set()
    for section in ticker_sections.values():
        if isinstance(section, Mapping):
            values.update(str(value) for value in section.values())
    return values
