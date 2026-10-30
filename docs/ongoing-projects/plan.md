# Issue #418: recoverable Quintaragon Castle resets

Status: **implemented; local qualification complete; ready for review**.
Updated 2026-10-30.
Issue: [Duris #418](https://github.com/LuminariMUD/Duris/issues/418).
Branch: [branch/issue-418-plan](https://github.com/LuminariMUD/Duris/tree/branch/issue-418-plan),
linked in issue #418's Development section.
Baseline: `origin/master` at `b23ea8c65a467d17683ccd5de91f66b362209d06`.
Worktree: `/home/aiwithapex/projects/duris-issue-418-plan`.

The preceding starter-arrow plan and qualification record are preserved byte-for-byte
in [plan-issue-428.md](plan-issue-428.md). The owner's follow-up authorizes
implementation, planned tests and gameplay qualification, commit/push and a PR.
Merge and production deployment remain separate work.

PR: [#476](https://github.com/LuminariMUD/Duris/pull/476). During publication,
`master` advanced to `bc1537d9eb996db126ab20835201909baa91349c`; its completed
bartender-quest plan is preserved byte-for-byte in
[plan-issue-437.md](plan-issue-437.md). The integration changes no castle source
or authored area data beyond the implementation documented here.

## Outcome

Choose an availability-based reset policy for Quintaragon Castle: its seven
consumable-key gates may reset locked only when their authored source can actually
supply the key. A reset must leave a connected or linkdead player body a physical
way out without another key, a lockpicking skill, a spell, or staff intervention.

Preserve consumption, ordinary carrier respawns, object and mobile limits, loot,
and mode-1 timer admission. A surviving carrier may remain keyless; access must
then cease to depend on that carrier. The issue requests a consistent
key/relocking policy, rather than mandating a new restocking mechanism.

## Current source findings

The issue is a hypothesis and acceptance specification, not runtime evidence for
this checkout. Its linked source baseline is older. The three authored castle
files have no diff between that baseline and this plan's baseline; the engine
paths below were read again on this checkout.

- `areas/AREA:12` selects `castle`; `areas/zon/castle.zon:1` identifies zone
  number **24**, with top room 2532, mode **1**, and lifespan range **5-10**.
  These are zone-age ticks, not a promise of 5-10 real minutes. The scheduler
  uses `PULSES_IN_TICK=300` and `WAIT_SEC=4`; configuration can also scale lifespan.
- `areas/obj/castle.obj` gives keys **2405, 2418, 2422, 2425, 2436, 2437,
  2438** a break chance of **100**. Entrance key **2402** has **0**; container
  key **2434** has **10**. Key 2434 belongs to a bookcase, not one of these gates.
- `src/cmd/actmove.c::do_unlock()` consumes a breaking key through `break_key()`
  and unlocks the matching reverse exit. `src/world/handler.c::extract_obj()`
  decrements the live prototype count. There is no permanent used-key counter
  in these paths. Making future keys durable would not by itself establish the
  behavior of existing instances or fix every lock-in.
- `src/world/db.c::reset_zone()`, around lines 3399-3410 and 3613-3680,
  rejects an ordinary `M` load at the live mobile limit, clears mobile context,
  and skips its conditional `E`/`G` rows. The current shopkeeper-specific
  admission rules do not restock these castle carriers.
- The `G` and `E` cases around lines 3807 and 3884 apply the live object limit
  before attaching an object to the newly loaded mobile. All seven key rows
  have limit **1** and chance **100**. A key held elsewhere can suppress the
  new carrier's key; consuming it later does not rerun the surviving carrier's
  conditional rows. Conversely, absent carrier plus absent key permits normal
  loading. The mechanism still supports the issue's reported sequence.
- The `D` case around line 4079 sets lock/closed state without checking key
  availability. Castle's door rows run **before** its mobile/item rows. A key
  availability decision made there would observe the wrong phase of the reset.
- `src/world/events.c::event_reset_zone()` calls `reset_zone(zone, 0)` when
  the zone is old enough and mode 2 or `is_empty()` permits it.
  `src/world/db.c::is_empty()` scans playing descriptors, not all player bodies.
  A connected player blocks the castle's ordinary timer reset; a descriptorless
  linkdead body does not. `src/cmd/actwiz.c::do_zreset()` bypasses this timer gate
  for `zreset ok` and purges then resets for `zreset full`.
- `src/cmd/actmove.c::find_door()` refuses hidden/blocked exits even if their
  lock bit is clear. The **2436** pair resets to state **6**, so merely unlocking
  it leaves a secret-exit obstruction. `setup_dir()` masks authored door type
  with `& 3`; the `7` in its room records means pickproof plus an ignored high
  bit at load, while the `D` rows establish runtime secrecy.
- An independent traversal of all authored castle exits found **5760**, reached
  south from **2401**, as its external physical destination. Relaxing only the
  seven consumable-key gates leaves no static exit route from their interior
  endpoints: the **2402 south <-> 2401 north** entrance still resets locked.
  Relaxing that pair as well yields routes from all seven interior endpoints.
  This over-approximates traversability: it permits every nonlocked physical
  exit and does not prove terrain, combat, or movement requirements. Real mortal
  command journeys must supply the missing gameplay proof.
- `has_key()` checks inventory and **HOLD only**. It cannot establish whether
  Glynn carries key **2437**, which is equipped in slot **4**. Source availability
  must inspect the carrier's direct inventory and all equipment slots.
- `src/world/new_events.c` uses reset argument **2** for a normal cold
  boot and skips initial reset during copyover/Redis world recovery.
  `src/world/world_recovery_pipeline.c` restores door flags. No new persistent
  state is needed, and this reset fix must not claim to rewrite an old recovery
  snapshot immediately on restore.

The reporter's actual live counts, key location, connection state, reset type,
and deployed revision remain unknown. No production reproduction is claimed.

## Exact gates and sources

Each line names the key, authored carrier/home, loading row, and both gate sides.
Directions are the runtime directions, not the key's prose description.

- **2405**: Juku, mobile **2406**, room **2427**, `E` slot **18**, zone row
  **263**; **2414 down <-> 2415 up**.
- **2418**: Giauque, mobile **2415**, room **2439**, `G`, zone row **289**;
  **2427 up <-> 2428 down**.
- **2422**: large rat, mobile **2418**, room **2452**, `G`, zone row **332**;
  **2446 west <-> 2448 east**.
- **2425**: Cetyla, mobile **2419**, room **2456**, `E` slot **18**, zone row
  **335**; **2460 up <-> 2461 down**.
- **2436**: Povtail, mobile **2433**, room **2481**, `G`, zone row **360**;
  **2471 north <-> 2479 south**, both reset secret as well as locked.
- **2437**: Glynn, mobile **2420**, room **2477**, `E` slot **4**, zone row
  **352**; **2480 north <-> 2488 south**.
- **2438**: Gilman, mobile **2428**, room **2493**, `E` slot **18**, zone row
  **390**; **2480 south <-> 2498 north**.
- Recovery boundary: durable entrance key **2402**, Tev **2401** in room
  **2401**; **2401 north <-> 2402 south**. Include this pair in occupied-zone
  escape handling, without changing its ordinary empty-zone reset policy.

## Selected policy and ablation

Run one castle-specific access correction at the **end of the existing reset
command loop**, after all `M`/`E`/`G` and `D` commands have finished:

1. Scope by `zone_table[zone].number == 24`, never by array index. Use the small
   explicit gate/source mapping above. Resolve VNUMs through existing lookups;
   verify matching reverse exits and keys before touching either side. Do not
   introduce a zone flag, reset opcode, config property, or reusable policy engine.
2. Determine whether any player body is currently in the zone using
   the live character list and a valid room. Include linkdead players, staff and
   morphed players (whose active body is represented as an NPC);
   do not use descriptor presence or change global `is_empty()` semantics.
3. If a player body remains, clear `EX_LOCKED` and `EX_SECRET` on both sides
   of all seven gates **and the entrance pair**. Leave their normal reset-closed
   state, door type and pickproof flags intact. These mapped exits are not
   blocked; this is not a general blocked-exit override. After reconnect, normal
   `open` and movement must suffice to follow the escape route.
4. Otherwise, for each of the seven keys, leave the ordinary reset state only
   if the authored carrier is alive in its authored room with that exact key
   in direct inventory or any equipment slot. If that source cannot supply the
   key, clear lock and secret bits on both gate sides. A global live count, a
   player's key, a corpse/container copy, or a carrier moved elsewhere does not
   establish an accessible authored source. Do not spawn, move, retire, or
   duplicate any object or mobile to satisfy this check.
5. Apply the correction to ordinary and explicit staff resets alike. A clean
   cold boot with all sources successfully loaded retains the normal locked
   progression. Existing forced-load behavior is not extended by this fix.
   Repeated resets are idempotent. Once the zone is empty and the source again
   has its key, the existing `D` rows may restore normal locked/secret state.

This deliberately prioritizes access when a key source is unavailable. Another
party may traverse an affected gate without obtaining a replacement key after
such a reset. An occupied staff reset also makes the mapped entrance/gates
available. These are explicit gameplay consequences, not claims of unchanged
progression. Fresh, empty resets with stocked sources still require the keys.
NPCs, hazards, and normal movement requirements remain in effect.

**Keep:** the scoped correction, all seven pairs, occupied-zone handling,
secret-bit clearing, the entrance recovery boundary, and executable proof.
Removing any of them leaves a traced acceptance failure.

**Simplify:** repair the lock/access contract after reset rather than trying to
teach `M`/`E`/`G` to re-equip surviving mobs. Reuse current loading and limits;
no area-row reordering or new runtime state is required.

**Drop:** global force-loading, unlimited key copies, changing all key break
chances, general survivor restocking, new escape items/exits, global linkdead
reset vetoes, persistence migrations, and a pathfinding service. Existing
`ITEM_SWITCH` opens blocked exits, not these locks; adding switches would also
require new behavior and area objects. These alternatives add work without
being necessary for the chosen outcome.

## Non-goals

Do not repair every consumable key in the world, change unrelated zones or
ordinary loot limits, change the bookcase key, redesign key custody, change
timer cadence, or implement adjacent issue #419. No retroactive inventory
migration, new persistent state, blanket lock bypass, or production operation
is part of this scope. Combat safety and freedom from all terrain/spell hazards
are not promised; the recovery guarantee concerns reset-created door obstruction.

## Files and implementation sequence

1. **Capture failing behavior.** Add one focused native regression, provisionally
   `tests/async/test_castle_key_reset.py` with a small companion C++ harness.
   Follow the production-code extraction/build pattern in
   `test_shopkeeper_population.py`; execute the actual reset loop and relevant
   cases, not a Python restatement. Use current castle data as fixture input.
   Compile into `bin/tests/` with ASan/UBSan. Establish the old E and G failures
   and negative controls before the production change.
2. **Implement the policy in `src/world/db.c`.** Keep the mapping and private
   correction next to `reset_zone()`, and call it once after the loop. Make no
   changes to the M/E/G limit/admission logic, key consumption, the scheduler,
   `is_empty()`, or authored castle content. Recheck the mapping against area
   inputs in the regression so future data edits cannot silently drift.
3. **Prove command-level recovery.** Add a focused disposable journey,
   provisionally `tests/async/test_castle_key_reset_journey.py`, reusing
   `test_flatfile_combat_journey.py`'s server-build, private runtime, port and
   socket helpers. Load the authored castle room graph, relevant mobs/objects
   and reset rows, plus the exterior landing room; do not replace the graph
   with an artificial two-room shortcut. Use synthetic accounts and ordinary
   mortal commands for consumption, reconnect, open and movement. Staff fixture
   setup may arrange state, but staff bypasses cannot serve as recovery proof.
4. **Document and qualify.** Record actual commands/results and the chosen
   gameplay tradeoff here; include a concise operator explanation in
   `docs/operations/RUNBOOK.md`. Read the final diff, format changed C/C++ lines,
   run the focused checks and required build, then prepare the implementation
   commit for normal review. No merge or deployment is part of this plan task.

Production scope is one existing C++ translation unit. Tests and the existing
runbook/plan are supporting changes. `actmove.c`, `handler.c`, `events.c`, castle
area files and recovery code are exercised dependencies, not planned edits.
If the mortal journey exposes a real movement obstruction on the proposed
route, resolve that specific requirement and update this plan before declaring
completion; static connectivity alone is insufficient.

## Proof and acceptance

- **Held-key sequence:** for every listed key, start with a player-held key and
  allow its dead carrier to respawn keyless. The new policy already leaves that
  gate unlocked at this first reset; assert this earlier prevention explicitly.
  To exercise the remainder of the historical sequence, let the key holder use
  normal close/lock/unlock commands to consume the key (or seed the native test
  with the pre-fix locked state), leave the carrier alive, then reset again.
  Both sides must be closed, unlocked and visible. Repeat the reset;
  carrier/loot counts must not change. Execute E and G production paths,
  including 2437's non-HOLD slot; do not expect unlocking an already unlocked
  door to consume a key.
- **Reload control:** with no live key and a dead carrier, an ordinary empty
  reset loads the carrier and key under existing limits. Both gate sides retain
  their authored locked state, including the 2436 secret bits. Killing a keyless
  carrier remains a valid route to normal replacement, but is no longer required
  just to make access possible.
- **Availability controls:** player-held, corpse, container and off-site copies
  do not count as a stocked source; the correct carrier with the key at home
  does. Missing/moved carriers and failed item materialization yield accessible
  gates without ordinary-loot duplication. Verify both sides, exact object
  counts/identities, and no unrelated equipment replacement.
- **Connected player:** exercise production `event_reset_zone()` and
  `is_empty()` together with a playing descriptor in zone 24. At expiry, no
  ordinary reset occurs. A playing character in a different zone does not block
  the castle. Testing `reset_zone()` directly is not proof of timer admission.
- **Linkdead and staff reset:** with a player body but no playing descriptor,
  the due timer may reset; all eight recovery pairs must be visible/unlocked.
  Reconnect the same mortal and physically leave from each of the seven interior
  endpoints to **2401**, then **5760**, without a key or magical/staff bypass.
  Include the secret closet explicitly. Run the same access assertions after
  `zreset ok` with a connected mortal; cover full-reset behavior in isolation.
- **Progression restoration:** after the final player leaves, an empty reset
  with stocked sources restores normal locks and closet secrecy. A missing key
  affects its mapped gate only. The entrance's empty-zone behavior remains normal.
- **Isolation:** prove a non-24 zone, unrelated castle doors, bookcase key 2434,
  ordinary equipment, mobile limits and existing shopkeeper special cases retain
  their baseline behavior. Do not redefine existing force-reset loot semantics.
- **Boot/recovery boundary:** verify cold-boot flags with stocked sources and
  rerun the sequence from restored-like live state. Existing door snapshots may
  retain old flags until a qualifying reset; immediate repair of arbitrary old
  snapshots, manually locked doors, and unrelated magical confinement is not
  promised. No new persistence field or save-data rewrite is planned.

Verification commands (the two planned test entry points are now implemented):

```sh
python3 tests/async/test_castle_key_reset.py
python3 tests/async/test_castle_key_reset_journey.py
python3 tests/async/test_key_break_custody_contract.py
python3 tests/async/test_zone_reset_timing_contract.py
python3 tests/async/test_no_reset_zone_key.py
python3 tests/async/test_shopkeeper_population.py
make -C src
./scripts/format.sh --check
python3 tests/async/test_documentation_contract.py
git diff --check
```

Keep binaries and disposable runtime evidence under `bin/`, and verify the test
environment before starting a server. A new worktree does not inherit `.env` or
running services. Use the existing isolated flat-file fixture, not production
accounts/data. No production reset, migration, restart, deployment, full burn-in,
or CI wait is needed for this scope. Report any unavailable runtime check.

## Original planning verification and estimate

Completed on this baseline:

- Read issue #418 and its comments (none), current source, all seven source/gate
  mappings and castle object values. The issue is open, with no project work
  items and no development branch linked before this task.
- Independently parsed all castle exits and key reset rows. Confirmed seven
  reciprocal gate pairs, four E and three G sources, the secret pair, and the
  entrance boundary needed for a static route to room 5760.
- `python3 tests/async/test_key_break_custody_contract.py`: passed.
- `python3 tests/async/test_zone_reset_timing_contract.py`: passed.
- `python3 tests/async/test_no_reset_zone_key.py`: passed.
- `python3 tests/async/test_documentation_contract.py`: all 14 tests passed
  before and after drafting.
- `git diff --check`: passed. The preserved issue #428 plan's SHA-256 matches
  the original tracked file exactly.

These are planning/source checks. The two existing key/timing contracts inspect
source text; they do not execute the reported gameplay sequence. The issue's old
uncommitted C++ probe was not assumed to be present or rerun. No new regression,
full build, socket journey, or production validation has been performed here.

Estimate: **3-5 hours of my active implementation and validation time** from this
plan, including roughly 45-75 minutes for the native regression, 30-45 minutes for
the scoped production change, 60-120 minutes for the real command/reconnect
journey, and 45-60 minutes for build, compatibility checks, documentation and
final review. Allow **up to 6 hours** if the authored castle fixture or safe
movement through its terrain needs additional qualification. This is an estimate,
not a guarantee; it excludes external review, merge scheduling and deployment.

## Implementation and qualification, 2026-10-30

The implementation keeps the planned policy in one private helper and one call
after the reset loop in `src/world/db.c`. The helper resolves the eight exact
gate pairs, examines carrier inventory and every equipment slot, and uses the
live character list to include linkdead occupants. It clears lock/secret bits
only on the mapped reciprocal exits. No source/item creation path, area input,
global emptiness rule, persistence field or migration changed.

The new native test extracts the production reset loop, M/G/E/D cases,
finalization, access correction, `is_empty()` and `event_reset_zone()`. Allocation,
placement, RNG and unrelated services are controlled; it is not a second reset
implementation. Fixture rows and exits come from the authored castle files.
Against the original source, all seven held-key/consumption cases fail at the
locked-door assertion. With the fix, all seven and the availability, occupancy
and boundary groups pass under ASan/UBSan. They cover stable surviving-carrier
identities, normal dead-carrier replacement, repeated resets, all equipment
slots, off-carrier/off-site copies, item creation failure, the outer entrance,
secret closet, unrelated bookcase key, another zone number and mismatched reverse
exits. The existing shopkeeper population regression also passes.

Implementation inspection found one required refinement: `morph()` moves the
original PC to limbo and represents the active player body as an NPC with
`orig_char`. Counting only `!IS_NPC` would miss a linkdead morphed player. The
occupancy check also uses the existing `IS_MORPH()` predicate; a native negative
control fails without it and passes with it. This preserves the player-body
recovery requirement without changing morph or global reset behavior.

The socket journey uses the real server with private flat-file authority, seven
new mortal accounts and one staff setup account. It loads the authored castle
room graph, key prototypes and relevant reset rows, with an exterior landing
room at 5760. Only the fixture's reset lifespan (one real timer tick), NPC
aggression/wandering and unrelated spawns are controlled. The real callback
still runs every 300 pulses; the test does not call it through a debug shortcut.

Staff removal drops NPC equipment/inventory on the floor, so the fixture takes
each original key after removing its carrier rather than creating a second copy.
Live object inspection confirms exactly one key of each VNUM, carried by the
mortal. The next empty timer reset creates keyless carriers. Real mortal
close/lock/unlock commands consume all seven keys, reducing each live count to
zero; another empty timer reset preserves the same carrier IDs and keeps both
sides of every gate accessible. Removing the keyless carriers permits normal
replacement and restores the authored locks, including the secret closet.

With seven connected mortals placed at the interior endpoints, the due timer
reports `will_reset=0` and leaves the locks intact. After their sockets close,
the same scheduler reports `will_reset=1`; all eight recovery pairs become
unlocked and visible. Each mortal reconnects and walks to 5760 using only normal
open/movement commands. Staff readback verifies the room after every movement:
**14, 13, 17, 21, 32, 34 and 34 steps**, respectively, **165 steps total**.
The closet is included. Separate connected-mortal journeys pass after both
`zreset ok` (basement) and `zreset full` (closet). The final empty, stocked timer
reset restores normal locks and secrecy. All six observed timer cases have zero
callback lateness. The disposable server exits successfully and is removed.

Completed commands/results:

- `python3 tests/async/test_castle_key_reset.py`: seven key sequences and three
  control groups passed under ASan/UBSan, including the morph negative control
  described above and unchanged surviving object identities.
- `python3 tests/async/test_castle_key_reset_journey.py`: passed all seven key
  consumption sequences, seven reconnect/escape routes, six timer cases, both
  staff-reset modes and normal progression restoration.
- `python3 tests/async/test_shopkeeper_population.py`: all five scenarios passed.
- Existing `test_key_break_custody_contract.py`,
  `test_zone_reset_timing_contract.py` and `test_no_reset_zone_key.py`: passed.
- `make -C src -j6`: MariaDB development build passed. The journey's existing
  build helper also compiled and validated its separate flat-file server.
- Python syntax, changed C/C++ formatting, all 14 documentation contracts and
  `git diff --check`: passed; final commit checks remain enabled.

Ignored evidence is under `bin/qualification/issue418/`: `gameplay-report.json`,
the command transcript/server log, and the MariaDB build log. This qualifies
reset/door behavior in isolated native and flat-file runtime fixtures. It does
not claim production validation, a MariaDB socket journey, full-zone combat
safety, or an old recovery-snapshot migration.

Final ablation retains one production helper/call, one native regression with
its harness, one socket journey using existing build/client helpers, and the
plan/runbook updates. No area mutation, source restocking, new setting, schema,
global timer change, or parallel implementation remains. The morph predicate
is the only source-discovered refinement to the planned behavior.

After integrating `master` at `bc1537d9e`, the native regressions, existing
key/reset and shopkeeper contracts, MariaDB build, documentation/format checks,
and the complete socket journey passed again. The integrated journey repeated
all seven key sequences, all seven escape routes (165 movements), both staff
reset modes and the six real timer cases. Its flat-file binary SHA-256 is
`e5a013228ae2c50cf82588044761b431da0ac457a078ad716fc81420cbc74ac5`.
The only merge conflict was the shared plan path; the other project's record
was preserved unchanged in `plan-issue-437.md`. No castle implementation change
was needed for integration.
