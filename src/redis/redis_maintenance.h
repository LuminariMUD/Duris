/****************************************************************************
 *
 *  File: redis_maintenance.h                                   Part of Duris
 *  Usage: Redis maintenance configuration and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef REDIS_MAINTENANCE_H
#define REDIS_MAINTENANCE_H

#include <stdint.h>

struct redis_connection_settings;

struct redis_maintenance_config
{
	const struct redis_connection_settings *connection;
	const char *key_namespace;
	uint64_t season_epoch;
	const char *presence_current_key;
	const char *presence_session_pattern;
	const char *presence_retry_pattern;
	const char *report_cache_pattern;
};

// Stopped-server season reset workflow. The caller must quiesce runtime writers first.
bool redis_maintenance_clear(const struct redis_maintenance_config *config);
bool redis_maintenance_validate(const struct redis_maintenance_config *config);

bool redis_clear_pwipe_state(void);
bool redis_validate_pwipe_state(void);

#endif
