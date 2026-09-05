# Specification

These documents are the normative description of what the code does. They are
condensed from the research dossier that produced the contracts (see
[PROVENANCE.md](PROVENANCE.md)) and updated only together with the code and the
conformance tests.

| Document | Covers |
| --- | --- |
| [observations.md](observations.md) | Observation envelope, statuses, freshness, receipts, observation keys |
| [vitals.md](vitals.md) | The seven Vitals: inputs, rules, bands, degradation, anti-gaming metadata |
| [integrity-ci.md](integrity-ci.md) | Verification normalization, parent identity, revision verdicts, failure-sticky history |
| [bundle.md](bundle.md) | Bundle members, canonical serialization, identity preimage, effective config, verification |
| [history-and-reports.md](history-and-reports.md) | Comparison states, delta semantics, activity interval, history store layout, report rendering |
| [github-adapter.md](github-adapter.md) | What the GitHub adapter collects, how it maps failures and caps, what it does not collect |
| [conformance.md](conformance.md) | Conformance case identifiers and where each is implemented |
| [PROVENANCE.md](PROVENANCE.md) | Contract identifiers and the research units they come from |

Vocabulary used throughout:

- **observation**: one typed fact with a status; never a bare number;
- **inventory**: a normalized list observation (commits, change requests, issues, branches, targets, revisions);
- **aggregate**: a count or duration derived deterministically from inventories;
- **Vital**: one of the seven named dimensions; its output is a band plus evaluation metadata;
- **bundle**: the immutable set of files one successful run produces;
- **store**: the append-only place bundles live, keyed by project.
