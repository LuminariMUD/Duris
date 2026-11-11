#include "item/named_set_effects.h"

/*
 ***************************************************************************
 *  File: new_skills.c                                       Part of Duris *
 *  Usage: This needs a better name (and organization) -JAB                *
 *  Copyright 1994 - 2008 - Duris Systems Ltd.                             *
 ***************************************************************************
 */

#include "core/prototypes.h"
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "core/utility.h"
#include "core/utils.h"
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "combat/damage.h"
#include "combat/guard.h"
#include "combat/justice.h"
#include "combat/training_dummy.h"
#include "item/objmisc.h"
#include "item/item_movement_transaction.h"
#include "magic/spells.h"
#include "world/weather.h"
#include "abilities/abilities.h"
/*
   external variables
 */

extern P_room world;
// extern char *dirs[];
extern const struct stat_data stat_factor[];
extern int innate_abilities[];
extern int class_innates[][5];
extern struct time_info_data time_info;
extern struct zone_data *zone;
extern struct zone_data *zone_table;
extern struct str_app_type str_app[];
extern const int numCarvables;
extern const char *carve_part_name[];
extern const int carve_part_flag[];
extern P_obj object_list;
extern P_index obj_index;
extern P_char character_list;

enum class summoned_replacement_kind : uint8_t
{
	book,
	totem,
};

struct summoned_replacement_context
{
	uint64_t item_uid;
	uint32_t recipient_pid;
	uint8_t kind;
};

static_assert(sizeof(summoned_replacement_context) <= ITEM_MOVEMENT_CONTEXT_MAX_BYTES);

static P_obj new_skills_find_object_by_uid(uint64_t item_uid)
{
	if (!item_uid)
		return NULL;
	for (P_obj object = object_list; object; object = object->next)
		if (object->obj_uid == item_uid)
			return object;
	return NULL;
}

static bool summoned_book_matches(P_obj object, P_char actor)
{
	if (!object || !object->name || !actor)
		return false;
	char bookname[512];
	snprintf(bookname, sizeof(bookname), "bookof%s", actor->player.name);
	char *suffix = strstr(object->name, bookname);
	return suffix && strcmp(suffix, bookname) == 0;
}

static bool summoned_totem_matches(P_obj object, P_char actor)
{
	if (!object || !object->name || !actor)
		return false;
	char totemname[512];
	snprintf(totemname, sizeof(totemname), "totem spirit %s", actor->player.name);
	char *suffix = strstr(object->name, totemname);
	return suffix && strcmp(suffix, totemname) == 0 && OBJ_VNUM(object) == 417;
}

static bool summoned_replacement_kind_valid(uint8_t kind)
{
	return kind == static_cast<uint8_t>(summoned_replacement_kind::book) ||
	       kind == static_cast<uint8_t>(summoned_replacement_kind::totem);
}

static void retire_other_summoned_items(P_char actor, uint64_t keep_uid,
					summoned_replacement_kind kind)
{
	for (P_obj object = object_list; object;)
	{
		P_obj next = object->next;
		const bool matches = kind == summoned_replacement_kind::book ?
					     summoned_book_matches(object, actor) :
					     summoned_totem_matches(object, actor);
		if (object->obj_uid != keep_uid && matches)
			extract_obj(object);
		object = next;
	}
}

static void summoned_replacement_completed(P_char actor, bool committed,
					   const item_transfer_result &result,
					   unsigned int /*error_code*/, const uint8_t *encoded,
					   size_t encoded_size)
{
	if (!actor || !encoded || encoded_size != sizeof(summoned_replacement_context) ||
	    GET_PID(actor) <= 0)
		return;

	summoned_replacement_context context = {};
	memcpy(&context, encoded, sizeof(context));
	if (context.recipient_pid != static_cast<uint32_t>(GET_PID(actor)) ||
	    !summoned_replacement_kind_valid(context.kind))
	{
		logit(LOG_FILE,
		      "summoned replacement completion had invalid context (uid=%llu pid=%d kind=%u)",
		      (unsigned long long)context.item_uid, GET_PID(actor),
		      static_cast<unsigned int>(context.kind));
		return;
	}
	const summoned_replacement_kind kind = static_cast<summoned_replacement_kind>(context.kind);
	if (!committed)
	{
		send_to_char(
			kind == summoned_replacement_kind::book ?
				"The magical spellbook could not be delivered; your existing spellbook was kept. "
				"Please try again later.\r\n" :
				"The magical totem could not be delivered; your existing totem was kept. "
				"Please try again later.\r\n",
			actor);
		return;
	}
	if (result.root_item_uid != context.item_uid || !result.item_count)
	{
		logit(LOG_FILE,
		      "summoned replacement completion identity mismatch (expected=%llu actual=%llu pid=%d kind=%u)",
		      (unsigned long long)context.item_uid,
		      (unsigned long long)result.root_item_uid, GET_PID(actor),
		      static_cast<unsigned int>(context.kind));
		send_to_char(
			"The ownership authority returned an unexpected replacement; your existing item was kept.\r\n",
			actor);
		return;
	}

	P_obj replacement = new_skills_find_object_by_uid(context.item_uid);
	const bool replacement_matches = kind == summoned_replacement_kind::book ?
						 summoned_book_matches(replacement, actor) :
						 summoned_totem_matches(replacement, actor);
	if (!replacement || !OBJ_CARRIED_BY(replacement, actor) || !replacement_matches)
	{
		logit(LOG_FILE,
		      "summoned replacement committed without live publication (uid=%llu pid=%d kind=%u)",
		      (unsigned long long)context.item_uid, GET_PID(actor),
		      static_cast<unsigned int>(context.kind));
		send_to_char(
			"The ownership authority delivered the replacement, but it is not available yet.\r\n",
			actor);
		return;
	}

	retire_other_summoned_items(actor, context.item_uid, kind);
	send_to_char(
		kind == summoned_replacement_kind::book ?
			"&+LA magical spellbook materializes slowly in your hands.&n\r\n" :
			"&+GMaglubiyet&n answers your call, and a magic totem slowly materializes in your hands.\r\n",
		actor);
}

static bool submit_summoned_replacement(P_char actor, P_obj object, summoned_replacement_kind kind)
{
	if (!actor || !object)
		return false;
	if (!IS_PC(actor))
	{
		obj_to_char(object, actor);
		retire_other_summoned_items(actor, object->obj_uid, kind);
		send_to_char(
			kind == summoned_replacement_kind::book ?
				"&+LA magical spellbook materializes slowly in your hands.&n\r\n" :
				"&+GMaglubiyet&n answers your call, and a magic totem slowly materializes in your hands.\r\n",
			actor);
		return true;
	}

	const summoned_replacement_context context = {
		object->obj_uid,
		static_cast<uint32_t>(GET_PID(actor)),
		static_cast<uint8_t>(kind),
	};
	if (item_creation_grant_submit_to_player_with_completion(actor, object, actor,
								 summoned_replacement_completed,
								 &context, sizeof(context)))
		return true;

	extract_obj(object, FALSE);
	send_to_char(
		kind == summoned_replacement_kind::book ?
			"The magical spellbook could not be created; your existing spellbook was kept. "
			"Please try again later.\r\n" :
			"The magical totem could not be created; your existing totem was kept. "
			"Please try again later.\r\n",
		actor);
	return false;
}

/*
   This func contains collection of those basic checks that all
   fighting-related commands should do. Collected here so I need
   not change all zillion places if I want to fix change something.
   -Torm
 */

int CanDoFightMove(P_char ch, P_char victim)
{
	if (!ch || !victim)
		return FALSE;
	if (training_dummy_is(ch))
		return FALSE;
	if (!training_dummy_target_allowed(ch, victim))
	{
		training_dummy_retarget_nonpet(ch, victim);
		return FALSE;
	}

	if (victim == ch)
	{
		send_to_char("Aren't we funny today...\r\n", ch);
		return FALSE;
	}

	if (!IS_ALIVE(victim))
	{
		debug("CanDoFightMove in new_skills.c called on dead victim '%s'.",
		      victim ? J_NAME(victim) : "NULL");
		send_to_char("What?  Dead isn't good enough?  Leave that corpse alone!\r\n", ch);
		return FALSE;
	}

	if (!IS_ALIVE(ch))
	{
		debug("CanDoFightMove in new_skills.c called on by dead ch '%s'.",
		      ch ? J_NAME(ch) : "NULL");
		return FALSE;
	}

	if (!IS_AWAKE(ch))
	{
		send_to_char("You can't do that if you're not awake!\r\n", ch);
		return FALSE;
	}

	if (affected_by_spell(ch, SONG_PEACE))
	{
		send_to_char("You feel way too peaceful to consider doing anything offensive!\r\n",
			     ch);
		return FALSE;
	}

	if (CHAR_IN_SAFE_ROOM(ch) && !training_dummy_is(victim))
	{
		send_to_char(
			"You feel ashamed trying to disrupt the tranquility of this place.\r\n",
			ch);
		return FALSE;
	}

	if (GET_MASTER(ch) == victim && GET_MASTER(ch))
	{
		act("$N is just such a good friend, you simply can't harm $M.", FALSE, ch, 0,
		    victim, TO_CHAR);
		return FALSE;
	}

	if (get_linked_char(ch, LNK_RIDING))
	{
		if (!GET_CHAR_SKILL(ch, SKILL_MOUNTED_COMBAT) /*&& !is_natural_mount(ch, mount)*/)
		{
			send_to_char("While mounted? I don't think so...\r\n", ch);
			return FALSE;
		}
	}

	if (get_linking_char(ch, LNK_RIDING) == victim)
	{
		send_to_char("You can't harm your rider.\r\n", ch);
		return FALSE;
	}

	if (IS_ROOM(ch->in_room, ROOM_SINGLE_FILE) && !AdjacentInRoom(ch, victim))
	{
		act("$N seems to be just a BIT out of reach.", FALSE, ch, 0, victim, TO_CHAR);
		return FALSE;
	}

	if (!CAN_SEE(ch, victim))
	{
		send_to_char("Um.. you don't see any such target here?\r\n", ch);
		return FALSE;
	}

	if (affected_by_spell(ch, SKILL_GAZE))
	{
		send_to_char("You are too petrified with fear to try that.\r\n", ch);
		return FALSE;
	}

	if (IS_AFFECTED2(ch, AFF2_STUNNED))
	{
		send_to_char("You're too stunned to contemplate that!\r\n", ch);
		return FALSE;
	}

	if (IS_AFFECTED(ch, AFF_KNOCKED_OUT))
	{
		send_to_char("You can't do much of anything while knocked out!\r\n", ch);
		return FALSE;
	}

	if (IS_AFFECTED2(ch, AFF2_MINOR_PARALYSIS) || IS_AFFECTED2(ch, AFF2_MAJOR_PARALYSIS))
	{
		send_to_char("It's tough to do anything while paralyzed.\r\n", ch);
		return FALSE;
	}

	if (IS_AFFECTED(ch, AFF_BOUND))
	{
		send_to_char("You're too bound to do that.\r\n", ch);
		return FALSE;
	}

	if (IS_AFFECTED5(ch, AFF5_NOT_OFFENSIVE))
	{
		send_to_char("Since you are not being offensive... try something else.\r\n", ch);
		return false;
	}

	return TRUE;
}

/*
   Generic function, but initially created for Shadow skill.

   * This function will recursively count the number of followers
   * effectively following 'ch'.  This means that 'ch' may have 3 chars
   * following him/her, but also, each of those chars have some followers.
   * The total number in the "tree" is returned.
   *
   *   --TAM 7-6-94
 */

int CountNumFollowers(P_char ch)
{
	struct follow_type *f;
	int count = 0;

	f = ch->followers;

	if (!f)
	{
		return 0;
	}
	else
	{
		while (f)
		{
			++count;
			count += CountNumFollowers(f->follower);
			f = f->next;
		}
	}

	return count;
}

int CountNumGreaterElementalFollowersInSameRoom(P_char ch)
{
	struct char_link_data *cld;
	P_char follower;
	int i = 0;

	if (!IS_ALIVE(ch))
	{
		return 0;
	}

	for (cld = ch->linked; cld; cld = cld->next_linked)
	{
		follower = cld->linking;

		if (cld->type != LNK_PET)
		{
			continue;
		}

		if (GET_LEVEL(follower) > 45 && IS_NPC(follower) && IS_PC_PET(follower) &&
		    IS_ELEMENTAL(follower))
		{
			i++;
		}
	}
	return i;
}

/* Awareness skill for assassins and rangers.   --TAM 7-8-94 */

// The most ticks awareness can last at this rating, before its roll.
static int awareness_max_duration(P_char ch, int skl_lvl)
{
	int duration = (int)((1 + (GET_LEVEL(ch) >> 3) * skl_lvl / 75));
	duration *= STAT_INDEX(GET_C_INT(ch)) / 9;
	return duration;
}

// The roll that picks awareness's duration, given a positive maximum.
static int awareness_rolled_duration(const Rolls &rolls, int duration)
{
	return rolls.number(1, duration);
}

std::string awareness_facts(P_char ch)
{
	const int most = awareness_max_duration(ch, GET_CHAR_SKILL(ch, SKILL_AWARENESS));
	return fact("Duration",
		    most > 0 ?
			    game_hours_range({ awareness_rolled_duration(lowest_rolls, most),
					       awareness_rolled_duration(highest_rolls, most) }) :
			    game_hours(most)) +
	       "  It always works. It lasts longer with intelligence, level and rating.\n";
}

void apply_awareness(P_char ch, int skl_lvl)
{
	struct affected_type af, *af_ptr;
	int duration = 0, lev_aware;
	lev_aware = STAT_INDEX(GET_C_INT(ch)) + STAT_INDEX(GET_C_DEX(ch)) + (GET_LEVEL(ch) >> 3);
	lev_aware = lev_aware * skl_lvl / 75;
	if (lev_aware > 0)
	{
		lev_aware = number((lev_aware >> 1), lev_aware);
	}
	duration = awareness_max_duration(ch, skl_lvl); /*
	                                              lower than 13 and player
	                                              suffers 'lack of attn span'
	                                              penalty
	                                            */
	if (duration > 0)
	{
		duration = awareness_rolled_duration(live_rolls, duration);
	}
	bzero(&af, sizeof(af));
	af.type = SKILL_AWARENESS;
	af.duration = duration;
	af.modifier = lev_aware;
	af.bitvector = AFF_SKILL_AWARE;
	af.flags = AFFTYPE_NODISPEL;

	if (IS_AFFECTED(ch, AFF_SKILL_AWARE))
	{
		for (af_ptr = ch->affected; af_ptr; af_ptr = af_ptr->next)
		{
			if (af_ptr->type == SKILL_AWARENESS)
			{
				break;
			}
		}
		if (af_ptr)
			affect_remove(ch, af_ptr);
		REMOVE_BIT(ch->specials.affected_by, AFF_SKILL_AWARE);
	}
	affect_to_char(ch, &af);
}

void do_awareness(P_char ch, char * /*argument*/, int /*cmd*/)
{
	int skl_lvl = 0;

	if (IS_PC(ch))
		skl_lvl = GET_CHAR_SKILL(ch, SKILL_AWARENESS);

	if (!skl_lvl)
	{
		act("You wouldn't know where to begin.", TRUE, ch, 0, 0, TO_CHAR);
		return;
	}
	act("You feel aligned with your surroundings.", TRUE, ch, 0, 0, TO_CHAR);

	named_set_ordinary_cast ordinary_cast(ch, SKILL_AWARENESS);
	apply_awareness(ch, skl_lvl);
	notch_skill(ch, SKILL_AWARENESS, 20);
}

int wornweight(P_char ch)
{
	int enc;
	int i;

	enc = 0;
	for (i = 0; i < MAX_WEAR; i++)
		if (ch->equipment[i])
			enc += (GET_OBJ_WEIGHT(ch->equipment[i]));
	return enc;
}

int MonkAcBonus(P_char ch)
{
	int b;

	if (GET_CLASS(ch, CLASS_MONK))
	{
		/*
		   base bonus level * 4
		 */
		b = -(4 * GET_LEVEL(ch));
		// Bonus based on martial arts skill
		b -= GET_CHAR_SKILL(ch, SKILL_MARTIAL_ARTS);
		/*
		   3x penalty for encumbering worn items with a small allowance for low levels
		 */
		b += MAX(0, (3 * (wornweight(ch) - ((60 - GET_LEVEL(ch)) / 6))));

		return BOUNDED(-400, b, 50);
	}
	else
		return 0;
}

void MonkSetSpecialDie(P_char ch)
{
	if (IS_PC(ch) && (ch->equipment[WIELD] || ch->equipment[WEAR_SHIELD] ||
			  ch->equipment[HOLD] || ch->equipment[SECONDARY_WEAPON]))
	{
		ch->points.damnodice = 1;
		ch->points.damsizedice = 1;
		return;
	}
	switch (GET_LEVEL(ch))
	{
	case 1:
	case 2:
	case 3:
		ch->points.damnodice = 2;
		ch->points.damsizedice = 5;
		break;
	case 4:
	case 5:
	case 6:
	case 7:
		ch->points.damnodice = 2;
		ch->points.damsizedice = 6;
		break;
	case 8:
	case 9:
	case 10:
	case 11:
	case 12:
	case 13:
	case 14:
		ch->points.damnodice = 2;
		ch->points.damsizedice = 8;
		break;
	case 15:
	case 16:
	case 17:
	case 18:
	case 19:
	case 20:
	case 21:
		ch->points.damnodice = 4;
		ch->points.damsizedice = 5;
		break;
	case 22:
	case 23:
	case 24:
	case 25:
	case 26:
	case 27:
	case 28:
	case 29:
		ch->points.damnodice = 5;
		ch->points.damsizedice = 5;
		break;
	case 30:
	case 31:
	case 32:
	case 33:
	case 34:
		ch->points.damnodice = 5;
		ch->points.damsizedice = 6;
		break;
	case 35:
	case 36:
	case 37:
	case 38:
		ch->points.damnodice = 5;
		ch->points.damsizedice = 7;
		break;
	case 39:
	case 40:
	case 41:
	case 42:
	case 43:
	case 44:
		ch->points.damnodice = 6;
		ch->points.damsizedice = 6;
		break;
	case 45:
	case 46:
	case 47:
	case 48:
	case 49:
		ch->points.damnodice = 6;
		ch->points.damsizedice = 7;
		break;
	case 50:
	case 51:
	case 52:
	case 53:
	case 54:
	case 55:
		ch->points.damnodice = 7;
		ch->points.damsizedice = 7;
		break;
	case 56:
	case 57:
	case 58:
	case 59:
	case 60:
	case 61:
	case 62:
		ch->points.damnodice = 8;
		ch->points.damsizedice = 8;
		break;
	default:
		ch->points.damnodice = 1;
		ch->points.damsizedice = 4;
		break;
	}
}

// What a player's martial arts adds to a monk's bare-hand damage.
static int monk_damage_bonus(int skl_lvl)
{
	return skl_lvl / 11;
}

int MonkDamage(P_char ch)
{
	int dam;
	int skl_lvl = 0;

	if (IS_PC(ch))
		skl_lvl = GET_CHAR_SKILL(ch, SKILL_MARTIAL_ARTS);

	if (GET_CLASS(ch, CLASS_MONK))
	{
		MonkSetSpecialDie(ch);
	}
	dam = dice(ch->points.damnodice, ch->points.damsizedice);
	dam += monk_damage_bonus(skl_lvl);

	if (GET_CLASS(ch, CLASS_MONK))
	{
		// Weight factor affected by lvl and str.
		int weight = wornweight(ch) - (GET_LEVEL(ch) * GET_C_STR(ch)) / 100;
		// Does at least 1 damage, and at most dam damage.
		dam = BOUNDED(1, dam - weight, dam);
	}
	return dam;
}

// How many of a monk's attack rolls each round: more for a low roll.
static int monk_attack_rolls(const Rolls &rolls, P_char ch)
{
	return ((4 * GET_LEVEL(ch)) / rolls.number(25, 38));
}

// A monk's attacks from how many of those rolls hit.
static int monk_attack_count(P_char ch, int a)
{
	if (GET_LEVEL(ch) >= 51)
	{
		if (GET_LEVEL(ch) >= 56)
			return BOUNDED(1, a + 2, 7);
		else
			return BOUNDED(1, a + 1, 6);
	}

	return BOUNDED(1, a, 5); /* 1 to 4 */
}

// The most of those rolls that count.
static int monk_attack_roll_limit()
{
	return 6;
}

int MonkNumberOfAttacks(P_char ch)
{
	int a, l;
	int skl_lvl = 0;

	/*
	   simplified combat routine, return 1 if not a monk
	 */
	/*  if (IS_AFFECTED4(ch, AFF4_VAMPIRE_FORM))
	      return 2 + number(0,1);*/
	// handled elsewhere
	if (!GET_CLASS(ch, CLASS_MONK))
		return 1;

	/*
	   monks without both hands free get 1 attack, period
	 */
	if (IS_PC(ch) &&
	    (ch->equipment[WIELD] || ch->equipment[SECONDARY_WEAPON] || ch->equipment[HOLD] ||
	     ch->equipment[WEAR_SHIELD] || ch->equipment[WEAR_LIGHT]))
		return 1;
	if (IS_PC(ch))
	{
		skl_lvl = GET_CHAR_SKILL(ch, SKILL_MARTIAL_ARTS);
		notch_skill(ch, SKILL_MARTIAL_ARTS, 1);
	}
	else
		skl_lvl = BOUNDED(5, GET_LEVEL(ch) * 2, 100);

	for (a = 0, l = monk_attack_rolls(live_rolls, ch);
	     (a < monk_attack_roll_limit()) && (l > 0); l--)
		if (number(1, 100) < skl_lvl)
			a++;
	return monk_attack_count(ch, a);
}

extern int monk_riposte_chance(int learned, int percent);
extern int monk_rise_rest();

std::string martial_arts_facts(P_char ch)
{
	if (!GET_CLASS(ch, CLASS_MONK))
		return "  Only monks fight with martial arts.\n";
	const int rating = GET_CHAR_SKILL(ch, SKILL_MARTIAL_ARTS);
	const int rolled = MIN(monk_attack_roll_limit(), monk_attack_rolls(lowest_rolls, ch));
	std::string text =
		fact("Armor class", std::to_string(MonkAcBonus(ch))) +
		"    (level and rating, less a penalty for full equipped weight)\n" +
		fact("Bare-hand damage added", std::to_string(monk_damage_bonus(rating))) +
		"    (full equipped weight above level * STR / 100 reduces base damage)\n" +
		fact("Attacks each round",
		     show({ monk_attack_count(ch, 0),
			    monk_attack_count(ch, rating > 1 ? rolled : 0) })) +
		"    (1 with a weapon, shield, held item, or equipped light)\n"
		"    (sum half of each equipped item's weight, rounded down)\n"
		"    (lose 1 per full 10 lb above STR / 2; at least 1 remains)\n"
		"    (weight reduces base attacks before slow and other modifiers)\n"
		"    (inventory ignored; worn bags include their effective contents)\n";
	if (rating)
		text += fact("Chance to counter a blow",
			     show({ monk_riposte_chance(rating, -100000),
				    monk_riposte_chance(rating, 100000) }) +
				     " in 150") +
			"    (half that against an elite or greater race)\n" +
			fact("Chance a knockdown lets you roll back up",
			     chance_under(GET_C_AGI(ch), 1, 1000) + ", then " +
				     chance_under(rating, 1, 100)) +
			fact("Before you can roll back up again", seconds(monk_rise_rest()));
	return text + "  It also feeds your kick.\n";
}

// What chanting takes first.
static std::string chant_note()
{
	return "  Your chant skill has its own roll first, and chanting adds its lag.\n";
}

// A roll of 1-101 below this fools the attackers, and again for each one it fools.
static int feign_death_threshold(const Rolls &rolls, int skl_lvl)
{
	return skl_lvl * rolls.number(2, 5) / 2;
}

static int feign_death_rest(P_char ch)
{
	int duration = WAIT_SEC * get_property("timer.secs.feignDeath", 60);
	if (GET_CLASS(ch, CLASS_NECROMANCER))
	{
		duration /= 3;
	}
	return duration;
}

// Above this level, a necromancer or theurgist who fools an attacker is forgotten too.
static int feign_death_forget_level()
{
	return 40;
}

static int feign_death_lag()
{
	return PULSE_VIOLENCE * 2;
}

static int feign_death_failed_lag()
{
	return PULSE_VIOLENCE * 3;
}

std::string feign_death_facts(P_char ch)
{
	const int rating = GET_CHAR_SKILL(ch, SKILL_FEIGN_DEATH);
	if (!rating)
		return "  You have not learned feign death.\n";
	std::string text =
		fact("Chance it stops the fight",
		     chance_under(feign_death_threshold(lowest_rolls, rating), 1, 101) + " to " +
			     chance_under(feign_death_threshold(highest_rolls, rating), 1, 101)) +
		"  Each attacker then rolls the same chance: it stops casting, and you hide.\n" +
		fact("Your lag if it works", seconds(feign_death_lag())) +
		fact("Your lag if it fails", seconds(feign_death_failed_lag())) +
		"  You end up prone if it fails, or if it works while anyone attacks you.\n" +
		fact("Before you can try again, even after a failure",
		     real_time(feign_death_rest(ch)));
	if (GET_CLASS(ch, CLASS_NECROMANCER) || GET_CLASS(ch, CLASS_THEURGIST))
		text += "  Above level " + std::to_string(feign_death_forget_level()) +
			", NPCs in the room also forget you when it works.\n";
	return text + "  Only while fighting, and not while riding.\n";
}

void do_feign_death(P_char ch, char * /*arg*/, int /*cmd*/)
{
	P_char t = NULL, t_next, tch;
	int skl_lvl = 0;
	struct affected_type af;

	if (IS_PC(ch))
	{
		skl_lvl = GET_CHAR_SKILL(ch, SKILL_FEIGN_DEATH);
	}
	else
	{
		skl_lvl = MIN(100, GET_LEVEL(ch) * 3);
	}

	if (!GET_OPPONENT(ch))
	{
		send_to_char("You are not fighting anything!\r\n", ch);
		return;
	}
	if (!skl_lvl)
	{
		send_to_char("You know not how!\r\n", ch);
		return;
	}
	if (IS_RIDING(ch))
	{
		send_to_char("While mounted? I don't think so...\r\n", ch);
		return;
	}

	// Changed this so wear off message works.. might want to redo affect_timer as a whole.
	//  if( !affect_timer(ch, WAIT_SEC * get_property("timer.secs.feignDeath", 60), SKILL_FEIGN_DEATH) )
	if (affected_by_spell(ch, SKILL_FEIGN_DEATH))
	{
		send_to_char("You don't feel up to faking it right now.\r\n", ch);
		return;
	}

	if (IS_PC(ch))
	{
		memset(&af, 0, sizeof(af));
		af.type = SKILL_FEIGN_DEATH;
		af.flags = AFFTYPE_STORE | AFFTYPE_SHORT;
		af.duration = feign_death_rest(ch);
		af.modifier = 0;
		affect_to_char(ch, &af);
	}

	send_to_char("You try to fake your own demise..\r\n", ch);
	death_cry(ch);
	act("$n is dead! R.I.P.", FALSE, ch, 0, 0, TO_ROOM);
	if (number(1, 101) < feign_death_threshold(live_rolls, skl_lvl))
	{
		stop_fighting(ch);
		for (t = world[ch->in_room].people; t; t = t_next)
		{
			t_next = t->next_in_room;
			if (GET_OPPONENT(t) == ch)
			{
				stop_fighting(t);
				if ((GET_CLASS(ch, CLASS_NECROMANCER) ||
				     GET_CLASS(ch, CLASS_THEURGIST)) &&
				    GET_LEVEL(ch) > feign_death_forget_level())
				{
					LOOP_THRU_PEOPLE(tch, ch)
					{
						if (IS_NPC(tch) && HAS_MEMORY(tch))
						{
							debug("FEIGN: (%s) feigned death and mob (%s) removed.",
							      GET_NAME(ch), J_NAME(tch));
							if (!ch || !tch)
								return;
							forget(tch, ch);
						}
					}
				}
				if (number(1, 101) < feign_death_threshold(live_rolls, skl_lvl))
				{
					if (IS_CASTING(t))
						StopCasting(t);
					SET_BIT(ch->specials.affected_by, AFF_HIDE);
				}
				SET_POS(ch, POS_PRONE + STAT_RESTING); // was SLEEPING..
			}
		}
		CharWait(ch, feign_death_lag());
		notch_skill(ch, SKILL_FEIGN_DEATH, 40);
		return;
	}
	else
	{
		SET_POS(ch, POS_PRONE + STAT_RESTING); // ditto
		notch_skill(ch, SKILL_FEIGN_DEATH, 40);
		CharWait(ch, feign_death_failed_lag());
	}
}

void do_first_aid(P_char ch, char * /*arg*/, int /*cmd*/)
{
	struct affected_type af;
	int skl_lvl = 0, bonus;

	if (IS_NPC(ch))
		return;

	send_to_char("Try using the bandage instead.", ch);
	return;

	if (has_innate(ch, INNATE_BATTLEAID))
	{
		bonus = dice(10, 10);
		send_to_char("Your increased knowledge helps you apply more efficent first aid.",
			     ch);
	}
	else
	{
		bonus = 0;
	}

	skl_lvl = GET_CHAR_SKILL(ch, SKILL_FIRST_AID);

	send_to_char("You attempt to render first aid unto yourself..\r\n", ch);

	if (affected_by_spell(ch, SKILL_FIRST_AID))
	{
		send_to_char("You can only do this once per day..\r\n", ch);
		return;
	}
	if (GET_HIT(ch) < GET_MAX_HIT(ch))
	{
		GET_HIT(ch) += (MAX(5, skl_lvl / 3) + bonus);
		if (GET_HIT(ch) > GET_MAX_HIT(ch))
			GET_HIT(ch) = GET_MAX_HIT(ch);
	}
	notch_skill(ch, SKILL_FIRST_AID, 17);

	bzero(&af, sizeof(af));
	af.duration = 24;
	af.type = SKILL_FIRST_AID;
	af.flags = AFFTYPE_NOSHOW | AFFTYPE_PERM | AFFTYPE_NODISPEL;
	affect_to_char(ch, &af);
}

static int calm_lag()
{
	return PULSE_VIOLENCE;
}

std::string calm_facts(P_char ch)
{
	if (!GET_CLASS(ch, CLASS_MONK) && !IS_TRUSTED(ch))
		return "  Only monks can chant calm.\n";
	const int rating = GET_CHAR_SKILL(ch, SKILL_CALM);
	if (rating < 1)
		return "  You need this skill to chant calm.\n";
	return fact("Chance for each fighter in the room", chance_under(rating, 1, 130)) +
	       "  A calmed fighter, you included, stops fighting and forgets its grudges.\n"
	       "  Not on elites or greater races.\n" +
	       fact("Your lag", seconds(calm_lag())) + chant_note();
}

void chant_calm(P_char ch, char * /*argument*/, int /*cmd*/)
{
	P_char d = NULL;
	int skl_lvl = 0;

	if (!GET_CLASS(ch, CLASS_MONK) && !IS_TRUSTED(ch))
	{
		send_to_char("Just breathe deeply, will calm you right down.\r\n", ch);
		return;
	}

	if (IS_PC(ch))
		skl_lvl = GET_CHAR_SKILL(ch, SKILL_CALM);
	else
		skl_lvl = MAX(100, GET_LEVEL(ch) * 3);

	send_to_char("You chant for peace and happiness for all.\r\n", ch);

	for (d = world[ch->in_room].people; d; d = d->next_in_room)
	{
		if (GET_OPPONENT(d))
		{
			if (notch_skill(ch, SKILL_CALM, 10) || number(1, 130) < skl_lvl)
			{
				if (!IS_GREATER_RACE(d) && !IS_ELITE(d))
				{
					stop_fighting(d);
					clearMemory(d);
					send_to_char("A sense of calm comes upon you.\r\n", d);
				}
			}
		}
	}
	CharWait(ch, calm_lag());
}

static int diamond_soul_duration(P_char ch)
{
	return MAX(2, (GET_LEVEL(ch) / 16) + 2);
}

static int diamond_soul_rest()
{
	return WAIT_SEC * get_property("timer.secs.monkDiamond", 120);
}

static int diamond_soul_failed_lag()
{
	return PULSE_VIOLENCE;
}

static int diamond_soul_lag()
{
	return PULSE_VIOLENCE;
}

static int diamond_soul_save(P_char ch)
{
	return -(MAX(2, (int)(GET_LEVEL(ch) / 8)));
}

std::string diamond_soul_facts(P_char ch)
{
	if (!GET_CLASS(ch, CLASS_MONK) && !IS_TRUSTED(ch))
		return "  Only monks can chant diamond soul.\n";
	const int rating = GET_CHAR_SKILL(ch, SKILL_DIAMOND_SOUL);
	if (rating < 1)
		return "  You need this skill to chant diamond soul.\n";
	return fact("Chance", chance_under(rating + 1, 1, 105)) +
	       fact("Duration", game_hours(diamond_soul_duration(ch))) +
	       fact("Saving throws against spells and paralysis",
		    std::to_string(diamond_soul_save(ch)) + " (lower is better)") +
	       fact("Before you can chant it again, even after a failure",
		    IS_TRUSTED(ch) ? "no wait, as an immortal" : seconds(diamond_soul_rest())) +
	       fact("Your lag", seconds(diamond_soul_lag())) +
	       fact("Your lag if you fail", seconds(diamond_soul_failed_lag())) +
	       "  Not under heroism.\n" + chant_note();
}

void chant_diamond_soul(P_char ch, char * /*argument*/, int /*cmd*/)
{
	struct affected_type af;
	char buf[100];
	int skl_lvl = 0;
	int duration = diamond_soul_duration(ch);

	if (!GET_CLASS(ch, CLASS_MONK) && !IS_TRUSTED(ch))
	{
		send_to_char("Try becoming a monk first.\r\n", ch);
		return;
	}

	if (!affect_timer(ch, diamond_soul_rest(), SKILL_DIAMOND_SOUL))
	{
		send_to_char("Your mind needs rest...\r\n", ch);
		return;
	}

	if (IS_PC(ch) || IS_PC_PET(ch))
		skl_lvl = GET_CHAR_SKILL(ch, SKILL_DIAMOND_SOUL);
	else
		skl_lvl = GET_LEVEL(ch) * 2;

	if (affected_by_spell(ch, SKILL_DIAMOND_SOUL))
	{
		send_to_char("You are already under the affects of diamond soul.\r\n", ch);
		return;
	}

	if (affected_by_spell(ch, SKILL_HEROISM))
	{
		send_to_char(
			"You cannot call upon the diamond soul technique while under the influence of heroism.\r\n",
			ch);
		return;
	}

	if (!notch_skill(ch, SKILL_DIAMOND_SOUL, 30) &&
	    number(1, 105) > skl_lvl) // 5 percent chance to fail at max pc skill.
	{
		send_to_char("Your inner thoughts are in turmoil.\r\n", ch);
		CharWait(ch, diamond_soul_failed_lag());
		return;
	}

	snprintf(buf, 100, "You feel your magical resistance harden like a diamond.\r\n");
	bzero(&af, sizeof(af));
	af.type = SKILL_DIAMOND_SOUL;
	af.flags = AFFTYPE_NODISPEL;
	af.duration = duration;

	af.modifier = diamond_soul_save(ch);
	af.location = APPLY_SAVING_SPELL;
	affect_to_char(ch, &af);

	af.modifier = diamond_soul_save(ch);
	af.location = APPLY_SAVING_PARA;
	af.wear_off_message_index = 1;
	affect_to_char(ch, &af);

	send_to_char(buf, ch);

	CharWait(ch, diamond_soul_lag());
}

static int heroism_duration(P_char ch)
{
	return MAX(5, (GET_LEVEL(ch) / 4) + 2);
}

static int heroism_rest()
{
	return WAIT_SEC * get_property("timer.secs.monkHeroism", 120);
}

static int heroism_lag()
{
	return PULSE_VIOLENCE;
}

static int heroism_hitroll(P_char ch)
{
	return MAX(2, (int)(GET_LEVEL(ch) / 8));
}

static int heroism_damroll(P_char ch)
{
	return MAX(2, GET_LEVEL(ch) / 8);
}

// The levels a monk's heroism adds a dazzling glow (way of the snake), haste, and blur.
static int heroism_dazzle_level()
{
	return 36;
}

static int heroism_haste_level()
{
	return 51;
}

static int heroism_blur_level()
{
	return 56;
}

std::string heroism_facts(P_char ch)
{
	if (!GET_CLASS(ch, CLASS_MONK) && !IS_TRUSTED(ch))
		return "  Only monks can chant heroism.\n";
	std::string text =
		fact("Chance", chance_under(GET_CHAR_SKILL(ch, SKILL_HEROISM) + 1, 1, 105)) +
		fact("Duration", game_hours(heroism_duration(ch))) +
		fact("Hitroll", "+" + std::to_string(heroism_hitroll(ch))) +
		fact("Damroll", "+" + std::to_string(heroism_damroll(ch))) +
		fact("Before you can chant it again, even after a failure",
		     seconds(heroism_rest())) +
		fact("Your lag", seconds(heroism_lag()));
	if (GET_SPEC(ch, CLASS_MONK, SPEC_WAYOFDRAGON))
		text += "  It also gives you indomitability, if you lack it.\n";
	if (GET_LEVEL(ch) >= heroism_dazzle_level() && GET_SPEC(ch, CLASS_MONK, SPEC_WAYOFSNAKE))
		text += "  It also makes you dazzle, if you don't already.\n";
	if (GET_LEVEL(ch) >= heroism_haste_level())
		text += "  It also hastes you, if you aren't already.\n";
	if (GET_LEVEL(ch) >= heroism_blur_level())
		text += "  It also blurs you, if you aren't already.\n";
	return text + "  Not under diamond soul.\n" + chant_note();
}

void chant_heroism(P_char ch, char * /*argument*/, int /*cmd*/)
{
	struct affected_type af, af1;
	char buf[100];
	int skl_lvl = 0;
	int duration = heroism_duration(ch);

	if (!GET_CLASS(ch, CLASS_MONK) && !IS_TRUSTED(ch))
	{
		send_to_char("You're no hero - you're a jackass.\r\n", ch);
		return;
	}

	if (!affect_timer(ch, heroism_rest(), SKILL_HEROISM))
	{
		send_to_char("Your mind needs rest...\r\n", ch);
		return;
	}

	if (IS_PC(ch) || IS_PC_PET(ch))
		skl_lvl = GET_CHAR_SKILL(ch, SKILL_HEROISM);
	else
		skl_lvl = GET_LEVEL(ch) * 2;

	if (affected_by_spell(ch, SKILL_HEROISM))
	{
		send_to_char("You are already under the affects of heroism.\r\n", ch);
		return;
	}

	if (affected_by_spell(ch, SKILL_DIAMOND_SOUL))
	{
		send_to_char(
			"You cannot call upon the heroism technique while under the influence of diamond soul.\r\n",
			ch);
		return;
	}

	// 5 percent chance to fail at max pc skill.
	if (!notch_skill(ch, SKILL_HEROISM, 30) && number(1, 105) > skl_lvl)
	{
		send_to_char("Your inner thoughts are in turmoil.\r\n", ch);
		CharWait(ch, heroism_lag());
		return;
	}

	snprintf(buf, 100, "A sense of heroism grows in your heart.\r\n");

	bzero(&af, sizeof(af));
	af.type = SKILL_HEROISM;
	af.flags = AFFTYPE_NODISPEL;
	af.duration = duration;

	af.modifier = heroism_hitroll(ch);
	af.location = APPLY_HITROLL;
	affect_to_char(ch, &af);

	af.modifier = heroism_damroll(ch);
	af.location = APPLY_DAMROLL;
	affect_to_char(ch, &af);

	af.modifier = 0;
	af.location = 0;

	if (GET_SPEC(ch, CLASS_MONK, SPEC_WAYOFDRAGON) &&
	    !affected_by_spell(ch, SPELL_INDOMITABILITY))
	{
		send_to_char(
			"Something wicked just happened didn't it? My god you feel weird. \r\n",
			ch);
		bzero(&af1, sizeof(af1));
		af1.type = SPELL_INDOMITABILITY;
		af1.flags = AFFTYPE_NODISPEL;
		af1.duration = duration;
		affect_to_char(ch, &af1);
	}

	send_to_char(buf, ch);

	if (GET_LEVEL(ch) >= heroism_dazzle_level() && GET_SPEC(ch, CLASS_MONK, SPEC_WAYOFSNAKE) &&
	    !IS_AFFECTED4(ch, AFF4_DAZZLER))
	{
		af.bitvector4 += AFF4_DAZZLER;
		send_to_char("Your body begins to glow with disorienting colors... \r\n", ch);
	}

	if (GET_LEVEL(ch) >= heroism_haste_level() && !IS_AFFECTED(ch, AFF_HASTE))
	{
		af.bitvector += AFF_HASTE;
		send_to_char("Your body begins to speed up!\r\n", ch);
	}

	if (GET_LEVEL(ch) >= heroism_blur_level() && !IS_AFFECTED3(ch, AFF3_BLUR))
	{
		af.bitvector3 += AFF3_BLUR;
		send_to_char("Your body begins to blur!\r\n", ch);
	}

	affect_to_char(ch, &af);
	CharWait(ch, heroism_lag());
}

static int buddha_palm_rest()
{
	return WAIT_SEC * get_property("timer.secs.monkBuddha", 30);
}

static int buddha_palm_failed_lag()
{
	return 2 * PULSE_VIOLENCE;
}

static int buddha_palm_lag()
{
	return PULSE_VIOLENCE;
}

// Targets it can burn; the first always burns once.
static int buddha_palm_targets(P_char ch)
{
	return GET_LEVEL(ch) / 10;
}

static int buddha_palm_damage(const Rolls &rolls, P_char ch)
{
	return rolls.dice(GET_LEVEL(ch) / 2, 8);
}

std::string buddha_palm_facts(P_char ch)
{
	if (!GET_CLASS(ch, CLASS_MONK) && !IS_TRUSTED(ch))
		return "  Only monks can chant buddha palm.\n";
	return fact("Chance", chance_under(GET_CHAR_SKILL(ch, SKILL_BUDDHA_PALM) + 1, 1, 101)) +
	       fact("Holy damage to each target", show({ buddha_palm_damage(lowest_rolls, ch),
							 buddha_palm_damage(highest_rolls, ch) }) +
							  ", one roll for all") +
	       fact("Most targets in the room", std::to_string(MAX(1, buddha_palm_targets(ch)))) +
	       fact("Before you can chant it again, even after a failure",
		    seconds(buddha_palm_rest())) +
	       fact("Your lag", seconds(buddha_palm_lag())) +
	       fact("Your lag if you fail", seconds(buddha_palm_failed_lag())) +
	       "  Not in a safe room. Spell damage modifiers and defenses apply after.\n" +
	       chant_note();
}

void chant_buddha_palm(P_char ch, char * /*argument*/, int /*cmd*/)
{
	P_char vict = NULL, hold = NULL;
	int dam, num_tar;
	int skl_lvl = 0;
	struct damage_messages messages = {
		"$N is wracked by spasms of agony as you reveal Buddha's true greatness!",
		"You are blasted by holy light sent by $n!",
		"$N is burned by brilliant light!",
		"$N dies from revealed trust of Buddha's greatness!",
		"As $n's chant nears it's end, you realize what a jerk you are!",
		"$N dies from $n's chant!"
	};

	if (!GET_CLASS(ch, CLASS_MONK) && !IS_TRUSTED(ch))
	{
		send_to_char("You may not perform the buddha palm chant.\r\n", ch);
		return;
	}

	if (!affect_timer(ch, buddha_palm_rest(), SKILL_BUDDHA_PALM))
	{
		send_to_char("You are not in the proper mood for that right now!\r\n", ch);
		return;
	}

	if (IS_PC(ch))
		skl_lvl = GET_CHAR_SKILL(ch, SKILL_BUDDHA_PALM);
	else
		skl_lvl = MAX(100, GET_LEVEL(ch) * 3);

	if (!notch_skill(ch, SKILL_BUDDHA_PALM, get_property("skill.notch.offensive", 10)) &&
	    number(1, 101) > skl_lvl)
	{
		send_to_char("You forgot the words for the chant.\r\n", ch);
		CharWait(ch, buddha_palm_failed_lag());
		return;
	}
	if (CHAR_IN_SAFE_ROOM(ch))
	{
		send_to_char(
			"You feel ashamed to try to disrupt the tranquility of this place.\r\n",
			ch);
		return;
	}
	if (EVIL_RACE(ch) || IS_EVIL(ch))
	{
		send_to_char(
			"A glowing globe of red light springs from your outstretched palms.\r\n",
			ch);
		act("A glowing glove of red light springs from $n's outstretched palms.", TRUE, ch,
		    0, 0, TO_ROOM);
	}
	else
	{
		send_to_char("A glowing globe of light springs from your outstretched palms.\r\n",
			     ch);
		act("A glowing glove of light springs from $n's outstretched palms.", TRUE, ch, 0,
		    0, TO_ROOM);
	}

	num_tar = buddha_palm_targets(ch);
	dam = buddha_palm_damage(live_rolls, ch);
	for (vict = world[ch->in_room].people; vict; vict = hold)
	{
		hold = vict->next_in_room;
		if (should_area_hit(ch, vict))
		{
			num_tar--;
			if (EVIL_RACE(ch) || IS_EVIL(ch))
			{
				act("You burn $N with your reddish light.", FALSE, ch, 0, vict,
				    TO_CHAR);
				act("$n burns $N with $s reddish light.", FALSE, ch, 0, vict,
				    TO_NOTVICT);
				act("$n burns you with $s reddish light.", FALSE, ch, 0, vict,
				    TO_VICT);
			}
			else
			{
				act("You burn $N with your heavenly starlight.", FALSE, ch, 0, vict,
				    TO_CHAR);
				act("$n burns $N with $s heavenly starlight.", FALSE, ch, 0, vict,
				    TO_NOTVICT);
				act("$n burns you with $s heavenly starlight.", FALSE, ch, 0, vict,
				    TO_VICT);
			}

			spell_damage(ch, vict, dam, SPLDAM_HOLY, SPLDAM_NOSHRUG | SPLDAM_NODEFLECT,
				     &messages);
			if (num_tar <= 0)
				break;
		}
	}
	CharWait(ch, buddha_palm_lag());
}

static int quivering_palm_rest()
{
	return WAIT_SEC * get_property("timer.secs.monkQuivering", 30);
}

static int quivering_palm_failed_lag()
{
	return 2 * PULSE_VIOLENCE;
}

static int quivering_palm_lag()
{
	return PULSE_VIOLENCE;
}

static int quivering_palm_damage(P_char ch)
{
	return GET_C_DEX(ch) * 2 + GET_CHAR_SKILL(ch, SKILL_QUIVERING_PALM);
}

// The chance threshold, rolled 0-100, of anatomy raising it.
static int quivering_palm_anatomy_threshold(P_char ch)
{
	return 5 + GET_CHAR_SKILL(ch, SKILL_ANATOMY) / 10;
}

static int quivering_palm_anatomy_damage(int dam)
{
	return (int)(dam * 1.5);
}

std::string quivering_palm_facts(P_char ch)
{
	if (!GET_CLASS(ch, CLASS_MONK) && !IS_TRUSTED(ch))
		return "  Only monks can chant quivering palm.\n";
	std::string text =
		fact("Chance", chance_under(GET_CHAR_SKILL(ch, SKILL_QUIVERING_PALM) + 1, 1, 100)) +
		fact("Damage",
		     std::to_string(quivering_palm_damage(ch)) + ", before the target's defenses");
	if (GET_CHAR_SKILL(ch, SKILL_ANATOMY))
		text += fact("With anatomy, chance of more damage",
			     chance_under(quivering_palm_anatomy_threshold(ch), 0, 100) + ", for " +
				     std::to_string(quivering_palm_anatomy_damage(
					     quivering_palm_damage(ch))));
	return text + fact("Before you can chant it again", seconds(quivering_palm_rest())) +
	       fact("Your lag", seconds(quivering_palm_lag())) +
	       fact("Your lag if you fail", seconds(quivering_palm_failed_lag())) +
	       "  Not in a safe room, or past the next in line in a single-file room.\n" +
	       chant_note();
}

void chant_quivering_palm(P_char ch, char *argument, int /*cmd*/)
{
	P_char vict = NULL;
	char name[256];
	int dam;
	int skl_lvl = 0;
	struct damage_messages messages = {
		"$N is wracked by pain after you briefly touch your vibrating palm to him!",
		"$n extends his vibrating hand, and touches you - sending spasms of agony through you.",
		"$n touches $N with his vibrating palm, sending $M into spasms of agony.",
		"$N is killed instantly by the dreaded quivering palm!",
		"As $n touches you, you feel your bones and organs shatter inside.",
		"$N dies as $n touches $M."
	};

	if (!GET_CLASS(ch, CLASS_MONK) && !IS_TRUSTED(ch))
	{
		send_to_char("Too bad you're not a monk.\r\n", ch);
		return;
	}

	if (IS_PC(ch))
		skl_lvl = GET_CHAR_SKILL(ch, SKILL_QUIVERING_PALM);
	else
		skl_lvl =
			GET_LEVEL(ch) * 2; // Let's try this at a value that makes a bit more sense.
	// Level 1 monk mobs should not have 100 skill, duhr.  - Jexni 09/20/08

	if (argument)
		one_argument(argument, name);
	if (!argument || !*argument || !(vict = get_char_room_vis(ch, name)))
	{
		if (GET_OPPONENT(ch) && (GET_STAT(GET_OPPONENT(ch)) != STAT_DEAD))
			vict = GET_OPPONENT(ch);
	}
	if (!vict || (GET_STAT(vict) == STAT_DEAD))
	{
		send_to_char("Chant on whom?\r\n", ch);
		return;
	}
	if (vict == ch)
	{
		send_to_char("You hum to yourself.\r\n", ch);
		return;
	}
	if (!affect_timer(ch, quivering_palm_rest(), SKILL_QUIVERING_PALM))
	{
		send_to_char("You are not in the proper mood for that right now!\r\n", ch);
		return;
	}
	if (CHAR_IN_SAFE_ROOM(ch))
	{
		send_to_char(
			"You feel ashamed to try to disrupt the tranquility of this place.\r\n",
			ch);
		return;
	}
	if ((IS_ROOM(ch->in_room, ROOM_SINGLE_FILE)) && (!AdjacentInRoom(ch, vict)))
	{
		send_to_char("Your target is too far for your palm to reach!\n", ch);
		return;
	}
	if (!notch_skill(ch, SKILL_QUIVERING_PALM, get_property("skill.notch.offensive", 10)) &&
	    number(1, 100) > skl_lvl)
	{
		send_to_char("You forgot the words for the chant.\r\n", ch);
		CharWait(ch, quivering_palm_failed_lag());
		return;
	}
	dam = quivering_palm_damage(ch);

	if (GET_CHAR_SKILL(ch, SKILL_ANATOMY) &&
	    quivering_palm_anatomy_threshold(ch) > number(0, 100))
	{
		dam = quivering_palm_anatomy_damage(dam);
	}

	/*  can't for the life of me figure out why we need 2 messages for this skill...
	act
	  ("You suddenly grab hold of $N's forehead and sends $M quivering with your chant.",
	   FALSE, ch, 0, vict, TO_CHAR);
	act
	  ("$n suddenly grabs hold of $N's forehead and sends $M quivering with $s chant.",
	   FALSE, ch, 0, vict, TO_NOTVICT);
	act
	  ("$n suddenly grabs hold of your forehead and sends you quivering with $s chant.",
	   FALSE, ch, 0, vict, TO_VICT); */
	melee_damage(ch, vict, dam, PHSDAM_TOUCH, &messages);
	if (!char_in_list(ch))
		return;
	CharWait(ch, quivering_palm_lag());
}

static int jin_touch_rest()
{
	return WAIT_SEC * get_property("timer.secs.monkJintouch", 30);
}

static int jin_touch_failed_lag()
{
	return PULSE_VIOLENCE;
}

static int jin_touch_lag()
{
	return 2 * PULSE_VIOLENCE;
}

static int jin_touch_damage(const Rolls &rolls, P_char ch)
{
	return (int)(rolls.dice(GET_C_DEX(ch), 3) + rolls.dice(GET_C_AGI(ch), 3) +
		     rolls.dice(GET_C_WIS(ch), 3)) /
	       4;
}

// Its damage after your rating.
static int jin_touch_rated_damage(int dam, int skl_lvl)
{
	if (skl_lvl <= 80)
		dam = (int)(0.4 * dam);
	else if (skl_lvl <= 90)
		dam = (int)(0.6 * dam);

	dam /= 2;
	return dam;
}

// The rating that can weaken the target's armor, for how long, and by how much.
static int jin_touch_weaken_rating()
{
	return 100;
}

static int jin_touch_weaken_duration()
{
	return 1;
}

static int jin_touch_weaken(const Rolls &rolls, P_char ch)
{
	return GET_LEVEL(ch) * rolls.number(2, 3);
}

std::string jin_touch_facts(P_char ch)
{
	if (!GET_CLASS(ch, CLASS_MONK))
		return "  Only monks can chant jin touch.\n";
	const int rating = GET_CHAR_SKILL(ch, SKILL_JIN_TOUCH);
	if (rating < 1)
		return "  You need this skill to chant jin touch.\n";
	std::string text =
		fact("Chance", chance_under(rating + 1, 1, 50)) +
		fact("Damage",
		     show({ jin_touch_rated_damage(jin_touch_damage(lowest_rolls, ch), rating),
			    jin_touch_rated_damage(jin_touch_damage(highest_rolls, ch), rating) })) +
		"    (past the target's armor and skin spells)\n" +
		fact("Before you can chant it again", seconds(jin_touch_rest())) +
		fact("Your lag", seconds(jin_touch_lag())) +
		fact("Your lag if you fail", seconds(jin_touch_failed_lag()));
	if (rating >= jin_touch_weaken_rating())
		text += fact("Target's armor class, on a further roll",
			     "+" + show({ jin_touch_weaken(lowest_rolls, ch),
					  jin_touch_weaken(highest_rolls, ch) })) +
			fact("  For", game_hours(jin_touch_weaken_duration())) +
			"    (not on soulless targets, elites or greater races)\n";
	return text + "  Not in a safe room, or past the next in line in a single-file room.\n" +
	       chant_note();
}

void chant_jin_touch(P_char ch, char *argument, int /*cmd*/)
{
	P_char vict = NULL;
	char name[256];
	int dam, percent, skl_lvl;

	if (!IS_ALIVE(ch) || IS_IMMOBILE(ch))
	{
		return;
	}

	if (!GET_CLASS(ch, CLASS_MONK))
	{
		send_to_char("Too bad you're not a monk.\r\n", ch);
		return;
	}
	else
	{
		if (IS_PC(ch) || IS_PC_PET(ch))
			skl_lvl = GET_CHAR_SKILL(ch, SKILL_JIN_TOUCH);
		else
			skl_lvl = MAX(100, GET_LEVEL(ch) * 3);
	}

	// debug("(%s) jin skill is (%d).", GET_NAME(ch), skl_lvl);

	if (IS_FIGHTING(ch))
		vict = GET_OPPONENT(ch);
	else if (argument)
	{
		one_argument(argument, name);
		vict = get_char_room_vis(ch, name);
	}

	if (!vict || !IS_ALIVE(vict))
	{
		send_to_char("&+GChant on whom?\r\n", ch);
		return;
	}

	if (!IS_TRUSTED(ch) && affected_by_skill(ch, SKILL_JIN_TOUCH))
	{
		send_to_char("&+GYour inner force has not realigned...\r\n", ch);
		return;
	}

	if (number(1, 50) > skl_lvl)
	{
		send_to_char("You forgot the words for the chant.\r\n", ch);

		CharWait(ch, jin_touch_failed_lag());

		if (IS_NPC(vict) && CAN_SEE(vict, ch) && number(0, 1))
		{
			remember(vict, ch);
			if (!IS_FIGHTING(vict))
			{
				MobStartFight(vict, ch);
			}
		}

		return;
	}

	affect_timer(ch, jin_touch_rest(), SKILL_JIN_TOUCH);
	CharWait(ch, jin_touch_lag());

	if (vict == ch)
	{
		send_to_char("&+GYou hum to yourself.\r\n", ch);
		return;
	}

	if (CHAR_IN_SAFE_ROOM(ch))
	{
		send_to_char(
			"&+GYou feel ashamed to try to disrupt the tranquility of this place.\r\n",
			ch);
		return;
	}

	if ((IS_ROOM(ch->in_room, ROOM_SINGLE_FILE)) && (!AdjacentInRoom(ch, vict)))
	{
		send_to_char("&+GYour target is too far for your touch to reach!\n", ch);
		return;
	}

	if (IS_NPC(vict) && CAN_SEE(vict, ch) && number(0, 1))
	{
		remember(vict, ch);
		if (!IS_FIGHTING(vict))
			MobStartFight(vict, ch);
	}

	dam = jin_touch_damage(live_rolls, ch);

	dam = jin_touch_rated_damage(dam, skl_lvl);

	act("&+CYou harness your full Jin, and deliver a powerful strike to&n $N!&n", FALSE, ch, 0,
	    vict, TO_CHAR);
	act("$n&+C chants a mantra, then touches&n $N&+C who reels in pain!&n", FALSE, ch, 0, vict,
	    TO_NOTVICT);
	act("$n&+C's chants a mantra as $e touches you - pain courses throughout your body!&n",
	    FALSE, ch, 0, vict, TO_VICT);

	debug("chant_jin_touch: (%s) hitting (%s) for (%d) dam.", GET_NAME(ch), GET_NAME(vict),
	      dam);
	if (melee_damage(ch, vict, dam, PHSDAM_NOREDUCE | PHSDAM_NOPOSITION | PHSDAM_TOUCH, 0) !=
	    DAM_NONEDEAD)
		return;

	if (!char_in_list(ch))
		return;

	percent = (BOUNDED(0, (GET_LEVEL(ch) - GET_LEVEL(vict)), 30)) + number(-5, 5);

	if (GET_CHAR_SKILL(ch, SKILL_ANATOMY))
		percent += (int)(GET_CHAR_SKILL(ch, SKILL_ANATOMY) / 10);

	if (!affected_by_spell(vict, SKILL_JIN_TOUCH) && (percent > number(0, 19)) &&
	    skl_lvl >= jin_touch_weaken_rating() && !IS_SOULLESS(vict) && !IS_GREATER_RACE(vict) &&
	    !IS_ELITE(vict))
	{
		act("&+cYou harness the full, harmonius energy of your Jin, directing it at&n $N!",
		    FALSE, ch, 0, vict, TO_CHAR);
		act("$n&+c attacks your very soul, and you feel less capable of defending yourself!&n",
		    FALSE, ch, 0, vict, TO_VICT);
		act("$n's &+ctouch seems to have particularly weakened&n $N!&n", FALSE, ch, 0, vict,
		    TO_NOTVICT);
		struct affected_type af;
		memset(&af, 0, sizeof(af));
		af.type = SKILL_JIN_TOUCH;
		af.duration = jin_touch_weaken_duration();

		af.modifier = jin_touch_weaken(live_rolls, ch);
		af.location = APPLY_AC;
		affect_to_char(vict, &af);
	}
}

static int ki_strike_rest()
{
	return WAIT_SEC * get_property("timer.secs.monkKistrike", 45);
}

static int ki_strike_failed_lag()
{
	return 2 * PULSE_VIOLENCE;
}

static int ki_strike_fall_lag()
{
	return (int)(PULSE_VIOLENCE);
}

static int ki_strike_lag()
{
	return (int)(2.5 * PULSE_VIOLENCE);
}

static int ki_strike_target_lag()
{
	return (int)(1.5 * PULSE_VIOLENCE);
}

// Added to your level above the target's; the sum must beat a roll of 1-30 to slow it.
static int ki_strike_slow_roll(const Rolls &rolls)
{
	return rolls.number(-5, 20);
}

static int ki_strike_anatomy_bonus(P_char ch)
{
	return (int)(GET_CHAR_SKILL(ch, SKILL_ANATOMY) / 10);
}

static int ki_strike_slow_duration()
{
	return 1;
}

std::string ki_strike_facts(P_char ch)
{
	if (!GET_CLASS(ch, CLASS_MONK))
		return "  Only monks can chant ki strike.\n";
	const int rating = GET_CHAR_SKILL(ch, SKILL_KI_STRIKE);
	if (rating < 1)
		return "  You need this skill to chant ki strike.\n";
	return fact("Chance", chance_under(rating + 1, 1, 100)) +
	       fact("Your lag", seconds(ki_strike_lag())) +
	       fact("Target's lag", seconds(ki_strike_target_lag())) +
	       fact("Your lag if you fail", seconds(ki_strike_failed_lag())) +
	       fact("Your lag if the target isn't standing",
		    seconds(ki_strike_fall_lag()) + ", and you fall over") +
	       fact("Before you can chant it again, even after a failure",
		    IS_TRUSTED(ch) ? "no wait, as an immortal" : seconds(ki_strike_rest())) +
	       fact("A further roll slows the target for", game_hours(ki_strike_slow_duration())) +
	       "    (your level above its, capped at 100, " +
	       show_signed(
		       { ki_strike_slow_roll(lowest_rolls), ki_strike_slow_roll(highest_rolls) }) +
	       " more,\n    and " + std::to_string(ki_strike_anatomy_bonus(ch)) +
	       " from anatomy, against 1-30)\n"
	       "    (not on elites, greater races or a target it already slowed)\n"
	       "  Not in a safe room, or past the next in line in a single-file room.\n" +
	       chant_note();
}

void chant_ki_strike(P_char ch, char *argument, int /*cmd*/)
{
	P_char vict = NULL, master;
	char name[256];
	int percent;
	int skl_lvl = 0;
	P_nevent combo_event;

	if (!GET_CLASS(ch, CLASS_MONK))
	{
		send_to_char("Too bad you're not a monk, eh?\r\n", ch);
		return;
	}

	if (IS_PC(ch))
		skl_lvl = GET_CHAR_SKILL(ch, SKILL_KI_STRIKE);
	else
		skl_lvl = MIN(100, GET_LEVEL(ch) * 2);

	if (argument)
		one_argument(argument, name);
	if (!argument || !*argument || !(vict = get_char_room_vis(ch, name)))
	{
		if (GET_OPPONENT(ch) && (GET_STAT(GET_OPPONENT(ch)) != STAT_DEAD))
			vict = GET_OPPONENT(ch);
	}
	if (!vict || (GET_STAT(vict) == STAT_DEAD))
	{
		send_to_char("Chant on whom?\r\n", ch);
		return;
	}
	if (vict == ch)
	{
		send_to_char("You hum to yourself.\r\n", ch);
		return;
	}
	if (!affect_timer(ch, ki_strike_rest(), SKILL_KI_STRIKE))
	{
		send_to_char("Yer not in proper mood for that right now!\r\n", ch);
		return;
	}
	if (CHAR_IN_SAFE_ROOM(ch))
	{
		send_to_char(
			"You feel ashamed to try to disrupt the tranquility of this place.\r\n",
			ch);
		return;
	}
	if ((IS_ROOM(ch->in_room, ROOM_SINGLE_FILE)) && (!AdjacentInRoom(ch, vict)))
	{
		send_to_char("Your target is too far for your touch to reach!\n", ch);
		return;
	}
	if (number(1, 100) > skl_lvl)
	{
		appear(ch);
		send_to_char("You forgot the words for the chant.\r\n", ch);
		CharWait(ch, ki_strike_failed_lag());

		if (IS_NPC(vict) && CAN_SEE(vict, ch) && number(0, 1))
		{
			remember(vict, ch);
			if (!IS_FIGHTING(vict))
				MobStartFight(vict, ch);
		}

		return;
	}

	// A surprise for those who want to use epic skills via charmies.
	if (IS_NPC(ch) && IS_PC(vict) && (master = get_linked_char(ch, LNK_PET)) != NULL)
	{
		if (IS_PC(master))
		{
			act("&+YThe chi-power of $n&+r's &+Wki strike&+Y breaks $N&+Y's control.&n",
			    FALSE, ch, 0, master, TO_NOTVICT);
			act("&+YThe chi-power of $n&+r's &+Wki strike&+Y breaks your control.&n",
			    FALSE, ch, 0, master, TO_VICT);
			act("&+YThe power of your &+Wki strike&+Y frees you from $N&+Y's control!",
			    FALSE, ch, 0, master, TO_CHAR);
			clear_links(ch, LNK_PET);
			vict = master;
		}
	}

	// appear is called in set_fighting.
	if (!IS_FIGHTING(ch))
		set_fighting(ch, vict);
	else
		appear(ch);

	// If ch dies too fast.
	if (!char_in_list(ch))
		return;

	// If in middle of combination, fail the combo.
	if ((combo_event = get_scheduled(ch, event_combination)) != NULL)
	{
		act("&+LYou abandon your combination to make your move...&n", FALSE, ch, 0, vict,
		    TO_CHAR);
		nevent_cancel(nevent_handle_from_event(combo_event));
		affect_from_char(ch, SKILL_COMBINATION);
	}

	// If target isn't standing, we fail.
	if (GET_POS(vict) != POS_STANDING)
	{
		act("&+BYou lean in to strike at $N&+B, but miss and fall over!&n", FALSE, ch, 0,
		    vict, TO_CHAR);
		act("&+B$n&+B lunges at $N&+B, and falls over!&n", FALSE, ch, 0, vict, TO_NOTVICT);
		act("&+B$n&+B lunges at you, misses his strike and falls over!&n", FALSE, ch, 0,
		    vict, TO_VICT);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		CharWait(ch, ki_strike_fall_lag());
		return;
	}

	act("&+BYou swiftly strike at $N&+B, delivering a quick, decisive blow to a pressure point!&n",
	    FALSE, ch, 0, vict, TO_CHAR);
	act("&+B$n&+B lunges at $N&+B striking $S chest, leaving $M slightly dazed!&n", FALSE, ch,
	    0, vict, TO_NOTVICT);
	act("&+B$n&+B lunges at you, and before you can react, you feel somewhat dazed!&n", FALSE,
	    ch, 0, vict, TO_VICT);

	CharWait(ch, ki_strike_lag());
	CharWait(vict, ki_strike_target_lag());

	percent = (BOUNDED(0, (GET_LEVEL(ch) - GET_LEVEL(vict)), 100));
	percent += ki_strike_slow_roll(live_rolls);

	if (GET_CHAR_SKILL(ch, SKILL_ANATOMY))
		percent += ki_strike_anatomy_bonus(ch);

	if (!affected_by_spell(vict, SKILL_KI_STRIKE) && (percent > number(1, 30)) &&
	    !IS_GREATER_RACE(vict) && !IS_ELITE(vict))
	{
		act("&+bYour attack on $N&+b's pressure point is particularly devastating!&n",
		    FALSE, ch, 0, vict, TO_CHAR);
		act("&+b$n&+b's attack strikes hard, and you feel yourself slloooowwwww down!&n",
		    FALSE, ch, 0, vict, TO_VICT);
		act("&+b$N&+b begins to move MUCH more sluggishly!&n", FALSE, ch, 0, vict,
		    TO_NOTVICT);
		struct affected_type af;
		memset(&af, 0, sizeof(af));
		af.type = SKILL_KI_STRIKE;
		af.duration = ki_strike_slow_duration();
		af.bitvector2 = AFF2_SLOW;
		affect_to_char(vict, &af);
	}
}

static int regenerate_rest()
{
	return WAIT_SEC * get_property("timer.secs.monkRegenerate", 120);
}

static int regenerate_failed_lag()
{
	return 2 * PULSE_VIOLENCE;
}

static int regenerate_lag()
{
	return PULSE_VIOLENCE;
}

static int regenerate_duration(P_char ch)
{
	return GET_LEVEL(ch) / 7;
}

static int regenerate_hit_regen(P_char ch)
{
	return GET_CHAR_SKILL(ch, SKILL_REGENERATE) * GET_LEVEL(ch);
}

std::string regenerate_facts(P_char ch)
{
	if (!GET_CHAR_SKILL(ch, SKILL_REGENERATE))
		return "  You need this skill to chant regenerate.\n";
	return fact("Chance", chance_under(GET_CHAR_SKILL(ch, SKILL_REGENERATE) + 1, 1, 100)) +
	       fact("Duration", game_hours(regenerate_duration(ch))) +
	       fact("Hit point regeneration", "+" + std::to_string(regenerate_hit_regen(ch))) +
	       fact("Before you can chant it again, even after a failure",
		    seconds(regenerate_rest())) +
	       fact("Your lag", seconds(regenerate_lag())) +
	       fact("Your lag if you fail", seconds(regenerate_failed_lag())) +
	       "  Not while fighting, regenerating or under accelerated healing.\n" + chant_note();
}

void chant_regenerate(P_char ch, char * /*argument*/, int /*cmd*/)
{
	struct affected_type af;

	if (!GET_CHAR_SKILL(ch, SKILL_REGENERATE))
	{
		send_to_char(
			"Your control over the body is not sufficient to attempt such sophisticated technique.\r\n",
			ch);
		return;
	}

	if (GET_OPPONENT(ch))
	{
		send_to_char("You can't concentrate enough!\r\n", ch);
		return;
	}

	if (!affect_timer(ch, regenerate_rest(), SKILL_REGENERATE))
	{
		send_to_char("Yer not in proper mood for that right now!\r\n", ch);
		return;
	}

	if (affected_by_spell(ch, SKILL_REGENERATE) || affected_by_spell(ch, SPELL_REGENERATION) ||
	    affected_by_spell(ch, SPELL_ACCEL_HEALING))
	{
		send_to_char("You are already regenerating.\r\n", ch);
		return;
	}

	if (!notch_skill(ch, SKILL_REGENERATE, 30) &&
	    number(1, 100) > GET_CHAR_SKILL(ch, SKILL_REGENERATE))
	{
		send_to_char("You forgot the words for the chant.\r\n", ch);
		CharWait(ch, regenerate_failed_lag());
		return;
	}

	send_to_char("You feel your body healing faster.\r\n", ch);
	bzero(&af, sizeof(af));
	af.type = SKILL_REGENERATE;
	af.duration = regenerate_duration(ch);
	af.location = APPLY_HIT_REG;
	af.modifier = regenerate_hit_regen(ch);
	affect_to_char(ch, &af);

	notch_skill(ch, SKILL_REGENERATE, 35);
	CharWait(ch, regenerate_lag());
}

static int tiger_palm_rest()
{
	return WAIT_SEC * get_property("timer.secs.monkTigerPalm", 30);
}

// The chance threshold, rolled 1-101.
static int tiger_palm_threshold(P_char ch)
{
	return (IS_PC(ch) ? (1 + GET_CHAR_SKILL(ch, SKILL_TIGER_PALM)) :
			    (MIN(100, GET_LEVEL(ch) * 2)));
}

static int tiger_palm_duration(P_char ch)
{
	return WAIT_SEC * (BOUNDED(4, (GET_CHAR_SKILL(ch, SKILL_TIGER_PALM) / 2), 55));
}

std::string tiger_palm_facts(P_char ch)
{
	extern float dam_factor[LAST_DF + 1];
	if (!GET_CHAR_SKILL(ch, SKILL_TIGER_PALM) && !IS_TRUSTED(ch))
		return "  You need this skill to chant tiger palm.\n";
	return fact("Chance", chance_under(tiger_palm_threshold(ch) + 1, 1, 101)) +
	       fact("Duration", seconds(tiger_palm_duration(ch))) +
	       fact("Psionic spell damage you take", share_percent(dam_factor[DF_TIGERPALM]) +
							     " of normal, added to other factors") +
	       fact("Before you can chant it again, even after a failure",
		    seconds(tiger_palm_rest())) +
	       chant_note();
}

void chant_tiger_palm(P_char ch, char * /*arg*/, int /*cmd*/)
{
	if (!GET_CHAR_SKILL(ch, SKILL_TIGER_PALM) && !IS_TRUSTED(ch))
	{
		send_to_char("You wouldnt know where to begin.\r\n", ch);
		return;
	}

	if (!affect_timer(ch, tiger_palm_rest(), SKILL_TIGER_PALM))
	{
		send_to_char("Yer not in proper mood for that right now!\r\n", ch);
		return;
	}

	if (!notch_skill(ch, SKILL_TIGER_PALM, get_property("skill.notch.chants", 20)) &&
	    (number(1, 101) > tiger_palm_threshold(ch)))
	{
		send_to_char("You fail to embrace the tiger palm concentration&n!\r\n", ch);
		return;
	}

	set_short_affected_by(ch, SKILL_TIGER_PALM, tiger_palm_duration(ch));
	send_to_char("&+rYou invoke the power of the tiger palm concentration.\r\n", ch);
	act("&+r$n&+r's concentration grows as $e summons $s inner chi-powers.&n", FALSE, ch, 0, 0,
	    TO_ROOM);
}

static int fist_of_dragon_rest()
{
	return WAIT_SEC * get_property("timer.secs.monkFistOfDragon", 30);
}

static int fist_of_dragon_duration(P_char ch, int skl_lvl)
{
	return WAIT_SEC * (MAX(4, (GET_LEVEL(ch) * skl_lvl / 100)));
}

extern int fist_of_dragon_roll(const Rolls &rolls);

std::string fist_of_dragon_facts(P_char ch)
{
	const int rating = IS_TRUSTED(ch) ? 100 : GET_CHAR_SKILL(ch, SKILL_FIST_OF_DRAGON);
	if (!rating)
		return "  You need this skill to chant fist of dragon.\n";
	return fact("Chance", chance_under(rating + 1, 1, 101)) +
	       fact("Duration", seconds(fist_of_dragon_duration(ch, rating))) +
	       fact("Chance a melee hit ignores armor that helps the target",
		    one_in(fist_of_dragon_roll)) +
	       "    (and goes through stoneskin and the like)\n" +
	       fact("Before you can chant it again, even after a failure",
		    seconds(fist_of_dragon_rest())) +
	       chant_note();
}

void chant_fist_of_dragon(P_char ch, char * /*arg*/, int /*cmd*/)
{
	int skl_lvl;

	skl_lvl = IS_TRUSTED(ch) ? 100 : GET_CHAR_SKILL(ch, SKILL_FIST_OF_DRAGON);

	if (!skl_lvl)
	{
		send_to_char("You wouldnt know where to begin.\r\n", ch);
		return;
	}

	if (!affect_timer(ch, fist_of_dragon_rest(), SKILL_FIST_OF_DRAGON))
	{
		send_to_char("Yer not in proper mood for that right now!\r\n", ch);
		return;
	}

	if (!notch_skill(ch, SKILL_FIST_OF_DRAGON, get_property("skill.notch.chants", 20)) &&
	    (number(1, 101) > skl_lvl))
	{
		send_to_char("You fail to summon the power of the &+RRed Dragon&n!\r\n", ch);
		return;
	}

	set_short_affected_by(ch, SKILL_FIST_OF_DRAGON, fist_of_dragon_duration(ch, skl_lvl));
	send_to_char("&+rThe strength of the &+Rred dragon &+rflows strong in your veins.\r\n", ch);
	act("&+r$n&+r's hands harden as $e summons $s inner chi-powers.&n", FALSE, ch, 0, 0,
	    TO_ROOM);
}

static int chant_roll_top(P_char ch)
{
	return 85 + GET_LEVEL(ch) / 2;
}

static int chant_lag()
{
	return PULSE_SPELLCAST;
}

std::string chant_facts(P_char ch)
{
	if (!GET_CLASS(ch, CLASS_MONK) && !IS_TRUSTED(ch))
		return "  Only monks can chant.\n";
	const int rating = IS_TRUSTED(ch) ? 100 : GET_CHAR_SKILL(ch, SKILL_CHANT);
	if (rating < 1)
		return "  You have not learned to chant.\n";
	return fact("Chance", chance_under(rating + GET_LEVEL(ch) + 1, 1, chant_roll_top(ch))) +
	       fact("Your lag, even if you fail", seconds(chant_lag())) +
	       "  Each chant adds its own roll and lag after this one.\n";
}

void do_chant(P_char ch, char *argument, int cmd)
{
	char buf[512];
	int chant_index;

	const char *chant_skills[] = { "quivering palm", "buddha palm",	 "heroism",
				       "calm",		 "regenerate",	 "jin touch",
				       "fist of dragon", "chi purge",	 "ki strike",
				       "tiger palm",	 "diamond soul", "\n" };

	int skl_lvl = 0;

	if (!GET_CLASS(ch, CLASS_MONK) && !IS_TRUSTED(ch))
	{
		send_to_char("Learn some Yoga..  Then you can chant.\r\n", ch);
		return;
	}

	if (IS_PC(ch))
		skl_lvl = IS_TRUSTED(ch) ? 100 : GET_CHAR_SKILL(ch, SKILL_CHANT);
	else
		skl_lvl = MAX(100, GET_LEVEL(ch) * 3);

	if (!argument || !*argument)
	{
		snprintf(buf, 512, "You know the following chants:\r\n");
		checked_snprintf(buf, 512, "%s============================\r\n", buf);
		if (IS_TRUSTED(ch) || GET_CHAR_SKILL(ch, SKILL_QUIVERING_PALM) > 0)
			checked_snprintf(buf, 512, "%sQuivering Palm\r\n", buf);
		if (IS_TRUSTED(ch) || GET_CHAR_SKILL(ch, SKILL_BUDDHA_PALM) > 0)
			checked_snprintf(buf, 512, "%sBuddha palm\r\n", buf);
		if (IS_TRUSTED(ch) || GET_CHAR_SKILL(ch, SKILL_HEROISM) > 0)
			checked_snprintf(buf, 512, "%sHeroism\r\n", buf);
		if (IS_TRUSTED(ch) || GET_CHAR_SKILL(ch, SKILL_CHI_PURGE) > 0)
			checked_snprintf(buf, 512, "%sChi Purge\r\n", buf);
		if (IS_TRUSTED(ch) || GET_CHAR_SKILL(ch, SKILL_CALM) > 0)
			checked_snprintf(buf, 512, "%sCalm\r\n", buf);
		if (IS_TRUSTED(ch) || GET_CHAR_SKILL(ch, SKILL_REGENERATE) > 0)
			checked_snprintf(buf, 512, "%sRegenerate\r\n", buf);
		if (IS_TRUSTED(ch) || GET_CHAR_SKILL(ch, SKILL_JIN_TOUCH) > 0)
			checked_snprintf(buf, 512, "%sJin Touch\r\n", buf);
		if (IS_TRUSTED(ch) || GET_CHAR_SKILL(ch, SKILL_FIST_OF_DRAGON) > 0)
			checked_snprintf(buf, 512, "%sFist of dragon\r\n", buf);
		if (IS_TRUSTED(ch) || GET_CHAR_SKILL(ch, SKILL_KI_STRIKE) > 0)
			checked_snprintf(buf, 512, "%sKi Strike\r\n", buf);
		if (IS_TRUSTED(ch) || GET_CHAR_SKILL(ch, SKILL_TIGER_PALM) > 0)
			checked_snprintf(buf, 512, "%sTiger Palm\r\n", buf);
		if (IS_TRUSTED(ch) || GET_CHAR_SKILL(ch, SKILL_DIAMOND_SOUL) > 0)
			checked_snprintf(buf, 512, "%sDiamond Soul\r\n", buf);

		send_to_char(buf, ch);
		return;
	}
	argument = one_argument(argument, buf);

	chant_index = search_block(buf, chant_skills, FALSE);

	if ((chant_index == -1) || !skl_lvl)
	{
		send_to_char("You hum to yourself.\r\n", ch);
		return;
	}
	CharWait(ch, chant_lag());
	/*
	   let them succeeed all the time if practed well
	 */
	if (number(1, chant_roll_top(ch)) > (skl_lvl + GET_LEVEL(ch)))
	{
		send_to_char("Your throat suddenly becomes dry.\r\n", ch);
		act("$n tries to say something, but $s voice is garbled.", FALSE, ch, 0, 0,
		    TO_ROOM);

		notch_skill(ch, SKILL_CHANT, 5);
		return;
	}
	notch_skill(ch, SKILL_CHANT, get_property("skill.notch.chants", 10));
	act("You start to chant in a deep voice.", FALSE, ch, 0, 0, TO_CHAR);
	act("$n starts to chant in a deep voice.", TRUE, ch, 0, 0, TO_ROOM);
	switch (chant_index)
	{
	case 0:
		chant_quivering_palm(ch, argument, cmd);
		break;
	case 1:
		chant_buddha_palm(ch, argument, cmd);
		break;
	case 2:
		chant_heroism(ch, argument, cmd);
		break;
	case 3:
		chant_calm(ch, argument, cmd);
		break;
	case 4:
		chant_regenerate(ch, argument, cmd);
		break;
	case 5:
		chant_jin_touch(ch, argument, cmd);
		break;
	case 6:
		chant_fist_of_dragon(ch, argument, cmd);
		break;
	case 7:
		chant_chi_purge(GET_LEVEL(ch), ch, NULL, 0, ch, NULL);
		break;
	case 8:
		chant_ki_strike(ch, argument, cmd);
		break;
	case 9:
		chant_tiger_palm(ch, argument, cmd);
		break;
	case 10:
		chant_diamond_soul(ch, argument, cmd);
		break;
	default:
		send_to_char("Error in chant, please report.\r\n", ch);
		break;
	}
}

/* Returns a % modifier based on condition of the victim. To use in offensive skills */

int GetConditionModifier(P_char victim)
{
	if (!victim || !IS_ALIVE(victim))
		return 0;

	if (GET_STAT(victim) == STAT_DYING || GET_STAT(victim) == STAT_INCAP)
		return 90;

	if (IS_AFFECTED2(victim, AFF2_MINOR_PARALYSIS) ||
	    IS_AFFECTED2(victim, AFF2_MAJOR_PARALYSIS))
		return 75;

	if (GET_STAT(victim) == STAT_SLEEPING || IS_AFFECTED(victim, AFF_KNOCKED_OUT))
		return 50;

	if (IS_AFFECTED2(victim, AFF2_STUNNED))
		return 30;

	if (IS_AFFECTED(victim, AFF_BOUND))
		return 20;

	if (get_linked_char(victim, LNK_RIDING))
	{
		if (!GET_CHAR_SKILL(victim,
				    SKILL_MOUNTED_COMBAT) /*&& !is_natural_mount(victim, mount)*/)
			return 15;
	}

	if (affected_by_spell(victim, SONG_PEACE))
		return 10;

	return 0;
}

// The target may be this many sizes from yours.
static int dragon_punch_size_gap()
{
	return 1;
}

static int dragon_punch_roll(const Rolls &rolls)
{
	return rolls.dice(60, 8);
}

static int dragon_punch_damage(int dam, int skl_lvl)
{
	return dam * MAX(30, skl_lvl) / 100;
}

static int dragon_punch_lag()
{
	return 2 * PULSE_VIOLENCE;
}

std::string dragon_punch_facts(P_char ch)
{
	const int rating = GET_CHAR_SKILL(ch, SKILL_DRAGON_PUNCH);
	if (!rating)
		return "  You have not learned dragon punch.\n";
	const int skl_lvl = BOUNDED(0, rating, 100);
	return fact("Damage",
		    show({ dragon_punch_damage(dragon_punch_roll(lowest_rolls), skl_lvl),
			   dragon_punch_damage(dragon_punch_roll(highest_rolls), skl_lvl) }) +
			    " at your rating") +
	       "    (a helpless target, such as a stunned or sleeping one, counts it higher)\n"
	       "  It always lands. The target's defenses apply to the damage after.\n" +
	       fact("Your lag", seconds(dragon_punch_lag())) +
	       fact("Sizes the target may differ from yours",
		    std::to_string(dragon_punch_size_gap()));
}

void do_dragon_punch(P_char ch, char *argument, int /*cmd*/)
{
	P_char vict = NULL;
	int skl_lvl = 0;
	int dam = 0;
	struct damage_messages messages = {
		"WHAP!  For a moment, you feel just like a dragon must as you punch $N.",
		"$n's fist flies toward you at frightening speeds, stopping only when it strikes your flesh.",
		"$n's fist shoots with sound barrier-breaking force towards $N, stopping only when it strikes $S flesh.",
		"You punch forcefully at $N, causing $S face to collapse under the blow, blood everywhere.  Hmm, doesn't look like $N will recover. Ever.",
		"$n's forceful punch causes you to see red, until you die shortly thereafter.",
		"$n punches $N right in the face!  There is blood everywhere, and $N seems to be dead!",
		0
	};

	if ((skl_lvl = GET_CHAR_SKILL(ch, SKILL_DRAGON_PUNCH)) == 0)
	{
		send_to_char("You don't know how.\r\n", ch);
		return;
	}

	vict = ParseTarget(ch, argument);
	if (!vict)
	{
		send_to_char(
			"A true martial artist would know his opponent for certain before striking.\r\n",
			ch);
		return;
	}
	if (!CanDoFightMove(ch, vict))
		return;

	if ((GET_ALT_SIZE(vict) < (GET_ALT_SIZE(ch) - dragon_punch_size_gap())) ||
	    (GET_ALT_SIZE(vict) > (GET_ALT_SIZE(ch) + dragon_punch_size_gap())))
	{
		send_to_char("Your punch would not be very effective on an opponent that size.\n\r",
			     ch);
		return;
	}

	skl_lvl = BOUNDED(0, skl_lvl + GetConditionModifier(vict), 100);

	dam = dragon_punch_roll(live_rolls);
	dam = dragon_punch_damage(dam, skl_lvl);

	notch_skill(ch, SKILL_DRAGON_PUNCH, get_property("skill.notch.offensive", 15));
	// Gona try making them always land, but have damage based on skill.
	/*
	if (!notch_skill(ch, SKILL_DRAGON_PUNCH,
	                 get_property("skill.notch.offensive", 15)) &&
	    number(1, 101) > skl_lvl)
	{
	  act("You miss $N with your haymaker!", FALSE, ch, 0, vict, TO_CHAR);
	  act("$n throws a haymaker at you which whistles by your ear!", FALSE, ch,
	      0, vict, TO_VICT);
	  act("$n just misses $N with a strong punch!", FALSE, ch, 0, vict,
	      TO_NOTVICT);
	}
	else
	*/
	const int result = melee_damage(ch, vict, dam, PHSDAM_TOUCH, &messages);

	if (result != DAM_CHARDEAD && result != DAM_BOTHDEAD)
		CharWait(ch, dragon_punch_lag());
}

void do_OLD_bandage(P_char ch, char *arg, int /*cmd*/)
{
	char name[MAX_INPUT_LENGTH];

	/*  char Gbuf1[MAX_STRING_LENGTH];*/
	P_char t_char = NULL;

	if (!SanityCheck(ch, "do_bandage"))
		return;

	if (IS_NPC(ch))
	{
		send_to_char("You're too NPC-like to try.\r\n", ch);
		return;
	}
	if (IS_PC(ch) && GET_CHAR_SKILL(ch, SKILL_BANDAGE) == 0)
	{
		send_to_char(
			"Maybe you should leave that to someone skilled in battlefield first aid.\r\n",
			ch);
		return;
	}
	if (!*arg)
	{
		send_to_char("Yes, but whom would you like to bandage?\r\n", ch);
		return;
	}
	if (IS_FIGHTING(ch))
	{
		send_to_char("Try again when someone isn't trying to kill you.\r\n", ch);
		return;
	}
	one_argument(arg, name);
	if (!(t_char = get_char_room_vis(ch, name)))
	{
		send_to_char("You don't see that person here.\r\n", ch);
		return;
	}
	if (NumAttackers(t_char))
	{
		send_to_char("That person is still being attacked, maybe you should wait?\r\n", ch);
		return;
	}
	if (GET_HIT(t_char) >= 0 /* && GET_HIT(t_char) < GET_MAX_HIT(t_char) */)
	{
		/*
		    snprintf(Gbuf1, MAX_STRING_LENGTH, "Your battlefield first-aid won't do much for %s right now.\r\n", GET_NAME(t_char));
		    send_to_char(Gbuf1, ch);
		*/
		act("Your battlefield first-aid won't do much for $N right now.", TRUE, ch, 0,
		    t_char, TO_CHAR);
		return;
	}
	else if (GET_HIT(t_char) == GET_MAX_HIT(t_char))
	{
		/*
		    snprintf(Gbuf1, MAX_STRING_LENGTH, "%s is in perfect shape already!\r\n", HSSH(t_char));
		    send_to_char(Gbuf1, ch);
		*/
		act("$N is in perfect shape already!", TRUE, ch, 0, t_char, TO_CHAR);
		return;
	}
	if (number(1, 10) <= GET_CHAR_SKILL(ch, SKILL_BANDAGE))
	{ /*
		 Made their
		 roll
	   */
		act("You bandage $N, whose wounds appear not quite so life-threatening.", TRUE, ch,
		    0, t_char, TO_CHAR);
		act("$n bandages $N, whose wounds appear not quite so life-threatening.", FALSE, ch,
		    0, t_char, TO_ROOM);
		act("You feel slightly better, but you still are in desperate need of healing.",
		    TRUE, ch, 0, t_char, TO_VICT);
		if (IS_THRIKREEN(t_char))
			GET_HIT(t_char) += 1;
		else
			GET_HIT(t_char) += 2;

		if (has_innate(ch, INNATE_BATTLEAID) && GET_HIT(t_char) < 0)
			GET_HIT(t_char) += ((GET_HIT(t_char) * -1) + 1);

		notch_skill(ch, SKILL_BANDAGE, 3.33);
	}
	else if (number(1, 100) > 90)
	{ /*
		 Failed, and failed badly. Tricky
		 business fixing someone out there on
		 the battlefield.
	   */
		act("Your hasty attempts to help $N just cause more damage!  You kill $M!", TRUE,
		    ch, 0, t_char, TO_CHAR);
		act("$n's hasty attempts to help $N just cause more damage!  $m kills $M!", FALSE,
		    ch, 0, t_char, TO_ROOM);
		act("You suddenly feel much worse!  Someone's attempts to help you failed!", TRUE,
		    ch, 0, t_char, TO_VICT);
		if (IS_PC(t_char))
		{
			statuslog(t_char->player.level,
				  "%s died when %s attempted to bandage %s at %s [%d].",
				  GET_NAME(t_char), GET_NAME(ch), HMHR(t_char),
				  world[t_char->in_room].name, world[t_char->in_room].number);
			logit(LOG_DEATH, "%s killed by failed bandage from %s at %s [%d].",
			      GET_NAME(t_char), GET_NAME(ch), world[t_char->in_room].name,
			      world[t_char->in_room].number);
		}
		die(t_char, ch);
		t_char = NULL;
	}
	else
	{
		act("You clumsily cause more damage to $N!", TRUE, ch, 0, t_char, TO_CHAR);
		act("$n clumsily causes more damage to $N!", FALSE, ch, 0, t_char, TO_ROOM);
		act("You feel slightly worse as someone causes more damage to you!", FALSE, ch, 0,
		    t_char, TO_VICT);
		GET_HIT(t_char)
		--;
		if (GET_HIT(t_char) <= -10)
		{
			if (IS_PC(t_char))
			{
				statuslog(t_char->player.level,
					  "%s: <-10 hps and died from %s's failed bandage in %d.",
					  GET_NAME(t_char), GET_NAME(ch),
					  ((t_char->in_room == NOWHERE) ?
						   -1 :
						   world[t_char->in_room].number));

				logit(LOG_DEATH,
				      "%s: <-10 hps and died from %s's failed bandage in %d.",
				      GET_NAME(t_char), GET_NAME(ch),
				      ((t_char->in_room == NOWHERE) ?
					       -1 :
					       world[t_char->in_room].number));
			}
			die(t_char, ch);
			t_char = NULL;
		}
	}
	if (t_char)
		update_pos(t_char);
	CharWait(ch, 2 * PULSE_VIOLENCE);
	return;
}

void event_summon_book(P_char ch, P_char /*victim*/, P_obj /*obj*/, void * /*data*/)
{
	P_obj book;
	char bookname[512];
	char namebuf[512];

	snprintf(bookname, 512, "bookof%s", ch->player.name);

	book = read_object(31, VIRTUAL);
	if (book == NULL)
		return;

	SET_BIT(book->str_mask, STRUNG_DESC2 || STRUNG_KEYS);
	checked_snprintf(namebuf, 512, "book spellbook %s", bookname);
	book->name = str_dup(namebuf);
	snprintf(namebuf, 512, "a &+Wsp&+wel&+Wlb&+woo&+Wk&n &+Lbearing the insignia of&n %s",
		 ch->player.name);
	book->short_description = str_dup(namebuf);
	book->bitvector = 0;

	submit_summoned_replacement(ch, book, summoned_replacement_kind::book);
}

static int summon_book_delay()
{
	return PULSE_VIOLENCE;
}

std::string summon_book_innate_facts(P_char /*ch*/)
{
	return fact("Your spellbook arrives after", seconds(summon_book_delay())) +
	       "  It needs no rest, has no lag, and comes on its own when you enter the game.\n";
}

void do_summon_book(P_char ch, char * /*arg*/, int /*cmd*/)
{
	send_to_char("You utter a magical formula summoning your spellbook..\r\n", ch);
	add_event(event_summon_book, summon_book_delay(), ch, 0, 0, 0, 0, 0);
}

static int summon_totem_hit_points()
{
	return 10;
}

static int summon_totem_pulse()
{
	return -1;
}

void event_summon_totem(P_char ch, P_char /*victim*/, P_obj /*obj*/, void * /*data*/)
{
	P_obj totem;
	char totemname[512];
	char namebuf[512];

	snprintf(totemname, 512, "totem spirit %s", ch->player.name);

	totem = read_object(417, VIRTUAL);
	if (totem == NULL)
		return;

	SET_BIT(totem->str_mask, STRUNG_DESC2 || STRUNG_KEYS);
	checked_snprintf(namebuf, 512, "totem spirit %s", totemname);
	totem->name = str_dup(namebuf);
	snprintf(namebuf, 512, "a &+wspirit &+ytotem&n of&n &+G%s&n", ch->player.name);
	totem->short_description = str_dup(namebuf);
	totem->bitvector = 0;
	/* okay, lets give the totem stats, based on the level of the lil baby goblin */
	if (GET_LEVEL(ch) >= 56)
	{
		totem->affected[2].location = APPLY_SPELL_PULSE;
		totem->affected[2].modifier = summon_totem_pulse();
	}
	if (GET_LEVEL(ch) >= 51)
	{
		totem->affected[1].location = APPLY_HIT;
		totem->affected[1].modifier = summon_totem_hit_points();
	}
	if (GET_LEVEL(ch) >= 41)
	{
		SET_BIT(totem->bitvector2, AFF2_SOULSHIELD);
	}
	if (GET_LEVEL(ch) >= 36)
	{
		SET_BIT(totem->bitvector, AFF_SENSE_LIFE);
	}
	if (GET_LEVEL(ch) >= 31)
	{
		SET_BIT(totem->bitvector, AFF_FARSEE);
	}

	submit_summoned_replacement(ch, totem, summoned_replacement_kind::totem);
}

static int summon_totem_delay()
{
	return PULSE_VIOLENCE;
}

std::string summon_totem_innate_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	std::string text = fact("Your totem arrives after", seconds(summon_totem_delay()));
	if (level >= 31)
		text += "  It grants farsee.\n";
	if (level >= 36)
		text += "  It grants sense life.\n";
	if (level >= 41)
		text += "  It grants soulshield.\n";
	if (level >= 51)
		text += fact("Hit points", "+" + std::to_string(summon_totem_hit_points()));
	if (level >= 56)
		text += fact("Spell pulse", std::to_string(summon_totem_pulse()));
	if (level < 56)
		text += "  More powers come with level: 31, 36, 41, 51 and 56.\n";
	return text + "  It replaces your last totem, with no rest and no lag.\n";
}

void do_summon_totem(P_char ch, char * /*arg*/, int /*cmd*/)
{
	send_to_char(
		"You thrust your arms skyward, uttering an incantation to &+GMaglubiyet&n.\r\n",
		ch);
	add_event(event_summon_totem, summon_totem_delay(), ch, 0, 0, 0, 0, 0);
}

static int summoned_mount_factor(const Rolls &rolls, P_char ch)
{
	const int factor = (int)(GET_LEVEL(ch) * get_property("mount.summoned.FactorMod", 0.750) +
				 rolls.number(GET_LEVEL(ch) < 6 ? 1 : -5, 5));
	return MAX(1, factor);
}

static int summoned_mount_level(int factor)
{
	return 10 + factor;
}

static int summoned_mount_hit_points(P_char ch, int factor)
{
	return factor * (IS_SKELETON(ch) ? 15 : 50);
}

static int summoned_mount_skeleton_vitality(const Rolls &rolls)
{
	return 100 + rolls.number(-25, 25);
}

void mount_summoning_thing(P_char ch, P_char /*victim*/, P_obj /*obj*/, void * /*data*/)
{
	P_char mount = NULL;
	int factor;
	struct follow_type *fol;

	if ((ch->in_room == NOWHERE) || !IS_ALIVE(ch))
		return;

	if (IS_ROOM(ch->in_room, ROOM_LOCKER))
	{
		if (IS_DRAGOON(ch))
			send_to_char(
				"Your &+Gdr&+Lag&+Gon&n couldn't find its way into the locker.\r\n",
				ch);
		else
			send_to_char("Your mount couldn't find its way into the locker.\r\n", ch);
		return;
	}

	if (!IS_DRAGOON(ch))
	{
		if (!is_prime_plane(ch->in_room) || world[ch->in_room].sector_type == SECT_OCEAN ||
		    IS_ROOM(ch->in_room, ROOM_SINGLE_FILE))
		{
			send_to_char("&+LYour mount cannot find you here...\r\n", ch);
			return;
		}
	}
	else
	{
		if (world[ch->in_room].sector_type == SECT_OCEAN ||
		    IS_ROOM(ch->in_room, ROOM_SINGLE_FILE))
		{
			send_to_char("&+LYour &+Gdr&+Lag&+Gon&n cannot find you here...\r\n", ch);
			return;
		}
	}

	for (fol = ch->followers; fol; fol = fol->next)
	{
		if (IS_NPC(fol->follower) && IS_SET(fol->follower->specials.act, ACT_MOUNT))
		{
			if (IS_DRAGOON(ch))
				send_to_char("You already have a &+Gdr&+Lag&+Gon&n!\r\n", ch);
			else
				send_to_char("You already have a mount!\r\n", ch);
			return;
		}
	}

	if (IS_SKELETON(ch))
	{
		mount = read_mobile(34429, VIRTUAL);
	}
	else if (IS_EVIL(ch) && GET_CLASS(ch, CLASS_ANTIPALADIN))
	{
		mount = read_mobile(GET_SPEC(ch, CLASS_ANTIPALADIN, SPEC_DEMONIC) ? 1234 : 1231,
				    VIRTUAL);
	}
	else if (IS_GOOD(ch) && GET_CLASS(ch, CLASS_PALADIN))
	{
		mount = read_mobile(GET_SPEC(ch, CLASS_PALADIN, SPEC_CAVALIER) ? 1235 : 1232,
				    VIRTUAL);
	}
	else if (GET_RACE(ch) == RACE_GOBLIN || GET_RACE(ch) == RACE_ORC)
	{
		mount = read_mobile(39, VIRTUAL);
	}
	else if (IS_DRAGOON(ch))
	{
		if (GET_LEVEL(ch) < 11)
			mount = read_mobile(102, VIRTUAL);
		else if (GET_LEVEL(ch) < 21)
			mount = read_mobile(103, VIRTUAL);
		else if (GET_LEVEL(ch) < 31)
			mount = read_mobile(104, VIRTUAL);
		else if (GET_LEVEL(ch) < 41)
			mount = read_mobile(105, VIRTUAL);
		else if (GET_LEVEL(ch) < 51)
			mount = read_mobile(106, VIRTUAL);
		else
			mount = read_mobile(107, VIRTUAL);
	}
	else
	{
		send_to_char("A mount didn't load. Please report this with the bug command.", ch);
		return;
	}
	if (!mount)
	{
		logit(LOG_DEBUG, "mount_summoning_thing() did not load mount.");
		send_to_char("No mount could be found, please report this to a god.\r\n", ch);
		return;
	}
	if (ch && mount) // Just making sure.
	{
		char_to_room(mount, ch->in_room, -2);

		if (IS_DRAGOON(ch))
		{
			act("$N answers your call for aid with a mighty &-L&+RROAR&n!", TRUE, ch, 0,
			    mount, TO_CHAR);
			act("$N swoops in with a mighty &-L&+RROAR&n, and stands ready to heed $n.",
			    TRUE, ch, 0, mount, TO_ROOM);
		}
		else
		{
			act("$N answers your summons!", TRUE, ch, 0, mount, TO_CHAR);
			act("$N walks in, seemingly from nowhere, and nuzzles $n's face.", TRUE, ch,
			    0, mount, TO_ROOM);
		}

		setup_pet(mount, ch, -1, PET_NOCASH);
		add_follower(mount, ch);

		if (IS_DRAGOON(ch))
			link_char(ch, mount, LNK_DRAGOON_MOUNT);

		if (GET_LEVEL(ch) > 50 || GET_SPEC(ch, CLASS_PALADIN, SPEC_CAVALIER) ||
		    GET_SPEC(ch, CLASS_ANTIPALADIN, SPEC_DEMONIC))
		{
			SET_BIT(mount->specials.affected_by, AFF_FLY);
		}

		// Made all ap and paladin mounts more resistant. Nov08 -Lucrot
		if (GET_CLASS(ch, CLASS_ANTIPALADIN | CLASS_PALADIN))
		{ // Tweaked AC from level * 3 to level * 6 Nov08 -Lucrot
			mount->points.base_armor = 0 - GET_LEVEL(ch) * 5;
			if (GET_LEVEL(ch) > 45)
			{
				SET_BIT(mount->specials.affected_by, AFF_PROT_FIRE);
				SET_BIT(mount->specials.affected_by2, AFF2_PROT_COLD);
				SET_BIT(mount->specials.affected_by2, AFF2_PROT_LIGHTNING);
				SET_BIT(mount->specials.affected_by2, AFF2_PROT_GAS);
				SET_BIT(mount->specials.affected_by2, AFF2_PROT_ACID);
				if (GET_SPEC(ch, CLASS_PALADIN, SPEC_CAVALIER))
				{
					SET_BIT(mount->specials.affected_by, AFF_PROTECT_EVIL);
				}
				else if (GET_SPEC(ch, CLASS_ANTIPALADIN, SPEC_DEMONIC))
				{
					SET_BIT(mount->specials.affected_by, AFF_PROTECT_GOOD);
				}
			}
		}

		if (GET_LEVEL(ch) > 50 && GET_SPEC(ch, CLASS_PALADIN, SPEC_CAVALIER))
		{ // Holy sacrifice affect does not help much. Nov08 -Lucrot
			SET_BIT(mount->specials.affected_by4, AFF4_HOLY_SACRIFICE);
			// Added. Nov08 -Lucrot
			SET_BIT(mount->specials.affected_by4, AFF4_REGENERATION);

			if (GET_LEVEL(ch) > 53)
			{ // Added. Nov08 -Lucrot
				SET_BIT(mount->specials.affected_by, AFF_HASTE);
			}
		}

		if (GET_LEVEL(ch) > 50 && GET_SPEC(ch, CLASS_ANTIPALADIN, SPEC_DEMONIC))
		{ // Battle X is excellent. Nov08 -Lucrot
			SET_BIT(mount->specials.affected_by4, AFF4_BATTLE_ECSTASY);
		}

		if (GET_LEVEL(ch) > 50 && // For all paladin and ap mounts. Nov08 -Lucrot
		    GET_CLASS(ch, CLASS_ANTIPALADIN | CLASS_PALADIN))
		{ // Added. Nov08 -Lucrot
			SET_BIT(mount->specials.affected_by4, AFF4_NOFEAR);

			if (GET_LEVEL(ch) > 51)
			{ // Added. Nov08 -Lucrot
				SET_BIT(mount->specials.affected_by5, AFF5_NOBLIND);
			}

			if (GET_LEVEL(ch) > 52)
			{ // Added. Nov08 -Lucrot
				SET_BIT(mount->specials.act, ACT_IMMUNE_TO_PARA);
			}
		}

		/*
		   now we modify the base mount, based on paladin's level and alignment
		 */

		/*
		   factor ranges from 0 to 25 (unlucky 351 align level 15 to lucky 1000 align
		   level 50)
		 */
		// Alignment adjusted only affect paladins. Making these modifiers
		// standard for both classes. Nov08 -Lucrot
		// align = GET_ALIGNMENT(ch) / 200;
		// if (IS_EVIL(ch))
		// align = -align;

		// Level 30 mount factor average = 22.5 based on 0.750 mod.
		// Level 56 mount factor average = 42 based on 0.750 mod. Nov08 -Lucrot

		factor = summoned_mount_factor(live_rolls, ch);

		mount->base_stats.Str = BOUNDED(75, mount->base_stats.Str, 75 + factor);
		mount->base_stats.Agi = BOUNDED(75, mount->base_stats.Agi, 75 + factor);
		mount->base_stats.Con = BOUNDED(75, mount->base_stats.Con, 75 + factor);
		mount->base_stats.Cha = 100;
		mount->player.level = summoned_mount_level(factor);
		mount->points.base_hit = summoned_mount_hit_points(ch, factor);
		GET_HIT(mount) = summoned_mount_hit_points(ch, factor);
		GET_MAX_HIT(mount) = summoned_mount_hit_points(ch, factor);
		mount->player.m_class = CLASS_NONE;
		MonkSetSpecialDie(mount);
		SET_BIT(mount->specials.act, ACT_MOUNT);

		if (IS_SKELETON(ch))
		{
			// Skeleton vitality is reset after conversion: 100 +/- 25, or 75-125.
			mount->points.vitality = mount->points.base_vitality =
				mount->points.max_vitality =
					summoned_mount_skeleton_vitality(live_rolls);
		}

		if (IS_SET(mount->specials.act, ACT_MEMORY))
		{
			clearMemory(mount);
			REMOVE_BIT(mount->specials.act, ACT_MEMORY);
		}
		return;
	}
	send_to_char("A mount didn't load. Please report this with the bug command.\r\n", ch);
	return;
}

// How long a call for a mount or warg takes, in pulses.
static int summon_mount_delay(const Rolls &rolls, P_char ch)
{
	return rolls.number(70 - GET_LEVEL(ch), 100 + rolls.number(1, 200 - 2 * GET_LEVEL(ch)));
}

// What answers a call: the numbers the mount and warg pages share.
static std::string summoned_mount_facts(P_char ch)
{
	const Range factor = { summoned_mount_factor(lowest_rolls, ch),
			       summoned_mount_factor(highest_rolls, ch) };
	std::string text =
		fact("It arrives after", seconds(summon_mount_delay(lowest_rolls, ch)) + " to " +
						 seconds(summon_mount_delay(highest_rolls, ch))) +
		fact("Its level", show({ summoned_mount_level(factor.low),
					 summoned_mount_level(factor.high) })) +
		fact("Its hit points", show({ summoned_mount_hit_points(ch, factor.low),
					      summoned_mount_hit_points(ch, factor.high) }));
	if (IS_SKELETON(ch))
		text += fact("Its vitality",
			     show({ summoned_mount_skeleton_vitality(lowest_rolls),
				    summoned_mount_skeleton_vitality(highest_rolls) }));
	return text;
}

std::string summon_mount_innate_facts(P_char ch)
{
	return summoned_mount_facts(ch) + innate_rest_facts(INNATE_SUMMON_MOUNT, 0) +
	       "  One mount at a time, and none in dragon form.\n"
	       "  Paladins must be good and antipaladins evil.\n"
	       "  Not in a locker, single-file room or ocean. A dragoon may call from\n"
	       "  anywhere else; others need the outdoors or underworld on the prime plane.\n";
}

void do_summon_mount(P_char ch, char * /*arg*/, int /*cmd*/)
{
	int sumtime;
	struct follow_type *fol;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (IS_DRAGON_FORM(ch))
		return;

	for (fol = ch->followers; fol; fol = fol->next)
	{
		if (IS_NPC(fol->follower) && IS_SET(fol->follower->specials.act, ACT_MOUNT))
		{
			send_to_char("You already have a mount!\r\n", ch);
			return;
		}
	}

	if (!IS_DRAGOON(ch))
	{
		if (!is_prime_plane(ch->in_room))
		{
			send_to_char(
				"&+LYour mount cannot answer your call in this strange land/terrain...\r\n",
				ch);
			return;
		}
	}

	if (IS_ROOM(ch->in_room, ROOM_LOCKER) || IS_ROOM(ch->in_room, ROOM_SINGLE_FILE))
	{
		if (IS_DRAGOON(ch))
			send_to_char("A dragon couldn't fit in here!\r\n", ch);
		else
			send_to_char("A horse couldn't fit in here!\r\n", ch);
		return;
	}

	if (world[ch->in_room].sector_type == SECT_OCEAN)
	{
		send_to_char("Nothing out here will answer your call!\r\n", ch);
		return;
	}

	if (!IS_GOOD(ch) && IS_PC(ch) && GET_CLASS(ch, CLASS_PALADIN))
	{
		send_to_char("Not even horses can stand your offensive presence!\r\n", ch);
		return;
	}

	if (!IS_EVIL(ch) && IS_PC(ch) && GET_CLASS(ch, CLASS_ANTIPALADIN))
	{
		send_to_char("Your innate skill seems to falter. You must be evil.\r\n", ch);
		return;
	}

	if (!IS_DRAGOON(ch))
	{
		if (!OUTSIDE(ch) && !IS_UNDERWORLD(ch->in_room))
		{
			send_to_char("Try again, OUTDOORS THIS TIME!\r\n", ch);
			return;
		}
	}

	if (!check_innate_time(ch, INNATE_SUMMON_MOUNT))
	{
		send_to_char("You can't summon another mount yet.\r\n", ch);
		return;
	}

	if (IS_PC_PET(ch))
	{
		send_to_char("No mount for pets.\n", ch);
		return;
	}

	if (IS_DRAGOON(ch))
		send_to_char("You call upon the &+Gdr&+Lag&+Gon&n &+Lgod&n for aid..\r\n", ch);
	else
		send_to_char("You begin calling for a mount..\r\n", ch);

	sumtime = summon_mount_delay(live_rolls, ch);
	add_event(mount_summoning_thing, sumtime, ch, 0, 0, 0, 0, 0);
}

std::string summon_warg_innate_facts(P_char ch)
{
	return summoned_mount_facts(ch) + innate_rest_facts(INNATE_SUMMON_WARG, 0) +
	       "  One at a time. It needs the outdoors or underworld on the prime plane,\n"
	       "  and arrives nowhere that is a locker, single-file room or ocean.\n";
}

void do_summon_warg(P_char ch, char * /*arg*/, int /*cmd*/)
{
	int sumtime;
	struct follow_type *fol;

	for (fol = ch->followers; fol; fol = fol->next)
		if (IS_NPC(fol->follower) && IS_SET(fol->follower->specials.act, ACT_MOUNT))
		{
			send_to_char("You already have a warg!\r\n", ch);
			return;
		}

	if (IS_ROOM(ch->in_room, ROOM_LOCKER))
	{
		send_to_char("A warg couldn't fit in here!\r\n", ch);
		return;
	}

	if (!OUTSIDE(ch) && !IS_UNDERWORLD(ch->in_room))
	{
		send_to_char("Try again, OUTDOORS THIS TIME!\r\n", ch);
		return;
	}
	if (!check_innate_time(ch, INNATE_SUMMON_WARG))
	{
		send_to_char("You can summon just one warg a day!\r\n", ch);
		return;
	}
	send_to_char("You begin calling for a warg..\r\n", ch);
	sumtime = summon_mount_delay(live_rolls, ch);
	add_event(mount_summoning_thing, sumtime, ch, 0, 0, 0, 0, 0);
}

static int summon_horde_most(P_char ch)
{
	return BOUNDED(1, (int)(GET_LEVEL(ch) / 10), 20);
}

static int summon_horde_orc_level()
{
	return 1;
}

static int summon_horde_orc_hit_points()
{
	return 1;
}

void orc_summoning_thing(P_char ch, P_char /*victim*/, P_obj /*obj*/, void * /*data*/)
{
	P_char orc = NULL;
	int /*shown = FALSE, */ called, i, count = 0, max_respond;
	struct char_link_data *cld;

	if (!ch || (ch->in_room == NOWHERE)) /*
	                                        They died in the meantime. Events
	                                        should have been pulled for them,
	                                        but why trust that
	                                      */
		return;

	if (IS_ROOM(ch->in_room, ROOM_LOCKER))
	{
		send_to_char("Your horde couldn't possibly fit in your locker!\r\n", ch);
		return;
	}

	if (IS_ROOM(ch->in_room, ROOM_SINGLE_FILE))
	{
		send_to_char(
			"Your horde failed to reach you in this single file room. They went home.\r\n",
			ch);
		return;
	}

	max_respond = summon_horde_most(ch);

	for (cld = ch->linked; cld; cld = cld->next_linked)
		if (GET_RACE(cld->linking) == RACE_ORC && IS_NPC(cld->linking))
			count++;

	if (count >= max_respond)
	{
		send_to_char("It appears no more will answer your call for help.\r\n", ch);
		return;
	}
	called = max_respond - count;

	for (i = 0; i < called; i++)
	{
		orc = read_mobile(4007, VIRTUAL);
		if (!orc /*&& !shown */)
		{
			logit(LOG_DEBUG, "orc_summoning_thing(): mob 4010 not loadable");
			send_to_char(
				"No orc horde could be found, please report this to a god.\r\n",
				ch);
			/*      shown = TRUE;*/
			return;
		}
		char_to_room(orc, ch->in_room, -2);

		//      GET_LEVEL(orc) = 5;
		orc->player.level = summon_horde_orc_level();
		GET_MAX_HIT(orc) = GET_HIT(orc) = summon_horde_orc_hit_points();

		orc->only.npc->aggro_flags = 0;
		setup_pet(orc, ch, -1, PET_NOCASH);
		add_follower(orc, ch);
	}

	send_to_char("Your brethren answer your call for help!\r\n", ch);
	act("A horde of orcs appear, charging in from every direction!", TRUE, ch, 0, 0, TO_ROOM);
}

static int summon_horde_delay(const Rolls &rolls, P_char ch)
{
	return rolls.number(70 - GET_LEVEL(ch), 70);
}

std::string summon_horde_innate_facts(P_char ch)
{
	return fact("Orcs", "up to " + std::to_string(summon_horde_most(ch)) +
				    " at your level, counting those you have") +
	       fact("Each orc's level", std::to_string(summon_horde_orc_level())) +
	       fact("Each orc's hit points", std::to_string(summon_horde_orc_hit_points())) +
	       fact("They arrive after", seconds(summon_horde_delay(lowest_rolls, ch)) + " to " +
						 seconds(summon_horde_delay(highest_rolls, ch))) +
	       innate_rest_facts(INNATE_SUMMON_HORDE, 0) +
	       "  Only an orc may call. Off the prime plane or on the ocean, no use is spent.\n"
	       "  They cannot reach single-file rooms or lockers.\n";
}

void do_summon_orc(P_char ch, char * /*arg*/, int /*cmd*/)
{
	int sumtime;

	SanityCheck(ch, "do_summon_orc");

	if (IS_PC(ch) && (GET_RACE(ch) != RACE_ORC))
	{
		send_to_char("Only an orc may call for the orc horde!\r\n", ch);
		return;
	}
	// Cannot summon horde to plane type rooms or on oceans.
	if (!is_prime_plane(ch->in_room) || world[ch->in_room].sector_type == SECT_OCEAN)
	{
		send_to_char(
			"&+LYou have a bad feeling that your horde will not arrive to this hostile environment...\r\n",
			ch);
		return;
	}

	if (!check_innate_time(ch, INNATE_SUMMON_HORDE))
	{
		send_to_char("You can call for the horde just thrice weekly!\r\n", ch);
		return;
	}

	act("$n throws $s head back, letting out a long, low-pitched howl...", FALSE, ch, 0, 0,
	    TO_ROOM);
	send_to_char("You throw your head back, letting out a long, low-pitched howl...\r\n", ch);

	if (IS_ROOM(ch->in_room, ROOM_SINGLE_FILE))
	{
		send_to_char("Your horde will not reach you here in this single file room.\r\n",
			     ch);
	}

	sumtime = summon_horde_delay(live_rolls, ch);
	add_event(orc_summoning_thing, sumtime, ch, 0, 0, 0, 0, 0);
}

static int ogre_roar_roll(const Rolls &rolls)
{
	return rolls.number(1, 101);
}

static int ogre_roar_worst_duration(int temp)
{
	return 10 + (temp / 7);
}

static int ogre_roar_best_duration(int temp)
{
	return 20 - (temp / 7);
}

static int ogre_roar_duration(int temp)
{
	return 15 - (temp / 7);
}

static int ogre_roar_best_ac(P_char ch)
{
	return GET_LEVEL(ch) + 10;
}

static int ogre_roar_ac(P_char ch)
{
	return GET_LEVEL(ch);
}

// How much of a hitroll each outcome takes, as hitroll * level / this.
static int ogre_roar_hitroll_divisor()
{
	return 90;
}

static int ogre_roar_best_hitroll_divisor()
{
	return 60;
}

static int ogre_roar_worst_hitroll_divisor()
{
	return 100;
}

// The ogre's outcome: below this the target is scared, and 1 is the best roar.
static int ogre_roar_threshold()
{
	return 68;
}

std::string ogre_roar_innate_facts(P_char ch)
{
	const int threshold = ogre_roar_threshold();
	return fact("Normal roar, with no modifiers",
		    chance_under(threshold - 1, ogre_roar_roll(lowest_rolls),
				 ogre_roar_roll(highest_rolls))) +
	       fact("Target's armor class", "+" + std::to_string(ogre_roar_ac(ch))) +
	       fact("Its hitroll loss", "its hitroll * " + std::to_string(GET_LEVEL(ch)) + " / " +
						std::to_string(ogre_roar_hitroll_divisor())) +
	       fact("For", game_hours_range(
				   { ogre_roar_duration(threshold - 1), ogre_roar_duration(2) })) +
	       fact("Best roar, " + one_in(ogre_roar_roll) + ": armor class",
		    "+" + std::to_string(ogre_roar_best_ac(ch))) +
	       fact("Its hitroll loss", "its hitroll * " + std::to_string(GET_LEVEL(ch)) + " / " +
						std::to_string(ogre_roar_best_hitroll_divisor())) +
	       fact("For", game_hours(ogre_roar_best_duration(1))) +
	       fact("Worst roar, " + one_in(ogre_roar_roll) + ": your hitroll loss",
		    "your hitroll * its level / " +
			    std::to_string(ogre_roar_worst_hitroll_divisor())) +
	       fact("And your armor class", "+1 + its level / 2") +
	       fact("For", game_hours(ogre_roar_worst_duration(101))) +
	       innate_rest_facts(INNATE_OGREROAR, 0) +
	       "  Only a plain ogre may roar. Level, power and wisdom shift the roll,\n"
	       "  and a fearful or meditating target favors you. Not while prone.\n"
	       "  Bigger targets and illithids ignore it, as do those who can't hear,\n"
	       "  are already roared at, or stand in a silent room. It has no lag.\n";
}

/* Ogre roar: Ogre scares the wits out of enemy. Assumed to be innate2 */
void do_ogre_roar(P_char ch, char *argument, int /*cmd*/)
{
	P_char vict = NULL;
	char name[MAX_INPUT_LENGTH];
	int temp = 0;
	struct affected_type af;

	/* Why is the Proc called at all? */
	if (!ch)
		return;

	/* Test if it is an Ogre that hasn't used innate too often */
	if (!has_innate(ch, INNATE_OGREROAR))
	{
		send_to_char("Your roar doesn't impress anybody that much!\r\n", ch);
		return;
	}
	if (!check_innate_time(ch, INNATE_OGREROAR))
	{
		send_to_char("Your throat is still too sore!\r\n", ch);
		return;
	}
	/* Are we ready to fight?  Impossible to roar loudly in reclined position */
	if (GET_POS(ch) == POS_PRONE)
	{
		send_to_char("They will just think you are snoring!\r\n", ch);
		return;
	}
	/* Do we have an enemy at all? */
	one_argument(argument, name);
	if (*name)
		vict = get_char_room_vis(ch, name);
	else if (!vict && GET_OPPONENT(ch))
	{
		vict = GET_OPPONENT(ch);
		if (vict->in_room != ch->in_room)
		{
			stop_fighting(ch);
			vict = NULL;
		}
	}
	if (!vict)
	{
		send_to_char("You roar and roar, but nobody cares.\r\n", ch);
		return;
	}
	/* do some basic fight checks */
	if (!CanDoFightMove(ch, vict))
		return;

	/* now checks on the race (size) and state of victim */
	/* big stuff isn't impressed at all, illithids have too much control
	   over their minds to be scared */
	if ((GET_ALT_SIZE(vict) > GET_ALT_SIZE(ch)) || IS_ILLITHID(vict) || IS_PILLITHID(vict))
	{
		act("$n roars loudly at $N, but $N isn't fazed at all.", FALSE, ch, 0, vict,
		    TO_ROOM);
		act("Obviously you are not as scary as you think you are.", FALSE, ch, 0, vict,
		    TO_CHAR);
		act("$n roars at you, but you couldn't care less.", FALSE, ch, 0, vict, TO_VICT);
		return;
	}

	/* victim isn't hearing the roar */
	if (IS_AFFECTED(vict, AFF_KNOCKED_OUT) || IS_AFFECTED(vict, AFF_SLEEP) ||
	    GET_STAT(vict) < STAT_RESTING || IS_ROOM(vict->in_room, ROOM_SILENT))
	{
		act("$N isn't able to hear your roar.", FALSE, ch, 0, vict, TO_CHAR);
		return;
	}
	/* victim is already affected, can't scare him twice... */
	if (affected_by_spell(vict, SKILL_OGRE_ROAR))
	{
		act("$N is scared beyond caring anyway.", FALSE, ch, 0, vict, TO_CHAR);
		return;
	}
	/* all tests passed, let's see if we can do it */
	/* people with good control of their minds are hard to impress */
	temp = (GET_LEVEL(vict) - GET_LEVEL(ch)) / 10 + (GET_C_POW(vict) - GET_C_POW(ch)) / 15 +
	       (GET_C_WIS(vict) - GET_C_WIS(ch)) / 15;
	/* chance modifier bounded to min/max +-(6+10+10)=+-26 */
	/* do magic/affects check: is victim fearful already or meditating? */
	if (IS_AFFECTED(vict, AFF_FEAR) || IS_AFFECTED(vict, AFF_MEDITATE))
		temp -= 5;
	/* chance modifier now bounded by -31 to +26 */

	/* do random 1-101, add chance modifier */
	temp = BOUNDED(1, ogre_roar_roll(live_rolls) + temp, 101);

	/* worst case for ogre */
	if (temp == 101)
	{
		act("$n tries to roar at $N, but just whimpers instead!", FALSE, ch, 0, vict,
		    TO_ROOM);
		act("You are simply not up to it, $N frightens you too much!", FALSE, ch, 0, vict,
		    TO_CHAR);
		act("$n snivels, being afraid of you.", FALSE, ch, 0, vict, TO_VICT);
		/* apply a downgraded AC/HITROLL hurt to char instead of victim */
		bzero(&af, sizeof(af));
		af.type = SKILL_OGRE_ROAR;
		af.duration = ogre_roar_worst_duration(temp);
		af.modifier = 1 + GET_LEVEL(vict) / 2;
		af.location = APPLY_AC;
		affect_to_char(ch, &af);
		af.modifier =
			-(GET_HITROLL(ch) * GET_LEVEL(vict) / ogre_roar_worst_hitroll_divisor());
		af.location = APPLY_HITROLL;
		affect_to_char(ch, &af);

		if (IS_NPC(vict) && CAN_SEE(vict, ch))
		{
			remember(vict, ch);
			if (!IS_FIGHTING(vict))
				MobStartFight(vict, ch);
		}

		return;
	}
	/* best case for ogre - his roar shakes the world */
	if (temp == 1)
	{
		act("$n roars incredibly loud at $N, $N is almost lifted off $S feet!", FALSE, ch,
		    0, vict, TO_ROOM);
		act("That roar would have stopped a charging elephant!", FALSE, ch, 0, vict,
		    TO_CHAR);
		act("$n's roar freezes your brain and pops your eardrums!", FALSE, ch, 0, vict,
		    TO_VICT);
		/* this really messes the victim up... worse than normal roar */
		bzero(&af, sizeof(af));
		af.type = SKILL_OGRE_ROAR;
		af.duration = ogre_roar_best_duration(temp);
		af.modifier = ogre_roar_best_ac(ch);
		af.location = APPLY_AC;
		affect_to_char(vict, &af);
		af.modifier =
			-(GET_HITROLL(vict) * GET_LEVEL(ch) / ogre_roar_best_hitroll_divisor());
		af.location = APPLY_HITROLL;
		affect_to_char(vict, &af);
		return;
	}
	else
		/* now the usual, ogres has a 2/3 chance to succeed against a
		   enemy with modifiers=0 */
		if (temp < ogre_roar_threshold())
		{
			act("$n roars loudly at $N, who is visibly shaken.", FALSE, ch, 0, vict,
			    TO_ROOM);
			act("Your roar at $N has definitely scared $m.", FALSE, ch, 0, vict,
			    TO_CHAR);
			act("You feel a strong urge to run away after $n's roar.", FALSE, ch, 0,
			    vict, TO_VICT);
			/* standard hurt to AC/HITROLL */
			bzero(&af, sizeof(af));
			af.type = SKILL_OGRE_ROAR;
			af.duration = ogre_roar_duration(temp);
			af.modifier = ogre_roar_ac(ch);
			af.location = APPLY_AC;
			affect_to_char(vict, &af);
			af.modifier =
				-(GET_HITROLL(vict) * GET_LEVEL(ch) / ogre_roar_hitroll_divisor());
			af.location = APPLY_HITROLL;
			affect_to_char(vict, &af);
			return;
		}
		else
		{
			act("$n's roar doesn't impress $N at all.", FALSE, ch, 0, vict, TO_ROOM);
			act("$N didn't seem to notice your roar.  Go for more volume!", FALSE, ch,
			    0, vict, TO_CHAR);
			act("$n's roar almost makes you laugh.", FALSE, ch, 0, vict, TO_VICT);

			if (IS_NPC(vict) && CAN_SEE(vict, ch))
			{
				remember(vict, ch);
				if (!IS_FIGHTING(vict))
					MobStartFight(vict, ch);
			}

			return;
		}
}

/* Krov: carving procedure. checks in value[3] of a corpse which body
   parts are missing and then puts a (named) body part in corpse
   if the carve was successful */

// 101 ruins every part of the corpse; otherwise a roll up to your rating cuts cleanly.
static int carve_roll(const Rolls &rolls)
{
	return rolls.number(1, 101);
}

std::string carve_facts(P_char ch)
{
	const int rating = GET_CHAR_SKILL(ch, SKILL_CARVE);
	if (rating < 1)
		return "  You have not learned to carve.\n";
	return fact("Chance of a clean cut", chance_under(rating + 1, 1, 101)) +
	       fact("Chance you ruin every part", one_in(carve_roll)) +
	       "  A failed cut still costs that part.\n"
	       "  It takes a humanoid corpse, and a wielded blade, dagger or knife.\n";
}

void do_carve(struct char_data *ch, char *argument, int /*cmd*/)
{
	struct obj_data *corpse, *carve, *tool;
	char cname[MAX_STRING_LENGTH];
	char part[MAX_STRING_LENGTH];
	char buf[MAX_STRING_LENGTH];
	char *dscp;
	::byte percent;
	int i, which, piece, none;

	int carve_weight[9];

	/* find out what corpse and what bodypart we want */
	half_chop(argument, cname, part);

	/* what corpse is player trying to carve? */
	if (*cname)
	{
		corpse = get_obj_in_list_vis(ch, cname, world[ch->in_room].contents);
		if (!corpse)
		{
			send_to_char("Open your eyes - that's not here.\r\n", ch);
			return;
		}
	}
	else
	{
		send_to_char("Maybe you should find something to carve first?\r\n", ch);
		return;
	}

	/* check if player is trying to carve a corpse */
	if (GET_ITEM_TYPE(corpse) != ITEM_CORPSE)
	{
		send_to_char("Geez... try carving a dead body.\r\n", ch);
		return;
	}
	/* for now only allow humanoid corpses */
	if (!(corpse->value[1] & HUMANOID_CORPSE))
	{
		send_to_char("Why would you want to do that?\r\n", ch);
		return;
	}
	/* check out what parts the body still has, if no part is given */
	none = 0;
	if (!*part)
	{
		snprintf(buf, MAX_STRING_LENGTH, "Parts of %s that are still intact:\r\n",
			 corpse->short_description);
		for (i = 0; i < numCarvables; i++)
			if (!(corpse->value[1] & carve_part_flag[i]))
			{
				strcat(buf, carve_part_name[i]);
				strcat(buf, " ");
				none++;
			}
		if (!none)
			strcat(buf, "nothing");
		strcat(buf, "\r\n");
		send_to_char(buf, ch);
		return;
	}
	tool = ch->equipment[WIELD];

	/* check if player wields a suitable weapon */
	if (!tool && !IS_TRUSTED(ch))
	{
		send_to_char("Trying to do it with your bare hands? Whew...\r\n", ch);
		return;
	}
	if (!IS_TRUSTED(ch) && !isname("blade", tool->name) && !isname("dagger", tool->name) &&
	    !isname("knife", tool->name))
	{
		send_to_char("You need some kind of knife for carving!\r\n", ch);
		return;
	}
	/* what does player want to carve */
	piece = 0;
	for (which = 0; which < numCarvables; which++)
		if (!str_cmp(part, carve_part_name[which]))
		{
			piece = carve_part_flag[which];
			break;
		}
	if (!piece)
	{
		send_to_char("What piece of the body do you want to disect?\r\n", ch);
		return;
	}
	/* does the corpse still have that part? */
	if (corpse->value[1] & piece)
	{
		send_to_char("There is nothing left of that. Terrible.\r\n", ch);
		return;
	}
	/* throw a number */
	percent = carve_roll(live_rolls); /* 101 is a complete failure */

	/* if it is a complete failure, then then all parts are destroyed */
	if (percent == 101)
	{
		act("$n makes a bloody mess, horribly cutting up the $p. Gross!", TRUE, ch, corpse,
		    0, TO_ROOM);
		act("Urgh. Great, the $o is cut up beyond repair.", FALSE, ch, corpse, 0, TO_CHAR);
		/* set all bodyparts to missing */
		for (i = 0; i < numCarvables; i++)
			corpse->value[1] |= carve_part_flag[i];
		return;
	}
	/* no matter if fail or not, corpse hasn't got part anymore */
	corpse->value[1] |= piece;
	if (percent > GET_CHAR_SKILL(ch, SKILL_CARVE))
	{
		send_to_char("You butcher! It's all minced up now...\r\n", ch);
		notch_skill(ch, SKILL_CARVE, 5);
		return;
	}
	/* he's done it, let's load the prototype and finish it up */
	carve_weight[0] = corpse->weight / 10;
	carve_weight[1] = carve_weight[2] = carve_weight[3] = carve_weight[4] = carve_weight[5] =
		corpse->weight / 80;
	carve_weight[6] = carve_weight[8] = corpse->weight / 4;
	carve_weight[7] = corpse->weight / 7;

	notch_skill(ch, SKILL_CARVE, 2);
	carve = read_object(8, VIRTUAL);
	if (!carve)
	{
		send_to_char("Strange... please talk to a god about this.", ch);
		logit(LOG_OBJ, "Carve: Failed to load prototype 8.");
		return;
	}
	carve->str_mask = (STRUNG_KEYS | STRUNG_DESC1 | STRUNG_DESC2 | STRUNG_DESC3);

	/* find out the player name and race from the copses' names */
	half_chop(corpse->name, cname, buf);

	/* as keywords the part name and the player */
	checked_snprintf(buf, MAX_STRING_LENGTH, "%s %s", carve_part_name[which], cname);
	carve->name = str_dup(buf);

	/* Converts "The corpse of an orc is lying here." to e.g. "The skull..." */
	dscp = corpse->description + 11;
	snprintf(buf, MAX_STRING_LENGTH, "The %s %s", carve_part_name[which], dscp);
	if (piece == MISSING_EYES || piece == MISSING_EARS || piece == MISSING_BOWELS ||
	    piece == MISSING_ARMS || piece == MISSING_LEGS)
	{
		dscp = strstr(buf, " is ");
		if (dscp != NULL)
			snprintf(dscp, MAX_STRING_LENGTH, " are lying here.");
	}
	carve->description = str_dup(buf);

	/* same trick, this time for short_description */
	dscp = corpse->short_description + 11;
	snprintf(buf, MAX_STRING_LENGTH, "the %s %s", carve_part_name[which], dscp);
	carve->short_description = str_dup(buf);

	/* for action description just the part name */
	snprintf(buf, MAX_STRING_LENGTH, "%s", carve_part_name[which]);
	carve->action_description = str_dup(buf);

	/* now add the appropriate weigth */
	carve->weight = carve_weight[which];
	corpse->weight -= carve_weight[which];

	switch (piece)
	{
	case MISSING_SKULL:
		SET_BIT(carve->wear_flags, ITEM_ATTACH_BELT);
		carve->material = MAT_BONE;
		break;
	case MISSING_SCALP:
		SET_BIT(carve->wear_flags, ITEM_ATTACH_BELT);
		break;
	case MISSING_FACE:
		SET_BIT(carve->wear_flags, ITEM_ATTACH_BELT);
		break;
	case MISSING_EYES:
		break;
	case MISSING_EARS:
		break;
	case MISSING_TONGUE:
		break;
	case MISSING_BOWELS:
		SET_BIT(carve->wear_flags, ITEM_ATTACH_BELT);
		SET_BIT(carve->wear_flags, ITEM_WEAR_NECK);
		break;
	case MISSING_ARMS:
		carve->type = ITEM_WEAPON;
		carve->value[0] = 10;
		carve->value[1] = 1;
		carve->value[2] = 4;
		carve->value[3] = 7;
		carve->weight = 5;
		SET_BIT(carve->wear_flags, ITEM_WIELD);
		break;
	case MISSING_LEGS:
		carve->type = ITEM_WEAPON;
		carve->value[0] = 10;
		carve->value[1] = 1;
		carve->value[2] = 6;
		carve->value[3] = 7;
		carve->weight = 12;
		SET_BIT(carve->wear_flags, ITEM_WIELD);
		break;
	}

	/* player still has to get it, remains in corpse... */
	obj_to_obj(carve, corpse);

	act("$n successfully carved $p. Yuk!", TRUE, ch, carve, 0, TO_ROOM);
	send_to_char("There. Finally you pried it loose!\r\n", ch);

	return;
}

/* TASFALEN replace do_bind, do_unbind */

/*
   Can only bound player that are incapacitated or worst or major paralyse
*/

void do_bind(P_char ch, char *arg, int /*cmd*/)
{
	char name[MAX_INPUT_LENGTH];
	P_char t_char = NULL;

	if (!*arg)
	{
		send_to_char("Who do you want to bind?\r\n", ch);
		return;
	}

	if (IS_FIGHTING(ch))
	{
		send_to_char("Try again when someone isn't trying to kill you.\r\n", ch);
		return;
	}
	one_argument(arg, name);

	if (!(t_char = get_char_room_vis(ch, name)))
	{
		send_to_char("You don't see that person here.\r\n", ch);
		return;
	}

	if (ch == t_char)
	{
		send_to_char("Nice try!\r\n", ch);
		return;
	}
	if (IS_AFFECTED(t_char, AFF_BOUND))
	{
		send_to_char("They are already bound!\r\n", ch);
		return;
	}

	if (IS_NPC(t_char))
	{
		send_to_char("You cannot bind a mob.\r\n", ch);
		return;
	}

	if (IS_FIGHTING(t_char))
	{
		send_to_char("Cannot bind someone fighting.\r\n", ch);
		return;
	}

	if (IS_AFFECTED(ch, AFF_BOUND))
	{
		send_to_char("Try to unbind yourself first!\r\n", ch);
		return;
	}

	if (IS_AFFECTED(t_char, AFF_BOUND))
	{
		send_to_char("That person is already bound!\r\n", ch);
		return;
	}

	if ((GET_STAT(t_char) > STAT_INCAP) && (!IS_AFFECTED2(t_char, AFF2_MAJOR_PARALYSIS)) &&
	    !IS_AFFECTED(t_char, AFF_KNOCKED_OUT))
	{
		send_to_char("The person you want to bind is not in a proper position.\r\n", ch);
		return;
	}

	/*
	 * need both hands free for capture
	 */
	if ((ch->equipment[WEAR_SHIELD]) || (ch->equipment[PRIMARY_WEAPON]) ||
	    (ch->equipment[SECONDARY_WEAPON]))
	{
		send_to_char("You need both hands free to capture someone!\r\n", ch);
		return;
	}

	if (!ch->equipment[HOLD] || (!isname("rope", ch->equipment[HOLD]->name)))
	{
		send_to_char("You need to be holding rope to bind somebody.\r\n", ch);
		return;
	}

	SET_BIT(t_char->specials.affected_by, AFF_BOUND);
	act("$n ties $N up.", TRUE, ch, 0, t_char, TO_NOTVICT);
	act("You tie $N up.", TRUE, ch, 0, t_char, TO_CHAR);
	act("$n ties you up.", TRUE, ch, 0, t_char, TO_VICT);

	if (!IS_AFFECTED(t_char, AFF_KNOCKED_OUT))
		send_to_char("You're now bound and cannot move.\r\n", t_char);

	extract_obj(unequip_char(ch, HOLD), TRUE); // Arti rope?

	CharWait(ch, 2 * PULSE_VIOLENCE);

	return;
}

void do_unbind(P_char ch, char *arg, int /*cmd*/)
{
	char name[MAX_INPUT_LENGTH];
	P_char t_char = NULL;
	::byte percent;

	if (!*arg)
	{
		send_to_char("Who do you want to unbind?\r\n", ch);
		return;
	}

	one_argument(arg, name);

	if (!(t_char = get_char_room_vis(ch, name)))
	{
		send_to_char("You don't see that person here.\r\n", ch);
		return;
	}

	if (IS_NPC(t_char))
	{
		send_to_char("You cannot unbind a mob.\r\n", ch);
		return;
	}

	if (!IS_AFFECTED(t_char, AFF_BOUND))
	{
		if (ch == t_char)
			send_to_char("You're free as a bird!\r\n", ch);
		else
			send_to_char("That person is not bind!\r\n", ch);
		return;
	}

	percent = number(1, 101);

	if (ch == t_char)
	{
		if (IS_THIEF(ch))
		{
			if (percent <= (10 + (GET_LEVEL(ch) / 3)))
			{
				send_to_char("You use your skill to break free.\r\n", ch);
				act("$n twists $s body and breaks free from $s binding.", TRUE, ch,
				    0, 0, TO_ROOM);
			}
			else
			{
				send_to_char(
					"You try to use your skill to break free, but fail.\r\n",
					ch);
				act("$n tries to break free from $s bindings, but ends up tightening them more.",
				    TRUE, ch, 0, 0, TO_ROOM);
				CharWait(ch, 3 * PULSE_VIOLENCE);
				return;
			}
		}
		else
		{
			if (percent <= (str_app[STAT_INDEX(GET_C_STR(ch))].todam + 10))
			{
				send_to_char("You use your brute strength to break free.\r\n", ch);
				act("$n screws $s face in concentration, breaking free from $s bindings.",
				    TRUE, ch, 0, 0, TO_ROOM);
			}
			else
			{
				send_to_char(
					"You try to use your strength to break free, but fail.\r\n",
					ch);
				act("$n's face becomes red as $e tries to free $mself.", TRUE, ch,
				    0, 0, TO_ROOM);
				CharWait(ch, 2 * PULSE_VIOLENCE);
				return;
			}
		}
	}
	else
	{
		if (IS_AFFECTED(ch, AFF_BOUND))
		{
			send_to_char("You try, but fail.\r\n", ch);
			return;
		}

		act("$n removes $N's bindings.", FALSE, ch, 0, t_char, TO_NOTVICT);
		act("$n removes your bindings.", FALSE, ch, 0, t_char, TO_VICT);

		CharWait(t_char, 2 * PULSE_VIOLENCE);
	}

	if (auto *entangle = get_spell_from_char(t_char, SPELL_ENTANGLE);
	    entangle && IS_SET(entangle->bitvector, AFF_BOUND))
		affect_remove(t_char, entangle);
	REMOVE_BIT(t_char->specials.affected_by, AFF_BOUND);
	send_to_char("You're now free of your bindings.\r\n", t_char);
	CharWait(ch, 1 * PULSE_VIOLENCE);

	return;
}

void capture(P_char ch, P_char victim)
{
	int percent, ch_chance;

	if (!SanityCheck(ch, "capture"))
		return;

	if ((IS_PC(ch) && (GET_CHAR_SKILL(ch, SKILL_CAPTURE) == 0)) ||
	    (IS_NPC(ch) && !GET_CLASS(ch, CLASS_MERCENARY)))
	{
		send_to_char("You don't know how to capture.\r\n", ch);
		return;
	}
	if (!victim)
	{
		send_to_char("Capture who?\r\n", ch);
		return;
	}
	if (!training_dummy_capture_target_allowed(victim))
	{
		send_to_char("The training dummy cannot be captured.\r\n", ch);
		return;
	}
	if (IS_NPC(victim))
	{
		send_to_char("You can't capture mobs.\r\n", ch);
		return;
	}

	if (!on_front_line(ch) || !on_front_line(victim))
	{
		send_to_char("You can't reach them!\r\n", ch);
		return;
	}

	if (IS_NPC(ch) && IS_PC(victim))
	{
		send_to_char("Nice try.\r\n", ch);
		return;
	}
	if (IS_AFFECTED(ch, AFF_BOUND))
	{
		send_to_char("Try to unbind yourself first!\r\n", ch);
		return;
	}
	if (!HAS_FOOTING(ch))
	{
		send_to_char("You have no footing here!\r\n", ch);
		return;
	}
	if (!CanDoFightMove(ch, victim))
		return;

	/*
	 * need both hands free for capture
	 */
	if ((ch->equipment[WEAR_SHIELD]) || (ch->equipment[PRIMARY_WEAPON]) ||
	    (ch->equipment[SECONDARY_WEAPON]))
	{
		send_to_char("You need both hands free to capture someone!\r\n", ch);
		return;
	}

	if (!ch->equipment[HOLD] || (!isname("rope", ch->equipment[HOLD]->name)))
	{
		send_to_char("You need to be holding rope to bind somebody.\r\n", ch);
		return;
	}

	if (IS_FIGHTING(ch) && (GET_OPPONENT(ch) != victim))
	{
		send_to_char("You're WAY too busy to even attempt to capture someone else.\r\n",
			     ch);
		return;
	}

	if (IS_AFFECTED(victim, AFF_BOUND))
	{
		send_to_char("That person is bind enought already, c'mon now freak!!!\r\n", ch);
		return;
	}
	/*
	 * for mobs too big and small
	 */
	if (GET_RACE(victim) == RACE_GHOST)
	{
		act("Your attempt to grab $N fails as you simply pass through $M.", FALSE, ch, 0,
		    victim, TO_CHAR);
		act("$n makes a valiant attempt to grab $N, but simply falls through $M.", FALSE,
		    ch, 0, victim, TO_CHAR);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		return;
	}
	if (GET_RACE(victim) == RACE_A_ELEMENTAL)
	{
		act("&+WYour attempt to grab $N fails as it blows you on your ass!", FALSE, ch, 0,
		    victim, TO_CHAR);
		act("&+W$n makes a valiant attempt to grab $N, but gets blown on $s ass!", FALSE,
		    ch, 0, victim, TO_CHAR);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		return;
	}
	if (GET_RACE(victim) == RACE_E_ELEMENTAL)
	{
		act("&+WYour attempt to grab $N feels like you just hit a brick wall!", FALSE, ch,
		    0, victim, TO_CHAR);
		act("&+W$n just fell flat on $s ass when $e tried to grab $N!", FALSE, ch, 0,
		    victim, TO_CHAR);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		return;
	}
	if (GET_RACE(victim) == RACE_F_ELEMENTAL)
	{
		act("&+WYour attempt to grab $N almost burns you to a crisp!", FALSE, ch, 0, victim,
		    TO_CHAR);
		act("&+W$n tries to grab $N, but falls right through $M and onto $s ass!", FALSE,
		    ch, 0, victim, TO_CHAR);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		return;
	}
	if (IS_WATERFORM(victim))
	{
		act("&+WYou almost drown in your attempt to grab $M!", FALSE, ch, 0, victim,
		    TO_CHAR);
		act("$n almost drowns as $e passes right through $N!", FALSE, ch, 0, victim,
		    TO_CHAR);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		return;
	}

	if (GET_ALT_SIZE(victim) > GET_ALT_SIZE(ch))
	{
		act("$n fails miserably in $s attempt to grab $N's massive form.", FALSE, ch, 0,
		    victim, TO_ROOM);
		act("You simply cannot get a grab of $N's massive form.", FALSE, ch, 0, victim,
		    TO_CHAR);
		return;
	}

	if (GET_ALT_SIZE(victim) < GET_ALT_SIZE(ch) - 1)
	{
		act("$n nearly topples over $mself as $e tries to grab $N.", FALSE, ch, 0, victim,
		    TO_ROOM);
		send_to_char("Capturing creatures of this minute size is hopeless at best.\r\n",
			     ch);
		return;
	}

	/*
	 * Get here iff. can capture victim
	 */

	percent = number(1, 101); /*
	                           * 101% is a complete failure
	                           */

	if (IS_NPC(ch))
		ch_chance = BOUNDED(5, GET_LEVEL(ch) << 1, 90);
	else
		ch_chance = BOUNDED(5, GET_CHAR_SKILL(ch, SKILL_CAPTURE), 90);

	/* capturing someone on the ground is a bit easier */

	ch_chance += ((GET_POS(victim) == POS_PRONE)	? 15 :
		      (GET_POS(victim) != POS_STANDING) ? 10 :
							  0);

	/*
	 * -20% for every level the guy is above you
	 */

	if (GET_LEVEL(victim) > GET_LEVEL(ch))
		ch_chance -= (GET_LEVEL(victim) - GET_LEVEL(ch)) * 20;

	/*
	 * let's take agility and dexterity into account, too
	 */

	if (GET_C_AGI(ch) - GET_C_AGI(victim))
		ch_chance += ((GET_C_AGI(ch) - GET_C_AGI(victim)) / 3);

	if (GET_C_DEX(ch) - GET_C_DEX(victim))
		ch_chance += ((GET_C_DEX(ch) - GET_C_DEX(victim)) / 5);

	if (GET_C_LUK(ch) - GET_C_LUK(victim))
	{
		ch_chance += ((GET_C_LUK(ch) - GET_C_LUK(victim)) / 5);
	}

	ch_chance = BOUNDED(1, ch_chance, 85); /*
	                                        * always at least 15% chance to
	                                        * fail
	                                        */

	/*
	 * final check to smarten mobs up a little, if odds are too low don't
	 * try very often.  JAB
	 */

	if (IS_NPC(ch) && (ch_chance < 20))
		if (number(1, 25) > ch_chance)
			return;

	if ((percent > ch_chance) || IS_TRUSTED(victim))
	{
		if (!IS_TRUSTED(victim) && !number(0, 3))
			notch_skill(ch, SKILL_CAPTURE, 3.33);

		SET_POS(ch, POS_PRONE + GET_STAT(ch));

		act("You try to grab $N, but find yourself face on the ground!", FALSE, ch, 0,
		    victim, TO_CHAR);
		act("You avoid $n's grab as $e falls to the ground!", FALSE, ch, 0, victim,
		    TO_VICT);
		act("$n falls face first on the ground as $N avoids $m.", FALSE, ch, 0, victim,
		    TO_NOTVICT);

		notch_skill(ch, SKILL_CAPTURE, .67);

		CharWait(ch, PULSE_VIOLENCE * 5);

		if ((GET_STAT(victim) > STAT_INCAP) && !IS_FIGHTING(ch))
			set_fighting(ch, victim);
	}
	else
	{
		/*
		 * yup, two CharWaits(), this first one prevents all the silly
		 * bash/flee things, can add more below if needed. JAB
		 */
		CharWait(ch, PULSE_VIOLENCE * 5);
		CharWait(victim, PULSE_VIOLENCE * 1);

		stop_fighting(ch);
		stop_fighting(victim);

		SET_BIT(victim->specials.affected_by, AFF_BOUND);
		SET_POS(victim, POS_PRONE + GET_STAT(victim));

		act("You knock $N to the ground and bind $M up!", FALSE, ch, 0, victim, TO_CHAR);
		act("You are knocked to the ground and bound up by $n!", FALSE, ch, 0, victim,
		    TO_VICT);
		act("$N is knocked to the ground and bound up by $n!", FALSE, ch, 0, victim,
		    TO_NOTVICT);

		/* get rid of their rope.. */
		extract_obj(unequip_char(ch, HOLD), TRUE); // Arti rope?

		notch_skill(ch, SKILL_CAPTURE, 2.22);

		return;
	}
#ifdef REALTIME_COMBAT
	if (GET_OPPONENT(ch) && !ch->specials.combat)
	{
		stop_fighting(ch);
		set_fighting(ch, victim);
	}
#endif
}

void do_capture(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL;

	SanityCheck(ch, "do_capture");

	victim = ParseTarget(ch, argument);

	capture(ch, victim);
}

// 101 makes a wild estimate; otherwise a roll up to your rating makes a close one.
static int appraise_roll(const Rolls &rolls)
{
	return rolls.number(1, 101);
}

// A wild estimate reads high unless this rolls 0.
static int appraise_wild_side_roll(const Rolls &rolls)
{
	return rolls.number(0, 1);
}

static int appraise_wild_multiple(const Rolls &rolls)
{
	return rolls.number(1, 3);
}

static int appraise_wild_divisor(const Rolls &rolls)
{
	return rolls.number(2, 4);
}

// A miss reads high unless this comes out zero.
static int appraise_miss_side_roll(const Rolls &rolls)
{
	return rolls.number(0, 2);
}

static int appraise_miss_high_divisor(const Rolls &rolls)
{
	return rolls.number(1, 15);
}

static int appraise_miss_low_divisor(const Rolls &rolls)
{
	return rolls.number(2, 15);
}

static int appraise_close_divisor(const Rolls &rolls)
{
	return rolls.number(80, 120);
}

static int appraise_lag()
{
	return 2 * PULSE_VIOLENCE;
}

std::string appraise_facts(P_char ch)
{
	const int rating = GET_CHAR_SKILL(ch, SKILL_APPRAISE);
	const int high_sides = appraise_miss_side_roll(highest_rolls);
	return fact("Chance of a close estimate", chance_under(rating + 1, 1, 101)) +
	       "  A close estimate is off by 1/" +
	       std::to_string(appraise_close_divisor(highest_rolls)) + " to 1/" +
	       std::to_string(appraise_close_divisor(lowest_rolls)) +
	       " of the value, either way.\n" +
	       fact("A miss reads high",
		    std::to_string(high_sides) + " in " + std::to_string(high_sides + 1) +
			    ", by up to 1/" +
			    std::to_string(appraise_miss_high_divisor(lowest_rolls)) +
			    " of the value") +
	       fact("Otherwise it reads low",
		    "by up to 1/" + std::to_string(appraise_miss_low_divisor(lowest_rolls))) +
	       fact("Chance of a wild estimate", one_in(appraise_roll)) + "    (" +
	       one_in(appraise_wild_side_roll) + " high by up to " +
	       std::to_string(appraise_wild_multiple(highest_rolls)) +
	       " times the value, else low by up to 1/" +
	       std::to_string(appraise_wild_divisor(lowest_rolls)) + ")\n" +
	       fact("Your lag", seconds(appraise_lag()));
}

void do_appraise(P_char ch, char *argument, int /*cmd*/)
{
	P_obj temp = NULL;
	char buf[MAX_STRING_LENGTH];
	int percent;
	int estimate_value;

	SanityCheck(ch, "do_appraise");

	one_argument(argument, buf);

	if (IS_AFFECTED(ch, AFF_BOUND))
	{
		send_to_char("Try to unbind yourself first!\r\n", ch);
		return;
	}

	if (!(temp = get_obj_in_list_vis(ch, buf, ch->carrying)))
	{
		act("You can't find it!", FALSE, ch, 0, 0, TO_CHAR);
		return;
	}

	act("You examine $p closely!", FALSE, ch, temp, 0, TO_CHAR);
	//    return;

	act("$n examines $p closely!", FALSE, ch, temp, 0, TO_ROOM);

	estimate_value = temp->cost;

	/* throw a number */
	percent = appraise_roll(live_rolls); /* 101 is a complete failure */

	/* if it is a complete failure, then the appraise is way off */
	if (percent == 101)
	{
		if ((appraise_wild_side_roll(live_rolls)))
			estimate_value += (estimate_value * (appraise_wild_multiple(live_rolls)));
		else
			estimate_value -= (estimate_value / (appraise_wild_divisor(live_rolls)));
	}
	else
	{
		if (percent > GET_CHAR_SKILL(ch, SKILL_APPRAISE))
		{
			notch_skill(ch, SKILL_APPRAISE, 5);
			if ((appraise_miss_side_roll(live_rolls)))
				estimate_value +=
					(estimate_value / (appraise_miss_high_divisor(live_rolls)));
			else
				estimate_value -=
					(estimate_value / (appraise_miss_low_divisor(live_rolls)));
		}
		else
		{
			if ((number(0, 1)))
				estimate_value +=
					(estimate_value / (appraise_close_divisor(live_rolls)));
			else
				estimate_value -=
					(estimate_value / (appraise_close_divisor(live_rolls)));
		}
	}

	if (estimate_value <= 0)
		snprintf(buf, MAX_STRING_LENGTH, "This look like a piece of crap.\r\n");
	else
		snprintf(buf, MAX_STRING_LENGTH, "You estimate its value to: %s\r\n",
			 coin_stringv(estimate_value));
	send_to_char(buf, ch);
	CharWait(ch, appraise_lag());

	return;
}

void do_chi(P_char ch, char *argument, int /*cmd*/)
{
	char arg[512];
	int skl_level;
	struct affected_type af;

	if (IS_NPC(ch))
		return;

	if (!GET_SPEC(ch, CLASS_MONK, SPEC_CHIMONK))
	{
		send_to_char("You lack the mental focus to perform this task.\n\r", ch);
		return;
	}

	if (IS_AFFECTED2(ch, AFF2_MINOR_PARALYSIS) || IS_AFFECTED2(ch, AFF2_MAJOR_PARALYSIS))
	{
		send_to_char("Your nervous system is to pre-occupied at the moment.\n\r", ch);
		return;
	}

	if (IS_RIDING(ch))
	{
		send_to_char("You cannot conventrate enough while mounted.\n\r", ch);
		return;
	}

	one_argument(argument, arg);

	if (!*arg)
	{
		send_to_char(
			"You can focus your chi into the following enchantments:\n\rDisplacement\n\rReconstruction\n\rSight\n\r",
			ch);
		return;
	}

	skl_level = GET_CHAR_SKILL(ch, SKILL_CHI);

	if ((number(0, 101) - skl_level) > 0)
	{
		act("You falter as you try to summon your inner power...", FALSE, ch, 0, 0,
		    TO_CHAR);
		act("$n's face looks frustrated as $e is unable to vanquish $s inner turmoil.",
		    TRUE, ch, 0, 0, TO_ROOM);
		notch_skill(ch, SKILL_CHI, 10);
		CharWait(ch, PULSE_VIOLENCE * 3);
		return;
	}
	else
	{
		send_to_char("You focus your thoughts, harnessing your inner power.\n\r", ch);
		if (is_abbrev(arg, "displacement"))
		{
			if (GET_POS(ch) < POS_STANDING)
			{
				send_to_char("You cannot concentrate while on the ground.\n\r", ch);
				return;
			}
			add_event(displacement_event, 2 * PULSE_VIOLENCE, ch, NULL, NULL, 0, NULL,
				  0);
			// AddEvent(EVENT_CHAR_EXECUTE, 2 * PULSE_VIOLENCE, TRUE, ch, displacement);
			CharWait(ch, PULSE_VIOLENCE * 2);
		}
		else if (is_abbrev(arg, "reconstruction"))
		{
			if (0 /*IS_AFFECTED5(ch, AFF5_LOTUS) */)
			{
				skl_level = 0;
				skl_level = GET_CHAR_SKILL(ch, SKILL_RECONSTRUCTION);
				if ((number(0, 101) - skl_level) > 0)
				{
					send_to_char("You are unable to focus your thoughts.\n\r",
						     ch);
					return;
				}
				send_to_char(
					"You turn your thoughts inward to your broken flesh.\n\rUsing your inner chi you cause your body to mend at an accelerated rate.\n\r",
					ch);
				act("&+cA strong sense of peace and calm emanates from $n&n.\n\r",
				    FALSE, ch, 0, 0, TO_ROOM);
				memset(&af, 0, sizeof(af));
				af.type = SKILL_RECONSTRUCTION;
				af.flags = AFFTYPE_SHORT;
				af.duration = 20 * PULSE_VIOLENCE;
				af.location = APPLY_HIT_REG;
				af.modifier = 5 * GET_CHAR_SKILL(ch, SKILL_RECONSTRUCTION);
				affect_to_char(ch, &af);
				notch_skill(ch, SKILL_RECONSTRUCTION, 10);
				CharWait(ch, PULSE_VIOLENCE * 2);
			}
			else
			{
				send_to_char("You must clear your mind first.\n\r", ch);
				return;
			}
		}
		else if (is_abbrev(arg, "sight"))
		{
			if (0 /*IS_AFFECTED5(ch, AFF5_LOTUS) */)
			{
				if (affected_by_spell(ch, SKILL_SIGHT))
					return;
				skl_level = 0;
				skl_level = GET_CHAR_SKILL(ch, SKILL_SIGHT);
				if ((number(0, 101) - skl_level) > 0)
				{
					send_to_char("You are unable to focus your thoughts.\n\r",
						     ch);
					SET_BIT(ch->specials.act2, PLR2_SPEC_TIMER);
					return;
				}
				send_to_char(
					"You expand your mind uncloaking the mysteries of life.\n\r",
					ch);
				act("$n's eyes start to glow with a pale blue light.", FALSE, ch, 0,
				    0, TO_ROOM);
				memset(&af, 0, sizeof(af));
				af.type = SKILL_SIGHT;
				af.duration = (GET_C_WIS(ch) / 10);
				af.bitvector = AFF_DETECT_INVISIBLE | AFF_SENSE_LIFE;
				af.bitvector2 = AFF2_DETECT_MAGIC;
				affect_to_char(ch, &af);
				notch_skill(ch, SKILL_SIGHT, 10);
				CharWait(ch, PULSE_VIOLENCE * 2);
			}
			else
			{
				send_to_char("You must clear your mind first.\n\r", ch);
				return;
			}
		}
		else
		{
			send_to_char("That is not an option.\n\r", ch);
			return;
		}
		notch_skill(ch, SKILL_CHI, 10);
	}
}

void displacement_event(P_char ch, P_char /*victim*/, P_obj /*obj*/, void * /*data*/)
{
	int skl_level;

	if (IS_NPC(ch))
		return;

	if (!GET_SPEC(ch, CLASS_MONK, SPEC_CHIMONK))
		return;

	if (GET_POS(ch) < POS_STANDING)
	{
		send_to_char("You cannot focus your mind while on the ground.\n\r", ch);
		return;
	}

	if (IS_AFFECTED2(ch, AFF2_MINOR_PARALYSIS) || IS_AFFECTED2(ch, AFF2_MAJOR_PARALYSIS))
	{
		send_to_char("Your nervous system is to pre-occupied at the moment.\n\r", ch);
		return;
	}

	if (IS_RIDING(ch))
	{
		send_to_char("You cannot concentrate enough while mounted.\n\r", ch);
		return;
	}

	skl_level = GET_CHAR_SKILL(ch, SKILL_DISPLACEMENT);

	if ((number(1, 101) - skl_level) > 0)
	{
		send_to_char("You are unable to focus your thoughts.\n\r", ch);
		return;
	}
	spell_teleport(GET_LEVEL(ch), ch, 0, 0, ch, 0);
	CharWait(ch, PULSE_VIOLENCE * 3);
	notch_skill(ch, SKILL_DISPLACEMENT, 10);
}

void do_lotus(P_char ch, char * /*argument*/, int /*cmd*/)
{
	if (IS_NPC(ch))
		return;

	if (!GET_SPEC(ch, CLASS_MONK, SPEC_CHIMONK))
	{
		send_to_char("You can not control your lotus chi!\n\r", ch);
		return;
	}

	if (IS_FIGHTING(ch))
	{
		send_to_char("That would be un-wise!\n\r", ch);
		return;
	}

	if (IS_AFFECTED2(ch, AFF2_MINOR_PARALYSIS) || IS_AFFECTED2(ch, AFF2_MAJOR_PARALYSIS))
	{
		send_to_char("Your nervous system is to pre-occupied at the moment.\n\r", ch);
		return;
	}

	if (0 /*IS_AFFECTED5(ch, AFF5_LOTUS) */)
	{
		send_to_char("You are already in the lotus position.\n\r", ch);
		return;
	}

	if (GET_POS(ch) != POS_SITTING)
		do_sit(ch, writable_arg(""), CMD_LOTUS);

	send_to_char("You bend your legs with your hands on your knees.\n\r", ch);
	act("$n bends his legs and rests his hands on his knees.", FALSE, ch, 0, 0, TO_ROOM);

	add_event(lotus_event, 2 * PULSE_VIOLENCE, ch, NULL, NULL, 0, NULL, 0);
	// AddEvent(EVENT_CHAR_EXECUTE, PULSE_VIOLENCE * 2, TRUE, ch, lotus);
	CharWait(ch, PULSE_VIOLENCE);
}

void lotus_event(P_char ch, P_char /*victim*/, P_obj /*obj*/, void * /*data*/)
{
	int skl_level;

	if (IS_NPC(ch))
		return;

	if (!GET_SPEC(ch, CLASS_MONK, SPEC_CHIMONK))
		return;

	if (IS_AFFECTED2(ch, AFF2_MINOR_PARALYSIS) || IS_AFFECTED2(ch, AFF2_MAJOR_PARALYSIS))
	{
		send_to_char("Your nervous system is to pre-occupied at the moment.\n\r", ch);
		return;
	}

	if (IS_FIGHTING(ch))
		return;

	if (IS_RIDING(ch))
	{
		send_to_char("You cannot concentrate while riding.\n\r", ch);
		return;
	}

	if (GET_POS(ch) != POS_SITTING)
	{
		send_to_char("You must be sitting to concetrate enough.\n\r", ch);
		return;
	}

	skl_level = GET_CHAR_SKILL(ch, SKILL_LOTUS);

	if ((number(0, 101) - skl_level) < 0)
	{
		act("You slip beyond your conscious self and become one with the universe.", FALSE,
		    ch, 0, 0, TO_CHAR);
		act("$n's face goes blank as $e enters a trance-like state.", FALSE, ch, 0, 0,
		    TO_ROOM);

		/*      if(!IS_AFFECTED5(ch, AFF5_LOTUS))
		         SET_BIT(ch->specials.affected_by5, AFF5_LOTUS);*/
		CharWait(ch, PULSE_VIOLENCE);
		notch_skill(ch, SKILL_LOTUS, 10);
		return;
	}

	send_to_char("You fail in your attempt to clear your mind of thoughts.\n\r", ch);
	CharWait(ch, PULSE_VIOLENCE * 2);
}

void do_true_strike(P_char ch, char *argument, int /*cmd*/)
{
	P_char vict = NULL;
	int skl_lvl = 0;
	int x;

	if (!GET_SPEC(ch, CLASS_MONK, SPEC_CHIMONK) || IS_NPC(ch))
	{
		send_to_char("You lack the mental focus to perform this task\n\r", ch);
		return;
	}

	skl_lvl = GET_CHAR_SKILL(ch, SKILL_TRUE_STRIKE);

	vict = ParseTarget(ch, argument);
	if (!vict)
	{
		send_to_char(
			"A true martial artist would know his opponent for certain before striking.\n\r",
			ch);
		return;
	}

	vict = guard_check(ch, vict);
	if (!vict)
	{
		send_to_char(
			"A true martial artist would know his opponent for certain before striking.\n\r",
			ch);
		return;
	}

	if (!on_front_line(ch) || !on_front_line(vict))
	{
		send_to_char("You can't reach them!\n\r", ch);
		return;
	}

	if (IS_ROOM(ch->in_room, ROOM_SINGLE_FILE) && (!AdjacentInRoom(ch, vict)))
	{
		send_to_char("Your target is to far away for your punch to reach.\n\r", ch);
		return;
	}

	if (GET_ALT_SIZE(vict) < (GET_ALT_SIZE(ch) - 1) ||
	    (GET_ALT_SIZE(vict) > (GET_ALT_SIZE(ch) + 1)))
	{
		send_to_char("Your punch would not be very effective on an opponent that size.\n\r",
			     ch);
		return;
	}

	if (CHAR_IN_SAFE_ROOM(ch))
	{
		send_to_char(
			"You feel ashamed to try to disrupt the tranquility of this place.\n\r",
			ch);
		return;
	}

	if (!CanDoFightMove(ch, vict))
		return;

	if (number(1, 101) > skl_lvl)
	{
		damage(ch, vict, 0, SKILL_TRUE_STRIKE);
		send_to_char(
			"You feel like a fool as you swing and completely miss your target.\n\r",
			ch);
		notch_skill(ch, SKILL_TRUE_STRIKE, 10);
	}
	else
	{
		send_to_char("You leap forward and deliver three strikes just below the ribs.\n\r",
			     ch);
		act("With lightning speed $n leaps forward and strikes $N three times below the ribs.",
		    FALSE, ch, 0, vict, TO_NOTVICT);
		act("With lightning speed $n leaps forward and strikes you three times just below the ribs.",
		    FALSE, ch, 0, vict, TO_VICT);

		if (damage(ch, vict, (40 + dice(1, 12)) * 3, SKILL_TRUE_STRIKE))
			return;

		x = number(1, 100);

		if (x <= 20)
		{
			send_to_char("You fall to your knees screaming with agony!\n\r", vict);
			act("$n falls to his knees howling from the pain!", FALSE, vict, 0, 0,
			    TO_ROOM);
			SET_POS(vict, POS_KNEELING + GET_STAT(ch));
			CharWait(vict, PULSE_VIOLENCE);
		}
		else if (x <= 40)
		{
			send_to_char(
				"The pain is to much to bear and totally numbs your senses.\n\r",
				vict);
			act("$n grimaces with pain.", FALSE, vict, 0, 0, TO_ROOM);
			Stun(vict, ch, PULSE_VIOLENCE * 2, FALSE);
		}
		else if (x <= 60)
		{
			send_to_char("You feel like your nervous system is on fire!\n\r", vict);
			send_to_char("You feel as tho you hit something vital!\n\r", ch);
			if (damage(ch, vict, (10 + dice(1, 12)) * 3, SKILL_TRUE_STRIKE) &&
			    !char_in_list(ch))
				return;
		}
		notch_skill(ch, SKILL_TRUE_STRIKE, 10);
	}
	CharWait(ch, 2 * PULSE_VIOLENCE);
}

// Above each level, chi purge cures one more thing.
static int chi_purge_poison_level()
{
	return 2;
}

static int chi_purge_curse_level()
{
	return 9;
}

static int chi_purge_blind_level()
{
	return 29;
}

static int chi_purge_wither_level()
{
	return 50;
}

static int chi_purge_disease_level()
{
	return 55;
}

static int chi_purge_failed_lag()
{
	return 2 * PULSE_VIOLENCE;
}

static int chi_purge_rest()
{
	return WAIT_SEC * get_property("timer.secs.monkChipurge", 25);
}

std::string chi_purge_facts(P_char ch)
{
	if (!GET_CLASS(ch, CLASS_MONK) && !IS_TRUSTED(ch))
		return "  Only monks can chant chi purge.\n";
	const int rating = GET_CHAR_SKILL(ch, SKILL_CHI_PURGE);
	if (rating < 1)
		return "  You need this skill to chant chi purge.\n";
	const struct
	{
		int level;
		const char *name;
	} cures[] = { { chi_purge_poison_level(), "poison" },
		      { chi_purge_curse_level(), "curses" },
		      { chi_purge_blind_level(), "blindness" },
		      { chi_purge_wither_level(), "withering" },
		      { chi_purge_disease_level(), "disease" } };
	std::string known, later;
	for (const auto &cure : cures)
	{
		if (GET_LEVEL(ch) > cure.level)
			known += (known.empty() ? "" : ", ") + std::string(cure.name);
		else
			later += fact("Above level " + std::to_string(cure.level), cure.name);
	}
	return fact("Chance", chance_under(rating + 1, 1, 100)) +
	       fact("Cures on you", known.empty() ? "nothing yet" : known) + later +
	       fact("Before you can chant it again, if it works",
		    IS_TRUSTED(ch) ? "no wait, as an immortal" : seconds(chi_purge_rest())) +
	       fact("Your lag if you fail", seconds(chi_purge_failed_lag())) + chant_note();
}

void chant_chi_purge(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		     P_obj /*obj*/)
{
	int poison, curse, wither, disease, blind;

	poison = FALSE;
	curse = FALSE;
	wither = FALSE;
	disease = FALSE;
	blind = FALSE;

	if (GET_LEVEL(ch) > chi_purge_poison_level())
		poison = TRUE;
	if (GET_LEVEL(ch) > chi_purge_curse_level())
		curse = TRUE;
	if (GET_LEVEL(ch) > chi_purge_blind_level())
		blind = TRUE;
	if (GET_LEVEL(ch) > chi_purge_wither_level())
		wither = TRUE;
	if (GET_LEVEL(ch) > chi_purge_disease_level())
		disease = TRUE;

	if (number(1, 100) > GET_CHAR_SKILL(ch, SKILL_CHI_PURGE) &&
	    !notch_skill(ch, SKILL_CHI_PURGE, 10))
	{
		send_to_char("You forgot the words for the chant.\r\n", ch);
		notch_skill(ch, SKILL_CHI_PURGE, 15);
		CharWait(ch, chi_purge_failed_lag());
		return;
	}

	if (!affect_timer(ch, chi_purge_rest(), SKILL_CHI_PURGE))
	{
		send_to_char("Yer not in proper mood for that right now!\r\n", ch);
		return;
	}

	if (poison && (affected_by_spell(ch, SPELL_POISON) ||
		       IS_SET(victim->specials.affected_by2, AFF2_POISONED)))
	{
		act("&+GYou close your eyes, willing the poison in your bloodstream to dissipate.&n",
		    FALSE, ch, 0, victim, TO_CHAR);
		poison_common_remove(victim);
	}

	if (curse && affected_by_spell(ch, SPELL_CURSE))
	{
		act("Harnessing your chi, you purify your mind and body of the curse.", FALSE, ch,
		    0, victim, TO_CHAR);
		affect_from_char(victim, SPELL_CURSE);
	}

	if (curse)
	{
		spell_remove_curse(level, ch, 0, 0, ch, NULL);
	}

	if (wither && affected_by_spell(ch, SPELL_WITHER))
	{
		act("You focus inward, causing your withered limbs to return to normal.", FALSE, ch,
		    0, victim, TO_CHAR);
		affect_from_char(victim, SPELL_WITHER);
	}

	if (disease && affected_by_spell(ch, SPELL_DISEASE))
	{
		act("&+rYou kneel, chanting, and begin to feel the effects of the disease fade away.",
		    FALSE, ch, 0, victim, TO_CHAR);
		// affect_from_char(victim, SPELL_DISEASE);
	}

	if (disease)
	{
		spell_cure_disease(level, ch, 0, 0, ch, NULL);
	}

	if (blind && IS_AFFECTED(ch, AFF_BLIND))
	{
		act("&+WYou close your eyes, chanting in a low tone, and when you open them once more, your vision has returned.",
		    FALSE, ch, 0, victim, TO_CHAR);
		affect_from_char(victim, SPELL_BLINDNESS);
		if (IS_SET(victim->specials.affected_by, AFF_BLIND))
			REMOVE_BIT(victim->specials.affected_by, AFF_BLIND);
	}

	return;
}
