"""Derive the aggregate observations the Vitals consume from provider-neutral inventories.

Adapters emit inventories (lists of normalized records with coverage metadata).
This module turns them into the aggregate observation keys named by the Vital
contracts, propagating status, freshness and provenance. Nothing here
interprets project health.
"""

from __future__ import annotations

from typing import Any, Callable

from . import timeutil
from .config import ResolvedProject
from .observations import AVAILABLE, PARTIAL, UNAVAILABLE, VALUE_BEARING, Observation, ObservationSet
from .policy import CLUTTER, FLOW, INTEGRITY, PLANNING, PULSE

INV_REPO = "forge.repository.metadata"
INV_COMMITS = "git.default_branch.commits_28d"
INV_CRS = "forge.change_requests.inventory"
INV_ISSUES = "forge.issues.inventory"
INV_BRANCHES = "git.nondefault_branches.inventory"
INV_TARGETS = "planning.explicit_targets.inventory"
INV_RELEASES = "forge.releases.inventory"
CI_CONFIGURED = "ci.configured"
CI_REVISIONS = "ci.revision_verdicts_14d"

INVENTORY_IDS = [INV_REPO, INV_COMMITS, INV_CRS, INV_ISSUES, INV_BRANCHES, INV_TARGETS, INV_RELEASES, CI_CONFIGURED, CI_REVISIONS]


def _derived(
    obs: ObservationSet,
    observation_id: str,
    value_type: str,
    source: Observation,
    compute: Callable[[list[dict[str, Any]]], Any],
    complete: bool = True,
    extra_sources: list[str] | None = None,
    reason_override: str | None = None,
) -> None:
    """Add an aggregate derived from ``source``; status follows the source and the coverage flag."""
    if observation_id in obs:
        return
    evidence = {"derived_from": [source.observation_id] + (extra_sources or [])}
    common = {
        "provider": source.provider,
        "collected_at": source.collected_at,
        "source_ref": f"derived:{source.observation_id}",
        "adapter_version": source.adapter_version,
        "freshness": source.freshness,
        "evidence_ref": evidence,
    }
    if source.status not in VALUE_BEARING or not isinstance(source.value, list):
        obs.add(
            Observation(
                observation_id=observation_id,
                status=source.status if source.status not in VALUE_BEARING else UNAVAILABLE,
                value_type=value_type,
                reason_code=reason_override or source.reason_code or "SOURCE_NOT_AVAILABLE",
                **common,
            )
        )
        return
    value = compute(source.value)
    status = AVAILABLE if (source.status == AVAILABLE and complete) else PARTIAL
    obs.add(
        Observation(
            observation_id=observation_id,
            status=status,
            value_type=value_type,
            value=value,
            coverage={"complete": status == AVAILABLE, "source_coverage": source.coverage},
            reason_code=None if status == AVAILABLE else (reason_override or "SOURCE_COVERAGE_INCOMPLETE"),
            **common,
        )
    )


def _flag(source: Observation, key: str) -> bool:
    coverage = source.coverage or {}
    return bool(coverage.get(key, True))


def _ts(value: str | None):
    return timeutil.parse_ts(value) if value else None


def _median(values: list[int]) -> int:
    ordered = sorted(values)
    count = len(ordered)
    middle = count // 2
    if count % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) // 2


def derive(obs: ObservationSet, project: ResolvedProject) -> ObservationSet:
    observed_at = timeutil.parse_ts(obs.observed_at)
    since_pulse = timeutil.minus_days(observed_at, PULSE["window_days"])
    since_flow = timeutil.minus_days(observed_at, FLOW["window_days"])
    since_planning = timeutil.minus_days(observed_at, PLANNING["frame_days"])
    stale_issue = timeutil.minus_days(observed_at, CLUTTER["issue_stale_days"])
    stale_cr = timeutil.minus_days(observed_at, CLUTTER["change_request_stale_days"])
    stale_branch = timeutil.minus_days(observed_at, CLUTTER["branch_stale_days"])

    commits = obs.get(INV_COMMITS)
    if commits is not None:
        _derived(
            obs, "git.default_branch.commits.count_28d", "count", commits,
            lambda items: len(items), complete=_flag(commits, "complete"),
        )
        _derived(
            obs, "git.default_branch.commit_active_days_28d", "count", commits,
            lambda items: len({timeutil.utc_day(timeutil.parse_ts(item["committed_at"])) for item in items}),
            complete=_flag(commits, "complete"),
        )

    crs = obs.get(INV_CRS)
    if crs is not None:
        open_ok = _flag(crs, "open_complete")
        window_ok = _flag(crs, "window_complete")

        def _open(items):
            return [item for item in items if item.get("state") == "OPEN"]

        def _merged_in_window(items):
            return [item for item in items if item.get("merged_at") and timeutil.parse_ts(item["merged_at"]) >= since_flow]

        def _updated_in_window(items):
            return [item for item in items if item.get("updated_at") and timeutil.parse_ts(item["updated_at"]) >= since_flow]

        _derived(obs, "forge.change_requests.open_count", "count", crs, lambda items: len(_open(items)), complete=open_ok)
        _derived(obs, "forge.change_requests.merged_count_28d", "count", crs, lambda items: len(_merged_in_window(items)), complete=window_ok)
        _derived(obs, "forge.change_requests.updated_count_28d", "count", crs, lambda items: len(_updated_in_window(items)), complete=window_ok)
        _derived(
            obs, "forge.change_requests.stale_open_count_14d", "count", crs,
            lambda items: len([i for i in _open(items) if timeutil.parse_ts(i["updated_at"]) < stale_cr]),
            complete=open_ok,
        )
        if crs.has_value and _open(crs.value):
            _derived(
                obs, "forge.change_requests.oldest_open_age_days", "duration", crs,
                lambda items: max(timeutil.age_days(observed_at, timeutil.parse_ts(i["created_at"])) for i in _open(items)),
                complete=open_ok,
            )
        if crs.has_value and _merged_in_window(crs.value):
            _derived(
                obs, "forge.change_requests.median_time_to_merge_hours_28d", "duration", crs,
                lambda items: _median([
                    timeutil.hours_between(timeutil.parse_ts(i["created_at"]), timeutil.parse_ts(i["merged_at"]))
                    for i in _merged_in_window(items)
                ]),
                complete=window_ok,
            )

        def _active(items):
            return [item for item in items if item.get("updated_at") and timeutil.parse_ts(item["updated_at"]) >= since_planning]

        def _linked(items):
            return [item for item in _active(items) if item.get("target_id") and item.get("target_state") == "OPEN"]

        def _links_per_target(items):
            counts: dict[str, int] = {}
            for item in _linked(items):
                counts[str(item["target_id"])] = counts.get(str(item["target_id"]), 0) + 1
            return dict(sorted(counts.items()))

        _derived(obs, "planning.linkage.active_change_requests_count_28d", "count", crs, lambda items: len(_active(items)), complete=window_ok)
        _derived(obs, "planning.linkage.active_change_requests_linked_to_open_target_count_28d", "count", crs, lambda items: len(_linked(items)), complete=window_ok)
        _derived(obs, "planning.linkage.links_per_target_28d", "record", crs, _links_per_target, complete=window_ok)

    issues = obs.get(INV_ISSUES)
    if issues is not None:
        open_ok = _flag(issues, "open_complete")
        window_ok = _flag(issues, "window_complete")

        def _open_issues(items):
            return [item for item in items if item.get("state") == "OPEN"]

        _derived(obs, "forge.issues.open_count", "count", issues, lambda items: len(_open_issues(items)), complete=open_ok)
        _derived(
            obs, "forge.issues.stale_open_count_30d", "count", issues,
            lambda items: len([i for i in _open_issues(items) if timeutil.parse_ts(i["updated_at"]) < stale_issue]),
            complete=open_ok,
        )
        _derived(
            obs, "forge.issues.updated_count_28d", "count", issues,
            lambda items: len([i for i in items if timeutil.parse_ts(i["updated_at"]) >= since_pulse]),
            complete=window_ok,
        )

    _derive_debt(obs, project, issues, observed_at, stale_issue, since_planning)

    branches = obs.get(INV_BRANCHES)
    if branches is not None:
        heads_ok = _flag(branches, "complete") and _flag(branches, "heads_resolved")
        _derived(
            obs, "git.nondefault_branches.stale_count_30d", "count", branches,
            lambda items: len([
                i for i in items if i.get("head_committed_at") and timeutil.parse_ts(i["head_committed_at"]) < stale_branch
            ]),
            complete=heads_ok,
            reason_override=None if heads_ok else "BRANCH_HEADS_UNRESOLVED",
        )

    _derive_planning(obs, project, observed_at, since_planning)
    return obs


def _derive_debt(obs, project, issues, observed_at, stale_issue, since_planning) -> None:
    if "debt.registry.capability" in obs:
        return
    base = {"provider": "config", "collected_at": obs.observed_at, "source_ref": "config:debt", "adapter_version": "config"}
    if project.debt_mapping is None:
        obs.add(Observation(observation_id="debt.registry.capability", status=AVAILABLE, value_type="enum", value="UNCONFIGURED", **base))
        return
    labels = set(project.debt_mapping["labels"])
    mapping_value = {"labels": sorted(labels), "mapping_version": project.debt_mapping["mapping_version"], "source": "issue_labels"}
    obs.add(Observation(observation_id="debt.registry.capability", status=AVAILABLE, value_type="enum", value="CONFIGURED", **base))
    obs.add(Observation(observation_id="debt.mapping", status=AVAILABLE, value_type="record", value=mapping_value, **base))
    if issues is None:
        obs.add(Observation(observation_id="debt.items.open_count", status="UNKNOWN", value_type="count", reason_code="ISSUES_NOT_COLLECTED", **base))
        return

    def _mapped(item):
        return bool(labels.intersection(item.get("labels") or []))

    open_ok = _flag(issues, "open_complete")
    window_ok = _flag(issues, "window_complete")
    _derived(
        obs, "debt.items.open_count", "count", issues,
        lambda items: len([i for i in items if i.get("state") == "OPEN" and _mapped(i)]),
        complete=open_ok, extra_sources=["debt.mapping"],
    )
    _derived(
        obs, "debt.items.open_stale_count_30d", "count", issues,
        lambda items: len([i for i in items if i.get("state") == "OPEN" and _mapped(i) and timeutil.parse_ts(i["updated_at"]) < stale_issue]),
        complete=open_ok, extra_sources=["debt.mapping"],
    )
    _derived(
        obs, "debt.items.closed_count_28d", "count", issues,
        lambda items: len([
            i for i in items if i.get("state") == "CLOSED" and _mapped(i) and i.get("closed_at") and timeutil.parse_ts(i["closed_at"]) >= since_planning
        ]),
        complete=window_ok, extra_sources=["debt.mapping"],
    )


def _derive_planning(obs, project, observed_at, since_planning) -> None:
    if "planning.explicit_targets.capability" in obs:
        return
    horizon_edge = timeutil.minus_days(observed_at, -PLANNING["frame_days"])
    base = {"provider": "config", "collected_at": obs.observed_at, "source_ref": "config:planning", "adapter_version": "config"}
    if project.planning_source == "none":
        obs.add(Observation(observation_id="planning.explicit_targets.capability", status=AVAILABLE, value_type="enum", value="UNSUPPORTED", **base))
        return
    targets = obs.get(INV_TARGETS)
    if targets is None:
        obs.add(Observation(observation_id="planning.explicit_targets.capability", status="UNKNOWN", value_type="enum", reason_code="TARGETS_NOT_COLLECTED", **base))
        return
    if not targets.good:
        obs.add(
            Observation(
                observation_id="planning.explicit_targets.capability",
                status=targets.status if targets.status not in VALUE_BEARING else PARTIAL,
                value_type="enum",
                value="SUPPORTED" if targets.status == PARTIAL else None,
                reason_code=targets.reason_code or "TARGETS_INCOMPLETE",
                provider=targets.provider, collected_at=targets.collected_at,
                source_ref=f"derived:{INV_TARGETS}", adapter_version=targets.adapter_version, freshness=targets.freshness,
            )
        )
        return
    items = list(targets.value)
    capability = "SUPPORTED" if items else "SUPPORTED_UNUSED"
    obs.add(
        Observation(
            observation_id="planning.explicit_targets.capability", status=AVAILABLE, value_type="enum", value=capability,
            provider=targets.provider, collected_at=targets.collected_at, source_ref=f"derived:{INV_TARGETS}",
            adapter_version=targets.adapter_version, freshness=targets.freshness, evidence_ref={"derived_from": [INV_TARGETS]},
        )
    )
    open_items = [i for i in items if i.get("state") == "OPEN"]
    future = [i for i in open_items if i.get("due_at") and timeutil.parse_ts(i["due_at"]) > observed_at]
    beyond = [i for i in future if timeutil.parse_ts(i["due_at"]) > horizon_edge]
    _derived(obs, "planning.explicit_targets.open_count", "count", targets, lambda _: len(open_items))
    _derived(obs, "planning.explicit_targets.open_with_future_boundary_count", "count", targets, lambda _: len(future))
    _derived(obs, "planning.explicit_targets.open_beyond_28d_count", "count", targets, lambda _: len(beyond))
    if future:
        nearest = min(int((timeutil.parse_ts(i["due_at"]) - observed_at).total_seconds() // 86400) for i in future)
        _derived(obs, "planning.explicit_targets.nearest_future_boundary_days", "duration", targets, lambda _: nearest)
