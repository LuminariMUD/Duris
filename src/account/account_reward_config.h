/****************************************************************************
 *
 *  File: account_reward_config.h                               Part of Duris
 *  Usage: account reward configuration interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef _ACCOUNT_REWARD_CONFIG_H_
#define _ACCOUNT_REWARD_CONFIG_H_

#include <stdbool.h>

void boot_account_reward_config(void);
int account_reward_config_cooldown_seconds(void);
int account_reward_config_max_active_rewards(void);
bool account_reward_config_show_claim_ids(void);
bool account_reward_config_preserve_on_pwipe(void);

#endif
