"""
Author: L. Saetta
Date Modified: 2026-05-12
License: MIT
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from examples.common import build_provider_from_environment, configure_logging


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the heart-rate provider example.

    Returns:
        Parsed arguments containing the inclusive start and end date. Dates
        must use ISO `YYYY-MM-DD` format because they are forwarded directly to
        the local provider boundary.
    """
    parser = argparse.ArgumentParser(
        description="Print raw Garmin Connect heart-rate payloads for a date range."
    )
    parser.add_argument("begin_date", help="Inclusive start date in YYYY-MM-DD format.")
    parser.add_argument("end_date", help="Inclusive end date in YYYY-MM-DD format.")
    return parser.parse_args()


def main() -> None:
    """Run the example and print daily Garmin heart-rate data as JSON."""
    configure_logging()
    args = parse_args()
    provider = build_provider_from_environment()
    heart_rates = provider.get_heart_rates(
        begin_date=args.begin_date,
        end_date=args.end_date,
    )
    print(json.dumps(heart_rates, indent=2, sort_keys=True, default=_json_default))


def _json_default(value: Any) -> str:
    """Convert otherwise non-serializable values into strings for JSON output."""
    return str(value)


if __name__ == "__main__":
    main()
