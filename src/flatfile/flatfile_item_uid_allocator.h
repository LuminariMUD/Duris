/****************************************************************************
 *
 *  File: flatfile_item_uid_allocator.h                         Part of Duris
 *  Usage: flat-file item uid allocator interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_ITEM_UID_ALLOCATOR_H
#define DURIS_FLATFILE_ITEM_UID_ALLOCATOR_H

#include <cstdint>
#include <string>

enum class flatfile_item_uid_result
{
	ok,
	invalid,
	exhausted,
	io_error
};

flatfile_item_uid_result flatfile_item_uid_reserve(const std::string &root, uint64_t count,
						   uint64_t *first, std::string *error);
flatfile_item_uid_result flatfile_item_uid_current(const std::string &root, uint64_t *next_uid,
						   uint64_t *revision, std::string *error);

#endif
