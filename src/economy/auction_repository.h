/****************************************************************************
 *
 *  File: auction_repository.h                                  Part of Duris
 *  Usage: SQL auction repository interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef AUCTION_REPOSITORY_H
#define AUCTION_REPOSITORY_H

#include "economy/auction_command.h"

#include <mysql/mysql.h>

bool auction_repository_execute(MYSQL *connection, const critical_command &command,
				auction_command_result *result, unsigned int *result_code,
				bool *mutation_applied);

#endif
