"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

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


class ChatResponse(BaseModel):
    """Non-streaming representation of a completed assistant answer."""

    answer: str
    conversation_id: str
    data_sources: list[DataSource] = Field(default_factory=list)


class ChatStreamEvent(BaseModel):
    """Single server-sent event payload emitted by the chat endpoint."""

    type: Literal["message_delta", "message_done", "error"]
    conversation_id: str
    delta: str | None = None
    answer: str | None = None
    data_sources: list[DataSource] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Health response consumed by local monitoring tools."""

    status: Literal["ok"]
    service: Literal["assistant_api"]
