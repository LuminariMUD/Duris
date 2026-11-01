/****************************************************************************
 *
 *  File: random_equipment.c                                    Part of Duris
 *  Usage: the random item generator, salvage materials, encrust stones and
 *         the affect helpers other code borrows
 *  Copyright  1990, 1991 - see 'license.doc' for complete information.
 *  Copyright 1994 - 2008 - Duris Systems Ltd.
 *  Created by: Kvark                   Date: 2002-04-18
 * ***************************************************************************
 */

#include "cmd/interp.h"
#include "net/comm.h"
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "item/objmisc.h"
#include "item/random_equipment.h"
#include "item/random_equipment_config.h"
#include "item/weapon_actions.h"
#include "magic/spells.h"
#include "world/difficulty.h"
#include "world/vnum.obj.h"
#include <string.h>
#include <string>

/*
 * external variables
 */
extern Skill skills[];
extern struct zone_data *zone_table;
extern P_index mob_index;
extern P_room world;
extern void material_restrictions(P_obj);

static P_obj setprefix_obj(P_obj obj, float modifier, int affectnumber);

// Salvage materials live at vnums 400000..400209: 42 material families of five
// quality tiers each, the tiers ascending in item value within a family.
#define MATERIAL_VNUM_BASE 400000
#define MATERIAL_FAMILIES 42
#define MATERIAL_TIERS 5

P_obj create_material(int index)
{
	// 'index' is the caller's level-derived quality on the 0..MAXMATERIAL
	// scale.  It used to be computed and then thrown away, which made every
	// salvaged material a flat roll over the whole range; map it onto the
	// quality tier and leave the family to chance.
	int tier = BOUNDED(0, index * MATERIAL_TIERS / (MAXMATERIAL + 1), MATERIAL_TIERS - 1);
	int matnum = MATERIAL_VNUM_BASE + number(0, MATERIAL_FAMILIES - 1) * MATERIAL_TIERS + tier;

	return read_object(matnum, VIRTUAL);
}

P_obj create_material(P_char killer, int finder_level, int source_level)
{
	if (GET_CLASS(killer, CLASS_ALCHEMIST))
	{
		if (IS_PC(killer) && !number(0, 6))
		{
			killer->only.pc->spell_bind_used = killer->only.pc->spell_bind_used - 10;
			send_to_char("&+YYou feel your power increase some...&n\n", killer);
		}
	}
	int howgood = (int)((finder_level + source_level) / 2.8);
	int material_index = number(0, BOUNDED(1, howgood, MAXMATERIAL));

	return create_material(material_index);
}

P_obj create_stones(void)
{
	return read_object(number(ENCRUST_VNUM_BEGIN, ENCRUST_VNUM_END), VIRTUAL);
}

// Slots 0..70 are the worn-equipment pool selected on two of three draws.
static constexpr int LAST_WORN_SLOT = 70;
static constexpr int WORN_SLOT_ROLL_MAX = 2;
static constexpr int NAMED_ROLL_MAX = 100000;
static constexpr int OWNER_MIN_LEVEL = 45; // Owner keywords require a source above this.
static constexpr int OWNER_ROLL_MAX = 9; // One in ten, also used for the first owner suffix.
static constexpr int EXTRA_SUFFIX_ROLL_MAX = 19; // Zone sets repeat a suffix one in twenty.
static constexpr int WEAPON_SPELL_ROLL_MAX = 2; // One in three zone-named weapons.
static constexpr double ONE_HANDED_BONUS = 0.7; // One-handed weapons retain 70% of hit/damage.

static int choose_slot(int requested)
{
	if (requested != -1)
		return BOUNDED(0, requested, MAX_SLOT - 1);
	return number(0, WORN_SLOT_ROLL_MAX) ? number(0, LAST_WORN_SLOT) : number(0, MAX_SLOT - 1);
}

static int choose_material(int finder_level, int source_level, int requested)
{
	const auto *config = random_equipment_config_get();
	int howgood = (int)((finder_level + source_level) / 2.0);
	howgood = (int)(howgood * config->quality_level_multiplier);
	howgood = difficulty_scale_int(howgood, difficulty_multiplier(DIFFICULTY_LOOT_QUALITY));
	if (requested != -1)
		return BOUNDED(0, requested, MAXMATERIAL - 1);
	int material = howgood > source_level / 3 ? number(source_level / 3, howgood) : howgood;
	return BOUNDED(0, material, MAXMATERIAL - 1);
}

enum random_name_style
{
	PLAIN_NAME,
	ZONE_NAME,
	OWNER_NAME
};

static random_name_style choose_name(P_char finder, int finder_level, int source_level,
				     int requested_material, const zone_data *zone)
{
	// Integer division intentionally makes each 11 levels and each 4 luck a step.
	int chance = 8 * (finder_level / 11) * ((GET_C_LUK(finder) - 60) / 4) * (source_level + 38);
	bool coloured = strip_ansi(zone->name) != zone->name;
	// Both rolls precede the other eligibility checks, even for a fixed material.
	if (number(1, NAMED_ROLL_MAX) < chance && requested_material == -1 && coloured &&
	    (IS_PC(finder) || mob_index[GET_RNUM(finder)].func.mob != shop_keeper))
		return ZONE_NAME;
	if (!number(0, OWNER_ROLL_MAX) && requested_material == -1 &&
	    source_level > OWNER_MIN_LEVEL)
		return OWNER_NAME;
	return PLAIN_NAME;
}

static void name_item(P_obj obj, P_char finder, int slot, int material, int prefix,
		      const zone_data *zone, random_name_style style)
{
	const char *adjective = prefix_data[prefix].m_name;
	const char *substance = material_data[material].m_name;
	const char *noun = slot_data[slot].m_name;
	std::string keyword_tag, display_tag;
	if (style == ZONE_NAME)
	{
		keyword_tag = " " + strip_ansi(zone->name);
		display_tag = std::string(" &+rfrom ") + zone->name;
		if (IS_NEWBIE(finder))
			send_to_char(
				"You got a named random item!  Use 'help named equipment' for a list of what named eq can do for you!\n\r",
				finder);
	}
	else if (style == OWNER_NAME)
	{
		char owner[MAX_STRING_LENGTH];
		snprintf(owner, sizeof(owner), "%s",
			 IS_PC(finder) ? GET_NAME(finder) : FirstWord(GET_NAME(finder)));
		keyword_tag = std::string(" ") + owner;
	}
	// The original tables end each noun with a two-character colour reset.
	bool plural = noun[strlen(noun) - 3] == 's';
	bool vowel = VOWEL(adjective[3]);
	char name[MAX_STRING_LENGTH], brief[MAX_STRING_LENGTH], description[MAX_STRING_LENGTH];
	snprintf(name, sizeof(name), "random _noquest_ %s %s %s%s", strip_ansi(adjective).c_str(),
		 strip_ansi(substance).c_str(), strip_ansi(noun).c_str(), keyword_tag.c_str());
	snprintf(brief, sizeof(brief), "%s %s %s %s%s&n",
		 plural ? "some" :
		 vowel	? "an" :
			  "a",
		 adjective, substance, noun, display_tag.c_str());
	snprintf(description, sizeof(description), "%s %s %s %s%s&n %s here on the ground.",
		 plural ? "Some" :
		 vowel	? "An" :
			  "A",
		 adjective, substance, noun, display_tag.c_str(), plural ? "lie" : "lies");
	set_keywords(obj, name);
	set_short_description(obj, brief);
	set_long_description(obj, description);
}

static bool add_name_affects(P_obj obj, random_name_style style, int slot, const zone_data *zone)
{
	if (style == ZONE_NAME)
	{
		setsuffix_obj_new(obj);
		while (!number(0, EXTRA_SUFFIX_ROLL_MAX))
			setsuffix_obj_new(obj);
		// Draw even for worn items; reversing the operands would shift later rolls.
		return !number(0, WEAPON_SPELL_ROLL_MAX) && slot_data[slot].wear_bit == ITEM_WIELD;
	}
	if (style == OWNER_NAME && !number(0, OWNER_ROLL_MAX))
	{
		setsuffix_obj_new(obj);
		int count = 0;
		// Draw before checking the cap, including after the second extra suffix.
		while (number(1, zone->difficulty + 6) > 6 && count < 2)
		{
			setsuffix_obj_new(obj);
			count++;
		}
	}
	return false;
}

// Apply the shape and weight, preserving float intermediates and truncation.
static void set_wear_and_weight(P_obj obj, int slot, int material, int prefix)
{
	const auto *config = random_equipment_config_get();
	float weight;
	SET_BIT(obj->wear_flags, ITEM_TAKE);
	SET_BIT(obj->wear_flags, slot_data[slot].wear_bit);

	weight = (slot_data[slot].base_weight * prefix_data[prefix].weight_mod *
		  material_data[material].weight_mod);
	weight = (weight + config->weight_base_multiplier * slot_data[slot].base_weight) /
		 config->weight_divisor;
	obj->weight = ((weight < 1.0) && (weight > 0.1)) ? 1 : weight;
}

// Draw tertiary, secondary, then primary, including eligibility rolls below their level.
static void set_stat_affects(P_obj obj, int slot, int material, int prefix, int source_level)
{
	const auto *config = random_equipment_config_get();
	int value;
	int maxValue = random_equipment_stat_max(source_level);
	if (!number(0, config->stat_tertiary_roll_max) &&
	    (source_level > config->stat_tertiary_min_level))
	{
		value = (int)(material_data[material].m_stat * prefix_data[prefix].m_stat *
				      slot_data[slot].m_stat +
			      number(0, config->stat_random_bonus_max));
		obj = setprefix_obj(
			obj, number(MIN(value / config->stat_tertiary_divisor, maxValue), maxValue),
			2);
	}
	if (!number(0, config->stat_secondary_roll_max) &&
	    (source_level > config->stat_secondary_min_level))
	{
		value = (int)(material_data[material].m_stat * prefix_data[prefix].m_stat *
				      slot_data[slot].m_stat +
			      number(0, config->stat_random_bonus_max));
		obj = setprefix_obj(
			obj,
			number(MIN(value / config->stat_secondary_divisor, maxValue), maxValue), 1);
	}
	value = (int)(material_data[material].m_stat * prefix_data[prefix].m_stat *
			      slot_data[slot].m_stat +
		      number(0, config->stat_random_bonus_max));
	obj = setprefix_obj(
		obj, number(MIN(value / config->stat_primary_divisor, maxValue), maxValue), 0);
}

static void set_weapon_spell(P_obj obj, int source_level)
{
	int spell, tries = 0;
	do
	{
		// Low-level negative indices clamp to ice missiles, the table's first row.
		spell = BOUNDED(1, source_level, 60) - number(0, 15);
		spell = MAX(0, spell);
		tries++;
	} while (spells_data[spell].self_only && tries < 100);
	if (tries < 100)
	{
		obj->value[5] = spells_data[spell].spell;
		obj->value[6] = number(15, MAX(20, source_level - 10));
		obj->value[7] = number(45, 60); // One cast per this many hits, on average.
		set_obj_extra2_flags(obj, obj->extra2_flags | (ITEM2_MAGIC));
	}
}

static void set_melee_values(P_obj obj, int slot, int material, int prefix, int source_level,
			     bool should_have_weapon_proc)
{
	int bonus;
	obj->value[0] = slot_data[slot].damage_type;
	obj->type = ITEM_WEAPON;

	if (slot_data[slot].numb_material > 2)
		obj->extra_flags |= ITEM_TWOHANDS;

	obj->value[1] = (int)(1 + (material_data[material].m_stat * prefix_data[prefix].m_stat *
					   slot_data[slot].m_ac +
				   number(0, 20)) /
					  20);

	// MIN is a macro: its repeated dice roll is part of the established sequence.
	obj->value[2] = MIN((1 + (material_data[material].m_stat * prefix_data[prefix].m_stat *
					  slot_data[slot].m_ac +
				  number(0, 20)) /
					 20),
			    ((obj->extra_flags & ITEM_TWOHANDS) ? 32 : 24) / obj->value[1]);
	obj->value[2] = BOUNDED(4, obj->value[2], 10);

	bonus = (int)((material_data[material].m_stat * prefix_data[prefix].m_stat *
		       slot_data[slot].m_stat) /
			      18 +
		      1);

	// Move 2 and 1 up to 3 and 2 so 1 doesn't get overwritten.
	obj->affected[3].location = obj->affected[2].location;
	obj->affected[3].modifier = obj->affected[2].modifier;
	obj->affected[2].location = obj->affected[1].location;
	obj->affected[2].modifier = obj->affected[1].modifier;

	obj->affected[1].location = APPLY_HITROLL;
	obj->affected[1].modifier = bonus + number(0, 1);
	obj->affected[0].location = APPLY_DAMROLL;
	obj->affected[0].modifier = bonus + number(0, 1);

	if (!(obj->extra_flags & ITEM_TWOHANDS))
	{
		obj->affected[0].modifier = (sbyte)(obj->affected[0].modifier * ONE_HANDED_BONUS);
		obj->affected[1].modifier = (sbyte)(obj->affected[1].modifier * ONE_HANDED_BONUS);
	}

	if (IS_BACKSTABBER(obj))
	{
		obj->value[1] = BOUNDED(1, (int)(obj->value[1] / 1.5), 3);
		obj->value[2] = BOUNDED(4, (int)(obj->value[2] * 1.6) + number(0, 2),
					obj->value[1] == 1 ? 8 : 6);
	}

	if (isname("lance", obj->name))
	{
		obj->value[1] = 1;
		obj->value[2] = BOUNDED(6, (int)(obj->value[2] * 1.6) + number(2, 4),
					obj->value[1] == 1 ? 13 : 9);
	}

	if (should_have_weapon_proc)
		set_weapon_spell(obj, source_level);

	if ((obj->affected[3].location != APPLY_NONE) || (obj->affected[2].location != APPLY_NONE))
	{
		set_obj_extra2_flags(obj, obj->extra2_flags | (ITEM2_MAGIC));
	}
}

static void set_longbow_values(P_obj obj, int slot, int material, int prefix)
{
	int bonus;
	obj->type = ITEM_FIREWEAPON;
	obj->value[3] = 1;

	if (slot_data[slot].numb_material > 2)
	{
		obj->extra_flags |= ITEM_TWOHANDS;
	}

	obj->value[0] = (int)(1 + (material_data[material].m_stat * prefix_data[prefix].m_stat *
					   slot_data[slot].m_ac +
				   number(0, 40)));
	obj->value[1] = (int)(1 + (material_data[material].m_stat * prefix_data[prefix].m_stat *
					   slot_data[slot].m_ac +
				   number(0, 40)));

	bonus = (int)((material_data[material].m_stat * prefix_data[prefix].m_stat *
		       slot_data[slot].m_stat) /
			      20 +
		      1);

	// Move 2 and 1 up to 3 and 2 so 1 doesn't get overwritten.
	obj->affected[3].location = obj->affected[2].location;
	obj->affected[3].modifier = obj->affected[2].modifier;
	obj->affected[2].location = obj->affected[1].location;
	obj->affected[2].modifier = obj->affected[1].modifier;

	obj->affected[1].location = APPLY_HITROLL;
	obj->affected[1].modifier = bonus + number(0, 2);
	obj->affected[0].location = APPLY_DAMROLL;
	obj->affected[0].modifier = bonus + number(0, 2);
}

static void set_type_values(P_obj obj, int slot, int material, int prefix, int source_level,
			    bool should_have_weapon_proc)
{
	if (IS_SET(obj->wear_flags, ITEM_WEAR_QUIVER))
	{
		GET_ITEM_TYPE(obj) = ITEM_QUIVER;
		obj->value[0] = (int)(material_data[material].m_stat * number(80, 120));
		obj->value[1] = number(0, 1);
		obj->value[2] = 1;
		obj->value[3] = 0;
	}
	else if (IS_SET(obj->wear_flags, ITEM_WEAR_SHIELD))
	{
		GET_ITEM_TYPE(obj) = ITEM_SHIELD;
		obj->value[0] = number(1, 2);
		obj->value[1] = number(1, 8);
		obj->value[2] = number(1, 5);
		obj->value[3] = (int)(material_data[material].m_stat + 75);
		if (isname("heater", obj->name) || isname("buckler", obj->name))
		{
			obj->value[3] -= 50;
		}
		else if (isname("tower", obj->name))
		{
			obj->value[3] += 50;
		}
		obj->value[4] = number(1, 5);
		obj->value[5] = number(0, 1);
	}
	else if (isname("robe", obj->name))
	{
		GET_ITEM_TYPE(obj) = ITEM_WORN;
		obj->value[0] = (int)(material_data[material].m_stat * number(90, 120));
		obj->value[1] = 0;
		obj->value[2] = 0;
		obj->value[3] = 1;
	}
	else if (IS_SET(obj->wear_flags, ITEM_WIELD) && !isname("longbow", obj->name))
		set_melee_values(obj, slot, material, prefix, source_level,
				 should_have_weapon_proc);
	else if (isname("longbow", obj->name))
		set_longbow_values(obj, slot, material, prefix);
	else
	{
		GET_ITEM_TYPE(obj) = ITEM_ARMOR;
		obj->value[0] = (int)(material_data[material].m_ac * prefix_data[prefix].m_ac *
				      slot_data[slot].m_ac);
	}
}

P_obj create_random_eq(P_char finder, int finder_level, int source_level, int requested_slot,
		       int requested_material)
{
	int slot = choose_slot(requested_slot);
	P_obj obj = read_object(slot_data[slot].wear_bit == ITEM_WIELD ? VOBJ_RANDOM_WEAPON :
									 VOBJ_RANDOM_ARMOR,
				VIRTUAL);
	if (!obj)
	{
		send_to_char("Failed to load a new item.\n\r", finder);
		return NULL;
	}
	// Each step keeps the old roll order, including rolls whose result is discarded.
	int prefix = number(0, MAXPREFIX);
	int material = choose_material(finder_level, source_level, requested_material);
	const auto *zone = &zone_table[world[finder->in_room].zone];
	random_name_style style =
		choose_name(finder, finder_level, source_level, requested_material, zone);
	name_item(obj, finder, slot, material, prefix, zone, style);
	bool weapon_spell = add_name_affects(obj, style, slot, zone);
	set_wear_and_weight(obj, slot, material, prefix);
	set_stat_affects(obj, slot, material, prefix, source_level);
	obj->material = material_data[material].m_number;
	material_restrictions(obj);
	if (isname("unique", obj->name))
		obj->craftsmanship = OBJCRAFT_HIGHEST;
	set_type_values(obj, slot, material, prefix, source_level, weapon_spell);
	return obj;
}

// A 5d6 sum from 5 through 27 sets a permanent affect. Sums 28..30 do nothing
// (21 of 7776 outcomes); the table keeps each sum's original field and bit.
P_obj setsuffix_obj_new(P_obj obj)
{
	static const struct
	{
		unsigned long obj_data::*field;
		unsigned long bit;
	} affects[] = {
		{ &obj_data::bitvector, AFF_DETECT_INVISIBLE }, // 5
		{ &obj_data::bitvector2, AFF2_ULTRAVISION }, // 6
		{ &obj_data::bitvector2, AFF2_FIRESHIELD }, // 7
		{ &obj_data::bitvector, AFF_SLOW_POISON }, // 8
		{ &obj_data::bitvector, AFF_WATERBREATH }, // 9
		{ &obj_data::bitvector, AFF_INFRAVISION }, // 10
		{ &obj_data::bitvector, AFF_PROTECT_GOOD }, // 11
		{ &obj_data::bitvector, AFF_PROTECT_EVIL }, // 12
		{ &obj_data::bitvector2, AFF2_PROT_COLD }, // 13
		{ &obj_data::bitvector, AFF_LEVITATE }, // 14
		{ &obj_data::bitvector2, AFF2_DETECT_EVIL }, // 15
		{ &obj_data::bitvector2, AFF2_DETECT_GOOD }, // 16
		{ &obj_data::bitvector2, AFF2_DETECT_MAGIC }, // 17
		{ &obj_data::bitvector, AFF_PROT_FIRE }, // 18
		{ &obj_data::bitvector5, AFF5_PROT_UNDEAD }, // 19
		{ &obj_data::bitvector2, AFF2_PROT_ACID }, // 20
		{ &obj_data::bitvector, AFF_SENSE_LIFE }, // 21
		{ &obj_data::bitvector, AFF_MINOR_GLOBE }, // 22
		{ &obj_data::bitvector, AFF_FARSEE }, // 23
		{ &obj_data::bitvector3, AFF3_COLDSHIELD }, // 24
		{ &obj_data::bitvector2, AFF2_SOULSHIELD }, // 25
		{ &obj_data::bitvector, AFF_BARKSKIN }, // 26
		{ &obj_data::bitvector, AFF_HASTE }, // 27
	};
	int index = dice(5, 6) - 5;
	if (index < static_cast<int>(ARRAY_SIZE(affects)))
		obj->*affects[index].field |= affects[index].bit;
	return obj;
}

static P_obj setprefix_obj(P_obj obj, float modifier, int affectnumber)
{
	static const struct
	{
		int location;
		float multiplier;
	} affects[] = {
		{ APPLY_HITROLL, 1 }, // 0
		{ APPLY_STR, 1.5 }, // 1
		{ APPLY_DEX, 1.5 }, // 2
		{ APPLY_INT, 1.5 }, // 3
		{ APPLY_WIS, 1.5 }, // 4
		{ APPLY_CON, 1.5 }, // 5
		{ APPLY_MANA, 8 }, // 6
		{ APPLY_HIT, 8 }, // 7
		{ APPLY_MOVE, 8 }, // 8
		{ APPLY_DAMROLL, 1 }, // 9
		{ APPLY_HITROLL, 1 }, // 10
		{ APPLY_DAMROLL, 1 }, // 11
		{ APPLY_SAVING_PARA, -1 }, // 12
		{ APPLY_SAVING_FEAR, -1 }, // 13
		{ APPLY_SAVING_BREATH, -1 }, // 14
		{ APPLY_SAVING_SPELL, -1 }, // 15
		{ APPLY_AGI, 1.5 }, // 16
		{ APPLY_POW, 1.5 }, // 17
		{ APPLY_LUCK, 1.5 }, // 18
		{ APPLY_STR_MAX, 1 }, // 19
		{ APPLY_DEX_MAX, 1 }, // 20
		{ APPLY_INT_MAX, 1 }, // 21
		{ APPLY_WIS_MAX, 1 }, // 22
		{ APPLY_CON_MAX, 1 }, // 23
		{ APPLY_AGI_MAX, 1 }, // 24
		{ APPLY_POW_MAX, 1 }, // 25
		{ APPLY_LUCK_MAX, 1 }, // 26
		{ APPLY_HIT, 7 }, // 27
		{ APPLY_HIT, 6 }, // 28
		{ APPLY_HIT, 5 }, // 29
		{ APPLY_HIT, 4 }, // 30
	};
	if ((int)modifier == 0)
	{
		obj->affected[affectnumber].location = APPLY_NONE;
		obj->affected[affectnumber].modifier = modifier;
		return obj;
	}
	bool duplicate;
	do
	{
		const auto &affect = affects[number(0, ARRAY_SIZE(affects) - 1)];
		obj->affected[affectnumber].location = affect.location;
		obj->affected[affectnumber].modifier = (int)(modifier * affect.multiplier);
		duplicate = false;
		for (int i = 0; i < static_cast<int>(ARRAY_SIZE(obj->affected)); i++)
			if (i != affectnumber && obj->affected[i].location == affect.location)
			{
				duplicate = true;
				break;
			}
	} while (duplicate);
	return obj;
}

// NOT CONNECTED: no object has this proc. specs.assign.c gives the random armour blank
// set_proc() and the random weapon blank nothing, and no other code assigns it, so it never
// runs in the game; tests/async/test_weapon_actions_runtime.py is its only caller. It is kept
// until it is attached on purpose. Its offensive route, selected_random_weapon_action() and
// the itemActions.randomWeapons settings, cannot start until then either.
int random_eq_proc(P_obj obj, P_char ch, int cmd, char *argument)
{
	P_char kala;
	int j;
	P_obj t_obj;
	long curr_time;
	int numNamed = 0;
	int wear_order[] = { 41, 24, 40, 6,  19, 21, 22, 20, 39, 3,  4,	 5,  35, 37,
			     12, 27, 23, 13, 28, 29, 30, 10, 31, 11, 14, 15, 33, 34,
			     9,	 32, 1,	 2,  16, 17, 25, 26, 7,	 36, 8,	 38, -1 };
	int chance = 0;

	if (cmd == CMD_SET_PERIODIC)
	{
		return FALSE;
	}

	if (!IS_ALIVE(ch) || !OBJ_WORN_BY(obj, ch) ||
	    (cmd != CMD_MELEE_HIT && cmd != CMD_GOTHIT && cmd != CMD_GOTNUKED))
	{
		return FALSE;
	}

	if (cmd == CMD_MELEE_HIT)
	{
		chance = 25;
	}

	if (cmd == CMD_GOTHIT)
	{
		chance = 100;
	}

	if (cmd == CMD_GOTNUKED)
	{
		chance = 50;
	}

	kala = legacy_proc_arg<P_char>(argument);

	if (!kala)
	{
		return FALSE;
	}

	curr_time = time(NULL);
	// obj->value[6] = GET_VNUM(mob);
	// obj->value[7] = named_spells[1];

	// wizlog(56, "%d, %d, diff=%d" , obj->timer[0], curr_time,  (obj->timer[0] - curr_time)   );

	if (obj->timer[0] + 15 <= curr_time)
	{
		for (j = 0; wear_order[j] != -1; j++)
		{
			if (ch->equipment[wear_order[j]])
			{
				t_obj = ch->equipment[wear_order[j]];

				if (obj->value[6] == t_obj->value[6] && t_obj->value[7] != 0)
				{
					numNamed++;
				}
			}
		}

		if (IS_FIGHTING(ch) && ((numNamed > 2 && !number(0, chance)) ||
					(cmd == CMD_MELEE_HIT && obj->value[6] == 999 &&
					 IS_SET(obj->wear_flags, ITEM_WIELD) && !number(0, 10))))
		{
			kala = GET_OPPONENT(ch);
			;
			numNamed = obj->value[7];
			if (cmd == CMD_MELEE_HIT)
			{
				const bool valid =
					numNamed > 0 &&
					numNamed < static_cast<int>(ARRAY_SIZE(spells_data));
				if ((!valid || !spells_data[numNamed].self_only) &&
				    selected_random_weapon_action(
					    obj, ch, kala, valid ? spells_data[numNamed].spell : 0,
					    curr_time) != item_action_start::legacy)
					return FALSE;
			}
			act("&+B$n's $q &+rpu&+Rls&+rat&+Res &+Lwith &+be&+Bn&+Wer&+Bg&+by &+Lfor a &+rmoment&+L...&N",
			    TRUE, ch, obj, kala, TO_NOTVICT);
			act("&+BYour $q &+rpu&+Rls&+rat&+Res &+Lwith &+be&+Bn&+Wer&+Bg&+by &+Lfor a &+rmoment&+L...&N",
			    TRUE, ch, obj, kala, TO_CHAR);
			act("&+B$n's $q &+rpu&+Rls&+rat&+Res &+Lwith &+be&+Bn&+Wer&+Bg&+by &+Lfor a &+rmoment&+L...&N",
			    TRUE, ch, obj, kala, TO_VICT);
			numNamed = obj->value[7];
			if (spells_data[numNamed].self_only)
			{
				kala = ch;
			}

			if (numNamed > 0)
			{
				((*skills[spells_data[numNamed].spell].spell_pointer)(
					(int)50, ch, 0, SPELL_TYPE_SPELL, kala, obj));
				// wizlog(56, "%d", numNamed);
				// wizlog(56, "Spell number:%d", spells_data[numNamed].spell);
				// wizlog(56, "List number:%d", spells_data[numNamed].s_number);
				// wizlog(56, "self only:%d", spells_data[numNamed].self_only);
				obj->timer[0] = curr_time;
			}
			return FALSE;
		}
	}

	return FALSE;
}

void set_encrust_affect(P_obj obj, int proc)
{
	switch (proc)
	{
	case SPELL_ACID_BLAST:
		SET_BIT(obj->bitvector2, AFF2_PROT_GAS);
		SET_BIT(obj->bitvector2, AFF2_PROT_ACID);
		break;
	case SPELL_FIREBALL:
		SET_BIT(obj->bitvector, AFF_PROT_FIRE);
		break;
	case SPELL_MAGIC_MISSILE:
		SET_BIT(obj->bitvector, AFF_PROTECT_GOOD);
		break;
	case SPELL_CHILL_TOUCH:
		SET_BIT(obj->bitvector2, AFF2_PROT_COLD);
		break;
	case SPELL_NEGATIVE_CONCUSSION_BLAST:
		SET_BIT(obj->bitvector, AFF_MINOR_GLOBE);
		break;
	case SPELL_SHOCKING_GRASP:
		SET_BIT(obj->bitvector, AFF_SLOW_POISON);
		break;
	case SPELL_FLAMESTRIKE:
		SET_BIT(obj->bitvector, AFF_SENSE_LIFE);
		break;
	case SPELL_BLINDNESS:
		SET_BIT(obj->bitvector2, AFF2_DETECT_MAGIC);
		break;
	case SPELL_ENERGY_DRAIN:
		SET_BIT(obj->bitvector, AFF_HASTE);
		break;
	}
}

bool identify_random(P_obj obj)
{
	char buffer[256];
	char old_name[256];
	char *c;
	int i;

	if (!obj->value[5])
		return false;

	for (i = 0;
	     i < static_cast<int>(ARRAY_SIZE(spells_data)) && spells_data[i].spell != obj->value[5];
	     i++)
		;

	if (i == static_cast<int>(ARRAY_SIZE(spells_data)) || !*spells_data[i].name)
		return false;

	strcpy(old_name, obj->short_description);
	if ((c = strstr(old_name, " of ")))
		*c = '\0';
	if ((c = strstr(old_name, " crafted by")))
		*c = '\0';

	checked_snprintf(buffer, 256, "%s of %s&n", old_name, spells_data[i].name);

	if (!strcmp(buffer, obj->short_description))
		return false;

	set_short_description(obj, buffer);

	return true;
}
