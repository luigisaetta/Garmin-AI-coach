# Multi-User Foundation

This document records the implemented local multi-user foundation for Milestone
7 and the remaining follow-up work. It expands
`docs/specs/personal_ai_garmin_assistant_spec.md`.

The project has evolved from the original single-user local deployment into a
small multi-user solution while preserving the current architecture:

* Next.js frontend
* Python assistant backend
* local Python Garmin provider boundary
* SQLite-backed local persistence for the initial nutrition implementation
* Docker Compose deployment on the local Intel NUC target
* no MCP server

The multi-user foundation must keep user data isolated by default. Garmin credentials,
Garmin session material, training-derived context, nutrition diary entries,
nutrition plans, generated reports, and any future cache or conversation
storage must be scoped to the authenticated application user.

## Current Status

Implemented:

* Local application user model with stable `user_id` and unique `username`
* NGINX Basic Auth in front of the browser-facing application
* Authenticated username forwarding through `X-Authenticated-User`
* Backend current-user resolution for protected routes
* Backend enforcement of authenticated user identity on chat and nutrition
  endpoints
* User-scoped nutrition diary and nutrition-plan persistence
* User-scoped Garmin credential repository with encrypted at-rest storage
* User-scoped Garmin session storage
* Migration path from the current single-user nutrition storage to per-user
  records, if existing data must be preserved
* Tests for current-user rejection, repository isolation, credential secrecy,
  and user-scoped Garmin provider construction

Remaining:

* Frontend should preserve and display `401 Unauthorized` and `403 Forbidden`
  responses consistently across proxy routes.
* The UI should show the current authenticated application username, or expose a
  safe current-user endpoint that the frontend can call.
* Basic Auth logout limitations should be documented for operators and users.
* HTTP-level cross-user isolation tests should be expanded across protected
  endpoints, complementing the current repository and service tests.
* Legacy single-user Garmin environment variables should remain only as a
  documented compatibility path until they can be removed or isolated from the
  default multi-user runtime.

## Authentication

The current implementation uses Basic Authentication at the NGINX layer. NGINX
sits in front of the frontend and assistant backend in Docker Compose and
authenticates users before protected requests reach backend services.

After authentication, NGINX passes the authenticated username through an
internal header:

```text
X-Authenticated-User: <username>
```

The backend trusts this header only when it is received through the
internal Docker network path controlled by NGINX. Direct public access to the
assistant backend is not exposed in the default multi-user Docker Compose
runtime.

Basic Auth is acceptable as a local first step, but it has limitations:

* Browser logout is awkward because browsers cache Basic Auth credentials.
* User provisioning requires managing both NGINX credentials and application
  user records.
* Future OAuth/OIDC integration may replace this layer without changing the
  backend data ownership model.

## Backend User Resolution

The backend has a single current-user resolver used by protected routes and
assistant orchestration entry points.

Current behavior:

1. Read the authenticated username from the trusted NGINX header.
2. Look up the corresponding local application user.
3. Use the stable internal `user_id` for all data access.
4. Reject requests when the username is missing, unknown, or not trusted.

The frontend may display the username, but request bodies must not contain an
authoritative `username` or `user_id` for ownership decisions.

## Local Users Table

Even though Basic Auth is handled by NGINX, the application keeps a local
`users` table so persisted data can reference a stable owner.

Current fields:

```text
id
username
display_name
is_active
created_at
updated_at
```

`username` is unique and maps to the Basic Auth username. The database primary
key is used as `user_id` in user-owned tables.

## User Provisioning

The implemented provisioning workflow is
`scripts/create_basic_auth_user.sh USERNAME [DISPLAY_NAME]`. The script creates
or updates the `.htpasswd` entry and ensures a matching row exists in the
SQLite `users` table. It can be run through Docker Compose for the default
container database path or locally with `USE_COMPOSE=0`.

A later admin-only UI can be added after the local model is stable.

## Existing Data Migration

Existing single-user nutrition storage can be migrated before enabling
multi-user behavior, or a deployment can start with an empty database.

Preserving existing data uses this deterministic migration:

1. Create or select the initial application user.
2. Add `user_id` columns to user-owned tables.
3. Backfill existing rows with the initial user's `user_id`.
4. Add constraints and indexes after backfill.

The safer schema target is to enforce user ownership in the database, not only
in Python service code.

The local migration script for this step is:

```bash
python -m services.assistant_api.identity.migrate_user_ids \
  --db-path /data/garmin_ai_coach.db \
  --initial-username alice \
  --display-name "Alice Runner"
```

Run the migration with the project runtime, Python 3.11 or newer. If the
database path is the Docker path `/data/garmin_ai_coach.db`, run the command
inside the assistant API container:

```bash
docker compose run --rm assistant_api \
  python -m services.assistant_api.identity.migrate_user_ids \
    --db-path /data/garmin_ai_coach.db \
    --initial-username alice \
    --display-name "Alice Runner"
```

If running the migration directly on the host, activate the Conda environment
and pass the host-visible SQLite path instead of the container path:

```bash
conda activate garmin-ai-coach
python --version
python -m services.assistant_api.identity.migrate_user_ids \
  --db-path /path/on/host/garmin_ai_coach.db \
  --initial-username alice \
  --display-name "Alice Runner"
```

The script ensures the local application user exists, rebuilds legacy
single-user nutrition tables with `user_id NOT NULL`, backfills existing diary
and current-plan rows to the initial user, and creates user-scoped indexes.

## Nutrition Schema Changes

Nutrition persistence is user-scoped.

Implemented schema behavior:

* `user_id` is present on nutrition diary entries.
* `user_id` is present on nutrition plan records.
* Diary uniqueness is scoped by `(user_id, entry_date)`.
* The current nutrition plan is scoped by `user_id`.
* Repository methods require
  `user_id`.

The "current nutrition plan" must mean "current plan for this authenticated
user", not a global singleton.

## Garmin Credential Storage

Each application user needs separate Garmin credentials.

The backend includes a Garmin credential repository with these
responsibilities:

* Store one Garmin credential record per application user.
* Encrypt Garmin secrets at rest.
* Never return Garmin passwords, tokens, or session material to the frontend.
* Never log Garmin credentials or include them in model prompts.
* Allow a user to replace or delete their Garmin credentials without affecting
  other users.

The implemented local MVP stores one Garmin credential row per `user_id` in
SQLite. The Garmin password is encrypted with Fernet using
`GARMIN_CREDENTIAL_ENCRYPTION_KEY` or `GARMIN_CREDENTIAL_ENCRYPTION_KEY_FILE`.
Only safe status metadata is returned to frontend clients.

A future deployment may replace this repository with a secret manager without
changing assistant tool contracts.

## Credential Encryption

Garmin passwords and sensitive session material must not be stored in
plaintext.

Implemented first step:

* Use a server-side encryption key supplied through an environment variable or
  mounted secret file.
* Do not store the encryption key in SQLite.
* Do not commit the encryption key.
* Use `cryptography.Fernet` for symmetric encryption.

Example configuration name:

```text
GARMIN_CREDENTIAL_ENCRYPTION_KEY
```

Key rotation can be added later, but the initial implementation should at least
make replacement possible with an explicit maintenance procedure.

## Garmin Session Storage Per User

Reusable Garmin session tokens or session files must be partitioned by
`user_id`.

Example layout:

```text
/data/garmin-sessions/{user_id}/
```

The provider construction path resolves the current authenticated user, loads
that user's Garmin credential record, and passes a user-specific session
storage path into `TrainingDataProvider`.

The implemented default root is `GARMIN_SESSION_STORAGE_ROOT`, which Docker
Compose sets to `/data/garmin-sessions`.

Assistant orchestration must not pass raw Garmin usernames, passwords, tokens,
or session paths through model tool arguments.

## Garmin Credential UI and API

The frontend includes a minimal account area for Garmin credential management.

Implemented capabilities:

* Show whether Garmin credentials are configured for the current user.
* Save or replace Garmin credentials.
* Test Garmin login with the stored credentials.
* Delete stored Garmin credentials.

The first UI surface is `/account`, backed by ordinary Next.js API proxy routes
under `/api/account/garmin-credentials`.

API responses must never include the stored Garmin password or decrypted secret
values.

## Protected Backend Access

If NGINX handles Basic Auth, direct access to `assistant_api` must not bypass
authentication.

Current default:

* Do not expose `assistant_api` directly on the host in Docker Compose.
* Route frontend proxy calls and browser-facing backend calls through NGINX.

If direct backend exposure is needed for local debugging, it should be
explicitly documented and disabled by default in multi-user mode.

## Frontend Changes

The frontend stays thin: it forwards authenticated requests to backend services
and does not make Garmin Connect or model calls directly.

Implemented:

* Add a Garmin credentials settings flow.
* Forward `X-Authenticated-User` from NGINX to backend proxy calls.

Remaining:

* Show the authenticated username returned by the backend or forwarded through
  a safe current-user endpoint.
* Handle `401 Unauthorized` and `403 Forbidden` responses clearly.

With Basic Auth, logout may need documentation rather than a polished UI
because browser credential caching makes clean logout unreliable.

## Backend Query Rules

Every user-owned repository method should require `user_id`.

Rules:

* Do not accept frontend-supplied `user_id` as an ownership boundary.
* Do not filter by display name.
* Use backend-resolved `user_id` for every query.
* Add database constraints and indexes that include `user_id`.
* Return safe not-found or forbidden responses without revealing another user's
  resource existence.

## Model and Prompt Privacy

The model should receive only the data needed for the authenticated user's
request.

Do not include:

* Application username unless there is a specific user-facing reason.
* Garmin username or email.
* Garmin password, tokens, session paths, or credential IDs.
* Cross-user metadata.

The assistant tools should continue to operate on user-scoped backend calls.
The LLM should never select or pass user identity as a tool argument.

## Test Coverage

Current tests cover the most important storage and backend ownership contracts.

Implemented:

* Unauthenticated protected requests are rejected.
* Unknown Basic Auth username is rejected by the backend resolver.
* User-scoped nutrition diary persistence is isolated by `user_id`.
* User-scoped current nutrition plans are isolated by `user_id`.
* Diary uniqueness is scoped by `(user_id, entry_date)`.
* Current nutrition plan is scoped by `user_id`.
* Garmin credential lookup returns only the current user's credential record.
* Garmin session storage path differs for User A and User B.
* Garmin credentials are not returned by API responses.

Remaining useful tests:

* HTTP-level User A/User B isolation tests for nutrition plan and diary routes.
* HTTP-level 401/403 propagation tests for Next.js proxy routes.
* Log and model tool output assertions that Garmin secrets are not emitted.

## Implementation Order

Completed order:

1. Added NGINX Basic Auth and authenticated username forwarding.
2. Added the local `users` table and provisioning script.
3. Added the backend current-user resolver.
4. Protected chat and nutrition endpoints with current-user resolution.
5. Added `user_id` to nutrition schema and migration support for existing data.
6. Updated nutrition repositories and services to require `user_id`.
7. Added encrypted Garmin credential storage per `user_id`.
8. Added user-scoped Garmin session storage and provider construction.
9. Added minimal frontend account/Garmin credential settings.
10. Added repository, service, and backend tests for the implemented ownership
    boundaries.
