# Demand interface (devostasis.demand.v2)

The demand interface is the generic consumer contract the research process
calls PV-ROLE-001 in its minimal form: for every Vital, one level from a small
ordered vocabulary, plus an attention order. Autonomous development systems
(SNAP, fleet control planes such as Whipstack) consume it opaquely to decide
where to spend effort; humans read it as "what needs work first".

PV-ROLE-001 accepted the default table, the `UNRESOLVED` semantics,
`aggregate = null`, the explicit `mapping_version` for overrides and the
generic consumer boundary, and required one repair: version 1 broke ties
inside a level by gauge, which compares numbers of different Vitals that
measure different phenomena. Version 2 removed that comparator.

## Levels

`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `MINIMAL`, and `UNRESOLVED`.

`UNRESOLVED` is emitted when the Vital has no band (`evaluation_status =
UNKNOWN`) or when the mapping has no entry for the band. Missing evidence must
never look like low demand: consumers treat `UNRESOLVED` as "do not skip",
exactly like the NO_HEALTH_SKIP rule of the SNAP consumer contract. It sorts
first (ROLE-02 UNKNOWN_FAILS_LOUD).

## Mapping

Levels come from a versioned table `band -> level` per Vital
(`demand.mapping_version`, `demand.levels`). The default table
`devostasis-default-1`:

| Vital | CRITICAL | HIGH | MEDIUM | LOW | MINIMAL |
| --- | --- | --- | --- | --- | --- |
| Pulse | | | DORMANT | QUIET | STEADY, SURGING |
| Flow | GRIDLOCKED | CONGESTED | | MOVING | NO_QUEUE |
| Integrity | FAILING | UNINSTRUMENTED, SPARSE_MIXED, FLAKY | NO_DECISIVE_RUNS | NO_RECENT_RUNS, SPARSE | CLEAN |
| Clutter | | HEAVY | CLUTTERED | LIGHT | CLEAN |
| Horizon | | | UNDECLARED | DECLARED | VISIBLE, EXTENDED |
| Direction | | SCATTERED | UNDECLARED, MIXED | | NO_ACTIVE_CHANGE, FULLY_LINKED |
| Debt | | | PRESENT | UNINSTRUMENTED | CLEAR |

Overrides in configuration replace single cells and require an explicit
`mapping_version`; invalid bands or levels fail closed (ROLE-04
MAPPING_VERSION_REQUIRED); every band of every Vital always has a level. The
default levels are routing policy under calibration (PV-CAL-004 measures
whether the attention order predicts where work actually happens next), not
Vital semantics.

## Attention order

Vitals are ordered by level rank (`UNRESOLVED` first, then CRITICAL down to
MINIMAL), then by the canonical Vital order (horizon, clutter, direction,
flow, integrity, debt, pulse). Nothing else enters the order.

Gauges are carried in the rows for presentation and provenance only. They
measure different phenomena on different scales and are never compared across
Vitals (accepted gauge contract, [gauges.md](gauges.md)): two Vitals at the
same level keep their relative order when only their gauges change (ROLE-01
SAME_LEVEL_GAUGE_INVARIANCE). This also closes a gaming path: moving a gauge
inside an unchanged band can no longer move one Vital ahead of another in a
consumer's routing.

The order is a ranking, never a sum. `aggregate` is always `null` (ROLE-03
NO_AGGREGATE): the seven Vitals share signals and are not independent votes,
so no scalar is computed from them, and consumers must not compute one from
levels or gauges either.

## Member

`demand.json` is a canonical bundle member, identity-bearing through
`demand_digest`:

```json
{
  "schema": "devostasis.demand.v2",
  "contract": "devostasis.demand.v2",
  "mapping_version": "devostasis-default-1",
  "observed_at": "2026-09-05T12:00:00Z",
  "canonical_semantics": "snapshot.json",
  "levels": ["CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL", "UNRESOLVED"],
  "aggregate": null,
  "vitals": [{"vital_id": "flow", "band": "CONGESTED", "evaluation_status": "AVAILABLE", "gauge": 41, "level": "HIGH", "reason": "BAND:CONGESTED"}],
  "attention_order": [{"vital_id": "flow", "level": "HIGH"}]
}
```

`devostasis demand --bundle <dir>` prints it; `--order-only` prints the
ranking as text. The report renders it as the "Attention" section, the fleet
overview shows the first entry per project, and the self-observation workflow
exposes it as the `attention` and `attention-order` outputs.

Bundles written under `devostasis.demand.v1` remain verifiable; their
`attention_order` entries carry the retired `attention_key` field and were
ordered by it. The demand contract is not part of comparability.

## Consumers

A consumer projects levels per Vital into its own decisions (which role runs,
which project a control plane routes attention to). It must not sum, average
or weight levels or gauges into a scalar, must treat `UNRESOLVED` as
attention-worthy, and should log the bundle id it acted on so every decision
is reproducible from an immutable bundle. SNAP role semantics stay outside
this repository.

## Anti-gaming

Demand inherits the anti-gaming rules of the bands: mass-linking cannot lift
Direction above FULLY_LINKED, retry-until-green cannot erase an Integrity
failure, closing valid issues to improve Clutter is visible in the counts,
and presentation gauges cannot reorder consumer attention (ROLE-01).
