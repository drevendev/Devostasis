"""Presentation-only gauges (devostasis.gauge.v1): ranges, monotonicity, unknown handling, rendering."""

from devostasis import gauges
from devostasis.render import render_status_card
from devostasis.vitals import build_snapshot
from helpers import full_inputs, obs_set


def _vital(vital_id, band, status="AVAILABLE", semantics="EXACT", **derived):
    return {"vital_id": vital_id, "band": band, "evaluation_status": status, "band_semantics": semantics, "derived": derived}


def test_every_band_lands_inside_its_declared_range():
    samples = {
        ("pulse", "DORMANT"): {"activity_events_28d": 0, "commit_active_days_28d": 0},
        ("pulse", "QUIET"): {"activity_events_28d": 2, "commit_active_days_28d": 1},
        ("pulse", "STEADY"): {"activity_events_28d": 20, "commit_active_days_28d": 6},
        ("pulse", "SURGING"): {"activity_events_28d": 120, "commit_active_days_28d": 20},
        ("flow", "NO_QUEUE"): {"open_count": 0},
        ("flow", "MOVING"): {"open_count": 3, "oldest_open_age_days": 4},
        ("flow", "CONGESTED"): {"open_count": 12, "oldest_open_age_days": 20},
        ("flow", "GRIDLOCKED"): {"open_count": 5, "oldest_open_age_days": 45, "median_time_to_merge_hours_28d": 500},
        ("clutter", "CLEAN"): {"stale_work_count": 0, "stale_branch_count": 0},
        ("clutter", "LIGHT"): {"stale_work_count": 2, "stale_branch_count": 1},
        ("clutter", "CLUTTERED"): {"stale_work_count": 9, "stale_branch_count": 3, "stale_work_ratio": {"num": 9, "den": 30}},
        ("clutter", "HEAVY"): {"stale_work_count": 40, "stale_branch_count": 25, "stale_work_ratio": {"num": 40, "den": 60}},
        ("integrity", "FAILING"): {"decisive_count_14d": 10, "failed_count_14d": 6},
        ("integrity", "SPARSE_MIXED"): {"decisive_count_14d": 2, "failed_count_14d": 1},
        ("integrity", "FLAKY"): {"decisive_count_14d": 20, "failed_count_14d": 2},
        ("integrity", "SPARSE"): {"decisive_count_14d": 2, "failed_count_14d": 0},
        ("integrity", "CLEAN"): {"decisive_count_14d": 12, "failed_count_14d": 0},
        ("horizon", "UNDECLARED"): {"capability": "SUPPORTED_UNUSED", "open_count": 0},
        ("horizon", "DECLARED"): {"capability": "SUPPORTED", "open_count": 2, "open_with_future_boundary_count": 0, "open_beyond_28d_count": 0},
        ("horizon", "VISIBLE"): {"capability": "SUPPORTED", "open_count": 2, "open_with_future_boundary_count": 1, "open_beyond_28d_count": 0},
        ("horizon", "EXTENDED"): {"capability": "SUPPORTED", "open_count": 3, "open_with_future_boundary_count": 2, "open_beyond_28d_count": 1},
        ("direction", "SCATTERED"): {"capability": "SUPPORTED", "active_change_count_28d": 10, "linked_active_change_count_28d": 2},
        ("direction", "MIXED"): {"capability": "SUPPORTED", "active_change_count_28d": 10, "linked_active_change_count_28d": 7},
        ("direction", "FULLY_LINKED"): {"capability": "SUPPORTED", "active_change_count_28d": 10, "linked_active_change_count_28d": 10},
        ("debt", "CLEAR"): {"capability": "CONFIGURED", "open_count": 0},
        ("debt", "PRESENT"): {"capability": "CONFIGURED", "open_count": 7, "open_stale_count_30d": 2},
    }
    for (vital_id, band), derived in samples.items():
        gauge = gauges.gauge_for(_vital(vital_id, band, **derived))
        low, high = gauges.BAND_RANGES[vital_id][band]
        assert gauge["value"] is not None and low <= gauge["value"] <= high, (vital_id, band, gauge["value"])
        assert gauge["canonical_semantics"] == "snapshot.json" and gauge["qualifier"] == "exact"


def test_unknown_and_not_applicable_states_have_no_value():
    assert gauges.gauge_for({"vital_id": "pulse", "band": None, "evaluation_status": "UNKNOWN", "derived": {}})["value"] is None
    assert gauges.gauge_for(_vital("integrity", "UNINSTRUMENTED"))["value"] is None
    assert gauges.gauge_for(_vital("integrity", "NO_RECENT_RUNS"))["value"] is None
    assert gauges.gauge_for(_vital("debt", "UNINSTRUMENTED", capability="UNCONFIGURED"))["value"] is None
    assert gauges.gauge_for(_vital("direction", "NO_ACTIVE_CHANGE", active_change_count_28d=0))["value"] is None
    assert gauges.gauge_for(_vital("horizon", "UNDECLARED", capability="UNSUPPORTED"))["value"] is None
    assert gauges.gauge_for(_vital("horizon", "UNDECLARED", capability="SUPPORTED_UNUSED"))["value"] == 0


def test_gauges_are_monotone_inside_a_band():
    low = gauges.gauge_for(_vital("debt", "PRESENT", capability="CONFIGURED", open_count=1, open_stale_count_30d=0))["value"]
    mid = gauges.gauge_for(_vital("debt", "PRESENT", capability="CONFIGURED", open_count=20, open_stale_count_30d=5))["value"]
    high = gauges.gauge_for(_vital("debt", "PRESENT", capability="CONFIGURED", open_count=80, open_stale_count_30d=40))["value"]
    assert low < mid < high == 100
    share = [gauges.gauge_for(_vital("direction", "MIXED", capability="SUPPORTED", active_change_count_28d=10, linked_active_change_count_28d=n))["value"] for n in (5, 7, 9)]
    assert share == [50, 70, 90]
    quiet = [gauges.gauge_for(_vital("pulse", "QUIET", activity_events_28d=n, commit_active_days_28d=1))["value"] for n in (1, 2, 3, 4, 9)]
    assert quiet == sorted(quiet) and quiet[-1] == 25


def test_degraded_results_carry_a_bound_qualifier():
    gauge = gauges.gauge_for(_vital("pulse", "SURGING", status="DEGRADED", semantics="CONSERVATIVE_LOWER_BOUND", activity_events_28d=300, commit_active_days_28d=20))
    assert gauge["qualifier"] == "at_least" and gauges.value_text(gauge).startswith("≥")


def test_bars_and_status_card_render_deterministically():
    assert gauges.bar(0) == "░░░░░░░░░░" and gauges.bar(100) == "██████████" and gauges.bar(None) == "░░░░░░░░░░"
    assert gauges.bar(46) == "█████░░░░░" and gauges.bar(45) == "█████░░░░░" and gauges.bar(44) == "████░░░░░░"
    snapshot = build_snapshot(full_inputs(obs_set()))
    card = render_status_card(snapshot)
    assert card == render_status_card(snapshot)
    assert card.count("\n") == 6 and "Horizon" in card and "EXTENDED" in card
    values = gauges.gauge_values(snapshot)
    assert set(values) == {"horizon", "clutter", "direction", "flow", "integrity", "debt", "pulse"}
    assert values["direction"] == 80 and values["debt"] is not None
