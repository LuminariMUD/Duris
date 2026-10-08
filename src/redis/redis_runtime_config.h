/****************************************************************************
 *
 *  File: redis_runtime_config.h                                Part of Duris
 *  Usage: Redis runtime connection types and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef REDIS_RUNTIME_CONFIG_H
#define REDIS_RUNTIME_CONFIG_H

struct redis_connection_settings;

struct redis_runtime_connections
{
	struct redis_connection_settings *world;
	struct redis_connection_settings *presence;
	struct redis_connection_settings *cache;
	struct redis_connection_settings *donation;
	struct redis_connection_settings *maintenance;
	const char *host;
	int port;
	bool unix_socket;
};

bool redis_runtime_connections_configure(bool donation_enabled,
					 struct redis_runtime_connections *connections);
void redis_runtime_connections_destroy(struct redis_runtime_connections *connections);

#endif
