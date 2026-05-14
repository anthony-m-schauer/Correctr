from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from correctr.database import (
    fetch_trusted_correction_events,
    save_correction_event,
)
from scripts.export_trusted_corrections import export_trusted_corrections


def test_trusted_fetch_includes_accepted_manual_event(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    event_id = save_correction_event(
        original_text="yuet",
        corrected_text="yet",
        source="manual",
        engine_version="test",
        review_status="accepted",
        database_path=db_path,
    )

    trusted = fetch_trusted_correction_events(database_path=db_path)

    assert [event["id"] for event in trusted] == [event_id]


def test_trusted_fetch_includes_linked_manual_teach_back_event(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    bad_event_id = save_correction_event(
        original_text="Laso I ma making many examlpe sentnces.",
        corrected_text="Lasso I am making many example sentences.",
        source="ai_context",
        engine_version="test_ai",
        review_status="manually_corrected",
        database_path=db_path,
    )
    manual_event_id = save_correction_event(
        original_text="Laso I ma making many examlpe sentnces.",
        corrected_text="Also I am making many example sentences.",
        source="manual",
        engine_version="review_queue_manual_v0.1",
        review_status="accepted",
        linked_event_id=bad_event_id,
        database_path=db_path,
    )

    trusted = fetch_trusted_correction_events(database_path=db_path)

    assert [event["id"] for event in trusted] == [manual_event_id]
    assert trusted[0]["linked_event_id"] == bad_event_id


def test_trusted_fetch_excludes_unsafe_statuses_and_unreviewed_ai(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    accepted_id = save_correction_event(
        original_text="bad",
        corrected_text="good",
        source="manual",
        engine_version="test",
        review_status="accepted",
        database_path=db_path,
    )
    for status in ["rejected", "test_event", "uncertain", "unreviewed"]:
        save_correction_event(
            original_text=f"bad {status}",
            corrected_text=f"good {status}",
            source="manual",
            engine_version="test",
            review_status=status,
            database_path=db_path,
        )
    save_correction_event(
        original_text="ai bad",
        corrected_text="ai maybe good",
        source="ai_context",
        engine_version="test_ai",
        review_status="unreviewed",
        database_path=db_path,
    )

    trusted = fetch_trusted_correction_events(database_path=db_path)

    assert [event["id"] for event in trusted] == [accepted_id]


def test_trusted_fetch_treats_null_review_status_as_unreviewed(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.sqlite"
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
                created_at, source, original_text, corrected_text, changed,
                corrections_json, engine_version, notes, review_status,
                reviewed_at, linked_event_id, review_notes
            )
            VALUES ('2026-05-13T00:00:00+00:00', 'manual', 'bad', 'good', 1,
                    '[]', 'legacy', '', NULL, NULL, NULL, '')
            """
        )

    trusted = fetch_trusted_correction_events(database_path=db_path)

    assert trusted == []


def test_trusted_fetch_excludes_blank_and_unchanged_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    valid_id = save_correction_event(
        original_text="normla",
        corrected_text="normal",
        source="manual",
        engine_version="test",
        review_status="accepted",
        database_path=db_path,
    )
    save_correction_event(
        original_text="   ",
        corrected_text="normal",
        source="manual",
        engine_version="test",
        review_status="accepted",
        database_path=db_path,
    )
    save_correction_event(
        original_text="same",
        corrected_text="same",
        source="manual",
        engine_version="test",
        review_status="accepted",
        database_path=db_path,
    )

    trusted = fetch_trusted_correction_events(database_path=db_path)

    assert [event["id"] for event in trusted] == [valid_id]


def test_trusted_fetch_deduplicates_exact_pairs(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    first_id = save_correction_event(
        original_text="anothr",
        corrected_text="another",
        source="manual",
        engine_version="test",
        review_status="accepted",
        database_path=db_path,
    )
    save_correction_event(
        original_text="anothr",
        corrected_text="another",
        source="manual",
        engine_version="test",
        review_status="accepted",
        database_path=db_path,
    )

    trusted = fetch_trusted_correction_events(database_path=db_path)

    assert [event["id"] for event in trusted] == [first_id]


def test_export_script_writes_jsonl_csv_and_report(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    export_dir = tmp_path / "exports"
    save_correction_event(
        original_text="yuet",
        corrected_text="yet",
        source="manual",
        engine_version="collect_mode_manual_v0.1",
        review_status="accepted",
        database_path=db_path,
    )
    save_correction_event(
        original_text="bad ai",
        corrected_text="worse ai",
        source="ai_context",
        engine_version="test_ai",
        review_status="rejected",
        database_path=db_path,
    )

    result = export_trusted_corrections(
        database_path=db_path,
        export_dir=export_dir,
    )

    assert result["trusted_count"] == 1
    assert result["total_count"] == 2
    assert result["jsonl_path"].exists()
    assert result["csv_path"].exists()
    assert result["report_path"].exists()

    jsonl_rows = [json.loads(line) for line in result["jsonl_path"].read_text(encoding="utf-8").splitlines()]
    assert jsonl_rows[0]["original_text"] == "yuet"
    assert jsonl_rows[0]["corrected_text"] == "yet"

    with result["csv_path"].open("r", encoding="utf-8", newline="") as file:
        csv_rows = list(csv.DictReader(file))
    assert csv_rows[0]["original_text"] == "yuet"
    assert csv_rows[0]["corrected_text"] == "yet"

    report_text = result["report_path"].read_text(encoding="utf-8")
    assert "Rows exported as trusted: 1" in report_text
    assert "Rows excluded from trusted export: 1" in report_text
    assert "Trusted dataset is too small for neural ranker training" in report_text


def test_export_report_warns_when_unreviewed_ai_events_exist(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    export_dir = tmp_path / "exports"
    save_correction_event(
        original_text="yuet",
        corrected_text="yet",
        source="manual",
        engine_version="collect_mode_manual_v0.1",
        review_status="accepted",
        database_path=db_path,
    )
    save_correction_event(
        original_text="ai typo",
        corrected_text="ai correction",
        source="ai_context",
        engine_version="test_ai",
        review_status="unreviewed",
        database_path=db_path,
    )

    result = export_trusted_corrections(database_path=db_path, export_dir=export_dir)

    report_text = result["report_path"].read_text(encoding="utf-8")
    assert "Unreviewed AI/context events exist and are excluded from trusted export." in report_text
