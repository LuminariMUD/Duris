/****************************************************************************
 *
 *  File: trophy.h                                              Part of Duris
 *  Usage: zone trophy award interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef _TROPHY_H_
#define _TROPHY_H_

#include "core/structs.h"
#include "item/trophy_state.h"

// Called only after gain_exp has credited a positive award. Returns whether the
// caller must include trophies in the same dirty revision as player XP.
bool record_zone_trophy_award(P_char ch, P_char victim, int credited_xp, int type);
void clear_zone_trophy(P_char ch);

#define ZONE_TROPHY(ch) (ch->only.pc->zone_trophy)

#endif
