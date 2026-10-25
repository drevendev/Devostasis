"""Independent source-selection predicates and explicit omitted-size proof limits."""

from copy import deepcopy
import json

import pytest

from devostasis.cli import main
from devostasis.codeanalysis.bundle import build, proof_scope, publish, verify_content
from devostasis.codeanalysis.engine import default_policy
from devostasis.codeanalysis.git import collect
from test_code_analysis import AT, repository


@pytest.mark.parametrize("reason", ["UNSAFE_PATH", "SOURCE_LINK_OR_SUBMODULE", "FILE_BYTE_CAP", "FILE_COUNT_CAP", "TOTAL_BYTE_CAP"])
def test_rehashed_source_omission_requires_its_actual_predicate(tmp_path, reason):
    config = default_policy()
    raw = collect(repository(tmp_path, {"safe.py": "pass\n"}), "HEAD", config, AT)
    raw["entries"][0].update(status="UNAVAILABLE", reason=reason)
    raw["sources"].clear()
    with pytest.raises(ValueError, match="unjustified source selection"):
        build(raw, config)


def test_valid_caps_and_policy_exclusions_still_replay(tmp_path):
    repo = repository(tmp_path, {"a.py": "pass\n", "b.py": "pass\n", "vendor/c.py": "pass\n", "README.md": "fixture"})
    for budget, value in (("max_files", 1), ("max_file_bytes", 1), ("max_total_bytes", 6)):
        config = default_policy(); config["budget"][budget] = value
        if budget == "max_total_bytes": config["budget"]["max_file_bytes"] = value
        raw = collect(repo, "HEAD", config, AT)
        _, members = build(raw, config)
        decoded = verify_content(members)
        assert decoded["analysis.json"]["coverage"] == "PARTIAL"
        assert proof_scope(decoded)["omitted_blob_sizes"] == "UNPROVEN"
        assert any(e["status"] == "OUT_OF_SCOPE" for e in raw["entries"])


def test_omitted_size_claim_does_not_become_independent_blob_proof(tmp_path, capsys):
    config = default_policy(legacy=True)
    raw = collect(repository(tmp_path, {"safe.py": "pass\n"}), "HEAD", config, AT)
    # The tree authenticates the blob id, not this replacement size metadata.
    changed = deepcopy(raw)
    changed["entries"][0].update(status="UNAVAILABLE", reason="FILE_BYTE_CAP", size=2_000_000)
    changed["sources"].clear()
    _, members = build(changed, config)
    decoded = verify_content(members)
    assert decoded["analysis.json"]["coverage"] == "PARTIAL"
    assert proof_scope(decoded)["omitted_blob_sizes"] == "UNPROVEN"
    root = publish(tmp_path / "bundle", members)
    assert main(["code", "verify", "--bundle", str(root)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["proof_scope"]["omitted_blob_sizes"] == "UNPROVEN"
    assert receipt["proof_scope"]["history_ancestry"] == "UNPROVEN"


def test_admitted_size_is_independently_bound_to_original_bytes(tmp_path):
    config = default_policy()
    raw = collect(repository(tmp_path, {"safe.py": "pass\n"}), "HEAD", config, AT)
    raw["entries"][0]["size"] += 1
    with pytest.raises(ValueError, match="source blob binding mismatch"):
        build(raw, config)
