"""
Correctr Database Layer

Purpose:
    Provides the local SQLite correction event foundation and review workflow.

Current scope:
    Manual Rejection Review_v0.1 Recent Event Review + Teach-Back.

This module stores correction events locally so future layers can use them for:
    - manual teach-back
    - personal correction memory
    - future LLM correction logging
    - future neural ranker training data
    - review labels for data quality

This module does not add neural ranking, suggestion UI, advanced spellcheck,
or app/hotkey behavior changes.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "corrections.sqlite"

ALLOWED_SOURCES = {
    "dictionary",
    "manual",
    "ai_context",
    "future_llm",
    "future_memory",
    "future_ranker",
}

ALLOWED_REVIEW_STATUSES = {
    "unreviewed",
    "accepted",
    "rejected",
    "manually_corrected",
    "test_event",
    "uncertain",
}

DEFAULT_MANUAL_ENGINE_VERSION = "manual_capture_v0.1"


def get_database_path(database_path: str | Path | None = None) -> Path:
    """
    Returns the SQLite database path.

    Args:
        database_path:
            Optional override path. Tests should pass a temporary path so they
            do not write to the real project database.

    Returns:
        Path to the SQLite database.
    """
    if database_path is None:
        return DEFAULT_DATABASE_PATH

    return Path(database_path)


def initialize_database(database_path: str | Path | None = None) -> Path:
    """
    Creates the SQLite database and correction_events table if needed.

    This also performs a small safe migration for review fields added in
    Manual Rejection Review_v0.1. Existing rows are preserved.

    Args:
        database_path:
            Optional override path.

    Returns:
        Path to the initialized database.
    """
    db_path = get_database_path(database_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with _connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS correction_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source TEXT NOT NULL,
                original_text TEXT NOT NULL,
                corrected_text TEXT NOT NULL,
                changed INTEGER NOT NULL CHECK (changed IN (0, 1)),
                corrections_json TEXT NOT NULL DEFAULT '[]',
                engine_version TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                review_status TEXT NOT NULL DEFAULT 'unreviewed',
                reviewed_at TEXT,
                linked_event_id INTEGER,
                review_notes TEXT NOT NULL DEFAULT ''
            )
            """
        )

        _add_column_if_missing(
            connection,
            table_name="correction_events",
            column_name="review_status",
            column_definition="TEXT NOT NULL DEFAULT 'unreviewed'",
        )
        _add_column_if_missing(
            connection,
            table_name="correction_events",
            column_name="reviewed_at",
            column_definition="TEXT",
        )
        _add_column_if_missing(
            connection,
            table_name="correction_events",
            column_name="linked_event_id",
            column_definition="INTEGER",
        )
        _add_column_if_missing(
            connection,
            table_name="correction_events",
            column_name="review_notes",
            column_definition="TEXT NOT NULL DEFAULT ''",
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_correction_events_created_at
            ON correction_events (created_at)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_correction_events_source
            ON correction_events (source)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_correction_events_review_status
            ON correction_events (review_status)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_correction_events_linked_event_id
            ON correction_events (linked_event_id)
            """
        )

    return db_path


def save_correction_event(
    *,
    original_text: str,
    corrected_text: str,
    source: str,
    changed: bool | None = None,
    corrections: list[dict[str, Any]] | None = None,
    engine_version: str = "unknown",
    notes: str = "",
    database_path: str | Path | None = None,
    review_status: str = "unreviewed",
    linked_event_id: int | None = None,
    review_notes: str = "",
) -> int:
    """
    Saves a correction event to SQLite.

    Args:
        original_text:
            Text before correction.
        corrected_text:
            Text after correction.
        source:
            Correction source. Supported values include:
            dictionary, manual, ai_context, future_llm, future_memory, future_ranker.
        changed:
            Optional explicit changed flag. If omitted, it is inferred from
            original_text != corrected_text.
        corrections:
            Optional structured correction records.
        engine_version:
            Version/name of the correction source.
        notes:
            Optional human note.
        database_path:
            Optional override database path.
        review_status:
            Review status for the event. Defaults to unreviewed.
        linked_event_id:
            Optional event id this event is linked to, such as a manual
            correction created from a bad automatic event.
        review_notes:
            Optional review note.

    Returns:
        Inserted row id.
    """
    _validate_source(source)
    _validate_review_status(review_status)

    if changed is None:
        changed = original_text != corrected_text

    corrections_json = _serialize_corrections(corrections)

    db_path = initialize_database(database_path)

    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO correction_events (
                created_at,
                source,
                original_text,
                corrected_text,
                changed,
                corrections_json,
                engine_version,
                notes,
                review_status,
                reviewed_at,
                linked_event_id,
                review_notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _utc_timestamp(),
                source,
                original_text,
                corrected_text,
                int(changed),
                corrections_json,
                engine_version,
                notes,
                review_status,
                _utc_timestamp() if review_status != "unreviewed" else None,
                linked_event_id,
                review_notes,
            ),
        )

        return int(cursor.lastrowid)


def save_dictionary_correction_result(
    correction_result: Any,
    *,
    database_path: str | Path | None = None,
    notes: str = "Saved from dictionary correction result.",
) -> int | None:
    """
    Saves a changed dictionary CorrectionResult to SQLite.

    Returns inserted event id if saved, or None if the result had no change.
    """
    if not correction_result.changed:
        return None

    return save_correction_event(
        original_text=correction_result.original_text,
        corrected_text=correction_result.corrected_text,
        source="dictionary",
        changed=correction_result.changed,
        corrections=correction_result.corrections,
        engine_version=correction_result.engine_version,
        notes=notes,
        database_path=database_path,
    )


def save_ai_context_correction_result(
    correction_result: Any,
    *,
    database_path: str | Path | None = None,
    notes: str = "Saved from AI/context correction result.",
) -> int | None:
    """
    Saves a changed AI/context CorrectionResult to SQLite.

    Returns inserted event id if saved, or None if the result had no change.
    """
    if not correction_result.changed:
        return None

    return save_correction_event(
        original_text=correction_result.original_text,
        corrected_text=correction_result.corrected_text,
        source="ai_context",
        changed=correction_result.changed,
        corrections=correction_result.corrections,
        engine_version=correction_result.engine_version,
        notes=notes,
        database_path=database_path,
    )


def save_manual_correction(
    *,
    original_text: str,
    corrected_text: str,
    notes: str = "",
    database_path: str | Path | None = None,
    linked_event_id: int | None = None,
) -> int:
    """
    Saves a manual teach-back correction.

    This captures useful training data when Correctr fails or produces an
    incomplete correction.
    """
    return save_correction_event(
        original_text=original_text,
        corrected_text=corrected_text,
        source="manual",
        changed=original_text != corrected_text,
        corrections=[],
        engine_version=DEFAULT_MANUAL_ENGINE_VERSION,
        notes=notes,
        database_path=database_path,
        linked_event_id=linked_event_id,
    )


def save_manual_correction_from_event(
    *,
    event_id: int,
    corrected_text: str,
    notes: str | None = None,
    database_path: str | Path | None = None,
) -> int:
    """
    Saves a trusted manual teach-back correction using the original text from an event.

    This is the review-queue fix path:
    - the original raw automatic event is preserved
    - the original event is marked review_status = manually_corrected
    - a new source = manual event is created and linked back to the original
    - the new manual event is marked review_status = accepted

    The original manually_corrected event should be treated as failure/history data.
    The linked accepted manual event is the trusted correction example.

    Args:
        event_id:
            Existing event that was wrong or incomplete.
        corrected_text:
            User-provided intended correction.
        notes:
            Optional note for the new manual event.
        database_path:
            Optional override database path.

    Returns:
        Inserted manual correction event id.
    """
    intended_text = corrected_text.strip()

    if not intended_text:
        raise ValueError("corrected_text cannot be blank.")

    event = fetch_correction_event_by_id(event_id, database_path=database_path)

    if event is None:
        raise ValueError(f"No correction event found with id {event_id}.")

    manual_notes = notes or f"Manual correction from review queue event ID {event_id}."

    manual_event_id = save_correction_event(
        original_text=event["original_text"],
        corrected_text=intended_text,
        source="manual",
        changed=event["original_text"] != intended_text,
        corrections=[],
        engine_version="review_queue_manual_v0.1",
        notes=manual_notes,
        database_path=database_path,
        review_status="accepted",
        linked_event_id=event_id,
        review_notes=manual_notes,
    )

    mark_correction_event_reviewed(
        event_id=event_id,
        review_status="manually_corrected",
        review_notes=f"Manual correction saved as linked event ID {manual_event_id}.",
        database_path=database_path,
    )

    return manual_event_id


def fetch_recent_correction_events(
    *,
    limit: int = 10,
    database_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """
    Fetches recent correction events.

    Args:
        limit:
            Maximum number of events to return.
        database_path:
            Optional override database path.

    Returns:
        List of event dictionaries ordered newest first.
    """
    if limit < 1:
        raise ValueError("limit must be at least 1.")

    db_path = initialize_database(database_path)

    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                id,
                created_at,
                source,
                original_text,
                corrected_text,
                changed,
                corrections_json,
                engine_version,
                notes,
                review_status,
                reviewed_at,
                linked_event_id,
                review_notes
            FROM correction_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [_row_to_event(row) for row in rows]


def fetch_unreviewed_correction_events(
    *,
    limit: int | None = None,
    database_path: str | Path | None = None,
    oldest_first: bool = True,
) -> list[dict[str, Any]]:
    """
    Fetches correction events that still need review.

    NULL or blank review_status values are treated as unreviewed so older
    migrated rows cannot bypass the review queue.

    Args:
        limit:
            Optional maximum number of events to return.
        database_path:
            Optional override database path.
        oldest_first:
            If true, review oldest unreviewed events first.

    Returns:
        List of unreviewed event dictionaries.
    """
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1.")

    order_direction = "ASC" if oldest_first else "DESC"
    limit_clause = "" if limit is None else " LIMIT ?"

    params: list[Any] = []
    if limit is not None:
        params.append(limit)

    db_path = initialize_database(database_path)

    with _connect(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT
                id,
                created_at,
                source,
                original_text,
                corrected_text,
                changed,
                corrections_json,
                engine_version,
                notes,
                review_status,
                reviewed_at,
                linked_event_id,
                review_notes
            FROM correction_events
            WHERE review_status IS NULL
               OR TRIM(review_status) = ''
               OR review_status = 'unreviewed'
            ORDER BY created_at {order_direction}, id {order_direction}
            {limit_clause}
            """,
            tuple(params),
        ).fetchall()

    return [_row_to_event(row) for row in rows]


def fetch_trusted_correction_events(
    *,
    limit: int | None = None,
    database_path: str | Path | None = None,
    include_accepted_ai: bool = True,
    oldest_first: bool = True,
    exclude_blank: bool = True,
    exclude_unchanged: bool = True,
    deduplicate_exact_pairs: bool = True,
) -> list[dict[str, Any]]:
    """
    Fetches only correction events safe for personal memory/export/ranker work.

    Trusted policy:
    - source = manual and review_status = accepted is trusted.
    - source = dictionary and review_status = accepted is trusted.
    - source = ai_context and review_status = accepted is trusted only when
      include_accepted_ai is true.
    - Original automatic rows marked manually_corrected are not trusted
      positive examples; the linked accepted manual row is trusted instead.
    - rejected, test_event, uncertain, unreviewed, blank, and NULL statuses
      are excluded.
    - Blank original/corrected text rows are excluded by default.
    - Unchanged original_text == corrected_text rows are excluded by default.
    - Exact duplicate original_text + corrected_text pairs are collapsed by default.

    Args:
        limit:
            Optional maximum number of trusted events to return after filtering.
        database_path:
            Optional override database path.
        include_accepted_ai:
            Whether explicitly accepted ai_context rows should be included.
        oldest_first:
            If true, returns oldest trusted examples first.
        exclude_blank:
            If true, excludes rows with blank original_text or corrected_text.
        exclude_unchanged:
            If true, excludes rows where original_text == corrected_text.
        deduplicate_exact_pairs:
            If true, keeps only the first exact original_text + corrected_text pair
            in the requested order. Database rows are not deleted.

    Returns:
        List of trusted correction event dictionaries.
    """
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1.")

    trusted_sources = ["manual", "dictionary"]

    if include_accepted_ai:
        trusted_sources.append("ai_context")

    placeholders = ", ".join("?" for _ in trusted_sources)
    order_direction = "ASC" if oldest_first else "DESC"

    params: list[Any] = ["accepted", *trusted_sources]

    db_path = initialize_database(database_path)

    with _connect(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT
                id,
                created_at,
                source,
                original_text,
                corrected_text,
                changed,
                corrections_json,
                engine_version,
                notes,
                review_status,
                reviewed_at,
                linked_event_id,
                review_notes
            FROM correction_events
            WHERE review_status = ?
              AND source IN ({placeholders})
            ORDER BY created_at {order_direction}, id {order_direction}
            """,
            tuple(params),
        ).fetchall()

    trusted_events: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()

    for row in rows:
        event = _row_to_event(row)
        original_text = event["original_text"]
        corrected_text = event["corrected_text"]

        if exclude_blank and (
            not original_text.strip() or not corrected_text.strip()
        ):
            continue

        if exclude_unchanged and original_text == corrected_text:
            continue

        exact_pair = (original_text, corrected_text)
        if deduplicate_exact_pairs and exact_pair in seen_pairs:
            continue

        seen_pairs.add(exact_pair)
        trusted_events.append(event)

        if limit is not None and len(trusted_events) >= limit:
            break

    return trusted_events


def fetch_all_correction_events(
    *,
    limit: int | None = None,
    database_path: str | Path | None = None,
    oldest_first: bool = True,
) -> list[dict[str, Any]]:
    """
    Fetches all correction events for local QA/reporting.

    Args:
        limit:
            Optional maximum number of events to return.
        database_path:
            Optional override database path.
        oldest_first:
            If true, returns oldest events first.

    Returns:
        List of event dictionaries.
    """
    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1.")

    order_direction = "ASC" if oldest_first else "DESC"
    limit_clause = "" if limit is None else " LIMIT ?"
    params: list[Any] = []

    if limit is not None:
        params.append(limit)

    db_path = initialize_database(database_path)

    with _connect(db_path) as connection:
        rows = connection.execute(
            f"""
            SELECT
                id,
                created_at,
                source,
                original_text,
                corrected_text,
                changed,
                corrections_json,
                engine_version,
                notes,
                review_status,
                reviewed_at,
                linked_event_id,
                review_notes
            FROM correction_events
            ORDER BY created_at {order_direction}, id {order_direction}
            {limit_clause}
            """,
            tuple(params),
        ).fetchall()

    return [_row_to_event(row) for row in rows]


def fetch_correction_event_by_id(
    event_id: int,
    *,
    database_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """
    Fetches one correction event by id.

    Returns:
        Event dictionary, or None if no matching event exists.
    """
    db_path = initialize_database(database_path)

    with _connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT
                id,
                created_at,
                source,
                original_text,
                corrected_text,
                changed,
                corrections_json,
                engine_version,
                notes,
                review_status,
                reviewed_at,
                linked_event_id,
                review_notes
            FROM correction_events
            WHERE id = ?
            """,
            (event_id,),
        ).fetchone()

    if row is None:
        return None

    return _row_to_event(row)


def mark_correction_event_reviewed(
    *,
    event_id: int,
    review_status: str,
    review_notes: str | None = None,
    database_path: str | Path | None = None,
) -> None:
    """
    Marks one correction event with a review status.

    Args:
        event_id:
            Event to update.
        review_status:
            One of unreviewed, accepted, rejected, manually_corrected,
            test_event, uncertain.
        review_notes:
            Optional review note.
        database_path:
            Optional override database path.
    """
    _validate_review_status(review_status)

    db_path = initialize_database(database_path)
    reviewed_at = None if review_status == "unreviewed" else _utc_timestamp()

    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            UPDATE correction_events
            SET
                review_status = ?,
                reviewed_at = ?,
                review_notes = ?
            WHERE id = ?
            """,
            (
                review_status,
                reviewed_at,
                review_notes or "",
                event_id,
            ),
        )

        if cursor.rowcount == 0:
            raise ValueError(f"No correction event found with id {event_id}.")


def _connect(database_path: Path) -> sqlite3.Connection:
    """
    Opens a SQLite connection with row access by column name.
    """
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    """
    Converts a SQLite row into a plain dictionary.
    """
    corrections_json = row["corrections_json"]

    review_status = row["review_status"] or "unreviewed"

    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "source": row["source"],
        "original_text": row["original_text"],
        "corrected_text": row["corrected_text"],
        "changed": bool(row["changed"]),
        "corrections_json": corrections_json,
        "corrections": json.loads(corrections_json),
        "engine_version": row["engine_version"],
        "notes": row["notes"],
        "review_status": review_status,
        "reviewed_at": row["reviewed_at"],
        "linked_event_id": row["linked_event_id"],
        "review_notes": row["review_notes"] or "",
    }


def _serialize_corrections(corrections: list[dict[str, Any]] | None) -> str:
    """
    Serializes correction records to JSON.
    """
    if corrections is None:
        corrections = []

    try:
        return json.dumps(corrections, ensure_ascii=False)
    except TypeError as error:
        raise ValueError("corrections must be JSON-serializable.") from error


def _validate_source(source: str) -> None:
    """
    Validates correction event source names.
    """
    if source not in ALLOWED_SOURCES:
        allowed = ", ".join(sorted(ALLOWED_SOURCES))
        raise ValueError(f"Unsupported correction source: {source!r}. Allowed sources: {allowed}")


def _validate_review_status(review_status: str) -> None:
    """
    Validates review status names.
    """
    if review_status not in ALLOWED_REVIEW_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_REVIEW_STATUSES))
        raise ValueError(f"Unsupported review status: {review_status!r}. Allowed statuses: {allowed}")


def _utc_timestamp() -> str:
    """
    Returns a UTC timestamp suitable for SQLite text storage.
    """
    return datetime.now(UTC).isoformat(timespec="seconds")


def _add_column_if_missing(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    column_name: str,
    column_definition: str,
) -> None:
    """
    Adds a SQLite column if it is missing.

    SQLite supports ADD COLUMN for simple migration needs like this.
    """
    existing_columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }

    if column_name not in existing_columns:
        connection.execute(
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}"
        )
