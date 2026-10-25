"""Independent object-proof admission rather than trust in collector claims."""

from copy import deepcopy
import itertools

import pytest

from devostasis.codeanalysis.bundle import admit, build, proof_scope, verify_content
from devostasis.codeanalysis.consumer import compare, packet, verify_packet
from devostasis.codeanalysis.engine import default_policy
from devostasis.codeanalysis.history_proof import line_edits
from test_code_analysis import NEXT, analyze, commit, git, repository


@pytest.mark.parametrize("claim", ["root", "repository", "ancestor", "count", "time", "complete", "frontier"])
def test_rehashed_history_claims_require_authenticated_objects(tmp_path, claim):
    repo = repository(tmp_path, {"a.py": "a = 1\n"})
    commit(repo, {"a.py": "a = 2\nb = 3\n"}, NEXT)
    raw, config, _, _, _ = analyze(repo, at=NEXT)
    raw = deepcopy(raw)
    if claim == "root": raw["subject"]["roots"] = ["0" * 40]
    if claim == "repository": raw["subject"]["repository_id"] = "sha256:" + "0" * 64
    if claim == "ancestor": raw["history_proof"]["commits"].clear()
    if claim == "count": raw["history"]["commits"][-1]["changes"][0]["added"] = 999
    if claim == "time": raw["history"]["commits"][0]["committed_at"] = NEXT
    if claim == "complete": raw["history"]["commits"].pop()
    if claim == "frontier": raw["history_proof"]["frontier"] = ["0" * 40]
    with pytest.raises(ValueError): build(raw, config)


def test_offline_replay_has_no_git_repository_or_subprocess_dependency(tmp_path, monkeypatch):
    repo = repository(tmp_path, {"a.py": "x = 1\n"})
    commit(repo, {"a.py": "x = 2\n"}, NEXT)
    raw, _, _, members, decoded = analyze(repo, at=NEXT)
    import subprocess
    def forbidden(*args, **kwargs): raise AssertionError("offline verifier invoked subprocess")
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    assert verify_content(members) == decoded
    assert proof_scope(decoded)["history_counts"] == "VERIFIED"
    assert len(raw["history"]["commits"]) == 2


def test_graph_walk_does_not_prune_clock_skew_or_merge_parents(tmp_path):
    repo = repository(tmp_path, {"a.py": "x = 1\n"})
    root = git(repo, "rev-parse", "HEAD").strip().decode()
    git(repo, "checkout", "-b", "side")
    side = commit(repo, {"side.py": "s = 1\n"}, NEXT)
    git(repo, "checkout", "main")
    main = commit(repo, {"main.py": "m = 1\n"}, "2026-08-01T00:00:00Z")
    git(repo, "merge", "--no-ff", "side", "-m", "synthetic merge", at=NEXT)
    raw, _, _, _, _ = analyze(repo, at=NEXT)
    assert raw["subject"]["roots"] == [root]
    assert raw["subject"]["roots_complete"] is True
    assert {r["revision"] for r in raw["history"]["commits"]} == {root, side}
    assert main in raw["history_proof"]["commits"]


@pytest.mark.parametrize("limit,value", [("max_ancestors", 1), ("max_objects", 1), ("max_blob_bytes", 1), ("max_diff_work", 1)])
def test_bounded_proof_never_claims_complete_history(tmp_path, limit, value):
    repo = repository(tmp_path, {"a.py": "x = 1\n"})
    commit(repo, {"a.py": "x = 2\n"}, NEXT)
    config = default_policy(); config["history"][limit] = value
    raw, _, _, _, decoded = analyze(repo, config, at=NEXT)
    assert raw["history"]["status"] == "PARTIAL"
    assert proof_scope(decoded)["history_counts"] == "PARTIAL"
    forged = deepcopy(raw); forged["history"]["status"] = "COMPLETE"; forged["history"]["reasons"] = []
    with pytest.raises(ValueError): admit(forged, config)
    if limit == "max_ancestors":
        assert raw["subject"]["roots"] == [] and not raw["subject"]["roots_complete"]
        assert compare(decoded, decoded)["status"] == "INCOMPARABLE"
        assert all(c["count_status"] == "UNAVAILABLE" for c in raw["history"]["commits"][0]["changes"])


def test_wrongly_typed_historic_objects_fail_closed(tmp_path):
    raw, config, _, _, _ = analyze(repository(tmp_path))
    raw["history_proof"]["blobs"][raw["subject"]["revision"]] = raw["proof"]["commit"]
    with pytest.raises(ValueError, match="hash mismatch"): admit(raw, config)


def test_v1_and_v2_replay_separately_and_do_not_compare_across_lineage(tmp_path):
    repo = repository(tmp_path)
    old = analyze(repo, default_policy(legacy=True))[4]
    new = analyze(repo)[4]
    assert old["manifest.json"]["contract"] == "devostasis.code-analysis.v1"
    assert new["manifest.json"]["contract"] == "devostasis.code-analysis.v2"
    assert proof_scope(old)["history_ancestry"] == "UNPROVEN"
    assert proof_scope(new)["history_ancestry"] == "VERIFIED"
    assert "ANALYSIS_LINEAGE_CHANGED" in compare(old, new)["reasons"]
    for decoded in (old, new):
        assert verify_packet(packet(decoded, ["src/pkg/a.py"]), decoded)


def test_byte_line_algorithm_matches_independent_lcs_oracle():
    limits = default_policy()["history"]
    words = [b"", b"a\n", b"b\n", b"a\nb\n", b"b\na\n", b"a\na\n", b"a"]
    for before, after in itertools.product(words, repeat=2):
        a, b = before.splitlines(keepends=True), after.splitlines(keepends=True)
        table = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
        for i in range(len(a)):
            for j in range(len(b)):
                table[i + 1][j + 1] = table[i][j] + 1 if a[i] == b[j] else max(table[i][j + 1], table[i + 1][j])
        common = table[-1][-1]
        assert line_edits(before, after, limits, [0]) == (len(b) - common, len(a) - common, "VERIFIED", None)
    assert line_edits(b"a\0", b"b", limits, [0])[2] == "BINARY"


def test_historic_proof_does_not_read_policy_excluded_blob_bytes(tmp_path):
    from devostasis.codeanalysis.history_proof import decoded
    secret = b"excluded fixture bytes, never part of proof\n"
    repo = repository(tmp_path, {"private/secret.txt": secret, "a.py": "x = 1\n"})
    commit(repo, {"private/secret.txt": b"other excluded bytes\n", "a.py": "x = 2\n"}, NEXT)
    config = default_policy(); config["exclude"].append("private")
    raw, _, _, _, _ = analyze(repo, config, at=NEXT)
    assert all(decoded(value, 4 * 1024 * 1024) != secret for value in raw["history_proof"]["blobs"].values())
    assert all(c["count_status"] == "OUT_OF_SCOPE" for row in raw["history"]["commits"] for c in row["changes"] if c["path"].startswith("private/"))


def test_valid_but_unreachable_historic_object_is_rejected(tmp_path):
    from devostasis.codeanalysis.git import object_digest
    from devostasis.codeanalysis.history_proof import encoded
    raw, config, _, _, _ = analyze(repository(tmp_path))
    extra = b"unreachable fixture"
    raw["history_proof"]["blobs"][object_digest(extra, "sha1")] = encoded(extra)
    with pytest.raises(ValueError, match="unused history object"): admit(raw, config)


def test_v2_frozen_example_replays_and_has_explicit_schemas():
    import json
    from pathlib import Path
    from devostasis.codeanalysis.bundle import verify
    from devostasis.workscope.bundle import verify as verify_work
    root = Path(__file__).resolve().parents[1]
    decoded = verify(root / "examples/code-v2/bundle")
    assert proof_scope(decoded)["history_ancestry"] == "VERIFIED"
    verify_packet(json.loads((root / "examples/code-v2/packet.json").read_text()), decoded)
    assert any(i["queue"] == "analyze_code" for i in verify_work(root / "examples/code-v2/work-bundle")["scope.json"]["items"])
    for name, value in (("code-manifest", decoded["manifest.json"]), ("code-policy", decoded["policy.json"]),
                        ("code-packet", json.loads((root / "examples/code-v2/packet.json").read_text()))):
        schema = json.loads((root / f"schemas/{name}-v2.schema.json").read_text())
        assert schema["properties"]["contract"]["const"] == value["contract"]
        assert set(value) == set(schema["required"]) == set(schema["properties"])
