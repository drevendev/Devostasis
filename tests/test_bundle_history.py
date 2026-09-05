"""Bundle identity, verification, immutability, comparison states and activity (ART-*, RPT-*)."""

import json

import pytest

from devostasis import canonical
from devostasis.bundle import BundleError, verify_dir, verify_members
from devostasis.config import single_project
from devostasis.history import FilesystemHistoryStore, ImmutabilityError
from devostasis.runner import build_from_observations
from helpers import OBSERVED_AT, add, finalize, full_inputs, obs_set


def _project(**overrides):
    return single_project("acme/widget", config_version="1", **overrides)


def _obs(observed_at=OBSERVED_AT):
    return full_inputs(obs_set(observed_at))


def test_art_01_first_bundle_is_baseline_without_fabricated_delta(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    bundle = build_from_observations(_project(), _obs(), store)
    assert bundle.manifest["comparison_status"] == "BASELINE" and bundle.manifest["previous_bundle_id"] is None
    delta = json.loads(bundle.members["delta.json"])
    assert {row["transition_class"] for row in delta["vitals"]} == {"BASELINE"}
    assert all(row["metric_deltas"] == {} for row in delta["vitals"])


def test_art_02_and_art_14_identity_is_reproducible_across_builds(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    first = build_from_observations(_project(), _obs(), store)
    second = build_from_observations(_project(), _obs(), store)
    assert first.bundle_id == second.bundle_id
    assert first.members == second.members
    preimage = first.manifest["identity_preimage"]
    assert canonical.sha256_hex(canonical.canonical_bytes(preimage)) == first.bundle_id


def test_art_13_and_art_22_preimage_excludes_post_identity_members(tmp_path):
    bundle = build_from_observations(_project(), _obs(), FilesystemHistoryStore(tmp_path))
    preimage = bundle.manifest["identity_preimage"]
    assert "members" not in preimage and "bundle_id" not in preimage and "run_meta" not in preimage
    assert preimage["effective_config_digest"] == bundle.manifest["effective_config_digest"]
    assert set(preimage) >= {"snapshot_digest", "delta_digest", "activity_digest", "source_receipts_digest", "observed_at"}


def test_art_16_observed_at_is_identity_bearing(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    a = build_from_observations(_project(), _obs("2026-09-05T12:00:00Z"), store)
    b = build_from_observations(_project(), _obs("2026-09-05T12:00:01Z"), store)
    assert a.bundle_id != b.bundle_id


def test_art_17_config_change_changes_bundle_id(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    a = build_from_observations(_project(activity={"list_cap": 50}), _obs(), store)
    b = build_from_observations(_project(activity={"list_cap": 5}), _obs(), store)
    assert a.bundle_id != b.bundle_id and a.manifest["config_version"] == b.manifest["config_version"]


def test_art_18_enabled_html_without_renderer_fails_closed(tmp_path):
    with pytest.raises(BundleError):
        build_from_observations(_project(report_html=True), _obs(), FilesystemHistoryStore(tmp_path))


def test_art_20_21_12_persisted_bundle_verifies_from_its_own_contents(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    bundle = build_from_observations(_project(), _obs(), store)
    path = store.commit(bundle, bundle.bands())
    assert verify_dir(path) == []
    stored = (path / "effective-config.json").read_bytes()
    assert canonical.digest_bytes(stored) == bundle.manifest["effective_config_digest"]
    assert canonical.canonical_bytes(json.loads(stored)) == stored


def test_tampering_is_detected(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    bundle = build_from_observations(_project(), _obs(), store)
    path = store.commit(bundle, bundle.bands())
    report = path / "report.md"
    report.write_bytes(report.read_bytes() + b"\nedited\n")
    problems = verify_dir(path)
    assert any("report.md" in p for p in problems)
    snapshot = json.loads((path / "snapshot.json").read_text("utf-8"))
    snapshot["vitals"][0]["band"] = "DECLARED"
    (path / "snapshot.json").write_text(json.dumps(snapshot), "utf-8")
    assert any("snapshot.json digest mismatch" in p for p in verify_dir(path))


def test_art_07_immutability(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    bundle = build_from_observations(_project(), _obs(), store)
    store.commit(bundle, bundle.bands())
    store.put_immutable(bundle)
    bundle.members["report.md"] = b"different"
    with pytest.raises(ImmutabilityError):
        store.put_immutable(bundle)


def test_second_run_is_comparable_with_unchanged_and_changed_transitions(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    first = build_from_observations(_project(), _obs("2026-09-05T12:00:00Z"), store)
    store.commit(first, first.bands())
    later = obs_set("2026-09-06T12:00:00Z")
    full_inputs(later)
    later.replace(type(later.get("forge.change_requests.open_count"))(**dict(later.get("forge.change_requests.open_count").to_dict(), value=12)))
    second = build_from_observations(_project(), later, store)
    assert second.manifest["comparison_status"] == "COMPARABLE" and second.manifest["previous_bundle_id"] == first.bundle_id
    delta = json.loads(second.members["delta.json"])
    rows = {row["vital_id"]: row for row in delta["vitals"]}
    assert rows["flow"]["transition_class"] == "CHANGED" and rows["flow"]["previous_band"] == "MOVING" and rows["flow"]["current_band"] == "CONGESTED"
    assert rows["flow"]["metric_deltas"]["open_count"] == {"previous": 2, "current": 12, "change": 10}
    assert rows["pulse"]["transition_class"] == "UNCHANGED"
    activity = json.loads(second.members["activity.json"])
    assert activity["interval"] == {"start": "2026-09-05T12:00:00Z", "end": "2026-09-06T12:00:00Z", "basis": "PREVIOUS_BUNDLE", "exclusive_start": True}


def test_observability_transitions(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    first_obs = _obs("2026-09-05T12:00:00Z")
    first_obs.replace(type(first_obs.get("ci.revision_verdicts_14d"))(**dict(first_obs.get("ci.revision_verdicts_14d").to_dict(), status="ERROR", value=None, reason_code="PROVIDER_ERROR")))
    finalize(first_obs)
    first = build_from_observations(_project(), first_obs, store)
    store.commit(first, first.bands())
    second = build_from_observations(_project(), _obs("2026-09-06T12:00:00Z"), store)
    rows = {row["vital_id"]: row for row in json.loads(second.members["delta.json"])["vitals"]}
    assert rows["integrity"]["transition_class"] == "OBSERVABILITY_GAINED"
    activity = json.loads(second.members["activity.json"])
    assert activity["classes"]["CAPABILITY_CHANGE"]["count"] == 1


def test_rpt_3_history_gap_keeps_current_snapshot_and_infers_no_change(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    first = build_from_observations(_project(), _obs("2026-09-05T12:00:00Z"), store)
    path = store.commit(first, first.bands())
    (store.project_dir(first.project_key) / "latest" / "snapshot.json").unlink()
    second = build_from_observations(_project(), _obs("2026-09-06T12:00:00Z"), store)
    assert second.manifest["comparison_status"] == "HISTORY_GAP"
    assert second.manifest["previous_bundle_id"] == first.bundle_id
    delta = json.loads(second.members["delta.json"])
    assert {row["transition_class"] for row in delta["vitals"]} == {"INCOMPARABLE"}
    assert json.loads(second.members["snapshot.json"])["vitals"][0]["band"] == "EXTENDED"
    assert path.exists()


def test_art_04_rpt_10_semantic_config_change_is_incomparable(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    first = build_from_observations(_project(), _obs("2026-09-05T12:00:00Z"), store)
    store.commit(first, first.bands())
    second = build_from_observations(_project(debt={"labels": ["debt"], "mapping_version": "1"}), _obs("2026-09-06T12:00:00Z"), store)
    assert second.manifest["comparison_status"] == "INCOMPARABLE"
    delta = json.loads(second.members["delta.json"])
    assert "SEMANTIC_CONFIG_CHANGED" in delta["incomparable_reasons"]
    assert {row["transition_class"] for row in delta["vitals"]} == {"INCOMPARABLE"}
    store.commit(second, second.bands())
    index = store.read_index(second.project_key)
    assert [entry["bundle_id"] for entry in index["bundles"]] == [first.bundle_id, second.bundle_id]


def test_art_06_neutral_rendering_of_fully_linked_and_present(tmp_path):
    obs = obs_set()
    full_inputs(obs)
    obs.replace(type(obs.get("planning.linkage.active_change_requests_linked_to_open_target_count_28d"))(**dict(obs.get("planning.linkage.active_change_requests_linked_to_open_target_count_28d").to_dict(), value=10)))
    bundle = build_from_observations(_project(), obs, FilesystemHistoryStore(tmp_path))
    report = bundle.members["report.md"].decode("utf-8")
    assert "FULLY_LINKED" in report and "PRESENT" in report
    for banned in ("ALIGNED", "ON_TRACK", "HEALTHY", "UNHEALTHY", "score"):
        assert banned not in report


def test_verify_members_reports_missing_manifest():
    assert verify_members({}) == ["manifest.json missing"]


def test_activity_disabled_marker_enters_identity(tmp_path):
    store = FilesystemHistoryStore(tmp_path)
    enabled = build_from_observations(_project(), _obs(), store)
    disabled = build_from_observations(_project(activity={"enabled": False}), _obs(), store)
    assert "activity.json" not in disabled.members
    assert disabled.manifest["identity_preimage"]["activity_digest"] == "ACTIVITY_DISABLED"
    assert enabled.bundle_id != disabled.bundle_id
