#ifndef DURIS_FLATFILE_CORPSE_OWNERSHIP_H
#define DURIS_FLATFILE_CORPSE_OWNERSHIP_H

#include "flatfile/flatfile_item_repository.h"
#include "player/player_load_repository.h"

#include <cstdint>
#include <string>
#include <vector>

enum class flatfile_corpse_ownership_result
{
	ok,
	not_found,
	invalid,
	io_error,
};

item_owner_identity flatfile_corpse_item_owner(uint32_t owner_pid, uint32_t save_id);
// A world record's item is taken if the ownership catalog has no record for it or
// names this owner. One naming anyone else is a stale copy: it is skipped and logged
// to logs/log/dupes, and what it held moves to the top level. `known` holds the
// catalog record of every item uid that has one.
flatfile_corpse_ownership_result
flatfile_world_filter_item_ownership(std::vector<player_item_snapshot> *items,
				     const item_owner_identity &owner, uint64_t owner_revision,
				     const std::vector<flatfile_item_ownership_record> &known,
				     std::vector<player_load_item_identity> *identities);
// Load what a corpse or room record holds through that filter; `items` receives the
// items to restore.
flatfile_corpse_ownership_result flatfile_corpse_load_item_ownership(
	const std::string &root, const flatfile_corpse_record &record,
	std::vector<player_item_snapshot> *items, uint64_t *owner_revision,
	std::vector<player_load_item_identity> *identities, std::string *error);
flatfile_corpse_ownership_result flatfile_room_load_item_ownership(
	const std::string &root, const flatfile_room_item_record &record,
	std::vector<player_item_snapshot> *items, uint64_t *owner_revision,
	std::vector<player_load_item_identity> *identities, std::string *error);

#endif
