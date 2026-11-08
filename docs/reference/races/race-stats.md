# PC racial stats: mechanics and balance

Source review: 2026-11-08, checkout `2c04736f56ce35f2e0bf648287dcca6ea72bad29`.
This is a best-effort analysis of checked-in source and configuration, not a
measurement of deployed overrides, equipment distributions, or race win rates.
No gameplay code or balance settings are changed by this document.

Companion: [PC racial size](race-size.md). Size, race-only abilities, class
eligibility, damage/speed multipliers and experience factors also affect balance
independently of the attributes analyzed here.

## 1. Effective stats from creation through gameplay

Ten attributes are stored: Strength (STR), Dexterity (DEX), Agility (AGI),
Constitution (CON), Power (POW), Intelligence (INT), Wisdom (WIS), Charisma (CHA),
Karma (KAR) and Luck (LUK, configuration key `luc`). Base stats are permanent,
unscaled numbers. `GET_C_*` reads the computed effective number used in gameplay.
[Storage](../../../src/core/structs.h#L1071),
[accessors](../../../src/core/utils.h#L439).

For each attribute in `apply_affs`:

```text
b = saved base stat
c = summed regular modifiers (including MAX modifiers)
m = summed maximum modifiers
F = racial percentage factor selected for this attribute
u = clamp(b + c, 1, 100 + m)
effective = clamp(int(F * u / 100.0 + 0.55), 1, 511)
```

`int` truncates; the source uses +0.55, not +0.5. Ordinary stat gear fills missing
base potential up to 100. MAX stat modifiers raise **both current and maximum**:
the MAX apply falls through to the regular apply. At base 100, +10 MAX STR gives
an Ogre approximately +23 effective STR; a +10 regular STR item gives nothing
unless there is room below the current cap. Modifiers from worn items, character
affects, epic stats, auras and racewar state aggregate before this calculation.
[Formula](../../../src/magic/affects.c#L833),
[MAX fallthrough](../../../src/magic/affects.c#L1204),
[aggregation](../../../src/magic/affects.c#L1707).

### Creation, permanent growth, and recalculation

Default creation rolls `86+1d4` (87..90); advanced creation rolls `77+3d6`
(80..95), with rerolls. Both allow four +5 base-stat bonuses and swaps; bonuses
clamp at 100. The historical class-minimum table is expressed in unscaled base stats; current
PC creation rolls do not read it. Race/class eligibility is separately configured. Login floors all ten base stats at 80.
Permanent improvements include stat pools, boon/epic shops, achievements and
permanent-stat spell handlers; a handler's existence does not prove a spell is
normally learned. These modify base stats, so the racial factor still applies.
[Rolls](../../../src/cmd/actwiz.c#L5707),
[creation](../../../src/account/nanny.c#L2768),
[bonuses](../../../src/account/nanny.c#L3482),
[minimum table](../../../src/core/constant.c#L1339),
[login floor](../../../src/account/nanny.c#L2154).

Human PCs alone receive the committed `stats.bonus.Human=5` as **both c and m**
for the eight main stats and Luck, excluding Karma. An unmodified base-100 Human
has **105** in those nine effective attributes, even though `race info` lists
100% factors. Halfling Gambler's Luck, granted at **level 26**, adds **10 final
Luck** after racial scaling and the 1..511 clamp. Base-100 Halfling Luck is 120
below 26, **130** with that innate. This flat addition is not clamped again there.
[Human bonus](../../../src/magic/affects.c#L535),
[Human-only call](../../../src/magic/affects.c#L823),
[property](../../../lib/duris.properties#L985),
[Halfling grant](../../../src/classes/innates.c#L824),
[final Luck](../../../src/magic/affects.c#L1032).

Epic stat skills add `rating/10` MAX. GOOD/EVIL racewar modifiers add their value
to both c and m for the eight main stats and Luck; they omit Karma. The racewar
setter ignores its separate `max_stat` argument. These are dynamic side bonuses,
not intrinsic racial factors. Temporary buffs and debuffs affect this same
pipeline and can hit its unscaled or final caps.
[Epic stats](../../../src/magic/affects.c#L1576),
[racewar modifiers](../../../src/combat/racewar_stat_mods.c#L30).

`APPLY_*_RACE` contains a race ID. It replaces that attribute's native factor;
among multiple override affects, the largest factor wins. The first override
can still be worse than the native race: selection does not compare it with the
native factor. Each attribute can use a different race. HP selects racial CON
with a separate scan, so the same effective CON need not mean the same maximum HP.
[Override selection](../../../src/magic/affects.c#L1281),
[effective selection](../../../src/magic/affects.c#L833),
[HP CON scan](../../../src/magic/affects.c#L427).

Ordinary second/third belt attachments are excluded from normal affect
aggregation unless artifacts. Held-item type/wear restrictions also apply. The
normal scan does not have the HP special scan's blanket back-slot exclusion. `AFFTYPE_NOAPPLY`
character affects are skipped. Recalculation preserves missing HP and mana when
it changes the maxima. `balance_affects` schedules the update, so a raw write may
not instantly update every derived value.
[Equipment](../../../src/magic/affects.c#L1720),
[affects and pools](../../../src/magic/affects.c#L1767),
[scheduled balance](../../../src/magic/affects.c#L522).

Base stats are captured and restored; current stats are recomputed. A real race
change therefore changes scaling on affect recalculation; display disguises do
not automatically copy the target's factors. Corpseform is disabled at entry.
Temporary real-race save/restore concerns are covered in
[race-size-issues.md](race-size-issues.md).
[Save](../../../src/player/player_snapshot_capture.c#L155),
[load](../../../src/player/player_load_materialize.c#L264),
[disguise](../../../src/core/utils.h#L425),
[corpseform](../../../src/classes/necromancy.c#L3230).

## 2. Complete PC racial factor comparison

Values are percentages: 155 means 1.55x. At base 100 without other effects,
these equal effective stats, except Human +5 and Halfling's level-26 Luck.
All 37 PC IDs are included. Ordinary creation offers 21; the other 16 are
restricted/legacy under the shared creation policy and `CREATION_ALL_RACES`.
[Rosters](../../../src/core/constant.c#L1590),
[creation policy](../../../lib/creation_availability.cfg#L46),
[property names](../../../src/core/common.c#L79),
[property loading](../../../src/world/db.c#L804),
[committed factors](../../../lib/duris.properties#L1023).

### Ordinary creation

| Race (ID) | STR | DEX | AGI | CON | POW | INT | WIS | CHA | LUK | KAR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Human (1) | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 | 100 |
| Barbarian (2) | 155 | 90 | 90 | 165 | 70 | 70 | 95 | 75 | 90 | 100 |
| Grey Elf (4) | 90 | 110 | 120 | 90 | 105 | 115 | 120 | 120 | 100 | 100 |
| Mountain Dwarf (5) | 135 | 100 | 95 | 120 | 90 | 85 | 125 | 80 | 100 | 100 |
| Halfling (7) | 95 | 130 | 125 | 95 | 80 | 100 | 115 | 110 | 120 | 100 |
| Gnome (8) | 85 | 115 | 120 | 90 | 105 | 130 | 95 | 95 | 100 | 100 |
| Centaur (15) | 140 | 90 | 90 | 155 | 65 | 80 | 110 | 90 | 90 | 100 |
| Githzerai (30) | 100 | 100 | 100 | 100 | 120 | 115 | 110 | 90 | 100 | 100 |
| Firbolg (36) | 230 | 75 | 75 | 200 | 65 | 75 | 80 | 80 | 90 | 100 |
| Drow Elf (3) | 90 | 110 | 130 | 90 | 110 | 120 | 115 | 110 | 100 | 100 |
| Duergar Dwarf (6) | 130 | 100 | 95 | 125 | 85 | 85 | 125 | 70 | 100 | 100 |
| Ogre (9) | 230 | 75 | 75 | 200 | 60 | 70 | 80 | 50 | 90 | 100 |
| Troll (10) | 160 | 90 | 90 | 160 | 75 | 70 | 95 | 70 | 90 | 100 |
| Orc (13) | 120 | 100 | 95 | 125 | 100 | 90 | 90 | 85 | 100 | 100 |
| Githyanki (16) | 100 | 100 | 100 | 100 | 130 | 120 | 100 | 75 | 100 | 100 |
| Goblin (20) | 100 | 135 | 115 | 100 | 85 | 110 | 105 | 90 | 125 | 100 |
| Kobold (32) | 90 | 110 | 120 | 95 | 95 | 125 | 105 | 100 | 110 | 100 |
| Drider (31) | 120 | 110 | 110 | 120 | 90 | 110 | 90 | 70 | 100 | 100 |
| Thri-Kreen (14) | 115 | 125 | 130 | 105 | 70 | 65 | 65 | 75 | 90 | 100 |
| Minotaur (17) | 165 | 80 | 80 | 170 | 65 | 85 | 85 | 70 | 85 | 100 |
| Tiefling (37) | 100 | 110 | 110 | 100 | 100 | 120 | 100 | 120 | 95 | 100 |

### Restricted and legacy PC IDs

| Race (ID) | STR | DEX | AGI | CON | POW | INT | WIS | CHA | LUK | KAR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Half-Elf (11) | 105 | 110 | 110 | 102 | 125 | 115 | 110 | 115 | 100 | 100 |
| Illithid (12) | 70 | 90 | 90 | 85 | 200 | 150 | 110 | 25 | 100 | 100 |
| Shade (18) | 85 | 140 | 125 | 100 | 120 | 140 | 100 | 100 | 115 | 100 |
| Revenant (19) | 145 | 90 | 110 | 169 | 85 | 70 | 75 | 50 | 100 | 100 |
| Lich (21) | 70 | 100 | 115 | 70 | 150 | 145 | 100 | 90 | 100 | 100 |
| Vampire (22) | 120 | 125 | 115 | 100 | 110 | 120 | 100 | 120 | 100 | 100 |
| Death Knight (23) | 120 | 95 | 95 | 120 | 105 | 100 | 95 | 70 | 100 | 100 |
| Shadow Beast (24) | 120 | 130 | 130 | 106 | 100 | 70 | 70 | 70 | 120 | 100 |
| Storm Giant (25) | 150 | 70 | 70 | 150 | 80 | 80 | 80 | 65 | 100 | 100 |
| Wight (26) | 135 | 80 | 80 | 155 | 100 | 60 | 60 | 50 | 100 | 100 |
| Phantom (27) | 90 | 140 | 130 | 97 | 125 | 100 | 100 | 100 | 100 | 100 |
| Harpy (28) | 80 | 115 | 130 | 109 | 100 | 120 | 110 | 100 | 80 | 100 |
| Orog (29) | 160 | 120 | 120 | 170 | 50 | 40 | 80 | 50 | 75 | 60 |
| Planetbound Illithid (33) | 83 | 105 | 105 | 82 | 125 | 120 | 100 | 100 | 100 | 100 |
| Kuo Toa (34) | 135 | 115 | 115 | 140 | 95 | 85 | 85 | 90 | 100 | 100 |
| Wood Elf (35) | 125 | 115 | 115 | 135 | 95 | 85 | 91 | 85 | 100 | 100 |

### Compare equal base rolls, equal gear, and equal displayed stats separately

An Ogre at base STR 90 has 207 effective STR; a base-90 Human has 95 after its +5.
Give each +10 MAX STR: 230 versus 105. At base100 with that same item: 253 versus
115. Regular +10 STR instead fills the 90 roll to its ordinary cap (Ogre230,
Human105), then stops. Thus high factors improve both initial stats and the
return on equal MAX gear.

Equal displayed stats remove some racial advantage on direct checks, but not
race-relative bonuses, racial HP terms or non-stat race mechanics. Rank races
within legal class/build contexts, not by averaging their factor columns.
Ogre/Firbolg lead ordinary STR/CON; Halfling/Goblin lead ordinary DEX/Luck;
Drow/Thri-kreen lead ordinary AGI; Gnome leads ordinary INT; Githyanki leads
ordinary POW; Dwarves lead ordinary WIS; Grey Elf/Tiefling lead ordinary CHA.
These identify attribute leaders, not overall winners.

## 3. Shared thresholds and derived mechanics

### STAT_INDEX and table plateaus

The active `I(x)=STAT_INDEX(x)` maps:

```text
x<1:0; 1..9:1; 10..15:2; 16..21:3; 22..27:4; 28..33:5;
34..39:6; 40..45:7; 46..50:8; 51..55:9; 56..61:10;
62..67:11; 68..73:12; 74..79:13; 80..85:14; 86..91:15;
92..100:16; 101..112:17; 113..124:18; 125..136:19;
137..148:20; then +1 per 12 points, up to 509+:51.
```

`STAT_INDEX2` is a separate display-description scale. A +1 crossing 100/101 or
124/125 can change many table-driven effects; a larger increase within a bucket
can leave them unchanged while improving direct-stat checks.
[Active index](../../../src/core/utility.c#L3861),
[display index](../../../src/core/utility.c#L3970).

STR's table supplies hit, damage, carry and wield values. DEX's reaction,
missile and pickpocket columns have active consumers. Its `p_locks`/`traps`
columns and `int_app.learn` have no active gameplay consumer found in this census;
their presence does not establish a current bonus. WIS's old “practice” bonus
column is actively used in parry, reaching 3 at WIS 101 and staying there.
[Tables](../../../src/core/constant.c#L807),
[layouts](../../../src/core/structs.h#L1997),
[WIS parry use](../../../src/combat/fight.c#L9789).

### Strength, burden, and spell damage

`TRUE_DAMROLL=damroll+str_app[I(STR)].todam`, before the usual damage multipliers.
230% STR therefore does not mean 2.3x all damage. The normal to-hit function uses
hitroll, skill, level/class and Luck; STR's table hit value is explicitly used
by certain skills and defense-opposition checks and in some displays.
[Damage](../../../src/core/utils.h#L527),
[damage use](../../../src/combat/fight.c#L8423),
[to-hit](../../../src/combat/fight.c#L6791).

STR determines carry capacity and wield limits; DEX determines PC item count
`6+I(DEX)/3`. Higher capacity lowers burden for the same equipment. The burden
function maps occupied capacity percentages <10,<20,<30,<40,<55,<65,<75,<85,<95,
>=95 to 75,85,95,105,125,145,165,185,200,300 respectively. It changes movement
cost (`burden*cost/200`), calculated AC (`+burden-75`) and AGI/DEX saves. Mount
load includes the rider's stored weight plus gear. Dragging and pickup handling
also use capacity, so STR has travel and logistics consequences beyond damage.
[Capacity/count](../../../src/core/utils.h#L612),
[burden](../../../src/cmd/actmove.c#L126),
[movement](../../../src/core/utility.c#L2618),
[rider load](../../../src/core/utility.c#L4343),
[wielding](../../../src/cmd/actobj.c#L6533).

The shared spell-damage path adds a STR multiplier: <=120 no bonus; 121..140
random +1..10%; 141..180 +11..20%; >=181 +21..30%. The macro names the top of
the band; application randomizes the preceding ten percentage points. This is
not a universal modifier to spell success, healing or duration.
[Thresholds](../../../src/core/utils.h#L1431),
[application](../../../src/combat/dam_mods.c#L682).

Monk bare-hand damage loses excess full worn weight over `level*STR/100`, bounded
to at least 1 damage. Monk base attacks lose one per ten excess weight above
`STR/2`, using half of each equipped item's weight and retaining at least one
base attack. Inventory is excluded from that attack penalty. Individual monk
armor weight restrictions are separate again.
[Bare hands](../../../src/classes/new_skills.c#L674),
[attacks](../../../src/combat/fight.c#L10411),
[armor](../../../src/cmd/actobj.c#L6016).

### Dexterity, hitroll, and extra attacks

Every two effective DEX **above the character's own racial DEX factor** add one
hitroll after the ordinary PC hitroll cap, still bounded at 127. High natural
racial DEX at unscaled100 alone creates no excess-stat hitroll. Human+5 does.
[Hitroll](../../../src/magic/affects.c#L981).

With `w=floor(100*weaponWeight/STR)`, extra attacks require:

- Primary slot: DEX>=125 and w<=6, or DEX>=150 and w<=20.
- Secondary slot: DEX>=150 and w<=6. A two-handed primary supplies the weight
  when the secondary is empty; on success that adds a primary attack.
- Each eligible slot rolls `number(1,DEX)>60`, probability `(DEX-60)/DEX`.
  DEX 125 gives 52%; DEX 150 gives 60%.

The active code accepts null weapons as weight0, despite its comment saying
bare hands are excluded. The old multi-attack ladder below it is commented out.
Equal DEX with different STR can therefore qualify different weapon weights.
[Active logic](../../../src/combat/fight.c#L10698).

### Agility, armor, dodge, and stability

AGI affects AC twice: stored current AC loses the amount above the character's
racial AGI factor, then final AC adds `io_agi_defense(AGI)` and burden. Final AC
clamps -750..100. In the normal non-`GOND_KLUDGE` build, the defense component is:

```text
i=max(-275,275-AGI)
defense=-((18906-i*i/4)/151-44)   // integer arithmetic
```

This component improves until AGI is near 275, then worsens; the separate
above-race subtraction can offset that. Evaluate combined AC when balancing.
[Race-relative AC](../../../src/magic/affects.c#L921),
[formula](../../../src/world/handler.c#L5320),
[final AC](../../../src/combat/fight.c#L6752).

Dodge starts from `int(AGI*damageFactor)-attackerWeaponSkill`, adds
`(I(defenderAGI)-I(attackerDEX))/2` and level difference, then bounds the result
between `AGI/10` and50 before posture, stun, class and innate modifiers. A normal
success uses a 1..101 roll. AGI also supplies half its value to weapon-skill
fumble rescue, plus leap and quick-step checks.
[Dodge](../../../src/combat/fight.c#L9193),
[contest](../../../src/combat/fight.c#L9334),
[bounds](../../../src/combat/fight.c#L9352),
[fumble](../../../src/combat/fight.c#L7609).

Highest-circle casting/willing can schedule an abort when
`number(0,100)>AGI/2+50`. AGI>=100 removes this failure route. This is separate
from casting speed, interrupts and target saves.
[Will](../../../src/net/sparser.c#L2410),
[cast](../../../src/net/sparser.c#L2906).

### Constitution and maximum hit points

For races other than original Illithid (ID 12), let L=level, C=min(effectiveCON,780), R=the HP function's
racial CON factor, K=class HP multiplier, H0=base hit points, and
`q(x)=L*(-14*x*x/152100+28*x/390-4)`:

```text
HP=H0*R/100+(precalculatedMaxHP-H0)
   +q(min(C,R))*(K-1)+(L/50*R*R*0.025)*K+q(C)
   +17+casterMaxCONGearBonus+toughness+newbie+hardcore
```

The result is integer, with some intermediate truncations. K is the better of
the classes for multiclass PCs. R begins at actual-race CON and only increases
through the function's separate valid worn CON-race scan. It differs from the
effective-stat factor selection; equal displayed CON does not equalize HP.
The committed `hitpoints.conMultiplier` is 0.025. Racial CON affects both base HP
scaling and a quadratic term, so it has a much larger effect than a flat CON
bonus. Do not substitute `racial_data.hp_bonus` for R.
[HP formula](../../../src/magic/affects.c#L410),
[property](../../../lib/duris.properties#L990).

Qualifying caster classes, or multiclasses with both classes in the caster set,
also get `wornMAX_CONsum*R/100*1.0` HP with the committed setting. This sum excludes
back and second/third belt attachments and is extra to the effective-CON effect.
Spell/epic MAX CON is not this gear sum.
[Classes](../../../src/core/utils.h#L1255),
[gear HP](../../../src/magic/affects.c#L471).

Original Illithid (ID 12) characters use
`precalculatedMaxHP+level+10+max(CON,100)-100+IllithidToughness` instead. CON below
100 has no further penalty in this term; above 100 adds one HP per point. CON
also affects physical stat saves, underwater breath time and falling injuries.
Normal HP regeneration has no general direct CON term; it uses posture, innates,
level/terrain and explicit regeneration instead.
Planetbound Illithid (ID 33) does **not** satisfy `IS_ILLITHID` and uses the
ordinary formula. [Identity predicate](../../../src/core/utils.h#L884),
[Illithid HP](../../../src/magic/affects.c#L417),
[breath](../../../src/mob/specials.c#L154),
[fall injury](../../../src/world/falling.c#L78),
[HP recovery](../../../src/world/limits.c#L254).

### Power, Intelligence, mana, critical hits, and vamping

Derived mana is `int(level/50.0*POW*INT*0.065)+6`, **added** to base/equipment mana
during PC recalculation. The committed property is 0.065; the code fallback is
0.025. POW and INT multiply: +10% in both means about +21% in this derived term.
Ordinary mana recovery starts `(POW+INT)/2.5`; meditation uses `(POW+INT)/0.2`,
then posture, feeblemind, explicit regen and difficulty modify it.
[Mana](../../../src/magic/affects.c#L344),
[property](../../../lib/duris.properties#L984),
[pool update](../../../src/magic/affects.c#L1804),
[recovery](../../../src/world/limits.c#L148).

Melee's initial critical chance is 8 below INT 105, then `8+(INT-100)/5`:105=>9,
125=>13,200=>28 out of 100. A second roll confirms with weaponSkill+LUK/4 against
30..101. Amorphous bodies and quick step can prevent the critical. The comment
claiming 100INT=>5% and200=>25% is stale.
[Critical threshold](../../../src/core/utils.h#L1426),
[confirmation](../../../src/combat/fight.c#L8015).

`POW_DIFF(attacker,defender)=I(defenderPOW)-I(attackerPOW)`. Many psionic saves
therefore use `2*I(defenderPOW)-I(attackerPOW)+otherModifiers` before the save cap.
Individual spells clamp the difference, add levels or make multiple saves.
POW also sets the vamp health ceiling, normally
`clamp(POW/90.0,1.1,2.5)+configuredAllBonus` times maximumHP. Prime antipaladins
add0.25 inside the2.5 ceiling. This is a ceiling, not the amount leeched.
[POW difference](../../../src/core/utils.h#L1009),
[example save](../../../src/classes/psionics.c#L386),
[vamp](../../../src/core/utils.h#L1416),
[ceiling use](../../../src/combat/fight.c#L5942).

### Wisdom and incoming spell damage

`MR=clamp((WIS-110)/2,0,75)` using integer division. MR 0 does nothing; MR 1..20
rolls1..MR percent damage reduction;21..40 rolls20..MR;41..75 rolls40..MR.
`SPLDAM_NOSHRUG` bypasses it. This is randomized damage reduction, not a chance
to negate a spell and its effects. WIS 112 starts MR 1;150=>20;152=>21;190=>40;
192=>41;260=>75.
[Formula](../../../src/core/utils.h#L1430),
[damage application](../../../src/combat/dam_mods.c#L664).

WIS parry contributes `wis_app[I(WIS)].bonus*5`, capped at+15 from WIS 101.
Other WIS effects keep growing: divine recovery, offensive/defensive spell
contests, propagated-message perception, theft resistance and Jin Touch damage.
It is not a universal healing multiplier.
[Parry](../../../src/combat/fight.c#L9789),
[messages](../../../src/world/graph.c#L1682).

### Charisma, calming, pets, and prices

Calming uses integer `CHA/9` below 80, `CHA/7` at 80..160, `CHA/4` above 160.
160=>22 but161=>40 is a real discontinuity. Callers add their own bonuses,
exceptions and random checks; this is not universal immunity to aggression.
CHA also affects elemental HP/control, recipe learning, beast follower admission,
Bard songs, Lay Hands and knight trample. Pet-duration divisions often read the
**pet's INT**, not the owner's; those must not be credited to PC racial INT.
[Calming](../../../src/core/utils.h#L1428),
[command aggro](../../../src/cmd/interp.c#L3958),
[elementals](../../../src/magic/magic.c#L2981),
[recipes](../../../src/combat/fight.c#L3285),
[beasts](../../../src/magic/smagic.c#L4297),
[Lay Hands](../../../src/classes/innates.c#L6100).

Shops look up `cha_app[I(max(100,CHA))]`, but buy/sell guards then reset the
computed favorable factor to the shop baseline+/-0.01. The positive >=100 table
values therefore do not yield the ordinary CHA price benefit one might expect.
Barter's separate `CHA>number(0,125)` remains active (buy factor -0.25 on success,
+0.10 on failure). Review this before promising high-CHA ordinary-shop discounts.
[Buy](../../../src/economy/shop.c#L1103),
[sell](../../../src/economy/shop.c#L1310),
[value](../../../src/economy/shop.c#L1473),
[list](../../../src/economy/shop.c#L1618).

### Luck and Karma

Luck affects hit multipliers, critical confirmation, parry/riposte, archery,
numerous moves, chaos/spells, loot drops, rare epic awards, enhancement,
mining and salvage. `LUK/2>number(0,100)` succeeds `min(101,LUK/2)/101` for
nonnegative integer Luck. Other callers use different denominators (including
0..10), so a single generic “Luck percent” is misleading.
[Hit Luck](../../../src/combat/fight.c#L6867),
[drops](../../../src/item/random_equipment_drop.c#L89),
[epics](../../../src/combat/fight.c#L3261),
[enhance](../../../src/item/enhance.c#L201),
[mining](../../../src/economy/mining.c#L473),
[salvage](../../../src/item/salvage.c#L277).

Karma is stored, scaled, modified and displayed, but no ordinary gameplay outcome
conditioned on effective Karma was found in this census. PC factors are100 except
restricted Orog KAR 60. The absence of an active Karma consumer means that factor
difference presently has no demonstrated ordinary combat/economy benefit or
penalty. Human and racewar bonuses omit Karma.

## 4. Detailed consumer catalog

Notation in this catalog: A is the acting character, D the target/defender;
`clamp(lo,x,hi)` and integer division follow the source. Listed terms are the
stat-dependent part of the mechanic, not its full probability after skill,
level, size, posture, awareness, armor, resistances and ability-specific guards.
Those conditions still apply; see [size limits](race-size.md) for legal targets.

### 4.1 Shared stat saves and their callers

`StatSave` accepts STR, DEX, AGI, CON, POW, INT and WIS (not CHA, Luck or Karma).
It succeeds when `number(1,21)<clamp(1,I(stat)+mod,20)`. Therefore the ordinary
maximum is **19/21**, not20/21 and not the comment's implied single failure out
of 21. At I=16 and no modifiers, success is 15/21; at I=20 it is 19/21. Bigger
attributes can still matter when penalties bring the score below the cap.
[Complete save](../../../src/core/utility.c#L3247).

AGI saves add haste+2/slow-2 for non-monks, load penalties1/2/3 at burden>99/>199/
>299, stunned-3, posture `GET_POS-3`, flight/levitation+1. DEX gets the same load,
stun and posture adjustments, haste+2/slow-2, thief+3, but no flight+1. INT/POW
can instantly pass through Quick Thinking before the ordinary roll. CON/WIS/STR
use the index plus caller modifier directly. The Quick Thinking description
mentions another roll after failure; this implementation itself performs an
initial innate pass check, then one ordinary save.
[Adjustments](../../../src/core/utility.c#L3266).

Active stat-save families found in the census:

- **POW:** molecular agitation, ego whip, inflict pain, psionic wave blast,
  domination and confuse use the defender/caster power-index difference; mental
  anguish and memory block clamp it to at most0. Spinal corruption has separate
  level-sensitive and power-difference saves. Other psionic controls use defender
  POW with level modifiers or no power difference. Vampire bite's NPC conversion
  route also uses POW difference. Defensive POW is consequently useful even on
  classes which never cast psionics.
- **AGI:** shaman movement/control spells, some physical magic, earth/water
  effects, several NPC sweep/earthquake/petrification/warhorse attacks and parasite
  attachment. Individual modifiers and ability guards differ.
- **DEX:** ballistic attack and the NPC theft path use DEX saves.
- **INT:** noticing shadowed movement and some NPC/pet awareness decisions.
- **CON/WIS:** individual NPC spell/proc defenses, including the multi-stat
  special-procedure checks. They do not replace the separate general magical
  saving-throw system.

Sources: [psionic saves](../../../src/classes/psionics.c#L386),
[mental anguish](../../../src/classes/psionics.c#L2044),
[spinal corruption](../../../src/classes/psionics.c#L1943),
[physical psionic save](../../../src/classes/psionics.c#L874),
[shaman AGI effects](../../../src/magic/smagic.c#L750),
[magic AGI effects](../../../src/magic/magic.c#L5029),
[shadow movement](../../../src/cmd/actmove.c#L1165),
[bite](../../../src/classes/innates.c#L2161),
[NPC saves](../../../src/specs/specs.mobile.c#L666),
[NPC sweeps](../../../src/specs/specs.underworld.c#L318).


For completeness, these are the remaining explicit stat-save caller groups;
shared formulas above apply, but target/level modifiers remain caller-specific.

| Caller group | Stat / additional modifier | Source |
|---|---|---|
| Control flames; ego blast | Defender POW, no extra difference | [flames](../../../src/classes/psionics.c#L1300), [blast](../../../src/classes/psionics.c#L1362) |
| Psychic crush; detonate and alternate detonate | Defender POW, `(targetLevel-casterLevel)/5` | [crush](../../../src/classes/psionics.c#L1539), [detonate2](../../../src/classes/psionics.c#L1733), [detonate](../../../src/classes/psionics.c#L1867) |
| Innate blast | Defender POW, `max(-3,(casterLevel-targetLevel)/3)` | [innate blast](../../../src/classes/psionics.c#L4062) |
| Ballistic attack | Defender DEX, zero extra modifier | [ballistic](../../../src/classes/psionics.c#L874) |
| Cyclone; earthquake; chaotic ripple | Defender AGI with level, save or randomized modifiers | [cyclone](../../../src/magic/magic.c#L5029), [quake](../../../src/magic/magic.c#L5390), [ripple](../../../src/magic/magic.c#L26581) |
| Elemental fury; pythonsting; transfer wellness | Defender AGI, respectively-4, computed temp, and-5 | [fury](../../../src/magic/smagic.c#L750), [python](../../../src/magic/smagic.c#L2291), [wellness](../../../src/magic/smagic.c#L2561) |
| NPC stomp/sweep | Target AGI with attack-specific modifiers | [stomp](../../../src/mob/mobact.c#L5005), [sweep](../../../src/mob/mobact.c#L5096) |
| Fetid breath | Separate target CON, AGI and WIS checks | [breath](../../../src/specs/specs.mobile.c#L666) |
| Warhorse | Target AGI with level modifier or-2; one response check is on the horse itself | [warhorse](../../../src/specs/specs.mobile.c#L8284) |
| Dragonkind; piercer; Tiamat | Target AGI, respectively-2,-10,-4 | [dragonkind](../../../src/specs/specs.underworld.c#L318), [piercer](../../../src/specs/specs.underworld.c#L1300), [Tiamat](../../../src/specs/specs.underworld.c#L1959) |
| NPC steal | Victim DEX with level modifier | [theft](../../../src/mob/specials.c#L415) |
| Water crossing / movement shadow awareness | Observer INT,-4 | [water](../../../src/cmd/actmove.c#L1165), [movement](../../../src/cmd/actmove.c#L1722) |
| NPC mundane pet/master awareness | NPC INT,0 | [awareness](../../../src/mob/mobact.c#L7943) |
| Zone powerspell message | Recipient POW,0 controls receiving the message | [message](../../../src/mob/mobact.c#L9055) |

No active `StatSave(...APPLY_STR...)` caller was found; support in the dispatcher
alone is not a current universal STR-saving-throw benefit. Each listed handler
can still reject targets or bypass the save under its own conditions.

### 4.2 Automatic melee defenses and weapon interactions

| Mechanic | Stat contribution and gameplay consequence | Source |
|---|---|---|
| Shield block | Defender score adds `DEXreaction*2`; attacker opposition adds `STRhit*4`. The final contest rolls separately against each score. Defender Luck reads into a separate `percent` variable, but final success uses `learned`; do not credit it as a working Luck bonus without fixing/reviewing that path. | [block](../../../src/combat/fight.c#L9533) |
| Parry | Defender adds `DEXreaction*15 + WISbonus*5`; attacker adds `STRhit*10 + STRdamage*15`, plus `A.STR-D.STR-35` if positive. Luck can raise defender score5% after an opposed Luck roll. This is a score contest, not additive percent chance. | [parry](../../../src/combat/fight.c#L9846) |
| Monk riposte | Defender adds `DEXreaction*2 + STRhit*1.5`; subtracts attacker STRhit+STRdamage. Off feet, AGI versus 1..1000 plus martial arts can trigger a recovery to standing and clear lag, with its own cooldown. | [riposte](../../../src/combat/fight.c#L9700) |
| Ordinary riposte | Opposed random Luck rolls participate in the riposte path. | [Luck contest](../../../src/combat/fight.c#L3952) |
| Mangle | The target/actor DEX difference changes skill rating by 5 per effective DEX. The final rating and expert-parry penalties still gate success. | [mangle](../../../src/combat/fight.c#L3742) |
| Quick step | Its avoidance threshold includes `level/5 + I(AGI)`; needs the skill and the normal response conditions. | [quick step](../../../src/combat/fight.c#L7705) |
| Leap | Base chance includes `AGI/7 - load_modifier/100`. | [leap](../../../src/combat/fight.c#L9125) |
| Rapier/dirk interaction | Defensive contest threshold uses `(AGI+WIS)/2 + level`. | [threshold](../../../src/combat/fight.c#L549) |
| Acid blood shield | Attacker AGI increases avoidance through the configurable divisor, so high AGI can reduce retaliation independently of ordinary dodge. | [shield](../../../src/combat/fight.c#L5338) |
| Arcane block | Threshold `level+LUK/10+arcaneBlockRating`, versus 1..250, before other spell-damage conditions. WIS damage reduction and this Luck effect are separate. | [arcane block](../../../src/combat/dam_mods.c#L259) |
| Guard | Guard AGI minus attacker AGI is bounded by the guard helper's agility limit; victim and attacker Luck separately adjust the contest. | [guard](../../../src/combat/guard.c#L334) |
| Zealot proc | STR must exceed1..340 to trigger the random proc selection; some outcomes add attacks, some grant MAX STR below STR 300. This is class/spec-specific, not general STR attack speed. | [zealot](../../../src/combat/fight.c#L10535) |
| Sanguinis ignis reaction | A mounted Dragoon opponent's response uses its shaman spell-knowledge rating but **the current actor's POW/20**, a potentially wrong-subject stat read worth reviewing. | [reaction](../../../src/combat/fight.c#L11162) |

The block function's temporary `percent` variable also appears uninitialized on
some paths and is not used by the final success contest. That is a source-level
review finding; the useful DEX/STR score terms above remain directly visible.
Do not turn it into a measured gameplay-crash claim without executable coverage.

### 4.3 Takedowns, kicks, charges, and dirty fighting

The shared takedown AGI adjustment is asymmetric. Let d=A.AGI-D.AGI (actor
Thri-kreen AGI is capped100 here). It computes
`0.70*priorChance + 0.30*clamp(0,100+d*(d<=0?2:0.5),125)`.
A 50-point AGI deficit can lose the entire30-point stat contribution; a 50-point
advantage adds only7.5 beyond the neutral contribution. Defender Thri-kreen AGI
is not capped by this actor-only rule. Shared Luck checks at `LUK/10` versus
1..100 multiply chance1.1 or0.9. Callers select which checks apply.
[Shared takedown](../../../src/cmd/actoff.c#L588).

| Move | Stat-dependent terms and practical consequence | Source |
|---|---|---|
| Bash | On the physical body path, blends70% prior chance and30% `clamp(-10,100+A.STR/2+A.DEX-D.AGI,110)`; Thri-kreen actor DEX is capped100. Damage begins `1+STRdamageTable`, then shield and other terms. | [chance](../../../src/cmd/actoff.c#L8748), [damage](../../../src/cmd/actoff.c#L8356) |
| Tackle | Shared takedown checks; on the failed flying/body recovery route, AGI+level versus 1..200 determines kneeling versus falling prone; CON versus 1..125 can prevent self-stun. Actor/target Luck use1..100 rolls. | [tackle](../../../src/cmd/actoff.c#L9322), [recovery](../../../src/cmd/actoff.c#L9442) |
| Bodyslam | Chance factor `clamp(60,100+(A.AGI-D.AGI)/2,155)%`; damage STRdamageTable+5. | [chance](../../../src/cmd/actoff.c#L11678), [damage](../../../src/cmd/actoff.c#L11540) |
| Trip | Chance factor `clamp(72,A.AGI,160)%`, then shared takedown. Target AGI minus actor AGI versus 0..110 can pull the actor down too. Existing quadruped size-window defect still applies. | [trip](../../../src/cmd/actoff.c#L12419) |
| Shieldpunch | Where the frontline adjustment applies, factor `clamp(6,10+(A.AGI-D.AGI)/10,15)/10`; Luck multiplies1.1/0.9. | [shieldpunch](../../../src/cmd/actoff.c#L10551) |
| Sweeping thrust | Chance factor `clamp(6,10+(A.DEX-D.AGI)/5,15)/10`. Failed sweep can drop the actor when AGI loses to 0..100, with a separate1-in3 gate. | [sweep](../../../src/cmd/actoff.c#L10828) |
| Charge | Adds `clamp(-20,(A.STR-3*D.AGI/2)/3,20)` to chance. Luck multiplies1.1/0.9; damage also uses the STR damage-table path. | [charge](../../../src/cmd/actoff.c#L1767) |
| Lance charge | Actor/target Luck/10 modifies success1.1/0.9; actor Luck/2 can raise the rolled effect tier. | [lance](../../../src/cmd/actoff.c#L1099) |
| Kick | Base damage `max(STR/2,martialArtsRating)+kickRating`. Success multiplies by `clamp(80,DEX,125)%` and `clamp(80,A.STR+A.AGI-D.AGI,125)%`; Luck/10 adds/removes5%. | [damage](../../../src/cmd/actoff.c#L4100), [chance](../../../src/cmd/actoff.c#L4263) |
| Rearkick | Base damage `max(STR/2,kickRating*configuredRearKickFactor)`, randomized from half to full. | [rearkick](../../../src/cmd/actoff.c#L11018) |
| Roundkick | Base damage `A.DEX+rating-D.AGI`; AGI difference contributes a bounded20..150% chance factor. DEX-AGI versus 0..100 gates the special knockdown. Actor Luck uses0..10 while target uses0..100: a large asymmetric Luck effect, not matching percentages. | [roundkick](../../../src/cmd/actoff.c#L5869), [Luck](../../../src/cmd/actoff.c#L5943) |
| Headbutt | Damage scales by STR/180 before level/size/settings. Chance adds `(A.AGI-D.AGI)/2`; actor/target Luck/2 versus 0..80 adds/subtracts10% of chance. | [damage](../../../src/cmd/actoff.c#L6271), [chance](../../../src/cmd/actoff.c#L6563) |
| Sneaky strike | Adds STRdamageTable+DEX/4 before damage multipliers; individual follow-up effects subtract targetAGI/6 from skill threshold. | [damage](../../../src/cmd/actoff.c#L6943), [effects](../../../src/cmd/actoff.c#L7141) |
| Backstab | Damage adds `(DEX+STR)*configuredStrDexFactor` and `number(10,Luck)/10` plus damroll/weapon terms. On the awareness path, targetINT*5/4 is compared to random opportunity derived from actorAGI/2+rating. Luck modifies attack chance on both sides. | [damage](../../../src/cmd/actoff.c#L7389), [awareness](../../../src/cmd/actoff.c#L7630), [Luck](../../../src/cmd/actoff.c#L7928) |
| Disarm | Adds `(rating+I(actorDEX)-I(targetDEX)+levelDifference)/2` to the chance. | [score](../../../src/cmd/actnew.c#L1539) |
| Dirt toss | Blindness duration is `clamp(5sec,rating*actorDEX/100-targetAGI,10sec)` in pulses. High targetAGI can floor it even against high DEX. | [duration](../../../src/cmd/actnew.c#L2867) |
| Throat crush | Threshold starts rating-targetAGI/10; beating targetDEX multiplies1.1 (otherwise0.9), and beating targetLuck applies a separate1.1 (otherwise0.9). | [crush](../../../src/cmd/actnew.c#L3835) |
| Hamstring | `rating-targetAGI/10` supplies the threshold; this is independent of STR damage bonuses. | [helper](../../../src/cmd/actnew.c#L3888), [use](../../../src/cmd/actnew.c#L4094) |
| Capture | Adds AGI difference/3, DEX difference/5, Luck difference/5 to actor chance before its 1..85 bound. | [capture](../../../src/classes/new_skills.c#L4228) |
| Gaze / restrain | Both scale chance by actorPOW/targetPOW, then levels and separate random terms. Luck/2 rolls versus 0..110 (actor) and0..90 (target) add/subtract5%; body/size guards remain. | [gaze](../../../src/cmd/actoff.c#L13297), [restrain](../../../src/cmd/actoff.c#L13607) |
| Parlay / battle orders | Actor Luck/2 can multiply the rating/chance1.1. | [parlay](../../../src/cmd/actoff.c#L9088), [orders](../../../src/cmd/actoff.c#L12993) |
| Combination / barrage | Actor Luck/2 triggers a5% score increase in the repeated attack sequences. | [combination](../../../src/cmd/actoff.c#L3377), [barrage](../../../src/cmd/actoff.c#L3585) |

### 4.4 Grapples, monk abilities, and mounted specials

- Bearhug damage starts `clamp(40,level+3*(A.STR-D.STR)*configuredFactor*rating/100,300)`
  plus its damage roll. Strength against the opponent matters, not just own STR.
- Improved headlock/leglock bonus effects use
  `clamp(0,A.STR-D.STR,5+grapplerCombat/20)+number(0,2)`.
  Continuing headlock/leglock damage uses `DEX/7 * damageFactor`; break damage uses
  `(DEX/10+STR/10)*4*breakFactor`. Armlock ordinary damage uses
  `DEX/15*4*factor`. Integer division can create plateaus before multiplication.
- Quivering palm's stat damage is `2*DEX+rating`. Jin Touch rolls DEX d3 + AGI d3
  + WIS d3, then divides4 before further modifiers. Chi Sight duration uses WIS/10.
- Dragoon power contribution is `max(0,(POW-100)/2)` for dragon roar, breath and
  strike success. Dragon strike knockdown chance multiplies by
  `clamp(83,50+AGI/2,120)%`; trample uses DEX in that position. Knight trample's
  control contribution is `max(0,(CHA-100)/2)`.
- Failed strike/trample recovery uses DEX (`50+DEX/2`) versus 0..100, then AGI
  (`50+AGI/2`) versus 0..100 for landing posture, with lancer/knight exceptions.
- Stampede's target avoidance includes targetAGI index alongside level and awareness.

Sources: [bearhug](../../../src/combat/grapple.c#L220),
[headlock](../../../src/combat/grapple.c#L805),
[armlock](../../../src/combat/grapple.c#L937),
[leglock](../../../src/combat/grapple.c#L1337),
[palm](../../../src/classes/new_skills.c#L1465),
[Jin Touch](../../../src/classes/new_skills.c#L1609),
[Chi](../../../src/classes/new_skills.c#L4588),
[dragoon power](../../../src/cmd/actoff.c#L4594),
[roar](../../../src/cmd/actoff.c#L4768),
[breath](../../../src/cmd/actoff.c#L5120),
[strike](../../../src/cmd/actoff.c#L5575),
[trample](../../../src/cmd/actoff.c#L11387),
[stampede](../../../src/cmd/actnew.c#L536).

### 4.5 Archery and thrown weapons

Archery speed is `min(weaponSpeed,int(DEX*1.5),skillSpeedLimit)` before haste and
conversion into timing/shots. Arrow strength is `min(weaponStrength,STR)`.
Arrow damage adds `number(0,LUK/40)+number(0,DEX/25)` as well as the strength,
weapon, skill and hitroll terms. Critical shot's threshold is
`criticalShotRating+Luck-100` versus 1..3000, followed by its configured damage
multiplier; do not substitute the ordinary INT-based melee critical rate.
Arrow-block score includes shieldBlockRating+AGI/2+shieldCombatRating/2+DEX/5+LUK/5.
Thrown-weapon chance adds DEXmissileTable*5 and a separate Luck/2-triggered1.1
multiplier. Weight/strength admission can still prevent using an item at all.
[Archery](../../../src/combat/range.c#L781),
[arrow damage](../../../src/combat/range.c#L1041),
[critical shot](../../../src/combat/range.c#L503),
[arrow block](../../../src/combat/range.c#L538),
[throw](../../../src/combat/range.c#L1478).

### 4.6 Spell recovery and memorization

These formulas repeatedly compare a current attribute with its own race factor,
so a +1 current INT above a high racial baseline can matter differently from
an equal current INT on another race. Let F be the indicated native factor and
`excess=max(0,effective-F)`. Larger tick factors shorten recovery:

| Recovery route | Attribute-dependent tick factor | Source |
|---|---|---|
| Ordinary book class | `max(1,I(INT))+excessINT` | [book recovery](../../../src/classes/memorize.c#L801) |
| Dragoon | `max(1,I(POW))+excessPOW` | [dragoon](../../../src/classes/memorize.c#L821) |
| Ordinary divine/non-book | `max(1,I(WIS))+excessWIS`; druid/blighter multiclass uses `int(excessWIS/1.3)` | [divine](../../../src/classes/memorize.c#L831) |
| Undead, warlock, angel and necroplasm route | `max(1,I(POW))+0.7*excessINT+0.35*excessWIS`, with float arithmetic | [undead](../../../src/classes/memorize.c#L638) |
| Tupor route | Ethermancer/shaman uses WIS index+excessWIS; others INT index+excessINT; multiplied by tupor configuration | [tupor](../../../src/classes/memorize.c#L684) |

The general time is proportional to circle factor divided by level factor and
tick factor, with class/multiclass, terrain, meditation, alignment, nature epics,
recovery settings and ability-specific modifiers afterward. Undead/tupor branch
selection happens before ordinary class selection. The commented alternative
psionic POW memorization branch is inactive; psionics use mana instead.
Human +5 creates excess recovery credit at base100 even without MAX gear.
[Dispatch and full recovery](../../../src/classes/memorize.c#L755).

### 4.7 Offensive magic, songs, and innate contests

These are the additional direct-stat consumers beyond common spell damage,
stat saves, MR, vamping and the mana/recovery formulas above.

| Ability family | Stat-dependent behavior | Source |
|---|---|---|
| Wither | Severity combines target saving modifier, actorPOW-targetPOW and level difference, then saves/wards and0..100 bounds determine its tier. Its descriptions of shrinking do not themselves change numeric size. | [Wither](../../../src/magic/magic.c#L2299) |
| Ray of enfeeblement | STR reduction is limited by target baseSTR/currentSTR as well as level, then written as an unscaled STR apply. High racial scaling changes the eventual loss. Separate damroll loss and save variants apply. | [Ray](../../../src/magic/magic.c#L8833) |
| Silence | Threshold includes actorWIS/2-targetWIS/4+levelDifference+2*save, bounded0..100. | [Silence](../../../src/magic/magic.c#L20191) |
| Feeblemind | Offensive/defensive WIS+level contest determines success/severity. Reduction uses `targetEffectiveStat/3+level/5+random(-15,5)` for INT/WIS, then applies an unscaled modifier: racial scaling can compound the loss. Recovery also has a separate feeblemind penalty. | [contest](../../../src/magic/magic.c#L20340), [loss](../../../src/magic/magic.c#L20263) |
| Power word stun | ActorPOW-targetPOW contributes0.75 times the difference to its score before other conditions. | [stun](../../../src/magic/magic.c#L20544) |
| Shatter / Shriek | Save modifier is `I(actorPOW)-15`; its old “92..100 has no bonus” comment disagrees with the index16 result (+1). | [Shatter](../../../src/magic/magic.c#L18358), [Shriek](../../../src/cmd/actoff.c#L13855) |
| Siren song | Supplies actorCHA-targetPOW as the `NewSaves` modifier on its lure path. Positive modifiers raise the save threshold and make the defender less likely to save, the opposite sign of a positive StatSave modifier. | [Siren](../../../src/magic/magic.c#L6557) |
| Chaos volley | Luck difference/10, bounded-2..2, changes the magical save modifier. | [volley](../../../src/magic/magic.c#L25961) |
| Blink | Attacker knocked off balance after the target blinks uses `max(20,50-attackerAGI/2)`, rolled versus 1..100. High AGI cannot remove the20 floor. | [Blink](../../../src/magic/magic.c#L26679) |
| Shaman WIS-result family | Result `clamp(0,A.WIS-int(D.WIS*0.5)+levelDifference+targetSave,120)+random(-10,10)`, with an animalist level roll. Used by molevision, mousestrength, shrewtameness and the earlier spirit spell path. | [shared result](../../../src/magic/smagic.c#L108), [uses](../../../src/magic/smagic.c#L2758) |
| Mousestrength / shrewtameness | Read both target baseSTR and effectiveSTR to cap a level-based unscaled STR reduction; stronger result tiers add other stat/roll changes. Mousestrength can also grant MAX DEX/AGI. | [mouse](../../../src/magic/smagic.c#L3147), [shrew](../../../src/magic/smagic.c#L3622) |
| Molevision | Uses current hitroll+STRhitTable in its blinding/hitroll consequence. | [molevision](../../../src/magic/smagic.c#L3002) |
| Earthen/greater earthen grasp | Duration adjustment uses `(A.STR-D.STR)/3` plus a random second, bounded +/-40 pulses; greater version also has a bounded STR-difference save modifier. | [grasp](../../../src/magic/smagic.c#L2058) |
| Awe | `clamp(5,casterPOW+casterLevel-targetINT-targetLevel,95)` is compared with 0..100; on its normal non-fighting path, higher POW raises domination success and higher target INT lowers it. | [Awe](../../../src/classes/psionics.c#L743) |
| Stunning visions | `int(0.8*(actorPOW-targetPOW))` adds to severity, plus level and target-save terms. | [visions](../../../src/classes/sillusionist.c#L819) |
| Delirium | Threshold includes actorPOW-targetINT+targetSave+levelDifference, bounded0..100 before other conditions. | [delirium](../../../src/classes/sillusionist.c#L2765) |
| Enrage | Initial duration/attack term uses effectivePOW difference plus random(-2,2) seconds, then its bounds and follow-up logic. | [enrage](../../../src/classes/psionics.c#L3765) |
| Excogitate | Reports mental-power tiers based on actorPOW-targetPOW, rather than altering either stat. | [probe](../../../src/classes/psionics.c#L4895) |
| Ogre roar | Target/actor POW difference/15 and WIS difference/15 plus level difference/10 modify resistance. | [roar](../../../src/classes/new_skills.c#L3503) |
| Bard general success | Independent AGI>0..125 and DEX>0..140 rolls multiply chance1.3 each; Luck>0..110 multiplies1.1. These stats can change song execution even when CHA is equal. | [song chance](../../../src/classes/bard.c#L431) |
| Song of healing | Singer amount includes CHA/8+songLevel/4+songLevel/14; allied healing uses its own share. | [healing](../../../src/classes/bard.c#L893) |
| Song of sleep | Against higher-level targets, CHA must meet a1..280 roll before the normal save and immunity checks. | [sleep](../../../src/classes/bard.c#L1245) |
| Song of dissonance | Singer/opponent score includes empowerment/3+level+CHA/2+Luck/5, with specialist and random contest terms. Also used against pets. | [dissonance](../../../src/classes/bard.c#L2327) |
| Lay Hands | Amount starts `floor(level/10)*CHA+random(1,100)`; Revenant and other route-specific adjustments still apply. | [Lay Hands](../../../src/classes/innates.c#L6100) |
| Insect/snake bite | Actor level+I(AGI) versus random up to target level+2*I(targetAGI) determines contact before poison/effect defenses. | [insect](../../../src/classes/innates.c#L1947), [snake](../../../src/classes/innates.c#L1990) |
| Parasite bite | Target AGI save modifier also includes actor AGI index/2 and levels. | [parasite](../../../src/classes/innates.c#L2077) |
| Branch | Chance scales by actorSTR/targetCON and max(actorDEX,40)/targetAGI plus levels, size and configured factor. High CON/AGI defend this independently of HP/AC. | [branch](../../../src/classes/innates.c#L5197) |
| Webwrap | Target AGI divides the level-based immobilization chance. | [wrap](../../../src/classes/innates.c#L5269) |
| Drider web spray | 70% of level*1.5 plus30% of the asymmetric AGI-contest term, bounded5..90; AGI changes admission, not periodic vitality drain. | [chance](../../../src/classes/innates.c#L5321), [drain](../../../src/classes/innates.c#L5365) |
| Tempest | Target Luck/10 participates in avoiding the extra effect. | [tempest](../../../src/classes/ethermancer.c#L2427) |
| Familiar bat effect | Target AGI participates in avoiding its lagging effect. | [familiar](../../../src/classes/epic_skills.c#L1048) |

### 4.8 Pets, summoning, recipes, and control

Owner stats have several independent effects:

- Specialized `conjure`: CHA versus 1..130 gates summoning; failed cooldown is
  inversely proportional to CHA. `2d(CHA/2)` chooses minion quality outcomes.
- Elemental paths use owner `CHA+level/5` in HP/control calculations. Ordinary
  home elemental summoning also uses CHA versus 0..400 for a guardian variant.
  Specialized elemental duration can multiply by ownerCHA/100 outside favorable
  terrain. Ethermancer elemental code has its parallel CHA helper.
- Beast admission counts existing matching pets against `max(1,CHA/30)` with an
  animalist level addition. The actual rejection is `existingCount > limit`,
  so the next summon can exceed the nominal limit by one. Treat it as a source
  boundary, not a guaranteed list of obtainable pets.
- Orders/control compare a random control score with owner's CHA clamped0..100.
  Mindflayer owners also subtract their POW from that score. Necromancer/theurgist
  matching pets and animalist animals have separate exemptions/adjustments.
- Learning a contained being's summoning recipe on a kill uses
  `clamp(1,ownerCHA,230)-targetLevel` against `number(1,targetINT)`, with legality
  and target exceptions. Solo and group-recipient paths both implement it.

Many pet lifetime expressions instead use **the summoned creature's INT**:
`400/I(petINT)`, `100/I(petINT)`, raised-undead variants with `6000/I(petINT)`,
and Bard charm's `1240/petINT`. They are not PC-owner racial INT benefits.
Owner stats also do not universally transfer to pet base attributes: creation
code explicitly initializes or floors pet stats. Illusion clones force current
CHA 1 for their special behavior rather than inheriting every displayed attribute.

Sources: [conjure gate/quality](../../../src/classes/drannak.c#L1124),
[elementals](../../../src/magic/magic.c#L2981),
[special duration](../../../src/magic/magic.c#L3890),
[ethermancer](../../../src/classes/ethermancer.c#L1446),
[beast count](../../../src/magic/smagic.c#L4340),
[control](../../../src/cmd/interp.c#L2187),
[recipe learning](../../../src/combat/fight.c#L3285),
[pet INT](../../../src/magic/magic.c#L3262),
[raised pet INT](../../../src/classes/necromancy.c#L1680),
[Bard charm](../../../src/classes/bard.c#L1158),
[illusion CHA](../../../src/classes/sillusionist.c#L1096).

### 4.9 Stealth, perception, movement, and survival

| Mechanic | Stat consequences | Source |
|---|---|---|
| Sneak / hide | AGI-index sneak/hide table bonuses; hiding additionally improves its roll10% on Luck/2 versus 0..100. Innate concealment, terrain, equipment and visibility still apply. | [sneak](../../../src/cmd/actoth.c#L2862), [hide](../../../src/cmd/actoth.c#L3010) |
| Steal | Actor DEX pickpocket table adds to chance; subtract `I(targetWIS)+I(targetINT)-19`. Target Luck can multiply chance0.85, actor Luck 1.05; cutpurse reach separately rolls actorDEX against75+I(targetDEX). | [steal](../../../src/cmd/actoth.c#L3809) |
| Awareness | Duration multiplies by integer `I(INT)/9`; awareness level uses `(I(INT)+I(DEX)+level/8)*rating/75`, then randomization. This produces plateaus, not continuous INT duration improvement. | [awareness](../../../src/classes/new_skills.c#L424) |
| Listen | Luck/2 can reduce the rolled difficulty10%. Other audible room propagation can use recipientWIS/5 and a WIS/10 floor, plus distance penalties and99 ceiling. | [listen](../../../src/cmd/actoth.c#L3353), [messages](../../../src/world/graph.c#L1682) |
| Look/scan concealment | `-(WIS-80)/2` changes the directional-scan baseline modifier. | [scan](../../../src/cmd/actinf.c#L9969) |
| Spell identification | Observer INT>1..100 can identify harmful casting in the spell display path; NPC retaliation notices through level+I(INT) versus 1..150. | [display](../../../src/net/sparser.c#L1083), [retaliation](../../../src/net/sparser.c#L2165) |
| Flee while stunned | WIS/10 adds to the stun-flee chance alongside level. | [flee](../../../src/cmd/actoff.c#L2899) |
| Wandering woods | INT changes the upper range of the “circles” roll: `100+(INT-100)/20`; failure below 61. Applies to ordinary movement and flee. | [move](../../../src/cmd/actmove.c#L2378), [flee](../../../src/cmd/actoff.c#L3075) |
| Unsteady standing | AGI+DEX raises the actor's random range against two sequential footing/balance rolls. | [stand](../../../src/cmd/actmove.c#L4046) |
| Water currents | STR/3 subtracts from current speed in the sweep/current resistance check. | [current](../../../src/cmd/actmove.c#L1425) |
| Underwater breath | Without the breathing exemption, an initial event is scheduled at 3*CON pulses; equipment/status and subsequent drowning logic still matter. | [breath](../../../src/mob/specials.c#L154) |
| Falling impact | Damage includes `maxHP*(speed/2.5)/100 + scaledImpactRoll - AGI`, minimum2 before safe-fall halving. Higher AGI reduces flat damage, while higher CON-derived maxHP can increase its percentage component. | [physics](../../../src/world/falling_policy.c#L71) |
| Falling injury | Opposes damage/maxHP-derived injury percent with a random range from I(CON)/2 to 3*I(CON). Knockout duration uses2..max(2,100-CON). | [injury](../../../src/world/falling.c#L78) |
| Wall of air | `(AGI+STR)/50` increases pass chance and lowers fall chance, alongside stored size. | [wall bonus](../../../src/classes/ethermancer.c#L4993) |
| Unbind | STR damage-table value+10 supplies brute-strength escape threshold. | [unbind](../../../src/classes/new_skills.c#L4008) |
| Quaff in combat | Threshold adds `(DEX+AGI/2-75)/4`, with Luck-triggered1.1 and Quick Thinking/combat-mind modifiers. | [quaff](../../../src/cmd/actoth.c#L4788) |
| Throw potion | AGI must meet1..140 for a steady throw; other skill targeting/error checks remain. | [throw potion](../../../src/cmd/actnew.c#L4363) |
| Slip | Threshold `clamp(5,slipRating+DEX/10,95)` for the quiet item-handling route. | [slip](../../../src/cmd/actobj.c#L198) |
| Examine | INT below a1..100 roll can misjudge craftsmanship by one grade; INT 100 removes that particular error. | [examine](../../../src/cmd/actinf.c#L3848) |
| Find/search | Average of INT+WIS+Luck versus 1..101 gates this item-search chance. | [search](../../../src/cmd/actobj.c#L7443) |
| Dig | Buried-item discovery compares1..100 to Luck/2+random 1..50. | [dig](../../../src/cmd/actoth.c#L6595) |

NPC AGI and DEX also determine how quickly aggressive NPCs react to entry;
NPC INT affects target selection, spell selection, noticing masters, assistance
and hunting behavior. These influence a PC's experience but are **not** advantages
of the PC's own racial AGI/DEX/INT. Calming can delay/prevent aggression, but the
source must be read with the actor/recipient correct.
[Entry reactions](../../../src/cmd/actmove.c#L1826),
[target selection](../../../src/mob/mobact.c#L251),
[command aggression](../../../src/cmd/interp.c#L3991).

### 4.10 Loot, crafting, and economy

- Random equipment/material drop chance starts with
  `(Luck/luckDivisor)*characterToMobLevelRatio + baseChance-100/luckDivisor`,
  then jitter, low-level/elite, hardcore, piece/equipment and difficulty modifiers.
  Owners receive the PC-pet kill credit through the drop dispatcher.
  Luck affects opportunity, not a universal guaranteed quality increase.
- Random recipe rewards add Luck/2 to the level/elite score versus 1..20000.
- Eligible NPC kills above level 30 can award a random epic when
  `number(1,5000)<Luck`; qualifying dragons have a separate guaranteed condition.
  Group recipients also perform the Luck check. This is distinct from ordinary
  kill XP and racial XP multipliers.
- Random equipment naming uses
  `8*(finderLevel/11)*((Luck-60)/4)*(sourceLevel+38)` against its named-item roll,
  plus zone/material/owner eligibility. Several integer plateaus apply. This
  changes naming selection; the material-quality helper uses levels and settings.
- Enhance uses three sequential `<Luck` rolls with configurable ranges for
  extreme/very/lucky outcomes, changing item-value gain and search attempts.
  Success still requires a valid candidate; Luck is not a guarantee of an item.
- Mining: Luck versus 1..3000 can produce a gem; Luck>random 80..140 gives the
  preserved-ore value bonus (1.3x). Higher Luck also avoids the low-end failures
  in related recovery paths.
- Salvage: low-value items can break unless Luck meets1..1000; recipe score is
  Luck+2*level+rating with item-value/tools adjustments. Rare essence uses several
  Luck-scaled rolls and a configured final chance. Each preserved-material bonus
  uses Luck>random 80..140, with separate tests for separate pieces.
- Forage: INT/15 adds to success, and a Luck/2 proc adds25 to chance; the giant
  secondary forage path also reads INT/15.
- Potion mixing: `(WIS+DEX)/2` must exceed1..160 for a bottle's potion result.
  Bottle/ingredient consumption and skill gates are separate.
- Ordinary shop CHA table benefits are neutralized by guards as explained above;
  Barter's separate CHA roll and other shop/race/condition restrictions remain.

Sources: [drop formula](../../../src/item/random_equipment_drop.c#L89),
[drop owner dispatch](../../../src/item/random_equipment_drop.c#L122),
[recipes](../../../src/classes/drannak.c#L867),
[epics](../../../src/combat/fight.c#L3258),
[naming](../../../src/item/random_equipment.c#L114),
[enhance](../../../src/item/enhance.c#L201),
[mining](../../../src/economy/mining.c#L473),
[salvage recipes](../../../src/item/salvage.c#L145),
[salvage essence](../../../src/item/salvage.c#L472),
[salvage value](../../../src/item/salvage.c#L525),
[forage](../../../src/cmd/actoth.c#L1720),
[mix](../../../src/classes/salchemist.c#L841).

### 4.11 Special procedures and environmental encounters

These are individual content/procedure consumers, not universal racial rules:

- Boulder pusher: targetDEX index improves boulder avoidance; NPC STR index
  adds damage and targetCON index shortens its knockout range.
- Banana peel: actorINT index improves avoiding the hazard; DEX index chooses
  the bad landing outcome.
- Huntsman ward: INT versus 0..120 lets the victim notice the triggering string.
- Holy weapon and Zion light/dark object effects: wielder Luck versus 0..500
  gates an extra mending/malison effect after their other proc conditions.
- Nexus guardian burst: targetAGI-50 bounded25..75 supplies avoidance versus 0..100.
- Necromantic flesh pet: targetAGI/6+15 helps avoid the blood effect.
- Conjured golem special: relative AGI and STR/15, levels and AC affect its attack.
- Mercenary intercept: a random 1..Luck roll contributes to interception.
- Barbarian weapon proc: the secondary restoration condition is
  `Luck < number(0,500)`, so **higher Luck reduces** this conditional proc chance,
  after the Barbarian-only lightning and1-in20 gates. Its comment implies a
  different direction; this warrants a focused behavior decision.
- Dragonnia NPC disarm: attacker DEX reaction and target `io_agi_defense`
  modify the disarm difficulty, independent of the ordinary disarm skill.
- Warhorse and Underworld sweeps also use AGI stat saves already described.

Sources: [boulder](../../../src/specs/specs.mobile.c#L5641),
[banana](../../../src/specs/specs.object.c#L5091),
[ward](../../../src/specs/specs.object.c#L11464),
[holy weapon](../../../src/specs/specs.object.c#L4703),
[Zion](../../../src/specs/specs.zion.c#L421),
[nexus](../../../src/economy/nexus_stones.c#L900),
[flesh pet](../../../src/specs/specs.mobile.c#L13197),
[golem](../../../src/specs/specs.mobile.c#L13395),
[intercept](../../../src/classes/drannak.c#L504),
[Barbarian proc](../../../src/specs/specs.underworld.c#L2935),
[NPC disarm](../../../src/specs/specs.dragonnia.c#L123).

Their presence in source establishes the conditional stat interaction; an
assignment/configuration and the particular item/NPC encounter are also needed
for it to occur. This audit does not claim every historical zone/proc is deployed
or obtainable. NPC-only STR damage and INT AI branches are kept distinct from
PC-owned stat benefits.

### 4.12 Stat-changing effects and feedback into the pipeline

A modifier computed from an effective stat is generally written back as an
**unscaled** apply. Recalculation then multiplies it by that attribute's selected
racial factor. This matters for both buffs and debuffs; a high factor can magnify
a penalty as well as a benefit. Cap interactions can mask a regular positive
apply completely on a capped character.

- Berserk computes MAX STR/CON/POW and regular INT/WIS penalties from **base**
  stats, with different berserker/quality formulas and random additions.
- Infuriate/titan computes MAX STR and CON plus regular AGI/DEX penalties from
  **base** stats; the titan variant has different fractions.
- Spell enlarge gives MAX STR=baseSTR/10 and MAX CON=baseCON/4, regular AGI and
  DEX penalties of-base/5. Spell reduce gives regular STR-base/4, CON-base/5,
  MAX AGI and DEX+base/5. Physical size/mass changes are separate. Innate enlarge
  does not grant this spell's stat package; see the documented source-collision
  concerns in [race-size-issues.md](race-size-issues.md).
- Elemental-form handlers likewise compute stat changes from base fractions,
  with a separate titan branch. A form's flavor text is not proof of copied
  racial attributes or size.
- Black Kush computes regular POW/INT/WIS increases from current effective
  attributes/10, level and its multiplier, plus regular STR/AGI decreases from
  current stats/10 and level. Gootwiet computes regular AGI/DEX increases using
  current stats divided by a random 9..13. These still pass through the ordinary
  unscaled cap and racial multiplier.
- Feeblemind's effective-stat-derived penalties are applied through regular
  INT/WIS modifiers. A “one-third” computed penalty need not mean a final
  one-third loss after racial scaling and other gear.
- Stat pools, epic/boon purchases, permanent-increase handlers and achievements
  alter **base** stats up to 100 in their respective paths. Reaching100 in the
  eight main base stats also triggers the full-stats achievement independently
  of current displayed attributes. The100-frag achievement raises baseCON2;
  the1000-frag achievement raises all ten base stats2, each bounded at 100.

Sources: [berserk](../../../src/cmd/actoth.c#L558),
[infuriate](../../../src/cmd/actoth.c#L920),
[enlarge](../../../src/magic/magic.c#L23080),
[reduce](../../../src/magic/magic.c#L23220),
[elemental form](../../../src/magic/magic.c#L17132),
[Black Kush](../../../src/core/smoke.c#L794),
[Gootwiet](../../../src/core/smoke.c#L921),
[feeblemind](../../../src/magic/magic.c#L20364),
[pools](../../../src/specs/specs.object.c#L7152),
[boon](../../../src/economy/boon.c#L1846),
[epic shops](../../../src/world/epic.c#L1374),
[permanent spells](../../../src/magic/magic.c#L27414),
[achievements](../../../src/world/achievements.c#L378).

## 5. Concrete racial differences and gear breakpoints

### Equal base100, no gear or temporary effects

The following figures use level 56 only for the **derived mana contribution**.
Human+5 and Halfling level 26+ Luck are included. STR hit/damage are table values,
not a promise of total hit chance or damage; capacity is the table's game-weight
limit, count is the ordinary PC inventory count. Crit is the initial melee
critical threshold before its confirmation. MR is the damage-reduction band
endpoint, not a spell-negation chance.

### Ordinary races

| Race | STR hit / damage | Carry / wield | Item count | INT crit | WIS MR | CHA calm | Derived mana (56) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Human | 3 / 13 | 535 / 36 | 11 | 9 | 0 | 15 | 808 |
| Barbarian | 5 / 21 | 895 / 48 | 11 | 8 | 0 | 8 | 362 |
| Drow Elf | 3 / 10 | 355 / 30 | 11 | 12 | 2 | 15 | 966 |
| Grey Elf | 3 / 10 | 355 / 30 | 11 | 11 | 5 | 17 | 885 |
| Mountain Dwarf | 4 / 17 | 715 / 42 | 11 | 8 | 7 | 11 | 562 |
| Duergar Dwarf | 4 / 17 | 715 / 42 | 11 | 8 | 7 | 7 | 531 |
| Halfling | 3 / 12 | 445 / 33 | 12 | 8 | 2 | 15 | 588 |
| Gnome | 2 / 9 | 285 / 27 | 12 | 14 | 0 | 13 | 999 |
| Ogre | 7 / 39 | 1435 / 68 | 10 | 8 | 0 | 5 | 311 |
| Troll | 5 / 21 | 895 / 48 | 11 | 8 | 0 | 7 | 388 |
| Orc | 4 / 15 | 625 / 39 | 11 | 8 | 0 | 12 | 661 |
| Thri-Kreen | 4 / 15 | 625 / 39 | 12 | 8 | 0 | 8 | 337 |
| Centaur | 4 / 19 | 805 / 45 | 11 | 8 | 0 | 12 | 384 |
| Githyanki | 3 / 12 | 445 / 33 | 11 | 12 | 0 | 8 | 1141 |
| Minotaur | 5 / 24 | 985 / 51 | 10 | 8 | 0 | 7 | 408 |
| Goblin | 3 / 12 | 445 / 33 | 12 | 10 | 0 | 12 | 686 |
| Githzerai | 3 / 12 | 445 / 33 | 11 | 11 | 0 | 12 | 1010 |
| Drider | 4 / 15 | 625 / 39 | 11 | 10 | 0 | 7 | 726 |
| Kobold | 3 / 10 | 355 / 30 | 11 | 13 | 0 | 14 | 870 |
| Firbolg | 7 / 39 | 1435 / 68 | 10 | 8 | 0 | 11 | 360 |
| Tiefling | 3 / 12 | 445 / 33 | 11 | 12 | 0 | 17 | 879 |

### Restricted/legacy races

| Race | STR hit / damage | Carry / wield | Item count | INT crit | WIS MR | CHA calm | Derived mana (56) |
|---|---:|---:|---:|---:|---:|---:|---:|
| Half-Elf | 3 / 13 | 535 / 36 | 11 | 11 | 0 | 16 | 1052 |
| Illithid | 1 / 6 | 175 / 19 | 11 | 18 | 0 | 2 | 2190 |
| Shade | 2 / 9 | 285 / 27 | 12 | 16 | 0 | 14 | 1229 |
| Revenant | 4 / 19 | 805 / 45 | 11 | 8 | 0 | 5 | 439 |
| Lich | 1 / 6 | 175 / 19 | 11 | 17 | 0 | 12 | 1589 |
| Vampire | 4 / 15 | 625 / 39 | 12 | 12 | 0 | 17 | 966 |
| Death Knight | 4 / 15 | 625 / 39 | 11 | 8 | 0 | 7 | 770 |
| Shadow Beast | 4 / 15 | 625 / 39 | 12 | 8 | 0 | 7 | 515 |
| Storm Giant | 5 / 21 | 895 / 48 | 10 | 8 | 0 | 7 | 471 |
| Wight | 4 / 17 | 715 / 42 | 10 | 8 | 0 | 5 | 442 |
| Phantom | 3 / 10 | 355 / 30 | 12 | 8 | 0 | 14 | 916 |
| Harpy | 2 / 9 | 285 / 27 | 12 | 12 | 0 | 14 | 879 |
| Orog | 5 / 21 | 895 / 48 | 12 | 8 | 0 | 5 | 151 |
| Planetbound Illithid | 2 / 9 | 285 / 27 | 11 | 12 | 0 | 14 | 1098 |
| Kuo Toa | 4 / 17 | 715 / 42 | 12 | 8 | 0 | 12 | 593 |
| Wood Elf | 4 / 17 | 715 / 42 | 12 | 8 | 0 | 12 | 593 |

These tables isolate stats; the same race/class combination may be illegal,
and the same derived mana term may have different practical value for a
memorizing class, racial PSP user or mana caster. Racial base mana, gear mana,
HP, vitality, combat/spell speed and damage multipliers are not included here.

Useful comparisons:

- Ogre/Firbolg STR 230 provides STR damage39 and capacity1435 versus a capped-base
  Human's STR 105 damage13 and capacity535. This is not the ratio of total weapon
  damage. Their natural STR also enters the highest shared spell-damage band,
  while their low INT limits initial melee criticals to 8.
- Gnome INT 130 gives initial melee critical14 versus Human105's9, as well as
  different mana and book-recovery behavior. Low natural STR does not get the
  shared spell-damage bonus until its threshold is reached through modifiers.
- Drow AGI 130 helps armor, stability and avoidance; its natural AGI does not
  receive the above-own-race AGI subtraction at base100. Human105 does get a5
  excess-AGI AC subtraction above its 100 baseline.
- Halfling Luck 120 below level 26 trails Goblin125; with Gambler's Luck it becomes
  130 and overtakes the Goblin's ungrown factor value. Other innate, class and
  build differences still matter. Luck is not a fixed percentage multiplier.
- Dwarf WIS 125 has MR 7 (random 1..7% reduction when applicable), not125% spell
  resistance. Drow115 has MR 2. The high-WIS bonus is modest here until MAX WIS
  reaches later bands, while its divine recovery and other checks also change.
- Natural large CON gives quadratic racial HP terms. Increasing effective CON
  on a low-CON race cannot recreate the larger race's native R-squared term.
  Conversely, changing the selected CON race can change more than the displayed
  attribute and needs a separate HP evaluation.

### MAX-stat investment needed from base100

Each cell is the **minimum additional unscaled MAX points**, with no other gear,
affects or factor override, to reach the named effective threshold. Human+5 is
included. Zero means the baseline already qualifies. This is arithmetic, not a
claim that all listed gear totals are obtainable or wise.

| Ordinary race | STR 121 (spell bonus) | DEX 125 (primary gate) | DEX 150 (secondary gate) | AGI 100 (no top-circle abort) | WIS 152 (MR 21) | CHA 161 (calm jump) |
|---|---:|---:|---:|---:|---:|---:|
| Human | 16 | 20 | 45 | 0 | 47 | 56 |
| Barbarian | 0 | 39 | 67 | 11 | 60 | 114 |
| Drow Elf | 34 | 14 | 36 | 0 | 32 | 46 |
| Grey Elf | 34 | 14 | 36 | 0 | 27 | 34 |
| Mountain Dwarf | 0 | 25 | 50 | 5 | 22 | 101 |
| Duergar Dwarf | 0 | 25 | 50 | 5 | 22 | 130 |
| Halfling | 27 | 0 | 15 | 0 | 32 | 46 |
| Gnome | 42 | 9 | 30 | 0 | 60 | 69 |
| Ogre | 0 | 66 | 100 | 33 | 90 | 221 |
| Troll | 0 | 39 | 67 | 11 | 60 | 130 |
| Orc | 1 | 25 | 50 | 5 | 69 | 89 |
| Thri-Kreen | 5 | 0 | 20 | 0 | 133 | 114 |
| Centaur | 0 | 39 | 67 | 11 | 38 | 79 |
| Githyanki | 21 | 25 | 50 | 0 | 52 | 114 |
| Minotaur | 0 | 56 | 87 | 25 | 79 | 130 |
| Goblin | 21 | 0 | 11 | 0 | 45 | 79 |
| Githzerai | 21 | 25 | 50 | 0 | 38 | 79 |
| Drider | 1 | 14 | 36 | 0 | 69 | 130 |
| Kobold | 34 | 14 | 36 | 0 | 45 | 61 |
| Firbolg | 0 | 66 | 100 | 33 | 90 | 101 |
| Tiefling | 21 | 14 | 36 | 0 | 52 | 34 |

At a smaller base roll, regular-stat items first fill the gap to the cap; MAX
modifiers increase current and cap together. STR/weapon weight still determines
whether the extra-attack gate pays out, and a save may already be capped.

## 6. Boundaries, misleading comments, and review priorities

This audit documents behavior; it does not silently rebalance races.

1. **Two save APIs have opposite modifier signs.** Positive StatSave modifiers
   help the defender. Positive `NewSaves` modifiers increase the save threshold
   (each modifier point is five threshold points), making the defender less
   likely to save. Several stat-difference spells deliberately use the second
   API. Do not standardize signs without tracing each call.
2. **StatSave's stated floor differs from its strict comparison.** Its maximum
   success is 19/21. Review the intended20/21 versus current19/21 before changing
   it; this affects every consumer, not a single race.
3. **The ordinary shop factor guards suppress the expected CHA table benefit.**
   Confirm intended pricing and cover buy/sell/value/list together; keep Barter
   outcomes distinct. Avoid promising a live discount from the table alone.
4. **Sanguinis ignis reads the other combatant's POW.** The mounted Dragoon's
   shaman skill is combined with current actorPOW, not DragoonPOW. Verify the
   intended subject and test asymmetric POW values before changing it.
5. **Shield-block's Luck/percent path needs review.** It touches a sometimes
   uninitialized temporary which the final success contest does not use; do not
   balance races as if it were an effective Luck-based shield-block bonus.
6. **MAX stats have thresholds and diminishing/negative returns.** DEX reaction
   caps at 9 from effective161, WIS parry bonus at 3 from 101, and the shared STR
   spell-damage band stops increasing at 181. Other consumers can keep improving.
   HP's `q(C)` peaks at CON 390 and falls afterward; increasing currentCON above 390
   while holding the other terms fixed reduces that HP component. AGI's isolated
   armor component turns near 275. Evaluate the full derived values and relevant
   encounters before changing caps or claiming “more always helps.”
7. **Natural racial baselines are reused after factor replacement.** Excess DEX
   hitroll, excess AGI armor and recovery still compare against native-race
   factors, while the effective attribute can use another race's factor.
   HP's CON-race scan differs again, including equipment-slot rules. Establish
   the intended authority before consolidating these paths.
8. **Effective-derived penalties can be rescaled.** Feeblemind and smoking
   examples show why an apparently fractional effective-stat loss/boost can have
   a second racial multiplier after being written as an apply. Regression cases
   should include low and high factors with caps, not only a Human.
9. **Some comments describe retired mechanics.** The old DEX attack ladder,
   old STR excess-damroll formula, INT-based critical comment, old reduced-range
   STAT_INDEX, class-minimum-based stat roller and alternate psionic memorization
   branch are commented out. The `wipe2011` INT notching adjustment is behind an
   undefined build flag in this checkout, not a current standard INT benefit.
   Likewise legacy height/weight comments about CON do not establish a live
   CON-based size/weight rule; see [race-size.md](race-size.md).
10. **Caps and truncation change marginal value.** Effective stats cap511 before
    the Halfling Luck addition, so the ordinary INT critical threshold tops out
    at 90, not the macro comment's hypothetical100+. Save caps can hide attribute
    gains; burden and weapon-weight integer boundaries can amplify a single point.

Sources: [NewSaves sign](../../../src/net/sparser.c#L1258),
[StatSave comparison](../../../src/core/utility.c#L3365),
[shop](../../../src/economy/shop.c#L1103),
[Sanguinis ignis](../../../src/combat/fight.c#L11152),
[shield block](../../../src/combat/fight.c#L9533),
[HP curve](../../../src/magic/affects.c#L449),
[AGI curve](../../../src/world/handler.c#L5320),
[override/excess](../../../src/magic/affects.c#L833),
[conditional notching](../../../src/guild/guild.c#L215),
[commented old roller](../../../src/cmd/actwiz.c#L5631).

For balance work, use three controlled comparisons: equal base rolls, equal MAX
gear budget, and equal final displayed attributes. Hold class/spec, level, size,
weapon weight, target defense, posture and relevant buffs constant. Compare the
whole outcome (damage plus hit/defense, control, resources and travel), then vary
those encounter conditions. Do not score races by average factors or assume that
a buff, physical size, racial resistance, combat speed, or XP factor is a stat.

## 7. Verification and coverage

Coverage was checked from source consumers outward and from the character
lifecycle inward. The comments-stripped stat-reference census contained 1,028
matching lines across 91 C/C++ source/header files, including declarations,
displays and persistence; those are search coverage counts, not1,028 distinct
gameplay mechanics. Direct accessors, direct struct reads/writes, factor tables,
lookup tables, shared derived macros and indirect stat-save callers were checked.
The catalog groups repeated calls while keeping distinct stat subjects, formulas
and conditional/dormant paths visible.

The review covers all 37 PC IDs and all 10 attributes, creation and permanent
improvement, regular/MAX/override aggregation, recomputation and persistence,
HP/mana/recovery, normal combat and active moves, magic and songs, pet ownership,
travel and hazards, visibility/handling, loot/crafting and special procedures.
Negative results are deliberate: no ordinary Karma outcome was found, old INT
learning-table comments do not establish a live benefit, vitality capacity and
normal HP regeneration do not have a generic direct CON term, and attributes do
not universally alter racial combat/cast pulse or physical size.

Verification performed:

- Extracted the production effective-stat block, active STAT_INDEX, stat tables,
  normal AGI-defense function, critical/MR/calming macros, HP function and mana
  function into an isolated C++ probe with explicit test fixtures and property
  values. AddressSanitizer/UndefinedBehaviorSanitizer passed 22,200 scenarios across
  all 37 races and all 10 attributes, plus factor replacement, index boundaries,
  all 511 valid index inputs, HP's post390 curve, equal-current-CON racial HP
  differences, Illithid versus Planetbound Illithid branches, worn-MAX-CON slot
  treatment and configured mana growth. These are actual extracted code paths,
  with fixture stubs for class/toughness/gear context, not a full running MUD.
- Compared all 370 racial factor values with the committed properties and race
  name mapping. Generated the derived tables from the executable probe. Checked
  source links and line-anchor bounds and documentation whitespace.
- Passed focused repository regressions: `test_character_stat_choice.py`,
  `test_monk_attack_weight.py`, `test_psp_move_regen.py`,
  `test_vampiric_overheal_regen.py`, `test_race_command.py` (both variants), and
  `test_falling_policy.py`. These verify their respective paths, not the entire
  gameplay catalog by themselves.

No live player session, deployed configuration, database journey, comprehensive
combat simulation or race win-rate study was performed. Conditional proc
availability and gameplay severity need encounter-specific verification. Review
findings distinguish visible source behavior from intended design; no runtime
fixes, production operations, commits or publication are implied by this audit.

To refresh the source census after changes, start with these independent searches
and follow the definitions and callers rather than treating matches as proof:

```sh
rg -n 'GET_C_(STR|DEX|AGI|CON|POW|INT|WIS|CHA|LUK|KAR)|base_stats|curr_stats' src
rg -n 'stat_factor|STAT_INDEX|str_app|dex_app|agi_app|wis_app|int_app|cha_app' src
rg -n 'StatSave|POW_DIFF|CRITRATE|CALMCHANCE|MAGICRES|MAGICDAMBONUS|VAMPPERCENT|CAN_CARRY_|TRUE_DAMROLL|io_agi_defense' src
```

Generated probe sources/results are local review artifacts under ignored
`bin/tests/race-stats-review/`; the durable conclusions, tables, conditions and
source references are contained in this file.
