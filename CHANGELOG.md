# Changelog

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
