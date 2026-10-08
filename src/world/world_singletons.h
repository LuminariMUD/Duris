/****************************************************************************
 *
 *  File: world_singletons.h                                    Part of Duris
 *  Usage: world singleton interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef WORLD_SINGLETONS_H
#define WORLD_SINGLETONS_H

#include "core/structs.h"

int singleton_shop_id(P_char keeper);
bool is_replicated_shop(int shop);
void bind_shopkeeper(P_char keeper, int shop_nr);
void remember_boot_shopkeepers();
bool snapshot_shopkeepers_for_copyover();
void reconcile_shopkeepers(bool recovered_inventory);

#endif
