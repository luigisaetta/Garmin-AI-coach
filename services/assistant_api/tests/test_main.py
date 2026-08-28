"""
Author: L. Saetta
Date Modified: 2026-07-10
License: MIT
"""

from __future__ import annotations

# pylint: disable=too-many-lines

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from garminconnect.exceptions import GarminConnectConnectionError

from services.assistant_api.api.main import (
    create_app,
    get_current_user,
    get_garmin_credential_repository,
    get_nutrition_diary_rewrite_service,
    get_nutrition_diary_service,
    get_nutrition_plan_service,
    get_orchestrator,
    get_training_client,
    get_training_data_provider_factory,
    get_training_metrics_analysis_service,
    get_training_metrics_service,
    get_training_trends_service,
    get_user_repository,
)
from services.assistant_api.api.schemas import (
    ChatRequest,
    ChatResponse,
    ChatStreamEvent,
)
from services.assistant_api.identity.garmin_credentials import (
    GarminCredentialRepository,
)
from services.assistant_api.identity.users import ApplicationUser, UserRepository
from services.assistant_api.nutrition.diary import NutritionDiaryService
from services.assistant_api.nutrition.plan import NutritionPlanService
from services.assistant_api.nutrition.rewrite import NutritionDiaryRewriteResult
from services.assistant_api.tests.database import build_test_database
from services.assistant_api.training_metrics import TrainingMetricsService
from services.assistant_api.training_metrics_analysis import (
    TrainingMetricsAnalysisResult,
)
from services.assistant_api.training_trends import (
    TrainingTrendsSummary,
    WeeklySportTrend,
    WeeklyTrainingTrend,
)


class FakeOrchestrator:
    """Predictable orchestrator used by HTTP endpoint tests."""

    async def complete_chat(
        self, request: ChatRequest, *, user_id: int
    ) -> ChatResponse:
        """Return a deterministic non-streaming response."""
        return ChatResponse(
            answer=(
                f"reply to {request.message} for user {user_id} "
                f"with {len(request.messages)} "
                "history message(s)"
            ),
            conversation_id=request.conversation_id or "generated-id",
        )

    async def stream_chat(
        self,
        request: ChatRequest,
        *,
        user_id: int,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Return two deterministic events for streaming assertions."""
        conversation_id = request.conversation_id or "generated-id"
        yield ChatStreamEvent(
            type="message_delta",
            conversation_id=conversation_id,
            delta=f"hello user {user_id}",
        )
        yield ChatStreamEvent(
            type="message_done",
            conversation_id=conversation_id,
            answer=f"reply to {request.message}",
        )


class FailingOrchestrator:  # pylint: disable=too-few-public-methods
    """Orchestrator that simulates an unexpected streaming failure."""

    async def stream_chat(
        self,
        request: ChatRequest,
        *,
        user_id: int,
    ) -> AsyncIterator[ChatStreamEvent]:
        """Raise a runtime error during SSE generation."""
        _ = user_id
        if request.conversation_id == "__never__":
            yield ChatStreamEvent(type="message_delta", conversation_id="unused")
        raise RuntimeError("backend unavailable")


class FakeTrainingProvider:  # pylint: disable=too-few-public-methods
    """Fake Garmin provider used by credential test endpoints."""

    calls: list[dict[str, str | None]] = []

    def __init__(
        self,
        *,
        username: str | None,
        password: str | None,
        session_storage_path: str | None,
    ) -> None:
        FakeTrainingProvider.calls.append(
            {
                "username": username,
                "password": password,
                "session_storage_path": session_storage_path,
            }
        )


class FailingGarminTrainingProvider:  # pylint: disable=too-few-public-methods
    """Fake provider that simulates Garmin rate limiting credential tests."""

    def __init__(
        self,
        *,
        username: str | None,
        password: str | None,
        session_storage_path: str | None,
    ) -> None:
        _ = (username, password, session_storage_path)
        raise GarminConnectConnectionError(
            "Login failed: CAPTCHA_REQUIRED and Mobile login returned 429"
        )


class FakeDiaryRewriteService:  # pylint: disable=too-few-public-methods
    """Fake diary rewrite service used by endpoint tests."""

    calls: list[dict[str, str]] = []

    async def rewrite(self, rewrite_input) -> NutritionDiaryRewriteResult:
        """Record the rewrite request and return edited text."""
        FakeDiaryRewriteService.calls.append(
            {
                "entry_date": rewrite_input.entry_date,
                "training_type": rewrite_input.training_type,
                "meals_text": rewrite_input.meals_text,
                "notes": rewrite_input.notes,
            }
        )
        return NutritionDiaryRewriteResult(
            rewritten_meals_text="Colazione: yogurt e miele."
        )


class FakeMetricsTrainingClient:  # pylint: disable=too-few-public-methods
    """Fake training client used by metrics endpoint tests."""

    calls: list[dict[str, str | int | None]] = []

    async def list_activities(
        self,
        *,
        user_id: int,
        begin_date: str,
        end_date: str,
        activity_type: str | None = None,
    ) -> list[dict[str, object]]:
        """Return dashboard activities and record the user-scoped query."""
        FakeMetricsTrainingClient.calls.append(
            {
                "user_id": user_id,
                "begin_date": begin_date,
                "end_date": end_date,
                "activity_type": activity_type,
            }
        )
        return [
            {
                "activityType": {"typeKey": "running"},
                "duration": 3600,
                "activityTrainingLoad": 120,
                "averageHR": 148,
                "aerobicTrainingEffect": 3.1,
                "anaerobicTrainingEffect": 0.7,
            },
            {
                "activityType": {"typeKey": "indoor_cycling"},
                "duration": 1800,
                "averageHR": 132,
                "moderateIntensityMinutes": 10,
                "vigorousIntensityMinutes": 20,
            },
        ]


class FakeTrendsTrainingClient:  # pylint: disable=too-few-public-methods
    """Fake training client used by training trends endpoint tests."""

    calls: list[dict[str, str | int | None]] = []

    async def list_activities(
        self,
        *,
        user_id: int,
        begin_date: str,
        end_date: str,
        activity_type: str | None = None,
    ) -> list[dict[str, object]]:
        """Return weekly trend activities and record the user-scoped query."""
        FakeTrendsTrainingClient.calls.append(
            {
                "user_id": user_id,
                "begin_date": begin_date,
                "end_date": end_date,
                "activity_type": activity_type,
            }
        )
        return [
            {
                "activityType": {"typeKey": "running"},
                "startTimeLocal": "2026-06-16T07:00:00",
                "duration": 3600,
                "activityTrainingLoad": 100,
            },
            {
                "activityType": {"typeKey": "indoor_cycling"},
                "startTimeLocal": "2026-06-24T07:00:00",
                "duration": 1800,
                "activityTrainingLoad": 50,
            },
        ]


class FakeTrainingMetricsAnalysisService:  # pylint: disable=too-few-public-methods
    """Fake LLM training metrics analysis service used by endpoint tests."""

    calls: list[dict[str, object]] = []

    async def analyze(
        self,
        *,
        summary,
        response_language: str = "italian",
    ) -> TrainingMetricsAnalysisResult:
        """Record the aggregate summary and return a deterministic analysis."""
        FakeTrainingMetricsAnalysisService.calls.append(
            {
                "begin_date": summary.begin_date.isoformat(),
                "end_date": summary.end_date.isoformat(),
                "response_language": response_language,
                "sport_count": len(summary.sports),
            }
        )
        return TrainingMetricsAnalysisResult(
            analysis="Periodo con carico concentrato sulla corsa."
        )


class FakeTrainingTrendsService:  # pylint: disable=too-few-public-methods
    """Fake training trends service used by endpoint tests."""

    calls: list[dict[str, object]] = []

    async def summarize(
        self,
        *,
        training_client,
        user_id: int,
        weeks: int,
        end_date=None,
    ) -> TrainingTrendsSummary:
        """Record the request and return deterministic weekly trends."""
        _ = (training_client, end_date)
        if weeks < 4:
            raise ValueError("weeks must be between 4 and 26.")
        FakeTrainingTrendsService.calls.append(
            {
                "user_id": user_id,
                "weeks": weeks,
            }
        )
        return TrainingTrendsSummary(
            begin_date=datetime.fromisoformat("2026-06-15T00:00:00").date(),
            end_date=datetime.fromisoformat("2026-07-12T00:00:00").date(),
            weeks_requested=4,
            weeks=[
                WeeklyTrainingTrend(
                    week_start=datetime.fromisoformat("2026-06-15T00:00:00").date(),
                    week_end=datetime.fromisoformat("2026-06-21T00:00:00").date(),
                    iso_year=2026,
                    iso_week=25,
                    label="2026-W25",
                    total_hours=1.0,
                    total_training_load=100.0,
                    activity_count=1,
                    sports=[
                        WeeklySportTrend(
                            sport="running",
                            label="Run",
                            hours=1.0,
                            training_load=100.0,
                            activity_count=1,
                        ),
                        WeeklySportTrend(
                            sport="cycling",
                            label="Bike",
                            hours=0.0,
                            training_load=0.0,
                            activity_count=0,
                        ),
                        WeeklySportTrend(
                            sport="swimming",
                            label="Swim",
                            hours=0.0,
                            training_load=0.0,
                            activity_count=0,
                        ),
                    ],
                    rolling_4_week_average_load=100.0,
                    previous_week_delta_percent=None,
                    acute_chronic_load_ratio=None,
                )
            ],
        )


def build_client() -> TestClient:
    """Create a test client with network-dependent orchestration replaced."""
    app = create_app()
    app.dependency_overrides[get_orchestrator] = FakeOrchestrator
    app.dependency_overrides[get_current_user] = _fake_user
    return TestClient(app)


def build_client_with_diary(tmp_path) -> TestClient:
    """Create a test client with a temporary nutrition diary database."""
    app = create_app()
    database = build_test_database(tmp_path, "nutrition.db")
    user = UserRepository(database).ensure_user(username="alice")
    app.dependency_overrides[get_orchestrator] = FakeOrchestrator
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_nutrition_diary_service] = (
        lambda: NutritionDiaryService(database)
    )
    FakeDiaryRewriteService.calls.clear()
    app.dependency_overrides[get_nutrition_diary_rewrite_service] = (
        FakeDiaryRewriteService
    )
    return TestClient(app)


def build_client_with_plan(tmp_path) -> TestClient:
    """Create a test client with a temporary nutrition plan database."""
    app = create_app()
    database = build_test_database(tmp_path, "nutrition.db")
    user = UserRepository(database).ensure_user(username="alice")
    app.dependency_overrides[get_orchestrator] = FakeOrchestrator
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_nutrition_plan_service] = lambda: (
        NutritionPlanService(
            database,
            text_extractor=lambda pdf_bytes: pdf_bytes.decode("utf-8"),
        )
    )
    return TestClient(app)


def build_client_with_garmin_credentials(tmp_path) -> TestClient:
    """Create a test client with encrypted Garmin credential storage."""
    app = create_app()
    database = build_test_database(tmp_path, "account.db")
    user = UserRepository(database).ensure_user(username="alice")
    repository = GarminCredentialRepository(
        database,
        encryption_key=Fernet.generate_key(),
    )
    FakeTrainingProvider.calls.clear()
    app.dependency_overrides[get_orchestrator] = FakeOrchestrator
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_garmin_credential_repository] = lambda: repository
    app.dependency_overrides[get_training_data_provider_factory] = (
        lambda: FakeTrainingProvider
    )
    return TestClient(app)


def build_client_with_failing_garmin_credentials(tmp_path) -> TestClient:
    """Create a test client whose Garmin provider fails with rate limiting."""
    app = create_app()
    database = build_test_database(tmp_path, "account.db")
    user = UserRepository(database).ensure_user(username="alice")
    repository = GarminCredentialRepository(
        database,
        encryption_key=Fernet.generate_key(),
    )
    app.dependency_overrides[get_orchestrator] = FakeOrchestrator
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_garmin_credential_repository] = lambda: repository
    app.dependency_overrides[get_training_data_provider_factory] = (
        lambda: FailingGarminTrainingProvider
    )
    return TestClient(app)


def build_client_with_training_metrics() -> TestClient:
    """Create a test client with fake training data for metrics requests."""
    app = create_app()
    FakeMetricsTrainingClient.calls.clear()
    FakeTrainingMetricsAnalysisService.calls.clear()
    app.dependency_overrides[get_orchestrator] = FakeOrchestrator
    app.dependency_overrides[get_current_user] = lambda: _fake_user(user_id=7)
    app.dependency_overrides[get_training_client] = FakeMetricsTrainingClient
    app.dependency_overrides[get_training_metrics_service] = TrainingMetricsService
    app.dependency_overrides[get_training_metrics_analysis_service] = (
        FakeTrainingMetricsAnalysisService
    )
    return TestClient(app)


def build_client_with_training_trends() -> TestClient:
    """Create a test client with fake training data for trends requests."""
    app = create_app()
    FakeTrendsTrainingClient.calls.clear()
    FakeTrainingTrendsService.calls.clear()
    app.dependency_overrides[get_orchestrator] = FakeOrchestrator
    app.dependency_overrides[get_current_user] = lambda: _fake_user(user_id=7)
    app.dependency_overrides[get_training_client] = FakeTrendsTrainingClient
    app.dependency_overrides[get_training_trends_service] = FakeTrainingTrendsService
    return TestClient(app)


def _fake_user(user_id: int = 1, username: str = "alice") -> ApplicationUser:
    """Create a current-user object for endpoint tests."""
    now = datetime.now(UTC).replace(microsecond=0)
    return ApplicationUser(
        id=user_id,
        username=username,
        display_name=username,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def test_health_returns_service_status() -> None:
    """Verify that monitoring tools can call the assistant health endpoint."""
    client = build_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "assistant_api"}


def test_chat_accepts_message_and_history() -> None:
    """Verify that the chat endpoint accepts the frontend conversation shape."""
    client = build_client()

    response = client.post(
        "/chat",
        json={
            "message": "Summarise my week",
            "conversation_id": "conversation-1",
            "messages": [
                {"role": "user", "content": "What did I do yesterday?"},
                {"role": "assistant", "content": "You completed a run."},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == "conversation-1"
    assert "2 history message" in body["answer"]


def test_chat_stream_returns_server_sent_events() -> None:
    """Verify that frontend clients can consume streamed assistant events."""
    client = build_client()

    with client.stream(
        "POST",
        "/chat/stream",
        json={"message": "Summarise my week", "conversation_id": "conversation-1"},
    ) as response:
        content = response.read().decode("utf-8")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse_events(content)
    assert events == [
        {
            "type": "message_delta",
            "conversation_id": "conversation-1",
            "delta": "hello user 1",
            "data_sources": [],
        },
        {
            "type": "message_done",
            "conversation_id": "conversation-1",
            "answer": "reply to Summarise my week",
            "data_sources": [],
        },
    ]


def test_chat_rejects_empty_message() -> None:
    """Verify that invalid frontend payloads receive validation errors."""
    client = build_client()

    response = client.post("/chat", json={"message": ""})

    assert response.status_code == 422


def test_chat_rejects_missing_authenticated_user_header(tmp_path) -> None:
    """Verify protected backend routes require a resolved authenticated user."""
    app = create_app()
    repository = UserRepository(build_test_database(tmp_path, "nutrition.db"))
    app.dependency_overrides[get_orchestrator] = FakeOrchestrator
    app.dependency_overrides[get_user_repository] = lambda: repository
    client = TestClient(app)

    response = client.post("/chat", json={"message": "Summarise my week"})

    assert response.status_code == 401


def test_chat_rejects_unknown_authenticated_user(tmp_path) -> None:
    """Verify unknown proxy-authenticated usernames are not accepted."""
    app = create_app()
    repository = UserRepository(build_test_database(tmp_path, "nutrition.db"))
    app.dependency_overrides[get_orchestrator] = FakeOrchestrator
    app.dependency_overrides[get_user_repository] = lambda: repository
    client = TestClient(app)

    response = client.post(
        "/chat",
        json={"message": "Summarise my week"},
        headers={"X-Authenticated-User": "missing"},
    )

    assert response.status_code == 403


def test_get_garmin_credential_status_returns_missing(tmp_path) -> None:
    """Verify account clients can detect missing Garmin credentials."""
    client = build_client_with_garmin_credentials(tmp_path)

    response = client.get("/account/garmin-credentials")

    assert response.status_code == 200
    assert response.json() == {
        "configured": False,
        "garmin_username": None,
        "updated_at": None,
    }


def test_save_garmin_credentials_returns_safe_status(tmp_path) -> None:
    """Verify saving credentials does not return the stored password."""
    client = build_client_with_garmin_credentials(tmp_path)

    response = client.put(
        "/account/garmin-credentials",
        json={
            "garmin_username": "alice@example.com",
            "garmin_password": "super-secret",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is True
    assert body["garmin_username"] == "alice@example.com"
    assert body["updated_at"]
    assert "password" not in body


def test_delete_garmin_credentials_removes_status(tmp_path) -> None:
    """Verify users can delete their stored Garmin credentials."""
    client = build_client_with_garmin_credentials(tmp_path)
    client.put(
        "/account/garmin-credentials",
        json={
            "garmin_username": "alice@example.com",
            "garmin_password": "super-secret",
        },
    )

    response = client.delete("/account/garmin-credentials")

    assert response.status_code == 204
    assert client.get("/account/garmin-credentials").json()["configured"] is False


def test_garmin_credential_test_uses_stored_secret_without_returning_it(
    tmp_path,
) -> None:
    """Verify credential testing initializes Garmin provider with user data."""
    client = build_client_with_garmin_credentials(tmp_path)
    client.put(
        "/account/garmin-credentials",
        json={
            "garmin_username": "alice@example.com",
            "garmin_password": "super-secret",
        },
    )

    response = client.post("/account/garmin-credentials/test")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "message": "Garmin credentials are valid.",
    }
    assert FakeTrainingProvider.calls == [
        {
            "username": "alice@example.com",
            "password": "super-secret",
            "session_storage_path": "/data/garmin-sessions/1",
        }
    ]


def test_garmin_credential_test_returns_safe_error_for_garmin_login_block(
    tmp_path,
) -> None:
    """Verify Garmin login blocks return a user-safe 502 instead of HTTP 500."""
    client = build_client_with_failing_garmin_credentials(tmp_path)
    client.put(
        "/account/garmin-credentials",
        json={
            "garmin_username": "alice@example.com",
            "garmin_password": "super-secret",
        },
    )

    response = client.post("/account/garmin-credentials/test")

    assert response.status_code == 502
    assert "Garmin Connect login failed" in response.json()["detail"]
    assert "CAPTCHA" in response.json()["detail"]
    assert "super-secret" not in response.text


def test_chat_stream_returns_error_event_for_runtime_failure() -> None:
    """Verify stream errors are sent as SSE events instead of raw tracebacks."""
    app = create_app()
    app.dependency_overrides[get_orchestrator] = FailingOrchestrator
    app.dependency_overrides[get_current_user] = _fake_user
    client = TestClient(app)

    with client.stream(
        "POST",
        "/chat/stream",
        json={"message": "Summarise my week", "conversation_id": "conversation-1"},
    ) as response:
        content = response.read().decode("utf-8")

    assert response.status_code == 200
    assert parse_sse_events(content) == [
        {
            "type": "error",
            "conversation_id": "conversation-1",
            "delta": "backend unavailable",
        }
    ]


def test_training_metrics_returns_aggregates_for_date_range() -> None:
    """Verify the training metrics endpoint returns compact sport aggregates."""
    client = build_client_with_training_metrics()

    response = client.get("/training/metrics?begin_date=2026-07-01&end_date=2026-07-31")

    assert response.status_code == 200
    assert response.json() == {
        "begin_date": "2026-07-01",
        "end_date": "2026-07-31",
        "sports": [
            {
                "sport": "running",
                "label": "Run",
                "activity_count": 1,
                "hours": 1.0,
                "total_duration_seconds": 3600.0,
                "total_training_load": 120.0,
                "training_load_per_hour": 120.0,
                "weighted_average_heart_rate": 148.0,
                "average_aerobic_training_effect": 3.1,
                "average_anaerobic_training_effect": 0.7,
                "moderate_intensity_minutes": 0.0,
                "vigorous_intensity_minutes": 0.0,
                "intensity_score": 120.0,
                "intensity_source": "training_load",
            },
            {
                "sport": "cycling",
                "label": "Bike",
                "activity_count": 1,
                "hours": 0.5,
                "total_duration_seconds": 1800.0,
                "total_training_load": None,
                "training_load_per_hour": None,
                "weighted_average_heart_rate": 132.0,
                "average_aerobic_training_effect": None,
                "average_anaerobic_training_effect": None,
                "moderate_intensity_minutes": 10.0,
                "vigorous_intensity_minutes": 20.0,
                "intensity_score": 50.0,
                "intensity_source": "intensity_minutes",
            },
            {
                "sport": "swimming",
                "label": "Swim",
                "activity_count": 0,
                "hours": 0.0,
                "total_duration_seconds": 0.0,
                "total_training_load": None,
                "training_load_per_hour": None,
                "weighted_average_heart_rate": None,
                "average_aerobic_training_effect": None,
                "average_anaerobic_training_effect": None,
                "moderate_intensity_minutes": 0.0,
                "vigorous_intensity_minutes": 0.0,
                "intensity_score": None,
                "intensity_source": "none",
            },
        ],
    }
    assert FakeMetricsTrainingClient.calls == [
        {
            "user_id": 7,
            "begin_date": "2026-07-01",
            "end_date": "2026-07-31",
            "activity_type": None,
        }
    ]


def test_training_metrics_rejects_reversed_date_range() -> None:
    """Verify the metrics endpoint validates the selected date range."""
    client = build_client_with_training_metrics()

    response = client.get("/training/metrics?begin_date=2026-07-31&end_date=2026-07-01")

    assert response.status_code == 422
    assert "begin_date" in response.json()["detail"]


def test_training_report_returns_deterministic_custom_report() -> None:
    """Verify the report endpoint uses one user-scoped activity-list request."""
    client = build_client_with_training_metrics()

    response = client.post(
        "/training/reports",
        json={
            "report_type": "custom",
            "begin_date": "2026-07-01",
            "end_date": "2026-07-31",
        },
    )

    assert response.status_code == 200
    assert response.json()["begin_date"] == "2026-07-01"
    assert response.json()["end_date"] == "2026-07-31"
    assert response.json()["report_type"] == "custom"
    assert "### Corsa" in response.json()["report"]
    assert FakeMetricsTrainingClient.calls == [
        {
            "user_id": 7,
            "begin_date": "2026-07-01",
            "end_date": "2026-07-31",
            "activity_type": None,
        }
    ]


def test_training_metrics_analysis_returns_llm_summary() -> None:
    """Verify clients can request an on-demand metrics analysis."""
    client = build_client_with_training_metrics()

    response = client.post(
        "/training/metrics/analysis",
        json={
            "begin_date": "2026-07-01",
            "end_date": "2026-07-31",
            "response_language": "italian",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "begin_date": "2026-07-01",
        "end_date": "2026-07-31",
        "analysis": "Periodo con carico concentrato sulla corsa.",
        "token_usage": None,
    }
    assert FakeMetricsTrainingClient.calls == [
        {
            "user_id": 7,
            "begin_date": "2026-07-01",
            "end_date": "2026-07-31",
            "activity_type": None,
        }
    ]
    assert FakeTrainingMetricsAnalysisService.calls == [
        {
            "begin_date": "2026-07-01",
            "end_date": "2026-07-31",
            "response_language": "italian",
            "sport_count": 3,
        }
    ]


def test_training_metrics_analysis_rejects_reversed_date_range() -> None:
    """Verify the analysis endpoint validates the selected date range."""
    client = build_client_with_training_metrics()

    response = client.post(
        "/training/metrics/analysis",
        json={
            "begin_date": "2026-07-31",
            "end_date": "2026-07-01",
        },
    )

    assert response.status_code == 422
    assert "begin_date" in response.json()["detail"]


def test_training_metrics_analysis_defaults_to_english() -> None:
    """Verify omitted analysis language uses English by default."""
    client = build_client_with_training_metrics()

    response = client.post(
        "/training/metrics/analysis",
        json={
            "begin_date": "2026-07-01",
            "end_date": "2026-07-31",
        },
    )

    assert response.status_code == 200
    assert (
        FakeTrainingMetricsAnalysisService.calls[-1]["response_language"] == "english"
    )


def test_training_trends_returns_weekly_series() -> None:
    """Verify clients can request weekly training trends."""
    client = build_client_with_training_trends()

    response = client.get("/training/trends?weeks=4")

    assert response.status_code == 200
    assert response.json() == {
        "begin_date": "2026-06-15",
        "end_date": "2026-07-12",
        "weeks_requested": 4,
        "weeks": [
            {
                "week_start": "2026-06-15",
                "week_end": "2026-06-21",
                "iso_year": 2026,
                "iso_week": 25,
                "label": "2026-W25",
                "total_hours": 1.0,
                "total_training_load": 100.0,
                "activity_count": 1,
                "sports": [
                    {
                        "sport": "running",
                        "label": "Run",
                        "hours": 1.0,
                        "training_load": 100.0,
                        "activity_count": 1,
                    },
                    {
                        "sport": "cycling",
                        "label": "Bike",
                        "hours": 0.0,
                        "training_load": 0.0,
                        "activity_count": 0,
                    },
                    {
                        "sport": "swimming",
                        "label": "Swim",
                        "hours": 0.0,
                        "training_load": 0.0,
                        "activity_count": 0,
                    },
                ],
                "rolling_4_week_average_load": 100.0,
                "previous_week_delta_percent": None,
                "acute_chronic_load_ratio": None,
            }
        ],
    }
    assert FakeTrainingTrendsService.calls == [{"user_id": 7, "weeks": 4}]


def test_training_trends_rejects_invalid_week_count() -> None:
    """Verify the trends endpoint validates requested week count."""
    client = build_client_with_training_trends()

    response = client.get("/training/trends?weeks=3")

    assert response.status_code == 422
    assert "weeks" in response.json()["detail"]


def test_put_nutrition_diary_entry_creates_day(tmp_path) -> None:
    """Verify the assistant API can persist one nutrition diary day."""
    client = build_client_with_diary(tmp_path)

    response = client.put(
        "/nutrition/diary-entries/2026-05-12",
        json={
            "training_type": "Easy run",
            "meals_text": "Breakfast: oats. Lunch: rice and chicken.",
            "notes": "Good energy.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["entry_date"] == "2026-05-12"
    assert body["training_type"] == "Easy run"
    assert body["meals_text"] == "Breakfast: oats. Lunch: rice and chicken."
    assert body["notes"] == "Good energy."
    assert body["created_at"]
    assert body["updated_at"]


def test_get_nutrition_diary_entry_returns_saved_day(tmp_path) -> None:
    """Verify the assistant API returns a previously saved diary day."""
    client = build_client_with_diary(tmp_path)
    client.put(
        "/nutrition/diary-entries/2026-05-12",
        json={
            "training_type": "Rest day",
            "meals_text": "Breakfast: toast.",
            "notes": "",
        },
    )

    response = client.get("/nutrition/diary-entries/2026-05-12")

    assert response.status_code == 200
    body = response.json()
    assert body["entry_date"] == "2026-05-12"
    assert body["training_type"] == "Rest day"
    assert body["meals_text"] == "Breakfast: toast."


def test_put_nutrition_diary_entry_updates_existing_day(tmp_path) -> None:
    """Verify saving the same day updates it rather than creating a duplicate."""
    client = build_client_with_diary(tmp_path)
    original = client.put(
        "/nutrition/diary-entries/2026-05-12",
        json={
            "training_type": "Rest day",
            "meals_text": "Breakfast: toast.",
            "notes": "",
        },
    ).json()

    updated_response = client.put(
        "/nutrition/diary-entries/2026-05-12",
        json={
            "training_type": "Intervals",
            "meals_text": "Breakfast: oats. Dinner: pasta.",
            "notes": "Hard session.",
        },
    )

    assert updated_response.status_code == 200
    updated = updated_response.json()
    assert updated["id"] == original["id"]
    assert updated["training_type"] == "Intervals"
    assert updated["meals_text"] == "Breakfast: oats. Dinner: pasta."
    assert updated["notes"] == "Hard session."


def test_post_nutrition_diary_entry_accepts_date_in_payload(tmp_path) -> None:
    """Verify clients can upsert a diary entry with a request body date."""
    client = build_client_with_diary(tmp_path)

    response = client.post(
        "/nutrition/diary-entries",
        json={
            "entry_date": "2026-05-12",
            "training_type": "Cycling",
            "meals_text": "Lunch: pasta.",
            "notes": "Long ride.",
        },
    )

    assert response.status_code == 200
    assert response.json()["training_type"] == "Cycling"


def test_post_nutrition_diary_rewrite_returns_unsaved_text(tmp_path) -> None:
    """Verify clients can ask the backend to rewrite diary meal text."""
    client = build_client_with_diary(tmp_path)

    response = client.post(
        "/nutrition/diary-entries/2026-05-15/rewrite",
        json={
            "training_type": "Easy run",
            "meals_text": "colazione yogurt miele",
            "notes": "energia buona",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "rewritten_meals_text": "Colazione: yogurt e miele.",
        "token_usage": None,
    }
    assert FakeDiaryRewriteService.calls == [
        {
            "entry_date": "2026-05-15",
            "training_type": "Easy run",
            "meals_text": "colazione yogurt miele",
            "notes": "energia buona",
        }
    ]


def test_get_nutrition_diary_entry_returns_404_for_missing_day(tmp_path) -> None:
    """Verify missing diary days return a clear not-found response."""
    client = build_client_with_diary(tmp_path)

    response = client.get("/nutrition/diary-entries/2026-05-12")

    assert response.status_code == 404


def test_upload_nutrition_plan_replaces_current_plan(tmp_path) -> None:
    """Verify PDF upload stores the current nutrition plan text."""
    client = build_client_with_plan(tmp_path)

    response = client.post(
        "/nutrition/plan",
        files={"file": ("plan.pdf", b"Breakfast plan", "application/pdf")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["original_filename"] == "plan.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["extracted_text"] == "Breakfast plan"
    assert len(body["file_sha256"]) == 64

    updated_response = client.post(
        "/nutrition/plan",
        files={"file": ("new-plan.pdf", b"Lunch plan", "application/pdf")},
    )

    assert updated_response.status_code == 200
    updated = updated_response.json()
    assert updated["id"] == body["id"]
    assert updated["original_filename"] == "new-plan.pdf"
    assert updated["extracted_text"] == "Lunch plan"
    assert updated["file_sha256"] != body["file_sha256"]


def test_get_current_nutrition_plan_returns_uploaded_plan(tmp_path) -> None:
    """Verify clients can read the currently uploaded nutrition plan."""
    client = build_client_with_plan(tmp_path)
    client.post(
        "/nutrition/plan",
        files={"file": ("plan.pdf", b"Breakfast plan", "application/pdf")},
    )

    response = client.get("/nutrition/plan/current")

    assert response.status_code == 200
    assert response.json()["extracted_text"] == "Breakfast plan"


def test_get_current_nutrition_plan_returns_404_when_missing(tmp_path) -> None:
    """Verify missing nutrition plans return a not-found response."""
    client = build_client_with_plan(tmp_path)

    response = client.get("/nutrition/plan/current")

    assert response.status_code == 404


def test_upload_nutrition_plan_rejects_non_pdf(tmp_path) -> None:
    """Verify the upload endpoint accepts only PDF files."""
    client = build_client_with_plan(tmp_path)

    response = client.post(
        "/nutrition/plan",
        files={"file": ("plan.txt", b"Breakfast plan", "text/plain")},
    )

    assert response.status_code == 415


def parse_sse_events(content: str) -> list[dict[str, object]]:
    """Extract JSON payloads from server-sent event text."""
    events: list[dict[str, object]] = []
    for block in content.strip().split("\n\n"):
        data_lines = [
            line.removeprefix("data: ")
            for line in block.splitlines()
            if line.startswith("data: ")
        ]
        if data_lines:
            events.append(json.loads("".join(data_lines)))

    return events
