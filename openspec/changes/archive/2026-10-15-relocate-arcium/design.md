## Context

Arcium room 85700 has east/south exits to UC 591773/592172. Homestead occupies
517245, with real approaches 517246/517645; retain all of those unchanged.

## Goals / Non-Goals

Move both Arcium pairs to GC northwest of the active Evermeet woodland without
creating a cross-continent shortcut through its entrance. Preserve all room IDs,
interior routes, resets, quests, and the owner's two no-change decisions.

## Decisions

Select footprint 516443 (43,41), east approach 516444 (44,41), and south approach
516843 (43,42). Both approaches are northwest of the active Evermeet landmark
517246 (46,43), using the surface grid based at 500000 with width 400. These
unoccupied hills/field rooms have no direct reset/quest/object/trigger/native
references. Validate loaded GC and ordinary walking before editing.

Move `85700 E <-> 591773 W` to `85700 E <-> 516444 W`, and
`85700 S <-> 592172 N` to `85700 S <-> 516843 N`. Remove the new marker's other
incoming edges from 516043/516442, following existing occupied-cell conventions.
Restore old footprint 591772 from its sector-0 placeholder to vine-covered hills
matching 591773; restore the east/south map edges while keeping north/west edges.
Existing mountains north/west remain barriers to ordinary walking.

## Risks / Trade-offs

Moving just one entrance would bridge continents. Check every surface entry to
85700, both returns, and Homestead's separate footprint. The real entrance is
dark forest; preserve its vision and progression requirements. Only approach
descriptions change to match the new hills and grasslands.

## Migration Plan

Generate and boot the development world, compare zcheck reports, walk all changed
routes through reset/restart, then publish a dependent PR. Production is separate.
Revert the authored changes and regenerate to restore the old placement.
