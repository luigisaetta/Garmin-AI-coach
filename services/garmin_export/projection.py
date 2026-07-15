"""
Author: L. Saetta
Date Modified: 2026-07-15
License: MIT
"""

from __future__ import annotations

from typing import Any

from services.garmin_api.training_data_provider import PII_EXACT_KEYS, PII_KEY_FRAGMENTS

HEART_RATE_FIELDS = frozenset(
    {
        "calendarDate",
        "restingHeartRate",
        "lastSevenDaysAvgRestingHeartRate",
        "minHeartRate",
        "maxHeartRate",
        "averageHeartRate",
        "heartRateValues",
        "heartRateValueDescriptors",
    }
)
HRV_FIELDS = frozenset(
    {
        "calendarDate",
        "lastNightAvg",
        "lastNight5MinHigh",
        "weeklyAvg",
        "weeklyHigh",
        "baselineLowUpper",
        "baselineBalancedLow",
        "baselineBalancedUpper",
        "status",
    }
)


def project_heart_rate(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return only daily heart-rate fields relevant to the coach."""
    return _project_payload(payload, HEART_RATE_FIELDS)


def project_hrv(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return only daily HRV fields relevant to the coach."""
    return _project_payload(payload, HRV_FIELDS)


def _project_payload(
    payload: dict[str, Any] | None, permitted_fields: frozenset[str]
) -> dict[str, Any] | None:
    """Filter a daily provider payload without retaining masked PII."""
    if payload is None:
        return None

    return {
        key: value
        for key, value in payload.items()
        if key in permitted_fields and not _is_pii_key(key)
    }


def _is_pii_key(key: str) -> bool:
    """Return whether a field name is personal or location-related metadata."""
    normalized_key = key.casefold()
    return key in PII_EXACT_KEYS or any(
        fragment in normalized_key for fragment in PII_KEY_FRAGMENTS
    )
