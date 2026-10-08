/****************************************************************************
 *
 *  File: flatfile_corpse_ownership.c                           Part of Duris
 *  Usage: who owns an item found in a flat-file corpse record
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "flatfile/flatfile_corpse_ownership.h"

#include "persistence/dupe_log.h"

#include <limits>
#include <new>
#include <unordered_map>
#include <utility>

item_owner_identity flatfile_corpse_item_owner(uint32_t owner_pid, uint32_t save_id)
{
	return { item_owner_type::corpse, item_corpse_owner_id(owner_pid, save_id), 0 };
}

flatfile_corpse_ownership_result
flatfile_world_filter_item_ownership(std::vector<player_item_snapshot> *items,
				     const item_owner_identity &owner, uint64_t owner_revision,
				     const std::vector<flatfile_item_ownership_record> &known,
				     std::vector<player_load_item_identity> *identities)
{
	if (!items || !identities || !item_owner_identity_valid(owner) ||
	    items->size() > static_cast<size_t>(std::numeric_limits<int>::max()))
		return flatfile_corpse_ownership_result::invalid;
	std::unordered_map<uint64_t, const flatfile_item_ownership_record *> by_uid;
	std::vector<player_item_snapshot> kept;
	std::vector<player_load_item_identity> reconciled;
	std::vector<int32_t> remap(items->size(), PLAYER_SNAPSHOT_NO_PARENT);
	try
	{
		by_uid.reserve(known.size());
		for (const auto &entry : known)
			by_uid.emplace(entry.item_uid, &entry);
		for (size_t index = 0; index < items->size(); ++index)
		{
			player_item_snapshot item = (*items)[index];
			if (!item.object_uid || item.equipment_slot != -1 ||
			    (item.parent_index != PLAYER_SNAPSHOT_NO_PARENT &&
			     (item.parent_index < 0 ||
			      static_cast<size_t>(item.parent_index) >= index)))
				return flatfile_corpse_ownership_result::invalid;
			const auto found = by_uid.find(item.object_uid);
			if (found != by_uid.end() &&
			    !item_owner_identity_equal(found->second->owner, owner))
			{
				dupe_log_item("load_skipped", item.object_uid, item.vnum, owner,
					      found->second->owner);
				continue;
			}
			const int32_t parent =
				item.parent_index == PLAYER_SNAPSHOT_NO_PARENT ?
					PLAYER_SNAPSHOT_NO_PARENT :
					remap[static_cast<size_t>(item.parent_index)];
			player_load_item_identity identity = {};
			identity.database_id = kept.size() + 1;
			identity.serialized_parent_id = parent == PLAYER_SNAPSHOT_NO_PARENT ?
								0 :
								static_cast<uint64_t>(parent) + 1;
			identity.quantity = 1;
			identity.override_mask = PLAYER_LOAD_ITEM_OVERRIDE_ALL;
			identity.item_uid = item.object_uid;
			identity.root_item_uid =
				parent == PLAYER_SNAPSHOT_NO_PARENT ?
					item.object_uid :
					reconciled[static_cast<size_t>(parent)].root_item_uid;
			identity.parent_item_uid =
				parent == PLAYER_SNAPSHOT_NO_PARENT ?
					0 :
					kept[static_cast<size_t>(parent)].object_uid;
			identity.owner = owner;
			identity.item_revision =
				found != by_uid.end() ? found->second->item_revision : 0;
			identity.owner_revision = owner_revision;
			identity.state = item_custody_state::active;
			item.parent_index = parent;
			remap[index] = static_cast<int32_t>(kept.size());
			kept.push_back(std::move(item));
			reconciled.push_back(identity);
		}
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_corpse_ownership_result::io_error;
	}
	*items = std::move(kept);
	*identities = std::move(reconciled);
	return flatfile_corpse_ownership_result::ok;
}

namespace
{
flatfile_corpse_ownership_result map_result(flatfile_item_repository_result result)
{
	return result == flatfile_item_repository_result::io_error ?
		       flatfile_corpse_ownership_result::io_error :
		       flatfile_corpse_ownership_result::invalid;
}
} // namespace

flatfile_corpse_ownership_result flatfile_world_load_item_ownership(
	const std::string &root, const item_owner_identity &owner,
	const std::vector<player_item_snapshot> &source, std::vector<player_item_snapshot> *items,
	uint64_t *owner_revision, std::vector<player_load_item_identity> *identities,
	std::string *error)
{
	if (!items || !owner_revision || !identities)
		return flatfile_corpse_ownership_result::invalid;
	uint64_t revision = 0;
	std::vector<flatfile_item_ownership_record> held;
	const auto loaded =
		flatfile_item_repository_load_owner(root, owner, &revision, &held, error);
	if (loaded == flatfile_item_repository_result::not_found)
		revision = 0;
	else if (loaded != flatfile_item_repository_result::ok)
		return map_result(loaded);
	std::vector<flatfile_item_ownership_record> known;
	try
	{
		*items = source;
		if (!source.empty())
		{
			std::vector<uint64_t> uids;
			uids.reserve(source.size());
			for (const auto &item : source)
				uids.push_back(item.object_uid);
			const auto found =
				flatfile_item_repository_load_uids(root, uids, &known, error);
			if (found != flatfile_item_repository_result::ok)
				return map_result(found);
		}
	}
	catch (const std::bad_alloc &)
	{
		return flatfile_corpse_ownership_result::io_error;
	}
	const auto filtered =
		flatfile_world_filter_item_ownership(items, owner, revision, known, identities);
	if (filtered == flatfile_corpse_ownership_result::ok)
		*owner_revision = revision;
	return filtered;
}

flatfile_corpse_ownership_result flatfile_corpse_load_item_ownership(
	const std::string &root, const flatfile_corpse_record &record,
	std::vector<player_item_snapshot> *items, uint64_t *owner_revision,
	std::vector<player_load_item_identity> *identities, std::string *error)
{
	if (!record.revision)
		return flatfile_corpse_ownership_result::invalid;
	return flatfile_world_load_item_ownership(
		root, flatfile_corpse_item_owner(record.owner_pid, record.save_id), record.items,
		items, owner_revision, identities, error);
}

flatfile_corpse_ownership_result flatfile_room_load_item_ownership(
	const std::string &root, const flatfile_room_item_record &record,
	std::vector<player_item_snapshot> *items, uint64_t *owner_revision,
	std::vector<player_load_item_identity> *identities, std::string *error)
{
	if (record.room_vnum <= 0 || !record.revision)
		return flatfile_corpse_ownership_result::invalid;
	return flatfile_world_load_item_ownership(
		root, { item_owner_type::room, static_cast<uint64_t>(record.room_vnum), 0 },
		record.items, items, owner_revision, identities, error);
}
