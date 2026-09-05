# History, comparison and reports (PV-REPORT-001 subset)

## Comparison states

| State | When |
| --- | --- |
| `BASELINE` | no canonical bundle exists yet for the project |
| `COMPARABLE` | the latest bundle loads, verifies, and shares `vitals_contract_version`, `observation_contract_version`, `policy_version` and the semantic configuration (planning source, debt mapping) |
| `HISTORY_GAP` | history is known to exist but the latest bundle cannot be loaded or verified |
| `INCOMPARABLE` | the latest bundle was produced under different semantics |

A current snapshot is always produced when current evidence is sufficient.
`HISTORY_GAP` and `INCOMPARABLE` never emit `UNCHANGED`; missing prior values
are never substituted by current values or zero.

## Delta

Per Vital: `previous_band`, `current_band`, evaluation statuses,
`transition_class`, `metric_deltas` (integers and ratio records only),
`coverage_delta` (inputs whose status or freshness changed), `reason_codes`.

Transition classes: `BASELINE`, `UNCHANGED`, `CHANGED`,
`OBSERVABILITY_GAINED`, `OBSERVABILITY_LOST`, `INCOMPARABLE`. `IMPROVED` and
`WORSENED` are reserved for Vitals with an accepted normative band ordering;
none exists in this version.

## Activity interval

The interval is `(previous.observed_at, current.observed_at]`, never a blind
24 hours: a missed day is covered by the next run. A `BASELINE` bundle reports
the trailing 28-day observation window and says so in `interval.basis`.

Activity classes: `REVISION` (default-branch commits), `CHANGE_REQUEST`
(opened, merged, closed), `WORK_ITEM` (opened, closed), `VERIFICATION`
(revisions verified, failed, unresolved), `RELEASE`, `CAPABILITY_CHANGE`
(observation statuses that differ from the previous receipt). Lists are
ordered by timestamp and identifier and capped by `activity.list_cap`;
truncation is explicit. Titles are reproduced as source facts and never
interpreted.

## History store

Layout of the filesystem store, intended to be a companion Git repository
committed by the scheduler:

```text
projects/README.md                               fleet overview (convenience)
projects/<forge>/<owner>/<repo>/latest/          copy of the newest bundle
projects/<forge>/<owner>/<repo>/history/YYYY/MM/DD/<bundle_id>/
projects/<forge>/<owner>/<repo>/index.json       chronological index with bands
```

Rules: history directories are append-only and never overwritten (an
identical re-put is idempotent, a different one is an `ImmutabilityError`);
`latest` is a convenience pointer, never authoritative; storage activity is
never observed as project activity because the store is not a target; a store
must not be more permissive than its sources. Rename continuity by immutable
project id is on the roadmap (`project_identity.immutable_project_id` is
already recorded).

## Report rendering (devostasis.render.v1)

`report.md` is generated only from the machine bundle, in this order:
identity and comparison header; the seven Vitals in canonical order with
band, evaluation, semantics and explanation; per-Vital metrics and
diagnostics; observability (non-available observations, capability notes);
changes since the previous bundle; activity; provenance.

Renderer rules: no numeric bars or 0-100 values; no colours or icons that
imply ordering; no evaluative aliases for neutral bands; `UNKNOWN` and
`DEGRADED` are always visible; no language model anywhere. `devostasis render`
regenerates the report from a bundle and `verify` checks that the stored
report is byte-identical.

## Conformance cases implemented

RPT-1 (ART-01) baseline without fake delta; RPT-2 interval from the previous
successful bundle; RPT-3 (ART-03) history gap; RPT-8 storage isolation by
construction; RPT-10 (ART-04) semantic incompatibility.
