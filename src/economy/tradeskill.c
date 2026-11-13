/****************************************************************************
 *
 *  File: randomeq.c                                           Part of Duris
 *  Usage: randomboject.c
 *  Copyright  1990, 1991 - see 'license.doc' for complete information.
 *  Copyright 1994 - 2008 - Duris Systems Ltd.
 *  Created by: Kvark                   Date: 2002-04-18
 * ***************************************************************************
 */

#define TROPHY

#include "core/prototypes.h"
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "item/item_movement_transaction.h"
#include "core/utility.h"
#include "core/utils.h"
#include "economy/tradeskill.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "world/achievements.h"
#include "combat/arena.h"
#include "combat/arenadef.h"
#include "guild/assocs.h"
#include "world/epic_transaction.h"
#include "guild/guildhall.h"
#include "combat/justice.h"
#include "world/map.h"
#include "core/mm.h"
#include "item/objmisc.h"
#include "specs/specs.barovia.h"
#include "specs/specs.eth2.h"
#include "specs/specs.juiblex.h"
#include "specs/specs.keleks.h"
#include "world/specs.prototypes.h"
#include "specs/specs.ravenloft.h"
#include "specs/specs.snogres.h"
#include "specs/specs.winterhaven.h"
#include "specs/specs.zion.h"
#include "magic/spells.h"
#include "sql/sql_player.h"
#include "world/vnum.obj.h"
#include "economy/crafting.h"
#include "economy/currency_transaction.h"
#include "core/files.h"
#include "net/gmcp.h"
#include "persistence/persistence_checkpoint.h"
#include "player/player_save_pipeline.h"
#include "world/weather.h"
#include "core/safe_format.h"
#include "abilities/abilities.h"

#define SMITH_MAX_ITEMS 20

namespace
{
bool grant_tradeskill_item(P_char ch, P_obj object)
{
	if (object && item_creation_grant_submit_to_player(ch, object, ch))
		return true;
	if (object)
		extract_obj(object, FALSE);
	send_to_char("The ownership authority is busy; no tradeskill item was created.\r\n", ch);
	return false;
}
}

/*
 * external variables
 */
extern Skill skills[];

namespace
{
struct epic_store_context
{
	int object_vnum;
	int cost;
	bool forest_sight;
};

void epic_store_committed(P_char pl, bool committed, const epic_command_result &, unsigned int,
			  const uint8_t *raw_context, size_t context_size)
{
	if (!committed || context_size != sizeof(epic_store_context))
	{
		send_to_char("Kannard says, 'Your epic purchase was declined.'\n", pl);
		return;
	}
	epic_store_context context = {};
	memcpy(&context, raw_context, sizeof(context));
	P_obj obj = read_object(context.object_vnum, VIRTUAL);
	if (!obj)
	{
		send_to_char("Kannard cannot find that item; your epics are being refunded.\n", pl);
		epic_transaction_submit(pl, context.cost, epic_reason_type::store_purchase,
					context.object_vnum, 0, critical_source_site::recovery,
					critical_deadline_class::recovery, nullptr, nullptr, 0);
		return;
	}
	if (context.forest_sight)
		SET_BIT(obj->bitvector5, AFF5_FOREST_SIGHT);
	send_to_char("Kannard says, 'Ah, good choice! Quite a rare item!'\n", pl);
	act("You now have $p!\r\n", FALSE, pl, obj, 0, TO_CHAR);
	epiclog(56, "%s bought '%s' (%d) at the epic store for %d epics.", J_NAME(pl),
		obj->short_description, context.object_vnum, context.cost);
	obj_to_char(obj, pl);
	if (!do_save_silent(pl, 1))
		logit(LOG_WIZ, "Failed to save %s after epic store purchase.", GET_NAME(pl));
}

bool submit_epic_store_purchase(P_char pl, int object_vnum, int cost, bool forest_sight = false)
{
	const epic_store_context context = { object_vnum, cost, forest_sight };
	if (epic_transaction_submit(pl, -cost, epic_reason_type::store_purchase, object_vnum,
				    EPIC_COMMAND_REQUIRE_FUNDS, critical_source_site::command,
				    critical_deadline_class::interactive, epic_store_committed,
				    &context, sizeof(context)))
		return true;
	send_to_char("The epic transaction service is busy. Please try again.\n", pl);
	return false;
}

void tradeskill_reset_committed(P_char pl, bool committed, const epic_command_result &,
				unsigned int, const uint8_t *, size_t)
{
	if (!committed)
	{
		send_to_char("Your tradeskill reset was declined.\n", pl);
		return;
	}
	if (!sql_delete_player_recipes(GET_PID(pl)))
	{
		send_to_char("Your reset could not be recorded; your epics are being refunded.\n",
			     pl);
		epic_transaction_submit(pl, 200, epic_reason_type::tradeskill_reset, 0, 0,
					critical_source_site::recovery,
					critical_deadline_class::recovery, nullptr, nullptr, 0);
		return;
	}
	for (int skill : { SKILL_FORGE, SKILL_MINE, SKILL_CRAFT })
	{
		pl->only.pc->skills[skill].taught = 0;
		pl->only.pc->skills[skill].learned = 0;
	}
	send_to_char("Your teacher cleanses your mind; you feel renewed.\n", pl);
	if (!do_save_silent(pl, 1))
		logit(LOG_WIZ, "Failed to save %s after tradeskill reset.", GET_NAME(pl));
	CharWait(pl, PULSE_VIOLENCE);
}
} // namespace
extern struct zone_data *zone_table;
extern const char *material_names[];
extern P_char character_list;
extern P_desc descriptor_list;
extern P_index mob_index;
extern P_index obj_index;
extern P_obj object_list;
extern P_room world;
extern const int top_of_world;
extern char debug_mode;
extern const char *race_types[];
extern const char *rude_ass[];

// extern const int material_absorbtion[][];
extern float fake_sqrt_table[];
extern int pulse;
extern int arena_hometown_location[];
extern struct arena_data arena;
extern struct agi_app_type agi_app[];
extern struct dex_app_type dex_app[];
extern struct message_list fight_messages[];
extern struct str_app_type str_app[];
extern struct time_info_data time_info;
extern struct zone_data *zone_table;
extern void material_restrictions(P_obj);
extern int find_map_place();
extern struct forge_item forge_item_list[];

int get_mincircle(int spell);
int calc_ore_cost(P_char ch, P_obj ore);
int calc_gem_cost(P_char ch, P_obj gem, bool randommob);

int forge_prices[] = { 2000, 5000, 15000, 30000, 50000 };

struct smith_data
{
	int vnum;
	short int items[SMITH_MAX_ITEMS + 1];
} smith_array[] = { { 76010, { 131, 132, 53, 54, 55, 56, -1 } },
		    { 82518, { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, -1 } },
		    { 22269, { 92, 93, 94, 95, 96, -1 } },
		    { 76691, { 88, 89, 91, 103, -1 } },
		    { 20240, { 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, -1 } },
		    { 40712, { 41, 42, 43, 44, 45, 46, 47, -1 } },
		    { 99716, { 62, 63, 64, 65, 66, 67, 68, 69, 76, 77, 78, 79, 80, -1 } },
		    { 9412, { 60, 61, 49, 50, 70, 71, 72, 73, 73, 75, -1 } },
		    { 96058, { 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 119, -1 } },
		    { 6002, { 6, 7, 8, 9, 10, 23, 24, 25, 26, 30, 37, 38, 39, 40, 113, -1 } },
		    { 66410, { 127, 128, 129, 130, 88, 89, 90, 91, -1 } },
		    { 1420, { 70, 57, 58, 59, 48, 36, 38, 37, 39, 40, -1 } }, // kobolds
		    { 96916,
		      { 57, 58, 59, 27, 29, 97, 101, 102, 107, 109, 112, -1 } }, // troll caves
		    { 75628, { 12, 13, 14, 66, 67, 67, 64, 65, 77, 76, -1 } }, // citadel
		    { 76502, { 60, 61, 34, 31, 32, 33, 74, 75, 88, 89, 92, -1 } },
		    { 28917, { 46, 47, 49, 45, 35, 78, 77, 86, 87, 85, -1 } }, // torg
		    { 37755, { 30, 26, 22, 23, 24, 25, 21, 11, 12, 13, 14, 15, 16, -1 } }, // nax
		    { 0, { -1 } } };

P_obj get_hammer(P_char ch)
{
	P_obj t_obj, next_obj;

	for (t_obj = ch->carrying; t_obj; t_obj = next_obj)
	{
		next_obj = t_obj->next_content;
		if (obj_index[t_obj->R_num].virtual_number == HAMMER_VNUM)
		{
			return t_obj;
		}
	}

	return NULL;
}

int parchment_forge(P_obj obj, P_char ch, int cmd, char * /*arg*/)
{
	P_char temp_ch;
	if (!ch)
		return FALSE;

	if (cmd != CMD_RECITE)
		return FALSE;

	temp_ch = obj->loc.wearing;

	if (!temp_ch)
		return FALSE;
	;

	if (ch != temp_ch)
		return FALSE;

	// This is broken atm.. and there's no way to forge atm as "waiter()" and "barmaid()" aren't linked to any mobs.
	// If you want to fix it, find some mob that makes sense to add "smith()" to, and add it to their proc.
	//   A warning though; this is a mess.
	return FALSE;

	for (int tmp = 1; tmp < MAX_FORGE_ITEMS; tmp++)
	{
		if (ch->only.pc->learned_forged_list[tmp] == obj->value[0])
		{
			send_to_char("You already know how to forge this item.\r\n", ch);
			return TRUE;
		}

		if (forge_item_list[ch->only.pc->learned_forged_list[obj->value[0]]].skill_min >
		    GET_CHAR_SKILL(ch, SKILL_FORGE))
		{
			send_to_char("This parchment contains smithing too advanced for you.\r\n",
				     ch);
			return TRUE;
		}
		if (ch->only.pc->learned_forged_list[tmp] == 0)
		{
			ch->only.pc->learned_forged_list[tmp] = obj->value[0];
			send_to_char("You learn a new item to forge!\r\n", ch);
			extract_obj(obj, TRUE); // Not an arti, but 'in game.'
			return TRUE;
		}
	}
}

void create_parchment(P_char ch)
{
	P_obj obj = read_object(PARCHMENT_VNUM, VIRTUAL);
	if (!obj)
		return;

	int howmany = 0;
	for (int tmp = 1; tmp < MAX_FORGE_ITEMS; tmp++)
	{
		if (forge_item_list[tmp].id == 0)
			break;

		howmany++;
	}
	obj->value[0] = number(1, howmany);

	// If it's not rare dont load it!
	if (forge_item_list[ch->only.pc->learned_forged_list[obj->value[0]]].how_rare <
	    number(1, 100))
		return;

	obj_to_room(obj, ch->in_room);
	act("$n's digging turns up $p&n!", TRUE, ch, obj, 0, TO_ROOM);
	act("Your digging turns up $p&n!", TRUE, ch, obj, 0, TO_CHAR);
}

P_obj forge_create(int choice, P_char ch, int material)
{
	char dummy[MAX_INPUT_LENGTH];
	char short_desc[MAX_STRING_LENGTH];
	char long_desc[MAX_INPUT_LENGTH];
	char keywords[MAX_INPUT_LENGTH];
	P_obj obj;

	if (!(obj = read_object(1255, VIRTUAL)))
	{
		wizlog(56, "unabled to load object 1255");
		return 0;
	}

	snprintf(keywords, MAX_INPUT_LENGTH, "%s", forge_item_list[choice].keywords);
	snprintf(dummy, MAX_INPUT_LENGTH, "%s", forge_item_list[choice].short_desc);
	checked_snprintf_runtime(short_desc, MAX_STRING_LENGTH, dummy, GET_NAME(ch));
	snprintf(dummy, MAX_INPUT_LENGTH, "%s", forge_item_list[choice].long_desc);
	checked_snprintf_runtime(long_desc, MAX_INPUT_LENGTH, dummy, GET_NAME(ch));

	set_short_description(obj, short_desc);
	set_long_description(obj, long_desc);
	set_keywords(obj, keywords);

	obj->material = material;
	obj->affected[0].location = forge_item_list[choice].loc0;
	obj->affected[0].modifier =
		number(forge_item_list[choice].min0, forge_item_list[choice].max0);
	obj->affected[1].location = forge_item_list[choice].loc1;
	obj->affected[1].modifier =
		number(forge_item_list[choice].min1, forge_item_list[choice].max1);

	SET_BIT(obj->wear_flags, ITEM_TAKE);
	SET_BIT(obj->wear_flags, forge_item_list[choice].wear_flags);

	SET_BIT(obj->bitvector, forge_item_list[choice].aff1);
	SET_BIT(obj->bitvector2, forge_item_list[choice].aff2);
	SET_BIT(obj->bitvector3, forge_item_list[choice].aff3);
	SET_BIT(obj->bitvector4, forge_item_list[choice].aff4);

	obj->anti_flags |= forge_item_list[choice].classes;

	if (forge_item_list[choice].allow_anti)
		obj->extra_flags = ITEM_ALLOWED_CLASSES;
	;
	if (isname("quiver", obj->name))
	{
		obj->value[0] = number(20, 80);
		obj->value[1] = number(0, 1);
		obj->value[2] = 1;
		obj->value[3] = 0;
		obj->type = ITEM_QUIVER;
	}
	else
		obj->type = ITEM_ARMOR;
	return obj;
}

void forge_describe(int choice, P_char ch)
{
	char buffer[1024];
	int i;

	snprintf(buffer, 1024, "To create %s you need:\n", forge_item_list[choice].short_desc);
	for (i = 0; i < 5 && forge_item_list[choice].ore_needed[i]; i++)
		APPENDF(buffer, "%s\n",
			obj_index[real_object(forge_item_list[choice].ore_needed[i])].desc2);

	send_to_char(buffer, ch);
	if (i <= 0 || i > (int)(sizeof(forge_prices) / sizeof(forge_prices[0])))
	{
		logit(LOG_DEBUG, "forge_describe: invalid ore count %d for forge item %d.", i,
		      choice);
		send_to_char("This forge recipe is misconfigured; please notify an Immortal.\n",
			     ch);
		return;
	}
	snprintf(buffer, 1024, "It will cost you %s to forge this.\n",
		 coin_stringv(forge_prices[i - 1]));
	send_to_char(buffer, ch);
}

P_obj check_foundry(P_char ch)
{
	P_obj t_obj;

	for (t_obj = world[ch->in_room].contents; t_obj; t_obj = t_obj->next_content)
	{
		if (obj_index[t_obj->R_num].virtual_number == 361)
		{
			return t_obj;
		}
	}

	return NULL;
}

void do_forge(P_char ch, char *argument, int /*cmd*/)
{
	crafting_handle_command(ch, CRAFTING_MODE_FORGE, argument);
}

/* OLD FORGE CODE:
  if (GET_CHAR_SKILL(ch, SKILL_FORGE) == 0){
    send_to_char("&+LYou dont know how to forge.\r\n", ch);
    return;
  }

  foundry = check_foundry(ch);

  if (!foundry)
   { // No furnace/foundry/forge in room
  act("&+LYou need to be by your foundry to forge...&n", FALSE, ch, 0, 0, TO_CHAR);
  return;
   }

  *buf1 = '\0';
  if (!*argument){
    snprintf(buf1 + strlen(buf1), MAX_STRING_LENGTH - strlen(buf1), "Syntax: 'forge info #', 'forge create #'\n");
    snprintf(buf1 + strlen(buf1), MAX_STRING_LENGTH - strlen(buf1), "You know how to forge the following items:\n");
    if(IS_TRUSTED(ch))
      for (int tmp = 1; tmp < MAX_FORGE_ITEMS; tmp++)
      {
        if(forge_item_list[tmp].short_desc == NULL)
          break;
        snprintf(buf1 + strlen(buf1), MAX_STRING_LENGTH - strlen(buf1), "%d -  %s\n", tmp, forge_item_list[tmp].short_desc);
      }
    else

      for (int tmp = 1; tmp < MAX_FORGE_ITEMS; tmp++)
      {
        if(ch->only.pc->learned_forged_list[tmp] != 0)
          snprintf(buf1 + strlen(buf1), MAX_STRING_LENGTH - strlen(buf1), "%d -  %s\n", tmp, forge_item_list[ch->only.pc->learned_forged_list[tmp]].short_desc );
      }
    strcat(buf1, "\n");
    page_string(ch->desc, buf1, 1);
    return;
  }

  snprintf(buf1, MAX_STRING_LENGTH, "");
  half_chop(argument, first, rest);
  half_chop(rest, second, rest);
  choice = (ush_int) atoi(second);

  if (choice < 1 || choice >= MAX_FORGE_ITEMS) {
    send_to_char("This is not a valid number.\n", ch);
    return;
  }

  if (is_abbrev(first, "info"))
  {

    if(!choice){
      send_to_char("Missing forge list number 'forge info 1'.\r\n", ch);
      return;
    }
    if(IS_TRUSTED(ch))
      choice = choice;
    else
      choice  = ch->only.pc->learned_forged_list[choice];

    if(!choice){
      send_to_char("You do not know how to make that. Type 'forge' to get a list of know items..\r\n", ch);
      return;
    }

    forge_describe(choice, ch);
    return;
  }

  if (is_abbrev(first, "create"))
  {
    if(!choice){
      send_to_char("Missing forge list number 'forge create 1'.\r\n", ch);
      return;
    }
    if(IS_TRUSTED(ch))
      choice = choice;
    else

      choice  = ch->only.pc->learned_forged_list[choice];
    if(!choice){
      send_to_char("You do not know how to make that. Type 'forge' to get a list of know items..\r\n", ch);
      return;
    }

    hammer = get_hammer(ch);
    if(!hammer)
    {
      act("You need to have a forge hammer in your inventory.", FALSE, ch, 0, 0, TO_CHAR);
      return;
    }

    if(forge_item_list[choice].short_desc == NULL)
    {
      send_to_char("Yes you are a god, but why try to create something that's not even possible?!?!.\r\n", ch);
      return;
    }

    int material = 0;
    int NEEDED = 0;
    int FOUND = 0;
    P_obj t_obj, next_obj;
    while(forge_item_list[choice].ore_needed[i] != 0)
    {
      NEEDED++;
      for (t_obj = ch->carrying; t_obj; t_obj = next_obj)
      {
        next_obj = t_obj->next_content;
        if(obj_index[t_obj->R_num].virtual_number == forge_item_list[choice].ore_needed[i]){
          if(!material)
            material = t_obj->material;
          snprintf(buf1, MAX_STRING_LENGTH, "You start to work on %s\n", t_obj->short_description );
          send_to_char(buf1, ch);
          extract_obj(t_obj);
          FOUND++;
          if(!number(0,2))
            if(GET_CHAR_SKILL(ch, SKILL_FORGE) < number(0, 99))
            {
              send_to_char("You swing wildly, slip, fall, hurt yourself, and destroy the ore!\r\n", ch);
              return;
            }
          break;
        }
      }
      i++;
    }
    if(FOUND == NEEDED || IS_TRUSTED(ch))
    {
      if(FOUND == 0)
        send_to_char("You are a god! Material type is created from the ore, since you used none it will be wrong..fyi!\n",ch);
      P_obj obj = forge_create(choice, ch, material);
      if (!obj)
        return;
      obj_to_char(obj, ch);
      snprintf(buf1, MAX_STRING_LENGTH, "You finishing forging: %s!\n", obj->short_description);
      send_to_char(buf1, ch);
      wizlog(56, "%s forged %s" , GET_NAME(ch), buf1);
      notch_skill(ch, SKILL_FORGE, 50);
      return;
    }
    else
    {
      send_to_char("You do not  have the required items. Type forge info # to find out what you need. You wasted some ore.\r\n", ch);
      return;
    }
    return;
  }
*/

P_obj get_pole(P_char ch)
{
	P_obj t_obj, next_obj;

	for (t_obj = ch->carrying; t_obj; t_obj = next_obj)
	{
		next_obj = t_obj->next_content;
		if (obj_index[t_obj->R_num].virtual_number == POLE_VNUM ||
		    obj_index[t_obj->R_num].virtual_number == 6025 ||
		    obj_index[t_obj->R_num].virtual_number == 26200 ||
		    obj_index[t_obj->R_num].virtual_number == 43120 ||
		    obj_index[t_obj->R_num].virtual_number == 66709 ||
		    obj_index[t_obj->R_num].virtual_number == 93913 ||
		    obj_index[t_obj->R_num].virtual_number == 29439 ||
		    obj_index[t_obj->R_num].virtual_number == 35234 ||
		    obj_index[t_obj->R_num].virtual_number == 88903 ||
		    obj_index[t_obj->R_num].virtual_number == 300039)
		{
			return t_obj;
		}
	}
	return NULL;
}

// What a round of tradeskill work takes from your vitality, at your rating.
int tradeskill_vitality_cost(const Rolls &rolls, int rating)
{
	return (rolls.number(0, 100) > rating) ? 3 : 2;
}

static int fishing_rounds(P_char ch)
{
	return IS_TRUSTED(ch) ? 2 : (140 - GET_CHAR_SKILL(ch, SKILL_FISHING)) / 4;
}

static int fishing_interval()
{
	return PULSE_VIOLENCE;
}

// The share of your rating a catch pays in experience, in percent, and how it falls.
static int fishing_exp_share()
{
	return 500;
}

static int fishing_exp_step()
{
	return 10;
}

static int fishing_exp_floor()
{
	return 20;
}

static int fishing_exp(int rating, int share)
{
	return (rating * share) / 100;
}

static int fishing_exp_memory()
{
	return 10;
}

// A roll of 0 damages the pole on a catch.
static int fishing_pole_damage_roll(const Rolls &rolls)
{
	return rolls.number(0, 2);
}

std::string fishing_facts(P_char ch)
{
	const int rating = GET_CHAR_SKILL(ch, SKILL_FISHING);
	if (!rating)
		return "  You have not learned to fish.\n";
	return fact("Wait for a bite", real_time((fishing_rounds(ch) + 1) * fishing_interval())) +
	       fact("Chance you catch something", chance_under(rating + 1, 1, 125)) +
	       fact("Experience for a catch",
		    std::to_string(fishing_exp(rating, fishing_exp_share())) + ", falling to " +
			    std::to_string(fishing_exp(rating, fishing_exp_floor()))) +
	       fact("  It recovers after no catch for", game_hours(fishing_exp_memory())) +
	       fact("Vitality each round",
		    show({ tradeskill_vitality_cost(lowest_rolls, rating),
			   tradeskill_vitality_cost(highest_rolls, rating) })) +
	       "    (you stop below 10)\n"
	       "  A catch damages the pole " +
	       one_in(fishing_pole_damage_roll) +
	       " times.\n"
	       "  It takes a pole and water, and it ruins a disguise.\n";
}

void do_fish(P_char ch, char *, int /*cmd*/)
{
	P_obj pole;
	struct fishing_data data;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (IS_NPC(ch) || GET_CHAR_SKILL(ch, SKILL_FISHING) == 0)
	{
		send_to_char("You don't know how to fish.\n", ch);
		return;
	}

	if (get_scheduled(ch, event_fish_check))
	{
		send_to_char("You're already fishing!\n", ch);
		return;
	}

	if (!MIN_POS(ch, POS_STANDING + STAT_NORMAL))
	{
		send_to_char("You're too relaxed to fish.\n", ch);
		return;
	}

	if (!(pole = get_pole(ch)))
	{
		send_to_char(
			"How are you supposed to fish when you don't have anything ready to fish with?\n",
			ch);
		return;
	}

	if (!IS_WATER_ROOM(ch->in_room))
	{
		send_to_char("Well you DO have a fishing pole, but where do you plan to fish???\n",
			     ch);
		return;
	}

	if (IS_DISGUISE(ch))
	{
		send_to_char("Fishing will ruin your disguise!\r\n", ch);
		return;
	}

	// Start fishing
	send_to_char("You cast your pole and start waiting...\n", ch);

	data.room = ch->in_room;
	// Two ticks for Immortals.. for testing
	data.counter = fishing_rounds(ch);

	add_event(event_fish_check, fishing_interval(), ch, 0, 0, 0, &data,
		  sizeof(struct fishing_data));
}

void event_fish_check(P_char ch, P_char /*victim*/, P_obj, void *data)
{
	struct fishing_data *fdata = (struct fishing_data *)data;
	P_obj pole, fish;
	const int fishes[12] = { 293, 294, 295, 318, 319, 330, 332, 333, 334, 335, 355, 356 };
	int random = number(0, 11);
	pole = get_pole(ch);
	struct affected_type *afp, af;

	if (!ch->desc || IS_FIGHTING(ch) || (ch->in_room != fdata->room) ||
	    !MIN_POS(ch, POS_STANDING + STAT_NORMAL) ||
	    IS_SET(ch->specials.affected_by, AFF_HIDE) || IS_IMMOBILE(ch) || !IS_AWAKE(ch) ||
	    IS_STUNNED(ch) || IS_CASTING(ch))
	{
		send_to_char("You stop fishing.\n", ch);
		return;
	}

	if (!IS_WATER_ROOM(ch->in_room))
	{
		send_to_char("You stop fishing.\n", ch);
		return;
	}

	if (IS_DISGUISE(ch))
	{
		send_to_char("Fishing will ruin your disguise!\r\n", ch);
		return;
	}

	if (!pole)
	{
		send_to_char(
			"How are you supposed to fish when you don't have anything ready to fish with?\n",
			ch);
		return;
	}

	if (fdata->counter == 0)
	{
		if (GET_CHAR_SKILL(ch, SKILL_FISHING) < number(1, 125))
		{
			send_to_char("You didn't catch a thing..\n", ch);
			return;
		}

		if (!(fish = read_object(fishes[random], VIRTUAL)))
		{
			wizlog(56, "Bug with fishing no fish with vnum %d", fishes[random]);
			return;
		}

		if (!fishing_pole_damage_roll(live_rolls))
		{
			DamageOneItem(ch, 9, pole, FALSE);
		}

		act("You reel in $p on your fishing pole!", FALSE, ch, fish, NULL, TO_CHAR);
		act("$n reels in $p on $s fishing pole", FALSE, ch, fish, NULL, TO_ROOM);

		// Diminishing returns to stop afk bot-fishing for exp, clears after 10 ticks of not catching anything.
		if (!(afp = get_spell_from_char(ch, SKILL_FISHING)))
		{
			bzero(&af, sizeof(af));
			af.type = SKILL_FISHING;
			af.modifier = fishing_exp_share();
			af.duration = fishing_exp_memory();
			af.flags = AFFTYPE_NOSHOW | AFFTYPE_NODISPEL | AFFTYPE_NOMSG |
				   AFFTYPE_OFFLINE;
			afp = affect_to_char(ch, &af);
		}
		else
		{
			afp->modifier -= fishing_exp_step();
			afp->modifier = MAX(afp->modifier, fishing_exp_floor());
			afp->duration = fishing_exp_memory();
		}

		gain_exp(ch, NULL, fishing_exp(GET_CHAR_SKILL(ch, SKILL_FISHING), afp->modifier),
			 EXP_BOON);

		// fish->timer[0] = time(NULL); Fish no longer decay - drannak 5/13/13
		grant_tradeskill_item(ch, fish);
		return;
	}

	if (GET_VITALITY(ch) < 10)
	{
		send_to_char("You are too exhausted to continue fishing.\n", ch);
		return;
	}

	send_to_char("You continue fishing...\n", ch);
	notch_skill(ch, SKILL_FISHING, 10);
	GET_VITALITY(ch) -= tradeskill_vitality_cost(live_rolls, GET_CHAR_SKILL(ch, SKILL_FISHING));

	fdata->counter--;
	add_event(event_fish_check, fishing_interval(), ch, 0, 0, 0, fdata,
		  sizeof(struct fishing_data));

	// noise distance calc
	for (P_desc i = descriptor_list; i; i = i->next)
	{
		if (i->connected != CON_PLAYING || ch == i->character ||
		    i->character->following == ch ||
		    world[i->character->in_room].zone != world[ch->in_room].zone ||
		    ch->in_room == i->character->in_room ||
		    ch->in_room == real_room(i->character->specials.was_in_room) ||
		    real_room(ch->specials.was_in_room) == i->character->in_room)
		{
			continue;
		}

		int dist = calculate_map_distance(ch->in_room, i->character->in_room);

		if (dist <= 225 && (number(1, 12) < 3))
		{
			zone_spellmessage(
				ch->in_room, TRUE,
				"&+cThe &+Csoft &+csound of &+Cwater&+c splashing can be heard in the distance...&n\r\n",
				"&+cThe &+Csoft &+csound of &+Cwater&+c splashing can be heard to the %s...&n\r\n");
		}
	}
}

int smith(P_char ch, P_char pl, int cmd, char *arg)
{
	struct smith_data *sdata;
	char buffer[256];
	P_obj tobj, needed_ore[5];
	int i, j, choice;

	if (cmd == CMD_SET_PERIODIC)
	{
		return TRUE;
	}

	if (cmd == CMD_PERIODIC && !number(0, 6))
	{
		act("$n hums a soft melody as $e forges another piece of armor.", FALSE, ch, 0, 0,
		    TO_ROOM);
		return TRUE;
	}

	if (cmd != CMD_FORGE)
	{
		return FALSE;
	}

	j = GET_VNUM(ch);
	for (i = 0; smith_array[i].vnum > 0; i++)
	{
		if (smith_array[i].vnum == j)
		{
			break;
		}
	}

	if (smith_array[i].vnum == 0)
	{
		return FALSE;
	}
	else
	{
		sdata = &smith_array[i];
	}

	if (!arg || !*arg)
	{
		act("$n tells you, 'I can forge the following items:'", FALSE, ch, 0, pl, TO_VICT);
		for (i = 0; i < SMITH_MAX_ITEMS && sdata->items[i] != -1; i++)
		{
			snprintf(buffer, 256, "%d) %s\n", i + 1,
				 forge_item_list[sdata->items[i]].short_desc);
			send_to_char(buffer, pl);
		}
		return TRUE;
	}

	choice = atoi(arg);
	int menu_items = 0;
	while (menu_items < SMITH_MAX_ITEMS && sdata->items[menu_items] != -1)
		++menu_items;

	// Can't 'forge 0' or 'forge -1'.  Also, can't 'forge <num>' where <num> goes off the list.
	if (choice < 1 || choice > menu_items)
		return FALSE;

	// Convert from list item to forge_item_list entry.
	choice = sdata->items[choice - 1];

	// Nullify all needed_ore entries.
	for (i = 0; i < 5; i++)
	{
		needed_ore[i] = NULL;
	}
	// Look through inventory for each needed ore.
	for (i = 0, j = 0; i < 5 && forge_item_list[choice].ore_needed[i]; i++)
	{
		for (tobj = pl->carrying; tobj; tobj = tobj->next_content)
		{
			// If we found a needed ore.
			if (forge_item_list[choice].ore_needed[i] == OBJ_VNUM(tobj))
			{
				// Stick it in the needed_ore array
				needed_ore[j++] = tobj;
				// And pull it from pl, so we don't find the same ore twice.
				obj_from_char(tobj);
				break;
			}
		}
		// If we encounter a needed ore that pl doesn't have,
		if (!tobj)
		{
			// Send a message about it,
			forge_describe(choice, pl);
			// And give back the ores we pulled.
			while (j-- > 0)
			{
				obj_to_char(needed_ore[j], pl);
			}
			return TRUE;
		}
	}

	/* Price tiers follow ore count, not this smith's menu length. */
	if (i <= 0 || i > (int)(sizeof(forge_prices) / sizeof(forge_prices[0])))
	{
		logit(LOG_DEBUG, "smith: invalid ore count %d for forge item %d.", i, choice);
		while (j-- > 0)
			obj_to_char(needed_ore[j], pl);
		return TRUE;
	}
	if (GET_COPPER(pl) + 10LL * GET_SILVER(pl) + 100LL * GET_GOLD(pl) +
		    1000LL * GET_PLATINUM(pl) <
	    forge_prices[i - 1])
	{
		forge_describe(choice, pl);
		while (j-- > 0)
			obj_to_char(needed_ore[j], pl);
		return TRUE;
	}

	// Create item 'choice' for 'pl' out of material type 'material'
	if (!(tobj = forge_create(choice, pl, needed_ore[0]->material)))
	{
		// Send an error message if we failed to create item.
		send_to_char(
			"&+YFailed to create the item.  Please tell an Immortal if you continue to have problems.\n\r",
			pl);
		// And give back the ores we pulled.
		while (j-- > 0)
		{
			obj_to_char(needed_ore[j], pl);
		}
		return TRUE;
	}

	// Like enhancement, prepare delivery before charging or consuming either input.
	if (!obj_to_char(tobj, pl))
	{
		while (j-- > 0)
			obj_to_char(needed_ore[j], pl);
		send_to_char("The forged item could not be delivered.\r\n", pl);
		return TRUE;
	}
	const int wallet_before[] = { GET_COPPER(pl), GET_SILVER(pl), GET_GOLD(pl),
				      GET_PLATINUM(pl) };
	const uint64_t wallet_revision_before = pl->only.pc->wallet_revision;
	if (SUB_MONEY(pl, forge_prices[i - 1], 0) != 0)
	{
		extract_obj(tobj, FALSE);
		while (j-- > 0)
			obj_to_char(needed_ore[j], pl);
		send_to_char("The forge payment could not be completed.\r\n", pl);
		return TRUE;
	}

	// Capture the debit, detached inputs and replacement together. Do not destroy
	// the inputs until that complete after-image has entered the writer.
	const int room = pl->in_room == NOWHERE ? NOWHERE : world[pl->in_room].number;
	const auto checkpoint =
		player_save_pipeline_request(pl, PLAYER_CHECKPOINT_COMPONENT_ALL, RENT_CRASH, room);
	if (checkpoint != player_save_pipeline_result::queued &&
	    checkpoint != player_save_pipeline_result::coalesced)
	{
		GET_COPPER(pl) = wallet_before[0];
		GET_SILVER(pl) = wallet_before[1];
		GET_GOLD(pl) = wallet_before[2];
		GET_PLATINUM(pl) = wallet_before[3];
		pl->only.pc->wallet_revision = wallet_revision_before;
		extract_obj(tobj, FALSE);
		while (j-- > 0)
			obj_to_char(needed_ore[j], pl);
		mark_player_dirty_components(GET_PID(pl), PLAYER_COMPONENT_STATUS |
								  PLAYER_COMPONENT_EQUIPMENT |
								  PLAYER_COMPONENT_INVENTORY);
		gmcp_char_vitals(pl);
		send_to_char("The forge checkpoint could not be started; nothing changed.\r\n", pl);
		return TRUE;
	}

	snprintf(buffer, sizeof buffer, "You hand $N %s.", coin_stringv(forge_prices[i - 1]));
	act(buffer, FALSE, pl, 0, ch, TO_CHAR);

	// And their ore.
	while (j-- > 0)
	{
		extract_obj(needed_ore[j], TRUE); // Ore is not an arti, but was 'in game.'
	}

	act("$n takes the pieces of ore and starts to work on them.\n"
	    "With powerful hammer strikes, the material starts to quickly take\n"
	    "shape of $p.\n"
	    "$n puts it in water which explodes in a cloud of &+Csteam&n hissing loudly.\n"
	    "'&+WThere you go!&n', $n gives you $p.",
	    FALSE, ch, tobj, pl, TO_VICT);
	act("$n takes the pieces of ore and starts to work on them.\n"
	    "With powerful hammer strikes, the material starts to quickly take\n"
	    "shape of $p.\n"
	    "$n puts it in water which explodes in a cloud of &+Csteam&n hissing loudly.\n"
	    "'&+WThere you go!&n', $n gives $N $p.",
	    FALSE, ch, tobj, pl, TO_NOTVICT);

	return TRUE;
}

void initialize_tradeskills()
{
	int i;

	initialize_mining();

	// set procs on smiths
	for (i = 0; smith_array[i].vnum; i++)
		if (!mob_index[real_mobile0(smith_array[i].vnum)].func.mob)
			mob_index[real_mobile0(smith_array[i].vnum)].func.mob = smith;
}

P_obj get_bandage(P_char ch)
{
	P_obj t_obj, next_obj;

	for (t_obj = ch->carrying; t_obj; t_obj = next_obj)
	{
		next_obj = t_obj->next_content;
		if (t_obj->type == ITEM_BANDAGE)
		{
			return t_obj;
		}
	}

	return NULL;
}

int poison_common_remove(P_char ch);

struct bandage_data
{
	int room;
	int healed;
	int maxheal;
};

// Zero, after notching, destroys the bandage: a low first roll lets the second reach zero.
static int bandage_fumble_roll(const Rolls &rolls, int rating)
{
	return rolls.number(rolls.number(0, 3), rating);
}

static int bandage_heal(int maxheal, int rating)
{
	return (maxheal / 20 + rating / 7);
}

// Zero lets a further roll neutralize the target's poison.
static int bandage_poison_roll(const Rolls &rolls)
{
	return rolls.number(0, 4);
}

static int bandage_interval()
{
	return PULSE_VIOLENCE;
}

static int bandage_duration()
{
	return 3;
}

static int bandage_lag()
{
	return 2 * PULSE_VIOLENCE;
}

std::string battlefield_aid_innate_facts(P_char /*ch*/)
{
	return "  Successful bandaging stabilizes a dying target still below positive HP\n"
	       "  to 1 hit point. Normal bandaging requirements and costs apply.\n";
}

std::string bandage_facts(P_char ch)
{
	const int rating = GET_CHAR_SKILL(ch, SKILL_BANDAGE);
	if (!rating)
		return "  You have not learned to bandage.\n";
	return fact("Healing every " + seconds(bandage_interval()),
		    std::to_string(bandage_heal(0, rating)) +
			    ", plus 1/20 of the bandage's strength") +
	       "    (up to its strength in all, and to 7/8 of the target's maximum)\n" +
	       fact("Chance each round destroys the bandage",
		    "1 in " + std::to_string(4 * (rating + 1))) +
	       fact("Chance each round cures poison",
		    one_in(bandage_poison_roll) + ", then " + chance_under(rating, 0, 100)) +
	       fact("Vitality each round",
		    show({ tradeskill_vitality_cost(lowest_rolls, rating),
			   tradeskill_vitality_cost(highest_rolls, rating) })) +
	       "    (you stop below 10)\n" + fact("Your lag", seconds(bandage_lag())) +
	       fact("Before the same target can be bandaged again",
		    game_hours(bandage_duration())) +
	       "    (unless it is dying)\n"
	       "  It takes a bandage and a target at or below 7/8 of its maximum, with nobody\n"
	       "  fighting you or it.\n";
}

void event_bandage_check(P_char ch, P_char victim, P_obj, void *data)
{
	struct bandage_data *mdata = (struct bandage_data *)data;
	char buf[MAX_STRING_LENGTH];
	int healed = 0;

	if (!ch || !victim)
		return;

	if (mdata->healed >= mdata->maxheal)
	{
		snprintf(buf, MAX_STRING_LENGTH,
			 "You can't &+Wbandage&n any more with this bandage.\n");
		send_to_char(buf, ch);
		return;
	}

	if (!ch->desc || IS_FIGHTING(ch) || (ch->in_room != mdata->room) ||
	    (GET_STAT(ch) < STAT_SLEEPING) || IS_SET(ch->specials.affected_by, AFF_HIDE) ||
	    IS_FIGHTING(victim) || (victim->in_room != mdata->room) ||
	    IS_SET(victim->specials.affected_by, AFF_HIDE) || affected_by_spell(ch, TAG_FIRING) ||
	    affected_by_spell(victim, TAG_FIRING) || IS_AFFECTED2(ch, AFF2_MEMORIZING) ||
	    IS_AFFECTED2(victim, AFF2_MEMORIZING) || IS_IMMOBILE(ch))
	{
		send_to_char("You are no longer bandaging...\n", ch);
		send_to_char("You are no longer being &+Wbandaged&n.\n", victim);
		return;
	}

	if (GET_VITALITY(ch) < 10)
	{
		send_to_char("You are too exhausted to continue.\n", ch);
		send_to_char("You are no longer being &+Wbandaged&n.\n", victim);
		return;
	}

	if (!notch_skill(ch, SKILL_BANDAGE, get_property("skill.notch.bandage", 3)) &&
	    !bandage_fumble_roll(live_rolls, (GET_CHAR_SKILL(ch, SKILL_BANDAGE))))
	{
		send_to_char("You are not focused enough, you destroy the &+Wbandage&n.\n", ch);
		send_to_char("You are no longer being &+Wbandaged&n.\n", victim);
		return;
	}

	if (ch != victim)
		act("You continue &+Wbandaging&n $N.", FALSE, ch, 0, victim, TO_CHAR);
	else
		act("You continue &+Wbandaging&n yourself.", FALSE, ch, 0, victim, TO_CHAR);

	act("$n continues to &+Wbandage&n you.", FALSE, ch, 0, victim, TO_VICT);
	act("$n continues to &+Wbandage&n $N", FALSE, ch, 0, victim, TO_NOTVICT);

	healed = bandage_heal(mdata->maxheal, GET_CHAR_SKILL(ch, SKILL_BANDAGE));
	healed = MIN(healed, mdata->maxheal - mdata->healed);
	mdata->healed = mdata->healed + healed;
	healed = vamp(victim, healed, GET_MAX_HIT(victim) * 0.875);
	if (healed > 0 && has_innate(ch, INNATE_BATTLEAID) && GET_HIT(victim) <= 0)
		GET_HIT(victim) = 1;
	update_pos(victim);

	if (IS_AFFECTED2(victim, AFF2_POISONED) && !bandage_poison_roll(live_rolls) &&
	    (number(0, 100) < GET_CHAR_SKILL(ch, SKILL_BANDAGE)))
	{
		send_to_char("&+WThe poison in your bloodstream is neutralized!\n", victim);
		poison_common_remove(victim);
	}

	if (healed == 0)
	{
		send_to_char("&+WYour bandage won't do any more good now&n.\n", ch);
		send_to_char("You are no longer being bandaged.\n", victim);
		return;
	}

	GET_VITALITY(ch) -= tradeskill_vitality_cost(live_rolls, GET_CHAR_SKILL(ch, SKILL_BANDAGE));
	add_event(event_bandage_check, bandage_interval(), ch, victim, 0, 0, mdata,
		  sizeof(struct bandage_data));
}

void do_bandage(P_char ch, char *arg, int /*cmd*/)
{
	struct affected_type af;
	struct bandage_data data;
	P_char victim = NULL;
	P_obj bandage;

	if (!SanityCheck(ch, "do_bandage"))
		return;

	if (IS_NPC(ch))
	{
		send_to_char("You're too NPC-like to try.\r\n", ch);
		return;
	}

	if (get_scheduled(ch, event_bandage_check))
	{
		send_to_char("Yes you are &+Wbandaging&n.\n", ch);
		return;
	}

	victim = ParseTarget(ch, arg);
	if (!victim)
	{
		send_to_char("Who are you trying to &+Wbandage&n?\r\n", ch);
		return;
	}

	if (affected_by_spell(victim, SKILL_BANDAGE) && GET_HIT(victim) >= 0)
	{
		send_to_char("&+WBandaging&n again wont do any good now.\r\n", ch);
		return;
	}

	if (IS_PC(ch) && GET_CHAR_SKILL(ch, SKILL_BANDAGE) == 0)
	{
		send_to_char(
			"Maybe you should leave that to someone skilled in battlefield first aid.\r\n",
			ch);
		return;
	}

	if (IS_FIGHTING(victim) || IS_FIGHTING(ch))
	{
		send_to_char("The battle in room prevents you from that.\r\n", ch);
		return;
	}

	if (NumAttackers(victim))
	{
		send_to_char("That person is still being attacked, maybe you should wait?\r\n", ch);
		return;
	}

	if (GET_HIT(victim) > GET_MAX_HIT(victim) - (GET_MAX_HIT(victim) / 8))
	{
		if (ch == victim)
			send_to_char("Try again when you are more hurt..\r\n", ch);
		else
			send_to_char("Try again when they more hurt.\r\n", ch);

		return;
	}

	bandage = get_bandage(ch);

	if (!bandage)
	{
		act("You have no &+Wbandage&n.", FALSE, ch, 0, 0, TO_CHAR);
		return;
	}

	data.maxheal = bandage->value[0];
	extract_obj(bandage, TRUE); // Not an arti, but 'in game.'

	if (ch != victim)
		act("You attempt to &+Wbandage&n $N.", FALSE, ch, 0, victim, TO_CHAR);
	else
		act("You attempt to &+Wbandage&n yourself.", FALSE, ch, 0, victim, TO_CHAR);

	act("$n attempts to &+Wbandage&n you.", FALSE, ch, 0, victim, TO_VICT);
	act("$n attempts to &+Wbandage&n $N", FALSE, ch, 0, victim, TO_NOTVICT);

	data.room = ch->in_room;
	data.healed = 0;

	add_event(event_bandage_check, bandage_interval(), ch, victim, 0, 0, &data,
		  sizeof(struct bandage_data));

	bzero(&af, sizeof(af));
	af.duration = bandage_duration();
	af.type = SKILL_BANDAGE;
	af.flags = AFFTYPE_NOSHOW | AFFTYPE_NODISPEL;
	affect_to_char(victim, &af);

	CharWait(ch, bandage_lag());
	return;
}

// Drannak Stuff
void create_recipes_file(const char *dir, char *name)
{
	char buf[256], *buff;
	char Gbuf1[MAX_STRING_LENGTH];
	FILE *f;

	strcpy(buf, name);
	buff = buf;
	for (; *buff; buff++)
		*buff = LOWER(*buff);
	snprintf(Gbuf1, MAX_STRING_LENGTH, "%s/%c/%s.crafting", dir, buf[0], buf);
	f = fopen(Gbuf1, "w");
	fclose(f);
}

void create_recipes_name(char *name)
{
	create_recipes_file("Players/Tradeskills", name);
}

int learn_recipe(P_obj obj, P_char ch, int cmd, char *arg)
{
	P_obj tobj;
	int recipenumber = obj->value[6];
	int recnum;
	bool forge = FALSE;
	bool craft = FALSE;

	// If not reciting, bad char, or char doesn't have obj.
	if (cmd != CMD_RECITE || !IS_ALIVE(ch) ||
	    !(OBJ_WORN_BY(obj, ch) || OBJ_CARRIED_BY(obj, ch)) || !arg)
	{
		return FALSE;
	}

	// Trying to recite a different object.
	if (obj != get_obj_in_list_vis(ch, skip_spaces(arg), ch->carrying) &&
	    obj != get_object_in_equip_vis(ch, arg, &recnum))
	{
		return FALSE;
	}

	if (recipenumber == 0)
	{
		send_to_char("This item is useless!\r\n", ch);
		return TRUE;
	}

	tobj = read_object(recipenumber, VIRTUAL);
	if (tobj == NULL)
	{
		send_to_char(
			"This recipe is damaged: its target item no longer exists. Please report it to an Immortal.\r\n",
			ch);
		logit(LOG_DEBUG, "learn_recipe: %s used a recipe with missing target vnum %d.",
		      GET_NAME(ch), recipenumber);
		return TRUE;
	}
	if (!crafting_recipe_target_is_available(tobj))
	{
		if (IS_OBJ_STAT2(tobj, ITEM2_QUESTITEM))
			send_to_char(
				"This recipe describes a quest item and cannot be learned for player crafting.\r\n",
				ch);
		else
			send_to_char(
				"This recipe cannot be learned because no player can make it under the current crafting configuration.\r\n",
				ch);
		logit(LOG_DEBUG, "learn_recipe: %s used an uncraftable recipe target %d.",
		      GET_NAME(ch), recipenumber);
		extract_obj(tobj);
		return TRUE;
	}

	if (IS_SET(tobj->wear_flags, ITEM_WEAR_HEAD) || IS_SET(tobj->wear_flags, ITEM_WEAR_BODY) ||
	    IS_SET(tobj->wear_flags, ITEM_WEAR_ARMS) || IS_SET(tobj->wear_flags, ITEM_WEAR_FEET) ||
	    IS_SET(tobj->wear_flags, ITEM_WEAR_SHIELD) || IS_SET(tobj->wear_flags, ITEM_WIELD) ||
	    IS_SET(tobj->wear_flags, ITEM_WEAR_LEGS) || IS_SET(tobj->wear_flags, ITEM_WEAR_HANDS))
	{
		forge = TRUE;
	}
	if (IS_SET(tobj->wear_flags, ITEM_WEAR_ABOUT) ||
	    IS_SET(tobj->wear_flags, ITEM_WEAR_WAIST) ||
	    IS_SET(tobj->wear_flags, ITEM_WEAR_EARRING) ||
	    IS_SET(tobj->wear_flags, ITEM_WEAR_NECK) || IS_SET(tobj->wear_flags, ITEM_WEAR_WRIST) ||
	    IS_SET(tobj->wear_flags, ITEM_WEAR_FINGER) ||
	    IS_SET(tobj->wear_flags, ITEM_WEAR_EYES) ||
	    IS_SET(tobj->wear_flags, ITEM_WEAR_QUIVER) ||
	    IS_SET(tobj->wear_flags, ITEM_WEAR_TAIL) || IS_SET(tobj->wear_flags, ITEM_WEAR_NOSE) ||
	    IS_SET(tobj->wear_flags, ITEM_WEAR_HORN) || IS_SET(tobj->wear_flags, ITEM_WEAR_FACE))
	{
		craft = TRUE;
	}

	if (forge)
	{
		if (GET_CHAR_SKILL(ch, SKILL_FORGE) < 1)
		{
			forge = FALSE;
			if (craft)
			{
				if (GET_CHAR_SKILL(ch, SKILL_CRAFT) < 1)
				{
					send_to_char(
						"This recipe can only be used by someone with the &+rCraft&n or &+LForge&n skill.\r\n",
						ch);
					return TRUE;
				}
			}
			else
			{
				send_to_char(
					"This recipe can only be used by someone with the &+LForge&n skill.\r\n",
					ch);
				return TRUE;
			}
		}
	}
	else if (craft)
	{
		if (GET_CHAR_SKILL(ch, SKILL_CRAFT) < 1)
		{
			send_to_char(
				"This recipe can only be used by someone with the &+rCraft&n skill.\r\n",
				ch);
			return TRUE;
		}
	}

	// check if player already knows this recipe
	if (sql_has_player_recipe(GET_PID(ch), recipenumber))
	{
		send_to_char("You already know how to create that item!&n\r\n", ch);
		extract_obj(tobj);
		return TRUE;
	}

	// add recipe to database
	if (!sql_add_player_recipe(GET_PID(ch), recipenumber))
	{
		send_to_char("Your recipe could not be recorded. Please try again later.\r\n", ch);
		logit(LOG_DEBUG, "learn_recipe: failed to save recipe %d for %s", recipenumber,
		      GET_NAME(ch));
		extract_obj(tobj);
		return TRUE;
	}
	act("$n opens their &+Ltome &+yof &+Ycraf&+ytsman&+Lship&n and begins scribing the &+yrecipe&n...\n"
	    "As they finish the last entry of the &+yrecipe&n, a &+Mbri&+mgh&+Wt &nflash of &+Clight&n appears,\n"
	    "quickly consuming $p, which vanishes from sight.\r\n",
	    FALSE, ch, obj, 0, TO_ROOM);
	act("You open your &+Ltome &+yof &+Ycraf&+ytsman&+Lship&n and begin scribing the recipe...\n"
	    "As you finish the last entry of the &+yrecipe&n, a &+Mbri&+mgh&+Wt &nflash of &+Clight&n appears,\n"
	    "quickly consuming $p, which vanishes from sight.\r\n",
	    FALSE, ch, obj, 0, TO_CHAR);

	extract_obj(obj, TRUE); // Not an arti, but 'in game.'

	if (forge)
	{
		notch_skill(ch, SKILL_FORGE, 1);
	}
	else if (craft)
	{
		notch_skill(ch, SKILL_CRAFT, 1);
	}
	else
	{
		// This should never happen.
		debug("learn_recipe: %s learned %s (%d) without craft or forge!?", J_NAME(ch),
		      tobj->short_description, recipenumber);
		logit(LOG_DEBUG, "learn_recipe: %s learned %s (%d) without craft or forge!?",
		      J_NAME(ch), tobj->short_description, recipenumber);
	}
	extract_obj(tobj);
	return TRUE;
}

/* This function handles buying epic items and attaches to
 *   the mob (shopkeeper) in specs_assign.c.
 * Recommended change: Variables for item vnum and epics needed
 *   and then just set them in the CMD_BUY case.  At the end,
 *   if( pl->..epics < epics needed ) {fail message and return}
 *   load item via var, message char "You bought $p", subtract epics,
 *   send item to char, and save char.
 */
#define COST_EPIC_MUSHROOM 225
#define COST_EPIC_FIX_SCROLL 105
#define COST_EPIC_FAERIE_BAG 100
#define COST_EPIC_BATTLEROBE 7500
#define COST_EPIC_TOCORPSE_POTION 500
#define COST_EPIC_LANTAN_TOOLS 500
#define COST_EPIC_FOREST_EYES 4500
#define COST_EPIC_BOTTLE_EPICS 100

int epic_store(P_char /*ch*/, P_char pl, int cmd, char *arg)
{
	char buffer[MAX_STRING_LENGTH];

	if (cmd == CMD_LIST)
	{
		if (!arg || !*arg)
		{
			// list called with no arguments
			snprintf(
				buffer, MAX_STRING_LENGTH,
				"&+WKannard&+L slowly lifts his hood and smiles.'\n"
				"&+WKannard&+L &+wsays 'Welcome adventurer. I offer exotic items from the far reaches beyond our own realm in exchange for &+cepic points&n.'\n"
				"&+WKannard&+L &+wsays 'Please &+Yrefer to my &-L&+ysign&n&-l for an explanation of each of these items and their affects.'\n"
				"&+y=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n"
				"&+y|		&+cItem Name					           Epic Cost            &+y|\n"
				"&+y|&+W 1) &+ga M&+Ga&+Wg&+Gi&+gc&+Ga&+Wl &+GGreen &+gMu&+Gshro&+gom from the &+GSylvan &+yWoods&n&+C%30d&n		&+y|\n"
				"&+y|&+W 2) &+ya tightly wrapped vellum scroll named '&+LFix&+y'&n   &+C%30d&n		&+y|\n"
				"&+y|&+W 3) &+Wa &+mm&+My&+Ys&+Bt&+Gc&+Ra&+Gl &+MFaerie &+Wbag of &+Lstolen loot&n           &+C%30d&n               &+y|\n"
				"&+y|&+W 4) &+Ya r&+ro&+Yb&+re &+Yof a &+mN&+We&+Mt&+Wh&+me&+Wr&+Mi&+Wl &+rBa&+Ytt&+rle&+Y M&+rag&+Ye&n              &+C%30d&n               &+y|\n"
				"&+y|&+W 5) &+La &+Gbottle &+Lof &+GT&+go&+GR&+gM&+Ge&+gN&+GT&+ge&+GD &+gS&+Goul&+gs     &n              &+C%30d&n               &+y|\n"
				"&+y|&+W 6) &+ca &+Cbr&+Will&+Bia&+Wnt &+cset of &+rLantan &+CScientific&+L Tools&n    &n&+C%30d&n               &+y|\n"
				"&+y|&+W 7) &+Lthe &+ge&+Gy&+ge&+Gs &+Lof the &+gHi&+Ggh For&+gest&n     &n              &+C%30d&n&+y               |\n"
				"&+y|&+W 8) &+Ca &+Wbottle &+Cof &+GPa&+gs&+Lt Exp&+gerien&+Gces&n     &n             &+C%30d&n&+y               |\n"
				"&+y|&+R Notice: You can not buy multiple items at once here!                                          &+y|&n\n"
				"&+y=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=\n"
				"\n",
				COST_EPIC_MUSHROOM, COST_EPIC_FIX_SCROLL, COST_EPIC_FAERIE_BAG,
				COST_EPIC_BATTLEROBE, COST_EPIC_TOCORPSE_POTION,
				COST_EPIC_LANTAN_TOOLS, COST_EPIC_FOREST_EYES,
				COST_EPIC_BOTTLE_EPICS);

			send_to_char(buffer, pl);
			return TRUE;
		}
	}
	else if (cmd == CMD_BUY)
	{
		// Prevent NPCs/pets from using the epic store
		if (IS_NPC(pl))
		{
			snprintf(
				buffer, MAX_STRING_LENGTH,
				"&+WKannard&+L &+wshouts 'Hey everyone! %s just tried to make their pet buy epic items! How embarrassing!'&n\n",
				GET_MASTER(pl) ? GET_NAME(GET_MASTER(pl)) : "Someone");
			send_to_all(buffer);
			return TRUE;
		}

		if (!arg || !*arg)
		{
			snprintf(buffer, MAX_STRING_LENGTH,
				 "&+WKannard&+L &+wsays 'What item would you like to buy?'\n");
			send_to_char(buffer, pl);
			return TRUE;
		}
		// 1 - lvl mushroom
		else if (strstr(arg, "1"))
		{
			// Check for level requirement.
			if (GET_LEVEL(pl) < 51)
			{
				send_to_char(
					"&+WKannard&+L &+wsays '&nI'm sorry, but you do not seem to have enough &+Wexperience&n to buy that item.\r\n&n",
					pl);
				return TRUE;
			}
			// Check for the epics required to purchase mushroom..
			if (pl->only.pc->epics < COST_EPIC_MUSHROOM)
			{
				send_to_char(
					"&+WKannard&+L &+wsays '&nI'm sorry, but you do not seem to have the &+Wepics&n available for that item.\r\n&n",
					pl);
				return TRUE;
			}
			submit_epic_store_purchase(pl, VOBJ_EPIC_MUSHROOM, COST_EPIC_MUSHROOM);
			return TRUE;
		}
		// 2 - fix scroll
		else if (strstr(arg, "2"))
		{
			// Check for the epics required for scroll..
			if (pl->only.pc->epics < COST_EPIC_FIX_SCROLL)
			{
				send_to_char(
					"&+WKannard&+L &+wsays '&nI'm sorry, but you do not seem to have the &+Wepics&n available for that item.\r\n&n",
					pl);
				return TRUE;
			}
			submit_epic_store_purchase(pl, VOBJ_EPIC_FIX_SCROLL, COST_EPIC_FIX_SCROLL);
			return TRUE;
		}
		// 3 - faerie bag
		else if (strstr(arg, "3"))
		{
			// Check for the epics required for bag..
			if (pl->only.pc->epics < COST_EPIC_FAERIE_BAG)
			{
				send_to_char(
					"&+WKannard&+L &+wsays '&nI'm sorry, but you do not seem to have the &+Wepics&n available for that item.\r\n&n",
					pl);
				return TRUE;
			}
			submit_epic_store_purchase(pl, VOBJ_EPIC_FAERIE_BAG, COST_EPIC_FAERIE_BAG);
			return TRUE;
		}
		// 4 - netheril robe
		else if (strstr(arg, "4"))
		{
			// Check for the epics required for robe..
			if (pl->only.pc->epics < COST_EPIC_BATTLEROBE)
			{
				send_to_char(
					"&+WKannard&+L &+wsays '&nI'm sorry, but you do not seem to have the &+Wepics&n available for that item.\r\n&n",
					pl);
				return TRUE;
			}
			submit_epic_store_purchase(pl, VOBJ_EPIC_BATTLEROBE, COST_EPIC_BATTLEROBE);
			return TRUE;
		}
		// 5 - corpse portal potion
		else if (strstr(arg, "5"))
		{
			// Check for the epics required for potion..
			if (pl->only.pc->epics < COST_EPIC_TOCORPSE_POTION)
			{
				send_to_char(
					"&+WKannard&+L &+wsays '&nI'm sorry, but you do not seem to have the &+Wepics&n available for that item.\r\n&n",
					pl);
				return TRUE;
			}
			submit_epic_store_purchase(pl, VOBJ_EPIC_TOCORPSE_POTION,
						   COST_EPIC_TOCORPSE_POTION);
			return TRUE;
		}
		// 6 - lantan tools
		else if (strstr(arg, "6"))
		{
			// Check for the epics required for lantans..
			if (pl->only.pc->epics < COST_EPIC_LANTAN_TOOLS)
			{
				send_to_char(
					"&+WKannard&+L &+wsays '&nI'm sorry, but you do not seem to have the &+Wepics&n available for that item.\r\n&n",
					pl);
				return TRUE;
			}
			submit_epic_store_purchase(pl, VOBJ_EPIC_LANTAN_TOOLS,
						   COST_EPIC_LANTAN_TOOLS);
			return TRUE;
		}
		// 7 - forest sight
		else if (strstr(arg, "7"))
		{
			// Check for the epics required for forest goggles..
			if (pl->only.pc->epics < COST_EPIC_FOREST_EYES)
			{
				send_to_char(
					"&+WKannard&+L &+wsays '&nI'm sorry, but you do not seem to have the &+Wepics&n available for that item.\r\n&n",
					pl);
				return TRUE;
			}
			submit_epic_store_purchase(pl, VOBJ_EPIC_FOREST_EYES, COST_EPIC_FOREST_EYES,
						   true);
			return TRUE;
		}
		else if (strstr(arg, "8"))
		{
			// Check for the epics required for forest goggles..
			if (pl->only.pc->epics < COST_EPIC_BOTTLE_EPICS)
			{
				send_to_char(
					"&+WKannard&+L &+wsays '&nI'm sorry, but you do not seem to have the &+Wepics&n available for that item.\r\n&n",
					pl);
				return TRUE;
			}
			submit_epic_store_purchase(pl, VOBJ_EPIC_BOTTLE_EPICS,
						   COST_EPIC_BOTTLE_EPICS);
			return TRUE;
		}
	}
	return FALSE;
}

int learn_tradeskill(P_char ch, P_char pl, int cmd, char *arg)
{
	char buffer[MAX_STRING_LENGTH];

	if (cmd == CMD_PRACTICE)
	{
		if (!arg || !*arg)
		{
			// practice called with no arguments
			snprintf(
				buffer, MAX_STRING_LENGTH,
				"'Greetings Adventurer!'\n"
				"'The choice of a &+Wtradeskill&n is an important one, as only &+Yone&n can be made.'\n"
				"'Of the abilities which I can train you are &+Lm&+wi&+Wn&+wi&+Lng&n, &+Lforging&n, or &+rcrafting&n.'\n"
				"'&+LM&+wi&+Wn&+wi&+Lng&n&n will allow you to gather raw &+mvaluable&n &+Lore&n from &+ymines&n scattered throughout the realm.'\n"
				"'&+LForging&n allows one to create amazing &+Larmor&n and &+Wweapons&n from &+yrecipes&n found through the &+ysalvage&n skill.'\n"
				"'&+rCrafting&n is the meticulous skill allowing one to craft &+Mjewelry&n, &+maccessories&n, and &+ccloak&n items from &+ysalvaged&n recipes.'\n"
				"'Please think long and hard about your decision, and then &+RPractice &neither &+Lforge&n, &+ymine&n, or &+Rcraft&n.\n"
				"'\n"
				"'If you are unhappy with your current &+ytradeskill&n, you can &+Rpractice reset&n and I will unlearn any &+ytradeskill&n you'\n"
				"'might know for the low price of &+c200 &+Cepic points&n. &+rBEWARE&n: this will wipe any learned &+Yrecipes&n!\n");
			send_to_char(buffer, pl);

			if (GET_CHAR_SKILL(pl, SKILL_FORGE) >= 1 ||
			    GET_CHAR_SKILL(pl, SKILL_MINE) >= 1 ||
			    GET_CHAR_SKILL(pl, SKILL_CRAFT) >= 1)
			{
				send_to_char(
					"\n"
					"'Unfortunately, I cannot teach you anything more, as you have already learned a tradeskill!'\n",
					pl);
				return TRUE;
			}

			return TRUE;
		}
		// Drannak - ability to reset their tradeskill 3/22/13
		else if (strstr(arg, "reset"))
		{
			// reset called

			// check for 200 epics required to reset
			int availepics = pl->only.pc->epics;
			if (availepics < 200)
			{
				if (pl->in_room == real_room(133071))
					send_to_char(
						"&nJodnan says '&+GI'm sorry, but you do not seem to have the &+Wepics&+G available for me to reset your &+gtradeskill&+G.\r\n&n",
						pl);
				else
					send_to_char(
						"&nGixnif says '&+GI'm sorry, but you do not seem to have the &+Wepics&+G available for me to reset your &+gtradeskill&+G.\r\n&n",
						pl);
				return TRUE;
			}
			if (!epic_transaction_submit(pl, -200, epic_reason_type::tradeskill_reset,
						     0, EPIC_COMMAND_REQUIRE_FUNDS,
						     critical_source_site::command,
						     critical_deadline_class::interactive,
						     tradeskill_reset_committed, nullptr, 0))
				send_to_char(
					"The epic transaction service is busy. Please try again.\n",
					pl);

			return TRUE;
		}

		else if (strstr(arg, "forge"))
		{
			// called with skill name
			if (GET_CHAR_SKILL(pl, SKILL_FORGE) >= 1 ||
			    GET_CHAR_SKILL(pl, SKILL_MINE) >= 1 ||
			    GET_CHAR_SKILL(pl, SKILL_CRAFT) >= 1)
			{
				send_to_char(
					"Unfortunately, I cannot teach you anything more, as you have already learned a tradeskill!\n",
					pl);
				return TRUE;
			}
			snprintf(
				buffer, MAX_STRING_LENGTH,
				"Your teacher takes you aside and teaches you the finer points of &+W%s&n.\n"
				"&+cYou feel your skill in %s improving.&n\n",
				skills[SKILL_FORGE].name, skills[SKILL_FORGE].name);
			act(buffer, FALSE, ch, 0, pl, TO_VICT);
			pl->only.pc->skills[SKILL_FORGE].learned = 10;
			pl->only.pc->skills[SKILL_FORGE].taught = 100;
			pl->only.pc->skills[SKILL_FORGE].learned = 10;
			// MIN(100, pl->only.pc->skills[SKILL_FORGE].learned + 10);
			if (!do_save_silent(pl, 1))
				logit(LOG_WIZ, "Failed to save %s after tradeskill change.",
				      GET_NAME(pl)); // tradeskills require a save.
			CharWait(pl, PULSE_VIOLENCE);
			return TRUE;
		}
		else if (strstr(arg, skills[SKILL_MINE].name))
		{
			// called with skill name
			if (GET_CHAR_SKILL(pl, SKILL_FORGE) >= 1 ||
			    GET_CHAR_SKILL(pl, SKILL_MINE) >= 1 ||
			    GET_CHAR_SKILL(pl, SKILL_CRAFT) >= 1)
			{
				send_to_char(
					"Unfortunately, I cannot teach you anything more, you have already learned a tradeskill!\n",
					pl);
				return TRUE;
			}
			snprintf(
				buffer, MAX_STRING_LENGTH,
				"Your teacher takes you aside and teaches you the finer points of &+W%s&n.\n"
				"&+cYou feel your skill in %s improving.&n\n",
				skills[SKILL_MINE].name, skills[SKILL_MINE].name);
			act(buffer, FALSE, ch, 0, pl, TO_VICT);
			pl->only.pc->skills[SKILL_MINE].taught = 100;
			pl->only.pc->skills[SKILL_MINE].learned = 10;
			// MIN(100, pl->only.pc->skills[SKILL_MINE].learned + 10);
			if (!do_save_silent(pl, 1))
				logit(LOG_WIZ, "Failed to save %s after tradeskill change.",
				      GET_NAME(pl)); // tradeskills require a save.
			CharWait(pl, PULSE_VIOLENCE);
			return TRUE;
		}
		else if (strstr(arg, skills[SKILL_CRAFT].name))
		{
			// called with skill name
			if (GET_CHAR_SKILL(pl, SKILL_FORGE) >= 1 ||
			    GET_CHAR_SKILL(pl, SKILL_MINE) >= 1 ||
			    GET_CHAR_SKILL(pl, SKILL_CRAFT) >= 1)
			{
				send_to_char(
					"Unfortunately, I cannot teach you anything more, you have already learned a tradeskill!\n",
					pl);
				return TRUE;
			}
			snprintf(
				buffer, MAX_STRING_LENGTH,
				"Your teacher takes you aside and teaches you the finer points of &+W%s&n.\n"
				"&+cYou feel your skill in %s improving.&n\n",
				skills[SKILL_CRAFT].name, skills[SKILL_CRAFT].name);
			act(buffer, FALSE, ch, 0, pl, TO_VICT);
			pl->only.pc->skills[SKILL_CRAFT].taught = 100;
			pl->only.pc->skills[SKILL_CRAFT].learned = 10;
			// MIN(100, pl->only.pc->skills[SKILL_CRAFT].learned + 10);
			if (!do_save_silent(pl, 1))
				logit(LOG_WIZ, "Failed to save %s after tradeskill change.",
				      GET_NAME(pl)); // tradeskills require a save.
			CharWait(pl, PULSE_VIOLENCE);
			return TRUE;
		}
	}
	return FALSE;
}

void do_salvation(P_char ch, char * /*arg*/, int /*cmd*/)
{
	struct affected_type af;
	if (!affected_by_spell(ch, ACH_MAYIHEALSYOU) && !IS_TRUSTED(ch))
	{
		send_to_char("&+CYou have not earned the right to use this skill.&n\r\n", ch);
		return;
	}

	if (affected_by_spell(ch, TAG_SALVATION))
	{
		send_to_char("You must rest before invoking this spell again.\r\n", ch);
		return;
	}

	if (!ch)
		return;
	memset(&af, 0, sizeof(struct affected_type));
	af.type = TAG_SALVATION;
	af.modifier = 0;
	af.duration = 24;
	af.location = 0;
	af.flags = AFFTYPE_NODISPEL;
	affect_to_char(ch, &af);
	act("&+YYou raise your eyes &+Cskyward&+Y in a plea for assistance...\n"
	    "&+Y..after a brief moment, your body &+Ctingles&+Y with warmth, and you feel &+Crenewed&+Y.",
	    FALSE, ch, 0, ch, TO_CHAR);
	act("&+Y$n raises their eyes &+Cskyward&+Y in a plea for assistance...\n"
	    "&+Y..after a brief moment, $n's body &+Ctingles&+Y with warmth, and they feel &+Crenewed&+Y.",
	    FALSE, ch, 0, 0, TO_ROOM);
	vamp(ch, number(100, 200), GET_MAX_HIT(ch));
}

// Returns the lowest material vnum (lowest quality) for material with the same type as obj->material.
// I.e. for a material type FEATHER -> returns 400000 (vnum for a small feather).
//   Material range for FEATHER is 400000 (lowest quality) - 400004 (highest quality).
int material_start_vnum(int objmat)
{
	int matstart;

	switch (objmat)
	{
	case MAT_NONSUBSTANTIAL:
		matstart = 400205;
		break;
	case MAT_FLESH:
		matstart = 400005;
		break;
	case MAT_CLOTH:
		matstart = 400015;
		break;
	case MAT_BARK:
		matstart = 400035;
		break;
	case MAT_SOFTWOOD:
		matstart = 400040;
		break;
	case MAT_HARDWOOD:
		matstart = 400050;
		break;
		/*
			    case MAT_SILICON:
			      matstart = 67283;
			      break;
			*/
	case MAT_CRYSTAL:
		matstart = 400090;
		break;
		/*
			    case MAT_CERAMIC:
			      matstart = 67283;
			      break;
			*/
	case MAT_BONE:
		matstart = 400065;
		break;
	case MAT_STONE:
		matstart = 400095;
		break;
	case MAT_HIDE:
		matstart = 400030;
		break;
	case MAT_LEATHER:
		matstart = 400045;
		break;
	case MAT_CURED_LEATHER:
		matstart = 400060;
		break;
	case MAT_IRON:
		matstart = 400110;
		break;
	case MAT_STEEL:
		matstart = 400120;
		break;
	case MAT_BRASS:
		matstart = 400125;
		break;
	case MAT_MITHRIL:
		matstart = 400185;
		break;
	case MAT_ADAMANTIUM:
		matstart = 400195;
		break;
	case MAT_BRONZE:
		matstart = 400130;
		break;
	case MAT_COPPER:
		matstart = 400135;
		break;
	case MAT_SILVER:
		matstart = 400140;
		break;
	case MAT_ELECTRUM:
		matstart = 400145;
		break;
	case MAT_GOLD:
		matstart = 400150;
		break;
	case MAT_PLATINUM:
		matstart = 400180;
		break;
	case MAT_GEM:
		matstart = 400155;
		break;
	case MAT_DIAMOND:
		matstart = 400190;
		break;
		/*
			    case MAT_LEAVES:
			      matstart = 67283;
			      break;
			*/
	case MAT_RUBY:
		matstart = 400165;
		break;
	case MAT_EMERALD:
		matstart = 400160;
		break;
	case MAT_SAPPHIRE:
		matstart = 400170;
		break;
	case MAT_IVORY:
		matstart = 400070;
		break;
	case MAT_DRAGONSCALE:
		matstart = 400200;
		break;
	case MAT_OBSIDIAN:
		matstart = 400175;
		break;
	case MAT_GRANITE:
		matstart = 400100;
		break;
	case MAT_MARBLE:
		matstart = 400105;
		break;
		/*
			    case MAT_LIMESTONE:
			      matstart = 67283;
			      break;
			*/
	case MAT_BAMBOO:
		matstart = 400055;
		break;
	case MAT_REEDS:
		matstart = 400010;
		break;
	case MAT_HEMP:
		matstart = 400020;
		break;
	case MAT_GLASSTEEL:
		matstart = 400115;
		break;
	case MAT_CHITINOUS:
		matstart = 400080;
		break;
	case MAT_REPTILESCALE:
		matstart = 400085;
		break;
	case MAT_RUBBER:
		matstart = 400025;
		break;
	case MAT_FEATHER:
		matstart = 400000;
		break;
	case MAT_PEARL:
		matstart = 400075;
		break;
	default:
		matstart = 400205;
		break;
	}
	return matstart;
}

int get_matstart(P_obj obj)
{
	return obj ? material_start_vnum(obj->material) : 0;
}

void do_refine(P_char ch, char *arg, int /*cmd*/)
{
	P_obj obj;
	P_obj t_obj, nextobj;
	int i = 0, o = 0, vnum;
	int orechance = 0;
	bool plat = FALSE;
	char gbuf1[MAX_STRING_LENGTH], gbuf3[MAX_STRING_LENGTH];

	argument_interpreter(arg, gbuf1, gbuf3);

	// If first argument.
	if (*gbuf1)
	{
		obj = get_obj_in_list(gbuf1, ch->carrying);
		if (!obj)
		{
			send_to_char(
				"&nYou must have the item you wish to &+yre&+Yfi&+yne &nin your inventory.&n\r\n",
				ch);
			return;
		}

		vnum = OBJ_VNUM(obj);
		// Must be salvaged material, and cannot be the highest salvage type.
		if ((vnum > 400208) || (vnum < 400000))
		{
			send_to_char("That item is not a &+ysalvaged&n item!\r\n", ch);
			return;
		}
		if (vnum == (get_matstart(obj) + 4))
		{
			send_to_char("That &+bmaterial&n is already of the &+Bhighest&n quality.\n",
				     ch);
			return;
		}
	}
	else
	{
		send_to_char(
			"What &+ysalvaged &+Ymaterial &nwould you like to &+yre&+Yfi&+yne?\r\n",
			ch);
		return;
	}

	// Check for other materials of same quality/type
	for (t_obj = ch->carrying; t_obj; t_obj = t_obj->next_content)
	{
		if (OBJ_VNUM(t_obj) == vnum)
		{
			i++;
		}
		if ((OBJ_VNUM(t_obj) > 193) && (OBJ_VNUM(t_obj) < 234))
		{
			o++;
		}
	}
	if (i < 2)
	{
		send_to_char(
			"You need at least &+Y2 &nof the &+ymaterials&n in your inventory in order to &+yre&+Yfi&+yne&n it.\r\n",
			ch);
		return;
	}
	// If no ore, check for 50 plat..
	if (o != 1)
	{
		if (SUB_MONEY(ch, 50000, 0) != 0)
		{
			send_to_char(
				"You must have &+Wexactly &+Rone&n &+Lm&+yi&+Ln&+ye&+Ld ore &nin your inventory or 50 &+Wplatinum&n in order to &+yre&+Yfi&+yne&n it.\r\n",
				ch);
			return;
		}
		else
		{
			plat = TRUE;
		}
	}

	i = 2;
	for (t_obj = ch->carrying; t_obj; t_obj = nextobj)
	{
		nextobj = t_obj->next_content;
		int t_vnum = OBJ_VNUM(t_obj);

		if ((t_vnum == vnum) && i > 0)
		{
			obj_from_char(t_obj);
			extract_obj(t_obj, TRUE); // Not an arti, but 'in game.'
			send_to_char(
				"You take the item and gently pour the melted ore over the item...\n",
				ch);
			i--;
		}
		// Paying in platinum uses no ore.
		else if (!plat && o && (t_vnum > 193) && (t_vnum < 234))
		{
			o--;
			orechance = (t_vnum - 194);
			obj_from_char(t_obj);
			extract_obj(t_obj, TRUE); // Not an arti, but 'in game.'
		}
	}

	int success = 61;
	// Increase by ore type or 10 pts for using platinum.
	success += plat ? 10 : orechance;
	if (success < number(1, 100))
	{
		// The material was extracted above; load a temp copy for messages.
		obj = read_object(vnum, VIRTUAL);
		if (plat)
		{
			act("&+W$n &+Ltakes their &+Wcoins&+L and begins to &+rh&+Rea&+Yt &+Lit in the &+yforge&+L.\r\n"
			    "&+W$n &+Lgently removes the &+rm&+Ro&+Ylt&+Re&+rn &+ymetal &+Land starts to spread it about their $ps&+L, which &-L&+Rshatters&n &+Lfrom the intense &+rheat&+L!&N",
			    TRUE, ch, obj, 0, TO_ROOM);
			act("&+LYou &+Ltake your &+Wcoins&+L and &+rh&+Rea&+Yt &+Lit in the &+yforge&+L.\r\n"
			    "&+LYou &+Lgently remove the &+rm&+Ro&+Ylt&+Re&+rn &+ymetal &+Land start to spread it about your $ps&+L, which &-L&+Rshatters&n &+Lfrom the intense &+rheat&+L!&N",
			    FALSE, ch, obj, 0, TO_CHAR);
		}
		else
		{
			act("&+W$n &+Ltakes their &+yore&+L and begins to &+rh&+Rea&+Yt &+Lit in the &+yforge&+L.\r\n"
			    "&+W$n &+Lgently removes the &+rm&+Ro&+Ylt&+Re&+rn &+yore &+Land starts to spread it about their $ps&+L, which &-L&+Rshatters&n &+Lfrom the intense &+rheat&+L!&N",
			    TRUE, ch, obj, 0, TO_ROOM);
			act("&+LYou &+Ltake your &+yore&+L and &+rh&+Rea&+Yt &+Lit in the &+yforge&+L.\r\n"
			    "&+LYou &+Lgently remove the &+rm&+Ro&+Ylt&+Re&+rn &+yore &+Land start to spread it about your $ps&+L, which &-L&+Rshatters&n &+Lfrom the intense &+rheat&+L!&N",
			    FALSE, ch, obj, 0, TO_CHAR);
		}
		extract_obj(obj);
		return;
	}

	// Success!
	// Give them the new material.
	obj = read_object(vnum + 1, VIRTUAL);
	if (!grant_tradeskill_item(ch, obj))
		return;
	// Load a temp copy of the old material for messages.
	obj = read_object(vnum, VIRTUAL);
	act("&+W$n &+Ltakes their &+yore&+L and begins to &+rh&+Rea&+Yt &+Lit in the &+yforge&+L.\r\n"
	    "&+W$n &+Lgently removes the &+rm&+Ro&+Ylt&+Re&+rn &+yore &+Land starts to spread it about their $ps&+L, which &+ycrack &+Land &+yreform&+L under the intense &+rheat&+L.&N",
	    TRUE, ch, obj, 0, TO_ROOM);
	act("&+LYou &+Ltake your &+yore&+L and &+rh&+Rea&+Yt &+Lit in the &+yforge&+L.\r\n"
	    "&+LYou &+Lgently remove the &+rm&+Ro&+Ylt&+Re&+rn &+yore &+Land start to spread it about your $ps&+L, which &+ycrack &+Land &+yreform&+L under the intense &+rheat&+L.&N",
	    FALSE, ch, obj, 0, TO_CHAR);
	// Then remove it from game.
	extract_obj(obj);
}

void do_dice(P_char ch, char *arg, int /*cmd*/)
{
	char first_arg[MAX_INPUT_LENGTH], second_arg[MAX_INPUT_LENGTH], gbuf[MAX_STRING_LENGTH];
	int numdice, dice;

	arg = one_argument(arg, first_arg);

	if (is_number(first_arg))
	{
		numdice = atoi(first_arg);
		if (numdice > 5)
		{
			send_to_char("Sorry, dice rolls are limited to 5 at a time.\r\n", ch);
			return;
		}

		arg = one_argument(arg, second_arg);
		if (!*second_arg)
		{
			send_to_char("How many sides should the dice have?\r\n", ch);
			return;
		}
		if (!is_number(second_arg))
		{
			send_to_char("That is not a valid number.\r\n", ch);
			return;
		}
		dice = atoi(second_arg);
		if (dice > 100)
		{
			send_to_char("Dice can only have a maximum of &+W100&n sides.", ch);
			return;
		}

		int result;
		int i = 0;
		while (i < numdice)
		{
			result = number(1, dice);
			i++;
			snprintf(
				gbuf, MAX_STRING_LENGTH,
				"&+yResult for &+W%s's&+y roll &+L#&+W%d&+y of a &+r%d&+y sided die: &+W%d&+y.",
				GET_NAME(ch), i, dice, result);
			act(gbuf, FALSE, ch, 0, 0, TO_CHAR);
			act(gbuf, FALSE, ch, 0, 0, TO_ROOM);

			// send_to_char(gbuf, ch);
		}
		return;
	}
	send_to_char("Roll some dice! Syntax: dice <number> <sides>\r\n", ch);
}

int assoc_founder(P_char mob, P_char pl, int cmd, char *arg)
{
	char buffer[MAX_STRING_LENGTH], buffer2[MAX_STRING_LENGTH], guild_name[MAX_INPUT_LENGTH];

	if (cmd == CMD_LIST)
	{
		if (!arg || !*arg)
		{
			snprintf(buffer2, MAX_STRING_LENGTH, "%s", PERS(mob, pl, FALSE));
			checked_snprintf(
				buffer, MAX_STRING_LENGTH,
				"%s&+L looks you over briefly and then chuckles.'\n"
				"%s &+wsays 'Welcome adventurer.  If it is a guild ye are wishing to found, then ye have come to the right place&n.'\n"
				"%s &+wsays 'Ye will find the command to create a guild listed here, as well as the cost.'\n"
				"&+y=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=+\n"
				"&+y|&+WFounding a guild will cost &+R%s &+Wplatinum coins.                                       &+y|\n"
				"&+y|&+WTo found the guild, type the following command and have the coins on your character:      &+y|\n"
				"&+y|&+Wbuy '<name of guild>'                                                                     &+y|\n"
				"&+y|                                                                                             &+y|\n"
				"&+y|&+Wexample: buy '&&+Lthe &&+MNetheril &&+mMages&&n'                                          &+y|\n"
				"&+y|&+WThis will create a guild named: '&+Lthe &+MNetheril &+mMages&n'                           &+y|\n"
				"&+y|&nSee help &+cansi &nand help &+ctestcolor&n for help in creatnig your guild colors.         &+y|\n"
				"&+y|&+WBe warned! Once you create the guild, there is no way to rename it, for now.              &+y|\n"
				"&+y=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=+\n"
				"&+RNO racist, hate speech, or curse words will be tolerated in guild names. Violations will be met with a ban.\n"
				"\n",
				buffer2, buffer2, buffer2, comma_string(GUILD_COST / 1000));
			send_to_char(buffer, pl);
			return TRUE;
		} // endifnoarg
	} // endiflist

	if (cmd == CMD_BUY)
	{
		if (GET_ASSOC(pl) != NULL)
		{
			send_to_char(
				"You cannot form a guild if you are currently a member of a guild.\r\n",
				pl);
			return TRUE;
		}

		arg = skip_spaces(arg);
		if ((*arg != '\'') || (arg[strlen(arg) - 1] != '\''))
		{
			send_to_char("The guild name must be enclosed in 'apostrophes'.\n", pl);
			send_to_char_f(pl, "\"%s\" is not good enough.\n", arg);
			return TRUE;
		}
		// Skip the opening '.
		snprintf(guild_name, MAX_INPUT_LENGTH, "%s", arg + 1);
		// Drop the closing ' and append a colour normal in its place. Truncating
		// first keeps the append a plain bounded write rather than one at an offset
		// the compiler cannot bound.
		const size_t quoted_length = strlen(guild_name);
		if (quoted_length)
			guild_name[quoted_length - 1] = '\0';
		checked_snprintf(guild_name + strlen(guild_name),
				 MAX_INPUT_LENGTH - strlen(guild_name), "&n");

		if (sub_string_cs(guild_name, "&-") || sub_string_cs(guild_name, "&="))
		{
			send_to_char(
				"You may not have blinking ansi or background colors in a guild name.\r\n",
				pl);
			return TRUE;
		}

		if (sub_string_set(guild_name, rude_ass))
		{
			send_to_char("No curse words. Violations will be met with ban.\r\n", pl);
			debug("Player '%s' %d is tryiing to make a rude-named guild: '%s'",
			      J_NAME(pl), GET_ID(pl), guild_name);
			return TRUE;
		}

		snprintf(buffer2, MAX_STRING_LENGTH,
			 "You have selected: %s for your guild name, is this correct? (y/n)\n",
			 guild_name);
		send_to_char(buffer2, pl);

		strcpy(pl->desc->last_command, guild_name);
		strcpy(pl->desc->client_str, "found_asc");
		pl->desc->confirm_state = CONFIRM_AWAIT;

		return TRUE;
	}
	return FALSE;
}

int get_mincircle(int spell)
{
	// Valid spells without a positive registration retain the legacy circle 13.
	int lowest = 13;

	// If not a spell, return 0.
	if (spell < FIRST_SPELL || spell > LAST_SPELL)
	{
		return 0;
	}

	// Classes are zero-based; MAX_SPEC is the last index, not the array size.
	for (const auto &class_info : skills[spell].m_class)
		for (const auto circle : class_info.rlevel)
			if (circle > 0 && circle < lowest)
				lowest = circle;

	return lowest;
}

// Calculates the base cost of ore (metal and size variables & level and skill of ch).
int calc_ore_cost(P_char ch, P_obj ore)
{
	// Cost in copper.
	float newcost;
	int vnum = OBJ_VNUM(ore);

	// Type of metal: 0=iron, 1=steel, 2=copper, 3=silver, 4=gold, 5=platinum, 6=mithril, 7=adamantium.
	switch ((vnum - LOWEST_ORE_VNUM) / 3)
	{
	case 0: // Iron
		newcost = 20000.0;
		break;
	case 1: // Tin
		newcost = 35000.0;
		break;
	case 2: // Copper
		newcost = 50000.0;
		break;
	case 3: // Silver
		newcost = 60000.0;
		break;
	case 4: // Gold
		newcost = 80000.0;
		break;
	case 5: // Platinum
		newcost = 100000.0;
		break;
	case 6: // Mithril
		newcost = 135000.0;
		break;
	case 7: // Adamantium
		newcost = 175000.0;
		break;
	default:
		// Base for unknown is 1 copper.
		newcost = 1.0;
		break;
	}

	// Size of metal: 0=small, 1=medium, 2=large
	switch ((vnum - LOWEST_ORE_VNUM) % 3)
	{
	case 0:
		// 75% cost for small.
		newcost *= .75;
		break;
	case 1:
		// 100% cost for meduim.
		newcost *= 1.0;
		break;
	case 2:
		// 150% cost for large.
		newcost *= 1.50;
		break;
	default:
		// Leave if unknown size.
		break;
	}

	// Add a little randomness for shape +/- 3%.
	newcost = newcost * number(970, 1030) / 1000.0;

	// Level/skill multipliers
	newcost *= (float)GET_LEVEL(ch) / 56.0;
	newcost *= (GET_CHAR_SKILL(ch, SKILL_MINE)) / 100.0;

	// Do you mine achievement.
	if (affected_by_spell(ch, ACH_DO_YOU_MINE))
		newcost *= 1.15;

	debug("New ore: '%s' (lvl: %d, skill: %d) value: %d,%d.", ore->short_description,
	      GET_LEVEL(ch), GET_CHAR_SKILL(ch, SKILL_MINE), (int)newcost / 1000,
	      (int)newcost % 1000);

	return (int)newcost;
}

// Calculates the base cost of a gem (metal and size variables & level and skill of ch).
int calc_gem_cost(P_char ch, P_obj gem, bool randommob)
{
	int newcost;
	int type = OBJ_VNUM(gem) - 504;
	P_char mob;

	// Base price based on gem type.
	switch (type / 8)
	{
	// Topaz
	case 0:
		newcost = 200000;
		if (randommob)
		{
			// A hideous zombie (#92)
			// a corpse gatherer (#89)
			mob = read_mobile(number(0, 1) ? 89 : 92, VIRTUAL);
			// Enters from below.
			char_to_room(mob, ch->in_room, 4);
		}
		break;
	// Sapphire
	case 1:
		newcost = 250000;
		if (randommob)
		{
			// An antlion (#94)
			// A purple worm (#95)
			mob = read_mobile(number(94, 95), VIRTUAL);
			// Enters from below.
			char_to_room(mob, ch->in_room, 4);
		}
		break;
	// Emerald
	case 2:
		newcost = 300000;
		if (randommob)
		{
			// a swarm of earth beetles (#97)
			// A skeletal warrior (#93)
			mob = read_mobile(number(0, 1) ? 93 : 97, VIRTUAL);
			// Enters from below.
			char_to_room(mob, ch->in_room, 4);
		}
		break;
	// Diamond
	case 3:
		newcost = 250000;
		if (randommob)
		{
			// A mohrg (#91)
			// a sleeping earth elemental (#96)
			mob = read_mobile(number(0, 1) ? 91 : 96, VIRTUAL);
			// Enters from below.
			char_to_room(mob, ch->in_room, 4);
		}
		break;
	// Ruby
	case 4:
		newcost = 300000;
		if (randommob)
		{
			// a GIANT purple worm (#90)
			// a burrow wraith (#98)
			mob = read_mobile(number(0, 1) ? 90 : 98, VIRTUAL);
			// Enters from below.
			char_to_room(mob, ch->in_room, 4);
		}
		break;
	// Buggy gemstones are 1 plat base.
	default:
		newcost = 1000;
		break;
	}
	newcost *= (float)GET_LEVEL(ch) / 56.0;
	newcost *= (GET_CHAR_SKILL(ch, SKILL_MINE)) / 100.0;
	switch (type % 8)
	{
	// Tiny imperfect.
	case 0:
		break;
	// Reg Imperfect.
	case 1:
		newcost *= 1.05;
		break;
	// Large Imperfect.
	case 2:
		newcost *= 1.15;
		break;
	// Tiny Reg.
	case 3:
		newcost *= 1.20;
		break;
	// Reg Reg.
	case 4:
		newcost *= 1.25;
		break;
	// Large Reg.
	case 5:
		newcost *= 1.35;
		break;
	// Reg Flawless.
	case 6:
		newcost *= 1.65;
		break;
	// Large Flawless.
	case 7:
		newcost *= 1.85;
		break;
	default:
		break;
	}
	return newcost;
}
