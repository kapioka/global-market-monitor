from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from project.market_data_provider import resolve_market_data_db_path, utc_now_iso

SCHEMA_VERSION = 1
DEFAULT_BUSY_TIMEOUT_SECONDS = 5.0
SUCCESS_STATUS = "success"


class MarketDataStoreError(RuntimeError):
    pass


class UnsupportedSchemaVersionError(MarketDataStoreError):
    pass


class SchemaMigrationError(MarketDataStoreError):
    pass


class SeriesDefinitionConflictError(MarketDataStoreError):
    pass


class IngestionConflictError(MarketDataStoreError):
    pass


class StoreBusyError(MarketDataStoreError):
    pass


class IntegrityCheckError(MarketDataStoreError):
    pass


class BackupError(MarketDataStoreError):
    pass


class MarketDataValidationError(MarketDataStoreError):
    pass


@dataclass(frozen=True)
class SeriesDefinition:
    series_id: str
    source_id: str
    source_type: str
    frequency: str
    value_kind: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ObservationInput:
    series_id: str
    observation_date: str
    value: float | int | None
    quality: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IngestionResult:
    status: str
    run_id: str
    input_fingerprint: str
    attempted_count: int
    inserted_count: int
    revised_count: int
    unchanged_count: int
    skipped_missing_count: int


def connect_market_data_store(
    db_path: str | Path | None = None,
    *,
    timeout_seconds: float = DEFAULT_BUSY_TIMEOUT_SECONDS,
    app_version: str | None = None,
) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else resolve_market_data_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    created_by_this_call = False
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
    except FileExistsError:
        pass
    else:
        os.close(descriptor)
        created_by_this_call = True
    conn = sqlite3.connect(path, timeout=timeout_seconds)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {max(0, int(timeout_seconds * 1000))}")
    try:
        if not created_by_this_call:
            if not _schema_migrations_table_exists(conn) or _current_schema_version(conn) == 0:
                raise SchemaMigrationError("existing database is not a recognized market data store")
        initialize_or_migrate(conn, app_version=app_version)
        conn.execute("PRAGMA journal_mode = WAL")
    except Exception:
        conn.close()
        raise
    return conn


def connect_market_data_store_read_only(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path).resolve(strict=True)
    conn = sqlite3.connect(f"{path.as_uri()}?mode=ro&immutable=1", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        if not _schema_migrations_table_exists(conn):
            raise SchemaMigrationError("existing database is not a recognized market data store")
        version = _current_schema_version(conn)
        if version != SCHEMA_VERSION:
            raise UnsupportedSchemaVersionError(f"market data schema version {version} does not match supported version {SCHEMA_VERSION}")
        check_integrity(conn)
        _validate_schema_contract(conn)
    except Exception:
        conn.close()
        raise
    return conn


def initialize_or_migrate(conn: sqlite3.Connection, *, app_version: str | None = None) -> None:
    current_version = _current_schema_version(conn)
    if current_version > SCHEMA_VERSION:
        raise UnsupportedSchemaVersionError(
            f"market data schema version {current_version} is newer than supported version {SCHEMA_VERSION}"
        )
    if current_version:
        check_integrity(conn)
    if current_version == SCHEMA_VERSION:
        _validate_schema_contract(conn)
        return
    try:
        conn.execute("BEGIN IMMEDIATE")
        if current_version < 1:
            _apply_schema_v1(conn)
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at, app_version) VALUES (?, ?, ?)",
                (1, utc_now_iso(), app_version),
            )
        conn.commit()
        _validate_schema_contract(conn)
    except sqlite3.OperationalError as exc:
        conn.rollback()
        if _is_busy_error(exc):
            raise StoreBusyError("market data schema is locked by another writer") from exc
        raise SchemaMigrationError("market data schema migration failed") from exc
    except Exception as exc:
        conn.rollback()
        if isinstance(exc, MarketDataStoreError):
            raise
        raise SchemaMigrationError("market data schema migration failed") from exc


def ingest_observations(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    observed_at: str,
    source: str,
    input_fingerprint: str,
    series_definitions: Iterable[SeriesDefinition],
    observations: Iterable[ObservationInput],
    warnings: Iterable[str] = (),
) -> IngestionResult:
    run_id = _required_text(run_id, "run_id")
    source = _required_text(source, "source")
    input_fingerprint = _required_text(input_fingerprint, "input_fingerprint")
    canonical_observed_at = _canonical_utc_timestamp(observed_at, "observed_at")
    warning_rows = list(warnings)
    definitions = _normalize_definitions(series_definitions)
    normalized, duplicate_unchanged, skipped_missing = _normalize_observations(
        observations,
        observed_date=canonical_observed_at[:10],
    )
    prior = conn.execute(
        "SELECT run_id FROM ingestion_runs WHERE source = ? AND input_fingerprint = ? AND status = ?",
        (source, input_fingerprint, SUCCESS_STATUS),
    ).fetchone()
    if prior:
        return IngestionResult(
            status="no_change",
            run_id=str(prior["run_id"]),
            input_fingerprint=input_fingerprint,
            attempted_count=len(normalized),
            inserted_count=0,
            revised_count=0,
            unchanged_count=len(normalized) + duplicate_unchanged,
            skipped_missing_count=skipped_missing,
        )

    inserted_count = 0
    revised_count = 0
    unchanged_count = duplicate_unchanged
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO ingestion_runs(
                run_id, observed_at, source, input_fingerprint, status, row_count,
                inserted_count, revised_count, warning_json, completed_at
            ) VALUES (?, ?, ?, ?, 'running', ?, 0, 0, ?, NULL)
            """,
            (
                run_id,
                canonical_observed_at,
                source,
                input_fingerprint,
                len(normalized),
                _json_text(warning_rows),
            ),
        )
        _register_series(conn, definitions, canonical_observed_at)
        for item in normalized:
            _require_known_series(conn, item.series_id)
            latest = conn.execute(
                """
                SELECT revision, value_hash, observed_at
                FROM observations
                WHERE series_id = ? AND observation_date = ?
                ORDER BY revision DESC
                LIMIT 1
                """,
                (item.series_id, item.observation_date),
            ).fetchone()
            value = _canonical_value(item.value)
            value_hash = _value_hash(value)
            if latest and latest["value_hash"] == value_hash:
                unchanged_count += 1
                continue
            if latest and canonical_observed_at <= str(latest["observed_at"]):
                raise IngestionConflictError(
                    f"changed value is not newer than the current revision: {item.series_id} {item.observation_date}"
                )
            revision = int(latest["revision"]) + 1 if latest else 1
            conn.execute(
                """
                INSERT INTO observations(
                    series_id, observation_date, revision, value, observed_at,
                    run_id, value_hash, quality_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.series_id,
                    item.observation_date,
                    revision,
                    value,
                    canonical_observed_at,
                    run_id,
                    value_hash,
                    _json_text(item.quality),
                ),
            )
            if latest:
                revised_count += 1
            else:
                inserted_count += 1
        conn.execute(
            """
            UPDATE ingestion_runs
            SET status = 'success', inserted_count = ?, revised_count = ?, completed_at = ?
            WHERE run_id = ?
            """,
            (inserted_count, revised_count, utc_now_iso(), run_id),
        )
        conn.commit()
    except sqlite3.OperationalError as exc:
        conn.rollback()
        if _is_busy_error(exc):
            raise StoreBusyError("market data store is locked by another writer") from exc
        _record_failed_run(
            conn,
            run_id=run_id,
            observed_at=canonical_observed_at,
            source=source,
            input_fingerprint=input_fingerprint,
            row_count=len(normalized),
            warnings=[*warning_rows, f"sqlite_error:{type(exc).__name__}"],
        )
        raise MarketDataStoreError("market data ingestion transaction failed") from exc
    except Exception as exc:
        conn.rollback()
        _record_failed_run(
            conn,
            run_id=run_id,
            observed_at=canonical_observed_at,
            source=source,
            input_fingerprint=input_fingerprint,
            row_count=len(normalized),
            warnings=[*warning_rows, f"error:{type(exc).__name__}"],
        )
        if isinstance(exc, MarketDataStoreError):
            raise
        raise MarketDataStoreError("market data ingestion transaction failed") from exc
    return IngestionResult(
        status="success",
        run_id=run_id,
        input_fingerprint=input_fingerprint,
        attempted_count=len(normalized),
        inserted_count=inserted_count,
        revised_count=revised_count,
        unchanged_count=unchanged_count,
        skipped_missing_count=skipped_missing,
    )


def load_current_frame(
    conn: sqlite3.Connection,
    *,
    series_ids: Sequence[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    return _load_frame(
        conn,
        relation="current_observations",
        series_ids=series_ids,
        start_date=start_date,
        end_date=end_date,
    )


def load_frame_as_of(
    conn: sqlite3.Connection,
    *,
    observed_at: str,
    series_ids: Sequence[str] | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> pd.DataFrame:
    cutoff = _canonical_utc_timestamp(observed_at, "observed_at")
    where, params = _query_filters(series_ids=series_ids, start_date=start_date, end_date=end_date)
    params = [cutoff, cutoff, *params]
    rows = conn.execute(
        f"""
        SELECT o.series_id, o.observation_date, o.value
        FROM observations AS o
        WHERE o.observed_at <= ?
          AND NOT EXISTS (
              SELECT 1 FROM observations AS newer
              WHERE newer.series_id = o.series_id
                AND newer.observation_date = o.observation_date
                AND newer.observed_at <= ?
                AND newer.revision > o.revision
          )
          {where}
        ORDER BY o.observation_date, o.series_id
        """,
        params,
    ).fetchall()
    return _rows_to_frame(rows, series_ids)


def check_integrity(conn: sqlite3.Connection) -> str:
    messages = [str(row[0]) for row in conn.execute("PRAGMA integrity_check").fetchall()]
    if messages != ["ok"]:
        raise IntegrityCheckError("; ".join(messages) or "integrity check returned no result")
    return "ok"


def backup_market_data_store(conn: sqlite3.Connection, destination: str | Path) -> Path:
    destination_path = Path(destination)
    if destination_path.exists():
        raise BackupError(f"backup target already exists: {destination_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{destination_path.name}.", suffix=".tmp", dir=destination_path.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    backup_conn: sqlite3.Connection | None = None
    try:
        check_integrity(conn)
        backup_conn = sqlite3.connect(temp_path)
        conn.backup(backup_conn)
        check_integrity(backup_conn)
        backup_conn.close()
        backup_conn = None
        publish_file_no_clobber(temp_path, destination_path)
        return destination_path
    except Exception as exc:
        if backup_conn is not None:
            backup_conn.close()
        temp_path.unlink(missing_ok=True)
        if isinstance(exc, BackupError):
            raise
        raise BackupError("market data backup failed") from exc


def restore_market_data_backup(backup_path: str | Path, target_path: str | Path) -> Path:
    source_path = Path(backup_path)
    destination_path = Path(target_path)
    if not source_path.is_file():
        raise BackupError(f"backup does not exist: {source_path}")
    if destination_path.exists():
        raise BackupError(f"restore target already exists: {destination_path}")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{destination_path.name}.", suffix=".tmp", dir=destination_path.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    source_conn: sqlite3.Connection | None = None
    target_conn: sqlite3.Connection | None = None
    try:
        uri = f"file:{source_path.resolve().as_posix()}?mode=ro"
        source_conn = sqlite3.connect(uri, uri=True)
        check_integrity(source_conn)
        target_conn = sqlite3.connect(temp_path)
        source_conn.backup(target_conn)
        check_integrity(target_conn)
        target_conn.close()
        target_conn = None
        source_conn.close()
        source_conn = None
        publish_file_no_clobber(temp_path, destination_path)
        return destination_path
    except Exception as exc:
        if target_conn is not None:
            target_conn.close()
        if source_conn is not None:
            source_conn.close()
        temp_path.unlink(missing_ok=True)
        if isinstance(exc, BackupError):
            raise
        raise BackupError("market data restore failed") from exc


def _apply_schema_v1(conn: sqlite3.Connection) -> None:
    script = """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL,
            app_version TEXT
        );

        CREATE TABLE IF NOT EXISTS series (
            series_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            frequency TEXT NOT NULL,
            value_kind TEXT NOT NULL,
            created_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ingestion_runs (
            run_id TEXT PRIMARY KEY,
            observed_at TEXT NOT NULL,
            source TEXT NOT NULL,
            input_fingerprint TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
            row_count INTEGER NOT NULL CHECK (row_count >= 0),
            inserted_count INTEGER NOT NULL CHECK (inserted_count >= 0),
            revised_count INTEGER NOT NULL CHECK (revised_count >= 0),
            warning_json TEXT NOT NULL,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS observations (
            series_id TEXT NOT NULL,
            observation_date TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK (revision >= 1),
            value REAL NOT NULL,
            observed_at TEXT NOT NULL,
            run_id TEXT NOT NULL,
            value_hash TEXT NOT NULL,
            quality_json TEXT NOT NULL,
            PRIMARY KEY (series_id, observation_date, revision),
            FOREIGN KEY (series_id) REFERENCES series(series_id),
            FOREIGN KEY (run_id) REFERENCES ingestion_runs(run_id)
        );

        CREATE TABLE IF NOT EXISTS artifact_registry (
            artifact_type TEXT NOT NULL,
            artifact_path TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            source_run_id TEXT,
            status TEXT NOT NULL,
            PRIMARY KEY (artifact_type, artifact_path, sha256),
            FOREIGN KEY (source_run_id) REFERENCES ingestion_runs(run_id)
        );

        CREATE INDEX IF NOT EXISTS observations_series_date_idx
            ON observations(series_id, observation_date);
        CREATE INDEX IF NOT EXISTS observations_run_idx ON observations(run_id);
        CREATE INDEX IF NOT EXISTS observations_observed_at_idx ON observations(observed_at);
        CREATE UNIQUE INDEX IF NOT EXISTS ingestion_runs_success_fingerprint_idx
            ON ingestion_runs(source, input_fingerprint) WHERE status = 'success';

        CREATE VIEW IF NOT EXISTS current_observations AS
        SELECT o.*
        FROM observations AS o
        JOIN (
            SELECT series_id, observation_date, MAX(revision) AS revision
            FROM observations
            GROUP BY series_id, observation_date
        ) AS latest
          ON latest.series_id = o.series_id
         AND latest.observation_date = o.observation_date
         AND latest.revision = o.revision;
        """
    for statement in script.split(";"):
        if statement.strip():
            conn.execute(statement)


def _current_schema_version(conn: sqlite3.Connection) -> int:
    if not _schema_migrations_table_exists(conn):
        return 0
    row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
    return int(row[0] or 0)


def _schema_migrations_table_exists(conn: sqlite3.Connection) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'schema_migrations'").fetchone() is not None


def publish_file_no_clobber(source: str | Path, destination: str | Path) -> None:
    source_path = Path(source)
    destination_path = Path(destination)
    os.link(source_path, destination_path)
    source_path.unlink()


def _validate_schema_contract(conn: sqlite3.Connection) -> None:
    required = {
        "table": {"schema_migrations", "series", "ingestion_runs", "observations", "artifact_registry"},
        "view": {"current_observations"},
    }
    for object_type, names in required.items():
        actual = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type = ?", (object_type,)).fetchall()}
        missing = sorted(names - actual)
        if missing:
            raise SchemaMigrationError(f"market data schema is incomplete: missing {object_type} {', '.join(missing)}")


def _normalize_definitions(definitions: Iterable[SeriesDefinition]) -> dict[str, SeriesDefinition]:
    result: dict[str, SeriesDefinition] = {}
    for definition in definitions:
        normalized = SeriesDefinition(
            series_id=_required_text(definition.series_id, "series_id"),
            source_id=_required_text(definition.source_id, "source_id"),
            source_type=_required_text(definition.source_type, "source_type"),
            frequency=_required_text(definition.frequency, "frequency"),
            value_kind=_required_text(definition.value_kind, "value_kind"),
            metadata=dict(definition.metadata),
        )
        previous = result.get(normalized.series_id)
        if previous is not None and previous != normalized:
            raise SeriesDefinitionConflictError(f"conflicting series definitions: {normalized.series_id}")
        result[normalized.series_id] = normalized
    return result


def _normalize_observations(
    observations: Iterable[ObservationInput],
    *,
    observed_date: str,
) -> tuple[list[ObservationInput], int, int]:
    result: dict[tuple[str, str], ObservationInput] = {}
    duplicate_unchanged = 0
    skipped_missing = 0
    for observation in observations:
        series_id = _required_text(observation.series_id, "series_id")
        observation_date = _canonical_date(observation.observation_date, "observation_date")
        if observation_date > observed_date:
            raise MarketDataValidationError(f"observation date {observation_date} is after ingestion date {observed_date}")
        if observation.value is None:
            skipped_missing += 1
            continue
        value = _canonical_value(observation.value)
        normalized = ObservationInput(
            series_id=series_id,
            observation_date=observation_date,
            value=value,
            quality=dict(observation.quality),
        )
        key = (series_id, observation_date)
        previous = result.get(key)
        if previous is not None:
            if _value_hash(_canonical_value(previous.value)) != _value_hash(value):
                raise IngestionConflictError(f"conflicting values in one batch: {series_id} {observation_date}")
            duplicate_unchanged += 1
            continue
        result[key] = normalized
    return [result[key] for key in sorted(result)], duplicate_unchanged, skipped_missing


def _register_series(
    conn: sqlite3.Connection,
    definitions: dict[str, SeriesDefinition],
    created_at: str,
) -> None:
    for definition in definitions.values():
        existing = conn.execute("SELECT * FROM series WHERE series_id = ?", (definition.series_id,)).fetchone()
        identity = (
            definition.source_id,
            definition.source_type,
            definition.frequency,
            definition.value_kind,
            _json_text(definition.metadata),
        )
        if existing:
            stored = (
                str(existing["source_id"]),
                str(existing["source_type"]),
                str(existing["frequency"]),
                str(existing["value_kind"]),
                str(existing["metadata_json"]),
            )
            if stored != identity:
                raise SeriesDefinitionConflictError(f"series definition changed: {definition.series_id}")
            continue
        conn.execute(
            """
            INSERT INTO series(
                series_id, source_id, source_type, frequency, value_kind, created_at, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (definition.series_id, *identity[:4], created_at, identity[4]),
        )


def _require_known_series(conn: sqlite3.Connection, series_id: str) -> None:
    if conn.execute("SELECT 1 FROM series WHERE series_id = ?", (series_id,)).fetchone() is None:
        raise MarketDataValidationError(f"observation references unknown series: {series_id}")


def _record_failed_run(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    observed_at: str,
    source: str,
    input_fingerprint: str,
    row_count: int,
    warnings: Iterable[str],
) -> None:
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO ingestion_runs(
                    run_id, observed_at, source, input_fingerprint, status, row_count,
                    inserted_count, revised_count, warning_json, completed_at
                ) VALUES (?, ?, ?, ?, 'failed', ?, 0, 0, ?, ?)
                """,
                (run_id, observed_at, source, input_fingerprint, row_count, _json_text(list(warnings)), utc_now_iso()),
            )
    except sqlite3.Error:
        return


def _load_frame(
    conn: sqlite3.Connection,
    *,
    relation: str,
    series_ids: Sequence[str] | None,
    start_date: str | None,
    end_date: str | None,
) -> pd.DataFrame:
    where, params = _query_filters(series_ids=series_ids, start_date=start_date, end_date=end_date)
    rows = conn.execute(
        f"""
        SELECT series_id, observation_date, value
        FROM {relation} AS o
        WHERE 1 = 1 {where}
        ORDER BY observation_date, series_id
        """,
        params,
    ).fetchall()
    return _rows_to_frame(rows, series_ids)


def _query_filters(
    *,
    series_ids: Sequence[str] | None,
    start_date: str | None,
    end_date: str | None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if series_ids is not None:
        normalized_ids = sorted({_required_text(value, "series_id") for value in series_ids})
        if not normalized_ids:
            clauses.append("1 = 0")
        else:
            placeholders = ",".join("?" for _ in normalized_ids)
            clauses.append(f"o.series_id IN ({placeholders})")
            params.extend(normalized_ids)
    if start_date is not None:
        clauses.append("o.observation_date >= ?")
        params.append(_canonical_date(start_date, "start_date"))
    if end_date is not None:
        clauses.append("o.observation_date <= ?")
        params.append(_canonical_date(end_date, "end_date"))
    return (" AND " + " AND ".join(clauses)) if clauses else "", params


def _rows_to_frame(rows: Sequence[sqlite3.Row], requested_series: Sequence[str] | None) -> pd.DataFrame:
    columns = sorted({_required_text(value, "series_id") for value in requested_series}) if requested_series else None
    if not rows:
        return pd.DataFrame(columns=columns, index=pd.DatetimeIndex([], name="date"), dtype=float)
    frame = pd.DataFrame([dict(row) for row in rows])
    wide = frame.pivot(index="observation_date", columns="series_id", values="value")
    wide.index = pd.to_datetime(wide.index)
    wide.index.name = "date"
    wide.columns.name = None
    if columns is not None:
        wide = wide.reindex(columns=columns)
    return wide.sort_index().sort_index(axis=1)


def _required_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MarketDataValidationError(f"{field_name} must be a non-empty string")
    return value.strip()


def _canonical_date(value: str, field_name: str) -> str:
    try:
        return date.fromisoformat(_required_text(value, field_name)).isoformat()
    except ValueError as exc:
        raise MarketDataValidationError(f"{field_name} must be an ISO date") from exc


def _canonical_utc_timestamp(value: str, field_name: str) -> str:
    text = _required_text(value, field_name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MarketDataValidationError(f"{field_name} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MarketDataValidationError(f"{field_name} must include a timezone")
    return parsed.astimezone(UTC).isoformat()


def _canonical_value(value: float | int | None) -> float:
    if isinstance(value, bool) or value is None:
        raise MarketDataValidationError("observation value must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise MarketDataValidationError("observation value must be a finite number")
    return 0.0 if number == 0 else number


def _value_hash(value: float) -> str:
    return hashlib.sha256(_json_text({"value": value}).encode("utf-8")).hexdigest()


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _is_busy_error(exc: sqlite3.OperationalError) -> bool:
    message = str(exc).lower()
    return "locked" in message or "busy" in message
