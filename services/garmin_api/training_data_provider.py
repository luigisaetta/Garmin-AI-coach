"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

from datetime import date
from typing import Any, Protocol

EXCLUDED_ACTIVITY_KEYS = frozenset(
    {
        "ownerDisplayName",
        "ownerFullName",
        "ownerId",
        "ownerProfileImageUrlLarge",
        "ownerProfileImageUrlMedium",
        "ownerProfileImageUrlSmall",
        "userRoles",
    }
)


class GarminConnectClient(Protocol):
    """Protocol describing the Garmin Connect client methods used here."""

    def login(self) -> None:
        """Authenticate the client session with Garmin Connect."""

    def get_activities_by_date(
        self, startdate: str, enddate: str, activitytype: str = ""
    ) -> list[dict[str, Any]]:
        """Return Garmin Connect activities for a date range."""


class TrainingDataProvider:  # pylint: disable=too-few-public-methods
    """Read training data from Garmin Connect through a narrow provider API.

    The provider is the only local object that should call the third-party
    `garminconnect` package directly. Backend HTTP handlers should depend on
    this class or on the same method contract, while the assistant backend must
    call the Garmin data API over HTTP instead of importing this provider.

    A preconfigured client can be injected for tests. When no client is passed,
    the provider creates and authenticates a `garminconnect.Garmin` client using
    the supplied Garmin Connect username and password.
    """

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        client: GarminConnectClient | None = None,
    ) -> None:
        """Create a training data provider.

        Args:
            username: Garmin Connect username or email address. Required when
                `client` is not supplied.
            password: Garmin Connect password. Required when `client` is not
                supplied.
            client: Optional Garmin-compatible client, primarily intended for
                tests and local fakes. The object must expose `login` and
                `get_activities_by_date`.

        Raises:
            ValueError: If username or password is missing when no client is
                injected.
            ImportError: If the `garminconnect` package is not installed and a
                real client must be created.
        """
        if client is not None:
            self._client = client
            return

        if not username or not password:
            raise ValueError("Garmin username and password are required.")

        self._client = self._build_client(username=username, password=password)
        self._client.login()

    def list_activities(
        self,
        begin_date: date | str,
        end_date: date | str,
        activity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return activities recorded in the requested date range.

        Args:
            begin_date: Inclusive start date for the query. Accepts either a
                `datetime.date` instance or an ISO `YYYY-MM-DD` string.
            end_date: Inclusive end date for the query. Accepts either a
                `datetime.date` instance or an ISO `YYYY-MM-DD` string.
            activity_type: Optional Garmin activity type filter, such as
                `running`, `cycling`, `swimming`, `walking`, or `hiking`. When
                omitted or blank, all activity types are returned.

        Returns:
            A list of activity dictionaries as returned by Garmin Connect. A
            later normalization layer should convert these dictionaries into
            stable API response models before exposing them over HTTP.

        Raises:
            ValueError: If either date cannot be parsed as an ISO date or if
                `begin_date` is after `end_date`.
        """
        start = self._coerce_date(begin_date, field_name="begin_date")
        end = self._coerce_date(end_date, field_name="end_date")

        if start > end:
            raise ValueError("begin_date must be earlier than or equal to end_date.")

        garmin_activity_type = activity_type.strip() if activity_type else ""
        activities = self._client.get_activities_by_date(
            startdate=start.isoformat(),
            enddate=end.isoformat(),
            activitytype=garmin_activity_type,
        )
        return [self._sanitize_activity(activity) for activity in activities]

    @staticmethod
    def _build_client(username: str, password: str) -> GarminConnectClient:
        """Create a Garmin Connect client from the third-party library.

        The import is intentionally lazy so unit tests can exercise the provider
        with fake clients without requiring the real `garminconnect` dependency
        or live Garmin credentials.

        Args:
            username: Garmin Connect username or email address.
            password: Garmin Connect password.

        Returns:
            An authenticated-capable Garmin Connect client instance.
        """
        from garminconnect import Garmin  # pylint: disable=import-outside-toplevel

        return Garmin(username, password)

    @staticmethod
    def _coerce_date(value: date | str, field_name: str) -> date:
        """Convert a supported date input into a `datetime.date`.

        Args:
            value: Date value supplied by callers. Strings must use ISO
                `YYYY-MM-DD` format.
            field_name: Human-readable field name used in validation errors.

        Returns:
            A `datetime.date` value.

        Raises:
            ValueError: If the value is not a date instance or a valid ISO date
                string.
        """
        if isinstance(value, date):
            return value

        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(
                    f"{field_name} must use ISO date format YYYY-MM-DD."
                ) from exc

        raise ValueError(f"{field_name} must be a date or ISO date string.")

    @classmethod
    def _sanitize_activity(cls, value: Any) -> Any:
        """Remove noisy or sensitive fields from Garmin activity payloads.

        Garmin activity objects may include large account metadata fields that
        are not useful for coaching analysis and would waste LLM context tokens.
        This sanitizer removes those fields recursively while preserving the
        rest of the payload structure for downstream normalization.

        Args:
            value: Garmin activity payload or nested value returned by the
                Garmin Connect client.

        Returns:
            A sanitized copy of the supplied value. Dictionaries and lists are
            copied recursively; scalar values are returned unchanged.
        """
        if isinstance(value, dict):
            return {
                key: cls._sanitize_activity(nested_value)
                for key, nested_value in value.items()
                if key not in EXCLUDED_ACTIVITY_KEYS
            }

        if isinstance(value, list):
            return [cls._sanitize_activity(item) for item in value]

        return value
