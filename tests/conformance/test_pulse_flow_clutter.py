"""V0 band tables for Pulse, Flow and Clutter plus the V0.1/V0.2 degraded-data repairs."""

from devostasis.observations import PARTIAL, UNAVAILABLE
from devostasis.vitals import clutter, flow, pulse
from helpers import add, clutter_inputs, flow_inputs, obs_set, pulse_inputs


def test_pulse_band_table():
    assert pulse.classify(15, 0, 0) == "SURGING"
    assert pulse.classify(2, 40, 2) == "SURGING"
    assert pulse.classify(2, 40, 1) == "STEADY" if False else pulse.classify(3, 40, 1) == "STEADY"
    assert pulse.classify(3, 5, 1) == "STEADY"
    assert pulse.classify(2, 5, 1) == "QUIET"
    assert pulse.classify(0, 0, 0) == "DORMANT"


def test_pulse_exact_when_every_channel_is_observed():
    obs = obs_set()
    pulse_inputs(obs, commits=10, active_days=4, cr_updates=3, issue_updates=0)
    result = pulse.evaluate(obs)
    assert (result.band, result.evaluation_status, result.band_semantics) == ("STEADY", "AVAILABLE", "EXACT")
    assert result.derived["activity_events_28d"] == 13 and result.derived["channel_count"] == 2


def test_pulse_missing_required_input_is_unknown():
    obs = obs_set()
    add(obs, "git.default_branch.commits.count_28d", 10)
    result = pulse.evaluate(obs)
    assert result.band is None and result.evaluation_status == "UNKNOWN"


def test_r3_zero_activity_with_unavailable_channel_is_degraded_dormant_lower_bound():
    obs = obs_set()
    pulse_inputs(obs, commits=0, active_days=0, cr_updates=0, issue_updates=None)
    add(obs, "forge.issues.updated_count_28d", status=UNAVAILABLE, reason_code="ISSUES_DISABLED")
    result = pulse.evaluate(obs)
    assert result.band == "DORMANT" and result.evaluation_status == "DEGRADED"
    assert result.band_semantics == "CONSERVATIVE_LOWER_BOUND"
    assert result.possible_bands == ["DORMANT", "QUIET", "STEADY", "SURGING"]


def test_v1_10_unavailable_channel_never_becomes_zero_but_lower_bound_still_classifies():
    obs = obs_set()
    pulse_inputs(obs, commits=30, active_days=16, cr_updates=None, issue_updates=2)
    add(obs, "forge.change_requests.updated_count_28d", status=PARTIAL, value=5, reason_code="PAGINATION_CAPPED")
    result = pulse.evaluate(obs)
    assert result.band == "SURGING" and result.evaluation_status == "DEGRADED"
    assert result.derived["activity_events_28d"] == 32
    assert any(code.startswith("UNOBSERVED_CHANNEL:forge.change_requests.updated_count_28d:PARTIAL") for code in result.diagnostics)


def test_capped_commit_enumeration_is_a_lower_bound_not_unknown():
    obs = obs_set()
    add(obs, "git.default_branch.commits.count_28d", 3000, status=PARTIAL, reason_code="PAGINATION_CAPPED")
    add(obs, "git.default_branch.commit_active_days_28d", 14, status=PARTIAL, reason_code="PAGINATION_CAPPED")
    add(obs, "forge.change_requests.updated_count_28d", 500)
    add(obs, "forge.issues.updated_count_28d", 100)
    result = pulse.evaluate(obs)
    assert result.band == "SURGING" and result.evaluation_status == "DEGRADED"
    assert result.band_semantics == "CONSERVATIVE_LOWER_BOUND" and result.possible_bands == ["SURGING"]
    assert any(code.startswith("REQUIRED_INPUT_PARTIAL:git.default_branch.commits.count_28d") for code in result.diagnostics)


def test_partial_required_input_without_value_stays_unknown():
    obs = obs_set()
    add(obs, "git.default_branch.commits.count_28d", status=PARTIAL, reason_code="PAGINATION_CAPPED")
    add(obs, "git.default_branch.commit_active_days_28d", 2)
    assert pulse.evaluate(obs).evaluation_status == "UNKNOWN"


def test_flow_no_queue_and_moving():
    obs = obs_set()
    flow_inputs(obs, 0, 0)
    assert flow.evaluate(obs).band == "NO_QUEUE"
    obs = obs_set()
    flow_inputs(obs, 2, 5, oldest=3, median=10)
    assert flow.evaluate(obs).band == "MOVING"


def test_flow_congested_by_age_count_or_median():
    for kwargs in ({"open_count": 1, "merged": 3, "oldest": 14, "median": 5}, {"open_count": 10, "merged": 3, "oldest": 1, "median": 5}, {"open_count": 1, "merged": 3, "oldest": 1, "median": 169}):
        obs = obs_set()
        flow_inputs(obs, **kwargs)
        assert flow.evaluate(obs).band == "CONGESTED", kwargs


def test_flow_gridlocked_by_stale_queue_or_slow_large_queue():
    obs = obs_set()
    flow_inputs(obs, 3, 0, oldest=30)
    assert flow.evaluate(obs).band == "GRIDLOCKED"
    obs = obs_set()
    flow_inputs(obs, 10, 2, oldest=2, median=337)
    assert flow.evaluate(obs).band == "GRIDLOCKED"


def test_flow_missing_conditional_input_is_unknown_not_guessed():
    obs = obs_set()
    flow_inputs(obs, 2, 0)
    result = flow.evaluate(obs)
    assert result.band is None and result.evaluation_status == "UNKNOWN"


def test_flow_literal_rule_with_empty_queue_and_slow_median_is_flagged():
    obs = obs_set()
    flow_inputs(obs, 0, 4, median=200)
    result = flow.evaluate(obs)
    assert result.band == "CONGESTED" and "FLOW_MEDIAN_WITH_EMPTY_QUEUE" in result.diagnostics


def test_clutter_band_table():
    assert clutter.classify(0, 0, 0) == "CLEAN"
    assert clutter.classify(1, 10, 0) == "LIGHT"
    assert clutter.classify(0, 0, 1) == "LIGHT"
    assert clutter.classify(5, 100, 0) == "CLUTTERED"
    assert clutter.classify(1, 4, 0) == "CLUTTERED"
    assert clutter.classify(0, 0, 6) == "CLUTTERED"
    assert clutter.classify(25, 100, 0) == "HEAVY"
    assert clutter.classify(2, 4, 0) == "HEAVY"
    assert clutter.classify(0, 0, 20) == "HEAVY"
    assert clutter.classify(1, 3, 0) == "LIGHT"


def test_clutter_exact_evaluation():
    obs = obs_set()
    clutter_inputs(obs, issues_open=10, issues_stale=3, cr_open=4, cr_stale=2, stale_branches=2)
    result = clutter.evaluate(obs)
    assert result.band == "CLUTTERED" and result.evaluation_status == "AVAILABLE"
    assert result.derived["stale_work_ratio"] == {"num": 5, "den": 14}


def test_clutter_issues_disabled_is_degraded_lower_bound():
    obs = obs_set()
    add(obs, "forge.issues.open_count", status=UNAVAILABLE, reason_code="ISSUES_DISABLED")
    add(obs, "forge.issues.stale_open_count_30d", status=UNAVAILABLE, reason_code="ISSUES_DISABLED")
    add(obs, "forge.change_requests.open_count", 1)
    add(obs, "forge.change_requests.stale_open_count_14d", 0)
    add(obs, "git.nondefault_branches.stale_count_30d", 0)
    result = clutter.evaluate(obs)
    assert result.band == "CLEAN" and result.evaluation_status == "DEGRADED"
    assert result.possible_bands == ["CLEAN", "LIGHT", "CLUTTERED", "HEAVY"]


def test_v1_11_branch_enumeration_unavailable_cannot_emit_exact_clean():
    obs = obs_set()
    clutter_inputs(obs, issues_open=0, issues_stale=0, cr_open=0, cr_stale=0, stale_branches=0)
    obs.replace(add(obs_set(), "git.nondefault_branches.stale_count_30d", status=UNAVAILABLE, reason_code="NOT_ENUMERABLE"))
    result = clutter.evaluate(obs)
    assert result.band == "CLEAN" and result.evaluation_status == "DEGRADED" and result.band_semantics == "CONSERVATIVE_LOWER_BOUND"


def test_clutter_partial_component_is_unknown():
    obs = obs_set()
    clutter_inputs(obs, issues_open=0, issues_stale=0, cr_open=0, cr_stale=0, stale_branches=0)
    obs.replace(add(obs_set(), "git.nondefault_branches.stale_count_30d", 3, status=PARTIAL, reason_code="PAGINATION_CAPPED"))
    result = clutter.evaluate(obs)
    assert result.band is None and result.evaluation_status == "UNKNOWN"
