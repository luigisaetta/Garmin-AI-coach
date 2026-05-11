"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

# pylint: disable=duplicate-code

from types import SimpleNamespace
from typing import Any

import pytest

from services.assistant_api.api.schemas import ChatRequest
from services.assistant_api.orchestration.chat import (
    AssistantOrchestrator,
    AssistantSettings,
)


class FakeResponses:  # pylint: disable=too-few-public-methods
    """Fake Responses API resource with deterministic tool-call flow."""

    def __init__(self) -> None:
        """Initialize captured Responses API calls."""
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        """Capture model requests and return a tool call, then final answer."""
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return SimpleNamespace(
                output_text="",
                output=[
                    SimpleNamespace(
                        type="function_call",
                        name="list_activities",
                        call_id="call_123",
                        arguments=(
                            '{"begin_date": "2026-05-04", ' '"end_date": "2026-05-10"}'
                        ),
                        model_dump=lambda **_: {
                            "type": "function_call",
                            "name": "list_activities",
                            "call_id": "call_123",
                            "arguments": (
                                '{"begin_date": "2026-05-04", '
                                '"end_date": "2026-05-10"}'
                            ),
                        },
                    )
                ],
            )
        return SimpleNamespace(output_text="You ran three times last week.", output=[])

    def stream(self, **kwargs: Any) -> "FakeStreamManager":
        """Capture streaming model requests and return a fake stream manager."""
        self.calls.append({**kwargs, "stream": True})
        return FakeStreamManager(
            events=[
                SimpleNamespace(type="response.output_text.delta", delta="You ran "),
                SimpleNamespace(
                    type="response.output_text.delta",
                    delta="three times.",
                ),
            ],
            final_text="You ran three times.",
        )


class FakeStreamManager:
    """Context manager fake returned by `responses.stream`."""

    def __init__(self, events: list[SimpleNamespace], final_text: str) -> None:
        """Store stream events and final text."""
        self._stream = FakeStream(events=events, final_text=final_text)

    def __enter__(self) -> "FakeStream":
        """Return the fake stream."""
        return self._stream

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Close the fake stream."""
        self._stream.close()


class FakeStream:
    """Small iterable fake for Responses API streaming events."""

    def __init__(self, events: list[SimpleNamespace], final_text: str) -> None:
        """Store stream events."""
        self._events = events
        self._final_text = final_text
        self.closed = False

    def __iter__(self):
        """Iterate over fake stream events."""
        return iter(self._events)

    def close(self) -> None:
        """Record that the stream was closed."""
        self.closed = True

    def get_final_response(self) -> SimpleNamespace:
        """Return a fake accumulated final response."""
        return SimpleNamespace(output_text=self._final_text)


class FakeInferenceClient:  # pylint: disable=too-few-public-methods
    """Fake OpenAI-compatible SDK client."""

    def __init__(self) -> None:
        """Initialize fake Responses API resource."""
        self.responses = FakeResponses()


class FakeTrainingClient:  # pylint: disable=too-few-public-methods
    """Fake local training data client."""

    def __init__(self) -> None:
        """Initialize captured training data calls."""
        self.calls: list[dict[str, str | None]] = []

    async def list_activities(
        self,
        *,
        begin_date: str,
        end_date: str,
        activity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Capture model-extracted date range arguments."""
        self.calls.append(
            {
                "begin_date": begin_date,
                "end_date": end_date,
                "activity_type": activity_type,
            }
        )
        return [{"activityId": 1, "activityName": "Run"}]


@pytest.mark.anyio
async def test_complete_chat_uses_responses_api_and_garmin_tool_call() -> None:
    """Verify the assistant performs one Responses API tool-call round."""
    inference_client = FakeInferenceClient()
    training_client = FakeTrainingClient()
    orchestrator = AssistantOrchestrator(
        settings=AssistantSettings(
            model_id="openai.gpt-5.4",
        ),
        inference_client=inference_client,
        training_client=training_client,
    )

    response = await orchestrator.complete_chat(
        ChatRequest(
            message="Summarise last week",
            messages=[],
            conversation_id="conversation-1",
        )
    )

    assert response.answer == "You ran three times last week."
    assert response.conversation_id == "conversation-1"
    assert response.data_sources[0].type == "garmin_activity_range"
    assert training_client.calls == [
        {
            "begin_date": "2026-05-04",
            "end_date": "2026-05-10",
            "activity_type": None,
        }
    ]
    assert len(inference_client.responses.calls) == 2
    assert inference_client.responses.calls[0]["tools"]
    assert "instructions" in inference_client.responses.calls[0]
    assert any(
        item.get("type") == "function_call_output"
        for item in inference_client.responses.calls[1]["input"]
    )


@pytest.mark.anyio
async def test_stream_chat_uses_responses_api_stream_for_final_answer() -> None:
    """Verify streamed chat emits model deltas from Responses API streaming."""
    inference_client = FakeInferenceClient()
    training_client = FakeTrainingClient()
    orchestrator = AssistantOrchestrator(
        settings=AssistantSettings(model_id="openai.gpt-5.4"),
        inference_client=inference_client,
        training_client=training_client,
    )

    events = [
        event
        async for event in orchestrator.stream_chat(
            ChatRequest(message="Summarise last week")
        )
    ]

    assert [event.type for event in events] == [
        "message_delta",
        "message_delta",
        "message_done",
    ]
    assert events[0].delta == "You ran "
    assert events[1].delta == "three times."
    assert events[2].answer == "You ran three times."
    assert inference_client.responses.calls[-1]["stream"] is True
