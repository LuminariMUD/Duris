/****************************************************************************
 *
 *  File: artifact_guild_repository.h                           Part of Duris
 *  Usage: SQL artifact guild repository interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef ARTIFACT_GUILD_REPOSITORY_H
#define ARTIFACT_GUILD_REPOSITORY_H

#include "guild/artifact_guild_command.h"

#include <mysql/mysql.h>

bool artifact_guild_repository_execute(MYSQL *connection, const critical_command &command,
				       artifact_guild_result *result, unsigned int *result_code,
				       bool *mutation_applied);

#endif
