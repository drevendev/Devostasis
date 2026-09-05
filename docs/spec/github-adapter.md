# GitHub adapter (devostasis.github.v1)

Read-only. Only `GET` requests, `Accept: application/vnd.github+json`,
API version `2022-11-28`, page-based pagination with 100 items per page.

## Requests per project

| Purpose | Endpoint | Cap |
| --- | --- | --- |
| identity | `GET /repos/{o}/{r}` | 1 (failure aborts the project: no subject, no bundle) |
| commits | `GET /repos/{o}/{r}/commits?sha=<default>&since=<28d>` | 30 pages (3000 commits) |
| change requests | `GET /pulls?state=open` and `GET /pulls?state=all&sort=updated&direction=desc` until older than 28 days | 20 pages each |
| issues | `GET /issues?state=open` and `GET /issues?state=all&since=<28d>` (pull requests filtered out) | 20 pages each; skipped when `has_issues` is false |
| branches | `GET /branches`, then `GET /commits/{sha}` for heads not on the default branch | 2 pages, 60 head lookups |
| targets | `GET /milestones?state=all` | 3 pages; skipped when `planning.source = none` |
| releases | `GET /releases?per_page=30` | 1 page |
| verification | `GET /actions/workflows` (count), `GET /actions/runs?branch=<default>&created=>=<14d>`, `GET /actions/runs/{id}/attempts/{n}` for reruns | 20 pages, 5 attempts per run, 60 attempt lookups |
| fallback verification | `GET /commits/{sha}/check-suites` per revision, only when no Actions runs exist | 100 revisions |

A typical small repository costs 10 to 30 requests; a very active one
(hundreds of merged change requests and more than a thousand default-branch
commits a month) costs 50 to 150. Enumerations are newest-first, so a capped
enumeration is a lower bound of the true activity and is reported as
`PARTIAL`.

## Failure mapping

| HTTP | Status | Reason code |
| --- | --- | --- |
| 401 | FORBIDDEN | `UNAUTHENTICATED` |
| 403 rate limited | ERROR | `RATE_LIMITED` (retryable) |
| 403 tier or plan message | UNAVAILABLE | `TIER_UNAVAILABLE` |
| 403 other | FORBIDDEN | `FORBIDDEN` |
| 404 | UNAVAILABLE | `NOT_FOUND` |
| 410 | UNAVAILABLE | `DISABLED` |
| 429 | ERROR | `RATE_LIMITED` |
| 5xx, network | ERROR | `PROVIDER_ERROR`, `NETWORK` |

A capped pagination yields `PARTIAL` with `PAGINATION_CAPPED`; unresolved
branch heads yield `PARTIAL` with `BRANCH_HEADS_UNRESOLVED`; incomplete
attempt history yields `PARTIAL` with `ATTEMPT_HISTORY_INCOMPLETE`.

## `ci.configured`

`true` when the repository has at least one workflow or any verification
parent was observed; `false` only when there are zero workflows and no check
suite on every sampled revision of the window; `UNKNOWN` with
`SAMPLE_INCOMPLETE` when more revisions exist than could be sampled.

## Normalization decisions

- Commit time is the committer date; active days are distinct UTC dates.
- A pull request is `MERGED` when `merged_at` is set, `CLOSED` when closed
  without merge, else `OPEN`. Its planning target is its milestone number;
  the target state is the milestone state.
- Only Actions runs whose `head_sha` is a default-branch commit of the window
  become parents; runs of pull-request branches are not default-branch
  verification.
- Skipped workflow runs are parents with `NOT_EXECUTED`; a revision whose
  only parents are skipped counts as verification activity without a decisive
  verdict.

## Not collected in this version

Branch protection and rulesets, commit statuses, external check apps when
Actions runs exist, GitHub Projects fields, pull request to issue linkage,
review latency, deployments and environments, discussions. Each is listed in
the ROADMAP with the observation it would feed.

## Token handling

Order of resolution: `--token`, `DEVOSTASIS_GITHUB_TOKEN`, `GITHUB_TOKEN`,
`GH_TOKEN`, the configured `token_env`, then `gh auth token`. Without a token
only public repositories are readable and the unauthenticated rate limit
applies. The token is sent only to `api.github.com` and is never persisted.
