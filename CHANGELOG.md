# Changelog

All notable changes to this project are documented here. Semantic changes to a
contract or a policy always come with a version bump of that contract.

## 0.1.1 (release/0.1.1, unreleased)

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
