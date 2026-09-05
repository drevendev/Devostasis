"""PULSE: observable activity intensity over the 28-day window.

Pulse is not productivity and low Pulse is not automatically unhealthy.
Supported optional channels that are not exactly observed cannot be treated as
zero: the band is then a conservative lower bound (V0.1/V0.2 repairs).
"""

from __future__ import annotations

from ..observations import ObservationSet
from ..policy import PULSE
from .common import (
    EVAL_AVAILABLE,
    EVAL_DEGRADED,
    SEM_EXACT,
    SEM_LOWER,
    VitalResult,
    as_int,
    bands_from,
    input_meta,
    missing_required,
    unknown_result,
)

VITAL_ID = "pulse"
VITAL_VERSION = "PV-VITALS-V1-002/pulse"
RULE_ID = "pulse.bands.v0"
BANDS = ["DORMANT", "QUIET", "STEADY", "SURGING"]

COMMITS = "git.default_branch.commits.count_28d"
ACTIVE_DAYS = "git.default_branch.commit_active_days_28d"
CR_UPDATES = "forge.change_requests.updated_count_28d"
ISSUE_UPDATES = "forge.issues.updated_count_28d"
REQUIRED = [COMMITS, ACTIVE_DAYS]
OPTIONAL = [CR_UPDATES, ISSUE_UPDATES]

SHARED = ["DEFAULT_BRANCH_ACTIVITY", "CHANGE_REQUEST_ACTIVITY", "ISSUE_ACTIVITY"]
GROUPS = ["FLOW_PULSE_ACTIVITY", "DIRECTION_PULSE_ACTIVITY"]


def classify(active_days: int, events: int, channel_count: int) -> str:
    if active_days >= PULSE["surging_active_days"] or (
        events >= PULSE["surging_events"] and channel_count >= PULSE["surging_channels"]
    ):
        return "SURGING"
    if active_days >= PULSE["steady_active_days"] and events >= PULSE["steady_events"]:
        return "STEADY"
    if events > 0:
        return "QUIET"
    return "DORMANT"


def evaluate(obs: ObservationSet) -> VitalResult:
    ids = REQUIRED + OPTIONAL
    missing = missing_required(obs, REQUIRED)
    if missing:
        return unknown_result(VITAL_ID, VITAL_VERSION, RULE_ID, obs, ids, missing, SHARED, GROUPS)

    commits = as_int(obs.value_of(COMMITS))
    active_days = as_int(obs.value_of(ACTIVE_DAYS))
    channels: dict[str, int] = {"commits": commits}
    unobserved: list[str] = []
    for oid in OPTIONAL:
        if obs.is_good(oid):
            channels[oid] = as_int(obs.value_of(oid))
        else:
            unobserved.append(f"UNOBSERVED_CHANNEL:{oid}:{obs.status_of(oid)}/{obs.freshness_of(oid)}")

    events = sum(channels.values())
    channel_count = sum(1 for value in channels.values() if value > 0)
    band = classify(active_days, events, channel_count)
    derived = {
        "commits_28d": commits,
        "commit_active_days_28d": active_days,
        "activity_events_28d": events,
        "channel_count": channel_count,
        "channels_observed": dict(sorted(channels.items())),
    }

    if not unobserved:
        return VitalResult(
            vital_id=VITAL_ID,
            vital_version=VITAL_VERSION,
            rule_id=RULE_ID,
            band=band,
            evaluation_status=EVAL_AVAILABLE,
            band_semantics=SEM_EXACT,
            possible_bands=None,
            inputs=input_meta(obs, ids),
            derived=derived,
            shared_signal_groups=SHARED,
            dependency_group_ids=GROUPS,
            diagnostics=[],
            explanation=(
                f"{commits} default-branch commits on {active_days} active days and "
                f"{events} activity events across {channel_count} channels in 28 days."
            ),
        )

    derived["activity_events_28d_semantics"] = "LOWER_BOUND"
    return VitalResult(
        vital_id=VITAL_ID,
        vital_version=VITAL_VERSION,
        rule_id=RULE_ID,
        band=band,
        evaluation_status=EVAL_DEGRADED,
        band_semantics=SEM_LOWER,
        possible_bands=bands_from(BANDS, band),
        inputs=input_meta(obs, ids),
        derived=derived,
        shared_signal_groups=SHARED,
        dependency_group_ids=GROUPS,
        diagnostics=unobserved,
        explanation=(
            f"At least {events} activity events observed ({commits} commits on {active_days} active days); "
            "one or more activity channels were not exactly observed, so the band is a lower bound."
        ),
    )
