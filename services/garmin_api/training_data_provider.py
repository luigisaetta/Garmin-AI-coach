"""
Author: L. Saetta
Date Modified: 2026-05-13
License: MIT
"""

from __future__ import annotations

from datetime import date, timedelta
import math
import os
from pathlib import Path
from typing import Any, Protocol

from dotenv import load_dotenv

PII_REDACTION_MASK = "*****"
PII_EXACT_KEYS = frozenset(
    {
        "beginLatitude",
        "beginLongitude",
        "endLatitude",
        "endLongitude",
        "ownerDisplayName",
        "ownerFullName",
        "ownerId",
        "ownerProfileImageUrlLarge",
        "ownerProfileImageUrlMedium",
        "ownerProfileImageUrlSmall",
        "userRoles",
    }
)
PII_KEY_FRAGMENTS = (
    "address",
    "displayname",
    "email",
    "fullname",
    "latitude",
    "location",
    "longitude",
    "owner",
    "profileimage",
    "userid",
    "username",
)
BOOLEAN_TRUE_VALUES = frozenset({"1", "true", "yes", "y", "on"})
BOOLEAN_FALSE_VALUES = frozenset({"0", "false", "no", "n", "off"})
MAX_FLOAT_DECIMAL_PLACES = 4


class GarminConnectClient(Protocol):
    """Protocol describing the Garmin Connect client methods used here."""

    def login(self, tokenstore: str | None = None) -> tuple[str | None, str | None]:
        """Authenticate the client session with Garmin Connect."""

    def get_activities_by_date(
        self, startdate: str, enddate: str, activitytype: str = ""
    ) -> list[dict[str, Any]]:
        """Return Garmin Connect activities for a date range."""

    def get_heart_rates(self, cdate: str) -> dict[str, Any]:
        """Return Garmin Connect heart-rate data for one date."""


class TrainingDataProvider:  # pylint: disable=too-few-public-methods
    """Read training data from Garmin Connect through a narrow provider API.

    The provider is the only local object that should call the third-party
    `garminconnect` package directly. Assistant tools should use this class
    through a narrow adapter so Garmin-specific behavior remains isolated from
    model orchestration code.

    A preconfigured client can be injected for tests. When no client is passed,
    the provider creates and authenticates a `garminconnect.Garmin` client using
    the supplied Garmin Connect username and password.
    """

    def __init__(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        username: str | None = None,
        password: str | None = None,
        session_storage_path: str | None = None,
        redact_pii: bool | None = None,
        client: GarminConnectClient | None = None,
    ) -> None:
        """Create a training data provider.

        Args:
            username: Garmin Connect username or email address. Required when
                `client` is not supplied.
            password: Garmin Connect password. Required when `client` is not
                supplied and no reusable session storage is configured.
            session_storage_path: Optional path where Garmin session tokens are
                loaded from and saved to. When present, the provider asks
                `garminconnect` to reuse tokens before performing a credential
                login, reducing repeated login attempts and Garmin rate-limit
                risk.
            redact_pii: Whether potential PII fields should be masked before
                payloads leave the provider. When omitted, `REDACT_PII` is read
                from the environment and defaults to enabled.
            client: Optional Garmin-compatible client, primarily intended for
                tests and local fakes. The object must expose `login` and
                `get_activities_by_date`.

        Raises:
            ValueError: If neither credentials nor a session storage path are
                supplied when no client is injected.
            ImportError: If the `garminconnect` package is not installed and a
                real client must be created.
        """
        self._redact_pii = self._resolve_redact_pii(redact_pii)

        if client is not None:
            self._client = client
            return

        if not session_storage_path and (not username or not password):
            raise ValueError(
                "Garmin username and password are required when session storage "
                "is not configured."
            )

        self._client = self._build_client(username=username, password=password)
        self._client.login(
            tokenstore=self._prepare_session_storage_path(session_storage_path)
        )

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

    def get_heart_rates(
        self,
        begin_date: date | str,
        end_date: date | str,
    ) -> dict[str, dict[str, Any]]:
        """Return Garmin heart-rate payloads for each day in a date range.

        Garmin Connect exposes heart-rate data as a per-day endpoint. This
        provider method preserves that raw Garmin payload shape and keys the
        responses by ISO date so callers can request an inclusive interval while
        still inspecting the original daily data returned by `garminconnect`.

        Args:
            begin_date: Inclusive start date for the query. Accepts either a
                `datetime.date` instance or an ISO `YYYY-MM-DD` string.
            end_date: Inclusive end date for the query. Accepts either a
                `datetime.date` instance or an ISO `YYYY-MM-DD` string.

        Returns:
            A dictionary keyed by ISO date. Each value is the corresponding
            Garmin Connect heart-rate dictionary for that day, preserving the
            raw provider shape apart from configured PII redaction.

        Raises:
            ValueError: If either date cannot be parsed as an ISO date or if
                `begin_date` is after `end_date`.
        """
        start = self._coerce_date(begin_date, field_name="begin_date")
        end = self._coerce_date(end_date, field_name="end_date")

        if start > end:
            raise ValueError("begin_date must be earlier than or equal to end_date.")

        heart_rates: dict[str, dict[str, Any]] = {}
        current = start
        while current <= end:
            current_date = current.isoformat()
            heart_rates[current_date] = self._sanitize_activity(
                self._client.get_heart_rates(current_date)
            )
            current += timedelta(days=1)

        return heart_rates

    @staticmethod
    def _build_client(
        username: str | None, password: str | None
    ) -> GarminConnectClient:
        """Create a Garmin Connect client from the third-party library.

        The import is intentionally lazy so unit tests can exercise the provider
        with fake clients without requiring the real `garminconnect` dependency
        or live Garmin credentials.

        Args:
            username: Optional Garmin Connect username or email address.
            password: Optional Garmin Connect password.

        Returns:
            An authenticated-capable Garmin Connect client instance.
        """
        from garminconnect import Garmin  # pylint: disable=import-outside-toplevel

        return Garmin(username, password)

    @staticmethod
    def _prepare_session_storage_path(session_storage_path: str | None) -> str | None:
        """Create and normalize the Garmin session token storage path.

        Args:
            session_storage_path: Optional local path used by `garminconnect` to
                load and persist reusable session tokens.

        Returns:
            A normalized string path when session storage is configured,
            otherwise `None`.
        """
        if not session_storage_path:
            return None

        path = Path(session_storage_path).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

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

    def _sanitize_activity(self, value: Any) -> Any:
        """Mask potential PII fields from Garmin activity payloads.

        Garmin activity objects may include account metadata, profile details,
        and location fields that are not needed for coaching analysis and may be
        interpreted as personal data by downstream guardrails. This sanitizer
        masks those values recursively while preserving payload shape for
        downstream normalization.

        Args:
            value: Garmin activity payload or nested value returned by the
                Garmin Connect client.

        Returns:
            A sanitized copy of the supplied value. Dictionaries and lists are
            copied recursively; float values are rounded to the provider's
            configured precision unless they are associated with a redacted key.
        """
        if isinstance(value, dict):
            return {
                key: (
                    PII_REDACTION_MASK
                    if self._redact_pii and self._is_pii_key(key)
                    else self._sanitize_activity(nested_value)
                )
                for key, nested_value in value.items()
            }

        if isinstance(value, list):
            return [self._sanitize_activity(item) for item in value]

        if isinstance(value, float) and math.isfinite(value):
            return round(value, MAX_FLOAT_DECIMAL_PLACES)

        return value

    @staticmethod
    def _resolve_redact_pii(redact_pii: bool | None) -> bool:
        """Resolve the PII redaction flag from an explicit value or environment.

        Args:
            redact_pii: Optional explicit setting supplied by callers.

        Returns:
            `True` when potential PII should be masked.

        Raises:
            ValueError: If `REDACT_PII` is set to an unsupported boolean value.
        """
        if redact_pii is not None:
            return redact_pii

        load_dotenv()
        raw_value = os.getenv("REDACT_PII", "true").strip().lower()
        if raw_value in BOOLEAN_TRUE_VALUES:
            return True
        if raw_value in BOOLEAN_FALSE_VALUES:
            return False

        raise ValueError(
            "REDACT_PII must be one of: true, false, yes, no, 1, 0, on, off."
        )

    @staticmethod
    def _is_pii_key(key: str) -> bool:
        """Return whether a Garmin payload key likely contains PII.

        Args:
            key: Payload key to classify.

        Returns:
            `True` when the key should be redacted before LLM use.
        """
        normalized_key = key.lower()
        return key in PII_EXACT_KEYS or any(
            fragment in normalized_key for fragment in PII_KEY_FRAGMENTS
        )
