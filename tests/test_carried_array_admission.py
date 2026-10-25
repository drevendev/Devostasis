"""Issue #83: malformed carried arrays cannot become empty history."""

import pytest

from devostasis.revision_history import (
    CARRIED, LINEAGE, REPLAYABLE_LINEAGE, HistoryShapeError, _carried_records,
    parent_from_current, parent_groups,
)
from devostasis.vitals import integrity
from helpers import add
from test_revision_history import _obs, _passing, _run


FIELDS = [
    pytest.param(LINEAGE, "parent_groups", id="v2-parent-groups"),
    pytest.param(LINEAGE, "unresolved", id="v2-unresolved"),
    pytest.param(REPLAYABLE_LINEAGE, "parents", id="v1-parents"),
]
BAD_ARRAYS = [
    pytest.param(None, id="null"),
    pytest.param(False, id="false"),
    pytest.param(0, id="zero"),
    pytest.param("", id="empty-string"),
    pytest.param({}, id="object"),
]


def _record():
    return {"revision": "r", "committed_at": "2026-09-07T10:00:00Z"}


@pytest.mark.parametrize("lineage,field", FIELDS)
@pytest.mark.parametrize("bad", BAD_ARRAYS)
def test_explicit_malformed_carried_array_is_rejected(lineage, field, bad):
    record = dict(_record(), **{field: bad})
    with pytest.raises(HistoryShapeError, match=f"{field} is not a list"):
        _carried_records({"lineage": lineage, "records": [record]})


@pytest.mark.parametrize("lineage,field", FIELDS)
@pytest.mark.parametrize("bad", BAD_ARRAYS)
def test_malformed_carried_array_cannot_produce_a_favorable_vital(lineage, field, bad):
    obs = _obs("2026-09-08T12:00:00Z", _passing([1, 2, 3, 5]))
    control = integrity.evaluate(obs)
    assert (control.evaluation_status, control.band) == ("AVAILABLE", "CLEAN")
    add(obs, CARRIED, {"lineage": lineage, "records": [dict(_record(), **{field: bad})]}, "record")
    result = integrity.evaluate(obs)
    assert (result.evaluation_status, result.band) == ("UNKNOWN", None)
    assert any(reason.startswith("REVISION_HISTORY_CARRY_MALFORMED:")
               for reason in result.diagnostics)


@pytest.mark.parametrize("lineage,field", FIELDS)
@pytest.mark.parametrize("present", [False, True], ids=["omitted", "empty-array"])
def test_omitted_and_empty_carried_arrays_remain_compatible(lineage, field, present):
    record = _record()
    if present:
        record[field] = []
    records, _ = _carried_records({"lineage": lineage, "records": [record]})
    assert len(records) == 1 and records[0]["revision"] == "r"
    assert records[0]["parents"] == []
    assert records[0]["history_state"] == "NO_DECISIVE_OBSERVED"


@pytest.mark.parametrize("lineage", [LINEAGE, REPLAYABLE_LINEAGE], ids=["v2", "v1"])
def test_valid_carried_failure_survives_array_admission(lineage):
    parent = _run(41, [(1, "VERIFY_FAIL")])
    record = _record()
    if lineage == LINEAGE:
        record["parent_groups"] = parent_groups([parent_from_current(parent, "test")])
    else:
        record["parents"] = [parent]
    records, _ = _carried_records({"lineage": lineage, "records": [record]})
    assert len(records) == 1
    assert records[0]["history_state"] == "FAILURE_OBSERVED"
    assert records[0]["historical_contribution"] == "VERIFY_FAIL"
