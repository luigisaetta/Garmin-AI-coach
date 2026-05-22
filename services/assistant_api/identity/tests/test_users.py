"""
Author: L. Saetta
Date Modified: 2026-05-22
License: MIT
"""

from __future__ import annotations

import pytest

from services.assistant_api.identity.users import UserRepository
from services.assistant_api.tests.database import build_test_database


def test_ensure_user_creates_application_user(tmp_path) -> None:
    """Verify a Basic Auth username gets a stable application user id."""
    repository = UserRepository(build_test_database(tmp_path))

    user = repository.ensure_user(username="Alice", display_name="Alice Runner")

    assert user.id > 0
    assert user.username == "alice"
    assert user.display_name == "Alice Runner"
    assert user.is_active is True
    assert user.created_at == user.updated_at


def test_ensure_user_updates_existing_username_without_changing_id(tmp_path) -> None:
    """Verify repeated provisioning keeps the stable ownership key."""
    repository = UserRepository(build_test_database(tmp_path))
    original = repository.ensure_user(username="alice", display_name="Alice")

    updated = repository.ensure_user(username="alice", display_name="A. Runner")

    assert updated.id == original.id
    assert updated.username == "alice"
    assert updated.display_name == "A. Runner"
    assert updated.updated_at >= original.updated_at


def test_get_by_username_returns_none_for_unknown_user(tmp_path) -> None:
    """Verify unknown authenticated usernames can be rejected later."""
    repository = UserRepository(build_test_database(tmp_path))

    assert repository.get_by_username("missing") is None


def test_ensure_user_rejects_blank_username(tmp_path) -> None:
    """Verify local users cannot be created without a username."""
    repository = UserRepository(build_test_database(tmp_path))

    with pytest.raises(ValueError, match="username"):
        repository.ensure_user(username=" ")
