"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from examples.common import (
    add_activity_range_arguments,
    build_provider_from_environment,
    configure_logging,
)


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
    add_activity_range_arguments(parser, start_name="start_date")
    return parser.parse_args()


def main() -> None:
    """Run the example and print returned Garmin activities as formatted JSON.

    The example performs a direct local Python call to `TrainingDataProvider`.
    It is intended for manual development checks before the Garmin data API HTTP
    service is scaffolded.
    """
    configure_logging()
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
