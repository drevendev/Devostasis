"""A successful answer of the wrong shape is a declared failure of that inventory, never a Python exception.

The research audits of 2026-09-23 (PV-AUDIT-GITHUB-REPO/COMMITS/CR/ISSUES/BRANCH/RELEASE/CI-PAYLOAD-001)
named the family the review of PR #29 found one member of: every collector
dereferenced its 200 payload after the boundary that turns failed requests
into observations, so a scalar row, a missing field or an unreadable
timestamp escaped as AttributeError, KeyError, TypeError or ValueError and the
project produced no bundle. A probe over the collectors reproduced twenty-six
such shapes before the repair. Alongside: register states outside the
vocabulary (PV-AUDIT-REGISTER-STATE-001), retry headers that overflow
(PV-AUDIT-GITHUB-RETRY-HEADER-001), a redirect that would carry the token
elsewhere (PV-AUDIT-GITHUB-REDIRECT-AUTH-001), a cache entry that no longer
hashes to its digest (PV-AUDIT-GITHUB-CACHE-INTEGRITY-001), and JSON the
canonical profile excludes (PV-AUDIT-CANONICAL-*-001).
"""

from __future__ import annotations

import base64
import json
import urllib.request
from datetime import datetime, timezone

import pytest

from devostasis import canonical
from devostasis.adapters.cache import ConditionalCache
from devostasis.adapters.github import (
    ApiFailure,
    CollectionError,
    GitHubAdapter,
    GitHubClient,
    RedirectRefused,
    RegisterError,
    RetryPolicy,
    UrllibTransport,
    _SameOriginRedirects,
    parse_debt_register,
    parse_targets_register,
    retry_after_seconds,
)
from devostasis.config import single_project
from devostasis.normalize import CI_CONFIGURED, CI_REVISIONS, INV_BRANCHES, INV_COMMITS, INV_CRS, INV_ISSUES, INV_RELEASES, INV_TARGETS
from devostasis.observations import AVAILABLE, ERROR, PARTIAL
from test_github_adapter import BASE, FakeTransport, _commit, _paged, _repo, _routes

NOW = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
SUITES_EMPTY = {
    f"{BASE}/actions/workflows": (200, {}, {"total_count": 0, "workflows": []}),
    f"{BASE}/commits/c1/check-suites": (200, {}, {"total_count": 0, "check_suites": []}),
    f"{BASE}/commits/c2/check-suites": (200, {}, {"total_count": 0, "check_suites": []}),
}


def _collect(routes, **project):
    client = GitHubClient(FakeTransport(routes), sleep=lambda seconds: None)
    return GitHubAdapter(client, NOW).collect(single_project("acme/widget", **project))


def _pull(**fields):
    base = {"number": 7, "id": 7, "title": "wip", "state": "open", "draft": False, "created_at": "2026-08-25T00:00:00Z", "updated_at": "2026-09-01T00:00:00Z", "merged_at": None, "closed_at": None, "milestone": None, "user": {"login": "a"}, "html_url": "p7"}
    base.update(fields)
    return base


def _issue(**fields):
    base = {"number": 3, "id": 3, "title": "bug", "state": "open", "created_at": "2026-07-01T00:00:00Z", "updated_at": "2026-07-02T00:00:00Z", "closed_at": None, "labels": [{"name": "bug"}], "user": {"login": "b"}, "html_url": "i3"}
    base.update(fields)
    return base


ROWS = {
    INV_COMMITS: [
        ("scalar row", {f"{BASE}/commits": _paged([1, 2])}),
        ("no sha", {f"{BASE}/commits": _paged([{"commit": {"committer": {"date": "2026-09-04T10:00:00Z"}}}])}),
        ("commit is a string", {f"{BASE}/commits": _paged([{"sha": "c1", "commit": "x"}])}),
        ("committer is a string", {f"{BASE}/commits": _paged([{"sha": "c1", "commit": {"committer": "me"}}])}),
        ("date unreadable", {f"{BASE}/commits": _paged([{"sha": "c1", "commit": {"committer": {"date": "yesterday"}}}])}),
        ("no date at all", {f"{BASE}/commits": _paged([{"sha": "c1", "commit": {"message": "x"}}])}),
    ],
    INV_CRS: [
        ("scalar row", {f"{BASE}/pulls": _paged(["seven"])}),
        ("no number", {f"{BASE}/pulls": _paged([{k: v for k, v in _pull().items() if k != "number"}])}),
        ("text number", {f"{BASE}/pulls": _paged([_pull(number="seven")])}),
        ("no updated_at", {f"{BASE}/pulls": _paged([{k: v for k, v in _pull().items() if k != "updated_at"}])}),
        ("updated_at unreadable", {f"{BASE}/pulls": _paged([_pull(updated_at="soon")])}),
        ("created_at unreadable", {f"{BASE}/pulls": _paged([_pull(created_at=20260825)])}),
        ("draft is a string", {f"{BASE}/pulls": _paged([_pull(draft="false")])}),
        ("user is a string", {f"{BASE}/pulls": _paged([_pull(user="a")])}),
    ],
    INV_ISSUES: [
        ("scalar row", {f"{BASE}/issues": lambda params: _paged(["three"] if params.get("state") == "open" else [])(params)}),
        ("no number", {f"{BASE}/issues": lambda params: _paged([{k: v for k, v in _issue().items() if k != "number"}] if params.get("state") == "open" else [])(params)}),
        ("labels is a string", {f"{BASE}/issues": lambda params: _paged([_issue(labels="bug")] if params.get("state") == "open" else [])(params)}),
        ("label without a name", {f"{BASE}/issues": lambda params: _paged([_issue(labels=[{"color": "red"}])] if params.get("state") == "open" else [])(params)}),
        ("user is a list", {f"{BASE}/issues": lambda params: _paged([_issue(user=["b"])] if params.get("state") == "open" else [])(params)}),
        ("timestamp unreadable", {f"{BASE}/issues": lambda params: _paged([_issue(updated_at="never")] if params.get("state") == "open" else [])(params)}),
    ],
    INV_BRANCHES: [
        ("scalar row", {f"{BASE}/branches": _paged(["main", "feature"])}),
        ("no name", {f"{BASE}/branches": _paged([{"commit": {"sha": "c3"}}])}),
        ("commit is a string", {f"{BASE}/branches": _paged([{"name": "feature", "commit": "c3"}])}),
        ("commit without sha", {f"{BASE}/branches": _paged([{"name": "feature", "commit": {}}])}),
        ("protected is a string", {f"{BASE}/branches": _paged([{"name": "feature", "commit": {"sha": "c3"}, "protected": "false"}])}),
    ],
    INV_TARGETS: [
        ("scalar row", {f"{BASE}/milestones": _paged([1])}),
        ("no number", {f"{BASE}/milestones": _paged([{"id": 1, "title": "v1", "state": "open"}])}),
        ("open_issues is text", {f"{BASE}/milestones": _paged([{"number": 1, "id": 1, "title": "v1", "state": "open", "open_issues": "many"}])}),
        ("due_on unreadable", {f"{BASE}/milestones": _paged([{"number": 1, "id": 1, "title": "v1", "state": "open", "due_on": "someday"}])}),
    ],
    INV_RELEASES: [
        ("scalar row", {f"{BASE}/releases": (200, {}, ["v1"])}),
        ("published_at unreadable", {f"{BASE}/releases": (200, {}, [{"tag_name": "v1", "draft": False, "prerelease": False, "published_at": "never"}])}),
        ("published release without a date", {f"{BASE}/releases": (200, {}, [{"tag_name": "v1", "draft": False, "prerelease": False, "published_at": None}])}),
        ("draft is a string", {f"{BASE}/releases": (200, {}, [{"tag_name": "v1", "draft": "false", "prerelease": False, "published_at": "2026-09-01T10:00:00Z"}])}),
        ("prerelease is a string", {f"{BASE}/releases": (200, {}, [{"tag_name": "v1", "draft": False, "prerelease": "false", "published_at": "2026-09-01T10:00:00Z"}])}),
        ("no tag", {f"{BASE}/releases": (200, {}, [{"draft": False, "prerelease": False, "published_at": "2026-09-01T10:00:00Z"}])}),
    ],
    CI_REVISIONS: [
        ("scalar run", {f"{BASE}/actions/runs": (200, {}, {"total_count": 1, "workflow_runs": [1]})}),
        ("run without head_sha", {f"{BASE}/actions/runs": (200, {}, {"total_count": 1, "workflow_runs": [{"id": 5, "run_attempt": 1, "status": "completed", "conclusion": "success"}]})}),
        ("run without id", {f"{BASE}/actions/runs": (200, {}, {"total_count": 1, "workflow_runs": [{"head_sha": "c1", "run_attempt": 2, "status": "completed", "conclusion": "success"}]})}),
        ("run_attempt is text", {f"{BASE}/actions/runs": (200, {}, {"total_count": 1, "workflow_runs": [{"id": 5, "head_sha": "c1", "run_attempt": "two", "status": "completed", "conclusion": "success"}]})}),
        ("runs without the list", {f"{BASE}/actions/runs": (200, {}, {"total_count": 1})}),
        ("attempt is a list", {f"{BASE}/actions/runs/100/attempts/1": (200, {}, [])}),
        ("attempt of another run", {f"{BASE}/actions/runs/100/attempts/1": (200, {}, {"id": 999, "run_attempt": 1, "status": "completed", "conclusion": "failure"})}),
        ("attempt with another number", {f"{BASE}/actions/runs/100/attempts/1": (200, {}, {"id": 100, "run_attempt": 2, "status": "completed", "conclusion": "failure"})}),
    ],
}
CASES = [(inventory, name, overrides) for inventory, cases in ROWS.items() for name, overrides in cases]


@pytest.mark.parametrize("inventory, name, overrides", CASES, ids=[f"{inventory.split('.')[1]}-{name}" for inventory, name, _ in CASES])
def test_a_malformed_successful_row_is_a_declared_failure_of_that_inventory_alone(inventory, name, overrides):
    obs = _collect(_routes(**overrides))
    item = obs.get(inventory)
    assert item.status == ERROR and item.reason_code == "UNEXPECTED_PAYLOAD", (inventory, name, item.reason_code)
    assert item.value is None, "nothing is coerced, defaulted or skipped in its place"
    untouched = [oid for oid in (INV_COMMITS, INV_CRS, INV_ISSUES, INV_BRANCHES, INV_RELEASES) if oid != inventory]
    if inventory == INV_COMMITS:
        untouched.remove(INV_BRANCHES) if INV_BRANCHES in untouched else None
    for oid in untouched:
        assert obs.status_of(oid) in (AVAILABLE, PARTIAL), f"{oid} was still collected"


def test_an_unreadable_commit_inventory_leaves_verification_unknown_not_uninstrumented():
    obs = _collect(_routes(**{f"{BASE}/commits": _paged([{"sha": "c1", "commit": "x"}])}))
    assert obs.get(INV_COMMITS).reason_code == "UNEXPECTED_PAYLOAD"
    assert obs.status_of(CI_CONFIGURED) == "UNKNOWN" and obs.status_of(CI_REVISIONS) == "UNKNOWN"


def test_a_head_detail_that_cannot_be_read_leaves_the_head_unresolved_not_the_inventory_failed():
    """GH-BRANCH-PAYLOAD-05..07: the branch row is fine, its head is not; the inventory is PARTIAL."""
    routes = _routes(**{f"{BASE}/branches": _paged([{"name": "feature", "commit": {"sha": "zz"}, "protected": False}]), f"{BASE}/commits/zz": (200, {}, [])})
    item = _collect(routes).get(INV_BRANCHES)
    assert item.status == PARTIAL and item.reason_code == "BRANCH_HEADS_UNRESOLVED"
    assert item.value[0]["head_committed_at"] is None, "never false stale, never false fresh"
    routes[f"{BASE}/commits/zz"] = (200, {}, {"sha": "zz", "commit": {"committer": {"date": "the other day"}}})
    item = _collect(routes).get(INV_BRANCHES)
    assert item.status == PARTIAL and item.value[0]["head_committed_at"] is None


def test_a_check_suite_answer_of_the_wrong_shape_is_a_declared_failure_not_zero_suites():
    """GH-CI-PAYLOAD-06..09: a missing list, a scalar suite, a suite without an id or a count nobody sent."""
    for body in ([], {"total_count": 0}, {"total_count": 1, "check_suites": [1]}, {"total_count": 1, "check_suites": [{"status": "completed", "conclusion": "success", "app": {"slug": "x"}, "latest_check_runs_count": 1}]}, {"total_count": 1, "check_suites": [{"id": 9, "status": "completed", "conclusion": "success", "app": {"slug": "x"}}]}, {"total_count": 1, "check_suites": [{"id": 9, "status": "completed", "conclusion": "success", "app": "x", "latest_check_runs_count": 1}]}):
        routes = _routes(**dict(SUITES_EMPTY, **{f"{BASE}/commits/c1/check-suites": (200, {}, body)}))
        obs = _collect(routes)
        assert obs.get(CI_CONFIGURED).status == ERROR and obs.get(CI_CONFIGURED).reason_code == "UNEXPECTED_PAYLOAD", body
        assert obs.get(CI_REVISIONS).status == ERROR and obs.get(CI_REVISIONS).reason_code == "UNEXPECTED_PAYLOAD", body
    routes = _routes(**SUITES_EMPTY)
    obs = _collect(routes)
    assert obs.value_of(CI_CONFIGURED) is False, "a valid empty list is still the one positive zero-suite case"


@pytest.mark.parametrize(
    "meta, reason",
    [
        ([1, 2], "not an object"),
        ({k: v for k, v in _repo()[2].items() if k != "default_branch"}, "default_branch"),
        (dict(_repo()[2], default_branch=""), "default_branch"),
        (dict(_repo()[2], default_branch=None), "default_branch"),
        ({k: v for k, v in _repo()[2].items() if k != "id"}, "id"),
        (dict(_repo()[2], id="42"), "id"),
        (dict(_repo()[2], id=True), "id"),
        (dict(_repo()[2], has_issues="false"), "has_issues"),
        (dict(_repo()[2], archived="false"), "archived"),
        (dict(_repo()[2], pushed_at="last week"), "pushed_at"),
    ],
    ids=["list", "no default branch", "empty default branch", "null default branch", "no id", "text id", "boolean id", "text has_issues", "text archived", "unreadable pushed_at"],
)
def test_repository_metadata_that_does_not_establish_the_routing_facts_is_a_declared_collection_failure(meta, reason):
    """GH-REPO-PAYLOAD-01..06: no guessed `main`, no truthiness of a string, no identity from nothing."""
    routes = _routes(**{BASE: (200, {}, meta)})
    transport = FakeTransport(routes)
    with pytest.raises(CollectionError) as failure:
        GitHubAdapter(GitHubClient(transport), NOW).collect(single_project("acme/widget"))
    assert "UNEXPECTED_PAYLOAD" in str(failure.value) and reason in str(failure.value)
    assert not any(path.endswith("/commits") for path, _ in transport.calls), "nothing was collected on a guessed branch"


def test_repository_metadata_with_no_push_yet_is_accepted():
    obs = _collect(_routes(**{BASE: (200, {}, dict(_repo()[2], pushed_at=None))}))
    assert obs.get("forge.repository.metadata").value["pushed_at"] is None


def test_a_malformed_repository_in_a_fleet_run_costs_one_outcome_and_the_next_project_still_runs(tmp_path, monkeypatch):
    """GH-REPO-PAYLOAD-08: the declared failure reaches run_project's boundary, not run_all's catch-all."""
    from devostasis import runner
    from devostasis.config import Config
    from devostasis.history import FilesystemHistoryStore

    routes = _routes(**{BASE: (200, {}, [])})
    routes["/repos/acme/fine"] = _repo()
    for path, handler in list(_routes().items()):
        routes[path.replace(BASE, "/repos/acme/fine")] = handler
    monkeypatch.setattr(runner, "UrllibTransport", lambda token, user_agent=None: FakeTransport(routes))
    config = Config(config_version="1", store_path=str(tmp_path), projects=(single_project("acme/widget", config_version="1"), single_project("acme/fine", config_version="1")))
    outcomes = runner.run_all(config, FilesystemHistoryStore(tmp_path), None, NOW)
    assert not outcomes[0].ok and "UNEXPECTED_PAYLOAD" in outcomes[0].error and "AttributeError" not in outcomes[0].error
    assert outcomes[1].ok


def test_a_valid_draft_release_without_a_date_is_ignored_and_valid_rows_keep_their_order():
    """GH-RELEASE-PAYLOAD-08."""
    rows = [
        {"tag_name": "v2", "name": "two", "draft": True, "prerelease": False, "published_at": None, "html_url": "r2"},
        {"tag_name": "v1", "name": "one", "draft": False, "prerelease": True, "published_at": "2026-09-01T10:00:00Z", "html_url": "r1"},
        {"tag_name": "v0", "name": "zero", "draft": False, "prerelease": False, "published_at": "2026-08-01T10:00:00Z", "html_url": "r0"},
    ]
    item = _collect(_routes(**{f"{BASE}/releases": (200, {}, rows)})).get(INV_RELEASES)
    assert item.status == AVAILABLE and [r["tag"] for r in item.value] == ["v0", "v1"]
    assert item.value[1]["prerelease"] is True


def test_a_register_of_the_wrong_size_type_is_a_declared_failure():
    routes = _routes()
    routes[f"{BASE}/contents/.devostasis/targets.json"] = (200, {}, {"type": "file", "size": "big", "encoding": "base64", "content": "e30="})
    item = _collect(routes, planning={"source": "file", "path": ".devostasis/targets.json"}).get(INV_TARGETS)
    assert item.status == ERROR and item.reason_code == "UNEXPECTED_PAYLOAD"


# --------------------------------------------------------------------------- register state (PV-AUDIT-REGISTER-STATE-001)


@pytest.mark.parametrize("value, expected", [("open", "OPEN"), (" Open ", "OPEN"), (None, "OPEN"), ("", "OPEN"), ("closed", "CLOSED"), ("done", "CLOSED"), ("resolved", "CLOSED"), ("cancelled", "CLOSED"), ("canceled", "CLOSED"), ("CLOSED", "CLOSED")])
def test_reg_state_01_02_the_documented_vocabulary_is_read(value, expected):
    entry = {"id": "T-1", "title": "x"}
    if value is not None:
        entry["state"] = value
    assert parse_targets_register({"schema": "devostasis.targets.v1", "targets": [entry]})[0]["state"] == expected


@pytest.mark.parametrize("value", ["clsoed", "garbage", 17, ["open"], {"state": "open"}, False, True])
def test_reg_state_03_04_06_07_a_state_outside_the_vocabulary_is_an_invalid_register_not_an_open_item(value):
    with pytest.raises(RegisterError, match="state"):
        parse_targets_register({"schema": "devostasis.targets.v1", "targets": [{"id": "T-1", "title": "x", "state": value}]})
    with pytest.raises(RegisterError, match="state"):
        parse_debt_register({"schema": "devostasis.debt.v1", "items": [{"id": "D-1", "title": "x", "opened": "2026-01-01", "state": value}]})


def test_reg_state_05_08_the_collectors_turn_an_invalid_state_into_error_invalid_register():
    targets = json.dumps({"schema": "devostasis.targets.v1", "targets": [{"id": "T-1", "title": "x", "state": "clsoed"}]})
    debt = json.dumps({"schema": "devostasis.debt.v1", "items": [{"id": "D-1", "title": "x", "opened": "2026-01-01", "state": 17}]})
    routes = _routes()
    routes[f"{BASE}/contents/.devostasis/targets.json"] = (200, {}, {"type": "file", "size": len(targets), "encoding": "base64", "content": base64.b64encode(targets.encode()).decode()})
    routes[f"{BASE}/contents/.devostasis/debt.json"] = (200, {}, {"type": "file", "size": len(debt), "encoding": "base64", "content": base64.b64encode(debt.encode()).decode()})
    obs = _collect(routes, planning={"source": "file", "path": ".devostasis/targets.json"}, debt={"source": "file", "path": ".devostasis/debt.json", "mapping_version": "1"})
    assert obs.get(INV_TARGETS).status == ERROR and obs.get(INV_TARGETS).reason_code == "INVALID_REGISTER"
    assert obs.get("debt.register.inventory").status == ERROR and obs.get("debt.register.inventory").reason_code == "INVALID_REGISTER"


# --------------------------------------------------------------------------- retry headers (PV-AUDIT-GITHUB-RETRY-HEADER-001)


@pytest.mark.parametrize("raw", ["inf", "-inf", "nan", "1e10000", "soon", "", "1e400"])
def test_gh_retry_header_01_03_an_unreadable_wait_hint_is_no_hint(raw):
    assert retry_after_seconds({"retry-after": raw}) is None or raw == ""
    assert retry_after_seconds({"x-ratelimit-remaining": "0", "x-ratelimit-reset": raw}, now=0) is None or raw == ""


def test_gh_retry_header_valid_values_still_read():
    assert retry_after_seconds({"retry-after": "2.7"}) == 2
    assert retry_after_seconds({"x-ratelimit-remaining": "0", "x-ratelimit-reset": "100"}, now=40) == 60


def test_gh_retry_header_04_06_a_malformed_hint_takes_the_bounded_backoff_and_ends_in_the_declared_status():
    waits: list[float] = []
    answers = iter([(503, {"retry-after": "inf"}, {"message": "later"}), (200, {}, [])])
    routes = _routes(**{f"{BASE}/releases": lambda params: next(answers)})
    client = GitHubClient(FakeTransport(routes), retry=RetryPolicy(attempts=3), sleep=waits.append)
    obs = GitHubAdapter(client, NOW).collect(single_project("acme/widget"))
    assert obs.status_of(INV_RELEASES) == AVAILABLE and waits == [1], "one deterministic backoff, then the answer"

    always = lambda params: (503, {"retry-after": "1e10000"}, {"message": "later"})  # noqa: E731
    client = GitHubClient(FakeTransport(_routes(**{f"{BASE}/releases": always})), retry=RetryPolicy(attempts=2), sleep=waits.append)
    item = GitHubAdapter(client, NOW).collect(single_project("acme/widget")).get(INV_RELEASES)
    assert item.status == ERROR and item.reason_code == "PROVIDER_ERROR"

    limited = lambda params: (403, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "inf"}, {"message": "API rate limit exceeded"})  # noqa: E731
    client = GitHubClient(FakeTransport(_routes(**{f"{BASE}/releases": limited})), retry=RetryPolicy(attempts=2), sleep=waits.append)
    item = GitHubAdapter(client, NOW).collect(single_project("acme/widget")).get(INV_RELEASES)
    assert item.status == ERROR and item.reason_code == "RATE_LIMITED"


# --------------------------------------------------------------------------- redirects (PV-AUDIT-GITHUB-REDIRECT-AUTH-001)


def _redirect(handler, url):
    request = urllib.request.Request("https://api.github.com/repos/acme/widget", method="GET")
    request.add_header("Authorization", "Bearer secret")
    return handler.redirect_request(request, None, 301, "Moved", {"location": url}, url)


def test_gh_redirect_auth_a_redirect_to_another_origin_is_refused_and_the_token_never_leaves():
    handler = _SameOriginRedirects("https://api.github.com")
    for url in ("https://evil.example/repos/acme/widget", "http://api.github.com/repos/acme/widget", "https://api.github.com.evil.example/x", "https://api.github.com:8443/x"):
        with pytest.raises(RedirectRefused):
            _redirect(handler, url)


def test_gh_redirect_auth_a_same_origin_redirect_is_followed_with_the_credential():
    handler = _SameOriginRedirects("https://api.github.com")
    followed = _redirect(handler, "https://api.github.com/repositories/42")
    assert followed.full_url == "https://api.github.com/repositories/42"
    assert followed.get_header("Authorization") == "Bearer secret", "a renamed repository still resolves"


def test_gh_redirect_auth_the_origin_is_the_configured_api_base():
    transport = UrllibTransport(token="t", api_base="https://ghe.example.com/api/v3/")
    assert transport.origin == "https://ghe.example.com"
    with pytest.raises(RedirectRefused):
        _redirect(_SameOriginRedirects(transport.origin), "https://api.github.com/x")


def test_gh_redirect_auth_a_refused_redirect_is_a_declared_transport_failure():
    transport = UrllibTransport(token="t")

    def refuse(request):
        raise RedirectRefused("redirect to https://evil.example refused")

    transport._open = refuse
    with pytest.raises(ApiFailure) as failure:
        transport.get("/repos/acme/widget")
    assert failure.value.reason_code == "REDIRECT_REFUSED"


# --------------------------------------------------------------------------- cache integrity (PV-AUDIT-GITHUB-CACHE-INTEGRITY-001)


def _cache_file(tmp_path, entries):
    path = tmp_path / "etags.json"
    path.write_text(json.dumps({"schema": "devostasis.http-cache.v2", "entries": entries}), encoding="utf-8")
    return path


def _entry(body, etag='"e"', used=1):
    cache = ConditionalCache(None)
    cache.store("k", etag, body)
    entry = dict(cache._entries["k"])
    entry["used"] = used
    return entry


def test_gh_cache_integrity_01_02_05_unreadable_metadata_is_a_miss_never_an_exception(tmp_path):
    entries = {
        "bad-used": dict(_entry({"n": 1}), used="not-int"),
        "no-etag": dict(_entry({"n": 1}), etag=""),
        "non-string-etag": dict(_entry({"n": 1}), etag=7),
        "good": _entry({"n": 2}),
    }
    cache = ConditionalCache(_cache_file(tmp_path, entries))
    assert cache.etag_for("good") == '"e"' and cache.body_for("good") == {"n": 2}
    assert cache.etag_for("bad-used") is None and cache.etag_for("no-etag") is None and cache.etag_for("non-string-etag") is None
    assert cache.discarded == 3
    foreign = tmp_path / "old.json"
    foreign.write_text(json.dumps({"schema": "devostasis.http-cache.v1", "entries": {"k": {"etag": '"e"', "body": {"n": 1}, "used": 1}}}), encoding="utf-8")
    assert len(ConditionalCache(foreign)) == 0, "a previous envelope version is a safe miss"


def test_gh_cache_integrity_03_07_a_body_that_no_longer_hashes_to_its_digest_is_not_replayed(tmp_path):
    tampered = _entry({"n": 1})
    tampered["body"] = {"n": 999}
    cache = ConditionalCache(_cache_file(tmp_path, {"k": tampered}))
    assert cache.etag_for("k") is None and cache.body_for("k") is None


def test_gh_cache_integrity_04_06_a_304_over_an_invalid_entry_refetches_once_and_a_valid_one_replays(tmp_path):
    body = {"id": 42, "full_name": "acme/widget", "default_branch": "main", "visibility": "public", "has_issues": True, "archived": False, "pushed_at": None, "html_url": "u"}
    valid = _entry(body, etag='"v1"')
    cache = ConditionalCache(_cache_file(tmp_path, {"/repos/acme/widget": valid}))
    calls: list[tuple[str, dict]] = []

    class Conditional(FakeTransport):
        def get(self, path, params=None, headers=None):
            calls.append((path, dict(headers or {})))
            if path == "/repos/acme/widget" and headers and headers.get("If-None-Match") == '"v1"':
                return 304, {}, None
            return 200, {"etag": '"v2"'}, body

    client = GitHubClient(Conditional({}), cache=cache)
    assert client.get("/repos/acme/widget") == body and client.conditional_hits == 1 and len(calls) == 1

    cache._entries["/repos/acme/widget"]["body"] = {"forged": True}
    client = GitHubClient(Conditional({}), cache=cache)
    assert client.get("/repos/acme/widget") == body, "only the provider's answer is consumed"
    assert client.conditional_hits == 0 and len(calls) == 3 and "If-None-Match" not in calls[-1][1], "exactly one unconditional refetch"


# --------------------------------------------------------------------------- canonical decoding (PV-AUDIT-CANONICAL-*-001)


@pytest.mark.parametrize("text", ["NaN", "Infinity", "-Infinity", '{"x": [1, NaN]}', "1.5", "1.0", "-0.0", "1e3", '{"x": [1, 2.25]}', "1e400", "1e-400"])
def test_canon_nonfinite_and_decimal_tokens_reject_at_the_decoder(text, tmp_path):
    with pytest.raises(canonical.CanonicalizationError):
        canonical.loads(text)
    path = tmp_path / "v.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(canonical.CanonicalizationError):
        canonical.load_file(path)


def test_canon_decimal_07_integers_of_any_size_stay_integers():
    assert canonical.loads("123456789012345678901234567890") == 123456789012345678901234567890
    assert canonical.loads('{"a": [0, -1, 42]}') == {"a": [0, -1, 42]}


@pytest.mark.parametrize("text", ['{"a": 1, "a": 1}', '{"schema": "x", "b": {"k": 1, "k": 2}}', '[{"a": 1, "a": 2}]'])
def test_canon_json_parser_a_member_named_twice_is_rejected_not_collapsed(text):
    with pytest.raises(canonical.CanonicalizationError, match="named twice"):
        canonical.loads(text)


@pytest.mark.parametrize("text", ['"\\ud800"', '"\\udc00"', '{"x": ["ok", "\\ud800"]}', '{"\\udc00": 1}'])
def test_canon_unicode_01_04_an_unpaired_surrogate_is_rejected(text):
    with pytest.raises(canonical.CanonicalizationError, match="surrogate"):
        canonical.loads(text)


def test_canon_unicode_05_08_a_valid_pair_and_ordinary_unicode_survive():
    assert canonical.loads('"\\ud83d\\ude00"') == "\U0001F600"
    assert canonical.canonical_bytes({"s": "\U0001F600 ü"}) == '{"s":"\U0001F600 ü"}'.encode("utf-8")


def test_canon_unicode_06_07_a_direct_surrogate_value_or_key_is_a_canonicalization_error_not_a_unicode_error():
    with pytest.raises(canonical.CanonicalizationError):
        canonical.canonical_bytes({"s": "\ud800"})
    with pytest.raises(canonical.CanonicalizationError):
        canonical.pretty_json({"\udc00": 1})
