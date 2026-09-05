"""FLOW: change-request queue movement and friction.

NO_QUEUE is descriptive, never positive: an abandoned repository must not look
healthy because it has zero open change requests.
"""

from __future__ import annotations

from ..observations import ObservationSet
from ..policy import FLOW
from .common import EVAL_AVAILABLE, SEM_EXACT, VitalResult, as_int, input_meta, unknown_result

VITAL_ID = "flow"
VITAL_VERSION = "PV-VITALS-V1-002/flow"
RULE_ID = "flow.bands.v0"
BANDS = ["NO_QUEUE", "MOVING", "CONGESTED", "GRIDLOCKED"]

OPEN = "forge.change_requests.open_count"
MERGED = "forge.change_requests.merged_count_28d"
OLDEST = "forge.change_requests.oldest_open_age_days"
MEDIAN = "forge.change_requests.median_time_to_merge_hours_28d"
IDS = [OPEN, MERGED, OLDEST, MEDIAN]

SHARED = ["CHANGE_REQUEST_INVENTORY", "CHANGE_REQUEST_ACTIVITY"]
GROUPS = ["CLUTTER_FLOW_FORGE", "FLOW_PULSE_ACTIVITY"]


def evaluate(obs: ObservationSet) -> VitalResult:
    diagnostics: list[str] = []
    for oid in (OPEN, MERGED):
        if not obs.is_good(oid):
            diagnostics.append(f"MISSING_REQUIRED:{oid}:{obs.status_of(oid)}/{obs.freshness_of(oid)}")
    if diagnostics:
        return unknown_result(VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS, diagnostics, SHARED, GROUPS)

    open_count = as_int(obs.value_of(OPEN))
    merged = as_int(obs.value_of(MERGED))
    oldest = None
    median = None
    if open_count > 0:
        if not obs.is_good(OLDEST):
            diagnostics.append(f"MISSING_CONDITIONAL:{OLDEST}:{obs.status_of(OLDEST)}/{obs.freshness_of(OLDEST)}")
        else:
            oldest = as_int(obs.value_of(OLDEST))
    if merged > 0:
        if not obs.is_good(MEDIAN):
            diagnostics.append(f"MISSING_CONDITIONAL:{MEDIAN}:{obs.status_of(MEDIAN)}/{obs.freshness_of(MEDIAN)}")
        else:
            median = as_int(obs.value_of(MEDIAN))
    if diagnostics:
        return unknown_result(VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS, diagnostics, SHARED, GROUPS)

    median_applicable = median is not None
    if (
        open_count >= FLOW["gridlocked_open"]
        and oldest is not None
        and oldest >= FLOW["gridlocked_oldest_days"]
        and merged == 0
    ) or (
        open_count >= FLOW["gridlocked_open_with_slow_median"]
        and median_applicable
        and median > FLOW["gridlocked_median_hours"]
    ):
        band = "GRIDLOCKED"
    elif (
        (oldest is not None and oldest >= FLOW["congested_oldest_days"])
        or open_count >= FLOW["congested_open"]
        or (median_applicable and median > FLOW["congested_median_hours"])
    ):
        band = "CONGESTED"
        if open_count == 0:
            diagnostics.append("FLOW_MEDIAN_WITH_EMPTY_QUEUE")
    elif open_count > 0:
        band = "MOVING"
    else:
        band = "NO_QUEUE"

    derived = {
        "open_count": open_count,
        "merged_count_28d": merged,
        "oldest_open_age_days": oldest,
        "median_time_to_merge_hours_28d": median,
    }
    parts = [f"{open_count} open change requests", f"{merged} merged in 28 days"]
    if oldest is not None:
        parts.append(f"oldest open for {oldest} days")
    if median is not None:
        parts.append(f"median time to merge {median} hours")
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
        explanation="; ".join(parts) + ".",
    )
