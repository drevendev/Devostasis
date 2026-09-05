"""End-to-end pipeline: observe -> normalize -> evaluate -> compare -> bundle -> persist."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from . import activity as activity_mod
from . import delta as delta_mod
from . import normalize, render, timeutil
from .adapters.github import CollectionError, GitHubAdapter, GitHubClient, UrllibTransport
from .bundle import Bundle, BundleError, build_bundle
from .config import Config, ResolvedProject
from .contracts import OBSERVATION_CONTRACT_VERSION, VITALS_CONTRACT_VERSION
from .history import FilesystemHistoryStore, HistoryStoreError
from .observations import ObservationSet
from .policy import POLICY_VERSION
from .vitals import build_snapshot, evaluate_all


@dataclass
class RunOutcome:
    locator: str
    ok: bool
    bundle_id: str | None = None
    comparison_status: str | None = None
    bands: dict[str, str | None] = field(default_factory=dict)
    path: str | None = None
    error: str | None = None
    requests: int = 0


def observe(project: ResolvedProject, client: GitHubClient, now: datetime) -> ObservationSet:
    obs = GitHubAdapter(client, now).collect(project)
    normalize.derive(obs, project)
    return obs


def evaluate(obs: ObservationSet, project: ResolvedProject | None = None) -> dict[str, Any]:
    if project is not None:
        normalize.derive(obs, project)
    return build_snapshot(obs, evaluate_all(obs))


def decide_comparison(store: FilesystemHistoryStore, project: ResolvedProject) -> tuple[str, str | None, dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    """Return (comparison_status, previous_bundle_id, previous_manifest, previous_snapshot, reasons)."""
    latest = store.latest(project.project_key)
    if not latest.exists:
        return delta_mod.BASELINE, None, None, None, []
    if not latest.verified or latest.manifest is None or latest.snapshot is None:
        return delta_mod.HISTORY_GAP, latest.bundle_id, None, None, latest.problems
    current_fields = {
        "vitals_contract_version": VITALS_CONTRACT_VERSION,
        "observation_contract_version": OBSERVATION_CONTRACT_VERSION,
        "policy_version": POLICY_VERSION,
        "semantic_config": project.semantic_config(),
    }
    reasons = delta_mod.compatibility_reasons(current_fields, latest.manifest)
    if reasons:
        return delta_mod.INCOMPARABLE, latest.bundle_id, latest.manifest, latest.snapshot, reasons
    return delta_mod.COMPARABLE, latest.bundle_id, latest.manifest, latest.snapshot, []


def build_from_observations(project: ResolvedProject, obs: ObservationSet, store: FilesystemHistoryStore, run_meta: dict[str, Any] | None = None) -> Bundle:
    snapshot = build_snapshot(obs, evaluate_all(obs))
    status, previous_id, previous_manifest, previous_snapshot, reasons = decide_comparison(store, project)
    delta = delta_mod.compare(snapshot, previous_snapshot, status, previous_id, reasons)
    activity = None
    if project.activity_enabled:
        interval_start = previous_manifest.get("observed_at") if (status == delta_mod.COMPARABLE and previous_manifest) else None
        activity = activity_mod.build_activity(obs, previous_manifest if status == delta_mod.COMPARABLE else None, interval_start, project.activity_list_cap)
    return build_bundle(project, obs, snapshot, delta, activity, previous_id, status, run_meta)


def run_project(project: ResolvedProject, store: FilesystemHistoryStore, client: GitHubClient, now: datetime) -> RunOutcome:
    started = timeutil.now_utc()
    try:
        obs = observe(project, client, now)
    except CollectionError as exc:
        return RunOutcome(project.locator, False, error=str(exc), requests=client.request_count)
    try:
        run_meta = {"collection_started_at": timeutil.format_ts(started), "requests": client.request_count}
        bundle = build_from_observations(project, obs, store, run_meta)
        path = store.commit(bundle, bundle.bands(), bundle.gauges())
    except (BundleError, HistoryStoreError) as exc:
        return RunOutcome(project.locator, False, error=str(exc), requests=client.request_count)
    return RunOutcome(
        project.locator,
        True,
        bundle_id=bundle.bundle_id,
        comparison_status=bundle.manifest["comparison_status"],
        bands=bundle.bands(),
        path=str(path),
        requests=client.request_count,
    )


def write_fleet_index(store: FilesystemHistoryStore) -> Path | None:
    entries = store.all_projects()
    if not entries:
        return None
    path = store.root / "projects" / "README.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render.render_fleet_index(entries).encode("utf-8"))
    return path


def run_all(config: Config, store: FilesystemHistoryStore, token: str | None, now: datetime, only: list[str] | None = None, user_agent: str | None = None) -> list[RunOutcome]:
    outcomes = []
    for project in config.projects:
        if only and project.locator not in only:
            continue
        transport = UrllibTransport(token, user_agent=user_agent or "devostasis/0.1 (+https://github.com/drevendev/devostasis)")
        client = GitHubClient(transport)
        outcomes.append(run_project(project, store, client, now))
    write_fleet_index(store)
    return outcomes
