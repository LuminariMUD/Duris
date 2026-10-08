/****************************************************************************
 *
 *  File: zone_touch_repository.h                               Part of Duris
 *  Usage: SQL zone touch repository interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef ZONE_TOUCH_REPOSITORY_H
#define ZONE_TOUCH_REPOSITORY_H

#include "world/zone_touch_command.h"

#include <mysql/mysql.h>

bool zone_touch_repository_execute(MYSQL *connection, const critical_command &command,
				   zone_touch_result *result, unsigned int *result_code,
				   bool *mutation_applied);

#endif
