/****************************************************************************
 *
 *  File: presence_policy.c                                     Part of Duris
 *  Usage: who is visible to DurisWeb presence
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "persistence/presence_policy.h"

#include "core/utils.h"

#include <cstdlib>
#include <cstring>

bool durisweb_private_presence_enabled(void)
{
	const char *value = getenv("DURISWEB_PRIVATE_PRESENCE");
	return value && !strcmp(value, "TRUE");
}

bool durisweb_presence_character_visible(P_char ch)
{
	return ch && IS_PC(ch) && (GET_WIZINVIS(ch) <= 0 || durisweb_private_presence_enabled());
}
