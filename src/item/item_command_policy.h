/****************************************************************************
 *
 *  File: item_command_policy.h                                 Part of Duris
 *  Usage: item command policy interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef ITEM_COMMAND_POLICY_H
#define ITEM_COMMAND_POLICY_H

#include "core/structs.h"

/* Command-facing item checks shared by get, put and empty. */
bool item_command_object_is_takeable(P_char actor, P_obj object);
bool item_command_container_is_valid(P_obj container);

#endif
