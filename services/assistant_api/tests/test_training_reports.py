"""
Author: L. Saetta
Date Modified: 2026-08-28
License: MIT
"""

from __future__ import annotations

import asyncio
from datetime import date

import pytest

from services.assistant_api.training_reports import (
    TrainingReportService,
    last_365_day_range,
    summarize_report_activities,
)


def test_report_summary_separates_sports_and_intensity() -> None:
    """Report categorisation keeps the four requested sports distinct."""
    summaries, uncategorised = summarize_report_activities(
        [
            _activity("running", aerobic=1.5, duration=1800, distance=5000),
            _activity("cycling", aerobic=2.5, duration=3600, distance=25000),
            _activity("lap_swimming", aerobic=3.0, anaerobic=2.1, duration=1200),
            _activity("open_water_swimming", aerobic=None, duration=1800),
            _activity("walking", aerobic=1.0),
        ]
    )

    by_sport = {summary.sport: summary for summary in summaries}
    assert by_sport["running"].low_count == 1
    assert by_sport["cycling"].medium_count == 1
    assert by_sport["pool_swimming"].high_count == 1
    assert by_sport["open_water_swimming"].unclassified_count == 1
    assert by_sport["running"].distance_metres == 5000
    assert uncategorised == 1


def test_custom_report_rejects_range_longer_than_366_days() -> None:
    """The report service enforces the bounded custom interval."""
    with pytest.raises(ValueError, match="366"):
        asyncio.run(
            TrainingReportService().create(
                training_client=UnusedTrainingClient(),
                user_id=7,
                begin_date=date(2025, 1, 1),
                end_date=date(2026, 1, 2),
                report_type="custom",
            )
        )


def test_report_marks_partial_months_and_compares_complete_months() -> None:
    """Trend text avoids comparing partial calendar months as complete months."""
    report = asyncio.run(
        TrainingReportService().create(
            training_client=StaticTrainingClient(
                [
                    _activity(
                        "running", start="2026-02-02", duration=3600, aerobic=2.0
                    ),
                    _activity(
                        "running", start="2026-03-02", duration=7200, aerobic=4.0
                    ),
                ]
            ),
            user_id=7,
            begin_date=date(2026, 1, 15),
            end_date=date(2026, 4, 10),
            report_type="custom",
        ),
    )

    assert "| Sport | Attività | Ore |" in report.report
    assert "| 2026-01 | Mese parziale | — | — | 0/0/0 |" in report.report
    assert "| 2026-02 | Primo mese completo | — | — | 0/1/0 |" in report.report
    assert "| 2026-03 | vs 2026-02 | +100% | 0% | 0/0/1 |" in report.report
    assert "| 2026-04 | Mese parziale | — | — | 0/0/0 |" in report.report


def test_last_365_day_range_is_inclusive() -> None:
    """Last-365 report range contains exactly 365 calendar days."""
    begin_date, end_date = last_365_day_range(date(2026, 8, 28))

    assert begin_date == date(2025, 8, 29)
    assert end_date == date(2026, 8, 28)
    assert (end_date - begin_date).days + 1 == 365


class StaticTrainingClient:  # pylint: disable=too-few-public-methods
    """Return fixed activity summaries to the report service."""

    def __init__(self, activities: list[dict[str, object]]) -> None:
        """Configure activity summaries."""
        self._activities = activities

    async def list_activities(self, **kwargs) -> list[dict[str, object]]:
        """Return the configured activities."""
        _ = kwargs
        return self._activities


class UnusedTrainingClient:  # pylint: disable=too-few-public-methods
    """Fail if validation accidentally calls Garmin data access."""

    async def list_activities(self, **kwargs) -> list[dict[str, object]]:
        """Reject unexpected Garmin reads."""
        _ = kwargs
        raise AssertionError("Training client must not be called")


# pylint: disable=too-many-arguments
def _activity(
    type_key: str,
    *,
    start: str = "2026-03-01",
    duration: float = 0,
    distance: float | None = None,
    aerobic: float | None = None,
    anaerobic: float | None = None,
) -> dict[str, object]:
    """Build one minimal Garmin activity summary fixture."""
    activity: dict[str, object] = {
        "activityType": {"typeKey": type_key},
        "startTimeLocal": f"{start} 08:00:00",
        "duration": duration,
        "aerobicTrainingEffect": aerobic,
        "anaerobicTrainingEffect": anaerobic,
    }
    if distance is not None:
        activity["distance"] = distance
    return activity
