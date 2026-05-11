"""
Author: L. Saetta
Date Modified: 2026-05-11
License: MIT
"""

from __future__ import annotations

import argparse
import logging
import os

from dotenv import load_dotenv

from services.garmin_api.training_data_provider import TrainingDataProvider


def configure_logging() -> None:
    """Reduce third-party Garmin library noise for command-line examples."""
    logging.getLogger("garminconnect").setLevel(logging.ERROR)


def add_activity_range_arguments(
    parser: argparse.ArgumentParser,
    *,
    start_name: str,
    end_name: str = "end_date",
) -> None:
    """Add shared Garmin date-range and activity-type CLI arguments.

    Args:
        parser: Argument parser to extend.
        start_name: Name of the positional start date argument.
        end_name: Name of the positional end date argument.
    """
    parser.add_argument(start_name, help="Inclusive start date in YYYY-MM-DD format.")
    parser.add_argument(end_name, help="Inclusive end date in YYYY-MM-DD format.")
    parser.add_argument(
        "--activity-type",
        default=None,
        help="Optional Garmin activity type, for example running or cycling.",
    )


def build_provider_from_environment() -> TrainingDataProvider:
    """Create a Garmin training data provider using local environment variables.

    The function loads `.env` when present and reads `GARMIN_USERNAME` and
    `GARMIN_PASSWORD`. When `GARMIN_SESSION_STORAGE_PATH` is set, Garmin session
    tokens are loaded from and saved to that path so repeated runs can avoid
    full credential login. It keeps credential handling outside command-line
    arguments so secrets are less likely to appear in shell history.

    Returns:
        A `TrainingDataProvider` authenticated with Garmin Connect credentials.

    Raises:
        RuntimeError: If either required credential is missing.
    """
    load_dotenv()

    username = os.getenv("GARMIN_USERNAME")
    password = os.getenv("GARMIN_PASSWORD")
    session_storage_path = os.getenv("GARMIN_SESSION_STORAGE_PATH")

    if not username or not password:
        raise RuntimeError(
            "GARMIN_USERNAME and GARMIN_PASSWORD must be set in the environment."
        )

    return TrainingDataProvider(
        username=username,
        password=password,
        session_storage_path=session_storage_path,
    )
