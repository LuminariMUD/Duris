/****************************************************************************
 *
 *  File: kingdom_restore.h                                     Part of Duris
 *  Usage: kingdom restore interface for the client-free build
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_KINGDOM_RESTORE_H
#define DURIS_KINGDOM_RESTORE_H
#include <string>
// Client-free build only: refuse even individually invalid realm records.
bool kingdom_flatfile_restore_validate(const std::string &root, std::string *error);
#endif
