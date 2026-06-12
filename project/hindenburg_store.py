from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from project.hindenburg_provider import resolve_hindenburg_db_path, utc_now_iso

SCHEMA_VERSION = 1
DEFINITION_VERSION = "hindenburg_legacy_compat_v1"
MARKET = "NYSE"
UNIVERSE_ID = "nyse_legacy_compat"
MIN_MCCLELLAN_HISTORY_DAYS = 39
RESET_CONFIRMATION_PHRASE = "Hindenburg Omenのローカル状態を再初期化"


@dataclass(frozen=True)
class StoreUpdateResult:
    status: str
    state: str
    failure_code: str | None = None
    context: dict[str, Any] | None = None
    is_previous_confirmed_result: bool = False
    inserted_count: int = 0
    attempted_count: int = 0
    provider_attempts: tuple[dict[str, Any], ...] = ()


def connect_hindenburg_store(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path else resolve_hindenburg_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    initialize_schema(conn)
    return conn


def initialize_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS hindenburg_schema_migrations (
            schema_version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS hindenburg_normalized_inputs (
            provider_id TEXT NOT NULL,
            universe_id TEXT NOT NULL,
            market_date TEXT NOT NULL,
            definition_version TEXT NOT NULL,
            market TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            source_label TEXT NOT NULL,
            payload_checksum TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            acquired_at TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            PRIMARY KEY (provider_id, universe_id, market_date, definition_version)
        );

        CREATE TABLE IF NOT EXISTS hindenburg_daily_results (
            provider_id TEXT NOT NULL,
            universe_id TEXT NOT NULL,
            market_date TEXT NOT NULL,
            definition_version TEXT NOT NULL,
            result_json TEXT NOT NULL,
            calculated_at TEXT NOT NULL,
            input_checksum TEXT NOT NULL,
            PRIMARY KEY (provider_id, universe_id, market_date, definition_version)
        );

        CREATE TABLE IF NOT EXISTS hindenburg_current_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            state TEXT NOT NULL,
            provider_id TEXT,
            universe_id TEXT,
            confirmed_market_date TEXT,
            context_json TEXT,
            last_update_attempt_at TEXT,
            last_successful_update_at TEXT,
            failure_code TEXT,
            history_complete INTEGER NOT NULL DEFAULT 0,
            is_previous_confirmed_result INTEGER NOT NULL DEFAULT 0,
            schema_version INTEGER NOT NULL,
            definition_version TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS hindenburg_provider_health (
            provider_id TEXT PRIMARY KEY,
            last_attempt_at TEXT,
            last_success_at TEXT,
            last_failure_code TEXT,
            consecutive_failures INTEGER NOT NULL DEFAULT 0,
            parser_version TEXT,
            last_market_date TEXT,
            last_payload_checksum TEXT,
            cooldown_until TEXT
        );

        CREATE TABLE IF NOT EXISTS hindenburg_auto_attempt_policy (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_attempt_market_date TEXT,
            last_attempt_at TEXT,
            last_attempt_result TEXT,
            last_successful_provider TEXT,
            manual_retry_after TEXT,
            provider_attempts_json TEXT,
            schema_version INTEGER NOT NULL,
            definition_version TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT OR IGNORE INTO hindenburg_schema_migrations(schema_version, applied_at) VALUES (?, ?)",
        (SCHEMA_VERSION, utc_now_iso()),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO hindenburg_current_state(
            id, state, schema_version, definition_version, history_complete, is_previous_confirmed_result
        ) VALUES (1, 'UNINITIALIZED', ?, ?, 0, 0)
        """,
        (SCHEMA_VERSION, DEFINITION_VERSION),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO hindenburg_auto_attempt_policy(
            id, schema_version, definition_version
        ) VALUES (1, ?, ?)
        """,
        (SCHEMA_VERSION, DEFINITION_VERSION),
    )
    conn.commit()


def load_current_context(conn: sqlite3.Connection) -> dict[str, Any] | None:
    row = conn.execute("SELECT context_json FROM hindenburg_current_state WHERE id = 1").fetchone()
    if not row or not row["context_json"]:
        return None
    return json.loads(row["context_json"])


def update_store_with_signals(
    conn: sqlite3.Connection,
    *,
    parsed: dict[str, Any],
    daily_signals: list[dict[str, Any]],
    context: dict[str, Any],
    provider_id: str,
    source_label: str,
    state: str,
    provider_attempts: list[dict[str, Any]] | None = None,
) -> StoreUpdateResult:
    frame = parsed.get("frame")
    if frame is None:
        return _preserve_previous(conn, state=state, failure_code=str(parsed.get("status") or "NO_FRAME"), provider_attempts=provider_attempts)
    normalized = _normalized_rows(frame, source_kind=str(parsed.get("source_kind") or provider_id), source_label=source_label, provider_id=provider_id)
    duplicate_error = _detect_incoming_duplicate_conflict(normalized)
    if duplicate_error:
        return _preserve_previous(conn, state="INVALID_DATA", failure_code=duplicate_error, provider_attempts=provider_attempts)
    result_by_date = {row["date"]: row for row in daily_signals}
    last = _current_state_row(conn)
    confirmed_date = str(last["confirmed_market_date"] or "") if last else ""
    if confirmed_date and any(item["market_date"] > confirmed_date for item in normalized) and not any(
        item["market_date"] == confirmed_date for item in normalized
    ):
        return _preserve_previous(conn, state="GAP_BLOCKED", failure_code="MISSING_CONFIRMED_ANCHOR", provider_attempts=provider_attempts)
    now = utc_now_iso()
    inserted_count = 0
    try:
        with conn:
            for item in normalized:
                existing = conn.execute(
                    """
                    SELECT payload_checksum FROM hindenburg_normalized_inputs
                    WHERE provider_id = ? AND universe_id = ? AND market_date = ? AND definition_version = ?
                    """,
                    (provider_id, UNIVERSE_ID, item["market_date"], DEFINITION_VERSION),
                ).fetchone()
                if existing:
                    if existing["payload_checksum"] != item["payload_checksum"]:
                        raise ConflictingCorrectionError(item["market_date"])
                    continue
                conn.execute(
                    """
                    INSERT INTO hindenburg_normalized_inputs(
                        provider_id, universe_id, market_date, definition_version, market, source_kind,
                        source_label, payload_checksum, payload_json, acquired_at, schema_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        provider_id,
                        UNIVERSE_ID,
                        item["market_date"],
                        DEFINITION_VERSION,
                        MARKET,
                        item["source_kind"],
                        item["source_label"],
                        item["payload_checksum"],
                        json.dumps(item["payload"], ensure_ascii=False, sort_keys=True),
                        now,
                        SCHEMA_VERSION,
                    ),
                )
                inserted_count += 1
            for market_date, signal in result_by_date.items():
                checksum = next((item["payload_checksum"] for item in normalized if item["market_date"] == market_date), "")
                if not checksum:
                    continue
                enriched = {
                    **signal,
                    "definition_version": DEFINITION_VERSION,
                    "denominator_method": "total_issues_if_valid_else_advancers_plus_decliners",
                    "uptrend_method": str((signal.get("criteria") or {}).get("uptrend", {}).get("detail", "unknown")),
                    "mcclellan_method": "source_supplied_or_internal_19_39_ema_fill",
                    "input_checksum": checksum,
                }
                conn.execute(
                    """
                    INSERT OR REPLACE INTO hindenburg_daily_results(
                        provider_id, universe_id, market_date, definition_version, result_json, calculated_at, input_checksum
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        provider_id,
                        UNIVERSE_ID,
                        market_date,
                        DEFINITION_VERSION,
                        json.dumps(enriched, ensure_ascii=False, sort_keys=True),
                        now,
                        checksum,
                    ),
                )
            stored_context = {
                **context,
                "state": state,
                "confirmed_market_date": context.get("latest_date"),
                "definition_version": DEFINITION_VERSION,
                "schema_version": SCHEMA_VERSION,
                "failure_code": None,
                "last_update_attempt_at": now,
                "last_successful_update_at": now,
                "is_previous_confirmed_result": False,
                "history_complete": True,
                "provider_id": provider_id,
                "provider_label": source_label,
                "provider_attempts": provider_attempts or [],
                "providers_attempted_count": len(provider_attempts or []),
            }
            conn.execute(
                """
                UPDATE hindenburg_current_state
                SET state = ?, provider_id = ?, universe_id = ?, confirmed_market_date = ?, context_json = ?,
                    last_update_attempt_at = ?, last_successful_update_at = ?, failure_code = NULL,
                    history_complete = 1, is_previous_confirmed_result = 0, schema_version = ?, definition_version = ?
                WHERE id = 1
                """,
                (
                    state,
                    provider_id,
                    UNIVERSE_ID,
                    stored_context.get("confirmed_market_date"),
                    json.dumps(stored_context, ensure_ascii=False, sort_keys=True),
                    now,
                    now,
                    SCHEMA_VERSION,
                    DEFINITION_VERSION,
                ),
            )
        return StoreUpdateResult(
            status="ok",
            state=state,
            context=stored_context,
            inserted_count=inserted_count,
            attempted_count=len(normalized),
            provider_attempts=tuple(provider_attempts or []),
        )
    except ConflictingCorrectionError as exc:
        return _preserve_previous(conn, state="INVALID_DATA", failure_code=f"CONFLICTING_CORRECTION:{exc.market_date}", provider_attempts=provider_attempts)
    except Exception:
        return _preserve_previous(conn, state="UPDATE_FAILED", failure_code="TRANSACTION_FAILED", provider_attempts=provider_attempts)


def mark_update_failed(
    conn: sqlite3.Connection,
    *,
    state: str,
    failure_code: str,
    provider_attempts: list[dict[str, Any]] | None = None,
) -> StoreUpdateResult:
    return _preserve_previous(conn, state=state, failure_code=failure_code, provider_attempts=provider_attempts)


def sqlite_integrity_check(conn: sqlite3.Connection) -> str:
    row = conn.execute("PRAGMA integrity_check").fetchone()
    return str(row[0]) if row else "unknown"


def history_progress(conn: sqlite3.Connection, provider_id: str | None = None) -> dict[str, Any]:
    params: list[Any] = [UNIVERSE_ID, DEFINITION_VERSION]
    where_provider = ""
    if provider_id:
        where_provider = " AND provider_id = ?"
        params.append(provider_id)
    row = conn.execute(
        f"""
        SELECT COUNT(*) AS count, MAX(market_date) AS latest_date
        FROM hindenburg_normalized_inputs
        WHERE universe_id = ? AND definition_version = ?{where_provider}
        """,
        params,
    ).fetchone()
    count = int(row["count"] or 0) if row else 0
    latest_date = str(row["latest_date"]) if row and row["latest_date"] else None
    return {
        "stored_valid_record_count": count,
        "minimum_required_record_count": MIN_MCCLELLAN_HISTORY_DAYS,
        "history_complete": count >= MIN_MCCLELLAN_HISTORY_DAYS,
        "history_progress_label": f"蓄積履歴: {count} / {MIN_MCCLELLAN_HISTORY_DAYS}営業日",
        "confirmed_market_date": latest_date,
    }


def load_provider_history_frame(conn: sqlite3.Connection, *, provider_id: str) -> pd.DataFrame:
    rows = conn.execute(
        """
        SELECT payload_json
        FROM hindenburg_normalized_inputs
        WHERE provider_id = ? AND universe_id = ? AND definition_version = ?
        ORDER BY market_date
        """,
        (provider_id, UNIVERSE_ID, DEFINITION_VERSION),
    ).fetchall()
    payloads = [json.loads(row["payload_json"]) for row in rows]
    if not payloads:
        return pd.DataFrame()
    records = []
    for payload in payloads:
        records.append(
            {
                "date": payload.get("market_date"),
                "new_highs": payload.get("new_highs"),
                "new_lows": payload.get("new_lows"),
                "advancers": payload.get("advancers"),
                "decliners": payload.get("decliners"),
                "unchanged": payload.get("unchanged"),
                "total_issues": payload.get("total_issues"),
                "nyse_index": payload.get("nyse_index"),
                "index_50d_ago": payload.get("index_50d_ago"),
                "index_above_50d": payload.get("index_above_50d"),
                "mcclellan_oscillator": payload.get("mcclellan_oscillator"),
                "source_note": payload.get("source_label"),
            }
        )
    return pd.DataFrame(records)


def load_auto_attempt_policy(conn: sqlite3.Connection) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM hindenburg_auto_attempt_policy WHERE id = 1").fetchone()
    if not row:
        return {}
    attempts_json = row["provider_attempts_json"] or "[]"
    try:
        attempts = json.loads(attempts_json)
    except json.JSONDecodeError:
        attempts = []
    return {
        "last_attempt_market_date": row["last_attempt_market_date"],
        "last_attempt_at": row["last_attempt_at"],
        "last_attempt_result": row["last_attempt_result"],
        "last_successful_provider": row["last_successful_provider"],
        "manual_retry_after": row["manual_retry_after"],
        "provider_attempts": attempts,
    }


def auto_attempt_eligible(conn: sqlite3.Connection, market_date: str, *, enabled: bool = True) -> dict[str, Any]:
    policy = load_auto_attempt_policy(conn)
    if not enabled:
        return {"eligible": False, "reason": "AUTO_DISABLED", "policy": policy}
    if policy.get("last_attempt_market_date") == market_date:
        return {"eligible": False, "reason": "ALREADY_ATTEMPTED_FOR_SESSION", "policy": policy}
    return {"eligible": True, "reason": "ELIGIBLE", "policy": policy}


def manual_retry_eligible(conn: sqlite3.Connection, *, now_iso: str | None = None) -> dict[str, Any]:
    now = now_iso or utc_now_iso()
    policy = load_auto_attempt_policy(conn)
    retry_after = str(policy.get("manual_retry_after") or "")
    if retry_after and now < retry_after:
        return {"eligible": False, "reason": "MANUAL_RETRY_COOLDOWN", "policy": policy}
    return {"eligible": True, "reason": "ELIGIBLE", "policy": policy}


def record_auto_attempt(
    conn: sqlite3.Connection,
    *,
    market_date: str,
    result: str,
    provider_attempts: list[dict[str, Any]],
    successful_provider: str | None = None,
    manual_retry_after: str | None = None,
) -> None:
    now = utc_now_iso()
    previous = load_auto_attempt_policy(conn)
    last_successful_provider = successful_provider or previous.get("last_successful_provider")
    with conn:
        conn.execute(
            """
            UPDATE hindenburg_auto_attempt_policy
            SET last_attempt_market_date = ?, last_attempt_at = ?, last_attempt_result = ?,
                last_successful_provider = ?, manual_retry_after = ?, provider_attempts_json = ?,
                schema_version = ?, definition_version = ?
            WHERE id = 1
            """,
            (
                market_date,
                now,
                result,
                last_successful_provider,
                manual_retry_after,
                json.dumps(provider_attempts, ensure_ascii=False, sort_keys=True),
                SCHEMA_VERSION,
                DEFINITION_VERSION,
            ),
        )
        for attempt in provider_attempts:
            provider_id = str(attempt.get("provider_id") or "")
            if not provider_id:
                continue
            status = str(attempt.get("status") or "")
            failure_code = attempt.get("failure_code")
            current = conn.execute(
                "SELECT consecutive_failures FROM hindenburg_provider_health WHERE provider_id = ?",
                (provider_id,),
            ).fetchone()
            consecutive_failures = 0 if status == "ok" else int(current["consecutive_failures"] or 0) + 1 if current else 1
            conn.execute(
                """
                INSERT INTO hindenburg_provider_health(
                    provider_id, last_attempt_at, last_success_at, last_failure_code,
                    consecutive_failures, parser_version, last_market_date, last_payload_checksum, cooldown_until
                ) VALUES (?, ?, ?, ?, ?, NULL, ?, NULL, NULL)
                ON CONFLICT(provider_id) DO UPDATE SET
                    last_attempt_at = excluded.last_attempt_at,
                    last_success_at = COALESCE(excluded.last_success_at, hindenburg_provider_health.last_success_at),
                    last_failure_code = excluded.last_failure_code,
                    consecutive_failures = excluded.consecutive_failures,
                    last_market_date = excluded.last_market_date
                """,
                (
                    provider_id,
                    now,
                    now if status == "ok" else None,
                    None if status == "ok" else failure_code,
                    consecutive_failures,
                    market_date,
                ),
            )


def reset_hindenburg_local_state(
    db_path: str | Path | None = None,
    *,
    confirmation: str,
    backup_dir: str | Path | None = None,
) -> dict[str, Any]:
    if confirmation != RESET_CONFIRMATION_PHRASE:
        return {"status": "confirmation_required", "backup_path": None, "message": "explicit confirmation phrase required"}
    path = Path(db_path) if db_path else resolve_hindenburg_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    backup_path: Path | None = None
    if path.exists():
        target_dir = Path(backup_dir) if backup_dir else path.parent / "backups"
        target_dir.mkdir(parents=True, exist_ok=True)
        backup_path = target_dir / f"{path.stem}.{utc_now_iso().replace(':', '').replace('+', 'Z')}.bak{path.suffix}"
        shutil.copy2(path, backup_path)
        if not backup_path.exists():
            return {"status": "backup_failed", "backup_path": str(backup_path), "message": "backup was not created"}
        path.unlink()
    conn = connect_hindenburg_store(path)
    try:
        integrity = sqlite_integrity_check(conn)
    finally:
        conn.close()
    return {
        "status": "ok" if integrity == "ok" else "reinitialized_with_integrity_warning",
        "backup_path": str(backup_path) if backup_path else None,
        "message": "Hindenburg Omen local state reinitialized",
        "integrity_check": integrity,
    }


class ConflictingCorrectionError(Exception):
    def __init__(self, market_date: str) -> None:
        super().__init__(market_date)
        self.market_date = market_date


def _preserve_previous(
    conn: sqlite3.Connection,
    *,
    state: str,
    failure_code: str,
    provider_attempts: list[dict[str, Any]] | None,
) -> StoreUpdateResult:
    now = utc_now_iso()
    previous_context = load_current_context(conn)
    with conn:
        if previous_context:
            preserved_state = "UPDATE_FAILED" if failure_code == "ALL_PROVIDERS_UNAVAILABLE" else state
            preserved = {
                **previous_context,
                "state": preserved_state,
                "failure_code": failure_code,
                "last_update_attempt_at": now,
                "is_previous_confirmed_result": True,
                "provider_attempts": provider_attempts or [],
                "providers_attempted_count": len(provider_attempts or []),
            }
            conn.execute(
                """
                UPDATE hindenburg_current_state
                SET state = ?, context_json = ?, last_update_attempt_at = ?, failure_code = ?,
                    is_previous_confirmed_result = 1, schema_version = ?, definition_version = ?
                WHERE id = 1
                """,
                (
                    preserved_state,
                    json.dumps(preserved, ensure_ascii=False, sort_keys=True),
                    now,
                    failure_code,
                    SCHEMA_VERSION,
                    DEFINITION_VERSION,
                ),
            )
            return StoreUpdateResult(
                status="previous_confirmed_preserved",
                state=preserved_state,
                failure_code=failure_code,
                context=preserved,
                is_previous_confirmed_result=True,
                provider_attempts=tuple(provider_attempts or []),
            )
        conn.execute(
            """
            UPDATE hindenburg_current_state
            SET state = ?, last_update_attempt_at = ?, failure_code = ?, is_previous_confirmed_result = 0,
                schema_version = ?, definition_version = ?
            WHERE id = 1
            """,
            (state, now, failure_code, SCHEMA_VERSION, DEFINITION_VERSION),
        )
    return StoreUpdateResult(status="failed", state=state, failure_code=failure_code, provider_attempts=tuple(provider_attempts or []))


def _current_state_row(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM hindenburg_current_state WHERE id = 1").fetchone()


def _normalized_rows(frame: pd.DataFrame, *, source_kind: str, source_label: str, provider_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, row in frame.sort_values("date").iterrows():
        market_date = pd.Timestamp(row["date"]).date().isoformat()
        payload = {
            "schema_version": SCHEMA_VERSION,
            "market": MARKET,
            "market_date": market_date,
            "status": "accepted",
            "new_highs": _int_like(row.get("new_highs")),
            "new_lows": _int_like(row.get("new_lows")),
            "advancers": _int_like(row.get("advancers")),
            "decliners": _int_like(row.get("decliners")),
            "unchanged": _int_like(row.get("unchanged")),
            "total_issues": _int_like(row.get("total_issues")),
            "nyse_index": _float_or_none(row.get("nyse_index")),
            "index_50d_ago": _float_or_none(row.get("index_50d_ago")),
            "index_above_50d": None if pd.isna(row.get("index_above_50d")) else str(row.get("index_above_50d")),
            "mcclellan_oscillator": _float_or_none(row.get("mcclellan_oscillator")),
            "provider_id": provider_id,
            "universe_id": UNIVERSE_ID,
            "source_label": source_label,
        }
        checksum = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        rows.append(
            {
                "market_date": market_date,
                "source_kind": source_kind,
                "source_label": source_label,
                "payload": payload,
                "payload_checksum": checksum,
            }
        )
    return rows


def _detect_incoming_duplicate_conflict(rows: list[dict[str, Any]]) -> str | None:
    by_date: dict[str, str] = {}
    for row in rows:
        previous = by_date.get(row["market_date"])
        if previous is not None and previous != row["payload_checksum"]:
            return f"CONFLICTING_DUPLICATE_DATE:{row['market_date']}"
        by_date[row["market_date"]] = row["payload_checksum"]
    return None


def _float_or_none(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _int_like(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    number = float(value)
    return int(number) if number.is_integer() else None
