/****************************************************************************
 *
 *  File: flatfile_character_delete.h                           Part of Duris
 *  Usage: flat-file character deletion interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_CHARACTER_DELETE_H
#define DURIS_FLATFILE_CHARACTER_DELETE_H

#include <cstdint>
#include <string>

enum class flatfile_character_delete_result
{
	ok,
	already_deleted,
	not_found,
	conflict,
	invalid,
	io_error
};

flatfile_character_delete_result flatfile_character_delete(const std::string &root, int32_t pid,
							   const std::string &expected_name,
							   std::string *error);

#endif
