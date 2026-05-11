"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from examples import example02


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


def test_build_user_message_preserves_natural_language_request() -> None:
    """Verify that the model receives the user's natural-language request."""
    message = example02.build_user_message(
        "Summarize my running from 2026-05-01 to 2026-05-10."
    )

    assert "Summarize my running" in message
    assert "2026-05-01" in message
    assert "2026-05-10" in message


def test_build_tool_outputs_uses_model_tool_arguments() -> None:
    """Verify that tool execution uses model-extracted tool arguments."""
    provider = FakeProvider()
    function_call = SimpleNamespace(
        type="function_call",
        name="list_activities",
        call_id="call_123",
        arguments=(
            '{"begin_date": "2026-05-01", "end_date": "2026-05-10", '
            '"activity_type": "running"}'
        ),
    )

    outputs = example02.build_tool_outputs(
        function_calls=[function_call],
        provider=provider,
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


def test_build_tool_outputs_returns_error_for_missing_required_dates() -> None:
    """Verify that invalid model tool arguments are returned as tool errors."""
    provider = FakeProvider()
    function_call = SimpleNamespace(
        type="function_call",
        name="list_activities",
        call_id="call_123",
        arguments='{"activity_type": "running"}',
    )

    outputs = example02.build_tool_outputs(
        function_calls=[function_call],
        provider=provider,
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
