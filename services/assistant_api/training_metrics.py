"""
Author: L. Saetta
Date Modified: 2026-07-10
License: MIT
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math
from typing import Any, Literal

Sport = Literal["running", "cycling", "swimming"]
IntensitySource = Literal["training_load", "intensity_minutes", "none"]

SPORT_LABELS: dict[Sport, str] = {
    "running": "Run",
    "cycling": "Bike",
    "swimming": "Swim",
}

SPORT_ALIASES: dict[Sport, frozenset[str]] = {
    "running": frozenset(
        {
            "running",
            "run",
            "street_running",
            "trail_running",
            "treadmill_running",
            "track_running",
            "virtual_running",
        }
    ),
    "cycling": frozenset(
        {
            "cycling",
            "biking",
            "road_biking",
            "mountain_biking",
            "gravel_cycling",
            "indoor_cycling",
            "virtual_ride",
            "e_biking",
            "e_mountain_biking",
        }
    ),
    "swimming": frozenset(
        {
            "swimming",
            "lap_swimming",
            "open_water_swimming",
            "pool_swimming",
        }
    ),
}


@dataclass(frozen=True)
class SportMetrics:  # pylint: disable=too-many-instance-attributes
    """Aggregate training metrics for one sport."""

    sport: Sport
    label: str
    activity_count: int
    hours: float
    total_duration_seconds: float
    total_training_load: float | None
    training_load_per_hour: float | None
    weighted_average_heart_rate: float | None
    average_aerobic_training_effect: float | None
    average_anaerobic_training_effect: float | None
    moderate_intensity_minutes: float
    vigorous_intensity_minutes: float
    intensity_score: float | None
    intensity_source: IntensitySource


@dataclass(frozen=True)
class TrainingMetricsSummary:
    """Aggregate training metrics for an inclusive date range."""

    begin_date: date
    end_date: date
    sports: list[SportMetrics]


class TrainingMetricsService:  # pylint: disable=too-few-public-methods
    """Compute compact training metrics from Garmin activity payloads."""

    async def summarize(
        self,
        *,
        training_client: Any,
        user_id: int,
        begin_date: date,
        end_date: date,
    ) -> TrainingMetricsSummary:
        """Return sport metrics for activities in an inclusive date range."""
        if begin_date > end_date:
            raise ValueError("begin_date must be earlier than or equal to end_date.")

        activities = await training_client.list_activities(
            user_id=user_id,
            begin_date=begin_date.isoformat(),
            end_date=end_date.isoformat(),
        )
        return summarize_training_metrics(
            activities=activities,
            begin_date=begin_date,
            end_date=end_date,
        )


def summarize_training_metrics(
    *,
    activities: list[dict[str, Any]],
    begin_date: date,
    end_date: date,
) -> TrainingMetricsSummary:
    """Aggregate raw Garmin activity dictionaries into dashboard metrics."""
    totals: dict[Sport, dict[str, float]] = {
        sport: {
            "activity_count": 0.0,
            "duration_seconds": 0.0,
            "training_load": 0.0,
            "training_load_count": 0.0,
            "heart_rate_duration_seconds": 0.0,
            "heart_rate_weighted_sum": 0.0,
            "aerobic_effect_duration_seconds": 0.0,
            "aerobic_effect_weighted_sum": 0.0,
            "anaerobic_effect_duration_seconds": 0.0,
            "anaerobic_effect_weighted_sum": 0.0,
            "moderate_minutes": 0.0,
            "vigorous_minutes": 0.0,
        }
        for sport in SPORT_LABELS
    }

    for activity in activities:
        sport = _sport_from_activity(activity)
        if sport is None:
            continue

        sport_totals = totals[sport]
        sport_totals["activity_count"] += 1
        duration_seconds = _number(activity.get("duration"))
        sport_totals["duration_seconds"] += duration_seconds

        training_load = _optional_number(activity.get("activityTrainingLoad"))
        if training_load is not None:
            sport_totals["training_load"] += training_load
            sport_totals["training_load_count"] += 1

        average_heart_rate = _optional_number(activity.get("averageHR"))
        if average_heart_rate is not None and duration_seconds > 0:
            sport_totals["heart_rate_weighted_sum"] += (
                average_heart_rate * duration_seconds
            )
            sport_totals["heart_rate_duration_seconds"] += duration_seconds

        aerobic_effect = _optional_number(activity.get("aerobicTrainingEffect"))
        if aerobic_effect is not None and duration_seconds > 0:
            sport_totals["aerobic_effect_weighted_sum"] += (
                aerobic_effect * duration_seconds
            )
            sport_totals["aerobic_effect_duration_seconds"] += duration_seconds

        anaerobic_effect = _optional_number(activity.get("anaerobicTrainingEffect"))
        if anaerobic_effect is not None and duration_seconds > 0:
            sport_totals["anaerobic_effect_weighted_sum"] += (
                anaerobic_effect * duration_seconds
            )
            sport_totals["anaerobic_effect_duration_seconds"] += duration_seconds

        sport_totals["moderate_minutes"] += _number(
            activity.get("moderateIntensityMinutes")
        )
        sport_totals["vigorous_minutes"] += _number(
            activity.get("vigorousIntensityMinutes")
        )

    sport_metrics = [
        _build_sport_metrics(sport=sport, values=totals[sport])
        for sport in SPORT_LABELS
    ]
    return TrainingMetricsSummary(
        begin_date=begin_date,
        end_date=end_date,
        sports=sport_metrics,
    )


def _build_sport_metrics(sport: Sport, values: dict[str, float]) -> SportMetrics:
    """Build a stable metrics object from accumulated sport totals."""
    total_training_load = (
        round(values["training_load"], 1) if values["training_load_count"] > 0 else None
    )
    moderate_minutes = round(values["moderate_minutes"], 1)
    vigorous_minutes = round(values["vigorous_minutes"], 1)

    if total_training_load is not None:
        intensity_score = total_training_load
        intensity_source: IntensitySource = "training_load"
    elif moderate_minutes > 0 or vigorous_minutes > 0:
        intensity_score = round(moderate_minutes + (2 * vigorous_minutes), 1)
        intensity_source = "intensity_minutes"
    else:
        intensity_score = None
        intensity_source = "none"

    duration_seconds = values["duration_seconds"]
    hours = duration_seconds / 3600
    return SportMetrics(
        sport=sport,
        label=SPORT_LABELS[sport],
        activity_count=int(values["activity_count"]),
        hours=round(hours, 2),
        total_duration_seconds=round(duration_seconds, 1),
        total_training_load=total_training_load,
        training_load_per_hour=(
            round(total_training_load / hours, 1)
            if total_training_load is not None and hours > 0
            else None
        ),
        weighted_average_heart_rate=_weighted_average(
            weighted_sum=values["heart_rate_weighted_sum"],
            weight=values["heart_rate_duration_seconds"],
        ),
        average_aerobic_training_effect=_weighted_average(
            weighted_sum=values["aerobic_effect_weighted_sum"],
            weight=values["aerobic_effect_duration_seconds"],
        ),
        average_anaerobic_training_effect=_weighted_average(
            weighted_sum=values["anaerobic_effect_weighted_sum"],
            weight=values["anaerobic_effect_duration_seconds"],
        ),
        moderate_intensity_minutes=moderate_minutes,
        vigorous_intensity_minutes=vigorous_minutes,
        intensity_score=intensity_score,
        intensity_source=intensity_source,
    )


def _sport_from_activity(activity: dict[str, Any]) -> Sport | None:
    """Map Garmin activity type variants to dashboard sport buckets."""
    activity_type = activity.get("activityType")
    candidates: list[str] = []

    if isinstance(activity_type, str):
        candidates.append(activity_type)
    elif isinstance(activity_type, dict):
        for key in ("typeKey", "typeName", "parentTypeId", "activityTypeKey"):
            value = activity_type.get(key)
            if isinstance(value, str):
                candidates.append(value)

    for key in ("activityTypeKey", "sportType", "activityType"):
        value = activity.get(key)
        if isinstance(value, str):
            candidates.append(value)

    normalized_candidates = {_normalize_activity_type(value) for value in candidates}
    for sport, aliases in SPORT_ALIASES.items():
        if normalized_candidates.intersection(aliases):
            return sport
    return None


def _weighted_average(*, weighted_sum: float, weight: float) -> float | None:
    """Return a rounded weighted average when the weight is available."""
    if weight <= 0:
        return None
    return round(weighted_sum / weight, 1)


def _normalize_activity_type(value: str) -> str:
    """Normalize Garmin activity type labels for alias matching."""
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _optional_number(value: Any) -> float | None:
    """Return a finite float for numeric payload values, otherwise None."""
    number = _number(value)
    if number == 0 and value in (None, ""):
        return None
    return number


def _number(value: Any) -> float:
    """Return a finite float for numeric payload values, otherwise zero."""
    if isinstance(value, bool) or value is None:
        return 0.0

    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0

    if not math.isfinite(number):
        return 0.0
    return number
