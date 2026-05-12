"""
Author: L. Saetta
Date Modified: 2026-05-12
License: MIT
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import uuid4

from services.assistant_api.api.schemas import (
    DataSource,
    ChatRequest,
    ChatResponse,
    ChatStreamEvent,
    TokenUsage,
)
from services.assistant_api.orchestration.prompts import SYSTEM_PROMPT
from services.assistant_api.orchestration.responses_tools import (
    AssistantToolRunner,
    build_model_input,
    build_tool_outputs,
    get_function_calls,
    response_output_as_input,
    tool_data_sources,
)
from services.assistant_api.orchestration.training_data import TrainingActivitiesClient

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AssistantSettings:
    """Runtime settings for the assistant orchestration layer."""

    model_id: str


class AssistantOrchestrator:
    """Assistant orchestration boundary for frontend chat requests."""

    def __init__(
        self,
        *,
        settings: AssistantSettings,
        inference_client: Any,
        training_client: TrainingActivitiesClient,
        nutrition_analysis_agent: Any | None = None,
    ) -> None:
        """Create an assistant orchestrator.

        Args:
            settings: Runtime model and service settings.
            inference_client: OpenAI-compatible client for Responses API calls.
            training_client: Local training data client used by assistant tools.
            nutrition_analysis_agent: Optional nutrition subagent used by assistant
                tools for period adherence analysis.
        """
        self._settings = settings
        self._inference_client = inference_client
        self._tool_runner = AssistantToolRunner(
            training_client,
            nutrition_analysis_agent=nutrition_analysis_agent,
        )

    async def complete_chat(self, request: ChatRequest) -> ChatResponse:
        """Return a complete chat answer for callers that do not stream."""
        conversation_id = request.conversation_id or str(uuid4())
        LOGGER.info(
            "chat complete start conversation_id=%s history_messages=%d message_length=%d",
            conversation_id,
            len(request.messages),
            len(request.message),
        )
        model_input = build_model_input(
            latest_message=request.message,
            history=request.messages,
            current_date=date.today().isoformat(),
        )
        LOGGER.info("responses initial request conversation_id=%s", conversation_id)
        initial_response = self._inference_client.responses.create(
            model=self._settings.model_id,
            instructions=SYSTEM_PROMPT,
            input=model_input,
            tools=self._tool_runner.tool_definitions(),
        )
        function_calls = get_function_calls(initial_response)
        LOGGER.info(
            "responses initial result conversation_id=%s tool_calls=%d",
            conversation_id,
            len(function_calls),
        )

        if not function_calls:
            LOGGER.info("chat complete done conversation_id=%s", conversation_id)
            return ChatResponse(
                answer=initial_response.output_text,
                conversation_id=conversation_id,
                token_usage=response_token_usage(initial_response),
            )

        LOGGER.info("tool execution start conversation_id=%s", conversation_id)
        tool_outputs = await build_tool_outputs(
            function_calls=function_calls,
            tool_runner=self._tool_runner,
        )
        LOGGER.info("tool execution done conversation_id=%s", conversation_id)
        LOGGER.info("responses final request conversation_id=%s", conversation_id)
        final_response = self._inference_client.responses.create(
            model=self._settings.model_id,
            instructions=SYSTEM_PROMPT,
            input=[
                *model_input,
                *response_output_as_input(initial_response),
                *tool_outputs,
            ],
        )
        LOGGER.info("chat complete done conversation_id=%s", conversation_id)
        return ChatResponse(
            answer=final_response.output_text,
            conversation_id=conversation_id,
            data_sources=tool_data_sources(function_calls),
            token_usage=combine_token_usage(
                response_token_usage(initial_response),
                response_token_usage(final_response),
            ),
        )

    async def stream_chat(self, request: ChatRequest) -> AsyncIterator[ChatStreamEvent]:
        """Stream the final model answer through Responses API streaming."""
        conversation_id = request.conversation_id or str(uuid4())
        data_sources: list[DataSource] = []
        LOGGER.info(
            "chat stream start conversation_id=%s history_messages=%d message_length=%d",
            conversation_id,
            len(request.messages),
            len(request.message),
        )
        model_input = build_model_input(
            latest_message=request.message,
            history=request.messages,
            current_date=date.today().isoformat(),
        )
        LOGGER.info("responses initial request conversation_id=%s", conversation_id)
        initial_response = self._inference_client.responses.create(
            model=self._settings.model_id,
            instructions=SYSTEM_PROMPT,
            input=model_input,
            tools=self._tool_runner.tool_definitions(),
        )
        function_calls = get_function_calls(initial_response)
        LOGGER.info(
            "responses initial result conversation_id=%s tool_calls=%d",
            conversation_id,
            len(function_calls),
        )

        final_input, data_sources = await self._build_final_stream_input(
            conversation_id=conversation_id,
            model_input=model_input,
            initial_response=initial_response,
            function_calls=function_calls,
        )

        LOGGER.info("responses stream request conversation_id=%s", conversation_id)
        answer = ""
        stream_manager = self._inference_client.responses.stream(
            model=self._settings.model_id,
            instructions=SYSTEM_PROMPT,
            input=final_input,
        )
        with stream_manager as stream:
            for event in stream:
                delta = self._extract_stream_delta(event)
                if delta:
                    answer += delta
                    yield ChatStreamEvent(
                        type="message_delta",
                        conversation_id=conversation_id,
                        delta=delta,
                    )

            final_response = stream.get_final_response()
            completed_text = str(_get_event_value(final_response, "output_text") or "")
            if completed_text:
                answer = completed_text

        LOGGER.info(
            "responses stream done conversation_id=%s answer_length=%d",
            conversation_id,
            len(answer),
        )
        yield ChatStreamEvent(
            type="message_done",
            conversation_id=conversation_id,
            answer=answer,
            data_sources=data_sources,
            token_usage=combine_token_usage(
                response_token_usage(initial_response),
                response_token_usage(final_response),
            ),
        )

    async def _build_final_stream_input(
        self,
        *,
        conversation_id: str,
        model_input: list[dict[str, str]],
        initial_response: Any,
        function_calls: list[Any],
    ) -> tuple[list[dict[str, Any]], list[DataSource]]:
        """Build the final streamed model input, executing tools when needed."""
        if not function_calls:
            LOGGER.info(
                "responses stream replays no-tool answer conversation_id=%s",
                conversation_id,
            )
            return model_input, []

        LOGGER.info("tool execution start conversation_id=%s", conversation_id)
        tool_outputs = await build_tool_outputs(
            function_calls=function_calls,
            tool_runner=self._tool_runner,
        )
        LOGGER.info("tool execution done conversation_id=%s", conversation_id)
        return [
            *model_input,
            *response_output_as_input(initial_response),
            *tool_outputs,
        ], tool_data_sources(function_calls)

    @staticmethod
    def _extract_stream_delta(event: Any) -> str:
        """Extract text deltas from Responses API stream events."""
        event_type = _get_event_value(event, "type")
        if event_type in {"response.output_text.delta", "response.refusal.delta"}:
            return str(_get_event_value(event, "delta") or "")
        return ""

    @staticmethod
    def _extract_completed_text(event: Any) -> str:
        """Extract completed text when an SDK stream does not emit deltas."""
        event_type = _get_event_value(event, "type")
        if event_type != "response.completed":
            return ""

        response = _get_event_value(event, "response")
        return str(_get_event_value(response, "output_text") or "")


def _get_event_value(event: Any, key: str) -> Any:
    """Read a Responses stream event value from SDK objects or dictionaries."""
    if isinstance(event, dict):
        return event.get(key)
    return getattr(event, key, None)


def combine_token_usage(*items: TokenUsage | None) -> TokenUsage | None:
    """Add token usage values from multiple Responses API calls."""
    present_items = [item for item in items if item is not None]
    if not present_items:
        return None

    return TokenUsage(
        input_tokens=sum(item.input_tokens for item in present_items),
        output_tokens=sum(item.output_tokens for item in present_items),
        total_tokens=sum(item.total_tokens for item in present_items),
    )


def response_token_usage(response: Any) -> TokenUsage | None:
    """Extract token usage from an SDK response object or plain dictionary."""
    usage = _get_event_value(response, "usage")
    if usage is None:
        return None

    input_tokens = _get_int_value(usage, "input_tokens")
    output_tokens = _get_int_value(usage, "output_tokens")
    total_tokens = _get_int_value(usage, "total_tokens")
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens

    return TokenUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
    )


def _get_int_value(item: Any, key: str) -> int:
    """Read an integer value from an SDK object or plain dictionary."""
    value = _get_event_value(item, key)
    if value is None:
        return 0
    return int(value)
