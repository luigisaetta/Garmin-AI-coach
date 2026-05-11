"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator

from dotenv import load_dotenv
from fastapi import Depends, FastAPI
from fastapi.responses import StreamingResponse

from services.assistant_api.api.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
)
from services.assistant_api.orchestration.chat import (
    AssistantOrchestrator,
    AssistantSettings,
)


def load_settings() -> AssistantSettings:
    """Load assistant API settings from environment variables."""
    load_dotenv()
    return AssistantSettings(
        model_id=os.getenv("OCI_MODEL_ID", "openai.gpt-5.4"),
        garmin_api_url=os.getenv("GARMIN_API_URL", "http://garmin_api:8000"),
    )


def get_orchestrator() -> AssistantOrchestrator:
    """Create the assistant orchestrator used by request handlers."""
    return AssistantOrchestrator()


def create_app() -> FastAPI:
    """Create the FastAPI application for uvicorn."""
    api = FastAPI(
        title="Garmin AI Coach Assistant API",
        version="0.1.0",
    )

    @api.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Return a lightweight health response for monitoring tools."""
        return HealthResponse(status="ok", service="assistant_api")

    @api.post("/chat", response_model=ChatResponse)
    async def chat(
        request: ChatRequest,
        orchestrator: AssistantOrchestrator = Depends(get_orchestrator),
    ) -> ChatResponse:
        """Return a complete assistant response for non-streaming clients."""
        return await orchestrator.complete_chat(request)

    @api.post("/chat/stream")
    async def chat_stream(
        request: ChatRequest,
        orchestrator: AssistantOrchestrator = Depends(get_orchestrator),
    ) -> StreamingResponse:
        """Stream an assistant response as server-sent events."""
        return StreamingResponse(
            _sse_events(orchestrator, request),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    return api


async def _sse_events(
    orchestrator: AssistantOrchestrator,
    request: ChatRequest,
) -> AsyncIterator[str]:
    """Serialize assistant stream events as server-sent events."""
    async for event in orchestrator.stream_chat(request):
        payload = event.model_dump(exclude_none=True)
        yield f"event: {event.type}\ndata: {json.dumps(payload)}\n\n"


app = create_app()
