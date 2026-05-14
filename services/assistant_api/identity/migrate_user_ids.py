"""
Author: L. Saetta
Date Modified: 2026-05-14
License: MIT
"""

from __future__ import annotations

# pylint: disable=duplicate-code,too-few-public-methods

import argparse
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from services.assistant_api.identity.users import ApplicationUser, UserRepository


@dataclass(frozen=True)
class MigrationResult:
    """Summary of rows migrated to the initial application user."""

    user_id: int
    username: str
    diary_rows: int
    plan_rows: int


class UserIdMigration:
    """Migrate single-user nutrition tables to user-owned SQLite tables."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        *,
        initial_username: str,
        display_name: str | None = None,
    ) -> MigrationResult:
        """Ensure the initial user and migrate existing nutrition rows."""
        user = UserRepository(self._database_path).ensure_user(
            username=initial_username,
            display_name=display_name,
        )

        with self._connect() as connection:
            connection.execute("BEGIN")
            try:
                diary_rows = self._migrate_diary_entries(connection, user)
                plan_rows = self._migrate_current_plan(connection, user)
                self._create_indexes(connection)
            except Exception:
                connection.rollback()
                raise
            connection.commit()

        return MigrationResult(
            user_id=user.id,
            username=user.username,
            diary_rows=diary_rows,
            plan_rows=plan_rows,
        )

    def _migrate_diary_entries(
        self,
        connection: sqlite3.Connection,
        user: ApplicationUser,
    ) -> int:
        """Rebuild nutrition diary entries with a required user owner."""
        if not _table_exists(connection, "nutrition_diary_entries"):
            connection.execute("""
                CREATE TABLE nutrition_diary_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    entry_date TEXT NOT NULL,
                    training_type TEXT NOT NULL,
                    meals_text TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """)
            return 0

        if _has_required_user_id(connection, "nutrition_diary_entries"):
            return _count_rows(connection, "nutrition_diary_entries")

        original_rows = _count_rows(connection, "nutrition_diary_entries")
        connection.execute(
            "ALTER TABLE nutrition_diary_entries RENAME TO nutrition_diary_entries_old"
        )
        connection.execute("""
            CREATE TABLE nutrition_diary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                entry_date TEXT NOT NULL,
                training_type TEXT NOT NULL,
                meals_text TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """)
        connection.execute(
            """
            INSERT INTO nutrition_diary_entries (
                id,
                user_id,
                entry_date,
                training_type,
                meals_text,
                notes,
                created_at,
                updated_at
            )
            SELECT
                id,
                ?,
                entry_date,
                training_type,
                meals_text,
                notes,
                created_at,
                updated_at
            FROM nutrition_diary_entries_old
            """,
            (user.id,),
        )
        connection.execute("DROP TABLE nutrition_diary_entries_old")
        return original_rows

    def _migrate_current_plan(
        self,
        connection: sqlite3.Connection,
        user: ApplicationUser,
    ) -> int:
        """Rebuild current nutrition plans with one current plan per user."""
        if not _table_exists(connection, "nutrition_plan_current"):
            connection.execute("""
                CREATE TABLE nutrition_plan_current (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE,
                    original_filename TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    file_sha256 TEXT NOT NULL,
                    extracted_text TEXT NOT NULL,
                    uploaded_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
                """)
            return 0

        if _has_required_user_id(connection, "nutrition_plan_current"):
            return _count_rows(connection, "nutrition_plan_current")

        original_rows = _count_rows(connection, "nutrition_plan_current")
        connection.execute(
            "ALTER TABLE nutrition_plan_current RENAME TO nutrition_plan_current_old"
        )
        connection.execute("""
            CREATE TABLE nutrition_plan_current (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                original_filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                file_sha256 TEXT NOT NULL,
                extracted_text TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """)
        connection.execute(
            """
            INSERT INTO nutrition_plan_current (
                id,
                user_id,
                original_filename,
                content_type,
                file_sha256,
                extracted_text,
                uploaded_at,
                updated_at
            )
            SELECT
                id,
                ?,
                original_filename,
                content_type,
                file_sha256,
                extracted_text,
                uploaded_at,
                updated_at
            FROM nutrition_plan_current_old
            """,
            (user.id,),
        )
        connection.execute("DROP TABLE nutrition_plan_current_old")
        return original_rows

    @staticmethod
    def _create_indexes(connection: sqlite3.Connection) -> None:
        """Create user-scoped lookup indexes after row ownership is backfilled."""
        connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_nutrition_diary_user_entry_date
            ON nutrition_diary_entries(user_id, entry_date)
            """)
        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_nutrition_diary_user_date_range
            ON nutrition_diary_entries(user_id, entry_date)
            """)
        connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_nutrition_plan_current_user
            ON nutrition_plan_current(user_id)
            """)

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection configured for explicit transactions."""
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.isolation_level = None
        return connection


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser used by the migration script."""
    parser = argparse.ArgumentParser(
        description="Migrate local nutrition data to user-owned tables.",
    )
    parser.add_argument("--db-path", required=True, help="SQLite database path.")
    parser.add_argument(
        "--initial-username",
        required=True,
        help="Existing single-user data will be assigned to this local user.",
    )
    parser.add_argument("--display-name")
    return parser


def main() -> None:
    """Run the user ownership migration from the command line."""
    args = build_parser().parse_args()
    result = UserIdMigration(args.db_path).run(
        initial_username=args.initial_username,
        display_name=args.display_name,
    )
    print(
        f"user_id={result.user_id} username={result.username} "
        f"diary_rows={result.diary_rows} plan_rows={result.plan_rows}"
    )


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


def _has_required_user_id(connection: sqlite3.Connection, table_name: str) -> bool:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row["name"] == "user_id" and row["notnull"] == 1 for row in rows)


def _count_rows(connection: sqlite3.Connection, table_name: str) -> int:
    row = connection.execute(
        f"SELECT COUNT(*) AS row_count FROM {table_name}"
    ).fetchone()
    return int(row["row_count"])


if __name__ == "__main__":
    main()
