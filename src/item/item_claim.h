#ifndef ITEM_CLAIM_H
#define ITEM_CLAIM_H

#include "item/item_transfer_command.h"
#include "player/player_snapshot.h"

#include <cstddef>
#include <cstdint>
#include <unordered_set>
#include <vector>

/*
 * A save claims what its owner holds in memory: it writes those items and makes
 * the ownership record agree, whoever the record named before. Two kinds of item
 * are left out, with their contents: those the economy holds (an auction, a
 * shopkeeper or the collector), because the economy still moves items through its
 * own transactions until Phase 2 of the persistence reset, and those whose record
 * says they were destroyed, because only a save captured before the destruction can
 * still hold them. Both backends use these rules: claim_items() in
 * item_claim_repository.c for MariaDB, and flatfile_item_repository_prepare_claim()
 * for the flat-file backend.
 */

struct item_claim_dupe
{
	uint64_t item_uid;
	int32_t vnum;
	item_owner_identity held_by;
};

struct item_claim_outcome
{
	// Items the save must not write, with their contents.
	std::unordered_set<uint64_t> left_out;
	// One entry per left-out item, for logs/log/dupes once the save commits.
	std::vector<item_claim_dupe> dupes;
	size_t inserted = 0;
	size_t claimed = 0;
};

bool item_claim_owner_is_economy(item_owner_type type);
// Owners whose holdings memory is the authority for: players, rooms, corpses, lockers
// and pets. A transfer out of or into one of them does not check that owner's revision
// or the item's recorded owner; it claims the items the way a save does.
inline bool item_claim_owner_is_memory_held(item_owner_type type)
{
	return type == item_owner_type::player || type == item_owner_type::room ||
	       type == item_owner_type::corpse || type == item_owner_type::locker ||
	       type == item_owner_type::pet;
}

// True when a save must leave out an item with this record: the economy holds it, or
// it was destroyed. A destroyed item stays destroyed, so an item sold to a shop for
// destruction, or a coin pile the currency transactions spent, never comes back from
// a save captured before that committed. A live coin pile is claimed like any item,
// so coins follow the bag that holds them.
bool item_claim_leaves_out(const item_owner_identity &owner, item_custody_state state);

// The items a save writes after its claim: all of them except those left with the
// economy. Parent indexes are renumbered for the items that remain.
std::vector<player_item_snapshot>
item_claim_written_items(const std::vector<player_item_snapshot> &items,
			 const std::unordered_set<uint64_t> &left_out);

// Write each left-out item to logs/log/dupes. Call after the save commits.
void item_claim_log_dupes(const char *event, const item_owner_identity &owner,
			  const item_claim_outcome &outcome);

#endif
