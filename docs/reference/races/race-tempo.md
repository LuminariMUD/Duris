# PC race tempo: timing, action economy, and sustained output

Source review: 2026-11-08, checkout
`7546d23336e1f60b3b07771a1c39408272666cb5`.
This layer covers **all 37 player-race IDs**, including restricted/legacy races,
and follows their timing settings into recalculation, combat, casting, command
admission, ranged attacks, songs, recovery, cooldowns and expiry. It explains
what a speed advantage actually buys, including cases where it buys nothing.

Values are from checked-in properties and current executable code. They are
not a measurement of deployed settings, obtainable endgame equipment, actual
PvP win rates or server/network latency. No gameplay setting was changed.
Read this alongside [stats](race-stats.md), [size](race-size.md),
[innates](race-innates.md), and their issue companions. Older documents retain
their own source snapshots; current timing code is authoritative here.

Navigation: [clocks](#1-the-clocks-and-what-they-control),
[melee formula](#2-melee-timing-from-properties-to-an-attack),
[all-race melee table](#3-all-player-races-melee-timing),
[casting](#4-casting-effect-time-is-not-next-action-time),
[all-race casting table](#5-all-player-races-casting-timing),
[attacks and control](#6-attacks-per-round-control-and-concurrent-actions),
[archery and songs](#7-archery-songs-movement-and-pets),
[racial powers](#8-innate-timers-and-racial-tempo-interactions),
[recovery](#9-recovery-and-the-time-between-fights),
[worked comparisons](#10-worked-comparisons),
[race implications](#11-what-this-means-for-every-player-race),
[measurement](#12-how-to-use-this-layer-for-balancing),
[verification](#13-verification-and-limits).

## 1. The clocks and what they control

### Units and the main loop

The nominal loop is **4 pulses per second**, or **0.25 seconds per pulse**.
`PULSES_IN_TICK=300` is **75 seconds**. `PULSE_VIOLENCE=16` is a fixed
**4-second constant**, not every character's actual attack interval.
`PULSE_SPELLCAST=9` is **2.25 seconds**, used when registering spell base times.
`WAIT_ROUND=12` is another legacy constant, **3 seconds**. A comment saying
“round” or “tick” does not establish which of these an action uses.
[Constants](../../../src/core/config.h#L75).

The loop's relevant ordering is:

```text
session input -> output -> due events -> activities -> melee combat
             -> advance scheduler tick / ordinary affects -> next loop
```

Each descriptor gets one normal input dispatch opportunity per loop. A command
wait cleared in the event phase normally allows queued input on the **next**
loop. A cast completed in the event phase can, however, stop suppressing an
automatic attack in that same loop's later combat phase. These are different
boundaries. The output phase also precedes those gameplay events, so received
text timestamps need not exactly equal internal effect timestamps.
[Loop](../../../src/net/comm.c#L3033),
[input](../../../src/net/comm.c#L2012),
[combat](../../../src/net/comm.c#L2587).

| Clock/state | Owning mechanism | What racial speed does |
|---|---|---|
| Automatic melee rounds | `base_combat_round`, then `combat_tics` | Racial melee base changes this interval |
| Attacks inside one round | `calculate_attacks()` and later attack-share rules | Stats, anatomy, class and buffs change the payload; pulse alone does not add swings to that payload |
| Ordinary spell preparation/landing | `SpellCastTime()` and segmented `event_spellcast` | Racial casting multiplier changes the initial duration |
| Command recovery | `CharWait()` / `event_wait` / `PLR2_WAIT` | Only changes where the caller derives its wait from a racial timing value |
| Ability reuse | Innate timer or action-specific skill affect | Normally independent of melee/casting pulse |
| Short affect / delayed effect | Absolute event deadline | Usually a fixed pulse duration, independent of racial round |
| Ordinary affect | Character's ordinary affect-update pass | Duration units are 75-second update steps, with update-phase and zero-removal behavior |
| HP/PSP/vitality/ward recovery | Resource events accumulating an elapsed-pulse rate | Racial stats/innates can change the rate; melee pulse is not the regeneration frequency |
| Spell replenishment | Memorization/commune/tupor/assimilation events | Separate formulas and resource-model rules |
| Songs | Bard event cadence | Haste changes song beats; racial casting multiplier does not |
| Archery | Volley count plus command lag | DEX and weapon/skill set the volley; final lag also reads the effective melee round |

### Event timing and ordinary-affect expiry

`add_event()` stores an absolute deadline. A zero-delay event scheduled before
the event pass may run in that pass; one scheduled during/after it waits until
at least the next tick. Positive delays have their own deadlines: the extra
step in the melee countdown must **not** be added to every event duration.
Player casts, waits and resource events receive scheduling priority, but this
does not guarantee a wall-clock deadline under overload. Record nominal pulses
and observed elapsed time separately.
[Scheduler](../../../src/world/new_events.c#L804),
[priority](../../../src/world/new_events.c#L292),
[event-system reference](../EVENTS.md).

For ordinary PC affects, `affect_update()` visits the player at the common
75-second phase. Its code decrements a positive duration; it removes an affect
only on a later pass that starts with duration zero. Thus a newly applied
ordinary duration **N** lasts approximately **N*75 to (N+1)*75 seconds**, depending
on update phase, assuming uninterrupted online updates. For example, duration
5 is approximately **375–450 seconds**, not an exact 375-second timer. A
short affect of 300 pulses instead has a nominal 75-second deadline. This
zero-removal distinction corrects the simpler duration shorthand in older
layers; neither duration label alone establishes exact buff uptime.
[Update ordering](../../../src/magic/affects.c#L4123),
[short-affect creation/expiry](../../../src/magic/affects.c#L2011).

## 2. Melee timing from properties to an attack

### Configuration and identity

`update_damage_data()` reads `damage.pulse.racial.<raceKey>` into
`combat_by_race[race][0]`, defaulting to 16 if absent. It separately loads class
offsets and `damage.pulse.class.all`, whose **committed value is +2**, although
its code fallback is +1. These are additive pulse values, not percentages.

`affect_total()` uses `tutorial_mobile_mechanics_race(ch)`; for ordinary PCs
this follows their stored mechanics race. A disguise's apparent race or a
stat-replacement apply does not automatically substitute another racial pulse
table. Actual race changes and switched/morphed bodies must be evaluated on
the character that executes the action. The tutorial-mobile override is a
separate NPC facility, not a player racial bonus.
[Loader](../../../src/magic/affects.c#L3467),
[recalculation](../../../src/magic/affects.c#L1887),
[race keys](../../../src/core/common.c#L79),
[mechanics-race helper](../../../src/specs/specs.ailvio.c).

For a single-class PC, define:

```text
R = loaded racial melee base
G = global additive melee offset (committed +2)
C = class additive melee offset
P = summed APPLY_COMBAT_PULSE value (negative is faster)

B = R + G + C
A(B) = (0.04/3)*B*B - (1.10/3)*B + 2.73
F = B + P*A(B)
```

Then apply, in this order:

1. Add the Two Daggers bonus when that innate's equipment condition holds
   (**-1 committed**, fallback -3).
2. Multiply by Flurry's melee factor if present (**0.65 committed**, fallback .70).
3. Add the applicable Reaver weapon penalty.
4. Clamp the result to **at least 3.0** and store it as a float in
   `base_combat_round`.

The old direct-AGI speed calculation is commented out. AGI still affects other
mechanics, but raising AGI does not run that retired formula. Haste is also
absent from this interval calculation: its melee benefit comes through attack
count, below. `P=-1` is not one fewer actual scheduler pulse; it subtracts
`A(B)` before the eventual truncation.
[Pulse formula](../../../src/core/utils.h#L1406),
[ordering/floor](../../../src/magic/affects.c#L1965),
[applies](../../../src/magic/affects.c#L1468).

### Class offsets, multiclassing, and weapon penalties

These are the loaded offsets for all 30 class IDs, whether or not the class
is ordinarily available. This table is not a race/class eligibility matrix.

| C | Classes |
|---|---|
| -2 | Ranger, Reaver |
| -1.2 | Monk |
| -1 | Bard, Illusionist, Assassin, Thief, MindFlayer, Dreadlord, Avenger |
| 0 | Warrior, Rogue, Mercenary, Berserker, Ethermancer, Warlock, Alchemist; Dragoon uses the absent-key fallback 0 |
| +1 | Paladin, Anti-Paladin, Cleric, Druid, Shaman, Blighter, Theurgist |
| +2 | Psionicist, Sorcerer, Necromancer, Conjurer, Summoner |

For a multiclass PC, recalculation uses **the smaller of the two class timing
offsets**, not their sum or average. Class damage factors are selected
separately. Having a class also enables its other applicable branches: a
Reaver weapon penalty can still follow the initial multiclass selection.
With committed settings, Ice Reaver adds 0 for a one-handed bludgeon or +1
for a two-handed bludgeon; the one-handed test has precedence. Flame Reaver
adds +1 for qualifying two-handed slashing/flaying. These are post-Flurry
additions, not values fed back into `A(B)`.
[Class loading](../../../src/magic/affects.c#L3495),
[multiclass selection](../../../src/magic/affects.c#L1922),
[Reaver rules](../../../src/classes/reavers.c#L2057),
[creation/class context](../CLASSES.md).

### The actual recurring interval

`perform_violence()` runs once per main-loop pulse. After its initial combat
validity check it performs:

```c
if (ch->specials.combat_tics-- > 0)
    continue;
else
    ch->specials.combat_tics = (int)ch->specials.base_combat_round;
```

For an unchanged, eligible fighter without Whirlwind, the steady interval is:

```text
N = trunc(F)                  # F is positive after the floor
I = N + 1                    # scheduler pulses between recurring rounds
seconds per round = I / 4
rounds per minute = 240 / I   # long-run rate, not an integer encounter count
```

For example, effective F=17 means a round every **18 pulses = 4.5 seconds**.
The minimum F=3 means **4 pulses = 1 second**, not .75 seconds. Values in the
same integer interval produce the same steady melee rate. Small gear changes
can have no immediate effect, while crossing the next boundary matters.
[Countdown](../../../src/combat/fight.c#L11053).

Whirlwind spends its configured vitality on a due round and, while vitality
remains positive, subtracts half the freshly reset **integer** countdown.
The following interval is `ceil(N/2)+1` pulses. It is not exactly half of
`N+1`; when vitality runs out, the shortened reset is not applied. This is a
class/action state, not a universal racial timer.

### Start-up, interruptions, and updates

- The ordinary attack opener resets the relevant countdowns and can execute a
  direct primary hit immediately. That opener is not an extra full recurring
  round. Command entry occurs before combat in the loop, so the first scheduled
  round's phase differs from a counter reset during combat.
- Backstab, anatomy confusion and other control paths can reset a countdown.
  Their delay can erase part of the target's nearly-completed round.
- The counter is reset **before** several later “cannot attack” checks, including
  casting without Battlemage, certain holds/paralysis and an active item action.
  A suppressed opportunity is generally lost; it is not banked for release.
  Initial combat-invalid paths can instead exit before decrementing.
- `CharWait()` alone is not the PC automatic-attack gate. A character can retain
  ordinary attacks while its commands are lagged; casting/immobility/etc. have
  their own checks. NPC `MobCombat()` separately requires `CAN_ACT`.
- Recalculation changes the next reset value, not an already-running
  `combat_tics`. `balance_affects()` schedules a zero-delay recalculation, so
  event phase and current round phase affect when a new bonus is felt.

[Opener](../../../src/cmd/actoff.c#L8183),
[anatomy reset](../../../src/combat/fight.c#L7455),
[suppression](../../../src/combat/fight.c#L11053),
[recalculation scheduling](../../../src/magic/affects.c#L522).

## 3. All player races: melee timing

The table uses a **class-neutral C=0 fixture**, committed G=2, no Two Daggers,
Flurry or Reaver weapon penalty, and no active timing innate unless represented
by P. It isolates race timing; it does not assert every restricted race can
create a Warrior. Actual attacks per round and damage are deliberately held
outside these columns.

`O` = ordinary creation; `R` = restricted/legacy under committed creation
policy. `I0/I-1/I-5` are actual recurring intervals in **seconds**, after the
integer countdown. `Rounds/60s` is the integer count **after** a recurring round
has just happened at time zero, excluding that round and including events
through second 60. This prevents the opening-hit phase from being hidden.

| ID | Race | Creation | R (pulses) | F at P=0 | I0 (s) | I-1 (s) | I-5 (s) | Rounds/60s at P=0 |
|---|---|---|---|---|---|---|---|---|
| 1 | Human | O | 15 | 17 | 4.5 | 4.25 | 4 | 13 |
| 2 | Barbarian | O | 18.25 | 20.25 | 5.25 | 5 | 4.25 | 11 |
| 3 | Drow Elf | O | 13.5 | 15.5 | 4 | 4 | 3.75 | 15 |
| 4 | Grey Elf | O | 13.5 | 15.5 | 4 | 4 | 3.75 | 15 |
| 5 | Mountain Dwarf | O | 17 | 19 | 5 | 4.75 | 4.25 | 12 |
| 6 | Duergar Dwarf | O | 17 | 19 | 5 | 4.75 | 4.25 | 12 |
| 7 | Halfling | O | 12.5 | 14.5 | 3.75 | 3.75 | 3.5 | 16 |
| 8 | Gnome | O | 11.5 | 13.5 | 3.5 | 3.5 | 3.25 | 17 |
| 9 | Ogre | O | 19 | 21 | 5.5 | 5.25 | 4.25 | 10 |
| 10 | Troll | O | 18.25 | 20.25 | 5.25 | 5 | 4.25 | 11 |
| 11 | Half-Elf | R | 14 | 16 | 4.25 | 4 | 3.75 | 14 |
| 12 | Illithid | R | 15.5 | 17.5 | 4.5 | 4.5 | 4 | 13 |
| 13 | Orc | O | 15 | 17 | 4.5 | 4.25 | 4 | 13 |
| 14 | Thri-Kreen | O | 17.5 | 19.5 | 5 | 4.75 | 4.25 | 12 |
| 15 | Centaur | O | 15.5 | 17.5 | 4.5 | 4.5 | 4 | 13 |
| 16 | Githyanki | O | 15 | 17 | 4.5 | 4.25 | 4 | 13 |
| 17 | Minotaur | O | 18.5 | 20.5 | 5.25 | 5 | 4.25 | 11 |
| 18 | Shade | R | 15 | 17 | 4.5 | 4.25 | 4 | 13 |
| 19 | Revenant | R | 16.4 | 18.4 | 4.75 | 4.5 | 4 | 12 |
| 20 | Goblin | O | 12 | 14 | 3.75 | 3.5 | 3.25 | 16 |
| 21 | Lich | R | 12 | 14 | 3.75 | 3.5 | 3.25 | 16 |
| 22 | Vampire | R | 13 | 15 | 4 | 3.75 | 3.5 | 15 |
| 23 | Death Knight | R | 14 | 16 | 4.25 | 4 | 3.75 | 14 |
| 24 | Shadow Beast | R | 12 | 14 | 3.75 | 3.5 | 3.25 | 16 |
| 25 | Storm Giant | R | 14.5 | 16.5 | 4.25 | 4.25 | 3.75 | 14 |
| 26 | Wight | R | 15.5 | 17.5 | 4.5 | 4.5 | 4 | 13 |
| 27 | Phantom | R | 14 | 16 | 4.25 | 4 | 3.75 | 14 |
| 28 | Harpy | R | 12 | 14 | 3.75 | 3.5 | 3.25 | 16 |
| 29 | Orog | R | 15 | 17 | 4.5 | 4.25 | 4 | 13 |
| 30 | Githzerai | O | 15 | 17 | 4.5 | 4.25 | 4 | 13 |
| 31 | Drider | O | 13.5 | 15.5 | 4 | 4 | 3.75 | 15 |
| 32 | Kobold | O | 10 | 12 | 3.25 | 3 | 2.75 | 18 |
| 33 | Planetbound Illithid | R | 14 | 16 | 4.25 | 4 | 3.75 | 14 |
| 34 | Kuo Toa | R | 15 | 17 | 4.5 | 4.25 | 4 | 13 |
| 35 | Wood Elf | R | 14 | 16 | 4.25 | 4 | 3.75 | 14 |
| 36 | Firbolg | O | 19 | 21 | 5.5 | 5.25 | 4.25 | 10 |
| 37 | Tiefling | O | 14 | 16 | 4.25 | 4 | 3.75 | 14 |

The values above came from the production table loaders and recalculation
excerpt executed with real engine types; the countdown was independently
exercised. All 37 rows use their source `no_spaces` property keys. Original
Illithid and Planetbound Illithid (`Pillithid`) are separate. PC Vampire uses
the `Vampire` timing key also used by the NPC race; this differs from the
special PC-only shrug key described in the innate layer.
[Properties](../../../lib/duris.properties#L432),
[PC names](../../../src/core/common.c#L79),
[creation availability](../../../lib/creation_availability.cfg).

## 4. Casting: effect time is not next-action time

### The shared racial calculation

`update_spellpulse_data()` loads `spellcast.pulse.racial.<raceKey>` as a float,
defaulting to 1.0. `SpellCastTime()` then runs the following stages, assigning
back to an integer after **each** multiplication:

```text
d = registered spell beats
d = trunc(d * racial casting factor)
d = trunc(d * global casting factor)       # committed All = 1.0
d = trunc(d * (1 + 0.03 * spell_pulse))
if Flurry: d = trunc(d * 0.30)
else if Haste: d = trunc(d * 0.80)
D = max(1, d)
```

Negative `APPLY_SPELL_PULSE` is faster. `-1` removes 0.03 from the pulse
multiplier, not .25 seconds or 3% of every final action cycle. Flurry replaces
Haste in this branch; they are not multiplied together. There is **no direct
Slow multiplier in this function**. Slow affects other systems, including
input polling and attack count. Spell registrations matter: Magic Missile
has 6 base pulses, Armor 9, Fireball 14 and Full Heal 18 in this checkout.
[Function](../../../src/net/sparser.c#L995),
[load](../../../src/net/sparser.c#L3485),
[registrations](../../../src/classes/skills.c#L743).

The global `spellcast.pulse.racial.All` is currently a multiplier; old additive
interpretations do not apply. Floating-point properties and intermediate
truncations are part of the executed behavior. Use the production function
for boundary comparisons, rather than multiplying decimal percentages once
and rounding at the end.

Both pulse applies accumulate from eligible equipment and affects through
`affect_modify()`. The old stepwise compression switches in `apply_affs()` are
commented out: current totals are assigned directly. If the CTF build path is
enabled, a qualifying CTF bonus separately divides both stored apply totals by
1.5 with integer conversion; that is outside the ordinary fixtures here.
[Aggregation](../../../src/magic/affects.c#L1465),
[direct totals](../../../src/magic/affects.c#L1110),
[conditional CTF adjustment](../../../src/magic/affects.c#L1812).

### Command path and timing transformations

Let `D` be the value above, `W` the initial command wait, and `T` the requested
cast duration after the command-specific branches. The following describes
successful admission; failed targeting, resource or interruption checks can
end the action earlier while retaining a wait.

| Path | Initial wait W | Requested effect duration T |
|---|---|---|
| Ordinary `cast`, no special branch | D | D |
| Successful Quick Chant afterward | Already-established W | `floor(previous T/2)` |
| Single-class Druid, ordinary branch | `floor(D/2)+6` | `floor(D/2)` through the automatic quick-cast branch |
| Single-class Blighter, ordinary branch | D | `floor(D/2)` |
| Successful Totemic Mastery / Nature's Sanctity / Nature's Ruin | `floor(.75D)` | Same initially; later quick-cast branch may halve it |
| Berserk cast branch | `floor(D * configured factor)`, committed factor **1.0**, fallback 1.5 | Same initially; this branch is after the earlier class/epic branches |
| `will`, no Spatial Focus proc | `floor(D/2)` | `floor(D/2)` |
| Chant Mastery best / Spatial Focus best | 1 | 1 |
| Chant Mastery good / Spatial Focus good | Half the duration entering that mastery | 1 |
| Chant Mastery fair / Spatial Focus fair | `floor(.8 * entering duration)` | `floor(.6 * entering duration)` |
| Chant Mastery low / Spatial Focus low | Full entering duration | `floor(.8 * entering duration)` |

Chant Mastery is the first branch of the `cast` preparation chain whenever
the skill is owned; even its failed proc selects that branch, rather than
falling through to every other epic. Its result then still passes through the
later Quick Chant/class shortening stage. Spatial Focus operates on the
already-halved `will` duration. These choices are not independent percentage
bonuses that always stack.

`will` is available by the resource model, including original and Planetbound
Illithid racial users. This is separate from the racial **Blast innate**, which
directly invokes its own spell handler. Original Illithid's factor .025 often
hits the one-pulse shared-function floor; `will` can subsequently halve 1 to
0, but the event path still schedules at least one pulse.
[Cast chain](../../../src/net/sparser.c#L2828),
[will](../../../src/net/sparser.c#L2265),
[mastery](../../../src/classes/epic_skills.c#L1295),
[resource-model selection](../../../src/core/utils.h#L974).

### Landing, post-cast recovery, and repeat rate

Ordinary casts/wills are scheduled in segments of at most four pulses. A
successful, uninterrupted cast lands at nominal **`max(1,T)` pulses**. It does
not acquire an extra pulse for every segment. `schedule_spellcast()` anchors
later segments to their intended deadlines, shortening subsequent delays after
lateness where possible. Scheduler overload can still delay completion; it
does not make a spell land before its intended deadline.

On the ordinary successful completion tail, the code calls
`CharWait(ch, PULSE_SPELLCAST/2)`: **4 pulses = 1 second**. An invoked spell can
add other waits or change the character's state, and earlier returns need not
reach that tail. For an otherwise plain successful action:

```text
C = max(1,T)                        # effect time
gate ready = max(W, C + 4)          # CharWait retains the longer remaining wait
next normal queued input = gate ready + 1 pulse
```

The last +1 comes from input preceding the event phase. It is an ideal
continuously queued, unslowed descriptor calculation, not network latency or
a universal promise for every spell. In particular, Quick Chant can reduce
the interruption window without halving the time until another cast starts.
There is also a difference between casting a prepared spell and releasing a
previously woven spell: the latter takes its immediate branch before the
ordinary preparation calculation. Its normal completion tail still requests
the one-second recovery; “instant effect” does not mean “no command recovery.”
[Segments](../../../src/net/sparser.c#L1386),
[continuations](../../../src/net/sparser.c#L3069),
[completion recovery](../../../src/net/sparser.c#L3449),
[wait semantics](../../../src/world/events.c#L372).

`CharWait()` compares the new delay to the **remaining** existing wait. A
shorter request does not shorten it, and a longer request replaces it from
now; waits are not blindly added. Manual `abort` cancels the cast and its
existing wait, then requests **16 pulses = 4 seconds**. Generic `StopCasting`
does not perform that same wait reset. A cancelled effect therefore does not
necessarily mean the actor is immediately free to act.
[Abort variants](../../../src/net/sparser.c#L1371).

The input loop also repairs a wait bit whose event is missing or has exceeded
its safety deadline. That deadline is the accepted event deadline plus eight
pulses (2s) of grace. The grace is a recovery safeguard, not an extra two seconds
added to every ordinary action.
[Gate repair](../../../src/net/comm.c#L1627),
[deadline publication](../../../src/world/events.c#L435).

While casting, the whitelist allows petition/return and enabled abort through
a separate queue gate; other commands remain type-ahead. Non-Monk Slow skips
alternate normal session-input pulses, adding another scheduling constraint. Consequently a
one-pulse cast is not permission to send unlimited actions between loop passes.
[Input gate](../../../src/net/comm.c#L1642),
[Slow polling](../../../src/net/comm.c#L2189),
[casting queue policy](../../../src/cmd/interp.c#L1676).

## 5. All player races: casting timing

All result columns are **pulses**, not seconds; divide by four. They execute
`SpellCastTime()` with global multiplier 1.0 and no class/command mastery.
`D6/D14/D18` use the registered base durations of Magic Missile/Fireball/Full
Heal. This is a timing fixture, **not a claim every race/class can cast those
spells**. `D18 -1` adds one negative spell-pulse apply; `D18 Haste` applies
Haste without that apply. The final column is the ideal ordinary non-Quick-Chant
repeat start interval `D18+5`, subject to the conditions above. Both Illithid
races normally route through `will`, so their ordinary-cast column must not
be mistaken for their actual `will` cycle.

| ID | Race | Racial factor | D6 | D14 | D18 | D18 -1 | D18 Haste | Plain D18 repeat-start pulses |
|---|---|---|---|---|---|---|---|---|
| 1 | Human | 1.000 | 6 | 14 | 18 | 17 | 14 | 23 |
| 2 | Barbarian | 1.220 | 7 | 17 | 21 | 20 | 16 | 26 |
| 3 | Drow Elf | 0.820 | 4 | 11 | 14 | 13 | 11 | 19 |
| 4 | Grey Elf | 0.820 | 4 | 11 | 14 | 13 | 11 | 19 |
| 5 | Mountain Dwarf | 0.850 | 5 | 11 | 15 | 14 | 12 | 20 |
| 6 | Duergar Dwarf | 0.850 | 5 | 11 | 15 | 14 | 12 | 20 |
| 7 | Halfling | 0.730 | 4 | 10 | 13 | 12 | 10 | 18 |
| 8 | Gnome | 0.700 | 4 | 9 | 12 | 11 | 9 | 17 |
| 9 | Ogre | 1.310 | 7 | 18 | 23 | 22 | 18 | 28 |
| 10 | Troll | 1.220 | 7 | 17 | 21 | 20 | 16 | 26 |
| 11 | Half-Elf | 0.900 | 5 | 12 | 16 | 15 | 12 | 21 |
| 12 | Illithid | 0.025 | 1 | 1 | 1 | 1 | 1 | 6 |
| 13 | Orc | 1.000 | 6 | 14 | 18 | 17 | 14 | 23 |
| 14 | Thri-Kreen | 1.000 | 6 | 14 | 18 | 17 | 14 | 23 |
| 15 | Centaur | 1.090 | 6 | 15 | 19 | 18 | 15 | 24 |
| 16 | Githyanki | 0.850 | 5 | 11 | 15 | 14 | 12 | 20 |
| 17 | Minotaur | 1.150 | 6 | 16 | 20 | 19 | 16 | 25 |
| 18 | Shade | 0.700 | 4 | 9 | 12 | 11 | 9 | 17 |
| 19 | Revenant | 1.300 | 7 | 18 | 23 | 22 | 18 | 28 |
| 20 | Goblin | 0.730 | 4 | 10 | 13 | 12 | 10 | 18 |
| 21 | Lich | 0.550 | 3 | 7 | 9 | 8 | 7 | 14 |
| 22 | Vampire | 0.800 | 4 | 11 | 14 | 13 | 11 | 19 |
| 23 | Death Knight | 1.500 | 9 | 21 | 27 | 26 | 21 | 32 |
| 24 | Shadow Beast | 1.100 | 6 | 15 | 19 | 18 | 15 | 24 |
| 25 | Storm Giant | 1.600 | 9 | 22 | 28 | 27 | 22 | 33 |
| 26 | Wight | 1.900 | 11 | 26 | 34 | 32 | 27 | 39 |
| 27 | Phantom | 0.700 | 4 | 9 | 12 | 11 | 9 | 17 |
| 28 | Harpy | 0.700 | 4 | 9 | 12 | 11 | 9 | 17 |
| 29 | Orog | 1.600 | 9 | 22 | 28 | 27 | 22 | 33 |
| 30 | Githzerai | 0.850 | 5 | 11 | 15 | 14 | 12 | 20 |
| 31 | Drider | 1.090 | 6 | 15 | 19 | 18 | 15 | 24 |
| 32 | Kobold | 0.700 | 4 | 9 | 12 | 11 | 9 | 17 |
| 33 | Planetbound Illithid | 0.750 | 4 | 10 | 13 | 12 | 10 | 18 |
| 34 | Kuo Toa | 1.100 | 6 | 15 | 19 | 18 | 15 | 24 |
| 35 | Wood Elf | 0.950 | 5 | 13 | 17 | 16 | 13 | 22 |
| 36 | Firbolg | 1.310 | 7 | 18 | 23 | 22 | 18 | 28 |
| 37 | Tiefling | 0.875 | 5 | 12 | 15 | 14 | 12 | 20 |

Several different factors produce the same short-spell duration. For example,
the .70 and .73 groups both produce 4 pulses from a 6-pulse base, while an
18-pulse base separates them into 12 versus 13. The original Illithid's .025
is a checked-in value, not the Planetbound .750 value and not an inferred typo.
Its one-pulse floor and post-cast recovery dominate short-spell tempo.
[Casting properties](../../../lib/duris.properties#L620).

## 6. Attacks per round, control, and concurrent actions

### Frequency and payload are different multipliers

A useful first approximation for eligible ordinary melee is:

```text
attempts/second = E[executed attacks per round] * 4/I
damage/second  = attempts/second * E[damage per attempted attack]
```

The second expectation includes misses/defenses and the applicable damage
pipeline. Do not multiply by hit chance again if the measured per-attempt
damage already includes misses. Proc eligibility, weapon slots, target deaths,
movement and interruption can make the simple product insufficient.

`calculate_attacks()` builds an ordered slot list. Key sources of racial
interaction are:

- Non-Monks ordinarily start with one primary attack unless Slow suppresses
  that branch; Haste satisfies its admission and adds a separate primary
  attack when not also slowed. Slow is **not** simply a slower melee timer.
- Dual wield, improved two-weapon and double/triple/quadruple attacks add
  separately gated opportunities. Their strict/non-strict comparisons and
  skill-notching branches mean “skill 100” is not interchangeable across rolls.
- Native **Thri-Kreen** has four hands. Equipped third/fourth weapons receive
  additional rolls alongside several primary/secondary grants. Drider's
  Spider Body does **not** make it a four-handed race. Four arms is another
  possible source of the anatomy bit.
- DEX can add primary/secondary attacks at weapon-weight/STR and DEX thresholds.
  The live branch accepts null weapons despite the old “not bare hands” comment.
  STR can thus improve attack count through weapon-weight admission as well as
  damage, and racial DEX can cross a discontinuous attack threshold.
- Monk base attacks use `MonkNumberOfAttacks()`, then the per-item half-equipped
  weight penalty relative to STR. Slow halves that base count when above one.
  PvP pressure-point replacements and later bonuses prevent equating each
  resulting slot with the same ordinary hit.
- Blur and class/spell packages add attacks through later branches. Base pulse
  differences multiply their eligible frequency too. Old direct Gnome/Kobold,
  Goblin/Halfling and Minotaur extra-attack blocks are commented out.

Afterward, a non-standing character without Groundfighting loses `floor(n/3)`
attacks when kneeling or `floor(n/2)` when sitting/prone. This preserves
`n-floor(n/k)`, not a floating-point percentage. Barbarian and Drider unlock
Groundfighting at 21; Troll no longer owns it. Their surviving attack list
then faces the separate inertial-barrier/armlock/intercept share and Combat Mind
floor, with `ceil(count * share)` at that later stage.
[Attack builder](../../../src/combat/fight.c#L10445),
[four hands](../../../src/core/utils.h#L951),
[DEX branches](../../../src/combat/fight.c#L10740),
[posture](../../../src/combat/fight.c#L10961),
[execution share](../../../src/combat/fight.c#L11123).

### Control changes delivered actions, not just average stats

Posture, command lag, stun, paralysis, casting and ability cooldown are distinct.
A 12-second command wait does not by itself prove three lost four-second attack
rounds. A knockdown may cut the attack count without stopping its clock; a
casting state can consume a due round without executing it; a timer reset can
delay a nearly-ready attack. Save/immunity and body-size admission from the
other layers decide whether the control occurs at all.

Shortening a cast can restore melee eligibility before a due opportunity,
giving a discrete extra round rather than a smooth percentage improvement.
If the opportunity was already consumed during casting, finishing immediately
afterward does not refund it. Conversely, Battlemage changes this interaction
by allowing the casting-state exception. The experiment must record both
cast completion and the melee round phase.

Faster attack tempo also changes how often eligible Battle Frenzy, touch vamp,
weapon procs and defensive reactions are tested. It can increase incoming
retaliation as well as outgoing damage. Per-hit, per-round and fixed-time procs
must be counted separately; no general “all procs scale with haste” rule exists.
Pet attacks remain on the pet's own action clocks.
[Combat suppression](../../../src/combat/fight.c#L11108),
[per-attack defense resolution](../../../src/combat/fight.c#L11432),
[racial proc/healing context](race-innates.md#6-offensive-passives-weapon-choices-and-group-scaling).

## 7. Archery, songs, movement, and pets

### Archery: racial melee timing also affects a command action

The main bow/crossbow firing path first computes a speed score:

```text
speed = min(weapon speed, trunc(1.5 * DEX), 2 * archery skill)
add +20 for Haste and +20 for Blur
add applicable Sharpshooter bonuses
subtract 60 while fighting
speed = max(speed, speedPerShot)
shots = floor(speed / speedPerShot)          # committed speedPerShot = 40
```

The arrows are processed in the command's volley; their count is not a sequence
of independently scheduled racial melee rounds. Ammunition, death and other
exits can end the volley early. After the loop, its processed-loop count `i`
determines the wait:

```text
delay = i / 3.0                            # committed per-arrow divisor
if still hidden: delay *= 2.4
if the fighting-shot check succeeded: delay *= 1.4
lag = trunc(4 + delay * trunc(F))           # pulses, passed to CharWait
```

Thus racial DEX can improve arrows per volley, while racial melee speed can
reduce recovery between volleys. Unlike ordinary recurring melee, this formula
uses `trunc(F)` **without** the extra countdown step. Increasing speed across
an arrow-count boundary changes both payload and lag. Arrow defenses and
`PHSDAM_NOSHIELDS` also differ from ordinary melee retaliation; do not treat
the volley as identical weapon swings.
[Volley calculation](../../../src/combat/range.c#L778),
[lag](../../../src/combat/range.c#L1300),
[properties](../../../lib/duris.properties#L2441).

### Songs

The first ordinary song beat is scheduled after `get_bard_pulse()`; subsequent
beats rearm with its then-current value. The period is **35 pulses = 8.75s**,
or **25 pulses = 6.25s with Haste**. The “15 sec” constant comment is obsolete.
Neither racial cast factor nor `APPLY_SPELL_PULSE` is read by this cadence.
Haste increases beat rate by **40%**, while also exhausting a fixed verse
count sooner. An already-scheduled beat is not automatically rescheduled by
changing Haste; the new value affects later scheduling.

Singing has its own instrument, silence, posture, success and maintenance
conditions. A fast-casting race does not automatically sing faster. It may
still cast other spells or perform melee differently when its build allows it.
Echo is a separate delayed effect, scheduled at integer `bardPulse/6` after
an eligible beat, not a second racial casting roll.
[Cadence](../../../src/classes/bard.c#L60),
[first beat](../../../src/classes/bard.c#L2897),
[rearm/verses](../../../src/classes/bard.c#L2687),
[echo](../../../src/classes/bard.c#L2514).

### Item activation and passive item effects

The shared item-action runtime has its own windup and activity state. It clamps
the selected definition's windup between the configured reaction and maximum
windows; it does not call `SpellCastTime()` or use racial melee timing to set
that window. Active admission rejects an existing active item action, ordinary
casting or command wait. While active, its separate input/melee gate applies;
abort does not erase an unrelated command wait. Passive actions do not enter
that active gate and do not stop melee merely by being scheduled.

**Committed master/device switches are off.** The opt-in wand/staff/scroll
categories have an 8-pulse windup setting, subject to shared bounds. Their
reaction-window machinery also guards a minimum monotonic elapsed time under
scheduler catch-up. These are conditional device timings, not a universal
two-second penalty on every currently used potion, scroll, weapon proc or
wand. Disabled/unselected routes retain their legacy handlers and costs.
Record which route was active when measuring a build that relies on items.
[Active scheduling](../../../src/item/item_actions.c#L510),
[item-action contract](../ITEM_ACTIONS.md),
[device routing](../DEVICE_ACTIONS.md),
[committed switches](../../../lib/duris.properties#L2).

### Movement, fixed-duration actions, and summons

Ordinary movement does not read `base_combat_round` or the racial casting table.
Its availability is constrained by input/command waits, movement admission,
terrain, mounts and vitality. Flight, levitation, size, breathing and sneak
change route access/cost/exposure; they should not be mislabeled a racial melee
pulse bonus. Special movement actions can impose their own fixed waits.
[Movement](../../../src/cmd/actmove.c),
[movement cost](../../../src/core/utility.c#L2628),
[size/travel layer](race-size.md#6-movement-information-tracking-and-recovery).

Circle and Flank are notable direct consumers of the melee round: their
duration is `(attacked ? 1 : 3) * (trunc(F)+1)` pulses. Faster round timing
also shortens that buff window in seconds. This need not reduce the number of
covered personal rounds, but it can matter for command timing and allies.
[Circle](../../../src/cmd/actoff.c#L2128),
[Flank](../../../src/cmd/actoff.c#L12598).

Summon arrival delay, pet control duration, pet attack cadence and eventual
despawn are four separate clocks. An Orc calling Horde/Warg does not transfer
its racial melee interval to every follower. Likewise Reflection's immediate
retargeting effect and the images' later attacks are different contributions.
Include owner and pet outcomes without counting the pet twice.
[Summon mechanics](race-innates.md#9-summons-images-equipment-and-economy),
[pet control](../../../src/classes/necromancy.c#L251).

## 8. Innate timers and racial tempo interactions

### The general rest is independent of pulse gear

`check_innate_time()` normally grants one use and starts a **720-second** timer.
It stores `TAG_INNATE_TIMER` as a short hidden nondispellable non-applying affect.
A supplied duration overrides the per-innate property. With configured multiple
uses, all uses recharge when the **first** timer expires, not individually after
each activation. Timer state is distinct from actor lag and effect duration.

These timers do not scale with racial melee/casting values or pulse equipment.
The helper uses seconds converted by `WAIT_SEC`; the Hatred watcher is a
different property interpreted directly as pulses. Generic timers are saved
and do not opt into offline advancement. Changing race is not a universal
reset of cooldowns, active affects, pets or summoned equipment.
[Timer creation](../../../src/classes/innates.c#L1229),
[duration/uses](../../../src/classes/innates.c#L1118),
[persistence context](race-innates.md#12-lifecycle-boundaries-and-interpretation).

### All PC-granted active innates: timing families

This covers all **34 active IDs** in the PC racial roster. “Default” means the
720-second generic rest above. Actor lag is the handler's normal successful
path; rejected attempts, deaths and special branches can differ. Fixed lag is
not scaled by spell-pulse gear merely because the innate invokes a spell.
The detailed target rules and costs remain in the innate reference; its old
rejected-use statements must be read with the [resolved issues](race-innates-issues.md#resolved-since-the-reference-snapshot).

| Innate(s) | Rest | Normal actor lag / delayed work |
|---|---|---|
| Levitate; Darkness; Strength; Enlarge; Burrow; Globe of Darkness; Phantasmal Form | Default | 4s; Phantasmal Form can be toggled off before rest |
| Underdark Invisibility; Ogre Roar; Blast; Shade Movement | Default | No explicit handler lag |
| Astral Shift; Prime Shift | Separate default timers | 4s on the normal dispatch/success paths |
| Shadow Door | Default | Underlying Dimension Door: normally 9s, Shadow Sorcerer 1s, Air Conjurer 3s |
| Battle Rage | Default | 8s; its Haste is cast directly at level 60 |
| Throw Lightning | Default | 4s actor lag; strike scheduled for 8s, selecting the then-current opponent |
| Summon Horde; Summon Warg | Default | No explicit actor lag; level-dependent delayed arrival, not racial-pulse-scaled |
| Bite | 12s via `innate.timer.secs.bite` | Insect-style 4s, Vampire 12s; shape variants differ |
| Stone Skin | Supplied 300s | 12s |
| Web Spray | Supplied 300s | 4s; 30s short effect, draining every 4s |
| Reflection | Configured 300s | 4s; linked image lifetime belongs to the pet system |
| Stampede | Supplied 60s | 4s on two or more hits, otherwise no actor lag |
| Charge | 12s skill-tag rest after a hit | Normally 8s and 30 vitality; opening/terrain branches differ |
| Call of the Grave | 240s skill-tag rest | 8s; arrival 6–10s; at level 56 explicit despawn 378s |
| Faerie Fire; Project Image; Fireshield; Disappear | No innate rest | 4s |
| Firestorm | No innate rest | 16s |
| Doorbash; Doorkick | No innate rest | 8s if actor survives; self-damage and door conditions |
| Bodyslam | No innate timer | Usually 12s; branch-specific waits and 30 vitality |
| Summon Totem | No innate rest | No explicit actor lag; item completion event after 4s |

[Dispatch/handlers](../../../src/classes/innates.c),
[summon/roar handlers](../../../src/classes/new_skills.c),
[physical actions](../../../src/cmd/actoff.c),
[Stampede](../../../src/cmd/actnew.c#L410).

The important temporal interactions are:

- **Mountain Dwarf Hatred (21):** visible qualifying races supply -1 combat
  pulse and -1 spell pulse. Its committed watcher interval is 4 raw pulses =
  1s, followed by ordinary affect recalculation scheduling. One watcher interval
  is not its damage bonus. Whether -1 crosses a timing boundary depends on B
  and the spell's intermediate integer duration.
- **Duergar Battle Rage (31):** Haste changes attack payload, cast calculation,
  archery speed and bard beat interval through different consumers. It does not
  directly lower F. Removing Slow can itself be the result of the Haste cast.
- **Goblin Totem (56):** an equipped new top-tier totem grants -1 spell pulse.
  It does not give -1 combat pulse or shorten every innate cooldown. An older
  lower-level totem does not upgrade itself when the owner levels.
- **Thri-Kreen cold vulnerability:** the additional 15-second Slow can remove
  attacks and restrict command polling; it does not simply multiply F or D by
  1.5. Its save can fail independently of the damage mitigation calculation.
- **Barbarian/Drider Groundfighting (21):** preserves the downed attack count,
  not the ability to issue every command while down or stunned.
- **Troll/Revenant regeneration:** improves recoverable HP over time through a
  rate, not by getting more resource events each melee round. Troll fire-burn
  suppression has the refresh defect documented in the issue companion.
- **Quick Thinker, Dauntless, Eyeless, shrug and body restrictions:** primarily
  preserve action availability by avoiding qualifying control/targeting outcomes.
  They do not have an interchangeable “speed percentage.”

## 9. Recovery and the time between fights

### Continuous resources

HP, PSP/mana, vitality and ward use separate resource events. They calculate a
per-game-tick rate, then accumulate:

```text
fractional gain += rate_per_tick * elapsed_pulses / 300
apply whole units; retain fractional remainder
```

PC callbacks normally rearm after one pulse. That is a 0.25-second accounting
opportunity, not an entire regeneration tick. At constant rate 600 HP per tick,
the nominal rate is **8 HP/s**, not 600 HP per attack or every .25s. A constant
300-HP deficit would take approximately 37.5s, with integer accrual and other
state changes accounted for in an actual journey.

Resource rate formulas inspect stats, posture, class, combat, room, difficulty,
affects and sometimes race. In-combat HP regeneration distinguishes a real
Regeneration affect from the passive bit. Sun vulnerability can stop HP/PSP
recovery; magical darkness has different exemptions in those two paths.
Zero-rate events stop and later state/periodic hooks restart them. In particular,
the ordinary affect pass rechecks PSP for racial mana users even in combat.
Negative rates and overheal decay also use the resource machinery.
[Accrual](../../../src/world/events.c#L223),
[start/rearm](../../../src/world/events.c#L272),
[rate formulas](../../../src/world/limits.c#L156),
[periodic restart](../../../src/magic/affects.c#L4143).

The racial innate component alone at level 56, awake and unburned, is 560 per
tick for Troll and 280 for Revenant: approximately **7.47 versus 3.73 HP/s**
before other recovery components, combat halving or blockers. Burned native
Troll's component becomes 1 per tick before posture multipliers, approximately
.0133 HP/s. These are components, not complete character regeneration rates.
[Innate rates](../../../src/classes/innates.c#L4859),
[recovery context](race-innates.md#regeneration--innate_regeneration).

### Spell resource models change the value of cast speed

The interface first gives mana precedence. Both Illithid PC IDs are racial mana
users, alongside eligible Psionicist/MindFlayer class configurations. Harpy
qualifies for Tupor; Ethermancer provides that route by class. Undead identity,
class, equipment and commune/deforest/focus rules can select other spell-slot
recovery paths. Do not infer the interface solely from an old undead-race list
or an innate: the actual macros and `spell_interface_command()` decide it.
[Selection](../../../src/classes/memorize.c#L134),
[resource predicates](../../../src/core/utils.h#L974).

`get_circle_memtime()` does **not** multiply by racial casting pulse or
`SPELL_PULSE`. Its main inputs include circle, level, relevant effective stats,
their native racial baselines, class/multiclass multipliers, terrain and state:

- Ordinary book recovery uses INT; non-book prayer/nature paths generally use
  WIS; Dragoon has a POW branch. Stats above the corresponding racial baseline
  add to the recovery denominator. Low-level smoothing, class, terrain,
  alignment and nature-epic branches apply in their own order.
- The undead-style helper uses `STAT_INDEX(POW)` plus .7 times excess INT and
  .35 times excess WIS. Its numerator factor is .85 for a non-semi-caster,
  1.7 for a semi-caster, before eligible meditation.
- Tupor uses WIS for Ethermancer/Shaman, otherwise INT, with full excess over
  that stat's racial baseline. The denominator then uses committed
  `memorize.factor.tupor=.9`. Sleeping prone multiplies the computed interval
  by .75; successful meditation can halve it further. Stages truncate.

These helpers return pulse intervals. They are not complete “refill all spells”
times: actual scheduled recovery is sequential and can contain extra stages.
`handle_undead_mem()` replenishes one slot, prioritizing the highest incomplete
circle. Subsequent intervals can carry a meditation check that adds another
half-interval on failure. Initial explicit assimilation/tupor schedules differ
from passive commune/deforest. Completing an explicit slot recovery applies
a one-second wait. Recent Tupor display work estimates that process without
rolling recovery procs merely to show the estimate.
[General formula](../../../src/classes/memorize.c#L752),
[undead/Tupor helpers](../../../src/classes/memorize.c#L638),
[slot recovery](../../../src/classes/memorize.c#L1042),
[event stages](../../../src/classes/memorize.c#L1411).

Casting segments call `DelayCommune()`, extending a pending spell-slot recovery
event. Commune/deforest paths also check combat/casting and can account for
remaining command wait. Speeding casts therefore changes resource depletion
and the opportunities to recover; it does not proportionately speed the recovery
formula. A fast caster can empty a fixed reserve sooner without improving its
long-run resource-limited output. Full reserves, sustained fights and depleted
recovery need separate comparisons.
[Recovery delay](../../../src/world/events.c#L349),
[slot gates](../../../src/classes/memorize.c#L1076),
[consumption](../../../src/classes/memorize.c#L2197).

## 10. Worked comparisons

All examples distinguish calculated mechanics from measured full-character
performance. Properties are committed values; timing is nominal at 4 pulses/s.

### A. Same class: Gnome, Human and Ogre Warriors

Use C=0, no pulse gear/temporary bonuses and the same attack payload. All three
have a Warrior entry in the committed class matrix. This deliberately holds
their different stats, equipment fit and per-hit damage outside the timing
comparison.

| Race | R | F=R+2 | Recurring interval | Rounds in (0,10s] | Rounds in (0,60s] | Attempts in 60s if exactly 4 per round |
|---|---|---|---|---|---|---|
| Gnome | 11.5 | 13.5 | 3.5s | 2 | 17 | 68 |
| Human | 15 | 17 | 4.5s | 2 | 13 | 52 |
| Ogre | 19 | 21 | 5.5s | 1 | 10 | 40 |

The reference round at time zero is excluded. Long-run Gnome frequency is
`22/14 = 1.5714` times Ogre frequency, or **57.14% more rounds**. The 60-second
integer window gives 17 versus 10, a different ratio due to boundary phase.
For equal final DPS with all else held constant, Ogre needs 1.5714 times the
expected damage per round. This is a break-even condition, not evidence Ogre
actually supplies that damage or is weaker overall.

### B. One more pulse apply can do nothing—or save a quarter-second

| Race, C=0 | F at P=0 | F at P=-1 | Interval before → after | Long-run round-rate gain |
|---|---|---|---|---|
| Gnome | 13.5 | 13.29 | 14 → 14 pulses | 0% |
| Drow/Grey Elf | 15.5 | 15.25 | 16 → 16 | 0% |
| Human | 17 | 16.65 | 18 → 17 | 5.88% |
| Mountain Dwarf | 19 | 18.423334 | 20 → 19 | 5.26% |
| Ogre | 21 | 20.09 | 22 → 21 | 4.76% |

At P=-5, Ogre and Mountain Dwarf both reach a 17-pulse interval; Human reaches
16 and Gnome 13. This does not make gear equally valuable to every race.
`A(B)` is small around B=13.75 and grows away from that region, so the response
to the same apply is nonlinear even before integer boundaries. The minimum
floor eventually stops further improvement; the examples do not establish
that every tested apply total is obtainable on a legal equipment set.

Mountain Dwarf Hatred is a concrete P=-1/S=-1 source when its level/visibility
condition is met. In this C=0 fixture it changes melee 5.0s → 4.75s and an
18-base spell's shared D from 15 → 14 pulses. Its watcher and current countdown
mean those gains need not begin on the exact instant another race enters.

### C. A spell lands earlier than the character becomes ready again

Use an 18-base spell, no Haste/mastery, no target-induced extra lag, an unslowed
player, successful execution and continuously queued input. Full Heal has this
registered base, but these rows compare timing, not shared spell eligibility.

| Fixture | D | Initial W | Landing C | Gate ready | Next queued start |
|---|---|---|---|---|---|
| Human ordinary cast | 18 | 18 | 18 | 22 | 23 pulses = 5.75s |
| Human successful Quick Chant | 18 | 18 | 9 | 18 | 19 = 4.75s |
| Gnome ordinary cast | 12 | 12 | 12 | 16 | 17 = 4.25s |
| Gnome successful Quick Chant | 12 | 12 | 6 | 12 | 13 = 3.25s |
| Planetbound Illithid ordinary `will` | 13 | 6 | 6 | 10 | 11 = 2.75s |
| Original Illithid ordinary `will` | 1 | 0 | 1 | 5 | 6 = 1.5s |

Human Quick Chant halves landing time from 4.5s to 2.25s, but this fixture's
repeat-start interval improves from 5.75s to 4.75s, not to 2.875s. It shortens
the vulnerable casting window and can preserve melee opportunities even when
the longer command wait still limits repeated casts. The original Illithid's
floor does not produce four completed, recoverable casts per real second.

### D. Short spells and racial rounding

For a 6-base spell, Gnome .70 and Halfling .73 both produce D=4. For an 18-base
spell they produce 12 and 13. An S=-1 modifier changes those 18-base results
to 11 and 12. It changes Human D=18 to 17. Thus “-1 spell pulse” can remove one
whole .25-second unit even though .03 of the intermediate duration is less
than one, because multiplication is followed by truncation. Further gear can
hit a plateau or the one-pulse floor. Compare a range of actually used spells,
not only one long benchmark spell.

### E. Haste changes multiple clocks differently

Take a Duergar Warrior with F=19 and a controlled pre-Haste payload of four
attacks per round, no Slow. Battle Rage's Haste adds one ordinary primary
attack: 4 → 5 is **25% more attempted attacks per eligible round**, while the
recurring interval remains 20 pulses = 5s. Its 18-base spell D changes
15 → 12; the plain repeat-start fixture changes 20 → 17 pulses.

On a legal singing build the same Haste bit would change song beats
35 → 25 pulses, a **40%** beat-rate increase. In archery it adds **20 speed
points**, which may or may not cross a 40-point arrow boundary. These are
distinct effects of one buff; adding their percentages into one universal
“haste strength” would double-count or invent benefits.

### F. Class and multiclass selection change the starting point

Human's R=15 and G=2 give F=17 for Warrior, 15 for Ranger, 15.8 for Monk and
19 for Sorcerer before applies/weapon exceptions. Their recurring intervals
are 18, 16, 16 and 20 pulses. Monk and Ranger therefore share this baseline
interval despite different floating values and very different attack builders.

A Human Ranger/Sorcerer timing fixture takes `min(-2,+2)=-2`, so F=15, not 17
or 19. This is a source-level multiclass timing comparison, not permission to
skip creation, secondary-class, skill or specialization rules.

### G. Archery uses both volley size and racial recovery

Use skill/weapon ceilings high enough not to bind, DEX=100, no Haste/Blur/spec,
not hidden and not fighting. Speed=150 yields three arrows at 40 each. Assuming
all three loop iterations complete, `delay=3/3=1`:

| C=0 fixture | trunc(F) | Arrow volley | Command wait |
|---|---|---|---|
| Gnome | 13 | 3 | 4+13 = 17 pulses = 4.25s |
| Human | 17 | 3 | 21 pulses = 5.25s |
| Ogre | 21 | 3 | 25 pulses = 6.25s |

These are isolated formula fixtures, not a claim every listed class/race has
archery. If Haste takes speed 150 → 170, the volley becomes four arrows and
the lag uses 4/3 of the integer melee value plus the fixed four pulses.
Extra arrows improve output but also extend command recovery and spend ammo.

### H. A lost combat opportunity is not repaid

Consider F=4, so recurring rounds are due at pulses 5,10,15 after a round at
zero. If casting suppresses the pulse-5 opportunity and ends at pulse 6, the
next ordinary round is pulse 10, not pulse 6. If the cast instead completes
in pulse 5's event phase, it can be clear before that pulse's combat phase.
A one-pulse difference in landing can therefore preserve an entire attack
payload. This example is a timing fixture near the floor, not a claimed
ordinary ungeared racial build.

### I. Posture changes the payload, with integer rounding

With five computed attacks, kneeling without Groundfighting leaves
`5-floor(5/3)=4`; sitting/prone leaves `5-floor(5/2)=3`. A qualifying
Groundfighting holder retains five at this stage. The interval remains the
same unless another effect changes it. Later barriers/shares and stun/control
admission still apply. Evaluate Barbarian/Drider's level-21 benefit by retained
actions during knockdowns, not by claiming every knockdown is resisted.

### J. Finite cooldowns and buff duration change short versus long fights

A 300-second innate used at time zero contributes once in a 60-second fight,
even on the fastest race. It can be ready again at second 300 in a longer
encounter; fixed actor lag still limits what the player does around each use.
A temporary ordinary duration-5 buff spans approximately 375–450 seconds
under the current expiry ordering, while a 300-pulse short buff lasts nominally
75 seconds. Those are not interchangeable “five ticks” and “300 duration.”

For an otherwise identical resource-limited caster, faster spending can improve
the opening burst while leaving refill time unchanged. Compare full-reserve
output, depletion time and a repeated fight-plus-recovery cycle separately.

## 11. What this means for every player race

The melee intervals below are the neutral P=0/C=0 comparisons from section 3.
The spell factor is an input, not a final throughput ratio. Native stats,
allowed classes, equipment, defenses, environment and active powers can outweigh
these isolated timing differences.

| ID | Race | Neutral melee interval / cast factor | Gameplay interpretation |
|---|---|---|---|
| 1 | Human | 4.5s / 1.000 | Reference-like melee/cast timing. Seadog changes ship/trade performance, not the personal combat clock; class and gear determine its attack payload. |
| 2 | Barbarian | 5.25s / 1.220 | Slower ordinary melee and casting; Bodyslam supplies an opener with its own costs. Groundfighting at 21 preserves attacks while down and Dauntless can prevent qualifying fear losses. |
| 3 | Drow Elf | 4s / 0.820 | Faster melee/casting than Human in the neutral fixture. Faerie Fire's fixed 4s command lag bypasses the cast-factor pipeline; sunlight can reduce sustained recovery. |
| 4 | Grey Elf | 4s / 0.820 | Same raw tempo as Drow, with a different innate/environment package. Racial casting speed does not automatically hasten songs or shorten every skill cooldown. |
| 5 | Mountain Dwarf | 5s / 0.850 | Slow melee base but favorable casting factor. Hatred can change both pulse applies; hammer/axe mastery changes attack payload, not the scheduled interval. |
| 6 | Duergar Dwarf | 5s / 0.850 | Same base timing as Mountain Dwarf; Battle Rage's Haste affects count, casts, songs and archery separately. Battle Frenzy opportunities depend on eligible hit frequency. |
| 7 | Halfling | 3.75s / 0.730 | Fast melee and casting; the first -1 combat apply does not cross this neutral fixture's integer boundary. Quick Thinker preserves actions through saves rather than directly reducing timers. |
| 8 | Gnome | 3.5s / 0.700 | Very fast ordinary timing. The first -1 combat apply has no interval effect here, but spell-pulse can cross a cast boundary; Reflection's 300s rest stays fixed. |
| 9 | Ogre | 5.5s / 1.310 | Slow ordinary melee/casting. High STR and equipment/attack effects must supply any per-round compensation; the old 1.8 racial total-output property is inactive. |
| 10 | Troll | 5.25s / 1.220 | Same base tempo as Barbarian; regeneration changes sustain and recovery. Fire and sun can erode those advantages, and Troll no longer has Groundfighting to preserve downed attacks. |
| 11 | Half-Elf | 4.25s / 0.900 | Moderately faster than Human on both axes, but restricted. Quick Thinker at 30 is action preservation; class/form availability must be checked before comparing builds. |
| 12 | Illithid | 4.5s / 0.025 | Restricted, exceptional .025 cast factor plus racial mana/will routing. Short effects hit the minimum; completion recovery and input phases dominate repeated actions. Blast has its own default rest. |
| 13 | Orc | 4.5s / 1.000 | Human-like base tempo. Horde/Warg have independent delayed arrivals and follower clocks; they do not add personal attacks to each racial round. |
| 14 | Thri-Kreen | 5s / 1.000 | Slower per-round timing but native four hands can increase attacks in that round. Cold-induced Slow alters attack count/input opportunities; current Leap unlocks at 21. |
| 15 | Centaur | 4.5s / 1.090 | Human-equivalent neutral integer melee interval despite a different floating base; somewhat slower casting. Horse Body and Stampede change control/admission, not every round's speed. |
| 16 | Githyanki | 4.5s / 0.850 | Human-like melee with favorable casting. Astral/Prime Shift use independent fixed-rest travel paths, and sun vulnerability can affect the sustained resource picture. |
| 17 | Minotaur | 5.25s / 1.150 | Slower melee/casting; Charge is a separate opening action, with hit-generated rest and fixed lag. No active old Minotaur-rage extra-attack block should be added to its round. |
| 18 | Shade | 4.5s / 0.700 | Restricted; Human-like melee with fast casting. Shade Movement changes approach/exposure and has its own lifetime issues; undead-style recovery can change fight-to-fight tempo. |
| 19 | Revenant | 4.75s / 1.300 | Restricted; slightly slower neutral melee than Human and slower casting. Regeneration and Shadow Door affect sustain/repositioning, not the raw race timer. |
| 20 | Goblin | 3.75s / 0.730 | Fast melee/casting. Disappear's 4s lag and Totem's 4s arrival are independent; the level-56 equipped totem supplies -1 spell pulse only. |
| 21 | Lich | 3.75s / 0.550 | Restricted; fast melee and .55 casting factor. Spell Absorb can replenish an eligible spent circle; undead-style recovery and Grave's independent 240s rest need separate accounting. |
| 22 | Vampire | 4s / 0.800 | Restricted; fast melee and favorable casting. Touch-vamp healing can scale with eligible damage opportunities; the active Bite has a much longer 12s actor lag. |
| 23 | Death Knight | 4.25s / 1.500 | Restricted; reasonably fast melee but slow 1.5 casting. Innate Firestorm/Fireshield call spells directly with fixed 16s/4s lag, so they do not inherit the ordinary cast-factor penalty. |
| 24 | Shadow Beast | 3.75s / 1.100 | Restricted; fast melee but slower-than-Human casting. Direct Strength/Enlarge and Project Image have their own costs; undead-style recovery is separate. |
| 25 | Storm Giant | 4.25s / 1.600 | Restricted; intermediate melee and slow casting despite no racial innate grants. Zero listed innates does not mean neutral timing or no racial differences. |
| 26 | Wight | 4.5s / 1.900 | Restricted; Human-equivalent neutral integer melee interval, but the slowest listed PC casting factor, 1.9. Innate Stone Skin instead uses fixed 12s lag/300s rest. |
| 27 | Phantom | 4.25s / 0.700 | Restricted; moderately fast melee and fast casting. Flight/form access can preserve travel opportunities, while fire/elemental weaknesses affect how long it can exploit its speed. |
| 28 | Harpy | 3.75s / 0.700 | Restricted; fast melee/casting and passive flight. Harpy selects Tupor unless an earlier resource-model rule wins; its recovery time does not use its .70 cast multiplier. |
| 29 | Orog | 4.5s / 1.600 | Restricted; Human-like melee but very slow casting. Fury can increase delivered damage through its own group/raw-damage rules without changing the timer. |
| 30 | Githzerai | 4.5s / 0.850 | Human-like melee with favorable casting. Rrakkma improves defense in eligible groups, preserving time alive rather than directly accelerating action clocks. |
| 31 | Drider | 4s / 1.090 | Elf-like melee frequency but slower casting. Groundfighting can preserve the attack payload; Spider Body is not four arms. Web Spray drains enemy vitality on fixed event timing. |
| 32 | Kobold | 3.25s / 0.700 | Fastest neutral PC melee interval in the committed table and a .70 casting factor. Reflection provides a separate fixed-rest disengagement tool; speed alone does not establish highest DPS. |
| 33 | Planetbound Illithid | 4.25s / 0.750 | Restricted; distinct from original Illithid: moderate melee, .75 casting and racial mana/will. Dayblind/sun affect access/recovery, not the same .025 floor behavior. |
| 34 | Kuo Toa | 4.5s / 1.100 | Restricted; Human-like melee and slower casting. Throw Lightning waits 8s and selects the current opponent; its arrival is not accelerated by casting gear. |
| 35 | Wood Elf | 4.25s / 0.950 | Restricted; moderately fast melee and slightly favorable casting. Terrain sneak/forest information can improve engagement choice without changing the personal clock. |
| 36 | Firbolg | 5.5s / 1.310 | Ogre-like slow melee/casting. High STR, body size and opener admission must be evaluated against the frequency cost; the old racial total-output value is inactive. |
| 37 | Tiefling | 4.25s / 0.875 | Moderately fast melee and favorable .875 casting. Its defenses and lack of a racial sun penalty change usable uptime; they are not extra pulse applies. |

## 12. How to use this layer for balancing

### Do not substitute inactive settings or display labels for execution

`damage.totalOutput.racial.*` still has many non-1 values in the property file,
but the loader's use of those values is commented out and
`combat_by_race[race][1]` is set to **1**. They do not compensate a slow race's
melee timer through that loader. Class damage factors remain a separate active
path. `damage.damrollModifier.racial.*` controls a racial damroll cap in
aggregation; it is not an equivalent per-hit racial multiplier. Other active
racial elemental damage factors also belong to their own damage predicates.
[Inactive racial total-output loading](../../../src/magic/affects.c#L3477),
[damroll cap](../../../src/magic/affects.c#L928),
[spell-type factors](../../../src/combat/dam_mods.c#L766).

The score display prints an integer melee value and a racial spell-factor ×
spell-pulse product. It is not the full scheduled melee interval or a specific
spell's truncated, hasted/mastered duration plus command recovery. Likewise,
generic innate readiness does not automatically inspect skill-tag cooldowns
such as Charge/Grave. Use the owning execution path for quantitative work.
[Score](../../../src/cmd/actinf.c#L6749),
[innate status issue](race-innates-issues.md#f11--generic-innate-status-misses-charge-and-call-of-the-grave-rests).

### Hold the comparison conditions explicitly

For every race/build comparison, record:

- Source revision and effective property snapshot; ordinary/restricted creation
  and actual class legality; level, prime/secondary class and specialization.
- Native/current mechanics race and any form, effective stats, weapon types,
  equipment weight, relevant skill ratings, P/S totals and active buffs.
- Target stats, defenses, posture and behavior; PvE/PvP; group size; room,
  sunlight, terrain and resource state.
- Starting command wait, melee countdown phase and cooldown state; whether an
  immediate opener or prewoven spell is included; the exact observation window.

Use at least an opening window, sustained full-contact window and repeated
encounter-plus-recovery window. Compare both equal gear and equal-budget
race-appropriate gear. A class-neutral racial timer is useful for isolating a
mechanism, but not a final race ranking.

Measure executed attacks, successful effects, effective damage/healing, control
time, commands denied/queued, resources spent, depletion, deaths and recovery.
Separate primary/secondary/pet contributions and attempted versus landed hits.
For a speed change, keep the random seed or repeated trial conditions comparable
and test near integer boundaries. Do not infer balance from popularity.

The existing [class-points comparison framework](../CLASS-POINTS.md#comparison-conditions)
provides encounter/build controls. [Combat telemetry](../../telemetry/COMBAT_METRICS.md)
defines damage/healing/casting/tanking summaries and quality flags, but its
default-off producer and heterogeneous control coverage do not establish that
a complete live dataset currently exists. A controlled local trace can supply
the missing round/command timing detail without claiming production evidence.

### Tuning and freshness

The staff `pulse` command lists loaded racial values, adjusts absolute values
through the property system and can save them separately. Its bounds differ:
casting .010–5.000 is a multiplier, melee 1.000–40.000 is a base pulse value.
Melee adjustment queues recalculation for matching races; casting reads its
loaded table at a new cast. An active cast, running melee countdown or innate
timer is not universally rewritten to match a new setting.

For a proposed change, recompute all affected legal class/gear cases through
the actual formula, identify threshold crossings, and then run a representative
gameplay journey. Keep a source snapshot with each result. A property diff that
looks numerically small can change a discrete extra action in a short fight.
[Staff command](../../../src/world/racial_pulse.c#L110),
[value rules](../../../src/world/racial_pulse_math.h),
[property refresh](../../../src/world/properties.c#L147).

## 13. Verification and limits

The review traced the complete PC race-key table, both property loaders, pulse
apply aggregation, melee recalculation/countdown, attack construction/execution,
cast/will/mastery/continuation/completion paths, input/wait ordering, ranged and
song consumers, innate rest families, ordinary/short expiry and resource/spell
recovery. A search of all `base_combat_round`, `combat_tics` and `SPELL_PULSE`
consumers cross-checked the direct timing paths; the broader stats/innate/size
layers supply the linked payload and admission details.

Isolated executable checks for this review:

- Compiled the production race/class name arrays, `update_damage_data()`,
  `update_spellpulse_data()`, `SpellCastTime()`, the melee recalculation excerpt
  and countdown excerpt with real engine types under ASan/UBSan. Checked all
  **37 PC races and 30 class IDs**, combat applies -25 through +10, spell bases
  1–72 and representative negative/zero/positive spell applies. Verified the
  floor, integer recurring periods, finite-window counts, multiclass selection
  and inactive racial total-output field. External services and special
  equipment conditions were fixtures; this does not exercise every legal build
  or the complete `affect_total()` lifecycle.
- Generated both 37-row numeric tables from those executions, then parsed the
  Markdown back against the recorded results. Confirmed the third table has
  every PC race once, and creation annotations match the 21 ordinary/16
  restricted split. All three use IDs 1–37 without substituting NPC races.
- Executed extracted production `CharWait()` and `event_wait()` with a
  deterministic scheduler/input-phase fixture: **6,480 wait/landing pairs**,
  plus overlapping waits, confirmed `max(W,C+4)+1` under the stated assumptions.
  The six casting rows in example C match that execution.
- Checked numeric worked examples, the 34-active-ID timing-family census,
  relative links, heading anchors, table shape and whitespace.

These existing focused checks also passed:

- `tests/async/test_racial_pulse.py`
- `tests/async/test_spellcast_racial_multiplier.py`
- `tests/async/test_cast_lateness_runtime.py`
- `tests/async/test_casting_input_gate_runtime.py`
- `tests/async/test_casting_input_queue_runtime.py`
- `tests/async/test_player_event_timing_contract.py`
- `tests/async/test_nevent_scheduler_runtime.py`
- `tests/async/test_psp_move_regen.py`
- `tests/async/test_tupor_recovery_contract.py`
- `tests/async/test_tupor_display_runtime.py`

The source-contract checks establish bindings, not live timing. The scheduler
runtime suite exercises deadlines, zero-delay scheduling, priority, cancellation,
short-affect expiry and overload/catch-up modes under sanitizers. Cast lateness
tests execute actual segmented casting with injected callback delays. Local
probe source, outputs and table data remain ignored artifacts under
`bin/tests/race-tempo-review/`.

This is a source and isolated-execution reference, not a live-server benchmark.
No production connection, configuration change, server restart, deployment,
commit or push is part of writing this layer. No C/C++ gameplay code changed,
so a full server build is not required. Live equipment/prototype availability,
every legal build, network behavior, server overload and emergent PvP outcomes
require separate evidence before drawing a race-balance conclusion.
