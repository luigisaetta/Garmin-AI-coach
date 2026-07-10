"""
Author: L. Saetta
Date Modified: 2026-07-10
License: MIT
"""

from __future__ import annotations

# pylint: disable=duplicate-code

from datetime import date

import pytest

from services.assistant_api.training_trends import (
    TrainingTrendsService,
    start_of_iso_week,
    summarize_training_trends,
)


class FakeTrainingClient:  # pylint: disable=too-few-public-methods
    """Fake training client returning deterministic activities."""

    def __init__(self, activities):
        self.activities = activities
        self.calls = []

    async def list_activities(
        self,
        *,
        user_id: int,
        begin_date: str,
        end_date: str,
        activity_type: str | None = None,
    ):
        """Record the user-scoped query and return configured activities."""
        self.calls.append(
            {
                "user_id": user_id,
                "begin_date": begin_date,
                "end_date": end_date,
                "activity_type": activity_type,
            }
        )
        return self.activities


def test_summarize_training_trends_builds_weekly_load_series() -> None:
    """Verify weekly trend aggregation and derived load metrics."""
    summary = summarize_training_trends(
        begin_date=date(2026, 6, 1),
        end_date=date(2026, 6, 28),
        weeks=4,
        activities=[
            {
                "activityType": {"typeKey": "running"},
                "startTimeLocal": "2026-06-02T07:00:00",
                "duration": 3600,
                "activityTrainingLoad": 100,
            },
            {
                "activityType": {"typeKey": "road_biking"},
                "startTimeLocal": "2026-06-10T07:00:00",
                "duration": 7200,
                "activityTrainingLoad": 200,
            },
            {
                "activityType": {"typeKey": "lap_swimming"},
                "startTimeLocal": "2026-06-17T07:00:00",
                "duration": 1800,
                "activityTrainingLoad": 50,
            },
            {
                "activityType": {"typeKey": "running"},
                "startTimeLocal": "2026-06-24T07:00:00",
                "duration": 5400,
                "activityTrainingLoad": 150,
            },
            {
                "activityType": {"typeKey": "walking"},
                "startTimeLocal": "2026-06-24T07:00:00",
                "duration": 9999,
                "activityTrainingLoad": 999,
            },
        ],
    )

    assert summary.begin_date == date(2026, 6, 1)
    assert summary.end_date == date(2026, 6, 28)
    assert [week.total_training_load for week in summary.weeks] == [
        100.0,
        200.0,
        50.0,
        150.0,
    ]
    assert [week.rolling_4_week_average_load for week in summary.weeks] == [
        100.0,
        150.0,
        116.7,
        125.0,
    ]
    assert summary.weeks[1].previous_week_delta_percent == 100.0
    assert summary.weeks[2].previous_week_delta_percent == -75.0
    assert summary.weeks[3].acute_chronic_load_ratio == 1.29
    assert summary.weeks[3].sports[0].hours == 1.5
    assert summary.weeks[3].sports[0].training_load == 150.0


def test_summarize_training_trends_includes_empty_weeks() -> None:
    """Verify weeks without matching activities are returned as zeros."""
    summary = summarize_training_trends(
        begin_date=date(2026, 6, 1),
        end_date=date(2026, 6, 28),
        weeks=4,
        activities=[],
    )

    assert len(summary.weeks) == 4
    assert all(week.total_training_load == 0 for week in summary.weeks)
    assert all(week.activity_count == 0 for week in summary.weeks)
    assert summary.weeks[0].label == "2026-W23"


@pytest.mark.anyio
async def test_training_trends_service_reads_requested_weeks_for_user() -> None:
    """Verify service queries the user-scoped client with ISO week boundaries."""
    client = FakeTrainingClient([])

    summary = await TrainingTrendsService().summarize(
        training_client=client,
        user_id=42,
        weeks=4,
        end_date=date(2026, 7, 10),
    )

    assert client.calls == [
        {
            "user_id": 42,
            "begin_date": "2026-06-15",
            "end_date": "2026-07-12",
            "activity_type": None,
        }
    ]
    assert summary.begin_date == date(2026, 6, 15)
    assert summary.end_date == date(2026, 7, 12)


def test_training_trends_rejects_invalid_week_count() -> None:
    """Verify trend week requests are bounded."""
    with pytest.raises(ValueError, match="weeks"):
        summarize_training_trends(
            begin_date=date(2026, 6, 1),
            end_date=date(2026, 6, 7),
            weeks=3,
            activities=[],
        )


def test_start_of_iso_week_returns_monday() -> None:
    """Verify ISO week alignment helper."""
    assert start_of_iso_week(date(2026, 7, 10)) == date(2026, 7, 6)
