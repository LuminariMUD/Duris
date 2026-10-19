# Class points

**Version 0.2 — a proposed design budget, calibrated to the ordinary class
roster.** Start with [Player classes (CLASSES.md)](CLASSES.md) for acquisition,
specializations, progression, and implementation links. This document supplies
the complementary question: what should a class's capabilities cost?

Use **100 class points (CP)** as the middle of the current roster, with **90–110
CP as an initial design review band**. Spend the budget on different strengths,
not on making every class equally good at every task. Price a change by its
effect on the complete playable build, not by counting its spells.

The premise is that the ordinary classes are roughly balanced across their
roles. That premise sets the scale; it does **not** establish their measured
performance or uniquely determine the prices below. The code establishes
availability and mechanics. The capability grades, relative prices, scenario
weights, and review thresholds here are explicit, editable design judgments.
The initial scorecards are estimates, not telemetry or a completed simulation.

## Quick use

1. Pick a legal class, race, specialization, level, equipment budget, and epic
   budget. Copy its nearest [reference scorecard](#initial-scorecards).
2. Describe the capability being added or changed, its implementation, and its
   limits. Compare the resulting kit with the [capability anchors](#capabilities-and-prices).
3. Adjust the affected grades and calculate `CP = 100 × raw / 84`. Keep the
   original grades, point delta, and [sensitivity bounds](#uncertainty-and-change-scores)
   alongside the proposal. A central estimate alone is insufficient.
4. Check the [interaction rules](#price-the-usable-kit) and each relevant
   [scenario](#comparison-conditions). A suitable total cannot excuse a
   guaranteed kill, permanent control, or a missing counter.
5. Test the changed behavior against a matched incumbent. Update the grade when
   evidence changes; update a shared price only when its valuation is wrong
   across classes. Do not automatically buff or nerf to meet a spreadsheet.

## Calibration roster and scope

Source snapshot: `1c3cc20e833109c2b102657e9d2b8605bedf4225`, reviewed on
2026-10-18. This is the documentation branch's code/configuration baseline,
not a claim about live population, deployed settings, or later `master`.

For this model, ordinary access means `CHAOS_MUD=FALSE`,
`CREATION_ALL_CLASSES=FALSE`, and `CREATION_ALL_RACES=FALSE`, with the committed
[creation policy](../../lib/creation_availability.cfg). Derive the roster by
intersecting enabled entries in `playable_races`, non-forbidden cells in
`class_table`, and enabled classes in
[constant.c](../../src/core/constant.c) and
[creation_availability_config.c](../../src/account/creation_availability_config.c).
Then check the actual creation and specialization routes. A class-name table
entry alone is insufficient.

This produces **21 classes**: Warrior, Ranger, Psionicist, Paladin,
Anti-Paladin, Cleric, Monk, Druid, Shaman, Sorcerer, Necromancer, Conjurer,
Rogue, Mercenary, Bard, Berserker, Reaver, Illusionist, Blighter, Ethermancer,
and Summoner. All 21 have a scorecard below; each contributes one observation
to the initial calibration, regardless of player population or spec count.

Exclude these from the calibration:

- **Dragoon:** disabled by the committed creation policy.
- **Standalone Assassin, Thief, Warlock, MindFlayer, Alchemist, Dreadlord,
  Avenger, and Theurgist:** no legal cell among the normal 21 races. Rogue's
  Assassin and Thief specializations remain ordinary paths.
- **Rogue Shadow Archer and the unused slot:** no ordinary allowed race path
  for the former; a placeholder for the latter.
- Chaos/staff equipment, restricted creation races, disabled ascent/descent,
  and presumed rewards from unreachable bodies. Existing exceptional characters
  or acquired temporary forms need their own explicit comparison profile.

The exact race/alignment matrix and Telnet/WebSocket differences are in
[Creation and alignment](CLASSES.md#creation-and-alignment). The example races
below establish legal matrix/spec intersections, not completed client journeys
or a recommendation that those races are optimal. In particular, neutral-only
creation choices require the documented alignment handling to be respected.

## What a point means

A CP is a **relative design price**, not a percentage of damage, win rate,
survivability, or player value. A 110 CP class is not proven 10% stronger than
a 100 CP class. Nor does an ability costing 5 CP imply changing its damage by 5%.

For a build, assign seven grades in the order `D, B, T, H, C, S, U`:

```text
raw = 6D + 4B + 5T + 5H + 4C + 4S + 2U
CP  = 100 × raw / M

M = 84 for versions 0.1 and 0.2
delta CP = (100 / 84) × (6 delta D + 4 delta B + 5 delta T
                         + 5 delta H + 4 delta C + 4 delta S + 2 delta U)
```

`M` is the original version 0.1 median raw score of the 21 initial scorecards,
not a separate normalizer for each class. Freeze it while evaluating a change
or a new class; otherwise adding power to the roster can silently move the
goalposts. Only an explicit model revision recalibrates it. Corrected grades
can change the current roster's median without changing `M`. Calculate with
full precision and round
only the displayed total and delta to one decimal place; subtracting rounded
totals can give a different delta.

The grade scale is shared across classes:

| Grade | Meaning relative to the current ordinary roster |
| --- | --- |
| 0 | No material class capability in this domain beyond common character actions. |
| 1 | Incidental benefit or a narrow emergency option. |
| 2 | Useful secondary capability; cannot reliably fill that role alone. |
| 3 | Credible contributor to the role, with meaningful gaps versus specialists. |
| 4 | Strong primary capability, approaching the specialist reference. |
| 5 | Frozen specialist reference quality under the declared conditions. |

Use half-grades for intermediate designs; finer precision requires measured
evidence. Five is an anchor, **not a clamp**: a new capability beyond the
incumbent ceiling must be scored above five and reviewed explicitly. Otherwise
unlimited power would become free once a column reached five. A grade of zero
does not mean the character cannot attack, flee, or use a common consumable.

### Uncertainty and change scores

For initial estimates, mark each judgment-based grade as uncertain by **±1 grade**
(floor at zero, no ceiling at five). With positive shared weights `w`, calculate:

```text
low_i  = max(0, grade_i - 1)
high_i = grade_i + 1
CP_low  = 100 × sum(w_i × low_i) / 84
CP_high = 100 × sum(w_i × high_i) / 84
```

An audited absence can use `low_i = grade_i = high_i = 0` when its capability
ledger establishes that absence for the selected build and conditions. The
initial table has no per-axis absence audits, so **all seven grades, including
zeros, use the default range**. A zero estimate is not proof of absence, and a
capability that has not been assessed must be marked unknown rather than zero.

These are conservative sensitivity bounds, not a statistical confidence
interval or a claim that every extreme is simultaneously playable. Shared
actions and resources can correlate the grades. Preserve those constraints in
the scenario tests; do not treat the upper vector as a legal action schedule.
Do not interpret one-decimal arithmetic as one-decimal knowledge. Measurements
must retain both trial variation and uncertainty in the mapping to grades;
precise damage measurements alone do not establish a precise design price.

For a change, score the **paired difference** under the same fixtures, anchors,
and prices. Unchanged axes cancel. Give each affected grade delta its own
evidence-based bounds, then apply the delta formula to those bounds. Do not
subtract two independently pessimistic/optimistic whole-kit ranges: that would
charge uncertainty twice for unchanged capabilities. If paired evidence is
missing, retain the conservative difference range and say it is unresolved.

For example, if Mercenary's C increase is estimated as `0 to 1` with midpoint
`0.5` and every other axis is unchanged, its delta is **0.0–4.8 CP**, midpoint
**+2.4 CP**. This does not establish that the interrupt improves the kit; it
identifies the uncertain claim to test. When an absolute range crosses a
review threshold, report the budget classification as unresolved. The range
does not override a demonstrated control, dominance, or counterplay failure.

## Capabilities and prices

Prices are deliberately few and shared. Sustained offense gets six raw units
per grade, durability and recovery five, burst/control/support four, and utility
two. This is the starting valuation of combat contribution versus access and
convenience, not a set of coefficients extracted from C++.

| Axis | Raw units / grade; CP / grade | Count here | Current comparison anchors |
| --- | --- | --- | --- |
| **D — sustained offense** | 6; 7.14 CP | Repeatable damage delivered over the sustained window, including the owner's active pets, ordinary attacks, spells, and damage over time. Account for misses, saves, resource exhaustion, and downtime. | Berserker/Mauler and Monk/Red Dragon; Ranger/Blademaster and pet casters provide other delivery models. |
| **B — burst and finishing** | 4; 4.76 CP | Damage concentrated into the opening/finishing window **above** what the same build's sustained rate would deliver in that window. Count access to the opener and recovery before its next use. | Rogue/Assassin, Sorcerer/Wizard, Berserker/Mauler. |
| **T — personal durability** | 5; 5.95 CP | HP, avoidance, mitigation, wards, and personal defensive uptime. Test physical and magical threats. Exclude restored HP already in H and escapes already in U. | Warrior/Guardian with shield; compare Healer wards, Monk defenses, and Earth Magus defenses separately. |
| **H — restoration** | 5; 5.95 CP | Effective HP restored to self, allies, or owned pets and recovery from harmful conditions. Exclude overheal; keep self-only, pet-only, and group reach visible. | Cleric/Healer at the specialist end; Shaman/Spiritualist, Druid, Paladin, and Bard offer different coverage. |
| **C — control and disruption** | 4; 4.76 CP | Enemy actions/position/options denied by lag, disabling effects, debuffs, dispels, and room barriers. Include resistance, immunity, break conditions, diminishing returns if implemented, and counterplay. | Illusionist/Magician; compare Psionicist, Ethermancer, and physical interrupts against the same target set. |
| **S — ally support and protection** | 4; 4.76 CP | Marginal benefit delivered to **other** characters by buffs, auras, guarding/rescue, and protection. Exclude direct healing in H and effects already supplied by the fixed comparison party. | Bard/Minstrel, Paladin auras, Conjurer protections, Guardian guard/rescue. |
| **U — mobility, information, and access** | 2; 2.38 CP | Scouting, stealth, tracking, travel, escape, access tools, and post-death recovery access. Value successful tasks and time saved, not the number of utility spells. | Rogue/Assassin for covert access; Druid and Illusionist for travel and escape. |

These anchors identify comparison kits, not verified DPS leaders. For example,
the source grants Mauler rage/attack tools and Monk unarmed techniques; only a
matched run establishes which delivers more damage in a particular matchup.
Within U, a travel specialist need not also be the best infiltrator.

### Turn abilities into grades

Maintain a short ledger for the build: `capability -> grant -> consumer ->
unlock -> conditions/cost -> axis -> evidence -> grade effect`. Follow the
registration into its handler/passive consumer; record removals as well as
additions. Then grade the **combined usable capability**, not each row of the
ledger independently. Ten interchangeable attacks do not buy ten D grades.

For a new ability, compare the build with and without it. If it raises C from
2 to 3, its control price is 4.76 CP. If it merely replaces an equally effective
attack, D may not move at all. An earlier unlock or a different counter can
still change another level or scenario. Shared prerequisites, extra spell names,
and multiple damage types earn value only when they improve an actual outcome
or meaningful choice.

When measurements become available, freeze the fixtures and named anchor
outputs for that model version. Record the measured output, units, anchor
outputs and interpolation rule alongside each resulting grade. Interpolate
between measured adjacent grades within the same axis and scenario; do not
assume that every ordinal grade is an equal percentage of damage or HP. If
evidence contradicts an initial grade, revise the grade before inventing a
class-specific discount.

Do not move the grade-5 anchor to each new strongest build: that would erase
increases in power even with `M` frozen. Until measured anchors exist, label the
grade as a design estimate even when some underlying measurements are available.

## Initial scorecards

These are **version 0.1 design estimates from the available kits**, at level
56, one named specialization, no secondary class, and no purchased epic skills.
They include ordinary learned grants up to their legal caps and supported spell
circles. They do not pool the strengths of mutually exclusive specializations.
The conditions below define how to replace the estimates with comparable data.

| Class / specialization | D | B | T | H | C | S | U | Raw | CP | CP low | CP high |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Warrior / Guardian | 4 | 2 | 5 | 0 | 3 | 3 | 1 | 83 | 98.8 | 69.0 | 134.5 |
| Ranger / Blademaster | 4 | 3 | 3 | 1 | 2 | 2 | 4 | 80 | 95.2 | 59.5 | 131.0 |
| Psionicist / Pyrokinetic | 4 | 4 | 2 | 1 | 4 | 2 | 3 | 85 | 101.2 | 65.5 | 136.9 |
| Paladin / Crusader | 3 | 3 | 4 | 3 | 2 | 4 | 2 | 93 | 110.7 | 75.0 | 146.4 |
| Anti-Paladin / Dark Knight | 4 | 4 | 3 | 2 | 3 | 3 | 2 | 93 | 110.7 | 75.0 | 146.4 |
| Cleric / Healer | 1 | 0 | 4 | 5 | 2 | 4 | 3 | 81 | 96.4 | 65.5 | 132.1 |
| Monk / Red Dragon | 5 | 3 | 4 | 1 | 3 | 0 | 2 | 83 | 98.8 | 67.9 | 134.5 |
| Druid / Forest Druid | 3 | 2 | 2 | 3 | 4 | 3 | 5 | 89 | 106.0 | 70.2 | 141.7 |
| Shaman / Spiritualist | 3 | 2 | 2 | 4 | 3 | 3 | 3 | 86 | 102.4 | 66.7 | 138.1 |
| Sorcerer / Wizard | 4 | 5 | 2 | 0 | 4 | 2 | 3 | 84 | 100.0 | 70.2 | 135.7 |
| Necromancer / Necrolyte | 4 | 3 | 2 | 2 | 4 | 2 | 3 | 86 | 102.4 | 66.7 | 138.1 |
| Conjurer / Earth Magus | 3 | 3 | 3 | 0 | 4 | 4 | 4 | 85 | 101.2 | 71.4 | 136.9 |
| Rogue / Assassin | 4 | 5 | 2 | 0 | 3 | 0 | 5 | 76 | 90.5 | 65.5 | 126.2 |
| Mercenary / Brigand | 4 | 4 | 3 | 0 | 4 | 1 | 4 | 83 | 98.8 | 69.0 | 134.5 |
| Bard / Minstrel | 2 | 2 | 2 | 3 | 4 | 5 | 4 | 89 | 106.0 | 70.2 | 141.7 |
| Berserker / Mauler | 5 | 5 | 3 | 0 | 3 | 1 | 1 | 83 | 98.8 | 69.0 | 134.5 |
| Reaver / Flame Reaver | 4 | 4 | 3 | 0 | 3 | 2 | 2 | 79 | 94.0 | 64.3 | 129.8 |
| Illusionist / Magician | 3 | 3 | 2 | 0 | 5 | 4 | 5 | 86 | 102.4 | 72.6 | 138.1 |
| Blighter / Scourge | 3 | 3 | 2 | 2 | 4 | 2 | 4 | 82 | 97.6 | 61.9 | 133.3 |
| Ethermancer / Frost Magus | 4 | 4 | 3 | 1 | 4 | 2 | 4 | 92 | 109.5 | 73.8 | 145.2 |
| Summoner / Controller | 4 | 3 | 2 | 0 | 4 | 3 | 4 | 82 | 97.6 | 67.9 | 133.3 |

The raw median is **84**, range **76–93**, producing **90.5–110.7 CP**.
Paladin and Anti-Paladin slightly exceed the initial review band. Under the
rough-balance premise, that is first a reason to examine estimated aura,
healing, offense, and action overlap, not evidence for a nerf. Rogue's low end
similarly calls for checking the price of stealth and opener access before
adding damage. No per-class fudge factor has forced the totals to 100.

**Every initial sensitivity range crosses both 90 and 110.** None of these
rows therefore establishes a class as over, under, or within budget with the
stated uncertainty. Keep the central estimates for designing comparisons, not
for ranking live classes or ordering numerical changes.

### Comparisons the current estimates flag

A vector dominates another estimate when it is at least as high on every axis
and strictly higher on at least one. This check is independent of the particular
positive prices. The current table flags these five pairs:

| Higher estimated vector | Lower estimated vector | Strictly higher axes |
| --- | --- | --- |
| Anti-Paladin / Dark Knight | Reaver / Flame Reaver | H, S |
| Ethermancer / Frost Magus | Ranger / Blademaster | B, C |
| Ethermancer / Frost Magus | Psionicist / Pyrokinetic | T, U |
| Ethermancer / Frost Magus | Mercenary / Brigand | H, S |
| Ethermancer / Frost Magus | Reaver / Flame Reaver | H, C, U |

These are priorities for matched comparisons, **not demonstrated gameplay
dominance**. Their sensitivity ranges overlap, and the seven grades hide
delivery methods, counters and subroles. Preserve those distinctions in the
ledger and compare feasible schedules before deciding whether the grades,
grouped axes, or mechanics need correction. Merely changing positive weights
cannot reverse a dominance relationship between these unchanged vectors.

### Source basis for the reference builds

The following are the concrete distinctions behind the estimates. All ordinary
grant examples are in [skills.c](../../src/classes/skills.c); innate grants and
their unlocks are in [innates.c](../../src/classes/innates.c). Legal spec rows
are in [specializations.c](../../src/classes/specializations.c). Class/spec help
links are indexed in the [class catalogue](CLASSES.md#class-catalogue).

`HP input` is the committed `hitpoints.class.<ClassName>` property in
[duris.properties](../../lib/duris.properties). It is an input to
`calculate_hitpoints2` in [affects.c](../../src/magic/affects.c), **not a final HP
multiplier and not the T grade**. This is why Monk defenses or Healer wards can
matter despite a lower HP input.

| Reference build | Example legal race | HP input | Source-backed capability basis and limiting distinction |
| --- | --- | ---: | --- |
| Warrior / Guardian | Human | 1.20 | Weapon attacks, shield block, guard/rescue, Bulwark at 41; Guardian removes dual wield. High personal protection and ally rescue, no spell healing. |
| Ranger / Blademaster | Human | 0.90 | Dual-wielding master, track/outdoor sneak, blade barrage, whirlwind, and nature utility; spec parry/riposte modifiers are outside the grant table. |
| Psionicist / Pyrokinetic | Githzerai | 0.55 | Mental offense and defenses, cell adjustment/lend health, wormhole; Pyrokinetic adds flame tools. Mana use differs from memorized spell slots. |
| Paladin / Crusader | Human | 1.00 | Weapon combat, lay hands, heal/group heal, auras; smite evil and Holy Sacrifice. Alignment and PvP/PvE conditions constrain the combined benefit. |
| Anti-Paladin / Dark Knight | Orc | 1.00 | Weapon combat, vampiric touch/life drain, fear and auras; Blood Tithe and Hellfire. Recovery is not interchangeable with Healer's group restoration. |
| Cleric / Healer | Human | 0.80 | Full/group healing, cleansing, warding faith and resurrection; the spec removes multiple offensive spells and kick. Healing can also refill the caster's ward. |
| Monk / Red Dragon | Human | 0.70 | Martial arts, combination attack, fist of dragon, regenerate, diamond soul, evasion; equipment/body and attack conditions matter. |
| Druid / Forest Druid | Human | 0.70 | Nature's Touch, regeneration, charm/shapechange, plane shift/moonwell; forest spells add control and summons. Terrain and form requirements limit breadth. |
| Shaman / Spiritualist | Human | 0.70 | Mending/wellness, spirit damage, attribute buffs and wards; improved healing and resurrection tools trade specialization space with other paths. |
| Sorcerer / Wizard | Human | 0.60 | Direct/area damage, disabling spells, haste and travel; spellweave, arcane block/riposte. Wizard removes Solbeep's Missile Barrage. |
| Necromancer / Necrolyte | Orc | 0.50 | Animate/raise/create undead, heal undead, life leech, debuffs, spawn/unholy alliance. Pet acquisition and replacement are real costs; disabled corpseform earns no value. |
| Conjurer / Earth Magus | Human | 0.50 | Elementals, barriers, haste/group protections and travel; living stone and earth spells. Pet and self-defense conditions matter more than the low HP input alone. |
| Rogue / Assassin | Human | 0.80 | Backstab/circle, stealth, tracking, locks and disguise; two-dagger innate. An opener requires access and must not be treated as repeatable every action. |
| Mercenary / Brigand | Human | 0.90 | Broad weapons, backstab, headbutt/tackle, rescue, track; ambush, crippling strike and disruptive blow. No spellbook or spell-healing package. |
| Bard / Minstrel | Human | 0.85 | Base songs, instruments, spells and limited melee; riff, blindsinging and Song of Drifting. Song/instrument/action restrictions prevent full simultaneous output from every song. |
| Berserker / Mauler | Human | 0.85 | Rage, maul, rampage, rush and attack progression; boiling blood and mangle. Offensive uptime and constraints matter; no spellcasting. |
| Reaver / Flame Reaver | Orc | 0.90 | Dual wield/attack progression with arcane buffs/debuffs; fire spells and pyrokinesis. Casting competes with martial actions; resistance changes the fire package's value. |
| Illusionist / Magician | Human | 0.50 | Disabling illusions, shadow creatures, reflection, invisibility and travel; deceptive flee and suppress sound. Strong options do not all coexist in a single action. |
| Blighter / Scourge | Orc | 0.70 | Destructive nature spells, drain nature/life leech, forms and plane shift; entangle, mist, spores and shambler. Recovery/terrain constraints differ from Druid's. |
| Ethermancer / Frost Magus | Human | 0.80 | Ice/wind damage, dispel/purge, flight, Purify Spirit cleansing and tupor resource path; iceflow armor and ice/wind spells. Cleansing earns H value despite lacking a general healing package. |
| Summoner / Controller | Human | 0.50 | Contain Being, haste, barriers, group protection and planar travel. Bound-creature availability, control limits and pet loss constrain the kit. |

These facts justify the *shape* of each scorecard. They do not numerically
prove its seven grades. For example, `SPELL_ADD` establishes a spell's circle,
not its successful casts per minute. [CLASSES.md's implementation map](CLASSES.md#implementation-map)
locates the relevant consumers, including shared magic and combat files.

Three useful cross-checks outside the grant lists are `heal` and the damage
branches in [fight.c](../../src/combat/fight.c), `spell_purify_spirit` in
[smagic.c](../../src/magic/smagic.c), and Summoner's `do_conjure` /
`valid_conjure` in [drannak.c](../../src/classes/drannak.c). Contain Being marks
an eligible NPC; the death path can teach a recipe, and conjuring checks the
creature's eligibility. The spell alone is not an unlimited pet grant or a
player-control effect.

## Comparison conditions

Use a written fixture shared by the candidate and incumbents. Version 0.1's
primary design profile is **level 56, ordinary mode, one legal spec, zero
purchased epic skills**, with normal training complete. Level 56 is a modeling
endpoint; the [frag cap](../../lib/frag_cap.cfg) and live unlock state determine
whether current players can reach it.

For the class-only comparison, hold final ordinary attributes, age, racial
stat factors, equipment value, consumables and external buffs constant where
possible. Keep class equipment restrictions and body requirements. Such a
normalized fixture is an analytical comparison, not a newly legal character.
Then test actual legal race/gear builds, especially the strongest plausible
combination. Race restrictions are not a negative CP coupon: a rare legal
combination can still dominate. Report class-only and complete-character
results separately.

Declare a weapon/armor/loadout manifest for each role under the same acquisition
budget; identical item VNUMs need not be wearable by both classes. Record pets,
instruments, spellbooks, consumable charges, room/terrain, alignment, resistances,
immunities, group composition and opponent behavior. No assumed limitless
corpses, pets, mana, tupor, prepared spells, or recovery time.

Use these initial scenario weights when measured scorecards replace the priors:

| Scenario | Weight | What must be represented |
| --- | ---: | --- |
| Solo PvE | 20% | Single durable target and a pack, physical and magical threats, sustained damage and recovery between pulls. |
| Group PvE | 30% | Fixed six-PC party with one slot replaced; measure clear progress, deaths, effective healing, damage prevented and downtime. |
| Small-party PvP | 20% | Fixed three-versus-three compositions, both starting initiative orders, target switching, escape, dispel and control counters. |
| Group PvP | 20% | Fixed six-versus-six compositions, physical/caster mixtures and opponents with realistic saves/counters; count effective recipients. |
| Travel, scouting and recovery | 10% | Fixed tasks for tracking/detection, stealth/access, group movement, escape and post-death return; include failures and time spent. |

Party sizes and weights are modeling choices, not engine group-size limits.
For each scenario, grade the seven axes under a **feasible action/resource
schedule**, then use the same prices and frozen `M` to calculate its CP.
Record each axis as measured, estimated, verified absent, deliberately irrelevant
to that fixture, or unknown. An irrelevant contribution, such as ally support in
a solo fixture, is zero for that scenario, not proof the class lacks it.
Apply the same relevance rules to every compared build. A missing measurement
does not become zero or inherit a score from a different scenario.

The complete summary is `sum(scenario weight × scenario CP)`, using fractions
that sum to one. If a scenario or relevant axis is unknown, report partial
coverage and withhold the complete summary; do not silently redistribute its
weight among completed tests. A summary containing judgment-based grades must
remain labeled an estimate. Preserve every scenario's vector and total; never
conceal a PvP failure inside a PvE average.

The 90–110 band was calibrated to the initial whole-kit estimates, **not to
these unrun scenarios**. Co-score the candidate and incumbents under the same
protocol and compare their paired scenario deltas. Do not directly classify a
measured scenario summary against the initial band or mix it with unmeasured
reference rows. A band for that measured profile needs an explicit calibration
revision with the old and new results preserved; retain `M=84` in the meantime.

Start with an **8-second burst window**, a **60-second sustained encounter**,
and a **five-minute repeated-encounter sequence including setup and recovery**.
These are test conventions, not ability cooldowns. Model a prepared opening and
a depleted/recovery case. Record actual elapsed time and pulses; property names
such as `rechargeTime` do not guarantee seconds. Run single-target and
three-target cases separately; an area effect does not hit an unlimited number
of useful targets.

### Separate sustained and burst damage

Use one damage trace and declare the burst window before observing the result.
For an encounter lasting `t` seconds with a burst window of `b` seconds, let
`Q` be total effective damage and `Qb` the damage inside that window. Require
`0 <= Qb <= Q` and a nonempty sustained remainder (`0 < b < t`), then use this
accounting convention:

```text
r = (Q - Qb) / (t - b)
burst_excess = max(0, Qb - r × b)
sustained_damage = Q - burst_excess
```

Use `sustained_damage / t` as the D input and `burst_excess` within the declared
window as the B input, each mapped through its own matched anchors. Their
damage amounts sum to `Q`; no damage is allocated twice. Retain the full trace
and total DPS as outcome evidence. This is an accounting convention, not a
claim that a distinct burst ability caused every point of excess damage.

For example, `t=60`, `b=8`, `Q=6800`, and `Qb=1600` give `r=100`,
`burst_excess=800`, and `sustained_damage=6000`: D uses **100 damage/second**,
and B uses **800 excess damage**. Using the full 113.3 DPS for D as well would
count the same 800 damage again. Constant output has zero burst excess; a weak
opening never earns negative B credit.

For repeated encounters, partition each encounter the same way and include
setup/recovery in the sequence's elapsed time. Use the same window protocol
for incumbents and candidates. An early kill before the sustained remainder
is measurable is a valid outcome, but not a complete D/B measurement; preserve
it and run the durable-target fixture too.

### Progression and alternate builds

Also rescore at **25, 30, 41, 46, and 51**. They expose early play, spec entry,
major innate/skill unlocks, and later progression. Calculate available circles
with the actual `get_max_circle` rule and discard not-yet-usable grants.
Compare with incumbents at the *same* level; do not multiply a level-56 budget
by `level / 56`, or demand 100 CP from unspecialized level-25 characters.

Epic skills are a second profile with the **same explicit earned/spent budget**
and valid prerequisites for all builds. Pick that budget from the season being
balanced; do not give every epic reward for free or assume a universal +20 CP.
Likewise, rate each other legal specialization separately. A class's mean, low,
and high scores can summarize those builds only after scoring them; do not
copy this document's one example spec to every spec.

## Price the usable kit

- **Respect removals and reachability.** A spec can replace or remove a base
  grant. Circle zero exclusions, unsupported circle-100 entries, disabled
  handlers, commented registrations, staff-only routes, and grants above the
  selected level buy no usable capability. `MAX_CIRCLE` is 12 in this snapshot.
  Code grants still require learning, equipment, preparation, and acquisition.
- **Charge for consequences once.** Personal damage belongs in D/B; added
  damage to other party members belongs in S. Direct restored HP belongs in H;
  prevention/absorption belongs in T for self and S for allies. Do not also
  award a generic buff, pet, versatility, or synergy bonus for the same result.
  Cleansing goes in H; removing enemy buffs goes in C; post-death return goes
  in U. Retain submetrics so these different effects stay visible.
  Enemy actions denied by control belong in C; do not also price their
  hypothetical prevented damage in T/S. A debuff whose only result is extra
  damage earns D/B or S through that damage, not another generic C bonus.
- **Do not add incompatible maxima.** Casting, attacking, healing, singing,
  equipping an instrument/shield, using a mount, and switching targets have
  opportunity costs. Use the real action schedule and permitted equipment.
  A kit may offer several choices, but its grades must reflect time spent
  choosing among them. Removing a shared-action constraint increases usable
  output and therefore can cost points even if no damage number changes.
- **Include pets through their output.** Add damage in D/B, control in C, and
  protection in T/S as appropriate. Include owner actions, command limits,
  acquisition, deaths, replacement, immunities, and master/pet identity checks.
  Do not add a flat price per pet on top of all its measured benefits.
- **Use marginal group value.** Compare the fixed party with and without the
  candidate's contribution. An already-present nonstacking buff adds no second
  full benefit; persistent simultaneous effects can add real value. Test the
  first and second copy of a support class. Avoid six recipients in the cost
  sheet when only two receive useful healing or protection.
- **Treat drawbacks as effective limits, not coupons.** Cooldown, lag, save
  chance, range, terrain, weapon requirements, self-damage, resource costs and
  uptime reduce the affected capability under the scenario. If those costs
  already reduced a grade, do not subtract them again. A drawback bypassed by
  ordinary gear or another ability warrants little or no discount. Flavor,
  rarity, race restrictions and inconvenient leveling do not pay for an
  uncounterable endgame ability.
- **Expose interactions.** Healing that refills a ward has both distinct
  restored-HP and absorbed-damage consequences; measure both without calling
  the same absorbed damage healing. Control that guarantees an opener, pets
  acting while their master casts, and mitigation that prolongs lifesteal need
  paired tests. Score the combined kit; do not assume standalone prices add
  linearly or hide the interaction in an unexplained surcharge.

### Specializations and multiclassing

A specialization is a **replacement build**, not an automatic extra point
allowance. Start with the base class at the same level, apply additions,
removals, cap/circle changes and passive combat modifiers, then rescore. It
may legitimately improve on remaining unspecialized; compare the final spec
against other specialized builds at the same level and evidence profile. The
90–110 band applies to the original level-56 design profile, not every level
or individual scenario.

Multiclassing is also one build, not the sum of two class scores. Only use
ordinary ordered pairs and eligible Human/Orc combinations from
[Multiclassing](CLASSES.md#multiclassing). Apply the restart, loss of spec,
primary/secondary identity rules, secondary-only skill delay/cap, extra spell
circle, and preparation/cost rules before rating the result. In this snapshot,
secondary-only ordinary skills use +5 levels and a 95% cap multiplier;
secondary-only spells use +1 circle within the supported limit. HP chooses
the larger class input rather than adding both. The initial 21-row calibration
does not claim these ordered pairs have already been measured or balanced.

## Worked decisions

### Small change: an additional control option

Mercenary/Brigand starts at raw 83, or 98.8 CP. Suppose a proposed interrupt
raises its net C grade from 4 to 4.5 after lag, saves and competing headbutt/
tackle actions are accounted for. New raw is `83 + 4 × 0.5 = 85`, or **101.2
CP**, a **+2.4 CP** change. If it only replaces an equally effective interrupt,
C stays at 4 and the price is zero. If it closes every escape window, the
control/counterplay check fails even though 101.2 is inside the band.

### Existing passive: Guardian's Bulwark

[fight.c](../../src/combat/fight.c) applies the configured `0.850` damage factor
when the target has the innate and wears a shield;
[innates.c](../../src/classes/innates.c) grants it at 41. Where that damage
branch applies, the isolated factor corresponds to `1 / 0.85 = 1.1765` times
the incoming pre-mitigation damage needed to exhaust the same HP, before other
interactions. That is not a blanket 15-point bonus or a 17.65% increase in total
character power.

Guardian's existing T=5 already includes this passive. Do not add it again.
If a matched before/after test of a *new* mitigation change justified moving T
from 4.5 to 5, the price would be `100 / 84 × 5 × 0.5 = 2.98 CP`. The half-grade
in that illustration is hypothetical, not a measured Bulwark valuation. Check
shield opportunity cost, bypassing damage paths, and the rest of the kit.

Blademaster and Swashbuckler similarly have combat multipliers outside
`skills.c`: both modify the defensive parry value; riposte and Swashbuckler's
opposing parry check have their own modifiers. A 10% calculation modifier is
not a flat ten-percentage-point success increase. Recompute actual outcomes
before pricing the change.

### New class: a hypothetical Spellwarden

Suppose the proposed playable kit earns `D4 B4 T4 H3 C4 S3 U4`: strong weapon/
spell offense, burst, defenses, healing, anti-magic control, group protection,
and travel. Raw is **111**, or **132.1 CP**. That is too much breadth at strong
grades under this model, even if each individual ability resembles an existing
one. Its ±1-grade uncertainty also means the first job is to substantiate the
most expensive claims, not immediately implement arbitrary reductions.

A deliberate narrower design could choose `D4 B4 T3 H1 C3 S3 U3`: limited
emergency recovery, reduced personal defenses, a narrower disruption role and
less travel. Raw becomes **90**, or **107.1 CP**. The **25.0 CP** reduction is
`(5 × 1 + 5 × 2 + 4 × 1 + 2 × 1) × 100 / 84`. This buys a plausible first
prototype; it does not prove it balanced. Compare it with Mercenary for weapon
pressure, Reaver for martial/casting competition, and Ethermancer for disruption.
Write actual ability limits that justify those lower grades. Naming an ability
"minor" or adding a bypassable restriction does not change its price.

## Updating the system as balance changes

Keep three different edits distinguishable:

1. **Mechanic change:** code/configuration changes what a class can do. Keep
   weights and anchors frozen, rescore affected builds, show before/after CP
   and scenario results, and update ordinary class/help documentation.
2. **Evidence correction:** better tests show an estimated grade was wrong.
   Change that grade, keep the old value and reason in the revision note, and
   check other users of the same mechanic. No gameplay change is implied.
3. **Valuation change:** the community's balance goals or repeated matched
   comparisons show that a domain is systematically under/overpriced. Change
   its shared weight, recalculate **all** incumbents and candidates, and publish
   both old-scale and new-scale totals. Recompute `M` only as an explicit model
   revision, not as part of every ability edit.

For example, changing U's weight from 2 to 3 with `M=84` frozen adds
`100 × U / 84` CP to every build: +5.95 for U5 and +1.19 for U1. This tests
whether the original system undervalued access/escape without a special Rogue
discount. Rerun the full cohort before choosing a revised normalizer or band.

Do not solve for weights solely by forcing all 21 totals to 100: the balance
assumption cannot identify unique prices, and several classes share correlated
capabilities. Preserve positive, shared prices and named anchors. Investigate
large residuals for missing mechanics, bad fixtures or misgraded capabilities.
Use independently observed role contribution and matchup results to distinguish
a pricing problem from an actual balance problem. If using a fitted model later,
validate it on held-out builds/specs instead of only its calibration rows.

When considering admission of a new class, require:

- A legal normal entry route and coherent identity/role, plus every intended
  spec scored independently. Keep it out of the incumbent normalizer until
  the design and evidence have been reviewed.
- An explained total near the 90–110 band and comparison with at least two
  relevant incumbents. Check both low and high uncertainty cases, not only the
  central estimate. Above/below the band triggers investigation; it is not an
  automatic numerical adjustment order.
- No unexplained dominance over its closest peers across their important
  axes/scenarios. A proposed >5 grade needs explicit counterplay and a real
  opportunity cost; retaining grade 5 while raising its output is not allowed.
- No reliable no-counter kill/control chain, unbounded damage/healing/pet loop,
  or mandatory stacking advantage concealed by the scalar score. Inspect the
  first/second party slot, common counters, strongest legal race/loadout, and
  ordinary progression checkpoints.
- Matched behavior evidence for the changed abilities and their interactions,
  with resource use, lag, effective healing, survival, throughput and outcome
  variation recorded. Use repeated independent fights and both initiative
  orders; report trial counts and uncertainty rather than treating one win as
  proof. Run acquisition/use/cleanup journeys where new lifecycle behavior is
  involved.

This is a design review gate, not an automatic live balance controller. The
existing [balance shadow policy](../telemetry/balance/SHADOW_POLICY.md) concerns
a different bounded recommendation target; it does not provide these class
measurements. Historical Power Atlas material also does not supply current
group, escape, resource-recovery or production-balance proof.

### Reusable change record

Keep this in the proposal/PR, or as a short revision note for this document:

```text
Model version / source commit / configuration:
Class, legal race, specialization or ordered multiclass pair:
Level / equipment and consumable manifest / epic budget:
Intended role / incumbent comparisons:
Capability ledger: grants, consumers, conditions, removals, counters:
Before grades D B T H C S U / raw / CP:
After grades D B T H C S U / raw / CP / delta:
Per-axis evidence status, anchors, uncertain grades and low/high CP:
Paired grade-delta bounds / CP delta bounds / shared uncertainties:
Scenario coverage, weights and progression results, including adverse matchups:
Action/resource schedule and first/second-copy group interactions:
Evidence: test commands, fixtures, trial counts, outcome variation, gaps:
Decision / rationale / next observation that would change the decision:
```

## Maintenance and verification

Change roster facts from the code/configuration first, then update this model
and [CLASSES.md](CLASSES.md) together. Preserve their reciprocal links. Recheck
the legal race/class/spec intersection when selecting a new reference build;
do not use all-classes mode to make a test fixture legal.

The [class point contract](../../tests/async/test_class_points_contract.py)
checks the source-eligible roster, example race/spec intersections, HP inputs,
shared weights, raw/CP/sensitivity arithmetic, current median/range, dominance
pairs, scenario weights, and worked calculations. It reads the maintained
Markdown tables directly, so there is no second copy of the scorecards to keep
in sync. The frozen `M` and the current median are checked separately: an
evidence correction must not force the corrected roster's median back to 84.
These checks establish internal consistency and source eligibility, not the
validity of the judgment-based grades or a completed character journey.

Run the focused audit and the existing creation/class help contracts:

```sh
python3 tests/async/test_class_points_contract.py
python3 tests/async/test_class_helpfiles_contract.py
python3 tests/async/test_creation_availability_contract.py
python3 tests/async/test_creation_all_classes_toggle.py
```

Also check relative links with the maintained documentation contract and run
`git diff --check`.

### Version 0.2 revision — 2026-10-19

Central grades, seven prices, scenario weights and `M=84` are unchanged from
version 0.1. The source/configuration snapshot above is unchanged. This revision
publishes the previously implicit sensitivity bounds, exposes the five
estimated dominance pairs, distinguishes incomplete scenario evidence, defines
damage accounting for D/B, and makes the numerical/source audit repeatable.
It does not supply new measured class outcomes or resolve the flagged
comparisons; those require the matched evidence described here.

No gameplay balance, runtime configuration, or production state changes with
this document. The delivered system is usable for transparent design estimates;
its numerical judgments remain provisional until the described matched evidence
is collected. That limitation is part of the scorecard, not a reason to give
unmeasured capabilities zero cost.
