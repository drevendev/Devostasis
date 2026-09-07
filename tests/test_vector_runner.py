"""The vector runner itself: it must fail closed, and a wrong expectation must fail.

A test suite that only ever runs passing vectors proves nothing about the
runner. These cases prove the two properties a conformance runner has to have:
a vector that cannot be executed is an error rather than a silent pass, and a
vector whose expectation is wrong fails.
"""

from __future__ import annotations

import json

import pytest

from devostasis import vectors
from devostasis.cli import main

CLUTTER_OBSERVATIONS = [
    {"observation_id": "forge.issues.open_count", "value": 4},
    {"observation_id": "forge.issues.stale_open_count_30d", "value": 1},
    {"observation_id": "forge.change_requests.open_count", "value": 2},
    {"observation_id": "forge.change_requests.stale_open_count_14d", "value": 0},
    {"observation_id": "git.nondefault_branches.stale_count_30d", "value": 0},
]


def document(**overrides):
    vector = {
        "case": "T-VECTOR-01",
        "title": "an exactly observed inventory with one stale item is LIGHT",
        "kind": "vital",
        "given": {"vital": "clutter", "observations": CLUTTER_OBSERVATIONS},
        "expect": {"band": "LIGHT", "evaluation_status": "AVAILABLE"},
    }
    vector.update(overrides)
    return {"schema": "devostasis.vectors.v1", "vectors": [vector]}


def parse(**overrides):
    return vectors.parse_document(document(**overrides))[0]


def test_a_correct_vector_passes():
    assert vectors.run(parse()).ok


def test_a_wrong_expectation_fails_and_says_what_it_expected():
    result = vectors.run(parse(expect={"band": "CLEAN", "evaluation_status": "AVAILABLE"}))
    assert not result.ok
    assert "band: expected 'CLEAN', got 'LIGHT'" in result.failures[0]


def test_a_derived_metric_that_the_vital_never_emits_fails():
    result = vectors.run(parse(expect={"band": "LIGHT", "evaluation_status": "AVAILABLE", "derived": {"invented_metric": 1}}))
    assert not result.ok and "derived.invented_metric" in result.failures[0]


def test_an_expected_diagnostic_that_is_absent_fails():
    result = vectors.run(parse(expect={"band": "LIGHT", "evaluation_status": "AVAILABLE", "diagnostics": ["COMPONENT_UNAVAILABLE"]}))
    assert not result.ok and "diagnostics" in result.failures[0]


def test_a_forbidden_diagnostic_that_is_emitted_fails():
    given = {
        "vital": "clutter",
        "observations": [
            {"observation_id": "forge.issues.open_count", "status": "UNAVAILABLE", "reason_code": "ISSUES_DISABLED"},
            {"observation_id": "forge.issues.stale_open_count_30d", "status": "UNAVAILABLE", "reason_code": "ISSUES_DISABLED"},
            {"observation_id": "forge.change_requests.open_count", "value": 2},
            {"observation_id": "forge.change_requests.stale_open_count_14d", "value": 0},
            {"observation_id": "git.nondefault_branches.stale_count_30d", "value": 0},
        ],
    }
    expect = {"band": "CLEAN", "evaluation_status": "DEGRADED", "diagnostics_absent": ["COMPONENT_UNAVAILABLE"]}
    result = vectors.run(parse(given=given, expect=expect))
    assert not result.ok and "must not be emitted" in result.failures[0]


def test_an_envelope_that_violates_the_observation_contract_is_a_failure_not_a_pass():
    """AVAILABLE without a value is invalid evidence; the vector reports it instead of crashing."""
    given = {"vital": "clutter", "observations": [{"observation_id": "forge.issues.open_count", "status": "AVAILABLE"}]}
    result = vectors.run(parse(given=given))
    assert not result.ok and "ObservationError" in result.failures[0]


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"kind": "bundle"}, "unknown kind"),
        ({"unexpected": 1}, "unknown keys"),
        ({"expect": {"band": "LIGHT", "evaluation_status": "AVAILABLE", "invented": 1}}, "unknown keys"),
        ({"given": {"vital": "gravity", "observations": CLUTTER_OBSERVATIONS}}, "unknown vital"),
        ({"given": {"vital": "clutter", "observations": []}}, "non-empty list"),
        ({"expect": {"band": "LIGHT"}}, "missing keys"),
    ],
)
def test_a_vector_that_cannot_run_is_rejected_at_load_time(overrides, message):
    with pytest.raises(vectors.VectorError) as error:
        parse(**overrides)
    assert message in str(error.value)


def test_a_file_that_is_not_a_vector_document_is_rejected():
    for bad in ({"schema": "devostasis.vectors.v99", "vectors": []}, {"schema": "devostasis.vectors.v1", "vectors": []}, {"vectors": []}):
        with pytest.raises(vectors.VectorError):
            vectors.parse_document(bad)


def test_two_files_may_not_claim_the_same_case_id(tmp_path):
    for name in ("a.json", "b.json"):
        (tmp_path / name).write_text(json.dumps(document()), encoding="utf-8")
    with pytest.raises(vectors.VectorError) as error:
        vectors.load([tmp_path])
    assert "duplicate case T-VECTOR-01" in str(error.value)


def test_a_missing_path_is_an_error_not_an_empty_run(tmp_path):
    with pytest.raises(vectors.VectorError):
        vectors.load([tmp_path / "absent"])


def test_the_delta_kind_defaults_both_sides_to_the_same_rule_so_no_boundary_is_invented():
    vector = parse(
        kind="delta",
        given={"previous": {"vitals": [{"vital_id": "flow", "band": "GRIDLOCKED"}]}, "current": {"vitals": [{"vital_id": "flow", "band": "MOVING"}]}},
        expect={"vitals": {"flow": {"transition_class": "IMPROVED"}}},
    )
    assert vectors.run(vector).ok


def test_the_cli_runs_a_corpus_and_reports_failures(tmp_path, capsys):
    (tmp_path / "good.json").write_text(json.dumps(document()), encoding="utf-8")
    assert main(["vectors", "--path", str(tmp_path)]) == 0
    assert "PASS T-VECTOR-01" in capsys.readouterr().out

    (tmp_path / "bad.json").write_text(
        json.dumps(document(case="T-VECTOR-02", expect={"band": "HEAVY", "evaluation_status": "AVAILABLE"})), encoding="utf-8"
    )
    assert main(["vectors", "--path", str(tmp_path)]) == 1
    assert "FAIL T-VECTOR-02" in capsys.readouterr().out

    assert main(["vectors", "--path", str(tmp_path), "--case", "T-VECTOR-01"]) == 0
    assert main(["vectors", "--path", str(tmp_path), "--case", "T-NOT-A-CASE"]) == 2


def test_the_published_vector_schema_and_the_runner_agree_on_the_shape():
    from devostasis import canonical

    schema = canonical.load_file("schemas/conformance-vector.schema.json")
    entry = schema["properties"]["vectors"]["items"]
    assert set(entry["required"]) == vectors.REQUIRED_VECTOR_KEYS
    assert set(entry["properties"]) == vectors.VECTOR_KEYS
    assert set(entry["properties"]["kind"]["enum"]) == set(vectors.KINDS)
    vital, delta = (branch["then"]["properties"] for branch in entry["allOf"])
    assert set(vital["given"]["properties"]) == vectors.VITAL_GIVEN_KEYS
    assert set(vital["expect"]["properties"]) == vectors.VITAL_EXPECT_KEYS
    assert set(delta["given"]["properties"]) == vectors.DELTA_GIVEN_KEYS
    delta_expect = schema["$defs"]["delta_expect"]
    assert delta["expect"] == {"$ref": "#/$defs/delta_expect"}, "the two expect shapes must be one definition, not two copies"
    assert set(delta_expect["properties"]) == vectors.DELTA_EXPECT_KEYS
    comparison = delta["given"]["properties"]["comparisons"]["items"]
    assert set(comparison["properties"]) == vectors.DELTA_COMPARISON_KEYS
    assert comparison["properties"]["expect"] == {"$ref": "#/$defs/delta_expect"}
    row = schema["$defs"]["side"]["properties"]["vitals"]["items"]
    assert set(row["properties"]) == vectors.DELTA_ROW_KEYS
    expect_row = delta_expect["properties"]["vitals"]["additionalProperties"]
    assert set(expect_row["properties"]) == vectors.DELTA_ROW_EXPECT_KEYS
    for holder in (delta["given"]["properties"], comparison["properties"], delta_expect["properties"]):
        assert set(holder["comparison_status"]["enum"]) == set(vectors.COMPARISON_STATUSES)


def test_the_schema_publishes_the_partial_envelope_the_runner_actually_accepts():
    """A vector states evidence, not a whole envelope; the published schema must say so.

    The runner fills status, provider, collected_at, source_ref and adapter_version
    before handing the envelope to the observation contract, so requiring the full
    RAW-OBS-V0 envelope here would declare every vector in this repository invalid
    against the schema that ships beside it.
    """
    from devostasis import canonical

    schema = canonical.load_file("schemas/conformance-vector.schema.json")
    observation = canonical.load_file("schemas/observation.schema.json")
    envelope = schema["$defs"]["envelope"]
    assert envelope["required"] == ["observation_id"]
    assert set(envelope["properties"]) == set(observation["properties"])
    vital = schema["properties"]["vectors"]["items"]["allOf"][0]["then"]["properties"]
    assert vital["given"]["properties"]["observations"]["items"] == {"$ref": "#/$defs/envelope"}


def test_a_comparison_status_the_engine_does_not_know_is_rejected():
    """An unrecognised status would silently run a different comparison and still pass."""
    given = {"previous": {"vitals": [{"vital_id": "flow", "band": "MOVING"}]}, "current": {"vitals": [{"vital_id": "flow", "band": "MOVING"}]}}
    expect = {"vitals": {"flow": {"transition_class": "UNCHANGED"}}}
    with pytest.raises(vectors.VectorError) as error:
        parse(kind="delta", given=dict(given, comparison_status="COMPARABEL"), expect=expect)
    assert "unknown comparison_status" in str(error.value)
    with pytest.raises(vectors.VectorError):
        parse(kind="delta", given=given, expect=dict(expect, comparison_status="COMPARABEL"))
