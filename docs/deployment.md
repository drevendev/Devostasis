# Deployment

The recommended production setup is a **companion history repository**: a
separate, private Git repository that holds the configuration, runs
Devostasis once a day in GitHub Actions, and commits the bundles to itself.
The observed repositories are never written to, and the history repository is
never observed, so storage activity cannot leak into project telemetry.

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
history repository. Devostasis never persists the token.

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
