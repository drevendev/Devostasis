"""Bounded Git object proofs and pure offline ancestry/line-edit admission.

No Git executable, diff driver, checkout, clock or repository is used by replay.
LF-delimited byte lines use a bounded shortest edit distance, independent of
Git configuration and rename/diff heuristics. Missing proof is explicit.
"""

import base64
from datetime import datetime, timedelta, timezone

from ..canonical import digest
from ..workscope.model import fields, instant, path, require, revision, timestamp
from . import HISTORY_PROOF
from .git import Git, _collect_v1, object_digest

KINDS = ("commit", "tree", "blob")
OMISSIONS = {"OBJECT_UNAVAILABLE", "OBJECT_BYTE_CAP", "OBJECT_COUNT_CAP", "PROOF_BYTE_CAP", "TIME_CAP"}
ALGORITHM = "MYERS_LF_BYTE_LINES_V1"


def encoded(data):
    return base64.b64encode(data).decode("ascii")


def decoded(value, cap):
    require(isinstance(value, str) and len(value) <= (cap + 2) // 3 * 4, "history object encoding cap")
    data = base64.b64decode(value, validate=True)
    require(len(data) <= cap and encoded(data) == value, "noncanonical history object")
    return data


def object_ref(value, width):
    revision(value)
    require(len(value) == width, "history object format mismatch")
    return value


def commit_headers(data, width):
    header, separator, _ = data.partition(b"\n\n")
    require(separator, "commit header terminator missing")
    lines = header.split(b"\n")
    trees = [line[5:].decode("ascii") for line in lines if line.startswith(b"tree ")]
    parents = [line[7:].decode("ascii") for line in lines if line.startswith(b"parent ")]
    committers = [line[10:] for line in lines if line.startswith(b"committer ")]
    require(len(trees) == 1 and len(committers) == 1 and len(parents) <= 10000
            and len(parents) == len(set(parents)), "commit tree/parent/committer shape")
    for ref in trees + parents:
        object_ref(ref, width)
    identity, epoch, zone = committers[0].rsplit(b" ", 2)
    require(identity.endswith(b">") and len(zone) == 5 and zone[:1] in (b"+", b"-")
            and zone[1:].isdigit(), "commit committer syntax")
    require(epoch.lstrip(b"-").isdigit(), "commit epoch syntax")
    when = timestamp(datetime.fromtimestamp(int(epoch), timezone.utc).isoformat())
    return {"tree": trees[0], "parents": parents, "committed_at": when}


def seed_objects(raw):
    fmt = raw["subject"]["object_format"]
    objects = {kind: {} for kind in KINDS}
    objects["commit"][raw["subject"]["revision"]] = decoded(raw["proof"]["commit"], 1024 * 1024)
    objects["tree"] = {oid: decoded(value, 8 * 1024 * 1024) for oid, value in raw["proof"]["trees"].items()}
    entries = {e["path"]: e for e in raw["entries"] if e["path"] is not None}
    for name, value in raw["sources"].items():
        objects["blob"][entries[name]["object_id"]] = base64.b64decode(value, validate=True)
    for kind, rows in objects.items():
        require(all(object_digest(data, fmt, kind) == oid for oid, data in rows.items()), "history seed object mismatch")
    return objects


class Objects:
    """Same bounded lookup interface for acquisition and independent replay."""

    def __init__(self, raw, config, proof=None, git=None):
        self.format = raw["subject"]["object_format"]
        self.width = 40 if self.format == "sha1" else 64
        self.limits = config["history"]
        self.seed = seed_objects(raw)
        self.objects = {kind: dict(rows) for kind, rows in self.seed.items()}
        self.extra = {kind: {} for kind in KINDS}
        self.omitted, self.used = {}, set()
        self.bytes = self.count = 0
        self.git = git
        if proof is not None:
            fields(proof, ("contract", "commits", "trees", "blobs", "omitted", "frontier"))
            require(proof["contract"] == HISTORY_PROOF, "unsupported history proof lineage")
            for kind in KINDS:
                rows = proof[kind + "s"]
                require(isinstance(rows, dict) and len(rows) <= self.limits["max_objects"], "history object count cap")
                for oid, value in rows.items():
                    object_ref(oid, self.width)
                    require(oid not in self.objects[kind], "duplicate source/history object")
                    cap = self.limits["max_blob_bytes"] if kind == "blob" else 1024 * 1024 if kind == "commit" else 8 * 1024 * 1024
                    data = decoded(value, cap)
                    require(object_digest(data, self.format, kind) == oid, "historic object hash mismatch")
                    self.objects[kind][oid] = self.extra[kind][oid] = data
                    self.bytes += len(data); self.count += 1
                    require(self.count <= self.limits["max_objects"] and self.bytes <= self.limits["max_proof_bytes"], "history proof budget exceeded")
            require(self.count <= self.limits["max_objects"] and self.bytes <= self.limits["max_proof_bytes"], "history proof budget exceeded")
            require(isinstance(proof["omitted"], dict) and len(proof["omitted"]) <= 100000, "history omission cap")
            for oid, reason in proof["omitted"].items():
                object_ref(oid, self.width)
                require(reason in OMISSIONS and not any(oid in rows for rows in self.objects.values()), "history omission mismatch")
            self.omitted = dict(proof["omitted"])

    def prefetch(self, kind, refs):
        if self.git is None:
            return
        refs = [oid for oid in sorted(set(refs)) if oid not in self.objects[kind] and oid not in self.omitted]
        if not refs:
            return
        try:
            metadata = self.git.run(["cat-file", "--batch-check"], data="".join(r + "\n" for r in refs).encode("ascii"), cap=len(refs) * 160)
            lines = metadata.splitlines()
            require(len(lines) == len(refs), "historic object header count")
            selected, size_total = [], 0
            for oid, line in zip(refs, lines):
                parts = line.split()
                if parts == [oid.encode("ascii"), b"missing"]:
                    self.omitted[oid] = "OBJECT_UNAVAILABLE"; continue
                require(len(parts) == 3 and parts[0].decode("ascii") == oid and parts[1].decode("ascii") == kind,
                        "historic object kind mismatch")
                size = int(parts[2])
                cap = self.limits["max_blob_bytes"] if kind == "blob" else 1024 * 1024 if kind == "commit" else 8 * 1024 * 1024
                if size > cap:
                    self.omitted[oid] = "OBJECT_BYTE_CAP"
                elif self.count + len(selected) >= self.limits["max_objects"]:
                    self.omitted[oid] = "OBJECT_COUNT_CAP"
                elif self.bytes + size_total + size > self.limits["max_proof_bytes"]:
                    self.omitted[oid] = "PROOF_BYTE_CAP"
                else:
                    require(size >= 0, "historic object negative size")
                    selected.append((oid, size)); size_total += size
            if selected:
                data = self.git.run(["cat-file", "--batch"], data="".join(r + "\n" for r, _ in selected).encode("ascii"), cap=size_total + len(selected) * 160)
                offset = 0
                for oid, size in selected:
                    end = data.index(b"\n", offset)
                    require(data[offset:end] == f"{oid} {kind} {size}".encode("ascii"), "historic object framing mismatch")
                    offset = end + 1; value = data[offset:offset + size]; offset += size
                    require(data[offset:offset + 1] == b"\n" and object_digest(value, self.format, kind) == oid, "historic object bytes mismatch")
                    offset += 1; self.objects[kind][oid] = self.extra[kind][oid] = value
                    self.bytes += size; self.count += 1
                require(offset == len(data), "historic object trailing bytes")
        except (ValueError, OSError) as exc:
            reason = "TIME_CAP" if "TIME_CAP" in str(exc) else "OBJECT_BYTE_CAP" if "BYTE_CAP" in str(exc) else "OBJECT_UNAVAILABLE"
            for oid in refs:
                if oid not in self.objects[kind]: self.omitted[oid] = reason

    def get(self, kind, oid):
        object_ref(oid, self.width)
        self.used.add((kind, oid))
        require(len(self.used) <= 100000, "history reference work cap")
        self.prefetch(kind, [oid])
        if oid in self.objects[kind]:
            return self.objects[kind][oid]
        require(oid in self.omitted, "required history object is neither proved nor explicitly unavailable")
        return None

    def finish(self):
        require(all((kind, oid) in self.used for kind in KINDS for oid in self.extra[kind]), "unreachable or unused history object")
        require(set(self.omitted) <= {oid for _, oid in self.used}, "unused history omission")

    def proof(self, frontier):
        return {"contract": HISTORY_PROOF, **{kind + "s": {oid: encoded(data) for oid, data in sorted(rows.items())}
                for kind, rows in self.extra.items()}, "omitted": dict(sorted(self.omitted.items())), "frontier": sorted(frontier)}


def graph(objects, head):
    pending, attempted, nodes, absent = {head}, set(), {}, set()
    while pending and len(attempted) < objects.limits["max_ancestors"]:
        batch = sorted(pending)[:min(64, objects.limits["max_ancestors"] - len(attempted))]
        objects.prefetch("commit", batch)
        for oid in batch:
            pending.remove(oid); attempted.add(oid)
            data = objects.get("commit", oid)
            if data is None:
                absent.add(oid); continue
            node = commit_headers(data, objects.width); nodes[oid] = node
            pending.update(p for p in node["parents"] if p not in attempted)
        require(len(pending) + len(absent) <= 10000, "history frontier cap")
    frontier = pending | absent
    roots = sorted(oid for oid, node in nodes.items() if not node["parents"])
    require(frontier or roots, "complete ancestry has no root")
    return nodes, frontier, roots


def tree(objects, root, work):
    stack, entries, complete = [(root, b"", frozenset())], {}, True
    while stack:
        oid, prefix, parents = stack.pop()
        require(oid not in parents, "historic tree cycle")
        data = objects.get("tree", oid)
        if data is None:
            complete = False; continue
        offset = 0
        while offset < len(data):
            work[0] += 1
            if work[0] > objects.limits["max_diff_work"]:
                return entries, False
            space = data.find(b" ", offset); end = data.find(b"\0", space)
            require(space > offset and end > space + 1 and end + 1 + objects.width // 2 <= len(data), "historic tree entry malformed")
            mode, name = data[offset:space], data[space + 1:end]
            require(b"/" not in name and name not in (b".", b".."), "historic tree name malformed")
            child = data[end + 1:end + 1 + objects.width // 2].hex(); offset = end + 1 + objects.width // 2
            filename = prefix + name
            if mode == b"40000":
                stack.append((child, filename + b"/", parents | {oid}))
            else:
                require(mode in (b"100644", b"100755", b"120000", b"160000") and filename not in entries, "historic tree mode/duplicate")
                entries[filename] = (mode, child)
        require(len(entries) <= 100000 and len(stack) <= 10000, "historic tree expansion cap")
    return entries, complete


def line_edits(before, after, limits, work):
    """Shortest insertion/deletion counts over exact LF-terminated byte lines."""
    if b"\0" in before or b"\0" in after:
        return None, None, "BINARY", None
    line_count = lambda value: value.count(b"\n") + int(bool(value) and not value.endswith(b"\n"))
    if line_count(before) + line_count(after) > limits["max_diff_lines"]:
        return None, None, "UNAVAILABLE", "DIFF_LINE_CAP"
    def lines(value):
        parts = value.split(b"\n")
        return [p + b"\n" for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
    a, b = lines(before), lines(after)
    n, m = len(a), len(b)
    if not n or not m:
        return m, n, "VERIFIED", None
    frontier = {1: 0}
    for distance in range(n + m + 1):
        for diagonal in range(-distance, distance + 1, 2):
            work[0] += 1
            if work[0] > limits["max_diff_work"]:
                return None, None, "UNAVAILABLE", "DIFF_WORK_CAP"
            if diagonal == -distance or (diagonal != distance and frontier.get(diagonal - 1, -1) < frontier.get(diagonal + 1, -1)):
                x = frontier.get(diagonal + 1, 0)
            else:
                x = frontier[diagonal - 1] + 1
            y = x - diagonal
            while x < n and y < m and a[x] == b[y]:
                work[0] += 1
                if work[0] > limits["max_diff_work"]:
                    return None, None, "UNAVAILABLE", "DIFF_WORK_CAP"
                x += 1; y += 1
            frontier[diagonal] = x
            if x >= n and y >= m:
                return (distance + m - n) // 2, (distance + n - m) // 2, "VERIFIED", None
    raise ValueError("line edit traversal failed")


def derive_history(raw, config, objects):
    head = raw["subject"]["revision"]
    nodes, frontier, roots = graph(objects, head)
    complete = not frontier
    identity = {"object_format": objects.format, "roots": roots}
    if not complete: identity["unproven_ancestry_anchor"] = head
    subject = {**raw["subject"], "roots": roots, "roots_complete": complete, "repository_id": digest(identity)}
    end = instant(raw["observed_at"]); start = end - timedelta(days=config["history"]["days"])
    history = {"status": "NOT_REQUESTED", "reasons": [], "start": timestamp(start.isoformat()), "end": timestamp(end.isoformat()),
        "commits": [], "ancestry_status": "COMPLETE" if complete else "PARTIAL", "count_algorithm": ALGORITHM}
    if not config["history"]["enabled"]:
        return subject, history, frontier
    reasons = set()
    if frontier: reasons.add("HISTORY_GRAPH_INCOMPLETE")
    selected = sorted(((oid, row) for oid, row in nodes.items() if len(row["parents"]) <= 1
        and start <= instant(row["committed_at"]) <= end), key=lambda pair: (pair[1]["committed_at"], pair[0]), reverse=True)
    if len(selected) > config["history"]["max_commits"]: reasons.add("HISTORY_COMMIT_CAP")
    selected = sorted(selected[:config["history"]["max_commits"]], key=lambda pair: (pair[1]["committed_at"], pair[0]))
    tree_cache, work = {}, [0]
    def inventory(root):
        if root not in tree_cache: tree_cache[root] = tree(objects, root, work)
        return tree_cache[root]
    for oid, row in selected:
        current, current_complete = inventory(row["tree"])
        parent = nodes.get(row["parents"][0]) if row["parents"] else None
        previous, previous_complete = inventory(parent["tree"]) if parent else ({}, not row["parents"])
        changes, changes_complete = [], current_complete and previous_complete
        for filename in sorted(set(current) | set(previous)):
            old, new = previous.get(filename), current.get(filename)
            if old == new: continue
            try: name = path(filename.decode("utf-8"))
            except (ValueError, UnicodeError):
                changes_complete = False; reasons.add("HISTORY_PATH_UNAVAILABLE"); continue
            included = not config["include"] or any(name == p or name.startswith(p + "/") for p in config["include"])
            excluded = any(name == p or name.startswith(p + "/") for p in config["exclude"])
            if not included or excluded:
                changes.append({"path": name, "added": None, "deleted": None,
                                "count_status": "OUT_OF_SCOPE", "reason": "POLICY_EXCLUSION"})
                continue
            sides = []
            for entry in (old, new):
                if entry is None: sides.append(b"")
                elif entry[0] == b"160000": sides.append(None)
                else: sides.append(objects.get("blob", entry[1]))
            if (old is None and not previous_complete) or (new is None and not current_complete):
                added, deleted, status, reason = None, None, "UNAVAILABLE", "HISTORIC_TREE_UNAVAILABLE"
            elif old and new and old[1] == new[1]:
                added, deleted, status, reason = 0, 0, "VERIFIED", None
            elif any(value is None for value in sides):
                added, deleted, status, reason = None, None, "UNAVAILABLE", "HISTORIC_BLOB_UNAVAILABLE"
            else:
                added, deleted, status, reason = line_edits(*sides, config["history"], work)
            if status == "UNAVAILABLE":
                changes_complete = False; reasons.add(reason)
            changes.append({"path": name, "added": added, "deleted": deleted, "count_status": status, "reason": reason})
        if not changes_complete: reasons.add("HISTORY_CHANGE_PROOF_INCOMPLETE")
        history["commits"].append({"revision": oid, "committed_at": row["committed_at"], "changes": changes,
                                   "changes_complete": changes_complete})
    history["reasons"] = sorted(reasons)
    history["status"] = "PARTIAL" if reasons else "COMPLETE"
    return subject, history, frontier


def collect_proven(directory, ref, config, at=None):
    git = Git(directory, config["budget"]["seconds"])
    raw = _collect_v1(directory, ref, config, at, _git=git, _source_only=True)
    objects = Objects(raw, config, git=git)
    subject, history, frontier = derive_history(raw, config, objects)
    raw.update(subject=subject, history=history, history_proof=objects.proof(frontier))
    objects.finish()
    return raw


def admit_proven(raw, config):
    objects = Objects(raw, config, proof=raw["history_proof"])
    subject, history, frontier = derive_history(raw, config, objects)
    require(raw["subject"] == subject, "ancestry/root identity proof mismatch")
    require(raw["history"] == history, "historic counts/completeness do not match object proof")
    require(raw["history_proof"]["frontier"] == sorted(frontier), "ancestry frontier mismatch")
    objects.finish()
    return objects
