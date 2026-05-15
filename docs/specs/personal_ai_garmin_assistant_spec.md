# Personal AI Garmin Assistant Specification

## 1. Purpose

This document defines the initial architecture and implementation constraints
for a personal AI assistant that answers questions about Garmin Connect training
data and, in a later product extension, helps track nutrition-plan adherence.

The project should start with a simple but rigorous architecture that can run
locally on an Intel NUC with Ubuntu Linux, while remaining extensible for
future features such as richer analytics, caching, additional data sources,
nutrition-plan adherence analysis, and deeper coaching workflows.

This document is referenced by `AGENTS.md` and should be treated as the source of truth for implementation decisions.

## 2. Product objective

Build a web based personal AI assistant that can:

* Access the user’s Garmin Connect training data
* Read training data on demand through a local API
* Use generative AI to answer interactive questions about workouts and training history
* Present answers through a Next.js web interface
* Run locally through Docker Compose on Ubuntu Linux
* Support multiple authenticated local users, keeping each user's Garmin
  credentials, training-derived context, nutrition diary entries, and nutrition
  plans isolated from other users

A later nutrition extension should allow the user to:

* Record a daily food diary with meals, free-text descriptions, and notes
* Upload the current nutrition plan received from a nutritionist as PDF or Markdown
* Extract and store a local, structured representation of the current nutrition plan
* Compare diary entries with the current plan week by week
* Surface adherence gaps, recurring patterns, and points to discuss with the nutritionist

The nutrition extension is an adherence and reflection companion. It must not
replace a nutritionist, prescribe a diet, diagnose medical conditions, or make
clinical recommendations.

Example user questions:

* What was my training load trend over the last four weeks?
* Which runs had unusually high heart rate for the pace?
* Summarise my last cycling workout.
* Compare this week with the previous week.
* Did I increase volume too quickly recently?
* What should I pay attention to before my next long run?

## 3. Non goals for the initial version

The initial version must not include:

* An MCP server
* Direct Garmin Connect access from the assistant backend
* Direct Garmin Connect access from the frontend
* Cloud deployment automation
* Complex distributed infrastructure
* Live writeback to Garmin Connect
* Long term coaching plan generation unless explicitly added later
* Autonomous diet prescription or medical nutrition advice
* Replacing the judgement of a qualified nutrition professional

## 4. Target runtime

The deployment target is:

* Intel NUC
* Ubuntu Linux
* Docker Compose
* Python 3.11 or newer for backend services
* Node.js runtime suitable for the selected Next.js version

## 5. High level architecture

The initial system is composed of two runnable services plus a local Python
Garmin access layer. In the current initial implementation, the Garmin access
layer runs inside the assistant backend process behind `TrainingDataProvider`.
A separate Garmin HTTP service is not part of the current implementation.

```text
Browser
  |
  v
Next.js frontend
  |
  | authenticated requests
  v
Assistant backend, Python
  |
  | resolves current user
  v
User-scoped local Python tool calls
  v
TrainingDataProvider, Python
  |
  | Garmin Connect access with user-scoped credentials/session
  v
Garmin Connect

Assistant backend
  |
  | Responses API
  v
OCI Enterprise AI, model openai.gpt-5.4
```

The nutrition extension keeps the same high-level service boundary:

```text
Browser
  |
  v
Next.js frontend, nutrition section
  |
  v
Assistant backend, Python
  |
  | local Python service calls
  v
Nutrition diary and plan services
  |
  v
Local persistence

Assistant backend
  |
  | Responses API
  v
OCI Enterprise AI, model openai.gpt-5.4
```

The nutrition extension must not introduce an MCP server. The first persistence
implementation uses SQLite inside the assistant backend service, with the
database path configured by `NUTRITION_DB_PATH`.

The current local architecture includes a multi-user foundation. Authenticated
requests carry a backend-validated user identity. Backend services use that
identity to scope Garmin credential lookup, Garmin session storage, nutrition
diary entries, nutrition plans, generated reports, and any future conversation
or cache records.

## 6. Service responsibilities

### 6.1 Next.js frontend

The frontend is responsible for:

* Rendering login, logout, and authenticated session state when the selected
  authentication mechanism supports it
* Rendering the assistant chat interface
* Rendering a nutrition section when the nutrition extension is implemented
* Sending user messages to the assistant backend
* Sending nutrition diary entries, plan uploads, and report requests to backend endpoints
* Displaying responses, errors, loading states, and basic activity summaries
* Displaying nutrition adherence summaries without performing backend analysis in the browser
* Displaying assistant-reported token usage counters for the current chat
* Keeping browser side logic simple

The frontend must not:

* Call Garmin Connect directly
* Store Garmin credentials
* Trust a user-selected username in request bodies as an authorization boundary
* Perform training analytics that belong in backend services
* Perform nutrition-plan parsing, adherence analysis, or model calls that belong in backend services
* Call OCI Enterprise AI directly

### 6.2 Assistant backend

The assistant backend is responsible for:

* Authenticating users and resolving the current user for every protected
  request
* Receiving user questions from the frontend
* Deciding what Garmin data is needed
* Exposing model tools that call the local Python training data provider
* Exposing nutrition-plan and diary workflows when the nutrition extension is implemented
* Constructing model requests using the Responses API
* Calling OCI Enterprise AI with model `openai.gpt-5.4`
* Returning grounded answers to the frontend
* Returning nutrition adherence reports with clear limits and source descriptions
* Returning Responses API token usage summaries when available
* Handling assistant level errors and response shaping

The assistant backend must not:

* Store Garmin credentials in plaintext
* Trust frontend-supplied usernames when selecting data or credentials
* Let the frontend access Garmin Connect or training provider code directly
* Introduce MCP server dependencies in the initial version
* Give prescriptive medical or nutrition advice in place of a qualified professional

### 6.3 Garmin data access layer

The Garmin data access layer is responsible for:

* Authenticating with Garmin Connect using credentials associated with the
  current authenticated application user
* Encapsulating Garmin Connect access in Python through `TrainingDataProvider`
* Normalising Garmin data into stable internal response schemas
* Handling Garmin specific errors, rate limits, and retries
* Optionally caching Garmin responses in a future iteration

The assistant backend may use `TrainingDataProvider` through a narrow local
adapter when executing model-selected tools. The frontend must never import or
call Garmin Connect code directly.

In multi-user mode, provider construction must be mediated by a backend
credential/session boundary. Assistant orchestration code must ask for training
data for the current authenticated user; it must not pass raw Garmin usernames,
passwords, or tokens through model tool arguments or prompts.

### 6.4 Nutrition plan and diary services

The nutrition extension should be implemented behind explicit Python service
boundaries. It should not be mixed into Garmin provider code.

Nutrition services are responsible for:

* Storing food diary entries entered by the authenticated user
* Storing uploaded nutrition-plan documents and extracted text for the
  authenticated user
* Normalising the current plan into a structured local representation
* Comparing diary entries against the current plan by week
* Producing adherence summaries, deviations, uncertainties, and points of attention
* Producing questions or discussion points to bring back to the nutritionist

Nutrition services must not:

* Claim to replace the nutritionist
* Diagnose medical conditions
* Prescribe calorie targets, macro targets, supplements, or diet changes unless they are explicitly present in the uploaded plan
* Treat model-generated analysis as a clinical decision
* Log raw diary entries, uploaded documents, or full nutrition prompts by default

The initial nutrition implementation uses simple local SQLite persistence. The
SQLite database is local to the assistant backend service and must be stored on
a Docker volume in container deployments so diary entries and the current
nutrition plan survive stop and restart. A separate database container is not
part of the initial nutrition MVP.

The initial nutrition-plan implementation stores one current plan. Uploading a
new PDF replaces the previous current plan. The backend extracts all available
text from the uploaded PDF and stores the extracted text plus metadata in
SQLite. The original PDF file is not retained in the MVP.

In multi-user mode, the "current plan" is per user. Uploading a nutrition plan
must replace only the authenticated user's current plan. Nutrition endpoints
must derive the user from the authenticated session or token and must not accept
a free-form username in the request body as the authority for data ownership.

### 6.5 Identity, accounts, and user-scoped data

Multi-user support introduces an application user identity independent of
Garmin Connect account identifiers.

The first multi-user implementation should use a simple local identity model
inside the assistant backend:

* A stable internal `user_id` is the ownership key for persisted data.
* A unique `username` identifies the local application account and may be used
  for login and display.
* Authentication state is established by the backend or a trusted local reverse
  proxy and carried to the backend through a backend-validated mechanism.
* Passwords, if local password authentication is used, must be stored only as
  modern salted password hashes.
* All protected backend endpoints must resolve the current user before reading
  or writing data.

The frontend may display the authenticated username, but data ownership must be
enforced by backend `user_id`, not by client-supplied fields.

Initial multi-user scope should remain local and small. OAuth/OIDC, user
invitation workflows, password reset email, roles beyond ordinary users, and
cloud identity-provider integration are future enhancements unless explicitly
requested.

### 6.6 Garmin credentials per user

Garmin credentials and reusable Garmin session material must be scoped per
authenticated application user.

The first implementation should introduce a backend credential service or
repository with these responsibilities:

* Store one Garmin credential record per application user, unless multiple
  Garmin accounts per user are explicitly added later.
* Encrypt Garmin credentials at rest using a server-side key supplied through an
  environment variable or mounted secret file.
* Never expose Garmin passwords, tokens, or session files to the frontend.
* Never include Garmin credentials or session tokens in model prompts, tool
  arguments, logs, or frontend responses.
* Keep Garmin session storage partitioned by stable `user_id`, for example
  under a user-specific directory in the backend data volume.
* Allow credentials to be replaced or removed for one user without affecting
  other users.

If encrypted local SQLite storage is used for the first multi-user iteration,
the encryption key must not be stored in SQLite or committed to the repository.
A future deployment may replace the local credential repository with a dedicated
secret manager without changing assistant tool contracts.

The first local implementation uses SQLite for one Garmin credential record per
application user and encrypts the Garmin password with Fernet. The Fernet key is
provided through `GARMIN_CREDENTIAL_ENCRYPTION_KEY` or a mounted secret file
referenced by `GARMIN_CREDENTIAL_ENCRYPTION_KEY_FILE`. User-scoped Garmin
session tokens are stored under `GARMIN_SESSION_STORAGE_ROOT/<user_id>/`.

## 7. Initial container model

Docker Compose should define at least these services:

* `frontend`, Next.js application
* `assistant_api`, Python assistant backend

Suggested internal ports:

* `frontend`, exposed to the host
* `assistant_api`, internal plus optionally exposed for local debugging

Service communication should use Docker Compose service names.

Example logical flow:

```text
frontend -> http://assistant_api:<port>
assistant_api -> local Python TrainingDataProvider
assistant_api -> OCI Enterprise AI endpoint
```

The Garmin access layer is intentionally not represented as a separate
container yet. Adding a standalone Garmin data API container would be an
architectural change and must update this specification before implementation.

The nutrition extension should initially run inside the assistant backend
service behind local Python service boundaries. Adding a separate nutrition API
container, document-processing worker, or database container is an architectural
change and must update this specification before implementation.

For the nutrition diary MVP, Docker Compose should mount a named volume at
`/data` in the assistant backend container and default `NUTRITION_DB_PATH` to
`/data/garmin_ai_coach.db`.

## 8. Backend implementation approach

Python backend services should use:

* Python 3.11 or newer
* Explicit configuration loaded from environment variables
* Typed request and response models
* Structured application modules
* Testable service classes or functions
* Clear HTTP boundaries

The exact Python web framework may be selected during implementation. FastAPI is a suitable default because it provides typed request models, OpenAPI documentation, and strong testing support.

### 8.1 Training data provider

Garmin Connect access should be encapsulated behind a provider interface. The
initial provider is `TrainingDataProvider`, backed by the open source Python
`garminconnect` library.

The initial provider interface should expose these operations:

```python
class TrainingDataProvider:
    def list_activities(...):
        ...

    def get_activity(...):
        ...

    def get_activity_streams(...):
        ...

    def get_heart_rates(...):
        ...

    def get_daily_metrics(...):
        ...
```

Provider responsibilities:

* Own all direct calls to the `garminconnect` library
* Authenticate with Garmin Connect using credentials resolved for the current
  authenticated application user
* Reuse Garmin session tokens from a user-scoped session storage path when
  configured, and save refreshed tokens there after credential login
* Convert Garmin Connect responses into stable internal models before they are returned to assistant tools
* Mask noisy or personal account and location fields that are not useful for coaching analysis, such as `userRoles`, owner metadata, profile image URLs, coordinates, and location names, before data can be passed toward the assistant or LLM context when `REDACT_PII` is enabled
* Hide Garmin-specific response shapes, exceptions, retries, rate limits, and session handling from the rest of the application
* Provide a mockable boundary for unit tests

The assistant backend must access Garmin data only through assistant tools and
the local provider adapter. Tool calls are selected by the LLM through the
Responses API; the frontend does not select or call tools directly.

### 8.2 Nutrition domain services

The nutrition extension should use cohesive Python modules with explicit
interfaces. The initial domain model should be intentionally small:

```python
class NutritionDiaryRepository:
    def create_entry(...):
        ...

    def list_entries(...):
        ...


class NutritionPlanRepository:
    def save_plan_document(user_id, ...):
        ...

    def get_current_plan(user_id, ...):
        ...


class NutritionAnalysisService:
    def analyze_weekly_adherence(...):
        ...
```

The first nutrition analysis implementation is a linear Python subagent graph
that accepts the current authenticated `user_id`, `begin_date`, and `end_date`
as input and runs these steps in order:

1. `ReadNutritionPlanStep` reads the current uploaded nutrition plan from local
   persistence.
2. `ReadDiaryEntriesStep` reads food diary entries day by day for the inclusive
   period, aggregates them, and records missing diary dates.
3. `ReadTrainingActivitiesStep` reads Garmin workouts for the same period
   through the local training data provider boundary and summarizes activity
   type, duration, timing, intensity, and combined workout days.
4. `GenerateNutritionReportStep` calls the Responses API with a dedicated
   nutrition analysis prompt and returns a detailed adherence report.

Each step should be implemented as a dedicated Python class and should log start
and completion messages without logging raw diary text, full plan text, raw
activity payloads, or complete model prompts.

The nutrition analysis subagent may comment on apparent macronutrient gaps and
calorie-volume adequacy only relative to the explicit uploaded plan, the diary
text, and the observed training load. When the plan or diary does not contain
enough detail, the report must state the uncertainty instead of inventing
calorie or macronutrient values. The report should include adherence findings,
points of attention, improvements, and questions to discuss with the
nutritionist.

Initial diary entries should support:

* Date
* Training context for the day
* Free-text meal description for the day
* Optional notes
* Optional tags

The first implemented API may store one entry per calendar day with the fields
`entry_date`, `training_type`, `meals_text`, and `notes`. More structured meal
types can be added later without moving Garmin or assistant orchestration code
into the nutrition service.

In multi-user mode, nutrition persistence must include a `user_id` ownership
column on user-owned records. Repository methods should require `user_id`
explicitly and should filter every read, update, and delete by that value.

The system should not require automatic calorie or macronutrient estimation in
the first nutrition implementation. Such estimation may be added later only
with explicit accuracy limits and tests.

Nutrition-plan upload should support PDF first for the MVP. PDF support must
handle extraction failures gracefully. The MVP stores only extracted text and
metadata; preserving the original uploaded document requires a future explicit
storage policy update.

## 9. Suggested repository structure

```text
.
├── AGENTS.md
├── docs
│   └── specs
│       └── personal_ai_garmin_assistant_spec.md
├── docker-compose.yml
├── services
│   ├── assistant_api
│   │   ├── api
│   │   ├── orchestration
│   │   ├── tests
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   └── garmin_api
│       ├── training_data_provider.py
│       └── tests
└── frontend
    ├── app
    ├── package.json
    └── Dockerfile
```

This structure is a recommendation for the initial implementation. Changes are allowed only when they improve clarity while preserving the architecture and service boundaries.

Shared provider and domain-layer modules must not be placed under folders named `app` or `apps`. Those names should be reserved for user-visible applications or distinct runnable application surfaces.

## 10. Assistant tool contract, initial draft

The frontend-facing API must not expose Garmin-specific endpoints. Garmin data
access is represented by Responses API function tools executed inside the
assistant backend.

### 10.1 `list_activities` tool

Tool arguments:

```json
{
  "begin_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "activity_type": "optional"
}
```

The tool returns a normalised list of activities. Each activity should include,
when available:

* Activity identifier
* Start time
* Activity type
* Duration
* Distance
* Average heart rate
* Maximum heart rate
* Average pace or speed
* Elevation gain
* Training effect fields, if available
* Link or reference to the source activity, if safe to expose locally

### 10.2 `get_heart_rates` tool

Tool arguments:

```json
{
  "begin_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD"
}
```

The tool returns Garmin daily heart-rate payloads keyed by ISO date for the
inclusive date range. The assistant should use this tool for resting heart
rate, daily heart-rate patterns, heart-rate trends, and heart-rate questions
that are not tied to one specific workout. When a question needs both workout
context and daily heart-rate context, the assistant may call both
`list_activities` and `get_heart_rates`.

### 10.3 Nutrition analysis tools

When the nutrition extension is implemented, nutrition analysis should be
available through explicit backend services and, where useful, Responses API
tools executed inside the assistant backend. The frontend should not call model
tools directly.

Initial nutrition tool capabilities may include:

* `get_current_nutrition_plan`
* `list_food_diary_entries`
* `analyze_nutrition_adherence_period`

The `analyze_nutrition_adherence_period` tool should accept `begin_date` and
`end_date` in `YYYY-MM-DD` format and may be used for any inclusive requested
period, including but not limited to one calendar week. The tool runs the
nutrition analysis subagent inside the assistant backend and returns the
generated report plus source metadata. The assistant frontend should continue to
access this capability only through the chat endpoint.

The analysis output should include:

* Week start and end dates
* Diary coverage and missing days or meals
* Observed adherence to explicit plan elements
* Deviations from the current plan
* Recurring patterns
* Uncertainties caused by incomplete diary entries or unclear plan text
* Points to discuss with the nutritionist

The analysis output must avoid presenting model inferences as clinical facts.

## 11. Assistant backend contract, initial draft

### 11.1 Health check

```text
GET /health
```

Returns service status.

### 11.2 Chat request

```text
POST /chat
```

Request body:

```json
{
  "message": "Summarise my training this week",
  "conversation_id": "optional stable id",
  "messages": [
    {
      "role": "user",
      "content": "What did I do yesterday?"
    },
    {
      "role": "assistant",
      "content": "You completed a run."
    }
  ]
}
```

Response body:

```json
{
  "answer": "...",
  "conversation_id": "...",
  "data_sources": [
    {
      "type": "garmin_activity_range",
      "description": "Activities from 2026-05-04 to 2026-05-10"
    }
  ]
}
```

The assistant should include enough source description to make the answer understandable, without exposing raw private payloads unnecessarily.

### 11.3 Streaming chat request

```text
POST /chat/stream
```

The request body is the same as `POST /chat`.

The response is a `text/event-stream` stream of server-sent events. Initial event types are:

* `message_delta`, containing partial assistant text in `delta`
* `message_done`, containing the completed `answer`, `conversation_id`, and safe `data_sources`
* `error`, reserved for recoverable assistant level failures

The frontend should treat `conversation_id` as stable across all events for the same assistant turn.

### 11.4 Nutrition API

The nutrition extension may expose ordinary backend HTTP endpoints in addition
to chat workflows. The nutrition MVP exposes:

```text
POST /nutrition/diary-entries
PUT /nutrition/diary-entries/{entry_date}
GET /nutrition/diary-entries/{entry_date}
POST /nutrition/plan
GET /nutrition/plan/current
```

Future endpoint candidates include:

```text
GET /nutrition/diary-entries?begin_date=YYYY-MM-DD&end_date=YYYY-MM-DD
POST /nutrition/reports/weekly
```

Nutrition endpoints must use typed request and response schemas, validate date
ranges, and return safe errors. File uploads must validate content type and
size. Normal tests must not require live OCI access.

In multi-user mode, all nutrition endpoints are protected endpoints. The
backend must derive the current user from authentication state and apply that
user to every nutrition repository operation. Request bodies must not contain
an authoritative `username` or `user_id` for ownership decisions.

## 12. Generative AI integration

The assistant backend must use OCI Enterprise AI.

The target model is:

```text
openai.gpt-5.4
```

Python integration must use the Responses API.

The assistant backend should structure model calls so that:

* The user question is preserved clearly
* Retrieved Garmin data is included only as needed
* Nutrition diary and plan data is included only as needed for the requested analysis
* Large raw payloads are summarised or reduced before being sent to the model
* Private data is handled carefully
* Model errors produce useful application errors
* Nutrition responses stay within adherence analysis and do not become medical prescriptions

## 13. Data access strategy

The assistant should retrieve Garmin data on demand.

Initial retrieval can be simple:

* Infer a likely date range from the user message
* Fetch recent activities when no date range is obvious
* Fetch activity details only when needed
* Pass compact normalised data into the model request

Future iterations may add:

* Local caching
* Precomputed training summaries
* Local nutrition-plan and food-diary persistence
* Embeddings or searchable summaries
* User controlled data retention
* Background sync jobs

These are not required in the initial version.

For the nutrition extension, the assistant should retrieve only the current
plan and diary entries for the requested analysis window. Weekly reports should
prefer compact structured summaries over raw full-document prompts.

## 14. Configuration

Configuration must come from environment variables or mounted secret files.

Likely configuration values:

* Local authentication/session secret
* Password hashing configuration, if local password authentication is used
* Garmin credential encryption key or mounted secret reference
* Garmin session storage root path, if used
* PII redaction flag, `REDACT_PII`, default enabled
* OCI region, `REGION`
* Generative AI API key, `GENAI_API_KEY`
* OpenAI-compatible generative AI base URL derived from `REGION` as `https://inference.generativeai.{REGION}.oci.oraclecloud.com/openai/v1`
* OCI model identifier, default `openai.gpt-5.4`
* Assistant API URL for the frontend
* Log level
* Nutrition storage path, when the nutrition extension is implemented
* Nutrition upload size limit, when document upload is implemented
* Nutrition document retention policy, when document upload is implemented

Secrets must not be committed to the repository.

Single-user Garmin username and password environment variables may remain
temporarily available only as a backwards-compatible local development path.
They must not be the primary mechanism for multi-user operation.

## 15. Security and privacy requirements

Training data and nutrition data must be treated as sensitive personal data.

Requirements:

* Do not commit credentials
* Do not store local user passwords in plaintext
* Do not store Garmin credentials in plaintext
* Do not log raw Garmin payloads by default
* Do not log raw food diary entries or uploaded nutrition-plan documents by default
* Do not log full prompts containing detailed personal activity data by default
* Do not log full prompts containing detailed nutrition data by default
* Redact tokens and passwords from logs
* Keep Garmin Connect access inside backend code and away from the frontend
* Keep nutrition-plan parsing and adherence analysis inside backend code and away from the frontend
* Enforce data ownership in backend repositories and service methods, not in
  frontend state
* Prevent cross-user reads and writes for Garmin credentials, nutrition plans,
  diary entries, generated reports, and future caches
* Store uploaded nutrition documents and extracted text only according to the configured retention policy
* Allow future deletion/export workflows to be added without changing public contracts unnecessarily
* Use least privilege configuration where possible

## 16. Testing strategy

Tests must use `pytest` for Python services.

Python test categories:

* Unit tests for date range parsing and assistant orchestration logic
* Unit tests for Garmin response normalisation
* Unit tests for nutrition diary validation and weekly adherence analysis
* Unit tests for nutrition-plan text extraction and parsing when document upload is implemented
* HTTP tests for service endpoints
* Contract tests for assistant backend to Garmin API interactions using mocks
* Contract tests for nutrition endpoints using local fixtures
* Authentication and authorization tests for protected endpoints
* Cross-user isolation tests for nutrition plans, diary entries, Garmin
  credential lookup, and session storage path selection
* Error handling tests for Garmin failures and OCI failures
* Error handling tests for malformed nutrition uploads and incomplete diary data

Tests must not require live Garmin Connect or live OCI access during normal execution.

Frontend tests may be added later according to the selected Next.js testing setup.

## 17. Code quality

Python code must pass:

```text
black
pylint
pytest
```

Project configuration should make these commands easy to run locally and in CI.

Recommended commands per Python service:

```text
black app tests
pylint app tests
pytest
```

## 18. Error handling principles

Errors should be explicit and actionable.

Examples:

* Unauthenticated requests to protected endpoints should return a clear
  authentication error
* Authenticated requests for another user's resources should not reveal whether
  those resources exist
* Garmin authentication failure should return a clear service error
* Nutrition-plan upload or parsing failure should return a clear service error
* Garmin unavailable should not crash the assistant backend
* OCI model failure should return a graceful assistant error
* Invalid user input should return a validation error
* Unsupported nutrition document formats should return a validation error
* Unexpected errors should be logged with safe metadata only

## 19. Observability

Initial observability should be simple:

* Structured logs where practical
* Health endpoints for all backend services
* Request identifiers if easy to add
* Safe timing metrics in logs

Do not add heavy observability infrastructure in the initial version unless explicitly requested.

## 20. Development workflow

For each implementation task:

1. Identify the exact objective.
2. Check this specification and `AGENTS.md`.
3. Make the smallest code change that satisfies the objective.
4. Add or update `pytest` tests for Python behaviour.
5. Run `black`, `pylint`, and `pytest` for changed Python services.
6. Update this specification only when behaviour, architecture, or contracts change.
7. Avoid unrelated refactoring.

## 21. Milestone status

### Milestone 1, repository skeleton

Status: implemented.

* `AGENTS.md`
* This specification
* Docker Compose skeleton
* Empty service structure
* Health endpoints for Python services
* Basic frontend page

### Milestone 2, Garmin data provider foundation

Status: implemented.

* `TrainingDataProvider` backed by the Python `garminconnect` library
* Authentication configuration
* Activity list provider method
* Activity detail provider method
* Activity streams provider method, if needed by the first assistant workflows
* Heart-rate range provider method, preserving Garmin daily payload shape
* Daily metrics provider method, if needed by the first assistant workflows
* Normalised response schemas
* Tests with mocked Garmin data

### Milestone 3, assistant backend foundation

Status: implemented.

* Chat endpoint
* Local training provider adapter for assistant tools
* Simple date range inference
* Responses API integration through OCI Enterprise AI
* Tests with mocked training provider and mocked model calls

### Milestone 4, frontend chat flow

Status: implemented.

* Chat input
* Markdown response display
* Loading and error states
* Streaming connection to assistant backend
* Token usage display when returned by the backend

### Milestone 5, local deployment hardening

Status: implemented.

* Docker Compose working on Ubuntu Linux
* NGINX browser-facing reverse proxy for the local multi-user deployment
* Environment variable documentation
* Health checks
* Basic README instructions

### Milestone 6, nutrition adherence extension

Status: partially implemented. The current MVP includes diary persistence, PDF
plan upload, extracted-text storage, and on-demand adherence analysis through
assistant tooling. Remaining work is mostly product depth and API polish.

Implemented:

* Nutrition section in the Next.js frontend
* Food diary entry creation and single-day retrieval
* PDF nutrition-plan upload with extracted text storage
* User-scoped local SQLite nutrition persistence
* On-demand adherence report via `analyze_nutrition_adherence_period`
* Safe nutrition analysis prompt limits
* Tests with local fixtures and mocked model calls

Not yet implemented:

* Date-range diary listing endpoint for frontend browsing
* Dedicated weekly report endpoint outside chat/tool orchestration
* Markdown nutrition-plan upload
* Explicit nutrition upload size limit
* Original uploaded document retention, because the MVP intentionally stores
  only extracted text and metadata

### Milestone 7, multi-user foundation

Status: implemented foundation. The current deployment uses NGINX Basic Auth as
the browser-facing authentication layer and backend `user_id` ownership for
protected data. Some frontend experience and test coverage polish remains.

Implemented:

* Detailed migration plan in `docs/migration_multi_user/README.md`
* Local application user model with stable `user_id` and unique `username`
* NGINX Basic Auth and authenticated username forwarding
* Backend current-user resolution from `X-Authenticated-User`
* Backend enforcement of authenticated user identity on chat and nutrition
  endpoints
* User-scoped nutrition diary and nutrition-plan persistence
* User-scoped Garmin credential repository with encrypted at-rest storage
* User-scoped Garmin session storage
* Migration path from the current single-user nutrition storage to per-user
  records, if existing data must be preserved
* Tests for current-user resolution, repository isolation, credential secrecy,
  and user-scoped Garmin session path selection

Remaining:

* Clearer frontend propagation and display of `401 Unauthorized` and
  `403 Forbidden` responses from all proxy routes
* Current-user display or a safe current-user endpoint
* Documentation of Basic Auth logout limitations
* Broader HTTP-level cross-user isolation tests across protected endpoints
* Eventual removal or stricter isolation of the legacy single-user Garmin
  environment fallback from the default multi-user runtime

## 22. Open questions

Resolved implementation choices:

* Which Python web framework is selected for each backend service?
  FastAPI is used for the assistant backend.
* Should uploaded nutrition-plan originals be retained, or should only extracted text and structured summaries be stored?
  The MVP stores only extracted text and metadata; original PDFs are not
  retained.
* Which PDF extraction library should be used?
  `pypdf` is used for the current PDF text extraction implementation.
* Should the first multi-user authentication mechanism be local
  username/password, reverse-proxy authentication, or an external OIDC provider?
  The current local implementation uses NGINX Basic Auth with backend
  current-user resolution.
* How should the first admin or initial user be created in local Docker Compose
  deployments?
  `scripts/create_basic_auth_user.sh` creates or updates the Basic Auth entry
  and matching local application user.
* Should existing single-user nutrition data be migrated to a chosen initial
  user, or should multi-user setup start with an empty database?
  Both paths are supported: new deployments can start empty, and
  `services.assistant_api.identity.migrate_user_ids` can backfill existing
  nutrition rows to an initial user.
* Should each user have exactly one Garmin account, or should multiple Garmin
  accounts per application user be supported later?
  The current model supports one Garmin credential record per application user.

Still open:

* Which OCI region should be used as the default development region?
* Should the assistant keep conversation history locally, and if so, where?
* Which activity types should be prioritised first, running, cycling, swimming, strength, or all available activities?
* What maximum upload size should be allowed for nutrition documents?
* Should food diary entries support photos in a later iteration?
* Should nutrition reports be generated only on demand, or cached locally?
* What password policy and session lifetime should be used for local accounts?
* Should conversations and token usage be stored per user, or remain browser
  session state only?

## 23. Change control

Any architectural change must update this specification.

Examples of architectural changes:

* Adding a database
* Adding a cache
* Adding multi-user authentication or authorization
* Adding a credential store for per-user Garmin secrets
* Adding an MCP server
* Adding a background worker
* Adding nutrition document storage or changing its retention policy
* Adding autonomous nutrition recommendation capabilities
* Allowing the assistant backend to access Garmin Connect directly
* Exposing Garmin Connect access to the frontend
* Changing the model provider or model identifier

Implementation details that do not affect architecture may be changed without specification updates, provided they remain scoped to the task objective.
