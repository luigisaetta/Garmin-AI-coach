# Garmin-to-Oracle Export Subproject Specification

Last Modified: 2026-07-15

## 1. Purpose

This document specifies the Garmin-to-Oracle data transfer subproject of
Garmin AI Coach. The subproject transfers only the Garmin data currently used
by the coach assistant. It uses two independent steps:

1. A local Python exporter downloads a bounded date range for one Garmin
   Connect account and creates a portable export package.
2. A separate Oracle loader, to be implemented later, validates a completed
   package and loads it into an existing Oracle schema.

The first exporter is implemented. The Oracle loader remains future work.
The first Oracle schema and loader version exclude HRV persistence until a
non-empty HRV payload is available for validation.

This document complements `personal_ai_garmin_assistant_spec.md`. The parent
specification remains authoritative for the `TrainingDataProvider` boundary,
Python quality requirements, and privacy requirements.

The relational Oracle schema is specified separately in
`docs/specs/garmin_oracle_schema_spec.md`.

## 2. Scope

The initial exporter scope is deliberately limited to data exposed to the
current coach assistant:

* Activity summaries from `list_activities`.
* Daily heart-rate data from `get_heart_rates`.
* Daily heart-rate variability data from `get_hrv_data`.

The exporter must not download or export activity streams, FIT/GPX/TCX files,
GPS coordinates, routes, media, device metadata, account or profile data,
daily metrics not used by the assistant, nutrition data, Garmin credentials,
or session tokens.

## 3. Architecture and responsibilities

The exporter is a local Python command-line tool. It is not an assistant tool,
does not expose an HTTP endpoint, and does not add or require a Docker Compose
service. It uses `TrainingDataProvider`, but it does not require the assistant
deployment, MySQL, application-user identity, application credentials, or
application session storage. It must not call the `garminconnect` library
directly or connect to Oracle.

The initial implementation is invoked from the repository root after the
`garmin-ai-coach` Conda environment has been activated:

```text
python -m services.garmin_export \
  --username <garmin-connect-username> \
  --from YYYY-MM-DD \
  --to YYYY-MM-DD \
  --output <output-root> \
  --session-dir <local-session-directory>
```

The command prompts for the Garmin Connect password without echoing it. The
password is used only for the current process and is never written to disk,
logs, or the export package. `TrainingDataProvider` creates or reuses a Garmin
session token in `--session-dir`, which defaults to
`data/garmin-export-session`. Docker and `.env` are not required.

```text
Garmin Connect
       |
       v
TrainingDataProvider
       |
       v
Garmin exporter CLI
       |
       v
Portable export package
       |
       v
Oracle loader (future, separate)
       |
       v
Existing Oracle schema
```

The future Oracle loader is a separate responsibility. It must consume only
completed packages that validate against their manifests. Oracle credentials
must be supplied through environment variables or mounted secret files and
must never be written to an export package.

## 4. Data minimisation and projection

### 4.1 Activity summaries

The exporter must apply the same coaching projection as the compact provider
payload, regardless of the `GARMIN_COMPACT_ACTIVITY_PAYLOAD` setting. Permitted
fields are:

* Activity identity, name, type, and start time.
* Duration, distance, elevation, calories, and steps.
* Training load and moderate or vigorous intensity minutes.
* Average and maximum heart rate.
* Speed or pace.
* Running cadence and running-dynamics values.
* Power values.
* Aerobic and anaerobic training effect and VO2 max.
* Heart-rate and power zone summaries.
* Split summaries, when available.

No field previously removed by the provider's PII redaction or compact activity
projection may be restored in an export.

### 4.2 Daily heart rate and HRV

The exporter must start from the provider's sanitised daily outputs. It retains
only fields relevant to current assistant questions:

* Calendar date, daily heart-rate summaries, and heart-rate time-series values.
* HRV nightly, weekly, status, and trend values, when available.

PII fields must be omitted rather than masked. A missing daily HRV response
must be represented as a record with a null `data` value, so that absence is
distinguishable from an unrequested date.

## 5. Export package contract, version 1

Each completed export creates one directory with this layout:

```text
<output-root>/<owner-id>/<begin-date>_to_<end-date>/
  manifest.json
  activities.ndjson
  daily_heart_rate.ndjson
  daily_hrv.ndjson
```

Dates use ISO `YYYY-MM-DD` format and are inclusive. `owner-id` is an opaque
local identifier selected with `--owner-id`; it defaults to `local-user` and
must never be a Garmin username or email address.

Each NDJSON file is UTF-8 and contains one JSON object per line. Every record
must contain:

* The dataset name.
* `schema_version`, initially `1`.
* The local `owner_id`.
* Its natural source key: `activityId` for activities or calendar date for
  daily datasets.
* A `data` object containing only the permitted fields for that dataset.

`manifest.json` must contain at least:

* `schema_version`, initially `1`.
* Dataset names and relative file names.
* The local `owner_id`.
* The inclusive requested date range.
* Export completion timestamp in UTC.
* Per-dataset record counts and SHA-256 checksums.
* Exporter version and explicit completion status.

## 6. Reliability and privacy requirements

The exporter writes into a temporary sibling directory and atomically renames
it to the final directory only after all files, checksums, and manifest have
been written successfully. It must fail rather than overwrite an existing
completed export directory.

Logs may contain only dates, local owner IDs, dataset counts, and safe error
metadata. They must not contain record payloads, Garmin credentials, session
tokens, or Oracle credentials.

## 7. Oracle loader requirements

The Oracle loader is not part of the first implementation, but packages must be
designed for its idempotent import. It must use Oracle `MERGE` operations keyed
by `(owner_id, activityId)` for activities and `(owner_id, calendar_date)` for
the daily heart-rate dataset. The `daily_hrv.ndjson` file remains part of the
portable export package but must not be loaded into Oracle version 1.

It must verify every manifest checksum and reject incomplete, altered, or
unsupported package versions before writing any data to Oracle.
