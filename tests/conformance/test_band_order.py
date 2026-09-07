"""Band ordering claims that no pair of bands can express (PV-BAND-ORDER-001).

ORDER-01..15 live as executable vectors in ``tests/vectors/band-order.json``.
What is left here is structural: an order exists only inside one Vital, only
over bands that Vital can actually emit, only inside a comparable bundle, and
never because a gauge moved.
"""

from __future__ import annotations

from devostasis import order
from devostasis.contracts import BAND_ORDER_CONTRACT, BAND_ORDER_VERSION, CORE_VITAL_IDS
from devostasis.delta import compare
from devostasis.gauges import gauge_values
from devostasis.vitals import BANDS, build_snapshot
from helpers import full_inputs, obs_set

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
