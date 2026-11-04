/*
 ***************************************************************************
 *  File: shaman.c                                          Part of  Duris *
 *  Usage: routines for handling shamans                                   *
 *  Copyright  1990, 1991 - see 'license.doc' for complete information.    *
 *  Copyright 1994 - 2008 - Duris Systems Ltd.                             *
 ***************************************************************************
 */

#include "core/prototypes.h"
#include "core/structs.h"
#include "net/comm.h"
#include "world/db.h"
#include "world/events.h"
#include "cmd/interp.h"
#include "core/utils.h"
#include <stdio.h>
#include <string.h>
#include "combat/justice.h"
#include "core/mm.h"
#include "item/objmisc.h"
#include "magic/spells.h"
#include "world/weather.h"

extern P_char character_list;
extern P_desc descriptor_list;
extern P_index mob_index;
extern P_index obj_index;
extern P_room world;
extern const struct stat_data stat_factor[];
extern int spl_table[TOTALLVLS][MAX_CIRCLE];
extern struct zone_data *zone_table;
extern struct time_info_data time_info;

extern Skill skills[];
extern const char *spells[];

// Returns the required totem's description, or nullptr if the shaman has it.
const char *missing_shaman_totem(P_char ch, int skill)
{
	const bool multiclass = IS_MULTICLASS_PC(ch);
	const bool greater = get_spell_circle(ch, skill) >= 6;
	const auto targets = skills[skill].targets;
	int flag = 0;
	const char *required = "casting";
	if (IS_SET(targets, TAR_ANIMAL))
	{
		flag = greater ? TOTEM_GR_ANIM : TOTEM_LESS_ANIM;
		required = greater ? "&+YGreater Animal&n" : "&+YLesser Animal&n";
	}
	else if (IS_SET(targets, TAR_ELEMENTAL))
	{
		flag = greater ? TOTEM_GR_ELEM : TOTEM_LESS_ELEM;
		required = greater ? "&+RGreater Elemental&n" : "&+RLesser Elemental&n";
	}
	else if (IS_SET(targets, TAR_SPIRIT))
	{
		flag = greater ? TOTEM_GR_SPIR : TOTEM_LESS_SPIR;
		required = greater ? "&+CGreater Spirit&n" : "&+CLesser Spirit&n";
	}

	const auto matches = [multiclass, flag](P_obj obj) {
		return obj && GET_ITEM_TYPE(obj) == ITEM_TOTEM &&
		       (multiclass || IS_SET(obj->value[0], flag));
	};

	for (int slot = 0; slot < MAX_WEAR; ++slot)
	{
		P_obj obj = ch->equipment[slot];
		if (matches(obj) ||
		    (obj && (slot == WIELD || slot == HOLD) && OBJ_VNUM(obj) == 139004))
			return nullptr;
	}
	for (P_obj obj = ch->carrying; obj; obj = obj->next_content)
	{
		if (matches(obj))
			return nullptr;
	}
	return required;
}
