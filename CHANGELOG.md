# Changelog

## 2026-07-15

### Changed

- Documented that Garmin Connect access now uses only the multi-user credential
  repository and user-scoped session storage. The legacy single-user Garmin
  credential and token path is abandoned and must not be used as a fallback.
- Added the Coach Overview dashboard requirement to the project specification,
  with goal-adherence explicitly deferred until user goal management exists.
- Added a separate Coach Overview frontend page as the first navigation item,
  summarising recent volume, current load, weekly trend, recovery caution, and
  sport mix from existing user-scoped training endpoints.
- Improved Coach Overview interpretation for the active ISO week so partial
  week-to-date load is labelled clearly and projected before comparison with
  completed weeks.

## 2026-07-10

### Added

- Added the Training metrics dashboard for run, bike, and swim summaries over a
  selected date range.
- Added derived training metrics including load per hour, duration-weighted
  heart rate, and average aerobic and anaerobic training effect.
- Added on-demand LLM analysis for Training metrics through a dedicated backend
  service and Responses API endpoint.
- Added the Training trends dashboard with weekly ISO-week load trends,
  sport-specific stacked load, four-week rolling average, week-over-week delta,
  and acute/chronic load ratio.

### Changed

- Switched the default OCI hosted model identifier to `openai.gpt-5.5`.
- Added sidebar navigation for the new Training trends page.

### Verified

- Python tests, formatting, and linting pass.
- Frontend linting and production build pass.
- Docker Compose deployment on Proxima was rebuilt and verified healthy.

## 2026-05-22

### Changed

- Updated the project specification to make MySQL Community Edition the
  long-term local persistence target for Docker Compose deployments.
- Documented the dedicated MySQL container, host-filesystem-backed storage, and
  future SQLite-to-MySQL migration requirement for identity, Garmin credential
  metadata, nutrition diary entries, and nutrition plans.
- Added a Docker Compose MySQL CE service with host-backed data storage.
- Replaced runtime SQLite repository access with a confined SQLAlchemy Core
  persistence layer using MySQL configuration from environment variables.
- Added a SQLite-to-MySQL migration command for local users, encrypted Garmin
  credential metadata, nutrition diary entries, and current nutrition plans.
- Updated README, Quickstart, and multi-user migration notes for the MySQL
  deployment model.
- Increased the NGINX request body limit so nutrition-plan PDF uploads can
  reach the frontend and assistant backend.

### Verified

- Targeted backend persistence tests pass.

## 2026-05-15

### Added

- Added optional Garmin activity payload compaction through `GARMIN_COMPACT_ACTIVITY_PAYLOAD` to reduce assistant tool token usage while preserving coaching-relevant fields.
- Added a server-side Responses API nutrition diary rewrite workflow and frontend "Rewrite with AI" action for unsaved meal-text cleanup.

### Changed

- Updated README, Quickstart, specification milestones, and multi-user migration notes to reflect the current local multi-user implementation.
- Clarified that nutrition adherence analysis is now available on demand through assistant tooling.
- Reclassified Milestone 6 and Milestone 7 items into implemented capabilities and remaining follow-up work.
- Documented Basic Auth logout limitations and current residual multi-user polish items.

### Verified

- Documentation-only update; no application code changed.

## 2026-05-13

### Added

- Added a final quantitative adherence rubric to nutrition analysis reports with 1 to 10 LLM-estimated scores for plan adherence, meal structure match, food choice alignment, training-day alignment, and assessment confidence.

### Changed

- Rounded finite floating-point Garmin provider payload values to a fixed maximum precision before exposing sanitized activity data.
- Updated chat token usage aggregation to include token usage reported by tool outputs, including the nutrition analysis subagent.

### Verified

- Python tests, formatting, and linting pass for the affected provider, assistant orchestration, and nutrition analysis modules.

## 2026-05-12

### Added

- Added a frontend navigation menu for moving between the coaching chat and the nutrition diary demo page.
- Added a food diary UI with date selection, training type selection, free-text meal descriptions, notes, and a local draft preview.
- Added SQLite-backed nutrition diary persistence through a dedicated backend service.
- Added assistant API nutrition diary endpoints for saving, updating, and reading one selected day.
- Added assistant API nutrition-plan endpoints for uploading one current PDF plan and reading the extracted current plan.
- Added a Docker Compose `assistant-data` volume for persistent nutrition storage across container stop and restart.
- Added a Next.js nutrition diary proxy route and connected the food diary page to the persistence API.
- Added a Next.js nutrition-plan upload proxy route and connected the food diary page to PDF plan upload status.
- Added PDF text extraction with `pypdf`; the MVP stores extracted text and metadata but does not retain the original PDF.
- Added `TrainingDataProvider.get_heart_rates(begin_date, end_date)` for inclusive Garmin heart-rate range access through the local provider boundary.
- Added the Responses API `get_heart_rates` assistant tool backed by the local provider boundary.
- Added `examples/example03.py` to print raw Garmin heart-rate payloads for a date range.
- Added mocked provider tests for heart-rate range calls, date validation, and PII masking.

### Changed

- Updated the project specification to include the heart-rate provider method while preserving the current Garmin provider boundary.
- Updated the assistant system prompt to choose between activity data, heart-rate data, or both based on the user request.
- Updated documentation and environment examples for the nutrition diary SQLite database path.
- Updated nutrition specifications for single-current-plan PDF upload and overwrite semantics.

### Verified

- Frontend linting and production build pass for the nutrition diary UI.
- Added backend tests for nutrition diary persistence and API contracts.
- Added backend tests for nutrition-plan persistence, overwrite behaviour, and API contracts.
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
