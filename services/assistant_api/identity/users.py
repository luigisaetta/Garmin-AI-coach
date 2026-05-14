"""
Author: L. Saetta
Date Modified: 2026-05-14
License: MIT
"""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class ApplicationUser:
    """A local application user resolved from an authenticated username."""

    id: int
    username: str
    display_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserRepository:
    """Persist local application users in SQLite."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def ensure_user(
        self,
        *,
        username: str,
        display_name: str | None = None,
        is_active: bool = True,
    ) -> ApplicationUser:
        """Create or update a local application user for a Basic Auth username."""
        normalized_username = _normalize_username(username)
        normalized_display_name = (display_name or normalized_username).strip()
        if not normalized_display_name:
            normalized_display_name = normalized_username

        now = _utc_now().isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO users (
                    username,
                    display_name,
                    is_active,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    display_name = excluded.display_name,
                    is_active = excluded.is_active,
                    updated_at = excluded.updated_at
                """,
                (
                    normalized_username,
                    normalized_display_name,
                    int(is_active),
                    now,
                    now,
                ),
            )

        user = self.get_by_username(normalized_username)
        if user is None:
            raise RuntimeError("application user was not persisted")
        return user

    def get_by_username(self, username: str) -> ApplicationUser | None:
        """Return an active or inactive user by unique username."""
        normalized_username = _normalize_username(username)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    username,
                    display_name,
                    is_active,
                    created_at,
                    updated_at
                FROM users
                WHERE username = ?
                """,
                (normalized_username,),
            ).fetchone()

        if row is None:
            return None
        return _user_from_row(row)

    def _initialize_schema(self) -> None:
        """Create the local user table required by multi-user ownership."""
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_username
                ON users(username)
                """)

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection configured for row-based reads."""
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser used by provisioning scripts."""
    parser = argparse.ArgumentParser(description="Manage local application users.")
    parser.add_argument("--db-path", required=True, help="SQLite database path.")

    subparsers = parser.add_subparsers(dest="command", required=True)
    ensure = subparsers.add_parser(
        "ensure-user",
        help="Create or update an application user.",
    )
    ensure.add_argument("--username", required=True)
    ensure.add_argument("--display-name")
    ensure.add_argument(
        "--inactive",
        action="store_true",
        help="Create or update the user as inactive.",
    )

    return parser


def main() -> None:
    """Run the local user management command-line interface."""
    args = build_parser().parse_args()
    repository = UserRepository(args.db_path)

    if args.command == "ensure-user":
        user = repository.ensure_user(
            username=args.username,
            display_name=args.display_name,
            is_active=not args.inactive,
        )
        active_label = str(user.is_active).lower()
        print(
            f"user_id={user.id} username={user.username} "
            f"display_name={user.display_name} is_active={active_label}"
        )


def _normalize_username(username: str) -> str:
    """Normalize and validate the local application username."""
    normalized_username = username.strip().lower()
    if not normalized_username:
        raise ValueError("username is required")
    if any(char.isspace() for char in normalized_username):
        raise ValueError("username must not contain whitespace")
    return normalized_username


def _user_from_row(row: sqlite3.Row) -> ApplicationUser:
    """Convert a SQLite row to an application user."""
    return ApplicationUser(
        id=row["id"],
        username=row["username"],
        display_name=row["display_name"],
        is_active=bool(row["is_active"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _utc_now() -> datetime:
    """Return the current UTC timestamp without microseconds."""
    return datetime.now(UTC).replace(microsecond=0)


if __name__ == "__main__":
    main()
