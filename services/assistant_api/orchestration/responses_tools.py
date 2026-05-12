"""
Author: L. Saetta
Date Modified: 2026-05-12
License: MIT
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from services.assistant_api.api.schemas import ChatMessage, DataSource
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

GET_HEART_RATES_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "get_heart_rates",
    "description": (
        "Return Garmin daily heart-rate payloads for an inclusive date range. "
        "Use this for questions about resting heart rate, daily heart-rate "
        "patterns, heart-rate trends, or heart-rate values not tied to one "
        "specific workout."
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
            "response_language": {
                "type": "string",
                "enum": ["italian", "english"],
                "description": (
                    "Language for the nutrition report. Choose italian when "
                    "the latest user request is in Italian, and english when "
                    "the latest user request is in English."
                ),
            },
        },
        "required": ["begin_date", "end_date", "response_language"],
        "additionalProperties": False,
    },
}

ANALYZE_NUTRITION_ADHERENCE_TOOL: dict[str, Any] = {
    "type": "function",
    "name": "analyze_nutrition_adherence_period",
    "description": (
        "Run the nutrition analysis subagent for an inclusive date range. "
        "Use this when the user asks to analyze nutrition adherence, compare "
        "their food diary with the current nutrition plan, or relate nutrition "
        "to training load for a specific period."
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
        },
        "required": ["begin_date", "end_date"],
        "additionalProperties": False,
    },
}

BASE_TOOLS = [
    LIST_ACTIVITIES_TOOL,
    GET_HEART_RATES_TOOL,
]


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


def tool_data_sources(function_calls: list[Any]) -> list[DataSource]:
    """Build safe frontend data-source descriptions for requested tools."""
    sources_by_type = {
        "list_activities": DataSource(
            type="garmin_activity_range",
            description="Activities returned by the local training provider.",
        ),
        "get_heart_rates": DataSource(
            type="garmin_heart_rate_range",
            description="Heart-rate data returned by the local training provider.",
        ),
        "analyze_nutrition_adherence_period": DataSource(
            type="nutrition_adherence_analysis",
            description=(
                "Nutrition analysis produced by the local nutrition subagent "
                "from the current plan, diary entries, and training summaries."
            ),
        ),
    }
    data_sources: list[DataSource] = []
    seen_types: set[str] = set()

    for call in function_calls:
        tool_name = str(_get_item_value(call, "name"))
        data_source = sources_by_type.get(tool_name)
        if data_source is None or data_source.type in seen_types:
            continue
        data_sources.append(data_source)
        seen_types.add(data_source.type)

    return data_sources


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
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
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

    def __init__(
        self,
        training_client: TrainingActivitiesClient,
        nutrition_analysis_agent: Any | None = None,
    ) -> None:
        """Create a tool runner with access to backend service clients."""
        self._training_client = training_client
        self._nutrition_analysis_agent = nutrition_analysis_agent

    def tool_definitions(self) -> list[dict[str, Any]]:
        """Return the tool schemas exposed to the model."""
        if self._nutrition_analysis_agent is None:
            return BASE_TOOLS
        return [*BASE_TOOLS, ANALYZE_NUTRITION_ADHERENCE_TOOL]

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
        if tool_name == "get_heart_rates":
            return await self._run_get_heart_rates(arguments)
        if tool_name == "analyze_nutrition_adherence_period":
            return await self._run_analyze_nutrition_adherence(arguments)

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

    async def _run_get_heart_rates(self, arguments: dict[str, Any]) -> str:
        """Run the Garmin heart-rate range tool."""
        LOGGER.info(
            "tool get_heart_rates start begin_date=%s end_date=%s",
            arguments.get("begin_date"),
            arguments.get("end_date"),
        )
        heart_rates = await self._training_client.get_heart_rates(
            begin_date=arguments["begin_date"],
            end_date=arguments["end_date"],
        )
        LOGGER.info("tool get_heart_rates done day_count=%d", len(heart_rates))
        return json.dumps({"heart_rates": heart_rates}, default=str)

    async def _run_analyze_nutrition_adherence(
        self,
        arguments: dict[str, Any],
    ) -> str:
        """Run the nutrition analysis subagent tool."""
        if self._nutrition_analysis_agent is None:
            raise ValueError("Nutrition analysis tool is not configured.")

        begin_date = date.fromisoformat(arguments["begin_date"])
        end_date = date.fromisoformat(arguments["end_date"])
        LOGGER.info(
            "tool analyze_nutrition_adherence_period start begin_date=%s end_date=%s",
            begin_date,
            end_date,
        )
        result = await self._nutrition_analysis_agent.analyze(
            begin_date=begin_date,
            end_date=end_date,
            response_language=arguments.get("response_language"),
        )
        LOGGER.info(
            "tool analyze_nutrition_adherence_period done diary_entries=%d "
            "missing_days=%d training_days=%d",
            result.diary_entry_count,
            len(result.missing_diary_dates),
            result.training_day_count,
        )
        return json.dumps(_nutrition_analysis_output(result), default=str)


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


def _nutrition_analysis_output(result: Any) -> dict[str, Any]:
    """Convert nutrition subagent output into a model tool payload."""
    return {
        "period": {
            "begin_date": result.begin_date.isoformat(),
            "end_date": result.end_date.isoformat(),
        },
        "report": result.report,
        "sources": {
            "plan_filename": result.plan_filename,
            "diary_entry_count": result.diary_entry_count,
            "missing_diary_dates": [
                missing_date.isoformat() for missing_date in result.missing_diary_dates
            ],
            "training_day_count": result.training_day_count,
        },
        "token_usage": (
            result.token_usage.model_dump() if result.token_usage is not None else None
        ),
    }


def _get_item_value(item: Any, key: str) -> Any:
    """Read a value from either an SDK object or a plain dictionary."""
    if isinstance(item, dict):
        return item.get(key)
    return getattr(item, key, None)
