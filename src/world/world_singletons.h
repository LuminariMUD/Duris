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

#include <vector>

// After the shops are booted, and whenever shop_index changes: singleton_shop_id() reads it.
void index_shopkeeper_prototypes();
// read_mobile() and extract_char() report each NPC, so that live_shopkeepers() can.
void shopkeeper_mob_created(P_char mob);
void shopkeeper_mob_extracted(P_char mob);
// The live characters singleton_shop_id() names `shop`, in no particular order.
std::vector<P_char> live_shopkeepers(int shop);
int singleton_shop_id(P_char keeper);
bool is_replicated_shop(int shop);
void bind_shopkeeper(P_char keeper, int shop_nr);
void remember_boot_shopkeepers();
bool snapshot_shopkeepers_for_copyover();
void reconcile_shopkeepers(bool recovered_inventory);

#endif
