/****************************************************************************
 *
 *  File: account_reward_snapshot.h                             Part of Duris
 *  Usage: account reward snapshot interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef _ACCOUNT_REWARD_SNAPSHOT_H_
#define _ACCOUNT_REWARD_SNAPSHOT_H_

#include "core/structs.h"
#include "account/account_reward.h"

char *account_reward_snapshot_serialize(P_obj obj);
bool account_reward_snapshot_apply(P_obj obj, const char *json, int template_version);

#endif
