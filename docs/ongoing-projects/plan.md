# Plan: random equipment, rewritten for clarity, and a flexible `randobj`

Written 2026-10-10 against `master` at `879adf0aa`; decisions confirmed by the owner the
same day. This file is a working note: delete it when the last pull request lands.
[RANDOM_EQUIPMENT.md](../reference/RANDOM_EQUIPMENT.md) describes how the system behaves
today; that behaviour is what this plan keeps.

## Review follow-up (2026-10-11)

**Outcome:** address every review finding, oldest PR first, and leave the five published
PRs ready to merge. **Non-goals:** game-rule changes, unrelated cleanup and landing the PRs.
**Files:** the existing harness, affected implementation and their documentation as findings
require. **Proof:** focused regressions, the unchanged golden fixture, mutation checks for
test-coverage findings and the applicable local gates below; GitHub CI is not a gate.

`origin/master` remains `879adf0aa`, already an ancestor of every phase. Keep the published
stack and existing review tags; merge lower fixes upward in order and tag each fixed
head with the next `randeq/phase-<n>-review-<round>` tag. No rebase or squash is needed.

PR #25 review round 3 addresses two findings received after the previous ready tag
`randeq/phase-1-review-2`. The four earlier findings remain fixed. The harness now covers:

- different pet/owner level, luck and room attributes;
- all 26 suffix totals and their RNG consumption;
- a sentinel RNG draw after all 1,480 cases, stored in a companion fixture captured
  from original `master` code at `879adf0aa`;
- real string setters and all three string ownership bits on every generated item,
  including kill drops, so generated names are marked for persistence;
- the weapon/armor blank vnum at both direct-generation and kill-drop observation points;
- ordinary NPC killers, player victims, dead player killers and dead pet killers, with no
  drops, messages or RNG draws allowed in these rejected contexts.

The original item fixture remains unchanged. Both fixtures are frozen for later phases.
Temporary mutations proved the repairs: either pet roll using the owner fails four cases;
removing suffix 5, 6 or 7 fails its assertion; an extra terminal longbow draw leaves item
output unchanged but fails three RNG sentinels; bypassing each string setter fails the
ownership assertion. No game code changed. The real setters replace three test stubs.

**Previous proof:** code/test commit `be9c9915d` passed the ASan/UBSan harness, full formatting,
`make test-all -j16 TEST_JOBS=16` (707/707, no reruns, including both build profiles),
`npm test --prefix site` (15 checks) and 12 documentation checks. `make security-check`
also passed on the unchanged security sources. The final record commit only updates this
plan. `make test-db` remains exempt for this tests/comments/docs phase. Logs are under
`/home/aiwithapex/projects/randeq-gate/`: `pr1-review3.log`, `pr1-review3-site.log`,
`pr1-review1-security.log`, `pr1-review1-mutations.log`, `pr1-review2-rng.log` and
`pr1-review3-ownership.log`. Earlier full gates also passed; their logs are retained.
CodeQL and Trivy are not installed locally; those external scanners were not rerun.
The new assertions preserve both frozen fixtures. ASan/UBSan passes, and temporary
mutations swapping the weapon blank or omitting any of the three eligibility predicates
fail. No new fixture or production code is needed: template identity is a fixed invariant
of the existing wear flags, and rejected contexts must be side-effect free. Evidence:
`pr1-review4-focused.log` and `pr1-review4-mutations.log`. The full local gate is pending.
Then merge upward through #26, #27, #28 and #29 in order; their prior fixes and evidence
remain valid, and #29's recipe repair is already committed at `02e391102`.

## Goal

1. **Clear code.** The random-equipment code (the kill-drop decision, the item generator,
   salvage materials and encrust stones, and the affect helpers other code borrows) and the
   `randobj` staff command become well structured, well named and accurately commented.
2. **Same game.** Every drop decision, item, material and stone the game makes today, it
   makes afterwards, roll for roll. A golden test (Phase 1) proves it at every phase. The
   defect fixes below change no generated output.
3. **A flexible `randobj`.** `randobj eq [slot] [level] [count]`, and level and count options
   where they make sense for the other subcommands.

Not in this plan: tuning or new settings, attaching `random_eq_proc()` (D1), random-zone and
random-mob internals beyond `randobj mob`'s options, and crafting's commented-out code that
once called the generator (`src/economy/crafting.c`, around lines 1011 to 1090).

## What is there now

`src/item/randomeq.c` (1,814 lines) holds everything, in this order:

| Lines | What | State |
|---|---|---|
| 11 | `#define TROPHY` | Unused here |
| 36 to 61 | 25 `extern` declarations | Most unused |
| 62 to 106 | `randomeq_weapon_data`, `randomeq_material_weapon_data`, `randomeq_prefix_data` | Never used |
| 107 to 150 | `highdrop_mobs`, 39 boss vnums | Used only by commented-out code |
| 152 to 175 | `stone_list`, `stone_spell_list` | Never read |
| 183 to 492 | Material, prefix, spell and slot tables | Live; columns half documented |
| 494 to 565 | `create_randoms()` | Body compiled out: `RANDOM_ZONES` is always defined (`src/core/defines.h:1389`), yet `src/net/comm.c:908` still calls it at boot |
| 567 to 605 | `create_material()` (both forms), `create_stones()` | Live |
| 608 to 802 | `check_random_drop()` | Live; a 14-case level switch, two commented-out features (high-drop mobs, trophies) |
| 804 to 1321 | `create_random_eq_new()` | Live; 520 lines in one function, three near-copies of the naming code, two large commented-out blocks |
| 1324 to 1401 | `setsuffix_obj_new()` | Live; also used by `src/classes/salchemist.c` |
| 1403 to 1565 | `setprefix_obj()` | Live; a 31-case switch |
| 1567 to 1678 | `random_eq_proc()` | Never attached to any object, in any version in our history; kept and marked "not connected" (D1) |
| 1680 to 1722 | `set_enchant_affect()` | No caller; one case sets an `AFF2_` bit in the `AFF1` field |
| 1724 to 1759 | `set_encrust_affect()` | Live (`salchemist.c:1313`); returns 0 from a `P_obj` function |
| 1761 to 1795 | `identify_random()` | Live (reveal true name, `src/magic/magic.c:10189`) |
| 1797 to 1814 | Commented-out copy of `stone_spell_list` | Dead |

`src/item/randobj.c` (582 lines) holds `do_randobj()` (lines 159 to 268) and, around it, an
abandoned second random-object system: `randomObjFieldsArr` (lines 38 to 135), `Encrypt()`,
`getMonsterDiffNumber()`, `createRandomItem()` and nine helpers (lines 270 to 582), with
their types in `src/item/randobj.h`. Nothing calls any of it.
`createRandomItem` is still declared in `src/core/prototypes.h:2290`.

Also worth fixing:

- The random-drop block lives in `die()` (`src/combat/fight.c`, about 45 lines), not in the
  module.
- The interface is scattered:
  - prototypes sit in `src/core/prototypes.h` (around line 1197) and the table structs in
    `src/core/structs.h` (around line 2466);
  - `src/ships/ship_npc.c:1706`, `salchemist.c:187` and `magic.c:270` redeclare functions
    locally;
  - `src/cmd/actnew.c:71` and `src/world/random.zone.c:68` declare tables they never read.
- The table sizes `MAX_SLOT`, `MAXMATERIAL` and `MAXPREFIX` sit in `src/core/config.h` and
  must match the tables by hand. The slot table ends in a `BUGGED` row that only exists to
  fill `MAX_SLOT + 1`.
- `do_randobj()` takes no arguments. It compares its whole argument string with each
  subcommand, so `randobj eq 30` reaches the usage line.

## How "same game" is proven: the golden test (Phase 1)

`tests/async/test_random_equipment_golden.py` builds a native harness under ASan/UBSan. It
compiles the module's own source files whole (not extracted functions), links the real
`src/core/random.c` and `src/item/random_equipment_config.c`, and stubs only the world:

- three zones: one with colour codes in its name (difficulty 5), one plain (difficulty 1),
  and a town; four rooms, including a guild room;
- blank objects for vnums 1252 and 1254;
- materials and stones by vnum;
- the difficulty dials at 1.0, plus one case at 1.5.

The three string setters are extracted from their real source. Generated equipment must
set all three string ownership bits so persistence saves its names.

Each case calls `randomize(seed)` with its own seed first, so cases are independent: a
failure names one case, and adding a case shifts no other.

| Part | Cases | Recorded |
|---|---|---|
| Drop decision | A grid: killer levels 1 to 16 and four higher, nine mob levels, luck 60/100/160, equipment roll; the material roll at luck 100. Each special condition (elite, neutral player, Hardcore, town, guild room, no-experience mob, shopkeeper, the loot dial at 1.5) at three level pairs, both rolls. 50 draws per case | One bit string per case |
| Kill drop | The drop block of `die()`, player and pet killer, four level pairs including level 1 versus 62 so both rolls always win, 40 kills each | Each kill's objects put on the victim, and who reads the salvage line |
| Generator | Every slot fixed, in the coloured zone at the best odds (so nearly all are named: every weapon path, shield, quiver, robe and the weapon spell) and in the plain zone; random slot across killer and mob levels, luck 60/100/160, both zones, player, NPC and shopkeeper killer; every material fixed; the quality dial at 1.5; a missing blank | Every field the generator sets: keywords, both descriptions, wear flags, type, extra flags, anti-class flags, material, craftsmanship, weight, `value[0..7]`, the four affects, all bitvectors, and its messages |
| Materials and stones | Levels 1 to 62, alchemist and not; `create_material(index)` for every index; stones | Vnums, and the alchemist's bind refund |
| Encrust and true name | `set_encrust_affect()` for each stone spell; `identify_random()` for every spell in the table | Bitvectors; the new short description |

The kill drop is still inside `die()` in Phase 1, so the harness compiles that block, cut
from `fight.c` between its `// object code - Normal kills.` comment and `update_pos(ch);`.
From Phase 3 it calls `random_equipment_kill_drop()` instead.

The expected output is committed as `tests/fixtures/random_equipment_golden.txt`, readable,
one case per line, about 260 KB. It is written once, from today's code. Later phases change
only the harness's file list and the calls into the new interface, never the fixture. A
phase whose output differs is wrong. The fixture never changes, so its coverage (named
items, owner tags, weapon spells, every item type) was checked once by hand when it was
written, not by an assertion.

The review added direct assertions for all 26 suffix totals and a companion RNG fixture,
captured from the original implementation, that pins the next draw after every case.
This catches terminal draws even when all fields of the current item still match.
Both fixtures stay frozen through the remaining phases.

Every refactor below must therefore keep the order of the random rolls. Turning a switch
into a table keeps the roll and its mapping. A helper that moves a roll must leave it at the
same point in the sequence.

## Target shape

| File | Holds |
|---|---|
| `src/item/random_equipment.h` | The module's whole interface, the table structs (out of `structs.h`), and `MAX_SLOT`, `MAXMATERIAL` and `MAXPREFIX` (out of `config.h`), each tied to its table by a `static_assert` |
| `src/item/random_equipment_tables.c` | The slot, prefix, material and spell tables, every column documented once above each table |
| `src/item/random_equipment_drop.c` | `check_random_drop()`, and the kill-drop block moved out of `die()` as one call, `random_equipment_kill_drop(killer, victim)` |
| `src/item/random_equipment.c` | The generator, salvage materials, stones, the affect helpers (`setsuffix_obj_new`, `setprefix_obj`, `set_encrust_affect`, `identify_random`), and `random_eq_proc()` in its own section headed "not connected" |
| `src/item/random_equipment_config.c` and `.h` | Unchanged |
| `src/item/randobj.c` | `do_randobj()` only |

`randomeq.c` becomes `random_equipment.c` by `git mv`, so `git log --follow` keeps its
history. The drop decision gets its own file because it is a separate question ("does this
kill drop something?") with its own callers and settings.

**The generator takes levels, not a mob.** `create_random_eq_new()` reads exactly one thing
from the mob, its level (eleven times). It reads the killer's level, luck, name, room,
player or shopkeeper status and newbie flag. The new core is:

```c
P_obj create_random_eq(P_char finder, int finder_level, int source_level, int slot, int material);
```

The kill path and every other caller pass `GET_LEVEL(killer)` and `GET_LEVEL(mob)`, so they
generate exactly what they do today. `randobj eq <level>` passes the level it was given for
both. No other abstraction is added.

**Inside the generator,** `create_random_eq()` becomes a short sequence of documented steps,
each a `static` function, in today's roll order:

1. pick the slot, then the prefix;
2. work out the quality and pick the material;
3. name the item: one function for the three styles (zone-named, owner-tagged, plain) and
   the plural ("some boots") and article ("an") rules, instead of three copies;
4. add the suffix affects;
5. set the weight, then the affects;
6. set the type-specific values (quiver, shield, robe, weapon, longbow, armour).

The rules the doc describes become named constants with a one-line why, for example:

- the 1-in-26 stone;
- the two-in-three worn-slot weighting and its last worn slot;
- the named-item odds;
- the owner tag's level 45 and 1 in 10;
- the 1-in-20 extra suffix and the 1-in-3 weapon spell;
- the one-handed 70 percent.

Comments state what the code does and why, never a stale percentage. The formula comments
are checked against the golden data.

**Tables instead of switches,** keeping the same roll mapping:

- `check_random_drop()`'s level ratio for killer levels 1 to 14 becomes a 14-row table of
  offset and divisor;
- `setprefix_obj()`'s 31 outcomes become a table of location and multiplier;
- `setsuffix_obj_new()`'s 23 affects become a table indexed by the 5d6 roll.

**One header everywhere.** Every caller includes `item/random_equipment.h`:

- callers: `fight.c`, `random.mob.c`, `random.zone.c`, `world_quest.c`, `drannak.c`,
  `ship_npc.c`, `salchemist.c`, `magic.c`, `randobj.c`;
- the local redeclarations and the unused table `extern`s go.

## The `randobj` command (Phase 5)

Syntax (Forger and up, as today):

| Command | Does | Defaults |
|---|---|---|
| `randobj` | Prints the full usage | |
| `randobj eq [slot] [level] [count]` | Generates equipment as a drop from a level-*level* mob killed by a level-*level* killer, using your luck and your zone | slot `any`, level your own, count 1 |
| `randobj eq list` | Lists the slot words: wear locations and slot nouns, grouped by location | |
| `randobj piece [level] [count]` | Salvage materials at that drop level | level your own, count 1 |
| `randobj stone [count]` | Encrust stones | count 1 |
| `randobj recipe [count]` | Zone recipes, as today, repeated | count 1 |
| `randobj mob [level] [count]` | Random mobs; level 0 means the generator's own choice, as today | level 0, count 1 |
| `randobj encrust [count]` | Sample encrusted names | count 10, as today |
| `randobj zone`, `map`, `remove` | Unchanged | |

**How the arguments are read** (`one_argument`):

- For `eq`, a first argument that is not a number is the slot; then the first number is the
  level and the second the count. So `randobj eq 50 5` means any slot, level 50, five items.
- **Slot words:**
  - `any`;
  - a wear location, the `wear_bits` names in `src/core/common.c:431` without their `WEAR_`
    prefix (`finger`, `neck`, `body`, `wield` and so on), which picks uniformly among the
    slot rows for that location;
  - a slot noun from the table, colour stripped and spaces as hyphens (`ring`,
    `tower-shield`, `long-sword`).
- **Limits:**
  - level 1 to 62;
  - count 1 to 50 for objects and 1 to 10 for mobs, since each random mob stays in the world
    as a wanderer.
- **Errors:** an unknown slot word, a level or count out of range, or a stray argument
  prints that subcommand's usage, and nothing is created.

**Output:**

- **Count 1:** `randobj eq` shows the item's `stat`, as today.
- **More than one:** a line per item (short description, level used), then a total.
- **Failure:** if an item cannot be created (a blank vnum missing from the world), the
  command says so and stops, instead of crashing.

The `RANDOBJ` entry in `lib/information/help_index` is rewritten with this table and three
examples.

## Defects to fix along the way

Each is its own commit, with a test. None changes generated output.

1. **Out-of-bounds read.** `identify_random()` scans `spells_data` up to index 61 of a
   61-entry table, so it reads past the end for a weapon whose spell is not a random-weapon
   spell. Fix: bound the loop by the table's size. Test: a foreign-spell case in the golden
   harness, which runs under ASan (an assertion, not a fixture line).
2. **`randobj` crash.** `randobj eq`, `piece` and `stone` pass the generator's result to
   `obj_to_char()` and `do_stat()` without checking it. Fixed by the rewrite (Phase 5);
   tested there.
3. **Wrong return type.** `set_encrust_affect()` returns 0 from a `P_obj` function, and its
   one caller ignores the result. Make it `void`.
4. **Wrong field.** `set_enchant_affect()` sets `AFF2_VAMPIRIC_TOUCH` in the `AFF1` field. It
   has no caller, so it is deleted (Phase 2), not fixed.

## Decisions (confirmed by the owner, 2026-10-10)

- **D1. Keep `random_eq_proc()` and the item-action route built on it, marked as not
  connected.** It has never been attached to an object in our history, so the
  `itemActions.randomWeapons` route (Liskin's 2026-09-13 telegraph pilot) cannot start
  either. Both stay, untouched apart from comments, until someone attaches the proc on
  purpose. The marking landed with this plan, in the bottom pull request:
  - a "NOT CONNECTED" comment above `random_eq_proc()` and above
    `selected_random_weapon_action()` in `src/item/weapon_actions.c`;
  - a comment beside the two `itemActions.randomWeapons.*` keys in `lib/duris.properties`;
  - a "Not connected yet" paragraph in [WEAPON_ACTIONS.md](../reference/WEAPON_ACTIONS.md)
    and its configuration row;
  - the same in [RANDOM_EQUIPMENT.md](../reference/RANDOM_EQUIPMENT.md).

  Every phase keeps those notes true: Phase 3 moves the function with its comment, and no
  phase reshapes its body. `test_weapon_actions_runtime.py` keeps driving it.
- **D2. File names** as in Target shape. They match the existing
  `random_equipment_config.*`, and `randobj.c` keeps the command's name.
- **D3. `randobj` syntax, defaults and limits** as in the command section: level defaults to
  your own, count to 1, at most 50 objects or 10 mobs.
- **D4. Stacked pull requests,** one per phase, as in Stack below.

## Phases

### Phase 1: the golden test

The harness and fixture described above, written against today's `randomeq.c`. No server
source changes.

Done when the test passes on `master`, and fails when a single roll in
`create_random_eq_new()` is moved (checked once by hand, not committed).

**Done (2026-10-10).** `tests/async/test_random_equipment_golden.py` and its 1,480-case
fixture; it runs in about 4 seconds. Coverage, checked by hand: 131 named items, 15
owner-tagged (one by an NPC), 10 weapon spells, every item type (88 weapons, 3 longbows,
274 armour, 22 shields, 7 quivers, 5 robes), lances, backstab weapons, heater, buckler and
tower shields, the newbie message, a stone on each of the kill drop's two rolls, 29
alchemist refunds. Probes, each reverted:

- the prefix roll moved below the zone lookup: 362 cases differ;
- the drop jitter moved past the percentage scaling: 444 differ;
- the kill drop's first stone roll made 1 in 25: 3 differ;
- the jitter and low-level bonus rolls swapped: no change, correctly, since both draw 11
  values that are only summed, so the game is the same.

The harness takes `dice`, `strip_ansi`, `FirstWord`, `isname`, `material_restrictions`,
`GET_CLASS` and `BOUNDED` from their real source by signature, and `ALL_MAGES` and
`ALL_ROGUES` from `objconv.c`. Phase 3 changes `MODULE_SOURCES` and the kill drop's call.

### Phase 2: dead code out

Remove what nothing runs:

- in `randomeq.c`:
  - the unused structs, `highdrop_mobs`, `stone_list`, `stone_spell_list`, the unused
    `extern`s and `TROPHY`;
  - `set_enchant_affect()` and the trailing commented-out table;
  - the commented-out features inside `check_random_drop()` and `create_random_eq_new()`:
    high-drop mobs, trophies, crafted names, the "quickmod" block;
- `create_randoms()` and its call in `comm.c`;
- the abandoned system in `randobj.c` and `randobj.h`, and `createRandomItem`'s prototype.

`random_eq_proc()` and its route stay (D1).

Tests and docs that name these change with them:

- `test_deferred_findings_repairs.py` (its `createSetItem` check stays true);
- the `create_randoms()` note in `docs/testing/REGRESSIONS.md`.

Done when the golden test passes unchanged and `git grep` finds none of the removed names.

### Phase 3: the module and its interface

- **Files:** `git mv` `randomeq.c` to `random_equipment.c`; move the tables to
  `random_equipment_tables.c` and the drop decision to `random_equipment_drop.c`.
- **Header:** add `random_equipment.h` with the structs, the size constants and their
  `static_assert`s; drop the `BUGGED` row (`number(0, MAX_SLOT - 1)` never reached it).
- **Kill drop:** move the block out of `die()` into `random_equipment_kill_drop()`. `die()`
  keeps one call in the same place, and its `tempobj` goes if nothing else uses it.
- **Declarations:** replace every local declaration and `prototypes.h` or `structs.h` entry
  with the header; update `src/Makefile`.
- **Tests that read files by name:**
  - `test_random_equipment_config_contract.py`;
  - `test_difficulty_dials.py` (its hook strings);
  - `test_deferred_findings_repairs.py`;
  - `test_random_drop_owner_message.py` (now reads the new function).

Every document that names `randomeq.c` or the moved functions follows:
[RANDOM_EQUIPMENT.md](../reference/RANDOM_EQUIPMENT.md),
[WEAPON_ACTIONS.md](../reference/WEAPON_ACTIONS.md), the module map in
[CODEBASE.md](../reference/CODEBASE.md), and
[WORLD_RECOVERY_FORMAT.md](../persistence/WORLD_RECOVERY_FORMAT.md).

Done when the golden test and the existing tests pass and the server builds (development and
the production `-O2` profile).

### Phase 4: a readable generator

Split `create_random_eq_new()` into the steps above, behind `create_random_eq()` with level
parameters (the old name goes, every caller moves). Then:

- turn the three switches into tables;
- name the rule constants;
- rewrite every comment in the module to state what is true;
- fix defects 1 and 3, each in its own commit.

Done when the golden test passes unchanged and no function in the module is longer than
about 80 lines, apart from the tables and `random_eq_proc()` (D1).
[RANDOM_EQUIPMENT.md](../reference/RANDOM_EQUIPMENT.md) names the new functions.

### Phase 5: `randobj` with arguments

Rewrite `do_randobj()` as in the command section, each subcommand a small `static` handler
over a shared argument parser, and rewrite the `RANDOBJ` help entry.

`tests/async/test_randobj_command.py`, a native harness that compiles the real `randobj.c`
with recording stand-ins for the generators, covers:

- defaults;
- slot words of each kind and `eq list`;
- the number rules;
- every limit and error;
- the failure message when the generator returns nothing.

Then one in-game check as a level 62 on a local server: `randobj eq ring 30 3`,
`randobj eq wield`, `randobj eq 62`, `randobj piece 40 5`, `randobj mob 20`, with the
output recorded in this file.

[RANDOM_EQUIPMENT.md](../reference/RANDOM_EQUIPMENT.md) gets `randobj`'s syntax, and
[REGRESSIONS.md](../testing/REGRESSIONS.md) a section for the `randobj` crash (defect 2).
Phase 4 adds the section for the out-of-bounds read (defect 1). The golden test is described
in RANDOM_EQUIPMENT.md from Phase 1, since REGRESSIONS.md holds one section per fixed defect.

Done when both pass.

Documentation moves with the code: each phase updates the documents its change makes untrue,
in the same pull request, so every head in the stack describes itself. When the last pull
request has landed, a record commit on `master` deletes this file.

## Stack

Worked in the worktree `/home/aiwithapex/projects/duris-plan`, set up as the earlier plans
were (its own `.env` with the journal path fixed, copies of `lib`, `certs`, `runtime`,
`Players` and `Accounts`, dev port 4000). One branch and one pull request per phase, each
based on the one below, so each pull request's diff is its own phase. The first targets
`master`.

- **Bottom of the stack.** PR 1's branch starts with everything that differed from `master`
  when the plan was locked: this file, the not-connected notes (D1), and two unrelated
  documentation changes from the same day: `docs/records/CREDITS.md` renamed to
  `CREDITS_modernizations.md` with its three links updated, which also fixed the
  documentation contract test.
- **Review.** Each head that goes up for review is tagged `randeq/phase-<n>-review-0`
  (lightweight). A review round's fixed head gets `-review-1`, and so on.
- **Fixes in lower phases.** A fix to a lower branch, after the ones above it exist, is a new
  commit on that branch. The branches above take it by merge, never by rebase once pushed. A
  phase takes `master`'s catch-up only through the phase below it.
- **Parallel sessions.** If one session per pull request runs at once, the session that owns
  `duris-plan` keeps it. The others each use their own worktree (`duris-plan-pr<n>`), set up
  the same way.
- **Landing.** Land in order with merge commits, which this repository permits, to keep
  the shared ancestry of the stack. Retarget each next pull request to `master`
  (`gh pr edit <n> --base master`) before deleting the branch it was stacked on.

| PR | Phase | Branch | GitHub | State |
|---|---|---|---|---|
| 1 | 1, golden test (plus the plan and the notes above) | `enhancement/randeq-1-golden` | opened | Done; up for review (`randeq/phase-1-review-0`) |
| 2 | 2, dead code out | `enhancement/randeq-2-dead-code` | | Not started |
| 3 | 3, module and interface | `enhancement/randeq-3-module` | | Not started |
| 4 | 4, readable generator | `enhancement/randeq-4-generator` | | Not started |
| 5 | 5, `randobj` with arguments | `enhancement/randeq-5-randobj` | | Not started |

## Checks per pull request

Every pull request runs the golden test and its own focused tests, then
`./scripts/format.sh --check`, a development and production build, and `make test-all` and
`make test-db` on its head in a throwaway worktree
(`git worktree add --detach ../duris-plan-gate <sha>`, removed after), in the background, so
the checkout can move on while the gate runs. PR 1 changes no server code (a test, comments
and documents), so it skips `make test-db`.

## Ablation review (2026-10-10, before Phase 1)

The plan was checked part by part against what each part is for:

- **Added:** the kill-drop part of the golden test. Phase 3 moves that block out of `die()`
  and nothing else would prove its rolls survived the move.
- **Added:** encrust and true-name cases. Both functions move in Phase 3 and change in
  Phase 4. Defect 1's test joins the same harness instead of a new file.
- **Simplified:** the drop-decision cross product is a grid sample, and the coverage check is
  a one-time hand check, not a committed assertion. The fixture came out at 260 KB, not the
  200 KB first guessed: both slot sweeps were kept rather than cut to fit, since each proves
  every slot row in one naming style.
- **Scaled:** PR 1's gate skips `make test-db`.
- **Kept:** everything else. Each part serves the goal or an owner decision (D1 to D4).
