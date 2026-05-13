import json
import sqlite3

import pytest

from correctr.correction_engine import correct_text_detailed
from correctr.database import (
    fetch_correction_event_by_id,
    fetch_recent_correction_events,
    initialize_database,
    mark_correction_event_reviewed,
    save_ai_context_correction_result,
    save_correction_event,
    save_dictionary_correction_result,
    save_manual_correction,
    save_manual_correction_from_event,
)


def test_database_initialization_creates_expected_table(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "correction_events" in table_names


def test_initialize_database_adds_review_columns_safely_to_existing_table(tmp_path):
    db_path = tmp_path / "old_schema.sqlite"

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE correction_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source TEXT NOT NULL,
                original_text TEXT NOT NULL,
                corrected_text TEXT NOT NULL,
                changed INTEGER NOT NULL,
                corrections_json TEXT NOT NULL DEFAULT '[]',
                engine_version TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT ''
            )
            """
        )

    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(correction_events)").fetchall()
        }

    assert "review_status" in columns
    assert "reviewed_at" in columns
    assert "linked_event_id" in columns
    assert "review_notes" in columns


def test_manual_correction_save_works(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    event_id = save_manual_correction(
        original_text="shiuld this not also be abl eto fix this?",
        corrected_text="Should this not also be able to fix this?",
        notes="manual teach-back test",
        database_path=db_path,
    )

    assert event_id == 1


def test_saved_original_and_corrected_text_can_be_fetched(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    save_manual_correction(
        original_text="shiuld this not also be abl eto fix this?",
        corrected_text="Should this not also be able to fix this?",
        database_path=db_path,
    )

    events = fetch_recent_correction_events(limit=1, database_path=db_path)

    assert len(events) == 1
    assert events[0]["original_text"] == "shiuld this not also be abl eto fix this?"
    assert events[0]["corrected_text"] == "Should this not also be able to fix this?"


def test_source_is_stored_correctly_for_manual_correction(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    save_manual_correction(
        original_text="bad text",
        corrected_text="good text",
        database_path=db_path,
    )

    events = fetch_recent_correction_events(limit=1, database_path=db_path)

    assert events[0]["source"] == "manual"


def test_corrections_json_can_store_structured_correction_data(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    corrections = [
        {
            "original": "testig",
            "corrected": "testing",
            "start_index": 0,
            "end_index": 6,
            "reason": "known_typo_dictionary",
        }
    ]

    save_correction_event(
        original_text="testig",
        corrected_text="testing",
        source="dictionary",
        corrections=corrections,
        engine_version="local_dictionary_v0.3",
        database_path=db_path,
    )

    events = fetch_recent_correction_events(limit=1, database_path=db_path)

    assert json.loads(events[0]["corrections_json"]) == corrections
    assert events[0]["corrections"] == corrections
    assert events[0]["engine_version"] == "local_dictionary_v0.3"


def test_changed_flag_is_inferred_when_not_provided(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    save_correction_event(
        original_text="testig",
        corrected_text="testing",
        source="dictionary",
        engine_version="local_dictionary_v0.3",
        database_path=db_path,
    )

    events = fetch_recent_correction_events(limit=1, database_path=db_path)

    assert events[0]["changed"] is True


def test_fetch_recent_correction_events_returns_newest_first(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    save_manual_correction(
        original_text="first bad",
        corrected_text="first good",
        database_path=db_path,
    )
    save_manual_correction(
        original_text="second bad",
        corrected_text="second good",
        database_path=db_path,
    )

    events = fetch_recent_correction_events(limit=2, database_path=db_path)

    assert events[0]["original_text"] == "second bad"
    assert events[1]["original_text"] == "first bad"


def test_invalid_source_raises_clear_error(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    with pytest.raises(ValueError, match="Unsupported correction source"):
        save_correction_event(
            original_text="bad",
            corrected_text="good",
            source="unsupported_source",
            database_path=db_path,
        )


def test_limit_must_be_positive(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    with pytest.raises(ValueError, match="limit must be at least 1"):
        fetch_recent_correction_events(limit=0, database_path=db_path)


def test_new_events_default_to_unreviewed(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    save_manual_correction(
        original_text="bad",
        corrected_text="good",
        database_path=db_path,
    )

    event = fetch_recent_correction_events(limit=1, database_path=db_path)[0]

    assert event["review_status"] == "unreviewed"
    assert event["reviewed_at"] is None
    assert event["review_notes"] == ""


def test_fetch_correction_event_by_id_works(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    event_id = save_manual_correction(
        original_text="bad",
        corrected_text="good",
        database_path=db_path,
    )

    event = fetch_correction_event_by_id(event_id, database_path=db_path)

    assert event is not None
    assert event["id"] == event_id
    assert event["original_text"] == "bad"


def test_fetch_correction_event_by_id_returns_none_for_missing_event(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    assert fetch_correction_event_by_id(999, database_path=db_path) is None


def test_mark_event_accepted_works(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    event_id = save_manual_correction(
        original_text="bad",
        corrected_text="good",
        database_path=db_path,
    )

    mark_correction_event_reviewed(
        event_id=event_id,
        review_status="accepted",
        review_notes="looks good",
        database_path=db_path,
    )

    event = fetch_correction_event_by_id(event_id, database_path=db_path)

    assert event["review_status"] == "accepted"
    assert event["reviewed_at"] is not None
    assert event["review_notes"] == "looks good"


def test_mark_event_rejected_works(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    event_id = save_manual_correction(
        original_text="bad",
        corrected_text="wrong",
        database_path=db_path,
    )

    mark_correction_event_reviewed(
        event_id=event_id,
        review_status="rejected",
        database_path=db_path,
    )

    event = fetch_correction_event_by_id(event_id, database_path=db_path)

    assert event["review_status"] == "rejected"


def test_mark_event_test_event_works(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    event_id = save_manual_correction(
        original_text="bad",
        corrected_text="good",
        database_path=db_path,
    )

    mark_correction_event_reviewed(
        event_id=event_id,
        review_status="test_event",
        database_path=db_path,
    )

    event = fetch_correction_event_by_id(event_id, database_path=db_path)

    assert event["review_status"] == "test_event"


def test_mark_event_uncertain_works(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    event_id = save_manual_correction(
        original_text="bad",
        corrected_text="maybe good",
        database_path=db_path,
    )

    mark_correction_event_reviewed(
        event_id=event_id,
        review_status="uncertain",
        database_path=db_path,
    )

    event = fetch_correction_event_by_id(event_id, database_path=db_path)

    assert event["review_status"] == "uncertain"


def test_invalid_review_status_raises_clear_error(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    event_id = save_manual_correction(
        original_text="bad",
        corrected_text="good",
        database_path=db_path,
    )

    with pytest.raises(ValueError, match="Unsupported review status"):
        mark_correction_event_reviewed(
            event_id=event_id,
            review_status="bad_status",
            database_path=db_path,
        )


def test_mark_missing_event_raises_clear_error(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    with pytest.raises(ValueError, match="No correction event found"):
        mark_correction_event_reviewed(
            event_id=999,
            review_status="accepted",
            database_path=db_path,
        )


def test_save_manual_correction_from_existing_event_works(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    bad_event_id = save_correction_event(
        original_text="Laso I ma making many examlpe sentnces.",
        corrected_text="Lasso I am making many example sentences.",
        source="ai_context",
        engine_version="orchestrator_v0.2:ai_context",
        database_path=db_path,
    )

    manual_event_id = save_manual_correction_from_event(
        event_id=bad_event_id,
        corrected_text="Also I am making many example sentences.",
        database_path=db_path,
    )

    manual_event = fetch_correction_event_by_id(manual_event_id, database_path=db_path)

    assert manual_event["source"] == "manual"
    assert manual_event["original_text"] == "Laso I ma making many examlpe sentnces."
    assert manual_event["corrected_text"] == "Also I am making many example sentences."
    assert manual_event["linked_event_id"] == bad_event_id


def test_save_manual_correction_from_missing_event_raises_error(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    with pytest.raises(ValueError, match="No correction event found"):
        save_manual_correction_from_event(
            event_id=999,
            corrected_text="Corrected text.",
            database_path=db_path,
        )


def test_original_event_can_be_marked_manually_corrected(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    bad_event_id = save_correction_event(
        original_text="Laso I ma making many examlpe sentnces.",
        corrected_text="Lasso I am making many example sentences.",
        source="ai_context",
        database_path=db_path,
    )

    save_manual_correction_from_event(
        event_id=bad_event_id,
        corrected_text="Also I am making many example sentences.",
        database_path=db_path,
    )
    mark_correction_event_reviewed(
        event_id=bad_event_id,
        review_status="manually_corrected",
        review_notes="manual correction saved",
        database_path=db_path,
    )

    bad_event = fetch_correction_event_by_id(bad_event_id, database_path=db_path)

    assert bad_event["review_status"] == "manually_corrected"
    assert bad_event["review_notes"] == "manual correction saved"


def test_existing_save_dictionary_correction_result_still_works(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    result = correct_text_detailed("testig")

    event_id = save_dictionary_correction_result(result, database_path=db_path)
    event = fetch_correction_event_by_id(event_id, database_path=db_path)

    assert event["source"] == "dictionary"
    assert event["corrected_text"] == "testing"
    assert event["review_status"] == "unreviewed"


def test_existing_ai_context_event_saving_still_works(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    class FakeResult:
        original_text = "bad"
        corrected_text = "good"
        changed = True
        corrections = [{"original": "bad", "corrected": "good"}]
        engine_version = "ai_context_test"

    event_id = save_ai_context_correction_result(FakeResult(), database_path=db_path)
    event = fetch_correction_event_by_id(event_id, database_path=db_path)

    assert event["source"] == "ai_context"
    assert event["corrected_text"] == "good"
    assert event["review_status"] == "unreviewed"


def test_legacy_nullable_review_status_is_treated_as_unreviewed(tmp_path):
    db_path = tmp_path / "legacy_nullable_review_status.sqlite"

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE correction_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                source TEXT NOT NULL,
                original_text TEXT NOT NULL,
                corrected_text TEXT NOT NULL,
                changed INTEGER NOT NULL,
                corrections_json TEXT NOT NULL DEFAULT '[]',
                engine_version TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                review_status TEXT,
                reviewed_at TEXT,
                linked_event_id INTEGER,
                review_notes TEXT
            )
            """
        )
        connection.execute(
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
            VALUES (
                '2026-05-12T00:00:00+00:00',
                'manual',
                'bad',
                'good',
                1,
                '[]',
                'legacy_test',
                '',
                NULL,
                NULL,
                NULL,
                NULL
            )
            """
        )

    event = fetch_correction_event_by_id(1, database_path=db_path)

    assert event["review_status"] == "unreviewed"
    assert event["review_notes"] == ""
