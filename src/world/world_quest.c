/****************************************************************************
 *
 *  File: world_quest.c                                      Part of Duris
 *  Usage: world_quest.c
 *  Copyright  1990, 1991 - see 'license.doc' for complete information.
 *  Copyright 1994 - 2008 - Duris Systems Ltd.
 *  Created by: Kvark 			Date: 2006-04-17
 * ***************************************************************************

todo:


Version 2
- Change so you can ask solo, small.



 */

#include <vector>
using namespace std;

#include "core/prototypes.h"
#include "world/difficulty.h"
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "core/utility.h"
#include "core/utils.h"
#include <ctype.h>
#include <fnmatch.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "world/epic.h"
#include "net/gmcp.h"
#include "combat/justice.h"
#include "world/map.h"
#include "item/objmisc.h"
#include "item/random_equipment.h"
#include "item/item_movement_transaction.h"
#include "persistence/persistence_checkpoint.h"
#include "player/player_save_pipeline.h"
#include "magic/spells.h"
#include "sql/sql.h"
#include "world/weather.h"
#include "world/world_quest.h"
#include "world/world_quest_policy.h"
#include "world/world_quest_policy_math.h"
#include "world/zone_story_quest_runtime.h"

/* * external variables */

extern char *target_locs[];
extern char *set_master_text[];
extern int mini_mode;
extern FILE *help_fl;
extern FILE *info_fl;
extern P_char character_list;
extern P_desc descriptor_list;
extern P_index mob_index;
extern P_index obj_index;
extern P_obj object_list;
extern P_room world;
extern struct class_names class_names_table[];
extern const char *color_liquid[];
extern const char *command[];
extern const char *connected_types[];
extern const char *craftsmanship_names[];
extern const char *dirs[];
extern const char *fullness[];
extern struct material_data materials[];
extern const char *month_name[];
extern const char *player_bits[];
extern const char *player_prompt[];
extern flagDef weapon_types[];
extern const char *weekdays[];
extern const int rev_dir[];
extern const long boot_time;
extern const struct stat_data stat_factor[];
extern const char *size_types[];
extern const char *item_size_types[];
extern long new_exp_table[]; // Arih: Fixed type mismatch bug - was int, should be long
extern int avail_descs;
extern int help_array[27][2];
extern int info_array[27][2];
extern int max_descs;
extern int max_users_playing;
extern int number_of_quests;
extern int number_of_shops;
extern int pulse;
extern int str_weightcarried, str_todam, str_tohit, dex_defense;
extern int top_of_helpt;
extern int top_of_infot;
extern int top_of_mobt;
extern int top_of_objt;
extern int top_of_zone_table;
extern int top_of_world;
extern int used_descs;
extern struct agi_app_type agi_app[];
extern struct command_info cmd_info[];
extern struct dex_app_type dex_app[];
extern struct info_index_element *info_index;
extern struct str_app_type str_app[];
extern struct time_info_data time_info;
extern struct zone_data *zone_table;
extern struct sector_data *sector_table;
extern char *specdata[][MAX_SPEC];
extern long sentbytes;
extern const struct race_names race_names_table[];
extern Skill skills[];
extern const mcname multiclass_names[];
extern void displayShutdownMsg(P_char);

void resetQuest(P_char ch)
{
	ch->only.pc->quest_active = 0;
	ch->only.pc->quest_mob_vnum = 0;
	ch->only.pc->quest_type = 0;
	ch->only.pc->quest_accomplished = 0;
	ch->only.pc->quest_started = 0;
	ch->only.pc->quest_zone_number = -1;
	ch->only.pc->quest_giver = 0;
	ch->only.pc->quest_level = 0;
	ch->only.pc->quest_receiver = 0;
	ch->only.pc->quest_shares_left = 0;
	ch->only.pc->quest_kill_how_many = 0;
	ch->only.pc->quest_kill_original = 0;
	ch->only.pc->quest_map_room = 0;
	ch->only.pc->quest_map_bought = 0;
	ch->only.pc->quest_origin_room = 0;
	ch->only.pc->quest_replacement_due = 0;
	mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS);
}

// How many other players a quest's receiver may share it with. world.quest.share.max
// defaults to 0, so every player takes, pays for and completes their own quest. The
// ceiling of 4 is the historical share limit.
static int world_quest_share_limit()
{
	return BOUNDED(0, static_cast<int>(get_property("world.quest.share.max", 0.000)), 4);
}

static int quest_epic_reward_amount(P_char ch)
{
	if (GET_LEVEL(ch) <= 45 || ch->only.pc->quest_level <= 45)
		return 0;
	const int level = ch->only.pc->quest_level;
	if (level > 55)
		return 15;
	const int low = level - 45;
	return number(low, level == 54 ? 10 : MIN(low + 2, 11));
}

void quest_epic_reward(P_char ch, int /*type*/, int amount)
{
	if (amount > 0)
		gain_epic(ch, EPIC_QUEST, 0, amount);
}

int quest_exp_reward(P_char ch, int /*type*/)
{
	int exp_gain = 0;
	if (GET_LEVEL(ch) <= 30)
		exp_gain = EXP_NOTCH(ch) * get_property("world.quest.exp.level.30.andUnder", 1.300);
	else if (GET_LEVEL(ch) <= 40)
		exp_gain = EXP_NOTCH(ch) * get_property("world.quest.exp.level.40.andUnder", 1.000);
	else if (GET_LEVEL(ch) <= 50)
		exp_gain = EXP_NOTCH(ch) * get_property("world.quest.exp.level.50.andUnder", 0.800);
	else if (GET_LEVEL(ch) <= 55)
		exp_gain = EXP_NOTCH(ch) * get_property("world.quest.exp.level.55.andUnder", 0.500);
	else
		exp_gain = EXP_NOTCH(ch) * get_property("world.quest.exp.level.other", 1.000);
	return exp_gain;
}

static player_world_quest_reward world_quest_prepare_reward(P_char ch, int type, bool final_kill)
{
	player_world_quest_reward reward;
	reward.experience = quest_exp_reward(ch, type);
	if (final_kill)
		reward.experience /= ch->only.pc->quest_kill_original;
	if (GET_CLASS(ch, CLASS_MERCENARY) && GET_LEVEL(ch) > 24)
		reward.money = GET_LEVEL(ch) * 1256 + number(1, 500);
	reward.epic = quest_epic_reward_amount(ch);
	return reward;
}

P_obj quest_item_reward(P_char ch)
{
	const int quest_level = ch->only.pc->quest_level > 0 ? ch->only.pc->quest_level :
							       GET_LEVEL(ch);
	P_obj reward = read_object(real_object(getQuestItemFromZone(
					   real_zone(ch->only.pc->quest_zone_number), quest_level)),
				   REAL);

	if (!reward)
	{
		reward = create_random_eq(ch, GET_LEVEL(ch), GET_LEVEL(ch), -1, -1);
	}

	if (reward)
	{
		wizlog(56, "quest_item_reward: %s reward was: %s [%d] ivalue %d.", GET_NAME(ch),
		       reward->short_description, OBJ_VNUM(reward), itemvalue(reward));

		REMOVE_BIT(reward->extra_flags, ITEM_SECRET);
		REMOVE_BIT(reward->extra_flags, ITEM_INVISIBLE);
		SET_BIT(reward->extra_flags, ITEM_NOREPAIR);
		REMOVE_BIT(reward->extra_flags, ITEM_NODROP);
	}
	return reward;
}

static P_obj world_quest_reward_by_uid(uint64_t uid)
{
	if (!uid)
		return NULL;
	for (P_obj object = object_list; object; object = object->next)
		if (object->obj_uid == uid)
			return object;
	return NULL;
}

// The history/after-image is durable before this publishes any completion rewards.
static void world_quest_deliver_reward(P_char ch, P_char quest_mob, int type, bool final_kill,
				       P_obj reward, bool already_secured,
				       const player_world_quest_reward &values)
{
	char Gbuf1[MAX_STRING_LENGTH];
	if (!final_kill && quest_mob && type == FIND_AND_ASK)
	{
		wizlog(56, "%s finished quest @%s (ask quest)", GET_NAME(ch),
		       quest_mob->player.short_descr);
		do_action(quest_mob, 0, CMD_NOD);
		mobsay(quest_mob,
		       "Thanks for bringing me the message. Here is a little something for your trouble.");
	}
	const bool reward_granted = reward && OBJ_CARRIED_BY(reward, ch);
	if (reward_granted && final_kill)
		send_to_char_f(ch, "For completing your quest you receive %s&n.\r\n",
			       reward->short_description);
	else if (reward_granted && quest_mob)
	{
		act("$n gives you $q ", TRUE, quest_mob, reward, ch, TO_VICT);
		act("$n gives $N $q.", FALSE, quest_mob, reward, ch, TO_NOTVICT);
	}
	else if (already_secured)
		send_to_char("Your completed task is ready for its remaining rewards.\r\n", ch);

	if (final_kill)
	{
		wizlog(56, "%s finished quest target %d (kill quest)", GET_NAME(ch),
		       ch->only.pc->quest_mob_vnum);
		send_to_char("&+WCongratulations&n&n&+W, you finished your quest!&n\r\n", ch);
		gain_exp(ch, NULL, values.experience, EXP_WORLD_QUEST);
	}

	if (values.money > 0)
	{
		if (quest_mob && !final_kill)
			mobsay(quest_mob, "I know you mercenaries don't work for free. Take this.");
		else if (final_kill)
		{
			act("A sneaky gremlin appears near $n and whispers something.", TRUE, ch, 0,
			    0, TO_ROOM);
			act("A sneaky gremlin appears beside you.", FALSE, ch, 0, 0, TO_CHAR);
			act("A sneaky gremlin whispers '&+LMy master sent me with your payment&N'.",
			    FALSE, ch, 0, 0, TO_CHAR);
		}
		snprintf(Gbuf1, MAX_STRING_LENGTH, "You receive %s.\r\n",
			 coin_stringv(values.money));
		send_to_char(Gbuf1, ch);
		ADD_MONEY(ch, values.money);
	}
	else if (GET_CLASS(ch, CLASS_MERCENARY) && quest_mob && !final_kill)
		mobsay(quest_mob,
		       "Sorry, but it's hard to take a little pipsqueek like you seriously as a mercenary. Grow up a bit and you'll start earning your keep.");

	quest_epic_reward(ch, type, values.epic);
	if (!final_kill)
	{
		gain_exp(ch, NULL, values.experience, EXP_WORLD_QUEST);
		if (quest_mob)
			act("&+WYou gain some experience.&n", FALSE, quest_mob, 0, ch, TO_VICT);
		else
			send_to_char("&+WYou gain some experience.&n\r\n", ch);
	}
	mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS);
	resetQuest(ch);
	gmcp_quest_status(ch);
}

static bool world_quest_start_reward(P_char ch, P_char quest_mob, int type, bool final_kill)
{
	P_obj reward = quest_item_reward(ch);
	if (reward && IS_OBJ_STAT2(reward, ITEM2_CRUMBLELOOT) && !IS_TRUSTED(ch))
	{
		extract_obj(reward, FALSE);
		send_to_char("The quest reward is unavailable; your task was not changed.\r\n", ch);
		return false;
	}
	if (!reward || !reward->obj_uid)
	{
		if (reward)
			extract_obj(reward, FALSE);
		send_to_char("The quest reward is unavailable; your task was not changed.\r\n", ch);
		return false;
	}
	const auto values = world_quest_prepare_reward(ch, type, final_kill);
	const uint64_t reward_uid = reward ? reward->obj_uid : 0;
	const uint64_t mob_id = quest_mob ? quest_mob->runtime_id : 0;
	const int target = ch->only.pc->quest_mob_vnum;
	const int started = ch->only.pc->quest_started;
	if (!sql_world_quest_finish_async(
		    ch, reward, true, final_kill, values,
		    [reward_uid, mob_id, target, started, type, final_kill, values](P_char actor)
		    {
			    if (!actor || !actor->only.pc || !actor->only.pc->quest_active ||
				actor->only.pc->quest_mob_vnum != target ||
				actor->only.pc->quest_started != started)
				    return;
			    actor->only.pc->quest_accomplished =
				    final_kill ? PLAYER_WORLD_QUEST_KILL_REWARD_PENDING :
						 PLAYER_WORLD_QUEST_REWARD_PENDING;
			    P_char mob = mob_id ? find_character_by_runtime_id(mob_id) : NULL;
			    if (mob && mob->in_room != actor->in_room)
				    mob = NULL;
			    world_quest_deliver_reward(actor, mob, type, final_kill,
						       world_quest_reward_by_uid(reward_uid), false,
						       values);
		    }))
	{
		if (reward)
			extract_obj(reward, FALSE);
		send_to_char("Your quest history is unavailable; your task was not changed.\r\n",
			     ch);
		return false;
	}
	if (player_save_pipeline_world_quest_pending(GET_PID(ch)))
		send_to_char("Your quest history is still being secured.\r\n", ch);
	return true;
}

void quest_full_reward(P_char ch, P_char quest_mob, int type)
{
	if (!IS_ALIVE(ch) || IS_NPC(ch) || player_save_pipeline_world_quest_pending(GET_PID(ch)))
		return;
	if (ch->only.pc->quest_accomplished == PLAYER_WORLD_QUEST_KILL_REWARD_UNSECURED)
	{
		world_quest_start_reward(ch, quest_mob, FIND_AND_KILL, true);
		return;
	}
	if (ch->only.pc->quest_accomplished == PLAYER_WORLD_QUEST_REWARD_PENDING ||
	    ch->only.pc->quest_accomplished == PLAYER_WORLD_QUEST_KILL_REWARD_PENDING)
	{
		const bool final_kill = ch->only.pc->quest_accomplished ==
					PLAYER_WORLD_QUEST_KILL_REWARD_PENDING;
		const player_world_quest_reward values = { ch->only.pc->quest_receiver,
							   ch->only.pc->quest_shares_left,
							   ch->only.pc->quest_kill_how_many };
		world_quest_deliver_reward(ch, quest_mob, final_kill ? FIND_AND_KILL : type,
					   final_kill, NULL, true, values);
		return;
	}
	world_quest_start_reward(ch, quest_mob, type, false);
}

static bool world_quest_matches_target(P_char ch, P_char mob, int type)
{
	return IS_ALIVE(ch) && IS_PC(ch) && ch->only.pc->quest_active == 1 &&
	       ch->only.pc->quest_type == type && mob && IS_NPC(mob) && mob->in_room >= 0 &&
	       mob->in_room <= top_of_world && GET_VNUM(mob) == ch->only.pc->quest_mob_vnum &&
	       zone_table[world[mob->in_room].zone].number == ch->only.pc->quest_zone_number;
}

void quest_ask(P_char ch, P_char quest_mob)
{
	if (!world_quest_matches_target(ch, quest_mob, FIND_AND_ASK))
		return;
	if (player_save_pipeline_world_quest_pending(GET_PID(ch)))
		return;

	quest_full_reward(ch, quest_mob, FIND_AND_ASK);
}

void quest_kill(P_char ch, P_char quest_mob)
{
	if (!world_quest_matches_target(ch, quest_mob, FIND_AND_KILL))
		return;
	if (player_save_pipeline_world_quest_pending(GET_PID(ch)))
		return;

	if (ch->only.pc->quest_accomplished)
	{
		send_to_char(
			"This quest is already finished, go visit your quest master for your reward!\r\n",
			ch);
		return;
	}

	ch->only.pc->quest_kill_how_many++;

	int exp_gain = quest_exp_reward(ch, FIND_AND_KILL);

	if (ch->only.pc->quest_kill_original == 0)
	{
		send_to_char("&-RMEMORY ERROR! quest_kill_original is zero, inform a god!&n\r\n",
			     ch);
		wizlog(56, "MEMORY ERROR: quest_kill_original is zero!");
		ch->only.pc->quest_kill_original = ch->only.pc->quest_kill_how_many;
	}

	if (ch->only.pc->quest_kill_how_many - ch->only.pc->quest_kill_original == 0)
	{
		if (!world_quest_start_reward(ch, quest_mob, FIND_AND_KILL, true))
		{
			ch->only.pc->quest_accomplished = PLAYER_WORLD_QUEST_KILL_REWARD_UNSECURED;
			mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS);
		}
	}
	else
	{
		gain_exp(ch, NULL, exp_gain / ch->only.pc->quest_kill_original, EXP_WORLD_QUEST);
		send_to_char(
			"&+YCongratulations&+y, you found the right mob, but you're not done yet.\r\n",
			ch);
		gmcp_quest_status(ch);
	}
}

#define EVIL_CONT 0
#define GOOD_CONT 1
#define UNDER_DARK 2

int get_map_room(int zone_id)
{
	int i2;
	int i;
	struct zone_data *zone = 0;

	if (zone_id < 0)
		return -1;

	zone = &zone_table[zone_id];

	for (i = zone->real_bottom; (i != NOWHERE) && (i <= zone->real_top); i++)
		for (i2 = 0; i2 < NUM_EXITS; i2++)
			if (world[i].dir_option[i2])
			{
				if ((world[i].dir_option[i2]->to_room == NOWHERE) ||
				    (world[world[i].dir_option[i2]->to_room].zone != world[i].zone))
				{
					if (world[i].dir_option[i2]->to_room == NOWHERE)
						;
					else
					{
						if (IS_MAP_ROOM(world[i].dir_option[i2]->to_room))
						{
							/*
						   snprintf(o_buf, MAX_STRING_LENGTH,
						   " &+Y[&n%5d&+Y](&n%5d&+Y)&n &+R%-5s&n to &+Y[&+R%3d&n:&+Y%5d&+Y](&n%5d&+Y)&n %s\n",
						   world[i].number, i, dirs[i2],
						   world[world[i].dir_option[i2]->to_room].zone,
						   world[world[i].dir_option[i2]->to_room].number,
						   world[i].dir_option[i2]->to_room,
						   world[world[i].dir_option[i2]->to_room].name);
						   wizlog(56, "%s", o_buf);
						 */
							return world[i].dir_option[i2]->to_room;
						}
					}
				}
			}
	return -1;
}

void do_quest(P_char ch, char *args, int /*cmd*/)
{
	P_char victim;

	char buf[MAX_STRING_LENGTH];

	char name[MAX_INPUT_LENGTH], who[MAX_STRING_LENGTH];

	if (IS_NPC(ch))
	{
		return;
	}
	half_chop(args, name, who);
	if (*name && isname(name, "daily"))
	{
		if (zone_story_quest_runtime::service())
		{
			const bool colors = ch->desc && ch->desc->term_type != TERM_GENERIC &&
					    ch->desc->term_type != TERM_SKIP_ANSI;
			std::string daily = zone_story_quest_runtime::render_daily(ch, colors);
			if (!daily.empty())
				send_to_char(daily.c_str(), ch);
		}
		return;
	}
	if (player_save_pipeline_world_quest_pending(GET_PID(ch)))
	{
		send_to_char("Your quest history is still being secured.\r\n", ch);
		return;
	}
	/* When a populated daily assignment exists, show its player-facing details
	 * alongside the ordinary bartender/world quest.  Empty or disabled daily
	 * state deliberately contributes no text. */
	if (zone_story_quest_runtime::service())
	{
		const bool colors = ch->desc && ch->desc->term_type != TERM_GENERIC &&
				    ch->desc->term_type != TERM_SKIP_ANSI;
		std::string daily = zone_story_quest_runtime::render_daily(ch, colors);
		if (!daily.empty())
			send_to_char(daily.c_str(), ch);
	}

	// Allow Illithids to do bartender quests.
	/* if( IS_ILLITHID(ch) )
	 {
	   send_to_char("No quests for you!", ch);
	   return;
	 }*/

	if (*name)
	{
		if (isname(name, "reset") && IS_TRUSTED(ch))
		{
			if (!*who)
			{
				send_to_char("Whos quest do you want to reset?\r\n", ch);
				return;
			}

			victim = ParseTarget(ch, who);
			if (!victim)
			{
				send_to_char("Hmm, who do you mean?\r\n", ch);
				return;
			}
			if (IS_PC(victim) &&
			    player_save_pipeline_world_quest_pending(GET_PID(victim)))
			{
				send_to_char("Their quest history is still being secured.\r\n", ch);
				return;
			}

			resetQuest(victim);

			send_to_char("Someone magically cleared your quest.\r\n", victim);
			send_to_char("You've cleared his quest.\r\n", ch);
			return;
		}
		else if (isname(name, "stat") && IS_TRUSTED(ch))
		{
			pc_only_data *pcdata;

			if (!*who)
			{
				send_to_char("Whos quest do you want to examine?\r\n", ch);
				return;
			}
			if (!(victim = ParseTarget(ch, who)))
			{
				send_to_char("Hmm, nobody around here by that name.\r\n", ch);
				return;
			}
			if (IS_NPC(victim))
			{
				send_to_char("Hmm, mobs don't have quests.  Try again.\n\r", ch);
				return;
			}
			pcdata = victim->only.pc;
			// One big string.. rawr.
			snprintf(
				buf, MAX_STRING_LENGTH,
				"Quest for %s (PID %d): \n\rActive: %s, Level: %d, Type: %s, Started: %s, Accomplished: %s\n\r"
				"Bartender Vnum: %d, Shares left: %d, Original Questor PID: %d, Can share: %s\n\r"
				"Target Mob Vnum: %d, Number Killed: %d out of %d needed.\n\r"
				"Zone: %s (%d), Map room: %s (%d), Map purchased: %s.\n\r",
				J_NAME(victim), GET_PID(victim), YESNO(pcdata->quest_active),
				pcdata->quest_level,
				(pcdata->quest_type == FIND_AND_ASK)	   ? "ASK" :
				(pcdata->quest_type == FIND_AND_KILL)	   ? "KILL" :
				(pcdata->quest_type == FIND_AND_SOMETHING) ? "SOMETHING" :
									     "UNKNOWN",
				YESNO(pcdata->quest_started), YESNO(pcdata->quest_accomplished),
				pcdata->quest_giver, pcdata->quest_shares_left,
				pcdata->quest_receiver,
				YESNO(GET_PID(victim) == pcdata->quest_receiver),
				pcdata->quest_mob_vnum, pcdata->quest_kill_how_many,
				pcdata->quest_kill_original,
				zone_table[real_zone0(pcdata->quest_zone_number)].name,
				pcdata->quest_zone_number,
				world[real_room0(pcdata->quest_map_room)].name,
				pcdata->quest_map_room, YESNO(pcdata->quest_map_bought));
			send_to_char(buf, ch);

			return;
		}
	}

	const auto availability = world_quest_refresh(ch);
	if (availability != world_quest_target_status::valid || !ch->only.pc->quest_active ||
	    ch->only.pc->quest_accomplished)
	{
		world_quest_describe(ch, availability);
		gmcp_quest_status(ch, availability);
		return;
	}

	if (*name)
		if (isname(name, "share"))
		{
			if (world_quest_share_limit() == 0)
			{
				send_to_char(
					"Quests can't be shared. Each adventurer takes their own from a bartender.\r\n",
					ch);
				return;
			}

			if (ch->only.pc->quest_receiver != GET_PID(ch))
			{
				send_to_char("Only the quest receiver can share the quest.\r\n",
					     ch);
				return;
			}

			/*if(ch->only.pc->quest_kill_how_many != 0)
			{
			  send_to_char("You already started the quest alone, so finish it alone!\r\n", ch);
			  return;
			}*/
			// A quest granted under a higher limit keeps no more shares than the current one.
			ch->only.pc->quest_shares_left =
				MIN(ch->only.pc->quest_shares_left, world_quest_share_limit());
			if (ch->only.pc->quest_shares_left == 0)
			{
				send_to_char("You cant share this quest with more people.\r\n", ch);
				return;
			}

			if (!*who)
			{
				send_to_char("Who do you want to share your quest with?\r\n", ch);
				return;
			}

			victim = ParseTarget(ch, who);
			if (!victim)
			{
				send_to_char("Hmm, who do you mean?\r\n", ch);
				return;
			}

			if (IS_NPC(victim) || victim->only.pc->quest_active ||
			    victim->only.pc->quest_replacement_due)
			{
				send_to_char("Your fellow adventurer is already on a task.\r\n",
					     ch);
				return;
			}

			if (!is_linked_to(ch, victim, LNK_CONSENT))
			{
				send_to_char(
					"Your fellow adventurer needs to consent you first.\r\n",
					ch);
				return;
			}

			if (ch->only.pc->quest_level <
			    GET_LEVEL(victim) - get_property("world.quest.level.high.value", 6))
			{
				send_to_char("They are much too experienced for that quest!\r\n",
					     ch);
				return;
			}

			if (ch->only.pc->quest_level >
			    GET_LEVEL(victim) + get_property("world.quest.level.low.value", 6))
			{
				send_to_char("They are too inexperienced for that quest!\r\n", ch);
				return;
			}

			if (sql_world_quest_can_do_another(victim) < 1)
			{
				send_to_char(
					"You are unable to receive a new quest, maybe you have already done a few recently?\r\n",
					victim);
				send_to_char(
					"They are unable to receive your quest, you need to find another friend to join you.\r\n",
					ch);
				return;
			}

			if (sql_world_quest_done_already(victim, ch->only.pc->quest_mob_vnum))
			{
				send_to_char(
					"You are unable to receive a new quest, maybe you have already done this quest??\r\n",
					victim);
				send_to_char("They've already done this quest!\r\n", ch);
				return;
			}
			const int remaining = ch->only.pc->quest_type == FIND_AND_KILL ?
						      ch->only.pc->quest_kill_original -
							      ch->only.pc->quest_kill_how_many :
						      1;
			const auto recipient = world_quest_policy_check_target(
				victim, ch->only.pc->quest_origin_room, ch->only.pc->quest_level,
				ch->only.pc->quest_zone_number, ch->only.pc->quest_mob_vnum,
				ch->only.pc->quest_type, remaining);
			if (recipient.status != world_quest_target_status::valid)
			{
				send_to_char(
					"Your fellow adventurer cannot currently use this task's route or target.\r\n",
					ch);
				return;
			}
			resetQuest(victim);

			ch->only.pc->quest_shares_left--;

			send_to_char("You receive a quest.\r\n", victim);

			send_to_char("You've shared your quest.\r\n", ch);

			victim->only.pc->quest_active = ch->only.pc->quest_active;
			victim->only.pc->quest_mob_vnum = ch->only.pc->quest_mob_vnum;
			victim->only.pc->quest_type = ch->only.pc->quest_type;
			victim->only.pc->quest_accomplished = ch->only.pc->quest_accomplished;
			victim->only.pc->quest_started = ch->only.pc->quest_started;
			victim->only.pc->quest_zone_number = ch->only.pc->quest_zone_number;
			victim->only.pc->quest_giver = ch->only.pc->quest_giver;
			victim->only.pc->quest_level = ch->only.pc->quest_level;
			victim->only.pc->quest_origin_room = ch->only.pc->quest_origin_room;
			victim->only.pc->quest_receiver = ch->only.pc->quest_receiver;
			victim->only.pc->quest_kill_how_many = ch->only.pc->quest_kill_how_many;
			victim->only.pc->quest_kill_original = ch->only.pc->quest_kill_original;
			victim->only.pc->quest_map_room =
				recipient.map_room >= 0 ? world[recipient.map_room].number : 0;
			mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS);
			mark_player_dirty_components(GET_PID(victim), PLAYER_COMPONENT_STATUS);
			world_quest_describe(victim, recipient.status);
			gmcp_quest_status(victim, recipient.status);

			return;
		}

	world_quest_describe(ch, availability);
	gmcp_quest_status(ch, availability);
}

void world_quest_describe(P_char ch, world_quest_target_status availability)
{
	using status = world_quest_target_status;
	if (!ch || IS_NPC(ch))
		return;
	if (ch->only.pc->quest_replacement_due)
	{
		send_to_char(
			"Your task is no longer available. Ask a bartender for a free replacement. Your earned progress and purchased map are retained.\r\n",
			ch);
		return;
	}
	if (!ch->only.pc->quest_active)
	{
		send_to_char("You don't have a quest!\r\n", ch);
		return;
	}
	if (ch->only.pc->quest_accomplished)
	{
		send_to_char("This quest is already finished, go talk to the quest master!\r\n",
			     ch);
		return;
	}
	if (availability != status::valid)
	{
		const char *message =
			availability == status::blocked ?
				"Your task is temporarily blocked by your current condition or travel abilities." :
			availability == status::needs_origin ?
				"This older task needs a bartender to check its travel origin." :
				"I cannot prove that your task is usable right now. Ask a bartender to check it.";
		send_to_char(message, ch);
		send_to_char("\r\nYour task and earned progress have been kept.\r\n", ch);
		return;
	}
	char buf[MAX_STRING_LENGTH];
	const int giver = real_mobile(ch->only.pc->quest_giver);
	const char *giver_name = giver >= 0 && mob_index[giver].desc2 ? mob_index[giver].desc2 :
									"A bartender";
	checked_snprintf(buf, MAX_STRING_LENGTH, "%s gave you the following quest:\r\n",
			 giver_name);
	send_to_char(buf, ch);

	const int target = real_mobile(ch->only.pc->quest_mob_vnum);
	const int zone = real_zone(ch->only.pc->quest_zone_number);
	if (target < 0 || !mob_index[target].desc2 || zone < 0)
	{
		send_to_char(
			"Your quest details are unavailable. Please ask a bartender to check your task.\r\n",
			ch);
	}
	else if (ch->only.pc->quest_type == FIND_AND_ASK)
	{
		checked_snprintf(buf, MAX_STRING_LENGTH, "Go ask %s in %s about the %s.\r\n",
				 mob_index[target].desc2, zone_table[zone].name,
				 month_name[time_info.month]);
		send_to_char(buf, ch);
	}
	else if (ch->only.pc->quest_type == FIND_AND_KILL)
	{
		checked_snprintf(
			buf, MAX_STRING_LENGTH, "Go kill %d %s (%d left) in %s!\r\n",
			ch->only.pc->quest_kill_original, mob_index[target].desc2,
			(ch->only.pc->quest_kill_original - ch->only.pc->quest_kill_how_many),
			zone_table[zone].name);
		send_to_char(buf, ch);
	}

	if (ch->only.pc->quest_map_bought == 1)
	{
		send_to_char("You also got some additional information from the quest master:\r\n",
			     ch);
		show_map_at(ch, real_room(ch->only.pc->quest_map_room));
	}

	if (ch->only.pc->quest_receiver != GET_PID(ch))
	{
		send_to_char("&+RThis quest was shared with you&n.\r\n", ch);
	}
	else
	{
		send_to_char("&+RThis quest was given to you&n.\r\n", ch);
		if (world_quest_share_limit() > 0)
		{
			snprintf(buf, MAX_STRING_LENGTH,
				 "You can share this quest with %d more people.\r\n",
				 MIN(ch->only.pc->quest_shares_left, world_quest_share_limit()));
			send_to_char(buf, ch);
		}
	}

	send_to_char(
		"If you're unable to finish it, go to the quest master and ask him to &+Wabandon&n your quest!\r\n",
		ch);
}

world_quest_target_status world_quest_refresh(P_char ch, int bartender_origin)
{
	using status = world_quest_target_status;
	if (!ch || IS_NPC(ch))
		return status::unproven;
	if (ch->only.pc->quest_active && player_save_pipeline_world_quest_pending(GET_PID(ch)))
		return status::unproven;
	auto &quest = *ch->only.pc;
	if (quest.quest_accomplished)
		return status::valid;
	if (quest.quest_replacement_due)
		return status::unavailable;
	if (!quest.quest_active)
		return status::valid;
	const int remaining = quest.quest_type == FIND_AND_KILL ?
				      quest.quest_kill_original - quest.quest_kill_how_many :
				      1;
	const int origin = quest.quest_origin_room > 0 ? quest.quest_origin_room : bartender_origin;
	const auto checked = world_quest_policy_check_target(ch, origin, quest.quest_level,
							     quest.quest_zone_number,
							     quest.quest_mob_vnum, quest.quest_type,
							     remaining);
	bool changed = false;
	if (checked.status == status::unavailable)
	{
		quest.quest_active = 0;
		quest.quest_replacement_due = 1;
		changed = true;
	}
	const int map = checked.status == status::valid && checked.map_room >= 0 ?
				world[checked.map_room].number :
				0;
	if (quest.quest_map_room != map)
	{
		quest.quest_map_room = map;
		if (ch->desc)
			ch->desc->gmcp_quest_map_sent = 0;
		changed = true;
	}
	if (checked.status == status::valid && quest.quest_origin_room <= 0 && origin > 0)
	{
		quest.quest_origin_room = origin;
		changed = true;
	}
	if (changed)
		mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS);
	return checked.status;
}

bool world_quest_replace(P_char ch, P_char giver)
{
	if (!ch || IS_NPC(ch) || player_save_pipeline_world_quest_pending(GET_PID(ch)) || !giver ||
	    !IS_NPC(giver) || ch->in_room < 0 || ch->in_room > top_of_world ||
	    giver->in_room != ch->in_room || !ch->only.pc->quest_replacement_due ||
	    ch->only.pc->quest_accomplished)
		return false;
	auto &quest = *ch->only.pc;
	const int remaining = quest.quest_type == FIND_AND_KILL ?
				      quest.quest_kill_original - quest.quest_kill_how_many :
				      1;
	if (remaining < 1)
		return false;
	world_quest_target target;
	const int origin = world[ch->in_room].number;
	if (world_quest_policy_select_target(ch, origin, quest.quest_level, target,
					     quest.quest_type,
					     remaining) != QUEST_CREATION_NO_FAILURE)
		return false;
	quest.quest_active = 1;
	quest.quest_replacement_due = 0;
	quest.quest_mob_vnum = target.mob_vnum;
	quest.quest_zone_number = zone_table[target.zone].number;
	quest.quest_origin_room = origin;
	quest.quest_giver = GET_VNUM(giver);
	quest.quest_map_room = target.map_room >= 0 ? world[target.map_room].number : 0;
	mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS);
	return true;
}

// The caller validates the real interaction and captures its origin before payment.
// Keep those VNUMs by value so a continuation cannot rediscover a different giver
// instance or use the customer's later position as the accepted origin.
// Returns TRUE if successful, and FALSE if failed.
bool createQuestForGiverVnum(P_char ch, int giver_vnum, int origin_vnum,
			     quest_creation_failure *failure)
{
	if (failure)
		*failure = QUEST_CREATION_NO_FAILURE;
	if (!ch || IS_NPC(ch) || player_save_pipeline_world_quest_pending(GET_PID(ch)) ||
	    giver_vnum <= 0 || origin_vnum <= 0 || real_room(origin_vnum) == NOWHERE)
	{
		if (failure)
			*failure = QUEST_CREATION_INVALID_ACTOR;
		return FALSE;
	}
	world_quest_target target;
	const auto outcome =
		world_quest_policy_select_target(ch, origin_vnum, GET_LEVEL(ch), target);
	if (outcome != QUEST_CREATION_NO_FAILURE)
	{
		if (failure)
			*failure = outcome;
		return FALSE;
	}
	const int quest_kill_original =
		MIN(difficulty_scale_world_quest_kills(number(7, 9)), target.usable_count - 1);
	ch->only.pc->quest_shares_left = world_quest_share_limit();
	ch->only.pc->quest_active = 1;
	ch->only.pc->quest_mob_vnum = target.mob_vnum;
	ch->only.pc->quest_type = target.type;
	ch->only.pc->quest_accomplished = 0;
	ch->only.pc->quest_started = time(NULL);
	ch->only.pc->quest_zone_number = zone_table[target.zone].number;
	ch->only.pc->quest_giver = giver_vnum;
	ch->only.pc->quest_level = GET_LEVEL(ch);
	ch->only.pc->quest_origin_room = origin_vnum;
	ch->only.pc->quest_replacement_due = 0;
	ch->only.pc->quest_receiver = GET_PID(ch);
	ch->only.pc->quest_kill_how_many = 0;
	ch->only.pc->quest_kill_original = quest_kill_original;
	ch->only.pc->quest_map_room = target.map_room >= 0 ? world[target.map_room].number : 0;
	ch->only.pc->quest_map_bought = 0;
	mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS);
	return TRUE;
}

// Synchronous callers still pass a live giver.  Validate it before reducing
// the identity to the stable vnum used by deferred continuations.
bool createQuest(P_char ch, P_char giver, quest_creation_failure *failure)
{
	if (!giver || !ch || IS_NPC(ch) || (IS_PC(giver) && !IS_TRUSTED(giver)) ||
	    giver->in_room != ch->in_room || ch->in_room == NOWHERE)
	{
		if (failure)
			*failure = QUEST_CREATION_INVALID_ACTOR;
		return FALSE;
	}
	return createQuestForGiverVnum(ch, GET_VNUM(giver), world[ch->in_room].number, failure);
}

void show_map_at(P_char ch, int room)
{
	if (!ch || !IS_ALIVE(ch) || IS_NPC(ch) || ch->only.pc->quest_map_bought != 1)
		return;
	if (room < 0 || room > top_of_world)
	{
		send_to_char("I cannot verify a map for your current quest right now.\r\n", ch);
		return;
	}

	// Match gmcp_quest_map's synchronous viewpoint without transfer hooks,
	// occupant-list changes or interrupting the viewer's current action.
	const int old_room = ch->in_room;
	ch->in_room = room;
	display_map_room(ch, room, 20, 999, 1);
	ch->in_room = old_room;
}

int quest_buy_map(P_char ch, world_quest_target_status availability)
{
	if (!IS_ALIVE(ch) || IS_NPC(ch) || availability != world_quest_target_status::valid ||
	    !ch->only.pc->quest_active || ch->only.pc->quest_replacement_due ||
	    ch->only.pc->quest_accomplished)
	{
		return 0;
	}

	if (ch->only.pc->quest_map_bought == 1)
	{
		send_to_char(
			"Your memory is bad, you dont have to pay me for this, you can just type 'quest'\r\n.",
			ch);
		return 0;
	}

	const int map_room =
		ch->only.pc->quest_map_room > 0 ? real_room(ch->only.pc->quest_map_room) : NOWHERE;
	if (map_room < 0)
	{
		send_to_char("I cannot verify a map for your current quest right now.\r\n", ch);
		return 0;
	}
	ch->only.pc->quest_map_bought = 1;
	mark_player_dirty_components(GET_PID(ch), PLAYER_COMPONENT_STATUS);
	send_to_char(
		"The 'quest' command will now show you additional information about the quest.\r\n",
		ch);

	if (map_room > 0)
	{
		show_map_at(ch, map_room);

		// show_map_at emits the paid map through Quest.Map as well as text.
		if (ch->desc)
			ch->desc->gmcp_quest_map_sent = 1;
		gmcp_quest_status(ch, availability);
	}

	return 1;
}

// Return random vnum for an item from a zone's boot-time cache.
int getItemFromZone(int zone)
{
	return world_quest_policy_random_item(zone);
}

int getQuestItemFromZone(int zone, int quest_level)
{
	return world_quest_policy_random_quest_item(zone, quest_level);
}

bool isInvalidQuestZone(int zone_number)
{
	return world_quest_policy_zone_is_invalid(zone_number);
}

// Called from comm.c to populate the boot-time world-quest catalog and avg_mob_level.
int calc_zone_mob_level()
{
	return world_quest_policy_bootstrap() ? 0 : -1;
}
