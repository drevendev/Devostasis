"""Seven-Vital snapshot semantics (V1-01, V1-02, V1-06, V1-12) and determinism (G4)."""

from devostasis import canonical
from devostasis.contracts import CORE_VITAL_IDS
from devostasis.vitals import build_snapshot, evaluate_all
from helpers import (
    clutter_inputs,
    debt_inputs,
    direction_inputs,
    finalize,
    flow_inputs,
    full_inputs,
    integrity_inputs,
    obs_set,
    planning_inputs,
    pulse_inputs,
)


def _bands(obs):
    return {r.vital_id: (r.band, r.evaluation_status) for r in evaluate_all(obs)}


def test_v1_01_empty_repository_with_complete_observations():
    obs = obs_set()
    pulse_inputs(obs, 0, 0, 0, 0)
    flow_inputs(obs, 0, 0)
    clutter_inputs(obs, 0, 0, 0, 0, 0)
    integrity_inputs(obs, False, [])
    planning_inputs(obs, "SUPPORTED_UNUSED")
    direction_inputs(obs, 0)
    debt_inputs(obs, "UNCONFIGURED")
    bands = _bands(obs)
    assert bands == {
        "horizon": ("UNDECLARED", "AVAILABLE"),
        "clutter": ("CLEAN", "AVAILABLE"),
        "direction": ("NO_ACTIVE_CHANGE", "AVAILABLE"),
        "flow": ("NO_QUEUE", "AVAILABLE"),
        "integrity": ("UNINSTRUMENTED", "AVAILABLE"),
        "debt": ("UNINSTRUMENTED", "AVAILABLE"),
        "pulse": ("DORMANT", "AVAILABLE"),
    }


def test_v1_02_commits_without_change_requests_or_targets():
    obs = obs_set()
    pulse_inputs(obs, 12, 5, 0, 0)
    flow_inputs(obs, 0, 0)
    clutter_inputs(obs, 0, 0, 0, 0, 0)
    integrity_inputs(obs, True, [])
    planning_inputs(obs, "SUPPORTED_UNUSED")
    direction_inputs(obs, 0)
    debt_inputs(obs, "UNCONFIGURED")
    bands = _bands(obs)
    assert bands["pulse"][0] == "STEADY" and bands["flow"][0] == "NO_QUEUE"
    assert bands["direction"][0] == "NO_ACTIVE_CHANGE" and bands["horizon"][0] == "UNDECLARED"


def test_v1_06_clear_debt_can_coexist_with_heavy_clutter():
    obs = obs_set()
    full_inputs(obs)
    obs.replace(type(obs.get("forge.issues.open_count"))(**dict(obs.get("forge.issues.open_count").to_dict(), value=60)))
    obs.replace(type(obs.get("forge.issues.stale_open_count_30d"))(**dict(obs.get("forge.issues.stale_open_count_30d").to_dict(), value=40)))
    obs.replace(type(obs.get("debt.items.open_count"))(**dict(obs.get("debt.items.open_count").to_dict(), value=0)))
    bands = _bands(obs)
    assert bands["debt"][0] == "CLEAR" and bands["clutter"][0] == "HEAVY"


def test_v1_12_snapshot_carries_dependency_metadata_and_no_aggregate():
    obs = finalize(full_inputs(obs_set()))
    snapshot = build_snapshot(obs)
    assert [v["vital_id"] for v in snapshot["vitals"]] == list(CORE_VITAL_IDS)
    for vital in snapshot["vitals"]:
        assert vital["dependency_group_ids"], vital["vital_id"]
    assert not any(key in snapshot for key in ("score", "health", "overall"))


def test_g4_same_observations_produce_identical_snapshot_digest():
    first = build_snapshot(full_inputs(obs_set()))
    second = build_snapshot(full_inputs(obs_set()))
    assert canonical.digest(first) == canonical.digest(second)


def test_unknown_in_one_vital_never_fabricates_another():
    obs = obs_set()
    full_inputs(obs)
    obs.replace(type(obs.get("ci.configured"))(**dict(obs.get("ci.configured").to_dict(), status="ERROR", value=None, reason_code="PROVIDER_ERROR")))
    obs.replace(type(obs.get("ci.revision_verdicts_14d"))(**dict(obs.get("ci.revision_verdicts_14d").to_dict(), status="ERROR", value=None, reason_code="PROVIDER_ERROR")))
    bands = _bands(obs)
    assert bands["integrity"] == (None, "UNKNOWN")
    assert bands["pulse"][0] == "STEADY" and bands["flow"][0] == "MOVING"
