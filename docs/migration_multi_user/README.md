# Migration Multi User

This document expands Milestone 7, "multi-user foundation", from
`docs/specs/personal_ai_garmin_assistant_spec.md`.

The goal is to evolve the current single-user local deployment into a
multi-user solution while preserving the current architecture:

* Next.js frontend
* Python assistant backend
* local Python Garmin provider boundary
* SQLite-backed local persistence for the initial nutrition implementation
* Docker Compose deployment on the local Intel NUC target
* no MCP server

The migration must keep user data isolated by default. Garmin credentials,
Garmin session material, training-derived context, nutrition diary entries,
nutrition plans, generated reports, and any future cache or conversation
storage must be scoped to the authenticated application user.

## Milestone 7 Scope

Milestone 7 should deliver:

* Local application user model with stable `user_id` and unique `username`
* Authentication flow for login, logout, and current-user resolution
* Backend enforcement of authenticated user identity on chat and nutrition
  endpoints
* User-scoped nutrition diary and nutrition-plan persistence
* User-scoped Garmin credential repository with encrypted at-rest storage
* User-scoped Garmin session storage
* Migration path from the current single-user nutrition storage to per-user
  records, if existing data must be preserved
* Tests for authentication, authorization, and cross-user isolation

## Proposed First Authentication Step

The first implementation can use Basic Authentication at the NGINX layer.
NGINX should sit in front of the frontend and assistant backend in Docker
Compose and should authenticate users before protected requests reach backend
services.

After authentication, NGINX should pass the authenticated username to the
backend through an internal header, for example:

```text
X-Authenticated-User: <username>
```

The backend should trust this header only when it is received through the
internal Docker network path controlled by NGINX. Direct public access to the
assistant backend must not be allowed to bypass NGINX authentication.

Basic Auth is acceptable as a local first step, but it has limitations:

* Browser logout is awkward because browsers cache Basic Auth credentials.
* User provisioning requires managing both NGINX credentials and application
  user records.
* Future OAuth/OIDC integration may replace this layer without changing the
  backend data ownership model.

## Backend User Resolution

The backend needs a single current-user resolver used by protected routes and
assistant orchestration entry points.

Recommended behavior:

1. Read the authenticated username from the trusted NGINX header.
2. Look up the corresponding local application user.
3. Use the stable internal `user_id` for all data access.
4. Reject requests when the username is missing, unknown, or not trusted.

The frontend may display the username, but request bodies must not contain an
authoritative `username` or `user_id` for ownership decisions.

## Local Users Table

Even when Basic Auth is handled by NGINX, the application should keep a local
`users` table so persisted data can reference a stable owner.

Suggested fields:

```text
id
username
display_name
created_at
updated_at
```

`username` should be unique and should map to the Basic Auth username. The
database primary key should be used as `user_id` in user-owned tables.

## User Provisioning

The first implementation needs a small provisioning workflow so NGINX users and
application users do not diverge.

Options:

* Add a local admin script that creates or updates the `.htpasswd` entry and
  ensures a matching row exists in the `users` table.
* Start with a manually managed `.htpasswd` file and a documented command to
  create the matching application user.
* Add a later admin-only UI only after the basic model is stable.

The first Docker Compose setup should document how the initial user is created.

## Existing Data Migration

The current nutrition storage is single-user. Before enabling multi-user
behavior, choose one of these paths:

* Migrate existing nutrition diary entries and current nutrition plan to a
  configured initial user.
* Start multi-user deployments with an empty database.

Preserving existing data requires a deterministic migration:

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

The script ensures the local application user exists, rebuilds the current
single-user nutrition tables with `user_id NOT NULL`, backfills existing diary
and current-plan rows to the initial user, and creates user-scoped indexes.
Run it after provisioning the initial Basic Auth user and before updating the
backend repositories to require `user_id`.

## Nutrition Schema Changes

Nutrition persistence must become user-scoped.

Expected changes:

* Add `user_id` to nutrition diary entries.
* Add `user_id` to nutrition plan records.
* Make diary uniqueness user-scoped, for example `(user_id, entry_date)`.
* Make the current nutrition plan user-scoped.
* Update repository methods so every read, write, update, and delete requires
  `user_id`.

The "current nutrition plan" must mean "current plan for this authenticated
user", not a global singleton.

## Garmin Credential Storage

Each application user needs separate Garmin credentials.

The backend should introduce a Garmin credential repository with these
responsibilities:

* Store one Garmin credential record per application user.
* Encrypt Garmin secrets at rest.
* Never return Garmin passwords, tokens, or session material to the frontend.
* Never log Garmin credentials or include them in model prompts.
* Allow a user to replace or delete their Garmin credentials without affecting
  other users.

For a local MVP, SQLite plus encrypted values is acceptable. A future deployment
may replace this repository with a secret manager without changing assistant
tool contracts.

The implemented local MVP stores one Garmin credential row per `user_id` in
SQLite. The Garmin password is encrypted with Fernet using
`GARMIN_CREDENTIAL_ENCRYPTION_KEY` or `GARMIN_CREDENTIAL_ENCRYPTION_KEY_FILE`.
Only safe status metadata is returned to frontend clients.

## Credential Encryption

Garmin passwords and sensitive session material must not be stored in
plaintext.

Recommended first step:

* Use a server-side encryption key supplied through an environment variable or
  mounted secret file.
* Do not store the encryption key in SQLite.
* Do not commit the encryption key.
* Consider `cryptography.Fernet` for the first local implementation because it
  is simple and well understood for symmetric encryption.

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

The provider construction path should resolve the current authenticated user,
load that user's Garmin credential record, and pass a user-specific session
storage path into `TrainingDataProvider`.

The implemented default root is `GARMIN_SESSION_STORAGE_ROOT`, which Docker
Compose sets to `/data/garmin-sessions`.

Assistant orchestration must not pass raw Garmin usernames, passwords, tokens,
or session paths through model tool arguments.

## Garmin Credential UI and API

The frontend will need a minimal account area for Garmin credential management.

Initial capabilities:

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

Preferred options:

* Do not expose `assistant_api` directly on the host in Docker Compose.
* Route frontend proxy calls and browser-facing backend calls through NGINX.
* Optionally require an internal shared header from NGINX to the backend.

If direct backend exposure is needed for local debugging, it should be
explicitly documented and disabled by default in multi-user mode.

## Frontend Changes

The frontend should stay thin.

Minimum changes:

* Show the authenticated username returned by the backend or forwarded through
  a safe current-user endpoint.
* Handle `401 Unauthorized` and `403 Forbidden` responses clearly.
* Add a Garmin credentials settings flow.

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

## Test Plan

Milestone 7 requires tests before implementation is considered complete.

Recommended tests:

* Unauthenticated protected requests are rejected.
* Unknown Basic Auth username is rejected by the backend resolver.
* User A cannot read User B's nutrition plan.
* User A cannot overwrite User B's nutrition diary entry.
* Diary uniqueness is scoped by `(user_id, entry_date)`.
* Current nutrition plan is scoped by `user_id`.
* Garmin credential lookup returns only the current user's credential record.
* Garmin session storage path differs for User A and User B.
* Garmin credentials are not returned by API responses.
* Logs and model tool outputs do not include Garmin secrets.

## Suggested Implementation Order

1. Add NGINX Basic Auth and authenticated username forwarding.
2. Add the local `users` table and provisioning script.
3. Add the backend current-user resolver.
4. Protect chat and nutrition endpoints with current-user resolution.
5. Add `user_id` to nutrition schema and migrate existing data.
6. Update nutrition repositories and services to require `user_id`.
7. Add encrypted Garmin credential storage per `user_id`.
8. Add user-scoped Garmin session storage and provider construction.
9. Add minimal frontend account/Garmin credential settings.
10. Add cross-user isolation tests and update documentation.

This order keeps the migration incremental while reducing the risk of
cross-user data leakage.
