# Character creation stat rolling: Git history

Research completed 2026-10-15 against
`8f36a9a04f48e621b440d261a189eab0836c563d`.
This is a source-history investigation; it changes no gameplay.

The system has alternated between fixed starting attributes, a point-allocation
experiment, constrained random totals, and independent dice rolls. The latest
balance change, on 2026-07-07, narrowed ordinary rolls to **87–90 per attribute**
and removed the reroll step from normal Telnet creation. It did not remove the
WebSocket roll command. Today Telnet grants **four +5 bonuses**, while WebSocket
grants **five**, both capped at 100 per attribute.

## Evidence and scope

- The local repository is not shallow. Its earliest commit is dated 2005-10-09,
  but `src/actwiz.c` and `src/nanny.c` first appear in
  [`be8dd5166`](https://github.com/LuminariMUD/Duris/commit/be8dd5166),
  dated 2009-08-12. Neither file exists in that commit's parent. Earlier creation
  messages establish what was advertised, not the exact implementation.
- Dates below are commit author dates, not verified production deployment dates.
  The investigation follows ancestors of the inspected HEAD, including merged
  branches. In particular, the 2011 point-allocation branch and the 2011–2012
  fixed/random-stat branch coexisted; they are not a single linear rollout.
- Findings come from patches and complete function snapshots, using message
  searches, `git log -G`/`-S`, function history, and ancestry checks. Commit
  messages alone miss substantial changes hidden under titles such as “stuff.”
- “Base” or “raw” stats here mean `base_stats` before creation bonuses, swaps,
  game-entry minimums, and racial/equipment/spell adjustments. The eight ordinary
  attributes are strength, dexterity, agility, constitution, power, intelligence,
  wisdom, and charisma. Luck and karma are tracked separately where their rules
  differed. NPC rolling is included only where it shares the creation function.

## 2005–2010: advertised rerolls, then fixed starting stats

| Date and evidence | Finding |
| --- | --- |
| 2005-10-09 — [`4e5f49ef1`](https://github.com/LuminariMUD/Duris/commit/4e5f49ef1), `lib/creation/reroll` and `bonus` | The initial messages offer rerolling, say total aptitude varies little, and promise four bonus rolls. Only the eight ordinary attributes are listed for bonuses. No roller source is present to establish its formula. |
| 2006-05-16 — [`914ee6ed5`](https://github.com/LuminariMUD/Duris/commit/914ee6ed5) | The messages switch to saying characters start with the same basic attributes; the reroll question disappears and luck becomes a bonus choice. This is evidence of a documented move to fixed starts, without enough source history to date or reconstruct the implementing code. |
| 2009-08-12 — [`be8dd5166`](https://github.com/LuminariMUD/Duris/commit/be8dd5166), `roll_basic_abilities` and creation handlers | The first source snapshot assigns **85 to all ten attributes for Humans**, **75 for other races**. Normal creation goes directly to bonuses. The bonus handler grants four selections of +5, capped at 100; luck is selectable, karma is not. |
| 2010-07-07 — [`c794ca23e`](https://github.com/LuminariMUD/Duris/commit/c794ca23e), despite its unrelated commit title | The Human condition and non-Human branch are disabled: **everyone gets 85** in all ten raw stats. |
| 2010-08-03 — [`137d4c047`](https://github.com/LuminariMUD/Duris/commit/137d4c047) | Raw stats become **75 for everyone**. A separate affect-layer racial bonus is introduced, with `stats.bonus.Human=10`. That implementation initially applies only to Human PCs, adding to current/max ordinary attributes and luck, not karma. The Human benefit has moved out of the roller. |

The 2009 snapshot also preserves two disabled designs:

- A `#if 0` algorithm starts with class minimums (at least 25), chooses a total
  from `totlim` plus dice, and distributes the remainder among eight attributes.
  Luck and karma are assigned separately. Its comments describe a broader system
  than the code actually executes.
- A commented algorithm draws eight values as `70 + number(1,15)` and rejects
  the whole set unless its sum is exactly `8 * 75`.

Neither is an active 2009 creation algorithm. The second does become active in
December 2011. The surviving comment about modifications in July 1994 is useful
provenance, but does not supply a dated Git change or prove the formula used then.

## 2011–2013: two development lines

### Point allocation on the wipe2011 branch

[`577c33603`](https://github.com/LuminariMUD/Duris/commit/577c33603)
(2011-05-16) introduces `select_attrib`, `allocation_total`, and `CON_STATMOD`.
Eight ordinary attributes start at **30**; luck and karma are separately drawn
from **50–100** and hidden from the creation display. Players enter an attribute
and signed amount, then `x` to finish. The display changes from quality labels to
numbers. The initial budget calculation targets a total of 540 across eight
attributes, implying 300 additions above the 240 starting total; the separate
`ALLOCATE_AMT 200` definition is not the authority for that first calculation.
The initial code also contains inconsistencies, including an uninitialized total
and a selection check at 85 while the mutation helper clamps at 80.

| Date and evidence | Development of that system |
| --- | --- |
| 2011-05-22 — [`44e59d712`](https://github.com/LuminariMUD/Duris/commit/44e59d712) | Initializes the total, adds configurable `charcreation.stat.min=30` / `.max=80`, improves allocation validation, requires spending the remaining points before keeping the character, and routes hometown completion into allocation. |
| 2011-05-29 — [`ae9e80f54`](https://github.com/LuminariMUD/Duris/commit/ae9e80f54) | Replaces total-based accounting with a `creation_pnts` balance and `calc_attr_cost`; the allocation pool is now explicitly 200. Raises the configured cap to 100 and introduces intended escalating costs above 75. |
| 2011-06-02 — [`90581b3ea`](https://github.com/LuminariMUD/Duris/commit/90581b3ea) | Fixes the alignment route to enter `CON_STATMOD`. |
| 2011-06-05 — [`a3d6abba5`](https://github.com/LuminariMUD/Duris/commit/a3d6abba5) | Separates PC and NPC starting-stat branches. PCs retain the ordinary-stat base of 30; final luck and karma assignments become `number(50,110)`. Those assignments at the end of the function overwrite earlier values in its PC/NPC branches. |
| 2011-06-11 — [`f3b065c41`](https://github.com/LuminariMUD/Duris/commit/f3b065c41) | Moves point initialization out of the allocation prompt, so redisplaying that prompt no longer resets the balance. |
| 2011-09-22 — [`d67aa2a32`](https://github.com/LuminariMUD/Duris/commit/d67aa2a32) | Repairs negative allocations to refund points and adds a bound on refunds. Makes the allocation pool property-driven, initially with inconsistent `allocation` versus `allocate` key spelling. |
| 2011-12-17 — [`1c46a8dc7`](https://github.com/LuminariMUD/Duris/commit/1c46a8dc7) | Aligns the pool lookup with `char.creation.allocate.amt` and changes that checked-in property from 200 to **320**. |
| 2012-02-17 — [`ef23c1a6e`](https://github.com/LuminariMUD/Duris/commit/ef23c1a6e) | Fixes the allocation-count display by passing an integer rather than the property value's floating-point type to `%d`. |

The advertised escalating costs need a qualification. In `ae9e80f54`, and still
in the later `8a4e33005` snapshot, the cost chain tests `i > 74` **before**
`else if (i > 79)`, `> 84`, `> 89`, and `> 94`. Thus the first branch catches
every high value; the intended 4/8/16/32-point tiers cannot run. The code has a
1/2-point distinction, not the full advertised progression. This is a source
finding, not a claim that the historical implementation was tested here.

### The other line: constrained totals and fixed 80s

The ancestry matters: `577c33603` and `d67aa2a32` are **not** ancestors of the
December 2011 constrained-total change or the October 2012 fixed-stat change.
Both lines later meet in the November 2013 history.

| Date and evidence | Finding |
| --- | --- |
| 2011-12-13 / 12-14 — [`aba65ea17`](https://github.com/LuminariMUD/Duris/commit/aba65ea17), [`bdfabeea7`](https://github.com/LuminariMUD/Duris/commit/bdfabeea7), [`5497450d0`](https://github.com/LuminariMUD/Duris/commit/5497450d0) | Broad backports briefly bring in the 30-point PC base and random luck/karma, revert to fixed 75s, then bring the code back. These rapid changes are another reason not to infer a stable live era from each commit date. |
| 2011-12-14 — [`b8d74f1a0`](https://github.com/LuminariMUD/Duris/commit/b8d74f1a0) | Activates the previously commented **eight 71–85 draws, accept only a total of 600** algorithm. Luck and karma are separately 50–110. This branch's normal creation handlers still advance directly to the four +5 bonuses; internal rejection sampling is not an interactive reroll prompt. |
| 2012-07-18 — [`8a4e33005`](https://github.com/LuminariMUD/Duris/commit/8a4e33005), [`7e2c9a44a`](https://github.com/LuminariMUD/Duris/commit/7e2c9a44a) | Copies the point-allocation creation code into this line and backs it out the same day. The commit sequence does not establish a sustained switch to allocation. |
| 2012-10-18 — [`b99308977`](https://github.com/LuminariMUD/Duris/commit/b99308977), then [`2adb4ba40`](https://github.com/LuminariMUD/Duris/commit/2adb4ba40) | Replaces the eight assigned random values with **85**, then lowers them to **80** about three minutes later. Luck and karma remain 50–110. The rejection-sampling loop remains running even though its ordinary-stat results are discarded. Describing this era only from the first commit would miss the final value of 80. |
| 2012-10-19 — [`c70190367`](https://github.com/LuminariMUD/Duris/commit/c70190367) | Adds a game-entry floor: ordinary base stats and luck below 80 are raised to 80. Karma is excluded. This applies in `enter_game`, so it must be distinguished from what the creation screen rolls and displays. |
| 2013-11-05 — [`7d755817f`](https://github.com/LuminariMUD/Duris/commit/7d755817f), [`8157949c5`](https://github.com/LuminariMUD/Duris/commit/8157949c5) | The branch merge and following `wipe2013` cleanup retain fixed ordinary stats of 80, remove `select_attrib` and its cost calculation, restore the bonus-state dispatcher and descriptive stat display, and restore the bonus helper's 1–100 bounds. |

## 2013–2026: independent rolls, swaps, and reduced randomness

| Date and evidence | Finding |
| --- | --- |
| 2013-11-13 — [`c31eab1d2`](https://github.com/LuminariMUD/Duris/commit/c31eab1d2) | Sets **all ten attributes independently** to `MIN(dice(5,8) + 53, 95)`. The actual range is **58–93**, so the 95 cap has no effect. Removes the unused total-600 loop. Alignment/hometown completion now enters the interactive reroll state; `lib/creation/reroll` stops claiming identical starting attributes. |
| 2013-11-14 — [`b28eb25ea`](https://github.com/LuminariMUD/Duris/commit/b28eb25ea) | Fixes the remaining class-completion route to enter `CON_REROLL`, completing the return of interactive rerolls for the normal Telnet routes. |
| 2014-07-24 — [`81cc6826a`](https://github.com/LuminariMUD/Duris/commit/81cc6826a) | Adds repeated pairwise stat swaps after bonuses and before keeping the character. The eight ordinary stats and luck can be swapped; karma cannot. |
| 2015-10-23 — [`7e43cb78a`](https://github.com/LuminariMUD/Duris/commit/7e43cb78a) | Renames `roll_basic_abilities` to `roll_basic_attributes`; adds explicit `ROLL_BAD`, `ROLL_NORMAL`, and three NPC roll types. Normal PC rolls remain **5d8 + 53**. NPC modes preserve preassigned lower limits; those NPC rules are not new player-creation options. |
| 2016-11-14 — [`5d84adc67`](https://github.com/LuminariMUD/Duris/commit/5d84adc67) | Changes normal rolls to **3d6 + 77**, range **80–95**. This substantially raises the average while narrowing the spread. The earlier game-entry floor no longer raises ordinary normal-roll results. |
| 2017–2025 — formula history and the later snapshots | No intervening change to that normal-roll formula was found in the inspected ancestry. The 2025 WebSocket implementation initially calls the same roller. This is not a claim that all character mechanics or racial balance stayed unchanged. |
| 2025-12-22 — [`8528c61c2`](https://github.com/LuminariMUD/Duris/commit/8528c61c2) | Introduces WebSocket `roll_stats`, `add_bonus`, `swap_stats`, and character creation. Rolls are stored on the descriptor, displayed as quality labels, and supplied with **five** +5 bonuses. This differs from the established four-bonus Telnet path from its introduction. |
| 2025-12-31 — [`3414c5453`](https://github.com/LuminariMUD/Duris/commit/3414c5453) | Colorizes Telnet stat quality labels. It changes presentation, not roll values or bonus count. |
| 2026-06-03 — [`5b7559cf6`](https://github.com/LuminariMUD/Duris/commit/5b7559cf6) | Replaces explicit assignments with an indexed loop over ten attributes. The roller formula is unchanged. However, converting the game-entry minimum to the same ten-attribute loop **adds karma to the 80 floor**; previously only nine attributes were covered. |
| 2026-07-07 — [`5da19f41c`](https://github.com/LuminariMUD/Duris/commit/5da19f41c) | Changes normal rolls to **1d4 + 86**, range **87–90**. All three normal Telnet completion routes now go straight to `CON_BONUS1`. The stated motivation is reducing the incentive to bot repeated rolls for excellent stats. The WebSocket handler is not changed. |
| 2026-09-13 — [`767e66e2b`](https://github.com/LuminariMUD/Duris/commit/767e66e2b) | Changes the prompt for `CON_BONUS5` from “fifth” to “fourth.” The state sequence already awarded four bonuses; this is a prompt correction, not a bonus reduction. |

### What the dice changes mean

These are raw values before bonuses and game-entry adjustments. Ranges and means
were checked by enumerating every possible dice outcome; means assume fair dice.

| Formula | Raw range per attribute | Mean | Relevant qualification |
| --- | --- | --- | --- |
| 5d8 + 53 (November 2013) | 58–93 | 75.5 | The existing entry floor raises ordinary stats and luck below 80 after the creation choices. Karma initially has no such floor. |
| 3d6 + 77 (November 2016) | 80–95 | 87.5 | Naturally rolled excellent values are possible; repeated rolls can improve a set. |
| 1d4 + 86 (July 2026) | 87–90 | 88.5 | Every initial value is “very good”; one +5 bonus makes that attribute 92–95, or “excellent.” |

The 2013 formula does not constrain the total across attributes. The older
class-minimum/total-budget code remains disabled in today's function. Also,
despite an inherited comment rejecting bell curves, summing several dice does
produce a concentrated distribution; it is the **shared total constraint** that
the 2013 implementation drops.

## Current creation behavior and discrepancies

The authoritative code is
[`roll_basic_attributes`](../../src/cmd/actwiz.c),
the selection/bonus/swap handlers in [`nanny.c`](../../src/account/nanny.c), and
the `ws_cmd_*` creation handlers in [`ws_handlers.c`](../../src/net/ws_handlers.c).

| Behavior at the inspected HEAD | Telnet | WebSocket |
| --- | --- | --- |
| Initial stats | Ten separate draws of 87–90 | Same shared roller (`0` is `ROLL_NORMAL`) |
| Display | Quality labels for all ten attributes, with colors | Quality labels for all ten attributes |
| Reroll step | Normal class/alignment/hometown routes bypass `CON_REROLL`; the old handler still exists | Authenticated `roll_stats` requests can be repeated; each replaces the stored stats and resets the bonus counter to five |
| Bonus count | Four: `CON_BONUS1 → CON_BONUS2 → CON_BONUS3 → CON_BONUS5` | Five, tracked by `chargen_bonus_remaining` |
| Bonus amount and targets | +5, capped at 100; eight ordinary stats or luck | Same amount, cap, and targets |
| Bonus applied to a stat already at 100 | Consumes the choice even though clamping prevents an increase | Rejected without decrementing the counter |
| Swaps | Repeatable after bonuses; ordinary stats and luck | Repeatable command for the same nine stats; no equivalent bonus-completion state gate in the handler |
| Karma | Rolled and displayed; cannot receive bonuses or be swapped | Same |

Four and five selections provide up to **20 and 25 added points**, respectively;
clamping can reduce the actual gain. Repeating a WebSocket roll replaces the
previous set and bonuses, so it does not accumulate bonuses on the same set.
The July 2026 Telnet change does not establish a server-wide ban on rerolling.

The current game-entry minimum remains 80 for all ten base stats, including
karma. Fresh 87–90 rolls are already above it. Its historical importance is
larger: in the 2013–2016 period, low creation-screen rolls could be raised on
entry. It is therefore misleading to use the raw roll range alone to describe
the character's eventual stats.

Race and class do not change the current normal raw-roll formula. Racial stat
factors and other modifiers are applied separately by
[`apply_affs`](../../src/magic/affects.c), with racial factors loaded by
[`update_stat_data`](../../src/world/db.c). For example, the 2015-09-14 commit
[`15d90898f`](https://github.com/LuminariMUD/Duris/commit/15d90898f) says Human
“base stats” became 100s, but its relevant edits are `stats.*.Human` properties,
not replacing the creation dice with fixed 100s. A complete history of racial
balance, equipment, and post-creation stat advancement is outside this report.

### Text that no longer describes the implementation

- The roller still has a comment saying normal rolls are 80–95 and an older
  comment saying it assigns static low starting values. The executable branch
  assigns 87–90.
- The bonus handler still describes random 5/10/15-point additions. Its call
  passes exactly 5, and `add_stat_bonus` adds that amount directly.
- Five named bonus states do not mean five Telnet bonuses. `CON_BONUS4` is
  skipped by the ordinary path; the checked-in
  [`bonus` message](../../lib/creation/bonus) correctly says four.
- The [`reroll` message](../../lib/creation/reroll) is still shown even though
  normal Telnet creation skips rerolling. Its legend stops at “very good: 86+,”
  while [`stat_names2`](../../src/cmd/actinf.c) and
  [`STAT_INDEX`](../../src/core/utility.c) distinguish **86–91 very good**,
  **92–100 excellent**, and **101+ quite excellent** for this display.

## Reproducing the investigation

Historical source paths are `src/actwiz.c`, `src/nanny.c`, and
`src/ws_handlers.c`. The August 2026 directory reorganization moved them to
`src/cmd/`, `src/account/`, and `src/net/`. Useful read-only commands:

```bash
git log --follow --format='%h %ad %s' --date=short -- src/account/nanny.c
git log --follow --format='%h %ad %s' --date=short -- lib/creation/reroll
git log --full-history -p -G 'roll_basic_|CON_REROLL|CON_STATMOD|CON_BONUS' -- src/nanny.c src/account/nanny.c
git log --full-history -p -G 'dice\(|totlim|base_stats.Str' -- src/actwiz.c src/cmd/actwiz.c
git show be8dd5166:src/actwiz.c
git show b8d74f1a0:src/actwiz.c
git show 2adb4ba40:src/actwiz.c
git show 8157949c5 -- src/nanny.c
git show 5da19f41c -- src/actwiz.c src/nanny.c
git show 5b7559cf6 -- src/actwiz.c src/nanny.c src/structs.h
git merge-base --is-ancestor 577c33603 b99308977
git merge-base --is-ancestor 577c33603 8157949c5
```

The last two commands return 1 and 0 respectively, demonstrating why the
point-allocation branch cannot simply be inserted into the other line's timeline.
Function-history output was cross-checked against whole snapshots and patches:
renames, merges, commented code, and `#if 0` blocks can otherwise give a misleading
sequence.

Verification for this report consists of source/patch inspection, commit ancestry
checks, dice-range arithmetic, local link checks, and whitespace validation.
No historical binaries were built, no live character was created, and no server
or database was changed. Git establishes the checked-in behavior and stated
intent; it does not prove which version was deployed on a particular date.
