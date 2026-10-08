/****************************************************************************
 *
 *  File: login_mode_banner.h                                   Part of Duris
 *  Usage: login mode banner interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#pragma once

#include <string>

/* DURIS_STAGING=TRUE (.env) marks a public staging server.  Only the login
 * banner reads it. */
bool duris_staging_enabled(void);

/* One blinking, all-caps line naming each enabled server mode, ending in CRLF,
 * or an empty string when no mode is enabled. */
std::string login_mode_banner(bool staging, bool chaos, bool all_races, bool all_classes);
