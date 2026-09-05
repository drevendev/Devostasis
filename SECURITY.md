# Security

## Reporting a vulnerability

Use GitHub's private vulnerability reporting on this repository
("Security" tab, "Report a vulnerability"). Do not open a public issue for
anything that could expose tokens, private repository data or history stores.
You will get an acknowledgement within a week.

## What Devostasis does and does not do

- **Read-only.** The GitHub adapter only issues `GET` requests. It never
  creates, edits or deletes anything on the forge.
- **Tokens.** A token is read from an argument, an environment variable or
  `gh auth token`, is sent only to `https://api.github.com`, and is never
  written to bundles, logs or the history store. Use a fine-grained token with
  read-only permissions (Contents, Issues, Pull requests, Actions, Metadata)
  scoped to the repositories you observe.
- **History stores hold repository content.** Bundles contain titles of
  issues and pull requests, commit subjects, branch names and CI outcomes. A
  store that observes a private repository must be at least as private as
  that repository; persistence into a more permissive location is a
  configuration mistake on the operator's side, and the deployment guide
  recommends a private companion repository.
- **No code execution from data.** Bundles, observation files and
  configuration are parsed as JSON only. Unknown configuration keys are
  rejected instead of interpreted.
- **No network in evaluation.** `evaluate`, `build`, `verify` and `render`
  are offline operations over local files.

## Supported versions

Only the latest release on `master` receives fixes.
