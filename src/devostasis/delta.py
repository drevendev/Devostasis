"""Deterministic previous-vs-current comparison of two snapshots.

Comparison states: BASELINE (no prior bundle), COMPARABLE, HISTORY_GAP (history
expected but the previous bundle cannot be loaded or verified) and INCOMPARABLE
(semantic versions or semantic configuration differ). Only COMPARABLE emits
UNCHANGED/CHANGED/IMPROVED/WORSENED.

A changed band is IMPROVED or WORSENED only where the Vital declares a
normative order over that pair of bands (``order.py``, PV-BAND-ORDER-001) and
both sides are exact measurements: the pair is COMPARABLE, the ``rule_id`` is
unchanged, and both evaluations are AVAILABLE with EXACT band semantics.
Everything else stays CHANGED and says why in a reason code. Observability
transitions and the rule version boundary keep precedence over the order, and
gauges never establish one.

Inside a COMPARABLE bundle a single Vital whose rule version changed since the
previous bundle is INCOMPARABLE on its own (``RULE_VERSION_BOUNDARY``): a rule
repair never reinterprets the historical band, and the other six Vitals keep
comparing.
"""

from __future__ import annotations

from typing import Any

from . import order
from .canonical import rational_parts
from .contracts import BAND_ORDER_CONTRACT, BAND_ORDER_VERSION, CORE_VITAL_IDS, DELTA_SCHEMA

BASELINE = "BASELINE"
COMPARABLE = "COMPARABLE"
HISTORY_GAP = "HISTORY_GAP"
INCOMPARABLE = "INCOMPARABLE"

T_BASELINE = "BASELINE"
T_UNCHANGED = "UNCHANGED"
T_CHANGED = "CHANGED"
T_IMPROVED = order.IMPROVED
T_WORSENED = order.WORSENED
T_GAINED = "OBSERVABILITY_GAINED"
T_LOST = "OBSERVABILITY_LOST"
T_INCOMPARABLE = "INCOMPARABLE"

EVAL_RANK = {"UNKNOWN": 0, "DEGRADED": 1, "AVAILABLE": 2}


def _numeric(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    return rational_parts(value) is not None


def _metric_deltas(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    deltas: dict[str, Any] = {}
    for key in sorted(set(previous) | set(current)):
        before = previous.get(key)
        after = current.get(key)
        if not (_numeric(before) or _numeric(after)):
            continue
        if before == after:
            continue
        entry: dict[str, Any] = {"previous": before, "current": after}
        if isinstance(before, int) and isinstance(after, int) and not isinstance(before, bool) and not isinstance(after, bool):
            entry["change"] = after - before
        deltas[key] = entry
    return deltas


def _coverage_delta(previous: list[dict[str, str]], current: list[dict[str, str]]) -> list[dict[str, Any]]:
    prev_map = {item["observation_id"]: item for item in previous}
    cur_map = {item["observation_id"]: item for item in current}
    changes = []
    for oid in sorted(set(prev_map) | set(cur_map)):
        before = prev_map.get(oid)
        after = cur_map.get(oid)
        b = (before or {}).get("status"), (before or {}).get("freshness")
        a = (after or {}).get("status"), (after or {}).get("freshness")
        if b != a:
            changes.append({"observation_id": oid, "previous": {"status": b[0], "freshness": b[1]}, "current": {"status": a[0], "freshness": a[1]}})
    return changes


def _transition(vital_id: str, previous: dict[str, Any], current: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    p_rule, c_rule = previous.get("rule_id"), current.get("rule_id")
    if p_rule != c_rule:
        return T_INCOMPARABLE, [f"RULE_VERSION_BOUNDARY:{p_rule}->{c_rule}"]
    p_band, c_band = previous.get("band"), current.get("band")
    p_eval, c_eval = previous.get("evaluation_status"), current.get("evaluation_status")
    if p_band is None and c_band is None:
        return T_UNCHANGED, ["UNKNOWN_BOTH"]
    if p_band is None and c_band is not None:
        return T_GAINED, ["BAND_BECAME_OBSERVABLE"]
    if p_band is not None and c_band is None:
        return T_LOST, ["BAND_NO_LONGER_OBSERVABLE"]
    if p_band != c_band:
        reasons.append(f"BAND:{p_band}->{c_band}")
        if p_eval != c_eval:
            reasons.append(f"EVALUATION_STATUS:{p_eval}->{c_eval}")
        moved, order_reason = order.classify(vital_id, previous, current)
        reasons.append(order_reason)
        if moved == order.IMPROVED:
            return T_IMPROVED, reasons
        if moved == order.WORSENED:
            return T_WORSENED, reasons
        return T_CHANGED, reasons
    if p_eval != c_eval:
        reasons.append(f"EVALUATION_STATUS:{p_eval}->{c_eval}")
        if EVAL_RANK.get(c_eval, 0) > EVAL_RANK.get(p_eval, 0):
            return T_GAINED, reasons
        return T_LOST, reasons
    if previous.get("band_semantics") != current.get("band_semantics"):
        reasons.append(f"BAND_SEMANTICS:{previous.get('band_semantics')}->{current.get('band_semantics')}")
    return T_UNCHANGED, reasons


def compare(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    comparison_status: str,
    previous_bundle_id: str | None,
    reasons: list[str] | None = None,
) -> dict[str, Any]:
    reasons = list(reasons or [])
    prev_vitals = {item["vital_id"]: item for item in (previous or {}).get("vitals", [])}
    cur_vitals = {item["vital_id"]: item for item in current.get("vitals", [])}
    rows = []
    for vital_id in CORE_VITAL_IDS:
        cur = cur_vitals.get(vital_id) or {}
        prev = prev_vitals.get(vital_id) if comparison_status == COMPARABLE else None
        row: dict[str, Any] = {
            "vital_id": vital_id,
            "previous_band": (prev or {}).get("band") if prev is not None else None,
            "current_band": cur.get("band"),
            "previous_evaluation_status": (prev or {}).get("evaluation_status") if prev is not None else None,
            "current_evaluation_status": cur.get("evaluation_status"),
            "metric_deltas": {},
            "coverage_delta": [],
            "reason_codes": [],
        }
        if comparison_status == BASELINE:
            row["transition_class"] = T_BASELINE
            row["reason_codes"] = ["NO_PREVIOUS_BUNDLE"]
        elif comparison_status != COMPARABLE:
            row["transition_class"] = T_INCOMPARABLE
            row["reason_codes"] = [comparison_status] + reasons
        elif prev is None:
            row["transition_class"] = T_INCOMPARABLE
            row["reason_codes"] = ["PREVIOUS_VITAL_MISSING"]
        else:
            transition, codes = _transition(vital_id, prev, cur)
            row["transition_class"] = transition
            row["reason_codes"] = codes
            if transition != T_INCOMPARABLE:
                row["metric_deltas"] = _metric_deltas(prev.get("derived") or {}, cur.get("derived") or {})
            row["coverage_delta"] = _coverage_delta(prev.get("inputs") or [], cur.get("inputs") or [])
        rows.append(row)
    return {
        "schema": DELTA_SCHEMA,
        "band_order_contract": BAND_ORDER_CONTRACT,
        "band_order_version": BAND_ORDER_VERSION,
        "comparison_status": comparison_status,
        "previous_bundle_id": previous_bundle_id,
        "previous_observed_at": (previous or {}).get("observed_at") if comparison_status == COMPARABLE else None,
        "current_observed_at": current.get("observed_at"),
        "incomparable_reasons": sorted(set(reasons)) if comparison_status in (INCOMPARABLE, HISTORY_GAP) else [],
        "vitals": rows,
    }


def normalize_semantic_config(config: dict[str, Any] | None) -> dict[str, Any] | None:
    """Bring the semantic config of an older bundle to the current shape without changing its meaning.

    Bundles written by devostasis.bundle.v1 recorded ``planning_source`` and a
    debt mapping without ``source``; those are the same semantics as the
    current ``planning`` object with default path and marker and a ``labels``
    debt source.
    """
    if not isinstance(config, dict):
        return config
    result = dict(config)
    if "planning" not in result and "planning_source" in result:
        result["planning"] = {"source": result.pop("planning_source"), "path": None, "link_marker": "Target:"}
    debt = result.get("debt_mapping")
    if isinstance(debt, dict) and "source" not in debt:
        result["debt_mapping"] = {"source": "labels", "labels": sorted(debt.get("labels") or []), "mapping_version": debt.get("mapping_version")}
    return result


def compatibility_reasons(current_manifest_fields: dict[str, Any], previous_manifest: dict[str, Any]) -> list[str]:
    """Reasons two bundles cannot be compared: semantic version or semantic config boundaries."""
    reasons = []
    for key in ("vitals_contract_version", "observation_contract_version", "policy_version"):
        if previous_manifest.get(key) != current_manifest_fields.get(key):
            reasons.append(f"VERSION_BOUNDARY:{key}:{previous_manifest.get(key)}->{current_manifest_fields.get(key)}")
    if normalize_semantic_config(previous_manifest.get("semantic_config")) != normalize_semantic_config(current_manifest_fields.get("semantic_config")):
        reasons.append("SEMANTIC_CONFIG_CHANGED")
    return reasons
