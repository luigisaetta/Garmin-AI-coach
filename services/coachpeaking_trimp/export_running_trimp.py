"""
Author: L. Saetta
Date Modified: 2026-07-17
License: MIT

Export completed CoachPeaking running TRIMP values through Playwright.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

DEFAULT_APP_URL = "https://app.coachpeaking.com/"
DEFAULT_ROW_SELECTOR = "tr[data-activity-id], .activity-item, .workout-item"
DEFAULT_ACTIVITY_TYPE_SELECTOR = ".activity-type, .sport, [data-field='activity-type']"
DEFAULT_DATE_SELECTOR = "time, .activity-date, .date, [data-field='date']"
DEFAULT_TRIMP_SELECTOR = ".trimp, [data-field='trimp'], [data-metric='trimp']"
CSV_COLUMNS = ("activity_type", "date", "trimp")
RUNNING_ACTIVITY_TYPES = frozenset({"run", "running", "corsa"})
DATE_PATTERN = re.compile(r"\b(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})\b")
NUMBER_PATTERN = re.compile(r"-?\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class ActivitySelectors:
    """CSS selectors used to read one activity row from CoachPeaking."""

    row: str = DEFAULT_ROW_SELECTOR
    activity_type: str = DEFAULT_ACTIVITY_TYPE_SELECTOR
    activity_date: str = DEFAULT_DATE_SELECTOR
    trimp: str = DEFAULT_TRIMP_SELECTOR


@dataclass(frozen=True)
class RunningTrimpRecord:
    """One completed running activity exported for label review."""

    activity_type: str
    activity_date: date
    trimp: float

    def to_csv_row(self) -> dict[str, str]:
        """Return the approved privacy-minimal CSV representation."""
        return {
            "activity_type": self.activity_type,
            "date": self.activity_date.isoformat(),
            "trimp": _format_trimp(self.trimp),
        }


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for login and export modes."""
    parser = argparse.ArgumentParser(
        description="Export CoachPeaking 2025 running activity dates and TRIMP values."
    )
    parser.add_argument(
        "--storage-state",
        type=Path,
        default=Path(".coachpeaking/storage-state.json"),
        help="Local Playwright session-state path; never commit this file.",
    )
    parser.add_argument(
        "--activities-url",
        default=DEFAULT_APP_URL,
        help="Authenticated CoachPeaking page containing the filtered activity list.",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open a visible browser and save the session after manual login.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/coachpeaking-trimp-labels/coachpeaking-running-2025.csv"),
        help="Review CSV path to create.",
    )
    parser.add_argument(
        "--year", type=int, default=2025, help="Activity year to export."
    )
    parser.add_argument("--row-selector", default=DEFAULT_ROW_SELECTOR)
    parser.add_argument(
        "--activity-type-selector", default=DEFAULT_ACTIVITY_TYPE_SELECTOR
    )
    parser.add_argument("--date-selector", default=DEFAULT_DATE_SELECTOR)
    parser.add_argument("--trimp-selector", default=DEFAULT_TRIMP_SELECTOR)
    return parser


def save_login_session(app_url: str, storage_state: Path) -> None:
    """Open CoachPeaking for manual login and store the local browser session."""
    storage_state.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(app_url, wait_until="domcontentloaded")
        input(
            "Complete login in the browser, then press Enter here to save the session. "
        )
        context.storage_state(path=str(storage_state))
        browser.close()


def export_running_trimp(
    activities_url: str,
    storage_state: Path,
    output_path: Path,
    activity_year: int,
    selectors: ActivitySelectors,
) -> int:
    """Export matching activity rows from an already-filtered authenticated page."""
    if not storage_state.is_file():
        raise ValueError(
            f"CoachPeaking session state not found: {storage_state}. Run with --login first."
        )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(storage_state))
        page = context.new_page()
        page.goto(activities_url, wait_until="networkidle")
        records = list(extract_running_records(page, activity_year, selectors))
        browser.close()
    write_review_csv(records, output_path)
    return len(records)


def extract_running_records(
    page: Page, activity_year: int, selectors: ActivitySelectors
) -> Iterable[RunningTrimpRecord]:
    """Read valid running records from the currently displayed activity list."""
    try:
        page.locator(selectors.row).first.wait_for(state="attached", timeout=10_000)
    except PlaywrightTimeoutError as exc:
        raise ValueError(
            "No activity rows found. Open the 2025 activity list and adjust --row-selector."
        ) from exc

    for row in page.locator(selectors.row).all():
        activity_type = _required_text(row, selectors.activity_type, "activity type")
        if _normalise_activity_type(activity_type) not in RUNNING_ACTIVITY_TYPES:
            continue
        activity_date = parse_activity_date(
            _required_text(row, selectors.activity_date, "activity date")
        )
        if activity_date.year != activity_year:
            continue
        trimp = parse_trimp(_required_text(row, selectors.trimp, "TRIMP"))
        yield RunningTrimpRecord("running", activity_date, trimp)


def write_review_csv(records: Iterable[RunningTrimpRecord], output_path: Path) -> None:
    """Write a privacy-minimal, chronologically ordered CoachPeaking review CSV."""
    sorted_records = sorted(
        records, key=lambda record: (record.activity_date, record.trimp)
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(record.to_csv_row() for record in sorted_records)


def parse_activity_date(value: str) -> date:
    """Extract an ISO or Italian numeric date from one CoachPeaking cell."""
    match = DATE_PATTERN.search(value)
    if match is None:
        raise ValueError(f"No supported date found in activity value: {value!r}")
    candidate = match.group(1)
    formats = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d")
    for date_format in formats:
        try:
            return datetime.strptime(candidate, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid activity date: {candidate!r}")


def parse_trimp(value: str) -> float:
    """Extract one non-negative decimal TRIMP score from a displayed cell."""
    match = NUMBER_PATTERN.search(value)
    if match is None:
        raise ValueError(f"No numeric TRIMP value found: {value!r}")
    trimp = float(match.group(0).replace(",", "."))
    if trimp < 0:
        raise ValueError(f"TRIMP must be non-negative: {value!r}")
    return trimp


def _required_text(row: Locator, selector: str, field_name: str) -> str:
    """Return stripped text for a required descendant selector."""
    locator = row.locator(selector).first
    if locator.count() == 0:
        raise ValueError(f"Missing {field_name}; adjust the relevant CSS selector.")
    value = locator.inner_text().strip()
    if not value:
        raise ValueError(f"Empty {field_name}; adjust the relevant CSS selector.")
    return value


def _normalise_activity_type(value: str) -> str:
    """Normalise a displayed CoachPeaking sport label for an exact comparison."""
    return " ".join(value.casefold().split())


def _format_trimp(value: float) -> str:
    """Format TRIMP without adding meaningless trailing zeroes."""
    return f"{value:g}"


def main() -> None:
    """Run manual login or create the CoachPeaking review export."""
    arguments = build_parser().parse_args()
    if arguments.login:
        save_login_session(arguments.activities_url, arguments.storage_state)
        return
    selectors = ActivitySelectors(
        row=arguments.row_selector,
        activity_type=arguments.activity_type_selector,
        activity_date=arguments.date_selector,
        trimp=arguments.trimp_selector,
    )
    count = export_running_trimp(
        arguments.activities_url,
        arguments.storage_state,
        arguments.output,
        arguments.year,
        selectors,
    )
    print(
        f"CoachPeaking running TRIMP review export created: {arguments.output} ({count} activities)"
    )


if __name__ == "__main__":
    main()
