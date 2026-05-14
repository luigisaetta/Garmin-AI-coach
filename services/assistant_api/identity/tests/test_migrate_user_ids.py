"""
Author: L. Saetta
Date Modified: 2026-05-14
License: MIT
"""

from __future__ import annotations

# pylint: disable=duplicate-code

import sqlite3

import pytest

from services.assistant_api.identity.migrate_user_ids import UserIdMigration


def test_migration_backfills_existing_nutrition_rows(tmp_path) -> None:
    """Verify single-user nutrition rows are assigned to the initial user."""
    database_path = tmp_path / "coach.db"
    _create_single_user_nutrition_schema(database_path)

    result = UserIdMigration(database_path).run(
        initial_username="Alice",
        display_name="Alice Runner",
    )

    with _connect(database_path) as connection:
        diary_row = connection.execute("""
            SELECT user_id, entry_date, training_type, meals_text, notes
            FROM nutrition_diary_entries
            """).fetchone()
        plan_row = connection.execute("""
            SELECT user_id, original_filename, extracted_text
            FROM nutrition_plan_current
            """).fetchone()
        user_row = connection.execute(
            "SELECT id, username, display_name FROM users"
        ).fetchone()

    assert result.user_id == user_row["id"]
    assert result.username == "alice"
    assert result.diary_rows == 1
    assert result.plan_rows == 1
    assert user_row["display_name"] == "Alice Runner"
    assert diary_row["user_id"] == result.user_id
    assert diary_row["entry_date"] == "2026-05-12"
    assert diary_row["training_type"] == "Easy run"
    assert diary_row["meals_text"] == "Breakfast: oats."
    assert diary_row["notes"] == "Good energy."
    assert plan_row["user_id"] == result.user_id
    assert plan_row["original_filename"] == "plan.pdf"
    assert plan_row["extracted_text"] == "Nutrition plan text"


def test_migration_enforces_user_scoped_constraints(tmp_path) -> None:
    """Verify migrated tables require ownership and user-scoped uniqueness."""
    database_path = tmp_path / "coach.db"
    _create_single_user_nutrition_schema(database_path)

    result = UserIdMigration(database_path).run(initial_username="alice")

    with _connect(database_path) as connection:
        diary_columns = _table_columns(connection, "nutrition_diary_entries")
        plan_columns = _table_columns(connection, "nutrition_plan_current")
        diary_indexes = _index_names(connection, "nutrition_diary_entries")
        plan_indexes = _index_names(connection, "nutrition_plan_current")

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO nutrition_diary_entries (
                    entry_date,
                    training_type,
                    meals_text,
                    notes,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "2026-05-13",
                    "Rest",
                    "Missing owner.",
                    "",
                    "2026-05-14T10:00:00+00:00",
                    "2026-05-14T10:00:00+00:00",
                ),
            )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO nutrition_diary_entries (
                    user_id,
                    entry_date,
                    training_type,
                    meals_text,
                    notes,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.user_id,
                    "2026-05-12",
                    "Duplicate",
                    "Duplicate day.",
                    "",
                    "2026-05-14T10:00:00+00:00",
                    "2026-05-14T10:00:00+00:00",
                ),
            )

    assert diary_columns["user_id"] == 1
    assert plan_columns["user_id"] == 1
    assert "idx_nutrition_diary_user_entry_date" in diary_indexes
    assert "idx_nutrition_plan_current_user" in plan_indexes


def test_migration_is_idempotent(tmp_path) -> None:
    """Verify the migration can be safely re-run."""
    database_path = tmp_path / "coach.db"
    _create_single_user_nutrition_schema(database_path)
    migration = UserIdMigration(database_path)

    first = migration.run(initial_username="alice")
    second = migration.run(initial_username="alice")

    with _connect(database_path) as connection:
        diary_count = connection.execute(
            "SELECT COUNT(*) AS row_count FROM nutrition_diary_entries"
        ).fetchone()["row_count"]
        plan_count = connection.execute(
            "SELECT COUNT(*) AS row_count FROM nutrition_plan_current"
        ).fetchone()["row_count"]

    assert second.user_id == first.user_id
    assert second.diary_rows == 1
    assert second.plan_rows == 1
    assert diary_count == 1
    assert plan_count == 1


def _create_single_user_nutrition_schema(database_path) -> None:
    with _connect(database_path) as connection:
        connection.execute("""
            CREATE TABLE nutrition_diary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL UNIQUE,
                training_type TEXT NOT NULL,
                meals_text TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)
        connection.execute(
            """
            INSERT INTO nutrition_diary_entries (
                entry_date,
                training_type,
                meals_text,
                notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-05-12",
                "Easy run",
                "Breakfast: oats.",
                "Good energy.",
                "2026-05-12T10:00:00+00:00",
                "2026-05-12T10:00:00+00:00",
            ),
        )
        connection.execute("""
            CREATE TABLE nutrition_plan_current (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                original_filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                file_sha256 TEXT NOT NULL,
                extracted_text TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)
        connection.execute(
            """
            INSERT INTO nutrition_plan_current (
                id,
                original_filename,
                content_type,
                file_sha256,
                extracted_text,
                uploaded_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "plan.pdf",
                "application/pdf",
                "a" * 64,
                "Nutrition plan text",
                "2026-05-12T10:00:00+00:00",
                "2026-05-12T10:00:00+00:00",
            ),
        )


def _connect(database_path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _table_columns(connection: sqlite3.Connection, table_name: str) -> dict[str, int]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"]: row["notnull"] for row in rows}


def _index_names(connection: sqlite3.Connection, table_name: str) -> set[str]:
    rows = connection.execute(f"PRAGMA index_list({table_name})").fetchall()
    return {row["name"] for row in rows}
