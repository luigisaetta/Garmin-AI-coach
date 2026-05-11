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

The initial system is composed of three main services.

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

## 6. Service responsibilities

### 6.1 Next.js frontend

The frontend is responsible for:

* Rendering the assistant chat interface
* Sending user messages to the assistant backend
* Displaying responses, errors, loading states, and basic activity summaries
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
* Calling the local Garmin data API over HTTP
* Constructing model requests using the Responses API
* Calling OCI Enterprise AI with model `openai.gpt-5.4`
* Returning grounded answers to the frontend
* Handling assistant level errors and response shaping

The assistant backend must not:

* Import Garmin Connect vendor client code directly
* Store Garmin credentials
* Bypass the Garmin data API
* Introduce MCP server dependencies in the initial version

### 6.3 Garmin data API

The Garmin data API is responsible for:

* Authenticating with Garmin Connect
* Encapsulating Garmin Connect access in Python through a local training data provider
* Exposing local HTTP endpoints for activity and training data
* Normalising Garmin data into stable internal response schemas
* Handling Garmin specific errors, rate limits, and retries
* Optionally caching Garmin responses in a future iteration

The Garmin data API must be the only service that knows Garmin Connect implementation details.

The initial Garmin Connect implementation must use a local `TrainingDataProvider` abstraction backed by the open source Python `garminconnect` library. The `garminconnect` dependency must remain inside the Garmin data API service and must not leak into the assistant backend or frontend.

## 7. Initial container model

Docker Compose should define at least these services:

* `frontend`, Next.js application
* `assistant_api`, Python assistant backend
* `garmin_api`, Python Garmin data API

Suggested internal ports:

* `frontend`, exposed to the host
* `assistant_api`, internal plus optionally exposed for local debugging
* `garmin_api`, internal only by default

Service communication should use Docker Compose service names.

Example logical flow:

```text
frontend -> http://assistant_api:<port>
assistant_api -> http://garmin_api:<port>
assistant_api -> OCI Enterprise AI endpoint
```

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

The Garmin data API should encapsulate Garmin Connect access behind a provider interface. The initial provider is `TrainingDataProvider`, implemented inside the Garmin data API service and backed by the open source Python `garminconnect` library.

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
* Convert Garmin Connect responses into stable internal models before they are returned by HTTP endpoints
* Hide Garmin-specific response shapes, exceptions, retries, rate limits, and session handling from the rest of the application
* Provide a mockable boundary for unit tests and HTTP contract tests

The assistant backend must call the Garmin data API over HTTP and must never import or instantiate `TrainingDataProvider` directly.

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
│   │   ├── app
│   │   ├── tests
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   └── garmin_api
│       ├── app
│       ├── tests
│       ├── pyproject.toml
│       └── Dockerfile
└── frontend
    ├── app
    ├── package.json
    └── Dockerfile
```

This structure is a recommendation for the initial implementation. Changes are allowed only when they improve clarity while preserving the architecture and service boundaries.

## 10. Garmin data API contract, initial draft

The initial API should expose a small set of read only endpoints.

### 10.1 Health check

```text
GET /health
```

Returns service status.

### 10.2 List activities

```text
GET /activities?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD&activity_type=optional
```

Returns a normalised list of activities.

Each activity should include, when available:

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

### 10.3 Activity detail

```text
GET /activities/{activity_id}
```

Returns detailed normalised information for one activity.

The detail response may include:

* Summary metrics
* Laps or splits
* Heart rate series summary
* Pace or speed series summary
* Power metrics, when available
* Training effect fields, when available
* Device metadata, when useful

### 10.4 Recent activities

```text
GET /activities/recent?limit=20
```

Returns the most recent normalised activities.

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
  "conversation_id": "optional stable id"
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
* OCI endpoint
* OCI authentication configuration
* OCI model identifier, default `openai.gpt-5.4`
* Assistant API URL for the frontend
* Garmin API URL for the assistant backend
* Log level

Secrets must not be committed to the repository.

## 15. Security and privacy requirements

Training data must be treated as sensitive personal data.

Requirements:

* Do not commit credentials
* Do not log raw Garmin payloads by default
* Do not log full prompts containing detailed personal activity data by default
* Redact tokens and passwords from logs
* Keep Garmin data API internal to Docker Compose unless explicitly exposed for debugging
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

### Milestone 2, Garmin data API foundation

Deliver:

* `TrainingDataProvider` backed by the Python `garminconnect` library
* Authentication configuration
* Activity list endpoint
* Activity detail endpoint
* Activity streams endpoint or provider method, if needed by the first assistant workflows
* Daily metrics endpoint or provider method, if needed by the first assistant workflows
* Normalised response schemas
* Tests with mocked Garmin data

### Milestone 3, assistant backend foundation

Deliver:

* Chat endpoint
* Garmin API client
* Simple date range inference
* Responses API integration through OCI Enterprise AI
* Tests with mocked Garmin API and mocked model calls

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
* What exact OCI Enterprise AI SDK or endpoint configuration is required for Responses API usage?
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
* Exposing the Garmin data API outside Docker Compose
* Changing the model provider or model identifier

Implementation details that do not affect architecture may be changed without specification updates, provided they remain scoped to the task objective.
