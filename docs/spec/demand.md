# Demand interface (devostasis.demand.v1)

The demand interface is the generic consumer contract the research process
calls PV-ROLE-001 in its minimal form: for every Vital, one level from a small
ordered vocabulary, plus an attention order. Autonomous development systems
(SNAP, fleet control planes such as Whipstack) consume it opaquely to decide
where to spend effort; humans read it as "what needs work first".

## Levels

`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `MINIMAL`, and `UNRESOLVED`.

`UNRESOLVED` is emitted when the Vital has no band (`evaluation_status =
UNKNOWN`) or when the mapping has no entry for the band. Missing evidence must
never look like low demand: consumers treat `UNRESOLVED` as "do not skip",
exactly like the NO_HEALTH_SKIP rule of the SNAP consumer contract.

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
`mapping_version`; every band of every Vital always has a level.

## Attention order

Vitals are ordered by level rank (`UNRESOLVED` first, then CRITICAL down to
MINIMAL), then by an attention key derived from the gauge, then by canonical
Vital order. The attention key is the gauge for Flow, Clutter and Debt (more
of the phenomenon, more attention) and `100 - gauge` for Pulse, Integrity,
Horizon and Direction (less of the phenomenon, more attention). A missing
gauge has key 0.

The order is a ranking, never a sum. `aggregate` is always `null`: the seven
Vitals share signals and are not independent votes, so no scalar is computed
from them.

## Member

`demand.json` is a canonical bundle member, identity-bearing through
`demand_digest`:

```json
{
  "schema": "devostasis.demand.v1",
  "contract": "devostasis.demand.v1",
  "mapping_version": "devostasis-default-1",
  "observed_at": "2026-09-05T12:00:00Z",
  "canonical_semantics": "snapshot.json",
  "levels": ["CRITICAL", "HIGH", "MEDIUM", "LOW", "MINIMAL", "UNRESOLVED"],
  "aggregate": null,
  "vitals": [{"vital_id": "flow", "band": "CONGESTED", "evaluation_status": "AVAILABLE", "gauge": 41, "level": "HIGH", "attention_key": 41, "reason": "BAND:CONGESTED"}],
  "attention_order": [{"vital_id": "flow", "level": "HIGH", "attention_key": 41}]
}
```

`devostasis demand --bundle <dir>` prints it; `--order-only` prints the
ranking as text. The report renders it as the "Attention" section and the
fleet overview shows the first entry per project.

## Anti-gaming

Demand inherits the anti-gaming rules of the bands: mass-linking cannot lift
Direction above FULLY_LINKED, retry-until-green cannot erase an Integrity
failure, closing valid issues to improve Clutter is visible in the counts.
Consumers that change behaviour on demand should log the bundle id they acted
on, so every decision is reproducible from an immutable bundle.
