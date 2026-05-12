"""
Show recent Correctr correction events.

Run from the project root:

    python scripts/show_recent_events.py

This script prints recent events from the local SQLite database so the user can
confirm dictionary and manual correction events were saved.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from correctr.database import fetch_recent_correction_events, get_database_path  # noqa: E402


def main() -> None:
    events = fetch_recent_correction_events(limit=10)

    print("Correctr recent correction events")
    print("---------------------------------")
    print(f"Database path: {get_database_path()}")
    print()

    if not events:
        print("No correction events found.")
        return

    for event in events:
        print(f"ID: {event['id']}")
        print(f"Created: {event['created_at']}")
        print(f"Source: {event['source']}")
        print(f"Changed: {event['changed']}")
        print(f"Engine: {event['engine_version']}")
        print(f"Original: {event['original_text']}")
        print(f"Corrected: {event['corrected_text']}")
        print(f"Corrections: {event['corrections']}")
        if event["notes"]:
            print(f"Notes: {event['notes']}")
        print("---------------------------------")


if __name__ == "__main__":
    main()
