# Random equipment and salvage drops

When a player kills an NPC, the server may generate a piece of equipment, a salvage
material or an encrust stone and put it on the corpse. The player sees "It appears you
were able to salvage a piece of equipment from your enemy." Nothing is drawn from a loot
table: the item is built at that moment from tables of slots, materials and prefixes.
The code lives in `src/item/randomeq.c`, the trigger in `die()` in
`src/combat/fight.c`, and the settings in `lib/random_equipment.cfg`.

## When a kill drops something

The drop block in `die()` runs when the victim is an NPC and the killer, still alive, is
a player or a player's pet. It makes two independent rolls with `check_random_drop()`:

| Roll | Scaled by | A win gives |
| --- | --- | --- |
| Equipment | `drop.piece.percentage` (15.0) | `create_random_eq_new()`, or `create_stones()` one time in 26 |
| Material | `drop.equipment.percentage` (8.0) | `create_material()`, or `create_stones()` one time in 26 |

The setting names are historical: the "piece" percentage governs equipment, and the
"equipment" percentage governs materials. Whatever is created goes into the dying mob's
inventory, so it ends up in the corpse. Only an equipment item prints the salvage line.
When the killer is a pet, the line goes to the pet's owner, but the rolls and the item
use the pet's own level and luck.

## The drop chance

`check_random_drop(killer, mob, piece)` refuses outright when the mob gives no
experience or is a shopkeeper, the killer stands in a guild room, the killer is in a
town and the mob is above level 25, or the killer is more than `drop.maximum.level.gap`
(10) levels above the mob.

A player on the neutral race-war side then wins one time in `drop.neutral.roll.max + 1`
(10) before any of the calculation below, and none of the scaling applies to that win.

Otherwise the chance is:

```text
chance = luck / divisor x level_ratio + (base - 100 / divisor)
       + jitter (-5..5)
       + low-level bonus (0..10, killer below level 26)
       + elite bonus (5..15, elite mob)
chance = chance x Hardcore multiplier x roll percentage x loot-drops dial
win when round(chance) >= a roll of 1..100
```

`divisor` is `drop.luck.divisor` (4.0) and `base` is `drop.base.chance` (50), so a
killer with 100 luck and a level ratio of 1 starts at 50 whatever the divisor. From
killer level 15 up, the level ratio is mob level divided by killer level. Below 15 a
per-level formula asks for a mob several levels higher to reach a ratio of 1. The ratio
never falls below 0.1.

At even levels, with 100 luck and the default settings, a kill wins the equipment roll
about 7.5 percent of the time and the material roll about 4 percent of the time.
The Hardcore multiplier is `bonus.random.equipment.multiplier` in `lib/hardcore.cfg`
(1.5) and applies only to a Hardcore player's own kills.

## What the equipment is

`create_random_eq_new(killer, mob, slot, material)` starts from a blank object,
`VOBJ_RANDOM_WEAPON` (1254) for a wielded slot or `VOBJ_RANDOM_ARMOR` (1252) for
anything else, and fills it in:

- **Slot.** Two times in three it picks from the first 71 entries of `slot_data`
  (armour, jewellery and shields), otherwise from all 109. About one drop in sixteen is a
  weapon.
- **Prefix.** One of the 57 entries of `prefix_data`, uniformly. Each scales stats,
  armour and weight.
- **Material.** The quality index is the average of the killer's and the mob's level,
  times `quality.level.multiplier`, then scaled by the loot-quality dial. The material is
  drawn between a third of the mob's level and that index (or is the index, when that is
  lower), from the 43 usable entries of `material_data`, which are ordered by quality.
- **Name.** The item is either a named zone item, an owner-tagged item or a plain item.
  A named zone item reads "a <prefix> <material> <slot> from <zone>". The roll for it is
  `8 x (killer level / 11) x ((luck - 60) / 4) x (mob level + 38)` out of 100,000,
  so it needs killer level 11 and 64 luck, and gives about 40 percent at level 56 with
  100 luck against a level 62 mob. It also needs the zone's name to contain colour
  codes. A named item gets a permanent affect almost always, and another one time in 20,
  repeating. A named weapon gets a spell proc one time in three. Failing that, a mob
  above level 45 tags one item in ten with the killer's name among its keywords. One in
  ten of those gets a permanent affect, with up to two more on a roll that favours
  harder zones. Everything else is plain.
- **Affects.** The primary affect is always rolled. A secondary affect is possible from
  mobs above `stat.secondary.minimum.level` (20), one time in 3, and a tertiary one from
  mobs above `stat.tertiary.minimum.level` (49), one time in 6. Each strength comes from
  the material, prefix and slot factors plus a random bonus, divided by its
  `stat.*.divisor`, and is capped by the mob's level band: 4, then 5 above level 35, 6
  above 49 and 8 above 60. `setprefix_obj()` picks the location (hit or damage roll, a
  stat or its maximum, hit points, mana, moves, or a saving throw) and re-rolls one the
  item already has.
- **Type.** Weapons get dice and hit and damage rolls from the material, prefix and slot
  factors. One-handed weapons keep 70 percent of the bonus, and backstab weapons and
  lances adjust their dice. Shields, quivers, robes and longbows are special cases, and
  everything else is armour with a value from the factors. `material_restrictions()`
  then adds the material's anti-class flags, and the weight comes from
  `weight.base.multiplier` and `weight.divisor`.

A generated item carries its own name, values and affects, so saves store it like any
other item ([world recovery](../persistence/WORLD_RECOVERY_FORMAT.md) covers it on floors
and corpses).

## Zone sets and weapon spells

Named items from the same zone form a set. `set_proc()` runs periodically on worn
`VOBJ_RANDOM_ARMOR` items, and `random_set()` counts the worn armour and weapons whose
short description has the same "from <zone>" text. The second and third belt attachment
slots do not count. From the third piece on, the wearer gains 5 hit points per piece
beyond the second. A zone listed in `zones_random_data` (`src/world/random.mob.c`) also
grants up to three spells, each at its own piece count, and takes them back when the
count drops.

A named weapon's spell proc stores the spell in `value[5]`, a casting level from 15 up
to the larger of 20 and the mob's level minus 10 in `value[6]`, and a 1-in-45-to-60
chance in `value[7]`. The spell is an entry of `spells_data` from up to 15 below the
mob's level (capped at 60), re-rolled while it is self-only. It fires through the ordinary `weapon_proc()` in
`fight.c`, the packed route of [weapon actions](WEAPON_ACTIONS.md). Identify only hints
that there is more to the weapon; the reveal true name spell appends "of <spell>" to its
name (`identify_random()`).

`random_eq_proc()` in `randomeq.c` is not attached to any object, so neither it nor the
random-equipment route in [weapon actions](WEAPON_ACTIONS.md) runs in the game. Only
`tests/async/test_weapon_actions_runtime.py` calls it.

## Salvage materials and encrust stones

`create_material(killer, mob)` draws a quality index from 0 up to the sum of both levels
divided by 2.8, maps it onto one of five quality tiers, and picks one of 42 material
families at random. The materials are vnums 400000 to 400209, five tiers per family.
When an alchemist's kill drops a material, one time in seven the alchemist also regains
some spell-binding capacity ("You feel your power increase some..."). `create_stones()`
picks one of the encrust stones, vnums 400291 to 400299, which the `encrust` command
uses.

## Other places that make random items

The same generators serve:

- random mobs (`src/world/random.mob.c`), which may carry and wear one or more items;
- the random-zone quest mob (`random_quest_mob_proc()` in `src/world/random.zone.c`),
  which rewards the item it asked for with a stone, then material and equipment pairs;
- the world-quest reward (`src/world/world_quest.c`), when the zone has no quest item;
- the zone recipe drop (`random_recipe()` in `src/classes/drannak.c`), which discards a
  random item instead of making a recipe from it;
- the Forger command `randobj` (`src/item/randobj.c`), with `eq`, `piece` and `stone`
  among its options;
- NPC ship treasure chests (`src/ships/ship_npc.c`), which hold materials and stones.

The calls in shops, crafting and NPC ship crews are commented out.

## Other drops on the same death

Next to the random drop, `die()` handles three more. A dragon that grants experience
drops a dragon scale (vnum 392). An NPC above level 51 that is neither a player's pet
nor conjured drops a soul shard (vnum 400230) 4 times in 250, or 9 in 250 when elite. A
player's kill inside the mob's own zone can drop a recipe for one of that zone's items.

## Tuning and tests

`lib/random_equipment.cfg` holds every setting above with a description, and is read at
boot; restart to apply a change. Hardcore's multiplier is in `lib/hardcore.cfg`. The
loot-drops and loot-quality dials are `difficulty.dial.loot.drops` and
`difficulty.dial.loot.quality` in `lib/duris.properties`; see
[server difficulty dials](CODEBASE.md#server-difficulty-dials).

```sh
python3 tests/async/test_random_equipment_config_contract.py
python3 tests/async/test_random_equipment_config_runtime.py
python3 tests/async/test_random_drop_owner_message.py
python3 tests/async/test_difficulty_dials.py
```

The first two hold the settings and their loader, the third the salvage message's
recipient, and the fourth the loot dials' hooks. No test rolls a drop on a running
server.
