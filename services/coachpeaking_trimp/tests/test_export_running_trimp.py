"""
Author: L. Saetta
Date Modified: 2026-07-17
License: MIT
"""

# pylint: disable=too-few-public-methods

import csv
from datetime import date
from pathlib import Path

import pytest

from services.coachpeaking_trimp.export_running_trimp import (
    ActivitySelectors,
    CSV_COLUMNS,
    RunningTrimpRecord,
    extract_running_records,
    parse_activity_date,
    parse_trimp,
    write_review_csv,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2025-01-15", date(2025, 1, 15)),
        ("15/01/2025", date(2025, 1, 15)),
        ("Allenamento 15-01-2025", date(2025, 1, 15)),
    ],
)
def test_parse_activity_date_supports_expected_display_formats(
    value: str, expected: date
) -> None:
    """Parse common CoachPeaking numeric activity-date formats."""
    assert parse_activity_date(value) == expected


@pytest.mark.parametrize("value", ("TRIMP: 42,5", "42.5", "0"))
def test_parse_trimp_accepts_non_negative_display_values(value: str) -> None:
    """Accept decimal commas and a zero TRIMP score."""
    assert parse_trimp(value) in {0.0, 42.5}


@pytest.mark.parametrize("value", ("not available", "TRIMP: -2"))
def test_parse_trimp_rejects_invalid_or_negative_values(value: str) -> None:
    """Reject values that cannot be valid model labels."""
    with pytest.raises(ValueError):
        parse_trimp(value)


def test_write_review_csv_writes_only_required_columns_in_date_order(
    tmp_path: Path,
) -> None:
    """Keep the review export limited to running type, date, and TRIMP."""
    output_path = tmp_path / "coachpeaking-running-2025.csv"
    records = [
        RunningTrimpRecord("running", date(2025, 2, 1), 42.5),
        RunningTrimpRecord("running", date(2025, 1, 15), 10.0),
    ]

    write_review_csv(records, output_path)

    with output_path.open(encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    assert tuple(rows[0]) == CSV_COLUMNS
    assert rows == [
        {"activity_type": "running", "date": "2025-01-15", "trimp": "10"},
        {"activity_type": "running", "date": "2025-02-01", "trimp": "42.5"},
    ]


def test_extract_running_records_excludes_other_sports_and_years() -> None:
    """Retain only displayed running activities from the requested year."""
    page = _FakePage(
        [
            {"type": "Running", "date": "15/01/2025", "trimp": "42,5"},
            {"type": "Cycling", "date": "16/01/2025", "trimp": "30"},
            {"type": "Corsa", "date": "31/12/2024", "trimp": "20"},
        ]
    )
    selectors = ActivitySelectors(
        row="row", activity_type="type", activity_date="date", trimp="trimp"
    )

    records = list(extract_running_records(page, 2025, selectors))

    assert records == [RunningTrimpRecord("running", date(2025, 1, 15), 42.5)]


class _FakePage:
    """Small Playwright-shaped fixture used to test row filtering without a browser."""

    def __init__(self, rows: list[dict[str, str]]) -> None:
        self._rows = [_FakeRow(row) for row in rows]

    def locator(self, selector: str) -> "_FakeRowCollection":
        """Return all configured fake activity rows."""
        assert selector == "row"
        return _FakeRowCollection(self._rows)


class _FakeRowCollection:
    """Expose the subset of Playwright locator methods the extractor uses."""

    def __init__(self, rows: list["_FakeRow"]) -> None:
        self.first = _FakeWaitableLocator()
        self._rows = rows

    def all(self) -> list["_FakeRow"]:
        """Return each fake activity row."""
        return self._rows


class _FakeWaitableLocator:
    """Provide the attachment wait used before extraction starts."""

    def wait_for(self, **_kwargs: object) -> None:
        """Treat fixture rows as attached immediately."""


class _FakeRow:
    """Map selectors to text locators for a synthetic activity row."""

    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def locator(self, selector: str) -> "_FakeTextCollection":
        """Return a text locator for the requested synthetic field."""
        return _FakeTextCollection(self._values.get(selector))


class _FakeTextCollection:
    """Expose the first property expected from a Playwright text locator."""

    def __init__(self, value: str | None) -> None:
        self.first = _FakeTextLocator(value)


class _FakeTextLocator:
    """Expose count and inner text for one synthetic table cell."""

    def __init__(self, value: str | None) -> None:
        self._value = value

    def count(self) -> int:
        """Return whether the requested fake cell exists."""
        return int(self._value is not None)

    def inner_text(self) -> str:
        """Return the synthetic cell contents."""
        return self._value or ""
