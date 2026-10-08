/****************************************************************************
 *
 *  File: redis_ship_legacy.h                                   Part of Duris
 *  Usage: Redis legacy ship cleanup interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef REDIS_SHIP_LEGACY_H
#define REDIS_SHIP_LEGACY_H

#include <stddef.h>
#include <stdint.h>

struct redisContext;
struct redis_connection_settings;

constexpr size_t REDIS_SHIP_LEGACY_QUEUE_CAPACITY = 64;
constexpr unsigned int REDIS_SHIP_LEGACY_MAX_COMMAND_ATTEMPTS = 3;

bool redis_ship_legacy_worker_init(const struct redis_connection_settings *connection);
bool redis_ship_legacy_worker_drain(uint64_t timeout_msec);
bool redis_ship_legacy_worker_shutdown(uint64_t timeout_msec);
void redis_ship_legacy_worker_cancel(void);
void redis_invalidate_ship_snapshot(const char *owner_name);
bool redis_clear_ship_snapshots(struct redisContext *context);

#endif
