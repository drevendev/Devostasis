"""RAW_OBSERVATION_CONTRACT_V0 conformance cases C1-C7."""

import pytest

from devostasis.observations import (
    AVAILABLE,
    ERROR,
    FORBIDDEN,
    NOT_REQUESTED,
    PARTIAL,
    STALE,
    UNAVAILABLE,
    UNKNOWN,
    Observation,
    ObservationError,
)
from helpers import add, finalize, obs_set


def test_c1_observed_zero_is_available_with_value_zero():
    obs = obs_set()
    item = add(obs, "forge.change_requests.open_count", 0)
    assert item.status == AVAILABLE and item.value == 0 and item.good


def test_c2_tier_limitation_is_unavailable_without_value():
    obs = obs_set()
    item = add(obs, "forge.rulesets.count", status=UNAVAILABLE, reason_code="TIER_UNAVAILABLE")
    assert item.value is None and not item.good and item.reason_code == "TIER_UNAVAILABLE"
    with pytest.raises(ObservationError):
        Observation(observation_id="x", status=UNAVAILABLE, value_type="count", value=0)


def test_c3_permission_denial_is_forbidden_not_unavailable():
    obs = obs_set()
    item = add(obs, "forge.issues.open_count", status=FORBIDDEN, reason_code="FORBIDDEN")
    assert item.status == FORBIDDEN and obs.value_of("forge.issues.open_count") is None


def test_c4_truncated_history_is_partial_with_coverage():
    obs = obs_set()
    item = add(obs, "ci.revision_verdicts_14d", [], "series", status=PARTIAL, reason_code="PAGINATION_CAPPED", coverage={"runs_complete": False})
    assert item.status == PARTIAL and not item.good and item.coverage["runs_complete"] is False


def test_c5_stale_evidence_keeps_value_but_is_not_fresh():
    obs = obs_set()
    item = add(obs, "forge.issues.open_count", 7, freshness=STALE)
    assert item.value == 7 and item.status == AVAILABLE and not item.good
    assert not obs.is_good("forge.issues.open_count")


def test_c6_connector_ambiguity_is_unknown():
    obs = obs_set()
    item = add(obs, "forge.rulesets.count", status=UNKNOWN, reason_code="AMBIGUOUS")
    assert item.status == UNKNOWN and item.value is None


def test_c7_transient_failure_is_error_not_unknown():
    obs = obs_set()
    item = add(obs, "forge.issues.open_count", status=ERROR, reason_code="PROVIDER_ERROR")
    assert item.status == ERROR and item.value is None


def test_receipt_distinguishes_not_requested_unknown_and_zero():
    obs = obs_set()
    add(obs, "forge.change_requests.open_count", 0)
    add(obs, "forge.issues.open_count", status=UNKNOWN, reason_code="AMBIGUOUS")
    finalize(obs)
    receipt = obs.receipt.to_dict()
    assert receipt["per_key"]["forge.change_requests.open_count"]["status"] == AVAILABLE
    assert receipt["per_key"]["forge.issues.open_count"]["status"] == UNKNOWN
    assert "forge.issues.open_count" not in receipt["returned_keys"]
    assert obs.status_of("git.nondefault_branches.stale_count_30d") == NOT_REQUESTED


def test_available_requires_a_value_and_duplicates_are_rejected():
    with pytest.raises(ObservationError):
        Observation(observation_id="x", status=AVAILABLE, value_type="count")
    obs = obs_set()
    add(obs, "a", 1)
    with pytest.raises(ObservationError):
        add(obs, "a", 2)


def test_round_trip_serialization_is_lossless():
    obs = obs_set()
    add(obs, "forge.issues.open_count", 3, coverage={"complete": True})
    add(obs, "forge.rulesets.count", status=UNAVAILABLE, reason_code="TIER_UNAVAILABLE")
    finalize(obs)
    from devostasis.observations import ObservationSet

    clone = ObservationSet.from_dict(obs.to_dict())
    assert clone.to_dict() == obs.to_dict()
    assert clone.digest() == obs.digest()
