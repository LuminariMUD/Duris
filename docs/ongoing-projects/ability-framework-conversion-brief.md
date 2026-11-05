# Ability framework conversion brief

How to give a spell, skill, song, epic skill or innate shared numbers. Every registered ability
is already converted or on the reviewed no-numbers list, so use this for a new ability, or for a
number that moves out of a handler later. It's written for a batch of spells, and the skills,
songs and innates sections below add what differs for them.

## The framework

Each number lives in one ordinary C++ function beside its handler. The handler calls it to play
the ability, and the info page calls it to describe the ability, so a coder changes balance by
editing that one function. The page is text only, and only coders change numbers.

- **Rolls:** a function that rolls takes a `const Rolls &` and calls `rolls.dice()` and
  `rolls.number()`. The handler passes `live_rolls`, which draws exactly as before. The page
  passes `lowest_rolls` and `highest_rolls`, which return each call's bounds without touching the
  RNG, following `dice()`'s clamping and `number()`'s reversed bounds. The two results are exact
  only when the number never decreases as a roll increases. An expression that subtracts a roll,
  multiplies one by a negative, or divides by one doesn't show a range from them.
- **Facts function:** beside the handler, it builds the ability's mechanics lines for the viewer.
  `ability_facts()` or `innate_facts()` in `src/abilities/` maps the ability to it, and the info
  page adds the section between the access section and the help entry.
- **Coverage test:** every registered ability must have a facts function or be on the reviewed
  no-numbers list, and the pending list may only shrink.

Rules for every facts function:

- Use the level and inputs the viewer's own use would pass, taken from the real call path.
- Never show a target's hidden values. A target-dependent result appears only as a stated
  condition, such as "if the target fails its save", or not at all.
- Leave out a number that isn't verified. Never show it as zero.
- Never roll, spend a use, or change game state. Innates read `TAG_INNATE_TIMER` through the
  read-only status, never `check_innate_time`.

Rules for moving a number:

- **Current gameplay is the authority.** A conversion moves existing math without changing
  results. Balance changes are separate commits.
- **Move, don't rewrite.** Keep the same calls, operand order, types and casts. An expression with
  several rolls stays whole, because C++ doesn't fix the order of `+` operands.
- **Leave decisions in place.** Saves, chance checks and the `spell_damage` handoff stay where they
  are in the handler.
- **Keep every caller.** Handler signatures don't change, so items, NPCs, scrolls, wands and nested
  casts keep the level they pass today.
- **Prove restructured code.** A conversion that changes the code's shape also gets an
  old-versus-new test under a seeded RNG, comparing results and the number of draws.
- **Convert a shared effect once,** beside its shared helper, not once per class.

## Read first

- The first examples:
  - `src/abilities/abilities.{h,c}`: `Rolls` (`live_rolls`, `lowest_rolls`,
    `highest_rolls`), `Range`, `fact()`, `show()`, `seconds()`, `game_hours()`,
    `ability_facts()`.
  - `src/magic/magic.c`: `fireball_damage`, `fireball_failed_save`,
    `fireball_passes_globes`, `fireball_facts`, and their use in `spell_fireball`.
  - `src/cmd/actoff.c`: `bash_damage` … `bash_facts` and their use in `bash()`.
  - `tests/async/test_ability_framework.py`, `tests/async/test_ability_coverage.py`.

## For each spell in your batch list

Each list line is: constant, handler function, file, spell name.

1. Read the handler and whatever computes its numbers.
2. Classify it:
   - **Convert** when it has numbers a player cares about: damage or healing amounts,
     affect durations, stat/AC/hitroll/damroll/save modifiers, counts, lag, fixed chance
     thresholds.
   - **No numbers** when nothing numeric reaches the player (a stub, a disabled spell, a
     pure utility with no duration or amount). Move its constant from
     `tests/fixtures/ability_coverage_pending.txt` to
     `tests/fixtures/ability_coverage_no_numbers.txt`.
   - **Leave pending** only when the numbers cannot be moved without restructuring logic.
     Say why in your final report. Convert the clear numbers rather than skipping a spell.
3. Convert by moving, not rewriting:
   - Add `static` functions beside the handler named `<spell>_<quantity>`, such as
     `heal_amount` or `armor_duration`. They take the handler's existing inputs (`level`,
     `ch`, …) and `const Rolls &rolls` when they roll. Keep the expression exactly as
     written, replacing only `dice(` with `rolls.dice(` and `number(` with
     `rolls.number(`. Keep operand order, types, casts, and intermediate variables.
   - The handler calls the function, passing `live_rolls`, exactly where the expression
     was. Saves, chance checks, `spell_damage`/heal calls, messages, and every other side
     effect stay in the handler in the same order.
   - Never reorder RNG calls. Do not move a roll across another RNG call or a save, or
     out of a branch it was conditionally in.
   - A clamped damage table moves into the shared function together with its clamp.
   - For the move checker, keep each roll in a plain `return`, and return a magnitude that
     the handler negates rather than `-1 * rolls`.
   - Fixed numbers (durations, modifiers) also become shared functions, so the page and
     the handler read the same value.
   - Handler signatures do not change, so NPC, item, scroll, and wand callers keep
     working.
4. Write `std::string <spell>_facts(P_char ch)` beside the handler (not static):
   - The viewer is the caster. Players cast at `GET_LEVEL(ch)` (`sparser.c` calls
     `spell_pointer)((int)GET_LEVEL(ch), …`) unless the handler derives another level.
   - Ranges: `{ f(lowest_rolls, …), f(highest_rolls, …) }`. This is only exact when the
     value never decreases as any roll increases. Otherwise show the fixed parts or leave
     the number out.
   - Use `fact(label, text)` and `show(Range)`. Use `seconds(pulses)` for pulse durations
     (CharWait, `AFFTYPE_SHORT` affects) and `game_hours(ticks)` for normal
     `af.duration`, which ticks once per game hour; an N-tick affect lasts more than N
     and up to N+1 game hours, and `game_hours()` prints that range (and "permanent"
     for -1).
   - Every line must be at most 79 characters, including the two leading spaces.
   - For damage and healing, say what applies after, and check what the handler and
     `spell_damage` really do. Fireball's page, for example, says whether globes stop it,
     based on its flags.
   - Never show a target's hidden values. A target-dependent number appears only as a
     stated condition ("if the target fails its save") or not at all.
   - Never print a number you have not verified from the code.
   - Match the Fireball and Bash wording style, for example:

     ```text
       Fire damage: 84-504 at your level, 50
       If the target fails its save: 168-1008
       Duration: 25-26 game hours (31.25-32.5 minutes)
       Armor class: -10
     ```
5. Register it:
   - Declare each facts function in `src/abilities/abilities.h` (the facts list).
   - Add `case SPELL_X: return x_facts;` to `ability_facts()` in
     `src/abilities/abilities.c`. Keep your batch's cases together, after the existing
     cases and before `default:`.
   - Remove the constant from `tests/fixtures/ability_coverage_pending.txt`.
   - If several IDs share a handler, give each ID its own case.
6. Test it in `tests/async/test_ability_batch_<N>.py`, modeled on
   `test_ability_framework.py`:
   - Extract (with `extract_function`) the shared and facts functions you added. Compile
     them with `src/abilities/abilities.c`, `src/core/random.c`, and
     `extract_function("utility.c", "int dice(int num, int size)")`, using the same g++
     flags (sanitizers, `-Werror`). Stub only what is needed.
   - For every converted roll, keep the ORIGINAL expression in the test as an oracle.
     Under `randomize(seed)` for 40 seeds and representative levels (such as 1, 10, 30,
     50, 56, 60), assert that the value and the next draw match the shared function with
     `live_rolls`, and that the value lies within the facts range.
   - Assert the exact text of some facts lines, and that building facts leaves the RNG
     untouched.
   - Add source-contract checks (`function_bodies` from `tests/async/_source_contract.py`)
     that each handler calls its shared functions.
   - Extract only your own statics, filtered by name; files like `guild.c` hold unrelated
     ones.
   - Keep the test compact and table-driven where possible.
7. Fix existing tests that your changes break:
   - Find tests that read your touched files and handlers:
     `grep -l '<handler name>\|"<file>.c"' tests/async/test_*.py`.
   - Run them. If a harness extracts a handler you changed, also extract your new static
     functions. If the harness has its own `dice`/`number`, define
     `const Rolls live_rolls = { dice, number };` in its prelude, as is done in
     `test_conjurer_fire_runtime.py` and `test_bash_vitals_knockdown.py`.
   - If the harness has no `dice`, extract the real one from `utility.c` as well.
   - `extract_function` takes the first match of a signature. For a function with a forward
     declaration, end the signature with `"\n{"`.
   - Contract tests slice source text by function name, so moving a helper can break them
     too. Update the slice.
   - Never weaken an assertion.
8. Build and check:
   - `make -C src -j8`. The first build in a fresh worktree takes a while. It must stay
     free of warnings (`-Werror`).
   - Run `./scripts/format.sh` before committing.
   - Run `python3 tests/async/test_ability_coverage.py`, your batch test, and the related
     tests.
9. Reread the diff against the old handler to confirm each move is straight. The commit hook
   also runs clang-tidy.

## Constraints

- Keep changes narrow and follow the nearby style. `.clang-format` is authoritative.
- Use the simplest code, with no new abstractions beyond these functions. Never change
  balance.
- Reuse the helpers in `src/abilities/abilities.{h,c}` before adding one. `show_signed()`, `show_landing()`, `share_percent()`, `game_hours_range()` and
  `innate_rest_facts()` are already there.
- If you find a pre-existing gameplay bug, report it and do not fix it.

## Skills, songs, and instruments

For skills, follow the steps above. Where it says "spell", read "skill, bard
song, or instrument". The differences are below.

### Your list

Each line is: constant, the source file that references it most, `epic` or `-`, and the
name. That file is only a starting point. Find every place the skill's numbers are
computed with `grep -rn '\bSKILL_X\b' src --include=*.c`. A skill has no spell pointer: it
runs through a command (`do_*` in `src/cmd/*`, often with a helper like `bash()`), a
passive check in combat code (`src/combat/fight.c` and friends), or song code
(`src/classes/bard.c`).

### Skill specifics

- The viewer is the user. Numbers usually depend on the viewer's rating
  `GET_CHAR_SKILL(ch, SKILL_X)` and level. Show them for the viewer, as Bash's
  `bash_facts` does with strength and shield.
- Chances against a target are mostly target-dependent:
  - Show a chance only when it is fully determined by the viewer, or as a stated
    condition.
  - Otherwise list the fixed parts (lag, damage, duration) and leave the chance out.
  - Keep "skill rating", "chance threshold", and "success probability" distinct. Never
    call a threshold a probability.
- Lag paths: every `CharWait` on the user that the page mentions must come from a shared
  function the handler calls, and the page must name the condition for each path.
- Passive skills checked on every hit (dodge, parry, riposte, and so on) are hot paths.
  Shared functions there must stay plain arithmetic with no allocation, and facts are
  built only on the info page.
- Epic skills: prerequisites and training costs are out of scope (a later add-on). Convert
  an epic skill only if it has numeric effects; otherwise list it as no-numbers.
- Bard songs and instruments: the song's effect numbers (by level, rating, instrument) are
  the facts. Song tick intervals are pulses, so use `seconds()`.
- Register skills in the same `ability_facts()` switch as spells; skills share the
  spell/skill ID space.
- `CharWait` ignores a shorter wait while a longer one runs, so a lag line is true only if
  it can outlast what is already running. Kick's evade lag, for example, never takes effect.
- `bash_facts` is done. `takedown_sleeping_target_lag()` and `takedown_evade_lag()` in
  `src/cmd/actoff.c` are shared by the takedown skills.
- Numbers spread across files: use a non-static shared function with a local `extern` where
  it is read.

Your test file is `tests/async/test_ability_skills_<N>.py`.

## Innates

For innates, follow the steps above. Where it says "spell", read "innate". The differences
are below.

- Innates are the `INNATE_*` constants plus `HOLY_COMBAT`, `MAGICAL_REDUCTION`,
  `MAGIC_VULNERABILITY` and `TWO_HANDED_SWORD_MASTERY`. Find their numbers with
  `grep -rnw <CONSTANT> src --include=*.c`; most checks go through `has_innate()`.
- Name the function `<innate>_innate_facts`, declare it in `abilities.h`, and add its case
  to `innate_facts()`, not `ability_facts()`. `reflection_innate_facts` in
  `src/classes/innates.c` is the example.
- Active innates: show `innate_rest_facts(INNATE_X, duration)` with the duration the
  handler passes to `check_innate_time()`, and every lag path as for skills. A handler that
  never calls `check_innate_time()` has no rest, so do not show one.
- Spell-backed innates: state the level the handler casts at and add the spell's page with
  `ability_facts(SPELL_X)`. If the handler casts at another level than the viewer's, the
  spell's page would be wrong: show the innate's own numbers instead.
- Passive innates checked in combat or on every affect update are hot paths: plain
  arithmetic, no allocation, facts built only on the info page.
- A pure flag with no number (infravision, a language, a movement permission) goes on the
  no-numbers list.
- The page also opens for viewers without the innate, so a facts function must not assume
  the viewer has it. Racial numbers that depend on the viewer's stats say so.

Your test file is `tests/async/test_ability_innates_<N>.py`.

## What reviews keep finding

Every reviewed batch so far had page lines its author got wrong. Before committing, reread
each page line against its handler and check:

- **Conditions that gate the number:** fear or other saves, immunities (elites, undead,
  angels, already-affected targets), terrain or flight, group-only casts, class or
  specialization refusals. Read every early return in the handler and in the functions it
  calls; `Stun(..., TRUE)`, for example, gives two fear saves.
- **Low levels:** no impossible thresholds ("below level 0") or negative ranges. Test level
  1 and every boundary, and sweep all levels and classes for line width and sanity.
  `show_signed()` shows negative ranges; `show_landing()` shows an amount that deals nothing
  below 1.
- **Whose numbers:** when a number depends on the target rather than the caster, say so,
  even on group and mass pages.
- **No numbers is often wrong:** a fixed level cutoff or fixed chance is a number (identify's
  level 51).
- **Fixed chances:** move the roll verbatim into a roll function and print "1 in N", as
  `spirit_walk_corpse_roll()` does. Watch for off-by-one between `<`, `<=` and thresholds.
- **Units:** decay and event timers are pulses; a normal `af.duration` is ticks. Use
  `seconds()`, `real_time()`, `game_hours()` or `game_hours_range()`, never hand division.
- **Damage stage:** read the actual flags at the `spell_damage` or `melee_damage` call
  (globes, wards, `PHSDAM_NOREDUCE`) and say what stops it.
- **Reachability:** do not show a branch the player's path cannot reach.
- **Tests:** exact whole-line text (no prefixes), source checks that tie each helper to its
  own branch, and a call check that dispatching spells pass the right level.
- **Gameplay bugs:** report them, and never fix them in a conversion. `MIN`/`MAX` macros
  double-roll: preserve that, and note that the page's range may not hold because of it.
- **Absolute claims:** "always" or "whether or not" needs every branch checked.
- **Success-gated lines:** "before your next X", or a lag gated on success, needs "if it works".
- **Rating 0 and empty inputs:** no chance for something the handler refuses, and no list line
  built from nothing.
- **`else if` branches** on the same effect each get their own line.
- **Placement:** insert new helpers above an existing comment, never between a comment and its
  function.
- **No page-only copies:** the handler must call the shared function.
- **Rolls:** every shared roll needs an oracle in the test.
- **Call checks:** scope handler-call checks to the branch or order in multi-path handlers;
  plain substring matches pass with swapped helpers.
- **State changes:** trace callees that change state between a lag or roll and a later check.
- **Saves:** a positive `NewSaves` modifier makes the save harder. Check the direction before
  writing it on a page.
- **Globes:** `damage()` picks globe flags from the spell's lowest circle in `MobSpellIndex`,
  not from flags at the call site.
- **Edge values:** a duration of -1 is permanent and anything else below 1 expires on the next
  tick. A portal throughput of zero or below means no limit.
- **Line width:** keep labels short. `show_landing()` adds 19 characters at low levels.
- **Disabled abilities:** an ability disabled for mortals goes on the no-numbers list, even if
  its handler still has lag code.
- **Passive effects:** they must not stay prose. Move the number and read its property live.
  Leave one pending only if it truly needs restructuring.
- **Search everywhere:** grep the whole `src` tree for each ability's constant. Main effects
  often live in `fight.c`, `dam_mods.c` or `actoff.c`.
- **Verbatim:** a non-verbatim move is a defect even when equivalent, and the checker only sees
  `Rolls` functions. Watch for merged if-chains, literals turned into arrays, and truncating a
  float expression earlier.
- **Properties:** check `lib/duris.properties` and do not state a default as a fact. Pages read
  properties live, and the wording must fit the live value.
- **All rolls:** every roll in the handler counts, including rolls inside caps.
- **Callee rules:** name blocked rooms, resistance groups and fizzle rules from callees such as
  `can_do_general_portal`, `Stun` and `how_close`.
- **Harnesses:** shared functions added to `fight.c`, `dam_mods.c` or `actoff.c` need the
  harnesses that build those files updated.
- **Move checker:** it reports old `VERBATIM?` findings in already-converted code whenever those
  files are in the diff. Compare against a run on your base and chase only new ones.
- **`get_property` overloads:** check which overload a default literal selects before calling
  something a float.
- **Grep flags too:** grep an ability's affect and link flags (`AFF2_PROT_*`, `LNK_ETHEREAL`)
  as well as its constant. A spell's main effect can sit behind the flag alone.
- **Property types:** `get_property(..., double)` returns float, so a `double` helper silently
  changes float arithmetic. Keep the original type.
- **`dam_factor`:** pages can read it directly. Its code fallbacks differ from the live file, so
  check `lib/duris.properties` before wording a line.
- **Parameter substitution:** a page has no mob or event to pass, so a shared function may take
  `mob_level` for `GET_LEVEL(mob)`. The move checker reports these; say so in your report.
- **Item-only spells:** a spell with no `SPELL_ADD` that players reach through an item stays
  converted. A disabled one goes on the no-numbers list.
- **Wider tests:** touching `fight.c` widens the related-test set a lot.
- **Spell damage:** a modifier in `spell_damage_modifiers` only affects spells, so say "spell
  damage" on the page.
- **Fear:** when a page mentions fear, name every `fear_check` immunity.
- **Skin spells:** a spell in `melee_damage`'s skin chain needs the fist of dragon line, as in
  `biofeedback_facts`. A spell spent elsewhere, such as vines in `raw_damage`, says what really
  happens.
- **Added factors:** spell damage adds fire factors together, so never present one alone as the
  final number.
- **Reachable stacking:** only name precedence a player can reach. Check what each handler
  refuses before writing "X applies instead".
- **Stubs:** when a test stub returns fallbacks, also check the key and the `dam_factor`
  assignment, so a wrong property name fails.
- **Object procs:** move the numbers and show them, as with the wall and pond procs. Leave a
  number pending only if moving it needs restructuring.
- **Subtracted rolls:** bound them by pairing, `{ lowest_rolls.dice, highest_rolls.number }`, and
  give the test a matching oracle.
- **Test paths:** `source("spells.c")` resolves to `src/cmd/spells.c`. Use `"magic/spells.c"`.
- **Move checker limits:** it compares within one file, so a cross-file move always shows as
  `VERBATIM?`. Its run on your base only covers the files in that diff.
- **Finding item-only spells:** parse `areas/obj/*.obj` for item types 2, 3, 4 and 10.
- **Refusals:** read every early `return` in a handler and put each reachable refusal on the
  page. `IS_TRUSTED` exceptions count: show them conditionally.
- **Existing helpers:** check the latest base for shared helpers before adding proc numbers.
  Batches keep needing the same wall and skin functions.
- **Harness order:** when a harness extracts `spell_X` before its `abilities.h` block, new
  helpers go above both.
- **`LNKFLG_ROOM`:** it does not mean a link ends on leaving the room. Read `check_room_links`.
- **Forward declarations:** they break `extract_function` and the batch regexes, so move the
  helper up the file instead.
- **Slow journeys:** `tests/run_db_tests.sh` has the arguments and wrappers some tests need.
  `test_flight_network_journey.py` needs about 16 minutes. Run slow journeys one at a time
  when judging failures.
- **Hard-coded examples:** journeys name an unconverted ability (`parry` in the skills journey).
  When you convert it, change the example to a no-numbers ability.
- **Amounts:** when a page says something heals or absorbs, give the amount.
- **Float reductions:** `melee_damage` reduces with floats, so a helper's return type must match
  the original arithmetic.
- **Rating thresholds:** for `rating > number(a, b)`, keep the roll in the handler, print the
  range on the page, and pin the text in the test. `chance_under()` and `one_in()` in `fight.c`
  print fixed chances; the off-by-one between `<`, `<=` and `>=` is the main risk.
- **Source checks:** strip whitespace first, because clang-format rewraps handler lines.
- **Runtime journey:** a batch touching `fight.c` also runs `test_mysql_combat_journey.py`.
- **Related tests:** grep every `tests/async/test_*.py` for each changed source file's name and
  run them all. Harnesses that link a whole file, such as `falling.c`, break on a new page there;
  `-ffunction-sections -Wl,--gc-sections` drops a page they never call.
- **Chance helpers:** `chance_under()` and `one_in()` are in `abilities.h`, so no local `extern`.
- **Pin arithmetic:** for `rating >= number(1, N)`, `chance_under(rating + 1, ...)` gives `rating`
  in N. Check it against the handler's comparison.
- **Double rolls:** `MAX` and `MIN` double rolls can fall below `{ lowest, highest }`, so the
  test needs an allowance for them, and the page says so.
- **Skills with no command:** a skill's only live use can be an object proc (`huntsman_ward` for
  `SKILL_TRAP`) while its command is compiled out.
- **Rating 0:** a skill the handler refuses or that does nothing says "not learned".
- **Short prose numbers:** a short note tied to a single code site ("half", "over 5", "below 15")
  may stay in the page text. Move it into a shared function once a second page or handler needs
  it. Fixed chances and rolls still move.
- **Anonymous namespaces:** `actobj.c` has them, and a non-static helper inside one gives an
  undefined reference at link time. Check before inserting.
- **`function_bodies`:** it can return several bodies for a name, so ordered call checks must
  try each one.
- **Disabled innates:** an innate with no `ADD_*_INNATE` line and no command path that skips
  `has_innate` goes on the no-numbers list.
- **Printed chances:** take `chance_under` bounds from the roll function, as in
  `chance_under(x, roll(lowest_rolls), roll(highest_rolls))`, so the denominator can't drift.
- **Text slices:** check harnesses for slices at `#define` lines, such as `test_shift_prime`.
  `do_shapechange` has an unmatched `}` in a comment, which ends brace-matched extraction early.
- **Effect formulas:** a divisor or multiplier printed in a formula is a number: read it from a
  function the handler also uses. Say whose stat each outcome changes.
- **No-numbers:** before calling an innate a pure flag, read what its checks gate. A flag that
  changes a fixed range, as dayblind's map sight does, has numbers.
- **After a rebase:** re-grep for helpers that now exist upstream.
- **`AFFTYPE_NOSAVE`:** it may only mean the affect isn't saved to the character file, not "no
  saving throw". Check before writing it on a page.
- **Race-gated innates:** a check on race rather than `has_innate`, like leap, applies to whoever
  has the race. Read the check before writing who gets the number.
- **Shared harness helpers:** when many harnesses need the same helpers, use
  `tests/async/_innate_numbers.py`.
