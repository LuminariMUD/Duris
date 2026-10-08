/****************************************************************************
 *
 *  File: flatfile_account_delete.h                             Part of Duris
 *  Usage: flat-file account deletion interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_ACCOUNT_DELETE_H
#define DURIS_FLATFILE_ACCOUNT_DELETE_H

#include <string>

enum class flatfile_account_delete_result
{
	ok,
	already_deleted,
	not_found,
	conflict,
	invalid,
	io_error
};

flatfile_account_delete_result flatfile_account_delete(const std::string &root,
						       const std::string &account_name,
						       std::string *error);

#endif
