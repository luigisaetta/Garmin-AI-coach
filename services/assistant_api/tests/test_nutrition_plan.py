"""
Author: L. Saetta
Date Modified: 2026-05-12
License: MIT
"""

from __future__ import annotations

from services.assistant_api.nutrition.plan import NutritionPlanService


def test_replace_current_plan_creates_plan(tmp_path) -> None:
    """Verify the nutrition plan service stores extracted PDF text."""
    service = NutritionPlanService(
        tmp_path / "nutrition.db",
        text_extractor=lambda _: "Breakfast plan\nLunch plan",
    )

    plan = service.replace_current_plan(
        original_filename="plan.pdf",
        content_type="application/pdf",
        pdf_bytes=b"%PDF-1.4 fake",
    )

    assert plan.id == 1
    assert plan.original_filename == "plan.pdf"
    assert plan.content_type == "application/pdf"
    assert plan.extracted_text == "Breakfast plan\nLunch plan"
    assert len(plan.file_sha256) == 64
    assert plan.uploaded_at == plan.updated_at


def test_replace_current_plan_overwrites_existing_plan(tmp_path) -> None:
    """Verify only one current nutrition plan is retained."""
    service = NutritionPlanService(
        tmp_path / "nutrition.db",
        text_extractor=lambda pdf_bytes: pdf_bytes.decode("utf-8"),
    )
    original = service.replace_current_plan(
        original_filename="first.pdf",
        content_type="application/pdf",
        pdf_bytes=b"first plan",
    )

    updated = service.replace_current_plan(
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
    service = NutritionPlanService(tmp_path / "nutrition.db")

    assert service.get_current_plan() is None


def test_replace_current_plan_rejects_pdf_without_text(tmp_path) -> None:
    """Verify empty extracted text is not stored as a usable plan."""
    service = NutritionPlanService(
        tmp_path / "nutrition.db",
        text_extractor=lambda _: "   ",
    )

    try:
        service.replace_current_plan(
            original_filename="scan.pdf",
            content_type="application/pdf",
            pdf_bytes=b"%PDF-1.4 fake",
        )
    except ValueError as exc:
        assert "extractable text" in str(exc)
    else:
        raise AssertionError("expected ValueError")
