# Roadmap

Ordered by what unblocks what, not by what is interesting. Every item names
who or what blocks it, so a reader can tell the difference between work not
started and work that cannot start.

## How this roadmap is worked

```text
standing obligations (interrupt anything)
        │
        ▼
Phase A  observe ourselves honestly            closed
        │
        ▼
Phase B  durability and coverage               4 of 7 done
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
| Research finding | an entry in `ANSWERS_TO_IMPLEMENTER`, an issue labelled `for:researcher`, or an accepted unit this repository has not adopted | adopt it, or record why not, before continuing queued work |
| Calibration contradiction | a bundle that contradicts a rule on real evidence | record it under "Calibration findings"; never change a threshold to make one repository look right |
| Consumer question | a consumer cannot do something the contract promised | answer it before adding surface |

**Rule changes are research units, not maintenance.** A band rule, threshold,
window or gauge constant changes only with named evidence, fixtures and an
independent judgement. Making the engine's own report look better by moving
its own thresholds is the failure the whole contract chain exists to prevent.

**Improving a project's Vitals is a different activity from improving the
Vitals themselves.** Devostasis reporting `SCATTERED` about itself is a true
statement; the fix belongs in this repository, not in the rule.

## Who blocks what

| Item | Owner of the next step | Blocker |
| --- | --- | --- |
| B1 vectors | research process | `PV-TEST-001`, READY in their queue, not yet produced |
| B7 first outside consumer | **the owner** | picking a repository; B5 has landed, so the consumer surface no longer moves |
| B3 durable revision history | research process | `PV-HIST-001` is PENDING behind their current queue |
| C1 GitLab adapter | research process | GitLab adapter requirements not yet produced |
| C2 uncollected GitHub surfaces | this repository | each surface needs a contract decision first |
| C3 Instruments | research process | `PV-INSTR-001` and children deferred past Iteration 1 |
| C4 register generators | this repository | none; low value until a second project uses registers |
| Renderer themes | owner | needs an owner-selected vocabulary per band |
| PyPI publication | owner | needs an owner decision that the API surface is stable |
| Compatibility policy | research process and owner | no contract defines what a breaking change is |
| `PV-CAL-004` predictive validity | elapsed time | needs calendar days of bundles, not more bundles (see the self-review) |
| Judgements owed to us | research process | five open, listed below |

Five judgements the research process owes this repository, all of them about
work already shipped:

| Unit | About | State |
| --- | --- | --- |
| `PV-REV-REGISTERS-001` | whether a `Target: <id>` marker is auditable enough under G7, and whether a bulk-editable register is gameable | READY |
| `PV-REV-FLEET-001` | whether `devostasis.fleet.v1` is right to declare no cross-project ordering | PENDING |
| `PV-REV-DIRECTION-CLOSED-TARGET-001` | calibration finding 9: closing a delivered target un-links the work that delivered it | PENDING |
| `PV-SPEC-001` | the conformance review of every adoption since the specification was last reviewed, now including B5 | **due**: B5 was adopted in 0.1.8 |
| [issue #9](https://github.com/drevendev/Devostasis/issues/9) | activity declaring an interval wider than its evidence | filed, not yet indexed |

One judgement is ours to ask for rather than to wait on: `ORDER-01..15` are
this repository's enumeration of the rules the accepted ordering contract
states, so `PV-SPEC-001` reviews whether the enumeration covers the contract,
not only whether the code matches the enumeration.

## Phase A: observe ourselves honestly — closed

- **A1. Devostasis declares its own plan and debt.** Done in 0.1.3. The
  registers are `.devostasis/targets.json` and `.devostasis/debt.json`, the
  fleet and the self-observation workflow read them, and a pull request links
  to a target with a `Target: <id>` line.
- **A2. This repository is the first consumer.** Continuing, not a
  deliverable: whatever a stranger would trip over, we trip over first.

Exit gate, met: Devostasis reports `DECLARED` for Horizon and a real linkage
share for Direction, and its own attention order is actionable.

## Phase B: make it trustworthy over time

### B1. Executable conformance vectors — the format is built, the vectors are owed

The specification names **70 conformance cases with no test behind them**
(T2..T9, R1, R2, R4..R53, ART-05, ART-08..ART-11, ART-15, RPT-4..RPT-6,
RPT-9) against 79 rows that do cite one. That number has not moved, and it is
the half of B1 this repository cannot deliver: the vectors are the research
process's `PV-TEST-001`, READY but not yet produced.

The half that was ours shipped in 0.1.8: `devostasis.vectors.v1`, a runner, a
`devostasis vectors` command and a published schema
([vectors.md](docs/spec/vectors.md)). A case is a JSON document that states
evidence and expected result; the `vital` kind evaluates one Vital over raw
observation envelopes, the `delta` kind compares two snapshots. It fails
closed, so an unknown kind or a malformed vector is a red build rather than a
case that silently did not run, and `ORDER-01..15` are already carried that
way. Two more kinds are foreseeable and deliberately absent until a case needs
them: bundle-level identity cases (`ART-*`) and store cases (`RPT-4..RPT-6`,
`RPT-9`) that need a fixture store rather than a snapshot pair.

Closing B1 needs the vectors themselves. Until then debt D-1 stays open, and
the specification keeps saying that "conformance" covers about half of what it
names.

### B7. First outside repository integrates self-observation — the owner's move

Last on purpose: B5 was the final change to the consumer surface, so an
adopter after it builds on something that will not move under them. One job in
one workflow, its own `GITHUB_TOKEN`, no secret. The point is not the number
of adopters but the first feedback from a consumer who did not write the
contract. The only remaining blocker is the owner choosing a repository.

### B3. Durable revision history across bundles — blocked by research

Integrity history is reconstructed from what the provider still exposes;
parent-level surfaces cannot prove earlier failures, which is diagnosed as
`HISTORY_PROVENANCE_PARENT_LEVEL_ONLY`. Persisting `revision_history_state`
per revision across bundles closes that gap, with policy provenance and
replay-or-`INCOMPARABLE` on semantic changes. The contract is `PV-HIST-001`,
PENDING behind the research queue; building it first would repeat the mistake
the consumer-surface freeze exists to avoid.

### Also open from the reporting review

`RPT-4..RPT-6` and `RPT-9` as executable cases, including a permission-domain
fixture for the store. Ours, and covered by B1's format.

### Done

- **B5** (0.1.8): the band ordering of `PV-BAND-ORDER-001`, adopted.
  `delta.json` is `devostasis.delta.v2`, emits `IMPROVED` and `WORSENED` where
  a Vital declares an order over the pair, and names the ordering it applied.
  Every row that could have been ordered and was not says why. Ordering is per
  Vital only: Clutter `CLEAN > LIGHT > CLUTTERED > HEAVY`, Flow
  `MOVING > CONGESTED > GRIDLOCKED` for a live queue with `NO_QUEUE`
  incomparable, Integrity `CLEAN > FLAKY > FAILING` and
  `SPARSE > SPARSE_MIXED` with no order across the families or with the
  evidence states; Pulse, Horizon, Direction and Debt declare none. A direction
  needs a `COMPARABLE` pair, an unchanged `rule_id` and `AVAILABLE`/`EXACT`
  evidence on both sides; observability transitions and
  `RULE_VERSION_BOUNDARY` keep precedence and gauges establish no order.
  Conformance `ORDER-01..15`, executable. It moved bundle identity once and
  made `PV-SPEC-001` due.
- **B2** (0.1.5): a project is located by `immutable_project_id`; a rename or
  transfer relocates the directory once and is recorded, and two projects are
  never merged into one directory. Closed debt D-3.
- **B4** (0.1.6): conditional requests with a persisted entity-tag cache,
  retries bounded by what the provider asks and by a total waiting budget, and
  a per-project request budget that truncates honestly. Measured on the fleet:
  rate-limited requests fell from 248 to 66 per run. Closed debt D-2.
- **B6** (0.1.4): `projects/index.json` under `devostasis.fleet.v1`, with no
  aggregate and no cross-project ordering.

Exit gate for Phase B: a fleet run survives a rate-limit day, a renamed
repository keeps its history, the conformance table names no case that is
unimplemented, and one outside repository has produced a bundle and said what
was unclear.

## The consumer surface

Integration is deferred until this list stops moving, because an adopter who
builds on a contract we then change pays for our churn. Version 0.1.2 is the
cautionary case: `devostasis.demand.v2` removed `attention_key`, and anything
built on it would have broken on our release, not theirs.

| Surface | Status |
| --- | --- |
| `demand.json` levels and attention order | `devostasis.demand.v2`, stable since 0.1.2 |
| `observe-self.yml` inputs and outputs | stable since 0.1.1 |
| `snapshot.json` bands and evaluation states | stable since 0.1.0 |
| machine-readable fleet index | `devostasis.fleet.v1`, stable since 0.1.4 |
| `delta.json` transition classes | `devostasis.delta.v2`, stable since 0.1.8 |

No row is moving. "The base is implemented" was stated as an observable
condition rather than a feeling, and the condition is now met: the next change
to any of these surfaces is a breaking change to somebody, which is exactly
why B7 comes next and why the compatibility policy is now the gap that matters.

## Phase C: reach

Not before Phase B, because each item multiplies the surface Phase B makes
trustworthy.

- **C1. GitLab adapter** (blocked by research): merge requests, pipelines with
  in-place retries, epics and iterations as planning targets, under the same
  provider-neutral observation keys. Until it exists, provider neutrality is a
  design intent rather than a demonstrated property.
- **C2. GitHub surfaces not collected yet** (ours, each needs a contract
  decision): external check apps alongside Actions, legacy commit statuses,
  branch protection and rulesets as an *enforcement* observation, pull request
  to issue to milestone linkage, GitHub Projects fields as planning targets.
- **C3. Instruments** (blocked by research, deferred past Iteration 1):
  configurable deterministic instruments separable from the seven Vitals and
  sharing their availability, freshness, coverage and provenance semantics:
  test state (`PV-TESTSTATE-001`), coverage (`PV-COV-001`), deployment state
  (`PV-DEPLOY-001`), normalized work since the previous bundle
  (`PV-WORK-001`).
- **C4. Register generators** (ours, unblocked): scripts that derive
  `targets.json` from a project's own roadmap format, so the register never
  drifts from the roadmap. Worth little until a second project uses registers.

## Presentation

- **Custom report templates** (ours, deferred by decision): a user-supplied
  template persisted in the bundle and hashed into its identity. The `display`
  configuration covers selection and layout without a template engine.
- **`report.html`** (ours, deferred): already identity-bearing, since enabling
  it changes `bundle_id`; the reporting review confirmed it stays optional.
- **Renderer themes** (blocked by the owner): vivid or clinical labels beside
  the canonical bands, in a layer that cannot alter machine semantics
  (`PV-RENDER-CLINICAL-001`). Needs an owner-selected vocabulary per band that
  respects the neutrality of Direction `FULLY_LINKED` and Debt `PRESENT`.
- **Per-Vital history views** (ours): transition timelines and observability
  history.
- **Locales beyond English** (ours).

## Storage and governance

- Object storage and same-repository history ref backends behind the
  `HistoryStore` interface (ours).
- Retention and compaction for convenience and derived views only; immutable
  bundles needed for audit are never destroyed (decided by the reporting
  review, ours to implement).
- Optional exclusion of `observations.json` for very active repositories
  (ours).
- **Publication to PyPI** (blocked by the owner): needs a decision that the
  API surface is stable.
- **Versioning and compatibility policy per contract identifier** (blocked by
  research and the owner): the repository declares 22 contract identifiers and
  nothing states what a breaking change to one of them is, or what a consumer
  may rely on across versions.

## What ends the loop

**0.2 is reached when** Phase A and Phase B are closed, which includes one
consumer outside this repository depending on a bundle, and no accepted
research unit is waiting for adoption.

**1.0 is reached when** the contract identifiers have a compatibility policy,
a second provider is implemented, and the calibration corpus is large enough
that a threshold change can be argued from evidence rather than from one
repository.

## Background clock

`PV-CAL-004` measures whether the attention order of one bundle predicts where
work happened in the next ones. It is blocked by elapsed time, and by corpus
quality rather than corpus size: see the self-review below.

## Self-review, 2026-09-06

An honest reading of the state, including what is weaker than the numbers
suggest.

**The calibration corpus is thinner than it looks.** 218 bundles across 18
projects sounds substantial. They span **two calendar days**, and 144 of them
were produced on the second day by manual runs minutes apart while releases
were being verified. `PV-CAL-004` asks whether the attention order of bundle N
predicts activity in bundles N+1..N+k; bundles minutes apart have almost no
activity between them by construction, so they add count without adding
evidence and could make the study look ready while it holds about one day of
real signal. The study must count calendar days, not bundles, and manual
triggering should stop now that the release chain is quiet.

**Half of the named conformance surface is unproven.** 79 table rows cite a
test; 70 named cases have none. The specification says so and the roadmap
admits it, so nothing is being hidden, but "conformance" currently covers
about half of what it names. This is debt D-1 and target B1. Since 0.1.8 the
missing half is missing evidence, not missing machinery: a case can be written
as a vector and executed, and the fifteen ordering cases are carried that way.
Building the runner did not prove one of the 70, and counting it as progress on
D-1 would be counting the tooling as the test.

**Provider neutrality is a design intent, not a demonstrated property.** Every
provider-neutral contract has exactly one implemented provider. The GitLab
semantics exist in the research contracts and nothing exercises them. Until a
second adapter exists, "provider-neutral" should be read as "designed to be",
and the first GitLab implementation should be expected to find contract
defects rather than to confirm the design.

**Bundle identity moved four times in two days** (0.1.2 receipt and rule
versions, 0.1.6 receipt v2, 0.1.7 evidence shape, 0.1.8 delta v2). Every one
was justified and comparability held throughout, but for a system whose product
is durable comparable history that cadence is a cost paid by whoever reads the
store. The fourth was the last planned one: the consumer surface is now frozen,
which is the natural place to slow down, and a fifth move would need a reason
strong enough to state here.

**The engine still has one consumer, and it wrote the contracts.** This is the
largest untested assumption in the project. It is deferred deliberately rather
than forgotten, and B7 is one step away.

**What is genuinely solid.** Every contract identifier traces to a research
unit and an independent judgement, recorded in `docs/spec/PROVENANCE.md`. The
fail-closed paths are tested where they matter: a stored configuration that
does not validate stops a replay, a locator held by another project refuses a
write, a capped enumeration cannot claim completeness. All 218 bundles in the
store verify from their own contents. Two automated guards now catch the
mechanical half of specification drift, and one of them found five undocumented
identifiers on the day it was written.

## Calibration findings from the real runs

Recorded so they reach the research process. Dispositions after `PV-CAL-002`
and `PV-CAL-003` (2026-09-06):

1. **Flow with an empty queue and a slow median.** Repaired in
   `flow.bands.v1` (`PV-FLOW-EMPTY-QUEUE-001`, FLOW-EQ-01..06).
2. **Pulse and bursty solo development.** Open observation: substantial work
   on two active days remains `QUIET`. The frozen active-day rule was found
   defensible; contrasting fixtures are wanted before any change.
3. **Integrity with a persistently failing secondary workflow.** Confirmed as
   the evidence-faithful reading; no repair.
4. **Direction when no milestone ever existed.** Confirmed: `SUPPORTED_UNUSED`
   yields `UNDECLARED`, not `SCATTERED`.
5. **`timed_out` and `startup_failure`.** Confirmed as `VERIFY_FAIL` and
   `UNKNOWN` (CI-OUTCOME-01..04).
6. **Pulse on capped enumerations.** Repaired in `pulse.bands.v1`
   (`PV-PULSE-REQUIRED-LOWER-BOUND-001`, PULSE-CAP-01..05).
7. **Median time to merge in whole hours.** Repaired: the classifier consumes
   the exact rational median in seconds (`PV-FLOW-MERGE-LATENCY-001`,
   FLOW-PREC-01..09).

Judged since:

8. **Per-Vital rule version boundary.** Accepted by
   `PV-REV-RULEBOUNDARY-001`: a Vital whose `rule_id` changed is
   `INCOMPARABLE` on its own while the bundle stays `COMPARABLE`.

Open:

9. **Closing a delivered target un-links the work that delivered it.**
   Direction counts links to *open* targets, so completing a target removes
   the linkage of the pull requests that delivered it while they are still in
   the 28-day window. Measured here: closing A1 and B6 took the linked count
   from 2 of 6 to 0. Never closing a target would keep the band higher than
   finishing the work. Awaiting `PV-REV-DIRECTION-CLOSED-TARGET-001`.
10. **Activity can declare an interval wider than its evidence.** Declared
    since 0.1.7 with `INTERVAL_EXCEEDS_EVIDENCE_WINDOW`; whether collection
    should widen instead is [issue #9](https://github.com/drevendev/Devostasis/issues/9).
