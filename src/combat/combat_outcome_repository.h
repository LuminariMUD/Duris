/****************************************************************************
 *
 *  File: combat_outcome_repository.h                           Part of Duris
 *  Usage: SQL combat outcome repository interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef COMBAT_OUTCOME_REPOSITORY_H
#define COMBAT_OUTCOME_REPOSITORY_H

#include "combat/combat_outcome_command.h"

#include <mysql/mysql.h>

bool combat_outcome_repository_execute(MYSQL *connection, const critical_command &command,
				       combat_outcome_result *result, unsigned int *result_code,
				       bool *mutation_applied);

#endif
