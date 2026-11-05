/*
 * ***************************************************************************
 * *  File: actoff.c                                           Part of Duris *
 * *  Usage: Offensive commands.
 * * *  Copyright  1990, 1991 - see 'license.doc' for complete information.
 *  * *  Copyright 1994 - 2008 - Duris Systems Ltd.
 * *
 * ***************************************************************************
 */

#define TAKEDOWN_DEFAULT 0
#define TAKEDOWN_AIR_ELEMENTAL BIT_1
#define TAKEDOWN_FIRE_ELEMENTAL BIT_2
#define TAKEDOWN_EARTH_ELEMENTAL BIT_3
#define TAKEDOWN_WATER_ELEMENTAL BIT_4
#define TAKEDOWN_GHOST BIT_5
#define TAKEDOWN_AIR_AURA BIT_6
#define TAKEDOWN_VICTIM_BACK_RANK BIT_7
#define TAKEDOWN_CHAR_BACK_RANK BIT_8
#define TAKEDOWN_AGI_CHECK BIT_9
#define TAKEDOWN_DRAGON BIT_10
#define TAKEDOWN_NO_BASH BIT_11
#define TAKEDOWN_FOOTING BIT_12
#define TAKEDOWN_HARPY BIT_13
#define TAKEDOWN_GRAPPLE BIT_14
#define TAKEDOWN_EVADE BIT_15
#define TAKEDOWN_LUK_CHECK BIT_16
#define TAKEDOWN_ELEMENTALS                                                           \
	TAKEDOWN_AIR_ELEMENTAL | TAKEDOWN_FIRE_ELEMENTAL | TAKEDOWN_EARTH_ELEMENTAL | \
		TAKEDOWN_WATER_ELEMENTAL

#define TAKEDOWN_ALL 65535U

#define TAKEDOWN_CANCELLED -1
#define TAKEDOWN_PENALTY -2

#include "core/prototypes.h"
#include "core/structs.h"
#include "net/comm.h"
#include "net/gmcp.h"
#include "world/db.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "cmd/divine_refusal_policy.h"
#include "core/utils.h"
#include "telemetry/telemetry_runtime.h"
#include <ctype.h>
#include <stdio.h>
#include <string.h>
#include <cmath>
#include <string>
#include <utility>
#include <vector>
#include "world/buildings.h"
#include "combat/damage.h"
#include "combat/forced_movement.h"
#include "combat/grapple.h"
#include "combat/guard.h"
#include "guild/guildhall.h"
#include "combat/justice.h"
#include "combat/training_dummy.h"
#include "economy/collector_presence.h"
#include "item/item_actions.h"
#include "item/objmisc.h"
#include "classes/paladins.h"
#include "magic/spells.h"
#include "abilities/abilities.h"

/*
 * external variables
 */
/*extern flagDef weapon_types[];*/
extern P_index mob_index;
extern P_index obj_index;
extern P_desc descriptor_list;
extern P_room world;
extern const char *command[];
extern const char *dirs[];
extern void act_convert(char *, const char *, P_char, P_char, P_obj, void *, int);
extern const struct stat_data stat_factor[];
extern struct str_app_type str_app[];
extern struct zone_data *zone_table;
extern int innate_abilities[];
extern int class_innates[][5];
extern const int rev_dir[];
extern Skill skills[];
extern unsigned long long ne_event_tick;
extern void kick_messages(P_char, P_char, bool, struct damage_messages *);
extern P_char misfire_check(P_char ch, P_char spell_target, int flag);
extern void event_mob_mundane(P_char, P_char, P_obj, void *);
extern P_char make_mirror(P_char);
extern void do_bite(P_char ch, char *arg, int cmd);
extern bool has_dragoon_mount(P_char ch);
extern bool is_dragoon_mounted(P_char ch);
extern bool is_dragoon_mount(P_char mount);
extern bool is_in_dragoon_group(P_char ch, P_char vict);
extern void DelayCommune(P_char ch, int delay);
extern int get_next_dragoon_circle(P_char ch);
extern P_char get_dragoon_mount(P_char ch);

struct failed_takedown_messages
{
	int reason;
	const char *to_char;
	const char *to_room;
	const char *to_vict;
};

/* DEFAULT messages must be ALWAYS at the end - also when you define
 * arrays for new skills and want to use skill_immunity* stuff
 */
struct failed_takedown_messages failed_bash_messages[] = {
	{ TAKEDOWN_GHOST, "Your attempt to bash $N fails as you simply pass through $M.",
	  "$n makes a valiant attempt to bash $N, but simply falls through $M.",
	  "$n's attempt to bash you fails as $e simply passes through you." },
	{ TAKEDOWN_AIR_ELEMENTAL, "&+WYour attempt to bash $N fails as $E blows you on your ass!",
	  "&+W$n makes a valiant attempt to bash $N, but gets blown on $s ass!",
	  "$n's attempt to bash you fails as you simply blow $m onto $s ass!" },
	{ TAKEDOWN_EARTH_ELEMENTAL,
	  "&+WYour attempt to bash $N feels like you just hit a brick wall!",
	  "&+W$n just fell flat on $s ass after trying to bash $N!",
	  "$n's attempt to bash you fails miserably." },
	{ TAKEDOWN_FIRE_ELEMENTAL, "&+WYour attempt to bash $N almost burns you to a crisp!",
	  "&+W$n tries to bash $N, but falls right through $M and onto $s ass!",
	  "$n's attempt to bash you almost burns $m to a crisp!" },
	{ TAKEDOWN_WATER_ELEMENTAL, "&+WYou almost drown in your attempt to bash $N!",
	  "$n almost drowns as $e passes right through $N!",
	  "$n almost drowns as $e attempts to bash you!" },
	{ TAKEDOWN_HARPY, "Your attempt to bash $N fails as $M flutters into the air.",
	  "$n makes a valiant attempt to bash $N, but $E flutters into the air.",
	  "$n's attempt to bash you fails as you flutter into the air." },
	{ TAKEDOWN_GRAPPLE,
	  "As you try to bash $N, $E sidesteps, trips you, and slams you face first into the ground.",
	  "As $n tries to bash $N, $N slips away from $m and slams $s face into the ground.",
	  "As $n tries to bash you, you slip away from $m and slam $s face into the ground." },
	{ TAKEDOWN_EVADE,
	  "Your powerful bash knocks $N to the ground yet $E quickly rolls back up onto $S feet.",
	  "$N spins out of the way and rolls back onto $S feet as $n tries to knock $M to the ground.",
	  "You use the momentum of $n's powerful bash to leap back up onto your feet!" },
	{ TAKEDOWN_DEFAULT, "You make a futile attempt to bash $N, but $E is simply immovable.",
	  "$n makes a futile attempt to bash $N, but $E is simply immovable.",
	  "$n makes a futile attempt to bash you, but you are simply immovable." },
};

struct failed_takedown_messages failed_trip_messages[] = {
	{ TAKEDOWN_GHOST, "Your attempt to trip $N fails as you simply pass through $M.",
	  "$n makes a valiant attempt to trip $N, but simply falls through $M.",
	  "$n's attempt to trip you fails as $e simply passes through you." },
	{ TAKEDOWN_HARPY, "Your attempt to trip $N fails as $M flutters into the air.",
	  "$n makes a valiant attempt to trip $N, but $E flutters into the air.",
	  "$n's attempt to trip you fails as you flutter into the air." },
	{ TAKEDOWN_GRAPPLE,
	  "As you try to trip $N, $E sidesteps, trips you, and slams you face first into the ground.",
	  "As $n tries to trip $N, $N slips away from $m and slams $s face into the ground.",
	  "As $n tries to trip you, you slip away from $m and slam $s face into the ground." },
	{ TAKEDOWN_EVADE,
	  "In an amazing display of dexterity $N does a backward flip avoiding being tripped!",
	  "As $n tries to trip $N $E flips over $S shoulder and escapes!",
	  "You spin out of reach as $n attempts to sweep your feet." },
	{ TAKEDOWN_DEFAULT, "You make a futile attempt to trip $N, but $E is simply immovable.",
	  "$n makes a futile attempt to trip $N, but $E is simply immovable.",
	  "$n makes a futile attempt to trip you, but you are simply immovable." }
};

struct failed_takedown_messages failed_round_kick_messages[] = {
	{ TAKEDOWN_GHOST, "Your attempt to kick $N fails as you simply pass through $M.",
	  "$n makes a valiant attempt to kick $N, but simply falls through $M.",
	  "$n's attempt to kick you fails as $e simply passes through you." },
	{ TAKEDOWN_AIR_ELEMENTAL, "&+WYour attempt to kick $N fails as $E blows you on your ass!",
	  "&+W$n makes a valiant attempt to kick $N, but gets blown on $s ass!",
	  "$n's attempt to kick you fails as you simply blow $m onto $s ass!" },
	{ TAKEDOWN_EARTH_ELEMENTAL,
	  "&+WYour attempt to kick $N feels like you just hit a brick wall!",
	  "&+W$n just fell flat on $s ass after trying to kick $N!",
	  "$n's attempt to kick you fails miserably." },
	{ TAKEDOWN_FIRE_ELEMENTAL, "&+WYour attempt to kick $N almost burns you to a crisp!",
	  "&+W$n tries to kick $N, but falls right through $M and onto $s ass!",
	  "$n's attempt to kick you almost burns $m to a crisp!" },
	{ TAKEDOWN_WATER_ELEMENTAL, "&+WYou almost drown in your attempt to kick $M!",
	  "$n almost drowns as $e passes right through $M!",
	  "$n almost drowns as $e attempts to kick you!" },
	{ TAKEDOWN_HARPY, "Your attempt to kick $N fails as $M flutters into the air.",
	  "$n makes a valiant attempt to kick $N, but $E flutters into the air.",
	  "$n's attempt to kick you fails as you flutter into the air." },
	{ TAKEDOWN_DEFAULT, "&+WYou attempt to kick $M but bounce right off!",
	  "$n tries to kick $N but bounces right off!",
	  "$n tries to kick you but bounces right off!" }
};

struct failed_takedown_messages failed_bodyslam_messages[] = {
	{ TAKEDOWN_GHOST, "Your attempt to bodyslam $N fails as you simply pass through $M.",
	  "$n tries to bodyslam $N, but simply falls through $M.",
	  "$n tries to bodyslam you, but simply falls through." },
	{ TAKEDOWN_AIR_ELEMENTAL,
	  "&+WYour attempt to bodyslam $N fails as $E blows you on your ass!",
	  "&+W$n makes a valiant attempt to bodyslam $N, but gets blown on $s ass!",
	  "$n's attempt to bodyslam you fails as you simply blow $m onto $s ass!" },
	{ TAKEDOWN_EARTH_ELEMENTAL,
	  "&+WYour attempt to bodyslam $N feels like you just hit a brick wall!",
	  "&+W$n just fell flat on $s ass after trying to bodyslam $N!",
	  "$n's attempt to bodyslam you fails miserably." },
	{ TAKEDOWN_FIRE_ELEMENTAL, "&+WYour attempt to bodyslam $N almost burns you to a crisp!",
	  "&+W$n tries to bodyslam $N, but falls right through $M and onto $s ass!",
	  "$n's attempt to bodyslam you almost burns $m to a crisp!" },
	{ TAKEDOWN_WATER_ELEMENTAL, "&+WYou almost drown in your attempt to bodyslam $M!",
	  "$n almost drowns as $e passes right through $M!",
	  "$n almost drowns as $e attempts to bodyslam you!" },
	{ TAKEDOWN_DRAGON, "You simply bounce off $N's massive form.",
	  "$n tries to bodyslam $N and bounces off, stunned!",
	  "$n tries to bodyslam you and bounces off, stunned!" },
	{ TAKEDOWN_HARPY, "Your attempt to bodyslam $N fails as $M flutters into the air.",
	  "$n tries to bodyslam $N, but $E flutters into the air.",
	  "$n's tries to bodyslam you but, you flutter into the air." },
	{ TAKEDOWN_GRAPPLE,
	  "As you try to bodyslam $N, $E sidesteps, trips you, and slams you face first into the ground.",
	  "As $n tries to bodyslam $N, $N slips away from $m and slams $s face into the ground.",
	  "As $n tries to bodyslam you, you slip away from $m and slam $s face into the ground." },
	{ TAKEDOWN_EVADE,
	  "The force of your bodyslam sends $N on $S ass but $E quickly recovers and leaps back up.",
	  "$n's bodyslam sends $N on $S ass but with great dexterity $E rolls backward and leaps back up.",
	  "$n bodyslams you to the ground but you use the momentum to roll backward onto your feet." },
	{ TAKEDOWN_DEFAULT, "You make a futile attempt to bodyslam $N, but $E is simply immovable.",
	  "$n makes a futile attempt to bodyslam $N, but $E is simply immovable.",
	  "$n makes a futile attempt to bodyslam you, but you are simply immovable." }
};

struct failed_takedown_messages failed_tackle_messages[] = {
	{ TAKEDOWN_GHOST, "Your attempt to tackle $N fails as you simply pass through $M.",
	  "$n makes a valiant attempt to tackle $N, but simply falls through $M.",
	  "$n's attempt to tackle you fails as $e simply passes through you." },
	{ TAKEDOWN_AIR_ELEMENTAL, "&+WYour attempt to tackle $N fails as $E blows you on your ass!",
	  "&+W$n makes a valiant attempt to tackle $N, but gets blown on $s ass!",
	  "$n's attempt to tackle you fails as you simply blow $m onto $s ass!" },
	{ TAKEDOWN_EARTH_ELEMENTAL,
	  "&+WYour attempt to tackle $N feels like you just hit a brick wall!",
	  "&+W$n just fell flat on $s ass after trying to tackle $N!",
	  "$n's attempt to tackle you fails miserably." },
	{ TAKEDOWN_FIRE_ELEMENTAL, "&+WYour attempt to tackle $N almost burns you to a crisp!",
	  "&+W$n tries to tackle $N, but falls right through $M and onto $s ass!",
	  "$n's attempt to tackle you almost burns $m to a crisp!" },
	{ TAKEDOWN_WATER_ELEMENTAL, "&+WYou almost drown in your attempt to tackle $M!",
	  "$n almost drowns as $e passes right through $M!",
	  "$n almost drowns as $e attempts to tackle you!" },
	{ TAKEDOWN_HARPY, "Your attempt to tackle $N fails as $M flutters into the air.",
	  "$n makes a valiant attempt to tackle $N, but $E flutters into the air.",
	  "$n's attempt to tackle you fails as you flutter into the air." },
	{ TAKEDOWN_GRAPPLE,
	  "As you try to tackle $N, $E sidesteps, trips you, and slams you face first into the ground.",
	  "As $n tries to tackle $N, $N slips away from $m and slams $s face into the ground.",
	  "As $n tries to tackle you, you slip away from $m and slam $s face into the ground." },
	{ TAKEDOWN_EVADE,
	  "As you try to tackle $N $E casually sidesteps forcing you to abort or topple to the ground.",
	  "As $n tries to tackle $N $E casually sidesteps causing $m to almost slip and fall.",
	  "You casually sidesteps $n as $e tries to tackle you causing $m to stumble and almost fall." },
	{ TAKEDOWN_DEFAULT, "You make a futile attempt to tackle $N, but $E is simply immovable.",
	  "$n makes a futile attempt to tackle $N, but $E is simply immovable.",
	  "$n makes a futile attempt to tackle you, but you are simply immovable." }
};

struct failed_takedown_messages failed_springleap_messages[] = {
	{ TAKEDOWN_GHOST, "You fly head first through $N, landing on your ass.",
	  "$n attempts to springleap $N but simply flies through $M.",
	  "$n attempts to springleap you.  Apparently $e didn't notice you're incorporeal." },
	{ TAKEDOWN_DRAGON, "You fly head first directly into what might as well be a brick wall.",
	  "$n flies into $N, and simply drops off the massive form.",
	  "$n is really quite an idiot to think $e could do that fancy crap on YOU." },
	{ TAKEDOWN_HARPY, "Your attempt to springleap $N fails as $M flutters into the air.",
	  "$n attempts to springleap $N, but $E flutters into the air.",
	  "$n's attempts to springleap you fails as you flutter into the air." },
	{ TAKEDOWN_GRAPPLE,
	  "As you try to springleap $N, $E sidesteps, trips you, and slams you face first into the ground.",
	  "As $n tries to springleap $N, $N slips away from $m and slams $s face into the ground.",
	  "As $n tries to springleap you, you slip away from $m and slam $s face into the ground." },
	{ TAKEDOWN_EVADE,
	  "Your springleap knocks $N to the ground, yet with great dexterity $E rolls back onto $S feet.",
	  "$n's springleap knocks $N to the ground, yet with great dexterity $E rolls back onto $S feet.",
	  "$n flies into you knocking you off your feet, but you tuck and roll springing up on to your feet." },
	{ TAKEDOWN_DEFAULT,
	  "You make a futile attempt to springleap $N, but $E is simply immovable.",
	  "$n makes a futile attempt to springleap $N, but $E is simply immovable.",
	  "$n makes a futile attempt to springleap you, but you are simply immovable." }
};

struct failed_takedown_messages failed_maul_messages[] = {
	{ TAKEDOWN_GHOST, "Your attempt to maul $N fails as you simply pass through $M.",
	  "$n attempts to maul $N, but simply falls through $M.",
	  "$n's maul passes right through you." },
	{ TAKEDOWN_HARPY, "Your attempt to maul $N fails as $M flutters into the air.",
	  "$n makes a valiant attempt to maul $N, but $E flutters into the air.",
	  "$n's attempt to maul you fails as you flutter into the air." },
	{ TAKEDOWN_GRAPPLE,
	  "As you attempt to maul $N, $E sidesteps, trips you, and slams you face first into the ground.",
	  "As $n attempts to maul $N, $N slips away from $m and slams $s face into the ground.",
	  "As $n attempts to maul, you slip away from $m and slam $s face into the ground." },
	{ TAKEDOWN_EVADE,
	  "In an amazing display of dexterity $N does a backward flip avoiding your maul!",
	  "As $n tries to maul $N $E flips over $S shoulder and escapes!",
	  "You spin out of reach as $n attempts to maul you into the ground!" },
	{ TAKEDOWN_DEFAULT, "You make a futile attempt to maul $N, but $E is simply immovable.",
	  "$n makes a futile attempt to maul $N, but $E is simply immovable.",
	  "$n makes a futile attempt to maul you, but you are simply immovable." }
};

void knock_out(P_char ch, int duration);

void show_failed_takedown_messages(P_char ch, P_char victim, int skill, int reason)
{
	struct failed_takedown_messages *messages_set;
	int i;

	switch (skill)
	{
	case SKILL_BASH:
		messages_set = (struct failed_takedown_messages *)failed_bash_messages;
		break;
	case SKILL_BODYSLAM:
		messages_set = (struct failed_takedown_messages *)failed_bodyslam_messages;
		break;
	case SKILL_ROUNDKICK:
		messages_set = (struct failed_takedown_messages *)failed_round_kick_messages;
		break;
	case SKILL_TACKLE:
		messages_set = (struct failed_takedown_messages *)failed_tackle_messages;
		break;
	case SKILL_SPRINGLEAP:
		messages_set = (struct failed_takedown_messages *)failed_springleap_messages;
		break;
	case SKILL_TRIP:
		messages_set = (struct failed_takedown_messages *)failed_trip_messages;
		break;
	case SKILL_MAUL:
		messages_set = (struct failed_takedown_messages *)failed_maul_messages;
		break;
	// Kick does not give messages for failed takedown; it's room / wall / groin kicks.
	case SKILL_KICK:
		return;
	default:
		debug("show_failed_takedown_mesages: Bad skill %s (%d) not in switch.",
		      skills[skill].name, skill);
		return;
	}

	i = 0;
	while (messages_set[i].reason != reason && messages_set[i].reason != TAKEDOWN_DEFAULT)
	{
		i++;
	}

	if (messages_set[i].to_char != NULL)
	{
		act(messages_set[i].to_char, FALSE, ch, 0, victim, TO_CHAR);
	}
	if (messages_set[i].to_room != NULL)
	{
		act(messages_set[i].to_room, FALSE, ch, 0, victim, TO_NOTVICT);
	}
	if (messages_set[i].to_vict != NULL)
	{
		act(messages_set[i].to_vict, FALSE, ch, 0, victim, TO_VICT);
	}
}

// The attacker's lag, in pulses, when a takedown's target is asleep and is attacked instead.
static int takedown_sleeping_target_lag()
{
	return PULSE_VIOLENCE;
}

// The attacker's lag, in pulses, when the target evades a takedown.
static int takedown_evade_lag()
{
	return (int)(PULSE_VIOLENCE * 0.5);
}

// The chance displacement dodges a takedown, against displacement_takedown_roll().
int displacement_takedown_chance(int level)
{
	return (5 + level / 10);
}

int displacement_takedown_roll(const Rolls &rolls)
{
	return rolls.number(1, 100);
}

// The chance threshold takedown_check() rolls 1-100 against for an evade.
static int evade_threshold(P_char ch)
{
	return GET_CHAR_SKILL(ch, SKILL_EVADE) / 3;
}

// How long, in pulses, a successful evade keeps the next one from working.
static int evade_rest()
{
	return PULSE_VIOLENCE / 2;
}

std::string evade_facts(P_char ch)
{
	return fact("Chance to evade a takedown", std::to_string(evade_threshold(ch)) + " in 100") +
	       fact("Before you can evade again", seconds(evade_rest())) +
	       fact("Attacker's lag when you evade",
		    seconds(takedown_evade_lag()) + ", unless already lagged longer") +
	       "  You can't evade while asleep or worse.\n";
}

// The chance threshold takedown_check() rolls 1-100 against for a grapple.
static int grapple_threshold(P_char ch)
{
	return GET_CHAR_SKILL(ch, SKILL_GRAPPLE) / 6;
}

std::string grapple_facts(P_char ch)
{
	return fact("Chance to foil a takedown",
		    std::to_string(grapple_threshold(ch)) + " in 100") +
	       "  You can't foil one while asleep or worse.\n";
}

// TAKEDOWN_CANCELLED means the victim was able to prevent the full action.
// TAKEDOWN_PENALTY means ch failed the action for some reason.
float takedown_check(P_char ch, P_char victim, float chance, int skill, ulong applicable)
{
	int cagi, vagi;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return TAKEDOWN_CANCELLED;
	}

	// Only multiple-room takedown is lance charge?  What about Red Dragon springleap?
	//   Right now, only lance charge calls this fn. before moving the char into the same room.
	//   Red Dragon super springleap moves into the same room first.
	if ((ch->in_room != victim->in_room) && !affected_by_spell(ch, SKILL_LANCE_CHARGE))
	{
		return TAKEDOWN_CANCELLED;
	}

	if ((applicable & TAKEDOWN_CHAR_BACK_RANK) && !on_front_line(ch))
	{
		send_to_char("You can't seem to break the ranks!\n", ch);
		return TAKEDOWN_CANCELLED;
	}

	if (GET_STAT(victim) <= STAT_SLEEPING)
	{
		if (affected_by_spell(ch, SKILL_LANCE_CHARGE))
		{
			return TAKEDOWN_PENALTY;
		}

		act("$N is no condition to avoid $n's attack!", TRUE, ch, 0, victim, TO_NOTVICT);
		act("$N cannot respond to your attack!", TRUE, ch, 0, victim, TO_CHAR);

		if (ch->equipment[PRIMARY_WEAPON])
			hit(ch, victim, ch->equipment[PRIMARY_WEAPON]);
		else if (ch->equipment[SECONDARY_WEAPON])
			hit(ch, victim, ch->equipment[SECONDARY_WEAPON]);
		else
			hit(ch, victim, NULL);

		CharWait(ch, takedown_sleeping_target_lag());

		return TAKEDOWN_CANCELLED;
	}

	// Evade - Dodges takedowns, max 33% chance.
	if (GET_CHAR_SKILL(victim, SKILL_EVADE) && !get_spell_from_char(victim, SKILL_EVADE) &&
	    (notch_skill(victim, SKILL_EVADE, get_property("skill.notch.offensive", 7)) ||
	     evade_threshold(victim) >= number(1, 100)))
	{
		show_failed_takedown_messages(ch, victim, skill, TAKEDOWN_EVADE);
		set_short_affected_by(victim, SKILL_EVADE, evade_rest());
		CharWait(ch, takedown_evade_lag());
		return TAKEDOWN_CANCELLED;
	}

	// Back ranked check
	if ((IS_PC(ch) || IS_PC_PET(ch)) && (applicable & TAKEDOWN_VICTIM_BACK_RANK) &&
	    !on_front_line(victim))
	{
		send_to_char("You can't quite seem to reach them...\n", ch);
		return TAKEDOWN_CANCELLED;
	}

	// Grapple - dodges takedowns too, max 16%.
	if (GET_CHAR_SKILL(victim, SKILL_GRAPPLE))
	{
		if (notch_skill(victim, SKILL_GRAPPLE, get_property("skill.notch.offensive", 7)) ||
		    grapple_threshold(victim) >= number(1, 100))
		{
			show_failed_takedown_messages(ch, victim, skill, TAKEDOWN_GRAPPLE);
			return TAKEDOWN_PENALTY;
		}
	}

	if (IS_GRAPPLED(ch))
	{
		send_to_char("You can't do that while in a hold!\n", ch);
		return TAKEDOWN_CANCELLED;
	}

	if ((applicable & TAKEDOWN_FOOTING) && !HAS_FOOTING(ch))
	{
		// Water elemental pets of Water Maguses don't need footing.
		if (GET_RACE(ch) == RACE_W_ELEMENTAL && IS_PC_PET(ch) &&
		    GET_SPEC(GET_MASTER(ch), CLASS_CONJURER, SPEC_WATER))
		{
			send_to_char("&+WYou are a &+BWater Elemental&+W!\n", ch);
		}
		else
		{
			send_to_char("You have no footing here!\n", ch);
			return TAKEDOWN_CANCELLED;
		}
	}

	if ((applicable & TAKEDOWN_GHOST) && IS_IMMATERIAL(victim))
	{
		if (IS_NPC(victim))
		{
			show_failed_takedown_messages(ch, victim, skill, TAKEDOWN_GHOST);
			return TAKEDOWN_PENALTY;
		}

		// Immaterial PCs get a 10% chance to dodge takedowns.
		if (IS_PC(victim) && !number(0, 9))
		{
			show_failed_takedown_messages(ch, victim, skill, TAKEDOWN_GHOST);
			return TAKEDOWN_PENALTY;
		}
	}

	// Displacement - Dodges takedowns, max 10% chance @ lvl 50.
	if (affected_by_spell(victim, SPELL_DISPLACEMENT) &&
	    displacement_takedown_chance(GET_LEVEL(ch)) >= displacement_takedown_roll(live_rolls))
	{
		show_failed_takedown_messages(ch, victim, skill, TAKEDOWN_GHOST);
		return TAKEDOWN_PENALTY;
	}

	// Harpies - 5% chance to dodge takedowns.
	if ((applicable & TAKEDOWN_HARPY) && IS_HARPY(victim) && (number(1, 100) <= 5))
	{
		show_failed_takedown_messages(ch, victim, skill, TAKEDOWN_HARPY);
		return TAKEDOWN_PENALTY;
	}

	// Earth Elemental race is !bash.
	if ((applicable & TAKEDOWN_EARTH_ELEMENTAL) && GET_RACE(victim) == RACE_E_ELEMENTAL)
	{
		show_failed_takedown_messages(ch, victim, skill, TAKEDOWN_EARTH_ELEMENTAL);
		return TAKEDOWN_PENALTY;
	}
	// Water Elemental race is !bash.
	if ((applicable & TAKEDOWN_WATER_ELEMENTAL) && GET_RACE(victim) == RACE_W_ELEMENTAL)
	{
		show_failed_takedown_messages(ch, victim, skill, TAKEDOWN_WATER_ELEMENTAL);
		return TAKEDOWN_PENALTY;
	}

	// !bash flag.
	if ((applicable & TAKEDOWN_NO_BASH) && IS_NPC(victim) &&
	    IS_SET(victim->specials.act, ACT_NO_BASH))
	{
		show_failed_takedown_messages(ch, victim, skill, TAKEDOWN_DEFAULT);
		return TAKEDOWN_PENALTY;
	}

	// All dragons are 100% !bash.
	if ((applicable & TAKEDOWN_DRAGON) && IS_DRAGON(victim) && IS_NPC(victim))
	{
		show_failed_takedown_messages(ch, victim, skill, TAKEDOWN_DEFAULT);
		return TAKEDOWN_PENALTY;
	}

	if ((applicable & TAKEDOWN_AIR_AURA) && IS_AFFECTED2(victim, AFF2_AIR_AURA))
	{
		// 6 out of 20 chance - 30%
		if (number(1, 20) <= 6)
		{
			show_failed_takedown_messages(ch, victim, skill, TAKEDOWN_GHOST);
			return TAKEDOWN_PENALTY;
		}
	}

	// Agi versus agi Nov08 -Lucrot
	if (applicable & TAKEDOWN_AGI_CHECK)
	{
		cagi = GET_C_AGI(ch);
		vagi = GET_C_AGI(victim);
		// Thris don't get a stat bonus for takedowns.
		if (IS_THRIKREEN(ch) && cagi > 100)
		{
			cagi = 100;
		}
		// chance 70% skill and 30% attributes
		// For attributes, contribute 2 points off the 30% for each - point of difference in agi, or add 1/2 point
		//   for each + point of difference in agi, with a limit of contributing no % for really bad agi on ch,
		//   and a limit of contributing 37.5 points (7.5 over limit of 30%) for really good agi on ch.
		// So, someone with no skill but awesome agi vs bad agi (50 points difference) has a 7.5% chance to be
		//   successful, and someone with perfect skill and bad agi vs awesome agi (-50 points difference), has
		//   a 70% chance to be successful.
		chance = .70 * chance +
			 .30 * BOUNDED(0.0, 100.0 + (cagi - vagi) * ((cagi - vagi <= 0) ? 2.0 : .5),
				       125.0);
	}

	// NPC bonus to bash Nov08 - Lucrot
	if (IS_NPC(ch) && !IS_PC_PET(ch))
	{
		chance *= get_property("skill.bash.NPC_Modifier", 1.2);
	}

	if (applicable & TAKEDOWN_LUK_CHECK)
	{
		// Lucky bashers get a 10% @100 luck chance for a 10% bonus.
		if (GET_C_LUK(ch) / 10 >= number(1, 100))
		{
			chance *= 1.1;
		}

		// Lucky victims get a 10% @100 luck chance for a 10% bonus to dodge.
		if (GET_C_LUK(victim) / 10 >= number(1, 100))
		{
			chance *= .9;
		}
	}

	// Guardian spirits protects vs takedowns - chance dictated by the property.
	if (affected_by_spell(victim, SPELL_GUARDIAN_SPIRITS))
	{
		guardian_spirits_messages(ch, victim);

		debug("Takedown_check: attacker (%s) reduced by Guardian Spirit from (%.2f) to (%.2f).",
		      GET_NAME(ch), chance, chance * get_property("spell.GuardianSpirit", 0.750));

		// No need to put bounds on chance here; a multiplier won't go into negative,
		//   nor do we need to worry about an upper bounds and definitely don't need to upper at 75%!
		// chance = BOUNDED(0, (int) (chance * get_property("spell.GuardianSpirit", 0.750)), 75);
		chance *= get_property("spell.GuardianSpirit", 0.750);
	}

	// Freedom of movement steadies the victim for the whole spell instead of being used up.
	if (affected_by_spell(victim, SPELL_FREEDOM_OF_MOVEMENT))
	{
		chance *= get_property("spell.FreedomOfMovement.takedown", 0.800);
	}

	// No need to bind chance here either.
	return chance;
}

P_char ParseTarget(P_char ch, char *argument)
{
	P_char victim = NULL;
	char name[MAX_INPUT_LENGTH];

	one_argument(argument, name);

	if (*name)
		victim = get_char_room_vis(ch, name);

	if (!victim && GET_OPPONENT(ch))
	{
		victim = GET_OPPONENT(ch);
		if ((!IS_ALIVE(victim)) || (victim->in_room != ch->in_room) ||
		    victim->specials.z_cord != ch->specials.z_cord)
		{
			stop_fighting(ch);
			victim = NULL;
		}
	}

	if (affected_by_spell(ch, SKILL_TAUNT))
	{
		struct affected_type *paf = get_spell_from_char(ch, SKILL_TAUNT);
		if (paf && paf->context != (void *)victim && CAN_SEE(ch, (P_char)paf->context))
		{
			send_to_char("You try to switch opponents but can't!", ch);
			victim = (P_char)paf->context;
		}
	}

	return victim;
}

/*
 * no messages from this routine, it's just to check yes/no. JAB
 */

bool should_not_kill(P_char ch, P_char victim)
{
	if (collector_presence_is_npc(ch) || collector_presence_is_npc(victim))
		return TRUE;
	if ((ch->in_room == NOWHERE) || (victim->in_room == NOWHERE))
		return TRUE;

	/* modified to provide for shapeshifters --TAM 04/12/94 */
	if (ch->desc && ch->desc->original && !ch->only.pc->switched)
		ch = ch->desc->original;

	if (EVIL_RACE(ch) || EVIL_RACE(victim))
		return FALSE;

	/* only PCs should get here, law system checks/calls will replace this. */

	return FALSE;
}

/* SamIam, from shayol code!! */
/* checks to see if PC is in safe room */
bool is_in_safe(P_char ch)
{
	if (!ch)
		return FALSE;

	if (IS_ROOM(ch->in_room, ROOM_SAFE))
	{
		send_to_char("No fighting permitted in this room.\n", ch);
		return TRUE;
	}
	else if (IS_SET(zone_table[world[ch->in_room].zone].flags, ZONE_SAFE))
	{
		send_to_char("You decide not to for some reason.\n", ch);
		return TRUE;
	}
	else
	{
		return FALSE;
	}
}

/*
 * Public Interface
 */

void do_stance([[maybe_unused]] P_char ch, [[maybe_unused]] char *argument, int /*cmd*/)
{
#ifdef STANCES_ALLOWED
	char buf1[MAX_STRING_LENGTH];
	char first[MAX_INPUT_LENGTH];
	char rest[MAX_INPUT_LENGTH];

	if (IS_PC_PET(ch))
		return;
	*buf1 = '\0';
	if (!*argument)
	{
		if (IS_AFFECTED5(ch, AFF5_STANCE_DEFENSIVE))
			send_to_char("&+yYou are atm in defensive stance\n", ch);

		else if (IS_AFFECTED5(ch, AFF5_STANCE_OFFENSIVE))
			send_to_char("&+rYou are atm in offensive stance\n", ch);
		else
			send_to_char("Syntax: stance <offensive|defensive|none>\n", ch);

		return;
	}
	half_chop(argument, first, rest);
	if (is_abbrev(first, "none"))
	{
		REMOVE_BIT(ch->specials.affected_by5, AFF5_STANCE_OFFENSIVE);
		REMOVE_BIT(ch->specials.affected_by5, AFF5_STANCE_DEFENSIVE);
		send_to_char("You stop holding any particular stance..\n", ch);
	}
	if (is_abbrev(first, "offensive"))
	{
		SET_BIT(ch->specials.affected_by5, AFF5_STANCE_OFFENSIVE);
		REMOVE_BIT(ch->specials.affected_by5, AFF5_STANCE_DEFENSIVE);
		send_to_char("You enter an offensive stance..\n", ch);
	}

	if (is_abbrev(first, "defensive"))
	{
		SET_BIT(ch->specials.affected_by5, AFF5_STANCE_DEFENSIVE);
		REMOVE_BIT(ch->specials.affected_by5, AFF5_STANCE_OFFENSIVE);
		send_to_char("You enter a defensive stance..\n", ch);
	}

	CharWait(ch, PULSE_VIOLENCE * 1);

#else
	return;
#endif
}

void do_hit(P_char ch, char *argument, int cmd)
{
	P_char victim;

	if (!ch)
	{
		logit(LOG_EXIT, "do_hit: bogus params: ch is NULL, cmd = %s %d.",
		      (cmd > 0 && cmd < MAX_CMD) ? command[cmd] : "unknown", cmd);
		return;
	}
	if (!IS_ALIVE(ch))
	{
		send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	victim = ParseTarget(ch, argument);

	if (!*argument && has_innate(ch, INNATE_SENSE_WEAKNESS))
	{
		P_char tch;

		for (tch = world[ch->in_room].people; tch; tch = tch->next_in_room)
		{
			if (!(ch->group && tch->group && (ch->group == tch->group)))
			{
				if (CAN_SEE(ch, tch) && on_front_line(tch) && (tch != ch) &&
				    (victim == NULL || GET_HIT(tch) < GET_HIT(victim)))
				{
					victim = tch;
				}
			}
		}
		if (victim != NULL)
		{
			act("You feel the &+rbl&+Loo&+rdl&+Lus&+rt&n pulse in your veins as you spot $N and charge!",
			    FALSE, ch, 0, victim, TO_CHAR);
			act("$n grins wickedly as he spots you!", FALSE, ch, 0, victim, TO_VICT);
		}
	}

	if (!strcmp(argument, "target"))
	{
		victim = get_linked_char(ch, LNK_BATTLE_ORDERS);
		clear_links(ch, LNK_BATTLE_ORDERS);
	}

	if (!victim)
	{
		send_to_char("Slay whom?\n", ch);
		return;
	}

	if ((!IS_PC(ch) && !IS_PC_PET(ch)) || (on_front_line(ch) && on_front_line(victim)))
	{
		attack(ch, victim);
	}
	else if (ch->equipment[PRIMARY_WEAPON] && IS_REACH_WEAPON(ch->equipment[PRIMARY_WEAPON]))
		attack(ch, victim);
	else
		send_to_char("You can't quite seem to reach them...\n", ch);
}

void do_murde(P_char ch, char * /*argument*/, int /*cmd*/)
{
	send_to_char("To prevent 'accidents', you may not abbreviate 'murder'.\n", ch);
}

void do_murder(P_char ch, char *argument, int /*cmd*/)
{
	/*
	 * murder is just a 'safety measure' command, all it does is call
	 * do_hit() with the cmd variable set to CMD_MURDER.  'hit', 'kill'
	 * and 'attack' do not work for pkill. JAB
	 */

	do_hit(ch, argument, CMD_MURDER);
}

// How long, in pulses, the rider must wait between lance charges.
static int lance_charge_rest()
{
	return 2 * PULSE_VIOLENCE;
}

// The rider's lag after a charge, in pulses.
static int lance_charge_lag()
{
	return (int)(PULSE_VIOLENCE * get_property("skill.lance.charge.CharLag", 1.500));
}

// The rider's lag after toppling off the mount, in pulses.
static int lance_charge_topple_lag()
{
	return PULSE_VIOLENCE * 2;
}

// Falling damage after toppling off the mount.
static int lance_charge_topple_damage(const Rolls &rolls)
{
	return rolls.number(1, 50);
}

// The target's lag after a hit, in pulses.
static int lance_charge_target_lag()
{
	return (int)(PULSE_VIOLENCE * get_property("skill.lance.charge.VictimLag", 1.000));
}

// The target's lag after being knocked down, in pulses.
static int lance_charge_knockdown_lag()
{
	return (int)(PULSE_VIOLENCE * get_property("skill.lance.charge.KnockdownLag", 2.000));
}

// The lance's own roll, before the rider's level scales it.
static int lance_charge_weapon_damage(const Rolls &rolls, P_obj weapon)
{
	return rolls.dice(weapon->value[2], weapon->value[1]) + weapon->value[2];
}

// The lance's roll scaled by the rider's level.
static int lance_charge_scaled_damage(int dam, int level)
{
	dam = (int)(dam * ((double)level) / 100 + 1);
	dam *= MAX(2, (int)(level / 5));
	return dam;
}

// The scaled damage of a charge from another room.
static int lance_charge_ranged_damage(int dam)
{
	return (int)(dam * get_property("skill.lance.charge.RangeDamMod", 2.000));
}

// What each kind of blow adds to the scaled damage.
static int lance_charge_impale_damage(const Rolls &rolls)
{
	return rolls.dice(20, 5);
}

static int lance_charge_glance_damage(const Rolls &rolls)
{
	return rolls.dice(15, 5);
}

static int lance_charge_ram_damage(const Rolls &rolls)
{
	return rolls.dice(20, 6);
}

static int lance_charge_through_damage(const Rolls &rolls)
{
	return rolls.dice(30, 6);
}

std::string lance_charge_facts(P_char ch)
{
	std::string facts =
		fact("Your lag", seconds(lance_charge_lag())) +
		fact("Your lag if the target evades", seconds(takedown_evade_lag())) +
		fact("Before you can charge again", seconds(lance_charge_rest())) +
		fact("Target's lag on a hit", seconds(lance_charge_target_lag())) +
		fact("Target's lag if knocked down", seconds(lance_charge_knockdown_lag()));
	if (GET_LEVEL(ch) <= 50)
		facts += fact("Your lag if you topple off your mount",
			      seconds(lance_charge_topple_lag())) +
			 fact("Falling damage if you topple off",
			      show({ lance_charge_topple_damage(lowest_rolls),
				     lance_charge_topple_damage(highest_rolls) }));
	P_obj weapon = ch->equipment[WIELD];
	if (weapon && IS_LANCE(weapon))
	{
		const int low = lance_charge_scaled_damage(
			lance_charge_weapon_damage(lowest_rolls, weapon), GET_LEVEL(ch));
		const int high = lance_charge_scaled_damage(
			lance_charge_weapon_damage(highest_rolls, weapon), GET_LEVEL(ch));
		facts += fact("Base damage with your lance", show({ low, high })) +
			 fact("Base damage from another room",
			      show({ lance_charge_ranged_damage(low),
				     lance_charge_ranged_damage(high) }));
	}
	return facts +
	       fact("Impaling blow",
		    "base + " + show({ lance_charge_impale_damage(lowest_rolls),
				       lance_charge_impale_damage(highest_rolls) })) +
	       fact("Glancing blow, which never knocks down",
		    "half base + " + show({ lance_charge_glance_damage(lowest_rolls),
					    lance_charge_glance_damage(highest_rolls) })) +
	       fact("Blow that carries you both out of the room",
		    "base + " + show({ lance_charge_ram_damage(lowest_rolls),
				       lance_charge_ram_damage(highest_rolls) })) +
	       fact("Blow that runs the target through",
		    "base + " + show({ lance_charge_through_damage(lowest_rolls),
				       lance_charge_through_damage(highest_rolls) })) +
	       "  You must ride a mount and wield a lance.\n"
	       "  The target's defenses apply to the damage after.\n";
}

void lance_charge(P_char ch, char *argument)
{
	P_char victim, mount;
	char arg1[MAX_INPUT_LENGTH], arg2[MAX_INPUT_LENGTH];
	P_obj weapon, other_weapon;
	int knockdown_chance, percent_chance, dam, dir = -1, continue_dir = -1;
	int effect = 0, available_exits = 0, choice, i;
	char buf[512];

	half_chop(argument, arg1, arg2);

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (!SanityCheck(ch, "lance_charge"))
		return;

	if (GET_CHAR_SKILL(ch, SKILL_LANCE_CHARGE) < 1)
	{
		send_to_char("You do not have the appropriate training.\n", ch);
		return;
	}

	if (IS_FIGHTING(ch))
	{
		send_to_char("You are too busy fighting to prepare yourself for a charge!", ch);
		return;
	}

	if (!(mount = get_linked_char(ch, LNK_RIDING)))
	{
		send_to_char("You can do this only while riding a mount!\n", ch);
		return;
	}

	if (IS_FIGHTING(mount))
	{
		send_to_char("You mount is too busy fighting!\r\n", ch);
		return;
	}

	if (IS_IMMOBILE(mount))
	{
		send_to_char("&+YYour mount is unable to move!!!\r\n", ch);
		return;
	}

	if (IS_WATER_ROOM(ch->in_room))
	{
		send_to_char(
			"&+YYour mounts feet would slip in the wet ground to much to do that!!!\r\n",
			ch);
		return;
	}

	if (affected_by_spell(ch, SKILL_LANCE_CHARGE))
	{
		send_to_char("You haven't reoriented the mount yet enough for another charge!\n",
			     ch);
		return;
	}

	weapon = ch->equipment[WIELD];

	if (!weapon || !IS_LANCE(weapon))
	{
		send_to_char("You need a lance to do that!\n", ch);
		return;
	}

	if (*arg2)
	{
		dir = dir_from_keyword(arg2);
		if (dir == -1)
		{
			send_to_char(
				"You have to specify a direction as one of north, east, west, east, NW, NE, SW, SE\n",
				ch);
			return;
		}

		if (!(victim = get_char_ranged(arg1, ch, 1, dir)))
		{
			send_to_char("Couldn't find that target.\n", ch);
			return;
		}
	}
	else
		victim = ParseTarget(ch, arg1);

	if (!(victim))
	{
		send_to_char("Charge who?\n", ch);
		return;
	}

	if (!CanDoFightMove(ch, victim))
		return;

	if (!CanDoFightMove(mount, victim))
	{
		send_to_char("Your mount cannot do that right now!\n", ch);
		return;
	}

	set_short_affected_by(ch, SKILL_LANCE_CHARGE, lance_charge_rest());

	percent_chance = (int)(0.9 * MAX(70, GET_CHAR_SKILL(ch, SKILL_LANCE_CHARGE)));

	if (GET_C_LUK(ch) / 10 > number(0, 100))
		percent_chance = (int)(percent_chance * 1.1);

	if (GET_C_LUK(victim) / 10 > number(0, 100))
		percent_chance = (int)(percent_chance * 0.9);

	percent_chance =
		(int)(percent_chance *
		      ((double)BOUNDED(8, 10 + (GET_LEVEL(ch) - GET_LEVEL(victim)) / 10, 11)) / 10);

	if (IS_AFFECTED(victim, AFF_AWARE))
		percent_chance =
			(int)(percent_chance * get_property("skill.lance.charge.AwareMod", 0.850));

	knockdown_chance =
		(int)(percent_chance * get_property("skill.lance.charge.KnockDownMod", 0.650));

	dam = lance_charge_weapon_damage(live_rolls, weapon);
	dam = lance_charge_scaled_damage(dam, GET_LEVEL(ch));

	if (dir != -1)
		dam = lance_charge_ranged_damage(dam); // ranged charge

	knockdown_chance = takedown_check(ch, victim, knockdown_chance, SKILL_LANCE_CHARGE,
					  TAKEDOWN_ALL ^ TAKEDOWN_FOOTING);

	if (knockdown_chance == TAKEDOWN_CANCELLED)
		return;
	else if (knockdown_chance == TAKEDOWN_PENALTY)
		knockdown_chance = 0;

	percent_chance = BOUNDED(1, percent_chance, 99);

	if (IS_NPC(ch) && (40 > percent_chance))
		return;

	if (dir == -1)
	{
		act("$n spurs $s mount and charges $N, the $q pointed at $S chest.", TRUE, ch,
		    weapon, victim, TO_NOTVICT);
		act("$n spurs $s mount and charges $N, the $q pointed at YOUR chest.", TRUE, ch,
		    weapon, victim, TO_VICT);
		act("You spur your mount and charge $N, the $q pointed at $S chest.", TRUE, ch,
		    weapon, victim, TO_CHAR);
	}
	else
	{
		snprintf(buf, sizeof buf, "$n rears up on $N and charges %s.", dirs[dir]);
		act(buf, TRUE, ch, weapon, mount, TO_NOTVICT);
		snprintf(buf, sizeof buf, "You rear up on $N and charge %s.", dirs[dir]);
		act(buf, TRUE, ch, weapon, mount, TO_CHAR);
		snprintf(buf, sizeof buf, "$n rears up on you and orders you to charge %s.",
			 dirs[dir]);
		act(buf, TRUE, ch, weapon, mount, TO_VICT);
		do_simple_move(ch, dir, 0);
	}

	// calculate dir for continued charge
	if (dir != -1 && CAN_GO(ch, dir) && !check_wall(ch->in_room, dir) &&
	    can_enter_room(ch, EXIT(ch, dir)->to_room, 0))
		continue_dir = dir;
	else
	{
		for (i = 0; i < NUM_EXITS; i++)
		{
			if (world[ch->in_room].dir_option[i])
			{
				if (CAN_GO(ch, i) && !check_wall(ch->in_room, dir) &&
				    (dir == -1 || dir != rev_dir[dir]) &&
				    can_enter_room(ch, EXIT(ch, i)->to_room, 0))
				{
					available_exits++;
				}
			}
		}

		choice = number(0, available_exits - 1);

		for (i = 0; i < NUM_EXITS; i++)
		{
			if (world[ch->in_room].dir_option[i])
			{
				if (CAN_GO(ch, i) && !check_wall(ch->in_room, dir) &&
				    (dir == -1 || dir != rev_dir[dir]) &&
				    can_enter_room(ch, EXIT(ch, i)->to_room, 0))
				{
					if (!choice--)
					{
						continue_dir = i;
						break;
					}
				}
			}
		}
	}

	//--------------------------------------
	// Lom:
	// 1) dont let them charge out guild golems or charge past them
	//--------------------------------------
	if (IS_OP_GOLEM(victim) || IS_GH_GOLEM(victim) || GET_RACE(victim) == RACE_CONSTRUCT)
		continue_dir = -1;

	CharWait(ch, lance_charge_lag());

	if (!notch_skill(ch, SKILL_LANCE_CHARGE, get_property("skill.notch.offensive", 7)) &&
	    percent_chance < number(1, 100))
	{
		// failure code.

		if (GET_LEVEL(ch) > 50)
			effect = 8;
		else
			effect = number(0, 8);

		if (GET_C_LUK(ch) / 2 > number(0, 100))
			effect++;

		if (effect == 0)
		{ // basically a critical miss
			act("You misjudge the distance to your target and topple off your mount!",
			    FALSE, ch, 0, ch, TO_CHAR);
			act("$n misjudges the distance to $s target and topples off $s mount!",
			    FALSE, ch, 0, ch, TO_ROOM);
			unlink_char(ch, mount, LNK_RIDING);
			CharWait(ch, lance_charge_topple_lag());
			damage(ch, ch, lance_charge_topple_damage(live_rolls), DAMAGE_FALLING);
			return;
		}
		else if (effect < 3)
		{
			P_char tch, new_victim = NULL;
			int count = 0, chosen, tries = 2;

			for (tch = world[victim->in_room].people; tch; tch = tch->next_in_room)
			{
				count++;
			}
			while (tries-- &&
			       (!new_victim || (ch->group && (ch->group == new_victim->group))))
			{
				chosen = number(1, count);
				for (tch = world[victim->in_room].people; tch;
				     tch = tch->next_in_room)
				{
					if (chosen-- == 1)
					{
						new_victim = tch;
						break;
					}
				}
			}
			if (new_victim != ch && new_victim != mount)
				victim = new_victim;
		}
		else if (effect < 5 && continue_dir != -1)
		{
			act("Your aim is off and your $q misses $N.\nUnable to halt your mount you charge onward!",
			    TRUE, ch, weapon, victim, TO_CHAR);
			snprintf(
				buf, sizeof buf,
				"As $n fails to impale $N upon $s $q $e is unable to halt $s charge and disappears %s.",
				dirs[continue_dir]);
			act(buf, TRUE, ch, weapon, victim, TO_NOTVICT);
			snprintf(
				buf, sizeof buf,
				"As $n fails to impale you upon $s $q $e is unable to halt $s charge and disappears %s.",
				dirs[continue_dir]);
			act(buf, TRUE, ch, weapon, victim, TO_VICT);
			do_simple_move(ch, continue_dir, 0);
			return;
		}
		else
		{
			act("You thunder past as you fail to impale $N with your $q.", TRUE, ch,
			    weapon, victim, TO_CHAR);
			act("$n thunders past as $e fails to impale you with $s $q.", TRUE, ch,
			    weapon, victim, TO_VICT);
			act("$n thunders past as $e fails to impale $N with $s $q.", TRUE, ch,
			    weapon, victim, TO_NOTVICT);
			return;
		}
	}

	// damage code.
	if (ch && victim)
	{
		effect = number(0, 4);
		// Successful charge now lags the victim a little. Nov08 -Lucrot
		CharWait(victim, lance_charge_target_lag());
	}

	switch (effect)
	{
	case 0:
	case 1:
		dam = dam + lance_charge_impale_damage(live_rolls);
		act("With a &+Wbone c&+wr&+Wu&+ws&+Wh&+wi&+Wn&+wg thud the $q slams into $N impaling $M.",
		    FALSE, ch, weapon, victim, TO_NOTVICT);
		act("With a &+Wbone c&+wr&+Wu&+ws&+Wh&+wi&+Wn&+wg thud the $q slams into $N impaling $M.",
		    FALSE, ch, weapon, victim, TO_CHAR);
		act("With a &+Wbone c&+wr&+Wu&+ws&+Wh&+wi&+Wn&+wg thud $n's $q slams into you!",
		    FALSE, ch, weapon, victim, TO_VICT);
		if (!number(0, 100))
			DamageOneItem(ch, SPLDAM_GENERIC, weapon, FALSE);
		break;
	case 2:
		dam = dam / 2 + lance_charge_glance_damage(live_rolls);
		act("You glance $N with the tip of your $q causing a small surface wound.", FALSE,
		    ch, weapon, victim, TO_CHAR);
		act("$n glances $N with the tip of $s $q causing a small surface wound.", FALSE, ch,
		    weapon, victim, TO_NOTVICT);
		act("$n glances you with the tip of $s $q causing a small surface wound.", FALSE,
		    ch, weapon, victim, TO_VICT);
		knockdown_chance = 0;
		if (!number(0, 100))
			DamageOneItem(ch, SPLDAM_GENERIC, weapon, FALSE);
		break;
	case 3:
		//--------------------------------------
		// Lom:
		// 2) need to do something to prevent charging out !lure mobs ?
		//--------------------------------------
		// 	&& !IS_SET(victim->specials.act, ACT_SENTINEL)
		if (continue_dir != -1)
		{
			int target_room = world[ch->in_room].dir_option[continue_dir]->to_room;
			dam = dam + lance_charge_ram_damage(live_rolls);
			snprintf(buf, sizeof buf,
				 "You ram your $q through $N sending both veering out %s.",
				 dirs[continue_dir]);
			act(buf, FALSE, ch, weapon, victim, TO_CHAR);
			snprintf(buf, sizeof buf,
				 "$n rams $s $q through $N sending both veering out %s.",
				 dirs[continue_dir]);
			act(buf, FALSE, ch, weapon, victim, TO_NOTVICT);
			snprintf(buf, sizeof buf,
				 "$n rams $s $q through you sending both veering out %s.",
				 dirs[continue_dir]);
			act(buf, FALSE, ch, weapon, victim, TO_VICT);
			char_from_room(victim);
			char_to_room(victim, target_room, -1);
			char_from_room(ch);
			char_to_room(ch, target_room, -1);
			set_fighting(ch, victim);
			snprintf(
				buf, sizeof buf,
				"$N is flung to the ground as $n charges in from the %s, with $M impaled on the tip of the $q.",
				dirs[rev_dir[continue_dir]]);
			if (!number(0, 100))
				DamageOneItem(ch, SPLDAM_GENERIC, weapon, FALSE);
			act(buf, FALSE, ch, weapon, victim, TO_NOTVICT);
			break;
		}
		[[fallthrough]];
	case 4:
		dam = dam + lance_charge_through_damage(live_rolls);
		act("You ram your $q right through $N causing &+Rb&+rl&+Ro&+ro&+Rd&n to pour from $S body.",
		    FALSE, ch, weapon, victim, TO_CHAR);
		act("$n rams $s $q right through $N causing &+Rb&+rl&+Ro&+ro&+Rd&n to pour from $S body.",
		    FALSE, ch, weapon, victim, TO_NOTVICT);
		act("$n rams $s $q right through your body making you &+RB&+rL&+RE&+rE&+RD&n all over!",
		    FALSE, ch, weapon, victim, TO_VICT);
		if (!number(0, 100))
			DamageOneItem(ch, SPLDAM_GENERIC, weapon, FALSE);
		break;
	default:
		break;
	}

	if (melee_damage(ch, victim, dam, PHSDAM_NOPOSITION, 0) != DAM_NONEDEAD)
		return;

	if (!IS_ALIVE(ch))
		return;

	for (other_weapon = ch->carrying; other_weapon; other_weapon = other_weapon->next_content)
		if (other_weapon->type == ITEM_WEAPON)
			break;

	if (other_weapon)
	{
		do_remove(ch, weapon->name, CMD_REMOVE);
		do_wield(ch, other_weapon->name, CMD_WIELD);
	}

	if (knockdown_chance > number(1, 100))
	{
		act("$n is knocked to the ground!", FALSE, victim, 0, 0, TO_ROOM);
		send_to_char("You are knocked to the ground!\n", victim);
		SET_POS(victim, POS_SITTING + GET_STAT(victim));
		update_group_vitals(victim);
		gmcp_char_vitals(victim);
		CharWait(victim, lance_charge_knockdown_lag());
	}
}

// The charger's lag, in pulses, once a charge at a valid target starts.
static int charge_lag()
{
	return 2 * PULSE_VIOLENCE;
}

// The vitality a charge needs and spends.
static int charge_vitality_cost()
{
	return 30;
}

// How long, in pulses, a charger is knocked out by a low ceiling.
static int charge_ceiling_knockout()
{
	return PULSE_VIOLENCE;
}

// The target's lag after a hit, in pulses.
static int charge_target_lag()
{
	return (int)(1.5 * PULSE_VIOLENCE);
}

// How long, in pulses, a hit keeps the charger from charging again.
static int charge_rest()
{
	return (int)(3.0 * PULSE_VIOLENCE);
}

// Damage from a hit, before melee_damage applies the target's defenses.
static int charge_damage(const Rolls &rolls, int level)
{
	return (rolls.number(1, level) + level) * 2;
}

std::string charge_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return "  These need the charge innate; without it, charge is a lance charge.\n" +
	       fact("Damage on a hit", show({ charge_damage(lowest_rolls, level),
					      charge_damage(highest_rolls, level) }) +
					       " at your level") +
	       fact("Vitality", "needs and spends " + std::to_string(charge_vitality_cost())) +
	       fact("Your lag", seconds(charge_lag())) +
	       fact("Before you can charge again after a hit", seconds(charge_rest())) +
	       fact("Target's lag on a hit", seconds(charge_target_lag())) +
	       fact("Knocked out by a low ceiling", seconds(charge_ceiling_knockout())) +
	       "  A target 2 or more sizes bigger or smaller spills you to the ground.\n"
	       "  The target's defenses apply to the damage after.\n";
}

void do_charge(P_char ch, char *argument, int /*cmd*/)
{
	static bool DEBUG = TRUE;

	P_char victim;
	int dir = -1, a;
	int level = GET_LEVEL(ch);
	char arg1[MAX_INPUT_LENGTH], arg2[MAX_INPUT_LENGTH];
	float percent_chance;

	struct damage_messages messages = {
		"Your charge impales $N.",    "Your stagger as $n charges into you.",
		"$n charges wildly into $N!", "You charge $N, goring them beyond recognition.",
		"$n charges you to death!",   "$n charges right through $N, yuck."
	};

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (IS_TRUSTED(ch) && !strcmp(argument, "debug"))
	{
		DEBUG = !DEBUG;
		debug("do_charge: DEBUG turned %s.", DEBUG ? "ON" : "OFF");
		return;
	}

	if (!SanityCheck(ch, "do_charge"))
	{
		return;
	}

	if (IS_IMMOBILE(ch))
	{
		send_to_char("&+RYou are in no condition to charge anything...\r\n", ch);
		return;
	}

	switch (world[ch->in_room].sector_type)
	{
	case SECT_OCEAN:
	case SECT_UNDERWATER:
	case SECT_UNDERWATER_GR:
	case SECT_WATER_SWIM:
	case SECT_UNDRWLD_WATER:
	case SECT_WATER_PLANE:
		send_to_char("&+WThe waves hamper your ability to charge!\r\n", ch);
		return;
	case SECT_AIR_PLANE:
	case SECT_NO_GROUND:
	case SECT_UNDRWLD_NOGROUND:
	case SECT_ETHEREAL:
	case SECT_ASTRAL:
	case SECT_FIREPLANE:
		send_to_char("&+WYou can't seem to find any footing here!\r\n", ch);
		return;
	case SECT_UNDRWLD_LOWCEIL:
		send_to_char("You hit your head on the ceiling, and fall to the ground!\n\r", ch);
		knock_out(ch, charge_ceiling_knockout());
		return;
	default:
		break;
	}

	if (IS_ROOM(ch->in_room, ROOM_UNDERWATER))
	{
		send_to_char("&+WThe waves hamper your ability to charge!\r\n", ch);
		return;
	}

	if (IS_ROOM(ch->in_room, ROOM_SINGLE_FILE) || IS_ROOM(ch->in_room, ROOM_TUNNEL))
	{
		send_to_char("It's too cramped in here to charge.\n", ch);
		return;
	}

	if (!has_innate(ch, INNATE_CHARGE) ||
	    (IS_RIDING(ch) && (GET_CLASS(ch, CLASS_PALADIN) || GET_CLASS(ch, CLASS_ANTIPALADIN) ||
			       GET_SPEC(ch, CLASS_DRAGOON, SPEC_DRAGON_LANCER))))
	{
		lance_charge(ch, argument);
		return;
	}

	if (affected_by_spell(ch, SKILL_CHARGE) && !IS_TRUSTED(ch))
	{
		send_to_char("&+GYou are still a bit dizzy from your last attempt.&n\n", ch);
		return;
	}

	if (IS_FIGHTING(ch))
	{
		send_to_char("&+rYou may not charge while already engaged!\r\n", ch);
		return;
	}

	half_chop(argument, arg1, arg2);

	if (!*arg1)
	{
		send_to_char("Usage: CHARGE <victim> [direction]\n", ch);
		return;
	}

	if (*arg2)
	{ /* they gave dir */
		switch (toupper(arg2[0]))
		{
		case 'N':
			if (toupper(arg2[1]) == 'W')
				dir = 6;
			else if (toupper(arg2[1]) == 'E')
				dir = 8;
			else
				dir = 0;
			break;
		case 'E':
			dir = 1;
			break;
		case 'S':
			if (toupper(arg2[1]) == 'W')
				dir = 7;
			else if (toupper(arg2[1]) == 'E')
				dir = 9;
			else
				dir = 2;
			break;
		case 'W':
			dir = 3;
			break;
		case 'U':
			dir = 4;
			break;
		case 'D':
			dir = 5;
			break;
		default:
			send_to_char(
				"Invalid direction given.  Use: N, NW, NE, E, S, SW, SE, W, U, or D.\n",
				ch);
			return;
		} /* end case */

		if (!(victim = get_char_ranged(arg1, ch, 1, dir)))
		{
			send_to_char("Your target doesn't seem to be there.\n", ch);
			return;
		} /* could find victim */

		if (IS_ROOM(victim->in_room, ROOM_SINGLE_FILE) ||
		    IS_ROOM(victim->in_room, ROOM_TUNNEL))
		{
			send_to_char("It's too cramped in there to charge.\n", ch);
			return;
		}

		switch (world[victim->in_room].sector_type)
		{
		case SECT_OCEAN:
		case SECT_UNDERWATER:
		case SECT_UNDERWATER_GR:
		case SECT_WATER_SWIM:
		case SECT_UNDRWLD_WATER:
		case SECT_WATER_PLANE:
			send_to_char("&+WThe waves hamper your ability to charge!\r\n", ch);
			return;
		case SECT_AIR_PLANE:
		case SECT_NO_GROUND:
		case SECT_UNDRWLD_NOGROUND:
		case SECT_ETHEREAL:
		case SECT_ASTRAL:
		case SECT_FIREPLANE:
			send_to_char("&+WYou can't seem to find any footing there!\r\n", ch);
			return;
		default:
			break;
		}
	}
	else
	{ /* not ranged */
		victim = get_char_room_vis(ch, arg1);
		if (!victim)
		{
			send_to_char("You don't see them here.\n", ch);
			return;
		}
	} /* end if arg2 */

	/* now we have target, and room */

	if (victim == ch)
	{
		send_to_char("You cannot charge yourself.\r\n", ch);
		return;
	}

	if (should_not_kill(ch, victim))
		return;

	if (!CanDoFightMove(ch, victim))
		return;

	CharWait(ch, charge_lag());

	if (GET_VITALITY(ch) < charge_vitality_cost())
	{
		send_to_char("You need to gather your energy before attempting to charge.\r\n", ch);
		return;
	}
	GET_VITALITY(ch) -= charge_vitality_cost();

	if (dir != -1)
	{
		if (!EXIT(ch, dir) || IS_SET(EXIT(ch, dir)->exit_info, EX_CLOSED) ||
		    IS_SET(EXIT(ch, dir)->exit_info, EX_SECRET) ||
		    IS_SET(EXIT(ch, dir)->exit_info, EX_BLOCKED) ||
		    IS_ROOM(ch->in_room, ROOM_GUILD)) // Prevents charging past golems
		{
			send_to_char("You slam into an obstacle!\n", ch);
			return;
		}

		a = do_simple_move(ch, dir, 0);

		if (!a)
			return; /* failed move */

		char_light(ch);
		room_light(ch->in_room, REAL);

		if (IS_SECT(ch->in_room, SECT_UNDRWLD_LOWCEIL))
		{
			send_to_char(
				"You hit your head on the ceiling, and fall to the ground!\n\r",
				ch);
			knock_out(ch, charge_ceiling_knockout());
			return;
		}
	}

	/* Not currently being used
	if( !on_front_line(ch) || !on_front_line(victim) )
	{
	  send_to_char("You can't seem to reach!\n", ch);
	  return;
	}
	*/

	// Chance to hit is based on target size, dex, and ch level
	victim = guard_check(ch, victim);

	if (get_takedown_size(victim) > get_takedown_size(ch) + 1)
	{
		act("$n makes a futile attempt to charge $N, but $E is simply immovable.", FALSE,
		    ch, 0, victim, TO_ROOM);
		act("$N is too huge for you to charge!", FALSE, ch, 0, victim, TO_CHAR);
		act("$n tries to charge you, but merely bounces off your huge girth.", FALSE, ch, 0,
		    victim, TO_VICT);

		if (number(0, 1))
		{
			SET_POS(ch, POS_SITTING + GET_STAT(ch));
		}
		else
		{
			SET_POS(ch, POS_PRONE + GET_STAT(ch));
		}

		if (!IS_FIGHTING(victim))
			set_fighting(victim, ch);
		return;
	}
	if (get_takedown_size(victim) < (get_takedown_size(ch) - 1))
	{
		act("$n topples over $mself as $e tries to charge into $N.", FALSE, ch, 0, victim,
		    TO_ROOM);
		act("$n topples over $mself as $e tries to charge into you.", FALSE, ch, 0, victim,
		    TO_VICT);
		act("$N is too small to charge.&n", FALSE, ch, 0, victim, TO_CHAR);

		if (number(0, 1))
		{
			SET_POS(ch, POS_SITTING + GET_STAT(ch));
		}
		else
		{
			SET_POS(ch, POS_PRONE + GET_STAT(ch));
		}

		// We charged, but why should we engage if we failed - Drannak
		// Good point, only have the victim start attacking. - Lohrr
		if (!IS_FIGHTING(victim))
			set_fighting(victim, ch);
		return;
	}

	percent_chance = get_property("innate.charge.base.chance", 60.00);

	if (GET_C_LUK(ch) / 2 > number(0, 100))
	{
		percent_chance = percent_chance * 1.1;
	}

	if (GET_C_LUK(victim) / 2 > number(0, 100))
	{
		percent_chance = percent_chance * 0.9;
	}

	//  percent_chance = percent_chance * (float) BOUNDED(60, 100 + (GET_LEVEL(ch) - GET_LEVEL(victim)) * 2, 145) / 100.;
	percent_chance += (float)BOUNDED(-20, (3 * (GET_LEVEL(ch) - GET_LEVEL(victim))) / 2, 20);

	//  percent_chance = percent_chance * (float) BOUNDED(60, 100 + (GET_C_STR(ch) - GET_C_AGI(victim)) / 4, 145) / 100.;
	percent_chance +=
		(float)BOUNDED(-20, (GET_C_STR(ch) - (3 * GET_C_AGI(victim)) / 2) / 3, 20);

	// percent_chance = (int) (percent_chance * ((double) BOUNDED(60, 100 + (get_takedown_size(victim) - get_takedown_size(ch)) * 5, 145)) / 100);

	percent_chance = percent_chance * ((GET_POS(victim) == POS_PRONE)    ? 0.05 :
					   (GET_POS(victim) != POS_STANDING) ? 0.15 :
									       1);

	if (IS_AFFECTED(victim, AFF_AWARE))
	{
		percent_chance = percent_chance * 0.80;
	}

	if (affected_by_spell(victim, SPELL_GUARDIAN_SPIRITS))
	{
		guardian_spirits_messages(ch, victim);
		percent_chance -= (float)GET_LEVEL(victim);
	}

	// Cap chance at 95%.
	if (percent_chance > 95.)
	{
		percent_chance = 95.;
	}

	if (DEBUG)
	{
		debug("do_charge: (%s) charging (%s) final percentage (%d).", GET_NAME(ch),
		      GET_NAME(victim), (int)percent_chance);
	}

	if (number(1, 100) <= (int)percent_chance || IS_IMMOBILE(victim) || !IS_AWAKE(victim))
	{
		if (get_takedown_size(victim) <= get_takedown_size(ch) && !number(0, 2))
		{
			act("&+yYou charge wildly into&n $N &+yknocking $M to the &+Yground!&n", 0,
			    ch, 0, victim, TO_CHAR);
			act("$n &+ycharges through the room and crashes into&n $N &+yknocking $M to the &+Yground!",
			    0, ch, 0, victim, TO_NOTVICT);
			act("$n &+ycharges into you, knocking you to the &+Yground!&n &+yYou hear a crunching noise as &+Wbones break!&n",
			    0, ch, 0, victim, TO_VICT);

			if (GET_POS(victim) == POS_PRONE)
			{
				;
			}
			else if (number(0, 1))
			{
				SET_POS(victim, POS_SITTING + GET_STAT(victim));
			}
			else
			{
				SET_POS(victim, POS_PRONE + GET_STAT(victim));
			}
		}
		else
		{
			act("&+yYou charge wildly into&n $N!", 0, ch, 0, victim, TO_CHAR);
			act("$n &+ycharges through the room and crashes into&n $N! &+yYou hear the sound of &+Wbreaking bones!",
			    0, ch, 0, victim, TO_NOTVICT);
			act("$n &+ycharges into you! You hear a crunching noise as &+Wbones break!&n",
			    0, ch, 0, victim, TO_VICT);
		}

		CharWait(victim, charge_target_lag());
		set_short_affected_by(ch, SKILL_CHARGE, charge_rest());

		// Damage(final) is about 3/4 * level or about 42 dam at 56.
		if (melee_damage(ch, victim, charge_damage(live_rolls, level), PHSDAM_TOUCH,
				 &messages) != DAM_NONEDEAD)
		{
			return;
		}
		/* Old calculations for damage and such:
		if(!melee_damage(ch, victim, str_app[STAT_INDEX(GET_C_STR(ch))].todam + 5, 0, &messages))

		if(!damage(ch, victim, number(GET_LEVEL(ch), 6 * GET_LEVEL(ch)), TYPE_CHARGE))
		   SET_POS(victim, POS_PRONE + GET_STAT(victim));
		   CharWait(victim, PULSE_VIOLENCE);
		   Stun(victim, ch, PULSE_VIOLENCE * 3, TRUE);
		   if(char_in_list(ch)) CharWait(ch, PULSE_VIOLENCE * 4);

		 */
	}
	// Miss
	else
	{
		if ((dir != -1) && EXIT(ch, dir) && EXIT(ch, dir)->to_room != NOWHERE &&
		    !(IS_SET(EXIT(ch, dir)->exit_info, EX_CLOSED | EX_BLOCKED | EX_SECRET)) &&
		    !IS_ROOM(ch->in_room, ROOM_GUILD)) // Prevents charging past golems
		{
			int room = EXIT(ch, dir)->to_room;
			if (world[room].sector_type == SECT_OCEAN)
			{
				if (!number(0, 3))
				{
					act("&+y$n &+ycharges right past you ... and into the &+BOcean&+y!  That dork.&n",
					    TRUE, ch, 0, victim, TO_VICT);
					act("&+y$n &+ycharges through the room ... and into the &+BOcean&+y!  That dork.&n",
					    TRUE, ch, 0, victim, TO_ROOM);
					act("&+yWhoops!  You charge right past $N&+y ... and fall into the &+BOcean&+y!&n",
					    TRUE, ch, 0, victim, TO_CHAR);
					char_from_room(ch);
					char_to_room(ch, room, -1);
					act("&+y$n &+ycomes charging into the &+BOcean&+y!  Splash...&n",
					    TRUE, ch, 0, NULL, TO_ROOM);
				}
				else
				{
					act("&+y$n &+ycharges right past you ... and stops just short of the &+BOcean&+y!&n",
					    TRUE, ch, 0, victim, TO_VICT);
					act("&+y$n &+ycharges through the room ... and stops just short of the &+BOcean&+y!&n",
					    TRUE, ch, 0, victim, TO_ROOM);
					act("&+yWhoops!  You charge right past $N&+y ... and stop just short of the &+BOcean&+y!&n",
					    TRUE, ch, 0, victim, TO_CHAR);
				}
				return;
			}

			/* Vroom, straight on through */
			act("$n &+ycharges right past you!", TRUE, ch, 0, victim, TO_VICT);
			act("$n &+ycharges through the room!", TRUE, ch, 0, victim, TO_ROOM);
			act("&+yWhoops!  You charge right past $N!", TRUE, ch, 0, victim, TO_CHAR);

			a = do_simple_move(ch, dir, 0);

			if (IS_ALIVE(ch))
			{
				act("$n curses under $s breath.&n", 0, ch, NULL, NULL, TO_ROOM);
			}
		}
		else if (IS_RIDING(ch))
		{
			act("$n &+ycharges in and $s mount maneuvers too quickly!", 0, ch, 0,
			    victim, TO_ROOM);
			send_to_char(
				"&+yYou &=LRcharge&n&n &+yand your mount adjusts its course too quickly!\r\n",
				ch);
			SET_POS(ch, POS_PRONE + GET_STAT(ch));
		}
		else if (has_innate(ch, INNATE_CHARGE))
		{
			act("$n &+ycharges&n and ends up on $s face!&n", 0, ch, 0, victim, TO_ROOM);
			send_to_char("&+yYou &=LRcharge&n&n &+yand end up on your face!\r\n", ch);
			SET_POS(ch, POS_PRONE + GET_STAT(ch));
		}
		else
		{
			act("$n &+ycharges&n and stumbles!&n", 0, ch, 0, victim, TO_ROOM);
			send_to_char("&+yYou &=LRcharge&n&n &+yand stumble!\r\n", ch);
			SET_POS(ch, POS_PRONE + GET_STAT(ch));
		}
	}
	return;
}

void do_kill(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim;
	char Gbuf1[MAX_STRING_LENGTH];

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	// Only gods with bare hands execute the quick-kill code.
	//   Otherwise, we just do_hit.
	if (!IS_TRUSTED(ch) || ch->equipment[WIELD] || ch->equipment[SECONDARY_WEAPON])
	{
		do_hit(ch, argument, CMD_HIT);
		return;
	}

	one_argument(argument, Gbuf1);

	if (!*Gbuf1)
	{
		send_to_char("Slay whom?\n", ch);
	}
	else
	{
		victim = get_char_room_vis(ch, Gbuf1);

		if (!victim)
		{
			send_to_char("He/she/it isn't here.\n", ch);
		}
		else if (ch == victim)
		{
			send_to_char("Your mother would be so sad... \n", ch);
		}
		else if (IS_TRUSTED(victim))
		{
			send_to_char("Not a chance...\n", ch);
		}
		else if (training_dummy_is(victim))
		{
			do_hit(ch, argument, CMD_HIT);
		}
		else
		{
			if (IS_PC(victim))
			{
				statuslog(victim->player.level, "%s killed by %s at %s [%d]",
					  GET_NAME(victim), GET_NAME(ch),
					  world[victim->in_room].name,
					  world[victim->in_room].number);
			}

			act("You grab $M by the throat and rip out $S still beating heart!", FALSE,
			    ch, 0, victim, TO_CHAR);
			act("$N grabs you by the throat and rips out your still beating heart!",
			    FALSE, victim, 0, ch, TO_CHAR);
			act("$n grabs $N by the throat and rips out $S still beating heart!", FALSE,
			    ch, 0, victim, TO_NOTVICT);

			if (!strcmp(GET_NAME(ch), "Lohrr") && !number(0, 99))
			{
				act("You eat $n's heart.", FALSE, ch, NULL, victim, TO_CHAR);
				act("$N eats your heart.", FALSE, ch, NULL, victim, TO_VICT);
				act("$N eats $n's heart.", FALSE, ch, NULL, victim, TO_NOTVICT);
			}
			die(victim, ch);
		}
	}
}

void do_backstab(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim;

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	// Toggle debugging on / off
	if (IS_TRUSTED(ch) && !strcmp(argument, "debug"))
	{
		backstab(ch, NULL);
		return;
	}

	if (GET_CHAR_SKILL(ch, SKILL_BACKSTAB) < 1)
	{
		send_to_char("You don't know how to backstab.\n", ch);
		return;
	}

	victim = ParseTarget(ch, argument);

	backstab(ch, victim);
}

void do_circle(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL;
	char target[128];

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (GET_CHAR_SKILL(ch, SKILL_CIRCLE) <= 0)
	{
		send_to_char("You twist around in a circle! Wheee!!!\r\n", ch);
		return;
	}

	if (IS_ROOM(ch->in_room, ROOM_SINGLE_FILE))
	{
		send_to_char("There is no room to circle your opponent in here.\r\n", ch);
		return;
	}

	if (GET_OPPONENT(ch))
	{
		circle(ch, GET_OPPONENT(ch));
		return;
	}

	one_argument(argument, target);

	if (!(victim = get_char_room_vis(ch, target)))
	{
		send_to_char("Circle whom?\n", ch);
	}
	else if (IS_ALIVE(victim))
	{
		circle(ch, victim);
	}
}

void event_uncircle(P_char ch, P_char victim, P_obj /*obj*/, void * /*args*/)
{
	unlink_char(ch, victim, LNK_CIRCLING);
}

void circling_broken(struct char_link_data *cld)
{
	act("$N suddenly orients $Mself into a more defensive position.", FALSE, cld->linking, 0,
	    cld->linked, TO_CHAR);
}

// How long, in pulses, a circle attempt keeps the next one from working.
static int circle_rest()
{
	return PULSE_VIOLENCE * 4;
}

// The circler's lag, in pulses.
static int circle_lag()
{
	return PULSE_VIOLENCE / 2;
}

// The chance threshold a circle rolls 1-100 against: assassins learn it faster.
static int circle_threshold(P_char ch)
{
	int skill = GET_CHAR_SKILL(ch, SKILL_CIRCLE);
	// Old school assassin mobs learn circle faster.
	if (GET_CLASS(ch, CLASS_ASSASSIN))
	{
		skill *= 2;
		if (skill > 100)
		{
			skill = 100;
		}
	}
	return skill;
}

extern float circle_damage_modifier();

// How long, in pulses, the circle holds: shorter when something is fighting the circler.
static int circle_duration(P_char ch, bool attacked)
{
	return (attacked ? 1 : 3) * ((int)ch->specials.base_combat_round + 1);
}

std::string circle_facts(P_char ch)
{
	const float modifier = circle_damage_modifier();
	return fact("Chance to get behind the target",
		    std::to_string(circle_threshold(ch)) + " in 100") +
	       fact("Damage on the circled target",
		    std::to_string((int)(modifier * 100)) + "% against a standing target, " +
			    std::to_string((int)((1 + modifier) / 2 * 100)) + "% otherwise") +
	       fact("How long it holds", seconds(circle_duration(ch, false))) +
	       fact("Before you can circle again", seconds(circle_rest())) +
	       fact("Your lag", seconds(circle_lag())) +
	       "  You can't circle while something is fighting you.\n";
}

bool circle(P_char ch, P_char victim)
{
	P_char tch;
	P_char t;
	int skill;

	if (get_linked_char(ch, LNK_CIRCLING))
	{
		send_to_char("You are already circling someone!\n", ch);
		return FALSE;
	}

	if (affected_by_spell(ch, SKILL_CIRCLE))
	{
		send_to_char("You aren't quite ready for another attempt.\n", ch);
		return 0;
	}

	if (ch == victim)
	{
		send_to_char(
			"You run in circles, attempting to stab yourself; your comrades stare at you in awe.\n",
			ch);
		return FALSE;
	}

	// Are they tanking?
	if (!IS_TRUSTED(ch))
	{
		for (t = world[ch->in_room].people; t; t = t->next_in_room)
		{
			if (GET_OPPONENT(t) == ch)
			{
				send_to_char(
					"It is a bit hard to circle someone when you are being beaten upon!\n",
					ch);
				return FALSE;
			}
		}
	}

	set_short_affected_by(ch, SKILL_CIRCLE, circle_rest());
	CharWait(ch, circle_lag());
	skill = circle_threshold(ch);

	if (!notch_skill(ch, SKILL_CIRCLE, get_property("skill.notch.offensive", 7)) &&
	    skill < number(1, 100))
	{
		act("Damn! You weren't quite stealthy enough, and $N noticed your attempt to circle $M!",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$n clumsily tries to sneak behind $N, but $N notices $m anyway.", FALSE, ch, 0,
		    victim, TO_NOTVICT);
		act("You notice $n attempting to maneuver behind you, and take a more defensive stance. Who is $e fooling?",
		    FALSE, ch, 0, victim, TO_VICT);
		return 0;
	}

	for (tch = world[ch->in_room].people; tch; tch = tch->next_in_room)
	{
		if (GET_OPPONENT(tch) == ch)
			break;
	}

	if (GET_OPPONENT(ch) == NULL)
		engage(ch, victim);

	act("You stealthily position yourself behind $N, circling $M.", FALSE, ch, 0, victim,
	    TO_CHAR);
	act("$n moves in the shadows, suddenly reappearing behind $N!", FALSE, ch, 0, victim,
	    TO_NOTVICT);
	act("$n disappears from your vision for a moment, suddenly appearing behind you; you fail to counter $s advance...",
	    FALSE, ch, 0, victim, TO_VICT);
	link_char(ch, victim, LNK_CIRCLING);
	add_event(event_uncircle, circle_duration(ch, tch), ch, victim, 0, 0, 0, 0);
	return 1;
}
/* old circle, once more commented out
void do_circle(P_char ch, char *argument, int cmd)
{
  P_char   victim;
  P_obj    weapon, first_w, second_w;
  byte     percent_chance;
  int   dam;
  struct affected_type af, *af_ptr;
  struct damage_messages eng_messages = {
    "You pretend to aim at $N's stomach only to circle $M around and place $p right in $S back.",
    "You instinctively bend protecting your stomach from $n's blow while $e stabs you right in the back!",
    "$n deceives $N with false attack and places $p right in $s back.",
    "$N makes a strange sound but is suddenly very silent as you place $p in $S back.",
    "Out of nowhere, $n stabs you in the back, RIP...",
    "$n places $p in the back of $N, resulting in some strange noises, a lot of blood and a corpse.", 0
  };
  struct damage_messages reg_messages = {
    "You sneak up behind $N and place $p right in $S back.",
    "$n stabbed you right in your back!",
    "$n sneaks up behind $N and places $p right in $S back.",
    "$N makes a strange sound but is suddenly very silent as you place $p in $S back.",
    "Out of nowhere, $n stabs you in the back, RIP...",
    "$n places $p in the back of $N, resulting in some strange noises, a lot of blood and a corpse.", 0
  };
  struct damage_messages *messages;

  victim = ParseTarget(ch, argument);

  if(IS_NPC(ch) && !IS_THIEF(ch))
    return;

  if(GET_CHAR_SKILL(ch, SKILL_CIRCLE) == 0)
  {
    send_to_char("You don't know how to sneak around people.\n", ch);
    return;
  }

  if(!victim)
  {
    send_to_char("Circle who?\n", ch);
    return;
  }

  if(get_takedown_size(ch) > get_takedown_size(victim) + 1 &&
      GET_POS(victim) > POS_KNEELING)
  {
    send_to_char
      ("Smirk. I don't believe you could sneak behind to stab it.\n", ch);
    return;
  }

  if(get_takedown_size(ch) + 1 < get_takedown_size(victim) &&
      GET_POS(victim) > POS_KNEELING)
  {
    send_to_char("Smirk. Backstabbing in a calf is not very effective.\n",
                 ch);
    return;
  }

  if(!CanDoFightMove(ch, victim))
    return;

  first_w = ch->equipment[WIELD];
  second_w = ch->equipment[SECONDARY_WEAPON];

  if((!first_w || !IS_BACKSTABBER(first_w)) &&
      (!second_w || !IS_BACKSTABBER(second_w)))
  {
    send_to_char("You have no backstabbing weapon currently wielded.\n", ch);
    return;
  }

  if(GET_OPPONENT(victim) && GET_OPPONENT(victim) == ch)
  {
    if(GET_CHAR_SKILL(ch, SKILL_CIRCLE) < 75)
      send_to_char("Although you haven't mastered circling someone hitting you, you try anyway..\n", ch);
    percent_chance = 3 * (MAX(0, GET_CHAR_SKILL(ch, SKILL_CIRCLE) - 70));
    messages = &eng_messages;
  } else {
    percent_chance = MIN(100, 20 + GET_CHAR_SKILL(ch, SKILL_CIRCLE));
    messages = &reg_messages;
  }

  if(first_w && IS_BACKSTABBER(first_w))
    weapon = first_w;
  else
    weapon = second_w;

  messages->obj = weapon;

  if(IS_AFFECTED(victim, AFF_AWARE) && IS_AWAKE(victim))
    percent_chance = (int)(0.5 * (float)percent_chance);

  percent_chance =
    (int) (percent_chance *
           ((double) BOUNDED(83, 50 + GET_C_DEX(ch) / 2, 120)) / 100);

  percent_chance = BOUNDED(0, percent_chance, 95);

  CharWait(ch, (int) (1.2 * PULSE_VIOLENCE));

  if(notch_skill(ch, SKILL_CIRCLE, get_property("skill.notch.offensive", 7))
    || percent_chance > number(0,100))
  {
    dam = (dice(weapon->value[1], MAX(1, weapon->value[2])) + weapon->value[2]);
    dam *= GET_LEVEL(ch)/5;
    melee_damage
        (ch, victim, dam, PHSDAM_NOREDUCE | PHSDAM_NOPOSITION, messages);
  }
  else
  {
    act("$N notices your attempt to circle $M and turns to you.", FALSE, ch, 0, victim, TO_CHAR);
    act("You notice $n's attempt to circle you.", FALSE, ch, 0, victim, TO_VICT);
    act("$N notices $n's attempt to circle $M.", FALSE, ch, 0, victim, TO_NOTVICT);
    hit(ch, victim, weapon);
  }
}
*/
#define CH_INROOM_SIZE 256

static divine_refusal_config current_divine_refusal_config()
{
	return divine_refusal_make_config(
		get_property("pets.divine_refusal.enabled", 0.0, false),
		get_property("pets.divine_refusal.summoner_only", 1.0, false),
		get_property("pets.divine_refusal.percent", 10.0, false),
		get_property("pets.divine_refusal.retry_lock_seconds", 4.0, false), WAIT_SEC);
}

static bool divine_refusal_eligible(P_char master, P_char pet, const divine_refusal_config &config)
{
	return master && pet && IS_PC(master) && IS_ALIVE(master) && IS_NPC(pet) &&
	       GET_MASTER(pet) == master && IS_AFFECTED(pet, AFF_CHARM) &&
	       GET_CLASS(pet, CLASS_CLERIC) &&
	       (!config.summoner_only || GET_CLASS(master, CLASS_SUMMONER));
}

static bool divine_refusal_order_candidate(P_char master, const divine_refusal_config &config,
					   int cmd)
{
	return config.enabled && config.percent > 0 && config.lock_pulses > 0 && master &&
	       IS_PC(master) && IS_ALIVE(master) &&
	       (!config.summoner_only || GET_CLASS(master, CLASS_SUMMONER)) && cmd > CMD_NONE &&
	       cmd < MAX_CMD && cmd != CMD_ABORT && cmd != CMD_FLEE;
}

static bool divine_refusal_command_blocked(P_char pet, int cmd)
{
	return (item_action_active(pet) || IS_AFFECTED2(pet, AFF2_CASTING)) &&
	       !cmd_allowed_while_casting(pet, cmd);
}

static void show_new_divine_refusal(P_char master, P_char pet)
{
	const bool pet_can_speak = !is_silent(pet, false) && CAN_SPEAK(pet);
	const bool master_can_hear =
		master->specials.z_cord == pet->specials.z_cord &&
		(IS_TRUSTED(master) ||
		 (!IS_ROOM(master->in_room, ROOM_SILENT) && !IS_AFFECTED4(master, AFF4_DEAF)));

	if (pet_can_speak)
	{
		act("$n says 'My deity has warned me against completing that action.'", TRUE, pet,
		    0, master, TO_NOTVICT | ACT_SILENCEABLE);
		if (master_can_hear)
			act("$N says 'My deity has warned me against completing that action.'",
			    FALSE, master, 0, pet, TO_CHAR | ACT_SILENCEABLE);
		else
			act("$N refuses your order with a solemn shake of $S head.", FALSE, master,
			    0, pet, TO_CHAR);
	}
	else
	{
		act("$n refuses the order with a solemn shake of $s head.", TRUE, pet, 0, master,
		    TO_NOTVICT);
		act("$N refuses your order with a solemn shake of $S head.", FALSE, master, 0, pet,
		    TO_CHAR);
	}
}

static bool divine_refusal_blocks_order(P_char master, P_char pet,
					const divine_refusal_config &config, int cmd,
					bool *new_refusal)
{
	if (new_refusal)
		*new_refusal = false;

	const bool recognized = cmd > CMD_NONE && cmd < MAX_CMD;
	const bool exempt = cmd == CMD_ABORT || cmd == CMD_FLEE;
	const bool blocked = recognized && divine_refusal_command_blocked(pet, cmd);
	const divine_refusal_outcome outcome = divine_refusal_decide(
		config, divine_refusal_eligible(master, pet, config), recognized, exempt, blocked,
		ne_event_tick, &pet->specials.divine_refusal_until_pulse, number);

	if (outcome == divine_refusal_outcome::refused_new)
	{
		show_new_divine_refusal(master, pet);
		if (new_refusal)
			*new_refusal = true;
		return true;
	}
	if (outcome == divine_refusal_outcome::refused_active)
	{
		act("$N is still refusing that order.", FALSE, master, 0, pet, TO_CHAR);
		return true;
	}
	return false;
}

void do_order(P_char ch, char *argument, int /*comd*/)
{
	char name[MAX_INPUT_LENGTH], message[MAX_INPUT_LENGTH];
	char cmd[MAX_INPUT_LENGTH], temp[MAX_INPUT_LENGTH], lowcmd[MAX_INPUT_LENGTH];
	char buf[256];
	bool found = FALSE, l_delay = FALSE, acknowledged = FALSE, refused = FALSE;
	int i, len, org_cord, numb_ch = 0;
	P_char victim, ch_inroom[CH_INROOM_SIZE], tmp_ch;
	P_char k = NULL;

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	half_chop(argument, name, message);
	half_chop(message, cmd, temp);

	if (is_silent(ch, TRUE))
	{
		return;
	}

	if (IS_MORPH(ch))
	{
		send_to_char("You're a morph, not a telepath.\n", ch);
		return;
	}

	if (IS_AFFECTED(ch, AFF_KNOCKED_OUT))
	{
		send_to_char("&+wYou dream you are a god and order your phalanx into battle!&n\n",
			     ch);
		return;
	}

	if (IS_SET(ch->specials.affected_by2, AFF2_MAJOR_PARALYSIS) ||
	    IS_SET(ch->specials.affected_by2, AFF2_MINOR_PARALYSIS))
	{
		send_to_char("You're too paralyzed to do that.\n", ch);
		return;
	}

	if (!CAN_ACT(ch))
	{
		send_to_char("You unable to order anything at the moment!\n", ch);
		return;
	}

	if (IS_AFFECTED(ch, AFF_WRAITHFORM))
	{
		send_to_char("You can't speak in this form.\n", ch);
		return;
	}

	memset(ch_inroom, 0, sizeof(P_char) * CH_INROOM_SIZE);

	if (!*name || !*message)
	{
		send_to_char("Order who to do what?\n", ch);
		return;
	}
	else if (!(victim = get_char_room_vis(ch, name)) && str_cmp("follower", name) &&
		 str_cmp("followers", name))
	{
		send_to_char("That person isn't here.\n", ch);
		return;
	}
	else if (ch == victim)
	{
		send_to_char("You obviously suffer from schizophrenia.\n", ch);
		return;
	}
	else
	{
		if (GET_MASTER(ch) != NULL)
		{
			send_to_char("Your master would not like you giving orders!\n", ch);
			return;
		}
		if (victim && (GET_LEVEL(victim) >= (2 * GET_LEVEL(ch))))
		{
			act("$N refuses to obey such a wimp as you!", TRUE, ch, 0, victim, TO_CHAR);
			return;
		}

		for (tmp_ch = world[ch->in_room].people; tmp_ch; tmp_ch = tmp_ch->next_in_room)
			numb_ch++;

		if (numb_ch >= CH_INROOM_SIZE)
		{
			send_to_char(
				"There are so many people in this room, it's impossible to hear yourself think!\n",
				ch);
			return;
		}

		tmp_ch = world[ch->in_room].people;

		for (i = 0; i < numb_ch; i++)
		{
			ch_inroom[i] = tmp_ch;
			tmp_ch = tmp_ch->next_in_room;

			if (!tmp_ch)
				break;
		}

		/*    ch_inroom[i] = NULL;*/
		const divine_refusal_config refusal_config = current_divine_refusal_config();
		const int refusal_cmd = ordered_command_number(message);
		const bool refusal_can_apply =
			divine_refusal_order_candidate(ch, refusal_config, refusal_cmd);

		if (victim)
		{
			/*
			      snprintf(buf, MAX_STRING_LENGTH, "$N orders you to '%s'", message);
			*/
			/*
			if(IS_NPC(victim))
			{
			  if(GET_VNUM(victim) == 250)
			  {
			    send_to_char("That thing can't be ordered to do stuff.\n", ch);
			    return;
			  }
			}
			*/

			strcpy(buf, "$N orders you to do something.");
			act(buf, FALSE, victim, 0, ch, TO_CHAR);
			act("$n gives $N an order.", FALSE, ch, 0, victim, TO_ROOM);

			len = strlen(cmd);
			for (i = 0; i < len; i++)
				lowcmd[i] = tolower(cmd[i]);
			lowcmd[i] = '\0';

			if (GET_MASTER(victim) != ch || !IS_AFFECTED(victim, AFF_CHARM) ||
			    strstr(lowcmd, "rent"))
			{
				act("$n has an indifferent look.", FALSE, victim, 0, 0, TO_ROOM);
				return;
			}
			else
			{
				if (CAN_ACT(victim))
				{
					bool new_refusal = false;
					if (divine_refusal_blocks_order(ch, victim, refusal_config,
									refusal_cmd, &new_refusal))
					{
						CharWait(ch, new_refusal ? PULSE_VIOLENCE : 2);
						return;
					}
					send_to_char("Ok.\n", ch);
					SET_BIT(ch->specials.affected_by5, AFF5_ORDERING);
					command_interpreter(victim, message);
					REMOVE_BIT(ch->specials.affected_by5, AFF5_ORDERING);
					if (char_in_list(ch))
					{
						if (char_in_list(victim) && !CAN_ACT(victim))
							CharWait(ch, PULSE_VIOLENCE);
						else
							CharWait(ch, 2);
					}
					return;
				}
				else
				{
					act("$N seems a bit busy at the moment, try later.", FALSE,
					    ch, 0, victim, TO_CHAR);
					return;
				}
			}
		}
		else
		{ /* This is order "followers" */
			act("$n gives an order to $s followers.", FALSE, ch, 0, 0, TO_ROOM);
			org_cord = ch->specials.z_cord;

			for (i = 0; i < numb_ch; i++)
			{
				k = ch_inroom[i];
				if (k && !char_in_list(k))
					k = NULL;

				if (k && ch)
				{
					if (k->in_room == ch->in_room &&
					    k->specials.z_cord == org_cord)
					{
						if (GET_MASTER(k) == ch)
						{
							if (IS_AFFECTED(k, AFF_CHARM))
							{
								/*
						if(IS_NPC(k))
								{
								  if(GET_VNUM(k) == 250)
								  {
								    continue;
								  }
								}
						*/
								if (!found)
								{
									found = TRUE;
									if (!refusal_can_apply)
									{
										send_to_char(
											"Ok.\n",
											ch);
										acknowledged = TRUE;
									}
								}
								if (!CAN_ACT(k) || IS_IMMOBILE(k))
								{
									act("$N seems a bit busy at the moment, try later.",
									    FALSE, ch, 0, k,
									    TO_CHAR);
								}
								else
								{
									bool new_refusal = false;
									if (divine_refusal_blocks_order(
										    ch, k,
										    refusal_config,
										    refusal_cmd,
										    &new_refusal))
									{
										refused = TRUE;
										if (new_refusal)
											l_delay =
												TRUE;
										continue;
									}
									if (!acknowledged)
									{
										send_to_char(
											"Ok.\n",
											ch);
										acknowledged = TRUE;
									}
									/*
									                  snprintf(buf, MAX_STRING_LENGTH, "$n orders you to '%s'", message);
									*/
									strcpy(buf,
									       "$n orders you to do something.");
									act(buf, TRUE, ch, 0, k,
									    TO_VICT);
									SET_BIT(ch->specials
											.affected_by5,
										AFF5_ORDERING);
									command_interpreter(
										k, message);
									REMOVE_BIT(
										ch->specials
											.affected_by5,
										AFF5_ORDERING);

									if (!char_in_list(ch))
										return; /* leader died */
									/*
									                              if(!(k)) {
									                                logit(LOG_DEBUG, "k got lost in do_order()");
									                              }
									            */
									if (!l_delay &&
									    (!char_in_list(k) ||
									     !CAN_ACT(k) ||
									     IS_IMMOBILE(k)))
									{
										l_delay = TRUE;
									}
								}
							}
						}
					}
				}
			}

			if (!found)
				send_to_char("None here are loyal subjects of yours!\n", ch);
			else
			{
				// Preserve the legacy acknowledgement for groups where every loyal
				// follower was busy. An all-refusal group must not say "Ok".
				if (!acknowledged && !refused)
					send_to_char("Ok.\n", ch);
				if (l_delay)
					CharWait(ch, PULSE_VIOLENCE);
				else
					CharWait(ch, 2);
			}
		}
	}
}

#undef CH_INROOM_SIZE

bool bad_flee_dir(const P_char ch, const int to_room)
{
	P_char mount;

	mount = get_linked_char(ch, LNK_RIDING);
	return ((world[to_room].sector_type == SECT_NO_GROUND || world[to_room].chance_fall ||
		 world[to_room].sector_type == SECT_UNDRWLD_NOGROUND) &&
		!IS_TRUSTED(ch) && !IS_AFFECTED(ch, AFF_LEVITATE) && !IS_AFFECTED(ch, AFF_FLY) &&
		!(mount && (IS_AFFECTED(mount, AFF_LEVITATE) || IS_AFFECTED(mount, AFF_FLY))));
}

#define DRAGONSLAYER_VNUM 80569

/* Restore only Sneak granted directly by currently worn equipment. This deliberately
 * does not rebuild skills, innates, spells, protections, or other affect sources. */
static bool restore_equipment_sneak_after_flee(P_char ch)
{
	int i;

	if (!ch || IS_FIGHTING(ch) || IS_AFFECTED(ch, AFF_SNEAK))
		return FALSE;

	for (i = 0; i < MAX_WEAR; i++)
	{
		if (ch->equipment[i] && IS_SET(ch->equipment[i]->bitvector, AFF_SNEAK))
		{
			SET_BIT(ch->specials.affected_by, AFF_SNEAK);
			return TRUE;
		}
	}

	return FALSE;
}

// The chance threshold flee rolls 1-100 against to go the way the rogue chose.
static int control_flee_threshold(int control_skill)
{
	return control_skill * MAX_CHANCE_TO_CONTROL_FLEE / 100;
}

std::string control_flee_facts(P_char ch)
{
	if (!GET_CLASS(ch, CLASS_ROGUE))
		return "  Only rogues can choose where they flee.\n";
	return fact("Chance to flee the way you choose",
		    std::to_string(control_flee_threshold(GET_CHAR_SKILL(ch, SKILL_CONTROL_FLEE))) +
			    " in 100");
}

// The chance threshold a fleeing fighter rolls 1-100 against to slip away.
static int expeditious_retreat_threshold(P_char ch)
{
	return GET_CHAR_SKILL(ch, SKILL_EXPEDITIOUS_RETREAT);
}

// How long, in ticks, the fleer stays sneaking after slipping away.
static int expeditious_retreat_duration()
{
	return 1;
}

std::string expeditious_retreat_facts(P_char ch)
{
	return fact("Chance when you flee a fight",
		    std::to_string(MAX(0, expeditious_retreat_threshold(ch) - 1)) + " in 100") +
	       fact("Sneaking after you get away", game_hours(expeditious_retreat_duration()));
}

// The chance threshold a rider rolls 1-100 against to calm a fleeing mount.
int mounted_combat_calm_threshold(P_char rider)
{
	return BOUNDED(5, GET_CHAR_SKILL(rider, SKILL_MOUNTED_COMBAT), 95);
}

void do_flee(P_char ch, char *argument, int cmd)
{
	int i, attempted_dir, start_room, atts;
	char buf[MAX_INPUT_LENGTH];
	P_char was_fighting = NULL;
	struct affected_type af;
	char arg[512];
	arg[0] = '\0';
	int available_exits, stun_chance_flee;
	int chance_when_engaged, succeded;
	int percent_chance;
	int tmp_mv;
	bool expeditious = false;
	bool flee_exits[NUM_EXITS] = {};
	P_char rider = get_linking_char(ch, LNK_RIDING);
	P_char mount = get_linked_char(ch, LNK_RIDING);
	P_char mount_opponent = mount ? GET_OPPONENT(mount) : NULL;

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (IS_NPC(ch))
		if (mob_index[GET_RNUM(ch)].virtual_number == 11002 ||
		    mob_index[GET_RNUM(ch)].virtual_number == 11003 ||
		    mob_index[GET_RNUM(ch)].virtual_number == 11004 ||
		    IS_SET(ch->specials.act2, ACT2_NO_LURE) || GET_RACE(ch) == RACE_CONSTRUCT)
			return;

	if (IS_IMMOBILE(ch))
	{
		send_to_char("&+RNo fleeing for you. Try again later.\r\n", ch);
		return;
	}

	if (grapple_flee_check(ch))
	{
		send_to_char("You can't flee while locked in a hold!\n", ch);
		return;
	}

	// Trying to flee while stunned was swallowing the command. Let
	// us make it interesting, but not impossible. Jan08 -Lucrot
	if (IS_AFFECTED2(ch, AFF2_STUNNED) && IS_FIGHTING(ch))
	{
		act("&+cYo&+Cu t&+cry &+Cto&+c ov&+Cer&+cco&+Cme &+cyo&+Cur &+cw&+Goo&+czy &+Cfe&+cel&+Cing.&n",
		    FALSE, ch, 0, 0, TO_CHAR);

		if (IS_HUMANOID(ch))
			act("$n &+yseems to be trying to shake off $s woozy feeling.&n", FALSE, ch,
			    0, 0, TO_ROOM);
		else if (GET_RACE(ch) == RACE_QUADRUPED)
			act("$n &+ysnorts and kicks&n at the ground for balance.&n", FALSE, ch, 0,
			    0, TO_ROOM);
		else
			act("$n appears &+Gunbalanced&n and unable to react quickly!&n", FALSE, ch,
			    0, 0, TO_ROOM);

		stun_chance_flee = 0;

		stun_chance_flee += (int)(GET_C_WIS(ch) / 10); // 100 wis 10%

		stun_chance_flee += (int)(GET_LEVEL(ch) / 4); // level 50 12%

		// 22% chance to flee or about 1 in 5. Jan08 -Lucrot
		// Advanced meditation can add 10% more.

		if (GET_CHAR_SKILL(ch, SKILL_ADVANCED_MEDITATION) > 0)
			stun_chance_flee += (int)(SKILL_ADVANCED_MEDITATION / 10);

		if (number(1, 100) > stun_chance_flee)
			return;
	}

	if (IS_FIGHTING(ch) && ch->equipment[WEAR_BODY] &&
	    (obj_index[ch->equipment[WEAR_BODY]->R_num].virtual_number == DRAGONSLAYER_VNUM))
	{
		if (cmd != CMD_FLEE)
		{
			act("&+WA powerful magic compels you to stay and fight!", FALSE, ch, 0, 0,
			    TO_CHAR);
			act("$n tries to flee but something compels $m to stay!", FALSE, ch, 0, 0,
			    TO_ROOM);
			return;
		}
		else if (number(0, 1))
		{
			act("&+WYou fight valiantly to escape, but an unseen force compels you to stay.",
			    FALSE, ch, 0, 0, TO_CHAR);
			act("$n tries to flee but something compels $m to stay!", FALSE, ch, 0, 0,
			    TO_ROOM);
			tmp_mv = 30 + number(0, 10);

			if ((GET_VITALITY(ch) - tmp_mv) < 20)
				tmp_mv = GET_VITALITY(ch) - 20;

			GET_VITALITY(ch) -= tmp_mv;

			return;
		}
		else
			act("&+WYour will breaks the magic of the platemail, and you try to flee...",
			    FALSE, ch, 0, 0, TO_CHAR);
	}

	// Not standing, flee fails, but they stand (if they can)
	if (!MIN_POS(ch, POS_STANDING + STAT_RESTING))
	{
		act("Looking panicked, $n scrambles madly to $s feet!", TRUE, ch, 0, 0, TO_ROOM);
		send_to_char("You scramble madly to your feet!\n", ch);

		// Returns TRUE if ch dies in the process.
		if (check_crippling_strike(ch))
			return;

		SET_POS(ch, POS_STANDING + GET_STAT(ch));
		return;
	}

	if (IS_NPC(ch) && IS_SET(ch->specials.act, ACT_MOUNT) && cmd != CMD_FLEE)
	{
		if (rider)
		{
			percent_chance = mounted_combat_calm_threshold(rider);

			if (number(1, 100) < percent_chance)
			{
				send_to_char(
					"Your mount tries to flee, but your manage to calm it.\n",
					rider);
				return;
			}
		}
	}

	available_exits = 0;

	for (i = 0; i < NUM_EXITS; i++)
		if (world[ch->in_room].dir_option[i])
			if (CAN_GO(ch, i) && !bad_flee_dir(ch, EXIT(ch, i)->to_room) &&
			    can_enter_room(ch, EXIT(ch, i)->to_room, 0))
			{
				flee_exits[i] = true;
				available_exits++;
			}

	attempted_dir = -1;
	/* control flee skill tries to get attempted_dir */
	char *remaining = one_argument(argument, arg);
	while (remaining && isspace(*remaining))
		remaining++;
	int control_skill = IS_PC(ch) && GET_CLASS(ch, CLASS_ROGUE) ?
				    GET_CHAR_SKILL(ch, SKILL_CONTROL_FLEE) :
				    0;
	if (*arg && control_skill)
	{
		attempted_dir = dir_from_keyword(arg);
		if ((remaining && *remaining) || attempted_dir < 0)
		{
			send_to_char("Choose one escape direction: flee <direction>.\n", ch);
			return;
		}
		if (!flee_exits[attempted_dir])
		{
			send_to_char("You cannot flee through that exit.\n", ch);
			return;
		}
	}
	if (!available_exits)
	{
		send_to_char("You cannot find a safe exit to flee through!\n", ch);
		return;
	}

	// Expeditious retreat check. Apr09 -Lucrot
	if (!IS_SET(ch->specials.act, ACT_MOUNT) && IS_FIGHTING(ch) &&
	    (notch_skill(ch, SKILL_EXPEDITIOUS_RETREAT, 10) ||
	     (expeditious_retreat_threshold(ch) > number(1, 100))))
		expeditious = true;

	if (attempted_dir >= 0)
	{
		notch_skill(ch, SKILL_CONTROL_FLEE, get_property("skill.notch.offensive", 7));
		int chance = control_flee_threshold(control_skill);
		if (number(1, 100) > chance)
		{
			send_to_char("You panic and lose control of your escape direction!\n", ch);
			attempted_dir = -1;
		}
	}

	/* here we calculate a correct random dir if we haven't got any yet */
	if (attempted_dir == -1)
	{
		int picked = number(0, available_exits - 1);

		for (i = 0; i < NUM_EXITS; i++)
		{
			if (flee_exits[i])
			{
				if (!picked--)
				{
					attempted_dir = i;
					break;
				}
			}
		}
	}

	start_room = ch->in_room; /* room they initially tried to flee from */
	was_fighting = GET_OPPONENT(ch);
	atts = NumAttackers(ch);

	chance_when_engaged =
		MIN_CHANCE_TO_FLEE +
		MIN(3, available_exits - 1) * (MAX_CHANCE_TO_FLEE - MIN_CHANCE_TO_FLEE) / 3;

	succeded = attempted_dir >= 0 && (!was_fighting || (number(0, 100) < chance_when_engaged));

	if (IS_AFFECTED(ch, AFF_SNEAK))
		REMOVE_BIT(ch->specials.affected_by, AFF_SNEAK);

	act("$n attempts to flee.", TRUE, ch, 0, 0, TO_ROOM);
	send_to_char("You attempt to flee...\n", ch);

	if (grapple_check_entrapment(ch))
		return;

	if (mount_opponent)
		stop_fighting(mount);

	if (!IS_TRUSTED(ch) &&
	    !(GET_CLASS(ch, CLASS_DRUID) ||
	      (IS_MULTICLASS_PC(ch) && GET_SECONDARY_CLASS(ch, CLASS_DRUID))) &&
	    get_spell_from_room(&world[ch->in_room], SPELL_WANDERING_WOODS))
	{
		if (number(1, (int)((GET_C_INT(ch) - 100) / 20) + 100) < 61)
		{
			send_to_char("You try to leave, but just end up going in circles!\n", ch);
			act("$n leaves one direction and enters from another!", FALSE, ch, 0, 0,
			    TO_ROOM);
			succeded = FALSE;
		}
	}

	if (IS_PC(ch))
		ch->only.pc->pc_timer[1] = time(NULL);

	ch->points.delay_move = 0;

	const auto removal_before = character_removal_generation;
	if (succeded)
		succeded = do_simple_move(ch, attempted_dir, MVFLG_DRAG_FOLLOWERS | MVFLG_FLEE);

	if ((removal_before != character_removal_generation && !char_in_list(ch)) || !IS_ALIVE(ch))
		return;

	if (start_room == ch->in_room)
	{
		act("$n tries to flee, but can't make it out of here!", TRUE, ch, 0, 0, TO_ROOM);

		if (was_fighting)
			send_to_char("PANIC!  You couldn't escape!\n", ch);
		else
			send_to_char("You couldn't escape!\n", ch);

		if (mount_opponent && !IS_FIGHTING(mount) && !mount->specials.next_fighting)
			set_fighting(mount, mount_opponent);

		return;
	}
	else
	{
		if (IS_PC(ch))
			(void)telemetry_runtime_game_encounter_leave(
				ch, telemetry_encounter_outcome::flee);
		if (IS_PC(ch) && !GET_CLASS(ch, CLASS_ROGUE) &&
		    !has_innate(ch, INNATE_IMPROVED_FLEE))
		{
			StartRegen(ch, regen_resource::vitality);

			if (GET_VITALITY(ch) > 0)
				GET_VITALITY(ch) = MAX(0, (GET_VITALITY(ch) - (number(20, 30))));
		}
		else if (GET_CLASS(ch, CLASS_ROGUE) && GET_VITALITY(ch) > 0)
			GET_VITALITY(ch) = MAX(0, (GET_VITALITY(ch) - number(5, 15)));
		else if (rider && mount && GET_VITALITY(mount) > 0)
			GET_VITALITY(mount) = MAX(0, (GET_VITALITY(mount) - (number(30, 40))));

		if (succeded)
		{
			snprintf(buf, sizeof buf, "You flee %sward!\n", dirs[attempted_dir]);
			send_to_char(buf, ch);
		}
		else
			send_to_char("Your escape takes an unexpected turn.\n", ch);

		if (!affected_by_spell(ch, SKILL_AWARENESS))
		{
			/*if they survive, they are gonna be somewhat twitchy */
			bzero(&af, sizeof(af));
			af.type = SKILL_AWARENESS;
			af.duration = 1;
			af.bitvector = AFF_AWARE;
			af.flags = AFFTYPE_NODISPEL;
			affect_to_char(ch, &af);
		}

		if (expeditious)
		{
			bzero(&af, sizeof(af));
			af.type = SKILL_EXPEDITIOUS_RETREAT;
			af.duration = expeditious_retreat_duration();
			af.bitvector = AFF_SNEAK;
			affect_to_char(ch, &af);

			send_to_char(
				"You retreat, hiding in plain sight, looking for a new vantage point!\n",
				ch);
		}
	}

	if (atts)
		StopAllAttackers(ch);
	if (start_room != ch->in_room && restore_equipment_sneak_after_flee(ch))
		send_to_char(
			"The moment of panic has passed, and you slip back into a quiet step.\r\n",
			ch);

	if (was_fighting && IS_NPC(was_fighting))
	{
		/*
		 * rather than instant response, reschedule next event
		 * call .5 seconds from now, that will allow fast, but not
		 * impossible chases
		 */
		disarm_char_nevents(was_fighting, event_mob_mundane);
		add_event(event_mob_mundane, WAIT_SEC / 2, was_fighting, 0, 0, 0, 0, 0);
	}
}

#define MAX_STR_NORMAL 300

const char *monk_combos_messages[][2][3] = {
	{ { "$n spins around on $s foot and swings at $N with $s leg...",
	    "You spin around on your foot and swing at $N with your leg...",
	    "$n spins around on $s foot and swings at you with $s leg..." },
	  { "$n pulls $N's head down and brings $s knee up, smashing it...",
	    "You pull $N's head down and bring your knee up, smashing it...",
	    "$n pulls $N's head down and brings $s knee up, smashing it..." } },
	{ { "...then swings $s elbow around, smashing $N's face...",
	    "...then swing your elbow around, smashing $N's face...",
	    "...then swings $s elbow around, smashing your face..." },
	  { "...then spins around and roundkicks $N in the solar plexus...",
	    "...then spin around and roundkick $N in the solar plexus...",
	    "...then spins around and roundkicks you in the solar plexus..." } },
	{ { "...then smashes $N's head between $s fists...",
	    "...then smash $N's head between your fists...",
	    "...then smashes your head between $s fists..." },
	  { "...then pounds $N's face with a series of swift jabs...",
	    "...then pound $N's face with a series of swift jabs...",
	    "...then pounds your face with a series of swift jabs..." } },
	{ { "...then drops to the ground and makes a sweeping kick to $N's thigh...",
	    "...then drop to the ground and make a sweeping kick to $N's thigh...",
	    "...then drops to the ground and makes a sweeping kick to your thigh..." },
	  { "...then grabs $N by the arm, twists $M around, and kicks $M in the back...",
	    "...then grab $N by the arm, twist $M around, and kick $M in the back...",
	    "...then grabs you by the arm, twists you around, and kicks you in the back..." } },
	{ { "...then nails $N with a swift uppercut...", "...then nail $N with a swift uppercut...",
	    "...then nails you with a swift uppercut..." },
	  { "...then launches a mighty kick to $N's groin...",
	    "...then launch a mighty kick to $N's groin...",
	    "...then launches a mighty kick to your groin..." } },
	{ { "...then whirls around behind $N sending a crushing blow to $S spine...",
	    "...then whirl around behind $N sending a crushing blow to $S spine...",
	    "...then whirls around behind you sending a crushing blow to your spine..." },
	  { "...then shifts balance, and rams $s head into $N's face...",
	    "...then shift balance, and ram your head into $N's face...",
	    "...then shifts balance, and rams $s head into your face..." } },
	{ { "...then, summoning the incredible power of $s chi, delivers a double-handed open-palmed blow directly to $N's torso!",
	    "...then, summoning the incredible power of your chi, deliver a double-handed open-palmed blow directly to $N's torso!",
	    "...then, summoning the incredible power of $s chi, delivers a double-handed open-palmed blow directly to YOUR torso!" },
	  { "...then leaps into the air, delivering a crushing blow with $s foot down directly on $N's head!",
	    "...then leap into the air, delivering a crushing blow with your foot down directly on $N's head!",
	    "...then leaps into the air, delivering a crushing blow with $s foot down directly on your head!" } }
};

// Each blow's damage, before melee_damage applies the target's defenses.
static int combination_damage(const Rolls &rolls, int stage)
{
	switch (stage)
	{
	case 0:
		return rolls.number(1, 30);
	case 1:
		return rolls.number(30, 60);
	case 2:
		return rolls.number(40, 70);
	case 3:
		return rolls.number(50, 90);
	case 4:
		return rolls.number(60, 100);
	case 5:
		return rolls.number(60, 120);
	default:
		return rolls.number(100, 150);
	}
}

// The rating each blow needs for the next one to follow; the last blow has no next.
static int combination_skill_required(int stage)
{
	static const int required[] = { 25, 35, 40, 55, 70, 85 };
	return required[stage];
}

// True when the combination falls apart before the first blow, 1 time in 51.
static bool combination_fumble_roll(const Rolls &rolls)
{
	return !rolls.number(0, 50);
}

// The monk's lag after the blows, in pulses.
static int combination_lag()
{
	return 2 * PULSE_VIOLENCE;
}

// The final blow's stun, in pulses, from level 50.
static int combination_stun()
{
	return PULSE_VIOLENCE * 2;
}

// How long, in pulses, a combination keeps the next one from starting.
static int combination_rest()
{
	return get_property("timer.secs.monkCombination", 30) * WAIT_SEC;
}

// How long, in pulses, the monk prepares before the blows land.
static int combination_delay(int level)
{
	return level < 51 ? 2 * PULSE_VIOLENCE : PULSE_VIOLENCE;
}

std::string combination_facts(P_char ch)
{
	std::string facts;
	for (int stage = 0; stage < 7; stage++)
	{
		std::string needs;
		if (stage)
			needs = " (rating " +
				std::to_string(combination_skill_required(stage - 1)) + ")";
		facts += fact("Blow " + std::to_string(stage + 1) + needs,
			      show({ combination_damage(lowest_rolls, stage),
				     combination_damage(highest_rolls, stage) }));
	}
	facts +=
		fact("Preparing before the first blow", seconds(combination_delay(GET_LEVEL(ch)))) +
		fact("Your lag after the blows", seconds(combination_lag())) +
		fact("Before you can start another", real_time(combination_rest())) +
		fact("Chance it falls apart", "1 in 51");
	if (GET_LEVEL(ch) >= 50)
		facts += fact("Blow 7 stuns unless the target saves", seconds(combination_stun()));
	return facts + "  Each later blow also needs a roll; a miss ends the combination.\n"
		       "  Needs empty hands. Golems, dragons, ghosts and phantasmal forms are\n"
		       "  refused. The target's defenses apply to the damage after.\n";
}

void event_combination(P_char ch, P_char victim, P_obj /*obj*/, void * /*data*/)
{
	int percent = 100, skill, stage = 0, dam = 0, move, result, skill_req = 0;
	struct damage_messages messages = {
		0,
		0,
		0,
		"...then you feign low and in a blur of speed leap into the air landing a swift roundkick to $S head.\n"
		"$N topples to the ground, $S neck broken.",
		"...then feigns low and in a blur of speed leaps into the air landing a swift roundkick to your head.\n"
		"Your visions blurs as you topple to the ground, your neck broken.",
		"...then feigns low and in a blur of speed leaps into the air and lands a swift roundkick to $S head.\n"
		"$N topples to the ground, $S neck broken."
	};

	victim = GET_OPPONENT(ch);
	victim = guard_check(ch, victim);
	affect_from_char(ch, SKILL_COMBINATION);
	if (!victim)
	{
		send_to_char("Your opponent has escaped your deadly combination.\n", ch);
		return;
	}

	if (GET_POS(ch) < POS_STANDING)
	{
		send_to_char("You were unable to execute your deadly combination.\n", ch);
		return;
	}

	if (ch->in_room != victim->in_room)
	{
		send_to_char("&+wYour victim is gone...\r\n", ch);
		return;
	}

	if ((GET_RACE(victim) == RACE_GOLEM) || (GET_RACE(victim) == RACE_DRAGON) ||
	    (GET_RACE(victim) == RACE_GHOST) || (IS_AFFECTED4(victim, AFF4_PHANTASMAL_FORM)))
	{
		send_to_char("You decide this would be a futile effort.\n", ch);
		return;
	}

	/* Ok, let's get it on! */
	act("&+L$n's limbs begin to blur...&n", TRUE, ch, 0, 0, TO_ROOM);
	act("&+LYour limbs begin to blur...&n", TRUE, ch, 0, 0, TO_CHAR);

	skill = GET_CHAR_SKILL(ch, SKILL_COMBINATION);

	if (combination_fumble_roll(live_rolls))
	{
		act("&+R$n attempts a combination, but falls flat on $s face!", FALSE, ch, 0, 0,
		    TO_ROOM);
		act("&+RYou attempt a combination, but fall flat on your face!", FALSE, ch, 0, 0,
		    TO_CHAR);
		return;
	}

	if (GET_C_LUK(ch) / 2 > number(0, 100))
	{
		percent = (int)(percent * 1.05);
	}

	do
	{
		switch (stage)
		{
		case 0:
			dam = combination_damage(live_rolls, stage);
			if (GET_LEVEL(ch) < 50)
				percent -= 10;
			skill_req = combination_skill_required(stage);
			break;
		case 1:
			if (GET_LEVEL(ch) < 50)
				percent -= 5;
			skill_req = combination_skill_required(stage);
			dam = combination_damage(live_rolls, stage);
			break;
		case 2:
			if (GET_LEVEL(ch) < 50)
				percent -= 5;
			skill_req = combination_skill_required(stage);
			dam = combination_damage(live_rolls, stage);
			break;
		case 3:
			percent -= 5;
			skill_req = combination_skill_required(stage);
			dam = combination_damage(live_rolls, stage);
			break;
		case 4:
			percent -= 5;
			skill_req = combination_skill_required(stage);
			dam = combination_damage(live_rolls, stage);
			break;
		case 5:
			skill_req = combination_skill_required(stage);
			dam = combination_damage(live_rolls, stage);
			break;
		case 6:
			dam = combination_damage(live_rolls, stage);
			break;
		}
		move = number(0, 1);
		messages.attacker = monk_combos_messages[stage][move][1];
		messages.victim = monk_combos_messages[stage][move][2];
		messages.room = monk_combos_messages[stage][move][0];
		result = melee_damage(ch, victim, dam, PHSDAM_TOUCH, &messages);
		if (result == DAM_NONEDEAD && stage == 6 && GET_LEVEL(ch) >= 50)
		{
			Stun(victim, ch, combination_stun(), TRUE);
			if (IS_AFFECTED2(victim, AFF2_STUNNED))
			{
				act("Your final move stuns $N!", FALSE, ch, 0, victim, TO_CHAR);
				act("$N is stunned by $n's vicious combination!", FALSE, ch, 0,
				    victim, TO_NOTVICT);
			}
		}
		stage++;
	} while (stage < 7 && result == DAM_NONEDEAD && skill >= skill_req &&
		 percent > number(0, 100));

	notch_skill(ch, SKILL_COMBINATION, get_property("skill.notch.offensive", 7));

	CharWait(ch, combination_lag());
}

void do_combination(P_char ch, char * /*argument*/, int /*cmd*/)
{
	struct affected_type af;

	if (!ch)
		return;

	if (!GET_CHAR_SKILL(ch, SKILL_COMBINATION) || !GET_CLASS(ch, CLASS_MONK))
	{
		send_to_char("You wouldn't know where to start.\n", ch);
		return;
	}
	if (!IS_FIGHTING(ch))
	{
		send_to_char("You have no opponent.\n", ch);
		return;
	}
	if (!affect_timer(ch, combination_rest(), SKILL_COMBINATION))
	{
		send_to_char("You're still recovering from your last move.\n", ch);
		return;
	}
	if (ch->equipment[WIELD] || ch->equipment[HOLD])
	{
		send_to_char("Your limbs are too encumbered.\n", ch);
		return;
	}
	if (affected_by_spell(ch, SKILL_COMBINATION))
	{
		send_to_char("You're already preparing for a combination!\n", ch);
		return;
	}

	memset(&af, 0, sizeof(af));
	af.type = SKILL_COMBINATION;
	af.flags = AFFTYPE_NODISPEL | AFFTYPE_NOSHOW;
	af.duration = 1;
	affect_to_char(ch, &af);
	/* Yes, the higher the skill, the longer it takes to prepare */
	add_event(event_combination, combination_delay(GET_LEVEL(ch)), ch, 0, 0, 0, 0, 0);
	act("&+L$n begins moving into position for a combination...&n", TRUE, ch, 0, 0, TO_ROOM);
	act("&+LYou begin moving into position for a combination...&n", TRUE, ch, 0, 0, TO_CHAR);
}

// True when the barrage falls apart before the first attack, 1 time in 31.
static bool blade_barrage_fumble_roll(const Rolls &rolls)
{
	return !rolls.number(0, 30);
}

// The rating each attack needs for the next one to follow; the last attack has no next.
static int blade_barrage_skill_required(int stage)
{
	static const int required[] = { 25, 35, 40, 55, 70, 85 };
	return required[stage];
}

// The fighter's lag once the barrage starts, in pulses.
static int blade_barrage_lag()
{
	return 2 * PULSE_VIOLENCE;
}

// How long, in pulses, a barrage keeps the next one from starting.
static int blade_barrage_rest()
{
	return get_property("timer.secs.monkCombination", 30) * WAIT_SEC;
}

// How long, in pulses, the fighter prepares before the attacks land.
static int blade_barrage_delay(int level)
{
	return level < 51 ? 2 * PULSE_VIOLENCE : PULSE_VIOLENCE;
}

std::string blade_barrage_facts(P_char ch)
{
	int attacks = 1;
	while (attacks < 7 &&
	       GET_CHAR_SKILL(ch, SKILL_BLADE_BARRAGE) >= blade_barrage_skill_required(attacks - 1))
		attacks++;
	return fact("Most weapon attacks at your rating", std::to_string(attacks)) +
	       fact("Preparing before the first attack",
		    seconds(blade_barrage_delay(GET_LEVEL(ch)))) +
	       fact("Your lag once it starts", seconds(blade_barrage_lag())) +
	       fact("Before you can start another", real_time(blade_barrage_rest())) +
	       fact("Chance it falls apart, with no lag", "1 in 31") +
	       "  You must wield a weapon and be fighting. Each later attack also needs a\n"
	       "  roll; a miss ends the barrage.\n";
}

// Drannak - Blade Barrage
//  Note: this only notches if the victim lives through it.
void event_barrage(P_char ch, P_char victim, P_obj /*obj*/, void * /*data*/)
{
	int percent, skill, stage, skill_req = 0;

	victim = GET_OPPONENT(ch);
	victim = guard_check(ch, victim);
	affect_from_char(ch, SKILL_BLADE_BARRAGE);

	if (!IS_ALIVE(victim))
	{
		send_to_char("&+cYour opponent has escaped your deadly blade barrage.\n", ch);
		return;
	}

	if (GET_POS(ch) < POS_STANDING)
	{
		send_to_char(
			"&+cYou are unable to execute such a technique in your current position.\n",
			ch);
		return;
	}

	if (ch->in_room != victim->in_room)
	{
		send_to_char("&+cYour victim has escaped...\r\n", ch);
		return;
	}

	/* Ok, let's get it on! */
	act("&+L$n &nbecomes a &+gF&+GL&+gu&+GR&+gr&+GY &nof &+Lweapons &nas they begin their onslaught...&n",
	    TRUE, ch, 0, 0, TO_ROOM);
	act("&nYou become a &+gF&+GL&+gu&+GR&+gr&+GY &nof &+Lweapons &nas you begin your onslaught&n...",
	    TRUE, ch, 0, 0, TO_CHAR);

	skill = GET_CHAR_SKILL(ch, SKILL_BLADE_BARRAGE);

	if (blade_barrage_fumble_roll(live_rolls))
	{
		act("&+R$n attempts a fancy attack, but almost cuts $s fingers off in the process!",
		    FALSE, ch, 0, 0, TO_ROOM);
		act("&+RYou attempt your blade barrage, but fail to execute the deadly attack!",
		    FALSE, ch, 0, 0, TO_CHAR);
		return;
	}

	// Percentage to start with.
	if (GET_C_LUK(ch) / 2 > number(0, 100))
	{
		percent = 105;
	}
	else
	{
		percent = 100;
	}

	// Yes, we lag before the attacks; it doesn't stop them, and we don't have to worry about victim dying.
	CharWait(ch, blade_barrage_lag());
	stage = 0;
	do
	{
		switch (stage)
		{
		case 0:
			hit(ch, victim, ch->equipment[PRIMARY_WEAPON]);
			if (!(IS_ALIVE(ch) && IS_ALIVE(victim)))
			{
				return;
			}
			if (GET_LEVEL(ch) < 50)
				percent -= 10;
			skill_req = blade_barrage_skill_required(stage);
			break;
		case 1:
			hit(ch, victim, ch->equipment[SECONDARY_WEAPON]);
			if (!(IS_ALIVE(ch) && IS_ALIVE(victim)))
			{
				return;
			}
			if (GET_LEVEL(ch) < 50)
				percent -= 5;
			skill_req = blade_barrage_skill_required(stage);
			break;
		case 2:
			hit(ch, victim, ch->equipment[PRIMARY_WEAPON]);
			if (!(IS_ALIVE(ch) && IS_ALIVE(victim)))
			{
				return;
			}
			if (GET_LEVEL(ch) < 50)
				percent -= 5;
			skill_req = blade_barrage_skill_required(stage);
			break;
		case 3:
			hit(ch, victim, ch->equipment[SECONDARY_WEAPON]);
			if (!(IS_ALIVE(ch) && IS_ALIVE(victim)))
			{
				return;
			}
			percent -= 5;
			skill_req = blade_barrage_skill_required(stage);
			break;
		case 4:
			hit(ch, victim, ch->equipment[PRIMARY_WEAPON]);
			if (!(IS_ALIVE(ch) && IS_ALIVE(victim)))
			{
				return;
			}
			percent -= 5;
			skill_req = blade_barrage_skill_required(stage);
			break;
		case 5:
			hit(ch, victim, ch->equipment[SECONDARY_WEAPON]);
			if (!(IS_ALIVE(ch) && IS_ALIVE(victim)))
			{
				return;
			}
			skill_req = blade_barrage_skill_required(stage);
			break;
		case 6:
			hit(ch, victim, ch->equipment[PRIMARY_WEAPON]);
			break;
		default:
			break;
		}
		stage++;
	} while (stage < 7 && skill >= skill_req && percent >= number(1, 100));

	notch_skill(ch, SKILL_BLADE_BARRAGE, get_property("skill.notch.offensive", 7));
}

void do_consume(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL;
	struct affected_type *af;
	victim = ParseTarget(ch, argument);

	if (!ch)
		return;

	if (!GET_SPEC(ch, CLASS_ANTIPALADIN, SPEC_VIOLATOR))
	{
		send_to_char("Consuming &+rflesh&n is too &+Ldark &nan art for you.&n\n", ch);
		return;
	}

	if (!victim)
	{
		send_to_char("Who's &+gflesh &nwould you like to consume?&n\n", ch);
		return;
	}

	if (!IS_AFFECTED5(victim, AFF5_DECAYING_FLESH))
	{
		send_to_char(
			"Your victim does not appear to be affected by &+gdecaying &+Gflesh&n.\n",
			ch);
		return;
	}
	else
	{
		act("&+L$n &nmakes a gesture, and chunks of &+R$N&n's &+grotten &+yflesh&n fall to the ground with a dull &+Lthud&n...&n",
		    FALSE, ch, 0, victim, TO_NOTVICT);
		act("&+L$n &nmakes a gesture, and chunks of your &+grotten &+yflesh&n fall to the ground with a dull &+Lthud&n...&n",
		    FALSE, ch, 0, victim, TO_VICT);
		act("You &nmake a gesture, and chunks of &+R$N&n's &+grotten &+yflesh&n fall to the ground with a dull &+Lthud&n...&n",
		    FALSE, ch, 0, victim, TO_CHAR);
		int tdam;
		tdam = (int)(GET_LEVEL(ch) * .8);
		/*if(!NewSaves(victim, SAVING_FEAR, 0))
		tdam = (int) (tdam * 1.33);*/
		af = get_spell_from_char(victim, SPELL_DECAYING_FLESH);
		vamp(ch, tdam, static_cast<double>(GET_MAX_HIT(ch)) * VAMPPERCENT(ch));
		// spell_damage(ch, victim, 4 * GET_LEVEL(ch), SPLDAM_GENERIC, RAWDAM_NOKILL, 0);
		while (--af->modifier > 0)
		{
			int temp_dam;
			temp_dam = (int)(GET_LEVEL(ch) * .8);
			act("...another chunk of &+R$N&n's &+grotten &+yflesh&n falls to the ground...&n",
			    FALSE, ch, 0, victim, TO_NOTVICT);
			act("...another chunk of your &+grotten &+yflesh&n falls to the ground...&n",
			    FALSE, ch, 0, victim, TO_VICT);
			act("...another chunk of &+R$N&n's &+grotten &+yflesh&n falls to the ground, and you feel your &+gprayer &nflow back into your mind...&n",
			    FALSE, ch, 0, victim, TO_CHAR);
			memorize_last_spell(ch);
			char buf[256];
			send_to_char(buf, ch);
			/*if(!NewSaves(victim, SAVING_FEAR, 0))
			temp_dam = (int) (temp_dam * 1.33);*/
			vamp(ch, temp_dam, static_cast<double>(GET_MAX_HIT(ch)) * VAMPPERCENT(ch));
			spell_damage(ch, victim, 3 * GET_LEVEL(ch), SPLDAM_GENERIC, RAWDAM_NOKILL,
				     0);
		}
		memorize_last_spell(ch);
		char buf[256];
		send_to_char(buf, ch);
		--af->modifier;
		REMOVE_BIT(victim->specials.affected_by5, AFF5_DECAYING_FLESH);
		affect_from_char(victim, SPELL_DECAYING_FLESH);
		spell_damage(ch, victim, 3 * GET_LEVEL(ch), SPLDAM_GENERIC, 0, 0);
		act("...with a final gesture, &+L$n&n tears the last bit of &+gr&+Go&+gt&+Gt&+gi&+Gn&+gg&+r flesh&n from $N&n's &+gco&+Lrrod&+ged&n body.&n\r\n",
		    FALSE, ch, 0, victim, TO_NOTVICT);
		act("...with a final gesture, &+L$n&n tears the last bit of &+gr&+Go&+gt&+Gt&+gi&+Gn&+gg&+r flesh&n from your&n &+gco&+Lrrod&+ged&n body.&n\r\n",
		    FALSE, ch, 0, victim, TO_VICT);
		act("...with a final gesture, &+Lyou&n tear the last bit of &+gr&+Go&+gt&+Gt&+gi&+Gn&+gg&+r flesh&n from $N&n's &+gco&+Lrrod&+ged&n body.&n\r",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("The mass of &+gflesh&n is quickly absorbed by you, leaving your body &+rstrengthened&n and your &+Lprayers &nrefreshed.&n\n",
		    FALSE, ch, 0, victim, TO_CHAR);
		CharWait(ch, PULSE_VIOLENCE);
	}
	attack_back(ch, victim, FALSE);
}

void do_barrage(P_char ch, char * /*argument*/, int /*cmd*/)
{
	struct affected_type af;

	if (!IS_ALIVE(ch))
		return;

	if (!GET_CHAR_SKILL(ch, SKILL_BLADE_BARRAGE))
	{
		send_to_char("You would probably hurt yourself trying.\n", ch);
		return;
	}

	if (!ch->equipment[WIELD])
	{
		send_to_char("&+CYou must have a weapon equipped in order to unleash a barrage!\n",
			     ch);
		return;
	}

	if (!IS_FIGHTING(ch))
	{
		send_to_char("You brandish your blades!... to no one in particular.\n", ch);
		return;
	}
	if (!affect_timer(ch, blade_barrage_rest(), SKILL_BLADE_BARRAGE))
	{
		send_to_char("You're still recovering from your last attempt.\n", ch);
		return;
	}

	if (affected_by_spell(ch, SKILL_BLADE_BARRAGE))
	{
		send_to_char("&+WYou're already executing a deadly barrage!\n", ch);
		return;
	}

	memset(&af, 0, sizeof(af));
	af.type = SKILL_BLADE_BARRAGE;
	af.flags = AFFTYPE_NODISPEL | AFFTYPE_NOSHOW;
	af.duration = 2;
	affect_to_char(ch, &af);
	/* Yes, the higher the skill, the longer it takes to prepare */
	add_event(event_barrage, blade_barrage_delay(GET_LEVEL(ch)), ch, 0, 0, 0, 0, 0);
	act("&+L$n &nbrandishes their &+Lweapons &nin a formal stance...&n", TRUE, ch, 0, 0,
	    TO_ROOM);
	act("&+LYou grasp your &+Lweapons &nand prepare for the &+Lonslaught&n...", TRUE, ch, 0, 0,
	    TO_CHAR);
}

void do_bash(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (IS_TRUSTED(ch) && !strcmp(argument, "debug"))
	{
		bash(ch, NULL, TRUE);
		return;
	}

	victim = ParseTarget(ch, argument);

	if (!IS_ALIVE(victim))
	{
		// CharWait(ch, (int)(0.5 * PULSE_VIOLENCE));
		send_to_char("Bash who?\n", ch);
		return;
	}

	bash(ch, victim);
}

void do_buck(P_char ch, char * /*argument*/, int /*cmd*/)
{
	if (!ch)
		return;

	buck(ch);
}

// The rusher's lag, in pulses.
static int rush_lag()
{
	return PULSE_VIOLENCE * 2;
}

std::string rush_facts(P_char ch)
{
	return fact("Chance to reach the target",
		    "up to " + std::to_string(GET_CHAR_SKILL(ch, SKILL_RUSH)) + " in 100") +
	       fact("Your lag", seconds(rush_lag())) +
	       "  Needs berserk. Your current opponent gets a free attack if it works.\n";
}

void rush(P_char ch, P_char victim)
{
	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (!CanDoFightMove(ch, victim))
	{
		return;
	}

	if (GET_OPPONENT(ch) && GET_OPPONENT(ch) == victim)
	{
		send_to_char("You are already fighting them!\n", ch);
		return;
	}

	if (victim == ch)
	{
		send_to_char("Just commit suicide.\n", ch);
		return;
	}

	CharWait(ch, rush_lag());

	if (notch_skill(ch, SKILL_RUSH, get_property("skill.notch.offensive", 7)) ||
	    number(1, 100) > GET_CHAR_SKILL(ch, SKILL_RUSH))
	{
		act("$n rushes toward $N in a furious rage, but misses $s target completely.",
		    FALSE, ch, 0, victim, TO_NOTVICT);
		act("$n rushes toward you in a furious rage, but you easily evade $s attack.",
		    FALSE, ch, 0, victim, TO_VICT);
		act("You try to madly rush at $N, but end up almost tripping yourself.", FALSE, ch,
		    0, victim, TO_CHAR);
	}
	else
	{
		act("$n rushes toward $N in a furious rage...", FALSE, ch, 0, victim, TO_NOTVICT);
		act("$n rushes toward you in a furious rage...", FALSE, ch, 0, victim, TO_VICT);
		act("&+rA red haze fills your vision as you madly rush at $N.", FALSE, ch, 0,
		    victim, TO_CHAR);

		if (GET_OPPONENT(ch))
		{
			// The person you are rushing away from gets a free attack.
			hit(GET_OPPONENT(ch), ch, GET_OPPONENT(ch)->equipment[PRIMARY_WEAPON]);
			stop_fighting(ch);
			set_fighting(ch, victim);
		}

		hit(ch, victim, ch->equipment[PRIMARY_WEAPON]);
	}

	return;
}

void do_rush(P_char ch, char *argument, int /*cmd*/)
{
	P_char target = NULL;
	char target_name[MAX_INPUT_LENGTH];

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (GET_CHAR_SKILL(ch, SKILL_RUSH) < 1)
	{
		send_to_char("&+GYou don't know how to rush.\n", ch);
		return;
	}

	if (!affected_by_spell(ch, SKILL_BERSERK))
	{
		send_to_char("&+LYou fail to muster sufficient &+Rrage &+Lto rush!\r\n", ch);
		return;
	}

	if (*argument)
		argument = one_argument(argument, target_name);
	else
	{
		send_to_char("Whom do you want to attack?\n", ch);
		return;
	}

	if (!on_front_line(ch))
	{
		send_to_char("You can't seem to reach!\n", ch);
		return;
	}

	if (!(target = get_char_room_vis(ch, target_name)))
	{
		send_to_char(
			"&+gYour eyes glow &+rred&+g with hatred, but you can't seem to find your victim.\n",
			ch);
		return;
	}

	SanityCheck(ch, "do_rush");

	if (!CanDoFightMove(ch, target))
	{
		return;
	}

	rush(ch, target);
}

void do_rescue(P_char ch, char *argument, int /*cmd*/)
{
	P_char target = NULL;
	char target_name[MAX_INPUT_LENGTH];

	if (!ch)
		return;

	if (!IS_ALIVE(ch))
		return;

	if (*argument)
		argument = one_argument(argument, target_name);
	else
	{
		send_to_char("Who do you want to rescue?\n", ch);
		return;
	}

	if (!on_front_line(ch))
	{
		send_to_char("You can't seem to reach!\n", ch);
		return;
	}

	SanityCheck(ch, "do_rescue");

	if (!(target = get_char_room_vis(ch, target_name)))
	{
		send_to_char("Who do you want to rescue?\n", ch);
		return;
	}

	if (GET_SPEC(ch, CLASS_WARRIOR, SPEC_GUARDIAN) && strstr(argument, "all") &&
	    GET_LEVEL(ch) >= 46)
		rescue(ch, target, TRUE);
	else
		rescue(ch, target, FALSE);
}

// NPC maul check. May09 -Lucrot

bool isMaulable(P_char ch, P_char victim)
{
	if (!IS_ALIVE(ch) || !IS_ALIVE(victim) || !CanDoFightMove(ch, victim) ||
	    !GET_CHAR_SKILL(ch, SKILL_MAUL) || GET_CHAR_SKILL(ch, SKILL_MAUL) < 1 ||
	    GET_POS(ch) != POS_STANDING || GET_POS(victim) != POS_STANDING ||
	    ch->in_room != victim->in_room || IS_IMMATERIAL(victim) || IS_ELEMENTAL(victim) ||
	    IS_WATERFORM(victim) || IS_DRAGON(victim) ||
	    (IS_NPC(victim) && IS_SET(victim->specials.act, ACT_NO_BASH)) ||
	    ch->specials.z_cord != 0)
	{
		return false;
	}

	if ((has_innate(victim, INNATE_HORSE_BODY) || has_innate(victim, INNATE_SPIDER_BODY)) &&
	    get_takedown_size(ch) <= get_takedown_size(victim))
	{
		return false;
	}

	if (get_takedown_size(victim) > get_takedown_size(ch) + 1)
	{
		return false;
	}

	if (get_takedown_size(victim) < get_takedown_size(ch) - 1)
	{
		return false;
	}

	return true;
}

void do_maul(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL;

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (GET_CHAR_SKILL(ch, SKILL_MAUL) < 1)
	{
		send_to_char("You don't know how to maul.\n", ch);
		return;
	}

	victim = ParseTarget(ch, argument);

	if (!IS_ALIVE(victim))
	{
		send_to_char("Maul who?\n", ch);
		return;
	}

	maul(ch, victim);
}

void do_restrain(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL;

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (GET_CHAR_SKILL(ch, SKILL_RESTRAIN) < 1)
	{
		send_to_char("&+LThe depths fail to respond to your incantation.&n\n", ch);
		return;
	}
	victim = ParseTarget(ch, argument);

	if (!IS_ALIVE(victim))
	{
		send_to_char("&+LWho would you like restrained?&n\n", ch);
		return;
	}
	restrain(ch, victim);
}

// A kick's damage before its roll: the better of half strength and martial arts, plus kick.
static int kick_base_damage(P_char ch)
{
	return MAX((int)(GET_C_STR(ch) / 2), GET_CHAR_SKILL(ch, SKILL_MARTIAL_ARTS)) +
	       GET_CHAR_SKILL(ch, SKILL_KICK);
}

// A kick's roll: half the base up to the base.
static int kick_rolled_damage(const Rolls &rolls, int dam)
{
	return rolls.number((int)(dam / 2), dam);
}

static int kick_scaled_damage(int dam)
{
	return (int)(dam * get_property("kick.damage.modifier", 1.000));
}

// The extra scaling dragons, dracoliches and centaurs get by level.
static int kick_quick_damage(int dam, int level)
{
	return (dam * 2 * level) / 60;
}

// The kicker's lag, in pulses, for dragons, dracoliches and centaurs.
static int kick_quick_lag()
{
	return (int)((PULSE_VIOLENCE * 2) / 3);
}

// The kicker's lag for everyone else, in pulses.
static int kick_lag(const Rolls &rolls)
{
	return (PULSE_VIOLENCE * 3) / 2 + rolls.number(-WAIT_SEC, WAIT_SEC);
}

// The target's lag, in pulses, after a kick out of the room.
static int kick_room_lag()
{
	return (int)(PULSE_VIOLENCE * get_property("kick.roomkick.victimlag", 1.000));
}

// The target's lag, in pulses, after a kick into a wall.
static int kick_wall_lag()
{
	return (int)(PULSE_VIOLENCE * get_property("kick.wallkick.victimlag", 1.5));
}

// The target's lag, in pulses, after a low kick from below.
static int kick_groin_lag()
{
	return (int)(PULSE_VIOLENCE * get_property("kick.groinkick.victimlag", 1.000));
}

// True on the 1 kick in 11 that lands low on a bigger humanoid.
static bool kick_low_roll(const Rolls &rolls)
{
	return !rolls.number(0, 10);
}

// True on the 1 in 25 kick into a wall or low kick that stuns.
static bool kick_stun_roll(const Rolls &rolls)
{
	return !rolls.number(0, 24);
}

// How long, in pulses, a kick into a wall stuns.
static int kick_wall_stun(const Rolls &rolls)
{
	return (PULSE_VIOLENCE * rolls.number(4, 9)) / 4;
}

// How long, in pulses, a low kick stuns.
static int kick_groin_stun(const Rolls &rolls)
{
	return (PULSE_VIOLENCE * rolls.number(4, 13)) / 4;
}

std::string kick_facts(P_char ch)
{
	const bool quick = IS_DRAGON(ch) || IS_CENTAUR(ch);
	int low = kick_scaled_damage(kick_rolled_damage(lowest_rolls, kick_base_damage(ch)));
	int high = kick_scaled_damage(kick_rolled_damage(highest_rolls, kick_base_damage(ch)));
	if (quick)
	{
		low = kick_quick_damage(low, GET_LEVEL(ch));
		high = kick_quick_damage(high, GET_LEVEL(ch));
	}
	std::string asleep;
	if (quick)
		asleep = fact("Your lag if it leaves a target 2+ sizes off incapacitated",
			      seconds(takedown_sleeping_target_lag())) +
			 "    (you attack it again; a sleeper just wakes when the kick lands)\n";
	return fact("Damage on a hit", show({ low, high }) + " with your strength and ratings") +
	       fact("Your lag", quick ? seconds(kick_quick_lag()) :
					seconds(kick_lag(lowest_rolls)) + " to " +
						seconds(kick_lag(highest_rolls))) +
	       asleep + "  A target that evades being sent flying adds no lag to yours.\n" +
	       fact("Target's lag if kicked out of the room", seconds(kick_room_lag())) +
	       fact("Target's lag if kicked into a wall instead", seconds(kick_wall_lag())) +
	       fact("  Chance that also stuns it",
		    "1 in 25, for " + seconds(kick_wall_stun(lowest_rolls)) + " to " +
			    seconds(kick_wall_stun(highest_rolls))) +
	       "    (only a target 2 or more sizes smaller than you can be sent flying)\n" +
	       fact("Target's lag after a low kick", seconds(kick_groin_lag())) +
	       fact("  Chance that also stuns it",
		    "1 in 25, for " + seconds(kick_groin_stun(lowest_rolls)) + " to " +
			    seconds(kick_groin_stun(highest_rolls))) +
	       "    (only a humanoid 2 or more sizes bigger than you, at most 1 kick in 11,\n"
	       "    after the takedown roll)\n"
	       "  An immaterial target takes no damage. A stun needs a failed save, and\n"
	       "  elites can't be stunned. The target's defenses apply to the damage after.\n";
}

static bool kick_admitted(P_char ch, P_char victim)
{
	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
		return false;

	if (GET_CHAR_SKILL(ch, SKILL_KICK) == 0)
	{
		send_to_char("You don't know how to kick.\n", ch);
		return false;
	}

	if (IS_IMMOBILE(ch))
	{
		send_to_char("Wait a sec, you can't kick anyone right now.\n", ch);
		return false;
	}

	if (LEGLESS(ch))
	{
		send_to_char("You haven't the necessary body parts to do that.\n", ch);
		return false;
	}

	if (!on_front_line(ch))
	{
		send_to_char("You can't seem to break the ranks!\n", ch);
		return false;
	}

	if ((IS_PC(ch) || IS_PC_PET(ch)) && !on_front_line(victim))
	{
		send_to_char("You can't quite seem to reach them...\n", ch);
		return false;
	}

	return CanDoFightMove(ch, victim);
}

int chance_kick(P_char ch, P_char victim)
{
	if (!kick_admitted(ch, victim))
		return 0;

	int percent_chance = GET_CHAR_SKILL(ch, SKILL_KICK);

	if (GET_RACE(ch) == RACE_CENTAUR)
		percent_chance *= 2;

	percent_chance = (int)(percent_chance * ((double)BOUNDED(80, GET_C_DEX(ch), 125)) / 100);

	percent_chance =
		(int)(percent_chance *
		      ((int)BOUNDED(80, GET_C_STR(ch) + GET_C_AGI(ch) - GET_C_AGI(victim), 125)) /
		      100);

	if (GET_C_LUK(ch) / 10 > number(1, 100))
	{
		percent_chance = (int)(percent_chance * 1.05);
	}

	if (GET_C_LUK(victim) / 10 > number(1, 100))
	{
		percent_chance = (int)(percent_chance * 0.95);
	}

	if (IS_AFFECTED(victim, AFF_AWARE))
	{
		percent_chance = (int)(percent_chance * 0.9);
	}

	if (IS_NPC(ch))
	{
		percent_chance = (int)(percent_chance * 1.30);
	}

	if (IS_IMMOBILE(victim) || GET_STAT(victim) <= STAT_SLEEPING)
	{
		percent_chance = 100;
	}

	return percent_chance;
}

using forced_departure_message = std::pair<uint64_t, std::string>;

static bool can_receive_forced_departure(P_char recipient, P_char attacker)
{
	return recipient->desc && IS_AWAKE(recipient) &&
	       recipient->specials.z_cord == attacker->specials.z_cord &&
	       (IS_NPC(recipient) || !recipient->only.pc || !recipient->only.pc->ignored ||
		recipient->only.pc->ignored != attacker);
}

// Capture recipient-specific names while both combatants still have valid rooms.
// The caller sends these only after departure scripts have allowed the move.
static std::vector<forced_departure_message>
snapshot_forced_departure(P_char ch, P_char victim, int direction, bool tackle, bool rear)
{
	char actor_text[512], room_text[512];
	const char *target_text;
	if (tackle)
	{
		snprintf(actor_text, sizeof actor_text,
			 "You tackle $N HARD and go flying out of the room together!");
		snprintf(room_text, sizeof room_text,
			 "$n tackles $N HARD, sending them both flying out of the room!");
		target_text = "$n tackles you HARD and sends you both flying out of the room!";
	}
	else
	{
		const char *skill = rear ? "rearkick" : "kick";
		snprintf(actor_text, sizeof actor_text,
			 "Your mighty %s sends $N flying out of the room to the %s!&n", skill,
			 dirs[direction]);
		snprintf(room_text, sizeof room_text,
			 "$n's mighty %s sends $N flying out of the room to the %s!&n", skill,
			 dirs[direction]);
		target_text = rear ? "$n's mighty rearkick sends you flying out of the room!" :
				     "$n's mighty kick sends you flying out of the room!";
	}
	std::vector<forced_departure_message> messages;
	for (P_char recipient = world[ch->in_room].people; recipient;
	     recipient = recipient->next_in_room)
	{
		if (!can_receive_forced_departure(recipient, ch))
			continue;
		const int type = recipient == ch     ? TO_CHAR :
				 recipient == victim ? TO_VICT :
						       TO_NOTVICT;
		const char *message = recipient == ch	  ? actor_text :
				      recipient == victim ? target_text :
							    room_text;
		char rendered[3 * MAX_STRING_LENGTH];
		act_convert(rendered, message, ch, recipient, nullptr, victim, type);
		messages.emplace_back(recipient->runtime_id, rendered);
	}
	return messages;
}

static void deliver_forced_departure(const std::vector<forced_departure_message> &messages,
				     P_char ch, P_char victim, int source, bool paired)
{
	for (const auto &message : messages)
	{
		P_char recipient = find_character_by_runtime_id(message.first);
		if (!recipient || !can_receive_forced_departure(recipient, ch))
			continue;
		const int expected_room =
			recipient == victim || (paired && recipient == ch) ? NOWHERE : source;
		if (recipient->in_room == expected_room)
			send_to_char(message.second.c_str(), recipient);
	}
}

static void forced_rebound_messages(P_char ch, P_char victim, forced_block reason, bool tackle)
{
	const char *attacker, *target, *room;
	switch (reason)
	{
	case forced_block::mountain:
		attacker =
			"The mountainside sends $N bouncing back down. So much for the scenic route!";
		target =
			"You go flying up the mountainside, almost glimpse the peak, then bounce all the way back down!";
		room = "$N sails up the mountainside, then tumbles back down in a decidedly undignified heap.";
		break;
	case forced_block::cavern_wall:
		attacker = "$N ricochets off the cavern wall. The rock seems unimpressed.";
		target =
			"You meet the cavern wall with a thud and bounce back. The rock wins this round!";
		room = "$N ricochets off the cavern wall and lands in a heap. The rock remains undefeated.";
		break;
	case forced_block::door:
		attacker = "$N bounces off the firmly shut door. It declines to become a doorway.";
		target =
			"You bounce off the firmly shut door. Apparently it is not accepting visitors!";
		room = "$N bounces off a firmly shut door and lands in a heap.";
		break;
	case forced_block::private_room:
		attacker =
			"$N tumbles back when there is no room to land. Reservations apparently matter!";
		target =
			"There is no room to land, so you tumble back. Next time, make a reservation!";
		room = "$N finds no room to land and tumbles back into a heap.";
		break;
	case forced_block::invalid_room:
		attacker =
			"$N starts an impressive flight, but the route goes nowhere. The landing is less impressive.";
		target =
			"Your flight plan goes nowhere, so you land right where you started. Gracefully? Hardly.";
		room = "$N starts an impressive flight and lands right where $E started.";
		break;
	default:
		attacker =
			"$N meets an uncooperative obstacle and bounces straight back into a heap!";
		target =
			"An uncooperative obstacle ends your flight early. You bounce back into a heap!";
		room = "$N meets an uncooperative obstacle and bounces straight back into a heap.";
		break;
	}
	act(attacker, FALSE, ch, 0, victim, TO_CHAR);
	act(target, FALSE, ch, 0, victim, TO_VICT);
	act(room, FALSE, ch, 0, victim, TO_NOTVICT);
	if (tackle)
		send_to_char("Your tackle ends here with a less-than-triumphant tumble.\n", ch);
}

void kick(P_char ch, P_char victim)
{
	struct damage_messages messages;
	int takedown_chance, dam = 0, door;
	int random_number = number(1, 100);
	int vsize = get_takedown_size(victim);
	int csize = get_takedown_size(ch);
	int percent_chance = 0;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return;
	}

	if ((percent_chance = chance_kick(ch, victim)) == 0)
	{
		return;
	}

	dam = kick_base_damage(ch);

	// Randomize damage a bit. Jan08 -Lucrot
	dam = kick_rolled_damage(live_rolls, dam);

	// Adjust property for dragon damage. Jan08 -Lucrot
	dam = kick_scaled_damage(dam);

	// Dragons do more damage and adjusted by level and a bit quicker.
	// Includes dracoliches. Jan08 -Lucrot
	if (IS_DRAGON(ch) || IS_CENTAUR(ch))
	{
		dam = kick_quick_damage(dam, GET_LEVEL(ch));
		CharWait(ch, kick_quick_lag());
	}
	else
	{
		CharWait(ch, kick_lag(live_rolls));
	}

	// debug("&+gKick&n (%s) chance (%d) at (%s).", GET_NAME(ch), percent_chance, GET_NAME(victim));

	if (IS_IMMATERIAL(victim))
	{
		act("Your foot passes through $N. Even your best kick needs something solid to meet!",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$n's foot passes harmlessly through you. Being mist has its moments!", FALSE,
		    ch, 0, victim, TO_VICT);
		act("$n's kick passes through $N, rearranging absolutely nothing.", FALSE, ch, 0,
		    victim, TO_NOTVICT);
		engage(ch, victim);
		return;
	}

	if (!notch_skill(ch, SKILL_KICK, get_property("skill.notch.offensive", 7)) &&
	    percent_chance < number(1, 100))
	{
		kick_messages(ch, victim, FALSE, &messages);
		act(messages.attacker, FALSE, ch, 0, victim, TO_CHAR);
		act(messages.victim, FALSE, ch, 0, victim, TO_VICT);
		act(messages.room, FALSE, ch, 0, victim, TO_NOTVICT);

		engage(ch, victim);

		return;
	}

	kick_messages(ch, victim, TRUE, &messages);

	if (melee_damage(ch, victim, dam, PHSDAM_TOUCH, &messages) != DAM_NONEDEAD)
	{
		return;
	}

	if (csize <= (vsize - 2))
	{
		takedown_chance = (vsize - csize) * 4; // This was 5 per level.
	}
	else if (csize >= (vsize + 2))
	{
		takedown_chance = (csize - vsize) * 4; // This was 5 per level.
	}
	else
	{
		return;
	}

	if (IS_NPC(ch) && !GET_MASTER(ch))
	{
		takedown_chance = (int)(takedown_chance * 1.2);
	}

	if ((IS_CENTAUR(ch) || IS_OGRE(ch) || (GET_RACE(ch) == RACE_FIRBOLG) ||
	     (GET_RACE(ch) == RACE_BARBARIAN) || (GET_RACE(ch) == RACE_TROLL)) &&
	    !IS_NPC(ch))
	{
		takedown_chance = (int)(takedown_chance * 1.4);
	}

	takedown_chance = takedown_check(ch, victim, takedown_chance, SKILL_KICK,
					 TAKEDOWN_ALL ^ TAKEDOWN_AGI_CHECK ^ TAKEDOWN_FOOTING);

	if (takedown_chance == TAKEDOWN_CANCELLED || takedown_chance == TAKEDOWN_PENALTY)
	{
		return;
	}

	if (GET_POS(victim) != POS_STANDING)
	{
		takedown_chance /= 5;
	}

	if (GET_RACE(ch) == RACE_CENTAUR)
	{
		takedown_chance *= 2;
	}

	if (takedown_chance > random_number && csize > (vsize + 1))
	{
		door = number(0, 9);

		if ((door == DIR_UP) || (door == DIR_DOWN))
		{
			door = number(0, 3);
		}

		const int source_room = ch->in_room;
		const auto messages = snapshot_forced_departure(ch, victim, door, false, false);
		const auto movement = move_forced(
			ch, victim, door, [&]()
			{ deliver_forced_departure(messages, ch, victim, source_room, false); });
		if (movement.status == forced_move_status::arrived)
		{
			act("$n flies in, crashing on the floor!", TRUE, victim, 0, 0, TO_ROOM);
			SET_POS(victim, POS_PRONE + GET_STAT(victim));
			CharWait(victim, kick_room_lag());
		}
		else if (movement.status == forced_move_status::blocked)
		{
			forced_rebound_messages(ch, victim, movement.reason, false);
			SET_POS(victim, POS_PRONE + GET_STAT(victim));
			if (kick_stun_roll(live_rolls) && !IS_STUNNED(victim))
				Stun(victim, ch, kick_wall_stun(live_rolls), TRUE);
			stop_fighting(victim);
			CharWait(victim, kick_wall_lag());
		}
		return;
	}
	if (IS_HUMANOID(victim) && takedown_chance > random_number && csize < vsize &&
	    kick_low_roll(live_rolls))
	{
		act("Your nimble kick slams into $N's groin, and $N whimpers before crashing to the ground!",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$n's nimble kick crashes into your groin .. OUCH!!! .. and down you go!",
		    FALSE, ch, 0, victim, TO_VICT);
		act("$n's nimble kick connects with $N's groin...\r$N crashes to the ground!",
		    FALSE, ch, 0, victim, TO_NOTVICT);
		SET_POS(victim, POS_SITTING + GET_STAT(victim));
		update_group_vitals(victim);
		gmcp_char_vitals(victim);

		if (kick_stun_roll(live_rolls))
		{
			// Added a little more play in the stun time (from 1 pulse vio. to 3 1/4 pulse vio's).
			Stun(victim, ch, kick_groin_stun(live_rolls), TRUE);
		}
		stop_fighting(victim);
		CharWait(victim, kick_groin_lag());
	}
	return;
}

// What the dragoon's power adds to a mount command's chance threshold.
static int dragoon_power(P_char ch)
{
	return MAX(0, (int)(((GET_C_POW(ch) - 100) / 2)));
}

// The hit points a roar gives the dragoon's group and mount.
static int dragon_roar_hit_points(P_char ch)
{
	return (GET_CHAR_SKILL(ch, SKILL_DRAGON_ROAR) / 2);
}

// The hitroll and damroll a roar gives the dragoon's group and mount.
static int dragon_roar_bonus(P_char ch)
{
	return (GET_CHAR_SKILL(ch, SKILL_DRAGON_ROAR) / 20);
}

// How long, in ticks, a roar's effects last.
static int dragon_roar_duration(int dampoints)
{
	return (dampoints) / 2;
}

// The chance threshold of a roar, before the dragoon's power.
static int dragon_roar_threshold(P_char ch)
{
	int percent_chance = (95 * GET_CHAR_SKILL(ch, SKILL_DRAGON_ROAR)) / 100;
	percent_chance = BOUNDED(1, percent_chance, 99);
	return percent_chance;
}

// A dragon hunter roars at full rating, others at half.
static int dragon_roar_empower(P_char ch, bool is_hunter)
{
	return is_hunter ? GET_CHAR_SKILL(ch, SKILL_DRAGON_ROAR) :
			   GET_CHAR_SKILL(ch, SKILL_DRAGON_ROAR) / 2;
}

// What a roar takes from everyone else's hitroll and damroll, as a negative modifier.
static int dragon_roar_penalty(P_char ch, int empower)
{
	return 0 - MAX(2, (GET_LEVEL(ch) / 8) + (empower / 10));
}

// How long, in pulses, a roar keeps the dragoon from another dragon command.
static int dragon_roar_rest()
{
	return (int)(3 * PULSE_VIOLENCE);
}

// The dragoon's lag after a roar, in pulses.
static int dragon_roar_lag()
{
	return PULSE_VIOLENCE;
}

// A dragon hunter's roar: the threshold of its flee roll, and the highest level it scares.
static int dragon_roar_flee_threshold()
{
	return (int)get_property("skill.dragon_roar.hunter.flee.chance", 10.000);
}

static int dragon_roar_flee_level(P_char ch, int empower)
{
	return GET_LEVEL(ch) + MIN(5, (empower / 20));
}

std::string dragon_roar_facts(P_char ch)
{
	const int bonus = dragon_roar_bonus(ch);
	const bool is_hunter = GET_SPEC(ch, CLASS_DRAGOON, SPEC_DRAGON_HUNTER);
	const int empower = dragon_roar_empower(ch, is_hunter);
	const int penalty = dragon_roar_penalty(ch, empower);
	std::string flee;
	if (is_hunter)
		flee = fact("Chance each other target also flees",
			    std::to_string(dragon_roar_flee_threshold()) + " in 101, then " +
				    std::to_string(GET_CHAR_SKILL(ch, SKILL_DRAGON_ROAR)) +
				    " in 101") +
		       "    (up to level " + std::to_string(dragon_roar_flee_level(ch, empower)) +
		       ", on a failed fear check; not elites or greater races)\n";
	return fact("Chance",
		    std::to_string(MIN(100, dragon_roar_threshold(ch) + dragoon_power(ch) - 1)) +
			    " in 100") +
	       fact("Your group and dragon, hit points",
		    "+" + std::to_string(dragon_roar_hit_points(ch))) +
	       fact("Your group and dragon, hitroll and damroll", "+" + std::to_string(bonus)) +
	       fact("Everyone else in the room, hitroll and damroll", std::to_string(penalty)) +
	       fact("Duration", game_hours(dragon_roar_duration(bonus))) +
	       fact("Your lag", seconds(dragon_roar_lag())) +
	       fact("Before your next dragon command if it works", seconds(dragon_roar_rest())) +
	       flee +
	       "  Spends a prepared dragon circle; with none it does nothing. Each effect\n"
	       "  skips anyone who already has it.\n";
}

void do_dragon_roar(P_char ch, char * /*argument*/, int /*cmd*/)
{
	P_char victim = NULL, mount = NULL;
	int skl_lvl = 0;
	int hpoints = dragon_roar_hit_points(ch);
	int dampoints = dragon_roar_bonus(ch);
	int percent_chance;
	bool is_hunter = FALSE;
	struct affected_type af;
	char buf[MAX_STRING_LENGTH];

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (!SanityCheck(ch, "dragon_roar"))
		return;

	if ((skl_lvl = GET_CHAR_SKILL(ch, SKILL_DRAGON_ROAR)) == 0)
	{
		send_to_char("You don't know how.\r\n", ch);
		return;
	}

	if (IS_IMMOBILE(ch))
	{
		send_to_char("Hold up! You can't command your &+Gdr&+Lag&+Gon&n right now.\n", ch);
		return;
	}

	if (!has_dragoon_mount(ch))
	{
		send_to_char("You must command a &+Gdr&+Lag&+Gon&n to do that.\n", ch);
		return;
	}

	if (!is_dragoon_mounted(ch))
	{
		send_to_char("You must be riding a &+Gdr&+Lag&+Gon&n to do that.\n", ch);
		return;
	}

	mount = get_dragoon_mount(ch);

	if (mount == NULL)
	{
		send_to_char("You are not mounted on your &+Gdr&+Lag&+Gon&n.\n", ch);
		return;
	}

	if (affected_by_spell(ch, SKILL_DRAGON_ROAR) ||
	    affected_by_spell(ch, SKILL_DRAGON_BREATH) ||
	    affected_by_spell(ch, SKILL_DRAGON_STRIKE))
	{
		if (IS_DRAGON_FORM(ch))
			send_to_char("You need to re-orient yourself before you can roar again.\n",
				     ch);
		else
			send_to_char(
				"Your &+Gdr&+Lag&+Gon&n needs to re-orient itself before it can roar again.\n",
				ch);
		return;
	}

	is_hunter = GET_SPEC(ch, CLASS_DRAGOON, SPEC_DRAGON_HUNTER);
	percent_chance = dragon_roar_threshold(ch);
	int power = dragoon_power(ch);

	appear(ch);
	appear(mount);

	if ((percent_chance + power) > number(1, 100)
	    /*&& number(0, 75) < GET_CHAR_SKILL(ch, SKILL_MOUNT)*/)
	{
		if (IS_DRAGON_FORM(ch))
		{
			send_to_char("You unleash a &+rpowerful &-L&+RROAR!!&n\r\n", ch);
			act("$n unleashes a &+rpowerful &-L&+RROAR!!&n", TRUE, ch, 0, 0, TO_ROOM);
		}
		else
		{
			send_to_char(
				"You command your &+Gdr&+Lag&+Gon&n to unleash a &+rpowerful &-L&+RROAR!!&n\r\n",
				ch);
			act("$n commands $N to unleash a &+rpowerful &-L&+RROAR!!&n", TRUE, ch, 0,
			    mount, TO_ROOM);
		}

		int empower = dragon_roar_empower(ch, is_hunter);

		// Will now drain spell circles but higher circles should do better shit IMHO
		int circle = get_next_dragoon_circle(ch);

		if (circle == 0)
		{
			if (IS_DRAGON_FORM(ch))
			{
				act("$N &+RBELCHES&n a large &+WPUFF&n of foul &+LSMOKE&n!", FALSE,
				    ch, 0, mount, TO_ROOM);
				act("You &+RBELCH&n a large &+WPUFF&n of foul &+LSMOKE&n!", FALSE,
				    ch, 0, mount, TO_CHAR);
			}
			else
			{
				act("$N &+RBELCHES&n a large &+WPUFF&n of foul &+LSMOKE&n!", FALSE,
				    ch, 0, mount, TO_ROOM);
				act("$N &+RBELCHES&n a large &+WPUFF&n of foul &+LSMOKE&n!", FALSE,
				    ch, 0, mount, TO_CHAR);
			}
		}
		else
		{
			for (victim = world[ch->in_room].people; victim;
			     victim = victim->next_in_room)
			{
				if (is_in_dragoon_group(ch, victim) || victim == mount)
				{
					if (!affected_by_spell(victim, SKILL_WAR_CRY))
					{
						bzero(&af, sizeof(af));
						af.type = SKILL_WAR_CRY;
						af.duration = dragon_roar_duration(dampoints);
						// HPS
						af.modifier = hpoints;
						af.location = APPLY_HIT;
						affect_to_char(victim, &af);
						// HIT
						af.modifier = dampoints;
						af.location = APPLY_HITROLL;
						affect_to_char(victim, &af);
						// DAM
						af.modifier = dampoints;
						af.location = APPLY_DAMROLL;
						affect_to_char(victim, &af);
						update_pos(victim);
						send_to_char(
							"Your &+rblood&n boils as you heed the &+Gdr&+Lag&+Gon&n &+Lgod&n's call!\r\n",
							victim);
						act("$n hearkens the &+Gdr&+Lag&+Gon&n &+Lgod&n's call!",
						    TRUE, victim, 0, 0, TO_ROOM);
					}
				}
				else
				{
					if (!affected_by_spell(victim, SONG_COWARDICE))
					{
						bzero(&af, sizeof(af));
						af.type = SONG_COWARDICE;
						af.duration = dragon_roar_duration(dampoints);
						af.modifier = dragon_roar_penalty(ch, empower);
						af.location = APPLY_HITROLL;
						affect_to_char(victim, &af);
						af.modifier = dragon_roar_penalty(ch, empower);
						af.location = APPLY_DAMROLL;
						affect_to_char(victim, &af);
						send_to_char(
							"The &+Gdr&+Lag&+Gon&n's &+RROAR&n shakes you to your core!\r\n",
							victim);
						act("$N looks shaken by the &+Gdr&+Lag&+Gon&n's &+RROAR&n!",
						    TRUE, ch, 0, victim, TO_NOTVICT);
					}

					if (!IS_AFFECTED4(victim, AFF4_NOFEAR) &&
					    !IS_ELITE(victim) && !IS_GREATER_RACE(victim))
					{
						if (is_hunter)
						{
							if ((number(0, 100) <
							     dragon_roar_flee_threshold()) &&
							    (number(0, 100) <
							     GET_CHAR_SKILL(ch,
									    SKILL_DRAGON_ROAR)) &&
							    (dragon_roar_flee_level(ch, empower) >=
							     GET_LEVEL(victim)) &&
							    !IS_TRUSTED(victim) &&
							    !fear_check(victim))
							{
								send_to_char(
									"The &+Gdr&+Lag&+Gon&n's &+RROAR&n fills you with &+LDREAD&n!\n",
									victim);
								do_flee(victim, 0, 0);
							}
						}
					}
				}
			}

			ch->specials.undead_spell_slots[circle]--;
			gmcp_spell_preparation_changed(ch);

			snprintf(
				buf, MAX_STRING_LENGTH,
				"The &+Gdr&+Lag&+Gon&n god's &+rpower&n drains from your %d%s circle of knowledge.\n",
				circle,
				circle == 1 ? "st" :
					      (circle == 2 ? "nd" : (circle == 3 ? "rd" : "th")));
			send_to_char(buf, ch);

			DelayCommune(ch, (int)(3 * PULSE_VIOLENCE));

			notch_skill(ch, SKILL_DRAGON_ROAR,
				    get_property("skill.notch.defensive", 7));
		}

		set_short_affected_by(ch, SKILL_DRAGON_ROAR, dragon_roar_rest());
	}
	else
	{
		if (IS_DRAGON_FORM(ch))
		{
			send_to_char("The &+Gdr&+Lag&+Gon&n god's &+rpower&n betrays you.\r\n", ch);
			act("$N's ophidian eyes dull as $s inner-eyelids close for a moment.", TRUE,
			    ch, 0, mount, TO_ROOM);
		}
		else
		{
			send_to_char("Your &+Gdr&+Lag&+Gon&n fails to obey your command.\r\n", ch);
			act("$N disobeys $n's command,", TRUE, ch, 0, mount, TO_ROOM);
		}
	}

	CharWait(ch, dragon_roar_lag());
}

// The chance threshold of a breath, before the dragoon's power.
static int dragon_breath_threshold(P_char ch)
{
	int percent_chance = (95 * GET_CHAR_SKILL(ch, SKILL_MOUNTED_COMBAT)) / 100;
	percent_chance = BOUNDED(1, percent_chance, 99);
	return percent_chance;
}

// How long, in pulses, a breath keeps the dragoon from another dragon command.
static int dragon_breath_rest()
{
	return (int)(3 * PULSE_VIOLENCE);
}

// The dragoon's lag after a breath, in pulses.
static int dragon_breath_lag()
{
	return PULSE_VIOLENCE;
}

std::string dragon_breath_facts(P_char ch)
{
	return fact("Chance",
		    std::to_string(MIN(100, dragon_breath_threshold(ch) + dragoon_power(ch))) +
			    " in 100, by your mounted combat") +
	       fact("Your lag", seconds(dragon_breath_lag())) +
	       fact("Before your next dragon command if it works", seconds(dragon_breath_rest())) +
	       "  The circle it spends picks the spell, cast at your dragon's level:\n"
	       "    1-2 burning hands, 3-4 flameburst, 5-6 molten spray,\n"
	       "    7-8 fireball, 9-10 magma burst, 11-12 immolate.\n"
	       "  With no circle prepared, it does nothing.\n";
}

void do_dragon_breath(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL, mount = NULL;
	int skl_lvl = 0;
	int percent_chance;
	bool is_priest = FALSE;
	char name[MAX_INPUT_LENGTH];
	char buf[MAX_STRING_LENGTH];
	char spellName[MAX_INPUT_LENGTH] = {};

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (!SanityCheck(ch, "dragon_strike"))
		return;

	if ((skl_lvl = GET_CHAR_SKILL(ch, SKILL_DRAGON_ROAR)) == 0)
	{
		send_to_char("You don't know how.\r\n", ch);
		return;
	}

	if (IS_IMMOBILE(ch))
	{
		send_to_char("Hold up! You can't command your &+Gdr&+Lag&+Gon&n right now.\n", ch);
		return;
	}

	if (!has_dragoon_mount(ch))
	{
		send_to_char("You must command a &+Gdr&+Lag&+Gon&n to do that.\n", ch);
		return;
	}

	if (!is_dragoon_mounted(ch))
	{
		send_to_char("You must be riding a &+Gdr&+Lag&+Gon&n to do that.\n", ch);
		return;
	}

	mount = get_dragoon_mount(ch);

	if (mount == NULL)
	{
		send_to_char("You are not mounted on your &+Gdr&+Lag&+Gon&n.\n", ch);
		return;
	}

	if (affected_by_spell(ch, SKILL_DRAGON_ROAR) ||
	    affected_by_spell(ch, SKILL_DRAGON_BREATH) ||
	    affected_by_spell(ch, SKILL_DRAGON_STRIKE))
	{
		if (IS_DRAGON_FORM(ch))
		{
			send_to_char(
				"You need to re-orient yourself before you can breath fire again.\n",
				ch);
		}
		else
		{
			send_to_char(
				"Your &+Gdr&+Lag&+Gon&n needs to re-orient itself before it can breath fire again.\n",
				ch);
		}
		return;
	}

	if (strcmp(argument, "") != 0 && strcmp(argument, " ") != 0)
	{
		argument = one_argument(argument, name);
	}

	if (*name)
	{
		victim = get_char_room_vis(ch, name);
	}

	if (victim && (mount == victim))
	{
		send_to_char("Your &+Gdr&+Lag&+Gon&n cannot breath fire at itself!\r\n", ch);
		return;
	}

	if ((victim == NULL) && IS_FIGHTING(ch))
	{
		victim = GET_OPPONENT(ch);
	}

	if (victim == NULL)
	{
		send_to_char("Breath fire at who or what?\r\n", ch);
		return;
	}

	if (!CanDoFightMove(ch, victim))
	{
		return;
	}

	if (IS_BLIND(ch))
	{
		send_to_char("&+LDang... someone turned out the lights!\n", ch);
		return;
	}

	if (!IS_IMMOBILE(mount) && !IS_BLIND(mount))
	{
		if (IS_DRAGON_FORM(ch))
		{
			send_to_char("You attempt to unleash a torrent of &+RFIRE&N!!!\n", ch);
		}
		else
		{
			switch (number(1, 3))
			{
			case 1:
				send_to_char(
					"You command your &+Gdr&+Lag&+Gon&n to unleash a torrent of &+RFIRE&N!!!\n",
					ch);
				break;
			case 2:
				send_to_char(
					"You command your &+Gdr&+Lag&+Gon&n to rear back and breath &+RFIRE&N!!!\n",
					ch);
				break;
			case 3:
				send_to_char(
					"You order your &+Gdr&+Lag&+Gon&n to breath &+RFIRE&N over your foe!!!\n",
					ch);
				break;
			}
		}
	}
	else
	{
		if (IS_DRAGON_FORM(ch))
		{
			send_to_char("The &+Gdr&+Lag&+Gon&n god's &+rpower&n betrays you.\r\n", ch);
		}
		else
		{
			send_to_char(
				"Your &+Gdra&+Lag&+Gon&n is afflicted and cannot hearken you.\n\r",
				ch);
		}
		return;
	}

	appear(ch);
	appear(mount);

	victim = guard_check(ch, victim);

	is_priest = GET_SPEC(ch, CLASS_DRAGOON, SPEC_DRAGON_PRIEST);

	percent_chance = dragon_breath_threshold(ch);
	int power = dragoon_power(ch);

	if ((!notch_skill(ch, SKILL_MOUNTED_COMBAT, get_property("skill.notch.offensive", 7)) &&
	     (percent_chance + power) <
		     number(1, 100)) /*|| number(0, 65) > GET_CHAR_SKILL(ch, SKILL_MOUNT)*/)
	{
		if (IS_DRAGON_FORM(ch))
		{
			send_to_char("The &+Gdr&+Lag&+Gon&n god's &+rpower&n betrays you.\r\n", ch);
			act("$N's ophidian eyes dull as $s inner-eyelids close for a moment.", TRUE,
			    ch, 0, mount, TO_ROOM);
		}
		else
		{
			act("$N thrashes wildy without heeding $n's order.", FALSE, ch, 0, mount,
			    TO_ROOM);
			act("$N thrashes wildy without heeding your order.", FALSE, ch, 0, mount,
			    TO_CHAR);
		}
	}
	else
	{
		int circle = get_next_dragoon_circle(ch);

		if (circle == 0)
		{
			if (IS_DRAGON_FORM(ch))
			{
				act("$N &+RBELCHES&n a large &+WPUFF&n of foul &+LSMOKE&n!", FALSE,
				    ch, 0, mount, TO_ROOM);
				act("You &+RBELCH&n a large &+WPUFF&n of foul &+LSMOKE&n!", FALSE,
				    ch, 0, mount, TO_CHAR);
			}
			else
			{
				act("$N &+RBELCHES&n a large &+WPUFF&n of foul &+LSMOKE&n!", FALSE,
				    ch, 0, mount, TO_ROOM);
				act("$N &+RBELCHES&n a large &+WPUFF&n of foul &+LSMOKE&n!", FALSE,
				    ch, 0, mount, TO_CHAR);
			}
		}
		else
		{
			if (GET_SPEC(ch, CLASS_DRAGOON, SPEC_DRAGON_PRIEST))
			{
				if (strcmp(argument, "") != 0 && strcmp(argument, " ") != 0)
				{
					argument = one_argument(argument, spellName);

					if (*spellName)
					{
						int chosenCircle = circle;

						if (is_abbrev(spellName, "burning hands"))
						{
							if (ch->specials.undead_spell_slots[2])
								chosenCircle = 2;
							else if (ch->specials.undead_spell_slots[1])
								chosenCircle = 1;
							else
								send_to_char(
									"You must commune with the &+Gdr&+Lag&+Gon&n god for more &+rpower&n\n",
									ch);
						}
						else if (is_abbrev(spellName, "flameburst"))
						{
							if (ch->specials.undead_spell_slots[4])
								chosenCircle = 4;
							else if (ch->specials.undead_spell_slots[3])
								chosenCircle = 3;
							else
								send_to_char(
									"You must commune with the &+Gdr&+Lag&+Gon&n god for more &+rpower&n\n",
									ch);
						}
						else if (is_abbrev(spellName, "molten spray"))
						{
							if (ch->specials.undead_spell_slots[6])
								chosenCircle = 6;
							else if (ch->specials.undead_spell_slots[5])
								chosenCircle = 5;
							else
								send_to_char(
									"You must commune with the &+Gdr&+Lag&+Gon&n god for more &+rpower&n\n",
									ch);
						}
						else if (is_abbrev(spellName, "fireball"))
						{
							if (ch->specials.undead_spell_slots[8])
								chosenCircle = 8;
							else if (ch->specials.undead_spell_slots[7])
								chosenCircle = 7;
							else
								send_to_char(
									"You must commune with the &+Gdr&+Lag&+Gon&n god for more &+rpower&n\n",
									ch);
						}
						else if (is_abbrev(spellName, "magma burst"))
						{
							if (ch->specials.undead_spell_slots[10])
								chosenCircle = 10;
							else if (ch->specials.undead_spell_slots[9])
								chosenCircle = 9;
							else
								send_to_char(
									"You must commune with the &+Gdr&+Lag&+Gon&n god for more &+rpower&n\n",
									ch);
						}
						else if (is_abbrev(spellName, "immolate"))
						{
							if (ch->specials.undead_spell_slots[12])
								chosenCircle = 12;
							else if (ch->specials.undead_spell_slots[11])
								chosenCircle = 11;
							else
								send_to_char(
									"You must commune with the &+Gdr&+Lag&+Gon&n god for more &+rpower&n\n",
									ch);
						}
						else
						{
							send_to_char(
								"The &+Gdr&+Lag&+Gon&n god's &+rpowers&n are:\n"
								"   (Circle  1 -  2) burning hands\n"
								"   (Circle  3 -  4) flameburst\n"
								"   (Circle  5 -  6) molten spray\n"
								"   (Circle  7 -  8) fireball\n"
								"   (Circle  9 - 10) magma burst\n"
								"   (Circle 11 - 12) immolate\n",
								ch);
							return;
						}

						int select_chance =
							(95 *
							 GET_CHAR_SKILL(ch, SKILL_DRAGON_BREATH)) /
							100;
						select_chance = BOUNDED(1, percent_chance, 99);

						if (((select_chance + power) > number(1, 100)))
						{
							circle = chosenCircle;
						}
					}
				}
			}

			// send_to_char("$n rears back and blasts $N with a torrent of &+RFLAMES&n\r\n", ch);
			act("$n rears back and blasts $N with a torrent of &+RFLAMES&n!", FALSE,
			    mount, 0, victim, TO_NOTVICTROOM);
			act("$n rears back and blasts YOU with a torrent of &+RFLAMES&n!", FALSE,
			    mount, 0, victim, TO_VICT);

			// force engagement on dragon or on dragon rider?
			engage(mount, victim);
			// engage(ch, victim);

			switch (circle)
			{
			case 1:
			case 2:
				spell_burning_hands(GET_LEVEL(mount), mount, writable_arg(""),
						    1 + is_priest, victim, 0);
				break;
			case 3:
			case 4:
				spell_flameburst(GET_LEVEL(mount), mount, writable_arg(""),
						 1 + is_priest, victim, 0);
				break;
			case 5:
			case 6:
				spell_molten_spray(GET_LEVEL(mount), mount, writable_arg(""),
						   1 + is_priest, victim, 0);
				break;
			case 7:
			case 8:
				spell_fireball(GET_LEVEL(mount), mount, writable_arg(""),
					       1 + is_priest, victim, 0);
				break;
			case 9:
			case 10:
				spell_magma_burst(GET_LEVEL(mount), mount, writable_arg(""),
						  1 + is_priest, victim, 0);
				break;
			case 11:
			case 12:
				spell_immolate(GET_LEVEL(mount), mount, writable_arg(""),
					       1 + is_priest, victim, 0);
				break;
			}

			ch->specials.undead_spell_slots[circle]--;
			gmcp_spell_preparation_changed(ch);

			snprintf(
				buf, MAX_STRING_LENGTH,
				"The &+Gdr&+Lag&+Gon&n god's &+rpower&n drains from your %d%s circle of knowledge.\n",
				circle,
				circle == 1 ? "st" :
					      (circle == 2 ? "nd" : (circle == 3 ? "rd" : "th")));
			send_to_char(buf, ch);

			notch_skill(ch, SKILL_DRAGON_BREATH,
				    get_property("skill.notch.offensive", 7));
			DelayCommune(ch, (int)(3 * PULSE_VIOLENCE));
		}

		set_short_affected_by(ch, SKILL_DRAGON_BREATH, dragon_breath_rest());
	}

	CharWait(ch, dragon_breath_lag());
}

// Damage from a tail strike, before a lancer's bonus and the target's defenses.
static int dragon_strike_damage(const Rolls &rolls, P_char ch)
{
	return 30 + rolls.number(1, GET_LEVEL(ch));
}

// A dragon lancer's tail strike damage.
static int dragon_strike_lancer_damage(int dam)
{
	return (int)(dam * get_property("skill.dragon_strike.lancer.DamageMultiplier", 2.000));
}

// The dragoon's lag after a strike, in pulses.
static int dragon_strike_lag()
{
	return PULSE_VIOLENCE;
}

// The dragoon's lag, in pulses, after a miss that throws them hard to the ground.
static int dragon_strike_face_plant_lag()
{
	return PULSE_VIOLENCE * 3;
}

// Damage from falling off the dragon on a miss.
static int dragon_strike_fall_damage(const Rolls &rolls, P_char ch)
{
	return rolls.number(1, GET_LEVEL(ch));
}

// How long, in pulses, a hit keeps the dragoon from another dragon command.
static int dragon_strike_rest()
{
	return (int)(3 * PULSE_VIOLENCE);
}

// A knocked down target's lag in pulses: vict_lag is 2, or 1 for a size mismatch.
static int dragon_strike_target_lag(int vict_lag)
{
	return vict_lag * PULSE_VIOLENCE;
}

std::string dragon_strike_facts(P_char ch)
{
	const bool is_lancer = GET_SPEC(ch, CLASS_DRAGOON, SPEC_DRAGON_LANCER);
	int low = dragon_strike_damage(lowest_rolls, ch);
	int high = dragon_strike_damage(highest_rolls, ch);
	if (is_lancer)
	{
		low = dragon_strike_lancer_damage(low);
		high = dragon_strike_lancer_damage(high);
	}
	std::string facts =
		fact("Damage on a hit", show({ low, high }) + " at your level") +
		fact("Your lag", seconds(dragon_strike_lag())) +
		fact("Before your next dragon command after a hit", seconds(dragon_strike_rest())) +
		fact("Target's lag if knocked down", seconds(dragon_strike_target_lag(2))) +
		fact("  If the sizes differ too much", seconds(dragon_strike_target_lag(1)));
	if (!is_lancer)
		facts += fact("Falling damage on a bad miss",
			      show({ dragon_strike_fall_damage(lowest_rolls, ch),
				     dragon_strike_fall_damage(highest_rolls, ch) })) +
			 fact("Your lag if you crash to the ground",
			      seconds(dragon_strike_face_plant_lag()));
	return facts + "  The target's defenses apply to the damage after.\n";
}

void do_dragon_strike(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL, mount = NULL;
	int knockdown_chance;
	int percent_chance;
	int dam, vict_lag;
	int skl_lvl = 0;
	int ch_size, vict_size;
	bool is_lancer;
	char name[MAX_INPUT_LENGTH];
	struct damage_messages messages = {
		"Your &+Gdr&+Lag&+Gon&N hearkens your call and sweeps $s tail into $N with a magnificent &-L&+RSWOOSH&n!",
		"$n's tail sweeps into you with a magnificent &-L&+RSWOOSH&n!",
		"$n's tail sweeps into $N's body with a magnificent &-L&+RSWOOSH&n!",
		"Your &+Gdr&+Lag&+Gon&N heeds your command and viciously sweeps $s tail into $N, turning $S into a pink mist!",
		"$n's tail sweeps into you, &-L&+RSKADOOSH&n!!! Your body is obliterated by the force!",
		"$n sweeps $s tail and viciously obliterates $N's body with a loud &-L&+RSKADOOSH&n!",
		0,
		0
	};

	struct damage_messages messages_dragon_form = {
		"You sweep your tail into $N with a magnificent &-L&+RSWOOSH&n!",
		"$n's tail sweeps into you with a magnificent &-L&+RSWOOSH&n!",
		"$n's tail sweeps into $N's body with a magnificent &-L&+RSWOOSH&n!",
		"You viciously sweep your tail into $N, turning $S into a pink mist!",
		"$n's tail sweeps into you, &-L&+RSKADOOSH&n!!! Your body is obliterated by the force!",
		"$n sweeps $s tail and viciously obliterates $N's body with a loud &-L&+RSKADOOSH&n!",
		0,
		0
	};

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (!SanityCheck(ch, "dragon_strike"))
		return;

	if ((skl_lvl = GET_CHAR_SKILL(ch, SKILL_DRAGON_ROAR)) == 0)
	{
		send_to_char("You don't know how.\r\n", ch);
		return;
	}

	if (IS_IMMOBILE(ch))
	{
		if (IS_DRAGON_FORM(ch))
			send_to_char("Hold up! You can't move right now.\n", ch);
		else
			send_to_char(
				"Hold up! You can't command your &+Gdr&+Lag&+Gon&n right now.\n",
				ch);
		return;
	}

	if (!has_dragoon_mount(ch))
	{
		send_to_char("You must command a &+Gdr&+Lag&+Gon&n to do that.\n", ch);
		return;
	}

	if (!is_dragoon_mounted(ch))
	{
		send_to_char("You must be riding a &+Gdr&+Lag&+Gon&n to do that.\n", ch);
		return;
	}

	mount = get_dragoon_mount(ch);

	if (mount == NULL)
	{
		send_to_char("You are not mounted on your &+Gdr&+Lag&+Gon&n.\n", ch);
		return;
	}

	if (affected_by_spell(ch, SKILL_DRAGON_ROAR) ||
	    affected_by_spell(ch, SKILL_DRAGON_BREATH) ||
	    affected_by_spell(ch, SKILL_DRAGON_STRIKE))
	{
		if (IS_DRAGON_FORM(ch))
			send_to_char(
				"You need to re-orient yourself before you can tail strike again.\n",
				ch);
		else
			send_to_char(
				"Your &+Gdr&+Lag&+Gon&n needs to re-orient itself before it can tail strike again.\n",
				ch);
		return;
	}

	one_argument(argument, name);
	if (*name)
	{
		victim = get_char_room_vis(ch, name);
	}

	if (victim && (mount == victim))
	{
		if (IS_DRAGON_FORM(ch))
			send_to_char("You cannot tail strike yourself!\r\n", ch);
		else
			send_to_char("Your &+Gdr&+Lag&+Gon&n cannot tail strike itself!\r\n", ch);
		return;
	}

	if ((victim == NULL) && IS_FIGHTING(ch))
	{
		victim = GET_OPPONENT(ch);
	}

	if (victim == NULL)
	{
		send_to_char("Tail strike who or what?\r\n", ch);
		return;
	}

	if (!CanDoFightMove(ch, victim))
	{
		return;
	}

	if (IS_BLIND(ch))
	{
		send_to_char("&+LDang... someone turned out the lights!\n", ch);
		return;
	}

	if (IS_IMMOBILE(mount) || IS_BLIND(mount))
	{
		if (IS_DRAGON_FORM(ch))
			send_to_char("The &+Gdr&+Lag&+Gon&n god's &+rpower&n betrays you.\n\r", ch);
		else
			send_to_char(
				"Your &+Gdra&+Lag&+Gon&n is afflicted and cannot hearken you.\n\r",
				ch);
		return;
	}
	else
	{
		// switch ( number(1, 3) )
		// {
		//   case 1:
		//     send_to_char("You command your &+Gdr&+Lag&+Gon&n to &+RSTRIKE&n!!!\n", ch);
		//   break;
		//   case 2:
		//     send_to_char("Your &+Gdr&+Lag&+Gon&n &+RSTRIKES&n with it's massive tail!!!\n", ch);
		//   break;
		//   case 3:
		//     send_to_char("Your &+Gdr&+Lag&+Gon&n crashes it's tail through the area!!!\n", ch);
		//   break;
		// }
	}

	appear(ch);
	appear(mount);

	victim = guard_check(ch, victim);

	is_lancer = GET_SPEC(ch, CLASS_DRAGOON, SPEC_DRAGON_LANCER);

	percent_chance = (95 * GET_CHAR_SKILL(ch, SKILL_MOUNTED_COMBAT)) / 100;

	knockdown_chance =
		(int)(percent_chance * get_property("skill.dragon_strike.knockdown", 0.700));

	vict_lag = 2;

	knockdown_chance =
		(int)(knockdown_chance *
		      ((double)BOUNDED(8, 10 + (GET_LEVEL(ch) - GET_LEVEL(victim)) / 10, 11)) / 10);
	knockdown_chance =
		(int)(knockdown_chance * ((double)BOUNDED(83, 50 + GET_C_AGI(ch) / 2, 120)) / 100);

	if (IS_AFFECTED(victim, AFF_AWARE))
	{
		knockdown_chance = (int)(knockdown_chance * 0.90);
	}

	vict_size = get_takedown_size(victim);
	ch_size = get_takedown_size(ch);

	dam = dragon_strike_damage(live_rolls, ch);

	if (is_lancer)
	{
		dam = dragon_strike_lancer_damage(dam);
	}

	if (IS_NPC(victim) && (IS_SET(victim->specials.act, ACT_NO_BASH) || IS_ELITE(victim)))
	{
		knockdown_chance = 0;
	}

	// If ch is over 1 size smaller than vict.
	if (ch_size < vict_size - 1)
	{
		knockdown_chance = 0;
		vict_lag = 1;
	}
	// If ch is one size smaller than vict.
	else if (ch_size == vict_size - 1)
	{
		if (IS_DRIDER(victim) || IS_CENTAUR(victim))
			knockdown_chance = 0;
		else if (!is_lancer)
			knockdown_chance = (int)(knockdown_chance * 0.5);
	}
	else if ((ch_size <= vict_size) && (IS_DRIDER(victim) || IS_CENTAUR(victim)))
	{
		knockdown_chance = 0;
	}
	// If ch is over 1 size larger than vict.
	if ((ch_size > vict_size + 1) && !(is_lancer && (vict_size == ch_size - 2)))
	{
		percent_chance = (int)(percent_chance * 0.9);
		knockdown_chance = (int)(knockdown_chance * 0.20);
		vict_lag = 1;
	}

	if (GET_POS(victim) != POS_STANDING)
	{
		knockdown_chance = 0;
	}

	CharWait(ch, dragon_strike_lag());

	knockdown_chance = takedown_check(ch, victim, knockdown_chance, SKILL_DRAGON_STRIKE,
					  TAKEDOWN_ALL & !TAKEDOWN_AGI_CHECK);

	if (knockdown_chance == TAKEDOWN_CANCELLED)
	{
		if (IS_DRAGON_FORM(ch))
			send_to_char(
				"Your tail swings wildy through the area missing your target!\r\n",
				ch);
		else
			send_to_char(
				"Your &+Gdr&+Lag&+Gon&n's tail swings wildy through the area missing it's target!\r\n",
				ch);
		return;
	}
	else if (knockdown_chance == TAKEDOWN_PENALTY)
	{
		knockdown_chance = 0;
	}

	percent_chance = BOUNDED(1, percent_chance, 99);
	int power = dragoon_power(ch);

	if (IS_NPC(ch) && (number(0, 50) > percent_chance))
	{
		return;
	}

	knockdown_chance = BOUNDED(0, knockdown_chance, 80);

	if (IS_DRAGON_FORM(ch))
		act("You attempt to tail strike $N.", FALSE, ch, 0, victim, TO_CHAR);
	else
		act("You order your &+Gdr&+Lag&+Gon&n to tail strike $N.", FALSE, ch, 0, victim,
		    TO_CHAR);

	if (!notch_skill(ch, SKILL_MOUNTED_COMBAT, get_property("skill.notch.offensive", 7)) &&
	    (percent_chance + power) < number(1, 100))
	{
		if (50 + GET_C_DEX(ch) / 2 > number(0, 100) || is_lancer)
		{
			if (IS_DRAGOON(ch))
			{
				send_to_char(
					"The &+Gdr&+Lag&+Gon&n god's &+rpower&n betrays you.\r\n",
					ch);
				act("$N's ophidian eyes dull as $s inner-eyelids close for a moment.",
				    TRUE, ch, 0, mount, TO_ROOM);
			}
			else
			{
				act("$N thrashes wildy without heeding $n's order.", FALSE, ch, 0,
				    mount, TO_ROOM);
				act("$N thrashes wildy without heeding your order.", FALSE, ch, 0,
				    mount, TO_CHAR);
			}
			SET_POS(ch, POS_STANDING + STAT_NORMAL);
		}
		else
		{
			if (IS_DRAGON_FORM(ch))
			{
				send_to_char(
					"You thrash wildly as the &+Gdr&+Lag&+Gon&n god's &+rpower&n betrays you.\r\n",
					ch);
				act("$N thrashes wildy $n as they miss thier target!", FALSE, ch, 0,
				    mount, TO_ROOM);
			}
			else
			{
				act("As $N thrashes wildy as you are thrown to the ground!", FALSE,
				    ch, 0, mount, TO_CHAR);
				act("As $N thrashes wildy as $n is thrown to the ground!", FALSE,
				    ch, 0, mount, TO_ROOM);
			}

			if (50 + GET_C_AGI(ch) / 2 < number(0, 100))
			{
				SET_POS(ch, POS_SITTING + GET_STAT(ch));
				act("You face plant hard into the ground!", FALSE, ch, 0, mount,
				    TO_CHAR);
				act("CRASH! $n face plants hard into the ground!", FALSE, ch, 0,
				    victim, TO_ROOM);
				CharWait(ch, dragon_strike_face_plant_lag());
			}
			if (damage(ch, ch, dragon_strike_fall_damage(live_rolls, ch),
				   DAMAGE_FALLING))
				return;

			if (!IS_DRAGON_FORM(ch))
				unlink_char(ch, mount, LNK_RIDING);
		}
	}
	else
	{
		notch_skill(ch, SKILL_DRAGON_STRIKE, get_property("skill.notch.offensive", 7));

		engage(mount, victim);

		if (IS_DRAGON_FORM(ch))
		{
			if (melee_damage(mount, victim, dam, PHSDAM_NOENGAGE | PHSDAM_TOUCH,
					 &messages_dragon_form))
				return;
		}
		else if (melee_damage(mount, victim, dam, PHSDAM_NOENGAGE | PHSDAM_TOUCH,
				      &messages))
		{
			return;
		}

		if (IS_PC(ch) && GET_POS(victim) == POS_STANDING)
		{
			debug("DRAGON_STRIKE: (%s) trying to dragon strike with (%d) percent knock down. Victim is (%s).",
			      GET_NAME(ch), knockdown_chance, GET_NAME(victim));
		}

		set_short_affected_by(ch, SKILL_DRAGON_STRIKE, dragon_strike_rest());

		if (knockdown_chance > number(1, 100))
		{
			act("$n is knocked to the ground!", FALSE, victim, 0, 0, TO_ROOM);
			send_to_char("You are knocked to the ground!\n", victim);
			SET_POS(victim, POS_SITTING + GET_STAT(victim));
			update_group_vitals(victim);
			gmcp_char_vitals(victim);
			CharWait(victim, dragon_strike_target_lag(vict_lag));
		}
	}
}

void do_kick(P_char ch, char *argument, int cmd)
{
	P_char victim;

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (IS_IMMOBILE(ch))
	{
		send_to_char("Hold up! You can't kick right now.\n", ch);
		return;
	}

	if (has_innate(ch, INNATE_HORSE_BODY))
	{
		do_rearkick(ch, argument, cmd);
		return;
	}

	victim = ParseTarget(ch, argument);

	if (!victim)
	{
		send_to_char("Kick who?\n", ch);
		return;
	}

	if (GET_RACE(ch) == RACE_PLANT)
	{
		branch(ch, victim);
	}
	else if ((GET_RACE(ch) == RACE_SNAKE) || (GET_RACE(ch) == RACE_INSECT) ||
		 (GET_RACE(ch) == RACE_PARASITE))
	{
		do_bite_target(ch, victim);
	}
	else
	{
		if (!kick_admitted(ch, victim))
			return;
		victim = guard_check(ch, victim);
		kick(ch, victim);
	}
}

static int roundkick_admission(P_char ch, P_char victim)
{
	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return 0;
	}

	if (affected_by_spell(ch, SKILL_BASH))
	{
		send_to_char("You haven't reoriented yourself yet enough for another kick!\n", ch);
		return 0;
	}

	if ((GET_CHAR_SKILL(ch, SKILL_ROUNDKICK) < 1) && !IS_TRUSTED(ch))
	{
		send_to_char("You don't know how to roundkick.\n", ch);
		return 0;
	}

	if (IS_NPC(ch) &&
	    LEGLESS(ch)) // Legless define includes immaterial. This hack allows the phantom
		// monk to use roundkick.
	{
		send_to_char("You don't possess the necessary body parts to roundkick.\n", ch);
		return 0;
	}

	if (!CanDoFightMove(ch, victim))
		return TAKEDOWN_CANCELLED;

	if (!on_front_line(ch) || !on_front_line(victim))
	{
		send_to_char("You can't reach them!\n", ch);
		return 0;
	}

	if ((get_takedown_size(victim) > get_takedown_size(ch)) ||
	    (get_takedown_size(victim) < get_takedown_size(ch) - 1))
	{
		send_to_char("You can't figure out how to kick them!\n", ch);
		return 0;
	}

	return 1;
}

// The kicker's lag, in pulses, against an immaterial target.
static int roundkick_immaterial_lag()
{
	return (int)(PULSE_VIOLENCE * 0.250);
}

// The kicker's lag, in pulses, on an ordinary attempt.
static int roundkick_lag()
{
	return (int)(PULSE_VIOLENCE * 2.500);
}

// A roundkick's damage before the target's agility comes off.
static int roundkick_damage(P_char ch)
{
	return GET_C_DEX(ch) + GET_CHAR_SKILL(ch, SKILL_ROUNDKICK);
}

// The target's lag after a hit, in pulses.
static int roundkick_target_lag()
{
	return PULSE_VIOLENCE;
}

// How long, in pulses, a hit keeps the kicker from another roundkick.
static int roundkick_rest()
{
	return 2 * PULSE_VIOLENCE;
}

std::string roundkick_facts(P_char ch)
{
	return fact("Damage on a hit", std::to_string(roundkick_damage(ch)) +
					       " less the target's agility, at least 1") +
	       fact("Damage on a miss", "half of that, and you drop to your knees") +
	       fact("Your lag", seconds(roundkick_lag())) +
	       fact("Your lag if the target is immaterial", seconds(roundkick_immaterial_lag())) +
	       fact("Your lag if the target is asleep",
		    seconds(takedown_sleeping_target_lag()) + " (you attack it instead)") +
	       fact("Your lag if the target evades", seconds(takedown_evade_lag())) +
	       fact("Before you can roundkick again after a hit", seconds(roundkick_rest())) +
	       fact("Target's lag on a hit", seconds(roundkick_target_lag())) +
	       "  The target must be your size or one smaller, and on the front line.\n"
	       "  The target's defenses apply to the damage after.\n";
}

int chance_roundkick(P_char ch, P_char victim)
{
	const int admission = roundkick_admission(ch, victim);
	if (admission != 1)
		return admission;

	if (IS_IMMATERIAL(victim))
	{
		act("Your sweeping kick passes through $N. A fine breeze, but a poor impact!",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$n's sweeping kick passes harmlessly through you. Being mist has its moments!",
		    FALSE, ch, 0, victim, TO_VICT);
		act("$n's sweeping kick passes through $N, rearranging absolutely nothing.", FALSE,
		    ch, 0, victim, TO_NOTVICT);
		CharWait(ch, roundkick_immaterial_lag());
		return TAKEDOWN_CANCELLED;
	}

	int percent_chance;

	if (IS_TRUSTED(ch))
	{
		percent_chance = 200;
	}
	else
	{
		percent_chance = GET_CHAR_SKILL(ch, SKILL_ROUNDKICK);
	}

	percent_chance =
		(int)(percent_chance *
		      ((double)BOUNDED(6, 10 + (GET_LEVEL(ch) - GET_LEVEL(victim)) / 10, 15)) / 10);

	/* agility is the prime stat of the monk */
	percent_chance =
		(int)(percent_chance *
		      ((double)BOUNDED(20, 100 + (int)(1.5 * (GET_C_AGI(ch) - GET_C_AGI(victim))),
				       150)) /
		      100);

	if (GET_C_LUK(ch) / 10 > number(0, 10))
	{
		percent_chance = (int)(percent_chance * 1.05);
	}

	if (GET_C_LUK(victim) / 10 > number(0, 100))
	{
		percent_chance = (int)(percent_chance * 0.95);
	}

	if (IS_AFFECTED(victim, AFF_AWARE) && IS_AWAKE(victim))
	{
		percent_chance = (int)(percent_chance * 0.95);
	}

	percent_chance = takedown_check(ch, victim, percent_chance, SKILL_ROUNDKICK, TAKEDOWN_ALL);

	return (int)percent_chance;
}

bool roundkick(P_char ch, P_char victim)
{
	int percent_chance, dam;
	struct damage_messages messages = {
		"Your roundhouse kick hits $N in the solar plexus!",
		"You're hit in solar plexus, wow, this is breathtaking!!",
		"$n roundhouse kicks $N in solar plexus, $N is rendered breathless!",
		"Your roundhouse kick at $N's face splits $S head open -- yummy!",
		"$n aims a roundhouse kick at your face which splits your head in two!",
		"$n neatly kicks $N's head into pieces -- YUMMY!",
		0
	};

	if (roundkick_admission(ch, victim) != 1)
		return false;

	victim = guard_check(ch, victim);
	percent_chance = chance_roundkick(ch, victim);

	if (percent_chance == TAKEDOWN_CANCELLED)
	{
		return FALSE;
	}

	CharWait(ch, roundkick_lag());

	if (percent_chance == TAKEDOWN_PENALTY)
	{
		return FALSE;
	}

	if (percent_chance <= 0)
	{
		return FALSE;
	}

	dam = roundkick_damage(ch) - GET_C_AGI(victim);

	if (!notch_skill(ch, SKILL_ROUNDKICK, get_property("skill.notch.offensive", 7)) &&
	    percent_chance < number(0, 100))
	{
		if (melee_damage(ch, victim, (int)(dam / 2), PHSDAM_TOUCH, 0) != DAM_NONEDEAD)
			return FALSE;

		act("You lose your footing and fall to your knees!", FALSE, ch, 0, victim, TO_CHAR);
		act("$n falls to $s knees after $s bad kick!", FALSE, ch, 0, victim, TO_VICT);
		act("$n falls to $s knees after $s bad kick!", FALSE, ch, 0, victim, TO_NOTVICT);
		SET_POS(ch, POS_KNEELING + GET_STAT(ch));
	}
	else if (melee_damage(ch, victim, MAX(1, dam), PHSDAM_TOUCH, &messages) == DAM_NONEDEAD)
	{
		CharWait(victim, roundkick_target_lag());
		set_short_affected_by(ch, SKILL_BASH, roundkick_rest());

		if (GET_C_DEX(ch) - GET_C_AGI(victim) > number(0, 100))
		{
			act("You do a &+cmagnificent maneuver&n, delivering a full &+yroundhouse kick&n to $N's chest!",
			    FALSE, ch, 0, victim, TO_CHAR);
			act("$n's &+ymighty roundhouse kick&n causes you to &+wfall to your knees!&n",
			    FALSE, ch, 0, victim, TO_VICT);
			act("$n swings about and delivers a &+ymighty roundhouse kick&n to $N!",
			    FALSE, ch, 0, victim, TO_NOTVICT);
			CharWait(victim, (int)(PULSE_VIOLENCE * 0.5));
			SET_POS(victim, POS_KNEELING + GET_STAT(victim));
		}
		else
		{
			act("Your kick knocks the wind out of $N!", FALSE, ch, 0, victim, TO_CHAR);
			act("$n's kick momentarily knocks the wind out of you!", FALSE, ch, 0,
			    victim, TO_VICT);
			act("$N has the wind knocked out of $M by $n's mighty kick!", FALSE, ch, 0,
			    victim, TO_NOTVICT);
		}
	}
#ifdef REALTIME_COMBAT
	if (GET_OPPONENT(ch) && !ch->specials.combat)
	{
		stop_fighting(ch);
		set_fighting(ch, victim);
	}
#endif

	return FALSE;
}

void do_roundkick(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL;

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	victim = ParseTarget(ch, argument);

	if (!victim)
	{
		send_to_char("Kick who?\n", ch);
		return;
	}
	roundkick(ch, victim);
}

void do_assist_core(P_char ch, P_char victim)
{
	if (GET_OPPONENT(ch))
	{
		send_to_char("You are too busy with your own problem to assist.\n", ch);
		return;
	}
	/*
	 * Muhahahahahaha!
	 */
	if (IS_ROOM(ch->in_room, ROOM_SINGLE_FILE))
	{
		if (AdjacentInRoom(ch, victim))
			act("$N is in your way!  You can't get past to assist $M!", FALSE, ch, 0,
			    victim, TO_CHAR);
		else
			act("You can't get to $N to assist $M!", FALSE, ch, 0, victim, TO_CHAR);
		return;
	}
	if (!GET_OPPONENT(victim))
	{
		send_to_char("That person is not fighting anyone.\n", ch);
		return;
	}
	if (!CAN_SEE(ch, GET_OPPONENT(victim)))
	{
		act("You can't see who is fighting $N.", FALSE, ch, 0, victim, TO_CHAR);
		return;
	}
	if (GET_STAT(GET_OPPONENT(victim)) == STAT_DEAD)
	{
		act("Too late, doesn't look like $N really needs any help.", FALSE, ch, 0, victim,
		    TO_CHAR);
		statuslog(56, "SHABOOM!  %s assisting %s against deader.", GET_NAME(ch),
			  GET_NAME(victim));
		return;
	}
	if (victim == ch)
	{
		send_to_char("You tried to assist yourself.  Nice try dork!\n", ch);
		return;
	}
	if (is_in_safe(ch))
	{
		return;
	}
	/*
	 * can't assist and attack someone who isn't within your level
	 */
	if (should_not_kill(ch, GET_OPPONENT(victim)) == TRUE)
	{
		return;
	}

	act("You assist $N heroically.", FALSE, ch, 0, victim, TO_CHAR);
	act("$n assists you heroically.", FALSE, ch, 0, victim, TO_VICT);
	act("$n assists $N heroically.", FALSE, ch, 0, victim, TO_NOTVICT);

	if (IS_NPC(ch))
		MobStartFight(ch, GET_OPPONENT(victim));
	else
		hit(ch, GET_OPPONENT(victim), ch->equipment[PRIMARY_WEAPON]);

	if (char_in_list(ch))
		CharWait(ch, (int)(PULSE_VIOLENCE * 0.5));
}

/*
 * Assist a person - fight the char that the person is attacking - SamIam
 */
void do_assist(P_char ch, char *argument, int /*cmd*/)
{
	char name[MAX_INPUT_LENGTH];
	P_char victim;

	one_argument(argument, name);

	if (!(victim = get_char_room_vis(ch, name)))
	{
		send_to_char("Assist whom?\n", ch);
		return;
	}

	do_assist_core(ch, victim);
}

void knock_out(P_char ch, int duration)
{
	struct affected_type af;

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (ch)
	{
		act("&+RCRASSSHHHH!&n  Your head is pulsating, the world around you "
		    "suddenly becomes &+Lblack.&n",
		    FALSE, ch, 0, 0, TO_CHAR);
		act("$n stumbles side to side with &+cs&+wt&+ca&+wr&+cr&+wy&n eyes and a lost "
		    "expression... finally collapsing.",
		    FALSE, ch, 0, 0, TO_ROOM);

		stop_fighting(ch);
		StopMercifulAttackers(ch);

		memset(&af, 0, sizeof(af));
		af.type = SKILL_HEADBUTT;
		af.bitvector = AFF_KNOCKED_OUT;
		af.flags = AFFTYPE_SHORT | AFFTYPE_NODISPEL | AFFTYPE_NOSHOW;
		af.duration = duration;

		affect_to_char_with_messages(ch, &af,
					     "&+GThe &+Cworld&n seems to come back into focus.",
					     "$n seems to have come back to his senses.");

		SET_POS(ch, POS_PRONE + GET_STAT(ch));
	}
}

/*
 * Headbutt skill.
 *
 * *   --TAM 7-1-94
 */

// The headbutter's lag, in pulses, by what happened.
static int headbutt_position_lag()
{
	return (int)(1 * WAIT_SEC);
}

static int headbutt_immaterial_lag()
{
	return (int)(PULSE_VIOLENCE * 1.0);
}

static int headbutt_refused_lag()
{
	return (int)(PULSE_VIOLENCE * 0.25);
}

static int headbutt_backfire_lag()
{
	return PULSE_VIOLENCE * 2;
}

static double headbutt_miss_lag()
{
	return PULSE_VIOLENCE * 1.5;
}

static int headbutt_hit_lag()
{
	return (int)(PULSE_VIOLENCE * 1.5);
}

// How long, in pulses, each outcome keeps the headbutter from another headbutt.
static int headbutt_backfire_rest()
{
	return (int)(PULSE_VIOLENCE * 3);
}

static int headbutt_miss_rest()
{
	return (int)(PULSE_VIOLENCE * 2);
}

static int headbutt_hit_rest()
{
	return (int)(PULSE_VIOLENCE * 2.5);
}

// Damage to the headbutter when it goes badly wrong, and when it merely fails.
static int headbutt_backfire_damage(const Rolls &rolls)
{
	return rolls.number(5, 15);
}

static int headbutt_miss_damage(const Rolls &rolls)
{
	return rolls.number(1, 8);
}

// How long, in pulses, a knock out lasts.
static int headbutt_knockout(const Rolls &rolls)
{
	return PULSE_VIOLENCE * rolls.number(2, 3);
}

// The roll in a hit's base damage.
static int headbutt_hit_roll(const Rolls &rolls)
{
	return rolls.number(20, 30);
}

// A hit's damage before the target's size, from the rating, strength, level and race.
static float headbutt_hit_damage(P_char ch, int roll)
{
	// Have the base run from 20 to 80 (20 = 1 skill, lowest possible, 80 = 100 skill highest possible).
	float dam = (float)GET_CHAR_SKILL(ch, SKILL_HEADBUTT) / 2. + roll;
	// Str modifier: We divide by 180 since that'll be about the average equipped character.
	dam = (dam * (float)GET_C_STR(ch)) / 180.;
	// 1/2 damage (+1/56th) for level 1s up to full damage at 56.
	dam = dam * (GET_LEVEL(ch) / 2 + 28.) / 56.;
	// Apply the damfactor property.
	dam *= get_property("skill.headbutt.damfactor", 1.000);

	if (GET_RACE(ch) == RACE_MINOTAUR)
	{
		dam *= get_property("damage.headbutt.damBonusMinotaur", 1.500);
	}

	// Added for Tieflings (they have horns!).
	if (GET_RACE(ch) == RACE_TIEFLING)
	{
		dam *= get_property("damage.headbutt.damBonusTiefling", 1.250);
	}
	return dam;
}

// What a smaller or larger target does to a hit's damage.
static float headbutt_smaller_factor()
{
	return get_property("damage.headbutt.damBonusVsSmaller", 1.10);
}

static float headbutt_larger_factor()
{
	return get_property("damage.headbutt.damPenaltyVsLarger", 0.900);
}

// What a target gets from a hit, in pulses: the strong and weak daze.
static int headbutt_daze_lag()
{
	return (int)(PULSE_VIOLENCE * 1);
}

static int headbutt_daze_stun()
{
	return (int)(PULSE_VIOLENCE * 1.5);
}

static int headbutt_weak_daze()
{
	return (int)(PULSE_VIOLENCE * 0.5);
}

// The chance threshold a second headbutt rolls 0-300 against.
static int double_headbutt_threshold(P_char ch)
{
	return GET_CHAR_SKILL(ch, SKILL_DOUBLE_HEADBUTT);
}

// The second headbutt's damage from the first's.
static int double_headbutt_damage(float dam)
{
	return (int)(dam / 2);
}

std::string headbutt_facts(P_char ch)
{
	const float low = headbutt_hit_damage(ch, headbutt_hit_roll(lowest_rolls));
	const float high = headbutt_hit_damage(ch, headbutt_hit_roll(highest_rolls));
	return fact("Damage on a hit",
		    show({ (int)low, (int)high }) + " with your rating, strength and level") +
	       fact("If the target is smaller", show({ (int)(low * headbutt_smaller_factor()),
						       (int)(high * headbutt_smaller_factor()) })) +
	       fact("If the target is larger", show({ (int)(low * headbutt_larger_factor()),
						      (int)(high * headbutt_larger_factor()) })) +
	       "  Armor and other damage reductions don't apply to a hit.\n" +
	       fact("Damage to you on a bad miss", show({ headbutt_miss_damage(lowest_rolls),
							  headbutt_miss_damage(highest_rolls) })) +
	       fact("Damage to you when it backfires, more on a smaller target",
		    show({ headbutt_backfire_damage(lowest_rolls),
			   headbutt_backfire_damage(highest_rolls) })) +
	       fact("Knocked out when it backfires",
		    seconds(headbutt_knockout(lowest_rolls)) + " to " +
			    seconds(headbutt_knockout(highest_rolls))) +
	       fact("Your lag on a hit", seconds(headbutt_hit_lag())) +
	       fact("Your lag on a bad miss", seconds((int)headbutt_miss_lag())) +
	       fact("Your lag when it backfires", seconds(headbutt_backfire_lag())) +
	       fact("Your lag if the target isn't standing", seconds(headbutt_position_lag())) +
	       fact("Your lag if the target is immaterial", seconds(headbutt_immaterial_lag())) +
	       fact("Your lag against an elite or greater race", seconds(headbutt_refused_lag())) +
	       fact("Your lag if you try again too soon", seconds(headbutt_refused_lag())) +
	       fact("Before you can headbutt again after a hit", seconds(headbutt_hit_rest())) +
	       fact("  After a miss", seconds(headbutt_miss_rest())) +
	       fact("  After a backfire", seconds(headbutt_backfire_rest())) +
	       "  A hit may also leave the target with one of these:\n" +
	       fact("  Knocked out", seconds(headbutt_knockout(lowest_rolls)) + " to " +
					     seconds(headbutt_knockout(highest_rolls))) +
	       fact("  Stunned and lagged",
		    seconds(headbutt_daze_stun()) + " and " + seconds(headbutt_daze_lag())) +
	       fact("  Stunned and lagged, 4 times in 5", seconds(headbutt_weak_daze()) + " each") +
	       fact("  Otherwise lagged", seconds(headbutt_daze_lag())) +
	       "  The target must be standing and within one size of you.\n";
}

std::string double_headbutt_facts(P_char ch)
{
	const float low = headbutt_hit_damage(ch, headbutt_hit_roll(lowest_rolls));
	const float high = headbutt_hit_damage(ch, headbutt_hit_roll(highest_rolls));
	return fact("Chance of a second headbutt after a hit",
		    std::to_string(double_headbutt_threshold(ch)) + " in 301") +
	       fact("Its damage against a target your size",
		    show({ double_headbutt_damage(low), double_headbutt_damage(high) })) +
	       "  It is half of the first hit's damage, after the target's size.\n";
}

void do_headbutt(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim, tch;
	struct affected_type af;
	int chsize, victsize, chance, roll;
	float dam;

	struct damage_messages messages_humanoid = {
		"You leave a huge, &+rred&N swollen lump on $N's temple.",
		"Everything is blurry after $n's head came crashing into your skull.",
		"$N's face turns pale as $n slams his head into $S face.",
		"You split $N's skull wide open, causing immediate death!",
		"$n's exploding headbutt relieves you of your duties in life.",
		"$n bashes $N's skull in with a swift, stern butt to the head.",
		0
	};
	struct damage_messages *messages = &messages_humanoid;

	struct damage_messages messages_other = {
		"You slam your head into $N, leaving a huge, &+rred&N swollen lump.",
		"$n's forehead &+Wslams&n into you!",
		"$n &+Wslams&n $s head into $N, leaving a huge, &+rred&n swollen lump.",
		"You slam $N with your head, destroying $M completely!",
		"$n's exploding headbutt relieves you of your duties in life.",
		"$n's headbutt sends $N into the afterlife."
	};

	struct damage_messages fail_messages = {
		"You get the best of $N as $E headbutts you.",
		"Ouch, that seriously hurt!",
		"$N headbutts $n, but apparently $n got the best of $M.",
		"As $N's skull crashes into you, it splits wide open, causing $S immediate death!",
		"You feel your head split, and your life escaping from you.",
		"$N skull splits open as it collides with $n in the wrong way.",
		0
	};

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (!(chance = GET_CHAR_SKILL(ch, SKILL_HEADBUTT)))
	{
		send_to_char("You don't know how.  Besides, you might hurt yourself.\n", ch);
		return;
	}

	if (!(victim = ParseTarget(ch, argument)))
	{
		send_to_char("Headbutt whom?\n", ch);
		// CharWait(ch, 1 * WAIT_SEC);
		return;
	}

	if (ch == victim)
	{
		act("Very funny.  But not as funny as your face. :P", TRUE, ch, 0, 0, TO_CHAR);
		return;
	}

	// Higher and equal level Immortals can headbutt.
	if ((IS_TRUSTED(victim) && GET_LEVEL(victim) > GET_LEVEL(ch)) ||
	    isname("_nobutt_", GET_NAME(victim)))
	{
		act("$N is clearly too quick and clever for such a brutish attack.", FALSE, ch, 0,
		    victim, TO_CHAR);
		return;
	}
	/*
	if (!HAS_FOOTING(ch))
	{
	  send_to_char("You have no footing here!\n", ch);
	  return;
	}
   */
	if (!CanDoFightMove(ch, victim))
	{
		return;
	}

	if (!on_front_line(ch) || !on_front_line(victim))
	{
		send_to_char("You can't quite get close enough...\n", ch);
		return;
	}

	chsize = get_takedown_size(ch);
	victsize = get_takedown_size(victim);
	// Size handling:
	// For standing, we're +1/-1 size.
	if (GET_POS(victim) == POS_STANDING)
	{
		if (victsize < chsize - 1)
		{
			act("It is far too small.  You're better off squashing it.", FALSE, ch, 0,
			    0, TO_CHAR);
			return;
		}
		if (victsize > chsize + 1)
		{
			act("You'd have to grow considerably to do that!", FALSE, ch, 0, 0,
			    TO_CHAR);
			return;
		}
	}
	/* Not allowing kneeling/sitting targets for now.
	  // For kneeling to be down 0, 1 or 2 sizes
	  // For sitting down 1/2/3 sizes.
	  else if( (GET_POS(victim) == POS_KNEELING && ( victsize >= chsize && victsize <= chsize + 2 ))
	    || (GET_POS(victim) == POS_SITTING && ( victsize >= chsize + 1 && victsize <= chsize + 3 )) )
	  {
	  }
	*/
	else
	{
		act("$n attempted to headbutt you.", FALSE, ch, 0, victim, TO_VICT);
		act("Headbutt requires you to be able to reach his head!", FALSE, ch, 0, 0,
		    TO_CHAR);
		CharWait(ch, headbutt_position_lag());
		return;
	}

	if (IS_IMMATERIAL(victim))
	{
		act("Your head passes through $N!", FALSE, ch, 0, victim, TO_CHAR);
		act("$n grunts as $s head passes cleanly through you!", FALSE, ch, 0, victim,
		    TO_VICT);
		act("$n grunts as $s head simply passes through $N!", FALSE, ch, 0, victim,
		    TO_NOTVICTROOM);
		CharWait(ch, headbutt_immaterial_lag());
		return;
	}

	if (IS_ELITE(victim) || IS_GREATER_RACE(victim))
	{
		send_to_char("They are far too skilled to fall for such a move.\n", ch);
		CharWait(ch, headbutt_refused_lag());
		return;
	}

	if (!IS_HUMANOID(victim) || get_takedown_size(victim) > get_takedown_size(ch) + 1)
	{
		messages = &messages_other;
	}

	if (affected_by_spell(ch, SKILL_HEADBUTT) && !IS_TRUSTED(ch))
	{
		act("You're still spinning in circles from your last headbutt.", FALSE, ch, 0, 0,
		    TO_CHAR);
		CharWait(ch, headbutt_refused_lag());
		return;
	}

	chance += (GET_LEVEL(ch) - GET_LEVEL(victim)) / 2;

	/* dont care for the penalty for larger mobs - Drannak
	  if (get_takedown_size(victim) > get_takedown_size(ch))
	  {
	    for( int j = 0; j < ( get_takedown_size(victim) - get_takedown_size(ch) ); j++ )
	    {
	      success = (int) success * 0.90;
	    }
	  }
	*/

	// anatomy check
	if (GET_CHAR_SKILL(ch, SKILL_ANATOMY) &&
	    5 + GET_CHAR_SKILL(ch, SKILL_ANATOMY) / 10 > number(0, 100))
	{
		chance += chance / 2;
	}

	/*  maybe the attacker or victim are lucky */
	if ((GET_C_LUK(ch) / 2) > number(0, 80))
	{
		chance += chance / 10;
	}
	if ((GET_C_LUK(victim) / 2) > number(0, 80))
	{
		chance -= chance / 10;
	}

	// Making agi a factor.
	chance += (GET_C_AGI(ch) - GET_C_AGI(victim)) / 2;

	if (/*IS_TRUSTED(ch) ||*/ !IS_AWAKE(victim))
	{
		roll = 100;
	}
	else
	{
		roll = number(1, chance);
	}

	debug("do_headbutt: (%s) butting (%s) chance (%d) roll (%d).", GET_NAME(ch),
	      GET_NAME(victim), chance, roll);

	// Damage results report deaths, so count delivered damage separately for feedback.
	auto headbutt_damage = [&](P_char source, P_char target, double amount, int flags,
				   damage_messages *hit_messages)
	{
		int delivered = 0;
		int result = melee_damage(source, target, amount, flags, hit_messages, &delivered);
		if (result == DAM_NONEDEAD && delivered == 0)
		{
			bool backfire = source != ch;
			act(backfire ? "Your headbutt backfires, but does no damage to you." :
				       "Your headbutt does no damage to $N.",
			    FALSE, ch, 0, victim, TO_CHAR);
			act(backfire ? "$n's headbutt backfires, but does no damage to $m." :
				       "$n's headbutt does no damage to you.",
			    FALSE, ch, 0, victim, TO_VICT);
			act(backfire ? "$n's headbutt backfires, but does no damage to $m." :
				       "$n's headbutt does no damage to $N.",
			    FALSE, ch, 0, victim, TO_NOTVICTROOM);
		}
		return result;
	};

	// failed catastrophically!
	if (!notch_skill(ch, SKILL_HEADBUTT, get_property("skill.notch.offensive", 7)) && roll <= 2)
	{
		dam = headbutt_backfire_damage(live_rolls);

		if (get_takedown_size(victim) < get_takedown_size(ch))
		{
			dam += dam / 2.;
		}

		memset(&af, 0, sizeof(af));
		af.type = SKILL_HEADBUTT;
		af.duration = headbutt_backfire_rest();
		af.flags = AFFTYPE_SHORT;
		affect_to_char(ch, &af);
		CharWait(ch, headbutt_backfire_lag());

		if (headbutt_damage(victim, ch, dam,
				    PHSDAM_NOPOSITION | PHSDAM_TOUCH | PHSDAM_NOREDUCE,
				    &fail_messages) != DAM_NONEDEAD)
		{
			return;
		}
		knock_out(ch, headbutt_knockout(live_rolls));
	}
	// merely failed
	else if (roll <= 5)
	{
		dam = headbutt_miss_damage(live_rolls);

		memset(&af, 0, sizeof(af));
		af.type = SKILL_HEADBUTT;
		af.duration = headbutt_miss_rest();
		af.flags = AFFTYPE_SHORT;
		affect_to_char(ch, &af);
		CharWait(ch, headbutt_miss_lag());

		if (headbutt_damage(victim, ch, dam, PHSDAM_NOPOSITION, &fail_messages) !=
		    DAM_NONEDEAD)
		{
			return;
		}
	}
	// success!
	else
	{
		/* This is really horrible.  Redoing this and including level.
		dam = ((56 * (number(1, 25))/51 + GET_C_STR(ch) + GET_CHAR_SKILL(ch, SKILL_HEADBUTT)));
		dam = (dam * 1.2);
		// Since we have PHSDAM_NOREDUCE, we need to divide by 4 from old code.
		dam /= 4;
		 */

		dam = headbutt_hit_damage(ch, headbutt_hit_roll(live_rolls));

		// if victim is smaller, do a bit more damage
		if (get_takedown_size(victim) < get_takedown_size(ch))
		{
			dam *= headbutt_smaller_factor();
		}

		// if victim is larger, do a bit less damage
		if (get_takedown_size(victim) > get_takedown_size(ch))
		{
			dam *= headbutt_larger_factor();
		}

		CharWait(ch, headbutt_hit_lag());
		debug("do_headbutt: (%s) butting (%s) dam (%d) skill (%d).", GET_NAME(ch),
		      GET_NAME(victim), (int)dam, GET_CHAR_SKILL(ch, SKILL_HEADBUTT));
		if (headbutt_damage(ch, victim, (int)dam,
				    PHSDAM_NOPOSITION | PHSDAM_TOUCH | PHSDAM_NOREDUCE,
				    messages) != DAM_NONEDEAD)
		{
			return;
		}

		if (double_headbutt_threshold(ch) > number(0, 300))
		{
			act("You deftly pull back your head and ram it into $N again!", FALSE, ch,
			    0, victim, TO_CHAR);
			act("With a quick move, $n pulls back $s head and rams it into you again!",
			    FALSE, ch, 0, victim, TO_VICT);
			act("$n deftly pulls back $s head and slams it into $N again!", FALSE, ch,
			    0, victim, TO_NOTVICTROOM);
			debug("do_headbutt: (%s) double butting (%s) dam (%d) skill (%d).",
			      GET_NAME(ch), GET_NAME(victim), (int)dam / 2,
			      GET_CHAR_SKILL(ch, SKILL_DOUBLE_HEADBUTT));
			if (headbutt_damage(ch, victim, double_headbutt_damage(dam),
					    PHSDAM_NOPOSITION | PHSDAM_TOUCH | PHSDAM_NOREDUCE,
					    messages) != DAM_NONEDEAD)
			{
				return;
			}
		}

		memset(&af, 0, sizeof(af));
		af.type = SKILL_HEADBUTT;
		af.duration = headbutt_hit_rest();
		af.flags = AFFTYPE_SHORT;
		affect_to_char(ch, &af);

		roll = number(1, 100 - (chance / 2));

		// 10% chance at 100% chance
		if (roll < 6 && !IS_AFFECTED(victim, AFF_KNOCKED_OUT))
		{
			knock_out(victim, headbutt_knockout(live_rolls));
		}
		else if (roll < 11)
		{
			send_to_char("Wow!  Look at all those stars!!\n", victim);
			CharWait(victim, headbutt_daze_lag());
			Stun(victim, ch, headbutt_daze_stun(), FALSE);
		}
		else if (roll < 16)
		{
			send_to_char("Wow!  Look at all those stars!\n", victim);

			if (number(0, 4))
			{
				CharWait(victim, headbutt_weak_daze());
				Stun(victim, ch, headbutt_weak_daze(), FALSE);
			}
		}
		else
		{
			CharWait(victim, headbutt_daze_lag());
		}
		if (roll < 25 && !IS_SET(ch->specials.act, PLR_VICIOUS) && IS_FIGHTING(ch))
		{
			for (tch = world[ch->in_room].people; tch; tch = tch->next_in_room)
			{
				if (GET_OPPONENT(tch) == ch)
				{
					break;
				}
			}
			if (!tch)
			{
				stop_fighting(ch);
			}
		}
	}
}

// The chance threshold a garrote rolls 1-105 against: assassins learn it faster.
static int garrote_threshold(P_char ch)
{
	int success = GET_CHAR_SKILL(ch, SKILL_GARROTE);
	// Old school assassin mobs learn garrote faster.
	if (GET_CLASS(ch, CLASS_ASSASSIN))
	{
		success *= 2;
		if (success > 100)
		{
			success = 100;
		}
	}
	return success;
}

// How long, in pulses, a miss and a hit keep the attacker from another garrote.
static int garrote_miss_rest()
{
	return PULSE_VIOLENCE;
}

static int garrote_hit_rest()
{
	return PULSE_VIOLENCE * 2;
}

// The attacker's lag, in pulses, on a miss and on a hit.
static int garrote_miss_lag()
{
	return (3 * WAIT_SEC) / 2;
}

static int garrote_hit_lag()
{
	return (WAIT_SEC * 3) / 2;
}

// The rounds a hit bleeds for, from the attacker's level.
static int garrote_rounds(const Rolls &rolls, P_char ch)
{
	return (GET_LEVEL(ch) - 1) / 11 + rolls.number(0, 2);
}

// One round's bleeding; ch here is the target, whose level sets it.
static int garrote_bleed_damage(const Rolls &rolls, P_char ch)
{
	return rolls.dice(GET_LEVEL(ch) / 18, 4);
}

// True on the 1 round in 10 that stops the target's casting.
static bool garrote_stops_casting_roll(const Rolls &rolls)
{
	return !rolls.number(0, 9);
}

std::string garrote_facts(P_char ch)
{
	// A round always happens, even when the roll leaves none to count down.
	return fact("Chance", std::to_string(garrote_threshold(ch)) + " in 105") +
	       fact("Rounds of bleeding", show({ MAX(1, garrote_rounds(lowest_rolls, ch)),
						 MAX(1, garrote_rounds(highest_rolls, ch)) }) +
						  " at your level") +
	       fact("Bleeding per round on a target of your level",
		    show({ garrote_bleed_damage(lowest_rolls, ch),
			   garrote_bleed_damage(highest_rolls, ch) })) +
	       "  Bleeding grows with the target's level, skips defenses and never kills.\n" +
	       fact("Chance each round stops casting", "1 in 10, not elites or greater races") +
	       fact("Your lag", seconds(garrote_hit_lag())) +
	       fact("Before you can garrote again", seconds(garrote_hit_rest()) + " after a hit, " +
							    seconds(garrote_miss_rest()) +
							    " after a miss") +
	       "  A hit also stops casting at once. The target must be within one size.\n";
}

// One round of bleeding from garrote (throat cut).
// Input: ch is cutter, victim is bleeding, obj should be NULL,
//   and data = int* to the number of rounds left to bleed.
// Output: victim bled one round (doesn't go below 0 hps),
//   *data decremented 1 and another round event created if *data > 0.
void event_garroteproc(P_char ch, P_char /*victim*/, P_obj /*obj*/, void *data)
{
	int dam;
	int count = *((int *)data);
	int rand1 = number(1, 100);

	dam = garrote_bleed_damage(live_rolls, ch);

	if (GET_HIT(ch) - dam > 0)
	{
		GET_HIT(ch) -= dam;
		if (rand1 > 50)
		{
			send_to_char("&+rYour bl&+Rood spl&+ratte&+Rrs as it hits the ground.&N\n",
				     ch);
			act("$n&+r's blo&+Rod spla&+rtter&+Rs as it hits the ground.&N", TRUE, ch,
			    NULL, NULL, TO_NOTVICT);
			make_bloodstain(ch);
			if (garrote_stops_casting_roll(live_rolls) && !IS_GREATER_RACE(ch) &&
			    !IS_ELITE(ch))
			{
				StopCasting(ch);
			}
		}
		else
		{
			send_to_char(
				"&+rYour wound gushes &+Rblood &+rall over the surrounding area.&N\n",
				ch);
			act("$n&+r's wound gushes &+Rblood &+rall over the surrounding area.", TRUE,
			    ch, NULL, NULL, TO_NOTVICT);
			make_bloodstain(ch);
			if (garrote_stops_casting_roll(live_rolls) && !IS_GREATER_RACE(ch) &&
			    !IS_ELITE(ch))
			{
				StopCasting(ch);
			}
		}
	}

	// Round already happened, so we subtract then check.
	if (--count > 0)
	{
		add_event(event_garroteproc, PULSE_VIOLENCE, ch, 0, 0, 0, &count, sizeof(count));
	}
	else
	{
		send_to_char("&+rYour bleeding appears to have stopped.&N\n", ch);
	}
}

// One round of an assassin's sneaky strike bleed.
static int sneaky_strike_bleed_damage(const Rolls &rolls)
{
	return rolls.dice(3, 6);
}

void event_bleedproc(P_char ch, P_char victim, P_obj /*obj*/, void *data)
{
	int count = *((int *)data);

	// Deliver damage with no reductions or messages.
	if (raw_damage(ch, victim, sneaky_strike_bleed_damage(live_rolls), PHSDAM_NOREDUCE, NULL) !=
	    DAM_NONEDEAD)
		return;

	// Show messages..
	if (number(1, 100) > 50)
	{
		send_to_char("&+rYour bl&+Rood spl&+ratte&+Rrs as it hits the ground.&N\n", victim);
		act("$n&+r's blo&+Rod spla&+rtter&+Rs as it hits the ground.&N", TRUE, victim, NULL,
		    NULL, TO_NOTVICT);
	}
	else
	{
		send_to_char("&+rYour wound gushes &+Rblood &+rall over the surrounding area.&N\n",
			     victim);
		act("$n&+r's wound gushes &+Rblood &+rall over the surrounding area.", TRUE, victim,
		    NULL, NULL, TO_NOTVICT);
	}
	make_bloodstain(ch);

	if (count >= 0)
	{
		count--;
		add_event(event_bleedproc, PULSE_VIOLENCE, ch, victim, 0, 0, &count, sizeof(count));
	}
	else
	{
		send_to_char("&+rYour bleeding appears to have stopped.&N\n", victim);
	}
}

// The weapon's roll in a sneaky strike.
static int sneaky_strike_weapon_damage(const Rolls &rolls, P_obj weapon)
{
	return (rolls.dice(weapon->value[1], MAX(1, weapon->value[2])) + weapon->value[2]);
}

// The multiplier rolled into a sneaky strike.
static int sneaky_strike_multiplier(const Rolls &rolls)
{
	return rolls.number(25, 30);
}

// A sneaky strike's damage from the weapon's roll and the multiplier.
static int sneaky_strike_damage(P_char ch, int dam, int multiplier, int skill)
{
	dam += str_app[STAT_INDEX(GET_C_STR(ch))].todam + GET_C_DEX(ch) / 4;
	dam = (int)(dam * multiplier * (1 + ((double)GET_LEVEL(ch)) / MAXLVLMORTAL) *
		    (((double)skill) / 100));

	// dambonus for thiefs - roughly 10-15 damage more at 12
	if (GET_SPEC(ch, CLASS_ROGUE,
		     SPEC_THIEF)) // proc skill for thief - possibility to blind on sneaky strike
	{
		dam /= 16 * 4;
	}
	else
	{
		dam /= 20 * 4;
	}
	return dam;
}

// The rolled rounds of an assassin's bleed; event_bleedproc runs two more than this.
static int sneaky_strike_bleed_rounds(const Rolls &rolls)
{
	return rolls.number(4, 7);
}

// The vitality a mercenary's strike takes from a player.
static int sneaky_strike_drain(const Rolls &rolls)
{
	return rolls.number(20, 45);
}

// How long, in pulses, a thief's strike blinds.
static int sneaky_strike_blind()
{
	return 1 * PULSE_VIOLENCE;
}

// The attacker's lag after a strike, in pulses.
static int sneaky_strike_lag()
{
	return PULSE_VIOLENCE;
}

std::string sneaky_strike_facts(P_char ch)
{
	std::string facts;
	const int skill = GET_CHAR_SKILL(ch, SKILL_SNEAKY_STRIKE);
	P_obj weapon = ch->equipment[WIELD];
	if (weapon)
		facts += fact("Damage with your weapon",
			      show({ sneaky_strike_damage(
					     ch, sneaky_strike_weapon_damage(lowest_rolls, weapon),
					     sneaky_strike_multiplier(lowest_rolls), skill),
				     sneaky_strike_damage(
					     ch, sneaky_strike_weapon_damage(highest_rolls, weapon),
					     sneaky_strike_multiplier(highest_rolls), skill) }));
	facts += "  Armor and other damage reductions don't apply to it.\n" +
		 fact("Your lag", seconds(sneaky_strike_lag()));
	if (GET_SPEC(ch, CLASS_ROGUE, SPEC_THIEF))
		facts += fact("Follow-up", "stab an NPC, or blind a player for " +
						   seconds(sneaky_strike_blind()));
	if (GET_CLASS(ch, CLASS_BARD))
		facts += fact("Follow-up", "a stab");
	if (GET_SPEC(ch, CLASS_ROGUE, SPEC_ASSASSIN))
		facts += fact("Follow-up",
			      "a stab and " +
				      show({ sneaky_strike_bleed_rounds(lowest_rolls) + 2,
					     sneaky_strike_bleed_rounds(highest_rolls) + 2 }) +
				      " rounds of bleeding") +
			 fact("Bleeding per round",
			      show({ sneaky_strike_bleed_damage(lowest_rolls),
				     sneaky_strike_bleed_damage(highest_rolls) }));
	if (GET_CLASS(ch, CLASS_MERCENARY))
		facts += fact("Follow-up", "stun an NPC, or take " +
						   show({ sneaky_strike_drain(lowest_rolls),
							  sneaky_strike_drain(highest_rolls) }) +
						   " vitality from a player");
	return facts + "  A follow-up rolls against your rating less 1/6 of the target's agility.\n"
		       "  You need a weapon, and the target must be within one size of you.\n";
}

void event_sneaky_strike(P_char ch, P_char victim, P_obj obj, void *data)
{
	static bool DEBUG = TRUE;

	int dam = 0;
	int skill = 0;
	P_obj weapon;
	int skl_lvl = 0;
	int i = 0;
	struct affected_type afs;

	struct damage_messages messages = {
		"You find weakness in $N's defenses and land a sneaky surprise attack!",
		"Before you can react $n suddenly lashes at you.",
		"$n gets past $N's defenses and strikes with a mighty blow.",
		"You find an open spot in $N's defenses and finish them off with a swift strike.",
		"Before you can react $n suddenly leaps at you, getting past all your defenses.",
		"$n finishes $N off with a sudden surprise attack!",
		0,
		0
	};

	if (IS_TRUSTED(ch) && !victim && (bool)data)
	{
		DEBUG = !DEBUG;
		debug("sneaky_strike: DEBUG display turned %s.", DEBUG ? "ON" : "OFF");
		return;
	}

	affect_from_char(ch, SKILL_SNEAKY_STRIKE);

	if (!(weapon = ch->equipment[WIELD])) /*
	   if(!weapon && !(weapon = ch->equipment[WIELD2]))
	     if(!weapon && !(weapon = ch->equipment[WIELD3]))
	       if(!weapon && !(weapon = ch->equipment[WIELD4]))*/
	{
		send_to_char("You must be wielding a weapon.\r\n", ch);
		return;
	}

	if (!victim || (ch->in_room != victim->in_room))
	{
		send_to_char("Your victim has escaped!\n", ch);
		return;
	}

	if (!CanDoFightMove(ch, victim))
		return;

	if (GET_POS(ch) < POS_STANDING)
	{
		send_to_char("You were unable to execute your deadly combination.\n", ch);
		return;
	}

	if (has_innate(victim, INNATE_DRAGONMIND) && !number(0, 1))
	{
		send_to_char("Your victim notice your attempt and rolls out of the way!\n", ch);
		send_to_char("You sidestep $N's attack.\n", victim);
		return;
	}
	if (!can_hit_target(ch, victim))
	{
		send_to_char("Seems that it's too crowded!\n", ch);
		return;
	}

	skill = GET_CHAR_SKILL(ch, SKILL_SNEAKY_STRIKE);

	if ((weapon = ch->equipment[WIELD]))
		dam = sneaky_strike_weapon_damage(live_rolls, weapon);
	else
	{
		dam = (IS_PC(ch) ? dice(1, skill / 5) :
				   dice(ch->points.damnodice, ch->points.damsizedice));
	}
	/* notch_skill(ch, SKILL_SNEAKY_STRIKE, get_property("skill.notch.offensive", 7)); */
	notch_skill(ch, SKILL_SNEAKY_STRIKE, 5);

	dam = sneaky_strike_damage(ch, dam, sneaky_strike_multiplier(live_rolls), skill);

	if (DEBUG)
	{
		debug("event_sneaky_strike: (%s) striking (%s) dam (%d).", GET_NAME(ch),
		      GET_NAME(victim), dam);
	}
	melee_damage(ch, victim, dam, PHSDAM_NOREDUCE | PHSDAM_NOPOSITION, &messages);
	if (!ch || !victim || !IS_ALIVE(victim) || !IS_ALIVE(ch))
	{
		return;
	}

	if (GET_SPEC(ch, CLASS_ROGUE, SPEC_THIEF) ||
	    (GET_CLASS(ch,
		       CLASS_BARD))) // proc skill for thief - possibility to blind on sneaky strike
	{
		skl_lvl = (int)(GET_CHAR_SKILL(ch, SKILL_SNEAKY_STRIKE));
		i = skl_lvl - (GET_C_AGI(victim) / 6);
		if (number(1, 100) < i)
		{
			if (IS_NPC(victim) && (GET_CLASS(ch, CLASS_ROGUE)))
			{
				act("&+LYou quickly step into the sh&+wad&+Wows&+L, and suddenly appear behind $N &+Lstriking violently...",
				    FALSE, ch, 0, victim, TO_CHAR);
				act("$n &+Lquickly steps into the sh&+wad&+Wows&+L, and suddenly appears behind $N &+Lstriking violently...",
				    TRUE, ch, 0, victim, TO_NOTVICT);
				single_stab(ch, victim, weapon);
				/* Commenting out 2nd stab
				            act("&+L...you then meld into your victim's sh&+wad&+Wow&+L, only to attack again!",
				              FALSE, ch, 0, victim, TO_CHAR);
				            act("&+L...$n &+Lthen quickly fades into the sh&+wad&+Wow&+L, re-appearing only to attack again!",
				            TRUE, ch, 0, victim, TO_NOTVICT);
				            single_stab(ch, victim, weapon);
				*/
			}
			else if (GET_CLASS(ch, CLASS_BARD))
			{
				act("&+LYou quickly step into the sh&+wad&+Wows&+L, and suddenly appear behind $N &+Lstriking violently...",
				    FALSE, ch, 0, victim, TO_CHAR);
				act("$n &+Lquickly steps into the sh&+wad&+Wows&+L, and suddenly appears behind $N &+Lstriking violently...",
				    TRUE, ch, 0, victim, TO_NOTVICT);
				single_stab(ch, victim, weapon);
			}
			else if (!IS_AFFECTED(victim, AFF_BLIND))
			{
				act("&+LYou lash out from the sh&+wad&+Wows&+L, hitting $N right in the &+Wface&+L, causing them to temporarily black out.",
				    FALSE, ch, 0, victim, TO_CHAR);
				act("$n &+Lsteps quickly into the sh&+wad&+Wows&+L and darts quickly at your &+Wface&+L, causing you to temporarily black out.",
				    TRUE, ch, 0, victim, TO_VICT);
				act("$n &+Lfades into the sh&+wad&+Wows&+L and quickly strikes at $N's &+Wface&+L, causing them to see stars.",
				    TRUE, ch, 0, victim, TO_NOTVICT);
				blind(ch, victim, sneaky_strike_blind());
			}
		}
	} // end thief|bard spec check

	if (GET_SPEC(ch, CLASS_ROGUE, SPEC_ASSASSIN)) // proc skill for assassin and bard
	{
		skl_lvl = (int)(GET_CHAR_SKILL(ch, SKILL_SNEAKY_STRIKE));
		i = skl_lvl - (GET_C_AGI(victim) / 6);
		if (number(1, 100) < i)
		{
			if (IS_NPC(victim))
			{
				int numb = sneaky_strike_bleed_rounds(live_rolls);
				act("&+rYou sneak up on $N &+rand drive your &+Lweapon &+rdeep into a vital organ!&N",
				    TRUE, ch, obj, victim, TO_CHAR);
				act("&+L$n &+rsneaks up on $N&+r driving their &+Lweapon &+rdeep into a vital organ!&N",
				    TRUE, ch, obj, victim, TO_NOTVICT);
				act("&+L$n&+r appears behind you and drives their &+Lweapon &+rdeep into one of your vital organs!&N",
				    TRUE, ch, obj, victim, TO_VICT);
				add_event(event_bleedproc, PULSE_VIOLENCE, ch, victim, 0, 0, &numb,
					  sizeof(numb));
				act("&+L...$n &+Lthen quickly fades into the sh&+wad&+Wow&+L, re-appearing only to attack again!",
				    TRUE, ch, 0, victim, TO_NOTVICT);
				single_stab(ch, victim, weapon);
			}
			else
			{
				int numb = sneaky_strike_bleed_rounds(live_rolls);
				act("&+rYou sneak up on $N &+rand drive your &+Lweapon &+rdeep into a vital organ!&N",
				    TRUE, ch, obj, victim, TO_CHAR);
				act("&+L$n &+rsneaks up on $N&+r driving their &+Lweapon &+rdeep into a vital organ!&N",
				    TRUE, ch, obj, victim, TO_NOTVICT);
				act("&+L&n&+r appears behind you and drives their &+Lweapon &+rdeep into one of your vital organs!&N",
				    TRUE, ch, obj, victim, TO_VICT);
				add_event(event_bleedproc, PULSE_VIOLENCE, ch, victim, 0, 0, &numb,
					  sizeof(numb));
				act("&+L...$n &+Lthen quickly fades into the sh&+wad&+Wow&+L, re-appearing only to attack again!",
				    TRUE, ch, 0, victim, TO_NOTVICT);
				single_stab(ch, victim, weapon);
			}
		}
	} // endassassinspeccheck

	if (GET_CLASS(ch, CLASS_MERCENARY)) // proc skill for mercenary - sucks moves
	{
		skl_lvl = (int)(GET_CHAR_SKILL(ch, SKILL_SNEAKY_STRIKE));
		i = skl_lvl - (GET_C_AGI(victim) / 6);
		if (number(1, 100) < i)
		{
			if (IS_NPC(victim) && !IS_STUNNED(victim))
			{
				act("&+yYou fill with the &+RRAGE &+yof your &+Yancestors&+y, striking $N &+ywith all of your &+Bmight&+y!",
				    FALSE, ch, 0, victim, TO_CHAR);
				act("$n &+yseems to fill with unearthly &+RRAGE&+y, and strikes $N &+ywith all of their &+Bmight&+y!",
				    TRUE, ch, 0, victim, TO_NOTVICT);
				Stun(victim, victim, PULSE_VIOLENCE, FALSE);
				;
			}
			else
			{
				act("&+yYou tighten up and skillfully hit $N right in the &+Ystomach&+y! $N appears a bit less energetic after that hit.",
				    FALSE, ch, 0, victim, TO_CHAR);
				act("$n &+yseems to tense up before unleasing a &+Ypowerful &+ystrike to your abdomen! You feel the a lot less &+Yenergetic&+y.",
				    TRUE, ch, 0, victim, TO_VICT);
				act("$n &+yseems to tense up before unleasing a &+Ypowerful &+ystrike to $N's &+yabdomen&+y, knocking the &+Cwind &+yout of them!",
				    TRUE, ch, 0, victim, TO_NOTVICT);
				i = sneaky_strike_drain(live_rolls);
				if ((GET_VITALITY(victim) - i) < 20)
				{
					GET_VITALITY(victim) = 0;
				}
				else
				{
					GET_VITALITY(victim) -= i;
				}
				StartRegen(victim, regen_resource::vitality);

				if (!affected_by_spell(victim, SKILL_AWARENESS))
				{
					bzero(&afs, sizeof(afs));
					afs.type = SKILL_AWARENESS;
					afs.duration = 5;
					afs.bitvector = AFF_AWARE;
					afs.flags = AFFTYPE_NODISPEL;
					affect_to_char(victim, &afs);
				}
			}
		}
	} // endmercclasscheck

	CharWait(ch, sneaky_strike_lag());
} // drantemp

bool is_preparing_for_sneaky_strike(P_char ch)
{
	if (affected_by_spell(ch, SKILL_SNEAKY_STRIKE))
	{
		return TRUE;
	}
	else
		return FALSE;
}

void sneaky_strike(P_char ch, P_char victim)
{
	struct affected_type af;
	P_obj weapon;
	int size_diff;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
		return;

	weapon = ch->equipment[WIELD];
	size_diff = GET_SIZE(ch) - GET_SIZE(victim);

	if (!weapon)
	{
		send_to_char("You must be wielding a weapon.\r\n", ch);
		return;
	}

	int is_weapon = (GET_ITEM_TYPE(weapon) == ITEM_WEAPON);

	if (!is_weapon) /*
	    if(!weapon && !(weapon = ch->equipment[WIELD2]))
	      if(!weapon && !(weapon = ch->equipment[WIELD3]))
	        if(!weapon && !(weapon = ch->equipment[WIELD4]))*/
	{
		act("$p is not a weapon.", FALSE, ch, weapon, NULL, TO_CHAR);
		return;
	}

	// Size limits 1 up 1 down.
	if (size_diff > 1)
	{
		act("$N is too small for you to strike at like that.", FALSE, ch, NULL,
		    (void *)victim, TO_CHAR);
		return;
	}
	if (size_diff < -1)
	{
		act("$N is too big for you to strike at like that.", FALSE, ch, NULL,
		    (void *)victim, TO_CHAR);
		return;
	}

	send_to_char("You think you noticed an opening in your victim defenses...\n", ch);

	memset(&af, 0, sizeof(af));
	af.type = SKILL_SNEAKY_STRIKE;
	af.flags = AFFTYPE_NODISPEL | AFFTYPE_NOSHOW | AFFTYPE_SHORT;
	af.duration = PULSE_VIOLENCE * number(1, 2);
	affect_to_char(ch, &af);
	add_event(event_sneaky_strike, PULSE_VIOLENCE, ch, victim, 0, 0, 0, 0);
}

void do_mug(P_char /*ch*/, char * /*argument*/, int /*cmd*/) {}

void do_sneaky_strike(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL;
	char target[128];

	if (IS_TRUSTED(ch) && !strcmp(argument, "debug"))
	{
		event_sneaky_strike(ch, NULL, NULL, (void *)(TRUE));
		return;
	}

	if (GET_CHAR_SKILL(ch, SKILL_SNEAKY_STRIKE) == 0)
	{
		send_to_char("Fighting dirty just isn't your bag, baby.\n", ch);
		return;
	}

	if (is_preparing_for_sneaky_strike(ch))
	{
		send_to_char("You're already preparing for a sneak attack!\n", ch);
		return;
	}

	if (GET_OPPONENT(ch))
	{
		victim = GET_OPPONENT(ch);
	}
	else
	{
		one_argument(argument, target);
		if (!(victim = get_char_room_vis(ch, target)))
		{
			send_to_char("Strike at whom?\n", ch);
			return;
		}
	}
	sneaky_strike(ch, victim);
}

// The rating a stab's damage uses: assassins learn it faster.
static int backstab_skill(int skill, P_char ch)
{
	// Old school assassin mobs learn backstab faster.
	if (GET_CLASS(ch, CLASS_ASSASSIN))
	{
		skill *= 2;
		if (skill > 100)
		{
			skill = 100;
		}
	}
	return skill;
}

// The luck roll in a stab's damage.
static int backstab_luck_bonus(const Rolls &rolls, P_char ch)
{
	return (rolls.number(10, GET_C_LUK(ch)) / 10);
}

// A stab's damage from the rating, the luck roll and the weapon.
static int backstab_damage(P_char ch, int skill, P_obj weapon, int luck_bonus)
{
	int dice_mult, dam = 0;
	float dice_mod, level_mult, final_mult, damroll_mult, strdex_mod;

	dice_mod = get_property("backstab.diceMultiplier", 1.000);
	final_mult = get_property("backstab.finalMultiplier", 1.000);
	damroll_mult = get_property("backstab.DamrollMultiplier", 0.500);
	strdex_mod = get_property("backstab.StrDexMultiplier", 0.500);

	dam = (int)((float)GET_DAMROLL(ch) * damroll_mult);

	dam += (GET_C_DEX(ch) + GET_C_STR(ch)) * strdex_mod;

	dam += luck_bonus;

	// 50% damage at 0 skill ... 100% damage at 100 skill.
	dam = (dam * (skill + 100)) / 200;

	dice_mult = (int)(weapon->value[1] + (weapon->value[2] / 2)) / 2;
	dice_mult += weapon->value[1] + (weapon->value[1] / 2);
	// Range from .50 at lvl 1 to 1.00 at 56.
	level_mult = .50 + (float)GET_LEVEL(ch) / 112.;

	dam = (int)dam * (dice_mult * dice_mod);
	dam = (int)dam * level_mult;
	dam = (int)dam * final_mult;
	return dam;
}

// What a target that notices the stab leaves of its damage; a repeat stab leaves less.
static int backstab_noticed_damage(int dam, bool quarter)
{
	dam *= quarter ? .25 : .6;
	return dam;
}

// The least a stab deals to an immobile or sleeping target, and to an incapacitated one.
static int backstab_helpless_damage()
{
	return 80;
}

static int backstab_incapacitated_damage()
{
	return 200;
}

// How long, in pulses, a stabbed player counts as just stabbed.
static int backstab_repeat_window()
{
	return 3 * WAIT_SEC;
}

// The stabber's lag, in pulses.
static int backstab_lag()
{
	return 3 * WAIT_SEC / 2;
}

// True when a target's air aura foils the stab.
static bool backstab_air_aura_roll(const Rolls &rolls)
{
	return rolls.number(1, 20) < 7;
}

// The chance thresholds of a critical stab and a spinal tap, rolled 1-100.
static float critical_stab_threshold(P_char ch)
{
	return get_property("backstab.CriticalStab", 0.200) *
	       GET_CHAR_SKILL(ch, SKILL_CRITICAL_STAB);
}

static float spinal_tap_threshold(P_char ch)
{
	return get_property("backstab.SpinalTap", 0.150) * GET_CHAR_SKILL(ch, SKILL_SPINAL_TAP);
}

// A critical stab's damage from the stab's.
static int critical_stab_damage(int dam)
{
	return dam + (dam * get_property("backstab.CriticalStab.Multiplier", 1.000));
}

// A spinal tap's extra damage; quarter is true on a repeat stab.
static int spinal_tap_damage(const Rolls &rolls, P_char ch, bool quarter)
{
	return (rolls.number(-12, 12) + GET_LEVEL(ch)) / (quarter ? 4 : 1);
}

// The number of 1-100 rolls below a fractional threshold.
static int rolls_below(float threshold)
{
	return MAX(0, (int)ceil(threshold) - 1);
}

// The wielded weapon a stab uses, or null when neither hand can stab.
static P_obj backstab_weapon(P_char ch)
{
	P_obj first_w = ch->equipment[WIELD], second_w = ch->equipment[SECONDARY_WEAPON];
	if (first_w && IS_BACKSTABBER(first_w))
		return first_w;
	return second_w && IS_BACKSTABBER(second_w) ? second_w : nullptr;
}

std::string backstab_facts(P_char ch)
{
	std::string facts;
	P_obj weapon = backstab_weapon(ch);
	if (weapon)
	{
		const int skill = backstab_skill(GET_CHAR_SKILL(ch, SKILL_BACKSTAB), ch);
		const int low =
			backstab_damage(ch, skill, weapon, backstab_luck_bonus(lowest_rolls, ch));
		const int high =
			backstab_damage(ch, skill, weapon, backstab_luck_bonus(highest_rolls, ch));
		facts += fact("Damage with your weapon",
			      show({ low, high }) + " by damroll, strength, dexterity and luck") +
			 fact("If the target notices the stab",
			      show({ backstab_noticed_damage(low, false),
				     backstab_noticed_damage(high, false) })) +
			 fact("A player stabbed again within " + seconds(backstab_repeat_window()),
			      show({ backstab_noticed_damage(low, true),
				     backstab_noticed_damage(high, true) }));
	}
	return facts +
	       fact("Least against an immobile or sleeping target",
		    std::to_string(backstab_helpless_damage())) +
	       fact("Least against an incapacitated target",
		    std::to_string(backstab_incapacitated_damage())) +
	       fact("Your lag", seconds(backstab_lag())) +
	       fact("Chance a target's air aura foils it", "6 in 20") +
	       "  Armor and other damage reductions don't apply. Stoneskin, biofeedback,\n"
	       "  shadow shield, drakescale aegis, vines and ironwood each absorb a stab,\n"
	       "  leaving 1 damage, and then end. You need a piercing weapon, and a target\n"
	       "  on its feet must be within one size of you.\n";
}

std::string critical_stab_facts(P_char ch)
{
	std::string facts =
		fact("Chance on each stab",
		     std::to_string(rolls_below(critical_stab_threshold(ch))) + " in 100");
	P_obj weapon = backstab_weapon(ch);
	if (weapon)
	{
		const int skill = backstab_skill(GET_CHAR_SKILL(ch, SKILL_BACKSTAB), ch);
		facts += fact(
			"Damage with your weapon",
			show({ critical_stab_damage(backstab_damage(
				       ch, skill, weapon, backstab_luck_bonus(lowest_rolls, ch))),
			       critical_stab_damage(
				       backstab_damage(ch, skill, weapon,
						       backstab_luck_bonus(highest_rolls, ch))) }));
	}
	return facts +
	       "  A critical stab gets past a target that would notice it, but a player you\n"
	       "  stabbed moments ago still takes a quarter of the damage.\n";
}

std::string spinal_tap_facts(P_char ch)
{
	return fact("Chance on each stab that isn't critical",
		    std::to_string(rolls_below(spinal_tap_threshold(ch))) + " in 100") +
	       fact("Extra damage",
		    "up to " + std::to_string(spinal_tap_damage(highest_rolls, ch, false)) +
			    " at your level") +
	       "  A repeat stab on a player gets a quarter of that. Armor and other damage\n"
	       "  reductions don't apply.\n";
}

/* stabs with primary weapon, returns TRUE if stabber or victim dies or
   they end up in different rooms */
bool single_stab(P_char ch, P_char victim, P_obj weapon)
{
	// Note: This DEBUG should always match the one in bool backstab(...).
	static bool DEBUG = TRUE;

	int room = ch->in_room, skill, dam = 0;
	bool spinal = FALSE, quarter = FALSE, crit = FALSE;
	struct damage_messages messages = {
		"$N makes a strange sound as you place $p in $S back.",
		"Out of nowhere, $n stabs you in the back.",
		"$n places $p in the back of $N, resulting in some strange noises and some blood.",
		"$N makes a strange sound but is suddenly very silent as you place $p in $S back.",
		"Out of nowhere, $n stabs you in the back, RIP...",
		"$n places $p in the back of $N, resulting in some strange noises, a lot of blood and a corpse.",
		0,
		weapon
	};

	// I know.. the hack here..
	if (ch && IS_TRUSTED(ch) && victim == NULL && weapon == NULL)
	{
		DEBUG = !DEBUG;
		debug("backstab: DEBUG display turned %s.", DEBUG ? "ON" : "OFF");
		return TRUE;
	}

	if (!ch || !victim || !IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		debug("single_stab: ch/victim missing or already dead.");
		return TRUE;
	}

	if ((skill = GET_CHAR_SKILL(ch, SKILL_BACKSTAB)) < 1)
	{
		return FALSE;
	}

	skill = backstab_skill(skill, ch);

	dam = backstab_damage(ch, skill, weapon, backstab_luck_bonus(live_rolls, ch));

	if (GET_CHAR_SKILL(ch, SKILL_CRITICAL_STAB))
	{
		crit = notch_skill(ch, SKILL_CRITICAL_STAB,
				   get_property("skill.notch.offensive", 7)) ||
		       (critical_stab_threshold(ch) > number(1, 100));
	}

	if (((IS_AFFECTED(victim, AFF_AWARE) || IS_AFFECTED(victim, AFF_SKILL_AWARE)) && !crit &&
	     !IS_AFFECTED(victim, AFF_KNOCKED_OUT)) ||
	    affected_by_spell(victim, SKILL_BACKSTAB))
	{
		// A little higher than just int.
		int chance = (5 * GET_C_INT(victim)) / 4;
		// Opportunity max around 150 for 100 skill and 100 agi, +2 agi -> +1 opportunity.
		int opportunity = GET_C_AGI(ch) / 2 + GET_CHAR_SKILL(ch, SKILL_BACKSTAB);
		// Pick a random number between 50 and 150 (for 100 agi 100 skill) to compare against victim's int (125 at 100 int).
		opportunity = number(opportunity / 3, opportunity);
		if (chance >= opportunity || affected_by_spell(victim, SKILL_BACKSTAB))
		{
			send_to_char(
				"&+LSince your victim is &+raware&+L of your presence, you are unable to take full advantage of them...\r\n",
				ch);
			quarter = affected_by_spell(victim, SKILL_BACKSTAB);
			dam = backstab_noticed_damage(dam, quarter);
		}
	}

	if (IS_IMMOBILE(victim) || GET_STAT(victim) <= STAT_SLEEPING)
		dam = MAX(backstab_helpless_damage(), dam);

	// Yeah.. we want them really dead.
	if (GET_STAT(victim) <= STAT_INCAP)
		dam = MAX(backstab_incapacitated_damage(), dam);

	if (affected_by_spell(victim, SPELL_STONE_SKIN) && dam > 1)
	{
		affect_from_char(victim, SPELL_STONE_SKIN);
		dam = 1;
		act("$n attempts to stab you in the back, but your &+Lstone skin&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_VICT);
		act("You attempt to stab $N in the back, but their &+Lstone skin&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$n attempts to stab $N in the back, but $N's &+Lstone skin&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_NOTVICTROOM);
	}

	if (affected_by_spell(victim, SPELL_DRAKESCALE_AEGIS) && dam > 1)
	{
		affect_from_char(victim, SPELL_DRAKESCALE_AEGIS);
		dam = 1;
		act("$n attempts to stab you in the back, but your &+Gdrak&+Les&+Gcale&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_VICT);
		act("You attempt to stab $N in the back, but their &+Gdrak&+Les&+Gcale&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$n attempts to stab $N in the back, but $N's &+Gdrak&+Les&+Gcale&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_NOTVICTROOM);
	}

	if (affected_by_spell(victim, SPELL_SHADOW_SHIELD) && dam > 1)
	{
		affect_from_char(victim, SPELL_SHADOW_SHIELD);
		dam = 1;
		act("$n attempts to stab you in the back, but your &+Lshadow shield&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_VICT);
		act("You attempt to stab $N in the back, but their &+Lshadow shield&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$n attempts to stab $N in the back, but $N's &+Lshadow shield&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_NOTVICTROOM);
	}

	if (affected_by_spell(victim, SPELL_BIOFEEDBACK) && dam > 1)
	{
		affect_from_char(victim, SPELL_BIOFEEDBACK);
		dam = 1;
		act("$n attempts to stab you in the back, but your &+Gbiofeedback&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_VICT);
		act("You attempt to stab $N in the back, but their &+Gbiofeedback&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$n attempts to stab $N in the back, but $N's &+Gbiofeedback&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_NOTVICTROOM);
	}

	if (affected_by_spell(victim, SPELL_VINES) && dam > 1)
	{
		affect_from_char(victim, SPELL_VINES);
		dam = 1;
		act("$n attempts to stab you in the back, but your &+Gvines&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_VICT);
		act("You attempt to stab $N in the back, but their &+Gvines&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$n attempts to stab $N in the back, but $N's &+Gvines&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_NOTVICTROOM);
	}

	if (affected_by_spell(victim, SPELL_IRONWOOD) && dam > 1)
	{
		affect_from_char(victim, SPELL_IRONWOOD);
		dam = 1;
		act("$n attempts to stab you in the back, but your &+yironwood&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_VICT);
		act("You attempt to stab $N in the back, but their &+yironwood&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$n attempts to stab $N in the back, but $N's &+yironwood&n quickly absorbs the impact before fading away!",
		    FALSE, ch, 0, victim, TO_NOTVICTROOM);
	}

	if (crit)
	{
		dam = critical_stab_damage(dam);
		send_to_char("&=LWYou score a CRITICAL HIT!!!&N\n", ch);
		if (DEBUG)
		{
			debug("single_stab: (%s) stabbing (%s) dam (%d) weapon (%dd%d) skill (%d).",
			      GET_NAME(ch), GET_NAME(victim), dam, weapon->value[1],
			      weapon->value[2], skill);
		}
		if (melee_damage(ch, victim, dam, PHSDAM_NOREDUCE | PHSDAM_NOPOSITION, &messages) ||
		    !is_char_in_room(ch, room))
		{
			return TRUE;
		}

		act("You twist the blade and watch as a $N writhes in agony.", FALSE, ch, 0, victim,
		    TO_CHAR);
		act("$n twists the blade lodged in your back causing you to writhe in agony.",
		    FALSE, ch, 0, victim, TO_VICT);
		act("$n twists the blade causing $N to writhe in agony,", FALSE, ch, 0, victim,
		    TO_NOTVICTROOM);
	}
	// else if - can not spinal as well as critical stab. (drannak 1/7/14)
	else if (GET_CHAR_SKILL(ch, SKILL_SPINAL_TAP) &&
		 (notch_skill(ch, SKILL_SPINAL_TAP, get_property("skill.notch.offensive", 7)) ||
		  spinal_tap_threshold(ch) > number(1, 100)))
	{
		if (DEBUG)
		{
			debug("single_stab: (%s) stabbing (%s) dam (%d) weapon (%dd%d) skill (%d).",
			      GET_NAME(ch), GET_NAME(victim), dam, weapon->value[1],
			      weapon->value[2], skill);
		}
		if (melee_damage(ch, victim, dam, PHSDAM_NOREDUCE | PHSDAM_NOPOSITION, &messages) ||
		    !is_char_in_room(ch, room))
		{
			return TRUE;
		}
		spinal = TRUE;
	}
	else
	{
		if (DEBUG)
		{
			debug("single_stab: (%s) stabbing (%s) dam (%d) weapon (%dd%d) skill (%d).",
			      GET_NAME(ch), GET_NAME(victim), dam, weapon->value[1],
			      weapon->value[2], skill);
		}
		if (melee_damage(ch, victim, dam, PHSDAM_NOREDUCE | PHSDAM_NOPOSITION, &messages) ||
		    (room < 1) || !is_char_in_room(ch, room))
		{
			return TRUE;
		}
	}

	if (spinal)
	{
		act("With a swift tug you wrench the weapon free, ramming it into $N's spine!.",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("With a swift tug $n wrenches the weapon free, ramming it into you again.",
		    FALSE, ch, 0, victim, TO_VICT);
		act("With a swift tug $n wrenches the weapon free, ramming it into $N's spine!",
		    FALSE, ch, 0, victim, TO_NOTVICTROOM);
		if (melee_damage(ch, victim, spinal_tap_damage(live_rolls, ch, quarter),
				 PHSDAM_NOREDUCE | PHSDAM_NOPOSITION, &messages) ||
		    !char_in_list(ch))
		{
			return TRUE;
		}
	}

	//  Yes weapon procs on backstabs - Drannak
	if (obj_index[weapon->R_num].func.obj)
	{
		(*obj_index[weapon->R_num].func.obj)(weapon, ch, CMD_MELEE_HIT, (char *)victim);
	}

	deliver_weapon_poison(ch, victim, weapon);

	// if(is_char_in_room(ch, room) && is_char_in_room(victim, room))
	//   weapon_proc(weapon, ch, victim);
	//  No weapon procs on backstab - Jexni 3/24/11

	return !(is_char_in_room(ch, room) && is_char_in_room(victim, room));
}

/*
 * this is a dupe of do_backstab, except it lacks the code to find a
 * target when given a string, instead it is passed a P_char to backstab,
 * used by MobStartFight and AggAttack.  JAB
 */

bool backstab(P_char ch, P_char victim)
{
	// Note this DEBUG should match the one in single_stab always!
	static bool DEBUG = TRUE;

	P_obj first_w, second_w;
	int percent_chance;
	bool stabbed = FALSE;

	if (!IS_ALIVE(ch))
		return FALSE;

	// I know.. the double hack here..
	if (IS_TRUSTED(ch) && victim == NULL)
	{
		DEBUG = !DEBUG;
		single_stab(ch, NULL, NULL);
		return TRUE;
	}

	if (!SanityCheck(ch, "do_backstab"))
		return FALSE;

	if (IS_IMMOBILE(ch))
	{
		send_to_char("In your present condition, just relax and take in the sights.\r\n",
			     ch);
		return FALSE;
	}

	if (IS_ROOM(ch->in_room, ROOM_SINGLE_FILE))
	{
		send_to_char(
			"It's far too narrow in here to sneak up behind someone to stab them in the back...\r\n",
			ch);
		return false;
	}

	if (!IS_FIGHTING(ch))
	{
		if (!IS_ALIVE(victim))
		{
			send_to_char("Backstab who?\n", ch);
			return FALSE;
		}
	}

	if (GET_OPPONENT(ch))
	{
		send_to_char(
			"Sorry, you cannot concentrate enough with that fellow pounding on you.\n",
			ch);
		return FALSE;
	}

	if (!can_hit_target(ch, victim))
	{
		send_to_char("Seems that it's too crowded!\n", ch);
		return FALSE;
	}

	victim = guard_check(ch, victim);

	if ((get_takedown_size(ch) > get_takedown_size(victim) + 1) && IS_AWAKE(victim) &&
	    GET_POS(victim) > POS_KNEELING)
	{
		send_to_char("Smirk. I don't believe you could sneak behind to stab it.\n", ch);
		return FALSE;
	}

	if (get_takedown_size(ch) + 1 < get_takedown_size(victim) && GET_POS(victim) > POS_KNEELING)
	{
		send_to_char("Smirk. Backstabbing in a calf is not very effective.\n", ch);
		return FALSE;
	}

	if (should_not_kill(ch, victim))
		return FALSE;

	if (!CanDoFightMove(ch, victim))
		return FALSE;

	first_w = ch->equipment[WIELD];
	second_w = ch->equipment[SECONDARY_WEAPON];

	if (!first_w && !second_w)
	{
		send_to_char("You need to wield a weapon to even try.\n", ch);
		return FALSE;
	}

	if ((!first_w || !IS_BACKSTABBER(first_w)) && (!second_w || !IS_BACKSTABBER(second_w)))
	{
		send_to_char("Only piercing weapons can be used to backstab.\n", ch);
		return FALSE;
	}

	victim = misfire_check(ch, victim, DISALLOW_SELF | DISALLOW_BACKRANK);

	percent_chance = (int)(0.95 * GET_CHAR_SKILL(ch, SKILL_BACKSTAB));

	// Old school assassin mobs learn backstab faster.
	if (GET_CLASS(ch, CLASS_ASSASSIN))
	{
		percent_chance *= 2;
		if (percent_chance > 95)
		{
			percent_chance = 95;
		}
	}

	if (GET_C_LUK(ch) / 2 > number(0, 100))
	{
		percent_chance = (int)(percent_chance * 1.1);
	}

	if (GET_C_LUK(victim) / 2 > number(0, 100))
	{
		percent_chance = (int)(percent_chance * 0.9);
	}

	if (GET_CHAR_SKILL(ch, SKILL_ANATOMY) &&
	    5 + GET_CHAR_SKILL(ch, SKILL_ANATOMY) / 10 > number(0, 100))
	{
		percent_chance = (int)(percent_chance * 1.1);
	}
	/* Commenting out the aware stuff and having aware just be damage reduction. - Lohrr 6/27/2015
	if( IS_AFFECTED(victim, AFF_AWARE) && IS_AWAKE(victim) && !IS_DWARF(ch) )
	{
	  percent_chance = (int) (percent_chance * get_property("backstab.AwareModifier", 0.850));
	}

	if( !IS_IMMOBILE(victim) && IS_AFFECTED(victim, AFF_SKILL_AWARE) && !IS_DWARF(ch) )
	{
	  for(af_ptr = victim->affected; af_ptr; af_ptr = af_ptr->next)
	  {
	    if(af_ptr->type == SKILL_AWARENESS)
	    {
	      break;
	    }
	  }
	  // Calculated in do_awareness()
	  if(af_ptr)
	    percent_chance = (int) (percent_chance * 0.01 * (100 - af_ptr->modifier));
	  else
	    logit(LOG_DEBUG, "aware, but no affected structure");
	}
	*/

	if (IS_FIGHTING(victim) && !IS_IMMOBILE(victim))
	{
		percent_chance = (int)(percent_chance / 1.5);
	}

	if (!CAN_SEE(victim, ch))
	{
		percent_chance = (int)(percent_chance * 1.5);
	}

	if (has_innate(victim, INNATE_DRAGONMIND) && number(0, 1))
	{
		act("$N notices your lethal attempt!", FALSE, ch, 0, victim, TO_CHAR);
		act("$n tries to backstab $N but is too slow!", FALSE, ch, 0, victim, TO_NOTVICT);
		act("$n's attempt to backstab you fails as the dragon mind within takes control!",
		    FALSE, ch, 0, victim, TO_VICT);
		set_fighting(ch, victim);

		return FALSE;
	}

	percent_chance =
		(int)(percent_chance *
		      (double)BOUNDED(8, 10 + (GET_LEVEL(ch) - GET_LEVEL(victim)) / 10, 11) / 10);
	percent_chance = BOUNDED(0, percent_chance, 95);

	if (IS_IMMOBILE(victim) || GET_STAT(victim) <= STAT_SLEEPING)
	{
		percent_chance = 101;
	}

	CharWait(ch, backstab_lag());

	if (IS_PC(ch) && (!on_front_line(ch) || !on_front_line(victim)))
	{
		send_to_char("You can't seem to break the ranks!\n", ch);
		return FALSE;
	}

	if (IS_AFFECTED2(victim, AFF2_AIR_AURA))
	{
		if (backstab_air_aura_roll(live_rolls))
		{
			act("As you try to backstab $N you simply pass through $M.", FALSE, ch, 0,
			    victim, TO_CHAR);
			act("$n tries to backstab $N but simply falls through $M.", FALSE, ch, 0,
			    victim, TO_NOTVICT);
			act("$n's attempt to backstab you fails as he passes through you.", FALSE,
			    ch, 0, victim, TO_VICT);
			set_fighting(ch, victim);
			return FALSE;
		}
	}

	if (affected_by_spell(victim, SPELL_GUARDIAN_SPIRITS))
	{
		guardian_spirits_messages(ch, victim);
		percent_chance = MAX(0, percent_chance - GET_LEVEL(victim));
	}

	if (affected_by_spell(victim, SPELL_FREEDOM_OF_MOVEMENT))
	{
		percent_chance = (int)(percent_chance *
				       get_property("spell.FreedomOfMovement.backstab", 0.700));
	}

	if (DEBUG)
	{
		debug("backstab: (%s) stabbing (%s) final percentage %d", J_NAME(ch),
		      J_NAME(victim), percent_chance);
	}

	if (first_w && IS_BACKSTABBER(first_w))
	{
		stabbed = TRUE;
		if (notch_skill(ch, SKILL_BACKSTAB, get_property("skill.notch.offensive", 7)) ||
		    percent_chance > number(0, 100) || GET_STAT(victim) <= STAT_SLEEPING)
		{
			if (single_stab(ch, victim, first_w))
			{
				return TRUE;
			}
		}
		else
		{
			hit(ch, victim, first_w);
		}
	}

	if (!char_in_list(victim) || (!IS_ALIVE(victim)) || (ch->in_room != victim->in_room))
	{
		return TRUE;
	}

	if ((!stabbed || GET_CLASS(ch, CLASS_ASSASSIN) ||
	     GET_SPEC(ch, CLASS_ROGUE, SPEC_ASSASSIN)) &&
	    second_w && IS_BACKSTABBER(second_w))
	{
		if (percent_chance > number(0, 100) || GET_STAT(victim) <= STAT_SLEEPING)
		{
			if (stabbed)
			{
				if (IS_FIGHTING(victim))
				{
					stop_fighting(victim);
				}
				ch->specials.combat_tics = (int)ch->specials.base_combat_round;
			}
			else
			{
				notch_skill(ch, SKILL_BACKSTAB,
					    get_property("skill.notch.offensive", 7));
			}
			single_stab(ch, victim, second_w);
		}
		else
		{
			hit(ch, victim, second_w);
		}
	}

	// Victim's timer resets each stab.. don't bother clearing it as it will auto-clear in a few sec anyway.
	if (victim && IS_ALIVE(victim) && IS_PC(victim))
	{
		set_short_affected_by(victim, SKILL_BACKSTAB, backstab_repeat_window());
		/* Making this a short duration instead of PULSE_VIOLENCE ticks (like 20 min).
		    bzero(&af, sizeof(af));
		    af.type = SKILL_BACKSTAB;
		    af.duration = PULSE_VIOLENCE;
		    af.bitvector = AFF_AWARE;
		    affect_to_char(victim, &af);
		*/
	}

	return TRUE;
}

std::string surprise_facts(P_char ch)
{
	return fact("Chance when you start a fight",
		    std::to_string(MAX(0, GET_CHAR_SKILL(ch, SKILL_SURPRISE) - 1)) + " in 100") +
	       "  It gives you two attacks in place of your one opening attack.\n";
}

int surprise(P_char ch, P_char victim)
{
	int skl = GET_CHAR_SKILL(ch, SKILL_SURPRISE);

	if (skl > number(1, 100))
	{
		notch_skill(ch, SKILL_SURPRISE, 7.69);
		send_to_char(
			"&+GAmidst your opponents unpreparedness, you leap forth and deliver a surprise attack!&n\n",
			ch);
		hit(ch, victim, ch->equipment[PRIMARY_WEAPON]);
		if (IS_ALIVE(victim) && ch->equipment[WIELD2])
		{
			hit(ch, victim, ch->equipment[SECONDARY_WEAPON]);
		}
		else
		{
			hit(ch, victim, ch->equipment[PRIMARY_WEAPON]);
		}
		return 1;
	}
	return 0;
}

// The attacker's lag, in pulses, after trying to switch opponents.
static int switch_opponents_lag()
{
	return PULSE_VIOLENCE + 2;
}

std::string switch_opponents_facts(P_char ch)
{
	return fact("Chance to switch",
		    std::to_string(GET_CHAR_SKILL(ch, SKILL_SWITCH_OPPONENTS)) +
			    " in 101, plus your level if the new target can't") +
	       "    act or isn't standing\n" +
	       "  If your current opponent can't fight back, you switch for sure, with no lag.\n" +
	       fact("Your lag otherwise, whether or not you switch",
		    seconds(switch_opponents_lag())) +
	       "  A miss drops you out of the fight. A target with a calming innate can\n"
	       "  lower your chance.\n";
}

void attack(P_char ch, P_char victim)
{
	struct affected_type *af;
	int skl;

	if (!ch || !victim || !CanDoFightMove(ch, victim) ||
	    IS_IMMOBILE(ch)
	    // If victim & ch are at different heights, we don't attack.
	    || victim->specials.z_cord != ch->specials.z_cord)
	{
		return;
	}

	skl = GET_CHAR_SKILL(ch, SKILL_SWITCH_OPPONENTS);

	if (affected_by_spell(ch, SKILL_TAUNT))
	{
		af = get_spell_from_char(ch, SKILL_TAUNT);
		if (af && CAN_SEE(ch, (P_char)af->context) && victim != (P_char)af->context)
		{
			send_to_char("You try to switch opponents but can't!", ch);
			victim = (P_char)af->context;
		}
	}

	if (!IS_FIGHTING(ch))
	{
		/*
		 * Tracked the mud crashing down to this call here.  Will dig further but
		 * for now am taking it out.  Mud dies when you kill a mobile that is in
		 * STAT_DYING state. -RCC   if(GET_STAT(victim) > STAT_INCAP)
		 */

		act("$n suddenly attacks $N!", FALSE, ch, 0, victim, TO_NOTVICT);
		act("$n suddenly attacks YOU!", FALSE, ch, 0, victim, TO_VICT);

		victim = guard_check(ch, victim);

		mobact_rescueHandle(victim, ch);

		ch->specials.combat_tics = (int)ch->specials.base_combat_round;

		if (!IS_FIGHTING(victim))
		{
			victim->specials.combat_tics = (int)victim->specials.base_combat_round;
		}

		if (IS_ALIVE(victim) && !surprise(ch, victim))
		{
			hit(ch, victim, ch->equipment[PRIMARY_WEAPON]);
		}
		if (char_in_list(ch) && (IS_PC(ch) || (ch->following && IS_PC(ch->following))))
		{
			CharWait(ch, PULSE_VIOLENCE + 2);
		}
	}
	else if (victim == GET_OPPONENT(ch))
	{
		send_to_char("C'mon, you are doing it all the time!\n", ch);
		return;
	}
	else
	{
		if (!CanDoFightMove(GET_OPPONENT(ch), ch) || IS_IMMOBILE(ch) ||
		    GET_STAT(GET_OPPONENT(ch)) <= STAT_SLEEPING)
		{
			stop_fighting(ch);
			act("$n turns to focus $s attack on $N!", FALSE, ch, 0, victim, TO_ROOM);
			victim = guard_check(ch, victim);
			set_fighting(ch, victim);
			send_to_char(
				"Being that your target is in so poor condition, you easily switch opponents!\n",
				ch);
			return;
		}

		if (!CAN_ACT(victim) || (GET_POS(victim) != POS_STANDING))
		{
			skl += GET_LEVEL(ch);
		}

		if (has_innate(victim, INNATE_CALMING) && (number(0, 120) <= GET_LEVEL(victim) * 2))
		{
			skl -= (110 - GET_CHAR_SKILL(ch, SKILL_SWITCH_OPPONENTS));
		}

		if (notch_skill(ch, SKILL_SWITCH_OPPONENTS,
				get_property("skill.notch.switch", 10)) ||
		    skl >= number(1, 101))
		{
			stop_fighting(ch);
			act("$n turns to focus $s attack on $N!", FALSE, ch, 0, victim, TO_ROOM);
			victim = guard_check(ch, victim);
			set_fighting(ch, victim);
			send_to_char("You switch opponents!\n", ch);

			if (IS_PC(ch) || (ch->following && IS_PC(ch->following)))
			{
				CharWait(ch, switch_opponents_lag());
			}
		}
		else
		{
			send_to_char("You try to switch opponents, but you become confused!\n", ch);
			stop_fighting(ch);
			if (IS_PC(ch) || (ch->following && IS_PC(ch->following)))
			{
				CharWait(ch, switch_opponents_lag());
			}
		}
	}
}

// New function for mobs to check before attempting a kick.
// Jan08 -Lucrot
bool isKickable(P_char ch, P_char victim)
{
	if (!IS_ALIVE(ch))
	{
		return false;
	}

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim) || IS_IMMOBILE(ch) || !CanDoFightMove(ch, victim) ||
	    IS_IMMATERIAL(victim) || (ch->in_room != victim->in_room) || !HAS_FOOTING(ch) ||
	    LEGLESS(ch))
	{
		return false;
	}

	return true;
}

/* used for mob AI, checks character attributes to see if ch can even try
   to bash victim */

// Expanding this function to check basher status, race, etc... Jan08 -Lucrot
bool isBashable(P_char ch, P_char victim, bool ignoreImmaterial)
{
	int vsize, csize;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return FALSE;
	}

	if (ch->in_room != victim->in_room)
	{
		return FALSE;
	}

	// non-size checks
	if (IS_IMMATERIAL(victim) || IS_ELEMENTAL(victim) || IS_WATERFORM(victim) ||
	    (IS_IMMATERIAL(ch) && !ignoreImmaterial) || IS_DRAGON(victim) || IS_DRAGON(ch) ||
	    (IS_NPC(victim) && IS_SET(victim->specials.act, ACT_NO_BASH)) ||
	    ((ch->specials.z_cord == 0) && !HAS_FOOTING(ch)) || !CanDoFightMove(ch, victim) ||
	    GET_POS(ch) != POS_STANDING || IS_STUNNED(ch))
	{
		return FALSE;
	}

	// size checks
	csize = get_takedown_size(ch);
	vsize = get_takedown_size(victim);

	if (has_innate(victim, INNATE_HORSE_BODY) && csize <= vsize)
	{
		return FALSE;
	}

	if (vsize > csize + 1)
	{
		return FALSE;
	}

	if (vsize < csize - 1)
	{
		return FALSE;
	}
	return TRUE;
}

int good_for_skewering(P_obj obj)
{
	if ((obj->value[0] == WEAPON_AXE || obj->value[0] == WEAPON_LONGSWORD ||
	     obj->value[0] == WEAPON_2HANDSWORD || obj->value[0] == WEAPON_POLEARM ||
	     obj->value[0] == WEAPON_SPEAR || obj->value[0] == WEAPON_LANCE ||
	     obj->value[0] == WEAPON_TRIDENT || obj->value[0] == WEAPON_SICKLE ||
	     obj->value[0] == WEAPON_HORN) &&
	    IS_SET(obj->extra_flags, ITEM_TWOHANDS))
	{
		return 1;
	}
	else
	{
		return 0;
	}
}

// Damage from a successful bash, before melee_damage applies the target's defenses.
static int bash_damage(const Rolls &rolls, P_char ch)
{
	int dmg = 1 + str_app[STAT_INDEX(GET_C_STR(ch))].todam;
	if (ch->equipment[WEAR_SHIELD])
	{
		dmg += rolls.number(0, 4) + ch->equipment[WEAR_SHIELD]->weight / 2;
		if (strstr(ch->equipment[WEAR_SHIELD]->name, "spiked"))
		{
			dmg *= 2;
		}
	}
	return MAX(1, dmg);
}

// The basher's lag after a hit, in pulses.
static int bash_hit_lag()
{
	return PULSE_VIOLENCE * 2;
}

// The basher's lag after a miss, in pulses; longer when the miss leaves them prone.
static int bash_miss_lag(bool prone)
{
	return prone ? PULSE_VIOLENCE * 3 : PULSE_VIOLENCE * 2;
}

// The basher's lag, in pulses, when the target is already down and the basher falls instead.
static int bash_target_down_lag()
{
	return (int)(PULSE_VIOLENCE * 2.000);
}

// The basher's lag, in pulses, when the target is too big or too small to bash: two or more
// takedown sizes away, or a centaur or drider at least the basher's size (any target, for
// a quadruped basher).
static int bash_size_lag()
{
	return (int)(PULSE_VIOLENCE * 0.500);
}

// The basher's lag, in pulses, when takedown_check() foils the bash: a grapple, an immaterial
// target, displacement, a harpy, air aura, an earth or water elemental, an NPC dragon, or an
// NPC that can't be bashed.
static int bash_takedown_penalty_lag()
{
	return PULSE_VIOLENCE * 2;
}

// The bashed target's lag, in pulses. bash() only reaches a hit on a standing target:
// a target already down ends the bash first, and guard_check() never swaps in a guard
// who is down.
static int bash_target_lag(P_char ch, bool target_standing)
{
	if (!target_standing)
		return PULSE_VIOLENCE * 1;
	if (GET_SPEC(ch, CLASS_WARRIOR, SPEC_GUARDIAN))
		return (int)(PULSE_VIOLENCE * 2.5);
	return (int)(PULSE_VIOLENCE * 2);
}

// How far a shieldless bash scales the chance threshold, in percent; at least a fifth.
static float shieldless_bash_modifier(P_char ch)
{
	float modifier = GET_CHAR_SKILL(ch, SKILL_SHIELDLESS_BASH);
	if (modifier < 20.0)
	{
		modifier = 20.0;
	}
	return modifier;
}

std::string shieldless_bash_facts(P_char ch)
{
	return fact("Bash chance threshold with no shield",
		    std::to_string((int)shieldless_bash_modifier(ch)) + "% of normal") +
	       "  With no rating, a paladin or anti-paladin uses a holy sword's weight instead.\n";
}

// A skewer on a downed target: the rating needed against 1-100, and the damage and lags.
static int skewer_down_threshold(int skewer)
{
	return skewer / 3;
}

static int skewer_off_target_rating(int skewer)
{
	return (int)(skewer * get_property("skill.skewer.OffTarget.Penalty", 0.500));
}

static int skewer_down_damage(const Rolls &rolls)
{
	return rolls.dice(20, 10);
}

static int skewer_down_lag()
{
	return (int)(PULSE_VIOLENCE * 1.75);
}

static int skewer_down_target_lag()
{
	return PULSE_VIOLENCE;
}

// A skewer after a successful bash: the rating needed against 0-100, and the damage and lags.
static int skewer_bash_threshold(P_char ch)
{
	return GET_CHAR_SKILL(ch, SKILL_SKEWER) / 2;
}

static int skewer_bash_damage(const Rolls &rolls)
{
	return rolls.dice(45, 10);
}

static int skewer_bash_lag()
{
	return PULSE_VIOLENCE * 2;
}

std::string skewer_facts(P_char ch)
{
	const int rating = GET_CHAR_SKILL(ch, SKILL_SKEWER);
	return fact("Chance after a bash lands",
		    std::to_string(skewer_bash_threshold(ch)) + " in 101") +
	       fact("  Damage",
		    show({ skewer_bash_damage(lowest_rolls), skewer_bash_damage(highest_rolls) })) +
	       fact("  Your lag and the target's", seconds(skewer_bash_lag()) + " each") +
	       fact("Chance when you bash a downed target",
		    std::to_string(MAX(0, skewer_down_threshold(rating) - 1)) + " in 100, or " +
			    std::to_string(
				    MAX(0, skewer_down_threshold(skewer_off_target_rating(rating)) -
						   1)) +
			    " off target") +
	       fact("  Damage",
		    show({ skewer_down_damage(lowest_rolls), skewer_down_damage(highest_rolls) })) +
	       fact("  Your lag", seconds(skewer_down_lag())) +
	       fact("  Target's lag", seconds(skewer_down_target_lag())) +
	       "  Needs a weapon that can skewer. The target's defenses apply to the damage.\n";
}

std::string bash_facts(P_char ch)
{
	return fact("Damage on a hit",
		    show({ bash_damage(lowest_rolls, ch), bash_damage(highest_rolls, ch) }) +
			    " with your strength and " +
			    (ch->equipment[WEAR_SHIELD] ? "shield" : "no shield")) +
	       fact("Your lag on a hit", seconds(bash_hit_lag())) +
	       fact("Your lag on a miss", seconds(bash_miss_lag(false)) + ", or " +
						  seconds(bash_miss_lag(true)) +
						  " if you fall prone") +
	       fact("Your lag if the target is already down", seconds(bash_target_down_lag())) +
	       fact("Your lag if the target is asleep",
		    seconds(takedown_sleeping_target_lag()) + " (you attack it instead)") +
	       fact("Your lag if the target evades", seconds(takedown_evade_lag())) +
	       fact("Your lag if the target is 2 or more sizes bigger or smaller",
		    seconds(bash_size_lag())) +
	       (GET_RACE(ch) == RACE_QUADRUPED ?
			"    (also any target at least your size)\n" :
			"    (also a centaur or drider at least your size)\n") +
	       fact("Your lag if the target foils the takedown",
		    seconds(bash_takedown_penalty_lag())) +
	       "    (grapple, displacement, air aura, an immaterial or harpy target, an earth\n"
	       "    or water elemental, an NPC dragon or an NPC that can't be bashed)\n" +
	       fact("Target's lag", seconds(bash_target_lag(ch, true))) +
	       "  The target's defenses apply to the damage after.\n";
}

void bash(P_char ch, P_char victim, bool _debug)
{
	static bool DEBUG = TRUE;
	float percent_chance, modifier;
	int dmg, ch_size, vict_size, rolled;
	int skewer = GET_CHAR_SKILL(ch, SKILL_SKEWER);
	P_obj weap = ch->equipment[WIELD];

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		if (ch && IS_TRUSTED(ch) && _debug)
		{
			DEBUG = !DEBUG;
			debug("bash: DEBUG turned %s.", DEBUG ? "ON" : "OFF");
		}
		return;
	}

	if (affected_by_spell(ch, SKILL_BASH))
	{
		send_to_char("You haven't reoriented yourself yet enough for another bash!\n", ch);
		return;
	}

	if (GET_CHAR_SKILL(ch, SKILL_BASH) < 1)
	{
		send_to_char("You don't know how to bash.\n", ch);
		return;
	}

	// Allowing NPC mentals to bash.
	if (IS_AFFECTED2(ch, AFF2_AIR_AURA) || affected_by_spell(ch, SPELL_ETHEREAL_FORM) ||
	    ((GET_RACE(ch) == RACE_F_ELEMENTAL || GET_RACE(ch) == RACE_A_ELEMENTAL) && !IS_NPC(ch)))
	{
		send_to_char("You couldnt bash in your current form if you wanted to.\r\n", ch);
		return;
	}

	if (get_linked_char(ch, LNK_RIDING) != NULL)
	{
		send_to_char("You cannot do that while riding! Try trample instead.\n", ch);
		return;
	}

	if (!CanDoFightMove(ch, victim))
	{
		return;
	}

	if (IS_TRUSTED(victim) && IS_SET(victim->specials.act, PLR_AGGIMMUNE))
	{
		send_to_char("Bash a god?  I think not.", ch);
		return;
	}

	appear(ch);

	if (GET_POS(victim) != POS_STANDING)
	{
		act("As $N avoids your bash, you topple over and fall to the ground.", FALSE, ch, 0,
		    victim, TO_CHAR);
		act("You dodge a bash from $n, who loses $s balance and falls.", FALSE, ch, 0,
		    victim, TO_VICT);
		act("$N avoids being bashed by $n, who loses $s balance and falls.", FALSE, ch, 0,
		    victim, TO_NOTVICT);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		update_group_vitals(ch);
		gmcp_char_vitals(ch);
		CharWait(ch, bash_target_down_lag());
		return;
	}

	victim = guard_check(ch, victim);

	vict_size = get_takedown_size(victim);
	ch_size = get_takedown_size(ch);

	/* lets make it a bit trickier to bash an ogre unless you're bigger
	   Lets comment this out for the wipe since they're huge again -Zion 12/24/07
	if((GET_RACE(victim) == RACE_OGRE) && ch_size < vict_size)
	{
	  if(number(0, 20) && (GET_POS(victim) == POS_STANDING))
	  {
	     act("$n makes an attempt to bash $N, but merely knocks $E slightly off balance...", FALSE, ch, 0, victim, TO_NOTVICT);
	     act("$n makes an attempt to bash you, but merely causes you to momentarily to lose footing...", FALSE, ch, 0, victim, TO_VICT);
	     act("You attempt to bash $N, but you merely knock them off balance...", FALSE, ch, 0, victim, TO_CHAR);
	  SET_POS(victim, POS_SITTING + GET_STAT(victim));
	  set_short_affected_by(ch, SKILL_BASH, (int) (2.8 * PULSE_VIOLENCE));
	  engage(ch, victim);
	  return;
	  }
	  else if(GET_POS(victim) == POS_STANDING)
	  {
	    act("$n makes a futile attempt to bash $N, but $E is simply immovable.", FALSE, ch, 0, victim, TO_NOTVICT);
	    act("$n makes a futile attempt to bash you, but you are simply immovable.", FALSE, ch, 0, victim, TO_VICT);
	    act("You attempt to bash $N, but $E is simply too huge for you to move!", FALSE, ch, 0, victim, TO_CHAR);
	  SET_POS(ch, POS_SITTING + GET_STAT(ch));
	  return;
	  }
	}*/
	/* you must be size more than size down or same size of centaur/drider to try bashing */
	if (ch_size < vict_size - 1 ||
	    ((has_innate(victim, INNATE_HORSE_BODY) || has_innate(victim, INNATE_SPIDER_BODY) ||
	      GET_RACE(ch) == RACE_QUADRUPED) &&
	     ch_size <= vict_size))
	{
		act("$n makes a futile attempt to bash $N, but $E is simply immovable.", FALSE, ch,
		    0, victim, TO_NOTVICT);
		act("$n makes a futile attempt to bash you, but you are simply immovable.", FALSE,
		    ch, 0, victim, TO_VICT);
		act("You attempt to bash $N, but $E is simply too huge for you to move!", FALSE, ch,
		    0, victim, TO_CHAR);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		update_group_vitals(ch);
		gmcp_char_vitals(ch);
		CharWait(ch, bash_size_lag());
		return;
	}

	if (ch_size > vict_size + 1)
	{
		act("$n topples over $mself as $e tries to bash $N.", FALSE, ch, 0, victim,
		    TO_NOTVICT);
		act("$n topples over $mself as $e tries to bash you.", FALSE, ch, 0, victim,
		    TO_VICT);
		act("You topple over yourself as you try to bash $N - $E's just too small!\n",
		    FALSE, ch, 0, victim, TO_CHAR);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		update_group_vitals(ch);
		gmcp_char_vitals(ch);
		CharWait(ch, bash_size_lag());
		return;
	}

	percent_chance = GET_CHAR_SKILL(ch, SKILL_BASH); // Base chance

	if (!on_front_line(victim))
	{
		percent_chance /= 2.0;
	}

	if (IS_HUMANOID(ch))
	{
		// Note: IS_PAL..SWORD checks to make sure weapon exists.
		if (!(ch->equipment[WEAR_SHIELD]) &&
		    (GET_CHAR_SKILL(ch, SKILL_SHIELDLESS_BASH) < 1) &&
		    (GET_CLASS(ch, CLASS_PALADIN | CLASS_ANTIPALADIN) && IS_PALADIN_SWORD(weap)))
		{
			// Artifacts are often low weight to allow all to use -  Jexni 6/7/08
			if (IS_ARTIFACT(weap))
			{
				percent_chance += 7.0;
			}
			else
			{
				percent_chance += weap->weight / 2.0;
			}
		}
		else
		{
			if (ch->equipment[WEAR_SHIELD])
			{
				// Heaviest shield in game atm is church door at 30 lbs -> 16.67 % increase.
				percent_chance += (ch->equipment[WEAR_SHIELD]->weight / 1.8);
			}
			else
			{
				notch_skill(ch, SKILL_SHIELDLESS_BASH,
					    get_property("skill.notch.offensive", 7));
				// Minimum of 4/5 reduction.  Max no reduction.
				modifier = shieldless_bash_modifier(ch);
				percent_chance *= modifier / 100.0;

				if (GET_CHAR_SKILL(ch, SKILL_SHIELDLESS_BASH) < 1)
				{
					send_to_char(
						"Bashing without a shield is tough, but you try anyway...\n",
						ch);
					//        debug("bash: (%s) shieldless bashing (%s) percentage (%d).", GET_NAME(ch), GET_NAME(victim), percent_chance);
				}
			}
		}
	}

	if (skewer > 0 && IS_FIGHTING(ch) && GET_OPPONENT(victim) != ch &&
	    GET_OPPONENT(ch) != victim)
	{
		skewer = skewer_off_target_rating(skewer);
	}

	if (skewer > 0 && GET_POS(victim) != POS_STANDING && weap && good_for_skewering(weap) &&
	    (notch_skill(ch, SKILL_SKEWER, get_property("skill.notch.offensive", 7)) ||
	     skewer_down_threshold(skewer) > number(1, 100)))
	{
		act("$n grins as $e skewers you with $s $q.", FALSE, ch, weap, victim, TO_VICT);
		act("You dive at $N skewering $M with your $q.", FALSE, ch, weap, victim, TO_CHAR);
		act("$n dives at $N skewering $M with $s $q.", FALSE, ch, weap, victim, TO_NOTVICT);

		if (melee_damage(ch, victim, skewer_down_damage(live_rolls), 0, 0) == DAM_NONEDEAD)
		{
			CharWait(victim, skewer_down_target_lag());
		}

		CharWait(ch, skewer_down_lag());

		return;
	}

	if (!IS_PC_PET(ch))
	{
		/* Old code uses a modifier for attributes; we're going to use a 30% * 100 base.
		modifier = 1 + ((GET_C_STR(ch) + GET_C_DEX(ch))/2 - GET_C_AGI(victim)) / 50.0;
		percent_chance *= modifier;
		*/
		// 70% comes from skill, 30% from stats.
		// On avg, (str 100, dex 100 and agi 100) this will contribute 50% or .15 towards the total bash %.
		// Thris don't get a bonus for their dex.
		modifier = 100 + GET_C_STR(ch) / 2.0 +
			   ((IS_THRIKREEN(ch) && GET_C_DEX(ch) > 100) ? 100 : GET_C_DEX(ch)) -
			   GET_C_AGI(victim);
		// Bind the modifier between subtracting 10% (-3% of total chance) to adding 10% (+33% of total chance).
		modifier = (modifier < -10.0) ? -10.0 : (modifier < 110.0) ? modifier : 110.0;
		percent_chance = .70 * percent_chance + .30 * modifier;
		//    debug("bash: (%s) bashing (%s) str/agi percentage (%d) mod (%f).", GET_NAME(ch), GET_NAME(victim), percent_chance, modifier);
	}
	else if (GET_RACE(ch) == RACE_E_ELEMENTAL ||
		 GET_RACE(ch) ==
			 RACE_W_ELEMENTAL) // Water and Earth Elementals get a 20% bonus to bash.
	{
		percent_chance += 20;
	}
	else
	{
		percent_chance -= 10;
	}

	// If they are fighting something and try to bash something else
	if (IS_FIGHTING(ch) && GET_OPPONENT(victim) != ch && GET_OPPONENT(ch) != victim)
	{
		send_to_char(
			"You are fighting something else! Nevertheless, you attempt the bash...\n",
			ch);
		percent_chance = (int)(percent_chance * 0.7);
	}

	modifier = (modifier < .80) ? .80 : (modifier < 1.1) ? modifier : 1.1;
	modifier = 1.0 + (GET_LEVEL(ch) - GET_LEVEL(victim)) / 50.0;
	if (modifier < .01)
	{
		modifier = .01;
	}
	percent_chance *= modifier;
	//  debug("bash: (%s) bashing (%s) lvl percentage (%d) mod (%f).", GET_NAME(ch), GET_NAME(victim), percent_chance, modifier);

	bool bigger_victim = FALSE;
	if (vict_size > ch_size ||
	    ((has_innate(victim, INNATE_HORSE_BODY) || has_innate(victim, INNATE_SPIDER_BODY) ||
	      GET_RACE(ch) == RACE_QUADRUPED) &&
	     ch_size == vict_size))
	{
		bigger_victim = TRUE;
	}

	if (bigger_victim)
	{
		percent_chance = percent_chance * 0.70;
	}

	if (IS_AFFECTED(victim, AFF_AWARE))
	{
		percent_chance = percent_chance * 0.93;
	}
	//  debug("bash: (%s) bashing (%s) aware/size percentage (%d).", GET_NAME(ch), GET_NAME(victim), percent_chance);

	// Yes, Thri-Kreen get a penalty % to bash 'cause they're different species and light and all.
	if (IS_THRIKREEN(ch))
	{
		percent_chance *= get_property("skill.bash.ThriKreen_Modifier", .70);
	}

	percent_chance =
		takedown_check(ch, victim, percent_chance, SKILL_BASH,
			       TAKEDOWN_ALL ^ TAKEDOWN_AGI_CHECK ^ TAKEDOWN_VICTIM_BACK_RANK);

	if (percent_chance == TAKEDOWN_CANCELLED)
	{
		return;
	}
	else if (percent_chance == TAKEDOWN_PENALTY)
	{
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		update_group_vitals(ch);
		gmcp_char_vitals(ch);
		CharWait(ch, bash_takedown_penalty_lag());
		return;
	}

	//  debug("bash: (%s) bashing (%s) takedown check percentage (%d).", GET_NAME(ch), GET_NAME(victim), percent_chance);

	if (IS_PC_PET(ch) && IS_ELEMENTAL(ch) && get_linked_char(ch, LNK_PET) &&
	    get_linked_char(ch, LNK_PET)->in_room == ch->in_room)
	{
		int NumFol =
			CountNumGreaterElementalFollowersInSameRoom(get_linked_char(ch, LNK_PET));

		if (NumFol > 1)
		{
			percent_chance /= NumFol;
		}
		// debug("Bash - elemental pet: (%d) chance versus (%s) numfol (%d).",percent_chance, GET_NAME(ch), NumFol);
	}

	percent_chance = BOUNDED(1, percent_chance, 99);

	/*
	 * final check to smarten mobs up a little, if odds are too low don't
	 * try very often.  JAB
	 * This comment is bizarre as below is just a standing check and % -> 0 .. nothing about AI here?
	 */
	// This needs to be after the BOUNDED( 1 .. 99 ) so we always fail on !standing.
	if (GET_POS(victim) != POS_STANDING)
	{
		percent_chance = 0;
	}

	rolled = number(1, 100);
	if (DEBUG)
	{
		debug("bash: (%s) bashing (%s) final percentage (%2.0f).", GET_NAME(ch),
		      GET_NAME(victim), percent_chance);
	}

	if (!notch_skill(ch, SKILL_BASH, get_property("skill.notch.offensive", 7)) &&
	    percent_chance < rolled)
	{
		if (bigger_victim && number(1, 2) == 1)
		{
			act("As $N withstands your bash, you bounce back and fall to the ground.",
			    FALSE, ch, 0, victim, TO_CHAR);
			act("You withstand a bash from $n, who bounces back and falls.", FALSE, ch,
			    0, victim, TO_VICT);
			act("$N withstands a bash from $n, who bounces back and falls.", FALSE, ch,
			    0, victim, TO_NOTVICT);
		}
		else
		{
			act("As $N avoids your bash, you topple over and fall to the ground.",
			    FALSE, ch, 0, victim, TO_CHAR);
			act("You dodge a bash from $n, who loses $s balance and falls.", FALSE, ch,
			    0, victim, TO_VICT);
			act("$N avoids being bashed by $n, who loses $s balance and falls.", FALSE,
			    ch, 0, victim, TO_NOTVICT);
		}

		/*
		 * mostly to knees, but can wind up prone too
		 */
		engage(ch, victim);
		if (rolled > (percent_chance * 3))
		{
			SET_POS(ch, POS_PRONE + GET_STAT(ch));
			CharWait(ch, bash_miss_lag(true));
		}
		else
		{
			SET_POS(ch, POS_KNEELING + GET_STAT(ch));
			CharWait(ch, bash_miss_lag(false));
		}
		update_group_vitals(ch);
		gmcp_char_vitals(ch);
	}
	else
	{
		dmg = bash_damage(live_rolls, ch);
		CharWait(ch, bash_hit_lag());
		CharWait(victim, bash_target_lag(ch, GET_POS(victim) == POS_STANDING));

		if (melee_damage(ch, victim, dmg, PHSDAM_TOUCH, 0) == DAM_NONEDEAD)
		{
			// act("Your bash knocks $N to the ground!", FALSE, ch, 0, victim, TO_CHAR);
			if (GET_SPEC(ch, CLASS_WARRIOR, SPEC_GUARDIAN))
			{
				act("Your skillful bash knocks $N to the ground!", FALSE, ch, 0,
				    victim, TO_CHAR);
				act("You are knocked to the ground by $n's skillful bash!", FALSE,
				    ch, 0, victim, TO_VICT);
				act("$N is knocked to the ground by $n's skillful bash!", FALSE, ch,
				    0, victim, TO_NOTVICT);
				set_short_affected_by(ch, SKILL_BASH, (int)(2.8 * PULSE_VIOLENCE));
			}
			else if (!LEGLESS(ch))
			{
				act("Your bash knocks $N to the ground!", FALSE, ch, 0, victim,
				    TO_CHAR);
				act("You are knocked to the ground by $n's mighty bash!", FALSE, ch,
				    0, victim, TO_VICT);
				act("$N is knocked to the ground by $n's mighty bash!", FALSE, ch,
				    0, victim, TO_NOTVICT);
				set_short_affected_by(ch, SKILL_BASH, (int)(2.8 * PULSE_VIOLENCE));
			}
			else
			{
				act("Your bash knocks $N to the ground!", FALSE, ch, 0, victim,
				    TO_CHAR);
				act("$n's mass &+rslams&n into you, knocking you to the &+yground!&n",
				    FALSE, ch, 0, victim, TO_VICT);
				act("$n's mass &+rslams&n into $N, knocking $M to the &+yground!&n",
				    FALSE, ch, 0, victim, TO_NOTVICT);
				set_short_affected_by(ch, SKILL_BASH, (int)(1.5 * PULSE_VIOLENCE));
			}

			SET_POS(victim, POS_SITTING + GET_STAT(victim));
			update_pos(victim);
			update_group_vitals(victim);
			gmcp_char_vitals(victim);
		}

		if (!IS_ALIVE(ch))
		{
			return;
		}

		if (GET_CHAR_SKILL(ch, SKILL_SKEWER) > 0 && weap && good_for_skewering(weap))
		{
			percent_chance = skewer_bash_threshold(ch);
			if (notch_skill(ch, SKILL_SKEWER,
					get_property("skill.notch.offensive", 7)) ||
			    percent_chance > number(0, 100))
			{
				if (!IS_ALIVE(victim))
				{
					act("$n grins as $e pierces the lifeless body again and again with $s $p.",
					    FALSE, ch, ch->equipment[WIELD], 0, TO_ROOM);
					act("You dive your $q right through the lifeless body of your opponent.",
					    FALSE, ch, ch->equipment[WIELD], 0, TO_CHAR);
				}
				else
				{
					act("$n grins as $e skewers you with $s $q.", FALSE, ch,
					    weap, victim, TO_VICT);
					act("You dive at $N skewering $M with your $q.", FALSE, ch,
					    weap, victim, TO_CHAR);
					act("$n dives at $N skewering $M with $s $q.", FALSE, ch,
					    weap, victim, TO_NOTVICT);
					// codemod dice(20, 10) - changed to make skewer do more damage instead of lag user longer
					if (melee_damage(ch, victim, skewer_bash_damage(live_rolls),
							 0, 0) == DAM_NONEDEAD)
					{
						CharWait(victim, skewer_bash_lag());
					}
					if (IS_ALIVE(ch))
					{
						CharWait(ch, skewer_bash_lag());
					}
				}
			}
		}

		if (!IS_ALIVE(ch) || !IS_ALIVE(victim) || (victim->in_room != ch->in_room))
		{
			return;
		}

		engage(ch, victim);
	}

#ifdef REALTIME_COMBAT
	if (GET_OPPONENT(ch) && !ch->specials.combat)
	{
		stop_fighting(ch);
		set_fighting(ch, victim);
	}
#endif
}

void do_parlay(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim;

	victim = ParseTarget(ch, argument);

	parlay(ch, victim);
}

// The parlay score: rating plus level, before an elite target.
static int parlay_score(int rating, int level)
{
	return rating + level;
}

// What an elite target takes off the score.
static int parlay_elite_penalty(const Rolls &rolls)
{
	return rolls.number(50, 150);
}

// The rolls the score must beat to make the target flee, and then to end the fight.
static int parlay_flee_roll(const Rolls &rolls)
{
	return rolls.number(85, 200);
}

static int parlay_truce_roll(const Rolls &rolls)
{
	return rolls.number(1, 100);
}

// The parlayer's lag, in pulses, when it works and when it doesn't.
static int parlay_success_lag()
{
	return PULSE_VIOLENCE * 2;
}

static int parlay_failure_lag()
{
	return PULSE_VIOLENCE;
}

std::string parlay_facts(P_char ch)
{
	return fact("Your score",
		    std::to_string(parlay_score(GET_CHAR_SKILL(ch, SKILL_PARLAY), GET_LEVEL(ch))) +
			    " (rating plus level; luck can raise the rating)") +
	       fact("The target flees if a roll is below it",
		    show({ parlay_flee_roll(lowest_rolls), parlay_flee_roll(highest_rolls) })) +
	       fact("Otherwise the fight ends if a roll is below it",
		    show({ parlay_truce_roll(lowest_rolls), parlay_truce_roll(highest_rolls) })) +
	       fact("An elite target takes off the score",
		    show({ parlay_elite_penalty(lowest_rolls),
			   parlay_elite_penalty(highest_rolls) })) +
	       fact("Your lag", seconds(parlay_success_lag()) + " if it works, " +
					seconds(parlay_failure_lag()) + " if not") +
	       "  It only works on a target that is fighting.\n";
}

void parlay(P_char ch, P_char victim)
{
	int skl_lvl;

	if (!ch || !victim)
	{
		send_to_char("&+WYou parlay with the wind, but it seems unresponsive.&n\n", ch);
		return;
	}

	skl_lvl = GET_CHAR_SKILL(ch, SKILL_PARLAY);

	if (skl_lvl == 0)
	{
		send_to_char(
			"&+WYou attempt to speak of &+Gharmony &+Wand &+Ypeace&+W...but everyone looks at you like an idiot.&n\n",
			ch);
		return;
	}

	if (GET_C_LUK(ch) / 2 > number(0, 100))
	{
		skl_lvl = (int)(skl_lvl * 1.1);
	}

	skl_lvl = parlay_score(skl_lvl, GET_LEVEL(ch));

	if (IS_ELITE(victim))
		skl_lvl -= parlay_elite_penalty(live_rolls);

	if (GET_OPPONENT(victim))
	{
		if (parlay_flee_roll(live_rolls) < skl_lvl)
		{
			stop_fighting(victim);
			stop_fighting(ch);
			clearMemory(victim);

			act("&+W$n speaks of &+Gharmony&+W and &+Ypeace&+W, convincing $N&+W to lay down their arms... &+Ckumbaya!&n",
			    FALSE, ch, 0, victim, TO_NOTVICT);
			act("&+WAfter listening to $n, you are convinced that fighting doesn't solve anything. Kumbaya my friend..&n",
			    FALSE, ch, 0, victim, TO_VICT);
			act("&+WYou convince $N&+W to lay down their arms!&n", FALSE, ch, 0, victim,
			    TO_CHAR);
			do_flee(victim, 0, 2);
			CharWait(ch, parlay_success_lag());
			return;
		}
		else if (skl_lvl > parlay_truce_roll(live_rolls))
		{
			act("&+WYou convince $N &+Wstop the duel with you, in the name of &+Ypeace!&n",
			    FALSE, ch, 0, victim, TO_CHAR);
			act("&+W$n&+W convinces you that your quarrel with $m is futile!&n", FALSE,
			    ch, 0, victim, TO_VICT);
			act("&+W$n convinces $N &+Wto give up the duel with $m!", FALSE, ch, 0,
			    victim, TO_NOTVICT);

			stop_fighting(victim);
			stop_fighting(ch);
			forget(victim, ch);
			CharWait(ch, parlay_success_lag());
			return;
		}
		else
		{
			send_to_char(
				"&+rYou fail to spread the message of &+Wpeace&+r and &+Gharmony&+r.&n\n",
				ch);
			notch_skill(ch, SKILL_PARLAY, 10);
			CharWait(ch, parlay_failure_lag());
			return;
		}
	}
}

// The tackler's lag, in pulses, by what happened.
static int tackle_body_lag()
{
	return PULSE_VIOLENCE * 1;
}

static int tackle_size_lag()
{
	return (int)(PULSE_VIOLENCE * 0.5);
}

static int tackle_lag()
{
	return PULSE_VIOLENCE * 2;
}

static int tackle_prone_lag()
{
	return PULSE_VIOLENCE * 3;
}

// How long, in pulses, a tackle keeps the tackler from the next takedown.
static int tackle_rest()
{
	return (int)(3.5 * PULSE_VIOLENCE);
}

// What a tackled target adds to its combat pulse, and for how many ticks.
static int tackle_combat_pulse()
{
	return 4;
}

static int tackle_combat_pulse_duration()
{
	return 0;
}

// How long, in pulses, a tackler who lands badly can be stunned.
static int tackle_self_stun()
{
	return PULSE_VIOLENCE;
}

std::string tackle_facts(P_char)
{
	return fact("Your lag and the target's on a hit", seconds(tackle_lag()) + " each") +
	       fact("Your lag on a miss", seconds(tackle_lag()) + ", or " +
						  seconds(tackle_prone_lag()) +
						  " if you land prone") +
	       fact("Stun if you land prone and fail a constitution roll",
		    seconds(tackle_self_stun())) +
	       fact("Your lag if the target is more than a size off", seconds(tackle_size_lag())) +
	       fact("Your lag if a centaur or drider is at least your size",
		    seconds(tackle_body_lag())) +
	       fact("Your lag if the target is asleep",
		    seconds(takedown_sleeping_target_lag()) + " (you attack it instead)") +
	       fact("Your lag if the target evades", seconds(takedown_evade_lag())) +
	       fact("Before your next takedown after a hit", seconds(tackle_rest())) +
	       fact("Target's combat pulse", "+" + std::to_string(tackle_combat_pulse()) + ", " +
						     game_hours(tackle_combat_pulse_duration())) +
	       "  Centaurs, quadrupeds and driders can't tackle. Tackling outside a fight\n"
	       "  can carry you both out of the room, 1 time in 5.\n";
}

void do_tackle(P_char ch, char *arg, int /*cmd*/)
{
	P_char vict = NULL, mount;
	struct affected_type af;
	int door, percent_chance;

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (IS_CENTAUR(ch) || GET_RACE(ch) == RACE_QUADRUPED || GET_RACE(ch) == RACE_DRIDER)
	{
		send_to_char("You rear up and .. wait, how does you tackle?!\n", ch);
		return;
	}

	if (!IS_FIGHTING(ch))
	{
		vict = ParseTarget(ch, arg);
		if (!vict)
		{
			send_to_char("Tackle who?\n", ch);
			return;
		}
	}
	else
	{
		vict = GET_OPPONENT(ch);
		if (!vict)
		{
			stop_fighting(ch);
			return;
		}
	}

	if (GET_CHAR_SKILL(ch, SKILL_TACKLE) < 1)
	{
		send_to_char("You really dont know how.\n", ch);
		return;
	}

	if (!CanDoFightMove(ch, vict))
		return;

	appear(ch);

	if ((has_innate(vict, INNATE_HORSE_BODY) || has_innate(vict, INNATE_SPIDER_BODY) ||
	     GET_RACE(ch) == RACE_QUADRUPED) &&
	    (get_takedown_size(ch) <= get_takedown_size(vict)))
	{
		act("$n makes a futile attempt to tackle $N, but $E is simply immovable.", FALSE,
		    ch, 0, vict, TO_NOTVICT);
		act("$n makes a futile attempt to tackle you, but you are simply immovable.", FALSE,
		    ch, 0, vict, TO_VICT);
		act("&+WThat damn half-horse half-man is too hefty to tackle!", FALSE, ch, 0, vict,
		    TO_CHAR);

		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		CharWait(ch, tackle_body_lag());

		if (!IS_FIGHTING(ch))
			set_fighting(ch, vict);

		return;
	}

	if (get_takedown_size(vict) < (get_takedown_size(ch) - 1))
	{
		send_to_char("No way, they are way too small!\n", ch);
		CharWait(ch, tackle_size_lag());
		return;
	}

	if (get_takedown_size(vict) > (get_takedown_size(ch) + 1))
	{
		send_to_char("No way, they are way too big!\n", ch);
		CharWait(ch, tackle_size_lag());
		return;
	}

	if (affected_by_spell(ch, SKILL_BASH))
	{
		send_to_char("You haven't yet reoriented yourself enough!\n", ch);
		return;
	}

	percent_chance = (int)BOUNDED(20, GET_CHAR_SKILL(ch, SKILL_TACKLE), 100);

	// percent_chance = (int) (percent_chance * ((double) BOUNDED(8, 10 + (GET_LEVEL(ch) - GET_LEVEL(vict)) / 10, 12)) / 10);

	if (affected_by_spell(vict, SKILL_TACKLE))
	{
		send_to_char("They are aware of deviousness but you try anyways!\n", ch);
		percent_chance = (int)(percent_chance * 0.95);
	}

	if (!on_front_line(ch) || // Not currently being used
	    !on_front_line(vict))
	{
		send_to_char("With an awesome aerial maneuver you manage to reach the target.\n",
			     ch);
		percent_chance = (int)(percent_chance * 0.5);
	}

	if (GET_C_LUK(ch) / 2 > number(1, 100))
		percent_chance = (int)(percent_chance * 1.1);

	if (GET_C_LUK(vict) / 2 > number(1, 100))
		percent_chance = (int)(percent_chance * 0.90);

	if (IS_AFFECTED(vict, AFF_AWARE))
	{
		percent_chance = (int)(percent_chance * 0.93);

		if (GET_CHAR_SKILL(ch, SKILL_TACKLE) > number(1, 110) &&
		    number(0, 4) == 4) // Easter egg message
		{
			send_to_char(
				"Your target seems to have a heightened sense of awareness...\n",
				ch);
		}
	}

	percent_chance = takedown_check(ch, vict, percent_chance, SKILL_TACKLE,
					TAKEDOWN_ALL ^ TAKEDOWN_FOOTING);

	if (percent_chance == TAKEDOWN_CANCELLED)
		return;

	if (percent_chance == TAKEDOWN_PENALTY)
		percent_chance = 0;
	else
		percent_chance = BOUNDED(5, percent_chance, 90);

	if (IS_PC(ch))
		debug("(%s) tackling (%s) with percentage of (%d).", GET_NAME(ch), GET_NAME(vict),
		      percent_chance);

	if (IS_NPC(ch) && IS_ELITE(ch) && !IS_PC_PET(ch))
		percent_chance = 100;

	if ((notch_skill(ch, SKILL_TACKLE, get_property("skill.notch.offensive", 7)) ||
	     number(1, 100) < percent_chance || IS_TRUSTED(ch)) &&
	    GET_POS(vict) == POS_STANDING)
	{
		if (!IS_TRUSTED(ch))
			set_short_affected_by(ch, SKILL_BASH, tackle_rest());

		if (!IS_FIGHTING(ch) && !number(0, 4) && GET_POS(vict) == POS_STANDING &&
		    !IS_ROOM(ch->in_room, ROOM_GUILD)) // Prevents tackling past golems.
		{
			door = number(0, NUM_EXITS - 1);

			const int source_room = ch->in_room;
			const auto messages =
				snapshot_forced_departure(ch, vict, door, true, false);
			const auto movement = move_forced_pair(ch, vict, door,
							       [&]() {
								       deliver_forced_departure(
									       messages, ch, vict,
									       source_room, true);
							       });
			if (movement.status == forced_move_status::interrupted)
				return;
			if (movement.status == forced_move_status::blocked)
				forced_rebound_messages(ch, vict, movement.reason, true);
		}

		SET_POS(vict, POS_SITTING + GET_STAT(vict));
		update_group_vitals(vict);
		gmcp_char_vitals(vict);
		CharWait(ch, tackle_lag());
		CharWait(vict, tackle_lag());

		act("You &+ctackle&n $N square in the chest knocking the &+Cwind&n out of $M!",
		    FALSE, ch, 0, vict, TO_CHAR);
		act("$n &+ctackles&n $N square in the chest knocking the &+Cwind&n out of $M!",
		    FALSE, ch, 0, vict, TO_NOTVICT);
		act("$n &+ctackles&n you square in the chest knocking the &+Cwind&n out of you!",
		    FALSE, ch, 0, vict, TO_VICT);
		if ((mount = get_linked_char(vict, LNK_RIDING)) &&
		    (number(1, 100) > GET_CHAR_SKILL(vict, SKILL_MOUNTED_COMBAT)))
		{
			act("$n falls off of $N.", FALSE, vict, NULL, mount, TO_ROOM);
			act("You fall off of $N.", FALSE, vict, NULL, mount, TO_CHAR);
			unlink_char(vict, mount, LNK_RIDING);
		}

		if (!affected_by_spell(vict, SKILL_TACKLE))
		{
			bzero(&af, sizeof(af));
			af.type = SKILL_TACKLE;
			af.location = APPLY_COMBAT_PULSE;
			af.modifier = tackle_combat_pulse();
			af.duration = tackle_combat_pulse_duration();
			affect_to_char(vict, &af);
			act("You suddenly don't have the energy to fight!", FALSE, ch, 0, vict,
			    TO_VICT);
		}
	}
	else
	{
		if (GET_POS(vict) != POS_STANDING)
		{
			act("You leap at $N only to realize $E is down already.", FALSE, ch, 0,
			    vict, TO_CHAR);
			act("$n leaps at $N only to realize $E is down already.", FALSE, ch, 0,
			    vict, TO_NOTVICT);
			act("$n leaps at you only to realize you are down already.", FALSE, ch, 0,
			    vict, TO_VICT);

			SET_POS(ch, POS_SITTING + GET_STAT(ch));
			CharWait(ch, tackle_lag());
		}
		else
		{
			act("You try to &+ctackle&N $N and &+Wfly &Nover $S head landing &+Gface &Nfirst in the &+ydirt&N!",
			    FALSE, ch, 0, vict, TO_CHAR);
			act("$n tries to &+ctackle&N $N and &+Wmisses completely&N, making a nice &+Gdent &Nin $s forehead and the ground!",
			    FALSE, ch, 0, vict, TO_NOTVICT);
			act("$n tries to &+ctackle&N you and &+Wmisses completely&N, making a nice &+Gdent &Nin $s forehead and the ground!",
			    FALSE, ch, 0, vict, TO_VICT);

			if ((GET_C_AGI(ch) + GET_LEVEL(ch)) > number(1, 200))
			{
				SET_POS(ch, POS_KNEELING + GET_STAT(ch));
				CharWait(ch, tackle_lag());
			}
			else
			{
				SET_POS(ch, POS_PRONE + GET_STAT(ch));

				if (GET_C_CON(ch) < number(1, 125))
					Stun(ch, ch, tackle_self_stun(), FALSE);

				CharWait(ch, tackle_prone_lag());
			}
		}
	}

	if (!IS_FIGHTING(ch))
		set_fighting(ch, vict);

	return;
}

/*
 * allow a mount to buck his rider
 */

void buck(P_char ch)
{
	P_char victim = get_linking_char(ch, LNK_RIDING);

	if (!SanityCheck(ch, "buck"))
		return;

	if ((IS_PC(ch) && !IS_CENTAUR(ch)) || (IS_NPC(ch) && !IS_SET(ch->specials.act, ACT_MOUNT)))
	{
		send_to_char(
			"You need to be at least somewhat horse-like in order to buck, don't you think?\n",
			ch);
		return;
	}

	if (!victim)
	{
		send_to_char("There's no one on your back to buck.\n", ch);
		return;
	}

	if (IS_IMMOBILE(ch))
	{
		send_to_char("You seem to be a tad under the weather.\n", ch);
		return;
	}

	if (GET_POS(ch) != POS_STANDING)
	{
		send_to_char("You need to be standing to even attempt to buck.\n", ch);
		return;
	}

	if (IS_FIGHTING(ch))
	{
		send_to_char("You're a tad busy right now, try again when you're not in battle.\n",
			     ch);
		return;
	}

	if (IS_FIGHTING(victim))
	{
		send_to_char(
			"Your rider seems a tad busy right now, try again when they're not in battle.\n",
			ch);
		return;
	}

	/* random failure */

	appear(ch);

	if (number(1, 50) <= 10)
	{
		act("You buck with ferocious might, but $N&n holds on too tightly.", TRUE, ch, 0,
		    victim, TO_CHAR);
		act("$n&n suddenly bucks in an attempt to remove you, but you hold on too tightly.",
		    TRUE, ch, 0, victim, TO_VICT);
		act("$n&n bucks in an attempt to dismount $N&n, but $E holds on too tightly.", TRUE,
		    ch, 0, victim, TO_NOTVICT);

		CharWait(ch, PULSE_VIOLENCE * 3);

		return;
	}

	/* success, toss em off, damage em a little */

	act("You buck with ferocious might, sending $N&n flying!", TRUE, ch, 0, victim, TO_CHAR);
	act("$n&n suddenly bucks, sending you flying!", TRUE, ch, 0, victim, TO_VICT);
	act("$n&n suddenly bucks, sending $N&n flying!", TRUE, ch, 0, victim, TO_NOTVICT);

	CharWait(ch, PULSE_VIOLENCE * 3);
	CharWait(victim, PULSE_VIOLENCE * 2);
	Stun(victim, ch, PULSE_VIOLENCE, TRUE);

	SET_POS(victim, POS_PRONE + GET_STAT(victim));

	unlink_char(ch, victim, LNK_RIDING);
	/*
	  GET_HIT(victim) -= dice(3, 4);
	  update_pos(victim);
	*/
	melee_damage(ch, victim, 1, 0, 0);
}

/*
 * This stuff added by DTS 7/19/95.   * do_disengage(), do_retreat().
 */

void do_disengage(P_char ch, char * /*arg*/, int /*cmd*/)
{
	int found;
	P_char k;

	if (!SanityCheck(ch, "do_disengage"))
		return;

	if (!IS_AWAKE(ch))
	{
		send_to_char("You're in no condition to disengage!\n", ch);
		return;
	}
	if (!IS_FIGHTING(ch))
	{
		send_to_char("But you aren't fighting anything!\n", ch);
		return;
	}
	if (IS_RIDING(ch))
	{
		send_to_char("The heat of battle is too distracting to your mount!\n", ch);
		return;
	}
	/*
	 * one attempt per round
	 */
	/* now applied only if one's opponent is showing any will to fight -Alver
	    CharWait(ch, PULSE_VIOLENCE); */

	/*
	 * Are they tanking?
	 */
	for (k = world[ch->in_room].people, found = FALSE; k; k = k->next_in_room)
		if (GET_OPPONENT(k) == ch)
		{
			found = TRUE;
			break;
		}
	if (found && !IS_TRUSTED(ch))
	{
		send_to_char("You are too busy fighting for your life to disengage!\n", ch);
		return;
	}
	else
	{
		if (GET_STAT(GET_OPPONENT(ch)) > STAT_SLEEPING)
			CharWait(ch, PULSE_VIOLENCE);
		stop_fighting(ch);
		act("You disengage from the fight!", FALSE, ch, 0, 0, TO_CHAR);
		act("$n stops fighting.", TRUE, ch, 0, 0, TO_ROOM);
		return;
	}
}

// The chance threshold of a retreat, rolled 1-100. While tanking (found), it falls with each
// attacker beyond the first. It drops by 10 unless going back the way the character came.
static int retreat_chance(int retc, int expdr, bool found, int ct, bool backdir)
{
	int tankret = MAX(retc - 80, expdr);
	int chance = found ? (tankret - (5 * (ct - 1))) : MAX(expdr, retc);

	chance -= backdir ? 0 : 10;
	return chance;
}

// The retreater's lag, in pulses, on every attempt, and again on a failure.
static int retreat_lag()
{
	return PULSE_VIOLENCE;
}

static std::string retreat_page(P_char ch)
{
	const int retc = GET_CHAR_SKILL(ch, SKILL_RETREAT);
	const int expdr = GET_CHAR_SKILL(ch, SKILL_EXPEDITED_RETREAT);
	return fact("Chance when nothing is fighting you",
		    std::to_string(MAX(0, retreat_chance(retc, expdr, false, 0, true))) +
			    " in 100, " +
			    std::to_string(MAX(0, retreat_chance(retc, expdr, false, 0, false))) +
			    " in a new direction") +
	       fact("Chance while tanking one attacker",
		    std::to_string(MAX(0, retreat_chance(retc, expdr, true, 1, true))) +
			    " in 100; 5 less for each other attacker") +
	       fact("Your lag", seconds(retreat_lag())) +
	       "  A retreat while tanking can only go back the way you came, unless your\n"
	       "  expedited retreat rating is between 1 and 19.\n";
}

std::string retreat_facts(P_char ch)
{
	return retreat_page(ch);
}

std::string expedited_retreat_facts(P_char ch)
{
	return retreat_page(ch);
}

void do_retreat(P_char ch, char *arg, int /*cmd*/)
{
	int dir, found = FALSE, ct = 0;
	char buf[MAX_INPUT_LENGTH];
	char Gbuf1[MAX_STRING_LENGTH];
	P_char k;

	int retc = 0, expdr = 0;

	/*
	  const char *keywords[] =
	  {
	    "north",
	    "east",
	    "south",
	    "west",
	    "up",
	    "down",
	    "northwest",
	    "southwest",
	    "northeast",
	    "southeast",
	    "",
	    "\n"
	  };
	*/

	if (!SanityCheck(ch, "do_retreat"))
		return;

	if (!IS_AWAKE(ch))
	{
		send_to_char("You're in no condition to retreat!\n", ch);
		return;
	}

	retc = GET_CHAR_SKILL(ch, SKILL_RETREAT);
	expdr = GET_CHAR_SKILL(ch, SKILL_EXPEDITED_RETREAT);

	if (retc <= 0 && expdr <= 0)
	{
		send_to_char("You don't have the necessary skill...", ch);
		return;
	}

	if (!IS_FIGHTING(ch))
	{
		send_to_char("You're not fighting anything to retreat from!\n", ch);
		return;
	}

	if (IS_RIDING(ch))
	{
		send_to_char("The battle is too disorienting to your mount to retreat!\n", ch);
		return;
	}

	if (grapple_flee_check(ch))
	{
		send_to_char("You can't flee while locked in a hold!\n", ch);
		return;
	}

	one_argument(arg, buf);
	if (!*buf)
	{
		send_to_char("What direction did you plan to retreat?\n", ch);
		return;
	}
	/*
	  dir = search_block(buf, keywords, FALSE);
	*/
	dir = dir_from_keyword(buf);

	if (dir == -1)
	{
		send_to_char("Uh, that isn't a valid direction to retreat!\n", ch);
		return;
	}
	if (!EXIT(ch, dir) || IS_SET(EXIT(ch, dir)->exit_info, EX_SECRET) ||
	    IS_SET(EXIT(ch, dir)->exit_info, EX_BLOCKED))
	{
		send_to_char("You see no exit in that direction!\n", ch);
		return;
	}
	if (EXIT(ch, dir)->to_room == NOWHERE)
	{
		send_to_char("That exit doesn't seem to lead anywhere!\n", ch);
		return;
	}
	if (IS_SET(EXIT(ch, dir)->exit_info, EX_CLOSED))
	{
		send_to_char("You can't retreat through a closed portal!\n", ch);
		return;
	}
	if (!world[ch->in_room].dir_option[dir] ||
	    !can_enter_room(ch, world[ch->in_room].dir_option[dir]->to_room, TRUE))
	{
		send_to_char("Sorry, you can't retreat in that direction.\n", ch);
		return;
	}

	if (!leave_by_exit(ch, dir))
	{
		send_to_char("You can't retreat through that exit!\n", ch);
		return;
	}

	if (GET_VITALITY(ch) < 1)
	{
		send_to_char("You are too tired to retreat.\n", ch);
		return;
	}
	/*
	 * once per combat round
	 */
	CharWait(ch, retreat_lag());

	/*
	 * Are they tanking?
	 */
	LOOP_THRU_PEOPLE(k, ch)
	{
		if (GET_OPPONENT(k) == ch)
		{
			ct++;
			found = TRUE;
		}
	}

	//  Know if they are just going back in the direction that they came from
	bool backdir = (world[ch->in_room].dir_option[dir]->to_room == ch->specials.was_in_room);

	//
	int chance = retreat_chance(retc, expdr, found, ct, backdir);

	if (found)
	{
		if (!backdir)
		{
			if (expdr && expdr < 20)
				send_to_char(
					"&+wKnowing well that it is nearly impossible, you attempt an expeditious retreat in a new direction!&n\n",
					ch);
			else
			{
				send_to_char(
					"&+WIt would be impossible to break away from combat and retreat in a new direction!&n\n",
					ch);
				return;
			}
		}
		else
		{
			if (!expdr)
			{
				if (chance < 10)
					send_to_char(
						"&+wKnowing well that it is nearly impossible, you attempt to break combat and retreat!&n\n",
						ch);
				else
					send_to_char(
						"&+wKnowing it will be VERY difficult, you attempt to break combat and retreat!&n\n",
						ch);
			}
			else
			{
				send_to_char(
					"&+wYou perform a quick cantrip and attempt an expeditious retreat!&n\n",
					ch);
				notch_skill(ch, SKILL_EXPEDITED_RETREAT, 5);
			}
		}
	}

	if (grapple_check_entrapment(ch))
		return;

	// 5% chance to notch, instead of 2.5% - Jexni 09/17/08
	// Changed notch_skill so that chance = % chance.
	notch_skill(ch, SKILL_RETREAT, 5);

	if (number(1, 100) <= chance)
	{ // Success...
		if (found)
		{
			if (expdr && !IS_RIDING(ch) && expdr > number(1, 110))
			{
				if (ch)
				{
					// Mirror image stuff broken, as is MoveAllAttackers
					//  So now, we'll just let them retreat
					// if(newvict = make_mirror(ch))
					StopAllAttackers(ch);
					// MoveAllAttackers(ch,newvict);
					stop_fighting(ch);
					snprintf(Gbuf1, MAX_STRING_LENGTH,
						 "&+WYou stop fighting and retreat to the %s!&n",
						 dirs[dir]);
					act(Gbuf1, FALSE, ch, 0, 0, TO_CHAR);

					if (number(1, 150) > expdr)
					{
						snprintf(
							Gbuf1, MAX_STRING_LENGTH,
							"&+WYour vision blurs, but you recover in time to see&n $n &+Wretreat %s!&n",
							dirs[dir]);
						act(Gbuf1, TRUE, ch, 0, 0, TO_ROOM);
					}
				}
				else
				{
					act("&+RYour cantrip fails!  You fail the retreat!&n",
					    FALSE, ch, 0, 0, TO_CHAR);
					return;
				}
			}
			else
			{
				StopAllAttackers(ch);
				stop_fighting(ch);
				snprintf(
					Gbuf1, MAX_STRING_LENGTH,
					"&+WYou strategically stop fighting and retreat to the %s!&n",
					dirs[dir]);
				act(Gbuf1, FALSE, ch, 0, 0, TO_CHAR);
				snprintf(
					Gbuf1, MAX_STRING_LENGTH,
					"$n suddenly stops fighting and attempts to retreat to the %s!",
					dirs[dir]);
				act(Gbuf1, TRUE, ch, 0, 0, TO_ROOM);
			}
		}
		else
		{
			StopAllAttackers(ch);
			stop_fighting(ch);
			snprintf(Gbuf1, MAX_STRING_LENGTH,
				 "&+wYou stop fighting and retreat to the %s!&n", dirs[dir]);
			act(Gbuf1, FALSE, ch, 0, 0, TO_CHAR);
			snprintf(Gbuf1, MAX_STRING_LENGTH,
				 "$n suddenly stops fighting and attempts to retreat to the %s!",
				 dirs[dir]);
			act(Gbuf1, TRUE, ch, 0, 0, TO_ROOM);
		}
		do_simple_move(ch, dir, 0);
		if (IS_PC(ch))
			(void)telemetry_runtime_game_encounter_leave(
				ch, telemetry_encounter_outcome::withdrawal);
	}
	else
	{ // Failure!
		if (found)
		{
			if (!expdr)
				send_to_char(
					"&+RYour opponents block your retreat, and you struggle to recover as they press the attack!\n",
					ch);
			else
				send_to_char(
					"&+RYou fail to deceive your opponents, and you struggle to recover as they press the attack!\n",
					ch);
		}
		else
			send_to_char("&+RYou spend some time trying, but you fail to retreat!\n",
				     ch);

		CharWait(ch, retreat_lag());
	}
	return;
}

// The rescuer's lag, in pulses: a guardian's rescue all takes longer.
static int rescue_lag(bool rescue_all)
{
	return rescue_all ? (WAIT_SEC * 6) : PULSE_VIOLENCE;
}

std::string rescue_facts(P_char ch)
{
	std::string facts =
		fact("Chance",
		     "up to " + std::to_string(GET_CHAR_SKILL(ch, SKILL_RESCUE)) + " in 100") +
		fact("Your lag", seconds(rescue_lag(false)));
	if (GET_SPEC(ch, CLASS_WARRIOR, SPEC_GUARDIAN))
		facts += fact("Your lag on a rescue all", seconds(rescue_lag(true)));
	return facts + "  Not while blind or in a single-file room.\n";
}

void rescue(P_char ch, P_char rescuee, bool rescue_all)
{
	P_char t_ch;
	bool found = FALSE;

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (GET_CHAR_SKILL(ch, SKILL_RESCUE) <= 0)
	{
		send_to_char("You don't have the necessary skill...", ch);
		return;
	}

	if (IS_IMMOBILE(ch))
	{
		send_to_char("Hold on a second. You seem unable to rescue anything!\n", ch);
		return;
	}

	if (IS_BLIND(ch))
	{
		send_to_char("&+LDang... someone turned out the lights!\n", ch);
		return;
	}

	if (IS_ROOM(ch->in_room, ROOM_SINGLE_FILE))
	{
		send_to_char("It's too narrow in here to rescue anyone!\n", ch);
		return;
	}

	appear(ch);

	if (IS_RIDING(ch))
	{
		if (!IS_IMMOBILE(get_linked_char(ch, LNK_RIDING)) &&
		    !IS_BLIND(get_linked_char(ch, LNK_RIDING)))
		{
			send_to_char("You deftly maneuver your steed to protect your friend!\n",
				     ch);
		}
		else
		{
			send_to_char("Your mount has an ailment! What is wrong???\n", ch);
			return;
		}
	}

	if (rescuee == ch)
	{
		send_to_char("What about fleeing instead?\n", ch);
		return;
	}

	if (GET_OPPONENT(ch) == rescuee)
	{
		send_to_char("How can you rescue someone you are trying to kill?\n", ch);
		return;
	}

	for (t_ch = world[ch->in_room].people; t_ch; t_ch = t_ch->next_in_room)
	{
		if (GET_OPPONENT(t_ch) != rescuee)
			continue;

		if (!found)
		{
			found = TRUE;
			if (notch_skill(ch, SKILL_RESCUE, get_property("skill.notch.rescue", 10)) ||
			    number(1, 100) > GET_CHAR_SKILL(ch, SKILL_RESCUE))
			{
				act("$n futilely tries to rescue $N!", FALSE, ch, 0, rescuee,
				    TO_NOTVICT);
				act("$n fails miserably in $s attempt to rescue you.", FALSE, ch, 0,
				    rescuee, TO_VICT);
				send_to_char("You fail the rescue.\n", ch);
				break;
			}
			else
			{
				if (affected_by_spell(t_ch, SPELL_BLEAK_FOEMAN))
				{
					char Gbuf1[MAX_STRING_LENGTH];

					snprintf(
						Gbuf1, MAX_STRING_LENGTH,
						"&+LAs you rush in to rescue %s&+L, the black magic surrounding $N &+Lcauses you\n&+Lto to tremble in terror! You spinelessly abandon your comrade!&n",
						GET_NAME(rescuee));
					act(Gbuf1, FALSE, ch, 0, t_ch, TO_CHAR);

					act("&+LAs $N &+Lattempts to rescue $S comrade, the black aura around you flares, and you\n"
					    "&+Lgrin evilly as $E reels backward, unable to complete $S maneuver!&n",
					    FALSE, t_ch, NULL, ch, TO_CHAR);

					snprintf(
						Gbuf1, MAX_STRING_LENGTH,
						"&+LA feeling of hope fills your body as you see %s &+Lrushing to your rescue - but $n\n&+Lgrins evilly, and %s &+Lreels in terror!&n",
						GET_NAME(ch), GET_NAME(ch));
					act(Gbuf1, FALSE, t_ch, 0, rescuee, TO_VICT);

					act("&+LThe black aura surrounding $n &+Lflares, and $e grins evilly as he blocks an\n"
					    "&+Lattempt to save $N!&n",
					    FALSE, t_ch, 0, rescuee, TO_NOTVICT);
					break;
				}

				if (!rescue_all && GET_CHAR_SKILL(ch, SKILL_CLEAVE))
					cleave(ch, t_ch);

				if (GET_STAT(t_ch) == STAT_DEAD)
					return;

				send_to_char("&+WBanzai! To the rescue...\n", ch);
				act("&+WYou are rescued by $N&+W, you are confused, but grateful!",
				    FALSE, rescuee, 0, ch, TO_CHAR);
				if (!rescue_all)
					act("$n &+Wheroically rescues $N&+W.", FALSE, ch, 0,
					    rescuee, TO_NOTVICT);
				else
					act("$n &+Wheroically dives at $N &+Wand pulls $M out of combat.",
					    FALSE, ch, 0, rescuee, TO_NOTVICT);
				if (GET_OPPONENT(rescuee) == t_ch)
					stop_fighting(rescuee);
				if (!IS_FIGHTING(ch))
					set_fighting(ch, t_ch);
			}
		}

		if (GET_OPPONENT(t_ch))
		{
			stop_fighting(t_ch);
			set_fighting(t_ch, ch);
		}

		if (!rescue_all)
		{
			break;
		}
	}

	if (!found)
	{
		act("But nobody is fighting $M?", FALSE, ch, 0, rescuee, TO_CHAR);
		return;
	}

	/* Guardian rescue all: 6 seconds of lag; normal rescue: 1 combat round */
	CharWait(ch, rescue_lag(rescue_all));

	// CharWait(rescuee, PULSE_VIOLENCE / 2);

	/*  if(!IS_FIGHTING(victim) && !victim->specials.next_fighting)
	    set_fighting(victim, ch);*/
}

// Damage from a maul, before a mauler's bonus and the target's defenses.
static int maul_damage(const Rolls &rolls, P_char ch)
{
	return rolls.dice(MIN(30, GET_LEVEL(ch)), 6) *
	       (get_property("skill.maul.damfactor", 1.000));
}

static int maul_mauler_damage(int dam)
{
	dam *= 1.5;
	return dam;
}

// The mauler's lag, in pulses, by what happened.
static int maul_penalty_lag()
{
	return (PULSE_VIOLENCE * 2);
}

static int maul_failed_lag()
{
	return (PULSE_VIOLENCE * get_property("skill.maul.failedmaul.lag", 1.500));
}

// A hit's lag and rest, in pulses, for mauler specialists (and elites) and for others.
static int maul_hit_lag(bool mauler)
{
	return mauler ? (PULSE_VIOLENCE * 1.800) : (PULSE_VIOLENCE * 2.000);
}

static int maul_target_lag(bool mauler)
{
	return mauler ? (PULSE_VIOLENCE * 1.200) : (PULSE_VIOLENCE * 1.000);
}

static int maul_rest(bool mauler)
{
	return mauler ?
		       (PULSE_VIOLENCE * get_property("skill.maul.IsMauler.ShieldBashlag", 2.000)) :
		       (PULSE_VIOLENCE *
			get_property("skill.maul.IsNotMauler.ShieldBashlag", 2.200));
}

// How long, in ticks, a mauled target stays aware.
static int maul_aware_duration()
{
	return 1;
}

// True on the 1 maul in 4 that clips a target of the wrong size for half damage.
static bool maul_clip_roll(const Rolls &rolls)
{
	return !rolls.number(0, 3);
}

std::string maul_facts(P_char ch)
{
	const bool mauler = GET_SPEC(ch, CLASS_BERSERKER, SPEC_MAULER);
	int low = maul_damage(lowest_rolls, ch), high = maul_damage(highest_rolls, ch);
	if (mauler)
	{
		low = maul_mauler_damage(low);
		high = maul_mauler_damage(high);
	}
	return fact("Damage on a hit", show({ low, high }) + " at your level") +
	       fact("Your lag on a hit", seconds(maul_hit_lag(mauler))) +
	       fact("Your lag on a miss or a target of the wrong size",
		    seconds(maul_failed_lag())) +
	       fact("Chance the wrong size still takes half damage", "1 in 4") +
	       fact("Your lag if the target foils the takedown", seconds(maul_penalty_lag())) +
	       fact("Your lag if the target is asleep",
		    seconds(takedown_sleeping_target_lag()) + " (you attack it instead)") +
	       fact("Your lag if the target evades", seconds(takedown_evade_lag())) +
	       fact("Before your next takedown after a hit", seconds(maul_rest(mauler))) +
	       fact("Target's lag on a hit", seconds(maul_target_lag(mauler))) +
	       fact("Target stays aware", game_hours(maul_aware_duration())) +
	       "  Needs berserk. The right size is your own or one either way; a centaur or\n"
	       "  drider must be smaller than you. The target's defenses apply to the damage.\n";
}

void maul(P_char ch, P_char victim)
{
	int percent_chance, ch_size, vict_size, dam;
	int percentroll = number(1, 100);
	bool too_big;
	struct affected_type af;

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (!IS_ALIVE(victim))
	{
		send_to_char("Your victim seems to be quite dead.\n", ch);
		return;
	}

	if (!affected_by_spell(ch, SKILL_BERSERK))
	{
		send_to_char("You aren't quite angry enough...\n", ch);
		return;
	}

	if (!CanDoFightMove(ch, victim))
		return;

	percent_chance = GET_CHAR_SKILL(ch, SKILL_MAUL);

	if (percent_chance < 1)
	{
		send_to_char("You get real angry, grrr.\n", ch);
		return;
	}

	if (!on_front_line(ch) || !on_front_line(victim))
	{
		send_to_char("You can't quite seem to reach them...\n", ch);
		return;
	}

	if (GET_CLASS(ch, CLASS_BERSERKER) && affected_by_spell(ch, SKILL_BASH))
	{
		send_to_char("&+LYou haven't reoriented yourself yet enough for another maul!&n\n",
			     ch);
		return;
	}

	appear(ch);
	engage(ch, victim);
	victim = guard_check(ch, victim);

	act("$n fills with &+rBLooDLuST&n and makes a ferocious leap at $N!", FALSE, ch, 0, victim,
	    TO_NOTVICT);
	act("$n fills with &+rBLoodLuST&n and makes a ferocious leap at YOU!", FALSE, ch, 0, victim,
	    TO_VICT);
	act("You fill with &+rBLoodLuST&n and make a ferocious attack against $N!", FALSE, ch, 0,
	    victim, TO_CHAR);

	percent_chance = takedown_check(ch, victim, percent_chance, SKILL_MAUL, TAKEDOWN_ALL);

	if (percent_chance == TAKEDOWN_CANCELLED)
		return;
	else if (percent_chance == TAKEDOWN_PENALTY)
	{
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		CharWait(ch, maul_penalty_lag());
		return;
	}
	else
		percent_chance = BOUNDED(2, percent_chance, 90);

	vict_size = get_takedown_size(victim);
	ch_size = get_takedown_size(ch);

	dam = maul_damage(live_rolls, ch);

	if (GET_SPEC(ch, CLASS_BERSERKER, SPEC_MAULER))
		dam = maul_mauler_damage(dam);

	percent_chance = (int)(percent_chance * (get_property("skill.maul.hitchance", 1.000)));

	if (IS_AFFECTED(victim, AFF_AWARE))
		percent_chance = (percent_chance * 0.84);

	if (IS_ELITE(ch) || GET_SPEC(ch, CLASS_BERSERKER, SPEC_MAULER))
		percent_chance = (percent_chance * 1.25);

	if (GET_POS(victim) != POS_STANDING)
		percent_chance = 0;

	/*
	 * if they are fighting something and try to maul something else
	 */
	if (IS_FIGHTING(ch) && GET_OPPONENT(victim) != ch && GET_OPPONENT(ch) != victim &&
	    !GET_SPEC(ch, CLASS_BERSERKER, SPEC_MAULER))
	{
		send_to_char(
			"You are fighting something else! Nevertheless, you attempt the maul...\n",
			ch);
		percent_chance = (percent_chance * 0.7);
	}

	if ((has_innate(victim, INNATE_HORSE_BODY) || has_innate(victim, INNATE_SPIDER_BODY)) &&
	    get_takedown_size(ch) <= get_takedown_size(victim))
		too_big = true;
	else if (vict_size > ch_size + 1)
		too_big = true;
	else
		too_big = false;

	if (too_big)
	{
		act("$n &+ymakes a futile attempt to maul&n $N, &+ybut $E is simply immovable.&n",
		    FALSE, ch, 0, victim, TO_NOTVICT);
		act("$n &+ymakes a futile attempt to maul you, but you are simply immovable.&n",
		    FALSE, ch, 0, victim, TO_VICT);
		act("&+yYou slam up against&n $N!", FALSE, ch, 0, victim, TO_CHAR);

		if (maul_clip_roll(live_rolls))
		{
			act("$n &+ygrowls&n on impact, and slams $s head into $N before falling to $s knees!",
			    FALSE, ch, 0, victim, TO_NOTVICT);
			act("But $e slams his head into you anyways, before falling to $s knees!",
			    FALSE, ch, 0, victim, TO_VICT);
			act("But you slam your head into $N before crashing to your knees!", FALSE,
			    ch, 0, victim, TO_CHAR);
			melee_damage(ch, victim, (int)(dam / 2), PHSDAM_TOUCH, 0);
		}

		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		CharWait(ch, maul_failed_lag());
	}
	else if (vict_size < ch_size - 1)
	{
		act("$n &+ytopples over $mself as $e tries to maul&n $N.", FALSE, ch, 0, victim,
		    TO_NOTVICT);
		act("$n &+ytopples over $mself as $e tries to maul you.&n", FALSE, ch, 0, victim,
		    TO_VICT);
		send_to_char("&+yMauling creatures of this minute size is hopeless at best.\n", ch);

		if (maul_clip_roll(live_rolls))
		{
			act("As $n falls, $e delivers a nasty backhand blow to $N!", FALSE, ch, 0,
			    victim, TO_NOTVICT);
			act("As $e goes down, $e backhands you!", FALSE, ch, 0, victim, TO_VICT);
			send_to_char("\n", ch);
			act("But you get the last laugh as you &+mbitch slap&n $N!", FALSE, ch, 0,
			    victim, TO_CHAR);

			melee_damage(ch, victim, (int)(dam / 2), PHSDAM_TOUCH, 0);
		}

		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		CharWait(ch, maul_failed_lag());
	}
	else if (percent_chance > percentroll ||
		 notch_skill(ch, SKILL_MAUL, get_property("skill.notch.offensive", 7)))
	{
		act("$n &+yknocks&n $N &+ydown with a mighty blow!&n", FALSE, ch, 0, victim,
		    TO_NOTVICT);
		act("$n &+yknocks you down with a mighty blow!&n", FALSE, ch, 0, victim, TO_VICT);
		act("&+yYou knock&n $N &+ydown with a mighty blow!&n", FALSE, ch, 0, victim,
		    TO_CHAR);

		SET_POS(victim, POS_KNEELING + GET_STAT(victim));

		// if((percent_chance / 5) > percentroll && !IS_STUNNED(victim))
		// Stun(victim, ch, PULSE_VIOLENCE, TRUE); //removing stun from maul - should not be better than regular takedown

		if (GET_SPEC(ch, CLASS_BERSERKER, SPEC_MAULER) || IS_ELITE(ch))
		{
			CharWait(victim, maul_target_lag(true));
			CharWait(ch, maul_hit_lag(true));
			set_short_affected_by(ch, SKILL_BASH, maul_rest(true));
		}
		else
		{
			CharWait(victim, maul_target_lag(false));
			CharWait(ch, maul_hit_lag(false));
			set_short_affected_by(ch, SKILL_BASH, maul_rest(false));
		}

		melee_damage(ch, victim, dam, PHSDAM_TOUCH, 0);

		if (!affected_by_spell(victim, SKILL_AWARENESS))
		{
			bzero(&af, sizeof(af));
			af.type = SKILL_AWARENESS;
			af.duration = maul_aware_duration();
			af.bitvector = AFF_AWARE;
			af.flags = AFFTYPE_NODISPEL;
			affect_to_char(victim, &af);
		}
	}
	else
	{
		act("$N &+yavoids&n $n's &+yferocious maul, and down $e goes!&n", FALSE, ch, 0,
		    victim, TO_NOTVICT);
		act("$n &+yattempts to maul you, but falters and falls to $s knees!&n", FALSE, ch,
		    0, victim, TO_VICT);
		act("You &+ygrowl&n as $N avoids your maul, and you become &+RFURIOUS&n when you hit the ground!",
		    FALSE, ch, 0, victim, TO_CHAR);
		SET_POS(ch, POS_KNEELING + GET_STAT(ch));

		CharWait(ch, maul_failed_lag());
	}
}

// The puncher's lag, in pulses.
static int shieldpunch_lag()
{
	return (int)(PULSE_VIOLENCE * get_property("skill.shieldpunch.lag", 1.000));
}

// The top of a punch's roll, from shield combat.
static int shieldpunch_bonus(P_char ch)
{
	return (int)(MAX(20, GET_CHAR_SKILL(ch, SKILL_SHIELD_COMBAT) / 2));
}

// Damage from a punch, before the target's defenses.
static int shieldpunch_damage(const Rolls &rolls, P_char ch, int dambonus)
{
	return 6 * (rolls.number(1, dambonus) + (ch->equipment[WEAR_SHIELD]->weight));
}

std::string shieldpunch_facts(P_char ch)
{
	std::string facts;
	if (ch->equipment[WEAR_SHIELD])
		facts = fact(
			"Damage on a hit",
			show({ shieldpunch_damage(lowest_rolls, ch, shieldpunch_bonus(ch)),
			       shieldpunch_damage(highest_rolls, ch, shieldpunch_bonus(ch)) }) +
				" with your shield");
	return facts + fact("Your lag", seconds(shieldpunch_lag())) +
	       "  You need a shield. The target can be up to 2 sizes bigger or 1 smaller, and\n"
	       "  not immaterial. The target's defenses apply to the damage.\n";
}

void shieldpunch(P_char ch, P_char victim)
{
	int ch_size, vict_size, percent_chance, dambonus, dmg;
	struct damage_messages messages = {
		"You slam your shield into $N with incredible force!",
		"You stagger as $n slams $s shield into you.",
		"A crunching noise is heard as $n slams $s shield into $N!",
		"You slam your shield into $N splitting $S skull like an egg, yuck.",
		"The world explodes in pain as $n smashes your face with $s shield, but the pain is brief...",
		"Bones crunching is heard as $n slams $s shield into $N's face."
	};

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (!IS_ALIVE(victim))
	{
		send_to_char("Your victim seems to be quite dead.\n", ch);
		return;
	}

	if (GET_CHAR_SKILL(ch, SKILL_SHIELDPUNCH) == 0) // Need the skill.
	{
		send_to_char("You are not skilled with the shield enough.\n", ch);
		return;
	}
	/*
	   if(affected_by_spell(ch, SKILL_BASH)) {
	   send_to_char("You must rest before trying.\n", ch);
	   return;
	   }
	 */
	if (!on_front_line(ch))
	{
		send_to_char("You can't seem to break the ranks!\n", ch);
		return;
	}
	if (!victim)
	{
		send_to_char("Punch who?\n", ch);
		CharWait(ch, 1 * WAIT_SEC);
		return;
	}
	if (!CanDoFightMove(ch, victim))
	{
		return;
	}
	if (!ch->equipment[WEAR_SHIELD])
	{
		send_to_char("Punch with what?\n", ch);
		return;
	}

	appear(ch);

	CharWait(ch, shieldpunch_lag());

	victim = guard_check(ch, victim);

	vict_size = get_takedown_size(victim);
	ch_size = get_takedown_size(ch);

	if (vict_size > ch_size + 2)
	{
		act("$n smashes $N with $s shield, but $E does not look impressed.", FALSE, ch, 0,
		    victim, TO_NOTVICT);
		act("$n hits you with $s puny shield.", FALSE, ch, 0, victim, TO_VICT);
		act("You smash $N with your shield, but $E does not look impressed.", FALSE, ch, 0,
		    victim, TO_CHAR);
		engage(ch, victim); // Simplified initiate combat code from above.
		return;
	}
	if (vict_size < ch_size - 1)
	{
		act("$n tries to hit $N with $s shield, but $E easily evades the attack.", FALSE,
		    ch, 0, victim, TO_NOTVICT);
		act("$n makes a swift move trying to hit you with $s shield but misses.", FALSE, ch,
		    0, victim, TO_VICT);
		act("You try to hit $N with your shield, but $E easily evades your attack.", FALSE,
		    ch, 0, victim, TO_CHAR);
		engage(ch, victim); // Simplified initiate combat code from above.
		return;
	}
	if (IS_HARPY(victim) && (number(0, 99) < 5))
	{
		act("Your attempt to shieldpunch $N fails as $M flutters into the air.", FALSE, ch,
		    0, victim, TO_CHAR);
		act("$n makes a valiant attempt to shieldpunch $N, but $E flutters into the air.",
		    FALSE, ch, 0, victim, TO_NOTVICT);
		act("$n's attempt to shieldpunch you fails as you flutter into the air.", FALSE, ch,
		    0, victim, TO_VICT);
		engage(ch, victim); // Simplified initiate combat code from above.
		return;
	}

	if (IS_IMMATERIAL(victim))
	{
		act("Your attempt to shieldpunch $N fails as you simply pass through $M.", FALSE,
		    ch, 0, victim, TO_CHAR);
		act("$n makes a valiant attempt to shieldpunch $N, but simply falls through $M.",
		    FALSE, ch, 0, victim, TO_NOTVICT);
		act("$n's attempt to shieldpunch you fails as $e simply passes through you.", FALSE,
		    ch, 0, victim, TO_VICT);
		engage(ch, victim); // Simplified initiate combat code from above.
		return;
	}
	if (IS_NPC(ch)) // NPCs receive a bonus. Need to make sure mobs use shield punch.
	{
		percent_chance = (int)(GET_CHAR_SKILL(ch, SKILL_SHIELDPUNCH) * 1.20);
	}
	else
	{
		percent_chance = GET_CHAR_SKILL(ch, SKILL_SHIELDPUNCH);
	}
	if (GET_C_LUK(ch) / 2 > number(0, 100))
	{
		percent_chance = (int)(percent_chance * 1.1);
	}
	if (GET_C_LUK(victim) / 2 > number(0, 100))
	{
		percent_chance = (int)(percent_chance * 0.9);
	}
	if (!on_front_line(victim))
	{
		percent_chance = (int)(percent_chance * 0.8);
	}
	if (IS_PC(victim) && IS_PC(ch))
	{
		percent_chance =
			(int)(percent_chance *
			      ((double)BOUNDED(6, 10 + (GET_C_AGI(ch) - GET_C_AGI(victim)) / 10,
					       15)) /
			      10);
	}

	/*
	 * if they are fighting something and try to shield punch something else
	 */
	if (IS_FIGHTING(ch) && GET_OPPONENT(victim) != ch && GET_OPPONENT(ch) != victim)
	{
		percent_chance = (int)(percent_chance * 0.7);
	}

	percent_chance =
		(int)(percent_chance *
		      ((double)BOUNDED(6, 10 + (GET_LEVEL(ch) - GET_LEVEL(victim)) / 10, 15)) / 10);

	if (GET_POS(victim) != POS_STANDING) // Just harder, but not impossible.
	{
		act("Your opponent isn't standing, but you try anyway.", FALSE, ch, 0, victim,
		    TO_CHAR);
		percent_chance = (int)(percent_chance / 2);
	}
	percent_chance = BOUNDED(5, percent_chance, 95);

	// !!!should make a separate function to calculate chances to it can be used in mob AI
	if (IS_NPC(ch) && (number(0, 50) > percent_chance))
	{
		return;
	}

	if (notch_skill(ch, SKILL_SHIELDPUNCH, get_property("skill.notch.offensive", 7)) ||
	    number(0, 100) < percent_chance)
	{
		dambonus = shieldpunch_bonus(ch);
		dmg = shieldpunch_damage(live_rolls, ch, dambonus);

		if (melee_damage(ch, victim, dmg, 0, &messages) != DAM_NONEDEAD)
		{
			return;
		}
		if (IS_ALIVE(victim) && IS_ALIVE(ch))
		{
			engage(ch, victim); // Simplified initiate combat code from above.
			CharWait(victim, (int)get_property("skill.shieldpunch.targetlag", 0.500));
		}
		else
		{
			return;
		}
	}
	else
	{
		act("You try to crush $N with your shield but fail.", FALSE, ch, 0, victim,
		    TO_CHAR);
		act("$n lunges at you with $s shield but misses.", FALSE, ch, 0, victim, TO_VICT);
		act("$n lunges at $N with $s shield but $s aim is off.", FALSE, ch, 0, victim,
		    TO_NOTVICT);
	}
}

void do_shieldpunch(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL;

	if (!ch)
	{
		logit(LOG_EXIT, "do_shieldpunch called in actoff.c with no ch");
		return;
	}
	if (ch) // Just making sure...
	{
		victim = ParseTarget(ch, argument);

		shieldpunch(ch, victim);
	}
}

// The thruster's lag, in pulses.
static int sweeping_thrust_lag()
{
	return (int)(PULSE_VIOLENCE * (get_property("skill.SweepingThrust.lag", 1.500)));
}

// The top of the 0-based roll that knocks a target to its knees: 0 means it does.
static int sweeping_thrust_odds(int level)
{
	int sweepthrustaffect = 4;
	if (level > 46)
	{
		sweepthrustaffect--;
	}

	if (level > 51)
	{
		sweepthrustaffect--;
	}
	return sweepthrustaffect;
}

// The target's lag, in pulses, when knocked to its knees.
static int sweeping_thrust_target_lag()
{
	return (int)(0.5 * PULSE_VIOLENCE);
}

std::string sweeping_thrust_facts(P_char ch)
{
	return fact("Chance a hit knocks the target to its knees",
		    "1 in " + std::to_string(sweeping_thrust_odds(GET_LEVEL(ch)) + 1) +
			    " at your level") +
	       fact("Target's lag when knocked to its knees",
		    seconds(sweeping_thrust_target_lag())) +
	       fact("Your lag", seconds(sweeping_thrust_lag())) +
	       fact("Your lag if the target is asleep",
		    seconds(takedown_sleeping_target_lag()) + " (you attack it instead)") +
	       fact("Your lag if the target evades", seconds(takedown_evade_lag())) +
	       "  Otherwise it is a normal attack with your weapon. You need a weapon, and the\n"
	       "  target can be up to 3 sizes bigger or 1 smaller, not immaterial or legless.\n";
}

void do_sweeping_thrust(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL;
	int ch_size, vict_size, percent_chance, takedown_chance, levelc, levelvict;
	int sweepthrustaffect;

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (GET_CHAR_SKILL(ch, SKILL_SWEEPING_THRUST) < 1) // Need the skill.
	{
		send_to_char("You don't know how to do this.\n", ch);
		return;
	}

	victim = ParseTarget(ch, argument); // Find the target.

	if (!victim) // No target.
	{
		send_to_char("Hit who?\n", ch);
		CharWait(ch, 1 * WAIT_SEC);
		return;
	}

	if (!IS_ALIVE(victim)) // Target is dead. Hrm...
	{
		return;
	}

	if (IS_STUNNED(ch)) // No can do while stunned.
	{
		act("You are too stunned to perform a sweeping attack.", FALSE, ch, 0, victim,
		    TO_VICT);
		return;
	}

	if (!ch->equipment[WIELD] && // Players need a weapon, but mobs can perform the action nevertheless.
	    !ch->equipment[WIELD2] && IS_PC(ch))
	{
		send_to_char("You need to wield a weapon.\n", ch);
		return;
	}

	takedown_chance = GET_CHAR_SKILL(ch, SKILL_SWEEPING_THRUST);
	takedown_chance = takedown_check(ch, victim, takedown_chance, SKILL_SWEEPING_THRUST,
					 TAKEDOWN_ALL ^ TAKEDOWN_AGI_CHECK ^ TAKEDOWN_FOOTING);

	if (takedown_chance == TAKEDOWN_CANCELLED)
	{
		return;
	}

	if (!CanDoFightMove(ch, victim))
	{
		return;
	}

	CharWait(ch, sweeping_thrust_lag());

	appear(ch);

	if (IS_IMMATERIAL(victim))
	{
		act("Your attempted sweeping thrust at $N fails as it is like &+wmist!&n", FALSE,
		    ch, 0, victim, TO_CHAR);
		act("$n makes a valiant attempt to thrust $N, but simply passes through $M.", FALSE,
		    ch, 0, victim, TO_NOTVICT);
		act("$n's attempts a fancy attack, but it simply passes through you.", FALSE, ch, 0,
		    victim, TO_VICT);

		engage(ch, victim);

		return;
	}

	if (LEGLESS(victim))
	{
		act("Your victim must have legs to swipe at!!!", FALSE, ch, 0, victim, TO_CHAR);
		return;
	}

	victim = guard_check(ch, victim);

	vict_size = get_takedown_size(victim);
	ch_size = get_takedown_size(ch);

	if (vict_size > ch_size + 3)
	{
		act("$n tries to find a weak point around $N's knees, but $E is simply too big!",
		    FALSE, ch, 0, victim, TO_NOTVICT);
		act("$n performs some swift maneuver around your feet. Did not hurt.", FALSE, ch, 0,
		    victim, TO_VICT);
		act("You try to find a weak point around $N's knees, but $E is simply too big!",
		    FALSE, ch, 0, victim, TO_CHAR);

		engage(ch, victim);

		return;
	}

	if (vict_size < ch_size - 1)
	{
		act("$n tries to find a weak point around $N's knees, but $E is just too small!",
		    FALSE, ch, 0, victim, TO_NOTVICT);
		act("$n lashes toward your legs, but just gets confused by your morphology.", FALSE,
		    ch, 0, victim, TO_VICT);
		act("You try to find a weak point around $N's knees, but $E is just too small!",
		    FALSE, ch, 0, victim, TO_CHAR);

		engage(ch, victim);

		return;
	}

	if (IS_HARPY(victim) && (int)(number(0, 99) < GET_LEVEL(victim) / 10))
	{
		act("Your attempt to thrust $N fails as $M flutters into the air.", FALSE, ch, 0,
		    victim, TO_CHAR);
		act("$n makes a valiant attempt to thrust $N, but $E flutters into the air.", FALSE,
		    ch, 0, victim, TO_NOTVICT);
		act("$n's attempt to thrust you fails as you flutter into the air.", FALSE, ch, 0,
		    victim, TO_VICT);

		engage(ch, victim);
		return;
	}

	percent_chance = GET_CHAR_SKILL(ch, SKILL_SWEEPING_THRUST);

	if (IS_NPC(ch) && // Mobiles have greater sweeping skill than normal up (25% bonus).
	    GET_CLASS(ch, CLASS_WARRIOR))
	{
		percent_chance = (int)(percent_chance * 1.25);
	}

	percent_chance = // Attacker checks dex, defender checks agi
		(int)(percent_chance *
		      ((double)(BOUNDED(6, 10 + (GET_C_DEX(ch) - GET_C_AGI(victim)) / 5, 15)) /
		       10));

	/*
	 * if they are fighting something and try to sweeping thrust something else
	 */
	if (IS_FIGHTING(ch) && GET_OPPONENT(victim) != ch && GET_OPPONENT(ch) != victim)
	{
		percent_chance = (int)(percent_chance *
				       0.9); // Trying to sweeping another target is penalized.
	}

	levelc = GET_LEVEL(ch);
	levelvict = GET_LEVEL(victim);

	percent_chance = // Level difference check with bonus going to the higher level.
		(int)(percent_chance * ((double)BOUNDED(6, 10 + (levelc - levelvict), 15)) / 10);

	percent_chance = BOUNDED(5, percent_chance, 95);

	if (GET_POS(victim) != POS_STANDING && // Don't want the players to notch skill here.
	    number(0, 99) < percent_chance)
	{
		act("You cleanly perform a &+csweeping attack&n on $N!", FALSE, ch, 0, victim,
		    TO_CHAR);
		act("$n beats on you while you are down with a &+cwide arcing attack!&n", FALSE, ch,
		    0, victim, TO_VICT);
		act("$n leans forward and &+cswipes&n $N who is powerless to stop the attack!",
		    FALSE, ch, 0, victim, TO_NOTVICT);

		hit(ch, victim, ch->equipment[PRIMARY_WEAPON]);
		engage(ch, victim);

		return;
	}

	if (IS_NPC(ch) && (number(0, 99) > percent_chance))
	{
		act("$n sweeps low but you quickly sidestep out of reach.", FALSE, ch, 0, victim,
		    TO_VICT);
		act("$n does a sweeping motion but $N reacts quickly and moves out of reach.",
		    FALSE, ch, 0, victim, TO_NOTVICT);

		engage(ch, victim);
		return;
	}

	if (notch_skill(ch, SKILL_SWEEPING_THRUST, get_property("skill.notch.offensive", 7)) ||
	    number(1, 100) < percent_chance)
	{
		sweepthrustaffect = sweeping_thrust_odds(GET_LEVEL(ch));

		if (!number(0, sweepthrustaffect) && GET_POS(victim) == POS_STANDING &&
		    (takedown_chance != TAKEDOWN_PENALTY))
		{
			act("$N was knocked off $S feet by $n's &+csweeping attack!&n", FALSE, ch,
			    0, victim, TO_NOTVICT);
			act("$N was knocked off $S feet by your &+csweeping attack!&n", FALSE, ch,
			    0, victim, TO_CHAR);
			act("You were knocked off your feet by $n's &+csweeping attack!&n", FALSE,
			    ch, 0, victim, TO_VICT);

			SET_POS(victim, POS_KNEELING + GET_STAT(victim));
			engage(ch, victim);
			CharWait(victim, sweeping_thrust_target_lag());
		}
		else
		{
			act("$n delivers &+ca sound hit&n on $N but does not sweep $M off $S feet.&n",
			    FALSE, ch, 0, victim, TO_NOTVICT);
			act("Your &+csweeping attack&n fails to drop $N, but you deliver a sound hit.&n",
			    FALSE, ch, 0, victim, TO_CHAR);
			act("$n performs a low &+csweeping attack&n and you are hit!", FALSE, ch, 0,
			    victim, TO_VICT);

			if (ch->equipment[WIELD])
			{
				hit(ch, victim, ch->equipment[PRIMARY_WEAPON]);
			}
			else
			{
				hit(ch, victim, ch->equipment[SECONDARY_WEAPON]);
			}

			engage(ch, victim);
		}
		return;
	}
	// Bad sweep and down the attacker goes!
	else if (!number(0, 2) && (number(0, 100) > GET_C_AGI(ch)))
	{
		SET_POS(ch, POS_KNEELING + GET_STAT(ch));
		update_pos(ch);
		act("You overreach and crash into the ground!", FALSE, ch, 0, victim, TO_CHAR);
		act("$n overreaches and hits the ground!", FALSE, ch, 0, victim, TO_VICT);
		act("$n does a fancy sweeping motion but ends up on the ground.", FALSE, ch, 0,
		    victim, TO_NOTVICT);

		engage(ch, victim);
		return;
	}
	else // A non critical failure.
	{
		act("You feign and try to strike $N but $E sidesteps easily.", FALSE, ch, 0, victim,
		    TO_CHAR);
		act("$n sweeps low but you quickly sidestep out of reach.", FALSE, ch, 0, victim,
		    TO_VICT);
		act("$n does a sweeping motion but $N reacts quickly and moves out of reach.",
		    FALSE, ch, 0, victim, TO_NOTVICT);

		engage(ch, victim);
		return;
	}
}

void do_rearkick(P_char ch, char *argument, int /*cmd*/)
{
	int door, takedown_chance, dam, ch_size, vict_size;
	P_char victim;
	double percent_chance;
	struct damage_messages messages = {
		"You shift your weight and viciously slam your rear hooves into $N with a &+Wstunning&n force!",
		"$n shifts $s weight and viciously slams $s rear hooves into you with a &+Wstunning&n force!",
		"$n shifts $s weight and viciously slams $s rear hooves into $N's chest with a stunning force.",
		"You shift your weight and viciously slam your rear hooves into $N, you feel this was the last thing $E could take.",
		"$n's hooves come at incredible speed right towards your face. Noise slowly fades as you fall into darkness.",
		"$n shifts $s weight and viciously slams $s rear hooves into $N's chest which falls in with a loud CRUNCH.",
		0,
		0
	};

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (!has_innate(ch, INNATE_HORSE_BODY) && !(GET_RACE(ch) == RACE_QUADRUPED) &&
	    !IS_TRUSTED(ch))
	{
		send_to_char("You wish you were a horse...\n", ch);
		return;
	}

	if (!on_front_line(ch))
	{
		send_to_char("You can't seem to break the ranks!\n", ch);
		return;
	}

	victim = ParseTarget(ch, argument);

	if (!IS_ALIVE(victim))
	{
		send_to_char("Rearkick who?\n", ch);
		return;
	}

	if (!kick_admitted(ch, victim))
	{
		return;
	}

	appear(ch);

	victim = guard_check(ch, victim);

	if ((percent_chance = chance_kick(ch, victim)) == 0)
	{
		return;
	}

	if (IS_IMMATERIAL(victim))
	{
		act("Your hooves pass through $N. All that horsepower, and nothing solid to kick!",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$n's hooves pass harmlessly through you. Being mist has its moments!", FALSE,
		    ch, 0, victim, TO_VICT);
		act("$n's hooves pass through $N, stirring up more embarrassment than damage.",
		    FALSE, ch, 0, victim, TO_NOTVICT);
		CharWait(ch, PULSE_VIOLENCE * 2);
		engage(ch, victim);
		return;
	}

	vict_size = get_takedown_size(victim);
	ch_size = get_takedown_size(ch);

	// Rear kick does similar damage to kick, and is no longer level based.  Bad idea.
	dam = (int)(MAX(GET_C_STR(ch) / 2,
			(GET_CHAR_SKILL(ch, SKILL_KICK)) * get_property("skill.rearkick.dam", 2)));

	// Randomize damage same as in kick.
	dam = number(dam / 2, dam);

	if (vict_size > ch_size + 1)
		dam = (dam * 3) / 4;

	if (vict_size < ch_size - 1)
		dam = (dam * 5) / 4;

	CharWait(ch, PULSE_VIOLENCE * 2);

	act("&+gYou tense up and prepare to rearkick&n $N &+gwith your hind legs!&n", FALSE, ch, 0,
	    victim, TO_CHAR);

	if (!notch_skill(ch, SKILL_KICK, get_property("skill.notch.offensive", 7)) &&
	    percent_chance <= number(0, 100))
	{
		act("But fail miserably!", FALSE, ch, 0, victim, TO_CHAR);
		act("You narrowly avoid $n's hooves!", FALSE, ch, 0, victim, TO_VICT);
		act("$n attempts to kick $N but fails miserably!", FALSE, ch, 0, victim,
		    TO_NOTVICT);
		engage(ch, victim);
		return;
	}

	if (melee_damage(ch, victim, dam, PHSDAM_TOUCH, &messages) != DAM_NONEDEAD)
		return;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
		return;

	if (IS_GREATER_RACE(victim) || LEGLESS(victim) || IS_TRUSTED(victim) || IS_ELITE(ch))
		return;

	if (get_takedown_size(victim) + 2 > get_takedown_size(ch))
		return;

	if (GET_POS(victim) != POS_STANDING)
		return;

	takedown_chance = (ch_size - vict_size) * 5; /*10-25% */

	if (IS_NPC(ch))
		takedown_chance += 15;

	takedown_chance = takedown_check(ch, victim, takedown_chance, SKILL_KICK,
					 TAKEDOWN_ALL ^ TAKEDOWN_AGI_CHECK ^ TAKEDOWN_FOOTING);

	if (takedown_chance == TAKEDOWN_CANCELLED || takedown_chance == TAKEDOWN_PENALTY)
		return;

	if (takedown_chance > number(0, 100))
	{
		//    int gh = (zone_table[world[ch->in_room].zone].number == GH_ZONE_NUMBER);

		door = number(0, 9);
		// Exit that's not up or down.
		if ((door == DIR_UP) || (door == DIR_DOWN))
			door = number(0, 3);

		const int source_room = ch->in_room;
		const auto messages = snapshot_forced_departure(ch, victim, door, false, true);
		const auto movement = move_forced(
			ch, victim, door, [&]()
			{ deliver_forced_departure(messages, ch, victim, source_room, false); });
		if (movement.status == forced_move_status::arrived)
		{
			act("$n flies in, crashing on the floor!", TRUE, victim, 0, 0, TO_ROOM);
			CharWait(victim, (int)(PULSE_VIOLENCE *
					       get_property("kick.roomkick.victimlag", 1.000)));
			SET_POS(victim, POS_PRONE + GET_STAT(victim));
			update_group_vitals(victim);
			gmcp_char_vitals(victim);
		}
		else if (movement.status == forced_move_status::blocked)
		{
			forced_rebound_messages(ch, victim, movement.reason, false);
			CharWait(victim, (int)(PULSE_VIOLENCE *
					       get_property("kick.wallkick.victimlag", 1.5)));
			SET_POS(victim, POS_SITTING + GET_STAT(victim));
			update_group_vitals(victim);
			gmcp_char_vitals(victim);
			stop_fighting(victim);
		}
	}
	return;
}

/*
 *  Old Rearkick down below
 */

/*
  percent_chance = 0.95*MAX(20, GET_CHAR_SKILL(ch, SKILL_KICK));

  if(IS_FIGHTING(ch) && (GET_OPPONENT(ch) != victim)) {
    percent_chance *= 0.8;
  }

  if(GET_CLASS(ch, CLASS_WARRIOR))
    knockdown_chance = percent_chance*0.15;
  else
    knockdown_chance = percent_chance*0.15;


  vict_lag = 2;

  knockdown_chance *= ((double)BOUNDED(8, 10+(GET_LEVEL(ch) - GET_LEVEL(victim))/10, 11))/10;

  knockdown_chance *= ((double)BOUNDED(90, 50 + GET_C_DEX(ch)/2, 110))/100;

  if(IS_AFFECTED(victim, AFF_AWARE)) {
    knockdown_chance *= 0.93;
  }

  vict_size = (GET_ALT_SIZE(victim)) +
    ((IS_RIDING(victim) &&
    (GET_ALT_SIZE(victim->riding) >= GET_ALT_SIZE(victim)))
    ?1:0);

  ch_size = GET_ALT_SIZE(ch);

  dam = 40 + (int) (1.7 *  number(1, GET_CHAR_SKILL(ch, SKILL_KICK)));
  if(vict_size > ch_size + 1) {
    knockdown_chance = 0;
    dam /= 2;
  }

  if(vict_size < ch_size - 1) {
    percent_chance *= 0.8;
    knockdown_chance *= 0.5 - BOUNDED(0, (ch_size - vict_size + 1)*0.1, 0.4);
    vict_lag = 1;
    dam = dam * 1.5;
  }


  if(vict_size > ch_size) {
    knockdown_chance *= 0.9;
  }

  if(vict_size < ch_size) {
    knockdown_chance *= 1.1;
  }

  if(GET_POS(victim) != POS_STANDING) {
    knockdown_chance = 0;
  }

  knockdown_chance =
    takedown_check(ch, victim, knockdown_chance, SKILL_KICK, TAKEDOWN_ALL);

  if(knockdown_chance == TAKEDOWN_CANCELLED) {
    return;
  } else if(knockdown_chance == TAKEDOWN_PENALTY) {
    knockdown_chance = 0;
  }

  percent_chance = BOUNDED(1, percent_chance, 95);

  if(IS_NPC(ch) && (number(0, 50) > percent_chance)) {
    return;
  }

  act("You tense up, preparing to kick $N with your rear legs..",
    FALSE, ch, 0, victim, TO_CHAR);

  CharWait(ch, PULSE_VIOLENCE*2);

  if(percent_chance<number(1,100)) {
    notch_skill(ch, SKILL_KICK, (int)get_property("skill.notch.", 5.));

        act("But fail miserably!",
      FALSE, ch, 0, victim, TO_CHAR);
        act("You narrowly avoid $n's hooves!",
      FALSE, ch, 0, victim, TO_VICT);
    act("$n attempts to kick $N but fails miserably!",
      FALSE, ch, 0, victim, TO_NOTVICT);

//
    if(number(0,1)) {
      SET_POS(ch, POS_SITTING + GET_STAT(ch));
      act("You land on your ass with a stunning force!",
        FALSE, ch, 0, victim, TO_CHAR);
      act("WHOP! $n landed heavily on $s ass!",
        FALSE, ch, 0, victim, TO_ROOM);
      CharWait(ch, PULSE_VIOLENCE*3);
      damage(ch, ch, 10, DAMAGE_FALLING);
    } else {
      SET_POS(ch, POS_STANDING + STAT_NORMAL);
    }
//
    if(!IS_FIGHTING(victim)) {
        if(IS_NPC(victim))
            MobStartFight(victim, ch);
          else
            set_fighting(victim, ch);
      } else
      if(!IS_FIGHTING(ch))
        set_fighting(ch, victim);

    } else {
    act("You shift your weight and viciously slam your rear hooves into $N with a &+Wstunning&n force!", FALSE, ch, 0, victim, TO_CHAR);
    act("$n shifts $s weight and viciously slams $s rear hooves into you with a &+Wstunning&n force!", FALSE, ch, 0, victim, TO_VICT);
    act("$n shifts $s weight and viciously slams $s rear hooves into $N's chest with a stunning force.", FALSE, ch, 0, victim, TO_NOTVICT);

    notch_skill(ch, SKILL_KICK, (int)get_property("skill.notch.", 2.));

    if(damage(ch, victim, dam, TYPE_UNDEFINED)) {
      return;
    }

    if((knockdown_chance + number(1,20)) > number(1,100))
    {
       Stun(victim, ch, PULSE_VIOLENCE * 2, TRUE);
       if(IS_AFFECTED2(victim, AFF2_STUNNED))
       {
         act("Your kick stuns $N!", FALSE, ch, 0, victim, TO_CHAR);
         act("You are STUNNED!", FALSE, ch, 0, victim, TO_VICT);
         act("$N is stunned by $n's mighty kick!", FALSE, ch, 0, victim, TO_NOTVICT);
       }
    }

    if(knockdown_chance > number(1,100)) {
      set_short_affected_by(ch, SKILL_BASH, (int)(2.8*PULSE_VIOLENCE));
      act("$n is knocked to the ground!", FALSE, victim, 0, 0, TO_ROOM);
      send_to_char("You are knocked to the ground!\n", victim);
      SET_POS(victim, POS_SITTING + GET_STAT(victim));
      CharWait(victim, vict_lag*PULSE_VIOLENCE);
    }
  }
*/

void do_trample(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL, mount = NULL;
	int knockdown_chance;
	int percent_chance;
	int dam, vict_lag;
	int ch_size, vict_size;
	bool is_knight;
	char name[MAX_INPUT_LENGTH];
	struct damage_messages messages = {
		"You shift your weight and viciously slam your rear hooves into $N with a &+Wstunning&n force!",
		"$n's hooves crash into you with a &+Wstunning&n force!",
		"$n's hooves crash into $N's chest with a stunning force.",
		"You shift your weight and viciously slam your rear hooves into $N, you feel this was the last thing $E could take.",
		"$n's hooves come at incredible speed right towards your face, BAANGGG!!! Noises around slowly fade as you fall into darkness.",
		"$n shifts $s weight and viciously slams $s rear hooves into $N's chest which collapses with a loud CRUNCH.",
		0,
		0
	};

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (!SanityCheck(ch, "trample"))
		return;

	if (GET_CHAR_SKILL(ch, SKILL_MOUNTED_COMBAT) < 1)
	{
		send_to_char("Your skill with a mount is horrible.\r\n", ch);
		return;
	}

	mount = get_linked_char(ch, LNK_RIDING);
	if (!mount)
	{
		send_to_char("You can do this only while riding a mount!\n", ch);
		return;
	}

	if (affected_by_spell(ch, SKILL_BASH))
	{
		send_to_char("You haven't reoriented the mount yet enough for another trample!\n",
			     ch);
		return;
	}

	one_argument(argument, name);
	if (*name)
	{
		victim = get_char_room_vis(ch, name);
	}

	if (victim && (mount == victim))
	{
		send_to_char("&+LYour mount cannot trample itself!\r\n", ch);
		return;
	}

	if ((victim == NULL) && IS_FIGHTING(ch))
	{
		victim = GET_OPPONENT(ch);
	}

	if (victim == NULL)
	{
		send_to_char("Trample who or what?\r\n", ch);
		return;
	}

	if (!CanDoFightMove(ch, victim))
	{
		return;
	}

	if (IS_BLIND(ch))
	{
		send_to_char("&+LDang... someone turned out the lights!\n", ch);
		return;
	}

	if (!IS_IMMOBILE(mount) && !IS_BLIND(mount))
	{
		switch (number(1, 3))
		{
		case 1:
			send_to_char("You nudge your mount into &+RBATTLE!!!\n", ch);
			break;
		case 2:
			send_to_char("You lean into your saddle for the engagement!!!\n", ch);
			break;
		case 3:
			send_to_char("You direct your battle steed into action!!!\n", ch);
			break;
		}
	}
	else
	{
		send_to_char("Your mount is afflicted and cannot heed your commands.\n\r", ch);
		return;
	}

	victim = guard_check(ch, victim);

	is_knight = has_innate(ch, INNATE_KNIGHT);

	percent_chance = (95 * GET_CHAR_SKILL(ch, SKILL_MOUNTED_COMBAT)) / 100;

	knockdown_chance = (int)(percent_chance * get_property("skill.trample.knockdown", 0.750));

	vict_lag = 2;

	knockdown_chance =
		(int)(knockdown_chance *
		      ((double)BOUNDED(8, 10 + (GET_LEVEL(ch) - GET_LEVEL(victim)) / 10, 11)) / 10);
	knockdown_chance =
		(int)(knockdown_chance * ((double)BOUNDED(83, 50 + GET_C_DEX(ch) / 2, 120)) / 100);

	if (IS_AFFECTED(victim, AFF_AWARE))
	{
		knockdown_chance = (int)(knockdown_chance * 0.90);
	}

	vict_size = get_takedown_size(victim);
	ch_size = get_takedown_size(ch);

	dam = 30 + number(1, GET_LEVEL(ch));

	if (is_knight)
	{
		dam = (int)(dam * get_property("skill.trample.Knight.DamageMultiplier", 2.500));
	}

	if (IS_NPC(victim) && (IS_SET(victim->specials.act, ACT_NO_BASH) || IS_ELITE(victim)))
	{
		knockdown_chance = 0;
	}

	// If ch is over 1 size smaller than vict.
	if (ch_size < vict_size - 1)
	{
		knockdown_chance = 0;
		vict_lag = 1;
	}
	// If ch is one size smaller than vict.
	else if (ch_size == vict_size - 1)
	{
		if (IS_DRIDER(victim) || IS_CENTAUR(victim))
			knockdown_chance = 0;
		else if (!is_knight)
			knockdown_chance = (int)(knockdown_chance * 0.5);
	}
	else if ((ch_size <= vict_size) && (IS_DRIDER(victim) || IS_CENTAUR(victim)))
	{
		knockdown_chance = 0;
	}
	// If ch is over 1 size larger than vict.
	if ((ch_size > vict_size + 1) && !(is_knight && (vict_size == ch_size - 2)))
	{
		percent_chance = (int)(percent_chance * 0.9);
		knockdown_chance = (int)(knockdown_chance * 0.20);
		vict_lag = 1;
	}

	if (GET_POS(victim) != POS_STANDING)
	{
		knockdown_chance = 0;
	}

	CharWait(ch, PULSE_VIOLENCE * 2);

	knockdown_chance = takedown_check(ch, victim, knockdown_chance, SKILL_TRAMPLE,
					  TAKEDOWN_ALL & !TAKEDOWN_AGI_CHECK);

	if (knockdown_chance == TAKEDOWN_CANCELLED)
	{
		send_to_char("&+yYour trample attempt fails horribly.\r\n", ch);
		return;
	}
	else if (knockdown_chance == TAKEDOWN_PENALTY)
	{
		knockdown_chance = 0;
	}

	percent_chance = BOUNDED(1, percent_chance, 99);
	int charisma = MAX(0, (int)(((GET_C_CHA(ch) - 100) / 2)));

	if (IS_NPC(ch) && (number(0, 50) > percent_chance))
	{
		return;
	}

	knockdown_chance = BOUNDED(0, knockdown_chance, 80);

	act("You order your mount to trample $N.", FALSE, ch, 0, victim, TO_CHAR);

	if (!notch_skill(ch, SKILL_MOUNTED_COMBAT, get_property("skill.notch.offensive", 7)) &&
	    (percent_chance + charisma) < number(1, 100))
	{
		if (50 + GET_C_DEX(ch) / 2 > number(0, 100) || is_knight)
		{
			act("$N bucks madly disobeying $n's order.", FALSE, ch, 0, mount, TO_ROOM);
			act("$N bucks madly disobeying your order.", FALSE, ch, 0, mount, TO_CHAR);
			SET_POS(ch, POS_STANDING + STAT_NORMAL);
		}
		else
		{
			act("As $N bucks madly you shoot up in the air!", FALSE, ch, 0, mount,
			    TO_CHAR);
			act("As $N bucks madly $n shoots up in the air!", FALSE, ch, 0, mount,
			    TO_ROOM);

			if (50 + GET_C_AGI(ch) / 2 < number(0, 100))
			{
				SET_POS(ch, POS_SITTING + GET_STAT(ch));
				act("You land on your ass with a stunning force!", FALSE, ch, 0,
				    mount, TO_CHAR);
				act("WHOP! $n landed heavily on $s ass!", FALSE, ch, 0, victim,
				    TO_ROOM);
				CharWait(ch, PULSE_VIOLENCE * 3);
			}
			if (damage(ch, ch, number(1, GET_LEVEL(ch)), DAMAGE_FALLING))
				return;
			unlink_char(ch, mount, LNK_RIDING);
		}
	}
	else
	{
		engage(ch, victim);

		if (melee_damage(mount, victim, dam, PHSDAM_NOENGAGE | PHSDAM_TOUCH, &messages))
		{
			return;
		}

		if (IS_PC(ch) && GET_POS(victim) == POS_STANDING)
		{
			debug("TRAMPLE: (%s) trying to trample with (%d) percent knock down. Victim is (%s).",
			      GET_NAME(ch), knockdown_chance, GET_NAME(victim));
		}

		if (knockdown_chance > number(1, 100))
		{
			set_short_affected_by(ch, SKILL_BASH, (int)(2.8 * PULSE_VIOLENCE));
			act("$n is knocked to the ground!", FALSE, victim, 0, 0, TO_ROOM);
			send_to_char("You are knocked to the ground!\n", victim);
			SET_POS(victim, POS_SITTING + GET_STAT(victim));
			update_group_vitals(victim);
			gmcp_char_vitals(victim);
			CharWait(victim, vict_lag * PULSE_VIOLENCE);
		}
	}
}

void do_bodyslam(P_char ch, char *arg, int /*cmd*/)
{
	char Gbuf1[MAX_STRING_LENGTH];
	P_char victim = NULL;

	one_argument(arg, Gbuf1);

	if (*Gbuf1)
		victim = get_char_room_vis(ch, Gbuf1);

	if (!victim)
	{
		send_to_char("Bodyslam who?\n", ch);
		return;
	}

	if (IS_RIDING(ch))
	{
		send_to_char("&+mDismount prior to a bodyslam attempt.\r\n", ch);
		return;
	}

	bodyslam(ch, victim);
}

void bodyslam(P_char ch, P_char victim)
{
	int percent_chance;
	struct affected_type af;
	bool fall = TRUE;

	if (!has_innate(ch, INNATE_BODYSLAM))
	{
		send_to_char("You don't feel massive enough to try such a daring maneuver.\n", ch);
		return;
	}

	if (GET_OPPONENT(ch))
	{
		send_to_char("You cannot get enough speed to bodyslam in the midst of combat!\n",
			     ch);
		return;
	}

	victim = guard_check(ch, victim);

	if (!CanDoFightMove(ch, victim))
		return;

	if (should_not_kill(ch, victim))
		return;

	if (GET_VITALITY(ch) < 30)
	{
		send_to_char(
			"You need to gather your energy before attempting to slam someone.\r\n",
			ch);
		return;
	}

	appear(ch);

	percent_chance = get_property("innate.bodyslam.base.chance", 60.00);

	percent_chance =
		(int)(percent_chance *
		      ((double)BOUNDED(80, 100 + GET_LEVEL(ch) - GET_LEVEL(victim), 125)) / 100);
	percent_chance =
		(int)(percent_chance *
		      ((double)BOUNDED(60, 100 + (GET_C_AGI(ch) - GET_C_AGI(victim)) / 2, 155)) /
		      100);

	if (IS_AFFECTED(victim, AFF_AWARE))
	{
		percent_chance = (percent_chance * 8) / 10;
	}

	debug("bodyslam: (%s) bodyslamming (%s) chance (%d).", J_NAME(ch), J_NAME(victim),
	      percent_chance);

	percent_chance =
		takedown_check(ch, victim, percent_chance, SKILL_BODYSLAM, ~TAKEDOWN_AGI_CHECK);

	GET_VITALITY(ch) -= 30;

	if (percent_chance == TAKEDOWN_CANCELLED)
	{
		return;
	}
	else if (percent_chance == TAKEDOWN_PENALTY)
	{
		// should be here, otherwise we might get double messages
	}
	else if (GET_POS(victim) != POS_STANDING)
	{
		act("$n trips over $N, in a futile attempt to slam $M down even further.", FALSE,
		    ch, 0, victim, TO_NOTVICT);
		act("You trip over $N while pointlessly slamming at someone already down.", FALSE,
		    ch, 0, victim, TO_CHAR);
		act("$n trips over you, in a futile attempt to slam you down even further.", FALSE,
		    ch, 0, victim, TO_VICT);
		CharWait(ch, 3 * PULSE_VIOLENCE);
	}
	else if (get_takedown_size(victim) > get_takedown_size(ch))
	{
		act("$n makes a futile attempt to bodyslam $N, but $E is simply immovable.", FALSE,
		    ch, 0, victim, TO_NOTVICT);
		act("$N is too huge for you to bodyslam!", FALSE, ch, 0, victim, TO_CHAR);
		act("$n tries to bodyslam you but merely bounces off your huge girth.", FALSE, ch,
		    0, victim, TO_VICT);
		CharWait(ch, 3 * PULSE_VIOLENCE);
	}
	else if (get_takedown_size(victim) < get_takedown_size(ch) - 2)
	{
		act("$n topples over $mself as $e tries to bodyslam $N.", FALSE, ch, 0, victim,
		    TO_NOTVICT);
		act("$n topples over $mself as $e tries to bodyslam you.", FALSE, ch, 0, victim,
		    TO_VICT);
		send_to_char("You may as well try and bodyslam a speck of dust!  Too small..\n",
			     ch);
		CharWait(ch, 3 * PULSE_VIOLENCE);
	}
	else if (percent_chance >= number(1, 100))
	{
		act("$n suddenly looks a bit dumb, and madly slams at $N!", TRUE, ch, 0, victim,
		    TO_NOTVICT);
		act("$n suddenly looks a bit dumb, and madly slams _YOU_!", TRUE, ch, 0, victim,
		    TO_VICT);
		act("You mindlessly slam $M with your mass!\n", TRUE, ch, 0, victim, TO_CHAR);
		fall = FALSE;
		CharWait(victim, PULSE_VIOLENCE * 3);
		SET_POS(victim, POS_PRONE + GET_STAT(victim));
		engage(ch, victim);
		CharWait(ch, 3 * PULSE_VIOLENCE);
		if (!damage(ch, victim, str_app[STAT_INDEX(GET_C_STR(ch))].todam + 5,
			    SKILL_BODYSLAM))
		{
			if (number(0, 1))
				Stun(victim, ch,
				     number(PULSE_VIOLENCE, (int)(PULSE_VIOLENCE * 2.5)), TRUE);
		}
		else
			return;
	}
	else
	{
		send_to_char("In your haste to slam people around, you slip and fall!\n", ch);
		act("In $s haste to slam $N around, $n slips and falls!", FALSE, ch, 0, victim,
		    TO_NOTVICT);
		act("In $s haste to slam you around, $n slips and falls!", FALSE, ch, 0, victim,
		    TO_VICT);
		CharWait(ch, 2 * PULSE_VIOLENCE);
		if (number(0, 1))
		{
			SET_POS(ch, POS_PRONE + GET_STAT(ch));
			fall = FALSE;
			Stun(ch, ch, PULSE_VIOLENCE, FALSE);
		}
	}

	if (fall)
	{
		if (number(0, 1))
			SET_POS(ch, POS_SITTING + GET_STAT(ch));
		else
			SET_POS(ch, POS_KNEELING + GET_STAT(ch));
	}

	if (!affected_by_spell(victim, SKILL_AWARENESS))
	{
		bzero(&af, sizeof(af));
		af.type = SKILL_AWARENESS;
		af.duration = 2;
		af.bitvector = AFF_AWARE;
		af.flags = AFFTYPE_NODISPEL;
		affect_to_char(victim, &af);
	}
}

// The leaper's lag, in pulses, after a leap that fails.
static int springleap_failed_lag()
{
	return PULSE_VIOLENCE * 2;
}

// The leaper's lag, in pulses, after a leap that lands: on their feet, or falling.
static int springleap_lag()
{
	return PULSE_VIOLENCE;
}

static int springleap_fall_lag()
{
	return (int)(PULSE_VIOLENCE * 1.5);
}

// The target's lag after a leap lands, in pulses.
static int springleap_target_lag()
{
	return (int)(PULSE_VIOLENCE * 1.5);
}

// How long, in pulses, a landed leap keeps the leaper from another.
static int springleap_rest()
{
	return (int)(2.8 * PULSE_VIOLENCE);
}

// Damage to the leaper for leaping at a target already down.
static int springleap_crash_damage(P_char ch)
{
	return GET_MAX_HIT(ch) / 25;
}

// True on the 3 leaps in 4 that a dragon monk lands as a plain leap.
static bool springleap_plain_roll(const Rolls &rolls)
{
	return rolls.number(0, 3);
}

// The damage of a dragon monk's stronger leap.
static int springleap_super_damage(const Rolls &rolls)
{
	return rolls.number(20, 80) + 40;
}

// How long, in pulses, a dragon monk's stronger leap can stun.
static int springleap_super_stun()
{
	return PULSE_VIOLENCE;
}

std::string springleap_facts(P_char ch)
{
	std::string facts =
		fact("Your lag", seconds(springleap_lag()) + ", or " +
					 seconds(springleap_fall_lag()) + " if you fall too") +
		fact("Your lag if it fails or the target is the wrong size",
		     seconds(springleap_failed_lag())) +
		fact("Your lag if the target is asleep",
		     seconds(takedown_sleeping_target_lag()) + " (you attack it instead)") +
		fact("Your lag if the target evades", seconds(takedown_evade_lag())) +
		fact("Damage to you for leaping at a downed target",
		     std::to_string(springleap_crash_damage(ch)) + ", 1/25 of your hit points") +
		fact("Before you can leap again", seconds(springleap_rest())) +
		fact("Target's lag", seconds(springleap_target_lag()));
	if (GET_SPEC(ch, CLASS_MONK, SPEC_WAYOFDRAGON))
		facts += fact("Chance of your dragon leap", "1 in 4") +
			 fact("  Its damage", show({ springleap_super_damage(lowest_rolls),
						     springleap_super_damage(highest_rolls) })) +
			 fact("  Chance it also stuns, if the target fails a save",
			      "1 in 2, for " + seconds(springleap_super_stun()));
	return facts + "  The target must be your size or one bigger.\n";
}

void do_springleap(P_char ch, char *argument, int /*cmd*/)
{
	P_char vict = NULL;
	char name[MAX_INPUT_LENGTH];
	int percent_chance;
	int SUPER_SPRINGLEAP = GET_SPEC(ch, CLASS_MONK, SPEC_WAYOFDRAGON);
	int RANGED_LEAP = 0;
	char arg2[MAX_INPUT_LENGTH];
	int dir = -1;
	int a;

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (!GET_CHAR_SKILL(ch, SKILL_SPRINGLEAP))
	{
		send_to_char("You don't know how to springleap!\n", ch);
		return;
	}

	if (IS_CENTAUR(ch) || GET_RACE(ch) == RACE_QUADRUPED || GET_RACE(ch) == RACE_DRIDER)
	{
		send_to_char("Show us how you'd do it, and you can do it.\n", ch);
		return;
	}

	percent_chance = GET_CHAR_SKILL(ch, SKILL_SPRINGLEAP);

	if (MIN_POS(ch, POS_STANDING + STAT_RESTING))
	{
		send_to_char("You're not in position for that!\n", ch);
		return;
	}

	vict = ParseTarget(ch, argument);

	//------------------------------------------
	// speciality super springleap
	half_chop(argument, name, arg2);

	if (*arg2 && SUPER_SPRINGLEAP)
	{
		if (*arg2)
		{ /* they gave dir */
			switch (toupper(arg2[0]))
			{
			case 'N':
				if (toupper(arg2[1]) == 'W')
					dir = 6;
				else if (toupper(arg2[1]) == 'E')
					dir = 8;
				else
					dir = 0;
				break;
			case 'E':
				dir = 1;
				break;
			case 'S':
				if (toupper(arg2[1]) == 'W')
					dir = 7;
				else if (toupper(arg2[1]) == 'E')
					dir = 9;
				else
					dir = 2;
				break;
			case 'W':
				dir = 3;
				break;
			case 'U':
				dir = 4;
				break;
			case 'D':
				dir = 5;
				break;
			default:
				send_to_char(
					"Invalid direction given.  Use N NW NE E S SW SE W U D\n",
					ch);
				return;
			} /* end case */

			if (!(vict = get_char_ranged(name, ch, 1, dir)))
			{
				send_to_char("Your target doesn't seem to be there.\n", ch);
				return;
			} /* could find victim */

			appear(ch);

			act("$n does a forward roll followed up by a hand-plant into a somersault\nand goes flying out of the room!",
			    FALSE, ch, 0, 0, TO_ROOM);

			act("You do a forward roll followed up by a hand-plant into a somersault\nand go flying toward $N!",
			    FALSE, ch, 0, vict, TO_CHAR);

			SET_POS(ch, POS_STANDING + GET_STAT(ch));
			a = do_simple_move(ch, dir, 0);
			if (!a)
			{
				send_to_char(
					"Contact Tom Cruise, join his next movie, cause you just left the game!.\n",
					ch);
				return; /* failed move */
			}
			char_light(ch);
			room_light(ch->in_room, REAL);
			RANGED_LEAP = 1;
		} // end arg2 check
	}
	// done: speciality super springleap
	//------------------------------------------

	if (!vict)
	{
		send_to_char("Spring-leap at who?\n", ch);
		return;
	}

	if (!CanDoFightMove(ch, vict))
	{
		return;
	}

	appear(ch);

	/* you must be size of centaur to springleap it */
	if ((has_innate(vict, INNATE_HORSE_BODY) || has_innate(vict, INNATE_SPIDER_BODY)) &&
	    (get_takedown_size(ch) < get_takedown_size(vict)))
	{
		act("$n makes a futile attempt to springleap $N, but $E is simply immovable.",
		    FALSE, ch, 0, vict, TO_NOTVICT);
		act("$n makes a futile attempt to springleap you, but you are simply immovable.",
		    FALSE, ch, 0, vict, TO_VICT);
		act("&+WThat damn half-horse half-man is too hefty to springleap!", FALSE, ch, 0,
		    vict, TO_CHAR);

		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		return;
	}

	percent_chance =
		(int)(percent_chance *
		      ((double)BOUNDED(80, 100 + GET_LEVEL(ch) - GET_LEVEL(vict), 125)) / 100);
	percent_chance = takedown_check(ch, vict, percent_chance, SKILL_SPRINGLEAP, TAKEDOWN_ALL);

	if (percent_chance == TAKEDOWN_CANCELLED)
	{
		return;
	}
	else if (percent_chance == TAKEDOWN_PENALTY)
	{
		CharWait(ch, springleap_failed_lag());
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		update_pos(ch);
		return;
	}
	else if (affected_by_spell(ch, SKILL_BASH) || affected_by_spell(ch, SKILL_SPRINGLEAP))
	{
		send_to_char("Such skills take patience!\n", ch);
		return;
	}
	else if ((get_takedown_size(vict) < (get_takedown_size(ch))) ||
		 (get_takedown_size(vict) > (get_takedown_size(ch) + 1)))
	{
		send_to_char("You're not quite the right size to springleap them.\n", ch);

		CharWait(ch, springleap_failed_lag());
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		update_pos(ch);
		return;
	}

	percent_chance = BOUNDED(1, percent_chance, 95);

	if (IS_PC(ch) && IS_PC(vict))
	{
		debug("Springleap (PVP): (%s) springing (%s) with (%d) percent chance.",
		      GET_NAME(ch), GET_NAME(vict), percent_chance);
	}

	if ((GET_POS(vict) < POS_STANDING))
	{
		send_to_char("You fly right over your target and land on your head!\n", ch);
		act("$n passes well above $s target and lands on $s head.", FALSE, ch, 0, 0,
		    TO_NOTVICT);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		CharWait(ch, springleap_failed_lag());
		damage(ch, ch, springleap_crash_damage(ch), SKILL_SPRINGLEAP);
		return;
	}

	if (!notch_skill(ch, SKILL_SPRINGLEAP, get_property("skill.notch.offensive", 7)) &&
	    percent_chance < number(1, 100))
	{
		send_to_char(
			"You manage with complete &+Wincompetence&N to throw yourself head first into the ground!\n",
			ch);

		act("$n, in a show of awesome skill, tackles the ground with $s head.", FALSE, ch,
		    0, 0, TO_NOTVICT);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		CharWait(ch, springleap_failed_lag());
		return;
	}

	percent_chance =
		(int)(percent_chance *
		      ((double)BOUNDED(80, 100 + GET_LEVEL(ch) - GET_LEVEL(vict), 125)) / 100);

	set_short_affected_by(ch, SKILL_SPRINGLEAP, springleap_rest());
	if (RANGED_LEAP)
	{
		act("$n dives in from nearby into a forward roll and leaps into $N!\nwho groans as $n spins around kicking $M in the chest.",
		    FALSE, ch, 0, vict, TO_ROOM);

		act("$N flies in from nearby into a forward roll and leaps right into you!", FALSE,
		    ch, 0, vict, TO_VICT);
		act("You fly into the room, twist around and leap into $N!", FALSE, ch, 0, vict,
		    TO_CHAR);
	}
	if (!SUPER_SPRINGLEAP || (springleap_plain_roll(live_rolls) && SUPER_SPRINGLEAP))
	{
		act("$n's leap knocks into you, sending you slightly off balance...", FALSE, ch, 0,
		    vict, TO_VICT);

		act("Your spring at $N sends $M slightly off balance...", FALSE, ch, 0, vict,
		    TO_CHAR);

		act("$n's leap knocks into $N, sending $M slightly off balance...", FALSE, ch, 0,
		    vict, TO_NOTVICT);
	}
	else
	{
		if (!number(0, 1))
		{
			act("Before you can react you are upside down falling...\n"
			    "...and with lightning speed $n spins around and kicks you in the face...\n"
			    "then somersaults backwards and lands on your chest as you hit the ground!",
			    FALSE, ch, 0, vict, TO_VICT);

			act("You leap low and land a backward sweep knocking $N off $S feet...\n"
			    "...only to follow-up high kicking $M in the face while $E is still falling...\n"
			    "...and as $E strikes ground you do a backward flip landing on $S chest.",
			    FALSE, ch, 0, vict, TO_CHAR);

			act("$n leaps low and lands a backward sweep knocking $N off $S feet...\n"
			    "...only to follow-up high kicking $M in the face while $E is still falling...\n"
			    "...and then does a back flip landing on $N's chest.",
			    FALSE, ch, 0, vict, TO_NOTVICT);
		}
		else
		{
			act("In a blur of speed $n spins around and hits you in the throat...\n"
			    "...and before you can recover leans low and strikes you below the rib...\n"
			    "...then slams a double chi-palm into your chest sending you flying!",
			    FALSE, ch, 0, vict, TO_VICT);

			act("You feign low and strike $N in the throat with the back of your hand...\n"
			    "...then spin low and deliver three quick punches below the ribs...\n"
			    "...only to place a double chi-palm strike sending $M flying!",
			    FALSE, ch, 0, vict, TO_CHAR);

			act("$n feigns low and strikes $N in the throat with the back of $s hand...\n"
			    "...then spins low and delivers three quick punches below the ribs...\n"
			    "...only to place a double chi-palm strike sending $M flying!",
			    FALSE, ch, 0, vict, TO_NOTVICT);
		}

		if (!damage(ch, vict, springleap_super_damage(live_rolls), SKILL_SPRINGLEAP))
		{
			if (number(0, 1))
				Stun(vict, ch, springleap_super_stun(), TRUE);
		}
		else
			return;
	}

	SET_POS(vict, POS_SITTING + GET_STAT(vict));

	CharWait(vict, springleap_target_lag());
	update_pos(vict);
	engage(ch, vict);

	if (percent_chance < number(1, 100))
	{
		act("&+WHowever, you grab $n's leg after $s funny little maneuver and yank $m to the ground!",
		    FALSE, ch, 0, vict, TO_VICT);
		act("&+WUnfortunately. $N grabs your leg and yanks you down to the ground!", FALSE,
		    ch, 0, vict, TO_CHAR);
		act("&+WHowever, $N grabs $n's leg after $s happy little maneuver and pulls $m to the ground!",
		    FALSE, ch, 0, vict, TO_NOTVICT);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		CharWait(ch, springleap_fall_lag());
		update_pos(ch);
	}
	else
	{
		SET_POS(ch, POS_STANDING + GET_STAT(ch));
		CharWait(ch, springleap_lag());
	}
}

// The vitality a whirlwind needs, and what a failed try spends.
static int whirlwind_vitality_needed()
{
	return 50;
}

static int whirlwind_failed_vitality()
{
	return 20;
}

// What a whirlwind takes from vitality regeneration.
static int whirlwind_move_regen()
{
	return (int)(get_property("skill.whirlwind.movement.drain", 60));
}

// How long, in pulses, a whirlwind lasts.
static int whirlwind_duration()
{
	return 3 * PULSE_VIOLENCE;
}

// The blindfighting rating a whirlwind needs while blinded by the spell.
static int whirlwind_blindfighting_needed()
{
	return 80;
}

std::string whirlwind_facts(P_char ch)
{
	return fact("Chance",
		    std::to_string(MAX(0, GET_CHAR_SKILL(ch, SKILL_WHIRLWIND) - 1)) + " in 100") +
	       fact("Vitality needed", std::to_string(whirlwind_vitality_needed())) +
	       fact("Vitality a failed try spends", std::to_string(whirlwind_failed_vitality())) +
	       fact("Vitality regeneration", "-" + std::to_string(whirlwind_move_regen())) +
	       fact("Duration", seconds(whirlwind_duration())) +
	       fact("Blindfighting needed under the blindness spell",
		    std::to_string(whirlwind_blindfighting_needed())) +
	       "  You must be fighting. While it lasts your attacks come about twice as fast\n"
	       "  and each round drains vitality; at none the whirlwind ends.\n";
}

void do_whirlwind(P_char ch, char * /*argument*/, int /*cmd*/)
{
	struct affected_type af;
	int mod = whirlwind_move_regen();

	if (affected_by_spell(ch, SKILL_WHIRLWIND))
	{
		send_to_char("You are fighting at your very best already!\n", ch);
		return;
	}

	if (GET_CHAR_SKILL(ch, SKILL_WHIRLWIND) < 1)
	{
		send_to_char(
			"You are not skilled enough to even attempt such sophisticated technique!\n",
			ch);
		return;
	}

	if (affected_by_spell(ch, SPELL_BLINDNESS))
	{
		if (GET_CHAR_SKILL(ch, SKILL_BLINDFIGHTING) < whirlwind_blindfighting_needed())
		{
			send_to_char(
				"You dare not attack any faster considering your current lack of sight!\n",
				ch);
			return;
		}
		else
		{
			send_to_char(
				"&+WHaving practiced blindfolded before, you ignore your plight and charge!&N\n",
				ch);
		}
	}

	if (!IS_FIGHTING(ch))
	{
		send_to_char("But you aren't engaged!\n", ch);
		return;
	}

	if (GET_VITALITY(ch) < whirlwind_vitality_needed())
	{
		send_to_char("You are too exhausted to fight any faster!\n", ch);
		return;
	}

	if (!notch_skill(ch, SKILL_WHIRLWIND, get_property("skill.notch.offensive", 7)) &&
	    GET_CHAR_SKILL(ch, SKILL_WHIRLWIND) <= number(1, 100))
	{
		send_to_char(
			"You concentrate and charge at your foes with insane speed.. alas, your coordination fails!\n",
			ch);
		act("$n attempts to fight even faster, but $s coordination failed $m.", FALSE, ch,
		    0, 0, TO_ROOM);
		GET_VITALITY(ch) -= whirlwind_failed_vitality();
		return;
	}

	send_to_char(
		"&+WYour mind goes &+wblank &+Wand the world &+wslows down &+Was you become one with the fight.\n",
		ch);
	act("$n turns into a blur of blades as $e charges at $s foes!", FALSE, ch, 0, 0, TO_ROOM);

	memset(&af, 0, sizeof(af));
	af.type = SKILL_WHIRLWIND;
	af.location = APPLY_MOVE_REG;
	af.modifier = -1 * mod;
	af.duration = whirlwind_duration();
	af.flags = AFFTYPE_SHORT;
	affect_to_char(ch, &af);
	/* Not needed -- Eikel
	  bzero(&af, sizeof(af));
	  af.type = SKILL_WHIRLWIND;
	  af.location = APPLY_COMBAT_PULSE;
	  af.modifier = -12;
	  af.duration = 5 * PULSE_VIOLENCE;
	  affect_to_char(ch, &af);*/
}

// The tripper's lag, in pulses: at a target already down or foiling the takedown, on a miss
// and on a hit.
static int trip_foiled_lag()
{
	return 2 * PULSE_VIOLENCE;
}

static int trip_miss_lag()
{
	return PULSE_VIOLENCE * (5 / 2);
}

static int trip_lag()
{
	return (int)(PULSE_VIOLENCE * 2.3);
}

// The target's lag after a hit, in pulses.
static int trip_target_lag()
{
	return (int)(PULSE_VIOLENCE * 1.5);
}

// Damage to the tripper on a miss.
static int trip_miss_damage(P_char ch)
{
	return GET_MAX_HIT(ch) / 25;
}

std::string trip_facts(P_char ch)
{
	return fact("Your lag on a hit", seconds(trip_lag())) +
	       fact("Your lag on a miss", seconds(trip_miss_lag())) +
	       fact("Damage to you on a miss",
		    std::to_string(trip_miss_damage(ch)) + ", a 25th of your hit points") +
	       fact("Your lag if the target is already down or foils it",
		    seconds(trip_foiled_lag())) +
	       fact("Your lag if the target is asleep",
		    seconds(takedown_sleeping_target_lag()) + " (you attack it instead)") +
	       fact("Your lag if the target evades", seconds(takedown_evade_lag())) +
	       fact("Target's lag on a hit", seconds(trip_target_lag())) +
	       "  The target must be your size or one bigger. Centaurs, quadrupeds and\n"
	       "  driders can't trip.\n";
}

void do_trip(P_char ch, char *argument, int /*cmd*/)
{
	P_char vict = NULL;
	char name[MAX_INPUT_LENGTH];
	int percent_chance;

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (GET_CHAR_SKILL(ch, SKILL_TRIP) < 1)
	{
		send_to_char("Battle-field tripping is too acrobatic for you to attempt.\n", ch);
		return;
	}

	if (IS_CENTAUR(ch) || GET_RACE(ch) == RACE_QUADRUPED || GET_RACE(ch) == RACE_DRIDER)
	{
		send_to_char("You worry about breaking your leg and decide not to try.\n", ch);
		return;
	}

	percent_chance = MIN(100, 10 + GET_CHAR_SKILL(ch, SKILL_TRIP));

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
		send_to_char("Trip who?\n", ch);
		return;
	}

	if (IS_FIGHTING(ch) && GET_OPPONENT(vict) != ch && GET_OPPONENT(ch) != vict)
	{
		act("You are locked in combat with someone else and unable to trip $N.&n", FALSE,
		    ch, 0, vict, TO_CHAR);
		return;
	}

	if (!CanDoFightMove(ch, vict))
		return;

	appear(ch);

	/* you must be size of centaur to springleap it */
	if ((has_innate(vict, INNATE_HORSE_BODY) || has_innate(vict, INNATE_SPIDER_BODY) ||
	     GET_RACE(vict) == RACE_QUADRUPED) &&
	    (get_takedown_size(ch) < get_takedown_size(vict) + 1))
	{
		act("$n makes a futile attempt to trip $N, but $E is simply immovable.", FALSE, ch,
		    0, vict, TO_NOTVICT);
		act("$n makes a futile attempt to trip you, but you are simply immovable.", FALSE,
		    ch, 0, vict, TO_VICT);
		act("&+WThat damn half-horse half-man is too hefty to trip!", FALSE, ch, 0, vict,
		    TO_CHAR);

		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		return;
	}

	percent_chance = (int)(percent_chance * ((double)BOUNDED(72, GET_C_AGI(ch), 160)) / 100);
	percent_chance = takedown_check(ch, vict, percent_chance, SKILL_TRIP, TAKEDOWN_ALL);

	if (percent_chance == TAKEDOWN_CANCELLED)
	{
		return;
	}

	engage(ch, vict);

	if (GET_POS(vict) != POS_STANDING)
	{
		act("$N is already on the ground!", FALSE, ch, 0, vict, TO_CHAR);
		send_to_char("But hey you try anyways and you fall on yer ass!\n", ch);
		act("$n does some sort of dance, and winds up flat on $s ass.", TRUE, ch, 0, vict,
		    TO_VICT);
		act("$n seems to dance with $N, but winds up flat on $s ass.", TRUE, ch, 0, vict,
		    TO_NOTVICT);
		stop_singing(ch);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		CharWait(ch, trip_foiled_lag());
		update_pos(ch);
		return;
	}
	else if (percent_chance == TAKEDOWN_PENALTY)
	{
		CharWait(ch, trip_foiled_lag());
		stop_singing(ch);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		update_pos(ch);
		return;
	}
	else if (get_takedown_size(vict) < get_takedown_size(ch))
	{
		send_to_char("Tripping creatures of this minute size is hopeless at best.\n", ch);
		stop_singing(ch);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		return;
	}
	else if (get_takedown_size(vict) > (get_takedown_size(ch) + 1))
	{
		send_to_char("You try to trip, but your opponent is too massive!\n", ch);
		stop_singing(ch);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		return;
	}

	if (!notch_skill(ch, SKILL_TRIP, get_property("skill.notch.offensive", 7)) &&
	    number(1, 100) > percent_chance)
	{
		send_to_char(
			"You manage, with complete incompetence, to throw yourself head-first into the ground!\n",
			ch);
		act("$n, in a show of awesome skill, manages to trip up $mself!", FALSE, ch, 0, 0,
		    TO_ROOM);
		stop_singing(ch);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		CharWait(ch, trip_miss_lag());
		damage(ch, ch, trip_miss_damage(ch), SKILL_TRIP);
		return;
	}

	if (GET_CHAR_SKILL(ch, SKILL_TRIP) - 80 > number(0, 20))
	{
		act("$n dances an amazing maneuver in battle, and trips up $N!", FALSE, ch, 0, vict,
		    TO_NOTVICT);
		act("You do an amazing maneuver, tripping $N.", FALSE, ch, 0, vict, TO_CHAR);
		act("$n dances an amazing maneuver in battle, tripping you.", FALSE, ch, 0, vict,
		    TO_VICT);
		SET_POS(vict, POS_PRONE + GET_STAT(vict));
	}
	else
	{
		act("$n dances an acrobatic maneuver in battle, and trips up $N!", FALSE, ch, 0,
		    vict, TO_NOTVICT);
		act("You do a fancy maneuver, tripping $N.", FALSE, ch, 0, vict, TO_CHAR);
		act("$n dances an acrobatic maneuver in battle, tripping you.", FALSE, ch, 0, vict,
		    TO_VICT);
		SET_POS(vict, POS_SITTING + GET_STAT(vict));
	}

	CharWait(vict, trip_target_lag());
	CharWait(ch, trip_lag());
	update_pos(vict);

	if (number(0, 110) < (GET_C_AGI(vict) - GET_C_AGI(ch)))
	{
		act("&+WHowever, you take $n down with you!", FALSE, ch, 0, vict, TO_VICT);
		act("&+WUnfortunately, $N proves to be quite agile $Mself, and you go down as well.",
		    FALSE, ch, 0, vict, TO_CHAR);
		act("&+Wbut $N manages to take $n down with $M!&N", FALSE, ch, 0, vict, TO_NOTVICT);
		stop_singing(ch);
		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		update_pos(ch);
	}
}

void do_flank(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL;
	char target[128];

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (!GET_CHAR_SKILL(ch, SKILL_FLANK))
	{
		send_to_char("You haven't the slightest clue how to even attempt that.\n", ch);
		return;
	}

	if (IS_GRAPPLED(ch))
	{
		send_to_char(
			"You are locked in close combat and unable to perform a flank maneuver.\r \n",
			ch);
		CharWait(ch, PULSE_VIOLENCE / 2);
		return;
	}

	if (IS_ROOM(ch->in_room, ROOM_SINGLE_FILE))
	{
		send_to_char("There is no room in here to flank...\r\n", ch);
		return;
	}

	if (GET_OPPONENT(ch))
	{
		flank(ch, GET_OPPONENT(ch));
		return;
	}

	one_argument(argument, target);

	if (!(victim = get_char_room_vis(ch, target)))
	{
		send_to_char("Flank who?\n", ch);
	}
	else
		flank(ch, victim);
}

void event_unflank(P_char ch, P_char victim, P_obj /*obj*/, void * /*args*/)
{
	unlink_char(ch, victim, LNK_FLANKING);
}

void flanking_broken(struct char_link_data *cld)
{
	act("$n maneuvers $mself into a better position.", FALSE, cld->linked, NULL, cld->linking,
	    TO_ROOM);
	act("You maneuver yourself into a better position.", FALSE, cld->linked, NULL, cld->linking,
	    TO_CHAR);
}

extern float flank_damage_modifier();

// How long, in pulses, a flank attempt keeps the next one from working.
static int flank_rest()
{
	return PULSE_VIOLENCE * 4;
}

// The flanker's lag, in pulses.
static int flank_lag()
{
	return PULSE_VIOLENCE * 1;
}

// How long, in pulses, the flank holds: shorter when something is fighting the flanker.
static int flank_duration(P_char ch, bool attacked)
{
	return (attacked ? 1 : 3) * ((int)ch->specials.base_combat_round + 1);
}

std::string flank_facts(P_char ch)
{
	const float modifier = flank_damage_modifier();
	const int rating = GET_CHAR_SKILL(ch, SKILL_FLANK);
	return fact("Chance", std::to_string(rating ? MIN(101, rating + 1) : 0) + " in 101") +
	       fact("Damage on the flanked target",
		    std::to_string((int)(modifier * 100)) + "% against a standing target, " +
			    std::to_string((int)((1 + modifier) / 2 * 100)) + "% otherwise") +
	       fact("How long it holds", seconds(flank_duration(ch, false)) + ", or " +
						 seconds(flank_duration(ch, true)) +
						 " if something is fighting you") +
	       fact("Your lag", seconds(flank_lag())) +
	       fact("Before you can flank again", seconds(flank_rest())) +
	       "  Not in a single-file room or while grappled.\n";
}

bool flank(P_char ch, P_char victim)
{
	P_char tch;

	if (!IS_ALIVE(victim))
	{
		send_to_char("You can only flank the living.", ch);
		return FALSE;
	}

	if (get_linked_char(ch, LNK_FLANKING))
	{
		send_to_char("But you are flanking someone already!\n", ch);
		return FALSE;
	}

	if (affected_by_spell(ch, SKILL_FLANK))
	{
		send_to_char("You haven't reoriented yet enough for another attempt!\n", ch);
		return FALSE;
	}

	if (ch == victim)
	{
		send_to_char(
			"You turn around a few times chasing your own buttocks and give up eventually.\n",
			ch);
		return FALSE;
	}

	set_short_affected_by(ch, SKILL_FLANK, flank_rest());

	appear(ch);

	CharWait(ch, flank_lag());

	if (!notch_skill(ch, SKILL_FLANK, get_property("skill.notch.offensive", 15)) &&
	    GET_CHAR_SKILL(ch, SKILL_FLANK) < number(0, 100))
	{
		act("You fail to properly maneuver yourself to attack $N's flank.", FALSE, ch, 0,
		    victim, TO_CHAR);
		act("$n attempts to flank $N, but fails miserably.", FALSE, ch, 0, victim,
		    TO_NOTVICT);
		act("You notice $n's clumsy attempt to flank you and turn to face $m.", FALSE, ch,
		    0, victim, TO_VICT);
		return FALSE;
	}

	for (tch = world[ch->in_room].people; tch; tch = tch->next_in_room)
	{
		if (GET_OPPONENT(tch) == ch)
			break;
	}

	if (GET_OPPONENT(ch) == NULL)
		engage(ch, victim);

	act("You circle $N flanking $M.", FALSE, ch, 0, victim, TO_CHAR);
	act("$n moves around $N in an attempt to flank $M.", FALSE, ch, 0, victim, TO_NOTVICT);
	act("$n sidesteps to the fight in an attempt to flank you.", FALSE, ch, 0, victim, TO_VICT);
	link_char(ch, victim, LNK_FLANKING);
	CharWait(ch, flank_lag());
	add_event(event_unflank, flank_duration(ch, tch), ch, victim, 0, 0, 0, 0);
	return TRUE;
}

// The wait before the dead rise or the ground strikes, in pulses.
static int call_grave_delay(const Rolls &rolls)
{
	return 4 * (5 + rolls.dice(1, 5));
}

// How long, in pulses, a call keeps the caller from another.
static int call_grave_rest()
{
	return (int)(60 * PULSE_VIOLENCE);
}

// The caller's lag, in pulses.
static int call_grave_lag()
{
	return 2 * PULSE_VIOLENCE;
}

// The rating that sets the skeletons: a lich's comes from level.
static int call_grave_skill(P_char ch)
{
	if (GET_RACE(ch) == RACE_LICH)
	{
		return GET_LEVEL(ch) + 50;
	}
	return GET_CHAR_SKILL(ch, SKILL_CALL_GRAVE);
}

// How many skeletons rise: the roll takes away from them.
static int call_grave_count_roll(const Rolls &rolls)
{
	return rolls.number(0, 5);
}

static int call_grave_count(int skill, int roll)
{
	return BOUNDED(1, (skill / 10) - roll, 6);
}

// A skeleton's level: the roll takes away from it.
static int call_grave_level_roll(const Rolls &rolls)
{
	return rolls.number(15, 35);
}

static int call_grave_level(P_char ch, int roll)
{
	return BOUNDED(6, (GET_LEVEL(ch) - roll), 42);
}

// A skeleton's hit points.
static int call_grave_hit_points(const Rolls &rolls, P_char ch)
{
	return (int)(GET_LEVEL(ch) * rolls.number(3, 5));
}

// How long, in pulses, a skeleton stays.
static int call_grave_lifetime(int skill)
{
	return WAIT_SEC * (60 + skill * 3);
}

// A deathlord's strike at a chosen target, before the floor of 1.
static int call_grave_target_damage(const Rolls &rolls, P_char ch)
{
	return 4 * (GET_LEVEL(ch) - 10 + rolls.number(0, 20));
}

std::string call_grave_facts(P_char ch)
{
	const int skill = call_grave_skill(ch);
	std::string facts =
		fact("Delay", seconds(call_grave_delay(lowest_rolls)) + " to " +
				      seconds(call_grave_delay(highest_rolls))) +
		fact("Your lag", seconds(call_grave_lag())) +
		fact("Before you can call again", real_time(call_grave_rest())) +
		fact("Skeletons",
		     show({ call_grave_count(skill, call_grave_count_roll(highest_rolls)),
			    call_grave_count(skill, call_grave_count_roll(lowest_rolls)) })) +
		fact("Skeleton level",
		     show({ call_grave_level(ch, call_grave_level_roll(highest_rolls)),
			    call_grave_level(ch, call_grave_level_roll(lowest_rolls)) })) +
		fact("Skeleton hit points", show({ call_grave_hit_points(lowest_rolls, ch),
						   call_grave_hit_points(highest_rolls, ch) })) +
		fact("Skeletons stay", real_time(call_grave_lifetime(skill)));
	if (GET_SPEC(ch, CLASS_DREADLORD, SPEC_DEATHLORD))
		facts += fact("Damage if you name a target instead",
			      show({ MAX(1, call_grave_target_damage(lowest_rolls, ch)),
				     MAX(1, call_grave_target_damage(highest_rolls, ch)) }));
	return facts + "  You need footing, and the dead can't rise in a single-file room.\n";
}

void do_call_grave(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL;
	char target[128];

	if (!GET_CHAR_SKILL(ch, SKILL_CALL_GRAVE) && !has_innate(ch, INNATE_CALL_GRAVE))
	{
		send_to_char("You haven't the slightest clue how to summon the dead.\n", ch);
		return;
	}

	if (!HAS_FOOTING(ch))
	{
		send_to_char("There is no ground here fit for corpses.\n", ch);
		return;
	}

	if (affected_by_spell(ch, SKILL_CALL_GRAVE))
	{
		send_to_char("You must wait to call your dead brethren.\n", ch);
		return;
	}

	act("&+LYou draw the power of the damned and beckon them to rise.", FALSE, ch, 0, 0,
	    TO_CHAR);

	act("&+L$n &+Lstarts an ominous chant ending with a loud &+WHOWL&+L.\n"
	    "&+LAll is deathly still, but the air seems to grow thicker and thicker.",
	    FALSE, ch, 0, 0, TO_NOTVICT);

	one_argument(argument, target);

	if (*target)
	{
		if (!(victim = get_char_room_vis(ch, target)))
		{
			send_to_char("Your brethren cannot find your enemy here.\n", ch);
			return;
		}
	}

	if (GET_SPEC(ch, CLASS_DREADLORD, SPEC_DEATHLORD) && victim)
		add_event(event_call_grave_target, call_grave_delay(live_rolls), ch, victim, NULL,
			  0, 0, 0);
	else
		add_event(event_call_grave, call_grave_delay(live_rolls), ch, NULL, NULL, 0, 0, 0);

	set_short_affected_by(ch, SKILL_CALL_GRAVE, call_grave_rest());
	CharWait(ch, call_grave_lag());
	notch_skill(ch, SKILL_CALL_GRAVE, get_property("skill.notch.callGrave", 10));
}

void event_call_grave(P_char ch, P_char /*victim*/, P_obj /*obj*/, void * /*data*/)
{
	int i, num, skill;
	P_char skeleton;

	if (IS_ROOM(ch->in_room, ROOM_SINGLE_FILE))
	{
		send_to_char("&+LYou find no corpses in this narrow environment.\r\n", ch);
		return;
	}

	act("&+LThe ground starts to buckle and crack as &+Wskeletons &+Lburst from the ground.",
	    FALSE, ch, 0, 0, TO_CHAR);

	act("&+LThe ground trembles, only to buckle and crack as &+Wskeletons &+Lrise from their cold graves.",
	    FALSE, ch, 0, 0, TO_NOTVICT);

	skill = call_grave_skill(ch);

	num = call_grave_count(skill, call_grave_count_roll(live_rolls));

	for (i = 0; i < num; i++)
	{
		skeleton = read_mobile(16, VIRTUAL);

		if (!skeleton)
		{
			send_to_char("something is wacked, tell a god\n", ch);
			return;
		}

		skeleton->player.level = call_grave_level(ch, call_grave_level_roll(live_rolls));

		if (!number(0, 4))
			skeleton->player.m_class = CLASS_WARRIOR;
		else if (!number(0, 5))
			skeleton->player.m_class = CLASS_DREADLORD;
		else
			skeleton->player.m_class = CLASS_NONE;

		GET_MAX_HIT(skeleton) = GET_HIT(skeleton) = skeleton->points.base_hit =
			call_grave_hit_points(live_rolls, ch);

		MonkSetSpecialDie(skeleton);
		skeleton->points.hitroll = (int)GET_LEVEL(skeleton) / 2;
		skeleton->points.damroll = (int)GET_LEVEL(skeleton) + 10;

		char_to_room(skeleton, ch->in_room, -2);
		setup_pet(skeleton, ch, GET_LEVEL(ch) / 2 + number(0, 10), PET_NOCASH);
		skeleton->only.npc->aggro_flags = 0;

		add_follower(skeleton, ch);
		// 1 Minute + 5 Mins at 100 skill.
		add_event(event_bye_grave, call_grave_lifetime(skill), skeleton, NULL, NULL, 0, 0,
			  0);
	}
}

void event_call_grave_target(P_char ch, P_char victim, P_obj /*obj*/, void * /*data*/)
{
	int dmg = 0;

	act("Skeletons and other abominations rise from the cold graves tearing and clawing at $N's flesh.",
	    FALSE, ch, 0, victim, TO_CHAR);

	act("Skeletons and other abominations rise from the cold graves tearing and clawing at $N's flesh.",
	    FALSE, ch, 0, victim, TO_NOTVICT);

	act("Skeletons and other abominations rise from the cold graves tearing and clawing at your flesh.",
	    FALSE, ch, 0, victim, TO_VICT);

	// damage: [dreadlord_level +- 1d10] hp
	dmg = call_grave_target_damage(live_rolls, ch);

	damage(ch, victim, MAX(1, dmg), TYPE_UNDEFINED);
}

void event_bye_grave(P_char ch, P_char /*victim*/, P_obj /*obj*/, void * /*data*/)
{
	if (ch->following && ch->in_room == ch->following->in_room)
	{
		act("$N &nturns toward you and bows slightly before vanishing, "
		    "sinking back into its cold grave.",
		    FALSE, ch->following, 0, ch, TO_CHAR);

		act("$N &nturns toward $n and bows slightly before vanishing, "
		    "sinking back into its cold grave.",
		    FALSE, ch->following, 0, ch, TO_NOTVICT);
	}
	else
	{
		if (ch->following)
		{
			send_to_char("&+LYour called &+Wskeleton &+Lreturns to its cold grave.\n",
				     ch->following);
		}
	}
	extract_char(ch);
}

void do_battle_orders(P_char ch, char *argument, int /*cmd*/)
{
	char target[128];
	P_char victim = NULL;

	one_argument(argument, target);

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (!ch->group || ch->group->ch != ch)
	{
		send_to_char("You must be commanding a force to use this.\n", ch);
		return;
	}

	if (!(victim = get_char_room_vis(ch, target)))
	{
		send_to_char("Target who?\n", ch);
		return;
	}

	battle_orders(ch, victim);
}

// The commander's lag, in pulses.
static int battle_orders_lag()
{
	return (int)(1.5 * PULSE_VIOLENCE);
}

// How long, in pulses, orders keep the commander from giving more.
static int battle_orders_rest()
{
	return (int)(5 * PULSE_VIOLENCE);
}

std::string battle_orders_facts(P_char ch)
{
	return fact("Chance", std::to_string(GET_CHAR_SKILL(ch, SKILL_BATTLE_ORDERS)) +
				      " in 101; luck can raise it") +
	       fact("Your lag", seconds(battle_orders_lag())) +
	       fact("Before you can give orders again", seconds(battle_orders_rest())) +
	       "  You must lead a group. A failed order can send it at random targets.\n";
}

void battle_orders(P_char ch, P_char victim)
{
	P_char gch, tmp;
	struct group_list *group;
	int percent_chance;

	if (affected_by_spell(ch, SKILL_BATTLE_ORDERS))
	{
		send_to_char("You need to rest a while before attempting this again.\n", ch);
		return;
	}

	percent_chance = GET_CHAR_SKILL(ch, SKILL_BATTLE_ORDERS);

	if (GET_C_LUK(ch) / 2 > number(0, 100))
	{
		percent_chance = (int)(percent_chance * 1.1);
	}

	if (notch_skill(ch, SKILL_BATTLE_ORDERS, get_property("skill.notch.switch", 10)) ||
	    percent_chance > number(0, 100))
	{
		act("You shout out your orders.", FALSE, ch, 0, victim, TO_CHAR);
		act("Your skin crawls as $n directs his troops in a hollow voice.", FALSE, ch, 0,
		    victim, TO_NOTVICT);

		group = ch->group;

		while (group)
		{
			gch = group->ch;

			clear_links(gch, LNK_BATTLE_ORDERS);
			link_char(gch, victim, LNK_BATTLE_ORDERS);

			group = group->next;
		}
	}
	else
	{
		if (50 > number(0, 100))
		{
			act("You shout out your orders, but no one hears you over the fighting.",
			    FALSE, ch, 0, victim, TO_CHAR);
		}
		else
		{
			act("You shout out your orders. Hmm, what was it you really ordered?",
			    FALSE, ch, 0, victim, TO_CHAR);
			act("Your skin crawls as $n directs his troops in a hollow voice.", FALSE,
			    ch, 0, victim, TO_NOTVICT);

			group = ch->group;

			while (group)
			{
				gch = group->ch;
				tmp = get_random_char_in_room(ch->in_room, ch,
							      DISALLOW_SELF | DISALLOW_GROUPED);
				if (tmp)
					link_char(gch, tmp, LNK_BATTLE_ORDERS);

				group = group->next;
			}
		}
	}

	CharWait(ch, battle_orders_lag());
	set_short_affected_by(ch, SKILL_BATTLE_ORDERS, battle_orders_rest());
}

void do_gaze(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL;
	char target[128];

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (GET_CHAR_SKILL(ch, SKILL_GAZE) < 1)
	{
		act("You stare deep into $N's eyes... Fascinating.", FALSE, ch, 0, victim, TO_CHAR);
		return;
	}

	one_argument(argument, target);

	if (!(victim = get_char_room_vis(ch, target)))
	{
		if (GET_OPPONENT(ch))
		{
			gaze(ch, GET_OPPONENT(ch));
		}
		else
		{
			send_to_char("Gaze at who?\n", ch);
		}
	}
	else
	{
		gaze(ch, victim);
	}
}

// The gazer's lag, in pulses, by what happened.
static int gaze_refused_lag()
{
	return PULSE_VIOLENCE;
}

static int gaze_resisted_lag()
{
	return (int)(2.5 * PULSE_VIOLENCE);
}

static int gaze_size_lag()
{
	return (int)(0.5 * PULSE_VIOLENCE);
}

static int gaze_lag()
{
	return 2 * PULSE_VIOLENCE;
}

// How long, in pulses, a hit dazes the target and keeps the gazer from the next takedown.
static int gaze_target_duration()
{
	return (int)(PULSE_VIOLENCE * 1.5);
}

static int gaze_rest()
{
	return (int)(PULSE_VIOLENCE * 3.0);
}

// An NPC target's lag after a hit, in pulses.
static int gaze_npc_lag()
{
	return (int)(0.75 * PULSE_VIOLENCE);
}

// The anatomy score in the hit points below which a gaze or restraint kills.
static int anatomy_kill_bonus(P_char ch)
{
	return GET_CHAR_SKILL(ch, SKILL_ANATOMY) - 25;
}

// A target below this many hit points dies from a gaze.
static int gaze_kill_hit_points(const Rolls &rolls, int anatomy_skill)
{
	return (int)(((rolls.number(0, 100) + anatomy_skill)) / 2);
}

std::string gaze_facts(P_char ch)
{
	return fact("Your lag", seconds(gaze_lag())) +
	       fact("Your lag if refused",
		    seconds(gaze_refused_lag()) + " (no eyes, no fear, or blind)") +
	       fact("Your lag if already dazed, elite or a greater NPC",
		    seconds(gaze_resisted_lag())) +
	       fact("Your lag if the size is too far off", seconds(gaze_size_lag())) +
	       fact("Target dazed on a hit", seconds(gaze_target_duration())) +
	       fact("An NPC target's lag on a hit", seconds(gaze_npc_lag())) +
	       fact("Before your next takedown after a hit", seconds(gaze_rest())) +
	       fact("A hit kills a target below",
		    "up to " +
			    std::to_string(
				    gaze_kill_hit_points(highest_rolls, anatomy_kill_bonus(ch))) +
			    " hit points, with your anatomy") +
	       "  The target can be up to 1 size bigger or 2 smaller.\n";
}

void gaze(P_char ch, P_char victim)
{
	int percent_chance, anatomy_skill, standing = 1, battling = 1;
	P_char temp_ch;

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (ch == victim)
	{
		send_to_char("You pull out a small mirror and stare into it for a few seconds.\n",
			     ch);
		CharWait(ch, gaze_refused_lag());
		return;
	}

	appear(ch);

	if (victim == (temp_ch = get_linked_char(ch, LNK_FLANKING)))
	{
		send_to_char("How can you gaze into the eyes of someone that isn't facing you?\r\n",
			     ch);
		return;
	}

	if (has_innate(victim, INNATE_EYELESS))
	{
		send_to_char(
			"&+LYour victim is eyeless like you, thus your gaze has no effect!\r\n",
			ch);
		CharWait(ch, gaze_refused_lag());
		return;
	}

	if (IS_AFFECTED4(victim, AFF4_NOFEAR))
	{
		act("$N &+Wgazes right back at you, completely immune to the fear.", FALSE, ch, 0,
		    victim, TO_CHAR);
		CharWait(ch, gaze_refused_lag());
		return;
	}

	if (affected_by_spell(victim, SKILL_GAZE))
	{
		act("$N &+yis already &+Yterrifed!!!&n", FALSE, ch, 0, victim, TO_CHAR);
		CharWait(ch, gaze_resisted_lag());
		return;
	}

	if (IS_BLIND(victim))
	{
		send_to_char("&+LThey can't see anything right now, especially you!\n", ch);
		act("$N never notices $n's sightless &+Lstare.&n", FALSE, ch, 0, victim,
		    TO_NOTVICT);
		CharWait(ch, gaze_refused_lag());
		return;
	}

	if (affected_by_spell(ch, SKILL_BASH))
	{
		send_to_char("You need to rest a while before attempting this again.\n", ch);
		return;
	}

	if (IS_NPC(victim) && (IS_GREATER_RACE(victim) || IS_ELITE(victim)))
	{
		act("You turn your &+Lstare&n toward $N, but it simply &+yhisses&n at you!", FALSE,
		    ch, 0, victim, TO_CHAR);
		act("$N turns towards $n and hisses a deep monotone sound...", FALSE, ch, 0, victim,
		    TO_NOTVICT);
		act("You turn towards $N and hiss a deep monotone sound...", FALSE, ch, 0, victim,
		    TO_VICT);
		do_action(ch, 0, CMD_SHIVER);
		CharWait(ch, gaze_resisted_lag());
		return;
	}

	if (get_takedown_size(victim) > get_takedown_size(ch) + 1)
	{
		act("You try to hold $N with your gaze but $E's just too tall.", FALSE, ch, 0,
		    victim, TO_CHAR);
		act("$n tries to hold $N with $s gaze but $E's just too tall.", FALSE, ch, 0,
		    victim, TO_NOTVICT);
		act("$n tries to hold you with $s gaze but $E's just too short.", FALSE, ch, 0,
		    victim, TO_VICT);
		CharWait(ch, gaze_size_lag());
		return;
	}

	if (get_takedown_size(victim) < get_takedown_size(ch) - 2)
	{
		act("You try to hold $N with your gaze but $E's just too short.", FALSE, ch, 0,
		    victim, TO_CHAR);
		act("$n tries to hold $N with $s gaze but $E's just too short.", FALSE, ch, 0,
		    victim, TO_NOTVICT);
		act("$n tries to hold you with $s gaze but $E's just too tall.", FALSE, ch, 0,
		    victim, TO_VICT);
		CharWait(ch, gaze_size_lag());
		return;
	}

	if (!on_front_line(ch))
	{
		act("$N is too far away for you to lock $M with your gaze.", FALSE, ch, 0, victim,
		    TO_CHAR);
		return;
	}

	// any conditions past this will lag the char for the full duration
	CharWait(ch, gaze_lag());

	if (!on_front_line(victim) && number(0, 2)) // 33% chance to gaze someone back'd
	{
		act("$N is too far away for you to lock $M with your gaze.", FALSE, ch, 0, victim,
		    TO_CHAR);
		return;
	}

	percent_chance = GET_CHAR_SKILL(ch, SKILL_GAZE); // Base percentage

	if (GET_POS(victim) != POS_STANDING)
	{
		act("$E is not in a proper position, but you try anyway!", FALSE, ch, 0, victim,
		    TO_CHAR);
		act("$n has difficulty locking $N with $s eyeless stare.", FALSE, ch, 0, victim,
		    TO_NOTVICT);
		act("$n has difficulty locking you with $s eyeless stare.", FALSE, ch, 0, victim,
		    TO_VICT);
		percent_chance /= 5; // Reduced chance to gaze a non standing opponent.
	}

	if (get_takedown_size(victim) == get_takedown_size(ch) + 1 ||
	    get_takedown_size(victim) == get_takedown_size(ch) - 2)
	{
		percent_chance = (int)(percent_chance * 0.6);
	}

	if (GET_C_LUK(ch) / 2 > number(0, 110))
	{
		percent_chance = (int)(percent_chance * 1.05);
	}

	if (GET_C_LUK(victim) / 2 > number(0, 90))
	{
		percent_chance = (int)(percent_chance * 0.95);
	}

	percent_chance = (int)(percent_chance * GET_C_POW(ch) / GET_C_POW(victim)) + GET_LEVEL(ch) -
			 GET_LEVEL(victim) + number(-15, 0);

	percent_chance = BOUNDED(1, percent_chance, 90);

	if (IS_ROOM(ch->in_room, ROOM_SINGLE_FILE) && !AdjacentInRoom(ch, victim) &&
	    !IS_TRUSTED(ch))
	{
		act("$N is difficult to gaze because this area is narrow.", FALSE, ch, 0, victim,
		    TO_CHAR);
		percent_chance = (int)(percent_chance * 0.65);
	}

	if (IS_FIGHTING(ch) && GET_OPPONENT(victim) != ch && GET_OPPONENT(ch) != victim)
	{
		act("You aren't battling $N, but you notice $M across the &+rfield of battle...&n",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$n sweeps $s &+Lsightless stare&n across the &+rfield of battle.&n", FALSE, ch,
		    0, victim, TO_NOTVICT);
		act("$n has difficulty locking you with $s eyeless &+Lstare.&n", FALSE, ch, 0,
		    victim, TO_VICT);

		percent_chance = (int)(percent_chance * 0.40);
	}

	// DEBUG CODE SECTION ---------------------

	if (GET_POS(victim) != POS_STANDING)
	{
		standing = 0;
	}

	if (IS_FIGHTING(ch) && GET_OPPONENT(victim) != ch && GET_OPPONENT(ch) != victim)
	{
		battling = 0;
	}

	debug("GAZE: (%s) with (%d) percent at (%s&n) - standing? (%d) battling? (%d).",
	      GET_NAME(ch), percent_chance, J_NAME(victim), standing, battling);
	// ---------------------------------------

	if (notch_skill(ch, SKILL_GAZE, get_property("skill.notch.offensive", 7)) ||
	    percent_chance > number(0, 100))
	{
		anatomy_skill = anatomy_kill_bonus(ch); // returns -25 to 70 int

		if (GET_HIT(victim) < gaze_kill_hit_points(live_rolls, anatomy_skill))
		{
			if (GET_CLASS(ch, CLASS_AVENGER))
			{
				act("Your powerful will easily dominates the inferior creature before you.\n"
				    "You draw $S soul into your essence sentencing $M to judgement.\n"
				    "The guilt is obvious for there are so few true of heart. You strip\n"
				    "the body of the soul and let the dead husk topple to the ground.",
				    FALSE, ch, 0, victim, TO_CHAR);
				act("As you stare into&n $N's bottomless eyes you loose yourself\n"
				    "in the endless void. Powers beyond your understanding probe your soul\n"
				    "judging your deeds. The verdict is one - guilty. Your soul is ripped\n"
				    "from your body and the now dead husk topples to the ground.",
				    FALSE, ch, 0, victim, TO_VICT);
				act("$N shudders as $E tries, and fails, to break free of the will of $n.\n"
				    "A second of silence passes before simply utters a silent sigh and topples over dead.",
				    FALSE, ch, 0, victim, TO_NOTVICT);
			}
			else
			{
				act("You turn your eyeless stare toward $N freezing $M with\n"
				    "your gaze. Prying into $S mind you clutch $S heart in a\n"
				    "deadly embrace. You throw back your head and let out a mocking\n"
				    "laughter as $N, groaning and clawing at $S chest, crumbles\n"
				    "in a lifeless heap.",
				    FALSE, ch, 0, victim, TO_CHAR);
				act("As you meet $n's eyeless gaze stark terror overwhelms\n"
				    "you. Grimacing, you clutch at your chest as a chilling cold\n"
				    "fills your heart. You grunt as the pain spreads and you begin\n"
				    "wobble. As your legs buckle and darkness consumes you, the\n"
				    "last thing you hear is the mocking laughter ringing in your\n"
				    "ears...",
				    FALSE, ch, 0, victim, TO_VICT);
				act("$N turns ashen and struggles to turn away as $n locks\n"
				    "$M with $s gaze. Suddenly $S eyes seem to bulge and shudders\n"
				    "wrack $S body. Moments later $E cries out and claws at $S chest\n"
				    "as $E topples to the ground.",
				    FALSE, ch, 0, victim, TO_NOTVICT);
			}
			die(victim, ch);
		}
		else
		{
			if (GET_CLASS(ch, CLASS_AVENGER))
			{
				act("&+WYou stare at&n $N &+Wforcing $M into &+wsubmission.&n",
				    FALSE, ch, 0, victim, TO_CHAR);
				act("$N &+wis lost in thought as $E meets&n $n's &+wgaze.", FALSE,
				    ch, 0, victim, TO_NOTVICT);
				act("&+WCalming visions sweep over you as you gaze into&n $n's &+Weyes.&n",
				    FALSE, ch, 0, victim, TO_VICT);
			}
			else
			{
				act("You turn your &+Leyeless stare&n toward $N freezing $M with your gaze.",
				    FALSE, ch, 0, victim, TO_CHAR);
				act("$N &+Lturns ashen and struggles to turn away as&n $n &+Lstares into $S eyes.&n",
				    FALSE, ch, 0, victim, TO_NOTVICT);
				act("&+yThe world ceases to be as&n $n &+yturns $s &+Leyeless gaze&n at you.",
				    FALSE, ch, 0, victim, TO_VICT);
			}

			set_short_affected_by(victim, SKILL_GAZE, gaze_target_duration());
			set_short_affected_by(ch, SKILL_BASH, gaze_rest());
			victim->specials.combat_tics = (int)victim->specials.base_combat_round;

			if (IS_NPC(victim))
			// they can't do any cmds anyway, so lag them so they can stack
			// cmds the same as being bashed, etc.
			{
				CharWait(victim, gaze_npc_lag());
			}
			StopCasting(victim);
			engage(ch, victim);
		}
	}
	else
	{
		act("&+wYou try to lock&n $N &+wwith your gaze but $E turns away.&n", FALSE, ch, 0,
		    victim, TO_CHAR);
		act("$N &+wshivers slightly, but turns away as&n $n &+wlooks at $M.&n", FALSE, ch,
		    0, victim, TO_NOTVICT);
		act("&+wYou avert your eyes as&n $n &+wtries to lock you with $s gaze.&n", FALSE,
		    ch, 0, victim, TO_VICT);
	}
}

// The restrainer's lag, in pulses, by what happened.
static int restrain_refused_lag()
{
	return (int)(PULSE_VIOLENCE);
}

static int restrain_resisted_lag()
{
	return (int)(1.5 * PULSE_VIOLENCE);
}

static int restrain_lag()
{
	return 2 * PULSE_VIOLENCE;
}

// How long, in pulses, a hit restrains and keeps the restrainer from the next takedown.
static int restrain_duration()
{
	return (PULSE_VIOLENCE * 2);
}

static int restrain_rest()
{
	return (int)(PULSE_VIOLENCE * 3.0);
}

// An NPC target's lag after a hit, in pulses.
static int restrain_npc_lag()
{
	return (int)(2.0 * PULSE_VIOLENCE);
}

// A target below this many hit points dies from a restraint.
static int restrain_kill_hit_points(const Rolls &rolls, int anatomy_skill)
{
	return (rolls.number(0, 100) + anatomy_skill) / 2;
}

std::string restrain_facts(P_char ch)
{
	return fact("Your lag", seconds(restrain_lag())) +
	       fact("Your lag if the target just used a takedown",
		    seconds(restrain_refused_lag())) +
	       fact("Your lag if dazed, elite, greater or the wrong size",
		    seconds(restrain_resisted_lag())) +
	       fact("Target restrained on a hit", seconds(restrain_duration())) +
	       fact("An NPC target's lag on a hit", seconds(restrain_npc_lag())) +
	       fact("Before your next takedown after a hit", seconds(restrain_rest())) +
	       fact("A hit kills a target below",
		    "up to " +
			    std::to_string(restrain_kill_hit_points(highest_rolls,
								    anatomy_kill_bonus(ch))) +
			    " hit points, with your anatomy") +
	       "  The target must be within 2 sizes; one not standing is very hard to restrain.\n"
	       "  A hit stops casting, 2 times in 3.\n";
}

void restrain(P_char ch, P_char victim)
{
	int percent_chance, anatomy_skill, standing = 1, battling = 1;
	struct affected_type af;

	if (!ch)
	{
		logit(LOG_EXIT, "restrain: no ch");
		return;
	}

	if (ch == victim)
	{
		send_to_char("&+LOh, but that would be way too much fun...\n", ch);
		CharWait(ch, restrain_refused_lag());
		return;
	}

	appear(ch);

	if (affected_by_spell(victim, SKILL_BASH))
	{
		send_to_char("&+LThey cannot be restrained in their current position.\n", ch);
		CharWait(ch, restrain_refused_lag());
		return;
	}

	if (affected_by_spell(victim, SKILL_GAZE))
	{
		act("$N &+Lappears to be paralyzed as it is!&n", FALSE, ch, 0, victim, TO_CHAR);
		CharWait(ch, restrain_resisted_lag());
		return;
	}

	if (affected_by_spell(ch, SKILL_BASH))
	{
		send_to_char("&+LYour &+rminions &+Lneed rest before restraining again.\n", ch);
		return;
	}

	if (IS_NPC(victim) && (IS_GREATER_RACE(victim) || IS_ELITE(victim)))
	{
		act("&+LYou call your &+rminions &+Lfrom the depths to harness&n $N&+L, but it simply shrugs them away!",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$N &+Lsimply shrugs away&n $n's &+Lattempt to restrain it...", FALSE, ch, 0,
		    victim, TO_NOTVICT);
		act("&+LYou simply shrug away&n $N's &+Lattempt to restrain you...", FALSE, ch, 0,
		    victim, TO_VICT);
		do_action(ch, 0, CMD_GROWL);
		CharWait(ch, restrain_resisted_lag());
		return;
	}

	if (get_takedown_size(victim) > get_takedown_size(ch) + 2)
	{
		act("&+LYou try to restrain&n $N&+L, but it easily breaks free of your &+rrestraints&+L.&n",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$n &+Ltries to restrain&n $N&+L, but &n$E &+Leasily breaks free of the &+rrestraings&+L.&n",
		    FALSE, ch, 0, victim, TO_NOTVICT);
		act("$n's&+L minions attempt to restrain you, but you simply break free of the &+rrestraints&+L.&n",
		    FALSE, ch, 0, victim, TO_VICT);
		CharWait(ch, restrain_resisted_lag());
		return;
	}

	if (get_takedown_size(victim) < get_takedown_size(ch) - 2)
	{
		act("&+LYou try to restrain&n $N&+L, but it easily evades your &+rminions.", FALSE,
		    ch, 0, victim, TO_CHAR);
		act("$n &+Ltries to restrain&n $N &+L, but they easily evade&n $n's &+rminions&n.",
		    FALSE, ch, 0, victim, TO_NOTVICT);
		act("$n &+Ltries to restrain you, but you easily evade the attempt!&n", FALSE, ch,
		    0, victim, TO_VICT);
		CharWait(ch, restrain_resisted_lag());
		return;
	}

	// any conditions past this will lag the char for the full duration
	CharWait(ch, restrain_lag());

	percent_chance = GET_CHAR_SKILL(ch, SKILL_RESTRAIN); // Base percentage

	if (GET_POS(victim) != POS_STANDING)
	{
		act("$E &+Lis not in a proper position to be restrained, but you summon your &+rminions &+Lanyway!",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$n &+Lcalls forth $s &+rminions &+Lwhich have trouble restraining &n$N.",
		    FALSE, ch, 0, victim, TO_NOTVICT);
		act("$n &+Lcalls forth $s &+rminions &+Lwhich have trouble restraining you&n.",
		    FALSE, ch, 0, victim, TO_VICT);
		percent_chance = 0; // Cannot restrain !standing victim.
	}

	if (get_takedown_size(victim) == get_takedown_size(ch) + 2 ||
	    get_takedown_size(victim) == get_takedown_size(ch) - 2)
	{
		percent_chance = (int)(percent_chance * 0.6);
	}

	if (GET_C_LUK(ch) / 2 > number(0, 110))
	{
		percent_chance = (int)(percent_chance * 1.05);
	}

	if (GET_C_LUK(victim) / 2 > number(0, 90))
	{
		percent_chance = (int)(percent_chance * 0.95);
	}

	percent_chance = (int)(percent_chance * GET_C_POW(ch) / GET_C_POW(victim)) + GET_LEVEL(ch) -
			 GET_LEVEL(victim) + number(-15, 5);

	if (IS_ROOM(ch->in_room, ROOM_SINGLE_FILE) && !AdjacentInRoom(ch, victim) &&
	    !IS_TRUSTED(ch))
	{
		act("&+LYour &+rminions &+Lwould have a difficult time in such a narrow area.",
		    FALSE, ch, 0, victim, TO_CHAR);
		percent_chance = (int)(percent_chance * 0.65);
	}

	if (IS_FIGHTING(ch) && GET_OPPONENT(victim) != ch && GET_OPPONENT(ch) != victim)
	{
		act("&+LYou turn from your current victim and direct your &+rsummons&+L toward&n $N&+L...&n",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$n &+Lturns $s focus away from the current fight and makes a strange &+rgesture &+Ltoward &n$N...&n",
		    FALSE, ch, 0, victim, TO_NOTVICT);
		act("$n &+Lturns $s focus away from the current fight and makes a strange &+rgesture &+Ltoward you.&n",
		    FALSE, ch, 0, victim, TO_VICT);

		percent_chance = (int)(percent_chance * 0.40);
	}

	// DEBUG CODE SECTION ---------------------

	if (GET_POS(victim) != POS_STANDING)
	{
		standing = 0;
	}

	if (IS_FIGHTING(ch) && GET_OPPONENT(victim) != ch && GET_OPPONENT(ch) != victim)
	{
		battling = 0;
	}

	percent_chance = BOUNDED(1, percent_chance, 90);

	debug("RESTRAIN: (%s) with (%d) percent at (%s&n) - standing? %s battling? %s.",
	      GET_NAME(ch), percent_chance, J_NAME(victim), YESNO(standing), YESNO(battling));
	// ---------------------------------------

	if (notch_skill(ch, SKILL_RESTRAIN, get_property("skill.notch.offensive", 15)) ||
	    percent_chance > number(0, 100))
	{
		anatomy_skill = anatomy_kill_bonus(ch); // returns -25 to 70 int

		// If hps are low.. like under 100 or so low, we insta-kill?  WTF?
		if (GET_HIT(victim) < restrain_kill_hit_points(live_rolls, anatomy_skill))
		{
			{
				act("&+LYou turn to &n$N &+Land make an un&+who&+Wly &+Lgesture.\n"
				    "&+LA &nsmoking &+Ldark pit opens beneath &n$S feet, the smell of death\n"
				    "&+Land decay fill the air. Suddenly, &+Wskeletal &+Lhands emerge, grasping\n"
				    "$N &+Ltightly! &n$N &+Llets out a final &+rsCCrrREEEaaMM &+Las they\n"
				    "&+Lare whisked away into the &+rabyss&+L.",
				    FALSE, ch, 0, victim, TO_CHAR);
				act("$n&+L turns to you &+Land makes an un&+who&+Wly &+Lgesture.\n"
				    "&+LA &nsmoking &+Ldark pit opens beneath your feet, the smell of death\n"
				    "&+Land decay fill the air. Suddenly, &+Wskeletal &+Lhands emerge, grasping\n"
				    "&+Lyou &+Ltightly! You struggle, but your efforts are fruitless...\n"
				    "&+LWith a final gasp, you cry out a final &+rsCCrrREEEaaMM &+Las you\n"
				    "&+Lare whisked away into the &+rabyss&+L.",
				    FALSE, ch, 0, victim, TO_VICT);
				act("$n&+L turns to &n$N &+Land makes an un&+who&+Wly &+Lgesture.\n"
				    "&+LA &nsmoking &+Ldark pit opens beneath &n$S feet, the smell of death\n"
				    "&+Land decay fill the air. Suddenly, &+Wskeletal &+Lhands emerge, grasping\n"
				    "$N &+Ltightly! &n$N &+Llets out a final &+rsCCrrREEEaaMM &+Las they\n"
				    "&+Lare whisked away into the &+rabyss&+L.",
				    FALSE, ch, 0, victim, TO_NOTVICT);
			}
			die(victim, ch);
		}
		else
		{
			if (GET_CLASS(ch, CLASS_AVENGER))
			{
				act("&+WYou stare at&n $N &+Wforcing $M into &+wsubmission.&n",
				    FALSE, ch, 0, victim, TO_CHAR);
				act("$N &+wis lost in thought as $E meets&n $n's &+wgaze.", FALSE,
				    ch, 0, victim, TO_NOTVICT);
				act("&+WCalming visions sweep over you as you gaze into&n $n's &+Weyes.&n",
				    FALSE, ch, 0, victim, TO_VICT);
			}
			else
			{
				act("&+LYou turn and make an un&+who&+Wly &+Lgesture in&n $N's &+Ldirection...\n"
				    "&+La band of &+Revil &+rminions &+Lsuddenly restrain &n$N&+L!",
				    FALSE, ch, 0, victim, TO_CHAR);
				act("$N &+Lis suddenly overcome by&n $n's &+Lband of un&+who&+Wly &+rminions&+L!&n",
				    FALSE, ch, 0, victim, TO_NOTVICT);
				act("&+LYou suddenly feel unable to move as&n $n's &+rminions &+Lsubdue you!&n",
				    FALSE, ch, 0, victim, TO_VICT);
			}

			memset(&af, 0, sizeof(af));
			af.type = SKILL_RESTRAIN;
			af.flags = AFFTYPE_SHORT | AFFTYPE_NODISPEL;
			af.duration = restrain_duration();
			affect_to_char_with_messages(
				victim, &af,
				"&+LThe &+rminions&+L finally release their hold on you!",
				"$n &+Lfinally breaks free from the &+rminions &+Lrestraining them.");
			set_short_affected_by(ch, SKILL_BASH, restrain_rest());
			victim->specials.combat_tics = (int)victim->specials.base_combat_round;
			// CharWait(victim, (int) (2.0 * PULSE_VIOLENCE));

			// They can't do any cmds anyway, so lag them so they can stack
			// cmds the same as being bashed, etc.
			if (IS_NPC(victim))
			{
				CharWait(victim, restrain_npc_lag());
			}
			if (number(0, 2))
			{
				StopCasting(victim);
			}
			engage(ch, victim);
		}
	}
	else
	{
		act("&+LYour &+rminions&+L attempt to restrain&n $N &+Lbut $E deftly escapes the attack.&n",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("$N &+Lmakes a dextrous move, quickly evading&n $n's &+rminions&+L.&n", FALSE,
		    ch, 0, victim, TO_NOTVICT);
		act("&+LYou quickly jump out of the way of&n $n's &+Levil &+rmionions&+L.&n", FALSE,
		    ch, 0, victim, TO_VICT);
	}
}

// How long, in pulses, a shriek keeps the shrieker from another.
static int shriek_rest()
{
	return (int)(WAIT_SEC * SECS_PER_REAL_MIN * 5);
}

// A shriek's base damage, and the base on a target that saves.
static int shriek_base_damage(int skl_lvl)
{
	return 2 * skl_lvl;
}

static int shriek_saved_damage(int basedamage)
{
	return basedamage / 2;
}

// What the roll adds to the base.
static int shriek_roll_damage(const Rolls &rolls)
{
	return 4 * rolls.number(1, 20);
}

std::string shriek_facts(P_char ch)
{
	const int base = shriek_base_damage(GET_CHAR_SKILL(ch, SKILL_SHRIEK));
	const int low = shriek_roll_damage(lowest_rolls), high = shriek_roll_damage(highest_rolls);
	return fact("Sound damage to each target in the room", show({ base + low, base + high })) +
	       fact("If the target saves",
		    show({ shriek_saved_damage(base) + low, shriek_saved_damage(base) + high })) +
	       fact("Before you can shriek again", real_time(shriek_rest())) +
	       "  Your power makes the save harder or easier. It can't be shrugged off or\n"
	       "  deflected. Not underwater or in a safe room.\n";
}

// Shriek:  skill level/2 + 1d20 area damage = 51 - 70 damage @100 skill, usable once every 5 minutes.
void do_shriek(P_char ch, char * /*argument*/, int /*cmd*/)
{
	int skl_lvl, basedamage, actualdam, savemod, count, res;
	P_char person = 0;
	P_char next_person = 0;

	if (!ch)
	{
		logit(LOG_EXIT, "assert: bogus params (do_shriek) - NULL ch");
		return;
	}
	if (!IS_ALIVE(ch))
	{
		send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	// Get the level of skill the player or mob is at
	skl_lvl = GET_CHAR_SKILL(ch, SKILL_SHRIEK);

	// If this is not a disharmonist
	if (skl_lvl == 0)
	{
		if (!IS_TRUSTED(ch))
		{
			send_to_char("That's right, let it out.. it's not good to store anger.\r\n",
				     ch);
			return;
		}
		else
		{
			skl_lvl = 100;
		}
	}

	if (is_in_safe(ch))
	{
		send_to_char("You can find the anger to shriek in such a peaceful place.\r\n", ch);
		return;
	}

	// Make sure this is the right terrain
	if (IS_SECT(ch->in_room, SECT_UNDERWATER) || IS_SECT(ch->in_room, SECT_UNDERWATER_GR))
	{
		send_to_char("It comes out more like a gurgle.\r\n", ch);
		return;
	}

	// Check to see if the player has shrieked recently
	if (affected_by_spell(ch, SKILL_SHRIEK))
	{
		send_to_char("Your vocal chords just won't respond!\r\n", ch);
		return;
	}

	// Denote that this char is effected by shriek to start the timer
	set_short_affected_by(ch, SKILL_SHRIEK, shriek_rest());

	appear(ch);

	struct damage_messages messages = {
		"$N clutches $S ears as your &+RSHRIEK&n ruptures $S cochleas.",
		"You clutch your ears as the terrible &+RSHRIEK&n shatters your cochleas.",
		"$N clutches $S ears as a loud &+RSHRIEK&n ruptures $S cochleas.",
		"Blood pours out of $N's ears as the sound pulverizes $S mind!",
		"The last thing you experience is the taste of blood as the sound pulverizes your brain.",
		"Blood pours down $N's ears as $E collapses into a lifeless heap.",
	};

	// skl_lvl / 2 * 4 == 2 * skl_lvl; we multiply by 4 'cause of old damage reduction.
	basedamage = shriek_base_damage(skl_lvl);
	// 92 - 100 pow has no bonus, < 92 pow means easier to save, > 100 pow means harder to save.
	savemod = STAT_INDEX(GET_C_POW(ch)) - 15;

	// Let the char know (s)he shrieked
	send_to_char("You expel your welled-up rage in a mind-aching &+RSHRIEK!&n\r\n", ch);
	act("$n expels $s welled-up rage in a mind-aching &+RSHRIEK!&n", FALSE, ch, 0, 0, TO_ROOM);

	// For each person in the room
	count = 0;
	for (person = world[ch->in_room].people; person; person = next_person)
	{
		// Figure out who the next person to test will be
		next_person = person->next_in_room;

		// Qualify against area attack rules
		if (!should_area_hit(ch, person))
			continue;

		// Count the number of affected people
		++count;

		// If they save, halve base damage (only).  This guarentees final damage > 0.
		if (NewSaves(person, SAVING_SPELL, savemod))
		{
			actualdam = shriek_saved_damage(basedamage);
		}
		else
		{
			actualdam = basedamage;
		}

		// Apply the actualdamage to the person + 1d20 randomness.
		// Note: spell_damage will engage victims (if they live), but not cause bashes/backstabs/etc so ch won't die.
		//       Should this change, we might want to look at GET_POS(ch) vs POS_STANDING to see if they got knocked down.
		res = spell_damage(ch, person, actualdam + shriek_roll_damage(live_rolls),
				   SPLDAM_SOUND, SPLDAM_NOSHRUG | SPLDAM_NODEFLECT, &messages);
		// If, somehow, the shrieker dies mid-shriek, stop shrieking and return.
		if (res == DAM_CHARDEAD || res == DAM_BOTHDEAD)
		{
			return;
		}
	}

	// We only notch if they actually shriek at a target.
	if (count > 0)
	{
		// Skill notch + 1/2% chance per target. (It takes 200 - 2 * base notch chance targets to get 100% notch chance).
		notch_skill(ch, SKILL_SHRIEK, get_property("skill.notch.shriek", 14) + count / 2);
	}
}

char isSpringable(P_char ch, P_char victim)
{
	if (!IS_ALIVE(ch) || !victim || IS_IMMATERIAL(victim) ||
	    affected_by_spell(ch, SKILL_BASH) || IS_ELEMENTAL(victim) || IS_WATERFORM(victim) ||
	    GET_CHAR_SKILL(ch, SKILL_SPRINGLEAP) < 1 || IS_INCORPOREAL(victim) ||
	    IS_DRAGON(victim) || IS_DRAGON(ch) ||
	    (IS_NPC(victim) && IS_SET(victim->specials.act, ACT_NO_BASH)) ||
	    (ch->specials.z_cord == 0) || !CanDoFightMove(ch, victim) ||
	    !MIN_POS(victim, POS_STANDING + STAT_NORMAL))
	{
		return FALSE;
	}

	if ((has_innate(victim, INNATE_HORSE_BODY) || has_innate(victim, INNATE_SPIDER_BODY)) &&
	    get_takedown_size(ch) <= get_takedown_size(victim))
	{
		return false;
	}

	if (get_takedown_size(victim) > get_takedown_size(ch) + 1)
	{
		return false;
	}

	if (get_takedown_size(victim) < get_takedown_size(ch) - 1)
	{
		return false;
	}

	return TRUE;
}

bool MobShouldFlee(P_char ch)
{
	if (!IS_NPC(ch))
		return false;

	if (GET_POS(ch) != POS_STANDING || IS_STUNNED(ch) || GET_STAT(ch) <= STAT_INCAP ||
	    !room_has_valid_exit(ch->in_room))
		return false;

	if (IS_ROOM(ch->in_room, (ROOM_NO_MAGIC | ROOM_SILENT)) ||
	    affected_by_spell(ch, SPELL_FEEBLEMIND) || IS_AFFECTED(ch, AFF_BLIND) ||
	    IS_AFFECTED2(ch, AFF2_SILENCED) || IS_SET(ch->specials.act, ACT_WIMPY) ||
	    get_spell_from_room(&world[ch->in_room], SPELL_WANDERING_WOODS) ||
	    affected_by_spell(ch, SPELL_WITHER) || affected_by_spell(ch, SPELL_RAY_OF_ENFEEBLEMENT))
	{
		if (IS_SET(ch->specials.act, ACT_SENTINEL) || IS_SHOPKEEPER(ch))
			return false;

		// Multiclass melee classes may not want to flee...
		if (IS_MELEE_CLASS(ch) && !number(0, 9))
			return true;
	}
	return false;
}

bool CheckMultiProcTiming(P_char ch)
{
	return true; // disabling multiproc check

	if (!IS_ALIVE(ch) || affected_by_spell(ch, TAG_STOP_PROC))
	{
		return false;
	}

	set_short_affected_by(ch, TAG_STOP_PROC, 1);

	return true;
}

extern float dreadnaught_attack_factor(const struct affected_type *paf);
extern float dreadnaught_melee_defense(const Rolls &rolls, const struct affected_type *paf);
extern double dreadnaught_spell_defense(const Rolls &rolls, const struct affected_type *paf);

// How long, in pulses, a stance lasts.
static int dreadnaught_duration(const Rolls &rolls, P_char ch, int skl_lvl)
{
	return PULSE_VIOLENCE * ((GET_LEVEL(ch) / 14) + rolls.number(0, skl_lvl / 50) + 1);
}

// How long, in pulses, a failed try keeps the user from another.
static int dreadnaught_failed_rest()
{
	return 65;
}

// How long past the stance's end, in pulses, before another.
static int dreadnaught_rest(int duration)
{
	return duration + PULSE_VIOLENCE;
}

std::string dreadnaught_facts(P_char ch)
{
	const int skl_lvl = GET_CHAR_SKILL(ch, SKILL_DREADNAUGHT);
	const int low = dreadnaught_duration(lowest_rolls, ch, skl_lvl);
	const int high = dreadnaught_duration(highest_rolls, ch, skl_lvl);
	struct affected_type stance;
	memset(&stance, 0, sizeof(stance));
	stance.level = skl_lvl;
	return fact("Chance", std::to_string(MAX(0, skl_lvl - 1)) + " in 101") +
	       fact("Duration", seconds(low) + " to " + seconds(high)) +
	       fact("Melee damage you deal",
		    std::to_string(std::lround(dreadnaught_attack_factor(&stance) * 100)) +
			    "% of normal") +
	       fact("Less melee damage you take",
		    show({ (int)dreadnaught_melee_defense(lowest_rolls, &stance),
			   (int)dreadnaught_melee_defense(highest_rolls, &stance) }) +
			    "%") +
	       fact("Less spell damage you take",
		    show({ (int)dreadnaught_spell_defense(lowest_rolls, &stance),
			   (int)dreadnaught_spell_defense(highest_rolls, &stance) }) +
			    "%") +
	       fact("Before you can try again",
		    seconds(dreadnaught_rest(low)) + " to " + seconds(dreadnaught_rest(high))) +
	       fact("  After a failure", seconds(dreadnaught_failed_rest())) +
	       "  It also makes you immune to fear while it lasts. Some attacks, such as a\n"
	       "  backstab, skip the melee numbers.\n";
}

void do_dreadnaught(P_char ch, char *, int)
{
	struct affected_type af;
	int skl_lvl = GET_CHAR_SKILL(ch, SKILL_DREADNAUGHT);

	if (skl_lvl < 1)
	{
		send_to_char(
			"You have no training in such a specialized area of defensive abilities.\r\n",
			ch);
		return;
	}

	if (affected_by_spell(ch, TAG_DREADNAUGHT))
	{
		send_to_char("You are not ready to assume a defensive stance yet.\r\n", ch);
		return;
	}

	// (skl_lvl/2) rounds + (char_level/14) rounds + 1 round = 3 to 7 rounds
	int duration = dreadnaught_duration(live_rolls, ch, skl_lvl);

	if (number(1, 101) < skl_lvl)
	{
		act("&+RCCCHHHAAARRGGEEEE!!!&+y You raise your defenses and assume a stoic stance!&n",
		    FALSE, ch, 0, 0, TO_CHAR);
		act("$n &+ysuddenly assumes a &+Ydefensive&+y position, shield and weapon at the ready!&n",
		    FALSE, ch, 0, 0, TO_ROOM);

		memset(&af, 0, sizeof(af));

		af.type = SKILL_DREADNAUGHT;
		af.bitvector5 = AFF5_DREADNAUGHT;
		af.flags = AFFTYPE_SHORT | AFFTYPE_NODISPEL;
		af.level = GET_CHAR_SKILL(ch, SKILL_DREADNAUGHT);
		af.duration = duration;
		affect_to_char(ch, &af);

		memset(&af, 0, sizeof(af));
		af.type = SKILL_DREADNAUGHT;
		af.bitvector4 = AFF4_NOFEAR;
		af.level = GET_CHAR_SKILL(ch, SKILL_DREADNAUGHT);
		af.duration = duration;
		af.flags = AFFTYPE_SHORT | AFFTYPE_NODISPEL;

		affect_to_char_with_messages(
			ch, &af, "&+yYou lower your &+Yguard&+y, and assume an offensive stance.",
			"$n &+ylowers his guard, and assumes an offensive stance.&n");

		set_short_affected_by(ch, TAG_DREADNAUGHT, dreadnaught_rest(duration));
		notch_skill(ch, SKILL_DREADNAUGHT, 6.67);
		return;
	}

	act("&nYou attempt to assume a &+ydefensive &nposition, but fail horribly!&n", FALSE, ch, 0,
	    0, TO_CHAR);
	act("$n &+yattempts to assume a &+Ydefensive&+y position, but fails horribly!&n", FALSE, ch,
	    0, 0, TO_ROOM);
	set_short_affected_by(ch, TAG_DREADNAUGHT, dreadnaught_failed_rest());
	notch_skill(ch, SKILL_DREADNAUGHT, 6.67);
}

// How long, in pulses, a step's stance and its rest last.
static int shadowstep_duration(P_char ch)
{
	return 140 - GET_CHAR_SKILL(ch, SKILL_SHADOWSTEP);
}

// How long, in pulses, a step hides the user.
static int shadowstep_hide_duration()
{
	return 20;
}

std::string shadowstep_facts(P_char ch)
{
	return fact("Chance",
		    std::to_string(MAX(0, GET_CHAR_SKILL(ch, SKILL_SHADOWSTEP) - 1)) + " in 102") +
	       fact("Duration, and the rest after a failure", seconds(shadowstep_duration(ch))) +
	       fact("Hidden", seconds(shadowstep_hide_duration())) +
	       "  If you are fighting, it ends the fight and your attackers stop.\n";
}

void do_shadowstep(P_char ch, char *, int)
{
	struct affected_type af;

	if (GET_CHAR_SKILL(ch, SKILL_SHADOWSTEP) < 1)
	{
		send_to_char("&+LYou are not sneaky enough to attempt shadow stepping.\r\n", ch);
		return;
	}

	if (affected_by_spell(ch, SKILL_SHADOWSTEP))
	{
		send_to_char(
			"&+LYou must wait for the &+wshadows&+L to coalesce before attempting to shadow step once again.\r\n",
			ch);
		return;
	}

	int dur = shadowstep_duration(ch);
	if (number(1, 102) < GET_CHAR_SKILL(ch, SKILL_SHADOWSTEP))
	{
		act("&+LPooF! You perform an evasive maneouver, quickling darting into the sha&+wdo&+Wws&+L!&n",
		    FALSE, ch, 0, 0, TO_CHAR);
		act("&+LPooF! &n$n &+ysuddenly performs an evasive maneouver, quickling darting into the sha&+wdo&+Wws&+L!&n",
		    FALSE, ch, 0, 0, TO_ROOM);

		memset(&af, 0, sizeof(af));

		af.type = SKILL_SHADOWSTEP;
		af.flags = AFFTYPE_SHORT | AFFTYPE_NODISPEL;
		af.duration = dur;
		affect_to_char_with_messages(
			ch, &af,
			"&+LYou grin as the sha&+wdo&+Wws &+Lslowly coalesce around you.&n",
			"$n &+Lflashes a &+rwicked&+L grin as the sha&+wdo&+Wws &+Lslowly coalesce around them.&n");

		memset(&af, 0, sizeof(af));
		af.type = SKILL_SHADOWSTEP;
		af.bitvector = AFF_HIDE;
		af.duration = shadowstep_hide_duration();
		af.flags = AFFTYPE_SHORT | AFFTYPE_NODISPEL | AFFTYPE_NOSHOW;
		affect_to_char(ch, &af);

		notch_skill(ch, SKILL_SHADOWSTEP, 6.67);
		if (IS_FIGHTING(ch))
		{
			P_char victim, victim2;
			for (victim = world[ch->in_room].people; victim; victim = victim2)
			{
				victim2 = victim->next_in_room;

				// immortals are not effected
				if (IS_TRUSTED(victim))
				{
					continue;
				}
				if (GET_OPPONENT(victim) == ch)
				{
					stop_fighting(victim);
				}
			}
		}
		stop_fighting(ch);
		return;
	}

	act("&nYou attempt to step into the &+Lsha&+wdo&+Wws&n, but fail horribly!&n", FALSE, ch, 0,
	    0, TO_CHAR);
	act("$n makes an attempt to step into the &+Lsha&+wdo&+Wws&n, but fails horribly!&n", FALSE,
	    ch, 0, 0, TO_ROOM);
	set_short_affected_by(ch, SKILL_SHADOWSTEP, dur);
	notch_skill(ch, SKILL_SHADOWSTEP, 6.67);
}

void do_garrote(P_char ch, char *argument, int /*cmd*/)
{
	P_char victim = NULL;
	int chsize, victsize;

	if (!IS_ALIVE(ch))
	{
		if (ch)
			send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (affected_by_spell(ch, SKILL_GARROTE))
	{
		send_to_char("You must wait before attempting to &+rgarrote&n again.\r\n", ch);
		return;
	}

	if (GET_CHAR_SKILL(ch, SKILL_GARROTE) < 1)
	{
		send_to_char("Sure! You'll probably cut yourself trying!&n\r\n", ch);
		return;
	}

	victim = ParseTarget(ch, argument);

	if (!IS_ALIVE(victim))
	{
		// CharWait(ch, (int)(0.5 * PULSE_VIOLENCE));
		send_to_char("Who's throat would you like to &+rcut&n?\n", ch);
		return;
	}

	chsize = get_takedown_size(ch);
	victsize = get_takedown_size(victim);
	// Size handling: +/- 1 (position irrelevant .. neck size is).
	if (victsize < chsize - 1)
	{
		act("You can't seem to reach down that far.", FALSE, ch, 0, 0, TO_CHAR);
		return;
	}
	if (victsize > chsize + 1)
	{
		act("You can't seem to get your arms around $s neck!", FALSE, ch, 0, victim,
		    TO_CHAR);
		return;
	}

	int success = garrote_threshold(ch);
	notch_skill(ch, SKILL_GARROTE, 6.67);
	if (number(1, 105) > success)
	{
		act("&+LYou try to slip behind &n$N&+L, but they notice the attempt and block your advance!",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("&+LYou notice &n$n &+Lattempting to sneak behind you, but quickly block their advance!",
		    FALSE, ch, 0, victim, TO_VICT);
		act("$N &+Ladeptly notices &n$n's attempt to &+rgarrote&+L them and blocks the attempt!",
		    FALSE, ch, 0, victim, TO_NOTVICT);
		set_short_affected_by(ch, SKILL_GARROTE, garrote_miss_rest());
		CharWait(ch, garrote_miss_lag());
		return;
	}

	act("&+LYou skillfully slip behind&n $N &+Land &+rslit &+Ltheir &+rth&+Rro&+rat&+L resulting in a &+Rmist &+Lof &+rblood&+L!&n",
	    FALSE, ch, 0, victim, TO_CHAR);
	act("&+rOUCH! &n$n &+Lsuddenly appears behind you and makes a &+rslashing &+Lmotion at your &+rth&+Rro&+rat&+L!",
	    FALSE, ch, 0, victim, TO_VICT);
	act("$N &+Lsuddenly stumbles, grasping at their &+rneck&+L as &n$n &+Lstands behind them grinning!",
	    FALSE, ch, 0, victim, TO_NOTVICT);
	if (IS_CASTING(victim))
	{
		StopCasting(victim);
	}
	set_short_affected_by(ch, SKILL_GARROTE, garrote_hit_rest());
	// @lvl 30: 2-4, @lvl 34: 3-5, @lvl 56: 5-7.
	int numb = garrote_rounds(live_rolls, ch);
	CharWait(ch, garrote_hit_lag());
	if (!IS_FIGHTING(ch))
	{
		set_fighting(ch, victim);
	}

	add_event(event_garroteproc, PULSE_VIOLENCE, victim, 0, 0, 0, &numb, sizeof(numb));
}

// The sweeper's lag, in pulses, when the size is too far off, and otherwise.
static int legsweep_size_lag()
{
	return (int)(PULSE_VIOLENCE * 0.5);
}

static int legsweep_lag()
{
	return PULSE_VIOLENCE * 2;
}

// How long, in pulses, a hit keeps the sweeper from the next takedown.
static int legsweep_rest()
{
	return (int)(3.5 * PULSE_VIOLENCE);
}

// True on the 15 sweeps in 100 that leave the target prone.
static bool legsweep_prone_roll(const Rolls &rolls)
{
	return rolls.number(1, 100) <= 15;
}

std::string legsweep_facts(P_char)
{
	return fact("Your lag and the target's on a hit", seconds(legsweep_lag()) + " each") +
	       fact("Your lag on a miss", seconds(legsweep_lag())) +
	       fact("Your lag if the size is too far off", seconds(legsweep_size_lag())) +
	       fact("Your lag if the target is asleep",
		    seconds(takedown_sleeping_target_lag()) + " (you attack it instead)") +
	       fact("Your lag if the target evades", seconds(takedown_evade_lag())) +
	       fact("Before your next takedown after a hit", seconds(legsweep_rest())) +
	       fact("Chance a hit leaves the target prone", "15 in 100") +
	       "  The target must be within one size of you. Centaurs, quadrupeds and\n"
	       "  driders can't sweep.\n";
}

void do_legsweep(P_char ch, char *arg, int /*cmd*/)
{
	P_char vict = NULL;
	float percent_chance;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (IS_CENTAUR(ch) || GET_RACE(ch) == RACE_QUADRUPED || GET_RACE(ch) == RACE_DRIDER)
	{
		send_to_char("You rear up and .. wait, how does your leg bend?!\n", ch);
		return;
	}

	if (!IS_FIGHTING(ch))
	{
		vict = ParseTarget(ch, arg);
		if (!vict)
		{
			send_to_char("Legsweep who?\n", ch);
			return;
		}
	}
	else
	{
		vict = GET_OPPONENT(ch);
		// If fighting and not fighting. buggy!
		if (!vict)
		{
			stop_fighting(ch);
			return;
		}
	}
	if (!IS_ALIVE(vict))
	{
		return;
	}

	if ((percent_chance = GET_CHAR_SKILL(ch, SKILL_LEGSWEEP)) < 1)
	{
		send_to_char("You really dont know how.\n", ch);
		return;
	}

	appear(ch);

	const int size_difference = get_takedown_size(vict) - get_takedown_size(ch);
	if (size_difference < -1)
	{
		act("Due to $S small size, you manage to take your own legs out from under you!",
		    FALSE, ch, 0, vict, TO_CHAR);
		act("$n attempts to legsweep $N and winds up on $s ass instead!", FALSE, ch, 0,
		    vict, TO_NOTVICT);
		act("$n attempts to legsweep you but loses $s &+Wbalance&n and lands on $s ass instead!",
		    FALSE, ch, 0, vict, TO_VICT);
		CharWait(ch, legsweep_size_lag());
		SET_POS(ch, POS_PRONE + GET_STAT(ch));
		return;
	}

	if (size_difference > 1)
	{
		act("You attempt to legsweep $M only to manage to hit $S massive shin and fall down yourself!",
		    FALSE, ch, 0, vict, TO_CHAR);
		act("$n attempts to legsweep $N and winds up on $s ass instead!", FALSE, ch, 0,
		    vict, TO_NOTVICT);
		act("$n attempts to legsweep you but loses $s &+Wbalance&n and lands on $s ass instead!",
		    FALSE, ch, 0, vict, TO_VICT);
		CharWait(ch, legsweep_size_lag());
		SET_POS(ch, POS_PRONE + GET_STAT(ch));
		return;
	}

	if (!CanDoFightMove(ch, vict))
	{
		return;
	}

	if (affected_by_spell(ch, SKILL_BASH))
	{
		send_to_char("You haven't yet reoriented yourself enough!\n", ch);
		return;
	}

	if (!on_front_line(ch) || !on_front_line(vict))
	{
		send_to_char("With an awesome aerial maneuver you manage to reach the target.\n",
			     ch);
		percent_chance *= 0.5;
	}

	if (IS_AFFECTED(vict, AFF_AWARE))
	{
		percent_chance *= .75;
	}

	// Adjacent size categories are harder to sweep, not automatic failures.
	if (size_difference != 0)
		percent_chance *= 0.75;

	percent_chance = takedown_check(ch, vict, percent_chance, SKILL_LEGSWEEP, TAKEDOWN_ALL);

	if (percent_chance == TAKEDOWN_CANCELLED)
	{
		return;
	}

	if (percent_chance == TAKEDOWN_PENALTY)
	{
		percent_chance = 0;
	}

	if (IS_NPC(ch) && IS_ELITE(ch) && !IS_PC_PET(ch))
	{
		percent_chance = 100;
	}

	if (percent_chance > 95)
	{
		percent_chance = 95;
	}

	if (IS_PC(ch) || IS_PC(vict))
	{
		debug("(%s) legsweeping (%s) with percentage of (%d).", J_NAME(ch), J_NAME(vict),
		      (int)percent_chance);
	}

	if ((notch_skill(ch, SKILL_LEGSWEEP, get_property("skill.notch.offensive", 7)) ||
	     number(1, 100) <= percent_chance || IS_TRUSTED(ch)) &&
	    GET_POS(vict) == POS_STANDING)
	{
		if (!IS_TRUSTED(ch))
		{
			set_short_affected_by(ch, SKILL_BASH, legsweep_rest());
		}

		// 15% chance to ass target.
		if (legsweep_prone_roll(live_rolls))
		{
			act("You quickly maneuver alongside $N&n, drop low and &+RCOMPLETELY&n &+Wsweep&n $S legs out from under $M!",
			    FALSE, ch, 0, vict, TO_CHAR);
			act("$n masterfully maneuvers next to $N and completely &+Wsweeps&n $S legs out from beneath $M!!!",
			    FALSE, ch, 0, vict, TO_NOTVICT);
			act("Before you can react, $n maneuvers beside you and &+RCOMPLETELY&n &+Wkicks&n your legs out from beneath you!!!",
			    FALSE, ch, 0, vict, TO_VICT);

			SET_POS(vict, POS_PRONE + GET_STAT(vict));
		}
		else
		{
			act("You swiftly maneuver next to $N&n, drop low and &+Wsweep&n $S legs out from under $M!",
			    FALSE, ch, 0, vict, TO_CHAR);
			act("$n quickly maneuvers alongside $N and &+Wsweeps&n $S legs out from under $M!",
			    FALSE, ch, 0, vict, TO_NOTVICT);
			act("$n quickly maneuvers beside you and &+Wkicks&n your legs out from under you!",
			    FALSE, ch, 0, vict, TO_VICT);

			SET_POS(vict, POS_SITTING + GET_STAT(vict));
		}
		CharWait(ch, legsweep_lag());
		CharWait(vict, legsweep_lag());
	}
	else
	{
		act("You attempt to legsweep $M but manage to land on your own ass instead!", FALSE,
		    ch, 0, vict, TO_CHAR);
		act("$n attemps to legsweep $N but only manages to land on $s ass.", FALSE, ch, 0,
		    vict, TO_NOTVICT);
		act("$n attemps to legsweep you, but only manages to land on $s ass.", FALSE, ch, 0,
		    vict, TO_VICT);

		SET_POS(ch, POS_SITTING + GET_STAT(ch));
		CharWait(ch, legsweep_lag());
	}

	if (!IS_FIGHTING(ch) && IS_ALIVE(ch) && IS_ALIVE(vict))
	{
		set_fighting(ch, vict);
	}
	return;
}

// The roll taken from the rating; what is left picks the strike.
static int crippling_strike_roll(const Rolls &rolls)
{
	return rolls.number(0, 170);
}

// How long, in pulses, the best strike deafens.
static int crippling_strike_deaf_duration(const Rolls &rolls)
{
	return rolls.number(25, 50) * WAIT_SEC;
}

// The vitality the two best strikes take.
static int crippling_strike_best_vitality(const Rolls &rolls)
{
	return rolls.number(10, 25);
}

static int crippling_strike_second_vitality(const Rolls &rolls)
{
	return rolls.number(5, 25);
}

// Each strike's damage, best first.
static int crippling_strike_best_damage(const Rolls &rolls)
{
	return 4 * (40 + (rolls.dice(2, 20)));
}

static int crippling_strike_second_damage(const Rolls &rolls)
{
	return 4 * (30 + (rolls.dice(2, 20)));
}

static int crippling_strike_third_damage(const Rolls &rolls)
{
	return 4 * (30 + (rolls.dice(1, 20)));
}

static int crippling_strike_fourth_damage(const Rolls &rolls)
{
	return 4 * (10 + (rolls.dice(1, 20)));
}

std::string crippling_strike_facts(P_char ch)
{
	const int skl = GET_CHAR_SKILL(ch, SKILL_CRIPPLING_STRIKE);
	// Of the 171 rolls, how many leave more than `least`.
	const auto above = [skl](int least) { return MAX(0, skl - least); };
	const auto chance = [&](int least, int best)
	{ return std::to_string(above(least) - above(best)) + " in 171"; };
	return fact("Best strike", chance(85, 171)) +
	       fact("  Damage", show({ crippling_strike_best_damage(lowest_rolls),
				       crippling_strike_best_damage(highest_rolls) })) +
	       fact("  Vitality lost", show({ crippling_strike_best_vitality(lowest_rolls),
					      crippling_strike_best_vitality(highest_rolls) })) +
	       fact("  Deafened", seconds(crippling_strike_deaf_duration(lowest_rolls)) + " to " +
					  seconds(crippling_strike_deaf_duration(highest_rolls))) +
	       fact("Second strike", chance(65, 85)) +
	       fact("  Damage", show({ crippling_strike_second_damage(lowest_rolls),
				       crippling_strike_second_damage(highest_rolls) })) +
	       fact("  Vitality lost", show({ crippling_strike_second_vitality(lowest_rolls),
					      crippling_strike_second_vitality(highest_rolls) })) +
	       fact("Third strike", chance(45, 65)) +
	       fact("  Damage", show({ crippling_strike_third_damage(lowest_rolls),
				       crippling_strike_third_damage(highest_rolls) })) +
	       fact("Fourth strike", chance(25, 45)) +
	       fact("  Damage", show({ crippling_strike_fourth_damage(lowest_rolls),
				       crippling_strike_fourth_damage(highest_rolls) })) +
	       "  It is checked when a humanoid, non-elite target you attack while it fights\n"
	       "  someone else gets back up or tries to flee. You must be standing.\n";
}

// Check for crippling strike skill
// Returns TRUE if ch is DEAD.
bool check_crippling_strike(P_char ch)
{
	P_char kala, kala2;
	int skl, success;
	struct affected_type af;

	if (IS_FIGHTING(ch))
	{
		for (kala = world[ch->in_room].people; kala; kala = kala2)
		{
			kala2 = kala->next_in_room;

			if (kala == ch)
			{
				continue;
			}

			if (GET_POS(kala) != POS_STANDING)
			{
				continue;
			}

			// We want to have crippling strike activate when the merc is not fighting
			// tanking the victim. It's more logical this way.
			if (GET_OPPONENT(ch) == kala)
			{
				continue;
			}

			if (GET_OPPONENT(kala) != ch)
			{
				continue;
			}

			if (IS_IMMOBILE(kala) || !IS_AWAKE(kala) || IS_STUNNED(kala) ||
			    !IS_HUMANOID(ch) || IS_ELITE(ch))
			{
				continue;
			}

			skl = GET_CHAR_SKILL(kala, SKILL_CRIPPLING_STRIKE);
			success = skl - crippling_strike_roll(live_rolls);

			if (skl && success > 0)
			{
				notch_skill(kala, SKILL_CRIPPLING_STRIKE, 15);
				if (success > 85)
				{
					act("You spin on your heel, slamming your elbow into $N's ear.",
					    FALSE, kala, 0, ch, TO_CHAR);
					act("$n spins around, slamming $s elbow into your ear. \nYour vision blurs and your ears start ringing!",
					    FALSE, kala, 0, ch, TO_VICT);
					act("$n spins around, slamming $s elbow into $N's ear.",
					    FALSE, kala, 0, ch, TO_NOTVICT);

					bzero(&af, sizeof(af));
					af.type = SKILL_CRIPPLING_STRIKE;
					af.bitvector4 = AFF4_DEAF;
					af.flags = AFFTYPE_SHORT | AFFTYPE_NODISPEL;
					af.duration = crippling_strike_deaf_duration(live_rolls);
					send_to_char("&+WDoh! You can't hear a thing!&n", ch);

					affect_to_char_with_messages(
						ch, &af,
						"&+WOooh, is that bird song you hear? How lovely.&n",
						"$n&n seems to be listening to the birds singing.");

					GET_VITALITY(ch) -=
						crippling_strike_best_vitality(live_rolls);
					damage(kala, ch, crippling_strike_best_damage(live_rolls),
					       SKILL_CRIPPLING_STRIKE);
					if (!IS_ALIVE(kala))
					{
						return TRUE;
					}
				}
				else if (success > 65)
				{
					act("You stomp down hard on $N's knee, twisting it.", FALSE,
					    kala, 0, ch, TO_CHAR);
					act("$n stomps down hard on your knee, twisting it painfully.",
					    FALSE, kala, 0, ch, TO_VICT);
					act("$n stomps on $N's knee, twisting it.", FALSE, kala, 0,
					    ch, TO_NOTVICT);
					GET_VITALITY(ch) -=
						crippling_strike_second_vitality(live_rolls);
					damage(kala, ch, crippling_strike_second_damage(live_rolls),
					       SKILL_CRIPPLING_STRIKE);
					if (!IS_ALIVE(kala))
					{
						return TRUE;
					}
				}
				else if (success > 45)
				{
					act("You grab $N by the head and slam your knee in his face.",
					    FALSE, kala, 0, ch, TO_CHAR);
					act("Blinding pain rushes over you as $n crushes your nose with his knee.",
					    FALSE, kala, 0, ch, TO_VICT);
					act("$n slams his knee into $N's face.", FALSE, kala, 0, ch,
					    TO_NOTVICT);
					damage(kala, ch, crippling_strike_third_damage(live_rolls),
					       SKILL_CRIPPLING_STRIKE);
					if (!IS_ALIVE(kala))
					{
						return TRUE;
					}
				}
				else if (success > 25)
				{
					act("As $N stands, you leap forward and slam the hilt of your weapon into $s back.",
					    FALSE, kala, 0, ch, TO_CHAR);
					act("$n leaps forward and slams the hilt of his weapon into your back, oof!!",
					    FALSE, kala, 0, ch, TO_VICT);
					act("As $N stands, $n leaps forward and slams the hilt of his weapon into $s back.",
					    FALSE, kala, 0, ch, TO_NOTVICT);
					damage(kala, ch, crippling_strike_fourth_damage(live_rolls),
					       SKILL_CRIPPLING_STRIKE);
					if (!IS_ALIVE(kala))
					{
						return TRUE;
					}
				}
				else
				{
					act("You charge $N, but $e rolls nimbly out of the way.",
					    FALSE, kala, 0, ch, TO_CHAR);
					act("$n lunges forward, but you roll out of the way", FALSE,
					    kala, 0, ch, TO_VICT);
					act("$n lunges forward, but $N rolls out of the way.",
					    FALSE, kala, 0, ch, TO_NOTVICT);
				}
			}
		}
	}
	return FALSE;
}

// What a taunt adds to make the target's fear save harder.
static int taunt_save_modifier(int skl_lvl)
{
	return MAX(2, skl_lvl / 5);
}

// The chance threshold a taunt rolls 1-100 against.
static int taunt_threshold(int skl_lvl)
{
	return MIN(skl_lvl, 99);
}

// How long, in pulses, a taunted target stays on the taunter; NPCs twice as long.
static int taunt_duration(int skl_lvl, bool npc)
{
	return BOUNDED(2, skl_lvl / 10, 10) * WAIT_SEC * (npc ? 2 : 1);
}

// The target's lag after a taunt lands, in pulses.
static int taunt_target_lag()
{
	return WAIT_SEC * 2;
}

// The taunter's lag, in pulses.
static int taunt_lag()
{
	return (int)(PULSE_VIOLENCE * 1);
}

std::string taunt_facts(P_char ch)
{
	const int skl_lvl = GET_CHAR_SKILL(ch, SKILL_TAUNT);
	return fact("Chance", std::to_string(taunt_threshold(skl_lvl)) + " in 100") +
	       fact("Modifier on the target's fear save",
		    "+" + std::to_string(taunt_save_modifier(skl_lvl))) +
	       fact("Target stays on you", seconds(taunt_duration(skl_lvl, false)) + ", a mob " +
						   seconds(taunt_duration(skl_lvl, true))) +
	       fact("Target's lag", seconds(taunt_target_lag())) +
	       fact("Your lag", seconds(taunt_lag())) +
	       "  The target's fear save stops both. Taunting it again adds to the time.\n";
}

void do_taunt(P_char ch, char *arg, int cmd)
{
	P_char vict;
	int skl_lvl = 0, saveMod, percent_chance;
	struct affected_type af;
	struct affected_type *paf;

	if (!IS_ALIVE(ch))
	{
		send_to_char("Lay still, you seem to be dead.\r\n", ch);
		return;
	}

	if (!SanityCheck(ch, "do_taunt"))
		return;

	if ((skl_lvl = GET_CHAR_SKILL(ch, SKILL_TAUNT)) == 0)
	{
		// taunt is a social if you don't have the skill
		do_action(ch, arg, cmd);
		return;
	}

	vict = ParseTarget(ch, arg);
	if (!vict)
	{
		send_to_char("Taunt who?\n", ch);
		return;
	}

	// mod of 2 to 20, scaled linearly with skill level
	saveMod = taunt_save_modifier(skl_lvl);
	percent_chance = taunt_threshold(skl_lvl);

	if (!IS_ALIVE(vict))
	{
		return;
	}

	if (IS_ROOM(vict->in_room, ROOM_SINGLE_FILE) && !AdjacentInRoom(vict, ch))
	{
		act("$N can't reach you in this narrow room.", FALSE, ch, NULL, vict, TO_CHAR);
		return;
	}

	if ((notch_skill(ch, SKILL_TAUNT, get_property("skill.notch.offensive", 7)) ||
	     number(1, 100) <= percent_chance || IS_TRUSTED(ch)))
	{
		act("You &+Wmercilessly &+Rtaunt&n $N.", TRUE, ch, NULL, vict, TO_CHAR);
		act("$n &+Wmercilessly &+Rtaunts &+Wyou.&n", TRUE, ch, NULL, vict, TO_VICT);
		act("$n &+Wmercilessly &+Rtaunts&n $N&+W.&n", TRUE, ch, NULL, vict, TO_NOTVICT);

		if (IS_TRUSTED(ch) || !NewSaves(vict, SAVING_FEAR, saveMod))
		{
			paf = get_spell_from_char(vict, SKILL_TAUNT);
			int duration = taunt_duration(skl_lvl, IS_NPC(vict));
			if (paf && paf->context == (void *)ch)
			{
				// update taunt duration
				paf->duration += duration;
			}
			else
			{
				// remove existing taunt
				if (paf)
					affect_from_char(vict, SKILL_TAUNT);

				// successful taunt
				bzero(&af, sizeof(af));
				af.type = SKILL_TAUNT;
				af.flags = AFFTYPE_SHORT | AFFTYPE_NOSAVE;
				af.context = (void *)ch;
				af.duration = duration;
				linked_affect_to_char(vict, &af, ch, LNK_TAUNT);
				if (GET_OPPONENT(vict) != ch)
				{
					stop_fighting(vict);
					engage(vict, ch);
				}
			}

			act("&+WYou definitely got under $S skin!&n", TRUE, ch, NULL, vict,
			    TO_CHAR);
			act("&=LRThat last momma joke was the final straw!&n", TRUE, ch, NULL, vict,
			    TO_VICT);
			act("$n &+Wseems to have riled up &n$N&+W!&n", TRUE, ch, NULL, vict,
			    TO_NOTVICT);

			CharWait(vict, taunt_target_lag());
		}
		else
		{
			// good taunt but target resisted
			act("&+LYou failed to get under $S skin.&n", TRUE, ch, NULL, vict, TO_CHAR);
			act("You have a thicker skin than that.", TRUE, ch, NULL, vict, TO_VICT);
			act("$N doesn't seem to be impressed.", TRUE, ch, NULL, vict, TO_NOTVICT);
		}
	}
	else
	{
		// unsuccesful taunt
		act("&+LYou attempt to taunt &n$N&+L, but just fumble around with words.&n", TRUE,
		    ch, NULL, vict, TO_CHAR);
		act("$n shouts something unintelligible at you.&n", TRUE, ch, NULL, vict, TO_VICT);
		act("$n shouts something unintelligible at $N.&n", TRUE, ch, NULL, vict,
		    TO_NOTVICT);
	}

	CharWait(ch, taunt_lag());
}
