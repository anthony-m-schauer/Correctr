"""
Review recent Correctr correction events.

Run from the project root:

    python scripts/review_recent_events.py

This is a simple terminal-based review workflow. It lets the user label recent
events and convert bad automatic corrections into manual teach-back examples.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from correctr.database import (  # noqa: E402
    fetch_correction_event_by_id,
    fetch_recent_correction_events,
    mark_correction_event_reviewed,
    save_manual_correction_from_event,
)


def main() -> None:
    print("Correctr Manual Rejection Review_v0.1")
    print("-------------------------------------")

    events = fetch_recent_correction_events(limit=15)

    if not events:
        print("No correction events found.")
        return

    print_recent_events(events)

    event_id = prompt_for_event_id()

    if event_id is None:
        print("Review canceled.")
        return

    event = fetch_correction_event_by_id(event_id)

    if event is None:
        print(f"No event found with id {event_id}.")
        return

    print()
    print_event_details(event)

    action = prompt_for_action()

    if action == "1":
        mark_correction_event_reviewed(
            event_id=event_id,
            review_status="accepted",
            review_notes=prompt_optional_note(),
        )
        print("Event marked accepted.")
    elif action == "2":
        mark_correction_event_reviewed(
            event_id=event_id,
            review_status="rejected",
            review_notes=prompt_optional_note(),
        )
        print("Event marked rejected.")
    elif action == "3":
        corrected_text = input("Enter intended corrected text: ").strip()

        if not corrected_text:
            print("No corrected text entered. Nothing saved.")
            return

        note = prompt_optional_note(
            default=f"Manual correction from reviewed event ID {event_id}."
        )

        new_event_id = save_manual_correction_from_event(
            event_id=event_id,
            corrected_text=corrected_text,
            notes=note,
        )

        mark_correction_event_reviewed(
            event_id=event_id,
            review_status="manually_corrected",
            review_notes=f"Manual correction saved as event ID {new_event_id}.",
        )

        print(f"Manual teach-back event saved. New event id: {new_event_id}")
        print("Original event marked manually_corrected.")
    elif action == "4":
        mark_correction_event_reviewed(
            event_id=event_id,
            review_status="test_event",
            review_notes=prompt_optional_note(),
        )
        print("Event marked test_event.")
    elif action == "5":
        mark_correction_event_reviewed(
            event_id=event_id,
            review_status="uncertain",
            review_notes=prompt_optional_note(),
        )
        print("Event marked uncertain.")
    else:
        print("Review canceled.")


def print_recent_events(events: list[dict[str, Any]]) -> None:
    """
    Prints a compact list of recent events.
    """
    print("Recent correction events:")
    print()

    for event in events:
        print(
            f"ID {event['id']} | source={event['source']} | "
            f"review={event['review_status']} | changed={event['changed']}"
        )
        print(f"Original:  {event['original_text']}")
        print(f"Corrected: {event['corrected_text']}")
        print("-" * 80)


def print_event_details(event: dict[str, Any]) -> None:
    """
    Prints full details for the selected event.
    """
    print("Selected event")
    print("--------------")
    print(f"ID: {event['id']}")
    print(f"Created: {event['created_at']}")
    print(f"Source: {event['source']}")
    print(f"Changed: {event['changed']}")
    print(f"Engine: {event['engine_version']}")
    print(f"Review status: {event['review_status']}")
    print(f"Reviewed at: {event['reviewed_at']}")
    print(f"Linked event id: {event['linked_event_id']}")
    print(f"Notes: {event['notes']}")
    print(f"Review notes: {event['review_notes']}")
    print()
    print("Original:")
    print(event["original_text"])
    print()
    print("Corrected:")
    print(event["corrected_text"])
    print()
    print("Corrections:")
    if not event["corrections"]:
        print("No structured corrections.")
    else:
        for record in event["corrections"]:
            print(f"- {record}")


def prompt_for_event_id() -> int | None:
    """
    Prompts for an event ID.
    """
    raw_value = input("Enter event ID to review, or press Enter to cancel: ").strip()

    if raw_value == "":
        return None

    try:
        return int(raw_value)
    except ValueError:
        print("Invalid event ID. Please enter a number.")
        return None


def prompt_for_action() -> str:
    """
    Prompts for a review action.
    """
    print()
    print("Choose review action:")
    print("1. mark accepted")
    print("2. mark rejected")
    print("3. enter intended correction / manual teach-back")
    print("4. mark test/development event")
    print("5. mark uncertain")
    print("6. cancel")
    return input("Choice: ").strip()


def prompt_optional_note(default: str = "") -> str:
    """
    Prompts for an optional note.
    """
    note = input("Optional review note: ").strip()

    if note:
        return note

    return default


if __name__ == "__main__":
    main()
