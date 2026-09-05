"""DEBT: explicitly registered unresolved technical-maintenance obligations.

Debt never infers itself from age, TODO text, lint output or issue prose. It
exists only through an explicit, versioned mapping (for example issue labels)
and without an accepted calibrated policy its bands are PRESENT, CLEAR and
UNINSTRUMENTED plus raw diagnostics (PV-VITALS-V1-002).
"""

from __future__ import annotations

from ..observations import PARTIAL, ObservationSet
from .common import (
    EVAL_AVAILABLE,
    EVAL_DEGRADED,
    SEM_EXACT,
    SEM_LOWER,
    VitalResult,
    as_int,
    input_meta,
    unknown_result,
)

VITAL_ID = "debt"
VITAL_VERSION = "PV-VITALS-V1-002/debt"
RULE_ID = "debt.bands.v1.1"
BANDS = ["UNINSTRUMENTED", "CLEAR", "PRESENT"]

CAPABILITY = "debt.registry.capability"
OPEN = "debt.items.open_count"
STALE = "debt.items.open_stale_count_30d"
CLOSED = "debt.items.closed_count_28d"
MAPPING = "debt.mapping"
IDS = [CAPABILITY, OPEN, STALE, CLOSED, MAPPING]

SHARED = ["EXPLICIT_DEBT_REGISTER", "FORGE_INVENTORY"]
GROUPS = ["DEBT_CLUTTER_MAINTENANCE"]

CAP_CONFIGURED = "CONFIGURED"
CAP_UNCONFIGURED = "UNCONFIGURED"


def _result(obs: ObservationSet, band: str, status: str, semantics: str, possible, derived: dict, explanation: str, diagnostics: list[str]) -> VitalResult:
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


def evaluate(obs: ObservationSet) -> VitalResult:
    if not obs.is_good(CAPABILITY):
        return unknown_result(
            VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS,
            [f"MISSING_REQUIRED:{CAPABILITY}:{obs.status_of(CAPABILITY)}/{obs.freshness_of(CAPABILITY)}"],
            SHARED, GROUPS,
        )
    capability = obs.value_of(CAPABILITY)
    mapping = obs.value_of(MAPPING) if obs.is_good(MAPPING) else None
    if capability == CAP_UNCONFIGURED:
        return _result(
            obs, "UNINSTRUMENTED", EVAL_AVAILABLE, SEM_EXACT, None,
            {"capability": capability, "mapping": None},
            "No debt register or category mapping is configured; debt is not instrumented.",
            [],
        )
    stale = obs.value_of(STALE) if obs.is_good(STALE) else None
    closed = obs.value_of(CLOSED) if obs.is_good(CLOSED) else None
    derived_base = {"capability": capability, "mapping": mapping, "open_stale_count_30d": stale, "closed_count_28d": closed}

    if obs.is_good(OPEN):
        open_count = as_int(obs.value_of(OPEN))
        band = "PRESENT" if open_count > 0 else "CLEAR"
        derived = dict(derived_base, open_count=open_count)
        explanation = f"{open_count} open registered debt items under mapping version {mapping.get('mapping_version') if isinstance(mapping, dict) else 'n/a'}."
        return _result(obs, band, EVAL_AVAILABLE, SEM_EXACT, None, derived, explanation, [])

    open_obs = obs.get(OPEN)
    if open_obs is not None and open_obs.status == PARTIAL and open_obs.has_value and as_int(open_obs.value) > 0:
        open_count = as_int(open_obs.value)
        derived = dict(derived_base, open_count=open_count, open_count_semantics="LOWER_BOUND")
        return _result(
            obs, "PRESENT", EVAL_DEGRADED, SEM_LOWER, ["PRESENT"], derived,
            f"At least {open_count} open registered debt items were observed; the register enumeration is incomplete.",
            [f"PARTIAL_REGISTER:{OPEN}"],
        )
    return unknown_result(
        VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS,
        [f"MISSING_REQUIRED:{OPEN}:{obs.status_of(OPEN)}/{obs.freshness_of(OPEN)}"],
        SHARED, GROUPS,
        explanation="Debt is configured but its register could not be observed completely; CLEAR is never assumed.",
    )
