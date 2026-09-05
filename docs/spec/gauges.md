# Gauges (devostasis.gauge.v1, presentation only)

The accepted contracts keep named bands canonical and allow 0-100 values only
as a presentation layer. Gauges are that layer: a deterministic placement of a
Vital on a 0-100 scale so that a human sees gradation inside a band instead of
a binary label.

Rules:

- gauges are computed from the authoritative snapshot only (band plus the
  derived metrics the rule used), with integer arithmetic;
- they are never written into `snapshot.json`, never enter bundle identity,
  and machine consumers must not read them as truth (`"authoritative": false`);
- each gauge measures the **intensity of the phenomenon the Vital
  describes**, not virtue: Clutter 90 is a lot of residue, Flow 90 is a lot of
  queue pressure, Integrity 90 is stable verification, Debt 90 is a lot of
  registered debt;
- inside a band the value is monotone in the metrics that define the band;
  bands never overlap on the scale;
- `UNKNOWN` Vitals and states where the phenomenon is not applicable render
  as `n/a`; a `DEGRADED` bound renders with `≥`, `≤` or `~`.

## Scales and band ranges

| Vital | Scale | Band ranges | Within-band drivers |
| --- | --- | --- | --- |
| Pulse | activity intensity | DORMANT 0; QUIET 5-30; STEADY 35-70; SURGING 75-100 | activity events, active days |
| Flow | queue pressure | NO_QUEUE 0; MOVING 5-30; CONGESTED 35-70; GRIDLOCKED 75-100 | open count, oldest age, median time to merge |
| Integrity | verification stability | FAILING 0-24; SPARSE_MIXED 25-49; FLAKY 50-74; SPARSE 75-87; CLEAN 88-100 | pass share, sample size |
| Clutter | stale residue | CLEAN 0; LIGHT 5-30; CLUTTERED 35-70; HEAVY 75-100 | stale work count, stale branches, stale ratio |
| Horizon | declared future work | UNDECLARED 0; DECLARED 10-40; VISIBLE 45-75; EXTENDED 80-100 | open targets, targets with a future boundary, targets beyond 28 days |
| Direction | traceability share | SCATTERED 0-49; MIXED 50-99; FULLY_LINKED 100; UNDECLARED 0 | linked / active change requests |
| Debt | registered debt | CLEAR 0; PRESENT 10-100 | open items (saturates at 50), stale items (saturates at 20) |

Not applicable (`n/a`): Integrity UNINSTRUMENTED, NO_RECENT_RUNS and
NO_DECISIVE_RUNS; Debt UNINSTRUMENTED; Direction NO_ACTIVE_CHANGE; Horizon and
Direction when planning is declared unsupported by configuration.

## Formulas

`part(x, cap, width) = width * clamp(x, 0, cap) / cap` with integer division.

- Pulse: QUIET `5 + 5*min(events, 4)`; STEADY `35 + max(part(events-5, 35, 35), part(days-3, 12, 35))`; SURGING `75 + max(part(events-40, 160, 25), part(days-15, 13, 25))`.
- Flow: MOVING `5 + max(part(open-1, 8, 25), part(oldest, 13, 25))`; CONGESTED `35 + max(part(open-10, 20, 35), part(oldest-14, 16, 35), part(median-168, 168, 35))`; GRIDLOCKED `75 + max(part(open-10, 40, 25), part(oldest-30, 60, 25), part(median-336, 336, 25))`.
- Clutter: LIGHT `5 + max(5*min(stale, 4), 4*min(branches, 5))`; CLUTTERED `35 + max(part(stale-5, 19, 35), part(branches-6, 13, 35), part(4*num-den, den, 35))`; HEAVY `75 + max(part(stale-25, 75, 25), part(branches-20, 30, 25), part(2*num-den, den, 25))`.
- Integrity with `passes = decisive - failed`: FAILING `part(passes, decisive, 24)`; SPARSE_MIXED `25 + part(passes, decisive, 24)`; FLAKY `50 + part(decisive-4*failed, decisive, 24)`; SPARSE `75 + 6*min(decisive-1, 2)`; CLEAN `88 + part(decisive-4, 20, 12)`.
- Horizon: DECLARED `10 + part(open, 6, 30)`; VISIBLE `45 + part(future, 6, 30)`; EXTENDED `80 + part(beyond, 5, 20)`.
- Direction: `100 * linked / active`.
- Debt: PRESENT `10 + part(open, 50, 70) + part(stale, 20, 20)`.

## Rendering

`report.md` opens with a monospace status card (bar, value, band per Vital)
and repeats the gauge in each Vital section. The fleet overview prints the
value after the band. `devostasis gauges --bundle <dir>` prints the gauges as
JSON, `--card` adds the text card.

## What gauges are not

They are not a health score, they are not comparable across Vitals, they are
not summed, and a theme that renames bands (for example clinical or playful
labels) is a separate, optional layer that cannot change machine semantics and
is not part of this version.
