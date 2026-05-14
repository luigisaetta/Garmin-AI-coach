"""
Author: L. Saetta
Date Modified: 2026-05-14
License: MIT
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from examples import example02
from services.assistant_api.orchestration.responses_tools import (
    AssistantToolRunner,
    build_tool_outputs,
)
from services.assistant_api.orchestration.training_data import LocalTrainingDataClient


class FakeProvider:  # pylint: disable=too-few-public-methods
    """Fake Garmin provider for example tool tests."""

    def __init__(self) -> None:
        """Initialize the fake provider with no recorded calls."""
        self.calls: list[dict[str, str | None]] = []

    def list_activities(
        self,
        begin_date: str,
        end_date: str,
        activity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Record tool inputs and return a predictable activity."""
        self.calls.append(
            {
                "begin_date": begin_date,
                "end_date": end_date,
                "activity_type": activity_type,
            }
        )
        return [{"activityId": 123, "activityName": "Morning Run"}]


class FakeResponses:  # pylint: disable=too-few-public-methods
    """Fake Responses API surface used to test stateless final calls."""

    def __init__(self) -> None:
        """Initialize the fake response API with no recorded calls."""
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        """Record response creation calls."""
        self.calls.append(kwargs)
        return SimpleNamespace(output_text="final answer")


class FakeClient:  # pylint: disable=too-few-public-methods
    """Fake OpenAI-compatible client for final response tests."""

    def __init__(self) -> None:
        """Create a fake client with a fake responses resource."""
        self.responses = FakeResponses()


def test_build_user_message_preserves_natural_language_request() -> None:
    """Verify that the model receives the user's natural-language request."""
    message = example02.build_user_message(
        "Summarize my running from 2026-05-01 to 2026-05-10."
    )

    assert "Summarize my running" in message
    assert "2026-05-01" in message
    assert "2026-05-10" in message


@pytest.mark.anyio
async def test_build_tool_outputs_uses_model_tool_arguments() -> None:
    """Verify that tool execution uses model-extracted tool arguments."""
    provider = FakeProvider()
    tool_runner = AssistantToolRunner(LocalTrainingDataClient(provider))
    function_call = SimpleNamespace(
        type="function_call",
        name="list_activities",
        call_id="call_123",
        arguments=(
            '{"begin_date": "2026-05-01", "end_date": "2026-05-10", '
            '"activity_type": "running"}'
        ),
    )

    outputs = await build_tool_outputs(
        function_calls=[function_call],
        tool_runner=tool_runner,
        user_id=1,
    )

    assert provider.calls == [
        {
            "begin_date": "2026-05-01",
            "end_date": "2026-05-10",
            "activity_type": "running",
        }
    ]
    assert outputs[0]["type"] == "function_call_output"
    assert outputs[0]["call_id"] == "call_123"
    assert "Morning Run" in outputs[0]["output"]


@pytest.mark.anyio
async def test_build_tool_outputs_returns_error_for_missing_required_dates() -> None:
    """Verify that invalid model tool arguments are returned as tool errors."""
    provider = FakeProvider()
    tool_runner = AssistantToolRunner(LocalTrainingDataClient(provider))
    function_call = SimpleNamespace(
        type="function_call",
        name="list_activities",
        call_id="call_123",
        arguments='{"activity_type": "running"}',
    )

    outputs = await build_tool_outputs(
        function_calls=[function_call],
        tool_runner=tool_runner,
        user_id=1,
    )

    assert not provider.calls
    assert outputs[0]["type"] == "function_call_output"
    assert outputs[0]["call_id"] == "call_123"
    assert "error" in outputs[0]["output"]


def test_get_function_calls_filters_response_output_items() -> None:
    """Verify that only Responses API function calls are selected."""
    response = SimpleNamespace(
        output=[
            SimpleNamespace(type="message"),
            SimpleNamespace(type="function_call", name="list_activities"),
        ]
    )

    function_calls = example02.get_function_calls(response)

    assert len(function_calls) == 1
    assert function_calls[0].name == "list_activities"


def test_create_final_response_uses_stateless_input_for_zdr_compatibility() -> None:
    """Verify final response creation avoids `previous_response_id`."""
    client = FakeClient()
    function_call = {
        "type": "function_call",
        "call_id": "call_123",
        "name": "list_activities",
        "arguments": '{"begin_date": "2026-05-01", "end_date": "2026-05-10"}',
    }
    initial_response = SimpleNamespace(id="resp_missing", output=[function_call])
    tool_outputs = [
        {
            "type": "function_call_output",
            "call_id": "call_123",
            "output": "[]",
        }
    ]

    response = example02.create_final_response(
        client=client,
        model="gpt-oss-120b",
        user_message="Summarize my runs from 2026-05-01 to 2026-05-10.",
        initial_response=initial_response,
        tool_outputs=tool_outputs,
    )

    assert response.output_text == "final answer"
    assert "previous_response_id" not in client.responses.calls[0]
    assert client.responses.calls[0]["input"] == [
        {
            "role": "user",
            "content": "Summarize my runs from 2026-05-01 to 2026-05-10.",
        },
        function_call,
        *tool_outputs,
    ]
