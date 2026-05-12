import pytest

from correctr.correction_engine import CorrectionResult
from correctr.llm_engine import (
    AI_CONTEXT_ENGINE_VERSION,
    correct_with_ai_context,
    get_ai_context_provider,
)


def test_mock_ai_provider_returns_correction_result():
    result = correct_with_ai_context(
        "shiuld this not also be abl eto fix this?",
        provider_mode="mock",
    )

    assert isinstance(result, CorrectionResult)


def test_mock_ai_provider_fixes_known_hard_sentence():
    result = correct_with_ai_context(
        "shiuld this not also be abl eto fix this?",
        provider_mode="mock",
    )

    assert result.corrected_text == "Should this not also be able to fix this?"
    assert result.changed is True


def test_mock_ai_provider_fixes_spacing_and_context_sentence():
    result = correct_with_ai_context(
        "These are testing mis takes for the app to hopefully fix. i ma making two sentences.",
        provider_mode="mock",
    )

    assert result.corrected_text == "These are testing mistakes for the app to hopefully fix. I am making two sentences."
    assert result.changed is True


def test_mock_ai_no_change_behavior():
    original = "This sentence should not change."

    result = correct_with_ai_context(original, provider_mode="mock")

    assert result.original_text == original
    assert result.corrected_text == original
    assert result.changed is False
    assert result.corrections == []


def test_mock_ai_correction_records_are_structured():
    original = "shiuld this not also be abl eto fix this?"

    result = correct_with_ai_context(original, provider_mode="mock")

    assert result.corrections == [
        {
            "original": original,
            "corrected": "Should this not also be able to fix this?",
            "start_index": 0,
            "end_index": len(original),
            "reason": "mock_ai_context",
            "provider": "mock",
        }
    ]


def test_mock_ai_engine_version_includes_provider():
    result = correct_with_ai_context(
        "shiuld this not also be abl eto fix this?",
        provider_mode="mock",
    )

    assert result.engine_version == f"{AI_CONTEXT_ENGINE_VERSION}:mock"


def test_disabled_provider_returns_no_change_result():
    original = "shiuld this not also be abl eto fix this?"

    result = correct_with_ai_context(original, provider_mode="disabled")

    assert result.original_text == original
    assert result.corrected_text == original
    assert result.changed is False
    assert result.corrections == []
    assert result.engine_version == f"{AI_CONTEXT_ENGINE_VERSION}:disabled"


def test_unsupported_provider_raises_clear_error():
    with pytest.raises(ValueError, match="Unsupported AI provider"):
        get_ai_context_provider("bad_provider")


def test_reserved_real_provider_is_not_implemented_yet():
    with pytest.raises(NotImplementedError, match="reserved for future work"):
        correct_with_ai_context("text", provider_mode="ollama")


def test_no_external_service_or_api_key_required(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)

    result = correct_with_ai_context(
        "shiuld this not also be abl eto fix this?",
        provider_mode="mock",
    )

    assert result.corrected_text == "Should this not also be able to fix this?"
