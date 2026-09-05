"""Append-only filesystem HistoryStore.

Layout (PV-REPORT-001 companion-store recommendation)::

    projects/<forge>/<owner>/<repo>/
      latest/            convenience copy of the newest bundle, never authoritative
      history/YYYY/MM/DD/<bundle_id>/   immutable bundles
      index.json         chronological index of bundles

The store root is meant to be a companion Git repository committed by the
scheduler, or a plain directory in local mode. Storage activity never enters
the telemetry of the observed project because the store is never a target.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import canonical
from .bundle import Bundle, load_bundle_dir, verify_members


class HistoryStoreError(Exception):
    pass


class ImmutabilityError(HistoryStoreError):
    pass


@dataclass
class LatestState:
    """What the store knows about the newest bundle of a project."""

    exists: bool
    verified: bool
    bundle_id: str | None
    manifest: dict[str, Any] | None
    snapshot: dict[str, Any] | None
    problems: list[str]


class FilesystemHistoryStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def project_dir(self, project_key: str) -> Path:
        parts = [part for part in project_key.split("/") if part and part not in (".", "..")]
        return self.root.joinpath("projects", *parts)

    def index_path(self, project_key: str) -> Path:
        return self.project_dir(project_key) / "index.json"

    def read_index(self, project_key: str) -> dict[str, Any]:
        path = self.index_path(project_key)
        if not path.exists():
            return {"schema": "devostasis.index.v1", "project_key": project_key, "bundles": []}
        try:
            return canonical.load_file(path)
        except Exception as exc:  # noqa: BLE001
            raise HistoryStoreError(f"index unreadable: {exc}") from exc

    def latest(self, project_key: str) -> LatestState:
        latest_dir = self.project_dir(project_key) / "latest"
        index = None
        expected_id = None
        try:
            index = self.read_index(project_key)
            if index["bundles"]:
                expected_id = index["bundles"][-1]["bundle_id"]
        except HistoryStoreError as exc:
            return LatestState(True, False, None, None, None, [str(exc)])
        if not latest_dir.exists() and expected_id is None:
            return LatestState(False, False, None, None, None, [])
        members = load_bundle_dir(latest_dir) if latest_dir.exists() else {}
        if not members:
            return LatestState(True, False, expected_id, None, None, ["latest bundle directory missing or empty"])
        problems = verify_members(members)
        try:
            manifest = canonical.loads(members["manifest.json"].decode("utf-8"))
            snapshot = canonical.loads(members["snapshot.json"].decode("utf-8")) if "snapshot.json" in members else None
        except Exception as exc:  # noqa: BLE001
            return LatestState(True, False, expected_id, None, None, [f"latest bundle unreadable: {exc}"])
        if expected_id and manifest.get("bundle_id") != expected_id:
            problems.append(f"latest pointer {manifest.get('bundle_id')} differs from index tail {expected_id}")
        return LatestState(True, not problems, manifest.get("bundle_id"), manifest, snapshot, problems)

    def history_dir(self, bundle: Bundle) -> Path:
        day = bundle.observed_at[:10].split("-")
        return self.project_dir(bundle.project_key).joinpath("history", *day, bundle.bundle_id)

    def put_immutable(self, bundle: Bundle) -> Path:
        target = self.history_dir(bundle)
        if target.exists():
            existing = load_bundle_dir(target)
            if existing == bundle.members:
                return target
            raise ImmutabilityError(f"bundle {bundle.bundle_id} already exists with different content; history is append-only")
        staging = target.with_name(target.name + ".staging")
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        for name, data in bundle.members.items():
            (staging / name).write_bytes(data)
        staging.rename(target)
        return target

    def publish_latest(self, bundle: Bundle) -> Path:
        latest_dir = self.project_dir(bundle.project_key) / "latest"
        staging = latest_dir.with_name("latest.staging")
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        for name, data in bundle.members.items():
            (staging / name).write_bytes(data)
        if latest_dir.exists():
            shutil.rmtree(latest_dir)
        staging.rename(latest_dir)
        return latest_dir

    def update_index(self, bundle: Bundle, bands: dict[str, str | None]) -> dict[str, Any]:
        index = self.read_index(bundle.project_key)
        entries = [entry for entry in index["bundles"] if entry.get("bundle_id") != bundle.bundle_id]
        relative = self.history_dir(bundle).relative_to(self.project_dir(bundle.project_key)).as_posix()
        entries.append(
            {
                "bundle_id": bundle.bundle_id,
                "observed_at": bundle.observed_at,
                "comparison_status": bundle.manifest["comparison_status"],
                "previous_bundle_id": bundle.manifest.get("previous_bundle_id"),
                "path": relative,
                "bands": dict(sorted(bands.items())),
            }
        )
        entries.sort(key=lambda entry: (entry["observed_at"], entry["bundle_id"]))
        index["bundles"] = entries
        index["project_identity"] = bundle.manifest["project_identity"]
        canonical.write_pretty(self.index_path(bundle.project_key), index)
        return index

    def commit(self, bundle: Bundle, bands: dict[str, str | None]) -> Path:
        """Persist immutably, then publish latest and the index."""
        path = self.put_immutable(bundle)
        self.publish_latest(bundle)
        self.update_index(bundle, bands)
        return path

    def all_projects(self) -> list[dict[str, Any]]:
        """Latest index entry of every project in the store, for the fleet overview."""
        entries = []
        projects_root = self.root / "projects"
        if not projects_root.exists():
            return entries
        for index_path in sorted(projects_root.rglob("index.json")):
            try:
                index = canonical.load_file(index_path)
            except Exception:  # noqa: BLE001
                continue
            if not index.get("bundles"):
                continue
            tail = index["bundles"][-1]
            project_dir = index_path.parent
            identity = index.get("project_identity") or {}
            entries.append(
                {
                    "project_key": index.get("project_key"),
                    "locator": identity.get("display_locator") or index.get("project_key"),
                    "observed_at": tail["observed_at"],
                    "comparison_status": tail["comparison_status"],
                    "bands": tail.get("bands") or {},
                    "report_path": (project_dir / "latest" / "report.md").relative_to(projects_root).as_posix(),
                }
            )
        return entries
