/* ***************************************************************************
 *  File: psionics.c                                         Part of Sojourn *
 *  Usage: procedures to create spell affects                                *
 *  Copyright  1990, 1991 - see 'license.doc' for complete information.      *
 *  Copyright  1994, 1995 - Sojourn Systems Ltd.                             *
 *************************************************************************** */

#include "core/prototypes.h"
#include "item/named_set_effects.h"
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "core/utils.h"
#include <stdio.h>
#include <string.h>
#include <time.h>
#include "combat/damage.h"
#include "world/graph.h"
#include "world/map.h"
#include "magic/spells.h"
#include "world/vnum.obj.h"
#include "combat/training_dummy.h"
#include "abilities/abilities.h"

/* external variables */

extern P_char character_list;
extern P_char combat_list;
extern P_obj object_list;
extern P_room world;
extern P_index obj_index;
extern const char *apply_types[];
extern const char *command[];
extern const flagDef extra_bits[];
extern const char *item_types[];
extern const struct stat_data stat_factor[];
extern int avail_hometowns[][LAST_RACE + 1];
extern int guild_locations[][CLASS_COUNT + 1];
extern int hometown[];
extern const int top_of_world;
extern struct time_info_data time_info;
extern struct wis_app_type wis_app[];
extern struct zone_data *zone_table;
extern struct remember_data *remember_array[];
extern int cast_as_damage_area(P_char, void (*func)(int, P_char, char *, int, P_char, P_obj), int,
			       P_char, float, float);
extern bool has_skin_spell(P_char);
extern float tower_iron_will_share();
extern float energy_containment_share();
extern float biofeedback_melee_share();
extern int skin_spell_deduct();
extern float inertial_barrier_attack_share();
extern float combat_mind_attack_floor();
extern int combat_mind_to_hit();
extern int combat_mind_parry_skill(int level);
extern int combat_mind_parry_bonus(int level);
extern int combat_mind_second_attack_above();
extern int combat_mind_bare_hand_damage(const Rolls &rolls, P_char ch);
extern int combat_mind_quaff_chance(int chance);
extern int displacement_absorb_roll(const Rolls &rolls);
extern int displacement_takedown_chance(int level);
extern int displacement_takedown_roll(const Rolls &rolls);
extern int cannibalize_least_damage();
extern double cannibalize_mana(int dam, int level);

// #define POW_DIFF(att, def) (STAT_INDEX(GET_C_POW(def)) - STAT_INDEX(GET_C_POW(att)))

// already defined: char     buf[MAX_STRING_LENGTH];

void event_illithid_feeding(P_char ch, P_char victim, P_obj /*obj*/, void * /*data*/)
{
	if ((!ch) || (!victim) || (ch->in_room != victim->in_room))
	{
		if (ch)
			send_to_char("Alas, your victim doesn't seem to be around anymore.\r\n",
				     ch);
		return;
	}
	send_to_char("&+MYou suck the last bit of brain from your victim.\r\n", ch);
	send_to_char("&+MYou complete your feeding, feeling refreshed.\r\n", ch);
	act("$n releases $N&n, pulling $s tentacles out of $S ear.", TRUE, ch, 0, victim,
	    TO_NOTVICT);
	act("$n releases you, pulling $s tentacles out of your ear.", TRUE, ch, 0, victim, TO_VICT);
	if (GET_MANA(ch) < GET_MAX_MANA(ch))
		GET_MANA(ch) = GET_MAX_MANA(ch);
	GET_COND(ch, FULL) += 36;
	GET_COND(ch, THIRST) += 36;
	die(victim, ch);
	return;
}

void do_drain(P_char ch, char *arg, int /*cmd*/)
{
	P_char victim;

	if (GET_RACE(ch) != RACE_ILLITHID)
	{
		send_to_char("What a sicko. Go home.\r\n", ch);
		return;
	}

	if (!*arg)
	{
		send_to_char("Who?!?!\r\n", ch);
		return;
	}

	if (!(victim = get_char_room_vis(ch, arg)))
	{
		send_to_char("I don't believe they are here.\r\n", ch);
		return;
	}

	if (victim == ch)
	{
		send_to_char("Wouldn't that be exciting?\r\n", ch);
		return;
	}

	if (GET_STAT(victim) >= STAT_SLEEPING)
	{
		send_to_char("Prep your food first!\r\n", ch);
		return;
	}

	add_event(event_illithid_feeding, GET_LEVEL(victim) / 2, ch, victim, 0, 0, 0, 0);

	act("&+MYou grip your victim's head in your tentacles, sending one deep into $S brain.  The feeding begins!",
	    FALSE, ch, 0, victim, TO_CHAR);
	act("&+M$n grips $N&n&+M's head in $s tentacles, sending one deep into $S brain.", TRUE, ch,
	    0, victim, TO_NOTVICT);
	act("&+RA wave of pain grips your brain as $N begins to slowly suck it out through your ear.",
	    FALSE, ch, 0, victim, TO_VICT);
}

void event_githyanki_neckbite(P_char ch, P_char victim, P_obj /*obj*/, void * /*data*/)
{
	int get_mana = 0;

	if ((!victim) || (ch->in_room != victim->in_room))
	{
		send_to_char("Alas, your victim doesn't seem to be around anymore.\r\n", ch);
		return;
	}

	send_to_char("&+RYou suck the last bit of blood from your victim.\r\n", ch);
	act("$n&n removes $s teeth from $N&n's neck, leaving a bloodless corpse.", TRUE, ch, 0,
	    victim, TO_NOTVICT);
	act("$n&n removes $s teeth from your neck -- you feel terrible.", TRUE, ch, 0, victim,
	    TO_VICT);
	if (GET_HIT(ch) < GET_MAX_HIT(ch))
		GET_HIT(ch) += MIN(GET_LEVEL(victim) * 4, GET_MAX_HIT(ch) - GET_HIT(ch));

	if (GET_LEVEL(victim) < MAX(GET_LEVEL(ch) / 2, GET_LEVEL(ch) - 10))
	{
		get_mana = MIN(GET_LEVEL(victim) * 2, GET_MAX_MANA(ch) - GET_MANA(ch));
	}
	else
		get_mana = GET_MAX_MANA(ch) - GET_MANA(ch);

	GET_MANA(ch) += get_mana;

	if (GET_MANA(ch) < GET_MAX_MANA(ch))
	{
		send_to_char("&+RSadly, your victim had too weak lifeforce to fully feed you.\r\n",
			     ch);
	}

	die(victim, ch);
}

void do_gith_neckbite(P_char ch, char *arg, int /*cmd*/)
{
	P_char victim;

	if (GET_RACE(ch) != RACE_PVAMPIRE)
	{
		send_to_char("What a sicko. Go home.\r\n", ch);
		return;
	}

	if (!*arg)
	{
		send_to_char("Who?!?!\r\n", ch);
		return;
	}

	if (!(victim = get_char_room_vis(ch, arg)))
	{
		send_to_char("I don't believe they are here.\r\n", ch);
		return;
	}

	if (ch == victim)
	{
		send_to_char("Bite your own neck?\r\n", ch);
		return;
	}

	if (!IS_HUMANOID(victim))
	{
		send_to_char("You sure they have a neck to bite?\r\n", ch);
		return;
	}

	if ((GET_STAT(victim) >= STAT_SLEEPING))
	{
		send_to_char("Prep your food first!\r\n", ch);
		return;
	}

	add_event(event_githyanki_neckbite, 15, ch, victim, 0, 0, 0, 0);

	send_to_char(
		"&+RYou sink your teeth deeply into their neck, relishing in the feast that is just beginning..\r\n",
		ch);
	act("&+R$n&+R sinks $s teeth into $N&n&+R's neck, clearly relishing the experience.", TRUE,
	    ch, 0, victim, TO_NOTVICT);
	act("&+RA wave of pain runs through your entire body as $n&+R sinks $s teeth into your neck.",
	    FALSE, ch, 0, victim, TO_VICT);
}

void event_illithid_feeding2(P_char ch, P_char victim, P_obj /*obj*/, void * /*data*/)
{
	if ((!victim) || (ch->in_room != victim->in_room))
	{
		send_to_char("Alas, your victim doesn't seem to be around anymore.\r\n", ch);
		return;
	}

	send_to_char("&+GYou suck the last bit of free energy from your victim.\r\n", ch);
	send_to_char("&+GYou complete your feeding, feeling refreshed.\r\n", ch);
	act("&+G$n releases $N&+G, pulling $s tentacles out of $S ear.", TRUE, ch, 0, victim,
	    TO_NOTVICT);
	act("&+G$n releases you, pulling $s tentacles out of your ear.", TRUE, ch, 0, victim,
	    TO_VICT);
	if (GET_HIT(ch) < GET_MAX_HIT(ch))
		GET_HIT(ch) = GET_MAX_HIT(ch);

	die(victim, ch);
}

void do_absorbe(P_char ch, char *arg, int /*cmd*/)
{
	P_char victim;

	if (GET_RACE(ch) != RACE_ILLITHID)
	{
		send_to_char("What a sicko. Go home.\r\n", ch);
		return;
	}

	if (!*arg)
	{
		send_to_char("Who?!?!\r\n", ch);
		return;
	}

	if (!(victim = get_char_room_vis(ch, arg)))
	{
		send_to_char("I don't believe they are here.\r\n", ch);
		return;
	}

	if (victim == ch)
	{
		send_to_char(
			"You send a tentacle into your brain..  R.I.P. you are dead!  go away..\r\n",
			ch);
		return;
	}

	if ((GET_STAT(victim) >= STAT_SLEEPING))
	{
		send_to_char("Your victim must be held in place first.\r\n", ch);
		return;
	}

	add_event(event_illithid_feeding2, GET_LEVEL(victim) >> 1, ch, victim, 0, 0, 0, 0);

	act("&+GYou grip your victim's head in your tentacles, sending one deep into $S brain.  The feeding begins!",
	    FALSE, ch, 0, victim, TO_CHAR);
	act("&+G$n grips $N&+G's head in $s tentacles, sending one deep into $S brain.", TRUE, ch,
	    0, victim, TO_NOTVICT);
	act("&+RA wave of pain grips your brain, as $N begins to slowly suck it out through your ear.",
	    FALSE, ch, 0, victim, TO_VICT);
}

// How long molecular control lasts, in ticks.
static int molecular_control_duration(int level)
{
	return level / 4;
}

std::string molecular_control_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Duration", game_hours(molecular_control_duration(level)) + " at your level, " +
					std::to_string(level)) +
	       "  You can walk through closed doors, except locked pickproof ones.\n"
	       "  Casting it again renews the duration.\n";
}

void spell_molecular_control(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			     P_char victim, P_obj /*obj*/)
{
	struct affected_type af;

	if (!((level >= 0) && ch))
	{
		logit(LOG_EXIT, "assert: bogus parms in molecular control");
		exit(1);
	}
	if (affected_by_spell(ch, SPELL_MOLECULAR_CONTROL))
	{
		struct affected_type *af1;

		for (af1 = victim->affected; af1; af1 = af1->next)
			if (af1->type == SPELL_MOLECULAR_CONTROL)
			{
				af1->duration = molecular_control_duration(level);
			}
		return;
	}

	bzero(&af, sizeof(af));
	af.type = SPELL_MOLECULAR_CONTROL;
	af.duration = molecular_control_duration(level);
	af.bitvector2 = AFF2_PASSDOOR;
	affect_to_char(ch, &af);

	act("&+YYou gain a keener understanding of your molecules!", FALSE, ch, 0, 0, TO_CHAR);
	act("&+W$n vibrates for a second, then is still.", TRUE, ch, 0, 0, TO_ROOM);

	return;
}

static int molecular_agitation_damage(const Rolls &rolls, int level)
{
	int dam_each[61] = { 0,	 0,  0,	 0,  0,	 12, 15, 18, 21, 24, 24, 24, 25, 25, 26, 26,
			     26, 27, 27, 27, 28, 28, 28, 29, 29, 29, 30, 30, 30, 31, 31, 31,
			     32, 32, 32, 33, 33, 33, 34, 34, 34, 35, 35, 35, 36, 36, 36, 37,
			     37, 37, 38, 38, 38, 38, 39, 39, 39, 39, 40, 40, 41 };

	level = MIN(level, static_cast<int>(ARRAY_SIZE(dam_each)) - 1);
	level = MAX(0, level);
	return rolls.number((dam_each[level] / 2), (dam_each[level] * 2));
}

// A target that saves takes two thirds.
static int molecular_agitation_saved(int dam)
{
	return (int)(dam / 1.5);
}

std::string molecular_agitation_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range hit = { molecular_agitation_damage(lowest_rolls, level),
			    molecular_agitation_damage(highest_rolls, level) };
	return fact("Psionic damage",
		    show_landing(hit) + " at your level, " + std::to_string(level)) +
	       fact("If the target makes a power save",
		    show_landing({ molecular_agitation_saved(hit.low),
				   molecular_agitation_saved(hit.high) })) +
	       "  Globes and spirit wards do not stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_molecular_agitation(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			       P_obj /*obj*/)
{
	int dam;
	struct damage_messages messages = {
		"$N's entire body quivers in deliciously searing full-body pain.",
		"&+ROUCH!&n  Your whole body momentarily seems to be on fire!",
		"$N's body suddenly quivers for a moment - that looked painful.",
		"$N doubles over in intense pain and the mindless muscle spasms end only after death claims $M.",
		"The pain you're feeling is so intense you'd rather be dead. Ah, you are...",
		"$N suddenly doubles over due to what must be incredible pain. Only death can save $M. Wait, it did..."
	};

	dam = molecular_agitation_damage(live_rolls, level);
	if (StatSave(victim, APPLY_POW, POW_DIFF(ch, victim)))
		dam = molecular_agitation_saved(dam);

	spell_damage(ch, victim, dam, SPLDAM_PSI, 0, &messages);
}

static int adrenaline_control_duration(int level)
{
	return level + 5;
}

// The strength and constitution adrenaline control adds.
static int adrenaline_control_bonus()
{
	return 15;
}

std::string adrenaline_control_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const std::string bonus = "+" + std::to_string(adrenaline_control_bonus());
	return fact("Duration", game_hours(adrenaline_control_duration(level)) +
					" at your level, " + std::to_string(level)) +
	       fact("Strength", bonus) + fact("Constitution", bonus) +
	       "  It has no effect while you already have it.\n";
}

void spell_adrenaline_control(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			      P_char /*victim*/, P_obj /*obj*/)
{
	named_set_ordinary_cast ordinary_cast(ch, SPELL_ADRENALINE_CONTROL);
	struct affected_type af;

	if (affected_by_spell(ch, SPELL_ADRENALINE_CONTROL))
	{
		send_to_char("Any more of an adrenaline rush, and yer heart would stop.\r\n", ch);
		return;
	}
	bzero(&af, sizeof(af));
	af.type = SPELL_ADRENALINE_CONTROL;
	af.duration = adrenaline_control_duration(level);
	af.location = APPLY_STR;
	af.modifier = adrenaline_control_bonus();
	af.bitvector = 0;
	affect_to_char(ch, &af);
	af.location = APPLY_CON;
	affect_to_char(ch, &af);

	send_to_char("&+CYou feel a massive rush of adrenaline!\r\n", ch);
	return;
}

static int aura_sight_duration()
{
	return 36;
}

// Aura sight grants more senses above these caster levels.
static int aura_sight_alignment_above()
{
	return 20;
}

static int aura_sight_life_above()
{
	return 25;
}

static int aura_sight_invisible_above()
{
	return 36;
}

static int aura_sight_farsee_above()
{
	return 41;
}

std::string aura_sight_facts(P_char /*ch*/)
{
	return fact("Duration", game_hours(aura_sight_duration())) +
	       "  It shows magic at any level.\n" +
	       fact("Detect good and evil",
		    "above level " + std::to_string(aura_sight_alignment_above())) +
	       fact("Sense life", "above level " + std::to_string(aura_sight_life_above())) +
	       fact("Detect invisibility",
		    "above level " + std::to_string(aura_sight_invisible_above())) +
	       fact("Farsee", "above level " + std::to_string(aura_sight_farsee_above())) +
	       "  Casting it again renews the duration.\n";
}

void spell_aura_sight(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
		      P_char victim, P_obj /*obj*/)
{
	struct affected_type af;

	if (!((level >= 0) && ch))
	{
		logit(LOG_EXIT, "assert: bogus parms in aura sight");
		exit(1);
	}
	if (affected_by_spell(ch, SPELL_AURA_SIGHT))
	{
		struct affected_type *af1;

		for (af1 = victim->affected; af1; af1 = af1->next)
			if (af1->type == SPELL_AURA_SIGHT)
			{
				af1->duration = aura_sight_duration();
			}
		return;
	}
	bzero(&af, sizeof(af));

	af.type = SPELL_AURA_SIGHT;
	af.duration = aura_sight_duration();

	af.bitvector2 = AFF2_DETECT_MAGIC;
	affect_to_char(ch, &af);

	if (GET_LEVEL(ch) > aura_sight_alignment_above())
	{
		af.bitvector2 = AFF2_DETECT_GOOD;
		affect_to_char(ch, &af);

		af.bitvector2 = AFF2_DETECT_EVIL;
		affect_to_char(ch, &af);
	}

	if (GET_LEVEL(ch) > aura_sight_life_above())
	{
		af.bitvector = AFF_SENSE_LIFE;
		af.bitvector2 = 0;
		affect_to_char(ch, &af);
	}

	if (GET_LEVEL(ch) > aura_sight_invisible_above())
	{
		af.bitvector = AFF_DETECT_INVISIBLE;
		affect_to_char(ch, &af);
	}

	if (GET_LEVEL(ch) > aura_sight_farsee_above())
	{
		af.bitvector = AFF_FARSEE;
		affect_to_char(ch, &af);
	}

	send_to_char("&+MYour vision sharpens considerably.&n\r\n", ch);
}

void spell_sever_link(int /*level*/, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		      P_obj /*obj*/)
{
	if (!ch || !victim)
		return;

	if (!victim->following)
	{
		send_to_char(
			"There is no link for you to sever. This creature is already free!\r\n",
			ch);
		return;
	}

	send_to_char("You attempt to sever the link between the pet and the master.\r\n", ch);
	send_to_char("You feel as if someone is probing the bond to your pet.\r\n",
		     victim->following);

	if (GET_LEVEL(victim) > 50)
	{
		send_to_char("But it seems that this time you are powerless.\r\n", ch);
		send_to_char("But it seems they are powerless.\r\n", victim->following);
		act("$N just tried to break the link between you and your master...", FALSE, ch, 0,
		    victim, TO_CHAR);
		if (!IS_FIGHTING(victim))
			MobStartFight(victim, ch);
		return;
	}

	if (number(0, 99) < BOUNDED(10, (100 - GET_LEVEL(victim)), 90))
	{
		act("$N jerks slighly as you tear through the bond.", FALSE, ch, 0, victim,
		    TO_CHAR);
		send_to_char("A stabbing pain fills your head as the bond is torn to shreads!\r\n",
			     victim->following);
		send_to_char("A sudden wave of blackness obscures your vision...\r\n", victim);
		send_to_char(
			"...and when it dissipates you feel you are no longer being controlled.\r\n",
			victim);
		stop_follower(victim);
	}
	else
		MobStartFight(victim, ch);
}

// Awe refuses a caster who already has this many charmed followers.
static int awe_follower_limit()
{
	return 5;
}

// The highest level awe can dominate. It also sets the limit a target's level plus the
// charmed followers' levels must stay below.
static int awe_limits(int level, P_char ch, int *max_total_levels)
{
	int max_level = 0;

	*max_total_levels = (int)(GET_LEVEL(ch) * 2);

	if (IS_ILLITHID(ch))
	{
		if (level > 51)
			max_level = level + 5;
		else if (level > 30)
			max_level = level;
		else if (level > 20)
			max_level = level - 4;
		else if (level > 15)
			max_level = level - 8;
		else
			max_level = 5;

		max_level = BOUNDED(5, max_level, 56);
	}
	else if (IS_TRUSTED(ch))
	{
		*max_total_levels = 500;
		max_level = 65;
	}
	else
	{
		*max_total_levels = 110;
		max_level = BOUNDED(5, level - 10, 36);
	}
	return max_level;
}

// The roll a dominating caster's threshold must not fall below.
static int awe_roll(const Rolls &rolls)
{
	return rolls.number(0, 100);
}

// The caster's power and level against the target's intelligence and level.
static int awe_threshold(int power, int level, int target_int, int target_level)
{
	return BOUNDED(5, power + level - target_int - target_level, 95);
}

std::string awe_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	int total_levels = 0;
	const int max_level = awe_limits(level, ch, &total_levels);
	std::string text =
		fact("Highest target level",
		     std::to_string(max_level) + " at your level, " + std::to_string(level)) +
		fact("Target plus charmed followers",
		     "below " + std::to_string(total_levels) + " total levels");
	if (!IS_TRUSTED(ch))
		text += fact("Refused at",
			     std::to_string(awe_follower_limit()) + " charmed followers");
	return text +
	       fact("Chance threshold",
		    show({ awe_threshold(0, 0, 1000, 1000), awe_threshold(1000, 1000, 0, 0) }) +
			    " on a roll of " +
			    show({ awe_roll(lowest_rolls), awe_roll(highest_rolls) }) +
			    ", from your power and level") +
	       "    against the target's intelligence and level.\n"
	       "  A target over a limit, or that wins while not fighting, attacks you.\n"
	       "  Only unowned NPCs of player-like races can be dominated; elites, greater\n"
	       "  races and undead cannot.\n";
}

void spell_awe(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim, P_obj /*obj*/)
{
	int num = 0;
	int max_level = 0;
	int total_levels = 0;
	int max_total_levels = 0;
	struct follow_type *followers;

	if (!victim)
	{
		send_to_char("You must have a target!\r\n", ch);
		return;
	}

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim) || IS_TRUSTED(victim))
	{
		return;
	}

	if (training_dummy_is(victim))
	{
		send_to_char("The training dummy has no mind to awe.\r\n", ch);
		return;
	}

	for (followers = ch->followers; followers; followers = followers->next)
	{
		if (affected_by_spell(followers->follower, SPELL_CHARM_PERSON))
		{
			num++;
			total_levels += GET_LEVEL(followers->follower);
		}

		if (!IS_TRUSTED(ch) && num >= awe_follower_limit())
		{
			send_to_char("You are unable to handle more followers.\r\n", ch);
			return;
		}
	}

	//  debug("part1: total_levels = %d", total_levels);

	max_level = awe_limits(level, ch, &max_total_levels);

	if (circle_follow(victim, ch))
	{
		return;
	}

	appear(ch);

	if (IS_NPC(victim) && !GET_MASTER(victim))
	{
		//    debug("Max level: %d Max_total_levels %d Victim level %d",
		//    max_level, max_total_levels, GET_LEVEL(victim));

		if (total_levels + GET_LEVEL(victim) >= max_total_levels ||
		    GET_LEVEL(victim) > max_level)
		{
			if (!IS_FIGHTING(victim))
			{
				act("$N&n seems really &+RPISSED OFF!&n", FALSE, ch, 0, victim,
				    TO_CHAR);
				act("You see $n gazing at you, then charges $m!&n", FALSE, ch, 0,
				    victim, TO_VICT);
				act("$N looks at $n, displays an &+rupset&n look, then charges $m!&n",
				    FALSE, ch, 0, victim, TO_NOTVICT);
				set_fighting(victim, ch);
			}
			return;
		}

		// For the most part, awe only works on player-like races.
		if (!IS_GREATER_RACE(victim) && !IS_ELITE(victim) && !IS_UNDEAD(victim) &&
		    !IS_TRUSTED(victim) &&
		    (OLD_RACE_EVIL(GET_RACE(victim), GET_ALIGNMENT(victim)) ||
		     OLD_RACE_GOOD(GET_RACE(victim), GET_ALIGNMENT(victim)) ||
		     GET_RACE(victim) == RACE_SNOW_OGRE || GET_RACE(victim) == RACE_RAKSHASA ||
		     GET_RACE(victim) == RACE_HUMANOID))
		{
			// Awe save is psi's power versus victim's int adjusted by level difference.
			// There is a chance for critical success or critical failure.
			int save = awe_threshold(GET_C_POW(ch), level, GET_C_INT(victim),
						 GET_LEVEL(victim));

			if (save < awe_roll(live_rolls) && !IS_TRUSTED(victim) &&
			    !IS_FIGHTING(victim))
			{
				set_fighting(victim, ch);
				return;
			}
			else if (!victim->following && !IS_TRUSTED(victim))
			{
				send_to_char("&+MYou dominate it!&n\n", ch);
				add_follower(victim, ch);
				// debug( "spell_awe: ch: '%s', victim: '%s', level: %d, setup_pet '%d'.", J_NAME(ch), J_NAME(victim), level,
				setup_pet(victim, ch, level, 0);
				act("&+MYour will is &+Ydominated!&n &+RUh oh...&n.", FALSE, ch, 0,
				    victim, TO_VICT);
				if (IS_SET(victim->specials.act, ACT_BREAK_CHARM))
				{
					send_to_char(
						"&+mYou get a funny feeling about this one.\n\r",
						ch);
				}
				if (IS_FIGHTING(victim))
				{
					stop_fighting(victim);
					StopMercifulAttackers(victim);
				}
			}
		}
		else
		{
			send_to_char(
				"&+MYou are unable to dominate the mind of this strange creature!&n\n",
				ch);
		}
		return;
	}
}

// The caster's lag on arriving, in pulses.
static int mind_travel_lag()
{
	return 5;
}

std::string mind_travel_facts(P_char /*ch*/)
{
	return fact("Your lag on arriving", seconds(mind_travel_lag())) +
	       "  It takes you to one of a fixed list of places, at random.\n"
	       "  It fails in combat, in no-teleport rooms and on oceans.\n";
}

void spell_mind_travel(int /*level*/, P_char ch, char * /*arg*/, int /*type*/, P_char /*victim*/,
		       P_obj obj)
{
	int num_rooms = 24; /* match the array below - 1 */
	int r_room = -1;
	int to_room[] = { 96563, 96563, 11545, 15273, 96900, 36171, 96563, 4109,  4437,
			  4109,	 96803, 17589, 17607, 96909, 3404,  23812, 23805, 12535,
			  12528, 25458, 25459, 25458, 12535, 12536, 12540 };

	if (IS_FIGHTING(ch))
	{
		act("$n travels with the speed of &+Clight&n and reappears at the same place...",
		    FALSE, ch, obj, 0, TO_CHAR);
		act("You travel with the speed of &+Clight&n and reappear at the same place", FALSE,
		    ch, obj, 0, TO_NOTVICT);
		return;
	}

	if (IS_ROOM(ch->in_room, ROOM_NO_TELEPORT) || world[ch->in_room].sector_type == SECT_OCEAN)
	{
		send_to_char("&+CYou failed.\r\n", ch);
		return;
	}
	char_from_room(ch);
	while (r_room == -1)
		r_room = real_room(to_room[number(0, num_rooms)]);
	act("$n travel with the speed of &+Clight&n and reapear elsewhere...bye!", FALSE, ch, obj,
	    0, TO_CHAR);
	act("You travel with the speed of &+Clight&n and reapear elsewhere...", FALSE, ch, obj, 0,
	    TO_CHAR);
	char_to_room(ch, r_room, -1);
	CharWait(ch, mind_travel_lag());
	return;
}

static int ballistic_attack_damage(const Rolls &rolls, int level)
{
	const int dam_each[61] = { 0,  3,  4,  4,  5,  6,  6,  6,  7,  7,  7,  7,  7,  8,  8,  8,
				   9,  9,  9,  10, 10, 10, 11, 11, 11, 12, 12, 12, 13, 13, 13, 14,
				   14, 14, 15, 15, 15, 16, 16, 16, 17, 17, 17, 18, 18, 18, 19, 19,
				   19, 20, 20, 21, 21, 21, 22, 22, 22, 23, 23, 23, 24 };

	level = MIN(level, static_cast<int>(ARRAY_SIZE(dam_each)) - 1);
	level = MAX(0, level);
	return rolls.number(dam_each[level] / 2, dam_each[level] * 4);
}

// A failed dexterity save doubles the damage.
static int ballistic_attack_failed_save(int dam)
{
	return dam * 2;
}

std::string ballistic_attack_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range hit = { ballistic_attack_damage(lowest_rolls, level),
			    ballistic_attack_damage(highest_rolls, level) };
	return fact("Damage", show(hit) + " at your level, " + std::to_string(level)) +
	       fact("If the target fails a dexterity save",
		    show({ ballistic_attack_failed_save(hit.low),
			   ballistic_attack_failed_save(hit.high) })) +
	       "  Globes, minor globes and spirit wards stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_ballistic_attack(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			    P_obj /*obj*/)
{
	int dam;

	dam = ballistic_attack_damage(live_rolls, level);

	act("&+LYou chuckle as a stone strikes $N&+L.", TRUE, ch, 0, victim, TO_CHAR);
	act("&+L$n&+L creates a boulder, striking you solidly!", TRUE, ch, 0, victim, TO_VICT);
	act("&+L$n&+L squints, and a boulder appears, striking $N&+L solidly!", TRUE, ch, 0, victim,
	    TO_NOTVICT);

	if (!StatSave(victim, APPLY_DEX, 0))
	{
		act("&+LYour mental boulder smashes $N&+L really hard.", TRUE, ch, 0, victim,
		    TO_CHAR);
		act("&+LYou are almost smashed by the force of the boulder.!", TRUE, ch, 0, victim,
		    TO_VICT);
		act("&+L$N&+L is almost smashed by the heavy projectile!", TRUE, ch, 0, victim,
		    TO_NOTVICT);
		dam = ballistic_attack_failed_save(dam);
	}

	damage(ch, victim, dam, SPELL_BALLISTIC_ATTACK);
}

static int biofeedback_duration()
{
	return 6;
}

// How many hits biofeedback absorbs.
static int biofeedback_absorb(const Rolls &rolls, int level)
{
	return (level / 2 + rolls.number(1, 4));
}

std::string biofeedback_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Hits absorbed", show({ biofeedback_absorb(lowest_rolls, level),
					    biofeedback_absorb(highest_rolls, level) }) +
					     " at your level, " + std::to_string(level)) +
	       fact("Each melee hit on you", std::to_string(skin_spell_deduct()) + " less") +
	       fact("Then, if over 10 is left",
		    share_percent(biofeedback_melee_share()) + " of that") +
	       "  It applies before the raw damage modifiers.\n"
	       "  Hits that ignore reductions go through it and use up nothing.\n"
	       "  An attacker's fist of dragon can do the same.\n" +
	       fact("Duration", game_hours(biofeedback_duration())) +
	       "  It has no effect while you have any skin spell.\n";
}

void spell_biofeedback(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
		       P_char victim, P_obj /*obj*/)
{
	named_set_ordinary_cast ordinary_cast(victim, SPELL_BIOFEEDBACK);
	struct affected_type af;

	if (has_skin_spell(victim) && IS_PC(victim))
	{
		send_to_char("Nothing happens.\n", ch);
		return;
	}

	bzero(&af, sizeof(af));
	af.type = SPELL_BIOFEEDBACK;
	af.duration = biofeedback_duration();
	af.modifier = biofeedback_absorb(live_rolls, level);
	affect_to_char(victim, &af);

	send_to_char("&+GYou are surrounded by a green mist!&n\r\n", ch);
	act("&+G$n&+G is suddenly surrounded by a green mist!", TRUE, ch, 0, 0, TO_NOTVICT);
}

// Cell adjustment heals more above these caster levels.
static int cell_adjustment_poison_above()
{
	return 2;
}

static int cell_adjustment_curse_above()
{
	return 9;
}

static int cell_adjustment_blindness_above()
{
	return 29;
}

static int cell_adjustment_wither_above()
{
	return 50;
}

static int cell_adjustment_disease_above()
{
	return 55;
}

std::string cell_adjustment_facts(P_char /*ch*/)
{
	return fact("Cures poison",
		    "above level " + std::to_string(cell_adjustment_poison_above())) +
	       fact("Removes curses",
		    "above level " + std::to_string(cell_adjustment_curse_above())) +
	       fact("Cures blindness",
		    "above level " + std::to_string(cell_adjustment_blindness_above())) +
	       fact("Removes wither",
		    "above level " + std::to_string(cell_adjustment_wither_above())) +
	       fact("Cures disease",
		    "above level " + std::to_string(cell_adjustment_disease_above()));
}

void spell_cell_adjustment(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			   P_obj /*obj*/)
{
	int poison, curse, wither, disease, blind;

	poison = FALSE;
	curse = FALSE;
	wither = FALSE;
	disease = FALSE;
	blind = FALSE;

	if (GET_LEVEL(ch) > cell_adjustment_poison_above())
		poison = TRUE;
	if (GET_LEVEL(ch) > cell_adjustment_curse_above())
		curse = TRUE;
	if (GET_LEVEL(ch) > cell_adjustment_blindness_above())
		blind = TRUE;
	if (GET_LEVEL(ch) > cell_adjustment_wither_above())
		wither = TRUE;
	if (GET_LEVEL(ch) > cell_adjustment_disease_above())
		disease = TRUE;

	if (poison && (affected_by_spell(ch, SPELL_POISON) ||
		       IS_SET(victim->specials.affected_by2, AFF2_POISONED)))
	{
		act("&+GYour willpower has neutralized the poison in your bloodstream.", FALSE, ch,
		    0, victim, TO_CHAR);
		poison_common_remove(victim);
	}

	if (curse && affected_by_spell(ch, SPELL_CURSE))
	{
		act("You tell the gods to fuck off and remove their curse!", FALSE, ch, 0, victim,
		    TO_CHAR);
		affect_from_char(victim, SPELL_CURSE);
	}

	if (curse)
	{
		spell_remove_curse(level, ch, 0, 0, ch, NULL);
	}

	if (wither && affected_by_spell(ch, SPELL_WITHER))
	{
		act("&+rYour sheer willpower causes your body to shrug off the filthy withered sensation.",
		    FALSE, ch, 0, victim, TO_CHAR);
		affect_from_char(victim, SPELL_WITHER);
	}

	if (disease && affected_by_spell(ch, SPELL_DISEASE))
	{
		act("&+rWith nothing but sheer willpower, you shrug off the putrid disease!", FALSE,
		    ch, 0, victim, TO_CHAR);
		// affect_from_char(victim, SPELL_DISEASE);
	}

	if (disease)
	{
		spell_cure_disease(level, ch, 0, 0, ch, NULL);
	}

	if (blind && IS_AFFECTED(ch, AFF_BLIND))
	{
		act("&+WYour vision returns, just as you willed it to.", FALSE, ch, 0, victim,
		    TO_CHAR);
		affect_from_char(victim, SPELL_BLINDNESS);
		if (IS_SET(victim->specials.affected_by, AFF_BLIND))
			REMOVE_BIT(victim->specials.affected_by, AFF_BLIND);
	}

	return;
}

static int combat_mind_duration(int level)
{
	return level + 3;
}

static int combat_mind_hitroll(int level)
{
	return level / 6;
}

static int combat_mind_damroll(int level)
{
	return level / 8;
}

std::string combat_mind_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	std::string text = fact("Duration", game_hours(combat_mind_duration(level)) +
						    " at your level, " + std::to_string(level));
	if (combat_mind_hitroll(level))
		text += fact("Hitroll", "+" + std::to_string(combat_mind_hitroll(level)));
	if (combat_mind_damroll(level))
		text += fact("Damroll", "+" + std::to_string(combat_mind_damroll(level)));
	text += fact("To-hit rate", std::to_string(combat_mind_to_hit()) + ", the warrior rate") +
		fact("When something cuts your melee attacks, you keep at least",
		     share_percent(combat_mind_attack_floor())) +
		fact("Chance not to spill a potion in combat",
		     std::to_string(combat_mind_quaff_chance(100)) + "% of normal") +
		"  Your hits ignore displacement's absorption, and you never fumble.\n"
		"  A berserker's mangle cannot disarm you.\n"
		"  Improving your parry skill no longer costs you that parry.\n";
	if (GET_CLASS(ch, CLASS_PSIONICIST))
		text += fact("As a psionicist, parry rating",
			     "+" + std::to_string(combat_mind_parry_skill(level) +
						  combat_mind_parry_bonus(level))) +
			fact("Extra main weapon attacks",
			     level > combat_mind_second_attack_above() ?
				     "2" :
				     "1, or 2 above level " +
					     std::to_string(combat_mind_second_attack_above())) +
			fact("Bare-handed damage before your bonuses",
			     show({ combat_mind_bare_hand_damage(lowest_rolls, ch),
				    combat_mind_bare_hand_damage(highest_rolls, ch) }));
	return text + "  Casting it again renews the duration.\n";
}

void spell_combat_mind(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
		       P_char victim, P_obj /*obj*/)
{
	named_set_ordinary_cast ordinary_cast(victim, SPELL_COMBAT_MIND);
	struct affected_type af;

	if (affected_by_spell(ch, SPELL_COMBAT_MIND))
	{
		struct affected_type *af1;

		for (af1 = victim->affected; af1; af1 = af1->next)
			if (af1->type == SPELL_COMBAT_MIND)
			{
				af1->duration = combat_mind_duration(level);
			}
		return;
	}

	bzero(&af, sizeof(af));
	af.type = SPELL_COMBAT_MIND;
	af.duration = combat_mind_duration(level);
	af.modifier = combat_mind_hitroll(level);
	af.bitvector = 0;
	af.location = APPLY_HITROLL;
	affect_to_char(victim, &af);

	af.duration = combat_mind_duration(level);
	af.modifier = combat_mind_damroll(level);
	af.location = APPLY_DAMROLL;
	affect_to_char(victim, &af);

	if (victim != ch)
		act("Ok.", FALSE, ch, 0, victim, TO_CHAR);
	act("&+yYour knowledge of battle tactics increases!", FALSE, ch, 0, victim, TO_VICT);
	return;
}

static int fire_aura_duration()
{
	return (SECS_PER_MUD_DAY / 60);
}

static int fire_aura_ac()
{
	return -15;
}

static int fire_aura_str_max()
{
	return 15;
}

// The maximum dexterity and maximum agility it lowers.
static int fire_aura_nimbleness()
{
	return -20;
}

static int fire_aura_con_max()
{
	return 25;
}

// The fear save for the full form is this much harder, on NewSaves()' scale.
static int fire_aura_full_form_save()
{
	return 4;
}

std::string fire_aura_facts(P_char /*ch*/)
{
	return fact("Duration", game_hours(fire_aura_duration())) +
	       fact("Armor class", std::to_string(fire_aura_ac())) +
	       fact("Maximum strength", "+" + std::to_string(fire_aura_str_max())) +
	       fact("Maximum dexterity", std::to_string(fire_aura_nimbleness())) +
	       fact("Maximum agility", std::to_string(fire_aura_nimbleness())) +
	       fact("Maximum constitution", "+" + std::to_string(fire_aura_con_max())) +
	       fact("Fear save for the full form",
		    "+" + std::to_string(fire_aura_full_form_save()) + ", worse") +
	       "  The full form adds a fire aura and a fireshield.\n"
	       "  You must stand on the fire plane or on lava.\n"
	       "  It has no effect while you have it or an elemental form.\n";
}

void spell_fire_aura(int /*level*/, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
		     P_char victim, P_obj /*obj*/)
{
	struct affected_type af;

	if (const char *failure = elemental_form_failure_message(ch, victim, SPELL_FIRE_AURA))
	{
		send_to_char(failure, ch);
		return;
	}

	if (!IS_ALIVE(ch))
		return;

	if (affected_by_spell(ch, SPELL_FIRE_AURA))
	{
		send_to_char("Nothing seems to happen.\n", ch);
		return;
	}

	if (world[ch->in_room].sector_type == SECT_FIREPLANE ||
	    world[ch->in_room].sector_type == SECT_LAVA)
	{
		act("&+rYour body glows with an aura of fire!", FALSE, ch, 0, 0, TO_CHAR);
		act("&+r$n's&+r body glows with an aura of fire!", FALSE, ch, 0, 0, TO_ROOM);
		bzero(&af, sizeof(af));
		af.type = SPELL_FIRE_AURA;
		af.duration = fire_aura_duration();

		af.location = APPLY_AC;
		af.modifier = fire_aura_ac();
		affect_to_char(victim, &af);

		af.location = APPLY_STR_MAX;
		af.modifier = fire_aura_str_max();
		affect_to_char(victim, &af);

		af.location = APPLY_DEX_MAX;
		af.modifier = fire_aura_nimbleness();
		affect_to_char(victim, &af);

		af.location = APPLY_AGI_MAX;
		af.modifier = fire_aura_nimbleness();
		affect_to_char(victim, &af);

		af.location = APPLY_CON_MAX;
		af.modifier = fire_aura_con_max();
		affect_to_char(victim, &af);

		if (NewSaves(ch, SAVING_FEAR, fire_aura_full_form_save()))
		{
			act("&+RYour body bursts into flames as you achieve full form!", FALSE, ch,
			    0, 0, TO_CHAR);
			act("&+R$n's&+R body bursts into flames as $e achieves full form!", FALSE,
			    ch, 0, 0, TO_ROOM);
			af.location = 0;
			af.modifier = 0;
			af.bitvector2 = AFF2_FIRE_AURA;
			affect_to_char(victim, &af);

			af.bitvector2 = AFF2_FIRESHIELD;
			affect_to_char(victim, &af);
		}
	}
	else
	{
		act("&+LYou need to stand on &+Rfire&+L in order to gain some of its properties.",
		    FALSE, ch, 0, 0, TO_CHAR);
	}
}

static int control_flames_damage(const Rolls &rolls, int level)
{
	const int dam_each[61] = { 0,  0,  0,  0,  0,  0,  0,  0,  16, 20, 24, 28, 32, 35, 38, 40,
				   42, 44, 45, 45, 45, 46, 46, 46, 47, 47, 47, 48, 48, 48, 49, 49,
				   49, 50, 50, 50, 51, 51, 51, 52, 52, 52, 53, 53, 53, 54, 54, 54,
				   55, 55, 55, 56, 56, 56, 57, 57, 58, 58, 58, 59, 59 };

	level = MIN(level, static_cast<int>(ARRAY_SIZE(dam_each)) - 1);
	level = MAX(0, level);
	return rolls.number(dam_each[level] / 2, dam_each[level] * 2);
}

// A target that makes its power save takes half.
static int control_flames_saved(int dam)
{
	return dam / 2;
}

std::string control_flames_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range hit = { control_flames_damage(lowest_rolls, level),
			    control_flames_damage(highest_rolls, level) };
	return fact("Damage", show_landing(hit) + " at your level, " + std::to_string(level)) +
	       fact("If the target makes a power save",
		    show_landing(
			    { control_flames_saved(hit.low), control_flames_saved(hit.high) })) +
	       "  The target must be carrying a torch.\n"
	       "  Globes and spirit wards stop it; minor globes do not.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_control_flames(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			  P_obj obj)
{
	int dam;
	char buf[MAX_STRING_LENGTH];

	snprintf(buf, MAX_STRING_LENGTH, "torch");
	obj = get_obj_in_list_vis(ch, buf, victim->carrying);
	if (!obj)
	{
		act("Your target must be carrying a torch.", 0, ch, 0, 0, TO_CHAR);
		return;
	}

	dam = control_flames_damage(live_rolls, level);

	if (StatSave(victim, APPLY_POW, 0))
		dam = control_flames_saved(dam);

	act("&+r$N's $p suddenly flares up, engulfing $M in flames!", TRUE, ch, obj, victim,
	    TO_CHAR);
	act("&+rYour $p suddenly flares up, engulfing you in flames!", TRUE, ch, obj, victim,
	    TO_VICT);
	act("&+r$N's $p suddenly flares up, engulfing $M in flames!", TRUE, ch, obj, victim,
	    TO_NOTVICT);

	damage(ch, victim, dam, SPELL_EGO_BLAST); // no messages in file, so this works

	return;
}

static int ego_blast_damage(const Rolls &rolls, int level)
{
	const int dam_each[61] = { 0,  0,  0,  0,  0,  0,  0,  0,  16, 20, 24, 28, 32, 35, 38, 40,
				   42, 44, 45, 45, 45, 46, 46, 46, 47, 47, 47, 48, 48, 48, 49, 49,
				   49, 50, 50, 50, 51, 51, 51, 52, 52, 52, 53, 53, 53, 54, 54, 54,
				   55, 55, 55, 56, 56, 56, 57, 57, 58, 58, 58, 59, 59 };

	level = MIN(level, static_cast<int>(ARRAY_SIZE(dam_each)) - 1);
	level = MAX(0, level);
	return rolls.number(dam_each[level] / 2, dam_each[level] * 2);
}

// A target that makes its power save takes half.
static int ego_blast_saved(int dam)
{
	return dam / 2;
}

std::string ego_blast_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range hit = { ego_blast_damage(lowest_rolls, level),
			    ego_blast_damage(highest_rolls, level) };
	return fact("Damage", show_landing(hit) + " at your level, " + std::to_string(level)) +
	       fact("If the target makes a power save",
		    show_landing({ ego_blast_saved(hit.low), ego_blast_saved(hit.high) })) +
	       "  Globes and spirit wards stop it; minor globes do not.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

/* used to be control_flames */

void spell_ego_blast(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		     P_obj /*obj*/)
{
	int dam;
	/*
	  snprintf(buf, MAX_STRING_LENGTH, "torch");
	  obj = get_obj_in_list_vis (ch, buf, victim->carrying);
	  if (!obj)
	    {
	      act ("Your target must be carrying a torch.", 0, ch, 0, 0, TO_CHAR);
	      return;
	    }
	*/
	dam = ego_blast_damage(live_rolls, level);

	if (StatSave(victim, APPLY_POW, 0))
		dam = ego_blast_saved(dam);
	/*
	      act ("&+r$N's $p suddenly flares up, engulfing $M in flames!", TRUE, ch, obj, victim, TO_CHAR);
	      act ("&+rYour $p suddenly flares up, engulfing you in flames!", TRUE, ch, obj, victim, TO_VICT);
	      act ("&+r$N's $p suddenly flares up, engulfing $M in flames!", TRUE, ch, obj, victim, TO_NOTVICT);
	*/

	act("&+MYou mentally blast $N's ego.", TRUE, ch, 0, victim, TO_CHAR);
	act("&+M$n mentally blasts your mind with stunning force!", TRUE, ch, 0, victim, TO_VICT);
	act("&+M$n squints and $N&+M screams out in great pain, holding $S head!", TRUE, ch, 0,
	    victim, TO_NOTVICT);

	damage(ch, victim, dam, SPELL_EGO_BLAST); // no messages in file, so this works

	return;
}

void spell_create_sound(int /*level*/, P_char ch, char * /*arg*/, int /*type*/, P_char /*victim*/,
			P_obj /*obj*/)
{
	if (IS_ROOM(ch->in_room, ROOM_SILENT))
	{
		act("&+WYour sonic boom of mental power dispels the silence!", 0, ch, 0, 0,
		    TO_CHAR);
		act("&+W$n sends out a blast of psionic sound!", FALSE, ch, 0, 0, TO_ROOM);
		REMOVE_BIT(world[ch->in_room].room_flags, ROOM_SILENT);
	}
	else
		send_to_char("Hmm, seems pretty noisy already.\r\n", ch);
}

static int psychic_crush_damage(const Rolls &rolls, int level)
{
	return rolls.dice((int)(MIN(level, 51) * 3), 10);
}

// A saving or elite target takes half.
static int psychic_crush_saved(int dam)
{
	return dam >> 1;
}

static int psychic_crush_penalty_duration()
{
	return (int)(0.05 * SECS_PER_MUD_HOUR * WAIT_SEC);
}

static int psychic_crush_penalty(int level)
{
	return (int)(-1 * (level / 2));
}

// An enslaver's follow-up: below the first limit the target is stunned, then it kneels.
static int psychic_crush_enslaver_roll(const Rolls &rolls)
{
	return rolls.number(1, 100);
}

static int psychic_crush_stun_below()
{
	return 10;
}

static int psychic_crush_kneel_below()
{
	return 15;
}

static int psychic_crush_stun()
{
	return PULSE_VIOLENCE * 1;
}

std::string psychic_crush_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range hit = { psychic_crush_damage(lowest_rolls, level),
			    psychic_crush_damage(highest_rolls, level) };
	std::string text =
		fact("Psionic damage", show(hit) + " at your level, " + std::to_string(level)) +
		fact("If the target makes a power save",
		     show({ psychic_crush_saved(hit.low), psychic_crush_saved(hit.high) })) +
		"  An elite target always takes the lower amount.\n"
		"  Globes and spirit wards do not stop it.\n"
		"  Spell damage modifiers and the target's defenses apply after.\n";
	if (psychic_crush_penalty(level))
		text += fact("Penalty", std::to_string(psychic_crush_penalty(level)) +
						" to power, intelligence or wisdom, at random") +
			fact("Penalty duration", seconds(psychic_crush_penalty_duration())) +
			"  A target already under the penalty does not get another.\n";
	if (GET_SPEC(ch, CLASS_PSIONICIST, SPEC_ENSLAVER))
		text += fact("Enslaver stun",
			     std::to_string(psychic_crush_stun_below() -
					    psychic_crush_enslaver_roll(lowest_rolls)) +
				     " in " +
				     std::to_string(psychic_crush_enslaver_roll(highest_rolls)) +
				     ", up to " + seconds(psychic_crush_stun()) +
				     "; fear saves shorten or stop it") +
			fact("Enslaver knockdown to the knees",
			     std::to_string(psychic_crush_kneel_below() -
					    psychic_crush_stun_below()) +
				     " in " +
				     std::to_string(psychic_crush_enslaver_roll(highest_rolls))) +
			"  Both need the target to survive the hit.\n"
			"  Elites, zombies, golems, dragons and plants are immune to both.\n"
			"  Other greater races and constructs may resist the stun, more often\n"
			"  the higher their level.\n";
	return text;
}

void spell_psychic_crush(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			 P_char victim, P_obj /*obj*/)
{
	int dam, spec_affect;
	char buf[256];
	struct affected_type af;
	struct damage_messages messages = {
		"$N's &+meyes briefly cloud over as $S entire psyche is wracked with wonderfully intense pain.",
		"&+mAs your body is consumed with pain, pain, and more pain, you briefly go to that 'happy place' inside.",
		"$N's &+meyes briefly cloud over as $S body is painfully ripped apart from within.",
		"$N &+mcrumples to the ground, blood seeping from $S ears as your psychic crush tears $S mind to pieces.",
		"&+mYou crumple to the ground, blood seeping from your ears as your mind is torn to pieces.",
		"&+RBlood &+mseeps from&n $N's &+mears as $S mind is torn to &+wpieces.",
		0
	};
	if (!ch)
	{
		logit(LOG_EXIT, "spell_psychic_crush called in psionics.c with no ch");
		exit(1);
	}
	if (!IS_ALIVE(victim))
	{
		send_to_char("Your prey seems to not be alive.\n", ch);
		return;
	}

	dam = psychic_crush_damage(live_rolls, level); // 105 saved 210 unsaved
	if (!affected_by_spell(victim, SPELL_PSYCHIC_CRUSH))
	{
		bzero(&af, sizeof(af));
		af.type = SPELL_PSYCHIC_CRUSH;
		// af.duration = (int) (level / 2);
		af.duration = psychic_crush_penalty_duration();
		af.flags = AFFTYPE_SHORT;
		af.modifier = psychic_crush_penalty(level);

		act("$n &+msuddenly clutches their head, as if trying to shrug off some unknown malady.&n",
		    FALSE, victim, 0, 0, TO_ROOM);

		switch (number(0, 2))
		{
		case 0:
			send_to_char(
				"&+wThat last attack was particularly invasive, and you feel your collective power decrease.&n\r\n",
				victim);
			af.location = APPLY_POW;
			break;

		case 1:
			send_to_char(
				"&+wThat last attack was particularly invasive, and you feel your collective intelligence decrease.&n\r\n",
				victim);
			af.location = APPLY_INT;
			break;

		case 2:
			send_to_char(
				"&+wThat last attack was particularly invasive, and you feel your collective wisdom decrease.&n\r\n",
				victim);
			af.location = APPLY_WIS;
			break;
		}

		affect_to_char(victim, &af);
	}

	if (!StatSave(victim, APPLY_POW, (GET_LEVEL(victim) - GET_LEVEL(ch)) / 5) &&
	    !IS_ELITE(victim))
	{
		if ((spell_damage(ch, victim, dam, SPLDAM_PSI, 0, &messages) != DAM_NONEDEAD))
		{
			return;
		}
	}
	else
	{
		if ((spell_damage(ch, victim, psychic_crush_saved(dam), SPLDAM_PSI, 0, &messages) !=
		     DAM_NONEDEAD))
		{
			return;
		}
	}
	// special affect on crush for +specced casters.
	if (GET_SPEC(ch, CLASS_PSIONICIST, SPEC_ENSLAVER) &&
	    !(IS_ELITE(victim) || IS_TRUSTED(victim) || IS_ZOMBIE(victim) ||
	      GET_RACE(victim) == RACE_GOLEM || GET_RACE(victim) == RACE_DRAGON ||
	      GET_RACE(victim) == RACE_PLANT))
	{
		spec_affect = psychic_crush_enslaver_roll(live_rolls);

		if (spec_affect < psychic_crush_stun_below())
		{
			Stun(victim, ch, psychic_crush_stun(), TRUE);
			if (IS_HUMANOID(victim))
			{
				strcpy(buf, "&n&+wGeT tHiS &+MThiNg&n &+wOuT oF mY hEaD !!!&n");
				do_say(victim, buf, CMD_SHOUT);
			}
		}
		else if (spec_affect < psychic_crush_kneel_below())
		{
			SET_POS(victim, POS_KNEELING + GET_STAT(victim));
			act("&+yYou fall to your knees as uncontrollable pain engulfs your entire brain!&n",
			    FALSE, ch, NULL, victim, TO_VICT);
			act("$N &+yfalls to their knees, grasping $s head and screaming in pain!&n",
			    FALSE, ch, NULL, victim, TO_NOTVICT);
			act("$N &+yfalls to their knees, grasping $s head and screaming in pain!!&n",
			    TRUE, ch, NULL, victim, TO_CHAR);
			do_action(victim, 0, CMD_CRY);
		}
		else if (IS_HUMANOID(victim) && spec_affect < 40)
		{
			do_action(victim, 0, CMD_PUKE);
		}
	}
}

static int death_field_damage(const Rolls &rolls, int level)
{
	return 130 + level * 3 + rolls.number(1, 10);
}

// An enslaver's death field deals double.
static int death_field_enslaver_damage(int dam, P_char ch)
{
	if (GET_SPEC(ch, CLASS_PSIONICIST, SPEC_ENSLAVER))
	{
		dam = dam * 2;
	}
	return dam;
}

static int death_field_player_damage(int dam)
{
	return dam * get_property("spell.area.damage.to.pc", 0.5);
}

// How long a death field keeps the room's stack timer, in seconds.
static int death_field_stack_seconds()
{
	return (int)get_property("spell.area.stackTimer.deathField", 5);
}

// A death field on a recent one of yours or your group's casts at half level.
static int death_field_stacked_level(int level)
{
	return level / 2;
}

static int death_field_lag()
{
	return WAIT_SEC * 2;
}

std::string death_field_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const int stacked = death_field_stacked_level(level);
	const auto damage_at = [ch](const Rolls &rolls, int at)
	{ return death_field_enslaver_damage(death_field_damage(rolls, at), ch); };
	const Range hit = { damage_at(lowest_rolls, level), damage_at(highest_rolls, level) };
	std::string text = fact("Psionic damage to each target hit",
				show(hit) + " at your level, " + std::to_string(level));
	if (IS_PC(ch))
		text += fact("Against a player", show({ death_field_player_damage(hit.low),
							death_field_player_damage(hit.high) }));
	return text +
	       fact("Cast within " + std::to_string(death_field_stack_seconds()) +
			    " seconds of yours or your group's here",
		    "level " + std::to_string(stacked)) +
	       "    That is " +
	       show({ damage_at(lowest_rolls, stacked), damage_at(highest_rolls, stacked) }) +
	       " before the adjustment against a player.\n"
	       "  An area cast can skip some of the players in the room.\n" +
	       fact("Your lag", seconds(death_field_lag())) +
	       "  Globes and spirit wards do not stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_single_death_field(int level, P_char ch, char * /*args*/, int /*type*/, P_char victim,
			      P_obj /*obj*/)
{
	int dam;
	struct damage_messages messages = {
		"$N's body shivers and $E turns pale as a wave of death reaches $M.",
		"Your mind blacks out for a moment as a wave of death runs through you.",
		"$N's body shivers and $E turns pale as a wave of death reaches $M.",
		"$N's body shivers and falls lifeless as a wave of death reaches $M.",
		"Your mind collapses as a wave of death runs through your body.",
		"$N's body shivers and falls lifeless as a wave of death reaches $M.",
		0
	};
	dam = death_field_damage(live_rolls, level);
	dam = death_field_enslaver_damage(dam, ch);
	if (IS_PC(ch) && IS_PC(victim))
	{
		dam = death_field_player_damage(dam);
	}

	spell_damage(ch, victim, dam, SPLDAM_PSI, 0, &messages);
}

void spell_death_field(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		       P_obj /*obj*/)
{
	P_char tch;

	if (IS_PC(ch) && (tch = stack_area(ch, SPELL_DEATH_FIELD, death_field_stack_seconds())))
	{
		act("&+LYour deadly wave interferes with $N's field!", FALSE, ch, 0, tch, TO_CHAR);
		act("&+L$n sends out a wave of psionic death!", FALSE, ch, 0, 0, TO_ROOM);
		level = death_field_stacked_level(level);
	}
	else
	{
		act("&+LYou send out a wave of psionic death!", FALSE, ch, 0, 0, TO_CHAR);
		act("&+L$n sends out a wave of psionic death!", FALSE, ch, 0, 0, TO_ROOM);
	}

	cast_as_damage_area(ch, spell_single_death_field, level, victim,
			    get_property("spell.area.minChance.deathField", 60),
			    get_property("spell.area.chanceStep.deathField", 30));

	zone_spellmessage(ch->in_room, TRUE,
			  "&+LYour brain hurts as a black haze fills the sky!\r\n");
	CharWait(ch, death_field_lag());
}

void spell_detonate2(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		     P_obj /*obj*/)
{
	int dam;
	struct damage_messages messages = {
		"You feel a warm sense of satisfaction as &+Rexplosions&N engulf $N.",
		"Tiny &+Yexplosions&N wrack your body with pain!",
		"Tiny &+Yexplosions&n wrack $N&n's body with pain!",
		"You &+Yexplode&n $N, satisfied yet? Good...",
		"Thousands of tiny &+Yexplosions&n blast your soul away from your body.",
		"$N &+Ydetonates&n, pieces of flesh splatter across the room."
	};

	dam = dice(MIN(level, 50) * 2, 8);
	dam += 2 * GET_DAMROLL(ch);

	// spell_damage already doubles against pets - Jexni 6/21/08
	if (/*get_linked_char(victim, LNK_PET) ||*/ GET_RACE(victim) == RACE_GOLEM ||
	    GET_RACE(victim) == RACE_PLANT)
		dam = (dam * 2);

	if (resists_spell(ch, victim))
	{
		if (GET_SPEC(ch, CLASS_PSIONICIST, SPEC_PYROKINETIC))
			dam = (int)(dam * get_property("spell.detonate.shrugModifier", 0.7));
		else if (GET_CLASS(ch, CLASS_MINDFLAYER) && IS_NPC(victim))
			dam = (int)(dam *
				    get_property("spell.detonate.shrugModifierMindflayer", 0.9));
		else
			return;
	}

	if (!StatSave(victim, APPLY_POW, (GET_LEVEL(victim) - GET_LEVEL(ch)) / 5) &&
	    !IS_ELITE(victim))
	{
		spell_damage(ch, victim, dam, SPLDAM_PSI, SPLDAM_NOSHRUG, &messages);
	}
	else
	{
		spell_damage(ch, victim, dam >> 1, SPLDAM_PSI, SPLDAM_NOSHRUG, &messages);
	}

	CharWait(ch, (int)(PULSE_SPELLCAST * 1));
}

static int detonate_damage(const Rolls &rolls, int level)
{
	return rolls.dice(MIN(level, 40) * 2, 8) + 60;
}

// The caster's damroll counts double.
static int detonate_damroll_bonus(P_char ch)
{
	return 2 * GET_DAMROLL(ch);
}

static int detonate_mindflayer_bonus(int level)
{
	return level * 3;
}

// Golems and plants take double.
static int detonate_construct_damage(int dam)
{
	return (dam * 2);
}

// The share of the damage a pyrokinetic keeps through a shrug.
static int detonate_pyrokinetic_shrug(int dam)
{
	return (int)(dam * get_property("spell.detonate.shrugModifier", 0.7));
}

// The share of the damage a mindflayer keeps through an NPC's shrug.
static int detonate_mindflayer_shrug(int dam)
{
	return (int)(dam * get_property("spell.detonate.shrugModifierMindflayer", 0.9));
}

// A target that makes its power save, or an elite, takes half.
static int detonate_saved(int dam)
{
	return dam / 2;
}

std::string detonate_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	Range hit = { detonate_damage(lowest_rolls, level) + detonate_damroll_bonus(ch),
		      detonate_damage(highest_rolls, level) + detonate_damroll_bonus(ch) };
	std::string shrug = "A target's shrug stops it.";
	if (GET_CLASS(ch, CLASS_MINDFLAYER))
	{
		hit.low += detonate_mindflayer_bonus(level);
		hit.high += detonate_mindflayer_bonus(level);
		shrug = "An NPC's shrug leaves " +
			show_landing({ detonate_mindflayer_shrug(hit.low),
				       detonate_mindflayer_shrug(hit.high) }) +
			"; a player's stops it.";
	}
	if (GET_SPEC(ch, CLASS_PSIONICIST, SPEC_PYROKINETIC))
		shrug = "A shrug leaves " +
			show_landing({ detonate_pyrokinetic_shrug(hit.low),
				       detonate_pyrokinetic_shrug(hit.high) }) +
			" instead of stopping it.";
	return fact("Psionic damage",
		    show_landing(hit) + " at your level, " + std::to_string(level)) +
	       "  It includes twice your damroll.\n" +
	       fact("If the target saves or is elite",
		    show_landing({ detonate_saved(hit.low), detonate_saved(hit.high) })) +
	       fact("Against golems and plants",
		    show_landing({ detonate_construct_damage(hit.low),
				   detonate_construct_damage(hit.high) }) +
			    ", before a save") +
	       "  " + shrug +
	       "\n"
	       "  Globes and spirit wards do not stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_detonate(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		    P_obj /*obj*/)
{
	int dam;
	struct damage_messages messages = {
		"You feel a warm sense of satisfaction as &+Rexplosions&N engulf $N.",
		"Tiny &+Yexplosions&N wrack your body with pain!",
		"Tiny &+Yexplosions&n wrack $N&n's body with pain!",
		"You &+Yexplode&n $N, satisfied yet? Good...",
		"Thousands of tiny &+Yexplosions&n blast your soul away from your body.",
		"$N &+Ydetonates&n, pieces of flesh splatter across the room."
	};

	// avg: 40 * 2 + 60 = 80d8 + 60-> 640/2+60 = 380/4 = 95
	dam = detonate_damage(live_rolls, level);
	dam += detonate_damroll_bonus(ch);

	// +2 damage per level?  Hell no! Not for a Lich. That's +102 damage at 56!!!
	//   Howabout, +.75 damage per level -> +42 damage at 56.
	if (GET_CLASS(ch, CLASS_MINDFLAYER))
	{
		dam += detonate_mindflayer_bonus(level);
	}

	// spell_damage already doubles against pets - Jexni 6/21/08
	if (GET_RACE(victim) == RACE_GOLEM || GET_RACE(victim) == RACE_PLANT)
	{
		dam = detonate_construct_damage(dam);
	}

	if (resists_spell(ch, victim))
	{
		if (GET_SPEC(ch, CLASS_PSIONICIST, SPEC_PYROKINETIC))
		{
			dam = detonate_pyrokinetic_shrug(dam);
		}
		else if (GET_CLASS(ch, CLASS_MINDFLAYER) && IS_NPC(victim))
		{
			dam = detonate_mindflayer_shrug(dam);
		}
		else
		{
			return;
		}
	}

	if (!StatSave(victim, APPLY_POW, (GET_LEVEL(victim) - GET_LEVEL(ch)) / 5) &&
	    !IS_ELITE(victim))
	{
		spell_damage(ch, victim, dam, SPLDAM_PSI, SPLDAM_NOSHRUG, &messages);
	}
	else
	{
		spell_damage(ch, victim, detonate_saved(dam), SPLDAM_PSI, SPLDAM_NOSHRUG,
			     &messages);
	}

	//  CharWait(ch, (int) (PULSE_SPELLCAST * 1));
}

// Which effect a target suffers after failing both saves.
static int spinal_corruption_effect_roll(const Rolls &rolls)
{
	return rolls.number(1, 5);
}

static int spinal_corruption_lag()
{
	return (int)(0.75 * PULSE_VIOLENCE);
}

static int spinal_corruption_slow_duration()
{
	return 3;
}

std::string spinal_corruption_facts(P_char /*ch*/)
{
	return "  A target that makes its first power save only feels a twinge.\n"
	       "  One that makes its second suffers nothing more.\n"
	       "  One that fails both falls prone and suffers one effect:\n" +
	       fact("Chance of each effect",
		    "1 in " + std::to_string(spinal_corruption_effect_roll(highest_rolls))) +
	       fact("Lag on the target", seconds(spinal_corruption_lag())) +
	       "  Sleep, or an attempt to silence it.\n" +
	       fact("Slowness if not already under it",
		    game_hours(spinal_corruption_slow_duration())) +
	       "  Lifeleak poison.\n";
}

void spell_spinal_corruption(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			     P_char victim, P_obj /*obj*/)
{
	struct affected_type af;

	if (!ch)
	{
		logit(LOG_EXIT, "spell_spinal_corruption called in psionics.c without ch");
		exit(1);
	}
	if (!IS_ALIVE(ch))
	{
		send_to_char("Stay still. You are dead.&n\r\n", ch);
		return;
	}
	if (!IS_ALIVE(victim))
	{
		act("&+MBut it's dead already!", TRUE, ch, 0, NULL, TO_CHAR);
		return;
	}

	if (affected_by_spell(ch, TAG_CONJURED_PET))
	{
		return;
	}

	if (CheckMindflayerPresence(ch))
	{
		send_to_char("You sense an ethereal disturbance and abort your spell!\r\n", ch);
		return;
	}

	if (StatSave(victim, APPLY_POW,
		     MIN(1, GET_LEVEL(ch) - GET_LEVEL(victim)) * POW_DIFF(ch, victim)))
	{
		send_to_char("&+RYou feel a twinge of pain along your spine.&n\r\n", victim);
		return;
	}
	appear(ch);

	act("&+RYou smile as you sense the agony $N&+R is feeling.", TRUE, ch, 0, victim, TO_CHAR);
	act("&+RYou collapse in agony as pure fire envelops your spine!&n", TRUE, ch, 0, victim,
	    TO_VICT);
	act("&+R$N&+R suddenly collapses, screaming in agony!", TRUE, ch, 0, victim, TO_NOTVICT);

	if (!StatSave(victim, APPLY_POW, POW_DIFF(ch, victim)))
	{
		switch (spinal_corruption_effect_roll(live_rolls))
		{
		case 1:
			CharWait(victim, spinal_corruption_lag());
			act("$n falls to the ground, trashing wildly!.", FALSE, victim, 0, 0,
			    TO_ROOM);
			send_to_char(
				"&+LYou feel your body stop responding to your commands, and you fall to the ground, thrashing.&n\r\n",
				victim);
			break;
		case 2:
			if (GET_STAT(victim) > STAT_SLEEPING && !IS_TRUSTED(victim))
			{
				act("&+L$n suddenly loses control, and falls asleep.", FALSE,
				    victim, 0, 0, TO_ROOM);
				send_to_char(
					"&+LYour are overwhelmed with a great desire to get some rest. Yawn.\r\n",
					victim);
				SET_POS(victim, GET_POS(victim) + STAT_SLEEPING);
				update_pos(victim);
			}
			break;
		case 3:
			spell_silence(60, ch, NULL, 0, victim, 0);
			break;
		case 4:
			if (!affected_by_spell(victim, SPELL_SPINAL_CORRUPTION))
			{
				bzero(&af, sizeof(af));
				af.type = SPELL_SPINAL_CORRUPTION;
				af.duration = spinal_corruption_slow_duration();
				af.bitvector2 = AFF2_SLOW;
				affect_to_char(victim, &af);
				act("&+LThe power of your psychic assault renders $N unable to react as quickly!",
				    TRUE, ch, 0, victim, TO_CHAR);
				send_to_char(
					"&+LIt seems as though you aren't as spry as you once were...\r\n",
					victim);
			}
			break;
		case 5:
			poison_lifeleak(level, ch, 0, 0, victim, 0);
			act("$n&n&+G shivers slightly.", TRUE, victim, 0, 0, TO_ROOM);
			send_to_char("&+yYou feel very sick.\n", victim);
			break;
		default:
			break;
		}
		SET_POS(victim, POS_PRONE + GET_STAT(victim));
		update_pos(victim);
		return;
	}
}

// How long mental anguish lasts, in pulses. The caster's own level counts.
static int mental_anguish_duration(P_char ch)
{
	return WAIT_SEC * (GET_LEVEL(ch) / 2);
}

std::string mental_anguish_facts(P_char ch)
{
	return fact("Duration", seconds(mental_anguish_duration(ch)) + " at your level, " +
					std::to_string(GET_LEVEL(ch))) +
	       "  A target that makes its power save is unaffected.\n"
	       "  Effective skill ratings are capped at 10 while it lasts.\n"
	       "  It does not stack.\n";
}

void spell_mental_anguish(int /*level*/, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			  P_char victim, P_obj /*obj*/)
{
	struct affected_type af;

	appear(ch);
	if (CheckMindflayerPresence(ch))
	{
		send_to_char("You sense an ethereal disturbance and abort your spell!\r\n", ch);
		return;
	}
	if (affected_by_spell(victim, SPELL_MENTAL_ANGUISH))
	{
		act("You cannot cause anymore anguish to $m!", TRUE, ch, 0, victim, TO_CHAR);
		return;
	}

	if (StatSave(victim, APPLY_POW, MIN(0, POW_DIFF(ch, victim))))
	{
		send_to_char("&+RYou feel a strange sensation inside your brain.&n\r\n", victim);
		send_to_char("&+RYou try, but fail to induce the anguish in your victim.\r\n", ch);
		return;
	}
	else
	{
		act("$N's eyes roll back as $S brain is filled with raw pain.", TRUE, ch, 0, victim,
		    TO_CHAR);
		act("&+RYour brain is filled with pain, making it hard to concentrate!&n", TRUE, ch,
		    0, victim, TO_VICT);

		bzero(&af, sizeof(af));
		af.type = SPELL_MENTAL_ANGUISH;
		// at 56, this spell will last 56/2 = 28 sec.
		af.duration = mental_anguish_duration(ch);
		af.bitvector5 = AFF5_MENTAL_ANGUISH;
		af.flags = AFFTYPE_SHORT;
		affect_to_char(victim, &af);
		return;
	}
}

// Each cast by a memory blocked character stops on a nonzero roll.
int memory_block_forget_roll(const Rolls &rolls)
{
	return rolls.number(0, 1);
}

static int memory_block_duration(P_char ch)
{
	return MAX(1, GET_LEVEL(ch) / 2) * WAIT_SEC;
}

std::string memory_block_facts(P_char ch)
{
	return fact("Duration", seconds(memory_block_duration(ch))) +
	       fact("Chance each cast fails",
		    "1 in " + std::to_string(memory_block_forget_roll(highest_rolls) -
					     memory_block_forget_roll(lowest_rolls) + 1)) +
	       "  A target that makes its power save is unaffected.\n";
}

void spell_memory_block(int /*level*/, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			P_obj /*obj*/)
{
	if (CheckMindflayerPresence(ch))
	{
		send_to_char("You sense an ethereal disturbance and abort your spell!\r\n", ch);
		return;
	}

	if (StatSave(victim, APPLY_POW, MIN(0, POW_DIFF(ch, victim))))
	{
		// if(StatSave (victim, APPLY_POW, MIN(1, GET_LEVEL(ch) - GET_LEVEL(victim))*POW_DIFF(ch, victim))) {
		send_to_char("&+RYou briefly forget why you're here.&n\r\n", victim);
		return;
	}
	appear(ch);

	act("$N stares around blankly.", TRUE, ch, 0, victim, TO_CHAR);
	act("You seem to have forgotten why you are here!&n", TRUE, ch, 0, victim, TO_VICT);
	act("$N stares around blankly.", TRUE, ch, 0, victim, TO_NOTVICT);

	affect_from_char(victim, SPELL_MEMORY_BLOCK);
	struct affected_type af
	{
	};
	af.type = SPELL_MEMORY_BLOCK;
	af.duration = memory_block_duration(ch);
	af.flags = AFFTYPE_SHORT;
	af.bitvector5 = AFF5_MEMORY_BLOCK;
	affect_to_char(victim, &af);
	return;
}

static int psionic_cloud_duration(int level)
{
	return level;
}

// How much power or movement the cloud takes.
static int psionic_cloud_penalty(const Rolls &rolls, int level)
{
	return rolls.number(level / 4, 35);
}

std::string psionic_cloud_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range penalty = { -psionic_cloud_penalty(highest_rolls, level),
				-psionic_cloud_penalty(lowest_rolls, level) };
	return fact("Power", show_signed(penalty) + " at your level, " + std::to_string(level)) +
	       fact("Movement", show_signed(penalty)) +
	       fact("Duration", game_hours(psionic_cloud_duration(level))) +
	       "  Each amount is rolled once per cast and hits everyone it reaches alike.\n"
	       "  Targets already under a cloud are not affected again.\n";
}

void spell_psionic_cloud(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			 P_char /*victim*/, P_obj /*obj*/)
{
	struct affected_type af;
	struct affected_type af1;
	P_char tch, next;

	if (CheckMindflayerPresence(ch))
	{
		send_to_char("You sense an ethereal disturbance and abort your spell!\r\n", ch);
		return;
	}

	bzero(&af, sizeof(af));
	af.type = SPELL_PSIONIC_CLOUD;
	af.duration = psionic_cloud_duration(level);
	af.modifier = -1 * psionic_cloud_penalty(live_rolls, level);
	af.bitvector = 0;
	af.location = APPLY_POW;

	bzero(&af1, sizeof(af1));
	af1.type = SPELL_PSIONIC_CLOUD;
	af1.duration = psionic_cloud_duration(level);
	af1.modifier = -1 * psionic_cloud_penalty(live_rolls, level);
	af1.bitvector = 0;
	af1.location = APPLY_MOVE;

	for (tch = world[ch->in_room].people; tch; tch = next)
	{
		next = tch->next_in_room;

		if (should_area_hit(ch, tch))
		{
			if (affected_by_spell(tch, SPELL_PSIONIC_CLOUD))
				continue;

			affect_to_char(tch, &af);
			affect_to_char(tch, &af1);
		}
	}
	act("&+LYou summon a dark haze of psionic energy with the power of your mind!", FALSE, ch,
	    0, 0, TO_CHAR);
	act("&+L$n &+Lsquints and a dark haze of psionic energy appears!", FALSE, ch, 0, 0,
	    TO_ROOM);
	zone_spellmessage(
		ch->in_room, FALSE,
		"&+LYou feel weakened as your psyche senses a massive energy influx!\r\n");

	return;
}

static int displacement_duration(int level)
{
	return level - 4;
}

static int displacement_ac(int level)
{
	return -level * 2;
}

std::string displacement_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	// affect_update() removes any duration below -1 on the next tick, as it does 0.
	const int duration = displacement_duration(level);
	return fact("Duration", game_hours(duration < -1 ? 0 : duration) + " at your level, " +
					std::to_string(level)) +
	       fact("Armor class", std::to_string(displacement_ac(level))) +
	       fact("Chance a melee hit on you deals nothing",
		    "1 in " + std::to_string(displacement_absorb_roll(highest_rolls) -
					     displacement_absorb_roll(lowest_rolls) + 1)) +
	       "  Combat mind, and hits that ignore reductions, get through.\n" +
	       fact("Chance to dodge a takedown",
		    std::to_string(displacement_takedown_chance(0)) + " in " +
			    std::to_string(displacement_takedown_roll(highest_rolls)) + ", +" +
			    std::to_string(displacement_takedown_chance(10) -
					   displacement_takedown_chance(0)) +
			    " per 10 levels of the attacker") +
	       "  It has no effect while you already have it.\n";
}

void spell_displacement(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			P_char victim, P_obj /*obj*/)
{
	named_set_ordinary_cast ordinary_cast(victim, SPELL_DISPLACEMENT);
	struct affected_type af;

	if (affected_by_spell(ch, SPELL_DISPLACEMENT))
	{
		send_to_char("You're already affected by displacement!\r\n", ch);
		return;
	}

	bzero(&af, sizeof(af));
	af.type = SPELL_DISPLACEMENT;
	af.duration = displacement_duration(level);
	af.modifier = displacement_ac(level);
	af.location = APPLY_AC;
	affect_to_char(victim, &af);

	act("&+WYour form shimmers, and you appear displaced.", FALSE, ch, 0, victim, TO_CHAR);
	act("&+W$N shimmers and appears a few inches away.", TRUE, ch, 0, victim, TO_ROOM);
}

void spell_domination(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		      P_obj /*obj*/)
{
	if (victim == ch)
	{
		send_to_char("Dominate yourself? You're wierd.\r\n", ch);
		return;
	}
	if (training_dummy_is(victim))
	{
		send_to_char("The training dummy has no mind to dominate.\r\n", ch);
		return;
	}
	if (GET_MASTER(victim) || GET_MASTER(ch) || level < GET_LEVEL(victim) ||
	    StatSave(victim, APPLY_POW, POW_DIFF(ch, victim)))
		return;
	/*
	   if (victim->leader)
	   stop_follower(victim);
	 */
	setup_pet(victim, ch, MAX(1, number(level - 20, level)), 0);
	add_follower(victim, ch);
	act("Your will dominates $N!", FALSE, ch, 0, victim, TO_CHAR);
	act("Your will is dominated by $n!", FALSE, ch, 0, victim, TO_VICT);

	return;
}

static int ectoplasmic_form_duration(int level)
{
	return level / 2;
}

std::string ectoplasmic_form_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Duration", game_hours(ectoplasmic_form_duration(level)) + " at your level, " +
					std::to_string(level)) +
	       "  It ends when you become visible again.\n"
	       "  Casting it again renews the duration.\n";
}

void spell_ectoplasmic_form(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			    P_char victim, P_obj obj)
{
	struct affected_type af;

	if (!((victim || obj) && ch))
	{
		logit(LOG_EXIT, "assert: bogus parms in ectoplasmic form");
		exit(1);
	}
	if (obj)
	{
		if (!IS_SET(obj->extra_flags, ITEM_INVISIBLE) && IS_SET(obj->wear_flags, ITEM_TAKE))
		{
			act("&+L$p turns invisible.", FALSE, ch, obj, 0, TO_CHAR);
			act("&+L$p turns invisible.", TRUE, ch, obj, 0, TO_ROOM);
			set_obj_extra_flags(obj, obj->extra_flags | (ITEM_INVISIBLE));
			set_obj_extra_flags(obj, obj->extra_flags & ~(ITEM_LIT));
		}
	}
	else
	{ /*
	   * Then it is a PC | NPC
	   */
		if (!affected_by_spell(victim, SPELL_ECTOPLASMIC_FORM))
		{
			act("&+L$n's form shimmers and then fades from sight..", TRUE, victim, 0, 0,
			    TO_ROOM);
			send_to_char("&+LYou shimmer, then fade from sight.\r\n", victim);

			bzero(&af, sizeof(af));

			af.type = SPELL_ECTOPLASMIC_FORM;
			af.duration = ectoplasmic_form_duration(level);
			af.bitvector3 = AFF3_ECTOPLASMIC_FORM;
			affect_to_char(victim, &af);
		}
		else
		{
			struct affected_type *af1;

			for (af1 = victim->affected; af1; af1 = af1->next)
				if (af1->type == SPELL_ECTOPLASMIC_FORM)
				{
					af1->duration = ectoplasmic_form_duration(level);
				}
		}
	}
}
static int ego_whip_damage(const Rolls &rolls, int level)
{
	const int dam_each[61] = { 0,  3,  4,  4,  5,  6,  6,  6,  7,  7,  7,  7,  7,  8,  8,  8,
				   9,  9,  9,  10, 10, 10, 11, 11, 11, 12, 12, 12, 13, 13, 13, 14,
				   14, 14, 15, 15, 15, 16, 16, 16, 17, 17, 17, 18, 18, 18, 19, 19,
				   19, 20, 20, 21, 21, 21, 22, 22, 22, 23, 23, 23, 24 };

	level = MIN(level, static_cast<int>(ARRAY_SIZE(dam_each)) - 1);
	level = MAX(0, level);
	return rolls.number(dam_each[level] >> 1, dam_each[level] << 1);
}

// A target that makes its power save takes two thirds.
static int ego_whip_saved(int dam)
{
	return (int)(dam / 1.5);
}

// Tower of iron will halves it, after the save.
static int ego_whip_iron_will(int dam)
{
	return dam / 2;
}

std::string ego_whip_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range hit = { ego_whip_damage(lowest_rolls, level),
			    ego_whip_damage(highest_rolls, level) };
	return fact("Damage", show_landing(hit) + " at your level, " + std::to_string(level)) +
	       fact("If the target makes a power save",
		    show_landing({ ego_whip_saved(hit.low), ego_whip_saved(hit.high) })) +
	       fact("With tower of iron will",
		    "half of either, " + show_landing({ ego_whip_iron_will(ego_whip_saved(hit.low)),
							ego_whip_iron_will(hit.high) })) +
	       "  Globes, minor globes and spirit wards stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_ego_whip(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		    P_obj /*obj*/)
{
	int dam;

	dam = ego_whip_damage(live_rolls, level);
	// dam = dice(4,6) * 2;

	if (StatSave(victim, APPLY_POW, POW_DIFF(ch, victim)))
		dam = ego_whip_saved(dam);
	if (IS_AFFECTED3(victim, AFF3_TOWER_IRON_WILL))
		dam = ego_whip_iron_will(dam);

	act("&+MYou mentally beat upon $N's ego.", TRUE, ch, 0, victim, TO_CHAR);
	act("&+M$n mentally beats upon your mind with stunning force!", TRUE, ch, 0, victim,
	    TO_VICT);
	act("&+M$n squints and $N&+M screams out in pain, holding $S head!", TRUE, ch, 0, victim,
	    TO_NOTVICT);

	damage(ch, victim, dam, SPELL_EGO_WHIP);
}

static int energy_containment_duration(int level)
{
	return level / 2 + 7;
}

static int energy_containment_save(int level)
{
	return -(level / 8);
}

std::string energy_containment_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	std::string text = fact("Duration", game_hours(energy_containment_duration(level)) +
						    " at your level, " + std::to_string(level));
	if (energy_containment_save(level))
		text += fact("Saving throw against spells",
			     std::to_string(energy_containment_save(level)));
	return text +
	       fact("Fire, cold, lightning, gas, acid and earth damage you take",
		    share_percent(energy_containment_share())) +
	       "  That is one of the spell damage modifiers.\n"
	       "  Casting it again renews the duration.\n";
}

void spell_energy_containment(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			      P_char victim, P_obj /*obj*/)
{
	named_set_ordinary_cast ordinary_cast(victim, SPELL_ENERGY_CONTAINMENT);
	struct affected_type af;

	if (!(victim && ch))
	{
		logit(LOG_EXIT, "assert: bogus parms in energy containment");
		exit(1);
	}
	if (affected_by_spell(ch, SPELL_ENERGY_CONTAINMENT))
	{
		struct affected_type *af1;

		for (af1 = victim->affected; af1; af1 = af1->next)
			if (af1->type == SPELL_ENERGY_CONTAINMENT)
			{
				af1->duration = energy_containment_duration(level);
			}
		return;
	}

	bzero(&af, sizeof(af));
	af.type = SPELL_ENERGY_CONTAINMENT;
	af.duration = energy_containment_duration(level);
	af.location = APPLY_SAVING_SPELL;
	af.modifier = energy_containment_save(level);
	affect_to_char(victim, &af);

	send_to_char("You can now absorb some forms of energy.\r\n", victim);

	return;
}

static int enhance_armor_duration()
{
	return 25;
}

static int enhance_armor_ac(int level)
{
	return -1 * level;
}

std::string enhance_armor_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Armor class", std::to_string(enhance_armor_ac(level)) + " at your level, " +
					   std::to_string(level)) +
	       fact("Duration", game_hours(enhance_armor_duration())) +
	       "  It stacks with other armor spells.\n"
	       "  Casting it again renews the duration.\n";
}

void spell_enhance_armor(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			 P_char victim, P_obj /*obj*/)
{
	named_set_ordinary_cast ordinary_cast(victim, SPELL_ENHANCE_ARMOR);
	struct affected_type af;

	if (!(victim && ch))
	{
		logit(LOG_EXIT, "assert: bogus parms in enhance armor");
		exit(1);
	}

	// Allowing this to stack with other armor spells, since it's "enhance" and there's flesh armor too.
	if (!affected_by_spell(ch, SPELL_ENHANCE_ARMOR))
	{
		bzero(&af, sizeof(af));
		af.type = SPELL_ENHANCE_ARMOR;
		af.duration = enhance_armor_duration();
		af.location = APPLY_AC;
		af.modifier = enhance_armor_ac(level);

		affect_to_char(victim, &af);
		send_to_char("&+BBands of psionic force surround you!\r\n", victim);
		act("$n becomes a little fuzzy as mist like bands surround $m.", TRUE, victim, 0, 0,
		    TO_ROOM);
	}
	else
	{
		struct affected_type *af1;

		for (af1 = victim->affected; af1; af1 = af1->next)
		{
			if (af1->type == SPELL_ENHANCE_ARMOR)
			{
				send_to_char("&+BThe bands of psionic force are refreshed!&n\r\n",
					     victim);
				af1->duration = enhance_armor_duration();
			}
		}
	}
}

static int enhanced_strength_duration(int level)
{
	return level;
}

static int enhanced_strength_bonus(int level)
{
	return 1 + (level / 4);
}

std::string enhanced_strength_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Strength", "+" + std::to_string(enhanced_strength_bonus(level)) +
					" at your level, " + std::to_string(level)) +
	       fact("Duration", game_hours(enhanced_strength_duration(level))) +
	       "  It has no effect while you already have it.\n";
}

void spell_enhanced_strength(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			     P_char victim, P_obj /*obj*/)
{
	named_set_ordinary_cast ordinary_cast(victim, SPELL_ENHANCED_STR);
	struct affected_type af;

	if (affected_by_spell(victim, SPELL_ENHANCED_STR))
	{
		send_to_char("You can't get any stronger than this.\r\n", victim);
		if (ch != victim)
			send_to_char("No effect...\r\n", ch);
		return;
	}
	bzero(&af, sizeof(af));
	af.type = SPELL_ENHANCED_STR;
	af.duration = enhanced_strength_duration(level);
	af.location = APPLY_STR;
	af.modifier = enhanced_strength_bonus(level);
	affect_to_char(victim, &af);

	send_to_char("Your muscles begin to expand.\r\n", victim);

	act("$n looks physically stronger.", TRUE, victim, 0, 0, TO_ROOM);

	return;
}

static int enhanced_dexterity_duration(int level)
{
	return level;
}

static int enhanced_dexterity_bonus(int level)
{
	return 1 + (level / 4);
}

std::string enhanced_dexterity_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Dexterity", "+" + std::to_string(enhanced_dexterity_bonus(level)) +
					 " at your level, " + std::to_string(level)) +
	       fact("Duration", game_hours(enhanced_dexterity_duration(level))) +
	       "  It has no effect while you already have it.\n";
}

void spell_enhanced_dexterity(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			      P_char victim, P_obj /*obj*/)
{
	named_set_ordinary_cast ordinary_cast(victim, SPELL_ENHANCED_DEX);
	struct affected_type af;

	if (affected_by_spell(victim, SPELL_ENHANCED_DEX))
	{
		send_to_char("You can't get any more dextrous than this.\r\n", victim);
		if (ch != victim)
			send_to_char("No effect...\r\n", ch);
		return;
	}
	bzero(&af, sizeof(af));
	af.type = SPELL_ENHANCED_DEX;
	af.duration = enhanced_dexterity_duration(level);
	af.location = APPLY_DEX;
	af.modifier = enhanced_dexterity_bonus(level);
	affect_to_char(victim, &af);

	send_to_char("Your coordination increases greatly.\r\n", victim);

	return;
}

static int enhanced_agility_duration(int level)
{
	return level;
}

static int enhanced_agility_bonus(int level)
{
	return 1 + (level / 4);
}

std::string enhanced_agility_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Agility", "+" + std::to_string(enhanced_agility_bonus(level)) +
				       " at your level, " + std::to_string(level)) +
	       fact("Duration", game_hours(enhanced_agility_duration(level))) +
	       "  It has no effect while you already have it.\n";
}

void spell_enhanced_agility(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			    P_char victim, P_obj /*obj*/)
{
	named_set_ordinary_cast ordinary_cast(victim, SPELL_ENHANCED_AGI);
	struct affected_type af;

	if (affected_by_spell(victim, SPELL_ENHANCED_AGI))
	{
		send_to_char("You can't get any more agile than this.\r\n", victim);
		if (ch != victim)
			send_to_char("No effect...\r\n", ch);
		return;
	}
	bzero(&af, sizeof(af));
	af.type = SPELL_ENHANCED_AGI;
	af.duration = enhanced_agility_duration(level);
	af.location = APPLY_AGI;
	af.modifier = enhanced_agility_bonus(level);
	affect_to_char(victim, &af);

	send_to_char("You feel more agile.\r\n", victim);

	return;
}

static int enhanced_constitution_duration(int level)
{
	return level;
}

static int enhanced_constitution_bonus(int level)
{
	return 1 + (level / 5);
}

std::string enhanced_constitution_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Constitution", "+" + std::to_string(enhanced_constitution_bonus(level)) +
					    " at your level, " + std::to_string(level)) +
	       fact("Duration", game_hours(enhanced_constitution_duration(level))) +
	       "  It has no effect while you already have it.\n";
}

void spell_enhanced_constitution(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
				 P_char victim, P_obj /*obj*/)
{
	named_set_ordinary_cast ordinary_cast(victim, SPELL_ENHANCED_CON);
	struct affected_type af;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (affected_by_spell(victim, SPELL_ENHANCED_CON))
	{
		send_to_char("You can't get any more virile than this.\r\n", victim);
		if (ch != victim)
			send_to_char("No effect...\r\n", ch);
		return;
	}
	bzero(&af, sizeof(af));
	af.type = SPELL_ENHANCED_CON;
	af.duration = enhanced_constitution_duration(level);
	af.location = APPLY_CON;
	af.modifier = enhanced_constitution_bonus(level);
	affect_to_char(victim, &af);

	send_to_char("You feel more vitalized.\r\n", victim);
}

static int flesh_armor_duration()
{
	return 25;
}

static int flesh_armor_ac(int level)
{
	return (int)(-1 * level);
}

std::string flesh_armor_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Armor class", std::to_string(flesh_armor_ac(level)) + " at your level, " +
					   std::to_string(level)) +
	       fact("Duration", game_hours(flesh_armor_duration())) +
	       "  It has no effect over another armor-type spell.\n"
	       "  Casting it again renews the duration.\n";
}

void spell_flesh_armor(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
		       P_char victim, P_obj /*obj*/)
{
	named_set_ordinary_cast ordinary_cast(victim, SPELL_FLESH_ARMOR);
	struct affected_type af;
	bool shown;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (IS_AFFECTED(victim, AFF_ARMOR))
	{
		struct affected_type *af1;
		shown = FALSE;

		for (af1 = victim->affected; af1; af1 = af1->next)
		{
			if (af1->type == SPELL_FLESH_ARMOR)
			{
				if (!shown)
				{
					send_to_char("&+RYour flesh rehardens.\r\n", victim);
					shown = TRUE;
				}
				af1->duration = flesh_armor_duration();
			}
		}
		if (!shown)
		{
			send_to_char("&+WYou're already affected by an armor-type spell.&n\n", ch);
		}
		return;
	}

	bzero(&af, sizeof(af));
	af.type = SPELL_FLESH_ARMOR;
	af.duration = flesh_armor_duration();
	af.location = APPLY_AC;
	af.bitvector = AFF_ARMOR;
	af.bitvector5 = AFF5_FLESH_ARMOR;
	af.modifier = flesh_armor_ac(level);
	affect_to_char(victim, &af);

	send_to_char("&+RYour flesh gains a steel-like hardness.\r\n", victim);
	act("$N's &+Rflesh begins to shimmer, then gains a harder look to it.", TRUE, ch, 0, victim,
	    TO_ROOM);
}

static int inertial_barrier_duration()
{
	return 30;
}

std::string inertial_barrier_facts(P_char /*ch*/)
{
	return fact("Duration", game_hours(inertial_barrier_duration())) +
	       fact("Melee attacks against you",
		    share_percent(inertial_barrier_attack_share()) +
			    " of normal, rounded up, before any hit rolls") +
	       fact("An attacker with combat mind keeps at least",
		    share_percent(combat_mind_attack_floor())) +
	       "  Casting it again renews the duration.\n";
}

void spell_inertial_barrier(int /*level*/, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			    P_char victim, P_obj /*obj*/)
{
	struct affected_type af;

	if (!(victim && ch))
	{
		logit(LOG_EXIT, "assert: bogus params (inertial barrier)");
		exit(1);
	}
	if (affected_by_spell(ch, SPELL_INERTIAL_BARRIER))
	{
		struct affected_type *af1;

		for (af1 = victim->affected; af1; af1 = af1->next)
			if (af1->type == SPELL_INERTIAL_BARRIER)
			{
				af1->duration = inertial_barrier_duration();
			}
		return;
	}

	bzero(&af, sizeof(af));
	af.type = SPELL_INERTIAL_BARRIER;
	af.duration = inertial_barrier_duration();
	af.modifier = 0;
	af.bitvector3 = AFF3_INERTIAL_BARRIER;
	affect_to_char(victim, &af);

	send_to_char(
		"You feel uneasy, almost as if a headache is coming on.  Almost as if you're slightly in control of reality now.\n",
		victim);

	return;
}

static int inflict_pain_damage(const Rolls &rolls, int level)
{
	return rolls.dice((int)(MIN(level, 31) * 1.5), 10);
}

// A target that makes its power save takes two thirds.
static int inflict_pain_saved(int dam)
{
	return (int)(dam / 1.5);
}

std::string inflict_pain_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range hit = { inflict_pain_damage(lowest_rolls, level),
			    inflict_pain_damage(highest_rolls, level) };
	return fact("Psionic damage", show(hit) + " at your level, " + std::to_string(level)) +
	       fact("If the target makes a power save",
		    show({ inflict_pain_saved(hit.low), inflict_pain_saved(hit.high) })) +
	       "  It cannot kill. A globe of invulnerability stops it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_inflict_pain(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			P_obj /*obj*/)
{
	struct damage_messages messages = { "$N &+Bscreams out in &+Rpain!&N",
					    "&+BA horrible &+Rpain&N wracks your brain!",
					    "$N &+Bscreams out in &+Rpain!&N" };
	int dam = inflict_pain_damage(live_rolls, level);

	if (StatSave(victim, APPLY_POW, POW_DIFF(ch, victim)))
		dam = inflict_pain_saved(dam);

	spell_damage(ch, victim, dam, SPLDAM_PSI, SPLDAM_GLOBE | RAWDAM_NOKILL, &messages);
}

static int intellect_fortress_duration()
{
	return 24;
}

static int intellect_fortress_intelligence(int level)
{
	return 1 + level / 5;
}

std::string intellect_fortress_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Intelligence", "+" + std::to_string(intellect_fortress_intelligence(level)) +
					    " at your level, " + std::to_string(level)) +
	       fact("Duration", game_hours(intellect_fortress_duration())) +
	       "  Casting it again renews the duration.\n";
}

void spell_intellect_fortress(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			      P_char victim, P_obj /*obj*/)
{
	named_set_ordinary_cast ordinary_cast(ch, SPELL_INTELLECT_FORTRESS);
	struct affected_type af;

	if (affected_by_spell(ch, SPELL_INTELLECT_FORTRESS))
	{
		struct affected_type *af1;

		for (af1 = victim->affected; af1; af1 = af1->next)
			if (af1->type == SPELL_INTELLECT_FORTRESS)
			{
				af1->duration = intellect_fortress_duration();
			}
		return;
	}

	bzero(&af, sizeof(af));
	af.type = SPELL_INTELLECT_FORTRESS;
	af.duration = intellect_fortress_duration();
	af.location = APPLY_INT;
	af.modifier = intellect_fortress_intelligence(level);
	affect_to_char(ch, &af);

	send_to_char("&+WA virtual fortress forms around you.\r\n", ch);

	return;
}

// The most health lent at once, at the caster's own level.
static int lend_health_most(P_char ch)
{
	return 25 + GET_LEVEL(ch) * 3 / 2;
}

static float lend_health_ratio()
{
	return get_property("spell.lendHealth.healRatio", 1.000);
}

// What the target gets for `hp` lent.
static int lend_health_healing(int hp)
{
	return (int)(lend_health_ratio() * hp);
}

// What the caster pays for `hp` lent.
static int lend_health_cost(int hp)
{
	return (int)(hp / lend_health_ratio());
}

// How far short of the target's full health this lending stops.
static int lend_health_short_roll(const Rolls &rolls)
{
	return rolls.number(1, 4);
}

// The caster may not end below this.
static int lend_health_lowest_health()
{
	return -9;
}

std::string lend_health_facts(P_char ch)
{
	const int most = MIN(50, lend_health_most(ch));
	return fact("Healing", "up to " + std::to_string(lend_health_healing(most)) +
				       " at your level, " + std::to_string(GET_LEVEL(ch))) +
	       fact("Your health spent", "up to " + std::to_string(lend_health_cost(most))) +
	       "  Never more than the target is missing. Healing modifiers apply.\n" +
	       fact("The target stops short of full health by",
		    show({ lend_health_short_roll(lowest_rolls),
			   lend_health_short_roll(highest_rolls) })) +
	       fact("Refused if it would leave you below",
		    std::to_string(lend_health_lowest_health()) + " health") +
	       "  Below 1 health you pass out.\n";
}

void spell_lend_health(int /*level*/, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		       P_obj /*obj*/)
{
	int hp;

	if (ch == victim)
	{
		send_to_char("Lend health to yourself? What a wierdo.\r\n", ch);
		return;
	}
	hp = MIN(50, GET_MAX_HIT(victim) - GET_HIT(victim));
	hp = MIN(lend_health_most(ch), hp);

	if (hp <= 0)
	{
		act("Nice thought, but $N doesn't need healing.", 0, ch, 0, victim, TO_CHAR);
		return;
	}
	if (GET_HIT(ch) - hp < lend_health_lowest_health())
	{
		send_to_char("You do not feel healthy enough yourself!\r\n", ch);
		return;
	}

	heal(victim, ch, lend_health_healing(hp),
	     GET_MAX_HIT(victim) - lend_health_short_roll(live_rolls));

	GET_HIT(ch) -= lend_health_cost(hp);
	if (GET_HIT(ch) > GET_MAX_HIT(ch))
		GET_HIT(ch) = GET_MAX_HIT(ch);
	if (GET_HIT(ch) < 1)
	{
		int tmp = GET_HIT(ch) - 1;
		GET_HIT(ch) = 1;
		act("&+WExhausted, $n &+Wpasses out!", FALSE, ch, 0, 0, TO_ROOM);
		send_to_char("&+WHealth reserves exhausted, you pass out!\r\n", ch);
		KnockOut(ch, -(int)tmp);
	}

	if (GET_HIT(victim) > GET_MAX_HIT(victim))
		GET_HIT(victim) = GET_MAX_HIT(victim);

	update_pos(victim);
	update_pos(ch);

	act("&+WYou lend some of your health to $N.", 0, ch, 0, victim, TO_CHAR);
	act("&+W$n lends you some of $s health.", 0, ch, 0, victim, TO_VICT);

	return;
}

// Confuse stops once the levels of those it reached add up to this.
static int confuse_target_levels(int level)
{
	return level * 3;
}

// What a target that failed its save suffers: see the switch in spell_confuse().
static int confuse_effect_roll(const Rolls &rolls)
{
	return rolls.number(1, 10);
}

static int confuse_stun()
{
	return PULSE_VIOLENCE * 2;
}

// A player turning on someone: each person in the room is picked on a roll up to the limit.
static int confuse_turn_roll(const Rolls &rolls)
{
	return rolls.number(1, 101);
}

static int confuse_turn_limit()
{
	return 30;
}

// The extra mana a githyanki pays.
static int confuse_githyanki_mana()
{
	return 50;
}

std::string confuse_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const std::string in_all = " in " + std::to_string(confuse_effect_roll(highest_rolls));
	std::string text =
		fact("Stops after reaching target levels totalling",
		     std::to_string(confuse_target_levels(level)) + " at your level, " +
			     std::to_string(level)) +
		"  A target that fails its power save suffers one of these:\n" +
		fact("Stunned", "3" + in_all + ", up to " + seconds(confuse_stun()) +
					"; fear saves shorten or stop it") +
		fact("Stops fighting, and a player flees", "3" + in_all) +
		fact("Nothing", "2" + in_all) +
		fact("A player may turn on someone in the room", "2" + in_all) +
		fact("Chance for each person there, until one is picked",
		     std::to_string(confuse_turn_limit() - confuse_turn_roll(lowest_rolls) + 1) +
			     " in " + std::to_string(confuse_turn_roll(highest_rolls))) +
		"  Elites cannot be stunned. Greater races, plants, golems and constructs\n"
		"  may resist a stun, more often the higher their level.\n";
	if (GET_RACE(ch) == RACE_GITHYANKI)
		text += fact("Extra mana for a githyanki",
			     std::to_string(confuse_githyanki_mana()));
	return text;
}

void spell_confuse(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim, P_obj /*obj*/)
{
	int temp, max_level = 0;
	P_char tch, next;
	P_char cht;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (victim == ch)
	{
		send_to_char("You suddenly decide against that, oddly enough.\r\n", ch);
		return;
	}
	appear(ch);

	if (GET_CLASS(ch, CLASS_BARD))
	{
		act("&+yYou &+Wsin&+Yg a s&+yong whic&+Yh seem&+Ws to con&+Yfuse you&+yr enemies thou&+Yght&+Ws!",
		    FALSE, ch, 0, 0, TO_CHAR);
		act("&+y$n &+Wsin&+Ygs a s&+yong whic&+Yh seem&+Ws to con&+Yfuse you&+yr thou&+Yght&+Ws!",
		    FALSE, ch, 0, 0, TO_ROOM);
	}
	else
	{
		act("&+LYou send out a wave of confusion!", FALSE, ch, 0, 0, TO_CHAR);
		act("&+L$n sends out a wave of energy!", FALSE, ch, 0, 0, TO_ROOM);
	}

	max_level = confuse_target_levels(level);

	for (tch = world[ch->in_room].people; tch; tch = next)
	{
		next = tch->next_in_room;

		if (should_area_hit(ch, tch))
		{
			if (max_level <= 0)
				break;
			max_level -= GET_LEVEL(tch);

			if (!StatSave(tch, APPLY_POW, POW_DIFF(ch, tch)))
			{
				temp = confuse_effect_roll(live_rolls);
				switch (temp)
				{
				case 1:
				case 2:
				case 3:
					Stun(tch, ch, confuse_stun(), TRUE);
					// Stun(tch, (2 * PULSE_VIOLENCE));
					break;
				case 4:
				case 5:

				case 6:
					if (IS_FIGHTING(tch))
						stop_fighting(tch);
					if ((!(IS_NPC(tch))) && (!(GET_RACE(tch) == RACE_GOLEM)))
					{
						do_flee(tch, 0, 2);
					}
					break;

				case 7:
				case 8:
					break;
				case 9:
				case 10:
					if (IS_NPC(tch))
						break;
					for (cht = world[ch->in_room].people; cht;
					     cht = cht->next_in_room)
					{
						if (confuse_turn_roll(live_rolls) <=
						    confuse_turn_limit())
						{
							if (cht != tch)
							{
								stop_fighting(tch);
								set_fighting(tch, cht);
								break;
							}
						}
					}
				}
			}
			else if (IS_NPC(tch) && CAN_SEE(tch, ch))
			{
				remember(tch, ch);
				if (!IS_FIGHTING(tch))
					MobStartFight(tch, ch);
			}
		}
	}
	// lets drain some extra mana if it's a gith. - Kvark
	if (GET_RACE(ch) == RACE_GITHYANKI)
		GET_MANA(ch) = MAX(0, GET_MANA(ch) - confuse_githyanki_mana());
}

// A target may only try to shrug pyrokinesis on a roll below the limit.
static int pyrokinesis_shrug_roll(const Rolls &rolls)
{
	return rolls.number(1, 100);
}

static int pyrokinesis_shrug_below()
{
	return 60;
}

// The psionic and the fire damage each roll this.
static int pyrokinesis_damage(const Rolls &rolls, int level)
{
	return rolls.dice(level * 2, 5);
}

static int pyrokinesis_pyrokinetic_fire(int dam)
{
	return (int)(dam * 1.20);
}

static int pyrokinesis_failed_psionic(int dam)
{
	return (int)(dam * 1.2);
}

static int pyrokinesis_failed_fire(int dam)
{
	return (int)(dam * 1.15);
}

static int pyrokinesis_penalty(int level)
{
	return (int)(-1 * (level / 5));
}

static int pyrokinesis_penalty_duration()
{
	return 1;
}

static int pyrokinesis_lag()
{
	return 2 * WAIT_SEC;
}

std::string pyrokinesis_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range hit = { pyrokinesis_damage(lowest_rolls, level),
			    pyrokinesis_damage(highest_rolls, level) };
	Range fire = hit;
	if (GET_SPEC(ch, CLASS_PSIONICIST, SPEC_PYROKINETIC))
		fire = { pyrokinesis_pyrokinetic_fire(hit.low),
			 pyrokinesis_pyrokinetic_fire(hit.high) };
	std::string text =
		fact("Psionic damage", show(hit) + " at your level, " + std::to_string(level)) +
		fact("If the target fails its save",
		     show({ pyrokinesis_failed_psionic(hit.low),
			    pyrokinesis_failed_psionic(hit.high) })) +
		fact("Fire damage first, on an NPC only", show(fire) + ", and it cannot kill") +
		fact("If the NPC fails its save", show({ pyrokinesis_failed_fire(fire.low),
							 pyrokinesis_failed_fire(fire.high) })) +
		"  Players take no fire component; psionic damage and penalties still apply.\n" +
		fact("Chance a target may try to shrug it",
		     std::to_string(pyrokinesis_shrug_below() -
				    pyrokinesis_shrug_roll(lowest_rolls)) +
			     " in " + std::to_string(pyrokinesis_shrug_roll(highest_rolls))) +
		"  A fire elemental, or a target with a fire aura and a fireshield, takes\n"
		"  no psionic damage, and neither the penalty nor your lag applies.\n" +
		"  A shrug stops all of it, and neither the penalty nor your lag applies.\n"
		"  Globes and spirit wards do not stop it.\n";
	if (pyrokinesis_penalty(level))
		text += fact("Penalty if it survives",
			     std::to_string(pyrokinesis_penalty(level)) +
				     " to agility, dexterity or strength, at random") +
			fact("Penalty duration", game_hours(pyrokinesis_penalty_duration())) +
			"  A target already under the penalty does not get another.\n";
	return text + fact("Your lag if the target survives", seconds(pyrokinesis_lag())) +
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_pyrokinesis(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
		       P_char victim, P_obj /*obj*/)
{
	struct affected_type af;
	struct damage_messages messages = {
		"&+mYou ignite a &+rpersonal &+ri&+Rn&+rf&+Re&+rr&+Rn&+ro &+mwithin &N$N's &+mbody.",
		"&+mYou scream in &+Wa&+wg&+Wo&+wn&+Wy &+mas &+rs&+Rea&+rri&+Rng &+rh&+Re&+Ra&+rt &+wi&+rg&+wn&+wi&+rt&+we&+rs and &+rb&+Rur&+Ws&+wt&+Rs &+Ri&+Wn&+wt&+Ro f&+Wl&+wa&+Wm&+Re&+Rs &+mwithin your "
		"body.",
		"&N$N &+mscreams and doubles over in &+Wa&+wg&+Wo&+wn&+Wy &+mas &+rs&+Rea&+rri&+Rng &+rh&+Re&+Ra&+rt &+ri&+Rg&+wn&+Wit&+we&+Rs &+mwithin $S body.",
		"&+mYou set &N$N's &+mwhole body &+Rab&+wl&+Wa&+wz&+Re&+m, leaving nothing but &+Lscorched &+mremains.",
		"&+RBl&+wa&+Wz&+wi&+Rn&+rg i&+Rn&+rf&+Re&+rr&+Rn&+ro &+mgrows from within and &+Lscorches &+myour whole body dead.",
		"&+RRa&+rgi&+Rng &+rf&+Rla&+rme&+Rs &+Wb&+wu&+Wr&+ws&+Wt &+mfrom within and &+We&+wn&+Wg&+wu&+Wl&+wf &N$N's &+mwhole body, leaving nothing but &+Lscorched &+mremains.",
		0
	};

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
		return;

	// 40% harder to shrug, same as crush
	if (pyrokinesis_shrug_roll(live_rolls) < pyrokinesis_shrug_below() &&
	    resists_spell(ch, victim))
		return;

	int phys_dam = pyrokinesis_damage(live_rolls, level);
	int fire_dam = pyrokinesis_damage(live_rolls, level);

	if (GET_SPEC(ch, CLASS_PSIONICIST, SPEC_PYROKINETIC))
		fire_dam = pyrokinesis_pyrokinetic_fire(fire_dam);

	int mod = get_default_save_mod(victim, ch, SAVING_SPELL, SPELL_PYROKINESIS);
	if (!NewSaves(victim, SAVING_SPELL, mod))
	{
		phys_dam = pyrokinesis_failed_psionic(phys_dam);
		fire_dam = pyrokinesis_failed_fire(fire_dam);
	}

	if (IS_NPC(victim))
	{
		act("&+LYou &+mwill &+rthe f&+Rl&+Ya&+Rm&+res &+Lof the &+rabyss &+Lto overwhelm and consume your foe...",
		    FALSE, ch, 0, 0, TO_CHAR);
		act("&+L$n &+mwills &+rthe f&+Rl&+Ya&+Rm&+res &+Lof the &+rabyss &+Lto overwhelm and consume thier foe...",
		    FALSE, ch, 0, 0, TO_ROOM);
		spell_damage(ch, victim, fire_dam, SPLDAM_FIRE,
			     SPLDAM_NOSHRUG | SPLDAM_NODEFLECT | RAWDAM_NOKILL, 0);
		if (IS_ALIVE(victim))
		{
			if ((IS_AFFECTED2(victim, AFF2_FIRE_AURA) &&
			     IS_AFFECTED2(victim, AFF2_FIRESHIELD)) ||
			    GET_RACE(victim) == RACE_F_ELEMENTAL)
				return;
			if (spell_damage(ch, victim, phys_dam, SPLDAM_PSI,
					 SPLDAM_NOSHRUG | SPLDAM_NODEFLECT,
					 &messages) != DAM_NONEDEAD)
				return;
		}
	}

	else
	{
		// Pyrokinesis intentionally has no fire-damage component against players.
		if (IS_ALIVE(victim))
		{
			if ((IS_AFFECTED2(victim, AFF2_FIRE_AURA) &&
			     IS_AFFECTED2(victim, AFF2_FIRESHIELD)) ||
			    GET_RACE(victim) == RACE_F_ELEMENTAL)
				return;
			if (spell_damage(ch, victim, phys_dam, SPLDAM_PSI,
					 SPLDAM_NOSHRUG | SPLDAM_NODEFLECT,
					 &messages) != DAM_NONEDEAD)
				return;
		}
	}
	if (!affected_by_spell(victim, SPELL_PYROKINESIS))
	{
		bzero(&af, sizeof(af));
		af.type = SPELL_PYROKINESIS;
		af.duration = pyrokinesis_penalty_duration();
		af.modifier = pyrokinesis_penalty(level);

		act("&+m$n &+msuddenly looks in pain as $e moves.&n", FALSE, victim, 0, 0, TO_ROOM);

		switch (number(0, 2))
		{
		case 0:
			send_to_char("&+mThe heat damages your muscles, you feel less agile.&n\r\n",
				     victim);
			af.location = APPLY_AGI;
			break;

		case 1:
			send_to_char(
				"&+mThe heat damages your muscles, you feel less dexterous.&n\r\n",
				victim);
			af.location = APPLY_DEX;
			break;

		case 2:
			send_to_char("&+mThe heat damages your muscles, you feel weaker.&n\r\n",
				     victim);
			af.location = APPLY_STR;
			break;
		default:
			break;
		}
		affect_to_char(victim, &af);
	}
	CharWait(ch, pyrokinesis_lag());
}

static int celerity_vitality(const Rolls &rolls, int level)
{
	return rolls.dice(3, level / 2);
}

// The health it costs, as psionic damage to the caster.
static int celerity_cost(int movepoints)
{
	return movepoints * 4;
}

std::string celerity_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range gain = { celerity_vitality(lowest_rolls, level),
			     celerity_vitality(highest_rolls, level) };
	return fact("Movement restored", show(gain) + " at your level, " + std::to_string(level)) +
	       fact("Psionic damage to yourself",
		    show({ celerity_cost(gain.low), celerity_cost(gain.high) })) +
	       "  It refuses if you are missing less than half of the roll.\n"
	       "  Spell damage modifiers apply to your cost, and it can kill you.\n";
}

void spell_celerity(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		    P_obj /*obj*/)
{
	int movepoints;

	if (!IS_ALIVE(ch) || ch->in_room == NOWHERE)
		return;

	movepoints = celerity_vitality(live_rolls, level);

	if (GET_VITALITY(ch) > (GET_MAX_VITALITY(ch) - (movepoints / 2)))
	{
		send_to_char(
			"You are quite capable of running right now, no need for extra boost.\n",
			ch);
		return;
	}

	act("&+WYou concentrate and attempt to transform part of your lifeforce....&n", FALSE, ch,
	    0, victim, TO_CHAR);
	act("$N &+Wconcentrates and pales visibly.&n", FALSE, ch, 0, victim, TO_NOTVICT);

	if (spell_damage(ch, ch, celerity_cost(movepoints), SPLDAM_PSI,
			 SPLDAM_NODEFLECT | SPLDAM_NOSHRUG, 0) != DAM_NONEDEAD)
		return;

	GET_VITALITY(ch) = MIN(GET_VITALITY(ch) + movepoints, GET_MAX_VITALITY(ch));

	act("&+yFresh energy pours through your body. &+WYou are invigorated!&n", FALSE, ch, 0, 0,
	    TO_CHAR);
	act("$N &+Wappears invigorated.&n", FALSE, ch, 0, 0, TO_ROOM);

	update_pos(ch);
}

// How many steps on the map depart can move.
static int depart_range()
{
	return get_property("spell.depart.range", 5);
}

// Below this level the room's magic can stop it.
static int depart_free_level()
{
	return 60;
}

static int depart_lag()
{
	return (3 * WAIT_SEC);
}

// In a limited teleport zone it fizzles if the landing is farther than this.
static int depart_limited_range()
{
	return 5;
}

std::string depart_facts(P_char /*ch*/)
{
	return fact("Distance on the map", "up to " + std::to_string(depart_range()) + " rooms") +
	       "  Off the map it takes you to a random room in the zone.\n" +
	       fact("Your lag if it works", seconds(depart_lag())) +
	       fact("Fails in no-teleport rooms, hometowns and oceans",
		    "below level " + std::to_string(depart_free_level())) +
	       fact("Fizzles in rooms 5700-5999 if the landing is farther than",
		    std::to_string(depart_limited_range()) + " rooms") +
	       "  It fails if you are not raidable.\n";
}

void spell_depart(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim, P_obj /*obj*/)
{
	P_char t_ch;
	int tries = 0, to_room, dir;
	int range = depart_range();

	if (!IS_ALIVE(ch) || ch->in_room == NOWHERE)
		return;

	if ((IS_ROOM(ch->in_room, ROOM_NO_TELEPORT) || IS_HOMETOWN(ch->in_room) ||
	     world[ch->in_room].sector_type == SECT_OCEAN) &&
	    level < depart_free_level())
	{
		send_to_char("The magic in this room prevents you from leaving.\n", ch);
		return;
	}

	if (!victim)
		victim = ch;

	if ((ch && !is_Raidable(ch, 0, 0)) || (victim && !is_Raidable(victim, 0, 0)))
	{
		send_to_char("&+WYou are not raidable. The spell fails!\r\n", victim);
		return;
	}

	if (IS_MAP_ROOM(victim->in_room))
	{
		to_room = victim->in_room;

		for (int i = 0; i < range; i++)
		{
			tries = 0;
			do
				dir = number(0, 3);

			while (tries++ < 10 && !VALID_TELEPORT_EDGE(to_room, dir, victim->in_room));

			if (tries < 10)
				to_room = TOROOM(to_room, dir);
		}
	}
	else
	{
		do
		{
			to_room = number(zone_table[world[victim->in_room].zone].real_bottom,
					 zone_table[world[victim->in_room].zone].real_top);
			tries++;
		} while ((IS_ROOM(to_room, ROOM_PRIVATE) || PRIVATE_ZONE(to_room) ||
			  IS_ROOM(to_room, ROOM_NO_TELEPORT) || IS_HOMETOWN(to_room) ||
			  world[to_room].sector_type == SECT_OCEAN) &&
			 tries < 1000);
	}

	if (tries >= 1000)
		to_room = victim->in_room;

	if (LIMITED_TELEPORT_ZONE(victim->in_room) &&
	    how_close(victim->in_room, to_room, depart_limited_range()) < 0)
	{
		send_to_char("The magic gathers, but somehow fades away before taking effect.\n",
			     victim);
		return;
	}

	act("You will yourself to be elsewhere...&n", FALSE, victim, 0, 0, TO_CHAR);
	act("A &+Lblack line&n forms from nowhere and $n falls through it!&n", FALSE, victim, 0, 0,
	    TO_ROOM);

	if (IS_FIGHTING(victim))
		stop_fighting(victim);

	if (victim->in_room != NOWHERE)
		for (t_ch = world[victim->in_room].people; t_ch; t_ch = t_ch->next_in_room)
			if (IS_FIGHTING(t_ch) && GET_OPPONENT(t_ch) == victim)
				stop_fighting(t_ch);

	if (victim->in_room != to_room)
	{
		char_from_room(victim);
		char_to_room(victim, to_room, -1);
	}

	act("and appear somewhere else!&n", FALSE, victim, 0, 0, TO_CHAR);
	act("A &+Lblack line&n appears from nowhere and $n rises directly out of it.", FALSE,
	    victim, 0, 0, TO_ROOM);

	CharWait(victim, depart_lag());
}

static int psionic_wave_blast_damage(const Rolls &rolls, int level)
{
	return rolls.dice(level, 4);
}

// Only a zero lets the target attempt a shrug, on every hit.
static int psionic_wave_blast_shrug_roll(const Rolls &rolls)
{
	return rolls.number(0, 2);
}

// How many waves follow the first hit.
static int psionic_wave_blast_waves()
{
	return 6;
}

static int psionic_wave_blast_wave_damage(const Rolls &rolls, int level)
{
	return rolls.dice(level, 16);
}

static int psionic_wave_blast_failed_save(int dam)
{
	return (int)(dam * 1.25);
}

// A target out of the caster's room takes a third.
static int psionic_wave_blast_away(int dam)
{
	return dam / 3;
}

static int psionic_wave_blast_interval()
{
	return PULSE_VIOLENCE;
}

static int psionic_wave_blast_mana()
{
	return 50;
}

std::string psionic_wave_blast_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const int outcomes = psionic_wave_blast_shrug_roll(highest_rolls) -
			     psionic_wave_blast_shrug_roll(lowest_rolls) + 1;
	const Range wave = { psionic_wave_blast_wave_damage(lowest_rolls, level),
			     psionic_wave_blast_wave_damage(highest_rolls, level) };
	return fact("First psionic hit", show({ psionic_wave_blast_damage(lowest_rolls, level),
						psionic_wave_blast_damage(highest_rolls, level) }) +
						 " at your level, " + std::to_string(level) +
						 "; it cannot kill") +
	       fact("Waves after it", "up to " + std::to_string(psionic_wave_blast_waves()) + ", " +
					      seconds(psionic_wave_blast_interval()) + " apart") +
	       fact("Damage per wave", show(wave)) +
	       fact("If the target fails its power save",
		    show({ psionic_wave_blast_failed_save(wave.low),
			   psionic_wave_blast_failed_save(wave.high) })) +
	       fact("If the target has left your room",
		    "a third, " + show_landing({ psionic_wave_blast_away(wave.low),
						 psionic_wave_blast_away(wave.high) })) +
	       fact("Mana per continuing wave", std::to_string(psionic_wave_blast_mana())) +
	       fact("Chance a target may try to shrug the first hit",
		    "1 in " + std::to_string(outcomes)) +
	       fact("Chance it may try to shrug a wave", "1 in " + std::to_string(outcomes)) +
	       "  This gates the shrug attempt; it does not change the target's shrug rating.\n"
	       "  A shrug of the first hit ends it; a shrugged wave still costs mana.\n"
	       "  Waves need the target to survive what came before.\n"
	       "  The target must be at full health when you cast it.\n"
	       "  Being stunned or off your feet interrupts the waves.\n"
	       "  Globes and spirit wards do not stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_psionic_wave_blast(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			      P_char victim, P_obj /*obj*/)
{
	int dam;
	struct affected_type *af;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
		return;

	/* if(IS_BRAINLESS(victim))
	 {
	   send_to_char("You probe your victim only to discover the lack of intelligence.\r\n", ch);
	   if(IS_SET((ch)->specials.affected_by2, AFF2_CASTING))
	     REMOVE_BIT((ch)->specials.affected_by2, AFF2_CASTING);
	   return;
	 }
	 */

	if (GET_HIT(victim) * 100LL < GET_MAX_HIT(victim) * 20LL)
	{
		send_to_char(
			"Your victim is in excruciating pain. You are unable to find the neural synapses to mentality assault!\r\n",
			ch);
		if (IS_SET((ch)->specials.affected_by2, AFF2_CASTING))
			REMOVE_BIT((ch)->specials.affected_by2, AFF2_CASTING);
		return;
	}

	dam = psionic_wave_blast_damage(live_rolls, level);

	// 66 percent less shrugging of this spell at start.
	if (!psionic_wave_blast_shrug_roll(live_rolls) && resists_spell(ch, victim))
		return;

	if (spell_damage(ch, victim, dam, SPLDAM_PSI,
			 RAWDAM_NOKILL | SPLDAM_NODEFLECT | SPLDAM_NOSHRUG, 0) != DAM_NONEDEAD)
		return;

	if (IS_ALIVE(victim))
	{
		struct affected_type new_affect;

		af = &new_affect;
		memset(af, 0, sizeof(new_affect));
		af->type = SPELL_PSIONIC_WAVE_BLAST;
		af->duration = 1;
		af->modifier = psionic_wave_blast_waves();
		affect_to_char(victim, af);
		add_event(event_psionic_wave_blast, 0, ch, victim, NULL, 0, &level, sizeof(level));
		SET_BIT((ch)->specials.affected_by2, AFF2_CASTING);
	}
}

void event_psionic_wave_blast(P_char ch, P_char victim, P_obj /*obj*/, void *data)
{
	int level, dam;
	struct affected_type *af;
	struct damage_messages messages = { "", "", "", "", "", "", 0 };

	level = *((int *)data);

	for (af = victim->affected; af && af->type != SPELL_PSIONIC_WAVE_BLAST; af = af->next)
		;

	if (af == NULL)
	{
		if (IS_SET((ch)->specials.affected_by2, AFF2_CASTING))
			REMOVE_BIT((ch)->specials.affected_by2, AFF2_CASTING);
		return;
	}

	if (af && ((GET_POS(ch) < POS_STANDING) || IS_STUNNED(ch)))
	{
		send_to_char("\r\nYour mental assault was interrupted!!!\r\n", ch);

		if (IS_SET((ch)->specials.affected_by2, AFF2_CASTING))
			REMOVE_BIT((ch)->specials.affected_by2, AFF2_CASTING);

		if (get_scheduled(ch, event_psionic_wave_blast))
			disarm_char_nevents(ch, event_psionic_wave_blast);

		if (affected_by_spell(victim, SPELL_PSIONIC_WAVE_BLAST))
			affect_from_char(victim, SPELL_PSIONIC_WAVE_BLAST);
		return;
	}

	if ((af->modifier)-- == 0)
	{
		send_to_char("You have reach the maximum capability of your mental assault.\n", ch);

		if (affected_by_spell(victim, SPELL_PSIONIC_WAVE_BLAST))
			affect_from_char(victim, SPELL_PSIONIC_WAVE_BLAST);

		if (IS_SET((ch)->specials.affected_by2, AFF2_CASTING))
			REMOVE_BIT((ch)->specials.affected_by2, AFF2_CASTING);

		return;
	}

	if (!psionic_wave_blast_shrug_roll(live_rolls) && resists_spell(ch, victim))
	{
		if (!(IS_SET((ch)->specials.affected_by2, AFF2_CASTING)))
			SET_BIT((ch)->specials.affected_by2, AFF2_CASTING);

		GET_MANA(ch) -= psionic_wave_blast_mana();

		add_event(event_psionic_wave_blast, psionic_wave_blast_interval(), ch, victim, NULL,
			  0, &level, sizeof(level));
		return;
	}

	dam = psionic_wave_blast_wave_damage(live_rolls, level);

	if (!StatSave(victim, APPLY_POW, POW_DIFF(ch, victim)))
		dam = psionic_wave_blast_failed_save(dam);

	if (ch->in_room != victim->in_room)
		dam = psionic_wave_blast_away(dam);

	const int result = spell_damage(ch, victim, dam, SPLDAM_PSI,
					SPLDAM_NODEFLECT | SPLDAM_NOSHRUG, &messages);
	if (result == DAM_NONEDEAD)
	{
		if (!IS_SET((ch)->specials.affected_by2, AFF2_CASTING))
			SET_BIT((ch)->specials.affected_by2, AFF2_CASTING);

		GET_MANA(ch) -= psionic_wave_blast_mana();

		add_event(event_psionic_wave_blast, psionic_wave_blast_interval(), ch, victim, NULL,
			  0, &level, sizeof(level));
		return;
	}

	if (result != DAM_VICTDEAD)
		return; // The caster is gone.

	if (IS_SET((ch)->specials.affected_by2, AFF2_CASTING))
		REMOVE_BIT((ch)->specials.affected_by2, AFF2_CASTING);
}

// The power difference, shifted by a random number of seconds.
static int enrage_attack(const Rolls &rolls, P_char ch, P_char victim)
{
	return (GET_C_POW(ch) - GET_C_POW(victim)) + rolls.number(-2, 2) * WAIT_SEC;
}

// The attack's limits, in pulses.
static int enrage_least()
{
	return WAIT_SEC;
}

static int enrage_most()
{
	return WAIT_SEC * 15;
}

// How long the berserk lasts, in pulses.
static int enrage_berserk(const Rolls &rolls, int attdiff)
{
	return rolls.number((2 * attdiff) / 3, (4 * attdiff) / 3);
}

std::string enrage_facts(P_char /*ch*/)
{
	return fact("Berserk", seconds(enrage_berserk(lowest_rolls, enrage_least())) + " to " +
				       seconds(enrage_berserk(highest_rolls, enrage_most()))) +
	       "  It lasts longer the more your power and level beat the target's.\n"
	       "  Another target gets a spell save, harder the stronger your attack is.\n"
	       "  It has no effect on someone already berserk.\n";
}

void spell_enrage(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim, P_obj /*obj*/)
{
	int attdiff;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return;
	}

	appear(ch);

	attdiff = enrage_attack(live_rolls, ch, victim);
	attdiff += 2 * (level - GET_LEVEL(victim));
	// debug( "attdiff(unbounded): %d, save(would be): %d.", attdiff, attdiff/WAIT_SEC );
	attdiff = BOUNDED(enrage_least(), attdiff, enrage_most());

	// debug( "attdiff(final): %d, save: %d.", attdiff, attdiff/WAIT_SEC );
	if ((ch != victim) && NewSaves(victim, SAVING_SPELL, attdiff / WAIT_SEC))
	{
		send_to_char("You feel a brief bit of &+ranger&n, but it passes.\r\n", victim);
		return;
	}

	// Min 2/3 sec - 1 1/3 sec, Max 10 sec - 20 sec.
	berserk(victim, enrage_berserk(live_rolls, attdiff));
	return;
}

// How long mind blank hides the caster, in pulses.
static int mind_blank_duration(int level)
{
	return level * 2 * WAIT_SEC;
}

static int mind_blank_cooldown()
{
	return 15;
}

std::string mind_blank_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Hidden from detection for", real_time(mind_blank_duration(level)) +
							 " at your level, " +
							 std::to_string(level)) +
	       fact("You cannot cast it again for", game_hours(mind_blank_cooldown())) +
	       "  It ends when you become visible again; the wait does not.\n";
}

void spell_mind_blank(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
		      P_char victim, P_obj /*obj*/)
{
	struct affected_type af;

	if (!(victim && ch))
	{
		logit(LOG_EXIT, "assert: bogus params in mind blank");
		exit(1);
	}
	if (CheckMindflayerPresence(ch))
	{
		send_to_char("You sense an ethereal disturbance and abort your spell!\r\n", ch);
		return;
	}

	if (affected_by_spell(ch, TAG_CONJURED_PET))
	{
		return;
	}

	if (affected_by_spell(ch, SPELL_MIND_BLANK))
	{
		act("Your mind goes completely blank... Maybe you should wait a while before trying that again.",
		    FALSE, ch, 0, 0, TO_CHAR);
		return;
	}

	bzero(&af, sizeof(af));
	af.type = SPELL_MIND_BLANK;
	af.duration = mind_blank_duration(level);
	af.flags = AFFTYPE_SHORT;
	af.bitvector3 = AFF3_NON_DETECTION;
	affect_to_char(ch, &af);

	// Cooldown timer.. in minutes.
	af.flags = 0;
	af.duration = mind_blank_cooldown();
	af.bitvector3 = 0;
	affect_to_char(ch, &af);

	act("&+YYour mind now protect you against detection!", FALSE, ch, 0, 0, TO_CHAR);

	return;
}

static int cannibalize_duration(int level)
{
	return level;
}

std::string cannibalize_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Duration", game_hours(cannibalize_duration(level)) + " at your level, " +
					std::to_string(level)) +
	       "  Casting it again renews the full duration.\n" +
	       fact("Mana you take per hit", show({ (int)cannibalize_mana(0, level),
						    (int)cannibalize_mana(INT_MAX, level) })) +
	       "  It rises with the damage dealt, and is taken after the damage lands.\n" +
	       fact("A hit must deal more than", std::to_string(cannibalize_least_damage())) +
	       "  It never takes more than the target has, or past your maximum.\n";
}

void spell_cannibalize(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
		       P_char victim, P_obj /*obj*/)
{
	struct affected_type af;

	if (!(victim && ch))
	{
		logit(LOG_EXIT, "assert: bogus params in cannibalize");
		exit(1);
	}

	if (affected_by_spell(ch, SPELL_CANNIBALIZE))
	{
		struct affected_type *af1;

		for (af1 = victim->affected; af1; af1 = af1->next)
		{
			if (af1->type == SPELL_CANNIBALIZE)
			{
				af1->duration = cannibalize_duration(level);
			}
		}
		return;
	}

	bzero(&af, sizeof(af));
	af.type = SPELL_CANNIBALIZE;
	/*
	  if (GET_RACE(ch) == RACE_ILLITHID)
	      af.duration = (level * 2);
	*/
	af.duration = cannibalize_duration(level);
	af.bitvector3 = AFF3_CANNIBALIZE;
	affect_to_char(ch, &af);

	act("&+YYou will now drain power from your victim!", FALSE, ch, 0, 0, TO_CHAR);
}

static int tower_iron_will_duration(int level)
{
	return level / 2;
}

std::string tower_iron_will_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Duration", game_hours(tower_iron_will_duration(level)) + " at your level, " +
					std::to_string(level)) +
	       fact("Psionic damage you take",
		    share_percent(tower_iron_will_share()) + " of normal") +
	       "  That is one of the spell damage modifiers.\n"
	       "  Casting it again renews the duration.\n";
}

void spell_tower_iron_will(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			   P_char victim, P_obj /*obj*/)
{
	struct affected_type af;

	if (!(victim && ch))
	{
		logit(LOG_EXIT, "assert: bogus params in tower of iron will");
		exit(1);
	}
	if (affected_by_spell(ch, SPELL_TOWER_IRON_WILL))
	{
		struct affected_type *af1;

		for (af1 = victim->affected; af1; af1 = af1->next)
			if (af1->type == SPELL_TOWER_IRON_WILL)
			{
				af1->duration = tower_iron_will_duration(level);
			}
		return;
	}

	bzero(&af, sizeof(af));
	af.type = SPELL_TOWER_IRON_WILL;
	af.duration = tower_iron_will_duration(level);
	af.bitvector3 = AFF3_TOWER_IRON_WILL;
	affect_to_char(ch, &af);

	act("&+YYour mind will now be more resistant to psionic attack!", FALSE, ch, 0, 0, TO_CHAR);

	return;
}

static int innate_blast_appear_roll(const Rolls &rolls)
{
	return rolls.number(0, 1);
}

static int innate_blast_paralysis_roll(const Rolls &rolls)
{
	return rolls.number(0, 2);
}

static int innate_blast_major_roll(const Rolls &rolls)
{
	return rolls.number(0, 1);
}

static int innate_blast_duration(int lev)
{
	return (lev >> 5) + 1;
}

// The blast's paralysis, as do_blast casts it at the user's level.
std::string blast_innate_facts(P_char ch)
{
	return fact("Paralysis chance",
		    one_in(innate_blast_paralysis_roll) + ", if a power save also fails") +
	       fact("Duration",
		    game_hours(innate_blast_duration(GET_LEVEL(ch))) + " at your level") +
	       (GET_LEVEL(ch) > 25 ?
			fact("Major instead of minor", one_in(innate_blast_major_roll)) :
			"  Paralysis is minor at your level.\n") +
	       fact("You appear", one_in(innate_blast_appear_roll) + " if you are unseen") +
	       innate_rest_facts(INNATE_BLAST, 0) +
	       "  Freedom of movement, paralysis immunity and existing paralysis stop it.\n"
	       "  A shopkeeper ignores it, but the use is still spent. It has no lag.\n";
}

void spell_innate_blast(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			P_char victim, P_obj obj)
{
	struct affected_type af;
	int lev = level;

	if (!((victim || obj) && ch))
	{
		return;
	}
	if (GET_STAT(ch) == STAT_DEAD)
		return;

	if (IS_TRUSTED(victim))
	{
		send_to_char("If only.\r\n", ch);
		return;
	}

	if (innate_blast_appear_roll(live_rolls))
		appear(ch);

	if (check_freedom_of_movement(victim) && !IS_TRUSTED(ch))
	{
		send_to_char("&+CTheir movement magic prevented your spell!&n\r\n", ch);
		return;
	}

	if (!innate_blast_paralysis_roll(live_rolls) &&
	    !StatSave(victim, APPLY_POW, MAX(-3, (GET_LEVEL(ch) - GET_LEVEL(victim)) / 3)) &&
	    !(IS_NPC(victim) && IS_SET(victim->specials.act, ACT_IMMUNE_TO_PARA)))
	{
		bzero(&af, sizeof(af));

		if ((GET_LEVEL(ch) > 25) && innate_blast_major_roll(live_rolls))
		{
			af.type = SPELL_MAJOR_PARALYSIS;
			af.bitvector2 = AFF2_MAJOR_PARALYSIS;
		}
		else
		{
			af.type = SPELL_MINOR_PARALYSIS;
			af.bitvector2 = AFF2_MINOR_PARALYSIS;
		}

		if (!IS_AFFECTED2(victim, AFF2_MAJOR_PARALYSIS) &&
		    !IS_AFFECTED2(victim, AFF2_MINOR_PARALYSIS))
		{
			af.duration = innate_blast_duration(lev);

			affect_to_char(victim, &af);

			act("$n &+Mceases to move.. still and lifeless.", FALSE, victim, 0, 0,
			    TO_ROOM);
			send_to_char(
				"&+LYour body becomes like stone as the paralyzation takes effect.\r\n",
				victim);
			if (IS_FIGHTING(victim))
				stop_fighting(victim);

			/*
			 * stop all non-vicious/agg attackers
			 */
			StopMercifulAttackers(victim);
		}

		if (CAN_SEE(victim, ch))
			remember(victim, ch);
	}
	else if (IS_NPC(victim) && CAN_SEE(victim, ch))
	{
		remember(victim, ch);
		if (!IS_FIGHTING(victim))
			MobStartFight(victim, ch);
	}
}

// The farthest a caster can go, by the caster's own level.
static int radial_navigation_range(P_char ch)
{
	return GET_LEVEL(ch) + 10;
}

static int radial_navigation_mana(int distance)
{
	return distance * get_property("spells.radialnavigation.manaburnfactor", 12);
}

static int radial_navigation_lag()
{
	return 2.5 * WAIT_SEC;
}

// How long a caster with negative mana stays knocked out, in pulses.
static int radial_navigation_knockout(int mana)
{
	return -(int)((float)(mana) * 1.5);
}

std::string radial_navigation_facts(P_char ch)
{
	return fact("Range", std::to_string(radial_navigation_range(ch)) +
				     " rooms at your level, " + std::to_string(GET_LEVEL(ch))) +
	       fact("Mana per room asked for", std::to_string(radial_navigation_mana(1))) +
	       "  You pay it even if the jaunt fails.\n" +
	       fact("Your lag", seconds(radial_navigation_lag())) +
	       fact("Knocked out below 0 mana",
		    real_time(radial_navigation_knockout(-100)) + " per 100 mana below") +
	       "  Both ends must be on the map, outside no-teleport rooms.\n";
}

void spell_radial_navigation(int /*level*/, P_char ch, char *arg, int /*type*/, P_char victim,
			     P_obj /*tar_obj*/)
{
	char arg1[MAX_STRING_LENGTH], arg2[MAX_STRING_LENGTH];
	int distance, i, dir, to_room, curr_room;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (!victim)
		victim = ch;

	argument_interpreter(arg, arg1, arg2);

	/* Bypassing class check. Lucrot 31Aug2008
	 *  if (!IS_TRUSTED(ch) && !GET_CLASS(ch, CLASS_PSIONICIST))
	 * {
	 *   send_to_char("You cannot master that power!\r\n", ch);
	 *   return;
	 * }
	 */

	if (!*arg1)
	{
		send_to_char("You must specify a direction of travel: n,s,e,w\r\n", ch);
		return;
	}
	if (!*arg2)
	{
		send_to_char("You must specify the distance you wish to travel.\r\n", ch);
		return;
	}
	switch (*arg1)
	{
	case 'n':
		dir = 0;
		break;
	case 'e':
		dir = 1;
		break;
	case 's':
		dir = 2;
		break;
	case 'w':
		dir = 3;
		break;
	default:
		send_to_char("That is not a valid direction.\r\n", ch);
		return;
	}
	if (!is_number(arg2) || (distance = atoi(arg2)) <= 0)
	{
		send_to_char("That is not a proper distance.\r\n", ch);
		return;
	}
	if (distance > radial_navigation_range(ch))
	{
		send_to_char("Your meager mentality cannot carry you that far!\r\n", ch);
		return;
	}
	to_room = ch->in_room;
	for (curr_room = 0; curr_room <= top_of_world; curr_room++)
	{
		BFSUNMARK(curr_room);
	}
	for (i = 0; i < distance; i++)
	{
		if (!VALID_RADIAL_EDGE(to_room, dir))
		{
			break;
		}
		to_room = TOROOM(to_room, dir);
	}

	if (!IS_TRUSTED(ch) &&
	    ((to_room == NOWHERE) || (to_room == ch->in_room) || !IS_MAP_ROOM(ch->in_room) ||
	     !IS_MAP_ROOM(to_room) || IS_ROOM(ch->in_room, ROOM_NO_TELEPORT) ||
	     IS_ROOM(to_room, ROOM_NO_TELEPORT) || (GET_MASTER(ch) && IS_PC(victim))))
	{
		act("&+L$n's&+L outline begins to &n&+rvibrate&+L, then &+Bblur&+L.... then stabilize.&N",
		    TRUE, ch, 0, 0, TO_ROOM);
		act("&+wYour will is not strong enough to carry you away.&n", TRUE, ch, 0, 0,
		    TO_CHAR);
	}
	else
	{
		act("&+L$n's&+L outline begins to &n&+rvibrate&+L, then &+Bblur&+L, then.....    disappear.&N",
		    TRUE, ch, 0, 0, TO_ROOM);
		char_from_room(ch);
		char_to_room(ch, to_room, -1);
		send_to_char("&+LYou feel exhausted from the jaunt.&N\r\n", ch);
		act("&+LFrom out of nowhere $n's&+L blurred form streaks into the room!&N", TRUE,
		    ch, 0, 0, TO_ROOM);
	}

	/* subtract mana regardless of success..  snif */
	GET_MANA(ch) -= radial_navigation_mana(distance);
	CharWait(ch, radial_navigation_lag());

	/* twould be best to add more to their knock out time if they're already knocked out, but f it */
	if ((GET_MANA(ch) < 0) && !IS_AFFECTED(ch, AFF_KNOCKED_OUT))
	{
		act("Exhausted, $n passes out!", FALSE, ch, 0, 0, TO_ROOM);
		send_to_char("Reserves exhausted, you pass out!\r\n", ch);
		KnockOut(ch, radial_navigation_knockout(GET_MANA(ch)));
	}
}

static int ethereal_rift_lag()
{
	return WAIT_SEC;
}

std::string ethereal_rift_facts(P_char /*ch*/)
{
	return fact("Your lag", seconds(ethereal_rift_lag())) +
	       "  It takes you to a random room in the target's zone.\n"
	       "  In a private, no-teleport, hometown or ocean room, yours or the target's,\n"
	       "  it leaves you where you are.\n"
	       "  It cannot target an NPC.\n";
}

void spell_ethereal_rift(int /*level*/, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			 P_obj /*obj*/)
{
	int to_room, dam, found = 0;
	P_char tmp, tmp_next;

	if (!ch)
		return;

	if (!victim)
		victim = ch;

	if (IS_NPC(victim))
	{
		send_to_char("Nice try...\r\n", ch);
		return;
	}

	dam = 1;
	if (dam <= 0)
		dam = 1;

	do
	{
		to_room = number(zone_table[world[victim->in_room].zone].real_bottom,
				 zone_table[world[victim->in_room].zone].real_top);
		found++;
	} while ((IS_ROOM(to_room, ROOM_PRIVATE) || PRIVATE_ZONE(to_room) ||
		  IS_ROOM(to_room, ROOM_NO_TELEPORT) || IS_HOMETOWN(to_room) ||
		  world[to_room].sector_type == SECT_OCEAN) &&
		 found < 1000);

	if ((IS_ROOM(victim->in_room, ROOM_PRIVATE) || PRIVATE_ZONE(victim->in_room) ||
	     IS_ROOM(victim->in_room, ROOM_NO_TELEPORT) || IS_HOMETOWN(victim->in_room) ||
	     world[victim->in_room].sector_type == SECT_OCEAN))
	{
		to_room = ch->in_room;
	}

	if ((IS_ROOM(ch->in_room, ROOM_PRIVATE) || PRIVATE_ZONE(ch->in_room) ||
	     IS_ROOM(ch->in_room, ROOM_NO_TELEPORT) || IS_HOMETOWN(ch->in_room) ||
	     (world[ch->in_room].sector_type == SECT_OCEAN)))
	{
		to_room = ch->in_room;
	}

	if (found == 1000)
		to_room = ch->in_room;

	send_to_char("Your mind catapults you through a tear in the ethereal fabric.\r\n", ch);

	for (tmp = world[ch->in_room].people; tmp; tmp = tmp_next)
	{
		tmp_next = tmp->next_in_room;
		if (IS_AFFECTED(tmp, AFF_BLIND) || (tmp == ch))
			continue;
		act("&+LA dark tear in reality opens, and $n shimmers and fades away!\r\n", FALSE,
		    ch, 0, tmp, TO_VICT);
	}
	char_from_room(ch);
	ch->specials.z_cord = victim->specials.z_cord;
	char_to_room(ch, to_room, -1);
	send_to_char("Your body aches as your molecules reassemble themselves. \r\n", ch);

	for (tmp = world[ch->in_room].people; tmp; tmp = tmp_next)
	{
		tmp_next = tmp->next_in_room;
		if (IS_AFFECTED(tmp, AFF_BLIND) || (tmp == ch))
			continue;
		act("&+LA black cloud shimmers and slowly forms into $n!\r\n", FALSE, ch, 0, tmp,
		    TO_VICT);
	}

	zone_powerspellmessage(to_room, "&+LYou sense a disturbance in the ethereal fabric.\r\n");

	CharWait(ch, ethereal_rift_lag());
	return;
}

// An illithid angers the Elder Brain warping to a non-illithid player below this level.
static int ether_warp_protected_below()
{
	return 51;
}

static int ether_warp_punishment_lag()
{
	return (int)(PULSE_SPELLCAST * 10);
}

// How many rooms away a psycheporter or illithid can find an NPC.
static int ether_warp_range(int level)
{
	return (int)(level * get_property("spell.dim.perlevel.modifier", 1.35));
}

static int ether_warp_lag()
{
	return 7 * WAIT_SEC;
}

std::string ether_warp_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const bool psycheporter = GET_SPEC(ch, CLASS_PSIONICIST, SPEC_PSYCHEPORTER);
	std::string text = fact("Your lag", psycheporter ? "none, as a psycheporter" :
							   seconds(ether_warp_lag()));
	if (IS_TRUSTED(ch))
		return text;
	if (psycheporter || IS_ILLITHID(ch))
		text += fact("Range to an NPC", std::to_string(ether_warp_range(level)) + " rooms" +
							" at your level, " + std::to_string(level));
	else
		text += "  You cannot warp to an NPC.\n";
	if (IS_ILLITHID(ch))
		text += fact("Warping to a non-illithid player below level " +
				     std::to_string(ether_warp_protected_below()),
			     "refused") +
			fact("Your lag for trying", seconds(ether_warp_punishment_lag()));
	return text + "  A warp that cannot reach the target leaves you where you are.\n";
}

void spell_ether_warp(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		      P_obj /*obj*/)
{
	int to_room, dam, temp;
	P_char tmp, tmp_next;
	int distance;

	if (!ch) // Something is amiss... Nov08 -Lucrot
	{
		logit(LOG_EXIT, "spell_ether_warp called in psionics.c with no ch.");
		exit(1);
	}

	if (!victim)
		victim = ch;

	dam = 70 - ((GET_LEVEL(ch) / 2) + number(10, 50));
	if (dam <= 0)
	{
		dam = 1;
	}

	if (IS_PC(victim) && IS_ILLITHID(ch) && !IS_TRUSTED(ch) && !IS_ILLITHID(victim) &&
	    GET_LEVEL(victim) < ether_warp_protected_below())
	{
		send_to_char("&+CThat being is too weak for you to find in the ether!\r\n", ch);
		send_to_char(
			"&+MThe Elder Brain is displeased and you feel numbness engulf you.&n\r\n",
			ch);
		wizlog(57, "%s attmpted to wormhole %s, and made the &+MElder Brain&n displeased.",
		       GET_NAME(ch), GET_NAME(victim));
		CharWait(ch, ether_warp_punishment_lag());
		return;
	}

	to_room = victim->in_room;
	temp = world[ch->in_room].sector_type;
	if (!IS_TRUSTED(ch) /*  && !IS_ILLITHID(ch) */ &&
	    ((to_room == NOWHERE) || (to_room == ch->in_room) || IS_TRUSTED(victim) ||
	     IS_ROOM(ch->in_room, ROOM_NO_TELEPORT) || IS_HOMETOWN(ch->in_room) ||
	     IS_HOMETOWN(to_room) || IS_ROOM(to_room, ROOM_NO_MAGIC) ||
	     IS_ROOM(to_room, ROOM_NO_TELEPORT) || world[to_room].sector_type == SECT_OCEAN ||
	     IS_AFFECTED3(victim, AFF3_NON_DETECTION) ||
	     (IS_NPC(victim) &&
	      (!GET_SPEC(ch, CLASS_PSIONICIST, SPEC_PSYCHEPORTER) && !IS_ILLITHID(ch))) ||
	     (IS_PC(victim) && IS_SET(victim->specials.act2, PLR2_NOLOCATE) &&
	      !is_introd(victim, ch)) ||
	     racewar(ch, victim) ||
	     ((GET_MASTER(ch) && IS_PC(victim))
	      /* Allowing warping off planes - Drannak
	                                                              || (((temp == SECT_EARTH_PLANE)
	                                                                   || (temp == SECT_AIR_PLANE) || (temp == SECT_ETHEREAL)
	                                                                   || (temp == SECT_FIREPLANE) || (temp == SECT_WATER_PLANE)
	                                                                   || (temp == SECT_NEG_PLANE))
	                                                       */
	      && !(temp == world[to_room].sector_type))))
	{
		to_room = ch->in_room;
	}

	if (!IS_TRUSTED(ch) /* && IS_ILLITHID(ch) */ &&
	    ((to_room == NOWHERE) || (to_room == ch->in_room) || IS_TRUSTED(victim) ||
	     IS_ROOM(ch->in_room, ROOM_NO_TELEPORT) || IS_HOMETOWN(ch->in_room) ||
	     IS_HOMETOWN(to_room) || IS_ROOM(to_room, ROOM_NO_MAGIC) ||
	     IS_ROOM(to_room, ROOM_NO_TELEPORT) || world[to_room].sector_type == SECT_OCEAN ||
	     IS_AFFECTED3(victim, AFF3_NON_DETECTION) ||
	     (IS_NPC(victim) &&
	      (!GET_SPEC(ch, CLASS_PSIONICIST, SPEC_PSYCHEPORTER) && !IS_ILLITHID(ch))) ||
	     (IS_PC(victim) && IS_SET(victim->specials.act2, PLR2_NOLOCATE) &&
	      !(temp == world[to_room].sector_type))))
	{
		to_room = ch->in_room;
	}

	distance = ether_warp_range(level);
	if (!IS_TRUSTED(ch) && IS_NPC(victim) &&
	    (GET_SPEC(ch, CLASS_PSIONICIST, SPEC_PSYCHEPORTER) || IS_ILLITHID(ch)) &&
	    how_close(ch->in_room, victim->in_room, distance) < 0 &&
	    how_close(victim->in_room, ch->in_room, distance) < 0)
	{
		to_room = ch->in_room;
	}

	send_to_char("Your body explodes into light.\r\n", ch);

	if (!IS_TRUSTED(ch))
	{
		char logbuf[500];
		snprintf(logbuf, 500, "Ether Warp from %s[%d] to %s[%d]", GET_NAME(ch),
			 world[ch->in_room].number, GET_NAME(victim), world[to_room].number);
		logit(LOG_PORTALS, "%s", logbuf);
		// spam immo's if it looks like a possible camped target
		if (IS_PC(victim) &&
		    ((world[to_room].number == GET_HOME(victim)) || (GET_LEVEL(victim) < 10)))
		{
			strcat(logbuf, " - &=RCPossible Camped Target&n");
			statuslog(57, "%s", logbuf);
		}
	}
	for (tmp = world[ch->in_room].people; tmp; tmp = tmp_next)
	{
		tmp_next = tmp->next_in_room;
		if (!CAN_SEE(tmp, ch) || IS_AFFECTED(tmp, AFF_BLIND) || (tmp == ch))
			continue;
		act("&+YBeams of light emit from $n, and $n explodes into energy!", FALSE, ch, 0,
		    tmp, TO_VICT);
	}
	char_from_room(ch);
	ch->specials.z_cord = victim->specials.z_cord;
	char_to_room(ch, to_room, -1);
	send_to_char("&+LYour body reforms from the light.\r\n", ch);

	for (tmp = world[ch->in_room].people; tmp; tmp = tmp_next)
	{
		tmp_next = tmp->next_in_room;
		if (!CAN_SEE(tmp, ch) || IS_AFFECTED(tmp, AFF_BLIND) || (tmp == ch))
			continue;
		act("Beams of light appear from nowhere, and implode into $n!", FALSE, ch, 0, tmp,
		    TO_VICT);
	}

	// if (!damage(ch, ch, dam, TYPE_UNDEFINED))
	if (GET_SPEC(ch, CLASS_PSIONICIST, SPEC_PSYCHEPORTER))
	{
		send_to_char(
			"&+LBeing a &+Bmaster &+Lof &+gmol&+Gecu&+glar &+Ltravel, your &+Gbody &+Lquickly recovers from your &+mjour&+Mney&+L.&n\r\n",
			ch);
	}
	else
	{
		CharWait(ch, ether_warp_lag());
	}
}

// How long a new beacon lasts, in pulses.
static int thought_beacon_duration(int level)
{
	return level * 4 * WAIT_MIN;
}

std::string thought_beacon_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const int duration = thought_beacon_duration(level);
	return fact("Beacon lasts",
		    real_time(duration) + " at your level, " + std::to_string(level)) +
	       fact("Your link to it", real_time(duration)) +
	       "  A new beacon replaces the old one and renews your link.\n"
	       "  It fails in no-teleport rooms and on oceans.\n";
}

void spell_thought_beacon(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			  P_char /*victim*/, P_obj /*tar_obj*/)
{
	P_obj beacon;
	struct affected_type af, *afp;
	int duration = thought_beacon_duration(level);

	if (IS_ROOM(ch->in_room, ROOM_NO_TELEPORT) || world[ch->in_room].sector_type == SECT_OCEAN)
	{
		send_to_char("Something blocks your mental powers here.\n", ch);
		return;
	}

	beacon = read_object(real_object(416), REAL);

	if (!beacon)
	{
		logit(LOG_DEBUG, "spell_thought_beacon(): obj x not loadable");
		return;
	}

	if ((afp = get_spell_from_char(ch, SPELL_THOUGHT_BEACON)))
	{
		P_obj previous;
		for (previous = world[afp->modifier].contents; previous;
		     previous = previous->next_content)
		{
			if (previous->R_num == real_object(VOBJ_THOUGHT_BEACON) &&
			    previous->value[0] == GET_PID(ch))
				break;
		}
		if (previous)
			extract_obj(previous, FALSE);
		affect_from_char(ch, SPELL_THOUGHT_BEACON);
	}

	memset(&af, 0, sizeof(af));
	af.type = SPELL_THOUGHT_BEACON;
	af.flags = AFFTYPE_SHORT | AFFTYPE_NODISPEL | AFFTYPE_NOAPPLY;
	af.modifier = ch->in_room;
	af.duration = duration;
	affect_to_char(ch, &af);

	act("&+LYou sink into your &+Mtho&+Wug&+Mhts, &+Lamplifying the "
	    "&+bpsy&+mch&+bic &+wene&+Wrgi&+wes&+L in this room.&n",
	    FALSE, ch, beacon, 0, TO_CHAR);
	act("&+L$n seems to concentrate for a moment, and a dark mist coalesces "
	    "in the center of the room.&n",
	    FALSE, ch, beacon, 0, TO_ROOM);

	set_obj_affected(beacon, duration, TAG_OBJ_DECAY, 0);

	beacon->value[0] = GET_PID(ch);

	obj_to_room(beacon, ch->in_room);
}

// An illithid angers the Elder Brain opening a wormhole to a non-illithid player below this level.
static int wormhole_protected_below()
{
	return 51;
}

static int wormhole_punishment_lag()
{
	return (int)(PULSE_SPELLCAST * 10);
}

// How many rooms away improved wormhole can find an NPC.
static int wormhole_range(int level)
{
	return (int)(level * get_property("spell.dim.perlevel.modifier", 1.35));
}

// Spacial focus: a longer wormhole, and more on its throughput roll.
static int improved_wormhole_decay(int decay_timer)
{
	return (decay_timer / 2) * 3;
}

static int improved_wormhole_bonus()
{
	return 3;
}

// How long a wormhole lasts, in pulses, unless it closes sooner.
static int wormhole_decay_timer(P_char ch)
{
	int decay_timer = get_property("portals.wormhole.decayTimeout", 60 * 2);

	if (has_innate(ch, INNATE_IMPROVED_WORMHOLE))
		decay_timer = improved_wormhole_decay(decay_timer);
	return decay_timer;
}

// A positive capacity is required: zero or below means unlimited to the portal code.
static int wormhole_throughput(const Rolls &rolls, P_char ch)
{
	int specBonus = 0;
	int maxToPass = get_property("portals.wormhole.maxToPass", 3);

	if (has_innate(ch, INNATE_IMPROVED_WORMHOLE))
		specBonus = improved_wormhole_bonus();
	const int capacity = (ch->player.level - 46) / 2 + rolls.number(1, maxToPass + specBonus);
	return MAX(1, capacity);
}

std::string wormhole_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range pass = { wormhole_throughput(lowest_rolls, ch),
			     wormhole_throughput(highest_rolls, ch) };
	std::string people = show(pass);
	std::string text =
		fact("Can pass each way", people + " at your level, " + std::to_string(level)) +
		fact("Portal lasts", "up to " + seconds(wormhole_decay_timer(ch))) +
		"  Cast on yourself, it opens to your thought beacon.\n";
	if (has_innate(ch, INNATE_IMPROVED_WORMHOLE))
		text += fact("Range to an NPC", std::to_string(wormhole_range(level)) + " rooms") +
			"  It cannot reach an NPC that cannot be summoned.\n";
	else if (!IS_TRUSTED(ch))
		text += "  It can only reach another player.\n";
	if (!IS_TRUSTED(ch))
		text += "  It fails from or to a no-teleport room or hometown, from an ocean,\n"
			"  and to a single-file or no-magic room.\n";
	if (IS_ILLITHID(ch) && !IS_TRUSTED(ch))
		text += fact("To a non-illithid player below level " +
				     std::to_string(wormhole_protected_below()),
			     "refused") +
			fact("Your lag for trying", seconds(wormhole_punishment_lag()));
	return text;
}

std::string improved_wormhole_innate_facts(P_char ch)
{
	const int base = get_property("portals.wormhole.decayTimeout", 60 * 2);
	return fact("Your wormholes last up to", seconds(improved_wormhole_decay(base))) +
	       fact("Added to the top of the roll for how many can pass",
		    "+" + std::to_string(improved_wormhole_bonus())) +
	       fact("Range to an NPC", std::to_string(wormhole_range(GET_LEVEL(ch))) + " rooms") +
	       "  A wormhole can reach an NPC, unless it cannot be summoned.\n";
}

void spell_wormhole(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		    P_obj /*obj*/)
{
	struct portal_settings set = {
		770, /* portal type  */
		-1, /* from room */
		-1, /* to room */
		0, /* How many can pass before closes */
		0, /* Timeout before anyone can enter after open */
		0, /* Timeout before next person can enter */
		0, /* Lag person gets when steps out portal */
		0 /* Portal decay timer */
	};
	struct portal_create_messages msg = {
		/*ch   */ "&+LThe rift swirls for a moment and disperses.\r\n",
		/*ch r */ "&+LA wormhole swirls for a moment and then disperses.",
		/*vic  */ 0,
		/*vic r*/ 0,
		/*ch   */ "&+LRipping through reality, a black rift opens up here.\r\n",
		/*ch r */ "&+LRipping through reality, a black rift opens up here.\r\n",
		/*vic  */ "&+LThe air before you seems to rend and tear, revealing a black rift.\r\n",
		/*vic r*/ "&+LThe air before you seems to rend and tear, revealing a black rift.\r\n",
		/*npc  */ "Can only open a wormhole to another player!\n",
		/*bad  */ 0
	};

	P_obj beacon;
	struct affected_type *afp;
	int to_room = ch ? ch->in_room : NOWHERE;
	int distance;
	bool success = true;

	if (!ch) // Something is amiss... Nov08 -Lucrot
	{
		logit(LOG_EXIT, "spell_wormhole called in psionics.c with no ch.");
		exit(1);
	}

	if (!victim)
	{
		victim = ch;
	}

	/*
	if(IS_ILLITHID(ch) && !IS_ILLITHID(victim) && !IS_TRUSTED(ch))
	{
	   send_to_char("You can't target them!\r\n", ch);
	   return;
	}
	*/
	/*
	if (GET_RACE(ch) == RACE_GITHYANKI)
	{
	   send_to_char("&+LYour mind is too puny to create such a rift!&N\r\n", ch);
	   return;
	}
	*/

	// disables BEACON
	/*if (victim == ch)
	{
	   return;
	}
	*/
	if (ch) // Just making sure... Nov08 -Lucrot
	{
		if (victim == ch)
		{
			afp = get_spell_from_char(ch, SPELL_THOUGHT_BEACON);
			if (afp)
			{
				to_room = afp->modifier;
				for (beacon = world[to_room].contents; beacon;
				     beacon = beacon->next_content)
				{
					if (obj_index[beacon->R_num].virtual_number == 416 &&
					    beacon->value[0] == GET_PID(ch))
						break;
				}
				if (!beacon)
					success = false;
			}
			else
				success = false;
		}
		else
			to_room = victim->in_room;

		if (IS_NPC(victim))
		{
			if (!has_innate(ch, INNATE_IMPROVED_WORMHOLE) ||
			    IS_SET(victim->specials.act, ACT_NO_SUMMON))
				success = false;
			else
			{
				distance = wormhole_range(level);

				if (how_close(ch->in_room, to_room, distance) < 0 &&
				    how_close(to_room, ch->in_room, distance) < 0)
					success = false;
			}
		}

		// Stopping the wayward Illithid griefing. Nov08 -Lucrot
		if (victim && !IS_TRUSTED(ch) && IS_PC(victim) && IS_ILLITHID(ch) &&
		    !IS_ILLITHID(victim) && GET_LEVEL(victim) < wormhole_protected_below())
		{
			send_to_char("&+CBother something else that isn't so weak!&n\r\n", ch);
			send_to_char(
				"&+MThe Elder Brain is displeased and you feel numbness engulf you.&n\r\n",
				ch);
			wizlog(57,
			       "%s attmpted to wormhole %s, and made the &+MElder Brain&n displeased.",
			       GET_NAME(ch), GET_NAME(victim));
			CharWait(ch, wormhole_punishment_lag());
			return;
		}
		if (victim && IS_NPC(victim) && victim != ch && !IS_TRUSTED(ch) &&
		    has_innate(ch, INNATE_IMPROVED_WORMHOLE) &&
		    IS_SET(victim->specials.act, ACT_NO_SUMMON))
		{
			act(msg.fail_to_caster, FALSE, ch, 0, 0, TO_CHAR);
			act(msg.fail_to_caster_room, FALSE, ch, 0, 0, TO_ROOM);
			return;
		}

		set.to_room = to_room;
		set.init_timeout = get_property("portals.wormhole.initTimeout", 3);
		set.post_enter_timeout = get_property("portals.wormhole.postEnterTimeout", 0);
		set.post_enter_lag = get_property("portals.wormhole.postEnterLag", 0);
		set.decay_timer = wormhole_decay_timer(ch);
		set.throughput = wormhole_throughput(live_rolls, ch);

		if (!can_do_general_portal(level, ch, victim, &set, &msg) ||
		    (!IS_TRUSTED(ch) && (!success || GET_MASTER(ch))))
		{
			act(msg.fail_to_caster, FALSE, ch, 0, 0, TO_CHAR);
			act(msg.fail_to_caster_room, FALSE, ch, 0, 0, TO_ROOM);
			return;
		}

		if (IS_NPC(victim) && !IS_TRUSTED(ch) && !has_innate(ch, INNATE_IMPROVED_WORMHOLE))
		{
			send_to_char(msg.npc_target_caster, ch);
			return;
		}

		spell_general_portal(level, ch, victim, &set, &msg);
	}
}

// The limits of the bands excogitate reports: the caster's power minus the target's.
static int excogitate_far_greater_below()
{
	return -20;
}

static int excogitate_greater_below()
{
	return -10;
}

static int excogitate_equal_below()
{
	return 10;
}

static int excogitate_less_below()
{
	return 20;
}

static int excogitate_much_less_below()
{
	return 30;
}

std::string excogitate_facts(P_char /*ch*/)
{
	return fact("Your power minus the target's splits the report at",
		    std::to_string(excogitate_far_greater_below()) + ", " +
			    std::to_string(excogitate_greater_below()) + ", " +
			    std::to_string(excogitate_equal_below()) + ", " +
			    std::to_string(excogitate_less_below()) + " and " +
			    std::to_string(excogitate_much_less_below())) +
	       "  A target notices unless your power beats it by " +
	       std::to_string(excogitate_equal_below()) + " or more.\n";
}

void spell_excogitate(int /*level*/, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		      P_obj /*obj*/)
{
	int diff;

	if (!ch) // Something is amiss... Nov08 -Lucrot
	{
		logit(LOG_EXIT, "spell_excogitate called in psionics.c with no ch.");
		exit(1);
	}
	if (ch)
	{
		if (!IS_ALIVE(ch))
		{
			send_to_char("Study a victim when you are alive.\r\n", ch);
			return;
		}
		if (!(victim))
		{
			send_to_char("Who/what do you wish to probe?\r\n", ch);
			return;
		}
		diff = GET_C_POW(ch) - GET_C_POW(victim);

		if (diff < excogitate_far_greater_below())
		{
			act("$N's mental power is &+yfar greater than yours.&n", TRUE, ch, 0,
			    victim, TO_CHAR);
			act("$n has probed your mind!", TRUE, ch, 0, victim, TO_VICT);
			return;
		}
		else if (diff < excogitate_greater_below())
		{
			act("$N's mental power is &+ygreater&n than yours.", TRUE, ch, 0, victim,
			    TO_CHAR);
			act("$n has probed your mind!", TRUE, ch, 0, victim, TO_VICT);
			return;
		}
		else if (diff < excogitate_equal_below())
		{
			act("$N's mental power is roughly &+yequal&n to yours.", TRUE, ch, 0,
			    victim, TO_CHAR);
			act("You feel something brush your thoughts!", TRUE, ch, 0, victim,
			    TO_VICT);
			return;
		}
		else if (diff < excogitate_less_below())
		{
			act("$N's mental power is &+yless&n than yours.", TRUE, ch, 0, victim,
			    TO_CHAR);
			return;
		}
		else if (diff < excogitate_much_less_below())
		{
			act("$N's mental power is &+ymuch less&n than yours.", TRUE, ch, 0, victim,
			    TO_CHAR);
			return;
		}
		else
		{
			act("Your mental powers are &+Ymuch &+ygreater&n than $N's.&n", TRUE, ch, 0,
			    victim, TO_CHAR);
			return;
		}
	}
}
