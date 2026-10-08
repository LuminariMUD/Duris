/****************************************************************************
 *
 *  File: redis_namespace.h                                     Part of Duris
 *  Usage: Redis namespace interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef REDIS_NAMESPACE_H
#define REDIS_NAMESPACE_H

#include <stddef.h>
#include <stdint.h>

bool redis_namespace_validate(const char *configured, const char *environment, char *output,
			      size_t output_size);
bool redis_namespace_season_key(const char *key_namespace, uint64_t epoch, const char *suffix,
				char *output, size_t output_size);

#endif
