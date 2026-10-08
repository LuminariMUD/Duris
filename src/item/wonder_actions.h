/****************************************************************************
 *
 *  File: wonder_actions.h                                      Part of Duris
 *  Usage: wonder item action interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_WONDER_ACTIONS_H
#define DURIS_WONDER_ACTIONS_H

#include "item/item_actions.h"

item_action_start begin_wonder_action(P_obj, P_char actor, P_char original_target,
				      int selected_level);
void update_wonder_action_properties();

#endif
