"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

from dotenv import load_dotenv

from examples.common import build_provider_from_environment, configure_logging
from services.garmin_api.training_data_provider import TrainingDataProvider
from services.shared.llm import get_inference_client

LIST_ACTIVITIES_TOOL = {
    "type": "function",
    "name": "list_activities",
    "description": "Return Garmin Connect activities for the requested date range.",
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
                "description": "Optional Garmin activity type filter.",
            },
        },
        "required": ["begin_date", "end_date"],
        "additionalProperties": False,
    },
}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the Responses API example.

    Returns:
        Parsed arguments containing the user request as a single natural
        language string.
    """
    parser = argparse.ArgumentParser(
        description="Ask the LLM a question with optional Garmin activity tool access."
    )
    parser.add_argument("request", help="Natural-language request to ask the model.")
    return parser.parse_args()


def build_user_message(request: str) -> str:
    """Build the user message sent to the model.

    Args:
        request: Natural-language request supplied by the user. The request may
            include dates and an activity type; the model decides whether to
            call the Garmin activity tool.

    Returns:
        Message text sent to the model.
    """
    return request


def get_model_id() -> str:
    """Return the configured model identifier for Responses API calls."""
    load_dotenv()
    return os.getenv("OCI_MODEL_ID", "openai.gpt-5.4")


def run_list_activities_tool(
    provider: TrainingDataProvider,
    begin_date: str,
    end_date: str,
    activity_type: str | None,
) -> str:
    """Execute the local Garmin activity tool and serialize its output.

    Args:
        provider: Garmin training data provider.
        begin_date: Inclusive start date controlled by the CLI.
        end_date: Inclusive end date controlled by the CLI.
        activity_type: Optional CLI activity type filter.

    Returns:
        JSON string containing the sanitized Garmin activities.
    """
    activities = provider.list_activities(
        begin_date=begin_date,
        end_date=end_date,
        activity_type=activity_type,
    )
    return json.dumps(activities, default=str)


def parse_tool_arguments(function_call: Any) -> dict[str, Any]:
    """Parse tool arguments emitted by the model.

    Args:
        function_call: Responses API function call item.

    Returns:
        Parsed function arguments.

    Raises:
        ValueError: If the model produced invalid JSON arguments.
    """
    try:
        return json.loads(function_call.arguments or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("Tool arguments must be valid JSON.") from exc


def get_function_calls(response: Any) -> list[Any]:
    """Extract function call items from a Responses API response object.

    Args:
        response: Response object returned by the OpenAI SDK.

    Returns:
        Function call output items, or an empty list when no tool was requested.
    """
    return [
        item
        for item in getattr(response, "output", [])
        if getattr(item, "type", None) == "function_call"
    ]


def build_tool_outputs(
    function_calls: list[Any],
    provider: TrainingDataProvider,
) -> list[dict[str, str]]:
    """Execute supported tool calls and build Responses API tool outputs.

    The model supplies tool arguments, including date range and optional
    activity type, based on the user's natural-language request.

    Args:
        function_calls: Function calls requested by the model.
        provider: Garmin training data provider.

    Returns:
        Tool output messages to send back to the Responses API.
    """
    tool_outputs: list[dict[str, str]] = []

    for call in function_calls:
        if getattr(call, "name", None) != "list_activities":
            output = json.dumps({"error": f"Unsupported tool: {call.name}"})
        else:
            try:
                arguments = parse_tool_arguments(call)
                output = run_list_activities_tool(
                    provider=provider,
                    begin_date=arguments["begin_date"],
                    end_date=arguments["end_date"],
                    activity_type=arguments.get("activity_type"),
                )
            except (KeyError, ValueError) as exc:
                output = json.dumps({"error": str(exc)})

        tool_outputs.append(
            {
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": output,
            }
        )

    return tool_outputs


def ask_with_optional_activity_tool(args: argparse.Namespace) -> str:
    """Ask the model a question, allowing one round of Garmin tool use.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Final model answer text.
    """
    client = get_inference_client()
    provider = build_provider_from_environment()
    model = get_model_id()

    response = client.responses.create(
        model=model,
        instructions=(
            "You are a concise training assistant. Use the Garmin activity tool "
            "only when activity data is needed to answer the question. Extract "
            "begin_date and end_date from the user's request in YYYY-MM-DD "
            "format before calling the tool. Include activity_type only when "
            "the user asks for a specific activity type. Do not invent data "
            "that was not returned by the tool."
        ),
        input=build_user_message(args.request),
        tools=[LIST_ACTIVITIES_TOOL],
    )

    function_calls = get_function_calls(response)
    if not function_calls:
        return response.output_text

    tool_outputs = build_tool_outputs(
        function_calls=function_calls,
        provider=provider,
    )
    final_response = client.responses.create(
        model=model,
        previous_response_id=response.id,
        input=tool_outputs,
    )
    return final_response.output_text


def main() -> None:
    """Run the Responses API example and print the final answer."""
    configure_logging()
    args = parse_args()
    print(ask_with_optional_activity_tool(args))


if __name__ == "__main__":
    main()
