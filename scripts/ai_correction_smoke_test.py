"""
Smoke test for Correctr AI Context Correction_v0.1.

Run from the project root:

    python scripts/ai_correction_smoke_test.py

This uses the deterministic mock provider. It does not call an external model,
does not require API keys, and does not require local model setup.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from correctr.config import get_default_config  # noqa: E402
from correctr.llm_engine import correct_with_ai_context  # noqa: E402


SAMPLE_TEXTS = [
    "shiuld this not also be abl eto fix this?",
    "These are testing mis takes for the app to hopefully fix. i ma making two sentences.",
    "This sentence should not change.",
]


def main() -> None:
    config = get_default_config()

    print("Correctr AI Context Correction_v0.1 Smoke Test")
    print("---------------------------------------------")
    print(f"Provider mode: {config.ai_provider}")
    print()

    for sample_text in SAMPLE_TEXTS:
        result = correct_with_ai_context(sample_text, provider_mode=config.ai_provider)

        print("Original text:")
        print(result.original_text)
        print()
        print("Corrected text:")
        print(result.corrected_text)
        print()
        print("Changed:")
        print(result.changed)
        print()
        print("Correction records:")
        if not result.corrections:
            print("No corrections made.")
        else:
            for record in result.corrections:
                print(
                    f"- {record['original']} -> {record['corrected']} "
                    f"({record['reason']}, provider={record['provider']}, "
                    f"indexes {record['start_index']}-{record['end_index']})"
                )
        print()
        print("Engine version:")
        print(result.engine_version)
        print("---------------------------------------------")


if __name__ == "__main__":
    main()
