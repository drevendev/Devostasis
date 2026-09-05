# Bundle (devostasis.bundle.v1, PV-BUNDLE-ID-002, PV-EFFECTIVE-CONFIG-001)

One successful canonical run of one project produces one immutable bundle.

## Members

| Member | Canonical | In identity | Content |
| --- | --- | --- | --- |
| `snapshot.json` | yes | digest | seven Vitals (authoritative) |
| `delta.json` | yes | digest | comparison with the previous bundle |
| `activity.json` | optional | digest or `ACTIVITY_DISABLED` | normalized activity in the interval |
| `observations.json` | optional | digest or `OBSERVATIONS_MEMBER_DISABLED` | every observation and the receipt |
| `effective-config.json` | yes | digest | the exact canonical effective config (B3 repair) |
| `report.md` | yes | no (post-identity) | deterministic rendering |
| `manifest.json` | yes | no (post-identity) | versions, identity preimage, member digests, receipt |

## Canonical serialization (devostasis.canon.v1)

UTF-8; object keys sorted by code point; no insignificant whitespace; only
`null`, booleans, integers, strings, arrays and objects; **no floats**
(ratios are `{"num": x, "den": y}` records); timestamps are
`YYYY-MM-DDTHH:MM:SSZ`. Digests are `sha256:<hex>` over canonical bytes.
Files may be stored pretty-printed; their digest is computed from the parsed
content. `effective-config.json` is stored in canonical form exactly.

## Effective config

Before identity is computed, the runtime projects every resolved
configuration value that can change canonical member presence or bytes into
`effective_bundle_config` (`devostasis.effective-config.v1`): planning source,
debt mapping, `report_html`, locale, activity and its list cap, observations
member. Omitted defaults and explicit defaults canonicalize identically;
reordered lists canonicalize identically. `effective_config_digest` is the
SHA-256 of that projection.

Every configuration input is classified as (A) already identity-bearing,
(B) projected, or (C) proven non-canonical. An unclassified input fails closed
with `CONFIG_IDENTITY_UNCLASSIFIED` before anything is persisted.

## Identity

Normative order: normalize evidence, build canonical machine artifacts,
digest members and receipt, assemble the identity preimage, compute
`bundle_id`, render outputs, digest outputs, write the manifest, persist
fail-closed, publish `latest`.

The identity preimage contains: `bundle_identity_contract`,
`artifact_contract_version`, `vitals_contract_version`,
`observation_contract_version`, `ci_unit_contract_version`, `policy_version`,
`config_version`, `renderer_version`, `canonical_serialization_version`,
`effective_config_contract`, `effective_config_digest`, `project_identity`,
`observed_at`, `previous_bundle_id`, `comparison_status`, `snapshot_digest`,
`delta_digest`, `activity_digest`, `observations_digest`,
`source_receipts_digest`.

`bundle_id = SHA-256(canonical(preimage))` as 64 hex characters. The manifest,
the report, output digests and `run_meta` are post-identity, so the dependency
graph is acyclic; `renderer_version` is identity-bearing so a changed renderer
never collides with an old bundle; `observed_at` is identity-bearing so two
collections of the same repository are distinct bundles. Presentation gauges
(see [gauges.md](gauges.md)) are derived at render time and are neither a
member nor part of the identity.

## Verification

`devostasis verify --bundle <dir>` recomputes every member digest, recomputes
`bundle_id` from the stored preimage, checks that the persisted effective
config is canonical and hashes to `effective_config_digest`, checks that the
preimage contains no post-identity field, and re-renders `report.md` with the
current renderer when the renderer version matches. Any mismatch is a
verification failure. Verification needs nothing outside the bundle
directory.

## Conformance cases implemented

ART-01 baseline, ART-02 repeatability, ART-06 neutral rendering, ART-07
immutability, ART-12 renderer purity, ART-13 acyclicity, ART-14
cross-implementation identity, ART-16 observed_at identity, ART-17 effective
config collision, ART-18 optional member identity (enabled HTML fails closed
in this version), ART-19 canonicalization invariance, ART-20 and ART-21
persisted preimage, ART-22 no identity cycle.
