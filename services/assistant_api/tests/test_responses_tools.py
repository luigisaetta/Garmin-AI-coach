"""
Author: L. Saetta
Date Modified: 2026-05-12
License: MIT
"""

from __future__ import annotations

# pylint: disable=duplicate-code

from types import SimpleNamespace
from typing import Any

import pytest

from services.assistant_api.api.schemas import ChatMessage
from services.assistant_api.orchestration import responses_tools
from services.assistant_api.orchestration.prompts import SYSTEM_PROMPT
from services.assistant_api.orchestration.responses_tools import AssistantToolRunner


class FakeTrainingClient:  # pylint: disable=too-few-public-methods
    """Fake local training data client for tool execution tests."""

    def __init__(self) -> None:
        """Initialize captured calls."""
        self.calls: list[dict[str, str | None]] = []
        self.heart_rate_calls: list[dict[str, str]] = []

    async def list_activities(
        self,
        *,
        begin_date: str,
        end_date: str,
        activity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Capture the training data request and return one activity."""
        self.calls.append(
            {
                "begin_date": begin_date,
                "end_date": end_date,
                "activity_type": activity_type,
            }
        )
        return [{"activityId": 123, "activityName": "Morning Run"}]

    async def get_heart_rates(
        self,
        *,
        begin_date: str,
        end_date: str,
    ) -> dict[str, dict[str, Any]]:
        """Capture the heart-rate request and return one daily payload."""
        self.heart_rate_calls.append(
            {
                "begin_date": begin_date,
                "end_date": end_date,
            }
        )
        return {
            begin_date: {
                "calendarDate": begin_date,
                "restingHeartRate": 48,
            }
        }


class FailingTrainingClient:  # pylint: disable=too-few-public-methods
    """Fake local training client that simulates provider failure."""

    async def list_activities(
        self,
        *,
        begin_date: str,
        end_date: str,
        activity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Raise a provider error."""
        raise ValueError("Training data provider failed.")

    async def get_heart_rates(
        self,
        *,
        begin_date: str,
        end_date: str,
    ) -> dict[str, dict[str, Any]]:
        """Raise a provider error."""
        raise ValueError("Training data provider failed.")


def test_tool_definitions_include_activity_and_heart_rate_tools() -> None:
    """Verify both assistant tool schemas are exposed to the model."""
    runner = AssistantToolRunner(FakeTrainingClient())

    tool_names = {tool["name"] for tool in runner.tool_definitions()}

    assert tool_names == {"list_activities", "get_heart_rates"}
    assert "get_heart_rates" in SYSTEM_PROMPT


def test_build_model_input_includes_history_and_latest_request() -> None:
    """Verify that model input preserves chat history and the latest request."""
    model_input = responses_tools.build_model_input(
        latest_message="Summarise my week",
        history=[
            ChatMessage(role="user", content="What did I do yesterday?"),
            ChatMessage(role="assistant", content="You completed a run."),
        ],
        current_date="2026-05-11",
    )

    assert model_input == [
        {"role": "user", "content": "What did I do yesterday?"},
        {"role": "assistant", "content": "You completed a run."},
        {
            "role": "user",
            "content": (
                "Current date: 2026-05-11\n\n" "Latest user request: Summarise my week"
            ),
        },
    ]


def test_build_model_input_deduplicates_latest_request_from_frontend_history() -> None:
    """Verify that the latest frontend message is not sent twice."""
    model_input = responses_tools.build_model_input(
        latest_message="Summarise my week",
        history=[ChatMessage(role="user", content="Summarise my week")],
        current_date="2026-05-11",
    )

    assert len(model_input) == 1
    assert model_input[0]["content"].endswith("Latest user request: Summarise my week")


@pytest.mark.anyio
async def test_build_tool_outputs_uses_model_extracted_activity_range() -> None:
    """Verify that Garmin API calls use arguments extracted by the model."""
    training_client = FakeTrainingClient()
    function_call = SimpleNamespace(
        type="function_call",
        name="list_activities",
        call_id="call_123",
        arguments=(
            '{"begin_date": "2026-05-04", "end_date": "2026-05-10", '
            '"activity_type": "running"}'
        ),
    )

    outputs = await responses_tools.build_tool_outputs(
        function_calls=[function_call],
        tool_runner=AssistantToolRunner(training_client),
    )

    assert training_client.calls == [
        {
            "begin_date": "2026-05-04",
            "end_date": "2026-05-10",
            "activity_type": "running",
        }
    ]
    assert outputs[0]["type"] == "function_call_output"
    assert outputs[0]["call_id"] == "call_123"
    assert "Morning Run" in outputs[0]["output"]


@pytest.mark.anyio
async def test_build_tool_outputs_uses_model_extracted_heart_rate_range() -> None:
    """Verify that heart-rate tool calls use model-extracted date arguments."""
    training_client = FakeTrainingClient()
    function_call = SimpleNamespace(
        type="function_call",
        name="get_heart_rates",
        call_id="call_heart_rate",
        arguments='{"begin_date": "2026-05-04", "end_date": "2026-05-05"}',
    )

    outputs = await responses_tools.build_tool_outputs(
        function_calls=[function_call],
        tool_runner=AssistantToolRunner(training_client),
    )

    assert training_client.heart_rate_calls == [
        {
            "begin_date": "2026-05-04",
            "end_date": "2026-05-05",
        }
    ]
    assert outputs[0]["type"] == "function_call_output"
    assert outputs[0]["call_id"] == "call_heart_rate"
    assert "restingHeartRate" in outputs[0]["output"]


@pytest.mark.anyio
async def test_build_tool_outputs_returns_error_for_missing_dates() -> None:
    """Verify that invalid model tool arguments are returned as tool output."""
    training_client = FakeTrainingClient()
    function_call = {
        "type": "function_call",
        "name": "list_activities",
        "call_id": "call_123",
        "arguments": '{"activity_type": "running"}',
    }

    outputs = await responses_tools.build_tool_outputs(
        function_calls=[function_call],
        tool_runner=AssistantToolRunner(training_client),
    )

    assert not training_client.calls
    assert outputs[0]["type"] == "function_call_output"
    assert "error" in outputs[0]["output"]


def test_get_function_calls_supports_sdk_objects_and_dicts() -> None:
    """Verify that function calls are extracted from mixed response items."""
    response = SimpleNamespace(
        output=[
            SimpleNamespace(type="message"),
            SimpleNamespace(type="function_call", name="list_activities"),
            {"type": "function_call", "name": "list_activities"},
        ]
    )

    function_calls = responses_tools.get_function_calls(response)

    assert len(function_calls) == 2


def test_tool_data_sources_describe_unique_requested_tools() -> None:
    """Verify data-source metadata reflects model-selected Garmin tools."""
    function_calls = [
        SimpleNamespace(type="function_call", name="list_activities"),
        SimpleNamespace(type="function_call", name="get_heart_rates"),
        SimpleNamespace(type="function_call", name="get_heart_rates"),
    ]

    data_sources = responses_tools.tool_data_sources(function_calls)

    assert [source.type for source in data_sources] == [
        "garmin_activity_range",
        "garmin_heart_rate_range",
    ]


@pytest.mark.anyio
async def test_tool_runner_rejects_unsupported_tools() -> None:
    """Verify that unknown model-selected tools fail through the dispatcher."""
    runner = AssistantToolRunner(FakeTrainingClient())

    with pytest.raises(ValueError, match="Unsupported tool"):
        await runner.run_tool("unknown_tool", {})


@pytest.mark.anyio
async def test_build_tool_outputs_returns_error_when_training_provider_fails() -> None:
    """Verify provider failures are returned as tool outputs."""
    function_call = SimpleNamespace(
        type="function_call",
        name="list_activities",
        call_id="call_123",
        arguments='{"begin_date": "2026-05-04", "end_date": "2026-05-10"}',
    )

    outputs = await responses_tools.build_tool_outputs(
        function_calls=[function_call],
        tool_runner=AssistantToolRunner(FailingTrainingClient()),
    )

    assert outputs[0]["type"] == "function_call_output"
    assert "Training data provider failed" in outputs[0]["output"]
