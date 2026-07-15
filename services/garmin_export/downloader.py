"""
Author: L. Saetta
Date Modified: 2026-07-15
License: MIT
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
import shutil
import tempfile
from typing import Any

from services.assistant_api.orchestration.training_data import TrainingActivitiesClient
from services.garmin_export.projection import project_heart_rate, project_hrv

SCHEMA_VERSION = 1
EXPORTER_VERSION = "0.1.0"
DATASET_FILES = {
    "activities": "activities.ndjson",
    "daily_heart_rate": "daily_heart_rate.ndjson",
    "daily_hrv": "daily_hrv.ndjson",
}


@dataclass(frozen=True)
class ExportRequest:  # pylint: disable=too-few-public-methods
    """Validated input for a single portable Garmin export."""

    owner_id: str
    begin_date: date
    end_date: date
    output_root: Path

    def __post_init__(self) -> None:
        """Validate the date range and non-sensitive local owner identifier."""
        if not self.owner_id or self.owner_id in {".", ".."}:
            raise ValueError("owner_id must be a non-empty safe identifier")
        if any(character in self.owner_id for character in ("/", "\\")):
            raise ValueError("owner_id must not contain path separators")
        if self.begin_date > self.end_date:
            raise ValueError("begin_date must be earlier than or equal to end_date")

    @property
    def destination(self) -> Path:
        """Return the completed export directory for this request."""
        range_name = f"{self.begin_date.isoformat()}_to_{self.end_date.isoformat()}"
        return self.output_root / self.owner_id / range_name


class GarminExportDownloader:  # pylint: disable=too-few-public-methods
    """Download the coach data scope and write an atomic export package."""

    def __init__(self, training_client: TrainingActivitiesClient) -> None:
        """Create an exporter using the existing user-scoped training client."""
        self._training_client = training_client

    async def export(self, request: ExportRequest) -> Path:
        """Fetch scoped Garmin data and return the completed package path."""
        destination = request.destination
        if destination.exists():
            raise FileExistsError(f"Export destination already exists: {destination}")

        activities = await self._training_client.list_activities(
            user_id=1,
            begin_date=request.begin_date.isoformat(),
            end_date=request.end_date.isoformat(),
        )
        heart_rates = await self._training_client.get_heart_rates(
            user_id=1,
            begin_date=request.begin_date.isoformat(),
            end_date=request.end_date.isoformat(),
        )
        hrv_data = await self._training_client.get_hrv_data(
            user_id=1,
            begin_date=request.begin_date.isoformat(),
            end_date=request.end_date.isoformat(),
        )

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_directory = Path(
            tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
        )
        try:
            dataset_counts = self._write_datasets(
                directory=temporary_directory,
                request=request,
                activities=activities,
                heart_rates=heart_rates,
                hrv_data=hrv_data,
            )
            self._write_manifest(
                directory=temporary_directory,
                request=request,
                dataset_counts=dataset_counts,
            )
            temporary_directory.replace(destination)
        except Exception:
            shutil.rmtree(temporary_directory, ignore_errors=True)
            raise

        return destination

    def _write_datasets(
        self,
        *,
        directory: Path,
        request: ExportRequest,
        activities: list[dict[str, Any]],
        heart_rates: dict[str, dict[str, Any]],
        hrv_data: dict[str, dict[str, Any] | None],
    ) -> dict[str, int]:
        """Write the three scoped datasets and return their record counts."""
        activity_records = [
            _record(
                dataset="activities",
                owner_id=request.owner_id,
                source_key=_activity_source_key(activity),
                data=activity,
            )
            for activity in activities
        ]
        heart_rate_records = [
            _record(
                dataset="daily_heart_rate",
                owner_id=request.owner_id,
                source_key=calendar_date,
                data=project_heart_rate(heart_rates.get(calendar_date)),
            )
            for calendar_date in _inclusive_dates(request.begin_date, request.end_date)
        ]
        hrv_records = [
            _record(
                dataset="daily_hrv",
                owner_id=request.owner_id,
                source_key=calendar_date,
                data=project_hrv(hrv_data.get(calendar_date)),
            )
            for calendar_date in _inclusive_dates(request.begin_date, request.end_date)
        ]

        records_by_dataset = {
            "activities": activity_records,
            "daily_heart_rate": heart_rate_records,
            "daily_hrv": hrv_records,
        }
        for dataset, records in records_by_dataset.items():
            _write_ndjson(directory / DATASET_FILES[dataset], records)

        return {
            dataset: len(records) for dataset, records in records_by_dataset.items()
        }

    @staticmethod
    def _write_manifest(
        *,
        directory: Path,
        request: ExportRequest,
        dataset_counts: dict[str, int],
    ) -> None:
        """Write a manifest only after all data files have been completed."""
        datasets = {
            dataset: {
                "file": filename,
                "record_count": dataset_counts[dataset],
                "sha256": _file_sha256(directory / filename),
            }
            for dataset, filename in DATASET_FILES.items()
        }
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "exporter_version": EXPORTER_VERSION,
            "status": "completed",
            "owner_id": request.owner_id,
            "begin_date": request.begin_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "completed_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "datasets": datasets,
        }
        with (directory / "manifest.json").open("w", encoding="utf-8") as output:
            json.dump(manifest, output, indent=2, sort_keys=True)
            output.write("\n")


def _record(
    *, dataset: str, owner_id: str, source_key: str, data: dict[str, Any] | None
) -> dict[str, Any]:
    """Build one schema-versioned portable export record."""
    return {
        "dataset": dataset,
        "schema_version": SCHEMA_VERSION,
        "owner_id": owner_id,
        "source_key": source_key,
        "data": data,
    }


def _activity_source_key(activity: dict[str, Any]) -> str:
    """Return the required activity identifier without accepting missing data."""
    activity_id = activity.get("activityId")
    if activity_id is None:
        raise ValueError("Activity export requires activityId")
    return str(activity_id)


def _inclusive_dates(begin_date: date, end_date: date) -> list[str]:
    """Return ISO dates for a validated inclusive interval."""
    day_count = (end_date - begin_date).days
    return [
        date.fromordinal(begin_date.toordinal() + offset).isoformat()
        for offset in range(day_count + 1)
    ]


def _write_ndjson(path: Path, records: list[dict[str, Any]]) -> None:
    """Write compact UTF-8 JSON records, one per line."""
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, separators=(",", ":"), sort_keys=True))
            output.write("\n")


def _file_sha256(path: Path) -> str:
    """Return the SHA-256 checksum of a completed file."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
