#include "persistence/copyover.c"
#include "guild/artifact_population_repository.h"

#include <cassert>
#include <climits>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>

static int replace_on_open = 0;
static unsigned file_opens = 0;
extern "C" int __real_open(const char *, int, ...);
extern "C" int __wrap_open(const char *path, int flags, ...)
{
	if (!strcmp(path, "copyover.dat") || !strcmp(path, "copyover.dat.recovering"))
	{
		++file_opens;
		if ((replace_on_open == 1 || replace_on_open == 2) && file_opens == 1)
		{
			assert(rename(path, "original.dat") == 0);
			if (replace_on_open == 1)
				assert(symlink("target.dat", path) == 0);
			else
				assert(rename("target.dat", path) == 0);
		}
		if (replace_on_open == 3 && file_opens == 2)
		{
			assert(rename(path, "original.dat") == 0);
			assert(rename("target.dat", path) == 0);
		}
	}
	return __real_open(path, flags);
}

static room_data rooms[1] = {};
static index_data objects[1] = {}, mobs[1] = {};
P_room world = rooms;
P_index obj_index = objects, mob_index = mobs;
extern const int top_of_world = 0;
static unsigned int template_reads = 0, custody_reads = 0, short_updates = 0;
P_obj read_object(int, int)
{
	++template_reads;
	return nullptr;
}
bool item_ownership_runtime_lookup(uint64_t, item_ownership_runtime_entry *)
{
	++custody_reads;
	return false;
}
void transport_capture(P_char, transport_snapshot *snapshot)
{
	*snapshot = {};
}
void updateShortAffects(P_char mob)
{
	++short_updates;
	if (mob->affected)
		mob->affected = mob->affected->next;
}

static std::vector<char> read_bytes(const std::string &path)
{
	std::ifstream input(path, std::ios::binary);
	return { std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>() };
}
static void write_bytes(const std::string &path, const std::vector<char> &bytes)
{
	std::ofstream output(path, std::ios::binary | std::ios::trunc);
	output.write(bytes.data(), bytes.size());
	assert(output.good());
}

static std::vector<char> descriptor_image(int version, const copyover_desc &desc)
{
	static_assert(offsetof(copyover_desc, gmcp_supports) == 660,
		      "versions 12-17 have a frozen 660-byte descriptor record");
	copyover_header header{};
	memcpy(header.magic, COPYOVER_MAGIC, 4);
	header.version = version;
	header.num_descriptors = 1;
	FILE *file = tmpfile();
	assert(file);
	assert(fwrite(&header, sizeof(header), 1, file) == 1);
	const int sockets[3] = { -1, -1, -1 };
	assert(fwrite(sockets, sizeof(sockets), 1, file) == 1);
	assert(fwrite(&desc, copyover_desc_bytes_for_version(version), 1, file) == 1);
	if (version >= 15)
	{
		telemetry_copyover_header telemetry{};
		memcpy(telemetry.magic, "TLMY", 4);
		telemetry.version = 1;
		telemetry.count = 1;
		telemetry_copyover_entry entry{};
		entry.fd = desc.fd;
		strcpy(entry.player_name, desc.player_name);
		assert(fwrite(&telemetry, sizeof(telemetry), 1, file) == 1);
		assert(fwrite(&entry, sizeof(entry), 1, file) == 1);
	}
	const auto size = ftell(file);
	assert(size > 0);
	rewind(file);
	std::vector<char> bytes(static_cast<size_t>(size));
	assert(fread(bytes.data(), bytes.size(), 1, file) == 1);
	fclose(file);
	return bytes;
}

static std::vector<char> image(int version = COPYOVER_VERSION, int affect_count = 80,
			       int inventory_count = 300)
{
	copyover_header header = {};
	memcpy(header.magic, COPYOVER_MAGIC, 4);
	header.version = version;
	header.timestamp = time(nullptr);
	header.num_mobs = 1;
	header.num_objects = version >= 17 ? inventory_count + 2 : 1;
	FILE *file = tmpfile();
	assert(file);
	assert(fwrite(&header, sizeof(header), 1, file) == 1);
	const int sockets[3] = { -1, -1, -1 };
	assert(fwrite(sockets, sizeof(sockets), 1, file) == 1);
	if (version >= 15)
	{
		telemetry_copyover_header telemetry = {};
		memcpy(telemetry.magic, "TLMY", 4);
		telemetry.version = 1;
		assert(fwrite(&telemetry, sizeof(telemetry), 1, file) == 1);
	}
	char_data mob = {};
	npc_only_data npc = {};
	mob.only.npc = &npc;
	mob.specials.act = ACT_ISNPC;
	mob.in_room = 0;
	npc.R_num = 0;
	npc.idnum = 42;
	npc.shopkeeper_shop_id = 7;
	mob.player.birthplace = 100;
	GET_MAX_HIT(&mob) = GET_HIT(&mob) = 100;
	std::vector<obj_data> inventory(inventory_count);
	for (size_t index = 0; index < inventory.size(); ++index)
	{
		inventory[index].R_num = 0;
		inventory[index].obj_uid = 10000 + index;
		inventory[index].next_content =
			index + 1 < inventory.size() ? &inventory[index + 1] : nullptr;
	}
	obj_data worn = {};
	worn.R_num = 0;
	worn.obj_uid = 9999;
	mob.carrying = inventory.data();
	mob.equipment[3] = &worn;
	std::vector<affected_type> affects(affect_count);
	for (size_t index = 0; index < affects.size(); ++index)
	{
		affects[index].duration = 30;
		affects[index].next = index + 1 < affects.size() ? &affects[index + 1] : nullptr;
	}
	mob.affected = affects.data();
	if (version >= 17)
	{
		const unsigned before = short_updates;
		assert(write_mob_entry(file, &mob) && write_mob_affects(file, &mob) &&
		       write_mob_inventory(file, &mob));
		assert(short_updates == before + 1);
	}
	else
	{
		copyover_mob entry = {};
		entry.vnum = 2000;
		entry.room = 100;
		entry.idnum = 42;
		entry.birthplace = 100;
		entry.num_affects = affect_count;
		entry.num_carrying = inventory_count;
		entry.shopkeeper_shop_id = 7;
		assert(fwrite(&entry, copyover_mob_bytes_for_version(version), 1, file) == 1);
		std::vector<copyover_affect> saved_affects(affect_count);
		assert(fwrite(saved_affects.data(), saved_affects.size() * sizeof(saved_affects[0]),
			      1, file) == 1);
		std::vector<copyover_carried_item> saved_inventory(inventory_count);
		for (auto &item : saved_inventory)
		{
			item.obj_uid = UINT64_MAX;
			item.vnum = 900;
		}
		assert(fwrite(saved_inventory.data(),
			      saved_inventory.size() * sizeof(saved_inventory[0]), 1, file) == 1);
	}
	if (version >= 14)
	{
		std::string extension;
		assert(generated_npc_extension_encode(2000, "", &extension));
		assert(fwrite(extension.data(), extension.size(), 1, file) == 1);
	}
	if (version >= 17)
	{
		std::array<uint64_t, 43> equipment = {};
		equipment[3] = 9999;
		assert(fwrite(equipment.data(), sizeof(equipment), 1, file) == 1);
		for (uint64_t uid = 9999; uid < 10000 + static_cast<uint64_t>(inventory_count);
		     ++uid)
		{
			world_recovery_object_record record = { 100, 1 };
			world_recovery_item_snapshot item = {};
			item.item_uid = item.root_item_uid = uid;
			item.vnum = 900;
			const uint32_t bytes = sizeof(record) + sizeof(item);
			assert(fwrite(&bytes, sizeof(bytes), 1, file) == 1 &&
			       fwrite(&record, sizeof(record), 1, file) == 1 &&
			       fwrite(&item, sizeof(item), 1, file) == 1);
		}
	}

	world_recovery_object_record root = { 100, 2 };
	world_recovery_item_snapshot nodes[2] = {};
	nodes[0].item_uid = nodes[0].root_item_uid = 7777;
	nodes[0].vnum = 901;
	nodes[1].item_uid = 8888;
	nodes[1].root_item_uid = 7777;
	nodes[1].parent_item_uid = 7777;
	nodes[1].vnum = 900;
	nodes[1].extra_flags = 1U << 28;
	nodes[1].flags = WORLD_RECOVERY_ITEM_AUTHORITY_REQUIRED;
	item_ownership_runtime_entry custody = {};
	custody.item_uid = custody.root_item_uid = 8888;
	custody.vnum = 900;
	custody.owner = { item_owner_type::corpse, 77, 12 };
	custody.item_revision = 9;
	custody.owner_revision = 31;
	custody.state = item_custody_state::active;
	const uint32_t bytes = sizeof(root) + sizeof(nodes) + sizeof(custody);
	assert(fwrite(&bytes, sizeof(bytes), 1, file) == 1 &&
	       fwrite(&root, sizeof(root), 1, file) == 1 &&
	       fwrite(nodes, sizeof(nodes), 1, file) == 1 &&
	       fwrite(&custody, sizeof(custody), 1, file) == 1);
	assert(fflush(file) == 0);
	const long size = ftell(file);
	assert(size > 0 && fseek(file, 0, SEEK_SET) == 0);
	std::vector<char> result(size);
	assert(fread(result.data(), result.size(), 1, file) == 1 && fclose(file) == 0);
	return result;
}

int main(int argc, char **argv)
{
	assert(argc == 2);
	rooms[0].number = 100;
	objects[0].virtual_number = 900;
	mobs[0].virtual_number = 2000;
	const std::string path = "copyover.dat", claimed = path + ".recovering";
	const auto valid = image();

	if (std::string(argv[1]) == "protocol")
	{
		copyover_desc desc{};
		desc.fd = 17;
		strcpy(desc.player_name, "Tester");
		desc.gmcp_enabled = 1;
		desc.gmcp_supports = 7;
		desc.gmcp_interests = 2;
		desc.gmcp_session_generation = 9007199254740993ULL;
		desc.gmcp_session_body_revision = 4;
		desc.gmcp_command_receipts = 1;
		desc.gmcp_input_sequence = 12345678901234567890ULL;
		strcpy(desc.gmcp_session_context, "0123456789abcdef0123456789abcdef");
		copyover_boot_snapshot snapshot;
		for (int version = 12; version <= COPYOVER_VERSION; ++version)
		{
			const auto bytes = descriptor_image(version, desc);
			write_bytes(path, bytes);
			assert(copyover_read_file(path, &snapshot) == copyover_boot_result::ready);
			copyover_desc decoded{};
			memcpy(&decoded,
			       snapshot.bytes.data() + sizeof(copyover_header) + 3 * sizeof(int),
			       copyover_desc_bytes_for_version(version));
			assert(decoded.fd == 17 && decoded.gmcp_enabled == 1 &&
			       !strcmp(decoded.player_name, "Tester"));
			if (version < 18)
				assert(!decoded.gmcp_supports && !decoded.gmcp_session_context[0] &&
				       !decoded.gmcp_session_generation);
			else
			{
				assert(decoded.gmcp_supports == 7 && decoded.gmcp_interests == 2);
				assert(decoded.gmcp_session_generation == 9007199254740993ULL &&
				       decoded.gmcp_session_body_revision == 4);
				assert(decoded.gmcp_input_sequence == 12345678901234567890ULL &&
				       decoded.gmcp_command_receipts == 1);
				assert(!strcmp(decoded.gmcp_session_context,
					       desc.gmcp_session_context));
			}
		}
		auto invalid = desc;
		invalid.gmcp_command_receipts = 2;
		write_bytes(path, descriptor_image(COPYOVER_VERSION, invalid));
		assert(copyover_read_file(path, &snapshot) == copyover_boot_result::failed);
		invalid = desc;
		memset(invalid.gmcp_session_context, 'a', sizeof(invalid.gmcp_session_context));
		write_bytes(path, descriptor_image(COPYOVER_VERSION, invalid));
		assert(copyover_read_file(path, &snapshot) == copyover_boot_result::failed);
		invalid = desc;
		invalid.gmcp_session_context[10] = 'z';
		write_bytes(path, descriptor_image(COPYOVER_VERSION, invalid));
		assert(copyover_read_file(path, &snapshot) == copyover_boot_result::failed);
		std::cout << "copyover descriptor protocol versions 12-18 passed\n";
		return 0;
	}
	if (std::string(argv[1]) == "formats")
	{
		copyover_boot_snapshot snapshot;
		for (int version = 12; version <= COPYOVER_VERSION; ++version)
		{
			const auto bytes = image(version);
			write_bytes(path, bytes);
			assert(copyover_read_file(path, &snapshot) == copyover_boot_result::ready);
			assert(snapshot.header.version == version && snapshot.mobs.size() == 1 &&
			       snapshot.objects.size() == (version >= 17 ? 302 : 1));
			copyover_mob_record mob;
			size_t used = 0;
			const auto span = snapshot.mobs[0];
			assert(copyover_decode_mob(snapshot.bytes.data() + span.offset, span.size,
						   version, &mob, &used) &&
			       used == span.size);
			assert(mob.affects.size() == (version >= 17 ? 79 : 80) &&
			       mob.inventory.size() == 300);
			assert(mob.mob.shopkeeper_shop_id == (version < 16 ? -1 : 7));
			artifact_recovery_population population;
			assert(!artifact_population_read_copyover(snapshot, &population));
			assert(population.mobs.size() == 1 &&
			       population.items.size() == (version >= 17 ? 303 : 302));
			for (const auto &row : population.items)
				if (row.domain == artifact_payload_domain::copyover_reconstruction)
					assert(!row.item_uid &&
					       row.role == artifact_payload_role::reconstruction &&
					       !row.custody_examined);
			const auto &child = population.items.back();
			assert(child.item_uid == 8888 && child.payload_root_item_uid == 7777 &&
			       child.parent_item_uid == 7777 && child.custody_examined &&
			       child.custody_found && child.custody_owner_revision_found &&
			       child.custody.item_revision == 9 &&
			       child.payload_owner.type == item_owner_type::corpse &&
			       child.payload_owner.id == 77);
			if (version >= 17)
			{
				copyover_carried_item expected;
				memset(&expected, 0, sizeof(expected));
				expected.vnum = 900;
				for (size_t index = 0; index < mob.inventory.size(); ++index)
				{
					expected.obj_uid = 10000 + index;
					assert(!memcmp(&mob.inventory[index], &expected,
						       sizeof(expected)));
				}
			}
		}
		const auto *retained = snapshot.bytes.data();
		for (size_t size :
		     { size_t{ 0 }, sizeof(copyover_header) - 1, snapshot.mobs[0].offset + 1,
		       snapshot.objects[0].offset - 1, valid.size() - 1 })
		{
			write_bytes(path, { valid.begin(), valid.begin() + size });
			assert(copyover_read_file(path, &snapshot) ==
				       copyover_boot_result::failed &&
			       snapshot.bytes.data() == retained);
		}
		for (uint64_t invalid_uid :
		     { uint64_t{ 0 }, uint64_t{ 10000 }, uint64_t{ 999999 } })
		{
			auto invalid = valid;
			const size_t equipment_offset = snapshot.mobs[0].offset +
							snapshot.mobs[0].size -
							sizeof(std::array<uint64_t, 43>);
			memcpy(invalid.data() + equipment_offset + 3 * sizeof(uint64_t),
			       &invalid_uid, sizeof(invalid_uid));
			write_bytes(path, invalid);
			assert(copyover_read_file(path, &snapshot) ==
				       copyover_boot_result::failed &&
			       snapshot.bytes.data() == retained);
		}

		auto malformed = valid;
		copyover_header header = {};
		memcpy(&header, malformed.data(), sizeof(header));
		header.num_mobs = -1;
		memcpy(malformed.data(), &header, sizeof(header));
		write_bytes(path, malformed);
		assert(copyover_read_file(path, &snapshot) == copyover_boot_result::failed &&
		       snapshot.bytes.data() == retained);
		malformed = valid;
		const int excessive = INT_MAX;
		memcpy(malformed.data() + snapshot.mobs[0].offset +
			       offsetof(copyover_mob, num_carrying),
		       &excessive, sizeof(excessive));
		write_bytes(path, malformed);
		assert(copyover_read_file(path, &snapshot) == copyover_boot_result::failed &&
		       snapshot.bytes.data() == retained);
		malformed = valid;
		malformed.push_back('x');
		write_bytes(path, malformed);
		assert(copyover_read_file(path, &snapshot) == copyover_boot_result::failed);
		malformed = valid;
		memcpy(&header, malformed.data(), sizeof(header));
		header.num_objects += 1;
		memcpy(malformed.data(), &header, sizeof(header));
		const auto object = snapshot.objects[0];
		const uint32_t frame_size = object.size;
		const auto *prefix = reinterpret_cast<const char *>(&frame_size);
		malformed.insert(malformed.end(), prefix, prefix + sizeof(frame_size));
		malformed.insert(malformed.end(), valid.begin() + object.offset,
				 valid.begin() + object.offset + object.size);
		write_bytes(path, malformed);
		assert(copyover_read_file(path, &snapshot) == copyover_boot_result::failed &&
		       snapshot.bytes.data() == retained);
		malformed = valid;
		const auto &custodied = snapshot.objects.back();
		const auto state_offset = custodied.offset + custodied.size -
					  sizeof(item_ownership_runtime_entry) +
					  offsetof(item_ownership_runtime_entry, state);
		malformed[state_offset] = static_cast<char>(item_custody_state::destroyed);
		write_bytes(path, malformed);
		assert(copyover_read_file(path, &snapshot) == copyover_boot_result::failed);
		FILE *sparse = fopen(path.c_str(), "wb");
		assert(sparse);
		assert(ftruncate(fileno(sparse), WORLD_RECOVERY_MAX_BYTES + 1) == 0 &&
		       fclose(sparse) == 0);
		assert(copyover_read_file(path, &snapshot) == copyover_boot_result::failed);
		assert(copyover_read_file("missing/parent/state", &snapshot) ==
		       copyover_boot_result::failed);
		assert(unlink(path.c_str()) == 0 && mkfifo(path.c_str(), 0600) == 0);
		assert(copyover_read_file(path, &snapshot) == copyover_boot_result::failed);
		assert(snapshot.bytes.data() == retained);
	}
	else if (std::string(argv[1]) == "limits")
	{
		copyover_boot_snapshot snapshot;
		for (const bool affects : { true, false })
		{
			const int bound = WORLD_RECOVERY_MAX_ITEM_TREE;
			write_bytes(path, image(12, affects ? bound : 1, affects ? 1 : bound));
			assert(copyover_read_file(path, &snapshot) == copyover_boot_result::ready);
			const auto *retained = snapshot.bytes.data();
			write_bytes(path,
				    image(12, affects ? bound + 1 : 1, affects ? 1 : bound + 1));
			assert(copyover_read_file(path, &snapshot) ==
				       copyover_boot_result::failed &&
			       snapshot.bytes.data() == retained);
		}
	}
	else if (std::string(argv[1]) == "race-symlink" || std::string(argv[1]) == "race-inode" ||
		 std::string(argv[1]) == "race-claimed-inode")
	{
		write_bytes(path, valid);
		write_bytes("target.dat", valid);
		replace_on_open = std::string(argv[1]) == "race-symlink" ? 1 :
				  std::string(argv[1]) == "race-inode"	 ? 2 :
									   3;
		assert(copyover_prepare_boot() == copyover_boot_result::failed &&
		       !copyover_boot_evidence());
		assert(read_bytes("original.dat") == valid);
		if (replace_on_open == 1)
			assert(read_bytes("target.dat") == valid);
		if (replace_on_open < 3)
			assert(access(claimed.c_str(), F_OK) != 0);
	}
	else if (std::string(argv[1]) == "pwipe")
	{
		write_bytes(path, valid);
		write_bytes(claimed, valid);
		copyover_boot_snapshot snapshot;
		assert(copyover_read_file(path, &snapshot) == copyover_boot_result::ready);
		artifact_recovery_population old_world;
		assert(!artifact_population_read_copyover(snapshot, &old_world) &&
		       !old_world.items.empty());
		assert(system("./Players/wipers/wipe_it_all --check >/dev/null") == 0);
		assert(read_bytes(path) == valid && read_bytes(claimed) == valid);
		assert(system("./Players/wipers/wipe_it_all >/dev/null") == 0);
		assert(copyover_read_file(path, &snapshot) == copyover_boot_result::absent);
		assert(copyover_read_file(claimed, &snapshot) == copyover_boot_result::absent);
		assert(copyover_prepare_boot() == copyover_boot_result::absent);
		unsigned archived = 0;
		for (const auto &entry : std::filesystem::directory_iterator("Players/Backup"))
			if (entry.path().filename().string().starts_with("pwipe-copyover."))
			{
				assert(read_bytes((entry.path() / "publication").string()) ==
				       valid);
				assert(read_bytes((entry.path() / "recovering").string()) == valid);
				++archived;
			}
		assert(archived == 1);
	}
	else if (std::string(argv[1]) == "pin")
	{
		write_bytes(path, valid);
		assert(copyover_prepare_boot() == copyover_boot_result::ready);
		const auto *snapshot = copyover_boot_evidence();
		assert(snapshot && snapshot->bytes == valid && access(path.c_str(), F_OK) != 0 &&
		       access(claimed.c_str(), F_OK) == 0);
		write_bytes(path, { 'n', 'e', 'w', 'e', 'r' });
		assert(copyover_prepare_boot() == copyover_boot_result::ready &&
		       copyover_boot_evidence() == snapshot && snapshot->bytes == valid);
		assert(copyover_has_durable_shopkeepers());
	}
	else if (std::string(argv[1]) == "failed")
	{
		write_bytes(path, { 'b', 'a', 'd' });
		assert(copyover_prepare_boot() == copyover_boot_result::failed &&
		       !copyover_boot_evidence());
		assert(read_bytes(path) == std::vector<char>({ 'b', 'a', 'd' }) &&
		       access(claimed.c_str(), F_OK) != 0);
		write_bytes(path, valid);
		assert(copyover_prepare_boot() == copyover_boot_result::failed &&
		       read_bytes(path) == valid);
		assert(!copyover_has_durable_shopkeepers());
	}
	else if (std::string(argv[1]) == "two")
	{
		write_bytes(path, valid);
		write_bytes(claimed, valid);
		assert(copyover_prepare_boot() == copyover_boot_result::failed &&
		       !copyover_boot_evidence());
		assert(read_bytes(path) == valid && read_bytes(claimed) == valid);
	}
	else if (std::string(argv[1]) == "nonregular")
	{
		assert(mkdir(path.c_str(), 0700) == 0);
		assert(copyover_prepare_boot() == copyover_boot_result::failed);
		struct stat original = {};
		assert(lstat(path.c_str(), &original) == 0 && S_ISDIR(original.st_mode));
		assert(access(claimed.c_str(), F_OK) != 0);
	}
	else if (std::string(argv[1]) == "symlink")
	{
		write_bytes("target.dat", valid);
		assert(symlink("target.dat", path.c_str()) == 0);
		assert(copyover_prepare_boot() == copyover_boot_result::failed);
		struct stat original = {};
		assert(lstat(path.c_str(), &original) == 0 && S_ISLNK(original.st_mode));
		assert(read_bytes("target.dat") == valid && access(claimed.c_str(), F_OK) != 0);
	}
	else if (std::string(argv[1]) == "absent")
	{
		assert(copyover_prepare_boot() == copyover_boot_result::absent &&
		       !copyover_boot_evidence());
		write_bytes(path, valid);
		assert(copyover_prepare_boot() == copyover_boot_result::absent);
		assert(!copyover_has_durable_shopkeepers());
	}
	else
		assert(false);
	assert(!template_reads && !custody_reads);
	std::cout << "copyover evidence " << argv[1]
		  << " passed without materialization or custody lookup\n";
}
