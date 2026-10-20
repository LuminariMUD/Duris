# Builder list commands: zone defaults, bounded output, and working olist

Status: implementation and local acceptance complete, 2026-10-20.
The PR stack is ready for review; merge and production deployment are separate.
Tracking: [issue #231](https://github.com/LuminariMUD/Duris/issues/231).
Work branch: [`branch/issue-231-builder-lists`](https://github.com/LuminariMUD/Duris/tree/branch/issue-231-builder-lists),
linked through the issue's Development section.
Branch base: [master `2129ec429f20`](https://github.com/LuminariMUD/Duris/commit/2129ec429f20c6ad59ce883ffabda2b57585992e).
Source baseline: [master `4eca0ea95245`](https://github.com/LuminariMUD/Duris/commit/4eca0ea95245dbcaf7cb8b5d2dd565323d9fd3fa).
The inspected command, index-loading, and paging files are unchanged between the
source baseline and branch base. The existing `plan.md` belongs to issue #169 and
is outside this change.

## Current execution / continuation

Review order:

1. [PR #232](https://github.com/LuminariMUD/Duris/pull/232): loader names and
   OpenSpec contract, `branch/issue-231-builder-lists`, code commit `c69506ea7`.
2. [PR #233](https://github.com/LuminariMUD/Duris/pull/233): commands, regressions
   and acceptance evidence, `branch/issue-231-builder-list-commands`, targeting
   the loader branch. Initial command commit `fae9f2c83`; runtime output repairs
   in `dfdf98b75`. The final continuation document is on this child branch.

OpenSpec change: `openspec/changes/issue-231-builder-lists/` (spec-driven).
All implementation/acceptance tasks are complete. Keep the change active until
review and merge. No release tag is appropriate for unmerged review work.
No deployment or production acceptance is included.

Ablation retained existing `desc2` ownership, normal loaders, sorted indices,
zone bounds, ANSI formatting and paging. No duplicate template cache, index
fields, service, configuration, database change or general pager/parser rewrite
was needed. Each shared helper has all three commands as callers; the prototype
renderer serves both mobile and object lists. Final diff review found no other
necessary pruning.

Implemented:

- Index generation reads shared short descriptions at boot, preserves record
  positions, excludes the payload-free sentinel and handles empty/EOF files.
  Normal, mini and material-rarity callers use the same unchanged interface.
- The handlers use checked syntax/public zone numbers and bounded lower-bound
  traversal. Mobile/object listing reads indices directly, without spawning,
  extracting, file/DB I/O, or event/procedure calls. Names are bounded and
  flattened; invalid sectors are safe. Room rows fit an 80-column terminal.
- Actual scope/count/empty/truncation output and continuation are implemented.
  Runtime checking repaired the inherited invalid paging advice: the actual
  recovery command is `toggle paging`.

Focused executable proof:

- `test_builder_list_commands.py` runs real handlers, parsing and ANSI helpers
  under ASan/UBSan and in an optimized build. It covers all syntax, public identity,
  missing location, empty tables, first/last/max VNUM, all planned result counts,
  names/sectors, access and paging errors, and continuation. A zone surrounded
  by 20,000 unrelated entries on each side takes logarithmic comparisons and at
  most 501 matching probes. Entity lists, staff/event state, rooms and index
  populations remain unchanged; entity loaders and file access fail the harness.
- `test_newbie_object_template.py` executes real generation, ordinary object
  parsing/publication and cleanup for cold names, sentinel/EOF and empty text.
  It proves original positions and shared pointer reuse under ASan/UBSan.
  Native full-world boot additionally exercises ordinary mobile and object loading.
- Actual full/mini mobile and object indices are strictly increasing. Full-world
  rooms are nondecreasing, with one existing adjacent VNUM overlap at 51800 in
  `hell_two_dis.wld` / `hell_three_minauros.wld`. Lower-bound lookup includes both
  records; an executable duplicate-room case also passes. Content is unchanged.

Local/dev gameplay acceptance:

- Environment was verified local (`duris_dev` on loopback). A disposable MariaDB
  container cloned that DB, with isolated runtime/ports/journals and Redis off.
  The first exact clone failed closed on existing incompatible saved shop 543
  (mob 101, room 132767). The acceptance fixture retained the configured staff
  account but cleared copied persisted item/stock tables in its disposable DB.
  Original DB, account/player files and the existing dev server were untouched.
- Configured staff Veridian exercised all commands at room 55612 (public zone
  550, internal index 210) and room 1402 (public zone 14). Winterhaven returned
  500 of 599 rooms, then 99 with `rlist zone 550 55544 2147483647`; mobiles 314,
  objects 483. The second zone returned rooms/mobiles/objects 147/58/66.
- Each broad `0 2147483647` search returned exactly 500 entries and continuation;
  `2147483647` returned no matches. Paging completed and cancelled correctly,
  help worked with paging off, recovery advice worked, and no generic pager
  overflow warning appeared. The real interpreter denied all three commands to
  a synthetic mortal on creation and subsequent character re-entry.
- During 18 repeated broad listings (six each), a second client completed 36
  `look` requests: min/median/max 244.53/250.19/255.69 ms, consistent with the
  normal four-pulse-per-second loop. Existing latency trace windows recorded
  command-sweep maxima up to 5.721 ms and whole-tick maxima up to 35.885 ms.
  Those sweep timings include other commands and pager input, not just handlers.
- Existing production profile timers around 50 optimized fixture handler calls
  measured min/average/max 81/85/126 us (`rlist`), 67/67/76 us (`mlist`), and
  67/103/248 us (`olist`) in the final focused run. These capture output in memory
  and exclude network rendering. No safe equivalent pre-change gameplay baseline
  was taken, so no speedup or production-latency claim is made.
- Actual unloaded mobile/object VNUM 1 rows stayed identical across five repeats
  each. Live corpses expired normally; global population stability is not claimed.
  Strong no-mutation/entity/event proof comes from the deterministic harness.
- Full-world and mini boots reached the game loop (reported boot stages 1,876 ms
  and 15 ms). Both isolated servers shut down normally; their containers were
  removed. These were native development builds with assigned special routines
  suppressed (`-s`), not a full-server sanitizer burn-in.

Boot cost was measured separately with old/new production generators on the same
files: full mobs 17,680 records, 22.37/16.14 ms, 488,202 added name bytes; full
objects 19,149 records, 23.94/21.62 ms, 670,174 bytes; mini mobs 171 records,
0.097/0.114 ms, 4,166 bytes; mini objects 801 records, 4.14/0.571 ms, 24,047 bytes.
Single-run timings are warm-cache-sensitive and do not establish a speedup.
Added full-world string payload is 1,158,376 bytes plus allocator overhead, shared
with later instances.

Final checks (all passed):

```sh
python3 tests/async/test_builder_list_commands.py
python3 tests/async/test_newbie_object_template.py
python3 tests/async/test_minimal_boot.py
python3 tests/async/test_documentation_contract.py  # 14 checks
./scripts/format.sh --check
make -C src -j4
node /home/aiwithapex/.nvm/versions/node/v24.15.0/lib/node_modules/@fission-ai/openspec/bin/openspec.js validate issue-231-builder-lists --strict
git diff --check
```

Local evidence is under `bin/tests/builder-list-runtime-3/` (`scope-acceptance.json`,
`acceptance.json`, acceptance transcripts, server logs and latency trace),
`bin/tests/builder-list-runtime-4-mini/`, and `bin/tests/builder-boot-cost`.
The acceptance server binary SHA256 is
`b5ffa39dd2e3889f0da390fb6891fadcdf90a0ffdf1c3c2589fd7bbbabf9008d`;
its tracked source matches `dfdf98b75` (later changes are tests/documentation).
No credentials, generated worlds or compiled artifacts are committed.

Continuation: no implementation work remains. Review/merge #232 before #233,
refresh moving master and validate the eventual merge tree, then archive OpenSpec.
At closeout master had advanced to `0701b0e29` (who behavior and locker docs);
`git merge-tree --write-tree HEAD origin/master` merged cleanly. The branches were
not rewritten, and the combined master tree was not built or gameplay-tested.
Do not equate these local acceptance results with deployment. The reported
production slowdown remains unmeasured; CI is not a prerequisite for this closeout.

## Outcome and scope

Make `rlist`, `mlist`, and `olist` useful, bounded staff inspection commands:
default to the standing zone, display at most **500 entries**, preserve explicit
VNUM searches, and avoid gameplay mutations or file/database reads while listing.
Implement the currently empty object listing and repair the directly related
input, identity, count, and bounds defects below.

Non-goals: changes to `zlist`, `hlist`, `zcheck`, `which race`, the global pager,
world content, reset rules, permissions, persistence, or production operations.
No new listing service, configuration option, background worker, or general
prototype framework is needed.

## Source findings

Historical pre-change findings, verified by source inspection; these are not claims
of a live reproduction:

1. [`do_rlist` and `do_mlist`](../../src/cmd/actinf.c#L10195) leave their filters
   disabled for empty input and iterate every room/mobile index. Neither has a
   result limit. The existing paging requirement does not bound their work:
   [`send_to_char`](../../src/net/comm.c#L4726) eventually stops buffering excess
   text, but the command's loop continues.
2. [`do_olist`](../../src/cmd/actinf.c#L10329) is an empty function. All three
   handlers are already [registered as IMMORTAL commands](../../src/cmd/interp.c#L3459);
   object listing needs an implementation, not a new command registration.
3. `mlist` calls [`read_mobile`](../../src/world/db.c#L1960) and `extract_char`
   for each row. Loading seeks/parses the mob file, allocates/registers a live
   mobile, increments its population, and can schedule events/invoke special
   procedures. The displayed `Num` is read before extraction, so includes the
   temporary mobile. A listing should use the index's real population directly.
4. `rlist zone <n>` compares `n` directly to `room.zone`, an internal table index;
   its Zone column also exposes that index. `zlist` displays `zone_table[].number`.
   [`zone_data` and `index_data`](../../src/core/structs.h#L654) distinguish these
   identities; a mob/object index has no zone field.
5. Both parsers use unchecked `atoi` after [`is_number`](../../src/cmd/interp.c#L2591),
   which even accepts a lone `-`. Overflow is unchecked. `mlist` casts a possibly
   empty index's `top_of_mobt == -1` to `size_t`, turning its loop bound enormous.
   Mobile headers and paging errors say "Rooms"/"Room List"; room headers report
   the whole-world count even for filtered results. Neither reports no matches.
6. `rlist` indexes `sector_types[room.sector_type]` before its null check.
   Out-of-range sectors must be checked against `NUM_SECT_TYPES` before access.
   This unsafe access is visible in source; no corrupt live sector was established.
7. Simply replacing `read_mobile` with `mob_index[i].desc2` is incomplete:
   [`generate_indices`](../../src/world/db.c#L1037) initializes names to null and
   normal loading fills them lazily. Unloaded prototypes still need real names.
   The existing [object-template cache](../../src/world/object_template.h) is
   deliberately selective and boot-only; it is not an all-prototype name catalog
   and must not acquire command-time file-read fallbacks.

The user's whole-MUD slowdown remains an unmeasured live symptom. The unbounded
loops and mobile instantiation explain plausible cost, but no timings or production
diagnosis are claimed. No game commands, builds, or migrations ran in this investigation.

## Behavior contract

Apply the following syntax to all three commands, keeping the existing single-VNUM
shorthand and reversed-range normalization:

```text
<command>                              current zone
<command> ? | help                     usage
<command> <vnum>                        exact prototype/room, any zone
<command> <from> <to>                   inclusive VNUM range, any zone
<command> zone <zone-number>            explicit zone
<command> zone <zone-number> <vnum>      zone intersected with one VNUM
<command> zone <zone-number> <from> <to> zone intersected with a range
```

- Resolve the default through `world[ch->in_room].zone` after validating the room
  and zone indices. Missing/invalid current location must not fall back to the
  world. Explicit VNUM searches do not need a current room.
- `zone-number` means the public number shown by `zlist`; use `real_zone` after
  checking that the zone table is nonempty. Do not silently interpret a failed
  public lookup as a table index. This intentionally corrects the old `rlist`
  meaning; explain it in usage and test a public number that differs from its index.
- Room ownership uses `world[r].zone` and the zone's `real_bottom`/`real_top`.
  For mobile/object prototypes, define zone membership by the numeric partition
  used by [`boot_world`](../../src/world/db.c#L1248):
  `0..zone_table[0].top`, then `(previous zone.top)..current zone.top`.
  This is prototype VNUM ownership, not current instance location or membership
  in reset commands. It includes unloaded prototypes and zones spanning more than
  100 VNUMs; do not infer ownership with `vnum / 100`. Document this in usage.
- Accept complete nonnegative decimal values representable as `int`; reject
  malformed tokens, signs, overflow, missing operands, unknown zones, and trailing
  arguments with a useful error/usage message before listing.
- Keep NPC rejection and existing IMMORTAL registration. Keep paging required
  for results, but make `?`/`help` usable with paging off. Errors must identify
  the actual command. Use the existing paged `send_to_char` path.
- Render at most **500 result entries**, excluding headers/footer. Probe at most
  one additional matching entry to distinguish exactly 500 from truncation,
  without rendering or instantiating it. Stop there; do not count all remaining
  matches. Display the selected scope and actual number shown. Say "No matching
  rooms/mobiles/objects" when empty.
- On truncation, say more matches exist and give a valid next VNUM range,
  preserving any zone filter and the original inclusive upper bound. No continuation
  token, saved search, or new pagination subsystem is needed. Avoid overflow at
  the maximum VNUM.
- Keep compact, ANSI-aware, single-row output with bounded names; prevent embedded
  line breaks in names from producing extra rows. Room columns:
  public Zone, VNUM, Name, Sector. Mobile and object columns: VNUM, Name,
  current population, reset limit. The index's `limit` is the existing reset
  limit, not a claim about all possible runtime population policies.

## Implementation steps

1. **Make short descriptions available before commands run.**
   In `generate_indices`, populate the existing shared `desc2` field for real
   mobile/object records during boot using the existing tilde-string readers.
   Read only the necessary string fields, retain the original record `pos`, and
   handle the `#9999999` terminator, EOF-terminated files, and empty descriptions.
   Reuse these strings through normal instantiation and existing cleanup; add no
   duplicate full-template cache or new `index_data` fields. Verify the
   `boot_material_rarity_objects` caller as well as normal/mini boot.
2. **Repair the three handlers together.**
   Keep rendering in `src/cmd/actinf.c`, with one local result-limit constant.
   Share only parsing/scope logic actually used by these three handlers, following
   the nearby checked `strtol` pattern instead of changing global `is_number`.
   Apply the contract above, implement `olist`, remove `mlist` entity loading,
   fix counts/labels, and guard the sector lookup. Use a clear placeholder only
   when the source description itself is empty, not for a never-loaded prototype.
3. **Bound traversal as well as output.**
   Use zone room bounds for room defaults and sorted VNUM lower-bound searches
   for explicit ranges and prototype indices. Intersect bounds before rendering,
   stop above the upper bound, and stop after the 501st matching candidate.
   Empty tables must return before pointer arithmetic or unsigned conversions.
   Check the sorted-index prerequisite against generated data; do not add a
   second index or a full-world count pass. The normal listing path should cost
   `O(log N + min(matches, 501))`, plus at most 500 bounded row renders.
4. **Prove behavior and record runtime acceptance.**
   Add focused executable command/index tests, then run the local/dev journey
   below. Record evidence in this plan and the issue. Keep implementation,
   local acceptance, publication, and any later production deployment distinct.

Expected implementation files: `src/cmd/actinf.c`, `src/world/db.c`, a focused
`tests/async/test_builder_list_commands.py`, and extensions to existing relevant
loader tests where suitable. Update in-command usage and
`docs/testing/REGRESSIONS.md`. A new shared module/header or database change is
not expected. Do not modify generated `areas/world.*` files.

## Verification and acceptance gates

Use the existing executable-harness approach in
[`test_staff_title.py`](../../tests/async/test_staff_title.py) and the real
parser/loader fixtures in
[`test_newbie_object_template.py`](../../tests/async/test_newbie_object_template.py).
Execute production function bodies, not a second implementation of the algorithm.

- **Scope and syntax:** two zones whose public numbers differ from their indices;
  all three bare commands, whitespace-only input, explicit zones, exact VNUMs,
  forward/reversed ranges, zone/range intersections, range gaps, first/last zone,
  multi-hundred-VNUM zones, missing location, unknown zone, and invalid/overflowing
  input. Include an unloaded prototype and a prototype used by a different zone's
  resets to prove the documented ownership rule.
- **Boundaries:** 0, 1, 199, 499, 500, and 501+ matches in each command; empty tables
  with top index `-1`; table first/last entries; and maximum accepted VNUM.
  Assert the displayed count, at-most-500 rows, truthful truncation, and usable
  continuation advice. A large unrelated prefix/suffix must not trigger a
  world traversal or a hidden count pass.
- **Read-only behavior:** fail the command harness if it calls mobile/object
  creation, extraction, file/DB access, events, or special procedures. Verify
  population counters and entity lists are unchanged and displayed counts equal
  fixture counts. Cover names before any prototype has been instantiated.
- **Boot compatibility:** execute real index generation and subsequent ordinary
  mobile/object loading with fixtures; prove shared names and file positions stay
  correct, sentinel records are not parsed as prototypes, EOF/empty text works,
  and cleanup is safe under ASan/UBSan. Measure added boot memory/time separately
  from command execution.
- **Output and access:** check `?`/`help` with paging off, command-specific paging
  errors, NPC/mortal restrictions through registration plus the runtime journey,
  long/colorized/multiline names, empty descriptions, and invalid sector values. Ensure
  500 rows plus footer fit the existing pager without its generic overflow warning.

After implementation, run:

```sh
python3 tests/async/test_builder_list_commands.py  # planned new executable regression
python3 tests/async/test_newbie_object_template.py
./scripts/format.sh --check
make -C src
python3 tests/async/test_documentation_contract.py
git diff --check
```

Then use the configured staff test character on a verified local/dev environment:
exercise all three commands in two zones, an empty result, a broad explicit range,
and paging completion/cancel. Verify `olist` is reachable and all visible counts,
scope, and continuation messages match the fixtures/world. Check a mortal cannot
invoke them. Capture handler timings and concurrent-client responsiveness during
repeated bounded listings, using existing instrumentation; compare under the same
conditions if a safe isolated pre-change measurement is available. Verify no
entity/population/event changes attributable to listing. Do not run the old
unbounded commands on production to obtain a baseline.

Completion requires focused regressions, build/format checks, and the local/dev
journey to pass, with measured performance evidence and any remaining uncertainty
stated explicitly. CI is not an acceptance prerequisite. Production deployment
is a separate authorized operation.

## Original planning record

The initial estimate was 4-8 active engineering hours, including cold-name boot
and runtime coverage. Planning commit `2ba175d38` added only this document and
passed all 14 documentation checks. The execution record above supersedes its
original implementation/runtime-pending status.
