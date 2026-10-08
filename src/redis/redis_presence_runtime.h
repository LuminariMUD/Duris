/****************************************************************************
 *
 *  File: redis_presence_runtime.h                              Part of Duris
 *  Usage: Redis presence runtime interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef REDIS_PRESENCE_RUNTIME_H
#define REDIS_PRESENCE_RUNTIME_H

#include "core/structs.h"

bool redis_presence_runtime_enabled(void);
void redis_presence_runtime_set_enabled(bool enabled);
void redis_player_online(P_char character);
void redis_player_offline(P_char character);
void redis_clear_online_players(void);

#endif
