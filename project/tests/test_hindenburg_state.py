from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from project.hindenburg_omen import build_hindenburg_omen_context
from project.hindenburg_provider import ProviderAttempt, ProviderResult
from project.hindenburg_store import (
    RESET_CONFIRMATION_PHRASE,
    connect_hindenburg_store,
    reset_hindenburg_local_state,
    sqlite_integrity_check,
)

CSV = """date,new_highs,new_lows,advancers,decliners,nyse_index,mcclellan_oscillator,index_above_50d
2026-01-02,80,75,1200,1200,10000,-5,true
2026-01-15,78,76,1200,1200,10100,-10,true
2026-03-01,82,80,1200,1200,10200,-8,true
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


def test_sqlite_bootstrap_reopen_and_repeated_import_are_idempotent(tmp_path: Path) -> None:
    csv_path = tmp_path / "hindenburg.csv"
    db_path = tmp_path / "hindenburg.sqlite3"
    csv_path.write_text(CSV, encoding="utf-8")

    first = build_hindenburg_omen_context(manual_csv_path=csv_path, db_path=db_path, as_of_date="2026-03-01")
    second = build_hindenburg_omen_context(manual_csv_path=csv_path, db_path=db_path, as_of_date="2026-03-01")

    assert first["state"] == "CONFIRMED"
    assert second["state"] == "CONFIRMED"
    assert second["confirmed_market_date"] == "2026-03-01"

    with sqlite3.connect(db_path) as conn:
        input_count = conn.execute("SELECT COUNT(*) FROM hindenburg_normalized_inputs").fetchone()[0]
        result_count = conn.execute("SELECT COUNT(*) FROM hindenburg_daily_results").fetchone()[0]
    assert input_count == 3
    assert result_count == 3

    reopened = connect_hindenburg_store(db_path)
    try:
        assert sqlite_integrity_check(reopened) == "ok"
    finally:
        reopened.close()


def test_conflicting_correction_preserves_previous_confirmed_result(tmp_path: Path) -> None:
    csv_path = tmp_path / "hindenburg.csv"
    db_path = tmp_path / "hindenburg.sqlite3"
    csv_path.write_text(CSV, encoding="utf-8")
    confirmed = build_hindenburg_omen_context(manual_csv_path=csv_path, db_path=db_path, as_of_date="2026-03-01")

    csv_path.write_text(CSV.replace("2026-01-15,78,76", "2026-01-15,79,76"), encoding="utf-8")
    failed = build_hindenburg_omen_context(manual_csv_path=csv_path, db_path=db_path, as_of_date="2026-03-01")

    assert confirmed["current_signal"] == "triggered_today"
    assert failed["state"] == "INVALID_DATA"
    assert failed["is_previous_confirmed_result"] is True
    assert failed["current_signal"] == confirmed["current_signal"]
    assert "CONFLICTING_CORRECTION" in failed["failure_code"]


def test_gap_blocked_preserves_previous_confirmed_result(tmp_path: Path) -> None:
    csv_path = tmp_path / "hindenburg.csv"
    db_path = tmp_path / "hindenburg.sqlite3"
    csv_path.write_text(CSV, encoding="utf-8")
    confirmed = build_hindenburg_omen_context(manual_csv_path=csv_path, db_path=db_path, as_of_date="2026-03-01")

    csv_path.write_text(
        "date,new_highs,new_lows,advancers,decliners,nyse_index,mcclellan_oscillator,index_above_50d\n"
        "2026-03-10,90,85,1200,1200,10300,-6,true\n",
        encoding="utf-8",
    )
    failed = build_hindenburg_omen_context(manual_csv_path=csv_path, db_path=db_path, as_of_date="2026-03-10")

    assert confirmed["confirmed_market_date"] == "2026-03-01"
    assert failed["state"] == "GAP_BLOCKED"
    assert failed["is_previous_confirmed_result"] is True
    assert failed["confirmed_market_date"] == "2026-03-01"


def test_update_failure_without_previous_result_is_not_not_triggered(tmp_path: Path) -> None:
    payload = build_hindenburg_omen_context(manual_csv_path=tmp_path / "missing.csv", db_path=tmp_path / "hindenburg.sqlite3")

    assert payload["state"] == "UNINITIALIZED"
    assert payload["current_signal"] == "unavailable"
    assert payload["current_signal"] != "not_triggered"
    assert payload["failure_code"] == "ALL_PROVIDERS_UNAVAILABLE"
    assert len(payload["provider_attempts"]) == 3


def test_all_provider_failure_preserves_previous_confirmed_result(tmp_path: Path) -> None:
    csv_path = tmp_path / "hindenburg.csv"
    db_path = tmp_path / "hindenburg.sqlite3"
    csv_path.write_text(CSV, encoding="utf-8")
    confirmed = build_hindenburg_omen_context(manual_csv_path=csv_path, db_path=db_path, as_of_date="2026-03-01")

    failed = build_hindenburg_omen_context(manual_csv_path=tmp_path / "missing.csv", db_path=db_path, as_of_date="2026-03-02")

    assert confirmed["state"] == "CONFIRMED"
    assert failed["state"] == "UPDATE_FAILED"
    assert failed["failure_code"] == "ALL_PROVIDERS_UNAVAILABLE"
    assert failed["is_previous_confirmed_result"] is True
    assert failed["confirmed_market_date"] == "2026-03-01"
    assert failed["current_signal"] == confirmed["current_signal"]


def test_builtin_auto_attempt_runs_once_per_expected_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "hindenburg.sqlite3"
    call_count = 0

    def counted_chain(**_kwargs: object) -> ProviderResult:
        nonlocal call_count
        call_count += 1
        return ProviderResult(
            status="failed",
            provider_id="builtin_provider_chain",
            provider_label="Built-in provider chain",
            failure_code="ALL_PROVIDERS_UNAVAILABLE",
            attempts=(ProviderAttempt("barchart_market_momentum", "Barchart Market Momentum", "failed", "MANDATORY_FIELD_MISSING"),),
            limitations=("3候補すべて取得不可",),
        )

    monkeypatch.setattr("project.hindenburg_omen.acquire_builtin_provider_chain", counted_chain)

    first = build_hindenburg_omen_context(manual_csv_path=tmp_path / "missing.csv", db_path=db_path, as_of_date="2026-03-03")
    second = build_hindenburg_omen_context(manual_csv_path=tmp_path / "missing.csv", db_path=db_path, as_of_date="2026-03-03")
    third = build_hindenburg_omen_context(manual_csv_path=tmp_path / "missing.csv", db_path=db_path, as_of_date="2026-03-04")

    assert call_count == 2
    assert first["automatic_acquisition"]["attempted"] is True
    assert second["automatic_acquisition"]["attempted"] is False
    assert second["automatic_acquisition"]["reason"] == "ALREADY_ATTEMPTED_FOR_SESSION"
    assert third["automatic_acquisition"]["attempted"] is True


def test_builtin_auto_attempt_can_be_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_chain(**_kwargs: object) -> ProviderResult:
        raise AssertionError("provider chain should not be called")

    monkeypatch.setattr("project.hindenburg_omen.acquire_builtin_provider_chain", unexpected_chain)

    payload = build_hindenburg_omen_context(
        manual_csv_path=tmp_path / "missing.csv",
        db_path=tmp_path / "hindenburg.sqlite3",
        experimental_builtin_auto_fetch=False,
    )

    assert payload["automatic_acquisition"]["attempted"] is False
    assert payload["automatic_acquisition"]["reason"] == "AUTO_DISABLED"


def test_reset_requires_confirmation_and_creates_backup(tmp_path: Path) -> None:
    db_path = tmp_path / "hindenburg.sqlite3"
    csv_path = tmp_path / "hindenburg.csv"
    csv_path.write_text(CSV, encoding="utf-8")
    build_hindenburg_omen_context(manual_csv_path=csv_path, db_path=db_path, as_of_date="2026-03-01")

    denied = reset_hindenburg_local_state(db_path, confirmation="wrong")
    result = reset_hindenburg_local_state(db_path, confirmation=RESET_CONFIRMATION_PHRASE, backup_dir=tmp_path / "backups")

    assert denied["status"] == "confirmation_required"
    assert result["status"] == "ok"
    assert result["backup_path"]
    assert Path(str(result["backup_path"])).exists()
    reopened = connect_hindenburg_store(db_path)
    try:
        assert sqlite_integrity_check(reopened) == "ok"
    finally:
        reopened.close()
