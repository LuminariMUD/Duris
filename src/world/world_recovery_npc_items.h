/****************************************************************************
 *
 *  File: world_recovery_npc_items.h                            Part of Duris
 *  Usage: world recovery NPC item interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef WORLD_RECOVERY_NPC_ITEMS_H
#define WORLD_RECOVERY_NPC_ITEMS_H

#include "core/structs.h"

#include <stddef.h>

bool world_recovery_rehydrate_npc_items(P_char const *mobs, size_t mob_count);

#endif
