"""
Author: L. Saetta
Date Modified: 2026-05-14
License: MIT
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


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
        database_path: str | Path,
        *,
        encryption_key: str | bytes,
    ) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._fernet = Fernet(_normalize_key(encryption_key))
        self._initialize_schema()

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
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO garmin_credentials (
                    user_id,
                    garmin_username,
                    encrypted_password,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    garmin_username = excluded.garmin_username,
                    encrypted_password = excluded.encrypted_password,
                    updated_at = excluded.updated_at
                """,
                (user_id, username, encrypted_password, now, now),
            )

        return self.get_status(user_id=user_id)

    def get_status(self, *, user_id: int) -> GarminCredentialStatus:
        """Return safe metadata for the user's Garmin credential record."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT garmin_username, updated_at
                FROM garmin_credentials
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            return GarminCredentialStatus(configured=False)

        return GarminCredentialStatus(
            configured=True,
            garmin_username=row["garmin_username"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def get_credentials(self, *, user_id: int) -> GarminCredentials | None:
        """Return decrypted credentials for backend-only Garmin access."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    user_id,
                    garmin_username,
                    encrypted_password,
                    created_at,
                    updated_at
                FROM garmin_credentials
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

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
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM garmin_credentials WHERE user_id = ?",
                (user_id,),
            )

    def _initialize_schema(self) -> None:
        """Create Garmin credential storage tables and indexes."""
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS garmin_credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    garmin_username TEXT NOT NULL,
                    encrypted_password TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """)
            connection.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_garmin_credentials_user
                ON garmin_credentials(user_id)
                """)

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection configured for row-based reads."""
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def load_garmin_credential_encryption_key() -> str:
    """Load the Garmin credential encryption key from env or secret file."""
    key_file = os.getenv("GARMIN_CREDENTIAL_ENCRYPTION_KEY_FILE")
    if key_file:
        return Path(key_file).read_text(encoding="utf-8").strip()

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
