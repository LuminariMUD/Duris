/****************************************************************************
 *
 *  File: forced_weapon_drop.h                                  Part of Duris
 *  Usage: forced weapon drop interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef FORCED_WEAPON_DROP_H
#define FORCED_WEAPON_DROP_H

#include "core/structs.h"

#include <cstdint>

enum class forced_weapon_drop_cause : uint8_t
{
	combat_fumble,
	critical_disarm,
};

enum class forced_weapon_drop_result : uint8_t
{
	rejected,
	dropped,
};

// Knock an equipped weapon out of the actor's grasp onto the floor.
forced_weapon_drop_result forced_weapon_drop(P_char actor, P_obj weapon,
					     forced_weapon_drop_cause cause);

#endif
