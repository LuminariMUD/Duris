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

P_obj create_material(P_char killer, P_char mob)
{
	if (GET_CLASS(killer, CLASS_ALCHEMIST))
	{
		if (IS_PC(killer) && !number(0, 6))
		{
			killer->only.pc->spell_bind_used = killer->only.pc->spell_bind_used - 10;
			send_to_char("&+YYou feel your power increase some...&n\n", killer);
		}
	}
	int howgood = (int)((GET_LEVEL(killer) + GET_LEVEL(mob)) /
			    2.8); /* make sure you understand this value before ya change it. */
	int material_index = number(0, BOUNDED(1, howgood, MAXMATERIAL));

	return create_material(material_index);
}

P_obj create_stones(void)
{
	return read_object(number(ENCRUST_VNUM_BEGIN, ENCRUST_VNUM_END), VIRTUAL);
}

P_obj create_random_eq_new(P_char killer, P_char mob, int object_type, int material_type)
{
	P_obj obj;
	int ansi_n = 0;
	int howgood, material, prefix, slot, value, bonus, count, chance;
	int splnum, tries;
	bool should_have_weapon_proc = FALSE;
	struct zone_data *zone = NULL;
	char o_name[MAX_STRING_LENGTH];
	char o_short[MAX_STRING_LENGTH];
	char o_long[MAX_STRING_LENGTH];
	char owner[MAX_STRING_LENGTH];
	float weight;
	const struct random_equipment_config *config = random_equipment_config_get();

	// Load the random item blank
	if (object_type == -1)
	{
		// This is hack to make equipment load more often than weapons. Aug09 -Lucrot
		if (number(0, 2))
		{
			slot = number(0, 70); // Worn eq
		}
		else
		{
			slot = number(0, MAX_SLOT - 1); // Anything
		}
	}
	else
	{
		slot = BOUNDED(0, object_type, MAX_SLOT - 1);
	}

	if (slot_data[slot].wear_bit == ITEM_WIELD)
	{
		obj = read_object(VOBJ_RANDOM_WEAPON, VIRTUAL);
	}
	else
	{
		obj = read_object(VOBJ_RANDOM_ARMOR, VIRTUAL);
	}

	if (!obj)
	{
		send_to_char("Failed to load a new item.\n\r", killer);
		return NULL;
	}

	prefix = number(0, MAXPREFIX);

	// Make sure you understand this value before ya change it.
	// howgood runs from 1 to 62 to start.
	howgood = (int)((GET_LEVEL(killer) + GET_LEVEL(mob)) / 2.0);
	// howgood is then changed by the configured seasonal multiplier.
	howgood = (int)(howgood * config->quality_level_multiplier);
	howgood = difficulty_scale_int(howgood, difficulty_multiplier(DIFFICULTY_LOOT_QUALITY));

	if (material_type == -1)
	{
		// howgood caps level check.
		if (howgood > GET_LEVEL(mob) / 3)
		{
			material = number(GET_LEVEL(mob) / 3, howgood);
		}
		else
		{
			material = howgood;
		}
		// Keep within bounds.
		material = BOUNDED(0, material, MAXMATERIAL - 1);
	}
	else
	{
		material = BOUNDED(0, material_type, MAXMATERIAL - 1);
	}

	zone = &zone_table[world[killer->in_room].zone];

	ansi_n = strcmp(strip_ansi(zone->name).c_str(), zone->name);

	if (IS_PC(killer))
	{
		snprintf(owner, MAX_STRING_LENGTH, "%s", GET_NAME(killer));
	}
	else
	{
		snprintf(owner, MAX_STRING_LENGTH, "%s", FirstWord(GET_NAME(killer)));
	}

	// Chance for a named item. 0% for <= level 10, luck = every 4 points over 60 gives one point to multiplier
	// At level 11 killer, 100 luck, 20 mob: 8 * 1 * 10 *  58 =   4640 ->  4.6% chance
	// At level 11 killer, 160 luck, 20 mob: 8 * 1 * 25 *  58 =  11600 -> 11.6% chance
	// At level 56 killer, 100 luck, 62 mob: 8 * 5 * 10 * 100 =  40000 -> 40.0% chance
	// At level 56 killer, 160 luck, 62 mob: 8 * 5 * 25 * 100 = 100000 -> almost certain
	chance = 8 * (GET_LEVEL(killer) / 11) * ((GET_C_LUK(killer) - 60) / 4) *
		 (GET_LEVEL(mob) + 38);
	//  Set the items name / short / long descriptions!
	//  For PCs and non-shop-keeper mobs.
	if ((number(1, 100000) < chance) && (material_type == -1) && ansi_n &&
	    (IS_PC(killer) || mob_index[GET_RNUM(killer)].func.mob != shop_keeper))
	{
		if (IS_NEWBIE(killer))
		{
			send_to_char(
				"You got a named random item!  Use 'help named equipment' for a list of what named eq can do for you!\n\r",
				killer);
		}
		snprintf(o_name, MAX_STRING_LENGTH, "random _noquest_ %s %s %s %s",
			 strip_ansi(prefix_data[prefix].m_name).c_str(),
			 strip_ansi(material_data[material].m_name).c_str(),
			 strip_ansi(slot_data[slot].m_name).c_str(),
			 strip_ansi(zone->name).c_str());

		// If it's a plural noun (ie shoes / boots / leggings / etc).
		// Note: Some plural nouns don't end in s, but ok.
		if (slot_data[slot].m_name[strlen(slot_data[slot].m_name) - 3] == 's')
		{
			snprintf(o_short, MAX_STRING_LENGTH, "some %s %s %s &+rfrom %s&n",
				 prefix_data[prefix].m_name, material_data[material].m_name,
				 slot_data[slot].m_name, zone->name);
			snprintf(o_long, MAX_STRING_LENGTH,
				 "Some %s %s %s &+rfrom %s&n lie here on the ground.",
				 prefix_data[prefix].m_name, material_data[material].m_name,
				 slot_data[slot].m_name, zone->name);
		}
		else
		{
			snprintf(o_short, MAX_STRING_LENGTH, "%s %s %s %s &+rfrom %s&n",
				 VOWEL(prefix_data[prefix].m_name[3]) ? "an" : "a",
				 prefix_data[prefix].m_name, material_data[material].m_name,
				 slot_data[slot].m_name, zone->name);
			snprintf(o_long, MAX_STRING_LENGTH,
				 "%s %s %s %s &+rfrom %s&n lies here on the ground.",
				 VOWEL(prefix_data[prefix].m_name[3]) ? "An" : "A",
				 prefix_data[prefix].m_name, material_data[material].m_name,
				 slot_data[slot].m_name, zone->name);
		}

		//  Zone named items get a higher chance to get multiple affects set.
		// 99.45% chance for one.
		obj = setsuffix_obj_new(obj);
		// 5% chance for 2, .025% chance for 3 ...
		while (!number(0, 19))
		{
			obj = setsuffix_obj_new(obj);
		}
		// set values for a proc(should the item turn out to be a weapon)
		if (!number(0, 2) && (slot_data[slot].wear_bit == ITEM_WIELD))
		{
			should_have_weapon_proc = TRUE;
		}
	}
	else if (!number(0, 9) && (material_type == -1) && (GET_LEVEL(mob) > 45))
	{
		checked_snprintf(o_name, MAX_STRING_LENGTH, "random _noquest_ %s %s %s %s",
				 strip_ansi(prefix_data[prefix].m_name).c_str(),
				 strip_ansi(material_data[material].m_name).c_str(),
				 strip_ansi(slot_data[slot].m_name).c_str(), owner);
		if (slot_data[slot].m_name[strlen(slot_data[slot].m_name) - 3] == 's')
		{
			snprintf(o_short, MAX_STRING_LENGTH, "some %s %s %s&n",
				 prefix_data[prefix].m_name, material_data[material].m_name,
				 slot_data[slot].m_name);
			snprintf(o_long, MAX_STRING_LENGTH,
				 "Some %s %s %s&n lie here on the ground.",
				 prefix_data[prefix].m_name, material_data[material].m_name,
				 slot_data[slot].m_name);
		}
		else
		{
			snprintf(o_short, MAX_STRING_LENGTH, "%s %s %s %s&n",
				 VOWEL(prefix_data[prefix].m_name[3]) ? "an" : "a",
				 prefix_data[prefix].m_name, material_data[material].m_name,
				 slot_data[slot].m_name);
			snprintf(o_long, MAX_STRING_LENGTH,
				 "%s %s %s %s&n lies here on the ground.",
				 VOWEL(prefix_data[prefix].m_name[3]) ? "An" : "A",
				 prefix_data[prefix].m_name, material_data[material].m_name,
				 slot_data[slot].m_name);
		}

		if (!number(0, 9))
		{
			obj = setsuffix_obj_new(obj);
			// To ensure that we don't infinite loop if difficulty isn't set
			count = 0;
			// Zone difficulty generally 1, range 1 to 9 (as of 5/27/2016).
			// For difficutly 1: 1 in 7 chance (about 14%), 2: 2 in 8, 3: 3 in 9, 4: 4 in 10 .. 9: 9 in 15 = 60% chance.
			while ((number(1, zone->difficulty + 6) > 6) && count < 2)
			{
				obj = setsuffix_obj_new(obj);
				count++;
			}
		}
	}
	else
	{
		snprintf(o_name, MAX_STRING_LENGTH, "random _noquest_ %s %s %s",
			 strip_ansi(prefix_data[prefix].m_name).c_str(),
			 strip_ansi(material_data[material].m_name).c_str(),
			 strip_ansi(slot_data[slot].m_name).c_str());
		if (slot_data[slot].m_name[strlen(slot_data[slot].m_name) - 3] == 's')
		{
			snprintf(o_short, MAX_STRING_LENGTH, "some %s %s %s&n",
				 prefix_data[prefix].m_name, material_data[material].m_name,
				 slot_data[slot].m_name);
			snprintf(o_long, MAX_STRING_LENGTH,
				 "Some %s %s %s&n lie here on the ground.",
				 prefix_data[prefix].m_name, material_data[material].m_name,
				 slot_data[slot].m_name);
		}
		else
		{
			snprintf(o_short, MAX_STRING_LENGTH, "%s %s %s %s&n",
				 VOWEL(prefix_data[prefix].m_name[3]) ? "an" : "a",
				 prefix_data[prefix].m_name, material_data[material].m_name,
				 slot_data[slot].m_name);
			snprintf(o_long, MAX_STRING_LENGTH,
				 "%s %s %s %s&n lies here on the ground.",
				 VOWEL(prefix_data[prefix].m_name[3]) ? "An" : "A",
				 prefix_data[prefix].m_name, material_data[material].m_name,
				 slot_data[slot].m_name);
		}
	}

	set_keywords(obj, o_name);
	set_short_description(obj, o_short);
	set_long_description(obj, o_long);

	// Set wear flags
	SET_BIT(obj->wear_flags, ITEM_TAKE);
	SET_BIT(obj->wear_flags, slot_data[slot].wear_bit);

	// base_weight ( 1 - 40 ) * weight_mod ( 0.75 - 1.21 ) * weight_mod( 0.15 - 5.00 )
	// Weight range = 0 - 242 .. wow 242 for an (unearthly or brutal) adamantium platemail
	weight = (slot_data[slot].base_weight * prefix_data[prefix].weight_mod *
		  material_data[material].weight_mod);
	// This brings the crazy platemail down to 107.
	weight = (weight + config->weight_base_multiplier * slot_data[slot].base_weight) /
		 config->weight_divisor;
	// If it's between .1 and 1, round up.
	obj->weight = ((weight < 1.0) && (weight > 0.1)) ? 1 : weight;

	// Shields run from ( 5 - 20) * ( 0.75 - 1.21 ) * ( 0.15 - 5.00 )
	// Min: (( 5 * 0.75 * 0.15) + (2 *  5)) / 3 = 10.5625 / 3 = 3
	// Max: ((11 * 1.21 * 5.00) + (2 * 11)) / 3 = 88.55 / 3 = 29.

	int maxValue = random_equipment_stat_max(GET_LEVEL(mob));
	// Item Attributes
	if (!number(0, config->stat_tertiary_roll_max) &&
	    (GET_LEVEL(mob) > config->stat_tertiary_min_level))
	{
		value = (int)(material_data[material].m_stat * prefix_data[prefix].m_stat *
				      slot_data[slot].m_stat +
			      number(0, config->stat_random_bonus_max));
		obj = setprefix_obj(
			obj, number(MIN(value / config->stat_tertiary_divisor, maxValue), maxValue),
			2);
	}
	if (!number(0, config->stat_secondary_roll_max) &&
	    (GET_LEVEL(mob) > config->stat_secondary_min_level))
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

	obj->material = material_data[material].m_number;

	// Sets anti-class flags based on material type (exemptions via object name)
	material_restrictions(obj);

	if (isname("unique", obj->name))
	{
		obj->craftsmanship = OBJCRAFT_HIGHEST;
	}

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
		// m_stat ranges from 12 - 50,  12-50 + 75 = 87-125 = ac bonus
		obj->value[3] = (int)(material_data[material].m_stat + 75);
		if (isname("heater", obj->name) || isname("buckler", obj->name))
		{
			// 37-75
			obj->value[3] -= 50;
		}
		else if (isname("tower", obj->name))
		{
			// 137-175
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
	{
		obj->value[0] = slot_data[slot].damage_type;
		obj->type = ITEM_WEAPON;

		if (slot_data[slot].numb_material > 2)
			obj->extra_flags |= ITEM_TWOHANDS;

		obj->value[1] =
			(int)(1 + (material_data[material].m_stat * prefix_data[prefix].m_stat *
					   slot_data[slot].m_ac +
				   number(0, 20)) /
					  20);

		obj->value[2] =
			MIN((1 + (material_data[material].m_stat * prefix_data[prefix].m_stat *
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
			obj->affected[0].modifier = (sbyte)(obj->affected[0].modifier * 0.7);
			obj->affected[1].modifier = (sbyte)(obj->affected[1].modifier * 0.7);
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
		{
			tries = 0;
			// Why are we making ice missiles so common here?
			do
			{
				// Range from -14 to 60
				splnum = BOUNDED(1, GET_LEVEL(mob), 60) - number(0, 15);
				// Range 0 to 60
				splnum = MAX(0, splnum);
				tries++;
			} while (spells_data[splnum].self_only && tries < 100);

			if (tries < 100)
			{
				// Spell number
				obj->value[5] = spells_data[splnum].spell;
				// Spell level
				obj->value[6] = number(15, MAX(20, GET_LEVEL(mob) - 10));
				// Chance for spell proc (1 in val7).
				obj->value[7] = number(45, 60);
				SET_BIT(obj->extra2_flags, ITEM2_MAGIC);
			}
		}

		if ((obj->affected[3].location != APPLY_NONE) ||
		    (obj->affected[2].location != APPLY_NONE))
		{
			SET_BIT(obj->extra2_flags, ITEM2_MAGIC);
		}
	}
	else if (isname("longbow", obj->name))
	{
		obj->type = ITEM_FIREWEAPON;
		obj->value[3] = 1;

		if (slot_data[slot].numb_material > 2)
		{
			obj->extra_flags |= ITEM_TWOHANDS;
		}

		obj->value[0] =
			(int)(1 + (material_data[material].m_stat * prefix_data[prefix].m_stat *
					   slot_data[slot].m_ac +
				   number(0, 40)));
		obj->value[1] =
			(int)(1 + (material_data[material].m_stat * prefix_data[prefix].m_stat *
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
	else
	{
		GET_ITEM_TYPE(obj) = ITEM_ARMOR;
		obj->value[0] = (int)(material_data[material].m_ac * prefix_data[prefix].m_ac *
				      slot_data[slot].m_ac);
	}

	return obj;
}

// Good chance of adding a bitvector effect on item. 1 - ( 1 + 6 + 36 ) / 6^5 = about 99.45%
P_obj setsuffix_obj_new(P_obj obj)
{
	switch (dice(5, 6))
	{
	case 5:
		SET_BIT(obj->bitvector, AFF_DETECT_INVISIBLE);
		break;
	case 6:
		SET_BIT(obj->bitvector2, AFF2_ULTRAVISION);
		break;
	case 7:
		SET_BIT(obj->bitvector2, AFF2_FIRESHIELD);
		break;
	case 8:
		SET_BIT(obj->bitvector, AFF_SLOW_POISON);
		break;
	case 9:
		SET_BIT(obj->bitvector, AFF_WATERBREATH);
		break;
	case 10:
		SET_BIT(obj->bitvector, AFF_INFRAVISION);
		break;
	case 11:
		SET_BIT(obj->bitvector, AFF_PROTECT_GOOD);
		break;
	case 12:
		SET_BIT(obj->bitvector, AFF_PROTECT_EVIL);
		break;
	case 13:
		SET_BIT(obj->bitvector2, AFF2_PROT_COLD);
		break;
	case 14:
		SET_BIT(obj->bitvector, AFF_LEVITATE);
		break;
	case 15:
		SET_BIT(obj->bitvector2, AFF2_DETECT_EVIL);
		break;
	case 16:
		SET_BIT(obj->bitvector2, AFF2_DETECT_GOOD);
		break;
	case 17:
		SET_BIT(obj->bitvector2, AFF2_DETECT_MAGIC);
		break;
	case 18:
		SET_BIT(obj->bitvector, AFF_PROT_FIRE);
		break;
	case 19:
		SET_BIT(obj->bitvector5, AFF5_PROT_UNDEAD);
		break;
	case 20:
		SET_BIT(obj->bitvector2, AFF2_PROT_ACID);
		break;
	case 21:
		SET_BIT(obj->bitvector, AFF_SENSE_LIFE);
		break;
	case 22:
		SET_BIT(obj->bitvector, AFF_MINOR_GLOBE);
		break;
	case 23:
		SET_BIT(obj->bitvector, AFF_FARSEE);
		break;
	case 24:
		SET_BIT(obj->bitvector3, AFF3_COLDSHIELD);
		break;
	case 25:
		SET_BIT(obj->bitvector2, AFF2_SOULSHIELD);
		break;
	case 26:
		SET_BIT(obj->bitvector, AFF_BARKSKIN);
		break;
	case 27:
		SET_BIT(obj->bitvector, AFF_HASTE);
		break;
	default:
		break;
	}
	return obj;
}

static P_obj setprefix_obj(P_obj obj, float modifier, int affectnumber)
{
	if ((int)modifier == 0)
	{
		obj->affected[affectnumber].location = APPLY_NONE;
	}
	else
	{
		int inUse[ARRAY_SIZE(obj->affected)];
		int i;
		bool reroll = true;
		float modOriginal = modifier;

		for (i = 0; i < static_cast<int>(ARRAY_SIZE(inUse)); i++)
		{
			inUse[i] = obj->affected[i].location;
		}

		while (reroll)
		{
			switch (number(0, 30))
			{
			case 0:
				obj->affected[affectnumber].location = APPLY_HITROLL;
				modifier = (int)(modifier * 1);
				break;
			case 1:
				obj->affected[affectnumber].location = APPLY_STR;
				modifier = (int)(modifier * 1.5);
				break;
			case 2:
				obj->affected[affectnumber].location = APPLY_DEX;
				modifier = (int)(modifier * 1.5);
				break;
			case 3:
				obj->affected[affectnumber].location = APPLY_INT;
				modifier = (int)(modifier * 1.5);
				break;
			case 4:
				obj->affected[affectnumber].location = APPLY_WIS;
				modifier = (int)(modifier * 1.5);
				break;
			case 5:
				obj->affected[affectnumber].location = APPLY_CON;
				modifier = (int)(modifier * 1.5);
				break;
			case 6:
				obj->affected[affectnumber].location = APPLY_MANA;
				modifier = (8 * modifier);
				break;
			case 7:
				obj->affected[affectnumber].location = APPLY_HIT;
				modifier = (8 * modifier);
				break;
			case 8:
				obj->affected[affectnumber].location = APPLY_MOVE;
				modifier = (8 * modifier);
				break;
			case 9:
				obj->affected[affectnumber].location = APPLY_DAMROLL;
				break;
			case 10:
				obj->affected[affectnumber].location = APPLY_HITROLL;
				break;
			case 11:
				obj->affected[affectnumber].location = APPLY_DAMROLL;
				break;
			case 12:
				obj->affected[affectnumber].location = APPLY_SAVING_PARA;
				modifier = (0 - modifier);
				break;
			case 13:
				obj->affected[affectnumber].location = APPLY_SAVING_FEAR;
				modifier = (0 - modifier);
				break;
			case 14:
				obj->affected[affectnumber].location = APPLY_SAVING_BREATH;
				modifier = (0 - modifier);
				break;
			case 15:
				obj->affected[affectnumber].location = APPLY_SAVING_SPELL;
				modifier = (0 - modifier);
				break;
			case 16:
				obj->affected[affectnumber].location = APPLY_AGI;
				modifier = (int)(modifier * 1.5);
				break;
			case 17:
				obj->affected[affectnumber].location = APPLY_POW;
				modifier = (int)(modifier * 1.5);
				break;
			case 18:
				obj->affected[affectnumber].location = APPLY_LUCK;
				modifier = (int)(modifier * 1.5);
				break;
			case 19:
				obj->affected[affectnumber].location = APPLY_STR_MAX;
				break;
			case 20:
				obj->affected[affectnumber].location = APPLY_DEX_MAX;
				break;
			case 21:
				obj->affected[affectnumber].location = APPLY_INT_MAX;
				break;
			case 22:
				obj->affected[affectnumber].location = APPLY_WIS_MAX;
				break;
			case 23:
				obj->affected[affectnumber].location = APPLY_CON_MAX;
				break;
			case 24:
				obj->affected[affectnumber].location = APPLY_AGI_MAX;
				break;
			case 25:
				obj->affected[affectnumber].location = APPLY_POW_MAX;
				break;
			case 26:
				obj->affected[affectnumber].location = APPLY_LUCK_MAX;
				break;
			case 27:
				obj->affected[affectnumber].location = APPLY_HIT;
				modifier = (7 * modifier);
				break;
			case 28:
				obj->affected[affectnumber].location = APPLY_HIT;
				modifier = (6 * modifier);
				break;
			case 29:
				obj->affected[affectnumber].location = APPLY_HIT;
				modifier = (5 * modifier);
				break;
			case 30:
				obj->affected[affectnumber].location = APPLY_HIT;
				modifier = (4 * modifier);
				break;
			default:
				obj->affected[affectnumber].location = APPLY_HIT;
				modifier = (3 * modifier);
				break;
			}

			for (i = 0; i < static_cast<int>(ARRAY_SIZE(inUse)); i++)
			{
				if (i == affectnumber)
				{
					continue;
				}

				if (obj->affected[affectnumber].location ==
				    obj->affected[i].location)
				{
					// collision on an existing affect slot
					modifier = modOriginal;
					break;
				}
			}
			reroll = (i < static_cast<int>(ARRAY_SIZE(inUse)));
		}
	}

	obj->affected[affectnumber].modifier = modifier;
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

P_obj set_encrust_affect(P_obj obj, int proc)
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

	return 0;
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

	if ((obj->str_mask & STRUNG_DESC2) && obj->short_description)
		FREE(obj->short_description);

	obj->short_description = str_dup(buffer);

	obj->str_mask |= STRUNG_DESC2;

	return true;
}
