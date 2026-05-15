"""
Author: L. Saetta
Date Modified: 2026-05-15
License: MIT
"""

from __future__ import annotations

# pylint: disable=too-few-public-methods

import asyncio
import json
from typing import Any

import pytest

from services.assistant_api.nutrition.rewrite import (
    NUTRITION_DIARY_REWRITE_PROMPT,
    NutritionDiaryRewriteError,
    NutritionDiaryRewriteInput,
    NutritionDiaryRewriteService,
    NutritionDiaryRewriteSettings,
)


class FakeResponses:
    """Fake Responses API surface used by rewrite tests."""

    def __init__(self, output_text: str) -> None:
        self.output_text = output_text
        self.requests: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        """Record the request and return the configured rewrite."""
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
            "input_tokens": 11,
            "output_tokens": 7,
            "total_tokens": 18,
        }


def test_diary_rewrite_uses_responses_api_with_guardrail_prompt() -> None:
    """Verify diary rewrite calls Responses with the dedicated editor prompt."""
    inference_client = FakeInferenceClient("Colazione: yogurt e miele.")
    service = NutritionDiaryRewriteService(
        inference_client=inference_client,
        settings=NutritionDiaryRewriteSettings(model_id="openai.gpt-5.4"),
    )

    result = asyncio.run(
        service.rewrite(
            NutritionDiaryRewriteInput(
                entry_date="2026-05-15",
                training_type="Easy run",
                meals_text="colazione yogurt miele",
                notes="energia buona",
            )
        )
    )

    assert result.rewritten_meals_text == "Colazione: yogurt e miele."
    assert result.token_usage is not None
    assert result.token_usage.total_tokens == 18
    request = inference_client.responses.requests[0]
    assert request["model"] == "openai.gpt-5.4"
    assert request["instructions"] == NUTRITION_DIARY_REWRITE_PROMPT
    payload = json.loads(request["input"][0]["content"])
    assert payload == {
        "entry_date": "2026-05-15",
        "training_type": "Easy run",
        "meals_text": "colazione yogurt miele",
        "notes": "energia buona",
    }


def test_diary_rewrite_returns_empty_without_model_call_for_blank_input() -> None:
    """Verify blank diary text does not trigger a Responses API call."""
    inference_client = FakeInferenceClient("unused")
    service = NutritionDiaryRewriteService(
        inference_client=inference_client,
        settings=NutritionDiaryRewriteSettings(model_id="openai.gpt-5.4"),
    )

    result = asyncio.run(
        service.rewrite(
            NutritionDiaryRewriteInput(
                entry_date="2026-05-15",
                training_type="Rest day",
                meals_text="   ",
            )
        )
    )

    assert result.rewritten_meals_text == ""
    assert not inference_client.responses.requests


def test_diary_rewrite_raises_when_model_returns_empty_text() -> None:
    """Verify empty Responses output fails clearly."""
    service = NutritionDiaryRewriteService(
        inference_client=FakeInferenceClient("   "),
        settings=NutritionDiaryRewriteSettings(model_id="openai.gpt-5.4"),
    )

    with pytest.raises(NutritionDiaryRewriteError):
        asyncio.run(
            service.rewrite(
                NutritionDiaryRewriteInput(
                    entry_date="2026-05-15",
                    training_type="Rest day",
                    meals_text="Breakfast: toast.",
                )
            )
        )


def test_diary_rewrite_prompt_preserves_text_editing_scope() -> None:
    """Verify the rewrite prompt prevents nutritional coaching behaviour."""
    prompt = " ".join(NUTRITION_DIARY_REWRITE_PROMPT.split())

    assert "Do not add foods" in prompt
    assert "judgments, recommendations, or assumptions" in prompt
    assert "Return only the rewritten diary text" in prompt
