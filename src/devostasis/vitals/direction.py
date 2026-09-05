"""DIRECTION: explicit traceability of active change work to declared targets.

FULLY_LINKED is neutral exact traceability; it is not strategy, prioritization
or target quality, and renderers must never alias it to ALIGNED or ON_TRACK.
"""

from __future__ import annotations

from ..observations import ObservationSet
from .common import EVAL_AVAILABLE, SEM_EXACT, VitalResult, as_int, input_meta, unknown_result
from .horizon import CAP_SUPPORTED_UNUSED, CAP_UNSUPPORTED, CAPABILITY

VITAL_ID = "direction"
VITAL_VERSION = "PV-VITALS-V1-002/direction"
RULE_ID = "direction.bands.v1.1"
BANDS = ["NO_ACTIVE_CHANGE", "UNDECLARED", "SCATTERED", "MIXED", "FULLY_LINKED"]

ACTIVE = "planning.linkage.active_change_requests_count_28d"
LINKED = "planning.linkage.active_change_requests_linked_to_open_target_count_28d"
TARGET_LINKS = "planning.linkage.links_per_target_28d"
IDS = [ACTIVE, LINKED, CAPABILITY, TARGET_LINKS]

SHARED = ["PLANNING_TARGETS", "CHANGE_REQUEST_ACTIVITY"]
GROUPS = ["HORIZON_DIRECTION_PLANNING", "DIRECTION_PULSE_ACTIVITY"]


def _result(obs: ObservationSet, band: str, derived: dict, explanation: str, diagnostics: list[str]) -> VitalResult:
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


def evaluate(obs: ObservationSet) -> VitalResult:
    if not obs.is_good(ACTIVE):
        return unknown_result(
            VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS,
            [f"MISSING_REQUIRED:{ACTIVE}:{obs.status_of(ACTIVE)}/{obs.freshness_of(ACTIVE)}"],
            SHARED, GROUPS,
        )
    active = as_int(obs.value_of(ACTIVE))
    if active == 0:
        return _result(obs, "NO_ACTIVE_CHANGE", {"active_change_count_28d": 0}, "No active change requests in the 28-day frame.", [])

    if not obs.is_good(CAPABILITY):
        return unknown_result(
            VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS,
            [f"MISSING_REQUIRED:{CAPABILITY}:{obs.status_of(CAPABILITY)}/{obs.freshness_of(CAPABILITY)}"],
            SHARED, GROUPS,
        )
    capability = obs.value_of(CAPABILITY)
    if capability in (CAP_UNSUPPORTED, CAP_SUPPORTED_UNUSED):
        return _result(
            obs,
            "UNDECLARED",
            {"active_change_count_28d": active, "capability": capability},
            f"{active} active change requests, but no explicit planning target or linkage mechanism is declared.",
            [f"PLANNING_CAPABILITY:{capability}"],
        )
    if not obs.is_good(LINKED):
        return unknown_result(
            VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS,
            [f"MISSING_REQUIRED:{LINKED}:{obs.status_of(LINKED)}/{obs.freshness_of(LINKED)}"],
            SHARED, GROUPS,
        )
    linked = as_int(obs.value_of(LINKED))
    unlinked = active - linked
    if unlinked > linked:
        band = "SCATTERED"
    elif unlinked > 0:
        band = "MIXED"
    else:
        band = "FULLY_LINKED"
    links = obs.value_of(TARGET_LINKS) if obs.is_good(TARGET_LINKS) else None
    derived = {
        "active_change_count_28d": active,
        "linked_active_change_count_28d": linked,
        "unlinked_active_change_count_28d": unlinked,
        "capability": capability,
        "links_per_target": links,
    }
    diagnostics: list[str] = []
    if isinstance(links, dict) and len(links) == 1 and linked > 1:
        diagnostics.append("ALL_LINKS_TO_SINGLE_TARGET")
    explanation = f"{linked} of {active} active change requests are explicitly linked to an open planning target."
    return _result(obs, band, derived, explanation, diagnostics)
