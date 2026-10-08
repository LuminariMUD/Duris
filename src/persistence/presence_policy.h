/****************************************************************************
 *
 *  File: presence_policy.h                                     Part of Duris
 *  Usage: presence policy interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef PRESENCE_POLICY_H
#define PRESENCE_POLICY_H

#include "core/structs.h"

bool durisweb_private_presence_enabled(void);
bool durisweb_presence_character_visible(P_char ch);

#endif
