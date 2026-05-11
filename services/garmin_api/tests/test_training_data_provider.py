"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from services.garmin_api.training_data_provider import TrainingDataProvider


class FakeGarminClient:
    """Fake Garmin Connect client used to test provider behavior."""

    def __init__(self) -> None:
        """Initialize the fake client with no recorded calls."""
        self.calls: list[dict[str, str]] = []

    def login(self) -> None:
        """Simulate Garmin Connect login without doing network I/O."""

    def get_activities_by_date(
        self, startdate: str, enddate: str, activitytype: str = ""
    ) -> list[dict[str, Any]]:
        """Record the date-range request and return a predictable activity."""
        self.calls.append(
            {
                "startdate": startdate,
                "enddate": enddate,
                "activitytype": activitytype,
            }
        )
        return [{"activityId": 123, "activityName": "Morning Run"}]


def test_list_activities_returns_all_activity_types_by_default() -> None:
    """Verify that an omitted activity type maps to Garmin's all-activity query."""
    client = FakeGarminClient()
    provider = TrainingDataProvider(client=client)

    activities = provider.list_activities("2026-05-01", "2026-05-10")

    assert activities == [{"activityId": 123, "activityName": "Morning Run"}]
    assert client.calls == [
        {
            "startdate": "2026-05-01",
            "enddate": "2026-05-10",
            "activitytype": "",
        }
    ]


def test_list_activities_passes_activity_type_filter() -> None:
    """Verify that a supplied activity type is forwarded to Garmin Connect."""
    client = FakeGarminClient()
    provider = TrainingDataProvider(client=client)

    provider.list_activities(
        begin_date=date(2026, 5, 1),
        end_date=date(2026, 5, 10),
        activity_type="running",
    )

    assert client.calls == [
        {
            "startdate": "2026-05-01",
            "enddate": "2026-05-10",
            "activitytype": "running",
        }
    ]


def test_list_activities_rejects_invalid_date_range() -> None:
    """Verify that the provider rejects ranges with a start after the end."""
    provider = TrainingDataProvider(client=FakeGarminClient())

    with pytest.raises(ValueError, match="begin_date"):
        provider.list_activities("2026-05-10", "2026-05-01")


def test_list_activities_rejects_invalid_date_format() -> None:
    """Verify that invalid date strings produce a clear validation error."""
    provider = TrainingDataProvider(client=FakeGarminClient())

    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        provider.list_activities("05/01/2026", "2026-05-10")
