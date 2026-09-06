"""Machine-readable fleet index (``devostasis.fleet.v1``).

``projects/README.md`` is written for a human and cannot be parsed without
guessing. A control plane that routes attention across many projects needs the
same facts as data, so a store also carries ``projects/index.json``.

The index adds no meaning. Every value in it comes from the latest bundle of
each project, and the bundle stays authoritative: a consumer that needs
provenance, coverage or the reasoning behind a band reads the bundle the entry
points at.

Two things are deliberately absent.

* There is no aggregate, per project or across projects. The seven Vitals
  share signals and are not independent votes, so no scalar is computed from
  them, and none may be computed from this file either.
* There is no cross-project ranking. Demand levels order Vitals inside one
  project, and no accepted contract defines what it means for one project's
  CRITICAL to outrank another's. A consumer that wants a fleet-wide order
  applies its own policy to this data and owns that decision.
"""

from __future__ import annotations

from typing import Any

from .contracts import CORE_VITAL_IDS, FLEET_SCHEMA

DEMAND_MEMBER = "demand.json"


def _vitals(entry: dict[str, Any]) -> dict[str, Any]:
    """One row per Vital: the band, its evaluation, the gauge and the demand level.

    Bands and gauges come from the project's chronological index; the
    evaluation status and the demand level come from the latest bundle's
    ``demand.json``. A bundle written before the demand interface existed has
    no such member, so those two fields are null rather than invented.
    """
    bands = entry.get("bands") or {}
    gauges = entry.get("gauges") or {}
    demand_rows = {row["vital_id"]: row for row in (entry.get("demand_rows") or [])}
    vitals: dict[str, Any] = {}
    for vital_id in CORE_VITAL_IDS:
        row = demand_rows.get(vital_id, {})
        vitals[vital_id] = {
            "band": row.get("band", bands.get(vital_id)),
            "evaluation_status": row.get("evaluation_status"),
            "gauge": row.get("gauge", gauges.get(vital_id)),
            "level": row.get("level"),
        }
    return vitals


def project_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "project_key": entry.get("project_key"),
        "locator": entry.get("locator"),
        "immutable_project_id": entry.get("immutable_project_id"),
        "observed_at": entry.get("observed_at"),
        "bundle_id": entry.get("bundle_id"),
        "comparison_status": entry.get("comparison_status"),
        "previous_bundle_id": entry.get("previous_bundle_id"),
        "attention": entry.get("top_attention"),
        "attention_order": list(entry.get("attention_order") or []),
        "vitals": _vitals(entry),
        "report_path": entry.get("report_path"),
        "bundle_path": entry.get("bundle_path"),
    }


def build_index(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """The fleet index document, ordered by project key so the file is stable."""
    return {
        "schema": FLEET_SCHEMA,
        "canonical_semantics": "the snapshot.json of each project's bundle",
        "aggregate": None,
        "cross_project_order": None,
        "projects": [project_entry(entry) for entry in sorted(entries, key=lambda item: item.get("project_key") or "")],
    }
