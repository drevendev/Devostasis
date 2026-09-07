"""Band ordering claims that no pair of bands can express (PV-BAND-ORDER-001).

ORDER-01..15 live as executable vectors in ``tests/vectors/band-order.json``.
What is left here is structural: an order exists only inside one Vital, only
over bands that Vital can actually emit, only inside a comparable bundle, and
never because a gauge moved.

Plus one guard on the corpus itself. 0.1.8 shipped ORDER-01..15 derived from
the contract's *rules* rather than transcribed from its ``Required conformance
cases`` section, which quietly moved every identifier onto a different claim
(PV-SPEC-001). The existing drift guards could not see it: both directions
resolved, because a citation still found a vector and every vector was still
cited. What no guard held was what an identifier *means*, so this file names
that, and reassigning one is now a red build.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from devostasis import order, vectors
from devostasis.contracts import BAND_ORDER_CONTRACT, BAND_ORDER_VERSION, CORE_VITAL_IDS
from devostasis.delta import compare
from devostasis.gauges import gauge_values
from devostasis.vitals import BANDS, build_snapshot
from helpers import full_inputs, obs_set

VECTOR_DIR = Path(__file__).resolve().parent.parent / "vectors"

# Transcribed from the `Required conformance cases` section of PV-BAND-ORDER-001:
# the accepted name of each case, and band pairs it names that the vector must
# actually execute. Nothing here is derived from the corpus; that is the point.
ACCEPTED_CASES = {
    "ORDER-01": ("CLUTTER_TRANSITIVE_IMPROVEMENT", [("HEAVY", "LIGHT"), ("LIGHT", "HEAVY")]),
    "ORDER-02": ("FLOW_LIVE_QUEUE_ORDER", [("GRIDLOCKED", "CONGESTED"), ("CONGESTED", "MOVING"), ("MOVING", "CONGESTED"), ("CONGESTED", "GRIDLOCKED")]),
    "ORDER-03": ("FLOW_NO_QUEUE_INCOMPARABLE", [("NO_QUEUE", "MOVING"), ("MOVING", "NO_QUEUE"), ("NO_QUEUE", "GRIDLOCKED"), ("GRIDLOCKED", "NO_QUEUE")]),
    "ORDER-04": ("INTEGRITY_ESTABLISHED_CHAIN", [("FAILING", "FLAKY"), ("FLAKY", "CLEAN"), ("CLEAN", "FLAKY"), ("FLAKY", "FAILING")]),
    "ORDER-05": ("INTEGRITY_SPARSE_CHAIN", [("SPARSE_MIXED", "SPARSE"), ("SPARSE", "SPARSE_MIXED")]),
    "ORDER-06": ("INTEGRITY_CROSS_FAMILY", [("SPARSE", "CLEAN"), ("SPARSE_MIXED", "FAILING"), ("NO_RECENT_RUNS", "CLEAN")]),
    "ORDER-07": ("PULSE_NEUTRALITY", [("DORMANT", "SURGING"), ("SURGING", "DORMANT"), ("QUIET", "STEADY")]),
    "ORDER-08": ("HORIZON_NEUTRALITY", [("EXTENDED", "VISIBLE"), ("VISIBLE", "EXTENDED"), ("DECLARED", "UNDECLARED"), ("UNDECLARED", "DECLARED")]),
    "ORDER-09": ("DIRECTION_NEUTRALITY", [("SCATTERED", "FULLY_LINKED"), ("FULLY_LINKED", "SCATTERED")]),
    "ORDER-10": ("DEBT_NEUTRALITY", [("PRESENT", "CLEAR"), ("CLEAR", "PRESENT")]),
    "ORDER-11": ("DEGRADED_NEVER_ORDERED", [("HEAVY", "CLEAN")]),
    "ORDER-12": ("UNKNOWN_OBSERVABILITY_PRECEDENCE", [(None, "CLEAN"), ("MOVING", None)]),
    "ORDER-13": ("RULE_VERSION_BOUNDARY_PRECEDENCE", [("HEAVY", "CLEAN"), ("CLEAN", "FAILING")]),
    "ORDER-14": ("GAUGE_INVARIANCE", [("LIGHT", "LIGHT")]),
    "ORDER-15": ("CROSS_VITAL_PROHIBITION", [("HEAVY", "CLEAN"), ("MOVING", "GRIDLOCKED")]),
}

ORDERED_TRANSITIONS = {"IMPROVED", "WORSENED"}


def _snapshot(observed_at: str = "2026-09-05T12:00:00Z"):
    return build_snapshot(full_inputs(obs_set(observed_at)))


def _with_band(snapshot, vital_id, band, **fields):
    copy = {key: value for key, value in snapshot.items()}
    copy["vitals"] = [dict(row, **({"band": band} | fields)) if row["vital_id"] == vital_id else dict(row) for row in snapshot["vitals"]]
    return copy


def _row(previous, current, vital_id, status="COMPARABLE"):
    document = compare(current, previous, status, "previous-id")
    return {row["vital_id"]: row for row in document["vitals"]}[vital_id]


def test_every_ordered_band_is_a_band_its_vital_can_emit():
    """An order over a band no rule produces would be an order over nothing."""
    for vital_id, families in order.ORDER_FAMILIES.items():
        assert vital_id in CORE_VITAL_IDS
        for family in families:
            assert len(set(family)) == len(family)
            unknown = sorted(set(family) - set(BANDS[vital_id]))
            assert not unknown, f"{vital_id} orders bands it never emits: {unknown}"
        listed = [band for family in families for band in family]
        assert len(set(listed)) == len(listed), f"{vital_id} lists a band in two families"


def test_the_bands_left_unordered_are_exactly_the_descriptive_and_evidence_states():
    """Every band outside a family is one the contract deliberately leaves incomparable."""
    unordered = {vital: sorted(set(BANDS[vital]) - set(order.ordered_bands(vital))) for vital in order.ORDER_FAMILIES}
    assert unordered == {
        "clutter": [],
        "flow": ["NO_QUEUE"],
        "integrity": ["NO_DECISIVE_RUNS", "NO_RECENT_RUNS", "UNINSTRUMENTED"],
    }


def test_four_vitals_declare_no_order_at_all():
    assert sorted(vital for vital in CORE_VITAL_IDS if not order.declares_order(vital)) == ["debt", "direction", "horizon", "pulse"]


def test_no_order_is_declared_across_vitals():
    """A band belongs to the order of its own Vital and to no other."""
    for vital_id in CORE_VITAL_IDS:
        for other in CORE_VITAL_IDS:
            if other == vital_id:
                continue
            for band in order.ordered_bands(vital_id):
                if band in BANDS[other]:
                    continue
                assert order.position(other, band) is None


def test_the_delta_declares_the_ordering_contract_it_applied_and_no_aggregate():
    document = compare(_snapshot(), _snapshot("2026-09-06T12:00:00Z"), "COMPARABLE", "previous-id")
    assert document["band_order_contract"] == BAND_ORDER_CONTRACT
    assert document["band_order_version"] == BAND_ORDER_VERSION
    assert "aggregate" not in document and "cross_vital_order" not in document


def test_a_bundle_that_is_not_comparable_never_reports_a_direction():
    previous = _with_band(_snapshot(), "clutter", "HEAVY")
    current = _with_band(_snapshot("2026-09-06T12:00:00Z"), "clutter", "CLEAN")
    for status in ("BASELINE", "HISTORY_GAP", "INCOMPARABLE"):
        row = _row(previous, current, "clutter", status)
        assert row["transition_class"] not in ORDERED_TRANSITIONS


def test_a_gauge_that_moved_inside_one_band_is_not_a_direction():
    """Gauges are a presentation normalization; movement inside a band is UNCHANGED."""
    previous = _snapshot()
    current = _snapshot("2026-09-06T12:00:00Z")
    for row in current["vitals"]:
        if row["vital_id"] == "clutter":
            row["derived"] = dict(row["derived"], stale_work_count=row["derived"]["stale_work_count"] + 1)
    assert gauge_values(current)["clutter"] != gauge_values(previous)["clutter"]
    assert _row(previous, current, "clutter")["transition_class"] == "UNCHANGED"


def test_an_unequal_band_of_an_unordered_vital_stays_changed_in_a_real_snapshot():
    previous = _with_band(_snapshot(), "pulse", "QUIET")
    current = _with_band(_snapshot("2026-09-06T12:00:00Z"), "pulse", "SURGING")
    row = _row(previous, current, "pulse")
    assert row["transition_class"] == "CHANGED"
    assert "BAND_ORDER_NOT_DECLARED:pulse" in row["reason_codes"]


# --------------------------------------------------------------------------- provenance of the case ids (PV-SPEC-001)


def _order_vectors():
    return {vector.case: vector for vector in vectors.load([VECTOR_DIR]) if vector.case.startswith("ORDER-")}


def _pairs(vector):
    """Every (previous band, current band) the case actually executes, per Vital."""
    given = vector.given
    comparisons = given.get("comparisons") or [given]
    found = set()
    for comparison in comparisons:
        previous = {row["vital_id"]: row.get("band") for row in comparison["previous"]["vitals"]}
        current = {row["vital_id"]: row.get("band") for row in comparison["current"]["vitals"]}
        for vital_id, before in previous.items():
            found.add((before, current.get(vital_id)))
    return found


def test_the_corpus_carries_exactly_the_accepted_case_ids():
    """No accepted case may go missing, and no local case may borrow the namespace."""
    assert set(_order_vectors()) == set(ACCEPTED_CASES)


@pytest.mark.parametrize("case_id", sorted(ACCEPTED_CASES))
def test_each_case_id_still_carries_the_meaning_the_contract_gave_it(case_id):
    """A research identifier is never reused: ORDER-nn must be the accepted ORDER-nn.

    Both existing drift guards pass while every id means something else, because
    they only check that citations and vectors refer to each other. This checks
    the one thing that actually moved in 0.1.8.
    """
    name, required = ACCEPTED_CASES[case_id]
    vector = _order_vectors()[case_id]
    assert vector.title.startswith(name), f"{case_id} is titled {vector.title!r}, which does not carry the accepted case {name}"
    assert vector.source_unit == "PV-BAND-ORDER-001"
    missing = sorted(str(pair) for pair in required if pair not in _pairs(vector))
    assert not missing, f"{case_id} ({name}) does not execute the band pairs the accepted case names: {missing}"


def test_the_conformance_table_names_the_accepted_case_of_every_id():
    """The published table is the claim; it must name the same case the vector executes."""
    text = (Path(__file__).resolve().parent.parent.parent / "docs" / "spec" / "conformance.md").read_text(encoding="utf-8")
    for case_id, (name, _) in ACCEPTED_CASES.items():
        row = next((line for line in text.splitlines() if line.startswith(f"| {case_id} |")), None)
        assert row, f"conformance.md has no row for {case_id}"
        assert name in row, f"conformance.md describes {case_id} without naming the accepted case {name}: {row}"


def test_cases_of_our_own_stay_out_of_the_research_namespace():
    """A DEV- id cannot be mistaken for evidence about an accepted case."""
    local = [vector for vector in vectors.load([VECTOR_DIR]) if vector.case.startswith("DEV-")]
    assert local, "the local band ordering cases are gone"
    for vector in local:
        assert vector.source_unit is None, f"{vector.case} claims research unit {vector.source_unit}"


def test_a_case_that_states_several_pairs_fails_when_any_one_of_them_fails():
    """A multi-pair case must not report PASS on the strength of its first comparison."""
    document = json.loads((VECTOR_DIR / "band-order.json").read_text(encoding="utf-8"))
    case = next(item for item in document["vectors"] if item["case"] == "ORDER-01")
    broken = json.loads(json.dumps(case))
    broken["case"] = "ORDER-BROKEN"
    second = broken["given"]["comparisons"][1]["expect"]["vitals"]
    row = second[next(iter(second))]
    truth = row["transition_class"]
    row["transition_class"] = "UNCHANGED" if truth != "UNCHANGED" else "CHANGED"
    parsed = vectors.parse_document({"schema": document["schema"], "vectors": [broken]})
    result = vectors.run(parsed[0])
    assert not result.ok, "a case whose second comparison is wrong reported PASS"
    assert any(truth in failure for failure in result.failures)
