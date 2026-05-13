"""
Correctr Correction Orchestrator

Purpose:
    Coordinates local dictionary correction and AI/context correction through
    a controlled routing layer.

Current scope:
    Controlled App Routing_v0.2 Dictionary-First AI-If-Needed Routing.

This module is the coordination layer above:
    - correctr.correction_engine
    - correctr.llm_engine

It does not implement real OpenAI calls, neural ranking, suggestion UI,
personal memory lookup, advanced spellcheck, or confidence scoring.
"""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Literal

from correctr.config import (
    AI_PROVIDER,
    CORRECTION_PIPELINE_MODE,
    validate_ai_provider,
    validate_correction_pipeline_mode,
)
from correctr.correction_engine import CorrectionResult, correct_text_detailed
from correctr.llm_engine import correct_with_ai_context


ORCHESTRATOR_VERSION = "orchestrator_v0.2"

PipelineMode = Literal[
    "dictionary_only",
    "dictionary_then_ai_if_unchanged",
    "dictionary_then_ai_always",
    "dictionary_then_ai_if_needed",
]


HARD_TYPO_TOKENS = {
    "shiuld",
    "thsi",
    "snother",
    "pracitve",
    "sentenc",
    "habe",
    "testin",
    "gexample",
}

SPLIT_WORD_PATTERNS = {
    "abl eto": "likely_spacing_error",
    "mis takes": "likely_spacing_error",
    "i ma": "likely_spacing_error",
    "th e": "likely_spacing_error",
    "th ethird": "likely_spacing_error",
    "testin gexample": "likely_spacing_error",
}


@dataclass(frozen=True)
class RoutingDecision:
    """
    Result of deciding whether the orchestrator should call AI/context.
    """

    use_ai: bool
    reasons: list[str]


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

        dictionary_then_ai_if_needed:
            Run dictionary correction first.
            Use lightweight typo/spacing signals to decide whether AI/context
            should run. This avoids calling AI on obviously clean text.
    """
    pipeline_mode = validate_correction_pipeline_mode(pipeline_mode)
    ai_provider_mode = validate_ai_provider(ai_provider_mode)

    dictionary_result = correct_text_detailed(text)

    if pipeline_mode == "dictionary_only":
        return _dictionary_orchestrator_result(text, dictionary_result)

    if pipeline_mode == "dictionary_then_ai_if_unchanged":
        if dictionary_result.changed:
            return _dictionary_orchestrator_result(text, dictionary_result)

        ai_result = correct_with_ai_context(text, provider_mode=ai_provider_mode)
        return _ai_or_no_change_result(
            original_text=text,
            dictionary_result=dictionary_result,
            ai_result=ai_result,
            route="ai_context",
            route_reasons=["dictionary_no_change_ai_route"],
        )

    if pipeline_mode == "dictionary_then_ai_always":
        ai_result = correct_with_ai_context(
            dictionary_result.corrected_text,
            provider_mode=ai_provider_mode,
        )
        return _dictionary_then_ai_result(
            original_text=text,
            dictionary_result=dictionary_result,
            ai_result=ai_result,
            route_reasons=["ai_always_mode"],
        )

    if pipeline_mode == "dictionary_then_ai_if_needed":
        decision = should_route_to_ai(
            original_text=text,
            dictionary_result=dictionary_result,
        )

        if not decision.use_ai:
            return _dictionary_orchestrator_result(
                original_text=text,
                dictionary_result=dictionary_result,
                route_reasons=decision.reasons,
            )

        ai_input = dictionary_result.corrected_text if dictionary_result.changed else text
        ai_result = correct_with_ai_context(ai_input, provider_mode=ai_provider_mode)

        if dictionary_result.changed:
            return _dictionary_then_ai_result(
                original_text=text,
                dictionary_result=dictionary_result,
                ai_result=ai_result,
                route_reasons=decision.reasons,
            )

        return _ai_or_no_change_result(
            original_text=text,
            dictionary_result=dictionary_result,
            ai_result=ai_result,
            route="ai_context",
            route_reasons=decision.reasons,
        )

    # validate_correction_pipeline_mode should prevent this path.
    raise ValueError(f"Unhandled correction pipeline mode: {pipeline_mode!r}")


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


def should_route_to_ai(
    *,
    original_text: str,
    dictionary_result: CorrectionResult,
) -> RoutingDecision:
    """
    Decides whether AI/context should be used after dictionary correction.

    This is a lightweight gate, not a full spellchecker. It looks for known
    hard typo tokens and split-word patterns from current Correctr testing.
    """
    text_to_check = dictionary_result.corrected_text if dictionary_result.changed else original_text
    reasons = detect_suspicious_text_signals(text_to_check)

    if dictionary_result.changed and reasons:
        return RoutingDecision(
            use_ai=True,
            reasons=["dictionary_changed_but_residual_suspicious_pattern", *reasons],
        )

    if not dictionary_result.changed and reasons:
        return RoutingDecision(
            use_ai=True,
            reasons=["dictionary_no_change_but_suspicious_pattern", *reasons],
        )

    if dictionary_result.changed:
        return RoutingDecision(
            use_ai=False,
            reasons=["dictionary_changed_no_residual_suspicious_pattern"],
        )

    return RoutingDecision(
        use_ai=False,
        reasons=["clean_text_gate_skipped_ai"],
    )


def detect_suspicious_text_signals(text: str) -> list[str]:
    """
    Detects simple typo/spacing signals that justify AI/context correction.

    Returns:
        List of reason codes. Empty list means no suspicious signal was found.
    """
    lowered_text = text.lower()
    reasons: list[str] = []

    for pattern, reason_code in sorted(SPLIT_WORD_PATTERNS.items()):
        if pattern in lowered_text:
            _append_unique(reasons, reason_code)
            _append_unique(reasons, f"pattern:{pattern}")

    tokens = re.findall(r"\b[a-zA-Z]+\b", lowered_text)
    for token in tokens:
        if token in HARD_TYPO_TOKENS:
            _append_unique(reasons, "likely_typo_token")
            _append_unique(reasons, f"token:{token}")

    return reasons


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

    if result.engine_version.endswith(":ai_context") or result.engine_version.endswith(":dictionary_then_ai"):
        return "ai_context"

    return "dictionary"


def _dictionary_orchestrator_result(
    original_text: str,
    dictionary_result: CorrectionResult,
    route_reasons: list[str] | None = None,
) -> CorrectionResult:
    """
    Wraps a dictionary result in orchestrator metadata.
    """
    return _as_orchestrator_result(
        original_text=original_text,
        corrected_text=dictionary_result.corrected_text,
        changed=dictionary_result.changed,
        corrections=_add_route_reasons(
            _tag_correction_records(dictionary_result.corrections, "dictionary"),
            route_reasons or [],
        ),
        route="dictionary",
    )


def _ai_or_no_change_result(
    *,
    original_text: str,
    dictionary_result: CorrectionResult,
    ai_result: CorrectionResult,
    route: str,
    route_reasons: list[str],
) -> CorrectionResult:
    """
    Returns an AI result unless it failed/rejected/fell back.

    If AI fails and dictionary made no useful change, this returns a safe
    no-change result.
    """
    if _ai_result_failed(ai_result):
        return _as_orchestrator_result(
            original_text=original_text,
            corrected_text=dictionary_result.corrected_text,
            changed=dictionary_result.changed,
            corrections=_add_route_reasons(
                _tag_correction_records(dictionary_result.corrections, "dictionary"),
                [*route_reasons, "ai_failed_or_rejected_safe_result_used"],
            ),
            route="dictionary" if dictionary_result.changed else "no_change",
        )

    return _as_orchestrator_result(
        original_text=original_text,
        corrected_text=ai_result.corrected_text,
        changed=ai_result.corrected_text != original_text,
        corrections=_add_route_reasons(
            _tag_correction_records(ai_result.corrections, "ai_context"),
            route_reasons,
        ),
        route=route,
    )


def _dictionary_then_ai_result(
    *,
    original_text: str,
    dictionary_result: CorrectionResult,
    ai_result: CorrectionResult,
    route_reasons: list[str],
) -> CorrectionResult:
    """
    Combines dictionary and AI results, while keeping safe fallback behavior.
    """
    dictionary_records = _tag_correction_records(dictionary_result.corrections, "dictionary")

    if _ai_result_failed(ai_result):
        return _as_orchestrator_result(
            original_text=original_text,
            corrected_text=dictionary_result.corrected_text,
            changed=dictionary_result.changed,
            corrections=_add_route_reasons(
                dictionary_records,
                [*route_reasons, "ai_failed_or_rejected_dictionary_result_kept"],
            ),
            route="dictionary" if dictionary_result.changed else "no_change",
        )

    if not ai_result.changed and dictionary_result.changed:
        return _as_orchestrator_result(
            original_text=original_text,
            corrected_text=dictionary_result.corrected_text,
            changed=True,
            corrections=_add_route_reasons(
                dictionary_records,
                [*route_reasons, "ai_no_change_dictionary_result_kept"],
            ),
            route="dictionary",
        )

    combined_corrections = [
        *dictionary_records,
        *_tag_correction_records(ai_result.corrections, "ai_context"),
    ]

    return _as_orchestrator_result(
        original_text=original_text,
        corrected_text=ai_result.corrected_text,
        changed=ai_result.corrected_text != original_text,
        corrections=_add_route_reasons(combined_corrections, route_reasons),
        route="dictionary_then_ai",
    )


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


def _add_route_reasons(
    correction_records: list[dict[str, object]],
    route_reasons: list[str],
) -> list[dict[str, object]]:
    """
    Adds route reasons to each correction record for debugging and logging.

    If no correction records exist, no synthetic record is added. No-change
    results should stay uncluttered.
    """
    if not route_reasons:
        return correction_records

    updated_records: list[dict[str, object]] = []

    for record in correction_records:
        updated_record = deepcopy(record)
        updated_record["route_reasons"] = list(route_reasons)
        updated_records.append(updated_record)

    return updated_records


def _ai_result_failed(result: CorrectionResult) -> bool:
    """
    Returns True when AI/context returned a fallback or rejected result.
    """
    if result.engine_version.endswith(":fallback") or result.engine_version.endswith(":rejected"):
        return True

    return any(
        record.get("reason") in {"ollama_fallback", "ai_output_rejected"}
        for record in result.corrections
    )


def _append_unique(items: list[str], value: str) -> None:
    """
    Appends value to items only if not already present.
    """
    if value not in items:
        items.append(value)
