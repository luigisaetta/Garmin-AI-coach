"""
Author: L. Saetta
Date Modified: 2026-05-13
License: MIT
"""

from __future__ import annotations

import json

# pylint: disable=duplicate-code

from types import SimpleNamespace
from datetime import date
from typing import Any

import pytest

from services.assistant_api.api.schemas import ChatRequest, TokenUsage
from services.assistant_api.nutrition.analysis import NutritionAnalysisResult
from services.assistant_api.orchestration.chat import (
    AssistantOrchestrator,
    AssistantSettings,
    tool_outputs_token_usage,
)


class FakeResponses:  # pylint: disable=too-few-public-methods
    """Fake Responses API resource with deterministic tool-call flow."""

    def __init__(self, tool_name: str = "list_activities") -> None:
        """Initialize captured Responses API calls."""
        self.calls: list[dict[str, Any]] = []
        self.tool_name = tool_name

    def create(self, **kwargs: Any) -> Any:
        """Capture model requests and return a tool call, then final answer."""
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return SimpleNamespace(
                output_text="",
                usage=SimpleNamespace(
                    input_tokens=100,
                    output_tokens=12,
                    total_tokens=112,
                ),
                output=[
                    SimpleNamespace(
                        type="function_call",
                        name=self.tool_name,
                        call_id="call_123",
                        arguments=(
                            '{"begin_date": "2026-05-04", '
                            '"end_date": "2026-05-10", '
                            '"response_language": "italian"}'
                        ),
                        model_dump=lambda **_: {
                            "type": "function_call",
                            "name": self.tool_name,
                            "call_id": "call_123",
                            "arguments": (
                                '{"begin_date": "2026-05-04", '
                                '"end_date": "2026-05-10", '
                                '"response_language": "italian"}'
                            ),
                        },
                    )
                ],
            )
        return SimpleNamespace(
            output_text="You ran three times last week.",
            usage=SimpleNamespace(
                input_tokens=140,
                output_tokens=28,
                total_tokens=168,
            ),
            output=[],
        )

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
        return SimpleNamespace(
            output_text=self._final_text,
            usage=SimpleNamespace(
                input_tokens=120,
                output_tokens=24,
                total_tokens=144,
            ),
        )


class FakeInferenceClient:  # pylint: disable=too-few-public-methods
    """Fake OpenAI-compatible SDK client."""

    def __init__(self, tool_name: str = "list_activities") -> None:
        """Initialize fake Responses API resource."""
        self.responses = FakeResponses(tool_name=tool_name)


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

    async def get_heart_rates(
        self,
        *,
        begin_date: str,
        end_date: str,
    ) -> dict[str, dict[str, Any]]:
        """Capture model-extracted heart-rate range arguments."""
        self.calls.append(
            {
                "begin_date": begin_date,
                "end_date": end_date,
                "activity_type": "heart_rate",
            }
        )
        return {begin_date: {"calendarDate": begin_date, "restingHeartRate": 48}}


class FakeNutritionAnalysisAgent:  # pylint: disable=too-few-public-methods
    """Fake nutrition analysis subagent."""

    def __init__(self) -> None:
        """Initialize captured nutrition analysis calls."""
        self.calls: list[dict[str, date]] = []

    async def analyze(
        self,
        *,
        begin_date: date,
        end_date: date,
        response_language: str | None = None,
    ) -> NutritionAnalysisResult:
        """Capture the requested period and return a deterministic report."""
        self.calls.append(
            {
                "begin_date": begin_date,
                "end_date": end_date,
                "response_language": response_language,
            }
        )
        return NutritionAnalysisResult(
            begin_date=begin_date,
            end_date=end_date,
            report="Report nutrizionale.",
            plan_filename="plan.pdf",
            diary_entry_count=4,
            missing_diary_dates=[],
            training_day_count=3,
            token_usage=TokenUsage(
                input_tokens=300,
                output_tokens=80,
                total_tokens=380,
            ),
        )


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
    assert response.token_usage is not None
    assert response.token_usage.input_tokens == 240
    assert response.token_usage.output_tokens == 40
    assert response.token_usage.total_tokens == 280
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
async def test_complete_chat_reports_heart_rate_data_source() -> None:
    """Verify heart-rate tool calls produce heart-rate data-source metadata."""
    inference_client = FakeInferenceClient(tool_name="get_heart_rates")
    training_client = FakeTrainingClient()
    orchestrator = AssistantOrchestrator(
        settings=AssistantSettings(model_id="openai.gpt-5.4"),
        inference_client=inference_client,
        training_client=training_client,
    )

    response = await orchestrator.complete_chat(ChatRequest(message="How was my HR?"))

    assert response.data_sources[0].type == "garmin_heart_rate_range"
    assert training_client.calls == [
        {
            "begin_date": "2026-05-04",
            "end_date": "2026-05-10",
            "activity_type": "heart_rate",
        }
    ]


@pytest.mark.anyio
async def test_complete_chat_runs_nutrition_analysis_tool() -> None:
    """Verify chat can expose and execute the nutrition subagent as a tool."""
    inference_client = FakeInferenceClient(
        tool_name="analyze_nutrition_adherence_period"
    )
    training_client = FakeTrainingClient()
    nutrition_agent = FakeNutritionAnalysisAgent()
    orchestrator = AssistantOrchestrator(
        settings=AssistantSettings(model_id="openai.gpt-5.4"),
        inference_client=inference_client,
        training_client=training_client,
        nutrition_analysis_agent=nutrition_agent,
    )

    response = await orchestrator.complete_chat(
        ChatRequest(message="Analizza l'aderenza nutrizionale della scorsa settimana")
    )

    assert response.data_sources[0].type == "nutrition_adherence_analysis"
    assert nutrition_agent.calls == [
        {
            "begin_date": date(2026, 5, 4),
            "end_date": date(2026, 5, 10),
            "response_language": "italian",
        }
    ]
    assert "analyze_nutrition_adherence_period" in {
        tool["name"] for tool in inference_client.responses.calls[0]["tools"]
    }
    assert response.token_usage is not None
    assert response.token_usage.input_tokens == 540
    assert response.token_usage.output_tokens == 120
    assert response.token_usage.total_tokens == 660


def test_tool_outputs_token_usage_extracts_nested_tool_usage() -> None:
    """Verify assistant totals include Responses calls made inside tools."""
    usage = tool_outputs_token_usage(
        [
            {
                "type": "function_call_output",
                "call_id": "call_1",
                "output": json.dumps({"activities": []}),
            },
            {
                "type": "function_call_output",
                "call_id": "call_2",
                "output": json.dumps(
                    {
                        "report": "Nutrition report.",
                        "token_usage": {
                            "input_tokens": 300,
                            "output_tokens": 80,
                            "total_tokens": 380,
                        },
                    }
                ),
            },
        ]
    )

    assert usage == TokenUsage(input_tokens=300, output_tokens=80, total_tokens=380)


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
    assert events[2].token_usage is not None
    assert events[2].token_usage.input_tokens == 220
    assert events[2].token_usage.output_tokens == 36
    assert events[2].token_usage.total_tokens == 256
    assert inference_client.responses.calls[-1]["stream"] is True
