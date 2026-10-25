"""Versioned offline CI evidence: native parents, explicit links and child fallback.

Input is a bounded projection of provider evidence, not a transport or a new
classifier. Old GitHub collection and historical observation bytes are unchanged.
"""

from copy import deepcopy

from .. import canonical, timeutil
from ..observations import Observation, ObservationSet
from ..revision_history import current_history
from . import github_ci as gh, gitlab_ci as gl

CONTRACT = "devostasis.ci-normalization.v1"
LINK_CONTRACT = "devostasis.ci-rerun-link.v1"
NATIVE = "ci.native_evidence"
PROVENANCE = "ci.normalization_provenance"
SURFACES = {"github": {"actions": gh.ACTIONS_KIND, "checks": "github_check_suite"},
            "gitlab": {"pipelines": "gitlab_pipeline"}}
PREFIX = {"actions": "github_actions:workflow_run:", "checks": "github_checks:check_suite:", "pipelines": "gitlab:pipeline:"}
AVAILABILITY = {"COMPLETE", "PARTIAL", "STALE", "UNAVAILABLE"}
NATIVE_KEYS = {"actions": {"id", "head_sha", "run_attempt", "status", "conclusion", "check_suite_id", "name", "event", "workflow_id", "html_url", "updated_at", "completed_at"},
    "checks": {"id", "head_sha", "status", "conclusion", "app", "url", "updated_at", "completed_at"},
    "pipelines": {"id", "sha", "status", "ref", "source", "web_url", "updated_at", "finished_at"},
    "check-run": {"id", "head_sha", "status", "conclusion", "name"},
    "job": {"id", "sha", "status", "name"}}


def require(condition, message):
    if not condition: raise ValueError(message)


def fields(value, required, allowed=None):
    require(isinstance(value, dict) and set(required) <= set(value) <= set(allowed or required), "unknown or missing CI evidence fields")


def text(value):
    require(isinstance(value, str) and 0 < len(value) <= 2048, "CI identity/text unavailable")
    return value


def identifier(value):
    require(type(value) is int and value > 0, "provider id must be a positive integer")
    return value


def reference(value, provider):
    fields(value, ("surface", "id"))
    require(value["surface"] in SURFACES[provider], "foreign parent surface")
    return PREFIX[value["surface"]] + str(identifier(value["id"]))


def evidence(row, provider, *, child=False):
    fields(row, ("surface", "revision", "observed_at", "coverage", "native", *(["parent"] if child else [])))
    surface, data = row["surface"], row["native"]
    require(surface in (("check-run",) if provider == "github" else ("job",)) if child else surface in SURFACES[provider], "foreign provider evidence")
    required = {"id", "sha" if provider == "gitlab" else "head_sha", "status"}
    if provider == "github": required.add("conclusion")
    if surface == "actions": required.add("run_attempt")
    fields(data, required, NATIVE_KEYS[surface]); identifier(data["id"])
    text(row["revision"]); timeutil.parse_ts(row["observed_at"])
    require(row["coverage"] in AVAILABILITY, "unknown CI source coverage")
    require(data.get("sha" if provider == "gitlab" else "head_sha") == row["revision"], "native revision binding mismatch")
    for key in ("status", "conclusion"):
        if key in data: require(data[key] is None or isinstance(data[key], str), "untyped native outcome")
    if surface == "actions": identifier(data["run_attempt"])
    for key in ("name", "event", "html_url", "url", "ref", "source", "web_url", "updated_at", "completed_at", "finished_at"):
        if data.get(key) is not None: text(data[key])
    if data.get("workflow_id") is not None: identifier(data["workflow_id"])
    if data.get("check_suite_id") is not None: identifier(data["check_suite_id"])
    if "app" in data:
        fields(data["app"], (), ("id", "slug"))
        if "id" in data["app"]: identifier(data["app"]["id"])
        if "slug" in data["app"]: text(data["app"]["slug"])
    if child and row["parent"] is not None: reference(row["parent"], provider)
    state = gl.normalize_outcome(data["status"]) if provider == "gitlab" else gh.normalize_outcome(data["status"], data["conclusion"])
    if provider == "github" and data["status"] not in ("completed", "queued", "in_progress", "waiting", "pending", "requested"):
        state = "UNKNOWN"
    return "UNKNOWN" if row["coverage"] in ("STALE", "UNAVAILABLE") else state


def canonical_input(value):
    fields(value, ("contract", "project", "outcome_map", "observed_at", "configured", "coverage", "revisions", "parents", "children", "rerun_links"))
    require(value["contract"] == CONTRACT, "unsupported CI normalization contract")
    project = value["project"]
    fields(project, ("provider", "forge_instance", "immutable_project_id", "default_branch"))
    require(project["provider"] in SURFACES, "unsupported CI provider")
    for item in project.values(): text(item)
    expected = gh.OUTCOME_MAP_VERSION if project["provider"] == "github" else gl.OUTCOME_MAP_VERSION
    require(value["outcome_map"] == expected, "mixed provider/outcome-map lineage")
    timeutil.parse_ts(value["observed_at"])
    require(value["configured"] is None or type(value["configured"]) is bool, "CI configured must be boolean or unknown")
    require(value["coverage"] in AVAILABILITY, "unknown CI inventory coverage")
    result = deepcopy(value)
    if isinstance(result["parents"], dict):
        fields(result["parents"], ("pages",))
        pages = result["parents"]["pages"]
        require(isinstance(pages, list) and 0 < len(pages) <= 1000, "CI pagination cap")
        for page in pages:
            fields(page, ("ordinal", "has_next", "items")); identifier(page["ordinal"])
            require(type(page["has_next"]) is bool and isinstance(page["items"], list), "malformed CI page")
        pages.sort(key=lambda p: p["ordinal"])
        require([p["ordinal"] for p in pages] == list(range(1, len(pages) + 1)), "missing or duplicate CI page")
        require(all(p["has_next"] for p in pages[:-1]), "contradictory CI continuation")
        if pages[-1]["has_next"]: result["coverage"] = "PARTIAL"
        result["parents"] = [item for p in pages for item in p["items"]]
    for key in ("revisions", "parents", "children", "rerun_links"):
        rows = result[key]
        require(isinstance(rows, list) and len(rows) <= 10000, "CI evidence cardinality cap")
        result[key] = [canonical.loads(data.decode()) for data in sorted({canonical.canonical_bytes(row) for row in rows})]
    require(len(canonical.canonical_bytes(result)) <= 16 * 1024 * 1024, "CI evidence byte cap")
    return result


def parent_from_snapshots(rows, provider):
    surface = rows[0]["surface"]
    if surface == "actions":
        suites = {r["native"]["check_suite_id"] for r in rows if r["native"].get("check_suite_id") is not None}
        require(len(suites) <= 1, "workflow run changed immutable suite binding")
    ordinal = max(r["native"]["run_attempt"] for r in rows) if surface == "actions" else None
    latest = [r for r in rows if surface != "actions" or r["native"]["run_attempt"] == ordinal]
    instant = max(timeutil.parse_ts(r["observed_at"]) for r in latest)
    latest = [r for r in latest if timeutil.parse_ts(r["observed_at"]) == instant]
    states = {evidence(r, provider) for r in latest}
    current = next(iter(states)) if len(states) == 1 else "UNKNOWN"
    row = min(latest, key=canonical.canonical_bytes); data = row["native"]
    attempts = [{"attempt": r["native"]["run_attempt"] if surface == "actions" else None, "state": evidence(r, provider)} for r in rows]
    attempts = [canonical.loads(b.decode()) for b in sorted({canonical.canonical_bytes(a) for a in attempts})]
    if any(r["coverage"] == "PARTIAL" for r in rows):
        # A partial parent projection cannot prove that its attempt history is
        # complete, even if the visible attempt numbers happen to be contiguous.
        attempts.append({"attempt": None, "state": "UNKNOWN"})
    parent = {"parent_id": PREFIX[surface] + str(data["id"]), "kind": SURFACES[provider][surface],
        "name": data.get("name") or surface, "event": data.get("event") or data.get("source"),
        "current_attempt": ordinal, "current_state": current, "attempts_observed": attempts,
        "attempts_complete": False, "history_state": "UNKNOWN_HISTORY", "url": data.get("html_url") or data.get("web_url") or data.get("url")}
    state, complete = current_history([parent]); parent.update(history_state=state, attempts_complete=complete)
    return parent


def collapse_links(parents, links, project, revision, diagnostics):
    """Only non-branching, acyclic, scope-bound provider evidence can collapse ids."""
    forward, backward, involved = {}, {}, set()
    valid = True
    for link in links:
        fields(link, ("contract", "provider", "forge_instance", "project_id", "revision", "earlier", "later", "status", "evidence_ref"))
        require(link["contract"] == LINK_CONTRACT, "unknown rerun-link lineage")
        require(link["provider"] in SURFACES and link["status"] in ("AVAILABLE", "UNKNOWN", "UNAVAILABLE", "FORBIDDEN", "ERROR"), "unknown rerun-link availability/provider")
        for key in ("forge_instance", "project_id", "revision"): text(link[key])
        if link["evidence_ref"] is not None: text(link["evidence_ref"])
        a, b = reference(link["earlier"], project["provider"]), reference(link["later"], project["provider"])
        scoped = (link["provider"] == project["provider"] and link["forge_instance"] == project["forge_instance"]
            and link["project_id"] == project["immutable_project_id"] and link["revision"] == revision
            and a in parents and b in parents and parents[a]["kind"] == parents[b]["kind"])
        if not scoped or link["status"] != "AVAILABLE" or not isinstance(link["evidence_ref"], str) or not link["evidence_ref"]:
            valid = False; continue
        involved.update((a, b))
        if (a in forward and forward[a] != b) or (b in backward and backward[b] != a) or a == b: valid = False
        forward[a] = b; backward[b] = a
    roots = sorted(involved - set(backward))
    visited, chains = set(), []
    for root in roots:
        chain, cursor = [], root
        while cursor not in visited:
            visited.add(cursor); chain.append(cursor)
            if cursor not in forward: break
            cursor = forward[cursor]
        else:
            valid = False
        chains.append(chain)
    if visited != involved: valid = False
    if not valid:
        diagnostics.add("RERUN_LINK_UNPROVEN_OR_AMBIGUOUS")
        return parents, {}
    output, aliases = dict(parents), {}
    for chain in chains:
        if len(chain) < 2: continue
        # Keep the oldest native key stable; current state comes only from leaf.
        parent = {**parents[chain[-1]], "parent_id": chain[0]}
        parent["current_attempt"] = None
        parent["attempts_observed"] = [{"attempt": None, "state": state} for state in sorted({a["state"] for key in chain for a in parents[key]["attempts_observed"]})]
        state, complete = current_history([parent]); parent.update(history_state=state, attempts_complete=complete)
        for key in chain: output.pop(key)
        output[chain[0]] = parent; aliases[chain[0]] = chain
    return output, aliases


def normalize(value):
    value = canonical_input(value)
    project, at = value["project"], timeutil.parse_ts(value["observed_at"])
    provider = project["provider"]
    start = timeutil.minus_days(at, 14)
    diagnostics, scope, excluded, seen = set(), {}, [], set()
    ordering = "KNOWN"
    for row in value["revisions"]:
        fields(row, ("revision", "committed_at", "default_branch")); ref = text(row["revision"])
        require(ref not in seen, "duplicate immutable revision metadata"); seen.add(ref)
        require(row["default_branch"] is None or type(row["default_branch"]) is bool, "untyped default-branch association")
        if row["default_branch"] is False:
            excluded.append({**row, "reason": "OFF_DEFAULT_BRANCH"}); continue
        if row["default_branch"] is None or row["committed_at"] is None:
            ordering = "UNKNOWN"; diagnostics.add("REVISION_ORDERING_UNAVAILABLE")
            excluded.append({**row, "reason": "ORDERING_UNAVAILABLE"}); continue
        committed = timeutil.parse_ts(row["committed_at"])
        if not start <= committed <= at:
            excluded.append({**row, "reason": "OUTSIDE_WINDOW"}); continue
        scope[ref] = row
    grouped, children, bindings = {}, {}, {}
    for row in value["parents"]:
        evidence(row, provider)
        require(timeutil.parse_ts(row["observed_at"]) <= at, "CI evidence is from after the observation boundary")
        require(row["revision"] in seen, "parent has no immutable revision metadata")
        if row["revision"] in scope:
            key = PREFIX[row["surface"]] + str(row["native"]["id"])
            require(key not in bindings or bindings[key] == row["revision"], "native parent identity changed immutable revision")
            bindings[key] = row["revision"]
            grouped.setdefault(row["revision"], {}).setdefault(key, []).append(row)
    for row in value["children"]:
        evidence(row, provider, child=True)
        require(timeutil.parse_ts(row["observed_at"]) <= at, "child evidence is from after the observation boundary")
        require(row["revision"] in seen, "child has no immutable revision metadata")
        if row["parent"] is not None:
            parent_key = reference(row["parent"], provider)
            require(parent_key not in bindings or bindings[parent_key] == row["revision"], "child parent belongs to another revision")
        children.setdefault(row["revision"], []).append(row)
    links = {}
    for row in value["rerun_links"]:
        require(isinstance(row, dict) and row.get("revision") in scope, "rerun link has no admitted revision")
        links.setdefault(row["revision"], []).append(row)
    records, provenance, units = [], {}, {}
    for ref, revision in sorted(scope.items(), key=lambda pair: (timeutil.parse_ts(pair[1]["committed_at"]), pair[0])):
        rows = grouped.get(ref, {})
        parents = {key: parent_from_snapshots(facts, provider) for key, facts in rows.items()}
        retained_suites = []
        if provider == "github":
            overlap = {}
            for key, facts in rows.items():
                for fact in facts:
                    suite = fact["native"].get("check_suite_id") if fact["surface"] == "actions" else None
                    if suite is not None: overlap.setdefault("github_checks:check_suite:" + str(suite), set()).add(key)
            for suite, actions in sorted(overlap.items()):
                if suite not in parents: continue
                if len(actions) != 1:
                    diagnostics.add("ACTIONS_CHECKS_OVERLAP_AMBIGUOUS"); continue
                target = parents[next(iter(actions))]; other = parents.pop(suite)
                if any(a["state"] == gh.VERIFY_FAIL for a in other["attempts_observed"]) and not any(a["state"] == gh.VERIFY_FAIL for a in target["attempts_observed"]):
                    target["attempts_observed"].append({"attempt": None, "state": gh.VERIFY_FAIL})
                # A newer unresolved suite cannot be resurrected as an older pass.
                latest_suite = max(timeutil.parse_ts(r["observed_at"]) for r in rows[suite])
                latest_actions = max(timeutil.parse_ts(r["observed_at"]) for r in rows[next(iter(actions))])
                if latest_suite > latest_actions and other["current_state"] != target["current_state"]:
                    target["current_state"] = "UNKNOWN"; diagnostics.add("LINKED_SURFACES_DISAGREE")
                retained_suites.append(suite)
        parents, aliases = collapse_links(parents, links.get(ref, []), project, ref, diagnostics)
        unit = "PARENT_AGGREGATE"
        if not parents and children.get(ref):
            # Child snapshots have identity too: earlier terminal states must
            # not overrule a newer pending observation of that same child.
            by_child = {}
            for row in children[ref]: by_child.setdefault(row["native"]["id"], []).append(row)
            states = []
            for facts in by_child.values():
                latest = max(timeutil.parse_ts(r["observed_at"]) for r in facts)
                current = {evidence(r, provider, child=True) for r in facts if timeutil.parse_ts(r["observed_at"]) == latest}
                states.append(next(iter(current)) if len(current) == 1 else "UNKNOWN")
            parents = {"revision-child-aggregate:" + ref: {"parent_id": "revision-child-aggregate:" + ref,
                "kind": "revision_child_aggregate_raw", "name": "child-only fallback", "event": None,
                "current_attempt": None, "current_state": gh.compose_current(states),
                # Raw child failures are not proof a canonical parent failed
                # (allowed-failure jobs exist). Keep them in native provenance.
                "attempts_observed": [{"attempt": None, "state": "UNKNOWN"}],
                "attempts_complete": False, "history_state": "UNKNOWN_HISTORY", "url": None}}
            unit = "REVISION_CHILD_AGGREGATE_RAW"; diagnostics.add("CHILD_ONLY_NONINDEPENDENT")
        ordered = [parents[key] for key in sorted(parents)]
        state, complete = current_history(ordered)
        current = gh.compose_current([p["current_state"] for p in ordered])
        records.append({"revision": ref, "committed_at": revision["committed_at"], "parents": ordered,
            "current_verdict": current, "history_state": state, "historical_contribution": gh.contribution(state),
            "history_provenance": gh.ATTEMPT_LEVEL if ordered and all(p["kind"] == gh.ACTIONS_KIND for p in ordered) else gh.PARENT_LEVEL_ONLY if ordered else None,
            "history_complete": complete})
        units[ref] = unit
        provenance[ref] = {"parent_ids": sorted(parents), "native_parent_ids": sorted(rows), "retained_suites": retained_suites,
            "rerun_aliases": aliases, "child_ids": sorted({r["native"]["id"] for r in children.get(ref, [])}),
            "current_attempts": {p["parent_id"]: {"ordinal": p["current_attempt"], "terminal": p["current_state"] not in ("UNKNOWN", gh.VERIFY_UNRESOLVED), "state": p["current_state"]} for p in ordered}}
    if any(row["coverage"] != "COMPLETE" for row in value["parents"] + value["children"]): diagnostics.add("NATIVE_EVIDENCE_INCOMPLETE")
    if any(p["current_state"] == "UNKNOWN" for record in records for p in record["parents"]): diagnostics.add("CURRENT_PARENT_UNKNOWN")
    decisive = [r for r in records if r["current_verdict"] in (gh.VERIFY_PASS, gh.VERIFY_FAIL)]
    latest = max(decisive, key=lambda r: (timeutil.parse_ts(r["committed_at"]), r["revision"]))["revision"] if decisive else None
    meta = {"contract": CONTRACT, "coverage": "DEGRADED" if diagnostics or value["coverage"] != "COMPLETE" else "COMPLETE",
        "ordering_status": ordering, "latest_decisive_default_branch": "UNKNOWN" if ordering == "UNKNOWN" else latest,
        "verification_units": units, "diagnostics": sorted(diagnostics), "provenance": provenance, "excluded_revisions": excluded}
    return {"contract": CONTRACT, "evidence": value, "records": records, "metadata": meta}


def observations(value, subject):
    normalized = normalize(value); value = normalized["evidence"]
    require(all(subject.get(k) == v for k, v in value["project"].items()), "CI project/subject binding mismatch")
    obs = ObservationSet(subject=deepcopy(subject), observed_at=value["observed_at"])
    common = {"provider": value["project"]["provider"], "collected_at": obs.observed_at, "adapter_version": CONTRACT,
              "source_ref": "native-ci:" + canonical.digest(value)}
    obs.add(Observation(observation_id=NATIVE, status="AVAILABLE", value_type="record", value=value, **common))
    obs.add(Observation(observation_id=PROVENANCE, status="AVAILABLE", value_type="record", value=normalized["metadata"], **common))
    configured = value["configured"]
    obs.add(Observation(observation_id="ci.configured", status="AVAILABLE" if configured is not None else "UNKNOWN", value_type="boolean", value=configured, **common))
    status = "AVAILABLE" if value["coverage"] == "COMPLETE" and normalized["metadata"]["ordering_status"] == "KNOWN" else "PARTIAL"
    obs.add(Observation(observation_id="ci.revision_verdicts_14d", status=status, value_type="series", value=normalized["records"], **common))
    return obs


def admitted_metadata(obs):
    source, metadata = obs.get(NATIVE), obs.get(PROVENANCE)
    require(source is not None and source.good and source.value_type == "record", "native CI evidence unavailable")
    expected = observations(source.value, obs.subject)
    require(expected.observed_at == obs.observed_at, "native CI observation-time mismatch")
    for key in (NATIVE, PROVENANCE, "ci.configured", "ci.revision_verdicts_14d"):
        actual, wanted = obs.get(key), expected.get(key)
        require(actual is not None and canonical.canonical_bytes(actual.to_dict()) == canonical.canonical_bytes(wanted.to_dict()),
                "native CI projection does not replay: " + key)
    return metadata.value
