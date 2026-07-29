from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from project.pipeline import collect_tickers, load_risk_engine_v2_episode_chronicle_summary, resample_weekly_closes


def test_resample_weekly_closes_drops_incomplete_future_week_label_before_ffill() -> None:
    prices = pd.DataFrame(
        {
            "2510.T": {
                pd.Timestamp("2026-05-22"): 806.0,
                pd.Timestamp("2026-05-29"): 809.1,
                pd.Timestamp("2026-06-05"): 810.8,
                pd.Timestamp("2026-06-12"): 814.6,
                pd.Timestamp("2026-06-19"): 813.7,
                pd.Timestamp("2026-06-20"): None,
            },
            "USDJPY=X": {
                pd.Timestamp("2026-06-20"): 161.2749,
            },
        }
    ).sort_index()

    weekly = resample_weekly_closes(prices)

    assert weekly.index[-1] == pd.Timestamp("2026-06-19")
    assert pd.Timestamp("2026-06-26") not in weekly.index
    assert weekly["2510.T"].dropna().iloc[-5] == 806.0


def test_collect_tickers_includes_risk_engine_official_series() -> None:
    config = {
        "tickers": {"risk_indicators": {"SPY": "SPY"}, "asset_classes": {"ACWI": "ACWI"}},
        "risk_engine_v2": {
            "official_series": {
                "credit_hy_oas": "FRED:BAMLH0A0HYM2",
                "financial_conditions": "FRED:NFCI",
            }
        },
    }

    tickers = collect_tickers(config)

    assert tickers == ["SPY", "ACWI", "FRED:BAMLH0A0HYM2", "FRED:NFCI"]


def test_load_episode_chronicle_summary_is_fail_closed(tmp_path: Path) -> None:
    assert load_risk_engine_v2_episode_chronicle_summary(tmp_path)["status"] == "not_available"
    path = tmp_path / "risk_engine_v2_episode_chronicle.json"
    path.write_text("{broken", encoding="utf-8")
    assert load_risk_engine_v2_episode_chronicle_summary(tmp_path)["status"] == "unavailable"

    payload = {
        "schema_version": "risk_engine_v2.episode_chronicle.v1",
        "implementation_version": "risk_engine_v2.episode_chronicle.implementation.v3",
        "generation_id": "fixture",
        "generated_at": "2026-07-19T00:00:00+00:00",
        "status": "ready",
        "freshness_status": "current",
        "policy_status": "diagnostic_only_not_promoted",
        "affects_final_action": False,
        "promotion_allowed": False,
        "page_filename": "risk_engine_v2_episode_chronicle.html",
        "summary": {
            "episode_count": 18,
            "mature_count": 16,
            "pending_count": 2,
            "latest_event_id": "event-latest",
            "latest_event_title": "2026年7月17日 — 警戒局面",
            "latest_event_date": "2026-07-17",
        },
        "decision": {"promotion_allowed": False},
        "contract": {"status": "pass"},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    invalid = load_risk_engine_v2_episode_chronicle_summary(tmp_path)
    assert invalid["status"] == "invalid"
    assert "page_file" in invalid["reason"]

    (tmp_path / str(payload["page_filename"])).write_text("<!doctype html>", encoding="utf-8")
    summary = load_risk_engine_v2_episode_chronicle_summary(tmp_path)
    assert summary["status"] == "ready"
    assert summary["episode_count"] == 18
    assert summary["promotion_allowed"] is False

    payload["freshness_status"] = "historical"
    path.write_text(json.dumps(payload), encoding="utf-8")
    historical = load_risk_engine_v2_episode_chronicle_summary(tmp_path)
    assert historical["status"] == "ready"
    assert historical["freshness_status"] == "historical"
