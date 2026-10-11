/****************************************************************************
 *
 *  File: randobj.c                                             Part of Duris
 *  Usage: randobj, the staff command that makes random items, mobs and zones
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
#include "cmd/interp.h"
#include "core/utils.h"
#include "economy/tradeskill.h"
#include "item/random_equipment.h"
#include "world/vnum.obj.h"

extern P_index obj_index;

void create_zone(int theme, int map_room1, int map_room2, int level_range, int rooms);

void do_randobj(P_char ch, char *strn, int /*val*/)
{
	P_obj o;
	char Gbuf5[MAX_STRING_LENGTH];

	if (!IS_TRUSTED(ch))
	{
		send_to_char("Bad mortal or mob.. bad!.\r\n", ch);
		return;
	}

	if (!str_cmp("remove", strn))
	{
		reset_lab(0);
		reset_lab(1);
		reset_lab(2);

		wizlog(56, "Reset map random");
		return;
	}

	if (!str_cmp("map", strn))
	{
		create_lab(0);
		create_lab(1);
		create_lab(2);
		wizlog(56, "Created map random");
		return;
	}

	if (!str_cmp("piece", strn))
	{
		o = create_material(ch, GET_LEVEL(ch), GET_LEVEL(ch));
		obj_to_char(o, ch);
		return;
	}
	if (!str_cmp("stone", strn))
	{
		o = create_stones();
		obj_to_char(o, ch);
		return;
	}
	if (!str_cmp("eq", strn))
	{
		o = create_random_eq(ch, GET_LEVEL(ch), GET_LEVEL(ch), -1, -1);
		obj_to_char(o, ch);
		snprintf(Gbuf5, MAX_STRING_LENGTH, "o %s", o->name);
		do_stat(ch, Gbuf5, CMD_STAT);
		return;
	}

	if (!str_cmp("recipe", strn))
	{
		o = random_zone_item(ch);
		if (!o)
		{
			send_to_char("Failed creating random zone item.\n", ch);
			return;
		}

		if (obj_index[o->R_num].virtual_number == VOBJ_RANDOM_ARMOR ||
		    obj_index[o->R_num].virtual_number == VOBJ_RANDOM_THRUSTED ||
		    obj_index[o->R_num].virtual_number == VOBJ_RANDOM_WEAPON)
		{
			act("Created random object: $q.  Deleting it.", FALSE, ch, o, NULL,
			    TO_CHAR);
			extract_obj(o);
			return;
		}
		create_recipe(ch, o);
		extract_obj(o);

		return;
	}

	if (!str_cmp("mob", strn))
	{
		create_random_mob(-1, 0);
		return;
	}

	if (!str_cmp("zone", strn))
	{
		create_zone(number(0, 2), 999, 999, 999, 999);
		return;
	}

	if (!str_cmp("encrust", strn))
	{
		for (int i = 0; i < 10; i++)
		{
			o = random_zone_item(ch);
			if (!o)
				return send_to_char("Failed to create item.\n", ch);
			o->affected[2].location = APPLY_MOVE_REG;
			describe_encrusted_enhanced(o);
			send_to_char_f(ch, "%s\n", o->short_description);
			extract_obj(o);
		}
		return;
	}

	send_to_char(
		"Syntax: randobj <remove, map, stone, piece, eq, recipe, mob, zone, encrust> \r\n",
		ch);
}
