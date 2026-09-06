"""Typed observation envelopes and collection receipts (RAW_OBSERVATION_CONTRACT_V0).

The core invariant of the contract: ``value != evidence status``. A collector
that cannot prove a value emits no value and an explicit non-available status.
Zero, empty and false are only ever positively observed values.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from . import canonical
from .contracts import OBSERVATION_CONTRACT_VERSION, OBSERVATIONS_SCHEMA, RECEIPT_SCHEMA

AVAILABLE = "AVAILABLE"
PARTIAL = "PARTIAL"
UNAVAILABLE = "UNAVAILABLE"
FORBIDDEN = "FORBIDDEN"
UNKNOWN = "UNKNOWN"
ERROR = "ERROR"
STATUSES = frozenset({AVAILABLE, PARTIAL, UNAVAILABLE, FORBIDDEN, UNKNOWN, ERROR})
VALUE_BEARING = frozenset({AVAILABLE, PARTIAL})

FRESH = "FRESH"
STALE = "STALE"
FRESHNESS_UNKNOWN = "UNKNOWN"
FRESHNESSES = frozenset({FRESH, STALE, FRESHNESS_UNKNOWN})

VALUE_TYPES = frozenset({"count", "ratio", "duration", "boolean", "enum", "string", "set", "series", "record"})

NOT_REQUESTED = "NOT_REQUESTED"


class ObservationError(ValueError):
    """Raised when an envelope violates the observation contract."""


@dataclass(frozen=True)
class Observation:
    observation_id: str
    status: str
    value_type: str
    value: Any = None
    freshness: str = FRESH
    provider: str = "unknown"
    collected_at: str | None = None
    source_ref: str | None = None
    coverage: dict[str, Any] | None = None
    evidence_ref: Any = None
    adapter_version: str | None = None
    reason_code: str | None = None
    notes: str | None = None
    schema_version: str = OBSERVATION_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.observation_id:
            raise ObservationError("observation_id is required")
        if self.status not in STATUSES:
            raise ObservationError(f"{self.observation_id}: invalid status {self.status!r}")
        if self.freshness not in FRESHNESSES:
            raise ObservationError(f"{self.observation_id}: invalid freshness {self.freshness!r}")
        if self.value_type not in VALUE_TYPES:
            raise ObservationError(f"{self.observation_id}: invalid value_type {self.value_type!r}")
        if self.status not in VALUE_BEARING and self.value is not None:
            raise ObservationError(
                f"{self.observation_id}: status {self.status} must not carry a value (value != evidence status)"
            )
        if self.status == AVAILABLE and self.value is None and self.value_type != "record":
            raise ObservationError(f"{self.observation_id}: AVAILABLE observation must carry a value")

    @property
    def good(self) -> bool:
        """Exact evidence: positively observed and fresh."""
        return self.status == AVAILABLE and self.freshness == FRESH

    @property
    def has_value(self) -> bool:
        return self.status in VALUE_BEARING and self.value is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "schema_version": self.schema_version,
            "provider": self.provider,
            "collected_at": self.collected_at,
            "source_ref": self.source_ref,
            "status": self.status,
            "freshness": self.freshness,
            "value_type": self.value_type,
            "value": self.value,
            "coverage": self.coverage,
            "evidence_ref": self.evidence_ref,
            "adapter_version": self.adapter_version,
            "reason_code": self.reason_code,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Observation":
        return cls(
            observation_id=data["observation_id"],
            status=data["status"],
            value_type=data.get("value_type", "count"),
            value=data.get("value"),
            freshness=data.get("freshness", FRESH),
            provider=data.get("provider", "unknown"),
            collected_at=data.get("collected_at"),
            source_ref=data.get("source_ref"),
            coverage=data.get("coverage"),
            evidence_ref=data.get("evidence_ref"),
            adapter_version=data.get("adapter_version"),
            reason_code=data.get("reason_code"),
            notes=data.get("notes"),
            schema_version=data.get("schema_version", OBSERVATION_CONTRACT_VERSION),
        )


@dataclass
class Receipt:
    """Collection receipt: distinguishes not requested, requested-but-unknown and observed zero.

    It records *what* was asked for and what came back, never *how* the answers
    were fetched. The number of HTTP calls a run needed is a property of the
    client and its cache, not of the evidence, so it lives in the bundle's
    post-identity ``run_meta``: enabling a conditional cache must not change the
    identity of a bundle built from identical observations (v2).
    """

    run_id: str
    collector_version: str
    target: dict[str, Any]
    started_at: str
    ended_at: str
    requested_keys: list[str] = field(default_factory=list)
    returned_keys: list[str] = field(default_factory=list)
    per_key: dict[str, dict[str, str]] = field(default_factory=dict)
    capability_notes: list[str] = field(default_factory=list)
    config_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": RECEIPT_SCHEMA,
            "run_id": self.run_id,
            "collector_version": self.collector_version,
            "target": self.target,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "requested_keys": sorted(self.requested_keys),
            "returned_keys": sorted(self.returned_keys),
            "per_key": {key: dict(self.per_key[key]) for key in sorted(self.per_key)},
            "capability_notes": sorted(set(self.capability_notes)),
            "config_hash": self.config_hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Receipt":
        return cls(
            run_id=data["run_id"],
            collector_version=data.get("collector_version", "unknown"),
            target=data.get("target", {}),
            started_at=data.get("started_at", ""),
            ended_at=data.get("ended_at", ""),
            requested_keys=list(data.get("requested_keys", [])),
            returned_keys=list(data.get("returned_keys", [])),
            per_key={k: dict(v) for k, v in data.get("per_key", {}).items()},
            capability_notes=list(data.get("capability_notes", [])),
            config_hash=data.get("config_hash"),
        )


class ObservationSet:
    """All observations of one subject at one ``observed_at`` plus the receipt."""

    def __init__(
        self,
        subject: dict[str, Any],
        observed_at: str,
        observations: Iterable[Observation] = (),
        receipt: Receipt | None = None,
    ) -> None:
        self.subject = dict(subject)
        self.observed_at = observed_at
        self._items: dict[str, Observation] = {}
        self.receipt = receipt
        for item in observations:
            self.add(item)

    def add(self, item: Observation) -> None:
        if item.observation_id in self._items:
            raise ObservationError(f"duplicate observation {item.observation_id}")
        self._items[item.observation_id] = item

    def replace(self, item: Observation) -> None:
        self._items[item.observation_id] = item

    def __contains__(self, observation_id: str) -> bool:
        return observation_id in self._items

    def __iter__(self):
        return iter(self.sorted())

    def __len__(self) -> int:
        return len(self._items)

    def ids(self) -> list[str]:
        return sorted(self._items)

    def sorted(self) -> list[Observation]:
        return [self._items[key] for key in sorted(self._items)]

    def get(self, observation_id: str) -> Observation | None:
        return self._items.get(observation_id)

    def status_of(self, observation_id: str) -> str:
        item = self._items.get(observation_id)
        return item.status if item else NOT_REQUESTED

    def freshness_of(self, observation_id: str) -> str:
        item = self._items.get(observation_id)
        return item.freshness if item else FRESHNESS_UNKNOWN

    def is_good(self, observation_id: str) -> bool:
        item = self._items.get(observation_id)
        return bool(item and item.good)

    def is_explicitly(self, observation_id: str, status: str) -> bool:
        item = self._items.get(observation_id)
        return bool(item and item.status == status)

    def value_of(self, observation_id: str, default: Any = None) -> Any:
        item = self._items.get(observation_id)
        if item is None or not item.has_value:
            return default
        return item.value

    def finalize_receipt(self, receipt: Receipt) -> Receipt:
        receipt.requested_keys = sorted(set(receipt.requested_keys) | set(self._items))
        receipt.returned_keys = [key for key in sorted(self._items) if self._items[key].has_value]
        receipt.per_key = {
            key: {"status": self._items[key].status, "freshness": self._items[key].freshness}
            for key in sorted(self._items)
        }
        self.receipt = receipt
        return receipt

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": OBSERVATIONS_SCHEMA,
            "observation_contract_version": OBSERVATION_CONTRACT_VERSION,
            "subject": self.subject,
            "observed_at": self.observed_at,
            "observations": [item.to_dict() for item in self.sorted()],
            "receipt": self.receipt.to_dict() if self.receipt else None,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ObservationSet":
        receipt = Receipt.from_dict(data["receipt"]) if data.get("receipt") else None
        return cls(
            subject=data.get("subject", {}),
            observed_at=data["observed_at"],
            observations=[Observation.from_dict(item) for item in data.get("observations", [])],
            receipt=receipt,
        )

    def save(self, path: str | Path) -> None:
        canonical.write_pretty(path, self.to_dict())

    @classmethod
    def load(cls, path: str | Path) -> "ObservationSet":
        return cls.from_dict(canonical.load_file(path))

    def digest(self) -> str:
        return canonical.digest(self.to_dict())


def unavailable(observation_id: str, value_type: str, reason_code: str, **extra: Any) -> Observation:
    return Observation(observation_id=observation_id, status=UNAVAILABLE, value_type=value_type, reason_code=reason_code, **extra)


def forbidden(observation_id: str, value_type: str, reason_code: str, **extra: Any) -> Observation:
    return Observation(observation_id=observation_id, status=FORBIDDEN, value_type=value_type, reason_code=reason_code, **extra)


def unknown(observation_id: str, value_type: str, reason_code: str, **extra: Any) -> Observation:
    return Observation(observation_id=observation_id, status=UNKNOWN, value_type=value_type, reason_code=reason_code, **extra)


def error(observation_id: str, value_type: str, reason_code: str, **extra: Any) -> Observation:
    return Observation(observation_id=observation_id, status=ERROR, value_type=value_type, reason_code=reason_code, **extra)
