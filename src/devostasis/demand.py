"""Generic consumer demand interface (``devostasis.demand.v2``).

Demand answers "how much attention does this Vital call for" with a small
ordered vocabulary that autonomous development systems can consume opaquely:
CRITICAL, HIGH, MEDIUM, LOW, MINIMAL, plus UNRESOLVED when the Vital has no
band (missing evidence must never look like low demand). Levels come from a
versioned mapping band -> level.

The attention order ranks Vitals by level and then by the canonical Vital
order. Gauges are carried for presentation and provenance only: they measure
different phenomena on different scales and are never compared across Vitals
(PV-ROLE-001 finding ROLE-01, SAME_LEVEL_GAUGE_INVARIANCE). Version 2 removed
the gauge tie-break of version 1 for that reason.

There is deliberately no aggregate: an attention *order* is emitted, never a
sum or a score, because the seven Vitals share signals and are not
independent votes.
"""

from __future__ import annotations

from typing import Any

from .contracts import CORE_VITAL_IDS, DEMAND_CONTRACT

DEMAND_SCHEMA = DEMAND_CONTRACT
LEVELS = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL")
UNRESOLVED = "UNRESOLVED"
RANK = {UNRESOLVED: -1, "CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "MINIMAL": 4}

DEFAULT_LEVELS: dict[str, dict[str, str]] = {
    "pulse": {"DORMANT": "MEDIUM", "QUIET": "LOW", "STEADY": "MINIMAL", "SURGING": "MINIMAL"},
    "flow": {"NO_QUEUE": "MINIMAL", "MOVING": "LOW", "CONGESTED": "HIGH", "GRIDLOCKED": "CRITICAL"},
    "integrity": {
        "UNINSTRUMENTED": "HIGH",
        "NO_RECENT_RUNS": "LOW",
        "NO_DECISIVE_RUNS": "MEDIUM",
        "SPARSE": "LOW",
        "SPARSE_MIXED": "HIGH",
        "FLAKY": "HIGH",
        "CLEAN": "MINIMAL",
        "FAILING": "CRITICAL",
    },
    "clutter": {"CLEAN": "MINIMAL", "LIGHT": "LOW", "CLUTTERED": "MEDIUM", "HEAVY": "HIGH"},
    "horizon": {"UNDECLARED": "MEDIUM", "DECLARED": "LOW", "VISIBLE": "MINIMAL", "EXTENDED": "MINIMAL"},
    "direction": {"NO_ACTIVE_CHANGE": "MINIMAL", "UNDECLARED": "MEDIUM", "SCATTERED": "HIGH", "MIXED": "MEDIUM", "FULLY_LINKED": "MINIMAL"},
    "debt": {"UNINSTRUMENTED": "LOW", "CLEAR": "MINIMAL", "PRESENT": "MEDIUM"},
}
DEFAULT_MAPPING_VERSION = "devostasis-default-1"


def order_key(row: dict[str, Any]) -> tuple[int, int]:
    """Level rank first, then the canonical Vital order; never a gauge (ROLE-01)."""
    return (RANK[row["level"]], CORE_VITAL_IDS.index(row["vital_id"]))


def build_demand(snapshot: dict[str, Any], gauges: list[dict[str, Any]], config: dict[str, Any]) -> dict[str, Any]:
    levels_table = config.get("levels") or DEFAULT_LEVELS
    gauge_by_id = {g["vital_id"]: g for g in gauges}
    rows = []
    for vital in snapshot["vitals"]:
        vital_id = vital["vital_id"]
        band = vital.get("band")
        gauge = gauge_by_id.get(vital_id, {}).get("value")
        if band is None:
            level, reason = UNRESOLVED, "EVALUATION_UNKNOWN"
        else:
            level = (levels_table.get(vital_id) or {}).get(band)
            if level is None:
                level, reason = UNRESOLVED, f"BAND_UNMAPPED:{band}"
            else:
                reason = f"BAND:{band}"
        rows.append(
            {
                "vital_id": vital_id,
                "band": band,
                "evaluation_status": vital.get("evaluation_status"),
                "gauge": gauge,
                "level": level,
                "reason": reason,
            }
        )
    order = sorted(rows, key=order_key)
    return {
        "schema": DEMAND_SCHEMA,
        "contract": DEMAND_CONTRACT,
        "mapping_version": config.get("mapping_version") or DEFAULT_MAPPING_VERSION,
        "observed_at": snapshot.get("observed_at"),
        "canonical_semantics": "snapshot.json",
        "levels": list(LEVELS) + [UNRESOLVED],
        "aggregate": None,
        "vitals": rows,
        "attention_order": [{"vital_id": r["vital_id"], "level": r["level"]} for r in order],
    }


def top_attention(demand: dict[str, Any]) -> str | None:
    order = demand.get("attention_order") or []
    if not order:
        return None
    first = order[0]
    return f"{first['vital_id']} {first['level']}"
