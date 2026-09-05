# Roadmap

Version 0.1.0 is a deliberately small base. Everything below is deferred on
purpose, in rough priority order. Items carry the identifier of the research
unit that owns them when one exists.

## Next: make the base trustworthy on real data

- **Calibration corpus (PV-CAL-002, PV-CAL-003).** Record engine output
  against human expectation for several materially different repositories
  over several windows; every disagreement becomes a calibration finding, not
  a threshold change.
- **Full synthetic fixture suite (PV-TEST-001).** Cover the remaining
  conformance identifiers (T1..T9, R1..R53, ART-08..ART-11, RPT-4..RPT-9)
  as machine-readable vectors in `tests/fixtures`.
- **Durable revision history across bundles.** Today Integrity history is
  reconstructed from what the provider still exposes; parent-level surfaces
  (check suites) cannot prove earlier failures. Persisting
  `revision_history_state` per revision across bundles closes that gap, with
  policy provenance and replay-or-INCOMPARABLE on semantic changes.
- **Band ordering contract.** No Vital declares a normative ordering yet, so
  deltas never say IMPROVED or WORSENED. An independently accepted ordering
  contract would unlock those transition classes where they are meaningful.
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

- **Consumer demand interface (PV-ROLE-001), next steps.** The minimal
  interface ships as `demand.json`; still open: independent review of the
  default table, per-consumer role projections (SNAP's S/N/A/P stay outside
  this repository), and a machine-readable fleet index next to the Markdown
  overview so control planes such as Whipstack can route attention without
  parsing reports.

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
  enabling it changes `bundle_id`).
- Optional renderer themes (PV-RENDER-CLINICAL-001): vivid or clinical
  labels next to the canonical bands in a theme layer that cannot alter
  machine semantics. Needs an owner-selected vocabulary per band that
  respects the neutrality rules for Direction FULLY_LINKED and Debt PRESENT;
  the gauge contract already provides the numeric side.
- Gauge calibration: the `devostasis.gauge.v1` ranges and within-band
  drivers are presentation constants chosen by the implementation; the
  research process may replace them with an accepted normalization contract.
- Per-Vital history views: transition timelines and observability history.
- Locales beyond English.

## Storage

- Object storage and same-repository history ref backends behind the
  `HistoryStore` interface.
- Retention and compaction policy that never destroys the immutable bundles
  needed for audit; optional exclusion of `observations.json` for very active
  repositories.

## Governance

- Publication to PyPI once the API surface is stable.
- Versioning and compatibility policy for each contract identifier.

## Calibration findings from the first real runs

Recorded here so they reach the research process; none of them changes a rule
in this version.

1. **Flow with an empty queue and a slow median.** The literal V0 rule
   classifies `open_count = 0` with `median_time_to_merge > 168h` as
   CONGESTED. The engine follows the rule and emits the diagnostic
   `FLOW_MEDIAN_WITH_EMPTY_QUEUE`.
2. **Pulse and bursty solo development.** A repository with 17 commits and 37
   activity events on two active days is QUIET because `commit_active_days`
   is below 3. Burst-heavy workflows may deserve a separate look.
3. **Integrity with a persistently failing secondary workflow.** When one
   workflow fails on every default-branch revision while another passes, the
   revision verdict is VERIFY_FAIL and the band is FAILING. This is the
   intended reading of the contract, but the human calibration expectation for
   the same repository was GUARDED or FRAGILE.
4. **Direction when no milestone ever existed.** The implementation treats a
   repository with zero milestones ever as `SUPPORTED_UNUSED`, so Direction is
   UNDECLARED rather than SCATTERED. The contract text leaves this case open.
5. **`timed_out` is mapped to VERIFY_FAIL** and `startup_failure` to
   UNKNOWN. Both are implementation choices under
   `devostasis.ci-outcomes.github.v1` and need confirmation.
6. **Pulse on capped enumerations.** A repository with more than 3000
   default-branch commits in 28 days exceeds the commit pagination cap. The
   implementation treats the capped, newest-first count as a lower bound and
   emits `DEGRADED / CONSERVATIVE_LOWER_BOUND` with the diagnostic
   `REQUIRED_INPUT_PARTIAL` instead of `UNKNOWN`. The contract only defines
   lower bounds for optional channels; this extension needs confirmation.
7. **Median time to merge in whole hours** floors sub-hour merges to 0 for
   repositories where an autonomous loop merges within minutes. A finer unit
   or a rational value may be more informative.
