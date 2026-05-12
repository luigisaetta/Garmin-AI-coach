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
