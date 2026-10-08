/****************************************************************************
 *
 *  File: redis_connection.h                                    Part of Duris
 *  Usage: Redis connection options and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef REDIS_CONNECTION_H
#define REDIS_CONNECTION_H

#include <hiredis/hiredis.h>

struct redis_connection_settings;

struct redis_connection_options
{
	const char *host;
	int port;
	int connect_timeout_msec;
	int command_timeout_msec;
	int database;
	const char *username;
	const char *password;
	bool tls;
	const char *ca_cert;
	const char *server_name;
	bool require_tls;
	const char *unix_socket;
};

struct redis_connection_settings *
redis_connection_settings_create(const struct redis_connection_options *options);
void redis_connection_settings_destroy(struct redis_connection_settings *settings);
redisContext *redis_connection_open(const struct redis_connection_settings *settings);
redisContext *redis_connection_open_with_timeout(const struct redis_connection_settings *settings,
						 int minimum_command_timeout_msec);

#endif
