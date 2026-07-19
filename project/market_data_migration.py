from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from project.market_data_provider import resolve_market_data_db_path
from project.market_data_store import (
    MarketDataStoreError,
    ObservationInput,
    SeriesDefinition,
    check_integrity,
    connect_market_data_store,
    connect_market_data_store_read_only,
    ingest_observations,
    load_current_frame,
    publish_file_no_clobber,
)

MIGRATION_SCHEMA_VERSION = "market_data_storage.csv_migration.v1"
LEGACY_TIMEZONE = ZoneInfo("Asia/Tokyo")


class MarketDataMigrationError(RuntimeError):
    pass


class MigrationParityError(MarketDataMigrationError):
    pass


class MigrationTargetExistsError(MarketDataMigrationError):
    pass


@dataclass(frozen=True)
class LoadedSnapshot:
    frame: pd.DataFrame
    csv_path: Path
    metadata_path: Path
    csv_sha256: str
    metadata_sha256: str
    observed_at: str
    source: str
    normalized_fingerprint: str
    input_fingerprint: str


def load_legacy_snapshot(csv_path: str | Path, metadata_path: str | Path) -> LoadedSnapshot:
    csv_file = Path(csv_path).resolve(strict=True)
    metadata_file = Path(metadata_path).resolve(strict=True)
    csv_bytes = csv_file.read_bytes()
    metadata_bytes = metadata_file.read_bytes()
    _validate_csv_header(csv_bytes)
    try:
        metadata = json.loads(metadata_bytes.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MarketDataMigrationError("snapshot metadata is not valid UTF-8 JSON") from exc
    if not isinstance(metadata, dict):
        raise MarketDataMigrationError("snapshot metadata root must be an object")
    try:
        frame = pd.read_csv(csv_file, index_col=0)
    except Exception as exc:
        raise MarketDataMigrationError("snapshot CSV could not be parsed") from exc
    frame = _normalize_wide_frame(frame)
    observed_at = _snapshot_observed_at(metadata.get("observed_at"))
    source = str(metadata.get("source") or "legacy_snapshot_csv")
    csv_sha256 = hashlib.sha256(csv_bytes).hexdigest()
    metadata_sha256 = hashlib.sha256(metadata_bytes).hexdigest()
    normalized_fingerprint = normalized_frame_fingerprint(frame)
    input_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "schema": MIGRATION_SCHEMA_VERSION,
                "csv_sha256": csv_sha256,
                "metadata_sha256": metadata_sha256,
                "normalized_fingerprint": normalized_fingerprint,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return LoadedSnapshot(
        frame=frame,
        csv_path=csv_file,
        metadata_path=metadata_file,
        csv_sha256=csv_sha256,
        metadata_sha256=metadata_sha256,
        observed_at=observed_at,
        source=source,
        normalized_fingerprint=normalized_fingerprint,
        input_fingerprint=input_fingerprint,
    )


def migrate_legacy_snapshot(
    csv_path: str | Path,
    metadata_path: str | Path,
    *,
    db_path: str | Path | None = None,
    expected_csv_sha256: str | None = None,
    expected_metadata_sha256: str | None = None,
) -> dict[str, Any]:
    snapshot = load_legacy_snapshot(csv_path, metadata_path)
    _require_expected_hash(snapshot.csv_sha256, expected_csv_sha256, "CSV")
    _require_expected_hash(snapshot.metadata_sha256, expected_metadata_sha256, "metadata")
    destination = Path(db_path) if db_path is not None else resolve_market_data_db_path()
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists():
        return _verify_existing_migration(destination, snapshot)

    fd, temp_name = tempfile.mkstemp(prefix=f".{destination.name}.migration.", suffix=".sqlite3", dir=destination.parent)
    os.close(fd)
    candidate = Path(temp_name)
    candidate.unlink()
    conn = None
    try:
        conn = connect_market_data_store(candidate, app_version=MIGRATION_SCHEMA_VERSION)
        result = ingest_observations(
            conn,
            run_id=f"csv-migration:{snapshot.input_fingerprint[:24]}",
            observed_at=snapshot.observed_at,
            source="legacy_market_snapshot_csv",
            input_fingerprint=snapshot.input_fingerprint,
            series_definitions=_series_definitions(snapshot.frame.columns),
            observations=_observation_inputs(snapshot.frame),
            warnings=("shadow migration; legacy CSV remains authoritative",),
        )
        parity = verify_snapshot_parity(conn, snapshot.frame, snapshot.normalized_fingerprint)
        check_integrity(conn)
        checkpoint = conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        if checkpoint is None or int(checkpoint[0]) != 0:
            raise MarketDataMigrationError("candidate database WAL checkpoint did not complete")
        conn.close()
        conn = None
        _remove_sidecars(candidate)
        try:
            publish_file_no_clobber(candidate, destination)
        except FileExistsError as exc:
            raise MigrationTargetExistsError("migration target appeared during publication; refusing to overwrite it") from exc
        return _migration_result(
            status="migrated",
            destination=destination,
            snapshot=snapshot,
            parity=parity,
            ingestion_status=result.status,
        )
    except Exception:
        if conn is not None:
            conn.close()
        candidate.unlink(missing_ok=True)
        _remove_sidecars(candidate)
        raise


def verify_snapshot_parity(
    conn,
    expected_frame: pd.DataFrame,
    expected_fingerprint: str,
) -> dict[str, Any]:
    expected_series = set(expected_frame.columns)
    actual_series = {str(row[0]) for row in conn.execute("SELECT series_id FROM series").fetchall()}
    if actual_series != expected_series:
        raise MigrationParityError("reconstructed series set differs from source CSV")
    expected_dates = {timestamp.date().isoformat() for timestamp in expected_frame.index}
    actual_dates = {str(row[0]) for row in conn.execute("SELECT DISTINCT observation_date FROM current_observations").fetchall()}
    if actual_dates != expected_dates:
        raise MigrationParityError("reconstructed date set differs from source CSV")
    expected_non_missing = int(expected_frame.notna().sum().sum())
    actual_non_missing = int(conn.execute("SELECT COUNT(*) FROM current_observations").fetchone()[0])
    if actual_non_missing != expected_non_missing:
        raise MigrationParityError("reconstructed observation count differs from source CSV")
    reconstructed = load_current_frame(conn, series_ids=list(expected_frame.columns))
    reconstructed = reconstructed.reindex(index=expected_frame.index, columns=expected_frame.columns)
    actual_fingerprint = normalized_frame_fingerprint(reconstructed)
    try:
        pd.testing.assert_frame_equal(
            reconstructed,
            expected_frame,
            check_dtype=False,
            check_exact=True,
            check_names=True,
            check_freq=False,
        )
    except AssertionError as exc:
        raise MigrationParityError(f"reconstructed frame differs from source CSV: {exc}") from exc
    if actual_fingerprint != expected_fingerprint:
        raise MigrationParityError("reconstructed frame fingerprint differs from source CSV")
    return {
        "status": "pass",
        "series_count": len(expected_frame.columns),
        "wide_row_count": len(expected_frame.index),
        "non_missing_count": expected_non_missing,
        "date_min": expected_frame.index.min().date().isoformat(),
        "date_max": expected_frame.index.max().date().isoformat(),
        "normalized_fingerprint": actual_fingerprint,
    }


def normalized_frame_fingerprint(frame: pd.DataFrame) -> str:
    digest = hashlib.sha256()
    digest.update(MIGRATION_SCHEMA_VERSION.encode("utf-8"))
    digest.update(json.dumps(list(frame.columns), ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    for index, row in frame.iterrows():
        digest.update(index.date().isoformat().encode("ascii"))
        digest.update(b"\0")
        for value in row:
            if pd.isna(value):
                digest.update(b"NA")
            else:
                number = float(value)
                if not math.isfinite(number):
                    raise MarketDataMigrationError("snapshot contains a non-finite value")
                digest.update(number.hex().encode("ascii"))
            digest.update(b"\0")
    return digest.hexdigest()


def _normalize_wide_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or not len(frame.columns):
        raise MarketDataMigrationError("snapshot CSV contains no market data")
    columns = [str(column).strip() for column in frame.columns]
    if any(not column for column in columns) or len(columns) != len(set(columns)):
        raise MarketDataMigrationError("snapshot CSV series columns must be non-empty and unique")
    frame = frame.copy()
    frame.columns = columns
    try:
        frame.index = pd.to_datetime(frame.index, errors="raise")
    except Exception as exc:
        raise MarketDataMigrationError("snapshot CSV index contains an invalid date") from exc
    if frame.index.tz is not None:
        frame.index = frame.index.tz_convert(UTC).tz_localize(None)
    frame.index = frame.index.normalize()
    frame.index.name = "date"
    if frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise MarketDataMigrationError("snapshot CSV dates must be strictly increasing and unique")
    if frame.isna().all(axis=1).any():
        raise MarketDataMigrationError("snapshot CSV contains an all-missing date that cannot be reconstructed")
    try:
        numeric = frame.apply(pd.to_numeric, errors="raise").astype(float)
    except (TypeError, ValueError) as exc:
        raise MarketDataMigrationError("snapshot CSV contains a non-numeric value") from exc
    finite_values = numeric.stack()
    if not finite_values.map(lambda value: math.isfinite(float(value))).all():
        raise MarketDataMigrationError("snapshot CSV contains a non-finite value")
    return numeric


def _validate_csv_header(csv_bytes: bytes) -> None:
    try:
        text = csv_bytes.decode("utf-8-sig")
        header = next(csv.reader(io.StringIO(text)))
    except (UnicodeDecodeError, StopIteration, csv.Error) as exc:
        raise MarketDataMigrationError("snapshot CSV header is invalid") from exc
    series_columns = [value.strip() for value in header[1:]]
    if len(header) < 2 or any(not value for value in series_columns) or len(series_columns) != len(set(series_columns)):
        raise MarketDataMigrationError("snapshot CSV series columns must be non-empty and unique")


def _snapshot_observed_at(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MarketDataMigrationError("snapshot metadata observed_at is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MarketDataMigrationError("snapshot metadata observed_at is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        parsed = parsed.replace(tzinfo=LEGACY_TIMEZONE)
    return parsed.astimezone(UTC).isoformat()


def _series_definitions(columns) -> list[SeriesDefinition]:
    return [
        SeriesDefinition(
            series_id=str(series_id),
            source_id=str(series_id),
            source_type="legacy_market_snapshot_csv",
            frequency="mixed_or_unknown",
            value_kind="snapshot_numeric_value",
            metadata={"origin": "legacy_market_snapshot_csv"},
        )
        for series_id in columns
    ]


def _observation_inputs(frame: pd.DataFrame):
    for observed_day, row in frame.iterrows():
        day = observed_day.date().isoformat()
        for series_id, value in row.items():
            yield ObservationInput(
                series_id=str(series_id),
                observation_date=day,
                value=None if pd.isna(value) else float(value),
                quality={"migration": MIGRATION_SCHEMA_VERSION},
            )


def _verify_existing_migration(destination: Path, snapshot: LoadedSnapshot) -> dict[str, Any]:
    try:
        conn = connect_market_data_store_read_only(destination)
    except MarketDataStoreError as exc:
        raise MigrationTargetExistsError("existing database is not a recognized matching market store; refusing to modify it") from exc
    try:
        run = conn.execute(
            """
            SELECT status FROM ingestion_runs
            WHERE source = 'legacy_market_snapshot_csv' AND input_fingerprint = ? AND status = 'success'
            """,
            (snapshot.input_fingerprint,),
        ).fetchone()
        if run is None:
            raise MigrationTargetExistsError("existing market database was not created from this exact snapshot; refusing to modify it")
        parity = verify_snapshot_parity(conn, snapshot.frame, snapshot.normalized_fingerprint)
        check_integrity(conn)
    finally:
        conn.close()
    return _migration_result(
        status="no_change",
        destination=destination,
        snapshot=snapshot,
        parity=parity,
        ingestion_status="no_change",
    )


def _migration_result(
    *,
    status: str,
    destination: Path,
    snapshot: LoadedSnapshot,
    parity: dict[str, Any],
    ingestion_status: str,
) -> dict[str, Any]:
    return {
        "schema_version": MIGRATION_SCHEMA_VERSION,
        "status": status,
        "shadow_only": True,
        "legacy_csv_remains_authoritative": True,
        "database_path": str(destination),
        "database_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        "database_bytes": destination.stat().st_size,
        "source_csv_path": str(snapshot.csv_path),
        "source_csv_sha256": snapshot.csv_sha256,
        "source_metadata_path": str(snapshot.metadata_path),
        "source_metadata_sha256": snapshot.metadata_sha256,
        "input_fingerprint": snapshot.input_fingerprint,
        "ingestion_status": ingestion_status,
        "integrity_check": "ok",
        "parity": parity,
    }


def _require_expected_hash(actual: str, expected: str | None, label: str) -> None:
    if expected is not None and actual.lower() != expected.lower():
        raise MarketDataMigrationError(f"{label} SHA256 does not match the approved baseline")


def _remove_sidecars(path: Path) -> None:
    Path(f"{path}-wal").unlink(missing_ok=True)
    Path(f"{path}-shm").unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate one verified legacy market snapshot into shadow SQLite storage.")
    parser.add_argument("--csv", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--db")
    parser.add_argument("--expected-csv-sha256")
    parser.add_argument("--expected-metadata-sha256")
    args = parser.parse_args()
    result = migrate_legacy_snapshot(
        args.csv,
        args.metadata,
        db_path=args.db,
        expected_csv_sha256=args.expected_csv_sha256,
        expected_metadata_sha256=args.expected_metadata_sha256,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
