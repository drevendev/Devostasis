"""GitHub outcome map devostasis.ci-outcomes.github.v1 (CI-OUTCOME-01..04, accepted by PV-CAL-003)."""

from devostasis.adapters import github_ci


def test_ci_outcome_01_timed_out_is_a_verification_failure():
    assert github_ci.normalize_outcome("completed", "timed_out") == github_ci.VERIFY_FAIL


def test_ci_outcome_02_startup_failure_is_unknown_not_a_project_failure():
    assert github_ci.normalize_outcome("completed", "startup_failure") == github_ci.UNKNOWN
    assert "startup_failure" not in github_ci.OUTCOME_MAP


def test_ci_outcome_03_current_execution_state_outranks_a_conclusion():
    for status in ("queued", "in_progress", "waiting", "requested", "pending", None):
        assert github_ci.normalize_outcome(status, "success") == github_ci.VERIFY_UNRESOLVED, status


def test_ci_outcome_04_unknown_future_conclusions_fail_closed():
    assert github_ci.normalize_outcome("completed", "brand_new_value") == github_ci.UNKNOWN
    assert github_ci.normalize_outcome("completed", None) == github_ci.UNKNOWN
    assert github_ci.OUTCOME_MAP_VERSION == "devostasis.ci-outcomes.github.v1"
