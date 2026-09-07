"""One project's failure must not end the fleet run (#12, finding 5).

``run_project`` turns every failure it anticipates into an unsuccessful
outcome. Everything it does not anticipate - a provider payload of the wrong
shape, a defect in a collector - used to propagate out of the loop in
``run_all``, so the first project with bad data stopped every project queued
behind it, skipped the entity-tag cache write and left the fleet index stale.
"""

from __future__ import annotations

from datetime import datetime, timezone

from devostasis import runner
from devostasis.config import Config, single_project
from devostasis.history import FilesystemHistoryStore
from devostasis.runner import RunOutcome, run_all

NOW = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


def _config() -> Config:
    return Config(
        config_version="test",
        store_path="history",
        projects=(single_project("acme/broken"), single_project("acme/fine")),
    )


def test_an_unexpected_failure_costs_one_project_and_not_the_fleet(tmp_path, monkeypatch):
    seen = []

    def fake_run_project(project, store, client, now):
        seen.append(project.locator)
        if project.repo == "broken":
            raise IndexError("list index out of range")
        return RunOutcome(project.locator, True, bundle_id="b" * 64)

    monkeypatch.setattr(runner, "run_project", fake_run_project)
    outcomes = run_all(_config(), FilesystemHistoryStore(tmp_path), None, NOW)

    assert seen == ["acme/broken", "acme/fine"], "the second project was never observed"
    assert [outcome.ok for outcome in outcomes] == [False, True]
    assert "IndexError" in outcomes[0].error and "list index out of range" in outcomes[0].error


def test_the_failure_reason_survives_so_the_run_still_exits_non_zero(tmp_path, monkeypatch):
    """Isolation must not become swallowing: an unsuccessful outcome stays unsuccessful."""
    monkeypatch.setattr(runner, "run_project", lambda *args: (_ for _ in ()).throw(RuntimeError("collector defect")))
    outcomes = run_all(_config(), FilesystemHistoryStore(tmp_path), None, NOW)

    assert all(not outcome.ok for outcome in outcomes)
    assert all("RuntimeError: collector defect" == outcome.error for outcome in outcomes)
