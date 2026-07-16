"""
Author: L. Saetta
Date Modified: 2026-07-16
License: MIT
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

from sqlalchemy import delete, select

from services.assistant_api.persistence import Database
from services.assistant_api.persistence.schema import race_goal_segments, race_goals

GoalSport = Literal["running", "cycling", "swimming", "multisport"]
GoalPriority = Literal["A", "B", "C"]
GoalType = Literal["completion", "finish_time"]
GoalStatus = Literal["upcoming", "completed", "cancelled"]
SegmentSport = Literal["swimming", "cycling", "running"]

MULTISPORT_FORMATS = frozenset(
    {
        "triathlon_sprint",
        "triathlon_olympic",
        "half_iron_distance",
        "full_iron_distance",
        "other_multisport",
    }
)


@dataclass(frozen=True)
class RaceGoalSegmentInput:
    """One ordered discipline belonging to a multisport goal."""

    sport: SegmentSport
    distance_meters: int | None = None


@dataclass(frozen=True)
class RaceGoalInput:  # pylint: disable=too-many-instance-attributes
    """Validated business input for creating or replacing a race goal."""

    title: str
    event_date: date
    sport: GoalSport
    distance_meters: int | None
    multisport_format: str | None
    priority: GoalPriority
    goal_type: GoalType
    target_duration_seconds: int | None
    notes: str
    status: GoalStatus
    segments: tuple[RaceGoalSegmentInput, ...] = ()


@dataclass(frozen=True)
class RaceGoalSegment:
    """A stored ordered multisport discipline."""

    sequence: int
    sport: SegmentSport
    distance_meters: int | None


@dataclass(frozen=True)
class RaceGoal:  # pylint: disable=too-many-instance-attributes
    """A user-scoped race goal stored by the assistant backend."""

    id: int
    user_id: int
    title: str
    event_date: date
    sport: GoalSport
    distance_meters: int | None
    multisport_format: str | None
    priority: GoalPriority
    goal_type: GoalType
    target_duration_seconds: int | None
    notes: str
    status: GoalStatus
    segments: tuple[RaceGoalSegment, ...]
    created_at: datetime
    updated_at: datetime


class RaceGoalService:
    """Persist and select race goals without crossing user ownership boundaries."""

    def __init__(self, database: Database) -> None:
        self._database = database

    def create_goal(self, *, user_id: int, goal_input: RaceGoalInput) -> RaceGoal:
        """Create one user-owned race goal and its ordered segments."""
        validated = _validate_goal_input(goal_input)
        now = _utc_now().isoformat()
        with self._database.engine.begin() as connection:
            result = connection.execute(
                race_goals.insert().values(
                    user_id=user_id,
                    title=validated.title,
                    event_date=validated.event_date.isoformat(),
                    sport=validated.sport,
                    distance_meters=validated.distance_meters,
                    multisport_format=validated.multisport_format,
                    priority=validated.priority,
                    goal_type=validated.goal_type,
                    target_duration_seconds=validated.target_duration_seconds,
                    notes=validated.notes,
                    status=validated.status,
                    created_at=now,
                    updated_at=now,
                )
            )
            goal_id = int(result.inserted_primary_key[0])
            self._replace_segments(
                connection=connection,
                goal_id=goal_id,
                segments=validated.segments,
            )
        goal = self.get_goal(user_id=user_id, goal_id=goal_id)
        if goal is None:
            raise RuntimeError("race goal was not persisted")
        return goal

    def update_goal(
        self,
        *,
        user_id: int,
        goal_id: int,
        goal_input: RaceGoalInput,
    ) -> RaceGoal | None:
        """Replace mutable data for one user-owned race goal."""
        validated = _validate_goal_input(goal_input)
        with self._database.engine.begin() as connection:
            existing = (
                connection.execute(
                    select(race_goals.c.id).where(
                        race_goals.c.id == goal_id,
                        race_goals.c.user_id == user_id,
                    )
                )
                .mappings()
                .fetchone()
            )
            if existing is None:
                return None
            connection.execute(
                race_goals.update()
                .where(race_goals.c.id == goal_id, race_goals.c.user_id == user_id)
                .values(
                    title=validated.title,
                    event_date=validated.event_date.isoformat(),
                    sport=validated.sport,
                    distance_meters=validated.distance_meters,
                    multisport_format=validated.multisport_format,
                    priority=validated.priority,
                    goal_type=validated.goal_type,
                    target_duration_seconds=validated.target_duration_seconds,
                    notes=validated.notes,
                    status=validated.status,
                    updated_at=_utc_now().isoformat(),
                )
            )
            self._replace_segments(
                connection=connection,
                goal_id=goal_id,
                segments=validated.segments,
            )
        return self.get_goal(user_id=user_id, goal_id=goal_id)

    def get_goal(self, *, user_id: int, goal_id: int) -> RaceGoal | None:
        """Return one goal only when it belongs to the requested user."""
        with self._database.engine.connect() as connection:
            row = (
                connection.execute(
                    select(race_goals).where(
                        race_goals.c.id == goal_id,
                        race_goals.c.user_id == user_id,
                    )
                )
                .mappings()
                .fetchone()
            )
            if row is None:
                return None
            segments = self._segments_for_goal(connection=connection, goal_id=goal_id)
        return _goal_from_row(row=row, segments=segments)

    def list_goals(self, *, user_id: int, status: str) -> list[RaceGoal]:
        """Return upcoming or historical goals ordered for athlete display."""
        if status not in {"upcoming", "history"}:
            raise ValueError("status must be 'upcoming' or 'history'")
        statement = select(race_goals).where(race_goals.c.user_id == user_id)
        if status == "upcoming":
            statement = statement.where(race_goals.c.status == "upcoming").order_by(
                race_goals.c.event_date.asc()
            )
        else:
            statement = statement.where(race_goals.c.status != "upcoming").order_by(
                race_goals.c.event_date.desc()
            )
        with self._database.engine.connect() as connection:
            rows = connection.execute(statement).mappings().fetchall()
            return [
                _goal_from_row(
                    row=row,
                    segments=self._segments_for_goal(
                        connection=connection, goal_id=row["id"]
                    ),
                )
                for row in rows
            ]

    def get_active_goal(
        self, *, user_id: int, sport: GoalSport | None = None
    ) -> RaceGoal | None:
        """Select the nearest upcoming A goal, then B or C, for an athlete."""
        goals = self.list_goals(user_id=user_id, status="upcoming")
        applicable = [goal for goal in goals if sport is None or goal.sport == sport]
        for priority in ("A", "B", "C"):
            selected = next(
                (goal for goal in applicable if goal.priority == priority), None
            )
            if selected is not None:
                return selected
        return None

    def _replace_segments(
        self, *, connection, goal_id: int, segments: tuple[RaceGoalSegmentInput, ...]
    ) -> None:
        connection.execute(
            delete(race_goal_segments).where(
                race_goal_segments.c.race_goal_id == goal_id
            )
        )
        if segments:
            connection.execute(
                race_goal_segments.insert(),
                [
                    {
                        "race_goal_id": goal_id,
                        "sequence": index,
                        "sport": segment.sport,
                        "distance_meters": segment.distance_meters,
                    }
                    for index, segment in enumerate(segments, start=1)
                ],
            )

    @staticmethod
    def _segments_for_goal(*, connection, goal_id: int) -> tuple[RaceGoalSegment, ...]:
        rows = (
            connection.execute(
                select(race_goal_segments)
                .where(race_goal_segments.c.race_goal_id == goal_id)
                .order_by(race_goal_segments.c.sequence.asc())
            )
            .mappings()
            .fetchall()
        )
        return tuple(
            RaceGoalSegment(
                sequence=row["sequence"],
                sport=row["sport"],
                distance_meters=row["distance_meters"],
            )
            for row in rows
        )


def _validate_goal_input(goal_input: RaceGoalInput) -> RaceGoalInput:
    title = goal_input.title.strip()
    if not title:
        raise ValueError("title is required")
    if goal_input.status == "upcoming" and goal_input.event_date < date.today():
        raise ValueError("upcoming goals cannot have an event date in the past")
    if goal_input.distance_meters is not None and goal_input.distance_meters <= 0:
        raise ValueError("distance_meters must be positive when provided")
    if goal_input.goal_type == "finish_time":
        if (
            goal_input.target_duration_seconds is None
            or goal_input.target_duration_seconds <= 0
        ):
            raise ValueError(
                "finish_time goals require a positive target_duration_seconds"
            )
    elif goal_input.target_duration_seconds is not None:
        raise ValueError("completion goals must not include target_duration_seconds")

    if goal_input.sport == "multisport":
        if goal_input.multisport_format not in MULTISPORT_FORMATS:
            raise ValueError("multisport goals require a supported multisport_format")
        if len(goal_input.segments) < 2:
            raise ValueError("multisport goals require at least two segments")
        for segment in goal_input.segments:
            if segment.distance_meters is not None and segment.distance_meters <= 0:
                raise ValueError(
                    "segment distance_meters must be positive when provided"
                )
    elif goal_input.multisport_format is not None or goal_input.segments:
        raise ValueError("single-sport goals must not include multisport data")

    return RaceGoalInput(
        title=title,
        event_date=goal_input.event_date,
        sport=goal_input.sport,
        distance_meters=goal_input.distance_meters,
        multisport_format=goal_input.multisport_format,
        priority=goal_input.priority,
        goal_type=goal_input.goal_type,
        target_duration_seconds=goal_input.target_duration_seconds,
        notes=goal_input.notes.strip(),
        status=goal_input.status,
        segments=goal_input.segments,
    )


def _goal_from_row(*, row, segments: tuple[RaceGoalSegment, ...]) -> RaceGoal:
    return RaceGoal(
        id=row["id"],
        user_id=row["user_id"],
        title=row["title"],
        event_date=date.fromisoformat(row["event_date"]),
        sport=row["sport"],
        distance_meters=row["distance_meters"],
        multisport_format=row["multisport_format"],
        priority=row["priority"],
        goal_type=row["goal_type"],
        target_duration_seconds=row["target_duration_seconds"],
        notes=row["notes"],
        status=row["status"],
        segments=segments,
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)
