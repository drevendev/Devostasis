# Configuration

`devostasis run` reads one JSON file. Every key is classified, because
configuration can change what a bundle contains and therefore must be part of
its identity or proven irrelevant:

- **A**: already identity-bearing elsewhere (`config_version`, `repo`);
- **B**: projected into `effective-config.json` and hashed into `bundle_id`;
- **C**: non-canonical, never affects bundle content (`store`, `token_env`).

Any other key is rejected with `CONFIG_IDENTITY_UNCLASSIFIED`.

```json
{
  "schema": "devostasis.config.v1",
  "config_version": "2026-09-05.1",
  "store": { "path": "." },
  "token_env": "DEVOSTASIS_TOKEN",
  "defaults": {
    "planning": { "source": "milestones" },
    "activity": { "enabled": true, "list_cap": 50 },
    "observations_member": true
  },
  "projects": [
    { "repo": "owner/name" },
    { "repo": "owner/other", "debt": { "labels": ["type:refactor", "debt"], "mapping_version": "2026-09" } },
    { "repo": "owner/archive", "planning": { "source": "none" }, "activity": { "list_cap": 10 } }
  ]
}
```

| Key | Class | Default | Meaning |
| --- | --- | --- | --- |
| `config_version` | A | required | label of this configuration revision; recorded as provenance |
| `store.path` | C | `.` | history store root, relative to the config file |
| `token_env` | C | none | extra environment variable to read the token from |
| `defaults` | B | see below | applies to every project unless overridden |
| `projects[].repo` | A | required | `owner/name` |
| `projects[].planning.source` | B | `milestones` | `milestones` reads GitHub milestones as planning targets; `none` declares planning positively absent (Horizon and Direction become `UNDECLARED`) |
| `projects[].debt` | B | `null` | `{"labels": [...], "mapping_version": "..."}`: issues carrying any listed label are registered debt items; without it Debt is `UNINSTRUMENTED` |
| `projects[].report_html` | B | `false` | reserved; `true` fails closed in this version |
| `projects[].locale` | B | `en` | report language (only `en`) |
| `projects[].activity.enabled` | B | `true` | include `activity.json` |
| `projects[].activity.list_cap` | B | `50` | maximum items per activity list |
| `projects[].observations_member` | B | `true` | include `observations.json` (full evidence; turn off to keep stores small) |
| `projects[].display_name`, `notes` | C | none | ignored by the runtime |

Changing `planning.source` or the debt mapping (labels or `mapping_version`)
changes the semantic configuration: the next bundle is `INCOMPARABLE` with the
previous one, on purpose. Changing `activity.list_cap` changes the bundle
identity but not the comparison.

## Token

Resolution order: `--token`, `DEVOSTASIS_GITHUB_TOKEN`, `GITHUB_TOKEN`,
`GH_TOKEN`, the configured `token_env`, then `gh auth token` when the GitHub
CLI is installed and logged in. Use a fine-grained token with read-only
Contents, Issues, Pull requests, Actions and Metadata permissions on the
repositories you observe.

## Reproducible runs

`--now 2026-09-05T12:00:00Z` fixes the observation timestamp so that two
collections of the same evidence produce the same bundle identity. Windows are
computed from that timestamp.
