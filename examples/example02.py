"""
Author: L. Saetta
Date Modified: 2026-05-12
License: MIT
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import time
from typing import Any

from dotenv import load_dotenv

from examples.common import build_provider_from_environment, configure_logging
from services.assistant_api.orchestration.prompts import SYSTEM_PROMPT
from services.assistant_api.orchestration.responses_tools import (
    AssistantToolRunner,
    build_tool_outputs,
    get_function_calls,
    response_output_as_input,
)
from services.assistant_api.orchestration.training_data import LocalTrainingDataClient
from services.shared.llm import get_inference_client

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


async def ask_with_optional_activity_tool(args: argparse.Namespace) -> str:
    """Ask the model a question, allowing one round of Garmin tool use.

    Args:
        args: Parsed command-line arguments.

    Returns:
        Final model answer text.
    """
    client = get_inference_client()
    provider = build_provider_from_environment()
    training_client = LocalTrainingDataClient(provider)
    tool_runner = AssistantToolRunner(training_client)
    model = get_model_id()
    user_message = build_user_message(args.request)

    start_time = time.perf_counter()
    LOGGER.info("Waiting for Responses API initial answer/tool decision")
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=user_message,
        tools=tool_runner.tool_definitions(),
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

    tool_outputs = await build_tool_outputs(
        function_calls=function_calls,
        tool_runner=tool_runner,
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
    print(asyncio.run(ask_with_optional_activity_tool(args)))


if __name__ == "__main__":
    main()
