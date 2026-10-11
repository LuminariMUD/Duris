# Plan: random equipment, rewritten for clarity, and a flexible `randobj`

Written 2026-10-10 against `master` at `879adf0aa`; decisions confirmed by the owner the
same day. This file is a working note: delete it when the last pull request lands.
[RANDOM_EQUIPMENT.md](../reference/RANDOM_EQUIPMENT.md) describes how the system behaves
today; that behaviour is what this plan keeps.

## Current handoff (2026-10-11)

All five phases are implemented and published as PRs #25 through #29. This checkout is
`enhancement/randeq-5-randobj`. PRs #25 through #28 are ready to merge in order; their
reviewed heads and local results are recorded below. PR #29's review is in progress.

Phase 5's original code commit `dbbc89dfe` passed both builds, 709/709 regressions,
72/72 database tests and the live command checks recorded in its phase section. The
current review carries in the lower-phase repairs and fixes recipe batch reporting:
only scrolls actually delivered count as created. The expanded ASan/UBSan command test
reproduced the old overcount and passes with the fix; both frozen fixtures, tokenizer,
formatting and documentation checks also pass. The live recipe check passed; only the
final full local gates remain. The PRs remain open and unmerged.

## Review follow-up (2026-10-11)

**Outcome:** address every review finding, oldest PR first, and leave the five published
PRs ready to merge. **Non-goals:** game-rule changes, unrelated cleanup and landing the PRs.
**Files:** the existing harness, affected implementation and their documentation as findings
require. **Proof:** focused regressions, the unchanged golden fixture, mutation checks for
test-coverage findings and the applicable local gates below; GitHub CI is not a gate.

`origin/master` remains `879adf0aa`, already an ancestor of every phase. Keep the published
stack and existing review tags; merge lower fixes upward in order and tag each fixed
head with the next `randeq/phase-<n>-review-<round>` tag. No rebase or squash is needed.

PR #25 is ready to merge at `randeq/phase-1-review-3`; all six review threads have
replies and are resolved. The harness now covers:

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
`pr1-review4-focused.log` and `pr1-review4-mutations.log`. Commit `a32d39dd7` passed
full formatting, both builds and `make test-all -j16 TEST_JOBS=16` (707/707, no reruns;
`pr1-review4.log`), plus site checks (15) and documentation checks (12). The final
record changes only this plan and reuses that code/test gate.


PR #26 is ready to merge at `randeq/phase-2-review-3`; its startup-help finding is fixed.
Merge `b4f4252a6` brings in all PR #25 repairs without conflicts or changes to Phase 2's
server code. It passed the strengthened ASan/UBSan golden harness, minimal boot checks,
full formatting, `make test-all -j16 TEST_JOBS=16` (707/707, both build profiles),
`make test-db` (72/72) and the site checks (15). No reruns were needed. The final record
only updates this plan and passes its 12 documentation checks. Evidence:
`randeq-gate/pr2-review1.log` and `pr2-review1-site.log`.

The second review merge adds only the two new golden assertions and documentation.
Its server source tree is byte-identical to the fully gated `fd38db525` revision. Reuse
that full build/regression/database evidence. The changed ASan/UBSan harness, 12
documentation checks, 15 site checks and formatting pass on this merge
(`pr2-review2-focused.log`, `pr2-review2-site.log`).

The final review repair removes the retired `[-l]` token from the fatal startup usage
message. Only that string changes in server code; option parsing and runtime behavior
are unchanged. Both builds and minimal-boot/format checks pass, and invalid invocations
of both binaries from a temporary directory exit with the corrected usage and no `[-l]`.
Evidence: `pr2-review3-{dev,production,focused,usage}.log`. Full regression/database
results above are retained for this help-only edit. The change propagates through #27–#29 before restarting #29's gate.

PR #27 is ready to merge at `randeq/phase-3-review-3`. Both findings are addressed: the
handoff, phase records and stack table now describe committed, published work and completed
gates; added author credits were removed from the three new module files. The inherited
harness retains the module split and all PR #25 repairs. Merge `131f095d8` passed full
formatting, 707/707 regressions, both builds and 72/72 database tests without reruns.
The final comment-only correction passed development and production builds, the ASan/UBSan
golden test and 12 documentation checks; the site checks passed (15). No executable code
changed after the full gate. Evidence: `randeq-gate/pr3-review1.log`,
`pr3-review1-site.log` and `pr3-review1-attribution-{dev,production}.log`.
The second review merge carries the new template and eligibility assertions into the
split module; rejected contexts call `random_equipment_kill_drop()` directly. Server
sources and build scripts remain identical to `9cbdca5fc`, retaining the completed full
gate above. The ASan/UBSan golden harness, 12 documentation checks, 15 site checks
and formatting pass (`pr3-review2-focused.log`, `pr3-review2-site.log`).
The third review merge adds only #26's corrected startup-help string and its record.
The previously completed module/golden/full gates remain valid; the help string was
built and exercised in both profiles on #26. Minimal-boot, formatting and 12 documentation
checks pass here.


PR #28 is ready to merge at `randeq/phase-4-review-3` and has no review findings.
The inherited ownership assertion initially treated the bare prototype in the foreign-spell
regression as generated equipment. It now runs at the direct-generation and kill-drop
observation points, retaining both exact mask checks while accepting the untouched
prototype. Temporary mutations removing `STRUNG_KEYS` fail on both observation paths.
No game code changed in this review pass, and both fixtures remain frozen.

Merge `00778b1b2` passed full formatting, both builds, the ASan/UBSan golden harness,
`make test-all -j16 TEST_JOBS=16` (707/707), `make test-db` (72/72), site checks (15) and
documentation checks (12). No gate reruns were needed. The final record changes only this
plan. Evidence: `randeq-gate/pr4-review1.log`, `pr4-review1-site.log`,
`pr4-review1-focused.log` and `pr4-review1-ownership.log`.

The second review merge retains both the ownership and template assertions at the two
generated-object observation points. Server sources and build scripts are identical to
`646ba5ca9`; their completed full-gate evidence remains valid. The ASan/UBSan golden
harness, 12 documentation checks, 15 site checks and formatting pass
(`pr4-review2-focused.log`, `pr4-review2-site.log`).
The third review merge adds only #26's corrected startup-help string and its record.
Minimal-boot, formatting and 12 documentation checks pass; the previous generator/full
and focused evidence is retained.


PR #29 review: `create_recipe()` now returns `bool`, reporting success only after
delivery, and the command uses it to guard the batch count and success line. Existing
eligibility rules and attempt limits are unchanged. The command harness uses the real
recipe function for containers/storage, four affect bitvectors, combat/spell pulse and
a controlled crafting-availability rejection, plus successful and mixed batches. Files: `randobj.c`, `drannak.c`,
`tradeskill.h`, the command harness and these notes. Proof: ASan/UBSan command checks,
both frozen fixtures, both builds, full regression/database gates and a private live
recipe check. This directly fixes the reporting boundary without duplicating eligibility
checks or adding retries. The all-rejected command failed before the repair and passes
afterward (`pr5-review1-recipe-before.log`, `pr5-review1-recipe.log`).

Merge `37abdac8c` retained every lower-phase assertion without changing server sources
from recipe-fix commit `02e391102`. Development, production and dedicated flat-file builds
passed (`pr5-review1-{dev,production,flatfile}.log`). The private level-62 live check
repeated the five requested commands and stat identity checks, then made 50 recipe
attempts: zero were eligible, output reported zero, and inventory stayed at 39 items.
Successful and mixed delivery are covered by the native command test. The first live
script stopped at a pagination prompt; adding page handling to that private script
completed the check (`pr5-review1-live-pages.log`). It saved and shut down cleanly.
The final follow-up adds #26's corrected startup usage string. The earlier gate on
`37abdac8c` was intentionally interrupted before completion when that finding arrived;
`pr5-review1.log` is not a completed gate. Fresh builds and full regression/database
gates will run on the merged revision (`pr5-review2.log`).

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

## Baseline before Phase 1

This inventory describes `879adf0aa`, not the current checkout. The phase records below
track what has been removed or moved; the line numbers here are historical.

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

Salvage generation also takes explicit levels as
`create_material(P_char finder, int finder_level, int source_level)`; its existing index
overload stays. This lets `randobj piece [level]` keep the alchemist refund and tier rolls
without mutating the staff character or constructing a fake mob.

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

**How the arguments are read** (`lohrr_chop`, which preserves every word):

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
5. **Wrong item displayed (found in Phase 5's live check).** Generated keywords start with
   `random`, and `do_stat()` parses only the first keyword. With existing random equipment
   it can display an older item. Phase 5 passes the generated object directly to the existing
   stat renderer through a four-argument overload in `actwiz.c`/`prototypes.h`. The normal
   three-argument command retains its lookup. This avoids reproducing equipment/inventory
   lookup ordering in `randobj` or mutating item keywords just to display it.
6. **Tokenizer buffer overflow (found while reviewing Phase 5).** `lohrr_chop()` restarted
   an unterminated single-quoted word without rewinding its output pointer, appending a
   second copy. A command-length word overflowed its output buffer under ASan. Rewind
   the pointer when restarting; a separate native tokenizer test proves the boundary,
   quote fallback and normal cases, and the randobj harness drives malformed long words
   through the command. This repair is a separate commit in Phase 5.

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

**Review and verification:** commit `3fdd367af`, open
[PR #25](https://github.com/LuminariMUD/Duris/pull/25), tag `randeq/phase-1-review-0`.
The golden test, seven other focused checks and formatting passed. `make test-all`
built the development and production profiles, then reported 706/707 Python tests
passing. `test_telemetry_capacity_272.py` exceeded its 5 ms budget during a concurrent
build, then passed alone on the same commit. The original log still records that
failure at `/home/aiwithapex/projects/randeq-gate/pr1.log`; the isolated pass was recorded
in the session and PR. `make test-db` was intentionally skipped for this phase.

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

**Done (2026-10-10).** 836 lines out. Found on the way and removed with the rest, since each
existed only for what went:

- two prototypes with no definition, `create_random_eq(int, int, int, int)` and
  `setsuffix_obj()`;
- `RANDOM_ZONES` in `defines.h`, read only by `create_randoms()`;
- the boot's `no_random` switch, which only guarded `create_randoms()`, with its `-l`
  option (nothing passes it; an unknown option only logs a line), the `-l` row in
  [ARCHITECTURE.md](../reference/ARCHITECTURE.md) ("disable random encounters", which it
  never did), and `test_minimal_boot.py`'s `no_random` assertion;
- the comment in `salchemist.c` pointing at `stone_list` and `stone_spell_list`.

`#define TROPHY` survives in other files, which use it for their own purposes.

**Ready to merge (2026-10-11):** `fd38db525`, [PR #26](https://github.com/LuminariMUD/Duris/pull/26),
tag `randeq/phase-2-review-1`. The review merge `b4f4252a6` passed both build profiles,
707/707 regressions and 72/72 database tests with no reruns. Golden, formatting, focused
and documentation/site checks also passed. The original interrupted gate is superseded;
its temporary worktree was removed. Evidence: `randeq-gate/pr2-review1.log`.

### Phase 3: the module and its interface

**Original implementation, committed and published:** `a3bff0079`, [PR #27](https://github.com/LuminariMUD/Duris/pull/27),
tag `randeq/phase-3-review-0`. The rename, three
new module files, moved structs/constants/prototypes, caller includes, `die()` delegation
and Makefile entries are in place. `setprefix_obj()` is private to the generator; the
unused `BUGGED` slot and empty material terminator are gone. The six affected tests and
four reference documents now follow the split, and every table's columns are documented.

The interrupted session's build failed on missing `CMD_*`, `TO_*`, `MAT_*` and `WEAPON_*`
definitions. Restoring `cmd/interp.h`, `net/comm.h` and `item/objmisc.h` fixed it; the
row-count assertions now compile. The golden harness includes the module header, compiles
all three source files and calls `random_equipment_kill_drop(killer, victim)` directly.

Original implementation validation: `make -C src -j16`, the unchanged 1,480-case golden fixture, all five other
affected tests and the 12 documentation checks. The disconnected proc body was compared
with Phase 2 and is unchanged. `make build-production -j16` and `./scripts/format.sh --check` also passed. Build logs:
`randeq-gate/pr3-dev.log` and `randeq-gate/pr3-production.log`. On `a3bff0079`,
`make test-all -j16 TEST_JOBS=16` passed 707/707 and `make test-db` passed 72/72 without
reruns (`randeq-gate/pr3.log`). The current review pass corrects this previously stale
handoff and carries in the stronger harness; its validation is recorded above.

- **Files:** `git mv` `randomeq.c` to `random_equipment.c`; move the tables to
  `random_equipment_tables.c` and the drop decision to `random_equipment_drop.c`.
- **Header:** add `random_equipment.h` with the structs and size constants, checked by
  `static_assert`s beside the table definitions; drop the `BUGGED` row
  (`number(0, MAX_SLOT - 1)` never reached it).
- **Kill drop:** move the block out of `die()` into `random_equipment_kill_drop()`. `die()`
  keeps one call in the same place, and its `tempobj` goes if nothing else uses it.
- **Declarations:** replace every local declaration and `prototypes.h` or `structs.h` entry
  with the header; update `src/Makefile`.
- **Tests that read files by name:**
  - `test_random_equipment_golden.py` (module sources, header and kill-drop call);
  - `test_random_equipment_config_contract.py`;
  - `test_difficulty_dials.py` (its hook strings);
  - `test_deferred_findings_repairs.py`;
  - `test_random_drop_owner_message.py` (now reads the new function);
  - `test_weapon_actions_runtime.py` (proc source path and the header for `random_spells`).

Every document that names `randomeq.c` or the moved functions follows:
[RANDOM_EQUIPMENT.md](../reference/RANDOM_EQUIPMENT.md),
[WEAPON_ACTIONS.md](../reference/WEAPON_ACTIONS.md), the module map in
[CODEBASE.md](../reference/CODEBASE.md), and
[WORLD_RECOVERY_FORMAT.md](../persistence/WORLD_RECOVERY_FORMAT.md).

Done when the golden test and the existing tests pass and the server builds (development and
the production `-O2` profile).

### Phase 4: a readable generator

**Original implementation, committed and published:** `4b7e68cb4`,
[PR #28](https://github.com/LuminariMUD/Duris/pull/28), tag `randeq/phase-4-review-0`.
The independent fixes are `316444732` (true-name
bounds) and `143fb1d5b` (void encrust return); the foreign-spell assertion and all existing
encrust cases pass under ASan/UBSan. The generator now has separate slot, material, naming,
suffix, weight, stat and type steps. The three naming copies are one function, and all
three switches are tables with the same mapping. Equipment and salvage use explicit
levels, with every live caller passing the same levels as before.

All 1,480 golden cases match the unchanged fixture. The fixture caught an attempted
`MAX(0, ... - number(...))` simplification drawing twice; the roll and clamp remain separate.
The weapon-dice `MIN` expression also deliberately retains its original repeated draw.
Every module function is at most 80 lines except the untouched, disconnected proc (112).
Development and production builds passed (`make -C src -j8`, `make build-production -j8`),
with logs `randeq-gate/pr4-dev.log` and `randeq-gate/pr4-production.log`. The affected
contracts and documentation checks passed. On `4b7e68cb4`, `make test-all -j16 TEST_JOBS=16`
passed 707/707 and `make test-db` passed 72/72 without reruns (`randeq-gate/pr4.log`).
Current review validation is recorded above.

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

**Original implementation, committed and published:** [PR #29](https://github.com/LuminariMUD/Duris/pull/29), branch
`enhancement/randeq-5-randobj`, tag `randeq/phase-5-review-0`. Code commit: `dbbc89dfe`;
the tag also includes the final documentation-only record.
The tokenizer repair is `a52c81902`. Both native harnesses, development and production
builds, the unchanged golden fixture, documentation checks and the live commands pass.
Build commands were `make -C src -j8`, `make build-production -j8` and the dedicated
flat-file build for the live check; their logs are `pr5-dev.log`, `pr5-production.log`
and `pr5-flatfile.log` under `/home/aiwithapex/projects/randeq-gate/`.

The committed-code gate passed `make test-all -j16 TEST_JOBS=16` (709/709) and
`make test-db` (72/72), without reruns. Evidence: `randeq-gate/pr5.log`.
The final handoff-only follow-up passes `python3 tests/async/test_documentation_contract.py`
(12 checks); it reuses the code gate because no source or test code changed afterward.

The existing `lohrr_chop` tokenizer replaces the planned `one_argument`: the latter
silently drops words like "at" and "with", violating
the requirement to reject stray arguments. No new tokenizer was added. Recipe batches
repeat attempts and report the number made, excluding ineligible random blanks and
all targets rejected by recipe eligibility rules.

The first live run completed all five commands but showed the previous wielded-type item
again after `eq 62`. That exposed defect 5 above; the corrected live run checks
item identity/type, not only the presence of a stat block. The native harness checks that
each single-item stat receives the new object even after a batch with identical keywords.

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

**Live results (2026-10-11):** existing isolated-server and account-creation journey helpers
created a private flat-file character, promoted it offline, then rebooted the same temporary
state with the full world. `score` confirmed level 62. The commands returned:

| Command | Observed output |
| --- | --- |
| `randobj eq ring 30 3` | Ashen ivory, well-used sapphire and hardened hemp rings, each `(level 30)`; `Created 3 equipment items.` |
| `randobj eq wield` | Stat for a soldier's dragonscale bastard sword from The Plains of Life; type `WEAPON`, wear `WIELD` |
| `randobj eq 62` | Stat for some hardened dragonscale shoes; type `ARMOR` |
| `randobj piece 40 5` | Intergalactic dust, still-living bloody flesh, hemp, platinum and marble, each `(level 40)`; `Created 5 materials.` |
| `randobj mob 20` | `Created mob: Eroruk halfling ethermancer (level 20)` |

Extra checks forced a long sword and then a ring while both prototypes were already carried:
the stat blocks showed the new weapon and new armour respectively. Ordinary `stat o sword`
still found the long sword. The character saved, the server shut down cleanly and the
private state was removed. The script and full output are
`/home/aiwithapex/projects/randeq-gate/pr5-live.py` and `pr5-live.log`.

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
| 1 | 1, golden test (plus the plan and the notes above) | `enhancement/randeq-1-golden` | [#25](https://github.com/LuminariMUD/Duris/pull/25) | Ready at `ef0f6ec8a` (`randeq/phase-1-review-3`); all six findings fixed |
| 2 | 2, dead code out | `enhancement/randeq-2-dead-code` | [#26](https://github.com/LuminariMUD/Duris/pull/26) | Ready at `40e6db8b4` (`randeq/phase-2-review-3`); startup-help finding fixed; full gates retained |
| 3 | 3, module and interface | `enhancement/randeq-3-module` | [#27](https://github.com/LuminariMUD/Duris/pull/27) | Ready at `cd712da5f` (`randeq/phase-3-review-3`); both findings fixed and full gates passed |
| 4 | 4, readable generator | `enhancement/randeq-4-generator` | [#28](https://github.com/LuminariMUD/Duris/pull/28) | Ready at `92ba5294f` (`randeq/phase-4-review-3`); no findings, full gates retained and new assertions passed |
| 5 | 5, `randobj` with arguments | `enhancement/randeq-5-randobj` | [#29](https://github.com/LuminariMUD/Duris/pull/29) | Review fix `02e391102` and all lower fixes merged; final full gates pending |

## Checks per pull request

Every pull request runs the golden test and its own focused tests, then
`./scripts/format.sh --check`, a development and production build, and `make test-all` and
`make test-db` on its head in a throwaway worktree
(`git worktree add --detach ../duris-plan-gate <sha>`, removed after), in the background, so
the checkout can move on while the gate runs. PR 1 changes no server code (a test, comments
and documents), so it skips `make test-db`.
For later tests/documentation-only follow-ups, retain the completed full gate after
verifying the server source tree is identical, and rerun the affected tests against each
phase's implementation. Behavioral changes still require fresh full gates.

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

## Ablation review at takeover (2026-10-10)

Outcome, non-goals, files and proof remain those above. Keep the module split: the drop
decision has independent callers, while the generator and staff command have different
responsibilities. Reuse the golden fixture and existing harnesses; no new compatibility
wrapper or test framework is needed for the move. The missing includes and stale harness
paths are required integration repairs, not changes to game rules.

Phase 5 retains the existing tokenizer and stat renderer. The tokenizer pointer reset and
direct-object stat overload are justified by reproduced failures; no new parser or second
display implementation is needed. Slot choices come from the existing tables, and explicit
levels avoid fake characters or temporary character mutations. The focused command and
tokenizer harnesses cover behavior the unchanged generation fixture cannot prove.
