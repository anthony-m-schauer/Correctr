import json
import urllib.error

from correctr.llm_engine import (
    OLLAMA_MODEL,
    correct_with_ai_context,
)


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_successful_fake_ollama_response_produces_correction_result(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse({"response": "Should this not also be able to fix this?", "done": True})

    monkeypatch.setattr("correctr.llm_engine.urllib.request.urlopen", fake_urlopen)

    result = correct_with_ai_context(
        "shiuld this not also be abl eto fix this?",
        provider_mode="ollama",
        ollama_model="llama3.2:3b",
    )

    assert result.original_text == "shiuld this not also be abl eto fix this?"
    assert result.corrected_text == "Should this not also be able to fix this?"
    assert result.changed is True
    assert result.engine_version == "ai_context_v0.3:ollama:llama3.2:3b"
    assert result.corrections[0]["reason"] == "ollama_ai_context"
    assert result.corrections[0]["provider"] == "ollama"
    assert result.corrections[0]["model"] == "llama3.2:3b"


def test_fake_ollama_same_text_response_is_no_change(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse({"response": "This sentence should not change.", "done": True})

    monkeypatch.setattr("correctr.llm_engine.urllib.request.urlopen", fake_urlopen)

    result = correct_with_ai_context(
        "This sentence should not change.",
        provider_mode="ollama",
    )

    assert result.changed is False
    assert result.corrections == []


def test_ollama_connection_failure_returns_safe_fallback(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("correctr.llm_engine.urllib.request.urlopen", fake_urlopen)

    result = correct_with_ai_context(
        "shiuld this not also be abl eto fix this?",
        provider_mode="ollama",
    )

    assert result.original_text == "shiuld this not also be abl eto fix this?"
    assert result.corrected_text == "shiuld this not also be abl eto fix this?"
    assert result.changed is False
    assert result.engine_version.endswith(":fallback")
    assert result.corrections[0]["reason"] == "ollama_fallback"


def test_ollama_invalid_json_returns_safe_fallback(monkeypatch):
    class InvalidJSONResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b"not-json"

    def fake_urlopen(request, timeout):
        return InvalidJSONResponse()

    monkeypatch.setattr("correctr.llm_engine.urllib.request.urlopen", fake_urlopen)

    result = correct_with_ai_context(
        "shiuld this not also be abl eto fix this?",
        provider_mode="ollama",
    )

    assert result.changed is False
    assert result.engine_version.endswith(":fallback")
    assert result.corrections[0]["reason"] == "ollama_fallback"
    assert "invalid JSON" in result.corrections[0]["error"]


def test_ollama_missing_response_returns_safe_fallback(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse({"done": True})

    monkeypatch.setattr("correctr.llm_engine.urllib.request.urlopen", fake_urlopen)

    result = correct_with_ai_context(
        "shiuld this not also be abl eto fix this?",
        provider_mode="ollama",
    )

    assert result.changed is False
    assert result.engine_version.endswith(":fallback")
    assert result.corrections[0]["reason"] == "ollama_fallback"


def test_ollama_output_strips_surrounding_quotes(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse({"response": '"Should this not also be able to fix this?"', "done": True})

    monkeypatch.setattr("correctr.llm_engine.urllib.request.urlopen", fake_urlopen)

    result = correct_with_ai_context(
        "shiuld this not also be abl eto fix this?",
        provider_mode="ollama",
    )

    assert result.corrected_text == "Should this not also be able to fix this?"


def test_ollama_lowercase_sentence_start_is_capitalized(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse({"response": "should this not also be able to fix this?", "done": True})

    monkeypatch.setattr("correctr.llm_engine.urllib.request.urlopen", fake_urlopen)

    result = correct_with_ai_context(
        "shiuld this not also be abl eto fix this?",
        provider_mode="ollama",
    )

    assert result.corrected_text == "Should this not also be able to fix this?"


def test_ollama_prefix_response_is_cleaned_and_accepted_if_remaining_text_is_plain(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse(
            {"response": "Here is the corrected text:\n\nThis here be the third practice testing sentence we have.", "done": True}
        )

    monkeypatch.setattr("correctr.llm_engine.urllib.request.urlopen", fake_urlopen)

    result = correct_with_ai_context(
        "Thsi here be th ethird pracitve testing sentenc we habe.",
        provider_mode="ollama",
    )

    assert result.corrected_text == "This here be the third practice testing sentence we have."
    assert result.changed is True


def test_ollama_explanation_style_response_is_rejected(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse(
            {"response": "I corrected the spelling mistakes in the sentence.", "done": True}
        )

    monkeypatch.setattr("correctr.llm_engine.urllib.request.urlopen", fake_urlopen)

    result = correct_with_ai_context(
        "Thsi here be th ethird pracitve testing sentenc we habe.",
        provider_mode="ollama",
    )

    assert result.changed is False
    assert result.engine_version.endswith(":rejected")
    assert result.corrections[0]["reason"] == "ai_output_rejected"


def test_ollama_markdown_response_is_rejected(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeHTTPResponse(
            {"response": "```text\nThis here be the third practice testing sentence we have.\n```", "done": True}
        )

    monkeypatch.setattr("correctr.llm_engine.urllib.request.urlopen", fake_urlopen)

    result = correct_with_ai_context(
        "Thsi here be th ethird pracitve testing sentenc we habe.",
        provider_mode="ollama",
    )

    assert result.changed is False
    assert result.engine_version.endswith(":rejected")
    assert result.corrections[0]["reason"] == "ai_output_rejected"


def test_ollama_request_uses_configurable_base_url_model_and_timeout(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["full_url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeHTTPResponse({"response": "Corrected text.", "done": True})

    monkeypatch.setattr("correctr.llm_engine.urllib.request.urlopen", fake_urlopen)

    correct_with_ai_context(
        "bad text.",
        provider_mode="ollama",
        ollama_base_url="http://localhost:11434",
        ollama_model="custom-model",
        ollama_timeout_seconds=3,
    )

    assert captured["full_url"] == "http://localhost:11434/api/generate"
    assert captured["timeout"] == 3
    assert captured["body"]["model"] == "custom-model"
    assert captured["body"]["stream"] is False
    assert captured["body"]["options"]["temperature"] == 0


def test_default_ollama_model_is_current_best_candidate():
    assert OLLAMA_MODEL == "llama3.2:3b"
