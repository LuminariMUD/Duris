/****************************************************************************
 *
 *  File: trophy_state.h                                        Part of Duris
 *  Usage: zone trophy state type
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_TROPHY_STATE_H
#define DURIS_TROPHY_STATE_H

#include <cstddef>

// Raw accepted XP for observation, retaining the existing snapshot/SQL format.
// Normalized familiarity and timestamped recovery require a versioned successor.
constexpr size_t ZONE_TROPHY_MAX_ZONES = 1024;

struct zone_trophy_data
{
	int zone_number;
	int exp;
};

#endif
