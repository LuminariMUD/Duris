# October 26 core dump: Frost Beam continues after killing its target

Status: fixed and validated on `fix/frost-beam-lifetime`. Production has not
been changed.

## Implementation follow-up

`spell_frost_beam()` now checks both participants after its damage branches and
returns before the paralysis save/effect if either is dead. The six-line change
preserves damage, shrug selection and the secondary effect for survivors.

The new `tests/async/test_frost_beam_lifetime.py` executes the production spell
and racial lookup under ASan/UBSan, with controlled damage and save boundaries.
All 192 combinations pass: three damage branches, four death/survival outcomes,
PC/NPC caster and target, fighting/idle target, and successful/failed saves.
Checks include the paralysis payload, messaging, combat cleanup, damage amount
and flags. Substituting the unmodified spell from `749e6b39b` reproduces the
null NPC-data access in `tutorial_mobile_mechanics_race()` and fails the test.

The fresh flat-file server build completed without compiler diagnostics. A
disposable socket journey then cast Frost Beam through the real event, damage,
death and extraction paths: a lethal cast left the expected NPC corpse, the
server remained responsive to `look`, and it shut down normally. Six casts at a
durable NPC all survived and the server remained healthy; each target saved, so
that journey did not directly observe paralysis. The deterministic regression
above covers both saving-throw outcomes and verifies the exact paralysis
payload for a surviving target.

A separate default MariaDB build was stopped after 259 of 494 object files when
the shared host exhausted swap while another build was active. It had produced
no compiler diagnostics. The completed flat-file build compiles the same
Frost Beam source with the repository's development warning profile; only the
persistence backend selection differs.

Also passed: `test_critical_attack_lifetime.py`,
`test_issue213_tutorial_combat.py`, `test_spellcast_racial_multiplier.py`, and
`./scripts/format.sh --check`. Test paths are under `tests/async/`.

The investigation record below describes the original crash and the initial
experiment, before this implementation. Its addresses and source line numbers
refer to the crashing executable.

## Finding

`spell_frost_beam()` kills and extracts its NPC target through `spell_damage()`,
then unconditionally calls `NewSaves()` to decide whether to apply paralysis.
The saving-throw path asks for the dead NPC's racial innates and dereferences its
already-freed, null `only.npc` pointer. This causes the production `SIGSEGV`.

The core, incident logs, source lifetime rules, and an isolated executable
experiment agree on this cause. The missing check belongs immediately after
Frost Beam's damage branches, before any saving throw or secondary effect.

## Incident and artifact identity

All times below are UTC on October 26, 2026. Paths are relative to the repository.

| Evidence | Value |
| --- | --- |
| Core | `core.2026.10.26-17.58.14` |
| Core size / modification time | 2,286,964,736 bytes / `17:58:03.276350935` |
| Crashed command / main LWP | `bin/server/dms 7777` / `1114679` |
| Matching executable | `bin/server/dms`, 188,642,248 bytes |
| Executable GNU build ID | `21a28ca92f53477d5e1c26786caf13cd6c041758` |
| Executable SHA-256 | `5f25703fd296725979a771ad10ffb9966dd1facb2cdd9ea8aa36f7326289d127` |
| Checkout inspected | `749e6b39ba52d417e42585d5845a8af18a74c45d` |
| Incident logs | `logs/old-logs/2026.10.26-17.58.14/` |
| Environment / persistence | `production` / `mariadb-primary` |

The build-ID note captured inside the core was read directly from its ELF load
segment and compared with the executable's note: the bytes match exactly.
The captured executable base is `0x5d78bad1e000`; the note is at offset `0x388`,
with the 20-byte ID at offset `0x398`. `bin/server/dms_new` has a different build
ID and was not used for symbolization. The checkout hash identifies the source
examined, not an independently recovered build commit.

The filename's `17:58:14` is the cycle script's archive timestamp;
[`scripts/cycle_mud.sh`](../../scripts/cycle_mud.sh) renames `core` and rotates
logs using `DATESTR`. The kill log and core modification time place the failure
around **17:58:02–03**, before that archival timestamp.

The incident's last logged command is at `cmd.debug:500` (command sequence 919):
`cast 'frost beam' guardian`, in room **9331**, at **17:58:00**.
At **17:58:02**, `exp:19–20` records the group kill and kill experience for
`guardian mage tower [9308]`, level 36, by the level-56 caster. The core retains
the same NPC name, the caster at level 56 in room 9331, and spell ID **679**
(`SPELL_FROST_BEAM`). Player identifiers and unrelated chat are omitted here.

A replacement server process, PID `1206949`, had started at `17:58:16` when
inspected. No restart, live-process attachment, deployment, database write, or
gameplay reproduction was performed during this investigation.

## Core evidence

The crashing thread's stack, abbreviated only below the event loop:

```text
#0  tutorial_mobile_mechanics_race(ch=0x725c3c962980)  specs/specs.ailvio.c:37
#1  innate_char_race(ch=0x725c3c962980)               classes/innates.c:385
#2  innate_unlock_level(ch=..., innate=78)           classes/innates.c:438
#3  has_innate(ch=..., innate=78)                    classes/innates.c:452
#4  NewSaves(ch=..., save_type=0, mod=0)             net/sparser.c:1162
#5  spell_frost_beam(level=56,
        ch=0x725c26724240, victim=0x725c3c962980)     classes/ethermancer.c:176
#6  event_spellcast(...)                            net/sparser.c:3080
#7  ne_events()                                    world/new_events.c:1677
#8  run_event_phase(...)                           net/comm.c:2290
#9  game_loop(...)                                 net/comm.c:2866
```

`SIGSEGV` has `si_code=1` and fault address `0x0`. The instruction at
`0x5d78bb0638e0` is `movslq (%rax),%rax`, with `rax=0`. It reads the NPC's
`R_num` through `only.npc` as part of `GET_VNUM()`.

| Target field in the core | Value / meaning |
| --- | --- |
| `only.npc` | `0x0` |
| `specials.position` | `7`, i.e. `POS_STANDING (3) + STAT_DEAD (4)` |
| `specials.act` | `0x608380e`, still includes `ACT_ISNPC (0x8)` |
| `in_room` | `-1`, i.e. `NOWHERE` |
| `specials.was_in_room` | `9331` |
| `points.hit` | `-11` |
| `runtime_id` | `4730` |
| `player.name` | `guardian mage tower` |

The caster's position is `131` (`POS_STANDING + STAT_NORMAL`), and its room
index `5238` maps to room vnum `9331`. Its specialization is `3`, so this cast
took one of the two non-Frostmagus damage branches. Which random shrug branch
was selected is not recoverable from the optimized locals; both discard the
damage result and reach the same unsafe continuation.

## Why the pointer remains non-null after death

The relevant source sequence is:

1. [`ethermancer.c`](../../src/classes/ethermancer.c), lines 149–176, checks both
   participants at entry, calls `spell_damage()` in one of three branches, and
   then calls `NewSaves(victim, SAVING_PARA, 0)` without checking survival again.
2. [`fight.c`](../../src/combat/fight.c), lines 4399–4400 and 6104–6112, connects
   spell damage to `raw_damage()`, which calls `die(victim, ch)` on lethal damage
   and returns a death result. NPC death calls `extract_char()` at line 2906.
3. [`handler.c`](../../src/world/handler.c), `extract_char()`, removes the
   character from the room and world list, marks it dead, and calls `free_char()`.
4. [`db.c`](../../src/world/db.c), lines 4369–4371, immediately frees and nulls
   `only.npc`. Lines 4430–4431 retain the outer `char_data` allocation until a
   delayed `release_mob_mem` event, ten seconds later. A raw `victim != nullptr`
   check therefore still succeeds after extraction; `IS_ALIVE(victim)` does not.
5. [`sparser.c`](../../src/net/sparser.c), line 1162, checks the Quick Thinking
   innate while resolving the save. [`innates.c`](../../src/classes/innates.c)
   calls `tutorial_mobile_mechanics_race()` for the racial profile. That helper
   reaches `GET_VNUM()` in [`specs.ailvio.c`](../../src/specs/specs.ailvio.c):37;
   [`utils.h`](../../src/core/utils.h):375–379 dereferences `only.npc`.

This is use of an extracted character with freed NPC substorage, manifesting
as a null-pointer dereference. The tutorial helper is used for ordinary NPCs
too; the guardian need not be a tutorial mobile for this path to execute.
Adding a fallback only in the helper would leave Frost Beam able to apply
effects and send messages through a dead character.

The unchecked Frost Beam continuation is present in the April 6 change
`0bae49b7c1` according to `git blame`. The October 24 tutorial change
`2ea317e8d` introduced the current racial-helper lookup path. The latter explains
the visible failure site; this investigation does not establish how the older
build behaved after the same lethal cast.

The October 25 critical-attack fix `365c0e8b9` and its existing
[`test_critical_attack_lifetime.py`](../../tests/async/test_critical_attack_lifetime.py)
address a different caller: continuation after a nested melee hit. This core's
caller is Frost Beam, which that test does not exercise.

## Proposed repair and validation

Add the existing survival check once, after all three `spell_damage()` branches
and immediately before `NewSaves()`:

```cpp
if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
{
    return;
}
```

The deferred outer-character release makes this check valid for the synchronous
continuation shown here. Checking both participants also prevents the secondary
effect after a damage callback kills the caster. Preserve the current damage
calculation, specialization and shrug choices, and paralysis behavior when both
participants survive. The damage result constants in
[`damage.h`](../../src/combat/damage.h) distinguish victim, caster and both-dead
outcomes; checking only `DAM_VICTDEAD` would miss the other outcomes.

An isolated ASan/UBSan experiment was run under the ignored directory
`bin/tests/core-20261026-frost-beam/`. It extracts the actual Frost Beam function
and racial helper, stubs damage to reproduce the observed extraction state, and
routes a stub saving throw through the real helper. Core dumps are disabled for
these child processes.

- The original extracted spell fails with UBSan's
  `member access within null pointer of type 'struct npc_only_data'`, through
  `tutorial_mobile_mechanics_race -> NewSaves -> spell_frost_beam`.
- Six original nonlethal controls pass: successful/failed saves across the
  Frostmagus branch and both non-Frostmagus random branches.
- An extracted copy with the proposed check passes 15 cases: those same three
  damage branches with target death, caster death, both deaths, and surviving
  targets that pass/fail their save. It verifies no save/effect after death and
  unchanged damage flags and effect admission for surviving participants.

This initial experiment proved the continuation defect under controlled
lifetime changes. The implementation follow-up above adds the tracked
regression, builds a fixed server, and executes its lethal damage and extraction
path over a disposable socket session. No fixed binary was deployed. The exact
damage roll and persistence durability of the production incident's final kill
were not determined from this core.

## Repeating the inspection

From the repository root, using the matching executable identified above:

```sh
gdb -nx -batch \
  -iex 'set auto-load off' -iex 'set debuginfod enabled off' \
  -ex 'set pagination off' -ex 'bt 15' -ex 'p $_siginfo' \
  -ex 'p ch->only.npc' -ex 'p ch->specials.position' \
  -ex 'p ch->in_room' -ex 'p ch->points.hit' \
  bin/server/dms core.2026.10.26-17.58.14
```

Local, untracked investigation artifacts are `core.gdb`, `core-evidence.txt`,
`investigate.py`, `original-failure.txt`, and the generated C++ sources/binaries
under `bin/tests/core-20261026-frost-beam/`. The experiment can be repeated with
`python3 bin/tests/core-20261026-frost-beam/investigate.py` while those artifacts
remain available. The essential evidence is recorded above so the write-up does
not depend on retaining them. The original core, executable, and incident logs
were left in place. Existing shared-worktree changes were preserved.
