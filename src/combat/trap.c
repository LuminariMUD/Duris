/****************************************************************************
 *
 *  File: trap.c                                                Part of Duris
 *  Usage: traps: setting, removing, listing, triggers, and damage
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
#include "core/utils.h"
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include "combat/damage.h"
#include "magic/spells.h"
#include "combat/trap.h"
#include <array>
#include <algorithm>
#include <new>
#include <vector>

extern P_desc descriptor_list;
extern P_index mob_index;
extern P_index obj_index;
extern P_obj object_list;
extern P_room world;
extern int top_of_world;

#define TRAP_DAM_SLEEP 0
#define TRAP_DAM_TELEPORT 1
#define TRAP_DAM_FIRE 2
#define TRAP_DAM_COLD 3
#define TRAP_DAM_ACID 4
#define TRAP_DAM_ENERGY 5
#define TRAP_DAM_BLUNT 6
#define TRAP_DAM_PIERCE 7
#define TRAP_DAM_SLASH 8
#define TRAP_DAM_DISPEL 9
#define TRAP_DAM_GATE 10
#define TRAP_DAM_SUMMON 11
#define TRAP_DAM_WITHER 12
#define TRAP_DAM_HARM 13
#define TRAP_DAM_POISON 14
#define TRAP_DAM_PARALYSIS 15
#define TRAP_DAM_STUN 16

#define TRAP_EFF_MOVE BIT_1 /* trigger on movement */
#define TRAP_EFF_OBJECT BIT_2 /* trigger on get or put */
#define TRAP_EFF_ROOM BIT_3 /* affect all in room */
#define TRAP_EFF_NORTH BIT_4 /* movement in this direction */
#define TRAP_EFF_EAST BIT_5
#define TRAP_EFF_SOUTH BIT_6
#define TRAP_EFF_WEST BIT_7
#define TRAP_EFF_UP BIT_8
#define TRAP_EFF_DOWN BIT_9
#define TRAP_EFF_OPEN BIT_10 /* trigger on open */
#define TRAP_EFF_MULTI BIT_11
#define TRAP_EFF_GLYPH BIT_12

struct trap_creature_profile
{
	int object, type, mobile, count, cap;
};

static const trap_creature_profile *trap_creature_for(int vnum, int type)
{
	static const trap_creature_profile profiles[] = {
		{ 41361, TRAP_DAM_GATE, 200, 1, 1 },	 { 42290, TRAP_DAM_GATE, 200, 1, 1 },
		{ 32820, TRAP_DAM_SUMMON, 32861, 3, 6 }, { 32870, TRAP_DAM_SUMMON, 32861, 3, 6 },
		{ 32835, TRAP_DAM_SUMMON, 32861, 1, 6 }, { 32846, TRAP_DAM_SUMMON, 32871, 1, 1 },
		{ 41927, TRAP_DAM_SUMMON, 200, 1, 1 },
	};
	for (const auto &profile : profiles)
		if (profile.object == vnum && profile.type == type)
			return &profile;
	return nullptr;
}

bool trap_configuration_valid(int vnum, int type, int level)
{
	if (type >= TRAP_DAM_SLEEP && type <= TRAP_DAM_SLASH)
		return true;
	if (type < TRAP_DAM_DISPEL || type > TRAP_DAM_STUN || level < 0)
		return false;
	return (type != TRAP_DAM_GATE && type != TRAP_DAM_SUMMON) || trap_creature_for(vnum, type);
}

static bool trap_damage_supported(P_obj obj)
{
	if (trap_configuration_valid(OBJ_VNUM(obj), obj->trap_dam, obj->trap_level) &&
	    (obj->trap_dam < TRAP_DAM_DISPEL || obj->trap_charge >= -1))
		return true;
	logit(LOG_WIZ,
	      "Trap object %d has invalid configuration (type %d, level %d, charges %d); charge preserved.",
	      OBJ_VNUM(obj), obj->trap_dam, obj->trap_level, obj->trap_charge);
	return false;
}

void do_trapremove(P_char ch, char *argument, int /*cmd*/)
{
	P_obj obj;
	char arg1[MAX_INPUT_LENGTH];

	argument = one_argument(argument, arg1);

	if (!(obj = get_obj_vis(ch, arg1)))
	{
		send_to_char("That is not here!\r\n", ch);
		return;
	}
	if (obj->trap_charge != 0)
	{
		obj->trap_charge = 0;
		send_to_char("Trap disarmed.\r\n", ch);
	}
	else
	{
		send_to_char("Trap has no charges.\r\n", ch);
	}
	return;
}

void do_trapstat(P_char ch, char *argument, int /*cmd*/)
{
	char buf[MAX_STRING_LENGTH];
	P_obj obj;

	if (!*argument)
		return;

	if (!(obj = get_obj_vis(ch, argument)))
	{
		send_to_char("That is not here!\r\n", ch);
		return;
	}
	if (obj->trap_charge)
	{
		send_to_char("That object is registered as a trap.\r\n", ch);
	}
	else
	{
		send_to_char("That object is not registered as a trap.\r\n", ch);
	}
	switch (obj->trap_dam)
	{
	case TRAP_DAM_SLEEP:
		send_to_char("Damage type is sleep.\r\n", ch);
		break;
	case TRAP_DAM_TELEPORT:
		send_to_char("Damage type is teleport.\r\n", ch);
		break;
	case TRAP_DAM_FIRE:
		send_to_char("Damage type is fire.\r\n", ch);
		break;
	case TRAP_DAM_COLD:
		send_to_char("Damage type is frost.\r\n", ch);
		break;
	case TRAP_DAM_ACID:
		send_to_char("Damage type is acid.\r\n", ch);
		break;
	case TRAP_DAM_ENERGY:
		send_to_char("Damage type is energy.\r\n", ch);
		break;
	case TRAP_DAM_BLUNT:
		send_to_char("Damage type is blunt.\r\n", ch);
		break;
	case TRAP_DAM_PIERCE:
		send_to_char("Damage type is pierce.\r\n", ch);
		break;
	case TRAP_DAM_SLASH:
		send_to_char("Damage type is slash.\r\n", ch);
		break;
	case TRAP_DAM_DISPEL:
	case TRAP_DAM_GATE:
	case TRAP_DAM_SUMMON:
	case TRAP_DAM_WITHER:
	case TRAP_DAM_HARM:
	case TRAP_DAM_POISON:
	case TRAP_DAM_PARALYSIS:
	case TRAP_DAM_STUN:
	{
		static const char *names[] = { "dispel", "gate",   "summon",	      "wither",
					       "harm",	 "poison", "minor paralysis", "stun" };
		send_to_char_f(ch, "Damage type is %s.\r\n",
			       names[obj->trap_dam - TRAP_DAM_DISPEL]);
		if (!trap_configuration_valid(OBJ_VNUM(obj), obj->trap_dam, obj->trap_level))
			send_to_char("Invalid creature profile or level; this trap is inert.\r\n",
				     ch);
		break;
	}
	default:
		send_to_char_f(ch,
			       "Damage type %d is unsupported; this trap needs builder repair.\r\n",
			       obj->trap_dam);
		break;
	}

	if (obj->trap_eff == 0)
	{
		send_to_char("The trap has no effect.\r\n", ch);
	}
	else
	{
		if (IS_SET(obj->trap_eff, TRAP_EFF_MOVE))
		{
			if (IS_SET(obj->trap_eff, TRAP_EFF_NORTH))
				send_to_char("The trap affects movement to the north.\r\n", ch);
			if (IS_SET(obj->trap_eff, TRAP_EFF_SOUTH))
				send_to_char("The trap affects movement to the south.\r\n", ch);
			if (IS_SET(obj->trap_eff, TRAP_EFF_EAST))
				send_to_char("The trap affects movement to the east.\r\n", ch);
			if (IS_SET(obj->trap_eff, TRAP_EFF_WEST))
				send_to_char("The trap affects movement to the west.\r\n", ch);
			if (IS_SET(obj->trap_eff, TRAP_EFF_UP))
				send_to_char("The trap affects movement up.\r\n", ch);
			if (IS_SET(obj->trap_eff, TRAP_EFF_DOWN))
				send_to_char("The trap affects movement down.\r\n", ch);
		}
		if (IS_SET(obj->trap_eff, TRAP_EFF_OBJECT))
			send_to_char("The trap is set off by get or put.\r\n", ch);
		if (IS_SET(obj->trap_eff, TRAP_EFF_OPEN))
			send_to_char("The trap is set off when opened.\r\n", ch);
		if (IS_SET(obj->trap_eff, TRAP_EFF_ROOM))
			send_to_char("The trap affects the whole room.\r\n", ch);
		if (IS_SET(obj->trap_eff, TRAP_EFF_GLYPH))
			send_to_char(
				"GLYPH: effects 9-16 allow movement after safe revalidation.\r\n",
				ch);
		if (IS_SET(obj->trap_eff, TRAP_EFF_MULTI))
			send_to_char(
				"MULTI: effects 9-16 are unlimited while charges are nonzero.\r\n",
				ch);
	}
	snprintf(buf, MAX_STRING_LENGTH, "Trap Charges left: %d.\r\n", obj->trap_charge);
	send_to_char(buf, ch);
	snprintf(buf, MAX_STRING_LENGTH, "Trap level: %d\r\n", obj->trap_level);
	send_to_char(buf, ch);
	return;
}

void do_traplist(P_char ch, char * /*argument*/, int /*cmd*/)
{
	char buf[MAX_INPUT_LENGTH];
	P_obj obj;
	bool found = FALSE;

	for (obj = object_list; obj != NULL; obj = obj->next)
	{
		if (!CAN_SEE_OBJ(ch, obj) || !obj->trap_charge)
			continue;

		found = TRUE;
		snprintf(buf, MAX_INPUT_LENGTH, "%s \r\n", where_obj(obj, FALSE));
		send_to_char(buf, ch);
	}
	if (!found)
		send_to_char("No traps found.\r\n", ch);

	return;
}

void do_trapset(P_char ch, char *argument, int /*cmd*/)
{
	static const char *names[] = { "sleep",	    "teleport", "fire",	  "cold",  "acid",
				       "energy",    "blunt",	"pierce", "slash", "dispel",
				       "gate",	    "summon",	"wither", "harm",  "poison",
				       "paralysis", "stun" };
	char item[MAX_INPUT_LENGTH], field[MAX_INPUT_LENGTH], value[MAX_INPUT_LENGTH];
	argument = one_argument(argument, item);
	argument = one_argument(argument, field);
	one_argument(argument, value);
	if (!*item || !*field)
	{
		send_to_char(
			"Syntax: trapset <object> <field> <value>\r\n"
			"Fields: move, object, room, open, multi, glyph, damage, charge, level\r\n"
			"Move: north, east, south, west, up, down, all\r\n"
			"Damage: sleep, teleport, fire, cold, acid, energy, blunt, pierce, slash,\r\n"
			"        dispel, gate, summon, wither, harm, poison, paralysis, stun\r\n"
			"Charge: -1..100 (0 disarms). Level: 0..32767 (0 defaults to 25).\r\n"
			"Effects 9..16 cap positive levels at 100; gate/summon require a listed profile.\r\n"
			"Object/room/open/multi/glyph set their flag without a value.\r\n",
			ch);
		return;
	}
	P_obj obj;
	P_char dummy;
	if (!generic_find(item, FIND_OBJ_INV | FIND_OBJ_ROOM | FIND_NO_TRACKS, ch, &dummy, &obj))
	{
		send_to_char("Nothing like that here!\r\n", ch);
		return;
	}
	int effect = obj->trap_eff, type = obj->trap_dam;
	int charge = obj->trap_charge, level = obj->trap_level;
	if (!str_cmp(field, "move"))
	{
		static const char *directions[] = { "north", "east", "south", "west", "up", "down" };
		int mask = 0;
		for (int direction = 0; direction < 6; ++direction)
			if (!str_cmp(value, directions[direction]) || !str_cmp(value, "all"))
				mask |= TRAP_EFF_NORTH << direction;
		if (!mask)
		{
			send_to_char("Specify north, east, south, west, up, down or all.\r\n", ch);
			return;
		}
		effect |= TRAP_EFF_MOVE | mask;
	}
	else if (!str_cmp(field, "object"))
		effect |= TRAP_EFF_OBJECT;
	else if (!str_cmp(field, "room"))
		effect |= TRAP_EFF_ROOM;
	else if (!str_cmp(field, "open"))
		effect |= TRAP_EFF_OPEN;
	else if (!str_cmp(field, "multi"))
		effect |= TRAP_EFF_MULTI;
	else if (!str_cmp(field, "glyph"))
		effect |= TRAP_EFF_GLYPH;
	else if (!str_cmp(field, "damage"))
	{
		type = -1;
		for (int candidate = 0; candidate <= TRAP_DAM_STUN; ++candidate)
			if (!str_cmp(value, names[candidate]))
				type = candidate;
		if (type < 0)
		{
			send_to_char("That damage type is not supported.\r\n", ch);
			return;
		}
	}
	else if (!str_cmp(field, "charge") || !str_cmp(field, "level"))
	{
		char *end;
		const long number = strtol(value, &end, 10);
		const bool changing_level = !str_cmp(field, "level");
		if (!*value || *end || number < (changing_level ? 0 : -1) ||
		    number > (changing_level ? 32767 : 100))
		{
			send_to_char("Charge range is -1..100; level range is 0..32767.\r\n", ch);
			return;
		}
		if (changing_level)
			level = number;
		else
			charge = number;
	}
	else
	{
		send_to_char("That is not an allowed field.\r\n", ch);
		return;
	}
	if (!trap_configuration_valid(OBJ_VNUM(obj), type, level))
	{
		send_to_char("Invalid trap type, creature profile or level; nothing changed.\r\n",
			     ch);
		return;
	}
	obj->trap_eff = effect;
	obj->trap_dam = type;
	obj->trap_charge = charge;
	obj->trap_level = level;
	send_to_char("Trap field set.\r\n", ch);
}

static bool trap_target_eligible(P_char ch)
{
	return IS_ALIVE(ch) && !IS_TRUSTED(ch) && (!IS_NPC(ch) || IS_PC_PET(ch)) &&
	       !IS_SET(ch->runtime_flags, CHAR_RFLAG_TRAP_CASTER);
}

static void trap_restored_damage(P_char ch, P_obj obj)
{
	if (!trap_target_eligible(ch) || ch->in_room < 0 || ch->in_room > top_of_world)
		return;
	const uint64_t actor_id = ch->runtime_id, object_uid = obj->obj_uid;
	const int room = ch->in_room, type = obj->trap_dam, effect = obj->trap_eff;
	const int raw_level = obj->trap_level, charges = obj->trap_charge;
	const int level = MIN(raw_level ? raw_level : 25, 100);
	const auto ready = [&]()
	{
		ch = find_character_by_runtime_id(actor_id);
		P_obj live = find_live_object(obj, object_uid);
		return ch && trap_target_eligible(ch) && ch->in_room == room && live &&
		       live->trap_dam == type && live->trap_eff == effect &&
		       live->trap_level == raw_level && live->trap_charge == charges;
	};
	const auto commit_charge = [&]()
	{
		if (charges > 0 && !IS_SET(effect, TRAP_EFF_MULTI))
			--obj->trap_charge;
	};

	if (const auto *profile = trap_creature_for(OBJ_VNUM(obj), type))
	{
		int population = 0;
		for (P_char mob = world[room].people; mob; mob = mob->next_in_room)
			if (IS_NPC(mob) && IS_ALIVE(mob) && GET_VNUM(mob) == profile->mobile)
				++population;
		if (population + profile->count > profile->cap)
			return;
		std::array<uint64_t, 3> created = {};
		const auto rollback = [&]()
		{
			for (uint64_t id : created)
				if (P_char mob = find_character_by_runtime_id(id))
					extract_char(mob);
		};
		// read_mobile registers, converts and schedules each ordinary NPC. Allocate
		// the complete batch before any member is exposed in the source room.
		for (int index = 0; index < profile->count; ++index)
		{
			P_char mob = read_mobile(profile->mobile, VIRTUAL);
			if (mob)
				created[index] = mob->runtime_id;
			if (!mob || !ready())
			{
				rollback();
				return;
			}
		}
		for (int index = 0; index < profile->count; ++index)
		{
			P_char mob = find_character_by_runtime_id(created[index]);
			const bool placed = mob && char_to_room(mob, room, -2);
			mob = find_character_by_runtime_id(created[index]);
			if (!placed || !mob || mob->in_room != room || !ready())
			{
				rollback();
				return;
			}
		}
		for (uint64_t id : created)
		{
			P_char mob = find_character_by_runtime_id(id);
			if (id && (!mob || !IS_ALIVE(mob) || mob->in_room != room))
			{
				rollback();
				return;
			}
		}
		commit_charge();
		for (uint64_t id : created)
		{
			P_char mob = find_character_by_runtime_id(id);
			ch = find_character_by_runtime_id(actor_id);
			if (!mob || !ch || !trap_target_eligible(ch) || mob->in_room != room ||
			    ch->in_room != room)
				continue;
			if (type == TRAP_DAM_GATE)
			{
				SET_BIT(mob->specials.act, ACT_MEMORY);
				mob->only.npc->trap_gate_target_runtime_id = actor_id;
				if (IS_PC(ch))
					remember(mob, ch, false);
			}
			else
				MobStartFight(mob, ch);
		}
		return;
	}

	std::vector<uint64_t> targets;
	try
	{
		if (IS_SET(effect, TRAP_EFF_ROOM))
		{
			for (P_char victim = world[room].people; victim;
			     victim = victim->next_in_room)
				if (trap_target_eligible(victim))
					targets.push_back(victim->runtime_id);
		}
		else
			targets.push_back(actor_id);
	}
	catch (const std::bad_alloc &)
	{
		return;
	}
	P_char caster = read_mobile(14, VIRTUAL, false);
	if (!caster)
		return;
	const uint64_t caster_id = caster->runtime_id;
	caster->player.level = level;
	SET_BIT(caster->runtime_flags, CHAR_RFLAG_TRAP_CASTER);
	const bool placed = char_to_room(caster, room, -2);
	caster = find_character_by_runtime_id(caster_id);
	if (!placed || !caster || !IS_ALIVE(caster) || caster->in_room != room || !ready())
	{
		if (caster)
			extract_char(caster);
		return;
	}
	commit_charge();
	for (uint64_t target : targets)
	{
		caster = find_character_by_runtime_id(caster_id);
		P_char victim = find_character_by_runtime_id(target);
		if (!caster || !IS_ALIVE(caster) || caster->in_room != room)
			break;
		if (!victim || victim->in_room != room || !trap_target_eligible(victim))
			continue;
		switch (type)
		{
		case TRAP_DAM_DISPEL:
			spell_dispel_magic(level, caster, nullptr, SPELL_TYPE_SPELL, victim,
					   nullptr);
			break;
		case TRAP_DAM_WITHER:
			spell_wither(level, caster, nullptr, SPELL_TYPE_SPELL, victim, nullptr);
			break;
		case TRAP_DAM_HARM:
			spell_harm(level, caster, nullptr, SPELL_TYPE_SPELL, victim, nullptr);
			break;
		case TRAP_DAM_POISON:
			spell_poison(level, caster, nullptr, SPELL_TYPE_SPELL, victim, nullptr);
			break;
		case TRAP_DAM_PARALYSIS:
			if (!IS_AFFECTED2(victim, AFF2_MINOR_PARALYSIS | AFF2_MAJOR_PARALYSIS))
				spell_minor_paralysis(BOUNDED(4, level / 5, 16), caster, nullptr,
						      SPELL_TYPE_SPELL, victim, nullptr);
			break;
		case TRAP_DAM_STUN:
			if (!resists_spell(caster, victim))
				Stun(victim, caster, BOUNDED(1, level / 20, 4) * WAIT_SEC, true);
			break;
		}
	}
	if ((caster = find_character_by_runtime_id(caster_id)))
		extract_char(caster);
}

bool movement_trap_trigger(P_obj obj, int direction)
{
	return obj->trap_charge && IS_SET(obj->trap_eff, TRAP_EFF_MOVE) &&
	       IS_SET(obj->trap_eff, TRAP_EFF_NORTH << direction);
}

bool checkmovetrap(P_char ch, int dir, std::vector<std::pair<P_obj, uint64_t>> *sprung)
{
	if (dir < DIR_NORTH || dir > DIR_DOWN || !trap_target_eligible(ch) || ch->in_room < 0 ||
	    ch->in_room > top_of_world)
		return false;
	const int room = ch->in_room;
	const uint64_t actor_id = ch->runtime_id;
	for (P_obj obj = world[room].contents; obj; obj = obj->next_content)
	{
		if (!movement_trap_trigger(obj, dir))
			continue;
		const std::pair<P_obj, uint64_t> identity = { obj, obj->obj_uid };
		if (sprung && std::find(sprung->begin(), sprung->end(), identity) != sprung->end())
			continue;
		if (!trap_damage_supported(obj))
			continue;
		const bool glyph = sprung && obj->trap_dam >= TRAP_DAM_DISPEL &&
				   IS_SET(obj->trap_eff, TRAP_EFF_GLYPH);
		if (glyph)
		{
			try
			{
				sprung->push_back(identity);
			}
			catch (const std::bad_alloc &)
			{
				return true;
			}
		}
		trapdamage(ch, obj);
		if (!glyph)
			return true;
		// Return to the movement owner's entire preflight before scanning another
		// trap. No cached character, mount, exit or next-content pointer survives.
		ch = find_character_by_runtime_id(actor_id);
		P_obj live = find_live_object(identity.first, identity.second);
		return !ch || !IS_ALIVE(ch) || ch->in_room != room || !IS_AWAKE(ch) ||
		       IS_IMMOBILE(ch) || IS_STUNNED(ch) || !CAN_ACT(ch) || !live ||
		       !OBJ_ROOM(live) || live->loc.room != room;
	}
	return false;
}

bool checkgetput(P_char ch, P_obj obj)
{
	if (!obj->trap_charge)
		return FALSE;
	if (obj->trap_dam >= TRAP_DAM_DISPEL && !trap_target_eligible(ch))
		return FALSE;

	if (IS_SET(obj->trap_eff, TRAP_EFF_OBJECT) && trap_damage_supported(obj))
	{
		trapdamage(ch, obj);
		return TRUE;
	}
	return FALSE;
}

bool checkopen(P_char ch, P_obj obj)
{
	if (!obj->trap_charge)
		return FALSE;
	if (obj->trap_dam >= TRAP_DAM_DISPEL && !trap_target_eligible(ch))
		return FALSE;

	if (IS_SET(obj->trap_eff, TRAP_EFF_OPEN) && trap_damage_supported(obj))
	{
		trapdamage(ch, obj);
		return TRUE;
	}
	return FALSE;
}

void trapdamage(P_char ch, P_obj obj)
{
	struct affected_type af;
	P_char wch, next_ch;
	int level, dam, numdice, numsides;
	struct damage_messages messages;

	if (!obj->trap_charge)
		return;

	if (!trap_damage_supported(obj))
		return;
	if (obj->trap_dam >= TRAP_DAM_DISPEL)
	{
		trap_restored_damage(ch, obj);
		return;
	}

	if (IS_NPC(ch) && !IS_PC_PET(ch))
		return;

	if (obj->trap_charge > 0)
		obj->trap_charge--;

	if (obj->trap_level)
		level = obj->trap_level;
	else
		level = 25;

	// Format: xxyy where xx d yy is the amount of damage.
	if (level > 100)
	{
		numdice = level / 100;
		numsides = level % 100;
	}
	else
	{
		numdice = level;
		numsides = 10;
	}

	messages.obj = obj;
	dam = dice(numdice, numsides);

	switch (obj->trap_dam)
	{
	case TRAP_DAM_SLEEP:
		if (!IS_SET(obj->trap_eff, TRAP_EFF_ROOM))
		{
			if (IS_AFFECTED(ch, AFF_SLEEP) || IS_TRUSTED(ch))
			{
				return;
			}

			bzero(&af, sizeof(af));
			af.type = SPELL_SLEEP;
			af.duration = 1 + number(0, level / 10);
			af.bitvector = AFF_SLEEP;
			affect_to_char(ch, &af);

			act("&+LA strange gas pours forth from $p, making you feel very sleepy ..... zzzzzz",
			    FALSE, ch, obj, 0, TO_CHAR);
			if (GET_OPPONENT(ch))
				stop_fighting(ch);

			if (GET_STAT(ch) > STAT_SLEEPING)
			{
				act("&+LA strange gas pours forth from $p, and $n goes to sleep.",
				    TRUE, ch, obj, 0, TO_ROOM);
				SET_POS(ch, GET_POS(ch) + STAT_SLEEPING);
			}
		}
		else
		{
			LOOP_THRU_PEOPLE(wch, ch)
			{
				if (IS_AFFECTED(wch, AFF_SLEEP) || IS_TRUSTED(wch))
					continue;

				bzero(&af, sizeof(af));
				af.type = SPELL_SLEEP;
				af.duration = 1 + number(0, level / 20);
				af.bitvector = AFF_SLEEP;
				affect_to_char(wch, &af);

				act("&+LA strange gas pours forth from $p, making you feel very sleepy ..... zzzzzz",
				    FALSE, wch, obj, 0, TO_CHAR);
				if (GET_OPPONENT(wch))
					stop_fighting(wch);
				if (GET_STAT(wch) > STAT_SLEEPING)
				{
					SET_POS(wch, GET_POS(wch) + STAT_SLEEPING);
				}
			}
		}
		break;
	case TRAP_DAM_TELEPORT:
		if (!IS_SET(obj->trap_eff, TRAP_EFF_ROOM))
		{
			send_to_char("You hear a strange... POP!\r\n", ch);
			spell_teleport(60, ch, 0, 0, ch, 0);
		}
		else
		{
			send_to_room("You hear a strange... POP!\r\n", ch->in_room);

			for (wch = world[ch->in_room].people; wch; wch = next_ch)
			{
				next_ch = wch->next_in_room;

				spell_teleport(60, wch, 0, 0, wch, 0);
			}
		}
		break;
	case TRAP_DAM_FIRE:
		messages.attacker = "The &+rfireball&N hits $N.";
		messages.victim =
			"You are enveloped in &+rflames from a fireball&N sent by $P - OUCH!";
		messages.room = "The &+rfireball&N explodes into the face of $N.";
		messages.death_attacker =
			"The &+rfireball&N hits $N with full force, causing an immediate death.";
		messages.death_victim =
			"As the &+rfireball&N hits you, you burst into &+rflames&N and die.";
		messages.death_room =
			"The heat from the &+rfireball&N turns $N into a charred corpse.";

		if (!IS_SET(obj->trap_eff, TRAP_EFF_ROOM))
		{
			act("A &+rfireball&n shoots out of $p and hits $n!", FALSE, ch, obj, 0,
			    TO_ROOM);
			act("A &+rfireball&n shoots out of $p and hits you!", TRUE, ch, obj, 0,
			    TO_CHAR);

			spell_damage(ch, ch, dam, SPLDAM_FIRE, SPLDAM_NOSHRUG | SPLDAM_NODEFLECT,
				     &messages);
		}
		else
		{
			act("A fireball shoots out of $p and hits everyone in the room!", FALSE, ch,
			    obj, 0, TO_ROOM);
			act("A fireball shoots out of $p and hits everyone in the room!", FALSE, ch,
			    obj, 0, TO_CHAR);
			for (wch = world[ch->in_room].people; wch; wch = next_ch)
			{
				next_ch = wch->next_in_room;

				spell_damage(wch, wch, dam, SPLDAM_FIRE,
					     SPLDAM_NOSHRUG | SPLDAM_NODEFLECT, &messages);
			}
		}
		break;
	case TRAP_DAM_COLD:
		messages.attacker = "&+BThe blast of &+ccold&+B strikes $N &+Bdead on.";
		messages.victim =
			"&+BThe blast of &+ccold&+B strikes you dead on, freezing up your limbs! BRRR.";
		messages.room = "&+BThe blast of &+ccold&+B hits $N&+B, who screams out in pain!";
		messages.death_attacker =
			"&+BThe blast of &+ccold&+B leaves $N &+Cfrozen &+Bsolid!";
		messages.death_victim =
			"&+BYour body turns to &+Cice&+B the blast of &+ccold&+B hits you, AARRGHGHHGH!!";
		messages.death_room =
			"&+BThe blast of &+ccold&+B hits $N&+B, who &+Cfreezes solid&+B and dies instantly!";

		if (!IS_SET(obj->trap_eff, TRAP_EFF_ROOM))
		{
			act("&+BA blast of &+cfrost&+B emanates from $p&+B!", FALSE, ch, obj, NULL,
			    TO_ROOM);
			act("&+BA blast of &+cfrost&+B emanates from $p&+B!", FALSE, ch, obj, NULL,
			    TO_CHAR);

			spell_damage(ch, ch, dam, SPLDAM_COLD, SPLDAM_NOSHRUG | SPLDAM_NODEFLECT,
				     &messages);
		}
		else
		{
			act("&+BA blast of &+cfrost&+B emanates from $p&+B and fills the room!",
			    FALSE, ch, obj, NULL, TO_ROOM);
			act("&+BA blast of &+cfrost&+B emanates from $p&+B and fills the room!",
			    FALSE, ch, obj, NULL, TO_CHAR);
			for (wch = world[ch->in_room].people; wch; wch = next_ch)
			{
				next_ch = wch->next_in_room;

				spell_damage(wch, wch, dam, SPLDAM_COLD,
					     SPLDAM_NOSHRUG | SPLDAM_NODEFLECT, &messages);
			}
		}
		break;
	case TRAP_DAM_ACID:
		messages.attacker = "The blast of &+Gacid&n douses $N.";
		messages.victim = "The blast of &+Gacid&n douses you.";
		messages.room = "The blast of &+Gacid&n hits $N, who screams out in pain!";
		messages.death_attacker =
			"The blast of &+Gacid&n turns $N into a &+gsticky ooze&n.";
		messages.death_victim =
			"Your body turns to &+gooze&n as the blast of &+Gacid&n hits you!";
		messages.death_room = "The blast of &+Gacid&n turns $N into a &+gsticky puddle&n.";

		if (!IS_SET(obj->trap_eff, TRAP_EFF_ROOM))
		{
			act("A blast of acid erupts from $p, burning your skin!", FALSE, ch, obj,
			    NULL, TO_CHAR);
			act("A blast of acid erupts from $p, burning $n's skin!", FALSE, ch, obj,
			    NULL, TO_ROOM);

			spell_damage(ch, ch, dam, SPLDAM_ACID, SPLDAM_NOSHRUG | SPLDAM_NODEFLECT,
				     &messages);
		}
		else
		{
			act("A blast of acid erupts from $p, burning your skin!", FALSE, ch, obj,
			    NULL, TO_ROOM);
			act("A blast of acid erupts from $p, burning your skin!", FALSE, ch, obj,
			    NULL, TO_CHAR);

			for (wch = world[ch->in_room].people; wch; wch = next_ch)
			{
				next_ch = wch->next_in_room;

				spell_damage(wch, wch, dam, SPLDAM_ACID,
					     SPLDAM_NOSHRUG | SPLDAM_NODEFLECT, &messages);
			}
		}
		break;
	case TRAP_DAM_ENERGY:
		messages.attacker = "The &+cpulse&n of &+Yenergy&n shocks $N.";
		messages.victim = "The &+cpulse&n of &+Yenergy&n shocks you.";
		messages.room = "The &+cpulse&n of &+Yenergy&n shocks $N.";
		messages.death_attacker = "The &+cpulse&n of &+Yenergy&n turns $N to &+Lash&n.";
		messages.death_victim = "The &+cpulse&n of &+Yenergy&n turns you to &+wash&n.";
		messages.death_room =
			"The &+cpulse&n of &+Yenergy&n turns $N to a pile of &+Ycrackling&n &+wash&n.";

		if (!IS_SET(obj->trap_eff, TRAP_EFF_ROOM))
		{
			act("A &+cpulse&n of &+Yenergy&n from $p zaps $n!", FALSE, ch, obj, NULL,
			    TO_ROOM);
			act("A &+cpulse&n of &+Yenergy&n from $p zaps you!", FALSE, ch, obj, NULL,
			    TO_CHAR);

			spell_damage(ch, ch, dam, SPLDAM_LIGHTNING,
				     SPLDAM_NOSHRUG | SPLDAM_NODEFLECT, &messages);
		}
		else
		{
			act("A &+cpulse&n of &+Yenergy&n from $p zaps you!", FALSE, ch, obj, NULL,
			    TO_ROOM);
			act("A &+cpulse&n of &+Yenergy&n from $p zaps you!", FALSE, ch, obj, NULL,
			    TO_CHAR);

			for (wch = world[ch->in_room].people; wch; wch = next_ch)
			{
				next_ch = wch->next_in_room;

				spell_damage(wch, wch, dam, SPLDAM_LIGHTNING,
					     SPLDAM_NOSHRUG | SPLDAM_NODEFLECT, &messages);
			}
		}
		break;
	case TRAP_DAM_BLUNT:
		if (!IS_SET(obj->trap_eff, TRAP_EFF_ROOM))
		{
			act("$n sets off a trap on $p and a blunt object flies forth!", FALSE, ch,
			    obj, NULL, TO_ROOM);
			act("You are hit by a blunt object from $p!", FALSE, ch, obj, NULL,
			    TO_CHAR);

			damage(ch, ch, dam, TYPE_TRAP);
		}
		else
		{
			act("$n sets off a trap on $p and you are hit by a flying object!", FALSE,
			    ch, obj, NULL, TO_ROOM);
			act("You are hit by a flying blunt object from $p!", FALSE, ch, obj, NULL,
			    TO_CHAR);

			for (wch = world[ch->in_room].people; wch; wch = next_ch)
			{
				next_ch = wch->next_in_room;

				damage(wch, wch, dam, TYPE_TRAP);
			}
		}
		break;
	case TRAP_DAM_PIERCE:
		if (!IS_SET(obj->trap_eff, TRAP_EFF_ROOM))
		{
			act("$n sets off a trap on $p and is pierced in the chest!", FALSE, ch, obj,
			    NULL, TO_ROOM);
			act("You set off a trap on $p and are pierced through the chest!", FALSE,
			    ch, obj, NULL, TO_CHAR);

			damage(ch, ch, dam, TYPE_TRAP);
		}
		else
		{
			act("$n sets off a trap on $p and you are hit by a piercing object!", FALSE,
			    ch, obj, NULL, TO_ROOM);
			act("You set off a trap on $p and are pierced through the chest!", FALSE,
			    ch, obj, NULL, TO_CHAR);

			for (wch = world[ch->in_room].people; wch; wch = next_ch)
			{
				next_ch = wch->next_in_room;

				damage(wch, wch, dam, TYPE_TRAP);
			}
		}
		break;
	case TRAP_DAM_SLASH:
		if (!IS_SET(obj->trap_eff, TRAP_EFF_ROOM))
		{
			act("$n just got slashed by a trap on $p.", FALSE, ch, obj, NULL, TO_ROOM);
			act("You just got slashed by a trap on $p!", FALSE, ch, obj, NULL, TO_CHAR);

			dam = (dam / 5);
			damage(ch, ch, dam, TYPE_TRAP);
		}
		else
		{
			act("$n set off a trap releasing a blade that slashes you!", FALSE, ch, obj,
			    NULL, TO_ROOM);
			act("You set off a trap releasing blades around the room..", FALSE, ch, obj,
			    NULL, TO_CHAR);
			act("One of the blades slashes you in the chest!", FALSE, ch, obj, NULL,
			    TO_CHAR);

			for (wch = world[ch->in_room].people; wch; wch = next_ch)
			{
				next_ch = wch->next_in_room;

				damage(wch, wch, dam, TYPE_TRAP);
			}
		}
		break;
	}
}
