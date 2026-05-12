"""
Author: L. Saetta
Date Modified: 2026-05-12
License: MIT
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from services.garmin_api.training_data_provider import TrainingDataProvider


@pytest.fixture(autouse=True)
def disable_dotenv_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent local `.env` files from influencing provider unit tests."""
    monkeypatch.setattr(
        "services.garmin_api.training_data_provider.load_dotenv", lambda: False
    )


class FakeGarminClient:
    """Fake Garmin Connect client used to test provider behavior."""

    def __init__(
        self,
        activities: list[dict[str, Any]] | None = None,
        heart_rates_by_date: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Initialize the fake client with optional activity payloads."""
        self.calls: list[dict[str, str]] = []
        self.heart_rate_calls: list[str] = []
        self.login_tokenstores: list[str | None] = []
        self.activities = activities or [
            {"activityId": 123, "activityName": "Morning Run"}
        ]
        self.heart_rates_by_date = heart_rates_by_date or {}

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

    def get_heart_rates(self, cdate: str) -> dict[str, Any]:
        """Record the daily heart-rate request and return a payload."""
        self.heart_rate_calls.append(cdate)
        return self.heart_rates_by_date.get(
            cdate,
            {
                "calendarDate": cdate,
                "restingHeartRate": 48,
                "heartRateValues": [[0, 52], [60, 58]],
            },
        )


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


def test_get_heart_rates_returns_daily_payloads_for_inclusive_range() -> None:
    """Verify that heart-rate range queries call Garmin once per day."""
    client = FakeGarminClient(
        heart_rates_by_date={
            "2026-05-01": {"calendarDate": "2026-05-01", "restingHeartRate": 48},
            "2026-05-02": {"calendarDate": "2026-05-02", "restingHeartRate": 47},
        }
    )
    provider = TrainingDataProvider(client=client)

    heart_rates = provider.get_heart_rates("2026-05-01", "2026-05-02")

    assert client.heart_rate_calls == ["2026-05-01", "2026-05-02"]
    assert heart_rates == {
        "2026-05-01": {"calendarDate": "2026-05-01", "restingHeartRate": 48},
        "2026-05-02": {"calendarDate": "2026-05-02", "restingHeartRate": 47},
    }


def test_get_heart_rates_rejects_invalid_date_range() -> None:
    """Verify that heart-rate queries reject ranges with a start after the end."""
    provider = TrainingDataProvider(client=FakeGarminClient())

    with pytest.raises(ValueError, match="begin_date"):
        provider.get_heart_rates("2026-05-10", "2026-05-01")


def test_get_heart_rates_masks_pii_fields_from_daily_payloads() -> None:
    """Verify that raw heart-rate payload shape still receives PII masking."""
    client = FakeGarminClient(
        heart_rates_by_date={
            "2026-05-01": {
                "calendarDate": "2026-05-01",
                "restingHeartRate": 48,
                "ownerDisplayName": "luigisaetta",
            }
        }
    )
    provider = TrainingDataProvider(client=client)

    heart_rates = provider.get_heart_rates("2026-05-01", "2026-05-01")

    assert heart_rates == {
        "2026-05-01": {
            "calendarDate": "2026-05-01",
            "restingHeartRate": 48,
            "ownerDisplayName": "*****",
        }
    }


def test_list_activities_masks_pii_fields_from_activity_payloads() -> None:
    """Verify that potential PII in Garmin payloads is masked recursively."""
    raw_activity = {
        "activityId": 123,
        "activityName": "Morning Run",
        "beginLatitude": 45.123,
        "beginLongitude": 9.456,
        "locationName": "Home",
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
            "ownerProfileImageUrlLarge": "https://example.test/large.png",
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
            "beginLatitude": "*****",
            "beginLongitude": "*****",
            "locationName": "*****",
            "ownerDisplayName": "*****",
            "ownerFullName": "*****",
            "ownerId": "*****",
            "ownerProfileImageUrlLarge": "*****",
            "ownerProfileImageUrlMedium": "*****",
            "ownerProfileImageUrlSmall": "*****",
            "userRoles": "*****",
            "metadata": {
                "device": "Garmin",
                "ownerFullName": "*****",
                "ownerProfileImageUrlLarge": "*****",
                "userRoles": "*****",
            },
            "laps": [{"lapIndex": 1, "ownerId": "*****", "userRoles": "*****"}],
        }
    ]
    assert raw_activity["userRoles"] == ["ROLE_CONNECTUSER", "SCOPE_CONNECT_READ"]
    assert raw_activity["ownerFullName"] == "Luigi Saetta"


def test_list_activities_can_return_unredacted_payloads_when_disabled() -> None:
    """Verify that PII redaction can be disabled for local debugging."""
    raw_activity = {
        "activityId": 123,
        "ownerFullName": "Luigi Saetta",
        "beginLatitude": 45.123,
    }
    provider = TrainingDataProvider(
        client=FakeGarminClient([raw_activity]),
        redact_pii=False,
    )

    activities = provider.list_activities("2026-05-01", "2026-05-10")

    assert activities == [raw_activity]


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
