# Verification semantics (PV-CI-UNIT-004, outcome map devostasis.ci-outcomes.github.v1)

Integrity is computed over **immutable revisions** of the default branch in
the 14-day window, never over runs. The adapter emits one canonical record per
revision in `ci.revision_verdicts_14d`; the evaluator only counts.

## Outcome normalization (PV-CI-NORM-001)

Provider conclusions map to a provider-neutral vocabulary. Unknown future
values fail closed. The GitHub map `devostasis.ci-outcomes.github.v1` was
accepted by PV-CAL-003 (CI-OUTCOME-01..04).

| Provider state | Normalized |
| --- | --- |
| not completed (queued, in progress, waiting) | `VERIFY_UNRESOLVED`, whatever conclusion is attached (CI-OUTCOME-03) |
| `success` | `VERIFY_PASS` |
| `failure` | `VERIFY_FAIL` |
| `timed_out` | `VERIFY_FAIL`: a verification attempt that exceeded its allowed time did not verify the revision (CI-OUTCOME-01) |
| `cancelled`, `neutral`, `action_required`, `stale` | `NON_VERIFY_TERMINAL` |
| `skipped` | `NOT_EXECUTED` |
| `startup_failure` | `UNKNOWN`: a provider could not start the job, which says nothing about the code; it is neither a project failure nor zero evidence (CI-OUTCOME-02) |
| `null`, anything else | `UNKNOWN` (CI-OUTCOME-04) |

## Parent identity

A **parent** is one logical verification execution of a revision. Identity
is provider-native, never heuristic:

- GitHub Actions: `workflow_run.id` plus `run_attempt`; all attempts of one
  run are one parent, and the greatest observed attempt governs its current
  state;
- generic GitHub Checks: `check_suite.id`; re-requests keep the same id, so
  earlier outcomes are not observable (`PARENT_LEVEL_ONLY` provenance).

When Actions runs exist for a revision, check suites created by Actions are
not collected again (overlap de-duplication). External check apps are only
collected when no Actions runs exist at all (see the adapter document).

## Revision verdicts

Per revision, two independent facts are recorded:

1. **Current verdict** composes the current state of every parent with the
   precedence `UNKNOWN > VERIFY_FAIL > VERIFY_UNRESOLVED > VERIFY_PASS >
   NON_VERIFY_TERMINAL > NOT_EXECUTED`. An unresolved sibling therefore blocks a
   pass but never hides an observed failure.
2. **History state** is derived from every attempt observed for the revision:
   `FAILURE_OBSERVED` if any attempt was `VERIFY_FAIL`, else
   `PASS_ONLY_OBSERVED` if any was `VERIFY_PASS`, else `NO_DECISIVE_OBSERVED`.
   `FAILURE_OBSERVED` is absorbing for the life of the revision in the window.

The **historical contribution** is `VERIFY_FAIL` for `FAILURE_OBSERVED`,
`VERIFY_PASS` for `PASS_ONLY_OBSERVED`, none otherwise. Exactly one
contribution per revision enters `decisive_count_14d` and
`failed_count_14d`; attempts are never independent samples, and retry count or
order cannot improve history (rule `ANY_FAIL_ELSE_ANY_PASS_PER_IMMUTABLE_REVISION`).

A newer revision is a distinct sample: a failed revision followed by a passing
newer revision yields one failure and one pass while both are in the window.
Integrity improves through new revisions and window expiry, never through
retries. A secondary workflow that fails on every revision therefore keeps
the band `FAILING` while another workflow passes; PV-CAL-002 confirmed this
reading against a real repository.

## Record shape

```json
{
  "revision": "<sha>",
  "committed_at": "2026-09-01T10:00:00Z",
  "parents": [
    {
      "parent_id": "github_actions:workflow_run:100",
      "kind": "github_actions_workflow_run",
      "name": "CI",
      "event": "push",
      "current_attempt": 2,
      "current_state": "VERIFY_PASS",
      "attempts_observed": [{"attempt": 1, "state": "VERIFY_FAIL"}, {"attempt": 2, "state": "VERIFY_PASS"}],
      "attempts_complete": true,
      "history_state": "FAILURE_OBSERVED",
      "url": "..."
    }
  ],
  "current_verdict": "VERIFY_PASS",
  "history_state": "FAILURE_OBSERVED",
  "historical_contribution": "VERIFY_FAIL",
  "history_provenance": "ATTEMPT_LEVEL"
}
```

## Known limitation of this version

History is reconstructed from what the provider still exposes at collection
time. Attempt-level surfaces (Actions) preserve failures; parent-level
surfaces (check suites) do not, which is diagnosed as
`HISTORY_PROVENANCE_PARENT_LEVEL_ONLY`. Persisting revision history across
bundles is on the roadmap (PV-HIST-001).

## Conformance cases implemented

R54 same-revision retry keeps historical failure; R55 retry-count invariance;
R56 newer revision is distinct; R57 order and surface invariance; the V0.7
composition precedence; CI-OUTCOME-01..04 outcome mapping; unresolved current
verification degrades instead of claiming `CLEAN`.
