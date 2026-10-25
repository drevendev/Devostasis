"""Version-pinned bridge to isolated, self-contained conformance scenarios.

No case is a pointer to a test name: declared inputs execute the operation and
every literal/negative assertion is checked against its returned checkpoints.
"""

from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

from devostasis import canonical
from devostasis.adapters import github_ci, gitlab_ci
from devostasis.bundle import verify_dir, verify_members
from devostasis.config import single_project
from devostasis.history import FilesystemHistoryStore, HistoryConflictError, ImmutabilityError
from devostasis.observations import Observation
from devostasis.runner import build_from_observations
from devostasis.vitals import build_snapshot, integrity
from helpers import add, finalize, full_inputs, integrity_inputs, obs_set
from ci_surface_bridge import consumer as vital_consumers, revisions as ci_revisions

CONTRACT = "devostasis.conformance-bridge.v1"
BUNDLE_LINEAGE = {"schema": "devostasis.manifest.v2", "artifact_contract_version": "devostasis.bundle.v3",
                  "bundle_identity_contract": "PV-BUNDLE-ID-003", "receipt_identity_contract": "PV-RECEIPT-IDENTITY-003"}


def shape(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"expected fields {sorted(keys)}")


def exact_bundle_lineage(value):
    if any(value.manifest.get(k) != v for k, v in BUNDLE_LINEAGE.items()):
        raise ValueError("bridge does not support this exact canonical bundle lineage")


def native(given, root):
    shape(given, ("variants",))
    result = {}
    for row in given["variants"]:
        shape(row, ("name", "provider", "mapping", "status", "conclusion"))
        if row["name"] in result: raise ValueError("duplicate variant")
        if row["provider"] == "github" and row["mapping"] == github_ci.OUTCOME_MAP_VERSION:
            outcome = github_ci.normalize_outcome(row["status"], row["conclusion"])
        elif row["provider"] == "gitlab" and row["mapping"] == gitlab_ci.OUTCOME_MAP_VERSION:
            if row["conclusion"] is not None: raise ValueError("GitLab has no separate conclusion")
            outcome = gitlab_ci.normalize_outcome(row["status"])
        else:
            raise ValueError("unsupported exact provider normalization lineage")
        # Feed normalized outcomes into the real revision composition too.
        result[row["name"]] = {"outcome": outcome,
            "revision_verdict": github_ci.compose_current([outcome]),
            "decisive": int(outcome in ("VERIFY_PASS", "VERIFY_FAIL")),
            "failed": int(outcome == "VERIFY_FAIL")}
    return result


def independence(given, root):
    shape(given, ("attempts", "sample_semantics"))
    states = given["attempts"]
    if not isinstance(states, list) or not states: raise ValueError("attempts required")
    attempts = [{"run_attempt": n + 1, "status": "completed", "conclusion": value} for n, value in enumerate(states)]
    run = {"id": 700, **attempts[-1]}
    records = github_ci.build_revision_records([{"sha": "one-immutable-revision", "committed_at": "2026-09-04T00:00:00Z"}],
        {"one-immutable-revision": [github_ci.actions_parent(run, attempts[:-1])]})
    obs = obs_set(); integrity_inputs(obs, True, records)
    add(obs, "ci.sample_semantics", given["sample_semantics"], "enum")
    result = integrity.evaluate(obs).to_dict()
    return {"canonical_revision_count": len(records), "result": result}


def multivital(given, root):
    shape(given, ("observation_id", "variants", "inventories"))
    results = {}
    for variant in given["variants"]:
        shape(variant, ("name", "status", "freshness"))
        if variant["name"] in results: raise ValueError("duplicate variant")
        from devostasis.normalize import derive
        obs = obs_set()
        allowed = {"git.default_branch.commits_28d", "forge.change_requests.inventory",
                   "forge.issues.inventory", "git.nondefault_branches.inventory"}
        if set(given["inventories"]) != allowed: raise ValueError("shared inventories must be explicit")
        record_keys = {"git.default_branch.commits_28d": {"sha", "committed_at"},
            "forge.change_requests.inventory": {"number", "state", "created_at", "updated_at", "merged_at"},
            "forge.issues.inventory": {"number", "state", "created_at", "updated_at"},
            "git.nondefault_branches.inventory": {"name", "committed_at"}}
        for oid, rows in given["inventories"].items():
            if not isinstance(rows, list): raise ValueError("inventory must be a list")
            for row in rows: shape(row, record_keys[oid])
            add(obs, oid, deepcopy(rows), "series", coverage={"complete": True, "open_complete": True, "window_complete": True})
        derive(obs, single_project("acme/widget", config_version="1"))
        finalize(obs)
        if given["observation_id"] is not None:
            old = obs.get(given["observation_id"])
            if old is None: raise ValueError("unknown substituted observation")
            value = old.value if variant["status"] in ("AVAILABLE", "PARTIAL") else None
            obs.replace(Observation(**{**old.to_dict(), "value": value, "status": variant["status"], "freshness": variant["freshness"]}))
            finalize(obs)
        elif variant != {"name": "shared", "status": "AVAILABLE", "freshness": "FRESH"}:
            raise ValueError("shared graph does not substitute evidence")
        snapshot = build_snapshot(obs)
        results[variant["name"]] = {"snapshot": snapshot,
            "vitals": {r["vital_id"]: r for r in snapshot["vitals"]},
            "sources": {item.observation_id: item.evidence_ref for item in obs if item.evidence_ref}}
    return results


def bundle(given, root):
    shape(given, ("operation",))
    store = FilesystemHistoryStore(root)
    project = single_project("acme/widget", config_version="1")
    value = build_from_observations(project, full_inputs(obs_set()), store)
    exact_bundle_lineage(value)
    path = store.commit(value)
    before = dict(value.members)
    op = given["operation"]
    if op == "canonical":
        a = canonical.loads('{"a":1,"b":[true,null]}')
        b = canonical.loads(' { "b" : [true, null], "a" : 1 } ')
        return {"same_bytes": canonical.canonical_bytes(a) == canonical.canonical_bytes(b),
            "same_digest": canonical.digest(a) == canonical.digest(b),
            "scalar_differs": canonical.digest(a) != canonical.digest({"a": 2, "b": [True, None]}),
            "type_differs": canonical.digest(a) != canonical.digest({"a": True, "b": [True, None]})}
    if op == "member-forbidden":
        original = Path.read_bytes
        def read(file):
            if file == path / "snapshot.json": raise PermissionError("FORBIDDEN")
            return original(file)
        with patch.object(Path, "read_bytes", read):
            try: problems = verify_dir(path)
            except PermissionError: return {"access": "FORBIDDEN", "verified": False}
        return {"access": "FORBIDDEN", "verified": not problems}
    if op == "receipt":
        content = dict(value.members); content.pop("source-receipts.json", None)
        # Current lineage persists receipt identity in the observation member.
        observations = canonical.loads(content["observations.json"].decode())
        receipt = observations["receipt_identity"]
        resolved = all(item["observation_id"] in receipt["requested_keys"]
                       and item["observation_id"] in receipt["per_key"] for item in observations["observations"]
                       if item["provider"] != "history")
        carrier = next(i for i in observations["observations"] if i["observation_id"] == "ci.revision_history_carried")
        # The internal carrier resolves through its own identity-bearing lineage,
        # not through a provider collection receipt that predates attachment.
        resolved = resolved and carrier["status"] == "UNAVAILABLE" and carrier["reason_code"] == "NO_PREVIOUS_BUNDLE"
        observations["receipt_identity"] = None
        content["observations.json"] = canonical.canonical_bytes(observations)
        problems = verify_members(content)
        return {"original_verified": verify_members(before) == [], "references_resolve": resolved,
                "missing_receipt_verified": problems == [],
                "receipt_binding_rejected": any("RECEIPT_COPY_MISMATCH" in p for p in problems)}
    if op == "public":
        # Verification consumes the persisted members, with all network disabled.
        with patch("urllib.request.urlopen", side_effect=AssertionError("network dependency")):
            return {"verified": verify_dir(path) == [], "report_present": bool((path / "report.md").read_bytes())}
    if op == "private":
        (root / "private-calibration.json").write_text('{"untrusted":"private"}', encoding="utf-8")
        (root / "SNAP.txt").write_text("convenience", encoding="utf-8")
        rebuilt = build_from_observations(project, full_inputs(obs_set()), FilesystemHistoryStore(root / "isolated"))
        return {"same_id": rebuilt.bundle_id == value.bundle_id, "same_members": rebuilt.members == before,
                "verified": verify_dir(path) == []}
    if op == "collision":
        value.members["snapshot.json"] += b" "
        try: store.put_immutable(value)
        except ImmutabilityError:
            return {"collision": True, "unchanged": all((path / name).read_bytes() == data for name, data in before.items())}
        return {"collision": False, "unchanged": False}
    raise ValueError("unsupported bundle operation")


def history(given, root):
    shape(given, ("operation",))
    store = FilesystemHistoryStore(root)
    project = single_project("acme/widget", config_version="1")
    first = build_from_observations(project, full_inputs(obs_set()), store)
    exact_bundle_lineage(first)
    path = store.commit(first)
    key = first.project_key
    second = build_from_observations(project, full_inputs(obs_set("2026-09-06T12:00:00Z")), store)
    op = given["operation"]
    if op == "idempotent":
        original = store.index_path(key).read_bytes()
        store.commit(first)
        second_path = store.put_immutable(first)
        first.members["snapshot.json"] += b" "
        try: store.put_immutable(first)
        except ImmutabilityError: collision = True
        else: collision = False
        return {"same_path": path == second_path, "same_index": original == store.index_path(key).read_bytes(), "collision": collision}
    if op == "failed-commit":
        with patch.object(store, "put_immutable", side_effect=OSError("incomplete immutable commit")):
            try: store.commit(second)
            except OSError: failed = True
            else: failed = False
        return {"failed": failed, "latest_preserved": store.latest(key, "123456").bundle_id == first.bundle_id,
                "first_verified": verify_dir(path) == []}
    if op == "missing-predecessor":
        (path / "snapshot.json").unlink()
        current = build_from_observations(project, full_inputs(obs_set("2026-09-06T12:00:00Z")), store)
        snapshot = canonical.loads(current.members["snapshot.json"].decode())
        delta = canonical.loads(current.members["delta.json"].decode())
        return {"comparison": current.manifest["comparison_status"], "snapshot_present": len(snapshot["vitals"]) == 7,
                "transitions": sorted(set(r["transition_class"] for r in delta["vitals"]))}
    if op == "forbidden":
        from devostasis import history as history_module
        original = canonical.load_file
        def read(file, *args, **kwargs):
            if file == store.index_path(key): raise PermissionError("FORBIDDEN")
            return original(file, *args, **kwargs)
        with patch.object(history_module.canonical, "load_file", read):
            current = build_from_observations(project, full_inputs(obs_set("2026-09-06T12:00:00Z")), store)
            state = store.latest(key, "123456")
        return {"comparison": current.manifest["comparison_status"], "forbidden_explicit": any("HISTORY_STORE_FORBIDDEN" in p for p in state.problems),
                "previous_preserved": verify_dir(path) == []}
    if op == "two-writers":
        # Both writers have already read first. Force writer A to commit before
        # writer B, then inspect the stale writer and its immutable candidate.
        third = build_from_observations(project, full_inputs(obs_set("2026-09-07T12:00:00Z")), store)
        from devostasis.workscope.bundle import locked
        with locked(root / ".history-store-lock"):
            try: store.commit(second)
            except HistoryConflictError: locked_writer_refused = True
            else: locked_writer_refused = False
        a_path = store.commit(second)
        try: store.commit(third)
        except HistoryConflictError: conflict = True
        else: conflict = False
        checkpoint = store.latest(key, "123456").bundle_id == second.bundle_id
        candidate = store.history_dir(third)
        rebuilt = build_from_observations(project, full_inputs(obs_set("2026-09-07T12:00:00Z")), store)
        b_path = store.commit(rebuilt)
        return {"conflict": conflict, "locked_writer_refused": locked_writer_refused, "checkpoint_latest_a": checkpoint,
            "immutable_candidates_preserved": all(verify_dir(p) == [] for p in (path, a_path, candidate, b_path)),
            "retry_uses_a": rebuilt.manifest["previous_bundle_id"] == second.bundle_id,
            "latest_retry": store.latest(key, "123456").bundle_id == rebuilt.bundle_id}
    raise ValueError("unsupported history operation")


SCENARIOS = {"ci-native.v1": native, "independence.v1": independence,
             "multi-vital.v1": multivital, "bundle.v1": bundle, "history-store.v1": history,
             "vital-consumers.v1": vital_consumers, "ci-revisions.v1": ci_revisions}


def load(path):
    document = canonical.loads(Path(path).read_text(encoding="utf-8"))
    shape(document, ("schema", "source", "cases"))
    if document["schema"] != CONTRACT: raise ValueError("unknown bridge lineage")
    if not isinstance(document["source"], str) or not document["source"]: raise ValueError("source required")
    if not isinstance(document["cases"], list) or not document["cases"]:
        raise ValueError("nonempty case inventory required")
    seen = set()
    for case in document["cases"]:
        shape(case, ("case", "scenario", "given", "checks"))
        if not isinstance(case["case"], str) or not case["case"] or case["case"] in seen: raise ValueError("duplicate or invalid case")
        seen.add(case["case"])
        if case["scenario"] not in SCENARIOS: raise ValueError("unknown scenario lineage")
        if not isinstance(case["given"], dict) or not isinstance(case["checks"], list) or not case["checks"]:
            raise ValueError("scenario input and checks required")
        for check in case["checks"]:
            if not isinstance(check, dict) or set(check) not in ({"path", "equals"}, {"path", "not_equals"}, {"path", "contains"}, {"path", "absent"}):
                raise ValueError("unknown assertion")
            if not isinstance(check["path"], list) or not all(type(p) in (str, int) for p in check["path"]):
                raise ValueError("invalid assertion path")
            if "absent" in check and check["absent"] is not True: raise ValueError("absent must be true")
        if case["case"] == "T8":
            required = {(s, "FRESH") for s in ("FORBIDDEN", "UNKNOWN", "ERROR", "PARTIAL")} | {("AVAILABLE", "STALE")}
            variants = case["given"].get("variants", [])
            if len(variants) != 5 or {(v.get("status"), v.get("freshness")) for v in variants} != required:
                raise ValueError("T8 requires every independent evidence-state substitution")
    return document["cases"]


def execute(case, root):
    actual = SCENARIOS[case["scenario"]](deepcopy(case["given"]), root)
    for check in case["checks"]:
        node, exists = actual, True
        for part in check["path"]:
            try: node = node[part]
            except (KeyError, IndexError, TypeError): exists = False; break
        where = f"{case['case']}:{check['path']}"
        if "absent" in check:
            if exists: raise AssertionError(f"{where}: forbidden field exists")
            continue
        if not exists: raise AssertionError(f"{where}: unknown checkpoint/assertion path")
        if "equals" in check:
            if canonical.canonical_bytes(node) != canonical.canonical_bytes(check["equals"]):
                raise AssertionError(f"{where}: expected {check['equals']!r}, got {node!r}")
        if "not_equals" in check:
            if canonical.canonical_bytes(node) == canonical.canonical_bytes(check["not_equals"]):
                raise AssertionError(f"{where}: forbidden value {node!r}")
        if "contains" in check:
            if check["contains"] not in node: raise AssertionError(f"{where}: missing {check['contains']!r}")
    return actual


def load_suite(paths=None):
    paths = paths if paths is not None else [Path(__file__).parent / "fixtures" / name
        for name in ("conformance-surface.json", "ci-revisions.json")]
    cases = [case for path in paths for case in load(path)]
    ids = [case["case"] for case in cases]
    if len(ids) != len(set(ids)): raise ValueError("duplicate permanent case across bridge carriers")
    return cases
