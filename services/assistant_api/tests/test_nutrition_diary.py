"""
Author: L. Saetta
Date Modified: 2026-05-12
License: MIT
"""

from __future__ import annotations

from datetime import date

from services.assistant_api.nutrition.diary import (
    NutritionDiaryEntryInput,
    NutritionDiaryService,
)


def test_upsert_creates_diary_entry(tmp_path) -> None:
    """Verify the diary service persists a new daily entry."""
    service = NutritionDiaryService(tmp_path / "nutrition.db")

    entry = service.upsert_entry(
        NutritionDiaryEntryInput(
            entry_date=date(2026, 5, 12),
            training_type="Easy run",
            meals_text="Breakfast: oats. Lunch: rice and chicken.",
            notes="Good energy.",
        )
    )

    assert entry.id > 0
    assert entry.entry_date == date(2026, 5, 12)
    assert entry.training_type == "Easy run"
    assert entry.meals_text == "Breakfast: oats. Lunch: rice and chicken."
    assert entry.notes == "Good energy."
    assert entry.created_at == entry.updated_at


def test_upsert_updates_existing_diary_entry(tmp_path) -> None:
    """Verify one calendar day is updated instead of duplicated."""
    service = NutritionDiaryService(tmp_path / "nutrition.db")
    original = service.upsert_entry(
        NutritionDiaryEntryInput(
            entry_date=date(2026, 5, 12),
            training_type="Rest day",
            meals_text="Breakfast: toast.",
        )
    )

    updated = service.upsert_entry(
        NutritionDiaryEntryInput(
            entry_date=date(2026, 5, 12),
            training_type="Intervals",
            meals_text="Breakfast: oats. Dinner: pasta.",
            notes="Hard session.",
        )
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
    service = NutritionDiaryService(tmp_path / "nutrition.db")

    assert service.get_entry(date(2026, 5, 12)) is None


def test_list_entries_returns_entries_in_inclusive_date_range(tmp_path) -> None:
    """Verify diary entries can be read for an inclusive analysis period."""
    service = NutritionDiaryService(tmp_path / "nutrition.db")
    service.upsert_entry(
        NutritionDiaryEntryInput(
            entry_date=date(2026, 5, 10),
            training_type="Rest",
            meals_text="Outside period.",
        )
    )
    service.upsert_entry(
        NutritionDiaryEntryInput(
            entry_date=date(2026, 5, 12),
            training_type="Run",
            meals_text="Breakfast: oats.",
        )
    )
    service.upsert_entry(
        NutritionDiaryEntryInput(
            entry_date=date(2026, 5, 13),
            training_type="Bike",
            meals_text="Lunch: rice.",
        )
    )

    entries = service.list_entries(
        begin_date=date(2026, 5, 12),
        end_date=date(2026, 5, 13),
    )

    assert [entry.entry_date for entry in entries] == [
        date(2026, 5, 12),
        date(2026, 5, 13),
    ]


def test_list_entries_rejects_invalid_range(tmp_path) -> None:
    """Verify diary range reads reject a start date after the end date."""
    service = NutritionDiaryService(tmp_path / "nutrition.db")

    try:
        service.list_entries(
            begin_date=date(2026, 5, 14),
            end_date=date(2026, 5, 12),
        )
    except ValueError as exc:
        assert "begin_date" in str(exc)
    else:
        raise AssertionError("expected ValueError")
