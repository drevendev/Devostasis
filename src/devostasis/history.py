"""Append-only filesystem HistoryStore.

Layout (PV-REPORT-001 companion-store recommendation)::

    projects/README.md                 fleet overview for people
    projects/index.json                fleet index for machines
    projects/<forge>/<owner>/<repo>/
      latest/            convenience copy of the newest bundle, never authoritative
      history/YYYY/MM/DD/<bundle_id>/   immutable bundles
      index.json         chronological index of bundles

The store root is meant to be a companion Git repository committed by the
scheduler, or a plain directory in local mode. Storage activity never enters
the telemetry of the observed project because the store is never a target.

**A project is identified by its immutable project id, not by its path**
(RPT-7). The directory keeps the human-readable ``<forge>/<owner>/<repo>``
locator because a store is browsed by people, but a project is located by the
provider's immutable id first. When a repository is renamed or transferred,
the directory is relocated once to the new locator and the rename is recorded
in the project index, so history stays one chain instead of silently splitting
into an old orphan and a new BASELINE.

Fail-closed rule: if the locator a project now claims is already occupied by a
different project, nothing is written. That is the case of a repository being
renamed and its old name immediately reused, which would otherwise merge two
projects' histories into one directory.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import canonical
from .bundle import Bundle, load_bundle_dir, verify_members

INDEX_SCHEMA = "devostasis.index.v1"


class HistoryStoreError(Exception):
    pass


class ImmutabilityError(HistoryStoreError):
    """Raised when an existing immutable bundle would be overwritten with different content."""


class IdentityConflictError(HistoryStoreError):
    """Raised when a locator is claimed by a project that is not the one being written."""


@dataclass
class LatestState:
    """What the store knows about the newest bundle of a project."""

    exists: bool
    verified: bool
    bundle_id: str | None
    manifest: dict[str, Any] | None
    snapshot: dict[str, Any] | None
    problems: list[str]


@dataclass
class ResolvedLocation:
    """Where a project's history lives, and whether the locator moved since the last bundle."""

    directory: Path
    previous_directory: Path | None = None

    @property
    def relocated(self) -> bool:
        return self.previous_directory is not None and self.previous_directory != self.directory


class FilesystemHistoryStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    @property
    def projects_root(self) -> Path:
        return self.root / "projects"

    def project_dir(self, project_key: str) -> Path:
        """The directory a locator names. Where a project actually lives is ``resolve``."""
        parts = [part for part in project_key.split("/") if part and part not in (".", "..")]
        return self.projects_root.joinpath(*parts)

    def index_path(self, project_key: str) -> Path:
        return self.project_dir(project_key) / "index.json"

    # ------------------------------------------------------------------ identity

    def _project_index_paths(self) -> list[Path]:
        """Every per-project index, excluding the fleet index that shares the name."""
        if not self.projects_root.exists():
            return []
        return [path for path in sorted(self.projects_root.rglob("index.json")) if path.parent != self.projects_root]

    @staticmethod
    def _identity_of(index: dict[str, Any] | None) -> str | None:
        identity = (index or {}).get("project_identity") or {}
        value = identity.get("immutable_project_id")
        return str(value) if value not in (None, "") else None

    def _read_index_at(self, directory: Path) -> dict[str, Any] | None:
        path = directory / "index.json"
        if not path.exists():
            return None
        try:
            return canonical.load_file(path)
        except Exception as exc:  # noqa: BLE001
            raise HistoryStoreError(f"index unreadable at {directory}: {exc}") from exc

    def find_by_identity(self, immutable_project_id: str | None) -> Path | None:
        """The directory whose recorded identity matches, wherever it currently sits."""
        if not immutable_project_id:
            return None
        for index_path in self._project_index_paths():
            try:
                index = canonical.load_file(index_path)
            except Exception:  # noqa: BLE001
                continue
            if self._identity_of(index) == str(immutable_project_id) and index.get("bundles"):
                return index_path.parent
        return None

    def resolve(self, project_key: str, immutable_project_id: str | None = None) -> ResolvedLocation:
        """Locate a project by identity, falling back to its locator.

        Without an immutable id the store behaves exactly as before: the
        locator is the identity, and a rename starts a new history. Adapters
        that cannot prove an id therefore lose continuity honestly rather than
        by guessing which directory belonged to whom.
        """
        wanted = self.project_dir(project_key)
        identity = str(immutable_project_id) if immutable_project_id not in (None, "") else None
        if identity is None:
            return ResolvedLocation(wanted)

        at_locator = self._identity_of(self._read_index_at(wanted))
        if at_locator == identity:
            return ResolvedLocation(wanted)
        if at_locator is not None:
            raise IdentityConflictError(
                f"{project_key} is occupied by project {at_locator}, and this run observes project {identity}; "
                "refusing to merge two histories in one directory"
            )

        existing = self.find_by_identity(identity)
        if existing is None or existing == wanted:
            return ResolvedLocation(wanted)
        if wanted.exists() and any(wanted.iterdir()):
            raise IdentityConflictError(
                f"project {identity} moved to {project_key}, but that directory already holds unidentified content; "
                "refusing to write over it"
            )
        return ResolvedLocation(wanted, previous_directory=existing)

    def _relocate(self, location: ResolvedLocation) -> None:
        """Move a renamed or transferred project to its new locator, once."""
        source, target = location.previous_directory, location.directory
        if source is None or source == target:
            return
        if target.exists():
            occupant = self._identity_of(self._read_index_at(target))
            raise IdentityConflictError(
                f"cannot move {source} to {target}: the destination already exists"
                + (f" and holds project {occupant}" if occupant else "")
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)

    # ------------------------------------------------------------------ reading

    def read_index(self, project_key: str, directory: Path | None = None) -> dict[str, Any]:
        directory = directory if directory is not None else self.project_dir(project_key)
        index = self._read_index_at(directory)
        if index is None:
            return {"schema": INDEX_SCHEMA, "project_key": project_key, "bundles": []}
        return index

    def latest(self, project_key: str, immutable_project_id: str | None = None) -> LatestState:
        try:
            location = self.resolve(project_key, immutable_project_id)
        except HistoryStoreError as exc:
            return LatestState(True, False, None, None, None, [str(exc)])
        directory = location.previous_directory or location.directory
        latest_dir = directory / "latest"
        expected_id = None
        try:
            index = self.read_index(project_key, directory)
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

    # ------------------------------------------------------------------ writing

    def bundle_identity(self, bundle: Bundle) -> str | None:
        return self._identity_of({"project_identity": bundle.manifest.get("project_identity")})

    def history_dir(self, bundle: Bundle, directory: Path | None = None) -> Path:
        day = bundle.observed_at[:10].split("-")
        directory = directory if directory is not None else self.project_dir(bundle.project_key)
        return directory.joinpath("history", *day, bundle.bundle_id)

    def put_immutable(self, bundle: Bundle, directory: Path | None = None) -> Path:
        target = self.history_dir(bundle, directory)
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

    def publish_latest(self, bundle: Bundle, directory: Path | None = None) -> Path:
        directory = directory if directory is not None else self.project_dir(bundle.project_key)
        latest_dir = directory / "latest"
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

    def update_index(
        self,
        bundle: Bundle,
        bands: dict[str, str | None],
        gauges: dict[str, int | None] | None = None,
        top_attention: str | None = None,
        directory: Path | None = None,
        renamed_from: str | None = None,
    ) -> dict[str, Any]:
        directory = directory if directory is not None else self.project_dir(bundle.project_key)
        index = self.read_index(bundle.project_key, directory)
        entries = [entry for entry in index["bundles"] if entry.get("bundle_id") != bundle.bundle_id]
        relative = self.history_dir(bundle, directory).relative_to(directory).as_posix()
        entries.append(
            {
                "bundle_id": bundle.bundle_id,
                "observed_at": bundle.observed_at,
                "comparison_status": bundle.manifest["comparison_status"],
                "previous_bundle_id": bundle.manifest.get("previous_bundle_id"),
                "path": relative,
                "bands": dict(sorted(bands.items())),
                "gauges": dict(sorted((gauges or {}).items())),
                "top_attention": top_attention,
            }
        )
        entries.sort(key=lambda entry: (entry["observed_at"], entry["bundle_id"]))
        index["schema"] = index.get("schema", INDEX_SCHEMA)
        index["bundles"] = entries
        index["project_key"] = bundle.project_key
        index["project_identity"] = bundle.manifest["project_identity"]
        if renamed_from:
            renames = [entry for entry in (index.get("renames") or []) if entry.get("to") != bundle.project_key or entry.get("from") != renamed_from]
            renames.append(
                {
                    "from": renamed_from,
                    "to": bundle.project_key,
                    "observed_at": bundle.observed_at,
                    "bundle_id": bundle.bundle_id,
                }
            )
            index["renames"] = sorted(renames, key=lambda entry: (entry["observed_at"], entry["bundle_id"]))
        canonical.write_pretty(directory / "index.json", index)
        return index

    def commit(
        self,
        bundle: Bundle,
        bands: dict[str, str | None] | None = None,
        gauges: dict[str, int | None] | None = None,
        top_attention: str | None = None,
    ) -> Path:
        """Relocate on rename, persist immutably, then publish latest and the index."""
        from .demand import top_attention as _top

        location = self.resolve(bundle.project_key, self.bundle_identity(bundle))
        renamed_from = None
        if location.relocated:
            renamed_from = location.previous_directory.relative_to(self.projects_root).as_posix()
            self._relocate(location)
        directory = location.directory
        path = self.put_immutable(bundle, directory)
        self.publish_latest(bundle, directory)
        bands = bands if bands is not None else bundle.bands()
        gauges = gauges if gauges is not None else bundle.gauges()
        if top_attention is None:
            try:
                top_attention = _top(bundle.demand())
            except KeyError:
                top_attention = None
        self.update_index(bundle, bands, gauges, top_attention, directory, renamed_from)
        return path

    # ------------------------------------------------------------------ fleet

    def all_projects(self) -> list[dict[str, Any]]:
        """Latest index entry of every project in the store, for the fleet overview and index."""
        entries = []
        projects_root = self.projects_root
        if not projects_root.exists():
            return entries
        for index_path in self._project_index_paths():
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
                    "immutable_project_id": identity.get("immutable_project_id"),
                    "observed_at": tail["observed_at"],
                    "bundle_id": tail.get("bundle_id"),
                    "previous_bundle_id": tail.get("previous_bundle_id"),
                    "comparison_status": tail["comparison_status"],
                    "bands": tail.get("bands") or {},
                    "gauges": tail.get("gauges") or {},
                    "top_attention": tail.get("top_attention"),
                    "demand_rows": self._demand_rows(project_dir),
                    "attention_order": self._attention_order(project_dir),
                    "renames": list(index.get("renames") or []),
                    "report_path": (project_dir / "latest" / "report.md").relative_to(projects_root).as_posix(),
                    "bundle_path": (project_dir / tail["path"]).relative_to(projects_root).as_posix() if tail.get("path") else None,
                }
            )
        return entries

    def _latest_demand(self, project_dir: Path) -> dict[str, Any] | None:
        """The demand member of the latest bundle, or None when it is absent or unreadable.

        Bundles written before the demand interface existed have no such
        member; their rows carry null levels rather than invented ones.
        """
        path = project_dir / "latest" / "demand.json"
        if not path.exists():
            return None
        try:
            document = canonical.load_file(path)
        except Exception:  # noqa: BLE001
            return None
        return document if isinstance(document, dict) else None

    def _demand_rows(self, project_dir: Path) -> list[dict[str, Any]]:
        demand = self._latest_demand(project_dir)
        rows = (demand or {}).get("vitals")
        return [row for row in rows if isinstance(row, dict) and row.get("vital_id")] if isinstance(rows, list) else []

    def _attention_order(self, project_dir: Path) -> list[dict[str, Any]]:
        demand = self._latest_demand(project_dir)
        order = (demand or {}).get("attention_order")
        if not isinstance(order, list):
            return []
        return [
            {"vital_id": item["vital_id"], "level": item.get("level")}
            for item in order
            if isinstance(item, dict) and item.get("vital_id")
        ]
