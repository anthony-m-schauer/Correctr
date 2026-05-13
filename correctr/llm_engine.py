"""
Correctr AI / LLM Context Correction Layer

Purpose:
    Provides a provider-neutral AI/context correction layer.

Current scope:
    AI Context Correction_v0.3 Prompt Tuning + Output Guardrails.

This module supports:
    - disabled: safe no-op provider
    - mock: deterministic local stand-in for tests and smoke checks
    - ollama: local model provider through Ollama's /api/generate endpoint

It does not implement OpenAI calls, neural ranking, suggestion UI, or app/hotkey
routing policy. The orchestrator decides when to use this layer.
"""

from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from correctr.config import (
    AI_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
    validate_ai_provider,
)
from correctr.correction_engine import CorrectionResult


AI_CONTEXT_ENGINE_VERSION = "ai_context_v0.3"

MOCK_AI_REASON = "mock_ai_context"
OLLAMA_AI_REASON = "ollama_ai_context"
OLLAMA_FALLBACK_REASON = "ollama_fallback"
AI_OUTPUT_REJECTED_REASON = "ai_output_rejected"


_RESPONSE_PREFIX_PATTERNS = [
    re.compile(r"^\s*here\s+is\s+the\s+corrected\s+text\s*:\s*", re.IGNORECASE),
    re.compile(r"^\s*corrected\s+text\s*:\s*", re.IGNORECASE),
    re.compile(r"^\s*correction\s*:\s*", re.IGNORECASE),
    re.compile(r"^\s*the\s+corrected\s+sentence\s+is\s*:\s*", re.IGNORECASE),
    re.compile(r"^\s*the\s+corrected\s+text\s+is\s*:\s*", re.IGNORECASE),
]

_EXPLANATION_PATTERNS = [
    re.compile(r"\bi\s+corrected\b", re.IGNORECASE),
    re.compile(r"\bi\s+fixed\b", re.IGNORECASE),
    re.compile(r"\bthe\s+mistake\s+was\b", re.IGNORECASE),
    re.compile(r"\bexplanation\b", re.IGNORECASE),
    re.compile(r"\breason\b", re.IGNORECASE),
    re.compile(r"\bhere'?s\s+why\b", re.IGNORECASE),
]

_ASSISTANT_PREFACE_PATTERNS = [
    re.compile(r"^\s*as\s+an\s+ai\b", re.IGNORECASE),
    re.compile(r"^\s*i\s+can\b", re.IGNORECASE),
    re.compile(r"^\s*sure[,!]\s*", re.IGNORECASE),
    re.compile(r"^\s*of\s+course[,!]\s*", re.IGNORECASE),
]


@dataclass(frozen=True)
class OutputValidationResult:
    """
    Result of checking whether model output is safe to use as corrected text.
    """

    is_acceptable: bool
    reason: str = ""


class AIContextProvider(Protocol):
    """
    Provider interface for AI/context correction.

    Providers should return CorrectionResult and preserve the user's meaning
    and tone while correcting typos and obvious spacing mistakes.
    """

    provider_name: str

    def correct(self, text: str) -> CorrectionResult:
        """
        Corrects text using provider-specific logic.
        """


class MockAIContextProvider:
    """
    Deterministic test-safe provider.

    This is not real AI. It exists to prove the interface and integration path
    without requiring external services, API keys, or local model setup.
    """

    provider_name = "mock"

    _KNOWN_CORRECTIONS = {
        "shiuld this not also be abl eto fix this?": "Should this not also be able to fix this?",
        "These are testing mis takes for the app to hopefully fix. i ma making two sentences.": (
            "These are testing mistakes for the app to hopefully fix. I am making two sentences."
        ),
    }

    def correct(self, text: str) -> CorrectionResult:
        corrected_text = self._KNOWN_CORRECTIONS.get(text, text)

        if corrected_text == text:
            return CorrectionResult(
                original_text=text,
                corrected_text=text,
                changed=False,
                corrections=[],
                engine_version=self._engine_version,
            )

        return CorrectionResult(
            original_text=text,
            corrected_text=corrected_text,
            changed=True,
            corrections=[
                {
                    "original": text,
                    "corrected": corrected_text,
                    "start_index": 0,
                    "end_index": len(text),
                    "reason": MOCK_AI_REASON,
                    "provider": self.provider_name,
                }
            ],
            engine_version=self._engine_version,
        )

    @property
    def _engine_version(self) -> str:
        return f"{AI_CONTEXT_ENGINE_VERSION}:{self.provider_name}"


class DisabledAIContextProvider:
    """
    Safe no-op provider.

    Useful when AI/context correction is explicitly disabled while still
    returning a structured CorrectionResult.
    """

    provider_name = "disabled"

    def correct(self, text: str) -> CorrectionResult:
        return CorrectionResult(
            original_text=text,
            corrected_text=text,
            changed=False,
            corrections=[],
            engine_version=f"{AI_CONTEXT_ENGINE_VERSION}:{self.provider_name}",
        )


class OllamaAIContextProvider:
    """
    Local Ollama provider.

    This provider calls a local Ollama server through:
        POST {base_url}/api/generate

    It uses stream=false so the response can be parsed as one JSON object.
    If Ollama is unavailable, returns invalid output, or produces rejected
    output, this provider returns a safe no-change CorrectionResult.
    """

    provider_name = "ollama"

    def __init__(
        self,
        *,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_MODEL,
        timeout_seconds: float = OLLAMA_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def correct(self, text: str) -> CorrectionResult:
        prompt = build_ollama_correction_prompt(text)
        payload = build_ollama_generate_payload(
            model=self.model,
            prompt=prompt,
        )

        try:
            response_json = _post_ollama_generate(
                base_url=self.base_url,
                payload=payload,
                timeout_seconds=self.timeout_seconds,
            )
        except Exception as error:
            return self._fallback_result(
                text=text,
                error_message=f"{type(error).__name__}: {error}",
                reason=OLLAMA_FALLBACK_REASON,
                version_suffix="fallback",
            )

        raw_response_text = _extract_ollama_response_text(response_json)

        if raw_response_text is None:
            return self._fallback_result(
                text=text,
                error_message="Invalid Ollama response: missing or empty response text.",
                reason=OLLAMA_FALLBACK_REASON,
                version_suffix="fallback",
            )

        corrected_text = clean_model_output(raw_response_text)
        corrected_text = apply_basic_sentence_start_capitalization(text, corrected_text)

        validation = validate_model_output(
            original_text=text,
            candidate_text=corrected_text,
            raw_model_output=raw_response_text,
        )

        if not validation.is_acceptable:
            return self._fallback_result(
                text=text,
                error_message=validation.reason,
                reason=AI_OUTPUT_REJECTED_REASON,
                version_suffix="rejected",
            )

        changed = corrected_text != text

        return CorrectionResult(
            original_text=text,
            corrected_text=corrected_text,
            changed=changed,
            corrections=(
                [
                    {
                        "original": text,
                        "corrected": corrected_text,
                        "start_index": 0,
                        "end_index": len(text),
                        "reason": OLLAMA_AI_REASON,
                        "provider": self.provider_name,
                        "model": self.model,
                    }
                ]
                if changed
                else []
            ),
            engine_version=self._engine_version,
        )

    @property
    def _engine_version(self) -> str:
        return f"{AI_CONTEXT_ENGINE_VERSION}:{self.provider_name}:{self.model}"

    def _fallback_result(
        self,
        *,
        text: str,
        error_message: str,
        reason: str,
        version_suffix: str,
    ) -> CorrectionResult:
        """
        Returns a no-change result when Ollama cannot produce a safe correction.
        """
        return CorrectionResult(
            original_text=text,
            corrected_text=text,
            changed=False,
            corrections=[
                {
                    "original": text,
                    "corrected": text,
                    "start_index": 0,
                    "end_index": len(text),
                    "reason": reason,
                    "provider": self.provider_name,
                    "model": self.model,
                    "error": error_message,
                }
            ],
            engine_version=f"{self._engine_version}:{version_suffix}",
        )


def get_ai_context_provider(
    provider_mode: str = AI_PROVIDER,
    *,
    ollama_base_url: str = OLLAMA_BASE_URL,
    ollama_model: str = OLLAMA_MODEL,
    ollama_timeout_seconds: float = OLLAMA_TIMEOUT_SECONDS,
) -> AIContextProvider:
    """
    Returns the configured AI/context correction provider.

    Implemented in v0.3:
        - mock
        - disabled
        - ollama

    Reserved for future work:
        - openai
    """
    provider_mode = validate_ai_provider(provider_mode)

    if provider_mode == "mock":
        return MockAIContextProvider()

    if provider_mode == "disabled":
        return DisabledAIContextProvider()

    if provider_mode == "ollama":
        return OllamaAIContextProvider(
            base_url=ollama_base_url,
            model=ollama_model,
            timeout_seconds=ollama_timeout_seconds,
        )

    raise NotImplementedError(
        f"AI provider {provider_mode!r} is reserved for future work and is not implemented in v0.3."
    )


def correct_with_ai_context(
    text: str,
    provider_mode: str = AI_PROVIDER,
    *,
    ollama_base_url: str = OLLAMA_BASE_URL,
    ollama_model: str = OLLAMA_MODEL,
    ollama_timeout_seconds: float = OLLAMA_TIMEOUT_SECONDS,
) -> CorrectionResult:
    """
    Corrects text using the configured AI/context provider.

    Returns:
        CorrectionResult with original_text, corrected_text, changed,
        corrections, and engine_version.
    """
    provider = get_ai_context_provider(
        provider_mode,
        ollama_base_url=ollama_base_url,
        ollama_model=ollama_model,
        ollama_timeout_seconds=ollama_timeout_seconds,
    )
    return provider.correct(text)


def build_ollama_correction_prompt(text: str) -> str:
    """
    Builds the conservative correction prompt sent to Ollama.

    The examples are intentionally compact. They teach the model to correct
    typos and spacing while preserving awkward user wording when it is not
    clearly a typo.
    """
    return (
        "You are Correctr, a conservative typo-correction engine.\n"
        "Your job is to correct only spelling mistakes, obvious typing mistakes, misplaced spaces, "
        "and basic sentence-start capitalization.\n"
        "Preserve the user's meaning, wording, and tone.\n"
        "Do not rewrite the sentence into a smoother or more polished style.\n"
        "Do not add new ideas.\n"
        "Return only the corrected text.\n"
        "Do not include explanations.\n"
        "Do not include prefixes such as 'Here is the corrected text:', 'Corrected text:', "
        "'Correction:', or 'The corrected sentence is:'.\n"
        "Do not use markdown.\n"
        "Do not wrap the answer in quotes unless the original text used quotes.\n"
        "Keep punctuation and capitalization appropriate for the original sentence.\n"
        "Capitalize the first word of a normal sentence when appropriate.\n"
        "\n"
        "Examples:\n"
        "Input: shiuld this not also be abl eto fix this?\n"
        "Output: Should this not also be able to fix this?\n"
        "\n"
        "Input: These are testing mis takes for the app to hopefully fix. i ma making two sentences.\n"
        "Output: These are testing mistakes for the app to hopefully fix. I am making two sentences.\n"
        "\n"
        "Input: Thsi here be th ethird pracitve testing sentenc we habe.\n"
        "Output: This here be the third practice testing sentence we have.\n"
        "\n"
        "Now correct this text. Return only the corrected text.\n"
        f"Input: {text}\n"
        "Output:"
    )


def build_ollama_generate_payload(*, model: str, prompt: str) -> dict[str, Any]:
    """
    Builds the Ollama /api/generate request payload.
    """
    return {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
        },
    }


def clean_model_output(text: str) -> str:
    """
    Conservatively removes common response wrappers from model output.

    This does not try to determine semantic quality. It only removes formatting
    artifacts that the prompt explicitly forbids.
    """
    cleaned = text.strip()

    cleaned = _remove_surrounding_code_fence(cleaned)

    for prefix_pattern in _RESPONSE_PREFIX_PATTERNS:
        cleaned = prefix_pattern.sub("", cleaned).strip()

    cleaned = _strip_single_pair_of_surrounding_quotes(cleaned)

    return cleaned.strip()


def validate_model_output(
    *,
    original_text: str,
    candidate_text: str,
    raw_model_output: str | None = None,
) -> OutputValidationResult:
    """
    Checks whether model output is safe enough to use as corrected text.

    This guardrail catches obvious formatting and assistant-response failures.
    It does not claim to detect every semantically bad correction.

    Validation order matters:
        - structural formatting issues are reported first
        - length issues are reported before explanation wording
        - explanation checks come after more specific formatting checks
    """
    candidate = candidate_text.strip()
    raw = raw_model_output if raw_model_output is not None else candidate_text

    if candidate == "":
        return OutputValidationResult(False, "Rejected AI output because it was empty.")

    if "```" in raw or "```" in candidate:
        return OutputValidationResult(False, "Rejected AI output because it contained markdown/code fences.")

    for prefix_pattern in _RESPONSE_PREFIX_PATTERNS:
        if prefix_pattern.search(candidate):
            return OutputValidationResult(False, "Rejected AI output because it still contained a correction prefix.")

    for preface_pattern in _ASSISTANT_PREFACE_PATTERNS:
        if preface_pattern.search(candidate):
            return OutputValidationResult(False, "Rejected AI output because it contained assistant-style preface text.")

    if _is_multiple_paragraphs(candidate) and not _is_multiple_paragraphs(original_text):
        return OutputValidationResult(False, "Rejected AI output because it introduced multiple paragraphs.")

    if _is_too_much_longer(original_text, candidate):
        return OutputValidationResult(False, "Rejected AI output because it was much longer than the original.")

    for explanation_pattern in _EXPLANATION_PATTERNS:
        if explanation_pattern.search(candidate):
            return OutputValidationResult(False, "Rejected AI output because it appeared to explain the correction.")

    if _looks_like_answer_instead_of_correction(candidate):
        return OutputValidationResult(False, "Rejected AI output because it appeared to answer instead of correct.")

    return OutputValidationResult(True, "")


def apply_basic_sentence_start_capitalization(original_text: str, corrected_text: str) -> str:
    """
    Capitalizes the first letter of a normal sentence when the model returns
    an otherwise acceptable lowercase sentence.

    This is intentionally conservative:
        - only changes the first alphabetic character
        - only when the text appears sentence-like
        - does not change all-caps, quoted, or already-capitalized text
    """
    stripped = corrected_text.strip()

    if stripped == "":
        return corrected_text

    if not _looks_sentence_like(original_text):
        return corrected_text

    first_alpha_index = None
    for index, character in enumerate(stripped):
        if character.isalpha():
            first_alpha_index = index
            break

    if first_alpha_index is None:
        return corrected_text

    first_alpha = stripped[first_alpha_index]

    if not first_alpha.islower():
        return corrected_text

    return (
        stripped[:first_alpha_index]
        + first_alpha.upper()
        + stripped[first_alpha_index + 1 :]
    )


def _post_ollama_generate(
    *,
    base_url: str,
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    """
    Sends one non-streaming generation request to Ollama.
    """
    endpoint = f"{base_url.rstrip('/')}/api/generate"
    request_data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        endpoint,
        data=request_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, socket.timeout) as error:
        raise RuntimeError(f"Ollama request failed: {error}") from error

    try:
        parsed = json.loads(response_body)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Ollama returned invalid JSON: {error}") from error

    if not isinstance(parsed, dict):
        raise RuntimeError("Ollama response JSON was not an object.")

    return parsed


def _extract_ollama_response_text(response_json: dict[str, Any]) -> str | None:
    """
    Extracts plain corrected text from Ollama's non-streaming response JSON.
    """
    response_text = response_json.get("response")

    if not isinstance(response_text, str):
        return None

    if response_text.strip() == "":
        return None

    return response_text


def _remove_surrounding_code_fence(text: str) -> str:
    """
    Removes one simple surrounding markdown code fence.

    Validation still rejects raw/code-fenced output before accepting it, so this
    cleanup mainly protects smoke-test display and future provider experiments.
    """
    lines = text.strip().splitlines()

    if len(lines) >= 3 and lines[0].strip().startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()

    return text


def _strip_single_pair_of_surrounding_quotes(text: str) -> str:
    """
    Removes one matching pair of surrounding quotes.
    """
    cleaned = text.strip()

    if len(cleaned) >= 2:
        if (cleaned[0] == cleaned[-1]) and cleaned[0] in {'"', "'"}:
            return cleaned[1:-1].strip()

    return cleaned


def _is_multiple_paragraphs(text: str) -> bool:
    """
    Returns True if text appears to contain multiple paragraphs.
    """
    return "\n\n" in text.strip()


def _is_too_much_longer(original_text: str, candidate_text: str) -> bool:
    """
    Rejects outputs that are much longer than the original.

    This catches explanations and broad rewrites without requiring semantic
    understanding.
    """
    original_length = max(len(original_text.strip()), 1)
    candidate_length = len(candidate_text.strip())

    if original_length < 30:
        return candidate_length > original_length + 80

    return candidate_length > original_length * 2.25


def _looks_like_answer_instead_of_correction(candidate_text: str) -> bool:
    """
    Catches a few obvious cases where the model answers rather than corrects.
    """
    candidate = candidate_text.strip().lower()

    answer_starters = (
        "yes,",
        "no,",
        "the answer is",
        "it depends",
        "as a language model",
    )

    return candidate.startswith(answer_starters)


def _looks_sentence_like(text: str) -> bool:
    """
    Returns True when text looks like a normal sentence or sentence fragment
    that should start with capitalization after correction.
    """
    stripped = text.strip()

    if stripped == "":
        return False

    if stripped[0] in {'"', "'", "`"}:
        return False

    return any(stripped.endswith(punctuation) for punctuation in (".", "?", "!"))
