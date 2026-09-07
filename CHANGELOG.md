# Changelog

All notable changes to this project are documented here. Semantic changes to a
contract or a policy always come with a version bump of that contract.

## 0.1.8 (release/0.1.8, unreleased)

Roadmap targets B5 and B1: the first accepted band ordering, and the format
and runner that make a conformance case executable. No threshold, window or
gauge changed, and no rule was retuned.

- **Band ordering (target B5, `PV-BAND-ORDER-001`).** Three Vitals now declare
  which of two of *their own* bands is better: Clutter
  `CLEAN > LIGHT > CLUTTERED > HEAVY`, Flow `MOVING > CONGESTED > GRIDLOCKED`
  for a live queue, Integrity `CLEAN > FLAKY > FAILING` and
  `SPARSE > SPARSE_MIXED`. `delta.json` therefore emits `IMPROVED` and
  `WORSENED` where the order applies. Pulse, Horizon, Direction and Debt
  declare no order at all, and neither does `NO_QUEUE` against a live queue or
  an Integrity evidence state against a verdict: those transitions stay
  `CHANGED`. No order is declared across Vitals or across projects, and none of
  this is a step towards an aggregate.
- **A direction is only ever reported about exact measurements.** The pair must
  be `COMPARABLE`, the `rule_id` unchanged and both sides `AVAILABLE` with
  `EXACT` band semantics; a `DEGRADED` band is a bound, and a move between
  bounds is not an improvement. The rule version boundary and observability
  transitions keep precedence, and a gauge that moved inside a band is still
  `UNCHANGED`. Every row that could have been ordered but was not says why:
  `BAND_ORDER_NOT_DECLARED`, `BAND_ORDER_INCOMPARABLE` or
  `BAND_ORDER_NOT_ELIGIBLE`.
- **`devostasis.delta.v2`** carries the two new classes and names the ordering
  it applied in `band_order_contract` and `band_order_version`, so a stored
  delta says under which order its classes were decided. This is the fourth
  and, with the consumer surface now frozen, the last planned move of bundle
  identity: every row of the consumer surface in the ROADMAP is stable.
- **Executable conformance vectors (target B1).** A conformance case can now be
  written as JSON and executed: `devostasis.vectors.v1` with a `vital` kind
  that evaluates one Vital over raw observation envelopes and a `delta` kind
  that compares two snapshots, a runner, a `devostasis vectors` command and a
  published schema ([docs/spec/vectors.md](docs/spec/vectors.md)). It fails
  closed: an unknown kind, an unknown key, a malformed envelope or a duplicate
  case id is an error, never a skipped case that looks like a pass.
- **The ordering ships as fifteen vectors, not as prose.** `ORDER-01..15` live
  in `tests/vectors/band-order.json`, run inside the ordinary test suite and in
  CI through the command line, and the conformance table cites them as
  `vector:ORDER-nn`. A third drift guard now checks both directions: a citation
  without a vector fails, and a vector nobody cites fails.
- The vectors of `PV-TEST-001` are still owed by the research process. The 70
  named cases without a test remain open (debt D-1), but what was missing on
  our side is now built, so those vectors arrive executable instead of needing
  translation.
- **Bookkeeping:** the 0.1.7 section still said "unreleased" after v0.1.7 was
  tagged and released, which is the exact drift debt D-4 names.

## 0.1.7 (2026-09-06)

A review of what exists, with no new capability. Six defects found and fixed,
one open question filed, and two guards added so the same classes cannot come
back. No rule, threshold, window or gauge changed.

- **A capped release enumeration reported itself as complete.** The collector
  always emitted `AVAILABLE` with `recent_only`, so a repository with more
  than thirty releases had the newest thirty recorded as the whole truth. A
  full page is now `PARTIAL` with the cap reason, like every other
  enumeration. No band reads releases, so no band was ever wrong.
- **A `PARTIAL` release inventory left no coverage note in `activity.json`**,
  so a truncated list looked complete in the report even when the collector
  had flagged it.
- **Activity could declare an interval wider than its evidence.** The
  inventories reach back 28 days; after a longer outage the report claimed the
  whole gap and the unobserved part read as "nothing happened". It now carries
  `INTERVAL_EXCEEDS_EVIDENCE_WINDOW:evidence_from=<timestamp>`. Whether the
  collection window should widen instead is
  [issue #9](https://github.com/drevendev/Devostasis/issues/9) for the
  reporting contract.
- **A `304` answered to a request that carried no entity tag** was treated as
  a successful empty body. It is now `UNEXPECTED_NOT_MODIFIED`, an explicit
  failure, because an empty answer that nobody asked for is not evidence.
- **A cached entry whose body was null kept its tag**, so every later `304`
  read as a miss and refetched forever. Such an entry is no longer stored.
- **`all_projects` collected a `renames` list that nothing consumed.** Rename
  history stays in the project index; a fleet consumer follows
  `immutable_project_id`, which the fleet index already carries.
- **Bookkeeping:** target B4 shipped in 0.1.6 and was never closed in the
  register.
- **Two guards against specification drift** (debt D-4): the conformance table
  may not cite a test that no longer exists, the specification index must link
  every specification page, and every contract identifier the runtime writes
  into a bundle must be findable in the specification. The last one immediately
  found five member schema identifiers that were documented nowhere, now listed
  in [bundle.md](docs/spec/bundle.md).

## 0.1.6 (2026-09-06)

Roadmap target B4: spend provider quota on what actually changed, wait only
when waiting helps, and truncate honestly when a budget runs out. No rule,
threshold, window or gauge changed.

- **Conditional requests.** `--cache <dir>` keeps the entity tags of previous
  runs (`devostasis.http-cache.v1`); an unchanged answer comes back as
  `304 Not Modified`, replays the stored body, and costs a round trip but no
  rate-limit quota. A missing or corrupt cache costs requests, never
  correctness.
- **Bounded retries.** A retryable failure waits only as long as the provider
  asked, through `Retry-After` or the rate-limit reset, and only while a
  single wait and a total waiting budget allow it. A primary rate limit resets
  on the hour, so waiting it out would be a hang: that becomes an explicit
  `ERROR / RATE_LIMITED` observation and the run moves on.
- **A request budget** per project, `--request-budget <n>`, so one very active
  repository cannot starve the rest of a fleet. When it bites, a partially
  enumerated inventory is `PARTIAL` and one that never started is `UNKNOWN`,
  both with the reason `REQUEST_BUDGET_EXHAUSTED`, and the receipt carries a
  matching capability note. A short list is never reported as complete.
- **Receipt `devostasis.receipt.v2`** no longer records the request count.
  How evidence was fetched is a property of the client and its cache, not of
  the evidence, and the receipt is identity-bearing: without this change,
  turning the cache on would have silently moved every `bundle_id`. The counts
  moved to the bundle's post-identity `run_meta`, which now also carries
  `billed_requests`, `conditional_hits` and `retries`. Bundles written under
  `devostasis.receipt.v1` remain verifiable, and their identities are
  unaffected because verification uses each bundle's stored preimage.
- Debt item D-2 is closed by this change; target B2 is closed as delivered.

Bundle identities change once for identical evidence, because the receipt
shape changed. Comparability is unaffected: the receipt is not part of the
semantic configuration.

## 0.1.5 (2026-09-06)

Roadmap target B2 and conformance case RPT-7: a project is its immutable id,
not its path. No rule, threshold, window or gauge changed.

- The history store locates a project by
  `project_identity.immutable_project_id` and uses the locator only as the
  human-readable place to put it. A renamed or transferred repository is
  relocated once to its new locator instead of starting a second history, and
  the move is recorded in the project index as a `renames` entry.
- Fail closed on ambiguity: a locator already held by a different project is
  refused rather than merged, and `latest()` reports the conflict instead of
  comparing against the wrong project's history. A repository whose old name
  is immediately reused by a new repository therefore yields two separate
  histories, because the ids differ.
- An adapter that cannot prove an immutable id keeps the previous behaviour:
  the locator is the identity and a rename starts a `BASELINE`, which is more
  honest than guessing that two names are the same project.
- Bundles are unchanged, including the `project_key` each records: a bundle
  keeps the locator it was observed under, and moving the directory does not
  rewrite it. Every relocated bundle still verifies.
- Debt item D-3 is closed by this change; targets A1 and B6 are closed as
  delivered.
- New calibration finding 9 for the research process, found by dogfooding:
  closing a delivered target un-links the pull requests that delivered it,
  because Direction counts links to *open* targets only.

## 0.1.4 (2026-09-06)

Roadmap target B6: the fleet as data, not only as Markdown. No rule,
threshold, window or gauge changed.

- `projects/index.json` (`devostasis.fleet.v1`, schema
  `schemas/fleet-index.schema.json`): one entry per project with the locator,
  the immutable project id, `observed_at`, `bundle_id`, `comparison_status`,
  the project's own attention order and one row per Vital carrying band,
  evaluation status, gauge and demand level, plus relative paths to the report
  and to the immutable bundle the entry came from. Written beside
  `projects/README.md` by every fleet run and by `devostasis index`.
- The index adds no meaning: every value comes from the latest bundle, which
  stays authoritative. `aggregate` and `cross_project_order` are explicitly
  `null`, because no accepted contract says what it means for one project's
  `CRITICAL` to outrank another's; a fleet-wide priority is the consumer's
  policy.
- Entries are ordered by project key and the file carries no generation
  timestamp, so a run that changes nothing rewrites the same bytes and the
  store stays quiet in version control.
- A bundle written before the demand interface existed yields `null` levels
  and an empty attention order rather than invented ones.

This is the last change to the consumer surface that the implementation owns.
The remaining one is the band ordering contract, which decides whether
`delta.json` ever emits `IMPROVED` and `WORSENED`, and it belongs to the
research process.

## 0.1.3 (2026-09-06)

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
- The reusable workflow's default `devostasis-ref` is `v0.1.3`, so a caller
  that pins the workflow at this tag and passes no ref installs this engine
  rather than the previous one (debt item D-5). Every documented pin in the
  README and the deployment guide names the same tag, and
  `tests/test_release_pins.py` fails the build when one of them, the package
  version or the changelog section falls behind.

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
