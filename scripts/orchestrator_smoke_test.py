"""
Smoke test for Correctr Correction Orchestrator_v0.1.

Run from the project root:

    python scripts/orchestrator_smoke_test.py

This script does not start the hotkey app. It checks controlled routing between
dictionary correction and the mock AI/context provider.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from correctr.correction_orchestrator import correct_with_orchestration  # noqa: E402


SMOKE_CASES = [
    (
        "dictionary_only",
        "These are testig misakes for the app to hopfully fix. I am maknig two sentencs.",
    ),
    (
        "dictionary_then_ai_if_unchanged",
        "shiuld this not also be abl eto fix this?",
    ),
    (
        "dictionary_then_ai_if_unchanged",
        "These are testing mis takes for the app to hopefully fix. i ma making two sentences.",
    ),
    (
        "dictionary_then_ai_always",
        "These are testig mis takes for the app to hopfully fix. i ma maknig two sentencs.",
    ),
]


def main() -> None:
    print("Correctr Correction Orchestrator_v0.1 Smoke Test")
    print("------------------------------------------------")

    for mode, text in SMOKE_CASES:
        result = correct_with_orchestration(
            text,
            pipeline_mode=mode,
            ai_provider_mode="mock",
        )

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
        print("Correction records:")
        if not result.corrections:
            print("No corrections made.")
        else:
            for record in result.corrections:
                print(f"- {record}")
        print("------------------------------------------------")


if __name__ == "__main__":
    main()
