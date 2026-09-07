"""Normative band ordering per Vital (PV-BAND-ORDER-001, devostasis.band-order.v1).

An order says one band of *one* Vital is better than another band of the same
Vital, and nothing else. It is never an order across Vitals, never an order
across projects, and never a step towards an aggregate: the seven Vitals
measure different phenomena over shared signals, so "better Clutter" and
"better Flow" are not commensurable and are never added up.

Three Vitals declare an order:

* **Clutter** ``CLEAN > LIGHT > CLUTTERED > HEAVY``, a single transitive chain.
* **Flow** ``MOVING > CONGESTED > GRIDLOCKED`` for a live queue. ``NO_QUEUE``
  is descriptive, not positive, and is incomparable with all of them: a queue
  that disappeared is a different situation, not a better one.
* **Integrity** ``CLEAN > FLAKY > FAILING`` and ``SPARSE > SPARSE_MIXED``, two
  separate families. There is no order between the families (a small sample
  that passed is not comparable with an established one) and none with the
  evidence states ``UNINSTRUMENTED``, ``NO_RECENT_RUNS`` and
  ``NO_DECISIVE_RUNS``, which describe what could be observed rather than what
  verification said.

Pulse, Horizon, Direction and Debt declare no order at all. More activity is
not better activity, ``EXTENDED`` is not better than ``VISIBLE``,
``FULLY_LINKED`` is neutral exact traceability and ``PRESENT`` debt is a fact
about a register, not a verdict. Every unequal transition of those four stays
``CHANGED``.

Gauges never establish an order: they are a presentation normalization
(``devostasis.gauge.v1``) and movement inside one band is not a transition.
"""

from __future__ import annotations

BAND_ORDER_CONTRACT = "PV-BAND-ORDER-001"
BAND_ORDER_VERSION = "devostasis.band-order.v1"

IMPROVED = "IMPROVED"
WORSENED = "WORSENED"

# Best band first inside each family; families of one Vital are unordered
# relative to each other. A band absent from every family of its Vital is
# ordered against nothing.
ORDER_FAMILIES: dict[str, tuple[tuple[str, ...], ...]] = {
    "clutter": (("CLEAN", "LIGHT", "CLUTTERED", "HEAVY"),),
    "flow": (("MOVING", "CONGESTED", "GRIDLOCKED"),),
    "integrity": (("CLEAN", "FLAKY", "FAILING"), ("SPARSE", "SPARSE_MIXED")),
}

# Reason codes recorded on the delta row, so a reader can always tell why an
# order did or did not apply without knowing this table by heart.
APPLIED = "BAND_ORDER_APPLIED"
NOT_DECLARED = "BAND_ORDER_NOT_DECLARED"
INCOMPARABLE_BANDS = "BAND_ORDER_INCOMPARABLE"
NOT_ELIGIBLE = "BAND_ORDER_NOT_ELIGIBLE"

EVALUATION_NOT_AVAILABLE = "EVALUATION_NOT_AVAILABLE"
BAND_SEMANTICS_NOT_EXACT = "BAND_SEMANTICS_NOT_EXACT"

EXACT = "EXACT"
AVAILABLE = "AVAILABLE"


def declares_order(vital_id: str) -> bool:
    """Whether this Vital declares any order at all."""
    return vital_id in ORDER_FAMILIES


def ordered_bands(vital_id: str) -> tuple[str, ...]:
    """Every band of the Vital that sits in some family, in declaration order."""
    return tuple(band for family in ORDER_FAMILIES.get(vital_id, ()) for band in family)


def position(vital_id: str, band: str | None) -> tuple[int, int] | None:
    """``(family index, rank)`` of a band, rank ascending from the best; None when unordered."""
    if band is None:
        return None
    for family_index, family in enumerate(ORDER_FAMILIES.get(vital_id, ())):
        if band in family:
            return family_index, family.index(band)
    return None


def chain(vital_id: str, band: str | None) -> str | None:
    """The declared family a band belongs to, rendered as ``BEST>...>WORST``."""
    found = position(vital_id, band)
    if found is None:
        return None
    return ">".join(ORDER_FAMILIES[vital_id][found[0]])


def comparable(vital_id: str, previous_band: str | None, current_band: str | None) -> bool:
    """Whether the two bands sit in the same declared family of this Vital."""
    before, after = position(vital_id, previous_band), position(vital_id, current_band)
    return before is not None and after is not None and before[0] == after[0]


def direction(vital_id: str, previous_band: str | None, current_band: str | None) -> str | None:
    """``IMPROVED``, ``WORSENED``, or None when the bands are equal or incomparable.

    This answers only the band question. Whether the *evidence* is exact enough
    for the answer to be emitted is :func:`eligibility_problem`.
    """
    if not comparable(vital_id, previous_band, current_band):
        return None
    before = position(vital_id, previous_band)[1]  # type: ignore[index]
    after = position(vital_id, current_band)[1]  # type: ignore[index]
    if after == before:
        return None
    return IMPROVED if after < before else WORSENED


def eligibility_problem(previous: dict, current: dict) -> str | None:
    """Why exactness forbids ordering this pair, or None when both sides are exact.

    An order compares two *measurements*, so both sides must be positively
    observed and exact. A ``DEGRADED`` band is a bound: the true band could be
    anywhere in ``possible_bands``, and calling a move between bounds an
    improvement would invent evidence (G2).
    """
    for side in (previous, current):
        if side.get("evaluation_status") != AVAILABLE:
            return EVALUATION_NOT_AVAILABLE
    for side in (previous, current):
        if side.get("band_semantics") != EXACT:
            return BAND_SEMANTICS_NOT_EXACT
    return None


def classify(vital_id: str, previous: dict, current: dict) -> tuple[str | None, str]:
    """``(IMPROVED | WORSENED | None, reason code)`` for one changed band pair.

    The reason code is recorded whether or not the order applied, and is
    resolved in a fixed order so the same pair always yields the same code: a
    Vital with no declared order first, then a band pair the order does not
    relate, then evidence that is not exact enough.
    """
    previous_band, current_band = previous.get("band"), current.get("band")
    if not declares_order(vital_id):
        return None, f"{NOT_DECLARED}:{vital_id}"
    if not comparable(vital_id, previous_band, current_band):
        return None, f"{INCOMPARABLE_BANDS}:{previous_band}|{current_band}"
    problem = eligibility_problem(previous, current)
    if problem is not None:
        return None, f"{NOT_ELIGIBLE}:{problem}"
    moved = direction(vital_id, previous_band, current_band)
    if moved is None:
        return None, f"{INCOMPARABLE_BANDS}:{previous_band}|{current_band}"
    return moved, f"{APPLIED}:{chain(vital_id, current_band)}"
