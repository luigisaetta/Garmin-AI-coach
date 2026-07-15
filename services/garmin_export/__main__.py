"""
Author: L. Saetta
Date Modified: 2026-07-15
License: MIT
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date
from getpass import getpass
from pathlib import Path

from services.assistant_api.orchestration.training_data import LocalTrainingDataClient
from services.garmin_api.training_data_provider import TrainingDataProvider
from services.garmin_export.downloader import ExportRequest, GarminExportDownloader


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for a single date-range export."""
    parser = argparse.ArgumentParser(
        description="Export the current coach Garmin data scope as a portable package."
    )
    parser.add_argument("--username", required=True, help="Garmin Connect username.")
    parser.add_argument("--from", dest="begin_date", required=True, type=_parse_date)
    parser.add_argument("--to", dest="end_date", required=True, type=_parse_date)
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Directory under which the export package is created.",
    )
    parser.add_argument(
        "--session-dir",
        type=Path,
        default=Path("data/garmin-export-session"),
        help="Local directory used to reuse the Garmin session token.",
    )
    parser.add_argument(
        "--owner-id",
        default="local-user",
        help="Opaque local identifier stored in the export package.",
    )
    return parser


def main() -> None:
    """Prompt for Garmin credentials and run one atomic portable export."""
    arguments = build_parser().parse_args()
    password = getpass("Garmin Connect password: ")
    if not password:
        raise SystemExit("A Garmin Connect password is required.")
    provider = TrainingDataProvider(
        username=arguments.username,
        password=password,
        session_storage_path=str(arguments.session_dir),
        redact_pii=True,
        compact_activity_payload=True,
    )
    destination = asyncio.run(
        GarminExportDownloader(LocalTrainingDataClient(provider)).export(
            ExportRequest(
                owner_id=arguments.owner_id,
                begin_date=arguments.begin_date,
                end_date=arguments.end_date,
                output_root=arguments.output,
            )
        )
    )
    print(f"Export completed: {destination}")


def _parse_date(value: str) -> date:
    """Parse an ISO date for CLI arguments."""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Dates must use YYYY-MM-DD.") from exc


if __name__ == "__main__":
    main()
