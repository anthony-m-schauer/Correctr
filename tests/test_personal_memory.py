from __future__ import annotations

from pathlib import Path

from correctr.correction_engine import CorrectionResult
from correctr.correction_orchestrator import correct_with_orchestration, get_event_source_for_result
from correctr.database import mark_correction_event_reviewed, save_correction_event
from correctr.personal_memory import (
    PERSONAL_MEMORY_ENGINE_VERSION,
    correct_with_personal_memory,
    find_exact_memory_match,
    find_normalized_memory_match,
    load_trusted_memory_examples,
    normalize_memory_text,
)


def add_event(
    db_path: Path,
    *,
    source: str = "manual",
    review_status: str = "accepted",
    original_text: str = "Laso I ma making many examlpe sentnces.",
    corrected_text: str = "Also I am making many example sentences.",
    engine_version: str = "manual_capture_v0.1",
) -> int:
    return save_correction_event(
        original_text=original_text,
        corrected_text=corrected_text,
        source=source,
        engine_version=engine_version,
        review_status=review_status,
        database_path=db_path,
    )


def test_load_trusted_memory_examples_includes_accepted_manual(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    event_id = add_event(db_path)

    examples = load_trusted_memory_examples(database_path=db_path)

    assert len(examples) == 1
    assert examples[0].event_id == event_id
    assert examples[0].source == "manual"
    assert examples[0].review_status == "accepted"


def test_load_trusted_memory_examples_includes_collect_mode_manual(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    event_id = add_event(
        db_path,
        engine_version="collect_mode_manual_v0.1",
        original_text="This is yuet anothr example.",
        corrected_text="This is yet another example.",
    )

    examples = load_trusted_memory_examples(database_path=db_path)

    assert [example.event_id for example in examples] == [event_id]


def test_load_trusted_memory_examples_excludes_rejected_test_uncertain_and_unreviewed(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    trusted_id = add_event(db_path, original_text="trusted bad", corrected_text="trusted good")
    add_event(db_path, review_status="rejected", original_text="rejected bad", corrected_text="rejected good")
    add_event(db_path, review_status="test_event", original_text="test bad", corrected_text="test good")
    add_event(db_path, review_status="uncertain", original_text="uncertain bad", corrected_text="uncertain good")
    add_event(db_path, review_status="unreviewed", original_text="unreviewed bad", corrected_text="unreviewed good")

    examples = load_trusted_memory_examples(database_path=db_path)

    assert [example.event_id for example in examples] == [trusted_id]


def test_load_trusted_memory_examples_excludes_accepted_ai_and_dictionary_by_default(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    manual_id = add_event(db_path, source="manual")
    add_event(db_path, source="ai_context", review_status="accepted", original_text="ai bad", corrected_text="ai good")
    add_event(db_path, source="dictionary", review_status="accepted", original_text="dict bad", corrected_text="dict good")

    examples = load_trusted_memory_examples(database_path=db_path)

    assert [example.event_id for example in examples] == [manual_id]


def test_load_trusted_memory_examples_excludes_manually_corrected_raw_history(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    raw_id = add_event(db_path, source="ai_context", review_status="unreviewed")
    add_event(
        db_path,
        source="manual",
        review_status="accepted",
        original_text="Laso I ma making many examlpe sentnces.",
        corrected_text="Also I am making many example sentences.",
        engine_version="review_queue_manual_v0.1",
    )
    mark_correction_event_reviewed(
        event_id=raw_id,
        review_status="manually_corrected",
        database_path=db_path,
    )

    examples = load_trusted_memory_examples(database_path=db_path)

    assert len(examples) == 1
    assert examples[0].source == "manual"


def test_exact_memory_match_works(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    add_event(db_path)
    examples = load_trusted_memory_examples(database_path=db_path)

    match = find_exact_memory_match(
        "Laso I ma making many examlpe sentnces.",
        examples=examples,
    )

    assert match is not None
    assert match.corrected_text == "Also I am making many example sentences."


def test_normalized_memory_match_works(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    add_event(db_path)
    examples = load_trusted_memory_examples(database_path=db_path)

    match = find_normalized_memory_match(
        "  laso   i ma making many examlpe sentnces.  ",
        examples=examples,
    )

    assert match is not None
    assert match.corrected_text == "Also I am making many example sentences."


def test_normalize_memory_text_collapses_whitespace_and_casefolds() -> None:
    assert normalize_memory_text("  Laso   I MA  ") == "laso i ma"


def test_correct_with_personal_memory_returns_correction_result_for_hit(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    event_id = add_event(db_path)

    result = correct_with_personal_memory(
        "Laso I ma making many examlpe sentnces.",
        database_path=db_path,
    )

    assert isinstance(result, CorrectionResult)
    assert result.corrected_text == "Also I am making many example sentences."
    assert result.changed is True
    assert result.engine_version == f"{PERSONAL_MEMORY_ENGINE_VERSION}:exact"
    assert result.corrections[0]["reason"] == "trusted_manual_memory"
    assert result.corrections[0]["match_type"] == "exact"
    assert result.corrections[0]["trusted_event_id"] == event_id


def test_correct_with_personal_memory_returns_normalized_match_result(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    add_event(db_path)

    result = correct_with_personal_memory(
        "  laso i ma making many examlpe sentnces.  ",
        database_path=db_path,
    )

    assert result.corrected_text == "Also I am making many example sentences."
    assert result.changed is True
    assert result.engine_version == f"{PERSONAL_MEMORY_ENGINE_VERSION}:normalized"
    assert result.corrections[0]["match_type"] == "normalized"


def test_correct_with_personal_memory_no_match_is_safe_no_change(tmp_path: Path) -> None:
    db_path = tmp_path / "corrections.sqlite"
    add_event(db_path)

    result = correct_with_personal_memory(
        "This is not in memory.",
        database_path=db_path,
    )

    assert result.corrected_text == "This is not in memory."
    assert result.changed is False
    assert result.corrections == []
    assert result.engine_version == f"{PERSONAL_MEMORY_ENGINE_VERSION}:no_match"


def test_orchestrator_can_use_memory_first_when_configured(monkeypatch) -> None:
    trusted_examples = [
        type(
            "MemoryExampleLike",
            (),
            {
                "event_id": 42,
                "original_text": "Laso I ma making many examlpe sentnces.",
                "corrected_text": "Also I am making many example sentences.",
                "source": "manual",
                "review_status": "accepted",
                "engine_version": "collect_mode_manual_v0.1",
                "linked_event_id": None,
            },
        )()
    ]

    def fake_correct_with_personal_memory(text: str):
        from correctr.personal_memory import correct_with_personal_memory as real_memory

        return real_memory(text, examples=trusted_examples)

    monkeypatch.setattr(
        "correctr.correction_orchestrator.correct_with_personal_memory",
        fake_correct_with_personal_memory,
    )

    result = correct_with_orchestration(
        "Laso I ma making many examlpe sentnces.",
        pipeline_mode="memory_then_dictionary_then_ai_if_needed",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "Also I am making many example sentences."
    assert result.engine_version == f"{PERSONAL_MEMORY_ENGINE_VERSION}:exact"
    assert get_event_source_for_result(result) == "future_memory"


def test_orchestrator_memory_first_falls_back_to_dictionary_when_no_match(monkeypatch) -> None:
    def fake_correct_with_personal_memory(text: str):
        return CorrectionResult(
            original_text=text,
            corrected_text=text,
            changed=False,
            corrections=[],
            engine_version=f"{PERSONAL_MEMORY_ENGINE_VERSION}:no_match",
        )

    monkeypatch.setattr(
        "correctr.correction_orchestrator.correct_with_personal_memory",
        fake_correct_with_personal_memory,
    )

    result = correct_with_orchestration(
        "testig misakes",
        pipeline_mode="memory_then_dictionary_then_ai_if_needed",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "testing mistakes"
    assert result.engine_version == "orchestrator_v0.2:dictionary"


def test_existing_dictionary_only_mode_still_works() -> None:
    result = correct_with_orchestration(
        "testig misakes",
        pipeline_mode="dictionary_only",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "testing mistakes"
    assert result.engine_version == "orchestrator_v0.2:dictionary"


def test_existing_dictionary_then_ai_if_needed_mode_still_works() -> None:
    result = correct_with_orchestration(
        "shiuld this not also be abl eto fix this?",
        pipeline_mode="dictionary_then_ai_if_needed",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "Should this not also be able to fix this?"
    assert result.engine_version == "orchestrator_v0.2:ai_context"
