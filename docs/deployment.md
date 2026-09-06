# Deployment

There are two ways to run Devostasis, and they complement each other:

| | Fleet observer | Self-observation |
| --- | --- | --- |
| Who reads whom | one history repository reads many projects | a project reads itself |
| Token | one read-only personal access token | none: the workflow's own `GITHUB_TOKEN` |
| History and deltas | full, in one place | only when a history store is given for comparison |
| Meant for | the human overview across projects and cross-project routing | the project's own autonomous loop deciding what to work on |
| Change in the project | none | one job in a workflow |

## Self-observation from a project (no secrets)

Add a job that calls the reusable workflow shipped in this repository:

```yaml
permissions:
  contents: read
  issues: read
  pull-requests: read
  actions: read
  checks: read

jobs:
  vitals:
    uses: drevendev/devostasis/.github/workflows/observe-self.yml@v0.1.2
    with:
      debt-labels: "type:debt"          # optional: issue labels that mark debt items
      # planning-source: file             # optional: targets register instead of milestones
      # planning-path: devostasis/targets.json
      # history-repo: owner/history       # optional: compare with the latest bundle there
    # secrets:
    #   history-token: ${{ secrets.HISTORY_READ_TOKEN }}   # only if history-repo is private

  decide:
    needs: vitals
    runs-on: ubuntu-latest
    steps:
      - run: echo "work on ${{ needs.vitals.outputs.attention }}"
      - if: contains(fromJSON(needs.vitals.outputs.levels).integrity, 'CRITICAL')
        run: echo "verification first"
```

What the job does: installs Devostasis at the given ref, observes the calling
repository with the workflow's own token, writes the status card and the
attention order to the job summary, uploads the bundle as the artifact
`devostasis-bundle`, and exposes outputs: `attention` (first attention entry,
e.g. `integrity CRITICAL`), `attention-order`, `levels`, `bands` and `gauges`
as JSON, `bundle-id`, `comparison-status`. Without `history-repo` every run
is a `BASELINE` bundle, which is enough to decide the current focus; with it
the run compares against the latest bundle of that store without writing to
it.

The caller's `permissions` block must grant the five read scopes above, or
the token cannot see issues, pull requests and workflow runs and the
corresponding Vitals come back FORBIDDEN.

Self-observation is a convenience shape, not durable history. The bundle
lives in the job's workspace and in the uploaded artifact, which expires with
the repository's artifact retention; nothing is appended to a canonical
store, and without `history-repo` every run is a `BASELINE` bundle. A project
that needs previous-vs-current deltas, an audit trail or replay must be
observed into a companion history repository as described below (decision
recorded by the research review of the reporting contract).

## Fleet observer with a companion history repository

The recommended production setup for history is a **companion history
repository**: a separate, private Git repository that holds the
configuration, runs Devostasis once a day in GitHub Actions, and commits the
bundles to itself. The observed repositories are never written to, and the
history repository is never observed, so storage activity cannot leak into
project telemetry.

## 1. Create the history repository

Create a private repository, for example `devostasis-history`, with:

```text
devostasis.json                 the fleet configuration (store.path = ".")
.github/workflows/observe.yml   the daily job below
projects/                       written by the job
```

The history repository must be at least as private as the most private
repository it observes; bundles contain issue and pull request titles,
commit subjects and branch names.

## 2. Create a read-only token

Create a fine-grained personal access token with read-only access to the
repositories you want to observe: Contents, Issues, Pull requests, Actions
and Metadata. Store it as the repository secret `DEVOSTASIS_TOKEN` in the
history repository. Devostasis never persists the token. A fine-grained token
is bound to one resource owner (a user or one organization); repositories of
other owners need their own token and configuration file, or use
self-observation instead.

## 3. The workflow

```yaml
name: Observe

on:
  schedule:
    - cron: "17 5 * * *"
  workflow_dispatch:

permissions:
  contents: write

concurrency:
  group: devostasis-observe
  cancel-in-progress: false

jobs:
  observe:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install Devostasis
        run: python -m pip install --quiet "git+https://github.com/drevendev/devostasis@release/0.1.0"
      - name: Observe every configured project
        id: run
        continue-on-error: true
        env:
          DEVOSTASIS_GITHUB_TOKEN: ${{ secrets.DEVOSTASIS_TOKEN }}
        run: devostasis run --config devostasis.json --store .
      - name: Commit bundles
        run: |
          git config user.name "devostasis"
          git config user.email "devostasis@users.noreply.github.com"
          git add projects
          git diff --cached --quiet || git commit -m "observe: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
          git push
      - name: Fail the job if any project failed
        if: steps.run.outcome == 'failure'
        run: exit 1
```

Pin the installed version to a release tag once one exists. `cancel-in-progress`
is false so that two overlapping runs never race on the store; the store
itself refuses to overwrite an existing bundle.

## 4. Cadence

Once per day plus manual dispatch is the recommended cadence. Devostasis is
schedule-agnostic: every bundle compares itself with the previous successful
bundle, so a missed day is covered by the next run and never fabricates a gap
as "no change".

## 5. Reading the results

- `projects/README.md` is the fleet overview: latest bands per project.
- `projects/<forge>/<owner>/<repo>/latest/report.md` is the current report.
- `history/YYYY/MM/DD/<bundle_id>/` holds every immutable bundle; verify any
  of them with `devostasis verify --bundle <dir>`.

## Local mode

Everything also works without Actions: `devostasis run --config devostasis.json --store ./history`
writes the same layout into a local directory. Commit it to any repository you
like, or keep it local.
