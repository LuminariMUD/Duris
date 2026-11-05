/****************************************************************************
 *
 *  File: avengers.c                                            Part of Duris
 *  Usage: avenger skills: holy smite
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "core/prototypes.h"
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "core/utils.h"
#include "classes/avengers.h"
#include <string.h>
#include "combat/damage.h"
#include "item/objmisc.h"
#include "magic/spells.h"
#include "abilities/abilities.h"

extern int holy_sword_alignment_damage(const Rolls &rolls);

static int holy_sword_duration(int level)
{
	return level / 2;
}

// The damroll and the hitroll holy sword adds.
static int holy_sword_bonus()
{
	return 5;
}

std::string holy_sword_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Duration", game_hours(holy_sword_duration(level)) + " at your level, " +
					std::to_string(level)) +
	       fact("Hitroll", "+" + std::to_string(holy_sword_bonus())) +
	       fact("Damroll", "+" + std::to_string(holy_sword_bonus())) +
	       fact("Added to damage against the opposite alignment",
		    show({ holy_sword_alignment_damage(lowest_rolls),
			   holy_sword_alignment_damage(highest_rolls) })) +
	       "  It is added before other damage multipliers.\n"
	       "  It also gives you an extra attack with your main weapon.\n"
	       "  Removing your main weapon or being disarmed ends it.\n"
	       "  You must be wielding a sword. It has no effect while you already have it.\n";
}

void spell_holy_sword(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
		      P_char /*victim*/, P_obj /*obj*/)
{
	struct affected_type af;

	if (affected_by_spell(ch, SPELL_HOLY_SWORD))
	{
		send_to_char("&+WYou cannot imbue your weapon with any more holy powers.&n\n", ch);
		return;
	}

	if (!ch->equipment[WIELD] || !IS_SWORD(ch->equipment[WIELD]))
	{
		send_to_char("&+WThe Gods refuse to bless your anything but your sword.&n.\n", ch);
		return;
	}

	bzero(&af, sizeof(af));

	af.type = SPELL_HOLY_SWORD;
	af.duration = holy_sword_duration(level);
	af.location = APPLY_DAMROLL;
	af.modifier = holy_sword_bonus();
	affect_to_char(ch, &af);

	af.location = APPLY_HITROLL;
	af.modifier = holy_sword_bonus();
	affect_to_char(ch, &af);

	send_to_char(
		"&+WHoliness flows down from the heavens, and imbues your sword with might!&n\n",
		ch);
}

static int divine_power_duration(int level)
{
	return level / 2;
}

// Each of the hitroll and maximum strength bonuses.
static int divine_power_bonus(const Rolls &rolls)
{
	return rolls.number(2, 5);
}

// The hit points divine power adds.
static int divine_power_health(int level)
{
	return level;
}

// Above this caster level divine power also adds hit points.
static int divine_power_health_above()
{
	return 49;
}

std::string divine_power_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const std::string bonus = "+" + std::to_string(divine_power_bonus(lowest_rolls)) + " to +" +
				  std::to_string(divine_power_bonus(highest_rolls));
	std::string text = fact("Duration", game_hours(divine_power_duration(level)) +
						    " at your level, " + std::to_string(level)) +
			   fact("Hitroll", bonus) + fact("Maximum strength", bonus);
	if (GET_LEVEL(ch) > divine_power_health_above())
		text += fact("Hit points", "+" + std::to_string(divine_power_health(level)));
	else
		text += fact("Hit points",
			     "above level " + std::to_string(divine_power_health_above()));
	return text + "  Only a good caster can use it, and only while not already affected.\n";
}

void spell_divine_power(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			P_char /*victim*/, P_obj /*obj*/)
{
	struct affected_type af;
	int healpoints = divine_power_health(level);

	if (!IS_GOOD(ch))
	{
		send_to_char("Nothing seems to happen.\n", ch);
		return;
	}
	if (!affected_by_spell(ch, SPELL_DIVINE_POWER))
	{
		act("&+WHoly power surrounds $n&+W, and imbues him with it's might!&n", FALSE, ch,
		    0, 0, TO_ROOM);
		send_to_char("&+WA wave of holy energy sweeps over your body.\n", ch);

		bzero(&af, sizeof(af));

		af.type = SPELL_DIVINE_POWER;
		af.duration = divine_power_duration(level);
		af.location = APPLY_HITROLL;
		af.modifier = divine_power_bonus(live_rolls);
		affect_to_char(ch, &af);

		af.location = APPLY_STR_MAX;
		af.modifier = divine_power_bonus(live_rolls);
		affect_to_char(ch, &af);

		if (GET_LEVEL(ch) > divine_power_health_above())
		{
			af.location = APPLY_HIT;
			af.modifier = healpoints;
			affect_to_char(ch, &af);
		}
	}
}

static int atonement_duration(int level)
{
	return level / 2;
}

static int atonement_regeneration(int level)
{
	return level * 2;
}

std::string atonement_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Duration", game_hours(atonement_duration(level)) + " at your level, " +
					std::to_string(level)) +
	       fact("Health regeneration", "+" + std::to_string(atonement_regeneration(level))) +
	       "  It has no effect while you already have it.\n";
}

void spell_atonement(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
		     P_char /*victim*/, P_obj /*obj*/)
{
	struct affected_type af;
	char Gbuf1[100];

	if (affected_by_spell(ch, SPELL_ATONEMENT))
	{
		send_to_char("&+wFurther forgiveness cannot be achieved.&n\n", ch);
		return;
	}

	snprintf(
		Gbuf1, 100,
		"&+WYou atone for your sins, and feel your holy power begin to heal your body.&n\n");

	bzero(&af, sizeof(af));
	af.type = SPELL_ATONEMENT;
	af.duration = atonement_duration(level);
	af.location = APPLY_HIT_REG;
	af.modifier = atonement_regeneration(level);
	send_to_char(Gbuf1, ch);
	affect_to_char(ch, &af);
}

// some skill type stuff, thrown in here for continuty
static int holy_smite_failed_lag()
{
	return PULSE_VIOLENCE;
}

static int holy_smite_lag()
{
	return 2 * PULSE_VIOLENCE;
}

static int holy_smite_damage(const Rolls &rolls, P_char ch, int skl_lvl)
{
	return rolls.dice((GET_LEVEL(ch) / 2), (skl_lvl / 10)) / 2;
}

// A roll of 1-150 below this blinds the target.
static int holy_smite_blind_threshold(P_char ch)
{
	return (GET_LEVEL(ch) / 2);
}

static int holy_smite_blind_duration(const Rolls &rolls)
{
	return rolls.number(8, 10) * WAIT_SEC;
}

std::string holy_smite_facts(P_char ch)
{
	const int rating = GET_CHAR_SKILL(ch, SKILL_HOLY_SMITE);
	if (!rating)
		return "  You have not learned holy smite.\n";
	std::string text =
		fact("Chance", chance_under(rating + 1, 1, 101)) +
		fact("Damage", show({ holy_smite_damage(lowest_rolls, ch, rating),
				      holy_smite_damage(highest_rolls, ch, rating) })) +
		"  Armor and skin spells don't reduce it, and shields don't answer it.\n" +
		fact("Your lag", seconds(holy_smite_lag())) +
		fact("Your lag if you fail", seconds(holy_smite_failed_lag()));
	if (holy_smite_blind_threshold(ch) > 1)
		text += fact("Chance it blinds a target it leaves alive",
			     chance_under(holy_smite_blind_threshold(ch), 1, 150)) +
			fact("  For", seconds(holy_smite_blind_duration(lowest_rolls)) + " to " +
					      seconds(holy_smite_blind_duration(highest_rolls))) +
			"    (not on a target that is already blind or can't be blinded)\n";
	return text + "  Only on an evil target.\n";
}

void do_holy_smite(P_char ch, char *argument, int /*cmd*/)
{
	P_char vict = NULL;
	char name[100];
	int skl_lvl = 0;
	struct damage_messages messages = {
		"Calling forth the virtue of the gods, you smite $N with holy power!",
		"$n smirks proudly, as $e burns your soul with $s holy power!",
		"$n's smirks, chanting to $mself, and divine energy ravages $N's body!",
		"$N is utterly dissolved by your mighty torrent of divine energy!",
		"$n smirks a final time, as you feel your very soul being torn apart divine energy!",
		"$N falls to the ground, $s soul purged and cleansed by $n.",
		0
	};

	if ((skl_lvl = GET_CHAR_SKILL(ch, SKILL_HOLY_SMITE)) == 0)
	{
		send_to_char("You don't know how.\r\n", ch);
		return;
	}

	if (!*argument)
	{
		if (!(vict = GET_OPPONENT(ch)))
		{
			send_to_char("Smite whom?\r\n", ch);
			return;
		}
	}
	if (!vict)
	{
		one_argument(argument, name);

		if (!(vict = get_char_room_vis(ch, name)))
		{
			send_to_char("Smite whom?\r\n", ch);
			return;
		}
	}
	if (!CanDoFightMove(ch, vict))
	{
		return;
	}

	if (GET_ALIGNMENT(vict) > -1)
	{
		send_to_char(
			"Your conscience prevents you from executing such a maneuver on this being.\r\n",
			ch);
		return;
	}
	if (!notch_skill(ch, SKILL_HOLY_SMITE, get_property("skill.notch.offensive", 7)) &&
	    number(1, 101) > skl_lvl)
	{
		act("You fruitlessly attempt to judge $N's sins.", FALSE, ch, 0, vict, TO_CHAR);
		act("$n's attempt to judge your sins causes you to laugh malevolently.", FALSE, ch,
		    0, vict, TO_VICT);
		act("$N laughs derisively at $n, as $e attempts to purify $S soul.", FALSE, ch, 0,
		    vict, TO_NOTVICT);
		engage(ch, vict);
		CharWait(ch, holy_smite_failed_lag());
		return;
	}
	else
	{
		melee_damage(ch, vict, holy_smite_damage(live_rolls, ch, skl_lvl),
			     PHSDAM_NOSHIELDS | PHSDAM_NOREDUCE | PHSDAM_NOPOSITION, &messages);
		if (holy_smite_blind_threshold(ch) > number(1, 150) && IS_ALIVE(vict))
		{
			act("&+L$N&+L is blinded by the &+Wholy&+L energy!&n", FALSE, ch, 0, vict,
			    TO_CHAR);
			act("&+LYou are blinded by the &+Wholy&+L energy!&n", FALSE, ch, 0, vict,
			    TO_VICT);
			act("&+L$N &+Lis blinded by the &+Wholy&+L energy!&n", FALSE, ch, 0, vict,
			    TO_NOTVICT);
			blind(ch, vict, holy_smite_blind_duration(live_rolls));
		}
	}
	CharWait(ch, holy_smite_lag());
}

static int celestial_aura_duration()
{
	return 4;
}

// How much armor class celestial aura improves.
static int celestial_aura_ac(const Rolls &rolls)
{
	return rolls.number(80, 150);
}

static int celestial_aura_health(const Rolls &rolls)
{
	return rolls.number(50, 150);
}

std::string celestial_aura_facts(P_char /*ch*/)
{
	return fact("Armor class", show_signed({ -celestial_aura_ac(highest_rolls),
						 -celestial_aura_ac(lowest_rolls) })) +
	       fact("Hit points", "+" + std::to_string(celestial_aura_health(lowest_rolls)) +
					  " to +" +
					  std::to_string(celestial_aura_health(highest_rolls))) +
	       fact("Duration", game_hours(celestial_aura_duration())) +
	       "  It has no effect over another armor-type spell.\n";
}

void spell_celestial_aura(int /*level*/, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			  P_char /*victim*/, P_obj /*obj*/)
{
	struct affected_type af;

	// The affects here are temporary, until I have time to whip up something really unique -Zion 9/13/08
	if (!IS_AFFECTED(ch, AFF_ARMOR))
	{
		act("&+WA beam of light emerges from the heavens, infusing $n&+W's body with h&+Yol&+Wy energy!&n",
		    TRUE, ch, 0, 0, TO_ROOM);
		act("&+WA column of holy light sweeps over your body; your prayers are answered!&n",
		    TRUE, ch, 0, 0, TO_CHAR);
		bzero(&af, sizeof(af));
		af.type = SPELL_CELESTIAL_AURA;
		af.duration = celestial_aura_duration();
		af.location = APPLY_AC;
		af.modifier = -celestial_aura_ac(live_rolls);
		af.bitvector = AFF_ARMOR;
		affect_to_char(ch, &af);

		af.location = APPLY_HIT;
		af.modifier = celestial_aura_health(live_rolls);
		affect_to_char(ch, &af);
	}
	else
	{
		send_to_char("&+WYou're already affected by an armor-type spell.\n", ch);
	}
}
