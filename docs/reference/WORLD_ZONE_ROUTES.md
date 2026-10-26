# World zone routes

These route contracts describe the authored world after
[PR #204](https://github.com/LuminariMUD/Duris/pull/204). Current room sources and
[route checks](../../tests/async/test_issue37_zone_routes.py) remain the authority
for future changes. Earlier placement decisions are retained separately in the
[October 15 implementation record](../records/2026-10-15-zone-placements.md);
the older Arcium and tower coordinates in that record are superseded.

Directions below form reciprocal exit pairs. A map marker is a labeled footprint,
not an ordinary room to enter. Room identities, interior exits, flags, resets,
quests, terrain barriers and unrelated secondary routes stay intact.

## Arcium, Homestead and Turopolis

Place Arcium on GC northwest of Evermeet, move Homestead to Turopolis's vacated
site, and move Turopolis to the Eagle Ridge Delta while preserving progression.

### Two Good Continent approaches

Arcium must connect through `517246 W <-> 85700 E` and `517645 N <-> 85700 S`,
replacing Homestead at map marker `517245`. Both approaches must be GC in the
Evermeet woodlands. The superseded approaches at `516444`/`516843` and the former UC approaches
at `591773`/`592172` must not enter Arcium.

#### Verification: Enter and leave through either approach

- When an ordinary player walks each new entrance and its return
- Verify the expected rooms are reached without staff movement bypass
- Also verify loaded continent and surface grid coordinates establish the required placement

### Relocate Homestead and Turopolis with coherent map travel

Homestead must use marker `548052`, with `548452 N <-> 35800 S` and
`548053 W <-> 35800 E`, preserving both wilderness approaches at its new location
and replacing Turopolis's former surface entrance. Both Homestead exits must
return to their new approaches, leaving no return to the former location. Turopolis must use marker `584445` and
`584845 N <-> 7102 S`. Its Zoo route `7123 W <-> 53000 E` must remain unchanged.
All three markers must have accurate zone labels and no ordinary incoming map
exit. Vacated Arcium footprint `516443` and the previously restored `591772`
must be hills with reciprocal cardinal grid edges.

#### Verification: Old site and surrounding map

- When a player walks the vacated approaches and around the new sites
- Verify the intended ordinary routes remain usable
- Also verify the existing mountains retain their ordinary movement barriers
- Also verify both Homestead approaches and Turopolis's entrance have their specified returns
- Also verify the Zoo route remains usable

### Preserve existing progression

The relocations must preserve room identities, interior exits, flags, resets,
quests, and unrelated secondary connections in all three zones.

#### Verification: Zone reset and clean restart

- When the world resets and restarts
- Verify all five surface entrance pairs remain loaded and traversable
- Also verify no new zcheck finding, dangling exit, or one-way trap is introduced

## Outcasts Tower and Lizizania

Place Outcasts Tower on GC south of Kimordril and Temple of Lizizania on EC south
of Torg while preserving the tower's Underworld route and coherent map travel.

### Good Continent surface access

Outcasts Tower must connect through `551667 N -> 11300` and `11300 S -> 551667`
at marker `551267` on the Good Continent south of Kimordril, replacing Lizizania's
surface entrance. The superseded entrance from `546861` must be removed.

#### Verification: Ordinary player enters and returns

- When a player walks north from 551667 and south from 11300
- Verify the player reaches 11300 and returns to 551667 without staff movement bypass
- Also verify 551667 is on loaded GC at (67,129), south of Kimordril at (61,109)

### Coherent map footprints and Lizizania access

The vacated footprint `546461` must have hill terrain and reciprocal cardinal
grid exits. Lizizania must use marker `615849` and
`616249 N <-> 9288 S` on EC south of Torg. Both active markers must have accurate
zone labels and no ordinary incoming map exit. Lizizania must no longer return
to `551667`.

#### Verification: Surrounding travel

- When a player traverses the old site and walks around the new footprints
- Verify all intended map routes remain usable without entering an isolated marker
- Also verify 546861 north reaches the restored hills at 546461
- Also verify 616249 north reaches Lizizania at 9288 and south returns to 616249

### Preserve existing progression and secondary access

The relocation must preserve `11348 N -> 30172` and `30172 S -> 11348`, tower
resets and interior exits, and Lizizania's internal routes, resets, and quests.

#### Verification: Reset and restart

- When the development world resets and restarts
- Verify both zones' surface pairs and the tower's secondary pair remain loaded and traversable
- Also verify no new dangling exits or one-way traps are introduced

## Misty Chasm and the Underdark

Provide ordinary two-way travel between Misty Chasm and the Underdark while
preserving its surface entrance and existing area progression.

### Ordinary two-way Underdark passage

Misty Chasm must connect `15015 D -> 834025` and `834025 U -> 15015` through
an open stair passage requiring no key, flight, swim, or staff movement bypass.
The existing low-ceiling tunnel's ordinary terrain constraints must remain.

#### Verification: Surface to tunnel and back

- When a human on foot enters from 638825, follows the forest trail to 15015,
  descends to 834025, walks the adjoining UD tunnel network, and returns
- Verify each intended room is reached, and the player can return to 638825
- Also verify the route needs no fall, secret door, locked door, or staff-only movement

### Preserve existing entrances and progression

The change must retain `638825 W <-> 15000 E`, both existing exits of 15015,
all room identities, bridge and shaft falls, pyramid locks, resets, and quests.

#### Verification: Existing area remains intact

- When the authored and generated world are checked
- Verify only the new reciprocal passage and its descriptions differ in the two endpoint records
- Also verify no existing exit is replaced or removed

### Durable loaded routes

The new passage must remain loaded and traversable after zone reset and clean
restart, without new zcheck findings or one-way traps.

#### Verification: Reset and restart

- When zones 150 and 7000 reset and the world restarts
- Verify ordinary surface-to-UD and return journeys still pass
- Also verify diagnostics differ from baseline only by the intended new entrances

## Underdark entrance markers

The October 26 missing-marker report is covered by eight labeled footprints:

- Mushroom Caverns: marker `819888` north of `820288 U <-> 24101 D`,
  and marker `824682` north of `825082 U <-> 24237 D`.
- Pragtog's Domain: reported footprint `822268` north of
  `822668 D <-> 10649 U`.
- The Tunnels of Cyric the Destroyer: marker `746083` north of
  `746483 D <-> 54554 U`.
- Caves of Mt. Skelenak: marker `709264` north of `709664 U <-> 4093 D`.
- The Stone Tomb of Kelek: marker `856819` north of `857219 D <-> 87950 U`.
- The Underworld Shafts: marker `844448` north of `844848 U <-> 10021 D`.
- The Chasm of the Misty Vale: marker `834024` west of `834025 U <-> 15015 D`.

These footprints use the existing zone glyph and marker flags, with no incoming
exits. Cyric's footprint fills an unused grid square; the other seven replace
mountain squares. The travel rooms keep their terrain and reciprocal zone exits,
including the Mushroom Caverns pool and the falling Underworld Shafts passage.

## Verification commands and boundaries

```sh
python3 tests/async/test_issue37_zone_routes.py
python3 tests/async/test_ud_zone_markers.py
make world
python3 tests/async/test_issue37_zone_routes.py --generated
python3 tests/async/test_ud_zone_markers.py --generated
python3 tests/async/test_falling_world_exits.py
python3 tests/async/test_documentation_contract.py
```

The route regression rejects independently broken return edges and checks marker
labels/flags, vacated hills and superseded entrances. Generated-world checks need
`make world` first. The existing
[isolated mortal journey](../../tests/async/run_issue37_zone_journey.py) covers
loaded routes, ordinary movement, reset/restart, terrain and diagnostics. Its
staff setup establishes starting points and reserves; it does not prove ordinary
acquisition or production acceptance. Changes to authored C/C++ still require the
normal server build; no specification generator is part of the game build.
