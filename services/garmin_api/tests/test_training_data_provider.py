"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from services.garmin_api.training_data_provider import TrainingDataProvider


class FakeGarminClient:
    """Fake Garmin Connect client used to test provider behavior."""

    def __init__(self, activities: list[dict[str, Any]] | None = None) -> None:
        """Initialize the fake client with optional activity payloads."""
        self.calls: list[dict[str, str]] = []
        self.login_tokenstores: list[str | None] = []
        self.activities = activities or [
            {"activityId": 123, "activityName": "Morning Run"}
        ]

    def login(self, tokenstore: str | None = None) -> tuple[str | None, str | None]:
        """Simulate Garmin Connect login without doing network I/O."""
        self.login_tokenstores.append(tokenstore)
        return None, None

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
        return self.activities


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


def test_list_activities_removes_excluded_fields_from_activity_payloads() -> None:
    """Verify that noisy Garmin account metadata is removed recursively."""
    raw_activity = {
        "activityId": 123,
        "activityName": "Morning Run",
        "ownerDisplayName": "luigisaetta",
        "ownerFullName": "Luigi Saetta",
        "ownerId": 1749304,
        "ownerProfileImageUrlLarge": "https://example.test/large.png",
        "ownerProfileImageUrlMedium": "https://example.test/medium.png",
        "ownerProfileImageUrlSmall": "https://example.test/small.png",
        "userRoles": ["ROLE_CONNECTUSER", "SCOPE_CONNECT_READ"],
        "metadata": {
            "device": "Garmin",
            "ownerFullName": "Luigi Saetta",
            "userRoles": ["ROLE_FITNESS_USER"],
        },
        "laps": [
            {
                "lapIndex": 1,
                "ownerId": 1749304,
                "userRoles": ["ROLE_WELLNESS_USER"],
            }
        ],
    }
    provider = TrainingDataProvider(client=FakeGarminClient([raw_activity]))

    activities = provider.list_activities("2026-05-01", "2026-05-10")

    assert activities == [
        {
            "activityId": 123,
            "activityName": "Morning Run",
            "metadata": {"device": "Garmin"},
            "laps": [{"lapIndex": 1}],
        }
    ]
    assert raw_activity["userRoles"] == ["ROLE_CONNECTUSER", "SCOPE_CONNECT_READ"]
    assert raw_activity["ownerFullName"] == "Luigi Saetta"


def test_provider_passes_session_storage_path_to_client_login(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify that the provider configures reusable Garmin session storage."""
    client = FakeGarminClient()
    session_path = tmp_path / "garmin-session"
    monkeypatch.setattr(
        TrainingDataProvider,
        "_build_client",
        staticmethod(lambda username, password: client),
    )

    provider = TrainingDataProvider(
        username="user@example.test",
        password="secret",
        session_storage_path=str(session_path),
    )

    provider.list_activities("2026-05-01", "2026-05-10")

    assert client.login_tokenstores == [str(session_path.resolve())]
    assert session_path.exists()
