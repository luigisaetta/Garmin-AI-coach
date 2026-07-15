"""
Author: L. Saetta
Date Modified: 2026-07-15
License: MIT
"""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

FEATURE_COLUMNS = (
    "DURATION_SECONDS",
    "DISTANCE_METERS",
    "AVERAGE_HEART_RATE",
    "MAX_HEART_RATE",
    "AVERAGE_SPEED_MPS",
    "MAX_SPEED_MPS",
    "AVERAGE_RUNNING_CADENCE_SPM",
    "ACTIVITY_TRAINING_LOAD",
    "AEROBIC_TRAINING_EFFECT",
    "ANAEROBIC_TRAINING_EFFECT",
    "HR_TIME_IN_ZONE_1",
    "HR_TIME_IN_ZONE_2",
    "HR_TIME_IN_ZONE_3",
    "HR_TIME_IN_ZONE_4",
    "HR_TIME_IN_ZONE_5",
)
OPTIONAL_FEATURES = (
    ("ACTIVITY_TRAINING_LOAD", "activityTrainingLoad"),
    ("AEROBIC_TRAINING_EFFECT", "aerobicTrainingEffect"),
    ("ANAEROBIC_TRAINING_EFFECT", "anaerobicTrainingEffect"),
)
CSV_COLUMNS = (
    "GARMIN_ACTIVITY_ID",
    "ACTIVITY_START_DATE",
    *FEATURE_COLUMNS,
    *(f"{column}_MISSING" for column, _ in OPTIONAL_FEATURES),
    "COACHPEAKING_TRIMP",
)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for 2025 training CSV extraction."""
    parser = argparse.ArgumentParser(
        description="Create a CoachPeaking TRIMP training-label CSV template."
    )
    parser.add_argument(
        "--input-root",
        required=True,
        type=Path,
        help="Directory containing completed monthly Garmin export packages.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="CSV template path to create.",
    )
    return parser


def extract_training_features(input_root: Path, output_path: Path) -> int:
    """Write one row per running activity and return the number of rows written."""
    rows = list(_running_feature_rows(input_root))
    rows.sort(key=lambda row: int(row["GARMIN_ACTIVITY_ID"]))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def _running_feature_rows(input_root: Path) -> Iterable[dict[str, Any]]:
    """Yield one feature row for every non-duplicate Garmin running activity."""
    manifests = sorted(input_root.glob("*/manifest.json"))
    if not manifests:
        raise ValueError(f"No export manifests found under: {input_root}")

    seen_activity_ids: set[str] = set()
    for manifest_path in manifests:
        package = _load_completed_package(manifest_path)
        activities_path = (
            manifest_path.parent / package["datasets"]["activities"]["file"]
        )
        yield from _rows_from_activities(activities_path, seen_activity_ids)


def _load_completed_package(manifest_path: Path) -> dict[str, Any]:
    """Load and minimally validate the manifest needed for feature extraction."""
    with manifest_path.open(encoding="utf-8") as source:
        manifest = json.load(source)
    if manifest.get("status") != "completed":
        raise ValueError(f"Export package is not completed: {manifest_path.parent}")
    activities = manifest.get("datasets", {}).get("activities")
    if not isinstance(activities, dict) or not isinstance(activities.get("file"), str):
        raise ValueError(
            f"Export package has no activities dataset: {manifest_path.parent}"
        )
    return manifest


def _rows_from_activities(
    activities_path: Path, seen_activity_ids: set[str]
) -> Iterable[dict[str, Any]]:
    """Yield feature rows from one activities NDJSON file."""
    with activities_path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            record = json.loads(line)
            activity = record.get("data")
            if not isinstance(activity, dict) or not _is_running(activity):
                continue
            row = _feature_row(activity, activities_path, line_number)
            activity_id = row["GARMIN_ACTIVITY_ID"]
            if activity_id in seen_activity_ids:
                raise ValueError(f"Duplicate Garmin activity ID: {activity_id}")
            seen_activity_ids.add(activity_id)
            yield row


def _is_running(activity: dict[str, Any]) -> bool:
    """Return whether the Garmin activity is outdoor or generic running only."""
    activity_type = activity.get("activityType")
    return isinstance(activity_type, dict) and activity_type.get("typeKey") == "running"


def _feature_row(
    activity: dict[str, Any], activities_path: Path, line_number: int
) -> dict[str, Any]:
    """Map one running activity to the explicitly allowed CSV columns."""
    activity_id = activity.get("activityId")
    if activity_id is None:
        raise ValueError(f"Missing activity ID in {activities_path} line {line_number}")

    row: dict[str, Any] = {
        "GARMIN_ACTIVITY_ID": str(activity_id),
        "ACTIVITY_START_DATE": _activity_start_date(
            activity, activities_path, line_number
        ),
        "DURATION_SECONDS": _required_number(
            activity, "duration", activities_path, line_number
        ),
        "DISTANCE_METERS": _required_number(
            activity, "distance", activities_path, line_number
        ),
        "AVERAGE_HEART_RATE": activity.get("averageHR"),
        "MAX_HEART_RATE": activity.get("maxHR"),
        "AVERAGE_SPEED_MPS": activity.get("averageSpeed"),
        "MAX_SPEED_MPS": activity.get("maxSpeed"),
        "AVERAGE_RUNNING_CADENCE_SPM": activity.get(
            "averageRunningCadenceInStepsPerMinute"
        ),
        "HR_TIME_IN_ZONE_1": activity.get("hrTimeInZone_1"),
        "HR_TIME_IN_ZONE_2": activity.get("hrTimeInZone_2"),
        "HR_TIME_IN_ZONE_3": activity.get("hrTimeInZone_3"),
        "HR_TIME_IN_ZONE_4": activity.get("hrTimeInZone_4"),
        "HR_TIME_IN_ZONE_5": activity.get("hrTimeInZone_5"),
        "COACHPEAKING_TRIMP": "",
    }
    for column, source_key in OPTIONAL_FEATURES:
        value = activity.get(source_key)
        row[column] = value
        row[f"{column}_MISSING"] = int(value is None)
    return row


def _activity_start_date(
    activity: dict[str, Any], activities_path: Path, line_number: int
) -> str:
    """Return the local activity date used to review manual label matching."""
    value = activity.get("startTimeLocal")
    if not isinstance(value, str):
        raise ValueError(
            f"Missing local start time in {activities_path} line {line_number}"
        )
    try:
        return date.fromisoformat(value[:10]).isoformat()
    except ValueError as exc:
        raise ValueError(
            f"Invalid local start time in {activities_path} line {line_number}"
        ) from exc


def _required_number(
    activity: dict[str, Any], key: str, activities_path: Path, line_number: int
) -> int | float:
    """Return one positive required numeric field or raise a clear error."""
    value = activity.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(
            f"Invalid {key} in {activities_path} line {line_number}: expected a positive number"
        )
    return value


def main() -> None:
    """Run extraction from the command line and print only the row count."""
    arguments = build_parser().parse_args()
    row_count = extract_training_features(arguments.input_root, arguments.output)
    print(
        f"Training feature template created: {arguments.output} ({row_count} activities)"
    )


if __name__ == "__main__":
    main()
