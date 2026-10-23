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

// Called inside the primary transaction. The child receipt/outbox retain the
// immutable v3 command; ordinary artifact/guild snapshots deliver its effect.
bool artifact_guild_repository_load_delivery(MYSQL *connection,
					     const critical_operation_id &operation,
					     critical_command *command, bool *acknowledged);
bool artifact_guild_repository_pending_deliveries(MYSQL *connection,
						  std::vector<critical_command> *commands);
bool artifact_guild_repository_prepare_delivery(MYSQL *connection, const critical_command &command);
bool artifact_guild_repository_delivery_saved(MYSQL *connection, const critical_command &command,
					      bool *saved);
bool artifact_guild_repository_delivery_acknowledged(MYSQL *connection,
						     const critical_command &command,
						     bool *acknowledged);

std::array<char, 1024> artifact_guild_repository_diagnostic(const critical_command &command,
							    const char *reason, unsigned int error);
bool artifact_guild_repository_execute(MYSQL *connection, const critical_command &command,
				       artifact_guild_result *result, unsigned int *result_code,
				       bool *mutation_applied,
				       std::array<char, 1024> *failure_detail);

#endif
