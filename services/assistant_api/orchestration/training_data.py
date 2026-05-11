"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

from typing import Any, Protocol


class TrainingActivitiesClient(Protocol):  # pylint: disable=too-few-public-methods
    """Protocol for assistant tool access to local training data."""

    async def list_activities(
        self,
        *,
        begin_date: str,
        end_date: str,
        activity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return activities from the local training data provider."""


class LocalTrainingDataClient:  # pylint: disable=too-few-public-methods
    """Async adapter around the local Python training data provider."""

    def __init__(self, provider: Any) -> None:
        """Create a local training data client.

        Args:
            provider: Object exposing `list_activities`, normally
                `TrainingDataProvider`.
        """
        self._provider = provider

    async def list_activities(
        self,
        *,
        begin_date: str,
        end_date: str,
        activity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return activities for a date range using local Python calls."""
        return self._provider.list_activities(
            begin_date=begin_date,
            end_date=end_date,
            activity_type=activity_type,
        )
