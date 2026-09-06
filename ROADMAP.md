# Roadmap

Version 0.1.2 closes the first round of research judgements and calibration
repairs made against real bundles. Everything below is deferred on purpose,
in rough priority order. Items carry the identifier of the research unit that
owns them when one exists.

## Next: keep the base trustworthy on real data

- **Executable conformance vectors (PV-TEST-001).** The remaining cases
  (T2..T9, R1..R53, ART-05, ART-08..ART-11, ART-15, RPT-4..RPT-9) as
  self-contained, provider-neutral JSON fixtures that the test suite executes
  from `tests/fixtures`; the research process authors them, this repository
  adds the runner.
- **Demand predictive validity (PV-CAL-004).** Does the attention order of
  bundle N predict where work happened in bundles N+1..N+k? Measured by the
  research process on the daily fleet bundles; the default table
  `devostasis-default-1` changes only on that evidence.
- **Band ordering contract (PV-ORDER-001).** No Vital declares a normative
  ordering yet, so deltas never say IMPROVED or WORSENED. An independently
  accepted ordering contract would unlock those transition classes where
  they are meaningful; it must respect the neutrality of Direction
  FULLY_LINKED and Debt PRESENT.
- **Reporting gaps returned by PV-REV-REPORT-001.** Close RPT-4..RPT-7 and
  RPT-9 as executable cases: key history by immutable project id rather than
  by owner/name directories (rename and transfer continuity), an executable
  permission-domain fixture for the store, and the remaining report cases.
- **Durable revision history across bundles (PV-HIST-001).** Today Integrity
  history is reconstructed from what the provider still exposes; parent-level
  surfaces (check suites) cannot prove earlier failures. Persisting
  `revision_history_state` per revision across bundles closes that gap, with
  policy provenance and replay-or-INCOMPARABLE on semantic changes.
- **Rate limits and caching.** ETag/conditional requests, backoff on
  `RATE_LIMITED`, and a request budget per run.

## Adapters and observation surfaces

- **GitLab adapter** (merge requests, pipelines with in-place retries, epics
  and iterations as planning targets) under the same provider-neutral
  observation keys (PV-VIT-006 and later define the identity semantics).
- **GitHub surfaces not collected yet:** external check apps alongside
  Actions, legacy commit statuses, branch protection and rulesets as an
  *enforcement* observation, pull request to issue to milestone linkage,
  GitHub Projects fields as planning targets.
- **Register generators.** Small scripts that derive `targets.json` from a
  project's own roadmap format, owned by the project, so the register never
  drifts from the roadmap.
- **Rename and transfer continuity (RPT-7):** key history by immutable
  project id rather than by owner/name directories.

## Consumers

- **Consumer demand interface, next steps.** `demand.json` is at
  `devostasis.demand.v2` (level rank, then canonical Vital order; gauges are
  never compared across Vitals). Still open: per-consumer role projections
  (SNAP's S/N/A/P stay outside this repository) and a machine-readable fleet
  index next to the Markdown overview so control planes such as Whipstack can
  route attention without parsing reports.

## Instruments (PV-INSTR-001 and children)

Configurable, deterministic instruments that are separable from the seven
core Vitals and share the same availability, freshness, coverage and
provenance semantics:

- test state (PV-TESTSTATE-001): suites, failures, skips, retries and flakes;
- code coverage (PV-COV-001): measured scope, line and branch metrics;
- deployment state (PV-DEPLOY-001): environments, last deployed revision,
  lag, rollback;
- normalized work since the previous bundle as a first-class instrument
  (PV-WORK-001).

## Presentation

- **Custom report templates.** A user-supplied template persisted in the
  bundle and hashed into its identity, so re-rendering stays reproducible;
  deferred because the `display` configuration covers selection and layout
  of the built-in report without a template engine.
- `report.html` as an optional canonical member (already identity-bearing:
  enabling it changes `bundle_id`; PV-REV-REPORT-001 confirmed it stays
  optional).
- Optional renderer themes (PV-RENDER-CLINICAL-001): vivid or clinical
  labels next to the canonical bands in a theme layer that cannot alter
  machine semantics. Needs an owner-selected vocabulary per band that
  respects the neutrality rules for Direction FULLY_LINKED and Debt PRESENT;
  the gauge contract already provides the numeric side.
- Gauge calibration: `devostasis.gauge.v1` is accepted by PV-REV-GAUGE-001
  as the versioned normalization for presentation and same-Vital ordering;
  any recalibration is a new identifier backed by fixtures.
- Per-Vital history views: transition timelines and observability history.
- Locales beyond English.

## Storage

- Object storage and same-repository history ref backends behind the
  `HistoryStore` interface.
- Retention and compaction policy for convenience and derived views only;
  immutable bundles needed for audit are never destroyed (decision of
  PV-REV-REPORT-001); optional exclusion of `observations.json` for very
  active repositories.

## Governance

- Publication to PyPI once the API surface is stable.
- Versioning and compatibility policy for each contract identifier.

## Calibration findings from the first real runs

Recorded here so they reach the research process. Dispositions after
PV-CAL-002 and PV-CAL-003 (2026-09-06):

1. **Flow with an empty queue and a slow median.** Repaired in
   `flow.bands.v1` (PV-FLOW-EMPTY-QUEUE-001): an empty queue is `NO_QUEUE`
   and the historical median is diagnosed instead of classified
   (FLOW-EQ-01..06).
2. **Pulse and bursty solo development.** Open observation: substantial work
   on two active days remains `QUIET`. PV-CAL-003 found the frozen active-day
   rule defensible and asks for contrasting fixtures before any change.
3. **Integrity with a persistently failing secondary workflow.** Confirmed as
   the evidence-faithful reading of the accepted contract; no repair.
4. **Direction when no milestone ever existed.** Confirmed:
   `SUPPORTED_UNUSED` yields `UNDECLARED`, not `SCATTERED`.
5. **`timed_out` and `startup_failure`.** Confirmed: `VERIFY_FAIL` and
   `UNKNOWN` respectively (CI-OUTCOME-01..04).
6. **Pulse on capped enumerations.** Repaired in `pulse.bands.v1`
   (PV-PULSE-REQUIRED-LOWER-BOUND-001, PULSE-CAP-01..05).
7. **Median time to merge in whole hours.** Repaired: the classifier consumes
   the exact rational median in seconds (PV-FLOW-MERGE-LATENCY-001,
   FLOW-PREC-01..09); the hour value is a presentation projection.

New findings from the 0.1.2 fleet runs are appended here as they appear.
