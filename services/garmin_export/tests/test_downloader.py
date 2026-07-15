"""
Author: L. Saetta
Date Modified: 2026-07-15
License: MIT
"""

from __future__ import annotations

import hashlib
import json
from datetime import date

import pytest

from services.garmin_export.downloader import ExportRequest, GarminExportDownloader


class FakeTrainingClient:
    """Return deterministic user-scoped data without Garmin network access."""

    async def list_activities(self, **_kwargs):
        """Return one provider-compacted activity."""
        return [{"activityId": 123, "activityName": "Morning Run", "averageHR": 150}]

    async def get_heart_rates(self, **_kwargs):
        """Return one allowed and one removed daily field."""
        return {
            "2026-07-01": {
                "calendarDate": "2026-07-01",
                "restingHeartRate": 48,
                "ownerDisplayName": "private",
                "unexpected": "not exported",
            }
        }

    async def get_hrv_data(self, **_kwargs):
        """Return a present first day and an absent second day."""
        return {
            "2026-07-01": {"calendarDate": "2026-07-01", "lastNightAvg": 49},
            "2026-07-02": None,
        }


@pytest.mark.anyio
async def test_export_writes_complete_minimised_package(tmp_path) -> None:
    """Verify the package contract, PII omission, and manifest checksums."""
    request = ExportRequest(
        owner_id="local-user",
        begin_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
        output_root=tmp_path / "exports",
    )

    destination = await GarminExportDownloader(FakeTrainingClient()).export(request)

    assert (
        destination == tmp_path / "exports" / "local-user" / "2026-07-01_to_2026-07-02"
    )
    activity = _read_ndjson(destination / "activities.ndjson")
    assert activity == [
        {
            "data": {
                "activityId": 123,
                "activityName": "Morning Run",
                "averageHR": 150,
            },
            "dataset": "activities",
            "schema_version": 1,
            "source_key": "123",
            "owner_id": "local-user",
        }
    ]
    heart_rates = _read_ndjson(destination / "daily_heart_rate.ndjson")
    assert heart_rates[0]["data"] == {
        "calendarDate": "2026-07-01",
        "restingHeartRate": 48,
    }
    assert heart_rates[1]["data"] is None
    assert _read_ndjson(destination / "daily_hrv.ndjson")[1]["data"] is None

    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["owner_id"] == "local-user"
    assert manifest["datasets"]["daily_hrv"]["record_count"] == 2
    for dataset in manifest["datasets"].values():
        contents = (destination / dataset["file"]).read_bytes()
        assert dataset["sha256"] == hashlib.sha256(contents).hexdigest()


@pytest.mark.anyio
async def test_export_rejects_existing_completed_destination(tmp_path) -> None:
    """Verify a repeated request cannot overwrite a completed package."""
    request = ExportRequest(
        owner_id="local-user",
        begin_date=date(2026, 7, 1),
        end_date=date(2026, 7, 1),
        output_root=tmp_path,
    )
    request.destination.mkdir(parents=True)

    with pytest.raises(FileExistsError):
        await GarminExportDownloader(FakeTrainingClient()).export(request)


def _read_ndjson(path):
    """Read one NDJSON file for assertions."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
