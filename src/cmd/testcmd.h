/****************************************************************************
 *
 *  File: testcmd.h                                             Part of Duris
 *  Usage: test command interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef _TESTCMD_H_
#define _TESTCMD_H_

#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"

void do_test(P_char ch, char *arg, int cmd);
int very_angry_npc(P_char, P_char, int, char *);

#endif
