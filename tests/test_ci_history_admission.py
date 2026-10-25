"""Release-review regressions at real observation, evaluator and bundle boundaries."""

from copy import deepcopy
import json

import pytest

from devostasis.bundle import verify_dir
from devostasis.config import single_project
from devostasis.history import FilesystemHistoryStore
from devostasis.observations import ObservationSet
from devostasis.revision_history import (
    CARRIED, LINEAGE, REPLAYABLE_LINEAGE, parent_from_current, union_state,
)
from devostasis.runner import build_from_observations
from devostasis.vitals import integrity
from helpers import add
from test_revision_history import (
    LOCATOR, _build, _integrity, _obs, _passing, _record, _run, _states,
)


@pytest.mark.parametrize("conflicting,reverse", [(False, False), (True, False), (True, True)])
def test_duplicate_current_revisions_never_improve_sample_or_overwrite_failure(tmp_path, conflicting, reverse):
    rows = _passing([1, 2, 3])
    duplicate = deepcopy(rows[0]) if not conflicting else _record("p1", 1, [_run(801, [(1, "VERIFY_FAIL")])])
    rows.append(duplicate)
    if reverse:
        rows.reverse()
    obs = ObservationSet.from_dict(_obs("2026-09-08T12:00:00Z", rows).to_dict())
    original = deepcopy(obs.to_dict())
    store = FilesystemHistoryStore(tmp_path)
    project = single_project(LOCATOR, config_version="1")
    bundle = build_from_observations(project, obs, store)
    result = _integrity(bundle)
    assert (result["band"], result["evaluation_status"]) == (None, "UNKNOWN")
    assert "REVISION_RECORD_DUPLICATE:p1" in result["diagnostics"]
    assert obs.to_dict() == original
    assert verify_dir(store.commit(bundle)) == []
    saved = ObservationSet.from_dict(json.loads(bundle.members["observations.json"]))
    assert build_from_observations(project, saved, FilesystemHistoryStore(tmp_path / "replay")).members == bundle.members


@pytest.mark.parametrize("bad", [None, [], {}, {"revision": "r"}, {"revision": "", "committed_at": "2026-09-04T10:00:00Z"},
    {"revision": 7, "committed_at": "2026-09-04T10:00:00Z"}, {"revision": "r", "committed_at": None},
    {"revision": "r", "committed_at": "invalid"}])
def test_malformed_current_inventory_cannot_prove_carried_failure_left_branch(tmp_path, bad):
    store = FilesystemHistoryStore(tmp_path)
    _build(store, "2026-09-06T12:00:00Z", [_record("r", 4, [_run(41, [(1, "VERIFY_FAIL")])])])
    bundle, path = _build(store, "2026-09-07T12:00:00Z", _passing([1, 2, 3, 5]) + [bad])
    assert _integrity(bundle)["evaluation_status"] == "UNKNOWN"
    assert _states(bundle)["r"] == "FAILURE_OBSERVED"
    assert verify_dir(path) == []


@pytest.mark.parametrize("bad_time", ["invalid", "2026-08-01T10:00:00Z", "2026-10-01T10:00:00Z"])
def test_four_bundles_preserve_failure_after_rejected_immutable_timestamp(tmp_path, bad_time):
    store = FilesystemHistoryStore(tmp_path)
    passing = _passing([1, 2, 3, 5])
    failed = _record("r", 4, [_run(41, [(1, "VERIFY_FAIL")])])
    _build(store, "2026-09-06T12:00:00Z", passing + [failed])
    corrupted = _record("r", 4, [_run(41, [(2, "VERIFY_PASS")], latest=2)])
    corrupted["committed_at"] = bad_time
    second, second_path = _build(store, "2026-09-07T12:00:00Z", passing + [corrupted])
    assert _states(second)["r"] == "FAILURE_OBSERVED"
    assert _integrity(second)["evaluation_status"] == "UNKNOWN"
    assert verify_dir(second_path) == []
    for day in (8, 9):
        bundle, path = _build(store, f"2026-09-{day:02d}T12:00:00Z", passing + [_record("r", 4, [_run(41, [(2, "VERIFY_PASS")], latest=2)])])
        result = _integrity(bundle)
        record = next(r for r in result["derived"]["revision_history"]["records"] if r["revision"] == "r")
        assert record["committed_at"] == failed["committed_at"]
        assert record["history_state"] == "FAILURE_OBSERVED"
        assert result["derived"]["failed_count_14d"] == 1 and result["band"] == "FLAKY"
        assert verify_dir(path) == []


def test_equivalent_timestamp_and_proven_departure_remain_admissible(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    failed = _record("r", 4, [_run(41, [(1, "VERIFY_FAIL")])])
    _build(store, "2026-09-06T12:00:00Z", [failed])
    equivalent = deepcopy(failed); equivalent["committed_at"] = "2026-09-04T12:00:00+02:00"
    bundle, _ = _build(store, "2026-09-07T12:00:00Z", [equivalent])
    assert _states(bundle)["r"] == "FAILURE_OBSERVED"
    assert not any("IMMUTABLE_COMMIT_TIME_MISMATCH" in d for d in _integrity(bundle)["diagnostics"])
    partial, _ = _build(store, "2026-09-08T12:00:00Z", [], series_status="PARTIAL")
    assert _states(partial)["r"] == "FAILURE_OBSERVED"
    departed, _ = _build(store, "2026-09-09T12:00:00Z", [])
    assert "r" not in _states(departed)


@pytest.mark.parametrize("attempts,latest", [([(1, "VERIFY_PASS"), (3, "VERIFY_PASS")], 3),
    ([(1, "VERIFY_PASS"), (2, "VERIFY_PASS"), (3, "VERIFY_PASS")], 2),
    ([(1, "VERIFY_PASS")], 10**12), ([(1, "UNKNOWN"), (2, "VERIFY_PASS")], 2)])
def test_incomplete_or_unknown_attempts_never_prove_pass_only(attempts, latest):
    parent = parent_from_current(_run(41, attempts, latest=latest), "test")
    assert union_state([parent], []) == ("UNKNOWN_HISTORY", False)


@pytest.mark.parametrize("lineage", [LINEAGE, REPLAYABLE_LINEAGE])
def test_unknown_attempts_stay_unknown_in_carried_lineages(lineage):
    from devostasis.revision_history import encode, union_record
    raw = _record("r", 4, [_run(41, [(1, "UNKNOWN"), (2, "VERIFY_PASS")])])
    records = [raw] if lineage == REPLAYABLE_LINEAGE else [encode(union_record("r", raw["committed_at"], [parent_from_current(raw["parents"][0], "test")], []))]
    obs = _obs("2026-09-08T12:00:00Z", [_record("r", 4, [])])
    add(obs, CARRIED, {"lineage": lineage, "records": records}, "record")
    assert integrity.evaluate(obs).band is None
    assert integrity.evaluate(obs).derived["revision_history"]["records"][0]["history_state"] == "UNKNOWN_HISTORY"


def test_unknown_vocabulary_is_rejected_but_legitimate_transitions_and_failures_survive():
    from devostasis.revision_history import HistoryShapeError, merge_parents
    with pytest.raises(HistoryShapeError):
        parent_from_current(_run(41, [(1, "NOT_A_CI_STATE")]), "test")
    pending = parent_from_current(_run(41, [(1, "VERIFY_UNRESOLVED")]), "test")
    passed = parent_from_current(_run(41, [(1, "VERIFY_PASS")]), "test")
    for first, second in ((pending, passed), (passed, pending)):
        merged, conflicts = merge_parents([first], [second])
        assert union_state(merged, conflicts) == ("PASS_ONLY_OBSERVED", True)
    failed = parent_from_current(_run(41, [(1, "VERIFY_FAIL"), (3, "UNKNOWN")], latest=3), "test")
    assert union_state([failed], []) == ("FAILURE_OBSERVED", False)


def test_current_revision_metadata_matches_its_reconciled_unknown_history():
    from helpers import parent, revision
    raw = revision("new", "2026-09-06T10:00:00Z", [parent("p-new", "UNKNOWN")], "UNKNOWN", "NO_DECISIVE_OBSERVED")
    result = integrity.evaluate(_obs("2026-09-08T12:00:00Z", _passing([1, 2, 3]) + [raw]))
    assert result.derived["current_revision"]["history_state"] == "UNKNOWN_HISTORY"
    assert result.derived["unknown_history_count_14d"] == 1
