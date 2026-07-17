"""
Author: L. Saetta
Date Modified: 2026-07-17
License: MIT
"""

import csv
from pathlib import Path

from services.coachpeaking_trimp.prepare_training_dataset import (
    COACHPEAKING_FILENAME,
    GARMIN_FILENAME,
    OUTPUT_FILENAME,
    prepare_training_dataset,
)


def test_preparation_preserves_duplicate_garmin_dates_without_labels(
    tmp_path: Path,
) -> None:
    """Keep every Garmin row while leaving ambiguous dates for manual review."""
    _write_csv(
        tmp_path / GARMIN_FILENAME,
        ["GARMIN_ACTIVITY_ID", "ACTIVITY_START_DATE", "COACHPEAKING_TRIMP"],
        [["1", "2025-01-01", ""], ["2", "2025-01-02", ""], ["3", "2025-01-02", ""]],
    )
    _write_csv(
        tmp_path / COACHPEAKING_FILENAME,
        ["activity_type", "date", "trimp"],
        [["running", "2025-01-01", "42"], ["running", "2025-01-03", "50"]],
    )

    report = prepare_training_dataset(tmp_path)

    with (tmp_path / OUTPUT_FILENAME).open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    assert rows == [
        {
            "GARMIN_ACTIVITY_ID": "1",
            "ACTIVITY_START_DATE": "2025-01-01",
            "COACHPEAKING_TRIMP": "42",
        },
        {
            "GARMIN_ACTIVITY_ID": "2",
            "ACTIVITY_START_DATE": "2025-01-02",
            "COACHPEAKING_TRIMP": "",
        },
        {
            "GARMIN_ACTIVITY_ID": "3",
            "ACTIVITY_START_DATE": "2025-01-02",
            "COACHPEAKING_TRIMP": "",
        },
    ]
    assert report["automatic_labels"] == 1
    assert report["manual_review_garmin_rows"] == 2
    assert report["unmatched_coachpeaking_rows"] == 1
    assert report["garmin_duplicate_dates"] == [{"date": "2025-01-02", "row_count": 2}]
    assert report["unmatched_coachpeaking_dates"] == ["2025-01-03"]


def _write_csv(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    """Write a compact CSV fixture."""
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(headers)
        writer.writerows(rows)
