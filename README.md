# Garmin AI Coach

A personal assistant for turning Garmin Connect training data into useful conversations, clear explanations, and coaching-style insights.

The idea is simple: instead of looking at charts, numbers, and isolated activities, you can ask natural-language questions about your training history and receive contextual answers. For example:

- How has my training load changed over the last four weeks?
- Which runs had an unusually high heart rate for the pace?
- Summarize my latest cycling workout.
- Did I increase volume too quickly this week?
- What should I pay attention to before my next long run?

The project is designed to be local, controllable, and privacy-first. Garmin training data is personal data, so the initial architecture avoids risky shortcuts and keeps data access, AI reasoning, and the web interface clearly separated.

## Vision

Garmin AI Coach aims to become a web assistant that can read Garmin Connect data on demand, reason about training context, and return coaching-style answers: not just metrics, but practical interpretation.

The goal is not to replace a coach or generate complex training plans in the first version. The initial goal is to build a solid foundation for querying personal sports data naturally:

- understand trends in volume, intensity, and recovery
- compare weeks, activities, and training periods
- identify anomalies in workouts
- get quick summaries of recent sessions
- receive cautious, grounded guidance on signals worth monitoring

## Intended Architecture

This repository follows a spec-driven development approach. The reference specification is:

```text
docs/specs/personal_ai_garmin_assistant_spec.md
```

The initial architecture is composed of two runnable services and a local
Python Garmin data access layer:

```text
Browser
  |
  v
Next.js frontend
  |
  v
Assistant backend, Python
  |
  | local Python tool calls
  v
TrainingDataProvider, Python
  |
  | Garmin Connect access
  v
Garmin Connect

Assistant backend
  |
  | Responses API
  v
OCI Enterprise AI, model openai.gpt-5.4
```

### Frontend Next.js

The frontend provides the web experience: chat, loading states, errors, and response rendering. It does not access Garmin Connect directly and does not call the AI model directly.

### Assistant backend

The assistant backend receives user questions, decides which Garmin data is needed through model tool calling, calls the local Python training data provider, and builds requests to OCI Enterprise AI using the Responses API.

### Garmin data access layer

The Garmin data access layer is the only code path that knows Garmin Connect implementation details. In the current implementation it runs inside the assistant backend process behind `TrainingDataProvider`. It handles authentication, data retrieval, PII redaction, Garmin-specific errors, rate limits, and future caching.

The project does not currently expose a separate Garmin HTTP API container. That remains a future architectural option if the specification is updated first.

## Guiding Principles

- Training data is sensitive: no credentials in the repository, no raw Garmin payloads in logs, and no full prompts containing private training details by default.
- The assistant backend never accesses Garmin Connect directly: it always goes through the dedicated local API.
- The first version does not introduce an MCP server.
- The deployment target is Docker Compose on Ubuntu Linux, intended to run locally on an Intel NUC.
- Python code must use Python 3.11 or newer, clear typing, small modules, and tests with `pytest`.
- Changes must stay small, verifiable, and consistent with the specification.

## Initial Milestones

1. Repository skeleton with Docker Compose, empty services, health endpoints, and a basic frontend page.
2. Garmin data provider foundation with a client wrapper, provider methods, and normalized schemas.
3. Assistant backend foundation with a chat endpoint, local training provider tools, simple date range inference, and OCI Enterprise AI integration.
4. Frontend chat flow with input, responses, loading states, and error states.
5. Local deployment hardening with environment variables, health checks, and operating documentation.

## Project Status

The project now has a first working vertical slice:

- A Next.js chatbot frontend with light and black themes, sidebar status indicators, quick prompts, streaming response handling, and Markdown rendering.
- A FastAPI assistant backend exposing `/health`, `/chat`, and `/chat/stream`.
- Responses API integration for OCI Enterprise AI using model `openai.gpt-5.4`.
- Initial model tool calling with `list_activities`, backed by the local Python `TrainingDataProvider`.
- A Garmin Connect provider foundation with PII redaction and mocked tests.
- Backend logging for request flow, model calls, tool execution, and stream completion.
- Docker Compose and Dockerfiles for the current two-service runtime: `frontend` and `assistant_api`.

The current implementation is still an early local development version. It requires local environment configuration for OCI inference and Garmin credentials or session storage before live end-to-end coaching questions can use real Garmin data.

## Local Docker Runtime

Create a local `.env` from `.env.example`, fill in private values, then run:

```bash
docker compose up --build
```

The frontend is exposed at `http://localhost:3000`. The assistant backend is exposed at `http://localhost:8000` for local debugging and is reached by the frontend inside Docker through `http://assistant_api:8000`.

If one of those host ports is already in use, override `FRONTEND_PORT` or `ASSISTANT_API_PORT` in `.env`.

## Quickstart

See `QUICKSTART.md` for local runtime and development environment setup.

Before changing application code, read:

```text
AGENTS.md
docs/specs/personal_ai_garmin_assistant_spec.md
```
