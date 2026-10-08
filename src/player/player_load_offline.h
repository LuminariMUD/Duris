/****************************************************************************
 *
 *  File: player_load_offline.h                                 Part of Duris
 *  Usage: offline player load interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef PLAYER_LOAD_OFFLINE_H
#define PLAYER_LOAD_OFFLINE_H

#include "player/player_load_repository.h"

#include <functional>

struct char_data;
typedef struct char_data *P_char;

/*
 * Loads a character that is not in the game (finger, disguise, staff commands) through
 * the player load pipeline, off the game loop, without its pets and, unless asked, its
 * items. done runs on the game thread on a later pulse with the character, which it then
 * owns (free_char()), or null when there is none or it could not be loaded. False when
 * the load could not be queued; done is not called then.
 */
bool player_load_offline(const char *name, bool include_items, std::function<void(P_char)> done);
// For a command of ch's: done runs only while ch is still in the game (otherwise the loaded
// character is freed). A load that cannot be queued tells ch.
bool player_load_offline_for(P_char ch, const char *name, bool include_items,
			     std::function<void(P_char ch, P_char loaded)> done);
// Hands a finished load to its offline caller; false when it was not an offline load.
bool player_load_offline_complete(const player_load_result &result);

#endif
