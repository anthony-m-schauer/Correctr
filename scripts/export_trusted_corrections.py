"""
Export trusted Correctr correction examples.

Run from the project root:
    python scripts/export_trusted_corrections.py

Outputs are written locally to data/exports/ by default:
    - trusted_corrections.jsonl
    - trusted_corrections.csv
    - data_quality_report.txt

These files may contain private writing and should stay ignored by Git.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from correctr.database import (  # noqa: E402
    DEFAULT_DATABASE_PATH,
    fetch_all_correction_events,
    fetch_trusted_correction_events,
    get_database_path,
)

DEFAULT_EXPORT_DIR = PROJECT_ROOT / "data" / "exports"
JSONL_FILENAME = "trusted_corrections.jsonl"
CSV_FILENAME = "trusted_corrections.csv"
REPORT_FILENAME = "data_quality_report.txt"

EXPORT_COLUMNS = [
    "id",
    "created_at",
    "source",
    "original_text",
    "corrected_text",
    "review_status",
    "linked_event_id",
    "engine_version",
    "notes",
    "review_notes",
    "corrections_json",
    "correction_type",
    "provider",
    "model",
    "route_reasons",
    "original_length",
    "corrected_length",
    "changed",
]


def utc_now_text() -> str:
    """Returns the current UTC timestamp as text."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def extract_metadata(event: dict[str, Any]) -> dict[str, Any]:
    """Extracts provider/model/route reason metadata from corrections."""
    provider = ""
    model = ""
    correction_type = ""
    route_reasons: list[str] = []

    corrections = event.get("corrections") or []

    for correction in corrections:
        if not isinstance(correction, dict):
            continue

        provider = provider or str(correction.get("provider") or "")
        model = model or str(correction.get("model") or "")
        correction_type = correction_type or str(
            correction.get("pipeline_stage") or correction.get("reason") or ""
        )

        raw_reasons = correction.get("route_reasons")
        if isinstance(raw_reasons, list):
            for reason in raw_reasons:
                reason_text = str(reason)
                if reason_text not in route_reasons:
                    route_reasons.append(reason_text)

    if not correction_type:
        correction_type = str(event.get("source") or "")

    return {
        "provider": provider,
        "model": model,
        "correction_type": correction_type,
        "route_reasons": ";".join(route_reasons),
    }


def event_to_export_row(event: dict[str, Any]) -> dict[str, Any]:
    """Converts one trusted database event into an export row."""
    metadata = extract_metadata(event)
    original_text = str(event.get("original_text") or "")
    corrected_text = str(event.get("corrected_text") or "")

    return {
        "id": event.get("id"),
        "created_at": event.get("created_at"),
        "source": event.get("source"),
        "original_text": original_text,
        "corrected_text": corrected_text,
        "review_status": event.get("review_status"),
        "linked_event_id": event.get("linked_event_id"),
        "engine_version": event.get("engine_version"),
        "notes": event.get("notes") or "",
        "review_notes": event.get("review_notes") or "",
        "corrections_json": event.get("corrections_json") or "[]",
        "correction_type": metadata["correction_type"],
        "provider": metadata["provider"],
        "model": metadata["model"],
        "route_reasons": metadata["route_reasons"],
        "original_length": len(original_text),
        "corrected_length": len(corrected_text),
        "changed": bool(event.get("changed")),
    }


def count_by_field(events: list[dict[str, Any]], field_name: str) -> Counter[str]:
    """Counts events by a given event dictionary field."""
    counter: Counter[str] = Counter()

    for event in events:
        value = event.get(field_name)
        if value is None or str(value).strip() == "":
            value = "unreviewed" if field_name == "review_status" else "<blank>"
        counter[str(value)] += 1

    return counter


def analyze_exclusions(
    events: list[dict[str, Any]],
    trusted_events: list[dict[str, Any]],
    *,
    include_accepted_ai: bool,
) -> dict[str, Any]:
    """Builds exclusion and data-quality counts for the report."""
    trusted_ids = {event["id"] for event in trusted_events}
    seen_pairs: set[tuple[str, str]] = set()
    possible_duplicate_count = 0
    exact_duplicate_pairs: Counter[tuple[str, str]] = Counter()
    exclusion_counts: Counter[str] = Counter()
    blank_or_invalid_count = 0
    linked_manual_count = 0
    unreviewed_ai_context_count = 0

    for event in events:
        original_text = str(event.get("original_text") or "")
        corrected_text = str(event.get("corrected_text") or "")
        review_status = event.get("review_status") or "unreviewed"
        source = event.get("source") or "<blank>"
        exact_pair = (original_text, corrected_text)

        exact_duplicate_pairs[exact_pair] += 1

        if exact_pair in seen_pairs:
            possible_duplicate_count += 1
        else:
            seen_pairs.add(exact_pair)

        if event.get("linked_event_id") is not None and source == "manual":
            linked_manual_count += 1

        if source == "ai_context" and review_status == "unreviewed":
            unreviewed_ai_context_count += 1

        if not original_text.strip() or not corrected_text.strip():
            blank_or_invalid_count += 1

        if event.get("id") in trusted_ids:
            continue

        reason = classify_primary_exclusion_reason(
            event,
            include_accepted_ai=include_accepted_ai,
        )
        exclusion_counts[reason] += 1

    duplicate_pair_count = sum(
        1 for count in exact_duplicate_pairs.values() if count > 1
    )

    return {
        "exclusion_counts": exclusion_counts,
        "blank_or_invalid_count": blank_or_invalid_count,
        "possible_duplicate_count": possible_duplicate_count,
        "duplicate_pair_count": duplicate_pair_count,
        "linked_manual_count": linked_manual_count,
        "unreviewed_ai_context_count": unreviewed_ai_context_count,
    }


def classify_primary_exclusion_reason(
    event: dict[str, Any],
    *,
    include_accepted_ai: bool,
) -> str:
    """Classifies why a row is not part of the trusted export."""
    original_text = str(event.get("original_text") or "")
    corrected_text = str(event.get("corrected_text") or "")
    review_status = event.get("review_status") or "unreviewed"
    source = event.get("source") or "<blank>"

    if review_status in {"rejected", "test_event", "uncertain", "unreviewed"}:
        return f"review_status:{review_status}"

    if review_status == "manually_corrected":
        return "manual_fix_history_row"

    if review_status != "accepted":
        return f"review_status:{review_status}"

    if source == "ai_context" and not include_accepted_ai:
        return "accepted_ai_excluded_by_setting"

    if source not in {"manual", "dictionary", "ai_context"}:
        return f"unsupported_source:{source}"

    if not original_text.strip() or not corrected_text.strip():
        return "blank_original_or_corrected"

    if original_text == corrected_text:
        return "unchanged_original_equals_corrected"

    return "duplicate_or_policy_filtered"


def write_jsonl(rows: list[dict[str, Any]], output_path: Path) -> None:
    """Writes rows as JSONL."""
    with output_path.open("w", encoding="utf-8", newline="") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    """Writes rows as CSV with stable headers."""
    with output_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=EXPORT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def format_counter(counter: Counter[str]) -> list[str]:
    """Formats a Counter for the plain text report."""
    if not counter:
        return ["- none"]

    return [f"- {key}: {counter[key]}" for key in sorted(counter)]


def build_data_quality_report(
    *,
    database_path: Path,
    export_dir: Path,
    all_events: list[dict[str, Any]],
    trusted_events: list[dict[str, Any]],
    export_rows: list[dict[str, Any]],
    analysis: dict[str, Any],
    include_accepted_ai: bool,
) -> str:
    """Builds the plain-text data quality report."""
    source_counts = count_by_field(all_events, "source")
    review_status_counts = count_by_field(all_events, "review_status")
    trusted_count = len(export_rows)
    excluded_count = len(all_events) - trusted_count

    lines: list[str] = []
    lines.append("Correctr Data Quality Report")
    lines.append("============================")
    lines.append(f"Export timestamp: {utc_now_text()}")
    lines.append(f"Database path: {database_path}")
    lines.append(f"Export directory: {export_dir}")
    lines.append(f"Accepted AI included: {include_accepted_ai}")
    lines.append("")
    lines.append("Summary")
    lines.append("-------")
    lines.append(f"Total correction_events count: {len(all_events)}")
    lines.append(f"Rows exported as trusted: {trusted_count}")
    lines.append(f"Rows excluded from trusted export: {excluded_count}")
    lines.append(f"Blank/invalid row count: {analysis['blank_or_invalid_count']}")
    lines.append(f"Possible duplicate row count: {analysis['possible_duplicate_count']}")
    lines.append(f"Duplicate exact pair count: {analysis['duplicate_pair_count']}")
    lines.append(f"Linked manual correction count: {analysis['linked_manual_count']}")
    lines.append(f"Unreviewed AI/context event count: {analysis['unreviewed_ai_context_count']}")
    lines.append("")
    lines.append("Count by source")
    lines.append("---------------")
    lines.extend(format_counter(source_counts))
    lines.append("")
    lines.append("Count by review_status")
    lines.append("----------------------")
    lines.extend(format_counter(review_status_counts))
    lines.append("")
    lines.append("Exclusion counts by primary reason")
    lines.append("----------------------------------")
    lines.extend(format_counter(analysis["exclusion_counts"]))
    lines.append("")
    lines.append("Export policy")
    lines.append("-------------")
    lines.append("- Export includes reviewed accepted rows from manual, dictionary, and optionally ai_context sources.")
    lines.append("- Export excludes rejected, test_event, uncertain, unreviewed, NULL/blank review_status, and manually_corrected raw history rows.")
    lines.append("- Export excludes blank original/corrected text and unchanged original_text == corrected_text rows.")
    lines.append("- Export deduplicates exact original_text + corrected_text pairs and keeps the first row in oldest-first order.")
    lines.append("- Database rows are never deleted by the export script.")
    lines.append("")
    lines.append("Warnings")
    lines.append("--------")

    warnings: list[str] = []
    if trusted_count < 25:
        warnings.append("Trusted dataset is too small for neural ranker training. Continue collect mode.")
    elif trusted_count < 100:
        warnings.append("Trusted dataset may support personal memory lookup experiments, but is still small for model training.")

    if analysis["unreviewed_ai_context_count"] > 0:
        warnings.append("Unreviewed AI/context events exist and are excluded from trusted export.")

    if not warnings:
        warnings.append("No blocking data-quality warnings detected by v0.1 report logic.")

    lines.extend(f"- {warning}" for warning in warnings)
    lines.append("")
    lines.append("Neural ranker status")
    lines.append("--------------------")
    if trusted_count < 100:
        lines.append("Neural Ranker_v0.1 remains blocked until more trusted examples are collected and reviewed.")
    else:
        lines.append("Trusted dataset size is approaching a more useful range, but ranker readiness still requires Lead Developer review.")
    lines.append("")
    lines.append("Trusted exported IDs")
    lines.append("--------------------")
    if trusted_events:
        lines.append(", ".join(str(event["id"]) for event in trusted_events))
    else:
        lines.append("none")

    return "\n".join(lines) + "\n"


def export_trusted_corrections(
    *,
    database_path: str | Path | None = None,
    export_dir: str | Path | None = None,
    include_accepted_ai: bool = True,
) -> dict[str, Any]:
    """Exports trusted corrections to JSONL, CSV, and a data-quality report."""
    db_path = get_database_path(database_path)
    output_dir = Path(export_dir) if export_dir is not None else DEFAULT_EXPORT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    all_events = fetch_all_correction_events(database_path=db_path, oldest_first=True)
    trusted_events = fetch_trusted_correction_events(
        database_path=db_path,
        include_accepted_ai=include_accepted_ai,
        oldest_first=True,
        exclude_blank=True,
        exclude_unchanged=True,
        deduplicate_exact_pairs=True,
    )
    export_rows = [event_to_export_row(event) for event in trusted_events]
    analysis = analyze_exclusions(
        all_events,
        trusted_events,
        include_accepted_ai=include_accepted_ai,
    )

    jsonl_path = output_dir / JSONL_FILENAME
    csv_path = output_dir / CSV_FILENAME
    report_path = output_dir / REPORT_FILENAME

    write_jsonl(export_rows, jsonl_path)
    write_csv(export_rows, csv_path)
    report_text = build_data_quality_report(
        database_path=db_path,
        export_dir=output_dir,
        all_events=all_events,
        trusted_events=trusted_events,
        export_rows=export_rows,
        analysis=analysis,
        include_accepted_ai=include_accepted_ai,
    )
    report_path.write_text(report_text, encoding="utf-8")

    return {
        "database_path": db_path,
        "export_dir": output_dir,
        "jsonl_path": jsonl_path,
        "csv_path": csv_path,
        "report_path": report_path,
        "trusted_count": len(export_rows),
        "total_count": len(all_events),
        "excluded_count": len(all_events) - len(export_rows),
    }


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Export trusted Correctr correction examples."
    )
    parser.add_argument(
        "--database-path",
        type=Path,
        default=None,
        help="Optional SQLite database path. Defaults to data/corrections.sqlite.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help="Output directory. Defaults to data/exports/.",
    )
    parser.add_argument(
        "--exclude-accepted-ai",
        action="store_true",
        help="Exclude accepted ai_context rows from the export.",
    )

    args = parser.parse_args()

    result = export_trusted_corrections(
        database_path=args.database_path,
        export_dir=args.export_dir,
        include_accepted_ai=not args.exclude_accepted_ai,
    )

    print("Correctr trusted correction export complete")
    print("-------------------------------------------")
    print(f"Database path: {result['database_path']}")
    print(f"Trusted rows exported: {result['trusted_count']}")
    print(f"Rows excluded: {result['excluded_count']}")
    print(f"JSONL: {result['jsonl_path']}")
    print(f"CSV: {result['csv_path']}")
    print(f"Report: {result['report_path']}")


if __name__ == "__main__":
    main()
