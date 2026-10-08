/****************************************************************************
 *
 *  File: help_cache.h                                          Part of Duris
 *  Usage: help cache types and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_HELP_CACHE_H
#define DURIS_HELP_CACHE_H

#include <array>
#include <string>
#include <vector>

struct help_page
{
	std::array<std::string, 5> fields;
};
using help_catalog = std::vector<help_page>;

bool help_cache_refresh();
void help_cache_pulse();
void help_cache_shutdown();
std::string help_cache_status();
const help_catalog *help_cache_get();
bool help_title_matches(const std::string &title, const std::string &query);
bool help_title_equal(const std::string &left, const std::string &right);

#endif
