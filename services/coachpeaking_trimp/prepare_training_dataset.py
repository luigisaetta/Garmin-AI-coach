"""
Author: L. Saetta
Date Modified: 2026-07-17
License: MIT

Create a date-matched local TRIMP training dataset with an audit report.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

GARMIN_FILENAME = "TRIMP_TRAIN_GARMIN.csv"
COACHPEAKING_FILENAME = "COACHPEAKING_RUNNING_2025.csv"
OUTPUT_FILENAME = "TRIMP_TRAIN_REVIEW.csv"
REPORT_FILENAME = "MATCH_REPORT.json"
DEFAULT_WORKING_DIRECTORY = Path("data/coachpeaking-trimp-dataset/2025/working")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for local data preparation."""
    parser = argparse.ArgumentParser(description="Prepare the 2025 TRIMP dataset.")
    parser.add_argument(
        "--working-directory", type=Path, default=DEFAULT_WORKING_DIRECTORY
    )
    return parser


def prepare_training_dataset(working_directory: Path) -> dict[str, Any]:
    """Create a Garmin-complete review CSV with safe exact-date labels."""
    garmin_path = working_directory / GARMIN_FILENAME
    coachpeaking_path = working_directory / COACHPEAKING_FILENAME
    garmin_rows, fieldnames = _read_garmin_rows(garmin_path)
    coachpeaking_rows = _read_coachpeaking_rows(coachpeaking_path)
    garmin_by_date = _group_by_date(garmin_rows, "ACTIVITY_START_DATE")
    coachpeaking_by_date = _group_by_date(coachpeaking_rows, "date")
    report = _build_report(garmin_by_date, coachpeaking_by_date)
    review_rows = _review_rows(garmin_rows, coachpeaking_by_date, garmin_by_date)
    _write_csv(working_directory / OUTPUT_FILENAME, fieldnames, review_rows)
    (working_directory / REPORT_FILENAME).write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _read_garmin_rows(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    """Read the feature source and validate its required columns."""
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames or []
        required = {"GARMIN_ACTIVITY_ID", "ACTIVITY_START_DATE", "COACHPEAKING_TRIMP"}
        if not required.issubset(fieldnames):
            raise ValueError(f"Invalid Garmin feature source: {path}")
        return list(reader), fieldnames


def _read_coachpeaking_rows(path: Path) -> list[dict[str, str]]:
    """Read and validate the compact CoachPeaking review source."""
    with path.open(encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["activity_type", "date", "trimp"]:
            raise ValueError(f"Invalid CoachPeaking source: {path}")
        rows = list(reader)
    for row in rows:
        if row["activity_type"] != "running" or float(row["trimp"]) < 0:
            raise ValueError(f"Invalid CoachPeaking label on {row['date']}")
    return rows


def _group_by_date(
    rows: list[dict[str, str]], date_column: str
) -> dict[str, list[dict[str, str]]]:
    """Group source rows by their ISO activity date."""
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row[date_column]].append(row)
    return dict(grouped)


def _build_report(
    garmin: dict[str, list[dict[str, str]]],
    coachpeaking: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    """Build an audit report for manual review; no Garmin row is discarded."""
    duplicate_garmin = _duplicate_dates(garmin)
    duplicate_coachpeaking = _duplicate_dates(coachpeaking)
    matched_dates = sorted(
        day
        for day in garmin.keys() & coachpeaking.keys()
        if len(garmin[day]) == 1 and len(coachpeaking[day]) == 1
    )
    return {
        "input_garmin_rows": sum(len(rows) for rows in garmin.values()),
        "input_coachpeaking_rows": sum(len(rows) for rows in coachpeaking.values()),
        "automatic_labels": len(matched_dates),
        "manual_review_garmin_rows": sum(len(rows) for rows in garmin.values())
        - len(matched_dates),
        "unmatched_coachpeaking_rows": sum(len(rows) for rows in coachpeaking.values())
        - len(matched_dates),
        "garmin_duplicate_dates": duplicate_garmin,
        "coachpeaking_duplicate_dates": duplicate_coachpeaking,
        "unmatched_garmin_dates": sorted(set(garmin) - set(coachpeaking)),
        "unmatched_coachpeaking_dates": sorted(set(coachpeaking) - set(garmin)),
    }


def _duplicate_dates(grouped: dict[str, list[dict[str, str]]]) -> list[dict[str, Any]]:
    """Report every date with more than one source row."""
    return [
        {"date": day, "row_count": len(rows)}
        for day, rows in sorted(grouped.items())
        if len(rows) > 1
    ]


def _review_rows(
    garmin_rows: list[dict[str, str]],
    coachpeaking: dict[str, list[dict[str, str]]],
    garmin: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    """Preserve every Garmin row, labelling only unambiguous exact-date matches."""
    review_rows = []
    for source_row in sorted(garmin_rows, key=lambda row: row["ACTIVITY_START_DATE"]):
        row = dict(source_row)
        day = row["ACTIVITY_START_DATE"]
        if len(garmin[day]) == 1 and len(coachpeaking.get(day, [])) == 1:
            row["COACHPEAKING_TRIMP"] = coachpeaking[day][0]["trimp"]
        else:
            row["COACHPEAKING_TRIMP"] = ""
        review_rows.append(row)
    return review_rows


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    """Write the labelled feature rows without modifying either source file."""
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    """Run preparation and print the compact match summary."""
    working_directory = build_parser().parse_args().working_directory
    report = prepare_training_dataset(working_directory)
    print(f"Training dataset created: {working_directory / OUTPUT_FILENAME}")
    print(f"Automatic labels: {report['automatic_labels']}")
    print(f"Garmin rows requiring manual review: {report['manual_review_garmin_rows']}")
    print(f"Unmatched CoachPeaking rows: {report['unmatched_coachpeaking_rows']}")


if __name__ == "__main__":
    main()
