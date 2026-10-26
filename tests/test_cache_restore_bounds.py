"""Implementation-local retention cases DEV-CACHE-RESTORE-01..06."""

import json
from pathlib import Path
from typing import Any

import pytest

from devostasis.adapters.cache import ConditionalCache
from devostasis.adapters.github import GitHubClient


def test_dev_cache_restore_01_lower_entry_cap_keeps_recent_evidence(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    cache = ConditionalCache(path, max_entries=4)
    for key in ("a", "b", "c"):
        cache.store(key, f'"{key}"', {"key": key})
    cache.body_for("a")
    cache.save()
    original = path.read_bytes()

    restored = ConditionalCache(path, max_entries=2)
    assert len(restored) == 2
    assert restored.body_for("a") == {"key": "a"}
    assert restored.body_for("c") == {"key": "c"}
    assert restored.etag_for("b") is None
    assert path.read_bytes() == original, "loading must not rewrite the persisted evidence"


def test_dev_cache_restore_02_current_body_cap_includes_exact_boundary(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    small, large = {"text": "\u00e9"}, {"text": "\u00e9\u00e9"}
    cache = ConditionalCache(path)
    cache.store("small", '"s"', small)
    cache.store("large", '"l"', large)
    cache.save()
    boundary = len(json.dumps(small, sort_keys=True, separators=(",", ":")).encode("utf-8"))

    restored = ConditionalCache(path, max_entry_bytes=boundary)
    assert restored.body_for("small") == small
    assert restored.etag_for("large") is None
    assert restored.body_for("large") is None
    assert restored.discarded == 1


def test_dev_cache_restore_03_zero_entry_cap_retains_nothing(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    cache = ConditionalCache(path)
    cache.store("a", '"a"', {"n": 1})
    cache.save()
    restored = ConditionalCache(path, max_entries=0)
    assert len(restored) == 0
    assert restored.etag_for("a") is None


@pytest.mark.parametrize("order", [("a", "b"), ("b", "a")])
def test_dev_cache_restore_04_equal_recency_has_stable_key_tie_break(
    tmp_path: Path, order: tuple[str, str]
) -> None:
    path = tmp_path / "cache.json"
    cache = ConditionalCache(path)
    for key in order:
        cache.store(key, f'"{key}"', {"key": key})
    cache.save()
    document = json.loads(path.read_text(encoding="utf-8"))
    for entry in document["entries"].values():
        entry["used"] = 7
    document["entries"] = {key: document["entries"][key] for key in order}
    path.write_text(json.dumps(document), encoding="utf-8")

    restored = ConditionalCache(path, max_entries=1)
    assert len(restored) == 1
    assert restored.etag_for("a") == '"a"'
    assert restored.etag_for("b") is None
    restored.store("c", '"c"', {"key": "c"})
    restored.save()
    assert ConditionalCache(path).body_for("c") == {"key": "c"}


def test_dev_cache_restore_05_tampering_still_becomes_a_miss(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    cache = ConditionalCache(path)
    cache.store("a", '"a"', {"n": 1})
    cache.save()
    document = json.loads(path.read_text(encoding="utf-8"))
    document["entries"]["a"]["body"] = {"n": 2}
    path.write_text(json.dumps(document), encoding="utf-8")
    restored = ConditionalCache(path, max_entries=1)
    assert restored.etag_for("a") is None
    assert restored.discarded == 1


def test_dev_cache_restore_06_oversize_body_refetches_without_old_etag(tmp_path: Path) -> None:
    path = tmp_path / "cache.json"
    cache = ConditionalCache(path)
    cache.store("/resource", '"old"', {"text": "x" * 100})
    cache.save()
    restored = ConditionalCache(path, max_entry_bytes=32)
    calls: list[dict[str, str]] = []

    class Transport:
        def get(
            self, path: str, params: dict[str, Any] | None = None,
            headers: dict[str, str] | None = None,
        ) -> tuple[int, dict[str, str], dict[str, bool]]:
            calls.append(dict(headers or {}))
            return 200, {"etag": '"fresh"'}, {"fresh": True}

    client = GitHubClient(Transport(), cache=restored)
    assert client.get("/resource") == {"fresh": True}
    assert calls == [{}]
    assert client.conditional_hits == 0
