/****************************************************************************
 *
 *  File: session_audit_repository.h                            Part of Duris
 *  Usage: SQL session audit repository interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef SESSION_AUDIT_REPOSITORY_H
#define SESSION_AUDIT_REPOSITORY_H

#include "account/session_audit_command.h"

#include <mysql/mysql.h>

bool session_audit_repository_execute(MYSQL *connection, const critical_command &command,
				      session_audit_result *result);

#endif
