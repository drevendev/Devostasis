"""End-to-end CLI paths that need no network."""

import json

from devostasis.cli import main
from helpers import full_inputs, obs_set


def test_build_verify_render_and_index(tmp_path, capsys):
    obs_path = tmp_path / "observations.json"
    full_inputs(obs_set()).save(obs_path)
    store = tmp_path / "store"
    assert main(["build", "--observations", str(obs_path), "--store", str(store)]) == 0
    out = capsys.readouterr().out
    assert "BASELINE" in out and "pulse=STEADY" in out
    latest = store / "projects" / "github.com" / "acme" / "widget" / "latest"
    assert main(["verify", "--bundle", str(latest)]) == 0
    assert "verified" in capsys.readouterr().out
    assert main(["render", "--bundle", str(latest)]) == 0
    rendered = capsys.readouterr().out
    assert rendered.encode("utf-8") == (latest / "report.md").read_bytes()
    assert (store / "projects" / "README.md").exists()
    assert main(["index", "--store", str(store)]) == 0
    index = json.loads((latest.parent / "index.json").read_text("utf-8"))
    assert len(index["bundles"]) == 1


def test_evaluate_command(tmp_path, capsys):
    obs_path = tmp_path / "observations.json"
    full_inputs(obs_set()).save(obs_path)
    out_path = tmp_path / "snapshot.json"
    assert main(["evaluate", "--observations", str(obs_path), "--out", str(out_path)]) == 0
    snapshot = json.loads(out_path.read_text("utf-8"))
    assert len(snapshot["vitals"]) == 7
    assert "integrity=CLEAN" in capsys.readouterr().out


def test_run_rejects_invalid_config(tmp_path, capsys):
    config = tmp_path / "devostasis.json"
    config.write_text(json.dumps({"config_version": "1", "projects": [{"repo": "a/b", "theme": "x"}]}), "utf-8")
    assert main(["run", "--config", str(config), "--store", str(tmp_path / "store")]) == 2
    assert "CONFIG_IDENTITY_UNCLASSIFIED" in capsys.readouterr().err
