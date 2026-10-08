/****************************************************************************
 *
 *  File: specs.venthix.h                                       Part of Duris
 *  Usage: Venthix's special procedures and the zombie game types
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef _SPECS_VENTHIX_H_
#define _SPECS_VENTHIX_H_

#include <vector>
using namespace std;

#include "core/structs.h"

struct ZombieGame
{
	ZombieGame();
	ZombieGame(P_obj _generator);
	~ZombieGame();

	int load();
	int unload();

	int id;

	static int next_id;

	P_obj generator;

	vector<P_char> zombies;
	int zombies_to_load;

	int zombies_alive()
	{
		if (zombies.size() < 1)
			return 0;

		return (int)zombies.size();
	}
};

int zgame_load_zombie(P_obj obj);
void zgame_clear_zombies(P_obj obj);
int zg_count_zombies(P_obj obj);
int zgame_mob_proc(P_char ch, P_char pl, int cmd, char *arg);
ZombieGame *get_zgame_from_obj(P_obj obj);

#endif
