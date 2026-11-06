/****************************************************************************
 *
 *  File: sillusionist.c                   Part of Durismud
 *  Usage: Illusionist spells woowoo!
 *  Copyright  1990, 1991 - see 'license.doc' for complete information.
 *  Copyright 1994 - 2008 - Duris Systems Ltd.
 *  Copyright  2000, 2003 - durismud project
 *  Created by: Ilienze                   Date: 2002-08-30
 *****************************************************************************
 */

#ifndef _ILLUSIONIST_MAGIC_C_

#include "core/prototypes.h"
#include "item/named_set_effects.h"
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "core/utils.h"
#include <algorithm>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "combat/arena.h"
#include "combat/arenadef.h"
#include "combat/ctf.h"
#include "combat/damage.h"
#include "classes/disguise.h"
#include "combat/justice.h"
#include "combat/training_dummy.h"
#include "core/mm.h"
#include "item/objmisc.h"
#include "world/specs.prototypes.h"
#include "magic/spells.h"
#include "abilities/abilities.h"
#include "player/player_load_offline.h"
#include "sql/sql.h"
#include "world/vnum.mob.h"
#include "world/weather.h"

/*
 * external variables
 */
extern P_index obj_index;
extern P_char character_list;
extern P_desc descriptor_list;
extern P_char combat_list;
extern P_obj object_list;
extern P_room world;
extern P_index mob_index;
extern const char *apply_types[];
extern const flagDef extra_bits[];
extern const flagDef anti_bits[];
extern const char *item_types[];
extern const struct stat_data stat_factor[];
extern const char *dirs[], *dirs2[];
extern const int rev_dir[];
extern int avail_hometowns[][LAST_RACE + 1];
extern int guild_locations[][CLASS_COUNT + 1];
extern int spl_table[TOTALLVLS][MAX_CIRCLE];
extern int hometown[];
extern struct str_app_type str_app[];
extern struct con_app_type con_app[];
extern struct time_info_data time_info;
extern struct wis_app_type wis_app[];
extern struct zone_data *zone_table;
extern struct sector_data *sector_table;
extern const char *undead_type[];
extern const int numCarvables;
extern const char *carve_part_name[];
extern const struct race_names race_names_table[];
extern const int carve_part_flag[];
extern struct mm_ds *dead_mob_pool;
extern struct mm_ds *dead_pconly_pool;

extern int cast_as_damage_area(P_char, void (*func)(int, P_char, char *, int, P_char, P_obj), int,
			       P_char, float, float);

extern bool exit_wallable(int room, int dir, P_char ch);
extern bool create_walls(int room, int exit, P_char ch, int level, int type, int power, int decay,
			 const char *short_desc, const char *desc, ulong flags);
extern bool has_skin_spell(P_char);

/* Let's do some spells yah! */

// How many shadows, swarms or dragons one caster keeps.
static int illusion_pet_limit(P_char ch)
{
	return MAX(1, GET_LEVEL(ch) / 14);
}

// How many ticks a summoned illusion stays under control.
static int illusion_pet_control()
{
	return 1;
}

// A pet's dice as a fight rolls them: dice() clamps both numbers to at least 1.
static std::string illusion_pet_dice(int count, int size)
{
	return std::to_string(std::max(count, 1)) + "d" + std::to_string(std::max(size, 1));
}

static std::string illusion_pet_control_facts()
{
	return fact("It serves you for", game_hours(illusion_pet_control())) +
	       "  A globe of shadows or unholy alliance makes that permanent.\n";
}

static int phantom_armor_duration()
{
	return 15;
}

static int phantom_armor_ac(int level)
{
	return -(level);
}

std::string phantom_armor_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Armor class", std::to_string(phantom_armor_ac(level)) + " at your level, " +
					   std::to_string(level)) +
	       fact("Duration", game_hours(phantom_armor_duration())) +
	       "  Recasting it only renews the duration.\n"
	       "  It does nothing to a target with another armor-type spell.\n";
}

void spell_phantom_armor(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			 P_char victim, P_obj /*obj*/)
{
	named_set_ordinary_cast ordinary_cast(victim, SPELL_PHANTOM_ARMOR);
	struct affected_type af;
	bool shown;

	if (!(victim && ch))
	{
		logit(LOG_EXIT, "assert: bogus parms");
		return;
	}

	if (!IS_AFFECTED(victim, AFF_ARMOR))
	{
		bzero(&af, sizeof(af));
		af.type = SPELL_PHANTOM_ARMOR;
		af.duration = phantom_armor_duration();
		af.modifier = phantom_armor_ac(level);
		af.bitvector = AFF_ARMOR;
		af.location = APPLY_AC;
		affect_to_char(victim, &af);
		send_to_char("&+LShadowy &+Wphantoms&N blur your image to the outside!\r\n",
			     victim);
	}
	else
	{
		struct affected_type *af1;

		shown = FALSE;
		for (af1 = victim->affected; af1; af1 = af1->next)
		{
			if (af1->type == SPELL_PHANTOM_ARMOR)
			{
				shown = TRUE;
				send_to_char(
					"&+LShadowy &+Wphantoms&N blur your image to the outside!\r\n",
					victim);
				af1->duration = phantom_armor_duration();
				break;
			}
		}
		if (!shown)
		{
			send_to_char("&+WYou're already affected by an armor-type spell.&n\n",
				     victim);
		}
	}
}

static int shadow_monster_level(const Rolls &rolls, int level)
{
	return BOUNDED(1, rolls.number(level - 5, level + 1), 55);
}

static int shadow_monster_hit_points(const Rolls &rolls, int mob_level)
{
	return rolls.dice(mob_level, 3) + (mob_level * 2);
}

static int shadow_monster_hitroll(P_char ch)
{
	return GET_LEVEL(ch);
}

static int shadow_monster_damroll(P_char ch)
{
	return GET_LEVEL(ch) / 2;
}

static int shadow_monster_dice_count(P_char ch)
{
	return (int)GET_LEVEL(ch) / 5;
}

static int shadow_monster_dice_size(P_char ch)
{
	return (int)GET_LEVEL(ch) / 6;
}

std::string shadow_monster_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range mob = { shadow_monster_level(lowest_rolls, level),
			    shadow_monster_level(highest_rolls, level) };
	return fact("Shadows at once",
		    std::to_string(GET_CLASS(ch, CLASS_ILLUSIONIST) ? illusion_pet_limit(ch) : 1) +
			    " at your level, " + std::to_string(level)) +
	       fact("Shadow's level", show(mob)) +
	       fact("Its hit points",
		    show({ shadow_monster_hit_points(lowest_rolls, mob.low),
			   shadow_monster_hit_points(highest_rolls, mob.high) })) +
	       fact("Its hitroll", std::to_string(shadow_monster_hitroll(ch))) +
	       fact("Its damroll", std::to_string(shadow_monster_damroll(ch))) +
	       fact("Its damage dice", illusion_pet_dice(shadow_monster_dice_count(ch),
							 shadow_monster_dice_size(ch))) +
	       illusion_pet_control_facts() +
	       "  It attacks your target at once. Safe rooms block it.\n";
}

void spell_shadow_monster(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			  P_char victim, P_obj /*obj*/)
{
	P_char mob;
	int summoned = 0;
	struct char_link_data *cld;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return;
	}

	if (CHAR_IN_SAFE_ROOM(ch))
	{
		send_to_char("A mysterious force blocks your conjuring!\r\n", ch);
		return;
	}

	for (cld = ch->linked; cld; cld = cld->next_linked)
	{
		if (cld->type == LNK_PET && IS_NPC(cld->linking) && GET_VNUM(cld->linking) == 1106)
		{
			summoned++;
		}
	}

	// Non-illusionists get a limit of 1 (for weapon procs etc).
	if (summoned >= illusion_pet_limit(ch) || (summoned && !GET_CLASS(ch, CLASS_ILLUSIONIST)))
	{
		send_to_char("You cannot summon any more shadows!\r\n", ch);
		return;
	}

	mob = read_mobile(real_mobile(1106), REAL);
	if (!mob)
	{
		logit(LOG_DEBUG, "spell_shadow_monster(): mob %d not loadable", 1106);
		send_to_char("Bug in shadow monster.  Tell a god!\r\n", ch);
		return;
	}

	char_to_room(mob, ch->in_room, 0);
	act("$n &+wappears from nowhere!", TRUE, mob, 0, 0, TO_ROOM);

	mob->player.level = shadow_monster_level(live_rolls, level);

	mob->player.m_class = 0;
	remove_plushit_bits(mob);

	GET_MAX_HIT(mob) = GET_HIT(mob) = mob->points.base_hit =
		shadow_monster_hit_points(live_rolls, GET_LEVEL(mob));

	setup_pet(mob, ch, illusion_pet_control(), PET_NOORDER | PET_NOCASH);

	GET_EXP(mob) = 0;
	mob->points.base_hitroll = mob->points.hitroll = shadow_monster_hitroll(ch);
	mob->points.base_damroll = mob->points.damroll = shadow_monster_damroll(ch);
	mob->points.damnodice = shadow_monster_dice_count(ch);
	mob->points.damsizedice = shadow_monster_dice_size(ch);

	group_add_member(ch, mob);
	MobStartFight(mob, victim);
}

static int insects_level(const Rolls &rolls, int level)
{
	return MIN(30, MAX(1, rolls.number(level - 7, level - 2)));
}

static int insects_hit_points(const Rolls &rolls, int mob_level, int ch_level)
{
	return rolls.dice(mob_level, 3) + (ch_level);
}

// A swarm gains blur and flurry when its caster is above these levels.
static int insects_blur_above()
{
	return 31;
}

static int insects_flurry_above()
{
	return 50;
}

static int insects_hitroll(P_char ch)
{
	return GET_LEVEL(ch);
}

static int insects_damroll(P_char ch)
{
	return (int)(GET_LEVEL(ch) / 3);
}

static int insects_dice_count(P_char ch)
{
	return (int)(GET_LEVEL(ch) / 8);
}

static int insects_dice_size(P_char ch)
{
	return (int)(GET_LEVEL(ch) / 9);
}

std::string insects_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range mob = { insects_level(lowest_rolls, level),
			    insects_level(highest_rolls, level) };
	return fact("Swarms at once", std::to_string(illusion_pet_limit(ch)) + " at your level, " +
					      std::to_string(level)) +
	       (GET_CLASS(ch, CLASS_ILLUSIONIST) ?
			"  A cast summons until you have that many.\n" :
			"  A cast summons one, as you are no illusionist.\n") +
	       fact("Swarm's level", show(mob)) +
	       fact("Its hit points",
		    show({ insects_hit_points(lowest_rolls, mob.low, level),
			   insects_hit_points(highest_rolls, mob.high, level) })) +
	       fact("Its hitroll", std::to_string(insects_hitroll(ch))) +
	       fact("Its damroll", std::to_string(insects_damroll(ch))) +
	       fact("Its damage dice",
		    illusion_pet_dice(insects_dice_count(ch), insects_dice_size(ch))) +
	       "  It is hasted.\n" +
	       fact("It has blur",
		    "if you are above level " + std::to_string(insects_blur_above())) +
	       fact("It has flurry",
		    "if you are above level " + std::to_string(insects_flurry_above())) +
	       illusion_pet_control_facts() +
	       "  It attacks your target at once. Safe rooms block it.\n";
}

void spell_insects(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type, P_char victim,
		   P_obj /*obj*/)
{
	P_char mob;
	int summoned, i;
	struct char_link_data *cld;

	if (!ch || !victim)
	{
		return;
	}

	if (CHAR_IN_SAFE_ROOM(ch))
	{
		send_to_char("A mysterious force blocks your conjuring!\r\n", ch);
		return;
	}

	summoned = 0;

	for (cld = ch->linked; cld; cld = cld->next_linked)
	{
		if (cld->type == LNK_PET && IS_NPC(cld->linking) && GET_VNUM(cld->linking) == 1107)
		{
			summoned++;
		}
	}

	for (i = illusion_pet_limit(ch); i > summoned; i--)
	{
		mob = read_mobile(real_mobile(1107), REAL);

		if (!mob)
		{
			logit(LOG_DEBUG, "spell_insects(): mob %d not loadable", 1107);
			send_to_char("Bug in insects.  Tell a god!\r\n", ch);
			return;
		}

		char_to_room(mob, ch->in_room, 0);
		act("$n &+Lappears from nowhere!", TRUE, mob, 0, 0, TO_ROOM);

		mob->player.level = insects_level(live_rolls, level);

		SET_BIT(mob->specials.affected_by, AFF_HASTE);
		SET_BIT(mob->specials.act, ACT_SPEC_DIE);

		if (GET_LEVEL(ch) > insects_blur_above())
		{
			SET_BIT(mob->specials.affected_by3, AFF3_BLUR);
		}
		if (GET_LEVEL(ch) > insects_flurry_above())
		{
			SET_BIT(mob->specials.affected_by2, AFF2_FLURRY);
		}

		mob->player.m_class = 0;
		remove_plushit_bits(mob);
		GET_MAX_HIT(mob) = GET_HIT(mob) = mob->points.base_hit =
			insects_hit_points(live_rolls, GET_LEVEL(mob), GET_LEVEL(ch));

		GET_EXP(mob) = 0;
		mob->points.base_hitroll = mob->points.hitroll = insects_hitroll(ch);
		mob->points.base_damroll = mob->points.damroll = insects_damroll(ch);
		mob->points.damnodice = insects_dice_count(ch);
		mob->points.damsizedice = insects_dice_size(ch);

		setup_pet(mob, ch, illusion_pet_control(), PET_NOORDER | PET_NOCASH);
		group_add_member(ch, mob);
		MobStartFight(mob, victim);

		if (!GET_CLASS(ch, CLASS_ILLUSIONIST))
			return;
	}
}

static int boulder_damage(const Rolls &rolls, int level)
{
	return rolls.dice(2 * level, 8);
}

static int boulder_saved(int dam)
{
	dam >>= 1;
	return dam;
}

// A roll of 0 knocks the target down.
static int boulder_knockdown_roll(const Rolls &rolls)
{
	return rolls.number(0, 9);
}

static int boulder_knockdown_lag()
{
	return (int)(PULSE_VIOLENCE * 0.5);
}

std::string boulder_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const int low = boulder_damage(lowest_rolls, level);
	const int high = boulder_damage(highest_rolls, level);
	return fact("Damage", show({ low, high }) + " at your level, " + std::to_string(level)) +
	       fact("If the target saves", show({ boulder_saved(low), boulder_saved(high) })) +
	       "  A major globe stops it; minor globes and spirit wards do not.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n" +
	       fact("Chance it knocks down a standing survivor",
		    "1 in " + std::to_string(boulder_knockdown_roll(highest_rolls) -
					     boulder_knockdown_roll(lowest_rolls) + 1)) +
	       fact("Lag on the target knocked down", seconds(boulder_knockdown_lag())) +
	       "  Elites and greater races do not fall.\n";
}

void spell_boulder(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim, P_obj /*obj*/)
{
	int dam;
	struct damage_messages messages = {
		"Your huge &+Willusional boulder&n hits $N causing $M to scream out in agony!",
		"A huge &+Wboulder&n created by $n&n hits you causing you to scream out in agony!",
		"A huge &+Wboulder&n created by $n&n hits $N causing $M to scream out in agony!",
		"Your &+Willusional boulder&n rolls into $N's body, killing $M instantly!",
		"$n&n's giant &+Wboulder&N is the last thing you ever see.",
		"$n&n's &+Wboulder&N rolls into $N flattening $M!",
		0
	};

	if (!(victim && ch))
	{
		logit(LOG_EXIT, "Damm boulders it's messed up!");
		return;
	}

	dam = boulder_damage(live_rolls, level);
	int mod = get_default_save_mod(victim, ch, SAVING_SPELL, SPELL_BOULDER);
	if (NewSaves(victim, SAVING_SPELL, mod))
		dam = boulder_saved(dam);

	if (spell_damage(ch, victim, dam, SPLDAM_GENERIC, SPLDAM_GLOBE, &messages) != DAM_NONEDEAD)
		return;

	if (!IS_AFFECTED2(victim, AFF2_GLOBE) && (GET_POS(victim) == POS_STANDING) &&
	    !IS_ELITE(victim) && !IS_GREATER_RACE(victim))
	{
		if (!boulder_knockdown_roll(live_rolls))
		{
			act("&+LYour &+Wboulder&n &+Lhit's $N dead on, knocking $M to the ground!&n",
			    0, ch, 0, victim, TO_CHAR);
			act("$N is knocked to the ground as $n's &+Wboulder hit's $M dead on!&n", 0,
			    ch, 0, victim, TO_NOTVICT);
			act("$n's &+Wboulder hit's dead on knocking you to the ground!&n", 0, ch, 0,
			    victim, TO_VICT);
			SET_POS(victim, POS_SITTING + GET_STAT(victim));
			CharWait(victim, boulder_knockdown_lag());
		}
	}
}

// The caster's lag, in pulses, whether or not it works.
static int shadow_travel_dreamer_lag()
{
	return 4;
}

static int shadow_travel_pc_lag()
{
	return 36;
}

static int shadow_travel_distance(int level)
{
	return (int)(level * get_property("spell.dim.perlevel.modifier", 1.35));
}

static int shadow_travel_dreamer_distance()
{
	return 15;
}

// A roll of 0 leaves one onlooker unaware of the caster going or coming.
static int shadow_travel_unseen_roll(const Rolls &rolls)
{
	return rolls.number(0, 5);
}

std::string shadow_travel_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const bool dreamer = GET_SPEC(ch, CLASS_ILLUSIONIST, SPEC_DARK_DREAMER);
	const int distance =
		shadow_travel_distance(level) + (dreamer ? shadow_travel_dreamer_distance() : 0);
	return (IS_TRUSTED(ch) ?
			fact("Range", "any, as an immortal") :
			fact("Range", std::to_string(distance) +
					      " rooms by exits, either way, at your level, " +
					      std::to_string(level))) +
	       fact("Your lag",
		    seconds(dreamer ? shadow_travel_dreamer_lag() : shadow_travel_pc_lag()) +
			    ", even if it fails") +
	       fact("Chance each onlooker misses you going or coming",
		    "1 in " + std::to_string(shadow_travel_unseen_roll(highest_rolls) -
					     shadow_travel_unseen_roll(lowest_rolls) + 1)) +
	       "  Non-detection, and no-locate players you do not know, hide a target.\n" +
	       (IS_TRUSTED(ch) ? "" : "  So does a mount with a rider.\n") +
	       "  A follower cannot reach a player.\n"
	       "  No-teleport rooms, hometowns and castles block it, as does ocean around\n"
	       "  you and the other racewar side. You, and a player target, must be raidable.\n";
}

void spell_shadow_travel(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			 P_obj /*obj*/)
{
	int location;
	char buf[256] = { 0 };
	P_char tmp = NULL;
	int distance;

	if (!ch)
	{
		logit(LOG_EXIT, "assert: bogus parms");
		return;
	}

	if (GET_SPEC(ch, CLASS_ILLUSIONIST, SPEC_DARK_DREAMER))
		CharWait(ch, shadow_travel_dreamer_lag());
	else if (IS_PC(ch))
		CharWait(ch, shadow_travel_pc_lag());
	else
		CharWait(ch, 5);

	if (!victim)
	{
		send_to_char("&+yYou failed.\r\n", ch);
		return;
	}

	if (IS_AFFECTED3(victim, AFF3_NON_DETECTION))
	{
		send_to_char("&+yYou failed.\r\n", ch);
		return;
	}

	if (IS_ROOM(ch->in_room, ROOM_NO_TELEPORT) ||
	    world[ch->in_room].sector_type == SECT_OCEAN || IS_HOMETOWN(ch->in_room))
	{
		send_to_char("&+yYou failed.\r\n", ch);
		return;
	}

	if (IS_PC(victim) && IS_SET(victim->specials.act2, PLR2_NOLOCATE) && !is_introd(victim, ch))
	{
		send_to_char("&+yYou failed.\r\n", ch);
		return;
	}

	location = victim->in_room;

	if (IS_ROOM(location, ROOM_NO_TELEPORT) || IS_HOMETOWN(location) ||
	    world[location].sector_type == SECT_CASTLE ||
	    world[location].sector_type == SECT_CASTLE_GATE ||
	    world[location].sector_type == SECT_CASTLE_WALL || racewar(ch, victim) ||
	    (GET_MASTER(ch) && IS_PC(victim)))
	{
		send_to_char("&+yYou failed.\r\n", ch);
		return;
	}
	P_char rider = get_linking_char(victim, LNK_RIDING);
	if (IS_NPC(victim) && rider && !IS_TRUSTED(ch))
	{
		send_to_char("&+yYou failed.\n", ch);
		return;
	}

	distance = shadow_travel_distance(level);
	if (GET_SPEC(ch, CLASS_ILLUSIONIST, SPEC_DARK_DREAMER))
		distance += shadow_travel_dreamer_distance();

	if (!IS_TRUSTED(ch) && how_close(ch->in_room, victim->in_room, distance) < 0 &&
	    how_close(victim->in_room, ch->in_room, distance) < 0)
	{
		send_to_char("&+yYou failed.\r\n", ch);
		return;
	}

	if (ch && !is_Raidable(ch, 0, 0))
	{
		send_to_char("&+WYou are not raidable. The spell fails!\r\n", ch);
		return;
	}

	if (victim && IS_PC(ch) && IS_PC(victim) && !is_Raidable(victim, 0, 0))
	{
		send_to_char("&+WYour target is not raidable. The spell fails!\r\n", ch);
		return;
	}

	for (tmp = world[ch->in_room].people; tmp; tmp = tmp->next_in_room)
	{
		if ((IS_AFFECTED(tmp, AFF_BLIND) || (tmp->specials.z_cord != ch->specials.z_cord) ||
		     (tmp == ch) || !shadow_travel_unseen_roll(live_rolls)) &&
		    (IS_PC(ch) && !IS_TRUSTED(ch)))
			continue;
		if (CAN_SEE(tmp, ch))
			act("&+L$n appears to become one with the shadows and silently starts to move away.",
			    FALSE, ch, 0, tmp, TO_VICT);
		else
			act("&+LAn odd looking shadow forms and silently starts to move away.",
			    FALSE, ch, 0, tmp, TO_VICT);
		send_to_char(buf, tmp);
	}

	char_from_room(ch);
	char_to_room(ch, location, -1);

	for (tmp = world[ch->in_room].people; tmp; tmp = tmp->next_in_room)
	{
		if ((IS_AFFECTED(tmp, AFF_BLIND) || (tmp == ch) ||
		     !shadow_travel_unseen_roll(live_rolls)) &&
		    (IS_PC(ch) && !IS_TRUSTED(ch)))
			continue;
		if (CAN_SEE(tmp, ch))
			act("&+LAn odd looking shadow silently arrives and slowly forms into $n.",
			    FALSE, ch, 0, tmp, TO_VICT);
		else
			act("&+LAn odd looking shadow silently arrives then vanishes.", FALSE, ch,
			    0, tmp, TO_VICT);
		send_to_char(buf, tmp);
	}
}

static int stunning_visions_percent(const Rolls &rolls, int level)
{
	return level + rolls.number(-10, 10);
}

static int stunning_visions_power_bonus(int power_gap)
{
	return (int)(power_gap * .8);
}

// The stun each score band gives, in pulses; a score under the last band gives none.
static int stunning_visions_deep_above()
{
	return 90;
}

static int stunning_visions_deep_stun()
{
	return PULSE_VIOLENCE * 2;
}

static int stunning_visions_trance_above()
{
	return 60;
}

static int stunning_visions_trance_stun()
{
	return PULSE_VIOLENCE;
}

static int stunning_visions_mesmerize_above()
{
	return 40;
}

static int stunning_visions_mesmerize_stun()
{
	return PULSE_VIOLENCE / 2;
}

static int stunning_visions_slight_from()
{
	return 25;
}

static int stunning_visions_slight_stun()
{
	return PULSE_VIOLENCE / 4;
}

std::string stunning_visions_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Score", show_signed({ stunning_visions_percent(lowest_rolls, level),
					   stunning_visions_percent(highest_rolls, level) }) +
				     " at your level, " + std::to_string(level)) +
	       "  It halves if you make your own spell save, and doubles on a player's pet.\n"
	       "  Your level minus the target's adds to it.\n" +
	       fact("Every 10 power you have over the target adds",
		    std::to_string(stunning_visions_power_bonus(10))) +
	       fact("Stun at a score over " + std::to_string(stunning_visions_deep_above()),
		    seconds(stunning_visions_deep_stun())) +
	       fact("Over " + std::to_string(stunning_visions_trance_above()),
		    seconds(stunning_visions_trance_stun())) +
	       fact("Over " + std::to_string(stunning_visions_mesmerize_above()),
		    seconds(stunning_visions_mesmerize_stun())) +
	       fact("At " + std::to_string(stunning_visions_slight_from()) + " or more",
		    seconds(stunning_visions_slight_stun())) +
	       "  A lower score does nothing. Fear saves do not apply.\n"
	       "  A stun stops your fight and the target's.\n"
	       "  Zombies, golems, plants, greater races and immortals are immune.\n"
	       "  Elites cannot be stunned, and the target's magic resistance can shrug it.\n"
	       "  It does nothing to a target already stunned, or down and lagged, unless\n"
	       "  it is bashed or you sprang at it.\n";
}

void spell_stunning_visions(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			    P_obj /*obj*/)
{
	int percent = stunning_visions_percent(live_rolls, level);

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim) || GET_HIT(victim) < 1 || IS_TRUSTED(victim) ||
	    IS_ZOMBIE(victim) || GET_RACE(victim) == RACE_GOLEM || GET_RACE(victim) == RACE_PLANT ||
	    IS_GREATER_RACE(victim))
	{
		send_to_char("&+rYour target is immune!\r\n", ch);
		return;
	}

	if (resists_spell(ch, victim))
	{
		return;
	}

	if (IS_STUNNED(victim))
	{
		send_to_char("Your target is already stunned!\r\n", ch);
		return;
	}

	// If they're bashed/tripped/etc no stun until they at least come out of the lag.
	//   Allow stun if they failed bash, or springleap.
	if (GET_POS(victim) != POS_STANDING && IS_ACT2(victim, PLR2_WAIT) &&
	    !(affected_by_spell(victim, SKILL_BASH) || affected_by_spell(ch, SKILL_SPRINGLEAP)))
	{
		act("&+Y$N&+Y seems to be preoccupied at the moment.&n\r\n", FALSE, ch, 0, victim,
		    TO_CHAR);
		return;
	}

	int mod = get_default_save_mod(victim, ch, SAVING_SPELL, SPELL_STUNNING_VISIONS);
	if (NewSaves(victim, SAVING_SPELL, mod))
	{
		percent /= 2;
	}

	if (IS_PC_PET(victim))
	{
		percent *= 2;
	}

	percent += (level - GET_LEVEL(victim));

	// percent += (GET_C_POW(ch) - GET_C_POW(victim)) / 3;
	percent += stunning_visions_power_bonus(GET_C_POW(ch) - GET_C_POW(victim));

	act("&+cYou send a wave of incredible visions toward&n $N.", FALSE, ch, 0, victim, TO_CHAR);

	if (percent < 11)
	{
		act("$n &+ctries to mesmerize you with some stunning visions, but fails miserably!\r\n",
		    FALSE, ch, 0, victim, TO_VICT);
		act("&+cYour visions fail to impress your foe...", FALSE, ch, 0, victim, TO_CHAR);
		return;
	}

	if (percent > stunning_visions_deep_above())
	{
		act("&+cYour wave of visions seems to completely entrance&n $N!", FALSE, ch, 0,
		    victim, TO_CHAR);
		act("$n's &+cstunning visions seem to completely entrance&n $N!", FALSE, ch, 0,
		    victim, TO_NOTVICT);
		act("$n &+ccauses visions to dance before your eyes, causing you to fall in a deep trance!&n.",
		    FALSE, ch, 0, victim, TO_VICT);

		if (IS_FIGHTING(victim))
		{
			stop_fighting(victim);
		}

		stop_fighting(ch);
		Stun(victim, ch, stunning_visions_deep_stun(), FALSE);
		return;
	}
	else if (percent > stunning_visions_trance_above())
	{
		act("&+cYour wave of visions seems to entrance&n $N!", FALSE, ch, 0, victim,
		    TO_CHAR);
		act("$n's &+Cstunning visions seem to entrance&n $N!", FALSE, ch, 0, victim,
		    TO_NOTVICT);
		act("$n &+ccauses visions to dance before your eyes, causing you to fall into a trance!&n.",
		    FALSE, ch, 0, victim, TO_VICT);

		if (IS_FIGHTING(victim))
		{
			stop_fighting(victim);
		}

		stop_fighting(ch);
		Stun(victim, ch, stunning_visions_trance_stun(), FALSE);
		return;
	}
	else if (percent > stunning_visions_mesmerize_above())
	{
		act("&+cYour wave of visions seems to mesmerize&n $N!", FALSE, ch, 0, victim,
		    TO_CHAR);
		act("$n's &+cstunning visions seem to mesmerize&n $N!", FALSE, ch, 0, victim,
		    TO_NOTVICT);
		act("$n &+ccauses visions to dance before your eyes mesmerizing you!&n.", FALSE, ch,
		    0, victim, TO_VICT);

		if (IS_FIGHTING(victim))
		{
			stop_fighting(victim);
		}

		stop_fighting(ch);
		Stun(victim, ch, stunning_visions_mesmerize_stun(), FALSE);
		return;
	}
	else if (percent >= stunning_visions_slight_from())
	{
		act("&+cYour wave of visions seems to slightly mesmerize&n $N!", FALSE, ch, 0,
		    victim, TO_CHAR);
		act("$n's &+cstunning visions seem to slightly mesmerize&n $N!", FALSE, ch, 0,
		    victim, TO_NOTVICT);
		act("$n &+ccauses visions to dance before your eyes, bewildering you!&n.", FALSE,
		    ch, 0, victim, TO_VICT);

		if (IS_FIGHTING(victim))
		{
			stop_fighting(victim);
		}

		stop_fighting(ch);
		Stun(victim, ch, stunning_visions_slight_stun(), FALSE);
		return;
	}
}

static int reflection_images(int level)
{
	return BOUNDED(1, (level - 26) / 5, 4);
}

static int reflection_image_hit_points(const Rolls &rolls, int level)
{
	return level * 4 + rolls.number(0, 50);
}

static int reflection_image_control()
{
	return 3;
}

std::string reflection_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Images", std::to_string(reflection_images(level)) + " at your level, " +
				      std::to_string(level)) +
	       fact("Each image's hit points",
		    show({ reflection_image_hit_points(lowest_rolls, level),
			   reflection_image_hit_points(highest_rolls, level) })) +
	       fact("They serve you for", game_hours(reflection_image_control())) +
	       "  A globe of shadows or unholy alliance makes that permanent.\n"
	       "  Those fighting the target turn on one image.\n"
	       "  Recasting replaces your images and the target's.\n"
	       "  It cannot target an NPC, and not while you have a titan illusion.\n";
}

void spell_reflection(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
		      P_char victim, P_obj /*obj*/)
{
	P_char image, tch, tch2;
	struct char_link_data *cld;
	char Gbuf1[MAX_STRING_LENGTH];
	int numb, i, spot, room, targ;
	struct follow_type *k, *p, *l, *q;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (IS_NPC(victim) && (IS_PC(ch) || IS_PC_PET(ch)))
	{
		send_to_char("You cannot cast this spell on NPCs.\r\n", ch);
		return;
	}

	for (cld = ch->linked; cld; cld = cld->next_linked)
	{
		if (cld->type == LNK_PET && IS_NPC(cld->linking) &&
		    GET_VNUM(cld->linking) == TITAN_NUMBER)
		{
			send_to_char("&+LBut you cant support so many different illusions!&n\r\n",
				     ch);
			return;
		}
	}

	for (k = ch->followers; k; k = p)
	{
		tch = k->follower;
		p = k->next;

		if (tch && IS_NPC(tch) && GET_VNUM(tch) == 250)
		{
			stop_fighting(tch);
			StopAllAttackers(tch);
			extract_char(tch);
		}
	}

	if (ch != victim)
	{
		for (l = victim->followers; l; l = q)
		{
			tch2 = l->follower;
			q = l->next;

			if (tch2 && IS_NPC(tch2) && GET_VNUM(tch2) == 250)
			{
				stop_fighting(tch2);
				StopAllAttackers(tch2);
				extract_char(tch2);
			}
		}
	}

	numb = reflection_images(level);

	// make reflection always disengage target
	spot = number(0, numb - 1);
	targ = number(0, numb - 1);
	while (targ == spot)
	{
		spot = number(0, numb);
	}

	act("&+L$n &+Cs&+Bs&+bs&+Cp&+Bp&+b&+Cl&+Bl&+bl&+Ci&+Bi&+bi&+Ct&+Bt&+bt&+Cs&+Bs&+bs&+L into many images!&N",
	    FALSE, victim, 0, 0, TO_ROOM);
	send_to_char(
		"&+LYou &+Cs&+Bs&+bs&+Cp&+Bp&+b&+Cl&+Bl&+bl&+Ci&+Bi&+bi&+Ct&+Bt&+bt&+Cs&+Bs&+bs&+L into many images!&N\r\n",
		victim);

	logit(LOG_DEBUG, "REFLECTION: (%s) casting on (%s).", GET_NAME(ch), GET_NAME(victim));

	for (i = 0; i < numb; i++)
	{
		image = read_mobile(real_mobile(250), REAL);

		if (!image)
		{
			send_to_char(
				"Your mirror ain't imaging tonight bubba.  Let a god know.\r\n",
				victim);
			return;
		}
		if (!image->only.npc)
		{
			logit(LOG_DEBUG, "Error reading image for %s.", GET_NAME(ch));
			send_to_char("Error reading image mob, let a god know.\r\n", ch);
			extract_char(image);
			return;
		}

		if (spot == i)
		{
			room = victim->in_room;
			char_from_room(victim);
			char_to_room(victim, room, -2);
		}

		char_to_room(image, victim->in_room, 0);

		if (!IS_ALIVE(image))
		{
			continue;
		}

		image->points.base_hit = GET_MAX_HIT(image) = GET_HIT(image) =
			reflection_image_hit_points(live_rolls, level);

		while (image->affected)
		{
			affect_remove(image, image->affected);
		}

		if (!IS_SET(image->specials.act, ACT_MEMORY))
		{
			clearMemory(image);
		}

		SET_BIT(image->specials.affected_by, AFF_DETECT_INVISIBLE);

		balance_affects(image);

		setup_pet(image, ch, reflection_image_control(), PET_NOCASH);

		add_follower(image, ch);

		/* string it */

		snprintf(Gbuf1, MAX_STRING_LENGTH, "image %s %s", GET_NAME(victim),
			 race_names_table[GET_RACE(victim)].normal);

		if (IS_SET(image->only.npc->str_mask, STRUNG_KEYS))
		{
			str_free(image->player.name);
			REMOVE_BIT(image->only.npc->str_mask, STRUNG_KEYS);
		}
		image->player.name = str_dup(Gbuf1);
		image->player.short_descr = str_dup(victim->player.name);

		snprintf(Gbuf1, MAX_STRING_LENGTH, "%s stands here.\r\n", victim->player.name);

		image->player.long_descr = str_dup(Gbuf1);
		SET_BIT(image->only.npc->str_mask, STRUNG_KEYS | STRUNG_DESC1 | STRUNG_DESC2);

		if (GET_TITLE(victim))
		{
			image->player.title = str_dup(GET_TITLE(victim));
		}

		GET_RACE(image) = GET_RACE(victim);
		GET_RACEWAR(image) = GET_RACEWAR(victim);
		GET_SEX(image) = GET_SEX(victim);
		GET_ALIGNMENT(image) = GET_ALIGNMENT(victim);
		GET_SIZE(image) = GET_SIZE(victim);
		// Make them ugly so they work for blocking.
		GET_C_CHA(image) = 1;

		remove_plushit_bits(image);

		if (targ == i && targ != spot)
		{
			for (tch = world[victim->in_room].people; tch; tch = tch->next_in_room)
			{
				if (IS_FIGHTING(tch))
				{
					if (GET_OPPONENT(tch) == victim)
					{
						stop_fighting(tch);
						stop_fighting(victim);
						set_fighting(tch, image);

						if (!IS_FIGHTING(image))
						{
							set_fighting(image, tch);
						}
					}
				}
			}
		}
	}
}

// Fading back to your own image lags you, in pulses.
static int illusion_fade_lag()
{
	return PULSE_VIOLENCE * 3;
}

// How much damage and time a mask or clone takes before it falls.
static int illusion_disguise_hits(P_char ch)
{
	return GET_LEVEL(ch) * 2;
}

// A mortal cannot copy anyone above this level.
static int illusion_copy_highest_level()
{
	return 56;
}

static int mask_size_lag()
{
	return PULSE_VIOLENCE;
}

std::string mask_facts(P_char ch)
{
	return fact("Disguise strength",
		    std::to_string(illusion_disguise_hits(ch)) + ", worn down by damage and time") +
	       fact("Your lag fading back with \"me\" or \"self\"", seconds(illusion_fade_lag())) +
	       (IS_TRUSTED(ch) ?
			fact("Highest level you can copy", "your own, as an immortal") :
			fact("Your lag if over one size off the target", seconds(mask_size_lag())) +
				fact("Highest level you can copy",
				     std::to_string(illusion_copy_highest_level()))) +
	       "  It only copies players, by name. You must be disguised to fade back.\n";
}

/* Masks ch as target, a loaded character (null when there is none), or back as itself. */
static void mask_as(P_char ch, P_char target, bool casting_on_self)
{
	char tbuf[MAX_STRING_LENGTH];

	if ((target && IS_PC(target) && GET_PID(target) == GET_PID(ch)) || casting_on_self)
	{
		if (!is_illusion_char(ch))
		{
			send_to_char("&+LSeems like you're already yourself...&N\r\n", ch);
			if (target)
				free_char(target);
			return;
		}
		else
		{
			send_to_char("&+WYou f&Nad&+Le back into your own image.&N\r\n", ch);
			act("&+W$n &+Wf&Nad&+Les back into $s &+Lown image.&N", FALSE, ch, 0, ch,
			    TO_ROOM);
			CharWait(ch, illusion_fade_lag());
			remove_disguise(ch, FALSE);
			if (target)
				free_char(target);
			return;
		}
	}

	if (!target)
	{
		send_to_char("&+LEven you are not that creative!&N\r\n", ch);
		return;
	}

	if (!IS_TRUSTED(ch) && target && GET_LEVEL(target) > illusion_copy_highest_level())
	{
		send_to_char(
			"&+LYou don't know what the divine look like to make their illusions.&N\r\n",
			ch);
		if (target)
			free_char(target);
		return;
	}
	if (IS_TRUSTED(ch))
	{
		if (GET_LEVEL(ch) < GET_LEVEL(target))
		{
			send_to_char("No you don't!\r\n", ch);
			if (target)
				free_char(target);
			return;
		}
	}

	if (target)
	{
		if ((GET_ALT_SIZE(ch) < (GET_ALT_SIZE(target) - 1)) && !IS_TRUSTED(ch))
		{
			send_to_char("You're too small for that!\r\n", ch);
			CharWait(ch, mask_size_lag());
		}
		else if ((GET_ALT_SIZE(ch) > (GET_ALT_SIZE(target) + 1)) && !IS_TRUSTED(ch))
		{
			send_to_char("You're too big for that!\r\n", ch);
			CharWait(ch, mask_size_lag());
		}
		else
		{
			if (target)
			{
				if (is_illusion_char(ch))
					remove_disguise(ch, FALSE);
				IS_DISGUISE_PC(ch) = TRUE;
				IS_DISGUISE_ILLUSION(ch) = TRUE;
				IS_DISGUISE_SHAPE(ch) = FALSE;
				ch->disguise.name = str_dup(GET_NAME(target));
				ch->disguise.m_class = target->player.m_class;
				ch->disguise.race = GET_RACE(target);
				ch->disguise.level = GET_LEVEL(target);
				ch->disguise.hit = illusion_disguise_hits(ch);
				ch->disguise.racewar = GET_RACEWAR(target);
				if (GET_TITLE(target))
					ch->disguise.title = str_dup(GET_TITLE(target));
				snprintf(
					tbuf, MAX_STRING_LENGTH,
					"&+LYour image shifts and &+bb&+Blur&+bs&+L into %s!&N\r\n",
					target->player.name);
				send_to_char(tbuf, ch);
				snprintf(
					tbuf, MAX_STRING_LENGTH,
					"&+LThe image of %s &+Lshifts and &+bb&+Blur&+bs&+L into %s&+L!&N\r\n",
					GET_NAME(ch), GET_NAME(target));
				act(tbuf, FALSE, ch, 0, NULL, TO_ROOM);
			}
		}
	}

	if (target)
		free_char(target);

	return;
}

void spell_mask([[maybe_unused]] int level, P_char ch, char *arg, int /*type*/, P_char /*victim*/,
		P_obj /*tar_obj*/)
{
	if (IS_NPC(ch))
		return;

	if (isname(arg, "me") || isname(arg, "self"))
	{
		mask_as(ch, NULL, TRUE);
		return;
	}
	player_load_offline_for(ch, arg, false, [](P_char caster, P_char target)
				{ mask_as(caster, target, FALSE); });
}

// How long a watching or illusionary wall lasts, in pulses.
static int illusion_wall_decay()
{
	return 1800;
}

static int watching_wall_strength(int level)
{
	return level;
}

// wall_generic rolls this when someone acts by the wall; a roll of 0 shows the caster.
int watching_wall_vision_roll(const Rolls &rolls)
{
	return rolls.number(0, 2);
}

// More than this many seconds pass between two such rolls.
int watching_wall_vision_gap()
{
	return 10;
}

std::string watching_wall_facts(P_char ch)
{
	extern int wall_climb_roll(const Rolls &rolls);
	extern int wall_climb_above();
	extern int wall_hit_lag();
	const int level = GET_LEVEL(ch);
	return fact("Wall lasts", real_time(illusion_wall_decay())) +
	       fact("Strength", std::to_string(watching_wall_strength(level)) + " at your level, " +
					std::to_string(level)) +
	       fact("Chance someone acting by it shows you the room",
		    "1 in " + std::to_string(watching_wall_vision_roll(highest_rolls) -
					     watching_wall_vision_roll(lowest_rolls) + 1)) +
	       fact("Seconds between those chances",
		    "more than " + std::to_string(watching_wall_vision_gap())) +
	       "  You must be elsewhere and in the game. Immortals show you nothing.\n"
	       "  Hits wear it down by the hitter's damroll and level, and hurt the hitter.\n"
	       "  Your own hit breaks it.\n" +
	       fact("A hitter's lag", seconds(wall_hit_lag())) +
	       fact("Wall climbers get over it",
		    std::to_string(wall_climb_roll(highest_rolls) - wall_climb_above()) + "%") +
	       "  Doors, blocked, secret, one-way and walled exits cannot take a wall, and\n"
	       "  some rooms disperse the magic. You cannot cast it disguised in a town.\n";
}

void spell_watching_wall(int level, P_char ch, char *arg, int /*type*/, P_char /*tar_ch*/,
			 P_obj /*tar_obj*/)
{
	char buf1[MAX_STRING_LENGTH], buf2[MAX_STRING_LENGTH], Gbuf4[MAX_STRING_LENGTH];
	int var = 0;

	one_argument(arg, Gbuf4);
	var = dir_from_keyword(Gbuf4);

	if (!exit_wallable(ch->in_room, var, ch))
	{
		return;
	}

	if (CHAR_IN_TOWN(ch) && IS_DISGUISE_ILLUSION(ch))
	{
		send_to_char("You cannot create any walls when disguised in any town!\r\n", ch);
		return;
	}

	if (create_walls(ch->in_room, var, ch, level, WATCHING_WALL, watching_wall_strength(level),
			 illusion_wall_decay(),
			 "&+La greyish stone wall covered with hundreds of eyes&n",
			 "&+yA massive stone wall embedded with eyes is here to the %s.&n", 0))
	{
		SET_BIT(EXIT(ch, var)->exit_info, EX_BREAKABLE);
		SET_BIT(VIRTUAL_EXIT((world[ch->in_room].dir_option[var])->to_room, rev_dir[var])
				->exit_info,
			EX_BREAKABLE);
		snprintf(buf1, MAX_STRING_LENGTH,
			 "&+yA massive eye-covered stone wall appears to the %s!&n\r\n", dirs[var]);
		snprintf(buf2, MAX_STRING_LENGTH,
			 "&+yA massive eye-covered stone wall appears to the %s!&n\r\n",
			 dirs[rev_dir[var]]);

		send_to_room(buf1, ch->in_room);
		send_to_room(buf2, (world[ch->in_room].dir_option[var])->to_room);
	}
}

// wall_generic rolls this as someone walks into the wall; a roll of 0 finds it out.
int illusionary_wall_block_roll(const Rolls &rolls)
{
	return rolls.number(0, 5);
}

std::string illusionary_wall_facts(P_char /*ch*/)
{
	return fact("Wall lasts", real_time(illusion_wall_decay())) +
	       fact("Chance a walker into it finds it out and passes",
		    "1 in " + std::to_string(illusionary_wall_block_roll(highest_rolls) -
					     illusionary_wall_block_roll(lowest_rolls) + 1)) +
	       "  It hides the exit. Once found, the next walker blows it away.\n"
	       "  Doors, blocked, secret, one-way and walled exits cannot take a wall, and\n"
	       "  some rooms disperse the magic. You cannot cast it disguised in a town.\n";
}

void spell_illusionary_wall(int level, P_char ch, char *arg, int /*type*/, P_char /*victim*/,
			    P_obj /*obj*/)
{
	char buf1[MAX_STRING_LENGTH], buf2[MAX_STRING_LENGTH], Gbuf4[MAX_STRING_LENGTH];
	int var = 0;

	one_argument(arg, Gbuf4);
	var = dir_from_keyword(Gbuf4);

	if (!exit_wallable(ch->in_room, var, ch))
	{
		return;
	}

	if (CHAR_IN_TOWN(ch) && IS_DISGUISE_ILLUSION(ch))
	{
		send_to_char("You cannot create any walls when disguised in any town!\r\n", ch);
		return;
	}

	if (create_walls(ch->in_room, var, ch, level, ILLUSIONARY_WALL, level,
			 illusion_wall_decay(), "&+wan illusionary wall&n",
			 "&+LAn &Nil&+Wlusiona&Nry&+L wall is here to the %s.&n", ITEM_SECRET))
	{
		snprintf(buf1, MAX_STRING_LENGTH, "&+LThe exit to the %s disappears!&n\r\n",
			 dirs[var]);
		snprintf(buf2, MAX_STRING_LENGTH, "&+LThe exit to the %s disappears!&n\r\n",
			 dirs[rev_dir[var]]);

		send_to_room(buf1, ch->in_room);
		send_to_room(buf2, (world[ch->in_room].dir_option[var])->to_room);
		SET_BIT(EXIT(ch, var)->exit_info, EX_ILLUSION);
		SET_BIT(VIRTUAL_EXIT((world[ch->in_room].dir_option[var])->to_room, rev_dir[var])
				->exit_info,
			EX_ILLUSION);
	}
}

void spell_nightmare(int /*level*/, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		     P_obj /*obj*/)
{
	if (!(victim && ch))
	{
		logit(LOG_EXIT, "assert: bogus parms");
		return;
	}

	if (affected_by_spell(victim, SKILL_BERSERK) || resists_spell(ch, victim))
		return;

	if (IS_DEMON(victim) || IS_DRAGON(victim) || IS_TRUSTED(victim))
	{
		act("How can you give $N nightmares? Nothing scares $M!", FALSE, ch, 0, victim,
		    TO_CHAR);

		return;
	}

	if (GET_STAT(ch) == STAT_DEAD)
		return;

	if (!saves_spell(victim, SAVING_SPELL))
	{
		switch (GET_RACE(victim))
		{
		case RACE_TROLL:
			act("You show $N a nightmare of $M taking a bath!", FALSE, ch, 0, victim,
			    TO_CHAR);
			act("A wave of painful terror overcomes you as $n shows you a nightmare of you taking a bath!",
			    FALSE, ch, 0, victim, TO_VICT);
			act("$n shows $N! his worst nightmare!", FALSE, ch, 0, victim, TO_NOTVICT);
			break;
		case RACE_HUMAN:
			act("You show $N a nightmare of an ogre sitting on $S face!", FALSE, ch, 0,
			    victim, TO_CHAR);
			act("A wave of painful terror overcomes you as $n shows you a nightmare of an ogre sitting on your face!",
			    FALSE, ch, 0, victim, TO_VICT);
			act("$n shows $N! his worst nightmare!", FALSE, ch, 0, victim, TO_NOTVICT);
			break;
		case RACE_MOUNTAIN:
		case RACE_DUERGAR:
			act("You show $N a nightmare of $M getting $S beard cut off!", FALSE, ch, 0,
			    victim, TO_CHAR);
			act("A wave of painful terror overcomes you as $n shows you a nightmare with you getting your beard cut off!",
			    FALSE, ch, 0, victim, TO_VICT);
			act("$n shows $N! his worst nightmare!", FALSE, ch, 0, victim, TO_NOTVICT);
			break;
		case RACE_HALFLING:
			act("You show $N a nightmare of $M getting $S hand caught in a cookie jar!",
			    FALSE, ch, 0, victim, TO_CHAR);
			act("A wave of painful terror overcomes you as $n shows you a nightmare with you getting your hand caught in a cookie jar!",
			    FALSE, ch, 0, victim, TO_VICT);
			act("$n shows $N! his worst nightmare!", FALSE, ch, 0, victim, TO_NOTVICT);
			break;
		case RACE_OGRE:
			act("You show $N a nightmare of a little white mouse.", FALSE, ch, 0,
			    victim, TO_CHAR);
			act("A wave of painful terror overcomes you as $n shows you a nightmare of a little white mouse jumping in front of you!",
			    FALSE, ch, 0, victim, TO_VICT);
			act("$n shows $N! his worst nightmare!", FALSE, ch, 0, victim, TO_NOTVICT);
			break;
		case RACE_THRIKREEN:
			act("You show $N a nightmare of $M getting stuffed into a freezer.", FALSE,
			    ch, 0, victim, TO_CHAR);
			act("A wave of painful terror overcomes you as $n shows you a nightmare of you getting stuffed into a freezer!",
			    FALSE, ch, 0, victim, TO_VICT);
			act("$n shows $N! his worst nightmare!", FALSE, ch, 0, victim, TO_NOTVICT);
			break;
		case RACE_CENTAUR:
			act("You show $N a nightmare of a old lady storm giant trying to ride $M.",
			    FALSE, ch, 0, victim, TO_CHAR);
			act("A wave of painful terror overcomes you as $n shows you a nightmare of a old lady storm giant trying to mount you!",
			    FALSE, ch, 0, victim, TO_VICT);
			act("$n shows $N! his worst nightmare!", FALSE, ch, 0, victim, TO_NOTVICT);
			break;
		case RACE_MINOTAUR:
			act("You show $N a nightmare of $M getting killed by a bull fighter!",
			    FALSE, ch, 0, victim, TO_CHAR);
			act("A wave of painful terror overcomes you as $n shows you a nightmare of you getting killed by a bull fighter!",
			    FALSE, ch, 0, victim, TO_VICT);
			act("$n shows $N! his worst nightmare!", FALSE, ch, 0, victim, TO_NOTVICT);
			break;
		case RACE_GOBLIN:
		case RACE_GNOME:
			act("You show $N a nightmare of $M getting stepped upon by a giant foot!",
			    FALSE, ch, 0, victim, TO_CHAR);
			act("A wave of painful terror overcomes you as $n shows you a nightmare with you getting stepped on!",
			    FALSE, ch, 0, victim, TO_VICT);
			act("$n shows $N! his worst nightmare!", FALSE, ch, 0, victim, TO_NOTVICT);
			break;
		case RACE_LICH:
		case RACE_PVAMPIRE:
			act("You show $N a nightmare of $M getting stabbed by a wooden stake through the heart!",
			    FALSE, ch, 0, victim, TO_CHAR);
			act("A wave of painful terror overcomes you as $n shows you a nightmare of you getting stabbed through the heart by a wooden stake!",
			    FALSE, ch, 0, victim, TO_VICT);
			act("$n shows $N! his worst nightmare!", FALSE, ch, 0, victim, TO_NOTVICT);
			break;
		default:
			act("You show $N a horror filled nightmare!", FALSE, ch, 0, victim,
			    TO_CHAR);
			act("A wave of painful terror overcomes you as $n shows you a horrible nightmare!",
			    FALSE, ch, 0, victim, TO_VICT);
			act("$n shows $N! his worst nightmare!", FALSE, ch, 0, victim, TO_NOTVICT);
			break;
		}

		/*
		    temp = MIN(35, level);
		    dam = dice(2 * temp, 3);
		    dam = dam * DAMFACTOR;

		    damage(ch, victim, dam, SPELL_NIGHTMARE);

		    if (char_in_list(victim) && !courage_check(victim))
		      do_flee(victim, 0, 2);
		*/
		if (char_in_list(victim) && !fear_check(victim))
			do_flee(victim, 0, 2);
	}
	else
	{
		act("$N doesn't look frightened of $n's nightmares.. $E DOES look pissed off though.",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$N looks pissed at $n for some reason.", TRUE, ch, 0, victim, TO_NOTVICT);
		act("$n's nightmares do not impress you.", TRUE, ch, 0, victim, TO_VICT);
	}
	if (ch->in_room == victim->in_room)
	{
		if (IS_NPC(victim) && CAN_SEE(victim, ch))
		{
			remember(victim, ch);
			if (!IS_FIGHTING(victim))
				MobStartFight(victim, ch);
		}
	}
}

static int shadow_shield_absorb(const Rolls &rolls, int level)
{
	return (level / 6) + rolls.number(1, 4);
}

static int shadow_shield_duration()
{
	return 4;
}

// Shadow shield's facts when cast at `level`, which `at` names.
static std::string shadow_shield_facts_at(int level, const std::string &at, const std::string &who)
{
	extern int skin_spell_deduct();
	extern float stone_skin_melee_share();
	return fact("Hits absorbed", show({ shadow_shield_absorb(lowest_rolls, level),
					    shadow_shield_absorb(highest_rolls, level) }) +
					     at) +
	       fact("Each melee hit on " + who, std::to_string(skin_spell_deduct()) + " less") +
	       fact("Then, if over 10 is left",
		    share_percent(stone_skin_melee_share()) + " of that") +
	       "  It applies before the raw damage modifiers.\n"
	       "  Hits that ignore reductions go through it and use up nothing.\n"
	       "  An attacker's fist of dragon can do the same.\n" +
	       fact("Duration", game_hours(shadow_shield_duration())) +
	       "  It does nothing to a target with any skin spell.\n";
}

std::string shadow_shield_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return shadow_shield_facts_at(level, " at your level, " + std::to_string(level), "you");
}

void spell_shadow_shield(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			 P_char victim, P_obj /*obj*/)
{
	named_set_ordinary_cast ordinary_cast(victim, SPELL_SHADOW_SHIELD);
	struct affected_type af;
	int absorb = shadow_shield_absorb(live_rolls, level);

	if (!has_skin_spell(victim))
	{
		act("&+LShadows start to swirl around and cover&n $n's &+Lskin.&n", TRUE, victim, 0,
		    0, TO_ROOM);
		act("&+LYou feel a strange shadowy mist cover your body.&n", TRUE, victim, 0, 0,
		    TO_CHAR);
	}
	else
	{
		send_to_char("Their body is already covered with a magic shell!\r\n", ch);
		return;
	}

	bzero(&af, sizeof(af));
	af.type = SPELL_SHADOW_SHIELD;
	af.duration = shadow_shield_duration();
	af.modifier = absorb;
	affect_to_char(victim, &af);
}

static int vanish_duration(int level)
{
	return level / 2;
}

std::string vanish_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Invisibility", game_hours(vanish_duration(level)) + " at your level, " +
					    std::to_string(level)) +
	       "  Recasting it, or invisibility, only renews the duration.\n"
	       "  It also hides you, except in water or on the ocean.\n";
}

void spell_vanish(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type, P_char victim,
		  P_obj obj)
{
	struct affected_type af;

	if (!((victim || obj) && ch))
	{
		logit(LOG_EXIT, "assert: bogus parms");
		return;
	}
	if (!affected_by_spell(victim, SPELL_INVISIBILITY))
	{
		act("&+L$n instantly vanishes out of existence.", TRUE, victim, 0, 0, TO_ROOM);
		send_to_char("&+LYou completely vanish.\r\n", victim);

		bzero(&af, sizeof(af));

		af.type = SPELL_INVISIBILITY;
		af.duration = vanish_duration(level);
		af.bitvector = AFF_INVISIBLE;
		affect_to_char(victim, &af);
	}
	else
	{
		struct affected_type *af1;

		for (af1 = victim->affected; af1; af1 = af1->next)
			if (af1->type == SPELL_INVISIBILITY)
			{
				af1->duration = vanish_duration(level);
			}
	}

	if (IS_WATER_ROOM(ch->in_room) || world[ch->in_room].sector_type == SECT_OCEAN)
	{
		send_to_char("It's far too wet to vanish and hide behind anything...\r\n", ch);
	}
	else
		SET_BIT(ch->specials.affected_by, AFF_HIDE);
}

// Immortals cast it at this level at most.
static int hammer_level(int level, P_char ch)
{
	if (level > 56 && IS_PC(ch))
	{
		level = 56;
	}
	return level;
}

static int hammer_damage(const Rolls &rolls, int level)
{
	return 9 * level + rolls.number(-25, 25);
}

static int hammer_saved(int dam)
{
	return (dam * 2) / 3;
}

// A deceiver's roll of 0 stuns.
static int hammer_stun_roll(const Rolls &rolls)
{
	return rolls.number(0, 19);
}

static int hammer_stun()
{
	return PULSE_VIOLENCE;
}

std::string hammer_facts(P_char ch)
{
	const int level = hammer_level(GET_LEVEL(ch), ch);
	const int low = hammer_damage(lowest_rolls, level);
	const int high = hammer_damage(highest_rolls, level);
	std::string text =
		fact("Damage", show_landing({ low, high }) + " at your level, " +
				       std::to_string(GET_LEVEL(ch))) +
		fact("If the target saves",
		     show_landing({ hammer_saved(low), hammer_saved(high) })) +
		"  Magic resistance can shrug it first; damage cannot then be shrugged.\n"
		"  Globes and spirit wards do not stop it.\n"
		"  Spell damage modifiers and the target's defenses apply after.\n";
	if (GET_SPEC(ch, CLASS_ILLUSIONIST, SPEC_DECEIVER))
		text += fact("Chance to stun if the target survives",
			     "1 in " + std::to_string(hammer_stun_roll(highest_rolls) -
						      hammer_stun_roll(lowest_rolls) + 1)) +
			fact("Stun", seconds(hammer_stun()) + "; fear saves shorten or stop it") +
			"  A target with deflect stuns you instead, with no fear save.\n"
			"  Elites cannot be stunned. Greater races, plants, golems and constructs\n"
			"  may resist.\n";
	return text;
}

void spell_hammer(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim, P_obj /*obj*/)
{
	struct damage_messages messages = {
		"Your massive &+Bhammer&N causes $N to double over in pain!",
		"$n creates a &+Bhammer&N out of thin air that smashes into you!",
		"$n creates a &+Bhammer&N out of thin air that smashes into $N, bits of &+yflesh&n and &+Wbone&n fly everywhere!",
		"Your &+Billusional hammer&N smashes into $N's body, killing $M instantly!",
		"$n's massive &+Bhammer&N is the last thing you ever see.",
		"$n's &+Bhammer&N strikes $N smashing $M into the ground!"
	};
	int dam;
	bool stunself = false;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return;
	}

	if (resists_spell(ch, victim))
	{
		return;
	}

	if (affected_by_spell(victim, SPELL_DEFLECT) || IS_AFFECTED4(victim, AFF4_DEFLECT))
	{
		stunself = 1;
	}

	// Imms casting hammer lvl reduced to 56 for testing.
	level = hammer_level(level, ch);
	dam = hammer_damage(live_rolls, level);

	// Adding a save for this since 115 damage for 7th circle is absurd.
	//  This brings 115 down to 76, which is normal non-sorc 7th circle damage.
	int mod = get_default_save_mod(victim, ch, SAVING_SPELL, SPELL_HAMMER);
	if (NewSaves(victim, SAVING_SPELL, mod))
	{
		dam = hammer_saved(dam);
	}

	if (spell_damage(ch, victim, dam, SPLDAM_GENERIC, SPLDAM_NOSHRUG, &messages) !=
	    DAM_NONEDEAD)
	{
		return;
	}

	if (GET_SPEC(ch, CLASS_ILLUSIONIST, SPEC_DECEIVER))
	{
		if (!hammer_stun_roll(live_rolls))
		{
			if (stunself)
				Stun(ch, ch, hammer_stun(), FALSE);
			else
				Stun(victim, ch, hammer_stun(), TRUE);
		}
	}
}

static int detect_illusion_duration(int level)
{
	return MAX(level, 10);
}

std::string detect_illusion_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Duration", game_hours(detect_illusion_duration(level)) + " at your level, " +
					std::to_string(level)) +
	       "  It also detects invisibility. Recasting it only renews the duration.\n";
}

void spell_detect_illusion(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			   P_char victim, P_obj /*obj*/)
{
	named_set_ordinary_cast ordinary_cast(victim, SPELL_DETECT_ILLUSION);
	struct affected_type af;

	if (!((level >= 0) && victim && ch))
	{
		logit(LOG_EXIT, "assert: bogus parms");
		return;
	}

	if (IS_AFFECTED4(victim, AFF4_DETECT_ILLUSION))
	{
		struct affected_type *af1;

		for (af1 = victim->affected; af1; af1 = af1->next)
			if (af1->type == SPELL_DETECT_ILLUSION)
			{
				af1->duration = detect_illusion_duration(level);
			}
		return;
	}

	bzero(&af, sizeof(af));
	af.type = SPELL_DETECT_ILLUSION;
	af.duration = detect_illusion_duration(level);
	af.bitvector = AFF_DETECT_INVISIBLE;
	af.bitvector4 = AFF4_DETECT_ILLUSION;
	affect_to_char(victim, &af);

	send_to_char("&+WYour vision feels enhanced!\r\n", victim);
}

// The caster's lag, in pulses, whether or not it works.
static int dream_travel_dreamer_lag(const Rolls &rolls)
{
	return rolls.number(4 * WAIT_SEC, 6 * WAIT_SEC);
}

static int dream_travel_pc_lag()
{
	return 12 * WAIT_SEC;
}

// What each group member brought to the caster is lagged, in pulses.
static int dream_travel_dreamer_member_lag()
{
	return 6 * WAIT_SEC;
}

static int dream_travel_member_lag()
{
	return 12 * WAIT_SEC;
}

std::string dream_travel_facts(P_char ch)
{
	const bool dreamer = GET_SPEC(ch, CLASS_ILLUSIONIST, SPEC_DARK_DREAMER);
	const int low = dream_travel_dreamer_lag(lowest_rolls);
	const int high = dream_travel_dreamer_lag(highest_rolls);
	return fact("Your lag", (dreamer ? seconds(low) + " to " + seconds(high) :
					   seconds(dream_travel_pc_lag())) +
					", even if it fails") +
	       "  Cast on another player, it takes you there, asleep.\n"
	       "  Cast on yourself, it brings your group to you, asleep: NPCs and players\n"
	       "  who consent and whom you can see, unless they are fighting.\n" +
	       (IS_TRUSTED(ch) ? "" : "  Group members in no-teleport rooms or hometowns stay.\n") +
	       fact("Each one's lag", seconds(dreamer ? dream_travel_dreamer_member_lag() :
							dream_travel_member_lag())) +
	       (IS_TRUSTED(ch) ?
			"" :
			"  It cannot reach an NPC, the other racewar side or an immortal,\n"
			"  and single-file rooms block it.\n") +
	       "  Non-detection, and no-locate players you do not know, hide a target.\n"
	       "  No-teleport rooms, hometowns and rooms you cannot enter block it, as do\n"
	       "  ocean around the target, and flying or swimming. Both must be raidable.\n";
}

void spell_dream_travel(int /*level*/, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			P_obj /*obj*/)
{
	int location;
	P_char targ, mount;
	struct group_list *group;

	if (!IS_ALIVE(ch) || ch->in_room < 0)
	{
		return;
	}

	if (GET_SPEC(ch, CLASS_ILLUSIONIST, SPEC_DARK_DREAMER))
		CharWait(ch, dream_travel_dreamer_lag(live_rolls));
	else if (IS_PC(ch))
		CharWait(ch, dream_travel_pc_lag());
	else
		CharWait(ch, 5 * WAIT_SEC);

	if (!can_relocate_to(ch, victim))
	{
		return;
	}

	if (victim == ch)
	{
		location = ch->in_room;

		for (group = ch->group; group; group = group->next)
		{
			targ = group->ch;

			if (IS_ALIVE(targ) && CAN_SEE(ch, targ))
			{
				if (IS_NPC(targ) || is_linked_to(ch, targ, LNK_CONSENT))
				{
					if ((IS_ROOM(targ->in_room, ROOM_NO_TELEPORT) ||
					     IS_HOMETOWN(targ->in_room)) &&
					    !IS_TRUSTED(ch))
					{
						send_to_char(
							"You feel slightly sleepy, but shake it off.\r\n",
							ch);
						continue;
					}

					if (IS_FIGHTING(targ))
					{
						send_to_char(
							"You feel slightly drowsy, but it's too noisy to sleep!\r\n",
							targ);
						continue;
					}

					if ((mount = GET_MOUNT(targ)) != NULL)
					{
						act("You feel really tired, and fall off $N.",
						    FALSE, targ, 0, mount, TO_CHAR);
						stop_riding(targ);
					}

					act("&+LYou &+Wblink&+L and $n &+Lis gone! &+CIt was just a &+Wdream&+C; $e &+Cwas never here to begin with.&N",
					    FALSE, targ, 0, 0, TO_ROOM);

#if defined(CTF_MUD) && (CTF_MUD == 1)
					if (ctf_carrying_flag(targ) == CTF_PRIMARY)
					{
						send_to_char("You can't carry that with you.\r\n",
							     targ);
						drop_ctf_flag(targ);
					}
#endif

					send_to_char(
						"&+WTh&Ne &+Lworld becomes surreal, everything becomes a &Nblur&+L and you cannot tell\r\n",
						targ);
					send_to_char(
						"&+Lthe difference between reality and dreams.  You are &+Wflying&N, &+rc&+Ro&+Yl&+Wo&+Cr&+Bs&+b f&+Bl&+Co&+Ww p&Na&+Lst\r\n",
						targ);
					send_to_char(
						"&+Lyou like paint in a river.  Then, as if something &+wchanged&+L, you feel a sense of urgency\r\n",
						targ);
					send_to_char(
						"&+Las you begin &+Wfalling &+Lrapidly towards the ground below.  You close your eyes as the &+Gground\r\n",
						targ);
					send_to_char("&+Lrushes towards you...&n\r\n", targ);

					if (GET_STAT(targ) == STAT_SLEEPING)
						SET_POS(targ, GET_POS(targ) + STAT_NORMAL);
					send_to_char("&+WYou open your eyes and see:&N\r\n", targ);

					targ->specials.z_cord = ch->specials.z_cord;
					char_from_room(targ);
					char_to_room(targ, location, -1);
					if (GET_STAT(targ) > STAT_SLEEPING)
					{
						SET_POS(targ, GET_POS(targ) + STAT_SLEEPING);
					}
					send_to_char(
						"&+WAre you really here?  It must be a dream, you must be sleeping.&N\r\n",
						targ);
					act("$n falls asleep.", FALSE, targ, 0, 0, TO_ROOM);

					if (GET_SPEC(ch, CLASS_ILLUSIONIST, SPEC_DARK_DREAMER))
						CharWait(targ, dream_travel_dreamer_member_lag());
					else
						CharWait(targ, dream_travel_member_lag());
				}
			}
		}
	}
	else
	{
		location = victim->in_room;

#if defined(CTF_MUD) && (CTF_MUD == 1)
		if (ctf_carrying_flag(ch) == CTF_PRIMARY)
		{
			send_to_char("You can't carry that with you.\r\n", ch);
			drop_ctf_flag(ch);
		}
#endif

		act("&+LYou &+Wblink&+L and $n &+Lis gone! &+CIt was just a &+Wdream&+C, $e &+Cwas never here to begin with.&N",
		    FALSE, ch, 0, 0, TO_ROOM);
		act("&+LYou drift into the world of dreams...&N", FALSE, ch, 0, 0, TO_CHAR);

		char_from_room(ch);
		if (GET_STAT(ch) > STAT_SLEEPING && !IS_TRUSTED(ch))
		{
			SET_POS(ch, GET_POS(ch) + STAT_SLEEPING);
		}
		char_to_room(ch, location, -1);

		act("$n falls asleep.", FALSE, ch, 0, 0, TO_ROOM);
	}
}

/*
Help function to detect illusions one for
mobile/player illusions and one for object..
- Kvark
*/

int is_illusion_char(P_char ch)
{
	if (!ch)
		return 0;

	// Quick solution until we get a bit that i can look for.....
	if (IS_DISGUISE(ch) && IS_DISGUISE_ILLUSION(ch))
		return 1;

	// Check for images....add a struct if ya plan to have more mobs you want to detect..
	if (IS_NPC(ch))
		if (GET_VNUM(ch) == 250)
			return 1;

	// OK nothing found soo let's leave it as a false!
	return 0;
}

int is_illusion_obj(P_obj obj)
{
	if (!obj)
		return 0;

	// Check for illusionary wall.
	if (obj_index[obj->R_num].virtual_number == 759)
		return 1;

	return 0;

	// Add what ever might wanna go in here!
}

std::string clone_form_facts(P_char ch)
{
	return fact("Disguise strength",
		    std::to_string(illusion_disguise_hits(ch)) + ", worn down by damage and time") +
	       fact("Your lag fading back with \"me\" or \"self\"", seconds(illusion_fade_lag())) +
	       (IS_TRUSTED(ch) ?
			fact("Highest level you can copy", "your own, as an immortal") :
			fact("Highest level you can copy",
			     std::to_string(illusion_copy_highest_level())) +
				"  You cannot copy anything over one size smaller than you.\n") +
	       "  You cannot copy a reflection image, the training dummy, or yourself.\n"
	       "  You must be disguised to fade back.\n";
}

void spell_clone_form(int level, P_char ch, char *arg, int /*type*/, P_char victim, P_obj /*obj*/)
{
	bool casting_on_self = FALSE;
	P_char t_ch, tch, next_ch, target = NULL;
	char tbuf[MAX_STRING_LENGTH];

	if ((level < 0) || !IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		logit(LOG_EXIT, "assert: bogus parms");
		return;
	}

	if (IS_NPC(ch))
		return;

	if (!IS_ALIVE(ch))
		return;

	if (!IS_TRUSTED(ch) && GET_LEVEL(victim) > illusion_copy_highest_level())
	{
		send_to_char("&+LTry to find something that is a lower level to clone.&N\r\n", ch);
		return;
	}

	if (isname(arg, "me") || isname(arg, "self"))
	{
		casting_on_self = TRUE;
	}

	if (IS_NPC(victim) && victim != ch && GET_VNUM(victim) == 250)
	{
		send_to_char(
			"&+WYour magic is unable to duplicate the appearance of an illusion.&N\r\n",
			ch);
		return;
	}

	if (casting_on_self && is_illusion_char(ch))
	{
		send_to_char("&+WYou f&Nad&+Le back into your own image.&N\r\n", ch);
		act("&+W$n &+Wf&Nad&+Les back into $s &+Lown image.&N", FALSE, ch, 0, ch, TO_ROOM);
		CharWait(ch, illusion_fade_lag());
		remove_disguise(ch, FALSE);
		return;
	}

	target = victim;

	if (target == ch)
	{
		if (!IS_DISGUISE(ch))
		{
			send_to_char("&+LMaking you looking like yourself is beyond you.&N\r\n",
				     ch);
			return;
		}

		else
		{
			for (tch = world[ch->in_room].people; tch; tch = next_ch)
			{
				next_ch = tch->next_in_room;
				if ((tch != ch) && isname(arg, GET_NAME(tch)))
				{
					target = tch;
					break;
				}
			}
			if (target == ch)
			{
				send_to_char("&+LYou just tried to clone into yourself.&N\n\r", ch);
				send_to_char(
					"&+LTo avoid problems, use arguments \"me\" or \"self\" if you want to return to your normal form.&N\r\n",
					ch);
				return;
			}
		}
	}

	if (!training_dummy_clone_target_allowed(target))
	{
		send_to_char("The training dummy cannot be used as a clone form.\r\n", ch);
		return;
	}

	if (IS_NPC(target))
	{
		if ((GET_ALT_SIZE(ch) > (GET_ALT_SIZE(target) + 1)) && !IS_TRUSTED(ch))
		{
			send_to_char("You're too big to even imagine trying to look like that!\r\n",
				     ch);
		}
		else
		{
			if (is_illusion_char(ch))
				remove_disguise(ch, FALSE);
			t_ch = target;
			// Handle NPC Corpses
			IS_DISGUISE_PC(ch) = FALSE;
			IS_DISGUISE_NPC(ch) = TRUE;
			IS_DISGUISE_ILLUSION(ch) = TRUE;
			IS_DISGUISE_SHAPE(ch) = FALSE;
			ch->disguise.title = str_dup(GET_NAME(t_ch));
			ch->disguise.name = str_dup(t_ch->player.short_descr);
			ch->disguise.longname = str_dup(t_ch->player.long_descr);
			ch->disguise.m_class = t_ch->player.m_class;
			ch->disguise.racewar = GET_RACEWAR(target);
			ch->disguise.race = GET_RACE(t_ch);
			ch->disguise.hit = illusion_disguise_hits(ch);
			snprintf(tbuf, MAX_STRING_LENGTH,
				 "&+LYou &+Bblur&N and take on the form of %s!\r\n",
				 t_ch->player.short_descr);
			send_to_char(tbuf, ch);
			snprintf(tbuf, MAX_STRING_LENGTH,
				 " &+LThe image of %s &Ndisappears&+L, and is replaced by %s!\r\n",
				 GET_NAME(ch), t_ch->player.short_descr);
			act(tbuf, FALSE, ch, 0, NULL, TO_ROOM);
		}
	}
	else
	{
		if (!IS_TRUSTED(ch) && target && GET_LEVEL(target) > MAXLVLMORTAL)
		{
			send_to_char(
				"&+LYou don't know what the divine look like to make their illusions.&N\r\n",
				ch);
			return;
		}
		if (IS_TRUSTED(ch))
		{
			if (GET_LEVEL(ch) < GET_LEVEL(target))
			{
				send_to_char("No you don't!\r\n", ch);
				return;
			}
		}
		if (target)
		{
			if ((GET_ALT_SIZE(ch) > (GET_ALT_SIZE(target) + 1)) && !IS_TRUSTED(ch))
			{
				send_to_char(
					"You're too big to even think of making yourself look like that!\r\n",
					ch);
				return;
			}
			else
			{
				if (target)
				{
					if (is_illusion_char(ch))
						remove_disguise(ch, FALSE);
					IS_DISGUISE_NPC(ch) = FALSE;
					IS_DISGUISE_PC(ch) = TRUE;
					IS_DISGUISE_ILLUSION(ch) = TRUE;
					IS_DISGUISE_SHAPE(ch) = FALSE;
					ch->disguise.name = str_dup(GET_NAME(target));
					ch->disguise.m_class = target->player.m_class;
					ch->disguise.race = GET_RACE(target);
					ch->disguise.level = GET_LEVEL(target);
					ch->disguise.hit = illusion_disguise_hits(ch);
					ch->disguise.racewar = GET_RACEWAR(target);
					if (GET_TITLE(target))
						ch->disguise.title = str_dup(GET_TITLE(target));
					snprintf(
						tbuf, MAX_STRING_LENGTH,
						"&+LYour image shifts and &+bb&+Blur&+bs&+L into %s!&N\r\n",
						target->player.name);
					send_to_char(tbuf, ch);
					snprintf(
						tbuf, MAX_STRING_LENGTH,
						"&+LThe image of %s &+Lshifts and &+bb&+Blur&+bs&+L into %s&+L!&N\r\n",
						GET_NAME(ch), GET_NAME(target));
					act(tbuf, FALSE, ch, 0, NULL, TO_ROOM);
					return;
				}
			}
		}
	}
}

// A roll above 0 gives the target a first fear save, at this modifier.
static int imprison_first_save_roll(const Rolls &rolls)
{
	return rolls.number(0, 1);
}

static int imprison_first_save_mod()
{
	return 10;
}

static int imprison_shell_hit_points(int level)
{
	return 400 + MAX(0, MIN(level, 53) - 46) * 40;
}

static int imprison_second_save_mod()
{
	return 3;
}

static int imprison_saved_hit_points(int shell_hps)
{
	return (int)(shell_hps * 0.65);
}

std::string imprison_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const int shell = imprison_shell_hit_points(level);
	return fact("Chance of a first fear save that stops it",
		    "1 in " +
			    std::to_string(imprison_first_save_roll(highest_rolls) -
					   imprison_first_save_roll(lowest_rolls) + 1) +
			    ", at +" + std::to_string(imprison_first_save_mod()) + ", harder") +
	       fact("Shell's strength",
		    std::to_string(shell) + " at your level, " + std::to_string(level)) +
	       fact("If it makes a fear save at +" + std::to_string(imprison_second_save_mod()) +
			    ", harder",
		    std::to_string(imprison_saved_hit_points(shell))) +
	       "  The shell takes the damage meant for the target until a hit exceeds it.\n"
	       "  It stops the target's fights. It only takes a player not in a fight, not\n"
	       "  already imprisoned, and not you.\n";
}

void spell_imprison(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		    P_obj /*obj*/)
{
	char buf[1024];
	P_obj shell;
	int shell_hps;

	if (IS_NPC(victim))
	{
		return;
	}

	if (IS_FIGHTING(victim))
	{
		send_to_char("With this much commotion you can't seem to get a fix on them!\r\n",
			     ch);
		return;
	}

	if (victim == ch)
	{
		send_to_char(
			"&+CYou instantly disbelieve the illusion for what it really is...\r\n",
			ch);
		return;
	}

	for (shell = world[victim->in_room].contents; shell; shell = shell->next_content)
	{
		if (obj_index[shell->R_num].virtual_number == 1300)
		{
			if (shell->value[0] == GET_PID(victim))
			{
				break;
			}
		}
	}

	if (shell != NULL)
	{
		send_to_char(
			"This poor guy is already deeply convinced that they are imprisoned!\r\n",
			ch);
		return;
	}

	shell = read_object(1300, VIRTUAL);

	if (!shell)
	{
		send_to_char("Bug with imprisonment, report this immediately!\r\n", ch);
		return;
	}

	if (imprison_first_save_roll(live_rolls))
	{
		if (NewSaves(victim, SAVING_FEAR, imprison_first_save_mod()))
		{
			act("$N is almost encased in a $q, but $E believes it is just an illusion.",
			    TRUE, victim, shell, victim, TO_ROOM);
			act("$n tries to encase you in a $q, but you disbelieve it!", FALSE, ch,
			    shell, victim, TO_VICT);
			return;
		}
	}

	shell_hps = imprison_shell_hit_points(level);

	if (NewSaves(victim, SAVING_FEAR, imprison_second_save_mod()))
	{
		shell_hps = imprison_saved_hit_points(shell_hps);
		act("$N blinks in &+cdi&+Csb&+cel&+Cie&+cf &nas a $q &nencases $M!", TRUE, victim,
		    shell, victim, TO_ROOM);
		act("You blink in &+cdi&+Csb&+cel&+Cie&+cf &nas a $q &ncreated by $n wraps around you!",
		    FALSE, ch, shell, victim, TO_VICT);
	}
	else
	{
		act("$N freezes in &+ct&+Ce&+cr&+Cr&+co&+Cr &nas a $q &nencases $M!", TRUE, victim,
		    shell, victim, TO_ROOM);
		act("You freeze in &+ct&+Ce&+cr&+Cr&+co&+Cr &nas a $q &ncreated by $n wraps around you!",
		    FALSE, ch, shell, victim, TO_VICT);
	}

	stop_fighting(victim);
	StopAllAttackers(victim);
	SET_BIT(victim->specials.affected_by5, AFF5_IMPRISON);

	SET_BIT(shell->str_mask, STRUNG_DESC1);

	checked_substitute(buf, 1024, shell->description,
			   victim->player.short_descr ? victim->player.short_descr : "someone");

	shell->description = str_dup(buf);
	shell->value[0] = GET_PID(victim);
	shell->value[1] = shell_hps;
	obj_to_room(shell, ch->in_room);

	return;
}

/* called from raw_damage */
bool handle_imprison_damage(P_char ch, P_char victim, int dam)
{
	P_obj t_obj;

	for (t_obj = world[victim->in_room].contents; t_obj; t_obj = t_obj->next_content)
	{
		if (obj_index[t_obj->R_num].virtual_number == 1300)
		{
			if (t_obj->value[0] == GET_PID(victim))
			{
				break;
			}
		}
	}

	if (t_obj == NULL)
	{
		REMOVE_BIT(victim->specials.affected_by5, AFF5_IMPRISON);
		return FALSE;
	}

	if (GET_OPPONENT(ch) == victim)
	{
		stop_fighting(victim);
		stop_fighting(ch);
	}

	if (t_obj->value[1] < dam)
	{
		act("A $q encasing $N suddenly blurs and fades into nothing under $n's assault!",
		    TRUE, ch, t_obj, victim, TO_NOTVICT);
		act("A $q encasing $N suddenly blurs and fades into nothing under your assault!",
		    TRUE, ch, t_obj, victim, TO_CHAR);
		act("A $q encasing you suddenly blurs and fades into nothing under $n's assault!",
		    FALSE, ch, t_obj, victim, TO_VICT);
		REMOVE_BIT(victim->specials.affected_by5, AFF5_IMPRISON);
		extract_obj(t_obj, TRUE); // Not gonna be an arti.
		return TRUE;
	}

	t_obj->value[1] -= dam;
	act("A $q encasing $N flares brightly as it absorbs $n's assault!", TRUE, ch, t_obj, victim,
	    TO_NOTVICT);
	act("A $q encasing $N flares brightly as it absorbs your assault!", TRUE, ch, t_obj, victim,
	    TO_CHAR);
	act("A $q encasing you flares brightly as it absorbs $n's assault!", FALSE, ch, t_obj,
	    victim, TO_VICT);

	return TRUE;
}

std::string nonexistence_facts(P_char ch)
{
	return fact("Casts", "invisibility on everyone in the room, at your level") +
	       invisibility_facts(ch) + "  It also hides them, except in water or on the ocean.\n";
}

void spell_nonexistence(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			P_obj /*obj*/)
{
	if (!IS_ALIVE(ch))
	{
		return;
	}

	act("&+LYou shimmer in and out of view as the &+millusion&+L begins to cover you.", 0, ch,
	    0, victim, TO_CHAR);

	LOOP_THRU_PEOPLE(victim, ch)
	{
		act("&+L$N shimmers in and out of view as $n's &+millusion&+L starts to cover $M.",
		    0, ch, 0, victim, TO_NOTVICT);
		act("&+LYou shimmer in and out of existence as $n's &+millusion&+L starts to cover you.",
		    0, ch, 0, victim, TO_VICT);
		spell_invisibility(level, ch, 0, 0, victim, 0);
	}

	if (IS_WATER_ROOM(ch->in_room) || world[ch->in_room].sector_type == SECT_OCEAN)
	{
		send_to_char("It's far too wet here for hide to take hold...\r\n", ch);
	}
	else
	{
		LOOP_THRU_PEOPLE(victim, ch)
		{
			SET_BIT(victim->specials.affected_by, AFF_HIDE);
		}
	}
	/* Guess this was too much?
	for (obj = world[ch->in_room].contents; obj; obj = obj->next_content)
	{
	  if( IS_SET(obj->wear_flags, ITEM_TAKE) )
	    spell_invisibility(level, ch, 0, 0, 0, obj);
	}
	*/
}

static int dragon_level(const Rolls &rolls, int level)
{
	return BOUNDED(1, rolls.number(level - 5, level + 1), 55);
}

static int dragon_hit_points(const Rolls &rolls, int mob_level)
{
	return rolls.dice(mob_level, 5) + (mob_level * 4);
}

std::string dragon_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range mob = { dragon_level(lowest_rolls, level), dragon_level(highest_rolls, level) };
	return fact("Dragons at once", std::to_string(illusion_pet_limit(ch)) + " at your level, " +
					       std::to_string(level)) +
	       fact("Dragon's level", show(mob)) +
	       fact("Its hit points", show({ dragon_hit_points(lowest_rolls, mob.low),
					     dragon_hit_points(highest_rolls, mob.high) })) +
	       illusion_pet_control_facts() +
	       "  It attacks your target at once. Safe rooms block it.\n";
}

void spell_dragon(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type, P_char victim,
		  P_obj /*obj*/)
{
	P_char mob;
	int summoned;
	struct char_link_data *cld;

	if (!ch || !victim)
		return;

	if (CHAR_IN_SAFE_ROOM(ch))
	{
		send_to_char("A mysterious force blocks your casting!\r\n", ch);
		return;
	}

	for (summoned = 0, cld = ch->linked; cld; cld = cld->next_linked)
	{
		if (cld->type == LNK_PET && IS_NPC(cld->linking) &&
		    GET_VNUM(cld->linking) == VMOB_ILLUS_DRAGON)
		{
			summoned++;
		}
	}

	if (summoned >= illusion_pet_limit(ch))
	{
		send_to_char("You cannot summon any more dragons right now!\r\n", ch);
		return;
	}

	mob = read_mobile(real_mobile(VMOB_ILLUS_DRAGON), REAL);
	if (!mob)
	{
		logit(LOG_DEBUG, "spell_dragon(): mob %d not loadable", VMOB_ILLUS_DRAGON);
		send_to_char("Your dragon has a bug.  Tell a &+WGod&n before it spreads!\r\n", ch);
		return;
	}

	char_to_room(mob, ch->in_room, 0);
	act("$n &+wappears from nowhere!", TRUE, mob, 0, 0, TO_ROOM);

	mob->player.level = dragon_level(live_rolls, level);

	SET_BIT(mob->specials.affected_by, AFF_INFRAVISION);
	mob->player.m_class = CLASS_WARRIOR;
	mob->specials.act |= ACT_SPEC_DIE;
	remove_plushit_bits(mob);

	GET_MAX_HIT(mob) = GET_HIT(mob) = mob->points.base_hit =
		dragon_hit_points(live_rolls, GET_LEVEL(mob));

	balance_affects(mob);

	setup_pet(mob, ch, illusion_pet_control(), PET_NOORDER | PET_NOCASH);
	if (ch->group)
	{
		group_add_member(ch->group->ch, mob);
	}
	else
	{
		group_add_member(ch, mob);
	}
	MobStartFight(mob, victim);
}

static int titan_level(const Rolls &rolls, int level)
{
	return BOUNDED(1, rolls.number(level - 5, level), 55);
}

static int titan_hit_points(P_char ch)
{
	return (int)(GET_MAX_HIT(ch) * 0.7);
}

static int titan_hitroll(int mob_level)
{
	return mob_level / 2;
}

static int titan_damroll(int mob_level)
{
	return mob_level / 3;
}

static int titan_dice_count(P_char ch)
{
	return (int)GET_LEVEL(ch) / 6;
}

static int titan_dice_size(P_char ch)
{
	return (int)GET_LEVEL(ch) / 8;
}

std::string titan_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range mob = { titan_level(lowest_rolls, level), titan_level(highest_rolls, level) };
	return fact("Titan's level", show(mob) + " at your level, " + std::to_string(level)) +
	       fact("Its hit points",
		    std::to_string(titan_hit_points(ch)) + " with your maximum hit points") +
	       fact("Its hitroll", show({ titan_hitroll(mob.low), titan_hitroll(mob.high) })) +
	       fact("Its damroll", show({ titan_damroll(mob.low), titan_damroll(mob.high) })) +
	       fact("Its damage dice",
		    illusion_pet_dice(titan_dice_count(ch), titan_dice_size(ch))) +
	       illusion_pet_control_facts() +
	       "  It attacks your target at once. You can have only one, and none while\n"
	       "  your reflection images follow you. Safe rooms block it.\n";
}

void spell_titan(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type, P_char victim,
		 P_obj /*obj*/)
{
	struct follow_type *k;
	P_char mob;
	char Gbuf1[512];
	int summoned = 0;
	struct char_link_data *cld;

	if (!ch || !victim)
		return;

	if (IS_NPC(ch) && (GET_VNUM(ch) == TITAN_NUMBER))
	{
		send_to_char("&+LNope. Illusions can't own other illusions.\r\n", ch);
		return;
	}

	if (CHAR_IN_SAFE_ROOM(ch))
	{
		send_to_char("A mysterious force blocks your conjuring!\r\n", ch);
		return;
	}

	for (cld = ch->linked; cld; cld = cld->next_linked)
	{
		if (cld->type == LNK_PET && IS_NPC(cld->linking) &&
		    GET_VNUM(cld->linking) == TITAN_NUMBER)
		{
			summoned++;
		}
	}

	if (summoned)
	{
		send_to_char("&+BThere can be only &+Yone&+B!&n\r\n", ch);
		return;
	}

	for (k = ch->followers; k; k = k->next)
	{
		mob = k->follower;
		if (IS_NPC(mob) && GET_VNUM(mob) == 250)
		{
			send_to_char("&+LBut you cant support so many different illusions!&n\r\n",
				     ch);
			return;
		}
	}

	mob = read_mobile(real_mobile(TITAN_NUMBER), REAL);
	if (!mob)
	{
		logit(LOG_DEBUG, "spell_titan(): mob %d not loadable", TITAN_NUMBER);
		send_to_char("Bug in titan.  Tell a god!\r\n", ch);
		return;
	}

	mob->player.level = titan_level(live_rolls, level);
	SET_BIT(mob->specials.affected_by, AFF_INFRAVISION);
	SET_BIT(mob->specials.affected_by, AFF_DETECT_INVISIBLE);
	mob->player.m_class = CLASS_ILLUSIONIST;

	remove_plushit_bits(mob);

	GET_MAX_HIT(mob) = GET_HIT(mob) = mob->points.base_hit = titan_hit_points(ch);

	GET_SIZE(mob) = SIZE_GIANT;

	mob->points.base_hitroll = mob->points.hitroll = titan_hitroll(GET_LEVEL(mob));
	mob->points.base_damroll = mob->points.damroll = titan_damroll(GET_LEVEL(mob));
	mob->points.damnodice = titan_dice_count(ch);
	mob->points.damsizedice = titan_dice_size(ch);
	mob->specials.act |= ACT_SPEC_DIE;

	mob->only.npc->str_mask = (STRUNG_KEYS | STRUNG_DESC1 | STRUNG_DESC2);
	snprintf(Gbuf1, 512, "titan huge illusion %s %s", GET_NAME(ch),
		 race_names_table[GET_RACE(ch)].normal);
	mob->player.name = str_dup(Gbuf1);
	snprintf(Gbuf1, 512, "&+BA &+Yhuge&+B illusion of &+R%s&n", ch->player.name);
	mob->player.short_descr = str_dup(Gbuf1);
	snprintf(Gbuf1, 512, "&+BA &+Yhuge&+B illusion of &+R%s &+Bstands here.&n\r\n",
		 ch->player.name);
	mob->player.long_descr = str_dup(Gbuf1);

	if (GET_TITLE(ch))
		mob->player.title = str_dup(GET_TITLE(ch));

	GET_RACE(mob) = RACE_GIANT;
	GET_SEX(mob) = GET_SEX(ch);
	GET_ALIGNMENT(mob) = GET_ALIGNMENT(ch);

	char_to_room(mob, ch->in_room, 0);
	act("$n &+Lappears from nowhere!", TRUE, mob, 0, 0, TO_ROOM);

	setup_pet(mob, ch, illusion_pet_control(), PET_NOORDER | PET_NOCASH);
	group_add_member(ch, mob);
	MobStartFight(mob, victim);
}

static int delirium_works_above()
{
	return 10;
}

static int delirium_duration()
{
	return 40;
}

// Each step of a delirious walker rolls this; a roll of 0 sends it a random way.
int delirium_wander_roll(const Rolls &rolls)
{
	return rolls.number(0, 2);
}

std::string delirium_facts(P_char /*ch*/)
{
	return fact("Duration", seconds(delirium_duration())) +
	       fact("Chance each step goes a random way",
		    "1 in " + std::to_string(delirium_wander_roll(highest_rolls) -
					     delirium_wander_roll(lowest_rolls) + 1)) +
	       fact("It works if this is over " + std::to_string(delirium_works_above()),
		    "your power minus the target's") +
	       "    intelligence, plus its spell save modifier, plus your level advantage.\n"
	       "  Recasting it on a confused target does nothing. You cannot target yourself.\n";
}

void spell_delirium(int /*level*/, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
		    P_char victim, P_obj /*obj*/)
{
	struct affected_type af;
	int percent = 0;
	int save;

	save = victim->specials.apply_saving_throw[SAVING_SPELL];

	percent = BOUNDED(
		0, (GET_C_POW(ch) - GET_C_INT(victim) + save + (GET_LEVEL(ch) - GET_LEVEL(victim))),
		100);

	if (IS_NPC(ch))
	{
		act("It's confused enough!!&n", TRUE, ch, 0, victim, TO_CHAR);
		return;
	}

	if (ch == victim)
	{
		act("Can't really, I mean who am I, and who is what and when?!&n", TRUE, ch, 0,
		    victim, TO_CHAR);
		return;
	}

	act("$n sends a delirius ray streaking towards $N!", TRUE, ch, 0, victim, TO_NOTVICT);
	act("$n sends a delirius ray streaking YOU!", TRUE, ch, 0, victim, TO_VICT);
	act("You grin evilly as you send delirius ray streaking towards $N!", TRUE, ch, 0, victim,
	    TO_CHAR);

	if (percent > delirium_works_above())
	{
		// if (!saves_spell(victim, SAVING_SPELL) && (!number(0, 1))) {

		if (!affected_by_spell(victim, SPELL_DELIRIUM))
		{
			bzero(&af, sizeof(af));
			af.type = SPELL_DELIRIUM;
			af.flags = AFFTYPE_SHORT;
			af.duration = delirium_duration();
			af.bitvector5 = AFF5_DELIRIUM;
			affect_to_char(victim, &af);

			act("$N &+Wlooks a bit &+Gconfused!&n", TRUE, ch, 0, victim, TO_NOTVICT);
			act("&+WYou feel a bit &+Gconfused&n!", TRUE, ch, 0, victim, TO_VICT);
			act("$N &+Wlooks a bit &+Gconfused!&n", TRUE, ch, 0, victim, TO_CHAR);
		}
		else
		{
			act("It's confused enough!!&n", TRUE, ch, 0, victim, TO_CHAR);
		}
	}
}

static int flicker_shield_level(int level)
{
	return (level / 3) * 2;
}

std::string flicker_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return "  You need a group. It leaves the room in twilight.\n" +
	       fact("Casts", "shadow shield on your group here, at level " +
				     std::to_string(flicker_shield_level(level))) +
	       shadow_shield_facts_at(flicker_shield_level(level), "", "them");
}

void spell_flicker(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim, P_obj /*obj*/)
{
	struct group_list *gl;

	if (ch && ch->group)
	{
		act("&+L$n creates a sh&+cim&+Cme&+cri&+Lng orb of light, casting s&+mha&+Mdo&+mw&+Ls over the room!&n",
		    TRUE, ch, 0, victim, TO_NOTVICT);
		act("&+LYou create a sh&+cim&+Cme&+cri&+Lng orb of light, casting s&+mha&+Mdo&+mw&+Ls over the room!&n",
		    TRUE, ch, 0, victim, TO_CHAR);

		act("&+LThe room is blanketed in da&+mnci&+Mng sh&+mado&+Lws.&n", 0, ch, 0, 0,
		    TO_ROOM);
		act("&+LThe room is blanketed in da&+mnci&+Mng sh&+mado&+Lws.&n", 0, ch, 0, 0,
		    TO_CHAR);
		SET_BIT(world[ch->in_room].room_flags, ROOM_TWILIGHT);

		gl = ch->group;
		/* leader first */
		if (gl->ch->in_room == ch->in_room)
			spell_shadow_shield(flicker_shield_level(level), ch, 0, 0, gl->ch, 0);
		/* followers */
		for (gl = gl->next; gl; gl = gl->next)
		{
			if (gl->ch->in_room == ch->in_room)
				spell_shadow_shield(flicker_shield_level(level), ch, 0, 0, gl->ch,
						    0);
		}
	}
}

void spell_greater_flicker(int /*level*/, P_char ch, char * /*arg*/, int /*type*/,
			   P_char /*victim*/, P_obj /*obj*/)
{
	send_to_char("This spell is not yet implemented.\r\n", ch);
}

static int obscuring_mist_duration(int level)
{
	return (level / 4 + 1);
}

std::string obscuring_mist_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Duration", game_hours(obscuring_mist_duration(level)) + " at your level, " +
					std::to_string(level)) +
	       "  No mortal can look into, or scan, a room holding someone in the mist.\n"
	       "  Recasting it on someone in the mist does nothing.\n";
}

void spell_obscuring_mist(int level, P_char /*ch*/, char * /*arg*/, [[maybe_unused]] int type,
			  P_char victim, P_obj /*obj*/)
{
	struct affected_type af;

	if (!IS_AFFECTED5(victim, AFF5_OBSCURING_MIST))
	{
		act("&+cA &npale grey &+cmist swirls around $n&+L!", TRUE, victim, 0, 0, TO_ROOM);
		act("&+cA &npale grey &+cmist swirls around you!", TRUE, victim, 0, 0, TO_CHAR);
		bzero(&af, sizeof(af));
		af.type = SPELL_OBSCURING_MIST;
		af.duration = obscuring_mist_duration(level);
		af.modifier = level;
		af.bitvector5 = AFF5_OBSCURING_MIST;
		affect_to_char(victim, &af);

		affect_total(victim, FALSE);
	}
	else
		send_to_char("You must are already surrounded by &+ctons of mist&n.\n", victim);
}

static int sound_suppression_duration()
{
	return 2;
}

// Sneak fails on a roll up to sound_suppression_sneak_fails_up_to().
static int sound_suppression_sneak_roll(const Rolls &rolls)
{
	return rolls.number(1, 100);
}

static int sound_suppression_sneak_fails_up_to(int counter)
{
	return counter * 2;
}

// Moving on the world map with this much noise or less makes none under suppression.
int sound_suppression_noise_limit()
{
	return 13;
}

std::string suppress_sound_facts(P_char /*ch*/)
{
	return "  You need a group. It covers everyone in it here.\n" +
	       fact("Duration", game_hours(sound_suppression_duration())) +
	       fact("Chance each member gets no sneak",
		    std::to_string(sound_suppression_sneak_fails_up_to(1)) + " in " +
			    std::to_string(sound_suppression_sneak_roll(highest_rolls)) +
			    " per group member") +
	       fact("On the world map, no noise moving with allies up to",
		    std::to_string(sound_suppression_noise_limit()) + ", give or take 1") +
	       "  Those under it cannot speak unless illithid, or use group chat or some\n"
	       "  other voice commands. It cannot be dispelled, and recasting does nothing.\n";
}

void spell_suppress_sound(int level, P_char ch, char * /*arg*/, int /*type*/, P_char /*victim*/,
			  P_obj /*obj*/)
{
	struct group_list *gl;
	if (ch && ch->group)
	{
		gl = ch->group;
		if (gl->ch->in_room == ch->in_room)
			spell_sound_suppression(level, ch, NULL, SPELL_TYPE_SPELL, gl->ch, 0);
		for (gl = gl->next; gl; gl = gl->next)
		{
			if (gl->ch->in_room == ch->in_room)
				spell_sound_suppression(level, ch, NULL, SPELL_TYPE_SPELL, gl->ch,
							0);
		}
	}
}

void spell_sound_suppression(int /*level*/, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			     P_char victim, P_obj /*obj*/)
{
	struct affected_type af;
	int counter;
	struct group_list *gl;

	if (!victim)
		return;

	for (gl = ch->group, counter = 0; gl; gl = gl->next)
	{
		counter++;
	}

	if (!affected_by_spell(victim, SPELL_SUPPRESSION))
	{
		bzero(&af, sizeof(af));
		af.type = SPELL_SUPPRESSION;
		af.duration = sound_suppression_duration();
		af.flags = AFFTYPE_NODISPEL;
		// success = add sneak
		if (sound_suppression_sneak_roll(live_rolls) >
		    sound_suppression_sneak_fails_up_to(counter))
		{
			af.bitvector = AFF_SNEAK;
			act("$n becomes deathly silent.&n", FALSE, victim, 0, 0, TO_ROOM);
			act("You are surrounded in silence.&n", FALSE, victim, 0, 0, TO_CHAR);
		}
		affect_to_char(victim, &af);
	}
}

static int shadow_merge_duration()
{
	return 4;
}

std::string shadow_merge_facts(P_char /*ch*/)
{
	return fact("Duration", game_hours(shadow_merge_duration())) +
	       "  It hides you, and you stay hidden moving with whoever you follow.\n"
	       "  Any other command or move takes you out of the shadows.\n"
	       "  Recasting it while merged does nothing.\n";
}

void spell_shadow_merge(int /*level*/, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			P_char /*victim*/, P_obj /*obj*/)
{
	P_char t_ch;
	struct affected_type af;

	if (!affected_by_spell(ch, SPELL_SHADOW_MERGE))
	{
		bzero(&af, sizeof(af));
		af.type = SPELL_SHADOW_MERGE;
		af.duration = shadow_merge_duration();

		affect_to_char(ch, &af);

		if (ch->following)
		{
			for (t_ch = world[ch->in_room].people; t_ch; t_ch = t_ch->next_in_room)
			{
				if (t_ch == ch->following)
				{
					act("$n fades in to the &+Lshadow&n of $N.&n", FALSE, ch, 0,
					    ch->following, TO_ROOM);
					act("You step back into the &+Lshadow&n of $N.&n", FALSE,
					    ch, 0, ch->following, TO_CHAR);
				}
			}
		}
		else
		{
			act("$n fades in to the &+Lshadows&n.&n", FALSE, ch, 0, 0, TO_ROOM);
			act("You step back into the &+Lshadows&n.&n", FALSE, ch, 0, 0, TO_CHAR);
		}
		SET_BIT(ch->specials.affected_by, AFF_HIDE);
	}
}

// The room the gate opens to.
static int ardgral_room_roll(const Rolls &rolls)
{
	return rolls.number(30401, 30464);
}

// How many can pass. A portal only counts a positive number; zero or below has no limit.
static int ardgral_throughput()
{
	return get_property("portals.gate.maxToPass", -1);
}

static int ardgral_init_timeout()
{
	return get_property("portals.gate.initTimeout", 0);
}

static int ardgral_post_enter_timeout()
{
	return get_property("portals.gate.postEnterTimeout", 0);
}

static int ardgral_post_enter_lag()
{
	return get_property("portals.gate.postEnterLag", 0);
}

static int ardgral_decay()
{
	return get_property("portals.gate.decayTimeout", 240);
}

std::string shdw_gate_ardgral_facts(P_char /*ch*/)
{
	const int pass = ardgral_throughput();
	std::string text =
		fact("Opens to", "one of " +
					 std::to_string(ardgral_room_roll(highest_rolls) -
							ardgral_room_roll(lowest_rolls) + 1) +
					 " rooms of Ardgral, one way") +
		fact("Can pass", pass > 0 ? std::to_string(pass) : "no limit") +
		fact("Portal lasts", "up to " + real_time(ardgral_decay()));
	if (ardgral_init_timeout() > 0)
		text += fact("Wait before anyone can enter", seconds(ardgral_init_timeout()));
	if (ardgral_post_enter_timeout() > 0)
		text += fact("Wait between entries", seconds(ardgral_post_enter_timeout()));
	if (ardgral_post_enter_lag() > 0)
		text += fact("Lag stepping out", seconds(ardgral_post_enter_lag()));
	return text +
	       "  No-gate rooms, hometowns and castles block it, and you must be raidable.\n";
}

void cast_ardgral(int level, P_char ch, char * /*arg*/, int /*type*/, P_char /*tar_ch*/,
		  P_obj /*tar_obj*/)
{
	struct portal_settings set = {
		291, /* portal type  */
		-1, /* from room */
		-1, /* to room */
		0, /* How many can pass before closes */
		0, /* Timeout before anyone can enter after open */
		0, /* Timeout before next person can enter */
		0, /* Lag person gets when steps out portal */
		0 /* Portal decay timer */
	};
	struct portal_create_messages msg = {
		/*ch   */ "&+cSomething prevents your escapist dreams here&n.\r\n",
		/*ch r */ 0,
		/*vic  */ 0,
		/*vic r*/ 0,
		/*ch   */
		"&+cThe winds of thought collect your &+Wdreams&+c and then quickly condense into $p&n&+c.",
		/*ch r */
		"&+cThe winds of thought collect your &+Wdreams&+c and then quickly condense into $p&n&+c.",
		/*vic  */ 0,
		/*vic r*/ 0,
		/*npc  */ 0,
		/*bad  */ 0
	};

	int to_room;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	to_room = real_room0(ardgral_room_roll(live_rolls));

	if (IS_ROOM(ch->in_room, ROOM_NO_GATE) || IS_HOMETOWN(ch->in_room))
	{
		send_to_char(msg.fail_to_caster, ch);
		return;
	}

	if (ch && !is_Raidable(ch, 0, 0))
	{
		send_to_char("&+WYou are not raidable. The spell fails!\r\n", ch);
		return;
	}

	set.to_room = to_room;
	set.throughput = ardgral_throughput();
	set.init_timeout = ardgral_init_timeout();
	set.post_enter_timeout = ardgral_post_enter_timeout();
	set.post_enter_lag = ardgral_post_enter_lag();
	set.decay_timer = ardgral_decay();

	// one way portal
	spell_general_portal(level, ch, 0, &set, &msg, TRUE);

	return;
}

struct sbb_data
{
	int room;
	int waves;
};

static int shadow_spawn_lag()
{
	return PULSE_VIOLENCE;
}

static int shadow_spawn_waves()
{
	return 2;
}

// Before the first wave, and between waves, in pulses.
static int shadow_spawn_wave_delay()
{
	return PULSE_VIOLENCE * 2;
}

// A player's or pet's next wave comes on a roll of 0.
static int shadow_spawn_player_splat()
{
	return 2;
}

static int shadow_spawn_wave_roll(const Rolls &rolls, int splat)
{
	return rolls.number(0, splat);
}

static int shadow_spawn_damage(const Rolls &rolls, int level)
{
	return level * 4 + rolls.number(-20, 40);
}

// A player's shadow spawn against another player.
static int shadow_spawn_player_damage(int dam)
{
	return dam * get_property("spell.area.damage.to.pc", 0.5);
}

static int shadow_spawn_undead_damage(int dam)
{
	return (int)(dam / 5);
}

// Added to the target's fear save against the blindness and terror.
static int shadow_spawn_save_mod(P_char ch)
{
	return (int)(GET_LEVEL(ch) / 10);
}

// Blindness and terror each land on a roll of 0, up to this.
static int shadow_spawn_affect_odds(P_char ch)
{
	int affmod = 5;

	// Level 56 npc have 50% to afflict each affect.
	if (IS_NPC(ch) && !GET_MASTER(ch))
	{
		affmod -= 1;
	}
	if (GET_LEVEL(ch) > 49)
	{
		affmod -= 1;
	}
	if (GET_LEVEL(ch) > 53)
	{
		affmod -= 1;
	}
	if (GET_LEVEL(ch) > 55)
	{
		affmod -= 1;
	}
	return affmod;
}

static int shadow_spawn_affect_roll(const Rolls &rolls, int affmod)
{
	return rolls.number(0, affmod);
}

static int shadow_spawn_blind_duration()
{
	return PULSE_VIOLENCE;
}

std::string shadow_spawn_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const int low = shadow_spawn_damage(lowest_rolls, level);
	const int high = shadow_spawn_damage(highest_rolls, level);
	const int player_low = shadow_spawn_player_damage(low);
	const int player_high = shadow_spawn_player_damage(high);
	const int odds = shadow_spawn_affect_odds(ch);
	const int save = shadow_spawn_save_mod(ch);
	const int splat = shadow_spawn_player_splat();
	return fact("Your lag", seconds(shadow_spawn_lag())) +
	       fact("First wave after", seconds(shadow_spawn_wave_delay())) +
	       fact("Waves", "at most " + std::to_string(shadow_spawn_waves())) +
	       fact("Chance of the next wave, after as long",
		    "1 in " + std::to_string(shadow_spawn_wave_roll(highest_rolls, splat) -
					     shadow_spawn_wave_roll(lowest_rolls, splat) + 1)) +
	       "  Leaving the room collapses the vortex. Safe rooms stop it.\n" +
	       fact("Spirit damage per wave",
		    show_landing({ low, high }) + " at your level, " + std::to_string(level)) +
	       fact("To another player", show_landing({ player_low, player_high })) +
	       fact("To an undead NPC", show_landing({ shadow_spawn_undead_damage(low),
						       shadow_spawn_undead_damage(high) })) +
	       fact("To an undead player",
		    show_landing({ shadow_spawn_undead_damage(player_low),
				   shadow_spawn_undead_damage(player_high) })) +
	       "  Globes and spirit wards do not stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n" +
	       fact("If a survivor fails a fear save",
		    (save ? "at +" + std::to_string(save) + ", harder" :
			    std::string("unmodified"))) +
	       fact("Chance it is blinded",
		    "1 in " +
			    std::to_string(shadow_spawn_affect_roll(highest_rolls, odds) -
					   shadow_spawn_affect_roll(lowest_rolls, odds) + 1) +
			    ", for " + seconds(shadow_spawn_blind_duration())) +
	       fact("Chance it flees",
		    "1 in " + std::to_string(shadow_spawn_affect_roll(highest_rolls, odds) -
					     shadow_spawn_affect_roll(lowest_rolls, odds) + 1)) +
	       "  Undead, elites and greater races ignore both, and magic resistance can\n"
	       "  shrug each. The blind and those who cannot be blinded stay as they are.\n";
}

void spell_shadow_burst(int /*level*/, P_char ch, char * /*arg*/, int /*type*/, P_char /*victim*/,
			P_obj /*obj*/)
{
	struct sbb_data sbbdata;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	sbbdata.waves = shadow_spawn_waves();
	sbbdata.room = ch->in_room;
	send_to_room(
		"&+LThe room clouds with &nmists&+L as a v&+ror&+Rt&+re&+Lx starts to form..\n",
		ch->in_room);
	add_event(event_shadow_spawn, shadow_spawn_wave_delay(), ch, 0, 0, 0, &sbbdata,
		  sizeof(struct sbb_data));
	CharWait(ch, shadow_spawn_lag());
}

void event_shadow_spawn(P_char ch, P_char /*victim*/, P_obj /*obj*/, void *data)
{
	struct sbb_data *sbbdata = (struct sbb_data *)data;
	int splat;

	if (!sbbdata)
	{
		debug("Passed null pointer to event_shadow_spawn_burst in sillusionist.c.");
		return;
	}

	if ((sbbdata->room != ch->in_room) || (sbbdata->waves < 1))
	{
		send_to_char("&+LThe swirling v&+ror&+Rt&+re&+Lx &+Lcollapses!\n", ch);
		;
		act("&+LThe swirling v&+ror&+Rt&+re&+Lx &+Lcollapses!", TRUE, ch, 0, 0, TO_ROOM);
		return;
	}

	act("&+LThe v&+ror&+Rt&+re&+Lx splits open and horrific n&+mi&+Lghtm&+ma&+Lr&+me&+Ls explode into the room!",
	    FALSE, ch, 0, 0, TO_CHAR);
	act("&+LThe v&+ror&+Rt&+re&+Lx splits open and horrific n&+mi&+Lghtm&+ma&+Lr&+me&+Ls explode into the room!",
	    FALSE, ch, 0, 0, TO_ROOM);
	cast_as_damage_area(ch, spell_shadow_spawn, GET_LEVEL(ch), NULL,
			    get_property("spell.area.minChance.spawn", 90),
			    get_property("spell.area.chanceStep.spawn", 10));

	sbbdata->waves--;

	if (ch && IS_NPC(ch) && !GET_MASTER(ch))
	{
		splat = 1;
	}
	else
	{
		splat = shadow_spawn_player_splat();
	}

	if ((sbbdata->waves > 0) && !shadow_spawn_wave_roll(live_rolls, splat))
	{
		send_to_room(
			"&+LA swirling v&+ror&+Rt&+re&+Lx continues to spill out n&+mi&+Lghtm&+ma&+Lr&+me&+Ls...\n",
			ch->in_room);
		add_event(event_shadow_spawn, shadow_spawn_wave_delay(), ch, 0, 0, 0, sbbdata,
			  sizeof(struct sbb_data));
	}
	else
	{
		send_to_char("&+LThe swirling v&+ror&+Rt&+re&+Lx &+Lcollapses!\n", ch);
		;
		act("&+LThe swirling v&+ror&+Rt&+re&+Lx &+Lcollapses!", TRUE, ch, 0, 0, TO_ROOM);
	}
}

void spell_shadow_spawn(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			P_obj /*obj*/)
{
	int dam, savemod, affmod;
	struct damage_messages messages = {
		"&+LYou conjure up the worst &+Rfears&+L of your foes and hurl it at them!",
		"&+LMaddening &+Cvisions &+Lfrom your worst n&+Ri&+Lghtm&+Ra&+Lr&+Re&+Ls sweep over you!",
		"&+LWaves of &+rhorrific &+Lcreatures descend upon $N, who begins to &+Wscream!&n",
		"&+L$N turns &+Wpale white&+L at the n&+mi&+Lghtm&+ma&+Lr&+me&+Ls and dies!",
		"&+L$N turns &+Wpale white&+L at the n&+mi&+Lghtm&+ma&+Lr&+me&+Ls and dies!",
		0
	};

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return;
	}

	dam = shadow_spawn_damage(live_rolls, level);
	// Meteorswarm damage is: 100 + level * 6 + number(1, 40);
	savemod = shadow_spawn_save_mod(ch);

	affmod = shadow_spawn_affect_odds(ch);

	if (IS_PC(ch) && IS_PC(victim))
	{
		dam = shadow_spawn_player_damage(dam);
	}

	// Undead just don't care too much about this.
	if (IS_UNDEAD(victim))
	{
		dam = shadow_spawn_undead_damage(dam);
	}

	if (spell_damage(ch, victim, dam, SPLDAM_SPIRIT, 0, &messages) == DAM_NONEDEAD)
	{
		// Undead, elite, and greater races don't care about the affects.
		if ((IS_ELITE(victim) || IS_GREATER_RACE(victim) || IS_UNDEAD(victim)))
		{
			return;
		}
		if (!NewSaves(victim, SAVING_FEAR, savemod))
		{
			/*
			if (!(number(0, 3))) {

			   act("&+LThe n&+mi&+Lghtm&+ma&+Lr&+me&+L bomeces groteqsue and $N starts to vomit!&n", FALSE, ch, 0, victim, TO_CHAR);
			   act("&+LThe n&+mi&+Lghtm&+ma&+Lr&+me&+L becomes grotesque and you start to vomit!&n", FALSE,
			    ch, 0, victim, TO_VICT);
			   act("&+LThe n&+mi&+Lghtm&+ma&+Lr&+me&+L becomes grotesque and $N starts to vomit!", FALSE, ch, 0, victim, TO_NOTVICT);
			  spell_disease(46, ch, NULL, SPELL_TYPE_SPELL, victim, 0);
			}
			*/
			if (!shadow_spawn_affect_roll(live_rolls, affmod))
			{
				act("&+LThe n&+mi&+Lghtm&+ma&+Lr&+me&+L is too much for $N, whose eyes close!&n",
				    FALSE, ch, 0, victim, TO_CHAR);
				act("&+LThe n&+mi&+Lghtm&+ma&+Lr&+me&+L is too much and you close your eyes!&n",
				    FALSE, ch, 0, victim, TO_VICT);
				act("&+LThe n&+mi&+Lghtm&+ma&+Lr&+me&+L is too much for $N, whose eyes close!",
				    FALSE, ch, 0, victim, TO_NOTVICT);
				if (ch && victim && !resists_spell(ch, victim))
				{
					blind(ch, victim, shadow_spawn_blind_duration());
				}
			}
			if (!shadow_spawn_affect_roll(live_rolls, affmod))
			{
				act("&+LThe n&+mi&+Lghtm&+ma&+Lr&+me&+L scares the bejesus out of $N!&n",
				    FALSE, ch, 0, victim, TO_CHAR);
				act("&+LA wave of utter terror overcomes you as the n&+mi&+Lghtm&+ma&+Lr&+me&+L consumes you!&n",
				    FALSE, ch, 0, victim, TO_VICT);
				act("&+LThe n&+mi&+Lghtm&+ma&+Lr&+me&+L scares the bejesus out of $N!",
				    FALSE, ch, 0, victim, TO_NOTVICT);
				if (ch && victim && !resists_spell(ch, victim))
				{
					do_flee(victim, 0, 2);
				}
			}
		}
	}
}

static int asphyxiate_rounds()
{
	return 3;
}

static int asphyxiate_delay()
{
	return 1;
}

static int asphyxiate_saved_damage(const Rolls &rolls, P_char ch)
{
	return (5 * GET_LEVEL(ch) + 65) / 2 + rolls.number(0, 40);
}

static int asphyxiate_failed_damage(const Rolls &rolls, P_char ch)
{
	return 5 * GET_LEVEL(ch) + rolls.number(5, 45);
}

std::string asphyxiate_facts(P_char ch)
{
	return fact("Hits", std::to_string(asphyxiate_rounds()) + ", " +
				    seconds(asphyxiate_delay()) + " apart") +
	       fact("Damage per hit if the target fails its save",
		    show({ asphyxiate_failed_damage(lowest_rolls, ch),
			   asphyxiate_failed_damage(highest_rolls, ch) }) +
			    " at your level, " + std::to_string(GET_LEVEL(ch))) +
	       fact("If it saves", show({ asphyxiate_saved_damage(lowest_rolls, ch),
					  asphyxiate_saved_damage(highest_rolls, ch) })) +
	       "  Each hit makes its own save. It stops if either of you dies.\n"
	       "  It does nothing to a target with no lungs. It cannot be deflected.\n"
	       "  Globes and spirit wards do not stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

// Event to handle asphyxiate spell.
void event_asphyxiate(P_char ch, P_char victim, P_obj /*obj*/, void *data)
{
	int rounds = *((int *)data);
	int dam, level;
	struct damage_messages messages = {
		"&+cYou smirk as a pair of &+Wgh&+Los&+wtl&+Wy h&+Lan&+wds &+Rtighten &+caround $N&+c's throat!&n",
		"&+cYou gasp for &+Cair &+cas a pair of &+Wgh&+Los&+wtl&+Wy h&+Lan&+wds &+ctighten around your throat!&n",
		"&+c$N &+cgasps for &+Cair &+cas a pair of &+Wgh&+Los&+wtl&+Wy h&+Lan&+wds &+ctighten around $S throat!&n",
		"&+cYour &+Cill&+Wusi&+cona&+Cry &+Whands &+Cchoke &+cthe life out of $N&+c, who falls over &+rdead &+cand &+Llifeless&+c.&n",
		"&+LEverything suddenly goes black as a pair of &+Wgh&+Los&+wtl&+Wy h&+wa&+Lnd&+Ws &+Cchoke &+Lthe life out of you...&n",
		"&+c$N &+Cgasps &+cfor air, &+Weyes &+Mbulging&+c, then falls over, slowly becoming &+Lmotionless&+c.&n",
		0
	};

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return;
	}

	level = GET_LEVEL(ch);
	if (level > 51)
		level = 51;

	int mod = get_default_save_mod(victim, ch, SAVING_SPELL, SPELL_ASPHYXIATE);

	if (NewSaves(victim, SAVING_SPELL, mod))
	{
		// 45 +/- 5 dam at 51.
		dam = asphyxiate_saved_damage(live_rolls, ch);
	}
	else
	{
		// 70 +/- 5 dam at 56.
		dam = asphyxiate_failed_damage(live_rolls, ch);
	}

	if (spell_damage(ch, victim, dam, SPLDAM_GENERIC, SPLDAM_NODEFLECT, &messages) ==
		    DAM_NONEDEAD &&
	    (--rounds > 0))
	{
		add_event(event_asphyxiate, asphyxiate_delay(), ch, victim, NULL, 0, &rounds,
			  sizeof(int));
	}
}

// _very_ quick dot that does damage over 3 ticks.
void spell_asphyxiate(int /*level*/, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		      P_obj /*obj*/)
{
	int rounds = asphyxiate_rounds();

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return;
	}
	if (!HAS_LUNGS(GET_RACE(victim)))
	{
		act("But $N doesn't need to breathe!", TRUE, ch, NULL, victim, TO_CHAR);
		return;
	}
	act("&+LA pair of &+wGh&+Los&+Wt&+wly &+WH&+La&+wnd&+Ws &+Lappear before &+c$N&+L, close around $S neck and begin to &+Rsqueeze&+L!&n",
	    FALSE, ch, NULL, victim, TO_CHAR);
	act("&+wGh&+Los&+Wt&+wly &+Wh&+La&+wnd&+Ws &+Lappear before &+c$N&+L, close around $S neck and begin to &+Rsqueeze&+L!&n",
	    FALSE, ch, NULL, victim, TO_NOTVICT);
	act("&+wGh&+Los&+Wt&+wly &+Wh&+La&+wnd&+Ws &+Lappear before you, close around your neck and begin to &+Rsqueeze&+L!&n",
	    FALSE, victim, NULL, NULL, TO_CHAR);

	event_asphyxiate(ch, victim, NULL, &rounds);
}

#define _ILLUSIONIST_MAGIC_C_
#endif
