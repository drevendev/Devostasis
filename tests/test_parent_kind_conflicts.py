"""Issue #83: parent-kind contradictions survive admission and reconciliation."""

from copy import deepcopy
import json

import pytest

from devostasis.bundle import verify_dir
from devostasis.config import single_project
from devostasis.history import FilesystemHistoryStore
from devostasis.observations import ObservationSet
from devostasis.revision_history import (
    CARRIED, LINEAGE, REPLAYABLE_LINEAGE, HistoryShapeError, _carried_records,
    encode, merge_parents, parent_from_current, reconcile, union_record,
)
from devostasis.runner import build_from_observations
from devostasis.vitals import integrity
from helpers import add
from test_revision_history import (
    LOCATOR, _carried, _integrity, _obs, _older_bundle, _passing, _record, _run,
)


PARENT_ID = "github_actions:workflow_run:41"
CONFLICT = f"PARENT_KIND_CONFLICT:{PARENT_ID}"
ORDERS = [pytest.param(False, id="actions-first"), pytest.param(True, id="suite-first")]
FAILURES = ["none", "actions", "suite"]


def _parents(reverse=False, failed="none"):
    actions = _run(41, [(1, "VERIFY_FAIL" if failed == "actions" else "VERIFY_PASS")])
    suite = _run(41, [(1, "VERIFY_FAIL" if failed == "suite" else "VERIFY_PASS")])
    suite["kind"] = "github_actions_check_suite"
    return [suite, actions] if reverse else [actions, suite]


def _carrier(reverse=False, failed="none", lineage=REPLAYABLE_LINEAGE):
    raw = _record("r", 4, _parents(reverse, failed))
    if lineage == LINEAGE:
        parents, conflicts = merge_parents([parent_from_current(p, "test") for p in raw["parents"]])
        raw = encode(union_record("r", raw["committed_at"], parents, conflicts))
    return {"lineage": lineage, "records": [raw]}


def _current(day=8):
    return _obs(f"2026-09-{day:02d}T12:00:00Z",
                _passing([1, 2, 3, 5]) + [_record("r", 4, [_run(41, [(1, "VERIFY_PASS")])])])


def _assert_conflict(record, failed):
    assert record.get("unresolved") == [CONFLICT]
    assert record["history_complete"] is False
    assert record["history_state"] == ("UNKNOWN_HISTORY" if failed == "none" else "FAILURE_OBSERVED")
    assert record["historical_contribution"] == (None if failed == "none" else "VERIFY_FAIL")
    states = {a["state"] for p in record["parents"] for a in p["attempts"]}
    assert "VERIFY_PASS" in states
    if failed != "none":
        assert "VERIFY_FAIL" in states


@pytest.mark.parametrize("reverse", ORDERS)
@pytest.mark.parametrize("failed", FAILURES)
def test_v1_kind_conflict_is_retained_in_both_orders(reverse, failed):
    raw = _carrier(reverse, failed)
    original = deepcopy(raw)
    records, _ = _carried_records(raw)
    _assert_conflict(records[0], failed)
    assert raw == original


@pytest.mark.parametrize("reverse", ORDERS)
@pytest.mark.parametrize("failed", FAILURES)
@pytest.mark.parametrize("lineage", [REPLAYABLE_LINEAGE, LINEAGE])
def test_kind_conflict_survives_repeated_complete_current_passes(reverse, failed, lineage):
    carrier = _carrier(reverse, failed, lineage)
    for day in (7, 8, 9):
        obs = _current(day)
        control = integrity.evaluate(obs)
        assert (control.evaluation_status, control.band) == ("AVAILABLE", "CLEAN")
        add(obs, CARRIED, carrier, "record")
        original = deepcopy(obs.to_dict())
        history = reconcile(obs)
        _assert_conflict(history.records["r"], failed)
        result = integrity.evaluate(obs)
        if failed == "none":
            assert (result.evaluation_status, result.band) == ("UNKNOWN", None)
            assert "REVISION_HISTORY_UNKNOWN:r" in result.diagnostics
        else:
            assert result.derived["failed_count_14d"] == 1
            assert result.band == "FLAKY"
        carrier = result.derived["revision_history"]
        assert carrier["lineage"] == LINEAGE
        # Normalized output is read back through the actual v2 reader each time.
        decoded, _ = _carried_records(carrier)
        _assert_conflict(next(r for r in decoded if r["revision"] == "r"), failed)
        assert obs.to_dict() == original


@pytest.mark.parametrize("shape", ["same-kind", "distinct-parent"])
@pytest.mark.parametrize("failed", [False, True])
def test_valid_parent_union_remains_compatible(shape, failed):
    first = _run(41, [(1, "VERIFY_PASS")])
    second = _run(42 if shape == "distinct-parent" else 41,
                  [(1, "VERIFY_FAIL" if failed else "VERIFY_PASS")])
    carrier = {"lineage": REPLAYABLE_LINEAGE, "records": [_record("r", 4, [first, second])]}
    records, _ = _carried_records(carrier)
    record = records[0]
    assert not record.get("unresolved")
    assert record["history_complete"] is True
    assert record["history_state"] == ("FAILURE_OBSERVED" if failed else "PASS_ONLY_OBSERVED")
    assert len(record["parents"]) == (2 if shape == "distinct-parent" else 1)


@pytest.mark.parametrize("reverse", ORDERS)
def test_v2_duplicate_parent_groups_still_fail_admission(reverse):
    raw = _record("r", 4, [])
    raw["parent_groups"] = [encode(union_record("r", raw["committed_at"],
        [parent_from_current(p, "test")], []))["parent_groups"][0] for p in _parents(reverse)]
    with pytest.raises(HistoryShapeError, match="is in two groups"):
        _carried_records({"lineage": LINEAGE, "records": [raw]})


@pytest.mark.parametrize("with_conflict", [False, True], ids=["lineage-gap-only", "lineage-and-kind"])
def test_complete_evidence_repairs_lineage_gap_but_not_kind_conflict(with_conflict):
    if with_conflict:
        carrier = _carrier(lineage=LINEAGE)
        carrier["records"][0]["unresolved"].append("LINEAGE_INCOMPATIBLE:old")
    else:
        carrier = {"lineage": "old-unsupported-lineage", "records": [_record("r", 4, [])]}
    obs = _current()
    add(obs, CARRIED, carrier, "record")
    result = integrity.evaluate(obs)
    records, _ = _carried_records(result.derived["revision_history"])
    record = next(r for r in records if r["revision"] == "r")
    if with_conflict:
        _assert_conflict(record, "none")
        assert (result.evaluation_status, result.band) == ("UNKNOWN", None)
    else:
        assert not record.get("unresolved")
        assert record["history_state"] == "PASS_ONLY_OBSERVED"
        assert record["history_complete"] is True
        assert (result.evaluation_status, result.band) == ("AVAILABLE", "CLEAN")


def test_all_structural_kind_markers_survive_lineage_repair():
    carrier = _carrier(lineage=LINEAGE)
    other = "PARENT_KIND_CONFLICT:another-parent"
    carrier["records"][0]["unresolved"] += [other, "LINEAGE_INCOMPATIBLE:old"]
    obs = _current()
    add(obs, CARRIED, carrier, "record")
    assert reconcile(obs).records["r"]["unresolved"] == sorted([CONFLICT, other])


@pytest.mark.parametrize("reason", ["aged-out", "left-branch"])
def test_conflicts_do_not_prevent_normal_revision_removal(reason):
    obs = (_obs("2026-09-20T12:00:00Z", _passing([7, 8, 9]), series_status="PARTIAL")
           if reason == "aged-out" else _obs("2026-09-08T12:00:00Z", _passing([1, 2, 3, 5])))
    add(obs, CARRIED, _carrier(lineage=LINEAGE), "record")
    assert "r" not in reconcile(obs).records


@pytest.mark.parametrize("origin", ["legacy", "current"])
@pytest.mark.parametrize("reverse", ORDERS)
@pytest.mark.parametrize("failed", ["none", "suite"])
def test_kind_conflict_crosses_four_bundles_and_exact_replay(tmp_path, origin, reverse, failed):
    project = single_project(LOCATOR, config_version="1")
    store = FilesystemHistoryStore(tmp_path)
    initial_obs = _obs("2026-09-06T12:00:00Z",
                       _passing([1, 2, 3, 5]) + [_record("r", 4, _parents(reverse, failed))])
    previous = (_older_bundle(project, initial_obs) if origin == "legacy"
                else build_from_observations(project, initial_obs, store))
    assert verify_dir(store.commit(previous)) == []
    for day in (7, 8, 9):
        bundle = build_from_observations(project, _current(day), store)
        carrier = _carried(bundle)["value"]
        assert carrier["source_bundle_id"] == previous.bundle_id
        assert carrier["lineage"] == (REPLAYABLE_LINEAGE if origin == "legacy" and day == 7 else LINEAGE)
        result = _integrity(bundle)
        records, _ = _carried_records(result["derived"]["revision_history"])
        _assert_conflict(next(r for r in records if r["revision"] == "r"), failed)
        assert result["band"] == (None if failed == "none" else "FLAKY")
        saved = ObservationSet.from_dict(json.loads(bundle.members["observations.json"]))
        replayed = build_from_observations(project, saved, store)
        assert replayed.bundle_id == bundle.bundle_id
        assert replayed.members == bundle.members
        assert verify_dir(store.commit(bundle)) == []
        previous = bundle
