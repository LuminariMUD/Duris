/*****************************************************************************
 *  File: specs.set.c   (Part of Duris)                                      *
 *  Usage: named and random equipment set procedures                         *
 *  Copyright  1990, 1991 - see 'license.doc' for complete information.      *
 *  Copyright 1994 - 2008 - Duris Systems Ltd.                               *
 *****************************************************************************/

#include "core/prototypes.h"
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "core/utils.h"
#include <ctype.h>
#include <stdio.h>
#include <strings.h>
#include "combat/damage.h"
#include "combat/justice.h"
#include "world/specs.prototypes.h"
#include "magic/spells.h"
#include "world/weather.h"
#include "item/named_sets.h"
#include "item/named_set_effects.h"
#include "item/named_set_origin.h"
#include "world/vnum.obj.h"

/*
   external variables
 */

extern P_index obj_index;
extern P_room world;
extern Skill skills[];
extern bool has_skin_spell(P_char);
void bard_dragons(int, P_char, P_char, int);
void event_balance_affects(P_char, P_char, P_obj, void *);
void event_object_proc(P_char, P_char, P_obj, void *);
extern struct zone_data *zone;
extern struct zone_data *zone_table;

const int set_master_vnum[] = { 22063, 22237, 22621, 45530, 45531, 82545, 75857, 0

};
const char *set_master_text[] = {
	"",
	"",
	"\n&+GMaster set granting:\n&+W*Stronger armor\n",
	"\n&+GMaster set granting:\n&+W*Stronger armor\n&+W*Defense vs spells\n",
	"\n&+GMaster set granting:\n&+W*Stronger armor\n&+W*Defense vs spells\n&+W*Hitroll\n",
	"\n&+GMaster set granting:\n&+W*Stronger armor\n&+W*Defense vs spells\n&+W*Hitroll\n&+W*Detect Invisbility\n",
	"\n&+GMaster set granting:\n&+W*Stronger armor\n&+W*Defense vs spells\n&+W*Hitroll\n&+W*Detect Invisbility\n&+W*Haste",
	" ",
	" ",
};

int master_set(P_obj obj, P_char ch, int cmd, char * /*arg*/)
{
	struct affected_type af;
	int numb_items = 0;
	int j = 0;
	int k = 0;
	P_obj t_obj;
	int wear_order[] = { 41, 24, 40, 6,  19, 21, 22, 20, 39, 3,  4,	 5, 35,
			     37, 12, 23, 13, 10, 31, 11, 14, 15, 33, 34, 9, 32,
			     1,	 2,  16, 17, 25, 26, 7,	 36, 8,	 38, -1 };

	if (cmd == CMD_SET_PERIODIC)
	{
		return TRUE;
	}

	if (!obj || !OBJ_WORN(obj) || !(ch = obj->loc.wearing) || cmd != CMD_PERIODIC)
	{
		return FALSE;
	}
	if (!IS_ALIVE(ch) || IS_NPC(ch))
	{
		return FALSE;
	}

	// For each slot,
	for (j = 0; wear_order[j] != -1; j++)
	{
		// If there's eq there..
		if (ch->equipment[wear_order[j]])
		{
			t_obj = ch->equipment[wear_order[j]];
			k = 0;
			// for each vnum in masters set..
			while (set_master_vnum[k] > 0)
			{
				// If the vnum matches, increase number of master items.
				if (obj_index[t_obj->R_num].virtual_number == set_master_vnum[k])
				{
					numb_items++;
					break;
				}
				k++;
			}
		}
	}

	// Remove all the old affects.
	affect_from_char(ch, TAG_SET_MASTER);
	bzero(&af, sizeof(af));
	af.type = TAG_SET_MASTER;

	if (numb_items > 6)
		numb_items = 6;
	if (numb_items > 1)
	{
		af.modifier = -20;
		af.location = APPLY_AC;
		affect_to_char(ch, &af);
	}
	if (numb_items > 2)
	{
		af.location = APPLY_SAVING_SPELL;
		af.modifier = -3;
		affect_to_char(ch, &af);
	}
	if (numb_items > 3)
	{
		af.modifier = 5;
		af.location = APPLY_HITROLL;
		affect_to_char(ch, &af);
	}
	if (numb_items > 4)
	{
		af.modifier = 0;
		af.location = 0;
		af.bitvector = AFF_DETECT_INVISIBLE;
		affect_to_char(ch, &af);
	}
	if (numb_items > 5)
	{
		af.bitvector = AFF_HASTE;
		affect_to_char(ch, &af);
	}

	if (numb_items < ch->only.pc->master_set)
	{
		act("Your $q glow of power decrese.", FALSE, ch, obj, obj, TO_CHAR);
		act("$n's $q glow of power decrese.", TRUE, ch, obj, NULL, TO_ROOM);
	}

	if (numb_items > ch->only.pc->master_set && numb_items > 1)
	{
		act("Your $q glow of power increase.", FALSE, ch, obj, obj, TO_CHAR);
		act("$n's $q glow of power increase.", TRUE, ch, obj, NULL, TO_ROOM);
	}

	ch->only.pc->master_set = numb_items;
	return FALSE;
}

typedef int (*set_func)(P_char ch, P_obj obj, int count, int cmd, char *arg);

static int master_set_adapter(P_char ch, P_obj obj, int /*count*/, int cmd, char *arg)
{
	return master_set(obj, ch, cmd, arg);
}

struct random_set_wear_off
{
	void *context;
	int zone;
	char zone_name[256];
};

void check_zone_spells(P_char ch, P_obj obj, int count, int zone, const char *zone_name);

void event_random_set_proc(P_char ch, P_char /*victim*/, P_obj /*obj*/, void *data)
{
	const auto *rdata = static_cast<const random_set_wear_off *>(data);
	struct affected_type *af = get_spell_from_char(ch, TAG_SETPROC, rdata->context);
	if (!af)
		return;
	char buffer[512];
	snprintf(buffer, sizeof buffer, "Spirits of %s no longer support you.\n", rdata->zone_name);
	send_to_char(buffer, ch);
	affect_remove(ch, af);
	check_zone_spells(ch, nullptr, 0, rdata->zone, rdata->zone_name);
}

#define SETMSG_NONE 0
#define SETMSG_PROTECT 1
#define SETMSG_STRENGTH 2

// The wearer's own grant lasts longer than a member's ordinary song, so while it holds, members who
// have lost theirs (only_missing) are granted it again rather than going without.
static void grant_dragons_to_group(P_char ch, int count, int zone, bool only_missing)
{
	P_char next = NULL;
	for (P_char tch = world[ch->in_room].people; tch; tch = next)
	{
		next = tch->next_in_room;

		if ((ch != tch) && !grouped(ch, tch))
			continue;
		if (only_missing && affected_by_spell(tch, SONG_DRAGONS))
			continue;

		named_set_grant group_grant(ch, tch, zone, SONG_DRAGONS);
		bard_dragons(MIN(56, count * 10), ch, tch, SONG_DRAGONS);
	}
}

void apply_zone_spell(P_char ch, int count, const char *zone_name, int zone, P_obj obj, int spell)
{
	if (!named_set_effect_supported(spell))
		return;
	if ((spell == SPELL_HOLY_LIGHT || spell == SPELL_MAGE_FLAME ||
	     spell == SPELL_GLOBE_OF_DARKNESS) &&
	    (IS_AFFECTED4(ch, AFF4_MAGE_FLAME) || IS_AFFECTED4(ch, AFF4_GLOBE_OF_DARKNESS)))
		return;
	// Automatic refreshes must not repeat the manual spell's class rejection.
	if (spell == SPELL_GUARDIAN_SPIRITS && !GET_CLASS(ch, CLASS_SHAMAN))
		return;
	for (const affected_type *affect = ch->affected; affect; affect = affect->next)
	{
		if ((affect->flags & AFFTYPE_SET_AFFECT) && affect->set_owner == ch->runtime_id &&
		    affect->set_spell == spell)
		{
			if (spell == SONG_DRAGONS)
				grant_dragons_to_group(ch, count, zone, true);
			return;
		}
		// Registered aliases can create a different native affect ID. Do not
		// refresh an ordinary cast or a surviving multipart grant through its alias.
		if (spell != SPELL_CONJURE_ELEMENTAL && spell != SPELL_INVIGORATE &&
		    (affect->type == spell ||
		     (affect->type > 0 && affect->type <= MAX_AFFECT_TYPES &&
		      skills[spell].spell_pointer &&
		      skills[affect->type].spell_pointer == skills[spell].spell_pointer)))
			return;
	}

	named_set_grant grant(ch, ch, zone, spell);
	// Summons and instant vitality create no set affects and have their own cooldowns.
	if (spell != SPELL_CONJURE_ELEMENTAL && spell != SPELL_INVIGORATE)
		grant.hold_wearer_output();
	int message = SETMSG_NONE;
	char buffer[512];

	switch (spell)
	{
	case SPELL_REGENERATION:
	case SPELL_ACCEL_HEALING:
	case SPELL_PACTUM_SERPENTIS:
		if (!affected_by_spell(ch, SPELL_REGENERATION) &&
		    !affected_by_spell(ch, SPELL_PACTUM_SERPENTIS) &&
		    !affected_by_spell(ch, SKILL_REGENERATE) &&
		    !affected_by_spell(ch, SPELL_ACCEL_HEALING))
		{
			(skills[spell].spell_pointer)(MIN(56, count * 10), ch, 0, 0, ch, 0);
			message = SETMSG_PROTECT;
		}
		break;
	case SPELL_STONE_SKIN:
		if (!has_skin_spell(ch) && !named_set_cooldown_remaining(ch, spell) &&
		    obj->timer[0] + get_property("timer.stoneskin.generic", 60) < time(NULL))
		{
			spell_stone_skin(MIN(56, count * 5), ch, 0, 0, ch, 0);
			obj->timer[0] = time(NULL);
			start_named_set_cooldown(
				ch, spell, get_property("timer.stoneskin.generic", 60) * WAIT_SEC);
			message = SETMSG_PROTECT;
		}
		break;
	case SPELL_ARMOR:
	case SPELL_BARKSKIN:
	case SPELL_THORNSKIN:
	case SPELL_SPIRIT_ARMOR:
	case SPELL_FLESH_ARMOR:
		if (!IS_AFFECTED(ch, AFF_ARMOR))
		{
			(skills[spell].spell_pointer)(MIN(56, count * 10), ch, 0, 0, ch, 0);
			message = SETMSG_PROTECT;
		}
		break;
	case SPELL_HASTE:
		if (!IS_AFFECTED(ch, AFF_HASTE))
		{
			spell_haste(MIN(56, count * 10), ch, 0, 0, ch, 0);
			message = SETMSG_STRENGTH;
		}
		break;
	case SPELL_FIRESHIELD:
		if (!IS_AFFECTED2(ch, AFF2_FIRESHIELD))
		{
			spell_fireshield(MIN(56, count * 10), ch, 0, 0, ch, 0);
			message = SETMSG_STRENGTH;
		}
		break;
	case SPELL_INFERNAL_FURY:
		if (!IS_AFFECTED(ch, AFF_INFERNAL_FURY))
		{
			spell_infernal_fury(MIN(56, count * 10), ch, 0, 0, ch, 0);
			message = SETMSG_STRENGTH;
		}
		break;
	case SPELL_STRENGTH:
	case SPELL_BLESS:
		(skills[spell].spell_pointer)(MIN(56, count * 10), ch, 0, 0, ch, 0);
		message = SETMSG_STRENGTH;
		break;
	case SPELL_CONJURE_ELEMENTAL:
		if (!named_set_cooldown_remaining(ch, spell) &&
		    obj->timer[0] + get_property("timer.conjureElement.generic", 300) < time(NULL))
		{
			(skills[spell].spell_pointer)(MIN(56, MAX(30, count * 10)), ch, 0, 0, ch,
						      0);
			obj->timer[0] = time(NULL);
			start_named_set_cooldown(ch, spell,
						 get_property("timer.conjureElement.generic", 300) *
							 WAIT_SEC);
			message = SETMSG_STRENGTH;
		}
		break;
	case SPELL_INVIGORATE:
		if (!named_set_cooldown_remaining(ch, spell) &&
		    obj->timer[0] + get_property("timer.invigorate.generic", 60) < time(NULL) &&
		    GET_VITALITY(ch) < GET_MAX_VITALITY(ch))
		{
			(skills[spell].spell_pointer)(MIN(56, MAX(30, count * 10)), ch, 0, 0, ch,
						      0);
			obj->timer[0] = time(NULL);
			start_named_set_cooldown(
				ch, spell, get_property("timer.invigorate.generic", 60) * WAIT_SEC);
			message = SETMSG_STRENGTH;
		}
		break;
	case SPELL_ENDURANCE:
		if (!affected_by_spell(ch, SPELL_MIELIKKI_VITALITY))
		{
			(skills[spell].spell_pointer)(MIN(56, MAX(30, count * 10)), ch, 0, 0, ch,
						      0);
			message = SETMSG_STRENGTH;
		}
		break;
	case SONG_DRAGONS:
		grant_dragons_to_group(ch, count, zone, false);
		break;
	case SKILL_EPIC_STRENGTH:
	case SKILL_EPIC_POWER:
	case SKILL_EPIC_AGILITY:
	case SKILL_EPIC_INTELLIGENCE:
	case SKILL_EPIC_DEXTERITY:
	case SKILL_EPIC_WISDOM:
	case SKILL_EPIC_CONSTITUTION:
	case SKILL_EPIC_CHARISMA:
	case SKILL_EPIC_LUCK:
		if (!affected_by_skill(ch, spell))
		{
			int level = MIN(56, count * 10);
			struct affected_type af;
			memset(&af, 0, sizeof(af));
			af.type = spell;
			af.duration = level / 10;
			af.location = APPLY_SKILL_GRANT;
			af.loc2 = spell;
			af.modifier = level;
			affect_to_char(ch, &af);
			message = SETMSG_STRENGTH;
		}
		break;
	default:
		(skills[spell].spell_pointer)(MIN(56, count * 10), ch, 0, 0, ch, 0);
		message = SETMSG_PROTECT;
		break;
	}

	if (spell != SPELL_CONJURE_ELEMENTAL && spell != SPELL_INVIGORATE &&
	    !grant.created_affects())
		message = SETMSG_NONE;
	grant.release_wearer_output();

	if (message == SETMSG_PROTECT)
	{
		snprintf(buffer, 512, "The spirits of %s grant you their protection.\n", zone_name);
		send_to_char(buffer, ch);
	}
	else if (message == SETMSG_STRENGTH)
	{
		snprintf(buffer, 512, "The spirits of %s grant you their strength.\n", zone_name);
		send_to_char(buffer, ch);
	}
}

#undef SETMSG_NONE
#undef SETMSG_PROTECT
#undef SETMSG_STRENGTH

// Random zone eq spellups (depends on # items worn == count).
void check_zone_spells(P_char ch, P_obj obj, int count, int zone, const char *zone_name)
{
	if (zone <= 0)
		return; // Ambiguous historical sets retain HP only.
	const named_set_definition *set = nullptr;
	for (size_t i = 0; i < named_set_count; ++i)
		if (named_sets[i].zone == zone)
		{
			set = &named_sets[i];
			break;
		}
	if (!set)
		return;

	bool spellsRemoved = false;

	// For the three possible spellups,
	for (int i = 0; i < 3; i++)
	{
		if (set->proc_spells[i][0])
		{
			// If the required num of eq is met for spell
			if (set->proc_spells[i][0] <= count)
			{
				// cast the spell on ch.
				apply_zone_spell(ch, count, zone_name, zone, obj,
						 set->proc_spells[i][1]);
			}
			else if (reconcile_named_set_spell(ch, set->proc_spells[i][1]))
				spellsRemoved = true;
		}
	}

	if (spellsRemoved)
	{
		char buffer[512];
		snprintf(buffer, 512, "The spirits of %s remove their blessings.\n", zone_name);
		send_to_char(buffer, ch);
	}
}

int random_set(P_char ch, P_obj obj, int count, int cmd, char * /*arg*/)
{
	struct affected_type af, *afp;
	char buffer[512];
	struct random_set_wear_off rdata;

	if (cmd == CMD_SET_PERIODIC)
	{
		return TRUE;
	}

	if (cmd != CMD_PERIODIC || !IS_ALIVE(ch))
	{
		return FALSE;
	}

	const auto identity = named_set_origin(obj);
	if (identity.zone < 0 || (!identity.zone && identity.legacy_title.empty()))
		return FALSE;
	const int source = identity.zone > 0 ? identity.zone : -identity.legacy_group;
	void *context = reinterpret_cast<void *>(static_cast<intptr_t>(source));
	const int zone_index = identity.zone > 0 ? real_zone(identity.zone) : -1;
	const char *zone_name = zone_index >= 0 ? zone_table[zone_index].name :
						  identity.legacy_title.c_str();

	if (count < 2)
	{
		return FALSE;
	}

	// Each set has its own transient HP affect.
	afp = get_spell_from_char(ch, TAG_SETPROC, context);
	if (!afp)
	{
		memset(&af, 0, sizeof(af));
		af.type = TAG_SETPROC;
		af.flags = AFFTYPE_NOSAVE | AFFTYPE_NOSHOW | AFFTYPE_NODISPEL;
		af.location = APPLY_HIT;
		// This should be indefinite: Only changes upon eq removal/wear new eq.
		af.duration = -1;
		af.context = context;
		afp = affect_to_char(ch, &af);
	}

	// Refresh only this group's cleanup event; other sets keep their deadlines.
	P_nevent pending = nullptr;
	for (P_nevent event = ch->nevents; event; event = event->next_char_nev)
		if (event->func == event_random_set_proc && event->data &&
		    static_cast<random_set_wear_off *>(event->data)->context == context)
		{
			pending = event;
			break;
		}
	if (pending)
		nevent_reschedule_after(nevent_handle_from_event(pending), PULSE_MOBILE + 5);
	else
	{
		rdata.context = context;
		rdata.zone = identity.zone;
		snprintf(rdata.zone_name, sizeof rdata.zone_name, "%s", zone_name);
		add_event(event_random_set_proc, PULSE_MOBILE + 5, ch, 0, 0, 0, &rdata,
			  sizeof(rdata));
	}

	check_zone_spells(ch, obj, count, identity.zone, zone_name);

	if (afp->modifier > (count - 2) * 5)
	{
		snprintf(buffer, sizeof buffer,
			 "You feel some of the %s's spirits attention leave you.\n", zone_name);
		send_to_char(buffer, ch);
	}
	else if (afp->modifier < (count - 2) * 5)
	{
		snprintf(buffer, sizeof buffer,
			 "You feel invigorated as the spirits of %s bless you.\n", zone_name);
		send_to_char(buffer, ch);
	}
	else
	{
		return TRUE;
	}

	afp->modifier = (count - 2) * 5;
	add_event(event_balance_affects, 0, ch, 0, 0, 0, 0, 0);

	return TRUE;
}

struct set_data
{
	set_func func;
	int items[MAX_WEAR];
} sets[] = { { master_set_adapter, { 22063, 22237, 22621, 45530, 45531, 75857, 82545, 82559 } },
	     { random_set, { VOBJ_RANDOM_ARMOR, VOBJ_RANDOM_WEAPON } },
	     { nullptr, { 0 } } };

int set_proc(P_obj obj, P_char ch, int cmd, char *arg)
{
	P_obj tobj, included[MAX_WEAR], cobj = obj;
	int s, i = 0, j, count = 0;
	unsigned int flag = (cmd != CMD_PERIODIC) ? ITEM2_NOPROC : ITEM2_NOTIMER;
	named_set_identity identity;

	// Look through the sets for the right vnum.
	for (s = 0; sets[s].func; s++)
	{
		for (i = 0; sets[s].items[i]; i++)
		{
			// We found a set that obj is in.
			if (sets[s].items[i] == obj_index[obj->R_num].virtual_number)
			{
				break;
			}
		}
		if (sets[s].items[i])
		{
			break;
		}
	}

	// If we didn't find a set that obj was in
	if (sets[s].items[i] == 0)
	{
		return FALSE;
	}

	// Set the periodic timer if appropriate.
	if (cmd == CMD_SET_PERIODIC)
	{
		return sets[s].func(ch, obj, count, cmd, arg);
	}

	if (sets[s].func == random_set)
	{
		identity = named_set_origin(obj);
		if (identity.zone < 0 || (!identity.zone && identity.legacy_title.empty()))
		{
			disarm_obj_nevents(obj, event_object_proc);
			return FALSE;
		}
	}

	// No proc if not worn.
	if (!OBJ_WORN(obj))
	{
		return FALSE;
	}

	if (IS_SET(obj->extra2_flags, flag))
	{
		REMOVE_BIT(obj->extra2_flags, flag);
		return FALSE;
	}

	if (cmd == CMD_PERIODIC)
	{
		ch = obj->loc.wearing;
	}

	memset(included, 0, sizeof(included));

	// Walk through worn equipment.
	for (i = 0; i < MAX_WEAR; i++)
	{
		tobj = ch->equipment[i];

		// Skip belted & back?  Shouldn't we allow prime belt slot? and skip empty slots.
		//   Allowing prime belt slot and on back.. 8/21/2014
		if (i == WEAR_ATTACH_BELT_3 || i == WEAR_ATTACH_BELT_2 || !tobj)
		//      || i == WEAR_ATTACH_BELT_1 || i == WEAR_BACK || !tobj )
		{
			continue;
		}
		// Walk through the current set..
		for (j = 0; sets[s].items[j]; j++)
		{
			// If the set vnum matches
			if (sets[s].items[j] == obj_index[tobj->R_num].virtual_number)
			{
				break;
			}
		}
		// If we didn't find a match, continue.
		if (!sets[s].items[j])
		{
			continue;
		}
		// If we have a random item..
		if (sets[s].func == random_set)
		{
			const auto candidate = named_set_origin(tobj);
			if (candidate.zone != identity.zone ||
			    candidate.legacy_title != identity.legacy_title)
				continue;
			if (candidate.zone > 0)
				set_named_set_origin(tobj, candidate.zone);
		}
		else
		{
			// Walk the included list.
			for (j = 0; included[j]; j++)
			{
				if (included[j]->R_num == tobj->R_num)
				{
					break;
				}
			}
			// Skip to next item if it's a duplicate vnum.
			if (included[j])
			{
				continue;
			}
		}
		// Set the no proc flag.
		if (tobj != obj)
		{
			SET_BIT(tobj->extra2_flags, flag);
		}

		// Add tobj to the end of the list of included objects.
		included[j] = tobj;
		// Save the object with the newest timer.
		if (cobj->timer[0] < tobj->timer[0])
		{
			cobj = tobj;
		}
		// Increment the counter of items in set.
		count++;
	}

	// If the set's function returns true..
	if (sets[s].func(ch, cobj, count, cmd, arg))
	{
		// If we're not periodic..
		if (cmd != CMD_PERIODIC)
		{
			// Remove the no proc flag from all items in set.
			for (i = 0; included[i]; i++)
			{
				REMOVE_BIT(included[i]->extra2_flags, ITEM2_NOPROC);
			}
		}
		return TRUE;
	}

	return FALSE;
}
