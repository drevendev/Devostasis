"""Offline GitLab native outcome boundary under PV-CI-NORM-001.

This pure normalizer is not a collector and cannot establish history coverage.
Pipeline ids remain distinct; an in-place retry keeps its pipeline identity.
"""

from .github_ci import (VERIFY_PASS, VERIFY_FAIL, VERIFY_UNRESOLVED,
                        NON_VERIFY_TERMINAL, NOT_EXECUTED, UNKNOWN)

OUTCOME_MAP_VERSION = "devostasis.ci-outcomes.gitlab.v1"
OUTCOME_MAP = {"success": VERIFY_PASS, "failed": VERIFY_FAIL,
               "canceled": NON_VERIFY_TERMINAL, "skipped": NOT_EXECUTED,
               "manual": NOT_EXECUTED, "scheduled": NOT_EXECUTED}
NONTERMINAL = frozenset({"created", "waiting_for_resource", "preparing", "waiting_for_callback",
                        "pending", "running", "canceling"})


def normalize_outcome(status):
    return VERIFY_UNRESOLVED if status in NONTERMINAL else OUTCOME_MAP.get(status, UNKNOWN)
