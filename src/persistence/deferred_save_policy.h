/****************************************************************************
 *
 *  File: deferred_save_policy.h                                Part of Duris
 *  Usage: deferred save policy interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DEFERRED_SAVE_POLICY_H
#define DEFERRED_SAVE_POLICY_H

#define PERSISTENCE_DEFERRED_RETRY_INITIAL 4
#define PERSISTENCE_DEFERRED_RETRY_MAX 240

int deferred_save_next_retry_delay(int current);

#endif
