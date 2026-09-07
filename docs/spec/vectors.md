# Executable conformance vectors (`devostasis.vectors.v1`)

A conformance case written in prose can only be checked by a person reading
both the sentence and the code. Written as a vector it is a JSON document that
states evidence and expected result, and the runner executes it. This page is
the format; `src/devostasis/vectors.py` is the runner, `devostasis vectors` the
command, and `schemas/conformance-vector.schema.json` the published schema.

The format exists before the vectors it will carry: the specification names 70
cases with no test behind them (debt D-1, target B1), and `PV-TEST-001` will
deliver them. Authored against this format they arrive executable instead of
needing translation.

## A vector file

```json
{
  "schema": "devostasis.vectors.v1",
  "notes": "what this file covers",
  "vectors": [ { "case": "ORDER-01", "title": "...", "kind": "delta",
                 "source_unit": "PV-BAND-ORDER-001",
                 "given": { }, "expect": { } } ]
}
```

`case` is the conformance case identifier, unique across the whole corpus and
never reused; `title` states the claim in one sentence; `source_unit` names the
research unit the case comes from. A file may hold any number of vectors, and
the corpus is every file under the directories the runner is given.

## Kinds

### `kind: "vital"`

Evaluates one Vital over an observation set built from raw observation
envelopes, so a vector states evidence exactly as a collector emits it
([observations.md](observations.md)). Envelope defaults: `status` is
`AVAILABLE`, `value_type` is `count`, freshness is `FRESH`. The envelope is
built through the ordinary observation contract, so evidence that violates it
(an `AVAILABLE` without a value, an unknown status) fails the vector. The
published schema declares this partial envelope as `$defs/envelope`: only
`observation_id` is required, and every key it allows is a key of the full
`RAW-OBS-V0` envelope, so a vector the runner accepts is never one the schema
beside it calls invalid.

```json
{"case": "EXAMPLE-VITAL-01", "kind": "vital",
 "title": "a fully observed inventory with one stale item is exactly LIGHT",
 "given": {"vital": "clutter", "observed_at": "2026-01-01T00:00:00Z",
           "observations": [
             {"observation_id": "forge.issues.open_count", "value": 4},
             {"observation_id": "forge.issues.stale_open_count_30d", "value": 1},
             {"observation_id": "forge.change_requests.open_count", "value": 2},
             {"observation_id": "forge.change_requests.stale_open_count_14d", "value": 0},
             {"observation_id": "git.nondefault_branches.stale_count_30d", "value": 0}]},
 "expect": {"band": "LIGHT", "evaluation_status": "AVAILABLE",
            "band_semantics": "EXACT", "possible_bands": null,
            "rule_id": "clutter.bands.v0",
            "derived": {"tracked_open_count": 6, "stale_work_count": 1},
            "diagnostics_absent": ["COMPONENT_UNAVAILABLE"],
            "explanation_contains": ["1 stale work items out of 6 tracked open items"]}}
```

`band` and `evaluation_status` are required; `band_semantics`,
`possible_bands` and `rule_id` are compared when present. `derived` is a
subset: every key it names must exist and be equal, and `derived_absent` names
keys that must not exist. `diagnostics` and `diagnostics_absent` match a
diagnostic that equals the given string or starts with it, so a case can
require `COMPONENT_UNAVAILABLE:issues:ISSUES_DISABLED` or just its prefix.
`explanation_contains` holds substrings of the deterministic explanation.

### `kind: "delta"`

Compares two snapshots given as partial Vital rows and checks transition
classes and reason codes. Only the fields the case is about are written; a row
defaults to `AVAILABLE`/`EXACT` when it names a band, to `UNKNOWN` when the
band is `null`, and to the same `rule_id` on both sides so that no rule version
boundary is invented. A case that names `rule_id` on one side only is
therefore a case about a rule version boundary; a case that is not about one
either omits it everywhere or states it on both sides. `comparison_status`
defaults to `COMPARABLE` and must be one of `BASELINE`, `COMPARABLE`,
`HISTORY_GAP` and `INCOMPARABLE`; an unrecognised one is rejected rather than
run as a comparison the case did not mean.

```json
{"case": "EXAMPLE-DELTA-01", "kind": "delta",
 "title": "a Vital with a declared order and exact evidence reports a direction",
 "given": {"comparison_status": "COMPARABLE",
           "previous": {"vitals": [{"vital_id": "clutter", "band": "CLUTTERED"}]},
           "current": {"vitals": [{"vital_id": "clutter", "band": "LIGHT"}]}},
 "expect": {"vitals": {"clutter": {
     "transition_class": "IMPROVED",
     "reason_codes": ["BAND_ORDER_APPLIED:CLEAN>LIGHT>CLUTTERED>HEAVY"],
     "reason_codes_absent": [], "metric_deltas": {}}}}}
```

`expect.vitals` is keyed by Vital; each entry requires `transition_class` and
may add `reason_codes` (prefix matching, as for diagnostics),
`reason_codes_absent`, and exact `metric_deltas` and `coverage_delta`. Vitals
the case does not name are not checked.

An accepted case often names more than one pair — *"`GRIDLOCKED → CONGESTED →
MOVING` follows the WORSENED/IMPROVED direction"* is six comparisons, and
*"every unequal Pulse band pair is CHANGED"* is twelve. Splitting such a case
across several vectors would split its identifier, so `given` may carry
`comparisons` instead of one `previous`/`current`: a list of pairs, each with
its own optional `title` and its own `expect`. The case then reports one
result, and it passes only when every pair passes.

```json
{"case": "EXAMPLE-DELTA-02", "kind": "delta",
 "title": "a case that names several pairs states them all",
 "given": {"comparisons": [
   {"title": "one rank better",
    "previous": {"vitals": [{"vital_id": "flow", "band": "CONGESTED"}]},
    "current": {"vitals": [{"vital_id": "flow", "band": "MOVING"}]},
    "expect": {"vitals": {"flow": {"transition_class": "IMPROVED"}}}},
   {"title": "and one rank worse",
    "previous": {"vitals": [{"vital_id": "flow", "band": "CONGESTED"}]},
    "current": {"vitals": [{"vital_id": "flow", "band": "GRIDLOCKED"}]},
    "expect": {"vitals": {"flow": {"transition_class": "WORSENED"}}}}]}}
```

A comparison takes the same keys as an inline `given` — `comparison_status`,
`previous_bundle_id`, `incomparable_reasons` — so one case can state pairs that
differ in more than their bands. `comparisons` replaces `previous`/`current`
rather than extending them, needs at least two entries, and leaves the vector
with no `expect` of its own; each of those is an error rather than a quietly
different run. A failure names the pair by its `title`, so a case with twelve
comparisons still says which one broke.

## Rules the runner enforces

- **It fails closed.** An unknown `kind`, an unknown key in a vector, an
  unknown comparison status, a malformed observation envelope, a missing path
  or a duplicate case id is an error. A vector that cannot run must never look like a vector that passed,
  and a case family this version cannot execute makes the suite red rather than
  silently skipped.
- **A vector states, it does not compute.** Expectations are literal values.
  Deriving an expectation from the implementation would prove only that the
  implementation equals itself.
- **Every stated expectation is checked**, and an unknown expectation key is
  rejected rather than ignored, so a typo cannot weaken a case.
- **Order is irrelevant.** Vectors run independently, in case-id order, and
  share no state.

## Running them

```bash
devostasis vectors                          # tests/vectors and examples/vectors
devostasis vectors --path path/to/vectors   # repeatable
devostasis vectors --case ORDER-07 --quiet
```

The same corpus runs inside the ordinary test suite
(`tests/conformance/test_vectors.py`), one pytest case per vector, so a
conformance case fails where every other test fails. Exit status is 1 when a
vector fails and 2 when the corpus itself cannot be loaded.

## Where the vectors live

| Directory | What it holds |
| --- | --- |
| `tests/vectors/` | the conformance corpus; every case id there is cited in [conformance.md](conformance.md) |
| `examples/vectors/` | the documented examples of this page, executed with the corpus so the format cannot drift |

`tests/test_vector_runner.py` proves the runner itself: a wrong expectation
fails, an invalid document is rejected, and the published schema agrees with
the validator.
