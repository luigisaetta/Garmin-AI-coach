"""
Author: L. Saetta
Date Modified: 2026-05-22
License: MIT
"""

from __future__ import annotations

from pathlib import Path

from services.assistant_api.persistence import Database


def build_test_database(tmp_path: Path, filename: str = "coach.db") -> Database:
    """Create a fast SQLite database using the production SQLAlchemy schema."""
    return Database.sqlite_for_tests(tmp_path / filename)
