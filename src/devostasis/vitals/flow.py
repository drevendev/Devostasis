"""FLOW: change-request queue movement and friction (rule ``flow.bands.v1``).

NO_QUEUE is descriptive, never positive: an abandoned repository must not look
healthy because it has zero open change requests.

Rule version 1 adopts two calibration repairs without touching a threshold:

* PV-FLOW-EMPTY-QUEUE-001: a positively observed empty queue is NO_QUEUE; the
  historical merge median is evidence about completed change requests and
  cannot make a queue that does not exist CONGESTED or GRIDLOCKED. The
  friction predicates apply only when ``open_count > 0``.
* PV-FLOW-MERGE-LATENCY-001: the classifier consumes the exact rational median
  merge latency in seconds (``{"numerator", "denominator"}``); the whole-hour
  value is a derived presentation projection and never a classifier input.
"""

from __future__ import annotations

from fractions import Fraction

from .. import timeutil
from ..canonical import rational_from_record, rational_record
from ..observations import ObservationSet
from ..policy import FLOW
from .common import EVAL_AVAILABLE, SEM_EXACT, VitalResult, as_int, input_meta, unknown_result

VITAL_ID = "flow"
VITAL_VERSION = "PV-VITALS-V1-002/flow"
RULE_ID = "flow.bands.v1"
EMPTY_QUEUE_RULE = "PV-FLOW-EMPTY-QUEUE-001"
MERGE_LATENCY_RULE = "PV-FLOW-MERGE-LATENCY-001"
BANDS = ["NO_QUEUE", "MOVING", "CONGESTED", "GRIDLOCKED"]

OPEN = "forge.change_requests.open_count"
MERGED = "forge.change_requests.merged_count_28d"
OLDEST = "forge.change_requests.oldest_open_age_days"
MEDIAN = "forge.change_requests.median_time_to_merge_seconds_28d"
MEDIAN_HOURS = "forge.change_requests.median_time_to_merge_hours_28d"  # presentation projection only
IDS = [OPEN, MERGED, OLDEST, MEDIAN]

SHARED = ["CHANGE_REQUEST_INVENTORY", "CHANGE_REQUEST_ACTIVITY"]
GROUPS = ["CLUTTER_FLOW_FORGE", "FLOW_PULSE_ACTIVITY"]


def _median_of(obs: ObservationSet, diagnostics: list[str]) -> Fraction | None:
    median = rational_from_record(obs.value_of(MEDIAN))
    if median is None:
        diagnostics.append(f"INVALID_INPUT:{MEDIAN}:NOT_A_RATIONAL_RECORD")
    return median


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
                median = _median_of(obs, diagnostics)
    elif obs.is_good(MEDIAN):
        # Auditable evidence about completed change requests; not applicable to an empty queue.
        median = _median_of(obs, diagnostics)
    if diagnostics:
        return unknown_result(VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS, diagnostics, SHARED, GROUPS)

    if open_count == 0:
        band = "NO_QUEUE"
        if median is not None and median > FLOW["congested_median_seconds"]:
            diagnostics.append("FLOW_HISTORICAL_MEDIAN_NOT_APPLICABLE:EMPTY_QUEUE")
    elif (
        open_count >= FLOW["gridlocked_open"]
        and oldest is not None
        and oldest >= FLOW["gridlocked_oldest_days"]
        and merged == 0
    ) or (
        open_count >= FLOW["gridlocked_open_with_slow_median"]
        and median is not None
        and median > FLOW["gridlocked_median_seconds"]
    ):
        band = "GRIDLOCKED"
    elif (
        (oldest is not None and oldest >= FLOW["congested_oldest_days"])
        or open_count >= FLOW["congested_open"]
        or (median is not None and median > FLOW["congested_median_seconds"])
    ):
        band = "CONGESTED"
    else:
        band = "MOVING"

    derived = {
        "open_count": open_count,
        "merged_count_28d": merged,
        "oldest_open_age_days": oldest,
        "median_time_to_merge_seconds_28d": rational_record(median) if median is not None else None,
        "median_time_to_merge_hours_28d": int(median // 3600) if median is not None else None,
    }
    parts = [f"{open_count} open change requests", f"{merged} merged in 28 days"]
    if oldest is not None:
        parts.append(f"oldest open for {oldest} days")
    if median is not None:
        text = f"median time to merge {timeutil.duration_text(median)}"
        if open_count == 0:
            text += " (historical; not applicable to an empty queue)"
        parts.append(text)
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
