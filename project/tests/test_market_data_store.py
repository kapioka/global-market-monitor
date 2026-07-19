from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from project.market_data_store import (
    BackupError,
    IngestionConflictError,
    MarketDataStoreError,
    MarketDataValidationError,
    ObservationInput,
    SchemaMigrationError,
    SeriesDefinition,
    SeriesDefinitionConflictError,
    StoreBusyError,
    UnsupportedSchemaVersionError,
    backup_market_data_store,
    check_integrity,
    connect_market_data_store,
    connect_market_data_store_read_only,
    ingest_observations,
    load_current_frame,
    load_frame_as_of,
    restore_market_data_backup,
)


def _series(series_id: str = "ACWI") -> SeriesDefinition:
    return SeriesDefinition(
        series_id=series_id,
        source_id=series_id,
        source_type="fixture",
        frequency="business_daily",
        value_kind="adjusted_close",
        metadata={"fixture": True},
    )


def _ingest(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    observed_at: str,
    fingerprint: str,
    values: list[ObservationInput],
    definitions: list[SeriesDefinition] | None = None,
):
    return ingest_observations(
        conn,
        run_id=run_id,
        observed_at=observed_at,
        source="fixture",
        input_fingerprint=fingerprint,
        series_definitions=definitions if definitions is not None else [_series()],
        observations=values,
    )


def test_schema_creation_reopen_and_future_version_rejection_are_fail_closed(tmp_path: Path) -> None:
    db_path = tmp_path / "market.sqlite3"
    conn = connect_market_data_store(db_path, app_version="test")
    try:
        assert check_integrity(conn) == "ok"
        assert conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()[0] == 1
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        assert {"series", "ingestion_runs", "observations", "artifact_registry"} <= tables
    finally:
        conn.close()

    before = db_path.read_bytes()
    reopened = connect_market_data_store(db_path)
    reopened.close()
    assert db_path.read_bytes() == before

    future_path = tmp_path / "future.sqlite3"
    with sqlite3.connect(future_path) as future:
        future.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT, app_version TEXT)")
        future.execute("INSERT INTO schema_migrations VALUES (999, '2026-07-19T00:00:00+00:00', 'future')")
    future_hash = hashlib.sha256(future_path.read_bytes()).hexdigest()
    with pytest.raises(UnsupportedSchemaVersionError):
        connect_market_data_store(future_path)
    assert hashlib.sha256(future_path.read_bytes()).hexdigest() == future_hash

    incomplete_path = tmp_path / "incomplete.sqlite3"
    with sqlite3.connect(incomplete_path) as incomplete:
        incomplete.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT, app_version TEXT)")
        incomplete.execute("INSERT INTO schema_migrations VALUES (1, '2026-07-19T00:00:00+00:00', 'broken')")
    incomplete_hash = hashlib.sha256(incomplete_path.read_bytes()).hexdigest()
    with pytest.raises(SchemaMigrationError, match="schema is incomplete"):
        connect_market_data_store(incomplete_path)
    assert hashlib.sha256(incomplete_path.read_bytes()).hexdigest() == incomplete_hash

    unrelated_path = tmp_path / "unrelated.sqlite3"
    with sqlite3.connect(unrelated_path) as unrelated:
        unrelated.execute("CREATE TABLE user_owned(value TEXT)")
        unrelated.execute("INSERT INTO user_owned VALUES ('preserve-me')")
    unrelated_hash = hashlib.sha256(unrelated_path.read_bytes()).hexdigest()
    with pytest.raises(SchemaMigrationError, match="not a recognized"):
        connect_market_data_store(unrelated_path)
    assert hashlib.sha256(unrelated_path.read_bytes()).hexdigest() == unrelated_hash
    with sqlite3.connect(unrelated_path) as unrelated:
        tables = {row[0] for row in unrelated.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"user_owned"}

    empty_migrations_path = tmp_path / "empty-migrations.sqlite3"
    with sqlite3.connect(empty_migrations_path) as empty_migrations:
        empty_migrations.execute("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT, app_version TEXT)")
    empty_migrations_hash = hashlib.sha256(empty_migrations_path.read_bytes()).hexdigest()
    with pytest.raises(SchemaMigrationError, match="not a recognized"):
        connect_market_data_store(empty_migrations_path)
    assert hashlib.sha256(empty_migrations_path.read_bytes()).hexdigest() == empty_migrations_hash


def test_schema_creation_uses_exclusive_file_reservation(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "creation-race.sqlite3"
    real_open = os.open

    def competing_open(path, flags, mode=0o777):
        if Path(path) == db_path and flags & os.O_EXCL:
            with sqlite3.connect(db_path) as competing:
                competing.execute("CREATE TABLE other_owner(value TEXT)")
                competing.execute("INSERT INTO other_owner VALUES ('preserve-me')")
            raise FileExistsError(str(db_path))
        return real_open(path, flags, mode)

    monkeypatch.setattr(os, "open", competing_open)
    with pytest.raises(SchemaMigrationError, match="not a recognized"):
        connect_market_data_store(db_path)
    with sqlite3.connect(db_path) as competing:
        assert competing.execute("SELECT value FROM other_owner").fetchone()[0] == "preserve-me"


def test_schema_migration_failure_rolls_back_every_created_object(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "migration-failure.sqlite3"

    def fail_after_first_object(conn: sqlite3.Connection) -> None:
        conn.execute("CREATE TABLE partial_object(id INTEGER)")
        raise RuntimeError("injected migration failure")

    monkeypatch.setattr("project.market_data_store._apply_schema_v1", fail_after_first_object)
    with pytest.raises(SchemaMigrationError):
        connect_market_data_store(db_path)
    with sqlite3.connect(db_path) as conn:
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "partial_object" not in names


def test_read_only_connection_does_not_create_wal_or_shm_sidecars(tmp_path: Path) -> None:
    db_path = tmp_path / "market.sqlite3"
    conn = connect_market_data_store(db_path)
    conn.close()
    assert not Path(f"{db_path}-wal").exists()
    assert not Path(f"{db_path}-shm").exists()

    read_only = connect_market_data_store_read_only(db_path)
    try:
        assert check_integrity(read_only) == "ok"
    finally:
        read_only.close()

    assert not Path(f"{db_path}-wal").exists()
    assert not Path(f"{db_path}-shm").exists()


def test_ingestion_is_idempotent_and_preserves_revision_history_and_as_of(tmp_path: Path) -> None:
    conn = connect_market_data_store(tmp_path / "market.sqlite3")
    try:
        first = _ingest(
            conn,
            run_id="run-1",
            observed_at="2026-07-18T00:00:00+00:00",
            fingerprint="fingerprint-1",
            values=[ObservationInput("ACWI", "2026-07-17", 100.0)],
        )
        repeated = _ingest(
            conn,
            run_id="run-1-repeated",
            observed_at="2026-07-18T01:00:00+00:00",
            fingerprint="fingerprint-1",
            values=[ObservationInput("ACWI", "2026-07-17", 100.0)],
        )
        same_value = _ingest(
            conn,
            run_id="run-2",
            observed_at="2026-07-18T02:00:00+00:00",
            fingerprint="fingerprint-2",
            values=[ObservationInput("ACWI", "2026-07-17", 100.0)],
        )
        revised = _ingest(
            conn,
            run_id="run-3",
            observed_at="2026-07-18T03:00:00+00:00",
            fingerprint="fingerprint-3",
            values=[ObservationInput("ACWI", "2026-07-17", 101.0)],
        )
        reverted = _ingest(
            conn,
            run_id="run-4",
            observed_at="2026-07-18T04:00:00+00:00",
            fingerprint="fingerprint-4",
            values=[ObservationInput("ACWI", "2026-07-17", 100.0), ObservationInput("ACWI", "2026-07-18", None)],
        )

        assert first.inserted_count == 1
        assert repeated.status == "no_change"
        assert repeated.run_id == "run-1"
        assert same_value.unchanged_count == 1
        assert revised.revised_count == 1
        assert reverted.revised_count == 1
        assert reverted.skipped_missing_count == 1
        history = conn.execute("SELECT revision, value FROM observations WHERE series_id = 'ACWI' ORDER BY revision").fetchall()
        assert [(row["revision"], row["value"]) for row in history] == [(1, 100.0), (2, 101.0), (3, 100.0)]
        assert load_current_frame(conn).loc[pd.Timestamp("2026-07-17"), "ACWI"] == 100.0
        assert load_frame_as_of(conn, observed_at="2026-07-18T02:30:00+00:00").loc[pd.Timestamp("2026-07-17"), "ACWI"] == 100.0
        assert load_frame_as_of(conn, observed_at="2026-07-18T03:30:00+00:00").loc[pd.Timestamp("2026-07-17"), "ACWI"] == 101.0
    finally:
        conn.close()


def test_batch_conflict_and_invalid_values_write_nothing(tmp_path: Path) -> None:
    conn = connect_market_data_store(tmp_path / "market.sqlite3")
    try:
        with pytest.raises(IngestionConflictError):
            _ingest(
                conn,
                run_id="conflict",
                observed_at="2026-07-19T00:00:00+00:00",
                fingerprint="conflict",
                values=[
                    ObservationInput("ACWI", "2026-07-18", 100.0),
                    ObservationInput("ACWI", "2026-07-18", 101.0),
                ],
            )
        with pytest.raises(MarketDataValidationError):
            _ingest(
                conn,
                run_id="nan",
                observed_at="2026-07-19T00:00:00+00:00",
                fingerprint="nan",
                values=[ObservationInput("ACWI", "2026-07-18", float("nan"))],
            )
        with pytest.raises(MarketDataValidationError):
            _ingest(
                conn,
                run_id="future",
                observed_at="2026-07-19T00:00:00+00:00",
                fingerprint="future",
                values=[ObservationInput("ACWI", "2026-07-20", 100.0)],
            )
        with pytest.raises(MarketDataValidationError, match="timezone"):
            _ingest(
                conn,
                run_id="naive",
                observed_at="2026-07-19T00:00:00",
                fingerprint="naive",
                values=[],
            )
        assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0] == 0
    finally:
        conn.close()


def test_changed_revision_cannot_move_current_backwards_in_observed_time(tmp_path: Path) -> None:
    conn = connect_market_data_store(tmp_path / "market.sqlite3")
    try:
        _ingest(
            conn,
            run_id="newer",
            observed_at="2026-07-19T04:00:00+00:00",
            fingerprint="newer",
            values=[ObservationInput("ACWI", "2026-07-17", 101.0)],
        )
        with pytest.raises(IngestionConflictError, match="not newer"):
            _ingest(
                conn,
                run_id="older",
                observed_at="2026-07-19T03:00:00+00:00",
                fingerprint="older",
                values=[ObservationInput("ACWI", "2026-07-17", 100.0)],
            )
        with pytest.raises(IngestionConflictError, match="not newer"):
            _ingest(
                conn,
                run_id="same-time",
                observed_at="2026-07-19T04:00:00+00:00",
                fingerprint="same-time",
                values=[ObservationInput("ACWI", "2026-07-17", 102.0)],
            )
        assert load_current_frame(conn).loc[pd.Timestamp("2026-07-17"), "ACWI"] == 101.0
        assert conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0] == 1
    finally:
        conn.close()


def test_definition_conflict_and_mid_transaction_failure_preserve_observations(tmp_path: Path) -> None:
    conn = connect_market_data_store(tmp_path / "market.sqlite3")
    try:
        _ingest(
            conn,
            run_id="seed",
            observed_at="2026-07-19T00:00:00+00:00",
            fingerprint="seed",
            values=[ObservationInput("ACWI", "2026-07-18", 100.0)],
        )
        conflicting = SeriesDefinition("ACWI", "different", "fixture", "daily", "price")
        with pytest.raises(SeriesDefinitionConflictError):
            _ingest(
                conn,
                run_id="definition-conflict",
                observed_at="2026-07-19T01:00:00+00:00",
                fingerprint="definition-conflict",
                values=[ObservationInput("ACWI", "2026-07-18", 101.0)],
                definitions=[conflicting],
            )
        conn.execute(
            """
            CREATE TRIGGER injected_failure BEFORE INSERT ON observations
            WHEN NEW.series_id = 'B' BEGIN SELECT RAISE(ABORT, 'injected'); END
            """
        )
        conn.commit()
        with pytest.raises(MarketDataStoreError):
            _ingest(
                conn,
                run_id="rollback",
                observed_at="2026-07-19T02:00:00+00:00",
                fingerprint="rollback",
                definitions=[_series("A"), _series("B")],
                values=[ObservationInput("A", "2026-07-18", 1.0), ObservationInput("B", "2026-07-18", 2.0)],
            )
        assert conn.execute("SELECT COUNT(*) FROM observations WHERE series_id IN ('A', 'B')").fetchone()[0] == 0
        failed = conn.execute("SELECT status FROM ingestion_runs WHERE run_id = 'rollback'").fetchone()
        assert failed["status"] == "failed"
    finally:
        conn.close()


def test_busy_writer_fails_in_bounded_time_and_recovers(tmp_path: Path) -> None:
    db_path = tmp_path / "market.sqlite3"
    first = connect_market_data_store(db_path, timeout_seconds=0.05)
    second = connect_market_data_store(db_path, timeout_seconds=0.05)
    try:
        first.execute("BEGIN IMMEDIATE")
        with pytest.raises(StoreBusyError):
            _ingest(
                second,
                run_id="busy",
                observed_at="2026-07-19T00:00:00+00:00",
                fingerprint="busy",
                values=[ObservationInput("ACWI", "2026-07-18", 100.0)],
            )
        first.rollback()
        result = _ingest(
            second,
            run_id="after-busy",
            observed_at="2026-07-19T00:00:00+00:00",
            fingerprint="after-busy",
            values=[ObservationInput("ACWI", "2026-07-18", 100.0)],
        )
        assert result.status == "success"
        assert check_integrity(second) == "ok"
    finally:
        first.close()
        second.close()


def test_backup_and_restore_are_verified_and_never_overwrite(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "market.sqlite3"
    backup_path = tmp_path / "backups" / "market.backup.sqlite3"
    restored_path = tmp_path / "restored.sqlite3"
    conn = connect_market_data_store(db_path)
    try:
        _ingest(
            conn,
            run_id="seed",
            observed_at="2026-07-19T00:00:00+00:00",
            fingerprint="seed",
            values=[ObservationInput("ACWI", "2026-07-18", 100.0)],
        )
        assert backup_market_data_store(conn, backup_path) == backup_path
        with pytest.raises(BackupError, match="already exists"):
            backup_market_data_store(conn, backup_path)

        raced_path = tmp_path / "backups" / "raced.sqlite3"

        def inject_race(_source, destination):
            Path(destination).write_bytes(b"other-owner")
            raise FileExistsError(destination)

        with monkeypatch.context() as patcher:
            patcher.setattr("project.market_data_store.os.link", inject_race)
            with pytest.raises(BackupError):
                backup_market_data_store(conn, raced_path)
        assert raced_path.read_bytes() == b"other-owner"
    finally:
        conn.close()

    assert restore_market_data_backup(backup_path, restored_path) == restored_path
    restored = connect_market_data_store(restored_path)
    try:
        assert check_integrity(restored) == "ok"
        assert load_current_frame(restored).loc[pd.Timestamp("2026-07-18"), "ACWI"] == 100.0
    finally:
        restored.close()
    with pytest.raises(BackupError, match="already exists"):
        restore_market_data_backup(backup_path, restored_path)
