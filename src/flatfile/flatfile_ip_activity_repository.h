/****************************************************************************
 *
 *  File: flatfile_ip_activity_repository.h                     Part of Duris
 *  Usage: flat-file IP activity repository interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_IP_ACTIVITY_REPOSITORY_H
#define DURIS_FLATFILE_IP_ACTIVITY_REPOSITORY_H

#include <stdint.h>

#include <string>

struct flatfile_ip_activity_record
{
	uint32_t pid = 0;
	std::string ip;
	int64_t last_connect = 0;
	int64_t last_disconnect = 0;
	int racewar_side = 0;
};

enum class flatfile_ip_activity_result
{
	ok,
	not_found,
	invalid,
	corrupt,
	io_error
};

flatfile_ip_activity_result flatfile_ip_activity_connect(const char *root, uint32_t pid,
							 const char *ip, int racewar_side,
							 int64_t occurred_at, std::string *error);
flatfile_ip_activity_result flatfile_ip_activity_disconnect(const char *root, uint32_t pid,
							    int racewar_side, int64_t occurred_at,
							    std::string *error);
flatfile_ip_activity_result flatfile_ip_activity_get(const char *root, uint32_t pid,
						     flatfile_ip_activity_record *record,
						     std::string *error);
flatfile_ip_activity_result flatfile_ip_activity_reset_active(const char *root, int64_t occurred_at,
							      std::string *error);

#endif
