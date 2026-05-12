"""
Author: L. Saetta
Date Modified: 2026-05-12
License: MIT
"""

from __future__ import annotations

# pylint: disable=duplicate-code

import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path


@dataclass(frozen=True)
class NutritionDiaryEntry:
    """A stored food diary entry for one calendar day."""

    id: int
    entry_date: date
    training_type: str
    meals_text: str
    notes: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class NutritionDiaryEntryInput:
    """Input accepted when creating or updating one food diary day."""

    entry_date: date
    training_type: str
    meals_text: str
    notes: str = ""


class NutritionDiaryService:
    """Persist nutrition diary entries in a local SQLite database."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def upsert_entry(
        self,
        entry_input: NutritionDiaryEntryInput,
    ) -> NutritionDiaryEntry:
        """Create or update the diary entry for one day."""
        now = _utc_now()
        with self._connect() as connection:
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
                ON CONFLICT(entry_date) DO UPDATE SET
                    training_type = excluded.training_type,
                    meals_text = excluded.meals_text,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    entry_input.entry_date.isoformat(),
                    entry_input.training_type,
                    entry_input.meals_text,
                    entry_input.notes,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )

        entry = self.get_entry(entry_input.entry_date)
        if entry is None:
            raise RuntimeError("nutrition diary entry was not persisted")
        return entry

    def get_entry(self, entry_date: date) -> NutritionDiaryEntry | None:
        """Return the diary entry for one day, when present."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    entry_date,
                    training_type,
                    meals_text,
                    notes,
                    created_at,
                    updated_at
                FROM nutrition_diary_entries
                WHERE entry_date = ?
                """,
                (entry_date.isoformat(),),
            ).fetchone()

        if row is None:
            return None

        return _entry_from_row(row)

    def list_entries(
        self,
        *,
        begin_date: date,
        end_date: date,
    ) -> list[NutritionDiaryEntry]:
        """Return diary entries for an inclusive date range."""
        if begin_date > end_date:
            raise ValueError("begin_date must be before or equal to end_date")

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    entry_date,
                    training_type,
                    meals_text,
                    notes,
                    created_at,
                    updated_at
                FROM nutrition_diary_entries
                WHERE entry_date >= ? AND entry_date <= ?
                ORDER BY entry_date ASC
                """,
                (begin_date.isoformat(), end_date.isoformat()),
            ).fetchall()

        return [_entry_from_row(row) for row in rows]

    def _initialize_schema(self) -> None:
        """Create database tables needed by the nutrition diary service."""
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS nutrition_diary_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_date TEXT NOT NULL UNIQUE,
                    training_type TEXT NOT NULL,
                    meals_text TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection configured for row-based reads."""
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def _entry_from_row(row: sqlite3.Row) -> NutritionDiaryEntry:
    """Convert a SQLite row to a typed diary entry."""
    return NutritionDiaryEntry(
        id=row["id"],
        entry_date=date.fromisoformat(row["entry_date"]),
        training_type=row["training_type"],
        meals_text=row["meals_text"],
        notes=row["notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _utc_now() -> datetime:
    """Return the current UTC timestamp without microseconds."""
    return datetime.now(UTC).replace(microsecond=0)
