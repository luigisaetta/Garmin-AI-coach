"""
Author: L. Saetta
Date Modified: 2026-05-15
License: MIT
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from services.assistant_api.api.schemas import TokenUsage
from services.assistant_api.orchestration.chat import response_token_usage

LOGGER = logging.getLogger(__name__)

NUTRITION_DIARY_REWRITE_PROMPT = """
You are a careful text editor for a personal nutrition diary.

Rewrite the user's daily meal diary so it is clearer, better structured, and
easier to read.

Strict rules:
- Do not add foods, drinks, quantities, calories, macronutrients, timings,
  symptoms, judgments, recommendations, or assumptions.
- Do not remove explicit foods, quantities, timings, uncertainty, or caveats.
- Preserve vague wording when the user is vague.
- Preserve the user's language. Expected languages are Italian or English.
- Format the result as plain text grouped by meal or moment of the day when the
  input supports that structure.
- If the input is empty or contains only whitespace, return an empty string.
- Return only the rewritten diary text, with no explanation or markdown fence.
""".strip()


class NutritionDiaryRewriteError(RuntimeError):
    """Raised when diary rewrite generation cannot complete."""


@dataclass(frozen=True)
class NutritionDiaryRewriteSettings:
    """Runtime settings for diary rewrite generation."""

    model_id: str


@dataclass(frozen=True)
class NutritionDiaryRewriteInput:
    """User-provided diary text accepted by the rewrite service."""

    entry_date: str
    training_type: str
    meals_text: str
    notes: str = ""


@dataclass(frozen=True)
class NutritionDiaryRewriteResult:
    """Rewritten diary text and optional model token usage."""

    rewritten_meals_text: str
    token_usage: TokenUsage | None = None


class NutritionDiaryRewriteService:  # pylint: disable=too-few-public-methods
    """Rewrite one nutrition diary entry using the Responses API."""

    def __init__(
        self,
        *,
        inference_client: Any,
        settings: NutritionDiaryRewriteSettings,
    ) -> None:
        self._inference_client = inference_client
        self._settings = settings

    async def rewrite(
        self,
        rewrite_input: NutritionDiaryRewriteInput,
    ) -> NutritionDiaryRewriteResult:
        """Rewrite the supplied diary text without changing its meaning."""
        if not rewrite_input.meals_text.strip():
            return NutritionDiaryRewriteResult(rewritten_meals_text="")

        LOGGER.info(
            "nutrition diary rewrite start entry_date=%s", rewrite_input.entry_date
        )
        response = self._inference_client.responses.create(
            model=self._settings.model_id,
            instructions=NUTRITION_DIARY_REWRITE_PROMPT,
            input=[
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "entry_date": rewrite_input.entry_date,
                            "training_type": rewrite_input.training_type,
                            "meals_text": rewrite_input.meals_text,
                            "notes": rewrite_input.notes,
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        )
        rewritten_text = str(getattr(response, "output_text", "")).strip()
        if not rewritten_text:
            raise NutritionDiaryRewriteError("Responses API returned an empty rewrite.")

        LOGGER.info(
            "nutrition diary rewrite done entry_date=%s input_length=%d output_length=%d",
            rewrite_input.entry_date,
            len(rewrite_input.meals_text),
            len(rewritten_text),
        )
        return NutritionDiaryRewriteResult(
            rewritten_meals_text=rewritten_text,
            token_usage=response_token_usage(response),
        )
