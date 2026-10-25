"""Issue #83: legacy conversion must not erase malformed value-bearing series.

Valid PARTIAL inventory-gap semantics belong to #87, not this admission repair.
"""

from copy import deepcopy
import json

import pytest

from devostasis.bundle import verify_dir
from devostasis.config import single_project
from devostasis.history import FilesystemHistoryStore
from devostasis.observations import ObservationSet
from devostasis.revision_history import (
    BASIS_SERIES, CARRIED, LINEAGE, REPLAYABLE_LINEAGE, REVISIONS,
    HistoryShapeError, _carried_records, carried_observation, reconcile,
    with_carried_history,
)
from devostasis.runner import build_from_observations
from devostasis.vitals import integrity
from test_revision_history import (
    LOCATOR, _carried, _integrity, _obs, _older_bundle, _passing,
    _record, _run, _states,
)


STATUSES = ["AVAILABLE", "PARTIAL"]
BAD_VALUES = [
    pytest.param(None, id="null"),
    pytest.param(False, id="false"),
    pytest.param(0, id="zero"),
    pytest.param("", id="empty-string"),
    pytest.param({}, id="object"),
]


def _legacy(status, value, *, present=True):
    series = {"observation_id": REVISIONS, "status": status}
    if present:
        series["value"] = value
    previous = {"observations": [series]}
    original = deepcopy(previous)
    carried = carried_observation(
        comparison_status="COMPATIBLE",
        previous_bundle_id="verified-previous-bundle",
        previous_manifest={"observed_at": "2026-09-07T12:00:00Z"},
        previous_snapshot={"vitals": []},
        previous_observations=previous,
        reasons=[], observed_at="2026-09-08T12:00:00Z",
    )
    assert previous == original, "conversion must not mutate the predecessor"
    assert carried.value["lineage"] == REPLAYABLE_LINEAGE
    assert carried.value["basis"] == BASIS_SERIES
    assert carried.value["source_series_status"] == status
    assert carried.value["source_bundle_id"] == "verified-previous-bundle"
    assert carried.evidence_ref == {"previous_bundle_id": "verified-previous-bundle"}
    return carried


@pytest.mark.parametrize("status", STATUSES)
@pytest.mark.parametrize("bad", BAD_VALUES)
def test_legacy_conversion_preserves_malformed_series_for_admission(status, bad):
    carried = _legacy(status, bad)
    assert type(carried.value["records"]) is type(bad)
    assert carried.value["records"] == bad
    with pytest.raises(HistoryShapeError, match="no lineage or no records"):
        _carried_records(carried.value)


@pytest.mark.parametrize("status", STATUSES)
@pytest.mark.parametrize("bad", BAD_VALUES)
def test_legacy_malformed_series_cannot_produce_a_favorable_vital(status, bad):
    obs = _obs("2026-09-08T12:00:00Z", _passing([1, 2, 3, 5]))
    control = integrity.evaluate(obs)
    assert (control.evaluation_status, control.band) == ("AVAILABLE", "CLEAN")
    combined = with_carried_history(obs, _legacy(status, bad))
    history = reconcile(combined)
    assert history.source["status"] == "MALFORMED"
    assert any(d.startswith("REVISION_HISTORY_CARRY_MALFORMED:") for d in history.problems)
    result = integrity.evaluate(combined)
    assert (result.evaluation_status, result.band) == ("UNKNOWN", None)
    assert any(d.startswith("REVISION_HISTORY_CARRY_MALFORMED:") for d in result.diagnostics)
    assert result.derived["revision_history"]["source"]["status"] == "MALFORMED"
    assert CARRIED not in obs


@pytest.mark.parametrize("status", STATUSES)
def test_legacy_real_empty_array_retains_conversion_compatibility(status):
    # This checks shape compatibility, not proof of complete acquisition (#87).
    carried = _legacy(status, [])
    assert carried.value["records"] == []
    assert _carried_records(carried.value)[0] == []


@pytest.mark.parametrize("status", STATUSES)
@pytest.mark.parametrize("state,expected", [
    ("VERIFY_FAIL", "FAILURE_OBSERVED"),
    ("VERIFY_PASS", "PASS_ONLY_OBSERVED"),
])
def test_legacy_valid_attempts_and_window_projection_survive(status, state, expected):
    parent = _run(41, [(1, state)])
    raw = _record("r", 4, [parent])
    old = dict(raw, revision="expired", committed_at="2026-08-01T10:00:00Z")
    carried = _legacy(status, [old, raw])
    projected = carried.value["records"]
    assert len(projected) == 1
    assert set(projected[0]) == {"revision", "committed_at", "parents"}
    assert projected[0]["parents"] == [{k: parent[k] for k in (
        "parent_id", "kind", "current_attempt", "attempts_observed",
    )}]
    records, _ = _carried_records(carried.value)
    assert records[0]["history_state"] == expected
    assert records[0]["historical_contribution"] == state


@pytest.mark.parametrize("status", STATUSES)
def test_legacy_missing_value_is_malformed_rather_than_empty(status):
    obs = _obs("2026-09-08T12:00:00Z", _passing([1, 2, 3, 5]))
    result = integrity.evaluate(with_carried_history(obs, _legacy(status, None, present=False)))
    assert (result.evaluation_status, result.band) == ("UNKNOWN", None)
    assert any(d.startswith("REVISION_HISTORY_CARRY_MALFORMED:") for d in result.diagnostics)


@pytest.mark.parametrize("status", STATUSES)
def test_legacy_failure_survives_four_generations_and_exact_replay(tmp_path, status):
    project = single_project(LOCATOR, config_version="1")
    store = FilesystemHistoryStore(tmp_path)
    failed = _record("r", 4, [_run(41, [(1, "VERIFY_FAIL"), (2, "VERIFY_PASS")])])
    older = _older_bundle(project, _obs(
        "2026-09-06T12:00:00Z", _passing([1, 2, 3]) + [failed], series_status=status,
    ))
    assert verify_dir(store.commit(older)) == []
    previous = older
    for day in (7, 8, 9):
        bundle = build_from_observations(project, _obs(
            f"2026-09-{day:02d}T12:00:00Z",
            _passing([1, 2, 3, 5]) + [_record("r", 4, [])],
        ), store)
        carrier = _carried(bundle)
        assert carrier["value"]["source_bundle_id"] == previous.bundle_id
        assert carrier["value"]["lineage"] == (REPLAYABLE_LINEAGE if day == 7 else LINEAGE)
        if day == 7:
            assert carrier["value"]["source_series_status"] == status
        assert _states(bundle)["r"] == "FAILURE_OBSERVED"
        assert _integrity(bundle)["derived"]["failed_count_14d"] == 1
        assert _integrity(bundle)["band"] == "FLAKY"
        saved = ObservationSet.from_dict(json.loads(bundle.members["observations.json"]))
        replayed = build_from_observations(project, saved, store)
        assert replayed.bundle_id == bundle.bundle_id
        assert replayed.members == bundle.members
        assert verify_dir(store.commit(bundle)) == []
        previous = bundle
