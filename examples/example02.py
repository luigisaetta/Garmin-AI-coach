"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
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

LOGGER = logging.getLogger(__name__)


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


def configure_example_logging() -> None:
    """Configure minimal progress logging for the example script."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    configure_logging()


def summarize_text(value: str, max_length: int = 120) -> str:
    """Return a compact one-line summary for log messages.

    Args:
        value: Text to summarize.
        max_length: Maximum number of characters to keep.

    Returns:
        Single-line summary truncated when needed.
    """
    compact = " ".join(value.split())
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 3]}..."


def log_duration(start_time: float) -> str:
    """Format elapsed wall-clock time for logging."""
    return f"{time.perf_counter() - start_time:.2f}s"


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
    start_time = time.perf_counter()
    LOGGER.info(
        "Waiting for Garmin list_activities begin_date=%s end_date=%s activity_type=%s",
        begin_date,
        end_date,
        activity_type or "all",
    )
    activities = provider.list_activities(
        begin_date=begin_date,
        end_date=end_date,
        activity_type=activity_type,
    )
    LOGGER.info(
        "Garmin list_activities returned %d activities in %s",
        len(activities),
        log_duration(start_time),
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


def response_output_as_input(response: Any) -> list[dict[str, Any]]:
    """Convert response output items into stateless follow-up input items.

    Some OpenAI-compatible providers do not retain `previous_response_id`
    server-side. In that case, the second request can include the first
    response's output items directly before the tool outputs.

    Args:
        response: Initial Responses API response object.

    Returns:
        JSON-serializable response output items.
    """
    input_items: list[dict[str, Any]] = []
    for item in getattr(response, "output", []):
        if hasattr(item, "model_dump"):
            input_items.append(item.model_dump(mode="json", exclude_none=True))
        elif isinstance(item, dict):
            input_items.append(item)
    return input_items


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


def create_final_response(
    client: Any,
    model: str,
    user_message: str,
    initial_response: Any,
    tool_outputs: list[dict[str, str]],
) -> Any:
    """Create the final model response after local tool execution.

    The function intentionally uses stateless input instead of
    `previous_response_id`. OCI/OpenAI-compatible deployments configured with
    Zero Data Retention reject `previous_response_id`, so the example carries
    the required context forward explicitly.

    Args:
        client: OpenAI-compatible SDK client.
        model: Model identifier.
        user_message: Original user message sent in the first request.
        initial_response: First Responses API response that requested tools.
        tool_outputs: Local tool outputs to send back to the model.

    Returns:
        Final Responses API response.
    """
    start_time = time.perf_counter()
    LOGGER.info("Waiting for Responses API final answer with stateless input")
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": user_message,
            },
            *response_output_as_input(initial_response),
            *tool_outputs,
        ],
    )
    LOGGER.info(
        "Responses API stateless final answer returned in %s: %s",
        log_duration(start_time),
        summarize_text(response.output_text),
    )
    return response


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
    user_message = build_user_message(args.request)

    start_time = time.perf_counter()
    LOGGER.info("Waiting for Responses API initial answer/tool decision")
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
        input=user_message,
        tools=[LIST_ACTIVITIES_TOOL],
    )
    function_calls = get_function_calls(response)
    LOGGER.info(
        "Responses API initial call returned %d tool call(s) in %s: %s",
        len(function_calls),
        log_duration(start_time),
        summarize_text(response.output_text),
    )

    if not function_calls:
        return response.output_text

    tool_outputs = build_tool_outputs(
        function_calls=function_calls,
        provider=provider,
    )
    final_response = create_final_response(
        client=client,
        model=model,
        user_message=user_message,
        initial_response=response,
        tool_outputs=tool_outputs,
    )
    return final_response.output_text


def main() -> None:
    """Run the Responses API example and print the final answer."""
    configure_example_logging()
    args = parse_args()
    print(ask_with_optional_activity_tool(args))


if __name__ == "__main__":
    main()
