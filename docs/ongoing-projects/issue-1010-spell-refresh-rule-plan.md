# Issue #1010: one refresh rule for buffs, with a generous setting (Vitality first)

Status: plan only; nothing is implemented.
Date: 2026-11-12.
Issue: [#1010](https://github.com/LuminariMUD/Duris/issues/1010).
Related: [#941](https://github.com/LuminariMUD/Duris/issues/941),
[PR #943](https://github.com/LuminariMUD/Duris/pull/943),
[PR #748](https://github.com/LuminariMUD/Duris/pull/748),
[PR #225](https://github.com/LuminariMUD/Duris/pull/225),
[#1028](https://github.com/LuminariMUD/Duris/issues/1028).
Source inspected: `master` at `f8919ad27`.

## Outcome and scope

A cast that lands on a buff the target already has follows one rule, decided
in one place. A gameplay setting makes the weaker case player-favorable. The
code's default is off, the strict rule. The checked-in properties file turns
it on, so the game as shipped is player-favorable.

| The new cast is | Setting off (code default) | Setting on (shipped) |
| --- | --- | --- |
| Stronger than the buff | Buff takes the cast's strength; fresh timer | Same |
| Equal | Fresh timer | Same |
| Weaker | Nothing happens | Fresh timer; the stronger strength stays |

Vitality is the first spell under the rule. Everything that reaches
`spell_vitality()` follows it: spell casts, Miracle, potions drunk or thrown,
the Vitality wand, and item effects that call the spell. Potions are not
special, so the PR #943 quaff guard is removed.

For a level-56 drinker holding power-56 Vitality (+224 hit points):

| Potion | Setting off | Setting on |
| --- | --- | --- |
| Power 22 (vnum 2800) | Consumed; nothing happens | +224 stays; timer back to 14 |
| Power 56 | Timer back to 14 | Same |
| Power 60 | +240; timer back to 14 | Same |

With the setting on, players have what issue #1010 asks for. With it off,
no weak source extends a strong Vitality by any route.

Other spells keep their current hand-written refresh until each is converted.
Tsunami, the Bahamut mask, deity blessings and named-set grants are untouched.
No area file, item flag, schema or migration changes. Staff can turn the
setting off at runtime; deployment itself is a separate task.

## Verified baseline and constraints

- The refresh branch of `spell_vitality()`
  ([magic.c:13255](../../src/magic/magic.c#L13255)) resets the timer of every
  Vitality node and never compares strength. A weaker cast keeps a stronger
  buff running; a stronger cast leaves the target with the weaker buff.
- Strength is `4 * power` hit points in the affect's `modifier`
  (`vitality_hit_points()`). Duration is `vitality_duration()`: for a player,
  `max(10, caster level / 4)` game hours, and a drinker is their own caster.
- Current hit points fall with maximum hit points
  ([affects.c:1046](../../src/magic/affects.c#L1046)), and the recalculation
  kills below -10. Lowering a Vitality in place would wound or kill its
  holder. That is why, with the setting off, a weaker cast does nothing
  instead of downgrading.
- The image, set-grant and deity checks in `spell_vitality()` run before the
  branch. `named_set_ordinary_cast` hides set-granted nodes from it.
- `apply_tsunami_vitality()`
  ([tsunami_actions.c:46](../../src/item/tsunami_actions.c#L46)) already
  raises a weaker Vitality in place: recalculate hit points around the
  modifier change, update position, then push vitals and affects to the
  client.
- The PR #943 guard is at [actoth.c:4966](../../src/cmd/actoth.c#L4966). It
  refuses any potion carrying Vitality when the drinker has Vitality,
  including equal and stronger potions.
- Thrown potions cast on their target as an ordinary spell
  ([actnew.c:4486](../../src/cmd/actnew.c#L4486)). One wand carries Vitality
  (vnum 30662, level 36); no scroll or staff does. Miracle casts Vitality on
  each group member at the caster's level.
- Three places write Vitality without the spell: Tsunami, the Bahamut mask
  ([specs.object.c:3974](../../src/specs/specs.object.c#L3974)) and the dream
  grant ([specs.eth2.c:488](../../src/specs/specs.eth2.c#L488)). The mask can
  lower its wearer's Vitality; that is tracked in #1028.
- Gameplay settings live in the tracked file
  [lib/duris.properties](../../lib/duris.properties) and are read with
  `get_property()` ([properties.c:85](../../src/world/properties.c#L85)).
  On/off settings are written `name.enabled=0.000` under a bracketed section
  line. Staff change them at runtime with `properties set` and keep them with
  `properties save` (Forger).
- [test_epic_gain_runtime.py](../../tests/async/test_epic_gain_runtime.py)
  asserts the quaff refusal across a 96-case matrix.
- [test_named_set_effect_ownership.py](../../tests/async/test_named_set_effect_ownership.py)
  and [test_native_artifact_runtime.py](../../tests/async/test_native_artifact_runtime.py)
  link the real `spell_vitality()`. Both pull `magic.c` functions by
  signature, so a new function the spell calls must be added to those lists.
  The first stubs `get_property()` to return its fallback, and one of its
  cases expects a weak cast to refresh a stronger one.
- `test_ability_batch_2.py` pins two lines of `spell_vitality()`: the
  `healpoints` declaration and the `vitality_duration()` assignment.

## Behavior decisions

1. **One rule, one place.** A small function takes the incoming and existing
   strength and answers replace, renew or nothing. It is the only code that
   reads the setting. Each spell supplies its own two numbers and applies the
   answer itself.
2. **The setting is `spell.generousRefresh.enabled`.** It is on only when its
   value is exactly 1. Missing or any other value is off, so the code's own
   default is the strict rule. The checked-in value is `1.000`.
3. **Replace** (cast at least as strong). When the cast is strictly stronger,
   raise the modifier in place with Tsunami's sequence so hit points are
   recalculated before position is checked. Set the timer as the branch does
   today. Never remove and re-add the affect; that drops hit points.
4. **Renew** (weaker, setting on). Set the timer only. This is today's
   behavior.
5. **Nothing** (weaker, setting off). Leave the affect alone and tell the
   caster `Nothing new seems to happen.`, as the set-grant check does.
6. **The existing checks are unchanged and still run first.** Set grants and
   deity blessings behave as they do now in both modes.
7. **The PR #943 guard and its message are removed in both modes.** A potion
   follows the spell's rule. A potion whose Vitality does nothing is still
   consumed, like any potion whose spell has no effect. A stronger potion now
   upgrades the drinker, which the guard blocked.
8. **Replace and renew keep the existing refresh message.**
9. **The client is told.** After a timer or strength change, push vitals and
   affects as Tsunami does, so the countdown and hit points update.
10. **Persistence is unchanged.** The same saved affect carries a new
    modifier or duration.

## Implementation sequence

### 1. Establish the failing tests

- `tests/async/test_epic_gain_runtime.py`: drop the refusal expectations in
  `check_vitality_quaff`. A drinker with Vitality now quaffs like any other:
  potion consumed, lag and cooldown applied, every slot's spell called, no
  "already affected" text. These fail on this baseline.
- `tests/async/test_named_set_effect_ownership.py`: make its `get_property()`
  stub switchable, then drive the real `spell_vitality()` over setting off
  and on, and casts weaker than, equal to and stronger than an ordinary +224
  on a wounded target. Assert modifier, duration, maximum and current hit
  points, survival and the message for each cell of the first table above.
  No cell may lower current hit points. Add that values 0, 2 and a missing
  key all behave as off. Update the existing weak-cast case and its comment
  to the default outcome.
- Assert the rule function directly for the six combinations.

### 2. Add the rule and the setting

In `src/magic/magic.c`, add the rule function from decision 1 and declare it
in `src/core/prototypes.h`. In `lib/duris.properties`, add a section line that
says what on and off mean, and `spell.generousRefresh.enabled=1.000`.

### 3. Apply it to Vitality

Rewrite only the refresh branch of `spell_vitality()` to act on the rule's
answer per decisions 3 to 5 and 8 to 9. Leave the two pinned lines and every
check above the branch as they are. Add the new function to the extraction
lists in the two harnesses that link the real spell.

### 4. Remove the quaff guard

Delete the loop at `src/cmd/actoth.c:4966`. Nothing replaces it.

### 5. Help

In `lib/information/help_index`, add the rule to `VITALITY (Spell)` (line
19537): a cast at least as strong replaces the Vitality you have; a weaker one
does nothing, unless the realm runs generous refresh, when it resets the timer
and leaves the strength alone. Help states both modes because it cannot know
which is active.

### 6. Qualify

```sh
python3 tests/async/test_epic_gain_runtime.py
python3 tests/async/test_gate_lightning_item_runtime.py
python3 tests/async/test_named_set_effect_ownership.py
python3 tests/async/test_native_artifact_runtime.py
python3 tests/async/test_ability_batch_2.py
python3 tests/async/test_help_layout.py
./scripts/format.sh --check
make -C src
```

Then one local gameplay journey with the `.env` test character on the
freshly built server, in both modes. `properties set` needs Forger; if the
character is below that, change the local `lib/duris.properties` and reload
instead.

- As shipped (on): hold power-56 Vitality, quaff potion 2800. +224 stays and
  the timer is back to full.
- `properties set spell.generousRefresh.enabled 0`, then quaff 2800 again
  after the potion cooldown. The potion is consumed, the message is
  `Nothing new seems to happen.`, and hit points and timer are unchanged.
- In either mode: hold the +88 from potion 2800, receive a power-56 cast, and
  confirm +224 with current hit points raised, not lowered.
- Save, leave and re-enter; strength and timer persist.
- Restore the setting to 1 without `properties save`.

Use no production data. Do not wait on hosted CI.

## Bringing other spells under the rule

Not part of this change. Each later spell is its own small change: choose its
strength measure, call the rule from its existing refresh branch, and add its
cases to a focused test. Where a spell's strength is not one modifier, the
affect's saved `level` field
([structs.h:1210](../../src/core/structs.h#L1210)) can carry the cast power.
Until a spell is converted it behaves as it does today.

## Settled with the owner (2026-11-12)

1. **With the setting off, a weaker cast does nothing.** No mode ever
   downgrades a buff.
2. **The setting's name is `spell.generousRefresh.enabled`.**
3. **The checked-in value is on.** Players get the favorable outcome as
   shipped; the strict rule is the code's default and one `properties set`
   away. At deploy, confirm production's properties file carries the key at
   1 (`properties show spell.generousRefresh`); a file that lacks the key
   runs the strict rule.
4. **Tsunami stays as it is.** On a stronger existing Vitality it keeps the
   strength and sets 15 hours, a deliberate artifact power from PR #225.
5. **The Bahamut mask is not part of this change.** Its own problems are
   tracked in [#1028](https://github.com/LuminariMUD/Duris/issues/1028).

## Review and completion

Review the diff against the ten decisions. Confirm the setting is read in
exactly one place, no path lowers a Vitality in place, the guard and its
message are gone from source and tests, and nothing was added that the
decisions do not need.

Completion needs the focused tests passing, a successful `make -C src`, the
two-mode local journey, accurate help, formatting, and `git diff --check`.
Record the tested commit and any check that could not run. Submit linked to
#1010 and leave the issue open until the implementation lands.
