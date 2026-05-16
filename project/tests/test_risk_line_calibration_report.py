from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from project.data_fetcher import FetchResult
from project.risk_line_calibration_report import (
    build_risk_line_backtest_from_config,
    render_risk_line_backtest_markdown,
    write_risk_line_backtest_report,
)


def _prices() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "SPY": [100.0 + i * 0.2 for i in range(180)],
            "HYG": [80.0 + i * 0.04 for i in range(180)],
            "LQD": [100.0 + i * 0.02 for i in range(180)],
            "^VIX": [18.0 + (i % 10) * 0.4 for i in range(180)],
            "^MOVE": [105.0 + (i % 8) * 1.1 for i in range(180)],
            "CL=F": [70.0 + i * 0.15 for i in range(180)],
            "BZ=F": [73.0 + i * 0.17 for i in range(180)],
            "DX-Y.NYB": [95.0 + i * 0.03 for i in range(180)],
            "^TNX": [2.0 + i * 0.01 for i in range(180)],
        },
        index=pd.date_range("2019-01-04", periods=180, freq="W-FRI"),
        dtype=float,
    )


def test_build_risk_line_backtest_from_config_uses_fetch_result(monkeypatch):
    def fake_fetch_market_data(**kwargs):
        return FetchResult(prices=_prices(), warnings=["stub"], source="sample", acquisition_log=[], diagnostics={})

    monkeypatch.setattr("project.risk_line_calibration_report.fetch_market_data", fake_fetch_market_data)

    config = {
        "data": {"period_years": 10, "interval": "1wk"},
        "paths": {"reports_dir": "project/reports", "cache_dir": "project/cache"},
        "tickers": {"risk_indicators": {"SPY": "SPY", "HYG": "HYG", "LQD": "LQD", "VIX": "^VIX", "MOVE": "^MOVE", "WTI": "CL=F", "Brent": "BZ=F", "DXY": "DX-Y.NYB", "US10Y": "^TNX"}},
    }

    report = build_risk_line_backtest_from_config(config, sample_only=True)

    assert report["indicator_count"] == 10
    assert report["data_source"] == "sample"
    assert report["warnings"] == ["stub"]
    assert "time_splits" in report["indicators"]["SPY"]["targets"]["warning_target"]
    assert "walk_forward" in report["indicators"]["SPY"]["targets"]["warning_target"]


def test_write_risk_line_backtest_report_writes_json_and_markdown(monkeypatch):
    def fake_fetch_market_data(**kwargs):
        return FetchResult(prices=_prices(), warnings=[], source="sample", acquisition_log=[], diagnostics={})

    def fake_load_config(_config_path):
        return {
            "paths": {"reports_dir": r"C:\\repo\\project\\reports", "cache_dir": r"C:\\repo\\project\\cache"},
            "data": {"period_years": 10, "interval": "1wk"},
            "tickers": {"risk_indicators": {"SPY": "SPY", "HYG": "HYG", "LQD": "LQD", "VIX": "^VIX", "MOVE": "^MOVE", "WTI": "CL=F", "Brent": "BZ=F", "DXY": "DX-Y.NYB", "US10Y": "^TNX"}},
        }

    writes = {}

    def fake_write_text(self, text, encoding="utf-8"):
        writes[str(self)] = text
        return len(text)

    monkeypatch.setattr("project.risk_line_calibration_report.fetch_market_data", fake_fetch_market_data)
    monkeypatch.setattr("project.risk_line_calibration_report.load_config", fake_load_config)
    monkeypatch.setattr(Path, "write_text", fake_write_text)
    monkeypatch.setattr(Path, "mkdir", lambda self, parents=False, exist_ok=False: None)

    json_path, md_path = write_risk_line_backtest_report("dummy.yaml", sample_only=True)

    assert str(json_path) in writes
    assert str(md_path) in writes
    payload = json.loads(writes[str(json_path)])
    assert payload["indicator_count"] == 10
    assert "Risk Line Model Backtest" in writes[str(md_path)]
    assert "walk_forward_windows" in writes[str(md_path)]
    assert "## ^MOVE" in writes[str(md_path)]
    assert "## CL=F" in writes[str(md_path)]


def test_render_risk_line_backtest_markdown_contains_best_feature():
    report = {
        "data_source": "sample",
        "rows": 100,
        "indicator_count": 1,
        "targets": ["warning_target"],
        "warnings": [],
        "indicators": {
            "SPY": {
                "family": "price_shock",
                "adverse_direction": "lower",
                "rows": 100,
                "targets": {
                    "warning_target": {
                        "candidate_count": 3,
                        "best": {
                            "feature": "roc_2w",
                            "threshold": -0.03,
                            "quantile": 0.2,
                            "precision": 0.5,
                            "recall": 0.6,
                            "f1": 0.55,
                            "false_positive_rate": 0.1,
                            "average_lead_weeks": 2.0,
                        },
                        "time_splits": {"split_count": 2, "average_test_f1": 0.41},
                        "walk_forward": {"window_count": 3, "average_test_f1": 0.38},
                    }
                },
            }
        },
    }

    text = render_risk_line_backtest_markdown(report)

    assert "## SPY" in text
    assert "- best feature: roc_2w" in text
    assert "- split_count: 2 / avg_test_f1: 0.41" in text
    assert "- walk_forward_windows: 3 / avg_test_f1: 0.38" in text
