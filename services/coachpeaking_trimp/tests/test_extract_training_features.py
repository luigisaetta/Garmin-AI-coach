"""
Author: L. Saetta
Date Modified: 2026-07-15
License: MIT
"""

import csv
import json
from pathlib import Path

import pytest

from services.coachpeaking_trimp.extract_training_features import (
    CSV_COLUMNS,
    extract_training_features,
)


def test_extracts_running_features_and_excludes_treadmill(tmp_path: Path) -> None:
    """Write the approved columns for running activities only."""
    input_root = tmp_path / "exports"
    _write_package(
        input_root,
        "2025-01-01_to_2025-01-31",
        [_activity(123, "running"), _activity(456, "treadmill_running")],
    )
    output_path = tmp_path / "dataset" / "TRIMP_TRAIN.csv"

    row_count = extract_training_features(input_root, output_path)

    with output_path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    assert row_count == 1
    assert tuple(rows[0]) == CSV_COLUMNS
    assert rows[0]["GARMIN_ACTIVITY_ID"] == "123"
    assert rows[0]["ACTIVITY_START_DATE"] == "2025-01-15"
    assert rows[0]["DURATION_SECONDS"] == "3600.0"
    assert rows[0]["HR_TIME_IN_ZONE_5"] == "50.0"
    assert rows[0]["ACTIVITY_TRAINING_LOAD_MISSING"] == "0"
    assert rows[0]["COACHPEAKING_TRIMP"] == ""


def test_marks_missing_optional_features_without_using_zero(tmp_path: Path) -> None:
    """Keep absent optional Garmin feature values distinct from zero."""
    input_root = tmp_path / "exports"
    activity = _activity(123, "running")
    activity.pop("activityTrainingLoad")
    activity.pop("aerobicTrainingEffect")
    activity.pop("anaerobicTrainingEffect")
    _write_package(input_root, "2025-01-01_to_2025-01-31", [activity])

    output_path = tmp_path / "TRIMP_TRAIN.csv"
    extract_training_features(input_root, output_path)

    with output_path.open(encoding="utf-8", newline="") as source:
        row = next(csv.DictReader(source))
    assert row["ACTIVITY_TRAINING_LOAD"] == ""
    assert row["ACTIVITY_TRAINING_LOAD_MISSING"] == "1"
    assert row["AEROBIC_TRAINING_EFFECT_MISSING"] == "1"
    assert row["ANAEROBIC_TRAINING_EFFECT_MISSING"] == "1"


def test_rejects_an_incomplete_export_package(tmp_path: Path) -> None:
    """Refuse packages that were not atomically completed by the exporter."""
    input_root = tmp_path / "exports"
    _write_package(input_root, "2025-01-01_to_2025-01-31", [_activity(123, "running")])
    manifest_path = input_root / "2025-01-01_to_2025-01-31" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "in_progress"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="not completed"):
        extract_training_features(input_root, tmp_path / "TRIMP_TRAIN.csv")


def _write_package(
    input_root: Path, name: str, activities: list[dict[str, object]]
) -> None:
    """Create a minimal completed package fixture."""
    package = input_root / name
    package.mkdir(parents=True)
    (package / "manifest.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "datasets": {"activities": {"file": "activities.ndjson"}},
            }
        ),
        encoding="utf-8",
    )
    records = [{"data": activity} for activity in activities]
    (package / "activities.ndjson").write_text(
        "".join(f"{json.dumps(record)}\n" for record in records), encoding="utf-8"
    )


def _activity(activity_id: int, type_key: str) -> dict[str, object]:
    """Build one minimal Garmin running activity fixture."""
    return {
        "activityId": activity_id,
        "activityType": {"typeKey": type_key},
        "startTimeLocal": "2025-01-15 08:30:00",
        "duration": 3600.0,
        "distance": 10000.0,
        "averageHR": 140.0,
        "maxHR": 170.0,
        "averageSpeed": 2.7778,
        "maxSpeed": 4.0,
        "averageRunningCadenceInStepsPerMinute": 170.0,
        "activityTrainingLoad": 80.0,
        "aerobicTrainingEffect": 3.0,
        "anaerobicTrainingEffect": 1.0,
        "hrTimeInZone_1": 100.0,
        "hrTimeInZone_2": 200.0,
        "hrTimeInZone_3": 300.0,
        "hrTimeInZone_4": 400.0,
        "hrTimeInZone_5": 50.0,
    }
