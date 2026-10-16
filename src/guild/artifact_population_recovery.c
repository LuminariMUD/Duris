#include "guild/artifact_population_repository.h"

#include "redis/redis_world_runtime.h"
#include "persistence/copyover.h"
#include "world/world_recovery_codec.h"

#include <algorithm>
#include <cerrno>
#include <climits>
#include <cstring>
#include <new>
#include <unordered_map>
#include <unordered_set>

namespace
{
unsigned int append_tree(const std::vector<unsigned char> &native, artifact_payload_domain domain,
			 uint64_t sequence, std::unordered_set<uint64_t> *seen,
			 artifact_recovery_population *population)
{
	world_recovery_object_record record = {};
	std::vector<world_recovery_item_snapshot> items;
	if (!world_recovery_read_object_record(native.data(), native.size(), &record, &items))
		return EINVAL;
	const auto overlaps =
		static_cast<size_t>(std::count_if(items.begin(), items.end(), [&](const auto &item)
						  { return seen->count(item.item_uid) != 0; }));
	const bool repeated = domain == artifact_payload_domain::redis_floor &&
			      overlaps == items.size();
	const bool conflict = overlaps && !repeated;
	population->restore_conflict = population->restore_conflict || conflict;
	std::unordered_map<uint64_t, uint64_t> row_ids;
	row_ids.reserve(items.size());
	for (const auto &item : items)
	{
		artifact_payload_projection row = {};
		row.domain = domain;
		row.role = repeated ? artifact_payload_role::history :
				      artifact_payload_role::stored;
		row.row_id = population->items.size() + 1;
		row.item_uid = item.item_uid;
		row.payload_root_item_uid = item.root_item_uid;
		row.parent_item_uid = item.parent_item_uid;
		if (item.parent_item_uid)
			row.parent_row_id = row_ids.at(item.parent_item_uid);
		row.owner_reference = record.room_vnum;
		row.owner_context = sequence;
		row.payload_owner = {
			item_owner_type::room,
			record.room_vnum >= 0 ? static_cast<uint64_t>(record.room_vnum) : 0, 0
		};
		row.vnum = item.vnum;
		row.extra_flags = item.extra_flags;
		row.extra_flags_present = true;
		row.quantity = 1;
		row.custody_required = (item.flags & WORLD_RECOVERY_ITEM_AUTHORITY_REQUIRED) != 0;
		row.source_quarantined = conflict;
		row_ids.emplace(item.item_uid, row.row_id);
		population->items.push_back(row);
	}
	if (!repeated)
		for (const auto &item : items)
			seen->insert(item.item_uid);
	return 0;
}
} // namespace

unsigned int artifact_population_read_recovery(const redis_world_boot_snapshot &snapshot,
					       artifact_recovery_population *population)
{
	if (!population)
		return EINVAL;
	if (snapshot.generation.size() > WORLD_RECOVERY_MAX_BYTES ||
	    snapshot.floor_records.size() > WORLD_RECOVERY_MAX_FLOOR_RECORDS)
		return E2BIG;
	size_t floor_bytes = 0;
	for (const auto &floor : snapshot.floor_records)
	{
		if (floor.size() > WORLD_RECOVERY_MAX_FLOOR_BYTES - floor_bytes)
			return E2BIG;
		floor_bytes += floor.size();
	}
	if (floor_bytes > WORLD_RECOVERY_MAX_BYTES - snapshot.generation.size())
		return E2BIG;
	if (!snapshot.sequence)
	{
		if (!snapshot.generation.empty() || !snapshot.floor_records.empty())
			return EINVAL;
		*population = {};
		return 0;
	}
	world_recovery_header header = {};
	// Freshness/authentication were established by preparation. Reuse framing
	// validation without making a long boot change the already-pinned source cut.
	if (!world_recovery_validate(snapshot.generation.data(), snapshot.generation.size(),
				     INT_MAX, snapshot.sequence, &header) ||
	    header.sequence != snapshot.sequence)
		return EINVAL;
	try
	{
		artifact_recovery_population staged;
		std::unordered_set<uint64_t> seen;
		size_t offset = WORLD_RECOVERY_WIRE_HEADER_BYTES;
		while (offset < snapshot.generation.size())
		{
			world_recovery_record_type type = {};
			uint32_t size = 0;
			if (!world_recovery_decode_record_header(
				    snapshot.generation.data() + offset,
				    snapshot.generation.size() - offset, &type, &size))
				return EINVAL;
			offset += WORLD_RECOVERY_WIRE_RECORD_HEADER_BYTES;
			std::vector<unsigned char> native;
			if (size > snapshot.generation.size() - offset ||
			    !world_recovery_decode_record(type, snapshot.generation.data() + offset,
							  size, &native))
				return EINVAL;
			if (type == world_recovery_record_type::object)
			{
				if (const auto failed = append_tree(
					    native, artifact_payload_domain::redis_generation,
					    snapshot.sequence, &seen, &staged))
					return failed;
			}
			else if (type == world_recovery_record_type::mob)
			{
				copyover_mob mob = {};
				memcpy(&mob, native.data(), sizeof(mob));
				artifact_recovery_mob_projection row = {};
				row.vnum = mob.vnum;
				row.instance_id = mob.idnum;
				row.room_vnum = mob.room;
				row.birthplace = mob.birthplace;
				row.shopkeeper_shop_id = mob.shopkeeper_shop_id;
				staged.mobs.push_back(row);
			}
			offset += size;
		}
		for (const auto &floor : snapshot.floor_records)
		{
			uint64_t root = 0;
			std::vector<unsigned char> native;
			if (!world_recovery_floor_object_root_uid(floor.data(), floor.size(),
								  &root) ||
			    !world_recovery_decode_record(
				    world_recovery_record_type::object,
				    floor.data() + WORLD_RECOVERY_FLOOR_PREFIX_BYTES,
				    floor.size() - WORLD_RECOVERY_FLOOR_PREFIX_BYTES, &native))
				return EINVAL;
			if (const auto failed = append_tree(native,
							    artifact_payload_domain::redis_floor,
							    snapshot.sequence, &seen, &staged))
				return failed;
		}
		*population = std::move(staged);
		return 0;
	}
	catch (const std::bad_alloc &)
	{
		return ENOMEM;
	}
}
