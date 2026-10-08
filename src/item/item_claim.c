/****************************************************************************
 *
 *  File: item_claim.c                                          Part of Duris
 *  Usage: which held items a save leaves out
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "item/item_claim.h"

#include "persistence/dupe_log.h"

bool item_claim_leaves_out(item_custody_state state)
{
	return state == item_custody_state::destroyed;
}

std::vector<player_item_snapshot>
item_claim_written_items(const std::vector<player_item_snapshot> &items,
			 const std::unordered_set<uint64_t> &left_out)
{
	if (left_out.empty())
		return items;
	std::vector<player_item_snapshot> kept;
	std::vector<int32_t> remap(items.size(), PLAYER_SNAPSHOT_NO_PARENT);
	kept.reserve(items.size());
	for (size_t index = 0; index < items.size(); ++index)
	{
		const player_item_snapshot &item = items[index];
		if (item.object_uid && left_out.count(item.object_uid))
			continue;
		player_item_snapshot copy = item;
		if (item.parent_index >= 0 && static_cast<size_t>(item.parent_index) < index)
			copy.parent_index = remap[item.parent_index];
		remap[index] = static_cast<int32_t>(kept.size());
		kept.push_back(std::move(copy));
	}
	return kept;
}

void item_claim_log_dupes(const char *event, const item_owner_identity &owner,
			  const item_claim_outcome &outcome)
{
	for (const item_claim_dupe &dupe : outcome.dupes)
		dupe_log_item(event, dupe.item_uid, dupe.vnum, owner, dupe.held_by);
}
