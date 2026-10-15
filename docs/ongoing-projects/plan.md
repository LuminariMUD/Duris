# Issue #37: zone placement and Underdark connection plan

Status: all five requests resolved and locally verified; owner accepted the three-PR stack for merge.
Tracking: [#37 — Complete the workbook's zone placements and Misty Chasm Underdark connection](https://github.com/LuminariMUD/Duris/issues/37).
Original branch: `branch/issue-37-zone-placements` (existing credits fix preserved).
Tower: [PR #103](https://github.com/LuminariMUD/Duris/pull/103), squash `31de38db9`.
Arcium: [PR #104](https://github.com/LuminariMUD/Duris/pull/104), squash `dbb48c013`.
Misty and final closeout: [PR #105](https://github.com/LuminariMUD/Duris/pull/105).
Source baseline: `0882c71c0228efd3608087660a7c9aa84df91327` (`master`), inspected 2026-10-15.

## Implementation handoff, 2026-10-15

- Refreshed #37 (open, no comments), `origin/master` at `34f3d8a62`, and the
  clean working branch at `de7904ce8`. Merged master without rewriting existing
  branch history; the pre-existing credits color fix is preserved.
- `.env` identifies this checkout as local. All acceptance servers use disposable
  flat-file authority and loopback ports; no production operations are authorized.
- Used three OpenSpec `spec-driven` changes for tower, Arcium, and Misty Chasm.
  They are now archived under `openspec/changes/archive/2026-10-15-*`, with the
  final requirements maintained in `openspec/specs/`.
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
- Git publication preserved the existing credits commit on the requested
  branch and copied only the three planning commits plus this implementation onto
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
- Tower implementation is published for review as PR #103, implementation commit
  `594a3151e`. Its source/test/spec/plan files exactly match the tested original
  branch checkpoint `cd71ac1e8`; only the unrelated credits fix is excluded.
  No tag was needed at that review checkpoint. Production deployment remains separate.
- Arcium continues on `branch/issue-37-arcium` from the tower PR. Selected
  footprint 516443 (43,41), east
  approach 516444 (44,41), south approach 516843 (43,42). These are unoccupied
  hills/field, northwest of the active Evermeet approach 517246 (46,43), and do
  not use Homestead's footprint or entrances. Its loaded baseline passed, as below.

### Arcium chunk completed

OpenSpec: `openspec/changes/archive/2026-10-15-relocate-arcium/`. Keep the two-entrance shape:
`516444 W <-> 85700 E` and `516843 N <-> 85700 S`; remove both old UC pairs at
591773/592172. Marker 516443 must have no ordinary incoming map edges; remove
the northern/western incoming edges from 516043/516442. Restore old footprint
591772 to vine-covered hills, preserving its north/west mountain boundaries.
The approaches are northwest of active Evermeet room 517246 (46,43) in the
same zero-based surface grid, with Homestead's 517245/517246/517645 untouched.

Source inspection found no direct native/reset/object/quest/trigger references
to the selected map cells. The candidate rooms have zero flags and ordinary
hills/field terrain. The pre-edit loaded-world baseline passed (including reset),
confirming GC, `map 9` views, old Arcium pairs, and retained routes. Both entrance
pairs and the two footprints are now edited; authored/generated checks pass,
after the old-data check failed at `516444 W -> 85700`. Each Arcium return edge
is independently removed in an in-memory fixture and rejected. Outcome/non-goals remain those above;
files are `arcium.wld`, `surface.wld`, the existing route tests, OpenSpec, and
this plan. Proof extends the already-used source/generated, ordinary walking,
geography, reset, restart, and zcheck checks. No new parser, launcher, connector
room, or native procedure is needed.

The area's D resets do not target 85700; the existing hermit quest uses the
unchanged lord item IDs, with no map-room dependency. Interior exits, room flags,
the quest, and resets are byte-for-byte unchanged. `make world` and
`make -C src -j2` passed. Cumulative ordinary walking and the existing full-world
restart test passed; evidence prefixes are `routes-arcium-baseline`,
`routes-arcium`, and `full-world-arcium` under `bin/analysis/issue37/`.
Both approaches, both returns, restored old-site east/south travel and north/west
mountain rejections, and surrounding map paths passed across boot/reset/restart/reset.
All seven normalized zcheck reports match baseline exactly in all four phases.
The earlier tower and accepted no-change routes passed again. Strict OpenSpec,
scoped diff review, and whitespace checks passed. No native or companion
reset/object/quest/trigger changes were needed.
Published as PR #104, implementation commit `4c74de53d`; 820 acceptance commands
were recorded. Next: create `branch/issue-37-misty-underdark` from this PR and
validate the source-selected candidate `15015 D <-> 834025 U`. Room 15015 is a
grounded cliff trail before the rope bridge; 834025 is an existing low-ceiling
Underdark tunnel at (25,335), with open northern/eastern continuation. No new
room is needed, and this avoids changing falls, the bridge, shafts, or pyramid
progression. The UD candidate belongs to a large connected tunnel component
with multiple existing area entrances; it is not selected by matching map
offsets. Confirm ordinary walking, vision/terrain constraints, and loaded exits
before editing. Preserve `638825 W <-> 15000 E` on Khomani-Khan.

### Misty Chasm chunk completed

OpenSpec: `openspec/changes/archive/2026-10-15-connect-misty-underdark/`. Outcome is a two-way,
open stair passage `15015 D <-> 834025 U`; no keys, doors, new rooms, reset
rows, native procs, or special movement are needed. Only the two authored room
records and descriptions change, in `mist_chasm.wld` and `underdark.wld`.
Existing surface access, bridge/fall/shaft/pyramid progression, room flags,
resets, and quests remain intact. No direct native/room-reset/trigger reference
was found for these endpoints; object/mob 15015 references are separate identities.

The ordinary surface path to 15015 is `638825 W 15000 W 15001 S 15006 S 15007
W 15008 W 15009 W 15010 N 15011 W 15012 N 15013 N 15014 W 15015`, with reverse
exits throughout. Its UD continuations are `834025 N <-> 833625 S` and
`834025 E <-> 834026 W`. An initial test's assumed square walk correctly failed
at 833626, an existing impassable cavern wall; the test now follows the two
verified tunnel branches and leaves that terrain intact. The pre-edit mortal
journey passed before editing, including a reset, both zones' zcheck reports,
endpoint stats, visible room titles, ordinary tunnel walking, and the return
forest trail. No flight, swimming, special vision, or movement privilege was
used. The source regression first rejected the absent `15015 D -> 834025` edge.

The two exits and matching descriptions are implemented. Authored/generated
contracts pass, including an independently removed UD return edge. `make world`,
`make -C src -j2`, and all 1,315 falling paths pass. The existing `areas/m_slow`
pipeline was also captured directly: no missing/ambiguous/error diagnostics,
and generation completed normally. Logs are under `bin/analysis/issue37/`,
with `routes-misty-baseline.json`, `world-generator-final.log`, and the successful
`routes-final`/`full-world-final` acceptance outputs.

Ablation retains prior relocation/reset evidence, rechecks those routes once,
and repeats the newly affected Misty/UD route and zones through reset/restart.
There is no reason to repeat unrelated old-site terrain four more times after
changing only these two rooms. All source/generated route contracts still run.
The final journey passed boot/reset/restart/reset (515 recorded commands), with
visible mortal room titles, no special movement or vision, the complete forest
trail in both directions, and both adjacent UD branches. Zone 150 retains
0 high/13 low findings and zone 7000 retains 0 high/197 low findings. Their
normalized reports differ only in the expected entrance list: 15015 added to
zone 150, and one extra entrance (834025, inspected directly) to zone 7000.
All other reports are unchanged; earlier relocation and accepted no-change
routes passed again. The full-world restart test also passed with the final data.

Final scope audit against `origin/master` (`34f3d8a62`): exactly 21 existing room
records changed across five authored world files. No room IDs were added or
removed. All native source, AREA selection, zone/reset/mob/object/quest/trigger
files, Homestead, Turolopolis ruins, and Zoo match master byte-for-byte. No
generated world, binary, log, credential, or player/account data is committed.

All implementation is complete. The owner authorized merging the stack on
2026-10-15. It lands in tower (#103), Arcium (#104), then Misty Chasm (#105)
order through squash merges, as required by master's linear-history rule.
Each dependent branch is rebased onto the preceding squash without changing
its verified content. Fresh source contracts pass; the unchanged world content
retains the recorded build, generation, gameplay, reset, and restart evidence.
Each landed tree and its single expected parent are checked against the PR head.

Issue #37 records all five outcomes and completed acceptance checks; close it
after verifying the final merge. The three OpenSpec changes are archived and
their canonical specifications validate strictly. There is no remaining
implementation work. Production deployment remains a separate operation.
The original integration branch retains its existing credits fix, which is
excluded from these focused PRs. No release tag is appropriate for this content work.

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
  This is the selected implementation site; runtime validation is complete above.

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

## Pre-change source inventory

This inventory records the planning baseline, before the changes above; use the
implementation handoff for final routes. Directions are N/E/S/W/U/D = D0..D5.
Every stated reciprocal pair was checked in both baseline authored files. The continent
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

## Completed implementation checklist

### 1. Record exact endpoints and verify the baseline

- [x] Refresh `master`, #37, and any intervening content changes; recheck this
  inventory against the exact implementation base. Confirm the test environment
  is local/dev without copying credentials into evidence.
- [x] Inspect a fresh development world's candidate zones and their approaches.
  Capture each zone's `zcheck` output, actual entrance directions, relevant
  door/reset state, and map views. Check relevant object/room/mob procs, triggers,
  and teleport references for affected vnums; ordinary exits are only the
  initial inventory. Exclude inactive files and disabled C++ blocks when deciding
  what actually runs.
- [x] Record all five owner decisions in this document; no design questions remain.
- [x] Record exact implementation endpoints in this document and #37. For every
  changed route, specify area/zone identity; old and new endpoint vnums; directions; surface/UD
  grid coordinates and landmark; continent/map section; door/key/terrain
  requirements; reciprocal or intentionally asymmetric behavior; and affected
  authored files. Record the owner's decision source/date and old-link disposition.
- [x] Arcium: owner accepted a separate GC site northwest of Evermeet woodland,
  preserving Homestead and its existing entrance.
- [x] Select and verify a free Arcium site northwest of the active Evermeet
  woodland. Record the map reference used for the relative-position check and
  the exact endpoint vnums/directions. Do not select Homestead's footprint
  `517245` or repurpose its approaches `517246`/`517645`.
- [x] Homestead: explicit owner decision received to retain current placement
  and connections.
- [x] Turolopolis: owner accepted the entire area as it is; retain current
  placement, external entrance, ruins/Zoo connection, and other content unchanged.
- [x] Misty Chasm: owner accepted the recommended area and two-way connection,
  retaining its current surface entrance.
- [x] Select and verify both Misty connector endpoints, including how an
  ordinary player reaches and leaves them. Prefer existing rooms and an
  ordinary reciprocal passage. Add the minimum connector rooms only if the
  agreed geography needs them, using verified unused vnums within valid zone
  bounds rather than renumbering existing rooms.
- [x] Outcasts Tower: owner delegated site selection; chose footprint 546461
  and southern approach 546861, retaining the secondary Underworld route.
- [x] Verify the selected tower site and the impact of retaining its secondary
  Underworld route in the booted development world.

**Implementation prerequisite:** select and validate the exact endpoints before
editing each approved route. The owner decisions above supply the intended
behavior; technical room selection does not need another design discussion.
Keep #37 open until Arcium, Misty Chasm, and Outcasts Tower are implemented and
verified, with Homestead and Turolopolis recorded as accepted without changes.

### 2. Edit the authored connections as complete route changes

- [x] Change Arcium's entrance and both surface counterparts together. Change
  Outcasts Tower's surface pair together, preserving its secondary connection
  unless the recorded decision explicitly changes it.
- [x] For each vacated entrance, inspect the map cell that the old entrance
  displaced and its neighbors. Restore the intended terrain, description, and
  ordinary map connections; remove all superseded entrances and unintended
  one-way remnants. Do not blindly restore numerical grid neighbors: existing
  placeholder cells can have sector 0 and misleading names, such as the old
  cells beside Arcium and Outcasts Tower.
- [x] At each new site, check existing exits, terrain, area occupancy, and
  neighboring travel first. Change only the approach edges needed for the
  approved footprint; do not overwrite another area's entrance. Make entrance
  descriptions and relevant map labels agree with the final routes.
- [x] Keep Homestead and Turolopolis/Zoo unchanged, including their surface
  approaches, the Zoo link, the transit-room exits, and resets/quests. Record
  the accepted no-change outcomes without editing their authored content.
- [x] Add the agreed Misty connector in both directions. Preserve its existing
  surface entrance and internal progression. If a door, switch, or connector
  room is required, update only the necessary corresponding authored reset,
  object, or trigger data; verify accessibility after reset. Avoid new native
  procs where an ordinary authored exit solves the request.
- [x] Review every incoming/outgoing reference to the changed endpoint rooms,
  including teleport/proc references actually found during step 1. Preserve zone
  IDs and existing room IDs. Change zone bounds or `AREA` only if an agreed new
  connector cannot fit the existing active area, with explicit overlap checks.

### 3. Prove the source and generated-world contracts

- [x] Add a focused `tests/async/test_issue37_zone_routes.py` regression using
  the approved route decisions as expected results. Read active authored data
  rather than relying on pre-existing `areas/world.*` outputs. Check endpoint
  existence and zone ownership, expected directions/reciprocity, removal of
  superseded entrances, preservation of named secondary routes, and any new
  connector vnum uniqueness. Do not impose universal reciprocity on unrelated
  intentional one-way exits or build a general connectivity framework.
- [x] Run the focused regression against the old data where applicable to
  demonstrate it catches the requested relocation/missing connector, then run
  it on the changed data. Also demonstrate that breaking one required return
  edge fails the check, using a disposable test fixture.
- [x] Run `make world` in development. Verify the generated room records for
  all changed endpoints and their reverse exits, and inspect generator output
  for missing/ambiguous area files. Generated output is verification material,
  not committed source.
- [x] Build the development server with `make -C src`. If C/C++ changes prove
  necessary, also run `./scripts/format.sh --check` and the smallest applicable
  executable regression; explain the concrete need before expanding scope.
- [x] Run `python3 tests/async/test_flatfile_full_world_boot.py` to exercise a
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

- [x] Walk from the surrounding surface map into each relocated area and back
  through every intended entrance. Check the old sites no longer enter the
  moved area and that their surrounding map routes remain usable.
- [x] Verify Arcium's final approach is GC and northwest of the chosen Evermeet
  landmark, and the tower's approach is GC and south of the chosen Kimordril
  landmark. Record actual vnums, grid coordinates, map views, and the loaded
  continent evidence; compare coordinates in one stated coordinate system.
- [x] Walk Misty's surface approach, internal path to the new connector,
  connector into the Underdark, and return path. Test under the intended player
  movement/vision requirements without staff bypass; inspect falls, water,
  secret/blocked doors, and resets on the chosen route.
- [x] Recheck the tower's retained `11348 <-> 30172` route and confirm the
  unchanged Homestead and Turolopolis/Zoo entrances remain intact. Check relevant
  existing quest/reset progression rather than assuming unchanged IDs suffice.
- [x] Repeat affected `zcheck` reports after a zone reset and a clean restart.
  Compare with the pre-change baseline, investigate new dangling exits,
  unintended one-way traps, or inaccessible required endpoints, and distinguish
  existing unrelated findings. Inspect loaded endpoints explicitly because
  `renum_world()` can remove invalid authored exits during boot.

### 5. Review and close out the implementation

- [x] Reread the diff and remove unrelated changes. Expected content files are
  `arcium.wld`, `mist_chasm.wld`, `otower.wld`, `surface.wld`, the selected UD
  endpoint's authored file, and only required companion `.zon`/`.obj`/`.trg`
  files. Homestead, the ruins, and the Zoo are excluded from content edits. Keep
  engine files unchanged unless a demonstrated blocker requires a narrow fix.
- [x] Run `git diff --check`, the focused route regression, and any required
  checks invalidated by the final edits. Inspect staged paths for generated
  areas, binaries, credentials, logs, or account/player data before committing.
- [x] Update this plan and #37 with a per-request outcome: exact old/new routes,
  the two blank-destination decisions, test commands/results, runtime evidence,
  and remaining blockers. Do not close #37 while an item is merely pending a
  destination, while a required walk is unperformed, or because #65 landed.
- [x] Publish the implementation for review under the repository's normal
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
