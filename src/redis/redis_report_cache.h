/****************************************************************************
 *
 *  File: redis_report_cache.h                                  Part of Duris
 *  Usage: Redis report cache interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef REDIS_REPORT_CACHE_H
#define REDIS_REPORT_CACHE_H

#include <stddef.h>
#include <stdint.h>

#include "sql/sql_work.h"

struct redis_connection_settings;

bool redis_report_cache_configure(const char *key_namespace, uint64_t epoch);
bool redis_report_cache_start(const struct redis_connection_settings *connection);
void redis_report_cache_cancel(void);
bool redis_report_cache_shutdown(uint64_t timeout_msec);
void redis_report_cache_reset(void);
bool redis_report_cache_enabled(void);
const char *redis_report_cache_pattern(void);

void redis_cache_named_report(void);
char *redis_get_named_report(void);
bool redis_invalidate_named_report(void);

// Rebuilds the cached fraglist from the leaderboard, which the writer reads; ch, when
// given, is shown the new list. False when the cache is off or the read not queued.
bool redis_cache_fraglist(struct char_data *ch = nullptr);
char *redis_get_fraglist(void);
bool redis_invalidate_fraglist(void);
// The leaderboard's top and lowest fraggers matching filter (SQL), as rows tagged 'top'
// and 'low': the tag, char_name and total_frags. For the writer.
bool fraglist_leaders(MYSQL *connection, const char *filter, sql_rows *rows);

void redis_cache_epic_zones(void);
void redis_cache_epic_zones_output(const char *output);
char *redis_get_epic_zones(void);
bool redis_invalidate_epic_zones(void);

void redis_cache_artifact_list(int type, bool godlist, const char *json);
char *redis_get_artifact_list(int type, bool godlist);
bool redis_invalidate_artifact_list(int type, bool godlist);
bool redis_invalidate_artifact_cache(void);

#endif
