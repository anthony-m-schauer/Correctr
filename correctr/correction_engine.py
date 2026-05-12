"""
Correctr Correction Engine

Purpose:
    Provides a small local deterministic correction layer.

Current scope:
    Correction Engine_v0.3 Structured Correction Result + Regression Tests.

This module performs direct word-level typo replacements only.
It does not use a spellcheck package, database memory, LLM calls,
neural ranking, suggestion UI, or sentence rewriting.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass


ENGINE_VERSION = "local_dictionary_v0.3"

KNOWN_TYPO_REASON = "known_typo_dictionary"


# Small deterministic typo dictionary for the first real correction layer.
# Keys should stay lowercase. Capitalization is handled separately.
TYPO_CORRECTIONS: dict[str, str] = {
    "testig": "testing",
    "misakes": "mistakes",
    "hopfully": "hopefully",
    "maknig": "making",
    "sentencs": "sentences",
    "somehting": "something",
    "stamdard": "standard",
    "nural": "neural",
    "contexr": "context",
    "hightlight": "highlight",
    "implimented": "implemented",
    "enviroment": "environment",
    "seperate": "separate",
    "recieve": "receive",
    "occured": "occurred",
}


WORD_PATTERN = re.compile(r"\b[A-Za-z]+\b")


@dataclass(frozen=True)
class CorrectionResult:
    """
    Structured result from the local correction engine.

    This prepares Correctr for future layers such as database logging,
    personal memory, confidence rules, spellcheck candidates, and LLM/ranker
    scoring without adding those systems yet.
    """

    original_text: str
    corrected_text: str
    changed: bool
    corrections: list[dict[str, object]]
    engine_version: str = ENGINE_VERSION


def correct_text(text: str, typo_corrections: Mapping[str, str] | None = None) -> str:
    """
    Returns only the corrected text.

    This is the simple public function used by the current app/hotkey workflow.
    """
    return correct_text_detailed(text, typo_corrections=typo_corrections).corrected_text


def correct_text_detailed(
    text: str,
    typo_corrections: Mapping[str, str] | None = None,
) -> CorrectionResult:
    """
    Corrects known typos and returns structured correction information.

    Args:
        text:
            The selected text copied from the user's active app.
        typo_corrections:
            Optional correction dictionary for tests or future configuration.
            Keys should be lowercase typo forms. Values should be lowercase
            correction forms.

    Returns:
        CorrectionResult with original text, corrected text, changed flag,
        correction records, and engine version.

    Behavior:
        - Preserves basic punctuation because only word tokens are replaced.
        - Preserves basic capitalization:
            testig -> testing
            Testig -> Testing
            TESTIG -> TESTING
        - Does not rewrite sentence structure or style.
    """
    corrections_map = typo_corrections or TYPO_CORRECTIONS
    correction_records: list[dict[str, object]] = []

    def replace_match(match: re.Match[str]) -> str:
        original_word = match.group(0)
        corrected_base_word = corrections_map.get(original_word.lower())

        if corrected_base_word is None:
            return original_word

        corrected_word = _match_capitalization(original_word, corrected_base_word)

        correction_records.append(
            {
                "original": original_word,
                "corrected": corrected_word,
                "start_index": match.start(),
                "end_index": match.end(),
                "reason": KNOWN_TYPO_REASON,
            }
        )

        return corrected_word

    corrected_text = WORD_PATTERN.sub(replace_match, text)

    return CorrectionResult(
        original_text=text,
        corrected_text=corrected_text,
        changed=corrected_text != text,
        corrections=correction_records,
        engine_version=ENGINE_VERSION,
    )


def _match_capitalization(original_word: str, corrected_word: str) -> str:
    """
    Applies the original word's simple capitalization pattern to the correction.

    This intentionally handles only basic cases for v0.3:
        - ALL CAPS
        - Title case / first letter uppercase
        - lowercase

    More complex casing can be handled later if it becomes necessary.
    """
    if original_word.isupper():
        return corrected_word.upper()

    if original_word[:1].isupper():
        return corrected_word.capitalize()

    return corrected_word


# Backward-compatible wrapper for Hotkey Clipboard_v0.1 code paths.
# New code should call correct_text().
def run_placeholder_correction(original_text: str) -> str:
    """
    Deprecated compatibility wrapper.

    Hotkey Clipboard_v0.1 called this function name. Keeping it here prevents
    older app.py versions from breaking, but it now runs local corrections.
    """
    return correct_text(original_text)
