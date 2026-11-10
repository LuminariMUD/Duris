# PC race combat resolution: damage, defenses, control, and sustain

Source review: 2026-11-08, checkout `afdd1fd4a40f27e5cc3f7686dcbb3de9f0ec2318`.
This reference describes the checked-in server and `lib/duris.properties`, not
deployed overrides or measured race win rates. No gameplay is changed.

See [race-combat-resolution-issues.md](race-combat-resolution-issues.md) for
potential defects, their gameplay effects, recommended fixes and distinctions
between implementation errors and balance-policy decisions.

This layer connects [stats](race-stats.md), [size](race-size.md),
[innates](race-innates.md), and [tempo](race-tempo.md): what happens to an
attempted action, how much reaches the target, and what it changes afterwards.
All 37 PC race IDs are covered, including the 21 ordinary creation races and
16 restricted/legacy IDs. A comparison fixture is not permission to create an
otherwise illegal race/class combination.

The source is the authority where an older layer describes a superseded path.
Suspected defects are identified as interpretation limits; they are not silently
replaced with an imagined fixed implementation or used to recommend balance
changes. In particular, the current Leap check requires innate ownership and
its level unlock, and shield block no longer contains the old unused Luck
calculation.

## 1. Resolution routes and comparison boundaries

There is no universal attack pipeline. The caller decides which admission,
accuracy, saving-throw, and defense checks run before damage delivery.

| Entry route | Main sequence | What is not automatically included |
|---|---|---|
| Recurring ordinary melee | `perform_violence` → `pv_common` → `hit` → `melee_damage` → `raw_damage` | A skill that calls `melee_damage` directly does not inherit the earlier parry/block/dodge chain or ordinary hit roll. |
| Monk HP-based attack slot | `calculate_attacks` selects `WEAR_NONE` → `monk_superhit` → physical/raw delivery with `NOREDUCE` | This slot bypasses `pv_common`, ordinary accuracy/critical construction, and many reductions. |
| Physical skill | Command-specific admission, contests and payload → selected damage API | Size, target restrictions, saves, engagement and lag differ by command. |
| Archery | `do_fire` admission and accuracy → projectile block → `melee_damage` with arrow flags | It does not execute `pv_common` or ordinary weapon critical construction. |
| Damage spell | Handler-specific admission, saves and base damage → `spell_damage` → `raw_damage` | `spell_damage` does not add a universal `NewSaves` roll. |
| Status spell | Handler-specific shrug/saves/immunities → affect or control helper | A non-damaging spell need never enter either damage pipeline. |
| Direct raw damage | Caller → `raw_damage` | Ordinary accuracy, melee armor/skins, and spell shrug/element predicates are absent unless the caller performed them. Raw damage still has modifiers and flags. |
| Retaliation/proc | Trigger-specific tests → one of the above APIs | Its damage type, flags, target and trigger frequency must be inspected separately. |

Sources: [round execution](../../../src/combat/fight.c#L10989),
[ordinary defenses](../../../src/combat/fight.c#L11436),
[hit construction](../../../src/combat/fight.c#L7905),
[melee delivery](../../../src/combat/fight.c#L5432),
[spell delivery](../../../src/combat/fight.c#L4418),
[raw delivery](../../../src/combat/fight.c#L6172),
[archery](../../../src/combat/range.c#L561).

Use **damage per attempted action**, including misses and complete negations,
when combining this layer with action frequency. Use **damage per landed hit**
only when the probability of reaching that hit is accounted for separately.
An avoided attack can also prevent its downstream proc or retaliation; a
reduced hit may still trigger them. A defensive message is not necessarily zero
HP loss: some paths later impose a one-point damage floor.

For an ordinary steady-state fixture:

```text
expected DPS = attempted rounds/second
             * expected executed attacks/round
             * expected HP damage/attempt
```

That product is conditional on target access, survival, resources, posture,
range and control. Finite skin charges, counters, changing targets, temporary
buffs and damage-triggered healing need a sequence of actions, not one average
multiplier. See [tempo comparison conditions](race-tempo.md#hold-the-comparison-conditions-explicitly).

## 2. Ordinary melee: admission, avoidance, and accuracy

### The defense chain precedes the hit roll

`pv_common()` runs these responses in short-circuit order:

1. Mangle.
2. Parry, including its possible riposte follow-up.
3. Divine Blessing parry.
4. Shield block, including possible shield retaliation.
5. Dodge, including mounted sidestep and Drow's additional check.
6. Leap.
7. Monk riposte.

The first successful response stops this attack before `hit()`. Afterwards,
equipped-object `CMD_GOTHIT` hooks run in a fixed slot order, then the NPC hook;
a handled hook also stops delivery. Only then does `hit()` construct its accuracy
and critical result. Thus “20% parry plus 20% dodge” is not 40% avoidance. With
independent eligible checks and no other changes it is `1 - .8*.8 = 36%`.
Actual eligibility and scores can change during preceding reactions.

This chain itself has gates: normal target status, the attacker's ability to
move, visibility/blindfighting, and a weapon-skill-notch condition. Shadow
Movement bypasses the ordinary defensive-skill chain, but not the later item
hooks. The current visibility gate reads **the attacker's** Eyeless innate;
do not reinterpret that as a guaranteed defender benefit. Direct callers of
`hit()` bypass `pv_common`, and direct callers of `melee_damage()` bypass both.
[Defense order](../../../src/combat/fight.c#L11436),
[mangle](../../../src/combat/fight.c#L3683),
[riposte](../../../src/combat/fight.c#L3883),
[equipment order](../../../src/combat/fight.c#L359),
[Eyeless review](race-innates-issues.md#f04--defense-eligibility-reads-the-attackers-eyeless-innate).

### Dodge, Leap, parry, and block

For ordinary dodge, using effective stats and current weapon skill:

```text
score = int(AGI * 1.20) - attackerWeaponSkill
if Giant Avoidance against Troll/Ogre/generic Giant: score = int(score * 1.10)
score += (STAT_INDEX(defenderAGI) - STAT_INDEX(attackerDEX)) / 2
score += defenderLevel - attackerLevel
chance = clamp(AGI/10, score, 50)
```

Integer division/truncation occurs along the path. Groundfighting while down,
or Gaze, halves the resulting chance; Dazzle divides it by five; stun leaves
6%; Monk then multiplies by 1.20; Zealot/Scoundrel adds five; a stunned attacker
increases it by 10%. The ordinary roll is `number(1,101) <= chance`.
Without Groundfighting, a downed defender normally fails admission before this
calculation. A raging defender cannot use it against someone other than its
current opponent. Mounted sidestep runs earlier with separate posture,
visibility and skill conditions.

**Drow:** when the dodge path is reached, an unstunned Drow with
`load_modifier < 100` first succeeds on `number(0,10)==0`. If that fails, the
ordinary roll remains available. For ordinary chance `q`, the combined result
is `1/11 + (10/11)*q`, not simply `q+10%`. The earlier admission restrictions
still apply. Battle Senses and the mounted Sanguinis Ignis state have their own
automatic-success branches here.
[Dodge](../../../src/combat/fight.c#L9335),
[helpers and Drow roll](../../../src/combat/fight.c#L9250).

**Leap:** current `leapSucceed()` requires `has_innate(INNATE_LEAP)`, standing
normal posture, and no Gaze. Its chance is
`clamp(1, AGI/7 - load_modifier/100 + (defenderLevel-attackerLevel)/2, 20)`
against 1..100. Native Thri-Kreen unlocks it at 21; Harpy at 1. These are
additional eligible defenses, not additions to dodge's percentage. No Leap
benefit should be credited below the current unlock.
[Leap implementation](../../../src/combat/fight.c#L9166),
[racial assignments](../../../src/classes/innates.c).

**Parry:** needs standing posture, a positive rating, an eligible defending
weapon, and an eligible attacking weapon/body. Flaying weapons have exclusions;
unarmed Monks/immaterial attackers have special admission. The defender adds
DEX reaction and WIS bonuses; the attacker adds STR hit and damage table
bonuses and any STR advantage exceeding 35. Class, specialization, opponent
selection, Luck, blindness, Gaze and stun modify the scores. The source writes
`MAX(5,number(1,score))` for each roll, with ties favoring the defender, but
`MAX` can evaluate the random call twice and defeat that apparent floor.
Use the actual draw behavior for quantitative comparisons; see
[the retained parry-roll issue](race-combat-resolution-issues.md#f16--parrys-supposed-floor-rolls-twice-and-is-intentionally-retained-today).
Stronger attackers generally defeat more parries even when their
ordinary hit chance is already capped. Groundfighting does not remove parry's
standing requirement.
[Parry](../../../src/combat/fight.c#L9892).

**Shield block:** needs a shield and a positive skill. Its score includes
`skill/4 + DEXreaction*2`, with Monk/flaying/Dazzle adjustments and a 1.20
multiplier while down. Attacker opposition is `WeaponSkill + STRhit*4`.
It succeeds when `random(0,attackerScore) <= random(0,defenderScore)`.
This is not the separate arrow-block formula. Skill advancement can cause an
individual block/parry check to fail; some other consumers treat advancement
as success, so deterministic comparisons should state their notching policy.
[Shield block](../../../src/combat/fight.c#L9521),
[Monk riposte](../../../src/combat/fight.c#L9725).

### Armor has two different jobs

`calculate_ac()` starts from stored AC, halves negative **PC** AC with the
committed `damage.neg.armorclass.multiplier=0.5`, adds load minus 75, Monk AC,
the nonlinear AGI defense term, and Rrakkma group AC. It clamps to -750..100.
Each other eligible Rrakkma holder contributes -10 here; its separate shrug
bonus has a holder cap. The AGI term and above-own-race AGI subtraction originate
in different functions and must not be counted as the same bonus twice.

- **Accuracy:** `chance_to_hit` uses only -100..100 of calculated AC, then
  applies its blindness adjustment. More negative AC beyond -100 therefore
  does not keep lowering this ordinary accuracy contribution.
- **Damage:** `melee_damage` uses the full calculated value through
  `damage *= 1 + calculatedAC/1000`. AC -100 gives .90, -500 gives .50,
  and -750 gives .25 before later stages. Positive AC increases damage.

Fist of Dragon can bypass beneficial AC and the skin stage on its successful
roll, while still allowing positive AC to increase the damage.
[Calculated AC](../../../src/combat/fight.c#L6764),
[accuracy use](../../../src/combat/fight.c#L6930),
[damage use](../../../src/combat/fight.c#L5476),
[AGI function](../../../src/world/handler.c#L5327),
[stat recalculation](../../../src/magic/affects.c#L921).

### Accuracy and criticals are related, but separate

The ordinary to-hit score uses class rate × level/6, weapon skill, a two-thirds
transform with a floor of 30, and `clamp(-10,hitroll*2,90)`. Bless and a Luck
roll can multiply it. Class rates are 10 for the main Warrior/knight group,
8 for the hitter/tank group, 7 for the rogue/Monk group, 6 for the clerical
group, and 4 for the mage group, with explicit specialization exceptions.
Multiclass membership follows the first matching branch.

`chance_to_hit` then adds alignment protections, visibility, posture,
immobility and armor effects and clamps to 1..100. `hit()` misses when its
1..100 roll is **greater than or equal to** that value, unless the critical
survives. Thus a displayed/calculated 100 permits 99 ordinary roll outcomes before fumble/other branches;
a critical can override that miss. This is distinct from skills that compare
with `>` or roll on 0..100.

The initial critical threshold is 8 below INT 105, otherwise
`8+(INT-100)/5`. Confirmation compares weapon skill plus Luck/4 with a roll
on 30..101; weapon-skill normalization, Amorphous Body, Quick Step and
Berserker defenses can alter the result. A normal critical doubles the payload;
Devastating Critical and Monk pressure-point paths have separate outcomes.
AGI also helps the weapon-fumble check. High INT is not an unconditional
percentage of extra final DPS.
[To-hit construction](../../../src/combat/fight.c#L6803),
[critical/fumble checks](../../../src/combat/fight.c#L7610),
[critical construction](../../../src/combat/fight.c#L8016),
[critical damage helpers](../../../src/combat/fight.c#L7770).

## 3. Melee payload and reduction

### What a landed ordinary attack starts with

For a wielded weapon on a PC, the weapon dice replace the initial unarmed/Monk
payload. A two-handed weapon multiplies those dice by 1.5. NPC equipment follows
a different additive route. The engine then adds a randomized damroll term:

```text
TRUE_DAMROLL = stored capped damroll + STR table damage
temp = int(TRUE_DAMROLL * 0.75)
temp = int(temp * random(90,100) / 100)
payload += temp
```

Critical multiplication follows this addition. Divine Force, Melee Master,
Vicious Strike, Anatomy, Boiling Blood, class damage, Orc room effects and
slaying are later conditional changes. A successful Battle Frenzy check can
deliver a separate physical hit before construction of the ordinary payload.
The class multiplier also affects archery, but it is not an automatic multiplier
on every skill or spell.
[Payload construction](../../../src/combat/fight.c#L8406),
[TRUE_DAMROLL](../../../src/core/utils.h#L527),
[late ordinary modifiers](../../../src/combat/fight.c#L8660),
[Battle Frenzy](../../../src/combat/fight.c#L11554).

The stored PC damroll cap is `int(50 * racialDamrollFactor)` once exceeded,
using the loaded float. **STR's table damage is added after this cap.** The
factor is neither a final damage multiplier nor a cap on total weapon damage.
For example, the saturated stored caps are Gnome 40, Human 50, Ogre 75, before
adding their STR contributions. Float rounding can affect an integer boundary;
the current Troll factor 1.18 produces a stored cap 58 in the executed fixture.

Follow-up on 2026-11-09: `damage.totalOutput.racial.*` is active with every
shipped entry reset to **1.000**, including NPC races; absent racial entries also
use 1.000. On 2026-11-10, `damage.totalOutput.playerRacial.*` adds a separate
1.150 factor for the six Large player races; NPCs do not receive it. Class factors are
unchanged, and multiclass PCs use the larger of their two class factors. Racial
and class factors multiply. Non-neutral factors appear as signed passive entries
in `race innates` and `class innates`; these apply to ordinary melee (including
unarmed attacks), archery and explicit consumers, not every spell or special
attack. See [modifier transparency](race-misc.md#3-visible-racial-and-class-attack-damage-modifiers).
The all-race table below records the separate damroll-cap factors.
[Damroll cap](../../../src/magic/affects.c#L929),
[table loading](../../../src/magic/affects.c#L3470),
[class selection](../../../src/magic/affects.c#L1920).

### Monk HP-based attack slots

Against a PC, `calculate_attacks()` can replace two remaining base Monk attacks
with one `WEAR_NONE` slot. The selection threshold is `level/2+9` against
1..100: 37% at 56 when at least two base attacks remain. The old comments
claiming 35% or a three-attack cost do not describe the actual decrement.
The round executor sends that slot directly to `monk_superhit`, bypassing the
ordinary `pv_common` defense chain and `hit()` accuracy/critical construction.

Its initial payload is `(targetMaxHP*.005)^2`. If below `MonkDamage`, it is
raised to that value; **otherwise** the branch caps it at225. With a sufficiently
low MonkDamage floor, maximum HP1000/2000/3000 gives25/100/225. The floor branch
can exceed225 if MonkDamage itself does, so225 is not an unconditional cap.
The attack still checks PvP crowding and ranks.

Delivery uses `PHSDAM_NOREDUCE | PHSDAM_TOUCH`: ordinary AC/skin reduction and
the raw-.75 baseline are bypassed, while other applicable stages such as
position, wards, enabled shared defenses, Touch healing and retaliation can
remain. A high-HP race therefore faces a different damage curve against this
route than against ordinary weapon hits. It is also distinct from the
sequential Slow/blind/lag/damage effects in `monk_critic()`.
[Slot construction](../../../src/combat/fight.c#L10449),
[HP-based delivery](../../../src/combat/fight.c#L11359),
[critical pressure points](../../../src/combat/fight.c#L7010),
[MonkDamage](../../../src/classes/new_skills.c#L656).

### Ordered physical delivery

After any required engagement, `melee_damage()` performs:

1. Unless `PHSDAM_NOREDUCE`: calculated AC, Troll Skin, Guardian's Bulwark,
   Berserk defense, rapier/dirk defense and offense, mounted knight offense,
   qualifying Soulshield, and Protection from Living.
2. Unless `PHSDAM_NOPOSITION`: Flank/Circle and victim posture. Standing
   Flank/Circle are 1.25/1.75; their bonuses are halved when the target is down.
   Kneeling/sitting/prone incoming multipliers are 1.15/1.30/1.50 without
   Groundfighting. Groundfighting does not erase Flank/Circle.
3. Berserker low-HP/rage offense, then integer damage-ward absorption.
   A ward reducing damage to zero exits here.
4. Earth Aura and Displacement negation checks when eligible; then selection
   of one skin, its fixed deduction, percentage reduction and charge use.
5. Dragonslayer and attacker/defender Dreadnaught changes, then minimum 1.
6. `raw_damage` with `RAWDAM_DEFAULT | flags | RAWDAM_NOWARD`.
7. If both survive: Warring Zeal's separate holy damage, eligible damage-shield
   reactions, and engagement response. Ordinary `hit()` then has its own
   subsequent class, Minotaur, poison and weapon proc hooks.

Troll Skin is **.85** in the committed file. Berserk defense is .90,
Soulshield melee .90 when its alignment/racewar predicate passes, and
Protection from Living .95 against a non-undead attacker. These are distinct
from the eventual shared raw-damage reduction.
[Physical delivery](../../../src/combat/fight.c#L5432),
[committed settings](../../../lib/duris.properties#L169),
[post-hit hooks](../../../src/combat/fight.c#L8711).

### Skins favor different incoming hit distributions

Only the first present skin in this precedence list is selected:

| Precedence | Skin | Share remaining after fixed deduction |
|---|---|---:|
| 1 | Stone Skin | .55 |
| 2 | Biofeedback | .45 |
| 3 | Shadow Shield | .70 |
| 4 | Ironwood | .80 |
| 5 | Ice Armor | .75 |
| 6 | Negative Energy Armor | .75 |
| 7 | Drakescale Aegis | .75 |

The selected skin first subtracts **46**. Its percentage stage runs only when
the remainder is greater than 10. The later minimum restores damage to at
least 1. Multiple skins do not multiply together, and the strongest percentage
does not necessarily win precedence. Ordinary Barkskin has no direct melee
reduction here despite the old property; its AC effect is a separate matter.

The selected skin's counter is consumed even when preceding Earth Aura or
Displacement set this intermediate damage to zero. Those apparent negations
also encounter the later minimum 1; a complete early return from a ward is
different. Wight's innate Stone Skin therefore has both finite-charge and
per-hit-size considerations. Fist of Dragon can bypass the selected skin.
[Skin selection and application](../../../src/combat/fight.c#L5618),
[charge handling](../../../src/combat/fight.c#L3605),
[Wight innate](race-innates.md#stone-skin--innate_stone).

## 4. Spell damage, shrug, and stacking

### A spell's handler owns its saving throws

A save may halve damage, reduce it by another fraction, prevent an effect,
shorten its duration, or select a different branch. Some handlers perform
multiple saves or only conditionally permit shrug. There is no general rule
that every spell receives both a save and a racial shrug, or that shrug always
prevents status effects applied before the damage call.

`spell_damage()` receives the handler's already-calculated base payload and
damage type. Its important ordering is:

1. Validate participants; absorb a damage ward; exit if nothing remains.
2. Fire/ice aura absorption into healing; eligible class evasion.
3. Flag-selected spirit wards and globes.
4. Unless `SPLDAM_NODEFLECT`: Deflect, equipped-item/NPC hooks, Stornog spheres,
   Arcane Riposte, Disperse Flames and Flame Mastery.
5. Fire consumes Ice Armor; holy consumes Negative Energy Armor, each leaving
   the target unharmed for that damage call.
6. Unless `SPLDAM_NOSHRUG`: racial shrug, then eligible Lich Spell Absorb.
7. Eligible Hellfire absorption/healing.
8. The spell modifier profile, global world-NPC spell difficulty, then the
   shared raw-damage stage. Surviving targets may suffer additional wet/lightning
   shock and equipment consequences.

This order matters: a sphere consumed before shrug can be spent on a spell
that the target might otherwise have shrugged. Spell Absorb only gets an
opportunity after shrug failed. Deflect redirects a damage call at .70 of the
incoming payload; Reflection's racial images are a completely different system.
[Spell delivery and early exits](../../../src/combat/fight.c#L4418),
[shrug and Spell Absorb ordering](../../../src/combat/fight.c#L4762).

Spell Absorb first requires `incomingDamage/50 > random(0,9)`, then a successful
`level/2` threshold against 1..100, an eligible slot-based resource model,
and a missing slot. It restores the highest spent circle and negates that
damage call. At level 56 and incoming damage 100, its two numeric gates give
20% × 28% = 5.6%, conditional on reaching this stage and having a free slot.
At full preparation it cannot supply that negation. This is additional to,
and reached after failure of, Lich's racial shrug.
[Spell Absorb helpers](../../../src/combat/fight.c#L4355).

### Shrug, penetration, and WIS reduction

At ordinary levels, innate shrug rating starts with the configured racial
value, loses `min(6,56-level)`, is scaled by `min(1,level/50)`, and is floored
at 5. Eligible Rrakkma holders add 5 each, up to five other holders; final rating
caps at 100. The actual check is against 1..101. Ownership is required: a race
without Magic Resistance does not acquire a universal five-point shrug.

Self/consented casts bypass shrug. Desecrated Land subtracts 10 from the rating
at the check. Successful same-room penetration can defeat a successful shrug:
an ordinary PC with penetration skill 100 gets threshold 50 against 0..110,
or 50/111. The marker temporarily bypasses further shrug checks, and the spell
modifier later consumes it while cutting damage by random 20..70 percent plus
the committed 0.8 percentage points. Penetration is therefore neither a pure
subtract-from-shrug stat nor an assurance of full spell damage.
[Resistance and penetration](../../../src/classes/innates.c#L4907),
[consumption/damage cut](../../../src/combat/dam_mods.c#L757),
[settings](../../../lib/duris.properties#L2117).

WIS uses a separate damage reduction: `MR=clamp((WIS-110)/2,0,75)`.
For MR 1..20 it rolls 1..MR%; MR 21..40 rolls 20..MR%; MR 41..75 rolls 40..MR%.
It neither cancels status effects nor equals innate shrug. `SPLDAM_NOSHRUG`
bypasses this WIS reduction **as well as shrug and the Spell Absorb block**.
At WIS 150 mean reduction is 10.5%; at 152 it is 20.5%; at 192 it is 40.5%.
[WIS predicate](../../../src/combat/dam_mods.c#L660),
[MR macro](../../../src/core/utils.h#L1430).

### The modifier profile is not a flat list of multipliers

Each predicate returns one category:

```text
Added:     sum flat additions, bounded -100..100
Increased: start at1, add each contribution, bounded .05..4 in spell_damage
More:      multiply (1 + each predicate's contribution), bounded .1..2
result = max(1, (base + Added) * Increased * More)
```

The implementation uses float clamps inside a double calculation; final raw
delivery truncates to integers. Critically, **several effects inside one
predicate add their contributions before that predicate becomes one More
factor**. Different predicates multiply. Do not multiply every listed effect
independently, and do not apply the 2× cap separately to each effect.
[Profile accumulation](../../../src/combat/fight.c#L4822),
[profile types](../../../src/combat/dam_mods.h#L17).

| Spell modifier family | Current behavior and racial consequence |
|---|---|
| Generic magic reduction | Dwarf/Duergar innate gives a separate .80 More factor for generic damage only. |
| Fire | Fire vulnerability, same/opposite shields, protection, Barkskin/Thornskin, Ironwood and Wet combine within the fire predicate. Troll and other native fire-vulnerable races start at 1.30; fire protection or Fireshield subtracts .10 there, producing 1.20 in isolation. |
| Cold | Same/opposite shields, protection, fire-body/aura effects and Barbarian's direct -.40 contribution combine in one predicate. Barbarian with its native cold protection at 31+ has .45 before other stages. |
| Lightning, gas, acid | Per-element shield/protection branches; lightning shield protects against lightning but increases gas/acid damage. |
| Psionic | Tower of Iron Will(-.25), Tiger Palm(-.35) and native Thri-Kreen(-.30) add inside one More predicate. |
| Holy | Undead identity alone adds no generic holy vulnerability here. Vampire's Sacrilegious Power gives .75/.50/.25 at 46/51/56; Soulshield and negative shield modify that same holy factor. |
| Negative | Angel vulnerability, Soulshield vulnerability and negative shield protection combine in one predicate. |
| Magic Vulnerability | Native Ogre/Firbolg with the innate add +.10 to Increased across damage types. |
| Cold Vulnerability | Thri-Kreen adds +.35 to Increased and can receive 15s Slow after a failed paralysis save. This is separate from the cold shield/protection predicate. |
| STR spell offense | STR 121/141/181 enters increasingly strong bands; top band rolls 1.21..1.30. This is separate from racial casting speed and POW/INT resources. |
| Racial type properties | Offensive and defensive racial type contributions add within one predicate. All 37 PC races are currently neutral through these property tables; active racial exceptions above live elsewhere. |
| Phantasmal Form | A separate 1.50 elemental More factor unless the named armor exception applies; a native fire-vulnerable Phantom can consequently take 1.30×1.50. |
| Other defense/offense | Energy Containment, Elemental Power, Arcane Block, WIS, elemental affinity, Chaos Shield, penetration, class Soulshield, Judicium, Dreadnaught and paladin spell-protection aura have their own predicates. |
| NPC, pet and group context | PC-to-pet multiplier, zone/NPC/area bonuses, designated necropet reduction, bloodlust and Ethereal Alliance can change delivery. Alliance can damage a second character during predicate evaluation. |

All 36 spell predicates were reviewed, including the global spell multiplier,
Dragonslayer/Demonslayer, Berserk/rage and the contextual paths grouped above.
“Elemental” is precisely fire/cold/lightning/gas/acid/**earth** here; it does not
include generic, holy, negative, psionic, spiritual or sound.
[Spell predicates](../../../src/combat/dam_mods.c#L290),
[racial type loader](../../../src/combat/fight.c#L377),
[type definitions](../../../src/combat/damage.h#L103).

## 5. The shared raw-damage stage and flags

Both melee and spell delivery normally enter `raw_damage()`. Direct callers
also use it, but their flags can select a different result.

After admission and any not-yet-checked ward, its 16 predicates build another
Added/Increased/More profile. The bounds are -100..100, **.10..4**, and .1..2.
Unless `PHSDAM_NOREDUCE` is present, one predicate subtracts .75 from Increased:
the neutral baseline therefore delivers **one quarter** of its incoming
payload. Other Increased contributions join that same category; they are not
necessarily multipliers on the quartered result.

The other predicates cover racewar side factors, world-mob bonus, bloodlust,
two hardcore adjustments, Holy Sword's flat addition, Paladin and Cleric
Sanctuary, Consecrated Land, Binding Wind, Protection from Animals, Battlelust,
Blood Tithe, Orog Fury, and NPC-to-PC context. Ordinary racewar side factors
are all 1 in the committed properties. The NPC-to-PC predicate uses the
configured value divided by 2, so the committed 2 means neutral at that stage.

Sanctuary's checks here require Paladin or Cleric class membership. Paladin
group scaling adds to its own Sanctuary predicate; a Paladin/Cleric multiclass
can meet both independent predicates. Consequently a generic “Sanctuary is
25% reduction on everyone” assumption is invalid.

After the profile, damage is clamped to 1..32766 and truncated. Blood Alliance,
Imprison and Vines can redirect/absorb later; nonlethal and overkill limits
then change actual HP loss. Vamp and related healing follow this actual
delivered amount. Training dummies record at an earlier point than several
of these live-character consequences, so dummy damage alone cannot measure
all sustain and redirection mechanics.
[Raw pipeline](../../../src/combat/fight.c#L6172),
[all raw predicates](../../../src/combat/dam_mods.c#L884).

| Flag | Meaning relevant to comparisons |
|---|---|
| `PHSDAM_NOREDUCE` | Skips many physical reductions and selected raw reductions, including the -.75 baseline. It does not mean every defense in the game is bypassed. |
| `PHSDAM_NOPOSITION` | Skips the physical posture and Flank/Circle block. |
| `PHSDAM_NOSHIELDS` | Suppresses the physical pipeline's shield retaliation. |
| `PHSDAM_NOENGAGE` | Suppresses that physical delivery's automatic engagement response. |
| `PHSDAM_TOUCH` / `PHSDAM_ARROW` | Select distinct hit-healing and other consumers. Ordinary weapon attacks do not universally carry Touch. |
| `SPLDAM_NOSHRUG` | Bypasses innate shrug, the Spell Absorb block and WIS reduction; other spell defenses remain. |
| `SPLDAM_NODEFLECT` | Skips the deflection/item-hook/sphere/class-reaction block, and the eligible Hellfire absorption. Other early absorptions and shrug remain. |
| Globe/ward spell flags | Identify which globe or spirit ward can stop this particular damage call. |
| `SPLDAM_NOVAMP` | Blocks the HP-vamp branches after the earlier cannibalize handling. |
| `RAWDAM_DEFAULT` | Enables normal shared vamp/Sanctuary/Imprison/Vines consumers; individual bits can be disabled by the caller. |
| `RAWDAM_NOWARD` | Avoids consuming the same ward twice when an outer pipeline already checked it. |

Spell delivery passes `(RAWDAM_DEFAULT ^ flags) | RAWDAM_NOWARD`; melee passes
`RAWDAM_DEFAULT | flags | RAWDAM_NOWARD`. XOR toggles a bit already present in
the defaults, whereas OR retains it. That distinction matters for retaliation
and spells intentionally disabling a default vamp route. The legacy `damage()`
wrapper translates spell/skill IDs into these APIs and flags; a display name
such as “spell” or “physical” is not sufficient evidence of its actual route.
[Shared flag vector](../../../src/combat/damage.h#L119),
[legacy wrapper](../../../src/combat/fight.c#L4218).

## 6. Saving throws, control, and body identity

### Magical saves and stat saves are different systems

`find_save()` calculates a threshold, not the probability of success:

```text
threshold = starting - level*(starting-top)/60
          + racial property + primary-class property
threshold += 5*(equipment/affect save apply + caller's modifier)
success = random(1,100) > clamp(1,threshold,99)
```

The level term uses integer division. A positive racial/caller adjustment is
worse for the defender. Racial property points are added directly; the caller's
modifier and character save apply are multiplied by 5. At 56, with no racial,
class, gear or caller adjustment, spell/breath success is 67%, and
paralysis/fear/rod success is 76%. Rod uses the loader's 70/20 defaults because
the committed file has no rod starting/top entries. The `petri` property name
feeds `SAVING_FEAR`; it should not be mistaken for a separate petrification-only
defense. Primary-class selection here differs from the best-of-two class
selection used by melee output and pulse.

Quick Thinker rerolls a failed `NewSaves` once: `p -> 1-(1-p)^2`.
Halfling receives it at 1; Half-Elf at 30. It works on any caller of this helper,
including physical actions that use a magical saving-throw category. At the
usual 99% individual cap the reroll reaches 99.99%, not guaranteed immunity.
[Save loader and calculation](../../../src/net/sparser.c#L1172),
[NewSaves](../../../src/net/sparser.c#L1258),
[racial/class properties](../../../lib/duris.properties#L2177).

`StatSave()` instead uses a stat's `STAT_INDEX`, caller modifiers and relevant
posture/load/status adjustments; success is
`random(1,21) < clamp(1,score,20)`. Its maximum is 19/21. Quick Thinker gives
a separate 15% immediate pass for **INT and POW only**, then the usual roll;
it does not reroll every stat save. Haste/Slow, flight, stun and load alter
selected AGI/DEX branches. The stat layer contains their full consumer catalog.
[Stat saves](../../../src/core/utility.c#L3247),
[stat-save consumers](race-stats.md#41-shared-stat-saves-and-their-callers).

### Control is resolved by several independent gates

| Control family | Admission/resolution and gameplay effect |
|---|---|
| Bash/tackle/maul and other takedowns | Command-specific size/body windows, then selected `takedown_check` flags: ranks, Evade, Grapple, footing, immaterial/Harpy defenses, auras, optional AGI/Luck adjustment, Guardian Spirits and Freedom of Movement. Passing size alone is not success. |
| Immaterial PC takedown defense | When the caller enables `TAKEDOWN_GHOST`, a PC immaterial target gets a 1/10 rejection; NPC immaterial targets are rejected outright. This is not universal PC bash immunity. |
| Harpy takedown defense | When `TAKEDOWN_HARPY` is enabled, a separate 5% rejection. It is independent of melee Leap. |
| Thri-Kreen takedown offense | In the shared AGI comparison, the attacker's AGI is capped at 100 for Thri-Kreen. Its high natural AGI still affects other consumers. |
| Stun | `Stun()` rejects elites/already-stunned targets and applies special greater/construct-like admission. With `Fear_Check=true`, a first failed fear save gives full duration; a first success and second failure gives half; two successes avoid it. `Fear_Check=false` skips these helper saves. |
| Fear | The caller may check shrug, `NewSaves`, undead identity, Berserk and `fear_check`. Barbarian's 41+ Dauntless supplies NOFEAR for ordinary checks; force-enabled calls can bypass that bit. A helper using the fear save category is not automatically blocked by NOFEAR. |
| Blindness | `blind()` checks its own immunity bits/body/innate rules; Lich's Eyeless is relevant here. Sight loss also changes accuracy, admission to automatic defenses and target acquisition. |
| Paralysis | Handlers choose minor/major, saves and Freedom of Movement checks. Both suppress due ordinary melee opportunities. Incoming external damage removes minor paralysis in `raw_damage`; major paralysis is not cleared by that same block. |
| Knockout/sleep | Separate status from stun/lag. Ordinary Sleep checks shrug, no-sleep equipment, level and body immunity, with a force-style negative-level route. Incoming damage has its own waking rules; knockout prevents ordinary waking. |
| Groundfighting | Preserves ordinary downed attack counts and avoids the 1.15/1.30/1.50 posture damage penalties; permits reduced dodge. It does not grant universal immunity to lag, stun, paralysis or the standing requirements of other abilities. |

Sources: [takedown helper](../../../src/cmd/actoff.c#L423),
[size and body windows](race-size.md#3-combat-target-windows),
[Stun and KnockOut](../../../src/magic/affects.c#L3563),
[fear helper](../../../src/combat/fight.c#L11688),
[ordinary Fear](../../../src/magic/magic.c#L14088),
[blind helper](../../../src/magic/affects.c#L3515),
[Sleep](../../../src/magic/magic.c#L11503),
[damage waking/release](../../../src/combat/fight.c#L6512),
[round suppression](../../../src/combat/fight.c#L11091).

Control can impose several costs simultaneously: denied commands, fewer or
missed melee attacks, weaker defenses, greater incoming damage, interrupted
preparation, and loss of target/range. Conversely, ordinary command lag alone
does not stop a PC's auto-melee. Track these costs separately rather than
converting every duration into the same number of lost rounds.

### Undead, immaterial, and body classifications

The eight native PC races satisfying `IS_UNDEADRACE` are **Shade, Revenant,
Lich, Vampire, Death Knight, Shadow Beast, Wight and Phantom**. Native
`IS_IMMATERIAL` includes **Shade, Wight and Phantom**; Phantasmal Form can add
that state to other races. Undead does not imply immaterial, Eyeless,
Amorphous Body, a universal fear rule, or immunity to every poison source.
`IS_UNDEAD` also includes these eight native PC races through
`OLD_RACE_PUNDEAD`; choosing between these two names alone does not establish
a native-PC immunity difference. Other body predicates and handler-specific
conditions still need separate evaluation.
[Identity macros](../../../src/core/utils.h#L141),
[undead predicates](../../../src/core/utils.h#L789).

Concrete consumers worth keeping in a racial matchup sheet:

- Ordinary Enervation, Dispel Lifeforce, Disease, Poison, Fear, Purge Living,
  Unholy Wind, Power Word Kill and Ghastly Touch have undead-specific refusal
  or immunity branches. Ordinary Sleep also excludes undead in its normal
  positive-level route. These are **named-handler protections**, not proof
  of a universal immunity to those damage types or status categories.
- Life Leech/Energy Drain can suppress their special caster-healing branch
  against undead without making the damage call itself disappear. Their
  own vamp flags also differ from a normal nuke.
- Destroy/Turn/Banish Undead, undead healing/protection spells and class
  pressure-point attacks use body-specific admission. The generic holy
  damage predicate does **not** impose a blanket 2× multiplier on every undead
  PC; individual spells may still target or punish undead specially.
- Unarmed immaterial attackers have special parry admission; immaterial
  targets escape Grappler Entrapment, but other grapple and physical moves
  use their own tests.
- Centaur/Drider bodies have particular groundslam and takedown restrictions,
  and cannot normally ride another mount. Their body benefits should not be
  generalized into immunity to all control.

Sources: [Enervation](../../../src/magic/magic.c#L1645),
[drain healing](../../../src/magic/magic.c#L1830),
[Dispel Lifeforce](../../../src/magic/magic.c#L7009),
[Disease/Poison](../../../src/magic/magic.c#L10600),
[Purge Living](../../../src/magic/magic.c#L18561),
[Power Word Kill](../../../src/magic/magic.c#L19069),
[Ghastly Touch](../../../src/magic/magic.c#L19351),
[undead-target spell family](../../../src/magic/magic.c#L16712),
[Entrapment](../../../src/combat/grapple.c#L65),
[body details](race-innates.md#horse-body-and-spider-body).

## 7. Racial exceptions, ranged attacks, and reactions

### Race-coded effects outside the innate roster

| Race/family | Active path and consequence |
|---|---|
| Barbarian | Direct -.40 in the cold predicate, in addition to 31+ cold protection; positive racial save penalties partly offset its durable physical profile. |
| Drow | Additional eligible 1/11 dodge branch, on top of high natural AGI and native shrug. Light load is necessary for this particular bonus. |
| Mountain/Duergar Berserker | `berserk_quality=3`: larger MAX-CON package, smaller WIS penalty, different MAX-POW, extra HP above 6, and-2 combat pulse with both required skills exactly 100. Other Berserkers use quality 2; other users quality 1. These are racial/class interactions, not grants to every dwarf. |
| Orc | `hit()` applies `orc_horde_dam_modifier` based on other Orcs in the room, including NPCs and enemies; it is not restricted to the caster's summoned horde or group. The current offensive and non-Orc-attacker defensive branches both increase the payload by 1.5% per other Orc. Orc-versus-Orc takes only the offensive branch because the dispatch is `if/else if`. The defensive sign deserves separate review; do not credit a fictional reduction. |
| Minotaur | Successful ordinary hit delivery can call `minotaur_race_proc`: an 8s short effect gives `-1-level/28` to both combat and spell pulse, with no stacking while its tag exists. Warrior chance is 1/11; Ranger/Reaver 1/31, Monk 1/21, Sorcerer/Conjurer/Summoner 1/7, other primary classes 1/16. At 56 the apply is-3. |
| Minotaur under pressure | After surviving raw damage below one-sixth maximum HP, a 1/6 check can start 24s Berserk if none exists. This is separate from the offensive pulse proc. |
| Minotaur/Tiefling | Headbutt base damage gets 1.40/1.25 respectively, before the remaining headbutt and delivery rules. Horns do not multiply every melee attack. |
| Centaur and large kickers | `chance_kick` doubles Centaur's starting kick rating; selected native PC races increase the size-gap knockdown chance. Normal Centaur command routing to Rearkick must still be respected. |
| Thri-Kreen | Four-hand attack payload, native -.30 psionic contribution, cold damage/Slow vulnerability, AGI restriction in selected takedowns, and a separate Polar Vortex paralysis opportunity even with Coldshield. |
| Harpy | Native melee Leap and separate conditional 5% takedown rejection; flight also enters selected footing/stat-save paths. |
| Githyanki/Githzerai | Holy Word/Voice of Creation use 1.5× base damage against Githyanki; Unholy Word uses 1.5× against Githzerai. Eligible PC-versus-PC words can additionally attempt astral banishment; at equal level the roll is 2/101, subject to room and protective-item gates. Githyanki Confuse has an additional 50-mana cost. |
| Troll | Judgement has a Troll-specific failed fear-save/Freedom-of-Movement gate for 6s major paralysis. Its fire/regeneration interaction is a separate counter. |
| Undead PC family | Eligible damage-generated healing, named spell/control immunities and exclusions, and undead-target spells. Judgement has an undead sleep branch, showing why ordinary Sleep immunity is not universal. |
| Original Illithid | Special HP/resource routes, strong shrug and distinct casting; its original-race Awe limits differ. The registered Drain command can finish feeding on an incapacitated target to restore mana and kill it; this is not passive regeneration or an ordinary damage exchange. Planetbound Illithid is a distinct ID. |
| PC Vampire | Native touch healing and bite; the registered `lick blood` consumes a room blood object, invokes Cure Serious, and imposes 10 pulses of lag. This is not free continuous combat healing. |

Sources: [Orc dispatch](../../../src/combat/fight.c#L8665),
[Orc room modifier](../../../src/combat/fight.c#L11975),
[Minotaur offensive proc](../../../src/classes/drannak.c#L589),
[low-HP Berserk](../../../src/combat/fight.c#L6726),
[dwarven Berserk](../../../src/cmd/actoth.c#L550),
[headbutt](../../../src/cmd/actoff.c#L6267),
[kick](../../../src/cmd/actoff.c#L4251),
[Polar Vortex](../../../src/classes/ethermancer.c#L3416),
[word damage](../../../src/magic/magic.c#L19611),
[banishment](../../../src/magic/magic.c#L19127),
[Confuse](../../../src/classes/psionics.c#L3170),
[Judgement](../../../src/magic/magic.c#L23700),
[Awe](../../../src/classes/psionics.c#L590),
[feeding](../../../src/classes/psionics.c#L73),
[blood healing](../../../src/cmd/actoth.c#L7385).

These paths can overturn an inference made from innate count alone. They also
show why a race's native identity, current form, primary class and mechanics
override must be recorded separately. Tutorial NPC mechanics overrides are
used in several racial checks, but not uniformly in every native-race macro.
A training dummy instead writes its selected profile race into `player.race`;
its NPC handling and early damage recording still differ from a live PC.
[Dummy assignment](../../../src/combat/training_dummy.c#L231),
[tutorial override](../../../src/specs/specs.ailvio.c#L32).

For Orog's Fury, the raw-stage bonus is
`clamp(.02, targetRoomGroupSize/100 + level/1120, .15)`, plus `peerCount/30`
for up to three other eligible Fury holders grouped in the room. At 56 the
level contribution alone is .05; the base component can reach .15 and the
peer component .10. This is one More predicate on the holder's output, including
spells that reach raw damage. It is not a flat bonus granted to all groupmates.
[Fury calculation](../../../src/combat/dam_mods.c#L224),
[Fury application](../../../src/combat/dam_mods.c#L999).

### Archery resolves a different kind of attack

`do_fire` handles range, line/target admission, skill accuracy and projectile
equipment. Its hit roll uses `<=`, unlike ordinary `hit()`'s strict comparison.
An eligible shield then gets a separate chance against 1..1600:

```text
blockScore = shieldBlockSkill + AGI/2 + shieldCombatSkill/2 + DEX/5 + Luck/5
if defender is fighting: blockScore /= 4
```

Arrow payload combines missile dice,35% of stored damroll times the .75 damroll
factor,25% hitroll, small DEX/Luck rolls, half the bow's damage value, and an
archery-skill term. It then applies class output, wind effects, archery critical
rules and the committed 500 per-arrow pre-delivery cap. It does not use
ordinary weapon `TRUE_DAMROLL` or its INT critical construction.

Physical arrow delivery carries `NOENGAGE | NOSHIELDS | NOPOSITION | ARROW`:
armor and skin reductions remain, but ordinary posture amplification and
physical shield retaliation are skipped. Enchanted arrows subsequently use
their own spell/status path, including possible paralysis; those effects are
not the same damage type as the physical projectile. A shield block prevents
the enchantment invocation in this route.
[Archery](../../../src/combat/range.c#L561),
[arrow block](../../../src/combat/range.c#L538),
[payload](../../../src/combat/range.c#L1029),
[delivery/enchantment](../../../src/combat/range.c#L1120),
[archery properties](../../../lib/duris.properties#L2446).

### Retaliation changes the value of attack frequency

After physical delivery, eligible damage shields run only when the remaining
pre-raw physical amount exceeds 5 and `NOSHIELDS` is absent. The reaction is
based on that outer amount, **not simply the HP loss recorded by raw_damage**.
Negative shield and qualifying Soulshield use one `if/else if` family; Infernal
Fury, Fireshield, Coldshield and Lightningshield use another mutually exclusive
family. Thornskin and Acid Blood can add separate reactions.

The committed elemental shield shares are fire/cold .65 and lightning .55;
their new spell-damage calls then face spell defenses and raw modifiers.
An undead attacker bypasses negative-shield retaliation, but can still meet
other shield predicates. Infernal Fury uses NOSHRUG; ordinary elemental shields
do not. Thornskin calls raw damage with NOREDUCE. The same faster melee clock
can therefore create more enemy reaction opportunities and more friendly
healing opportunities, depending on payload and flags.
[Retaliation dispatch](../../../src/combat/fight.c#L4971),
[cutoff and outer amount](../../../src/combat/fight.c#L5738).

## 8. HP, healing, vamping, and sustained survival

Native HP scaling belongs to the [stat layer](race-stats.md#constitution-and-maximum-hit-points).
It includes a racial-CON-squared term for ordinary races and a separate original
Illithid formula. Equal displayed CON does not establish equal HP. Combine
that pool with this layer's defenses; do not add “HP%, dodge%, shrug%” into a
single universal score.

`raw_damage` calls `check_vamp` after clipping nonlethal/overkill damage and
subtracting HP. Images, a construct target, Negative Energy Barrier, flags,
minimum-hit thresholds, class precedence and existing successful vamp routes
can prevent or replace healing. Cannibalize is evaluated before several HP-vamp
refusals and restores mana rather than HP.

| Route | Current amount and important restrictions |
|---|---|
| PC Touch | Needs `PHSDAM_TOUCH`, the Vampiric Touch bit, and no Vampire Form. Original Illithid gets .25; otherwise class precedence gives Antipaladin .70, Monk .25, Mercenary/Warrior/Ranger .15, Berserker .18, Rogue .17, Paladin .10, Dreadlord/Avenger .70, default .25. |
| Arrow Touch | Needs an arrow hit of at least 4, the Touch bit, and no Battle Ecstasy; heals .05 of delivered damage. |
| Native undead/angel route | Needs `RAWDAM_TRANCEVAMP`, no earlier successful vamp route, no Battle Ecstasy, and at least 12 damage for a PC. The committed PC share is .75; ordinary cap is maximum HP. Lich spell damage can use its POW-dependent overheal cap instead. |
| Vampire Form/trance | Separate branch and .334 share; it should not be added automatically to native Touch and undead vamp. |
| Battle Ecstasy | Has self and group branches with different eligibility and flags. It can replace earlier routes; group healing is not simply the attacker's personal sustain. |
| Hellfire/Battletide | Separate flags, payload/target rules and caps; weapon damage can limit the Hellfire basis. |
| Holy Sacrifice | A group healing budget with per-hit/per-round limits and player-hit scaling. It is a defender/group response, not a racial HP multiplier. |

The common POW cap is `clamp(POW/90,1.1,2.5)` times maximum HP; prime
Antipaladin adds .25 within its 2.5 ceiling. This is the permitted health ceiling,
not the fraction of damage healed. `vamp()` truncates the requested amount,
applies healing suppression and eligible modifiers, and clips to remaining
capacity. Plague, carrier plague, Blackmantle and Flamestrike use different
suppression branches. `heal()` also applies caster healing modifiers before
calling this helper. Immunity to a spell's damage does not imply immunity to
every healing-suppression effect.
[Vamp dispatch](../../../src/combat/fight.c#L5858),
[undead branch](../../../src/combat/fight.c#L6097),
[healing application](../../../src/combat/fight.c#L684),
[healer application](../../../src/combat/fight.c#L764),
[committed vamp shares](../../../lib/duris.properties#L112),
[POW cap](../../../src/core/utils.h#L1416).

Troll and Revenant regeneration is time-based recovery, not healing per swing.
Their base innate awake contributions at 56 are 560 and 280 HP per 75s tick before
the other recovery rules. Fire burn can suppress Troll's innate component;
sunlight, posture, combat, terrain and room constraints matter. The existing
passive-versus-affect representation and burn-refresh issues prevent treating
the paper rate as unconditional live sustain. See
[recovery timing](race-tempo.md#9-recovery-and-the-time-between-fights) and
[innate regeneration](race-innates.md#regeneration--innate_regeneration).

For a deliberately stationary threat with constant eligible prevention,
`effective HP = HP / expected damage fraction` can be useful. With reliable
healing rate H and incoming damage rate D, time to depletion is approximately
`HP/(D-H)` only while D>H and the assumptions remain true. Burst damage,
control, changing skins, heal-blocking, resource exhaustion and lethal hits
break that approximation. Report threat-specific durability and recovery
separately, including PvE/PvP and solo/group conditions.


## 9. Complete player-race resolution tables

### Active racial caps, shrug, elemental effects, and identity

All rows use native race, level 56, committed properties, no class-granted
innates, no form, no Rrakkma peers, and no active racial buff. `O` means ordinary
creation; `R` restricted/legacy. `U` means native `IS_UNDEADRACE`; `I` native
`IS_IMMATERIAL`. These labels describe the predicates in section 6, not universal
immunities. Shrug is a **rating out of 101** when the check is eligible; a dash
means no native Magic Resistance grant.

The elemental column isolates native shared damage predicates. It excludes
natural WIS reduction, attacker STR, shrug, caller saves, class/gear effects,
the raw stage, and named-spell racial exceptions. An omitted element is neutral
in this isolated profile. In particular, the offensive/defensive spell-type
property tables are 1 for every one of the 37 PC IDs across all 12 types, by
explicit setting or loader default.

| ID | Race | Creation | Damroll factor → stored cap | Shrug rating | Body | Native shared spell modifier |
|---|---|---|---|---|---|---|
| 1 | Human | O | 1.000 → 50 | — | — | — |
| 2 | Barbarian | O | 1.150 → 57 | — | — | Cold .45 (.60 before 31) |
| 3 | Drow Elf | O | 0.750 → 37 | 38 | — | — |
| 4 | Grey Elf | O | 0.770 → 38 | 30 | — | — |
| 5 | Mountain Dwarf | O | 1.120 → 56 | — | — | Generic .80 |
| 6 | Duergar Dwarf | O | 1.110 → 55 | — | — | Generic .80 |
| 7 | Halfling | O | 0.850 → 42 | — | — | — |
| 8 | Gnome | O | 0.800 → 40 | — | — | — |
| 9 | Ogre | O | 1.500 → 75 | — | — | All types: +.10 Increased |
| 10 | Troll | O | 1.180 → 58 | — | — | Fire 1.30; burn suppresses recovery |
| 11 | Half-Elf | R | 1.030 → 51 | 20 | — | — |
| 12 | Illithid | R | 0.450 → 22 | 70 | — | — |
| 13 | Orc | O | 1.030 → 51 | — | — | — |
| 14 | Thri-Kreen | O | 1.000 → 50 | — | — | Psionic .70; cold +.35 Increased and Slow check |
| 15 | Centaur | O | 1.180 → 58 | — | — | — |
| 16 | Githyanki | O | 0.970 → 48 | 25 | — | — |
| 17 | Minotaur | O | 1.200 → 60 | — | — | — |
| 18 | Shade | R | 0.700 → 35 | — | U, I | Fire 1.30 |
| 19 | Revenant | R | 1.400 → 70 | — | U | Fire 1.30 |
| 20 | Goblin | O | 0.950 → 47 | — | — | — |
| 21 | Lich | R | 0.650 → 32 | 65 | U | Cold .85 |
| 22 | Vampire | R | 1.280 → 64 | 40 | U | Holy .25 at 56 |
| 23 | Death Knight | R | 1.475 → 73 | — | U | Fire .85 |
| 24 | Shadow Beast | R | 1.250 → 62 | — | U | Fire 1.30 |
| 25 | Storm Giant | R | 1.455 → 72 | — | — | — |
| 26 | Wight | R | 1.350 → 67 | — | U, I | Fire 1.30 |
| 27 | Phantom | R | 0.900 → 45 | 20 | U, I | Fire 1.30; form is additional |
| 28 | Harpy | R | 1.050 → 52 | — | — | — |
| 29 | Orog | R | 1.200 → 60 | — | — | — |
| 30 | Githzerai | O | 0.975 → 48 | 20 | — | — |
| 31 | Drider | O | 1.175 → 58 | 25 | — | — |
| 32 | Kobold | O | 0.775 → 38 | — | — | — |
| 33 | Planetbound Illithid | R | 0.650 → 32 | 50 | — | — |
| 34 | Kuo Toa | R | 1.250 → 62 | — | — | — |
| 35 | Wood Elf | R | 1.150 → 57 | 5 | — | — |
| 36 | Firbolg | O | 1.450 → 72 | — | — | All types: +.10 Increased |
| 37 | Tiefling | O | 1.000 → 50 | 20 | — | Fire .85 |

The cap is the saturated **stored** damroll value, not TRUE_DAMROLL. Calculations
use the production float representation and integer truncation. Tiefling has
no dedicated damroll-factor entry and uses 1.0. PC Vampire shares the `Vampire`
damage-property key with the NPC race, but its shrug loader deliberately uses
`PVampire`; original Illithid and `Pillithid` are separate keys.
[Race names](../../../src/core/common.c#L79),
[damroll properties](../../../lib/duris.properties#L246),
[shrug loader](../../../src/net/sparser.c),
[creation roster](../../../src/core/constant.c#L1590).

### Actual save success in a controlled level 56 fixture

These are `NewSaves` success probabilities using the real `find_save` thresholds,
zero caller modifier, zero save applies, and no primary-class adjustment.
Quick Thinker's native reroll is included for Halfling and Half-Elf. They do
not include shrug or body immunity; a spell blocked before the save never
reaches this roll. Percentages therefore isolate racial save behavior rather
than predicting final spell effectiveness.

| ID | Race | Spell | Paralysis | Fear (`petri`) | Breath | Rod |
|---|---|---:|---:|---:|---:|---:|
| 1 | Human | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 2 | Barbarian | 47.00% | 66.00% | 66.00% | 57.00% | 76.00% |
| 3 | Drow Elf | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 4 | Grey Elf | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 5 | Mountain Dwarf | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 6 | Duergar Dwarf | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 7 | Halfling | 89.11% | 94.24% | 94.24% | 89.11% | 94.24% |
| 8 | Gnome | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 9 | Ogre | 67.00% | 61.00% | 86.00% | 77.00% | 76.00% |
| 10 | Troll | 67.00% | 61.00% | 66.00% | 57.00% | 76.00% |
| 11 | Half-Elf | 89.11% | 94.24% | 94.24% | 89.11% | 94.24% |
| 12 | Illithid | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 13 | Orc | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 14 | Thri-Kreen | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 15 | Centaur | 67.00% | 76.00% | 51.00% | 67.00% | 76.00% |
| 16 | Githyanki | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 17 | Minotaur | 52.00% | 61.00% | 61.00% | 57.00% | 76.00% |
| 18 | Shade | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 19 | Revenant | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 20 | Goblin | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 21 | Lich | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 22 | Vampire | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 23 | Death Knight | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 24 | Shadow Beast | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 25 | Storm Giant | 57.00% | 61.00% | 66.00% | 57.00% | 76.00% |
| 26 | Wight | 37.00% | 51.00% | 51.00% | 42.00% | 76.00% |
| 27 | Phantom | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 28 | Harpy | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 29 | Orog | 27.00% | 66.00% | 51.00% | 57.00% | 76.00% |
| 30 | Githzerai | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 31 | Drider | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 32 | Kobold | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 33 | Planetbound Illithid | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 34 | Kuo Toa | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 35 | Wood Elf | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 36 | Firbolg | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |
| 37 | Tiefling | 67.00% | 76.00% | 76.00% | 67.00% | 76.00% |

For example, Barbarian's +20 spell threshold reduces 67% to 47%; this is not a
20% damage increase. Ogre has worse paralysis saves but better breath/fear
saves than the neutral fixture. Orog's +40 spell threshold produces 27%, while
its physical stats can remain strong. A caller modifier of +2 adds 10 threshold
points; negative save gear can compensate until the clamp. Paladin's native
class spell adjustment is-10 threshold points, separately from these racial
values. The same race can therefore compare differently across classes and
spell categories.
[Save equations](../../../src/net/sparser.c#L1185),
[save properties](../../../lib/duris.properties#L2177).

### Gameplay interpretation for every player race

The following joins the verified tables to the earlier layers. These are
mechanical tradeoffs, not recommendations to rank unlike classes or to treat
restricted races as ordinary creation choices. Native stats below mean the
committed factors; gear and class overlap can change their practical value.

| Race | Offense and action delivery | Defense, sustain, and matchup cost |
|---|---|---|
| Human | Broad +5 stats; neutral racial output, cap 50; native Human/Orc multiclass access must be valued separately. | No native shrug or elemental reduction; versatile stats do not supply the specialized defenses of another race. |
| Barbarian | Strong STR/CON, cap 57, slow base rounds, Bodyslam and selected kick control. | Groundfighting 21, cold factor .45 at 31+, fear protection 41; weaker native saves remain relevant outside immunity checks. |
| Drow Elf | Fast rounds/casts, cap 37, longsword mastery and reveal utility. | Native shrug 38, conditional extra dodge and high AGI; sunlight/recovery constraints and low natural CON remain separate costs. |
| Grey Elf | Drow-like base tempo, cap 38, longsword mastery and terrain information. | Shrug 30 and high WIS/AGI; no Drow extra dodge and no native sunlight penalty. |
| Mountain Dwarf | STR, cap 56, axe/hammer mastery and matchup-dependent Hatred; special dwarven Berserker package. | Generic spell .80, WIS reduction and specific Giant Avoidance; no native shrug. Slow base melee is not a universal magic-defense penalty. |
| Duergar Dwarf | Cap 55, Frenzy, active STR/Enlarge/Haste and dwarven Berserker package. | Generic spell .80 and high WIS; sun/recovery and active-buff conditions distinguish it from Mountain Dwarf. |
| Halfling | Fast rounds/casts, high DEX/Luck and cap 42; weapon-weight gates still matter. | Quick Thinker from 1, later Luck/information benefits; no native shrug or blanket spell-damage reduction. Small size changes control reach. |
| Gnome | Very fast tempo, high INT critical/recovery contributions and cap 40. | Reflection and vision provide situational protection; low natural CON/STR and no native shrug must be tested against actual opponents. |
| Ogre | High STR and cap 75 support large payloads and stronger opposition to parry/block; slow rounds and narrow Huge control windows. | High native HP scaling, Roar utility, but +.10 spell Increased and sun constraints; paralysis saves worsen while breath/fear saves improve. |
| Troll | STR, cap 58, Bodyslam and selected kick effects; slower rounds. | Troll Skin .85 and regeneration; fire 1.30 with recovery suppression, worse paralysis/breath/fear saves, and no native Groundfighting. |
| Half-Elf | Intermediate tempo and cap 51; weapon mastery. | Shrug 20 plus Quick Thinker 30 can protect different stages of one hostile effect; restricted access and class context matter. |
| Illithid | Exceptional casting, POW/INT and racial mana; cap 22/low STR constrain ordinary hits. Awe/feeding are original-race-specific. | Shrug 70; its separate HP formula must be evaluated directly. Sun and resource/target restrictions prevent treating casting speed as unlimited throughput. |
| Orc | Cap 51 and room-Orc payload scaling; Horde/Warg and native multiclass access add distinct build options. | No native shrug or sun penalty. Current horde defensive sign raises incoming ordinary-hit payload; follower utility must not be counted as a proven reduction. |
| Thri-Kreen | Four hands and high DEX/AGI can increase round payload; cap 50; selected takedowns cap offensive AGI at 100. | Leap 21 and psionic .70; cold +.35 Increased, Slow and Polar Vortex's extra paralysis route are separate risks. |
| Centaur | STR/cap 58, horse-body Rearkick/Stampede and later two-handed slashing mastery. | High CON and body-specific control rejection; no normal riding, no native shrug, and worse fear-category saves. |
| Githyanki | POW, favorable casting, cap 48, astral access; Confuse has an extra mana cost. | Shrug 25; Holy Word/Voice of Creation bane and eligible banishment, plus sunlight recovery costs. |
| Minotaur | STR/cap 60, stronger headbutt, Charge and nonstacking hit-triggered pulse buff. | High CON and possible low-HP Berserk; save penalties and Huge reach limits. Its pulse proc is not always-on extra attacks. |
| Shade | High DEX/INT, fast casting but cap 35; shadow movement affects approach. | Undead and immaterial predicates; fire 1.30, no native shrug, and conditional shadow-state behavior. |
| Revenant | Cap 70/STR, physical opener and travel utility. | High native CON, regeneration and undead consumers; fire 1.30, no native shrug or Groundfighting. |
| Goblin | Fast tempo, high DEX/Luck, cap 47 and equipped totem benefits. | Disappear/vision; no native shrug. Totem ownership, equipment opportunity cost and level-specific payload must be recorded. |
| Lich | Fast casting, POW/INT, cap 32 and spell-eligible undead vamp; skeleton utility. | Shrug 65, cold .85, Eyeless, undead admission and slot-dependent Spell Absorb; low native CON and sun constraints. |
| Vampire | Favorable tempo, cap 64, Bite and flag/class-dependent native Touch healing. | Shrug 40, undead consumers and holy .25 at 56; no native fire vulnerability. Touch, trance and undead healing do not simply add together. |
| Death Knight | Cap 73, moderate melee speed, slow ordinary casting; innate Firestorm/Fireshield have separate timing. | Fire .85 and undead consumers; no native shrug. Shield retaliation depends on flags, attacker defenses and surviving delivery. |
| Shadow Beast | Fast melee, cap 62, active STR/Enlarge and images. | Undead consumers, high DEX/AGI and concealment; fire 1.30. It is not natively immaterial under the shared macro. |
| Storm Giant | Cap 72 and physical stats despite zero assigned racial innates. | High CON but worse saves and very slow casting. Its PC Huge size is distinct from inconsistent generic lookup results documented in the size layer. |
| Wight | Cap 67 and physical opener; slowest listed ordinary cast factor. | Undead/immaterial consumers and finite Stone Skin; fire 1.30, broad save penalties, no native shrug. |
| Phantom | Fast casting, cap 45, astral/form/flight utility. | Shrug 20 and undead/immaterial consumers; fire 1.30 and form's additional elemental 1.50 are distinct factors. |
| Harpy | Fast rounds/casts, cap 52, flight and information. | Leap 1 and conditional 5% takedown defense; no native shrug or elemental weakness. Resource-model recovery is separate from casting speed. |
| Orog | STR/DEX/CON, cap 60 and Fury's target-group/holder scaling. | Physical durability trades against low mental stats and especially weak spell saves; sun and slow casting add context. |
| Githzerai | POW/INT, favorable casting, cap 48 and astral utility with later outgoing shift. | Shrug 20 plus group Rrakkma AC/shrug; Unholy Word bane/banishment, but no native sun penalty. |
| Drider | Fast melee, cap 58, balanced physical factors, Web Spray vitality pressure. | Shrug 25, Spider Body and Groundfighting 21; no normal riding. Four-hand attacks do not follow from Spider Body. |
| Kobold | Fastest neutral melee interval, fast casting, INT and cap 38. | Reflection and underworld movement utility; no native shrug, low natural STR/CON, and Small control reach. |
| Planetbound Illithid | Favorable casting/mana, cap 32; does not inherit original Illithid's extreme cast factor, HP formula or every original-race command. | Shrug 50 and ordinary racial HP formula; Dayblind/sun and delayed Levitate are distinct costs. |
| Kuo Toa | Cap 62, strong physical factors and delayed lightning. | Terrain/water utility with no native shrug; sun constraints. Water access is not an automatic combat damage reduction. |
| Wood Elf | STR/CON, cap 57, longsword mastery and terrain concealment. | Small native shrug 5; movement/information utility is valuable without constituting general damage mitigation. |
| Firbolg | Ogre-like STR and slow rounds, cap 72, Bodyslam and forest information. | High CON with +.10 spell Increased; no native sun penalty, shrug or dark-vision grant. Native saves are neutral in the table. |
| Tiefling | Moderate tempo, INT/CHA, cap 50 and headbutt 1.25. | Shrug 20 and fire .85 without native sunlight penalty; no active innate attack is required for these passive defenses. |

Sources for the common baseline and eligibility:
[racial stats](race-stats.md#2-complete-pc-racial-factor-comparison),
[innate assignments](race-innates.md#2-complete-race-by-race-unlock-roster),
[tempo](race-tempo.md#3-all-player-races-melee-timing),
[class legality](../CLASSES.md#creation-and-alignment),
[multiclass admission](../../../src/cmd/actoth.c#L144).
The earlier sections cite the current owning paths for additional exceptions
and for the corrected Leap/block behavior.

## 10. Worked comparisons

All examples isolate named mechanisms. They use committed settings, ordinary
PC rules and nominal 4 pulses/second unless explicitly stated. They do not
claim a particular equipment collection is obtainable, that every combination
is legal, or that a full combat journey was simulated. Fractional expectations
are distinguished from per-event integer HP delivery.

### A. High STR can compensate for tempo, depending on weapon payload

Compare legal level 56 Gnome/Human/Ogre Warriors. Set base stats 100, no temporary
buffs, enough ordinary damroll to reach each racial cap, one-handed weapon,
and class output 1.15. Isolate noncritical hits that have already passed all
accuracy/avoidance. The target has calculated AC 0, no skin/ward or other
modifiers; the ordinary raw quartering applies. Average the actual 90..100
damroll randomization and preserve the production integer truncations.

The fixed weapon die outcomes 20 and 100 are **synthetic payload fixtures**,
not claims about two available items. Four successfully delivered hits per
round are held constant, with native neutral intervals 3.5/4.5/5.5s.

| Race | STR / TRUE_DAMROLL | Mean HP per hit, weapon 20 | HP/s at 4 hits/round | Mean HP per hit, weapon 100 | HP/s at 4 hits/round |
|---|---|---:|---:|---:|---:|
| Gnome | 85 / 49 | 14.9091 | 17.0390 | 37.9091 | 43.3247 |
| Human | 105 / 63 | 17.9091 | 15.9192 | 40.9091 | 36.3636 |
| Ogre | 230 / 114 | 28.3636 | 20.6281 | 51.3636 | 37.3554 |

Ogre wins the smaller-payload fixture; Gnome wins the larger-payload fixture.
As the shared weapon contribution grows, fixed STR/damroll differences become
a smaller fraction of each hit while the frequency difference remains. Real
STR also affects weapon admission and opposing parry/block; real INT/DEX
affects criticals/attack count, so neither fixture establishes the final
ranking. This is precisely why tempo alone cannot settle the comparison.
[Payload](../../../src/combat/fight.c#L8406),
[cap](../../../src/magic/affects.c#L929),
[tempo fixture](race-tempo.md#a-same-class-gnome-human-and-ogre-warriors).

### B. A Troll physical hit through armor, skin, and the raw stage

Start with 500 at `melee_damage`, calculated AC-200, Troll Skin, Stone Skin,
standing posture and no other effects:

```text
500 * .80 armor                    = 400
400 * .85 Troll Skin               = 340
(340 - 46) * .55 Stone Skin        = 161.7
raw Increased baseline .25         = 40.425
integer HP delivery                = 40
```

This consumes one skin charge. The same Troll without Stone Skin takes 85;
the difference is not captured by simply adding 15% and 45% reduction.
The calculation assumes no avoidance, ward or redirection and sufficient HP
to avoid overkill clipping. [Physical delivery](../../../src/combat/fight.c#L5432).

### C. Equal incoming totals do not behave equally against skins

With AC 0, Stone Skin and otherwise neutral physical/raw stages:

- Two 50-point incoming hits: each becomes 4 after the 46 deduction, skips the
  percentage stage, and becomes 1 HP after raw reduction: **2 HP total**.
- One 100-point incoming hit: `(100-46)*.55*.25 = 7.425`, truncated to **7 HP**.

The two small hits consume two charges; the larger hit consumes one. Fixed
deductions favor the defender against small packets while charge depletion
favors repeated attacks over a longer sequence. Neither observation should
be extrapolated without the remaining charge count.

### D. Drow's extra dodge is conditional and multiplicative

Hold ordinary dodge at 30/101 and satisfy all earlier defense gates. A lightly
loaded, unstunned Drow's combined dodge is:

```text
1/11 + (10/11)*(30/101) = 36.0936%
ordinary dodge alone               = 29.7030%
```

The gain is 6.3906 percentage points, not 10. Once load reaches 100 or the Drow
is stunned, that extra branch is absent. Earlier successful parry/block means
neither dodge roll is reached. [Drow branch](../../../src/combat/fight.c#L9457).

### E. Shrug and Quick Thinker protect different stages

Use an eligible status spell that performs one shrug check and one magical
save, with ordinary save success held at 50%, no penetration and no other
immunity. At 56:

| Target | Probability the effect lands |
|---|---:|
| Human | .50 =50% |
| Halfling | .50² =25% |
| Drow | (63/101) × .50 =31.1881% |
| Half-Elf | (81/101) × .50² =20.0495% |

Half-Elf combines shrug with its 30+ Quick Thinker. The result changes if the
handler skips a gate, penetration succeeds, or the save only reduces duration.
For a damage spell whose successful save halves damage, halving the failure
probability does not halve average damage: with full damage 800, Human's mean
pre-other-defense payload is 600 and Halfling's 500. Fireball is an actual
handler with a 2:1 failed/successful-save damage ratio.
[Quick Thinker](../../../src/net/sparser.c#L1303),
[Fireball](../../../src/magic/magic.c#L4714).

### F. WIS breakpoints and a bypass flag

For 1000 incoming spell-profile damage, neutral attacker STR and no other
modifiers, WIS 150 gives MR 20 and mean remaining 895; WIS 152 gives MR 21 and
mean remaining 795. Two WIS points cross the branch that raises the minimum
reduction from 1% to 20%. These are means before raw-stage integer delivery.
With `SPLDAM_NOSHRUG`, both instead retain 1000 at this isolated stage because
the WIS predicate is bypassed. This is why equal average enemy spell damage
is insufficient without knowing their flags.

### G. Barbarian cold and Thri-Kreen psionic stacking

Barbarian's direct cold contribution is -.40. Below 31, without cold protection,
the isolated factor is .60. At 31+, native cold protection adds -.15 in the same
predicate, producing **.45**, not `.60*.85=.51`.

Thri-Kreen's psionic factor is .70. Tower of Iron Will contributes -.25 in the
same predicate, giving .45; Tiger Palm's -.35 then gives .10. These are separate
from cold vulnerability, which enters Increased and can apply Slow. Having
one strong elemental defense does not make a race broadly resistant to magic.

### H. Generic dwarf mitigation versus shrug

Take 1000 generic damage after the caller's save, neutral WIS and attacker STR,
no penetration and no other effects. Dwarf's native generic reduction gives
800 before raw delivery, hence 200 HP. Drow takes 250 HP if shrug fails and 0
if it succeeds, giving mean `250*63/101 =155.9406` HP per attempt. Against
a status-only spell, the dwarf's generic damage reduction does nothing;
against a NOSHRUG generic spell, Drow loses its shrug advantage while the
dwarf reduction remains. Variance and spell flags matter as well as the mean.

### I. Groundfighting preserves both sides of the exchange

Assume a six-attack ordinary round and a 400-point incoming physical hit,
calculated AC 0, no other modifiers. Sitting/prone without Groundfighting
reduces the attack list to 3. Prone incoming damage is
`400*1.50*.25 =150` HP. A level 21+ Barbarian or Drider retains 6 attacks and
takes `400*.25 =100` HP in that same delivery fixture; reduced dodge may also
remain available. This does not restore command access, parry or immunity to
stun. It measures a posture advantage, not a universal 2× damage bonus.

### J. Native undead healing has a threshold and a ceiling

For an eligible native undead PC with no prior successful vamp branch,
no Battle Ecstasy, missing HP and ordinary `RAWDAM_TRANCEVAMP`:

- A 12-HP delivered hit requests 9 HP from the .75 route.
- Two 6-HP hits request none from this route, despite the same total damage.
- A 100-HP delivered hit requests 75, but only 10 is restored if just 10 HP
  remains below its cap.

Lich's spell route can use its POW overheal ceiling; the ordinary native
undead route caps at normal maximum HP. Negative Energy Barrier on the target
prevents HP vamp. These conditions make “75% lifesteal” an incomplete balance
description. Healing suppression and alternate Touch/trance routes must also
be tested. [Dispatch and threshold](../../../src/combat/fight.c#L6097).

### K. Vampire holy reduction is not a blanket undead weakness

At 56, the isolated Vampire holy predicate supplies .25. Add Soulshield and
its -.10 contribution in that same predicate: the result is .15, not .225.
Other classes/buffs can add independent predicates. A Lich without the
Sacrilegious Power grant gets no corresponding native holy reduction from
this branch, but the generic branch also does not automatically double its
holy damage. Specific undead-target spells remain separate threats.

### L. Orc room population affects both directions today

With one other Orc in the room, `orc_horde_dam_modifier(1000)` produces 1015
for offense and also 1015 for the currently implemented defensive branch.
With five other Orcs, both factors are 1.075. Ownership, friendliness and
grouping do not enter this helper. A non-Orc attacking an Orc invokes the
defensive branch; an Orc attacking an Orc invokes only the attacker's offensive
branch. This is current behavior to isolate during testing, not an endorsement
of the defensive sign as intended balance.

## 11. Using the layer for balance decisions

For every comparison, record source revision and effective properties, legal
race/class/spec, level, native/current race, gear budget, weapon and shield
choices, stats, pulse applies, skill ratings, formation, posture, load, group,
room/terrain/light, active affects, resource state and enemy behavior. Hold
class/gear constant to isolate one mechanism, then compare equal-budget builds
suited to each race. Restricted races and forced test combinations should be
labelled explicitly.

Use at least these threat families:

1. Ordinary physical attacks with both small/frequent and large/infrequent hits.
2. Generic, elemental, psionic and holy spells; include damage-save and
   status-save cases, penetration, NOSHRUG and relevant globe flags.
3. Control-heavy melee, including posture, stun, paralysis and interrupted casts.
4. Damage-shield/retaliation targets and healing-suppression targets.
5. Short burst, sustained contact, and repeated encounters plus recovery.
6. Solo and representative group compositions, particularly Rrakkma, Fury,
   Sanctuary, pets and other Orcs in the room.

Record attempted actions, eligible defenses, full negations, successful hits,
damage before/after each pipeline, **actual HP loss**, healing requested versus
restored, skin charges, resource costs and control time. Separate own, pet,
proc and retaliation output. A combat “hit” counter or successful API return
does not necessarily mean the nominal target lost positive HP.

The next empirical layer should use these routes to explain encounter results.
The remaining broad knowledge gap is how legal class/spec kits, available
equipment and progression change the combinations; this document does not
pretend that an isolated factor table resolves those questions.
[Controlled comparison guidance](../CLASS-POINTS.md),
[combat metrics](../../telemetry/COMBAT_METRICS.md),
[tempo conditions](race-tempo.md#hold-the-comparison-conditions-explicitly).

## 12. Verification, coverage, and limits

The review traced ordinary melee from its round/defense/accuracy stages through
physical and raw delivery; all 36 spell and 16 raw modifier predicates;
archery delivery; damage shields; common save, stun, fear, blind, knockout and
takedown helpers; native body classification; healing/vamp; racial proc and
named-spell exceptions. It cross-checked the current 37-race roster, native
grants, properties and prior reference layers. An indexed search of racial
references was used to find exceptions outside the main combat files; it was
not treated as proof that every matching line was an active player ability.

Executable review fixtures under ignored `bin/tests/race-combat-resolution-review/`
used real engine types, production race/STR tables, property values, racial
shrug and spell-type loaders, native grant data, `find_save`, selected actual
spell predicates, the spell/raw profile accumulation and clamp code, and the
physical reduction/damroll excerpts. They covered all 37 races ×12 spell types
and all five save categories, plus the worked skin, elemental, WIS, STR,
posture and Orc comparisons. C++ fixtures ran with AddressSanitizer and
UndefinedBehaviorSanitizer. External dependencies were bounded test adapters;
these were **isolated production-code calculations**, not a running MUD or
complete obtainable-build duels.

Focused existing checks passed:

- [Racial shrug and Rrakkma](../../../tests/async/test_racial_shrug.py)
- [Racial spell damage types](../../../tests/async/test_racial_spell_damage.py)
- [Shared elemental damage and modifier bounds](../../../tests/async/test_medium_damage_dispositions.py)
- [Holy Sacrifice budgets and vamp caps](../../../tests/async/test_holy_sacrifice_and_vamp_cap.py)
- [Innate actions and Leap unlocks](../../../tests/async/test_innate_action_dispositions.py)
- [Combat effects and activation boundaries](../../../tests/async/test_medium_combat_effects.py)

Document checks cover all 37 rows in each roster table, computed table/example
values, local links/anchors, source-line bounds, conflict markers and whitespace.
No C/C++ gameplay files were changed, so a full server build or deployment was
not required. Live overrides, player equipment distributions, complete
matchups and every individual item/NPC procedure remain unmeasured; their
documented hooks explain where those effects enter rather than assigning them
invented average values.
