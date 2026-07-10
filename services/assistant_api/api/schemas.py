"""
Author: L. Saetta
Date Modified: 2026-07-10
License: MIT
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

MessageRole = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    """One message from the frontend conversation history."""

    role: MessageRole
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    """Chat request accepted by the assistant backend."""

    message: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(default_factory=list)
    conversation_id: str | None = None


class DataSource(BaseModel):
    """Safe description of a data source used to ground an answer."""

    type: str
    description: str


class TokenUsage(BaseModel):
    """Token usage returned by Responses API calls for one assistant turn."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class ChatResponse(BaseModel):
    """Non-streaming representation of a completed assistant answer."""

    answer: str
    conversation_id: str
    data_sources: list[DataSource] = Field(default_factory=list)
    token_usage: TokenUsage | None = None


class ChatStreamEvent(BaseModel):
    """Single server-sent event payload emitted by the chat endpoint."""

    type: Literal["message_delta", "message_done", "error"]
    conversation_id: str
    delta: str | None = None
    answer: str | None = None
    data_sources: list[DataSource] = Field(default_factory=list)
    token_usage: TokenUsage | None = None


class HealthResponse(BaseModel):
    """Health response consumed by local monitoring tools."""

    status: Literal["ok"]
    service: Literal["assistant_api"]


class TrainingSportMetricsResponse(BaseModel):
    """Aggregate training metrics for one dashboard sport bucket."""

    sport: Literal["running", "cycling", "swimming"]
    label: str
    activity_count: int
    hours: float
    total_duration_seconds: float
    total_training_load: float | None = None
    training_load_per_hour: float | None = None
    weighted_average_heart_rate: float | None = None
    average_aerobic_training_effect: float | None = None
    average_anaerobic_training_effect: float | None = None
    moderate_intensity_minutes: float
    vigorous_intensity_minutes: float
    intensity_score: float | None = None
    intensity_source: Literal["training_load", "intensity_minutes", "none"]


class TrainingMetricsResponse(BaseModel):
    """Aggregate training metrics returned for a selected date range."""

    begin_date: date
    end_date: date
    sports: list[TrainingSportMetricsResponse]


class GarminCredentialRequest(BaseModel):
    """Request payload for saving Garmin Connect credentials."""

    garmin_username: str = Field(min_length=1, max_length=320)
    garmin_password: str = Field(min_length=1, max_length=1024)


class GarminCredentialStatusResponse(BaseModel):
    """Safe Garmin credential metadata returned to frontend clients."""

    configured: bool
    garmin_username: str | None = None
    updated_at: datetime | None = None


class GarminCredentialTestResponse(BaseModel):
    """Result of testing the current user's stored Garmin credentials."""

    ok: bool
    message: str


class NutritionDiaryEntryRequest(BaseModel):
    """Request payload for creating or updating one nutrition diary day."""

    entry_date: date
    training_type: str = Field(min_length=1, max_length=80)
    meals_text: str = Field(min_length=1, max_length=12000)
    notes: str = Field(default="", max_length=4000)


class NutritionDiaryEntryUpdateRequest(BaseModel):
    """Request payload for updating the nutrition diary day in the URL."""

    training_type: str = Field(min_length=1, max_length=80)
    meals_text: str = Field(min_length=1, max_length=12000)
    notes: str = Field(default="", max_length=4000)


class NutritionDiaryRewriteRequest(BaseModel):
    """Request payload for rewriting one diary day's meal text."""

    training_type: str = Field(min_length=1, max_length=80)
    meals_text: str = Field(min_length=1, max_length=12000)
    notes: str = Field(default="", max_length=4000)


class NutritionDiaryRewriteResponse(BaseModel):
    """Rewritten meal text returned by the assistant API."""

    rewritten_meals_text: str
    token_usage: TokenUsage | None = None


class NutritionDiaryEntryResponse(BaseModel):
    """Stored nutrition diary entry returned by the assistant API."""

    id: int
    entry_date: date
    training_type: str
    meals_text: str
    notes: str
    created_at: datetime
    updated_at: datetime


class NutritionPlanResponse(BaseModel):
    """Stored current nutrition plan returned by the assistant API."""

    id: int
    original_filename: str
    content_type: str
    file_sha256: str
    extracted_text: str
    uploaded_at: datetime
    updated_at: datetime
