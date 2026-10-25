# Release acceptance through 0.6

This is the cumulative acceptance ledger for the prepared 0.2–0.6 increments.
They remain unreleased until maintainer merges/tags under CONTRIBUTING.md.
The latest published tag observed in the October 21 audit was v0.1.9.
Implementation evidence and independent acceptance are separate gates.

The assurance increment is part of **0.6.0**, not a new release number. It
includes the October 21 readiness repairs and preserves older canonical bundles.
The pull request records final commit/run links; the commands below reproduce
the acceptance from a source checkout without network or private calibration.

## 0.2.0 — durable core history and incomplete evidence

- [x] Current malformed/duplicate revision records cannot erase carried failure
  or multiply immutable revision samples; timestamps and attempt identities are
  admitted before reconciliation. UNKNOWN attempt evidence remains unknown.
- [x] Four-generation store/evaluator chains preserve same-revision failures,
  immutable revision time, expiry and exact current/historical replay.
- [x] Horizon, Direction and Debt incomplete-evidence contracts and the accepted
  T9 generator execute; unavailable evidence cannot become favorable zero.
- [x] Core bundle verification and example builds remain deterministic.
- [ ] Independent review of the repaired #57 head and associated admission findings.
- [ ] Maintainer resolves the stacked #53 release path and publishes v0.2.0.

Evidence: `tests/test_ci_history_admission.py`, `tests/test_revision_history.py`,
`tests/conformance/`, core example
verification. The #57 fork matrix passed on Python 3.12/3.13/3.14 at `b849923`.
The broader B1/B7 milestone is still open; this ledger does not silently mark
that historical target achieved.

## 0.3.0 — Evidence to Action

- [x] Five deterministic queues, explicit priority/dependencies and bounded
  acceptance; observed exact-head evidence gates merge admission.
- [x] SARIF/JUnit/Cobertura/performance evidence retains source/revision/age gaps.
- [x] Bounded handoff, cursors, conditional reads and offline replay execute.
- [x] Missing/forbidden/stale reports cannot satisfy acceptance.
- [ ] Independent release review of #59; maintainer release merge/tag.

Evidence: `tests/test_workscope.py`,
`tests/test_work_handoff.py`, `examples/work`. The #59 fork matrix passed at
`a41fac6` on Python 3.12/3.13/3.14.

## 0.4.0 — reproducible consumer handoff

- [x] Receipt execution mechanics are outside canonical identity; semantic
  acquisition distinctions remain identity bearing.
- [x] Exact historical verification precedes compatibility dispatch. Unknown,
  mixed, ambiguous or unauthorized nonidentity edges fail closed.
- [x] Mutable branch/change bindings resolve immutable projects and commit
  membership before/after source reads; packets bind exact verified bytes.
- [x] Historical work v1 and core lineages retain their own replay paths.
- [ ] Independent review of #64 and receipt/compatibility/consumer boundaries.
- [ ] Maintainer release merge/tag.

Evidence: `tests/test_receipt_identity.py`, `tests/test_compatibility.py`,
`tests/test_work_handoff.py`, historical examples. The #64 fork matrix passed
at `c98e7ed` on Python 3.12/3.13/3.14.

## 0.5.0 — Consumer Operations

- [x] Adopter project/policy/engine bindings reject wrong subjects before
  collection or canonical publication; disabled invocations retain negative control.
- [x] Shared request/deadline budgets remain bounded under parallel collection.
- [x] Repeated generations, immutable invocation receipts and calendar-day audit
  survive private history export, verification and restore.
- [x] Packet-bound outcomes remain caller reports and grant no independent acceptance.
- [ ] Independent review of #69 and archive/caller/budget boundaries.
- [ ] Maintainer release merge/tag.

Evidence: `tests/test_work_operations.py`, `examples/work/adoption.json`,
CI archive round trip. The #69 fork matrix passed at `aa5e0e1` on
Python 3.12/3.13/3.14. Actual scheduled outside adoption (#71), collection
qualification (#62), long-term incremental archive scale (#67) and B7 remain
explicit owner/external gates.

## 0.6.0 — offline analysis and executable assurance

- [x] Pinned SHA-1/SHA-256 source/tree/blob proofs, Python 3.12 AST/import analysis,
  conservative finding comparison, SARIF and bounded verified source packets.
- [x] v2 authenticates reachable raw commits, all parent edges and historical
  tree/blob objects; roots, window selection, edit counts and COMPLETE claims
  are derived again without Git, a checkout, network or source execution.
- [x] Merge ancestry, clock skew, shallow/missing objects, graph/object/byte/work
  caps and unsafe paths retain explicit partial states; incomplete roots cannot
  establish comparable repository identity.
- [x] Rehashed root/ancestor/time/count/frontier/complete forgeries, wrong object
  kinds and unused proof objects fail. An independent LCS oracle checks the
  declared byte-line edit algorithm, including repeated/unterminated lines.
- [x] Legacy `examples/code` regenerates byte for byte. New `examples/code-v2`
  and separate schemas replay independently; cross-lineage comparison is refused.
- [x] Sixty-three permanent conformance IDs execute real native normalization,
  consumed RAW_RUNS provenance, one shared multi-Vital graph, all T8 substitutions,
  canonical bundle operations and stateful HistoryStore operations.
- [x] R11–R53 are materialized under their 43 permanent IDs, with 84 CI variants:
  native parent identities, exact overlap, proved reruns, unresolved precedence,
  commit-time order/window and failure-sticky real-store lifecycles. Raw child
  fallback and parent-level history limits remain explicit.
- [x] Governed Integrity recomputes native evidence/provenance/records and rejects
  altered bindings; unknown lineage, contradictory identity, broken pagination
  and incomplete favorable history fail closed. New behavior is opt in under
  a separate rule; old bundle examples and legacy paths retain exact replay.
- [x] HistoryStore publication is locked; a stale advancing writer preserves
  candidates, reports conflict and rebuilds from latest. Permission failures
  remain explicit HISTORY_GAP.
- [ ] Independent review of Git proof completeness, bounds and algorithm specification.
- [ ] Independent review of the concrete conformance surface and exact fixtures;
  capability-level research acceptance alone does not accept this implementation.
- [ ] Independent release/admission review of the final cumulative head, including
  the October findings on #75 and the included readiness fixes.
- [ ] Upstream workflow approval where GitHub requires maintainer authorization.
- [ ] Maintainer merges the reviewed feature into release/0.6.0, reconciles the
  cumulative #75 release PR, then merges/tags v0.6.0 under CONTRIBUTING.md.

Reproduce:

```sh
python -m pytest
devostasis vectors --quiet
python scripts/check_conformance_surface.py
devostasis verify --bundle examples/sample-bundle
python scripts/make_code_examples.py
python scripts/make_code_examples.py --v2
git diff --exit-code -- examples/code examples/code-v2
devostasis code verify --bundle examples/code/bundle
devostasis code verify --bundle examples/code-v2/bundle
devostasis code verify-packet --bundle examples/code-v2/bundle --packet examples/code-v2/packet.json
devostasis work verify --bundle examples/code-v2/work-bundle
devostasis work replay --bundle examples/code-v2/work-bundle
python -m pip wheel --no-deps .
```

CI additionally verifies both work/core examples, deterministic repeated builds
and the operations archive restore on Python 3.12/3.13/3.14. Green checks establish
those executions at the recorded head; they do not complete the unchecked gates.

The former 62-case implementation gap is materialized; B1 retains independent
concrete-surface/whole-case exact-fixture acceptance and separate T9 cell-key
delivery. B7 retains sustained
outside-consumer evidence. Legacy v1 history and omitted blob sizes keep their
documented proof limits. No compatibility migration, core GitLab collector,
threshold retuning, aggregate health score or publication is implied by this PR.
