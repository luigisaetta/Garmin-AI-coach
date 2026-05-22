# Quickstart

This guide prepares a local runtime and development environment for Garmin AI Coach.

The project currently has a local multi-user vertical slice: an NGINX Basic
Auth reverse proxy, a Next.js frontend, a FastAPI assistant backend, Responses
API integration, a local Python Garmin data provider boundary, user-scoped
Garmin credentials, and user-scoped nutrition persistence. The commands below
prepare the local development and Docker runtime.

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
GARMIN_CREDENTIAL_ENCRYPTION_KEY=
GARMIN_SESSION_STORAGE_ROOT=/data/garmin-sessions
REDACT_PII=true
GARMIN_COMPACT_ACTIVITY_PAYLOAD=false
GENAI_API_KEY=
REGION=
OCI_MODEL_ID=openai.gpt-5.4
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_DATABASE=garmin_ai_coach
MYSQL_USER=garmin_coach
MYSQL_PASSWORD=change-me
MYSQL_ROOT_PASSWORD=change-root-me
MYSQL_DATA_DIR=./data/mysql
ASSISTANT_API_URL=http://localhost:8000
NEXT_PUBLIC_ASSISTANT_API_URL=http://localhost:8000
FRONTEND_PORT=3000
LOG_LEVEL=INFO
```

For local development, keep private values in an untracked `.env` file or in shell-specific secret management.

Configuration reference:

| Variable | Required | Description |
| --- | --- | --- |
| `GARMIN_USERNAME` | Only for legacy local scripts | Garmin Connect account username used by the legacy single-user local training data provider path. |
| `GARMIN_PASSWORD` | Only for legacy local scripts | Garmin Connect account password used by the legacy single-user local training data provider path. |
| `GARMIN_SESSION_STORAGE_PATH` | Only for legacy local scripts | Local path for Garmin session token reuse in the legacy single-user provider path. |
| `GARMIN_CREDENTIAL_ENCRYPTION_KEY` | Yes for multi-user Garmin access | Fernet key used by the assistant backend to encrypt per-user Garmin credentials in MySQL. Generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. |
| `GARMIN_SESSION_STORAGE_ROOT` | Recommended | Root directory for user-scoped Garmin session tokens. Docker Compose defaults this to `/data/garmin-sessions`. |
| `REDACT_PII` | No | Redacts account, owner, profile, location, and coordinate-like fields before data can move toward assistant context. Keep this set to `true` unless explicitly debugging sanitized provider behaviour. |
| `GARMIN_COMPACT_ACTIVITY_PAYLOAD` | No | Reduces Garmin activity payloads to coaching-relevant summary, zone, split, and training-effect fields before they are sent to assistant tooling. Defaults to `false` for backward-compatible local debugging. |
| `GENAI_API_KEY` | Yes for model calls | OCI Enterprise AI OpenAI-compatible API key. |
| `REGION` | Yes for model calls | OCI region used to build the OpenAI-compatible inference endpoint, for example `eu-frankfurt-1`. |
| `OCI_MODEL_ID` | No | OCI hosted model identifier. Defaults to `openai.gpt-5.4`. |
| `MYSQL_HOST` | Yes | MySQL host. Docker Compose sets this to `mysql`. |
| `MYSQL_PORT` | Yes | MySQL port. Docker Compose defaults this to `3306`. |
| `MYSQL_DATABASE` | Yes | Application database name. Defaults to `garmin_ai_coach`. |
| `MYSQL_USER` | Yes | Application database username. |
| `MYSQL_PASSWORD` | Yes | Application database password. Keep this in `.env` or a secret file. |
| `MYSQL_ROOT_PASSWORD` | Yes | MySQL root password for the local container. Keep this in `.env` or a secret file. |
| `MYSQL_DATA_DIR` | Recommended | Host filesystem path mounted to `/var/lib/mysql`. Defaults to `./data/mysql`. |
| `ASSISTANT_API_URL` | Yes for local frontend development | URL the Next.js server uses to call the assistant backend when running outside Docker, usually `http://localhost:8000`. Docker Compose overrides it internally to `http://assistant_api:8000`. |
| `NEXT_PUBLIC_ASSISTANT_API_URL` | No | Optional fallback backend URL for non-Docker frontend experiments. Docker Compose sets it internally to `http://assistant_api:8000`. |
| `FRONTEND_PORT` | No | Host port for the frontend container. Defaults to `3000`. |
| `LOG_LEVEL` | No | Assistant backend logging level. Defaults to `INFO`. |

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

- `nginx`, the browser-facing reverse proxy with Basic Authentication
- `frontend`, a Next.js web application
- `assistant_api`, a Python assistant backend that uses the local `TrainingDataProvider`
- `mysql`, a MySQL Community Edition database with host-backed storage

Create a local `.env` file first:

```bash
cp .env.example .env
```

Fill in private OCI values and set `GARMIN_CREDENTIAL_ENCRYPTION_KEY`, then
create the first local user:

```bash
docker compose build assistant_api
./scripts/create_basic_auth_user.sh alice "Alice Runner"
```

The script updates `deployment/nginx/auth/.htpasswd` and ensures a matching
row exists in the MySQL `users` table. It creates one user per run.

MySQL data is stored on the host at `${MYSQL_DATA_DIR:-./data/mysql}` and is
mounted into the MySQL container at `/var/lib/mysql`. Preserve that host
directory to keep local users, Garmin credential metadata, diary entries, and
nutrition plans across container rebuilds.

The `.htpasswd` file is bind-mounted into the NGINX container and must be
readable by the container's NGINX worker. If NGINX returns HTTP 500 and logs
`Permission denied` for `/etc/nginx/auth/.htpasswd`, run:

```bash
chmod 644 deployment/nginx/auth/.htpasswd
docker compose restart nginx
```

After login, open `/account` to save, test, replace, or delete the Garmin
credentials for the authenticated application user. The backend stores the
Garmin password encrypted and keeps Garmin session tokens under
`GARMIN_SESSION_STORAGE_ROOT/<user_id>/`.

Then start the stack:

```bash
docker compose up --build
```

The frontend is available at:

```text
http://localhost:3000
```

If port `3000` is already in use, set `FRONTEND_PORT=3001` in `.env` and open `http://localhost:3001` instead.

The assistant backend is no longer exposed directly on the host in the
multi-user deployment. Inside Docker, the frontend calls the backend through:

```text
http://assistant_api:8000
```

The frontend should communicate only with the assistant backend. Assistant tools call the local Python Garmin training data provider inside backend code. A standalone Garmin data API container is not part of the current implementation.

To migrate an existing SQLite database into MySQL, start the database service
and run the migration command from the assistant container:

```bash
docker compose up -d mysql
docker compose run --rm \
  --volume /absolute/host/path/garmin_ai_coach.db:/migration/garmin_ai_coach.db:ro \
  assistant_api \
  python -m services.assistant_api.persistence.migrate_sqlite_to_mysql \
    --sqlite-path /migration/garmin_ai_coach.db \
    --initial-username alice
```

Omit `--initial-username` when the SQLite source already contains multi-user
`users` and `user_id` columns.

Basic Auth credentials are cached by browsers, so logout is limited in the
current local deployment. To switch users reliably during testing, use a fresh
private browser session or clear the browser's saved Basic Auth credentials.

## Specification First

Before changing implementation code, read:

```text
AGENTS.md
docs/specs/personal_ai_garmin_assistant_spec.md
```

Any architectural change must update the specification before or alongside the implementation.
