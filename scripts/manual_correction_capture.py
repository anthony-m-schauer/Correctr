"""
Manual correction capture script for Correctr.

Run from the project root:

    python scripts/manual_correction_capture.py

This script captures a manual teach-back example:
    original bad text -> corrected text

The saved event uses:
    source = manual
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from correctr.database import fetch_recent_correction_events, get_database_path, save_manual_correction  # noqa: E402


def main() -> None:
    print("Correctr Manual Correction Capture_v0.1")
    print("----------------------------------------")
    print("Enter the original bad text and the corrected version.")
    print()

    original_text = input("Original bad text: ").strip()
    corrected_text = input("Corrected text: ").strip()
    notes = input("Optional note: ").strip()

    if not original_text:
        print("No original text entered. Nothing saved.")
        return

    if not corrected_text:
        print("No corrected text entered. Nothing saved.")
        return

    event_id = save_manual_correction(
        original_text=original_text,
        corrected_text=corrected_text,
        notes=notes,
    )

    recent_event = fetch_recent_correction_events(limit=1)[0]

    print()
    print("Manual correction saved.")
    print(f"Event id: {event_id}")
    print(f"Source: {recent_event['source']}")
    print(f"Changed: {recent_event['changed']}")
    print(f"Database path: {get_database_path()}")


if __name__ == "__main__":
    main()
