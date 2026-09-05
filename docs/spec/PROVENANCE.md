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
| `devostasis.policy.v1` | numeric constants frozen in PV-VIT-001 and preserved through V1.1 | provisional calibration constants |
| `devostasis.bundle.v1` | PV-ARTIFACT-001, PV-ARTIFACT-002 (`PV-BUNDLE-ID-001`), PV-ARTIFACT-003 (`PV-EFFECTIVE-CONFIG-001`, `PV-BUNDLE-ID-002`) plus the B3 repair required by PV-REV-ARTIFACT-003 | produced; B3 repair implemented ahead of its review |
| history store and reports | PV-REPORT-001 | produced, not yet independently reviewed |
| `devostasis.ci-outcomes.github.v1` | implementation choice within PV-CI-NORM-001 | needs confirmation |
| `devostasis.render.v1`, `devostasis.canon.v1` | implementation choices within the artifact contract | local |

Implementation choices that the contracts left open, all listed in the
ROADMAP as calibration findings: the literal Flow rule with an empty queue,
Direction `UNDECLARED` when no milestone ever existed, `timed_out` as a
verification failure, `startup_failure` as `UNKNOWN`, and reconstruction of
Integrity history from provider-exposed attempts only.

The research process continues independently. Changes flow into this
repository as explicit adoption changes that name the unit they adopt;
disagreements found by the implementation flow back as issues labelled
`for:researcher`. The repository never depends on private research material:
everything needed to reproduce a bundle is in this repository and the bundle
itself.
