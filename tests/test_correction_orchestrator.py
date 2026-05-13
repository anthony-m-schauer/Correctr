from correctr.correction_engine import CorrectionResult
from correctr.correction_orchestrator import (
    correct_with_orchestration,
    detect_suspicious_text_signals,
    get_event_source_for_result,
    should_route_to_ai,
)


def test_clean_text_does_not_route_to_ai():
    result = correct_with_orchestration(
        "This is already correct.",
        pipeline_mode="dictionary_then_ai_if_needed",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "This is already correct."
    assert result.changed is False
    assert result.engine_version == "orchestrator_v0.2:no_change" or result.engine_version == "orchestrator_v0.2:dictionary"


def test_this_is_already_correct_remains_unchanged_in_ai_if_needed():
    result = correct_with_orchestration(
        "This is already correct.",
        pipeline_mode="dictionary_then_ai_if_needed",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "This is already correct."
    assert result.changed is False


def test_dictionary_only_fix_does_not_route_to_ai_unnecessarily():
    result = correct_with_orchestration(
        "These are testig misakes for the app to hopfully fix. I am maknig two sentencs.",
        pipeline_mode="dictionary_then_ai_if_needed",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "These are testing mistakes for the app to hopefully fix. I am making two sentences."
    assert result.changed is True
    assert result.engine_version == "orchestrator_v0.2:dictionary"
    assert get_event_source_for_result(result) == "dictionary"


def test_dictionary_changed_but_residual_suspicious_pattern_routes_to_ai():
    result = correct_with_orchestration(
        "These are testig mis takes for the app to hopfully fix. i ma maknig two sentencs.",
        pipeline_mode="dictionary_then_ai_if_needed",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "These are testing mistakes for the app to hopefully fix. I am making two sentences."
    assert result.changed is True
    assert result.engine_version == "orchestrator_v0.2:dictionary_then_ai"
    assert get_event_source_for_result(result) == "ai_context"


def test_dictionary_unchanged_but_suspicious_typo_routes_to_ai():
    result = correct_with_orchestration(
        "shiuld this not also be abl eto fix this?",
        pipeline_mode="dictionary_then_ai_if_needed",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "Should this not also be able to fix this?"
    assert result.changed is True
    assert result.engine_version == "orchestrator_v0.2:ai_context"
    assert get_event_source_for_result(result) == "ai_context"


def test_snother_example_routes_to_ai_with_mock_provider():
    result = correct_with_orchestration(
        "Snother testin gexample.",
        pipeline_mode="dictionary_then_ai_if_needed",
        ai_provider_mode="mock",
    )

    # Mock provider does not know this exact example yet, so it should route
    # to AI but remain unchanged. Real llama3.2:3b is expected to fix it.
    assert result.corrected_text == "Snother testin gexample."
    assert result.changed is False


def test_should_route_to_ai_returns_clean_gate_reason_for_clean_text():
    dictionary_result = CorrectionResult(
        original_text="This is already correct.",
        corrected_text="This is already correct.",
        changed=False,
        corrections=[],
        engine_version="test",
    )

    decision = should_route_to_ai(
        original_text="This is already correct.",
        dictionary_result=dictionary_result,
    )

    assert decision.use_ai is False
    assert decision.reasons == ["clean_text_gate_skipped_ai"]


def test_should_route_to_ai_detects_split_word_pattern():
    dictionary_result = CorrectionResult(
        original_text="mis takes",
        corrected_text="mis takes",
        changed=False,
        corrections=[],
        engine_version="test",
    )

    decision = should_route_to_ai(
        original_text="mis takes",
        dictionary_result=dictionary_result,
    )

    assert decision.use_ai is True
    assert "dictionary_no_change_but_suspicious_pattern" in decision.reasons
    assert "likely_spacing_error" in decision.reasons


def test_detect_suspicious_text_signals_detects_hard_typo_tokens():
    reasons = detect_suspicious_text_signals("Thsi sentenc we habe.")

    assert "likely_typo_token" in reasons
    assert "token:thsi" in reasons
    assert "token:sentenc" in reasons
    assert "token:habe" in reasons


def test_ai_fallback_returns_dictionary_result_when_dictionary_changed(monkeypatch):
    def fake_ai_result(text, provider_mode):
        return CorrectionResult(
            original_text=text,
            corrected_text=text,
            changed=False,
            corrections=[
                {
                    "original": text,
                    "corrected": text,
                    "reason": "ollama_fallback",
                }
            ],
            engine_version="ai_context_v0.3:ollama:test:fallback",
        )

    monkeypatch.setattr("correctr.correction_orchestrator.correct_with_ai_context", fake_ai_result)

    result = correct_with_orchestration(
        "These are testig mis takes for the app to hopfully fix. i ma maknig two sentencs.",
        pipeline_mode="dictionary_then_ai_if_needed",
        ai_provider_mode="ollama",
    )

    assert result.corrected_text == "These are testing mis takes for the app to hopefully fix. i ma making two sentences."
    assert result.changed is True
    assert result.engine_version == "orchestrator_v0.2:dictionary"


def test_ai_fallback_returns_no_change_when_dictionary_did_not_change(monkeypatch):
    def fake_ai_result(text, provider_mode):
        return CorrectionResult(
            original_text=text,
            corrected_text=text,
            changed=False,
            corrections=[
                {
                    "original": text,
                    "corrected": text,
                    "reason": "ollama_fallback",
                }
            ],
            engine_version="ai_context_v0.3:ollama:test:fallback",
        )

    monkeypatch.setattr("correctr.correction_orchestrator.correct_with_ai_context", fake_ai_result)

    result = correct_with_orchestration(
        "shiuld this not also be abl eto fix this?",
        pipeline_mode="dictionary_then_ai_if_needed",
        ai_provider_mode="ollama",
    )

    assert result.corrected_text == "shiuld this not also be abl eto fix this?"
    assert result.changed is False
    assert result.engine_version == "orchestrator_v0.2:no_change"


def test_dictionary_only_behavior_still_works():
    result = correct_with_orchestration(
        "testig misakes",
        pipeline_mode="dictionary_only",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "testing mistakes"
    assert result.engine_version == "orchestrator_v0.2:dictionary"


def test_dictionary_then_ai_if_unchanged_still_works():
    result = correct_with_orchestration(
        "shiuld this not also be abl eto fix this?",
        pipeline_mode="dictionary_then_ai_if_unchanged",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "Should this not also be able to fix this?"
    assert result.engine_version == "orchestrator_v0.2:ai_context"


def test_dictionary_then_ai_always_still_works():
    result = correct_with_orchestration(
        "These are testig mis takes for the app to hopfully fix. i ma maknig two sentencs.",
        pipeline_mode="dictionary_then_ai_always",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "These are testing mistakes for the app to hopefully fix. I am making two sentences."
    assert result.engine_version == "orchestrator_v0.2:dictionary_then_ai"


def test_result_is_correction_result():
    result = correct_with_orchestration(
        "testig",
        pipeline_mode="dictionary_only",
        ai_provider_mode="mock",
    )

    assert isinstance(result, CorrectionResult)


def test_no_real_ollama_server_required_for_pytest():
    result = correct_with_orchestration(
        "shiuld this not also be abl eto fix this?",
        pipeline_mode="dictionary_then_ai_if_needed",
        ai_provider_mode="mock",
    )

    assert result.corrected_text == "Should this not also be able to fix this?"
