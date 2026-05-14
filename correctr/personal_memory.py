"""
Correctr Personal Memory Lookup Layer

Purpose:
    Looks up trusted manual correction examples before slower or less-trusted
    correction layers are used.

Current scope:
    Personal Memory Lookup_v0.1 Trusted Manual Memory Layer.

This is not a neural ranker, model-training system, fuzzy matcher, or broad
memory engine. It is intentionally conservative:
    - trusted manual/collect-mode accepted examples only
    - exact match first
    - simple normalized match second
    - safe no-change result when no match exists
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from correctr.correction_engine import CorrectionResult
from correctr.database import fetch_trusted_correction_events


PERSONAL_MEMORY_ENGINE_VERSION = "personal_memory_v0.1"
PERSONAL_MEMORY_REASON = "trusted_manual_memory"
PERSONAL_MEMORY_PIPELINE_STAGE = "personal_memory"


@dataclass(frozen=True)
class MemoryExample:
    """
    One trusted memory example loaded from reviewed manual correction data.
    """

    event_id: int
    original_text: str
    corrected_text: str
    source: str
    review_status: str
    engine_version: str
    linked_event_id: int | None = None
    notes: str = ""
    review_notes: str = ""


def normalize_memory_text(text: str) -> str:
    """
    Normalizes text for conservative memory matching.

    v0.1 intentionally keeps this simple:
        - trim leading/trailing whitespace
        - collapse repeated whitespace
        - compare case-insensitively
    """
    collapsed = re.sub(r"\s+", " ", text.strip())
    return collapsed.casefold()


def load_trusted_memory_examples(
    *,
    database_path: str | Path | None = None,
    limit: int | None = None,
) -> list[MemoryExample]:
    """
    Loads trusted manual correction examples for personal memory lookup.

    v0.1 policy:
        Include only source = manual and review_status = accepted rows.
        This includes collect-mode manual corrections and linked teach-back
        corrections because both are stored as accepted manual rows.

    Excluded by policy:
        accepted ai_context, accepted dictionary, rejected, test_event,
        uncertain, unreviewed, and manually_corrected raw history rows.
    """
    trusted_events = fetch_trusted_correction_events(
        database_path=database_path,
        limit=limit,
        include_accepted_ai=False,
        oldest_first=True,
        exclude_blank=True,
        exclude_unchanged=True,
        deduplicate_exact_pairs=True,
    )

    examples: list[MemoryExample] = []

    for event in trusted_events:
        if event.get("source") != "manual":
            continue

        if event.get("review_status") != "accepted":
            continue

        examples.append(
            MemoryExample(
                event_id=int(event["id"]),
                original_text=str(event["original_text"]),
                corrected_text=str(event["corrected_text"]),
                source=str(event["source"]),
                review_status=str(event["review_status"]),
                engine_version=str(event["engine_version"]),
                linked_event_id=event.get("linked_event_id"),
                notes=str(event.get("notes") or ""),
                review_notes=str(event.get("review_notes") or ""),
            )
        )

    return examples


def find_exact_memory_match(
    text: str,
    *,
    examples: list[MemoryExample] | None = None,
    database_path: str | Path | None = None,
) -> MemoryExample | None:
    """
    Finds a trusted memory example whose original_text exactly matches text.
    """
    memory_examples = examples if examples is not None else load_trusted_memory_examples(
        database_path=database_path,
    )

    for example in memory_examples:
        if example.original_text == text:
            return example

    return None


def find_normalized_memory_match(
    text: str,
    *,
    examples: list[MemoryExample] | None = None,
    database_path: str | Path | None = None,
) -> MemoryExample | None:
    """
    Finds a trusted memory example using conservative normalized comparison.
    """
    memory_examples = examples if examples is not None else load_trusted_memory_examples(
        database_path=database_path,
    )
    normalized_text = normalize_memory_text(text)

    for example in memory_examples:
        if normalize_memory_text(example.original_text) == normalized_text:
            return example

    return None


def correct_with_personal_memory(
    text: str,
    *,
    database_path: str | Path | None = None,
    examples: list[MemoryExample] | None = None,
) -> CorrectionResult:
    """
    Applies trusted personal memory correction when a match is found.

    Returns a CorrectionResult for both hit and no-hit cases so the
    orchestrator can safely route after memory lookup.
    """
    memory_examples = examples if examples is not None else load_trusted_memory_examples(
        database_path=database_path,
    )

    exact_match = find_exact_memory_match(text, examples=memory_examples)
    if exact_match is not None:
        return _memory_hit_result(text=text, example=exact_match, match_type="exact")

    normalized_match = find_normalized_memory_match(text, examples=memory_examples)
    if normalized_match is not None:
        return _memory_hit_result(text=text, example=normalized_match, match_type="normalized")

    return CorrectionResult(
        original_text=text,
        corrected_text=text,
        changed=False,
        corrections=[],
        engine_version=f"{PERSONAL_MEMORY_ENGINE_VERSION}:no_match",
    )


def _memory_hit_result(*, text: str, example: MemoryExample, match_type: str) -> CorrectionResult:
    """
    Builds a CorrectionResult for a trusted memory match.
    """
    corrected_text = example.corrected_text

    return CorrectionResult(
        original_text=text,
        corrected_text=corrected_text,
        changed=corrected_text != text,
        corrections=[
            {
                "original": text,
                "corrected": corrected_text,
                "start_index": 0,
                "end_index": len(text),
                "reason": PERSONAL_MEMORY_REASON,
                "source": PERSONAL_MEMORY_PIPELINE_STAGE,
                "pipeline_stage": PERSONAL_MEMORY_PIPELINE_STAGE,
                "match_type": match_type,
                "trusted_event_id": example.event_id,
                "linked_event_id": example.linked_event_id,
                "trusted_engine_version": example.engine_version,
            }
        ],
        engine_version=f"{PERSONAL_MEMORY_ENGINE_VERSION}:{match_type}",
    )
