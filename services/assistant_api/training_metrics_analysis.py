"""
Author: L. Saetta
Date Modified: 2026-07-10
License: MIT
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Literal

from services.assistant_api.api.schemas import TokenUsage
from services.assistant_api.orchestration.chat import response_token_usage
from services.assistant_api.training_metrics import TrainingMetricsSummary

LOGGER = logging.getLogger(__name__)

TrainingMetricsAnalysisLanguage = Literal["italian", "english"]

TRAINING_METRICS_ANALYSIS_PROMPT = """
You are a concise endurance training coach for a personal Garmin training
dashboard.

Analyze only the aggregate metrics in the input payload. Do not invent workouts,
paces, zones, personal records, fatigue, illness, injury status, sleep, HRV, or
readiness values that are not present in the payload.

This is coaching reflection, not medical advice. Avoid diagnosis and avoid
prescriptive clinical statements. If data is missing, say so plainly.

Write in the response_language provided by the payload.

Return a short, practical analysis with these section meanings, translated into
the response language:
1. Period summary
2. Sport distribution
3. Intensity and useful signals
4. Next focus

Keep the full answer under 180 words. Prefer concrete observations tied to the
numbers. Mention limitations when training load, heart rate, or training effect
data is missing for a sport.
""".strip()


class TrainingMetricsAnalysisError(RuntimeError):
    """Raised when the training metrics analysis cannot complete."""


@dataclass(frozen=True)
class TrainingMetricsAnalysisSettings:
    """Runtime settings for training metrics analysis."""

    model_id: str


@dataclass(frozen=True)
class TrainingMetricsAnalysisResult:
    """LLM-generated analysis for one training metrics summary."""

    analysis: str
    token_usage: TokenUsage | None = None


class TrainingMetricsAnalysisService:  # pylint: disable=too-few-public-methods
    """Generate a compact LLM analysis from aggregate training metrics."""

    def __init__(
        self,
        *,
        inference_client: Any,
        settings: TrainingMetricsAnalysisSettings,
    ) -> None:
        self._inference_client = inference_client
        self._settings = settings

    async def analyze(
        self,
        *,
        summary: TrainingMetricsSummary,
        response_language: TrainingMetricsAnalysisLanguage = "italian",
    ) -> TrainingMetricsAnalysisResult:
        """Generate a synthetic coaching analysis for aggregate metrics."""
        if response_language not in {"italian", "english"}:
            raise ValueError("response_language must be 'italian' or 'english'")

        LOGGER.info(
            "training metrics analysis request begin_date=%s end_date=%s",
            summary.begin_date,
            summary.end_date,
        )
        response = self._inference_client.responses.create(
            model=self._settings.model_id,
            instructions=TRAINING_METRICS_ANALYSIS_PROMPT,
            input=[
                {
                    "role": "user",
                    "content": json.dumps(
                        build_training_metrics_analysis_payload(
                            summary=summary,
                            response_language=response_language,
                        ),
                        ensure_ascii=False,
                        default=str,
                    ),
                }
            ],
        )
        analysis = str(getattr(response, "output_text", "")).strip()
        if not analysis:
            raise TrainingMetricsAnalysisError(
                "Responses API returned an empty training metrics analysis."
            )

        LOGGER.info(
            "training metrics analysis done analysis_length=%d",
            len(analysis),
        )
        return TrainingMetricsAnalysisResult(
            analysis=analysis,
            token_usage=response_token_usage(response),
        )


def build_training_metrics_analysis_payload(
    *,
    summary: TrainingMetricsSummary,
    response_language: TrainingMetricsAnalysisLanguage,
) -> dict[str, Any]:
    """Build the compact payload sent to the training metrics analysis model."""
    return {
        "period": {
            "begin_date": summary.begin_date.isoformat(),
            "end_date": summary.end_date.isoformat(),
        },
        "response_language": response_language,
        "sports": [
            {
                "sport": sport.sport,
                "label": sport.label,
                "activity_count": sport.activity_count,
                "hours": sport.hours,
                "total_training_load": sport.total_training_load,
                "training_load_per_hour": sport.training_load_per_hour,
                "weighted_average_heart_rate": sport.weighted_average_heart_rate,
                "average_aerobic_training_effect": (
                    sport.average_aerobic_training_effect
                ),
                "average_anaerobic_training_effect": (
                    sport.average_anaerobic_training_effect
                ),
                "moderate_intensity_minutes": sport.moderate_intensity_minutes,
                "vigorous_intensity_minutes": sport.vigorous_intensity_minutes,
                "intensity_score": sport.intensity_score,
                "intensity_source": sport.intensity_source,
            }
            for sport in summary.sports
        ],
    }
