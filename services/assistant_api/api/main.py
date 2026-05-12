"""
Author: L. Saetta
Date Modified: 2026-05-12
License: MIT
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator
from datetime import date
from functools import lru_cache

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from services.assistant_api.api.schemas import (
    ChatRequest,
    ChatResponse,
    HealthResponse,
    NutritionDiaryEntryRequest,
    NutritionDiaryEntryResponse,
    NutritionDiaryEntryUpdateRequest,
    NutritionPlanResponse,
)
from services.assistant_api.nutrition.diary import (
    NutritionDiaryEntry,
    NutritionDiaryEntryInput,
    NutritionDiaryService,
)
from services.assistant_api.nutrition.plan import NutritionPlan, NutritionPlanService
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


@lru_cache(maxsize=1)
def get_nutrition_diary_service() -> NutritionDiaryService:
    """Create the local nutrition diary persistence service once."""
    load_dotenv()
    database_path = os.getenv("NUTRITION_DB_PATH", "/data/garmin_ai_coach.db")
    LOGGER.info("nutrition diary service init database_path=%s", database_path)
    return NutritionDiaryService(database_path)


@lru_cache(maxsize=1)
def get_nutrition_plan_service() -> NutritionPlanService:
    """Create the local nutrition plan persistence service once."""
    load_dotenv()
    database_path = os.getenv("NUTRITION_DB_PATH", "/data/garmin_ai_coach.db")
    LOGGER.info("nutrition plan service init database_path=%s", database_path)
    return NutritionPlanService(database_path)


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

    @api.post(
        "/nutrition/diary-entries",
        response_model=NutritionDiaryEntryResponse,
    )
    async def upsert_nutrition_diary_entry(
        request: NutritionDiaryEntryRequest,
        diary_service: NutritionDiaryService = Depends(get_nutrition_diary_service),
    ) -> NutritionDiaryEntryResponse:
        """Create or update a nutrition diary entry for the selected day."""
        LOGGER.info("nutrition diary upsert request entry_date=%s", request.entry_date)
        entry = diary_service.upsert_entry(
            NutritionDiaryEntryInput(
                entry_date=request.entry_date,
                training_type=request.training_type,
                meals_text=request.meals_text,
                notes=request.notes,
            )
        )
        return _diary_entry_response(entry)

    @api.get(
        "/nutrition/diary-entries/{entry_date}",
        response_model=NutritionDiaryEntryResponse,
    )
    async def get_nutrition_diary_entry(
        entry_date: date,
        diary_service: NutritionDiaryService = Depends(get_nutrition_diary_service),
    ) -> NutritionDiaryEntryResponse:
        """Return the nutrition diary entry for one day."""
        LOGGER.info("nutrition diary get request entry_date=%s", entry_date)
        entry = diary_service.get_entry(entry_date)
        if entry is None:
            raise HTTPException(
                status_code=404, detail="Nutrition diary entry not found"
            )
        return _diary_entry_response(entry)

    @api.put(
        "/nutrition/diary-entries/{entry_date}",
        response_model=NutritionDiaryEntryResponse,
    )
    async def update_nutrition_diary_entry(
        entry_date: date,
        request: NutritionDiaryEntryUpdateRequest,
        diary_service: NutritionDiaryService = Depends(get_nutrition_diary_service),
    ) -> NutritionDiaryEntryResponse:
        """Create or update the nutrition diary entry for one URL date."""
        LOGGER.info("nutrition diary update request entry_date=%s", entry_date)
        entry = diary_service.upsert_entry(
            NutritionDiaryEntryInput(
                entry_date=entry_date,
                training_type=request.training_type,
                meals_text=request.meals_text,
                notes=request.notes,
            )
        )
        return _diary_entry_response(entry)

    @api.post(
        "/nutrition/plan",
        response_model=NutritionPlanResponse,
    )
    async def upload_nutrition_plan(
        file: UploadFile = File(...),
        plan_service: NutritionPlanService = Depends(get_nutrition_plan_service),
    ) -> NutritionPlanResponse:
        """Replace the current nutrition plan with an uploaded PDF."""
        content_type = file.content_type or "application/octet-stream"
        if content_type != "application/pdf":
            raise HTTPException(
                status_code=415, detail="Only PDF uploads are supported"
            )

        pdf_bytes = await file.read()
        if not pdf_bytes:
            raise HTTPException(status_code=422, detail="Uploaded PDF is empty")

        LOGGER.info("nutrition plan upload request filename=%s", file.filename)
        try:
            plan = plan_service.replace_current_plan(
                original_filename=file.filename or "nutrition-plan.pdf",
                content_type=content_type,
                pdf_bytes=pdf_bytes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        return _nutrition_plan_response(plan)

    @api.get(
        "/nutrition/plan/current",
        response_model=NutritionPlanResponse,
    )
    async def get_current_nutrition_plan(
        plan_service: NutritionPlanService = Depends(get_nutrition_plan_service),
    ) -> NutritionPlanResponse:
        """Return the current nutrition plan extracted from an uploaded PDF."""
        LOGGER.info("nutrition plan get current request")
        plan = plan_service.get_current_plan()
        if plan is None:
            raise HTTPException(status_code=404, detail="Nutrition plan not found")
        return _nutrition_plan_response(plan)

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


def _diary_entry_response(
    entry: NutritionDiaryEntry,
) -> NutritionDiaryEntryResponse:
    """Convert a stored diary entry into the API response schema."""
    return NutritionDiaryEntryResponse(
        id=entry.id,
        entry_date=entry.entry_date,
        training_type=entry.training_type,
        meals_text=entry.meals_text,
        notes=entry.notes,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _nutrition_plan_response(plan: NutritionPlan) -> NutritionPlanResponse:
    """Convert a stored nutrition plan into the API response schema."""
    return NutritionPlanResponse(
        id=plan.id,
        original_filename=plan.original_filename,
        content_type=plan.content_type,
        file_sha256=plan.file_sha256,
        extracted_text=plan.extracted_text,
        uploaded_at=plan.uploaded_at,
        updated_at=plan.updated_at,
    )


app = create_app()
