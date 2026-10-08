/****************************************************************************
 *
 *  File: boon_reward_repository.h                              Part of Duris
 *  Usage: SQL boon reward repository interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef BOON_REWARD_REPOSITORY_H
#define BOON_REWARD_REPOSITORY_H

#include "economy/boon_reward_command.h"

#include <mysql/mysql.h>

bool boon_reward_repository_execute(MYSQL *connection, const critical_command &command,
				    boon_reward_result *result, unsigned int *result_code,
				    bool *mutation_applied);

#endif
