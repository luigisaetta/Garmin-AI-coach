"""
Author: L. Saetta
Date Modified: 2026-05-22
License: MIT
"""

from __future__ import annotations

# pylint: disable=duplicate-code

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select

from services.assistant_api.persistence import Database
from services.assistant_api.persistence.schema import nutrition_diary_entries


@dataclass(frozen=True)
class NutritionDiaryEntry:  # pylint: disable=too-many-instance-attributes
    """A stored food diary entry for one calendar day."""

    id: int
    user_id: int
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
    """Persist nutrition diary entries in the assistant database."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def upsert_entry(
        self,
        *,
        user_id: int,
        entry_input: NutritionDiaryEntryInput,
    ) -> NutritionDiaryEntry:
        """Create or update the diary entry for one day."""
        now = _utc_now()
        with self._database.engine.begin() as connection:
            existing = (
                connection.execute(
                    select(nutrition_diary_entries.c.id).where(
                        nutrition_diary_entries.c.user_id == user_id,
                        nutrition_diary_entries.c.entry_date
                        == entry_input.entry_date.isoformat(),
                    )
                )
                .mappings()
                .fetchone()
            )
            if existing is None:
                connection.execute(
                    nutrition_diary_entries.insert().values(
                        user_id=user_id,
                        entry_date=entry_input.entry_date.isoformat(),
                        training_type=entry_input.training_type,
                        meals_text=entry_input.meals_text,
                        notes=entry_input.notes,
                        created_at=now.isoformat(),
                        updated_at=now.isoformat(),
                    )
                )
            else:
                connection.execute(
                    nutrition_diary_entries.update()
                    .where(nutrition_diary_entries.c.id == existing["id"])
                    .values(
                        training_type=entry_input.training_type,
                        meals_text=entry_input.meals_text,
                        notes=entry_input.notes,
                        updated_at=now.isoformat(),
                    )
                )

        entry = self.get_entry(user_id=user_id, entry_date=entry_input.entry_date)
        if entry is None:
            raise RuntimeError("nutrition diary entry was not persisted")
        return entry

    def get_entry(
        self, *, user_id: int, entry_date: date
    ) -> NutritionDiaryEntry | None:
        """Return the diary entry for one day, when present."""
        with self._database.engine.connect() as connection:
            row = (
                connection.execute(
                    select(
                        nutrition_diary_entries.c.id,
                        nutrition_diary_entries.c.user_id,
                        nutrition_diary_entries.c.entry_date,
                        nutrition_diary_entries.c.training_type,
                        nutrition_diary_entries.c.meals_text,
                        nutrition_diary_entries.c.notes,
                        nutrition_diary_entries.c.created_at,
                        nutrition_diary_entries.c.updated_at,
                    ).where(
                        nutrition_diary_entries.c.user_id == user_id,
                        nutrition_diary_entries.c.entry_date == entry_date.isoformat(),
                    )
                )
                .mappings()
                .fetchone()
            )

        if row is None:
            return None

        return _entry_from_row(row)

    def list_entries(
        self,
        *,
        user_id: int,
        begin_date: date,
        end_date: date,
    ) -> list[NutritionDiaryEntry]:
        """Return diary entries for an inclusive date range."""
        if begin_date > end_date:
            raise ValueError("begin_date must be before or equal to end_date")

        with self._database.engine.connect() as connection:
            rows = (
                connection.execute(
                    select(
                        nutrition_diary_entries.c.id,
                        nutrition_diary_entries.c.user_id,
                        nutrition_diary_entries.c.entry_date,
                        nutrition_diary_entries.c.training_type,
                        nutrition_diary_entries.c.meals_text,
                        nutrition_diary_entries.c.notes,
                        nutrition_diary_entries.c.created_at,
                        nutrition_diary_entries.c.updated_at,
                    )
                    .where(
                        nutrition_diary_entries.c.user_id == user_id,
                        nutrition_diary_entries.c.entry_date >= begin_date.isoformat(),
                        nutrition_diary_entries.c.entry_date <= end_date.isoformat(),
                    )
                    .order_by(nutrition_diary_entries.c.entry_date.asc())
                )
                .mappings()
                .fetchall()
            )

        return [_entry_from_row(row) for row in rows]


def _entry_from_row(row) -> NutritionDiaryEntry:
    """Convert a database row to a typed diary entry."""
    return NutritionDiaryEntry(
        id=row["id"],
        user_id=row["user_id"],
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
