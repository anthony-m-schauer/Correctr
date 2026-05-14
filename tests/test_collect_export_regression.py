from __future__ import annotations

from correctr.database import (
    fetch_correction_event_by_id,
    fetch_trusted_correction_events,
    save_collect_mode_manual_correction,
)


def test_collect_mode_manual_helper_survives_export_database_changes(tmp_path):
    db_path = tmp_path / "corrections.sqlite"

    event_id = save_collect_mode_manual_correction(
        original_text="This is yuet anothr example.",
        corrected_text="This is yet another example.",
        database_path=db_path,
    )

    event = fetch_correction_event_by_id(event_id, database_path=db_path)

    assert event is not None
    assert event["source"] == "manual"
    assert event["engine_version"] == "collect_mode_manual_v0.1"
    assert event["review_status"] == "accepted"
    assert event["reviewed_at"] is not None
    assert event["original_text"] == "This is yuet anothr example."
    assert event["corrected_text"] == "This is yet another example."


def test_collect_mode_manual_helper_exports_as_trusted(tmp_path):
    db_path = tmp_path / "corrections.sqlite"

    event_id = save_collect_mode_manual_correction(
        original_text="bad sentnce",
        corrected_text="bad sentence",
        database_path=db_path,
    )

    trusted_ids = [
        event["id"]
        for event in fetch_trusted_correction_events(database_path=db_path)
    ]

    assert trusted_ids == [event_id]
