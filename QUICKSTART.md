# Quickstart

This guide prepares a local runtime and development environment for Garmin AI Coach.

The project currently has a first working vertical slice: a Next.js frontend, a FastAPI assistant backend, Responses API integration, and a local Python Garmin data provider boundary. The commands below prepare the local development and Docker runtime.

## Prerequisites

Install these tools on the development machine:

- Conda or Miniforge
- Docker and Docker Compose
- Git

The target runtime for the full application is Docker Compose on Ubuntu Linux, intended for a local Intel NUC deployment.

## Create the Conda Environment

Create the project environment from the root of the repository:

```bash
conda env create -f environment.yml
```

Activate it:

```bash
conda activate garmin-ai-coach
```

Update an existing environment after dependency changes:

```bash
conda env update -f environment.yml --prune
```

The environment includes the initial Python runtime and development tools:

- Python 3.11
- `pytest`
- `black`
- `pylint`
- `garminconnect`
- FastAPI and related HTTP/testing dependencies
- the Python OpenAI SDK for Responses API integration through OCI Enterprise AI

## Runtime Configuration

Runtime configuration must come from environment variables or mounted secret files. Do not commit credentials or generated secret files.

Start from the sample environment file:

```bash
cp .env.example .env
```

Expected configuration values include:

```bash
GARMIN_USERNAME=
GARMIN_PASSWORD=
GARMIN_SESSION_STORAGE_PATH=.garmin/tokens
REDACT_PII=true
GENAI_API_KEY=
REGION=
OCI_MODEL_ID=openai.gpt-5.4
ASSISTANT_API_URL=
LOG_LEVEL=INFO
```

For local development, keep private values in an untracked `.env` file or in shell-specific secret management.

## Development Checks

Run Python checks from the activated Conda environment:

```bash
conda activate garmin-ai-coach
pytest
black .
pylint <python_package_or_module_paths>
```

Once Python services are scaffolded, prefer running checks from each service directory or through service-specific task commands if they are added.

## Docker Compose Runtime

The current Docker Compose runtime is:

- `frontend`, a Next.js web application
- `assistant_api`, a Python assistant backend that uses the local `TrainingDataProvider`

Create a local `.env` file first:

```bash
cp .env.example .env
```

Fill in private Garmin and OCI values, then start the stack:

```bash
docker compose up --build
```

The frontend is available at:

```text
http://localhost:3000
```

If port `3000` is already in use, set `FRONTEND_PORT=3001` in `.env` and open `http://localhost:3001` instead.

The assistant backend is exposed for local debugging at:

```text
http://localhost:8000
```

Inside Docker, the frontend calls the backend through:

```text
http://assistant_api:8000
```

The frontend should communicate only with the assistant backend. Assistant tools call the local Python Garmin training data provider inside backend code. A standalone Garmin data API container is not part of the current implementation.

## Specification First

Before changing implementation code, read:

```text
AGENTS.md
docs/specs/personal_ai_garmin_assistant_spec.md
```

Any architectural change must update the specification before or alongside the implementation.
