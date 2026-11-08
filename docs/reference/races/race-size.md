# PC race size: mechanics and balance

Source review: 2026-11-08, checkout `b9bcce5e1c0081d373382c0e9cd3f18d48832b84`.
This is a reference to the checked-in server and `lib/duris.properties`, not a
measurement of deployed settings or race win rates. No gameplay was changed.
Runtime property overrides can change the configurable values below.

See [race-size-issues.md](race-size-issues.md) for potential defects, each one's
gameplay impact, recommendations, and the distinction between active bugs,
design questions, and dormant code.

Availability correction from follow-up review: `spell_corpseform()` immediately
returns “Temporarily disabled.” Its size/form implementation described below
is dormant, not an accessible player route. The size lookup discrepancies still
affect training dummy profiles and NPC race defaults independently of corpseform.
[Disabled entry point](../../../src/classes/necromancy.c#L3230).

## Main findings

- Ordinary creation offers 21 races in four base sizes: Small, Medium, Large,
  and Huge. The complete 37-race PC ID range also has no naturally Tiny, Giant,
  or Gargantuan race under the player initialization rules.
- Size chiefly controls **which targets a move can affect**, knockdown behavior,
  and PvP melee crowding. It is not a universal damage, armor, hit, dodge, or
  spell-resistance modifier. Both being too large and being too small can fail.
- There are four different inputs: stored size, effective size, mounted takedown
  size, and physical height/weight. They are not interchangeable. Several
  mechanics deliberately or historically read stored size, ignoring growth.
- The two racial size authorities disagree for six PC races. Barbarian is the
  ordinary-roster example: Large at creation/login, Medium in `race_size()`.
- Giant weapon handling, dwarf giant avoidance, centaur/drider bodies, racial
  stats, and racial skill grants are separate rules. Changing a size number
  does not automatically give those racial benefits or remove those restrictions.

## 1. Definitions and character lifecycle

### Size scale

The IDs are ordinal categories, not inches, pounds, occupied room tiles, or
weapon damage dice. Arithmetic such as `+1` means one category.

| ID | Name | Ordinary starting PC races |
|---|---|---|
| 1 | Tiny | None; reachable by reducing a Small character |
| 2 | Small | Halfling, Gnome, Goblin, Kobold |
| 3 | Medium | Human, Grey Elf, Mountain Dwarf, Githzerai, Drow, Duergar, Orc, Githyanki, Thri-kreen, Tiefling |
| 4 | Large | Barbarian, Centaur, Troll, Drider |
| 5 | Huge | Firbolg, Ogre, Minotaur |
| 6 | Giant | None; reachable through growth |
| 7 | Gargantuan | None; reachable through growth, and the effective-size ceiling |

`SIZE_NONE=0` and `SIZE_DEFAULT=-1` also exist for data initialization/NPCs.
Effective size is always clamped to 1–7, even when stored size is 0.
Sources: [size constants](../../../src/core/defines.h#L1128),
[player size assignments](../../../src/account/nanny.c#L3827),
[ordinary and restricted creation rosters](../../../src/core/constant.c#L1590),
[committed creation policy](../../../lib/creation_availability.cfg#L46).

### Complete PC roster

The ordinary roster below is enabled in the committed creation policy. This
does not promise that every race/class combination is legal or that a live
environment has the same overrides. `B` is the stored size assigned by
`set_char_size()`. `R` is the separate `race_size(race)` lookup.

| Ordinary race | PC race ID | B | R |
|---|---|---|---|
| Human | 1 | Medium | Medium |
| Barbarian | 2 | **Large** | **Medium** |
| Grey Elf | 4 | Medium | Medium |
| Mountain Dwarf | 5 | Medium | Medium |
| Halfling | 7 | Small | Small |
| Gnome | 8 | Small | Small |
| Centaur | 15 | Large | Large |
| Githzerai | 30 | Medium | Medium |
| Firbolg | 36 | Huge | Huge |
| Drow | 3 | Medium | Medium |
| Duergar | 6 | Medium | Medium |
| Ogre | 9 | Huge | Huge |
| Troll | 10 | Large | Large |
| Orc | 13 | Medium | Medium |
| Githyanki | 16 | Medium | Medium |
| Goblin | 20 | Small | Small |
| Kobold | 32 | Small | Small |
| Drider | 31 | Large | Large |
| Thri-kreen | 14 | Medium | Medium |
| Minotaur | 17 | Huge | Huge |
| Tiefling | 37 | Medium | Medium |

The other 16 PC IDs are restricted/legacy races. They are exposed at creation
through `CREATION_ALL_RACES=TRUE`, subject to the shared creation policy. Their
presence in the roster is not proof that an old transformation is available:
`descend` explicitly returns with a disabled message; the old descend path
rejects PCs, and `ascend` also rejects PCs at entry.

| Restricted/legacy race | PC race ID | B | R |
|---|---|---|---|
| Half-Elf | 11 | Medium | Medium |
| Illithid | 12 | Medium | Medium |
| Shade | 18 | Small | Small |
| Revenant | 19 | Large | Large |
| Lich | 21 | Medium | Medium |
| Vampire (`RACE_PVAMPIRE`) | 22 | Medium | Medium |
| Death Knight | 23 | **Large** | **Medium** |
| Shadow Beast | 24 | **Medium** | **Large** |
| Storm Giant | 25 | **Huge** | **Medium** |
| Wight | 26 | **Huge** | **Medium** |
| Phantom | 27 | Medium | Medium |
| Harpy | 28 | **Small** | **Medium** |
| Orog | 29 | Medium | Medium |
| Planetbound Illithid | 33 | Medium | Medium |
| Kuo-Toa | 34 | Medium | Medium |
| Wood Elf | 35 | Medium | Medium |

The naming is significant: PC Storm Giant is `RACE_SGIANT`, not NPC
`RACE_GIANT`. Wight and Phantom are also distinct from Wraith and Ghost.
`race_size()` falls through to Medium for Storm Giant, Wight, Phantom, and
Harpy; it explicitly classifies Death Knight and Barbarian as Medium and
Shadow Beast as Large. Sources: [race IDs](../../../src/core/defines.h#L901),
[race_size](../../../src/core/common.c#L184),
[disabled transformations](../../../src/cmd/actoth.c#L7587).

### The four values used by gameplay

Use these symbols in the rest of this document:

```text
B = GET_SIZE(character) = character.player.size
R = race_size(GET_RACE(character))
S = GET_ALT_SIZE(character)
T = get_takedown_size(character)

S = clamp((TAG_RACE_CHANGE present ? R : B)
          + (AFF3_ENLARGE ? 1 : 0)
          - (AFF3_REDUCE ? 1 : 0)
          + (AFF5_TITAN_FORM ? 2 : 0), 1, 7)

T = min(7, S + 1), if linked to a mount whose S >= rider's S
T = S, otherwise
```

Enlarge and reduce are independent `if` statements in `GET_ALT_SIZE()`: if both
bits are present, their category changes cancel. Titan form adds **two**, not
three; the old three-step macro survives only inside comments. A very large
mount adds one to the rider's takedown size, not its own size or weight.
[Effective size](../../../src/core/utility.c#L5100),
[mounted takedown size](../../../src/core/utility.c#L5852).

Ordinary spell growth does not write `B`. The disabled corpseform implementation writes the
current race and installs `TAG_RACE_CHANGE`, so `S` switches to `R` while `B`
stays behind. An ordinary disguise or learned animal shape stores its displayed
race under `disguise`, without becoming that race's numeric size. Dragon form
from draconic apotheosis sets the race to Dragon and adds the enlarge bit, but
does not itself install the race-change tag or assign Gargantuan size: absent
another tag, its size is the old `B+1`.
[Corpseform](../../../src/classes/necromancy.c#L3358),
[shapechange](../../../src/cmd/actnew.c#L2824),
[draconic apotheosis](../../../src/magic/magic.c#L30340).

Both telnet and WebSocket new-character completion call `init_char()`, which
calls `set_char_height_weight()` and `set_char_size()`. Existing-character login
calls `set_char_size()` again. Native player snapshots capture and materialize
stored size, height, and weight, but the login assignment means saved size is
not the only authority for PC `B`. Staff `set ... race` also calls
`set_char_size()`; staff can separately set physical fields/size.
[Initialization](../../../src/account/nanny.c#L3969),
[WebSocket completion](../../../src/net/ws_handlers.c#L2397),
[login](../../../src/account/nanny.c#L1751),
[snapshot capture](../../../src/player/player_snapshot_capture.c#L142),
[materialization](../../../src/player/player_load_materialize.c#L239),
[staff race change](../../../src/cmd/actset.c#L626).

The older `init_height_weight()` assigns `B=R` and uses another physical formula.
Its call in `do_reinitphys()` occurs after an unconditional return, so it is
not the current ordinary character-generation route. Old ascend/descend bodies
also contain size assignments, but do not establish accessible PC progression.
The Yzar race-change event explicitly writes `B=R` for its changing form.
[Old physical initialization](../../../src/account/nanny.c#L301),
[unreachable reinit tail](../../../src/cmd/actwiz.c#L6505),
[Yzar event](../../../src/magic/spells.c#L3800).

Follow-up persistence finding: native snapshot capture records the current
`GET_RACE(ch)` while omitting affects marked `AFFTYPE_NOSAVE`. Draconic
apotheosis stores the original race in such an omitted affect. A scratch probe
using the production snapshot capture and codec reproduced saved Dragon race
with no original-race restoration affect. Reload materialization applies the
saved race directly. This is a high-confidence identity-restoration defect for
that registered spell; no live logout/relogin journey was run. The same storage
problem is present in the dormant corpseform implementation, whose original-race
tag is also NOSAVE. A repair must preserve permanent identity or the complete
reversible form, rather than saving only its temporary race.
[Snapshot race](../../../src/player/player_snapshot_capture.c#L138),
[NOSAVE filter](../../../src/player/player_snapshot_capture.c#L310),
[dragon restoration record](../../../src/magic/magic.c#L30340),
[loaded race](../../../src/player/player_load_materialize.c#L227).

## 2. Physical height and body weight

Height and weight are randomized separately from size category. Mountain and
Duergar dwarves are Medium despite being shorter than many Small characters;
Thri-kreen and Minotaur share physical-generation parameters despite being
Medium and Huge. Centaur and Human share height parameters but have very
different body weights. There is no height-to-size threshold conversion.

These are the **generator inputs**, not guaranteed final averages. `H` and
`D` are height parameters in inches, `W` is a weight parameter in pounds,
`U/O` are under/overweight parameters, and `F` is the female scaling percentage
(male/other sex uses 100).

| Races sharing physical inputs | H | D | W | U/O | F |
|---|---|---|---|---|---|
| Ogre, Storm Giant, Wight | 90 | 10 | 400 | 80/150 | 100 |
| Troll | 95 | 10 | 220 | 90/115 | 100 |
| Mountain Dwarf, Duergar | 48 | 8 | 175 | 80/125 | 95 |
| Barbarian, Firbolg, Minotaur, Death Knight, Shadow Beast, Thri-kreen, Revenant, Orog | 76 | 18 | 210 | 70/150 | 85 |
| Human, Vampire, Githyanki, Orc, Phantom, Githzerai, Tiefling, Kuo-Toa | 68 | 24 | 150 | 65/180 | 85 |
| Halfling | 38 | 6 | 55 | 85/150 | 95 |
| Gnome, Goblin, Shade, Kobold | 42 | 6 | 55 | 75/120 | 95 |
| Lich, Drow, Grey Elf, Wood Elf, Harpy, Illithid, Planetbound Illithid, Drider | 70 | 8 | 125 | 90/115 | 95 |
| Half-Elf | 69 | 16 | 145 | 80/145 | 90 |
| Centaur | 68 | 24 | 650 | 65/100 | 90 |

The implementation, using C integer division/truncation at each step, is:

```text
h_roll = dice(4, 51) - 104 + number(5, 13)       # -95 through 113
height = (H*F + (D*F*h_roll)/200) / 100
tmp = ((height*1000*F) / (H*F/10)) / 10
w_roll = U + ((dice(3, 34)-3) * (O-U+1)) / 100
weight = (W*tmp*w_roll) / 100000
```

The historical comment claims constitution influences the result; the current
function does **not** read CON. Sex/physical random rolls do not change `B`.
The audited character-height readers only display it; body height itself does
not supply combat reach, size category, or movement clearance.
For example, male Human endpoint rolls give 56–81 inches and 80–319 lb; male
Centaur endpoints give 56–81 inches and 347–774 lb. These are generator bounds,
not a uniform distribution or a sample of actual characters.
[Complete generator](../../../src/account/nanny.c#L3668).

Displayed/usable physical values have their own transformations:

| Flags | `GET_HEIGHT` | `GET_WEIGHT` |
|---|---|---|
| Neither | stored height | stored weight |
| Enlarge | stored height × 1.5, converted to unsigned short | stored weight × 2 |
| Reduce, with no enlarge | stored height ÷ 1.5, converted to unsigned short | stored weight ÷ 2, integer |
| Both | enlarge branch wins | enlarge branch wins |
| Titan form alone | unchanged | unchanged |

Thus titan form changes the effective category without multiplying body mass;
enlarge messages saying “twice your normal size” do not mean doubled height.
Both flags can yield an unchanged category but doubled weight. A plain item
affect bit has the same geometric consequences without inherently adding the
spell's attribute package. [Physical macros](../../../src/core/utils.h#L503).

## 3. Combat target windows

Here `delta = target size - actor size`. A range is inclusive. These are the
**size conditions only**: skill access, footing, posture, safe-room rules,
front ranks, immunity, elite/greater races, saves, and cooldowns still apply.
Meeting a size window is not a successful hit. The table distinguishes `S`,
`T`, and `B` because buffs and mounts do not affect every move alike.

| Move | Input | Allowed delta / size result |
|---|---|---|
| Charge | T | −1 through +1; mismatch can topple the charger with lag and starts combat; successful charge's extra knockdown requires target T ≤ actor T |
| Bash | T | −1 through +1; mismatch makes basher sit and wait; horse/spider-body target additionally must be strictly smaller |
| Tackle | T | −1 through +1; mismatch spends lag; horse/spider-body target must be strictly smaller, otherwise tackler sits with lag |
| Maul | T | −1 through +1; horse/spider-body target must be strictly smaller; mismatch seats the actor, with a chance of half-damage clipping |
| Roundkick | T | −1 through 0 |
| Headbutt, including double headbutt | T | −1 through +1, standing target; smaller/larger target also changes damage as detailed below |
| Shieldpunch | T | −1 through +2; otherwise no effective strike after the command's lag |
| Sweeping thrust | T | −1 through +3; otherwise fails and engages |
| Bodyslam | T | −2 through 0; larger or excessively small target fails with lag |
| Springleap | T | 0 through +1; horse/spider-body target must also be no bigger, leaving **equal size only** for those bodies |
| Trip | T | 0 through +1; the earlier horse/spider/quadruped-body check conflicts with this interval, so those targets have **no passing size combination** |
| Gaze | T | −2 through +1; delta −2 or +1 multiplies chance by 0.6; outside window fails with lag |
| Restrain | T | −2 through +2; delta ±2 multiplies chance by 0.6; outside window fails with lag |
| Garrote | T | −1 through +1, regardless of target posture |
| Legsweep | T | −1 through +1; delta ±1 multiplies chance by 0.75; outside window makes actor prone with lag |
| Backstab | T | Normally −1 through +1 for a standing target; posture/awareness exceptions below |
| Sneaky strike preparation | **B** | −1 through +1; otherwise refuses to schedule the attack |
| Throat crush | S | −1 through +1 |
| Dragon punch | S | −1 through +1 (`dragon_punch_size_gap()` = 1) |
| True strike | S | −1 through +1 |
| Capture | S | −1 through 0 |
| Ogre roar | S | Any delta ≤ 0; bigger targets are unimpressed; Illithid and Planetbound Illithid also immune |
| Branch pickup | T | Any delta ≤ 0; adds `10 × (actor T − target T)` to chance before the configurable multiplier and cap |
| Webwrap | T | Any delta ≤ +1; no lower size limit |

Sources:
[charge](../../../src/cmd/actoff.c#L1720),
[bash](../../../src/cmd/actoff.c#L8623),
[tackle](../../../src/cmd/actoff.c#L9254),
[maul](../../../src/cmd/actoff.c#L10282),
[roundkick](../../../src/cmd/actoff.c#L5837),
[headbutt](../../../src/cmd/actoff.c#L6469),
[shieldpunch](../../../src/cmd/actoff.c#L10483),
[sweeping thrust](../../../src/cmd/actoff.c#L10763),
[bodyslam](../../../src/cmd/actoff.c#L11699),
[springleap](../../../src/cmd/actoff.c#L11985),
[trip](../../../src/cmd/actoff.c#L12390),
[gaze](../../../src/cmd/actoff.c#L13224),
[restrain](../../../src/cmd/actoff.c#L13548),
[garrote](../../../src/cmd/actoff.c#L14189),
[legsweep](../../../src/cmd/actoff.c#L14334),
[backstab](../../../src/cmd/actoff.c#L7870),
[sneaky strike](../../../src/cmd/actoff.c#L7281),
[throat crush](../../../src/cmd/actnew.c#L3821),
[dragon punch](../../../src/classes/new_skills.c#L2482),
[true strike](../../../src/classes/new_skills.c#L4785),
[capture](../../../src/classes/new_skills.c#L4180),
[ogre roar](../../../src/classes/new_skills.c#L3478),
[branch](../../../src/classes/innates.c#L5187),
[webwrap](../../../src/classes/innates.c#L5263).

Important qualifications:

- A backstab target more than one category smaller is rejected only when awake
  **and** above kneeling. A target more than one category bigger is rejected
  whenever above kneeling, without the awake requirement. Kneeling/sitting/prone
  removes both of these size rejections; it does not bypass other admission rules.
- Charge's extra knockdown has a `!number(0,2)` gate (one in three) after its
  successful-hit branch, and only for a target no bigger than the charger.
- Maul's wrong-size clip uses `number(0,3)==0` (one in four), deals half damage,
  and still leaves the mauler sitting and lagged.
- Bash and tackle additionally test **the actor's** `RACE_QUADRUPED` in their
  body-size condition. It must not be silently described as a check of the
  target's quadruped race. `isBashable()` checks horse body but omits spider body;
  its result therefore does not establish that the actual bash will pass.
- `isMaulable()` uses the ±1/body-smaller test. `isSpringable()` also uses ±1 and
  requires a horse/spider-body target strictly smaller, unlike the actual
  springleap command's `[0,+1]` window/equal-body case. These are AI/admission
  helper discrepancies, not alternate player command rules.
- Trip's body contradiction follows directly from requiring `actor ≥ target+1`
  in the early body check and `target ≥ actor` later. Growth does not resolve it.
- Gaze/restrain have separate posture penalties, and shared `takedown_check()`
  applies other defenses after some size adjustments. Size does not bypass
  Freedom of Movement, evasion, footing checks, or other applicable defenses.

[Maul clip roll](../../../src/cmd/actoff.c#L10145),
[isBashable](../../../src/cmd/actoff.c#L8283),
[isSpringable](../../../src/cmd/actoff.c#L13905),
[shared takedown checks](../../../src/cmd/actoff.c#L422).

### Cost of a size mismatch

These are the `CharWait` requests on the relevant command path with the
committed tuning, expressed in seconds (`PULSE_VIOLENCE=16`, `WAIT_SEC=4`).
They are not guaranteed wall-clock recovery times when other lag, status,
or command admission conditions also apply. “No added size lag” does not
cancel lag already imposed by casting or another action.

| Attempt | Size-related failure cost |
|---|---|
| Charge | 8-second command lag already imposed; mismatch always makes actor sitting or prone, each with a 50% roll; idle target starts fighting actor |
| Bash | 2 seconds; actor sits |
| Tackle outside ±1 | 2 seconds; no extra posture change in that branch |
| Tackle body-size rejection | 4 seconds; actor sits |
| Maul mismatch | 6 seconds; actor sits even if its 25% half-damage clip occurs |
| Headbutt outside ±1 | Refuses without an added size-specific lag; the separate non-standing-target refusal requests 1 second |
| Shieldpunch mismatch | 8-second command lag already imposed (`skill.shieldpunch.lag=2` rounds, fallback 1 round) |
| Sweeping thrust mismatch | 6-second command lag already imposed (`skill.SweepingThrust.lag=1.5` rounds) |
| Bodyslam mismatch | 12 seconds |
| Springleap outside its interval | 8 seconds; actor sits; its earlier body rejection sits actor without its own added wait |
| Trip outside its interval/body check | Actor sits; ordinary too-small/too-big branches also stop singing; those branches add no separate size wait |
| Gaze mismatch | 2 seconds |
| Restrain mismatch | 6 seconds |
| Legsweep outside ±1 | 2 seconds; actor becomes prone |
| Physical disguise mismatch | 8 seconds |
| Illusion mask mismatch | 4 seconds |

The size intervals remain as listed above; this table explains why testing an
unreachable size window can be costly even when it deals no damage.
[Command lag helpers](../../../src/cmd/actoff.c),
[disguise helpers](../../../src/classes/disguise.c),
[mask helper](../../../src/classes/sillusionist.c#L1141),
[committed command properties](../../../lib/duris.properties#L2117).

### Matchups on the ordinary roster

For an unmodified, unmounted ±1 move, the following matrix is the size test
alone. Bodies and all the other conditions above can still reject it.

| Actor \ target | Small | Medium | Large | Huge |
|---|---|---|---|---|
| Small | Pass | Pass | Fail | Fail |
| Medium | Pass | Pass | Pass | Fail |
| Large | Fail | Pass | Pass | Pass |
| Huge | Fail | Fail | Pass | Pass |

Examples: a Small character enlarged to Medium can throat-crush a Large target;
an unmodified Huge actor cannot throat-crush Medium. Reducing Huge to Large
opens Medium but closes Giant. Sneaky strike does not follow these buff changes
because it uses `B`. A Medium rider on a sufficiently large mount has `T=Large`
for headbutt/bash, while throat crush still sees that rider's `S=Medium`.

### Kick: size changes follow-up control, not its base damage

`kick()` calculates its ordinary hit/damage before the size-dependent follow-up.
There is no ±1 admission window for the ordinary kick. If `abs(delta)<2`, it
returns after that damage without this size follow-up. Otherwise:

```text
follow-up chance = 4 * abs(target T - actor T)
NPC actor with no master: truncate(chance * 1.2)
PC Centaur/Ogre/Firbolg/Barbarian/Troll actor: truncate(chance * 1.4)
then shared takedown_check, without agility and footing checks
non-standing target: chance /= 5
Centaur actor: chance *= 2
```

An actor at least two sizes bigger can kick the target through a random exit;
blocked forced movement makes the target prone, can stun, stops its combat,
and imposes wall-impact lag. Successful departure also makes it prone and lagged.
An actor at least two sizes smaller can instead groin-kick a humanoid to sitting,
potentially stun it, stop its combat, and impose lag, with the additional
`number(0,10)==0` gate (one in eleven). The wall/groin stun roll is
`number(0,24)==0` (one in twenty-five), before `Stun()`'s own defenses. The
final comparison is strictly `chance > number(1,100)`,
and the initial random number is reused. Race-specific quick kick damage/lag for
Centaur/Dragon is separate from size arithmetic.
For a size gap of at least two, the shared check can also make the kicker hit
an incapacitated target again and impose its sleeping-target lag; the size-gap
early return prevents that follow-up path at gaps zero or one.
[Complete kick](../../../src/cmd/actoff.c#L4414),
[follow-up](../../../src/cmd/actoff.c#L4487).

### Headbutt and double headbutt damage

The first hit's damage is multiplied by the smaller/larger-target property;
it is not multiplied once for every category of difference. Standing admission
already limits the difference to one. Double headbutt derives its second hit
from half of that size-adjusted first damage, with integer truncation.

| Target compared with actor T | Committed property | Code fallback |
|---|---|---|
| Smaller | `damage.headbutt.damBonusVsSmaller=1.150` | 1.10 |
| Equal | 1.0 | 1.0 |
| Larger | `damage.headbutt.damPenaltyVsLarger=1.000` | 0.90 |

A backfire against a smaller target also increases the actor's self-damage by
half. Minotaur/Tiefling headbutt bonuses are independent racial multipliers.
The committed larger-target setting means the fallback 10% penalty is not the
checked-in tuning. These factors precede the actual damage delivery and defenses.
[Headbutt factors](../../../src/cmd/actoff.c#L6284),
[backfire/hit application](../../../src/cmd/actoff.c#L6603),
[properties](../../../lib/duris.properties#L2140).

### Dragon strike and trample

Both use rider/actor `T` and target `T`, not simply mount race or mount `B`.
Their damage can still happen when the size conditions eliminate knockdown.

| Target delta | Effect on knockdown/hit before subsequent defenses |
|---|---|
| +2 or more | Knockdown chance becomes 0; `vict_lag=1` |
| +1 | Knockdown chance halved, except Dragon Lancer for dragon strike / Knight for trample; centaur/drider target instead gets zero |
| 0, centaur/drider target | Knockdown chance becomes 0 |
| −1, or 0 without that body exception | No size adjustment |
| −2 or smaller | Hit chance ×0.9, knockdown chance ×0.2, `vict_lag=1`; waived at **exactly −2** for the relevant Lancer/Knight specialization |

Normal `vict_lag` is 2 combat rounds; 1 means one round (4 seconds with the
current pulse constants), and applies if a knockdown actually happens. A zero
knockdown chance is not one round of guaranteed target lag. Non-standing targets
also get zero knockdown chance. [Dragon strike](../../../src/cmd/actoff.c#L5588),
[trample](../../../src/cmd/actoff.c#L11396),
[pulse constants](../../../src/core/config.h#L84).

### Rearkick

Rearkick damage is multiplied by 3/4 when target `T > actor T+1`. Its follow-up
knockdown requires target at least two categories smaller and standing, with
base chance `5*(actor T-target T)`; NPC actors add 15 before shared defenses.
Other race/immunity checks can stop the follow-up. This is neither ordinary
kick's follow-up formula nor dragon strike's rule.
[Rearkick](../../../src/cmd/actoff.c#L11001).

## 4. Grappling and body mass damage

Bearhug, headlock, leglock, and groundslam use `S`, not mounted `T`. The configured
limits depend on whether the **target** is a PC or NPC; a player-owned pet still
counts as NPC for these tests. An ongoing hold is not continuously revalidated
by these admission checks merely because a size flag later changes.

| Move | PC target: allowed delta with committed properties | NPC target: allowed delta | Relevant fallback differences |
|---|---|---|---|
| Bearhug | −1 through +1 | −1 through +1 | `size.mob` fallback is 3, not committed 1 |
| Headlock | −1 through +1 | −3 through +3 | PC `size.down` fallback is 2, not committed 1 |
| Leglock | −1 through +1 | −3 through +3 | PC `size.down` fallback is 2, not committed 1 |
| Groundslam | −2 through 0 | −2 through 0 | `size.up` fallback is 2, not committed 0 |

`size.down` permits smaller targets and `size.up` permits larger ones. Groundslam
does not split PC/NPC limits and refuses horse/spider-body targets regardless of
size. Holds also require suitable humanoid/material bodies and posture/hold state;
passing the table is not sufficient.
[Bearhug](../../../src/combat/grapple.c#L354),
[headlock](../../../src/combat/grapple.c#L623),
[leglock](../../../src/combat/grapple.c#L1163),
[groundslam](../../../src/combat/grapple.c#L1489),
[committed grapple properties](../../../lib/duris.properties#L2411).

Successful groundslam's raw damage is:

```text
truncate((GET_WEIGHT(actor) / 5) * grapple.groundslam.dmgmod)
committed dmgmod = 1.0
```

This is **the actor's body weight**, not the target's, gear weight, or size ID.
It invokes raw damage and shield checks. A 150 lb actor supplies 30 before those
effects; enlarged to 300 lb supplies 60; reduced to 75 lb supplies 15. Titan
form alone does not increase that mass-derived amount. Both characters end up
prone and lagged on success. [Groundslam delivery](../../../src/combat/grapple.c#L1518).

Armlock and other grapple continuation/escape paths have no additional direct
size formula in the audited source. Their ordinary checks and the prerequisite
hold can still determine whether a size-sensitive sequence is reachable.

## 5. PvP melee crowding

`can_hit_target()` permits NPC attackers or NPC victims without this size budget.
For PC against PC it examines **other PCs already fighting that victim**:

```text
cost per existing opponent = 2^(opponent S)
target budget = 2^(target S+3)
reject if number of other PC opponents > 3
reject if their total cost > target budget
otherwise allow
```

The incoming/current actor's cost is not included; equality is allowed. Therefore
this is not the simpler rule “total size including the new attacker must fit.”
It is checked at engagement and melee-hit sites (including monk superhit), so
changes to size or opponents can also affect continued hits. It is not a global
cap on spells or every skill's direct damage call.

| Target S | Budget | Existing Huge PC cost | Sequential Huge PCs admitted from empty combat |
|---|---|---|---|
| Tiny (1) | 16 | 32 each | 1 |
| Small (2) | 32 | 32 each | 2 |
| Medium (3) | 64 | 32 each | 3 |
| Large (4) | 128 | 32 each | 4 |
| Huge (5) | 256 | 32 each | 4 |
| Giant (6) | 512 | 32 each | 4 |
| Gargantuan (7) | 1024 | 32 each | 4 |

This table assumes identical sequential arrivals and no other changes. Mixed
sizes/order matter because the candidate is excluded. Four PCs each the same
size as the target fit before the count cap binds. Existing participants can
subsequently fail their own hit checks if the other opponents grow or the target
shrinks. Being small can reduce exposure to many large melee attackers; enlarging
the target doubles its budget, while enlarging an attacker doubles the cost it
imposes on the other attackers. Mounts do not add the takedown-size step here.
[Budget and count](../../../src/combat/fight.c#L4171),
[hit gate](../../../src/combat/fight.c#L7943),
[engagement gate](../../../src/combat/fight.c#L8889),
[monk gate](../../../src/combat/fight.c#L11353).

## 6. Movement, information, tracking, and recovery

### Mount admission and burden

Mounting is refused if rider `B > mount B+1`. This permits a rider one stored
category bigger than the mount; it does not require the mount to be bigger.
Enlarge/reduce/titan form does not change this particular test. Conversely, the
mounted combat bonus uses both parties' effective `S`, as defined earlier.
Thri-kreen and Drider cannot ride, and other mount/terrain/consent/shape rules
apply independently. [Mount command](../../../src/classes/mount.c#L234).

`total_carried_weight(mount)` includes the rider's **stored** body weight plus
the rider's carry weight. It does not use `GET_WEIGHT(rider)`. Consequently a
heavier racial body burdens its mount, but an enlarge flag's doubling of body
weight does not double this particular rider burden. Encumbrance/movement uses
this total; carry capacity itself comes from STR, not size ID.
[Burden](../../../src/core/utility.c#L4343),
[carry capacity](../../../src/core/utils.h#L612),
[overloaded movement](../../../src/cmd/actmove.c#L1460).

### Wall of Air and web walls

Wall of Air uses the walker's **B**, ignoring category changes from ordinary
enlarge/reduce/titan form. Its base chances are:

| B | Base pass chance | Base fall chance after a failed pass |
|---|---|---|
| None/Tiny/Small | 15% | 20% |
| Medium | 25% | 15% |
| Large/Huge | 50% | 10% |
| Giant/Gargantuan | 70% | 0% |
| Default/invalid | 0% | 100% |

Add integer `(current AGI + current STR)/50` to pass chance and subtract it from
fall chance. Two independent 1–100 rolls are used: falling is tested **only
after failing to pass**. For example, with AGI=STR=100, Small passes 19% and
falls on `81%*16%=12.96%` of all attempts; Large passes 54% and falls on
`46%*6%=2.76%`. Successful passage triggers follower handling, but each follower
executes its own command. Spells can indirectly change these stat terms even
though the size category input remains `B`.
[Base chances](../../../src/classes/ethermancer.c#L4953),
[wall resolution](../../../src/specs/specs.object.c#L6670).

A web wall, after entry and its paralysis/save handling, receives a dispel cast
at level `45+S` from the walker. Bigger effective size therefore increases that
dispel's input level (47/48/49/50 for ordinary Small/Medium/Large/Huge), not a
guaranteed automatic break or immunity to the web.
[Web wall](../../../src/specs/specs.object.c#L6445).

### Shout/yell range

`do_yell()` computes `radius = map.shout.range + B*map.shout.sizeFactor`, then
compares squared map distance with `radius²`. Committed inputs are 40 and 4:
Small 48, Medium 52, Large 56, Huge 60 map units. It remains restricted to the
same zone; indoors it reaches only the same room. Non-map zone shouts do not
gain a distance restriction from this formula. Silence, underwater conditions,
race speech restrictions (including Thri-kreen/Illithids), and recipient toggles
still apply. Ordinary growth flags do not expand the radius.
[Yell](../../../src/cmd/actcomm.c#L2031),
[map distance](../../../src/world/map.c#L330),
[properties](../../../lib/duris.properties#L151).

### Improved listen and visual size information

For distant emotes that the listener detects, a smaller **B** emoter can be
anonymized as “someone ... scurrying about.” This occurs when
`number(70,90) > max(75, improved_listen_skill)`. Conditional on reaching that
check, it is 15/21 at skill ≤75, 10/21 at 80, 0 at ≥90. It compares the
emoter's `B` with the listener's `B`; growth flags do not affect that comparison.
This is a specific emote identification rule, not a universal sneak/hide bonus.
[Listen thresholds](../../../src/net/listen.c#L133),
[emote handling](../../../src/net/listen.c#L273).

Character inspection/room listings and `attributes` display effective `S` through
`size_types`; attributes displays `GET_HEIGHT`/`GET_WEIGHT` too. This can disagree
with the stored input used by an individual command. Map NPC markers require
NPC `B >= Small`; Tiny NPCs/images/pets do not get that marker through this test.
PC map markers are handled separately, so a reduced PC is not hidden by it.
[Inspection](../../../src/cmd/actinf.c#L1130),
[attributes](../../../src/cmd/actinf.c#L5340),
[NPC map markers](../../../src/world/map.c#L810).

### Track lifetime

After terrain, racial terrain exceptions, fly/sneak, and Dragonkin adjustments,
`add_track()` adds `GET_WEIGHT(character)/10` to its decay duration, then clamps
to 10–90 seconds in pulses (`WAIT_SEC=4`). Body pounds are added as **pulses**,
not seconds: 150 lb adds 15 pulses (3.75 seconds), 300 lb adds 30 pulses
(7.5 seconds), before clamping. A terrain already at the cap can erase the
difference. Mount tracks add another 15 seconds **after** that clamp.
Pass Without Trace and certain race/flight cases suppress tracks entirely.
Heavy does not universally mean “easier to find”; it changes persistence here.
[Track creation](../../../src/cmd/track.c#L472),
[weight/clamp](../../../src/cmd/track.c#L600),
[mounted extension](../../../src/cmd/track.c#L640).

### Dragging a living character and handling a corpse

Dragging an incapacitated/dying PC requires:

```text
GET_WEIGHT(target) + total_carried_weight(target)
    <= 1.75*CAN_CARRY_W(dragger) - total_carried_weight(dragger)
```

Untrusted actors cannot use this branch to drag NPCs. A heavier racial body,
or enlarge on the target, makes rescue harder; reduce makes it easier. The
dragger's own body mass is not added to their burden by this expression, though
their changed STR can alter capacity. Other vitality/movement conditions remain.
[Character dragging](../../../src/cmd/actmove.c#L3767),
[MAX_DRAG](../../../src/core/config.h#L64).

PC corpse creation records `corpse->weight=GET_WEIGHT(dead character)` and
records the carried-content weight separately in `CORPSE_WEIGHT`. Do not confuse
body mass with the saved contents-weight counter. Thus a flag active at death
can affect recorded corpse body weight. Object dragging compares
`GET_OBJ_WEIGHT(corpse)` with the same `1.75*capacity-current load` allowance;
the getter uses nonnegative current object weight. Later content-weight changes
also propagate through object weight handling, so this is not a second read of
the deceased character's size. Taking/looting additionally has its own corpse
access and item-capacity rules. NPC corpse weight follows a different
carried-weight formula. [Corpse creation](../../../src/combat/fight.c#L1770),
[object drag gate](../../../src/cmd/actmove.c#L3877),
[object weight getter](../../../src/core/utils.h#L607),
[weight propagation](../../../src/world/handler.c#L5369).

## 7. Disguise, shapechange, and size-changing abilities

### Access to assumed appearances/forms

| System | Size requirement | Does passing it assign the copied numeric size? |
|---|---|---|
| Physical disguise | Actor S within ±1 of saved target B, or the predefined disguise entry's size | No; appearance is stored in disguise fields |
| Illusion mask | Actor S within ±1 of target S | No |
| Clone form | Actor S may be at most one bigger than target S; no corresponding upper limit on how much bigger the target may be | No |
| Learn an animal shape | Actor S must equal creature S exactly | No; learns a form; actual shapechange changes disguise fields |
| Use an already learned shape | No active size recheck; old check is commented out | No |
| Corpseform (currently disabled) | Dormant code requires actor S within ±1 of `race_size(corpse race)` | Dormant code changes current race and installs tag; effective S then uses that lookup |
| Animal growth | Animal's B within ±1 of caster S | Casts enlarge/reduce **on caster**, not animal; equal size does nothing |

These are size rules, not complete form eligibility. Trusted staff bypass some
appearance restrictions. The disabled corpseform code additionally rejects several body races and
unusable corpses. In particular its Barbarian corpse comparison uses Medium
from the lookup, not the Large assignment of a living Barbarian.
[Disguise](../../../src/classes/disguise.c#L303),
[mask](../../../src/classes/sillusionist.c#L1212),
[clone](../../../src/classes/sillusionist.c#L2154),
[shape learning](../../../src/cmd/actnew.c#L2647),
[shape reuse](../../../src/cmd/actnew.c#L2819),
[corpseform](../../../src/classes/necromancy.c#L3308),
[animal growth](../../../src/magic/magic.c#L23024).

### Spell and innate packages

The following attribute changes accompany the **spells**, not every size change.
`base.X` refers to the character's `base_stats` value; integer divisions truncate.
Max-stat modifiers are not a promise that current stats rise by that amount.

| Source | Category effect | Attribute package and duration |
|---|---|---|
| Enlarge spell | S +1 via enlarge bit | Max STR `+base.Str/10`, max CON `+base.Con/4`, current AGI `−base.Agi/5`, current DEX `−base.Dex/5`; 3 game hours |
| Reduce spell | S −1 via reduce bit | Current STR `−base.Str/4`, current CON `−base.Con/5`, max AGI `+base.Agi/5`, max DEX `+base.Dex/5`; 3 game hours |
| Enlarge innate | S +1 via enlarge bit | No spell stat package; 5 game hours |
| Reduce innate | S −1 via reduce bit | No spell stat package; 15 game hours |
| Infuriate enlarge branch | S +1 | Max STR `+base.Str/12`, max CON `+base.Con/7`, AGI/DEX each `−base/3`; 3 game hours |
| Infuriate titan branch | S +2 | Max STR `+base.Str/10`, max CON `+base.Con/5`, AGI/DEX each `−base/5`; 3 game hours; titan alone does not change mass |

The enlarge spell first rejects elemental form/titan form and requires consent
for another target. Reduce can be hostile subject to a save. On opposite flags,
the spells remove the opposite bit and its matching spell affects and return;
one cast is cancellation, not a two-category jump. Recasting the same spell
refreshes durations, without stacking category increments. Stored Tiny/Gargantuan
checks use `B`, not the final clamped `S`. In particular the early Tiny reduce
check can refuse a Tiny base even when it currently has enlarge.

The innates are different paths: innate reduce does not first remove enlarge,
and innate enlarge does not first remove reduce. Both bits may therefore coexist,
which makes the effective-size and mass precedence distinction relevant. Items
can supply the bits too. An innate spell record already present also affects
whether a subsequent spell applies a new package or merely refreshes it.

Infuriate requires berserk and rejects existing enlarge/titan form; its titan
branch occurs when skill rating is at least `number(70,100)`. At rating 100 it
always selects titan, at 70 it does so 1/31 of attempts. Elemental form's growth
wording/attribute package does not itself add a category in `GET_ALT_SIZE()`;
the elemental-form bit is absent from that calculation.
[Enlarge/reduce](../../../src/magic/magic.c#L23071),
[innates](../../../src/classes/innates.c#L2765),
[infuriate](../../../src/cmd/actoth.c#L920),
[elemental form](../../../src/magic/magic.c#L17172).

World/item procs can invoke the same spells rather than a new size system,
including [Shabo's size-changing effects](../../../src/specs/specs.shabo.c#L169),
[Winterhaven](../../../src/specs/specs.winterhaven.c#L673), and
[Undermountain](../../../src/specs/specs.undermountain.c#L937). Equipment may grant
enlarge/reduce/titan flags directly. Their extra stats, triggers, availability,
and coexistence rules must be read from that item, not inferred from its size bit.
Wither's “decrease in size” messages do not change the category: that branch
applies hitroll/damroll/AC effects, not a size flag.
[Wither](../../../src/magic/magic.c#L2405).

## 8. NPC, pet, item, and zone-specific interactions

These are checked-in dispatch/proc behaviors, not proof that a particular NPC,
item, or proc is currently present in a deployed world. They matter to PC size
both as incoming threats and as player-controlled pet abilities.

| Effect | Size input and exact consequence |
|---|---|
| Construct room toss | Per eligible target, `(number(0,9)-2) > target S`; conditional chance is `(7-S)/10`: Tiny 60%, Small 50%, Medium 40%, Large 30%, Huge 20%, Giant 10%, Gargantuan 0%; makes target prone, stops fighting, one round lag |
| `lightning` item's rubbed whirlwind | Same effective-size probability as construct; prone, stops fighting, 0.7-round lag; additional hostility/group/safe-room/500-second timer gates |
| Xorn pet charge | On its one-in-ten combat trigger, target **B** must be Tiny through Giant; if not already prone/sitting/kneeling, seats and lags it for one round; Gargantuan B is too big |
| Golem pet throw/hug | On its one-in-ten trigger, B above Giant exits. B ≤ Small gets a throw attempt through an exit or wall impact (1–30 HP loss on blocked throw), sitting/lag as applicable. The later hug requires target S between golem S−2 and golem S, plus other checks |
| Djinni pet whirlwind | On its combat proc and each additional eligible one-in-eleven selection, B above Giant resists lifting; otherwise target sits with one-round lag |
| Giantbane weapon | Requires target **B exactly Giant**, and not Dragon; one-in-twenty melee proc casts level-51 Bigby's clenched fist. Enlarging Huge to effective Giant alone does not qualify |
| Vecna vampire-name defensive item proc | After its damage, kneels a standing victim if the NPC wearer's B ≥ victim B; requires a non-PC, non-PC-pet wearer and the name branch, and compares stored sizes |
| Snow Ogre berserker toss collision | The collision calls `damage(second PC, first PC, GET_WEIGHT(second PC)/2, TYPE_UNDEFINED)`. The **first** thrown PC takes damage based on the **second** PC's mass; both are stunned and stopped. Do not reverse the damage direction |

Construct's outer activation gate also has its own random roll; percentages above
are conditional on reaching the per-target comparison. Likewise the other proc
rolls are not per-round overall effectiveness estimates.
[Construct](../../../src/specs/specs.mobile.c#L11678),
[whirlwind item](../../../src/specs/specs.underworld.c#L419),
[Xorn](../../../src/specs/specs.mobile.c#L13215),
[Golem](../../../src/specs/specs.mobile.c#L13302),
[Djinni](../../../src/specs/specs.mobile.c#L13444),
[Giantbane](../../../src/specs/specs.jot.c#L315),
[Vecna](../../../src/specs/specs.vecna.c#L1583),
[collision](../../../src/specs/specs.snogres.c#L341).

The assignment table binds construct to mobile 22956; golem/Xorn/Djinni to
1121/1122/1132; Giantbane to object 96066; `lightning` to object 24406;
berserker toss to mobile 87700. Despite its name, `mob_vecna_procs` is assigned
to object 130038 as a defensive item proc; its size-dependent vampire branch
requires an NPC wearer that is not a PC pet.
[Assignments](../../../src/specs/specs.assign.c).

### NPC target selection changes what PCs are subjected to

`pick_target()` supports `PT_SMALLER` (actor T strictly bigger), `PT_BASH_SIZE`
(±1 T), and `PT_TRIP_SIZE` (target T equal or one bigger). `PT_SIZE_TOLERANT` can
retain a candidate before those size filters; `PT_TOLERANT` instead retains one
after them. An active taunt target is returned before the normal picker loop.
The size flags therefore are not absolute immunity guarantees.
Mercenary/thief/start-fight AI also uses effective-size windows for selecting
grapple, tackle, backstab, and bodyslam attempts; some differ from the eventual
command's exact admission tests. Branch/webwrap selection uses the stricter
`PT_SMALLER` even though the abilities themselves permit some larger/equal targets.
[Picker](../../../src/mob/mobact.c#L150),
[mercenary AI](../../../src/mob/mobact.c#L5914),
[branch/webwrap AI](../../../src/mob/mobact.c#L6415),
[fight-opening selection](../../../src/mob/mobact.c#L6881).

### NPC size producers and copies

NPCs may use explicitly authored sizes, race-derived defaults, or spell-assigned
sizes. They are not limited to the PC creation table. Necromancy, elemental,
living-stone, titan/avatar/demon, random-NPC, and item-summoning paths assign
their own stored sizes, which then feed all applicable checks above.
Reflection/mirror/projected-image paths copy stored size; size flags are separate
state. Pet/generated-NPC save/restore also captures stored size. The world map
distinguishes Tiny NPCs as described earlier.
[NPC conversion](../../../src/mob/mobconv.c#L111),
[random NPC sizes](../../../src/world/random.mob.c#L644),
[reflection copy](../../../src/classes/sillusionist.c#L1094),
[mirror copy](../../../src/magic/magic.c#L2583),
[projected image](../../../src/classes/innates.c#L3128),
[pet restoration](../../../src/player/pet_restore_runtime.c#L89),
[generated NPC restoration](../../../src/world/generated_npc_runtime.c#L57).

Training dummies use `race_size(profile race)` rather than player
`set_char_size()`. A Barbarian-profile dummy is therefore Medium, and the other
five mismatching PC races likewise follow the lookup column. This matters when
designing a race-specific size comparison journey.
[Dummy profile](../../../src/combat/training_dummy.c#L237).

## 9. Related racial rules that are not numeric size rules

These explain otherwise misleading balance conclusions. They are not bonuses
gained by changing `B`, `S`, height, or weight alone.

- **One-handed use of two-handed weapons:** `wield_item_size()` charges one hand
  for a weapon when `IS_GIANT(actor)`, otherwise the normal two-hand rules apply.
  The race predicate includes Giant, Ogre, Storm Giant, Minotaur, Snow Ogre,
  Firbolg, Fire Giant, Frost Giant; it does not test effective Giant size.
  Ordinary Ogre/Minotaur/Firbolg get the discount; an enlarged Human does not.
  It is a weapon discount, not a general discount for any two-handed held item.
  Hand capacity remains two, or four with the separate four-hand trait.
  [Predicate](../../../src/core/utils.h#L770),
  [weapon hand cost](../../../src/cmd/actobj.c#L104),
  [hand accounting](../../../src/cmd/actobj.c#L5608).
- **Ogre offhand weight allowance:** for non-Rangers without four hands,
  the secondary-weapon weight test uses `weight*2 <= STR wield allowance` for
  Ogre/Snow Ogre instead of `weight*3 <= allowance`. Four-handed actors bypass
  that block; reach-weapon and training rules still apply. This is another race
  identity rule: it is not shared by all Huge races or gained through enlarge.
  [Offhand admission](../../../src/cmd/actobj.c#L6587).
- **Dwarf giant avoidance:** Mountain Dwarf's innate multiplies the pre-clamp
  dodge score by 1.10 specifically against Troll, Ogre, or NPC Giant race.
  It does not compare sizes and is not the whole `IS_GIANT` roster; Firbolg and
  Minotaur do not qualify through this check. Reducing an Ogre does not remove
  it, and enlarging Human does not trigger it. This is score scaling, not an
  unconditional ten-percentage-point increase to final dodge probability.
  [Grant](../../../src/classes/innates.c#L488),
  [dodge application](../../../src/combat/fight.c#L9326).
- **Horse/spider bodies, legs, material form:** these independently change
  takedown admission. Size does not turn a humanoid into a centaur or restore
  missing legs. Thri-kreen four hands and centaur equipment slots are also
  anatomical rules, not generic Small/Medium/Large/Huge equipment fitting.
- **Giant foraging and Jotun access/fear:** `IS_GIANT` enables the fallback
  uprooting branch of forage, exempts its races from Utgard-Loki's vision/fear
  processing, and permits Mimer's west passage below level 51. These persist
  under ordinary reduce and are not acquired by ordinary enlarge.
  [Forage](../../../src/cmd/actoth.c#L1736),
  [Loki](../../../src/specs/specs.mobile.c#L9259),
  [Mimer](../../../src/specs/specs.mobile.c#L9374).

Item `size` labels (`ITEM_SIZE_*`) and shield-size constants describe item data.
The character object-size getter is used for item inspection, not a general
body-size fit gate in the audited wear/wield path. Actual restrictions can still
come from race masks, class, slots, item weight/STR, ownership, and flags.
Monk equipment-weight penalties count equipment, not the monk's body pounds.
[Item label getter](../../../src/core/utils.h#L609),
[item display](../../../src/cmd/actinf.c#L953),
[monk attack weight](../../../src/combat/fight.c#L10413).

## 10. Balance implications and existing inconsistencies

These are deductions from the rules above, not measured performance rankings.

1. **There is no universally best size.** Small avoids many Huge ±1 moves and
   has a tighter PvP crowding budget, but loses reach against Large/Huge.
   Huge reaches Large/Huge and some big NPCs, but loses many moves against
   Medium/Small. Medium connects Small through Large; Large connects Medium
   through Huge. Skill kit and expected enemy roster determine the value.
2. **Growth is tactical.** It trades the target window in both directions,
   alters other participants' melee budget, and can change mass-based damage,
   rescue burden, or track lifetime. Reducing can be beneficial for an offensive
   size window while harmful through STR/CON loss. Titan shifts categories by
   two without the same mass effect. Evaluate the full source package.
3. **Ordinary physical appearance is an unreliable guide to category.** Dwarf
   height and centaur weight do not define their size tests; Drider's category
   and body restrictions are distinct. Equal-category races still differ in
   groundslam damage, rescue burden, mount load, and tracks through body mass.
4. **Stored/effective mixing produces surprising outcomes.** An enlarged Small
   PC looks Medium and changes throat-crush eligibility/crowding but retains
   Small shout radius, mount-admission size, Wall of Air size chance, Giantbane
   eligibility, and the pet procs' stored-size classifications. Attribute changes
   can still affect those systems through separate stat terms.
5. **There are six authority mismatches, not one shared racial size table.**
   Corpseform, tagged race changes, NPC race defaults, and dummy profiles can
   differ from creation/login. Barbarian and Death Knight go down one category
   via the lookup; Shadow Beast goes up one; Storm Giant/Wight go down two;
   Harpy goes up one. Do not “correct” documentation by silently merging them.
6. **Command/helper contradictions need explicit treatment in future changes.**
   Trip's body window is empty; springleap's helper disagrees with its command;
   bash's helper omits spider body; bash/tackle's quadruped check names the actor.
   Those are verified code observations, not proposed balance fixes in this file.
7. **Property fallback values are not the checked-in balance.** Headbutt and
   grapple differences above are material. A comparison must record actual
   effective configuration before treating an observed behavior as a race effect.

The audited category/mass readers do **not** establish generic size modifiers for
ordinary weapon damage dice, spell damage/saves, AC/hitroll, dodge/parry/block,
attack count, XP/epic rewards, hunger/thirst, ordinary walking/swimming speed,
or generic door/tunnel fit. Those may differ by race/class/stats/equipment,
and the explicitly listed size-sensitive control/movement paths still apply.
`specials.z_cord`/“height” in aerial combat and spell targeting is elevation,
not racial height. Group size, ship hull size, dice size, and buffer sizes are
also unrelated. Random kick messages about height/small size do not constitute
an additional size calculation.

## 11. Coverage and verification

This audit followed stored/effective/takedown size, physical height/weight,
`race_size()`, their assignments and consumers, direct struct field uses,
enlarge/reduce/titan affect bits, NPC selection flags, the giant-race predicate,
and item-size/weapon-hand handling. Block-commented legacy code was separated
from executable code. The source inventory covers these areas:

| Source family | Coverage |
|---|---|
| `core/common.c`, `core/defines.h`, `core/utils.h`, `core/utility.c` | Race/category definitions, physical macros, effective and mounted size, carry burden, giant predicate |
| `account/nanny.c`, `net/ws_handlers.c`, `cmd/actset.c`, `cmd/actwiz.c`, `cmd/actoth.c` | Creation/login, staff changes, old/unavailable physical and ascend/descend paths, infuriate |
| `cmd/actoff.c`, `cmd/actnew.c`, `classes/new_skills.c`, `combat/grapple.c`, `classes/innates.c` | All direct size-dependent offensive/grapple/innate checks and copied images |
| `combat/fight.c`, `classes/mount.c`, `cmd/actmove.c`, `cmd/actobj.c` | PvP crowding, corpse body weight, mount admission, drag/rescue, hand costs, giant avoidance |
| `classes/disguise.c`, `classes/sillusionist.c`, `classes/necromancy.c`, `magic/magic.c`, `magic/spells.c` | Appearance/form admission, growth packages, race-change lifecycle, image/pet sizes |
| `classes/ethermancer.c`, `specs/specs.object.c`, `cmd/actcomm.c`, `net/listen.c`, `cmd/track.c`, `cmd/actinf.c`, `world/map.c` | Wall/web interaction, communication, detection/display, tracks, map markers |
| `mob/mobact.c`, `mob/mobconv.c`, `world/db.c`, `world/random.mob.c`, `combat/training_dummy.c` | AI choices, NPC size loading/defaults/generation, dummy discrepancy |
| `specs/specs.mobile.c`, `specs/specs.underworld.c`, `specs/specs.jot.c`, `specs/specs.vecna.c`, `specs/specs.snogres.c`, `specs/specs.assign.c` | Every direct size/mass-dependent special proc found, plus giant identity zone hooks |
| `specs/specs.winterhaven.c`, `specs/specs.shabo.c`, `specs/specs.undermountain.c` | NPC size producers and indirect calls to the shared growth spells |
| `player/player_snapshot_capture.c`, `player/player_load_materialize.c`, `player/pet_restore_runtime.c`, `world/generated_npc_runtime.c`, `core/files.c` | Player/pet/generated-NPC persistence of stored physical fields |

Checks run for this documentation:

- A scratch C++ harness extracted the actual `race_size`, `set_char_size`,
  `set_char_height_weight`, `GET_ALT_SIZE`, `get_takedown_size`, `can_hit_target`,
  and `wall_of_air_chances` functions. With external character/affect/random
  services stubbed, ASan/UBSan passed all 37 PC base assignments, all 4,144
  combinations of PC race/stored size/growth flags/tag state, all 49 rider/mount
  category pairs, physical flag precedence/truncation examples, all seven wall
  categories, and the sequential Huge-attacker examples. Physical generator
  endpoint examples were evaluated through the actual function.
- `python3 tests/async/test_headbutt_feedback.py` passed its executable command,
  damage/ward, size-refusal, and feedback cases. It is not an exhaustive race
  balance test and uses property fixtures rather than live settings.
- `python3 tests/async/test_freedom_of_movement_takedown.py` passed its shared
  defense and backstab regressions.
- `python3 tests/async/test_race_command.py` passed all 37 profile/innate routes,
  race-specific specializations, restrictions, and overrides for both harness
  variants. `python3 tests/async/test_creation_all_races_toggle.py` passed.

The comprehensive claim is about the checked-in size mechanics and their
consumers, supported by source tracing and focused execution. No live staff
gameplay, deployed property inspection, production operation, population study,
or end-to-end booted journey of every proc was performed. No C/C++ source changed,
so a full server rebuild was not required. Generated harness artifacts stay
under ignored `bin/` and are not documentation inputs.

For maintenance, repeat repository searches for `GET_SIZE`, `GET_ALT_SIZE`,
`get_takedown_size`, `race_size`, `GET_HEIGHT`, `GET_WEIGHT`, direct
`player.size/height/weight` uses, the three affect bits, `IS_GIANT`,
`PT_SMALLER/PT_BASH_SIZE/PT_TRIP_SIZE`, and `wield_item_size`. Inspect full
function bodies and property values, not just matched lines. Extend this
reference when a new consumer or race is added. Keep unrelated racial mechanics
in their own pages rather than assuming their effects follow from size.
