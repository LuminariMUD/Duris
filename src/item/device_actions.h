/****************************************************************************
 *
 *  File: device_actions.h                                      Part of Duris
 *  Usage: device item action interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_DEVICE_ACTIONS_H
#define DURIS_DEVICE_ACTIONS_H

#include "item/item_actions.h"

item_action_start begin_device_action(P_obj source, P_char actor, const char *arguments);
void update_device_action_properties();
// Physical removal of committed scrolls occurs after command/event callbacks
// unwind. The ink is already consumed synchronously at acceptance.
void device_actions_pulse();

#endif
