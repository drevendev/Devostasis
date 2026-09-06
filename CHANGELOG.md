# Changelog

All notable changes to this project are documented here. Semantic changes to a
contract or a policy always come with a version bump of that contract.

## 0.1.3 (release/0.1.3, unreleased)

Roadmap target A1: Devostasis declares its own plan and debt, so its report
about itself stops saying `UNDECLARED` and `UNINSTRUMENTED` and starts saying
something a consumer can act on. No rule, threshold, window or gauge changed.

- `.devostasis/targets.json` and `.devostasis/debt.json`: this repository's
  planning targets and registered maintenance obligations, maintained by hand
  and mirroring the phases in `ROADMAP.md`. They are also the worked example
  an adopter copies, replacing the fictional paths in the specification.
- Self-observation reads them: `self-observe.yml` passes `planning-source:
  file`, both register paths and a debt `mapping_version`, so the workflow and
  the fleet observation see the same metadata and cannot disagree.
- `CONTRIBUTING.md` documents the `Target: <id>` line that links a pull
  request to a target, the rule that a `due` date is written only when it is
  real, and the boundary between a target and a debt item.
- `docs/deployment.md` names this repository as the worked example and states
  that registers are read from the default branch, so a register on a working
  branch is `REGISTER_NOT_FOUND` until it merges.
- The reusable workflow's default `devostasis-ref` is `v0.1.2`.

This is the first real-repository evidence for `planning.source = file` and
`debt.source = file`; until now both contracts existed only in synthetic
fixtures. Devostasis's own history is `INCOMPARABLE` once when the fleet
configuration adopts the registers, because the semantic configuration
changed.

## 0.1.2 (2026-09-06)

Adopts the first round of research judgements and calibration repairs made
against real bundles (PV-REV-ARTIFACT-005, PV-REV-REPORT-001,
PV-REV-GAUGE-001, PV-ROLE-001, PV-CAL-002, PV-CAL-003 and their repair
units). No numeric threshold or window changed.

- Flow rule `flow.bands.v1`: a positively observed empty queue is `NO_QUEUE`
  regardless of the historical merge median (PV-FLOW-EMPTY-QUEUE-001); the
  classifier consumes the exact rational median merge latency in seconds,
  `forge.change_requests.median_time_to_merge_seconds_28d`, with the
  boundaries 604800 s and 1209600 s as exact conversions of 168 h and 336 h
  (PV-FLOW-MERGE-LATENCY-001); the whole-hour observation stays as a derived
  presentation projection. Fractional timestamps are handled exactly.
- Pulse rule `pulse.bands.v1`: a capped required enumeration is evaluated
  over every admissible completion of the missing tail
  (PV-PULSE-REQUIRED-LOWER-BOUND-001): one forced band, or every reachable
  band in `possible_bands`, or `UNKNOWN` when no bound is defensible.
- Delta: a Vital whose rule version changed since the previous bundle is
  `INCOMPARABLE` on its own (`RULE_VERSION_BOUNDARY`) while the bundle stays
  `COMPARABLE`; historical bands are never reinterpreted.
- Demand `devostasis.demand.v2`: the attention order is level rank, then
  canonical Vital order; the cross-Vital gauge tie-break of v1 is removed
  (ROLE-01 SAME_LEVEL_GAUGE_INVARIANCE) and `attention_key` is gone.
- Verification adopts PV-EFFECTIVE-CONFIG-AUTHORITY-001: the stored effective
  config is schema-validated fail-closed
  (`EFFECTIVE_CONFIG_SCHEMA_INVALID_OR_UNSUPPORTED`, ART-25), the canonical
  member profile is derived from it and checked against the manifest, the
  members and the identity markers (`CANONICAL_MEMBER_PROFILE_MISMATCH`,
  ART-23), and the report is replayed only from the validated stored config
  (ART-24). Bundles of both effective-config schemas (v1 history, v2) verify.
- Renderer `devostasis.render.v4`: states the v2 demand ordering and renders
  exact rational durations.
- GitHub outcome map `devostasis.ci-outcomes.github.v1` confirmed by
  PV-CAL-003 (`timed_out` is `VERIFY_FAIL`, `startup_failure` is `UNKNOWN`),
  with CI-OUTCOME-01..04 tests.
- Documentation: gauges accepted (PV-REV-GAUGE-001) and their cross-Vital
  boundary stated; reporting decisions of PV-REV-REPORT-001 (permission-domain
  stores, optional `report.html`, retention, self-observation is not durable
  history); provenance, conformance table and calibration findings updated;
  the stale gauges docstring fixed.
- Conformance tests added: FLOW-EQ-01..06, FLOW-PREC-01..09, PULSE-CAP-01..05,
  ROLE-01..04, CI-OUTCOME-01..04, ART-23..ART-25, rule version boundary,
  legacy effective-config v1 verification.

Bundle identities change for every project (new rule ids, demand v2,
renderer v4). History stays `COMPARABLE`; Flow and Pulse report
`RULE_VERSION_BOUNDARY` on the first bundle after the upgrade.

## 0.1.1 (2026-09-05)

- Self-observation: the reusable workflow `.github/workflows/observe-self.yml`
  lets any repository observe itself with its own `GITHUB_TOKEN`, upload the
  bundle as an artifact, print the status card and attention order in the job
  summary and expose `attention`, `attention-order`, `levels`, `bands`,
  `gauges`, `bundle-id` and `comparison-status` as outputs; optional read-only
  comparison against a history store.
- `devostasis run --repo owner/name` observes one repository from flags
  without a configuration file; `devostasis actions-summary` writes the job
  summary and step outputs.
- Devostasis observes itself weekly with the workflow it ships.
- No contract, policy or bundle change: bundles of 0.1.0 and 0.1.1 are
  identical for identical evidence.

## 0.1.0 (2026-09-05)

First minimum viable version: useful on real repositories today.

- Observation envelope `RAW-OBS-V0` with explicit AVAILABLE / PARTIAL /
  UNAVAILABLE / FORBIDDEN / UNKNOWN / ERROR statuses, orthogonal freshness and
  collection receipts.
- Seven deterministic Vitals under `PV-VITALS-V1-002`: Horizon, Clutter,
  Direction, Flow, Integrity, Debt and Pulse, with the V0 thresholds frozen as
  `devostasis.policy.v1`.
- Integrity implements `PV-CI-UNIT-004`: revision-level verdicts,
  provider-native parent identity (GitHub Actions run + attempt, check suite),
  greatest-attempt current state, failure-sticky history.
- Read-only GitHub adapter (REST, stdlib only) with pagination caps reported as
  PARTIAL and tier or permission failures reported as UNAVAILABLE / FORBIDDEN.
  Caps sized for very active repositories (3000 commits, 2000 change requests
  or issues, 2000 workflow runs per window); a capped newest-first enumeration
  is a lower bound, and Pulse degrades to a conservative lower bound instead
  of UNKNOWN.
- Immutable bundle (`devostasis.bundle.v1`): manifest, snapshot, delta,
  activity, observations, persisted effective config and a deterministic
  Markdown report; SHA-256 identity over an acyclic preimage
  (`PV-BUNDLE-ID-002`, `PV-EFFECTIVE-CONFIG-001`).
- Append-only filesystem history store with BASELINE / COMPARABLE /
  HISTORY_GAP / INCOMPARABLE comparison and a fleet overview.
- CLI: `observe`, `evaluate`, `run`, `build`, `verify`, `render`, `index`,
  `gauges`.
- Gauges (`devostasis.gauge.v1`): deterministic 0-100 placement of each
  band on the scale of its phenomenon, persisted as the identity-bearing
  member `gauges.json`, rendered as a status card in `report.md` and in the
  fleet overview; the band stays the semantic authority.
- Demand interface (`devostasis.demand.v1`, member `demand.json`): one level
  per Vital from a versioned, overridable band-to-level table plus an
  attention order; `UNRESOLVED` for missing evidence; no aggregate.
- Register files: planning targets from `targets.json` and debt items from
  `debt.json` committed to the observed repository, change requests linked
  to targets with a `Target: <id>` marker; label-based debt mapping kept.
- Display configuration: which Vitals, which card components (bar, number,
  band) and which report sections are rendered; part of the effective config
  and therefore of the bundle identity (renderer `devostasis.render.v3`,
  bundle `devostasis.bundle.v2`, effective config `v2`).
- `demand` CLI command; older `bundle.v1` history stays verifiable and
  comparable.
- 107 conformance and unit tests named after the research cases they
  implement.
- Released under the MIT license.
