from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from project.hindenburg_omen import (
    build_hindenburg_omen_context,
    compute_hindenburg_daily_signals,
    import_hindenburg_manual_record,
    parse_hindenburg_breadth_auto_csv,
    parse_hindenburg_breadth_csv,
    summarize_hindenburg_periods,
)
from project.hindenburg_provider import ProviderAttempt, ProviderResult

CSV = """date,new_highs,new_lows,advancers,decliners,nyse_index,mcclellan_oscillator,index_above_50d,source_note
2026-01-02,80,75,1200,1200,10000,-5,true,fixture
2026-01-15,78,76,1200,1200,10100,-10,true,fixture
2026-03-01,82,80,1200,1200,10200,-8,true,fixture
"""


@pytest.fixture(autouse=True)
def isolated_hindenburg_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HINDENBURG_OMEN_DB_PATH", str(tmp_path / "hindenburg.sqlite3"))
    monkeypatch.setenv("HINDENBURG_OMEN_DATA_DIR", str(tmp_path / "hindenburg_data"))

    def no_live_builtin_chain(**_kwargs: object) -> ProviderResult:
        attempts = (
            ProviderAttempt("barchart_market_momentum", "Barchart Market Momentum", "failed", "MANDATORY_FIELD_MISSING"),
            ProviderAttempt("marketwatch_us_market_data", "MarketWatch U.S. Market Data", "failed", "ACCESS_DENIED"),
            ProviderAttempt("wsj_market_diary", "WSJ Markets Diary", "failed", "MANDATORY_FIELD_MISSING"),
        )
        return ProviderResult(
            status="failed",
            provider_id="builtin_provider_chain",
            provider_label="Built-in provider chain",
            failure_code="ALL_PROVIDERS_UNAVAILABLE",
            attempts=attempts,
            limitations=("3候補すべて取得不可",),
        )

    monkeypatch.setattr("project.hindenburg_omen.acquire_builtin_provider_chain", no_live_builtin_chain)


def _derived_mcclellan_csv() -> str:
    lines = ["date,new_highs,new_lows,advancers,decliners,nyse_index,index_above_50d"]
    start = date(2026, 1, 1)
    for offset in range(39):
        current = start + timedelta(days=offset)
        lines.append(f"{current.isoformat()},10,8,1400,1000,{10000 + offset},true")
    lines.append("2026-02-09,80,75,900,1500,10100,true")
    return "\n".join(lines) + "\n"


def test_missing_manual_csv_returns_safe_unavailable(tmp_path: Path) -> None:
    payload = build_hindenburg_omen_context(manual_csv_path=tmp_path / "missing.csv")

    assert payload["status"] == "data_unavailable"
    assert payload["state"] == "UNINITIALIZED"
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


def test_auto_csv_source_is_used_when_manual_csv_is_missing(tmp_path: Path) -> None:
    auto_path = tmp_path / "auto_breadth.csv"
    auto_path.write_text(CSV, encoding="utf-8")

    payload = build_hindenburg_omen_context(
        manual_csv_path=tmp_path / "missing.csv",
        auto_csv_url=auto_path,
        as_of_date="2026-03-01",
    )

    assert payload["status"] == "ok"
    assert payload["source_kind"] == "auto_csv"
    assert payload["source_path"] == str(auto_path)
    assert payload["current_signal"] == "triggered_today"
    assert payload["must_not_affect_final_action"] is True
    assert payload["must_not_affect_buy_readiness_score"] is True


def test_manual_csv_takes_precedence_over_auto_csv(tmp_path: Path) -> None:
    manual_path = tmp_path / "manual.csv"
    auto_path = tmp_path / "auto.csv"
    manual_path.write_text(CSV, encoding="utf-8")
    auto_path.write_text("date,new_highs,new_lows\n2026-01-02,1,1\n", encoding="utf-8")

    payload = build_hindenburg_omen_context(
        manual_csv_path=manual_path,
        auto_csv_url=auto_path,
        as_of_date="2026-03-01",
    )

    assert payload["status"] == "ok"
    assert payload["source_kind"] == "local_manual_file"
    assert payload["source_path"] == str(manual_path)


def test_manual_parse_error_does_not_fall_back_to_auto_csv(tmp_path: Path) -> None:
    manual_path = tmp_path / "manual_bad.csv"
    auto_path = tmp_path / "auto.csv"
    manual_path.write_text("date,new_highs,new_lows\n2026-01-02,1,1\n", encoding="utf-8")
    auto_path.write_text(CSV, encoding="utf-8")

    payload = build_hindenburg_omen_context(
        manual_csv_path=manual_path,
        auto_csv_url=auto_path,
        as_of_date="2026-03-01",
    )

    assert payload["status"] == "parse_error"
    assert payload["source_kind"] == "local_manual_file"
    assert payload["current_signal"] == "unavailable"


def test_auto_csv_parser_reports_fetch_errors() -> None:
    parsed = parse_hindenburg_breadth_auto_csv("Z:/missing/hindenburg_breadth.csv")

    assert parsed["status"] == "auto_fetch_error"
    assert parsed["frame"] is None
    assert parsed["source_kind"] == "auto_csv"


def test_auto_csv_can_derive_mcclellan_from_advance_decline_history(tmp_path: Path) -> None:
    auto_path = tmp_path / "auto_breadth.csv"
    auto_path.write_text(_derived_mcclellan_csv(), encoding="utf-8")

    payload = build_hindenburg_omen_context(
        manual_csv_path=tmp_path / "missing.csv",
        auto_csv_url=auto_path,
        as_of_date="2026-02-09",
    )

    assert payload["status"] == "ok"
    assert payload["source_kind"] == "auto_csv"
    assert payload["current_signal"] == "triggered_today"
    assert payload["mcclellan_oscillator"] is not None
    assert payload["mcclellan_oscillator"] < 0
    assert "negative_mcclellan" in payload["criteria_passed"]
    assert any("内部算出" in item for item in payload["limitations"])


def test_parser_reports_missing_required_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("date,new_highs,new_lows\n2026-01-02,10,10\n", encoding="utf-8")

    parsed = parse_hindenburg_breadth_csv(path)

    assert parsed["status"] == "parse_error"
    assert "必須列不足" in parsed["limitations"][0]


def test_template_sample_rows_are_not_imported() -> None:
    parsed = parse_hindenburg_breadth_csv("project/manual_sources/hindenburg_breadth_template.csv")

    assert parsed["status"] == "parse_error"
    assert parsed["failure_code"] == "TEMPLATE_SAMPLE_ROW"


def test_manual_daily_input_validates_and_records_manual_source(tmp_path: Path) -> None:
    db_path = tmp_path / "hindenburg.sqlite3"

    payload = import_hindenburg_manual_record(
        market_date="2026-01-02",
        new_highs=20,
        new_lows=18,
        advancers=1200,
        decliners=1100,
        total_issues=2500,
        nyse_index=10000,
        index_50d_ago=9900,
        db_path=db_path,
    )

    assert payload["source_kind"] == "manual_daily_input"
    assert payload["state"] == "INSUFFICIENT_HISTORY"
    assert payload["history_progress_label"] == "蓄積履歴: 1 / 39営業日"
    assert payload["current_signal"] == "unconfirmed"
    assert payload["current_signal"] != "not_triggered"


def test_manual_daily_input_rejects_negative_value(tmp_path: Path) -> None:
    payload = import_hindenburg_manual_record(
        market_date="2026-01-02",
        new_highs=-1,
        new_lows=18,
        advancers=1200,
        decliners=1100,
        db_path=tmp_path / "hindenburg.sqlite3",
    )

    assert payload["state"] == "INVALID_DATA"
    assert payload["current_signal"] == "unavailable"


def test_manual_daily_input_idempotent_and_conflict_detection(tmp_path: Path) -> None:
    db_path = tmp_path / "hindenburg.sqlite3"
    kwargs = {
        "market_date": "2026-01-02",
        "new_highs": 20,
        "new_lows": 18,
        "advancers": 1200,
        "decliners": 1100,
        "db_path": db_path,
    }
    first = import_hindenburg_manual_record(**kwargs)
    second = import_hindenburg_manual_record(**kwargs)
    conflict = import_hindenburg_manual_record(**{**kwargs, "new_highs": 21})

    assert first["history_progress_label"] == "蓄積履歴: 1 / 39営業日"
    assert second["history_progress_label"] == "蓄積履歴: 1 / 39営業日"
    assert conflict["state"] == "INVALID_DATA"
    assert conflict["is_previous_confirmed_result"] is True


def test_manual_daily_input_reaches_minimum_history(tmp_path: Path) -> None:
    db_path = tmp_path / "hindenburg.sqlite3"
    start = date(2026, 1, 1)
    payload = {}
    for offset in range(39):
        current = start + timedelta(days=offset)
        payload = import_hindenburg_manual_record(
            market_date=current.isoformat(),
            new_highs=10,
            new_lows=8,
            advancers=1400,
            decliners=1000,
            nyse_index=10000 + offset,
            index_50d_ago=9900,
            db_path=db_path,
        )

    assert payload["stored_valid_record_count"] == 39
    assert payload["minimum_required_record_count"] == 39
    assert payload["state"] == "CONFIRMED"
    assert payload["history_complete"] is True


def test_all_criteria_pass_triggers_and_builds_active_period(tmp_path: Path) -> None:
    path = tmp_path / "hindenburg_breadth.csv"
    path.write_text(CSV, encoding="utf-8")

    payload = build_hindenburg_omen_context(manual_csv_path=path, as_of_date="2026-03-01")

    assert payload["status"] == "ok"
    assert payload["current_signal"] == "triggered_today"
    assert payload["current_signal_level"] == "active"
    assert payload["data_latest_date"] == "2026-03-01"
    assert payload["as_of_date"] == "2026-03-01"
    assert payload["stale_data"] is False
    assert payload["is_active_as_of_latest_data"] is True
    assert payload["is_currently_active"] is True
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

    payload = build_hindenburg_omen_context(manual_csv_path=path, as_of_date="2026-01-02")

    assert payload["current_signal"] == "not_triggered"
    assert "new_highs_threshold" in payload["criteria_failed"]
    assert payload["trigger_dates"] == []


def test_missing_mcclellan_or_uptrend_prevents_confirmed_signal(tmp_path: Path) -> None:
    path = tmp_path / "hindenburg_breadth.csv"
    path.write_text(
        "date,new_highs,new_lows,advancers,decliners,nyse_index\n" "2026-01-02,20,18,1200,1200,10000\n",
        encoding="utf-8",
    )

    payload = build_hindenburg_omen_context(manual_csv_path=path, as_of_date="2026-01-02")

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

    payload = build_hindenburg_omen_context(manual_csv_path=path, as_of_date="2026-01-02")

    assert payload["current_signal"] == "not_triggered"
    assert "high_low_balance" in payload["criteria_failed"]


def test_stale_csv_does_not_report_confident_current_active_signal(tmp_path: Path) -> None:
    path = tmp_path / "hindenburg_breadth.csv"
    path.write_text(CSV, encoding="utf-8")

    payload = build_hindenburg_omen_context(manual_csv_path=path, as_of_date="2026-03-20")

    assert payload["status"] == "ok"
    assert payload["data_latest_date"] == "2026-03-01"
    assert payload["as_of_date"] == "2026-03-20"
    assert payload["latest_trigger_date"] == "2026-03-01"
    assert payload["active_until"] == "2026-03-31"
    assert payload["is_active_as_of_latest_data"] is True
    assert payload["is_currently_active"] is False
    assert payload["stale_data"] is True
    assert payload["current_signal"] == "unconfirmed"
    assert any("市場幅CSVの最新日が古い" in item for item in payload["limitations"])


def test_invalid_negative_or_zero_breadth_values_are_parse_errors(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "date,new_highs,new_lows,advancers,decliners,nyse_index,mcclellan_oscillator,index_above_50d\n"
        "2026-01-02,-1,18,0,0,10000,-5,true\n",
        encoding="utf-8",
    )

    payload = build_hindenburg_omen_context(manual_csv_path=path, as_of_date="2026-01-02")

    assert payload["status"] == "parse_error"
    assert payload["current_signal"] == "unavailable"
    assert payload["trigger_dates"] == []
    assert any("new_highs が負の値" in item for item in payload["limitations"])
    assert any("advancers+decliners が0以下" in item for item in payload["limitations"])


def test_invalid_total_issues_or_non_numeric_values_are_parse_errors(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "date,new_highs,new_lows,advancers,decliners,total_issues,nyse_index,mcclellan_oscillator,index_above_50d\n"
        "2026-01-02,120,18,60,50,100,10000,not-a-number,true\n",
        encoding="utf-8",
    )

    parsed = parse_hindenburg_breadth_csv(path)

    assert parsed["status"] == "parse_error"
    assert parsed["frame"] is None
    assert any("new_highs が total_issues を超えています" in item for item in parsed["limitations"])
    assert any("mcclellan_oscillator が数値ではありません" in item for item in parsed["limitations"])


def test_invalid_date_is_parse_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "date,new_highs,new_lows,advancers,decliners,nyse_index,mcclellan_oscillator,index_above_50d\n"
        "not-a-date,20,18,1200,1200,10000,-5,true\n",
        encoding="utf-8",
    )

    parsed = parse_hindenburg_breadth_csv(path)

    assert parsed["status"] == "parse_error"
    assert parsed["frame"] is None
    assert any("date列" in item for item in parsed["limitations"])


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
