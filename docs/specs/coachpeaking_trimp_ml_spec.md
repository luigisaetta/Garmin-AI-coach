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

## 4. Manual label file

CoachPeaking TRIMP labels are entered manually in a separate CSV file. The file
is the input to data preparation; it is not an Oracle source table and must not
be committed to Git.

The default local path is:

```text
data/coachpeaking-trimp-labels.csv
```

The required UTF-8 CSV format is:

```csv
GARMIN_ACTIVITY_ID,COACHPEAKING_TRIMP
123456789,42.5
```

`GARMIN_ACTIVITY_ID` is copied from `activities.ndjson` or from the loaded
`GARMIN_ACTIVITY` table. `COACHPEAKING_TRIMP` is the effective TRIMP value read
from CoachPeaking for that completed activity.

The manual label file must contain one row per Garmin activity identifier. It
must not contain Garmin credentials, session tokens, athlete email addresses,
or CoachPeaking credentials.

Data preparation supplies `OWNER_ID` as an explicit run parameter and performs
the deterministic join on `(OWNER_ID, GARMIN_ACTIVITY_ID)`. It rejects duplicate
activity identifiers, labels for unknown activities, non-numeric values, and
negative TRIMP values. Activity start time, duration, sport, and distance are
used as a review report for manually entered labels, not as an alternate
automatic matching key.

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
exclusion applies to training, development, inference, feature selection, and
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

The dataset must record the source export schema version, data-preparation
timestamp, feature-extraction version, and `ZONE_PROFILE_VERSION` for
reproducibility. `ZONE_PROFILE_VERSION` identifies the Garmin and
CoachPeaking zone configuration applicable to an activity. Activities recorded
before a material zone-configuration change must be excluded from the first
model unless they can be assigned to an equivalent zone-profile version.

## 7. Data preparation outputs

The full data-preparation workflow reads the Oracle activity tables and the
manual label file. It creates a reproducible tabular feature dataset after
applying the eligibility, feature, and missing-value rules in this
specification.

Before the Oracle loader is implemented, a local bootstrap extractor may read
completed portable Garmin export packages directly. It is limited to creating
the 2025 training CSV template for manual CoachPeaking TRIMP entry. The
extractor must validate that each package is completed, include only
`running` activities (excluding `treadmill_running`), and write only the
activity identifier, local activity start date for label review, the included
features in section 5.1, the required
optional-feature missingness indicators, and an empty
`COACHPEAKING_TRIMP` target column. It must not write raw payloads, activity
names, coordinates, or other excluded fields. This bootstrap output is not a
replacement for the later Oracle-based reproducible dataset workflow.

The default local output directory is:

```text
data/coachpeaking-trimp-dataset/<DATASET_VERSION>/
```

The process writes these UTF-8 CSV or Parquet files:

```text
TRIMP_FEATURES.<csv|parquet>
TRIMP_TRAIN.<csv|parquet>
TRIMP_DEV.<csv|parquet>
TRIMP_TEST.<csv|parquet>
DATASET_MANIFEST.json
```

`TRIMP_FEATURES` contains all eligible labelled activities before the temporal
split. `TRIMP_TRAIN`, `TRIMP_DEV`, and `TRIMP_TEST` contain the chronological
partitions defined in section 9. The manifest records the data-preparation
version, source import batches, label-file checksum, owner identifier, feature
list, row counts, date boundaries, and missing-value rules.

The data-preparation output files are derived local data and must not be
committed to Git.

## 8. Model development approach

The development sequence is deliberately simple:

1. Establish a transparent baseline using regularised linear regression with
   non-negative zone-duration coefficients.
2. Compare the baseline with a compact tabular non-linear model, such as a
   gradient-boosted tree model or a generalised additive model.
3. Select the simpler model unless the more complex model provides a material,
   stable improvement on future-time development data.

Neural networks are out of scope for the first iteration.

The initial dataset goal is at least 200 labelled running activities. A more
reliable first evaluation target is 300 or more activities spanning easy runs,
long runs, interval sessions, races, and recovery runs.

## 9. Temporal split and evaluation

Data must be split chronologically, never randomly. For an initial dataset
starting on 2025-01-01 and containing approximately two to three running
activities per week, the first experiment uses:

```text
2025-01-01 to 2025-12-31  -> training set
2026-01-01 to 2026-03-31  -> development set
2026-04-01 to 2026-06-30  -> final test set
```

This produces an estimated 104 to 156 training activities and 26 to 39
activities in each development and test period. If the available labelled data
is smaller, use an earliest 65% training period, followed by 15% development and
20% test periods. Development and test periods should each contain at least 25
eligible activities and must end on complete calendar weeks where possible.

The test set is not used for feature selection, hyperparameter selection, or
missing-value rules. Scaling, imputation, and all feature transformations must
be fitted on the training set only and then applied unchanged to development and
test data.

After the first experiment, perform rolling-origin validation:

```text
Train through a cutoff date -> validate on the following three months
Advance the cutoff date      -> repeat
```

This checks whether the estimation remains stable across future training
periods instead of fitting one favourable historical split.

The evaluation report must include:

* Mean absolute error in TRIMP points.
* Root mean squared error in TRIMP points.
* Mean absolute percentage error, excluding labels equal to zero.
* Error by TRIMP range and activity duration range.
* A comparison with the transparent linear baseline.

The report must explicitly state the covered time period, number of activities,
missing-feature handling, and whether Garmin and CoachPeaking zone
configurations were known to differ.

## 10. Future extension: activity heart-rate samples

The current portable export contains activity summary zone durations but not an
activity-level heart-rate time series. If summary features do not estimate
CoachPeaking TRIMP with sufficient accuracy, a later, separately specified
extension may export the heart-rate stream for each eligible running activity.

That extension must be optional, privacy-reviewed, and limited to the running
ML dataset. It is not authorised by this specification to collect GPS streams,
routes, or unrelated activity-stream data.
