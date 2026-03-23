from __future__ import annotations

from datetime import date
import logging
from pathlib import Path
import shutil
import sys
import uuid

from project.main import collect_tickers, compute_backfill_dates, default_config_path, open_dashboard_file
from project.main import build_report, persist_report
from project.data_fetcher import FetchResult
import pandas as pd


TEST_TMP_ROOT = Path(__file__).resolve().parent / "_tmp"


def make_test_dir(name: str) -> Path:
    path = TEST_TMP_ROOT / f"{name}_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_collect_tickers_deduplicates_across_groups():
    config = {
        "tickers": {
            "group_a": {"A": "SPY", "B": "ACWI"},
            "group_b": {"C": "SPY", "D": "GLD"},
        }
    }
    assert collect_tickers(config) == ["SPY", "ACWI", "GLD"]


def test_open_dashboard_file_uses_default_browser(monkeypatch):
    captured = {}
    dashboard_path = Path(__file__).resolve().parents[1] / "reports" / "dashboard.html"

    def fake_open(url: str) -> bool:
        captured["url"] = url
        return True

    monkeypatch.setattr("project.main.webbrowser.open", fake_open)

    assert open_dashboard_file(dashboard_path) is True
    assert captured["url"] == dashboard_path.resolve().as_uri()


def test_compute_backfill_dates_returns_missing_days():
    tmp_path = make_test_dir("backfill")
    try:
        history_dir = tmp_path / "reports" / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        (history_dir / "report_2026-03-16_073000.json").write_text("{}", encoding="utf-8")
        (history_dir / "report_2026-03-18_073000.json").write_text("{}", encoding="utf-8")

        missing = compute_backfill_dates(tmp_path / "reports", date(2026, 3, 19), max_backfill_days=5)

        assert missing == [date(2026, 3, 14), date(2026, 3, 15), date(2026, 3, 17)]
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_default_config_path_for_source_layout():
    expected = Path(__file__).resolve().parents[1] / "config.yaml"
    assert default_config_path() == expected


def test_default_config_path_for_frozen_layout(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"E:\dist\GlobalMarketMonitor\GlobalMarketMonitor.exe", raising=False)

    assert default_config_path() == Path(r"E:\dist\GlobalMarketMonitor\project\config.yaml")


def test_default_config_path_prefers_internal_bundle_when_root_copy_is_missing(monkeypatch):
    tmp_path = make_test_dir("bundle")
    try:
        internal_config = tmp_path / "_internal" / "project" / "config.yaml"
        internal_config.parent.mkdir(parents=True, exist_ok=True)
        internal_config.write_text("app: {}", encoding="utf-8")

        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "GlobalMarketMonitor.exe"), raising=False)
        monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "_internal"), raising=False)

        assert default_config_path() == internal_config
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_build_report_includes_alerts():
    config = {
        "app": {"report_title": "Test"},
        "data": {
            "min_history_points": 5,
            "monitor_windows_weeks": {"short": 1, "medium": 4, "long": 12},
            "zscore_window_weeks": 10,
            "max_analogue_results": 2,
        },
        "thresholds": {
            "adx_trend_strong": 20,
            "drawdown_alert": -0.12,
            "volatility_compression_ratio": 0.9,
            "regime_risk_on_score": 0.35,
            "regime_risk_off_score": -0.15,
            "spot_score_buy": 0.65,
            "spot_score_watch": 0.45,
            "penalty_transition": 0.02,
            "penalty_risk_off": 0.06,
            "penalty_risk_off_relief": 0.02,
            "penalty_risk_off_relief_score_min": 0.48,
            "penalty_credit_stress_moderate": 0.12,
            "penalty_credit_stress_severe": 0.16,
            "penalty_credit_stress": 0.16,
            "penalty_inflation_shock_oil_only": 0.06,
            "penalty_inflation_shock_broad": 0.1,
            "penalty_inflation_shock": 0.1,
            "penalty_stagflation_warning": 0.18,
        },
        "weights": {
            "trend": 0.2,
            "momentum": 0.2,
            "breadth_proxy": 0.15,
            "drawdown": 0.15,
            "volatility": 0.1,
            "macro_proxy": 0.1,
            "credit_stress": 0.1,
        },
        "tickers": {
            "sector_etfs": {"Energy": "XLE"},
            "asset_classes": {"Stocks": "SPY", "Gold": "GLD"},
            "credit": {"HighYield": "HYG", "InvestmentGrade": "LQD"},
            "inflation": {"Oil": "CL=F", "Gold": "GC=F", "Dollar": "DX-Y.NYB", "Mortgage_30Y": "FRED:MORTGAGE30US"},
        },
        "scheduler": {"hour": 7, "minute": 30},
    }
    index = pd.date_range("2025-01-03", periods=80, freq="W-FRI")
    prices = pd.DataFrame(
        {
            "ACWI": range(100, 180),
            "XLE": range(80, 160),
            "SPY": range(90, 170),
            "GLD": range(70, 150),
            "HYG": [80 - (i * 0.05) for i in range(80)],
            "LQD": [100 + (i * 0.02) for i in range(80)],
            "CL=F": [70 + (i * 0.4) for i in range(80)],
            "GC=F": [1800 + (i * 2) for i in range(80)],
            "DX-Y.NYB": [100 + (i * 0.08) for i in range(80)],
            "FRED:MORTGAGE30US": [6.0 + (i * 0.01) for i in range(80)],
        },
        index=index,
        dtype=float,
    )
    fetch = FetchResult(
        prices=prices,
        source="sample",
        warnings=[],
        acquisition_log=[],
        diagnostics={"summary": {"source": "sample", "failed_attempt_count": 0, "suspected_network_issue": False}},
    )

    report = build_report(config, fetch)

    assert "alerts" in report
    assert isinstance(report["alerts"], list)
    assert "risk_lines" in report
    assert report["risk_lines"]["stage_label"]
    assert "investment_candidates" in report
    assert report["investment_candidates"]["label"] in {"優先候補", "観察候補", "候補なし"}


def test_build_report_holds_decision_when_critical_series_are_sample_based():
    config = {
        "app": {"report_title": "Test"},
        "data": {
            "min_history_points": 5,
            "monitor_windows_weeks": {"short": 1, "medium": 4, "long": 12},
            "zscore_window_weeks": 10,
            "max_analogue_results": 2,
        },
        "thresholds": {
            "adx_trend_strong": 20,
            "drawdown_alert": -0.12,
            "volatility_compression_ratio": 0.9,
            "regime_risk_on_score": 0.35,
            "regime_risk_off_score": -0.15,
            "spot_score_buy": 0.65,
            "spot_score_watch": 0.45,
            "penalty_transition": 0.02,
            "penalty_risk_off": 0.06,
            "penalty_risk_off_relief": 0.02,
            "penalty_risk_off_relief_score_min": 0.48,
            "penalty_credit_stress_moderate": 0.12,
            "penalty_credit_stress_severe": 0.16,
            "penalty_credit_stress": 0.16,
            "penalty_inflation_shock_oil_only": 0.06,
            "penalty_inflation_shock_broad": 0.1,
            "penalty_inflation_shock": 0.1,
            "penalty_stagflation_warning": 0.18,
        },
        "weights": {
            "trend": 0.2,
            "momentum": 0.2,
            "breadth_proxy": 0.15,
            "drawdown": 0.15,
            "volatility": 0.1,
            "macro_proxy": 0.1,
            "credit_stress": 0.1,
        },
        "tickers": {
            "global_equities": {"ACWI": "ACWI"},
            "sector_etfs": {"Energy": "XLE"},
            "asset_classes": {"Stocks": "SPY", "Gold": "GLD"},
            "credit": {"HighYield": "HYG", "InvestmentGrade": "LQD"},
            "inflation": {"Oil": "CL=F", "Gold": "GC=F", "Dollar": "DX-Y.NYB"},
        },
        "scheduler": {"hour": 7, "minute": 30},
    }
    index = pd.date_range("2025-01-03", periods=80, freq="W-FRI")
    prices = pd.DataFrame(
        {
            "ACWI": range(100, 180),
            "XLE": range(80, 160),
            "SPY": range(90, 170),
            "GLD": range(70, 150),
            "HYG": [80 - (i * 0.05) for i in range(80)],
            "LQD": [100 + (i * 0.02) for i in range(80)],
            "CL=F": [70 + (i * 0.4) for i in range(80)],
            "GC=F": [1800 + (i * 2) for i in range(80)],
            "DX-Y.NYB": [100 + (i * 0.08) for i in range(80)],
        },
        index=index,
        dtype=float,
    )
    fetch = FetchResult(
        prices=prices,
        source="mixed",
        warnings=[],
        acquisition_log=[
            {"requested_ticker": "ACWI", "status": "sample_fallback"},
            {"requested_ticker": "HYG", "status": "ok"},
            {"requested_ticker": "LQD", "status": "ok"},
            {"requested_ticker": "CL=F", "status": "ok"},
            {"requested_ticker": "GC=F", "status": "ok"},
            {"requested_ticker": "DX-Y.NYB", "status": "ok"},
        ],
        diagnostics={"summary": {"source": "mixed", "requested_count": 6, "sample_fallback_count": 1, "unavailable_count": 0, "failed_attempt_count": 1, "suspected_network_issue": False}},
    )

    report = build_report(config, fetch)

    assert report["data_reliability"]["decision_allowed"] is True
    assert report["regime"]["regime_label"] != "data_unavailable"
    assert report["risk_lines"]["strict_judgement_available"] is False
    assert "厳密な" in report["risk_lines"]["summary"]
    assert report["warnings"]


def test_persist_report_skips_non_live_history_and_prunes_same_day_entries():
    tmp_path = make_test_dir("persist")
    try:
        paths = {
            "reports_dir": tmp_path / "reports",
            "sample_output_dir": tmp_path / "sample_output",
        }
        paths["reports_dir"].mkdir(parents=True, exist_ok=True)
        paths["sample_output_dir"].mkdir(parents=True, exist_ok=True)
        history_dir = paths["reports_dir"] / "history"
        history_dir.mkdir(parents=True, exist_ok=True)

        valid_report = {
            "title": "Test",
            "generated_at": "2026-03-20T07:30:00",
            "data_source": "mixed",
            "runtime_context": {},
            "fetch_diagnostics": {"summary": {"source": "mixed"}},
            "data_reliability": {"decision_allowed": True, "level": "medium"},
            "regime": {"regime_label": "risk_on"},
            "cycle": {"phase_label": "upswing", "phase_angle_deg": 10},
            "score": {"total_score": 0.7},
            "spot_signal": {"action": "buy_window", "second_leg_risk": "low"},
            "sector_rotation": {"table": []},
            "asset_compare": [],
            "investment_candidates": {"label": "候補なし", "summary": "-", "candidate_tickers": [], "rationale": []},
            "credit_monitor": [],
            "inflation_monitor": [],
            "alerts": [],
            "analogues": [],
            "warnings": [],
            "data_availability": [],
        }
        invalid_report = {
            **valid_report,
            "generated_at": "2026-03-20T08:30:00",
            "data_source": "sample",
            "data_reliability": {"decision_allowed": False, "level": "low"},
            "regime": {"regime_label": "data_unavailable"},
            "spot_signal": {"action": "wait", "second_leg_risk": "high"},
        }
        later_valid_report = {
            **valid_report,
            "generated_at": "2026-03-20T09:30:00",
        }

        logger = logging.getLogger("test")
        persist_report(valid_report, paths, logger, open_dashboard=False, persist_history=True)
        persist_report(invalid_report, paths, logger, open_dashboard=False, persist_history=True)
        persist_report(later_valid_report, paths, logger, open_dashboard=False, persist_history=True)

        history_files = sorted(history_dir.glob("report_*.json"))
        assert len(history_files) == 1
        assert history_files[0].name == "report_2026-03-20_093000.json"
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
