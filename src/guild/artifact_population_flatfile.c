#include "guild/artifact_population_repository.h"

#include "guild/artifact_identity.h"
#include "flatfile/flatfile_auction_repository.h"
#include "flatfile/flatfile_collector_repository.h"
#include "flatfile/flatfile_item_repository.h"
#include "flatfile/flatfile_locker_repository.h"
#include "flatfile/flatfile_player_snapshot_file.h"
#include "flatfile/flatfile_shopkeeper_repository.h"
#include "flatfile/flatfile_shop_trade_materialization.h"
#include "flatfile/flatfile_world_item_repository.h"
#include "item/legacy_object_identity.h"
#include "player/player_snapshot_codec.h"

#include <algorithm>
#include <cerrno>
#include <charconv>
#include <filesystem>
#include <new>

namespace
{
// Input graphs have already passed the selected store's bounded snapshot codec.
unsigned int append_items(artifact_payload_domain domain, int64_t owner_reference,
			  uint64_t owner_context, const item_owner_identity &owner,
			  const std::vector<player_item_snapshot> &items,
			  std::vector<artifact_payload_projection> *projections)
{
	if (items.size() > ARTIFACT_IDENTITY_MAX_RECORDS - projections->size())
		return E2BIG;
	for (size_t index = 0; index < items.size(); ++index)
	{
		const auto &item = items[index];
		artifact_payload_projection row = {};
		row.domain = domain;
		row.row_id = index + 1;
		row.item_uid = item.object_uid;
		if (item.parent_index != PLAYER_SNAPSHOT_NO_PARENT)
		{
			row.parent_row_id = static_cast<uint64_t>(item.parent_index) + 1;
			row.parent_item_uid = items[item.parent_index].object_uid;
			row.parent_missing = !row.parent_item_uid;
		}
		row.owner_reference = owner_reference;
		row.owner_context = owner_context;
		row.payload_owner = owner;
		row.vnum = item.vnum;
		row.extra_flags = item.extra_flags;
		row.extra_flags_present = true;
		row.quantity = 1;
		projections->push_back(row);
	}
	return 0;
}

unsigned int read_players(const std::string &root, std::vector<artifact_payload_projection> *items,
			  std::string *error)
{
	const auto directory = flatfile_player_snapshot_file::player_directory(root);
	const auto suffix = flatfile_player_snapshot_file::player_filename(1).substr(1);
	std::error_code failure;
	std::filesystem::directory_iterator entry(directory, failure), end;
	if (failure == std::errc::no_such_file_or_directory)
		return 0;
	size_t entries = 0;
	for (; !failure && entry != end; entry.increment(failure))
	{
		if (++entries > ARTIFACT_IDENTITY_MAX_RECORDS)
			return E2BIG;
		const auto name = entry->path().filename().string();
		if (!name.ends_with(suffix))
			continue;
		int32_t pid = 0;
		const char *last = name.data() + name.size() - suffix.size();
		const auto parsed = std::from_chars(name.data(), last, pid);
		if (parsed.ec != std::errc{} || parsed.ptr != last || pid <= 0 ||
		    name != flatfile_player_snapshot_file::player_filename(pid))
		{
			if (error)
				*error = "noncanonical player population filename";
			return EINVAL;
		}
		player_snapshot snapshot;
		const auto loaded = flatfile_player_snapshot_read(root, pid, &snapshot, error);
		if (loaded != flatfile_player_load_result::ok)
			return loaded == flatfile_player_load_result::io_error ? EIO : EINVAL;
		if (const auto failed =
			    append_items(artifact_payload_domain::player, pid, 0,
					 { item_owner_type::player, static_cast<uint64_t>(pid), 0 },
					 snapshot.items, items))
			return failed;
		for (size_t pet = 0; pet < snapshot.pets.size(); ++pet)
		{
			const auto &saved = snapshot.pets[pet];
			const item_owner_identity owner =
				saved.pet_uid ?
					item_owner_identity{ item_owner_type::pet, saved.pet_uid,
							     static_cast<uint64_t>(pid) } :
					item_owner_identity{ item_owner_type::player,
							     static_cast<uint64_t>(pid), 0 };
			if (const auto failed = append_items(artifact_payload_domain::pet, pid,
							     pet + 1, owner, saved.items, items))
				return failed;
		}
	}
	if (failure && error)
		*error = "player population directory read failed";
	return failure ? EIO : 0;
}

unsigned int read_blob_payloads(const std::string &root,
				std::vector<artifact_payload_projection> *items, std::string *error)
{
	{
		std::vector<flatfile_auction_listing_projection> listings;
		const auto read = flatfile_auction_list_retained(root, &listings, error);
		if (read != flatfile_auction_query_result::ok)
			return read == flatfile_auction_query_result::io_error ? EIO : EINVAL;
		for (const auto &listing : listings)
		{
			legacy_object_identity identity;
			if (!legacy_object_identity_read(listing.object_blob.data(),
							 listing.object_blob.size(), &identity))
			{
				if (error)
					*error = "invalid auction population payload listing=" +
						 std::to_string(listing.auction_id);
				return EINVAL;
			}
			for (size_t index = 0; index < listing.items.size(); ++index)
			{
				const auto &item = listing.items[index];
				if (item.vnum != identity.vnum)
				{
					if (error)
						*error =
							"auction population vnum mismatch listing=" +
							std::to_string(listing.auction_id);
					return EINVAL;
				}
				if (items->size() == ARTIFACT_IDENTITY_MAX_RECORDS)
					return E2BIG;
				artifact_payload_projection row = {};
				row.domain = artifact_payload_domain::auction;
				row.role = item.claimed ? artifact_payload_role::history :
							  artifact_payload_role::stored;
				row.row_id = index + 1;
				// The claim path replaces the template blob's UID with this binding.
				row.item_uid = item.item_uid;
				row.owner_reference = listing.auction_id;
				row.owner_context = item.claim_pid;
				row.payload_owner =
					item.claimed ?
						item_owner_identity{ item_owner_type::player,
								     item.claim_pid, 0 } :
						item_owner_identity{ item_owner_type::auction,
								     listing.auction_id, 0 };
				row.vnum = identity.vnum;
				row.extra_flags = identity.extra_flags;
				row.extra_flags_present = identity.extra_flags_present;
				row.quantity = 1;
				items->push_back(row);
			}
		}
	}
	{
		std::vector<collector_listing_detail> listings;
		const auto read =
			flatfile_collector_repository_read_payloads(root, &listings, error);
		if (read != flatfile_collector_repository_result::ok)
			return read == flatfile_collector_repository_result::io_error ? EIO :
											EINVAL;
		for (const auto &listing : listings)
		{
			std::vector<player_item_snapshot> decoded;
			const auto parsed = player_item_snapshot_list_decode(
				listing.item_blob.data(), listing.item_blob.size(), &decoded);
			if (parsed != player_snapshot_codec_result::ok)
				return parsed == player_snapshot_codec_result::allocation_failure ?
					       ENOMEM :
					       EINVAL;
			const auto &entry = listing.entry;
			const size_t first = items->size();
			if (const auto failed =
				    append_items(artifact_payload_domain::collector,
						 entry.beneficiary, entry.listing,
						 { item_owner_type::collector,
						   item_collector_owner_id(entry.listing), 0 },
						 decoded, items))
				return failed;
			critical_operation_id operation;
			if (!critical_operation_id_from_hex(entry.death_operation.data(),
							    &operation))
				return EINVAL;
			for (size_t index = first; index < items->size(); ++index)
			{
				(*items)[index].source_operation = operation;
				(*items)[index].role =
					entry.status == collector::state::collected ||
							entry.status ==
								collector::state::available ?
						artifact_payload_role::stored :
						artifact_payload_role::history;
			}
		}
	}
	{
		flatfile_authority_lock lock;
		if (!lock.acquire(root, error))
			return EIO;
		std::vector<flatfile_item_materialization_projection> events;
		const auto read = flatfile_item_materialization_read(root, lock, &events, error);
		if (read != flatfile_shop_trade_materialization_result::ok)
			return read == flatfile_shop_trade_materialization_result::io_error ?
				       EIO :
				       EINVAL;
		for (size_t event_index = 0; event_index < events.size(); ++event_index)
		{
			const auto &event = events[event_index];
			const size_t first = items->size();
			if (const auto failed = append_items(artifact_payload_domain::delivery,
							     event.player_pid, 0, event.owner,
							     event.items, items))
				return failed;
			for (size_t index = first; index < items->size(); ++index)
			{
				(*items)[index].source_operation = event.operation_id;
				(*items)[index].delivery_ordinal = event_index + 1;
				(*items)[index].role = event.inbound ?
							       artifact_payload_role::delivery :
							       artifact_payload_role::history;
			}
		}
	}
	return 0;
}
} // namespace

unsigned int artifact_population_read_flat_payloads(const std::string &root,
						    std::vector<artifact_payload_projection> *items,
						    std::string *error)
{
	if (root.empty() || !items)
		return EINVAL;
	if (error)
		error->clear();
	try
	{
		std::vector<artifact_payload_projection> staged;
		{
			std::vector<flatfile_locker_record> lockers;
			std::vector<flatfile_locker_access_record> access;
			const auto read = flatfile_locker_list(root, &lockers, &access, error);
			if (read != flatfile_locker_result::ok &&
			    read != flatfile_locker_result::not_found)
				return read == flatfile_locker_result::io_error ? EIO : EINVAL;
			for (const auto &locker : lockers)
				for (const auto &chest : locker.chests)
					if (const auto failed = append_items(
						    artifact_payload_domain::locker,
						    locker.locker_id, chest.chest_id,
						    { item_owner_type::locker, locker.locker_id,
						      chest.chest_id },
						    chest.items, &staged))
						return failed;
		}
		if (const auto failed = read_players(root, &staged, error))
			return failed;
		{
			std::vector<flatfile_corpse_record> corpses;
			std::vector<flatfile_saved_world_item_record> saved;
			const auto read = flatfile_world_item_list(root, &corpses, &saved, error);
			if (read != flatfile_world_item_result::ok &&
			    read != flatfile_world_item_result::not_found)
				return read == flatfile_world_item_result::io_error ? EIO : EINVAL;
			for (const auto &corpse : corpses)
				if (const auto failed =
					    append_items(artifact_payload_domain::corpse,
							 corpse.owner_pid, corpse.save_id,
							 { item_owner_type::corpse,
							   item_corpse_owner_id(corpse.owner_pid,
										corpse.save_id),
							   0 },
							 corpse.items, &staged))
					return failed;
			for (const auto &record : saved)
				if (const auto failed = append_items(
					    artifact_payload_domain::room, record.room_vnum,
					    record.items.front().object_uid,
					    { item_owner_type::room,
					      static_cast<uint64_t>(record.room_vnum), 0 },
					    record.items, &staged))
					return failed;
		}
		{
			std::vector<flatfile_room_item_record> rooms;
			const auto read = flatfile_world_item_list_rooms(root, &rooms, error);
			if (read != flatfile_world_item_result::ok &&
			    read != flatfile_world_item_result::not_found)
				return read == flatfile_world_item_result::io_error ? EIO : EINVAL;
			for (const auto &room : rooms)
				if (const auto failed = append_items(
					    artifact_payload_domain::room, room.room_vnum, 0,
					    { item_owner_type::room,
					      static_cast<uint64_t>(room.room_vnum), 0 },
					    room.items, &staged))
					return failed;
		}
		{
			std::vector<flatfile_shopkeeper_record> shops;
			const auto read = flatfile_shopkeeper_list(root, &shops, error);
			if (read != flatfile_shopkeeper_result::ok &&
			    read != flatfile_shopkeeper_result::not_found)
				return read == flatfile_shopkeeper_result::io_error ? EIO : EINVAL;
			for (const auto &shop : shops)
				if (const auto failed = append_items(
					    artifact_payload_domain::shopkeeper, shop.shop_id, 0,
					    { item_owner_type::shopkeeper,
					      item_shopkeeper_owner_id(shop.shop_id), 0 },
					    shop.items, &staged))
					return failed;
		}
		if (const auto failed = read_blob_payloads(root, &staged, error))
			return failed;
		std::vector<flatfile_item_ownership_record> custody;
		const auto read = flatfile_item_repository_read_population(root, &custody, error);
		if (read != flatfile_item_repository_result::ok)
			return read == flatfile_item_repository_result::io_error ? EIO : EINVAL;
		for (const auto &record : custody)
		{
			if (record.coin_payload.empty())
				continue;
			std::vector<player_item_snapshot> decoded;
			const auto parsed = player_item_snapshot_list_decode(
				record.coin_payload.data(), record.coin_payload.size(), &decoded);
			if (parsed != player_snapshot_codec_result::ok)
				return parsed == player_snapshot_codec_result::allocation_failure ?
					       ENOMEM :
					       EINVAL;
			const size_t first = staged.size();
			if (const auto failed = append_items(artifact_payload_domain::embedded, 0,
							     record.item_uid, {}, decoded, &staged))
				return failed;
			// Current loaders use this legacy field for compatibility checks;
			// they do not materialize it as a pending delivery. An active custody
			// record does not turn its retained historical bytes into a live copy.
			for (size_t index = first; index < staged.size(); ++index)
				staged[index].role = artifact_payload_role::history;
		}
		for (auto &row : staged)
		{
			const auto found = std::lower_bound(custody.begin(), custody.end(),
							    row.item_uid,
							    [](const auto &entry, uint64_t uid)
							    { return entry.item_uid < uid; });
			if (found == custody.end() || found->item_uid != row.item_uid)
				continue;
			row.custody_found = true;
			row.custody = {
				found->item_uid, found->root_item_uid, found->parent_item_uid,
				found->owner,	 found->item_revision, 0,
				found->vnum,	 found->state
			};
		}
		*items = std::move(staged);
		return 0;
	}
	catch (const std::bad_alloc &)
	{
		return ENOMEM;
	}
}
