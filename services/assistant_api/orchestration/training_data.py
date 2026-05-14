"""
Author: L. Saetta
Date Modified: 2026-05-14
License: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from services.assistant_api.identity.garmin_credentials import (
    GarminCredentialRepository,
)


class TrainingActivitiesClient(Protocol):  # pylint: disable=too-few-public-methods
    """Protocol for assistant tool access to local training data."""

    async def list_activities(
        self,
        *,
        user_id: int,
        begin_date: str,
        end_date: str,
        activity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return activities from the local training data provider."""

    async def get_heart_rates(
        self,
        *,
        user_id: int,
        begin_date: str,
        end_date: str,
    ) -> dict[str, dict[str, Any]]:
        """Return daily heart-rate payloads from the local provider."""


class LocalTrainingDataClient:  # pylint: disable=too-few-public-methods
    """Async adapter around the local Python training data provider."""

    def __init__(self, provider: Any) -> None:
        """Create a local training data client.

        Args:
            provider: Object exposing `list_activities`, normally
                `TrainingDataProvider`.
        """
        self._provider = provider

    async def list_activities(
        self,
        *,
        user_id: int,
        begin_date: str,
        end_date: str,
        activity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return activities for a date range using local Python calls."""
        _ = user_id
        return self._provider.list_activities(
            begin_date=begin_date,
            end_date=end_date,
            activity_type=activity_type,
        )

    async def get_heart_rates(
        self,
        *,
        user_id: int,
        begin_date: str,
        end_date: str,
    ) -> dict[str, dict[str, Any]]:
        """Return daily heart-rate payloads using local Python calls."""
        _ = user_id
        return self._provider.get_heart_rates(
            begin_date=begin_date,
            end_date=end_date,
        )


class UserScopedTrainingDataClient:  # pylint: disable=too-few-public-methods
    """Create Garmin providers from credentials owned by the current user."""

    def __init__(
        self,
        *,
        credential_repository: GarminCredentialRepository,
        session_storage_root: str | Path,
        provider_factory: Any,
    ) -> None:
        """Create a user-scoped Garmin training data adapter."""
        self._credential_repository = credential_repository
        self._session_storage_root = Path(session_storage_root)
        self._provider_factory = provider_factory

    async def list_activities(
        self,
        *,
        user_id: int,
        begin_date: str,
        end_date: str,
        activity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return activities for the authenticated user's Garmin account."""
        return self._provider_for_user(user_id).list_activities(
            begin_date=begin_date,
            end_date=end_date,
            activity_type=activity_type,
        )

    async def get_heart_rates(
        self,
        *,
        user_id: int,
        begin_date: str,
        end_date: str,
    ) -> dict[str, dict[str, Any]]:
        """Return heart-rate payloads for the authenticated user's account."""
        return self._provider_for_user(user_id).get_heart_rates(
            begin_date=begin_date,
            end_date=end_date,
        )

    def _provider_for_user(self, user_id: int) -> Any:
        """Build a provider using decrypted credentials and user session storage."""
        credentials = self._credential_repository.get_credentials(user_id=user_id)
        if credentials is None:
            raise RuntimeError("Garmin credentials are not configured for this user.")

        session_path = self._session_storage_root / str(user_id)
        return self._provider_factory(
            username=credentials.garmin_username,
            password=credentials.garmin_password,
            session_storage_path=str(session_path),
        )
