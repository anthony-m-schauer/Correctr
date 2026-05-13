from __future__ import annotations

import sqlite3
from pathlib import Path

from correctr.database import fetch_trusted_correction_events


def create_test_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "corrections.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE correction_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            source TEXT NOT NULL,
            original_text TEXT NOT NULL,
            corrected_text TEXT NOT NULL,
            changed INTEGER NOT NULL CHECK (changed IN (0, 1)),
            corrections_json TEXT NOT NULL DEFAULT '[]',
            engine_version TEXT NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            review_status TEXT DEFAULT 'unreviewed',
            reviewed_at TEXT,
            linked_event_id INTEGER,
            review_notes TEXT DEFAULT ''
        )
        """
    )
    conn.commit()
    conn.close()
    return db_path


def insert_event(
    db_path: Path,
    *,
    source: str,
    review_status: str | None,
    original_text: str = "wrong text",
    corrected_text: str = "right text",
    linked_event_id: int | None = None,
) -> int:
    conn = sqlite3.connect(db_path)
    cursor = conn.execute(
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
            "2026-05-12T22:09:23+00:00",
            source,
            original_text,
            corrected_text,
            1,
            "[]",
            "test_engine",
            "test note",
            review_status,
            None,
            linked_event_id,
            "",
        ),
    )
    conn.commit()
    event_id = int(cursor.lastrowid)
    conn.close()
    return event_id


def test_trusted_fetch_includes_accepted_manual_dictionary_and_ai_rows(tmp_path: Path) -> None:
    db_path = create_test_db(tmp_path)
    manual_id = insert_event(db_path, source="manual", review_status="accepted")
    dictionary_id = insert_event(db_path, source="dictionary", review_status="accepted")
    ai_id = insert_event(db_path, source="ai_context", review_status="accepted")

    trusted_ids = [event["id"] for event in fetch_trusted_correction_events(database_path=db_path)]

    assert trusted_ids == [manual_id, dictionary_id, ai_id]


def test_trusted_fetch_can_exclude_accepted_ai_rows_when_requested(tmp_path: Path) -> None:
    db_path = create_test_db(tmp_path)
    manual_id = insert_event(db_path, source="manual", review_status="accepted")
    dictionary_id = insert_event(db_path, source="dictionary", review_status="accepted")
    insert_event(db_path, source="ai_context", review_status="accepted")

    trusted_ids = [
        event["id"]
        for event in fetch_trusted_correction_events(
            database_path=db_path,
            include_accepted_ai=False,
        )
    ]

    assert trusted_ids == [manual_id, dictionary_id]


def test_trusted_fetch_excludes_rejected_test_uncertain_unreviewed_and_null_rows(tmp_path: Path) -> None:
    db_path = create_test_db(tmp_path)
    accepted_id = insert_event(db_path, source="manual", review_status="accepted")
    insert_event(db_path, source="manual", review_status="rejected")
    insert_event(db_path, source="manual", review_status="test_event")
    insert_event(db_path, source="manual", review_status="uncertain")
    insert_event(db_path, source="manual", review_status="unreviewed")
    insert_event(db_path, source="manual", review_status=None)
    insert_event(db_path, source="ai_context", review_status="unreviewed")

    trusted_ids = [event["id"] for event in fetch_trusted_correction_events(database_path=db_path)]

    assert trusted_ids == [accepted_id]


def test_trusted_fetch_excludes_original_manually_corrected_event(tmp_path: Path) -> None:
    db_path = create_test_db(tmp_path)
    original_id = insert_event(
        db_path,
        source="ai_context",
        review_status="manually_corrected",
        original_text="Laso I ma making many examlpe sentnces.",
        corrected_text="Lasso I am making many example sentences.",
    )
    manual_id = insert_event(
        db_path,
        source="manual",
        review_status="accepted",
        original_text="Laso I ma making many examlpe sentnces.",
        corrected_text="Also I am making many example sentences.",
        linked_event_id=original_id,
    )

    trusted_ids = [event["id"] for event in fetch_trusted_correction_events(database_path=db_path)]

    assert trusted_ids == [manual_id]
