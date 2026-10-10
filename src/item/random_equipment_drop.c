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

// Returns TRUE iff a random item should be created from ch killing the mob.
bool check_random_drop(P_char ch, P_char mob, bool piece)
{
	// Normally, we'd do char_lvl and mob_lvl as ints, but that would require a lot of casting.
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

	// Neutrals get a 10% bonus chance for drops.
	if (IS_PC(ch) && (GET_RACEWAR(ch) == RACEWAR_NEUTRAL) &&
	    !number(0, config->drop_neutral_roll_max))
		return TRUE;

	// Since extremely low lvl characters can easily get a high multiplier.
	// Note: 1x = base 50% chance, 2x = base 75% chance, 3x = base 100% chance.
	switch ((int)char_lvl)
	{
	case 1:
		// Requires lvl 5 mob for 1x multiplier, 8 for 2x, 11 for 3x
		char_mob_lvl_div = (mob_lvl - 2.) / 3.;
		break;
	case 2:
		// Requires lvl 7 mob for 1x multiplier, 11 for 2x, 15 for 3x
		char_mob_lvl_div = (mob_lvl - 3.) / 4.;
		break;
	case 3:
		// Requires lvl 9 mob for 1x multiplier, 14 for 2x, 19 for 3x
		char_mob_lvl_div = (mob_lvl - 4.) / 5.;
		break;
	case 4:
		// Requires lvl 10 mob for 1x multiplier, 16 for 2x and 22 for 3x
		char_mob_lvl_div = (mob_lvl - 4.) / 6.;
		break;
	case 5:
		// Requires lvl 11 mob for 1x multiplier, 17 for 2x and 23 for 3x
		char_mob_lvl_div = (mob_lvl - 5.) / 6.;
		break;
	case 6:
		// Requires lvl 12 mob for 1x multiplier, 19 for 2x, 26 for 3x
		char_mob_lvl_div = (mob_lvl - 5.) / 7.;
		break;
	case 7:
		// Requires lvl 12 mob for 1x multiplier, 20 for 2x, 28 for 3x
		char_mob_lvl_div = (mob_lvl - 4.) / 8.;
		break;
	case 8:
		// Requires lvl 13 mob for 1x multiplier, 22 for 2x, 31 for 3x
		char_mob_lvl_div = (mob_lvl - 4.) / 9.;
		break;
	case 9:
		// Requires lvl 13 mob for 1x multiplier, 23 for 2x, 33 for 3x
		char_mob_lvl_div = (mob_lvl - 3.) / 10.;
		break;
	case 10:
		// Requires lvl 13 mob for 1x multiplier, 24 for 2x, 35 for 3x
		char_mob_lvl_div = (mob_lvl - 2.) / 11.;
		break;
	case 11:
		// Requires lvl 14 mob for 1x multiplier, 26 for 2x, 38 for 3x
		char_mob_lvl_div = (mob_lvl - 2.) / 12.;
		break;
	case 12:
		// Requires lvl 14 mob for 1x multiplier, 27 for 2x, 40 for 3x
		char_mob_lvl_div = (mob_lvl - 1.) / 13.;
		break;
	case 13:
		// Requires lvl 14 mob for 1x multiplier, 28 for 2x, 42 for 3x
		char_mob_lvl_div = mob_lvl / 14.;
		break;
	case 14:
		// Requires lvl 14 mob for 1x multiplier, 29 for 2x, 44 for 3x
		char_mob_lvl_div = (mob_lvl + 1.) / 15.;
		break;
	default:
		// Note: Since MAXLVL = 62, and 3 ~~ 62 / 20, the highest level you can score 100% base via level
		//   is ch at level 20 vs a level 60 or higher mob.  Highest likely is level 16 ch vs level 48 mob.
		char_mob_lvl_div = mob_lvl / char_lvl;
		break;
	}
	// Minimum of 1/10th - equivalent of a lvl 50 fighting a lvl 5 mob.
	if (char_mob_lvl_div < .1)
	{
		char_mob_lvl_div = .1;
	}
	luck_divisor = config->drop_luck_divisor;

	/* Start with a 50% chance for even levels and 100 luck.
	 * All of below assumes luck_divisor == 4.000:
	 * To start with a 100% chance with equal levels, you need 300 luck = (50 * luck_divisor + 100).
	 *   So, to make it 400 luck for 100% chance with equal levels, set luck_divisor = 6 (+1. for every +50 luck).
	 * To start with a 100% chance with 100 luck, you need a level multiplier of 3.0.
	 *   Due to the multiplier not being a straight division at low lvls (for 100% base chance):
	 *     @lvl 1 ch, mob lvl >= 12, @lvl 2 ch, mob lvl >= 14, @lvl 3 ch, mob lvl >= 21, @lvl 4 ch, mob lvl >= 24.
	 *   At lvl 5 ch, mob lvl >= 15... hrm
	 * Note: To change the 50% base chance, do not change the format of the function below,
	 *   just change the 50 near the end to whatever base % you want.
	 * You can change drop.luck.divisor in lib/random_equipment.cfg without changing the base chance
	 *   with the equation in this format.
	 */
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

	if (piece)
	{
		chance *= config->drop_piece_percentage / 100.0;
	}
	else
	{
		chance *= config->drop_equipment_percentage / 100.0;
	}

	// Add .5 for rounding fix to floor-function type-casting.
	chance *= static_cast<float>(difficulty_multiplier(DIFFICULTY_LOOT_DROPS));

	// Preserve the original truncation, including negative chances, during the move.
	if ((int)(chance + .5) >= number(1, 100)) // NOLINT(bugprone-incorrect-roundings)
		return TRUE;

	return FALSE;
}

// object code - Normal kills.  Kvark
void random_equipment_kill_drop(P_char killer, P_char victim)
{
	P_obj tempobj;

	if ((IS_PC(killer) || IS_PC_PET(killer)) && IS_NPC(victim) && IS_ALIVE(killer))
	{
		// A pet's kill is reported to its owner; the pet has no one to read it.
		P_char credited_killer = IS_PC_PET(killer) ? GET_MASTER(killer) : killer;

		// if(GET_LEVEL(victim) < 30 || GET_LEVEL(killer) < 20)
		//   {
		if (check_random_drop(killer, victim, TRUE))
		{
			if (!number(0, 25)) // &&
			// (GET_LEVEL(victim) > 51))
			{
				tempobj = create_stones();
			}
			else
			{
				// if(GET_LEVEL(victim) < 30 || GET_LEVEL(killer) < 20) //removing level restriction, adding racewar check goods only - drannak
				// if(GET_RACEWAR(killer) == RACEWAR_GOOD || GET_RACEWAR(killer) == RACEWAR_EVIL) //allowing evils to get randoms 1/26/13 drannak
				if (GET_LEVEL(killer) > 0)
				{
					tempobj = create_random_eq_new(killer, victim, -1, -1);
					send_to_char(
						"It appears you were able to salvage a piece of equipment from your enemy.\n",
						credited_killer);
				}
				else
				{
					tempobj = create_material(killer, victim);
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
			if (!number(0, 25)) // &&
				// (GET_LEVEL(victim) > 51))
				tempobj = create_stones();
			else
				tempobj = create_material(killer, victim);

			if (tempobj)
				obj_to_char(tempobj, victim);
		}
		// }
	}
}
