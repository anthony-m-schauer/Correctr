import pytest

from correctr.correction_engine import CorrectionResult
from correctr.correction_orchestrator import (
    correct_with_orchestration,
    get_event_source_for_result,
)


def test_dictionary_only_returns_dictionary_result():
    result = correct_with_orchestration(
        "These are testig misakes.",
        pipeline_mode="dictionary_only",
        ai_provider_mode="mock",
    )

    assert isinstance(result, CorrectionResult)
    assert result.corrected_text == "These are testing mistakes."
    assert result.changed is True
    assert result.engine_version == "orchestrator_v0.1:dictionary"


def test_dictionary_only_tags_dictionary_records():
    result = correct_with_orchestration(
        "testig",
        pipeline_mode="dictionary_only",
        ai_provider_mode="mock",
    )

    assert result.corrections[0]["pipeline_stage"] == "dictionary"


def test_dictionary_then_ai_if_unchanged_uses_ai_when_dictionary_makes_no_change():
    result = correct_with_orchestration(
        "shiuld this not also be abl eto fix this?",
        pipeline_mode="dictionary_then_ai_if_unchanged",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "Should this not also be able to fix this?"
    assert result.changed is True
    assert result.engine_version == "orchestrator_v0.1:ai_context"
    assert result.corrections[0]["pipeline_stage"] == "ai_context"


def test_dictionary_then_ai_if_unchanged_does_not_use_ai_when_dictionary_changed_text():
    result = correct_with_orchestration(
        "These are testig misakes.",
        pipeline_mode="dictionary_then_ai_if_unchanged",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "These are testing mistakes."
    assert result.changed is True
    assert result.engine_version == "orchestrator_v0.1:dictionary"
    assert all(record["pipeline_stage"] == "dictionary" for record in result.corrections)


def test_dictionary_then_ai_always_runs_both_layers_for_combined_example():
    result = correct_with_orchestration(
        "These are testig mis takes for the app to hopfully fix. i ma maknig two sentencs.",
        pipeline_mode="dictionary_then_ai_always",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "These are testing mistakes for the app to hopefully fix. I am making two sentences."
    assert result.changed is True
    assert result.engine_version == "orchestrator_v0.1:dictionary_then_ai"

    pipeline_stages = [record["pipeline_stage"] for record in result.corrections]
    assert "dictionary" in pipeline_stages
    assert "ai_context" in pipeline_stages


def test_dictionary_then_ai_always_preserves_original_input_text():
    original = "These are testig mis takes for the app to hopfully fix. i ma maknig two sentencs."

    result = correct_with_orchestration(
        original,
        pipeline_mode="dictionary_then_ai_always",
        ai_provider_mode="mock",
    )

    assert result.original_text == original


def test_no_change_result_remains_no_change():
    original = "This sentence should not change."

    result = correct_with_orchestration(
        original,
        pipeline_mode="dictionary_then_ai_if_unchanged",
        ai_provider_mode="mock",
    )

    assert result.original_text == original
    assert result.corrected_text == original
    assert result.changed is False


def test_event_source_for_dictionary_result_is_dictionary():
    result = correct_with_orchestration(
        "testig",
        pipeline_mode="dictionary_only",
        ai_provider_mode="mock",
    )

    assert get_event_source_for_result(result) == "dictionary"


def test_event_source_for_ai_result_is_ai_context():
    result = correct_with_orchestration(
        "shiuld this not also be abl eto fix this?",
        pipeline_mode="dictionary_then_ai_if_unchanged",
        ai_provider_mode="mock",
    )

    assert get_event_source_for_result(result) == "ai_context"


def test_event_source_for_dictionary_then_ai_result_is_ai_context_when_ai_record_exists():
    result = correct_with_orchestration(
        "These are testig mis takes for the app to hopfully fix. i ma maknig two sentencs.",
        pipeline_mode="dictionary_then_ai_always",
        ai_provider_mode="mock",
    )

    assert get_event_source_for_result(result) == "ai_context"


def test_invalid_pipeline_mode_raises_clear_error():
    with pytest.raises(ValueError, match="Unsupported correction pipeline mode"):
        correct_with_orchestration(
            "testig",
            pipeline_mode="bad_mode",
            ai_provider_mode="mock",
        )


def test_no_external_model_or_api_key_is_required(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)

    result = correct_with_orchestration(
        "shiuld this not also be abl eto fix this?",
        pipeline_mode="dictionary_then_ai_if_unchanged",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "Should this not also be able to fix this?"
