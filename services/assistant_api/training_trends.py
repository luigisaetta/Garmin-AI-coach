"""
Author: L. Saetta
Date Modified: 2026-07-10
License: MIT
"""

from __future__ import annotations

# pylint: disable=duplicate-code

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import math
from typing import Any

from services.assistant_api.training_metrics import (
    SPORT_LABELS,
    Sport,
    _number,  # pylint: disable=protected-access
    _optional_number,  # pylint: disable=protected-access
    _sport_from_activity,  # pylint: disable=protected-access
)

MIN_TREND_WEEKS = 4
MAX_TREND_WEEKS = 26
DEFAULT_TREND_WEEKS = 12


@dataclass(frozen=True)
class WeeklySportTrend:
    """Sport-specific training trend values for one ISO week."""

    sport: Sport
    label: str
    hours: float
    training_load: float
    activity_count: int


@dataclass(frozen=True)
class WeeklyTrainingTrend:  # pylint: disable=too-many-instance-attributes
    """Aggregate training trend values for one ISO week."""

    week_start: date
    week_end: date
    iso_year: int
    iso_week: int
    label: str
    total_hours: float
    total_training_load: float
    activity_count: int
    sports: list[WeeklySportTrend]
    rolling_4_week_average_load: float | None
    previous_week_delta_percent: float | None
    acute_chronic_load_ratio: float | None


@dataclass(frozen=True)
class TrainingTrendsSummary:
    """Training trends for a fixed number of recent ISO weeks."""

    begin_date: date
    end_date: date
    weeks_requested: int
    weeks: list[WeeklyTrainingTrend]


class TrainingTrendsService:  # pylint: disable=too-few-public-methods
    """Compute weekly training trends from Garmin activity payloads."""

    async def summarize(
        self,
        *,
        training_client: Any,
        user_id: int,
        weeks: int = DEFAULT_TREND_WEEKS,
        end_date: date | None = None,
    ) -> TrainingTrendsSummary:
        """Return weekly training trends for the requested recent period."""
        validated_weeks = validate_weeks(weeks)
        effective_end_date = end_date or date.today()
        week_start = start_of_iso_week(effective_end_date) - timedelta(
            days=7 * (validated_weeks - 1)
        )
        week_end = start_of_iso_week(effective_end_date) + timedelta(days=6)

        activities = await training_client.list_activities(
            user_id=user_id,
            begin_date=week_start.isoformat(),
            end_date=week_end.isoformat(),
        )
        return summarize_training_trends(
            activities=activities,
            begin_date=week_start,
            end_date=week_end,
            weeks=validated_weeks,
        )


def summarize_training_trends(  # pylint: disable=too-many-locals
    *,
    activities: list[dict[str, Any]],
    begin_date: date,
    end_date: date,
    weeks: int,
) -> TrainingTrendsSummary:
    """Aggregate raw Garmin activities into weekly trend values."""
    validated_weeks = validate_weeks(weeks)
    normalized_begin_date = start_of_iso_week(begin_date)
    expected_end_date = normalized_begin_date + timedelta(
        days=(validated_weeks * 7) - 1
    )
    if end_date < expected_end_date:
        raise ValueError("end_date must cover the requested number of ISO weeks.")

    week_totals = {
        week_start: _empty_week_totals()
        for week_start in _week_starts(normalized_begin_date, validated_weeks)
    }

    for activity in activities:
        activity_date = _activity_date(activity)
        if activity_date is None:
            continue

        week_start = start_of_iso_week(activity_date)
        if week_start not in week_totals:
            continue

        sport = _sport_from_activity(activity)
        if sport is None:
            continue

        duration_seconds = _number(activity.get("duration"))
        training_load = _optional_number(activity.get("activityTrainingLoad")) or 0.0
        sport_totals = week_totals[week_start]["sports"][sport]
        sport_totals["activity_count"] += 1
        sport_totals["duration_seconds"] += duration_seconds
        sport_totals["training_load"] += training_load

    weekly_trends = _build_weekly_trends(week_totals)
    return TrainingTrendsSummary(
        begin_date=normalized_begin_date,
        end_date=expected_end_date,
        weeks_requested=validated_weeks,
        weeks=weekly_trends,
    )


def validate_weeks(weeks: int) -> int:
    """Validate and return the requested number of trend weeks."""
    if weeks < MIN_TREND_WEEKS or weeks > MAX_TREND_WEEKS:
        raise ValueError(
            f"weeks must be between {MIN_TREND_WEEKS} and {MAX_TREND_WEEKS}."
        )
    return weeks


def start_of_iso_week(value: date) -> date:
    """Return the Monday that starts the ISO week containing the date."""
    return value - timedelta(days=value.weekday())


def _build_weekly_trends(
    week_totals: dict[date, dict[str, Any]],
) -> list[WeeklyTrainingTrend]:
    """Convert accumulated week totals into API-ready trend objects."""
    trends: list[WeeklyTrainingTrend] = []
    loads: list[float] = []

    for week_start, values in sorted(week_totals.items()):
        sports = [
            _build_sport_trend(sport=sport, values=values["sports"][sport])
            for sport in SPORT_LABELS
        ]
        total_hours = round(sum(sport.hours for sport in sports), 2)
        total_training_load = round(sum(sport.training_load for sport in sports), 1)
        activity_count = sum(sport.activity_count for sport in sports)
        previous_load = loads[-1] if loads else None
        rolling_average = _rolling_average([*loads, total_training_load], window=4)
        chronic_load = _rolling_average(loads[-4:], window=4) if loads else None

        iso_year, iso_week, _ = week_start.isocalendar()
        trends.append(
            WeeklyTrainingTrend(
                week_start=week_start,
                week_end=week_start + timedelta(days=6),
                iso_year=iso_year,
                iso_week=iso_week,
                label=f"{iso_year}-W{iso_week:02d}",
                total_hours=total_hours,
                total_training_load=total_training_load,
                activity_count=activity_count,
                sports=sports,
                rolling_4_week_average_load=rolling_average,
                previous_week_delta_percent=_delta_percent(
                    current=total_training_load,
                    previous=previous_load,
                ),
                acute_chronic_load_ratio=_ratio(
                    numerator=total_training_load,
                    denominator=chronic_load,
                ),
            )
        )
        loads.append(total_training_load)

    return trends


def _build_sport_trend(
    *,
    sport: Sport,
    values: dict[str, float],
) -> WeeklySportTrend:
    """Build one sport-specific weekly trend object."""
    return WeeklySportTrend(
        sport=sport,
        label=SPORT_LABELS[sport],
        hours=round(values["duration_seconds"] / 3600, 2),
        training_load=round(values["training_load"], 1),
        activity_count=int(values["activity_count"]),
    )


def _empty_week_totals() -> dict[str, Any]:
    """Create zero-filled weekly accumulators for every sport."""
    return {
        "sports": {
            sport: {
                "activity_count": 0.0,
                "duration_seconds": 0.0,
                "training_load": 0.0,
            }
            for sport in SPORT_LABELS
        }
    }


def _week_starts(begin_date: date, weeks: int) -> list[date]:
    """Return every ISO week start in ascending order."""
    return [begin_date + timedelta(days=7 * offset) for offset in range(weeks)]


def _rolling_average(values: list[float], *, window: int) -> float | None:
    """Return the average of the most recent window values."""
    if not values:
        return None
    recent_values = values[-window:]
    return round(sum(recent_values) / len(recent_values), 1)


def _delta_percent(*, current: float, previous: float | None) -> float | None:
    """Return week-over-week percent change when a baseline is available."""
    if previous is None or previous <= 0:
        return None
    return round(((current - previous) / previous) * 100, 1)


def _ratio(*, numerator: float, denominator: float | None) -> float | None:
    """Return a rounded ratio when the denominator is available."""
    if denominator is None or denominator <= 0:
        return None
    ratio = numerator / denominator
    if not math.isfinite(ratio):
        return None
    return round(ratio, 2)


def _activity_date(activity: dict[str, Any]) -> date | None:
    """Infer the local activity date from common Garmin payload fields."""
    for key in (
        "startTimeLocal",
        "startTimeGMT",
        "activityStartTimeGMT",
        "startTime",
        "date",
    ):
        raw_value = activity.get(key)
        if raw_value is not None:
            return _coerce_date(raw_value)
    return None


def _coerce_date(raw_value: Any) -> date | None:
    """Convert Garmin date-like values into a date."""
    if isinstance(raw_value, datetime):
        return raw_value.date()
    if isinstance(raw_value, date):
        return raw_value
    if isinstance(raw_value, str):
        normalized = raw_value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized).date()
        except ValueError:
            try:
                return date.fromisoformat(raw_value[:10])
            except ValueError:
                return None
    return None
