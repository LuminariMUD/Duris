/****************************************************************************
 *
 *  File: racewar_stat_mods.h                                   Part of Duris
 *  Usage: racewar stat modifier interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef _RACEWAR_STAT_MODS_H_
#define _RACEWAR_STAT_MODS_H_

#include <vector>
using namespace std;

#include "core/structs.h"

int add_racewar_stat_mods(P_char ch, struct hold_data *affs);
int set_racewar_stat_mod(int racewar, int stat_affect, int regular_stat, int max_stat);
void reset_racewar_stat_mods();

#endif
