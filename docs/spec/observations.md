# Observations (RAW-OBS-V0)

## Core invariant

`value != evidence status`. A numeric, string or list value is never sufficient
on its own. Zero, empty and false are only ever *positively observed* values. A
collector that cannot prove a value emits no value and an explicit status.

## Envelope

| Field | Meaning |
| --- | --- |
| `observation_id` | Stable provider-neutral key, e.g. `forge.issues.open_count` |
| `schema_version` | `RAW-OBS-V0` |
| `provider` | `github`, `config`, or a future adapter id |
| `collected_at` | Acquisition timestamp (UTC, second precision) |
| `source_ref` | Deterministic description of the endpoint, query or derivation |
| `status` | `AVAILABLE`, `PARTIAL`, `UNAVAILABLE`, `FORBIDDEN`, `UNKNOWN`, `ERROR` |
| `freshness` | `FRESH`, `STALE`, `UNKNOWN`; orthogonal to status |
| `value_type` | `count`, `ratio`, `duration`, `boolean`, `enum`, `string`, `set`, `series`, `record` |
| `value` | Present only for `AVAILABLE` and `PARTIAL` |
| `coverage` | Denominator and scope: completeness flags, window boundaries, caps |
| `evidence_ref` | Identifiers needed to reproduce or audit the observation |
| `adapter_version` | Collector implementation version |
| `reason_code` | Normalized reason for a non-available state |
| `notes` | Diagnostic text; never consumed by evaluation |

## Status semantics

- **AVAILABLE**: the requested semantic value was observed over the declared scope with no known completeness defect.
- **PARTIAL**: some valid evidence exists but the scope is known to be incomplete (a pagination cap, an unresolved subset). Partial is never permission to scale up or impute.
- **UNAVAILABLE**: the source does not exist for this repository, plan or configuration (a disabled feature, a tier limitation, `planning.source = none`). This is not a zero.
- **FORBIDDEN**: the source plausibly exists but access was denied.
- **UNKNOWN**: the collector cannot establish whether the source exists, is complete or is accessible.
- **ERROR**: acquisition was attempted and failed for a technical reason (network, provider error, rate limit); `retryable` semantics live in the reason code.

Freshness: `FRESH` when collected in the current run; `STALE` when an older
value is reused past its allowed age; `UNKNOWN` when the age cannot be
established. `AVAILABLE + STALE` keeps its value but never satisfies an exact
predicate.

## Collection receipt

Every observation set carries a receipt so a consumer can tell "not
requested" from "requested but unknown" from "observed zero":

`run_id`, `collector_version`, `target`, `started_at`, `ended_at`,
`requested_keys`, `returned_keys`, `per_key` status and freshness,
`capability_notes`, `config_hash`, `request_count`.

## Aggregation rule

A Vital consumes only the observation keys named in its contract and records
each input's status and freshness in its output. A required input that is not
`AVAILABLE + FRESH` yields `UNKNOWN` or a contract-defined conservative
`DEGRADED` result. Zero, mean, last-known-good or estimated substitutions are
forbidden.

## Observation keys

Inventories (emitted by adapters):

| Key | Type | Content |
| --- | --- | --- |
| `forge.repository.metadata` | record | id, default branch, visibility, `has_issues`, archived, pushed_at |
| `git.default_branch.commits_28d` | series | `{sha, committed_at, title}` for the 28-day window; coverage `complete` |
| `forge.change_requests.inventory` | series | all open change requests plus those updated in 28 days; coverage `open_complete`, `window_complete` |
| `forge.issues.inventory` | series | all open issues plus those updated in 28 days; `UNAVAILABLE` when issues are disabled |
| `git.nondefault_branches.inventory` | series | `{name, head_sha, head_committed_at, protected}`; coverage `complete`, `heads_resolved` |
| `planning.explicit_targets.inventory` | series | milestones with state and due date; `UNAVAILABLE` when `planning.source = none` |
| `forge.releases.inventory` | series | recent published releases |
| `ci.configured` | boolean | positively observed presence or absence of verification |
| `ci.revision_verdicts_14d` | series | one canonical record per default-branch revision of the 14-day window (see [integrity-ci.md](integrity-ci.md)) |

Aggregates (derived deterministically from inventories; status follows the
relevant coverage flag):

| Key | From |
| --- | --- |
| `git.default_branch.commits.count_28d`, `git.default_branch.commit_active_days_28d` | commits |
| `forge.change_requests.open_count`, `.merged_count_28d`, `.updated_count_28d`, `.stale_open_count_14d`, `.oldest_open_age_days` (when open > 0), `.median_time_to_merge_seconds_28d` (when merged > 0; exact rational record `{"numerator": n, "denominator": d}` in seconds), `.median_time_to_merge_hours_28d` (whole-hour projection of the former, presentation only) | change requests |
| `forge.issues.open_count`, `.stale_open_count_30d`, `.updated_count_28d` | issues |
| `git.nondefault_branches.stale_count_30d` | branches (heads older than 30 days) |
| `planning.explicit_targets.capability` (`SUPPORTED`, `SUPPORTED_UNUSED`, `UNSUPPORTED`), `.open_count`, `.open_with_future_boundary_count`, `.open_beyond_28d_count`, `.nearest_future_boundary_days` | targets and configuration |
| `planning.linkage.active_change_requests_count_28d`, `.active_change_requests_linked_to_open_target_count_28d`, `.links_per_target_28d` | change requests with milestone linkage |
| `debt.registry.capability` (`CONFIGURED`, `UNCONFIGURED`), `debt.mapping`, `debt.items.open_count`, `.open_stale_count_30d`, `.closed_count_28d` | issues filtered by the configured label mapping |

Definitions: "stale" means open and not updated for the stated number of days;
"active" change requests are those updated within the 28-day frame; "linked"
means the change request carries an explicit reference to an open planning
target; merge durations are computed exactly from the timestamps (fractional
seconds of an RFC 3339 timestamp are kept as exact decimal fractions, never
rounded through binary floats), the "median" over an odd sample is the middle
duration and over an even sample the exact arithmetic mean of the two middle
durations, reduced to lowest terms (PV-FLOW-MERGE-LATENCY-001); the whole-hour
value is the floor of that median and never a classifier input.

## Conformance cases

C1 observed zero, C2 tier limitation, C3 permission denial, C4 truncated
history, C5 stale cache, C6 connector ambiguity, C7 transient failure. See
[conformance.md](conformance.md).
