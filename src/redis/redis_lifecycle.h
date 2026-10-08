/****************************************************************************
 *
 *  File: redis_lifecycle.h                                     Part of Duris
 *  Usage: Redis subsystem lifecycle interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef REDIS_LIFECYCLE_H
#define REDIS_LIFECYCLE_H

bool redis_init(void);
void redis_cleanup(void);
bool redis_runtime_enabled(void);

#endif
