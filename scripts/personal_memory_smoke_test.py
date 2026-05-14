"""
Smoke test the Personal Memory Lookup_v0.1 layer.

Run from the project root:
    python scripts/personal_memory_smoke_test.py

This script reads trusted manual memory examples from the local database, if
available. It does not modify the database.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from correctr.personal_memory import (  # noqa: E402
    correct_with_personal_memory,
    load_trusted_memory_examples,
    normalize_memory_text,
)


def main() -> None:
    print("Correctr Personal Memory Smoke Test")
    print("====================================")
    print()

    examples = load_trusted_memory_examples()
    print(f"Trusted manual memory examples available: {len(examples)}")
    print()

    if not examples:
        print("No trusted manual examples found.")
        print("Use collect mode to accept/manual-fix examples, then rerun this script.")
        return

    first_example = examples[0]

    print("Exact match test")
    print("----------------")
    exact_result = correct_with_personal_memory(
        first_example.original_text,
        examples=examples,
    )
    print(f"Trusted event ID: {first_example.event_id}")
    print(f"Original: {exact_result.original_text}")
    print(f"Corrected: {exact_result.corrected_text}")
    print(f"Changed: {exact_result.changed}")
    print(f"Engine: {exact_result.engine_version}")
    if exact_result.corrections:
        print(f"Match type: {exact_result.corrections[0].get('match_type')}")
    print()

    print("Normalized match test")
    print("---------------------")
    normalized_input = f"  {first_example.original_text.upper()}  "
    normalized_result = correct_with_personal_memory(
        normalized_input,
        examples=examples,
    )
    print(f"Normalized input: {normalized_input}")
    print(f"Normalized comparison key: {normalize_memory_text(normalized_input)}")
    print(f"Corrected: {normalized_result.corrected_text}")
    print(f"Changed: {normalized_result.changed}")
    print(f"Engine: {normalized_result.engine_version}")
    if normalized_result.corrections:
        print(f"Match type: {normalized_result.corrections[0].get('match_type')}")
    print()

    print("No-match safety test")
    print("--------------------")
    no_match_result = correct_with_personal_memory(
        "This sentence should not be in personal memory yet.",
        examples=examples,
    )
    print(f"Corrected: {no_match_result.corrected_text}")
    print(f"Changed: {no_match_result.changed}")
    print(f"Engine: {no_match_result.engine_version}")


if __name__ == "__main__":
    main()
