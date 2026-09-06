# Bundle (devostasis.bundle.v2, PV-BUNDLE-ID-002, PV-EFFECTIVE-CONFIG-001, PV-EFFECTIVE-CONFIG-AUTHORITY-001)

One successful canonical run of one project produces one immutable bundle.

## Members

| Member | Canonical | In identity | Content |
| --- | --- | --- | --- |
| `snapshot.json` | yes | digest | seven Vitals (authoritative) |
| `delta.json` | yes | digest | comparison with the previous bundle |
| `gauges.json` | yes | digest | 0-100 normalization of every band ([gauges.md](gauges.md)) |
| `demand.json` | yes | digest | demand levels and attention order ([demand.md](demand.md)) |
| `activity.json` | optional | digest or `ACTIVITY_DISABLED` | normalized activity in the interval |
| `observations.json` | optional | digest or `OBSERVATIONS_MEMBER_DISABLED` | every observation and the receipt |
| `effective-config.json` | yes | digest | the exact canonical effective config (B3 repair); the semantic authority of the bundle (B4) |
| `report.md` | yes | no (post-identity) | deterministic rendering under the persisted `display` configuration |
| `report.html` | optional | presence (through the effective config) | not rendered in this version; enabling it fails closed |
| `manifest.json` | yes | no (post-identity) | versions, identity preimage, member profile, member digests, receipt |

## Member schema identifiers

Every canonical member names its own schema in its first field, so a consumer
can tell what it is holding without inferring it from the file name:

| Member | `schema` |
| --- | --- |
| `snapshot.json` | `devostasis.snapshot.v1` |
| `delta.json` | `devostasis.delta.v1` |
| `activity.json` | `devostasis.activity.v1` |
| `observations.json` | `devostasis.observations.v1`, with a receipt of `devostasis.receipt.v2` |
| `gauges.json` | `devostasis.gauges.v1` |
| `demand.json` | `devostasis.demand.v2` |
| `effective-config.json` | `devostasis.effective-config.v2` |
| `manifest.json` | `devostasis.manifest.v1` |

The store adds two documents that are not bundle members and carry their own
identifiers: a project's chronological index (`devostasis.index.v1`) and the
fleet index (`devostasis.fleet.v1`, see
[history-and-reports.md](history-and-reports.md)).

## Canonical serialization (devostasis.canon.v1)

UTF-8; object keys sorted by code point; no insignificant whitespace; only
`null`, booleans, integers, strings, arrays and objects; **no floats**
(ratios are `{"num": x, "den": y}` records, exact durations in seconds are
`{"numerator": n, "denominator": d}` records); timestamps are
`YYYY-MM-DDTHH:MM:SSZ`. Digests are `sha256:<hex>` over canonical bytes.
Files may be stored pretty-printed; their digest is computed from the parsed
content. `effective-config.json` is stored in canonical form exactly.

## Effective config

Before identity is computed, the runtime projects every resolved
configuration value that can change canonical member presence or bytes into
`effective_bundle_config` (`devostasis.effective-config.v2`): planning source,
path and link marker, debt mapping, `report_html`, locale, activity and its
list cap, observations member, the display options and the full demand
mapping. Omitted defaults and explicit defaults canonicalize identically;
reordered lists canonicalize identically. `effective_config_digest` is the
SHA-256 of that projection.

Every configuration input is classified as (A) already identity-bearing,
(B) projected, or (C) proven non-canonical. An unclassified input fails closed
with `CONFIG_IDENTITY_UNCLASSIFIED` before anything is persisted.

The persisted projection is not merely hashed: it is the **semantic
authority** of the bundle (PV-EFFECTIVE-CONFIG-AUTHORITY-001). The canonical
member profile recorded in the manifest (`report_md`, `report_html`,
`activity_json`, `observations_json`, `gauges_json`, `demand_json`,
`effective_config_json`, each `REQUIRED`, `ENABLED` or `DISABLED`) is derived
from it at build time, and verification derives it again from the stored
file rather than trusting the manifest.

## Identity

Normative order: normalize evidence, build canonical machine artifacts,
digest members and receipt, assemble the identity preimage, compute
`bundle_id`, render outputs, digest outputs, write the manifest, persist
fail-closed, publish `latest`.

The identity preimage contains: `bundle_identity_contract`,
`artifact_contract_version`, `vitals_contract_version`,
`observation_contract_version`, `ci_unit_contract_version`, `gauge_contract`,
`demand_contract`, `policy_version`, `config_version`, `renderer_version`,
`canonical_serialization_version`, `effective_config_contract`,
`effective_config_digest`, `project_identity`, `observed_at`,
`previous_bundle_id`, `comparison_status`, `snapshot_digest`, `delta_digest`,
`activity_digest`, `gauges_digest`, `demand_digest`, `observations_digest`,
`source_receipts_digest`.

`bundle_id = SHA-256(canonical(preimage))` as 64 hex characters. The manifest,
the report, output digests and `run_meta` are post-identity, so the dependency
graph is acyclic; `renderer_version` is identity-bearing so a changed renderer
never collides with an old bundle; `observed_at` is identity-bearing so two
collections of the same repository are distinct bundles.

Bundles written by `devostasis.bundle.v1` remain verifiable: verification
uses the preimage stored in each manifest, validates their
`devostasis.effective-config.v1` projection under that schema (no gauges,
demand, display or demand mapping members), and the comparison logic maps
the older semantic-config shape onto the current one so history stays
`COMPARABLE` across the upgrade.

## Verification

`devostasis verify --bundle <dir>` needs nothing outside the bundle
directory and performs, in this order:

1. every declared member exists, is readable and hashes to its manifest
   digest; every present member is declared; `effective-config.json` is in
   canonical form (ART-21);
2. `bundle_id` recomputes from the stored preimage; the preimage contains no
   post-identity field (ART-22); the persisted effective config hashes to
   `effective_config_digest` in both preimage and manifest, else
   `EFFECTIVE_CONFIG_PREIMAGE_MISMATCH` (ART-20/ART-21);
3. the stored effective config is validated fail-closed under its recorded
   schema (`devostasis.effective-config.v1` or `v2`: exact key set, enums,
   planning, debt mapping, display and demand shapes), else
   `EFFECTIVE_CONFIG_SCHEMA_INVALID_OR_UNSUPPORTED` (ART-25);
4. the canonical member profile is derived from the validated stored config
   and must equal the manifest profile, agree with the members actually
   present and declared, and agree with the `ACTIVITY_DISABLED` /
   `OBSERVATIONS_MEMBER_DISABLED` markers in the identity preimage, else
   `CANONICAL_MEMBER_PROFILE_MISMATCH` (ART-23);
5. only when steps 3 and 4 passed, and the renderer version matches, is
   `report.md` re-rendered from the immutable machine members and the
   `display` of the stored config (never from current defaults) and compared
   byte for byte (ART-12/ART-24). A bundle whose stored config failed the
   checks reports that the replay was skipped instead of replaying from an
   untrusted source.

Any problem is a verification failure. A consistently re-hashed forgery that
claims a member disabled in the stored config while keeping the member, or
that changes the stored config to an unsupported shape, fails at step 3 or 4
even though every digest matches.

## Conformance cases implemented

ART-01 baseline, ART-02 repeatability, ART-06 neutral rendering, ART-07
immutability, ART-12 renderer purity, ART-13 acyclicity, ART-14
cross-implementation identity, ART-16 observed_at identity, ART-17 effective
config collision, ART-18 optional member identity (enabled HTML fails closed
in this version), ART-19 canonicalization invariance, ART-20 and ART-21
persisted preimage, ART-22 no identity cycle, ART-23 member profile from
stored config, ART-24 stored-config render authority, ART-25 effective config
schema verification.
