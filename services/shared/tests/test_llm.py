"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

import pytest

from services.shared import llm


@pytest.fixture(autouse=True)
def disable_dotenv_loading(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prevent local `.env` files from influencing unit tests."""
    monkeypatch.setattr(llm, "load_dotenv", lambda: False)


class FakeOpenAIClient:  # pylint: disable=too-few-public-methods
    """Small fake that captures OpenAI client constructor options."""

    def __init__(self, **options: object) -> None:
        """Store constructor options for assertions."""
        self.options = options


def client_options(client: object) -> dict[str, object]:
    """Return captured fake OpenAI client constructor options."""
    return getattr(client, "options")


def test_get_inference_client_uses_genai_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that the shared client reads required config from the environment."""
    monkeypatch.setenv("GENAI_API_KEY", "test-key")
    monkeypatch.setenv("REGION", "eu-frankfurt-1")
    monkeypatch.setattr(llm, "OpenAI", FakeOpenAIClient)

    client = llm.get_inference_client()

    assert client_options(client) == {
        "api_key": "test-key",
        "base_url": "https://inference.generativeai.eu-frankfurt-1.oci.oraclecloud.com/openai/v1",
        "max_retries": 2,
    }


def test_get_inference_client_prefers_explicit_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that explicit configuration overrides environment values."""
    monkeypatch.setenv("GENAI_API_KEY", "env-key")
    monkeypatch.setenv("REGION", "eu-frankfurt-1")
    monkeypatch.setattr(llm, "OpenAI", FakeOpenAIClient)

    client = llm.get_inference_client(
        api_key="explicit-key",
        region="us-ashburn-1",
        timeout=30.0,
        max_retries=4,
    )

    assert client_options(client) == {
        "api_key": "explicit-key",
        "base_url": "https://inference.generativeai.us-ashburn-1.oci.oraclecloud.com/openai/v1",
        "timeout": 30.0,
        "max_retries": 4,
    }


def test_build_oci_openai_base_url_strips_region_whitespace() -> None:
    """Verify that OCI OpenAI-compatible URLs are generated from region values."""
    assert (
        llm.build_oci_openai_base_url(" eu-frankfurt-1 ")
        == "https://inference.generativeai.eu-frankfurt-1.oci.oraclecloud.com/openai/v1"
    )


def test_get_inference_client_requires_region(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that missing region configuration fails fast."""
    monkeypatch.setenv("GENAI_API_KEY", "test-key")
    monkeypatch.delenv("REGION", raising=False)

    with pytest.raises(RuntimeError, match="REGION"):
        llm.get_inference_client()


def test_get_inference_client_requires_genai_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify that missing API key configuration fails fast."""
    monkeypatch.delenv("GENAI_API_KEY", raising=False)
    monkeypatch.setenv("REGION", "eu-frankfurt-1")

    with pytest.raises(RuntimeError, match="GENAI_API_KEY"):
        llm.get_inference_client()
