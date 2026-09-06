"""Machine-readable fleet index (``devostasis.fleet.v1``).

``projects/README.md`` cannot be parsed without guessing, so a store also
carries ``projects/index.json``. The index must add no meaning, stay stable
between identical runs, and never grow an aggregate or a cross-project order.
"""

from __future__ import annotations

import json

import pytest

from devostasis import canonical, fleet
from devostasis.config import single_project
from devostasis.contracts import CORE_VITAL_IDS
from devostasis.history import FilesystemHistoryStore
from devostasis.runner import build_from_observations, write_fleet_index
from helpers import full_inputs, obs_set


def _store_with(tmp_path, projects=("acme/widget",), observed_at="2026-09-05T12:00:00Z"):
    store = FilesystemHistoryStore(tmp_path)
    for locator in projects:
        obs = full_inputs(obs_set(observed_at))
        obs.subject = dict(obs.subject, owner=locator.split("/")[0], repo=locator.split("/")[1], display_locator=locator)
        bundle = build_from_observations(single_project(locator, config_version="1"), obs, store)
        store.commit(bundle)
    write_fleet_index(store)
    return store


def _index(store):
    return json.loads((store.root / "projects" / "index.json").read_text("utf-8"))


def test_the_index_is_written_beside_the_overview(tmp_path):
    store = _store_with(tmp_path)
    assert (store.root / "projects" / "README.md").exists()
    document = _index(store)
    assert document["schema"] == "devostasis.fleet.v1"
    assert len(document["projects"]) == 1


def test_every_entry_carries_the_bundle_it_came_from(tmp_path):
    store = _store_with(tmp_path)
    entry = _index(store)["projects"][0]
    assert entry["project_key"] == "github.com/acme/widget"
    assert entry["locator"] == "acme/widget"
    assert entry["comparison_status"] == "BASELINE"
    assert entry["previous_bundle_id"] is None
    bundle_dir = store.root / "projects" / entry["bundle_path"]
    manifest = json.loads((bundle_dir / "manifest.json").read_text("utf-8"))
    assert manifest["bundle_id"] == entry["bundle_id"]
    assert (store.root / "projects" / entry["report_path"]).exists()


def test_the_index_repeats_the_bundle_and_invents_nothing(tmp_path):
    """Every value must be findable in the bundle the entry points at."""
    store = _store_with(tmp_path)
    entry = _index(store)["projects"][0]
    latest = store.root / "projects" / "github.com" / "acme" / "widget" / "latest"
    demand = json.loads((latest / "demand.json").read_text("utf-8"))
    rows = {row["vital_id"]: row for row in demand["vitals"]}
    assert set(entry["vitals"]) == set(CORE_VITAL_IDS)
    for vital_id, cell in entry["vitals"].items():
        assert cell["band"] == rows[vital_id]["band"]
        assert cell["gauge"] == rows[vital_id]["gauge"]
        assert cell["level"] == rows[vital_id]["level"]
        assert cell["evaluation_status"] == rows[vital_id]["evaluation_status"]
    assert entry["attention_order"] == [{"vital_id": item["vital_id"], "level": item["level"]} for item in demand["attention_order"]]
    assert entry["attention"] == f"{demand['attention_order'][0]['vital_id']} {demand['attention_order'][0]['level']}"


def test_there_is_no_aggregate_and_no_cross_project_order(tmp_path):
    store = _store_with(tmp_path, projects=("acme/widget", "acme/gadget"))
    document = _index(store)
    assert document["aggregate"] is None and document["cross_project_order"] is None
    text = (store.root / "projects" / "index.json").read_text("utf-8")
    for forbidden in ("score", "rank", "worst", "health", "total"):
        assert forbidden not in text.lower(), forbidden


def test_projects_are_ordered_by_key_so_the_file_is_stable(tmp_path):
    store = _store_with(tmp_path, projects=("acme/widget", "acme/gadget", "acme/thing"))
    keys = [entry["project_key"] for entry in _index(store)["projects"]]
    assert keys == sorted(keys)


def test_rewriting_an_unchanged_store_produces_identical_bytes(tmp_path):
    """No wall-clock timestamp may leak in, or every run would dirty the store."""
    store = _store_with(tmp_path)
    first = (store.root / "projects" / "index.json").read_bytes()
    write_fleet_index(store)
    assert (store.root / "projects" / "index.json").read_bytes() == first


def test_the_fleet_index_is_not_mistaken_for_a_project(tmp_path):
    """all_projects globs index.json; the fleet index sits in the same tree."""
    store = _store_with(tmp_path)
    write_fleet_index(store)
    assert [entry["project_key"] for entry in store.all_projects()] == ["github.com/acme/widget"]
    assert len(_index(store)["projects"]) == 1


def test_a_bundle_without_a_demand_member_yields_null_levels(tmp_path):
    """Bundles written before the demand interface existed must not get invented levels."""
    store = _store_with(tmp_path)
    (store.root / "projects" / "github.com" / "acme" / "widget" / "latest" / "demand.json").unlink()
    write_fleet_index(store)
    entry = _index(store)["projects"][0]
    assert entry["attention_order"] == []
    for vital_id, cell in entry["vitals"].items():
        assert cell["level"] is None and cell["evaluation_status"] is None
        assert cell["band"] is not None, vital_id


def test_an_unreadable_demand_member_degrades_instead_of_failing(tmp_path):
    store = _store_with(tmp_path)
    (store.root / "projects" / "github.com" / "acme" / "widget" / "latest" / "demand.json").write_text("{ not json", "utf-8")
    write_fleet_index(store)
    assert _index(store)["projects"][0]["vitals"]["flow"]["level"] is None


def test_an_empty_store_writes_nothing(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    assert write_fleet_index(store) is None
    assert not (store.root / "projects" / "index.json").exists()


@pytest.mark.parametrize("key", ["schema", "canonical_semantics", "aggregate", "cross_project_order", "projects"])
def test_the_document_matches_its_published_schema(tmp_path, key):
    schema = canonical.load_file("schemas/fleet-index.schema.json")
    document = _index(_store_with(tmp_path))
    assert key in schema["required"] and key in document
    entry_schema = schema["properties"]["projects"]["items"]
    assert set(document["projects"][0]) == set(entry_schema["required"])


def test_build_index_is_a_pure_function_of_its_entries():
    entries = [
        {
            "project_key": "github.com/acme/widget",
            "locator": "acme/widget",
            "immutable_project_id": "1",
            "observed_at": "2026-09-05T12:00:00Z",
            "bundle_id": "a" * 64,
            "previous_bundle_id": None,
            "comparison_status": "BASELINE",
            "bands": {vital: "CLEAN" for vital in CORE_VITAL_IDS},
            "gauges": {vital: 1 for vital in CORE_VITAL_IDS},
            "top_attention": "flow LOW",
            "demand_rows": [],
            "attention_order": [],
            "report_path": "r",
            "bundle_path": "b",
        }
    ]
    assert fleet.build_index(entries) == fleet.build_index(entries)
    cell = fleet.build_index(entries)["projects"][0]["vitals"]["flow"]
    assert cell == {"band": "CLEAN", "evaluation_status": None, "gauge": 1, "level": None}
