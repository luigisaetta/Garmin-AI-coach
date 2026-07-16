"""
Author: L. Saetta
Date Modified: 2026-07-16
License: MIT
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import LONGTEXT

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("username", String(255), nullable=False, unique=True),
    Column("display_name", String(255), nullable=False),
    Column("is_active", Boolean, nullable=False, default=True),
    Column("created_at", String(32), nullable=False),
    Column("updated_at", String(32), nullable=False),
    Index("idx_users_username", "username"),
)

garmin_credentials = Table(
    "garmin_credentials",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False, unique=True),
    Column("garmin_username", String(255), nullable=False),
    Column("encrypted_password", Text, nullable=False),
    Column("created_at", String(32), nullable=False),
    Column("updated_at", String(32), nullable=False),
    Index("idx_garmin_credentials_user", "user_id", unique=True),
)

nutrition_diary_entries = Table(
    "nutrition_diary_entries",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("entry_date", String(10), nullable=False),
    Column("training_type", String(255), nullable=False),
    Column("meals_text", Text, nullable=False),
    Column("notes", Text, nullable=False, default=""),
    Column("created_at", String(32), nullable=False),
    Column("updated_at", String(32), nullable=False),
    UniqueConstraint(
        "user_id",
        "entry_date",
        name="idx_nutrition_diary_user_entry_date",
    ),
    Index("idx_nutrition_diary_user_date_range", "user_id", "entry_date"),
)

nutrition_plan_current = Table(
    "nutrition_plan_current",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False, unique=True),
    Column("original_filename", String(1024), nullable=False),
    Column("content_type", String(255), nullable=False),
    Column("file_sha256", String(64), nullable=False),
    Column("extracted_text", Text().with_variant(LONGTEXT, "mysql"), nullable=False),
    Column("uploaded_at", String(32), nullable=False),
    Column("updated_at", String(32), nullable=False),
    Index("idx_nutrition_plan_current_user", "user_id", unique=True),
)

race_goals = Table(
    "race_goals",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id"), nullable=False),
    Column("title", String(255), nullable=False),
    Column("event_date", String(10), nullable=False),
    Column("sport", String(32), nullable=False),
    Column("distance_meters", Integer, nullable=True),
    Column("multisport_format", String(64), nullable=True),
    Column("priority", String(1), nullable=False),
    Column("goal_type", String(32), nullable=False),
    Column("target_duration_seconds", Integer, nullable=True),
    Column("notes", Text, nullable=False, default=""),
    Column("status", String(16), nullable=False),
    Column("created_at", String(32), nullable=False),
    Column("updated_at", String(32), nullable=False),
    Index("idx_race_goals_user_event_date", "user_id", "event_date"),
    Index("idx_race_goals_user_status", "user_id", "status"),
)

race_goal_segments = Table(
    "race_goal_segments",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("race_goal_id", Integer, ForeignKey("race_goals.id"), nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("sport", String(32), nullable=False),
    Column("distance_meters", Integer, nullable=True),
    UniqueConstraint("race_goal_id", "sequence", name="idx_race_goal_segments_order"),
    Index("idx_race_goal_segments_goal", "race_goal_id"),
)
