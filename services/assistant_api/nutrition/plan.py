"""
Author: L. Saetta
Date Modified: 2026-05-22
License: MIT
"""

from __future__ import annotations

# pylint: disable=duplicate-code

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from sqlalchemy import select

from services.assistant_api.persistence import Database
from services.assistant_api.persistence.schema import nutrition_plan_current


@dataclass(frozen=True)
class NutritionPlan:  # pylint: disable=too-many-instance-attributes
    """The current stored nutrition plan extracted from an uploaded PDF."""

    id: int
    user_id: int
    original_filename: str
    content_type: str
    file_sha256: str
    extracted_text: str
    uploaded_at: datetime
    updated_at: datetime


class NutritionPlanService:
    """Persist a single current nutrition plan in the assistant database."""

    CURRENT_PLAN_ID = 1

    def __init__(
        self,
        database: Database,
        text_extractor: Callable[[bytes], str] | None = None,
    ) -> None:
        self._database = database
        self._text_extractor = text_extractor or extract_pdf_text

    def replace_current_plan(
        self,
        *,
        user_id: int,
        original_filename: str,
        content_type: str,
        pdf_bytes: bytes,
    ) -> NutritionPlan:
        """Replace the current nutrition plan with text extracted from a PDF."""
        extracted_text = self._text_extractor(pdf_bytes).strip()
        if not extracted_text:
            raise ValueError("PDF does not contain extractable text")

        now = _utc_now()
        file_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        with self._database.engine.begin() as connection:
            existing = (
                connection.execute(
                    select(nutrition_plan_current.c.id).where(
                        nutrition_plan_current.c.user_id == user_id
                    )
                )
                .mappings()
                .fetchone()
            )
            if existing is None:
                connection.execute(
                    nutrition_plan_current.insert().values(
                        user_id=user_id,
                        original_filename=original_filename,
                        content_type=content_type,
                        file_sha256=file_sha256,
                        extracted_text=extracted_text,
                        uploaded_at=now.isoformat(),
                        updated_at=now.isoformat(),
                    )
                )
            else:
                connection.execute(
                    nutrition_plan_current.update()
                    .where(nutrition_plan_current.c.id == existing["id"])
                    .values(
                        original_filename=original_filename,
                        content_type=content_type,
                        file_sha256=file_sha256,
                        extracted_text=extracted_text,
                        uploaded_at=now.isoformat(),
                        updated_at=now.isoformat(),
                    )
                )

        plan = self.get_current_plan(user_id=user_id)
        if plan is None:
            raise RuntimeError("nutrition plan was not persisted")
        return plan

    def get_current_plan(self, *, user_id: int) -> NutritionPlan | None:
        """Return the current nutrition plan, when one has been uploaded."""
        with self._database.engine.connect() as connection:
            row = (
                connection.execute(
                    select(
                        nutrition_plan_current.c.id,
                        nutrition_plan_current.c.user_id,
                        nutrition_plan_current.c.original_filename,
                        nutrition_plan_current.c.content_type,
                        nutrition_plan_current.c.file_sha256,
                        nutrition_plan_current.c.extracted_text,
                        nutrition_plan_current.c.uploaded_at,
                        nutrition_plan_current.c.updated_at,
                    ).where(nutrition_plan_current.c.user_id == user_id)
                )
                .mappings()
                .fetchone()
            )

        if row is None:
            return None

        return _plan_from_row(row)


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from every page of a PDF document."""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except PdfReadError as exc:
        raise ValueError("Uploaded file is not a readable PDF") from exc

    page_text = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(text.strip() for text in page_text if text.strip())


def _plan_from_row(row) -> NutritionPlan:
    """Convert a SQLite row to a typed nutrition plan."""
    return NutritionPlan(
        id=row["id"],
        user_id=row["user_id"],
        original_filename=row["original_filename"],
        content_type=row["content_type"],
        file_sha256=row["file_sha256"],
        extracted_text=row["extracted_text"],
        uploaded_at=datetime.fromisoformat(row["uploaded_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _utc_now() -> datetime:
    """Return the current UTC timestamp without microseconds."""
    return datetime.now(UTC).replace(microsecond=0)
