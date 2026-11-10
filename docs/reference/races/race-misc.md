# Race balance: miscellaneous rules and historical rationale

Reviewed 2026-11-10. This page collects specific balance considerations that
cross the other race references. Historical explanations are distinguished
from current server behavior and from decisions about future balance.

## 1. Evil-race hardship and racial power

The community-maintained [Duris Wiki: Evil Races](https://duris.fandom.com/wiki/Evil_Races)
explicitly describes a tradeoff. Its introduction lists hostile hometowns,
unhelpful guards, dangerous Underdark travel, and sunlight disadvantages, then
states:

> in return their statistics are generally slightly better, and their racial abilities are superior to the ones the good races receive

This documents a historical rationale for a modest advantage in racial stats
and abilities in exchange for a more difficult environment. It does not specify
a percentage, require every evil race to beat every good counterpart, or
establish a particular damage multiplier.

The repository's inherited documentation corroborates the intended hardship:

- [Drow help](../../../lib/information/help_index#L4877), with similar warnings
  for other evil races, describes deliberately dangerous hometowns as an extra
  challenge for experienced players.
- [Racewars help](../../../lib/information/help_index#L13056) describes harder
  progression and surface travel for evil and undead races.
- The [area-writing guide](../../content/area_writing.txt#L3158) says evil
  characters are intended to have a harder time, in its discussion of shops.

The explicit promise of stronger racial packages comes from community
documentation, not a current formal power-budget specification. The wiki and
inherited help contain older mechanics; they are evidence of historical design
intent, not proof of today's difficulty or racial advantage. No numeric
compensation policy is established by these sources.

**Balance implication:** compare the complete racial package with environmental
costs that still exist. Starting-area difficulty, persistent sunlight penalties,
travel and access restrictions need separate consideration: a temporary early
leveling obstacle does not automatically justify a permanent endgame advantage.
That last point is balance guidance, not a rule quoted from the historical docs.

## 2. Huge player races: Monkey Grip

Formalized 2026-11-10 as the level-1 passive **Monkey Grip**
(`INNATE_MONKEY_GRIP`). All five Huge player races list it in `race innates`;
`innate info monkey grip` explains its effect, eligibility and restrictions.
Equipment hand cost and innate access share `has_monkey_grip()`, which checks
the player's stored base size. The named innate preserves the existing equipment
behavior and the separate NPC giant rule.

### Current hand-cost rule

For a PC, a weapon costs one hand when the character's **stored base size is Huge
or larger**. Under the current player-size assignments, this includes:

- Ogre, Firbolg and Minotaur: ordinary creation races.
- Storm Giant and Wight: restricted/legacy player races.

Wight is the only addition to the previous eligible player roster. Previously,
the rule used the `IS_GIANT` race list for players and NPCs alike, which omitted
Wight. NPCs retain that existing race-based rule.

Barbarian, Troll, Centaur, Drider and Revenant are Large, so they do not receive
this benefit. Death Knight is also Large; Shadow Beast is Medium in the player
initialization path.

The check reads `GET_SIZE`, not the effective-size helper or the inconsistent
`race_size()` lookup. Enlarge, Reduce and Titan Form therefore neither grant nor
remove the hand discount. Player initialization and login assign the base size;
see the [complete size roster](race-size.md#complete-pc-roster).

Sources: [hand cost](../../../src/cmd/actobj.c#L104),
[player size assignment](../../../src/account/nanny.c#L3827),
[NPC giant predicate](../../../src/core/utils.h#L770).

### Gameplay effects and limits

- A qualifying PC can combine a two-handed weapon with a shield or held item,
  or wield two such weapons when training and weapon eligibility permit.
- This reduces weapon hand cost; it does not add hands. Capacity remains two,
  or four with the separate four-hand trait. Two-handed nonweapon items still
  consume two hands.
- Strength-based weapon weight limits, offhand restrictions, dual-wield
  training and class/item restrictions still apply. Wight does not inherit
  Ogre's more permissive offhand weight rule.
- A weapon flagged `ITEM_TWOHANDS` retains the ordinary **1.5 multiplier on
  weapon dice** even when its hand cost is one. This does not multiply the
  entire hit: the damroll contribution is added separately. Hand cost also
  does not change which weapon proficiency the attack uses.
- The legacy `WEAPON_2HANDSWORD` type is recognized as two-handed for hand cost
  even without the flag; the damage multiplier specifically checks the flag.

Sources: [hand accounting and placement](../../../src/cmd/actobj.c),
[weapon proficiency and hit damage](../../../src/combat/fight.c),
[damage construction](race-combat-resolution.md#what-a-landed-ordinary-attack-starts-with).

This is an equipment advantage to include when comparing racial offense and
defense. Equal-weapon comparisons isolate stats, but can miss the value of a
two-handed weapon plus shield or a different legal dual-wield loadout.

### Verification

[The equipment regression](../../../tests/async/test_wear_all_regression.py)
executes the production player-size assignments, hand-cost calculation and
wield/hold/shield branches. Its [fixture](../../../tests/async/wear_all_fixture.cpp)
covers all 37 PC races, the five Huge races' equip-order combinations, growth
and shrinkage flags, the unchanged NPC distinction, nonweapon hand costs, and
Wight's weight/training restrictions. This is executable command-path coverage
with controlled dependencies, not a live-server gameplay session.


## 3. Visible racial and class attack-damage modifiers

Implemented 2026-11-09. Racial output loading is active again, with all **93**
existing `damage.totalOutput.racial.*` entries set to **1.000**, including NPC
entries. Missing racial keys use 1.000 too. This restores configurability while
preserving the previous neutral racial contribution. Every
`damage.totalOutput.class.*` setting is unchanged. The None sentinel retains
its existing special handling.

`race innates <race>` and `class innates <class or specialization>` show a
computed passive feature only when the selected loaded factor differs from
1.000. For example:

```text
*Melee and archery damage: +15% (passive)
*Melee and archery damage: -17.5% (passive)
```

The displayed percentage is `(factor - 1) * 100`, with a sign and fractional
precision. Warrior currently shows +15%, Berserker -10%, Monk -17.5%, and
Rogue +10%. As of 2026-11-10, the six Large player races (Barbarian, Troll,
Centaur, Drider, Revenant and Death Knight) receive +15% melee and archery
damage through `damage.totalOutput.playerRacial.*`. Their racial innate listings
show that bonus. This uses the Large category from player creation/login;
Huge races remain a separate category.
Specializations inherit the base class factor: normal Thief and Assassin use
Rogue's +10%, rather than the retired standalone class IDs. Values come from
the loaded combat tables and player racial properties, not a duplicate innate
grant or the viewer's class.
These are descriptive features, with no new innate IDs, unlocks or commands.

The factor multiplies ordinary melee damage, including ordinary unarmed
attacks, and archery. Some explicit special-attack/item consumers also use it.
It is **not** a universal spell, skill or final-DPS modifier: backstab and Monk's
HP-based superhit use separate formulas. Weapon proficiency, attack counts,
accuracy, timing, spell defenses and other damage stages remain separate.
[Consumers and delivery](race-combat-resolution.md#what-a-landed-ordinary-attack-starts-with).

Racial and class factors multiply: +15% from each yields `1.15 * 1.15 = 1.3225`,
or +32.25% at that stage. Multiclass PCs use the **higher** class factor, then
multiply it by the racial factor. This does not add or multiply both class
bonuses. NPCs keep their separate zone scaling and do not gain PC class factors.
The player racial factor multiplies the shared racial factor before the class
factor. NPCs do not receive the player racial factor, including NPCs with the
same race ID as a Large player race. Missing player racial keys default to 1.000.
The existing damage floor, later defenses and rounding still apply.

The output factor is separate from `damage.damrollModifier.racial.*`, which
limits stored damroll. Activating output does not alter those caps, racial
pulse settings, or the existing class values. Normal property application
updates the loaded tables; character recalculation continues to compose the
combat factor through the existing path.

`race innates <race>` lists every playable race's cap, for example
`*Max damroll (gear + buffs): 75` for Ogre. It uses the same calculation that
enforces the cap, so Troll and Centaur show the 58 they currently receive.

Sources: [loading and composition](../../../src/magic/affects.c),
[racial listing](../../../src/classes/innates.c),
[class listing](../../../src/cmd/class.c),
[shared display formatter](../../../src/abilities/abilities.c),
[shipped properties](../../../lib/duris.properties).

Verification: [damage-output regression](../../../tests/async/test_damage_output_modifiers.py)
checks all shipped racial/class settings, the six Large player bonuses,
defaults and reloads, race/class composition, multiclass maximum, and NPC
isolation and zone scaling. The
[race](../../../tests/async/test_race_command.py) and
[class](../../../tests/async/test_class_command.py) command fixtures exercise
positive, negative, fractional and neutral entries and specialization inheritance.
The [isolated class-command journey](../../../tests/async/run_class_command_journey.py)
also covers mortal-visible class output, live racial property changes, neutral
omission, and modifier help.
