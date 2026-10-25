"""Executable capability acceptance and fail-closed bridge regression checks."""

from copy import deepcopy
from pathlib import Path

import pytest

from devostasis import canonical, vectors
from surface_bridge import execute, load, load_suite

CASES = Path(__file__).parent / "fixtures" / "conformance-surface.json"


@pytest.mark.parametrize("case", load_suite(), ids=lambda c: c["case"])
def test_conformance_surface(case, tmp_path):
    execute(case, tmp_path)


def test_bridge_and_v1_do_not_duplicate_permanent_ids():
    old = {v.case for v in vectors.load([Path(__file__).parent / "vectors"])}
    assert not old.intersection(c["case"] for c in load_suite())


@pytest.mark.parametrize("mutation", ["schema", "scenario", "check", "case", "extra", "empty"])
def test_bridge_unknown_and_duplicate_lineage_never_skips(tmp_path, mutation):
    document = canonical.loads(CASES.read_text(encoding="utf-8"))
    if mutation == "schema": document["schema"] += "+future"
    if mutation == "scenario": document["cases"][0]["scenario"] += "+future"
    if mutation == "check": document["cases"][0]["checks"][0]["ignored"] = True
    if mutation == "case": document["cases"].append(document["cases"][0])
    if mutation == "extra": document["ignored"] = True
    if mutation == "empty": document["cases"] = []
    file = tmp_path / "bad.json"; file.write_bytes(canonical.canonical_bytes(document))
    with pytest.raises(ValueError): load(file)


def test_bridge_consumes_negative_assertions_and_wrong_expectations(tmp_path):
    case = deepcopy(next(c for c in load(CASES) if c["case"] == "ART-08"))
    case["checks"][0]["equals"] = False
    with pytest.raises(AssertionError, match="expected"): execute(case, tmp_path)


def test_unknown_input_and_assertion_paths_cannot_pass(tmp_path):
    case = deepcopy(next(c for c in load(CASES) if c["case"] == "R5"))
    case["given"]["ignored"] = True
    with pytest.raises(ValueError): execute(case, tmp_path)
    case["given"].pop("ignored")
    case["checks"] = [{"path": ["not-a-checkpoint"], "equals": None}]
    with pytest.raises(AssertionError, match="unknown checkpoint"): execute(case, tmp_path)


def test_t8_cannot_drop_a_required_substitution(tmp_path):
    document = canonical.loads(CASES.read_text(encoding="utf-8"))
    case = next(c for c in document["cases"] if c["case"] == "T8")
    case["given"]["variants"].pop()
    file = tmp_path / "incomplete.json"; file.write_bytes(canonical.canonical_bytes(document))
    with pytest.raises(ValueError, match="every independent"): load(file)


@pytest.mark.parametrize("status,freshness,value", [("UNKNOWN", "FRESH", None), ("AVAILABLE", "STALE", "RAW_RUNS"), ("AVAILABLE", "FRESH", "FUTURE")])
def test_independence_provenance_is_consumed_fail_closed(status, freshness, value):
    from helpers import add, obs_set, integrity_inputs, passing_revisions
    from devostasis.vitals.integrity import evaluate
    obs = obs_set(); integrity_inputs(obs, True, passing_revisions(4))
    add(obs, "ci.sample_semantics", value, "enum", status=status, freshness=freshness)
    result = evaluate(obs)
    assert result.evaluation_status == "UNKNOWN" and result.band is None
    assert "CI_SAMPLE_INDEPENDENCE_UNKNOWN" in result.diagnostics
