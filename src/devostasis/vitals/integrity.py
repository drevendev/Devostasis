"""INTEGRITY: automated verification stability of recent immutable revisions.

The adapter produces one canonical record per default-branch revision of the
14-day window (PV-CI-UNIT-004 semantics: one contribution per immutable
revision, failure-sticky history, current verdict independent of history).
This evaluator only counts and classifies; it never re-interprets provider
outcomes.
"""

from __future__ import annotations

from typing import Any

from ..canonical import ratio
from ..observations import AVAILABLE, FRESH, PARTIAL, ObservationSet
from ..policy import INTEGRITY
from .common import (
    EVAL_AVAILABLE,
    EVAL_DEGRADED,
    SEM_EXACT,
    SEM_SUPERSET,
    VitalResult,
    input_meta,
    unknown_result,
)

VITAL_ID = "integrity"
VITAL_VERSION = "PV-VITALS-V1-002/integrity"
RULE_ID = "integrity.bands.v0+ci-unit-004"
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


def _result(
    obs: ObservationSet,
    band: str,
    status: str,
    semantics: str,
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


def _superset(band: str) -> list[str]:
    return [band] + [b for b in ("FAILING", "FLAKY", "SPARSE_MIXED") if b != band]


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
    if series.status == PARTIAL:
        diagnostics.append("REVISION_SERIES_PARTIAL")

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
        status = EVAL_DEGRADED if series.status == PARTIAL else EVAL_AVAILABLE
        return _result(
            obs,
            "NO_RECENT_RUNS",
            status,
            SEM_EXACT if status == EVAL_AVAILABLE else SEM_SUPERSET,
            None if status == EVAL_AVAILABLE else _superset("NO_RECENT_RUNS"),
            {"decisive_count_14d": 0, "failed_count_14d": 0, "revisions_in_window": len(revisions), "revisions_with_verification": 0},
            diagnostics,
            f"Verification is configured but none of the {len(revisions)} recent default-branch revisions has a verification execution.",
        )

    if not configured_known:
        diagnostics.append("CONFIGURED_INFERRED_FROM_RUNS")

    decisive = [r for r in active if r.get("historical_contribution") in DECISIVE]
    failed = [r for r in decisive if r.get("history_state") == "FAILURE_OBSERVED"]
    latest = max(active, key=lambda r: (r.get("committed_at") or "", r.get("revision") or ""))
    current = latest.get("current_verdict") or VERDICT_UNKNOWN
    n = len(decisive)
    f = len(failed)
    established = INTEGRITY["established_sample"]
    fail_num, fail_den = INTEGRITY["failing_ratio"]

    provenance: dict[str, int] = {}
    for r in active:
        key = r.get("history_provenance") or "UNKNOWN"
        provenance[key] = provenance.get(key, 0) + 1
    if provenance.get("PARENT_LEVEL_ONLY"):
        diagnostics.append(f"HISTORY_PROVENANCE_PARENT_LEVEL_ONLY:{provenance['PARENT_LEVEL_ONLY']}")

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

    current_reference = current
    if current not in DECISIVE and current != VERIFY_UNRESOLVED:
        decisive_current = [r for r in active if r.get("current_verdict") in DECISIVE]
        if decisive_current:
            fallback = max(decisive_current, key=lambda r: (r.get("committed_at") or "", r.get("revision") or ""))
            current_reference = fallback.get("current_verdict")
            derived["latest_decisive_revision"] = {
                "revision": fallback.get("revision"),
                "committed_at": fallback.get("committed_at"),
                "current_verdict": current_reference,
            }
            diagnostics.append(f"LATEST_REVISION_NON_DECISIVE:{current}")

    if n == 0:
        band = "NO_DECISIVE_RUNS"
        explanation = f"{len(active)} recent revisions carry verification executions but none produced a decisive pass/fail verdict."
    elif current_reference == VERIFY_FAIL or (n >= established and f * fail_den >= n * fail_num):
        band = "FAILING"
        explanation = f"{f} of {n} decisive revisions failed verification in 14 days; latest decisive verdict is {current_reference}."
    elif n >= established and f > 0:
        band = "FLAKY"
        explanation = f"{f} of {n} decisive revisions failed verification in 14 days; latest decisive verdict is {current_reference}."
    elif n >= established:
        band = "CLEAN"
        explanation = f"All {n} decisive revisions passed verification in 14 days; latest decisive verdict is {current_reference}."
    elif f >= 1:
        band = "SPARSE_MIXED"
        explanation = f"Only {n} decisive revisions in 14 days, {f} of them failed; the sample is too small for a rate."
    else:
        band = "SPARSE"
        explanation = f"Only {n} decisive revisions in 14 days, all passed; the sample is too small for a rate."

    status = EVAL_AVAILABLE
    semantics = SEM_EXACT
    possible: list[str] | None = None
    if series.status == PARTIAL:
        status = EVAL_DEGRADED
        semantics = SEM_SUPERSET
        possible = _superset(band)
    if current_reference == VERIFY_UNRESOLVED and band != "FAILING":
        status = EVAL_DEGRADED
        semantics = SEM_SUPERSET
        possible = _superset(band)
        diagnostics.append("CURRENT_VERIFICATION_UNRESOLVED")
        explanation += " The latest revision is still being verified, so the current state is unresolved."
    return _result(obs, band, status, semantics, possible, derived, diagnostics, explanation)
