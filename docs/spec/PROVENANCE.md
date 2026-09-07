# Provenance of the contracts

Devostasis implements contracts that were produced and independently reviewed
by a bounded research process before any code existed. Each unit was written
by one run and judged by a separate run; only accepted units are treated as
normative here. The process is domain-neutral and documented in the
[EndlessZen](https://github.com/drevendev/EndlessZen) operating model.

| Identifier used by the code | Source unit(s) | Status when implemented |
| --- | --- | --- |
| `RAW-OBS-V0` | PV-OBS-001 | accepted |
| `PV-VITALS-V1-002` | PV-VIT-001 (V0), PV-VIT-002..009 repairs, PV-VIT-010 (V1.0), PV-VIT-012 (V1.1) | accepted by PV-REV-012 |
| `PV-CI-UNIT-004` | PV-VIT-004..011 (PV-CI-NORM-001, PV-CI-UNIT-001..004, PV-CI-PARENT-001..002) | accepted by PV-REV-011 |
| `devostasis.policy.v1` | numeric constants frozen in PV-VIT-001 and preserved through V1.1; the second constants of Flow are exact conversions | provisional calibration constants |
| `flow.bands.v1` | PV-FLOW-EMPTY-QUEUE-001 (PV-CAL-FLOW-001) and PV-FLOW-MERGE-LATENCY-001 (PV-CAL-FLOW-PRECISION-001), both from PV-CAL-002 findings | produced with fixtures; adopted in 0.1.2, conformance review by PV-SPEC-001 pending |
| `pulse.bands.v1` | PV-PULSE-REQUIRED-LOWER-BOUND-001 (PV-CAL-PULSE-CAP-001, from PV-CAL-003) | produced with fixtures; adopted in 0.1.2, conformance review by PV-SPEC-001 pending |
| `devostasis.bundle.v2`, `PV-BUNDLE-ID-002`, `PV-EFFECTIVE-CONFIG-001`, `PV-EFFECTIVE-CONFIG-AUTHORITY-001` | PV-ARTIFACT-001..005 (B1 acyclicity, B2 config identity, B3 persisted preimage, B4 stored-config authority); v2 adds gauges.json and demand.json to the identity preimage | PV-ARTIFACT-V1-005 accepted by PV-REV-ARTIFACT-005; ART-23..ART-25 adopted in 0.1.2 |
| history store and reports | PV-REPORT-001 | accepted by PV-REV-REPORT-001 with the non-decisions resolved as documented; RPT-4..RPT-7/RPT-9 remain open implementation work |
| `PV-BAND-ORDER-001`, `devostasis.band-order.v1` | PV-BAND-ORDER-001, which supersedes the PV-ORDER-001 research item that asked whether an order could be declared at all | accepted, adoption authorized; adopted in 0.1.8 with cases ORDER-01..15, executable as vectors. Ordering is per Vital only; the conformance review of the adoption is PV-SPEC-001 |
| `devostasis.vectors.v1` | implementation choice ahead of PV-TEST-001 | local: the format and runner are this repository's, so the vectors of PV-TEST-001 (READY, not yet produced) arrive executable rather than needing translation |
| `devostasis.gauge.v1` | implementation-defined normalization submitted for judgement | accepted by PV-REV-GAUGE-001 for presentation and same-Vital ordering; never cross-Vital, never aggregated |
| `devostasis.demand.v2` | PV-ROLE-001 (minimal consumer demand interface); v1 defined by the implementation, v2 removes the cross-Vital gauge tie-break required by ROLE-01 | default table, UNRESOLVED semantics and aggregate-free projection accepted by PV-ROLE-001; the v2 repair awaits PV-SPEC-001; predictive validity under calibration in PV-CAL-004 |
| `devostasis.ci-outcomes.github.v1` | implementation choice within PV-CI-NORM-001 | accepted by PV-CAL-003 (timed_out is VERIFY_FAIL, startup_failure is UNKNOWN) |
| `devostasis.targets.v1`, `devostasis.debt.v1`, register link marker | implementation choice under the explicit-register allowance of the V1 taxonomy | submitted for judgement (G7 auditability of the marker) |
| `devostasis.render.v4`, `devostasis.canon.v1`, `devostasis.effective-config.v2` | implementation choices within the artifact contract | local |

Implementation choices the contracts left open, with their disposition after
PV-CAL-002 and PV-CAL-003: the literal Flow rule with an empty queue (repaired,
`flow.bands.v1`); whole-hour merge latency (repaired, exact seconds);
`timed_out` as a verification failure and `startup_failure` as `UNKNOWN`
(confirmed); Direction `UNDECLARED` when no milestone ever existed
(confirmed); Integrity `FAILING` with a persistently failing secondary
workflow (confirmed as the evidence-faithful reading); Pulse on bursty solo
work (open observation, no rule change); Pulse on capped required
enumerations (repaired, `pulse.bands.v1`); reconstruction of Integrity history
from provider-exposed attempts only (open, PV-HIST-001).

The research process continues independently. Changes flow into this
repository as explicit adoption changes that name the unit they adopt;
disagreements found by the implementation flow back as issues labelled
`for:researcher` and as calibration findings in the ROADMAP. The repository
never depends on private research material: everything needed to reproduce a
bundle is in this repository and the bundle itself.
