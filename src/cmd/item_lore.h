/****************************************************************************
 *
 *  File: item_lore.h                                           Part of Duris
 *  Usage: captures an item's description for lore
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_ITEM_LORE_H
#define DURIS_ITEM_LORE_H
#include "core/structs.h"
#include <string>
// Capture the current item description without sending output or imposing recovery.
std::string item_lore_description(P_char ch, P_obj obj);
#endif
