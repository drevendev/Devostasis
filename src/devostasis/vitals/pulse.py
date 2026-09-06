"""PULSE: observable activity intensity over the 28-day window (rule ``pulse.bands.v1``).

Pulse is not productivity and low Pulse is not automatically unhealthy.
Supported optional channels that are not exactly observed cannot be treated as
zero: the band is then a conservative lower bound (V0.1/V0.2 repairs).

A required input that is PARTIAL because a newest-first enumeration was capped
follows PV-PULSE-REQUIRED-LOWER-BOUND-001: the observed rows are a lower bound,
never complete evidence. The classifier is evaluated over every admissible
completion of the missing tail. If every completion yields the same band, that
band is emitted as DEGRADED / CONSERVATIVE_LOWER_BOUND; if completions can
cross a band boundary, ``possible_bands`` lists every reachable band and no
exact band is asserted; a capped input without a usable value stays UNKNOWN.
"""

from __future__ import annotations

from ..observations import FRESH, PARTIAL, ObservationSet
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
    unknown_result,
)

VITAL_ID = "pulse"
VITAL_VERSION = "PV-VITALS-V1-002/pulse"
RULE_ID = "pulse.bands.v1"
REQUIRED_LOWER_BOUND_RULE = "PV-PULSE-REQUIRED-LOWER-BOUND-001"
BANDS = ["DORMANT", "QUIET", "STEADY", "SURGING"]

COMMITS = "git.default_branch.commits.count_28d"
ACTIVE_DAYS = "git.default_branch.commit_active_days_28d"
CR_UPDATES = "forge.change_requests.updated_count_28d"
ISSUE_UPDATES = "forge.issues.updated_count_28d"
REQUIRED = [COMMITS, ACTIVE_DAYS]
OPTIONAL = [CR_UPDATES, ISSUE_UPDATES]

SHARED = ["DEFAULT_BRANCH_ACTIVITY", "CHANGE_REQUEST_ACTIVITY", "ISSUE_ACTIVITY"]
GROUPS = ["FLOW_PULSE_ACTIVITY", "DIRECTION_PULSE_ACTIVITY"]

UNBOUNDED_EVENTS = 10**9


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


def reachable_bands(
    active_days: int,
    days_uncertain: bool,
    events: int,
    events_uncertain: bool,
    channels_low: int,
    channels_high: int,
) -> list[str]:
    """Every band some admissible completion of the partial evidence can reach.

    The classifier is monotone in active days, events and channel count and
    piecewise constant between the policy thresholds, so evaluating it at the
    observed lower bounds and at every threshold above them covers the whole
    completion space exactly.
    """
    window = PULSE["window_days"]
    if days_uncertain:
        days_set = {d for d in (active_days, PULSE["steady_active_days"], PULSE["surging_active_days"], window) if active_days <= d <= window}
    else:
        days_set = {active_days}
    if events_uncertain:
        events_set = {e for e in (events, PULSE["steady_events"], PULSE["surging_events"], UNBOUNDED_EVENTS) if e >= events}
    else:
        events_set = {events}
    reached = {
        classify(d, e, c)
        for d in days_set
        for e in events_set
        for c in range(channels_low, channels_high + 1)
    }
    return [band for band in BANDS if band in reached]


def _partial_lower_bound(obs: ObservationSet, oid: str) -> bool:
    item = obs.get(oid)
    return bool(item is not None and item.status == PARTIAL and item.freshness == FRESH and item.has_value)


def evaluate(obs: ObservationSet) -> VitalResult:
    ids = REQUIRED + OPTIONAL
    missing: list[str] = []
    partial_required: list[str] = []
    for oid in REQUIRED:
        if obs.is_good(oid):
            continue
        if _partial_lower_bound(obs, oid):
            partial_required.append(f"REQUIRED_INPUT_PARTIAL:{oid}:{obs.get(oid).reason_code}")
        else:
            missing.append(f"MISSING_REQUIRED:{oid}:{obs.status_of(oid)}/{obs.freshness_of(oid)}")
    if missing:
        return unknown_result(VITAL_ID, VITAL_VERSION, RULE_ID, obs, ids, missing + partial_required, SHARED, GROUPS)

    commits = as_int(obs.value_of(COMMITS))
    active_days = as_int(obs.value_of(ACTIVE_DAYS))
    commits_capped = not obs.is_good(COMMITS)
    days_capped = not obs.is_good(ACTIVE_DAYS)
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

    if not unobserved and not partial_required:
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
    if partial_required:
        # PV-PULSE-REQUIRED-LOWER-BOUND-001: bounded inference over every admissible completion.
        channels_high = channel_count + len(unobserved) + (1 if commits == 0 and commits_capped else 0)
        possible = reachable_bands(
            active_days,
            days_capped,
            events,
            commits_capped or bool(unobserved),
            channel_count,
            channels_high,
        )
        band = possible[0]
        if commits_capped:
            derived["commits_28d_semantics"] = "LOWER_BOUND"
        if days_capped:
            derived["commit_active_days_28d_semantics"] = "LOWER_BOUND"
        derived["required_lower_bound_rule"] = REQUIRED_LOWER_BOUND_RULE
        if len(possible) == 1:
            tail = f"a required enumeration was capped, and every admissible completion still yields {band}"
        else:
            tail = f"a required enumeration was capped, and the unseen tail could reach {', '.join(possible)}"
    else:
        possible = bands_from(BANDS, band)
        tail = "one or more activity channels were not exactly observed, so the band is a lower bound"
    return VitalResult(
        vital_id=VITAL_ID,
        vital_version=VITAL_VERSION,
        rule_id=RULE_ID,
        band=band,
        evaluation_status=EVAL_DEGRADED,
        band_semantics=SEM_LOWER,
        possible_bands=possible,
        inputs=input_meta(obs, ids),
        derived=derived,
        shared_signal_groups=SHARED,
        dependency_group_ids=GROUPS,
        diagnostics=unobserved + partial_required,
        explanation=(
            f"At least {events} activity events observed ({commits} commits on {active_days} active days); {tail}."
        ),
    )
