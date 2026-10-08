/****************************************************************************
 *
 *  File: flatfile_shop_trophy_history.h                        Part of Duris
 *  Usage: flat-file shop trophy history interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_SHOP_TROPHY_HISTORY_H
#define DURIS_FLATFILE_SHOP_TROPHY_HISTORY_H

#include <stdint.h>

#include <string>

enum class flatfile_shop_trophy_result
{
	ok,
	invalid,
	corrupt,
	io_error
};

flatfile_shop_trophy_result flatfile_shop_trophy_record(const char *root, int item, int value,
							int seller, int64_t occurred_at,
							std::string *error);
flatfile_shop_trophy_result flatfile_shop_trophy_count(const char *root, int item, int64_t now,
						       int *count, std::string *error);

#endif
