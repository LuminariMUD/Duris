/****************************************************************************
 *
 *  File: information_cache.h                                   Part of Duris
 *  Usage: information cache interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_INFORMATION_CACHE_H
#define DURIS_INFORMATION_CACHE_H
#include <string>
bool information_cache_refresh();
void information_cache_pulse();
void information_cache_shutdown();
std::string information_cache_status();
// Null means unavailable or not an informational page. The pointer is valid
// until the next game-thread publication; pagers must own their text.
const std::string *information_cache_get(const std::string &name);
#endif
