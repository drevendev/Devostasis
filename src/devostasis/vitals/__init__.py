"""Seven deterministic core Vitals over a normalized observation set."""

from __future__ import annotations

from typing import Any

from ..contracts import CORE_VITAL_IDS, OBSERVATION_CONTRACT_VERSION, SNAPSHOT_SCHEMA, VITALS_CONTRACT_VERSION
from ..observations import ObservationSet
from ..policy import POLICY_VERSION
from . import clutter, debt, direction, flow, horizon, integrity, pulse
from .common import VitalResult

EVALUATORS = {
    "horizon": horizon.evaluate,
    "clutter": clutter.evaluate,
    "direction": direction.evaluate,
    "flow": flow.evaluate,
    "integrity": integrity.evaluate,
    "debt": debt.evaluate,
    "pulse": pulse.evaluate,
}

BANDS = {
    "horizon": horizon.BANDS,
    "clutter": clutter.BANDS,
    "direction": direction.BANDS,
    "flow": flow.BANDS,
    "integrity": integrity.BANDS,
    "debt": debt.BANDS,
    "pulse": pulse.BANDS,
}


def evaluate_all(obs: ObservationSet) -> list[VitalResult]:
    return [EVALUATORS[vital_id](obs) for vital_id in CORE_VITAL_IDS]


def build_snapshot(obs: ObservationSet, results: list[VitalResult] | None = None) -> dict[str, Any]:
    """Authoritative machine snapshot: exactly seven Vitals in canonical order."""
    results = results if results is not None else evaluate_all(obs)
    return {
        "schema": SNAPSHOT_SCHEMA,
        "vitals_contract_version": VITALS_CONTRACT_VERSION,
        "observation_contract_version": OBSERVATION_CONTRACT_VERSION,
        "policy_version": POLICY_VERSION,
        "subject": obs.subject,
        "observed_at": obs.observed_at,
        "observations_digest": obs.digest(),
        "vitals": [result.to_dict() for result in results],
    }


def bands_of(snapshot: dict[str, Any]) -> dict[str, str | None]:
    return {item["vital_id"]: item["band"] for item in snapshot.get("vitals", [])}
