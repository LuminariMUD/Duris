/****************************************************************************
 *
 *  File: player_snapshot_capture.h                             Part of Duris
 *  Usage: player snapshot capture interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef PLAYER_SNAPSHOT_CAPTURE_H
#define PLAYER_SNAPSHOT_CAPTURE_H

#include "player/player_snapshot.h"

struct char_data;
typedef struct char_data *P_char;
struct obj_data;
typedef struct obj_data *P_obj;

player_snapshot_capture_result player_snapshot_capture(P_char ch, player_revision_t revision,
						       player_component_mask_t components,
						       int save_intent, int room_vnum,
						       player_snapshot *snapshot_out);
player_snapshot_capture_result
player_item_snapshot_list_capture(P_char owner, bool equipment, bool inventory, bool omit_norent,
				  std::vector<player_item_snapshot> *items_out,
				  size_t *estimated_bytes_out);
player_snapshot_capture_result
player_item_snapshot_tree_capture(P_obj root, std::vector<player_item_snapshot> *items_out,
				  size_t *estimated_bytes_out);
// Every item inside container, as top-level rows in snapshot order.
player_snapshot_capture_result
player_item_snapshot_contents_capture(P_obj container,
				      std::vector<player_item_snapshot> *items_out);

#endif
