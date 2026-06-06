from __future__ import annotations

from pathlib import Path

from project.hindenburg_omen import (
    build_hindenburg_omen_context,
    compute_hindenburg_daily_signals,
    parse_hindenburg_breadth_csv,
    summarize_hindenburg_periods,
)

CSV = """date,new_highs,new_lows,advancers,decliners,nyse_index,mcclellan_oscillator,index_above_50d,source_note
2026-01-02,80,75,1200,1200,10000,-5,true,fixture
2026-01-15,78,76,1200,1200,10100,-10,true,fixture
2026-03-01,82,80,1200,1200,10200,-8,true,fixture
"""


def test_missing_manual_csv_returns_safe_unavailable(tmp_path: Path) -> None:
    payload = build_hindenburg_omen_context(manual_csv_path=tmp_path / "missing.csv")

    assert payload["status"] == "manual_file_missing"
    assert payload["current_signal"] == "unavailable"
    assert payload["is_currently_active"] is False
    assert payload["trigger_dates"] == []
    assert payload["must_not_affect_final_action"] is True
    assert payload["must_not_affect_buy_readiness_score"] is True


def test_parser_accepts_valid_manual_csv(tmp_path: Path) -> None:
    path = tmp_path / "hindenburg_breadth.csv"
    path.write_text(CSV, encoding="utf-8")

    parsed = parse_hindenburg_breadth_csv(path)

    assert parsed["status"] == "ok"
    assert parsed["source_kind"] == "local_manual_file"
    assert len(parsed["frame"]) == 3


def test_parser_reports_missing_required_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("date,new_highs,new_lows\n2026-01-02,10,10\n", encoding="utf-8")

    parsed = parse_hindenburg_breadth_csv(path)

    assert parsed["status"] == "parse_error"
    assert "必須列不足" in parsed["limitations"][0]


def test_all_criteria_pass_triggers_and_builds_active_period(tmp_path: Path) -> None:
    path = tmp_path / "hindenburg_breadth.csv"
    path.write_text(CSV, encoding="utf-8")

    payload = build_hindenburg_omen_context(manual_csv_path=path)

    assert payload["status"] == "ok"
    assert payload["current_signal"] == "triggered_today"
    assert payload["current_signal_level"] == "active"
    assert payload["latest_trigger_date"] == "2026-03-01"
    assert payload["active_until"] == "2026-03-31"
    assert payload["trigger_dates"] == ["2026-01-02", "2026-01-15", "2026-03-01"]
    assert payload["active_periods"] == [
        {
            "period_start": "2026-01-02",
            "period_end": "2026-02-14",
            "trigger_day_count": 2,
            "latest_trigger_date": "2026-01-15",
        },
        {
            "period_start": "2026-03-01",
            "period_end": "2026-03-31",
            "trigger_day_count": 1,
            "latest_trigger_date": "2026-03-01",
        },
    ]


def test_period_summary_extends_and_starts_new_period() -> None:
    periods = summarize_hindenburg_periods(["2026-01-01", "2026-01-15", "2026-03-01"], active_window_days=30)

    assert periods[0]["period_start"] == "2026-01-01"
    assert periods[0]["period_end"] == "2026-02-14"
    assert periods[0]["trigger_day_count"] == 2
    assert periods[1]["period_start"] == "2026-03-01"


def test_threshold_failures_do_not_trigger(tmp_path: Path) -> None:
    path = tmp_path / "hindenburg_breadth.csv"
    path.write_text(
        "date,new_highs,new_lows,advancers,decliners,nyse_index,mcclellan_oscillator,index_above_50d\n"
        "2026-01-02,2,18,1200,1200,10000,-5,true\n",
        encoding="utf-8",
    )

    payload = build_hindenburg_omen_context(manual_csv_path=path)

    assert payload["current_signal"] == "not_triggered"
    assert "new_highs_threshold" in payload["criteria_failed"]
    assert payload["trigger_dates"] == []


def test_missing_mcclellan_or_uptrend_prevents_confirmed_signal(tmp_path: Path) -> None:
    path = tmp_path / "hindenburg_breadth.csv"
    path.write_text(
        "date,new_highs,new_lows,advancers,decliners,nyse_index\n" "2026-01-02,20,18,1200,1200,10000\n",
        encoding="utf-8",
    )

    payload = build_hindenburg_omen_context(manual_csv_path=path)

    assert payload["status"] == "partial"
    assert payload["current_signal"] == "unconfirmed"
    assert "negative_mcclellan" in payload["criteria_unknown"]
    assert "uptrend" in payload["criteria_unknown"]
    assert payload["trigger_dates"] == []


def test_high_low_balance_rule_blocks_fake_trigger(tmp_path: Path) -> None:
    path = tmp_path / "hindenburg_breadth.csv"
    path.write_text(
        "date,new_highs,new_lows,advancers,decliners,nyse_index,mcclellan_oscillator,index_above_50d\n"
        "2026-01-02,60,20,1200,1200,10000,-5,true\n",
        encoding="utf-8",
    )

    payload = build_hindenburg_omen_context(manual_csv_path=path)

    assert payload["current_signal"] == "not_triggered"
    assert "high_low_balance" in payload["criteria_failed"]


def test_compute_daily_signals_does_not_infer_from_etf_like_missing_data(tmp_path: Path) -> None:
    path = tmp_path / "hindenburg_breadth.csv"
    path.write_text(
        "date,new_highs,new_lows,advancers,decliners\n" "2026-01-02,20,18,1200,1200\n",
        encoding="utf-8",
    )
    parsed = parse_hindenburg_breadth_csv(path)

    rows = compute_hindenburg_daily_signals(parsed["frame"])

    assert rows[0]["triggered"] is False
    assert rows[0]["criteria"]["uptrend"]["state"] == "unknown"
    assert rows[0]["criteria"]["negative_mcclellan"]["state"] == "unknown"
