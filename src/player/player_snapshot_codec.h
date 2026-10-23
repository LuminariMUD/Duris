/****************************************************************************
 *
 *  File: player_snapshot_codec.h                               Part of Duris
 *  Usage: player snapshot codec interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef PLAYER_SNAPSHOT_CODEC_H
#define PLAYER_SNAPSHOT_CODEC_H

#include "player/player_snapshot.h"

#include <cstdint>
#include <vector>

enum class player_snapshot_codec_result : uint8_t
{
	ok,
	invalid_value,
	truncated,
	limit_exceeded,
	unsupported_version,
	allocation_failure,
};

// Missing in old/partial snapshots means no delivered Divine award. A duplicate
// or signed marker is malformed, rather than permission to reset delivery.
bool player_snapshot_divine_delivery_sequence(const player_snapshot &snapshot, uint64_t *sequence);
// Partial status operations that do not touch money do not advance its revision.
bool player_snapshot_writes_wallet(const player_snapshot &snapshot);
// One affect row, shared with compound cargo settlement. Its enclosing payload
// owns the wire version, independently of full player snapshots.
player_snapshot_codec_result player_affect_snapshot_encode(const player_affect_snapshot &affect,
							   std::vector<uint8_t> *bytes);
player_snapshot_codec_result player_affect_snapshot_decode(const uint8_t *bytes, size_t size,
							   player_affect_snapshot *affect);
bool player_snapshot_trade_pending(const player_snapshot &snapshot);
// Reconcile only the captured operation, once, in an owned snapshot copy.
player_snapshot_codec_result player_snapshot_settle_trade(player_snapshot *snapshot,
							  bool committed);

player_snapshot_codec_result player_snapshot_encode(const player_snapshot &snapshot,
						    std::vector<uint8_t> *encoded_out);
player_snapshot_codec_result player_snapshot_decode(const uint8_t *encoded, size_t encoded_size,
						    player_snapshot *snapshot_out);
player_snapshot_codec_result
player_item_snapshot_list_encode(const std::vector<player_item_snapshot> &items,
				 std::vector<uint8_t> *encoded_out);
player_snapshot_codec_result
player_item_snapshot_list_decode(const uint8_t *encoded, size_t encoded_size,
				 std::vector<player_item_snapshot> *items_out);
player_snapshot_codec_result
player_item_snapshot_extract_subtree(const std::vector<player_item_snapshot> &items,
				     uint64_t selected_uid,
				     std::vector<player_item_snapshot> *selected_out,
				     std::vector<player_item_snapshot> *remaining_out);
player_snapshot_codec_result
player_item_snapshot_extract_forest(const std::vector<player_item_snapshot> &items,
				    const std::vector<uint64_t> &selected_root_uids,
				    std::vector<player_item_snapshot> *selected_out,
				    std::vector<player_item_snapshot> *remaining_out);

#endif
