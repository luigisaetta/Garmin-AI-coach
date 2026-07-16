# Training Goals and Race Calendar Specification

Last Modified: 2026-07-16

## 1. Purpose and status

This document specifies a future advanced feature for Garmin AI Coach: a
user-scoped place to record training goals and upcoming races, visualise them
alongside completed activities, and use them as explicit context for coaching
analysis.

The feature is not part of the initial implementation. It is deliberately
specified separately because its product rules must evolve from real athlete
use before the application attempts structured training-plan generation.

A frontend-only UX prototype is available at `/goals`. It uses sample data kept
only in browser memory to validate the create, edit, list, history, and
calendar experience. It must not be represented as stored user data.

The backend persistence foundation is implemented: authenticated users can
create, list, read, replace, and select active single-sport or multisport race
goals through protected `/training/goals` endpoints. The frontend prototype is
not connected to those endpoints yet. The compact activity calendar endpoint
and goal-aware dashboard, chat, and LLM analysis integration remain future
work.

`personal_ai_garmin_assistant_spec.md` remains authoritative for the
application architecture, authentication, Garmin provider boundary, OCI
integration, privacy requirements, and quality rules. This document becomes
authoritative for this feature when implementation begins.

## 2. User outcome

An authenticated athlete can answer three practical questions without having
to repeat their context in every chat message:

1. Which races and performance goals am I working toward?
2. How much time remains before my next important race, and what have I done
   recently for that sport?
3. How should the assistant interpret my recent training in the context of
   that goal?

The feature provides context and transparent interpretation. It must not claim
that an athlete is ready for a race, prescribe training, create a training
plan, or provide medical advice.

## 3. Scope

The first implementation includes:

* Creating, viewing, editing, completing, and cancelling race goals.
* A calendar and list view of the authenticated user's race goals and compact
  summaries of completed Garmin activities.
* A single active primary goal, selected from the user's upcoming goals.
* Single-sport races and multisport events, including sprint triathlon and
  half iron-distance / 70.3 events.
* Goal context in the Coach Overview, weekly reviews when implemented, training
  metrics analysis, training trends, and interactive chat when relevant.
* Explicit source and uncertainty descriptions in goal-aware analyses.

The first implementation does not include:

* Training-plan creation, scheduled workouts, or workout delivery to Garmin.
* Comparison of planned versus completed workouts.
* Automatic changes to a training plan or automatic workout recommendations.
* Push notifications, email reminders, or background jobs.
* Fitness predictions, race-time predictions, or readiness guarantees.
* Generic non-event goals such as "get fitter" without a race or event date.
* Sharing goals between application users.

## 4. Domain model

The initial domain entity is a `race_goal`. It represents one athlete-owned
event and the outcome the athlete wants from it. A separate generic goal table
or a full training-plan model is out of scope until experience shows that it is
needed.

Each record has at least these fields:

| Field | Rules | Purpose |
| --- | --- | --- |
| `id` | Backend-generated stable identifier. | Identifies the goal without exposing ownership keys. |
| `user_id` | Backend-owned; never accepted as an authoritative request field. | Enforces ownership. |
| `title` | Required, concise text. | Identifies the event, for example `Rome Marathon`. |
| `event_date` | Required ISO calendar date. | Enables calendar placement and countdown. |
| `sport` | Required: `running`, `cycling`, `swimming`, or `multisport`. | Selects relevant training context. |
| `distance_meters` | Optional positive integer for a single-sport event. | Describes the event without forcing a known distance. |
| `multisport_format` | Required for `multisport`; otherwise null. Initial values are `triathlon_sprint`, `triathlon_olympic`, `half_iron_distance`, `full_iron_distance`, and `other_multisport`. | Identifies the event format without relying on a race brand. |
| `segments` | Required logical collection for `multisport`; otherwise empty. Every segment has an ordered discipline and optional distance in metres. | Represents swim, bike, run, or another explicitly recorded discipline without flattening them into one misleading distance. |
| `priority` | Required: `A`, `B`, or `C`. | Distinguishes the main event from secondary events. |
| `goal_type` | Required: `completion` or `finish_time`. | Defines whether a measurable time target exists. |
| `target_duration_seconds` | Required only for `finish_time`; otherwise null. | Stores the target as a duration rather than a locale-specific string. |
| `notes` | Optional short free text. | Retains athlete context such as "first marathon". |
| `status` | `upcoming`, `completed`, or `cancelled`. | Preserves history without destructive deletion. |
| `created_at`, `updated_at` | Backend timestamps. | Supports audit and display. |

Validation rules:

* `event_date` may be in the past only when creating a `completed` or
  `cancelled` historical record.
* A `finish_time` target must be positive and use a realistic upper bound
  defined by the implementation; the API must return a validation error rather
  than silently normalising it.
* An athlete may have multiple upcoming goals, but only one upcoming goal with
  priority `A` for the same sport and event date.
* The user may edit an upcoming goal. A completed or cancelled goal remains
  visible in history and may be corrected only through an intentional status or
  metadata update.
* Goals are archived through their status; the initial UI must not offer hard
  deletion.
* A multisport goal must contain at least two ordered segments. The common
  triathlon case uses swimming, cycling, and running; the model must not assume
  a discipline that the athlete did not enter.
* `distance_meters` and segment distances must not both be treated as a
  canonical event distance. For a multisport goal, segment distances are the
  authoritative representation whenever they are available.

`segments` is a domain collection, not an opaque free-text field. The MySQL
implementation should persist it in a user-scoped `race_goal_segments` child
table keyed by the owning `race_goal`, with `sequence`, `sport`, and optional
`distance_meters` columns. This preserves ordering and allows future athlete
feedback to refine the model without changing goal ownership or public API
semantics.

## 5. User experience

The frontend should expose a dedicated `/goals` page and link it from the main
navigation.

### 5.1 Create and edit

The create form must be short and use progressive disclosure:

1. Event title, date, sport, and priority.
2. Optional distance for a single-sport race; a multisport format plus ordered
   disciplines and optional distances for a multisport event.
3. Goal choice: finish the event or finish within a target time.
4. Optional notes.

The edit experience must show the current values and let the athlete change an
upcoming event, mark it completed, or cancel it. It must clearly state that
changing a goal changes the context used for future analyses, but does not
rewrite previously generated answers or reports.

### 5.2 List and calendar

The page must provide:

* A compact next-goal card with title, priority, sport, target, and days until
  the event.
* An upcoming-goals list ordered by event date, followed by historical goals.
* A monthly calendar that displays race goals and compact completed-activity
  markers for the selected date interval.
* A clear visual distinction between an event, a completed activity, and an
  empty day. The calendar must not imply that an activity was planned merely
  because it appears next to a race goal.

The calendar may initially use monthly navigation and a bounded date range.
It must retrieve activity summaries and goals through backend endpoints and
must never access Garmin Connect from the browser.

### 5.3 Coach Overview

Coach Overview should display the selected primary goal only when one exists.
The card must show the event title, sport, event date, days remaining, priority,
and target when present. It may state that the current week's load is
week-to-date or projected, following the existing overview rules.

It must not show a synthetic "goal readiness" percentage in the first
implementation. When no primary goal exists, it should offer a quiet call to
action to add one rather than treating the absence as an error.

## 6. Backend API contract

All endpoints are protected. The assistant backend resolves the authenticated
user from backend-validated authentication state and applies it to every read
and write. Request bodies and query parameters must not contain an
authoritative `user_id` or username.

Initial endpoint candidates are:

```text
POST  /training/goals
GET   /training/goals?status=upcoming|history
GET   /training/goals/{goal_id}
PATCH /training/goals/{goal_id}
GET   /training/goals/active
GET   /training/calendar?begin_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

`PATCH /training/goals/{goal_id}` handles metadata changes and explicit status
transitions. A separate archive endpoint is unnecessary in the first contract.

The calendar response must contain only compact goal and activity data needed
for display, for example identifiers, local calendar date, sport, event title,
status, activity duration, and activity type. It must not return raw Garmin
payloads, credentials, session data, GPS coordinates, or activity streams.

The backend must validate inclusive calendar ranges and impose a documented
maximum range. It may call `TrainingDataProvider` for the authenticated user to
obtain compact activity summaries. Goal persistence belongs in MySQL through a
dedicated repository or service; Garmin provider access remains behind
`TrainingDataProvider`.

## 7. Goal selection for analysis

Goal-aware analysis must be deterministic about which goal is used:

1. An explicitly selected `goal_id` is used only after ownership and
   applicability validation.
2. Otherwise, use the nearest upcoming `A` priority goal for the analysis
   sport.
3. If there is no applicable `A` goal, use the nearest upcoming `B` or `C`
   goal for that sport.
4. If no applicable goal exists, perform the existing analysis without goal
   context and say that no event goal was selected when this matters.

A goal for one sport must not silently shape an analysis for another sport. A
multisport goal may provide event-level context only when selected explicitly
or when the question concerns the event as a whole. It must not automatically
shape a running-only, cycling-only, or swimming-only analysis. Segment-specific
context requires an explicit athlete selection in a future iteration.

## 8. Use in analyses

### 8.1 Deterministic dashboards

The Coach Overview, training metrics, and training trends views may display
goal metadata and countdown information directly from backend responses. Their
canonical training metrics remain deterministic and unchanged by the goal.

The application may relate recent sport-specific volume and load to the time
remaining before an event, but it must not infer a required load, declare
readiness, or imply that a load ratio represents race preparedness. Missing
training load, missing heart-rate data, a partial active week, and a small
history window must remain visible as uncertainty.

### 8.2 LLM training metrics analysis and chat

The backend may provide local model tools such as:

```text
get_active_training_goal()
get_training_goal(goal_id)
list_training_goals(begin_date, end_date)
```

Goal data passed to OCI must be compact: title, event date, sport, distance,
multisport format, compact segment descriptors, priority, goal type, target
duration, and notes when relevant. It must not include data belonging to
another user.

The dedicated metrics-analysis request may accept an optional `goal_id`.
Interactive chat should request goal context only when the athlete asks about
an event, a target, preparation, or a goal-aware comparison. The assistant must
describe the goal as athlete-provided context, distinguish observed facts from
interpretation, and avoid prescriptions or performance guarantees.

### 8.3 Future weekly review

When a dedicated weekly review is implemented, it may include the applicable
active goal, days remaining, relevant sport-specific completed training, and
clearly labelled uncertainty. It must not compare planned and completed
workouts until a separately specified training-plan feature exists.

### 8.4 Nutrition analysis

Nutrition adherence analysis may use an applicable goal only as contextual
metadata, for example an upcoming running event or a high-load week. It must
continue to assess adherence to the uploaded nutrition plan and recorded diary,
not prescribe intake, diagnose conditions, or infer quantities absent from the
diary or plan.

## 9. Persistence, privacy, and security

* Race goals are sensitive personal training context and must be scoped by
  `user_id` in every query and repository operation.
* The database must index ownership and event date for list, calendar, and
  active-goal queries.
* Goal notes must not be logged verbatim or included in broad diagnostic logs.
* Cross-user reads and writes must return intentional safe errors without
  revealing whether another user's goal exists.
* The UI must not expose internal identifiers, credential metadata, Garmin
  session paths, or raw training payloads.

## 10. Testing requirements

Implementation must add fast tests for:

* Field validation, target-duration rules, allowed status transitions, and
  multisport format/segment rules.
* Current-user ownership enforcement for every CRUD endpoint.
* Repository isolation between at least two users.
* Active-goal selection by explicit selection, priority, sport, event date,
  and the rule that a multisport goal does not implicitly apply to one sport.
* Calendar range validation and compact response shaping.
* Goal omission and applicable-goal inclusion in model-tool and analysis
  requests, using mocked OCI and Garmin provider calls.
* Frontend create, edit, empty state, and calendar rendering behaviours.

Normal tests must not use live Garmin Connect or OCI credentials.

## 11. Delivery sequence

1. Done: add the MySQL schema, repository, typed backend contracts, and
   ownership tests.
2. In progress: connect the goal list and create/edit form to the protected
   backend contracts, add status transitions to the persisted UI, and add the
   active-goal Coach Overview card.
3. Add the bounded calendar view with compact completed-activity markers.
4. Add explicit goal selection and compact context to metrics analysis and chat.
5. Evaluate athlete use before specifying generic goals, training plans,
   planned-versus-completed comparisons, notifications, or recommendations.

## 12. Decisions to revisit from athlete feedback

The following choices should be validated after real use rather than assumed in
the first release:

* Whether athletes need generic goals in addition to event-based goals.
* Whether one primary goal per sport is sufficient or priority rules need to be
  more flexible.
* Whether distance, location, race series, or an external event reference adds
  meaningful value without creating unnecessary private data.
* Which multisport formats and segment fields athletes actually need beyond
  swim, bike, and run distances.
* How much historical goal editing should be allowed.
* Whether a future training-plan feature should be manual, imported, or both.
* Which goal-aware messages athletes find useful rather than distracting.
