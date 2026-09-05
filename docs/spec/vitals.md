# The seven Vitals (PV-VITALS-V1-002, policy devostasis.policy.v1)

## Global rules

- **G1** Missing, unavailable, forbidden, stale, partial, contradictory,
  unknown or errored evidence never becomes zero, empty, false, healthy or
  clean unless that exact state is positively observed.
- **G2** `AVAILABLE` is emitted only when every observation the matched
  predicate needs is complete and fresh. A `DEGRADED` result is a conservative
  bound and cannot improve the band relative to what unknown favourable
  evidence could prove.
- **G3** Rules are evaluated top-down inside a Vital; first match wins.
- **G4** Same normalized observations plus the same policy and configuration
  versions produce the same result, byte for byte after canonicalization.
- **G5** `UNKNOWN` in one Vital never fabricates a band in another.
- **G6** Vitals are not independent votes. Shared signals are declared through
  `shared_signal_groups` and `dependency_group_ids` and are never combined into
  an authoritative score.
- **G7** Text classification, sentiment, embeddings, language models and
  provider-specific labels have no authority unless converted upstream into
  explicit configuration or an enumerated observation with provenance.
- **G8** Adapters normalize topology but preserve unsupported capabilities as
  explicit availability states.
- **G9** Numeric thresholds and windows are policy constants; this version
  freezes the V0 values and adds none.

Every Vital emits: `vital_id`, `vital_version`, `rule_id`, `band`,
`evaluation_status` (`AVAILABLE`, `DEGRADED`, `UNKNOWN`), `band_semantics`
(`EXACT`, `CONSERVATIVE_LOWER_BOUND`, `CONSERVATIVE_UPPER_BOUND`,
`NON_AUTHORITATIVE_CONSERVATIVE_SUPERSET`), `possible_bands` when degraded,
`inputs` with status and freshness, `derived` metrics actually used,
`shared_signal_groups`, `dependency_group_ids`, `diagnostics` and a
deterministic `explanation`. An `UNKNOWN` Vital has `band = null`.

## Pulse

*How intense is recent observable activity?* Not productivity; low Pulse is
not automatically unhealthy.

Required: `git.default_branch.commits.count_28d`,
`git.default_branch.commit_active_days_28d`. Optional channels:
`forge.change_requests.updated_count_28d`, `forge.issues.updated_count_28d`.

Derived: `activity_events_28d` = commits + observed channel updates;
`channel_count` = channels with positive activity.

| Band | Rule |
| --- | --- |
| SURGING | `commit_active_days_28d >= 15` or (`activity_events_28d >= 40` and `channel_count >= 2`) |
| STEADY | `commit_active_days_28d >= 3` and `activity_events_28d >= 5` |
| QUIET | `activity_events_28d > 0` |
| DORMANT | `activity_events_28d = 0` |

Degradation: a required input that is not exact yields `UNKNOWN`. An optional
channel that is not exact is never treated as zero: the band is computed from
the observed channels as a `CONSERVATIVE_LOWER_BOUND` with `possible_bands`
listing every band from that bound upward (zero observed activity therefore
degrades to `DORMANT`, not `QUIET`).

Groups: `DEFAULT_BRANCH_ACTIVITY`, `CHANGE_REQUEST_ACTIVITY`, `ISSUE_ACTIVITY`;
dependencies `FLOW_PULSE_ACTIVITY`, `DIRECTION_PULSE_ACTIVITY`.

## Flow

*What is the state and friction of the change-request queue?* `NO_QUEUE` is
descriptive, never positive.

Required: `forge.change_requests.open_count`, `.merged_count_28d`; conditional
`.oldest_open_age_days` when open > 0 and `.median_time_to_merge_hours_28d`
when merged > 0. Any applicable input that is not exact yields `UNKNOWN`.

| Band | Rule |
| --- | --- |
| GRIDLOCKED | (`open >= 3` and `oldest >= 30` days and `merged_28d = 0`) or (`open >= 10` and `median > 336` h) |
| CONGESTED | `oldest >= 14` days or `open >= 10` or `median > 168` h |
| MOVING | `open > 0` |
| NO_QUEUE | `open = 0` |

The rules are applied literally; an empty queue with a slow recent median is
`CONGESTED` and carries the diagnostic `FLOW_MEDIAN_WITH_EMPTY_QUEUE`
(calibration finding, see ROADMAP).

Groups: `CHANGE_REQUEST_INVENTORY`, `CHANGE_REQUEST_ACTIVITY`; dependencies
`CLUTTER_FLOW_FORGE`, `FLOW_PULSE_ACTIVITY`.

## Integrity

*What does automated verification say about recent immutable revisions?*
Inputs and revision semantics are in [integrity-ci.md](integrity-ci.md).
Derived: `decisive_count_14d`, `failed_count_14d`, `failure_ratio_14d`
(exact rational), the latest revision's current verdict.

| Band | Rule |
| --- | --- |
| UNINSTRUMENTED | CI positively observed as not configured and no verification evidence |
| NO_RECENT_RUNS | CI configured, no revision in the window has a verification execution |
| NO_DECISIVE_RUNS | executions exist but no revision contributes a decisive verdict |
| FAILING | latest decisive verdict is `VERIFY_FAIL`, or `decisive >= 4` and `failed / decisive >= 1/4` |
| FLAKY | `decisive >= 4` and `0 < failed / decisive < 1/4` |
| CLEAN | `decisive >= 4`, `failed = 0`, latest decisive verdict `VERIFY_PASS` |
| SPARSE_MIXED | `1 <= decisive <= 3` with at least one failure |
| SPARSE | `1 <= decisive <= 3` with no failure |

Degradation: a `PARTIAL` revision series, or a latest revision whose
verification is still unresolved, yields `DEGRADED` with a
`NON_AUTHORITATIVE_CONSERVATIVE_SUPERSET` that always includes `FAILING`.
When the latest revision has no decisive verdict (skipped or cancelled), the
latest decisive revision is used and diagnosed.

Groups: `CI_VERIFICATION`; dependency `INTEGRITY_ONLY`.

## Clutter

*How much unresolved stale residue is observable?* Attention burden, not
value.

Inputs: `forge.issues.open_count`, `.stale_open_count_30d`,
`forge.change_requests.open_count`, `.stale_open_count_14d`,
`git.nondefault_branches.stale_count_30d`. Change-request inventory is
required; the issue and branch components may be explicitly `UNAVAILABLE`.

Derived: `tracked_open_count`, `stale_work_count`, `stale_work_ratio` (when
tracked > 0), `stale_branch_count`.

| Band | Rule |
| --- | --- |
| HEAVY | `stale_work >= 25`, or `ratio >= 1/2` with `tracked >= 4`, or `stale_branches >= 20` |
| CLUTTERED | `stale_work >= 5`, or `ratio >= 1/4` with `tracked >= 4`, or `stale_branches >= 6` |
| LIGHT | `stale_work > 0` or `stale_branches > 0` |
| CLEAN | everything observable is zero |

Degradation: an explicitly `UNAVAILABLE` component is excluded and the result
is a `CONSERVATIVE_LOWER_BOUND`; exact `CLEAN` is impossible when a component
could not be enumerated. A `PARTIAL`, `FORBIDDEN`, `UNKNOWN` or `ERROR`
component yields `UNKNOWN`.

Groups: `FORGE_INVENTORY`, `BRANCH_RESIDUE`; dependency `CLUTTER_FLOW_FORGE`.

## Horizon

*Is future work explicitly declared, and does any declaration reach beyond
the 28-day frame?* Forward visibility, not roadmap quality.

Inputs: `planning.explicit_targets.capability`, `.open_count`,
`.open_with_future_boundary_count`, `.open_beyond_28d_count`,
`.nearest_future_boundary_days`.

| Band | Rule |
| --- | --- |
| EXTENDED | `open_beyond_28d > 0` |
| VISIBLE | `open_with_future_boundary > 0` |
| DECLARED | `open > 0` |
| UNDECLARED | `open = 0`, including capability `UNSUPPORTED` or `SUPPORTED_UNUSED` |

`EXTENDED` is not better than `VISIBLE`. Creating empty milestones improves
Horizon; that is why Horizon exposes counts and never contributes to a score.

Groups: `PLANNING_TARGETS`; dependency `HORIZON_DIRECTION_PLANNING`.

## Direction

*Is active change work explicitly traceable to declared targets?* Linkage
must be explicit and auditable (milestone on the change request); keyword,
branch-name or model heuristics are forbidden.

Inputs: `planning.linkage.active_change_requests_count_28d`,
`.active_change_requests_linked_to_open_target_count_28d`,
`planning.explicit_targets.capability`, `.links_per_target_28d`.

| Band | Rule |
| --- | --- |
| NO_ACTIVE_CHANGE | `active = 0` |
| UNDECLARED | `active > 0` and planning capability positively absent (`UNSUPPORTED`, `SUPPORTED_UNUSED`) |
| SCATTERED | `unlinked > linked` |
| MIXED | `unlinked > 0` and `unlinked <= linked` |
| FULLY_LINKED | `unlinked = 0` |

`FULLY_LINKED` is neutral exact traceability. It is never rendered as
ALIGNED, ON_TRACK or HEALTHY. Mass-linking every change to one target yields
`FULLY_LINKED` truthfully, with the diagnostic `ALL_LINKS_TO_SINGLE_TARGET`.

Groups: `PLANNING_TARGETS`, `CHANGE_REQUEST_ACTIVITY`; dependencies
`HORIZON_DIRECTION_PLANNING`, `DIRECTION_PULSE_ACTIVITY`.

## Debt

*How much explicitly registered maintenance obligation is unresolved?* Debt
exists only through an explicit, versioned mapping (issue labels in this
version). Age, TODO comments, lint output and prose never count.

Inputs: `debt.registry.capability`, `debt.mapping`, `debt.items.open_count`,
`.open_stale_count_30d`, `.closed_count_28d`.

| Band | Rule |
| --- | --- |
| UNINSTRUMENTED | no mapping configured |
| PRESENT | `open > 0` with complete configured coverage |
| CLEAR | `open = 0` with complete configured coverage |

No universal quantitative thresholds exist for Debt: the retired
`ACCUMULATED` band is never emitted. Configured debt evidence that is
forbidden, unknown, errored, stale or partial yields `UNKNOWN`, never `CLEAR`;
a partial register with at least one observed item yields `DEGRADED PRESENT`.
A change of `mapping_version` makes history `INCOMPARABLE`.

Groups: `EXPLICIT_DEBT_REGISTER`, `FORGE_INVENTORY`; dependency
`DEBT_CLUTTER_MAINTENANCE`.

## Cross-Vital contract

Known correlations are metadata, not defects: Horizon and Direction share
planning targets; Clutter and Flow share change-request inventory; Clutter
and Debt may share issue inventory; Direction, Flow and Pulse share
change-request activity. Consumers must not count seven bands as seven
independent confirmations. No band ordering is declared in this version, so
comparisons report `CHANGED` rather than improved or worsened.

## Policy constants

| Constant | Value |
| --- | --- |
| Activity and planning window | 28 days |
| Integrity revision window | 14 days |
| Stale issue / stale change request / stale branch | 30 / 14 / 30 days |
| Integrity established sample | 4 decisive revisions |
| Integrity failing ratio | 1/4 |
| Pulse surging | 15 active days, or 40 events on 2 channels |
| Pulse steady | 3 active days and 5 events |
| Flow congested | 14 days, 10 open, 168 hours |
| Flow gridlocked | 3 open for 30 days with 0 merged, or 10 open with median over 336 hours |
| Clutter heavy / cluttered | 25 / 5 stale items, ratio 1/2 / 1/4 with 4 tracked, 20 / 6 stale branches |
