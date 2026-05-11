"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import uuid4

from services.assistant_api.api.schemas import (
    ChatRequest,
    ChatResponse,
    ChatStreamEvent,
)


@dataclass(frozen=True)
class AssistantSettings:
    """Runtime settings for the assistant orchestration layer."""

    model_id: str
    garmin_api_url: str


class AssistantOrchestrator:
    """Initial assistant orchestration boundary for frontend chat requests.

    The first implementation keeps the HTTP contract stable and stream-capable
    while the next step wires this boundary to OCI Responses API calls and
    local Garmin API tool calls.
    """

    async def complete_chat(self, request: ChatRequest) -> ChatResponse:
        """Return a complete chat answer for callers that do not stream."""
        conversation_id = request.conversation_id or str(uuid4())
        answer = self._build_bootstrap_answer(request)
        return ChatResponse(answer=answer, conversation_id=conversation_id)

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]:
        """Stream the assistant answer as small frontend-friendly chunks."""
        response = await self.complete_chat(request)

        for chunk in self._split_answer(response.answer):
            yield ChatStreamEvent(
                type="message_delta",
                conversation_id=response.conversation_id,
                delta=chunk,
            )

        yield ChatStreamEvent(
            type="message_done",
            conversation_id=response.conversation_id,
            answer=response.answer,
            data_sources=response.data_sources,
        )

    @staticmethod
    def _build_bootstrap_answer(request: ChatRequest) -> str:
        """Build the initial deterministic answer before model wiring exists."""
        history_count = len(request.messages)
        return (
            "Assistant API is ready to receive Garmin coaching questions. "
            "The current endpoint accepts the latest message and "
            f"{history_count} history message(s), and streams responses for "
            "the frontend. Garmin API tool calls and OCI Responses API "
            "generation will be connected behind this same boundary next."
        )

    @staticmethod
    def _split_answer(answer: str) -> list[str]:
        """Split an answer into stable chunks without dropping spaces."""
        words = answer.split(" ")
        chunks: list[str] = []
        current: list[str] = []

        for word in words:
            current.append(word)
            if len(" ".join(current)) >= 48:
                chunks.append(" ".join(current) + " ")
                current = []

        if current:
            chunks.append(" ".join(current))

        return chunks
