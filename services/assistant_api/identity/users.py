"""
Author: L. Saetta
Date Modified: 2026-05-22
License: MIT
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from services.assistant_api.persistence import Database, load_database_settings
from services.assistant_api.persistence.schema import users


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
    """Persist local application users in the assistant database."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def ensure_user(
        self,
        *,
        username: str,
        display_name: str | None = None,
        is_active: bool = True,
    ) -> ApplicationUser:
        """Create or update a local application user for a Basic Auth username."""
        normalized_username = normalize_username(username)
        normalized_display_name = (display_name or normalized_username).strip()
        if not normalized_display_name:
            normalized_display_name = normalized_username

        now = _utc_now().isoformat()
        with self._database.engine.begin() as connection:
            existing = (
                connection.execute(
                    select(users.c.id).where(users.c.username == normalized_username)
                )
                .mappings()
                .fetchone()
            )
            if existing is None:
                connection.execute(
                    users.insert().values(
                        username=normalized_username,
                        display_name=normalized_display_name,
                        is_active=is_active,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                connection.execute(
                    users.update()
                    .where(users.c.id == existing["id"])
                    .values(
                        display_name=normalized_display_name,
                        is_active=is_active,
                        updated_at=now,
                    )
                )

        user = self.get_by_username(normalized_username)
        if user is None:
            raise RuntimeError("application user was not persisted")
        return user

    def get_by_username(self, username: str) -> ApplicationUser | None:
        """Return an active or inactive user by unique username."""
        normalized_username = normalize_username(username)
        with self._database.engine.connect() as connection:
            row = (
                connection.execute(
                    select(
                        users.c.id,
                        users.c.username,
                        users.c.display_name,
                        users.c.is_active,
                        users.c.created_at,
                        users.c.updated_at,
                    ).where(users.c.username == normalized_username)
                )
                .mappings()
                .fetchone()
            )

        if row is None:
            return None
        return _user_from_row(row)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser used by provisioning scripts."""
    parser = argparse.ArgumentParser(description="Manage local application users.")

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
    repository = UserRepository(Database.from_settings(load_database_settings()))

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


def normalize_username(username: str) -> str:
    """Normalize and validate the local application username."""
    normalized_username = username.strip().lower()
    if not normalized_username:
        raise ValueError("username is required")
    if any(char.isspace() for char in normalized_username):
        raise ValueError("username must not contain whitespace")
    return normalized_username


def _user_from_row(row) -> ApplicationUser:
    """Convert a database row to an application user."""
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
