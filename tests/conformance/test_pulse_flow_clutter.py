"""V0 band tables for Pulse, Flow and Clutter, the V0.1/V0.2 degraded-data repairs, and the
calibration repairs adopted by rule versions pulse.bands.v1 (PULSE-CAP-01..05) and
flow.bands.v1 (FLOW-EQ-01..06, FLOW-PREC-03..06, FLOW-PREC-09)."""

from devostasis.observations import PARTIAL, STALE, UNAVAILABLE, UNKNOWN
from devostasis.vitals import clutter, flow, pulse
from helpers import MEDIAN_HOURS, MEDIAN_SECONDS, add, clutter_inputs, flow_inputs, obs_set, pulse_inputs


def test_pulse_band_table():
    assert pulse.classify(15, 0, 0) == "SURGING"
    assert pulse.classify(2, 40, 2) == "SURGING"
    assert pulse.classify(3, 40, 1) == "STEADY"
    assert pulse.classify(3, 5, 1) == "STEADY"
    assert pulse.classify(2, 5, 1) == "QUIET"
    assert pulse.classify(0, 0, 0) == "DORMANT"


def test_pulse_exact_when_every_channel_is_observed():
    obs = obs_set()
    pulse_inputs(obs, commits=10, active_days=4, cr_updates=3, issue_updates=0)
    result = pulse.evaluate(obs)
    assert (result.band, result.evaluation_status, result.band_semantics) == ("STEADY", "AVAILABLE", "EXACT")
    assert result.derived["activity_events_28d"] == 13 and result.derived["channel_count"] == 2
    assert result.rule_id == "pulse.bands.v1"


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


def _capped_pulse(commits_days: tuple[int, int], cr_updates: int, issue_updates: int, days_exact: bool = False, coverage=None):
    obs = obs_set()
    commits, days = commits_days
    add(obs, "git.default_branch.commits.count_28d", commits, status=PARTIAL, reason_code="PAGINATION_CAPPED", coverage=coverage)
    if days_exact:
        add(obs, "git.default_branch.commit_active_days_28d", days)
    else:
        add(obs, "git.default_branch.commit_active_days_28d", days, status=PARTIAL, reason_code="PAGINATION_CAPPED", coverage=coverage)
    add(obs, "forge.change_requests.updated_count_28d", cr_updates)
    add(obs, "forge.issues.updated_count_28d", issue_updates)
    return obs


def test_pulse_cap_01_invariant_lower_bound_forces_one_band():
    result = pulse.evaluate(_capped_pulse((3000, 14), 500, 100))
    assert result.band == "SURGING" and result.evaluation_status == "DEGRADED"
    assert result.band_semantics == "CONSERVATIVE_LOWER_BOUND" and result.possible_bands == ["SURGING"]
    assert result.derived["commits_28d_semantics"] == "LOWER_BOUND" and result.derived["commit_active_days_28d_semantics"] == "LOWER_BOUND"
    assert result.derived["required_lower_bound_rule"] == "PV-PULSE-REQUIRED-LOWER-BOUND-001"
    assert any(code.startswith("REQUIRED_INPUT_PARTIAL:git.default_branch.commits.count_28d") for code in result.diagnostics)


def test_pulse_cap_01_exact_days_with_capped_commits_is_forced_quiet():
    result = pulse.evaluate(_capped_pulse((3000, 2), 0, 0, days_exact=True))
    assert result.band == "QUIET" and result.possible_bands == ["QUIET"] and result.evaluation_status == "DEGRADED"
    assert "commit_active_days_28d_semantics" not in result.derived


def test_pulse_cap_02_boundary_crossing_lists_every_reachable_band_and_no_exact_band():
    result = pulse.evaluate(_capped_pulse((3000, 2), 0, 0))
    assert result.evaluation_status == "DEGRADED" and result.band_semantics == "CONSERVATIVE_LOWER_BOUND"
    assert result.band == "QUIET" and result.possible_bands == ["QUIET", "STEADY", "SURGING"]
    assert "could reach QUIET, STEADY, SURGING" in result.explanation


def test_pulse_cap_03_unconstrained_required_tail_is_unknown():
    obs = obs_set()
    add(obs, "git.default_branch.commits.count_28d", status=PARTIAL, reason_code="PAGINATION_CAPPED")
    add(obs, "git.default_branch.commit_active_days_28d", 2)
    assert pulse.evaluate(obs).evaluation_status == "UNKNOWN"
    stale = obs_set()
    add(stale, "git.default_branch.commits.count_28d", 3000, status=PARTIAL, freshness=STALE, reason_code="PAGINATION_CAPPED")
    add(stale, "git.default_branch.commit_active_days_28d", 2)
    result = pulse.evaluate(stale)
    assert result.evaluation_status == "UNKNOWN" and result.band is None


def test_pulse_cap_04_optional_channel_cannot_make_capped_required_input_exact():
    result = pulse.evaluate(_capped_pulse((3000, 2), 500, 0))
    assert result.band == "SURGING" and result.possible_bands == ["SURGING"]
    assert result.evaluation_status == "DEGRADED" and result.band_semantics == "CONSERVATIVE_LOWER_BOUND"


def test_pulse_cap_05_pagination_metadata_is_non_semantic():
    results = [
        pulse.evaluate(_capped_pulse((3000, 2), 0, 0, coverage={"complete": False, "page_size": page_size})).to_dict()
        for page_size in (100, 30)
    ]
    assert results[0] == results[1]


def test_flow_no_queue_and_moving():
    obs = obs_set()
    flow_inputs(obs, 0, 0)
    result = flow.evaluate(obs)
    assert result.band == "NO_QUEUE" and result.rule_id == "flow.bands.v1"
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


def test_flow_eq_01_empty_queue_with_slow_historical_median_is_no_queue():
    obs = obs_set()
    flow_inputs(obs, 0, 1, median=240)
    result = flow.evaluate(obs)
    assert (result.band, result.evaluation_status, result.band_semantics) == ("NO_QUEUE", "AVAILABLE", "EXACT")
    assert "FLOW_HISTORICAL_MEDIAN_NOT_APPLICABLE:EMPTY_QUEUE" in result.diagnostics
    assert result.derived["median_time_to_merge_hours_28d"] == 240
    assert result.derived["median_time_to_merge_seconds_28d"] == {"numerator": 864000, "denominator": 1}
    assert "not applicable to an empty queue" in result.explanation


def test_flow_eq_02_extreme_historical_median_cannot_gridlock_an_empty_queue():
    obs = obs_set()
    flow_inputs(obs, 0, 1, median=500)
    assert flow.evaluate(obs).band == "NO_QUEUE"


def test_flow_eq_03_live_queue_keeps_the_congested_median_threshold():
    obs = obs_set()
    flow_inputs(obs, 1, 1, oldest=1, median=240)
    assert flow.evaluate(obs).band == "CONGESTED"


def test_flow_eq_04_live_large_queue_keeps_the_gridlocked_predicate():
    obs = obs_set()
    flow_inputs(obs, 10, 1, oldest=1, median=400)
    assert flow.evaluate(obs).band == "GRIDLOCKED"


def test_flow_eq_05_missing_open_count_never_becomes_an_empty_queue():
    for status, value in ((PARTIAL, 0), (UNKNOWN, None)):
        obs = obs_set()
        add(obs, "forge.change_requests.open_count", value, status=status, reason_code="PAGINATION_CAPPED")
        add(obs, "forge.change_requests.merged_count_28d", 1)
        add(obs, MEDIAN_SECONDS, {"numerator": 864000, "denominator": 1}, "duration")
        result = flow.evaluate(obs)
        assert result.band is None and result.evaluation_status == "UNKNOWN", status


def test_flow_eq_06_provider_and_order_invariance():
    first = obs_set()
    flow_inputs(first, 0, 1, median=240)
    second = obs_set()
    add(second, MEDIAN_SECONDS, {"numerator": 864000, "denominator": 1}, "duration")
    add(second, "forge.change_requests.merged_count_28d", 1)
    add(second, "forge.change_requests.open_count", 0)
    add(second, MEDIAN_HOURS, 240, "duration")
    assert flow.evaluate(first).to_dict() == flow.evaluate(second).to_dict()


def test_flow_prec_03_04_lower_boundary_is_exact_in_seconds():
    obs = obs_set()
    flow_inputs(obs, 1, 1, oldest=1, median_seconds=604800)
    assert flow.evaluate(obs).band == "MOVING"
    obs = obs_set()
    flow_inputs(obs, 1, 1, oldest=1, median_seconds=604801)
    assert flow.evaluate(obs).band == "CONGESTED"


def test_flow_prec_05_upper_boundary_is_exact_in_seconds():
    obs = obs_set()
    flow_inputs(obs, 10, 1, oldest=1, median_seconds=1209600)
    assert flow.evaluate(obs).band == "CONGESTED"
    obs = obs_set()
    flow_inputs(obs, 10, 1, oldest=1, median_seconds=1209601)
    assert flow.evaluate(obs).band == "GRIDLOCKED"


def test_flow_prec_06_empty_queue_takes_precedence_over_any_median():
    obs = obs_set()
    flow_inputs(obs, 0, 1, median_seconds=2000000)
    assert flow.evaluate(obs).band == "NO_QUEUE"


def test_flow_prec_09_partial_evidence_stays_unknown():
    obs = obs_set()
    add(obs, "forge.change_requests.open_count", 1)
    add(obs, "forge.change_requests.merged_count_28d", 1, status=PARTIAL, reason_code="PAGINATION_CAPPED")
    add(obs, "forge.change_requests.oldest_open_age_days", 1, "duration")
    add(obs, MEDIAN_SECONDS, {"numerator": 600, "denominator": 1}, "duration")
    assert flow.evaluate(obs).evaluation_status == "UNKNOWN"


def test_flow_fractional_median_is_classified_exactly_and_projected_to_whole_hours():
    obs = obs_set()
    flow_inputs(obs, 1, 2, oldest=1, median_seconds=(1209599, 2))
    result = flow.evaluate(obs)
    assert result.band == "MOVING"
    assert result.derived["median_time_to_merge_seconds_28d"] == {"numerator": 1209599, "denominator": 2}
    assert result.derived["median_time_to_merge_hours_28d"] == 167
    assert "median time to merge 167h 59m" in result.explanation


def test_flow_rejects_a_non_rational_median_record():
    obs = obs_set()
    add(obs, "forge.change_requests.open_count", 1)
    add(obs, "forge.change_requests.merged_count_28d", 1)
    add(obs, "forge.change_requests.oldest_open_age_days", 1, "duration")
    add(obs, MEDIAN_SECONDS, 600, "duration")
    result = flow.evaluate(obs)
    assert result.evaluation_status == "UNKNOWN" and any(code.startswith("INVALID_INPUT:") for code in result.diagnostics)


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
