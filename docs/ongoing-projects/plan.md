# Issue #37: zone placement and Underdark connection plan

Status: Outcasts Tower implemented and locally verified; Arcium and Misty Chasm pending.
Tracking: [#37 — Complete the workbook's zone placements and Misty Chasm Underdark connection](https://github.com/LuminariMUD/Duris/issues/37).
Working branch: `branch/issue-37-zone-placements`.
Source baseline: `0882c71c0228efd3608087660a7c9aa84df91327` (`master`), inspected 2026-10-15.

## Implementation handoff, 2026-10-15

- Refreshed #37 (open, no comments), `origin/master` at `34f3d8a62`, and the
  clean working branch at `de7904ce8`. Merged master without rewriting existing
  branch history; the pre-existing credits color fix is preserved.
- `.env` identifies this checkout as local. All acceptance servers use disposable
  flat-file authority and loopback ports; no production operations are authorized.
- Using OpenSpec `spec-driven` changes, starting with
  `openspec/changes/return-outcasts-tower/`. Subsequent focused PR chunks will
  relocate Arcium and connect Misty Chasm, stacked if their test/plan work depends
  on earlier chunks. Leave the issue and PRs open for review.
- Ablation: outcome is the three approved route changes plus explicit preservation
  of Homestead and Turolopolis. Non-goals remain engine changes, new tooling,
  production rollout, and #65. Files are the affected authored `.wld` sources,
  focused regression/journey tests, this plan, and OpenSpec. Proof is authored and
  generated route checks, the existing build/full-world restart test, loaded map
  inspection, reset checks, and ordinary-player traversal.
- Tower discovery: vacated footprint `615849` is a sector-0 placeholder titled
  Waters of the Abyss; its west/east neighbors `615848`/`615850` are DarkPeak hills
  with their inward exits absent. Restore hill terrain and all four reciprocal
  grid edges there. At new marker `546461`, remove the three non-entrance incoming
  edges and redirect `546861 N` to `11300`, retaining the existing marker-cell
  convention. The only native room-proc assignment of `11300` is disabled by
  `#if 0`; mob/object IDs with the same number are separate identities.
- Baseline `make world`, `make -C src -j2`, and the isolated full-world restart
  passed. The mortal journey confirmed loaded GC at 546861/543661, old tower
  access, secondary access, and unchanged Homestead/Turolopolis/Zoo pairs. Real
  `zreset ok` and paged `zcheck` reports were captured before content regeneration.
- Tower source changes are implemented. Authored and generated route tests pass;
  the test failed first on old data at `546861 N -> 11300`, and a disposable
  missing-return-edge fixture is rejected. All 1,315 existing falling paths still
  land. Strict OpenSpec and whitespace checks pass. The changed-world
  full-world restart passed. The changed-world walk exposed an incorrect test
  expectation: the pre-existing mountain 615449 north of the restored footprint
  rejects ordinary walking. Preserve that barrier and test its rejection; verify
  east/west/south approaches by walking. The corrected journey passed. Evidence is under
  `bin/analysis/issue37/`, especially `routes-baseline.json` and `routes-tower.json`.
- Git publication will preserve the existing credits commit on the requested
  branch and copy only the three planning commits plus this implementation onto
  `branch/issue-37-outcasts-tower` from current master. That PR excludes the
  unrelated credits change; later chunks will stack on its head without rewriting
  the original branch.
- Changed-world acceptance passed in four phases: initial boot, zone reset,
  clean restart, and another zone reset (544 recorded commands). All seven
  normalized zcheck reports match their baseline exactly in every phase:
  zones 113/300/530/857 clean; 358 has the existing 1 high/2 low findings;
  71 has 0 high/34 low; 150 has 0 high/13 low. These pre-existing findings do
  not establish new defects; the owner explicitly excluded Homestead/Turolopolis
  edits. No new dangling route, reciprocity gap, or inaccessible endpoint appeared.
- Actual `map 9` views and loaded `stat room` reports confirm GC for 546861 and
  543661. The coordinate comparison is the surface grid: (61,117) versus (61,109).
  Both entrance directions, retained Underworld pair, all accepted no-change
  entrance pairs, the eight-step ring around the new marker, and the old hill's
  east/west/south pairs were walked by a level-one human without movement,
  door, or vision bypass. Synthetic health/vitality reserves isolate combat and
  exhaustion. The old northern peak's ordinary movement rejection is preserved.
- Reproduction commands: `python3 tests/async/test_issue37_zone_routes.py`, the
  same command with `--generated`, `python3 tests/async/test_falling_world_exits.py`,
  `make world`, `make -C src -j2`, and
  `DURIS_REGRESSION_BUILD_CACHE=bin/tests/issue37-cache python3 tests/async/test_flatfile_full_world_boot.py`.
  Route acceptance: `DURIS_REGRESSION_BUILD_CACHE=bin/tests/issue37-cache python3 tests/async/run_issue37_zone_journey.py --evidence bin/analysis/issue37/routes-tower.json`.
  OpenSpec: `openspec validate --all --strict`. All passed.
- Next: commit/push the verified tower chunk and publish its focused PR; then
  select and validate Arcium's exact endpoints before editing its sources.

## Decisions from the owner discussion, 2026-10-15

- **Homestead: retain its current placement and connections.** The owner accepts
  it as it is for now. This resolves the blank Homestead request as no change;
  Arcium's relocation must not displace it or repurpose its existing entrance.
- **Turolopolis: retain everything as it is.** The owner explicitly accepted
  the existing placement, external entrance, and ruins/Zoo connection; no
  Turolopolis or Zoo change is part of this implementation.
  The current ordinary external approach is surface room **548452**, "Fertile
  Grasslands of the Hearth Valley", on source-inferred GC, at `(52,121)`.
  Walking north enters ruins room 7102; south returns to the surface. This is
  southwest of Kimordril's southern approach `(61,109)` in grid terms. This
  resolves the blank Turolopolis request as no change.
- **Misty Chasm: use the recommended direction.** Treat the request as zone 150,
  retain the Khomani-Khan surface entrance, and add a usable two-way Underdark
  passage. Selection of suitable endpoint rooms is implementation work, subject
  to the source and gameplay checks below, not another request for the owner
  to supply room IDs. Preserve the area's existing progression.
- **Arcium: move to a separate GC site northwest of Evermeet woodland.** The
  owner accepted this recommendation, leaving Homestead in place. Selection
  of exact room IDs and validation of the new site are implementation work;
  no further owner placement decision is required. The nearby "Acrium" label
  is a surface-room title, not the actual Arcium entrance: `517246 W` and
  `517645 N` lead to Homestead room 35800.
  Arcium room 85700 instead connects to 591773/592172 on source-inferred UC.
  The misleading title is not evidence that either area should be swapped into
  the other's entrance. Do not use Homestead's footprint for Arcium.
- **Outcasts Tower: site selection delegated; selected site recorded below.**
  Use the open Hearth Valley hill cell **546461** `(61,116)` as the new tower
  footprint, with the grassland approach **546861** `(61,117)` to its south.
  The planned pair is `546861 N -> 11300` and `11300 S -> 546861`. The footprint
  is seven rows south of Kimordril's southern approach `543661` `(61,109)`, on
  the same grid column. Keep the existing `11348 <-> 30172` Underworld route.
  This is the selected implementation site; runtime validation is still pending.

All five owner decisions are settled. Remaining endpoint selection, source
inspection, builds, and gameplay checks are implementation tasks, not unanswered
design questions. The issue remains open until the three approved changes are
implemented and verified; the two no-change decisions above are already resolved.

## Outcome and boundaries

Resolve all five requests in #37: place Arcium on the Good Continent northwest
of Evermeet woodland; retain Homestead and Turolopolis/Zoo unchanged; add the
agreed Misty Chasm connection to the Underdark; and return Outcasts Tower to the
Good Continent south of Kimordril. Every implemented route
must have exact source/destination room vnums, directions, intended return
behavior, and evidence from the generated and booted development world.

The issue is a request and discovery lead, not an authoritative description of
the world. Its workbook transcription has not been independently compared with
the original XLSX or live Google Sheet in this planning pass. Blank spreadsheet
destinations do not authorize invented relocations. An explicit owner decision
to retain an area's current placement is a valid resolution of a blank request;
an unanswered request is not complete.

This is content work. Preserve area/zone identities, existing room vnums, resets,
quests, and unrelated connections. Do not implement racial balance (#33/#34),
general map tooling, movement changes, migrations, or production deployment.
[Native zone connection tracking](zone-connections.md), tracked by
[#65](https://github.com/LuminariMUD/Duris/issues/65), is still a proposed feature
at this baseline. Use its reports if it lands in time, but do not implement #65
or make it a prerequisite for these placements.

## How this repository defines the world

- [areas/AREA](../../areas/AREA) selects the active authored area files.
  Presence of a `.wld` or `.zon` file alone does not establish that it is loaded.
  All six candidate area files below and Kimordril are active. The old
  `sylvandawn` area is not active, despite containing Evermeet names; do not use
  its obsolete room references as the current Evermeet landmark.
- [make_wld.c](../../areas/src/wld/make_wld.c) combines the selected `.wld`
  sources. The root [Makefile](../../Makefile) exposes `make world`, which builds
  the area tools and runs the existing `areas/m_slow` pipeline when inputs are
  stale. Edit authored files, not ignored/generated `areas/world.*`,
  `areas/tworld.*`, lookup files, or map archives.
- The surface source is [surface.wld](../../areas/wld/surface.wld), zone 5000;
  the principal Underdark map source is
  [underdark.wld](../../areas/wld/underdark.wld), zone 7000. Their
  [surface](../../areas/zon/surface.zon) and
  [Underdark](../../areas/zon/underdark.zon) zone headers specify 400 by 400 grids.
  `areas/map/*.json` is not the world input used by this loading path.
- [map.c](../../src/world/map.c), `calculate_relative_room()`, uses grid offsets
  from the zone's first room. For surface grid vnums 500000..659999,
  `column = (vnum - 500000) % 400` and
  `row = (vnum - 500000) / 400` using integer division. Columns increase east;
  rows increase south. Underdark grid vnums use origin 700000. The surface zone
  also has tail rooms through 660003 that are not grid cells. Do not confuse
  these grid coordinates with `calculate_map_coordinates()`'s graph-derived
  coordinates, where north increases `y` and different map sections cannot be
  compared directly. Account for map wrapping when choosing a relative position.
- `assign_continents()`/`set_continent()` in the same file assign continent IDs
  from seed rooms through reciprocal, same-zone, non-ocean exits. GC's seed is
  546926; EC's is 607066. An area name, room-number range, or a number in a zone
  header does not establish continent membership. Confirm the **surface
  approach** belongs to GC in the loaded world; area interiors need not inherit
  that continent ID because the algorithm does not cross zones.
- [db.c](../../src/world/db.c), `boot_world()`, assigns rooms by active zone
  boundaries; `setup_dir()` reads authored exits and `renum_world()` resolves
  destinations, removing unresolved exits. A boot that succeeds is therefore
  insufficient proof that every authored exit survived. Zone reset `D` commands
  can subsequently change door state.
- [zcheck.c](../../src/world/zcheck.c) audits loaded exits and resets. Its
  reachability scan can start inside a zone when no external entrance exists;
  it does not inspect every compiled proc or scripted trigger. Combine source
  inspection, `zcheck <zone-vnum>`, and actual ordinary-player traversal. Neither
  a clean report nor missing static edges proves all dynamic routes absent.

## Verified source inventory

Directions below are actual authored exits: N/E/S/W/U/D correspond to D0..D5.
Every stated reciprocal pair was checked in both authored files. The continent
labels below are **source-graph inferences**, obtained by following the current
surface exits with `set_continent()`'s reciprocal/non-ocean restrictions and seed
order; they are not observations from a running server. Grid coordinates are
zero-based `(column, row)`.

### Arcium — zone 857, rooms 85700..85818

Sources: [arcium.zon](../../areas/zon/arcium.zon),
[arcium.wld](../../areas/wld/arcium.wld), and `surface.wld`.

- `85700 E -> 591773`, with `591773 W -> 85700`.
- `85700 S -> 592172`, with `592172 N -> 85700`.
- The approaches are `(173,229)` and `(172,230)` on the inferred Undead
  Continent, not GC. The issue's room references are still current, and its
  relocation request is supported by source geography.
- Both exits belong to one entrance room. Moving only one pair would retain a
  cross-continent passage through that room. Relocate both together unless the
  owner explicitly chooses a different entrance shape.

### Abandoned Elven Homestead — zone 358, rooms 35800..35851

Sources: [elvish.zon](../../areas/zon/elvish.zon),
[elvish.wld](../../areas/wld/elvish.wld), and `surface.wld`.

- `35800 E -> 517246`, with `517246 W -> 35800`.
- `35800 S -> 517645`, with `517645 N -> 35800`.
- Approaches `(46,43)` and `(45,44)` are already on inferred GC and are named
  "The Magnificent Woodlands of Evermeet".
- Nearby surface cell `517245` is named **"Acrium"**, but the neighboring
  entrance edges point to Homestead, not Arcium. This label/route discrepancy
  does not authorize displacing Homestead or declaring Arcium already on GC.
  Keep its existing footprint out of Arcium's relocation.
- The workbook destination was blank. The owner has now explicitly accepted
  the current placement and connections; retain them.

### Turolopolis — connected ruins (zone 71) and Zoo (zone 530)

Sources: [willem.zon](../../areas/zon/willem.zon),
[willem.wld](../../areas/wld/willem.wld),
[turolzoo.zon](../../areas/zon/turolzoo.zon), and
[turolzoo.wld](../../areas/wld/turolzoo.wld).

- The Ruins of Turolopolis are zone 71, rooms 7100..7253.
  `7102 S -> 548452` and `548452 N -> 7102` form its surface entrance in the
  Hearth Valley on source-inferred GC, at surface grid `(52,121)`.
- Turolopolis Zoo is zone 530, rooms 53000..53061. It is already joined to the
  ruins: `7123 W -> 53000`, `53000 E -> 7123`. Its sole authored external exit
  is this connection, not a separate surface entrance.
- Ruins room 7198, "Lothrell's Start Spot", also has outbound exits N/E/S/W/U/D
  to 578047/532894/551641/550095/514897/524045 respectively. A scan of active
  authored exits found no incoming ordinary exit to 7198. Its description
  explicitly says it is not an explorable part of the zone and asks players
  who reach it to petition. Do not present its six outbound exits as ordinary
  entrances or as six normal travel connections. Dynamic access remains
  unproven. Leave this room and its exits unchanged.
- After reviewing the external connection, the owner explicitly accepted the
  whole area as it is. Preserve its current placement, surface entrance, Zoo
  connection, and all other content; no relocation or cleanup is requested.

### Misty Chasm — zone 150, rooms 15000..15099

Sources: [mist_chasm.zon](../../areas/zon/mist_chasm.zon) and
[mist_chasm.wld](../../areas/wld/mist_chasm.wld).

- The authored name is "The Chasm of the Misty Vale". The owner accepted the
  recommendation to use this area, retain its surface entrance, and add a
  traversable return route for the new Underdark connection.
- `15000 E -> 638825`, with `638825 W -> 15000`, is the area's only authored
  external exit. The surface approach is `(25,347)`, on inferred Khomani-Khan.
  Beyond that surface pair, there is no authored exit to zone 7000 or any other
  area.
  This is not proof that every possible dynamic Underdark route is absent.
- The request adds a connection; it does not request moving the existing
  surface entrance. Select a reachable in-area endpoint and an actual
  Underdark endpoint, then define the passage and return route. Do not assume
  the same grid offset on two maps makes suitable endpoints, or select a
  falling/air/blocked chasm room solely from its name.

### Outcasts Tower — zone 113, rooms 11300..11350

Sources: [otower.zon](../../areas/zon/otower.zon),
[otower.wld](../../areas/wld/otower.wld),
[underworld3.wld](../../areas/wld/underworld3.wld), and `surface.wld`.

- `11300 S -> 616249`, with `616249 N -> 11300`, is the surface entrance.
  The approach `(249,290)` is on inferred EC, supporting the request to move it
  back to GC.
- A second, reciprocal external route exists: `11348 N -> 30172`,
  `30172 S -> 11348`. Room 30172 belongs to The Underworld, zone 300, in
  `underworld3.wld`. That area has other external routes, including authored
  pairs `30281 N <-> 722840 S` and `30282 D <-> 709628 U` into the main
  Underdark map. Reachability between those endpoints still needs testing.
- Preserving the secondary route is the default. Record the topology impact
  of moving the tower's surface approach and explicitly resolve any intended
  change to that secondary route; do not silently sever it or infer that the
  surface move cannot affect travel between continents.
- [Kimordril](../../areas/zon/kimordril.zon) is zone 955. Its
  [authored exits](../../areas/wld/kimordril.wld) are reciprocal surface pairs
  `95502 W <-> 543256 E`, `95655 E <-> 542862 W`, and
  `95658 S <-> 543661 N`. These map approaches are `(56,108)`, `(62,107)`, and
  `(61,109)`, all on inferred GC. The selected new tower footprint is directly
  south of the last of these, as recorded in the owner decisions above.
- The selected footprint 546461 is ordinary hills, and approach 546861 is
  ordinary grassland. Both have zero authored room flags, reciprocal cardinal
  map exits, and no existing area entrance. A search of zone resets, objects,
  quests, triggers, and native sources found no direct reference to either vnum.
  A reciprocal route over road/field/hill/forest sectors exists from Kimordril's
  western approach to this neighborhood; actual traversal remains to be tested.
- Do not reuse the old surface label "Outcast Tower" at 551267 merely because
  of its name: the southern approach 551667 currently enters room 9288, not
  11300. Also leave the nearer hill cell 545661 alone: its surface reset loads
  the named NPC Surak there. Neither existing location is needed for this move.
- At the new site, `546861 N` currently reaches 546461. Apply the repository's
  occupied-map-cell convention to the footprint and review the other incoming
  edges (`546061 S`, `546460 E`, `546462 W`) so none becomes an accidental
  one-way entry into the marker cell. Preserve ordinary movement around the
  footprint and the surrounding NPC routes; do not merely replace one exit and
  leave the rest of the footprint inconsistent.

## Implementation sequence

### 1. Record exact endpoints and verify the baseline

- [ ] Refresh `master`, #37, and any intervening content changes; recheck this
  inventory against the exact implementation base. Confirm the test environment
  is local/dev without copying credentials into evidence.
- [ ] Inspect a fresh development world's candidate zones and their approaches.
  Capture each zone's `zcheck` output, actual entrance directions, relevant
  door/reset state, and map views. Check relevant object/room/mob procs, triggers,
  and teleport references for affected vnums; ordinary exits are only the
  initial inventory. Exclude inactive files and disabled C++ blocks when deciding
  what actually runs.
- [x] Record all five owner decisions in this document; no design questions remain.
- [ ] Record exact implementation endpoints in this document and #37. For every
  changed route, specify area/zone identity; old and new endpoint vnums; directions; surface/UD
  grid coordinates and landmark; continent/map section; door/key/terrain
  requirements; reciprocal or intentionally asymmetric behavior; and affected
  authored files. Record the owner's decision source/date and old-link disposition.
- [x] Arcium: owner accepted a separate GC site northwest of Evermeet woodland,
  preserving Homestead and its existing entrance.
- [ ] Select and verify a free Arcium site northwest of the active Evermeet
  woodland. Record the map reference used for the relative-position check and
  the exact endpoint vnums/directions. Do not select Homestead's footprint
  `517245` or repurpose its approaches `517246`/`517645`.
- [x] Homestead: explicit owner decision received to retain current placement
  and connections.
- [x] Turolopolis: owner accepted the entire area as it is; retain current
  placement, external entrance, ruins/Zoo connection, and other content unchanged.
- [x] Misty Chasm: owner accepted the recommended area and two-way connection,
  retaining its current surface entrance.
- [ ] Select and verify both Misty connector endpoints, including how an
  ordinary player reaches and leaves them. Prefer existing rooms and an
  ordinary reciprocal passage. Add the minimum connector rooms only if the
  agreed geography needs them, using verified unused vnums within valid zone
  bounds rather than renumbering existing rooms.
- [x] Outcasts Tower: owner delegated site selection; chose footprint 546461
  and southern approach 546861, retaining the secondary Underworld route.
- [ ] Verify the selected tower site and the impact of retaining its secondary
  Underworld route in the booted development world.

**Implementation prerequisite:** select and validate the exact endpoints before
editing each approved route. The owner decisions above supply the intended
behavior; technical room selection does not need another design discussion.
Keep #37 open until Arcium, Misty Chasm, and Outcasts Tower are implemented and
verified, with Homestead and Turolopolis recorded as accepted without changes.

### 2. Edit the authored connections as complete route changes

- [ ] Change Arcium's entrance and both surface counterparts together. Change
  Outcasts Tower's surface pair together, preserving its secondary connection
  unless the recorded decision explicitly changes it.
- [ ] For each vacated entrance, inspect the map cell that the old entrance
  displaced and its neighbors. Restore the intended terrain, description, and
  ordinary map connections; remove all superseded entrances and unintended
  one-way remnants. Do not blindly restore numerical grid neighbors: existing
  placeholder cells can have sector 0 and misleading names, such as the old
  cells beside Arcium and Outcasts Tower.
- [ ] At each new site, check existing exits, terrain, area occupancy, and
  neighboring travel first. Change only the approach edges needed for the
  approved footprint; do not overwrite another area's entrance. Make entrance
  descriptions and relevant map labels agree with the final routes.
- [ ] Keep Homestead and Turolopolis/Zoo unchanged, including their surface
  approaches, the Zoo link, the transit-room exits, and resets/quests. Record
  the accepted no-change outcomes without editing their authored content.
- [ ] Add the agreed Misty connector in both directions. Preserve its existing
  surface entrance and internal progression. If a door, switch, or connector
  room is required, update only the necessary corresponding authored reset,
  object, or trigger data; verify accessibility after reset. Avoid new native
  procs where an ordinary authored exit solves the request.
- [ ] Review every incoming/outgoing reference to the changed endpoint rooms,
  including teleport/proc references actually found during step 1. Preserve zone
  IDs and existing room IDs. Change zone bounds or `AREA` only if an agreed new
  connector cannot fit the existing active area, with explicit overlap checks.

### 3. Prove the source and generated-world contracts

- [ ] Add a focused `tests/async/test_issue37_zone_routes.py` regression using
  the approved route decisions as expected results. Read active authored data
  rather than relying on pre-existing `areas/world.*` outputs. Check endpoint
  existence and zone ownership, expected directions/reciprocity, removal of
  superseded entrances, preservation of named secondary routes, and any new
  connector vnum uniqueness. Do not impose universal reciprocity on unrelated
  intentional one-way exits or build a general connectivity framework.
- [ ] Run the focused regression against the old data where applicable to
  demonstrate it catches the requested relocation/missing connector, then run
  it on the changed data. Also demonstrate that breaking one required return
  edge fails the check, using a disposable test fixture.
- [ ] Run `make world` in development. Verify the generated room records for
  all changed endpoints and their reverse exits, and inspect generator output
  for missing/ambiguous area files. Generated output is verification material,
  not committed source.
- [ ] Build the development server with `make -C src`. If C/C++ changes prove
  necessary, also run `./scripts/format.sh --check` and the smallest applicable
  executable regression; explain the concrete need before expanding scope.
- [ ] Run `python3 tests/async/test_flatfile_full_world_boot.py` to exercise a
  fresh full-world boot/restart on disposable authority with current generated
  data. This existing test checks full-world boot and ferry route viability,
  but does **not** replace the route-specific journeys below.

### 4. Walk the changed routes and verify geography

Use an isolated development instance and synthetic/test characters. The
disposable full-world setup in
[test_flight_network_journey.py](../../tests/async/test_flight_network_journey.py)
and [test_flatfile_full_world_boot.py](../../tests/async/test_flatfile_full_world_boot.py)
provides existing setup patterns if automating these journeys. Do not build a
second server launcher. Staff inspection or teleporting to a starting point is
setup, not proof that an ordinary player can traverse the passage.

- [ ] Walk from the surrounding surface map into each relocated area and back
  through every intended entrance. Check the old sites no longer enter the
  moved area and that their surrounding map routes remain usable.
- [ ] Verify Arcium's final approach is GC and northwest of the chosen Evermeet
  landmark, and the tower's approach is GC and south of the chosen Kimordril
  landmark. Record actual vnums, grid coordinates, map views, and the loaded
  continent evidence; compare coordinates in one stated coordinate system.
- [ ] Walk Misty's surface approach, internal path to the new connector,
  connector into the Underdark, and return path. Test under the intended player
  movement/vision requirements without staff bypass; inspect falls, water,
  secret/blocked doors, and resets on the chosen route.
- [ ] Recheck the tower's retained `11348 <-> 30172` route and confirm the
  unchanged Homestead and Turolopolis/Zoo entrances remain intact. Check relevant
  existing quest/reset progression rather than assuming unchanged IDs suffice.
- [ ] Repeat affected `zcheck` reports after a zone reset and a clean restart.
  Compare with the pre-change baseline, investigate new dangling exits,
  unintended one-way traps, or inaccessible required endpoints, and distinguish
  existing unrelated findings. Inspect loaded endpoints explicitly because
  `renum_world()` can remove invalid authored exits during boot.

### 5. Review and close out the implementation

- [ ] Reread the diff and remove unrelated changes. Expected content files are
  `arcium.wld`, `mist_chasm.wld`, `otower.wld`, `surface.wld`, the selected UD
  endpoint's authored file, and only required companion `.zon`/`.obj`/`.trg`
  files. Homestead, the ruins, and the Zoo are excluded from content edits. Keep
  engine files unchanged unless a demonstrated blocker requires a narrow fix.
- [ ] Run `git diff --check`, the focused route regression, and any required
  checks invalidated by the final edits. Inspect staged paths for generated
  areas, binaries, credentials, logs, or account/player data before committing.
- [ ] Update this plan and #37 with a per-request outcome: exact old/new routes,
  the two blank-destination decisions, test commands/results, runtime evidence,
  and remaining blockers. Do not close #37 while an item is merely pending a
  destination, while a required walk is unperformed, or because #65 landed.
- [ ] Publish the implementation for review under the repository's normal
  review requirements. Hosted CI is not a substitute for or prerequisite to
  the required local evidence. Production rollout remains a separate authorized
  operation; no production mutation is part of this planning task.

## Planning-pass verification and publication

Completed for this document:

- Read #37 and #65, the active area list, candidate zone/room sources, incoming
  authored exits, map/grid/continent code, world loading/generation, `zcheck`,
  and existing isolated full-world test patterns at the baseline above.
- Rechecked candidate external edges and their reverse records across the
  active authored world. Computed source-grid positions and continent inferences;
  these remain explicitly separate from runtime acceptance.
- Validated local Markdown links and all five request sections. Read-only
  assertions checked the quoted candidate external/return edges, the absence
  of authored incoming exits to room 7198, and the inactive Evermeet-area warning.
- Kept the plan to source changes, one focused route regression, existing build
  and boot tooling, and the required gameplay journeys. A new reporting system,
  new service, bulk zone cleanup, or #65 implementation is unnecessary here.

Publication is a docs-only commit on `branch/issue-37-zone-placements`, natively
linked to #37. #65 remains separately tracked supporting work, not a second issue
claimed for implementation by this branch. Verify the published plan blob and
exact local/remote commit equality, ahead/behind `0 0`, a clean working tree,
and the issue's linked-branch readback before reporting publication complete.

During the historical planning pass, no world generation, server build, boot,
gameplay acceptance, area-data edit, or production operation was performed.
Current implementation evidence and remaining work are recorded at the top.
