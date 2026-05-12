"""
Author: L. Saetta
Date Modified: 2026-05-12
License: MIT
"""

from __future__ import annotations

# pylint: disable=duplicate-code

import hashlib
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


@dataclass(frozen=True)
class NutritionPlan:
    """The current stored nutrition plan extracted from an uploaded PDF."""

    id: int
    original_filename: str
    content_type: str
    file_sha256: str
    extracted_text: str
    uploaded_at: datetime
    updated_at: datetime


class NutritionPlanService:
    """Persist a single current nutrition plan in a local SQLite database."""

    CURRENT_PLAN_ID = 1

    def __init__(
        self,
        database_path: str | Path,
        text_extractor: Callable[[bytes], str] | None = None,
    ) -> None:
        self._database_path = Path(database_path)
        self._text_extractor = text_extractor or extract_pdf_text
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def replace_current_plan(
        self,
        *,
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
        with self._connect() as connection:
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
                ON CONFLICT(id) DO UPDATE SET
                    original_filename = excluded.original_filename,
                    content_type = excluded.content_type,
                    file_sha256 = excluded.file_sha256,
                    extracted_text = excluded.extracted_text,
                    uploaded_at = excluded.uploaded_at,
                    updated_at = excluded.updated_at
                """,
                (
                    self.CURRENT_PLAN_ID,
                    original_filename,
                    content_type,
                    file_sha256,
                    extracted_text,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )

        plan = self.get_current_plan()
        if plan is None:
            raise RuntimeError("nutrition plan was not persisted")
        return plan

    def get_current_plan(self) -> NutritionPlan | None:
        """Return the current nutrition plan, when one has been uploaded."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    id,
                    original_filename,
                    content_type,
                    file_sha256,
                    extracted_text,
                    uploaded_at,
                    updated_at
                FROM nutrition_plan_current
                WHERE id = ?
                """,
                (self.CURRENT_PLAN_ID,),
            ).fetchone()

        if row is None:
            return None

        return _plan_from_row(row)

    def _initialize_schema(self) -> None:
        """Create database tables needed by the nutrition plan service."""
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS nutrition_plan_current (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    original_filename TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    file_sha256 TEXT NOT NULL,
                    extracted_text TEXT NOT NULL,
                    uploaded_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)

    def _connect(self) -> sqlite3.Connection:
        """Open a SQLite connection configured for row-based reads."""
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from every page of a PDF document."""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
    except PdfReadError as exc:
        raise ValueError("Uploaded file is not a readable PDF") from exc

    page_text = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(text.strip() for text in page_text if text.strip())


def _plan_from_row(row: sqlite3.Row) -> NutritionPlan:
    """Convert a SQLite row to a typed nutrition plan."""
    return NutritionPlan(
        id=row["id"],
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
