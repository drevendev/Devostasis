"""Numeric policy constants (``devostasis.policy.v1``).

Every constant here is a PROVISIONAL calibration constant frozen by the V0
taxonomy and preserved unchanged through V1.1. Changing any of them is a policy
version change and must be justified against the conformance fixtures, never
against one repository looking right.

The ``*_median_seconds`` constants are the exact dimensional conversions of the
hour constants demanded by PV-FLOW-MERGE-LATENCY-001 (168 h = 604800 s,
336 h = 1209600 s); they are not a new threshold and keep the policy version.
"""

POLICY_VERSION = "devostasis.policy.v1"

PULSE = {
    "window_days": 28,
    "surging_active_days": 15,
    "surging_events": 40,
    "surging_channels": 2,
    "steady_active_days": 3,
    "steady_events": 5,
}

FLOW = {
    "window_days": 28,
    "gridlocked_open": 3,
    "gridlocked_oldest_days": 30,
    "gridlocked_open_with_slow_median": 10,
    "gridlocked_median_hours": 336,
    "gridlocked_median_seconds": 336 * 3600,
    "congested_oldest_days": 14,
    "congested_open": 10,
    "congested_median_hours": 168,
    "congested_median_seconds": 168 * 3600,
}

CLUTTER = {
    "issue_stale_days": 30,
    "change_request_stale_days": 14,
    "branch_stale_days": 30,
    "ratio_min_tracked": 4,
    "heavy_stale_work": 25,
    "heavy_ratio": (1, 2),
    "heavy_stale_branches": 20,
    "cluttered_stale_work": 5,
    "cluttered_ratio": (1, 4),
    "cluttered_stale_branches": 6,
}

INTEGRITY = {
    "window_days": 14,
    "established_sample": 4,
    "failing_ratio": (1, 4),
}

PLANNING = {
    "frame_days": 28,
}

ACTIVITY = {
    "window_days": 28,
}


def as_dict() -> dict:
    return {
        "policy_version": POLICY_VERSION,
        "pulse": dict(PULSE),
        "flow": dict(FLOW),
        "clutter": {k: list(v) if isinstance(v, tuple) else v for k, v in CLUTTER.items()},
        "integrity": {k: list(v) if isinstance(v, tuple) else v for k, v in INTEGRITY.items()},
        "planning": dict(PLANNING),
        "activity": dict(ACTIVITY),
    }
