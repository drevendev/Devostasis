"""Immutable canonical bundle: identity, members, manifest and verification.

Normative order (PV-BUNDLE-ID-002): canonical machine artifacts -> member and
receipt digests -> identity metadata and preimage -> bundle_id -> deterministic
renderer outputs -> output digests -> manifest -> persistence. The manifest,
report and output digests are post-identity, so the graph is acyclic.

The exact canonical effective config preimage is persisted as the member
``effective-config.json`` (B3 repair): a historical bundle can recompute its
own ``effective_config_digest`` and re-render itself without any external
configuration. ``gauges.json`` and ``demand.json`` are derived from the
snapshot under versioned contracts and are identity-bearing members.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import __version__, canonical, render
from .config import ResolvedProject
from .contracts import (
    ARTIFACT_CONTRACT_VERSION,
    BUNDLE_IDENTITY_CONTRACT,
    CANONICAL_SERIALIZATION_VERSION,
    CI_UNIT_CONTRACT_VERSION,
    DEMAND_CONTRACT,
    EFFECTIVE_CONFIG_CONTRACT,
    GAUGE_CONTRACT,
    MANIFEST_SCHEMA,
    OBSERVATION_CONTRACT_VERSION,
    RENDERER_VERSION,
    VITALS_CONTRACT_VERSION,
)
from .demand import build_demand
from .gauges import gauges_member
from .observations import ObservationSet
from .policy import POLICY_VERSION

ACTIVITY_DISABLED = "ACTIVITY_DISABLED"
MEMBER_NAMES = (
    "manifest.json",
    "snapshot.json",
    "delta.json",
    "activity.json",
    "observations.json",
    "gauges.json",
    "demand.json",
    "effective-config.json",
    "report.md",
)


@dataclass
class Bundle:
    bundle_id: str
    project_key: str
    observed_at: str
    manifest: dict[str, Any]
    members: dict[str, bytes] = field(default_factory=dict)

    def _json(self, name: str) -> dict[str, Any]:
        return canonical.loads(self.members[name].decode("utf-8"))

    @property
    def snapshot(self) -> dict[str, Any]:
        return self._json("snapshot.json")

    def bands(self) -> dict[str, str | None]:
        return {item["vital_id"]: item["band"] for item in self.snapshot["vitals"]}

    def gauges(self) -> dict[str, int | None]:
        return {g["vital_id"]: g["value"] for g in self._json("gauges.json")["gauges"]}

    def demand(self) -> dict[str, Any]:
        return self._json("demand.json")


class BundleError(Exception):
    """Raised when a bundle cannot be built or verified."""


def project_identity(obs: ObservationSet, project: ResolvedProject) -> dict[str, Any]:
    subject = obs.subject
    return {
        "provider": "github",
        "forge_instance": subject.get("forge_instance", "github.com"),
        "immutable_project_id": subject.get("immutable_project_id"),
        "display_locator": subject.get("display_locator", project.locator),
        "default_branch": subject.get("default_branch"),
    }


def build_bundle(
    project: ResolvedProject,
    obs: ObservationSet,
    snapshot: dict[str, Any],
    delta: dict[str, Any],
    activity: dict[str, Any] | None,
    previous_bundle_id: str | None,
    comparison_status: str,
    run_meta: dict[str, Any] | None = None,
) -> Bundle:
    if project.report_html:
        raise BundleError("report_html=ENABLED is not supported by this version; canonical persistence fails closed rather than silently disabling the member")
    if obs.receipt is None:
        raise BundleError("observation set has no collection receipt")

    effective_config = project.effective_bundle_config()
    effective_bytes = canonical.canonical_bytes(effective_config)
    effective_digest = canonical.digest_bytes(effective_bytes)
    receipt_dict = obs.receipt.to_dict()
    identity = project_identity(obs, project)

    gauges_doc = gauges_member(snapshot)
    demand_doc = build_demand(snapshot, gauges_doc["gauges"], project.demand)

    snapshot_digest = canonical.digest(snapshot)
    delta_digest = canonical.digest(delta)
    activity_digest = canonical.digest(activity) if activity is not None else ACTIVITY_DISABLED
    gauges_digest = canonical.digest(gauges_doc)
    demand_digest = canonical.digest(demand_doc)
    observations_dict = obs.to_dict()
    observations_digest = canonical.digest(observations_dict)
    receipt_digest = canonical.digest(receipt_dict)

    preimage = {
        "bundle_identity_contract": BUNDLE_IDENTITY_CONTRACT,
        "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
        "vitals_contract_version": VITALS_CONTRACT_VERSION,
        "observation_contract_version": OBSERVATION_CONTRACT_VERSION,
        "ci_unit_contract_version": CI_UNIT_CONTRACT_VERSION,
        "gauge_contract": GAUGE_CONTRACT,
        "demand_contract": DEMAND_CONTRACT,
        "policy_version": POLICY_VERSION,
        "config_version": project.config_version,
        "renderer_version": RENDERER_VERSION,
        "canonical_serialization_version": CANONICAL_SERIALIZATION_VERSION,
        "effective_config_contract": EFFECTIVE_CONFIG_CONTRACT,
        "effective_config_digest": effective_digest,
        "project_identity": identity,
        "observed_at": obs.observed_at,
        "previous_bundle_id": previous_bundle_id,
        "comparison_status": comparison_status,
        "snapshot_digest": snapshot_digest,
        "delta_digest": delta_digest,
        "activity_digest": activity_digest,
        "gauges_digest": gauges_digest,
        "demand_digest": demand_digest,
        "observations_digest": observations_digest if project.observations_member else "OBSERVATIONS_MEMBER_DISABLED",
        "source_receipts_digest": receipt_digest,
    }
    bundle_id = canonical.sha256_hex(canonical.canonical_bytes(preimage))

    manifest_core = {
        "schema": MANIFEST_SCHEMA,
        "bundle_id": bundle_id,
        "project_key": project.project_key,
        "project_identity": identity,
        "observed_at": obs.observed_at,
        "previous_bundle_id": previous_bundle_id,
        "comparison_status": comparison_status,
        "supersedes_bundle_id": None,
        "artifact_contract_version": ARTIFACT_CONTRACT_VERSION,
        "bundle_identity_contract": BUNDLE_IDENTITY_CONTRACT,
        "vitals_contract_version": VITALS_CONTRACT_VERSION,
        "observation_contract_version": OBSERVATION_CONTRACT_VERSION,
        "ci_unit_contract_version": CI_UNIT_CONTRACT_VERSION,
        "gauge_contract": GAUGE_CONTRACT,
        "demand_contract": DEMAND_CONTRACT,
        "policy_version": POLICY_VERSION,
        "config_version": project.config_version,
        "renderer_version": RENDERER_VERSION,
        "canonical_serialization_version": CANONICAL_SERIALIZATION_VERSION,
        "effective_config_contract": EFFECTIVE_CONFIG_CONTRACT,
        "effective_config_digest": effective_digest,
        "semantic_config": project.semantic_config(),
        "canonical_member_profile": {
            "report_md": "REQUIRED",
            "report_html": "DISABLED",
            "activity_json": "ENABLED" if activity is not None else "DISABLED",
            "observations_json": "ENABLED" if project.observations_member else "DISABLED",
            "gauges_json": "REQUIRED",
            "demand_json": "REQUIRED",
            "effective_config_json": "REQUIRED",
        },
        "adapters": [{"provider": "github", "adapter_version": obs.receipt.collector_version}],
        "receipt": receipt_dict,
        "identity_preimage": preimage,
    }

    report_text = render.render_report(manifest_core, snapshot, delta, activity, gauges_doc, demand_doc, effective_config.get("display"))
    report_bytes = report_text.encode("utf-8")

    members: dict[str, bytes] = {
        "snapshot.json": canonical.pretty_json(snapshot).encode("utf-8"),
        "delta.json": canonical.pretty_json(delta).encode("utf-8"),
        "gauges.json": canonical.pretty_json(gauges_doc).encode("utf-8"),
        "demand.json": canonical.pretty_json(demand_doc).encode("utf-8"),
        "effective-config.json": effective_bytes,
        "report.md": report_bytes,
    }
    if activity is not None:
        members["activity.json"] = canonical.pretty_json(activity).encode("utf-8")
    if project.observations_member:
        members["observations.json"] = canonical.pretty_json(observations_dict).encode("utf-8")

    manifest = dict(manifest_core)
    manifest["members"] = {
        "snapshot.json": snapshot_digest,
        "delta.json": delta_digest,
        "gauges.json": gauges_digest,
        "demand.json": demand_digest,
        "effective-config.json": effective_digest,
        "report.md": canonical.digest_bytes(report_bytes),
    }
    if activity is not None:
        manifest["members"]["activity.json"] = activity_digest
    if project.observations_member:
        manifest["members"]["observations.json"] = observations_digest
    manifest["run_meta"] = dict(run_meta or {}, tool={"name": "devostasis", "version": __version__})
    members["manifest.json"] = canonical.pretty_json(manifest).encode("utf-8")
    return Bundle(bundle_id=bundle_id, project_key=project.project_key, observed_at=obs.observed_at, manifest=manifest, members=members)


def load_bundle_dir(directory: str | Path) -> dict[str, bytes]:
    directory = Path(directory)
    members: dict[str, bytes] = {}
    for name in MEMBER_NAMES:
        path = directory / name
        if path.exists():
            members[name] = path.read_bytes()
    return members


PREIMAGE_MEMBER_DIGESTS = (
    ("snapshot.json", "snapshot_digest"),
    ("delta.json", "delta_digest"),
    ("activity.json", "activity_digest"),
    ("observations.json", "observations_digest"),
    ("gauges.json", "gauges_digest"),
    ("demand.json", "demand_digest"),
)


def verify_members(members: dict[str, bytes]) -> list[str]:
    """Return verification problems for a bundle (empty list means verified)."""
    problems: list[str] = []
    if "manifest.json" not in members:
        return ["manifest.json missing"]
    try:
        manifest = canonical.loads(members["manifest.json"].decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [f"manifest.json unreadable: {exc}"]

    declared = manifest.get("members") or {}
    for name, digest in sorted(declared.items()):
        if name not in members:
            problems.append(f"{name} declared but missing")
            continue
        data = members[name]
        if name == "report.md":
            actual = canonical.digest_bytes(data)
        elif name == "effective-config.json":
            actual = canonical.digest_bytes(data)
            try:
                parsed = canonical.loads(data.decode("utf-8"))
                if canonical.canonical_bytes(parsed) != data:
                    problems.append("effective-config.json is not stored in canonical form (ART-21)")
            except Exception as exc:  # noqa: BLE001
                problems.append(f"effective-config.json unreadable: {exc}")
        else:
            try:
                actual = canonical.digest(canonical.loads(data.decode("utf-8")))
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{name} unreadable: {exc}")
                continue
        if actual != digest:
            problems.append(f"{name} digest mismatch: manifest {digest}, actual {actual}")

    preimage = manifest.get("identity_preimage") or {}
    if not preimage:
        problems.append("identity preimage missing from manifest")
    else:
        recomputed = canonical.sha256_hex(canonical.canonical_bytes(preimage))
        if recomputed != manifest.get("bundle_id"):
            problems.append(f"bundle_id mismatch: manifest {manifest.get('bundle_id')}, recomputed {recomputed}")
        if preimage.get("effective_config_digest") != manifest.get("effective_config_digest"):
            problems.append("effective_config_digest differs between preimage and manifest")
        if "effective-config.json" in members and preimage.get("effective_config_digest") != canonical.digest_bytes(members["effective-config.json"]):
            problems.append("persisted effective config does not hash to effective_config_digest (ART-20/ART-21)")
        for member, key in PREIMAGE_MEMBER_DIGESTS:
            if member in declared and key in preimage and preimage.get(key) != declared[member]:
                problems.append(f"{member} digest differs between preimage and manifest members")
        for key in ("bundle_id", "members", "run_meta"):
            if key in preimage:
                problems.append(f"identity preimage must not contain post-identity field {key} (ART-22)")

    if "report.md" in members and "snapshot.json" in members and "delta.json" in members:
        try:
            snapshot = canonical.loads(members["snapshot.json"].decode("utf-8"))
            delta = canonical.loads(members["delta.json"].decode("utf-8"))
            activity = canonical.loads(members["activity.json"].decode("utf-8")) if "activity.json" in members else None
            gauges_doc = canonical.loads(members["gauges.json"].decode("utf-8")) if "gauges.json" in members else None
            demand_doc = canonical.loads(members["demand.json"].decode("utf-8")) if "demand.json" in members else None
            display = None
            if "effective-config.json" in members:
                display = canonical.loads(members["effective-config.json"].decode("utf-8")).get("display")
            if manifest.get("renderer_version") == RENDERER_VERSION:
                rendered = render.render_report(manifest, snapshot, delta, activity, gauges_doc, demand_doc, display).encode("utf-8")
                if rendered != members["report.md"]:
                    problems.append("report.md is not reproducible from the machine bundle with the current renderer (ART-12)")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"report re-rendering failed: {exc}")
    return problems


def verify_dir(directory: str | Path) -> list[str]:
    return verify_members(load_bundle_dir(directory))
