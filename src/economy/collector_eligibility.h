/****************************************************************************
 *
 *  File: collector_eligibility.h                               Part of Duris
 *  Usage: shared collector eligibility rules
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_COLLECTOR_ELIGIBILITY_H
#define DURIS_COLLECTOR_ELIGIBILITY_H

#include "player/player_snapshot.h"

// Shared by game-thread intake and both persistence backends. Eligibility is
// evaluated from the immutable item snapshot carried by the custody command.
bool collector_death_item_snapshot_eligible(const player_item_snapshot &item);

#endif
