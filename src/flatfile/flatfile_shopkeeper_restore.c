/****************************************************************************
 *
 *  File: flatfile_shopkeeper_restore.c                         Part of Duris
 *  Usage: restores saved shopkeepers from the flat-file store
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "flatfile/flatfile_shopkeeper_restore.h"

#include "flatfile/flatfile_shopkeeper_materialize.h"
#include "flatfile/flatfile_shopkeeper_capture.h"
#include "flatfile/flatfile_shopkeeper_ownership.h"
#include "flatfile/flatfile_item_repository.h"
#include "item/item_ownership_runtime.h"
#include "economy/shop_trade_runtime.h"
#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"
#include "world/world_singletons.h"

#include <new>
#include <unordered_set>
#include <vector>

extern P_char character_list;
extern P_index mob_index;
extern P_index obj_index;
extern struct shop_data *shop_index;
extern int number_of_shops;
extern int top_of_objt;
extern P_room world;
extern int top_of_world;

namespace
{
bool valid_shop_binding(const flatfile_shopkeeper_record &record)
{
	if (number_of_shops < 0 || record.shop_id >= static_cast<uint32_t>(number_of_shops))
		return false;
	const int mobile_rnum = real_mobile(record.mob_vnum);
	if (mobile_rnum < 0 || shop_index[record.shop_id].keeper != mobile_rnum)
		return false;
	if (record.room_vnum == 0 || real_room(record.room_vnum) == NOWHERE ||
	    (!shop_index[record.shop_id].shop_is_roaming &&
	     record.room_vnum != shop_index[record.shop_id].in_room))
		return false;
	const int produced_count = shop_index[record.shop_id].number_items_produced;
	if (produced_count < 0 || produced_count > MAX_PROD)
		return false;
	for (int produced = 0; produced < produced_count; ++produced)
	{
		const int object_rnum = shop_index[record.shop_id].producing[produced];
		// Legacy shop loading leaves missing prototypes disabled as -1, and
		// reconciliation never creates stock for those slots.
		if (object_rnum == -1)
			continue;
		if (object_rnum < 0 || object_rnum > top_of_objt)
			return false;
		const int object_vnum = obj_index[object_rnum].virtual_number;
		bool found = false;
		for (const auto &item : record.items)
			if (item.parent_index == PLAYER_SNAPSHOT_NO_PARENT &&
			    item.equipment_slot == 0 && item.vnum == object_vnum)
			{
				found = true;
				break;
			}
		if (!found)
			return false;
	}
	return true;
}

void forget_record_items(const flatfile_shopkeeper_record &record)
{
	for (const auto &item : record.items)
		item_ownership_runtime_forget(item.object_uid);
}

void discard_staged(std::vector<flatfile_materialized_shopkeeper> *staged,
		    const std::vector<flatfile_shopkeeper_record> &records)
{
	if (!staged)
		return;
	for (size_t index = 0; index < staged->size(); ++index)
	{
		forget_record_items(records[index]);
		if ((*staged)[index].character)
			extract_char((*staged)[index].character);
		(*staged)[index].character = nullptr;
	}
}
}

flatfile_shopkeeper_restore_result flatfile_shopkeeper_restore_catalog(const std::string &root,
								       std::string *error)
{
	std::vector<flatfile_shopkeeper_record> records;
	const auto listed = flatfile_shopkeeper_list(root, &records, error);
	if (listed != flatfile_shopkeeper_result::ok)
		return listed == flatfile_shopkeeper_result::not_found ?
			       flatfile_shopkeeper_restore_result::not_found :
		       listed == flatfile_shopkeeper_result::io_error ?
			       flatfile_shopkeeper_restore_result::io_error :
			       flatfile_shopkeeper_restore_result::invalid;

	std::unordered_set<uint64_t> shop_ids;
	std::vector<flatfile_materialized_shopkeeper> staged;
	try
	{
		shop_ids.reserve(records.size());
		staged.reserve(records.size());
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_shopkeeper_restore_result::io_error;
	}
	for (const auto &record : records)
	{
		try
		{
			const uint64_t identity = record.shop_id;
			if (!shop_ids.insert(identity).second || !valid_shop_binding(record))
			{
				if (error && error->empty())
					*error = "shop " + std::to_string(record.shop_id) +
						 " has an invalid saved binding";
				discard_staged(&staged, records);
				return flatfile_shopkeeper_restore_result::invalid;
			}
		}
		catch (const std::bad_alloc &)
		{
			discard_staged(&staged, records);
			return flatfile_shopkeeper_restore_result::io_error;
		}
		flatfile_materialized_shopkeeper materialized = {};
		const auto restored = flatfile_shopkeeper_materialize(root, record, &materialized,
								      nullptr, error);
		if (restored != flatfile_shopkeeper_materialize_result::ok)
		{
			if (error && error->empty())
				*error = "shop " + std::to_string(record.shop_id) +
					 " materialization=" +
					 std::to_string(static_cast<unsigned int>(restored));
			discard_staged(&staged, records);
			return flatfile_shopkeeper_restore_result::materialize_failure;
		}
		staged.push_back(materialized);
	}

	for (size_t index = 0; index < staged.size(); ++index)
		if (!char_to_room(staged[index].character, staged[index].room_rnum, 0))
		{
			forget_record_items(records[index]);
			staged[index].character = nullptr;
			discard_staged(&staged, records);
			return flatfile_shopkeeper_restore_result::publish_failure;
		}
		else if (staged[index].character->in_room != staged[index].room_rnum)
		{
			discard_staged(&staged, records);
			return flatfile_shopkeeper_restore_result::publish_failure;
		}
	std::unordered_set<P_char> replacements;
	try
	{
		replacements.reserve(staged.size());
		for (const auto &entry : staged)
			replacements.insert(entry.character);
	}
	catch (const std::bad_alloc &)
	{
		discard_staged(&staged, records);
		return flatfile_shopkeeper_restore_result::io_error;
	}
	if (!shop_trade_runtime_replace_revisions(records))
	{
		discard_staged(&staged, records);
		return flatfile_shopkeeper_restore_result::io_error;
	}
	for (const auto &record : records)
	{
		P_char incumbent = nullptr;
		int incumbent_count = 0;
		for (P_char existing : live_shopkeepers(static_cast<int>(record.shop_id)))
		{
			if (replacements.find(existing) != replacements.end() ||
			    existing->in_room < 0 || existing->in_room > top_of_world ||
			    mob_index[GET_RNUM(existing)].virtual_number != record.mob_vnum ||
			    (!shop_index[record.shop_id].shop_is_roaming &&
			     world[existing->in_room].number != record.room_vnum))
				continue;
			incumbent = existing;
			++incumbent_count;
		}
		if (incumbent_count == 1)
			extract_char(incumbent);
	}
	for (const auto &record : records)
	{
		shop_index[record.shop_id].dirty = 1;
		shopkeeper_save_retry_reset(&shop_index[record.shop_id].dirty_save_retry);
	}
	return flatfile_shopkeeper_restore_result::ok;
}

bool flatfile_shopkeeper_bootstrap_new(const std::string &root, std::string *error)
{
	std::vector<flatfile_shopkeeper_record> records, additions;
	const auto listed = flatfile_shopkeeper_list(root, &records, error);
	if (listed != flatfile_shopkeeper_result::ok &&
	    listed != flatfile_shopkeeper_result::not_found)
		return false;
	try
	{
		std::unordered_set<uint32_t> known;
		for (const auto &record : records)
			known.insert(record.shop_id);
		for (int shop = 0; shop < number_of_shops; ++shop)
		{
			if (known.count(static_cast<uint32_t>(shop)))
				continue;
			const auto keepers = live_shopkeepers(shop);
			if (keepers.empty())
				continue;
			if (keepers.size() != 1)
			{
				if (error)
					*error = "new shop has ambiguous live keepers";
				return false;
			}
			flatfile_shopkeeper_record record;
			const auto captured = flatfile_shopkeeper_capture(
				keepers.front(), static_cast<uint32_t>(shop), 1, time(nullptr),
				&record);
			if (captured != player_snapshot_capture_result::ok ||
			    !valid_shop_binding(record))
			{
				if (error)
					*error = "new shop " + std::to_string(shop) +
						 " stock capture=" +
						 std::to_string(
							 static_cast<unsigned int>(captured)) +
						 " mob=" + std::to_string(record.mob_vnum) +
						 " room=" + std::to_string(record.room_vnum);
				return false;
			}
			additions.push_back(std::move(record));
		}
		if (additions.empty())
			return true;
		{
			flatfile_authority_lock lock;
			if (!lock.acquire(root, error))
				return false;
			flatfile_authority_after_image shops;
			if (flatfile_shopkeeper_prepare_addition(root, lock, additions, &shops,
								 error) !=
			    flatfile_shopkeeper_result::ok)
			{
				if (error && error->empty())
					*error = "new shop catalog preparation failed";
				return false;
			}
			std::vector<flatfile_item_claim> claims;
			std::vector<uint64_t> uids;
			for (const auto &record : additions)
			{
				const auto owner = flatfile_shopkeeper_item_owner(record.shop_id);
				uint64_t revision = 0;
				std::vector<flatfile_item_ownership_record> held;
				if (flatfile_item_repository_load_owner_locked(
					    root, lock, owner, &revision, &held, error) !=
				    flatfile_item_repository_result::not_found)
				{
					if (error)
						*error = "new shop already has item custody";
					return false;
				}
				claims.push_back({ owner, &record.items, {}, true });
				for (const auto &item : record.items)
					uids.push_back(item.object_uid);
			}
			std::vector<flatfile_item_ownership_record> existing;
			const auto found = flatfile_item_repository_load_uids_locked(
				root, lock, uids, &existing, error);
			if ((found != flatfile_item_repository_result::ok &&
			     found != flatfile_item_repository_result::not_found) ||
			    !existing.empty())
			{
				if (error)
					*error = "new shop stock already has item custody";
				return false;
			}
			flatfile_authority_operation custody;
			std::vector<flatfile_item_claim_audit> audits;
			if (flatfile_item_repository_prepare_claim(root, lock, &claims, &custody,
								   &audits, error) !=
			    flatfile_item_repository_result::ok)
			{
				if (error && error->empty())
					*error = "new shop custody preparation failed";
				return false;
			}
			flatfile_authority_operation catalog;
			catalog.filename = std::move(shops.filename);
			catalog.bytes = std::move(shops.bytes);
			if (flatfile_authority_transaction_commit_operations(
				    root, lock, { custody, catalog }, error) !=
			    flatfile_authority_transaction_result::ok)
			{
				if (error && error->empty())
					*error = "new shop atomic initialization failed";
				return false;
			}
		}
		for (const auto &record : additions)
		{
			std::vector<item_ownership_runtime_entry> ownership;
			uint64_t revision = 0;
			std::vector<player_load_item_identity> identities;
			if (flatfile_shopkeeper_load_item_ownership(root, record, &revision,
								    &identities, error) !=
			    flatfile_shopkeeper_ownership_result::ok)
			{
				if (error && error->empty())
					*error = "new shop custody reload failed";
				return false;
			}
			for (size_t index = 0; index < identities.size(); ++index)
			{
				const auto &identity = identities[index];
				ownership.push_back({ identity.item_uid, identity.root_item_uid,
						      identity.parent_item_uid, identity.owner,
						      identity.item_revision,
						      identity.owner_revision,
						      record.items[index].vnum, identity.state });
			}
			if (!item_ownership_runtime_hydrate_batch(ownership.data(),
								  ownership.size()))
			{
				if (error && error->empty())
					*error = "new shop custody publication failed: " +
						 std::to_string(record.shop_id);
				return false;
			}
			records.push_back(record);
		}
		if (!shop_trade_runtime_replace_revisions(records))
		{
			if (error && error->empty())
				*error = "new shop runtime publication failed";
			return false;
		}
		return true;
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
}
