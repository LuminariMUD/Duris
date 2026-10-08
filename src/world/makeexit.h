/****************************************************************************
 *
 *  File: makeexit.h                                            Part of Duris
 *  Usage: makeexit command interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef __MAKEEXIT_H__
#define __MAKEEXIT_H__

#include "core/prototypes.h"
#include "core/utils.h"

void do_makeexit(P_char ch, char *arg, int cmd);
int link_room(int from_r, int to_r, int dir);

#endif
