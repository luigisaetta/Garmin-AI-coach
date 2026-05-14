"""
Author: L. Saetta
Date Modified: 2026-05-14
License: MIT
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator, Callable
from datetime import date
from functools import lru_cache
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from services.assistant_api.api.schemas import (
    ChatRequest,
    ChatResponse,
    GarminCredentialRequest,
    GarminCredentialStatusResponse,
    GarminCredentialTestResponse,
    HealthResponse,
    NutritionDiaryEntryRequest,
    NutritionDiaryEntryResponse,
    NutritionDiaryEntryUpdateRequest,
    NutritionPlanResponse,
)
from services.assistant_api.identity.garmin_credentials import (
    GarminCredentialError,
    GarminCredentialRepository,
    GarminCredentialStatus,
    load_garmin_credential_encryption_key,
)
from services.assistant_api.nutrition.diary import (
    NutritionDiaryEntry,
    NutritionDiaryEntryInput,
    NutritionDiaryService,
)
from services.assistant_api.nutrition.analysis import (
    NutritionAnalysisSettings,
    NutritionAnalysisSubAgent,
)
from services.assistant_api.nutrition.plan import NutritionPlan, NutritionPlanService
from services.assistant_api.identity.users import ApplicationUser, UserRepository
from services.assistant_api.orchestration.chat import (
    AssistantOrchestrator,
    AssistantSettings,
)
from services.assistant_api.orchestration.training_data import (
    LocalTrainingDataClient,
    UserScopedTrainingDataClient,
)
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


def create_training_data_provider(
    *,
    username: str | None,
    password: str | None,
    session_storage_path: str | None,
) -> TrainingDataProvider:
    """Create a Garmin training data provider for one authenticated user."""
    load_dotenv()
    LOGGER.info("training provider init start")
    provider = TrainingDataProvider(
        username=username,
        password=password,
        session_storage_path=session_storage_path,
    )
    LOGGER.info("training provider init done")
    return provider


def get_training_data_provider_factory() -> Callable[..., TrainingDataProvider]:
    """Return the provider factory used for Garmin credential tests."""
    return create_training_data_provider


@lru_cache(maxsize=1)
def get_training_data_provider() -> TrainingDataProvider:
    """Create the legacy global Garmin provider for local compatibility."""
    load_dotenv()
    return create_training_data_provider(
        username=os.getenv("GARMIN_USERNAME"),
        password=os.getenv("GARMIN_PASSWORD"),
        session_storage_path=os.getenv("GARMIN_SESSION_STORAGE_PATH"),
    )


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


@lru_cache(maxsize=1)
def get_user_repository() -> UserRepository:
    """Create the local user repository used by authenticated requests."""
    load_dotenv()
    database_path = os.getenv("APP_DB_PATH", "/data/garmin_ai_coach.db")
    LOGGER.info("user repository init database_path=%s", database_path)
    return UserRepository(database_path)


@lru_cache(maxsize=1)
def get_garmin_credential_repository() -> GarminCredentialRepository:
    """Create the encrypted Garmin credential repository."""
    load_dotenv()
    database_path = os.getenv("APP_DB_PATH", "/data/garmin_ai_coach.db")
    return GarminCredentialRepository(
        database_path,
        encryption_key=load_garmin_credential_encryption_key(),
    )


def get_current_user(
    authenticated_username: Annotated[
        str | None,
        Header(alias="X-Authenticated-User"),
    ] = None,
    user_repository: UserRepository = Depends(get_user_repository),
) -> ApplicationUser:
    """Resolve the current backend user from the trusted proxy header."""
    if authenticated_username is None or not authenticated_username.strip():
        raise HTTPException(status_code=401, detail="Authenticated user is required")

    user = user_repository.get_by_username(authenticated_username)
    if user is None or not user.is_active:
        raise HTTPException(status_code=403, detail="Authenticated user is not allowed")

    return user


def get_orchestrator() -> AssistantOrchestrator:
    """Create the assistant orchestrator used by request handlers."""
    settings = load_settings()
    inference_client = get_inference_client()
    if os.getenv("GARMIN_CREDENTIAL_ENCRYPTION_KEY") or os.getenv(
        "GARMIN_CREDENTIAL_ENCRYPTION_KEY_FILE"
    ):
        training_client = UserScopedTrainingDataClient(
            credential_repository=get_garmin_credential_repository(),
            session_storage_root=os.getenv(
                "GARMIN_SESSION_STORAGE_ROOT",
                "/data/garmin-sessions",
            ),
            provider_factory=get_training_data_provider_factory(),
        )
    else:
        training_client = LocalTrainingDataClient(get_training_data_provider())
    LOGGER.info("orchestrator create model_id=%s", settings.model_id)
    return AssistantOrchestrator(
        settings=settings,
        inference_client=inference_client,
        training_client=training_client,
        nutrition_analysis_agent=NutritionAnalysisSubAgent.create(
            plan_service=get_nutrition_plan_service(),
            diary_service=get_nutrition_diary_service(),
            training_client=training_client,
            inference_client=inference_client,
            settings=NutritionAnalysisSettings(model_id=settings.model_id),
        ),
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

    @api.get(
        "/account/garmin-credentials",
        response_model=GarminCredentialStatusResponse,
    )
    async def get_garmin_credentials_status(
        current_user: ApplicationUser = Depends(get_current_user),
        repository: GarminCredentialRepository = Depends(
            get_garmin_credential_repository
        ),
    ) -> GarminCredentialStatusResponse:
        """Return safe Garmin credential status for the current user."""
        return _garmin_credential_status_response(
            repository.get_status(user_id=current_user.id)
        )

    @api.put(
        "/account/garmin-credentials",
        response_model=GarminCredentialStatusResponse,
    )
    async def save_garmin_credentials(
        request: GarminCredentialRequest,
        current_user: ApplicationUser = Depends(get_current_user),
        repository: GarminCredentialRepository = Depends(
            get_garmin_credential_repository
        ),
    ) -> GarminCredentialStatusResponse:
        """Save or replace Garmin credentials for the current user."""
        try:
            status = repository.save_credentials(
                user_id=current_user.id,
                garmin_username=request.garmin_username,
                garmin_password=request.garmin_password,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _garmin_credential_status_response(status)

    @api.delete("/account/garmin-credentials", status_code=204)
    async def delete_garmin_credentials(
        current_user: ApplicationUser = Depends(get_current_user),
        repository: GarminCredentialRepository = Depends(
            get_garmin_credential_repository
        ),
    ) -> None:
        """Delete stored Garmin credentials for the current user."""
        repository.delete_credentials(user_id=current_user.id)

    @api.post(
        "/account/garmin-credentials/test",
        response_model=GarminCredentialTestResponse,
    )
    async def test_garmin_credentials(
        current_user: ApplicationUser = Depends(get_current_user),
        repository: GarminCredentialRepository = Depends(
            get_garmin_credential_repository
        ),
        provider_factory: Callable[..., TrainingDataProvider] = Depends(
            get_training_data_provider_factory
        ),
    ) -> GarminCredentialTestResponse:
        """Validate that stored Garmin credentials can initialize the provider."""
        credentials = repository.get_credentials(user_id=current_user.id)
        if credentials is None:
            raise HTTPException(
                status_code=404,
                detail="Garmin credentials are not configured for this user.",
            )

        session_path = os.getenv("GARMIN_SESSION_STORAGE_ROOT", "/data/garmin-sessions")
        try:
            provider_factory(
                username=credentials.garmin_username,
                password=credentials.garmin_password,
                session_storage_path=str(
                    os.path.join(session_path, str(current_user.id))
                ),
            )
        except (GarminCredentialError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return GarminCredentialTestResponse(
            ok=True,
            message="Garmin credentials are valid.",
        )

    @api.post("/chat", response_model=ChatResponse)
    async def chat(
        request: ChatRequest,
        current_user: ApplicationUser = Depends(get_current_user),
        orchestrator: AssistantOrchestrator = Depends(get_orchestrator),
    ) -> ChatResponse:
        """Return a complete assistant response for non-streaming clients."""
        LOGGER.info("chat request received conversation_id=%s", request.conversation_id)
        return await orchestrator.complete_chat(request, user_id=current_user.id)

    @api.post("/chat/stream")
    async def chat_stream(
        request: ChatRequest,
        current_user: ApplicationUser = Depends(get_current_user),
        orchestrator: AssistantOrchestrator = Depends(get_orchestrator),
    ) -> StreamingResponse:
        """Stream an assistant response as server-sent events."""
        LOGGER.info(
            "chat stream request received conversation_id=%s",
            request.conversation_id,
        )
        return StreamingResponse(
            _sse_events(orchestrator, request, user_id=current_user.id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    @api.post(
        "/nutrition/diary-entries",
        response_model=NutritionDiaryEntryResponse,
    )
    async def upsert_nutrition_diary_entry(
        request: NutritionDiaryEntryRequest,
        current_user: ApplicationUser = Depends(get_current_user),
        diary_service: NutritionDiaryService = Depends(get_nutrition_diary_service),
    ) -> NutritionDiaryEntryResponse:
        """Create or update a nutrition diary entry for the selected day."""
        LOGGER.info("nutrition diary upsert request entry_date=%s", request.entry_date)
        entry = diary_service.upsert_entry(
            user_id=current_user.id,
            entry_input=NutritionDiaryEntryInput(
                entry_date=request.entry_date,
                training_type=request.training_type,
                meals_text=request.meals_text,
                notes=request.notes,
            ),
        )
        return _diary_entry_response(entry)

    @api.get(
        "/nutrition/diary-entries/{entry_date}",
        response_model=NutritionDiaryEntryResponse,
    )
    async def get_nutrition_diary_entry(
        entry_date: date,
        current_user: ApplicationUser = Depends(get_current_user),
        diary_service: NutritionDiaryService = Depends(get_nutrition_diary_service),
    ) -> NutritionDiaryEntryResponse:
        """Return the nutrition diary entry for one day."""
        LOGGER.info("nutrition diary get request entry_date=%s", entry_date)
        entry = diary_service.get_entry(user_id=current_user.id, entry_date=entry_date)
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
        current_user: ApplicationUser = Depends(get_current_user),
        diary_service: NutritionDiaryService = Depends(get_nutrition_diary_service),
    ) -> NutritionDiaryEntryResponse:
        """Create or update the nutrition diary entry for one URL date."""
        LOGGER.info("nutrition diary update request entry_date=%s", entry_date)
        entry = diary_service.upsert_entry(
            user_id=current_user.id,
            entry_input=NutritionDiaryEntryInput(
                entry_date=entry_date,
                training_type=request.training_type,
                meals_text=request.meals_text,
                notes=request.notes,
            ),
        )
        return _diary_entry_response(entry)

    @api.post(
        "/nutrition/plan",
        response_model=NutritionPlanResponse,
    )
    async def upload_nutrition_plan(
        file: UploadFile = File(...),
        current_user: ApplicationUser = Depends(get_current_user),
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
                user_id=current_user.id,
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
        current_user: ApplicationUser = Depends(get_current_user),
        plan_service: NutritionPlanService = Depends(get_nutrition_plan_service),
    ) -> NutritionPlanResponse:
        """Return the current nutrition plan extracted from an uploaded PDF."""
        LOGGER.info("nutrition plan get current request")
        plan = plan_service.get_current_plan(user_id=current_user.id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Nutrition plan not found")
        return _nutrition_plan_response(plan)

    return api


async def _sse_events(
    orchestrator: AssistantOrchestrator,
    request: ChatRequest,
    *,
    user_id: int,
) -> AsyncIterator[str]:
    """Serialize assistant stream events as server-sent events."""
    yield ": connected\n\n"
    try:
        async for event in orchestrator.stream_chat(request, user_id=user_id):
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


def _garmin_credential_status_response(
    status: GarminCredentialStatus,
) -> GarminCredentialStatusResponse:
    """Convert safe Garmin credential metadata to an API response."""
    return GarminCredentialStatusResponse(
        configured=status.configured,
        garmin_username=status.garmin_username,
        updated_at=status.updated_at,
    )


app = create_app()
