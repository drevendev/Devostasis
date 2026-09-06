"""A project is its immutable id, not its path (RPT-7).

Renaming or transferring a repository used to split its history in two: the
old directory became an orphan nobody read again, and the new one started at
BASELINE as if the project had just been born. The store now locates a project
by the provider's immutable id, relocates the directory once, and records the
rename.
"""

from __future__ import annotations

import json

import pytest

from devostasis.config import single_project
from devostasis.history import FilesystemHistoryStore, IdentityConflictError
from devostasis.runner import build_from_observations, write_fleet_index
from helpers import full_inputs, obs_set


def _observe(store, locator, project_id, observed_at, **project_kwargs):
    """One bundle for `locator` whose subject carries `project_id`."""
    owner, repo = locator.split("/")
    obs = full_inputs(obs_set(observed_at))
    obs.subject = dict(obs.subject, owner=owner, repo=repo, display_locator=locator, immutable_project_id=project_id)
    project = single_project(locator, config_version="1", **project_kwargs)
    bundle = build_from_observations(project, obs, store)
    path = store.commit(bundle)
    return bundle, path


def _index(store, key):
    return json.loads((store.project_dir(key) / "index.json").read_text("utf-8"))


def test_rpt_7_a_renamed_repository_keeps_one_history(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    first, _ = _observe(store, "acme/widget", "42", "2026-09-05T12:00:00Z")
    second, _ = _observe(store, "acme/gadget", "42", "2026-09-06T12:00:00Z")

    assert second.manifest["comparison_status"] == "COMPARABLE"
    assert second.manifest["previous_bundle_id"] == first.bundle_id

    index = _index(store, "github.com/acme/gadget")
    assert [entry["bundle_id"] for entry in index["bundles"]] == [first.bundle_id, second.bundle_id]
    assert index["project_key"] == "github.com/acme/gadget"


def test_the_old_directory_is_moved_not_copied(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    _observe(store, "acme/widget", "42", "2026-09-05T12:00:00Z")
    _observe(store, "acme/gadget", "42", "2026-09-06T12:00:00Z")
    assert not store.project_dir("github.com/acme/widget").exists()
    assert (store.project_dir("github.com/acme/gadget") / "latest").exists()


def test_the_rename_is_recorded_rather_than_silent(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    _observe(store, "acme/widget", "42", "2026-09-05T12:00:00Z")
    second, _ = _observe(store, "acme/gadget", "42", "2026-09-06T12:00:00Z")
    renames = _index(store, "github.com/acme/gadget")["renames"]
    assert renames == [
        {
            "from": "github.com/acme/widget",
            "to": "github.com/acme/gadget",
            "observed_at": "2026-09-06T12:00:00Z",
            "bundle_id": second.bundle_id,
        }
    ]


def test_a_transfer_to_another_owner_is_the_same_event(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    first, _ = _observe(store, "acme/widget", "42", "2026-09-05T12:00:00Z")
    second, _ = _observe(store, "globex/widget", "42", "2026-09-06T12:00:00Z")
    assert second.manifest["comparison_status"] == "COMPARABLE"
    assert second.manifest["previous_bundle_id"] == first.bundle_id
    assert _index(store, "github.com/globex/widget")["renames"][0]["from"] == "github.com/acme/widget"


def test_an_old_name_reused_by_a_new_repository_is_a_new_project(tmp_path):
    """Rename widget to gadget, then create a fresh widget. The two must not merge."""
    store = FilesystemHistoryStore(tmp_path)
    _observe(store, "acme/widget", "42", "2026-09-05T12:00:00Z")
    _observe(store, "acme/gadget", "42", "2026-09-06T12:00:00Z")
    fresh, _ = _observe(store, "acme/widget", "99", "2026-09-07T12:00:00Z")

    assert fresh.manifest["comparison_status"] == "BASELINE"
    assert len(_index(store, "github.com/acme/widget")["bundles"]) == 1
    assert len(_index(store, "github.com/acme/gadget")["bundles"]) == 2
    assert _index(store, "github.com/acme/widget")["project_identity"]["immutable_project_id"] == "99"


def test_a_locator_held_by_another_project_fails_closed(tmp_path):
    """Two projects claiming one directory must not be merged into one history."""
    store = FilesystemHistoryStore(tmp_path)
    _observe(store, "acme/widget", "42", "2026-09-05T12:00:00Z")
    _observe(store, "acme/gadget", "99", "2026-09-05T12:00:00Z")

    with pytest.raises(IdentityConflictError):
        _observe(store, "acme/gadget", "42", "2026-09-06T12:00:00Z")

    assert len(_index(store, "github.com/acme/gadget")["bundles"]) == 1
    assert _index(store, "github.com/acme/gadget")["project_identity"]["immutable_project_id"] == "99"
    assert store.project_dir("github.com/acme/widget").exists()


def test_a_conflict_is_reported_before_anything_is_written(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    _observe(store, "acme/widget", "42", "2026-09-05T12:00:00Z")
    _observe(store, "acme/gadget", "99", "2026-09-05T12:00:00Z")
    state = store.latest("github.com/acme/gadget", "42")
    assert state.exists and not state.verified
    assert any("refusing to merge" in problem for problem in state.problems)


def test_without_an_immutable_id_the_locator_is_the_identity(tmp_path):
    """An adapter that cannot prove an id loses continuity honestly, never by guessing."""
    store = FilesystemHistoryStore(tmp_path)
    _observe(store, "acme/widget", None, "2026-09-05T12:00:00Z")
    second, _ = _observe(store, "acme/gadget", None, "2026-09-06T12:00:00Z")
    assert second.manifest["comparison_status"] == "BASELINE"
    assert store.project_dir("github.com/acme/widget").exists()
    assert "renames" not in _index(store, "github.com/acme/gadget")


def test_an_unchanged_locator_is_never_recorded_as_a_rename(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    _observe(store, "acme/widget", "42", "2026-09-05T12:00:00Z")
    _observe(store, "acme/widget", "42", "2026-09-06T12:00:00Z")
    index = _index(store, "github.com/acme/widget")
    assert "renames" not in index and len(index["bundles"]) == 2


def test_the_fleet_surfaces_show_a_renamed_project_once(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    _observe(store, "acme/widget", "42", "2026-09-05T12:00:00Z")
    _observe(store, "acme/gadget", "42", "2026-09-06T12:00:00Z")
    write_fleet_index(store)

    fleet = json.loads((store.root / "projects" / "index.json").read_text("utf-8"))
    assert [entry["locator"] for entry in fleet["projects"]] == ["acme/gadget"]
    assert fleet["projects"][0]["immutable_project_id"] == "42"

    overview = (store.root / "projects" / "README.md").read_text("utf-8")
    assert "acme/gadget" in overview and "acme/widget" not in overview


def test_history_survives_the_move_and_still_verifies(tmp_path):
    from devostasis.bundle import verify_dir

    store = FilesystemHistoryStore(tmp_path)
    first, _ = _observe(store, "acme/widget", "42", "2026-09-05T12:00:00Z")
    _observe(store, "acme/gadget", "42", "2026-09-06T12:00:00Z")
    directory = store.project_dir("github.com/acme/gadget")
    for entry in _index(store, "github.com/acme/gadget")["bundles"]:
        assert verify_dir(directory / entry["path"]) == []
    moved = json.loads((directory / _index(store, "github.com/acme/gadget")["bundles"][0]["path"] / "manifest.json").read_text("utf-8"))
    assert moved["bundle_id"] == first.bundle_id
    assert moved["project_key"] == "github.com/acme/widget", "a bundle records the locator it was observed under"


def test_resolve_reports_where_a_project_lives(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    _observe(store, "acme/widget", "42", "2026-09-05T12:00:00Z")
    unmoved = store.resolve("github.com/acme/widget", "42")
    assert unmoved.directory == store.project_dir("github.com/acme/widget") and not unmoved.relocated
    moving = store.resolve("github.com/acme/gadget", "42")
    assert moving.relocated and moving.previous_directory == store.project_dir("github.com/acme/widget")
    fresh = store.resolve("github.com/acme/other", "77")
    assert fresh.directory == store.project_dir("github.com/acme/other") and not fresh.relocated
