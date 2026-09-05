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
  "config_version": "2026-09-05.2",
  "store": { "path": "." },
  "token_env": "DEVOSTASIS_TOKEN",
  "defaults": {
    "planning": { "source": "milestones" },
    "display": { "gauge": ["bar", "number", "band"] },
    "activity": { "enabled": true, "list_cap": 50 }
  },
  "projects": [
    { "repo": "owner/name" },
    { "repo": "owner/other", "debt": { "source": "labels", "labels": ["type:debt"], "mapping_version": "2026-09" } },
    {
      "repo": "owner/planned",
      "planning": { "source": "file", "path": "devostasis/targets.json", "link_marker": "Target:" },
      "debt": { "source": "file", "path": "devostasis/debt.json", "mapping_version": "2026-09" },
      "display": { "vitals": ["integrity", "flow", "direction"], "gauge": ["number", "band"], "sections": ["demand", "changes"] },
      "demand": { "mapping_version": "team-1", "levels": { "debt": { "PRESENT": "HIGH" } } }
    },
    { "repo": "owner/archive", "planning": { "source": "none" }, "activity": { "list_cap": 10 } }
  ]
}
```

## Keys

| Key | Class | Default | Meaning |
| --- | --- | --- | --- |
| `config_version` | A | required | label of this configuration revision; recorded as provenance |
| `store.path` | C | `.` | history store root, relative to the config file |
| `token_env` | C | none | extra environment variable to read the token from |
| `defaults` | B | see below | applies to every project unless overridden |
| `projects[].repo` | A | required | `owner/name` |
| `projects[].planning.source` | B | `milestones` | `milestones` reads GitHub milestones; `file` reads a targets register ([registers](spec/registers.md)); `none` declares planning positively absent |
| `projects[].planning.path` | B | none | repository path of the targets register, required for `file` |
| `projects[].planning.link_marker` | B | `Target:` | marker that links a change request to a target id in its text (`file` source) |
| `projects[].debt` | B | `null` | `{"source": "labels", "labels": [...], "mapping_version"}` or `{"source": "file", "path": ..., "mapping_version"}`; without it Debt is `UNINSTRUMENTED` |
| `projects[].display.vitals` | B | all seven | which Vitals appear, in which order |
| `projects[].display.gauge` | B | `bar, number, band` | components of the status card |
| `projects[].display.sections` | B | all | report sections: `demand`, `details`, `observability`, `changes`, `activity`, `provenance` |
| `projects[].demand.mapping_version` | B | `devostasis-default-1` | version of the band-to-level table |
| `projects[].demand.levels` | B | `{}` | overrides per Vital and band ([demand](spec/demand.md)); require an explicit `mapping_version` |
| `projects[].report_html` | B | `false` | reserved; `true` fails closed in this version |
| `projects[].locale` | B | `en` | report language (only `en`) |
| `projects[].activity.enabled` | B | `true` | include `activity.json` |
| `projects[].activity.list_cap` | B | `50` | maximum items per activity list |
| `projects[].observations_member` | B | `true` | include `observations.json` (full evidence; turn off to keep stores small) |
| `projects[].display_name`, `notes` | C | none | ignored by the runtime |

## What changes comparability

Changing `planning` (source, path or marker) or `debt` (source, labels, path
or `mapping_version`) changes the semantic configuration: the next bundle is
`INCOMPARABLE` with the previous one, on purpose. Changing `display`,
`demand`, `activity.list_cap` or `observations_member` changes the bundle
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

## Command-line equivalents

`observe` and `build` accept the same project options as flags:
`--planning {milestones,file,none}`, `--planning-path`, `--link-marker`,
`--debt-label` (repeatable), `--debt-path`, `--debt-mapping-version`.
