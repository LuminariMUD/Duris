/****************************************************************************
 *
 *  File: redis_key_registry.c                                  Part of Duris
 *  Usage: the Redis key registry table
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "redis/redis_key_registry.h"

const redis_key_registry_entry redis_key_registry[] = {
#define REDIS_STORE(symbol, lifecycle_id, locator, kind)
#define REDIS_SURFACE(symbol, token, pattern, store, kind, state) \
	{ #symbol, token, pattern, REDIS_STORE_ID_##store, kind, state },
#define REDIS_OWNED_PATTERN(symbol, pattern)
#include "redis/redis_key_registry.def"
#undef REDIS_OWNED_PATTERN
#undef REDIS_SURFACE
#undef REDIS_STORE
};

const size_t redis_key_registry_count = sizeof redis_key_registry / sizeof redis_key_registry[0];
