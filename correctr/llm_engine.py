"""
Correctr AI / LLM Context Correction Layer

Purpose:
    Provides the first controlled provider-neutral AI/context correction layer.

Current scope:
    AI Context Correction_v0.1 Controlled LLM/SLM Correction Layer.

This module does not call an external model yet. It establishes a safe interface
and a deterministic mock provider so tests and downstream integration can be
built without API keys, local model setup, or network calls.

Future provider directions:
    - mock: deterministic local stand-in for tests and smoke checks
    - ollama: future local SLM/LLM provider
    - openai: future API-based provider
    - disabled: safe no-op provider
"""

from __future__ import annotations

from typing import Protocol

from correctr.config import AI_PROVIDER, validate_ai_provider
from correctr.correction_engine import CorrectionResult


AI_CONTEXT_ENGINE_VERSION = "ai_context_v0.1"

MOCK_AI_REASON = "mock_ai_context"


class AIContextProvider(Protocol):
    """
    Provider interface for AI/context correction.

    Future providers should return CorrectionResult and preserve the same
    public behavior as the mock provider.
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

    Useful when a future config path wants AI explicitly disabled while still
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


def get_ai_context_provider(provider_mode: str = AI_PROVIDER) -> AIContextProvider:
    """
    Returns the configured AI/context correction provider.

    Only mock and disabled are implemented in v0.1.
    ollama and openai are reserved values for future packages.
    """
    provider_mode = validate_ai_provider(provider_mode)

    if provider_mode == "mock":
        return MockAIContextProvider()

    if provider_mode == "disabled":
        return DisabledAIContextProvider()

    raise NotImplementedError(
        f"AI provider {provider_mode!r} is reserved for future work and is not implemented in v0.1."
    )


def correct_with_ai_context(text: str, provider_mode: str = AI_PROVIDER) -> CorrectionResult:
    """
    Corrects text using the configured AI/context provider.

    Returns:
        CorrectionResult with original_text, corrected_text, changed,
        corrections, and engine_version.
    """
    provider = get_ai_context_provider(provider_mode)
    return provider.correct(text)
