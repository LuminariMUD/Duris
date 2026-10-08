/****************************************************************************
 *
 *  File: player_name.h                                         Part of Duris
 *  Usage: normalizes a player name's letter case
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef PLAYER_NAME_H
#define PLAYER_NAME_H

#include "core/utils.h"

static inline void normalize_player_name_case(char *name)
{
	if (!name || !*name)
		return;

	name[0] = UPPER(name[0]);
	for (char *p = name + 1; *p; ++p)
	{
		*p = LOWER(*p);
	}
}

#endif
