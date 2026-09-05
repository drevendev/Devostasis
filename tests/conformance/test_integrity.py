"""Integrity bands and PV-CI-UNIT-004 revision semantics (R54-R57 and the V0.x chain)."""

from devostasis.adapters import github_ci
from devostasis.observations import PARTIAL
from devostasis.vitals import integrity
from helpers import add, integrity_inputs, obs_set, parent, passing_revisions, revision


def test_uninstrumented_when_ci_positively_absent():
    obs = obs_set()
    integrity_inputs(obs, False, [revision("a", "2026-09-01T00:00:00Z")])
    result = integrity.evaluate(obs)
    assert result.band == "UNINSTRUMENTED" and result.evaluation_status == "AVAILABLE"


def test_unknown_when_configuration_cannot_be_established():
    obs = obs_set()
    integrity_inputs(obs, None, [revision("a", "2026-09-01T00:00:00Z")])
    result = integrity.evaluate(obs)
    assert result.band is None and result.evaluation_status == "UNKNOWN"


def test_t1_no_recent_runs_is_neither_clean_nor_uninstrumented():
    obs = obs_set()
    integrity_inputs(obs, True, [revision("a", "2026-09-01T00:00:00Z")])
    assert integrity.evaluate(obs).band == "NO_RECENT_RUNS"


def test_no_decisive_runs_when_only_cancelled_or_unresolved():
    obs = obs_set()
    integrity_inputs(obs, True, [revision("a", "2026-09-01T00:00:00Z", [parent("p1", "NON_VERIFY_TERMINAL")], "NON_VERIFY_TERMINAL")])
    assert integrity.evaluate(obs).band == "NO_DECISIVE_RUNS"


def test_sparse_and_sparse_mixed():
    obs = obs_set()
    integrity_inputs(obs, True, passing_revisions(2))
    assert integrity.evaluate(obs).band == "SPARSE"
    obs = obs_set()
    revs = passing_revisions(2) + [revision("bad", "2026-08-30T00:00:00Z", [parent("pf", "VERIFY_FAIL")], "VERIFY_FAIL", "FAILURE_OBSERVED")]
    integrity_inputs(obs, True, revs)
    assert integrity.evaluate(obs).band == "SPARSE_MIXED"


def test_clean_flaky_and_failing_by_ratio():
    obs = obs_set()
    integrity_inputs(obs, True, passing_revisions(4))
    assert integrity.evaluate(obs).band == "CLEAN"

    obs = obs_set()
    revs = passing_revisions(7) + [revision("f1", "2026-08-30T00:00:00Z", [parent("pf", "VERIFY_FAIL")], "VERIFY_FAIL", "FAILURE_OBSERVED")]
    integrity_inputs(obs, True, revs)
    result = integrity.evaluate(obs)
    assert result.band == "FLAKY" and result.derived["failure_ratio_14d"] == {"num": 1, "den": 8}

    obs = obs_set()
    revs = passing_revisions(3) + [revision("f1", "2026-08-30T00:00:00Z", [parent("pf", "VERIFY_FAIL")], "VERIFY_FAIL", "FAILURE_OBSERVED")]
    integrity_inputs(obs, True, revs)
    assert integrity.evaluate(obs).band == "FAILING"


def test_failing_when_latest_revision_currently_fails_even_with_clean_history():
    obs = obs_set()
    revs = passing_revisions(6) + [revision("zz", "2026-09-09T00:00:00Z", [parent("pf", "VERIFY_FAIL")], "VERIFY_FAIL", "FAILURE_OBSERVED")]
    integrity_inputs(obs, True, revs)
    assert integrity.evaluate(obs).band == "FAILING"


def test_r54_same_revision_retry_success_keeps_historical_failure():
    run = {"id": 1, "run_attempt": 2, "status": "completed", "conclusion": "success", "name": "ci", "event": "push"}
    prior = [{"run_attempt": 1, "status": "completed", "conclusion": "failure"}]
    parent_record = github_ci.actions_parent(run, prior)
    assert parent_record["current_state"] == "VERIFY_PASS" and parent_record["history_state"] == "FAILURE_OBSERVED"
    records = github_ci.build_revision_records([{"sha": "r", "committed_at": "2026-09-01T00:00:00Z"}], {"r": [parent_record]})
    assert records[0]["current_verdict"] == "VERIFY_PASS"
    assert records[0]["historical_contribution"] == "VERIFY_FAIL"
    obs = obs_set()
    integrity_inputs(obs, True, passing_revisions(3) + records)
    result = integrity.evaluate(obs)
    assert result.derived["failed_count_14d"] == 1 and result.derived["decisive_count_14d"] == 4 and result.band == "FAILING"


def test_r55_retry_count_invariance():
    def contribution(retries: int) -> str:
        prior = [{"run_attempt": 1, "status": "completed", "conclusion": "failure"}] + [
            {"run_attempt": n, "status": "completed", "conclusion": "success"} for n in range(2, retries + 1)
        ]
        run = {"id": 9, "run_attempt": retries + 1, "status": "completed", "conclusion": "success", "name": "ci"}
        records = github_ci.build_revision_records([{"sha": "r", "committed_at": "2026-09-01T00:00:00Z"}], {"r": [github_ci.actions_parent(run, prior)]})
        return records[0]["historical_contribution"]

    assert {contribution(n) for n in (1, 2, 3, 4)} == {"VERIFY_FAIL"}


def test_r56_newer_revision_is_a_distinct_sample():
    failed = revision("r1", "2026-09-01T00:00:00Z", [parent("p1", "VERIFY_FAIL")], "VERIFY_FAIL", "FAILURE_OBSERVED")
    passed = revision("r2", "2026-09-02T00:00:00Z", [parent("p2", "VERIFY_PASS")], "VERIFY_PASS", "PASS_ONLY_OBSERVED")
    obs = obs_set()
    integrity_inputs(obs, True, [failed, passed])
    result = integrity.evaluate(obs)
    assert result.derived["decisive_count_14d"] == 2 and result.derived["failed_count_14d"] == 1
    assert result.band == "SPARSE_MIXED"


def test_r57_order_and_surface_invariance():
    commits = [{"sha": "a", "committed_at": "2026-09-01T00:00:00Z"}, {"sha": "b", "committed_at": "2026-09-02T00:00:00Z"}]
    run_a = {"id": 1, "run_attempt": 2, "status": "completed", "conclusion": "success", "name": "ci"}
    prior_a = [{"run_attempt": 1, "status": "completed", "conclusion": "failure"}]
    run_b = {"id": 2, "run_attempt": 1, "status": "completed", "conclusion": "success", "name": "ci"}
    forward = github_ci.build_revision_records(commits, {"a": [github_ci.actions_parent(run_a, prior_a)], "b": [github_ci.actions_parent(run_b, [])]})
    backward = github_ci.build_revision_records(list(reversed(commits)), {"b": [github_ci.actions_parent(run_b, [])], "a": [github_ci.actions_parent(run_a, list(reversed(prior_a)))]})
    assert forward == backward


def test_v0_7_unresolved_sibling_blocks_pass_but_not_fail():
    assert github_ci.compose_current(["VERIFY_PASS", "VERIFY_UNRESOLVED"]) == "VERIFY_UNRESOLVED"
    assert github_ci.compose_current(["VERIFY_FAIL", "VERIFY_UNRESOLVED"]) == "VERIFY_FAIL"
    assert github_ci.compose_current(["UNKNOWN", "VERIFY_PASS"]) == "UNKNOWN"
    assert github_ci.compose_current(["NOT_EXECUTED", "VERIFY_PASS"]) == "VERIFY_PASS"


def test_ci_norm_outcome_mapping_fails_closed():
    assert github_ci.normalize_outcome("completed", "success") == "VERIFY_PASS"
    assert github_ci.normalize_outcome("completed", "failure") == "VERIFY_FAIL"
    assert github_ci.normalize_outcome("completed", "timed_out") == "VERIFY_FAIL"
    assert github_ci.normalize_outcome("completed", "cancelled") == "NON_VERIFY_TERMINAL"
    assert github_ci.normalize_outcome("completed", "skipped") == "NOT_EXECUTED"
    assert github_ci.normalize_outcome("in_progress", None) == "VERIFY_UNRESOLVED"
    assert github_ci.normalize_outcome("completed", "startup_failure") == "UNKNOWN"
    assert github_ci.normalize_outcome("completed", "some_future_value") == "UNKNOWN"


def test_current_unresolved_degrades_instead_of_claiming_clean():
    revs = passing_revisions(4) + [revision("new", "2026-09-09T00:00:00Z", [parent("pn", "VERIFY_UNRESOLVED")], "VERIFY_UNRESOLVED", "NO_DECISIVE_OBSERVED")]
    obs = obs_set()
    integrity_inputs(obs, True, revs)
    result = integrity.evaluate(obs)
    assert result.band == "CLEAN" and result.evaluation_status == "DEGRADED"
    assert "FAILING" in result.possible_bands and "CURRENT_VERIFICATION_UNRESOLVED" in result.diagnostics


def test_partial_revision_series_is_degraded_superset():
    obs = obs_set()
    integrity_inputs(obs, True, passing_revisions(5), status=PARTIAL)
    result = integrity.evaluate(obs)
    assert result.band == "CLEAN" and result.evaluation_status == "DEGRADED" and result.band_semantics == "NON_AUTHORITATIVE_CONSERVATIVE_SUPERSET"


def test_latest_non_decisive_revision_falls_back_to_latest_decisive_verdict():
    revs = passing_revisions(4) + [revision("skip", "2026-09-09T00:00:00Z", [parent("ps", "NOT_EXECUTED")], "NOT_EXECUTED", "NO_DECISIVE_OBSERVED")]
    obs = obs_set()
    integrity_inputs(obs, True, revs)
    result = integrity.evaluate(obs)
    assert result.band == "CLEAN" and result.evaluation_status == "AVAILABLE"
    assert any(code.startswith("LATEST_REVISION_NON_DECISIVE") for code in result.diagnostics)


def test_parent_level_provenance_is_diagnosed():
    revs = [revision("s", "2026-09-01T00:00:00Z", [parent("suite", "VERIFY_PASS", kind="github_check_suite")], "VERIFY_PASS", "PASS_ONLY_OBSERVED", provenance="PARENT_LEVEL_ONLY")]
    obs = obs_set()
    integrity_inputs(obs, True, revs)
    result = integrity.evaluate(obs)
    assert "HISTORY_PROVENANCE_PARENT_LEVEL_ONLY:1" in result.diagnostics
