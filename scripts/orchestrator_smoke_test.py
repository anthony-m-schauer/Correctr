"""
Smoke test for Correctr Correction Orchestrator_v0.2.

Run from the project root:

    python scripts/orchestrator_smoke_test.py

This script does not start the hotkey app. It checks controlled routing between
dictionary correction and the configured AI/context provider.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from correctr.config import get_default_config  # noqa: E402
from correctr.correction_engine import correct_text_detailed  # noqa: E402
from correctr.correction_orchestrator import (  # noqa: E402
    correct_with_orchestration,
    get_event_source_for_result,
    should_route_to_ai,
)


SMOKE_CASES = [
    (
        "dictionary_then_ai_if_needed",
        "This is already correct.",
    ),
    (
        "dictionary_then_ai_if_needed",
        "shiuld this not also be abl eto fix this?",
    ),
    (
        "dictionary_then_ai_if_needed",
        "These are testig misakes for the app to hopfully fix. I am maknig two sentencs.",
    ),
    (
        "dictionary_then_ai_if_needed",
        "These are testig mis takes for the app to hopfully fix. i ma maknig two sentencs.",
    ),
    (
        "dictionary_then_ai_if_needed",
        "Snother testin gexample.",
    ),
    (
        "dictionary_only",
        "These are testig misakes for the app to hopfully fix. I am maknig two sentencs.",
    ),
    (
        "dictionary_then_ai_if_unchanged",
        "shiuld this not also be abl eto fix this?",
    ),
    (
        "dictionary_then_ai_always",
        "These are testig mis takes for the app to hopfully fix. i ma maknig two sentencs.",
    ),
]


def main() -> None:
    config = get_default_config()

    print("Correctr Correction Orchestrator_v0.2 Smoke Test")
    print("------------------------------------------------")
    print(f"Configured AI provider: {config.ai_provider}")
    print(f"Configured Ollama model: {config.ollama_model}")
    print()

    for mode, text in SMOKE_CASES:
        dictionary_result = correct_text_detailed(text)
        decision = should_route_to_ai(
            original_text=text,
            dictionary_result=dictionary_result,
        )
        result = correct_with_orchestration(
            text,
            pipeline_mode=mode,
            ai_provider_mode=config.ai_provider,
        )

        expected_source = "no_event"
        if result.changed:
            expected_source = get_event_source_for_result(result)

        print(f"Mode: {mode}")
        print("Original text:")
        print(result.original_text)
        print()
        print("Corrected text:")
        print(result.corrected_text)
        print()
        print("Changed:")
        print(result.changed)
        print()
        print("Engine version:")
        print(result.engine_version)
        print()
        print("AI-if-needed decision preview:")
        print(f"use_ai = {decision.use_ai}")
        print(f"reasons = {decision.reasons}")
        print()
        print("Expected event source if app logs this result:")
        print(expected_source)
        print()
        print("Correction records:")
        if not result.corrections:
            print("No corrections made.")
        else:
            for record in result.corrections:
                print(f"- {record}")
        print("------------------------------------------------")


if __name__ == "__main__":
    main()
