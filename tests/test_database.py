import json
import sqlite3

import pytest

from correctr.database import (
    fetch_recent_correction_events,
    initialize_database,
    save_correction_event,
    save_manual_correction,
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
