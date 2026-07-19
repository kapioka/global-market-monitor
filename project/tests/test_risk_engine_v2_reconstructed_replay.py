from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest
import yaml

import project.risk_engine_v2_reconstructed_replay as reconstructed_replay
from project.pipeline import load_risk_engine_v2_reconstructed_replay_summary
from project.report_generator import render_developer_diagnostics_markdown
from project.risk_engine_v2_reconstructed_replay import (
    build_reconstructed_history_entries,
    build_reconstructed_risk_engine_v2_replay,
    run_reconstructed_risk_engine_v2_replay,
)
from project.risk_engine_v2_replay_schedule import canonical_weekly_prices, limit_cases_across_period, select_calendar_spaced_dates


def _prices() -> pd.DataFrame:
    index = pd.date_range("2020-01-03", periods=170, freq="W-FRI")
    values = [100.0 + i * 0.1 for i in range(len(index))]
    return pd.DataFrame(
        {
            "ACWI": values,
            "SPY": values,
            "HYG": [100.0] * len(index),
            "LQD": [100.0] * len(index),
            "^VIX": [20.0] * len(index),
            "^MOVE": [100.0] * len(index),
            "CL=F": [70.0] * len(index),
            "BZ=F": [75.0] * len(index),
            "DX-Y.NYB": [100.0] * len(index),
            "^TNX": [4.0] * len(index),
        },
        index=index,
    )


def _config() -> dict:
    return {
        "data": {
            "monitor_windows_weeks": {"short": 1, "medium": 4, "long": 12},
            "zscore_window_weeks": 8,
        },
        "tickers": {
            "risk_indicators": {
                "SPY": "SPY",
                "HYG": "HYG",
                "LQD": "LQD",
                "VIX": "^VIX",
                "MOVE": "^MOVE",
                "WTI": "CL=F",
                "Brent": "BZ=F",
                "DXY": "DX-Y.NYB",
                "US10Y": "^TNX",
            }
        },
        "risk_engine_v2": {
            "mode": "shadow",
            "minimum_eligible_domain_coverage": 0.75,
            "official_series": {
                "credit_hy_oas": "FRED:BAMLH0A0HYM2",
                "credit_ig_oas": "FRED:BAMLC0A0CM",
                "real_yield_10y": "FRED:DFII10",
                "breakeven_10y": "FRED:T10YIE",
                "curve_10y2y": "FRED:T10Y2Y",
                "curve_10y3m": "FRED:T10Y3M",
                "financial_conditions": "FRED:NFCI",
            },
            "persistence": {
                "warning_entry_observations": 2,
                "warning_entry_window": 3,
                "danger_entry_consecutive": 2,
                "exit_consecutive": 2,
            },
        },
    }


def _official_prices() -> pd.DataFrame:
    official_prices = pd.DataFrame(index=_prices().index)
    for ticker in _config()["risk_engine_v2"]["official_series"].values():
        official_prices[ticker] = [1.0 + index * 0.01 for index in range(len(official_prices))]
    return official_prices


def _write_config(path, *, official_series_csv: str | None = None) -> None:
    config = yaml.safe_load(Path("project/config.yaml").read_text(encoding="utf-8"))
    safe_official_series_csv = official_series_csv.replace("\\", "/") if official_series_csv else None
    if safe_official_series_csv:
        config.setdefault("risk_engine_v2", {})["official_series_csv"] = safe_official_series_csv
    path.write_text(yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_reconstructed_history_entries_are_point_in_time():
    entries = build_reconstructed_history_entries(
        _prices(),
        _config(),
        start_date="2021-01-01",
        end_date="2021-03-31",
        stride_weeks=4,
    )

    assert entries
    for entry in entries:
        evaluation_date = entry["generated_at"][:10]
        assert entry["reconstruction"]["point_in_time"] is True
        assert entry["reconstruction"]["latest_price_date"] == evaluation_date
        for row in entry["risk_monitor"]:
            assert row["observation_metadata"]["latest_observation_date"] <= evaluation_date


def test_reconstructed_replay_keeps_policy_diagnostic_only():
    payload = build_reconstructed_risk_engine_v2_replay(
        _prices(),
        _config(),
        start_date="2021-01-01",
        end_date="2021-12-31",
        stride_weeks=4,
    )

    assert payload["status"] == "ok"
    assert payload["replay_type"] == "risk_engine_v2_reconstructed_shadow"
    assert payload["policy_status"] == "diagnostic_only_not_promoted"
    assert payload["affects_final_action"] is False
    assert payload["reconstruction"]["history_files_modified"] is False
    assert payload["summary"]["outcome_summary"]["status"] == "ok"


def test_reconstructed_replay_writes_and_loads_developer_summary(tmp_path):
    prices_path = tmp_path / "prices.csv"
    reports_dir = tmp_path / "reports"
    _prices().to_csv(prices_path)

    result = run_reconstructed_risk_engine_v2_replay(
        input_prices=prices_path,
        config_path="project/config.yaml",
        reports_dir=reports_dir,
        start_date="2021-01-01",
        end_date="2021-12-31",
        stride_weeks=4,
    )
    summary = load_risk_engine_v2_reconstructed_replay_summary(reports_dir)
    markdown = render_developer_diagnostics_markdown(
        {
            "title": "Test",
            "generated_at": "2026-01-01T07:30:00",
            "risk_engine_v2_reconstructed_replay": summary,
        }
    )

    assert result["status"] == "ok"
    assert summary["outcome_status"] == "ok"
    assert summary["affects_final_action"] is False
    assert "risk_engine_v2 再構築リプレイ" in markdown
    assert "history_files_modified: いいえ" in markdown


def test_reconstructed_replay_auto_loads_official_series_store(tmp_path):
    prices_path = tmp_path / "prices.csv"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    _prices().to_csv(prices_path)
    _official_prices().to_csv(reports_dir / "risk_engine_v2_official_series.csv")

    result = run_reconstructed_risk_engine_v2_replay(
        input_prices=prices_path,
        config_path="project/config.yaml",
        reports_dir=reports_dir,
        official_series_csv=reports_dir / "risk_engine_v2_official_series.csv",
        start_date="2021-01-01",
        end_date="2021-12-31",
        stride_weeks=13,
        max_cases=3,
    )

    assert result["reconstruction"]["strict_primary_available"] is True
    snapshot = result["reconstruction"]["market_snapshot"]
    assert snapshot["loaded"] is True
    assert snapshot["requested_path"] == str(prices_path)
    assert snapshot["resolved_path"] == str(prices_path.resolve())
    assert snapshot["sha256"] == hashlib.sha256(prices_path.read_bytes()).hexdigest()
    assert snapshot["row_count"] == len(_prices())
    assert snapshot["min_observation_date"] == "2020-01-03"
    assert snapshot["max_observation_date"] == "2023-03-31"
    assert snapshot["duplicate_date_count"] == 0
    store = result["reconstruction"]["official_series_store"]
    assert store["loaded"] is True
    assert store["selection_origin"] == "cli_explicit"
    assert store["exists"] is True
    assert store["sha256"] == hashlib.sha256((reports_dir / "risk_engine_v2_official_series.csv").read_bytes()).hexdigest()
    assert all(store["required_series_presence"].values())


def test_reconstructed_replay_explicit_missing_official_series_fails_without_overwrite(tmp_path):
    prices_path = tmp_path / "prices.csv"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    _prices().to_csv(prices_path)
    output = reports_dir / "risk_engine_v2_reconstructed_replay.json"
    output.write_text('{"status":"previous"}', encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="selection_origin=cli_explicit"):
        run_reconstructed_risk_engine_v2_replay(
            input_prices=prices_path,
            config_path="project/config.yaml",
            reports_dir=reports_dir,
            official_series_csv=tmp_path / "missing_official_series.csv",
            start_date="2021-01-01",
            end_date="2021-12-31",
            stride_weeks=13,
            max_cases=3,
        )

    assert output.read_text(encoding="utf-8") == '{"status":"previous"}'


def test_reconstructed_replay_env_missing_official_series_fails_without_overwrite(tmp_path, monkeypatch):
    prices_path = tmp_path / "prices.csv"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    _prices().to_csv(prices_path)
    output = reports_dir / "risk_engine_v2_reconstructed_replay.json"
    output.write_text('{"status":"previous"}', encoding="utf-8")
    monkeypatch.setenv(reconstructed_replay.OFFICIAL_SERIES_ENV_VAR, str(tmp_path / "missing_env.csv"))

    with pytest.raises(FileNotFoundError, match=f"selection_origin=env:{reconstructed_replay.OFFICIAL_SERIES_ENV_VAR}"):
        run_reconstructed_risk_engine_v2_replay(
            input_prices=prices_path,
            config_path="project/config.yaml",
            reports_dir=reports_dir,
            start_date="2021-01-01",
            end_date="2021-12-31",
            stride_weeks=13,
            max_cases=3,
        )

    assert output.read_text(encoding="utf-8") == '{"status":"previous"}'


def test_reconstructed_replay_config_missing_official_series_fails_without_overwrite(tmp_path, monkeypatch):
    prices_path = tmp_path / "prices.csv"
    reports_dir = tmp_path / "reports"
    config_path = tmp_path / "config.yaml"
    reports_dir.mkdir()
    _prices().to_csv(prices_path)
    _write_config(config_path, official_series_csv=str(tmp_path / "missing_config.csv"))
    output = reports_dir / "risk_engine_v2_reconstructed_replay.json"
    output.write_text('{"status":"previous"}', encoding="utf-8")
    monkeypatch.delenv(reconstructed_replay.OFFICIAL_SERIES_ENV_VAR, raising=False)

    with pytest.raises(FileNotFoundError, match="selection_origin=config:risk_engine_v2.official_series_csv"):
        run_reconstructed_risk_engine_v2_replay(
            input_prices=prices_path,
            config_path=config_path,
            reports_dir=reports_dir,
            start_date="2021-01-01",
            end_date="2021-12-31",
            stride_weeks=13,
            max_cases=3,
        )

    assert output.read_text(encoding="utf-8") == '{"status":"previous"}'


def test_reconstructed_replay_default_missing_official_series_fails_without_overwrite(tmp_path, monkeypatch):
    prices_path = tmp_path / "prices.csv"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    _prices().to_csv(prices_path)
    output = reports_dir / "risk_engine_v2_reconstructed_replay.json"
    output.write_text('{"status":"previous"}', encoding="utf-8")
    monkeypatch.delenv(reconstructed_replay.OFFICIAL_SERIES_ENV_VAR, raising=False)
    monkeypatch.setattr(reconstructed_replay, "DEFAULT_OFFICIAL_SERIES_CSV", tmp_path / "missing_default.csv")

    with pytest.raises(FileNotFoundError, match="selection_origin=repository_default"):
        run_reconstructed_risk_engine_v2_replay(
            input_prices=prices_path,
            config_path="project/config.yaml",
            reports_dir=reports_dir,
            start_date="2021-01-01",
            end_date="2021-12-31",
            stride_weeks=13,
            max_cases=3,
        )

    assert output.read_text(encoding="utf-8") == '{"status":"previous"}'


def test_reconstructed_replay_invalid_official_series_schema_fails_without_overwrite(tmp_path):
    prices_path = tmp_path / "prices.csv"
    reports_dir = tmp_path / "reports"
    invalid_store = tmp_path / "invalid_official.csv"
    reports_dir.mkdir()
    _prices().to_csv(prices_path)
    pd.DataFrame({"FRED:BAMLH0A0HYM2": [1.0]}, index=pd.to_datetime(["2021-01-01"])).to_csv(invalid_store)
    output = reports_dir / "risk_engine_v2_reconstructed_replay.json"
    output.write_text('{"status":"previous"}', encoding="utf-8")

    with pytest.raises(ValueError, match="does not satisfy the required schema"):
        run_reconstructed_risk_engine_v2_replay(
            input_prices=prices_path,
            config_path="project/config.yaml",
            reports_dir=reports_dir,
            official_series_csv=invalid_store,
            start_date="2021-01-01",
            end_date="2021-12-31",
            stride_weeks=13,
            max_cases=3,
        )

    assert output.read_text(encoding="utf-8") == '{"status":"previous"}'


def test_reconstructed_replay_valid_default_official_series_succeeds(tmp_path, monkeypatch):
    prices_path = tmp_path / "prices.csv"
    reports_dir = tmp_path / "reports"
    default_store = tmp_path / "risk_engine_v2_official_series.csv"
    reports_dir.mkdir()
    _prices().to_csv(prices_path)
    _official_prices().to_csv(default_store)
    monkeypatch.delenv(reconstructed_replay.OFFICIAL_SERIES_ENV_VAR, raising=False)
    monkeypatch.setattr(reconstructed_replay, "DEFAULT_OFFICIAL_SERIES_CSV", default_store)

    result = run_reconstructed_risk_engine_v2_replay(
        input_prices=prices_path,
        config_path="project/config.yaml",
        reports_dir=reports_dir,
        start_date="2021-01-01",
        end_date="2021-12-31",
        stride_weeks=13,
        max_cases=3,
    )

    store = result["reconstruction"]["official_series_store"]
    assert result["status"] == "ok"
    assert store["selection_origin"] == "repository_default"
    assert store["loaded"] is True
    assert all(store["required_series_presence"].values())


def test_reconstructed_replay_resolves_relative_official_series_from_repo_root(tmp_path):
    prices_path = tmp_path / "prices.csv"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    _prices().to_csv(prices_path)

    result = run_reconstructed_risk_engine_v2_replay(
        input_prices=prices_path,
        config_path="project/config.yaml",
        reports_dir=reports_dir,
        official_series_csv="project/reports/risk_engine_v2_official_series.csv",
        start_date="2023-08-01",
        end_date="2023-10-31",
        stride_weeks=13,
        max_cases=2,
    )

    store = result["reconstruction"]["official_series_store"]
    assert store["selection_origin"] == "cli_explicit"
    assert store["exists"] is True
    assert store["loaded"] is True
    assert store["resolved_path"].endswith("project\\reports\\risk_engine_v2_official_series.csv") or store["resolved_path"].endswith(
        "project/reports/risk_engine_v2_official_series.csv"
    )


def test_stride_weeks_uses_calendar_weeks_not_rows():
    daily_candidates = pd.date_range("2021-01-01", periods=90, freq="B")

    selected = select_calendar_spaced_dates(daily_candidates, stride_weeks=13)

    assert len(selected) == 2
    assert (selected[1] - selected[0]).days >= 91


def test_max_cases_limits_across_full_period_without_latest_only_truncation():
    dates = list(pd.date_range("2018-01-05", periods=36, freq="13W-FRI"))

    selected = limit_cases_across_period(dates, max_cases=6)

    assert len(selected) == 6
    assert selected[0] == dates[0]
    assert selected[-1] == dates[-1]
    assert selected[1] < dates[-6]


def test_reconstructed_replay_resamples_daily_prices_to_weekly_and_reports_coverage():
    daily_index = pd.date_range("2020-01-01", periods=650, freq="B")
    values = [100.0 + i * 0.1 for i in range(len(daily_index))]
    daily_prices = pd.DataFrame(
        {
            "ACWI": values,
            "SPY": values,
            "HYG": [100.0] * len(daily_index),
            "LQD": [100.0] * len(daily_index),
            "^VIX": [20.0] * len(daily_index),
            "^MOVE": [100.0] * len(daily_index),
            "CL=F": [70.0] * len(daily_index),
            "BZ=F": [75.0] * len(daily_index),
            "DX-Y.NYB": [100.0] * len(daily_index),
            "^TNX": [4.0] * len(daily_index),
        },
        index=daily_index,
    )

    entries = build_reconstructed_history_entries(
        daily_prices,
        _config(),
        start_date="2021-01-01",
        end_date="2021-12-31",
        stride_weeks=13,
        max_cases=3,
    )
    payload = build_reconstructed_risk_engine_v2_replay(
        daily_prices,
        _config(),
        start_date="2021-01-01",
        end_date="2021-12-31",
        stride_weeks=13,
        max_cases=3,
    )

    assert len(entries) == 53
    assert entries[0]["date"].startswith("2021")
    assert entries[-1]["date"].startswith("2021")
    assert entries[0]["reconstruction"]["frequency"] == "canonical_weekly"
    assert entries[0]["reconstruction"]["calibration_pack_frequency"] == "weekly"
    assert entries[0]["reconstruction"]["strict_primary_available"] is False
    assert entries[0]["reconstruction"]["fallback_replay_available"] is True
    assert payload["reconstruction"]["strict_primary_available"] is False
    assert payload["reconstruction"]["fallback_domain_coverage"] == 1.0
    assert payload["reconstruction"]["cadence"]["engine_evaluation_cadence"] == "canonical_weekly"
    assert payload["reconstruction"]["cadence"]["case_sampling_stride"] == 13
    assert payload["summary"]["timeline_case_count"] == 53
    assert payload["summary"]["sampled_case_count"] == 3
    assert payload["summary"]["persistence_gap_reset_count"] == 0
    assert payload["summary"]["strict_primary_available"] is False
    assert payload["summary"]["primary_strict_available_cases"] == 0
    assert payload["summary"]["fallback_strict_available_cases"] >= 0
    assert payload["decision"]["primary_strict_available_cases"] == 0
    assert "FRED:" in payload["reconstruction"]["primary_missing_series"][0]


def test_reconstructed_replay_uses_official_series_when_present():
    prices = _prices()
    for ticker in _config()["risk_engine_v2"]["official_series"].values():
        prices[ticker] = [1.0 + index * 0.01 for index in range(len(prices))]

    payload = build_reconstructed_risk_engine_v2_replay(
        prices,
        _config(),
        start_date="2021-01-01",
        end_date="2021-12-31",
        stride_weeks=13,
        max_cases=3,
    )

    assert payload["reconstruction"]["strict_primary_available"] is True
    assert payload["reconstruction"]["primary_domain_coverage"] == 1.0
    assert payload["reconstruction"]["primary_missing_series"] == []
    assert payload["summary"]["strict_primary_available"] is True
    assert payload["summary"]["primary_strict_available_cases"] == payload["summary"]["fallback_strict_available_cases"]


def test_canonical_weekly_prices_uses_last_observation_before_week_end():
    daily = pd.DataFrame({"SPY": [1.0, 2.0, 3.0]}, index=pd.to_datetime(["2021-01-04", "2021-01-05", "2021-01-08"]))

    weekly = canonical_weekly_prices(daily)

    assert list(weekly.index) == [pd.Timestamp("2021-01-08")]
    assert float(weekly.iloc[0]["SPY"]) == 3.0
