"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from services.assistant_api.api.main import create_app, get_orchestrator
from services.assistant_api.api.schemas import (
    ChatRequest,
    ChatResponse,
    ChatStreamEvent,
)


class FakeOrchestrator:
    """Predictable orchestrator used by HTTP endpoint tests."""

    async def complete_chat(self, request: ChatRequest) -> ChatResponse:
        """Return a deterministic non-streaming response."""
        return ChatResponse(
            answer=(
                f"reply to {request.message} with {len(request.messages)} "
                "history message(s)"
            ),
            conversation_id=request.conversation_id or "generated-id",
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]:
        """Return two deterministic events for streaming assertions."""
        conversation_id = request.conversation_id or "generated-id"
        yield ChatStreamEvent(
            type="message_delta",
            conversation_id=conversation_id,
            delta="hello",
        )
        yield ChatStreamEvent(
            type="message_done",
            conversation_id=conversation_id,
            answer=f"reply to {request.message}",
        )


class FailingOrchestrator:  # pylint: disable=too-few-public-methods
    """Orchestrator that simulates an unexpected streaming failure."""

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]:
        """Raise a runtime error during SSE generation."""
        if request.conversation_id == "__never__":
            yield ChatStreamEvent(type="message_delta", conversation_id="unused")
        raise RuntimeError("backend unavailable")


def build_client() -> TestClient:
    """Create a test client with network-dependent orchestration replaced."""
    app = create_app()
    app.dependency_overrides[get_orchestrator] = FakeOrchestrator
    return TestClient(app)


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
            "delta": "hello",
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


def test_chat_stream_returns_error_event_for_runtime_failure() -> None:
    """Verify stream errors are sent as SSE events instead of raw tracebacks."""
    app = create_app()
    app.dependency_overrides[get_orchestrator] = FailingOrchestrator
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
