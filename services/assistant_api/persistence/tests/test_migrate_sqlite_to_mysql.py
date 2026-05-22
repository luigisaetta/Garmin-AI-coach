"""
Author: L. Saetta
Date Modified: 2026-05-22
License: MIT
"""

from __future__ import annotations

import sqlite3
from datetime import date

from cryptography.fernet import Fernet

from services.assistant_api.identity.garmin_credentials import (
    GarminCredentialRepository,
)
from services.assistant_api.identity.users import UserRepository
from services.assistant_api.nutrition.diary import NutritionDiaryService
from services.assistant_api.nutrition.plan import NutritionPlanService
from services.assistant_api.persistence.migrate_sqlite_to_mysql import (
    SqliteToMysqlMigration,
)
from services.assistant_api.tests.database import build_test_database


def test_migration_copies_multi_user_sqlite_rows_to_target_database(tmp_path) -> None:
    """Verify the migration preserves user-owned SQLite records."""
    source_path = tmp_path / "legacy.db"
    _create_multi_user_source(source_path)
    target_database = build_test_database(tmp_path, "target.db")

    summary = SqliteToMysqlMigration(source_path, target_database).run()

    assert summary.users == 1
    assert summary.garmin_credentials == 1
    assert summary.diary_entries == 1
    assert summary.nutrition_plans == 1
    user = UserRepository(target_database).get_by_username("alice")
    assert user is not None
    diary_entry = NutritionDiaryService(target_database).get_entry(
        user_id=user.id,
        entry_date=date(2026, 5, 12),
    )
    assert diary_entry is not None
    assert diary_entry.meals_text == "Breakfast: oats."
    plan = NutritionPlanService(target_database).get_current_plan(user_id=user.id)
    assert plan is not None
    assert plan.extracted_text == "Plan text"
    credentials = GarminCredentialRepository(
        target_database,
        encryption_key=_fernet_key(),
    ).get_status(user_id=user.id)
    assert credentials.configured is True


def test_migration_assigns_legacy_single_user_rows(tmp_path) -> None:
    """Verify old nutrition tables without user_id can be assigned to one user."""
    source_path = tmp_path / "single_user.db"
    _create_single_user_source(source_path)
    target_database = build_test_database(tmp_path, "target.db")

    summary = SqliteToMysqlMigration(source_path, target_database).run(
        initial_username="Alice"
    )

    assert summary.users == 1
    assert summary.diary_entries == 1
    user = UserRepository(target_database).get_by_username("alice")
    assert user is not None
    entry = NutritionDiaryService(target_database).get_entry(
        user_id=user.id,
        entry_date=date(2026, 5, 12),
    )
    assert entry is not None
    assert entry.training_type == "Run"


def _create_multi_user_source(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE garmin_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                garmin_username TEXT NOT NULL,
                encrypted_password TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE nutrition_diary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                entry_date TEXT NOT NULL,
                training_type TEXT NOT NULL,
                meals_text TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE nutrition_plan_current (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                original_filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                file_sha256 TEXT NOT NULL,
                extracted_text TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
        connection.execute("""
            INSERT INTO users
            VALUES (1, 'alice', 'Alice', 1, '2026-05-12T00:00:00+00:00',
                    '2026-05-12T00:00:00+00:00')
            """)
        connection.execute("""
            INSERT INTO garmin_credentials
            VALUES (1, 1, 'alice@example.com', 'encrypted',
                    '2026-05-12T00:00:00+00:00',
                    '2026-05-12T00:00:00+00:00')
            """)
        connection.execute("""
            INSERT INTO nutrition_diary_entries
            VALUES (1, 1, '2026-05-12', 'Run', 'Breakfast: oats.', '',
                    '2026-05-12T00:00:00+00:00',
                    '2026-05-12T00:00:00+00:00')
            """)
        connection.execute("""
            INSERT INTO nutrition_plan_current
            VALUES (1, 1, 'plan.pdf', 'application/pdf', 'abc', 'Plan text',
                    '2026-05-12T00:00:00+00:00',
                    '2026-05-12T00:00:00+00:00')
            """)


def _create_single_user_source(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE nutrition_diary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_date TEXT NOT NULL,
                training_type TEXT NOT NULL,
                meals_text TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
        connection.execute("""
            INSERT INTO nutrition_diary_entries
            VALUES (1, '2026-05-12', 'Run', 'Breakfast: oats.', '',
                    '2026-05-12T00:00:00+00:00',
                    '2026-05-12T00:00:00+00:00')
            """)


def _fernet_key() -> bytes:
    return Fernet.generate_key()
