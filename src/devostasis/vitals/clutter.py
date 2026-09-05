"""CLUTTER: unresolved stale work inventory and branch residue.

Clutter measures attention burden, not value. Closing valid work only to
improve Clutter is a known gaming path, so the band stays descriptive and the
counts stay visible.
"""

from __future__ import annotations

from ..canonical import ratio
from ..observations import UNAVAILABLE, ObservationSet
from ..policy import CLUTTER
from .common import (
    EVAL_AVAILABLE,
    EVAL_DEGRADED,
    SEM_EXACT,
    SEM_LOWER,
    VitalResult,
    as_int,
    bands_from,
    input_meta,
    unknown_result,
)

VITAL_ID = "clutter"
VITAL_VERSION = "PV-VITALS-V1-002/clutter"
RULE_ID = "clutter.bands.v0"
BANDS = ["CLEAN", "LIGHT", "CLUTTERED", "HEAVY"]

ISSUES_OPEN = "forge.issues.open_count"
ISSUES_STALE = "forge.issues.stale_open_count_30d"
CR_OPEN = "forge.change_requests.open_count"
CR_STALE = "forge.change_requests.stale_open_count_14d"
BRANCHES_STALE = "git.nondefault_branches.stale_count_30d"
IDS = [ISSUES_OPEN, ISSUES_STALE, CR_OPEN, CR_STALE, BRANCHES_STALE]

SHARED = ["FORGE_INVENTORY", "BRANCH_RESIDUE"]
GROUPS = ["CLUTTER_FLOW_FORGE"]


def classify(stale_work: int, tracked_open: int, stale_branches: int | None) -> str:
    branches = stale_branches or 0
    heavy_num, heavy_den = CLUTTER["heavy_ratio"]
    clut_num, clut_den = CLUTTER["cluttered_ratio"]
    ratio_ok = tracked_open >= CLUTTER["ratio_min_tracked"]
    if (
        stale_work >= CLUTTER["heavy_stale_work"]
        or (ratio_ok and stale_work * heavy_den >= tracked_open * heavy_num)
        or branches >= CLUTTER["heavy_stale_branches"]
    ):
        return "HEAVY"
    if (
        stale_work >= CLUTTER["cluttered_stale_work"]
        or (ratio_ok and stale_work * clut_den >= tracked_open * clut_num)
        or branches >= CLUTTER["cluttered_stale_branches"]
    ):
        return "CLUTTERED"
    if stale_work > 0 or branches > 0:
        return "LIGHT"
    return "CLEAN"


def evaluate(obs: ObservationSet) -> VitalResult:
    diagnostics: list[str] = []
    for oid in (CR_OPEN, CR_STALE):
        if not obs.is_good(oid):
            diagnostics.append(f"MISSING_REQUIRED:{oid}:{obs.status_of(oid)}/{obs.freshness_of(oid)}")
    if diagnostics:
        return unknown_result(VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS, diagnostics, SHARED, GROUPS)

    cr_open = as_int(obs.value_of(CR_OPEN))
    cr_stale = as_int(obs.value_of(CR_STALE))
    excluded: list[str] = []

    if obs.is_good(ISSUES_OPEN) and obs.is_good(ISSUES_STALE):
        issues_open = as_int(obs.value_of(ISSUES_OPEN))
        issues_stale = as_int(obs.value_of(ISSUES_STALE))
    elif obs.is_explicitly(ISSUES_OPEN, UNAVAILABLE) and obs.is_explicitly(ISSUES_STALE, UNAVAILABLE):
        issues_open = None
        issues_stale = None
        excluded.append(f"COMPONENT_UNAVAILABLE:issues:{obs.get(ISSUES_OPEN).reason_code}")
    else:
        diagnostics.append(f"COMPONENT_UNRESOLVED:issues:{obs.status_of(ISSUES_OPEN)}/{obs.status_of(ISSUES_STALE)}")
        return unknown_result(VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS, diagnostics, SHARED, GROUPS)

    if obs.is_good(BRANCHES_STALE):
        stale_branches = as_int(obs.value_of(BRANCHES_STALE))
    elif obs.is_explicitly(BRANCHES_STALE, UNAVAILABLE):
        stale_branches = None
        excluded.append(f"COMPONENT_UNAVAILABLE:branches:{obs.get(BRANCHES_STALE).reason_code}")
    else:
        diagnostics.append(f"COMPONENT_UNRESOLVED:branches:{obs.status_of(BRANCHES_STALE)}/{obs.freshness_of(BRANCHES_STALE)}")
        return unknown_result(VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS, diagnostics, SHARED, GROUPS)

    tracked_open = cr_open + (issues_open or 0)
    stale_work = cr_stale + (issues_stale or 0)
    band = classify(stale_work, tracked_open, stale_branches)
    derived = {
        "tracked_open_count": tracked_open,
        "stale_work_count": stale_work,
        "stale_work_ratio": ratio(stale_work, tracked_open) if tracked_open > 0 else None,
        "stale_branch_count": stale_branches,
        "components": {
            "change_requests": {"open": cr_open, "stale_14d": cr_stale},
            "issues": None if issues_open is None else {"open": issues_open, "stale_30d": issues_stale},
            "branches": None if stale_branches is None else {"stale_30d": stale_branches},
        },
    }
    explanation = (
        f"{stale_work} stale work items out of {tracked_open} tracked open items"
        + (f"; {stale_branches} stale non-default branches" if stale_branches is not None else "")
        + "."
    )
    if not excluded:
        return VitalResult(
            vital_id=VITAL_ID,
            vital_version=VITAL_VERSION,
            rule_id=RULE_ID,
            band=band,
            evaluation_status=EVAL_AVAILABLE,
            band_semantics=SEM_EXACT,
            possible_bands=None,
            inputs=input_meta(obs, IDS),
            derived=derived,
            shared_signal_groups=SHARED,
            dependency_group_ids=GROUPS,
            diagnostics=diagnostics,
            explanation=explanation,
        )
    return VitalResult(
        vital_id=VITAL_ID,
        vital_version=VITAL_VERSION,
        rule_id=RULE_ID,
        band=band,
        evaluation_status=EVAL_DEGRADED,
        band_semantics=SEM_LOWER,
        possible_bands=bands_from(BANDS, band),
        inputs=input_meta(obs, IDS),
        derived=derived,
        shared_signal_groups=SHARED,
        dependency_group_ids=GROUPS,
        diagnostics=diagnostics + excluded,
        explanation=explanation + " One or more inventory components are unavailable, so the band is a lower bound.",
    )
