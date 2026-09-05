# Changelog

All notable changes to this project are documented here. Semantic changes to a
contract or a policy always come with a version bump of that contract.

## 0.1.0 (release/0.1.0, unreleased)

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
- Immutable bundle (`devostasis.bundle.v1`): manifest, snapshot, delta,
  activity, observations, persisted effective config and a deterministic
  Markdown report; SHA-256 identity over an acyclic preimage
  (`PV-BUNDLE-ID-002`, `PV-EFFECTIVE-CONFIG-001`).
- Append-only filesystem history store with BASELINE / COMPARABLE /
  HISTORY_GAP / INCOMPARABLE comparison and a fleet overview.
- CLI: `observe`, `evaluate`, `run`, `build`, `verify`, `render`, `index`.
- 107 conformance and unit tests named after the research cases they
  implement.
- Released under the MIT license.
