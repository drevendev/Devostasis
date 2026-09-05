# Devostasis report: acme/widget

- Observed at: 2026-09-05T12:00:00Z
- Comparison: BASELINE
- Bundle: `c6e34ba1e2e98068f8439bd61f9bbaea461e621ff3d9e3ff5bc7c8afe5834178`
- Contracts: vitals PV-VITALS-V1-002, observations RAW-OBS-V0, policy devostasis.policy.v1

```text
Horizon    ████████░░    84  EXTENDED
Clutter    █░░░░░░░░░    10  LIGHT
Direction  █████░░░░░    50  MIXED
Flow       █░░░░░░░░░    10  MOVING
Integrity  ██████░░░░    62  FLAKY
Debt       █░░░░░░░░░    11  PRESENT
Pulse      ████████░░    82  SURGING
```

Bands are the canonical states. The 0-100 gauges are presentation only (devostasis.gauge.v1): they place a band on the scale of the phenomenon it describes (activity, queue pressure, verification stability, residue, declared future work, traceability share, registered debt) and are never machine truth. UNKNOWN means evidence was insufficient; DEGRADED means a conservative bound, shown as ≥ or ~.

## Vitals

| Vital | Gauge | Band | Evaluation | Semantics | Explanation |
| --- | --- | --- | --- | --- | --- |
| Horizon | 84 | EXTENDED | AVAILABLE | EXACT | 1 open planning targets, 1 with a future boundary, 1 reaching beyond 28 days. |
| Clutter | 10 | LIGHT | AVAILABLE | EXACT | 1 stale work items out of 5 tracked open items; 1 stale non-default branches. |
| Direction | 50 | MIXED | AVAILABLE | EXACT | 5 of 10 active change requests are explicitly linked to an open planning target. |
| Flow | 10 | MOVING | AVAILABLE | EXACT | 2 open change requests; 8 merged in 28 days; oldest open for 3 days; median time to merge 20 hours. |
| Integrity | 62 | FLAKY | AVAILABLE | EXACT | 1 of 8 decisive revisions failed verification in 14 days; latest decisive verdict is VERIFY_PASS. |
| Debt | 11 | PRESENT | AVAILABLE | EXACT | 1 open registered debt items under mapping version example-1. |
| Pulse | 82 | SURGING | AVAILABLE | EXACT | 19 default-branch commits on 19 active days and 32 activity events across 3 channels in 28 days. |

### Horizon: EXTENDED

_Is future work explicitly declared, and does any declaration reach beyond 28 days?_

- Evaluation: AVAILABLE; rule `horizon.bands.v1`
- Gauge (declared future work): ████████░░ 84
- Shares signals with: HORIZON_DIRECTION_PLANNING

| Metric | Value |
| --- | --- |
| capability | SUPPORTED |
| nearest_future_boundary_days | 55 |
| open_beyond_28d_count | 1 |
| open_count | 1 |
| open_with_future_boundary_count | 1 |

### Clutter: LIGHT

_How much unresolved stale residue is observable?_

- Evaluation: AVAILABLE; rule `clutter.bands.v0`
- Gauge (stale residue): █░░░░░░░░░ 10
- Shares signals with: CLUTTER_FLOW_FORGE

| Metric | Value |
| --- | --- |
| stale_branch_count | 1 |
| stale_work_count | 1 |
| stale_work_ratio | 0.20 (1/5) |
| tracked_open_count | 5 |

### Direction: MIXED

_Is active change work explicitly traceable to declared targets?_

- Evaluation: AVAILABLE; rule `direction.bands.v1.1`
- Gauge (traceability share): █████░░░░░ 50
- Shares signals with: HORIZON_DIRECTION_PLANNING, DIRECTION_PULSE_ACTIVITY

| Metric | Value |
| --- | --- |
| active_change_count_28d | 10 |
| capability | SUPPORTED |
| linked_active_change_count_28d | 5 |
| unlinked_active_change_count_28d | 5 |

Diagnostics:
- `ALL_LINKS_TO_SINGLE_TARGET`

### Flow: MOVING

_What is the state and friction of the current change-request queue?_

- Evaluation: AVAILABLE; rule `flow.bands.v0`
- Gauge (queue pressure): █░░░░░░░░░ 10
- Shares signals with: CLUTTER_FLOW_FORGE, FLOW_PULSE_ACTIVITY

| Metric | Value |
| --- | --- |
| median_time_to_merge_hours_28d | 20 |
| merged_count_28d | 8 |
| oldest_open_age_days | 3 |
| open_count | 2 |

### Integrity: FLAKY

_What does automated verification say about recent immutable revisions?_

- Evaluation: AVAILABLE; rule `integrity.bands.v0+ci-unit-004`
- Gauge (verification stability): ██████░░░░ 62
- Shares signals with: INTEGRITY_ONLY

| Metric | Value |
| --- | --- |
| decisive_count_14d | 8 |
| failed_count_14d | 1 |
| failure_ratio_14d | 0.13 (1/8) |
| revisions_in_window | 8 |
| revisions_with_verification | 8 |

### Debt: PRESENT

_How much explicitly registered maintenance obligation is unresolved?_

- Evaluation: AVAILABLE; rule `debt.bands.v1.1`
- Gauge (registered debt): █░░░░░░░░░ 11
- Shares signals with: DEBT_CLUTTER_MAINTENANCE

| Metric | Value |
| --- | --- |
| capability | CONFIGURED |
| closed_count_28d | 1 |
| open_count | 1 |
| open_stale_count_30d | 0 |

### Pulse: SURGING

_How intense is recent observable activity?_

- Evaluation: AVAILABLE; rule `pulse.bands.v0`
- Gauge (activity intensity): ████████░░ 82
- Shares signals with: FLOW_PULSE_ACTIVITY, DIRECTION_PULSE_ACTIVITY

| Metric | Value |
| --- | --- |
| activity_events_28d | 32 |
| channel_count | 3 |
| commit_active_days_28d | 19 |
| commits_28d | 19 |

## Observability

Every requested observation was available and fresh.

Capability notes:
- `CHECKS_SURFACE_NOT_COLLECTED`
- `CI_SURFACE:GITHUB_ACTIONS_ONLY`

## Changes since previous bundle

This is the first canonical bundle for the project: there is no previous state to compare against.

## Activity

Interval over the trailing 28-day observation window (no previous bundle): (2026-08-08T12:00:00Z, 2026-09-05T12:00:00Z].

| Class | Counts |
| --- | --- |
| Revisions on default branch | 19 |
| Change requests | opened 10, merged 8, closed 0 |
| Work items | opened 2, closed 1 |
| Verification | 8 revisions verified, 1 with an observed failure, 0 unresolved |
| Releases | 1 |
| Capability changes | 0 |

Change requests:
- OPENED #31 Merged change 1 (2026-08-13T10:00:00Z)
- MERGED #31 Merged change 1 (2026-08-14T06:00:00Z)
- OPENED #32 Merged change 2 (2026-08-14T10:00:00Z)
- MERGED #32 Merged change 2 (2026-08-15T06:00:00Z)
- OPENED #33 Merged change 3 (2026-08-15T10:00:00Z)
- MERGED #33 Merged change 3 (2026-08-16T06:00:00Z)
- OPENED #34 Merged change 4 (2026-08-16T10:00:00Z)
- MERGED #34 Merged change 4 (2026-08-17T06:00:00Z)
- OPENED #35 Merged change 5 (2026-08-17T10:00:00Z)
- MERGED #35 Merged change 5 (2026-08-18T06:00:00Z)
- OPENED #36 Merged change 6 (2026-08-18T10:00:00Z)
- MERGED #36 Merged change 6 (2026-08-19T06:00:00Z)
- OPENED #37 Merged change 7 (2026-08-19T10:00:00Z)
- MERGED #37 Merged change 7 (2026-08-20T06:00:00Z)
- OPENED #38 Merged change 8 (2026-08-20T10:00:00Z)
- MERGED #38 Merged change 8 (2026-08-21T06:00:00Z)
- OPENED #40 Refactor the pricing module (2026-09-02T10:00:00Z)
- OPENED #41 Add the export button (2026-09-03T10:00:00Z)

Work items:
- OPENED #12 Replace the legacy parser (2026-08-20T10:00:00Z)
- CLOSED #11 Remove dead configuration flags (2026-08-25T10:00:00Z)
- OPENED #13 Crash on empty input (2026-09-04T10:00:00Z)

Verification findings:
- 000000000000 current VERIFY_PASS, history FAILURE_OBSERVED (2026-08-25T09:00:00Z)

Releases:
- v1.1.0 Release 1.1 (2026-08-16T10:00:00Z)

## Provenance

- Artifact contract: devostasis.bundle.v1; bundle identity: PV-BUNDLE-ID-002; renderer: devostasis.render.v2; gauges: devostasis.gauge.v1 (presentation only)
- Effective config digest: `sha256:35a43d1a9e243a617bc76aba57435486457a04c7eedd9060c9cdfab30d1f7c9b` (config version `example-1`)
- Adapters: github devostasis.github.v1
- Observations digest: `sha256:61531d2a880e51902e9d0723cc71eaeb495286ac61fe337c9f90480b31015e8e`
- Generated deterministically from the machine bundle without any language model.
