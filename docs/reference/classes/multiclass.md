# Multiclassing

Source audit: **2026-11-09**, checkout `9652c5296`; source links and affected
owners refreshed against master `dc93ca3bcb` before publication. Values described
as checked-in come from [duris.properties](../../../lib/duris.properties); a running
server can use different loaded settings. This reference documents implemented
PC behavior, including inconsistencies, rather than an intended balance model.

See the [class overview](../CLASSES.md) for the roster and shared class rules,
the [class documentation index](README.md) for related references, and the
[class points proposal](../CLASS-POINTS.md#specializations-and-multiclassing)
for balance evaluation. Player help is `help multiclass`
([maintained entry](../../../help/duris_help_parsed.hlp#L17645)).

- [Character model and class order](#character-model-and-class-order)
- [Eligibility and requirements](#eligibility-and-requirements)
- [Allowed class pairs](#allowed-class-pairs)
- [Progression reset](#progression-reset)
- [Leveling again](#leveling-again)
- [Skills, spells, and costs](#skills-spells-and-costs)
- [Spell resources and preparation](#spell-resources-and-preparation)
- [Innates and Bard songs](#innates-and-bard-songs)
- [Combat, stats, equipment, and identity](#combat-stats-equipment-and-identity)
- [Class-specific exceptions](#class-specific-exceptions)
- [Removing a secondary class](#removing-a-secondary-class)
- [Persistence and reload](#persistence-and-reload)
- [Worked builds](#worked-builds)
- [Verification and maintenance](#verification-and-maintenance)

## Character model and class order

A PC has one primary class bit (`player.m_class`), one secondary class bit
(`player.secondary_class`), one specialization slot (`player.spec`), one level,
and one XP balance. Multiclassing adds a secondary class to that same character;
it does not create separate class levels, split XP between two tracks, or add
two HP/slot pools. Normal admission never changes the primary class.

`IS_MULTICLASS_PC` means a PC whose secondary field is positive and is not the
legacy `BIT_32` sentinel. Ordinary selection allows one secondary, and rejects
another while it is set. A specialized character can multiclass, losing the
specialization; a multiclass character cannot specialize.

Class membership is deliberately different at different consumers:

- `GET_CLASS(ch, mask)`: either class matches any bit in the mask.
- `GET_PRIME_CLASS`: primary only; `GET_SECONDARY_CLASS`: secondary only.
- `GET_SPEC(ch, class, spec)`: primary class plus specialization slot.
- `SKILL_DATA` / `SKILL_DATA2`: raw primary / secondary ability metadata.
  `SKILL_DATA_ALL` merges them, subject to the rules below.
- `GET_CLASS1` also handles disguise. Displayed class/race and actual class/race
  are not interchangeable.

Order therefore matters even when both directions of a pair are allowed.
The command's legality table is ordered, while the cosmetic multiclass name
lookup accepts either order. For example, Warrior/Mercenary and
Mercenary/Warrior both display Gladiator, but retain different primary classes.
The much larger name table does not authorize additional combinations.
`get_multiclass_name` returns an error string for an unrecognized stored pair.

Sources: [fields](../../../src/core/structs.h#L1046),
[membership and metadata](../../../src/core/utility.c#L5069),
[macros](../../../src/core/utils.h#L420),
[multiclass predicate](../../../src/core/utils.h#L872),
[specialization rejection](../../../src/classes/specializations.c#L590),
[display names](../../../src/cmd/actinf.c#L7442).

NPC multiclassing is a different representation: an NPC marked
`AFF4_MULTI_CLASS` can have several bits in `m_class`. Its skill metadata
chooses the class entry with the highest base cap; its spell lookup chooses the
lowest granted circle across its class bits. PC secondary penalties do not
describe that system. See [NPC skill merge](../../../src/core/utility.c#L5185)
and [NPC spell circles](../../../src/classes/memorize.c#L293).

## Eligibility and requirements

### Listing versus committing a choice

`multiclass` outside a trainer room calls `do_multiclass`, which only lists
choices. Its argument is ignored, so `multiclass cleric` elsewhere cannot
commit a choice. It rejects NPCs, existing multiclass PCs, and actual races
other than **Human or Orc**. Below the required level it still lists future
choices. At sufficient level, outside the proper room it explains that the
location is wrong.

The room's `multiclass_proc` handles the actual `multiclass <class>` command.
In addition to normal interpreter state/posture checks, it requires:

1. A PC with actual `GET_RACE` Human or Orc. NPC/morphed bodies are rejected;
   this is not a general ban on every PC disguise or spell affect.
2. No existing secondary class.
3. At least `multiclass.level.req.min`: checked-in **50**.
4. Epic balance at least `multiclass.epic.req.min`: checked-in **0**.
5. A recognized class name whose ordered pair and target race/class cell pass
   `can_char_multi_to_class`.

The epic requirement is a **balance threshold**, not a charge. The room makes
no admission deduction. It does not require the character to unspecialize
first, and does not ask for a second confirmation before resetting progression.

The room strips leading spaces and scans class IDs in ascending order for the
first `is_abbrev` match against `class_names_table[i].normal`. Use full class
names to avoid prefix ambiguity. This is not the class browser's richer
class/specialization alias parser.

With no argument at the right room, the proc lists choices, but checks the
epic threshold first. Below the level threshold, it lists future choices.
The ordinary listing does not itself check the epic threshold.

Missing-property fallbacks differ: listing defaults to level **41**, whereas
the room defaults to level **50** and **250 epics**. They are not the
checked-in policy and can disagree if configuration keys disappear.

Sources: [listing](../../../src/cmd/actoth.c#L124),
[room admission and mutation](../../../src/specs/specs.room.c#L157),
[command registration](../../../src/cmd/interp.c#L3332),
[requirements](../../../lib/duris.properties#L56).

### Assigned locations

[Assignments](../../../src/specs/specs.assign.c#L1690) bind the proc to rooms
**17** and **52904**. In the loaded area set these are:

- Room 17: Bright White Corridor, in
  [heavens.wld](../../../areas/wld/heavens.wld#L131).
- Room 52904: Before a Flux of Raw Energy, in
  [multiclass_temple.wld](../../../areas/wld/multiclass_temple.wld#L54).
  Its west exit is a gate, and the
  [zone resets](../../../areas/zon/multiclass_temple.zon) include the gate,
  a flux object, and an ice golem.

The [area list](../../../areas/AREA) includes those areas. These are source
placements, not proof that a particular player can reach the room in a
deployed world. Merely standing at a similarly named altar elsewhere does not
invoke this proc.

## Allowed class pairs

The first column below is the unchanged
[`allowed_secondary_classes` table](../../../src/core/constant.c#L41).
The last two columns apply only the **target** race/class filter. They do not
claim that the listed primary can be ordinarily created by that race.

| Primary | Candidate secondary classes | Human target filter | Orc target filter |
| --- | --- | --- | --- |
| Warrior | Mercenary; Cleric | Mercenary; Cleric | Mercenary; Cleric |
| Ranger | Warrior; Druid; Rogue; Psionicist | Warrior; Druid; Rogue | Warrior; Rogue |
| Paladin | Warrior | Warrior | Warrior |
| Anti-Paladin | Warrior | Warrior | Warrior |
| Cleric | Druid; Bard; Warrior; Shaman | Druid; Bard; Warrior; Shaman | Bard; Warrior; Shaman |
| Shaman | Conjurer; Druid; Cleric; Blighter | Conjurer; Druid; Cleric | Conjurer; Cleric; Blighter |
| Sorcerer | Conjurer | Conjurer | Conjurer |
| Conjurer | Sorcerer; Shaman; Bard | Sorcerer; Shaman; Bard | Sorcerer; Shaman; Bard |
| Rogue | Bard; Mercenary | Bard; Mercenary | Bard; Mercenary |
| Mercenary | Rogue; Warrior | Rogue; Warrior | Rogue; Warrior |
| Bard | Sorcerer; Rogue; Illusionist; Conjurer | Sorcerer; Rogue; Illusionist; Conjurer | Sorcerer; Rogue; Illusionist; Conjurer |
| Reaver | Sorcerer; Rogue; Psionicist | Sorcerer; Rogue | Sorcerer; Rogue |
| Ethermancer | Sorcerer; Shaman | Sorcerer; Shaman | Sorcerer; Shaman |
| Summoner | Sorcerer; Shaman | Sorcerer; Shaman | Sorcerer; Shaman |

All other primary rows have no candidates, including **Druid, Blighter,
Psionicist, Necromancer, Monk, Illusionist, Berserker, and Dragoon**.
Paladin can add Warrior; Warrior cannot add Paladin. No allowed candidate
survives as secondary Psionicist for either Human or Orc.

The original [race/class matrix](../../../src/core/constant.c#L1399) forbids
Human Anti-Paladin/Reaver and Orc Ranger/Paladin primaries. The helper does not
revalidate the primary; an existing staff/override-created character can
therefore see results for a primary absent from normal creation.

The helper only requires the target cell to differ from **5** (forbidden).
It does **not**:

- compare the target cell's alignment encoding with current alignment;
- consult creation availability switches or the all-classes/all-races override;
- require a secondary-class teacher or a specialization/race row.

Admission leaves alignment and racewar side unchanged. Subsequent abilities
still enforce their own alignment, deity, terrain, resource, and class checks.
General help's generated candidate list is not race-filtered; the ordinary
`multiclass` command is the personal listing.

Sources: [legality helper](../../../src/core/utility.c#L2111),
[generated help](../../../src/cmd/wikihelp.c#L1044).

## Progression reset

### Exact order

The successful room branch performs these operations in order:

1. Zero `points.max_mana` and `points.base_vitality`, and retain the stored
   `player.time.played` baseline.
2. Call `do_start(ch, CMD_MULTICLASS)` **before** assigning the secondary class.
   This sets level **1**, XP **1**, base HP **1**, and base mana **1**; clears
   the title, ordinary learned skills, XP trophies, and prestige; and puts a
   guilded character on **parole**.
3. Run the normal starter-kit path and `NewbySkillSet(ch, false)` inside
   `do_start`. Epic and tradeskill learning is preserved at this stage.
   Eligible level-one ordinary skills receive a random **5–20** learned
   rating and a taught value of raw base cap minus ten; other ordinary learned
   ratings are zeroed. The starter spell branch initializes qualifying
   praying-class spells.
4. Restore the stored played-time baseline, assign the chosen secondary bit,
   and set specialization to **0**.
5. Call `do_restore`: request affects/derived-value recalculation through
   `balance_affects`, refill HP, mana, vitality, and applicable per-circle slots,
   and restore ordinary conditions. `balance_affects` queues a zero-delay
   event; it is not a synchronous recalculation before the next statement.
6. `forget_spells(ch, -1)` removes all `TAG_MEMORIZE` entries, ready and
   pending. It does not zero the separate per-circle slot array filled by
   restore, nor remove every unrelated spell buff. It also stops active
   preparation; that stop path ends meditation when applicable.
7. Attempt the epic-skill refund described below.
8. Clear XP trophies again.

Sources: [room sequence](../../../src/specs/specs.room.c#L208),
[starter skills](../../../src/cmd/actwiz.c#L5751),
[start/reset](../../../src/cmd/actwiz.c#L5783),
[restore](../../../src/cmd/actwiz.c#L6276),
[deferred recalculation](../../../src/magic/affects.c#L524),
[forgetting](../../../src/classes/memorize.c#L2055),
[preparation stop](../../../src/classes/memorize.c#L613).

The starter-kit call is not an unconditional second equipment grant:
[`load_obj_to_newbies`](../../../src/account/nanny.c#L1120) ordinarily returns
when a PC already has carried items and no pending starter-kit flag. Inventory
and equipped items are not wiped by the multiclass room handler.

The reset does not reroll base attributes, clear the wallet/bank, reset race,
alignment, racewar, frags, birth time, recorded highest level, achievements, or
the separate completed-epic-zone history. XP trophies are their own collection:
[`clear_zone_trophy`](../../../src/item/trophy.c#L81) empties that collection
and marks status/trophies dirty. It is not a reset of every kind of trophy or
progression record.

Most player toggles and Hardcore identity survive because the ordinary
new-character flag initialization is skipped for `CMD_MULTICLASS`. Paladins
have vicious mode cleared. Stored played time is retained, but `do_start`
sets `time.logon` to now without adding elapsed time from the active session;
retaining the stored baseline is not the same as retaining that elapsed time.

There is no final `update_skills` call after secondary assignment. Starter
skills were initialized against the old primary-only state. Later leveling
and login call `update_skills`; do not describe the transition as immediately
retraining every merged skill to its final multiclass cap.

### Epic-skill refund

The start routine temporarily preserves epic skills so the
[refund routine](../../../src/world/epic.c#L2391) can price them:

- Scan epic skills, excluding names matching forge/mine/craft.
- For each skill with a reward-table entry, take
  `q = GET_CHAR_SKILL(ch, skill) / 10` whole ten-point steps.
- With `step = int(epic.progressFactor) / 10` (checked-in **3**), sum
  `1 + n / step` for `n = 0 .. q - 1`, using integer division.
- Refund each summed step at **3 × reward.points_cost** epic points and
  **2 × reward.coins** coin value.

This uses the current effective skill rating and current reward costs, not a
history of what the player paid. It does not reapply the secondary-only
purchase surcharges, and incomplete ten-point steps are not separately priced.

If total point refund is zero, the function returns without its reset
callback. Otherwise a successful in-memory epic transaction clears **all**
non-tradeskill epic learned/taught ratings, credits the epic refund, stages
the coins in the money-pickup mechanism (with a direct-wallet refund fallback
if staging fails), and requests a full character save. Failure does not roll
back the already-performed multiclass reset.

Sources: [refund completion](../../../src/world/epic.c#L295),
[transaction semantics](../../../src/world/epic_transaction.c#L32),
[properties](../../../lib/duris.properties#L2231).
A subsequent epic purchase still requires the configured minimum skill-learning
level, checked-in **30**; a level-one multiclass character has not been granted
a bypass.

## Leveling again

There is one normal XP balance and the same required-XP table, generated by
[`update_exp_table`](../../../src/world/limits.c#L1025). There is no separate
multiclass XP split or required-XP multiplier in that generator. Ordinary
leveling calls `update_skills`, increments prestige, and updates the recorded
highest level only when it is exceeded. Repeating previously reached levels
therefore does not make them new highest-level achievements.

The general progression rules remain in force: the racewar/frag cap, the mortal
maximum **56**, ordinary XP leveling through `exp.maxExpLevel` (checked-in
**50**), and epic-stone advancement above that. Hardcore's configured
XP-leveling bypass is a separate rule; it is not a multiclass benefit.
See [XP advancement](../../../src/world/limits.c#L1808),
[level advancement](../../../src/world/limits.c#L762), and the
[frag-cap reference](../CODEBASE.md#frag-based-level-caps).

The [epic-stone path](../../../src/world/epic.c#L995) also checks
`exp.maxMultiLevel`, checked-in **56**. This property is enforced there; it is
not a universal cap on every staff or Hardcore XP-advance path.

| Target level | Checked-in base epic cost |
| --- | --- |
| 51 | 1,000 |
| 52 | 2,500 |
| 53 | 4,500 |
| 54 | 7,000 |
| 55 | 10,000 |
| 56 | 13,500 |

When the **current** level is already at least 51, multiclass stone cost is
multiplied by `int(exp.multiEpicMultiplier)`, checked-in **1** (fallback **2**).
Thus the present configuration adds no multiclass epic-level surcharge.
That conditional does not multiply the 50→51 purchase.

A matching-level stone accepts the normal epic balance threshold. Another
stone requires a balance of **twice** that cost, but the current transaction
still debits the **single** calculated cost. This is the implemented
eligibility/charge distinction, not a promise that the double threshold is a
double payment. XP and the ordinary level/funds gates must also pass.
See [stone thresholds and debit](../../../src/world/epic.c#L1037),
[configured costs](../../../lib/duris.properties#L2248), and
[Hardcore XP policy](../../../lib/hardcore.cfg#L59).

Death and deleveling use the shared progression rules. In particular, losing
access to a level/circle can invalidate abilities or saved spell copies;
multiclass status does not freeze the pre-reset level or protect it.

## Skills, spells, and costs

### Ordinary skills and instruments/songs

For the active specialization slot (normally **0**), let `Lp/Ls` be the raw
primary/secondary required levels and `Cp/Cs` their raw caps. With checked-in
primary factor **100%** and secondary factor **95%**,
[`SKILL_DATA_ALL`](../../../src/core/utility.c#L5136) returns:

| Granted by | Merged requirement | Merged cap |
| --- | --- | --- |
| Primary only | `Lp` | `floor(Cp × 100 / 100)` |
| Secondary only | `Ls + 5` | `floor(Cs × 95 / 100)` |
| Both | `min(Lp, Ls + 5)` | `max(floor(Cp × 100 / 100), floor(Cs × 95 / 100))` |
| Neither | 0 | 0 |

The factors are configurable through `skill.cap.multi.mod.primarySkill` and
`skill.cap.multi.mod.secondarySkill`. Positive fractional results truncate:
a secondary base cap of **89** becomes **84**, not 95. A secondary-only level-51
skill becomes available at **56**; one requiring level 52 becomes 57 and is
outside ordinary mortal progression.

A merged cap is metadata, not an unconditional ceiling on every effective
rating. [`update_skills`](../../../src/guild/guild.c#L58) checks the merged
level, sets taught values, applies the ordinary `min(40, 3 × level / 2)`
starter floor, and normally clamps learned ordinary skills back to taught.
Instruments and songs have their own update loop using the same metadata.
Equipment/affect skill modifiers and mental anguish act separately in
[`GET_CHAR_SKILL_P`](../../../src/core/utility.c#L5243) and
[`GET_CHAR_SKILL`](../../../src/core/utils.h#L221).
Chaos mode can override ordinary learned/taught values; it must be evaluated
as a separate operating mode, not as normal multiclass progression.

Learning/practice still has its own teacher, affordability, and level/circle
checks in [guild.c](../../../src/guild/guild.c#L740). Gaining class membership
does not automatically finish practicing a skill.

### Spell circles are a separate calculation

Spell `rlevel` means a **circle**, not a character level. The character
overload of [`get_spell_circle`](../../../src/classes/memorize.c#L293) does:

1. If the primary class grants the spell at the active spec slot, use that
   primary circle, even if the secondary has an earlier grant.
2. Otherwise, if the secondary base class grants it, use its circle **+1**.
3. A secondary circle-12 grant becomes unavailable: the +1 result must be
   strictly below the unavailable sentinel `MAX_CIRCLE + 1` (13).

Maximum accessible circle is `clamp(1 + (level - 1) / 5, 1, 12)`: circles
1–12 open at levels **1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56**.
Consequently a secondary-only circle-1 spell first opens at level **6**, and a
secondary-only circle-11 spell at **56**. Both available-circle and actual-grant
checks still apply.

The metadata helper can still be called on spell entries, for example for
training or page calculations, but its `+5` is not the casting-circle rule.
Do not derive spell readiness from a skill listing's merged `rlevel`.

[`knows_spell`](../../../src/classes/memorize.c#L2145) rechecks current circle
access before accepting a saved ready copy. For non-slot preparation, a valid
ready copy returns **-1**; otherwise it checks access metadata and returns the
circle. A circle result alone does not prove there is a ready copy, slot, mana,
book, material component, or legal target. The parser handles those gates.
[`bad_spell_check`](../../../src/classes/memorize.c#L3260) removes memorized
entries no longer granted at any supported circle; it is not the same as the
current-level readiness check.

### Book pages

[`GetSpellPages`](../../../src/classes/memorize.c#L372) starts from the merged
metadata `rlevel`, or 13 if absent; for a multiclass PC it integer-divides
that page count by **2**. Scribe mastery subtracts
`max(1, int(rating / 5))` when present, then the result is floored at one page.
Thus page cost can involve the metadata `+5`, halving, and mastery, while the
spell's usable circle still follows the separate rule above.

### Epic skills

Reward class masks accept **either** class. Level, teacher, prerequisite,
mutual-exclusion, race, and skill-max rules still apply. No specialization
abilities survive merely because both base classes now exist.

For ordinary epic-teacher purchases, with current rating `r`:

```text
cost_mod = 1 + r / epic.progressFactor       (integer division)
epic cost = 3 × int(cost_mod × reward.points_cost)
coin cost = 2 × int(cost_mod × reward.coins)
```

If and only if the reward mask permits the secondary but not the primary,
multiply those results by `int(epic.multiclass.EpicSkillCost)` (**2**) and
`int(epic.multiclass.EpicPlatCost)` (**3**), respectively. A reward permitted
by both classes pays no secondary surcharge; an unrestricted class mask also
does not match that surcharge condition. The 95% ordinary secondary cap is not
the epic-teacher maximum.

`epic.progressFactor=30`, `epic.skillGain=10`, and
`epic.skills.minLevel=30` are the checked-in values. Actual increments and
admission also depend on the teacher record and prerequisites. The teacher
rejects a current rating already at its maximum or at 100; the successful
callback sets learned/taught to `min(100, expected effective rating + gain)`.
It does not additionally clamp the new value to the teacher's maximum. That
callback also debits the coins, refreshes affects, requests a full save, and
applies a combat-round wait; changed funds/rating instead cause an epic refund.
Sources: [teacher and pricing](../../../src/classes/epic_skills.c#L474),
[purchase completion](../../../src/classes/epic_skills.c#L48),
[reward definitions](../../../src/classes/epic_skills.c#L86),
[general reward menus](../../../src/world/epic.c#L2229).

## Spell resources and preparation

### Choose one resource interface, not one per class

The predicates in [utils.h](../../../src/core/utils.h#L954) and
[memorize.c](../../../src/classes/memorize.c#L96) choose how the character
prepares and spends **all** accessible spells.

- A caster primary normally selects the preparation family. Only a
  non-caster primary falls back to secondary book/pray/memorize/commune/
  deforest or psionic-mana predicates.
- The pure-caster set is Sorcerer, Conjurer, Illusionist, Summoner,
  Necromancer, Cleric, Shaman, Bard, Druid, Ethermancer, Theurgist, and Blighter.
  The semi-caster set is Anti-Paladin, Paladin, Ranger, Dragoon, Reaver, and
  Avenger. Avenger is also the partial-caster class.
- Psionicist/MindFlayer primary and Illithid/Planetbound Illithid race use mana.
  A secondary psionic class selects mana only behind a non-caster primary.
  Neither Human nor Orc can ordinarily select secondary Psionicist today.
- Ethermancer membership or Harpy race selects tupor. Undead/celestial forms,
  necroplasm and focus-using races can select other slot interfaces. These
  special states are not additional ordinary Human/Orc multiclass choices.
- `spell_interface_command` resolves interfaces in this order:
  **will → focus → commune → deforest → tupor → assimilate → pray → memorize**,
  subject to the predicates, not merely to possession of a spell.

For ordinary Human/Orc pairs, the resulting families are:

| Primary/build | Spell interface and book classification |
| --- | --- |
| Warrior/Cleric | Pray; no book |
| Ranger with any eligible secondary | Commune; no book |
| Paladin/Warrior or Anti-Paladin/Warrior | Pray; no book |
| Cleric with any eligible secondary | Pray; no book, including secondary Bard |
| Shaman with any eligible secondary | Memorize; classified as non-book |
| Sorcerer, Conjurer, Bard, Reaver, or Summoner with a secondary | Memorize; book class |
| Rogue/Bard | Memorize; book classification inherited from secondary Bard |
| Ethermancer/Sorcerer or Ethermancer/Shaman | Tupor |
| Warrior/Mercenary, Rogue/Mercenary, or either Mercenary pair | No spell interface through those classes |

The book-class set is Sorcerer, Conjurer, Necromancer, Illusionist, Bard,
Summoner, Reaver, and Theurgist; Shaman memorizes but is not in that set.
Primary Shaman/Conjurer and primary Conjurer/Shaman therefore differ even
though both are pure/pure multiclasses.

### Circle capacity and consumption

There is a single capacity calculation:
[`max_spells_in_circle`](../../../src/classes/memorize.c#L233). For an
accessible circle `c`, let `j=max(1, spl_table[min(level, MAXLVL)][c-1])`.

- A partial-caster pair uses `int((j + 1) / 1.5)`.
- Otherwise a multiclass pair uses full `j` only if **both** classes are in
  the pure-caster set; all other pairs use `int((j + 1) / 2)`.
- Above the character's accessible maximum circle, capacity is zero.

This is not two classes' slots added together. The same capacity function
controls list preparation and the per-circle pool for slot systems. New slot
circles are zeroed when leveling unlocks them and must recover.

The [casting-consumption path](../../../src/classes/memorize.c#L2244) checks mana
first, then slot systems, then individual prepared copies. Slot casting spends
one from the spell's **effective** circle; non-slot casting consumes a ready
`TAG_MEMORIZE` copy. Devotion and other explicit retention/recovery skills can
modify consumption. There is no general rule to spend a primary pool for
primary spells and a secondary pool for secondary spells.

### Recovery time

The ordinary [recovery calculation](../../../src/classes/memorize.c#L752)
first diverts undead/Warlock/celestial/necroplasm and tupor users to their
special formulas. For the remaining PC multiclass path, base `time_mult` is:

| Primary | Property | Checked-in value |
| --- | --- | --- |
| Druid or Ranger | `memorize.factor.multi.commune` | 1.75 |
| Blighter | `memorize.factor.multi.deforest` | 1.75 |
| Other | `memorize.factor.multiclass` | 1.75 |

Druid/Blighter primaries have no ordinary secondary candidates, but those
branches still exist for stored or staff-created states.

The ordinary core calculation is:

```text
time = time_mult × lfactor[circle - 1] / (level_factor × stat_factor)
```

Book classes use INT; other ordinary paths use WIS, with a Dragoon POW branch.
The stat factor begins at at least one `STAT_INDEX` unit and includes stat
excess over the actual race's baseline. A primary Druid/Blighter multiclass
receives only `int(excess WIS / 1.3)` for that excess. Below the configured
low-level cap (**25**), the level factor receives the normal low-level
adjustment. The returned time truncates to integer.

Primary Ranger/Druid also receive the checked-in
`memorize.factor.commune=0.9`, terrain modifiers, applicable nature-epic rolls,
and command-lag delay. When not calculating a stat-only display, outside
combat, `level > number(0, 65)` divides the time by **1.5**. Alignment then
multiplies multiclass recovery time by **1** for `[-350,+350]`, **1.6** when
`350 < |alignment| < 900`, and **2** at `|alignment| >= 900`. The extra
single-class reduction at `[-10,+10]` does not apply to multiclasses.
Primary Blighter has its own terrain/nature/lag branch without that alignment
multiplier.

The 1.75 value is an input coefficient, not a universal “75% slower” result.
The comparable ordinary single pure-caster coefficient is 1.25; a single
semi-caster uses 2.25 with a different circle-index adjustment. Class order,
effective circle, stats, terrain, and the special branches can all change the
comparison.

Tupor and undead-style recovery instead use **0.85** for full casters and
**1.7** for semi-casters as classified above. Tupor uses WIS for
Ethermancer/Shaman membership and INT otherwise. Its checked-in
`memorize.factor.tupor=0.9` multiplies the **stat-factor denominator**; sleeping
prone multiplies time by **0.75**, and a successful meditation notch/roll
halves time. Undead-style recovery uses POW's stat index plus its own INT/WIS
excess contributions and a meditation roll. These paths return before the
ordinary 1.75 branch.
Sources: [undead formula](../../../src/classes/memorize.c#L638),
[tupor formula](../../../src/classes/memorize.c#L682),
[terrain/stat detail](../races/race-stats.md),
[recovery timing detail](../races/race-tempo.md).

## Innates and Bard songs

### Innates have a primary-class gate

`has_innate` does not simply union every secondary innate. In
[`innate_unlock_level`](../../../src/classes/innates.c#L413):

1. Class-grant lookup runs only if `class_innates_at_all[innate]` contains the
   **primary** class. That mask includes registrations across specializations,
   not just the currently selected spec.
2. Once inside that gate, it loops through `GET_CLASS` membership, taking the
   lowest applicable class unlock level.
3. The effective racial innate path is evaluated independently; the lower
   eligible racial/class unlock wins.
4. `has_innate` then compares current level to that unlock.

There is no generic +5 secondary-innate delay or 95% innate-strength rule.
However, an innate granted exclusively by the secondary's class family can
fail the primary gate entirely. For example, the Druid/Blighter Forest Sight
registrations do not put Cleric in that mask: Human Cleric/Druid does not gain
Forest Sight just from its secondary Druid entry. This is a current
implementation limitation, not a conclusion that all Druid abilities are
unavailable; many ability handlers use class checks directly.
The displayed-level helper has the same outer primary gate.

Sources: [Forest Sight registrations](../../../src/classes/innates.c#L927),
[`has_innate`](../../../src/classes/innates.c#L457),
[level helper](../../../src/classes/innates.c#L6762).

### Secondary Bard metadata does not govern every song consumer

Instruments and songs receive merged requirements/caps through `update_skills`.
But [`song_learned_level`](../../../src/classes/bard.c#L282) reads only
`m_class`, not `secondary_class`. When the primary has no song entry, the
base-class song helper returns `MAXLVLMORTAL + 1` (**57**).

That value feeds the song chance term `rating + character level - song level`
and the start/verse failure-rest calculations. Thus a secondary-Bard character's
song can be trainable via merged metadata while its performance calculations
still use a primary-only fallback. This is not a blanket prohibition on
singing: instrument type, instrument level/rating, artifact instruments, and
the resulting chance still matter.
Sources: [song chance](../../../src/classes/bard.c#L325),
[song-level fallback](../../../src/classes/memorize.c#L3226).

## Combat, stats, equipment, and identity

### Timing, damage, HP, and saves

The shared combat recalculation selects independent inputs:

- **Melee timing offset:** the **smaller** of
  `damage.pulse.class.<Primary>` and `.<Secondary>`.
- **Ordinary damage factor:** the **larger** of
  `damage.totalOutput.class.<Primary>` and `.<Secondary>`, multiplied by the
  racial output factor. It is not the sum or product of the two class factors.
- **HP class input:** the **larger**
  `hitpoints.class.<Primary/Secondary>` value. This is an input to the HP
  formula, not a multiplier applied to all final displayed HP.
- **Caster MAX-CON equipment HP bonus:** both primary **and** secondary must
  belong to `MAX_CON_BONUS_CLASSES`. That set includes the pure casters plus
  Psionicist/MindFlayer, but excludes ordinary martial/semi-caster classes.
  Merely adding Cleric to Warrior does not qualify.

Timing still goes through AGI/affect/pulse adjustments, Flurry, applicable
Reaver rules, and the final minimum. A lower class timing input does not
remove later class-specific penalties. Ordinary damage factors cover melee
and archery plus explicit consumers, not every spell, special attack, or
final-DPS stage.

The shared [mana calculation](../../../src/magic/affects.c#L344) uses level,
POW, INT, and the configured multiplier; it does not add two class mana
formulas. [Vitality](../../../src/world/limits.c#L110) combines the racial
base, stored base vitality, and applicable endurance. Multiclass reset zeroes
the stored base vitality; subsequent skills/gear/affects still contribute.

Toughness's martial multiplier tests either-class membership in
Warrior/Paladin/Anti-Paladin/Mercenary. It is a separate HP contribution, not
part of the maximum-of-two-class-input rule.

Saving throws are **primary-only** at the class-property stage:
[`find_save`](../../../src/net/sparser.c#L1185) adds
`saves.<type>.class.<Primary>`, not the better/sum of both classes.
[`get_default_save_mod`](../../../src/net/sparser.c#L1209) likewise obtains
the aggressor's spell requirement from primary metadata before its level-based
modifier; a secondary-only spell is not automatically assigned its effective
`get_spell_circle` value there.

Sources: [timing/damage selection](../../../src/magic/affects.c#L1922),
[HP and MAX-CON gate](../../../src/magic/affects.c#L458),
[caster set](../../../src/core/utils.h#L1256),
[toughness](../../../src/magic/affects.c#L364),
[loaded class values](../../../src/magic/affects.c#L3489).
For the full surrounding formulas see [stats](../races/race-stats.md),
[tempo](../races/race-tempo.md), and
[ordinary combat resolution](../races/race-combat-resolution.md).

### Ordinary equipment uses either class, with exceptions

After the applicable race gate,
[`can_char_use_item`](../../../src/world/handler.c#L5159) interprets class
masks this way for a PC multiclass:

- A class **deny list** rejects the item only if **both** classes are denied.
- A class **allow list** accepts the class requirement if **either** class is
  allowed.
- Blighter membership can accept Druid allow-list equipment; Summoner
  membership can accept Conjurer allow-list equipment via earlier special
  branches.

Class access does not remove race, alignment, body-slot, weapon, binding,
ownership, or item-proc restrictions. The broad helper itself also has special
Illithid/primary-MindFlayer behavior; that is not ordinary Human/Orc admission.

[`can_prime_class_use_item`](../../../src/world/handler.c#L5312) instead
tests only the primary class. Its consumers include necroplasm validation/
self-equipping and the Orb of the Sea's slip-out-of-hand behavior. Secondary
eligibility to wear something does not guarantee its proc or form will work.
See [necroplasm](../../../src/item/necroplasm_actions.c#L43),
[self-equipping proc](../../../src/specs/specs.object.c#L2675), and
[Orb of the Sea](../../../src/specs/specs.underworld.c#L559).

The Battlemage coat, object **400218**, has explicit multiclass rejection in
the wear, wear-all, and grab commands. Its Battlemage affect is also only
granted to non-multiclass wearers.
Sources: [wear/grab gates](../../../src/cmd/actobj.c#L7100),
[wear affect](../../../src/cmd/actobj.c#L5542).

The admission and removal handlers do not run a general unequip pass or
revalidate every item proc already active on the character. Do not infer
automatic equipment cleanup merely from changing class state.

## Class-specific exceptions

These are additional explicit PC multiclass/class-order consumers. They
supplement ability grants; none is a universal multiplier on every ability.

- **Shaman totems:** `missing_shaman_totem` accepts any totem for a multiclass
  Shaman rather than requiring the spell's typed lesser/greater totem. The
  cast parser also explicitly bypasses a missing-totem rejection for
  multiclass PCs. A totem can still affect other benefits such as the
  Totemic Mastery cast-time branch.
  [Totem helper](../../../src/classes/shaman.c#L39),
  [parser](../../../src/net/sparser.c#L2057).
- **Druid/Blighter casting speed:** multiclasses lose the automatic
  single-class quick-chant cast-time branch. They use their actual quick-chant
  toggles/skill rolls and other applicable acceleration. The separate Druid
  shortened command-wait branch also requires single-class status.
  [Casting branches](../../../src/net/sparser.c#L2857).
- **Druid alignment balance:** either-class Druid membership qualifies for
  `balance_align`, but it runs in forest terrain. Outside the special
  near-neutral/Evil-racewar case that sets alignment to zero, a multiclass
  shifts by **1** per call rather than the ordinary **5**.
  Druid combat alignment changes outside forests are also doubled.
  [Balance](../../../src/classes/memorize.c#L988),
  [combat alignment](../../../src/combat/fight.c#L2253).
- **Plane shift:** Druid membership in either class retains the level-41
  requirement. The direct home/birthplace return to Prime for a single-class
  Druid/Blighter is explicitly unavailable to multiclasses; other plane-shift
  route checks still apply.
  [Plane shift](../../../src/magic/spells.c#L706).
- **Nature movement and tracking:** either-class Druid membership bypasses
  Wandering Woods' confusion checks for ordinary movement and fleeing.
  Tracking's Druid disturbance branch excludes a **primary Ranger**, so
  Ranger/Druid follows that distinct tracking path.
  [Movement](../../../src/cmd/actmove.c#L2476),
  [flee](../../../src/cmd/actoff.c#L3094),
  [tracking](../../../src/cmd/track.c#L969).
- **Charm:** Druid membership in either class selects the Druid charm rules,
  including maximum target level `character level - 10` and its separate
  natural-creature sure-charm threshold. It is not solely determined by which
  class granted the spell.
  [Charm classification and limits](../../../src/magic/magic.c#L12125).
- **Shape learning:** `shapechange_learn_level` subtracts **10** effective
  levels for multiclass status, and another **5** for non-Druids. This affects
  learning a creature's shape against its required level, not the stored
  character level. The forest specialization bonus normally cannot coexist
  with multiclass status.
  [Shape learning](../../../src/cmd/actnew.c#L2517).
- **Conjure:** a multiclass PC can validate a conjured target with at most
  **one class**, versus three for another caster. NPC class count comes from
  the NPC multiclass flags. The default conjurable VNUM **400003** bypasses
  that target-level/class-count block; ordinary targets must also be within
  five levels.
  [Conjure eligibility](../../../src/classes/drannak.c#L1281).
- **Soulshield:** the `|alignment| >= 950` alignment gate is bypassed for a
  multiclass PC. Other soulshield restrictions still apply.
  [Soulshield](../../../src/magic/magic.c#L22351).
- **Quest class admission:** the named-quest acceptance branch checks
  `m_class & allowed_classes`; a secondary class does not satisfy that
  primary-only mask.
  [Quest acceptance](../../../src/cmd/nq.c#L838).
- **Hardcore score:** multiclass status multiplies the completed base score
  `level × level_points + XP / experience_divisor + frags × frag_points`
  by `score.multiclass.multiplier`, checked-in **2**. It does not double the
  individual stored level, XP, or frags.
  [Score](../../../src/world/hardcore.c#L63),
  [configuration](../../../lib/hardcore.cfg#L128).

Normal class-conditioned consumers using `GET_CLASS` still see either class.
Their own branch ordering, equipment, skill rating, alignment, and prerequisites
determine the result; there is no general rule to add two copies of a passive
or replace every primary-only check with the better class.

Ascend/descend and the historical Monk remort are not alternative ordinary
multiclass selectors. The former are PC-disabled as described in the
[class overview](../CLASSES.md#unavailable-commands-and-temporary-forms);
the Monk remort assignment is
[commented out](../../../src/specs/specs.assign.c#L198).

## Removing a secondary class

The assigned route is object **44165**, `unmulti_altar`, invoked through
`pray altar`. The proc requires `CMD_PRAY`, an argument containing the
literal substring `altar`, and a multiclass PC. The
[object assignment](../../../src/specs/specs.assign.c#L1554),
[object](../../../areas/obj/tikitt.obj#L1045), and
[zone reset](../../../areas/zon/tikitt.zon#L198) place a high altar in room
**44333**, The High Altar
([room](../../../areas/wld/tikitt.wld#L5264)). That establishes checked-in
placement, not successful access or a live reset.

[`unmulti`](../../../src/cmd/actinf.c#L10274) requires **100 epics**, then
submits a **100-epic deduction**. On successful in-memory completion it:

1. Sets secondary class and specialization to **0**.
2. Forgets all ready/pending `TAG_MEMORIZE` copies.
3. Calls `update_skills` against the remaining primary class.
4. Reports that the recent knowledge has fallen away.

This keeps the **current** level and XP. It does not restore the pre-multiclass
level, XP, specialization, learned ordinary skill snapshot, title, prestige,
or guild status. Ordinary secondary-only skills/songs can be zeroed by the
update. Shared/primary ordinary skills follow their current recalculation.

The removal callback does not call `refund_epic_skills`: it does not refund
secondary epic purchases, and `update_skills` ordinarily leaves existing epic
learned/taught ratings alone. Possession of a retained epic rating is still
distinct from satisfying that skill handler's class checks. No explicit full
restore, pool reset, equipment sweep, or full-save request is made by this
callback.

There is no historical-secondary lock or one-time selection flag checked by
ordinary admission. After removal, reaching the eligibility requirements again
permits a new choice and another reset. Specialization becomes possible only
when its usual level/teacher/race/cooldown checks pass; unmulti does not clear
the saved unspecialize timer.

Sources: [altar dispatch](../../../src/specs/specs.object.c#L11765),
[removal completion](../../../src/cmd/actinf.c#L10258),
[skill update](../../../src/guild/guild.c#L58).

## Persistence and reload

MariaDB persistence stores the live character's new state; there is no separate
pre-multiclass restore record in this transition.

- Snapshot status captures `class_primary`, `class_secondary`,
  specialization, level, XP, base values, alignment, epics, and other state.
  Skill learned/taught ratings, affects, and XP trophies are separate snapshot
  components.
- The repository maps those class fields to `player_data.m_class`,
  `secondary_class`, and `spec`. Materialization reapplies the class fields
  before loading saved skills/affects.
- Login later calls `update_skills`, and spell use checks current eligibility.
  A saved spell copy cannot authorize an otherwise inaccessible circle.
- Epic transactions change balances in memory and invoke their completion
  **before returning**. They mark status dirty and separately queue the ledger
  record. “Committed” in these callbacks is not a MariaDB class-change
  acknowledgement.

There are material differences between the two transitions' save requests:

- **Selection:** `clear_zone_trophy` explicitly marks status and trophies
  dirty. A positive epic-skill refund also requests a full character save.
  Without that refund, the room handler does not explicitly request a full
  checkpoint or mark its changed skills/affects components dirty.
- **Removal:** the epic deduction marks status dirty. The callback changes
  skills and prepared affects but does not explicitly mark those components
  dirty or request a full save.
- The periodic dirty-player checkpoint captures **marked** components, not an
  unconditional full character image. An ordinary manual/full or terminal
  save can capture the remaining components. The exact intervening crash
  outcome therefore depends on which components were queued and written.

Do not equate the success messages with a fully durable, atomic
class/skills/affects/refund transition. In particular, this audit does not
establish crash-safe rollback or atomic coupling to the staged coin refund.
Ordinary checkpoints are not journaled; the single writer's documented retry
and failure rules apply.

Sources: [status capture](../../../src/player/player_snapshot_capture.c#L134),
[repository columns](../../../src/player/player_snapshot_repository.c#L177),
[class hydration](../../../src/player/player_load_materialize.c#L211),
[skill hydration](../../../src/player/player_load_materialize.c#L674),
[login skill update](../../../src/account/nanny.c#L1727),
[epic transaction boundary](../../../src/world/epic_transaction.c#L32),
[dirty checkpoint](../../../src/persistence/persistence_checkpoint.c#L99),
[component selection](../../../src/player/player_save_pipeline.c#L252),
[full save](../../../src/cmd/actoth.c#L2439).
See the [save pipeline](../../persistence/PLAYER_SAVE_PIPELINE.md) for the full
persistence contract.

The MariaDB materializer bounds the specialization value but does not itself
rerun multiclass admission, race filtering, or clear every nonzero spec on a
multiclass record. Do not assume an arbitrary staff/SQL-created state is a
legal player build. The legacy parser's spec cleanup is not proof that the
authoritative MariaDB hydration applies the same cleanup.

## Worked builds

These examples apply the checked-in rules and coefficients, not measured
combat ratings.

**Human Warrior → Cleric:** a legal ordered pair. Admission at level 50 resets
to level 1. The character uses prayer, with semi-caster capacity because
Warrior is not a pure caster. A Cleric-only circle-1 spell moves to circle 2
(level 6). A Cleric-only ordinary level-10 skill moves to level 15 with 95% of
its raw secondary cap. HP uses the Warrior input **1.2**, ordinary output uses
Warrior **1.15**, and the timing offset is `min(0, +1)=0`. The two-caster
MAX-CON gear-HP bonus does not apply.

**Human Conjurer → Shaman versus Human Shaman → Conjurer:** both directions are
legal and both have full pure/pure capacity. Their maximum HP class input is
**0.7**, ordinary output **0.9**, and timing offset **+1**. Conjurer primary is
a book class using INT-based ordinary recovery; Shaman primary is a non-book
memorizing class using WIS. Primary spell circles and which epic rewards
receive secondary-only surcharges differ by order.

**Human Rogue → Bard versus Human Bard → Rogue:** both are legal. Both use
memorization with book classification and semi-caster capacity; their selected
HP input is **0.85**, ordinary output **1.2**, and timing offset **-1**.
Rogue/Bard receives secondary-only song metadata penalties and the primary-only
song-level fallback described above. Bard/Rogue does not use that fallback
for base Bard songs.

**Orc Shaman → Blighter:** legal, while Orc Shaman → Druid is filtered out.
The primary remains Shaman: preparation is non-book memorization, not deforest.
A Blighter-only spell still receives +1 circle, and secondary-only innate
access must pass the actual innate gate rather than being assumed.

## Verification and maintenance

The 2026-11-09 audit traced admission, reset, class/race tables, skill merge,
spell circles/resources/recovery, innates, Bard consumers, epic purchases/
refunds/leveling, combat/stat selection, equipment, removal, and MariaDB
capture/hydration. It made no gameplay-code changes.

The following existing checks passed during the audit, run individually from
the repository root:

```sh
python3 tests/async/test_spells_command.py
python3 tests/async/test_skills_command.py
python3 tests/async/test_memorized_spell_eligibility.py
python3 tests/async/test_damage_output_modifiers.py
python3 tests/async/test_epic_skill_level_gate.py
python3 tests/async/test_epic_transaction_contract.py
python3 tests/async/test_epic_stone_runtime.py
python3 tests/async/test_player_snapshot_capture.py
python3 tests/async/test_documentation_contract.py
git diff --check
```

Their evidence differs: the browser, eligibility, and damage checks execute
real extracted calculations under sanitizers; the epic checks mix source
contracts and native harnesses; snapshot checks qualify capture/codec
behavior. They do not constitute a complete multiclass lifecycle journey.

An additional temporary ASan/UBSan probe executed the real legality helper,
skill merge, and innate lookup against bounded fixtures. It confirmed the
Human/Orc target filters, secondary +5 delay, truncated 95% cap, shared-skill
merge, and the primary-gated secondary Forest Sight example. Its race/skill
fixtures are not a live-world or database qualification.

**Not exercised end to end:** a real player traveling to both procs,
multiclassing with existing gear/pets/buffs, every class-pair ability,
positive/zero/failing epic refunds and coin collection, removal followed by
reselection/specialization, and save/restart/crash windows across all changed
components. The source-level save gaps and primary-only innate/song consumers
above should remain visible until direct qualification or implementation
changes resolve them.

When changing multiclass behavior, check both command and room paths,
ordered pairs **and** race filters, shared versus secondary-only grants,
resource classification, existing learned/affect state, and save-component
marking. Update this reference and the maintained help sources when their
player-facing claims change. Keep `CLASSES.md` as the link to this dedicated
reference rather than reintroducing a second multiclass rules section.
