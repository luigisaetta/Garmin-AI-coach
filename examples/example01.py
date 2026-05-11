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

from services.garmin_api.training_data_provider import TrainingDataProvider


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the local provider example.

    Returns:
        Parsed arguments containing the inclusive start date, inclusive end date,
        and optional Garmin activity type filter. Dates must use ISO
        `YYYY-MM-DD` format because they are forwarded to the provider without
        additional interpretation.
    """
    parser = argparse.ArgumentParser(
        description="List Garmin Connect activities for a date range."
    )
    parser.add_argument("start_date", help="Inclusive start date in YYYY-MM-DD format.")
    parser.add_argument("end_date", help="Inclusive end date in YYYY-MM-DD format.")
    parser.add_argument(
        "--activity-type",
        default=None,
        help="Optional Garmin activity type, for example running or cycling.",
    )
    return parser.parse_args()


def build_provider_from_environment() -> TrainingDataProvider:
    """Create a Garmin training data provider using local environment variables.

    The function loads `.env` when present and reads `GARMIN_USERNAME` and
    `GARMIN_PASSWORD`. It keeps credential handling outside command-line
    arguments so secrets are less likely to appear in shell history.

    Returns:
        A `TrainingDataProvider` authenticated with Garmin Connect credentials.

    Raises:
        RuntimeError: If either required credential is missing.
    """
    load_dotenv()

    username = os.getenv("GARMIN_USERNAME")
    password = os.getenv("GARMIN_PASSWORD")

    if not username or not password:
        raise RuntimeError(
            "GARMIN_USERNAME and GARMIN_PASSWORD must be set in the environment."
        )

    return TrainingDataProvider(username=username, password=password)


def main() -> None:
    """Run the example and print returned Garmin activities as formatted JSON.

    The example performs a direct local Python call to `TrainingDataProvider`.
    It is intended for manual development checks before the Garmin data API HTTP
    service is scaffolded.
    """
    args = parse_args()
    provider = build_provider_from_environment()
    activities = provider.list_activities(
        begin_date=args.start_date,
        end_date=args.end_date,
        activity_type=args.activity_type,
    )
    print(json.dumps(activities, indent=2, sort_keys=True, default=_json_default))


def _json_default(value: Any) -> str:
    """Convert otherwise non-serializable values into strings for JSON output.

    Args:
        value: Value passed by `json.dumps` when the default encoder does not
            know how to serialize it.

    Returns:
        String representation of the value.
    """
    return str(value)


if __name__ == "__main__":
    main()
