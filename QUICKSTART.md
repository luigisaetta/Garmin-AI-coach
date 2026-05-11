# Quickstart

This guide prepares a local runtime and development environment for Garmin AI Coach.

The project is currently in the specification and skeleton phase. The commands below establish the shared environment that future backend services, tests, and quality checks should use.

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
GARMIN_API_URL=
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

The intended service model is:

- `frontend`, a Next.js web application
- `assistant_api`, a Python assistant backend
- `garmin_api`, a Python Garmin data API

When `docker-compose.yml` is added, the expected local run command will be:

```bash
docker compose up --build
```

The Garmin data API should remain internal to Docker Compose by default. The frontend should communicate with the assistant backend, and the assistant backend should communicate with the Garmin data API over local HTTP.

## Specification First

Before changing implementation code, read:

```text
AGENTS.md
docs/specs/personal_ai_garmin_assistant_spec.md
```

Any architectural change must update the specification before or alongside the implementation.
