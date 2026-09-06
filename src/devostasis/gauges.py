"""Non-authoritative 0-100 gauges derived from canonical bands and metrics (``devostasis.gauge.v1``).

A gauge is a presentation aid: it places a Vital on a 0-100 scale so that a
human sees gradation inside a band instead of a binary label. Gauges are
computed deterministically from the authoritative snapshot (band plus the
derived metrics the rule actually used) with integer arithmetic. They are
never part of ``snapshot.json``; they are persisted as the identity-bearing
member ``gauges.json`` (``gauges_digest`` enters the bundle identity), and no
consumer may treat them as machine truth: the named band and the observations
remain canonical. Gauges of different Vitals measure different phenomena and
are never compared with each other or summed (accepted by PV-REV-GAUGE-001).

Each gauge measures the *intensity of the phenomenon the Vital describes*,
not virtue: Clutter 90 means a lot of residue, Flow 90 means a lot of queue
pressure, Integrity 90 means stable verification, Debt 90 means a lot of
registered debt.
"""

from __future__ import annotations

from typing import Any

GAUGE_CONTRACT = "devostasis.gauge.v1"

SCALES = {
    "pulse": "activity intensity",
    "flow": "queue pressure",
    "integrity": "verification stability",
    "clutter": "stale residue",
    "horizon": "declared future work",
    "direction": "traceability share",
    "debt": "registered debt",
}

BAND_RANGES: dict[str, dict[str, tuple[int, int]]] = {
    "pulse": {"DORMANT": (0, 0), "QUIET": (5, 30), "STEADY": (35, 70), "SURGING": (75, 100)},
    "flow": {"NO_QUEUE": (0, 0), "MOVING": (5, 30), "CONGESTED": (35, 70), "GRIDLOCKED": (75, 100)},
    "clutter": {"CLEAN": (0, 0), "LIGHT": (5, 30), "CLUTTERED": (35, 70), "HEAVY": (75, 100)},
    "integrity": {"FAILING": (0, 24), "SPARSE_MIXED": (25, 49), "FLAKY": (50, 74), "SPARSE": (75, 87), "CLEAN": (88, 100)},
    "horizon": {"UNDECLARED": (0, 0), "DECLARED": (10, 40), "VISIBLE": (45, 75), "EXTENDED": (80, 100)},
    "direction": {"SCATTERED": (0, 49), "MIXED": (50, 99), "FULLY_LINKED": (100, 100), "UNDECLARED": (0, 0)},
    "debt": {"CLEAR": (0, 0), "PRESENT": (10, 100)},
}


def _num(value: Any, default: int = 0) -> int:
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, int):
        return value
    return default


def _part(value: int, cap: int, width: int) -> int:
    """width * clamp(value, 0, cap) / cap with integer arithmetic."""
    if cap <= 0:
        return 0
    return width * min(max(value, 0), cap) // cap


def _ratio(record: Any) -> tuple[int, int] | None:
    if isinstance(record, dict) and isinstance(record.get("num"), int) and isinstance(record.get("den"), int) and record["den"] > 0:
        return record["num"], record["den"]
    return None


def _pulse(band: str, d: dict[str, Any]) -> int | None:
    events = _num(d.get("activity_events_28d"))
    days = _num(d.get("commit_active_days_28d"))
    if band == "DORMANT":
        return 0
    if band == "QUIET":
        return 5 + 5 * min(events, 4)
    if band == "STEADY":
        return 35 + max(_part(events - 5, 35, 35), _part(days - 3, 12, 35))
    if band == "SURGING":
        return 75 + max(_part(events - 40, 160, 25), _part(days - 15, 13, 25))
    return None


def _flow(band: str, d: dict[str, Any]) -> int | None:
    open_count = _num(d.get("open_count"))
    oldest = _num(d.get("oldest_open_age_days"))
    median = _num(d.get("median_time_to_merge_hours_28d"))
    if band == "NO_QUEUE":
        return 0
    if band == "MOVING":
        return 5 + max(_part(open_count - 1, 8, 25), _part(oldest, 13, 25))
    if band == "CONGESTED":
        return 35 + max(_part(open_count - 10, 20, 35), _part(oldest - 14, 16, 35), _part(median - 168, 168, 35))
    if band == "GRIDLOCKED":
        return 75 + max(_part(open_count - 10, 40, 25), _part(oldest - 30, 60, 25), _part(median - 336, 336, 25))
    return None


def _clutter(band: str, d: dict[str, Any]) -> int | None:
    stale = _num(d.get("stale_work_count"))
    branches = _num(d.get("stale_branch_count"))
    ratio = _ratio(d.get("stale_work_ratio"))
    if band == "CLEAN":
        return 0
    if band == "LIGHT":
        return 5 + max(5 * min(stale, 4), 4 * min(branches, 5))
    if band == "CLUTTERED":
        parts = [_part(stale - 5, 19, 35), _part(branches - 6, 13, 35)]
        if ratio:
            num, den = ratio
            parts.append(_part(4 * num - den, den, 35))
        return 35 + max(parts)
    if band == "HEAVY":
        parts = [_part(stale - 25, 75, 25), _part(branches - 20, 30, 25)]
        if ratio:
            num, den = ratio
            parts.append(_part(2 * num - den, den, 25))
        return 75 + max(parts)
    return None


def _integrity(band: str, d: dict[str, Any]) -> int | None:
    decisive = _num(d.get("decisive_count_14d"))
    failed = _num(d.get("failed_count_14d"))
    passes = max(decisive - failed, 0)
    if band == "FAILING":
        return _part(passes, decisive, 24) if decisive else 0
    if band == "SPARSE_MIXED":
        return 25 + (_part(passes, decisive, 24) if decisive else 0)
    if band == "FLAKY":
        return 50 + (_part(decisive - 4 * failed, decisive, 24) if decisive else 0)
    if band == "SPARSE":
        return 75 + 6 * min(max(decisive - 1, 0), 2)
    if band == "CLEAN":
        return 88 + _part(decisive - 4, 20, 12)
    return None


def _horizon(band: str, d: dict[str, Any]) -> int | None:
    if d.get("capability") == "UNSUPPORTED":
        return None
    open_count = _num(d.get("open_count"))
    future = _num(d.get("open_with_future_boundary_count"))
    beyond = _num(d.get("open_beyond_28d_count"))
    if band == "UNDECLARED":
        return 0
    if band == "DECLARED":
        return 10 + _part(open_count, 6, 30)
    if band == "VISIBLE":
        return 45 + _part(future, 6, 30)
    if band == "EXTENDED":
        return 80 + _part(beyond, 5, 20)
    return None


def _direction(band: str, d: dict[str, Any]) -> int | None:
    if band == "NO_ACTIVE_CHANGE" or d.get("capability") == "UNSUPPORTED":
        return None
    if band == "UNDECLARED":
        return 0
    active = _num(d.get("active_change_count_28d"))
    linked = _num(d.get("linked_active_change_count_28d"))
    if band in ("SCATTERED", "MIXED", "FULLY_LINKED") and active > 0:
        return 100 * linked // active
    return None


def _debt(band: str, d: dict[str, Any]) -> int | None:
    if band == "UNINSTRUMENTED":
        return None
    if band == "CLEAR":
        return 0
    if band == "PRESENT":
        open_count = _num(d.get("open_count"))
        stale = _num(d.get("open_stale_count_30d"))
        return 10 + _part(open_count, 50, 70) + _part(stale, 20, 20)
    return None


COMPUTE = {
    "pulse": _pulse,
    "flow": _flow,
    "clutter": _clutter,
    "integrity": _integrity,
    "horizon": _horizon,
    "direction": _direction,
    "debt": _debt,
}


def gauge_for(vital: dict[str, Any]) -> dict[str, Any]:
    """Gauge record for one canonical Vital result (snapshot entry)."""
    vital_id = vital["vital_id"]
    band = vital.get("band")
    derived = vital.get("derived") or {}
    value = COMPUTE[vital_id](band, derived) if band is not None else None
    if value is not None:
        value = max(0, min(100, int(value)))
    if value is None:
        qualifier = None
    elif vital.get("evaluation_status") == "AVAILABLE":
        qualifier = "exact"
    elif vital.get("band_semantics") == "CONSERVATIVE_LOWER_BOUND":
        qualifier = "at_least"
    elif vital.get("band_semantics") == "CONSERVATIVE_UPPER_BOUND":
        qualifier = "at_most"
    else:
        qualifier = "approximate"
    return {
        "vital_id": vital_id,
        "band": band,
        "value": value,
        "qualifier": qualifier,
        "scale": SCALES[vital_id],
        "contract": GAUGE_CONTRACT,
        "canonical_semantics": "snapshot.json",
    }


def gauges_for_snapshot(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [gauge_for(vital) for vital in snapshot.get("vitals", [])]


def gauge_values(snapshot: dict[str, Any]) -> dict[str, int | None]:
    return {g["vital_id"]: g["value"] for g in gauges_for_snapshot(snapshot)}


def gauges_member(snapshot: dict[str, Any]) -> dict[str, Any]:
    """The ``gauges.json`` bundle member: a versioned normalization of the snapshot."""
    return {
        "schema": "devostasis.gauges.v1",
        "contract": GAUGE_CONTRACT,
        "observed_at": snapshot.get("observed_at"),
        "canonical_semantics": "snapshot.json",
        "contract_status": "implementation-defined ranges; submitted for independent review",
        "gauges": gauges_for_snapshot(snapshot),
    }


def bar(value: int | None, width: int = 10) -> str:
    """Text bar; an unknown value renders as an empty bar."""
    if value is None:
        return "░" * width
    filled = (value * width + 50) // 100
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def value_text(gauge: dict[str, Any]) -> str:
    value = gauge.get("value")
    if value is None:
        return "n/a"
    prefix = {"at_least": "≥", "at_most": "≤", "approximate": "~"}.get(gauge.get("qualifier") or "", "")
    return f"{prefix}{value}"
