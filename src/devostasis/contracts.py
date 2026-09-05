"""Version identifiers of every contract the runtime implements.

Identifiers that end in an accepted research unit name (PV-...) implement that
unit as written. Identifiers under the ``devostasis.`` prefix are this
implementation's own versioned choices where the research contract was not yet
independently accepted; ``docs/spec/PROVENANCE.md`` maps each one to its source.
"""

# Observation envelope: RAW_OBSERVATION_CONTRACT_V0 (unit PV-OBS-001).
OBSERVATION_CONTRACT_VERSION = "RAW-OBS-V0"

# Seven-Vital taxonomy: accepted PV-VITALS-V1-002 (units PV-VIT-010/012).
VITALS_CONTRACT_VERSION = "PV-VITALS-V1-002"

# Integrity revision/verification semantics: accepted PV-CI-UNIT-004 (PV-VIT-011).
CI_UNIT_CONTRACT_VERSION = "PV-CI-UNIT-004"

# Numeric thresholds and windows frozen in V0 and preserved by V1.1.
POLICY_VERSION = "devostasis.policy.v1"

# Bundle layout: PV-ARTIFACT-V1-003 plus the B3 repair (persisted effective config).
ARTIFACT_CONTRACT_VERSION = "devostasis.bundle.v1"
BUNDLE_IDENTITY_CONTRACT = "PV-BUNDLE-ID-002"
EFFECTIVE_CONFIG_CONTRACT = "PV-EFFECTIVE-CONFIG-001"
EFFECTIVE_CONFIG_SCHEMA = "devostasis.effective-config.v1"

# Deterministic Markdown renderer (v2 adds non-authoritative gauges).
RENDERER_VERSION = "devostasis.render.v2"

# Presentation-only 0-100 gauges derived from bands and metrics.
GAUGE_CONTRACT = "devostasis.gauge.v1"

# Canonical JSON profile used for every digest.
CANONICAL_SERIALIZATION_VERSION = "devostasis.canon.v1"

# Schema identifiers of the machine artifacts.
SNAPSHOT_SCHEMA = "devostasis.snapshot.v1"
DELTA_SCHEMA = "devostasis.delta.v1"
ACTIVITY_SCHEMA = "devostasis.activity.v1"
MANIFEST_SCHEMA = "devostasis.manifest.v1"
OBSERVATIONS_SCHEMA = "devostasis.observations.v1"
RECEIPT_SCHEMA = "devostasis.receipt.v1"

# Canonical order of the seven core Vitals inside every snapshot.
CORE_VITAL_IDS = ("horizon", "clutter", "direction", "flow", "integrity", "debt", "pulse")
