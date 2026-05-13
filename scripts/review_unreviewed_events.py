"""
Review unreviewed Correctr correction events one at a time.

Run from the project root:
    python scripts/review_unreviewed_events.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from textwrap import shorten
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from correctr.database import (  # noqa: E402
    fetch_unreviewed_correction_events,
    mark_correction_event_reviewed,
    save_manual_correction_from_event,
)


def parse_corrections_json(corrections_json: Any) -> list[dict[str, Any]]:
    """
    Safely parses corrections_json for compact terminal display.
    """
    if corrections_json is None:
        return []

    if isinstance(corrections_json, list):
        return [item for item in corrections_json if isinstance(item, dict)]

    text = str(corrections_json).strip()

    if not text:
        return []

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return []

    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]

    if isinstance(parsed, dict):
        return [parsed]

    return []


def extract_event_metadata(event: dict[str, Any]) -> dict[str, Any]:
    """
    Extracts provider/model/route reason info from correction records.
    """
    corrections = event.get("corrections")

    if not corrections:
        corrections = parse_corrections_json(event.get("corrections_json"))

    provider = None
    model = None
    pipeline_stage = None
    route_reasons: list[str] = []

    for correction in corrections:
        provider = provider or correction.get("provider")
        model = model or correction.get("model")
        pipeline_stage = pipeline_stage or correction.get("pipeline_stage")

        raw_reasons = correction.get("route_reasons")

        if isinstance(raw_reasons, list):
            for reason in raw_reasons:
                reason_text = str(reason)

                if reason_text not in route_reasons:
                    route_reasons.append(reason_text)

    return {
        "provider": provider,
        "model": model,
        "pipeline_stage": pipeline_stage,
        "route_reasons": route_reasons,
    }


def print_text_block(label: str, text: str) -> None:
    """
    Prints a readable text block without exporting data anywhere.
    """
    print(f"{label}:")
    print(str(text))
    print()


def print_event(event: dict[str, Any], index: int, total: int) -> None:
    """
    Prints one unreviewed event with enough context to decide quickly.
    """
    metadata = extract_event_metadata(event)
    route_reasons: list[str] = metadata.get("route_reasons") or []

    print("-" * 72)
    print(f"Unreviewed event {index} of {total}")
    print()
    print(f"ID: {event.get('id')}")
    print(f"Created: {event.get('created_at')}")
    print(f"Source: {event.get('source')}")
    print(f"Engine: {event.get('engine_version')}")

    ai_metadata = []

    if metadata.get("provider"):
        ai_metadata.append(f"provider={metadata['provider']}")

    if metadata.get("model"):
        ai_metadata.append(f"model={metadata['model']}")

    if metadata.get("pipeline_stage"):
        ai_metadata.append(f"stage={metadata['pipeline_stage']}")

    if ai_metadata:
        print("AI metadata: " + ", ".join(ai_metadata))

    notes = event.get("notes")

    if notes:
        print(f"Notes: {shorten(str(notes), width=120, placeholder='...')}")

    print()
    print_text_block("Original", str(event.get("original_text", "")))
    print_text_block("Corrected", str(event.get("corrected_text", "")))

    if route_reasons:
        print("Route reasons:")

        for reason in route_reasons:
            print(f"- {reason}")

        print()

    print("Choose:")
    print("[A] accept as trusted")
    print("[R] reject")
    print("[F] fix / create manual correction")
    print("[T] mark as test/dev event")
    print("[U] mark uncertain")
    print("[S] skip for now")
    print("[Q] quit")


def prompt_choice() -> str:
    """
    Prompts until the user enters a valid review command.
    """
    while True:
        choice = input("Choice: ").strip().lower()

        if choice in {"a", "r", "f", "t", "u", "s", "q"}:
            return choice

        print("Please enter A, R, F, T, U, S, or Q.")


def review_event(event: dict[str, Any], index: int, total: int) -> bool:
    """
    Reviews one event.

    Returns:
        True to continue the queue, False to quit.
    """
    print_event(event, index, total)

    choice = prompt_choice()
    event_id = int(event["id"])

    if choice == "a":
        mark_correction_event_reviewed(
            event_id=event_id,
            review_status="accepted",
            review_notes="Accepted from unreviewed-event review queue.",
        )
        print(f"Accepted event ID {event_id} as trusted.")
        return True

    if choice == "r":
        mark_correction_event_reviewed(
            event_id=event_id,
            review_status="rejected",
            review_notes="Rejected from unreviewed-event review queue.",
        )
        print(f"Rejected event ID {event_id}.")
        return True

    if choice == "f":
        print()
        print("Enter the intended corrected text.")
        print("Leave blank to cancel the fix and keep this event unreviewed.")
        intended = input("Intended correction: ").strip()

        if not intended:
            print("Fix cancelled. Event left unreviewed.")
            return True

        manual_event_id = save_manual_correction_from_event(
            event_id=event_id,
            corrected_text=intended,
            notes=f"Manual correction from review queue event ID {event_id}.",
        )
        print(
            f"Created accepted manual event ID {manual_event_id} linked to original event ID {event_id}."
        )
        print(f"Marked original event ID {event_id} as manually_corrected.")
        return True

    if choice == "t":
        mark_correction_event_reviewed(
            event_id=event_id,
            review_status="test_event",
            review_notes="Marked as test/development event from unreviewed-event review queue.",
        )
        print(f"Marked event ID {event_id} as test_event.")
        return True

    if choice == "u":
        mark_correction_event_reviewed(
            event_id=event_id,
            review_status="uncertain",
            review_notes="Marked uncertain from unreviewed-event review queue.",
        )
        print(f"Marked event ID {event_id} as uncertain.")
        return True

    if choice == "s":
        print(f"Skipped event ID {event_id}. It remains unreviewed.")
        return True

    print("Exiting review queue.")
    return False


def main() -> None:
    """
    Runs the unreviewed event queue.
    """
    print("Correctr unreviewed correction event review queue")
    print("=" * 52)
    print()

    events = fetch_unreviewed_correction_events(oldest_first=True)
    total = len(events)

    if total == 0:
        print("No unreviewed correction events found.")
        return

    print(f"Found {total} unreviewed correction event(s).")
    print("Review decisions are saved immediately after each event.")
    print()

    events_shown = 0

    for index, event in enumerate(events, start=1):
        events_shown += 1
        should_continue = review_event(event, index, total)
        print()

        if not should_continue:
            break

    remaining = len(fetch_unreviewed_correction_events(oldest_first=True))
    print("Review queue session complete.")
    print(f"Events shown this session: {events_shown}")
    print(f"Unreviewed events remaining: {remaining}")


if __name__ == "__main__":
    main()
