"""
Author: L. Saetta
Date Modified: 2026-07-10
License: MIT
"""

from __future__ import annotations

# pylint: disable=duplicate-code,too-few-public-methods

import asyncio
import json
from datetime import date
from typing import Any

import pytest

from services.assistant_api.training_metrics import summarize_training_metrics
from services.assistant_api.training_metrics_analysis import (
    TRAINING_METRICS_ANALYSIS_PROMPT,
    TrainingMetricsAnalysisError,
    TrainingMetricsAnalysisService,
    TrainingMetricsAnalysisSettings,
    build_training_metrics_analysis_payload,
)


class FakeResponses:
    """Fake Responses API surface used by training metrics analysis tests."""

    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.requests: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        """Record the request and return the configured analysis."""
        self.requests.append(kwargs)
        return FakeResponse(self.output_text)


class FakeInferenceClient:
    """Fake OpenAI-compatible client exposing a Responses API namespace."""

    def __init__(self, output_text: str) -> None:
        self.responses = FakeResponses(output_text)


class FakeResponse:
    """Minimal fake Responses API result."""

    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.usage = {
            "input_tokens": 30,
            "output_tokens": 20,
            "total_tokens": 50,
        }


def _summary():
    """Build a deterministic aggregate metrics summary."""
    return summarize_training_metrics(
        begin_date=date(2026, 7, 1),
        end_date=date(2026, 7, 7),
        activities=[
            {
                "activityType": {"typeKey": "running"},
                "duration": 3600,
                "activityTrainingLoad": 120,
                "averageHR": 148,
                "aerobicTrainingEffect": 3.1,
                "anaerobicTrainingEffect": 0.7,
            }
        ],
    )


def test_training_metrics_analysis_uses_responses_api_with_compact_payload() -> None:
    """Verify training metrics analysis uses aggregate metrics only."""
    inference_client = FakeInferenceClient("Buon equilibrio, carico concentrato.")
    service = TrainingMetricsAnalysisService(
        inference_client=inference_client,
        settings=TrainingMetricsAnalysisSettings(model_id="openai.gpt-5.5"),
    )

    result = asyncio.run(
        service.analyze(summary=_summary(), response_language="italian")
    )

    assert result.analysis == "Buon equilibrio, carico concentrato."
    assert result.token_usage is not None
    assert result.token_usage.total_tokens == 50
    request = inference_client.responses.requests[0]
    assert request["model"] == "openai.gpt-5.5"
    assert request["instructions"] == TRAINING_METRICS_ANALYSIS_PROMPT
    payload = json.loads(request["input"][0]["content"])
    assert payload["period"] == {
        "begin_date": "2026-07-01",
        "end_date": "2026-07-07",
    }
    assert payload["response_language"] == "italian"
    assert payload["sports"][0]["sport"] == "running"
    assert payload["sports"][0]["total_training_load"] == 120.0
    assert "activities" not in payload


def test_build_training_metrics_analysis_payload_includes_missing_sports() -> None:
    """Verify payload keeps empty sport buckets explicit."""
    payload = build_training_metrics_analysis_payload(
        summary=_summary(),
        response_language="english",
    )

    assert [sport["sport"] for sport in payload["sports"]] == [
        "running",
        "cycling",
        "swimming",
    ]
    assert payload["sports"][2]["activity_count"] == 0
    assert payload["sports"][2]["total_training_load"] is None


def test_training_metrics_analysis_raises_when_model_returns_empty_text() -> None:
    """Verify empty Responses output fails clearly."""
    service = TrainingMetricsAnalysisService(
        inference_client=FakeInferenceClient("   "),
        settings=TrainingMetricsAnalysisSettings(model_id="openai.gpt-5.5"),
    )

    with pytest.raises(TrainingMetricsAnalysisError):
        asyncio.run(service.analyze(summary=_summary()))


def test_training_metrics_analysis_prompt_limits_scope() -> None:
    """Verify the analysis prompt prevents unsupported inferences."""
    prompt = " ".join(TRAINING_METRICS_ANALYSIS_PROMPT.split())

    assert "aggregate metrics" in prompt
    assert "Do not invent workouts" in prompt
    assert "medical advice" in prompt
