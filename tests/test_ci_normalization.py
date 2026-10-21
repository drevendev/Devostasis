"""Admission attacks and compatibility at the opt-in native CI boundary."""

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import subprocess
import sys

import pytest

from devostasis import canonical
from devostasis.adapters import ci
from devostasis.delta import compare
from devostasis.vitals import integrity
from helpers import SUBJECT, obs_set, integrity_inputs, passing_revisions
from surface_bridge import load, load_suite

FIXTURE = Path(__file__).parent / "fixtures" / "ci-revisions.json"


def evidence():
    case = next(c for c in load(FIXTURE) if c["case"] == "R26")
    return deepcopy(case["given"]["variants"][0]["steps"][0]["evidence"])


def observed(value=None):
    value = evidence() if value is None else value
    return ci.observations(value, {**SUBJECT, **value["project"]})


@pytest.mark.parametrize("key,field,value", [
    (ci.NATIVE, "provider", "gitlab"),
    (ci.NATIVE, "adapter_version", "future"),
    (ci.NATIVE, "source_ref", "native-ci:forged"),
    (ci.PROVENANCE, "collected_at", "2026-09-01T00:00:00Z"),
    (ci.PROVENANCE, "value", {}),
    ("ci.revision_verdicts_14d", "value", []),
    ("ci.revision_verdicts_14d", "freshness", "STALE"),
    ("ci.configured", "value", False),
])
def test_governed_integrity_refuses_forged_native_projections(key, field, value):
    obs = observed()
    obs.replace(replace(obs.get(key), **{field: value}))
    with pytest.raises(ValueError, match="does not replay"):
        integrity.evaluate(obs)


@pytest.mark.parametrize("change", ["contract", "mapping", "provider", "extra", "native-extra", "sha", "id", "attempt", "name", "future", "parent-binding", "revision-binding", "missing-page", "duplicate-page", "continuation"])
def test_native_input_unknown_shapes_and_ambiguous_bindings_fail_closed(change):
    value = evidence()
    first = value["parents"][0]
    if change == "contract": value["contract"] += "+future"
    elif change == "mapping": value["outcome_map"] = "devostasis.ci-outcomes.gitlab.v1"
    elif change == "provider": value["project"]["provider"] = "future"
    elif change == "extra": value["ignored"] = True
    elif change == "native-extra": first["native"]["ignored"] = True
    elif change == "sha": first["native"]["head_sha"] = "foreign"
    elif change == "id": first["native"]["id"] = True
    elif change == "attempt": first["native"]["run_attempt"] = 0
    elif change == "name": first["native"]["name"] = 42
    elif change == "future": first["observed_at"] = "2099-01-01T00:00:00Z"
    elif change in ("parent-binding", "revision-binding"):
        value["revisions"].append({**value["revisions"][0], "revision": "foreign"})
        row = deepcopy(first); row["revision"] = row["native"]["head_sha"] = "foreign"
        if change == "parent-binding": value["parents"].append(row)
        else: value["revisions"].append({**value["revisions"][0], "committed_at": "2026-09-01T00:00:00Z"})
    else:
        page = {"ordinal": 1, "has_next": False, "items": value["parents"]}
        value["parents"] = {"pages": [page]}
        if change == "missing-page": page["ordinal"] = 2
        elif change == "duplicate-page": value["parents"]["pages"].append(deepcopy(page))
        else: value["parents"]["pages"].append({"ordinal": 2, "has_next": False, "items": []})
    with pytest.raises(ValueError): ci.normalize(value)


def test_subject_and_observation_anchor_are_bound_to_native_evidence():
    value = evidence()
    with pytest.raises(ValueError, match="project/subject"):
        ci.observations(value, {**SUBJECT, "immutable_project_id": "foreign"})
    obs = observed(value); obs.observed_at = "2026-09-04T00:00:00Z"
    with pytest.raises(ValueError, match="observation-time"):
        integrity.evaluate(obs)


def test_page_transport_and_enumeration_do_not_change_canonical_observations():
    value = evidence(); before = deepcopy(value)
    alternate = deepcopy(value)
    alternate["parents"] = {"pages": [
        {"ordinal": 2, "has_next": False, "items": [value["parents"][0]]},
        {"ordinal": 1, "has_next": True, "items": list(reversed(value["parents"]))},
    ]}
    a, b = observed(value), observed(alternate)
    assert canonical.canonical_bytes(a.to_dict()) == canonical.canonical_bytes(b.to_dict())
    assert integrity.evaluate(a).to_dict() == integrity.evaluate(b).to_dict()
    assert value == before


def test_partial_inventory_and_partial_parent_cannot_prove_favorable_history():
    value = evidence()
    # One observed passing attempt would be complete without the partial flag.
    row = deepcopy(value["parents"][-1]); row["native"]["run_attempt"] = 1
    row["native"].update(status="completed", conclusion="success")
    value["parents"] = [row]
    value["parents"][0]["coverage"] = "PARTIAL"
    normalized = ci.normalize(value)
    assert normalized["records"][0]["history_state"] == "UNKNOWN_HISTORY"
    assert integrity.evaluate(observed(value)).evaluation_status == "UNKNOWN"
    row["coverage"] = "COMPLETE"
    value["parents"] = {"pages": [{"ordinal": 1, "has_next": True, "items": [row]}]}
    obs = observed(value)
    assert obs.get("ci.revision_verdicts_14d").status == "PARTIAL"
    assert integrity.evaluate(obs).evaluation_status == "UNKNOWN"


def test_unknown_native_outcome_is_unknown_and_child_current_uses_latest_snapshot():
    value = evidence()
    for row in value["parents"]: row["native"]["status"] = "future"
    assert ci.normalize(value)["records"][0]["current_verdict"] == "UNKNOWN"
    case = next(c for c in load(FIXTURE) if c["case"] == "R17")
    value = deepcopy(case["given"]["variants"][0]["steps"][0]["evidence"])
    old = value["children"][0]; value["children"] = [old]
    old["observed_at"] = "2026-09-04T00:00:00Z"
    newer = deepcopy(old); newer["observed_at"] = value["observed_at"]
    newer["native"].update(status="in_progress", conclusion=None)
    value["children"].append(newer)
    result = ci.normalize(value)
    assert result["records"][0]["current_verdict"] == "VERIFY_UNRESOLVED"
    assert result["records"][0]["history_state"] == "UNKNOWN_HISTORY"


def test_normalization_is_opt_in_and_delta_names_the_rule_boundary():
    old = obs_set(); integrity_inputs(old, True, passing_revisions(4))
    previous = integrity.evaluate(old).to_dict()
    assert previous["rule_id"] == integrity.RULE_ID
    assert "ci_normalization" not in previous["derived"]
    current = integrity.evaluate(observed()).to_dict()
    assert current["rule_id"] == integrity.RULE_ID + "+ci-normalization-001"
    delta = compare({"vitals": [current]}, {"vitals": [previous]}, "COMPARABLE", "previous")
    row = next(r for r in delta["vitals"] if r["vital_id"] == "integrity")
    assert row["transition_class"] == "INCOMPARABLE"
    assert row["reason_codes"][0].startswith("RULE_VERSION_BOUNDARY:")


def test_all_r11_r53_have_one_permanent_case_and_required_matrix_variants():
    cases = load(FIXTURE)
    assert {c["case"] for c in cases} == {f"R{i}" for i in range(11, 54)}
    assert len(cases) == 43
    assert sum(len(c["given"]["variants"]) for c in cases if c["scenario"] == "ci-revisions.v1") == 84
    # Cross-carrier duplication must never become two competing meanings.
    with pytest.raises(ValueError, match="across bridge carriers"):
        load_suite([FIXTURE, FIXTURE])


def test_bridge_wrong_assertion_still_fails_with_optimized_python(tmp_path):
    code = "from surface_bridge import execute; from pathlib import Path; execute({'case':'negative','scenario':'ci-native.v1','given':{'variants':[{'name':'x','provider':'github','mapping':'devostasis.ci-outcomes.github.v1','status':'completed','conclusion':'success'}]},'checks':[{'path':[],'equals':None}]}, Path('.'))"
    result = subprocess.run([sys.executable, "-O", "-c", code], cwd=Path(__file__).parent, capture_output=True, text=True)
    assert result.returncode != 0 and "AssertionError" in result.stderr
