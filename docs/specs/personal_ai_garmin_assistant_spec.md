# Personal AI Garmin Assistant Specification

## 1. Purpose

This document defines the initial architecture and implementation constraints for a personal AI assistant that answers questions about Garmin Connect training data.

The project should start with a simple but rigorous architecture that can run locally on an Intel NUC with Ubuntu Linux, while remaining extensible for future features such as richer analytics, caching, additional data sources, and deeper coaching workflows.

This document is referenced by `AGENTS.md` and should be treated as the source of truth for implementation decisions.

## 2. Product objective

Build a web based personal AI assistant that can:

* Access the user’s Garmin Connect training data
* Read training data on demand through a local API
* Use generative AI to answer interactive questions about workouts and training history
* Present answers through a Next.js web interface
* Run locally through Docker Compose on Ubuntu Linux

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
* Multi user account management
* Cloud deployment automation
* Complex distributed infrastructure
* Live writeback to Garmin Connect
* Long term coaching plan generation unless explicitly added later

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

## 6. Service responsibilities

### 6.1 Next.js frontend

The frontend is responsible for:

* Rendering the assistant chat interface
* Sending user messages to the assistant backend
* Displaying responses, errors, loading states, and basic activity summaries
* Displaying assistant-reported token usage counters for the current chat
* Keeping browser side logic simple

The frontend must not:

* Call Garmin Connect directly
* Store Garmin credentials
* Perform training analytics that belong in backend services
* Call OCI Enterprise AI directly

### 6.2 Assistant backend

The assistant backend is responsible for:

* Receiving user questions from the frontend
* Deciding what Garmin data is needed
* Exposing model tools that call the local Python training data provider
* Constructing model requests using the Responses API
* Calling OCI Enterprise AI with model `openai.gpt-5.4`
* Returning grounded answers to the frontend
* Returning Responses API token usage summaries when available
* Handling assistant level errors and response shaping

The assistant backend must not:

* Store Garmin credentials outside environment variables or mounted secret files
* Let the frontend access Garmin Connect or training provider code directly
* Introduce MCP server dependencies in the initial version

### 6.3 Garmin data access layer

The Garmin data access layer is responsible for:

* Authenticating with Garmin Connect
* Encapsulating Garmin Connect access in Python through `TrainingDataProvider`
* Normalising Garmin data into stable internal response schemas
* Handling Garmin specific errors, rate limits, and retries
* Optionally caching Garmin responses in a future iteration

The assistant backend may use `TrainingDataProvider` through a narrow local
adapter when executing model-selected tools. The frontend must never import or
call Garmin Connect code directly.

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

    def get_daily_metrics(...):
        ...
```

Provider responsibilities:

* Own all direct calls to the `garminconnect` library
* Authenticate with Garmin Connect using configuration supplied by environment variables or mounted secret files
* Reuse Garmin session tokens from `GARMIN_SESSION_STORAGE_PATH` when configured, and save refreshed tokens there after credential login
* Convert Garmin Connect responses into stable internal models before they are returned to assistant tools
* Mask noisy or personal account and location fields that are not useful for coaching analysis, such as `userRoles`, owner metadata, profile image URLs, coordinates, and location names, before data can be passed toward the assistant or LLM context when `REDACT_PII` is enabled
* Hide Garmin-specific response shapes, exceptions, retries, rate limits, and session handling from the rest of the application
* Provide a mockable boundary for unit tests

The assistant backend must access Garmin data only through assistant tools and
the local provider adapter. Tool calls are selected by the LLM through the
Responses API; the frontend does not select or call tools directly.

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
* Large raw payloads are summarised or reduced before being sent to the model
* Private data is handled carefully
* Model errors produce useful application errors

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
* Embeddings or searchable summaries
* User controlled data retention
* Background sync jobs

These are not required in the initial version.

## 14. Configuration

Configuration must come from environment variables or mounted secret files.

Likely configuration values:

* Garmin username or credential reference
* Garmin password or credential reference
* Garmin session storage path, if used
* PII redaction flag, `REDACT_PII`, default enabled
* OCI region, `REGION`
* Generative AI API key, `GENAI_API_KEY`
* OpenAI-compatible generative AI base URL derived from `REGION` as `https://inference.generativeai.{REGION}.oci.oraclecloud.com/openai/v1`
* OCI model identifier, default `openai.gpt-5.4`
* Assistant API URL for the frontend
* Log level

Secrets must not be committed to the repository.

## 15. Security and privacy requirements

Training data must be treated as sensitive personal data.

Requirements:

* Do not commit credentials
* Do not log raw Garmin payloads by default
* Do not log full prompts containing detailed personal activity data by default
* Redact tokens and passwords from logs
* Keep Garmin Connect access inside backend code and away from the frontend
* Use least privilege configuration where possible

## 16. Testing strategy

Tests must use `pytest` for Python services.

Python test categories:

* Unit tests for date range parsing and assistant orchestration logic
* Unit tests for Garmin response normalisation
* HTTP tests for service endpoints
* Contract tests for assistant backend to Garmin API interactions using mocks
* Error handling tests for Garmin failures and OCI failures

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

* Garmin authentication failure should return a clear service error
* Garmin unavailable should not crash the assistant backend
* OCI model failure should return a graceful assistant error
* Invalid user input should return a validation error
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

## 21. Initial milestones

### Milestone 1, repository skeleton

Deliver:

* `AGENTS.md`
* This specification
* Docker Compose skeleton
* Empty service structure
* Health endpoints for Python services
* Basic frontend page

### Milestone 2, Garmin data provider foundation

Deliver:

* `TrainingDataProvider` backed by the Python `garminconnect` library
* Authentication configuration
* Activity list provider method
* Activity detail provider method
* Activity streams provider method, if needed by the first assistant workflows
* Daily metrics provider method, if needed by the first assistant workflows
* Normalised response schemas
* Tests with mocked Garmin data

### Milestone 3, assistant backend foundation

Deliver:

* Chat endpoint
* Local training provider adapter for assistant tools
* Simple date range inference
* Responses API integration through OCI Enterprise AI
* Tests with mocked training provider and mocked model calls

### Milestone 4, frontend chat flow

Deliver:

* Chat input
* Response display
* Loading and error states
* Connection to assistant backend

### Milestone 5, local deployment hardening

Deliver:

* Docker Compose working on Ubuntu Linux
* Environment variable documentation
* Health checks
* Basic README instructions

## 22. Open questions

These questions should be resolved before or during implementation:

* Should Garmin sessions be stored on disk, and where inside the container volume?
* Which Python web framework is selected for each backend service?
* Which OCI region should be used as the default development region?
* Should the assistant keep conversation history locally, and if so, where?
* Which activity types should be prioritised first, running, cycling, swimming, strength, or all available activities?

## 23. Change control

Any architectural change must update this specification.

Examples of architectural changes:

* Adding a database
* Adding a cache
* Adding an MCP server
* Adding a background worker
* Allowing the assistant backend to access Garmin Connect directly
* Exposing Garmin Connect access to the frontend
* Changing the model provider or model identifier

Implementation details that do not affect architecture may be changed without specification updates, provided they remain scoped to the task objective.
