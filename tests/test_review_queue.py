from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from correctr.database import (
    fetch_correction_event_by_id,
    fetch_unreviewed_correction_events,
    mark_correction_event_reviewed,
    save_manual_correction_from_event,
)


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
    source: str = "ai_context",
    original_text: str = "Laso I ma making many examlpe sentnces.",
    corrected_text: str = "Lasso I am making many example sentences.",
    review_status: str | None = "unreviewed",
    corrections_json: str = "[]",
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
            corrections_json,
            "orchestrator_v0.2:ai_context",
            "Saved from test.",
            review_status,
            None,
            None,
            "",
        ),
    )
    conn.commit()
    event_id = int(cursor.lastrowid)
    conn.close()
    return event_id


def test_fetch_unreviewed_events_includes_unreviewed_status(tmp_path: Path) -> None:
    db_path = create_test_db(tmp_path)
    event_id = insert_event(db_path, review_status="unreviewed")

    events = fetch_unreviewed_correction_events(database_path=db_path)

    assert [event["id"] for event in events] == [event_id]


def test_fetch_unreviewed_events_treats_null_as_unreviewed(tmp_path: Path) -> None:
    db_path = create_test_db(tmp_path)
    event_id = insert_event(db_path, review_status=None)

    events = fetch_unreviewed_correction_events(database_path=db_path)

    assert [event["id"] for event in events] == [event_id]


def test_mark_event_accepted(tmp_path: Path) -> None:
    db_path = create_test_db(tmp_path)
    event_id = insert_event(db_path)

    mark_correction_event_reviewed(
        event_id=event_id,
        review_status="accepted",
        database_path=db_path,
    )

    event = fetch_correction_event_by_id(event_id, database_path=db_path)
    assert event is not None
    assert event["review_status"] == "accepted"
    assert event["reviewed_at"] is not None


def test_mark_event_rejected(tmp_path: Path) -> None:
    db_path = create_test_db(tmp_path)
    event_id = insert_event(db_path)

    mark_correction_event_reviewed(
        event_id=event_id,
        review_status="rejected",
        database_path=db_path,
    )

    event = fetch_correction_event_by_id(event_id, database_path=db_path)
    assert event is not None
    assert event["review_status"] == "rejected"


def test_mark_event_test_event(tmp_path: Path) -> None:
    db_path = create_test_db(tmp_path)
    event_id = insert_event(db_path)

    mark_correction_event_reviewed(
        event_id=event_id,
        review_status="test_event",
        database_path=db_path,
    )

    event = fetch_correction_event_by_id(event_id, database_path=db_path)
    assert event is not None
    assert event["review_status"] == "test_event"


def test_mark_event_uncertain(tmp_path: Path) -> None:
    db_path = create_test_db(tmp_path)
    event_id = insert_event(db_path)

    mark_correction_event_reviewed(
        event_id=event_id,
        review_status="uncertain",
        database_path=db_path,
    )

    event = fetch_correction_event_by_id(event_id, database_path=db_path)
    assert event is not None
    assert event["review_status"] == "uncertain"


def test_skip_behavior_leaves_event_unreviewed_when_no_update_is_called(tmp_path: Path) -> None:
    db_path = create_test_db(tmp_path)
    event_id = insert_event(db_path)

    event = fetch_correction_event_by_id(event_id, database_path=db_path)

    assert event is not None
    assert event["review_status"] == "unreviewed"
    assert len(fetch_unreviewed_correction_events(database_path=db_path)) == 1


def test_fix_creates_linked_manual_event_and_marks_original_manually_corrected(tmp_path: Path) -> None:
    db_path = create_test_db(tmp_path)
    bad_event_id = insert_event(db_path)

    manual_event_id = save_manual_correction_from_event(
        event_id=bad_event_id,
        corrected_text="Also I am making many example sentences.",
        database_path=db_path,
    )

    bad_event = fetch_correction_event_by_id(bad_event_id, database_path=db_path)
    manual_event = fetch_correction_event_by_id(manual_event_id, database_path=db_path)

    assert bad_event is not None
    assert manual_event is not None
    assert bad_event["review_status"] == "manually_corrected"
    assert bad_event["reviewed_at"] is not None
    assert manual_event["source"] == "manual"
    assert manual_event["review_status"] == "accepted"
    assert manual_event["linked_event_id"] == bad_event_id
    assert manual_event["original_text"] == bad_event["original_text"]
    assert manual_event["corrected_text"] == "Also I am making many example sentences."
    assert manual_event["engine_version"] == "review_queue_manual_v0.1"


def test_fix_rejects_blank_manual_correction(tmp_path: Path) -> None:
    db_path = create_test_db(tmp_path)
    bad_event_id = insert_event(db_path)

    with pytest.raises(ValueError):
        save_manual_correction_from_event(
            event_id=bad_event_id,
            corrected_text="   ",
            database_path=db_path,
        )
