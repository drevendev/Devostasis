"""Read-only GitHub REST adapter.

Every endpoint failure becomes an explicit observation status instead of a
value: tier limitations are UNAVAILABLE, authorization denials are FORBIDDEN,
transient failures are ERROR, and a capped pagination is PARTIAL. The adapter
performs no mutation of any kind.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from .. import timeutil
from ..config import ResolvedProject
from ..normalize import (
    CI_CONFIGURED,
    CI_REVISIONS,
    INV_BRANCHES,
    INV_COMMITS,
    INV_CRS,
    INV_ISSUES,
    INV_RELEASES,
    INV_REPO,
    INV_TARGETS,
)
from ..observations import AVAILABLE, ERROR, FORBIDDEN, PARTIAL, UNAVAILABLE, UNKNOWN, Observation, ObservationSet, Receipt
from ..policy import CLUTTER, FLOW, INTEGRITY, PULSE
from . import github_ci

ADAPTER_VERSION = "devostasis.github.v1"
API_BASE = "https://api.github.com"
PER_PAGE = 100
MAX_PAGES = 10
MAX_COMMIT_PAGES = 30
MAX_CHANGE_REQUEST_PAGES = 20
MAX_ISSUE_PAGES = 20
MAX_RUN_PAGES = 20
MAX_BRANCH_PAGES = 2
MAX_BRANCH_HEAD_LOOKUPS = 60
MAX_ATTEMPT_LOOKUPS = 60
MAX_ATTEMPTS_PER_RUN = 5
MAX_SUITE_REVISIONS = 100


class CollectionError(Exception):
    """The subject could not be identified; no observation set can be produced."""


@dataclass
class ApiFailure(Exception):
    status_code: int
    observation_status: str
    reason_code: str
    message: str
    retryable: bool = False

    def __str__(self) -> str:
        return f"HTTP {self.status_code} {self.reason_code}: {self.message}"


@dataclass
class NetworkFailure(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


def classify_http_error(status: int, body: Any, headers: dict[str, str]) -> tuple[str, str, bool]:
    """Map an HTTP failure to (observation status, reason code, retryable)."""
    message = ""
    if isinstance(body, dict):
        message = str(body.get("message", ""))
    lowered = message.lower()
    if status == 401:
        return FORBIDDEN, "UNAUTHENTICATED", False
    if status == 403:
        if "rate limit" in lowered or headers.get("x-ratelimit-remaining") == "0":
            return ERROR, "RATE_LIMITED", True
        if "upgrade to github" in lowered or "github pro" in lowered or "not available" in lowered:
            return UNAVAILABLE, "TIER_UNAVAILABLE", False
        return FORBIDDEN, "FORBIDDEN", False
    if status == 404:
        return UNAVAILABLE, "NOT_FOUND", False
    if status == 410:
        return UNAVAILABLE, "DISABLED", False
    if status == 429:
        return ERROR, "RATE_LIMITED", True
    if status >= 500:
        return ERROR, "PROVIDER_ERROR", True
    return ERROR, f"HTTP_{status}", False


class UrllibTransport:
    """Minimal HTTPS transport on the standard library."""

    def __init__(self, token: str | None, api_base: str = API_BASE, user_agent: str = "devostasis/0.1", timeout: int = 30) -> None:
        self.token = token
        self.api_base = api_base.rstrip("/")
        self.user_agent = user_agent
        self.timeout = timeout

    def get(self, path: str, params: dict[str, Any] | None = None) -> tuple[int, dict[str, str], Any]:
        url = self.api_base + path
        if params:
            url += "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, method="GET")
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        request.add_header("User-Agent", self.user_agent)
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read()
                headers = {k.lower(): v for k, v in response.headers.items()}
                return response.status, headers, json.loads(raw.decode("utf-8")) if raw else None
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
            try:
                body = json.loads(raw.decode("utf-8")) if raw else None
            except ValueError:
                body = {"message": raw.decode("utf-8", "replace")[:200]}
            return exc.code, headers, body
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise NetworkFailure(f"network failure for {path}: {exc}") from exc


class GitHubClient:
    def __init__(self, transport: Any) -> None:
        self.transport = transport
        self.request_count = 0

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self.request_count += 1
        status, headers, body = self.transport.get(path, params)
        if status >= 400:
            obs_status, reason, retryable = classify_http_error(status, body, headers)
            message = body.get("message", "") if isinstance(body, dict) else ""
            raise ApiFailure(status, obs_status, reason, message, retryable)
        return body

    def paginate(
        self,
        path: str,
        params: dict[str, Any] | None,
        max_pages: int,
        stop: Callable[[dict[str, Any]], bool] | None = None,
        items_key: str | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Page-number pagination. Returns (items, complete)."""
        items: list[dict[str, Any]] = []
        params = dict(params or {})
        params["per_page"] = PER_PAGE
        for page in range(1, max_pages + 1):
            params["page"] = page
            body = self.get(path, params)
            batch = body.get(items_key, []) if items_key else body
            if not isinstance(batch, list):
                raise ApiFailure(200, ERROR, "UNEXPECTED_PAYLOAD", f"expected a list from {path}")
            items.extend(batch)
            if stop is not None and batch and stop(batch[-1]):
                return items, True
            if len(batch) < PER_PAGE:
                return items, True
        return items, False


def _failure_observation(observation_id: str, value_type: str, exc: Exception, common: dict[str, Any]) -> Observation:
    if isinstance(exc, ApiFailure):
        return Observation(
            observation_id=observation_id,
            status=exc.observation_status,
            value_type=value_type,
            reason_code=exc.reason_code,
            notes=f"HTTP {exc.status_code}: {exc.message}"[:300],
            **common,
        )
    return Observation(observation_id=observation_id, status=ERROR, value_type=value_type, reason_code="NETWORK", notes=str(exc)[:300], **common)


def _title(text: str | None) -> str:
    if not text:
        return ""
    return text.strip().splitlines()[0][:160]


class GitHubAdapter:
    """Collect provider-neutral inventories for one repository at one moment."""

    def __init__(self, client: GitHubClient, now: datetime) -> None:
        self.client = client
        self.now = now.astimezone(timeutil.UTC).replace(microsecond=0)
        self.observed_at = timeutil.format_ts(self.now)
        self.notes: list[str] = []

    def _common(self, source_ref: str) -> dict[str, Any]:
        return {"provider": "github", "collected_at": self.observed_at, "source_ref": source_ref, "adapter_version": ADAPTER_VERSION}

    def collect(self, project: ResolvedProject) -> ObservationSet:
        owner, repo = project.owner, project.repo
        base = f"/repos/{owner}/{repo}"
        started = timeutil.format_ts(timeutil.now_utc())
        try:
            meta = self.client.get(base)
        except (ApiFailure, NetworkFailure) as exc:
            raise CollectionError(f"cannot identify {owner}/{repo}: {exc}") from exc
        default_branch = meta.get("default_branch") or "main"
        subject = {
            "provider": "github",
            "forge_instance": "github.com",
            "owner": owner,
            "repo": repo,
            "display_locator": f"{owner}/{repo}",
            "immutable_project_id": str(meta.get("id")) if meta.get("id") is not None else None,
            "default_branch": default_branch,
            "visibility": meta.get("visibility"),
        }
        obs = ObservationSet(subject=subject, observed_at=self.observed_at)
        obs.add(
            Observation(
                observation_id=INV_REPO,
                status=AVAILABLE,
                value_type="record",
                value={
                    "id": meta.get("id"),
                    "full_name": meta.get("full_name"),
                    "default_branch": default_branch,
                    "visibility": meta.get("visibility"),
                    "has_issues": bool(meta.get("has_issues")),
                    "archived": bool(meta.get("archived")),
                    "pushed_at": timeutil.normalize_ts(meta.get("pushed_at")),
                    "html_url": meta.get("html_url"),
                },
                evidence_ref={"endpoint": base},
                **self._common(base),
            )
        )

        commits_by_sha = self._collect_commits(obs, base, default_branch)
        self._collect_change_requests(obs, base)
        self._collect_issues(obs, base, bool(meta.get("has_issues")))
        self._collect_branches(obs, base, default_branch, commits_by_sha)
        self._collect_targets(obs, base, project)
        self._collect_releases(obs, base)
        self._collect_ci(obs, base, default_branch, commits_by_sha)

        receipt = Receipt(
            run_id=f"run-{timeutil.compact_ts(self.now)}-{owner}-{repo}",
            collector_version=ADAPTER_VERSION,
            target=subject,
            started_at=started,
            ended_at=timeutil.format_ts(timeutil.now_utc()),
            capability_notes=list(self.notes),
            config_hash=project.effective_config_digest(),
            request_count=self.client.request_count,
        )
        obs.finalize_receipt(receipt)
        return obs

    def _collect_commits(self, obs: ObservationSet, base: str, default_branch: str) -> dict[str, dict[str, Any]]:
        since = timeutil.minus_days(self.now, PULSE["window_days"])
        path = f"{base}/commits"
        common = self._common(f"{path}?sha={default_branch}&since={timeutil.format_ts(since)}")
        try:
            raw, complete = self.client.paginate(path, {"sha": default_branch, "since": timeutil.format_ts(since)}, MAX_COMMIT_PAGES)
        except (ApiFailure, NetworkFailure) as exc:
            obs.add(_failure_observation(INV_COMMITS, "series", exc, common))
            return {}
        items = []
        for commit in raw:
            info = commit.get("commit") or {}
            committed = (info.get("committer") or {}).get("date") or (info.get("author") or {}).get("date")
            if not committed:
                continue
            items.append({"sha": commit["sha"], "committed_at": timeutil.normalize_ts(committed), "title": _title(info.get("message"))})
        items.sort(key=lambda c: (c["committed_at"], c["sha"]))
        obs.add(
            Observation(
                observation_id=INV_COMMITS,
                status=AVAILABLE if complete else PARTIAL,
                value_type="series",
                value=items,
                coverage={"window_start": timeutil.format_ts(since), "window_end": self.observed_at, "complete": complete, "branch": default_branch},
                reason_code=None if complete else "PAGINATION_CAPPED",
                evidence_ref={"endpoint": path, "branch": default_branch},
                **common,
            )
        )
        return {item["sha"]: item for item in items}

    def _collect_change_requests(self, obs: ObservationSet, base: str) -> None:
        since = timeutil.minus_days(self.now, FLOW["window_days"])
        path = f"{base}/pulls"
        common = self._common(f"{path}?state=open|updated>={timeutil.format_ts(since)}")
        try:
            open_raw, open_complete = self.client.paginate(path, {"state": "open", "sort": "created", "direction": "asc"}, MAX_CHANGE_REQUEST_PAGES)
            recent_raw, window_complete = self.client.paginate(
                path,
                {"state": "all", "sort": "updated", "direction": "desc"},
                MAX_CHANGE_REQUEST_PAGES,
                stop=lambda item: timeutil.parse_ts(item["updated_at"]) < since,
            )
        except (ApiFailure, NetworkFailure) as exc:
            obs.add(_failure_observation(INV_CRS, "series", exc, common))
            return
        merged: dict[int, dict[str, Any]] = {}
        for pull in open_raw + recent_raw:
            if pull.get("merged_at"):
                state = "MERGED"
            elif pull.get("state") == "closed":
                state = "CLOSED"
            else:
                state = "OPEN"
            milestone = pull.get("milestone") or None
            merged[int(pull["number"])] = {
                "number": int(pull["number"]),
                "id": pull.get("id"),
                "title": _title(pull.get("title")),
                "state": state,
                "draft": bool(pull.get("draft")),
                "created_at": timeutil.normalize_ts(pull.get("created_at")),
                "updated_at": timeutil.normalize_ts(pull.get("updated_at")),
                "merged_at": timeutil.normalize_ts(pull.get("merged_at")),
                "closed_at": timeutil.normalize_ts(pull.get("closed_at")),
                "target_id": str(milestone["number"]) if milestone else None,
                "target_state": (milestone.get("state") or "").upper() or None if milestone else None,
                "author": (pull.get("user") or {}).get("login"),
                "url": pull.get("html_url"),
            }
        items = [merged[number] for number in sorted(merged)]
        complete = open_complete and window_complete
        obs.add(
            Observation(
                observation_id=INV_CRS,
                status=AVAILABLE if complete else PARTIAL,
                value_type="series",
                value=items,
                coverage={"open_complete": open_complete, "window_complete": window_complete, "window_start": timeutil.format_ts(since)},
                reason_code=None if complete else "PAGINATION_CAPPED",
                evidence_ref={"endpoint": path},
                **common,
            )
        )

    def _collect_issues(self, obs: ObservationSet, base: str, has_issues: bool) -> None:
        since = timeutil.minus_days(self.now, PULSE["window_days"])
        path = f"{base}/issues"
        common = self._common(f"{path}?state=open|since={timeutil.format_ts(since)}")
        if not has_issues:
            obs.add(Observation(observation_id=INV_ISSUES, status=UNAVAILABLE, value_type="series", reason_code="ISSUES_DISABLED", **common))
            return
        try:
            open_raw, open_complete = self.client.paginate(path, {"state": "open", "sort": "created", "direction": "asc"}, MAX_ISSUE_PAGES)
            recent_raw, window_complete = self.client.paginate(
                path, {"state": "all", "since": timeutil.format_ts(since), "sort": "updated", "direction": "desc"}, MAX_ISSUE_PAGES
            )
        except (ApiFailure, NetworkFailure) as exc:
            obs.add(_failure_observation(INV_ISSUES, "series", exc, common))
            return
        merged: dict[int, dict[str, Any]] = {}
        for issue in open_raw + recent_raw:
            if issue.get("pull_request"):
                continue
            milestone = issue.get("milestone") or None
            merged[int(issue["number"])] = {
                "number": int(issue["number"]),
                "id": issue.get("id"),
                "title": _title(issue.get("title")),
                "state": "CLOSED" if issue.get("state") == "closed" else "OPEN",
                "created_at": timeutil.normalize_ts(issue.get("created_at")),
                "updated_at": timeutil.normalize_ts(issue.get("updated_at")),
                "closed_at": timeutil.normalize_ts(issue.get("closed_at")),
                "labels": sorted(label.get("name", "") for label in (issue.get("labels") or []) if isinstance(label, dict)),
                "target_id": str(milestone["number"]) if milestone else None,
                "author": (issue.get("user") or {}).get("login"),
                "url": issue.get("html_url"),
            }
        items = [merged[number] for number in sorted(merged)]
        complete = open_complete and window_complete
        obs.add(
            Observation(
                observation_id=INV_ISSUES,
                status=AVAILABLE if complete else PARTIAL,
                value_type="series",
                value=items,
                coverage={"open_complete": open_complete, "window_complete": window_complete, "window_start": timeutil.format_ts(since)},
                reason_code=None if complete else "PAGINATION_CAPPED",
                evidence_ref={"endpoint": path},
                **common,
            )
        )

    def _collect_branches(self, obs: ObservationSet, base: str, default_branch: str, commits_by_sha: dict[str, dict[str, Any]]) -> None:
        path = f"{base}/branches"
        common = self._common(path)
        try:
            raw, complete = self.client.paginate(path, {}, MAX_BRANCH_PAGES)
        except (ApiFailure, NetworkFailure) as exc:
            obs.add(_failure_observation(INV_BRANCHES, "series", exc, common))
            return
        items = []
        lookups = 0
        heads_resolved = True
        for branch in raw:
            name = branch.get("name")
            if name == default_branch:
                continue
            sha = (branch.get("commit") or {}).get("sha")
            committed_at = None
            if sha in commits_by_sha:
                committed_at = commits_by_sha[sha]["committed_at"]
            elif sha and lookups < MAX_BRANCH_HEAD_LOOKUPS:
                lookups += 1
                try:
                    detail = self.client.get(f"{base}/commits/{sha}")
                    info = detail.get("commit") or {}
                    committed_at = timeutil.normalize_ts((info.get("committer") or {}).get("date") or (info.get("author") or {}).get("date"))
                except (ApiFailure, NetworkFailure):
                    heads_resolved = False
            else:
                heads_resolved = False
            items.append({"name": name, "head_sha": sha, "head_committed_at": committed_at, "protected": bool(branch.get("protected"))})
        items.sort(key=lambda b: b["name"])
        status = AVAILABLE if (complete and heads_resolved) else PARTIAL
        obs.add(
            Observation(
                observation_id=INV_BRANCHES,
                status=status,
                value_type="series",
                value=items,
                coverage={"complete": complete, "heads_resolved": heads_resolved, "head_lookups": lookups},
                reason_code=None if status == AVAILABLE else ("PAGINATION_CAPPED" if not complete else "BRANCH_HEADS_UNRESOLVED"),
                evidence_ref={"endpoint": path},
                **common,
            )
        )

    def _collect_targets(self, obs: ObservationSet, base: str, project: ResolvedProject) -> None:
        path = f"{base}/milestones"
        common = self._common(f"{path}?state=all")
        if project.planning_source == "none":
            obs.add(Observation(observation_id=INV_TARGETS, status=UNAVAILABLE, value_type="series", reason_code="PLANNING_SOURCE_NONE", **common))
            return
        try:
            raw, complete = self.client.paginate(path, {"state": "all", "sort": "due_on", "direction": "asc"}, 3)
        except (ApiFailure, NetworkFailure) as exc:
            obs.add(_failure_observation(INV_TARGETS, "series", exc, common))
            return
        items = [
            {
                "target_id": str(m["number"]),
                "id": m.get("id"),
                "title": _title(m.get("title")),
                "state": "CLOSED" if m.get("state") == "closed" else "OPEN",
                "due_at": timeutil.normalize_ts(m.get("due_on")),
                "open_items": int(m.get("open_issues") or 0),
                "closed_items": int(m.get("closed_issues") or 0),
                "url": m.get("html_url"),
            }
            for m in raw
        ]
        items.sort(key=lambda m: int(m["target_id"]))
        obs.add(
            Observation(
                observation_id=INV_TARGETS,
                status=AVAILABLE if complete else PARTIAL,
                value_type="series",
                value=items,
                coverage={"complete": complete, "source": "milestones"},
                reason_code=None if complete else "PAGINATION_CAPPED",
                evidence_ref={"endpoint": path},
                **common,
            )
        )

    def _collect_releases(self, obs: ObservationSet, base: str) -> None:
        path = f"{base}/releases"
        common = self._common(path)
        try:
            raw = self.client.get(path, {"per_page": 30})
        except (ApiFailure, NetworkFailure) as exc:
            obs.add(_failure_observation(INV_RELEASES, "series", exc, common))
            return
        items = [
            {
                "tag": r.get("tag_name"),
                "name": _title(r.get("name")),
                "published_at": timeutil.normalize_ts(r.get("published_at")),
                "prerelease": bool(r.get("prerelease")),
                "url": r.get("html_url"),
            }
            for r in raw
            if not r.get("draft") and r.get("published_at")
        ]
        items.sort(key=lambda r: (r["published_at"], r["tag"] or ""))
        obs.add(
            Observation(
                observation_id=INV_RELEASES,
                status=AVAILABLE,
                value_type="series",
                value=items,
                coverage={"recent_only": True, "limit": 30},
                evidence_ref={"endpoint": path},
                **common,
            )
        )

    def _collect_ci(self, obs: ObservationSet, base: str, default_branch: str, commits_by_sha: dict[str, dict[str, Any]]) -> None:
        since = timeutil.minus_days(self.now, INTEGRITY["window_days"])
        window_commits = [c for c in commits_by_sha.values() if timeutil.parse_ts(c["committed_at"]) >= since]
        commits_obs = obs.get(INV_COMMITS)
        common_conf = self._common(f"{base}/actions/workflows")
        common_rev = self._common(f"{base}/actions/runs?branch={default_branch}&created>={timeutil.utc_day(since)}")
        if commits_obs is None or not commits_obs.has_value:
            obs.add(Observation(observation_id=CI_CONFIGURED, status=UNKNOWN, value_type="boolean", reason_code="REVISIONS_UNAVAILABLE", **common_conf))
            obs.add(Observation(observation_id=CI_REVISIONS, status=UNKNOWN, value_type="series", reason_code="REVISIONS_UNAVAILABLE", **common_rev))
            return

        workflows_total: int | None = None
        workflows_failure: Exception | None = None
        try:
            workflows_total = int(self.client.get(f"{base}/actions/workflows", {"per_page": 1}).get("total_count", 0))
        except (ApiFailure, NetworkFailure) as exc:
            workflows_failure = exc

        parents_by_sha: dict[str, list[dict[str, Any]]] = {}
        runs_complete = True
        attempts_complete = True
        runs_failure: Exception | None = None
        runs_seen = 0
        if workflows_total:
            try:
                runs, runs_complete = self.client.paginate(
                    f"{base}/actions/runs",
                    {"branch": default_branch, "created": f">={timeutil.utc_day(since)}"},
                    MAX_RUN_PAGES,
                    items_key="workflow_runs",
                )
            except (ApiFailure, NetworkFailure) as exc:
                runs_failure = exc
                runs = []
            attempt_lookups = 0
            for run in runs:
                sha = run.get("head_sha")
                if sha not in commits_by_sha:
                    continue
                runs_seen += 1
                prior: list[dict[str, Any]] = []
                current_attempt = int(run.get("run_attempt") or 1)
                if current_attempt > 1:
                    wanted = list(range(max(1, current_attempt - MAX_ATTEMPTS_PER_RUN), current_attempt))
                    for number in wanted:
                        if attempt_lookups >= MAX_ATTEMPT_LOOKUPS:
                            attempts_complete = False
                            break
                        attempt_lookups += 1
                        try:
                            prior.append(self.client.get(f"{base}/actions/runs/{run['id']}/attempts/{number}"))
                        except (ApiFailure, NetworkFailure):
                            attempts_complete = False
                    if current_attempt - 1 > MAX_ATTEMPTS_PER_RUN:
                        attempts_complete = False
                parents_by_sha.setdefault(sha, []).append(github_ci.actions_parent(run, prior))
            self.notes.append("CI_SURFACE:GITHUB_ACTIONS_ONLY")
            if runs_seen:
                self.notes.append("CHECKS_SURFACE_NOT_COLLECTED")

        suites_sampled = 0
        suites_failure: Exception | None = None
        if not runs_seen and not runs_failure:
            for commit in sorted(window_commits, key=lambda c: (c["committed_at"], c["sha"]), reverse=True)[:MAX_SUITE_REVISIONS]:
                suites_sampled += 1
                try:
                    body = self.client.get(f"{base}/commits/{commit['sha']}/check-suites", {"per_page": 100})
                except (ApiFailure, NetworkFailure) as exc:
                    suites_failure = exc
                    break
                for suite in body.get("check_suites", []) or []:
                    app_slug = (suite.get("app") or {}).get("slug")
                    if app_slug == "github-actions" and workflows_total:
                        continue
                    if suite.get("latest_check_runs_count", 1) == 0:
                        continue
                    parents_by_sha.setdefault(commit["sha"], []).append(github_ci.check_suite_parent(suite))
            if suites_sampled:
                self.notes.append("CI_SURFACE:GITHUB_CHECK_SUITES_SAMPLED")

        any_parents = any(parents_by_sha.values())
        if workflows_total and workflows_total > 0:
            obs.add(Observation(observation_id=CI_CONFIGURED, status=AVAILABLE, value_type="boolean", value=True, evidence_ref={"workflows_total": workflows_total}, **common_conf))
        elif any_parents:
            obs.add(Observation(observation_id=CI_CONFIGURED, status=AVAILABLE, value_type="boolean", value=True, evidence_ref={"check_suites": True}, **common_conf))
        elif workflows_failure is not None:
            obs.add(_failure_observation(CI_CONFIGURED, "boolean", workflows_failure, common_conf))
        elif suites_failure is not None:
            obs.add(_failure_observation(CI_CONFIGURED, "boolean", suites_failure, common_conf))
        elif window_commits and suites_sampled < len(window_commits):
            obs.add(Observation(observation_id=CI_CONFIGURED, status=UNKNOWN, value_type="boolean", reason_code="SAMPLE_INCOMPLETE", **common_conf))
        else:
            obs.add(Observation(observation_id=CI_CONFIGURED, status=AVAILABLE, value_type="boolean", value=False, evidence_ref={"workflows_total": 0, "check_suites_sampled": suites_sampled}, **common_conf))

        if runs_failure is not None:
            obs.add(_failure_observation(CI_REVISIONS, "series", runs_failure, common_rev))
            return
        if suites_failure is not None and not any_parents and not workflows_total:
            obs.add(_failure_observation(CI_REVISIONS, "series", suites_failure, common_rev))
            return
        if suites_failure is not None:
            reason = suites_failure.reason_code if isinstance(suites_failure, ApiFailure) else "NETWORK"
            self.notes.append(f"CHECK_SUITES_UNAVAILABLE:{reason}")
        records = github_ci.build_revision_records(window_commits, parents_by_sha)
        complete = runs_complete and attempts_complete and (commits_obs.status == AVAILABLE)
        reason = None
        if not runs_complete:
            reason = "PAGINATION_CAPPED"
        elif not attempts_complete:
            reason = "ATTEMPT_HISTORY_INCOMPLETE"
        elif commits_obs.status != AVAILABLE:
            reason = "REVISIONS_PARTIAL"
        obs.add(
            Observation(
                observation_id=CI_REVISIONS,
                status=AVAILABLE if complete else PARTIAL,
                value_type="series",
                value=records,
                coverage={
                    "window_start": timeutil.format_ts(since),
                    "window_end": self.observed_at,
                    "runs_complete": runs_complete,
                    "attempts_complete": attempts_complete,
                    "outcome_map_version": github_ci.OUTCOME_MAP_VERSION,
                    "surface": "github_actions" if runs_seen else ("github_check_suites" if any_parents else "none"),
                },
                reason_code=reason,
                evidence_ref={"branch": default_branch, "runs_matched": runs_seen},
                **common_rev,
            )
        )
