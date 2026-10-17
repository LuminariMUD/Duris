/****************************************************************************
 *
 *  File: flatfile_shopkeeper_restore.h                         Part of Duris
 *  Usage: flat-file shopkeeper restore interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_SHOPKEEPER_RESTORE_H
#define DURIS_FLATFILE_SHOPKEEPER_RESTORE_H

#include <string>

enum class flatfile_shopkeeper_restore_result
{
	ok,
	not_found,
	invalid,
	materialize_failure,
	publish_failure,
	io_error,
};

flatfile_shopkeeper_restore_result flatfile_shopkeeper_restore_catalog(const std::string &root,
								       std::string *error);

#endif
