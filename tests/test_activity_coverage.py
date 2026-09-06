"""Activity must not report more coverage than its evidence has.

Two defects found by review. A release inventory that was PARTIAL produced a
count with no coverage note, so a truncated list read as complete. And an
interval following a long outage was reported in full while the inventories
behind it only reach back a fixed window, so the older part of the interval
read as "nothing happened" instead of "not observed" (G1).
"""

from __future__ import annotations

from devostasis import normalize
from devostasis.activity import build_activity
from devostasis.observations import PARTIAL, UNAVAILABLE
from devostasis.policy import ACTIVITY
from helpers import add, finalize, obs_set

END = "2026-09-06T12:00:00Z"
EVIDENCE_FROM = "2026-08-09T12:00:00Z"  # END minus the 28-day activity window
WINDOW_NOTE = f"INTERVAL_EXCEEDS_EVIDENCE_WINDOW:evidence_from={EVIDENCE_FROM}"


def _activity(interval_start=None, **inventories):
    obs = obs_set(END)
    for key, (value, status, reason) in inventories.items():
        add(obs, getattr(normalize, key), value, "series", status=status, reason_code=reason)
    finalize(obs)
    return build_activity(obs, {"observed_at": interval_start} if interval_start else None, interval_start, 50)


def _release(published_at="2026-09-05T10:00:00Z"):
    return [{"tag": "v1", "name": "one", "published_at": published_at, "prerelease": False}]


def test_a_partial_release_inventory_declares_its_coverage():
    activity = _activity(INV_RELEASES=(_release(), PARTIAL, "PAGINATION_CAPPED"))
    assert "RELEASE:PARTIAL:PAGINATION_CAPPED" in activity["coverage_notes"]
    assert activity["classes"]["RELEASE"]["count"] == 1, "the observed releases are still reported"


def test_an_exact_release_inventory_says_nothing():
    activity = _activity(INV_RELEASES=(_release(), "AVAILABLE", None))
    assert not any(note.startswith("RELEASE:") for note in activity["coverage_notes"])


def test_an_unavailable_release_inventory_still_declares_itself():
    activity = _activity(INV_RELEASES=(None, UNAVAILABLE, "NOT_FOUND"))
    assert "RELEASE:UNAVAILABLE" in activity["coverage_notes"]
    assert activity["classes"]["RELEASE"]["count"] == 0


def test_an_interval_wider_than_the_evidence_window_says_so():
    """A run after a long outage claims a wide interval; the inventories do not reach that far."""
    activity = _activity("2026-06-01T00:00:00Z", INV_RELEASES=(_release(), "AVAILABLE", None))
    assert WINDOW_NOTE in activity["coverage_notes"]
    assert activity["interval"]["start"] == "2026-06-01T00:00:00Z"
    assert activity["interval"]["basis"] == "PREVIOUS_BUNDLE", "the interval itself is not shortened"


def test_an_interval_inside_the_evidence_window_is_quiet():
    activity = _activity("2026-09-05T12:00:00Z", INV_RELEASES=(_release(), "AVAILABLE", None))
    assert not any("INTERVAL" in note for note in activity["coverage_notes"])


def test_the_boundary_of_the_evidence_window_is_not_a_gap():
    activity = _activity(EVIDENCE_FROM, INV_RELEASES=(_release(), "AVAILABLE", None))
    assert not any("INTERVAL" in note for note in activity["coverage_notes"])
    one_second_earlier = _activity("2026-08-09T11:59:59Z", INV_RELEASES=(_release(), "AVAILABLE", None))
    assert WINDOW_NOTE in one_second_earlier["coverage_notes"]


def test_a_baseline_bundle_is_never_wider_than_its_evidence():
    """A BASELINE interval is exactly the observation window, so it can never overrun it."""
    activity = _activity(None, INV_RELEASES=(_release(), "AVAILABLE", None))
    assert activity["interval"]["basis"] == "OBSERVATION_WINDOW_28D"
    assert not any("INTERVAL" in note for note in activity["coverage_notes"])
    assert ACTIVITY["window_days"] == 28
