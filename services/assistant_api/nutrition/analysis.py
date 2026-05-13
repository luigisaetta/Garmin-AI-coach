"""
Author: L. Saetta
Date Modified: 2026-05-13
License: MIT
"""

from __future__ import annotations

# pylint: disable=too-many-instance-attributes

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any, Protocol

from services.assistant_api.api.schemas import TokenUsage
from services.assistant_api.nutrition.diary import (
    NutritionDiaryEntry,
    NutritionDiaryService,
)
from services.assistant_api.nutrition.plan import NutritionPlan, NutritionPlanService
from services.assistant_api.orchestration.chat import response_token_usage
from services.assistant_api.orchestration.training_data import TrainingActivitiesClient

LOGGER = logging.getLogger(__name__)

NUTRITION_ANALYSIS_PROMPT = """
You are a nutrition adherence analysis subagent for a personal Garmin training
assistant.

Your task is to compare the user's food diary with the uploaded nutrition plan
for the requested period, taking training load and timing into account.

Important safety and scope rules:
- This is adherence and reflection support, not medical nutrition advice.
- Do not diagnose medical conditions.
- Do not prescribe a new diet, supplements, calories, or macronutrients.
- Discuss calorie volume and macronutrient gaps only as apparent alignment or
  possible insufficiency relative to the explicit uploaded plan and diary text.
- If the plan or diary does not contain enough detail, say the conclusion is
  uncertain instead of inventing numbers.
- Highlight useful points to discuss with the nutritionist.

Write the report in the response_language provided in the input payload. If no
response_language is provided, use the same language as the user's request when
it is clear; expected languages are Italian or English.

Return a detailed report with these sections:
1. Period summary
2. Diary coverage and missing data
3. Training during the period
4. Comparison with the nutrition plan
5. Macronutrients and calorie volume
6. Points of attention
7. Improvement opportunities
8. Questions to bring to the nutritionist

End every report with a clearly separated section titled
"Quantitative adherence rubric". In that section, provide these 1 to 10 scores:
- Plan adherence score
- Meal structure match
- Food choice alignment
- Training-day alignment
- Confidence in assessment

For each score, include one short evidence-based sentence explaining the rating.
The scores are an LLM-estimated adherence rubric, not a clinical or nutritional
assessment. Base them only on explicit plan text, diary entries, and available
training context. Do not include "Consistency across days" or "Evidence
completeness" as metrics.
""".strip()


class NutritionAnalysisError(RuntimeError):
    """Raised when the nutrition analysis subagent cannot complete."""


@dataclass(frozen=True)
class NutritionAnalysisSettings:
    """Runtime settings for the nutrition analysis subagent."""

    model_id: str


@dataclass(frozen=True)
class DailyTrainingSummary:
    """Compact training summary for one activity day."""

    activity_date: date
    activity_count: int
    activity_types: list[str]
    total_duration_minutes: float | None
    total_distance_km: float | None
    intensities: list[str]
    time_of_day: str
    combined_workout: bool
    activities: list[dict[str, Any]]


@dataclass
class NutritionAnalysisContext:
    """Mutable state passed through the linear nutrition subagent graph."""

    begin_date: date
    end_date: date
    response_language: str | None = None
    plan: NutritionPlan | None = None
    diary_entries: list[NutritionDiaryEntry] = field(default_factory=list)
    missing_diary_dates: list[date] = field(default_factory=list)
    training_summaries: list[DailyTrainingSummary] = field(default_factory=list)
    report: str = ""
    token_usage: TokenUsage | None = None


@dataclass(frozen=True)
class NutritionAnalysisResult:
    """Completed nutrition analysis report and source metadata."""

    begin_date: date
    end_date: date
    report: str
    plan_filename: str
    diary_entry_count: int
    missing_diary_dates: list[date]
    training_day_count: int
    token_usage: TokenUsage | None = None


class NutritionAnalysisStep(Protocol):  # pylint: disable=too-few-public-methods
    """Protocol implemented by every linear nutrition subagent step."""

    async def run(self, context: NutritionAnalysisContext) -> NutritionAnalysisContext:
        """Run the step and return the updated context."""


class ReadNutritionPlanStep:  # pylint: disable=too-few-public-methods
    """Load the current nutrition plan from local persistence."""

    def __init__(self, plan_service: NutritionPlanService) -> None:
        self._plan_service = plan_service

    async def run(self, context: NutritionAnalysisContext) -> NutritionAnalysisContext:
        """Read the active nutrition plan."""
        LOGGER.info("nutrition analysis step=read_plan start")
        context.plan = self._plan_service.get_current_plan()
        if context.plan is None:
            raise NutritionAnalysisError("No current nutrition plan is available.")

        LOGGER.info(
            "nutrition analysis step=read_plan done filename=%s text_length=%d",
            context.plan.original_filename,
            len(context.plan.extracted_text),
        )
        return context


class ReadDiaryEntriesStep:  # pylint: disable=too-few-public-methods
    """Load and aggregate food diary entries for the requested period."""

    def __init__(self, diary_service: NutritionDiaryService) -> None:
        self._diary_service = diary_service

    async def run(self, context: NutritionAnalysisContext) -> NutritionAnalysisContext:
        """Read diary entries and calculate missing dates."""
        LOGGER.info(
            "nutrition analysis step=read_diary start begin_date=%s end_date=%s",
            context.begin_date,
            context.end_date,
        )
        context.diary_entries = self._diary_service.list_entries(
            begin_date=context.begin_date,
            end_date=context.end_date,
        )
        present_dates = {entry.entry_date for entry in context.diary_entries}
        context.missing_diary_dates = [
            current_date
            for current_date in _date_range(context.begin_date, context.end_date)
            if current_date not in present_dates
        ]
        LOGGER.info(
            "nutrition analysis step=read_diary done entry_count=%d missing_days=%d",
            len(context.diary_entries),
            len(context.missing_diary_dates),
        )
        return context


class ReadTrainingActivitiesStep:  # pylint: disable=too-few-public-methods
    """Load Garmin training activities and build day-level summaries."""

    def __init__(self, training_client: TrainingActivitiesClient) -> None:
        self._training_client = training_client

    async def run(self, context: NutritionAnalysisContext) -> NutritionAnalysisContext:
        """Read activities and summarize workout type, timing, and intensity."""
        LOGGER.info(
            "nutrition analysis step=read_training start begin_date=%s end_date=%s",
            context.begin_date,
            context.end_date,
        )
        activities = await self._training_client.list_activities(
            begin_date=context.begin_date.isoformat(),
            end_date=context.end_date.isoformat(),
        )
        context.training_summaries = summarize_training_by_day(activities)
        LOGGER.info(
            "nutrition analysis step=read_training done activity_count=%d day_count=%d",
            len(activities),
            len(context.training_summaries),
        )
        return context


class GenerateNutritionReportStep:  # pylint: disable=too-few-public-methods
    """Call Responses API with a dedicated nutrition analysis prompt."""

    def __init__(
        self,
        *,
        inference_client: Any,
        settings: NutritionAnalysisSettings,
    ) -> None:
        self._inference_client = inference_client
        self._settings = settings

    async def run(self, context: NutritionAnalysisContext) -> NutritionAnalysisContext:
        """Generate the final nutrition adherence report."""
        if context.plan is None:
            raise NutritionAnalysisError("Cannot generate report without a plan.")

        LOGGER.info("nutrition analysis step=generate_report start")
        response = self._inference_client.responses.create(
            model=self._settings.model_id,
            instructions=NUTRITION_ANALYSIS_PROMPT,
            input=[
                {
                    "role": "user",
                    "content": json.dumps(
                        build_nutrition_report_payload(context),
                        ensure_ascii=False,
                        default=str,
                    ),
                }
            ],
        )
        context.report = str(getattr(response, "output_text", "")).strip()
        context.token_usage = response_token_usage(response)
        if not context.report:
            raise NutritionAnalysisError("Responses API returned an empty report.")

        LOGGER.info(
            "nutrition analysis step=generate_report done report_length=%d",
            len(context.report),
        )
        return context


class NutritionAnalysisSubAgent:
    """Linear graph that analyzes diary adherence against plan and training."""

    def __init__(self, steps: Sequence[NutritionAnalysisStep]) -> None:
        if not steps:
            raise ValueError("At least one nutrition analysis step is required.")
        self._steps = list(steps)

    @classmethod
    def create(  # pylint: disable=too-many-arguments
        cls,
        *,
        plan_service: NutritionPlanService,
        diary_service: NutritionDiaryService,
        training_client: TrainingActivitiesClient,
        inference_client: Any,
        settings: NutritionAnalysisSettings,
    ) -> "NutritionAnalysisSubAgent":
        """Create the default linear nutrition analysis graph."""
        return cls(
            [
                ReadNutritionPlanStep(plan_service),
                ReadDiaryEntriesStep(diary_service),
                ReadTrainingActivitiesStep(training_client),
                GenerateNutritionReportStep(
                    inference_client=inference_client,
                    settings=settings,
                ),
            ]
        )

    async def analyze(
        self,
        *,
        begin_date: date,
        end_date: date,
        response_language: str | None = None,
    ) -> NutritionAnalysisResult:
        """Run every graph step and return the completed report."""
        if begin_date > end_date:
            raise ValueError("begin_date must be before or equal to end_date")
        if response_language not in {None, "italian", "english"}:
            raise ValueError("response_language must be 'italian' or 'english'")

        LOGGER.info(
            "nutrition analysis graph start begin_date=%s end_date=%s",
            begin_date,
            end_date,
        )
        context = NutritionAnalysisContext(
            begin_date=begin_date,
            end_date=end_date,
            response_language=response_language,
        )
        for step in self._steps:
            context = await step.run(context)

        if context.plan is None:
            raise NutritionAnalysisError("Nutrition analysis finished without a plan.")

        LOGGER.info("nutrition analysis graph done")
        return NutritionAnalysisResult(
            begin_date=begin_date,
            end_date=end_date,
            report=context.report,
            plan_filename=context.plan.original_filename,
            diary_entry_count=len(context.diary_entries),
            missing_diary_dates=context.missing_diary_dates,
            training_day_count=len(context.training_summaries),
            token_usage=context.token_usage,
        )


def build_nutrition_report_payload(
    context: NutritionAnalysisContext,
) -> dict[str, Any]:
    """Build the compact payload sent to the nutrition analysis model."""
    if context.plan is None:
        raise NutritionAnalysisError("Cannot build payload without a plan.")

    return {
        "period": {
            "begin_date": context.begin_date.isoformat(),
            "end_date": context.end_date.isoformat(),
        },
        "response_language": context.response_language,
        "current_plan": {
            "original_filename": context.plan.original_filename,
            "uploaded_at": context.plan.uploaded_at.isoformat(),
            "extracted_text": context.plan.extracted_text,
        },
        "diary_entries": [
            {
                "entry_date": entry.entry_date.isoformat(),
                "training_type": entry.training_type,
                "meals_text": entry.meals_text,
                "notes": entry.notes,
            }
            for entry in context.diary_entries
        ],
        "missing_diary_dates": [
            missing_date.isoformat() for missing_date in context.missing_diary_dates
        ],
        "training_summaries": [
            {
                "activity_date": summary.activity_date.isoformat(),
                "activity_count": summary.activity_count,
                "activity_types": summary.activity_types,
                "total_duration_minutes": summary.total_duration_minutes,
                "total_distance_km": summary.total_distance_km,
                "intensities": summary.intensities,
                "time_of_day": summary.time_of_day,
                "combined_workout": summary.combined_workout,
                "activities": summary.activities,
            }
            for summary in context.training_summaries
        ],
    }


def summarize_training_by_day(
    activities: Sequence[dict[str, Any]],
) -> list[DailyTrainingSummary]:
    """Summarize Garmin activities by calendar day."""
    activities_by_date: dict[date, list[dict[str, Any]]] = {}
    for activity in activities:
        activity_date = _activity_date(activity)
        if activity_date is None:
            continue
        activities_by_date.setdefault(activity_date, []).append(activity)

    return [
        _summarize_activity_day(activity_date, day_activities)
        for activity_date, day_activities in sorted(activities_by_date.items())
    ]


def _summarize_activity_day(
    activity_date: date,
    activities: Sequence[dict[str, Any]],
) -> DailyTrainingSummary:
    """Build a compact day-level training summary."""
    durations = [_duration_minutes(activity) for activity in activities]
    distances = [_distance_km(activity) for activity in activities]
    compact_activities = [_compact_activity(activity) for activity in activities]
    times_of_day = [_activity_time_of_day(activity) for activity in activities]
    known_times = [item for item in times_of_day if item != "unknown"]

    return DailyTrainingSummary(
        activity_date=activity_date,
        activity_count=len(activities),
        activity_types=sorted({_activity_type(activity) for activity in activities}),
        total_duration_minutes=_sum_known(durations),
        total_distance_km=_sum_known(distances),
        intensities=sorted({_activity_intensity(activity) for activity in activities}),
        time_of_day=_combined_time_of_day(known_times),
        combined_workout=len(activities) > 1,
        activities=compact_activities,
    )


def _compact_activity(activity: dict[str, Any]) -> dict[str, Any]:
    """Extract activity fields useful for nutrition analysis."""
    return {
        "name": _first_present(activity, ["activityName", "name"]),
        "type": _activity_type(activity),
        "start_time": _first_present(
            activity,
            ["startTimeLocal", "startTimeGMT", "activityStartTimeGMT", "startTime"],
        ),
        "duration_minutes": _duration_minutes(activity),
        "distance_km": _distance_km(activity),
        "average_heart_rate": _first_present(
            activity,
            ["averageHR", "averageHr", "avgHr", "averageHeartRate"],
        ),
        "max_heart_rate": _first_present(
            activity,
            ["maxHR", "maxHr", "maxHeartRate"],
        ),
        "training_effect": _first_present(
            activity,
            ["aerobicTrainingEffect", "trainingEffect", "activityTrainingLoad"],
        ),
        "intensity": _activity_intensity(activity),
        "time_of_day": _activity_time_of_day(activity),
    }


def _activity_date(  # pylint: disable=too-many-return-statements
    activity: dict[str, Any],
) -> date | None:
    """Infer the local activity date from common Garmin payload fields."""
    raw_value = _first_present(
        activity,
        ["startTimeLocal", "startTimeGMT", "activityStartTimeGMT", "startTime", "date"],
    )
    if raw_value is None:
        return None

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


def _activity_time_of_day(activity: dict[str, Any]) -> str:
    """Classify workout timing as morning, afternoon, evening, or unknown."""
    raw_value = _first_present(
        activity,
        ["startTimeLocal", "startTimeGMT", "activityStartTimeGMT", "startTime"],
    )
    activity_time = _coerce_time(raw_value)
    if activity_time is None:
        return "unknown"
    if activity_time < time(12, 0):
        return "morning"
    if activity_time < time(18, 0):
        return "afternoon"
    return "evening"


def _activity_type(
    activity: dict[str, Any],
) -> str:  # pylint: disable=too-many-return-statements
    """Extract a readable activity type."""
    raw_type = activity.get("activityType")
    if isinstance(raw_type, dict):
        for key in ("typeKey", "displayName", "parentTypeId"):
            value = raw_type.get(key)
            if value:
                return str(value)
    if raw_type:
        return str(raw_type)

    raw_type = activity.get("activityTypeDTO")
    if isinstance(raw_type, dict):
        for key in ("typeKey", "displayName"):
            value = raw_type.get(key)
            if value:
                return str(value)

    return str(
        _first_present(activity, ["sportType", "activityName", "type"]) or "unknown"
    )


def _activity_intensity(  # pylint: disable=too-many-return-statements
    activity: dict[str, Any],
) -> str:
    """Infer a coarse activity intensity from available Garmin fields."""
    training_effect = _as_float(
        _first_present(activity, ["aerobicTrainingEffect", "trainingEffect"])
    )
    if training_effect is not None:
        if training_effect >= 4:
            return "high"
        if training_effect >= 2.5:
            return "moderate"
        return "low"

    average_hr = _as_float(
        _first_present(
            activity, ["averageHR", "averageHr", "avgHr", "averageHeartRate"]
        )
    )
    if average_hr is not None:
        if average_hr >= 155:
            return "high"
        if average_hr >= 125:
            return "moderate"
        return "low"

    return "unknown"


def _duration_minutes(activity: dict[str, Any]) -> float | None:
    """Extract activity duration in minutes."""
    raw_duration = _as_float(
        _first_present(
            activity,
            ["duration", "elapsedDuration", "movingDuration", "elapsed_time"],
        )
    )
    if raw_duration is None:
        return None
    return round(raw_duration / 60, 1)


def _distance_km(activity: dict[str, Any]) -> float | None:
    """Extract activity distance in kilometers."""
    raw_distance = _as_float(_first_present(activity, ["distance", "distanceMeters"]))
    if raw_distance is None:
        return None
    return round(raw_distance / 1000, 2)


def _combined_time_of_day(values: Sequence[str]) -> str:
    """Describe whether workouts happened in one or multiple day windows."""
    unique_values = sorted(set(values))
    if not unique_values:
        return "unknown"
    if len(unique_values) == 1:
        return unique_values[0]
    return "combined: " + ", ".join(unique_values)


def _date_range(begin_date: date, end_date: date) -> list[date]:
    """Return every date in an inclusive date range."""
    return [
        date.fromordinal(ordinal)
        for ordinal in range(begin_date.toordinal(), end_date.toordinal() + 1)
    ]


def _first_present(activity: dict[str, Any], keys: Sequence[str]) -> Any:
    """Return the first non-empty value found in an activity dictionary."""
    for key in keys:
        value = activity.get(key)
        if value not in (None, ""):
            return value
    return None


def _coerce_time(value: Any) -> time | None:
    """Convert a supported timestamp value into a time when possible."""
    if isinstance(value, datetime):
        return value.time()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).time()
        except ValueError:
            return None
    return None


def _as_float(value: Any) -> float | None:
    """Convert numeric-like values to float."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sum_known(values: Sequence[float | None]) -> float | None:
    """Sum known numeric values, preserving unknown when none are present."""
    known_values = [value for value in values if value is not None]
    if not known_values:
        return None
    return round(sum(known_values), 2)
