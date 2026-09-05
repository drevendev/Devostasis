"""Deterministic Markdown renderer (``devostasis.render.v1``).

The renderer is a pure function of the canonical bundle: it adds no health
semantics, no scores, no colours and no evaluative aliases. Neutral bands such
as Direction FULLY_LINKED and Debt PRESENT stay neutral.
"""

from __future__ import annotations

from typing import Any

from .canonical import ratio_text

VITAL_TITLES = {
    "horizon": "Horizon",
    "clutter": "Clutter",
    "direction": "Direction",
    "flow": "Flow",
    "integrity": "Integrity",
    "debt": "Debt",
    "pulse": "Pulse",
}

VITAL_QUESTIONS = {
    "horizon": "Is future work explicitly declared, and does any declaration reach beyond 28 days?",
    "clutter": "How much unresolved stale residue is observable?",
    "direction": "Is active change work explicitly traceable to declared targets?",
    "flow": "What is the state and friction of the current change-request queue?",
    "integrity": "What does automated verification say about recent immutable revisions?",
    "debt": "How much explicitly registered maintenance obligation is unresolved?",
    "pulse": "How intense is recent observable activity?",
}


def _band(vital: dict[str, Any]) -> str:
    return vital.get("band") or "UNKNOWN"


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict) and set(value) == {"num", "den"}:
        return f"{ratio_text(value)} ({value['num']}/{value['den']})"
    if isinstance(value, dict):
        return ", ".join(f"{k}={_fmt(v)}" for k, v in sorted(value.items())) or "none"
    if isinstance(value, list):
        return ", ".join(_fmt(v) for v in value) or "none"
    return str(value)


def _metric_rows(derived: dict[str, Any]) -> list[str]:
    rows = []
    for key in sorted(derived):
        value = derived[key]
        if isinstance(value, dict) and set(value) != {"num", "den"}:
            continue
        rows.append(f"| {key} | {_fmt(value)} |")
    return rows


def render_report(manifest: dict[str, Any], snapshot: dict[str, Any], delta: dict[str, Any], activity: dict[str, Any] | None) -> str:
    identity = manifest["project_identity"]
    lines: list[str] = []
    lines.append(f"# Devostasis report: {identity['display_locator']}")
    lines.append("")
    lines.append(f"- Observed at: {manifest['observed_at']}")
    lines.append(f"- Comparison: {manifest['comparison_status']}" + (f" (previous bundle `{manifest['previous_bundle_id']}`)" if manifest.get("previous_bundle_id") else ""))
    lines.append(f"- Bundle: `{manifest['bundle_id']}`")
    lines.append(f"- Contracts: vitals {manifest['vitals_contract_version']}, observations {manifest['observation_contract_version']}, policy {manifest['policy_version']}")
    lines.append("")
    lines.append("Bands are descriptive states, not grades, and there is no composite number. UNKNOWN means evidence was insufficient; DEGRADED means the band is a conservative bound.")
    lines.append("")

    lines.append("## Vitals")
    lines.append("")
    lines.append("| Vital | Band | Evaluation | Semantics | Explanation |")
    lines.append("| --- | --- | --- | --- | --- |")
    for vital in snapshot["vitals"]:
        lines.append(
            f"| {VITAL_TITLES[vital['vital_id']]} | {_band(vital)} | {vital['evaluation_status']} | {vital.get('band_semantics') or 'n/a'} | {vital.get('explanation', '')} |"
        )
    lines.append("")

    for vital in snapshot["vitals"]:
        lines.append(f"### {VITAL_TITLES[vital['vital_id']]}: {_band(vital)}")
        lines.append("")
        lines.append(f"_{VITAL_QUESTIONS[vital['vital_id']]}_")
        lines.append("")
        lines.append(f"- Evaluation: {vital['evaluation_status']}; rule `{vital['rule_id']}`")
        if vital.get("possible_bands"):
            lines.append(f"- Possible bands (conservative superset): {', '.join(vital['possible_bands'])}")
        if vital.get("dependency_group_ids"):
            lines.append(f"- Shares signals with: {', '.join(vital['dependency_group_ids'])}")
        metric_rows = _metric_rows(vital.get("derived") or {})
        if metric_rows:
            lines.append("")
            lines.append("| Metric | Value |")
            lines.append("| --- | --- |")
            lines.extend(metric_rows)
        if vital.get("diagnostics"):
            lines.append("")
            lines.append("Diagnostics:")
            for code in vital["diagnostics"]:
                lines.append(f"- `{code}`")
        lines.append("")

    lines.append("## Observability")
    lines.append("")
    receipt = manifest.get("receipt") or {}
    non_available = [
        (key, meta) for key, meta in sorted((receipt.get("per_key") or {}).items())
        if meta.get("status") != "AVAILABLE" or meta.get("freshness") != "FRESH"
    ]
    if non_available:
        lines.append("| Observation | Status | Freshness |")
        lines.append("| --- | --- | --- |")
        for key, meta in non_available:
            lines.append(f"| {key} | {meta.get('status')} | {meta.get('freshness')} |")
    else:
        lines.append("Every requested observation was available and fresh.")
    if receipt.get("capability_notes"):
        lines.append("")
        lines.append("Capability notes:")
        for note in receipt["capability_notes"]:
            lines.append(f"- `{note}`")
    lines.append("")

    lines.append("## Changes since previous bundle")
    lines.append("")
    status = delta["comparison_status"]
    if status == "BASELINE":
        lines.append("This is the first canonical bundle for the project: there is no previous state to compare against.")
    elif status == "HISTORY_GAP":
        lines.append("History exists but the previous bundle could not be loaded or verified. No change is inferred.")
    elif status == "INCOMPARABLE":
        lines.append("The previous bundle was produced under different semantics: " + "; ".join(delta.get("incomparable_reasons") or []) + ". No change is inferred.")
    else:
        lines.append(f"Compared with the bundle observed at {delta.get('previous_observed_at')}.")
        lines.append("")
        lines.append("| Vital | Previous | Current | Transition | Reasons |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in delta["vitals"]:
            lines.append(
                f"| {VITAL_TITLES[row['vital_id']]} | {row.get('previous_band') or 'UNKNOWN'} | {row.get('current_band') or 'UNKNOWN'} | {row['transition_class']} | {', '.join(row.get('reason_codes') or []) or 'none'} |"
            )
        metric_lines = []
        for row in delta["vitals"]:
            for key, entry in sorted((row.get("metric_deltas") or {}).items()):
                change = entry.get("change")
                change_text = f" ({'+' if isinstance(change, int) and change > 0 else ''}{change})" if isinstance(change, int) else ""
                metric_lines.append(f"- {VITAL_TITLES[row['vital_id']]} {key}: {_fmt(entry.get('previous'))} to {_fmt(entry.get('current'))}{change_text}")
        if metric_lines:
            lines.append("")
            lines.append("Metric changes:")
            lines.extend(metric_lines)
    lines.append("")

    lines.append("## Activity")
    lines.append("")
    if activity is None:
        lines.append("Activity collection is disabled for this project.")
    else:
        interval = activity["interval"]
        basis = "since the previous bundle" if interval["basis"] == "PREVIOUS_BUNDLE" else "over the trailing 28-day observation window (no previous bundle)"
        lines.append(f"Interval {basis}: ({interval['start']}, {interval['end']}].")
        classes = activity["classes"]
        lines.append("")
        lines.append("| Class | Counts |")
        lines.append("| --- | --- |")
        lines.append(f"| Revisions on default branch | {classes['REVISION']['count']} |")
        cr = classes["CHANGE_REQUEST"]
        lines.append(f"| Change requests | opened {cr['opened']}, merged {cr['merged']}, closed {cr['closed']} |")
        wi = classes["WORK_ITEM"]
        lines.append(f"| Work items | opened {wi['opened']}, closed {wi['closed']} |")
        ver = classes["VERIFICATION"]
        lines.append(f"| Verification | {ver['revisions_verified']} revisions verified, {ver['failed']} with an observed failure, {ver['unresolved']} unresolved |")
        lines.append(f"| Releases | {classes['RELEASE']['count']} |")
        lines.append(f"| Capability changes | {classes['CAPABILITY_CHANGE']['count']} |")
        for label, key, formatter in (
            ("Change requests", "CHANGE_REQUEST", lambda e: f"- {e['kind']} #{e['number']} {e.get('title') or ''} ({e['at']})"),
            ("Work items", "WORK_ITEM", lambda e: f"- {e['kind']} #{e['number']} {e.get('title') or ''} ({e['at']})"),
            ("Verification findings", "VERIFICATION", lambda e: f"- {e['revision'][:12]} current {e.get('current_verdict')}, history {e.get('history_state')} ({e['committed_at']})"),
            ("Releases", "RELEASE", lambda e: f"- {e.get('tag')} {e.get('name') or ''} ({e.get('published_at')})"),
            ("Capability changes", "CAPABILITY_CHANGE", lambda e: f"- {e['observation_id']}: {_fmt(e.get('previous'))} to {_fmt(e.get('current'))}"),
        ):
            items = classes[key]["items"]
            if items:
                lines.append("")
                lines.append(f"{label}:")
                for item in items:
                    lines.append(formatter(item))
                if activity["truncated"].get(key):
                    lines.append(f"- list truncated to {activity['list_cap']} items")
        if activity.get("coverage_notes"):
            lines.append("")
            lines.append("Coverage notes: " + "; ".join(activity["coverage_notes"]))
    lines.append("")

    lines.append("## Provenance")
    lines.append("")
    lines.append(f"- Artifact contract: {manifest['artifact_contract_version']}; bundle identity: {manifest['bundle_identity_contract']}; renderer: {manifest['renderer_version']}")
    lines.append(f"- Effective config digest: `{manifest['effective_config_digest']}` (config version `{manifest['config_version']}`)")
    lines.append(f"- Adapters: {', '.join(a['provider'] + ' ' + a['adapter_version'] for a in manifest.get('adapters', []))}")
    lines.append(f"- Observations digest: `{snapshot['observations_digest']}`")
    lines.append("- Generated deterministically from the machine bundle without any language model.")
    lines.append("")
    return "\n".join(lines)


def render_fleet_index(entries: list[dict[str, Any]]) -> str:
    """Convenience overview of the latest bands of every project in a store (non-canonical)."""
    lines = ["# Devostasis fleet overview", "", "Latest canonical bundle per project. Bands are descriptive, not grades; UNKNOWN is honest, not empty.", ""]
    lines.append("| Project | Observed at | Comparison | Pulse | Flow | Integrity | Clutter | Horizon | Direction | Debt | Report |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for entry in sorted(entries, key=lambda e: e["locator"]):
        bands = entry["bands"]
        lines.append(
            f"| {entry['locator']} | {entry['observed_at']} | {entry['comparison_status']} | "
            f"{bands.get('pulse') or 'UNKNOWN'} | {bands.get('flow') or 'UNKNOWN'} | {bands.get('integrity') or 'UNKNOWN'} | "
            f"{bands.get('clutter') or 'UNKNOWN'} | {bands.get('horizon') or 'UNKNOWN'} | {bands.get('direction') or 'UNKNOWN'} | "
            f"{bands.get('debt') or 'UNKNOWN'} | [report]({entry['report_path']}) |"
        )
    lines.append("")
    return "\n".join(lines)
