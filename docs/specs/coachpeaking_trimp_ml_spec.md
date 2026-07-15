# CoachPeaking TRIMP Estimation ML Subproject Specification

Last Modified: 2026-07-15

## 1. Purpose

This document specifies a future supervised machine-learning subproject that
estimates the effective TRIMP score reported by CoachPeaking for a completed
running activity using Garmin-derived activity data.

The target is an estimate of the CoachPeaking score, not a medical assessment,
not a universal physiological TRIMP calculation, and not a replacement for a
coach's judgement. The model is personal to one `OWNER_ID`; it must not be
presented as a model that generalises to other athletes without separate
validation.

This subproject is not implemented by the current downloader, Oracle loader,
or Garmin AI Coach runtime.

## 2. Scope

The first iteration is limited to:

* Completed activities whose Garmin activity type is `running`.
* A CoachPeaking effective TRIMP value associated with the same activity.
* Garmin activity-summary and heart-rate-zone data already planned for the
  Oracle schema.

The first iteration does not include cycling, swimming, multisport activities,
planned-workout TRIMP, medical advice, training prescriptions, or automated
changes to a training plan.

## 3. Problem definition

For each eligible completed running activity, the model predicts:

```text
TARGET = COACHPEAKING_EFFECTIVE_TRIMP
```

CoachPeaking and Garmin may use different heart-rate zone boundaries. The
model therefore estimates the CoachPeaking output from Garmin features; it does
not assume Garmin zones are equivalent to CoachPeaking zones.

## 4. Label dataset

The Oracle schema will later be extended with this table:

```text
GARMIN_ACTIVITY_TRIMP_LABEL
```

| Column | Purpose |
|---|---|
| `OWNER_ID` | Opaque owner identifier. |
| `GARMIN_ACTIVITY_ID` | Garmin activity identifier. |
| `TRIMP_SOURCE` | Initially the constant `COACHPEAKING`. |
| `TRIMP_VALUE` | Effective TRIMP reported by CoachPeaking. |
| `LABEL_RECORDED_AT_UTC` | Timestamp at which the label was collected. |

The primary key is `(OWNER_ID, GARMIN_ACTIVITY_ID, TRIMP_SOURCE)`.

Each label must be matched deterministically to the Garmin activity. The
preferred key is the shared external activity identifier when available.
Otherwise, matching must use a documented combination of activity start time,
duration, sport, and distance, with ambiguous matches rejected for manual
review.

## 5. Feature set

All feature values must be available after the activity has completed. The
model must not use CoachPeaking-derived values as input features.

### 5.1 Included features

The initial feature set is:

```text
DURATION_SECONDS
DISTANCE_METERS
AVERAGE_HEART_RATE
MAX_HEART_RATE
AVERAGE_SPEED_MPS
MAX_SPEED_MPS
AVERAGE_RUNNING_CADENCE_SPM
ACTIVITY_TRAINING_LOAD
AEROBIC_TRAINING_EFFECT
ANAEROBIC_TRAINING_EFFECT
HR_TIME_IN_ZONE_1
HR_TIME_IN_ZONE_2
HR_TIME_IN_ZONE_3
HR_TIME_IN_ZONE_4
HR_TIME_IN_ZONE_5
```

`HR_TIME_IN_ZONE_<N>` is derived by pivoting the rows of
`GARMIN_ACTIVITY_HR_ZONE` for the activity. A missing zone duration must be
represented as zero only when the activity has a valid heart-rate-zone payload;
otherwise the activity must be marked as having missing heart-rate-zone data.

The training-load and training-effect fields are optional Garmin features. The
dataset must retain a missingness indicator for each optional feature rather
than replacing missing values with an unlabelled zero.

### 5.2 Explicitly excluded features

The model must not use elevation fields, including direct or derived values:

```text
ELEVATION_GAIN_METERS
ELEVATION_LOSS_METERS
TOTAL_ASCENT
MAX_ELEVATION_GAIN_METERS
```

Historic elevation data is not reliable for part of the available period. This
exclusion applies to training, validation, inference, feature selection, and
derived features.

The model must also exclude Garmin credentials, session data, GPS coordinates,
routes, activity names, media, raw payloads, and data from other athletes.

## 6. Data quality and eligibility

An activity is eligible only when it:

* Has type `running`.
* Has a non-negative CoachPeaking TRIMP label.
* Has a valid duration and distance.
* Has a deterministic activity-label match.

Activities missing heart-rate data may be retained only in a separate
experimentation cohort. They must not be mixed silently with activities having
valid heart-rate-zone data.

The dataset must record the source export schema version, label collection
timestamp, and feature-extraction version for reproducibility.

## 7. Model development approach

The development sequence is deliberately simple:

1. Establish a transparent baseline using regularised linear regression with
   non-negative zone-duration coefficients.
2. Compare the baseline with a compact tabular non-linear model, such as a
   gradient-boosted tree model or a generalised additive model.
3. Select the simpler model unless the more complex model provides a material,
   stable improvement on future-time validation data.

Neural networks are out of scope for the first iteration.

The initial dataset goal is at least 200 labelled running activities. A more
reliable first evaluation target is 300 or more activities spanning easy runs,
long runs, interval sessions, races, and recovery runs.

## 8. Evaluation

Data must be split chronologically, never randomly. For example:

```text
Oldest activities       -> training set
Following activities    -> validation set
Most recent activities  -> final test set
```

The evaluation report must include:

* Mean absolute error in TRIMP points.
* Root mean squared error in TRIMP points.
* Mean absolute percentage error, excluding labels equal to zero.
* Error by TRIMP range and activity duration range.
* A comparison with the transparent linear baseline.

The report must explicitly state the covered time period, number of activities,
missing-feature handling, and whether Garmin and CoachPeaking zone
configurations were known to differ.

## 9. Future extension: activity heart-rate samples

The current portable export contains activity summary zone durations but not an
activity-level heart-rate time series. If summary features do not estimate
CoachPeaking TRIMP with sufficient accuracy, a later, separately specified
extension may export the heart-rate stream for each eligible running activity.

That extension must be optional, privacy-reviewed, and limited to the running
ML dataset. It is not authorised by this specification to collect GPS streams,
routes, or unrelated activity-stream data.
