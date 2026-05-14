from __future__ import annotations

import pytest

from correctr.database import (
    fetch_correction_event_by_id,
    fetch_trusted_correction_events,
    save_collect_mode_manual_correction,
)


def test_collect_mode_manual_correction_is_saved_as_trusted_manual_event(tmp_path):
    db_path = tmp_path / "corrections.sqlite"

    event_id = save_collect_mode_manual_correction(
        original_text="Laso I ma making many examlpe sentnces.",
        corrected_text="Also I am making many example sentences.",
        database_path=db_path,
    )

    event = fetch_correction_event_by_id(event_id, database_path=db_path)

    assert event["source"] == "manual"
    assert event["engine_version"] == "collect_mode_manual_v0.1"
    assert event["review_status"] == "accepted"
    assert event["reviewed_at"] is not None
    assert event["original_text"] == "Laso I ma making many examlpe sentnces."
    assert event["corrected_text"] == "Also I am making many example sentences."


def test_collect_mode_manual_correction_appears_in_trusted_fetch(tmp_path):
    db_path = tmp_path / "corrections.sqlite"

    event_id = save_collect_mode_manual_correction(
        original_text="shiuld this not also be abl eto fix this?",
        corrected_text="Should this not also be able to fix this?",
        database_path=db_path,
    )

    trusted_ids = [
        event["id"]
        for event in fetch_trusted_correction_events(database_path=db_path)
    ]

    assert trusted_ids == [event_id]


def test_collect_mode_manual_correction_rejects_blank_text(tmp_path):
    db_path = tmp_path / "corrections.sqlite"

    with pytest.raises(ValueError, match="corrected_text cannot be blank"):
        save_collect_mode_manual_correction(
            original_text="bad text",
            corrected_text="   ",
            database_path=db_path,
        )
