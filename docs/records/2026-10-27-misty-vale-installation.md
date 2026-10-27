# Misty Vale replacement — issue #403

Source: `Misty_Vale_proposed_zone_3000_no_push.zip`, supplied by the owner.
SHA-256: `897b87496ac382ccd851c7b49460a79909592b9a70e536ac3afdd3309ae3f24b`.
Base: `f0264a484`. The owner explicitly chose replacement of zone 150 with
zone 3000, retaining the surface and Underdark connections, and requested
changes only where something is broken.

## Installation

The six authored `thechasmofthemistyvale` files supply 167 rooms, 38 mobile
prototypes, 42 object prototypes, 21 quest-giver records, and one shop.
`areas/AREA` reserves 3000–3001, with zone top 300199. Existing active sources
have no overlapping room, mobile, or object IDs in this allocation.

The old zone's rooms, resets and quests are retired. Its mobile and object
prototypes remain indexed under `mist_chasm` so existing saved gear and pets
still have their original prototype IDs. No old populations are spawned.
The old allocation is marked retired rather than offered for reuse.

Connections:

- Surface: `638825 W <-> 300000 E`.
- Underdark: `300019 D <-> 834025 U`; marker 834024 remains unchanged.
- Dirkn: object 300031 in room 300166 enters room 96821; well 96824 returns
  to 300166. This applies the supplied change from drink container to portal;
  the well no longer serves as a drink container.

## Demonstrated defects repaired

- The package had no outside entrance or Underdark connection. Both are now
  reciprocal, with an ordinary walking route through the expanded forest.
- Global mobile limits of one suppressed repeated authored reset rows and
  follower groups. Limits now cover the number of authored instances of each
  prototype. Object limits likewise cover repeated authored placements/drops.
  Spawn rows, probabilities, stats and reward amounts were not redesigned.
- The warrior advertised either scale, but only one `Q` block collected both
  scales and both payments. A second recipe delimiter makes the alternatives
  independent, retaining their original 25/50 platinum rewards.
- Gynaeros (mobile 300006) had only the placeholder keywords `new mob`, so her
  displayed name and role could not target either quest. Her keywords are now
  `gynaeros pygmie shaman`, allowing ordinary `ask` and `give` commands.
- Winterhaven still requires old necklace 15012. The existing casket and
  necklace reset now reside in the replacement burial chamber. The surface
  hermit accepts both legacy potion 15008 and replacement potion 300036.
- Necklace 300033 had no neck wear flag despite its neck equip reset. Tunic
  300035 used the legs slot. Those flags now match the authored uses.
- Canoe 300038 was a vehicle, which does not satisfy ordinary boat travel.
  It now uses the native boat type. The fishing command's explicit pole list
  now recognizes the new rod, 300039.
- Pond 300028 was portable and lacked `ITEM_FLOAT`. Native placement submerged
  it out of sight, and a mortal's `enter pond` failed. It is now a fixed,
  floating entrance. No room sector was changed to work around the failure.

One description for an age-ambiguous young NPC was replaced with nonsexual
foraging text. Other prose, stats, recipes, departure behavior, portal actions,
switch puzzles and fall paths are preserved from the supplied package.

The package notes' suggestion to make the weaver reusable was not implemented:
each recipe still has its authored `D` departure behavior. The native journey
resets the zone between recipes and checks the departure after each turn-in.

## Verification

Evidence and build logs are retained locally under `bin/issue403/`; generated
world outputs, binaries, logs, synthetic accounts and the original ZIP are not
committed.

Passed:

- `make -C src -j6 PERSISTENCE_BACKEND=flatfile`.
- `make -C src -j6 SERVER_BIN_DIR=$PWD/bin/server/mariadb` (default MariaDB profile).
- `make world` and `./scripts/format.sh --check`.
- `python3 tests/async/test_misty_vale_zone.py`: allocation/collisions, all 167
  rooms reachable including portals, no dangling exits or references to retired
  rooms, reset caps, quest targets/recipes, switches, and item roles.
- `python3 tests/async/test_issue37_zone_routes.py` and
  `python3 tests/async/test_ud_zone_markers.py`, both authored and `--generated`.
- `python3 tests/async/test_falling_world_exits.py`: 1,314 fall entries over
  253,452 rooms terminate; longest fall 27 rooms.
- `python3 tests/async/test_area_object_bitvector5_contract.py` and
  `python3 tests/async/test_area_filename_case.py`.
- `run_issue37_zone_journey.run()` with the freshly built flat-file binary:
  ordinary mortal surface/Underdark walks before/after reset and clean restart;
  938 command/phase records in `bin/issue403/routes.json`.

The focused native mechanics journey is
`python3 tests/async/run_misty_vale_journey.py --server bin/server/dms_new --evidence bin/issue403/journey.json`.
It passed all 13 checks with 369 recorded commands: all five portal pairs, all
five switches, sampled native populations (19 male pygmies, three lion
followers, two wyvern followers, nine forest salamanders), all five weaver
recipes and their incomplete-hand-in gates/departures, independent small/large
scale exchanges, both shop purchases, native fishing, and survival of every
crafting reward plus the purchased canoe across a clean restart.

Native `zcheck 3000` reports **0 high / 46 low** findings and no disabled reset
commands. The low findings are 23 rooms accessible through object portals and
23 asymmetric fall/portal-return edges. The static traversal includes portals;
the native journey exercises their actual commands and returns. No one-way
traps are reported.

It uses synthetic accounts, staff-supplied discovered recipe ingredients, and
tranquilized local NPCs, with combat effects cleared, to isolate mechanics from
combat. A fixture warrior is loaded in the treehouse for hand-ins because the
authored warriors roam. It does not qualify
encounter balance or the difficulty of gathering ingredients. Ordinary route
acceptance is covered separately by the route journey above. MariaDB was built;
the gameplay journeys use isolated flat-file authority.

### PR #404 review follow-up

The Gynaeros keyword regression failed against the original `new mob` record
and passed after the keyword repair. The native journey now asks about scales
and completes both shaman quests using `shaman` and `gynaeros`, checking each
reward, incomplete hand-ins, and the authored departure.

Passed again after this data-only fix:

- `python3 tests/async/test_misty_vale_zone.py`.
- `make world`.
- `python3 tests/async/run_misty_vale_journey.py --server bin/server/dms_new --evidence bin/issue403/pr404-journey.json`:
  all 15 checks, including the two added shaman quests and the existing zone
  mechanics/restart checks.
- `python3 -m py_compile tests/async/test_misty_vale_zone.py tests/async/run_misty_vale_journey.py`.
- `./scripts/format.sh --check` and `git diff --check`.

The server binary matches the SHA-256 in the original passing journey evidence.
The existing flat-file/MariaDB builds and route qualification remain applicable;
no C/C++, routes, reset definitions, or quest recipes changed in this follow-up.

## Rollout boundary

This change installs and qualifies the zone in an isolated local world. It does
not deploy production, merge the PR, or mutate existing accounts/player data.
Before a live replacement, operators must account for saved locations and
floor/corpse custody referring to retired rooms 15000–15099. Keeping legacy
prototypes preserves identities; it is not a migration of those room references.
The original zone remains recoverable from Git history.
