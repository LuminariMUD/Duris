/****************************************************************************
 *
 *  File: flatfile_identity_adapter.h                           Part of Duris
 *  Usage: flat-file player identity adapter interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_IDENTITY_ADAPTER_H
#define DURIS_FLATFILE_IDENTITY_ADAPTER_H

#include <stdint.h>

#include <string>

bool flatfile_player_identity_exists(const char *name, bool *exists, std::string *error);
bool flatfile_player_identity_pid(const char *name, int32_t *pid, std::string *error);
bool flatfile_player_identity_allocate(int32_t *pid, std::string *error);
bool flatfile_player_identity_highest(int32_t *pid, std::string *error);

#endif
