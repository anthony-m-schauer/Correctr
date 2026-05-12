"""
Correctr Database Layer

Purpose:
    Provides the local SQLite correction event foundation.

Current scope:
    Supports dictionary, manual, and AI/context correction event sources.

This module stores correction events locally so future layers can use them for:
    - manual teach-back
    - personal correction memory
    - future LLM correction logging
    - future neural ranker training data

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
                notes TEXT NOT NULL DEFAULT ''
            )
            """
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

    Returns:
        Inserted row id.
    """
    _validate_source(source)

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
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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

    This function does not make app/hotkey workflow call AI. It only provides
    a clean logging path for scripts or future orchestrator work.
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
) -> int:
    """
    Saves a manual teach-back correction.

    This is the first simple way to capture useful training data when Correctr
    fails or produces an incomplete correction.
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
    )


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
                notes
            FROM correction_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [_row_to_event(row) for row in rows]


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


def _utc_timestamp() -> str:
    """
    Returns a UTC timestamp suitable for SQLite text storage.
    """
    return datetime.now(UTC).isoformat(timespec="seconds")
