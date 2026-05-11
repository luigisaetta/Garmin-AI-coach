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

The initial architecture is composed of three main services:

```text
Browser
  |
  v
Next.js frontend
  |
  v
Assistant backend, Python
  |
  | local HTTP calls
  v
Garmin data API, Python
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

The assistant backend receives user questions, decides which Garmin data is needed, calls the local Garmin data API, and builds requests to OCI Enterprise AI using the Responses API.

### Garmin data API

The Garmin data API is the only service that knows Garmin Connect implementation details. It handles authentication, data retrieval, activity normalization, Garmin-specific errors, rate limits, and future caching.

## Guiding Principles

- Training data is sensitive: no credentials in the repository, no raw Garmin payloads in logs, and no full prompts containing private training details by default.
- The assistant backend never accesses Garmin Connect directly: it always goes through the dedicated local API.
- The first version does not introduce an MCP server.
- The deployment target is Docker Compose on Ubuntu Linux, intended to run locally on an Intel NUC.
- Python code must use Python 3.11 or newer, clear typing, small modules, and tests with `pytest`.
- Changes must stay small, verifiable, and consistent with the specification.

## Initial Milestones

1. Repository skeleton with Docker Compose, empty services, health endpoints, and a basic frontend page.
2. Garmin data API foundation with a client wrapper, activity endpoints, and normalized schemas.
3. Assistant backend foundation with a chat endpoint, Garmin API client, simple date range inference, and OCI Enterprise AI integration.
4. Frontend chat flow with input, responses, loading states, and error states.
5. Local deployment hardening with environment variables, health checks, and operating documentation.

## Project Status

The project is in the initial definition and skeleton phase. The technical direction is already defined in the specification, while implementation will proceed through small, testable steps.

Before changing application code, read:

```text
AGENTS.md
docs/specs/personal_ai_garmin_assistant_spec.md
```
