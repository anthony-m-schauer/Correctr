"""
Show all Correctr correction events.

Purpose:
    Prints the full correction_events history from the local SQLite database.
    This is useful for QA/data-quality review when show_recent_events.py is too limited.

Usage from the project root:
    python scripts/show_all_events.py
    python scripts/show_all_events.py --limit 100
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from correctr.database import fetch_recent_correction_events, get_database_path  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show all Correctr correction events."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100000,
        help="Maximum number of events to show. Default: 100000.",
    )

    args = parser.parse_args()

    events = fetch_recent_correction_events(limit=args.limit)

    print("Correctr ALL correction events")
    print("--------------------------------")
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
        print(f"Review status: {event['review_status']}")

        if event.get("reviewed_at"):
            print(f"Reviewed at: {event['reviewed_at']}")

        if event.get("linked_event_id") is not None:
            print(f"Linked event id: {event['linked_event_id']}")

        print(f"Original: {event['original_text']}")
        print(f"Corrected: {event['corrected_text']}")
        print(f"Corrections: {event['corrections']}")

        if event.get("notes"):
            print(f"Notes: {event['notes']}")

        if event.get("review_notes"):
            print(f"Review notes: {event['review_notes']}")

        print("--------------------------------")


if __name__ == "__main__":
    main()
