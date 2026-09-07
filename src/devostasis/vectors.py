"""Executable conformance vectors: the format and the runner (``devostasis.vectors.v1``).

A conformance case is a claim about behaviour. Written in prose it can only be
checked by a person reading both the sentence and the code; written as a vector
it is a JSON document that states the evidence and the expected result, and the
runner executes it against this implementation. The specification names cases
that no test covers (debt D-1, target B1); the vectors of ``PV-TEST-001`` are
authored against this format so that they arrive executable instead of needing
translation.

A vector file is::

    {"schema": "devostasis.vectors.v1", "notes": "...", "vectors": [ <vector>, ... ]}

and a vector is::

    {"case": "ORDER-01", "title": "...", "kind": "vital" | "delta",
     "source_unit": "PV-BAND-ORDER-001", "given": {...}, "expect": {...}}

``kind`` selects what is executed:

* **vital** evaluates one Vital over an observation set built from raw
  observation envelopes (``RAW_OBSERVATION_CONTRACT_V0``), so a vector states
  evidence exactly as a collector would emit it.
* **delta** compares two snapshots given as partial Vital rows and checks the
  transition classes and reason codes.

Three rules keep a vector suite honest:

* **It fails closed.** An unknown ``kind``, an unknown key, an unknown
  comparison status, a malformed envelope or a duplicate case id is an error,
  never a skip: a vector that cannot run must never look like a vector that
  passed.
* **It states, never computes.** Expectations are literal values. A vector
  that derived its expectation from the implementation would prove only that
  the implementation equals itself.
* **Every expectation is checked.** Absent keys are not checked, but a key that
  is present is asserted, and unknown expectation keys are rejected rather than
  quietly ignored.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .contracts import CORE_VITAL_IDS, VECTOR_SCHEMA
from .delta import BASELINE, COMPARABLE, HISTORY_GAP, INCOMPARABLE, compare
from .observations import Observation, ObservationSet
from .vitals import EVALUATORS

KINDS = ("vital", "delta")
COMPARISON_STATUSES = (BASELINE, COMPARABLE, HISTORY_GAP, INCOMPARABLE)

FILE_KEYS = {"schema", "notes", "vectors"}
VECTOR_KEYS = {"case", "title", "kind", "source_unit", "notes", "given", "expect"}
REQUIRED_VECTOR_KEYS = {"case", "title", "kind", "given", "expect"}

VITAL_GIVEN_KEYS = {"vital", "observations", "observed_at", "subject"}
VITAL_EXPECT_KEYS = {
    "band",
    "evaluation_status",
    "band_semantics",
    "possible_bands",
    "rule_id",
    "derived",
    "derived_absent",
    "diagnostics",
    "diagnostics_absent",
    "explanation_contains",
}
REQUIRED_VITAL_EXPECT_KEYS = {"band", "evaluation_status"}

DELTA_GIVEN_KEYS = {"comparison_status", "previous", "current", "previous_bundle_id", "incomparable_reasons"}
DELTA_SIDE_KEYS = {"observed_at", "vitals"}
DELTA_ROW_KEYS = {"vital_id", "band", "evaluation_status", "band_semantics", "rule_id", "derived", "inputs"}
DELTA_EXPECT_KEYS = {"comparison_status", "vitals"}
DELTA_ROW_EXPECT_KEYS = {"transition_class", "reason_codes", "reason_codes_absent", "metric_deltas", "coverage_delta"}

DEFAULT_OBSERVED_AT = "2026-01-01T00:00:00Z"
DEFAULT_SUBJECT = {
    "provider": "vector",
    "forge_instance": "vector.invalid",
    "owner": "vector",
    "repo": "vector",
    "display_locator": "vector/vector",
    "immutable_project_id": "vector",
    "default_branch": "master",
    "visibility": "public",
}


class VectorError(ValueError):
    """Raised when a vector file cannot be read as a valid vector document."""


@dataclass(frozen=True)
class Vector:
    case: str
    title: str
    kind: str
    given: dict[str, Any]
    expect: dict[str, Any]
    source_unit: str | None = None
    notes: str | None = None
    path: str = ""

    @property
    def label(self) -> str:
        return f"{self.case} ({self.kind})"


@dataclass
class VectorResult:
    vector: Vector
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures

    @property
    def case(self) -> str:
        return self.vector.case

    def report(self) -> str:
        head = f"{'PASS' if self.ok else 'FAIL'} {self.vector.case:<16} {self.vector.title}"
        return "\n".join([head] + [f"     - {failure}" for failure in self.failures])


# --------------------------------------------------------------------------- loading


def _require_keys(where: str, data: Any, allowed: set[str], required: set[str]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise VectorError(f"{where}: expected an object, got {type(data).__name__}")
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise VectorError(f"{where}: unknown keys {unknown}")
    missing = sorted(required - set(data))
    if missing:
        raise VectorError(f"{where}: missing keys {missing}")
    return data


def _validate_vital(where: str, given: dict[str, Any], expect: dict[str, Any]) -> None:
    _require_keys(f"{where} given", given, VITAL_GIVEN_KEYS, {"vital", "observations"})
    if given["vital"] not in EVALUATORS:
        raise VectorError(f"{where} given: unknown vital {given['vital']!r}")
    if not isinstance(given["observations"], list) or not given["observations"]:
        raise VectorError(f"{where} given: observations must be a non-empty list")
    _require_keys(f"{where} expect", expect, VITAL_EXPECT_KEYS, REQUIRED_VITAL_EXPECT_KEYS)


def _comparison_status(where: str, holder: dict[str, Any]) -> None:
    """A comparison status the engine does not know is an error, not a silently different run."""
    status = holder.get("comparison_status")
    if status is not None and status not in COMPARISON_STATUSES:
        raise VectorError(f"{where}: unknown comparison_status {status!r}, known are {list(COMPARISON_STATUSES)}")


def _validate_delta(where: str, given: dict[str, Any], expect: dict[str, Any]) -> None:
    _require_keys(f"{where} given", given, DELTA_GIVEN_KEYS, {"previous", "current"})
    _comparison_status(f"{where} given", given)
    for side in ("previous", "current"):
        rows = _require_keys(f"{where} given.{side}", given[side], DELTA_SIDE_KEYS, {"vitals"})["vitals"]
        if not isinstance(rows, list) or not rows:
            raise VectorError(f"{where} given.{side}: vitals must be a non-empty list")
        for row in rows:
            _require_keys(f"{where} given.{side} row", row, DELTA_ROW_KEYS, {"vital_id", "band"})
            if row["vital_id"] not in CORE_VITAL_IDS:
                raise VectorError(f"{where} given.{side}: unknown vital {row['vital_id']!r}")
    rows_expect = _require_keys(f"{where} expect", expect, DELTA_EXPECT_KEYS, {"vitals"})["vitals"]
    _comparison_status(f"{where} expect", expect)
    if not isinstance(rows_expect, dict) or not rows_expect:
        raise VectorError(f"{where} expect: vitals must be a non-empty object keyed by vital id")
    for vital_id, row in rows_expect.items():
        if vital_id not in CORE_VITAL_IDS:
            raise VectorError(f"{where} expect: unknown vital {vital_id!r}")
        _require_keys(f"{where} expect.{vital_id}", row, DELTA_ROW_EXPECT_KEYS, {"transition_class"})


def parse_document(document: Any, path: str = "") -> list[Vector]:
    """Every vector of one parsed file, validated structurally. Fails closed."""
    where = path or "<document>"
    data = _require_keys(where, document, FILE_KEYS, {"schema", "vectors"})
    if data["schema"] != VECTOR_SCHEMA:
        raise VectorError(f"{where}: schema {data['schema']!r} is not {VECTOR_SCHEMA}")
    if not isinstance(data["vectors"], list) or not data["vectors"]:
        raise VectorError(f"{where}: vectors must be a non-empty list")
    parsed: list[Vector] = []
    for index, item in enumerate(data["vectors"]):
        label = f"{where}[{index}]"
        entry = _require_keys(label, item, VECTOR_KEYS, REQUIRED_VECTOR_KEYS)
        case = entry["case"]
        if not isinstance(case, str) or not case:
            raise VectorError(f"{label}: case must be a non-empty string")
        kind = entry["kind"]
        if kind not in KINDS:
            raise VectorError(f"{where}[{case}]: unknown kind {kind!r}, known kinds are {list(KINDS)}")
        validator = {"vital": _validate_vital, "delta": _validate_delta}[kind]
        validator(f"{where}[{case}]", entry["given"], entry["expect"])
        parsed.append(
            Vector(
                case=case,
                title=entry["title"],
                kind=kind,
                given=entry["given"],
                expect=entry["expect"],
                source_unit=entry.get("source_unit"),
                notes=entry.get("notes"),
                path=path,
            )
        )
    return parsed


def load_file(path: str | Path) -> list[Vector]:
    path = Path(path)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VectorError(f"{path}: {exc}") from exc
    return parse_document(document, str(path))


def load(paths: Iterable[str | Path]) -> list[Vector]:
    """Vectors of every given file or directory, ordered by case id, with unique case ids."""
    files: list[Path] = []
    for entry in paths:
        entry = Path(entry)
        if entry.is_dir():
            files.extend(sorted(entry.rglob("*.json")))
        elif entry.exists():
            files.append(entry)
        else:
            raise VectorError(f"{entry}: no such file or directory")
    vectors: list[Vector] = []
    seen: dict[str, str] = {}
    for file in files:
        for vector in load_file(file):
            if vector.case in seen:
                raise VectorError(f"duplicate case {vector.case} in {vector.path} and {seen[vector.case]}")
            seen[vector.case] = vector.path
            vectors.append(vector)
    return sorted(vectors, key=lambda vector: (vector.case, vector.path))


# --------------------------------------------------------------------------- execution


def _observation_set(given: dict[str, Any], case: str) -> ObservationSet:
    observed_at = given.get("observed_at", DEFAULT_OBSERVED_AT)
    obs = ObservationSet(subject=dict(given.get("subject") or DEFAULT_SUBJECT), observed_at=observed_at)
    for envelope in given["observations"]:
        if not isinstance(envelope, dict) or "observation_id" not in envelope:
            raise VectorError(f"{case}: an observation envelope needs an observation_id")
        filled = dict(envelope)
        filled.setdefault("status", "AVAILABLE")
        filled.setdefault("provider", "vector")
        filled.setdefault("collected_at", observed_at)
        filled.setdefault("source_ref", f"vector:{case}")
        filled.setdefault("adapter_version", VECTOR_SCHEMA)
        obs.add(Observation.from_dict(filled))
    return obs


def _matches(expected: str, emitted: list[str]) -> bool:
    """A code expectation matches a code it equals or is a prefix of."""
    return any(code == expected or code.startswith(expected) for code in emitted)


def _check_codes(kind: str, expected: Any, absent: Any, emitted: list[str], failures: list[str]) -> None:
    for code in expected or []:
        if not _matches(code, emitted):
            failures.append(f"{kind}: expected {code!r}, emitted {emitted}")
    for code in absent or []:
        if _matches(code, emitted):
            failures.append(f"{kind}: {code!r} must not be emitted, emitted {emitted}")


def _check_equal(what: str, expected: Any, actual: Any, failures: list[str]) -> None:
    if expected != actual:
        failures.append(f"{what}: expected {expected!r}, got {actual!r}")


def _run_vital(vector: Vector) -> list[str]:
    failures: list[str] = []
    obs = _observation_set(vector.given, vector.case)
    result = EVALUATORS[vector.given["vital"]](obs).to_dict()
    expect = vector.expect
    for key in ("band", "evaluation_status", "band_semantics", "possible_bands", "rule_id"):
        if key in expect:
            _check_equal(key, expect[key], result.get(key), failures)
    for key, value in (expect.get("derived") or {}).items():
        if key not in result["derived"]:
            failures.append(f"derived.{key}: expected {value!r}, the Vital derived no such metric")
        else:
            _check_equal(f"derived.{key}", value, result["derived"][key], failures)
    for key in expect.get("derived_absent") or []:
        if key in result["derived"]:
            failures.append(f"derived.{key}: must be absent, got {result['derived'][key]!r}")
    _check_codes("diagnostics", expect.get("diagnostics"), expect.get("diagnostics_absent"), result["diagnostics"], failures)
    for text in expect.get("explanation_contains") or []:
        if text not in result["explanation"]:
            failures.append(f"explanation: {text!r} not in {result['explanation']!r}")
    return failures


def _delta_row(row: dict[str, Any]) -> dict[str, Any]:
    """A partial Vital row completed with the defaults a vector may leave out."""
    band = row.get("band")
    return {
        "vital_id": row["vital_id"],
        "band": band,
        "evaluation_status": row.get("evaluation_status", "AVAILABLE" if band is not None else "UNKNOWN"),
        "band_semantics": row.get("band_semantics", "EXACT" if band is not None else None),
        "rule_id": row.get("rule_id", f"{row['vital_id']}.vector"),
        "derived": row.get("derived") or {},
        "inputs": row.get("inputs") or [],
    }


def _delta_side(side: dict[str, Any]) -> dict[str, Any]:
    return {
        "observed_at": side.get("observed_at", DEFAULT_OBSERVED_AT),
        "vitals": [_delta_row(row) for row in side["vitals"]],
    }


def _run_delta(vector: Vector) -> list[str]:
    failures: list[str] = []
    given = vector.given
    document = compare(
        _delta_side(given["current"]),
        _delta_side(given["previous"]),
        given.get("comparison_status", COMPARABLE),
        given.get("previous_bundle_id"),
        given.get("incomparable_reasons"),
    )
    rows = {row["vital_id"]: row for row in document["vitals"]}
    if "comparison_status" in vector.expect:
        _check_equal("comparison_status", vector.expect["comparison_status"], document["comparison_status"], failures)
    for vital_id, expect in vector.expect["vitals"].items():
        row = rows[vital_id]
        _check_equal(f"{vital_id}.transition_class", expect["transition_class"], row["transition_class"], failures)
        _check_codes(f"{vital_id}.reason_codes", expect.get("reason_codes"), expect.get("reason_codes_absent"), row["reason_codes"], failures)
        for key in ("metric_deltas", "coverage_delta"):
            if key in expect:
                _check_equal(f"{vital_id}.{key}", expect[key], row[key], failures)
    return failures


RUNNERS = {"vital": _run_vital, "delta": _run_delta}


def run(vector: Vector) -> VectorResult:
    """Execute one vector. A vector that cannot run is a failure, never a skip."""
    runner = RUNNERS.get(vector.kind)
    if runner is None:  # unreachable through load(); reachable through a hand-built Vector
        return VectorResult(vector, [f"unknown kind {vector.kind!r}"])
    try:
        return VectorResult(vector, runner(vector))
    except Exception as exc:  # noqa: BLE001 - a vector must report, never crash the suite
        return VectorResult(vector, [f"{type(exc).__name__}: {exc}"])


def run_all(vectors: Iterable[Vector]) -> list[VectorResult]:
    return [run(vector) for vector in vectors]
