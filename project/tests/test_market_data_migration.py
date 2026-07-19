from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from project.market_data_migration import (
    MarketDataMigrationError,
    MigrationParityError,
    MigrationTargetExistsError,
    load_legacy_snapshot,
    migrate_legacy_snapshot,
)
from project.market_data_store import (
    ObservationInput,
    SeriesDefinition,
    check_integrity,
    connect_market_data_store,
    ingest_observations,
    load_current_frame,
)


def _write_snapshot(tmp_path: Path) -> tuple[Path, Path]:
    csv_path = tmp_path / "snapshot.csv"
    metadata_path = tmp_path / "snapshot.json"
    frame = pd.DataFrame(
        {"ACWI": [100.0, 101.5, 99.0], "^VIX": [20.0, float("nan"), 30.0]},
        index=pd.to_datetime(["2026-07-15", "2026-07-16", "2026-07-17"]),
    )
    frame.to_csv(csv_path, encoding="utf-8")
    metadata_path.write_text(
        json.dumps({"observed_at": "2026-07-19T17:14:07", "source": "fixture"}),
        encoding="utf-8",
    )
    return csv_path, metadata_path


def test_migration_round_trip_is_exact_idempotent_and_preserves_source(tmp_path: Path) -> None:
    csv_path, metadata_path = _write_snapshot(tmp_path)
    db_path = tmp_path / "market.sqlite3"
    source_hashes = (hashlib.sha256(csv_path.read_bytes()).hexdigest(), hashlib.sha256(metadata_path.read_bytes()).hexdigest())

    first = migrate_legacy_snapshot(csv_path, metadata_path, db_path=db_path)
    db_hash = hashlib.sha256(db_path.read_bytes()).hexdigest()
    second = migrate_legacy_snapshot(csv_path, metadata_path, db_path=db_path)

    assert first["status"] == "migrated"
    assert second["status"] == "no_change"
    assert second["parity"]["status"] == "pass"
    assert second["parity"]["series_count"] == 2
    assert second["parity"]["wide_row_count"] == 3
    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == db_hash
    assert source_hashes == (
        hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        hashlib.sha256(metadata_path.read_bytes()).hexdigest(),
    )
    conn = connect_market_data_store(db_path)
    try:
        frame = load_current_frame(conn, series_ids=["ACWI", "^VIX"])
        assert check_integrity(conn) == "ok"
        assert pd.isna(frame.loc[pd.Timestamp("2026-07-16"), "^VIX"])
    finally:
        conn.close()


def test_migration_rejects_wrong_hash_and_invalid_or_unreconstructable_input(tmp_path: Path) -> None:
    csv_path, metadata_path = _write_snapshot(tmp_path)
    with pytest.raises(MarketDataMigrationError, match="SHA256"):
        migrate_legacy_snapshot(
            csv_path,
            metadata_path,
            db_path=tmp_path / "wrong-hash.sqlite3",
            expected_csv_sha256="0" * 64,
        )
    assert not (tmp_path / "wrong-hash.sqlite3").exists()

    csv_path.write_text("date,ACWI\n2026-07-17,\n", encoding="utf-8")
    with pytest.raises(MarketDataMigrationError, match="all-missing"):
        load_legacy_snapshot(csv_path, metadata_path)

    csv_path.write_text("date,ACWI\n2026-07-17,100\n2026-07-17,101\n", encoding="utf-8")
    with pytest.raises(MarketDataMigrationError, match="strictly increasing"):
        load_legacy_snapshot(csv_path, metadata_path)

    csv_path.write_text("date,ACWI,ACWI\n2026-07-17,100,101\n", encoding="utf-8")
    with pytest.raises(MarketDataMigrationError, match="unique"):
        load_legacy_snapshot(csv_path, metadata_path)

    for non_finite in ("inf", "-inf"):
        csv_path.write_text(f"date,ACWI\n2026-07-17,{non_finite}\n", encoding="utf-8")
        with pytest.raises(MarketDataMigrationError, match="non-finite"):
            load_legacy_snapshot(csv_path, metadata_path)


def test_parity_failure_never_publishes_candidate_database(tmp_path: Path, monkeypatch) -> None:
    csv_path, metadata_path = _write_snapshot(tmp_path)
    db_path = tmp_path / "market.sqlite3"

    def fail_parity(*_args, **_kwargs):
        raise MigrationParityError("injected parity mismatch")

    monkeypatch.setattr("project.market_data_migration.verify_snapshot_parity", fail_parity)
    with pytest.raises(MigrationParityError, match="injected"):
        migrate_legacy_snapshot(csv_path, metadata_path, db_path=db_path)

    assert not db_path.exists()
    assert not list(tmp_path.glob("*.migration.*"))


def test_publication_race_preserves_the_competing_target(tmp_path: Path, monkeypatch) -> None:
    csv_path, metadata_path = _write_snapshot(tmp_path)
    db_path = tmp_path / "market.sqlite3"

    def inject_race(_source, destination):
        Path(destination).write_bytes(b"other-owner")
        raise FileExistsError(destination)

    monkeypatch.setattr("project.market_data_migration.publish_file_no_clobber", inject_race)
    with pytest.raises(MigrationTargetExistsError, match="appeared during publication"):
        migrate_legacy_snapshot(csv_path, metadata_path, db_path=db_path)
    assert db_path.read_bytes() == b"other-owner"


def test_existing_unrelated_database_is_never_modified(tmp_path: Path) -> None:
    csv_path, metadata_path = _write_snapshot(tmp_path)
    db_path = tmp_path / "existing.sqlite3"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE user_owned(value TEXT)")
        conn.execute("INSERT INTO user_owned VALUES ('preserve-me')")
    before = hashlib.sha256(db_path.read_bytes()).hexdigest()

    with pytest.raises(MigrationTargetExistsError, match="refusing to modify"):
        migrate_legacy_snapshot(csv_path, metadata_path, db_path=db_path)

    assert hashlib.sha256(db_path.read_bytes()).hexdigest() == before
    with sqlite3.connect(db_path) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert tables == {"user_owned"}


def test_existing_migration_parity_rejects_extra_series_or_dates(tmp_path: Path) -> None:
    csv_path, metadata_path = _write_snapshot(tmp_path)
    db_path = tmp_path / "market.sqlite3"
    migrate_legacy_snapshot(csv_path, metadata_path, db_path=db_path)
    conn = connect_market_data_store(db_path)
    try:
        ingest_observations(
            conn,
            run_id="extra",
            observed_at="2026-07-20T00:00:00+00:00",
            source="fixture",
            input_fingerprint="extra",
            series_definitions=[SeriesDefinition("EXTRA", "EXTRA", "fixture", "daily", "value", {"fixture": True})],
            observations=[ObservationInput("EXTRA", "2026-07-18", 1.0)],
        )
    finally:
        conn.close()

    with pytest.raises(MigrationParityError, match="series set"):
        migrate_legacy_snapshot(csv_path, metadata_path, db_path=db_path)


def test_parity_preserves_a_valid_all_missing_series(tmp_path: Path) -> None:
    csv_path = tmp_path / "all-missing-series.csv"
    metadata_path = tmp_path / "all-missing-series.json"
    frame = pd.DataFrame(
        {"ACWI": [100.0, 101.0], "EMPTY": [float("nan"), float("nan")]},
        index=pd.to_datetime(["2026-07-15", "2026-07-16"]),
    )
    frame.to_csv(csv_path, encoding="utf-8")
    metadata_path.write_text(
        json.dumps({"observed_at": "2026-07-19T17:14:07", "source": "fixture"}),
        encoding="utf-8",
    )

    result = migrate_legacy_snapshot(csv_path, metadata_path, db_path=tmp_path / "all-missing-series.sqlite3")
    assert result["parity"]["series_count"] == 2
