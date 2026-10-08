/****************************************************************************
 *
 *  File: redis_floor_runtime.h                                 Part of Duris
 *  Usage: Redis floor runtime interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef REDIS_FLOOR_RUNTIME_H
#define REDIS_FLOOR_RUNTIME_H

#include "core/structs.h"

#include <stdint.h>

bool redis_floor_runtime_configure(const char *key_namespace, uint64_t epoch);
void redis_floor_runtime_reset(void);
void redis_floor_runtime_set_enabled(bool enabled);
void redis_floor_runtime_set_quiesced(bool quiesced);
void redis_floor_runtime_set_materializing(bool active);
bool redis_floor_runtime_enabled(void);

void redis_log_floor_drop(P_obj obj, int room_vnum);
void redis_remove_floor_drop(unsigned long obj_uid);
bool redis_flush_floor_drops(void);

#endif
