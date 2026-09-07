"""GitHub adapter against a fake transport: status classification, pagination, CI normalization."""

from datetime import datetime, timezone

import pytest

from devostasis.adapters.github import GitHubAdapter, GitHubClient, LinkageEvidenceError, classify_http_error
from devostasis.config import single_project
from devostasis.normalize import CI_CONFIGURED, CI_REVISIONS, INV_BRANCHES, INV_CRS, INV_ISSUES, INV_TARGETS, derive
from devostasis.observations import AVAILABLE, ERROR, FORBIDDEN, PARTIAL, UNAVAILABLE
from devostasis.vitals import evaluate_all

NOW = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
BASE = "/repos/acme/widget"


class FakeTransport:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, dict(params or {})))
        handler = self.routes.get(path)
        if handler is None:
            return 404, {}, {"message": "Not Found"}
        if callable(handler):
            return handler(params or {})
        return handler


def _repo(has_issues=True):
    return 200, {}, {"id": 42, "full_name": "acme/widget", "default_branch": "main", "visibility": "private", "has_issues": has_issues, "archived": False, "pushed_at": "2026-09-05T10:00:00Z", "html_url": "https://github.com/acme/widget"}


def _commit(sha, when):
    return {"sha": sha, "commit": {"message": f"commit {sha}\n\nbody", "committer": {"date": when}, "author": {"date": when}}}


def _paged(items):
    def handler(params):
        page = int(params.get("page", 1))
        per_page = int(params.get("per_page", 100))
        return 200, {}, items[(page - 1) * per_page: page * per_page]
    return handler


def _routes(**overrides):
    commits = [_commit("c1", "2026-09-04T10:00:00Z"), _commit("c2", "2026-09-01T10:00:00Z"), _commit("c3", "2026-08-20T10:00:00Z")]
    pulls_open = [{"number": 7, "id": 7, "title": "wip", "state": "open", "draft": False, "created_at": "2026-08-25T00:00:00Z", "updated_at": "2026-09-01T00:00:00Z", "merged_at": None, "closed_at": None, "milestone": {"number": 1, "state": "open"}, "user": {"login": "a"}, "html_url": "p7"}]
    pulls_recent = pulls_open + [{"number": 6, "id": 6, "title": "done", "state": "closed", "draft": False, "created_at": "2026-08-28T00:00:00Z", "updated_at": "2026-08-29T00:00:00Z", "merged_at": "2026-08-29T00:00:00Z", "closed_at": "2026-08-29T00:00:00Z", "milestone": None, "user": {"login": "a"}, "html_url": "p6"}]
    issues_open = [{"number": 3, "id": 3, "title": "bug", "state": "open", "created_at": "2026-07-01T00:00:00Z", "updated_at": "2026-07-02T00:00:00Z", "closed_at": None, "labels": [{"name": "bug"}], "user": {"login": "b"}, "html_url": "i3"}]
    runs = [
        {"id": 100, "run_attempt": 2, "head_sha": "c1", "status": "completed", "conclusion": "success", "name": "CI", "event": "push", "html_url": "r100", "workflow_id": 1},
        {"id": 101, "run_attempt": 1, "head_sha": "c2", "status": "completed", "conclusion": "success", "name": "CI", "event": "push", "html_url": "r101", "workflow_id": 1},
        {"id": 102, "run_attempt": 1, "head_sha": "c2", "status": "completed", "conclusion": "skipped", "name": "Docs", "event": "push", "html_url": "r102", "workflow_id": 2},
    ]
    routes = {
        BASE: _repo(),
        f"{BASE}/commits": _paged(commits),
        f"{BASE}/pulls": lambda params: _paged(pulls_open if params.get("state") == "open" else pulls_recent)(params),
        f"{BASE}/issues": lambda params: _paged(issues_open if params.get("state") == "open" else [])(params),
        f"{BASE}/branches": _paged([{"name": "main", "commit": {"sha": "c1"}, "protected": True}, {"name": "feature", "commit": {"sha": "c3"}, "protected": False}]),
        f"{BASE}/milestones": _paged([{"number": 1, "id": 1, "title": "v1", "state": "open", "due_on": "2026-10-30T00:00:00Z", "open_issues": 2, "closed_issues": 1, "html_url": "m1"}]),
        f"{BASE}/releases": (200, {}, []),
        f"{BASE}/actions/workflows": (200, {}, {"total_count": 2, "workflows": []}),
        f"{BASE}/actions/runs": lambda params: (200, {}, {"total_count": len(runs), "workflow_runs": runs if int(params.get("page", 1)) == 1 else []}),
        f"{BASE}/actions/runs/100/attempts/1": (200, {}, {"id": 100, "run_attempt": 1, "status": "completed", "conclusion": "failure"}),
    }
    routes.update(overrides)
    return routes


def _collect(routes, **project):
    transport = FakeTransport(routes)
    client = GitHubClient(transport)
    adapter = GitHubAdapter(client, NOW)
    obs = adapter.collect(single_project("acme/widget", **project))
    return obs, transport, client


def test_full_collection_and_evaluation():
    obs, transport, client = _collect(_routes())
    derive(obs, single_project("acme/widget"))
    assert obs.subject["immutable_project_id"] == "42" and obs.subject["default_branch"] == "main"
    assert obs.value_of("git.default_branch.commits.count_28d") == 3
    assert obs.value_of("forge.change_requests.open_count") == 1
    assert obs.value_of("forge.change_requests.merged_count_28d") == 1
    assert obs.value_of("forge.issues.open_count") == 1 and obs.value_of("forge.issues.stale_open_count_30d") == 1
    assert obs.value_of("git.nondefault_branches.stale_count_30d") == 0
    assert obs.value_of("planning.explicit_targets.capability") == "SUPPORTED"
    assert obs.value_of("planning.linkage.active_change_requests_linked_to_open_target_count_28d") == 1
    revisions = obs.value_of(CI_REVISIONS)
    by_sha = {r["revision"]: r for r in revisions}
    assert set(by_sha) == {"c1", "c2"}
    assert by_sha["c1"]["current_verdict"] == "VERIFY_PASS" and by_sha["c1"]["history_state"] == "FAILURE_OBSERVED"
    assert by_sha["c2"]["current_verdict"] == "VERIFY_PASS" and len(by_sha["c2"]["parents"]) == 2
    assert obs.value_of(CI_CONFIGURED) is True
    bands = {r.vital_id: r.band for r in evaluate_all(obs)}
    assert bands["integrity"] == "SPARSE_MIXED" and bands["pulse"] == "STEADY" and bands["flow"] == "MOVING"
    assert bands["horizon"] == "EXTENDED" and bands["direction"] == "MIXED" and bands["debt"] == "UNINSTRUMENTED"
    assert client.request_count > 0 and not hasattr(obs.receipt, "request_count"), "how evidence was fetched is not part of the receipt (v2)"
    assert "CHECKS_SURFACE_NOT_COLLECTED" in obs.receipt.capability_notes


def test_c2_c3_c7_http_failures_become_explicit_statuses():
    routes = _routes(**{
        f"{BASE}/branches": (403, {}, {"message": "Upgrade to GitHub Pro or make this repository public to enable this feature."}),
        f"{BASE}/milestones": (403, {"x-ratelimit-remaining": "5"}, {"message": "Resource not accessible by integration"}),
        f"{BASE}/pulls": (503, {}, {"message": "Service Unavailable"}),
    })
    obs, _, _ = _collect(routes)
    assert obs.status_of(INV_BRANCHES) == UNAVAILABLE and obs.get(INV_BRANCHES).reason_code == "TIER_UNAVAILABLE"
    assert obs.status_of(INV_TARGETS) == FORBIDDEN
    assert obs.status_of(INV_CRS) == ERROR and obs.get(INV_CRS).reason_code == "PROVIDER_ERROR"
    assert obs.value_of(INV_CRS) is None


def test_issues_disabled_is_unavailable_not_zero():
    routes = _routes(**{BASE: _repo(has_issues=False)})
    obs, transport, _ = _collect(routes)
    assert obs.status_of(INV_ISSUES) == UNAVAILABLE and obs.get(INV_ISSUES).reason_code == "ISSUES_DISABLED"
    assert not any(path.endswith("/issues") for path, _ in transport.calls)


def test_c4_pagination_cap_is_partial(monkeypatch):
    from devostasis.adapters import github as github_module

    monkeypatch.setattr(github_module, "MAX_COMMIT_PAGES", 2)
    many = [_commit(f"s{i:03d}", "2026-09-01T10:00:00Z") for i in range(250)]
    obs, _, _ = _collect(_routes(**{f"{BASE}/commits": _paged(many)}))
    commits = obs.get("git.default_branch.commits_28d")
    assert commits.status == PARTIAL and commits.reason_code == "PAGINATION_CAPPED" and len(commits.value) == 200
    derive(obs, single_project("acme/widget"))
    assert obs.status_of("git.default_branch.commits.count_28d") == PARTIAL
    bands = {r.vital_id: r for r in evaluate_all(obs)}
    assert bands["pulse"].evaluation_status == "DEGRADED" and bands["pulse"].band_semantics == "CONSERVATIVE_LOWER_BOUND"
    assert bands["integrity"].evaluation_status == "DEGRADED"


def test_no_workflows_and_no_check_suites_is_positively_uninstrumented():
    routes = _routes(**{
        f"{BASE}/actions/workflows": (200, {}, {"total_count": 0, "workflows": []}),
        f"{BASE}/commits/c1/check-suites": (200, {}, {"total_count": 0, "check_suites": []}),
        f"{BASE}/commits/c2/check-suites": (200, {}, {"total_count": 0, "check_suites": []}),
    })
    obs, _, _ = _collect(routes)
    assert obs.value_of(CI_CONFIGURED) is False
    assert all(not r["parents"] for r in obs.value_of(CI_REVISIONS))
    assert {r.vital_id: r.band for r in evaluate_all(derive(obs, single_project("acme/widget")))}["integrity"] == "UNINSTRUMENTED"


def test_external_check_suites_are_parent_level_provenance():
    routes = _routes(**{
        f"{BASE}/actions/workflows": (200, {}, {"total_count": 0, "workflows": []}),
        f"{BASE}/commits/c1/check-suites": (200, {}, {"total_count": 1, "check_suites": [{"id": 9, "status": "completed", "conclusion": "failure", "app": {"slug": "circleci"}, "url": "s9", "latest_check_runs_count": 3}]}),
        f"{BASE}/commits/c2/check-suites": (200, {}, {"total_count": 0, "check_suites": []}),
    })
    obs, _, _ = _collect(routes)
    revisions = {r["revision"]: r for r in obs.value_of(CI_REVISIONS)}
    assert revisions["c1"]["history_provenance"] == "PARENT_LEVEL_ONLY" and revisions["c1"]["current_verdict"] == "VERIFY_FAIL"
    assert obs.value_of(CI_CONFIGURED) is True


def test_classify_http_error_table():
    assert classify_http_error(401, {"message": "Bad credentials"}, {}) == (FORBIDDEN, "UNAUTHENTICATED", False)
    assert classify_http_error(403, {"message": "API rate limit exceeded"}, {}) == (ERROR, "RATE_LIMITED", True)
    assert classify_http_error(403, {"message": "x"}, {"x-ratelimit-remaining": "0"}) == (ERROR, "RATE_LIMITED", True)
    assert classify_http_error(404, {}, {}) == (UNAVAILABLE, "NOT_FOUND", False)
    assert classify_http_error(410, {}, {}) == (UNAVAILABLE, "DISABLED", False)
    assert classify_http_error(500, {}, {}) == (ERROR, "PROVIDER_ERROR", True)


def test_planning_source_none_skips_milestone_requests():
    obs, transport, _ = _collect(_routes(), planning={"source": "none"})
    assert obs.status_of(INV_TARGETS) == UNAVAILABLE
    assert not any(path.endswith("/milestones") for path, _ in transport.calls)
    derive(obs, single_project("acme/widget", planning={"source": "none"}))
    assert obs.value_of("planning.explicit_targets.capability") == "UNSUPPORTED"


def test_collection_error_when_repository_is_unreachable():
    import pytest
    from devostasis.adapters.github import CollectionError

    with pytest.raises(CollectionError):
        _collect({BASE: (404, {}, {"message": "Not Found"})})


def test_observation_set_round_trips_through_json(tmp_path):
    obs, _, _ = _collect(_routes())
    path = tmp_path / "obs.json"
    obs.save(path)
    from devostasis.observations import ObservationSet

    loaded = ObservationSet.load(path)
    assert loaded.digest() == obs.digest()


def test_a_full_page_of_releases_is_partial_not_complete():
    """A capped enumeration is never complete evidence, even when nothing failed."""
    from devostasis.adapters.github import MAX_RELEASES
    from devostasis.normalize import INV_RELEASES

    full_page = [
        {"tag_name": f"v{i}", "name": f"release {i}", "published_at": f"2026-09-{i % 28 + 1:02d}T10:00:00Z", "draft": False, "prerelease": False, "html_url": f"r{i}"}
        for i in range(MAX_RELEASES)
    ]
    obs, _, _ = _collect(_routes(**{f"{BASE}/releases": (200, {}, full_page)}))
    item = obs.get(INV_RELEASES)
    assert item.status == PARTIAL and item.reason_code == "PAGINATION_CAPPED"
    assert item.coverage["complete"] is False and item.coverage["limit"] == MAX_RELEASES

    short_page = full_page[:-1]
    obs, _, _ = _collect(_routes(**{f"{BASE}/releases": (200, {}, short_page)}))
    item = obs.get(INV_RELEASES)
    assert item.status == AVAILABLE and item.reason_code is None and item.coverage["complete"] is True


# --------------------------------------------------------------------------- error boundaries (#12 finding 5)


def test_a_register_title_that_is_only_whitespace_is_a_register_error_not_a_crash():
    """`text.strip().splitlines()[0]` raised IndexError, which no boundary caught."""
    from devostasis.adapters.github import RegisterError, parse_targets_register

    items = parse_targets_register({"schema": "devostasis.targets.v1", "targets": [{"id": "T-1", "title": "   "}]})
    assert items[0]["title"] == ""
    try:
        parse_targets_register({"schema": "devostasis.targets.v1", "targets": [{"id": "T-1", "title": 1}]})
    except RegisterError as exc:
        assert "must be a string" in str(exc)
    else:
        raise AssertionError("a non-string target title must be an invalid register")


def test_a_debt_title_of_the_wrong_type_is_a_register_error():
    from devostasis.adapters.github import RegisterError, parse_debt_register

    document = {"schema": "devostasis.debt.v1", "items": [{"id": "D-1", "title": ["not", "a", "string"], "opened": "2026-01-01"}]}
    try:
        parse_debt_register(document)
    except RegisterError as exc:
        assert "D-1" in str(exc)
    else:
        raise AssertionError("a non-string debt title must be an invalid register")


def test_a_provider_title_of_the_wrong_type_is_a_missing_title_not_a_failed_run():
    """Commit messages, change-request and issue titles are payload, not contract."""
    from devostasis.adapters.github import _title

    assert _title(None) == "" and _title("") == "" and _title("   \n  ") == ""
    assert _title(7) == "" and _title(["a"]) == ""
    assert _title("  first line\nsecond") == "first line"


def test_an_invalid_register_reaches_the_snapshot_as_an_error_observation():
    """The contract says INVALID_REGISTER, and only a RegisterError can produce it."""
    import base64
    import json as json_mod

    register = json_mod.dumps({"schema": "devostasis.targets.v1", "targets": [{"id": "T-1", "title": 1}]})
    routes = _routes()
    routes[f"{BASE}/contents/.devostasis/targets.json"] = (
        200,
        {},
        {"type": "file", "encoding": "base64", "content": base64.b64encode(register.encode("utf-8")).decode("ascii")},
    )
    client = GitHubClient(FakeTransport(routes))
    project = single_project("acme/widget", planning={"source": "file", "path": ".devostasis/targets.json"})
    obs = GitHubAdapter(client, NOW).collect(project)
    targets = obs.get(INV_TARGETS)
    assert targets.status == ERROR and targets.reason_code == "INVALID_REGISTER"


def test_a_successful_response_that_is_not_json_becomes_a_declared_provider_failure():
    """HTTP 200 with an unreadable body escaped every handler as a ValueError."""
    import io
    import urllib.request

    from devostasis.adapters.github import ApiFailure, UrllibTransport

    class _Response(io.BytesIO):
        status = 200
        headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    transport = UrllibTransport(token=None)
    original = urllib.request.urlopen
    urllib.request.urlopen = lambda request, timeout=None: _Response(b"<html>maintenance</html>")
    try:
        transport.get("/repos/acme/widget")
    except ApiFailure as exc:
        assert exc.reason_code == "MALFORMED_RESPONSE" and exc.status_code == 200
    else:
        raise AssertionError("a 200 with a non-JSON body must be a declared failure")
    finally:
        urllib.request.urlopen = original


# --------------------------------------------------------------------------- linkage evidence (PV-REV-PR-015)


def _pull(number=7, **fields):
    base = {
        "number": number,
        "id": number,
        "title": "wip",
        "body": None,
        "state": "open",
        "draft": False,
        "created_at": "2026-08-25T00:00:00Z",
        "updated_at": "2026-09-01T00:00:00Z",
        "merged_at": None,
        "closed_at": None,
        "milestone": None,
        "user": {"login": "a"},
        "html_url": "p7",
    }
    base.update(fields)
    return base


def _file_planning_project():
    return single_project("acme/widget", planning={"source": "file", "path": ".devostasis/targets.json", "link_marker": "Target:"})


def _observe(routes, project):
    return GitHubAdapter(GitHubClient(FakeTransport(routes)), NOW).collect(project)


@pytest.mark.parametrize("field, value", [("title", 7), ("title", ["a"]), ("body", {"a": 1}), ("body", 3.5)])
def test_unreadable_linkage_evidence_is_declared_not_read_as_unlinked(field, value):
    """`Target: <id>` lives in the title and the body, so payload of the wrong type there is not an absent link."""
    routes = _routes(**{f"{BASE}/pulls": _paged([_pull(**{field: value})])})
    try:
        _observe(routes, _file_planning_project())
    except LinkageEvidenceError as exc:
        assert "#7" in str(exc) and field in str(exc)
    else:
        raise AssertionError(f"a {type(value).__name__} {field} must not silently become an unlinked change request")


def test_a_change_request_with_no_marker_is_unlinked_and_that_is_not_an_error():
    """The distinction the error exists to preserve: absent evidence is a fact, unreadable evidence is not."""
    routes = _routes(**{f"{BASE}/pulls": _paged([_pull(title="nothing to see", body="no marker here")])})
    item = _observe(routes, _file_planning_project()).get(INV_CRS)
    assert item.status == AVAILABLE
    assert item.value[0]["target_refs"] == [] and item.value[0]["target_id"] is None


def test_a_marker_in_the_body_still_links_after_the_repair():
    routes = _routes(**{f"{BASE}/pulls": _paged([_pull(title="a change", body="Target: B1")])})
    item = _observe(routes, _file_planning_project()).get(INV_CRS)
    assert item.value[0]["target_id"] == "B1"


def test_a_milestone_without_a_number_cannot_name_the_target_it_links_to():
    """Under planning.source=milestones the milestone *is* the link; a malformed one is unreadable evidence."""
    routes = _routes(**{f"{BASE}/pulls": _paged([_pull(milestone={"state": "open"})])})
    try:
        _observe(routes, single_project("acme/widget"))
    except LinkageEvidenceError as exc:
        assert "#7" in str(exc)
    else:
        raise AssertionError("a milestone with no number must not be read as no milestone")


def test_unreadable_linkage_evidence_is_a_collection_error_so_one_project_fails_alone():
    """It reaches run_project's declared boundary, not run_all's catch-all for the unanticipated."""
    from devostasis.adapters.github import CollectionError

    assert issubclass(LinkageEvidenceError, CollectionError)


# --------------------------------------------------------------------------- register shapes (#12 finding 5)


@pytest.mark.parametrize(
    "document, expected",
    [
        ([], "must be an object"),
        ("not a document", "must be an object"),
        ({"schema": "devostasis.targets.v1", "targets": {"T-1": "open"}}, "requires a targets list"),
        ({"schema": "devostasis.targets.v1", "targets": [1]}, "string id"),
        ({"schema": "devostasis.targets.v1", "targets": [{"id": "T-1", "title": "x", "due": "the third of never"}]}, "invalid date"),
        ({"schema": "devostasis.targets.v1", "targets": [{"id": "T-1", "title": "x", "due": 20260101}]}, "date must be a string"),
    ],
)
def test_a_register_of_the_wrong_shape_or_with_an_invalid_date_is_an_invalid_register(document, expected):
    from devostasis.adapters.github import RegisterError, parse_targets_register

    try:
        parse_targets_register(document)
    except RegisterError as exc:
        assert expected in str(exc)
    else:
        raise AssertionError(f"{document!r} must not parse as a valid register")


def test_an_invalid_date_reaches_the_snapshot_as_an_error_observation():
    """The whole point of RegisterError: it survives the collector as a status, not as a crash."""
    import base64
    import json as json_mod

    register = json_mod.dumps({"schema": "devostasis.targets.v1", "targets": [{"id": "T-1", "title": "x", "due": "the third of never"}]})
    routes = _routes()
    routes[f"{BASE}/contents/.devostasis/targets.json"] = (
        200,
        {},
        {"type": "file", "encoding": "base64", "content": base64.b64encode(register.encode("utf-8")).decode("ascii")},
    )
    targets = _observe(routes, _file_planning_project()).get(INV_TARGETS)
    assert targets.status == ERROR and targets.reason_code == "INVALID_REGISTER"
