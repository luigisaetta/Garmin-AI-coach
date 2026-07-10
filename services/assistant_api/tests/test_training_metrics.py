"""
Author: L. Saetta
Date Modified: 2026-07-10
License: MIT
"""

from __future__ import annotations

from datetime import date

import pytest

from services.assistant_api.training_metrics import (
    TrainingMetricsService,
    summarize_training_metrics,
)


class FakeTrainingClient:  # pylint: disable=too-few-public-methods
    """Fake training client returning deterministic Garmin payloads."""

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
        """Return configured activities and record the query."""
        self.calls.append(
            {
                "user_id": user_id,
                "begin_date": begin_date,
                "end_date": end_date,
                "activity_type": activity_type,
            }
        )
        return self.activities


def test_summarize_training_metrics_groups_sports_and_training_load() -> None:
    """Verify sport grouping, hour totals, and training-load intensity."""
    summary = summarize_training_metrics(
        begin_date=date(2026, 7, 1),
        end_date=date(2026, 7, 31),
        activities=[
            {
                "activityType": {"typeKey": "running"},
                "duration": 3600,
                "activityTrainingLoad": 130.25,
                "moderateIntensityMinutes": 15,
                "vigorousIntensityMinutes": 35,
            },
            {
                "activityType": {"typeKey": "trail_running"},
                "duration": 1800,
                "activityTrainingLoad": "70.25",
            },
            {
                "activityType": {"typeKey": "road_biking"},
                "duration": 7200,
                "moderateIntensityMinutes": 40,
                "vigorousIntensityMinutes": 50,
            },
            {
                "activityType": {"typeKey": "walking"},
                "duration": 9999,
                "activityTrainingLoad": 999,
            },
        ],
    )

    running, cycling, swimming = summary.sports

    assert running.sport == "running"
    assert running.activity_count == 2
    assert running.hours == 1.5
    assert running.total_training_load == 200.5
    assert running.intensity_score == 200.5
    assert running.intensity_source == "training_load"

    assert cycling.sport == "cycling"
    assert cycling.activity_count == 1
    assert cycling.hours == 2.0
    assert cycling.total_training_load is None
    assert cycling.intensity_score == 140
    assert cycling.intensity_source == "intensity_minutes"

    assert swimming.sport == "swimming"
    assert swimming.activity_count == 0
    assert swimming.intensity_score is None
    assert swimming.intensity_source == "none"


@pytest.mark.anyio
async def test_training_metrics_service_reads_all_activities_for_user() -> None:
    """Verify service queries the user-scoped client with the selected range."""
    client = FakeTrainingClient(
        [
            {
                "activityType": "lap_swimming",
                "duration": 2700,
                "activityTrainingLoad": 55,
            }
        ]
    )

    summary = await TrainingMetricsService().summarize(
        training_client=client,
        user_id=42,
        begin_date=date(2026, 7, 1),
        end_date=date(2026, 7, 7),
    )

    assert client.calls == [
        {
            "user_id": 42,
            "begin_date": "2026-07-01",
            "end_date": "2026-07-07",
            "activity_type": None,
        }
    ]
    assert summary.sports[2].sport == "swimming"
    assert summary.sports[2].hours == 0.75


@pytest.mark.anyio
async def test_training_metrics_service_rejects_reversed_dates() -> None:
    """Verify invalid date ranges fail before provider access."""
    client = FakeTrainingClient([])

    with pytest.raises(ValueError, match="begin_date"):
        await TrainingMetricsService().summarize(
            training_client=client,
            user_id=42,
            begin_date=date(2026, 7, 8),
            end_date=date(2026, 7, 1),
        )

    assert not client.calls
