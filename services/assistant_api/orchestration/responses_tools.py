"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

import json
import logging
from typing import Any

from services.assistant_api.api.schemas import ChatMessage
from services.assistant_api.orchestration.training_data import TrainingActivitiesClient

LOGGER = logging.getLogger(__name__)

LIST_ACTIVITIES_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "list_activities",
    "description": (
        "Return Garmin training activities for an inclusive date range. "
        "Use this when answering questions about workouts, weekly training, "
        "activity volume, pace, heart rate, or recent training history."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "begin_date": {
                "type": "string",
                "description": "Inclusive start date in YYYY-MM-DD format.",
            },
            "end_date": {
                "type": "string",
                "description": "Inclusive end date in YYYY-MM-DD format.",
            },
            "activity_type": {
                "type": "string",
                "description": (
                    "Optional Garmin activity type filter, such as running, "
                    "cycling, swimming, walking, or hiking."
                ),
            },
        },
        "required": ["begin_date", "end_date"],
        "additionalProperties": False,
    },
}

AVAILABLE_TOOLS = [LIST_ACTIVITIES_TOOL]

SYSTEM_PROMPT = """
You are Garmin AI Coach, a careful training assistant for one athlete.

Use the conversation history and the latest user request to decide whether
Garmin activity data is needed. When data is needed, call the list_activities
tool. Extract begin_date and end_date from the user's natural-language request
in YYYY-MM-DD format. If the user asks for a relative period, infer the range
from the current date supplied in the latest user message. Include activity_type
only when the user requests a specific sport.

Do not claim to have seen Garmin data unless it was returned by a tool. Do not
invent workouts, distances, paces, heart-rate values, or training load. Keep
answers practical and coaching-oriented. Treat all training data as private:
summarize only what is needed for the answer and avoid exposing unnecessary raw
payload details.
""".strip()


def build_model_input(
    *,
    latest_message: str,
    history: list[ChatMessage],
    current_date: str,
) -> list[dict[str, str]]:
    """Build Responses API input from frontend history and latest request."""
    input_items = [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in history
    ]

    if input_items and input_items[-1] == {"role": "user", "content": latest_message}:
        input_items.pop()

    input_items.append(
        {
            "role": "user",
            "content": (
                f"Current date: {current_date}\n\n"
                f"Latest user request: {latest_message}"
            ),
        }
    )
    return input_items


def get_function_calls(response: Any) -> list[Any]:
    """Extract Responses API function-call output items."""
    return [
        item
        for item in getattr(response, "output", [])
        if _get_item_value(item, "type") == "function_call"
    ]


def response_output_as_input(response: Any) -> list[dict[str, Any]]:
    """Convert response output items into stateless follow-up input items."""
    input_items: list[dict[str, Any]] = []
    for item in getattr(response, "output", []):
        if hasattr(item, "model_dump"):
            input_items.append(item.model_dump(mode="json", exclude_none=True))
        elif isinstance(item, dict):
            input_items.append(item)
    return input_items


async def build_tool_outputs(
    *,
    function_calls: list[Any],
    tool_runner: "AssistantToolRunner",
) -> list[dict[str, str]]:
    """Execute supported model-requested tool calls."""
    outputs: list[dict[str, str]] = []

    for call in function_calls:
        call_id = str(_get_item_value(call, "call_id"))
        tool_name = str(_get_item_value(call, "name"))
        try:
            arguments = parse_tool_arguments(call)
            output = await tool_runner.run_tool(tool_name, arguments)
        except (KeyError, TypeError, ValueError) as exc:
            output = json.dumps({"error": str(exc)})

        outputs.append(
            {
                "type": "function_call_output",
                "call_id": call_id,
                "output": output,
            }
        )

    return outputs


class AssistantToolRunner:
    """Execute model-selected assistant tools behind one generic dispatcher."""

    def __init__(self, training_client: TrainingActivitiesClient) -> None:
        """Create a tool runner with access to backend service clients."""
        self._training_client = training_client

    def tool_definitions(self) -> list[dict[str, Any]]:
        """Return the tool schemas exposed to the model."""
        return AVAILABLE_TOOLS

    async def run_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        """Run one model-selected tool by name.

        Args:
            tool_name: Function name emitted by the Responses API.
            arguments: JSON arguments emitted by the model for that function.

        Returns:
            JSON string to send back as `function_call_output`.

        Raises:
            ValueError: If the model requests an unsupported tool.
        """
        if tool_name == "list_activities":
            return await self._run_list_activities(arguments)

        raise ValueError(f"Unsupported tool requested: {tool_name}")

    async def _run_list_activities(self, arguments: dict[str, Any]) -> str:
        """Run the Garmin activity range tool."""
        LOGGER.info(
            "tool list_activities start begin_date=%s end_date=%s activity_type=%s",
            arguments.get("begin_date"),
            arguments.get("end_date"),
            arguments.get("activity_type") or "all",
        )
        activities = await self._training_client.list_activities(
            begin_date=arguments["begin_date"],
            end_date=arguments["end_date"],
            activity_type=arguments.get("activity_type"),
        )
        LOGGER.info("tool list_activities done activity_count=%d", len(activities))
        return json.dumps({"activities": activities}, default=str)


def parse_tool_arguments(function_call: Any) -> dict[str, Any]:
    """Parse JSON tool arguments emitted by a Responses API function call."""
    raw_arguments = _get_item_value(function_call, "arguments") or "{}"
    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        raise ValueError("Tool arguments must be valid JSON.") from exc

    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be a JSON object.")
    return arguments


def _get_item_value(item: Any, key: str) -> Any:
    """Read a value from either an SDK object or a plain dictionary."""
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)
