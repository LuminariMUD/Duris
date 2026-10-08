/****************************************************************************
 *
 *  File: redis_donation_runtime.h                              Part of Duris
 *  Usage: Redis donation runtime interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef REDIS_DONATION_RUNTIME_H
#define REDIS_DONATION_RUNTIME_H

#include "core/structs.h"

bool redis_donation_runtime_enabled(void);
void redis_donation_runtime_set_enabled(bool enabled);
void event_check_donation_messages(P_char ch, P_char victim, P_obj obj, void *data);

#endif
