# Zone placement implementation record, October 15, 2026

This record preserves the design rationale, original route contracts and completed
local checks for [issue #37](https://github.com/LuminariMUD/Duris/issues/37), delivered
in [#103](https://github.com/LuminariMUD/Duris/pull/103),
[#104](https://github.com/LuminariMUD/Duris/pull/104) and
[#105](https://github.com/LuminariMUD/Duris/pull/105).

The Arcium and tower placements below describe the October 15 implementation.
[PR #204](https://github.com/LuminariMUD/Duris/pull/204) subsequently corrected five
surface locations, including Homestead, Turopolis and Lizizania. Use
[World zone routes](../reference/WORLD_ZONE_ROUTES.md) and the current authored
world/tests for present-day entrances. The Misty Chasm/Underdark route remains.
Completed checklists record historical development evidence, not a new run or a
production deployment. Any then-pending review steps are historical checkpoints;
the three PRs were subsequently merged.

## Outcasts Tower

Delivery: [PR #103](https://github.com/LuminariMUD/Duris/pull/103).

### Original scope

#### Why

Issue #37 requests Outcasts Tower on the Good Continent south of Kimordril.
Its current surface approach is on the Evil Continent. The owner selected the
new site and required the existing Underworld route to remain available.

#### What Changes

- Move the reciprocal surface entrance to `546861 N <-> 11300 S`.
- Mark footprint `546461`, preserve travel around it, and restore terrain and
  reciprocal map travel at the vacated footprint `615849`.
- Preserve tower identities, resets, progression, and `11348 N <-> 30172 S`.
- Prove authored, generated, and loaded routes with focused local checks.

#### Impact

Authored `otower.wld` and `surface.wld`, focused route tests, and the issue plan.
No engine, database, production, or unrelated area changes.

### Design and decisions

#### Context

The owner selected footprint 546461 (61,116), with southern approach 546861
(61,117), seven rows south of Kimordril's approach 543661 (61,109). Coordinates
are zero-based surface grid offsets from 500000, width 400.

#### Goals and boundaries

Move the tower's surface access to GC and keep its Underworld access. Preserve
all area IDs, resets, and interior progression. Do not relocate Homestead or
Turolopolis, change engine movement, or deploy production.

#### Decisions

Use the existing occupied map-cell convention: a named marker at 546461 with no
ordinary incoming map exits. Redirect the southern edge to the actual entrance;
remove inward edges from 546061/546460/546462. Keep surrounding grid routes.

Restore old footprint 615849 to DarkPeak hills matching its east/west neighbors,
restore their missing inward edges, and return 616249 N to the footprint. Its
sector-0 Waters of the Abyss placeholder is not usable terrain to retain.
The existing mountain 615449 to its north remains impassable to an ordinary
walker; retain its authored edge and test the terrain rejection, alongside
successful east/west/south traversal. Do not flatten the peak to satisfy a test.

Reuse existing world generation, parsing, isolated authority, and character
journey helpers. Native assignment of 11300 as a ship room is disabled code.

#### Risks / Trade-offs

The retained Underworld route now connects GC to the same Underworld network;
this is an explicit owner decision. Check the loaded continent, all entrance
directions, old-site walking, resets, and zcheck deltas before publication.

#### Development validation and rollback

Regenerate and boot only a disposable development world. Publish authored sources
for review; production rollout remains separate. Reverting the authored diff and
regenerating restores the old placement without changing persisted identities.

### Completed development checks

#### 1. Verify baseline

- [x] 1.1 Refresh issue/base, verify local environment, inspect active sources and proc references.
- [x] 1.2 Capture baseline loaded endpoints, GC site, and affected zcheck reports.

#### 2. Implement and prove

- [x] 2.1 Add focused route contract and show failure on the old data.
- [x] 2.2 Relocate the surface pair, mark the new footprint, and restore the old footprint.
- [x] 2.3 Pass source checks and a deliberately broken return-edge fixture.
- [x] 2.4 Generate world, build server, and pass isolated full-world restart.
- [x] 2.5 Verify ordinary walking, loaded geography, retained routes, reset/restart, and zcheck deltas.

#### 3. Publish

- [x] 3.1 Update the plan, review the scoped diff and route documentation.
- [x] 3.2 Commit, push, open a focused PR, and verify remote state (PR #103).

#### Historical route contract

##### Good Continent surface access

Outcasts Tower must connect through `546861 N -> 11300` and `11300 S -> 546861`
on the Good Continent south of Kimordril. The old EC entrance must be removed.

###### Verification: Ordinary player enters and returns

- When a player walks north from 546861 and south from 11300
- Verify the player reaches 11300 and returns to 546861 without staff movement bypass
- Also verify 546861 is on loaded GC at (61,117), south of Kimordril at (61,109)

##### Coherent map footprints

The new marker at 546461 must have no ordinary incoming map exit. The vacated
615849 footprint must have hill terrain and reciprocal cardinal grid exits.

###### Verification: Surrounding travel

- When a player traverses the old site and walks around the new footprint
- Verify all intended map routes remain usable without entering an isolated marker
- Also verify 616249 north reaches 615849 rather than the tower
- Also verify the existing mountain at 615449 still rejects ordinary walking north

##### Preserve existing progression and secondary access

The relocation must preserve `11348 N -> 30172` and `30172 S -> 11348`, tower
resets and interior exits, and Homestead and Turolopolis/Zoo content.

###### Verification: Reset and restart

- When the development world resets and restarts
- Verify both surface and secondary exit pairs remain loaded and traversable
- Also verify no new dangling exits or one-way traps are introduced

## Arcium

Delivery: [PR #104](https://github.com/LuminariMUD/Duris/pull/104).

### Original scope

#### Why

Issue #37 and the owner's 2026-10-15 decision require Arcium on GC northwest of
Evermeet. Its two surface approaches currently lead to the Undead Continent.
Homestead's nearby misleading "Acrium" map label does not authorize moving it.

#### What Changes

- Move both Arcium entrance pairs to a separate foothill site northwest of the
  active Evermeet woodland, using existing rooms only.
- Restore the old hill footprint and mark the new footprint without stray entries.
- Preserve Homestead, Arcium interior progression, and the preceding tower change.

#### Impact

Authored `arcium.wld` and `surface.wld`, existing issue #37 tests and plan.
Stacked on the Outcasts Tower PR for shared tests and planning context. No engine,
zone identity, reset, quest, production, or Homestead change.

### Design and decisions

#### Context

Arcium room 85700 has east/south exits to UC 591773/592172. Homestead occupies
517245, with real approaches 517246/517645; retain all of those unchanged.

#### Goals and boundaries

Move both Arcium pairs to GC northwest of the active Evermeet woodland without
creating a cross-continent shortcut through its entrance. Preserve all room IDs,
interior routes, resets, quests, and the owner's two no-change decisions.

#### Decisions

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

#### Risks / Trade-offs

Moving just one entrance would bridge continents. Check every surface entry to
85700, both returns, and Homestead's separate footprint. The real entrance is
dark forest; preserve its vision and progression requirements. Only approach
descriptions change to match the new hills and grasslands.

#### Development validation and rollback

Generate and boot the development world, compare zcheck reports, walk all changed
routes through reset/restart, then publish a dependent PR. Production is separate.
Revert the authored changes and regenerate to restore the old placement.

### Completed development checks

#### 1. Establish exact routes

- [x] 1.1 Inspect free sites, active landmark, existing exits, and non-exit references.
- [x] 1.2 Verify candidate GC rooms and baseline routes in the loaded development world.

#### 2. Implement and verify

- [x] 2.1 Extend the existing route contract and demonstrate old-data failure.
- [x] 2.2 Move both pairs, restore the old hill, and mark the new footprint.
- [x] 2.3 Verify authored/generated contracts and broken-return rejection.
- [x] 2.4 Generate/build and pass the isolated full-world restart.
- [x] 2.5 Walk both new pairs, old-site paths, surrounding map, and unchanged routes through reset/restart; compare zcheck.

#### 3. Publish

- [x] 3.1 Update the plan, inspect the diff and route documentation.
- [x] 3.2 Commit/push and open a focused PR stacked on #103; verify publication (PR #104).

#### Historical route contract

##### Two Good Continent approaches

Arcium must connect through `516444 W <-> 85700 E` and `516843 N <-> 85700 S`.
Both approaches must be GC and northwest of active Evermeet woodland at 517246.
The former UC entrances at 591773 and 592172 must no longer enter Arcium.

###### Verification: Enter and leave through either approach

- When an ordinary player walks each new entrance and its return
- Verify the expected rooms are reached without staff movement bypass
- Also verify loaded continent and surface grid coordinates establish the required placement

##### Preserve map travel and Homestead

The new marker 516443 must have no ordinary incoming map exit. The old footprint
591772 must be hills with reciprocal cardinal grid edges. Homestead's footprint
517245 and approaches 517246/517645 must remain unchanged.

###### Verification: Old site and surrounding map

- When a player walks the vacated east/south approaches and around the new site
- Verify the intended ordinary routes remain usable
- Also verify the existing north/west mountains retain their ordinary movement barriers
- Also verify both Homestead entrance pairs remain usable

##### Preserve Arcium progression

The relocation must preserve all Arcium room identities, interior exits, flags,
resets, quests, and all accepted no-change areas.

###### Verification: Zone reset and clean restart

- When the world resets and restarts
- Verify both new entrance pairs remain loaded and traversable
- Also verify no new zcheck finding, dangling exit, or one-way trap is introduced

## Misty Chasm

Delivery: [PR #105](https://github.com/LuminariMUD/Duris/pull/105).

### Original scope

#### Why

Issue #37 requests a usable Underdark connection for the Chasm of the Misty Vale
(zone 150). The owner accepted a two-way passage while retaining the area's
Khomani-Khan surface entrance and existing progression.

#### What Changes

- Connect grounded cliff trail 15015 down to existing Underdark tunnel 834025,
  with an up return, describing a long stair passage through the rock.
- Preserve the surface pair, bridge, falling rooms, shafts, and pyramid locks.
- Extend the existing route regression and disposable mortal journey.

#### Impact

Only `mist_chasm.wld` and `underdark.wld` need content changes. Tests, route documentation,
and the continuation plan share the preceding #103/#104 stack. No new rooms,
zone boundaries, resets, procs, migrations, or production operations.

### Design and decisions

#### Context

Misty's sole ordinary external pair is `638825 W <-> 15000 E`. Grounded cliff
trail 15015 is reached before the rope bridge through 15001, 15006..15014. It
has no fall chance, door reset, or down exit. Its existing east/south trail exits
continue unchanged. Selecting a trail here avoids the falling bridge and shaft
rooms and does not provide a shortcut into the locked pyramid.

#### Goals and boundaries

Provide ordinary two-way passage into the actual Underdark and back to the
surface. Preserve all existing progression, identities, exits, and accepted
no-change areas. Do not create native movement logic, connector rooms, doors,
keys, or reset machinery when two authored open exits suffice.

#### Decisions

Use `15015 D <-> 834025 U`. The UD endpoint is a low-ceiling tunnel at (25,335)
in the grid based at 700000, width 400. It has no up exit and connects through
833625 and 834026 to the surrounding tunnel network. Source traversal reaches
thousands of non-mountain/non-slime/non-air UD cells and multiple area entrances;
this is an existing network, not an isolated numeric counterpart of the surface.

Describe a long, winding stair cut into the cliff and bedrock. Both exits have
zero door flags and require no key. A human on foot can fit the existing low
ceiling; keep that ordinary terrain constraint. Confirm actual light/vision,
movement, map section, and return behavior in a disposable world before editing.

#### Risks / Trade-offs

The additional route intentionally connects Khomani-Khan to the Underdark.
Adding it before the bridge preserves the bridge/fall/pyramid progression.
Compare zones 150 and 7000 against baseline: the expected entrance lists gain
15015 and 834025 respectively, with no new structural findings. Reuse valid
earlier relocation evidence; repeat unchanged routes once and the new path
through reset/restart, rather than retesting unrelated terrain four times.

#### Development validation and rollback

Regenerate and boot only development data, walk surface-to-UD and back, check
the immediate UD network, resets and restart, then publish the final stacked PR.
Reverting the two room edits removes the passage without changing saved identities.

### Completed development checks

#### 1. Validate endpoints

- [x] 1.1 Inspect grounded trail, connected UD tunnel, progression, and non-exit references.
- [x] 1.2 Capture loaded endpoints, ordinary forest/UD walks, vision/terrain, and baseline reports.

#### 2. Implement and prove

- [x] 2.1 Extend the existing regression and demonstrate the missing-connector failure.
- [x] 2.2 Add two open reciprocal exits and matching descriptions without changing other content.
- [x] 2.3 Pass authored/generated contracts and independently broken return-edge fixtures.
- [x] 2.4 Generate/build, run falling checks, and pass the full-world restart.
- [x] 2.5 Walk surface-to-UD and back through reset/restart and compare diagnostics.

#### 3. Publish and finish

- [x] 3.1 Update all five outcomes and acceptance checkboxes in the plan and #37.
- [x] 3.2 Review route documentation and scope, commit/push, and open the final PR stacked on #104.
- [x] 3.3 Verify all PR bases/heads and remote parity; leave ready for review without merging/deploying.

#### Historical route contract

##### Ordinary two-way Underdark passage

Misty Chasm must connect `15015 D -> 834025` and `834025 U -> 15015` through
an open stair passage requiring no key, flight, swim, or staff movement bypass.
The existing low-ceiling tunnel's ordinary terrain constraints must remain.

###### Verification: Surface to tunnel and back

- When a human on foot enters from 638825, follows the forest trail to 15015,
  descends to 834025, walks the adjoining UD tunnel network, and returns
- Verify each intended room is reached, and the player can return to 638825
- Also verify the route needs no fall, secret door, locked door, or staff-only movement

##### Preserve existing entrances and progression

The change must retain `638825 W <-> 15000 E`, both existing exits of 15015,
all room identities, bridge and shaft falls, pyramid locks, resets, and quests.

###### Verification: Existing area remains intact

- When the authored and generated world are checked
- Verify only the new reciprocal passage and its descriptions differ in the two endpoint records
- Also verify no existing exit is replaced or removed

##### Durable loaded routes

The new passage must remain loaded and traversable after zone reset and clean
restart, without new zcheck findings or one-way traps.

###### Verification: Reset and restart

- When zones 150 and 7000 reset and the world restarts
- Verify ordinary surface-to-UD and return journeys still pass
- Also verify diagnostics differ from baseline only by the intended new entrances
