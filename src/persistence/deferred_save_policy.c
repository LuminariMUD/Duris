/****************************************************************************
 *
 *  File: deferred_save_policy.c                                Part of Duris
 *  Usage: retry delay for deferred saves
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "persistence/deferred_save_policy.h"

int deferred_save_next_retry_delay(int current)
{
	if (current < PERSISTENCE_DEFERRED_RETRY_INITIAL)
		return PERSISTENCE_DEFERRED_RETRY_INITIAL;
	if (current >= PERSISTENCE_DEFERRED_RETRY_MAX / 2)
		return PERSISTENCE_DEFERRED_RETRY_MAX;
	return current * 2;
}
