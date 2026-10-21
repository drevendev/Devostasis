# Executable operation conformance bridge

`devostasis.conformance-bridge.v1` is a source-checkout bridge implementing the
capabilities of `devostasis.executable-conformance-surface.v1`, accepted by
PV-REV-CONFORMANCE-SURFACE-001. Capability acceptance does not independently
accept this implementation or its exact fixture materialization. Those reviews
remain pending. Existing `devostasis.vectors.v1` files retain their meaning.

Run offline, without provider APIs, secrets or private history:

```sh
python scripts/check_conformance_surface.py
python -m pytest tests/test_conformance_surface.py
```

The closed file envelope is `schema`, `source`, `cases`. Each case has exactly
`case`, `scenario`, `given`, `checks`. The published shape is
`schemas/conformance-bridge.schema.json`; execution additionally validates
operation inputs, unique IDs across both carriers and exact recorded lineage.
The bridge and self-contained drivers are in `tests/surface_bridge.py`;
literal inputs and assertions are in `tests/fixtures/conformance-surface.json`
and `tests/fixtures/ci-revisions.json`. CI revision drivers are in
`tests/ci_surface_bridge.py`; their native input schema is
`schemas/ci-normalization.schema.json`.
No arbitrary module, executable, test-name pointer or evaluated code is admitted.

Each check contains a JSON path array and exactly one of `equals`, `not_equals`,
`contains`, `absent: true`. Equality compares canonical JSON bytes, preserving
scalar types. A positive check of an unknown path fails. Unknown operations,
fields, assertions or lineages fail; none is a passing skip. Every declared
check executes. T8 requires all five independent status/freshness substitutions;
R9 keeps both provider variants under one permanent ID. Failure output names
the permanent case and checkpoint path, including its subordinate variant.

| Scenario version | Executed boundary |
| --- | --- |
| `ci-native.v1` | GitHub native status/conclusion or GitLab native status through exact `devostasis.ci-outcomes.github.v1` / `devostasis.ci-outcomes.gitlab.v1`, then revision composition; outcome and contribution assertions run before any Vital interpretation |
| `independence.v1` | real Actions attempts → one immutable revision → governed Integrity consuming positive `ci.sample_semantics=RAW_RUNS`; history failure remains sticky and retry count cannot establish independent samples |
| `multi-vital.v1` | one explicit shared commit/change-request/issue/branch inventory graph → normal derivation → seven-Vital snapshot; dependency provenance and absent aggregate assertions inspect the same execution |
| `bundle.v1` | persisted canonical core bundle, canonical byte/digest production, member access failure, receipt binding, public-only verification, private/convenience exclusion, immutable collision |
| `vital-consumers.v1` | actual degraded Vital evaluation, gauge qualification and per-Vital delta over literal observation inputs |
| `ci-revisions.v1` | version-pinned native CI normalization → admitted observations → governed Integrity → real isolated HistoryStore → persisted bundle verification; explicit BASELINE/CONTINUE/GAP operations, literal current/history/coverage assertions |
| `history-store.v1` | real isolated FilesystemHistoryStore, idempotent put, failed commit, missing predecessor, permission-domain failure and deterministic two-writer checkpoints/retry |

Bundle/store scenarios pin `devostasis.manifest.v2`, `devostasis.bundle.v3`,
`PV-BUNDLE-ID-003` and `PV-RECEIPT-IDENTITY-003`. They do not use a compatibility
registry to verify exact source content. Changing that tuple requires a new
scenario version. Provider maps are explicit fixture discriminators; an unknown
or mixed provider/map pair is refused.

The GitLab surface is an offline parent normalizer, separate from the planned
core GitLab collector. It establishes current pipeline identity/state and
retains observed failures, without claiming favorable pipeline-history
completeness. Child-only current verification is explicitly raw/degraded;
canonical parent history remains unknown. Exact Actions/suite overlap requires
check_suite_id, and cross-id reruns require scope-bound linear proof. Neither
names nor app equality deduplicate parents. See [integrity-ci.md](integrity-ci.md).

T3 introduces the opt-in rule
`integrity.bands.v1+ci-unit-004+hist-002+independence-001`. Absent provenance
uses the exact historical rule. Positive RAW_RUNS keeps one revision contribution
and reports `sample_strength=PROVISIONAL_NONINDEPENDENT`; an AVAILABLE result is
reduced to DEGRADED. Unknown/stale/unsupported provenance yields UNKNOWN without
a band. No threshold or window changes. The rule boundary is visible to delta.

The store uses a nonblocking OS publication lock. A stale advancing writer
preserves its immutable candidate and raises `HISTORY_WRITE_CONFLICT`; it must
rebuild from latest before retrying. Identical indexed writes remain idempotent.
The RPT-9 scenario forces both readers to observe one predecessor, refuses an
overlapping lock holder, commits writer A, refuses stale writer B, inspects
latest and all immutable candidates, then rebuilds and commits B. Index access
denial remains `HISTORY_STORE_FORBIDDEN`, hence HISTORY_GAP, never BASELINE.

Sixty-three permanent IDs execute across seven scenario versions: R5–R53,
T3, T6, T8, ART-05/08/09/10/11/15 and RPT-4/5/6/8/9. This materializes the
former 62-case gap and adds an RPT-8 operation fixture. R11–R53 add 43 cases
with 84 subordinate CI variants; each variant executes all lifecycle steps.
Permanent IDs are unique across both bridge files and the legacy vector corpus.
Checks remain active under optimized Python. Expectations are literal research
obligations, not snapshots generated by the implementation under test.

B1 stays open for independent concrete-surface and whole-case exact-fixture
acceptance and separate T9 cell-key delivery. Core GitLab and external B7
evidence remain separate. This implementation does not declare those accepted.
