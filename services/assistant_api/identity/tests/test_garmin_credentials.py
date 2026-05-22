"""
Author: L. Saetta
Date Modified: 2026-05-22
License: MIT
"""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from services.assistant_api.identity.garmin_credentials import (
    GarminCredentialRepository,
)
from services.assistant_api.identity.users import UserRepository
from services.assistant_api.persistence.schema import garmin_credentials
from services.assistant_api.tests.database import build_test_database


def test_save_credentials_encrypts_password_and_returns_safe_status(tmp_path) -> None:
    """Verify Garmin credentials are encrypted and status excludes secrets."""
    database = build_test_database(tmp_path)
    user_id = UserRepository(database).ensure_user(username="alice").id
    repository = GarminCredentialRepository(
        database,
        encryption_key=Fernet.generate_key(),
    )

    status = repository.save_credentials(
        user_id=user_id,
        garmin_username="alice@example.com",
        garmin_password="super-secret",
    )

    assert status.configured is True
    assert status.garmin_username == "alice@example.com"
    assert status.updated_at is not None

    with database.engine.connect() as connection:
        stored = connection.execute(
            select(garmin_credentials.c.encrypted_password).where(
                garmin_credentials.c.user_id == user_id
            )
        ).scalar_one()

    assert stored != "super-secret"
    credentials = repository.get_credentials(user_id=user_id)
    assert credentials is not None
    assert credentials.garmin_username == "alice@example.com"
    assert credentials.garmin_password == "super-secret"


def test_credentials_are_isolated_by_user_id(tmp_path) -> None:
    """Verify one user's Garmin credentials do not leak to another user."""
    database = build_test_database(tmp_path)
    users = UserRepository(database)
    alice_id = users.ensure_user(username="alice").id
    bob_id = users.ensure_user(username="bob").id
    repository = GarminCredentialRepository(
        database,
        encryption_key=Fernet.generate_key(),
    )

    repository.save_credentials(
        user_id=alice_id,
        garmin_username="alice@example.com",
        garmin_password="alice-secret",
    )
    repository.save_credentials(
        user_id=bob_id,
        garmin_username="bob@example.com",
        garmin_password="bob-secret",
    )

    alice = repository.get_credentials(user_id=alice_id)
    bob = repository.get_credentials(user_id=bob_id)

    assert alice is not None
    assert bob is not None
    assert alice.garmin_username == "alice@example.com"
    assert alice.garmin_password == "alice-secret"
    assert bob.garmin_username == "bob@example.com"
    assert bob.garmin_password == "bob-secret"


def test_delete_credentials_removes_only_current_user_record(tmp_path) -> None:
    """Verify deleting credentials is scoped to the requested user."""
    database = build_test_database(tmp_path)
    users = UserRepository(database)
    alice_id = users.ensure_user(username="alice").id
    bob_id = users.ensure_user(username="bob").id
    repository = GarminCredentialRepository(
        database,
        encryption_key=Fernet.generate_key(),
    )
    repository.save_credentials(
        user_id=alice_id,
        garmin_username="alice@example.com",
        garmin_password="alice-secret",
    )
    repository.save_credentials(
        user_id=bob_id,
        garmin_username="bob@example.com",
        garmin_password="bob-secret",
    )

    repository.delete_credentials(user_id=alice_id)

    assert repository.get_credentials(user_id=alice_id) is None
    assert repository.get_credentials(user_id=bob_id) is not None


def test_save_credentials_rejects_blank_values(tmp_path) -> None:
    """Verify blank Garmin credential fields are rejected."""
    database = build_test_database(tmp_path)
    user_id = UserRepository(database).ensure_user(username="alice").id
    repository = GarminCredentialRepository(
        database,
        encryption_key=Fernet.generate_key(),
    )

    with pytest.raises(ValueError):
        repository.save_credentials(
            user_id=user_id,
            garmin_username="",
            garmin_password="secret",
        )
