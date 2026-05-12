"""
Correctr Correction Orchestrator

Purpose:
    Coordinates local dictionary correction and AI/context correction through
    a controlled routing layer.

Current scope:
    Correction Orchestrator_v0.1 Controlled Routing Layer.

This module is the coordination layer above:
    - correctr.correction_engine
    - correctr.llm_engine

It does not implement real OpenAI/Ollama calls, neural ranking, suggestion UI,
personal memory lookup, advanced spellcheck, or confidence scoring.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Literal

from correctr.config import (
    AI_PROVIDER,
    CORRECTION_PIPELINE_MODE,
    validate_ai_provider,
    validate_correction_pipeline_mode,
)
from correctr.correction_engine import CorrectionResult, correct_text_detailed
from correctr.llm_engine import correct_with_ai_context


ORCHESTRATOR_VERSION = "orchestrator_v0.1"

PipelineMode = Literal[
    "dictionary_only",
    "dictionary_then_ai_if_unchanged",
    "dictionary_then_ai_always",
]


def correct_with_orchestration(
    text: str,
    *,
    pipeline_mode: str = CORRECTION_PIPELINE_MODE,
    ai_provider_mode: str = AI_PROVIDER,
) -> CorrectionResult:
    """
    Runs the controlled correction pipeline and returns one final CorrectionResult.

    Routing policy:
        dictionary_only:
            Run dictionary correction and return it.

        dictionary_then_ai_if_unchanged:
            Run dictionary correction first.
            If dictionary changed the text, return dictionary result.
            If dictionary did not change the text, run AI/context correction.

        dictionary_then_ai_always:
            Run dictionary correction first.
            Then send dictionary corrected_text into AI/context correction.
            Return one final result with combined correction records.
    """
    pipeline_mode = validate_correction_pipeline_mode(pipeline_mode)
    ai_provider_mode = validate_ai_provider(ai_provider_mode)

    dictionary_result = correct_text_detailed(text)

    if pipeline_mode == "dictionary_only":
        return _as_orchestrator_result(
            original_text=text,
            corrected_text=dictionary_result.corrected_text,
            changed=dictionary_result.changed,
            corrections=_tag_correction_records(dictionary_result.corrections, "dictionary"),
            route="dictionary",
        )

    if pipeline_mode == "dictionary_then_ai_if_unchanged":
        if dictionary_result.changed:
            return _as_orchestrator_result(
                original_text=text,
                corrected_text=dictionary_result.corrected_text,
                changed=True,
                corrections=_tag_correction_records(dictionary_result.corrections, "dictionary"),
                route="dictionary",
            )

        ai_result = correct_with_ai_context(text, provider_mode=ai_provider_mode)
        return _as_orchestrator_result(
            original_text=text,
            corrected_text=ai_result.corrected_text,
            changed=ai_result.corrected_text != text,
            corrections=_tag_correction_records(ai_result.corrections, "ai_context"),
            route="ai_context",
        )

    if pipeline_mode == "dictionary_then_ai_always":
        ai_result = correct_with_ai_context(
            dictionary_result.corrected_text,
            provider_mode=ai_provider_mode,
        )

        combined_corrections = [
            *_tag_correction_records(dictionary_result.corrections, "dictionary"),
            *_tag_correction_records(ai_result.corrections, "ai_context"),
        ]

        return _as_orchestrator_result(
            original_text=text,
            corrected_text=ai_result.corrected_text,
            changed=ai_result.corrected_text != text,
            corrections=combined_corrections,
            route="dictionary_then_ai",
        )

    # validate_correction_pipeline_mode should prevent this path.
    raise ValueError(f"Unhandled correction pipeline mode: {pipeline_mode!r}")


# Backward-compatible alias with a shorter name for future callers.
def run_correction_pipeline(
    text: str,
    *,
    pipeline_mode: str = CORRECTION_PIPELINE_MODE,
    ai_provider_mode: str = AI_PROVIDER,
) -> CorrectionResult:
    """
    Alias for correct_with_orchestration().
    """
    return correct_with_orchestration(
        text,
        pipeline_mode=pipeline_mode,
        ai_provider_mode=ai_provider_mode,
    )


def get_event_source_for_result(result: CorrectionResult) -> str:
    """
    Determines the database source for an orchestrated CorrectionResult.

    Returns:
        "dictionary" or "ai_context"

    Notes:
        The app uses this to save one event per changed hotkey correction.
        No-change results should be skipped before calling this function.
    """
    for record in result.corrections:
        if record.get("pipeline_stage") == "ai_context":
            return "ai_context"

    if result.engine_version.endswith(":ai_context"):
        return "ai_context"

    return "dictionary"


def _as_orchestrator_result(
    *,
    original_text: str,
    corrected_text: str,
    changed: bool,
    corrections: list[dict[str, object]],
    route: str,
) -> CorrectionResult:
    """
    Builds a CorrectionResult that identifies the orchestrator route.
    """
    return CorrectionResult(
        original_text=original_text,
        corrected_text=corrected_text,
        changed=changed,
        corrections=corrections,
        engine_version=f"{ORCHESTRATOR_VERSION}:{route}",
    )


def _tag_correction_records(
    correction_records: list[dict[str, object]],
    pipeline_stage: str,
) -> list[dict[str, object]]:
    """
    Adds lightweight pipeline-stage metadata to correction records.

    The original records are copied so lower-level engine outputs are not mutated.
    """
    tagged_records: list[dict[str, object]] = []

    for record in correction_records:
        tagged_record = deepcopy(record)
        tagged_record["pipeline_stage"] = pipeline_stage
        tagged_records.append(tagged_record)

    return tagged_records
