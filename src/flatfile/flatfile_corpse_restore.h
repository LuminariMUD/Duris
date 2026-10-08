/****************************************************************************
 *
 *  File: flatfile_corpse_restore.h                             Part of Duris
 *  Usage: flat-file corpse restore interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_CORPSE_RESTORE_H
#define DURIS_FLATFILE_CORPSE_RESTORE_H

#include <string>

enum class flatfile_corpse_restore_result
{
	ok,
	not_found,
	invalid,
	unknown_prototype,
	unknown_room,
	allocation_failure,
	item_failure,
	publish_failure,
	io_error,
};

flatfile_corpse_restore_result flatfile_corpse_restore_catalog(const std::string &root,
							       std::string *error);

#endif
