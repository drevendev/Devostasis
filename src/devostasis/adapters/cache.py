"""Conditional-request cache for read-only provider calls.

A fleet run asks the same provider the same questions every day, and most of
the answers did not change. HTTP already solves this: the provider returns an
entity tag, the next request carries it back as ``If-None-Match``, and the
provider answers ``304 Not Modified`` with no body. GitHub does not count a
304 against the primary rate limit, so a store that keeps its tags between
runs spends quota only on what actually moved.

The cache holds evidence, never conclusions: a cached body is exactly the body
the provider returned, and a run that uses it produces the same observations,
the same bundle and the same identity as a run that fetched everything again.
That property is what makes the cache safe to enable and disable at will, and
it is covered by a test.

The file is a plain JSON document so it can be inspected, deleted or shipped
through an ordinary CI cache. Nothing in it is required: a missing, corrupt or
stale cache costs requests, never correctness. That holds entry by entry as
well as for the file: an entry is replayed only when its complete shape is
readable and the body it holds still hashes to the digest recorded beside the
tag, because a 304 confirms the provider's validator, not whatever bytes sit
next to it on disk. Anything else is a miss and is fetched again
(PV-AUDIT-GITHUB-CACHE-INTEGRITY-001). The digest guards against accidental
corruption, not against an adversary who can rewrite the file.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CACHE_SCHEMA = "devostasis.http-cache.v2"
DEFAULT_MAX_ENTRIES = 4000
DEFAULT_MAX_ENTRY_BYTES = 2_000_000


def _serialized(body: Any) -> str | None:
    """The body as the deterministic text its digest is taken over, or None when it cannot be serialized."""
    try:
        return json.dumps(body, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return None


def _digest(serialized: str) -> str:
    return "sha256:" + hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def valid_entry(entry: Any) -> bool:
    """Whether a persisted entry is complete, well typed and still hashes to its digest."""
    if not isinstance(entry, dict):
        return False
    etag = entry.get("etag")
    used = entry.get("used", 0)
    if not isinstance(etag, str) or not etag.strip():
        return False
    if isinstance(used, bool) or not isinstance(used, int) or used < 0:
        return False
    if "body" not in entry or entry["body"] is None:
        return False
    serialized = _serialized(entry["body"])
    if serialized is None:
        return False
    return entry.get("digest") == _digest(serialized)


class ConditionalCache:
    """Entity tags and bodies of previous responses, keyed by request.

    Eviction is least-recently-used by an internal counter rather than by a
    clock, so the file does not depend on when it was written.
    """

    def __init__(
        self,
        path: str | Path | None = None,
        max_entries: int = DEFAULT_MAX_ENTRIES,
        max_entry_bytes: int = DEFAULT_MAX_ENTRY_BYTES,
    ) -> None:
        self.path = Path(path) if path is not None else None
        self.max_entries = max_entries
        self.max_entry_bytes = max_entry_bytes
        self._entries: dict[str, dict[str, Any]] = {}
        self._tick = 0
        self.hits = 0
        self.stores = 0
        self.discarded = 0
        self.load()

    # ------------------------------------------------------------------ file

    def load(self) -> None:
        """Read the cache file. A missing, unreadable or foreign file is an empty cache; a bad entry is a miss."""
        if self.path is None or not self.path.exists():
            return
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return
        if not isinstance(document, dict) or document.get("schema") != CACHE_SCHEMA:
            return
        entries = document.get("entries")
        if not isinstance(entries, dict):
            return
        kept: dict[str, dict[str, Any]] = {}
        for key, entry in entries.items():
            if isinstance(key, str) and key and valid_entry(entry):
                kept[key] = {"etag": entry["etag"], "body": entry["body"], "used": entry.get("used", 0), "digest": entry["digest"]}
            else:
                self.discarded += 1
        self._entries = kept
        self._tick = max((entry["used"] for entry in self._entries.values()), default=0)

    def save(self) -> None:
        if self.path is None:
            return
        self._evict()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        document = {"schema": CACHE_SCHEMA, "entries": self._entries}
        self.path.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")), encoding="utf-8")

    def _evict(self) -> None:
        if len(self._entries) <= self.max_entries:
            return
        ordered = sorted(self._entries.items(), key=lambda item: int(item[1].get("used", 0)), reverse=True)
        self._entries = dict(ordered[: self.max_entries])

    # ------------------------------------------------------------------ use

    @staticmethod
    def key(path: str, params: dict[str, Any] | None) -> str:
        if not params:
            return path
        rendered = "&".join(f"{name}={params[name]}" for name in sorted(params))
        return f"{path}?{rendered}"

    def etag_for(self, key: str) -> str | None:
        entry = self._entries.get(key)
        return entry.get("etag") if entry else None

    def body_for(self, key: str) -> Any:
        """The cached body, recorded as used. Returns None when the entry is gone or no longer hashes to its digest."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        if not valid_entry(entry):
            self._entries.pop(key, None)
            self.discarded += 1
            return None
        self._tick += 1
        entry["used"] = self._tick
        self.hits += 1
        return entry.get("body")

    def store(self, key: str, etag: str | None, body: Any) -> None:
        """Remember a response. Bodies too large, or absent, are not worth a tag."""
        if not etag or body is None:
            return
        serialized = _serialized(body)
        if serialized is None:
            return
        if len(serialized) > self.max_entry_bytes:
            self._entries.pop(key, None)
            return
        self._tick += 1
        self._entries[key] = {"etag": etag, "body": body, "used": self._tick, "digest": _digest(serialized)}
        self.stores += 1

    def __len__(self) -> int:
        return len(self._entries)
