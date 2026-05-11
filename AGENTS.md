# AGENTS.md

## Project

Personal AI Assistant for Garmin training data.

The goal is to build a web based assistant that can answer interactive questions about the user’s Garmin Connect training data. The assistant should read training data on demand through a local Python provider API, reason over that data using OCI Enterprise AI, and return useful coaching style insights through a Next.js frontend.

This repository follows spec driven development. Before changing implementation code, read and follow the specification in:

`docs/specs/personal_ai_garmin_assistant_spec.md`

## Operating principles for coding agents

### 1. Keep every change scoped

Every code change must be limited to the stated objective.

Do not refactor unrelated files, rename unrelated modules, change public interfaces, reformat untouched files, or introduce new architectural patterns unless the task explicitly requires it.

When a change appears to require broader work, stop and document the reason before proceeding.

### 2. Write documentation in English

All repository documentation must be written in English.

This includes README files, specifications, architecture notes, setup guides, code comments that document behaviour, and any new documentation added by agents.

### 3. Work from the specification

Use the specification as the source of truth for architecture, responsibilities, boundaries, and development priorities.

When implementation and specification disagree, prefer the specification. If the specification is incomplete, update the specification first or propose the smallest explicit clarification needed.

### 4. Prefer simple, rigorous, extensible design

The initial architecture must stay simple while preserving clear boundaries:

* Python backend services
* Python Garmin Connect access layer
* Local Python API for training data access
* Next.js web frontend
* Docker Compose deployment
* Ubuntu Linux on an Intel NUC as the target runtime
* OCI Enterprise AI for generative AI calls
* Responses API from Python for model interaction
* No MCP server in the initial version

### 5. Backend language and runtime

Backend code must use Python 3.11 or newer.

Use clear typing, explicit interfaces, and small modules. Avoid hidden global state except for configuration that is loaded once at service startup.

Every Python file must start with a multiline string header using exactly these fields on separate lines:

```python
"""
Author: L. Saetta
Date Modified: YYYY-MM-DD
License: MIT
"""
```

Use the real last-modified date for `Date Modified`.

Do not place shared provider or domain-layer code under folders named `app` or `apps`. Reserve `app` or `apps` folders for user-visible applications, such as frontend applications or distinct runnable application surfaces.

### 6. Python quality requirements

All Python code must pass:

* `pytest`
* `black`
* `pylint`

Use the Conda environment named `garmin-ai-coach` for Python quality commands.

Run Python checks from an activated environment:

```text
conda activate garmin-ai-coach
pytest
black .
pylint <python_package_or_module_paths>
```

Tests must be written with `pytest`.

New behaviour must include tests. Bug fixes must include regression tests unless the task explicitly states otherwise.

### 7. Frontend requirements

The frontend is implemented with Next.js.

Keep frontend logic focused on interaction, display, and API calls. Do not duplicate Garmin Connect integration logic in the frontend.

### 8. Docker Compose deployment

The local deployment target is Docker Compose running on Ubuntu Linux on an Intel NUC.

The initial service model should include separate containers for:

* Web frontend
* Assistant backend

The current initial implementation keeps Garmin Connect access inside the
assistant backend container behind the Python `TrainingDataProvider` boundary.
A separate local Garmin data API container may be introduced later only after
the specification is updated for that architectural change.

Additional containers may be added only when justified by the specification or by an explicit task.

### 9. Garmin Connect access boundary

Garmin Connect integration must be encapsulated behind a Python API.

The assistant backend must not use Garmin Connect package calls directly in
orchestration code. It must call the local Python provider boundary exposed by
the Garmin data access layer.

This boundary keeps authentication, data retrieval, caching, rate limits, and vendor specific behaviour isolated from the assistant logic.

### 10. Generative AI integration

Use OCI Enterprise AI and OCI hosted models.

The initial target model is:

`openai.gpt-5.4`

Python code that interacts with the model must use the Responses API.

Do not introduce MCP servers in the initial implementation. Tool access to
training data is represented by ordinary local calls to the Python Garmin data
provider boundary.

### 11. Security and privacy

Training data is personal data. Treat it as sensitive by default.

Do not log raw activity payloads, credentials, tokens, or full model prompts containing private training details unless an explicit debugging task requires temporary redacted logging.

Configuration secrets must come from environment variables or secret files mounted by Docker Compose. Do not commit secrets.

### 12. Testing expectations

Tests should cover the behaviour being introduced or modified.

Prefer fast unit tests for business logic and HTTP boundary tests for service contracts. Use mocks or fixtures for Garmin Connect and OCI calls.

Do not require live Garmin Connect credentials or live OCI credentials for normal test execution.

### 13. Code style expectations

Use small functions, descriptive names, and explicit error handling.

Avoid broad exception handlers unless they rethrow typed domain errors or return intentional HTTP error responses.

Keep modules cohesive:

* Garmin client code belongs in the Garmin data service
* Assistant orchestration belongs in the assistant backend
* Presentation logic belongs in the frontend
* Shared contracts should be explicit and versioned when needed

### 14. Definition of done

A task is complete only when:

* The implementation matches the stated objective
* The specification remains accurate
* Relevant tests are added or updated
* `pytest` passes
* `black` passes
* `pylint` passes
* Docker Compose still reflects the intended service boundaries
* No unrelated changes are included
