"""
Author: L. Saetta
Date Modified: 2026-05-14
License: MIT
"""

from __future__ import annotations

from cryptography.fernet import Fernet
import pytest

from services.assistant_api.identity.garmin_credentials import (
    GarminCredentialRepository,
)
from services.assistant_api.identity.users import UserRepository
from services.assistant_api.orchestration.training_data import (
    UserScopedTrainingDataClient,
)


class FakeProvider:
    """Fake Garmin provider that captures construction arguments."""

    def __init__(
        self,
        *,
        username: str,
        password: str,
        session_storage_path: str,
    ) -> None:
        self.username = username
        self.password = password
        self.session_storage_path = session_storage_path

    def list_activities(
        self,
        *,
        begin_date: str,
        end_date: str,
        activity_type: str | None = None,
    ) -> list[dict[str, str | None]]:
        """Return one activity containing non-secret provider metadata."""
        return [
            {
                "username": self.username,
                "password": self.password,
                "session_storage_path": self.session_storage_path,
                "begin_date": begin_date,
                "end_date": end_date,
                "activity_type": activity_type,
            }
        ]

    def get_heart_rates(
        self,
        *,
        begin_date: str,
        end_date: str,
    ) -> dict[str, dict[str, str]]:
        """Return one heart-rate payload containing session metadata."""
        return {
            begin_date: {
                "session_storage_path": self.session_storage_path,
                "end_date": end_date,
            }
        }


def _provider_factory(**kwargs) -> FakeProvider:
    """Build the fake provider used by user-scoped client tests."""
    return FakeProvider(**kwargs)


@pytest.mark.anyio
async def test_user_scoped_training_client_uses_current_user_credentials(
    tmp_path,
) -> None:
    """Verify Garmin credentials and session storage are scoped per user."""
    database_path = tmp_path / "coach.db"
    user_id = UserRepository(database_path).ensure_user(username="alice").id
    repository = GarminCredentialRepository(
        database_path,
        encryption_key=Fernet.generate_key(),
    )
    repository.save_credentials(
        user_id=user_id,
        garmin_username="alice@example.com",
        garmin_password="alice-secret",
    )
    client = UserScopedTrainingDataClient(
        credential_repository=repository,
        session_storage_root=tmp_path / "sessions",
        provider_factory=_provider_factory,
    )

    activities = await client.list_activities(
        user_id=user_id,
        begin_date="2026-05-01",
        end_date="2026-05-07",
        activity_type="running",
    )

    assert activities == [
        {
            "username": "alice@example.com",
            "password": "alice-secret",
            "session_storage_path": str(tmp_path / "sessions" / str(user_id)),
            "begin_date": "2026-05-01",
            "end_date": "2026-05-07",
            "activity_type": "running",
        }
    ]


@pytest.mark.anyio
async def test_user_scoped_training_client_rejects_missing_credentials(
    tmp_path,
) -> None:
    """Verify Garmin data access fails when credentials are not configured."""
    database_path = tmp_path / "coach.db"
    user_id = UserRepository(database_path).ensure_user(username="alice").id
    repository = GarminCredentialRepository(
        database_path,
        encryption_key=Fernet.generate_key(),
    )
    client = UserScopedTrainingDataClient(
        credential_repository=repository,
        session_storage_root=tmp_path / "sessions",
        provider_factory=_provider_factory,
    )

    try:
        await client.get_heart_rates(
            user_id=user_id,
            begin_date="2026-05-01",
            end_date="2026-05-01",
        )
    except RuntimeError as exc:
        assert "not configured" in str(exc)
    else:
        raise AssertionError("Expected missing Garmin credentials to fail")
