"""HORIZON: how much future work is explicitly declared in planning metadata.

Horizon measures forward visibility, not roadmap quality. EXTENDED is not
better than VISIBLE; UNDECLARED may be entirely appropriate.
"""

from __future__ import annotations

from ..observations import ObservationSet
from .common import EVAL_AVAILABLE, SEM_EXACT, VitalResult, as_int, input_meta, unknown_result

VITAL_ID = "horizon"
VITAL_VERSION = "PV-VITALS-V1-002/horizon"
RULE_ID = "horizon.bands.v1"
BANDS = ["UNDECLARED", "DECLARED", "VISIBLE", "EXTENDED"]

CAPABILITY = "planning.explicit_targets.capability"
OPEN = "planning.explicit_targets.open_count"
FUTURE = "planning.explicit_targets.open_with_future_boundary_count"
BEYOND = "planning.explicit_targets.open_beyond_28d_count"
NEAREST = "planning.explicit_targets.nearest_future_boundary_days"
IDS = [CAPABILITY, OPEN, FUTURE, BEYOND, NEAREST]

SHARED = ["PLANNING_TARGETS"]
GROUPS = ["HORIZON_DIRECTION_PLANNING"]

CAP_SUPPORTED = "SUPPORTED"
CAP_SUPPORTED_UNUSED = "SUPPORTED_UNUSED"
CAP_UNSUPPORTED = "UNSUPPORTED"


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
            {"capability": capability, "open_count": 0, "open_with_future_boundary_count": 0, "open_beyond_28d_count": 0},
            "No explicit planning targets are declared for this repository.",
            [f"PLANNING_CAPABILITY:{capability}"],
        )
    missing = [f"MISSING_REQUIRED:{oid}:{obs.status_of(oid)}/{obs.freshness_of(oid)}" for oid in (OPEN, FUTURE, BEYOND) if not obs.is_good(oid)]
    if missing:
        return unknown_result(VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS, missing, SHARED, GROUPS)

    open_count = as_int(obs.value_of(OPEN))
    future = as_int(obs.value_of(FUTURE))
    beyond = as_int(obs.value_of(BEYOND))
    nearest = obs.value_of(NEAREST) if obs.is_good(NEAREST) else None
    if beyond > 0:
        band = "EXTENDED"
    elif future > 0:
        band = "VISIBLE"
    elif open_count > 0:
        band = "DECLARED"
    else:
        band = "UNDECLARED"
    derived = {
        "capability": capability,
        "open_count": open_count,
        "open_with_future_boundary_count": future,
        "open_beyond_28d_count": beyond,
        "nearest_future_boundary_days": nearest,
    }
    explanation = f"{open_count} open planning targets, {future} with a future boundary, {beyond} reaching beyond 28 days."
    return _result(obs, band, derived, explanation, [])
