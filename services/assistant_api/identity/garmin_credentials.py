"""
Author: L. Saetta
Date Modified: 2026-05-22
License: MIT
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from services.assistant_api.persistence import Database
from services.assistant_api.persistence.schema import garmin_credentials


class GarminCredentialError(RuntimeError):
    """Raised when Garmin credentials cannot be encrypted or decrypted."""


@dataclass(frozen=True)
class GarminCredentialStatus:
    """Safe Garmin credential metadata that can be returned to clients."""

    configured: bool
    garmin_username: str | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class GarminCredentials:
    """Decrypted Garmin credentials for backend-only provider construction."""

    user_id: int
    garmin_username: str
    garmin_password: str
    created_at: datetime
    updated_at: datetime


class GarminCredentialRepository:
    """Store one encrypted Garmin credential record per application user."""

    def __init__(
        self,
        database: Database,
        *,
        encryption_key: str | bytes,
    ) -> None:
        self._database = database
        self._fernet = Fernet(_normalize_key(encryption_key))

    def save_credentials(
        self,
        *,
        user_id: int,
        garmin_username: str,
        garmin_password: str,
    ) -> GarminCredentialStatus:
        """Create or replace the Garmin credentials for one user."""
        username = garmin_username.strip()
        password = garmin_password.strip()
        if not username:
            raise ValueError("garmin_username is required")
        if not password:
            raise ValueError("garmin_password is required")

        encrypted_password = self._fernet.encrypt(password.encode("utf-8")).decode(
            "ascii"
        )
        now = _utc_now().isoformat()
        with self._database.engine.begin() as connection:
            existing = (
                connection.execute(
                    select(garmin_credentials.c.id).where(
                        garmin_credentials.c.user_id == user_id
                    )
                )
                .mappings()
                .fetchone()
            )
            if existing is None:
                connection.execute(
                    garmin_credentials.insert().values(
                        user_id=user_id,
                        garmin_username=username,
                        encrypted_password=encrypted_password,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                connection.execute(
                    garmin_credentials.update()
                    .where(garmin_credentials.c.id == existing["id"])
                    .values(
                        garmin_username=username,
                        encrypted_password=encrypted_password,
                        updated_at=now,
                    )
                )

        return self.get_status(user_id=user_id)

    def get_status(self, *, user_id: int) -> GarminCredentialStatus:
        """Return safe metadata for the user's Garmin credential record."""
        with self._database.engine.connect() as connection:
            row = (
                connection.execute(
                    select(
                        garmin_credentials.c.garmin_username,
                        garmin_credentials.c.updated_at,
                    ).where(garmin_credentials.c.user_id == user_id)
                )
                .mappings()
                .fetchone()
            )

        if row is None:
            return GarminCredentialStatus(configured=False)

        return GarminCredentialStatus(
            configured=True,
            garmin_username=row["garmin_username"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def get_credentials(self, *, user_id: int) -> GarminCredentials | None:
        """Return decrypted credentials for backend-only Garmin access."""
        with self._database.engine.connect() as connection:
            row = (
                connection.execute(
                    select(
                        garmin_credentials.c.user_id,
                        garmin_credentials.c.garmin_username,
                        garmin_credentials.c.encrypted_password,
                        garmin_credentials.c.created_at,
                        garmin_credentials.c.updated_at,
                    ).where(garmin_credentials.c.user_id == user_id)
                )
                .mappings()
                .fetchone()
            )

        if row is None:
            return None

        try:
            password = self._fernet.decrypt(
                row["encrypted_password"].encode("ascii")
            ).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise GarminCredentialError(
                "Stored Garmin credentials could not be decrypted."
            ) from exc

        return GarminCredentials(
            user_id=row["user_id"],
            garmin_username=row["garmin_username"],
            garmin_password=password,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def delete_credentials(self, *, user_id: int) -> None:
        """Remove the Garmin credential record for one user."""
        with self._database.engine.begin() as connection:
            connection.execute(
                garmin_credentials.delete().where(
                    garmin_credentials.c.user_id == user_id
                )
            )


def load_garmin_credential_encryption_key() -> str:
    """Load the Garmin credential encryption key from env or secret file."""
    key_file = os.getenv("GARMIN_CREDENTIAL_ENCRYPTION_KEY_FILE")
    if key_file:
        with open(key_file, encoding="utf-8") as key_handle:
            return key_handle.read().strip()

    key = os.getenv("GARMIN_CREDENTIAL_ENCRYPTION_KEY")
    if key:
        return key.strip()

    raise GarminCredentialError(
        "GARMIN_CREDENTIAL_ENCRYPTION_KEY or "
        "GARMIN_CREDENTIAL_ENCRYPTION_KEY_FILE is required."
    )


def _normalize_key(encryption_key: str | bytes) -> bytes:
    """Validate and normalize a Fernet key."""
    key = (
        encryption_key.strip().encode("ascii")
        if isinstance(encryption_key, str)
        else encryption_key.strip()
    )
    Fernet(key)
    return key


def _utc_now() -> datetime:
    """Return the current UTC timestamp without microseconds."""
    return datetime.now(UTC).replace(microsecond=0)
