"""
Author: L. Saetta
Date Modified: 2026-05-22
License: MIT
"""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from services.assistant_api.identity.users import normalize_username
from services.assistant_api.persistence import Database, load_database_settings
from services.assistant_api.persistence.schema import (
    garmin_credentials,
    nutrition_diary_entries,
    nutrition_plan_current,
    users,
)


@dataclass(frozen=True)
class MigrationSummary:
    """Row counts copied from a legacy SQLite database into MySQL."""

    users: int
    garmin_credentials: int
    diary_entries: int
    nutrition_plans: int


class SqliteToMysqlMigration:  # pylint: disable=too-few-public-methods
    """Copy legacy SQLite data into the configured assistant database."""

    def __init__(self, sqlite_path: str | Path, target_database: Database) -> None:
        self._sqlite_path = Path(sqlite_path)
        self._target_database = target_database

    def run(self, *, initial_username: str | None = None) -> MigrationSummary:
        """Run an idempotent migration from SQLite to the target database."""
        if not self._sqlite_path.exists():
            raise FileNotFoundError(f"SQLite database not found: {self._sqlite_path}")

        with _connect_sqlite(self._sqlite_path) as source:
            source_users = self._read_users(source)
            if not source_users and initial_username:
                source_users = [_build_initial_user(initial_username)]

            initial_user_id = source_users[0]["id"] if source_users else None
            diary_rows = self._read_diary_entries(source, initial_user_id)
            plan_rows = self._read_nutrition_plans(source, initial_user_id)
            credential_rows = self._read_garmin_credentials(source)

        with self._target_database.engine.begin() as target:
            user_count = _upsert_rows(target, users, source_users)
            credential_count = _upsert_rows(target, garmin_credentials, credential_rows)
            diary_count = _upsert_rows(target, nutrition_diary_entries, diary_rows)
            plan_count = _upsert_rows(target, nutrition_plan_current, plan_rows)

        return MigrationSummary(
            users=user_count,
            garmin_credentials=credential_count,
            diary_entries=diary_count,
            nutrition_plans=plan_count,
        )

    @staticmethod
    def _read_users(connection: sqlite3.Connection) -> list[dict[str, Any]]:
        """Read local application users from SQLite when present."""
        if not _table_exists(connection, "users"):
            return []

        return [dict(row) for row in connection.execute("""
                SELECT id, username, display_name, is_active, created_at, updated_at
                FROM users
                ORDER BY id ASC
                """).fetchall()]

    @staticmethod
    def _read_diary_entries(
        connection: sqlite3.Connection,
        initial_user_id: int | None,
    ) -> list[dict[str, Any]]:
        """Read diary entries, assigning legacy single-user rows when needed."""
        if not _table_exists(connection, "nutrition_diary_entries"):
            return []

        has_user_id = _column_exists(connection, "nutrition_diary_entries", "user_id")
        if not has_user_id and initial_user_id is None:
            raise ValueError(
                "nutrition_diary_entries has no user_id; pass --initial-username"
            )

        selected_user_id = "user_id" if has_user_id else f"{initial_user_id} AS user_id"
        return [dict(row) for row in connection.execute(f"""
                SELECT
                    id,
                    {selected_user_id},
                    entry_date,
                    training_type,
                    meals_text,
                    notes,
                    created_at,
                    updated_at
                FROM nutrition_diary_entries
                ORDER BY id ASC
                """).fetchall()]

    @staticmethod
    def _read_nutrition_plans(
        connection: sqlite3.Connection,
        initial_user_id: int | None,
    ) -> list[dict[str, Any]]:
        """Read current nutrition plans, assigning legacy rows when needed."""
        if not _table_exists(connection, "nutrition_plan_current"):
            return []

        has_user_id = _column_exists(connection, "nutrition_plan_current", "user_id")
        if not has_user_id and initial_user_id is None:
            raise ValueError(
                "nutrition_plan_current has no user_id; pass --initial-username"
            )

        selected_user_id = "user_id" if has_user_id else f"{initial_user_id} AS user_id"
        return [dict(row) for row in connection.execute(f"""
                SELECT
                    id,
                    {selected_user_id},
                    original_filename,
                    content_type,
                    file_sha256,
                    extracted_text,
                    uploaded_at,
                    updated_at
                FROM nutrition_plan_current
                ORDER BY id ASC
                """).fetchall()]

    @staticmethod
    def _read_garmin_credentials(
        connection: sqlite3.Connection,
    ) -> list[dict[str, Any]]:
        """Read already encrypted Garmin credential metadata when present."""
        if not _table_exists(connection, "garmin_credentials"):
            return []

        return [dict(row) for row in connection.execute("""
                SELECT
                    id,
                    user_id,
                    garmin_username,
                    encrypted_password,
                    created_at,
                    updated_at
                FROM garmin_credentials
                ORDER BY id ASC
                """).fetchall()]


def build_parser() -> argparse.ArgumentParser:
    """Build the SQLite-to-MySQL migration command-line parser."""
    parser = argparse.ArgumentParser(
        description="Migrate legacy Garmin AI Coach SQLite data to MySQL.",
    )
    parser.add_argument("--sqlite-path", required=True, help="Legacy SQLite file path.")
    parser.add_argument(
        "--target-database-url",
        help="Optional SQLAlchemy target URL. Defaults to MYSQL_* environment vars.",
    )
    parser.add_argument(
        "--initial-username",
        help=(
            "Application username used to own legacy nutrition rows when the "
            "SQLite tables do not include user_id."
        ),
    )
    return parser


def main() -> None:
    """Run the SQLite-to-MySQL migration from the command line."""
    args = build_parser().parse_args()
    target_database = (
        Database.from_url(args.target_database_url)
        if args.target_database_url
        else Database.from_settings(load_database_settings())
    )
    summary = SqliteToMysqlMigration(args.sqlite_path, target_database).run(
        initial_username=args.initial_username
    )
    print(
        f"users={summary.users} garmin_credentials={summary.garmin_credentials} "
        f"diary_entries={summary.diary_entries} nutrition_plans={summary.nutrition_plans}"
    )


def _build_initial_user(username: str) -> dict[str, Any]:
    normalized_username = normalize_username(username)
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    return {
        "id": 1,
        "username": normalized_username,
        "display_name": normalized_username,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }


def _upsert_rows(connection, table, rows: list[dict[str, Any]]) -> int:
    for row in rows:
        existing = (
            connection.execute(select(table.c.id).where(table.c.id == row["id"]))
            .mappings()
            .fetchone()
        )
        if existing is None:
            connection.execute(table.insert().values(**row))
        else:
            values = {key: value for key, value in row.items() if key != "id"}
            connection.execute(
                table.update().where(table.c.id == row["id"]).values(**values)
            )
    return len(rows)


def _connect_sqlite(sqlite_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(sqlite_path)
    connection.row_factory = sqlite3.Row
    return connection


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _column_exists(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
) -> bool:
    return any(
        row["name"] == column_name
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    )


if __name__ == "__main__":
    main()
