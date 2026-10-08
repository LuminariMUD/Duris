/****************************************************************************
 *
 *  File: locker_identify.h                                     Part of Duris
 *  Usage: locker identify interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_LOCKER_IDENTIFY_H
#define DURIS_LOCKER_IDENTIFY_H
#include "core/structs.h"
void locker_identify(P_char ch, P_obj obj, int cost);
void locker_identify_pulse();
bool locker_identify_init(const char *journal_directory);
void locker_identify_shutdown();
void locker_identify_replay(P_char ch);
void locker_identify_receipt(P_char ch);
#endif
