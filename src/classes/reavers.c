/****************************************************************************
 *
 *  File: reavers.c                                             Part of Duris
 *  Usage: reaver powers: blood alliance and the named artifact weapons
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
#include "item/named_set_effects.h"
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "core/utils.h"
#include "classes/reavers.h"
#include <string.h>
#include "combat/damage.h"
#include "item/objmisc.h"
#include "magic/spells.h"
#include "abilities/abilities.h"

static int baladors_duration()
{
	return 32;
}

static int baladors_alignment_above()
{
	return 25;
}

static int baladors_saves_above()
{
	return 45;
}

static int baladors_save()
{
	return -3;
}

static int baladors_armor_above()
{
	return 4;
}

static int baladors_armor_class()
{
	return -20;
}

std::string baladors_protection_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	std::string text = fact("Duration", game_hours(baladors_duration()));
	if (level > baladors_armor_above())
		text += fact("Armor class", std::to_string(baladors_armor_class()));
	else
		text += "  It gives you nothing until level " +
			std::to_string(baladors_armor_above() + 1) + ".\n";
	if (level > baladors_alignment_above())
		text += "  It protects you from good and from evil.\n";
	if (level > baladors_saves_above())
		text += fact("All five saves", std::to_string(baladors_save()));
	return text;
}

void spell_baladors_protection(int /*level*/, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			       P_char victim, P_obj /*obj*/)
{
	struct affected_type af;

	if (affected_by_spell(ch, SPELL_BALADORS_PROTECTION))
	{
		struct affected_type *af1;

		for (af1 = victim->affected; af1; af1 = af1->next)
		{
			if (af1->type == SPELL_BALADORS_PROTECTION)
			{
				af1->duration = baladors_duration();
			}
		}
		return;
	}
	bzero(&af, sizeof(af));

	if (GET_LEVEL(ch) > baladors_alignment_above())
	{
		af.type = SPELL_BALADORS_PROTECTION;
		af.duration = baladors_duration();
		af.bitvector = AFF_PROTECT_GOOD;
		affect_to_char(victim, &af);

		af.bitvector = AFF_PROTECT_EVIL;
		affect_to_char(victim, &af);
	}

	if (GET_LEVEL(ch) > baladors_saves_above())
	{
		af.type = SPELL_BALADORS_PROTECTION;
		af.duration = baladors_duration();
		af.location = APPLY_SAVING_SPELL;
		af.modifier = baladors_save();
		affect_to_char(victim, &af);

		af.location = APPLY_SAVING_PARA;
		af.modifier = baladors_save();
		affect_to_char(victim, &af);

		af.location = APPLY_SAVING_ROD;
		af.modifier = baladors_save();
		affect_to_char(victim, &af);

		af.location = APPLY_SAVING_FEAR;
		af.modifier = baladors_save();
		affect_to_char(victim, &af);

		af.location = APPLY_SAVING_BREATH;
		af.modifier = baladors_save();
		affect_to_char(victim, &af);
	}

	//  if( GET_LEVEL(ch) > 4 && !IS_AFFECTED(victim, AFF_ARMOR) )
	// Taking the AFF_ARMOR part out of this so it'll give some ac regardless.
	if (GET_LEVEL(ch) > baladors_armor_above())
	{
		af.type = SPELL_BALADORS_PROTECTION;
		af.duration = baladors_duration();
		af.modifier = baladors_armor_class();

		//    af.bitvector = AFF_ARMOR;
		af.location = APPLY_AC;
		affect_to_char(victim, &af);
	}

	send_to_char("&+WYou feel Balador's protection wash over you.&n\n", victim);
}

static int ferrix_precision_duration()
{
	return 32;
}

static int ferrix_precision_bonus(int level)
{
	return ((int)(level / 7)) + 2;
}

std::string ferrix_precision_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Maximum dexterity and hitroll",
		    "+" + std::to_string(ferrix_precision_bonus(level)) + " at your level, " +
			    std::to_string(level)) +
	       fact("Duration", game_hours(ferrix_precision_duration())) +
	       "  Casting it again renews the duration.\n";
}

void spell_ferrix_precision(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			    P_char victim, P_obj /*obj*/)
{
	struct affected_type af;

	if (affected_by_spell(ch, SPELL_FERRIX_PRECISION))
	{
		struct affected_type *af1;

		for (af1 = victim->affected; af1; af1 = af1->next)
		{
			if (af1->type == SPELL_FERRIX_PRECISION)
			{
				af1->duration = ferrix_precision_duration();
			}
		}
		return;
	}
	bzero(&af, sizeof(af));

	af.type = SPELL_FERRIX_PRECISION;
	af.duration = ferrix_precision_duration();
	af.modifier = ferrix_precision_bonus(level);
	af.location = APPLY_DEX_MAX;
	affect_to_char(victim, &af);

	af.duration = ferrix_precision_duration();
	af.modifier = ferrix_precision_bonus(level);
	af.location = APPLY_HITROLL;
	affect_to_char(victim, &af);

	send_to_char("&+BYour precision in battle has increased greatly!&n\n", ch);
}

void spell_eshabalas_vitality(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			      P_char victim, P_obj /*obj*/)
{
	struct affected_type af;
	bool message = false;
	int healpoints = (2 * level) + number(40, 90);

	if (affected_by_spell(ch, SPELL_MIELIKKI_VITALITY))
	{
		send_to_char("&+WThe vitality spell fails.\r\n", ch);
		return;
	}

	if (affected_by_spell(ch, SPELL_VITALITY))
	{
		send_to_char("&+rThe vitality spell is negated by Eshabala!\r\n", victim);
		return;
	}

	if (affected_by_spell(ch, SPELL_ESHABALAS_VITALITY))
	{
		struct affected_type *af1;

		for (af1 = victim->affected; af1; af1 = af1->next)
			if (af1->type == SPELL_ESHABALAS_VITALITY)
			{
				af1->duration = 15;
				message = true;
			}

		if (message)
			send_to_char("&+mEshabalas vitality flows through you!&n\n", ch);

		return;
	}
	bzero(&af, sizeof(af));
	af.type = SPELL_ESHABALAS_VITALITY;
	af.duration = 15;
	af.modifier = healpoints;
	af.location = APPLY_HIT;
	affect_to_char(victim, &af);

	/*
	af.duration = 15;
	af.modifier = number(20, 45);
	af.location = APPLY_MOVE;
	affect_to_char(victim, &af);
	*/

	send_to_char("&+mEshabalas vitality flows through you!&n\n", ch);
}

static int kanchelsis_duration()
{
	return 10;
}

static int kanchelsis_earth_penalty()
{
	return 3;
}

static int kanchelsis_strength(int level)
{
	return (level / 7) + 2;
}

static int kanchelsis_fastest_level()
{
	return 56;
}

static int kanchelsis_fastest_pulse()
{
	return -3;
}

static int kanchelsis_faster_level()
{
	return 53;
}

static int kanchelsis_faster_pulse()
{
	return -2;
}

static int kanchelsis_fast_level()
{
	return 51;
}

static int kanchelsis_fast_pulse()
{
	return -1;
}

// fight.c: the extra attacks a reaver under this fury gains by level.
int kanchelsis_second_attack_level()
{
	return 41;
}

int kanchelsis_third_attack_level()
{
	return 51;
}

int kanchelsis_fourth_attack_level()
{
	return 56;
}

std::string kanchelsis_fury_facts(P_char ch)
{
	int level = GET_LEVEL(ch);
	const int real_level = level;
	if (GET_SPEC(ch, CLASS_REAVER, SPEC_EARTH_REAVER))
		level -= kanchelsis_earth_penalty();
	std::string text =
		fact("Maximum strength", "+" + std::to_string(kanchelsis_strength(level)) +
						 " at your level, " + std::to_string(real_level)) +
		fact("Duration", game_hours(kanchelsis_duration()));
	if (level >= kanchelsis_fastest_level())
		text += fact("Combat pulse", std::to_string(kanchelsis_fastest_pulse()));
	else if (level >= kanchelsis_faster_level())
		text += fact("Combat pulse", std::to_string(kanchelsis_faster_pulse()));
	else if (level >= kanchelsis_fast_level())
		text += fact("Combat pulse", std::to_string(kanchelsis_fast_pulse()));
	text += "  A reaver gains an attack with the main weapon.\n";
	if (real_level >= kanchelsis_second_attack_level())
		text += "  One with the off hand too, on a dual wield skill roll.\n";
	if (real_level >= kanchelsis_third_attack_level())
		text += "  Another with the main weapon.\n";
	if (real_level >= kanchelsis_fourth_attack_level())
		text += "  Another with the off hand.\n";
	return text;
}

void spell_kanchelsis_fury(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			   P_char victim, P_obj /*obj*/)
{
	struct affected_type af;

	if (!affected_by_spell(victim, SPELL_KANCHELSIS_FURY))
	{
		send_to_char(
			"&+mYou feel your heart start to burn as the fury of Kanchelsis takes hold!\n",
			victim);
		act("$n &+mlooks stronger and starts to move with uncanny speed!", TRUE, victim, 0,
		    0, TO_ROOM);
		bzero(&af, sizeof(af));

		// Earth reavers are a bit slower.
		if (GET_SPEC(ch, CLASS_REAVER, SPEC_EARTH_REAVER))
		{
			level -= kanchelsis_earth_penalty();
		}
		af.type = SPELL_KANCHELSIS_FURY;
		af.duration = kanchelsis_duration();
		af.modifier = kanchelsis_strength(level);
		af.location = APPLY_STR_MAX;
		affect_to_char(victim, &af);
		if (level >= kanchelsis_fastest_level())
		{
			af.location = APPLY_COMBAT_PULSE;
			af.modifier = kanchelsis_fastest_pulse();
			affect_to_char(victim, &af);
		}
		else if (level >= kanchelsis_faster_level())
		{
			af.location = APPLY_COMBAT_PULSE;
			af.modifier = kanchelsis_faster_pulse();
			affect_to_char(victim, &af);
		}
		else if (level >= kanchelsis_fast_level())
		{
			af.location = APPLY_COMBAT_PULSE;
			af.modifier = kanchelsis_fast_pulse();
			affect_to_char(victim, &af);
		}
	}
	else
	{
		struct affected_type *af1;

		for (af1 = victim->affected; af1; af1 = af1->next)
			if (af1->type == SPELL_KANCHELSIS_FURY)
			{
				af1->duration = kanchelsis_duration();
			}
	}
}

void spell_blood_alliance(int /*level*/, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			  P_obj /*obj*/)
{
	if (get_linking_char(victim, LNK_BLOOD_ALLIANCE))
	{
		send_to_char("This person has already granted blood allegiance to someone.\n", ch);
		return;
	}

	if (!is_linked_to(ch, victim, LNK_CONSENT))
	{
		send_to_char("You need consent from your friend to seal your alliance.\n", ch);
		return;
	}

	if (ch == victim)
	{
		send_to_char("Nothing happens.\n", ch);
		return;
	}

	act("Your forearm glows &+rred&n as you align it with $N's forearm.", FALSE, ch, 0, victim,
	    TO_CHAR);
	act("Your forearm glows &+rred&n as $n aligns it with $s forearm.", FALSE, ch, 0, victim,
	    TO_VICT);
	act("&+rRed glow&n surrounds $n's and $N's forearms as they align them "
	    "with each other.",
	    FALSE, ch, 0, victim, TO_NOTVICT);

	link_char(ch, victim, LNK_BLOOD_ALLIANCE);
}

void check_blood_alliance(P_char ch, int dam)
{
	P_char linked;
	struct affected_type *afp, af;

	if (GET_HIT(ch) >= GET_MAX_HIT(ch) * 0.5)
		return;

	linked = get_linking_char(ch, LNK_BLOOD_ALLIANCE);

	if (!linked)
		linked = get_linked_char(ch, LNK_BLOOD_ALLIANCE);

	if (linked)
	{
		afp = get_spell_from_char(ch, SPELL_BLOOD_ALLIANCE);
		if (afp)
			afp->modifier += dam;
		else
		{
			memset(&af, 0, sizeof(af));
			af.type = SPELL_BLOOD_ALLIANCE;
			af.flags = AFFTYPE_NOSHOW | AFFTYPE_NODISPEL | AFFTYPE_NOAPPLY;
			af.modifier = dam;
			af.duration = 1;
			affect_to_char(ch, &af);
			add_event(event_blood_alliance, 0, ch, linked, 0, 0, 0, 0);
		}
	}
}

void event_blood_alliance(P_char ch, P_char /*victim*/, P_obj /*obj*/, void * /*data*/)
{
	P_char linked;
	struct affected_type *af;
	int sdam;

	linked = get_linking_char(ch, LNK_BLOOD_ALLIANCE);

	if (!linked)
		linked = get_linked_char(ch, LNK_BLOOD_ALLIANCE);

	if (linked->in_room != ch->in_room)
		return;

	if (GET_HIT(linked) < GET_MAX_HIT(linked) * 0.7)
		return;

	if (!(af = get_spell_from_char(ch, SPELL_BLOOD_ALLIANCE)))
		return;

	sdam = (int)(get_property("damage.reduction.bloodAlliance", 0.4) * af->modifier);
	sdam = MIN(sdam, GET_HIT(linked) - 5);

	GET_HIT(linked) -= sdam;
	vamp(ch, sdam, GET_MAX_HIT(ch));
	if (sdam > number(0, 40))
	{
		act("You share some of your blood with $N.", FALSE, linked, 0, ch, TO_CHAR);
		if (linked->desc)
			linked->desc->prompt_mode = TRUE;
	}

	affect_remove(ch, af);
}

static int ilienzes_flame_sword_duration(int level)
{
	return level / 2;
}

static int ilienzes_flame_sword_hitroll(const Rolls &rolls)
{
	return rolls.number(1, 4);
}

// The fire each weapon hit adds, and more under your own fireshield.
static int ilienze_sword_damage(const Rolls &rolls, int level)
{
	return rolls.number(1, (level / 4));
}

static int ilienze_sword_fireshield(const Rolls &rolls)
{
	return rolls.number(2, 8);
}

// A charged burst fires when the charge beats this roll.
static int ilienze_sword_burst_roll(const Rolls &rolls)
{
	return rolls.number(4, 40);
}

static int ilienze_sword_burst(const Rolls &rolls, int charge)
{
	return rolls.dice(charge, 12);
}

std::string ilienzes_flame_sword_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Hitroll", "+" + show({ ilienzes_flame_sword_hitroll(lowest_rolls),
					    ilienzes_flame_sword_hitroll(highest_rolls) })) +
	       fact("Duration",
		    game_hours(ilienzes_flame_sword_duration(level)) + " at your level") +
	       fact("Fire on each hit",
		    show_landing({ ilienze_sword_damage(lowest_rolls, level),
				   ilienze_sword_damage(highest_rolls, level) })) +
	       fact("With fireshield", "+" + show({ ilienze_sword_fireshield(lowest_rolls),
						    ilienze_sword_fireshield(highest_rolls) })) +
	       "  A target with fireshield takes only 1. The fire cannot be shrugged.\n"
	       "  With fireshield and immolate, each hit adds a charge.\n" +
	       fact("It bursts at a charge above",
		    show({ ilienze_sword_burst_roll(lowest_rolls),
			   ilienze_sword_burst_roll(highest_rolls) })) +
	       fact("A burst of fire deals, per charge",
		    show({ ilienze_sword_burst(lowest_rolls, 1),
			   ilienze_sword_burst(highest_rolls, 1) })) +
	       "  You need a sword, flail or whip in hand. Constructs are unaffected.\n";
}

void spell_ilienzes_flame_sword(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
				P_char victim, P_obj /*obj*/)
{
	struct affected_type af;
	bool weapon = false;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (affected_by_spell(ch, SPELL_ILIENZES_FLAME_SWORD))
	{
		send_to_char("Your weapon is already on &+Rfire!!\n", ch);
		return;
	}

	if (ch->equipment[WIELD] && FLAME_REAVER_WEAPONS(ch->equipment[WIELD]))
	{
		weapon = true;
	}

	if (!weapon && ch->equipment[WIELD2] && FLAME_REAVER_WEAPONS(ch->equipment[WIELD2]))
	{
		weapon = true;
	}

	if (!weapon)
	{
		send_to_char("You need to wield the correct type of weapon!\n", ch);
		return;
	}

	bzero(&af, sizeof(af));

	af.type = SPELL_ILIENZES_FLAME_SWORD;
	af.duration = ilienzes_flame_sword_duration(level);
	af.location = APPLY_HITROLL;
	af.modifier = ilienzes_flame_sword_hitroll(live_rolls);

	affect_to_char(victim, &af);

	send_to_char("&+rIlienze's &+Lpower&+r &+Rflows&+r down inflaming your weapon!!&n\n", ch);
}

bool ilienze_sword(P_char ch, P_char victim, P_obj wpn)
{
	int dam;
	char ch_msg[256], vict_msg[256], room_msg[256];
	struct affected_type *afp, af;

	struct damage_messages messages = {
		"&+LYour&N $q &+Rburns&n $N &+Rwith a godly fire!&n",
		"&+L$n's&N $q &+Rburns you with a godly fire!&n",
		"&+L$n's&N $q &+Rburns&n $N &+Rwith a godly fire!&n",
		"&+LYour&N $q &+Rburned&n $N &+Rto a crisp!&n",
		"&+L$n's&N $q's &+Rgodly fire burned&n $N &+Rto death!&n",
		"&+L$n's&N $q &+Rburned&n $N &+Rto a crisp!&n",
		DAMMSG_TERSE
	};

	struct damage_messages proc_messages = {
		ch_msg,
		vict_msg,
		room_msg,
		"&+rUnholy &+Rflames&n &+rflow down your blade and devour $N's &+rbody in a &+Rdancing inferno&n.",
		"&+rUnholy &+Rflames&n &+rflow down $n's &+rblade and devour your body in a &+Rdancing inferno&n.",
		"&+rUnholy &+Rflames&n &+rflow down $n's &+rblade and devour $N's &+rbody in a &+Rdancing inferno&n.",
		DAMMSG_TERSE
	};

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim) || !(wpn) || !FLAME_REAVER_WEAPONS(wpn))
	{
		return false;
	}

	messages.obj = wpn;

	dam = ilienze_sword_damage(live_rolls, GET_LEVEL(ch));

	if (IS_AFFECTED2(ch, AFF2_FIRESHIELD))
	{
		dam += ilienze_sword_fireshield(live_rolls);
	}

	if (IS_AFFECTED2(victim, AFF2_FIRESHIELD))
	{
		dam = 1;
	}

	if (spell_damage(ch, victim, dam, SPLDAM_FIRE, SPLDAM_NODEFLECT | SPLDAM_NOSHRUG,
			 &messages) != DAM_NONEDEAD)
	{
		return TRUE;
	}

	if (IS_AFFECTED2(ch, AFF2_FIRESHIELD) && has_innate(ch, INNATE_IMMOLATE))
	{
		afp = get_spell_from_char(ch, TAG_ILIENZE_SWORD_CHARGE);

		if (!afp)
		{
			memset(&af, 0, sizeof(af));
			af.type = TAG_ILIENZE_SWORD_CHARGE;
			af.modifier = 1;
			af.flags = AFFTYPE_NOSHOW | AFFTYPE_NODISPEL | AFFTYPE_NOAPPLY;
			af.duration = 2;
			afp = affect_to_char(ch, &af);
			send_to_char(
				"&+rYou start to gather the &+Rf&+Yl&+Ra&+rmes&n &+raround your blade..&n\n",
				ch);
		}
		else if (afp->modifier > ilienze_sword_burst_roll(live_rolls))
		{
			if (afp->modifier < 8)
			{
				ilienze_sword_proc_messages(ch_msg, vict_msg, room_msg,
							    sizeof ch_msg,
							    "&+Rf&+Yi&+Rr&+re&+rball&n");
			}
			else if (afp->modifier < 14)
			{
				ilienze_sword_proc_messages(ch_msg, vict_msg, room_msg,
							    sizeof ch_msg,
							    "&+Rf&+Yi&+Rr&+Re&+rb&+rall");
			}
			else if (afp->modifier < 21)
			{
				ilienze_sword_proc_messages(ch_msg, vict_msg, room_msg,
							    sizeof ch_msg,
							    "&+Rf&+Yi&+Rr&+Re&+Rb&+rall&n");
			}
			else
			{
				ilienze_sword_proc_messages(ch_msg, vict_msg, room_msg,
							    sizeof ch_msg,
							    "&+Rf&+Yi&+Rr&+Re&+Rb&+Ra&+rll&n");
			}

			dam = ilienze_sword_burst(live_rolls, afp->modifier);
			afp->modifier = 0;

			return (spell_damage(ch, victim, dam, SPLDAM_FIRE, 0, &proc_messages) !=
				DAM_NONEDEAD);
		}
		else
		{
			afp->modifier++;
		}
	}

	return FALSE;
}

/* Formats into the caller's own buffers.  size is the caller's real buffer
   size: this used to format with MAX_STRING_LENGTH into 256-byte buffers. */
void ilienze_sword_proc_messages(char *attacker, char *victim, char *room, size_t size,
				 const char *sub)
{
	snprintf(
		attacker, size,
		"&+rUnholy &+Rflames&n &+rflow down your blade and shoot in a %s &+rtowards $N&+r.&n",
		sub);
	snprintf(
		victim, size,
		"&+rUnholy &+Rflames&n &+rflow down $n's &+rblade and shoot in a %s &+rtowards &+Ryou&+r.&n",
		sub);
	snprintf(
		room, size,
		"&+rUnholy &+Rflames&n &+rflow down $n's &+rblade and shoot in a %s &+rtowards $N&+r.&n",
		sub);
}

void cegilunes_broken(struct char_obj_link_data *cold)
{
	wear_off_message(cold->ch, cold->affect);
}

static int cegilune_blade_duration(int level)
{
	return level / 2;
}

// A roll of 0 raises the damage tier and deals that tier's damage.
static int cegilune_tier_roll(const Rolls &rolls)
{
	return rolls.number(0, 4);
}

static int cegilune_tier_0(const Rolls &rolls)
{
	return rolls.number(8, 16);
}

static int cegilune_tier_1(const Rolls &rolls)
{
	return rolls.number(16, 32);
}

static int cegilune_tier_2(const Rolls &rolls)
{
	return rolls.number(32, 40);
}

static int cegilune_tier_3(const Rolls &rolls)
{
	return rolls.number(40, 56);
}

static int cegilune_tier_4(const Rolls &rolls)
{
	return rolls.number(56, 64);
}

static int cegilune_tier_5(const Rolls &rolls)
{
	return rolls.number(64, 80);
}

// From this tier a roll of 0 sets the target on fire.
static int cegilune_burn_tier()
{
	return 3;
}

static int cegilune_burn_roll(const Rolls &rolls)
{
	return rolls.number(0, 5);
}

// The burn counts down from this, once every interval, before each burn.
static int cegilune_burn_rounds()
{
	return 5;
}

static int cegilune_burn_interval()
{
	return PULSE_VIOLENCE;
}

static int cegilune_burn_damage(const Rolls &rolls)
{
	return rolls.dice(12, 4);
}

std::string cegilunes_searing_blade_facts(P_char ch)
{
	const auto range = [](int (*tier)(const Rolls &))
	{ return show({ tier(lowest_rolls), tier(highest_rolls) }); };
	const int tier_odds =
		cegilune_tier_roll(highest_rolls) - cegilune_tier_roll(lowest_rolls) + 1;
	const int burn_odds =
		cegilune_burn_roll(highest_rolls) - cegilune_burn_roll(lowest_rolls) + 1;
	return fact("Duration",
		    game_hours(cegilune_blade_duration(GET_LEVEL(ch))) + " at your level") +
	       "  It lasts no longer than Ilienze's flaming sword has left.\n" +
	       fact("Each hit raises the tier", "1 in " + std::to_string(tier_odds)) +
	       fact("Fire by tier", range(cegilune_tier_0) + ", " + range(cegilune_tier_1) + ", " +
					    range(cegilune_tier_2) + ", " + range(cegilune_tier_3) +
					    ", " + range(cegilune_tier_4) + ", " +
					    range(cegilune_tier_5)) +
	       "  A miss or a change of fight resets the tier.\n" +
	       fact("From tier " + std::to_string(cegilune_burn_tier()) + ", each hit sets a burn",
		    "1 in " + std::to_string(burn_odds)) +
	       fact("Burn", range(cegilune_burn_damage) + " fire every " +
				    seconds(cegilune_burn_interval()) + ", " +
				    std::to_string(cegilune_burn_rounds() - 1) + " times") +
	       "  You need Ilienze's flaming sword up and a sword, flail or whip in hand.\n"
	       "  Only the weapon it was cast on burns. Constructs are unaffected.\n";
}

void spell_cegilunes_searing_blade(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
				   P_char /*victim*/, P_obj obj)
{
	struct affected_type af;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	// If they don't have a prime or secondary reaver weapon.
	if (!(((obj = ch->equipment[WIELD]) && FLAME_REAVER_WEAPONS(obj)) ||
	      ((obj = ch->equipment[WIELD2]) && FLAME_REAVER_WEAPONS(obj)) ||
	      ((obj = ch->equipment[WIELD3]) && FLAME_REAVER_WEAPONS(obj)) ||
	      ((obj = ch->equipment[WIELD4]) && FLAME_REAVER_WEAPONS(obj))))
	{
		send_to_char("You need to wield the correct type of weapon!\n", ch);
		return;
	}

	if (affected_by_spell(ch, SPELL_CEGILUNE_BLADE))
	{
		send_to_char("&+LCegilune can infuse your weapon no further.&n\n", ch);
		return;
	}

	if (!affected_by_spell(ch, SPELL_ILIENZES_FLAME_SWORD))
	{
		send_to_char(
			"&+LYour weapon glows for a moment, and then grows cool once more.&n\n",
			ch);
		return;
	}

	struct affected_type *afp = get_spell_from_char(ch, SPELL_ILIENZES_FLAME_SWORD);

	bzero(&af, sizeof(af));

	af.type = SPELL_CEGILUNE_BLADE;
	af.duration = MIN(afp->duration, cegilune_blade_duration(level));
	af.location = APPLY_NONE;
	af.modifier = 0;

	linked_affect_to_char_obj(ch, &af, obj, LNK_CEGILUNE);

	act("&+LYour weapon glows with a strange &+Rh&+rea&+Rt&+L as Cegilune infuses it.&n", false,
	    ch, 0, 0, TO_CHAR);
}

// Called by reaver_hit_proc, this function handles the cegilune's proc.
bool cegilune_blade(P_char ch, P_char victim, P_obj wpn)
{
	struct affected_type *afp, *af2p, af;
	struct damage_messages tiers_messages[6] = {
		{ "&+LThe &+Rs&+re&+Ra&+rr&+Ri&+rn&+Rg &+Lblade slices into $N, causing $m to scream in pain!&n",
		  "&+L$n's $q &+Lglows &+rf&+Rie&+rry &+wh&+Wo&+wt &+Las it painfully brands your flesh.&n",
		  "&+L$N screams in &+rt&+Re&+rr&+Rr&+ro&+Rr &+Las $n's $q &+Lsears past $S armor into $S flesh!&n",
		  "&+LThe &+rs&+Rea&+rr&+Rin&+rg &+Lw&+round&+Ls are too much for $N to handle, and $E falls to the ground, thrashing wildly.&n",
		  "&+LAs $n's $q &+Lstrikes you, it opens up a fatal w&+roun&+Ld. The last thing you sense is the burning of your own &+rflesh&+L.&n",
		  "&+LThe &+rs&+Rea&+rr&+Rin&+rg &+Lw&+round&+Ls are too much for $N to handle, and $E falls to the ground, thrashing wildly.&n",
		  DAMMSG_TERSE },
		{ "&+LYour $q &+Ltakes on a mind of it's own as it &+rb&+Ru&+rr&+Rn&+rs&+L deep into $N's flesh.&n",
		  "&+w$n's $q &+Lglows &+rf&+Rie&+rry &+wh&+Wo&+wt &+was it painfully brands your flesh.&n",
		  "&+L$N screams in &+rbl&+Roo&+rd&+wc&+rur&+Rdl&+rin&+Rg &+Lpain as $n's $q &+Lsears deep into $S flesh.&n",
		  "&+LThe &+rs&+Rea&+rr&+Rin&+rg &+Lw&+round&+Ls are too much for $N to handle, and $E falls to the ground, thrashing wildly.&n",
		  "&+LAs $n's $q strikes you, it opens up a fatal w&+roun&+Ld. The last thing you sense is the burning of your own &+rflesh&+L.&n",
		  "&+LThe &+rs&+Rea&+rr&+Rin&+rg &+Lw&+round&+Ls are too much for $N to handle, and $E falls to the ground, thrashing wildly.&n",
		  DAMMSG_TERSE },
		{ "&+rSe&+Rar&+wi&+rng &+Lf&+rur&+Ly fills your $q &+Las it rends $N's &+rf&+Rl&+re&+Rs&+rh&+L, leaving a horrid stench.&n",
		  "&+L$n thrusts $s $q &+Linto your flesh with &+wbli&+Wndin&+wg &+Lf&+rur&+Ly, causing you great &+rse&+Rar&+wi&+rng &+Lp&+Ra&+ri&+Ln!&n",
		  "&+L$n's $q &+L&+Lmoves in a &+wbli&+Wndin&+wg &+Lrush of &+rse&+Rar&+wi&+rng &+Lf&+rur&+Ly as it slices into $N!&n",
		  "&+LThe &+rs&+Rea&+rr&+Rin&+rg &+Lw&+round&+Ls are too much for $N to handle, and $E falls to the ground, thrashing wildly.&n",
		  "&+LAs $n's $q strikes you, it opens up a fatal w&+roun&+Ld. The last thing you sense is the burning of your own &+rflesh&+L.&n",
		  "&+LThe &+rs&+Rea&+rr&+Rin&+rg &+Lw&+round&+Ls are too much for $N to handle, and $E falls to the ground, thrashing wildly.&n",
		  DAMMSG_TERSE },
		{ "&+LYou press your attack, and $q &+Lglows with a &+Wwh&+wit&+We &+rh&+Ro&+rt &+rf&+Rl&+ra&+Rm&+re&+L, nearly igniting $N's &+rflesh&+L!&n",
		  "&+L$n gazes into your eyes, &+rh&+Rell&+rfi&+Lr&+we &+Ldancing in $s pupils. Suddenly, $q &+Lcomes alive with &+rs&+Rear&+Lin&+rg &+rf&+Rl&+ra&+Rm&+re&+Rs &+Las it slashes into you!",
		  "&+L$n fiercely presses $s attack on $N, and $q &+Lglows with &+Wwh&+wit&+We &+rh&+Ro&+rt &+rf&+Rl&+ra&+Rm&+re&+L, cleaving into $S flesh with it's &+rd&+Rem&+Lon&+ri&+Rc "
		  "&+rh&+Rell&+rfi&+Lr&+we&+L!&n",
		  "&+LThe &+rs&+Rea&+rr&+Rin&+rg &+Lw&+round&+Ls are too much for $N to handle, and $E falls to the ground, thrashing wildly.&n",
		  "&+LAs $n's $q strikes you, it opens up a fatal w&+roun&+Ld. The last thing you sense is the burning of your own &+rflesh&+L.&n",
		  "&+LThe &+rs&+Rea&+rr&+Rin&+rg &+Lw&+round&+Ls are too much for $N to handle, and $E falls to the ground, thrashing wildly.&n",
		  DAMMSG_TERSE },
		{ "&+LNearing the apex of it's might, &+ww&+Wi&+ws&+Wp&+ws&+L of &+rse&+Rar&+Lin&+rg &+rf&+Rl&+ra&+Rm&+re&+Rs &+Lbegin to dance along the edges of $q &+Las it strikes $N.&n",
		  "&+LYou feel the very &+rw&+Rar&+rmt&+Rh &+Lbeing sucked from your &+cs&+Co&+cu&+Cl&+L, being used to feed the growing &+rhe&+Rllf&+Lir&+re &+Las $n's $q &+Lslams into your body!",
		  "&+LWithout warning, $n's $q &+Lbegins sucking all the &+rh&+Rea&+rt &+Lfrom the room as it sla&+Rs&+Lhes into $N!",
		  "&+LThe &+rs&+Rea&+rr&+Rin&+rg &+Lw&+round&+Ls are too much for $N to handle, and $E falls to the ground, thrashing wildly.&n",
		  "&+LAs $n's $q strikes you, it opens up a fatal w&+roun&+Ld. The last thing you sense is the burning of your own &+rflesh&+L.&n",
		  "&+LThe &+rs&+Rea&+rr&+Rin&+rg &+Lw&+round&+Ls are too much for $N to handle, and $E falls to the ground, thrashing wildly.&n",
		  DAMMSG_TERSE },
		{ "&+LYour $q &+Lbursts into &+rhe&+Rll&+ris&+Lh &+rf&+Rl&+ra&+Rm&+re&+Rs &+Land causes $N to scream in great and &+wa&+Lg&+wo&+Ln&+wi&+Lz&+wi&+Ln&+wg &+Lp&+rai&+Ln as it burns away at $S "
		  "&+rflesh&+L!",
		  "&+rHe&+Rll&+Lis&+rh &+rf&+Rl&+ra&+Rm&+re&+Rs &+Lburst forth from $n's $q&+L, rending your flesh and causing you incredible p&+rai&+Ln!",
		  "&+rF&+Rl&+ra&+Rm&+re&+Rs &+Lburst forth from $q&+L, dancing along $N's &+rflesh&+L as $E screams in sheer &+Lp&+rai&+Ln!",
		  "&+LThe &+rs&+Rea&+rr&+Rin&+rg &+Lw&+round&+Ls are too much for $N to handle, and $E falls to the ground, thrashing wildly.&n",
		  "&+LAs $n's $q strikes you, it opens up a fatal w&+roun&+Ld. The last thing you sense is the burning of your own &+rflesh&+L.&n",
		  "&+LThe &+rs&+Rea&+rr&+Rin&+rg &+Lw&+round&+Ls are too much for $N to handle, and $E falls to the ground, thrashing wildly.&n",
		  DAMMSG_TERSE }
	};

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim) || !(wpn) || !FLAME_REAVER_WEAPONS(wpn))
	{
		return FALSE;
	}

	for (int i = 0; i < 6; i++)
		tiers_messages[i].obj = wpn;

	afp = get_spell_from_char(ch, SPELL_CEGILUNE_BLADE);
	if (!afp)
		return FALSE;

	// Chance for upgrading tier of damage.
	if (!cegilune_tier_roll(live_rolls))
	{
		// Modifier holds tier of damage.
		switch (afp->modifier++)
		{
		case 0:
			if (spell_damage(ch, victim, cegilune_tier_0(live_rolls), SPLDAM_FIRE,
					 SPLDAM_NODEFLECT,
					 &tiers_messages[afp->modifier]) != DAM_NONEDEAD)
			{
				afp->modifier = 0;
				return TRUE;
			}
			break;
		case 1:
			if (spell_damage(ch, victim, cegilune_tier_1(live_rolls), SPLDAM_FIRE,
					 SPLDAM_NODEFLECT,
					 &tiers_messages[afp->modifier]) != DAM_NONEDEAD)
			{
				afp->modifier = 0;
				return TRUE;
			}
			break;
		case 2:
			if (spell_damage(ch, victim, cegilune_tier_2(live_rolls), SPLDAM_FIRE,
					 SPLDAM_NODEFLECT,
					 &tiers_messages[afp->modifier]) != DAM_NONEDEAD)
			{
				afp->modifier = 0;
				return TRUE;
			}
			break;
		case 3:
			if (spell_damage(ch, victim, cegilune_tier_3(live_rolls), SPLDAM_FIRE,
					 SPLDAM_NODEFLECT,
					 &tiers_messages[afp->modifier]) != DAM_NONEDEAD)
			{
				afp->modifier = 0;
				return TRUE;
			}
			break;
		case 4:
			if (spell_damage(ch, victim, cegilune_tier_4(live_rolls), SPLDAM_FIRE,
					 SPLDAM_NODEFLECT,
					 &tiers_messages[afp->modifier]) != DAM_NONEDEAD)
			{
				afp->modifier = 0;
				return TRUE;
			}
			break;
		default:
			if (spell_damage(ch, victim, cegilune_tier_5(live_rolls), SPLDAM_FIRE,
					 SPLDAM_NODEFLECT, &tiers_messages[5]) != DAM_NONEDEAD)
			{
				afp->modifier = 0;
				return TRUE;
			}
			afp->modifier = 0; // lets not go over max int
			break;
		}
	}

	// if we are on 3th tier or higher there is chance for immolate like attack
	if (afp->modifier >= cegilune_burn_tier())
	{
		if (!cegilune_burn_roll(live_rolls))
		{
			act("&+LYour $q&+L suddenly ig&+rni&+Rte&+rs &+Linto &+rf&+Rl&+ra&+Rm&+re&+Rs &+Las it strikes $N!&n",
			    FALSE, ch, wpn, victim, TO_CHAR);
			act("&+L$n's $q&+L ignites into a raging &+ri&+Rn&+rf&+Re&+rr&+Rn&+ro &+Las it bites deep into your &+rflesh&+L.&n",
			    FALSE, ch, wpn, victim, TO_VICT);
			act("&+LRaging &+rhe&+Rll&+rfi&+Lre bursts forth from $n's $q&+L as it slices into $N!&n",
			    FALSE, ch, wpn, victim, TO_NOTVICT);

			af2p = get_spell_from_char(victim, TAG_CEGILUNE_FIRE);
			if (!af2p)
			{
				memset(&af, 0, sizeof(af));
				af.type = TAG_CEGILUNE_FIRE;
				af.modifier = cegilune_burn_rounds();
				af.flags = AFFTYPE_NOSHOW | AFFTYPE_NODISPEL | AFFTYPE_NOAPPLY;
				af.duration = 10;
				af2p = affect_to_char(victim, &af);
				add_event(event_cegilune_searing, cegilune_burn_interval(), ch,
					  victim, wpn, 0, 0, 0);
			}
			else
			{
				af2p->modifier = cegilune_burn_rounds();
			}
		}
	}
	return FALSE;
}

void event_cegilune_searing(P_char ch, P_char vict, P_obj wpn, void * /*data*/)
{
	struct damage_messages messages = {
		"",
		"&+LThe &+rf&+Ri&+rr&+Re&+rs &+Llick at your wound, causing you to scream in pain!&n",
		"",
		"&+L$N &+Lsuddenly begins thrashing around violently. Several chunks of smoldering &+rflesh&+L fall from $S body, and $E topples to the ground, screaming violently--then is suddenly "
		"silent!&n",
		"&+LThe &+rf&+Ri&+re&+Rr&+ry &+Lp&+rai&+Ln is too much for you to handle, and you think you hear the incessant cackling of &+md&+Lemoni&+mc &+Llaughter as your vision spins toward "
		"oblivion...&n",
		"&+L$N &+Lsuddenly begins thrashing around violently. Several chunks of smoldering &+rflesh&+L fall from$S body, and $E topples to the ground, screaming violently--then is suddenly silent!&n",
		0
	};

	if (!IS_ALIVE(ch) || !IS_ALIVE(vict) || !FLAME_REAVER_WEAPONS(wpn))
	{
		return;
	}

	struct affected_type *afp;
	afp = get_spell_from_char(vict, TAG_CEGILUNE_FIRE);

	if (!afp)
	{
		return;
	}

	if (--(afp->modifier) <= 0)
	{
		send_to_char("&+RThe flames engulfing your body subside.\n", vict);
		affect_remove(vict, afp);
		return;
	}

	// This correlates to 3 to 12 damage
	if (spell_damage(ch, vict, cegilune_burn_damage(live_rolls), SPLDAM_FIRE, SPLDAM_NODEFLECT,
			 &messages) == DAM_NONEDEAD)
	{
		add_event(event_cegilune_searing, cegilune_burn_interval(), ch, vict, wpn, 0, 0, 0);
	}
}

static int girilals_granite_hammer_duration(int level)
{
	return level / 2;
}

static int girilals_granite_hammer_damroll(int level)
{
	return level / 14;
}

static int girilals_granite_hammer_damage(const Rolls &rolls, int level)
{
	return rolls.number(8, (level * 2) / 5);
}

std::string girilals_granite_hammer_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const int a = girilals_granite_hammer_damage(lowest_rolls, level);
	const int b = girilals_granite_hammer_damage(highest_rolls, level);
	return fact("Damroll", "+" + std::to_string(girilals_granite_hammer_damroll(level)) +
				       " at your level, " + std::to_string(level)) +
	       fact("Duration", game_hours(girilals_granite_hammer_duration(level))) +
	       fact("Earth damage on each hit", show({ MAX(1, a), MAX(1, b) })) +
	       "  It cannot be shrugged. Constructs are unaffected.\n"
	       "  You need a one-handed bludgeon in hand.\n";
}

void spell_girilals_granite_hammer(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
				   P_char victim, P_obj /*obj*/)
{
	P_obj weapon = NULL;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (affected_by_spell(ch, SPELL_GIRILALS_GRANITE_HAMMER))
	{
		send_to_char("&+LGirilal&+L refuses to grant you any more of his powers!&n\n", ch);
		return;
	}

	if (ch->equipment[WIELD] && EARTH_REAVER_WEAPONS(ch->equipment[WIELD]))
	{
		weapon = ch->equipment[WIELD];
	}

	if (!weapon && ch->equipment[WIELD2] && EARTH_REAVER_WEAPONS(ch->equipment[WIELD2]))
	{
		weapon = ch->equipment[WIELD2];
	}

	if (!weapon)
	{
		send_to_char(
			"&+LThe power of &+yGirilal&+L requires you to have a suitable weapon!&n\n",
			ch);
		return;
	}

	struct affected_type af;
	bzero(&af, sizeof(af));

	af.type = SPELL_GIRILALS_GRANITE_HAMMER;
	af.duration = girilals_granite_hammer_duration(level);
	af.location = APPLY_DAMROLL;
	// +1 at 30 and +4 at 56.
	af.modifier = girilals_granite_hammer_damroll(level);

	affect_to_char(victim, &af);

	act("&+LA dull &+yglow&+L surrounds $p.", FALSE, ch, weapon, NULL, TO_CHAR);
}

bool girilals_granite_hammer(P_char ch, P_char victim, P_obj wpn)
{
	int dam;

	struct damage_messages messages = {
		"&+LThe &+ydust&+L surrounding $p &+Lscratches at $N&+L!&n",
		"&+LThe &+ydust&+L surrounding $n&+L's $q &+Lscratches at your flesh!&n",
		"&+LThe &+ydust&+L surrounding $n&+L's $q &+Lscratchs at $N&+L's flesh!&n",
		"&+LThe &+ydust&+L is too much for $N&+L; they fall to the ground in a &+rbloody&+L heap.&n",
		"&+LThe &+ydust&+L overwhelms you causing everything to go black.&n",
		"&+LThe &+ydust&+L is too much for $N&+L; they fall to the ground in a &+rbloody&+L heap.&n",
		DAMMSG_TERSE
	};

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim) || !(wpn) || !EARTH_REAVER_WEAPONS(wpn))
	{
		return FALSE;
	}

	messages.obj = wpn;

	// 2 to 5 damage at lvl 50.
	dam = girilals_granite_hammer_damage(live_rolls, GET_LEVEL(ch));

	dam = MAX(1, dam);

	if (spell_damage(ch, victim, dam, SPLDAM_EARTH, SPLDAM_NODEFLECT | SPLDAM_NOSHRUG,
			 &messages) != DAM_NONEDEAD)
		return TRUE;

	return FALSE;
}

void ileshs_broken(struct char_obj_link_data *cold)
{
	wear_off_message(cold->ch, cold->affect);
}

static int ileshs_duration(int level)
{
	return level / 2;
}

// A roll of 0 raises the tier and casts that tier's spell.
static int ilesh_tier_roll(const Rolls &rolls)
{
	return rolls.number(0, 4);
}

// In the fifth tier, a roll of 0 casts acid immolate rather than acid stream.
static int ilesh_immolate_roll(const Rolls &rolls)
{
	return rolls.number(0, 3);
}

static int ilesh_blindness(const Rolls &rolls)
{
	return rolls.number(4, 12) * WAIT_SEC;
}

std::string ileshs_smashing_fury_facts(P_char ch)
{
	const int tier_odds = ilesh_tier_roll(highest_rolls) - ilesh_tier_roll(lowest_rolls) + 1;
	const int immolate_odds =
		ilesh_immolate_roll(highest_rolls) - ilesh_immolate_roll(lowest_rolls) + 1;
	return fact("Duration", game_hours(ileshs_duration(GET_LEVEL(ch))) + " at your level") +
	       "  It lasts no longer than Girilal's hammer has left.\n" +
	       fact("Each hit casts at your level", "1 in " + std::to_string(tier_odds)) +
	       "  In turn: blindness, acid blast twice, earthen grasp, then acid stream.\n" +
	       fact("Acid immolate replaces the stream", "1 in " + std::to_string(immolate_odds)) +
	       fact("Then dust blinds the target",
		    seconds(ilesh_blindness(lowest_rolls)) + " to " +
			    seconds(ilesh_blindness(highest_rolls))) +
	       "  The turn then starts over.\n"
	       "  You need Girilal's hammer up and a one-handed bludgeon in hand.\n"
	       "  Only the weapon it was cast on counts. Constructs are unaffected.\n";
}

void spell_ileshs_smashing_fury(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
				P_char /*victim*/, P_obj /*obj*/)
{
	struct affected_type af;
	P_obj weapon;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	// If they don't have a prime or secondary reaver weapon.
	if (!(((weapon = ch->equipment[WIELD]) && EARTH_REAVER_WEAPONS(weapon)) ||
	      ((weapon = ch->equipment[WIELD2]) && EARTH_REAVER_WEAPONS(weapon)) ||
	      ((weapon = ch->equipment[WIELD3]) && EARTH_REAVER_WEAPONS(weapon)) ||
	      ((weapon = ch->equipment[WIELD4]) && EARTH_REAVER_WEAPONS(weapon))))
	{
		send_to_char("You need to wield the correct type of weapon!\n", ch);
		return;
	}

	if (affected_by_spell(ch, SPELL_ILESHS_SMASHING_FURY))
	{
		send_to_char("&+yIlesh &+Lwill infuse your weapon no further.&n\n", ch);
		return;
	}

	if (!affected_by_spell(ch, SPELL_GIRILALS_GRANITE_HAMMER))
	{
		send_to_char(
			"&+LYour weapon glows for a moment, and then grows cool once more.&n\n",
			ch);
		return;
	}

	struct affected_type *afp = get_spell_from_char(ch, SPELL_GIRILALS_GRANITE_HAMMER);

	bzero(&af, sizeof(af));

	af.type = SPELL_ILESHS_SMASHING_FURY;
	af.duration = MIN(afp->duration, ileshs_duration(level));
	af.location = APPLY_NONE;
	af.modifier = 0;

	linked_affect_to_char_obj(ch, &af, weapon, LNK_ILESH);

	act("&+L$p&+L glows with a strange &+yhue&+L as &+yIlesh&+L infuses it.&n", FALSE, ch,
	    weapon, 0, TO_CHAR);
}

// Called by reaver_hit_proc, this function handles the Ilesh's proc.
bool ilesh_fury(P_char ch, P_char victim, P_obj wpn)
{
	struct affected_type *afp;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim) || !(wpn) || !EARTH_REAVER_WEAPONS(wpn))
	{
		return FALSE;
	}

	afp = get_spell_from_char(ch, SPELL_ILESHS_SMASHING_FURY);
	if (!afp)
		return FALSE;

	// Chance for upgrading tier of damage.
	if (!ilesh_tier_roll(live_rolls))
	{
		// Modifier holds tier of damage.
		switch (afp->modifier++)
		{
		case 0:
			spell_blindness(GET_LEVEL(ch), ch, NULL, 0, victim, NULL);
			break;
		case 1:
		case 2:
			spell_acid_blast(GET_LEVEL(ch), ch, NULL, 0, victim, NULL);
			break;
		case 3:
			spell_earthen_grasp(GET_LEVEL(ch), ch, NULL, 0, victim, NULL);
			break;
		case 4:
			if (!ilesh_immolate_roll(live_rolls))
				spell_acidimmolate(GET_LEVEL(ch), ch, NULL, 0, victim, NULL);
			else
				spell_acid_stream(GET_LEVEL(ch), ch, NULL, 0, victim, NULL);
			break;
		default:
			act("&+LThe &+ydust&+L flies into your &+reyes&n.", FALSE, ch, 0, victim,
			    TO_VICT);
			blind(ch, victim, ilesh_blindness(live_rolls));
			afp->modifier = 0; // lets not go over max int
			break;
		}
	}
	return FALSE;
}

/*
void event_cegilune_searing(P_char ch, P_char vict, P_obj wpn, void *data)
{
  struct damage_messages messages = {
    "",
    "&+LThe &+rf&+Ri&+rr&+Re&+rs &+Llick at your wound, causing you to scream in pain!&n",
    "",
    "&+L$N &+Lsuddenly begins thrashing around violently. Several chunks of smoldering &+rflesh&+L fall from $S body, and $E topples to the ground, screaming violently--then is suddenly silent!&n",
    "&+LThe &+rf&+Ri&+re&+Rr&+ry &+Lp&+rai&+Ln is too much for you to handle, and you think you hear the incessant cackling of &+md&+Lemoni&+mc &+Llaughter as your vision spins toward oblivion...&n",
    "&+L$N &+Lsuddenly begins thrashing around violently. Several chunks of smoldering &+rflesh&+L fall from$S body, and $E topples to the ground, screaming violently--then is suddenly silent!&n", 0
  };

  if( !IS_ALIVE(ch) || !IS_ALIVE(vict) || !FLAME_REAVER_WEAPONS(wpn) )
  {
    return;
  }

  struct affected_type *afp;
  afp = get_spell_from_char(vict, TAG_CEGILUNE_FIRE);

  if (!afp)
  {
    return;
  }

  if( --(afp->modifier) <= 0 )
  {
    send_to_char("&+RThe flames engulfing your body subside.\n", vict);
    affect_remove(vict, afp);
    return;
  }

  // This correlates to 3 to 12 damage
  if( spell_damage(ch, vict, dice( 12, 4 ), SPLDAM_FIRE, SPLDAM_NODEFLECT, &messages) == DAM_NONEDEAD )
  {
    add_event(event_cegilune_searing, PULSE_VIOLENCE, ch, vict, wpn, 0, 0, 0);
  }
}

*/
static int thryms_icerazor_duration(int level)
{
	return level / 2;
}

static int thryms_icerazor_hitroll(int level)
{
	return 5 + MAX(0, level - 51);
}

static int thryms_icerazor_damage(const Rolls &rolls)
{
	return rolls.number(8, 6);
}

static int thryms_icerazor_coldshield(const Rolls &rolls)
{
	return rolls.number(4, 3);
}

static int thryms_icerazor_fireshield(const Rolls &rolls)
{
	return rolls.number(4, 4);
}

// With coldshield, a roll up to thryms_icerazor_slow_upto() slows the target.
static int thryms_icerazor_slow_roll(const Rolls &rolls)
{
	return rolls.number(1, 100);
}

static int thryms_icerazor_slow_upto()
{
	return 5;
}

static int thryms_icerazor_slow_duration()
{
	return 2;
}

std::string thryms_icerazor_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Hitroll", "+" + std::to_string(thryms_icerazor_hitroll(level)) +
				       " at your level, " + std::to_string(level)) +
	       fact("Duration", game_hours(thryms_icerazor_duration(level))) +
	       fact("Cold damage on each hit", show({ thryms_icerazor_damage(lowest_rolls),
						      thryms_icerazor_damage(highest_rolls) })) +
	       fact("With coldshield", "+" + show({ thryms_icerazor_coldshield(lowest_rolls),
						    thryms_icerazor_coldshield(highest_rolls) })) +
	       fact("With fireshield",
		    "-" + std::to_string(thryms_icerazor_fireshield(lowest_rolls))) +
	       fact("Chance to slow with coldshield",
		    std::to_string(thryms_icerazor_slow_upto()) + "% per hit") +
	       fact("Slow lasts", game_hours(thryms_icerazor_slow_duration())) +
	       "  It deals at least 1 and cannot be shrugged. Constructs are unaffected.\n"
	       "  You need a bludgeon in hand.\n";
}

void spell_thryms_icerazor(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			   P_char victim, P_obj /*obj*/)
{
	named_set_ordinary_cast ordinary_cast(victim, SPELL_THRYMS_ICERAZOR);
	bool weapon = false;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (affected_by_spell(ch, SPELL_THRYMS_ICERAZOR))
	{
		send_to_char("&+CThrym&+L refuses to grant you any more of his powers!&n\n", ch);
		return;
	}

	if (ch->equipment[WIELD] && FROST_REAVER_WEAPONS(ch->equipment[WIELD]))
	{
		weapon = true;
	}

	if (!weapon && ch->equipment[WIELD2] && FROST_REAVER_WEAPONS(ch->equipment[WIELD2]))
	{
		weapon = true;
	}

	if (!weapon)
	{
		send_to_char(
			"&+LThe power of &+CThrym&+L requires you to have a suitable weapon!&n\n",
			ch);
		return;
	}

	struct affected_type af;
	bzero(&af, sizeof(af));

	af.type = SPELL_THRYMS_ICERAZOR;
	af.duration = thryms_icerazor_duration(level);
	af.location = APPLY_HITROLL;
	af.modifier = thryms_icerazor_hitroll(level);

	affect_to_char(victim, &af);

	send_to_char("&+LThe &+CChill &+Lof &+BThrym&+L permeates your weapon.&n\n", ch);
}

bool thryms_icerazor(P_char ch, P_char victim, P_obj wpn)
{
	int dam;
	struct affected_type af;

	struct damage_messages messages = {
		"&+CThe shards of &+Bice&+C surrounding $q &+Csplinter off as they strike $N&+C!&n",
		"&+CThe shards of &+Bice&+C surrounding $n's $q &+Ctear into your flesh!&n",
		"&+CThe chilling &+Bice &+Csurrounding $n's $q &+Cslices into $N&+C's flesh!&n",
		"&+CThe &+Bchilling &+Ccold is too much for $N&+C, and they fall to the ground, the stench of rending flesh filling the air.&n",
		"&+CThe &+Bchilling &+Cice is too much, and you fall to the ground, before everything goes &+Lblack&+C.&n",
		"&+CThe &+Bchilling &+Ccold is too much for $N&+C, and they fall to the ground, the stench of rending flesh filling the air.&n",
		DAMMSG_TERSE
	};

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim) || !(wpn) || !FROST_REAVER_WEAPONS(wpn))
	{
		return false;
	}

	messages.obj = wpn;

	dam = thryms_icerazor_damage(live_rolls);

	if (IS_AFFECTED3(ch, AFF3_COLDSHIELD))
		dam += thryms_icerazor_coldshield(live_rolls);

	if (IS_AFFECTED2(ch, AFF2_FIRESHIELD))
		dam -= thryms_icerazor_fireshield(live_rolls);

	dam = MAX(1, dam);

	if (IS_AFFECTED3(ch, AFF3_COLDSHIELD) &&
	    thryms_icerazor_slow_roll(live_rolls) <= thryms_icerazor_slow_upto())
	{
		// additional slowness messages
		act("&+CThe &+Bchilling&+C ice surrounding $n's &+Cweapon suddenly begin to vibrate as they strike $N!&n",
		    FALSE, ch, 0, victim, TO_ROOM);
		act("&+CThe &+Bchilling&+C ice surrounding your weapon suddenly begins to vibrate as it strikes $N!&n",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("&+CThe &+Bchilling&+C ice surrounding $n's $q &+Csuddenly begins to vibrate as it strikes you!&n",
		    FALSE, ch, 0, victim, TO_VICT);

		// apply slowness
		bzero(&af, sizeof(af));
		af.type = SPELL_SLOW;
		af.duration = thryms_icerazor_slow_duration();
		af.modifier = 2;
		af.bitvector2 = AFF2_SLOW;
		affect_to_char(victim, &af);
	}

	if (spell_damage(ch, victim, dam, SPLDAM_COLD, SPLDAM_NODEFLECT | SPLDAM_NOSHRUG,
			 &messages) != DAM_NONEDEAD)
		return TRUE;

	return FALSE;
}

static int lliendils_stormshock_duration(int level)
{
	return level / 2;
}

static int lliendils_stormshock_pulse(const Rolls &rolls)
{
	return rolls.number(-1, -2);
}

static int lliendils_stormshock_damage(const Rolls &rolls, int level)
{
	return rolls.number(1, level / 4);
}

std::string lliendils_stormshock_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Combat pulse", show_signed({ lliendils_stormshock_pulse(lowest_rolls),
						  lliendils_stormshock_pulse(highest_rolls) })) +
	       fact("Duration",
		    game_hours(lliendils_stormshock_duration(level)) + " at your level") +
	       fact("Lightning on each hit",
		    show_landing({ lliendils_stormshock_damage(lowest_rolls, level),
				   lliendils_stormshock_damage(highest_rolls, level) })) +
	       "  It cannot be shrugged. Constructs are unaffected.\n"
	       "  You need a one-handed sword, axe or dagger in hand.\n";
}

void spell_lliendils_stormshock(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
				P_char victim, P_obj /*obj*/)
{
	struct affected_type af;
	bool weapon = false;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (affected_by_spell(ch, SPELL_LLIENDILS_STORMSHOCK))
	{
		send_to_char("&+LLliendil &+Brefuses to grant you any more of his power!&n\n", ch);
		return;
	}

	if (ch->equipment[WIELD] && SHOCK_REAVER_WEAPONS(ch->equipment[WIELD]))
	{
		weapon = true;
	}

	if (!weapon && ch->equipment[WIELD2] && SHOCK_REAVER_WEAPONS(ch->equipment[WIELD2]))
	{
		weapon = true;
	}

	if (!weapon)
	{
		send_to_char("You need to wield a suitable weapon!\n", ch);
		return;
	}

	bzero(&af, sizeof(af));

	af.type = SPELL_LLIENDILS_STORMSHOCK;
	af.duration = lliendils_stormshock_duration(level);
	af.location = APPLY_COMBAT_PULSE;
	af.modifier = lliendils_stormshock_pulse(live_rolls);

	affect_to_char(victim, &af);

	send_to_char(
		"&+BSparks begin to &+barc&+B and &+Wjump&+B across your weapon&+B, and &+LLliendil&+B infuses your blade with the fury of &+wst&+Lor&+wms&+B!&n\n",
		ch);
}

bool lliendils_stormshock(P_char ch, P_char victim, P_obj wpn)
{
	int dam;

	struct damage_messages messages = {
		"&+BSearing &+Yb&+Colt&+Ys &+Bof &+Lblack &+Blig&+Whtn&+Bing &+Bflow forth from your $q, &+Bstriking $N!&n",
		"&+BSearing &+Yb&+Colt&+Ys &+Bof &+Lblack &+Blig&+Whtn&+Bing &+Bflow forth from $n's $q, &+Bstriking you soundly!&n",
		"&+BSearing &+Yb&+Colt&+Ys &+Bof &+Lblack &+Blig&+Whtn&+Bing &+Bflow forth from $n's $q, &+Bcausing $N to scream in pain!&n",
		"&+BAs the &+Lblack &+Yb&+Colt&+Ys &+Bwrack $N's body, they suddenly fall to the ground, a crackling heap of burnt flesh!&n",
		"&+BThe last thing your senses notice before you leave this mortal coil, is the scent of your own burning flesh.&n",
		"&+BSuddenly, a HUGE &+Lblack &+Yb&+Col&+Yt &+Bleaps forth from $n's $q&+B, and $N&+B falls to the ground, nothing but a twitching mass of burnt flesh!&n",
		DAMMSG_TERSE
	};

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim) || !(wpn) || !SHOCK_REAVER_WEAPONS(wpn))
	{
		return false;
	}

	messages.obj = wpn;

	dam = lliendils_stormshock_damage(live_rolls, GET_LEVEL(ch));

	if (IS_AFFECTED3(ch, AFF3_LIGHTNINGSHIELD) && number(1, 100) <= 5)
	{
		// apply some lightning effect
		act("&+BA HUGE bolt of lightning flares forth from $n's &+Bweapon! ZAAAAP!&n",
		    FALSE, ch, 0, victim, TO_ROOM);
		act("&+BA HUGE bolt of lightning flares forth from your weapon! ZAAAAP!&N", FALSE,
		    ch, 0, victim, TO_CHAR);
	}

	if (spell_damage(ch, victim, dam, SPLDAM_LIGHTNING, SPLDAM_NODEFLECT | SPLDAM_NOSHRUG,
			 &messages) != DAM_NONEDEAD)
	{
		return TRUE;
	}

	return FALSE;
}

static int stormcallers_fury_duration(int level)
{
	return level / 2;
}

// A roll of 0 builds a charge on a repeated target.
static int stormcallers_fury_build_roll(const Rolls &rolls)
{
	return rolls.number(0, 1);
}

// A charge above this roll sets off the flurry.
static int stormcallers_fury_trigger_roll(const Rolls &rolls)
{
	return rolls.number(14, 16);
}

static int stormcallers_fury_hits(const Rolls &rolls)
{
	return rolls.number(3, 6);
}

std::string stormcallers_fury_facts(P_char ch)
{
	const int odds = stormcallers_fury_build_roll(highest_rolls) -
			 stormcallers_fury_build_roll(lowest_rolls) + 1;
	return fact("Duration",
		    game_hours(stormcallers_fury_duration(GET_LEVEL(ch))) + " at your level") +
	       fact("Each hit on the same target builds a charge", "1 in " + std::to_string(odds)) +
	       fact("A flurry comes above",
		    show({ stormcallers_fury_trigger_roll(lowest_rolls),
			   stormcallers_fury_trigger_roll(highest_rolls) }) +
			    " charges") +
	       fact("Extra hits in the flurry", show({ stormcallers_fury_hits(lowest_rolls),
						       stormcallers_fury_hits(highest_rolls) })) +
	       "  A new target resets the charge. Constructs are unaffected.\n"
	       "  You need Lliendil's stormshock up and a one-handed sword, axe or dagger.\n";
}

void spell_stormcallers_fury(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			     P_char victim, P_obj /*obj*/)
{
	struct affected_type af;
	bool weapon = false;

	if (!IS_ALIVE(ch))
	{
		return;
	}

	if (affected_by_spell(ch, SPELL_STORMCALLERS_FURY))
	{
		send_to_char("You already are infuriated!&n\n", ch);
		return;
	}

	if (!affected_by_spell(ch, SPELL_LLIENDILS_STORMSHOCK))
	{
		send_to_char("&+LYou must have the power of Lliendil to cast this spell!\n", ch);
		return;
	}

	if (ch->equipment[WIELD] && SHOCK_REAVER_WEAPONS(ch->equipment[WIELD]))
	{
		weapon = true;
	}

	if (!weapon && ch->equipment[WIELD2] && SHOCK_REAVER_WEAPONS(ch->equipment[WIELD2]))
	{
		weapon = true;
	}

	if (!weapon)
	{
		send_to_char("You need to wield a suitable weapon!\n", ch);
		return;
	}

	bzero(&af, sizeof(af));

	af.type = SPELL_STORMCALLERS_FURY;
	af.duration = stormcallers_fury_duration(level);
	af.modifier = 0;

	affect_to_char(victim, &af);

	send_to_char("&+BThe power of the storm causes your weapon to crackle with energy.\n", ch);
}

bool stormcallers_fury(P_char ch, P_char victim, P_obj wpn)
{
	int pid;
	struct affected_type *afp;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim) || !(wpn) || !SHOCK_REAVER_WEAPONS(wpn))
	{
		return false;
	}

	if (!affected_by_spell(ch, SPELL_LLIENDILS_STORMSHOCK))
	{
		return FALSE;
	}

	afp = get_spell_from_char(ch, SPELL_STORMCALLERS_FURY);

	if (!afp)
	{
		return FALSE;
	}

	/*
	 the current level of chargeup is stored in the spell modifier
	 the targets get TAG_STORMCALLERS_FURY_TARGET counters with the pid of the attacker,
	 so if the reaver attacks a new target without the counter, it will reset the chargeup
	 */

	pid = (IS_PC(ch) ? GET_PID(ch) : GET_RNUM(ch));

	int stormcaller_id = counter(victim, TAG_STORMCALLERS_FURY_TARGET);

	if (stormcaller_id != pid)
	{
		// starting on a new target, reset spell modifier
		afp->modifier = 0;
		remove_counter(victim, TAG_STORMCALLERS_FURY_TARGET, pid);
		add_counter(victim, TAG_STORMCALLERS_FURY_TARGET, pid, 0);
		return FALSE;
	}
	else
	{
		// buildup
		if (!stormcallers_fury_build_roll(live_rolls))
		{
			afp->modifier++;

			if (afp->modifier == 6)
			{
				act("&+BSparks begin to &+Yarc &+Band &+Ljump &+Bacross your weapon&+B.&n",
				    FALSE, ch, wpn, victim, TO_CHAR);
				act("&+BSparks begin to &+Yarc &+Band &+Ljump &+Bacross $n's weapon&+B.&n",
				    FALSE, ch, wpn, victim, TO_VICT);
				act("&+BSparks begin to &+Yarc &+Band &+Ljump &+Bacross $n's weapon&+B.&n",
				    FALSE, ch, wpn, victim, TO_NOTVICT);
			}
			else if (afp->modifier == 12)
			{
				act("&+BThe &+Yelectrical&+B aura around your weapon &+Bintensifies, and begins to &+Wcrackle &+Bloudly!&n",
				    FALSE, ch, wpn, victim, TO_CHAR);
				act("&+BThe &+Yelectrical&+B aura around $n's &+Bweapon &+Bintensifies, and begins to &+Wcrackle &+Bloudly!&n",
				    FALSE, ch, wpn, victim, TO_VICT);
				act("&+BThe &+Yelectrical&+B aura around $n's &+Bweapon &+Bintensifies, and begins to &+Wcrackle &+Bloudly!&n",
				    FALSE, ch, wpn, victim, TO_NOTVICT);
			}
			else if (afp->modifier > stormcallers_fury_trigger_roll(live_rolls))
			{
				afp->modifier = 0;

				act("&+BSuddenly, the &+Yenergy&+B surrounding your weapon &+Bleaps into your body, and empowers you to strike down $N&+B!&n",
				    FALSE, ch, wpn, victim, TO_CHAR);
				act("&+BSuddenly, the &+Yenergy&+B surrounding $n's &+Bweapon &+Bleaps into their body, causing them to strike out in a flurry of movement!&n",
				    FALSE, ch, wpn, victim, TO_VICT);
				act("&+BSuddenly, the &+Yenergy&+B surrounding $n's &+Bweapon &+Bleaps into their body, causing them to strike out in a flurry of movement!&n",
				    FALSE, ch, wpn, victim, TO_NOTVICT);

				int num_hits = stormcallers_fury_hits(live_rolls);

				for (int i = 0; i < num_hits && IS_ALIVE(victim); i++)
					hit(ch, victim, wpn);

				afp->modifier = 0;

				if (!IS_ALIVE(victim))
					return TRUE;
			}
		}

		remove_counter(victim, TAG_STORMCALLERS_FURY_TARGET, pid);
		add_counter(victim, TAG_STORMCALLERS_FURY_TARGET, pid, 0);
		return FALSE;
	}

	return FALSE;
}

static int kostchtchies_implosion_duration(int level)
{
	return level / 2;
}

// A roll of 0 builds a charge on a repeated target.
static int kostchtchies_implosion_build_roll(const Rolls &rolls)
{
	return rolls.number(0, 1);
}

// A charge above this roll sets off the shards.
static int kostchtchies_implosion_trigger_roll(const Rolls &rolls)
{
	return rolls.number(14, 16);
}

static int kostchtchies_implosion_damage(const Rolls &rolls)
{
	return 450 + rolls.dice(10, 10);
}

std::string kostchtchies_implosion_facts(P_char ch)
{
	const int odds = kostchtchies_implosion_build_roll(highest_rolls) -
			 kostchtchies_implosion_build_roll(lowest_rolls) + 1;
	return fact("Duration",
		    game_hours(kostchtchies_implosion_duration(GET_LEVEL(ch))) + " at your level") +
	       fact("Each hit on the same target builds a charge", "1 in " + std::to_string(odds)) +
	       fact("Shards fly above",
		    show({ kostchtchies_implosion_trigger_roll(lowest_rolls),
			   kostchtchies_implosion_trigger_roll(highest_rolls) }) +
			    " charges") +
	       fact("Cold damage", show({ kostchtchies_implosion_damage(lowest_rolls),
					  kostchtchies_implosion_damage(highest_rolls) })) +
	       "  A new target resets the charge. It cannot be shrugged.\n"
	       "  You need Thrym's icerazor up and a bludgeon in hand.\n"
	       "  Constructs are unaffected.\n";
}

void spell_kostchtchies_implosion(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
				  P_char victim, P_obj /*obj*/)
{
	struct affected_type af;
	bool weapon = false;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return;
	}

	if (affected_by_spell(ch, SPELL_CHILLING_IMPLOSION))
	{
		send_to_char("&+CKostchtchie &+Lrefuses to grant you any more power!&n\n", ch);
		return;
	}

	if (!affected_by_spell(ch, SPELL_THRYMS_ICERAZOR))
	{
		send_to_char("&+CYou must have the power of &+LThrym&+C to cast this spell!\n", ch);
		return;
	}

	if (ch->equipment[WIELD] && FROST_REAVER_WEAPONS(ch->equipment[WIELD]))
	{
		weapon = true;
	}

	if (!weapon && ch->equipment[WIELD2] && FROST_REAVER_WEAPONS(ch->equipment[WIELD2]))
	{
		weapon = true;
	}

	if (!weapon)
	{
		send_to_char("You need to wield a suitable weapon!\n", ch);
		return;
	}

	bzero(&af, sizeof(af));

	af.type = SPELL_CHILLING_IMPLOSION;
	af.duration = kostchtchies_implosion_duration(level);
	af.modifier = 0;

	affect_to_char(victim, &af);

	send_to_char("You become implosive with the power of the flair!\n", ch);
}

bool kostchtchies_implosion(P_char ch, P_char victim, P_obj wpn)
{
	int pid;
	struct affected_type *afp;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim) || !(wpn) || !FROST_REAVER_WEAPONS(wpn))
	{
		return false;
	}

	if (!affected_by_spell(ch, SPELL_THRYMS_ICERAZOR))
	{
		return FALSE;
	}

	afp = get_spell_from_char(ch, SPELL_CHILLING_IMPLOSION);

	if (!afp)
	{
		return FALSE;
	}

	/*
	 the current level of chargeup is stored in the spell modifier
	 the targets get TAG_CHILLING_IMPLOSION_TARGET counters with the pid of the attacker,
	 so if the reaver attacks a new target without the counter, it will reset the chargeup
	 */

	pid = (IS_PC(ch) ? GET_PID(ch) : GET_RNUM(ch));

	int imploder_id = counter(victim, TAG_CHILLING_IMPLOSION_TARGET);

	if (imploder_id != pid)
	{
		// starting on a new target, reset spell modifier
		afp->modifier = 0;
		remove_counter(victim, TAG_CHILLING_IMPLOSION_TARGET, pid);
		add_counter(victim, TAG_CHILLING_IMPLOSION_TARGET, pid, 0);
		return FALSE;
	}
	else
	{
		// buildup
		if (!kostchtchies_implosion_build_roll(live_rolls))
		{
			afp->modifier++;

			if (afp->modifier == 6)
			{
				act("&+CThe &+Bchilling &+Cice begins to gather upon your weapon&+C.&n",
				    FALSE, ch, wpn, victim, TO_CHAR);
				act("&+CThe &+Bchilling &+Cice begins to gather upon $n's weapon&+C.&n",
				    FALSE, ch, wpn, victim, TO_VICT);
				act("&+CThe &+Bchilling &+Cice begins to gather upon $n's weapon&+C.&n",
				    FALSE, ch, wpn, victim, TO_NOTVICT);
			}
			else if (afp->modifier == 12)
			{
				act("&+CThe &+Bice &+Cbegins to become heavy on your weapon&+C, and your determination grows!&n",
				    FALSE, ch, wpn, victim, TO_CHAR);
				act("&+CThe &+Bice &+Cbegins to become heavy on $n's weapon&+C, and their determination fiercely intensifies!&n",
				    FALSE, ch, wpn, victim, TO_VICT);
				act("&+CThe &+Bice &+Cbegins to become heavy on $n's weapon&+C, and their determination fiercely intensifies!&n",
				    FALSE, ch, wpn, victim, TO_NOTVICT);
			}
			else if (afp->modifier > kostchtchies_implosion_trigger_roll(live_rolls))
			{
				afp->modifier = 0;
				struct damage_messages messages = {
					"&+CSuddenly, a the &+Lshards &+Cof &+Bice &+Cfly forth from your weapon&+C, slicing into $N's &+Cflesh!&n",
					"&+CSuddenly, a the &+Lshards &+Cof &+Bice &+Cfly forth from $n's weapon&+C, slicing into your &+Cflesh!&n ",
					"&+CSuddenly, a the &+Lshards &+Cof &+Bice &+Cfly forth from $n's weapon&+C, slicing into $N's &+Cflesh!&n ",
					"&+CThe &+Lshards &+Cof &+Bice &+Ccut deep into $N&+C, leaving only a pile of rending flesh!&n",
					"&+CThe &+Lshards &+Cof &+Bice &+Care too much for you to handle, and you fall to the ground, the pain finally subsiding.",
					"&+CThe &+Lshards &+Cof &+Bice &+Ccut deep into $N&+C, leaving only a pile of rending flesh!&n",
					DAMMSG_TERSE
				};

				int dam = kostchtchies_implosion_damage(live_rolls);

				if (spell_damage(ch, victim, dam, SPLDAM_COLD,
						 SPLDAM_NODEFLECT | SPLDAM_NOSHRUG,
						 &messages) != DAM_NONEDEAD)
					return TRUE;
			}
		}

		remove_counter(victim, TAG_CHILLING_IMPLOSION_TARGET, pid);
		add_counter(victim, TAG_CHILLING_IMPLOSION_TARGET, pid, 0);
		return FALSE;
	}

	return FALSE;
}

/*
 called in hit() if the ch is a reaver.
 put all the checks for the reaver spells here
 */

bool reaver_hit_proc(P_char ch, P_char victim, P_obj weapon)
{
	if (GET_RACE(victim) == RACE_CONSTRUCT)
		return FALSE;

	if (affected_by_spell(ch, SPELL_STORMCALLERS_FURY) && stormcallers_fury(ch, victim, weapon))
		return TRUE;

	if (affected_by_spell(ch, SPELL_CHILLING_IMPLOSION) &&
	    kostchtchies_implosion(ch, victim, weapon))
		return TRUE;

	if (is_linked_to(ch, weapon, LNK_CEGILUNE) && cegilune_blade(ch, victim, weapon))
		return TRUE;

	if (is_linked_to(ch, weapon, LNK_ILESH) && ilesh_fury(ch, victim, weapon))
		return TRUE;

	if (affected_by_spell(ch, SPELL_ILIENZES_FLAME_SWORD) && ilienze_sword(ch, victim, weapon))
		return TRUE;

	if (affected_by_spell(ch, SPELL_THRYMS_ICERAZOR) && thryms_icerazor(ch, victim, weapon))
		return TRUE;

	if (affected_by_spell(ch, SPELL_LLIENDILS_STORMSHOCK) &&
	    lliendils_stormshock(ch, victim, weapon))
		return TRUE;

	if (affected_by_spell(ch, SPELL_GIRILALS_GRANITE_HAMMER) &&
	    girilals_granite_hammer(ch, victim, weapon))
		return TRUE;

	return FALSE;
}

// What each weapon adds to a reaver's combat round, in pulses.
float ice_reaver_1h_bludgeon_penalty()
{
	return get_property("reavers.ice.penalty.pulse.1hBludgeon", 2.);
}

float ice_reaver_2h_bludgeon_penalty()
{
	return get_property("reavers.ice.penalty.pulse.2hBludgeon", 3.);
}

float flame_reaver_2h_penalty()
{
	return get_property("reavers.flame.penalty.pulse.2hSlashing", 3.);
}

/*
 called from affect_total() in affects.c
 set all standard mods for reavers based on weapons, skills, etc
 */
void apply_reaver_mods(P_char ch)
{
	if (!ch)
		return;

	P_obj w1 = ch->equipment[WIELD];
	P_obj w2 = ch->equipment[WIELD2];

	if (GET_SPEC(ch, CLASS_REAVER, SPEC_ICE_REAVER))
	{
		if ((w1 && required_weapon_skill(w1) == SKILL_1H_BLUDGEON) ||
		    (w2 && required_weapon_skill(w2) == SKILL_1H_BLUDGEON))
		{
			ch->specials.base_combat_round += ice_reaver_1h_bludgeon_penalty();
		}
		else if ((w1 && required_weapon_skill(w1) == SKILL_2H_BLUDGEON) ||
			 (w2 && required_weapon_skill(w2) == SKILL_2H_BLUDGEON))
		{
			ch->specials.base_combat_round += ice_reaver_2h_bludgeon_penalty();
		}
	}
	else if (GET_SPEC(ch, CLASS_REAVER, SPEC_FLAME_REAVER))
	{
		if (required_weapon_skill(w1) == SKILL_2H_SLASHING ||
		    required_weapon_skill(w2) == SKILL_2H_SLASHING ||
		    required_weapon_skill(w1) == SKILL_2H_FLAYING ||
		    required_weapon_skill(w2) == SKILL_2H_FLAYING)
		{
			ch->specials.base_combat_round += flame_reaver_2h_penalty();
		}
	}
	/* Shock reavers currently have no two handed weapon skills. Apr09 -Lucrot
	  else if( GET_SPEC(ch, CLASS_REAVER, SPEC_SHOCK_REAVER) )
	  {
	    if( required_weapon_skill(w1) == SKILL_2H_SLASHING ||
	        required_weapon_skill(w2) == SKILL_2H_SLASHING )
	    {
	      ch->specials.base_combat_round += get_property("reavers.shock.penalty.pulse.2hSlashing", 3.);
	    }
	  } */
}
