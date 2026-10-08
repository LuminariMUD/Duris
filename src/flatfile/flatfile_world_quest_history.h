/****************************************************************************
 *
 *  File: flatfile_world_quest_history.h                        Part of Duris
 *  Usage: flat-file world quest history interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_WORLD_QUEST_HISTORY_H
#define DURIS_FLATFILE_WORLD_QUEST_HISTORY_H

#include <stdint.h>

#include <string>

#include "flatfile/flatfile_authority_transaction.h"

enum class flatfile_world_quest_result
{
	ok,
	not_found,
	invalid,
	corrupt,
	io_error
};

flatfile_world_quest_result flatfile_world_quest_record(const char *root, uint32_t pid,
							int quest_target, int player_level,
							int64_t occurred_at, std::string *error);
flatfile_world_quest_result flatfile_world_quest_completed(const char *root, uint32_t pid,
							   int quest_target, bool *completed,
							   std::string *error);
flatfile_world_quest_result flatfile_world_quest_count_day(const char *root, uint32_t pid,
							   int player_level, int64_t now,
							   int *count, std::string *error);
flatfile_world_quest_result
flatfile_world_quest_prepare_remove(const std::string &root, const flatfile_authority_lock &lock,
				    uint32_t pid, flatfile_authority_operation *operation,
				    std::string *error);

#endif
