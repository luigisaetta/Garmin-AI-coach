# Changelog

## 2026-05-12

### Added

- Added a frontend navigation menu for moving between the coaching chat and the nutrition diary demo page.
- Added a food diary UI with date selection, training type selection, free-text meal descriptions, notes, and a local draft preview.
- Added SQLite-backed nutrition diary persistence through a dedicated backend service.
- Added assistant API nutrition diary endpoints for saving, updating, and reading one selected day.
- Added a Docker Compose `assistant-data` volume for persistent nutrition diary storage across container stop and restart.
- Added a Next.js nutrition diary proxy route and connected the food diary page to the persistence API.
- Added `TrainingDataProvider.get_heart_rates(begin_date, end_date)` for inclusive Garmin heart-rate range access through the local provider boundary.
- Added the Responses API `get_heart_rates` assistant tool backed by the local provider boundary.
- Added `examples/example03.py` to print raw Garmin heart-rate payloads for a date range.
- Added mocked provider tests for heart-rate range calls, date validation, and PII masking.

### Changed

- Updated the project specification to include the heart-rate provider method while preserving the current Garmin provider boundary.
- Updated the assistant system prompt to choose between activity data, heart-rate data, or both based on the user request.
- Updated documentation and environment examples for the nutrition diary SQLite database path.

### Verified

- Frontend linting and production build pass for the nutrition diary UI.
- Added backend tests for nutrition diary persistence and API contracts.
- Python tests, formatting, and linting pass for backend services and examples.

## 2026-05-11

### Added

- Added the Next.js frontend chat interface with light and black themes, sidebar indicators, quick prompts, and a central chatbot conversation view.
- Added frontend proxy routes for assistant health checks and streamed chat responses.
- Added Markdown rendering for assistant messages, including GitHub-flavored Markdown support.
- Added Responses API tool-calling orchestration in the assistant backend.
- Added the first assistant tool, `list_activities`, backed by the local Python `TrainingDataProvider`.
- Added timestamped backend logs for assistant request flow, model calls, tool execution, and stream completion.

### Changed

- Simplified Garmin data access by removing the separate Garmin HTTP API approach from the initial architecture.
- Updated the assistant stream path to use real Responses API streaming for final model output.
- Updated project documentation and configuration examples to reflect the single assistant API plus local provider model.

### Verified

- Python tests, formatting, and linting pass for backend services.
- Frontend linting and production build pass.
