"""
Author: L. Saetta
Date Modified: 2026-07-16
License: MIT
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from services.assistant_api.goals.race_goals import (
    RaceGoalInput,
    RaceGoalSegmentInput,
    RaceGoalService,
)
from services.assistant_api.identity.users import UserRepository
from services.assistant_api.tests.database import build_test_database


def _future_date(days: int) -> date:
    return date.today() + timedelta(days=days)


def _single_goal_input(*, priority: str = "A") -> RaceGoalInput:
    return RaceGoalInput(
        title="Autumn Marathon",
        event_date=_future_date(90),
        sport="running",
        distance_meters=42195,
        multisport_format=None,
        priority=priority,
        goal_type="finish_time",
        target_duration_seconds=13_500,
        notes="Main goal",
        status="upcoming",
    )


def _multisport_goal_input() -> RaceGoalInput:
    return RaceGoalInput(
        title="Coastal 70.3",
        event_date=_future_date(60),
        sport="multisport",
        distance_meters=None,
        multisport_format="half_iron_distance",
        priority="A",
        goal_type="completion",
        target_duration_seconds=None,
        notes="",
        status="upcoming",
        segments=(
            RaceGoalSegmentInput(sport="swimming", distance_meters=1900),
            RaceGoalSegmentInput(sport="cycling", distance_meters=90000),
            RaceGoalSegmentInput(sport="running", distance_meters=21100),
        ),
    )


def test_create_multisport_goal_persists_ordered_segments(tmp_path) -> None:
    """Verify a multisport race goal preserves user-scoped segment order."""
    database = build_test_database(tmp_path, "goals.db")
    user_id = UserRepository(database).ensure_user(username="alice").id
    service = RaceGoalService(database)

    goal = service.create_goal(user_id=user_id, goal_input=_multisport_goal_input())

    assert goal.id > 0
    assert goal.user_id == user_id
    assert goal.sport == "multisport"
    assert [segment.sport for segment in goal.segments] == [
        "swimming",
        "cycling",
        "running",
    ]
    assert [segment.distance_meters for segment in goal.segments] == [
        1900,
        90000,
        21100,
    ]


def test_goals_are_isolated_by_user_id(tmp_path) -> None:
    """Verify one athlete cannot read another athlete's race goal."""
    database = build_test_database(tmp_path, "goals.db")
    users = UserRepository(database)
    alice_id = users.ensure_user(username="alice").id
    bob_id = users.ensure_user(username="bob").id
    service = RaceGoalService(database)
    goal = service.create_goal(user_id=alice_id, goal_input=_single_goal_input())

    assert service.get_goal(user_id=bob_id, goal_id=goal.id) is None
    assert service.list_goals(user_id=bob_id, status="upcoming") == []


def test_active_goal_prefers_nearest_a_priority_goal(tmp_path) -> None:
    """Verify active-goal selection follows priority before date ordering."""
    database = build_test_database(tmp_path, "goals.db")
    user_id = UserRepository(database).ensure_user(username="alice").id
    service = RaceGoalService(database)
    b_goal = service.create_goal(
        user_id=user_id,
        goal_input=RaceGoalInput(
            **{
                **_single_goal_input(priority="B").__dict__,
                "event_date": _future_date(20),
            }
        ),
    )
    a_goal = service.create_goal(user_id=user_id, goal_input=_single_goal_input())

    assert service.get_active_goal(user_id=user_id) == a_goal
    assert service.get_active_goal(user_id=user_id, sport="running") == a_goal
    assert b_goal.priority == "B"


def test_multisport_goal_requires_at_least_two_segments(tmp_path) -> None:
    """Verify invalid multisport goals fail before being persisted."""
    database = build_test_database(tmp_path, "goals.db")
    user_id = UserRepository(database).ensure_user(username="alice").id
    service = RaceGoalService(database)
    invalid = RaceGoalInput(
        **{
            **_multisport_goal_input().__dict__,
            "segments": (RaceGoalSegmentInput(sport="swimming"),),
        }
    )

    with pytest.raises(ValueError, match="at least two"):
        service.create_goal(user_id=user_id, goal_input=invalid)
