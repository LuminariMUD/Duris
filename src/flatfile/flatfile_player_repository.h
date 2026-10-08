/****************************************************************************
 *
 *  File: flatfile_player_repository.h                          Part of Duris
 *  Usage: flat-file player repository types and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_FLATFILE_PLAYER_REPOSITORY_H
#define DURIS_FLATFILE_PLAYER_REPOSITORY_H

#include "economy/collector_storage.h"
#include "flatfile/flatfile_authority_transaction.h"
#include "flatfile/flatfile_locker_repository.h"
#include "flatfile/flatfile_player_snapshot_file.h"
#include "flatfile/flatfile_world_item_repository.h"
#include "player/player_load_repository.h"
#include "player/player_save_worker.h"

#include <memory>
#include <array>
#include <string>

class flatfile_player_snapshot_lock
{
    public:
	flatfile_player_snapshot_lock() noexcept;
	~flatfile_player_snapshot_lock();
	flatfile_player_snapshot_lock(const flatfile_player_snapshot_lock &) = delete;
	flatfile_player_snapshot_lock &operator=(const flatfile_player_snapshot_lock &) = delete;

	bool acquire(const std::string &root, int32_t pid, std::string *error);
	bool matches(const std::string &root, int32_t pid) const;

    private:
	struct state;
	std::unique_ptr<state> state_;
	bool owns(const std::string &root, int32_t pid) const;
};

flatfile_player_load_result flatfile_player_snapshot_load(const std::string &root, int32_t pid,
							  player_snapshot *snapshot,
							  std::string *error);
player_load_result flatfile_player_load_repository_execute(const std::string &root,
							   const player_load_request &request);
player_load_result
flatfile_player_load_repository_execute_selected(const player_load_request &request, void *context);
player_save_apply_result flatfile_player_snapshot_apply(const std::string &root,
							const player_snapshot &snapshot,
							std::string *error);
player_save_apply_result flatfile_player_snapshot_apply_selected(const player_snapshot &snapshot,
								 void *context);

// A bank change (the characters of an account share its bank), added to the account's
// bank record for that side in one authority transaction. The record with the change
// is prepared once, into *prepared (empty the first time): a retry after a commit that
// may already have written it writes the same record again instead of adding the
// change twice.
player_save_apply_result flatfile_bank_delta_apply(const std::string &root,
						   const std::string &account_name, int8_t racewar,
						   const std::array<int64_t, 4> &delta,
						   flatfile_authority_operation *prepared,
						   std::string *error);

// The flat-file corpse and saved-item saves: claim the items for their owner and
// write the corpse record, or the item's graph into its room's record, as memory holds
// it (or remove it), in one authority transaction. A corpse save carrying a death (a
// nonzero operation id) also enrols it with the collector.
player_save_apply_result flatfile_corpse_snapshot_apply(const std::string &root,
							const flatfile_corpse_record &corpse,
							bool remove,
							const collector_death_snapshot &death,
							std::string *error);
player_save_apply_result
flatfile_saved_item_snapshot_apply(const std::string &root,
				   const flatfile_saved_world_item_record &item, bool remove,
				   std::string *error);
// Write a locker's public chest, claiming its items for it, creating a new locker, in one
// authority transaction.
player_save_apply_result flatfile_locker_snapshot_apply(const std::string &root,
							const flatfile_locker_save &locker,
							std::string *error);
flatfile_player_load_result flatfile_player_snapshot_prepare_remove(
	const std::string &root, const flatfile_player_snapshot_lock &snapshot_lock,
	const flatfile_authority_lock &authority_lock, int32_t pid,
	flatfile_authority_operation *operation, std::string *error);

#endif
