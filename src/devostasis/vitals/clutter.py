"""CLUTTER: unresolved stale work inventory and branch residue (rule ``clutter.bands.v1``).

Clutter measures attention burden, not value. Closing valid work only to
improve Clutter is a known gaming path, so the band stays descriptive and the
counts stay visible.

Rule version 1 adopts the accepted incomplete-evidence contract
``PV-CLUTTER-INCOMPLETE-001`` (accepted by ``PV-REV-CLUTTER-INCOMPLETE-001``,
cases ``CLU-INCOMPLETE-01..20``) and its reconciliation of issue #26
(``PV-ISSUE-026-RECONCILE-001``) on top of the unchanged V1.1 band table. No
threshold or window moved.

* Complete, fresh evidence classifies exactly, as it always did.
* An explicitly ``UNAVAILABLE`` optional component (issues, branches) or a
  ``PARTIAL`` count-bearing component that carries a trustworthy observed
  subset makes the cell *incomplete*. The band is then a confirmed burden
  floor built only from facts omitted records cannot erase: observed stale
  work counts, classified stale branch counts, and the stale-work ratio only
  when every open and stale count of the issue and change-request domain is
  complete. A ``HEAVY`` floor is ``DEGRADED / HEAVY / EXACT``, because the
  terminal band is invariant under any completion; ``CLUTTERED`` and
  ``LIGHT`` floors are ``DEGRADED`` lower bounds with a conservative
  ``possible_bands`` superset; a floor of nothing is ``UNKNOWN`` with no band.
  Incomplete evidence is never positive emptiness, so it is never ``CLEAN``.
* A stale branch is residue only when it is known to be one (permanent case
  T7). A complete count whose retention semantics are ``UNCLASSIFIED`` is an
  upper bound (``CONSERVATIVE_UPPER_BOUND``,
  ``CLUTTER_BRANCH_PURPOSE_UNCLASSIFIED``), and an unclassified count never
  proves a floor. A ``PARTIAL`` branch count proves a floor only with
  explicit complete, fresh ``CLASSIFIED`` retention semantics (issue #26): an
  inventory that declares none is read as it always was when the count is
  complete, and cannot establish a floor when it is not.
* ``FORBIDDEN``, ``UNKNOWN``, ``ERROR`` and stale components, a required
  change-request component that is neither complete nor a trustworthy
  subset, and a ``PARTIAL`` count without a value stay ``UNKNOWN``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..canonical import ratio
from ..observations import AVAILABLE, FRESH, PARTIAL, UNAVAILABLE, ObservationSet
from ..policy import CLUTTER
from .common import (
    EVAL_AVAILABLE,
    EVAL_DEGRADED,
    EVAL_UNKNOWN,
    SEM_EXACT,
    SEM_LOWER,
    SEM_SUPERSET,
    SEM_UPPER,
    VitalResult,
    as_int,
    input_meta,
    unknown_result,
)

VITAL_ID = "clutter"
VITAL_VERSION = "PV-VITALS-V1-002/clutter"
RULE_ID = "clutter.bands.v1"
INCOMPLETE_RULE = "PV-CLUTTER-INCOMPLETE-001"
BRANCH_CAP_RULE = "PV-ISSUE-026-RECONCILE-001"
BANDS = ["CLEAN", "LIGHT", "CLUTTERED", "HEAVY"]

ISSUES_OPEN = "forge.issues.open_count"
ISSUES_STALE = "forge.issues.stale_open_count_30d"
CR_OPEN = "forge.change_requests.open_count"
CR_STALE = "forge.change_requests.stale_open_count_14d"
BRANCHES_STALE = "git.nondefault_branches.stale_count_30d"
BRANCHES_RETENTION = "git.nondefault_branches.retention_semantics"
IDS = [ISSUES_OPEN, ISSUES_STALE, CR_OPEN, CR_STALE, BRANCHES_STALE]

RETENTION_CLASSIFIED = "CLASSIFIED"
RETENTION_UNCLASSIFIED = "UNCLASSIFIED"
RETENTIONS = (RETENTION_CLASSIFIED, RETENTION_UNCLASSIFIED)

PURPOSE_UNCLASSIFIED = "CLUTTER_BRANCH_PURPOSE_UNCLASSIFIED"
INCOMPLETE_COMPONENT = "CLUTTER_INCOMPLETE_COMPONENT"
CONFIRMED_FLOOR = "CLUTTER_CONFIRMED_BURDEN_FLOOR"
RATIO_NOT_PROOF = "CLUTTER_RATIO_NOT_PROOF_INCOMPLETE_DENOMINATOR"
BRANCH_FLOOR_NOT_PROVEN = "CLUTTER_BRANCH_FLOOR_NOT_PROVEN"

# Acquisition classes of one component, in the sense of the accepted contract.
COMPLETE = "COMPLETE"
INCOMPLETE_PARTIAL = "PARTIAL"
INCOMPLETE_UNAVAILABLE = "UNAVAILABLE"
UNRESOLVED = "UNRESOLVED"

FLOOR_NONE = "NONE"

SHARED = ["FORGE_INVENTORY", "BRANCH_RESIDUE"]
GROUPS = ["CLUTTER_FLOW_FORGE"]


def classify(stale_work: int, tracked_open: int, stale_branches: int | None) -> str:
    branches = stale_branches or 0
    heavy_num, heavy_den = CLUTTER["heavy_ratio"]
    clut_num, clut_den = CLUTTER["cluttered_ratio"]
    ratio_ok = tracked_open >= CLUTTER["ratio_min_tracked"]
    if (
        stale_work >= CLUTTER["heavy_stale_work"]
        or (ratio_ok and stale_work * heavy_den >= tracked_open * heavy_num)
        or branches >= CLUTTER["heavy_stale_branches"]
    ):
        return "HEAVY"
    if (
        stale_work >= CLUTTER["cluttered_stale_work"]
        or (ratio_ok and stale_work * clut_den >= tracked_open * clut_num)
        or branches >= CLUTTER["cluttered_stale_branches"]
    ):
        return "CLUTTERED"
    if stale_work > 0 or branches > 0:
        return "LIGHT"
    return "CLEAN"


def confirmed_burden_floor(stale_work_lb: int, tracked_open: int, stale_branch_lb: int, ratio_domain_complete: bool) -> str:
    """The most burdensome predicate the authoritative facts prove (section 3.4 of the contract).

    ``stale_work_lb`` and ``stale_branch_lb`` are lower bounds omitted records
    cannot erase; the ratio predicates are admitted only when the whole issue
    and change-request domain is complete, because a denominator that can
    still grow proves nothing. ``NONE`` is deliberately not ``CLEAN``.
    """
    band = classify(stale_work_lb, tracked_open if ratio_domain_complete else 0, stale_branch_lb)
    return FLOOR_NONE if band == "CLEAN" else band


@dataclass
class Component:
    """One Clutter component and how it was acquired."""

    name: str
    ids: tuple[str, ...]
    kind: str
    values: dict[str, int] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    @property
    def incomplete(self) -> bool:
        return self.kind in (INCOMPLETE_PARTIAL, INCOMPLETE_UNAVAILABLE)

    def value(self, oid: str) -> int:
        return self.values[oid]


def _acquire(obs: ObservationSet, name: str, ids: tuple[str, ...]) -> Component:
    """Classify a component: complete, a trustworthy partial subset, explicitly unavailable, or unresolved."""
    items = [obs.get(oid) for oid in ids]
    if all(item is not None and item.good for item in items):
        return Component(name, ids, COMPLETE, {oid: as_int(item.value) for oid, item in zip(ids, items)})
    if all(item is not None and item.status == UNAVAILABLE for item in items):
        return Component(name, ids, INCOMPLETE_UNAVAILABLE, {}, [item.reason_code or "UNAVAILABLE" for item in items])
    subset = all(
        item is not None and item.status in (AVAILABLE, PARTIAL) and item.freshness == FRESH and item.has_value for item in items
    )
    if subset and any(item.status == PARTIAL for item in items):
        reasons = [item.reason_code or "INCOMPLETE" for item in items if item.status == PARTIAL]
        return Component(name, ids, INCOMPLETE_PARTIAL, {oid: as_int(item.value) for oid, item in zip(ids, items)}, reasons)
    return Component(name, ids, UNRESOLVED, {}, [f"{obs.status_of(oid)}/{obs.freshness_of(oid)}" for oid in ids])


def _retention(obs: ObservationSet) -> tuple[str | None, bool]:
    """``(semantics, resolved)``: the declared retention semantics, or None when undeclared; resolved is False when declared but unreadable."""
    item = obs.get(BRANCHES_RETENTION)
    if item is None:
        return None, True
    if item.good and item.value in RETENTIONS:
        return item.value, True
    return None, False


def _components(cr: Component, issues: Component, branches: Component) -> dict:
    return {
        "change_requests": {"open": cr.values.get(CR_OPEN), "stale_14d": cr.values.get(CR_STALE), "acquisition": cr.kind},
        "issues": None if issues.kind == INCOMPLETE_UNAVAILABLE else {"open": issues.values.get(ISSUES_OPEN), "stale_30d": issues.values.get(ISSUES_STALE), "acquisition": issues.kind},
        "branches": None if branches.kind == INCOMPLETE_UNAVAILABLE else {"stale_30d": branches.values.get(BRANCHES_STALE), "acquisition": branches.kind},
    }


def _result(obs: ObservationSet, band: str | None, status: str, semantics: str | None, possible: list[str] | None, derived: dict, diagnostics: list[str], explanation: str) -> VitalResult:
    return VitalResult(
        vital_id=VITAL_ID,
        vital_version=VITAL_VERSION,
        rule_id=RULE_ID,
        band=band,
        evaluation_status=status,
        band_semantics=semantics,
        possible_bands=possible,
        inputs=input_meta(obs, IDS + [BRANCHES_RETENTION]),
        derived=derived,
        shared_signal_groups=SHARED,
        dependency_group_ids=GROUPS,
        diagnostics=diagnostics,
        explanation=explanation,
    )


def evaluate(obs: ObservationSet) -> VitalResult:
    cr = _acquire(obs, "change_requests", (CR_OPEN, CR_STALE))
    if cr.kind in (UNRESOLVED, INCOMPLETE_UNAVAILABLE):
        # Required evidence: wholly unavailable, forbidden, errored, stale or
        # valueless change-request counts leave nothing to bound.
        diagnostics = [f"MISSING_REQUIRED:{oid}:{obs.status_of(oid)}/{obs.freshness_of(oid)}" for oid in cr.ids if not obs.is_good(oid)]
        return unknown_result(VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS, diagnostics, SHARED, GROUPS)
    issues = _acquire(obs, "issues", (ISSUES_OPEN, ISSUES_STALE))
    if issues.kind == UNRESOLVED:
        return unknown_result(VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS, [f"COMPONENT_UNRESOLVED:issues:{obs.status_of(ISSUES_OPEN)}/{obs.status_of(ISSUES_STALE)}"], SHARED, GROUPS)
    branches = _acquire(obs, "branches", (BRANCHES_STALE,))
    retention, retention_resolved = _retention(obs)
    if branches.kind == UNRESOLVED or not retention_resolved:
        return unknown_result(
            VITAL_ID, VITAL_VERSION, RULE_ID, obs, IDS,
            [f"COMPONENT_UNRESOLVED:branches:{obs.status_of(BRANCHES_STALE)}/{obs.freshness_of(BRANCHES_STALE)}"]
            + ([] if retention_resolved else [f"COMPONENT_UNRESOLVED:branch_retention:{obs.status_of(BRANCHES_RETENTION)}/{obs.freshness_of(BRANCHES_RETENTION)}"]),
            SHARED, GROUPS,
        )

    if not any(component.incomplete for component in (cr, issues, branches)):
        return _complete(obs, cr, issues, branches, retention)
    return _incomplete(obs, cr, issues, branches, retention)


def _complete(obs: ObservationSet, cr: Component, issues: Component, branches: Component, retention: str | None) -> VitalResult:
    """Every component complete and fresh: the exact V1.1 evaluation, with T7 on top."""
    cr_open, cr_stale = cr.value(CR_OPEN), cr.value(CR_STALE)
    issues_open, issues_stale = issues.value(ISSUES_OPEN), issues.value(ISSUES_STALE)
    stale_branches = branches.value(BRANCHES_STALE)
    tracked_open = cr_open + issues_open
    stale_work = cr_stale + issues_stale
    band = classify(stale_work, tracked_open, stale_branches)
    derived = {
        "tracked_open_count": tracked_open,
        "stale_work_count": stale_work,
        "stale_work_ratio": ratio(stale_work, tracked_open) if tracked_open > 0 else None,
        "stale_branch_count": stale_branches,
        "components": _components(cr, issues, branches),
    }
    if retention is not None:
        derived["branch_retention_semantics"] = retention
    explanation = f"{stale_work} stale work items out of {tracked_open} tracked open items; {stale_branches} stale non-default branches."
    if retention == RETENTION_UNCLASSIFIED and stale_branches > 0:
        # T7: the count is an upper bound on residue, because none of these
        # branches is known to be waste. Every classified residue from none to
        # all of them is admissible, and each is classified with the work items.
        reachable = {classify(stale_work, tracked_open, residue) for residue in range(0, stale_branches + 1)}
        possible = [candidate for candidate in BANDS if candidate in reachable]
        derived["stale_branch_count_semantics"] = "UPPER_BOUND"
        if possible == [band]:
            # The work items alone reach the band the full count reaches: the
            # band is invariant, and only its evidence is degraded.
            return _result(
                obs, band, EVAL_DEGRADED, SEM_EXACT, None, derived, [PURPOSE_UNCLASSIFIED],
                explanation + " The purpose of the stale branches is unclassified, but the work items alone reach this band.",
            )
        return _result(
            obs, band, EVAL_DEGRADED, SEM_UPPER, possible, derived, [PURPOSE_UNCLASSIFIED],
            explanation + " The purpose of the stale branches is unclassified, so the band is an upper bound on the residue.",
        )
    return _result(obs, band, EVAL_AVAILABLE, SEM_EXACT, None, derived, [], explanation)


def _incomplete(obs: ObservationSet, cr: Component, issues: Component, branches: Component, retention: str | None) -> VitalResult:
    """At least one eligible incomplete component: the confirmed burden floor of PV-CLUTTER-INCOMPLETE-001."""
    diagnostics: list[str] = []
    for component in (cr, issues, branches):
        if component.incomplete:
            diagnostics.append(f"{INCOMPLETE_COMPONENT}:{component.name}:{component.kind}")
            diagnostics.append(f"COMPONENT_{component.kind}:{component.name}:{component.reasons[0]}")

    # 3.1 stale-work lower bound and the observed tracked domain.
    stale_work_lb = cr.value(CR_STALE) + (issues.value(ISSUES_STALE) if issues.kind != INCOMPLETE_UNAVAILABLE else 0)
    tracked_open = cr.value(CR_OPEN) + (issues.value(ISSUES_OPEN) if issues.kind != INCOMPLETE_UNAVAILABLE else 0)
    # 3.2 the ratio is proof only over a complete issue+CR domain.
    ratio_domain_complete = cr.kind == COMPLETE and issues.kind == COMPLETE
    if not ratio_domain_complete:
        diagnostics.append(RATIO_NOT_PROOF)

    # 3.3 branch evidence contributes only when the counted residue is known to be residue.
    stale_branches = branches.values.get(BRANCHES_STALE)
    stale_branch_lb = 0
    branch_semantics: str | None = None
    if branches.kind == COMPLETE:
        if retention == RETENTION_UNCLASSIFIED:
            branch_semantics = "UPPER_BOUND"
            if stale_branches > 0:
                diagnostics.append(PURPOSE_UNCLASSIFIED)
        else:
            stale_branch_lb = stale_branches
            branch_semantics = "EXACT"
    elif branches.kind == INCOMPLETE_PARTIAL:
        if retention == RETENTION_CLASSIFIED:
            stale_branch_lb = stale_branches
            branch_semantics = "LOWER_BOUND"
        else:
            branch_semantics = "UPPER_BOUND" if retention == RETENTION_UNCLASSIFIED else "UNPROVEN"
            if stale_branches > 0:
                diagnostics.append(f"{BRANCH_FLOOR_NOT_PROVEN}:{retention or 'UNDECLARED'}")
                if retention == RETENTION_UNCLASSIFIED:
                    diagnostics.append(PURPOSE_UNCLASSIFIED)

    floor = confirmed_burden_floor(stale_work_lb, tracked_open, stale_branch_lb, ratio_domain_complete)
    diagnostics.append(f"{CONFIRMED_FLOOR}:{floor}")

    derived = {
        "tracked_open_count": tracked_open,
        "tracked_open_count_semantics": "EXACT" if ratio_domain_complete else "OBSERVED_SUBSET",
        "stale_work_count": stale_work_lb,
        "stale_work_count_semantics": "EXACT" if ratio_domain_complete else "LOWER_BOUND",
        "stale_work_ratio": ratio(stale_work_lb, tracked_open) if ratio_domain_complete and tracked_open > 0 else None,
        "stale_branch_count": stale_branches,
        "stale_branch_count_semantics": branch_semantics,
        "components": _components(cr, issues, branches),
        "confirmed_burden_floor": floor,
        "confirmed_stale_work_lower_bound": stale_work_lb,
        "confirmed_stale_branch_lower_bound": stale_branch_lb,
        "ratio_domain_complete": ratio_domain_complete,
        "incomplete_components": {component.name: component.kind for component in (cr, issues, branches) if component.incomplete},
        "branch_retention_semantics": retention,
        "incomplete_evidence_rule": INCOMPLETE_RULE,
    }
    incomplete_names = ", ".join(f"{component.name} {component.kind}" for component in (cr, issues, branches) if component.incomplete)
    facts = f"{stale_work_lb} stale work items were observed out of {tracked_open} tracked open items"
    if stale_branches is not None:
        facts += f", and {stale_branches} stale non-default branches"
    facts += f"; evidence is incomplete ({incomplete_names})."

    if floor == FLOOR_NONE:
        return _result(
            obs, None, EVAL_UNKNOWN, None, None, derived, diagnostics,
            facts + " No stale residue is proven, and incomplete evidence is never positive emptiness, so no band is claimed.",
        )
    if floor == "HEAVY":
        return _result(
            obs, "HEAVY", EVAL_DEGRADED, SEM_EXACT, None, derived, diagnostics,
            facts + " The observed residue already proves HEAVY, and no completion of the missing evidence can make Clutter less burdensome.",
        )
    possible = ["CLUTTERED", "HEAVY"] if floor == "CLUTTERED" else ["LIGHT", "CLUTTERED", "HEAVY"]
    derived["possible_bands_semantics"] = SEM_SUPERSET
    return _result(
        obs, floor, EVAL_DEGRADED, SEM_LOWER, possible, derived, diagnostics,
        facts + f" The observed residue proves at least {floor}; the missing evidence could add burden but cannot remove it.",
    )
