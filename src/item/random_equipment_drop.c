/****************************************************************************
 *
 *  File: random_equipment_drop.c                               Part of Duris
 *  Usage: whether a kill drops random equipment, and the drop itself
 *  Copyright  1990, 1991 - see 'license.doc' for complete information.
 *  Copyright 1994 - 2008 - Duris Systems Ltd.
 *  Created by: Kvark                   Date: 2002-04-18
 * ***************************************************************************
 */

#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "combat/justice.h"
#include "item/random_equipment.h"
#include "item/random_equipment_config.h"
#include "world/difficulty.h"
#include "world/hardcore_config.h"

extern struct zone_data *zone_table;
extern P_index mob_index;
extern P_room world;

// The first fourteen levels use their original offset/divisor pairs. Use double
// arithmetic here before rounding to float, as the former switch did.
static float drop_level_ratio(float finder_level, float source_level)
{
	static const struct
	{
		double offset;
		double divisor;
	} low_levels[] = { { 2, 3 },  { 3, 4 },	 { 4, 5 },  { 4, 6 },  { 5, 6 },
			   { 5, 7 },  { 4, 8 },	 { 4, 9 },  { 3, 10 }, { 2, 11 },
			   { 2, 12 }, { 1, 13 }, { 0, 14 }, { -1, 15 } };
	int index = (int)finder_level - 1;
	if (index >= 0 && index < static_cast<int>(ARRAY_SIZE(low_levels)))
		return (source_level - low_levels[index].offset) / low_levels[index].divisor;
	return source_level / finder_level;
}

// Returns TRUE iff a random item should be created from ch killing the mob.
bool check_random_drop(P_char ch, P_char mob, bool piece)
{
	float char_lvl, mob_lvl, chance, char_mob_lvl_div, luck_divisor;
	const struct random_equipment_config *config = random_equipment_config_get();

	if (!ch || !mob)
	{
		return FALSE;
	}

	if (!GET_EXP(mob) || IS_SHOPKEEPER(mob))
	{
		return FALSE;
	}

	if (IS_ROOM(ch->in_room, ROOM_GUILD))
	{
		return FALSE;
	}

	char_lvl = (float)GET_LEVEL(ch);
	mob_lvl = (float)GET_LEVEL(mob);

	if (CHAR_IN_TOWN(ch) && (mob_lvl > 25))
	{
		return FALSE;
	}

	if ((char_lvl - mob_lvl) > config->drop_max_level_gap)
	{
		return FALSE;
	}

	// Neutral players have an early, unscaled win at the configured odds.
	if (IS_PC(ch) && (GET_RACEWAR(ch) == RACEWAR_NEUTRAL) &&
	    !number(0, config->drop_neutral_roll_max))
		return TRUE;

	char_mob_lvl_div = drop_level_ratio(char_lvl, mob_lvl);
	// Minimum of 1/10th - equivalent of a lvl 50 fighting a lvl 5 mob.
	if (char_mob_lvl_div < .1)
	{
		char_mob_lvl_div = .1;
	}
	luck_divisor = config->drop_luck_divisor;

	// At ratio 1 and luck 100 this starts at the configured base chance. The
	// jitter, low-level bonus and elite bonus are drawn in that order.
	chance = (GET_C_LUK(ch) / luck_divisor) * char_mob_lvl_div +
		 (config->drop_base_chance - 100. / luck_divisor);
	chance += (float)number(config->drop_jitter_min, config->drop_jitter_max);

	if (char_lvl < config->drop_low_level_threshold)
	{
		chance += (float)number(0, config->drop_low_level_bonus_max);
	}

	if (IS_ELITE(mob))
		chance += (float)number(config->drop_elite_bonus_min, config->drop_elite_bonus_max);

	if (IS_HARDCORE(ch))
	{
		chance *= hardcore_config_get()->bonus_random_equipment_multiplier;
	}

	chance *=
		(piece ? config->drop_piece_percentage : config->drop_equipment_percentage) / 100.0;

	chance *= static_cast<float>(difficulty_multiplier(DIFFICULTY_LOOT_DROPS));

	// Preserve the legacy truncation, including negative chances.
	if ((int)(chance + .5) >= number(1, 100)) // NOLINT(bugprone-incorrect-roundings)
		return TRUE;

	return FALSE;
}

// Each successful drop becomes a stone one time in 26.
static constexpr int STONE_ROLL_MAX = 25;

// Equipment and material are independent rolls, with messages credited to the owner.
void random_equipment_kill_drop(P_char killer, P_char victim)
{
	P_obj tempobj;

	if ((IS_PC(killer) || IS_PC_PET(killer)) && IS_NPC(victim) && IS_ALIVE(killer))
	{
		// A pet's kill is reported to its owner; the pet has no one to read it.
		P_char credited_killer = IS_PC_PET(killer) ? GET_MASTER(killer) : killer;

		if (check_random_drop(killer, victim, TRUE))
		{
			if (!number(0, STONE_ROLL_MAX))
			{
				tempobj = create_stones();
			}
			else
			{
				if (GET_LEVEL(killer) > 0)
				{
					tempobj = create_random_eq(killer, GET_LEVEL(killer),
								   GET_LEVEL(victim), -1, -1);
					send_to_char(
						"It appears you were able to salvage a piece of equipment from your enemy.\n",
						credited_killer);
				}
				else
				{
					tempobj = create_material(killer, GET_LEVEL(killer),
								  GET_LEVEL(victim));
					send_to_char(
						"It appears you were able to salvage a piece of material from your enemy.\n",
						credited_killer);
				}
			}
			if (tempobj && victim)
				obj_to_char(tempobj, victim);
		}
		if (check_random_drop(killer, victim, FALSE))
		{
			if (!number(0, STONE_ROLL_MAX))
				tempobj = create_stones();
			else
				tempobj = create_material(killer, GET_LEVEL(killer),
							  GET_LEVEL(victim));

			if (tempobj)
				obj_to_char(tempobj, victim);
		}
	}
}
