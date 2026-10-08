/****************************************************************************
 *
 *  File: random.zone.h                                         Part of Duris
 *  Usage: random zone and relic types
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef _RANDOM_ZONE_H_
#define _RANDOM_ZONE_H_

struct random_zone
{
	int map_room;
	int first_room;
	int last_room;
	int theme;
	int chest;
	int lvl_potion;
};

extern struct random_zone random_zone_data[];

struct relic_struct
{
	int good_relic;
	int evil_relic;
	int undead_relic;
};

extern struct relic_struct relic_struct_data[];

#define RANDOM_ZONE_ID 1000

#define RANDOM_START_ROOM 100000
#define RANDOM_END_ROOM 105000

#define MAX_RANDOM_ROOMS 30
#define MAX_RANDOM_ZONES 25

#define IS_RANDOM_ROOM(room) \
	(world[room].number >= RANDOM_START_ROOM && world[room].number <= RANDOM_END_ROOM)

int random_entrance_vnum(int rroom);

#endif
