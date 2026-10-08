/****************************************************************************
 *
 *  File: epic_bonus.h                                          Part of Duris
 *  Usage: epic bonus data types
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef __EPIC_BONUS_H__
#define __EPIC_BONUS_H__

#define EPIC_BONUS_NONE 0
#define EPIC_BONUS_CARGO 1
#define EPIC_BONUS_SHOP 2
#define EPIC_BONUS_EXP 3
#define EPIC_BONUS_EPIC_POINT 4
#define EPIC_BONUS_HEALTH_REG 5
#define EPIC_BONUS_MOVE_REG 6

#define EPIC_HEALTH_REGEN_MOD 40

struct EpicBonusData
{
	int pid;
	int type;
	char time[32];
};

struct epic_bonus_data
{
	int type;
	const char *name;
	const char *description;
};

void do_epic_bonus(P_char, char *, int);
void epic_bonus_help(P_char);
void epic_bonus_set(P_char, int);
float get_epic_bonus_max(int);
bool get_epic_bonus_data(P_char, EpicBonusData *);
float get_epic_bonus(P_char, int);
void epic_bonus_hydrate(P_char);
void epic_bonus_record_gain(P_char, int, int);
#endif
