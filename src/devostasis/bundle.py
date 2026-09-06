"""Immutable canonical bundle: identity, members, manifest and verification.

Normative order (PV-BUNDLE-ID-002): canonical machine artifacts -> member and
receipt digests -> identity metadata and preimage -> bundle_id -> deterministic
renderer outputs -> output digests -> manifest -> persistence. The manifest,
report and output digests are post-identity, so the graph is acyclic.

The exact canonical effective config preimage is persisted as the member
``effective-config.json`` (B3 repair) and is the semantic authority of a
historical bundle (PV-EFFECTIVE-CONFIG-AUTHORITY-001, B4): verification
validates it under its recorded schema, derives the canonical member profile
from it, checks that profile against the actual members and the manifest, and
only then replays the renderer from stored config plus immutable machine
members. ``gauges.json`` and ``demand.json`` are derived from the snapshot
under versioned contracts and are identity-bearing members.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import __version__, canonical, render
from .config import PROFILE_MEMBERS, ResolvedProject, member_profile_from_config, validate_effective_config
from .contracts import (
    ARTIFACT_CONTRACT_VERSION,
    BUNDLE_IDENTITY_CONTRACT,
    CANONICAL_SERIALIZATION_VERSION,
    CI_UNIT_CONTRACT_VERSION,
    DEMAND_CONTRACT,
    EFFECTIVE_CONFIG_AUTHORITY_CONTRACT,
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
OBSERVATIONS_DISABLED = "OBSERVATIONS_MEMBER_DISABLED"
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
    "report.html",
)

# Verification problem codes named by the accepted artifact contract.
EFFECTIVE_CONFIG_SCHEMA_INVALID = "EFFECTIVE_CONFIG_SCHEMA_INVALID_OR_UNSUPPORTED"
CANONICAL_MEMBER_PROFILE_MISMATCH = "CANONICAL_MEMBER_PROFILE_MISMATCH"
EFFECTIVE_CONFIG_PREIMAGE_MISMATCH = "EFFECTIVE_CONFIG_PREIMAGE_MISMATCH"


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
    member_profile = member_profile_from_config(effective_config)
    if (activity is None) != (member_profile["activity_json"] == "DISABLED"):
        raise BundleError("activity member presence disagrees with the effective configuration")

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
        "observations_digest": observations_digest if project.observations_member else OBSERVATIONS_DISABLED,
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
        "effective_config_authority_contract": EFFECTIVE_CONFIG_AUTHORITY_CONTRACT,
        "effective_config_digest": effective_digest,
        "semantic_config": project.semantic_config(),
        "canonical_member_profile": member_profile,
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

BYTE_DIGESTED_MEMBERS = ("report.md", "report.html", "effective-config.json")


def _member_digest(name: str, data: bytes) -> str:
    if name in BYTE_DIGESTED_MEMBERS:
        return canonical.digest_bytes(data)
    return canonical.digest(canonical.loads(data.decode("utf-8")))


def _check_member_profile(members: dict[str, bytes], manifest: dict[str, Any], config: dict[str, Any]) -> list[str]:
    """ART-23: the profile implied by the stored config must match the manifest and the actual members."""
    problems: list[str] = []
    expected = member_profile_from_config(config)
    recorded = manifest.get("canonical_member_profile")
    if recorded != expected:
        problems.append(
            f"{CANONICAL_MEMBER_PROFILE_MISMATCH}: manifest profile {recorded} differs from the profile implied by the stored effective config {expected} (ART-23)"
        )
    declared = manifest.get("members") or {}
    for key, member in PROFILE_MEMBERS.items():
        state = expected.get(key)
        present = member in members or member in declared
        if state is None:
            if present:
                problems.append(f"{CANONICAL_MEMBER_PROFILE_MISMATCH}: {member} is present but the stored effective config schema knows no such member (ART-23)")
            continue
        if state in ("REQUIRED", "ENABLED") and not present:
            problems.append(f"{CANONICAL_MEMBER_PROFILE_MISMATCH}: {member} is {state} by the stored effective config but absent (ART-23)")
        if state == "DISABLED" and present:
            problems.append(f"{CANONICAL_MEMBER_PROFILE_MISMATCH}: {member} is DISABLED by the stored effective config but present (ART-23)")
    preimage = manifest.get("identity_preimage") or {}
    if preimage:
        activity_disabled = preimage.get("activity_digest") == ACTIVITY_DISABLED
        if activity_disabled != (expected["activity_json"] == "DISABLED"):
            problems.append(f"{CANONICAL_MEMBER_PROFILE_MISMATCH}: identity preimage activity marker disagrees with the stored effective config (ART-23)")
        observations_disabled = preimage.get("observations_digest") == OBSERVATIONS_DISABLED
        if observations_disabled != (expected["observations_json"] == "DISABLED"):
            problems.append(f"{CANONICAL_MEMBER_PROFILE_MISMATCH}: identity preimage observations marker disagrees with the stored effective config (ART-23)")
    return problems


def verify_members(members: dict[str, bytes]) -> list[str]:
    """Return verification problems for a bundle (empty list means verified).

    Order: member digests and canonical form; identity preimage and bundle_id;
    the stored effective config as semantic authority (schema, member profile,
    identity markers); only then the renderer replay from stored config.
    """
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
        try:
            actual = _member_digest(name, data)
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{name} unreadable: {exc}")
            continue
        if name == "effective-config.json":
            try:
                if canonical.canonical_bytes(canonical.loads(data.decode("utf-8"))) != data:
                    problems.append("effective-config.json is not stored in canonical form (ART-21)")
            except Exception as exc:  # noqa: BLE001
                problems.append(f"effective-config.json unreadable: {exc}")
        if actual != digest:
            problems.append(f"{name} digest mismatch: manifest {digest}, actual {actual}")
    for name in sorted(members):
        if name != "manifest.json" and name not in declared:
            problems.append(f"{name} is present but not declared in the manifest")
    if "effective-config.json" not in members:
        problems.append("effective-config.json missing (ART-20)")

    preimage = manifest.get("identity_preimage") or {}
    if not preimage:
        problems.append("identity preimage missing from manifest")
    else:
        recomputed = canonical.sha256_hex(canonical.canonical_bytes(preimage))
        if recomputed != manifest.get("bundle_id"):
            problems.append(f"bundle_id mismatch: manifest {manifest.get('bundle_id')}, recomputed {recomputed}")
        if preimage.get("effective_config_digest") != manifest.get("effective_config_digest"):
            problems.append(f"{EFFECTIVE_CONFIG_PREIMAGE_MISMATCH}: effective_config_digest differs between preimage and manifest")
        if "effective-config.json" in members and preimage.get("effective_config_digest") != canonical.digest_bytes(members["effective-config.json"]):
            problems.append(f"{EFFECTIVE_CONFIG_PREIMAGE_MISMATCH}: persisted effective config does not hash to effective_config_digest (ART-20/ART-21)")
        for member, key in PREIMAGE_MEMBER_DIGESTS:
            if member in declared and key in preimage and preimage.get(key) != declared[member]:
                problems.append(f"{member} digest differs between preimage and manifest members")
        for key in ("bundle_id", "members", "run_meta"):
            if key in preimage:
                problems.append(f"identity preimage must not contain post-identity field {key} (ART-22)")

    # B4: the stored effective config is the semantic authority (ART-25, then ART-23).
    config: dict[str, Any] | None = None
    authority_ok = "effective-config.json" in members
    if authority_ok:
        try:
            config = canonical.loads(members["effective-config.json"].decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{EFFECTIVE_CONFIG_SCHEMA_INVALID}: effective-config.json unreadable: {exc} (ART-25)")
            authority_ok = False
    if authority_ok:
        schema_problems = validate_effective_config(config)
        if schema_problems:
            problems.extend(f"{EFFECTIVE_CONFIG_SCHEMA_INVALID}: {problem} (ART-25)" for problem in schema_problems)
            authority_ok = False
    if authority_ok:
        profile_problems = _check_member_profile(members, manifest, config)
        if profile_problems:
            problems.extend(profile_problems)
            authority_ok = False

    # ART-24: replay only from the validated stored config and immutable machine members.
    if "report.md" in members:
        if not authority_ok:
            problems.append("report.md replay skipped: the stored effective config is not a valid authority (ART-24)")
        elif "snapshot.json" in members and "delta.json" in members and manifest.get("renderer_version") == RENDERER_VERSION:
            try:
                snapshot = canonical.loads(members["snapshot.json"].decode("utf-8"))
                delta = canonical.loads(members["delta.json"].decode("utf-8"))
                activity = canonical.loads(members["activity.json"].decode("utf-8")) if "activity.json" in members else None
                gauges_doc = canonical.loads(members["gauges.json"].decode("utf-8")) if "gauges.json" in members else None
                demand_doc = canonical.loads(members["demand.json"].decode("utf-8")) if "demand.json" in members else None
                rendered = render.render_report(manifest, snapshot, delta, activity, gauges_doc, demand_doc, config.get("display")).encode("utf-8")
                if rendered != members["report.md"]:
                    problems.append("report.md is not reproducible from the machine bundle and the stored effective config with the current renderer (ART-12/ART-24)")
            except Exception as exc:  # noqa: BLE001
                problems.append(f"report re-rendering failed: {exc}")
    return problems


def verify_dir(directory: str | Path) -> list[str]:
    return verify_members(load_bundle_dir(directory))
