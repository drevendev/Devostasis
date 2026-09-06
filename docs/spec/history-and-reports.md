# History, comparison and reports (PV-REPORT-001, accepted by PV-REV-REPORT-001)

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

Inside a `COMPARABLE` bundle, one Vital whose `rule_id` differs from the
previous bundle is `INCOMPARABLE` on its own with the reason
`RULE_VERSION_BOUNDARY:<old>-><new>` and no metric deltas: a rule repair
(for example `flow.bands.v0` to `flow.bands.v1`) never reinterprets the
historical band, and the other six Vitals keep comparing. Coverage deltas
are still reported because observability facts remain comparable.

## Delta

Per Vital: `previous_band`, `current_band`, evaluation statuses,
`transition_class`, `metric_deltas` (integers and rational records only),
`coverage_delta` (inputs whose status or freshness changed), `reason_codes`.

Transition classes: `BASELINE`, `UNCHANGED`, `CHANGED`,
`OBSERVABILITY_GAINED`, `OBSERVABILITY_LOST`, `INCOMPARABLE`. `IMPROVED` and
`WORSENED` are reserved for Vitals with an accepted normative band ordering;
none exists in this version (PV-ORDER-001 is the research unit that decides
it).

## Activity interval

The interval is `(previous.observed_at, current.observed_at]`, never a blind
24 hours: a missed day is covered by the next run. A `BASELINE` bundle reports
the trailing 28-day observation window and says so in `interval.basis`.

Activity classes: `REVISION` (default-branch commits), `CHANGE_REQUEST`
(opened, merged, closed), `WORK_ITEM` (opened, closed), `VERIFICATION`
(revisions verified, failed, unresolved), `RELEASE`, `CAPABILITY_CHANGE`
(observation statuses that differ from the previous receipt). This is the
GitHub implementation subset of PV-REPORT-001: `DEPLOYMENT` waits for an
adapter contract and branch changes appear as classifier diagnostics rather
than activity events. Lists are ordered by timestamp and identifier and
capped by `activity.list_cap`; truncation is explicit. Titles are reproduced
as source facts and never interpreted.

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
already recorded, the path still keys by owner and name).

Decisions taken by PV-REV-REPORT-001 on the questions the contract left open:

- **Store naming** is deployment configuration, not contract.
- **One store per permission domain.** Several projects may share a store
  only when the deployment can establish one equivalent access boundary for
  all of them; otherwise they get separate stores. A store is never more
  readable than the most private repository it observes.
- **`report.html`** is an optional canonical member controlled by the
  identity-bearing effective config, not a mandatory one.
- **Daily wall-clock time** is a deployment choice; the core is
  schedule-agnostic and the comparison interval prevents missed-day
  truncation.
- **Retention.** Immutable canonical bundles required for audit and replay
  are never destroyed; convenience, index and derived views may be compacted.
  A different durability promise needs a versioned retention contract.
- **Self-observation durability.** The self-observation workflow writes its
  bundle to an ephemeral workspace and uploads it as a CI artifact; without a
  configured `HistoryStore` this is a convenience shape whose comparison is
  `BASELINE` and whose artifact expires. It is not canonical durable history,
  and a deployment claiming durable history must persist through a store
  outside CI artifact retention ([deployment.md](../deployment.md)).

## Report rendering (devostasis.render.v4)

`report.md` is generated only from the machine bundle and the persisted
`display` configuration, in this order: identity and comparison header; a
monospace status card with gauge, value and band per Vital; the "Attention"
section of the demand interface (levels, then canonical Vital order; gauges
shown, never compared); the shown Vitals with gauge, band, evaluation,
semantics and explanation; per-Vital metrics and diagnostics; observability
(non-available observations, capability notes); changes since the previous
bundle; activity; provenance. Exact rational durations render as a decimal
with the fraction beside it; the explanation states them in whole hours,
minutes and seconds.

Renderer rules: gauges are labelled as the versioned normalization and never
enter `snapshot.json` ([gauges.md](gauges.md)); no colours or icons that
imply an ordering the contract does not declare; no evaluative aliases for
neutral bands; `UNKNOWN` and `DEGRADED` are always visible; no language model
anywhere. `devostasis render` regenerates the report from a bundle and
`verify` checks that the stored report is byte-identical for the renderer
version that produced it, replaying only from the validated stored config.

## Conformance cases implemented

RPT-1 (ART-01) baseline without fake delta; RPT-2 interval from the previous
successful bundle; RPT-3 (ART-03) history gap; RPT-8 storage isolation by
construction; RPT-10 (ART-04) semantic incompatibility; per-Vital rule
version boundary. RPT-4..RPT-7 and RPT-9 (including rename continuity keyed
by immutable id and an executable permission-domain fixture) remain open
implementation work named by PV-REV-REPORT-001.
