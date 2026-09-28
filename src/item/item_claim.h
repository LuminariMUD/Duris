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
 * the ownership record agree, whoever the record named before. Only items the
 * economy holds (an auction, a shopkeeper or the collector) are left out, with
 * their contents, because the economy still moves items through its own
 * transactions until Phase 2 of the persistence reset. Both backends use these
 * rules: claim_items() in item_claim_repository.c for MariaDB, and
 * flatfile_item_repository_prepare_claim() for the flat-file backend.
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

// Coin piles keep the ownership the currency transactions give them until
// Phase 2: a save records a pile nobody has recorded, and writes a pile it holds,
// but never takes or revives one the ownership record gives elsewhere.
bool item_claim_leaves_owner_alone(const player_item_snapshot &item);

// The items a save writes after its claim: all of them except those left with the
// economy. Parent indexes are renumbered for the items that remain.
std::vector<player_item_snapshot>
item_claim_written_items(const std::vector<player_item_snapshot> &items,
			 const std::unordered_set<uint64_t> &left_out);

// Write each left-out item to logs/log/dupes. Call after the save commits.
void item_claim_log_dupes(const char *event, const item_owner_identity &owner,
			  const item_claim_outcome &outcome);

#endif
