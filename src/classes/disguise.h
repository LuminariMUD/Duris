/****************************************************************************
 *
 *  File: disguise.h                                            Part of Duris
 *  Usage: disguise interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef __DISGUISE_H__
#define __DISGUISE_H__

#include "core/structs.h"
#include <stdio.h>
#include <stdlib.h>
#include <string>
#include "core/config.h"

void do_disguise(P_char, char *, int);
void remove_disguise(P_char ch, bool show_messages);

#endif // __DISGUISE_H__
