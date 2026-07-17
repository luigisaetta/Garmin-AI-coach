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

DEFAULT_APP_URL = (
    "https://app.coachpeaking.com/"
    + "scheda_allenamento_atleta.php?prima=3&dopo=4&oggi=1"
)
DEFAULT_ROW_SELECTOR = (
    ".evento-attivita.attivita-sport-1, " + ".evento-allenamento.allenamento-sport-1"
)
DEFAULT_ACTIVITY_TYPE_SELECTOR = ""
DEFAULT_DATE_SELECTOR = "xpath=ancestor::div[contains(@class, 'calendar-table__cell')]"
DEFAULT_TRIMP_SELECTOR = ".ev-all__content--trimp"
CSV_COLUMNS = ("activity_type", "date", "trimp")
RUNNING_ACTIVITY_TYPES = frozenset({"run", "running", "corsa"})
DATE_PATTERN = re.compile(r"\b(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})\b")
CALENDAR_DAY_CLASS_PATTERN = re.compile(r"\bday-(\d{4}-\d{2}-\d{2})\b")
MONTH_PATTERN = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
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
        description="Export CoachPeaking running activity dates and TRIMP values."
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
        help="Authenticated CoachPeaking calendar page.",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open a visible browser and save the session after manual login.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Review CSV path to create; defaults to a month-specific filename.",
    )
    parser.add_argument(
        "--month",
        type=parse_month,
        help="Calendar month to export in YYYY-MM form, for example 2025-01.",
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
    activity_month: date,
    selectors: ActivitySelectors,
) -> int:
    """Select one calendar month and export its matching activity rows."""
    if not storage_state.is_file():
        raise ValueError(
            f"CoachPeaking session state not found: {storage_state}. Run with --login first."
        )
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(storage_state))
        page = context.new_page()
        page.goto(activities_url, wait_until="networkidle")
        select_calendar_month(page, activity_month)
        records = list(extract_running_records(page, activity_month, selectors))
        browser.close()
    write_review_csv(records, output_path)
    return len(records)


def extract_running_records(
    page: Page, activity_month: date, selectors: ActivitySelectors
) -> Iterable[RunningTrimpRecord]:
    """Read valid running records from the currently displayed activity list."""
    try:
        page.locator(selectors.row).first.wait_for(state="attached", timeout=10_000)
    except PlaywrightTimeoutError as exc:
        raise ValueError(
            "No activity rows found. Open the 2025 activity list and adjust --row-selector."
        ) from exc

    for row in page.locator(selectors.row).all():
        if selectors.activity_type:
            activity_type = _required_text(
                row, selectors.activity_type, "activity type"
            )
            if _normalise_activity_type(activity_type) not in RUNNING_ACTIVITY_TYPES:
                continue
        activity_date = _row_activity_date(row, selectors.activity_date)
        if _month_start(activity_date) != activity_month:
            continue
        trimp_text = _optional_text(row, selectors.trimp)
        if trimp_text is None:
            continue
        trimp = parse_trimp(trimp_text)
        yield RunningTrimpRecord("running", activity_date, trimp)


def select_calendar_month(page: Page, activity_month: date) -> None:
    """Select one month through the CoachPeaking calendar datepicker."""
    page.locator(".datepicker.compact .input-group-addon").first.click()
    picker = _first_visible(
        page.locator(".bootstrap-datetimepicker-widget"), "calendar datepicker"
    )
    picker_switch = _first_visible(
        picker.locator("[data-action='pickerSwitch']"), "calendar month switch"
    )
    picker_switch.click()
    _first_visible(
        picker.locator("[data-action='pickerSwitch']"), "calendar year switch"
    ).click()
    _first_visible(
        picker.locator("span.year", has_text=str(activity_month.year)),
        f"year {activity_month.year}",
    ).click()
    _first_visible(
        picker.locator("span.month").nth(activity_month.month - 1),
        f"month {activity_month.month}",
    ).click()
    _first_visible(
        picker.locator(f"td[data-day='{_datepicker_day(activity_month)}']"),
        f"first day of {activity_month:%Y-%m}",
    ).click()
    try:
        page.locator(
            f".calendar-table__cell.day-{activity_month.isoformat()}"
        ).first.wait_for(state="visible", timeout=15_000)
    except PlaywrightTimeoutError as exc:
        raise ValueError(
            f"CoachPeaking did not display the requested month: {activity_month:%Y-%m}"
        ) from exc


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


def parse_month(value: str) -> date:
    """Parse a requested calendar month in strict YYYY-MM form."""
    match = MONTH_PATTERN.fullmatch(value)
    if match is None:
        raise argparse.ArgumentTypeError("Month must use YYYY-MM format.")
    return date(int(match.group(1)), int(match.group(2)), 1)


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


def _optional_text(row: Locator, selector: str) -> str | None:
    """Return stripped text for an optional descendant selector."""
    locator = row.locator(selector).first
    if locator.count() == 0:
        return None
    value = locator.inner_text().strip()
    return value or None


def _row_activity_date(row: Locator, selector: str) -> date:
    """Read the activity date from text or the CoachPeaking calendar-cell class."""
    date_element = row.locator(selector).first
    if date_element.count() == 0:
        raise ValueError("Missing activity date; adjust --date-selector.")
    class_value = date_element.get_attribute("class") or ""
    class_match = CALENDAR_DAY_CLASS_PATTERN.search(class_value)
    if class_match is not None:
        return date.fromisoformat(class_match.group(1))
    return parse_activity_date(date_element.inner_text())


def _first_visible(locator: Locator, description: str) -> Locator:
    """Return the first visible locator, skipping hidden CoachPeaking templates."""
    for candidate in locator.all():
        if candidate.is_visible():
            return candidate
    raise ValueError(f"No visible {description} found in CoachPeaking calendar.")


def _normalise_activity_type(value: str) -> str:
    """Normalise a displayed CoachPeaking sport label for an exact comparison."""
    return " ".join(value.casefold().split())


def _month_start(value: date) -> date:
    """Return the canonical first day used for month comparisons."""
    return value.replace(day=1)


def _datepicker_day(activity_month: date) -> str:
    """Format the first calendar day as required by the CoachPeaking widget."""
    return activity_month.strftime("%d/%m/%Y")


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
    if arguments.month is None:
        build_parser().error("--month is required unless --login is used.")
    output_path = arguments.output or _default_output_path(arguments.month)
    count = export_running_trimp(
        arguments.activities_url,
        arguments.storage_state,
        output_path,
        arguments.month,
        selectors,
    )
    print(
        f"CoachPeaking running TRIMP review export created: {output_path} ({count} activities)"
    )


def _default_output_path(activity_month: date) -> Path:
    """Return a month-specific path that cannot overwrite another month by default."""
    filename = f"coachpeaking-running-{activity_month:%Y-%m}.csv"
    return Path("data/coachpeaking-trimp-labels") / filename


if __name__ == "__main__":
    main()
