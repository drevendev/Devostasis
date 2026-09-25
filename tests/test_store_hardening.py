"""The store fails closed on what it reads about itself.

The review of the #28 repair (PR #31) found that the index tail, now the
authority of the comparison, was followed wherever it pointed and the bundle
found there was never bound to the project whose history it was read as: a
damaged index for project A could name a valid bundle of project B and the
next run would compare A against B. The research audits of 2026-09-20/24
found the same family elsewhere in the store: an unreadable index treated as
an absent project while proving an identity lives nowhere else, or while
publishing the fleet surfaces; a locator that derives a path outside the
store; an index truncated in place; two configured spellings of one
repository observed twice.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone

import pytest

from devostasis import canonical, runner
from devostasis.bundle import Bundle
from devostasis.config import ConfigError, load_config_dict, single_project
from devostasis.history import FilesystemHistoryStore, HistoryStoreError
from devostasis.runner import RunOutcome, build_from_observations, run_all, write_fleet_index
from helpers import full_inputs, obs_set

NOW = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


def _observe(store, locator, project_id, observed_at="2026-09-05T12:00:00Z"):
    owner, repo = locator.split("/")
    obs = full_inputs(obs_set(observed_at))
    obs.subject = dict(obs.subject, owner=owner, repo=repo, display_locator=locator, immutable_project_id=project_id)
    project = single_project(locator, config_version="1")
    bundle = build_from_observations(project, obs, store)
    return bundle, store.commit(bundle), project


def _index_path(store, key):
    return store.project_dir(key) / "index.json"


def _rewrite_tail(store, key, **fields):
    path = _index_path(store, key)
    index = json.loads(path.read_text("utf-8"))
    index["bundles"][-1].update(fields)
    path.write_text(json.dumps(index), "utf-8")


def _two_projects(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    a, a_path, a_project = _observe(store, "acme/widget", "42")
    b, b_path, _ = _observe(store, "acme/gadget", "99")
    return store, (a, a_path, a_project), (b, b_path)


# --------------------------------------------------------------------------- the index tail (review of PR #31)


def test_a_tail_path_that_escapes_the_history_tree_is_a_history_gap_never_a_comparison(tmp_path):
    store, (a, _, a_project), (b, b_path) = _two_projects(tmp_path)
    escape = "../gadget/" + b_path.relative_to(store.project_dir("github.com/acme/gadget")).as_posix()
    _rewrite_tail(store, "github.com/acme/widget", path=escape, bundle_id=b.bundle_id)
    state = store.latest("github.com/acme/widget", "42")
    assert state.exists and not state.verified
    assert any("INDEX_TAIL_INVALID" in problem for problem in state.problems)
    later = build_from_observations(a_project, _later_obs("acme/widget", "42"), store)
    assert later.manifest["comparison_status"] == "HISTORY_GAP", "the id the damaged index claims is recorded, the bundle behind it is never compared against"
    delta = json.loads(later.members["delta.json"])
    assert {row["transition_class"] for row in delta["vitals"]} == {"INCOMPARABLE"}
    assert any("INDEX_TAIL_INVALID" in reason for reason in delta["incomparable_reasons"])


def test_an_absolute_tail_path_is_refused(tmp_path):
    store, (a, _, _), (b, b_path) = _two_projects(tmp_path)
    _rewrite_tail(store, "github.com/acme/widget", path=str(b_path), bundle_id=b.bundle_id)
    state = store.latest("github.com/acme/widget", "42")
    assert not state.verified and any("INDEX_TAIL_INVALID" in problem for problem in state.problems)


def test_a_tail_whose_basename_is_not_its_bundle_id_is_refused(tmp_path):
    store, (a, a_path, _), _ = _two_projects(tmp_path)
    alias = a_path.with_name("a" * 64)
    shutil.copytree(a_path, alias)
    _rewrite_tail(store, "github.com/acme/widget", path=alias.relative_to(store.project_dir("github.com/acme/widget")).as_posix())
    state = store.latest("github.com/acme/widget", "42")
    assert not state.verified and any("INDEX_TAIL_INVALID" in problem for problem in state.problems)


def test_another_projects_bundle_inside_the_history_tree_is_refused_by_identity(tmp_path):
    """The path is canonical and the bundle verifies internally; it is still not this project's history."""
    store, (a, a_path, a_project), (b, b_path) = _two_projects(tmp_path)
    copied = a_path.with_name(b.bundle_id)
    shutil.copytree(b_path, copied)
    _rewrite_tail(store, "github.com/acme/widget", path=copied.relative_to(store.project_dir("github.com/acme/widget")).as_posix(), bundle_id=b.bundle_id)
    state = store.latest("github.com/acme/widget", "42")
    assert state.exists and not state.verified
    assert any(problem.startswith("PROJECT_IDENTITY_MISMATCH") and "99" in problem and "42" in problem for problem in state.problems)
    later = build_from_observations(a_project, _later_obs("acme/widget", "42"), store)
    assert later.manifest["comparison_status"] == "HISTORY_GAP"


def test_without_identities_the_locator_binds_the_bundle(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    a, a_path, a_project = _observe(store, "acme/widget", None)
    b, b_path, _ = _observe(store, "acme/gadget", None)
    copied = a_path.with_name(b.bundle_id)
    shutil.copytree(b_path, copied)
    _rewrite_tail(store, "github.com/acme/widget", path=copied.relative_to(store.project_dir("github.com/acme/widget")).as_posix(), bundle_id=b.bundle_id)
    state = store.latest("github.com/acme/widget")
    assert not state.verified and any(problem.startswith("PROJECT_IDENTITY_MISMATCH") for problem in state.problems)


def test_an_honest_store_still_verifies_and_compares(tmp_path):
    store, (a, _, a_project), _ = _two_projects(tmp_path)
    state = store.latest("github.com/acme/widget", "42")
    assert state.verified and state.bundle_id == a.bundle_id
    later = build_from_observations(a_project, _later_obs("acme/widget", "42"), store)
    assert later.manifest["comparison_status"] == "COMPARABLE" and later.manifest["previous_bundle_id"] == a.bundle_id


def test_an_index_of_the_wrong_shape_is_a_history_gap_and_is_never_appended_to(tmp_path):
    store, (a, _, a_project), _ = _two_projects(tmp_path)
    path = _index_path(store, "github.com/acme/widget")
    before = path.read_bytes()
    path.write_text(json.dumps({"schema": "devostasis.index.v1", "bundles": {"oops": 1}}), "utf-8")
    state = store.latest("github.com/acme/widget", "42")
    assert state.exists and not state.verified and any("index invalid" in problem for problem in state.problems)
    later = build_from_observations(a_project, _later_obs("acme/widget", "42"), store)
    assert later.manifest["comparison_status"] == "HISTORY_GAP"
    with pytest.raises(HistoryStoreError):
        store.commit(later)
    assert path.read_bytes() != before and json.loads(path.read_text("utf-8"))["bundles"] == {"oops": 1}, "the corrupt index is left for diagnosis, not rewritten"


# --------------------------------------------------------------------------- identity lookup (PV-AUDIT-HISTORYSTORE-001)


def test_an_unreadable_index_elsewhere_makes_the_identity_lookup_fail_closed(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    _observe(store, "acme/widget", "42")
    _index_path(store, "github.com/acme/widget").write_text("{ not json", "utf-8")
    with pytest.raises(HistoryStoreError, match="cannot be proven absent"):
        store.find_by_identity("42")
    obs = full_inputs(obs_set("2026-09-06T12:00:00Z"))
    obs.subject = dict(obs.subject, owner="acme", repo="gadget", display_locator="acme/gadget", immutable_project_id="42")
    project = single_project("acme/gadget", config_version="1")
    bundle = build_from_observations(project, obs, store)
    assert bundle.manifest["comparison_status"] == "HISTORY_GAP", "no false BASELINE"
    with pytest.raises(HistoryStoreError):
        store.commit(bundle)
    assert not store.project_dir("github.com/acme/gadget").exists(), "nothing is written for a project whose history may exist elsewhere"


# --------------------------------------------------------------------------- fleet surfaces (PV-AUDIT-FLEET-INDEX-001, PV-AUDIT-FLEET-COVERAGE-001)


def test_a_corrupt_project_index_stops_the_fleet_surfaces_instead_of_dropping_the_project(tmp_path):
    store, _, _ = _two_projects(tmp_path)
    write_fleet_index(store)
    fleet_before = (store.projects_root / "index.json").read_bytes()
    _index_path(store, "github.com/acme/gadget").write_text("{ not json", "utf-8")
    with pytest.raises(HistoryStoreError, match="index unreadable"):
        write_fleet_index(store)
    assert (store.projects_root / "index.json").read_bytes() == fleet_before, "no shortened fleet index passes for a fresh one"


def test_a_single_corrupt_project_is_a_failure_not_an_empty_store(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    _observe(store, "acme/widget", "42")
    _index_path(store, "github.com/acme/widget").write_text("[]", "utf-8")
    with pytest.raises(HistoryStoreError):
        write_fleet_index(store)


def test_a_present_but_unreadable_demand_member_is_not_a_pre_demand_bundle(tmp_path):
    store, (a, a_path, _), _ = _two_projects(tmp_path)
    (a_path / "demand.json").write_text("{ not json", "utf-8")
    with pytest.raises(HistoryStoreError, match="demand member unreadable"):
        store.all_projects()
    (a_path / "demand.json").unlink()
    entry = next(e for e in store.all_projects() if e["locator"] == "acme/widget")
    assert entry["demand_rows"] == [] and entry["attention_order"] == [], "an absent member is the legacy case and stays null"


def test_the_run_command_reports_a_fleet_surface_failure_as_a_store_error(tmp_path, monkeypatch, capsys):
    from devostasis.cli import main

    store = FilesystemHistoryStore(tmp_path / "history")
    _observe(store, "acme/widget", "42")
    _index_path(store, "github.com/acme/widget").write_text("{ not json", "utf-8")
    assert main(["index", "--store", str(tmp_path / "history")]) == 1
    assert "store error" in capsys.readouterr().err


# --------------------------------------------------------------------------- publication (PV-AUDIT-HISTORYSTORE-ATOMIC-PUBLICATION-001)


def test_the_index_is_replaced_never_truncated(tmp_path, monkeypatch):
    store, (a, _, a_project), _ = _two_projects(tmp_path)
    path = _index_path(store, "github.com/acme/widget")
    before = path.read_bytes()
    later = build_from_observations(a_project, _later_obs("acme/widget", "42"), store)

    def refuse(source, destination):
        raise OSError("disk full at the worst moment")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(OSError):
        store.commit(later)
    monkeypatch.undo()
    assert path.read_bytes() == before, "the previous index is byte-for-byte intact"
    assert json.loads(path.read_text("utf-8"))["bundles"][-1]["bundle_id"] == a.bundle_id
    state = store.latest("github.com/acme/widget", "42")
    assert state.verified and state.bundle_id == a.bundle_id
    store.commit(later)
    assert [entry["bundle_id"] for entry in json.loads(path.read_text("utf-8"))["bundles"]] == [a.bundle_id, later.bundle_id], "the retry is idempotent"


def test_a_stale_copy_left_by_an_interrupted_publication_is_recovered_not_a_gap(tmp_path, monkeypatch):
    """HISTORY-PUBLISH-03/05: the index is written before the copy; a failure between the two leaves the previous copy."""
    store, (a, _, a_project), _ = _two_projects(tmp_path)
    later = build_from_observations(a_project, _later_obs("acme/widget", "42"), store)
    original = FilesystemHistoryStore.publish_latest

    def refuse(self, bundle, directory=None):
        raise OSError("interrupted before the copy was refreshed")

    monkeypatch.setattr(FilesystemHistoryStore, "publish_latest", refuse)
    with pytest.raises(OSError):
        store.commit(later)
    monkeypatch.setattr(FilesystemHistoryStore, "publish_latest", original)
    project_dir = store.project_dir("github.com/acme/widget")
    assert json.loads((project_dir / "latest" / "manifest.json").read_text("utf-8"))["bundle_id"] == a.bundle_id, "the previous copy is still there"
    state = store.latest("github.com/acme/widget", "42")
    assert state.verified and state.bundle_id == later.bundle_id, "the index tail is the authority and the stale copy is not a gap"
    third = build_from_observations(a_project, _later_obs("acme/widget", "42", "2026-09-07T12:00:00Z"), store)
    assert third.manifest["comparison_status"] == "COMPARABLE" and third.manifest["previous_bundle_id"] == later.bundle_id
    store.commit(third)
    assert json.loads((project_dir / "latest" / "manifest.json").read_text("utf-8"))["bundle_id"] == third.bundle_id, "the next commit replaces the stale copy"


def test_a_copy_of_a_bundle_the_index_does_not_know_is_still_refused(tmp_path):
    store, (a, _, _), (b, _) = _two_projects(tmp_path)
    store.publish_latest(b, store.project_dir("github.com/acme/widget"))
    state = store.latest("github.com/acme/widget", "42")
    assert not state.verified and any("latest pointer" in problem for problem in state.problems)


def test_leftovers_of_an_interrupted_latest_publication_are_cleared_by_the_next(tmp_path):
    store, (a, _, a_project), _ = _two_projects(tmp_path)
    project_dir = store.project_dir("github.com/acme/widget")
    (project_dir / "latest.retired").mkdir()
    (project_dir / "latest.retired" / "junk").write_text("x", "utf-8")
    (project_dir / "latest.staging").mkdir()
    later = build_from_observations(a_project, _later_obs("acme/widget", "42"), store)
    store.commit(later)
    assert not (project_dir / "latest.retired").exists() and not (project_dir / "latest.staging").exists()
    assert json.loads((project_dir / "latest" / "manifest.json").read_text("utf-8"))["bundle_id"] == later.bundle_id


# --------------------------------------------------------------------------- wrapper binding (PV-AUDIT-STORE-BUNDLE-PATH-BINDING-001, PV-AUDIT-STORE-PROJECT-BINDING-001)


def test_a_wrapper_that_disagrees_with_its_manifest_is_refused_before_anything_is_written(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    obs = full_inputs(obs_set())
    bundle = build_from_observations(single_project("acme/widget", config_version="1"), obs, store)
    aliased = Bundle(bundle_id="a" * 64, project_key=bundle.project_key, observed_at=bundle.observed_at, manifest=dict(bundle.manifest), members=dict(bundle.members))
    with pytest.raises(HistoryStoreError, match="BUNDLE_BINDING_MISMATCH"):
        store.commit(aliased)
    rerouted = Bundle(bundle_id=bundle.bundle_id, project_key="github.com/acme/gadget", observed_at=bundle.observed_at, manifest=dict(bundle.manifest), members=dict(bundle.members))
    with pytest.raises(HistoryStoreError, match="BUNDLE_BINDING_MISMATCH"):
        store.commit(rerouted)
    assert not store.projects_root.exists(), "nothing was written"
    store.commit(bundle)
    assert store.latest(bundle.project_key, "123456").verified


# --------------------------------------------------------------------------- locators (PV-AUDIT-STORE-PATH-001, PV-AUDIT-PROJECT-LOCATOR-ALIAS-001)


@pytest.mark.parametrize("key", ["github.com/C:\\escape/widget", "github.com/../widget", "github.com/./widget", "github.com/acme", "github.com/acme/widget/extra", "github.com//widget", "github.com/acme/wid get"])
def test_a_key_that_is_not_a_locator_derives_no_store_path(tmp_path, key):
    store = FilesystemHistoryStore(tmp_path)
    with pytest.raises(HistoryStoreError):
        store.project_dir(key)


def test_a_locator_stays_beneath_the_store(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    assert store.project_dir("github.com/acme/widget") == tmp_path / "projects" / "github.com" / "acme" / "widget"


@pytest.mark.parametrize("repo", ["C:\\escape/widget", "../x", "acme/..", "acme/wid get", "acme/", "/widget"])
def test_a_configured_repo_that_is_not_a_locator_is_rejected(repo):
    with pytest.raises(ConfigError):
        single_project(repo)


def test_case_variants_of_one_locator_are_one_configured_project():
    raw = {"schema": "devostasis.config.v1", "config_version": "1", "projects": [{"repo": "DREVENDEV/DEVOSTASIS"}, {"repo": "drevendev/Devostasis"}]}
    with pytest.raises(ConfigError, match="duplicate project"):
        load_config_dict(raw)


def test_two_locators_the_provider_resolves_to_one_repository_are_observed_once(tmp_path, monkeypatch):
    from devostasis.config import Config

    seen: list[str] = []

    def fake_run_project(project, store, client, now, *, admitted=None):
        seen.append(project.locator)
        obs = full_inputs(obs_set("2026-09-05T12:00:00Z"))
        obs.subject = dict(obs.subject, owner=project.owner, repo=project.repo, display_locator=project.locator, immutable_project_id="42")
        key = f"github.com:42"
        earlier = admitted.get(key) if admitted is not None else None
        if earlier is not None and earlier != project.locator:
            return RunOutcome(project.locator, False, error=f"DUPLICATE_PROJECT_IDENTITY: {project.locator} is repository 42, already observed in this run as {earlier}")
        if admitted is not None:
            admitted[key] = project.locator
        bundle = build_from_observations(project, obs, store)
        store.commit(bundle)
        return RunOutcome(project.locator, True, bundle_id=bundle.bundle_id)

    monkeypatch.setattr(runner, "run_project", fake_run_project)
    config = Config(config_version="1", store_path=str(tmp_path), projects=(single_project("acme/widget", config_version="1"), single_project("acme/alias", config_version="1")))
    outcomes = run_all(config, FilesystemHistoryStore(tmp_path), None, NOW)
    assert seen == ["acme/widget", "acme/alias"]
    assert outcomes[0].ok and not outcomes[1].ok and "DUPLICATE_PROJECT_IDENTITY" in outcomes[1].error
    store = FilesystemHistoryStore(tmp_path)
    assert store.project_dir("github.com/acme/widget").exists() and not store.project_dir("github.com/acme/alias").exists()
    index = json.loads(_index_path(store, "github.com/acme/widget").read_text("utf-8"))
    assert "renames" not in index and len(index["bundles"]) == 1


def test_run_project_refuses_the_second_locator_of_one_repository_before_writing(tmp_path):
    """The real run_project, with the admitted map the fleet run keeps: the alias never reaches the store."""
    from devostasis.adapters.github import GitHubAdapter, GitHubClient
    from test_github_adapter import BASE, FakeTransport, _routes

    routes = _routes()
    alias_base = "/repos/acme/ALIAS"
    for path, handler in list(routes.items()):
        routes[path.replace(BASE, alias_base)] = handler
    store = FilesystemHistoryStore(tmp_path)
    admitted: dict[str, str] = {}
    first = runner.run_project(single_project("acme/widget"), store, GitHubClient(FakeTransport(routes)), NOW, admitted=admitted)
    second = runner.run_project(single_project("acme/ALIAS"), store, GitHubClient(FakeTransport(routes)), NOW, admitted=admitted)
    assert first.ok and not second.ok and second.error.startswith("DUPLICATE_PROJECT_IDENTITY")
    assert not store.project_dir("github.com/acme/ALIAS").exists()


# --------------------------------------------------------------------------- configuration shape (PV-AUDIT-CONFIG-SHAPE-001)


@pytest.mark.parametrize(
    "raw, message",
    [
        ({"schema": "devostasis.config.v1", "config_version": "1", "projects": [{"repo": "a/b", "activity": {"enabled": "false"}}]}, "activity.enabled must be a boolean"),
        ({"schema": "devostasis.config.v1", "config_version": "1", "projects": [{"repo": "a/b"}], "store": "tmp"}, "store must be an object"),
        ({"schema": "devostasis.config.v1", "config_version": "1", "projects": [{"repo": "a/b"}], "store": {"path": 3}}, "store.path must be a non-empty string"),
        ({"schema": "devostasis.config.v1", "config_version": "1", "projects": [{"repo": "a/b"}], "store": {"bucket": "x"}}, "store key"),
    ],
)
def test_configuration_of_the_wrong_shape_is_rejected_not_coerced(raw, message):
    with pytest.raises(ConfigError, match=message):
        load_config_dict(raw)


def _later_obs(locator, project_id, observed_at="2026-09-06T12:00:00Z"):
    owner, repo = locator.split("/")
    obs = full_inputs(obs_set(observed_at))
    obs.subject = dict(obs.subject, owner=owner, repo=repo, display_locator=locator, immutable_project_id=project_id)
    return obs
