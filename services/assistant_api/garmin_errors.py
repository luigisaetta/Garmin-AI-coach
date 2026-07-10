"""
Author: L. Saetta
Date Modified: 2026-07-10
License: MIT
"""

from __future__ import annotations

from garminconnect.exceptions import (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

GARMIN_LOGIN_BLOCKED_MESSAGE = (
    "Garmin Connect login failed. Garmin may be rate-limiting this server, "
    "requiring CAPTCHA/MFA, or rejecting an expired session. Wait before "
    "retrying, complete any Garmin Connect browser challenge, then test the "
    "credentials again from the account page."
)

GARMIN_PROVIDER_ERRORS = (
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)


def safe_garmin_error_message(exc: BaseException) -> str:
    """Return a user-safe message for Garmin provider failures."""
    details = str(exc).strip()
    if not details:
        return GARMIN_LOGIN_BLOCKED_MESSAGE

    normalized_details = details.lower()
    if any(
        marker in normalized_details
        for marker in ("429", "captcha", "rate limit", "rate-limited", "http 403")
    ):
        return GARMIN_LOGIN_BLOCKED_MESSAGE

    return f"Garmin Connect access failed: {details}"
