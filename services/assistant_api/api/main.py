"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from functools import lru_cache

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
from services.assistant_api.orchestration.training_data import LocalTrainingDataClient
from services.garmin_api.training_data_provider import TrainingDataProvider
from services.shared.llm import get_inference_client

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure simple timestamped API logs."""
    load_dotenv()
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def load_settings() -> AssistantSettings:
    """Load assistant API settings from environment variables."""
    load_dotenv()
    return AssistantSettings(
        model_id=os.getenv("OCI_MODEL_ID", "openai.gpt-5.4"),
    )


@lru_cache(maxsize=1)
def get_training_data_provider() -> TrainingDataProvider:
    """Create the local Garmin training data provider once per process."""
    load_dotenv()
    LOGGER.info("training provider init start")
    provider = TrainingDataProvider(
        username=os.getenv("GARMIN_USERNAME"),
        password=os.getenv("GARMIN_PASSWORD"),
        session_storage_path=os.getenv("GARMIN_SESSION_STORAGE_PATH"),
    )
    LOGGER.info("training provider init done")
    return provider


def get_orchestrator() -> AssistantOrchestrator:
    """Create the assistant orchestrator used by request handlers."""
    settings = load_settings()
    LOGGER.info("orchestrator create model_id=%s", settings.model_id)
    return AssistantOrchestrator(
        settings=settings,
        inference_client=get_inference_client(),
        training_client=LocalTrainingDataClient(get_training_data_provider()),
    )


def create_app() -> FastAPI:
    """Create the FastAPI application for uvicorn."""
    configure_logging()
    api = FastAPI(
        title="Garmin AI Coach Assistant API",
        version="0.1.0",
    )

    @api.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        """Return a lightweight health response for monitoring tools."""
        LOGGER.info("health check")
        return HealthResponse(status="ok", service="assistant_api")

    @api.post("/chat", response_model=ChatResponse)
    async def chat(
        request: ChatRequest,
        orchestrator: AssistantOrchestrator = Depends(get_orchestrator),
    ) -> ChatResponse:
        """Return a complete assistant response for non-streaming clients."""
        LOGGER.info("chat request received conversation_id=%s", request.conversation_id)
        return await orchestrator.complete_chat(request)

    @api.post("/chat/stream")
    async def chat_stream(
        request: ChatRequest,
        orchestrator: AssistantOrchestrator = Depends(get_orchestrator),
    ) -> StreamingResponse:
        """Stream an assistant response as server-sent events."""
        LOGGER.info(
            "chat stream request received conversation_id=%s",
            request.conversation_id,
        )
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
    try:
        async for event in orchestrator.stream_chat(request):
            payload = event.model_dump(exclude_none=True)
            yield f"event: {event.type}\ndata: {json.dumps(payload)}\n\n"
    except RuntimeError as exc:
        LOGGER.exception("chat stream runtime error")
        payload = {
            "type": "error",
            "conversation_id": request.conversation_id or "",
            "delta": str(exc),
        }
        yield f"event: error\ndata: {json.dumps(payload)}\n\n"


app = create_app()
