"""INTEGRITY: automated verification stability of recent immutable revisions.

The adapter produces one canonical record per default-branch revision of the
14-day window (PV-CI-UNIT-004 semantics: one contribution per immutable
revision, failure-sticky history, current verdict independent of history).
This evaluator only counts and classifies; it never re-interprets provider
outcomes.

Rule ``integrity.bands.v1`` carries three accepted repairs on top of the V0
band table, none of which moves a threshold or a window:

* **PV-REV-INTEGRITY-UNKNOWN-001** (INT-UNKNOWN-01..06): a newest in-scope
  revision whose current verdict is ``UNKNOWN`` never inherits an older
  decisive verdict. ``UNKNOWN`` is the absence of an observation, so the Vital
  is ``UNKNOWN`` with no band; historical decisive evidence stays in
  ``derived`` and is never reconstructed as a pass. Positively observed
  ``NOT_EXECUTED`` and ``NON_VERIFY_TERMINAL`` keep the accepted fallback to
  the latest decisive revision.
* **PV-REV-TEST-003**: a required revision series with acquisition status
  ``PARTIAL`` has no accepted degraded path. It is ``UNKNOWN`` with no band;
  the counts of the truncated evidence stay visible, marked as such.
* **PV-REV-TEST-VECTORS-002** (R1, R2): one to three decisive revisions are a
  ``SPARSE`` sample, four or more an ``ESTABLISHED`` one, and
  ``CI_SPARSE_SAMPLE`` is emitted whenever the sample is sparse.

The one degraded path that remains, a newest revision still being verified,
declares a ``possible_bands`` set derived from the completions the evidence
admits (the revision passes, fails, or ends without a verdict), instead of a
fixed tail: PV-VIT-004 requires the superset to contain every band that is
provably reachable, and the previous fixed list did not.
"""

from __future__ import annotations

from typing import Any

from ..canonical import ratio
from ..observations import AVAILABLE, FRESH, PARTIAL, ObservationSet
from ..policy import INTEGRITY
from .common import (
    EVAL_AVAILABLE,
    EVAL_DEGRADED,
    EVAL_UNKNOWN,
    SEM_EXACT,
    SEM_SUPERSET,
    VitalResult,
    input_meta,
    unknown_result,
)

VITAL_ID = "integrity"
VITAL_VERSION = "PV-VITALS-V1-002/integrity"
RULE_ID = "integrity.bands.v1+ci-unit-004"
UNKNOWN_RULE = "PV-REV-INTEGRITY-UNKNOWN-001"
PARTIAL_RULE = "PV-REV-TEST-003"
SPARSE_RULE = "PV-REV-TEST-VECTORS-002"
BANDS = ["UNINSTRUMENTED", "NO_RECENT_RUNS", "NO_DECISIVE_RUNS", "SPARSE", "SPARSE_MIXED", "FLAKY", "CLEAN", "FAILING"]

CONFIGURED = "ci.configured"
REVISIONS = "ci.revision_verdicts_14d"
IDS = [CONFIGURED, REVISIONS]

SHARED = ["CI_VERIFICATION"]
GROUPS = ["INTEGRITY_ONLY"]

VERIFY_PASS = "VERIFY_PASS"
VERIFY_FAIL = "VERIFY_FAIL"
VERIFY_UNRESOLVED = "VERIFY_UNRESOLVED"
NON_VERIFY_TERMINAL = "NON_VERIFY_TERMINAL"
NOT_EXECUTED = "NOT_EXECUTED"
VERDICT_UNKNOWN = "UNKNOWN"
DECISIVE = {VERIFY_PASS, VERIFY_FAIL}

SAMPLE_SPARSE = "SPARSE"
SAMPLE_ESTABLISHED = "ESTABLISHED"
SPARSE_DIAGNOSTIC = "CI_SPARSE_SAMPLE"


def _result(
    obs: ObservationSet,
    band: str | None,
    status: str,
    semantics: str | None,
    possible: list[str] | None,
    derived: dict[str, Any],
    diagnostics: list[str],
    explanation: str,
) -> VitalResult:
    return VitalResult(
        vital_id=VITAL_ID,
        vital_version=VITAL_VERSION,
        rule_id=RULE_ID,
        band=band,
        evaluation_status=status,
        band_semantics=semantics,
        possible_bands=possible,
        inputs=input_meta(obs, IDS),
        derived=derived,
        shared_signal_groups=SHARED,
        dependency_group_ids=GROUPS,
        diagnostics=diagnostics,
        explanation=explanation,
    )


def _newest(records: list[dict[str, Any]]) -> dict[str, Any]:
    return max(records, key=lambda r: (r.get("committed_at") or "", r.get("revision") or ""))


def classify(n: int, f: int, current_reference: str | None) -> str:
    """The V0 band table over a decisive population and the verdict that speaks for the newest revision."""
    established = INTEGRITY["established_sample"]
    fail_num, fail_den = INTEGRITY["failing_ratio"]
    if n == 0:
        return "NO_DECISIVE_RUNS"
    if current_reference == VERIFY_FAIL or (n >= established and f * fail_den >= n * fail_num):
        return "FAILING"
    if n >= established and f > 0:
        return "FLAKY"
    if n >= established:
        return "CLEAN"
    if f >= 1:
        return "SPARSE_MIXED"
    return "SPARSE"


def sample_strength(n: int) -> str | None:
    """``SPARSE`` for one to three decisive revisions, ``ESTABLISHED`` from four; none without a sample."""
    if n <= 0:
        return None
    return SAMPLE_SPARSE if n < INTEGRITY["established_sample"] else SAMPLE_ESTABLISHED


def reachable_after_unresolved(n: int, f: int, fallback_verdict: str | None) -> list[str]:
    """Every band some completion of a still-verifying newest revision can reach.

    The revision can fail (the latest decisive verdict becomes a failure), pass
    (one more decisive pass, latest verdict a pass), or end without a verdict
    (the latest decisive revision speaks, or nothing does).
    """
    reached = {
        "FAILING",
        classify(n + 1, f, VERIFY_PASS),
        classify(n, f, fallback_verdict),
    }
    return [band for band in BANDS if band in reached]


def evaluate(obs: ObservationSet) -> VitalResult:
    diagnostics: list[str] = []
    configured_obs = obs.get(CONFIGURED)
    series = obs.get(REVISIONS)
    configured_known = configured_obs is not None and configured_obs.good
    configured = bool(configured_obs.value) if configured_known else None

    series_usable = (
        series is not None
        and series.status in (AVAILABLE, PARTIAL)
        and series.freshness == FRESH
        and isinstance(series.value, list)
    )
    if not series_usable:
        if configured_known and configured is False:
            return _result(
                obs,
                "UNINSTRUMENTED",
                EVAL_AVAILABLE,
                SEM_EXACT,
                None,
                {"decisive_count_14d": 0, "failed_count_14d": 0, "revisions_with_verification": 0},
                diagnostics,
                "No automated verification is configured for this repository.",
            )
        diagnostics.append(f"MISSING_REQUIRED:{REVISIONS}:{obs.status_of(REVISIONS)}/{obs.freshness_of(REVISIONS)}")
        if not configured_known:
            diagnostics.append(f"MISSING_REQUIRED:{CONFIGURED}:{obs.status_of(CONFIGURED)}/{obs.freshness_of(CONFIGURED)}")
        return unknown_result(VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS, diagnostics, SHARED, GROUPS)

    revisions: list[dict[str, Any]] = list(series.value)
    active = [r for r in revisions if r.get("parents")]
    decisive = [r for r in active if r.get("historical_contribution") in DECISIVE]
    failed = [r for r in decisive if r.get("history_state") == "FAILURE_OBSERVED"]
    n, f = len(decisive), len(failed)

    if series.status == PARTIAL:
        # PV-REV-TEST-003: a truncated required series has no accepted degraded
        # path. The counts of what was collected stay visible, marked as
        # incomplete, and no band is claimed over evidence known to be short.
        diagnostics.append(f"MISSING_REQUIRED:{REVISIONS}:{PARTIAL}/{series.freshness}")
        diagnostics.append(f"REVISION_SERIES_PARTIAL:{series.reason_code or 'INCOMPLETE'}")
        return _result(
            obs,
            None,
            EVAL_UNKNOWN,
            None,
            None,
            {
                "series_status": PARTIAL,
                "revisions_in_window": len(revisions),
                "revisions_with_verification": len(active),
                "decisive_count_14d": n,
                "failed_count_14d": f,
                "partial_series_rule": PARTIAL_RULE,
            },
            diagnostics,
            f"The revision series is incomplete ({series.reason_code or 'truncated'}); {n} decisive revisions were observed, and no band is claimed over evidence known to be short.",
        )

    if not active:
        if configured_known and configured is False:
            return _result(
                obs,
                "UNINSTRUMENTED",
                EVAL_AVAILABLE,
                SEM_EXACT,
                None,
                {"decisive_count_14d": 0, "failed_count_14d": 0, "revisions_in_window": len(revisions), "revisions_with_verification": 0},
                diagnostics,
                "No automated verification is configured and no verification evidence exists for recent revisions.",
            )
        if not configured_known:
            diagnostics.append(f"MISSING_REQUIRED:{CONFIGURED}:{obs.status_of(CONFIGURED)}/{obs.freshness_of(CONFIGURED)}")
            return unknown_result(VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS, diagnostics, SHARED, GROUPS)
        return _result(
            obs,
            "NO_RECENT_RUNS",
            EVAL_AVAILABLE,
            SEM_EXACT,
            None,
            {"decisive_count_14d": 0, "failed_count_14d": 0, "revisions_in_window": len(revisions), "revisions_with_verification": 0},
            diagnostics,
            f"Verification is configured but none of the {len(revisions)} recent default-branch revisions has a verification execution.",
        )

    if not configured_known:
        diagnostics.append("CONFIGURED_INFERRED_FROM_RUNS")

    latest = _newest(active)
    current = latest.get("current_verdict") or VERDICT_UNKNOWN

    provenance: dict[str, int] = {}
    for r in active:
        key = r.get("history_provenance") or "UNKNOWN"
        provenance[key] = provenance.get(key, 0) + 1
    if provenance.get("PARENT_LEVEL_ONLY"):
        diagnostics.append(f"HISTORY_PROVENANCE_PARENT_LEVEL_ONLY:{provenance['PARENT_LEVEL_ONLY']}")

    strength = sample_strength(n)
    if strength == SAMPLE_SPARSE:
        diagnostics.append(SPARSE_DIAGNOSTIC)

    derived: dict[str, Any] = {
        "revisions_in_window": len(revisions),
        "revisions_with_verification": len(active),
        "decisive_count_14d": n,
        "failed_count_14d": f,
        "failure_ratio_14d": ratio(f, n) if n else None,
        "current_revision": {
            "revision": latest.get("revision"),
            "committed_at": latest.get("committed_at"),
            "current_verdict": current,
            "history_state": latest.get("history_state"),
        },
        "history_provenance": dict(sorted(provenance.items())),
    }
    if strength is not None:
        derived["sample_strength"] = strength

    if current == VERDICT_UNKNOWN:
        # PV-REV-INTEGRITY-UNKNOWN-001: nobody observed what verification said
        # about the newest revision, so nothing exact can be said about the
        # current state. The decisive history above is preserved as it is.
        diagnostics.append(f"CURRENT_VERDICT_UNKNOWN:{latest.get('revision')}")
        derived["unknown_verdict_rule"] = UNKNOWN_RULE
        return _result(
            obs,
            None,
            EVAL_UNKNOWN,
            None,
            None,
            derived,
            diagnostics,
            f"The verification outcome of the newest revision is unknown; {f} of {n} decisive revisions failed in 14 days, and no current band is claimed over an unobserved verdict.",
        )

    current_reference = current
    fallback_verdict: str | None = None
    decisive_current = [r for r in active if r.get("current_verdict") in DECISIVE]
    if decisive_current:
        fallback_verdict = _newest(decisive_current).get("current_verdict")
    if current not in DECISIVE and current != VERIFY_UNRESOLVED and decisive_current:
        fallback = _newest(decisive_current)
        current_reference = fallback.get("current_verdict")
        derived["latest_decisive_revision"] = {
            "revision": fallback.get("revision"),
            "committed_at": fallback.get("committed_at"),
            "current_verdict": current_reference,
        }
        diagnostics.append(f"LATEST_REVISION_NON_DECISIVE:{current}")

    band = classify(n, f, current_reference)
    if band == "NO_DECISIVE_RUNS":
        explanation = f"{len(active)} recent revisions carry verification executions but none produced a decisive pass/fail verdict."
    elif band in ("FAILING", "FLAKY"):
        explanation = f"{f} of {n} decisive revisions failed verification in 14 days; latest decisive verdict is {current_reference}."
    elif band == "CLEAN":
        explanation = f"All {n} decisive revisions passed verification in 14 days; latest decisive verdict is {current_reference}."
    elif band == "SPARSE_MIXED":
        explanation = f"Only {n} decisive revisions in 14 days, {f} of them failed; the sample is too small for a rate."
    else:
        explanation = f"Only {n} decisive revisions in 14 days, all passed; the sample is too small for a rate."

    status = EVAL_AVAILABLE
    semantics = SEM_EXACT
    possible: list[str] | None = None
    if current_reference == VERIFY_UNRESOLVED:
        reachable = reachable_after_unresolved(n, f, fallback_verdict)
        if reachable != [band]:
            status = EVAL_DEGRADED
            semantics = SEM_SUPERSET
            possible = reachable
            diagnostics.append("CURRENT_VERIFICATION_UNRESOLVED")
            explanation += " The latest revision is still being verified, so the current state is unresolved."
    return _result(obs, band, status, semantics, possible, derived, diagnostics, explanation)
