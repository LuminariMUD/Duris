/****************************************************************************
 *
 *  File: player_load_materialize.h                             Part of Duris
 *  Usage: player load materialization interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef PLAYER_LOAD_MATERIALIZE_H
#define PLAYER_LOAD_MATERIALIZE_H

#include "player/player_load_repository.h"

struct char_data;
typedef struct char_data *P_char;

bool player_load_materialize(P_char character, const player_load_result &result);

#endif
