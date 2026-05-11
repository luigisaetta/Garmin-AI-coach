"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

OCI_OPENAI_BASE_URL_TEMPLATE = (
    "https://inference.generativeai.{region}.oci.oraclecloud.com/openai/v1"
)


def get_inference_client(
    *,
    api_key: str | None = None,
    region: str | None = None,
    timeout: float | None = None,
    max_retries: int = 2,
) -> OpenAI:
    """Create a shared OpenAI-compatible client for Responses API calls.

    The project uses OCI Enterprise AI with OpenAI-compatible hosted models.
    This helper centralizes client creation so assistant code can consistently
    use the same API key and endpoint configuration when calling the Responses
    API.

    Configuration is loaded from the local environment, including an optional
    `.env` file for development. Explicit function arguments take precedence
    over environment variables.

    Environment variables:
        GENAI_API_KEY: Required API key used to authenticate model requests.
        REGION: Required OCI region used to build the OpenAI-compatible
            inference endpoint.

    Args:
        api_key: Optional explicit API key. When omitted, `GENAI_API_KEY` is
            read from the environment.
        region: Optional explicit OCI region. When omitted, `REGION` is read
            from the environment.
        timeout: Optional request timeout in seconds.
        max_retries: Number of SDK-level retries for transient failures.

    Returns:
        Configured `OpenAI` SDK client suitable for Responses API calls.

    Raises:
        RuntimeError: If no API key is provided and `GENAI_API_KEY` is missing.
    """
    load_dotenv()

    resolved_api_key = api_key or os.getenv("GENAI_API_KEY")
    if not resolved_api_key:
        raise RuntimeError("GENAI_API_KEY must be set to create an inference client.")

    resolved_region = (region or os.getenv("REGION") or "").strip()
    if not resolved_region:
        raise RuntimeError("REGION must be set to create an inference client.")

    client_options: dict[str, Any] = {
        "api_key": resolved_api_key,
        "base_url": build_oci_openai_base_url(resolved_region),
        "max_retries": max_retries,
    }

    if timeout is not None:
        client_options["timeout"] = timeout

    return OpenAI(**client_options)


def build_oci_openai_base_url(region: str) -> str:
    """Build the OCI OpenAI-compatible inference base URL for a region.

    Args:
        region: OCI region identifier, for example `eu-frankfurt-1`.

    Returns:
        OpenAI-compatible OCI Generative AI endpoint base URL.

    Raises:
        ValueError: If `region` is blank.
    """
    normalized_region = region.strip()
    if not normalized_region:
        raise ValueError("region must not be blank.")

    return OCI_OPENAI_BASE_URL_TEMPLATE.format(region=normalized_region)
