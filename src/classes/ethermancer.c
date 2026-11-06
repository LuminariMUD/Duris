/****************************************************************************
 *
 *  File: ethermancer.c                                         Part of Duris
 *  Usage: ethermancer spells: wind blade, frost bolt, tempest, and more
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "abilities/abilities.h"
#include "core/prototypes.h"
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "core/utils.h"
#include <stdio.h>
#include <string.h>
#include "combat/ctf.h"
#include "combat/damage.h"
#include "classes/disguise.h"
#include "world/graph.h"
#include "combat/justice.h"
#include "world/map.h"
#include "world/specs.prototypes.h"
#include "magic/spells.h"
#include "item/item_movement_transaction.h"
#include "world/vnum.obj.h"
#include "world/weather.h"

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
extern Skill skills[];

extern const char *get_function_name(void *);
extern bool has_skin_spell(P_char);
extern bool exit_wallable(int room, int dir, P_char ch);
extern bool create_walls(int room, int exit, P_char ch, int level, int type, int power, int decay,
			 const char *short_desc, const char *desc, ulong flags);

#define WIND_BLADE 98

int cast_as_damage_area(P_char, void (*func)(int, P_char, char *, int, P_char, P_obj), int, P_char,
			float, float);
int cast_as_damage_area(P_char, void (*func)(int, P_char, char *, int, P_char, P_obj), int, P_char,
			float, float, bool (*s_func)(P_char, P_char));

// Vapor armor lasts at least 10 ticks and improves armor class with the cast level.
static int vapor_armor_duration(int level)
{
	return MAX(10, (int)(level / 2));
}

static int vapor_armor_ac(int level)
{
	return (int)(-1 * level * 1.25);
}

std::string vapor_armor_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Duration", game_hours(vapor_armor_duration(level)) + " at your level, " +
					std::to_string(level)) +
	       fact("Armor class", std::to_string(vapor_armor_ac(level))) +
	       "  Recasting it only renews the duration.\n"
	       "  It does nothing to a target with another armor-type spell.\n";
}

void spell_vapor_armor(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
		       P_char victim, P_obj /*tar_obj*/)
{
	struct affected_type af;
	bool shown;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return;
	}

	if (!IS_AFFECTED(victim, AFF_ARMOR))
	{
		memset(&af, 0, sizeof(af));

		af.type = SPELL_VAPOR_ARMOR;
		af.duration = vapor_armor_duration(level);
		af.modifier = vapor_armor_ac(level);
		af.bitvector = AFF_ARMOR;
		af.location = APPLY_AC;

		affect_to_char(victim, &af);

		send_to_char(
			"&+CYou feel the protection of the winds and storms flow through you.&n\r\n",
			victim);
	}
	else
	{
		struct affected_type *af1;
		shown = FALSE;
		for (af1 = victim->affected; af1; af1 = af1->next)
		{
			if (af1->type == SPELL_VAPOR_ARMOR)
			{
				af1->duration = vapor_armor_duration(level);
				if (!shown)
				{
					send_to_char("&+cYour vaporous armor is renewed!\r\n",
						     victim);
					shown = TRUE;
				}
			}
		}
		if (!shown)
		{
			send_to_char("&+WYou're already affected by an armor-type spell.\n",
				     victim);
		}
	}
}

// A damage factor from dam_factor as a page shows it, such as 15% less.
static std::string damage_change(double factor)
{
	const double percent = (factor - 1.0) * 100.0;
	char text[32];
	snprintf(text, sizeof(text), "%g%% %s", percent < 0 ? -percent : percent,
		 percent < 0 ? "less" : "more");
	return text;
}

// Frost beam damage reads the caster's own level.
static int frost_beam_damage(const Rolls &rolls, P_char ch)
{
	return GET_LEVEL(ch) * 14 + rolls.number(10, 20);
}

// Outside the frost magus spec, a roll below the chance cannot be shrugged.
static int frost_beam_noshrug_roll(const Rolls &rolls)
{
	return rolls.number(0, 99);
}

static int frost_beam_noshrug_chance()
{
	return 50;
}

// The paralysis lasts this many pulses.
static int frost_beam_paralysis(int level)
{
	return (int)(level * WAIT_SEC * 0.75);
}

std::string frost_beam_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const int outcomes =
		frost_beam_noshrug_roll(highest_rolls) - frost_beam_noshrug_roll(lowest_rolls) + 1;
	return fact("Cold damage", show({ frost_beam_damage(lowest_rolls, ch),
					  frost_beam_damage(highest_rolls, ch) }) +
					   " at your level, " + std::to_string(level)) +
	       fact("Cannot be shrugged", GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_FROSTMAGUS) ?
						  "always, as a frost magus" :
						  std::to_string(frost_beam_noshrug_chance()) +
							  " in " + std::to_string(outcomes)) +
	       fact("Minor paralysis", seconds(frost_beam_paralysis(level)) +
					       " if the target lives and fails a paralysis save") +
	       "  Globes and spirit wards do not stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_frost_beam(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
		      P_char victim, P_obj /*obj*/)
{
	struct affected_type af;
	if (!ch)
	{
		logit(LOG_EXIT, "spell_frost_beam called in magic.c with no ch");
		return;
	}

	if (!victim)
	{
		return;
	}

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return;
	}

	act("Your &+BF&+br&+Bo&+bs&+Bt&n beam strikes $N leaving them shaken!", TRUE, ch, 0, victim,
	    TO_CHAR);
	act("A &+GBeam&n of &+BF&+Br&+Bo&+bs&+BT&n streams from $n's hands, hitting you sqaure in the torso",
	    FALSE, ch, 0, victim, TO_VICT);
	act("A &+GBeam&n of &+BF&+Br&+Bo&+bs&+BT&n streams from $n's hands, striking $N square in the torso!",
	    FALSE, ch, 0, victim, TO_NOTVICT);

	// if (ch && victim)
	//	engage(ch, victim);

	int dam = frost_beam_damage(live_rolls, ch);

	if (GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_FROSTMAGUS))
		spell_damage(ch, victim, dam, SPLDAM_COLD, SPLDAM_NOSHRUG, NULL);
	else
	{
		if (frost_beam_noshrug_roll(live_rolls) <
		    frost_beam_noshrug_chance()) // 50% chance to be !shrug.
			spell_damage(ch, victim, dam, SPLDAM_COLD, SPLDAM_NOSHRUG, NULL);
		else
			spell_damage(ch, victim, dam, SPLDAM_COLD, 0, NULL);
	}

	// Damage can extract either participant before the paralysis check.
	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return;
	}

	if (!NewSaves(victim, SAVING_PARA, 0))
	{
		bzero(&af, sizeof(af));
		af.type = SPELL_MINOR_PARALYSIS;
		af.flags = AFFTYPE_SHORT;
		af.duration = frost_beam_paralysis(level);
		af.bitvector2 = AFF2_MINOR_PARALYSIS;
		affect_to_char(victim, &af);

		act("$n &+Wturns pale as &+bice&N spreads across $s body, causing all motion to halt.",
		    FALSE, victim, 0, 0, TO_ROOM);
		send_to_char("&+LYour body becomes like stone as is is encased by &+bice&n.\n",
			     victim);

		if (IS_FIGHTING(victim))
			stop_fighting(victim);
		StopMercifulAttackers(victim);
	}
}

static int faerie_sight_duration(int level)
{
	return level / 2;
}

// From this level the caster's faerie sight also detects invisibility.
static bool faerie_sight_detects_invisible(P_char ch)
{
	return GET_LEVEL(ch) >= 36;
}

std::string faerie_sight_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Duration", game_hours(faerie_sight_duration(level)) + " at your level, " +
					std::to_string(level)) +
	       fact("Detect invisibility", faerie_sight_detects_invisible(ch) ?
						   "yes, at your level" :
						   "not at your level") +
	       "  Carrying faerie dust uses one to add detect magic, good and evil.\n"
	       "  Recasting tops up a shorter duration; detect magic costs a dust.\n";
}

void spell_faerie_sight(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			P_char victim, P_obj /*tar_obj*/)
{
	struct affected_type af;
	P_obj t_obj;
	bool refreshed;
	struct affected_type *pAff;

	if (!(victim && ch))
	{
		logit(LOG_EXIT, "spell_faerie_sight: bogus params.");
		return;
	}

	if (affected_by_spell(victim, SPELL_FAERIE_SIGHT))
	{
		refreshed = FALSE;

		for (pAff = victim->affected; pAff; pAff = pAff->next)
		{
			if ((pAff->type == SPELL_FAERIE_SIGHT) &&
			    (pAff->duration < faerie_sight_duration(level)))
			{
				// Takes a faerie dust to refresh the detect magic/good/evil.
				if (!IS_SET(pAff->bitvector2, AFF2_DETECT_MAGIC) ||
				    (vnum_in_inv(ch, VOBJ_FORAGE_FAERIE_DUST) > 0))
				{
					if (IS_SET(pAff->bitvector2, AFF2_DETECT_MAGIC))
					{
						vnum_from_inv(ch, VOBJ_FORAGE_FAERIE_DUST, 1);
					}
					pAff->duration = faerie_sight_duration(level);
					refreshed = TRUE;
				}
			}
		}

		if (!IS_AFFECTED2(victim, AFF2_DETECT_MAGIC) &&
		    (vnum_in_inv(ch, VOBJ_FORAGE_FAERIE_DUST) > 0))
		{
			vnum_from_inv(ch, VOBJ_FORAGE_FAERIE_DUST, 1);
			memset(&af, 0, sizeof(af));
			af.type = SPELL_FAERIE_SIGHT;
			af.duration = faerie_sight_duration(level);
			af.bitvector2 = AFF2_DETECT_MAGIC | AFF2_DETECT_GOOD | AFF2_DETECT_EVIL;
			affect_to_char(victim, &af);
			send_to_char("&+mYour eyes begin to twinkle even &+Mmore&+m.&n\r\n",
				     victim);
			refreshed = TRUE;
		}
		if (!refreshed)
		{
			send_to_char("Nothing happens.\n", victim);
		}
		else
		{
			send_to_char("Your eyes feel &+mwonderful&n.\n", victim);
		}
		return;
	}

	memset(&af, 0, sizeof(af));
	af.type = SPELL_FAERIE_SIGHT;
	af.duration = faerie_sight_duration(level);
	af.bitvector = AFF_FARSEE;

	affect_to_char(victim, &af);

	if (faerie_sight_detects_invisible(ch))
	{
		af.bitvector = af.bitvector | AFF_DETECT_INVISIBLE;
		af.bitvector2 = 0;
	}

	/* Changed this to the below, can change it back if 2 dusts do anything.
	  for (count = 0, t_obj = ch->carrying; t_obj; t_obj = next_obj)
	  {
	    next_obj = t_obj->next_content;

	    if (obj_index[t_obj->R_num].virtual_number == VOBJ_FORAGE_FAERIE_DUST)
	    {
	      used_obj[count] = t_obj;
	      count++;
	    }
	  }

	  if( GET_LEVEL(ch) >= 50 || count > 0 )
	  {
	    af.bitvector2 = AFF2_DETECT_MAGIC | AFF2_DETECT_GOOD | AFF2_DETECT_EVIL;

	    if( count > 0 )
	       extract_obj(used_obj[0]);
	  }
	*/
	for (t_obj = ch->carrying; t_obj; t_obj = t_obj->next_content)
	{
		if (OBJ_VNUM(t_obj) == VOBJ_FORAGE_FAERIE_DUST)
		{
			af.bitvector2 = AFF2_DETECT_MAGIC | AFF2_DETECT_GOOD | AFF2_DETECT_EVIL;
			extract_obj(t_obj);
			break;
		}
	}

	affect_to_char(victim, &af);
	send_to_char("&+mYour eyes begin to twinkle.&n\r\n", ch);
}

// The target's armor class worsens by this much and the caster's improves by it.
static int cold_snap_amount(const Rolls &rolls)
{
	return rolls.dice(10, 5);
}

static int cold_snap_caster_ac(int num)
{
	return num * -1;
}

static int cold_snap_duration()
{
	return 10;
}

// A roll below the chance also casts slow on the target.
static int cold_snap_slow_roll(const Rolls &rolls)
{
	return rolls.number(0, 100);
}

static int cold_snap_slow_chance()
{
	return 10;
}

std::string cold_snap_facts(P_char /*ch*/)
{
	const int low = cold_snap_amount(lowest_rolls), high = cold_snap_amount(highest_rolls);
	const int outcomes =
		cold_snap_slow_roll(highest_rolls) - cold_snap_slow_roll(lowest_rolls) + 1;
	return fact("Target's armor class", show({ low, high }) + " worse") +
	       fact("Your armor class",
		    show_signed({ cold_snap_caster_ac(high), cold_snap_caster_ac(low) }) +
			    ", unless you already have it") +
	       fact("Duration", game_hours(cold_snap_duration())) +
	       fact("Chance to also cast slow",
		    std::to_string(cold_snap_slow_chance()) + " in " + std::to_string(outcomes)) +
	       "  It does nothing to a target that already has it.\n";
}

void spell_cold_snap(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type, P_char victim,
		     P_obj tar_obj)
{
	int num;
	struct affected_type af, af2;

	memset(&af, 0, sizeof(af));
	memset(&af2, 0, sizeof(af2));

	if (!(victim && ch))
	{
		logit(LOG_EXIT, "assert: bogus params");
		return;
	}

	if (affected_by_spell(victim, SPELL_COLD_SNAP))
	{
		send_to_char("They are already affected!\r\n", ch);
		return;
	}

	num = cold_snap_amount(live_rolls);

	af.type = SPELL_COLD_SNAP;
	af.duration = cold_snap_duration();
	af.modifier = num;
	af.location = APPLY_AC;

	af2.type = SPELL_COLD_SNAP;
	af2.duration = cold_snap_duration();
	af2.modifier = cold_snap_caster_ac(num);
	af2.location = APPLY_AC;

	affect_to_char(victim, &af);

	if (!affected_by_spell(ch, SPELL_COLD_SNAP))
		affect_to_char(ch, &af2);

	act("&+CYou unleash a blast of &+Wfreezing wind&n&+C at $N&+C, encasing $M in a layer of frost.",
	    TRUE, ch, 0, victim, TO_CHAR);

	act("&+CYou suddenly feel incredibly stiff from the &+Wblast&n&+C of cold unleashed by $n.&n",
	    TRUE, ch, 0, victim, TO_VICT);

	act("&+C$n &+Cunleashes a blast of &+Wfreezing wind&n&+C at $N&+C, encasing $M in a layer of frost.",
	    TRUE, ch, 0, victim, TO_NOTVICT);

	if (cold_snap_slow_roll(live_rolls) < cold_snap_slow_chance())
		spell_slow(level, ch, 0, 0, victim, tar_obj);
}

void spell_path_of_frost(int /*level*/, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			 P_char /*victim*/, P_obj /*tar_obj*/)
{
	struct affected_type af;

	if (affected_by_spell(ch, SPELL_PATH_OF_FROST))
	{
		send_to_char("You are frosty enough as it is..\r\n", ch);
		return;
	}

	send_to_char("Your body emanates with a &+Cfrosty&n glow.\r\n", ch);

	memset(&af, 0, sizeof(af));
	af.type = SPELL_PATH_OF_FROST;
	af.flags = AFFTYPE_SHORT;
	af.duration = 980;
	affect_to_char(ch, &af);
}

std::string mass_fly_facts(P_char ch)
{
	return "  Casts fly on each group member in the room at your level.\n"
	       "  It does nothing outside a group.\n" +
	       fly_facts(ch);
}

void spell_mass_fly(int level, P_char ch, char * /*arg*/, int /*type*/, P_char /*victim*/,
		    P_obj /*tar_obj*/)
{
	struct group_list *gl;

	if (ch && ch->group)
	{
		gl = ch->group;

		/* leader first */
		if (gl->ch->in_room == ch->in_room)
			spell_fly(level, ch, 0, SPELL_TYPE_SPELL, gl->ch, 0);

		/* followers */
		for (gl = gl->next; gl; gl = gl->next)
		{
			if (gl->ch->in_room == ch->in_room)
				spell_fly(level, ch, 0, SPELL_TYPE_SPELL, gl->ch, 0);
		}
	}
}

// Attacks from casting wind blade in combat while wielding it, and their hitroll bonus.
static int wind_blade_attacks(const Rolls &rolls, P_char ch)
{
	return BOUNDED(2, rolls.number(1, GET_LEVEL(ch) / 10), 4);
}

static int wind_blade_hitroll(const Rolls &rolls)
{
	return rolls.number(5, 15);
}

// The blade's powers at its creator's level.
static bool wind_blade_procs_ice_missile(P_char ch)
{
	return GET_LEVEL(ch) >= 21;
}

static bool wind_blade_protects_from_cold(P_char ch)
{
	return GET_LEVEL(ch) >= 26;
}

static bool wind_blade_gives_coldshield(P_char ch)
{
	return GET_LEVEL(ch) >= 31;
}

static bool wind_blade_procs_cone_of_cold(P_char ch)
{
	return GET_LEVEL(ch) >= 36;
}

static bool wind_blade_procs_frostbite(P_char ch)
{
	return GET_LEVEL(ch) >= 41;
}

static bool wind_blade_procs_iceball(P_char ch)
{
	return GET_LEVEL(ch) >= 51;
}

static bool wind_blade_gives_air_aura(P_char ch)
{
	return GET_LEVEL(ch) >= 56;
}

// value[7]: weapon_proc rolls number(0, this - 1) on each hit and casts on a 0.
static int wind_blade_proc_chance()
{
	return 40;
}

std::string wind_blade_facts(P_char ch)
{
	std::string text = fact("Extra attacks if cast in combat with it wielded",
				show({ wind_blade_attacks(lowest_rolls, ch),
				       wind_blade_attacks(highest_rolls, ch) })) +
			   fact("Hitroll during those attacks",
				"+" + std::to_string(wind_blade_hitroll(lowest_rolls)) + " to +" +
					std::to_string(wind_blade_hitroll(highest_rolls)));
	const char *proc = wind_blade_procs_iceball(ch)	     ? "shattering iceball" :
			   wind_blade_procs_frostbite(ch)    ? "frostbite" :
			   wind_blade_procs_cone_of_cold(ch) ? "cone of cold" :
			   wind_blade_procs_ice_missile(ch)  ? "ice missile" :
							       nullptr;
	if (proc)
		text += fact("Blade's spell", std::string(proc) + " at your level, 1 in " +
						      std::to_string(wind_blade_proc_chance()) +
						      " hits");
	extern float dam_factor[LAST_DF + 1];
	if (wind_blade_gives_coldshield(ch))
		text += fact("Cold shield while wielded",
			     damage_change(dam_factor[DF_ELSHIELDRED]) + " cold spell damage");
	else if (wind_blade_protects_from_cold(ch))
		text += fact("Cold protection while wielded",
			     damage_change(dam_factor[DF_PROTECTION]) + " cold spell damage");
	if (wind_blade_gives_air_aura(ch))
		text += "  Wielding it gives you an air aura.\n";
	return text;
}

void wind_blade_attack_routine(P_char ch, P_char victim)
{
	int attacks = wind_blade_attacks(live_rolls, ch);

	P_obj obj = ch->equipment[PRIMARY_WEAPON];

	if (!obj)
	{
		wizlog(MINLVLIMMORTAL, "Screw up in wind blade attack routine for %s",
		       GET_NAME(ch));
		return;
	}

	act("&+CWinds gather in the area to guide your weapon against $N!", TRUE, ch, 0, victim,
	    TO_CHAR);
	act("&+cWinds gather around $n &n&+cto guide $s &n&+cweapon in combat!", TRUE, ch, 0,
	    victim, TO_ROOM);

	struct affected_type af;
	bzero(&af, sizeof(af));

	af.type = SPELL_WIND_BLADE;
	af.flags = AFFTYPE_SHORT;
	af.duration = 1;
	af.modifier = wind_blade_hitroll(live_rolls);
	af.location = APPLY_HITROLL;

	affect_to_char(ch, &af);

	affect_total(ch, FALSE);

	for (; attacks; attacks--)
	{
		if (IS_ALIVE(victim) && IS_ALIVE(ch))
		{
			hit(ch, victim, obj);
		}
	}

	if (IS_ALIVE(ch) && affected_by_spell(ch, SPELL_WIND_BLADE))
		affect_from_char(ch, SPELL_WIND_BLADE);
}

bool has_wind_blade_wielded(P_char ch)
{
	P_obj obj = ch->equipment[PRIMARY_WEAPON];

	int blade_vnum = WIND_BLADE;

	if (!obj)
		return FALSE;

	if (obj->R_num == real_object(blade_vnum))
		return TRUE;
	else
		return FALSE;
}

bool has_wind_blade(P_char ch)
{
	P_obj obj, next_obj;

	int blade_vnum = WIND_BLADE;

	if (has_wind_blade_wielded(ch))
		return TRUE;

	for (obj = ch->carrying; obj; obj = next_obj)
	{
		next_obj = obj->next_content;

		if (obj_index[obj->R_num].virtual_number == blade_vnum)
		{
			return TRUE;
		}
	}
	return FALSE;
}

struct wind_blade_grant_context
{
	uint64_t item_uid;
};

static P_obj find_carried_object_by_uid(P_char ch, uint64_t item_uid)
{
	if (!ch || !item_uid)
		return NULL;
	for (P_obj object = ch->carrying; object; object = object->next_content)
		if (object->obj_uid == item_uid)
			return object;
	return NULL;
}

static void wind_blade_grant_completed(P_char actor, bool committed,
				       const item_transfer_result &result,
				       unsigned int /*error_code*/, const uint8_t *encoded,
				       size_t encoded_size)
{
	if (!actor || !encoded || encoded_size != sizeof(wind_blade_grant_context))
		return;

	wind_blade_grant_context context = {};
	memcpy(&context, encoded, sizeof(context));
	if (!committed)
	{
		send_to_char("The winds could not deliver the blade; nothing was equipped. "
			     "Please try again later.\r\n",
			     actor);
		return;
	}
	if (result.root_item_uid != context.item_uid)
	{
		logit(LOG_FILE,
		      "wind blade grant result identity mismatch (expected_uid=%llu result_uid=%llu pid=%d)",
		      (unsigned long long)context.item_uid,
		      (unsigned long long)result.root_item_uid, GET_PID(actor));
		send_to_char("The ownership authority returned an unexpected blade; nothing was "
			     "equipped.\r\n",
			     actor);
		return;
	}

	P_obj blade = find_carried_object_by_uid(actor, context.item_uid);
	if (!blade || blade->R_num != real_object(WIND_BLADE))
	{
		logit(LOG_FILE,
		      "wind blade grant committed without the expected live blade (uid=%llu rnum=%d pid=%d)",
		      (unsigned long long)context.item_uid, blade ? blade->R_num : -1,
		      GET_PID(actor));
		send_to_char("The ownership authority delivered the blade, but it is not "
			     "available to wield yet.\r\n",
			     actor);
		return;
	}

	act("&+cSwirling air solidifies into a slender sword.&n.", TRUE, actor, blade, 0, TO_ROOM);
	act("&+cSwirling air solidifies into a slender sword.&n", TRUE, actor, blade, 0, TO_CHAR);
	if (actor->equipment[PRIMARY_WEAPON])
	{
		send_to_char("You are now wielding another weapon, so the wind blade remains "
			     "in your inventory.\r\n",
			     actor);
		return;
	}
	if (!wear(actor, blade, 12, TRUE))
		return;

	if (IS_FIGHTING(actor) && has_wind_blade_wielded(actor))
	{
		if (P_char victim = GET_OPPONENT(actor))
			wind_blade_attack_routine(actor, victim);
	}
}

void grant_wind_blade(P_char ch)
{
	P_obj blade;

	int blade_vnum = WIND_BLADE;

	blade = read_object(real_object(blade_vnum), REAL);

	if (!blade)
	{
		logit(LOG_DEBUG, "spell_wind_blade(): obj 98 not loadable");
		return;
	}
	blade->extra_flags |= ITEM_NORENT;
	blade->bitvector = 0;
	/* how about some gay de procs for wind blade? Yeah baby! */
	if (wind_blade_procs_ice_missile(ch))
	{
		blade->value[5] = 191;
		blade->value[6] = GET_LEVEL(ch);
		blade->value[7] = wind_blade_proc_chance(); // procs ice missile
	}
	if (wind_blade_protects_from_cold(ch))
	{
		SET_BIT(blade->bitvector2, AFF2_PROT_COLD);
	}
	if (wind_blade_gives_coldshield(ch))
	{
		SET_BIT(blade->bitvector3, AFF3_COLDSHIELD);
	}
	if (wind_blade_procs_cone_of_cold(ch))
	{
		blade->value[5] = 10;
		blade->value[6] = GET_LEVEL(ch);
		blade->value[7] = wind_blade_proc_chance(); // procs cone of cold
	}
	if (wind_blade_procs_frostbite(ch))
	{
		blade->value[5] = 325;
		blade->value[6] = GET_LEVEL(ch);
		blade->value[7] = wind_blade_proc_chance(); // procs frostbite
	}
	if (wind_blade_procs_iceball(ch))
	{
		blade->value[5] = 254;
		blade->value[6] = GET_LEVEL(ch);
		blade->value[7] = wind_blade_proc_chance(); // procs iceball
	}
	if (wind_blade_gives_air_aura(ch))
	{
		SET_BIT(blade->bitvector2, AFF2_AIR_AURA);
	}
	blade->timer[0] = 180;

	const wind_blade_grant_context context = { blade->obj_uid };
	if (!item_creation_grant_submit_to_player_with_completion(
		    ch, blade, ch, wind_blade_grant_completed, &context, sizeof(context)))
	{
		extract_obj(blade, FALSE);
		send_to_char("The winds could not create the blade right now. Please try "
			     "again later.\r\n",
			     ch);
	}
}

void spell_wind_blade(int /*level*/, P_char ch, char * /*arg*/, int /*type*/, P_char /*victim*/,
		      P_obj /*tar_obj*/)
{
	P_obj obj, next_obj;

	if (!has_wind_blade(ch))
	{
		if (item_movement_transaction_player_busy(ch))
		{
			send_to_char(
				"The winds are still resolving another item movement. Please wait "
				"a moment.\r\n",
				ch);
			return;
		}
		grant_wind_blade(ch);
		return;
	}
	else
	{
		if (!IS_FIGHTING(ch))
			send_to_char("&+cThe winds are already aiding you!\r\n", ch);
		if (!has_wind_blade_wielded(ch) && !ch->equipment[PRIMARY_WEAPON])
		{
			for (obj = ch->carrying; obj; obj = next_obj)
			{
				next_obj = obj->next_content;
				if (obj_index[obj->R_num].virtual_number == WIND_BLADE)
				{
					wear(ch, obj, 12, TRUE);
				}
			}
		}
	}

	if (IS_FIGHTING(ch))
	{
		if (has_wind_blade_wielded(ch))
		{
			if (P_char vict = GET_OPPONENT(ch))
				wind_blade_attack_routine(ch, vict);
		}
		else
			send_to_char(
				"You need to wield the gift of the air if you want to receive even greater aid!\r\n",
				ch);
	}
}

static int windwalk_pc_lag()
{
	return 36;
}

static int windwalk_npc_lag()
{
	return 5;
}

// A roll of 0 hides the caster's leaving or arrival from one onlooker.
static int windwalk_unseen_roll(const Rolls &rolls)
{
	return rolls.number(0, 5);
}

// Windwalk reaches this many rooms, more for a tempest magus.
static int windwalk_distance(int level, P_char ch)
{
	int distance = (int)(level * get_property("spell.dim.perlevel.modifier", 1.35));
	if (GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_TEMPESTMAGUS))
		distance += 15;
	return distance;
}

std::string windwalk_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Range", std::to_string(windwalk_distance(level, ch)) +
				     " rooms by exits, either way, at your level, " +
				     std::to_string(level)) +
	       fact("Your lag", seconds(IS_PC(ch) ? windwalk_pc_lag() : windwalk_npc_lag()) +
					", even if it fails") +
	       fact("Chance each onlooker misses you going or coming",
		    "1 in " + std::to_string(windwalk_unseen_roll(highest_rolls) -
					     windwalk_unseen_roll(lowest_rolls) + 1)) +
	       "  Non-detection, and no-locate players you do not know, hide a target.\n"
	       "  So does a mount with a rider. A follower cannot reach a player.\n" +
	       "  No-teleport rooms, ocean, castles and the other racewar side block it.\n"
	       "  You, and a player target, must be raidable.\n";
}

void spell_windwalk(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
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

	if (IS_PC(ch))
		CharWait(ch, windwalk_pc_lag());
	else
		CharWait(ch, windwalk_npc_lag());

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
	if (IS_ROOM(ch->in_room, ROOM_NO_TELEPORT) || world[ch->in_room].sector_type == SECT_OCEAN)
	{
		send_to_char("&+yYou failed.\r\n", ch);
		return;
	}
	if (IS_PC(victim) && IS_SET(victim->specials.act2, PLR2_NOLOCATE) && !is_introd(victim, ch))
	{
		send_to_char("&+yYou failed.\r\n", ch);
		return;
	}
	P_char rider = get_linking_char(victim, LNK_RIDING);
	if (IS_NPC(victim) && rider)
	{
		send_to_char("&+yYou failed.\n", ch);
		return;
	}

	location = victim->in_room;

	if (IS_ROOM(location, ROOM_NO_TELEPORT) || world[location].sector_type == SECT_CASTLE ||
	    world[location].sector_type == SECT_CASTLE_WALL ||
	    world[location].sector_type == SECT_CASTLE_GATE || racewar(ch, victim) ||
	    (GET_MASTER(ch) && IS_PC(victim)))
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

	distance = windwalk_distance(level, ch);

	if (!IS_TRUSTED(ch) && how_close(ch->in_room, victim->in_room, distance) < 0 &&
	    how_close(victim->in_room, ch->in_room, distance) < 0)
	{
		send_to_char("&+yYou failed.\r\n", ch);
		return;
	}
	for (tmp = world[ch->in_room].people; tmp; tmp = tmp->next_in_room)
	{
		if ((IS_AFFECTED(tmp, AFF_BLIND) || (tmp->specials.z_cord != ch->specials.z_cord) ||
		     (tmp == ch) || !windwalk_unseen_roll(live_rolls)) &&
		    (IS_PC(ch) && !IS_TRUSTED(ch)))
			continue;
		if (CAN_SEE(tmp, ch))
			act("&+C$n rides the wind and starts to move away.", FALSE, ch, 0, tmp,
			    TO_VICT);
		else
			act("&+CAn ethereal cloud forms and a gust of wind starts to move it away.",
			    FALSE, ch, 0, tmp, TO_VICT);
		send_to_char(buf, tmp);
	}

#if defined(CTF_MUD) && (CTF_MUD == 1)
	if (ctf_carrying_flag(ch) == CTF_PRIMARY)
	{
		send_to_char("You can't carry that with you.\r\n", ch);
		drop_ctf_flag(ch);
	}
#endif

	char_from_room(ch);
	char_to_room(ch, location, -1);

	for (tmp = world[ch->in_room].people; tmp; tmp = tmp->next_in_room)
	{
		if ((IS_AFFECTED(tmp, AFF_BLIND) || (tmp == ch) ||
		     !windwalk_unseen_roll(live_rolls)) &&
		    (IS_PC(ch) && !IS_TRUSTED(ch)))
			continue;
		if (CAN_SEE(tmp, ch))
			act("&+C$n appears in a gust of swirling wind.", FALSE, ch, 0, tmp,
			    TO_VICT);
		else
			act("&+CAn ethereal cloud forms in a gust of swirling wind.", FALSE, ch, 0,
			    tmp, TO_VICT);
		send_to_char(buf, tmp);
	}
}

// The beacon decays after this many pulses.
static int frost_beacon_decay(const Rolls &rolls, int level)
{
	return rolls.dice(level / 7, 2) * WAIT_MIN;
}

// A nonzero roll in the beacon's object proc warns its owner of someone leaving its room.
int frost_beacon_alert_roll(const Rolls &rolls)
{
	return rolls.number(0, 2);
}

std::string frost_beacon_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const int outcomes =
		frost_beacon_alert_roll(highest_rolls) - frost_beacon_alert_roll(lowest_rolls) + 1;
	return fact("Beacon lasts", real_time(frost_beacon_decay(lowest_rolls, level)) + " to " +
					    real_time(frost_beacon_decay(highest_rolls, level)) +
					    " at your level, " + std::to_string(level)) +
	       fact("Warns you of a player walking out of its room",
		    std::to_string(outcomes - 1) + " in " + std::to_string(outcomes)) +
	       "  No warning for your group, or while you are in that room.\n";
}

void spell_frost_beacon(int level, P_char ch, char * /*arg*/, int /*type*/, P_char /*victim*/,
			P_obj /*tar_obj*/)
{
	P_obj beacon;

	beacon = read_object(real_object(99), REAL);

	if (!beacon)
	{
		logit(LOG_DEBUG, "spell_frost_beacon(): obj x not loadable");
		return;
	}

	act("&+CYou conjure a block of ice and mentally link it to yourself.", FALSE, ch, beacon, 0,
	    TO_CHAR);
	act("&+C$n conjures up a block of arcane ice and leaves it to melt.", FALSE, ch, beacon, 0,
	    TO_ROOM);

	// 8 to 16 minutes at lvl 56.  Get spell 6th circle, so level 26 / 7 = 3 to 6 minutes when you get it.
	set_obj_affected(beacon, frost_beacon_decay(live_rolls, level), TAG_OBJ_DECAY, 0);

	beacon->value[0] = GET_PID(ch);

	obj_to_room(beacon, ch->in_room);
	SET_BIT(beacon->extra_flags, ITEM_SECRET);
}

static int vapor_strike_duration(int level)
{
	return MAX(5, level / 2);
}

static int vapor_strike_hitroll(const Rolls &rolls)
{
	return rolls.dice(3, 3) + rolls.number(0, 2);
}

std::string vapor_strike_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Duration", game_hours(vapor_strike_duration(level)) + " at your level, " +
					std::to_string(level)) +
	       fact("Hitroll", "+" + show({ vapor_strike_hitroll(lowest_rolls),
					    vapor_strike_hitroll(highest_rolls) })) +
	       "  Recasting it only renews the duration.\n";
}

void spell_vapor_strike(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			P_char victim, P_obj /*tar_obj*/)
{
	struct affected_type af;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
		return;

	bzero(&af, sizeof(af));

	if (!affected_by_spell(victim, SPELL_VAPOR_STRIKE))
	{
		send_to_char("&+cThe vapors have increased your precision.\r\n", victim);

		af.type = SPELL_VAPOR_STRIKE;
		af.duration = vapor_strike_duration(level);
		af.modifier = vapor_strike_hitroll(live_rolls);
		af.location = APPLY_HITROLL;
		affect_to_char(victim, &af);
	}
	else
	{
		struct affected_type *af1;
		for (af1 = victim->affected; af1; af1 = af1->next)
		{
			if (af1->type == SPELL_VAPOR_STRIKE)
			{
				af1->duration = vapor_strike_duration(level);
				send_to_char(
					"&+cYour &+Cvapor strike &+c ability was refreshed!\r\n",
					victim);
			}
		}
	}
}

static int forked_lightning_forks(P_char ch)
{
	int num_missiles = 3;
	if (GET_LEVEL(ch) >= 53)
	{
		num_missiles++;
	}
	return num_missiles;
}

// Damage per fork, and what a successful save leaves of it.
static int forked_lightning_damage(const Rolls &rolls, int level)
{
	return 2 * level + rolls.number(30, 64);
}

static int forked_lightning_saved(int dam)
{
	return (dam * 2) / 3;
}

std::string forked_lightning_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range hit = { forked_lightning_damage(lowest_rolls, level),
			    forked_lightning_damage(highest_rolls, level) };
	return fact("Forks", std::to_string(forked_lightning_forks(ch)) + " at your level, " +
				     std::to_string(level)) +
	       fact("Lightning damage per fork", show(hit)) +
	       fact("If the target saves, once for all forks",
		    show({ forked_lightning_saved(hit.low), forked_lightning_saved(hit.high) })) +
	       "  Globes and spirit wards do not stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_forked_lightning(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			    P_obj /*tar_obj*/)
{
	int dam;
	int num_missiles = forked_lightning_forks(ch);
	struct damage_messages messages = {
		"You unleash a powerful blast of &-L&+Bforked lightning&n directed at $N.",
		"Giant bolts of &-L&+Bforked lightning&n hit you square in the chest, sending you reeling.",
		"$n stretches out $s hand, unleashing a blast of deadly &-L&+Bforked lightning&n toward $N.",
		"Your deadly blast of &-L&+Bforked lightning&n ends $N's life abruptly.",
		"Your body goes numb as a bolt of &+Blightning&n ends your life.",
		"$n hits $N with such a blast of &-L&+Blightning&n that nothing is left but a pair of smoking boots.",
		0
	};

	// dam should total: 9 * level +/- 25 .. but 3 forks -> 3 * level +/- 8..
	dam = forked_lightning_damage(live_rolls, level);

	int mod = get_default_save_mod(victim, ch, SAVING_SPELL, SPELL_FORKED_LIGHTNING);
	if (NewSaves(victim, SAVING_SPELL, mod))
	{
		dam = forked_lightning_saved(dam);
	}

	while (num_missiles-- &&
	       spell_damage(ch, victim, dam, SPLDAM_LIGHTNING, 0, &messages) == DAM_NONEDEAD)
	{
		;
	}
}

// Frost bolt's damage level stops growing at 30.
static int frost_bolt_level(int level)
{
	if (level > 30)
		level = 30;
	return level;
}

static int frost_bolt_damage(const Rolls &rolls, int level)
{
	return 4 * (rolls.number(6, 9) + (level / 3));
}

static int frost_bolt_saved(int dam)
{
	return (2 * dam) / 3;
}

// The later hits: the first this many pulses after casting, then one more after a shorter
// wait, for this many rounds after the casting hit.
static int frost_bolt_first_delay()
{
	return PULSE_VIOLENCE;
}

static int frost_bolt_next_delay()
{
	return (3 * PULSE_SPELLCAST) / 2;
}

static int frost_bolt_later_hits()
{
	return 2;
}

// The chill of the first hit.
static int frost_bolt_chill_duration()
{
	return 2;
}

static int frost_bolt_chill_strength()
{
	return -1;
}

std::string frost_bolt_facts(P_char ch)
{
	const int level = frost_bolt_level(GET_LEVEL(ch));
	const Range hit = { frost_bolt_damage(lowest_rolls, level),
			    frost_bolt_damage(highest_rolls, level) };
	return fact("Cold damage per hit",
		    show(hit) + " at level " + std::to_string(level) + ", your level up to 30") +
	       fact("If the target saves, each hit",
		    show({ frost_bolt_saved(hit.low), frost_bolt_saved(hit.high) })) +
	       fact("Hits", std::to_string(frost_bolt_later_hits() + 1) + ": on casting, " +
				    seconds(frost_bolt_first_delay()) + " later, then " +
				    seconds(frost_bolt_next_delay()) + " later") +
	       fact("Stopped by", "any globe of invulnerability or spirit ward") +
	       fact("If its first hit lands and a second save fails",
		    "strength " + std::to_string(frost_bolt_chill_strength())) +
	       fact("That strength loss lasts", game_hours(frost_bolt_chill_duration())) +
	       "  It joins any chill touch already on the target.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

struct frost_data
{
	int level;
	int round;
};

void event_frost_bolt(P_char ch, P_char victim, P_obj /*obj*/, void *data)
{
	struct frost_data *fdata;

	int dam;
	struct damage_messages messages = {
		"&+WYou send a bolt of &+Bchilling frost&n &+Wstreaking towards $N, which shatters on impact.",
		"&+BThe chill in your bones makes your body ache.",
		"&+b$N is hit by an intense blast of &+Bfrost&n&+W, sending shards of ice flying through the room.",
		"&+WYour &+Bfrost bolt&+W is simply too much for $N who collapses in a frozen lump.",
		"&+BThe intense cold is simply too much as it completely overwhelms your body.",
		"&+W$n's &+Bfrost bolt&+W is simply too much for $N who collapses in a frozen lump.",
		0
	};

	fdata = (struct frost_data *)data;

	// Actual damage @lvl 11: 9-12 | 6-8 saved, @lvl 30: 16-19 | 10-12 saved.
	dam = frost_bolt_damage(live_rolls, fdata->level);
	int mod = get_default_save_mod(victim, ch, SAVING_SPELL, SPELL_FROST_BOLT);
	if (NewSaves(victim, SAVING_SPELL, mod))
		dam = frost_bolt_saved(dam);

	if (spell_damage(ch, victim, dam, SPLDAM_COLD, SPLDAM_ALLGLOBES, &messages) == DAM_NONEDEAD)
	{
		// We will have an initil round 0 at cast, then round 1 on first pulse, and round 2 on second pulse, but no 3rd.
		if (++(fdata->round) < frost_bolt_later_hits())
			add_event(event_frost_bolt, frost_bolt_next_delay(), ch, victim, NULL, 0,
				  fdata, sizeof(struct frost_data));
	}
}

void spell_frost_bolt(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
		      P_char victim, P_obj /*tar_obj*/)
{
	P_obj obj;
	struct frost_data fdata;
	struct affected_type af;
	int dam;
	struct damage_messages messages = {
		"&+WYou send a bolt of &+Bchilling frost&n &+Wstreaking towards $N, which shatters on impact.",
		"&+BYou feel an intense cold that turns your body numb.",
		"&+b$N is hit by an intense blast of &+Bfrost&n&+W, sending shards of ice flying through the room.",
		"&+WYour &+Bfrost bolt&+W is simply too much for $N who collapses in a frozen lump.",
		"&+BThe intense cold is simply too much as it completely overwhelms your body.",
		"&+W$n's &+Bfrost bolt&+W is simply too much for $N who collapses in a frozen lump.",
		0
	};

	obj = read_object(50, VIRTUAL);
	if (!obj || ch->in_room == NOWHERE)
		return;

	set_obj_affected(obj, 800, TAG_OBJ_DECAY, 0);
	obj_to_room(obj, ch->in_room);

	level = frost_bolt_level(level);

	// Actual damage @lvl 11: 9-12 | 6-8 saved, @lvl 30: 16-19 | 10-12 saved.
	dam = frost_bolt_damage(live_rolls, level);
	int mod = get_default_save_mod(victim, ch, SAVING_SPELL, SPELL_FROST_BOLT);
	if (NewSaves(victim, SAVING_SPELL, mod))
		dam = frost_bolt_saved(dam);

	fdata.round = 0;
	fdata.level = level;

	if (!spell_damage(ch, victim, dam, SPLDAM_COLD, SPLDAM_ALLGLOBES, &messages))
	{
		if (!NewSaves(victim, SAVING_SPELL, mod))
		{
			memset(&af, 0, sizeof(af));
			af.type = SPELL_CHILL_TOUCH;
			af.duration = frost_bolt_chill_duration();
			af.modifier = frost_bolt_chill_strength();
			af.location = APPLY_STR;
			affect_join(victim, &af, TRUE, FALSE);
		}
		add_event(event_frost_bolt, frost_bolt_first_delay(), ch, victim, NULL, 0, &fdata,
			  sizeof(fdata));
	}
}

static int ethereal_form_duration(P_char ch)
{
	return (int)(8 + GET_LEVEL(ch) / 10 + GET_CHAR_SKILL(ch, SKILL_DEVOTION) / 10);
}

std::string ethereal_form_facts(P_char ch)
{
	extern float dam_factor[LAST_DF + 1];
	return fact("Duration",
		    game_hours(ethereal_form_duration(ch)) + " with your level and devotion") +
	       fact("Elemental spell damage to you", damage_change(dam_factor[DF_PHANTFORM])) +
	       "  You turn invisible, pass through doors and cannot bash.\n"
	       "  Recasting it only renews the duration.\n";
}

void spell_ethereal_form(int /*level*/, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			 P_char victim, P_obj /*tar_obj*/)
{
	struct affected_type af;
	int duration = ethereal_form_duration(ch);

	if (affected_by_spell(ch, SPELL_ETHEREAL_FORM))
	{
		struct affected_type *af1;
		for (af1 = victim->affected; af1; af1 = af1->next)
		{
			if (af1->type == SPELL_ETHEREAL_FORM)
			{
				af1->duration = duration;
			}
		}
		send_to_char("&+LYour ethereal energy form is renewed\r\n", ch);
		return;
	}

	send_to_char("&+LYour physical substance seems to fade away...&n\r\n", ch);
	act("&+L$n physical substance seems to fade away...&n", FALSE, ch, 0, 0, TO_ROOM);

	memset(&af, 0, sizeof(af));
	af.type = SPELL_ETHEREAL_FORM;
	af.duration = duration;
	af.bitvector = AFF_INVISIBLE;
	af.bitvector2 = AFF2_PASSDOOR;
	af.bitvector4 = AFF4_PHANTASMAL_FORM;
	affect_to_char(ch, &af);
}

// What the conjure air, void and ice spells share. An elemental's level comes from the
// cast level, within 10-45, or within 10-51 for the spec it belongs to.
static int conjured_elemental_charisma(P_char ch)
{
	return GET_C_CHA(ch) + (GET_LEVEL(ch) / 5);
}

static int conjured_elemental_base(int level)
{
	return (level / 5) * 2;
}

static int conjured_elemental_roll(const Rolls &rolls, int mlvl)
{
	return rolls.number(mlvl, mlvl * 3);
}

static int conjured_elemental_level(int lvl)
{
	return BOUNDED(10, lvl, 45);
}

static int conjured_elemental_spec_level(int level)
{
	return BOUNDED(10, level, 51);
}

static int conjured_elemental_hit_points(const Rolls &rolls, int mob_level, int charisma)
{
	return rolls.dice(mob_level / 2, 10) + mob_level + charisma;
}

static int conjured_elemental_roll_bonus(int mob_level)
{
	return mob_level / 3;
}

// A player's elemental above the player's level rebels when charisma is below this roll.
static int conjured_elemental_temper_roll(const Rolls &rolls)
{
	return rolls.number(10, 100);
}

// A rebelling elemental dies after this many pulses.
static int conjured_elemental_poof(const Rolls &rolls)
{
	return (4 + rolls.number(1, 6)) * WAIT_SEC;
}

// Charm ticks at the elemental's intelligence index. Unless charmed for good, it then dies
// this many pulses from the summons: the charm's ticks as minutes, plus the roll and one.
static int conjured_elemental_charm(int intelligence_index)
{
	return 400 / intelligence_index;
}

static int conjured_elemental_late_death_roll(const Rolls &rolls)
{
	return rolls.number(1, 10);
}

static int conjured_elemental_death_delay(int duration)
{
	return (duration + 1) * 60 * 4;
}

// The rolled level range of a caster outside the elemental's spec.
static Range conjured_elemental_level_range(int level)
{
	const int mlvl = conjured_elemental_base(level);
	return { conjured_elemental_level(conjured_elemental_roll(lowest_rolls, mlvl)),
		 conjured_elemental_level(conjured_elemental_roll(highest_rolls, mlvl)) };
}

static Range conjured_elemental_plain_hit_points(P_char ch, Range mob)
{
	const int charisma = conjured_elemental_charisma(ch);
	return { conjured_elemental_hit_points(lowest_rolls, mob.low, charisma),
		 conjured_elemental_hit_points(highest_rolls, mob.high, charisma) };
}

static std::string conjured_elemental_page(P_char ch, Range mob, Range hit_points,
					   const char *hit_points_source)
{
	const int level = GET_LEVEL(ch);
	std::string text =
		fact("Elemental's level", show(mob) + " at your level, " + std::to_string(level)) +
		fact("Its hit points", show(hit_points) + " with your " + hit_points_source) +
		fact("Its hitroll and damroll", show({ conjured_elemental_roll_bonus(mob.low),
						       conjured_elemental_roll_bonus(mob.high) }));
	if (mob.high > level)
		text += fact("If it outlevels you, by charisma",
			     "attacks, gone in " + seconds(conjured_elemental_poof(lowest_rolls)) +
				     " to " + seconds(conjured_elemental_poof(highest_rolls)));
	return text +
	       fact("It dies after its charm's ticks as minutes, plus",
		    real_time(conjured_elemental_death_delay(
			    conjured_elemental_late_death_roll(lowest_rolls))) +
			    " to " +
			    real_time(conjured_elemental_death_delay(
				    conjured_elemental_late_death_roll(highest_rolls)))) +
	       "  Its charm depends on its intelligence; a globe of shadows or unholy\n"
	       "  alliance makes the charm permanent, and then it does not die.\n"
	       "  Only one elemental at a time; safe rooms block it.\n";
}

// A tempest magus's air elemental has the caster's own hit points and more.
static int conjure_air_tempest_hit_points(P_char ch, int charisma)
{
	return ch->points.base_hit + (GET_LEVEL(ch) * 2) + charisma;
}

// A roll below the chance, or the tempest magus spec, conjures the huge air elemental.
static int conjure_air_huge_roll(const Rolls &rolls)
{
	return rolls.number(0, 100);
}

static int conjure_air_huge_chance()
{
	return 15;
}

std::string conjure_air_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const int outcomes =
		conjure_air_huge_roll(highest_rolls) - conjure_air_huge_roll(lowest_rolls) + 1;
	if (GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_TEMPESTMAGUS))
	{
		const int mob = conjured_elemental_spec_level(level);
		const int hit_points =
			conjure_air_tempest_hit_points(ch, conjured_elemental_charisma(ch));
		return fact("Huge elemental", "always, as a tempest magus") +
		       conjured_elemental_page(ch, { mob, mob }, { hit_points, hit_points },
					       "base hit points and charisma");
	}
	const Range mob = conjured_elemental_level_range(level);
	return fact("Huge elemental",
		    std::to_string(conjure_air_huge_chance()) + " in " + std::to_string(outcomes)) +
	       conjured_elemental_page(ch, mob, conjured_elemental_plain_hit_points(ch, mob),
				       "charisma");
}

void spell_conjure_air(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		       P_obj /*tar_obj*/)
{
	P_char mob;
	int sum, mlvl, lvl;
	int i, j;
	int charisma = conjured_elemental_charisma(ch);
	struct follow_type *k;

	static struct
	{
		const int mob_number;
		const char *message;
	} summons[] = { { 1102, "&+CA gust of wind solidifies into&n $n." },
			{ 43, "&+CA HUGE gust of wind solidifies into&n $n." } };

	if (CHAR_IN_SAFE_ROOM(ch))
	{
		send_to_char("A mysterious force blocks your conjuring!\r\n", ch);
		return;
	}

	for (k = ch->followers, i = 0, j = 0; k; k = k->next)
	{
		victim = k->follower;
		if (IS_ELEMENTAL(victim))
		{
			if (GET_LEVEL(victim) < 50)
				i++;
			else
				j++;
		}
	}

	if (i >= 1 || j >= 1)
	{
		send_to_char("You cannot control any more elementals!\r\n", ch);
		return;
	}

	if (conjure_air_huge_roll(live_rolls) < conjure_air_huge_chance() ||
	    GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_TEMPESTMAGUS))
		sum = 1;
	else
		sum = 0;

	mob = read_mobile(real_mobile(summons[sum].mob_number), REAL);

	if (!mob)
	{
		logit(LOG_DEBUG, "spell_conjure_elemental(): mob %d not loadable",
		      summons[sum].mob_number);
		send_to_char("Bug in conjure elemental.  Tell a god!\r\n", ch);
		return;
	}

	GET_SIZE(mob) = SIZE_MEDIUM;
	mob->player.m_class = CLASS_WARRIOR;
	char_to_room(mob, ch->in_room, 0);

	act(summons[sum].message, TRUE, mob, 0, 0, TO_ROOM);

	mlvl = conjured_elemental_base(level);
	lvl = conjured_elemental_roll(live_rolls, mlvl);

	if (GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_TEMPESTMAGUS))
		mob->player.level = conjured_elemental_spec_level(level);
	else
		mob->player.level = conjured_elemental_level(lvl);

	if (GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_TEMPESTMAGUS))
	{
		GET_MAX_HIT(mob) = GET_HIT(mob) = mob->points.base_hit =
			conjure_air_tempest_hit_points(ch, charisma);
		/*
		 GET_MAX_HIT(mob) = GET_HIT(mob) = mob->points.base_hit =
		dice(GET_LEVEL(mob) / 2, 45) + GET_LEVEL(mob) + charisma;
		*/
	}
	else
	{
		GET_MAX_HIT(mob) = GET_HIT(mob) = mob->points.base_hit =
			conjured_elemental_hit_points(live_rolls, GET_LEVEL(mob), charisma);
	}

	SET_BIT(mob->specials.affected_by, AFF_INFRAVISION);

	mob->points.base_hitroll = mob->points.hitroll =
		conjured_elemental_roll_bonus(GET_LEVEL(mob));
	mob->points.base_damroll = mob->points.damroll =
		conjured_elemental_roll_bonus(GET_LEVEL(mob));
	MonkSetSpecialDie(mob); /* 2d6 to 4d5 */

	if (IS_PC(ch) && /*(GET_LEVEL(mob) > number((level - i * 4), level * 3 / 2)) */
	    (GET_LEVEL(mob) > GET_LEVEL(ch)) &&
	    charisma < conjured_elemental_temper_roll(live_rolls))
	{
		act("$N is NOT pleased at being suddenly summoned against $S will!", TRUE, ch, 0,
		    mob, TO_ROOM);
		act("$N is NOT pleased with you at all!", TRUE, ch, 0, mob, TO_CHAR);
		// Poof in 5-10 sec.
		add_event(event_pet_death, conjured_elemental_poof(live_rolls), mob, NULL, NULL, 0,
			  NULL, 0);
		MobStartFight(mob, ch);
	}
	else
	{ /* Under control */
		act("$N sulkily says 'Your wish is my command, $n!'", TRUE, ch, 0, mob, TO_ROOM);
		act("$N sulkily says 'Your wish is my command, master!'", TRUE, ch, 0, mob,
		    TO_CHAR);

		int duration = setup_pet(
			mob, ch, conjured_elemental_charm(STAT_INDEX(GET_C_INT(mob))), PET_NOCASH);
		add_follower(mob, ch);
		/* if the pet will stop being charmed after a bit, also make it suicide 1-10 minutes later */
		if (duration >= 0)
		{
			duration += conjured_elemental_late_death_roll(live_rolls);
			add_event(event_pet_death, conjured_elemental_death_delay(duration), mob,
				  NULL, NULL, 0, NULL, 0);
		}
	}
}

static int storm_empathy_duration(int level)
{
	return level;
}

// Lightning protection cuts lightning breath by this factor.
double storm_empathy_lightning_breath_factor()
{
	return .80;
}

std::string storm_empathy_facts(P_char ch)
{
	extern float dam_factor[LAST_DF + 1];
	const int level = GET_LEVEL(ch);
	return fact("Duration", game_hours(storm_empathy_duration(level)) + " at your level, " +
					std::to_string(level)) +
	       fact("Cold and lightning spell damage", damage_change(dam_factor[DF_PROTECTION])) +
	       fact("Lightning breath damage",
		    damage_change(storm_empathy_lightning_breath_factor())) +
	       "  A cold or lightning shield replaces that spell damage cut.\n";
}

void spell_storm_empathy(int level, P_char /*ch*/, char * /*arg*/, [[maybe_unused]] int type,
			 P_char victim, P_obj /*tar_obj*/)
{
	struct affected_type af;

	bzero(&af, sizeof(af));

	af.type = SPELL_STORM_EMPATHY;
	af.duration = storm_empathy_duration(level);
	af.bitvector2 = AFF2_PROT_COLD | AFF2_PROT_LIGHTNING;

	affect_to_char(victim, &af);

	send_to_char("You feel protected from the storms!\r\n", victim);
}

// number() takes its bounds in either order, so a low level heals up to 150.
static int greater_ethereal_recharge_healing(const Rolls &rolls, P_char ch)
{
	return rolls.number(150, (GET_LEVEL(ch) * 5));
}

std::string greater_ethereal_recharge_facts(P_char ch)
{
	return fact("Healing", show({ greater_ethereal_recharge_healing(lowest_rolls, ch),
				      greater_ethereal_recharge_healing(highest_rolls, ch) }) +
				       " at your level, " + std::to_string(GET_LEVEL(ch))) +
	       "  It also cures blindness.\n"
	       "  Only for phantasmal forms and air or void elemental pets.\n";
}

void spell_greater_ethereal_recharge(int level, P_char ch, char * /*arg*/, int /*type*/,
				     P_char victim, P_obj tar_obj)
{
	int healpoints;

	if (IS_PC_PET(victim) && GET_RACE(victim) != RACE_A_ELEMENTAL &&
	    GET_RACE(victim) != RACE_V_ELEMENTAL)
	{
		send_to_char("They are not composed of ethereal matter...\r\n", ch);
		return;
	}

	if (!IS_PC_PET(victim) && !IS_AFFECTED4(victim, AFF4_PHANTASMAL_FORM))
	{
		send_to_char("They are not composed of ethereal matter...\r\n", ch);
		return;
	}

	spell_cure_blind(level, ch, NULL, SPELL_TYPE_SPELL, victim, tar_obj);

	healpoints = greater_ethereal_recharge_healing(live_rolls, ch);
	heal(victim, ch, healpoints, GET_MAX_HIT(victim));

	if (victim != ch)
	{
		act("$n reaches out at $N, touching $M. ", FALSE, ch, 0, victim, TO_NOTVICT);
		act("You reach out your hand and touch $N, greatly healing $s ethereal body.", TRUE,
		    ch, 0, victim, TO_CHAR);
	}

	send_to_char("&+WYou feel the powers of greater ethereal matter recharge you..!\r\n",
		     victim);
	act("$n's ethereal form shimmers and seems to glow with renewed strength.", FALSE, victim,
	    0, 0, TO_ROOM);

	update_pos(victim);
}

// Roll once, then cap the healing at 150.
static int ethereal_recharge_healing(const Rolls &rolls, int level)
{
	const int healing = rolls.dice(5, level);
	return MIN(150, healing);
}

// An air conjurer healing their own air form gains at most this many hit points.
static int ethereal_recharge_air_cap()
{
	return 100;
}

std::string ethereal_recharge_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const int high = ethereal_recharge_healing(highest_rolls, level);
	std::string text =
		fact("Healing", show({ ethereal_recharge_healing(lowest_rolls, level), high }) +
					" at your level, " + std::to_string(level));
	if (GET_SPEC(ch, CLASS_CONJURER, SPEC_AIR))
		text += fact("On your own air form",
			     "at most " + std::to_string(ethereal_recharge_air_cap()) +
				     " hit points");
	return text + "  It also cures blindness.\n"
		      "  Only for phantasmal forms and air or void elemental pets.\n";
}

void spell_ethereal_recharge(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			     P_obj tar_obj)
{
	int healpoints;
	const bool air_self = ch == victim && IS_PC(ch) && GET_SPEC(ch, CLASS_CONJURER, SPEC_AIR) &&
			      affected_by_spell(ch, SPELL_AIR_FORM);

	if (!air_self && IS_PC_PET(victim) && GET_RACE(victim) != RACE_A_ELEMENTAL &&
	    GET_RACE(victim) != RACE_V_ELEMENTAL)
	{
		send_to_char("They are not composed of ethereal matter...\r\n", ch);
		return;
	}

	if (!air_self && !IS_PC_PET(victim) && !IS_AFFECTED4(victim, AFF4_PHANTASMAL_FORM))
	{
		send_to_char("They are not composed of ethereal matter...\r\n", ch);
		return;
	}

	spell_cure_blind(level, ch, NULL, SPELL_TYPE_SPELL, victim, tar_obj);

	healpoints = ethereal_recharge_healing(live_rolls, level);
	heal(victim, ch, healpoints,
	     air_self ? MIN(GET_MAX_HIT(victim), GET_HIT(victim) + ethereal_recharge_air_cap()) :
			GET_MAX_HIT(victim));

	if (victim != ch)
	{
		act("$n reaches out at $N, touching $M.", FALSE, ch, 0, victim, TO_NOTVICT);
		act("You reach out at $N and touch $M.", TRUE, ch, 0, victim, TO_CHAR);
	}

	send_to_char("&+WYou feel ethereal power recharge you!\r\n", victim);
	act("$n appears to gain strength from a cloud of ethereal matter.", FALSE, victim, 0, 0,
	    TO_ROOM);

	update_pos(victim);
}

// Each of the target's affects is stolen when this roll is below the cast level.
static int arcane_whirlwind_roll(const Rolls &rolls)
{
	return rolls.number(0, 100);
}

std::string arcane_whirlwind_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const int outcomes =
		arcane_whirlwind_roll(highest_rolls) - arcane_whirlwind_roll(lowest_rolls) + 1;
	return fact("Chance to steal each spell",
		    std::to_string(level) + " in " + std::to_string(outcomes) + " at your level, " +
			    std::to_string(level)) +
	       "  A stolen spell is cast on you at the target's level.\n"
	       "  Self-only, aggressive and stored spells cannot be stolen.\n";
}

void spell_arcane_whirlwind(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			    P_char victim, P_obj /*tar_obj*/)
{
	int success = 0;
	struct affected_type *aff;

	if (IS_TRUSTED(victim))
	{
		send_to_char("&+ROh no you don't!\r\n", ch);
		return;
	}

	if (victim->affected)
	{
		struct affected_type *next;

		for (aff = victim->affected; aff; aff = next)
		{
			next = aff->next;

			if (arcane_whirlwind_roll(live_rolls) < level)
			{
				if (IS_SPELL(aff->type) && skills[aff->type].spell_pointer &&
				    !(skills[aff->type].targets & TAR_SELF_ONLY) &&
				    !(skills[aff->type].targets & TAR_AGGRO) &&
				    !(aff->flags & AFFTYPE_STORE))
				{
					success++;
					skills[aff->type].spell_pointer(GET_LEVEL(victim), ch, 0,
									SPELL_TYPE_SPELL, ch, 0);
					wear_off_message(victim, aff);
					affect_remove(victim, aff);
				}
			}
		}
	}

	if (success)
	{
		act("&+WHuge &+Cgusts&n&+W of arcane wind sweep across the area, encircling $N then quickly returning back to $n.&n",
		    FALSE, ch, 0, victim, TO_NOTVICT);
		act("&+CArcane&+W wind from $n envelopes you, then returns, leaving you feeling drained.",
		    FALSE, ch, 0, victim, TO_VICT);
		act("&+WAs the &+Carcane &+Wwind hits $N and returns back you, you feel infused with stolen magic.",
		    FALSE, ch, 0, victim, TO_CHAR);
	}
}

static int purge_damage(int level, int victim_level)
{
	return 10 * (3 * level - victim_level);
}

std::string purge_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Damage",
		    std::to_string(purge_damage(level, 0)) + " at your level, " +
			    std::to_string(level) + ", less " +
			    std::to_string(purge_damage(level, 0) - purge_damage(level, 1)) +
			    " per target level") +
	       "  Only creatures with a master and no experience can be purged.\n"
	       "  Globes and spirit wards do not stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_purge(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		 P_obj /*tar_obj*/)
{
	int dam;
	struct damage_messages messages = {
		"&+CYou chant a harmonic spell, sending forth a blast of magical wind, purging $N.",
		"&+CYou feel your enchantments waver and dissipate from the onslaught of $n's purge.",
		"$n spell sends $N reeling by the powerful dispelling magic.",
		"You purge $N instantly, banishing it from this world and sending it back where it belongs.",
		"$N is simply overwhelmed by the incredible power of $n's purge, and vanishes.",
		""
	};

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim) || ch == victim)
		return;

	if (!GET_MASTER(victim) || GET_EXP(victim))
	{
		act("$N belongs to this world, $E cannot be affected.", FALSE, ch, 0, victim,
		    TO_CHAR);
		return;
	}

	dam = purge_damage(level, GET_LEVEL(victim));

	spell_damage(ch, victim, dam, SPLDAM_GENERIC,
		     RAWDAM_TRANCEVAMP | RAWDAM_BTXVAMP | RAWDAM_SHRTVMP, &messages);
	// Changed the damage type here from SPLDAM_NEGATIVE to SPLDAM_GENERIC, since the negative type would heal undead pets. Zion 9/28/2008
}

void event_tupor_wake(P_char /*ch*/, P_char victim, P_obj /*obj*/, void * /*data*/)
{
	if (!victim || !IS_ALIVE(victim))
	{
		return;
	}

	if (IS_AFFECTED4(victim, AFF4_TUPOR))
	{
		REMOVE_BIT(victim->specials.affected_by4, AFF4_TUPOR);
	}

	if (IS_AFFECTED(victim, AFF_SLEEP))
	{
		REMOVE_BIT(victim->specials.affected_by, AFF_SLEEP);
	}

	do_wake(victim, NULL, CMD_WAKE);
	do_alert(victim, NULL, CMD_ALERT);
}

// A roll of 0 skips the target's save.
static int induce_tupor_save_roll(const Rolls &rolls)
{
	return rolls.number(0, 9);
}

static int induce_tupor_save_mod()
{
	return 5;
}

static int induce_tupor_duration()
{
	return (int)(5 * PULSE_VIOLENCE);
}

static int induce_tupor_wake_delay()
{
	return (PULSE_VIOLENCE * 5);
}

// A nonzero roll makes a sleeping NPC forget its enemies.
static int induce_tupor_forget_roll(const Rolls &rolls)
{
	return rolls.number(0, 2);
}

std::string induce_tupor_facts(P_char /*ch*/)
{
	const int no_save =
		induce_tupor_save_roll(highest_rolls) - induce_tupor_save_roll(lowest_rolls) + 1;
	const int forget = induce_tupor_forget_roll(highest_rolls) -
			   induce_tupor_forget_roll(lowest_rolls) + 1;
	return fact("Sleep", seconds(induce_tupor_duration())) +
	       fact("Target wakes after", seconds(induce_tupor_wake_delay())) +
	       fact("Chance of no save", "1 in " + std::to_string(no_save)) +
	       fact("Otherwise a spell save",
		    "+" + std::to_string(induce_tupor_save_mod()) + ", harder") +
	       fact("Chance a slept NPC forgets its enemies",
		    std::to_string(forget - 1) + " in " + std::to_string(forget)) +
	       "  Elites cannot be slept, nor NPC dragons, demons, devils, angels,\n"
	       "  beholders, liches, avatars or constructs. It can be shrugged.\n"
	       "  Anyone asleep or knocked out already is not affected.\n";
}

void spell_induce_tupor(int /*level*/, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			P_char victim, P_obj /*tar_obj*/)
{
	if (!IS_ALIVE(ch) || !IS_ALIVE(victim) || IS_TRUSTED(victim))
	{
		return;
	}

	if (ch == victim)
	{
		send_to_char("No can do!\r\n", ch);
		return;
	}

	act("&+WYou whisper a musical incantation attempting to induce a deep sleep upon $N.", TRUE,
	    ch, 0, victim, TO_CHAR);

	if (IS_AFFECTED4(victim, AFF4_TUPOR))
	{
		send_to_char("Your victim is already in a tupor!\r\n", ch);
		return;
	}

	if (IS_AFFECTED(victim, AFF_SLEEP) || IS_AFFECTED(victim, AFF_KNOCKED_OUT) ||
	    (GET_STAT(victim) == STAT_SLEEPING) || affected_by_spell(victim, SPELL_SLEEP) ||
	    get_scheduled(victim, event_tupor_wake))
	{
		send_to_char("Your victim is already dreaming of a better life.\r\n", ch);
		return;
	}

	if (resists_spell(ch, victim))
	{
		return;
	}

	// 10% of the time there is no save.
	if (induce_tupor_save_roll(live_rolls))
	{
		if (NewSaves(victim, SAVING_SPELL, induce_tupor_save_mod()))
		{
			return;
		}
	}

	if (IS_ELITE(victim) || IS_GREATER_RACE(victim))
	{
		send_to_char("You sense your victim cannot be forced into a tupor.\r\n", ch);
		return;
	}

	struct affected_type af;
	bzero(&af, sizeof(af));

	af.type = SPELL_SLEEP;
	af.flags = AFFTYPE_SHORT | AFFTYPE_NODISPEL;
	af.duration = induce_tupor_duration();
	af.bitvector = AFF_SLEEP;

	if (GET_OPPONENT(victim))
		stop_fighting(victim);
	affect_to_char(victim, &af);

	if (GET_STAT(victim) > STAT_SLEEPING)
	{
		act("&+WYou suddenly feel very sleepy...", TRUE, victim, 0, 0, TO_CHAR);
		act("&+W$n blinks dreamily, closes $s eyes and enters a deep sleep.", TRUE, victim,
		    0, 0, TO_ROOM);
		SET_POS(victim, GET_POS(victim) + STAT_SLEEPING);
	}

	stop_memorizing(victim, memorization_stop_reason::disrupted);

	if (induce_tupor_forget_roll(live_rolls) && IS_NPC(victim))
	{
		act("&+W$N sleepily stares about blankly, forgetting why $n is here.", TRUE, ch, 0,
		    victim, TO_ROOM);
		act("&+W$N sleepily stares about blankly, forgetting why you are here.", TRUE, ch,
		    0, victim, TO_CHAR);
		clearMemory(victim);
	}

	StopMercifulAttackers(victim);

	if (!get_scheduled(victim, event_tupor_wake))
	{
		add_event(event_tupor_wake, induce_tupor_wake_delay(), ch, victim, NULL, 0, NULL,
			  0);
	}
}

// The terrain changes this many pulses after casting and changes back after this many more.
static int tempest_terrain_delay()
{
	return 2 * PULSE_VIOLENCE;
}

static int tempest_terrain_duration()
{
	return 20 * PULSE_VIOLENCE;
}

std::string tempest_terrain_facts(P_char /*ch*/)
{
	return fact("Takes hold after", seconds(tempest_terrain_delay())) +
	       fact("Lasts", seconds(tempest_terrain_duration())) +
	       "  Not in towns, on roads, indoors or on the air plane.\n";
}

struct tempest_data
{
	int room;
	int old_sect;
};

void spell_tempest_terrain(int /*level*/, P_char ch, char * /*arg*/, int /*type*/,
			   P_char /*victim*/, P_obj /*tar_obj*/)
{
	if (CHAR_IN_TOWN(ch))
	{
		send_to_char("This spell is too powerful to use around town.\n", ch);
		return;
	}
	if (world[ch->in_room].sector_type == SECT_AIR_PLANE)
	{
		send_to_char("This terrain is tempest enough!\n", ch);
		return;
	}
	if (world[ch->in_room].sector_type == SECT_ROAD)
	{
		send_to_char("Nothing seems to happen.\n", ch);
		return;
	}
	if (world[ch->in_room].sector_type == SECT_INSIDE)
	{
		send_to_char("You need to see the sky to invoke the tempest powers.\n", ch);
		return;
	}

	send_to_char(
		"&+CYou raise your hands to the heavens and whisper arcane words, bending the landscape to your will.\r\n",
		ch);

	act("&+C$n raises $s hands while chanting, and dense clouds start gathering around.", FALSE,
	    ch, 0, 0, TO_NOTVICT);

	add_event(event_tempest_terrain, tempest_terrain_delay(), 0, NULL, NULL, 0, &ch->in_room,
		  sizeof(ch->in_room));
}

void event_tempest_terrain(P_char /*ch*/, P_char /*victim*/, P_obj /*obj*/, void *data)
{
	struct tempest_data tdata;

	tdata.room = *((int *)data);
	tdata.old_sect = world[tdata.room].sector_type;

	send_to_room("&+cThe landscape suddenly turns into a billowing cloudscape!\n", tdata.room);

	world[tdata.room].sector_type = SECT_AIR_PLANE;

	add_event(event_tempest_terrain_bye, tempest_terrain_duration(), 0, NULL, NULL, 0, &tdata,
		  sizeof(tdata));
}

void event_tempest_terrain_bye(P_char /*ch*/, P_char /*victim*/, P_obj /*obj*/, void *data)
{
	struct tempest_data *tdata = (struct tempest_data *)data;

	world[tdata->room].sector_type = tdata->old_sect;

	send_to_room(
		"&+cThe landscape shimmers, the clouds disperse, and the terrain shifts back to normal...&n\r\n",
		tdata->room);
}

// Squall damage per target, each condition applied in the handler's order.
static int tempest_damage(const Rolls &rolls, int level)
{
	return level * 5 + rolls.number(1, 20);
}

static double tempest_flying_damage(double dam)
{
	return dam * 1.2;
}

static double tempest_wind_tunnel_damage(double dam)
{
	return dam * 1.2;
}

static double tempest_binding_wind_damage(double dam)
{
	return dam / 1.2;
}

static double tempest_indoors_damage(double dam)
{
	return dam / 2;
}

static double tempest_player_damage(double dam)
{
	return dam * get_property("spell.area.damage.to.pc", 0.5);
}

static double tempest_area_damage(double dam)
{
	return dam * get_property("spell.area.damage.factor.squallTempest", 1.000);
}

// A target above this roll of number(0, 100) is thrown from the room, before the handler's
// changes for the target's luck, flying, the room's winds and being indoors.
static int tempest_takedown_threshold(int level)
{
	return (int)(level / 4);
}

static double tempest_takedown_flying(double takedown_chance)
{
	return takedown_chance * 1.5;
}

static double tempest_takedown_wind_tunnel(double takedown_chance)
{
	return takedown_chance * 1.3;
}

static double tempest_takedown_binding_wind(double takedown_chance)
{
	return takedown_chance / 1.3;
}

static double tempest_takedown_indoors(double takedown_chance)
{
	return takedown_chance / 1.1;
}

static double tempest_takedown_unlucky(double takedown_chance)
{
	return takedown_chance / 2;
}

// The threshold halves when the target's luck over 10 is below this roll.
static int tempest_luck_roll(const Rolls &rolls)
{
	return rolls.number(1, 100);
}

static int tempest_takedown_roll(const Rolls &rolls)
{
	return rolls.number(0, 100);
}

// A direction to throw the target, rerolled among the flat ones for up or down.
static int tempest_door_roll(const Rolls &rolls)
{
	return rolls.number(0, 9);
}

static int tempest_flat_door_roll(const Rolls &rolls)
{
	return rolls.number(0, 3);
}

static int tempest_thrown_lag()
{
	return PULSE_VIOLENCE * 1;
}

static int tempest_lag()
{
	return (int)(PULSE_SPELLCAST * 1);
}

std::string tempest_facts(P_char ch)
{
	const int level = GET_LEVEL(ch), threshold = tempest_takedown_threshold(level);
	const auto number_text = [](double value)
	{
		char text[32];
		snprintf(text, sizeof(text), "%.3g", value);
		return std::string(text);
	};
	const Range hit = { tempest_damage(lowest_rolls, level),
			    tempest_damage(highest_rolls, level) };
	const auto after = [&hit](double (*change)(double))
	{
		return show({ (int)tempest_area_damage(change(hit.low)),
			      (int)tempest_area_damage(change(hit.high)) });
	};
	std::string text = fact(
		"Cold damage",
		show({ (int)tempest_area_damage(hit.low), (int)tempest_area_damage(hit.high) }) +
			" to each target at your level, " + std::to_string(level));
	if (IS_PC(ch))
		text += fact("Against a player", after(tempest_player_damage));
	return text + fact("Against a flying target", after(tempest_flying_damage)) +
	       fact("With a wind tunnel in the room", after(tempest_wind_tunnel_damage)) +
	       fact("With a binding wind in the room", after(tempest_binding_wind_damage)) +
	       fact("Indoors", after(tempest_indoors_damage)) +
	       fact("Room-throw threshold", std::to_string(threshold) + " of a 0-100 roll") +
	       (threshold > 0 ?
			fact("It becomes if flying, or with a wind tunnel",
			     number_text(tempest_takedown_flying(threshold)) + ", " +
				     number_text(tempest_takedown_wind_tunnel(threshold))) +
				fact("With a binding wind, or indoors",
				     number_text(tempest_takedown_binding_wind(threshold)) + ", " +
					     number_text(tempest_takedown_indoors(threshold))) :
			std::string()) +
	       fact("Halved unless the target's luck over 10 reaches a roll of",
		    show({ tempest_luck_roll(lowest_rolls), tempest_luck_roll(highest_rolls) })) +
	       "  It needs an open exit in a random direction.\n" +
	       fact("A thrown target's lag", seconds(tempest_thrown_lag())) +
	       fact("Your lag", seconds(tempest_lag())) +
	       "  Safe rooms block it, and a crowd of players may not all be hit.\n"
	       "  Globes and spirit wards do not stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

// Frost Magus spec

void spell_single_tempest(int level, P_char ch, char * /*args*/, int /*type*/, P_char victim,
			  P_obj /*obj*/)
{
	double takedown_chance, dam;
	int door, target_room;

	struct damage_messages messages = {
		"$N&+W is savagely tossed about by the &+cfreezing &+Wsquall!",
		"&+WYou are savagely tossed around by the &+cfreezing &+Wsquall!",
		"$N&+W is savagely tossed around by the sudden and intense squall.",
		"$N&+W is shredded by &+Cicicles &+Wand violent wind!",
		"&+WYou feel so tired, &+wso very tired. &+LYou close your eyes...",
		"$N&+W is shredded and buffeted to death!",
		0
	};

	if (!IS_ALIVE(victim) || !IS_ALIVE(ch))
		return;

	dam = tempest_damage(live_rolls, level);

	/* Level 56 takedown_chance base % = 14% */
	takedown_chance = tempest_takedown_threshold(level);

	/* Flying around in a squall is a bad idea. */
	if (IS_AFFECTED(victim, AFF_FLY))
	{
		act("&+wFlying right now is a &+rbad idea...&n", FALSE, ch, 0, victim, TO_VICT);
		dam = tempest_flying_damage(dam);
		takedown_chance = tempest_takedown_flying(takedown_chance); // Level 56 % = 21%
	}

	/* Increase damage and takedown probability if wind tunnel is present. */
	if (get_spell_from_room(&world[ch->in_room], SPELL_WIND_TUNNEL))
	{
		dam = tempest_wind_tunnel_damage(dam);
		takedown_chance = tempest_takedown_wind_tunnel(takedown_chance); // Level 56 % = 27%
	}

	/*  Reduced damage and takedown probability if binding wind is present. */
	if (get_spell_from_room(&world[ch->in_room], SPELL_BINDING_WIND))
	{
		dam = tempest_binding_wind_damage(dam);
		takedown_chance = tempest_takedown_binding_wind(takedown_chance);
	}

	/* Indoors and non precipitation rooms are poor terrains. */
	if (world[ch->in_room].sector_type == SECT_INSIDE || IS_ROOM(ch->in_room, ROOM_INDOORS))
	{
		dam = tempest_indoors_damage(dam);
		takedown_chance = tempest_takedown_indoors(takedown_chance);
	}

	/* Victim might get lucky */
	if ((GET_C_LUK(victim) / 10) < tempest_luck_roll(live_rolls))
		takedown_chance = tempest_takedown_unlucky(takedown_chance);

	if (IS_PC(ch) && IS_PC(victim))
	{
		dam = tempest_player_damage(dam);
	}

	dam = tempest_area_damage(dam);

	if (spell_damage(ch, victim, dam, SPLDAM_COLD, SPLDAM_NODEFLECT, &messages) == DAM_NONEDEAD)
	{
		/* Room kick code from actoff.c
		 * Maximum probability is 27% for a room kick.*/
		if (takedown_chance > tempest_takedown_roll(live_rolls))
		{
			door = tempest_door_roll(live_rolls);
			if ((door == DIR_UP) || (door == DIR_DOWN))
				door = tempest_flat_door_roll(live_rolls);
			if ((CAN_GO(victim, door)) && (!check_wall(victim->in_room, door)))
			{
				act("&+LA mighty &+Wwind&+L sends&n $N &+Lflying out of the room!&n",
				    FALSE, ch, 0, victim, TO_CHAR);
				act("&+LA mighty &+Wwind&+L sends you flying out of the room!&n",
				    FALSE, ch, 0, victim, TO_VICT);
				act("&+LThe mighty &+Wwind&+L sends&n $N &+Lflying out of the room!&n",
				    FALSE, ch, 0, victim, TO_NOTVICT);
				target_room = world[victim->in_room].dir_option[door]->to_room;
				char_from_room(victim);
				if (char_to_room(victim, target_room, -1))
				{
					act("$n flies in looking slightly dazed!", TRUE, victim, 0,
					    0, TO_ROOM);
					CharWait(victim, tempest_thrown_lag());
				}
			}
		}
	}
}

void spell_tempest(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		   P_obj /*tar_obj*/)
{
	int room = ch->in_room;

	if (!IS_ALIVE(ch) || room == NOWHERE)
		return;

	act("&+yYou raise your hands to the sky calling on the winds of the north to send forth a &+cfreezing&+y squall!",
	    FALSE, ch, 0, 0, TO_CHAR);
	act("$n &+Wraises &+y$s hands to the sky calling forth a &+cfreezing &+ysquall.", FALSE, ch,
	    0, 0, TO_NOTVICT);

	cast_as_damage_area(ch, spell_single_tempest, level, victim,
			    get_property("spell.area.minChance.squallTempest", 90),
			    get_property("spell.area.chanceStep.squallTempest", 10));

	if (world[room].sector_type == SECT_INSIDE || IS_ROOM(room, ROOM_INDOORS))
		act("&+wYou have difficulty summoning the squall.&n", FALSE, ch, 0, victim,
		    TO_CHAR);

	zone_spellmessage(ch->in_room, FALSE, "&+wYou feel a bitterly &+Ccold&+w wisp of air.\r\n",
			  "&+wYou feel a bitterly &+Ccold&+w wisp of air from the %s.\r\n");

	CharWait(ch, tempest_lag());
}

static int wind_rage_duration(int level)
{
	return level / 3;
}

static int wind_rage_wisdom_max(int level)
{
	return level / 4;
}

// From this level windrage also shortens the spell pulse.
static bool wind_rage_quickens(int level)
{
	return level >= 51;
}

static int wind_rage_spell_pulse(int level)
{
	return (level >= 56) ? -2 : -1;
}

std::string wind_rage_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	std::string text =
		fact("Duration", game_hours(wind_rage_duration(level)) + " at your level, " +
					 std::to_string(level)) +
		fact("Maximum wisdom", "+" + std::to_string(wind_rage_wisdom_max(level)));
	if (wind_rage_quickens(level))
		text += fact("Spell pulse", std::to_string(wind_rage_spell_pulse(level)));
	return text;
}

void spell_wind_rage(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type, P_char victim,
		     P_obj /*tar_obj*/)
{
	if (affected_by_spell(ch, SPELL_WIND_RAGE))
	{
		send_to_char("&+cYou are already infused with the fury of the wind!\n", ch);
		return;
	}

	struct affected_type af;

	bzero(&af, sizeof(af));
	af.type = SPELL_WIND_RAGE;
	af.duration = wind_rage_duration(level);
	af.location = APPLY_WIS_MAX;
	af.modifier = wind_rage_wisdom_max(level);
	affect_to_char(victim, &af);
	if (wind_rage_quickens(level))
	{
		af.location = APPLY_SPELL_PULSE;
		af.modifier = wind_rage_spell_pulse(level);
		affect_to_char(victim, &af);
		send_to_char(
			"&+cYour mystic incantation bestows you with the &+Cspeed &+cand fury of the winds!\r\n",
			victim);
	}
	else
		send_to_char(
			"&+cYour mystic incantation bestows you with the fury of the winds!\r\n",
			victim);
}

static int ethereal_alliance_duration()
{
	return 32;
}

// What a hit on one ally passes to the other, and the change to the hit itself.
double ethereal_alliance_partner_damage(double damage)
{
	return damage * 0.5;
}

double ethereal_alliance_damage_mod()
{
	return -0.5;
}

std::string ethereal_alliance_facts(P_char /*ch*/)
{
	return fact("Duration", game_hours(ethereal_alliance_duration())) +
	       fact("Spell damage to either of you",
		    damage_change(1.0 + ethereal_alliance_damage_mod())) +
	       fact("Share of it the other ally takes",
		    std::to_string((int)(ethereal_alliance_partner_damage(1.0) * 100)) + "%") +
	       "  The player turns invisible while it lasts.\n"
	       "  Needs your ethereal form and another player's consent.\n";
}

// Windtalker spec

void spell_ethereal_alliance(int /*level*/, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			     P_char victim, P_obj /*tar_obj*/)
{
	struct affected_type af1, af2;

	bzero(&af1, sizeof(af1));
	bzero(&af2, sizeof(af2));

	af1.type = SPELL_ETHEREAL_ALLIANCE;

	if (!ch || !victim || ch == victim)
	{
		return;
	}

	if (IS_NPC(victim))
	{
		send_to_char("I don't think so.\n", ch);
		return;
	}

	if (!is_linked_to(ch, victim, LNK_CONSENT))
	{
		send_to_char("They won't appreciate it.\n", ch);
		return;
	}

	if (get_linked_char(ch, LNK_ETHEREAL) || get_linking_char(victim, LNK_ETHEREAL))
	{
		send_to_char("You already have an ethereal alliance.\n", ch);
		return;
	}

	if (!affected_by_spell(ch, SPELL_ETHEREAL_FORM))
	{
		send_to_char("You must be in ethereal form.\n", ch);
		return;
	}

	af1.type = SPELL_ETHEREAL_ALLIANCE;
	af1.duration = ethereal_alliance_duration();
	af1.bitvector5 = AFF5_ETHEREAL_ALLIANCE;

	// Removing phantasmal form and passdoor from target,
	// that's way too powerful for a basher/shreader.
	af2.type = SPELL_ETHEREAL_ALLIANCE;
	af2.duration = ethereal_alliance_duration();
	af2.bitvector = AFF_INVISIBLE;
	// af2.bitvector2 = AFF2_PASSDOOR;
	// af2.bitvector4 = AFF4_PHANTASMAL_FORM;
	af2.bitvector5 = AFF5_ETHEREAL_ALLIANCE;

	affect_to_char(victim, &af2);
	affect_to_char(ch, &af1);

	act("&+CYou form an ethereal connection with $N.", FALSE, ch, 0, victim, TO_CHAR);
	act("&+CYou form an ethereal connection with $n.", FALSE, ch, 0, victim, TO_VICT);

	link_char(ch, victim, LNK_ETHEREAL);
	return;
}

// Cosmomancer spec

static int comet_damage(const Rolls &rolls, int level)
{
	return rolls.dice(((int)(level / 3) + 5), 6) * 4;
}

// A star magus's comet.
static int comet_star_damage(const Rolls &rolls, int level)
{
	return rolls.dice(((int)(level / 3) + 5), 8) * 4 + 40;
}

static int comet_failed_save(int dam)
{
	return (int)(dam * 1.2);
}

std::string comet_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range hit = GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_STARMAGUS) ?
				  Range{ comet_star_damage(lowest_rolls, level),
					 comet_star_damage(highest_rolls, level) } :
				  Range{ comet_damage(lowest_rolls, level),
					 comet_damage(highest_rolls, level) };
	return fact("Damage", show(hit) + " at your level, " + std::to_string(level)) +
	       fact("If the target fails its save",
		    show({ comet_failed_save(hit.low), comet_failed_save(hit.high) })) +
	       "  Globes and spirit wards do not stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_comet(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		 P_obj /*tar_obj*/)
{
	int dam;
	struct damage_messages messages = {
		"&+LYou open a rift in the &+Yco&+Wsm&+Yos&+L and call forth a small &+Yco&+yme&+Yt&+L that &+Rsm&+ras&+Rhes &+Linto $N&+L!&n",
		"&+LA rift opens in front of you, and in it you see &+Yst&+War&+Ys &+Land &+Cgalaxies&+L.  Suddenly, a &+Yco&+yme&+Yt &+Lflies out of it &+Rsm&+rash&+Ring &+Linto YOU!&n",
		"&+LA large rift opens in front of $N&+L, you see &+Yst&+War&+Ys &+Lthrough it, and then a &+Yco&+yme&+Yt &+Lflies forth &+Rsmashing &+Linto $M!&n",
		"&+LYou open a rift into space and call forth a comet, and an exceptionally &+RLARGE &+Yco&+yme&+Yt &+Lsails through the rift and through the &+rrem&+Rnan&+rts &+Lof $N&+L.&n",
		"&+LA black rift opens before you, showing you &+Yst&+yar&+Ys&+L.  Suddenly a &+Rmassive &+Yco&+yme&+Yt &+Lflies through it and you...ending your &+Rl&+rif&+Re&+L...&n",
		"&+LA black rift opens before $N &+Land out comes a &+RMASSIVE &+Yco&+yme&+Yt &+Lutterly &+Rpul&+rver&+Rizi&+rng &+L$M!&n",
		0
	};

	if (!GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_STARMAGUS))
	{
		// Fireball damage.
		dam = comet_damage(live_rolls, level);
	}
	else
	{
		// A little more than fireball damage (d8 instead of d6 and + 10 dam).
		dam = comet_star_damage(live_rolls, level);
	}

	int mod = get_default_save_mod(victim, ch, SAVING_SPELL, SPELL_COMET);
	if (!NewSaves(victim, SAVING_SPELL, mod))
	{
		dam = comet_failed_save(dam);
	}

	spell_damage(ch, victim, (int)dam, SPLDAM_GENERIC, 0, &messages);
}

// Cosmic vacuum and supernova's burn: they work when number(1, 100) is below this.
static int cosmic_success_chance(int level, int victim_level)
{
	return BOUNDED(50, 70 + level - victim_level, 80);
}

static int cosmic_success_roll(const Rolls &rolls)
{
	return rolls.number(1, 100);
}

// A level this far above or below the target's reaches the chance's bounds.
static std::string cosmic_success_page()
{
	return show({ cosmic_success_chance(0, 100) - 1, cosmic_success_chance(100, 0) - 1 }) +
	       "%, higher the more you outlevel the target";
}

// The pulses a saving target suffers it, and the ticks a failing one does.
static int cosmic_saved_duration(int level)
{
	return level / 3 * WAIT_SEC;
}

static int cosmic_failed_duration(int level)
{
	return level / 10;
}

// Armor class worsens by the cast level, stopping at 100.
static int cosmic_vacuum_ac(int level, int victim_ac)
{
	return (victim_ac + level) > 100 ? 100 - victim_ac : level;
}

// APPLY_CURSE adds its size to the target's saves, whatever its sign.
static int cosmic_vacuum_curse(int level)
{
	return level / 5 - 2;
}

std::string cosmic_vacuum_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	return fact("Chance to work", cosmic_success_page()) +
	       fact("Lasts if the target saves", seconds(cosmic_saved_duration(level))) +
	       fact("Lasts if it fails", game_hours(cosmic_failed_duration(level))) +
	       fact("Armor class", std::to_string(cosmic_vacuum_ac(level, 0)) +
					   " worse at your level, " + std::to_string(level) +
					   ", at most to 100") +
	       fact("All saving throws",
		    std::to_string(std::abs(cosmic_vacuum_curse(level))) + " worse") +
	       "  It can be shrugged, and does nothing to a target that has it.\n";
}

void spell_cosmic_vacuum(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			 P_char victim, P_obj /*tar_obj*/)
{
	int success_chance;
	struct affected_type af;

	if (affected_by_spell(victim, SPELL_COSMIC_VACUUM))
	{
		send_to_char("&+cThey are already affected by a cosmic vacuum!\r\n", ch);
		return;
	}
	else if (resists_spell(ch, victim))
	{
		return;
	}

	success_chance = cosmic_success_chance(GET_LEVEL(ch), GET_LEVEL(victim));
	if (success_chance <= cosmic_success_roll(live_rolls))
	{
		return;
	}

	memset(&af, 0, sizeof(af));

	int mod = get_default_save_mod(victim, ch, SAVING_SPELL, SPELL_COSMIC_VACUUM);
	if (NewSaves(victim, SAVING_SPELL, mod))
	{
		af.flags = AFFTYPE_SHORT;
		// Saved -> 1/3 level seconds
		af.duration = cosmic_saved_duration(level);
	}
	else
	{
		// Failed save -> level / 10 minutes.
		af.duration = cosmic_failed_duration(level);
	}

	af.type = SPELL_COSMIC_VACUUM;
	// Set AC to 100 if AC + level goes over 100.
	af.modifier = cosmic_vacuum_ac(level, GET_AC(victim));
	af.location = APPLY_AC;
	affect_to_char(victim, &af);

	// At level 55, it's 11-2=9 points vs curse at 10 points max for PC.
	// At level 60, it's the same as curse.  Requires item/NPC.
	af.modifier = cosmic_vacuum_curse(level);
	af.location = APPLY_CURSE;
	affect_to_char(victim, &af);

	act("&+LYou invoke &+Yco&+Wsm&+Yic&+L forces, opening a rift in space and creating a vacuum next to&n $N.",
	    TRUE, ch, 0, victim, TO_CHAR);
	act("&+wThe &+Yco&+Wsm&+Yic &+Lvacuum's &+wpowerful force leaves you temporarily defenseless.",
	    TRUE, ch, 0, victim, TO_VICT);
	act("$n &+wopens a &+Yco&+Wsm&+Yic&+L vacuum &+wby&n $N&+w, draining $M&+w of $S&+w defenses.",
	    TRUE, ch, 0, victim, TO_NOTVICT);

	DamageStuff(victim, SPLDAM_NEGATIVE);
}

static int supernova_damage(const Rolls &rolls, int level)
{
	return 120 + level * 6 + rolls.number(1, 40);
}

static int supernova_player_damage(int dam)
{
	return dam * get_property("spell.area.damage.to.pc", 0.5);
}

static int supernova_area_damage(int dam)
{
	return dam * get_property("spell.area.damage.factor.superNova", 1.000);
}

static int supernova_constitution(int level)
{
	return level / -10;
}

// The caster's brief knockout, rounded up to one pulse.
static int supernova_knockout()
{
	return MAX(1, WAIT_SEC / 10);
}

std::string supernova_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range hit = { supernova_damage(lowest_rolls, level),
			    supernova_damage(highest_rolls, level) };
	std::string text =
		fact("Damage",
		     show({ supernova_area_damage(hit.low), supernova_area_damage(hit.high) }) +
			     " to each target at your level, " + std::to_string(level));
	if (IS_PC(ch))
		text += fact("Against a player",
			     show({ supernova_area_damage(supernova_player_damage(hit.low)),
				    supernova_area_damage(supernova_player_damage(hit.high)) }));
	return text + fact("Chance a survivor also burns", cosmic_success_page()) +
	       fact("Its constitution", std::to_string(supernova_constitution(level))) +
	       fact("Lasts if it saves", seconds(cosmic_saved_duration(level))) +
	       fact("Lasts if it fails", game_hours(cosmic_failed_duration(level))) +
	       fact("You are then knocked out", seconds(supernova_knockout()) + ", left prone") +
	       "  Safe rooms block it, and a crowd of players may not all be hit.\n"
	       "  You must be outside to cast it, not indoors or underground.\n"
	       "  Globes and spirit wards do not stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_single_supernova(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			    P_char victim, P_obj /*tar_obj*/)
{
	int dam;
	struct affected_type af;
	struct damage_messages messages = {
		"&+LYou blast&n $N &+Lwith &+Yco&+Wsm&+Yic &+Lenergies!",
		"$n &+Lblasts you with &+Yco&+Wsm&+Yic &+Lenergies, stunning you!",
		"$n &+Rblasts&n $N&+w with &+Yco&+Wsm&+Yic&+L energies!",
		"$N is &+Rblasted&n by your focused energies!",
		"&+LYou are sent reeling by&n $n's &+Lcosmic energies!",
		"$n &+Gvaporizes&n $N to nothing with $s &+Yco&+Wsm&+Yic &+Lenergies!",
		0
	};

	dam = supernova_damage(live_rolls, level);
	if (IS_PC(ch) && IS_PC(victim))
	{
		dam = supernova_player_damage(dam);
	}
	dam = supernova_area_damage(dam);
	if (spell_damage(ch, victim, dam, SPLDAM_GENERIC, 0, &messages))
		return;

	if (affected_by_spell(victim, SPELL_SUPERNOVA))
	{
		return;
	}

	int success_chance = cosmic_success_chance(GET_LEVEL(ch), GET_LEVEL(victim));
	if (success_chance <= cosmic_success_roll(live_rolls))
		return;

	memset(&af, 0, sizeof(af));

	int mod = get_default_save_mod(victim, ch, SAVING_SPELL, SPELL_SUPERNOVA);
	if (NewSaves(victim, SAVING_SPELL, mod))
	{
		af.flags = AFFTYPE_SHORT;
		af.duration = cosmic_saved_duration(level);
	}
	else
	{
		af.duration = cosmic_failed_duration(level);
	}

	af.type = SPELL_SUPERNOVA;
	af.modifier = supernova_constitution(level);
	af.location = APPLY_CON;
	affect_to_char(victim, &af);

	act("&+LYou are &+Yburnt &+Lby the &+Yco&+Wsm&+Yic &+Lenergies!", TRUE, ch, 0, victim,
	    TO_VICT);
}

void spell_supernova(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		     P_obj /*tar_obj*/)
{
	int room;

	room = ch->in_room;

	if (!OUTSIDE(ch))
	{
		send_to_char("You must be outside to cast this spell!\n", ch);
		return;
	}

	act("&+LThrough your &+Yco&+Wsm&+Yic &+Lmanipulations you channel the powers of a distant &+Ynova &+Lright onto the battlefield!",
	    FALSE, ch, 0, 0, TO_CHAR);
	act("$n &+Lchannels the powers of a distant &+Ynova &+Lright onto the battlefield!", FALSE,
	    ch, 0, 0, TO_ROOM);

	zone_spellmessage(
		ch->in_room, FALSE,
		"&n&+cThe He&+Wav&n&+cens themselves &-L&+Yflash&n&+c as a &+YSupernova&n&+c is unleashed nearby!&n\r\n",
		"&n&+cThe He&+Wav&n&+cens to the %s &-L&+Yflash&n&+c as a &+YSupernova&n&+c is unleashed nearby!&n\r\n");
	cast_as_damage_area(ch, spell_single_supernova, level, victim,
			    get_property("spell.area.minChance.superNova", 50),
			    get_property("spell.area.chanceStep.superNova", 10));

	if (!is_char_in_room(ch, room))
		return;

	act("&+LExhausted, $n passes out!", FALSE, ch, 0, 0, TO_ROOM);
	send_to_char("&+LExhausted, you pass out!\r\n", ch);
	KnockOut(ch, supernova_knockout());
}

// Damage for each spell stripped from a target.
static int ethereal_discharge_damage(int level, P_char ch)
{
	return (int)((level + GET_CHAR_SKILL(ch, SKILL_DEVOTION) / 5) / 2);
}

// Added to the target's save; higher is harder.
static int ethereal_discharge_save_mod(int level, int victim_level, int devotion)
{
	return (MAX(0, level - victim_level) + (int)(devotion / 25));
}

// A roll of 0 strips a spell even after a successful save.
static int ethereal_discharge_strip_roll(const Rolls &rolls)
{
	return rolls.number(0, 9);
}

std::string ethereal_discharge_facts(P_char ch)
{
	const int dam = ethereal_discharge_damage(GET_LEVEL(ch), ch);
	const int mod = ethereal_discharge_save_mod(0, 0, GET_CHAR_SKILL(ch, SKILL_DEVOTION));
	const int outcomes = ethereal_discharge_strip_roll(highest_rolls) -
			     ethereal_discharge_strip_roll(lowest_rolls) + 1;
	return fact("Damage per spell stripped", show_landing({ dam, dam })) +
	       fact("Save against each strip",
		    "+" + std::to_string(mod) + " with your devotion, harder") +
	       "  Each level you have above your target makes it 1 harder.\n" +
	       fact("Stripped despite the save", "1 in " + std::to_string(outcomes)) +
	       "  It uses up your ethereal form and hits all but your group here.\n"
	       "  It cannot kill or be shrugged; globes and wards do not stop it.\n";
}

void spell_ethereal_discharge(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			      P_char /*victim*/, P_obj /*tar_obj*/)
{
	int dam, mod;
	P_char tch, next_tch;
	struct affected_type *afp, *next_afp;
	struct damage_messages messages = {
		"$N&+L is sent reeling by the shockwave of your expelled e&+ct&+Ch&+ce&+Lreal energy!&n",
		"&n&+LThe e&+ct&+Ch&+ce&+Lreal shockwave from&n $n&+L slams into you with violent force!&n",
		"$n&+L sends&n $N&+L reeling with the e&+ct&+Ch&+ce&+Lreal shockwave!&n",
		"$N&+L is blasted by your shockwave!&n",
		"&n&+LA fierce shockwave of e&+ct&+Ch&+ce&+Lreal magic slams into you!&n",
		"$N&+L is overwhelmed by the e&+ct&+Ch&+ce&+Lreal shockwave, and collapses, d&+Ce&+Lad.&n",
		0
	};

	// An area cast arrives with no target; every victim comes from the room.
	if (!ch || !IS_ALIVE(ch))
	{
		return;
	}

	if (!(afp = get_spell_from_char(ch, SPELL_ETHEREAL_FORM)))
	{
		send_to_char("&+LYou must be in et&+ch&+Ce&+cr&+Leal form.\n", ch);
		return;
	}

	act("&+LYou summon your internal e&+ct&+Ch&+ce&+Lreal energies and force them outwards &+Lv&+ci&+Co&+cl&+Lently.&n",
	    FALSE, ch, 0, 0, TO_CHAR);
	act("$n &+Lreleases an e&+ct&+Ch&+ce&+Lreal shockwave!&n", FALSE, ch, 0, 0, TO_ROOM);

	dam = ethereal_discharge_damage(level, ch);

	wear_off_message(ch, afp);
	affect_remove(ch, afp);

	for (tch = world[ch->in_room].people; tch; tch = next_tch)
	{
		next_tch = tch->next_in_room;

		if (!should_area_hit(ch, tch))
			continue;

		mod = ethereal_discharge_save_mod(GET_LEVEL(ch), GET_LEVEL(tch),
						  GET_CHAR_SKILL(ch, SKILL_DEVOTION));

		// Damage can remove affects itself, so finish walking the list first.
		int strips = 0;
		for (afp = tch->affected; afp; afp = next_afp)
		{
			next_afp = afp->next;

			if (!(afp->flags & AFFTYPE_NODISPEL) && (afp->type > 0))
			{
				if (!NewSaves(tch, SAVING_SPELL, mod) ||
				    !ethereal_discharge_strip_roll(live_rolls))
				{
					wear_off_message(tch, afp);
					affect_remove(tch, afp);
					strips++;
				}
			}
		}

		for (; strips > 0; strips--)
		{
			const int result = spell_damage(ch, tch, dam, SPLDAM_GENERIC,
							RAWDAM_NOKILL | SPLDAM_NOSHRUG, &messages);
			if (result == DAM_CHARDEAD || result == DAM_BOTHDEAD)
				return;
			if (result != DAM_NONEDEAD)
				break;
		}
	}
}

// Each result rolls afresh, and is reached only if the ones before it were not.
static int planetary_alignment_roll(const Rolls &rolls)
{
	return rolls.number(0, 100);
}

static int planetary_alignment_perfect_chance()
{
	return 11;
}

static int planetary_alignment_strong_chance()
{
	return 31;
}

static int planetary_alignment_partial_chance()
{
	return 51;
}

static int planetary_alignment_nudge_chance()
{
	return 80;
}

// The two stronger results raise maximum stats and last longer.
static int planetary_alignment_long_duration(int level)
{
	return level / 4;
}

static int planetary_alignment_short_duration(int level)
{
	return level / 5;
}

static int planetary_alignment_perfect_modifier()
{
	return 15;
}

static int planetary_alignment_strong_modifier()
{
	return 10;
}

static int planetary_alignment_partial_modifier()
{
	return 10;
}

static int planetary_alignment_nudge_modifier()
{
	return 5;
}

// Pulses before it can be cast again.
static int planetary_alignment_rest()
{
	return get_property("timer.mins.planetaryAlignment", 3) * WAIT_MIN;
}

std::string planetary_alignment_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const std::string outcomes =
		" in " + std::to_string(planetary_alignment_roll(highest_rolls) -
					planetary_alignment_roll(lowest_rolls) + 1);
	return fact("First roll, " + std::to_string(planetary_alignment_perfect_chance()) +
			    outcomes,
		    "all maximum stats +" +
			    std::to_string(planetary_alignment_perfect_modifier())) +
	       fact("Else " + std::to_string(planetary_alignment_strong_chance()) + outcomes,
		    "all maximum stats +" + std::to_string(planetary_alignment_strong_modifier())) +
	       fact("Maximum stats last", game_hours(planetary_alignment_long_duration(level))) +
	       fact("Else " + std::to_string(planetary_alignment_partial_chance()) + outcomes,
		    "all stats +" + std::to_string(planetary_alignment_partial_modifier())) +
	       fact("Else " + std::to_string(planetary_alignment_nudge_chance()) + outcomes,
		    "all stats +" + std::to_string(planetary_alignment_nudge_modifier())) +
	       fact("Stats last", game_hours(planetary_alignment_short_duration(level))) +
	       "  Otherwise it fails.\n" +
	       fact("Rest between casts", real_time(planetary_alignment_rest()));
}

void spell_planetary_alignment(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			       P_char victim, P_obj /*tar_obj*/)
{
	struct affected_type af;

	if (affected_by_spell(ch, SPELL_PLANETARY_ALIGNMENT))
	{
		send_to_char("&+LNothing seems to ha&+Cp&+Lpen.&n\n", ch);
		return;
	}

	if (!affect_timer(ch, planetary_alignment_rest(), SPELL_PLANETARY_ALIGNMENT))
	{
		send_to_char("&+LYou are too tired to align celestial bodies.&n\n", ch);
		return;
	}

	act("&+LYou communicate to the &+Yco&+Wsm&+Yos&n&+L, reaching out mentally to the planets and moons...&n",
	    FALSE, ch, 0, 0, TO_CHAR);
	act("$n &+Lgazes upwards towards the &+Yco&+Wsm&+Yos&n&+L and strains for control.&n",
	    FALSE, ch, 0, 0, TO_ROOM);

	memset(&af, 0, sizeof(af));

	if (planetary_alignment_roll(live_rolls) < planetary_alignment_perfect_chance())
	{
		af.type = SPELL_PLANETARY_ALIGNMENT;
		af.duration = planetary_alignment_long_duration(level);

		af.location = APPLY_STR_MAX;
		af.modifier = planetary_alignment_perfect_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_DEX_MAX;
		af.modifier = planetary_alignment_perfect_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_AGI_MAX;
		af.modifier = planetary_alignment_perfect_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_CON_MAX;
		af.modifier = planetary_alignment_perfect_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_INT_MAX;
		af.modifier = planetary_alignment_perfect_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_WIS_MAX;
		af.modifier = planetary_alignment_perfect_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_POW_MAX;
		af.modifier = planetary_alignment_perfect_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_CHA_MAX;
		af.modifier = planetary_alignment_perfect_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_LUCK_MAX;
		af.modifier = planetary_alignment_perfect_modifier();
		affect_to_char(victim, &af);

		act("&+Land succeed in pulling them into alignment...&n", FALSE, ch, 0, 0, TO_CHAR);
		act("&+Lso perfectly that energies strengthen you immensely...&n", FALSE, ch, 0, 0,
		    TO_CHAR);
		act("&+LYou are bathed in &+Yco&+Wsm&+Yic&n&+L power, which strengthening every part of you.&n",
		    FALSE, ch, 0, 0, TO_CHAR);
	}
	else if (planetary_alignment_roll(live_rolls) < planetary_alignment_strong_chance())
	{
		af.type = SPELL_PLANETARY_ALIGNMENT;
		af.duration = planetary_alignment_long_duration(level);

		af.location = APPLY_STR_MAX;
		af.modifier = planetary_alignment_strong_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_DEX_MAX;
		af.modifier = planetary_alignment_strong_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_AGI_MAX;
		af.modifier = planetary_alignment_strong_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_CON_MAX;
		af.modifier = planetary_alignment_strong_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_INT_MAX;
		af.modifier = planetary_alignment_strong_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_WIS_MAX;
		af.modifier = planetary_alignment_strong_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_POW_MAX;
		af.modifier = planetary_alignment_strong_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_CHA_MAX;
		af.modifier = planetary_alignment_strong_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_LUCK_MAX;
		af.modifier = planetary_alignment_strong_modifier();
		affect_to_char(victim, &af);

		act("&+Land succeed in pulling them into alignment...&n", FALSE, ch, 0, 0, TO_CHAR);
		act("&+LYou are bathed in &+Yco&+Wsm&+Yic&n&+L power, strengthening every part of you.&n",
		    FALSE, ch, 0, 0, TO_CHAR);
	}
	else if (planetary_alignment_roll(live_rolls) < planetary_alignment_partial_chance())
	{
		af.type = SPELL_PLANETARY_ALIGNMENT;
		af.duration = planetary_alignment_short_duration(level);
		af.modifier = planetary_alignment_partial_modifier();

		af.location = APPLY_STR;
		affect_to_char(victim, &af);

		af.location = APPLY_DEX;
		affect_to_char(victim, &af);

		af.location = APPLY_AGI;
		affect_to_char(victim, &af);

		af.location = APPLY_CON;
		affect_to_char(victim, &af);

		af.location = APPLY_INT;
		affect_to_char(victim, &af);

		af.location = APPLY_WIS;
		affect_to_char(victim, &af);

		af.location = APPLY_POW;
		affect_to_char(victim, &af);

		af.location = APPLY_CHA;
		affect_to_char(victim, &af);

		af.location = APPLY_LUCK;
		affect_to_char(victim, &af);

		act("&+Land partially pulling them into alignment...&n", FALSE, ch, 0, 0, TO_CHAR);
		act("&+LYou are warmed by the &+Yco&+Wsm&+Yic&n&+L power.&n", FALSE, ch, 0, 0,
		    TO_CHAR);
	}
	else if (planetary_alignment_roll(live_rolls) < planetary_alignment_nudge_chance())
	{
		af.type = SPELL_PLANETARY_ALIGNMENT;
		af.duration = planetary_alignment_short_duration(level);

		af.location = APPLY_STR;
		af.modifier = planetary_alignment_nudge_modifier();
		affect_to_char(victim, &af);

		af.location = APPLY_DEX;
		affect_to_char(victim, &af);

		af.location = APPLY_AGI;
		affect_to_char(victim, &af);

		af.location = APPLY_CON;
		affect_to_char(victim, &af);

		af.location = APPLY_INT;
		affect_to_char(victim, &af);

		af.location = APPLY_WIS;
		affect_to_char(victim, &af);

		af.location = APPLY_POW;
		affect_to_char(victim, &af);

		af.location = APPLY_CHA;
		affect_to_char(victim, &af);

		af.location = APPLY_LUCK;
		affect_to_char(victim, &af);

		act("&+Land nudge into alignment...&n", FALSE, ch, 0, 0, TO_CHAR);
		act("&+LThe &+Yco&+Wsm&+Yic&n&+L power brushes you.&n", FALSE, ch, 0, 0, TO_CHAR);
	}
	else
	{
		act("&n&+LYet you fail to bring them under your control.&n", FALSE, ch, 0, 0,
		    TO_CHAR);
	}
}

static int polar_vortex_damage(const Rolls &rolls, int level)
{
	return rolls.dice(level, 6) * 3;
}

static int polar_vortex_player_damage(int dam)
{
	return dam * get_property("spell.area.damage.to.pc", 0.5);
}

static int polar_vortex_area_damage(int dam)
{
	return dam * get_property("spell.area.damage.factor.polarVortex", 1.000);
}

// Added to the paralysis save; higher is harder. A thrikreen also rolls a plain one.
static int polar_vortex_save_mod()
{
	return 2;
}

// The paralysis lasts this many pulses.
static int polar_vortex_paralysis(const Rolls &rolls)
{
	return WAIT_SEC * rolls.number(1, 3);
}

std::string polar_vortex_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range hit = { polar_vortex_damage(lowest_rolls, level),
			    polar_vortex_damage(highest_rolls, level) };
	std::string text = fact(
		"Cold damage",
		show({ polar_vortex_area_damage(hit.low), polar_vortex_area_damage(hit.high) }) +
			" to each target at your level, " + std::to_string(level));
	if (IS_PC(ch))
		text += fact(
			"Against a player",
			show({ polar_vortex_area_damage(polar_vortex_player_damage(hit.low)),
			       polar_vortex_area_damage(polar_vortex_player_damage(hit.high)) }));
	return text +
	       fact("Major paralysis first",
		    seconds(polar_vortex_paralysis(lowest_rolls)) + " to " +
			    seconds(polar_vortex_paralysis(highest_rolls))) +
	       fact("Its paralysis save",
		    "+" + std::to_string(polar_vortex_save_mod()) + ", harder") +
	       "  Cold shield stops it, except on thrikreen, who also risk a plain save.\n"
	       "  Freedom of movement can stop it too.\n"
	       "  Safe rooms block it, and a crowd of players may not all be hit.\n"
	       "  Globes and spirit wards do not stop the damage.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_single_polar_vortex(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			       P_char victim, P_obj /*obj*/)
{
	struct damage_messages messages = {
		"$N&+C is horrendously battered by the intense vortex!&n",
		"$n's &+Cchilling vortex encases you in a sheet of &+Bice&+C!&n",
		"$n&+C's chilling vortex encases&n $N&+C in a sheet of &+Bice&+C, causing $M to scream in pain!&n",
		"&+CYour polar vortex is too much for&n $N&+C, and $E gives up the fight for good.&n",
		"&+CYou are encased in a solid block of ice, and then the world fades to black...&n",
		"$N&+C is frozen solid! Where's Boba Fett?&n",
		0
	};

	int dam = polar_vortex_damage(live_rolls, level);
	if (IS_PC(ch) && IS_PC(victim))
		dam = polar_vortex_player_damage(dam);
	dam = polar_vortex_area_damage(dam);

	if (((!IS_AFFECTED3(victim, AFF3_COLDSHIELD) &&
	      !NewSaves(victim, SAVING_PARA, polar_vortex_save_mod())) ||
	     (GET_RACE(victim) == RACE_THRIKREEN && !NewSaves(victim, SAVING_PARA, 0))) &&
	    !check_freedom_of_movement(victim))
	{
		struct affected_type af;

		send_to_char("&+CThe intense cold causes your entire body to freeze!\n", victim);
		act("&+CThe intense cold causes $n&+C's entire body to freeze!", FALSE, victim, 0,
		    0, TO_ROOM);
		act("$n &+Mceases to move.. still and lifeless.", FALSE, victim, 0, 0, TO_ROOM);
		send_to_char("&+LYour body becomes like stone as the paralyzing takes effect.\n",
			     victim);

		bzero(&af, sizeof(af));
		af.type = SPELL_MAJOR_PARALYSIS;
		af.flags = AFFTYPE_SHORT;
		af.duration = polar_vortex_paralysis(live_rolls);
		af.bitvector2 = AFF2_MAJOR_PARALYSIS;

		affect_to_char(victim, &af);

		if (IS_FIGHTING(victim))
			stop_fighting(victim);
	}

	send_to_char("&+CYou find no shelter from the savage vortex!&n\n", victim);
	spell_damage(ch, victim, dam, SPLDAM_COLD, 0, &messages);
}

void spell_polar_vortex(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			P_obj /*obj*/)
{
	if (victim == ch)
	{
		send_to_char("You suddenly decide against that, oddly enough.\n", ch);
		return;
	}

	send_to_char(
		"&+WYou call upon the chilling winds of the north, summoning a mighty storm!&n\n",
		ch);
	act("&+WThe wind in the room starts to pick up, as&n $n&+W completes $s incantation.&n",
	    FALSE, ch, 0, 0, TO_ROOM);

	cast_as_damage_area(ch, spell_single_polar_vortex, level, victim,
			    get_property("spell.area.minChance.polarVortex", 50),
			    get_property("spell.area.chanceStep.polarVortex", 20));

	zone_spellmessage(
		ch->in_room, FALSE,
		"&+CA blast of &+cfreezing &+Cair swirls violently through the area.\r\n",
		"&+CA blast of &+cfreezing &+Cair from the %s swirls violently through the area.\r\n");
}

// The lag of a grouped caster and of each group member moved; a lone caster has none.
static double ethereal_travel_caster_lag()
{
	return 2.5 * PULSE_VIOLENCE;
}

static int ethereal_travel_member_lag()
{
	return 2 * PULSE_VIOLENCE;
}

std::string ethereal_travel_facts(P_char /*ch*/)
{
	return fact("Your lag in a group", seconds((int)ethereal_travel_caster_lag())) +
	       fact("Lag of each group member moved", seconds(ethereal_travel_member_lag())) +
	       "  Travelling alone has no lag.\n"
	       "  It moves your group in the room to another player.\n"
	       "  No-teleport rooms, hometowns and ocean block it.\n"
	       "  You and the target must be raidable.\n";
}

void spell_ethereal_travel(int /*level*/, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			   P_obj /*obj*/)
{
	int from_room;
	int location;
	struct group_list *gl = 0;

	location = victim->in_room;

	if (IS_ROOM(ch->in_room, ROOM_NO_TELEPORT) || IS_HOMETOWN(ch->in_room))
	{
		send_to_char("The magic in this room prevents you from leaving.\n", ch);
		return;
	}

	if (world[ch->in_room].sector_type == SECT_OCEAN)
	{
		send_to_char("Yeah, break out the bathing suit and...idiot.\n", ch);
		return;
	}

	if (IS_NPC(victim) || (victim == ch))
	{
		send_to_char("Can only travel to another player.\n", ch);
		return;
	}
	if (IS_PC_PET(ch) && IS_PC(victim))
	{
		send_to_char("won't work.\n", ch);
		return;
	}
	if (IS_ROOM(location, ROOM_NO_TELEPORT) || IS_HOMETOWN(location))
	{
		send_to_char("The magic in that room prevents you from entering.\n", ch);
		return;
	}

	if ((ch && !is_Raidable(ch, 0, 0)) || (victim && !is_Raidable(victim, 0, 0)))
	{
		send_to_char("&+WYou or your target is not raidable. The spell fails!\r\n", ch);
		return;
	}

	// get the room the teleport is taking place so we don't have to move the teleporter last
	from_room = ch->in_room;

	// if the teleporter is grouped
	if (ch->group)
	{
		// teleport the group members in the character's room
		for (gl = ch->group; gl; gl = gl->next)
		{
			if (gl->ch->in_room == from_room)
			{
				// show the room they're fading
				act("$n&+W slowly fades into the ethereal mists.&n", FALSE, gl->ch,
				    0, 0, TO_ROOM);

				// if they're fighting, break it up
				if (IS_FIGHTING(gl->ch))
					stop_fighting(gl->ch);

				// move the char
				char_from_room(gl->ch);
				char_to_room(gl->ch, location, -1);

				// show the new room they've arrived
				act("&+WA HUGE ethereal portal opens up, and&n $n&+W emerges from the mists!&n",
				    FALSE, gl->ch, 0, 0, TO_ROOM);
				CharWait(gl->ch, ethereal_travel_member_lag());
			}
			CharWait(ch, ethereal_travel_caster_lag());
		}
	}
	else
	{
		// show the room they're fading
		act("$n&+W slowly fades into the ethereal mists.&n", FALSE, ch, 0, 0, TO_ROOM);

		// if they're fighting, break it up
		if (IS_FIGHTING(ch))
			stop_fighting(ch);

#if defined(CTF_MUD) && (CTF_MUD == 1)
		if (ctf_carrying_flag(ch) == CTF_PRIMARY)
		{
			send_to_char("You can't carry that with you.\r\n", ch);
			drop_ctf_flag(ch);
		}
#endif

		// move the char
		char_from_room(ch);
		char_to_room(ch, location, -1);

		// show the new room they've arrived
		act("&+WA HUGE ethereal portal opens up, and&n $n&+W emerges from the mists!&n",
		    FALSE, ch, 0, 0, TO_ROOM);
	}
}

// The rift's strength does not depend on the caster.
static int cosmic_rift_damage(const Rolls &rolls)
{
	return rolls.dice(rolls.number(25, 75), 4) * 4;
}

static int cosmic_rift_player_damage(int dam)
{
	return dam * get_property("spell.area.damage.to.pc", 0.5);
}

static int cosmic_rift_area_damage(int dam)
{
	return dam * get_property("spell.area.damage.factor.cosmicRift", 1.000);
}

// Where a corpse goes.
static int cosmic_rift_astral_room(const Rolls &rolls)
{
	return rolls.number(ASTRAL_VNUM_BEGIN, ASTRAL_VNUM_END);
}

// A target with fewer hit points than this dies outright.
static int cosmic_rift_kill_threshold(int dam)
{
	return dam / 4;
}

std::string cosmic_rift_facts(P_char ch)
{
	const Range hit = { cosmic_rift_area_damage(cosmic_rift_damage(lowest_rolls)),
			    cosmic_rift_area_damage(cosmic_rift_damage(highest_rolls)) };
	std::string text = fact("Damage", show(hit) + " to each target");
	if (IS_PC(ch))
	{
		const Range player = { cosmic_rift_area_damage(cosmic_rift_player_damage(
					       cosmic_rift_damage(lowest_rolls))),
				       cosmic_rift_area_damage(cosmic_rift_player_damage(
					       cosmic_rift_damage(highest_rolls))) };
		text += fact("Against a player", show(player));
	}
	return text +
	       fact("Dies outright below", show({ cosmic_rift_kill_threshold(hit.low),
						  cosmic_rift_kill_threshold(hit.high) }) +
						   " hit points, a quarter of its damage") +
	       "  Corpses of those it kills go to the astral plane.\n"
	       "  Safe rooms block it, and a crowd of players may not all be hit.\n"
	       "  Globes and spirit wards stop neither.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_single_cosmic_rift(int /*level*/, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			      P_char victim, P_obj /*obj*/)
{
	struct damage_messages messages = {
		"&+LThe cosmic rift bends the fabric space and time around&n $N&+L, causing $M extreme pain!&n",
		"&+LTime seems to come to a stop, and as it resumes, you a filled with sheer &+RPAIN&+L!&n",
		"$N&+L is nearly consumed by the black hole!&n",
		"$N&+L tries to resist the power of your cosmic rift, but alas, $E succumbs to it's might.&n",
		"&+LThe cosmic rift is too much, and you feel yourself being swallowed whole by it...&n",
		"$N&+L is consumed completely by the cosmic rift!&n",
		0
	};
	int dam = cosmic_rift_damage(live_rolls);
	if (IS_PC(ch) && IS_PC(victim))
		dam = cosmic_rift_player_damage(dam);
	dam = cosmic_rift_area_damage(dam);

	if (GET_HIT(victim) < cosmic_rift_kill_threshold(dam))
	{
		int id = -1;

		if (IS_PC(victim))
			id = GET_PID(victim);
		else
			id = GET_VNUM(victim);

		act("$N &+Ltries to resist the power of your cosmic rift, but alas, $E succumbs to it's might.&n",
		    FALSE, ch, 0, victim, TO_CHAR);
		act("&+LThe cosmic rift is too much, and you feel yourself being swallowed whole by it...&n",
		    FALSE, ch, 0, victim, TO_VICT);
		act("$N&+L is consumed completely by the cosmic rift!&n", FALSE, ch, 0, victim,
		    TO_NOTVICT);

		die(victim, ch);
		victim = NULL;

		for (P_obj room_obj = world[ch->in_room].contents; room_obj;
		     room_obj = room_obj->next_content)
		{
			if (room_obj->value[3] == id)
			{
				obj_from_room(room_obj);
				obj_to_room(room_obj,
					    real_room(cosmic_rift_astral_room(live_rolls)));
				if (room_obj->type == ITEM_CORPSE &&
				    IS_SET(room_obj->value[1], PC_CORPSE))
					writeCorpse(room_obj);
			}
		}
	}
	spell_damage(ch, victim, dam, SPLDAM_GENERIC, 0, &messages);
}

void spell_cosmic_rift(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		       P_obj /*obj*/)
{
	cast_as_damage_area(ch, spell_single_cosmic_rift, level, victim,
			    get_property("spell.area.minChance.cosmicRift", 0),
			    get_property("spell.area.chanceStep.cosmicRift", 20));
	zone_spellmessage(ch->in_room, FALSE, "&+LThe air visibly ripples and distorts.\r\n",
			  "&+LThe air to the %s visibly ripples and distorts.\r\n");
}

// The discharge's level stops growing at 46, however many casts add to it.
static int static_discharge_level(int level)
{
	return MIN(46, level);
}

static int static_discharge_damage(const Rolls &rolls, int level, int intensity)
{
	return (rolls.dice(((level / 5) + 5) * intensity, 5) * 3);
}

// Each failed save, one per cast, adds this much.
static int static_discharge_failed_save(int dam, int intensity)
{
	return (int)(dam * 0.10 / intensity);
}

static int static_discharge_wet_damage(int dam)
{
	return (int)(dam * 1.5);
}

// A roll of 0 sets it off.
static int static_discharge_trigger_roll(const Rolls &rolls, int intensity)
{
	return rolls.number(0, 4 - intensity);
}

// Pulses between tries, and the tries that may pass before one sets it off anyway.
static int static_discharge_interval()
{
	return PULSE_VIOLENCE;
}

static int static_discharge_tries()
{
	return 5;
}

std::string static_discharge_facts(P_char ch)
{
	const int cast = GET_LEVEL(ch), level = static_discharge_level(cast);
	const Range hit = { static_discharge_damage(lowest_rolls, level, 1),
			    static_discharge_damage(highest_rolls, level, 1) };
	const int twice = static_discharge_level(2 * cast);
	const int outcomes = static_discharge_trigger_roll(highest_rolls, 1) -
			     static_discharge_trigger_roll(lowest_rolls, 1) + 1;
	return fact("Lightning damage",
		    show(hit) + " at level " + std::to_string(level) + ", your level up to 46") +
	       fact("If the target fails its save",
		    show({ hit.low + static_discharge_failed_save(hit.low, 1),
			   hit.high + static_discharge_failed_save(hit.high, 1) })) +
	       fact("Against a wet target", show({ static_discharge_wet_damage(hit.low),
						   static_discharge_wet_damage(hit.high) }) +
						    " before its save") +
	       fact("Goes off",
		    "1 in " + std::to_string(outcomes) + " every " +
			    seconds(static_discharge_interval()) + ", at most " +
			    seconds(static_discharge_interval() * (static_discharge_tries() + 1))) +
	       "  A wet target or a water room sets it off at the first try.\n" +
	       fact("If recast first, two casts of yours",
		    show({ static_discharge_damage(lowest_rolls, twice, 2),
			   static_discharge_damage(highest_rolls, twice, 2) })) +
	       "  Each recast adds its level and dice, and makes it likelier to go off.\n" +
	       fact("Stopped by", "globe of invulnerability, greater spirit ward") +
	       "  After two casts only the greater ward stops it; after three, neither.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

struct static_discharge_data
{
	int level;
	int intensity;
	int round;
	bool discharge_now;
	P_char caster;
};

void static_discharge(P_char ch, P_char victim, int level, int intensity)
{
	int dam;

	struct damage_messages messages = {
		"&+LThe &+Cel&+cec&+Ctr&+cic&+Cit&+cy&N &+Lsurrounding&n $N &+ydischarges &+Lin a huge burst of &+cli&+Cgh&+ctn&+Cin&+cg!",
		"&+LThe &+Cel&+cec&+Ctr&+cic&+Cit&+cy&N &+Lsurrounding you suddenly &+ydischarges &+Lin a burst of &+cli&+Cgh&+ctn&+Cin&+cg!",
		"&+LThe &+Cel&+cec&+Ctr&+cic&+Cit&+cy&N &+Lsurrounding&n $N &+ydischarges &+Lin a huge burst of &+cli&+Cgh&+ctn&+Cin&+cg.",
		"$N &+Lsuddenly &+Rex&+Ypl&+Rod&+Yes &+Lamongst a cloud of &+cli&+Cgh&+ctn&+Cin&+cg, &+Lleaving behind $S &+rcha&+Rrre&+rd re&+Rmai&+rns.",
		"&+LThe &+Cel&+cec&+Ctr&+cic&+Cit&+cy&N &+Lsurrounding you &+ydischarges &+Lin a huge burst of &+cli&+Cgh&+ctn&+Cin&+cg! R.I.P.",
		"$N &+Lis overwhelmed by a burst of &+cli&+Cgh&+ctn&+Cin&+cg, &+Land leaves behind $S &+rcha&+Rrre&+rd re&+Rmai&+rns.",
		0
	};

	level = static_discharge_level(level);
	dam = static_discharge_damage(live_rolls, level, intensity);

	for (int i = intensity; i; i--)
	{
		if (!NewSaves(victim, SAVING_SPELL, intensity - 1))
			dam += static_discharge_failed_save(dam, intensity);
	}

	if (IS_AFFECTED5(victim, AFF5_WET))
		dam = static_discharge_wet_damage(dam);

	uint flags = SPLDAM_NODEFLECT | SPLDAM_GLOBE | SPLDAM_GRSPIRIT;

	if (intensity >= 5)
		flags |= SPLDAM_NOSHRUG;

	if (intensity >= 3)
		flags &= SPLDAM_GLOBE;

	if (intensity >= 2)
		flags &= SPLDAM_GRSPIRIT;

	spell_damage(ch, victim, dam, SPLDAM_LIGHTNING, flags, &messages);
}

void event_static_discharge(P_char ch, P_char victim, P_obj /*obj*/, void *data)
{
	struct static_discharge_data *sdata;

	sdata = (struct static_discharge_data *)data;

	if (sdata->discharge_now || !static_discharge_trigger_roll(live_rolls, sdata->intensity) ||
	    (++(sdata->round) > static_discharge_tries()))
		static_discharge(victim, ch, sdata->level, sdata->intensity);
	else
	{
		act("&+WThe &+cli&+Cgh&+ctn&+Cin&+cg &+Wsurrounding&n $n &+Yglo&+yws b&+Yrie&+yfly.",
		    TRUE, ch, 0, victim, TO_ROOM);
		act("&+WThe &+cli&+Cgh&+ctn&+Cin&+cg &+Wsurrounding you &+Yglo&+yws b&+Yrie&+yfly.",
		    TRUE, ch, 0, 0, TO_CHAR);
		add_event(event_static_discharge, static_discharge_interval(), ch, victim, NULL, 0,
			  sdata, sizeof(struct static_discharge_data));
	}
}

void spell_static_discharge([[maybe_unused]] int level, P_char ch, char * /*arg*/, int /*type*/,
			    P_char victim, P_obj /*obj*/)
{
	struct static_discharge_data sdata;
	struct static_discharge_data *tmpsdata;
	P_nevent e1 = 0;
	int delay = 0;

	sdata.level = GET_LEVEL(ch);
	sdata.intensity = 1;
	sdata.round = 0;
	sdata.discharge_now = FALSE;
	sdata.caster = ch;

	bool found = FALSE;
	LOOP_EVENTS_CH(e1, victim->nevents)
	{
		// wizlog(56, "victim: found event: %s", get_function_name((void*)e1->func));
		if (e1->func == event_static_discharge)
		{
			// wizlog(56, "found it");
			found = TRUE;
			break;
		}
	}

	if (found)
	{
		tmpsdata = (struct static_discharge_data *)e1->data;
		sdata.level += tmpsdata->level;
		sdata.intensity += tmpsdata->intensity;
		disarm_char_nevents(victim, event_static_discharge);
	}

	if (IS_AFFECTED5(victim, AFF5_WET) || IS_WATER_ROOM(victim->in_room))
	{
		act("&+BThe moisture around&n $n &+Bcauses the &+cli&+Cgh&+ctn&+Cin&+cgs &+Bto discharge immediately!",
		    TRUE, victim, 0, 0, TO_ROOM);
		act("&+BThe moisture around you causes the &+cli&+Cgh&+ctn&+Cin&+cgs &+Bto discharge immediately!",
		    TRUE, victim, 0, 0, TO_CHAR);
		sdata.discharge_now = TRUE;
	}

	delay = static_discharge_interval();

	if (found)
	{
		if (!static_discharge_trigger_roll(live_rolls, sdata.intensity))
		{
			delay = 0;
		}
		else
		{
			act("&+WA web of &+cli&+Cgh&+ctn&+Cin&+cg &+Waround $n &+Bintensifies!",
			    TRUE, victim, 0, 0, TO_ROOM);
			act("&+WA web of &+cli&+Cgh&+ctn&+Cin&+cg &+Waround you &+Bintensifies!",
			    TRUE, victim, 0, 0, TO_CHAR);
		}
	}
	else
	{
		act("&+WA web of &+Ycr&+yac&+Lki&+cng &+clig&+Chtn&+cing &+Wappears around $n!",
		    TRUE, victim, 0, 0, TO_ROOM);
		act("&+WA web of &+Ycr&+yac&+Lki&+cng &+clig&+Chtn&+cing &+Wappears around you!",
		    TRUE, victim, 0, 0, TO_CHAR);
	}

	add_event(event_static_discharge, delay, victim, ch, NULL, 0, &sdata, sizeof(sdata));
}

static int razor_wind_damage(const Rolls &rolls)
{
	return 180 + rolls.number(-40, 40);
}

static int razor_wind_failed_save(int dam)
{
	return (int)(dam * 1.2);
}

// Gusts of one cast, gusts a recast adds, and the pulses between them.
static int razor_wind_gusts()
{
	return 3;
}

static int razor_wind_recast_gusts()
{
	return 2;
}

static int razor_wind_interval()
{
	return PULSE_SPELLCAST;
}

std::string razor_wind_facts(P_char /*ch*/)
{
	const Range hit = { razor_wind_damage(lowest_rolls), razor_wind_damage(highest_rolls) };
	return fact("Cold damage per gust", show(hit)) +
	       fact("If the target fails its save, each gust",
		    show({ razor_wind_failed_save(hit.low), razor_wind_failed_save(hit.high) })) +
	       fact("Gusts", std::to_string(razor_wind_gusts()) + ", " +
				     seconds(razor_wind_interval()) + " apart, the first after " +
				     seconds(razor_wind_interval())) +
	       fact("Recasting while it blows adds",
		    std::to_string(razor_wind_recast_gusts()) + " gusts") +
	       "  Globes and spirit wards do not stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

// victim and ch have to be backwards for the event search to work right.. *sigh*
void event_razor_wind(P_char victim, P_char ch, P_obj /*obj*/, void *data)
{
	int dam, duration;

	struct damage_messages messages = {
		"&+CThe &+Wwi&+wnd&+Wst&+wor&+Wm &+csends &+Ldebris &+cflying into $N&+c at high speed causing $M to &+Rb&+rle&+Red&+c.&n",
		"&+CThe &+Wwi&+wnd&+Wst&+wor&+Wm &+csends &+Ldebris &+cflying into you at high speed causing you to &+Rb&+rle&+Red&+c.&n",
		"&+CThe &+Wwi&+wnd&+Wst&+wor&+Wm &+csends &+Ldebris &+cflying into $N&+c at high speed causing $M to &+Rb&+rle&+Red&+c.&n",
		"&+cThe &+Rvi&+rol&+Ren&+rt &+Ww&+wi&+Wn&+wd&+Ws&+wt&+Wo&+wr&+Wm &+cproves to be too much for $N as the winds tear $M to &+Rpi&+rec&+Res&+c.&n",
		"&+RB&+rle&+Red&+rin&+Rg &+cprofusely, you succumb to the awesome power of the &+Ww&+wi&+Wn&+wd&+C.&n",
		"&+cThe &+Rvi&+rol&+Ren&+rt &+Ww&+wi&+Wn&+wd&+Ws&+wt&+Wo&+wr&+Wm &+cproves to be too much for $N as the winds tear $M to &+Rpi&+rec&+Res&+c.&n",
		0
	};

	duration = *((int *)data);
	// 35-55 damage.
	dam = razor_wind_damage(live_rolls);

	int mod = get_default_save_mod(victim, ch, SAVING_SPELL, SPELL_RAZOR_WIND);
	if (!NewSaves(victim, SAVING_SPELL, mod))
	{
		dam = razor_wind_failed_save(dam);
	}

	if (spell_damage(ch, victim, (int)dam, SPLDAM_COLD, SPLDAM_NODEFLECT, &messages) ==
		    DAM_NONEDEAD &&
	    --duration > 0)
	{
		// This has to be backwards for the event search to work right.. *sigh*
		add_event(event_razor_wind, razor_wind_interval(), victim, ch, NULL, 0, &duration,
			  sizeof(int));
	}
	else if (IS_ALIVE(victim) && duration <= 0)
	{
		send_to_char(
			"&+CThe &+Wwi&+wnd&+Wst&+wor&+Wm &+ccalms, the &+Ldebris &+cfalls, and the room becomes quiet.&n",
			victim);
	}
}

void spell_razor_wind(int /*level*/, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		      P_obj /*obj*/)
{
	int duration = razor_wind_gusts();
	P_nevent e1 = NULL;
	bool found = FALSE;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return;
	}

	// Look for an event already going on.
	LOOP_EVENTS_CH(e1, victim->nevents)
	{
		if (e1->func == event_razor_wind)
		{
			found = TRUE;
			break;
		}
	}

	// If there's an event already going on, suck it's data and kill it!
	if (found)
	{
		duration = *((int *)e1->data) + razor_wind_recast_gusts();
		disarm_char_nevents(victim, event_razor_wind);
		act("&+cThe &+Ww&+wi&+Wn&+wd&+Ws&+wt&+Wo&+wr&+Wm &+csurrounding $N &+Cintensifies&+c!",
		    TRUE, ch, 0, victim, TO_CHAR);
		act("&+cThe &+Ww&+wi&+Wn&+wd&+Ws&+wt&+Wo&+wr&+Wm &+csurrounding you &+Cintensifies&+c!",
		    TRUE, ch, 0, victim, TO_VICT);
		act("&+cThe &+Ww&+wi&+Wn&+wd&+Ws&+wt&+Wo&+wr&+Wm &+csurrounding $N &+Cintensifies&+c!",
		    TRUE, ch, 0, victim, TO_NOTVICT);
	}
	else
	{
		act("&+cYou summon forth &+Rv&+ri&+Ro&+rl&+Re&+rn&+Rt &+Ww&+wi&+Wn&+wd&+Ws &+cto batter $N&+c!",
		    TRUE, ch, 0, victim, TO_CHAR);
		act("&+c$n summons forth &+Rv&+ri&+Ro&+rl&+Re&+rn&+Rt &+Ww&+wi&+Wn&+wd&+Ws &+cto batter you!&n",
		    TRUE, ch, 0, victim, TO_VICT);
		act("&+cGales of &+Wvi&+wol&+Wen&+wt &+Ww&+wi&+Wn&+wd &+csurrounds $N&+c causing flying &+Ldebris &+cto shred and errode $S skin!",
		    TRUE, ch, 0, victim, TO_NOTVICT);
	}

	// This has to be backwards for the event search to work right.. *sigh*
	add_event(event_razor_wind, razor_wind_interval(), victim, ch, NULL, 0, &duration,
		  sizeof(duration));
}

// A star magus's void elemental.
static int conjure_void_star_hit_points(const Rolls &rolls, int mob_level, int charisma)
{
	return rolls.dice(mob_level / 2, 40) + mob_level + charisma;
}

std::string conjure_void_elemental_facts(P_char ch)
{
	const int level = GET_LEVEL(ch), charisma = conjured_elemental_charisma(ch);
	if (GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_STARMAGUS))
	{
		const int mob = conjured_elemental_spec_level(level);
		return conjured_elemental_page(
			ch, { mob, mob },
			{ conjure_void_star_hit_points(lowest_rolls, mob, charisma),
			  conjure_void_star_hit_points(highest_rolls, mob, charisma) },
			"charisma");
	}
	const Range mob = conjured_elemental_level_range(level);
	return conjured_elemental_page(ch, mob, conjured_elemental_plain_hit_points(ch, mob),
				       "charisma");
}

void spell_conjure_void_elemental(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
				  P_obj /*tar_obj*/)
{
	P_char mob;
	int mlvl, lvl;
	int i, j;
	int charisma = conjured_elemental_charisma(ch);
	struct follow_type *k;

	if (CHAR_IN_SAFE_ROOM(ch))
	{
		send_to_char("A mysterious force blocks your conjuring!\r\n", ch);
		return;
	}

	for (k = ch->followers, i = 0, j = 0; k; k = k->next)
	{
		victim = k->follower;
		if (IS_ELEMENTAL(victim))
		{
			if (GET_LEVEL(victim) < 50)
				i++;
			else
				j++;
		}
	}

	if (i >= 1 || j >= 1)
	{
		send_to_char("You cannot control any more elementals!\r\n", ch);
		return;
	}

	mob = read_mobile(real_mobile(76), REAL);

	if (!mob)
	{
		send_to_char("Bug in conjure elemental.  Tell a god!\r\n", ch);
		return;
	}

	GET_SIZE(mob) = SIZE_MEDIUM;
	mob->player.m_class = CLASS_WARRIOR;
	char_to_room(mob, ch->in_room, 0);

	act("&+LNegative energies coalesce and form a Voi&+wd Elemen&+Ltal!&n", TRUE, mob, 0, 0,
	    TO_ROOM);

	mlvl = conjured_elemental_base(level);
	lvl = conjured_elemental_roll(live_rolls, mlvl);

	if (GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_STARMAGUS))
		mob->player.level = conjured_elemental_spec_level(level);
	else
		mob->player.level = conjured_elemental_level(lvl);

	if (GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_STARMAGUS))
	{
		GET_MAX_HIT(mob) = GET_HIT(mob) = mob->points.base_hit =
			conjure_void_star_hit_points(live_rolls, GET_LEVEL(mob), charisma);
	}
	else
	{
		GET_MAX_HIT(mob) = GET_HIT(mob) = mob->points.base_hit =
			conjured_elemental_hit_points(live_rolls, GET_LEVEL(mob), charisma);
	}

	SET_BIT(mob->specials.affected_by, AFF_INFRAVISION);

	mob->points.base_hitroll = mob->points.hitroll =
		conjured_elemental_roll_bonus(GET_LEVEL(mob));
	mob->points.base_damroll = mob->points.damroll =
		conjured_elemental_roll_bonus(GET_LEVEL(mob));
	MonkSetSpecialDie(mob); /* 2d6 to 4d5 */

	if (IS_PC(ch) && /*(GET_LEVEL(mob) > number((level - i * 4), level * 3 / 2)) */
	    (GET_LEVEL(mob) > GET_LEVEL(ch)) &&
	    charisma < conjured_elemental_temper_roll(live_rolls))
	{
		act("$N is NOT pleased at being suddenly summoned against $S will!", TRUE, ch, 0,
		    mob, TO_ROOM);
		act("$N is NOT pleased with you at all!", TRUE, ch, 0, mob, TO_CHAR);
		// Poof in 5-10 sec.
		add_event(event_pet_death, conjured_elemental_poof(live_rolls), mob, NULL, NULL, 0,
			  NULL, 0);
		MobStartFight(mob, ch);
	}
	else
	{ /* Under control */
		act("$N sulkily says 'Your wish is my command, $n!'", TRUE, ch, 0, mob, TO_ROOM);
		act("$N sulkily says 'Your wish is my command, master!'", TRUE, ch, 0, mob,
		    TO_CHAR);

		int duration = setup_pet(
			mob, ch, conjured_elemental_charm(STAT_INDEX(GET_C_INT(mob))), PET_NOCASH);
		add_follower(mob, ch);
		/* if the pet will stop being charmed after a bit, also make it suicide 1-10 minutes later */
		if (duration >= 0)
		{
			duration += conjured_elemental_late_death_roll(live_rolls);
			add_event(event_pet_death, conjured_elemental_death_delay(duration), mob,
				  NULL, NULL, 0, NULL, 0);
		}
	}
}

// A frost magus's ice elemental.
static int conjure_ice_frost_hit_points(const Rolls &rolls, int mob_level, int charisma)
{
	return rolls.dice(mob_level / 2, 50) + mob_level + charisma;
}

std::string conjure_ice_elemental_facts(P_char ch)
{
	const int level = GET_LEVEL(ch), charisma = conjured_elemental_charisma(ch);
	if (GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_FROSTMAGUS))
	{
		const int mob = conjured_elemental_spec_level(level);
		return conjured_elemental_page(
			ch, { mob, mob },
			{ conjure_ice_frost_hit_points(lowest_rolls, mob, charisma),
			  conjure_ice_frost_hit_points(highest_rolls, mob, charisma) },
			"charisma");
	}
	const Range mob = conjured_elemental_level_range(level);
	return conjured_elemental_page(ch, mob, conjured_elemental_plain_hit_points(ch, mob),
				       "charisma");
}

void spell_conjure_ice_elemental(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
				 P_obj /*tar_obj*/)
{
	P_char mob;
	int mlvl, lvl;
	int i, j;
	int charisma = conjured_elemental_charisma(ch);
	struct follow_type *k;

	if (CHAR_IN_SAFE_ROOM(ch))
	{
		send_to_char("A mysterious force blocks your conjuring!\r\n", ch);
		return;
	}

	for (k = ch->followers, i = 0, j = 0; k; k = k->next)
	{
		victim = k->follower;
		if (IS_ELEMENTAL(victim))
		{
			if (GET_LEVEL(victim) < 50)
				i++;
			else
				j++;
		}
	}

	if (i >= 1 || j >= 1)
	{
		send_to_char("You cannot control any more elementals!\r\n", ch);
		return;
	}

	mob = read_mobile(real_mobile(1157), REAL);

	if (!mob)
	{
		send_to_char("Bug in conjure elemental.  Tell a god!\r\n", ch);
		return;
	}

	GET_SIZE(mob) = SIZE_MEDIUM;
	mob->player.m_class = CLASS_WARRIOR;
	char_to_room(mob, ch->in_room, 0);

	act("&+WAn Ice Elemental forms from a cold gust of air.&n", TRUE, mob, 0, 0, TO_ROOM);

	mlvl = conjured_elemental_base(level);
	lvl = conjured_elemental_roll(live_rolls, mlvl);

	if (GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_FROSTMAGUS))
		mob->player.level = conjured_elemental_spec_level(level);
	else
		mob->player.level = conjured_elemental_level(lvl);

	if (GET_SPEC(ch, CLASS_ETHERMANCER, SPEC_FROSTMAGUS))
	{
		GET_MAX_HIT(mob) = GET_HIT(mob) = mob->points.base_hit =
			conjure_ice_frost_hit_points(live_rolls, GET_LEVEL(mob), charisma);
	}
	else
	{
		GET_MAX_HIT(mob) = GET_HIT(mob) = mob->points.base_hit =
			conjured_elemental_hit_points(live_rolls, GET_LEVEL(mob), charisma);
	}

	SET_BIT(mob->specials.affected_by, AFF_INFRAVISION);

	mob->points.base_hitroll = mob->points.hitroll =
		conjured_elemental_roll_bonus(GET_LEVEL(mob));
	mob->points.base_damroll = mob->points.damroll =
		conjured_elemental_roll_bonus(GET_LEVEL(mob));
	MonkSetSpecialDie(mob); /* 2d6 to 4d5 */

	if (IS_PC(ch) && /*(GET_LEVEL(mob) > number((level - i * 4), level * 3 / 2)) */
	    (GET_LEVEL(mob) > GET_LEVEL(ch)) &&
	    charisma < conjured_elemental_temper_roll(live_rolls))
	{
		act("$N is NOT pleased at being suddenly summoned against $S will!", TRUE, ch, 0,
		    mob, TO_ROOM);
		act("$N is NOT pleased with you at all!", TRUE, ch, 0, mob, TO_CHAR);
		// Poof in 5-10 sec.
		add_event(event_pet_death, conjured_elemental_poof(live_rolls), mob, NULL, NULL, 0,
			  NULL, 0);
		MobStartFight(mob, ch);
	}
	else
	{ /* Under control */
		act("$N sulkily says 'Your wish is my command, $n!'", TRUE, ch, 0, mob, TO_ROOM);
		act("$N sulkily says 'Your wish is my command, master!'", TRUE, ch, 0, mob,
		    TO_CHAR);

		int duration = setup_pet(
			mob, ch, conjured_elemental_charm(STAT_INDEX(GET_C_INT(mob))), PET_NOCASH);
		add_follower(mob, ch);
		/* if the pet will stop being charmed after a bit, also make it suicide 1-10 minutes later */
		if (duration >= 0)
		{
			duration += conjured_elemental_late_death_roll(live_rolls);
			add_event(event_pet_death, conjured_elemental_death_delay(duration), mob,
				  NULL, NULL, 0, NULL, 0);
		}
	}
}

// Hits the armor absorbs before it breaks; casting it always doubles the roll.
static int iceflow_armor_absorb(const Rolls &rolls, int level)
{
	return (level / 4) + rolls.number(1, 4);
}

static int iceflow_armor_doubled(int absorb)
{
	return (int)(absorb * 2);
}

static int iceflow_armor_duration()
{
	return 8;
}

std::string iceflow_armor_facts(P_char ch)
{
	extern int skin_spell_deduct();
	extern float iceflow_armor_melee_share();
	const int level = GET_LEVEL(ch);
	return fact("Hits absorbed",
		    show({ iceflow_armor_doubled(iceflow_armor_absorb(lowest_rolls, level)),
			   iceflow_armor_doubled(iceflow_armor_absorb(highest_rolls, level)) }) +
			    " at your level, " + std::to_string(level)) +
	       fact("Duration", game_hours(iceflow_armor_duration())) +
	       fact("Each melee hit on you", std::to_string(skin_spell_deduct()) + " less") +
	       fact("Then, if over 10 is left",
		    share_percent(iceflow_armor_melee_share()) + " of that") +
	       "  It applies before the raw damage modifiers.\n"
	       "  Hits that ignore reductions go through it and use up nothing.\n"
	       "  An attacker's fist of dragon can do the same.\n" +
	       "  You need a cold shield and no other skin spell.\n"
	       "  A fire spell melts it without hurting you.\n";
}

void spell_iceflow_armor(int level, P_char ch, char * /*arg*/, [[maybe_unused]] int type,
			 P_char victim, P_obj /*obj*/)
{
	struct affected_type af;
	int absorb = iceflow_armor_absorb(live_rolls, level);

	if (!IS_AFFECTED3(ch, AFF3_COLDSHIELD))
	{
		send_to_char("You lack the &+Cicy&n aura of &+Bcoldshield&n!\n", ch);
		return;
	}

	if (!has_skin_spell(ch))
	{
		absorb = iceflow_armor_doubled(absorb);
		act("$n&+C is surrounded by a &+Bfrigid&+W aura&+C!&n", TRUE, victim, 0, 0,
		    TO_ROOM);
		act("&+CFlowing &+Wi&+Cc&+we &+cencases you in a &+Bsolid &+cprotective barrier!&n",
		    TRUE, victim, 0, 0, TO_CHAR);
	}
	else
	{
		send_to_char("You are already affected by a magical barrier!\n", ch);
		return;
	}

	bzero(&af, sizeof(af));
	af.type = SPELL_ICE_ARMOR;
	af.duration = iceflow_armor_duration();
	af.modifier = absorb;
	affect_to_char(victim, &af);
}

// Hits the barrier absorbs before it breaks; casting it always doubles the roll.
static int negative_feedback_barrier_absorb(const Rolls &rolls, int level)
{
	return (level / 4) + rolls.number(1, 4);
}

static int negative_feedback_barrier_doubled(int absorb)
{
	return (int)(absorb * 2);
}

static int negative_feedback_barrier_duration()
{
	return 8;
}

std::string negative_feedback_barrier_facts(P_char ch)
{
	extern int skin_spell_deduct();
	extern float negative_feedback_barrier_melee_share();
	const int level = GET_LEVEL(ch);
	return fact("Hits absorbed",
		    show({ negative_feedback_barrier_doubled(
				   negative_feedback_barrier_absorb(lowest_rolls, level)),
			   negative_feedback_barrier_doubled(
				   negative_feedback_barrier_absorb(highest_rolls, level)) }) +
			    " at your level, " + std::to_string(level)) +
	       fact("Duration", game_hours(negative_feedback_barrier_duration())) +
	       fact("Each melee hit on you", std::to_string(skin_spell_deduct()) + " less") +
	       fact("Then, if over 10 is left",
		    share_percent(negative_feedback_barrier_melee_share()) + " of that") +
	       "  It applies before the raw damage modifiers.\n"
	       "  Hits that ignore reductions go through it and use up nothing.\n"
	       "  An attacker's fist of dragon can do the same.\n" +
	       "  You need a negative shield and no other skin spell.\n"
	       "  A holy spell disperses it without hurting you.\n";
}

void spell_negative_feedback_barrier(int level, P_char ch, char * /*arg*/,
				     [[maybe_unused]] int type, P_char victim, P_obj /*obj*/)
{
	struct affected_type af;
	int absorb = negative_feedback_barrier_absorb(live_rolls, level);

	if (!IS_AFFECTED4(ch, AFF4_NEG_SHIELD))
	{
		send_to_char("&+LYou lack the &+rnegative&+L energy to conjure a barrier!&n!\n",
			     ch);
		return;
	}

	if (!has_skin_spell(ch))
	{
		absorb = negative_feedback_barrier_doubled(absorb);
		act("$n &+Lis encased in a &+rdark &+Lenergy field!&n", TRUE, victim, 0, 0,
		    TO_ROOM);
		act("&+LGravitational &+wenergy &+Lbegins to &+ws&+Lwi&+wrl &+Laround you in a protective barrier.&n",
		    TRUE, victim, 0, 0, TO_CHAR);
	}
	else
	{
		send_to_char("You are already affected by a magical barrier!\n", ch);
		return;
	}

	bzero(&af, sizeof(af));
	af.type = SPELL_NEG_ARMOR;
	af.duration = negative_feedback_barrier_duration();
	af.modifier = absorb;
	affect_to_char(victim, &af);
}

// A direction on the map, and a room in the target's zone.
static int etheric_gust_direction_roll(const Rolls &rolls)
{
	return rolls.number(0, 3);
}

static int etheric_gust_zone_room_roll(const Rolls &rolls, P_char victim)
{
	return rolls.number(zone_table[world[victim->in_room].zone].real_bottom,
			    zone_table[world[victim->in_room].zone].real_top);
}

// Steps taken on the map.
static int etheric_gust_range()
{
	return get_property("spell.ethericgust.range", 5);
}

// A limited-teleport zone keeps the target this close.
static int etheric_gust_limited_range()
{
	return 5;
}

static int etheric_gust_lag()
{
	return (3 * WAIT_SEC);
}

// Below this level no-teleport rooms, hometowns and ocean refuse the spell.
static bool etheric_gust_room_limited(int level)
{
	return level < 60;
}

std::string etheric_gust_facts(P_char ch)
{
	std::string text = fact("Your lag on arrival", seconds(etheric_gust_lag())) +
			   fact("On the world map",
				"up to " + std::to_string(etheric_gust_range()) + " rooms away") +
			   fact("In a limited-teleport zone",
				"within " + std::to_string(etheric_gust_limited_range()) +
					" rooms, or fails") +
			   "  Elsewhere it lands in a random room of the zone, never a private,\n"
			   "  no-teleport, hometown or ocean room.\n";
	if (etheric_gust_room_limited(GET_LEVEL(ch)))
		text += "  No-teleport rooms, hometowns and ocean block it.\n";
	return text + "  You must be raidable.\n";
}

void spell_etheric_gust(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			P_obj /*obj*/)
{
	P_char t_ch;
	int tries = 0, to_room, dir;
	int range = etheric_gust_range();

	if (!IS_ALIVE(ch) || ch->in_room == NOWHERE)
		return;

	if ((IS_ROOM(ch->in_room, ROOM_NO_TELEPORT) || IS_HOMETOWN(ch->in_room) ||
	     world[ch->in_room].sector_type == SECT_OCEAN) &&
	    etheric_gust_room_limited(level))
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
				dir = etheric_gust_direction_roll(live_rolls);

			while (tries++ < 10 && !VALID_TELEPORT_EDGE(to_room, dir, victim->in_room));

			if (tries < 10)
				to_room = TOROOM(to_room, dir);
		}
	}
	else
	{
		do
		{
			to_room = etheric_gust_zone_room_roll(live_rolls, victim);
			tries++;
		} while ((IS_ROOM(to_room, ROOM_PRIVATE) || PRIVATE_ZONE(to_room) ||
			  IS_ROOM(to_room, ROOM_NO_TELEPORT) || IS_HOMETOWN(to_room) ||
			  world[to_room].sector_type == SECT_OCEAN) &&
			 tries < 1000);
	}

	if (tries >= 1000)
		to_room = victim->in_room;

	if (LIMITED_TELEPORT_ZONE(victim->in_room) &&
	    how_close(victim->in_room, to_room, etheric_gust_limited_range()) < 0)
	{
		send_to_char("The magic gathers, but somehow fades away before taking effect.\n",
			     victim);
		return;
	}

	act("&+cA strange &+Wwind &+csuddenly fills the area, and carries you away...&n", FALSE,
	    victim, 0, 0, TO_CHAR);
	act("&+cA strange &+Wwind &+cbegins to blow and carries $n&+c away into a &+Cvortex!&n",
	    FALSE, victim, 0, 0, TO_ROOM);

	if (IS_FIGHTING(victim))
		stop_fighting(victim);

	if (victim->in_room != NOWHERE)
		for (t_ch = world[victim->in_room].people; t_ch; t_ch = t_ch->next)
			if (IS_FIGHTING(t_ch) && GET_OPPONENT(t_ch) == victim)
				stop_fighting(t_ch);

	if (victim->in_room != to_room)
	{
		char_from_room(victim);
		char_to_room(victim, to_room, -1);
	}

	act("&+cand softly deposits you elsewhere!&n", FALSE, victim, 0, 0, TO_CHAR);
	act("&+cA strange &+Wvortex &+cappears, and deposits $n&+c in the room!&n", FALSE, victim,
	    0, 0, TO_ROOM);

	CharWait(victim, etheric_gust_lag());
}

static int antimatter_collision_damage(const Rolls &rolls)
{
	return 200 + rolls.number(-40, 40);
}

static int antimatter_collision_failed_save(int dam)
{
	return (int)(dam * 1.2);
}

// Hits of one cast, hits a recast adds, and the pulses between them.
static int antimatter_collision_hits()
{
	return 3;
}

static int antimatter_collision_recast_hits()
{
	return 2;
}

static int antimatter_collision_interval()
{
	return PULSE_SPELLCAST * 2;
}

std::string antimatter_collision_facts(P_char /*ch*/)
{
	const Range hit = { antimatter_collision_damage(lowest_rolls),
			    antimatter_collision_damage(highest_rolls) };
	return fact("Negative damage per hit", show(hit)) +
	       fact("If the target fails its save, each hit",
		    show({ antimatter_collision_failed_save(hit.low),
			   antimatter_collision_failed_save(hit.high) })) +
	       fact("Hits", std::to_string(antimatter_collision_hits()) + ", " +
				    seconds(antimatter_collision_interval()) +
				    " apart, the first after " +
				    seconds(antimatter_collision_interval())) +
	       fact("Recasting while it lasts adds",
		    std::to_string(antimatter_collision_recast_hits()) + " hits") +
	       "  Globes and spirit wards do not stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

// Event for spec nuke
// victim and ch have to be backwards for the event search to work right.. *sigh*
void event_antimatter_collision(P_char victim, P_char ch, P_obj /*obj*/, void *data)
{
	int dam, duration;

	struct damage_messages messages = {
		"&+LThe black dots swarm and COLLIDE with $N&+L absorbing his &+Mfl&+mes&+Mh&+L!&n",
		"&+LTiny orbs of anti-matter &=LYCO&+WL&+YLI&+WD&+YE&n &+Linto you absorbing your very flesh!",
		"&+LThe black dots swarm and COLLIDE with $N&+L absorbing his &+Mfl&+mes&+Mh&+L!&n",
		"&+LYou &+Ws&+wh&+Wi&+wv&+We&+wr &+Las you watch the tiny black orbs absorb the majority of $N who drops dead and lifeless.",
		"&+LThe black orbs crash into you and invade your very center causing your &+Mbr&+mai&+Mn &+Land internal &+Ror&+rga&+Rns &+Lto shut down.&n",
		"&+LYou &+Ws&+wh&+Wi&+wv&+We&+wr &+Las you watch the tiny black orbs absorb the majority of $N who drops dead and lifeless.",
		0
	};

	duration = *((int *)data);
	// 40-60 damage.
	dam = antimatter_collision_damage(live_rolls);

	int mod = get_default_save_mod(victim, ch, SAVING_SPELL, SPELL_AMATTER_COLLISION);
	if (!NewSaves(victim, SAVING_SPELL, mod))
	{
		dam = antimatter_collision_failed_save(dam);
	}

	if (spell_damage(ch, victim, (int)dam, SPLDAM_NEGATIVE, SPLDAM_NODEFLECT, &messages) ==
		    DAM_NONEDEAD &&
	    --duration > 0)
	{
		// This has to be backwards for the event search to work right.. *sigh*
		add_event(event_antimatter_collision, antimatter_collision_interval(), victim, ch,
			  NULL, 0, &duration, sizeof(int));
	}
}

// Spec nuke.
void spell_antimatter_collision(int /*level*/, P_char ch, char * /*arg*/, int /*type*/,
				P_char victim, P_obj /*obj*/)
{
	int duration = antimatter_collision_hits();
	P_nevent e1 = NULL;
	bool found = FALSE;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return;
	}

	// Look for an event already going on.
	LOOP_EVENTS_CH(e1, victim->nevents)
	{
		if (e1->func == event_antimatter_collision)
		{
			found = TRUE;
			break;
		}
	}

	// If there's an event already going on, suck it's data and kill it!
	if (found)
	{
		duration = *((int *)e1->data) + antimatter_collision_recast_hits();
		disarm_char_nevents(victim, event_antimatter_collision);

		act("&+LMore small black orbs rush out of the rift crashing into $N!", TRUE, ch, 0,
		    victim, TO_CHAR);
		act("&+LMore small black orbs come rushing out of the rift swarming you!", TRUE, ch,
		    0, victim, TO_VICT);
		act("&+LMore small black orbs rush out of the rift crashing into $N!", TRUE, ch, 0,
		    victim, TO_NOTVICT);
	}
	else
	{
		act("&+wYou open up a &+Ymighty &+WCo&+Ysm&+Wi&+Yc &+Lrift &+win &+Lspace &+wand tiny &+Lblack dots &+wcome pouring out &+Yco&+Ll&+Yl&+Lid&+Ying &+wwith $N&+L!",
		    TRUE, ch, 0, victim, TO_CHAR);
		act("&+LA black rift opens in which you see &+Ws&+Yta&+Wr&+Ys &+Land &+Yco&+yme&+Yts&+L when suddenly small black orbs come pouring out crashing into you!",
		    TRUE, ch, 0, victim, TO_VICT);
		act("&+LA HUGE &+YCo&+Wsm&+Yic &+LRift opens and tiny black orbs come flying out and slam into $N&n!",
		    TRUE, ch, 0, victim, TO_NOTVICT);
	}

	// This has to be backwards for the event search to work right.. *sigh*
	add_event(event_antimatter_collision, antimatter_collision_interval(), victim, ch, NULL, 0,
		  &duration, sizeof(int));
}

static int arctic_blast_damage(const Rolls &rolls)
{
	return 180 + rolls.number(-40, 40);
}

static int arctic_blast_failed_save(int dam)
{
	return (int)(dam * 1.2);
}

// Blasts of one cast at the cast level; a recast adds one fewer.
static int arctic_blast_blasts(int level)
{
	return 3 + (MAX(level - 40, 0) / 5);
}

static int arctic_blast_recast_blasts(int remaining, int duration)
{
	return remaining + duration - 1;
}

// Pulses to the first blast, and between the later ones.
static int arctic_blast_first_delay()
{
	return PULSE_SPELLCAST;
}

static int arctic_blast_interval()
{
	return PULSE_SPELLCAST * 2;
}

std::string arctic_blast_facts(P_char ch)
{
	const int level = GET_LEVEL(ch), blasts = arctic_blast_blasts(level);
	const Range hit = { arctic_blast_damage(lowest_rolls), arctic_blast_damage(highest_rolls) };
	return fact("Cold damage per blast", show(hit)) +
	       fact("If the target fails its save, each blast",
		    show({ arctic_blast_failed_save(hit.low),
			   arctic_blast_failed_save(hit.high) })) +
	       fact("Blasts", std::to_string(blasts) + " at your level, " + std::to_string(level)) +
	       fact("The first comes after", seconds(arctic_blast_first_delay()) + ", the rest " +
						     seconds(arctic_blast_interval()) + " apart") +
	       fact("Recasting while it blows adds",
		    std::to_string(arctic_blast_recast_blasts(0, blasts)) + " blasts") +
	       "  Globes and spirit wards do not stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

// Event for spec nuke
// victim and ch have to be backwards for the event search to work right.. *sigh*
void event_arctic_blast(P_char victim, P_char ch, P_obj /*obj*/, void *data)
{
	int dam, duration;

	struct damage_messages messages = {
		"&+C$N&+C &+Wsh&+wud&+Wde&+wrs &+Cviolently as the &+Wi&+Cc&+we &+Bcold &+Wwinds &+Cslice through $M.&n",
		"&+CYou &+Wsh&+wud&+Wde&+wr &+Cviolently as the &+Wi&+Cc&+we &+Bcold &+Wwinds &+Cslice through you.&n",
		"&+C$N&+C &+Wsh&+wud&+Wde&+wrs &+Cviolently as the &+Wi&+Cc&+we &+Bcold &+Wwinds &+Cslice through $M.&n",
		"&+CThe &+Wi&+Cc&+wy &+Wwinds &+Cclaim the life of $N&+C...&n",
		"&+CThe &+Wfrozen gale &+Cproves to be too much, sapping the last bit of &+rheat &+Cfrom your body leaving you in a &+Bfrost &+Ccovered heap...&n",
		"&+CThe &+Wi&+Cc&+wy &+Wwinds &+Cclaim the life of $N&+C...&n",
		0
	};

	duration = *((int *)data);
	// 35-55 damage.
	dam = arctic_blast_damage(live_rolls);

	int mod = get_default_save_mod(victim, ch, SAVING_SPELL, SPELL_ARCTIC_BLAST);
	if (!NewSaves(victim, SAVING_SPELL, mod))
	{
		dam = arctic_blast_failed_save(dam);
	}

	if (spell_damage(ch, victim, (int)dam, SPLDAM_COLD, SPLDAM_NODEFLECT, &messages) ==
		    DAM_NONEDEAD &&
	    --duration > 0)
	{
		// This has to be backwards for the event search to work right.. *sigh*
		add_event(event_arctic_blast, arctic_blast_interval(), victim, ch, NULL, 0,
			  &duration, sizeof(int));
	}
	else if (IS_ALIVE(victim) && duration <= 0)
	{
		send_to_char("&+CThe &+Bcold &+Wwinds &+Csurrounding you subside.&n\n\r", victim);
	}
}

void spell_arctic_blast(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
			P_obj /*tar_obj*/)
{
	int duration = arctic_blast_blasts(level);
	P_nevent e1 = NULL;
	bool found = FALSE;

	if (!IS_ALIVE(ch) || !IS_ALIVE(victim))
	{
		return;
	}

	// Look for an event already going on.
	LOOP_EVENTS_CH(e1, victim->nevents)
	{
		if (e1->func == event_arctic_blast)
		{
			found = TRUE;
			break;
		}
	}

	// If there's an event already going on, suck it's data and kill it!
	if (found)
	{
		duration = arctic_blast_recast_blasts(*((int *)e1->data), duration);
		disarm_char_nevents(victim, event_arctic_blast);

		act("&+CThe &+Wfr&+Ce&+cez&+Win&+Cg &+Wwinds &+Caround $N &+Wintensify!", TRUE, ch,
		    0, victim, TO_CHAR);
		act("&+CThe &+Wfr&+Ce&+cez&+Win&+Cg &+Wwinds &+Caround you &+Wintensify!", TRUE, ch,
		    0, victim, TO_VICT);
		act("&+CThe &+Wfr&+Ce&+cez&+Win&+Cg &+Wwinds &+Caround $N &+Wintensify!", TRUE, ch,
		    0, victim, TO_NOTVICT);
	}
	else
	{
		act("&+CYou open an &+Wi&+Cc&+wy &+cvortex &+Cin the ether and &+Wbl&+Ca&+Cs&+wt $N &+Cwith the &+BF&+bu&+BR&+by &+Cof &+WAu&+Cri&+wl&+C!",
		    TRUE, ch, 0, victim, TO_CHAR);
		act("&+cAn &+Carctic &+Wgale &+cbegins to blow unleashing the &+Bcold &+Cf&+Wu&+Cr&+Wy &+con YOU!",
		    TRUE, ch, 0, victim, TO_VICT);
		act("&+BCold &+cand &+Wi&+Cc&+wy &+Wwinds &+cbegin to &+wblow &+cand engulf $N&+c!&n",
		    TRUE, ch, 0, victim, TO_NOTVICT);
	}

	// This has to be backwards for the event search to work right.. *sigh*
	add_event(event_arctic_blast, arctic_blast_first_delay(), victim, ch, NULL, 0, &duration,
		  sizeof(int));
}

static int ice_spikes_count(const Rolls &rolls, int level)
{
	return rolls.number(3, 4) + (level > 50 ? 1 : 0);
}

static int ice_spikes_damage(const Rolls &rolls, int level)
{
	return (3 * level) + rolls.number(0, level);
}

static int ice_spikes_saved(int base_dam)
{
	return (base_dam * 2) / 3;
}

std::string ice_spikes_facts(P_char ch)
{
	const int level = GET_LEVEL(ch);
	const Range hit = { ice_spikes_damage(lowest_rolls, level),
			    ice_spikes_damage(highest_rolls, level) };
	return fact("Spikes", show({ ice_spikes_count(lowest_rolls, level),
				     ice_spikes_count(highest_rolls, level) }) +
				      " at your level, " + std::to_string(level)) +
	       fact("Cold damage per spike", show(hit) + ", one roll for all of them") +
	       fact("If the target saves, per spike",
		    show({ ice_spikes_saved(hit.low), ice_spikes_saved(hit.high) })) +
	       "  Globes and spirit wards do not stop it.\n"
	       "  Spell damage modifiers and the target's defenses apply after.\n";
}

void spell_ice_spikes(int level, P_char ch, char * /*arg*/, int /*type*/, P_char victim,
		      P_obj /*tar_obj*/)
{
	int base_dam, missile_dam;
	int num_missiles = ice_spikes_count(live_rolls, level);
	struct damage_messages messages = {
		"&+CYou hurl a spike of &+Rr&+raz&+Ror &+Csharp &+Wice &+Cat $N&+C.",
		"&+CGiant Spikes of &+Wice&+C hit you square in the chest, impaling you!",
		"$n &+Cstretches out $s hand, unleashing a torret of &+Rr&+raz&+Ror &+Csharp &+Wice &+Ctoward $N&+C!&n",
		"&+CYour deadly &+Wspike &+Cof &+Wice &+Rimpales &+C$N&+C ending $S life abruptly.&n",
		"&+CYou clutch at the &+Wice spike &+rimpaling &+Cyour chest as the world fades &+cto &+Lblack...&n",
		"$n &+Chits $N&+C with one final &+rbarrage &+Cof &+Wice spikes &+Cand $E falls over clutching $S chest...&n",
		0
	};

	base_dam = missile_dam = ice_spikes_damage(live_rolls, level);

	int mod = get_default_save_mod(victim, ch, SAVING_SPELL, SPELL_ICE_SPIKES);
	if (NewSaves(victim, SAVING_SPELL, mod))
	{
		missile_dam = ice_spikes_saved(base_dam);
	}

	while (num_missiles-- &&
	       spell_damage(ch, victim, missile_dam, SPLDAM_COLD, 0, &messages) == DAM_NONEDEAD)
	{
		// save chance per missile
		if (NewSaves(victim, SAVING_SPELL, mod))
		{
			missile_dam = ice_spikes_saved(base_dam);
		}
		else
		{
			missile_dam = base_dam;
		}
	}
}

// The wall decays after this many pulses.
static int wall_of_air_decay()
{
	return 1800;
}

// By the walker's size, the percent chance to break through the wall, and otherwise to be
// knocked down by it. wall_generic adds the walker's stats.
void wall_of_air_chances(int size, int &chance, int &fall_chance)
{
	switch (size)
	{
	case SIZE_NONE:
	case SIZE_TINY:
	case SIZE_SMALL:
		chance = 15;
		fall_chance = 20;
		break;
	case SIZE_MEDIUM:
		chance = 25;
		fall_chance = 15;
		break;
	case SIZE_LARGE:
	case SIZE_HUGE:
		chance = 50;
		fall_chance = 10;
		break;
	case SIZE_GIANT:
	case SIZE_GARGANTUAN:
		chance = 70;
		fall_chance = 0;
		break;
	case SIZE_DEFAULT:
	default:
		chance = 0;
		fall_chance = 100;
		break;
	}
}

// wall_generic rolls this against each chance, and adds this to the walker's chance to pass
// and takes it from the chance to fall.
int wall_of_air_roll(const Rolls &rolls)
{
	return rolls.number(1, 100);
}

int wall_of_air_stat_bonus(P_char ch)
{
	return (GET_C_AGI(ch) + GET_C_STR(ch)) / 50;
}

std::string wall_of_air_facts(P_char /*ch*/)
{
	std::string through, down;
	const struct
	{
		int size;
		const char *name;
	} sizes[] = { { SIZE_SMALL, "small" },
		      { SIZE_MEDIUM, "medium" },
		      { SIZE_LARGE, "large" },
		      { SIZE_GIANT, "giant" } };
	for (const auto &entry : sizes)
	{
		int chance, fall_chance;
		wall_of_air_chances(entry.size, chance, fall_chance);
		through +=
			(through.empty() ? "" : ", ") + std::to_string(chance) + "% " + entry.name;
		down += (down.empty() ? "" : ", ") + std::to_string(fall_chance) + "% " +
			entry.name;
	}
	return fact("Wall lasts", real_time(wall_of_air_decay())) +
	       fact("Breaking through", through) + fact("Else knocked down", down) +
	       "  Agility plus strength, over 50, adds to the first and cuts the second.\n"
	       "  Doors, blocked, secret, one-way and walled exits cannot take a wall.\n"
	       "  Tiny counts as small, huge as large and gargantuan as giant.\n";
}

void spell_wall_of_air(int level, P_char ch, char *arg, int /*type*/, P_char /*tar_ch*/,
		       P_obj /*tar_obj*/)
{
	char buf1[MAX_STRING_LENGTH], buf2[MAX_STRING_LENGTH], dir_string[MAX_INPUT_LENGTH];
	int var = 0;

	one_argument(arg, dir_string);
	var = dir_from_keyword(dir_string);

	if (!exit_wallable(ch->in_room, var, ch))
	{
		send_to_char("It's not possible to wall in that direction.\n", ch);
		return;
	}

	if (create_walls(
		    ch->in_room, var, ch, level, WALL_OF_AIR, level, wall_of_air_decay(),
		    "&+wa wall of air&n",
		    "&+WThe &+Cwinds &+Wappear to be especially strong coming from the %s&+W!&n",
		    ITEM_NONE))
	{
		snprintf(buf1, MAX_STRING_LENGTH,
			 "&+WThe winds pick up &+Rviolently &+Wto the %s!&n\r\n", dirs[var]);
		snprintf(buf2, MAX_STRING_LENGTH,
			 "&+WThe winds pick up &+Rviolently &+Wto the %s!&n\r\n",
			 dirs[rev_dir[var]]);

		send_to_room(buf1, ch->in_room);
		send_to_room(buf2, (world[ch->in_room].dir_option[var])->to_room);
	}
}
