/****************************************************************************
 *
 *  File: persistence_checkpoint.h                              Part of Duris
 *  Usage: persistence checkpoint interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef PERSISTENCE_CHECKPOINT_H
#define PERSISTENCE_CHECKPOINT_H

#include "persistence/persistence_observability.h"
#include "player/player_revision_state.h"
#include "core/structs.h"

void mark_player_dirty_components(int pid, player_component_mask_t components);
int get_dirty_player_count(void);
struct persistence_dirty_save_snapshot persistence_dirty_save_snapshot_copy(void);
void event_flush_dirty_players(P_char ch, P_char victim, P_obj obj, void *data);

#endif
