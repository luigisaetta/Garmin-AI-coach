"""
Author: L. Saetta
Date Modified: 2026-05-22
License: MIT
"""

from __future__ import annotations

from datetime import date

from services.assistant_api.nutrition.diary import (
    NutritionDiaryEntryInput,
    NutritionDiaryService,
)
from services.assistant_api.identity.users import UserRepository
from services.assistant_api.persistence import Database
from services.assistant_api.tests.database import build_test_database


def _create_user(database: Database, username: str = "alice") -> int:
    return UserRepository(database).ensure_user(username=username).id


def test_upsert_creates_diary_entry(tmp_path) -> None:
    """Verify the diary service persists a new daily entry."""
    database = build_test_database(tmp_path, "nutrition.db")
    user_id = _create_user(database)
    service = NutritionDiaryService(database)

    entry = service.upsert_entry(
        user_id=user_id,
        entry_input=NutritionDiaryEntryInput(
            entry_date=date(2026, 5, 12),
            training_type="Easy run",
            meals_text="Breakfast: oats. Lunch: rice and chicken.",
            notes="Good energy.",
        ),
    )

    assert entry.id > 0
    assert entry.user_id == user_id
    assert entry.entry_date == date(2026, 5, 12)
    assert entry.training_type == "Easy run"
    assert entry.meals_text == "Breakfast: oats. Lunch: rice and chicken."
    assert entry.notes == "Good energy."
    assert entry.created_at == entry.updated_at


def test_upsert_updates_existing_diary_entry(tmp_path) -> None:
    """Verify one calendar day is updated instead of duplicated."""
    database = build_test_database(tmp_path, "nutrition.db")
    user_id = _create_user(database)
    service = NutritionDiaryService(database)
    original = service.upsert_entry(
        user_id=user_id,
        entry_input=NutritionDiaryEntryInput(
            entry_date=date(2026, 5, 12),
            training_type="Rest day",
            meals_text="Breakfast: toast.",
        ),
    )

    updated = service.upsert_entry(
        user_id=user_id,
        entry_input=NutritionDiaryEntryInput(
            entry_date=date(2026, 5, 12),
            training_type="Intervals",
            meals_text="Breakfast: oats. Dinner: pasta.",
            notes="Hard session.",
        ),
    )

    assert updated.id == original.id
    assert updated.entry_date == original.entry_date
    assert updated.training_type == "Intervals"
    assert updated.meals_text == "Breakfast: oats. Dinner: pasta."
    assert updated.notes == "Hard session."
    assert updated.created_at == original.created_at
    assert updated.updated_at >= original.updated_at


def test_get_entry_returns_none_for_missing_day(tmp_path) -> None:
    """Verify missing days can be distinguished from empty entries."""
    database = build_test_database(tmp_path, "nutrition.db")
    user_id = _create_user(database)
    service = NutritionDiaryService(database)

    assert service.get_entry(user_id=user_id, entry_date=date(2026, 5, 12)) is None


def test_list_entries_returns_entries_in_inclusive_date_range(tmp_path) -> None:
    """Verify diary entries can be read for an inclusive analysis period."""
    database = build_test_database(tmp_path, "nutrition.db")
    user_id = _create_user(database)
    service = NutritionDiaryService(database)
    service.upsert_entry(
        user_id=user_id,
        entry_input=NutritionDiaryEntryInput(
            entry_date=date(2026, 5, 10),
            training_type="Rest",
            meals_text="Outside period.",
        ),
    )
    service.upsert_entry(
        user_id=user_id,
        entry_input=NutritionDiaryEntryInput(
            entry_date=date(2026, 5, 12),
            training_type="Run",
            meals_text="Breakfast: oats.",
        ),
    )
    service.upsert_entry(
        user_id=user_id,
        entry_input=NutritionDiaryEntryInput(
            entry_date=date(2026, 5, 13),
            training_type="Bike",
            meals_text="Lunch: rice.",
        ),
    )

    entries = service.list_entries(
        user_id=user_id,
        begin_date=date(2026, 5, 12),
        end_date=date(2026, 5, 13),
    )

    assert [entry.entry_date for entry in entries] == [
        date(2026, 5, 12),
        date(2026, 5, 13),
    ]


def test_list_entries_rejects_invalid_range(tmp_path) -> None:
    """Verify diary range reads reject a start date after the end date."""
    database = build_test_database(tmp_path, "nutrition.db")
    user_id = _create_user(database)
    service = NutritionDiaryService(database)

    try:
        service.list_entries(
            user_id=user_id,
            begin_date=date(2026, 5, 14),
            end_date=date(2026, 5, 12),
        )
    except ValueError as exc:
        assert "begin_date" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_entries_are_isolated_by_user_id(tmp_path) -> None:
    """Verify users can keep distinct diary entries on the same date."""
    database = build_test_database(tmp_path, "nutrition.db")
    alice_id = _create_user(database, "alice")
    bob_id = _create_user(database, "bob")
    service = NutritionDiaryService(database)

    service.upsert_entry(
        user_id=alice_id,
        entry_input=NutritionDiaryEntryInput(
            entry_date=date(2026, 5, 12),
            training_type="Run",
            meals_text="Alice meals.",
        ),
    )
    service.upsert_entry(
        user_id=bob_id,
        entry_input=NutritionDiaryEntryInput(
            entry_date=date(2026, 5, 12),
            training_type="Ride",
            meals_text="Bob meals.",
        ),
    )

    alice_entry = service.get_entry(user_id=alice_id, entry_date=date(2026, 5, 12))
    bob_entry = service.get_entry(user_id=bob_id, entry_date=date(2026, 5, 12))

    assert alice_entry is not None
    assert bob_entry is not None
    assert alice_entry.meals_text == "Alice meals."
    assert bob_entry.meals_text == "Bob meals."
