# Roadmap

Version 0.1.2 closed the first round of research judgements and calibration
repairs made against real bundles. What follows is ordered by what unblocks
what, not by what is interesting.

## How this roadmap is worked

The project runs a loop, and two things sit outside it.

```text
standing obligations (interrupt anything)
        │
        ▼
Phase A  dogfood and one outside consumer
        │
        ▼
Phase B  durability and coverage the feedback justifies
        │
        ▼
Phase C  reach: other providers and instruments
        │
        └── back to A whenever a consumer or the research process
            says the base is wrong
```

**Standing obligations** are not phases and do not wait their turn:

| Obligation | Trigger | Response |
| --- | --- | --- |
| Research finding | an entry in `ANSWERS_TO_IMPLEMENTER`, an issue labelled `for:researcher`, or an accepted unit that this repository has not adopted | adopt it, or record why not, before continuing queued work |
| Calibration contradiction | a bundle that contradicts a rule on real evidence | record it under "Calibration findings" below; never change a threshold to make one repository look right |
| Consumer question | a consumer of the bundle cannot do something the contract promised | answer it before adding surface |

**Rule changes are research units, not maintenance.** A band rule, a
threshold, a window or a gauge constant changes only with named evidence,
fixtures, and an independent judgement. Making the engine's own report look
better by moving its own thresholds is the one failure the whole contract
chain exists to prevent.

**Improving a project's Vitals is a different activity from improving the
Vitals themselves.** Devostasis reporting `UNDECLARED` about itself is a true
statement about this repository's metadata; the fix belongs in this
repository, not in the rule.

## Phase A: observe ourselves honestly

Small, and it unblocks the rest.

- **A1. Devostasis declares its own plan and debt.** Add the two register
  files, point the fleet configuration and the self-observation workflow at
  them, and link pull requests to targets. This is the next task, specified
  in full below. It also gives the calibration corpus its first real evidence
  for `planning.source = file` and `debt.source = file`, which exist today
  only in synthetic fixtures.
- **A2. This repository is the first consumer.** The self-observation
  workflow already reads its own outputs, and the history store already
  consumes bundles. Whatever a stranger would trip over, we trip over first
  and fix here, where a broken contract costs one commit instead of an
  apology to another project.

Exit gate for Phase A: Devostasis's own bundle reports `DECLARED` or better
for Horizon and a real linkage share for Direction, and its own attention
order is something a consumer could act on.

## The consumer surface

Integration is deferred until this list stops moving, because an adopter who
builds on a contract we then change pays for our churn. Version 0.1.2 is the
cautionary case: `devostasis.demand.v2` removed the `attention_key` field, and
anything built on it would have broken on our release, not on theirs.

These are the only surfaces an outside consumer touches:

| Surface | Status |
| --- | --- |
| `demand.json` levels and attention order | `devostasis.demand.v2`, changed in 0.1.2 |
| `observe-self.yml` inputs and outputs | unchanged since 0.1.1 |
| `delta.json` transition classes | still moving: B5 decides whether IMPROVED and WORSENED exist |
| machine-readable fleet index | `devostasis.fleet.v1`, added in 0.1.4 |
| `snapshot.json` bands and evaluation states | stable since 0.1.0 |

"The base is implemented" is therefore an observable condition, not a feeling:
every row above is either stable or deliberately frozen for a release.

One row is still moving, and it is not ours. B5 is the research unit
PV-ORDER-001; until it reports, the surface cannot be declared frozen and B7
cannot start. Everything else the implementation owns has landed.

## Phase B: make it trustworthy over time

Ordered; each item is worth doing only because something in Phase A or a
standing obligation asked for it.

- **B1. Executable conformance vectors (PV-TEST-001).** The remaining cases
  (T2..T9, R1..R53, ART-05, ART-08..ART-11, ART-15, RPT-4..RPT-9) as
  self-contained, provider-neutral JSON fixtures under `tests/fixtures`. The
  research process authors the vectors; this repository adds the runner. The
  conformance table already names the gap, so it is visible to anyone.
- **B2. Durable history the store cannot lose.** *Delivered in 0.1.5.* A
  project is located by `project_identity.immutable_project_id`; a rename or
  transfer relocates the directory once and is recorded, and two projects are
  never merged into one directory (RPT-7). Still open from the same review:
  RPT-4..RPT-6 and RPT-9 as executable cases, including a permission-domain
  fixture for the store.
- **B3. Durable revision history across bundles (PV-HIST-001).** Integrity
  history is reconstructed from what the provider still exposes; parent-level
  surfaces cannot prove earlier failures. Persisting `revision_history_state`
  per revision across bundles closes that, with policy provenance and
  replay-or-INCOMPARABLE on semantic changes.
- **B4. Rate limits and caching.** *Delivered in 0.1.6.* Conditional requests
  with a persisted entity-tag cache, retries bounded by what the provider asks
  and by a total waiting budget, and a per-project request budget that
  truncates honestly. The receipt stopped recording the request count in the
  same change, so enabling the cache cannot move a bundle identity.
- **B5. Band ordering contract (PV-ORDER-001).** No Vital declares a
  normative ordering, so deltas never say IMPROVED or WORSENED. An
  independently accepted ordering unlocks those transition classes where they
  are meaningful, and must respect the neutrality of Direction
  `FULLY_LINKED` and Debt `PRESENT`.
- **B6. Machine-readable fleet index.** *Delivered in 0.1.4.*
  `projects/index.json` (`devostasis.fleet.v1`) carries the facts of
  `projects/README.md` as data, with no aggregate and no cross-project
  ordering, so a control plane routes attention without parsing Markdown.
- **B7. One repository that is not this one integrates self-observation.**
  Last, on purpose: B5 and B6 are the remaining changes to the consumer
  surface, so after them an adopter builds on something that will not move
  under them. A single job in one workflow, its own `GITHUB_TOKEN`, no
  secret. The point is not the number of adopters, it is the first feedback
  from a consumer who did not write the contract. Record what they could not
  do without reading `docs/spec`, and answer it before Phase C.

Exit gate for Phase B: a fleet run survives a rate-limit day, a renamed
repository keeps its history, the conformance table has no case that is named
but unimplemented, and one outside repository has produced at least one
bundle of its own and said what was unclear.

## Phase C: reach

Not before Phase B, because each item multiplies the surface that Phase B
makes trustworthy.

- **C1. GitLab adapter**: merge requests, pipelines with in-place retries,
  epics and iterations as planning targets, under the same provider-neutral
  observation keys. PV-VIT-006 and later already define the identity
  semantics.
- **C2. GitHub surfaces not collected yet**: external check apps alongside
  Actions, legacy commit statuses, branch protection and rulesets as an
  *enforcement* observation, pull request to issue to milestone linkage,
  GitHub Projects fields as planning targets.
- **C3. Instruments (PV-INSTR-001 and children)**: configurable,
  deterministic instruments separable from the seven core Vitals, sharing the
  same availability, freshness, coverage and provenance semantics: test state
  (PV-TESTSTATE-001), code coverage (PV-COV-001), deployment state
  (PV-DEPLOY-001), normalized work since the previous bundle (PV-WORK-001).
- **C4. Register generators.** Small scripts that derive `targets.json` from
  a project's own roadmap format, owned by the project, so the register never
  drifts from the roadmap.

## Presentation

- **Custom report templates.** A user-supplied template persisted in the
  bundle and hashed into its identity, so re-rendering stays reproducible;
  deferred because `display` covers selection and layout without a template
  engine.
- `report.html` as an optional canonical member (already identity-bearing:
  enabling it changes `bundle_id`; PV-REV-REPORT-001 confirmed it stays
  optional).
- Optional renderer themes (PV-RENDER-CLINICAL-001): vivid or clinical labels
  next to the canonical bands in a layer that cannot alter machine semantics.
  Needs an owner-selected vocabulary per band that respects the neutrality
  rules; the gauge contract already provides the numeric side.
- Per-Vital history views: transition timelines and observability history.
- Locales beyond English.

## Storage and governance

- Object storage and same-repository history ref backends behind the
  `HistoryStore` interface.
- Retention and compaction for convenience and derived views only; immutable
  bundles needed for audit are never destroyed (PV-REV-REPORT-001).
- Optional exclusion of `observations.json` for very active repositories.
- Publication to PyPI once the API surface is stable.
- Versioning and compatibility policy per contract identifier.

## What ends the loop

The loop is not open-ended. Two named versions end it.

**0.2 is reached when** Phase A and Phase B are closed, which includes one
consumer outside this repository depending on a bundle, and no accepted
research unit is waiting for adoption.

**1.0 is reached when** the contract identifiers have a compatibility policy,
a second provider is implemented, and the calibration corpus is large enough
that a threshold change can be argued from evidence rather than from one
repository. Only then is a new major idea a decision rather than a distraction.

## Background clock

`PV-CAL-004` measures whether the attention order of one bundle predicts where
work actually happened in the next bundles. Its evidence window starts at the
first daily bundle produced by 0.1.2, on 2026-09-06, and needs about two weeks.
Nothing waits for it; it reports when it reports.

## Task A1: Devostasis declares its own plan and debt

**Status: delivered on `release/0.1.3`.** The registers, the workflow inputs
and the documentation are in the branch. The fleet configuration lands after
the merge, because a register is read from the default branch and does not
exist until then.

**Why.** Devostasis reported `Horizon UNDECLARED`, `Direction UNDECLARED` and
`Debt UNINSTRUMENTED` about itself, and the first two entries of its own
attention order were exactly those. Every word of that was true and it was a
statement about this repository's metadata. Fixing it costs two small files
and gives three things at once: an honest self-report, the first real-world
evidence for the register contracts, and a worked example a new adopter can
copy.

**Deliverables.**

1. `devostasis/targets.json` (`devostasis.targets.v1`): one target per item
   of this roadmap that is actually in flight, with a stable id that is never
   reused, a title, `state`, and `due` only where a date is real. Suggested
   ids follow the roadmap sections (`A1`, `A2`, `B1` and so on) so the file
   and this document cannot drift apart silently.
2. `devostasis/debt.json` (`devostasis.debt.v1`): the maintenance
   obligations this repository actually carries, not features. Candidates
   visible today: the conformance table names cases that have no executable
   fixture; the adapter has no conditional requests or backoff; history is
   keyed by a mutable `owner/name` path; specification and provenance drift
   is caught only by a manual pass.
3. Fleet configuration: the `drevendev/devostasis` entry in the history
   store's `devostasis.json` gains `planning` with `source: file` and the
   register path, and `debt` with `source: file`, the register path and a
   `mapping_version`. Bump `config_version`.
4. Self-observation: `self-observe.yml` passes `planning-source`,
   `planning-path`, `debt-path` and `debt-mapping-version` so both surfaces
   read the same metadata and cannot disagree.
5. Contribution rule: a pull request that advances a target carries a
   `Target: <id>` line in its description. Document it in `CONTRIBUTING.md`;
   it is the only linkage the engine accepts, by design.
6. Documentation: `docs/deployment.md` points at these two files as the
   worked example, replacing the fictional one where it helps.

**Measured effect**, checked against the register content rather than assumed
(`tests/test_own_registers.py`): Horizon becomes `DECLARED` with ten open
targets; Debt becomes `PRESENT` with five open items and none stale;
Direction follows the pull requests, `NO_ACTIVE_CHANGE` with none open,
`FULLY_LINKED` when every active one carries a marker, `MIXED` when some do
not. Horizon stops at `DECLARED` rather than `VISIBLE` because no target
carries a `due` date, and none does because none of the dates would be real.

**Known and intended side effects.** Changing `planning` and `debt` changes
the semantic configuration, so the first bundle after the fleet adopts the
registers is `INCOMPARABLE` with the previous one for this project. Until the
registers reach the default branch, both are `UNAVAILABLE /
REGISTER_NOT_FOUND` and Horizon, Direction and Debt are `UNKNOWN`: the
contract fails closed instead of guessing, and a self-observation run on the
branch shows that honestly.

**Not in this task.** No rule, threshold, window or gauge changes. If the
register evidence contradicts a rule, that is a calibration finding for the
research process, recorded below.

**After A1.** B1's fixture runner and B2 and B4 are unblocked and entirely
ours; B4 pays down debt item D-2 and B2 pays down D-3. B1's vectors depend on
the research process, which has PV-TEST-001 queued behind its own calibration
unit.

## Calibration findings from the real runs

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

Open for judgement, introduced by the implementation in 0.1.2:

8. **Per-Vital rule version boundary.** A Vital whose `rule_id` changed since
   the previous bundle is `INCOMPARABLE` on its own
   (`RULE_VERSION_BOUNDARY`) while the bundle stays `COMPARABLE`. No research
   unit defined this; it was chosen so a rule repair never reinterprets a
   historical band. Submitted for judgement.

Found by dogfooding in 0.1.5, in the accepted V1 Direction rule:

9. **Closing a delivered target un-links the work that delivered it.**
   Direction counts active change requests linked to an **open** target, so
   the moment a target is completed and closed, every pull request that
   delivered it becomes unlinked while it is still inside the 28-day active
   window. Measured on this repository: with targets A1 and B6 open, two of
   six active change requests were linked; closing both on delivery took the
   linked count to zero and left the band `SCATTERED` on 0 of 3.
   The incentive this creates is the wrong way round: never closing a target
   keeps Direction high, and finishing work lowers it. The rule is not wrong
   about the present moment, since work on a finished target is genuinely not
   traceable to anything open, but the effect deserves a decision rather than
   an accident. Candidate readings for the research process: a change request
   linked to a target that was open *when the change request was last active*
   stays linked; or the window for linkage follows the target's closing date;
   or the current behaviour is confirmed and the anti-gaming note is amended
   to say that Direction is a statement about work in flight only.

New findings from later fleet runs are appended here as they appear.
