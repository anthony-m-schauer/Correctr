from correctr.database import (
    fetch_recent_correction_events,
    save_ai_context_correction_result,
)
from correctr.llm_engine import correct_with_ai_context


def test_ai_context_result_can_be_saved_to_database(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"
    result = correct_with_ai_context(
        "shiuld this not also be abl eto fix this?",
        provider_mode="mock",
    )

    event_id = save_ai_context_correction_result(result, database_path=db_path)

    assert event_id == 1


def test_ai_context_event_saves_source_original_corrected_and_engine_version(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"
    result = correct_with_ai_context(
        "shiuld this not also be abl eto fix this?",
        provider_mode="mock",
    )

    save_ai_context_correction_result(result, database_path=db_path)
    events = fetch_recent_correction_events(limit=1, database_path=db_path)

    assert events[0]["source"] == "ai_context"
    assert events[0]["original_text"] == "shiuld this not also be abl eto fix this?"
    assert events[0]["corrected_text"] == "Should this not also be able to fix this?"
    assert events[0]["engine_version"] == result.engine_version
    assert events[0]["changed"] is True


def test_ai_context_event_saves_structured_correction_records(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"
    result = correct_with_ai_context(
        "shiuld this not also be abl eto fix this?",
        provider_mode="mock",
    )

    save_ai_context_correction_result(result, database_path=db_path)
    events = fetch_recent_correction_events(limit=1, database_path=db_path)

    assert events[0]["corrections"] == result.corrections
    assert events[0]["corrections"][0]["reason"] == "mock_ai_context"
    assert events[0]["corrections"][0]["provider"] == "mock"


def test_no_change_ai_context_result_is_not_saved(tmp_path):
    db_path = tmp_path / "test_corrections.sqlite"
    result = correct_with_ai_context("This sentence should not change.", provider_mode="mock")

    event_id = save_ai_context_correction_result(result, database_path=db_path)
    events = fetch_recent_correction_events(limit=10, database_path=db_path)

    assert event_id is None
    assert events == []
