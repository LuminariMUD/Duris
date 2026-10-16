#include "guild/artifact_population_repository.h"
#include "redis/redis_world_runtime.h"
#include "persistence/copyover.h"
#include "world/world_recovery_codec.h"

#include <array>
#include <cassert>
#include <cerrno>
#include <climits>
#include <cstring>
#include <ctime>
#include <iostream>
#include <vector>
#include <zlib.h>

static unsigned int template_reads = 0, extractions = 0, custody_reads = 0;
P_obj read_object(int, int)
{
	++template_reads;
	return nullptr;
}
void extract_obj(P_obj, int)
{
	++extractions;
}
bool item_ownership_runtime_lookup(uint64_t, item_ownership_runtime_entry *)
{
	++custody_reads;
	return false;
}

static world_recovery_item_snapshot item(uint64_t uid, uint64_t root, uint64_t parent,
					 int vnum = 900)
{
	world_recovery_item_snapshot value = {};
	value.item_uid = uid;
	value.root_item_uid = root;
	value.parent_item_uid = parent;
	value.vnum = vnum;
	value.extra_flags = 1U << 28;
	return value;
}
static std::vector<unsigned char> tree(const std::vector<world_recovery_item_snapshot> &items,
				       int room = 100)
{
	world_recovery_object_record record = { room, static_cast<uint32_t>(items.size()) };
	std::vector<unsigned char> native(sizeof(record) + items.size() * sizeof(items[0]));
	memcpy(native.data(), &record, sizeof(record));
	memcpy(native.data() + sizeof(record), items.data(), items.size() * sizeof(items[0]));
	return native;
}
static std::vector<unsigned char>
encoded_floor(const std::vector<world_recovery_item_snapshot> &items, int room = 100)
{
	const auto native = tree(items, room);
	std::vector<unsigned char> bytes;
	assert(world_recovery_encode_floor_object(native.data(), native.size(), &bytes));
	return bytes;
}
static redis_world_boot_snapshot
snapshot(const std::vector<std::vector<world_recovery_item_snapshot>> &trees, bool mob = true)
{
	redis_world_boot_snapshot result;
	result.sequence = UINT64_MAX;
	result.generation.resize(WORLD_RECOVERY_WIRE_HEADER_BYTES);
	auto append = [&](world_recovery_record_type type, const std::vector<unsigned char> &native)
	{
		std::vector<unsigned char> wire(WORLD_RECOVERY_MAX_RECORD_BYTES);
		size_t size = 0;
		assert(world_recovery_encode_record(type, native.data(), native.size(), wire.data(),
						    wire.size(), &size));
		const size_t offset = result.generation.size();
		result.generation.resize(offset + WORLD_RECOVERY_WIRE_RECORD_HEADER_BYTES + size);
		assert(world_recovery_encode_record_header(
			type, size, result.generation.data() + offset,
			WORLD_RECOVERY_WIRE_RECORD_HEADER_BYTES));
		memcpy(result.generation.data() + offset + WORLD_RECOVERY_WIRE_RECORD_HEADER_BYTES,
		       wire.data(), size);
	};
	if (mob)
	{
		copyover_mob entry = {};
		entry.vnum = 2000;
		entry.idnum = 42;
		entry.room = 200;
		entry.birthplace = 100;
		entry.max_hit = 50;
		entry.shopkeeper_shop_id = 7;
		std::vector<unsigned char> native(sizeof(entry));
		memcpy(native.data(), &entry, sizeof(entry));
		append(world_recovery_record_type::mob, native);
	}
	for (const auto &items : trees)
		append(world_recovery_record_type::object, tree(items));
	world_recovery_header header = {};
	memcpy(header.magic, "WR12", 4);
	header.schema_version = WORLD_RECOVERY_SCHEMA_VERSION;
	header.header_size = WORLD_RECOVERY_WIRE_HEADER_BYTES;
	header.timestamp = time(nullptr);
	header.sequence = result.sequence;
	header.complete = 1;
	header.mob_count = mob;
	header.object_count = trees.size();
	header.payload_size = result.generation.size() - WORLD_RECOVERY_WIRE_HEADER_BYTES;
	header.checksum = crc32(0, result.generation.data() + WORLD_RECOVERY_WIRE_HEADER_BYTES,
				header.payload_size);
	assert(world_recovery_encode_header(&header, result.generation.data(),
					    result.generation.size()));
	return result;
}
int main()
{
	auto root = item(1000, 1000, 0, 901), child = item(1001, 1000, 1000),
	     ordinary = item(1002, 1000, 1001);
	root.extra_flags = ordinary.extra_flags = 0;
	child.flags = WORLD_RECOVERY_ITEM_AUTHORITY_REQUIRED;
	auto data = snapshot({ { root, child, ordinary }, { item(UINT64_MAX, UINT64_MAX, 0) } });
	data.floor_records = { encoded_floor({ root }, 200),
			       encoded_floor({ item(2000, 2000, 0), item(2001, 2000, 2000) }) };
	artifact_recovery_population population;
	world_recovery_header verified = {};
	assert(world_recovery_validate(data.generation.data(), data.generation.size(), INT_MAX,
				       data.sequence, &verified));
	assert(!artifact_population_read_recovery(data, &population));
	assert(population.items.size() == 7 && population.mobs.size() == 1 &&
	       !population.restore_conflict);
	assert(population.items[0].extra_flags_present && !population.items[0].extra_flags);
	const auto &descendant = population.items[1];
	assert(!descendant.custody_examined);
	assert(descendant.item_uid == 1001 && descendant.parent_row_id == 1 &&
	       descendant.parent_item_uid == 1000 && descendant.payload_root_item_uid == 1000 &&
	       descendant.vnum == 900 && descendant.custody_required && !descendant.custody_found &&
	       descendant.payload_owner.type == item_owner_type::room &&
	       descendant.payload_owner.id == 100 && descendant.owner_context == UINT64_MAX);
	assert(population.items[2].parent_row_id == 2 && population.items[2].extra_flags_present &&
	       !population.items[2].extra_flags);
	assert(population.items[3].item_uid == UINT64_MAX);
	assert(population.items[4].domain == artifact_payload_domain::redis_floor &&
	       population.items[4].role == artifact_payload_role::history &&
	       population.items[4].owner_reference == 200);
	assert(population.items[5].role == artifact_payload_role::stored &&
	       population.items[6].parent_row_id == 6);
	const auto &mob = population.mobs[0];
	assert(mob.vnum == 2000 && mob.instance_id == 42 && mob.room_vnum == 200 &&
	       mob.birthplace == 100 && mob.shopkeeper_shop_id == 7);
	data.floor_records.push_back(encoded_floor({ root, item(3000, 1000, 1000) }));
	assert(!artifact_population_read_recovery(data, &population) &&
	       population.items.size() == 9 && population.restore_conflict &&
	       population.items[7].source_quarantined && population.items[8].source_quarantined);
	auto duplicate = snapshot({ { root }, { root } }, false);
	assert(!artifact_population_read_recovery(duplicate, &population) &&
	       population.items.size() == 2 && population.restore_conflict &&
	       population.items[1].source_quarantined);
	const auto *retained = population.items.data();
	auto reject = [&](const redis_world_boot_snapshot &invalid, unsigned int error = EINVAL)
	{
		assert(artifact_population_read_recovery(invalid, &population) == error);
		assert(population.items.data() == retained && population.items.size() == 2 &&
		       population.restore_conflict);
	};
	auto invalid = data;
	invalid.sequence = 0;
	reject(invalid);
	invalid = data;
	invalid.sequence = 1;
	reject(invalid);
	invalid = data;
	invalid.generation.back() ^= 1;
	reject(invalid);
	invalid = data;
	invalid.floor_records.back().pop_back();
	reject(invalid);
	invalid = data;
	invalid.floor_records.back()[0] = 'X';
	reject(invalid);
	invalid = data;
	invalid.floor_records.resize(WORLD_RECOVERY_MAX_FLOOR_RECORDS + 1);
	reject(invalid, E2BIG);
	invalid = data;
	invalid.floor_records = { std::vector<unsigned char>(WORLD_RECOVERY_MAX_FLOOR_BYTES + 1) };
	reject(invalid, E2BIG);
	for (int failure = 0; failure < 7; ++failure)
	{
		auto changed = child;
		if (failure == 0)
			changed.parent_item_uid = 99999;
		if (failure == 1)
			changed.root_item_uid = 99999;
		if (failure == 2)
			changed.item_uid = root.item_uid;
		if (failure == 3)
			changed.flags = ~WORLD_RECOVERY_ITEM_AUTHORITY_REQUIRED;
		if (failure == 4)
			changed.material = SCHAR_MAX + 1;
		if (failure == 5)
			changed.affect_locations[0] = -1;
		if (failure == 6)
			memset(changed.name, 'x', sizeof(changed.name));
		// Both the generation and the floor path use the same actual validator.
		reject(snapshot({ { root, changed } }, false));
		invalid = snapshot({ { root } }, false);
		invalid.floor_records = { encoded_floor({ root, changed }) };
		reject(invalid);
	}
	world_recovery_object_record record_out = { -7, 99 };
	std::vector<world_recovery_item_snapshot> items_out = { item(88, 88, 0) };
	auto native = tree({ root, child });
	assert(!world_recovery_read_object_record(native.data(), native.size() - 1, &record_out,
						  &items_out));
	assert(record_out.room_vnum == -7 && record_out.item_count == 99 &&
	       items_out[0].item_uid == 88);
	assert(!artifact_population_read_recovery({}, &population) && population.items.empty() &&
	       population.mobs.empty());
	assert(!template_reads && !extractions && !custody_reads);
	std::cout
		<< "pinned recovery projections retain nested identity, explicit flags, NPC hints and overlapping evidence; "
		   "malformed/bounded failures preserve prior output without materialization or custody reads\n";
}
