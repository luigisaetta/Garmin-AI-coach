"""
Author: L. Saetta
Date Modified: 2026-05-14
License: MIT
"""

from __future__ import annotations

# pylint: disable=duplicate-code

from services.assistant_api.nutrition.plan import NutritionPlanService
from services.assistant_api.identity.users import UserRepository


def _create_user(database_path, username: str = "alice") -> int:
    return UserRepository(database_path).ensure_user(username=username).id


def test_replace_current_plan_creates_plan(tmp_path) -> None:
    """Verify the nutrition plan service stores extracted PDF text."""
    database_path = tmp_path / "nutrition.db"
    user_id = _create_user(database_path)
    service = NutritionPlanService(
        database_path,
        text_extractor=lambda _: "Breakfast plan\nLunch plan",
    )

    plan = service.replace_current_plan(
        user_id=user_id,
        original_filename="plan.pdf",
        content_type="application/pdf",
        pdf_bytes=b"%PDF-1.4 fake",
    )

    assert plan.id == 1
    assert plan.user_id == user_id
    assert plan.original_filename == "plan.pdf"
    assert plan.content_type == "application/pdf"
    assert plan.extracted_text == "Breakfast plan\nLunch plan"
    assert len(plan.file_sha256) == 64
    assert plan.uploaded_at == plan.updated_at


def test_replace_current_plan_overwrites_existing_plan(tmp_path) -> None:
    """Verify only one current nutrition plan is retained."""
    database_path = tmp_path / "nutrition.db"
    user_id = _create_user(database_path)
    service = NutritionPlanService(
        database_path,
        text_extractor=lambda pdf_bytes: pdf_bytes.decode("utf-8"),
    )
    original = service.replace_current_plan(
        user_id=user_id,
        original_filename="first.pdf",
        content_type="application/pdf",
        pdf_bytes=b"first plan",
    )

    updated = service.replace_current_plan(
        user_id=user_id,
        original_filename="second.pdf",
        content_type="application/pdf",
        pdf_bytes=b"second plan",
    )

    assert updated.id == original.id
    assert updated.original_filename == "second.pdf"
    assert updated.extracted_text == "second plan"
    assert updated.file_sha256 != original.file_sha256


def test_get_current_plan_returns_none_when_missing(tmp_path) -> None:
    """Verify missing nutrition plans can be distinguished from empty text."""
    database_path = tmp_path / "nutrition.db"
    user_id = _create_user(database_path)
    service = NutritionPlanService(database_path)

    assert service.get_current_plan(user_id=user_id) is None


def test_replace_current_plan_rejects_pdf_without_text(tmp_path) -> None:
    """Verify empty extracted text is not stored as a usable plan."""
    database_path = tmp_path / "nutrition.db"
    user_id = _create_user(database_path)
    service = NutritionPlanService(
        database_path,
        text_extractor=lambda _: "   ",
    )

    try:
        service.replace_current_plan(
            user_id=user_id,
            original_filename="scan.pdf",
            content_type="application/pdf",
            pdf_bytes=b"%PDF-1.4 fake",
        )
    except ValueError as exc:
        assert "extractable text" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_current_plan_is_isolated_by_user_id(tmp_path) -> None:
    """Verify each user has a separate current nutrition plan."""
    database_path = tmp_path / "nutrition.db"
    alice_id = _create_user(database_path, "alice")
    bob_id = _create_user(database_path, "bob")
    service = NutritionPlanService(
        database_path,
        text_extractor=lambda pdf_bytes: pdf_bytes.decode("utf-8"),
    )

    service.replace_current_plan(
        user_id=alice_id,
        original_filename="alice.pdf",
        content_type="application/pdf",
        pdf_bytes=b"Alice plan",
    )
    service.replace_current_plan(
        user_id=bob_id,
        original_filename="bob.pdf",
        content_type="application/pdf",
        pdf_bytes=b"Bob plan",
    )

    alice_plan = service.get_current_plan(user_id=alice_id)
    bob_plan = service.get_current_plan(user_id=bob_id)

    assert alice_plan is not None
    assert bob_plan is not None
    assert alice_plan.original_filename == "alice.pdf"
    assert alice_plan.extracted_text == "Alice plan"
    assert bob_plan.original_filename == "bob.pdf"
    assert bob_plan.extracted_text == "Bob plan"
