# Devostasis

**Deterministic, model-free vital signs for software repositories.**

Devostasis reads a repository through its forge API and reports seven named
states, the *Vitals*: **Pulse**, **Flow**, **Integrity**, **Clutter**,
**Horizon**, **Direction** and **Debt**. Every run produces an immutable,
verifiable bundle with the current state, a deterministic comparison against
the previous run and a plain-language report. No language model is involved at
any point, there is no health score, and evidence that could not be collected
never makes a project look healthier.

The name is *development* plus *homeostasis*: the goal is a stable, honest
reading of where a project actually stands, so that people and autonomous
development systems can react to it.

## Why this exists

Repository dashboards usually fail in one of four ways:

1. **They collapse everything into one number.** A green badge hides a red
   workflow; a "health 82" hides which of five different questions is bad.
2. **They treat missing data as zero.** A denied API call becomes "no branch
   protection"; a disabled issue tracker becomes "no backlog"; a rate-limited
   query becomes "no activity".
3. **They can be gamed by noise.** Retrying CI until it passes erases a real
   failure; closing valid issues improves a backlog metric; mass-linking every
   change to one milestone looks like focus.
4. **They summarise with a model** whose output changes from run to run and
   cannot be audited afterwards.

Devostasis is built against those failures:

- **Seven orthogonal questions, seven named bands.** No arithmetic ever
  combines them into an authoritative scalar. Correlations between Vitals are
  declared as metadata instead of hidden.
- **Unknown is not zero.** Every observation carries an explicit status
  (`AVAILABLE`, `PARTIAL`, `UNAVAILABLE`, `FORBIDDEN`, `UNKNOWN`, `ERROR`) and
  a freshness. A Vital without sufficient evidence says `UNKNOWN`, or emits a
  conservative `DEGRADED` bound with the set of bands still possible.
- **Same evidence, same output.** Evaluation is a pure function of the
  recorded observations and a declared policy version. Two implementations
  computing the same bundle get the same identity.
- **History is immutable and self-contained.** A bundle can be verified and
  re-rendered years later from its own files, without the original
  configuration or provider access.
- **Anti-gaming rules are part of the contract.** A revision that failed
  verification keeps its failure in the history window even if a retry later
  passes. A zero queue is not "good flow". Full milestone linkage is a fact,
  not a compliment.

## The seven Vitals

| Vital | Question it answers | Bands |
| --- | --- | --- |
| Pulse | How intense is recent observable activity? | DORMANT, QUIET, STEADY, SURGING |
| Flow | What is the state and friction of the change-request queue? | NO_QUEUE, MOVING, CONGESTED, GRIDLOCKED |
| Integrity | What does automated verification say about recent revisions? | UNINSTRUMENTED, NO_RECENT_RUNS, NO_DECISIVE_RUNS, SPARSE, SPARSE_MIXED, FLAKY, CLEAN, FAILING |
| Clutter | How much unresolved stale residue is observable? | CLEAN, LIGHT, CLUTTERED, HEAVY |
| Horizon | Is future work explicitly declared, and how far ahead? | UNDECLARED, DECLARED, VISIBLE, EXTENDED |
| Direction | Is active change work explicitly traceable to declared targets? | NO_ACTIVE_CHANGE, UNDECLARED, SCATTERED, MIXED, FULLY_LINKED |
| Debt | How much explicitly registered maintenance obligation is unresolved? | UNINSTRUMENTED, CLEAR, PRESENT |

Bands describe state, not virtue. A mature project may be temporarily
`CONGESTED`; a young project may be `CLEAN` and `UNINSTRUMENTED` at the same
time. The exact rules, windows and thresholds are in
[docs/spec/vitals.md](docs/spec/vitals.md).

Every report opens with a status card that places each band on a 0-100
gauge of the phenomenon it describes, so gradation inside a band is visible:

```text
Horizon    ████████░░    84  EXTENDED
Clutter    █░░░░░░░░░    10  LIGHT
Direction  █████░░░░░    50  MIXED
Flow       █░░░░░░░░░    10  MOVING
Integrity  ██████░░░░    62  FLAKY
Debt       █░░░░░░░░░    11  PRESENT
Pulse      ████████░░    82  SURGING
```

Gauges are a versioned normalization ([docs/spec/gauges.md](docs/spec/gauges.md))
persisted as `gauges.json`; the band stays the semantic truth, the gauge is
the position inside it, and nothing is ever summed into a health score.

## Where to focus

Every bundle also carries `demand.json`
([docs/spec/demand.md](docs/spec/demand.md)): one level per Vital from
CRITICAL, HIGH, MEDIUM, LOW, MINIMAL or UNRESOLVED, taken from a versioned
band-to-level table you can override, plus an attention order that ranks the
Vitals by level and then by their canonical order (gauges are shown but never
compared across Vitals, because they measure different phenomena). Autonomous
development systems consume it to decide what to work on; the report shows it
as the "Attention" section.
UNRESOLVED means evidence was missing and must never be read as "nothing to
do".

Horizon, Direction and Debt read explicit planning metadata only: GitHub
milestones with due dates and milestones set on pull requests, or two small
register files committed to the repository, `targets.json` and `debt.json`
([docs/spec/registers.md](docs/spec/registers.md)), with pull requests linked
to targets by a `Target: <id>` line. A repository without any of those
declares nothing and gets `UNDECLARED` or `UNINSTRUMENTED`, which is a fact
about its metadata, not about its code.

Devostasis uses the register files on itself: see
[`.devostasis/targets.json`](.devostasis/targets.json) and
[`.devostasis/debt.json`](.devostasis/debt.json), which are the worked example
to copy.

The `display` configuration chooses which Vitals appear, whether the card
shows bars, numbers or band names, and which report sections are rendered
([docs/configuration.md](docs/configuration.md)).

## What a run produces

One successful run of one project writes one immutable bundle:

| Member | Content |
| --- | --- |
| `snapshot.json` | The authoritative machine state: seven Vitals with band, evaluation status, inputs, derived metrics, diagnostics. |
| `gauges.json` | The 0-100 position of every band on the scale of its phenomenon, under a versioned normalization contract. |
| `demand.json` | One demand level per Vital and the attention order, for consumers that decide where to work. |
| `delta.json` | Deterministic comparison with the previous bundle: `BASELINE`, `COMPARABLE`, `HISTORY_GAP` or `INCOMPARABLE`, plus per-Vital transitions. |
| `activity.json` | Normalized activity since the previous successful bundle: revisions, change requests, work items, verification, releases, capability changes. |
| `observations.json` | Every raw observation with its status, coverage and evidence references, so the snapshot can be recomputed. |
| `effective-config.json` | The exact configuration that shaped the bundle, in canonical form. |
| `report.md` | A neutral, deterministic report rendered only from the files above. |
| `manifest.json` | Versions, project identity, receipts, member digests and the identity preimage from which `bundle_id` is recomputed. |

Bundles live in an append-only history store, normally a private companion
Git repository, next to a convenience `latest/` copy and a fleet overview:

```text
projects/
  README.md                          fleet overview for people
  index.json                         the same fleet as data, for machines
  github.com/<owner>/<repo>/
    latest/                          convenience copy, never authoritative
    history/YYYY/MM/DD/<bundle_id>/  immutable bundles
    index.json
```

`projects/index.json` ([docs/spec/history-and-reports.md](docs/spec/history-and-reports.md))
gives a control plane the bands, gauges and demand levels of every project
without parsing Markdown. It adds no meaning to the bundles it points at, and
it carries neither an aggregate nor a cross-project ordering: which project
comes first is the consumer's policy, and no accepted contract defines it.

## Quick start

Requires Python 3.12 or newer. The runtime uses the standard library only.

```bash
pip install git+https://github.com/drevendev/devostasis@v0.1.7
```

Observe one repository (a GitHub token is read from `DEVOSTASIS_GITHUB_TOKEN`,
`GITHUB_TOKEN`, `GH_TOKEN` or `gh auth token`; public repositories work
without one, with a low rate limit):

```bash
devostasis observe --repo owner/name --out observations.json
devostasis evaluate --observations observations.json --out snapshot.json
```

Run a fleet from a configuration file and persist bundles into a store:

```bash
devostasis run --config devostasis.json --store ./history
```

Verify any bundle from its own contents, or re-render its report:

```bash
devostasis verify --bundle history/projects/github.com/owner/name/latest
devostasis render --bundle history/projects/github.com/owner/name/latest
```

A minimal configuration:

```json
{
  "schema": "devostasis.config.v1",
  "config_version": "2026-09-05.1",
  "store": { "path": "." },
  "projects": [
    { "repo": "owner/name" },
    { "repo": "owner/other", "debt": { "labels": ["type:refactor"], "mapping_version": "1" } }
  ]
}
```

A project can also observe itself from its own GitHub Actions, with no
secret at all, and branch its next steps on the demand levels:

```yaml
jobs:
  vitals:
    uses: drevendev/devostasis/.github/workflows/observe-self.yml@v0.1.7
  decide:
    needs: vitals
    runs-on: ubuntu-latest
    steps:
      - run: echo "work on ${{ needs.vitals.outputs.attention }}"
```

See [docs/configuration.md](docs/configuration.md) for every option and
[docs/deployment.md](docs/deployment.md) for both deployment shapes: the
fleet observer with a companion history repository, and self-observation.

## Example

The fleet overview written to `projects/README.md`:

| Project | Observed at | Comparison | Pulse | Flow | Integrity | Clutter | Horizon | Direction | Debt |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| acme/widget | 2026-09-05T12:00:00Z | COMPARABLE | STEADY | MOVING | CLEAN | LIGHT | EXTENDED | MIXED | PRESENT |

A complete synthetic bundle is checked in under
[examples/sample-bundle](examples/sample-bundle); its
[report.md](examples/sample-bundle/report.md) shows what a human reads.

## Semantics worth knowing before you trust a band

- `evaluation_status` is as important as the band. `AVAILABLE` means the
  band is exact. `DEGRADED` means a conservative bound: the `possible_bands`
  list says what could still be true. `UNKNOWN` means no band at all.
- Integrity works on immutable revisions, not on runs. One revision
  contributes at most one verdict to the 14-day sample; once a revision was
  observed to fail, that failure stays in its history for the rest of the
  window even if a retry of the same revision passes.
- `NO_QUEUE` for Flow, `UNDECLARED` for Horizon and Direction, and
  `UNINSTRUMENTED` for Integrity and Debt are descriptive states, never
  healthy defaults.
- Direction `FULLY_LINKED` and Debt `PRESENT` are neutral facts. The renderer
  never relabels them as aligned, on track, healthy or unhealthy.
- Comparisons are only ever `COMPARABLE` when both bundles share the same
  contract versions and the same semantic configuration. A missing or corrupt
  previous bundle yields `HISTORY_GAP`, never "unchanged".
- Thresholds are provisional calibration constants under an explicit policy
  version. They are not tuned to make any single repository look right.

## Status

Version 0.1.0 is the minimum viable version: GitHub only, seven Vitals,
immutable bundles, filesystem history store, Markdown report. The
[ROADMAP](ROADMAP.md) lists what is deliberately deferred: a GitLab adapter,
consumer demand interfaces for autonomous development systems, additional
instruments (test state, coverage, deployments), an HTML renderer and a
calibration corpus.

## Provenance

The contracts implemented here come from an independent research process that
produced and reviewed them unit by unit before any code existed. The
specifications are reproduced in [docs/spec](docs/spec) and the mapping from
each contract to its research unit is in
[docs/spec/PROVENANCE.md](docs/spec/PROVENANCE.md). Disagreements between the
implementation and the specification are reported back to that process rather
than patched ad hoc.

## License

[MIT](LICENSE).
