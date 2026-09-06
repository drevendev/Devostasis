"""This repository's own registers must stay readable by the engine that reads them.

Devostasis observes itself through ``.devostasis/targets.json`` and
``.devostasis/debt.json``. A typo there does not fail loudly: the adapter
reports ``INVALID_REGISTER`` and Horizon, Direction and Debt fall to UNKNOWN
in the next bundle, which looks like an observability problem rather than a
broken file. These tests turn that into a red build instead.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devostasis.adapters.github import parse_debt_register, parse_targets_register
from devostasis.config import single_project
from devostasis.contracts import CORE_VITAL_IDS
from devostasis.normalize import INV_CRS, INV_DEBT_REGISTER, INV_TARGETS, derive
from devostasis.vitals import build_snapshot
from helpers import add, finalize, obs_set

ROOT = Path(__file__).resolve().parent.parent
TARGETS_PATH = ROOT / ".devostasis" / "targets.json"
DEBT_PATH = ROOT / ".devostasis" / "debt.json"
DEBT_MAPPING_VERSION = "2026-09-06"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_the_workflow_points_at_the_registers_that_exist():
    """self-observe.yml and the files must not drift apart."""
    workflow = (ROOT / ".github" / "workflows" / "self-observe.yml").read_text(encoding="utf-8")
    assert "planning-source: file" in workflow
    assert f"planning-path: {TARGETS_PATH.relative_to(ROOT).as_posix()}" in workflow
    assert f"debt-path: {DEBT_PATH.relative_to(ROOT).as_posix()}" in workflow
    assert f'debt-mapping-version: "{DEBT_MAPPING_VERSION}"' in workflow
    assert 'link-marker: "Target:"' in workflow


def test_targets_register_parses_and_carries_stable_unique_ids():
    targets = parse_targets_register(_load(TARGETS_PATH))
    assert targets, "an empty register is SUPPORTED_UNUSED, which is not what this repository means"
    ids = [item["target_id"] for item in targets]
    assert len(ids) == len(set(ids)), "target ids are never reused"
    assert all(item["state"] in ("OPEN", "CLOSED") for item in targets)
    assert any(item["state"] == "OPEN" for item in targets)


def test_debt_register_parses_and_every_item_is_dated():
    items = parse_debt_register(_load(DEBT_PATH))
    assert items
    ids = [item["id"] for item in items]
    assert len(ids) == len(set(ids))
    for item in items:
        assert item["state"] in ("OPEN", "CLOSED")
        assert item["opened_at"] or item["updated_at"], f"{item['id']} has no date, so staleness cannot be computed"
        if item["state"] == "CLOSED":
            assert item["closed_at"], f"{item['id']} is closed without a closing date"


def test_a_due_date_is_written_only_when_it_is_real():
    """An invented deadline moves Horizon without moving the project."""
    for item in parse_targets_register(_load(TARGETS_PATH)):
        if item["due_at"] is not None:
            assert item["due_at"].endswith("Z"), f"{item['target_id']} has an unparseable due date"


@pytest.mark.parametrize(
    "change_requests, expected_direction",
    [
        ([], "NO_ACTIVE_CHANGE"),
        ([{"refs": ["A1"]}], "FULLY_LINKED"),
        ([{"refs": ["A1"]}, {"refs": []}], "MIXED"),
    ],
)
def test_the_registers_produce_the_bands_they_are_meant_to(change_requests, expected_direction):
    """The content, not only the syntax, must classify: DECLARED and PRESENT rather than UNKNOWN."""
    obs = obs_set("2026-09-06T09:00:00Z")
    add(obs, INV_TARGETS, parse_targets_register(_load(TARGETS_PATH)), "series", coverage={"complete": True, "source": "file"})
    add(obs, INV_DEBT_REGISTER, parse_debt_register(_load(DEBT_PATH)), "series", coverage={"complete": True, "source": "file"})
    add(
        obs,
        INV_CRS,
        [
            {
                "number": index,
                "title": f"pull request {index}",
                "state": "MERGED",
                "created_at": "2026-09-06T08:00:00Z",
                "updated_at": "2026-09-06T08:30:00Z",
                "merged_at": "2026-09-06T08:30:00Z",
                "closed_at": "2026-09-06T08:30:00Z",
                "target_refs": [{"target_id": ref, "state": "OPEN"} for ref in item["refs"]],
                "url": f"https://example.invalid/pull/{index}",
            }
            for index, item in enumerate(change_requests, start=1)
        ],
        "series",
        coverage={"open_complete": True, "window_complete": True},
    )
    project = single_project(
        "drevendev/devostasis",
        planning={"source": "file", "path": TARGETS_PATH.relative_to(ROOT).as_posix()},
        debt={"source": "file", "path": DEBT_PATH.relative_to(ROOT).as_posix(), "mapping_version": DEBT_MAPPING_VERSION},
    )
    derive(obs, project)
    finalize(obs)
    bands = {vital["vital_id"]: vital for vital in build_snapshot(obs)["vitals"]}
    assert [vital_id for vital_id in bands] == list(CORE_VITAL_IDS)
    assert bands["horizon"]["band"] == "DECLARED" and bands["horizon"]["evaluation_status"] == "AVAILABLE"
    assert bands["debt"]["band"] == "PRESENT" and bands["debt"]["evaluation_status"] == "AVAILABLE"
    assert bands["direction"]["band"] == expected_direction
    assert obs.value_of("debt.items.open_stale_count_30d") == 0 or bands["debt"]["band"] == "PRESENT"
