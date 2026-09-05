"""Shared output contract of every Vital evaluator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts import VITALS_CONTRACT_VERSION
from ..observations import ObservationSet
from ..policy import POLICY_VERSION

EVAL_AVAILABLE = "AVAILABLE"
EVAL_DEGRADED = "DEGRADED"
EVAL_UNKNOWN = "UNKNOWN"

SEM_EXACT = "EXACT"
SEM_LOWER = "CONSERVATIVE_LOWER_BOUND"
SEM_UPPER = "CONSERVATIVE_UPPER_BOUND"
SEM_SUPERSET = "NON_AUTHORITATIVE_CONSERVATIVE_SUPERSET"


@dataclass
class VitalResult:
    vital_id: str
    vital_version: str
    rule_id: str
    band: str | None
    evaluation_status: str
    band_semantics: str | None
    possible_bands: list[str] | None
    inputs: list[dict[str, str]]
    derived: dict[str, Any]
    shared_signal_groups: list[str]
    dependency_group_ids: list[str]
    diagnostics: list[str] = field(default_factory=list)
    explanation: str = ""
    policy_version: str = POLICY_VERSION
    vitals_contract_version: str = VITALS_CONTRACT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "vital_id": self.vital_id,
            "vital_version": self.vital_version,
            "vitals_contract_version": self.vitals_contract_version,
            "rule_id": self.rule_id,
            "policy_version": self.policy_version,
            "band": self.band,
            "evaluation_status": self.evaluation_status,
            "band_semantics": self.band_semantics,
            "possible_bands": list(self.possible_bands) if self.possible_bands is not None else None,
            "inputs": list(self.inputs),
            "derived": self.derived,
            "shared_signal_groups": list(self.shared_signal_groups),
            "dependency_group_ids": list(self.dependency_group_ids),
            "diagnostics": sorted(set(self.diagnostics)),
            "explanation": self.explanation,
        }


def input_meta(obs: ObservationSet, ids: list[str]) -> list[dict[str, str]]:
    return [
        {"observation_id": oid, "status": obs.status_of(oid), "freshness": obs.freshness_of(oid)}
        for oid in ids
    ]


def missing_required(obs: ObservationSet, ids: list[str]) -> list[str]:
    return [f"MISSING_REQUIRED:{oid}:{obs.status_of(oid)}/{obs.freshness_of(oid)}" for oid in ids if not obs.is_good(oid)]


def unknown_result(
    vital_id: str,
    vital_version: str,
    rule_id: str,
    obs: ObservationSet,
    ids: list[str],
    diagnostics: list[str],
    shared_signal_groups: list[str],
    dependency_group_ids: list[str],
    explanation: str = "Evidence is insufficient for a deterministic band; no band is fabricated.",
) -> VitalResult:
    return VitalResult(
        vital_id=vital_id,
        vital_version=vital_version,
        rule_id=rule_id,
        band=None,
        evaluation_status=EVAL_UNKNOWN,
        band_semantics=None,
        possible_bands=None,
        inputs=input_meta(obs, ids),
        derived={},
        shared_signal_groups=shared_signal_groups,
        dependency_group_ids=dependency_group_ids,
        diagnostics=diagnostics,
        explanation=explanation,
    )


def bands_from(order: list[str], band: str) -> list[str]:
    """Conservative superset of bands reachable from a lower bound ``band``."""
    return order[order.index(band):]


def as_int(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeError("boolean where integer expected")
    return int(value)
