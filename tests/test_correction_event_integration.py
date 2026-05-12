from correctr.correction_engine import correct_text_detailed
from correctr.database import (
    fetch_recent_correction_events,
    save_dictionary_correction_result,
    save_manual_correction,
)


def test_dictionary_correction_result_can_be_saved(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"
    result = correct_text_detailed("testig misakes")

    event_id = save_dictionary_correction_result(result, database_path=db_path)

    assert event_id == 1


def test_dictionary_event_source_is_saved_as_dictionary(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"
    result = correct_text_detailed("testig")

    save_dictionary_correction_result(result, database_path=db_path)
    events = fetch_recent_correction_events(limit=1, database_path=db_path)

    assert events[0]["source"] == "dictionary"


def test_dictionary_event_saves_original_and_corrected_text(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"
    result = correct_text_detailed("testig misakes")

    save_dictionary_correction_result(result, database_path=db_path)
    events = fetch_recent_correction_events(limit=1, database_path=db_path)

    assert events[0]["original_text"] == "testig misakes"
    assert events[0]["corrected_text"] == "testing mistakes"
    assert events[0]["changed"] is True


def test_dictionary_event_saves_correction_records_json(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"
    result = correct_text_detailed("testig")

    save_dictionary_correction_result(result, database_path=db_path)
    events = fetch_recent_correction_events(limit=1, database_path=db_path)

    assert events[0]["corrections"] == [
        {
            "original": "testig",
            "corrected": "testing",
            "start_index": 0,
            "end_index": 6,
            "reason": "known_typo_dictionary",
        }
    ]


def test_dictionary_event_saves_engine_version(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"
    result = correct_text_detailed("testig")

    save_dictionary_correction_result(result, database_path=db_path)
    events = fetch_recent_correction_events(limit=1, database_path=db_path)

    assert events[0]["engine_version"] == result.engine_version


def test_no_change_dictionary_result_is_not_saved(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"
    result = correct_text_detailed("These words are already correct.")

    event_id = save_dictionary_correction_result(result, database_path=db_path)
    events = fetch_recent_correction_events(limit=10, database_path=db_path)

    assert event_id is None
    assert events == []


def test_manual_correction_saving_still_works(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"

    save_manual_correction(
        original_text="shiuld this not also be abl eto fix this?",
        corrected_text="Should this not also be able to fix this?",
        database_path=db_path,
    )

    events = fetch_recent_correction_events(limit=1, database_path=db_path)

    assert events[0]["source"] == "manual"
    assert events[0]["original_text"] == "shiuld this not also be abl eto fix this?"
    assert events[0]["corrected_text"] == "Should this not also be able to fix this?"
