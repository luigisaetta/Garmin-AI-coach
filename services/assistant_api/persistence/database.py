"""
Author: L. Saetta
Date Modified: 2026-05-22
License: MIT
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL

from services.assistant_api.persistence.schema import metadata


@dataclass(frozen=True)
class DatabaseSettings:
    """Database connection settings for the assistant backend."""

    host: str
    port: int
    database: str
    username: str
    password: str
    connect_timeout_seconds: int = 10


class Database:
    """Small SQLAlchemy Core wrapper used by persistence repositories."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine
        self.initialize_schema()

    @classmethod
    def from_url(cls, database_url: str) -> "Database":
        """Create a database wrapper from a SQLAlchemy URL."""
        return cls(
            create_engine(
                database_url,
                future=True,
                pool_pre_ping=True,
            )
        )

    @classmethod
    def from_settings(cls, settings: DatabaseSettings) -> "Database":
        """Create a MySQL database wrapper from structured settings."""
        return cls.from_url(build_mysql_url(settings))

    @classmethod
    def sqlite_for_tests(cls, database_path: str | Path) -> "Database":
        """Create a SQLite-backed database for fast local unit tests only."""
        path = Path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        return cls.from_url(f"sqlite:///{path}")

    def initialize_schema(self) -> None:
        """Create all assistant database tables when they do not exist."""
        metadata.create_all(self.engine)


def load_database_settings() -> DatabaseSettings:
    """Load MySQL database settings from environment variables."""
    return DatabaseSettings(
        host=os.getenv("MYSQL_HOST", "mysql"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        database=os.getenv("MYSQL_DATABASE", "garmin_ai_coach"),
        username=os.getenv("MYSQL_USER", "garmin_coach"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        connect_timeout_seconds=int(os.getenv("MYSQL_CONNECT_TIMEOUT_SECONDS", "10")),
    )


def build_mysql_url(settings: DatabaseSettings) -> str:
    """Build a SQLAlchemy URL for the MySQL runtime database."""
    url = URL.create(
        "mysql+pymysql",
        username=settings.username,
        password=settings.password,
        host=settings.host,
        port=settings.port,
        database=settings.database,
        query={
            "charset": "utf8mb4",
            "connect_timeout": str(settings.connect_timeout_seconds),
        },
    )
    return url.render_as_string(hide_password=False)
