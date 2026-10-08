/****************************************************************************
 *
 *  File: zone_story_quest_state_repository.h                   Part of Duris
 *  Usage: SQL zone story quest state repository interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef ZONE_STORY_QUEST_STATE_REPOSITORY_H
#define ZONE_STORY_QUEST_STATE_REPOSITORY_H

#include <cstdint>
#include <string>

enum class sql_zone_story_quest_state_result
{
	ok,
	not_found,
	invalid,
	io_error,
};

sql_zone_story_quest_state_result
sql_zone_story_quest_state_load(uint32_t expected_catalog_revision, std::string *state,
				std::string *error = nullptr);
sql_zone_story_quest_state_result sql_zone_story_quest_state_save(uint32_t catalog_revision,
								  const std::string &state,
								  std::string *error = nullptr);

#endif
