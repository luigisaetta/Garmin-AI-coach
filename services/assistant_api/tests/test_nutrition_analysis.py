"""
Author: L. Saetta
Date Modified: 2026-05-12
License: MIT
"""

from __future__ import annotations

# pylint: disable=too-few-public-methods

import json
import asyncio
from datetime import date
from typing import Any

from services.assistant_api.nutrition.analysis import (
    NUTRITION_ANALYSIS_PROMPT,
    NutritionAnalysisSettings,
    NutritionAnalysisSubAgent,
    summarize_training_by_day,
)
from services.assistant_api.nutrition.diary import (
    NutritionDiaryEntryInput,
    NutritionDiaryService,
)
from services.assistant_api.nutrition.plan import NutritionPlanService


class FakeResponses:
    """Fake Responses API surface used by nutrition analysis tests."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        """Record the request and return a predictable report."""
        self.requests.append(kwargs)
        return FakeResponse("Report nutrizionale dettagliato.")


class FakeInferenceClient:
    """Fake OpenAI-compatible client exposing a Responses API namespace."""

    def __init__(self) -> None:
        self.responses = FakeResponses()


class FakeResponse:
    """Minimal fake Responses API result."""

    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.usage = {
            "input_tokens": 10,
            "output_tokens": 20,
            "total_tokens": 30,
        }


class FakeTrainingClient:
    """Fake local training client for nutrition analysis tests."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def list_activities(
        self,
        *,
        begin_date: str,
        end_date: str,
        activity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return activities with known timing and intensity."""
        self.calls.append(
            {
                "begin_date": begin_date,
                "end_date": end_date,
                "activity_type": activity_type or "",
            }
        )
        return [
            {
                "activityName": "Morning Run",
                "activityType": {"typeKey": "running"},
                "startTimeLocal": "2026-05-12T07:30:00",
                "duration": 3600,
                "distance": 10000,
                "averageHR": 150,
            },
            {
                "activityName": "Evening Strength",
                "activityType": {"typeKey": "strength_training"},
                "startTimeLocal": "2026-05-12T19:00:00",
                "duration": 1800,
                "aerobicTrainingEffect": 1.5,
            },
        ]

    async def get_heart_rates(
        self,
        *,
        begin_date: str,
        end_date: str,
    ) -> dict[str, dict[str, Any]]:
        """Return no heart-rate data; unused by this subagent."""
        return {"begin_date": {"begin_date": begin_date, "end_date": end_date}}


def test_summarize_training_by_day_detects_combined_timing_and_totals() -> None:
    """Verify workout summaries include duration, timing, and combined days."""
    summaries = summarize_training_by_day(
        [
            {
                "activityName": "Run",
                "activityType": {"typeKey": "running"},
                "startTimeLocal": "2026-05-12T07:00:00",
                "duration": 1800,
                "distance": 5000,
                "averageHR": 160,
            },
            {
                "activityName": "Ride",
                "activityType": {"typeKey": "cycling"},
                "startTimeLocal": "2026-05-12T18:30:00",
                "duration": 3600,
                "distance": 30000,
                "averageHR": 120,
            },
        ]
    )

    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.activity_date == date(2026, 5, 12)
    assert summary.activity_count == 2
    assert summary.combined_workout is True
    assert summary.total_duration_minutes == 90
    assert summary.total_distance_km == 35
    assert summary.time_of_day == "combined: evening, morning"
    assert summary.activity_types == ["cycling", "running"]


def test_nutrition_analysis_subagent_runs_linear_graph(tmp_path) -> None:
    """Verify the subagent reads plan, diary, training, then calls Responses."""
    asyncio.run(_run_subagent_graph_assertions(tmp_path))


async def _run_subagent_graph_assertions(tmp_path) -> None:
    """Run async subagent assertions without requiring pytest async plugins."""
    database_path = tmp_path / "nutrition.db"
    plan_service = NutritionPlanService(
        database_path,
        text_extractor=lambda _: "Breakfast: oats. Lunch: rice and protein.",
    )
    plan_service.replace_current_plan(
        original_filename="plan.pdf",
        content_type="application/pdf",
        pdf_bytes=b"plan",
    )
    diary_service = NutritionDiaryService(database_path)
    diary_service.upsert_entry(
        NutritionDiaryEntryInput(
            entry_date=date(2026, 5, 12),
            training_type="Run plus strength",
            meals_text="Breakfast: coffee. Lunch: salad. Dinner: pasta.",
            notes="Hungry after training.",
        )
    )
    training_client = FakeTrainingClient()
    inference_client = FakeInferenceClient()
    subagent = NutritionAnalysisSubAgent.create(
        plan_service=plan_service,
        diary_service=diary_service,
        training_client=training_client,
        inference_client=inference_client,
        settings=NutritionAnalysisSettings(model_id="openai.gpt-5.4"),
    )

    result = await subagent.analyze(
        begin_date=date(2026, 5, 12),
        end_date=date(2026, 5, 13),
        response_language="italian",
    )

    assert result.report == "Report nutrizionale dettagliato."
    assert result.plan_filename == "plan.pdf"
    assert result.diary_entry_count == 1
    assert result.missing_diary_dates == [date(2026, 5, 13)]
    assert result.training_day_count == 1
    assert result.token_usage is not None
    assert result.token_usage.total_tokens == 30
    assert training_client.calls == [
        {
            "begin_date": "2026-05-12",
            "end_date": "2026-05-13",
            "activity_type": "",
        }
    ]
    assert len(inference_client.responses.requests) == 1
    request = inference_client.responses.requests[0]
    assert request["model"] == "openai.gpt-5.4"
    assert request["instructions"] == NUTRITION_ANALYSIS_PROMPT
    payload = json.loads(request["input"][0]["content"])
    assert payload["period"] == {
        "begin_date": "2026-05-12",
        "end_date": "2026-05-13",
    }
    assert payload["response_language"] == "italian"
    assert payload["missing_diary_dates"] == ["2026-05-13"]
    assert payload["training_summaries"][0]["combined_workout"] is True


def test_nutrition_analysis_prompt_does_not_force_italian() -> None:
    """Verify the nutrition subagent prompt keeps language selection flexible."""
    assert "Return a detailed report in Italian" not in NUTRITION_ANALYSIS_PROMPT
    assert "response_language" in NUTRITION_ANALYSIS_PROMPT
    assert "Period summary" in NUTRITION_ANALYSIS_PROMPT
