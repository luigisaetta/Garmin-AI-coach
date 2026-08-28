"""
Author: L. Saetta
Date Modified: 2026-08-28
License: MIT
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import math
from typing import Any, Literal

# pylint: disable=too-many-instance-attributes

ReportSport = Literal["running", "cycling", "pool_swimming", "open_water_swimming"]
Intensity = Literal["low", "medium", "high", "unclassified"]

MAX_REPORT_DAYS = 366
REPORT_SPORTS: tuple[ReportSport, ...] = (
    "running",
    "cycling",
    "pool_swimming",
    "open_water_swimming",
)
SPORT_LABELS: dict[ReportSport, str] = {
    "running": "Corsa",
    "cycling": "Bici",
    "pool_swimming": "Nuoto in piscina",
    "open_water_swimming": "Nuoto in acque libere",
}
RUNNING_TYPES = frozenset(
    {
        "running",
        "run",
        "street_running",
        "trail_running",
        "treadmill_running",
        "track_running",
        "virtual_running",
    }
)
CYCLING_TYPES = frozenset(
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
)
POOL_SWIMMING_TYPES = frozenset({"lap_swimming", "pool_swimming"})
OPEN_WATER_SWIMMING_TYPES = frozenset({"open_water_swimming"})


@dataclass(frozen=True)  # pylint: disable=too-many-instance-attributes
class SportReportSummary:
    """Deterministic summary for one report sport category."""

    sport: ReportSport
    activity_count: int
    duration_seconds: float
    distance_metres: float
    distance_count: int
    training_load: float
    training_load_count: int
    low_count: int
    medium_count: int
    high_count: int
    unclassified_count: int


@dataclass(frozen=True)
class MonthlyReportSummary:
    """One calendar-month summary used for report trend text."""

    month_start: date
    is_complete: bool
    sport_summaries: list[SportReportSummary]


@dataclass(frozen=True)
class TrainingReport:
    """Complete deterministic report returned by the report endpoint."""

    begin_date: date
    end_date: date
    report_type: Literal["last_365_days", "custom"]
    report: str
    sport_summaries: list[SportReportSummary]
    uncategorised_activity_count: int


class TrainingReportService:  # pylint: disable=too-few-public-methods
    """Build deterministic textual reports from activity summaries."""

    async def create(
        self,
        *,
        training_client: Any,
        user_id: int,
        begin_date: date,
        end_date: date,
        report_type: Literal["last_365_days", "custom"],
    ) -> TrainingReport:
        """Load one bounded activity interval and build its report."""
        _validate_range(begin_date, end_date)
        activities = await training_client.list_activities(
            user_id=user_id,
            begin_date=begin_date.isoformat(),
            end_date=end_date.isoformat(),
        )
        summaries, uncategorised_count = summarize_report_activities(activities)
        monthly_summaries = summarize_report_months(
            activities=activities,
            begin_date=begin_date,
            end_date=end_date,
        )
        return TrainingReport(
            begin_date=begin_date,
            end_date=end_date,
            report_type=report_type,
            report=render_training_report(
                begin_date=begin_date,
                end_date=end_date,
                summaries=summaries,
                monthly_summaries=monthly_summaries,
                uncategorised_activity_count=uncategorised_count,
            ),
            sport_summaries=summaries,
            uncategorised_activity_count=uncategorised_count,
        )


def last_365_day_range(today: date) -> tuple[date, date]:
    """Return the inclusive 365-day range ending on ``today``."""
    return today - timedelta(days=364), today


def summarize_report_activities(
    activities: list[dict[str, Any]],
) -> tuple[list[SportReportSummary], int]:
    """Summarise recognised report activities and count unrecognised ones."""
    totals = _empty_totals_by_sport()
    uncategorised_count = 0
    for activity in activities:
        sport = _report_sport(activity)
        if sport is None:
            uncategorised_count += 1
            continue
        _add_activity(totals[sport], activity)
    return _sport_summaries(totals), uncategorised_count


def summarize_report_months(
    *,
    activities: list[dict[str, Any]],
    begin_date: date,
    end_date: date,
) -> list[MonthlyReportSummary]:
    """Build month-by-month summaries for the requested inclusive interval."""
    totals_by_month: dict[date, dict[ReportSport, dict[str, float]]] = {
        month: _empty_totals_by_sport() for month in _month_starts(begin_date, end_date)
    }
    for activity in activities:
        activity_date = _activity_date(activity)
        sport = _report_sport(activity)
        if activity_date is None or sport is None:
            continue
        month_start = activity_date.replace(day=1)
        month_totals = totals_by_month.get(month_start)
        if month_totals is not None:
            _add_activity(month_totals[sport], activity)

    return [
        MonthlyReportSummary(
            month_start=month,
            is_complete=_month_is_complete(month, begin_date, end_date),
            sport_summaries=_sport_summaries(totals_by_month[month]),
        )
        for month in _month_starts(begin_date, end_date)
    ]


def render_training_report(
    *,
    begin_date: date,
    end_date: date,
    summaries: list[SportReportSummary],
    monthly_summaries: list[MonthlyReportSummary],
    uncategorised_activity_count: int,
) -> str:
    """Render a concise, deterministic Italian training report."""
    total_days = (end_date - begin_date).days + 1
    lines = [
        "# Report allenamento",
        "",
        f"Periodo: {begin_date.isoformat()} — {end_date.isoformat()} ({total_days} giorni).",
        "",
        "## Attività per sport",
        "",
        "| Sport | Attività | Ore | Distanza | Carico | Bassa | Media | Alta | Non classificata |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for summary in summaries:
        lines.append(_sport_summary_row(summary))
    if uncategorised_activity_count:
        lines.extend(
            [
                "",
                (
                    f"Attività non assegnate alle quattro categorie richieste: "
                    f"{uncategorised_activity_count}."
                ),
            ]
        )
    lines.extend(["", "## Trend"])
    if total_days < 28:
        lines.append(
            "Intervallo inferiore a quattro settimane: dati insufficienti per "
            "una conclusione di trend robusta."
        )
    else:
        lines.extend(_monthly_trend_table(monthly_summaries))
    return "\n".join(lines)


def _sport_summary_row(summary: SportReportSummary) -> str:
    """Render one sport summary as a Markdown table row."""
    return (
        f"| {SPORT_LABELS[summary.sport]} | {summary.activity_count} | "
        f"{_format_hours(summary.duration_seconds)} | "
        f"{_format_distance(summary.distance_metres) if summary.distance_count else '—'} | "
        f"{_format_training_load(summary)} | "
        f"{summary.low_count} | {summary.medium_count} | {summary.high_count} | "
        f"{summary.unclassified_count} |"
    )


def _monthly_trend_table(months: list[MonthlyReportSummary]) -> list[str]:
    """Render monthly changes without treating partial months as complete."""
    lines = [
        "",
        "| Mese | Confronto | Volume | Carico | Intensità bassa/media/alta |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    previous: MonthlyReportSummary | None = None
    for month in months:
        label = month.month_start.strftime("%Y-%m")
        totals = _combine_summaries(month.sport_summaries)
        intensity = _intensity_distribution(totals)
        if not month.is_complete:
            lines.append(f"| {label} | Mese parziale | — | — | {intensity} |")
            previous = month
            continue
        if previous is None or not previous.is_complete:
            lines.append(f"| {label} | Primo mese completo | — | — | {intensity} |")
            previous = month
            continue
        previous_totals = _combine_summaries(previous.sport_summaries)
        lines.append(
            f"| {label} | vs {previous.month_start.strftime('%Y-%m')} | "
            f"{_change_percent(previous_totals.duration_seconds, totals.duration_seconds)} | "
            f"{_change_percent(previous_totals.training_load, totals.training_load)} | "
            f"{intensity} |"
        )
        previous = month
    return lines


def _intensity_distribution(summary: SportReportSummary) -> str:
    """Format the current low, medium, and high intensity counts."""
    return f"{summary.low_count}/{summary.medium_count}/{summary.high_count}"


def _change_percent(previous: float, current: float) -> str:
    """Format one neutral month-over-month percentage change."""
    if previous == 0:
        if current == 0:
            return "0%"
        return "n/d"
    percent = ((current - previous) / previous) * 100
    return f"{'+' if percent >= 0 else ''}{percent:.0f}%"


def _combine_summaries(summaries: list[SportReportSummary]) -> SportReportSummary:
    """Combine sport summaries for a period-level trend comparison."""
    return SportReportSummary(
        sport="running",
        activity_count=sum(item.activity_count for item in summaries),
        duration_seconds=sum(item.duration_seconds for item in summaries),
        distance_metres=sum(item.distance_metres for item in summaries),
        distance_count=sum(item.distance_count for item in summaries),
        training_load=sum(item.training_load for item in summaries),
        training_load_count=sum(item.training_load_count for item in summaries),
        low_count=sum(item.low_count for item in summaries),
        medium_count=sum(item.medium_count for item in summaries),
        high_count=sum(item.high_count for item in summaries),
        unclassified_count=sum(item.unclassified_count for item in summaries),
    )


def _empty_totals_by_sport() -> dict[ReportSport, dict[str, float]]:
    """Create mutable numeric accumulators for every report sport."""
    return {sport: defaultdict(float) for sport in REPORT_SPORTS}


def _add_activity(totals: dict[str, float], activity: dict[str, Any]) -> None:
    """Add one activity to a mutable sport accumulator."""
    totals["activity_count"] += 1
    totals["duration_seconds"] += _number(activity.get("duration"))
    distance = _optional_number(activity.get("distance"))
    if distance is not None:
        totals["distance_metres"] += distance
        totals["distance_count"] += 1
    training_load = _optional_number(activity.get("activityTrainingLoad"))
    if training_load is not None:
        totals["training_load"] += training_load
        totals["training_load_count"] += 1
    totals[f"{_intensity(activity)}_count"] += 1


def _sport_summaries(
    totals: dict[ReportSport, dict[str, float]],
) -> list[SportReportSummary]:
    """Convert mutable totals into stable, ordered summaries."""
    return [
        SportReportSummary(
            sport=sport,
            activity_count=int(values["activity_count"]),
            duration_seconds=values["duration_seconds"],
            distance_metres=values["distance_metres"],
            distance_count=int(values["distance_count"]),
            training_load=values["training_load"],
            training_load_count=int(values["training_load_count"]),
            low_count=int(values["low_count"]),
            medium_count=int(values["medium_count"]),
            high_count=int(values["high_count"]),
            unclassified_count=int(values["unclassified_count"]),
        )
        for sport, values in totals.items()
    ]


def _report_sport(activity: dict[str, Any]) -> ReportSport | None:
    """Map Garmin type variants to the report's four explicit sport buckets."""
    type_key = _activity_type_key(activity)
    if type_key in RUNNING_TYPES:
        return "running"
    if type_key in CYCLING_TYPES:
        return "cycling"
    if type_key in POOL_SWIMMING_TYPES:
        return "pool_swimming"
    if type_key in OPEN_WATER_SWIMMING_TYPES:
        return "open_water_swimming"
    return None


def _activity_type_key(activity: dict[str, Any]) -> str:
    """Extract a normalised Garmin activity-type key when available."""
    activity_type = activity.get("activityType")
    if isinstance(activity_type, dict):
        value = activity_type.get("typeKey")
        return value.strip().lower() if isinstance(value, str) else ""
    if isinstance(activity_type, str):
        return activity_type.strip().lower()
    return ""


def _intensity(activity: dict[str, Any]) -> Intensity:
    """Classify one activity using the specified Garmin Training Effect rules."""
    aerobic = _optional_number(activity.get("aerobicTrainingEffect"))
    anaerobic = _optional_number(activity.get("anaerobicTrainingEffect"))
    if (aerobic is not None and aerobic >= 3.5) or (
        anaerobic is not None and anaerobic >= 2.0
    ):
        return "high"
    if aerobic is None:
        return "unclassified"
    if aerobic >= 2.0:
        return "medium"
    return "low"


def _activity_date(activity: dict[str, Any]) -> date | None:
    """Return the local activity date from Garmin's activity summary fields."""
    value = activity.get("startTimeLocal") or activity.get("startTimeGMT")
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def _month_starts(begin_date: date, end_date: date) -> list[date]:
    """Return all calendar-month starts touched by the inclusive interval."""
    current = begin_date.replace(day=1)
    months: list[date] = []
    while current <= end_date:
        months.append(current)
        current = _next_month(current)
    return months


def _month_is_complete(month_start: date, begin_date: date, end_date: date) -> bool:
    """Return whether the full calendar month falls within the interval."""
    return begin_date <= month_start and end_date >= (
        _next_month(month_start) - timedelta(days=1)
    )


def _next_month(value: date) -> date:
    """Return the first day of the following calendar month."""
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _validate_range(begin_date: date, end_date: date) -> None:
    """Validate report interval ordering and the 366-day maximum."""
    if begin_date > end_date:
        raise ValueError("begin_date must be earlier than or equal to end_date.")
    if (end_date - begin_date).days + 1 > MAX_REPORT_DAYS:
        raise ValueError("The report interval must not exceed 366 days.")


def _optional_number(value: Any) -> float | None:
    """Convert finite numeric values while preserving missing values."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _number(value: Any) -> float:
    """Convert a numeric value to zero when it is absent or invalid."""
    return _optional_number(value) or 0.0


def _format_hours(seconds: float) -> str:
    """Format duration as compact decimal hours."""
    return f"{seconds / 3600:.1f} h"


def _format_distance(metres: float) -> str:
    """Format Garmin metres as kilometres."""
    return f"{metres / 1000:.1f} km"


def _format_training_load(summary: SportReportSummary) -> str:
    """Format training load only when Garmin supplied at least one value."""
    return f"{summary.training_load:.0f}" if summary.training_load_count else "—"
