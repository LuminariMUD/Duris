/****************************************************************************
 *
 *  File: timers.h                                              Part of Duris
 *  Usage: player timer interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef _TIMERS_H_
#define _TIMERS_H_

void set_timer(const char *name);
void set_timer(const char *name, int date);
int get_timer(const char *name);
bool has_elapsed(const char *name, int seconds);

void timers_activity();

#endif
