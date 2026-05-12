"""
Smoke test for Correctr Correction Engine_v0.3.

Run from the project root:

    python scripts/smoke_test_correction.py

This is a simple project-useful script for checking the local correction engine
without starting the hotkey/clipboard app.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from correctr.correction_engine import correct_text_detailed  # noqa: E402


def main() -> None:
    original_text = "These are testig misakes for the app to hopfully fix. I am maknig two sentencs."
    result = correct_text_detailed(original_text)

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
                f"({record['reason']}, indexes {record['start_index']}-{record['end_index']})"
            )
    print()
    print("Engine version:")
    print(result.engine_version)


if __name__ == "__main__":
    main()
