#include "economy/divine_trade_repository.h"
#include "player/player_snapshot_codec.h"
#include <openssl/sha.h>
#include "flatfile/flatfile_ship_repository.h"
#include "flatfile/flatfile_cargo_repository.h"
#include "ships/ships.h"
#include "flatfile/flatfile_player_repository.h"
#include "flatfile/flatfile_boon_repository.h"
#include "flatfile/flatfile_identity_repository.h"
#include "flatfile/flatfile_item_repository.h"
#include "flatfile/flatfile_artifact_repository.h"
#include "flatfile/flatfile_player_domain_repository.h"
#include "flatfile/flatfile_world_item_repository.h"
#include "persistence/persistence_observability.h"
#include "player/player_snapshot_codec.h"
#include "classes/necromancy.h"
#include "core/defines.h"
#include "magic/spells.h"
#include "world/vnum.obj.h"
#include "combat/combat_outcome_command.h"
#include "world/zone_touch_command.h"
#include <algorithm>
#include <cerrno>
#include <cstring>
#include <ctime>
#include <openssl/sha.h>

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <sys/wait.h>
#include <unistd.h>

namespace fs = std::filesystem;

bool player_load_request_valid(const player_load_request &request, uint64_t now)
{
	const bool pid_identity = request.pid > 0 &&
				  request.account_name.size() <= PLAYER_LOAD_ACCOUNT_MAX;
	const bool name_identity = request.pid == 0 && !request.player_name.empty() &&
				   request.player_name.size() <= PLAYER_LOAD_NAME_MAX;
	return request.schema_version == PLAYER_LOAD_SCHEMA_VERSION && request.request_id > 0 &&
	       (pid_identity || name_identity) && request.deadline_usec > now &&
	       request.deadline_usec - now <= PLAYER_LOAD_TIMEOUT_USEC &&
	       (!request.include_pets || request.include_items);
}

static void require(bool condition, const std::string &message)
{
	if (!condition)
	{
		std::cerr << message << '\n';
		exit(1);
	}
}

static player_snapshot make_full(player_revision_t revision)
{
	player_snapshot snapshot = {};
	snapshot.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
	snapshot.pid = 42;
	snapshot.revision = revision;
	snapshot.components = PLAYER_CHECKPOINT_COMPONENT_ALL;
	snapshot.save_intent = 4;
	snapshot.room_vnum = 1201;
	snapshot.encoded_size_bound = 8192;
	snapshot.status_integers.push_back({ player_status_field::level, 50, 0, false });
	snapshot.status_integers.push_back({ player_status_field::racewar, 0, 0, false });
	snapshot.status_integers.push_back({ player_status_field::copper, 11, 0, false });
	snapshot.status_integers.push_back({ player_status_field::silver, 12, 0, false });
	snapshot.status_integers.push_back({ player_status_field::gold, 13, 0, false });
	snapshot.status_integers.push_back({ player_status_field::platinum, 14, 0, false });
	snapshot.status_integers.push_back({ player_status_field::epics, 15, 0, false });
	snapshot.status_integers.push_back({ player_status_field::frags, 16, 0, false });
	snapshot.status_integers.push_back({ player_status_field::old_frags, 17, 0, false });
	for (int index = 0; index < 10; ++index)
		snapshot.status_integers.push_back(
			{ static_cast<player_status_field>(
				  static_cast<unsigned int>(player_status_field::base_strength) +
				  index),
			  50 + index, 0, false });
	snapshot.status_integers.push_back(
		{ player_status_field::learned_flight_stops, 0, (uint64_t{ 1 } << 26) | 1, true });
	snapshot.status_strings.push_back({ player_status_string_field::name, "Player" });
	snapshot.conditions = { 1, 2, 3, 4, 5 };
	snapshot.quest_values[3] = 77;
	snapshot.languages.push_back({ 1, 90, 0 });
	snapshot.introductions.push_back({ 2, 44, 12345 });
	snapshot.timers.push_back({ 3, 67890, 0 });
	snapshot.undead_slots.push_back({ 4, 2, 0 });
	snapshot.forged_items.push_back({ 5, 6001, 0 });
	snapshot.granted_commands.push_back(42);
	snapshot.skills.push_back({ 9, 80, 1 });
	player_affect_snapshot affect = {};
	affect.type = 11;
	affect.duration = 12;
	affect.bitvectors[2] = 99;
	affect.wear_off_character = "gone";
	snapshot.affects.push_back(affect);
	player_item_snapshot parent = {};
	parent.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	parent.object_uid = 100;
	parent.vnum = 500;
	parent.string_mask = 1;
	parent.name = "container";
	parent.values[0] = 8;
	parent.dynamic_affects.push_back({ 1, 2, 3 });
	player_item_extra_description_snapshot description = {};
	description.keyword = "SPELLBOOK";
	description.spellbook = true;
	description.spell_ids = { 7, 12 };
	parent.extra_descriptions.push_back(description);
	snapshot.items.push_back(parent);
	player_item_snapshot child = {};
	child.parent_index = 0;
	child.object_uid = 101;
	child.vnum = 501;
	snapshot.items.push_back(child);
	player_pet_snapshot pet = {};
	pet.mob_vnum = 700;
	pet.room_vnum = 1201;
	pet.items.push_back(child);
	pet.items[0].parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	pet.items[0].object_uid = 102;
	snapshot.pets.push_back(pet);
	snapshot.shapes.push_back({ 800, 2, 100, 200 });
	snapshot.trophies.push_back({ 12, 300 });
	snapshot.recipes_are_external = true;
	snapshot.output_preferences = "v1;m=1;12=27";
	snapshot.status_strings.push_back(
		{ player_status_string_field::last_read_news_hash, std::string(64, 'a') });
	return snapshot;
}

/** Create a minimal status-only snapshot with the revision, level, and room under test. */
static player_snapshot make_status(player_revision_t revision, int level, int room)
{
	player_snapshot snapshot = {};
	snapshot.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
	snapshot.pid = 42;
	snapshot.revision = revision;
	snapshot.components = PLAYER_COMPONENT_STATUS;
	snapshot.save_intent = 1;
	snapshot.room_vnum = room;
	snapshot.encoded_size_bound = 1024;
	snapshot.status_integers.push_back({ player_status_field::level, level, 0, false });
	snapshot.status_strings.push_back({ player_status_string_field::name, "Player" });
	snapshot.recipes_are_external = true;
	snapshot.status_strings.push_back(
		{ player_status_string_field::last_read_news_hash, std::string(64, 'b') });
	return snapshot;
}

// Read existing synthetic authority without recovery or mutation. Used by the
// full-world journey to compare item identities across real server restarts.
static void inspect_authority(const std::string &root, int32_t pid)
{
	std::string error;
	player_snapshot snapshot;
	require(flatfile_player_snapshot_load(root, pid, &snapshot, &error) ==
			flatfile_player_load_result::ok,
		"inspect player snapshot: " + error);
	flatfile_identity_record identity;
	require(flatfile_identity_lookup_pid(root, pid, &identity, &error) ==
			flatfile_identity_result::ok,
		"inspect identity: " + error);
	flatfile_player_domain_record domains;
	require(flatfile_player_domain_load(root, pid, identity.account, identity.racewar, &domains,
					    &error) == flatfile_player_domain_result::ok,
		"inspect wallet: " + error);
	flatfile_authority_lock lock;
	require(lock.acquire(root, &error), "inspect authority lock: " + error);
	std::cout << "{\"revision\":" << snapshot.revision << ",\"intent\":" << snapshot.save_intent
		  << ",\"room\":" << snapshot.room_vnum;
	for (const auto &entry : snapshot.status_strings)
		if (entry.field == player_status_string_field::last_read_news_hash)
		{
			require(entry.value.empty() ||
					(entry.value.size() == 64 &&
					 std::all_of(entry.value.begin(), entry.value.end(),
						     [](unsigned char c) {
							     return (c >= '0' && c <= '9') ||
								    (c >= 'a' && c <= 'f');
						     })),
				"invalid acknowledgement in inspection fixture");
			std::cout << ",\"last_read_news_hash\":\"" << entry.value << '"';
		}
	std::cout << ",\"base_stats\":[";
	for (size_t i = 0; i < domains.domains.base_stats.size(); ++i)
	{
		if (i)
			std::cout << ',';
		std::cout << domains.domains.base_stats[i];
	}
	std::cout << ']';
	std::cout << ",\"snapshot_uids\":[";
	for (size_t i = 0; i < snapshot.items.size(); ++i)
	{
		if (i)
			std::cout << ',';
		std::cout << snapshot.items[i].object_uid;
	}
	std::cout << "],\"wallet\":[";
	for (size_t i = 0; i < 4; ++i)
	{
		if (i)
			std::cout << ',';
		std::cout << domains.domains.wallet[i];
	}
	std::cout << "],\"wallet_revision\":" << domains.domains.wallet_revision;
	std::cout << ",\"bank\":[";
	for (size_t i = 0; i < 4; ++i)
	{
		if (i)
			std::cout << ',';
		std::cout << domains.domains.bank[i];
	}
	std::cout << "],\"bank_revision\":" << domains.domains.bank_revision;
	for (const auto &field : snapshot.status_integers)
		if (field.field == player_status_field::wimpy)
			std::cout
				<< ",\"wimpy\":"
				<< (field.is_unsigned ? field.unsigned_value : field.signed_value);
	for (const auto &field : snapshot.status_integers)
	{
		const char *name =
			field.field == player_status_field::hometown   ? "hometown" :
			field.field == player_status_field::birthplace ? "birthplace" :
			field.field == player_status_field::original_birthplace ?
									 "original_birthplace" :
			field.field == player_status_field::race       ? "race" :
			field.field == player_status_field::deaths     ? "death_count" :
			field.field == player_status_field::experience ? "experience" :
			field.field == player_status_field::level      ? "level" :
			field.field == player_status_field::learned_flight_stops ?
								    "learned_flight_stops" :
								    nullptr;
		if (name)
			std::cout
				<< ",\"" << name << "\":"
				<< (field.is_unsigned ? field.unsigned_value : field.signed_value);
	}
	for (const auto &owner :
	     { item_owner_identity{ item_owner_type::player, static_cast<uint64_t>(pid), 0 },
	       item_owner_identity{ item_owner_type::room,
				    static_cast<uint64_t>(snapshot.room_vnum), 0 } })
	{
		uint64_t revision = 0;
		std::vector<flatfile_item_ownership_record> items;
		const auto result = flatfile_item_repository_load_owner_locked(
			root, lock, owner, &revision, &items, &error);
		require(result == flatfile_item_repository_result::ok ||
				result == flatfile_item_repository_result::not_found,
			"inspect item owner: " + error);
		std::cout << (owner.type == item_owner_type::player ? ",\"player_items\":[" :
								      ",\"room_items\":[");
		bool first = true;
		for (const auto &item : items)
		{
			if (!first)
				std::cout << ',';
			first = false;
			std::cout << "{\"uid\":" << item.item_uid << ",\"vnum\":" << item.vnum
				  << ",\"root\":" << item.root_item_uid
				  << ",\"parent\":" << item.parent_item_uid << '}';
		}
		std::cout << ']';
		std::cout
			<< (owner.type == item_owner_type::player ? ",\"player_owner_revision\":" :
								    ",\"room_owner_revision\":")
			<< revision;
	}
	std::cout << "}\n";
}

static void inspect_world_items(const std::string &root, int argc, char **argv)
{
	std::string error;
	std::vector<flatfile_corpse_record> corpses;
	std::vector<flatfile_saved_world_item_record> saved_items;
	require(flatfile_world_item_list(root, &corpses, &saved_items, &error) ==
			flatfile_world_item_result::ok,
		"inspect world items: " + error);
	std::cout << "{\"items\":[";
	bool first = true;
	for (const auto &corpse : corpses)
		for (const auto &item : corpse.items)
		{
			bool requested = false;
			for (int index = 3; index < argc; ++index)
				requested |= item.vnum == std::stoi(argv[index]);
			if (!requested)
				continue;
			if (!first)
				std::cout << ',';
			first = false;
			std::cout << "{\"uid\":" << item.object_uid << ",\"vnum\":" << item.vnum;
			for (const auto &description : item.extra_descriptions)
				if (description.keyword == "DURIS_TRAP_STATE_V1")
					std::cout << ",\"trap_state\":\"" << description.description
						  << '"';
			std::cout << '}';
		}
	std::cout << "]}\n";
}

static void source_id_gap_case(const fs::path &path)
{
	const std::string root = path.string();
	for (const auto &directory : { path, path / "players", path / "domains",
				       path / "identities", path / "identities/names" })
	{
		fs::create_directories(directory);
		fs::permissions(directory, fs::perms::owner_all, fs::perm_options::replace);
	}
	std::string error;
	int32_t allocated = 0;
	for (int i = 0; i < 42; ++i)
		require(flatfile_identity_allocate_pid(root, &allocated, &error) ==
				flatfile_identity_result::ok,
			"source-gap PID");
	require(flatfile_identity_claim(root, 42, "Player", "Account-One", &error) ==
			flatfile_identity_result::ok,
		"source-gap identity");
	auto original = make_full(1);
	for (auto &item : original.items)
		if (item.parent_index != PLAYER_SNAPSHOT_NO_PARENT)
			++item.parent_index;
	player_item_snapshot held = {};
	held.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	held.vnum = 900;
	original.items.insert(original.items.begin(), held);
	require(flatfile_player_snapshot_apply(root, original, &error).outcome ==
			player_save_apply_outcome::applied,
		"source-gap seed");
	player_load_request request = {};
	request.request_id = 1;
	request.pid = 42;
	request.account_name = "Account-One";
	request.deadline_usec = persistence_observability_now_usec() + PLAYER_LOAD_TIMEOUT_USEC;
	const auto loaded = flatfile_player_load_repository_execute(root, request);
	require(loaded.outcome == player_load_outcome::applied &&
			loaded.snapshot.items.size() == 2 &&
			loaded.item_identities[0].database_id == 2 &&
			loaded.item_identities[1].database_id == 3 &&
			loaded.item_sources[1].item_uid == loaded.item_identities[0].item_uid &&
			loaded.item_sources[2].item_uid == loaded.item_identities[1].item_uid &&
			loaded.item_sources[1].vnum == loaded.snapshot.items[0].vnum &&
			loaded.item_sources[1].extra_flags_present &&
			loaded.item_sources[1].quantity == 1 &&
			loaded.item_sources[1].custody_owner_revision_found,
		"filtered flat rows compacted original source IDs");
}

static void retained_roots_case(const fs::path &path, bool unknown_root)
{
	const std::string root = path.string();
	for (const auto &directory : { path, path / "players", path / "domains",
				       path / "identities", path / "identities/names" })
	{
		fs::create_directories(directory);
		fs::permissions(directory, fs::perms::owner_all, fs::perm_options::replace);
	}
	std::string error;
	int32_t allocated = 0;
	for (int i = 0; i < 42; ++i)
		require(flatfile_identity_allocate_pid(root, &allocated, &error) ==
				flatfile_identity_result::ok,
			"retention fixture identity allocation");
	require(flatfile_identity_claim(root, 42, "Player", "Account-One", &error) ==
			flatfile_identity_result::ok,
		"retention fixture identity");
	auto original = make_full(1);
	player_item_snapshot unknown = {};
	unknown.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	unknown.object_uid = unknown_root ? 0 : 500;
	unknown.vnum = 900;
	unknown.name = "retained legacy root";
	unknown.values[7] = 77;
	original.items.push_back(unknown);
	player_item_snapshot child = {};
	child.parent_index = 2;
	child.object_uid = unknown_root ? 150 : 0;
	child.vnum = 901;
	original.items.push_back(child);
	require(flatfile_player_snapshot_apply(root, original, &error).outcome ==
			player_save_apply_outcome::applied,
		"legacy flat fixture seed: " + error);
	// The valid UID inside the held graph now belongs to another player. A
	// later save must retain the payload without claiming that UID back.
	require(flatfile_identity_allocate_pid(root, &allocated, &error) ==
				flatfile_identity_result::ok &&
			allocated == 43 &&
			flatfile_identity_claim(root, 43, "Other", "Account-One", &error) ==
				flatfile_identity_result::ok,
		"retention counterparty identity");
	auto other = make_full(1);
	other.pid = 43;
	other.status_strings[0].value = "Other";
	other.items = { unknown_root ? child : unknown };
	other.items[0].parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	other.pets.clear();
	require(flatfile_player_snapshot_apply(root, other, &error).outcome ==
			player_save_apply_outcome::applied,
		"retention counterparty save: " + error);
	player_load_request request = {};
	request.request_id = 1;
	request.pid = 42;
	request.account_name = "Account-One";
	request.deadline_usec = persistence_observability_now_usec() + PLAYER_LOAD_TIMEOUT_USEC;
	const auto loaded = flatfile_player_load_repository_execute(root, request);
	require(loaded.outcome == player_load_outcome::applied && loaded.snapshot.items.size() == 2,
		"unidentified root and its descendants must be withheld together");
	const auto foreign_source = std::find_if(
		loaded.item_sources.begin(), loaded.item_sources.end(),
		[&](const auto &source) { return source.item_uid == other.items[0].object_uid; });
	require(foreign_source != loaded.item_sources.end() && foreign_source->custody_found &&
			!foreign_source->custody_owner_revision_found &&
			foreign_source->custody.owner_revision == 0,
		"foreign flat revision was asserted as authoritative zero");
	require(loaded.item_sources.size() == 4 && loaded.item_sources[0].custody_found &&
			loaded.item_sources[0].root_item_uid == 100 &&
			loaded.item_sources[0].custody.owner.id == 42 &&
			loaded.item_sources[0].custody.owner_revision ==
				loaded.item_owner_revision &&
			loaded.item_sources[0].custody.state == item_custody_state::active &&
			loaded.item_sources[1].root_item_uid == 100 &&
			loaded.item_sources[1].custody.parent_item_uid == 100 &&
			loaded.item_sources[0].bytes > 0,
		"flat source cut lost custody, original ancestry or byte bounds");
	require(loaded.item_sources[2].vnum == 900 && loaded.item_sources[2].quantity == 1 &&
			loaded.item_sources[2].extra_flags_present &&
			loaded.item_sources[2].extra_flags == unknown.extra_flags &&
			loaded.item_sources[3].vnum == 901,
		"flat inspection lost withheld raw source metadata");
	auto partial = loaded.snapshot;
	partial.revision = 2;
	partial.components = PLAYER_COMPONENT_LANGUAGES;
	partial.languages[0].value = 97;
	require(flatfile_player_snapshot_apply(root, partial, &error).outcome ==
			player_save_apply_outcome::applied,
		"partial save with retained source metadata: " + error);
	auto saved = loaded.snapshot;
	saved.revision = 3;
	saved.components = PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY;
	saved.items[0].values[0] = 99;
	require(flatfile_player_snapshot_apply(root, saved, &error).outcome ==
			player_save_apply_outcome::applied,
		"unrelated flat inventory save: " + error);
	player_snapshot stored;
	require(flatfile_player_snapshot_load(root, 42, &stored, &error) ==
				flatfile_player_load_result::ok &&
			stored.items.size() == 4 && stored.items[0].values[0] == 99 &&
			stored.items[2].object_uid == unknown.object_uid &&
			stored.items[2].name == unknown.name && stored.items[2].values[7] == 77 &&
			stored.items[3].object_uid == child.object_uid &&
			stored.items[3].parent_index == 2,
		"flat save lost held source data or the independent valid update");
	require(stored.retained_items.rows.empty(),
		"in-process selectors became an on-disk authority");
	saved.revision = 4;
	saved.items.resize(1);
	saved.items[0].values[0] = 123;
	require(flatfile_player_snapshot_apply(root, saved, &error).outcome ==
			player_save_apply_outcome::applied,
		"repeated save after valid prefix changed: " + error);
	request.request_id = 2;
	const auto again = flatfile_player_load_repository_execute(root, request);
	require(again.outcome == player_load_outcome::applied && again.snapshot.items.size() == 1 &&
			again.snapshot.retained_items.rows.size() == 2,
		"retention did not rederive after reload");
	auto retry = again.snapshot;
	retry.revision = 5;
	require(flatfile_player_snapshot_apply(root, retry, &error).outcome ==
			player_save_apply_outcome::applied,
		"save after retention reload: " + error);
	auto pet_overlap = retry;
	pet_overlap.revision = 6;
	pet_overlap.components = PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY |
				 PLAYER_COMPONENT_PETS;
	auto conflicting_pet = original.pets.front();
	conflicting_pet.pet_uid = 70042;
	conflicting_pet.items = { unknown_root ? child : unknown };
	conflicting_pet.items[0].parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	pet_overlap.pets = { conflicting_pet };
	const auto pet_refused = flatfile_player_snapshot_apply(root, pet_overlap, &error);
	require(pet_refused.outcome == player_save_apply_outcome::terminal_failure &&
			pet_refused.error_code == ESTALE,
		"active pet/held inventory UID overlap accepted");
	// The revision and foreign custody checks below prove refusal was atomic.
	retry.revision = 6;
	retry.retained_items.rows.pop_back();
	require(flatfile_player_snapshot_apply(root, retry, &error).outcome ==
			player_save_apply_outcome::terminal_failure,
		"changed retained source selection was accepted");
	require(flatfile_player_snapshot_load(root, 42, &stored, &error) ==
				flatfile_player_load_result::ok &&
			stored.revision == 5 && stored.items.size() == 3 &&
			stored.items[1].object_uid == unknown.object_uid &&
			stored.items[2].parent_index == 1,
		"failed retained save changed the original source");
	std::vector<flatfile_item_ownership_record> custody;
	require(flatfile_item_repository_load_uids(root, { other.items[0].object_uid }, &custody,
						   &error) == flatfile_item_repository_result::ok &&
			custody.size() == 1 && custody[0].owner.type == item_owner_type::player &&
			custody[0].owner.id == 43,
		"saving retained payload stole foreign custody");
	if (!unknown_root)
	{
		// Legacy files can contain two roots with the same foreign UID. Keep
		// all matching evidence without making unrelated inventory unavailable.
		stored.items.push_back(unknown);
		std::vector<uint8_t> payload;
		require(player_snapshot_encode(stored, &payload) ==
				player_snapshot_codec_result::ok,
			"encode duplicate-root fixture");
		stored.encoded_size_bound = payload.size();
		require(player_snapshot_encode(stored, &payload) ==
				player_snapshot_codec_result::ok,
			"normalize duplicate-root fixture");
		unsigned char digest[SHA256_DIGEST_LENGTH];
		SHA256(payload.data(), payload.size(), digest);
		std::ofstream file(path / "players/42.snapshot",
				   std::ios::binary | std::ios::trunc);
		const auto number = [&](uint64_t value, size_t bytes)
		{
			for (size_t index = 0; index < bytes; ++index)
				file.put(static_cast<char>(value >> (index * 8)));
		};
		const auto &magic = flatfile_player_snapshot_file::player_magic;
		file.write(reinterpret_cast<const char *>(magic.data()), magic.size());
		number(flatfile_player_snapshot_file::player_file_version, 4);
		number(payload.size(), 4);
		number(stored.pid, 4);
		number(stored.revision, 8);
		number(stored.components, 8);
		file.write(reinterpret_cast<const char *>(digest), sizeof(digest));
		file.write(reinterpret_cast<const char *>(payload.data()), payload.size());
		file.close();
		require(file.good(), "write duplicate-root fixture");
		request.request_id = 3;
		const auto aliased = flatfile_player_load_repository_execute(root, request);
		require(aliased.outcome == player_load_outcome::applied &&
				aliased.snapshot.items.size() == 1 &&
				aliased.snapshot.retained_items.rows.size() == 3,
			"foreign duplicate retained roots blocked unrelated inventory");
		auto next = aliased.snapshot;
		next.revision = 6;
		require(flatfile_player_snapshot_apply(root, next, &error).outcome ==
					player_save_apply_outcome::applied &&
				flatfile_player_snapshot_load(root, 42, &stored, &error) ==
					flatfile_player_load_result::ok &&
				stored.items.size() == 4,
			"save lost aliased retained roots");
	}
}

// A save claims what the player holds in the same authority transaction that writes
// the player file, so the ownership catalog follows memory: whatever the player file
// says after a save, the catalog says too, and nothing is left for a load to repair.
static void item_consistency_matrix(const fs::path &path)
{
	const std::string root = path.string();
	for (const auto &directory : { path, path / "players", path / "domains",
				       path / "identities", path / "identities/names" })
	{
		fs::create_directories(directory);
		fs::permissions(directory, fs::perms::owner_all, fs::perm_options::replace);
	}
	std::string error;
	int32_t pid = 0;
	for (int32_t i = 1; i <= 42; ++i)
		require(flatfile_identity_allocate_pid(root, &pid, &error) ==
				flatfile_identity_result::ok,
			"consistency identity allocation");
	require(flatfile_identity_claim(root, 42, "Player", "Account-One", &error) ==
			flatfile_identity_result::ok,
		"consistency identity claim");
	require(flatfile_player_snapshot_apply(root, make_full(1), &error).outcome ==
			player_save_apply_outcome::applied,
		"consistency baseline: " + error);
	auto reload = [&](const player_snapshot &snapshot, uint64_t request_id)
	{
		require(flatfile_player_snapshot_apply(root, snapshot, &error).outcome ==
				player_save_apply_outcome::applied,
			"item-consistency fixture save failed: " + error);
		player_load_request items_request = {};
		items_request.request_id = request_id;
		items_request.pid = 42;
		items_request.account_name = "account-one";
		items_request.deadline_usec =
			persistence_observability_now_usec() + PLAYER_LOAD_TIMEOUT_USEC;
		return flatfile_player_load_repository_execute(root, items_request);
	};
	player_item_snapshot orphan = {};
	orphan.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	orphan.object_uid = 103;
	orphan.vnum = 503;

	// The child taken out of its container stays out: the catalog moved with it.
	player_snapshot moved = make_full(2);
	moved.items[1].parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	player_load_result loaded = reload(moved, 9);
	require(loaded.outcome == player_load_outcome::applied && loaded.repaired_item_rows == 0 &&
			loaded.stale_item_rows == 0 &&
			loaded.snapshot.items[1].parent_index == PLAYER_SNAPSHOT_NO_PARENT &&
			!loaded.item_identities[1].parent_item_uid,
		"a moved item did not load where the save put it");

	// An item nobody had recorded is recorded by the save that holds it.
	player_snapshot extra = make_full(3);
	extra.items.push_back(orphan);
	loaded = reload(extra, 10);
	require(loaded.outcome == player_load_outcome::applied &&
			loaded.snapshot.items.size() == 3 && loaded.stale_item_rows == 0 &&
			loaded.missing_payload_rows == 0 &&
			// The legacy pet has no UID, so its item is the player's too.
			loaded.authoritative_item_count == 4,
		"a newly held item was not recorded by the save");

	// A container's contents follow it into another container.
	player_snapshot nested = make_full(4);
	nested.items.insert(nested.items.begin(), orphan);
	nested.items[1].parent_index = 0;
	nested.items[2].parent_index = 1;
	loaded = reload(nested, 11);
	require(loaded.outcome == player_load_outcome::applied &&
			loaded.snapshot.items.size() == 3 && loaded.stale_item_rows == 0 &&
			loaded.promoted_item_rows == 0 &&
			loaded.snapshot.items[1].parent_index == 0 &&
			loaded.snapshot.items[2].parent_index == 1 &&
			loaded.item_identities[1].root_item_uid == 103 &&
			loaded.item_identities[1].parent_item_uid == 103 &&
			loaded.item_identities[2].root_item_uid == 103,
		"nested contents did not load under their new container");

	// An item the player no longer holds stays recorded until its next holder claims
	// it; the load simply has no payload for it.
	player_snapshot dropped = make_full(5);
	dropped.items.pop_back();
	loaded = reload(dropped, 12);
	require(loaded.outcome == player_load_outcome::applied &&
			loaded.snapshot.items.size() == 1 && loaded.stale_item_rows == 0 &&
			loaded.missing_payload_rows == 2,
		"an item the player dropped refused the load");
}

// The wallet, epic points and frags are memory's: every save writes the ones it carries
// into the domain record.
static void saved_wallet_matrix(const fs::path &path)
{
	const std::string root = path.string();
	for (const auto &directory : { path, path / "players", path / "domains",
				       path / "identities", path / "identities/names" })
	{
		fs::create_directories(directory);
		fs::permissions(directory, fs::perms::owner_all, fs::perm_options::replace);
	}
	std::string error;
	int32_t pid = 0;
	for (int32_t i = 1; i <= 42; ++i)
		require(flatfile_identity_allocate_pid(root, &pid, &error) ==
				flatfile_identity_result::ok,
			"wallet player identity allocation");
	require(flatfile_identity_claim(root, 42, "Player", "Account-One", &error) ==
			flatfile_identity_result::ok,
		"wallet player identity claim");
	auto snapshot = make_full(1);
	snapshot.wallet_revision = 7; // Creation can already have granted starter money.
	for (const std::array<int64_t, 4> &wallet :
	     { std::array<int64_t, 4>{ 11, 12, 13, 14 }, std::array<int64_t, 4>{ 5, 0, 0, 1 },
	       std::array<int64_t, 4>{ 0, 0, 0, 0 } })
	{
		for (player_snapshot_integer &row : snapshot.status_integers)
			if (row.field == player_status_field::copper)
				row.signed_value = wallet[0];
			else if (row.field == player_status_field::silver)
				row.signed_value = wallet[1];
			else if (row.field == player_status_field::gold)
				row.signed_value = wallet[2];
			else if (row.field == player_status_field::platinum)
				row.signed_value = wallet[3];
			else if (row.field == player_status_field::epics)
				row.signed_value = wallet[0] * 100 - 5;
			else if (row.field == player_status_field::frags)
				row.signed_value = wallet[1] - 3;
			else if (row.field == player_status_field::old_frags)
				row.signed_value = wallet[2] + 1;
		require(flatfile_player_snapshot_apply(root, snapshot, &error).outcome ==
				player_save_apply_outcome::applied,
			"wallet player save: " + error);
		++snapshot.revision;
		flatfile_player_domain_record domain;
		require(flatfile_player_domain_load(root, 42, "Account-One", 0, &domain, &error) ==
					flatfile_player_domain_result::ok &&
				domain.domains.wallet_revision == snapshot.wallet_revision &&
				domain.domains.wallet ==
					std::array<uint64_t, 4>{
						static_cast<uint64_t>(wallet[0]),
						static_cast<uint64_t>(wallet[1]),
						static_cast<uint64_t>(wallet[2]),
						static_cast<uint64_t>(wallet[3]) } &&
				domain.domains.epics == wallet[0] * 100 - 5 &&
				domain.domains.frags == wallet[1] - 3 &&
				domain.domains.old_frags == wallet[2] + 1,
			"the save did not write the wallet, epics, frags and captured wallet revision");
		++snapshot.wallet_revision;
	}
	// A bank change is a delta added to the account's record for its side, created
	// when missing; a debit the record cannot cover is refused and changes nothing.
	const auto bank = [&]
	{
		flatfile_player_domain_record domain;
		require(flatfile_player_domain_load(root, 42, "Account-One", 0, &domain, &error) ==
				flatfile_player_domain_result::ok,
			"bank domain load");
		return domain.domains.bank;
	};
	flatfile_authority_operation credit, delta, debit;
	require(flatfile_bank_delta_apply(root, "Account-One", 0, { 7, 0, 3, 0 }, &credit, &error)
					.outcome == player_save_apply_outcome::applied &&
			(bank() == std::array<uint64_t, 4>{ 7, 0, 3, 0 }),
		"a bank credit did not create the record: " + error);
	require(flatfile_bank_delta_apply(root, "Account-One", 0, { 1, 0, -3, 4 }, &delta, &error)
					.outcome == player_save_apply_outcome::applied &&
			(bank() == std::array<uint64_t, 4>{ 8, 0, 0, 4 }),
		"a bank delta did not add to the record: " + error);
	// The writer retries a job whose commit may already have been written: the retry
	// writes the record the job prepared, so the change is not added twice.
	require(flatfile_bank_delta_apply(root, "Account-One", 0, { 1, 0, -3, 4 }, &delta, &error)
					.outcome == player_save_apply_outcome::applied &&
			(bank() == std::array<uint64_t, 4>{ 8, 0, 0, 4 }),
		"a retried bank delta was added twice: " + error);
	require(flatfile_bank_delta_apply(root, "Account-One", 0, { -9, 0, 0, 0 }, &debit, &error)
					.outcome == player_save_apply_outcome::terminal_failure &&
			(bank() == std::array<uint64_t, 4>{ 8, 0, 0, 4 }),
		"a debit the record cannot cover changed it");
	std::cout
		<< "flatfile saves write the wallet, epics and frags they carry; bank deltas add up\n";
}

/** Inspect synthetic authority on request, otherwise exercise player repository durability and recovery. */
// Real dispatcher -> six authority after-images -> interrupted commit/retry.
static void divine_trade_settlement(const fs::path &base)
{
	for (int boundary = 0; boundary <= 6; ++boundary)
	{
		const bool contraband = boundary % 2;
		const bool zero_sale = boundary == 6;
		const int slot_type = contraband ? SLOT_CONTRABAND : SLOT_CARGO;
		const auto goods = contraband ? divine_trade_goods::contraband :
						divine_trade_goods::cargo;
		const auto path = base / std::to_string(boundary);
		std::string root = path.string();
		const auto apply = [&](const critical_command &value)
		{ return flatfile_critical_command_repository_apply_selected(value, root.data()); };
		for (const auto &part :
		     { path, path / "players", path / "domains", path / "metadata",
		       path / "identities", path / "identities/names" })
		{
			fs::create_directories(part);
			fs::permissions(part, fs::perms::owner_all, fs::perm_options::replace);
		}
		std::string error;
		int32_t pid = 0;
		for (int i = 0; i < 42; ++i)
			require(flatfile_identity_allocate_pid(root, &pid, &error) ==
					flatfile_identity_result::ok,
				error);
		require(flatfile_identity_claim(root, 42, "Player", "Account-One", &error) ==
				flatfile_identity_result::ok,
			error);
		auto opening = make_full(1);
		opening.wallet_revision = 7;
		require(flatfile_player_snapshot_apply(root, opening, &error).outcome ==
				player_save_apply_outcome::applied,
			error);
		flatfile_ship_record ship;
		ship.ship_id = 1;
		ship.revision = 1;
		ship.owner_pid = 42;
		ship.owner_name = "player";
		ship.ship_name = "Trade fixture";
		ship.anchor_room = 1201;
		ship.slots.push_back({ 3, slot_type, 2, SLOT_HOLD, 0, { 9, 900, -1, -1, -1 } });
		require(flatfile_ship_establish(root, { ship }, &error) == flatfile_ship_result::ok,
			"trade ship establish: " + error);
		flat_cargo_record market;
		market.cargo.fill(1.0f);
		market.contraband.fill(1.0f);
		require(flatfile_cargo_save(root, market, &error) == flat_cargo_result::ok, error);
		critical_entity_key account;
		require(currency_account_key("Account-One", 0, &account),
			"canonical trade account");
		divine_boon_slot boon;
		boon.id = 17;
		boon.category = divine_boon_category::cargo;
		boon.starts_at = 100;
		boon.expires_at = 14500;
		boon.source_port = boon.cargo_commodity = boon.contraband_commodity = 2;
		boon.destination_port = 4;
		critical_operation_id buy_id{}, sell_id{};
		require(critical_operation_id_generate(&buy_id) &&
				critical_operation_id_generate(&sell_id),
			"trade IDs");
		divine_trade_purchase buy;
		buy.operation = buy_id;
		buy.goods = goods;
		buy.account = account.id;
		buy.ship_id = 1;
		buy.full_hold = 10;
		buy.slot = 3;
		buy.source_port = 2;
		buy.at = 101;
		buy.quantity = 1;
		buy.paid = 100;
		buy.slot_quantity_before = 9;
		buy.slot_basis_before = 900;
		divine_trade_payload purchase;
		purchase.pid = purchase.ship_owner_pid = 42;
		purchase.ship_id = 1;
		purchase.wallet_revision = 7;
		purchase.admitted_at = 101;
		purchase.payment = -100;
		purchase.wallet_after.amount = { 1, 3, 3, 15 }; // 15431 - 100 = 15331.
		purchase.slots_after.push_back(
			{ 3, slot_type, 2, SLOT_HOLD, 0, { 10, 1000, -1, -1, -1 } });
		purchase.slots_before = ship.slots;
		purchase.crew_before = ship.crew;
		purchase.market_after.push_back({ 2, 2, goods, 1.03f, 100 });
		require(divine_trade_prepare_purchase({}, boon, buy, &purchase.book_after),
			"prepare paid trade lot");
		critical_command command;
		require(divine_trade_command_build(&command, buy_id, purchase),
			"prepare buy command");
		for (int changed_field = 0; changed_field < 2; ++changed_field)
		{
			std::vector<flatfile_ship_record> stored;
			require(flatfile_ship_list(root, &stored, &error) ==
					flatfile_ship_result::ok,
				"read ship preimage");
			const auto original = stored.front();
			auto changed = original;
			if (changed_field)
				changed.crew.sail_chief = 1;
			else
			{
				changed.slots[0].values[0] = 8;
				changed.slots[0].values[1] = 800;
			}
			require(flatfile_ship_upsert(root, &changed, &error) ==
					flatfile_ship_result::ok,
				"ordinary ship change before delayed trade");
			critical_operation_id stale_id;
			require(critical_operation_id_generate(&stale_id), "stale ship command id");
			auto stale_trade = purchase;
			stale_trade.book_after.lots.back().purchase = stale_id;
			critical_command stale_command;
			require(divine_trade_command_build(&stale_command, stale_id, stale_trade),
				"prepare delayed ship command");
			require(apply(stale_command).error_code == ESTALE,
				"trade overwrote changed ship slot or crew");
			require(flatfile_ship_list(root, &stored, &error) ==
						flatfile_ship_result::ok &&
					stored[0].slots == changed.slots &&
					stored[0].crew == changed.crew,
				"stale trade changed ordinary ship state");
			auto restore = original;
			require(flatfile_ship_upsert(root, &restore, &error) ==
					flatfile_ship_result::ok,
				"restore ship preimage for journal boundary test");
		}
		setenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL", "1", 1);
		auto applied = apply(command);
		unsetenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL");
		require(applied.outcome == critical_apply_outcome::retryable_failure,
			"buy journal fault did not fire");
		applied = apply(command);
		require(applied.outcome == critical_apply_outcome::already_applied,
			"buy retry was not a stored receipt");
		std::vector<divine_trade_book> books;
		require(divine_trade_flatfile_books(root, 17, &books) && books.size() == 1 &&
				books[0] == purchase.book_after,
			"buy manifest did not recover");
		require(divine_trade_flatfile_restore_validate(root, &error),
			"valid trade history did not qualify");
		const auto market_path = fs::path(root) / "metadata" / "cargo_market";
		std::ifstream old_market_input(market_path, std::ios::binary);
		const std::string old_market{ std::istreambuf_iterator<char>(old_market_input),
					      std::istreambuf_iterator<char>() };
		char buy_hex[CRITICAL_COMMAND_ID_HEX_SIZE];
		critical_operation_id_to_hex(buy_id, buy_hex, sizeof(buy_hex));
		for (const auto &name :
		     { std::string("divine-trade-17-") +
			       std::to_string(purchase.book_after.account) + ".book",
		       std::string("divine-trade-command-") + buy_hex + ".receipt" })
		{
			std::fstream file(std::filesystem::path(root) / "domains" / name,
					  std::ios::in | std::ios::out | std::ios::binary);
			char original;
			file.seekg(-1, std::ios::end);
			file.read(&original, 1);
			require(file.good(), "open trade history corruption fixture");
			const char corrupt = original ^ 1;
			file.seekp(-1, std::ios::end);
			file.write(&corrupt, 1);
			file.flush();
			require(!divine_trade_flatfile_restore_validate(root, &error),
				"restore qualification ignored corrupt trade history");
			file.seekp(-1, std::ios::end);
			file.write(&original, 1);
			file.flush();
			require(divine_trade_flatfile_restore_validate(root, &error),
				"repaired trade history did not qualify");
		}

		std::vector<flatfile_ship_record> ships;
		require(flatfile_ship_list(root, &ships, &error) == flatfile_ship_result::ok &&
				ships.size() == 1 && ships[0].slots[0].values[0] == 10,
			"paid purchase cargo did not recover");
		flatfile_player_domain_record domain;
		require(flatfile_player_domain_load(root, 42, "Account-One", 0, &domain, &error) ==
					flatfile_player_domain_result::ok &&
				domain.domains.wallet == std::array<uint64_t, 4>{ 1, 3, 3, 15 } &&
				domain.domains.wallet_revision == 8,
			"paid purchase wallet did not recover");
		if (boundary == 0)
		{
			divine_trade_removal loss;
			loss.ship_id = 1;
			loss.slot = 3;
			loss.goods = goods;
			loss.source_port = 2;
			loss.at = 150;
			loss.slot_quantity_before = loss.quantity = 10;
			loss.slot_basis_before = 1000;
			divine_trade_book retired;
			divine_trade_consumption removed;
			require(divine_trade_prepare_removal(purchase.book_after, {}, loss,
							     &retired, &removed) &&
					retired.lots.empty() && !retired.consumed &&
					retired.first_full_hold == 10,
				"prepare complete ordinary cargo loss");
			flatfile_authority_operation proof;
			proof.filename = "divine-trade-17-" + std::to_string(account.id) + ".book";
			require(divine_trade_book_encode(retired, &proof.bytes),
				"encode loss proof");
			const std::vector<flatfile_authority_operation> after_images{ proof };
			for (bool deletion : { false, true })
				for (int interrupted = 0; interrupted <= 2; ++interrupted)
				{
					const auto clone =
						base /
						(std::string(deletion ? "delete-" : "loss-") +
						 std::to_string(interrupted));
					fs::copy(path, clone, fs::copy_options::recursive);
					auto changed = ships[0];
					changed.slots[0] = {
						3, SLOT_EMPTY, -1, -1, 0, { -1, -1, -1, -1, -1 }
					};
					const std::string step = std::to_string(interrupted);
					const char *fault =
						interrupted ?
							"DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_OPERATION" :
							"DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL";
					setenv(fault, interrupted ? step.c_str() : "1", 1);
					const auto saved =
						deletion ? flatfile_ship_remove(clone.string(), 1,
										changed.owner_name,
										&error,
										&after_images) :
							   flatfile_ship_upsert(clone.string(),
										&changed, &error,
										&after_images);
					unsetenv(fault);
					require(saved == flatfile_ship_result::io_error,
						"ordinary ship loss fault did not fire");
					std::vector<flatfile_ship_record> restored_ships;
					require(flatfile_ship_list(clone.string(), &restored_ships,
								   &error) ==
								flatfile_ship_result::ok &&
							(deletion ? restored_ships.empty() :
								    restored_ships[0]
										    .slots[0]
										    .slot_type ==
									    SLOT_EMPTY),
						"loss inventory journal recovery");
					std::vector<divine_trade_book> restored_books;
					require(divine_trade_flatfile_books(clone.string(), 17,
									    &restored_books) &&
							restored_books.size() == 1 &&
							restored_books[0] == retired,
						"loss proof/cap did not recover with inventory");
				}
		}
		auto conflict = purchase;
		conflict.wallet_after.amount[0]++;
		require(divine_trade_command_build(&command, buy_id, conflict),
			"conflicting retry command");
		require(apply(command).error_code == EEXIST,
			"trade identity conflict was accepted");
		auto stale = opening;
		stale.revision = 9999;
		require(flatfile_player_snapshot_apply(root, stale, &error).outcome ==
					player_save_apply_outcome::applied &&
				flatfile_player_domain_load(root, 42, "Account-One", 0, &domain,
							    &error) ==
					flatfile_player_domain_result::ok &&
				domain.domains.wallet == std::array<uint64_t, 4>{ 1, 3, 3, 15 } &&
				domain.domains.wallet_revision == 8,
			"old capture overwrote committed purchase money");
		divine_trade_removal remove;
		remove.goods = goods;
		remove.account = account.id;
		remove.ship_id = 1;
		remove.slot = 3;
		remove.source_port = 2;
		remove.destination_port = 4;
		remove.at = 200;
		remove.slot_quantity_before = remove.quantity = 10;
		remove.slot_basis_before = 1000;
		divine_trade_payload sale;
		sale.action = divine_trade_action::sale;
		sale.pid = sale.ship_owner_pid = 42;
		sale.ship_id = 1;
		sale.generation = 1;
		sale.book_revision = 1;
		sale.wallet_revision = 8;
		sale.admitted_at = 200;
		sale.payment =
			zero_sale ? 0 :
				    1230; // 10 * 120 ordinary + only the one eligible crate * 30.
		sale.wallet_after.amount = zero_sale ? std::array<int64_t, 4>{ 1, 3, 3, 15 } :
						       std::array<int64_t, 4>{ 1, 6, 5, 16 };
		sale.slots_after.push_back({ 3, SLOT_EMPTY, -1, -1, 0, { -1, -1, -1, -1, -1 } });
		sale.slots_before = purchase.slots_after;
		sale.crew_before = purchase.crew_after;
		sale.market_after.push_back(
			{ 4, 2, goods, zero_sale ? 0.0f : .95f, zero_sale ? 0 : 120 });
		divine_trade_consumption consumed;
		require(divine_trade_prepare_removal(books[0], boon, remove, &sale.book_after,
						     &consumed) &&
				consumed.qualifying_quantity == 1,
			"merged cargo sale boosted old stock");
		sale.qualifying_quantity = consumed.qualifying_quantity;
		sale.has_cargo_effect = !contraband && !zero_sale;
		sale.cargo_effect.type = PLAYER_TRADE_CARGO_AFFECT;
		sale.cargo_effect.duration = -1;
		sale.cargo_effect.modifier = 10005;

		require(divine_trade_command_build(&command, sell_id, sale),
			"prepare sale command");
		const std::string step = std::to_string(boundary);
		setenv(boundary ? "DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_OPERATION" :
				  "DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL",
		       boundary ? step.c_str() : "1", 1);
		applied = apply(command);
		unsetenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_OPERATION");
		unsetenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL");
		require(applied.outcome == critical_apply_outcome::retryable_failure,
			"sale boundary fault did not fire");
		applied = apply(command);
		require(applied.outcome == critical_apply_outcome::already_applied,
			"sale retry repeated the financial operation");
		char sell_hex[CRITICAL_COMMAND_ID_HEX_SIZE];
		critical_operation_id_to_hex(sell_id, sell_hex, sizeof(sell_hex));
		const auto buy_file = path / "domains" /
				      (std::string("divine-trade-command-") + buy_hex + ".receipt");
		const auto sell_file =
			path / "domains" /
			(std::string("divine-trade-command-") + sell_hex + ".receipt");
		std::ifstream receipt_input(sell_file, std::ios::binary);
		const std::vector<uint8_t> current_receipt{ std::istreambuf_iterator<char>(
								    receipt_input),
							    std::istreambuf_iterator<char>() };
		auto legacy_receipt = current_receipt;
		legacy_receipt.erase(legacy_receipt.begin() + 12,
				     legacy_receipt.begin() + 12 + CRITICAL_COMMAND_ID_BYTES);
		legacy_receipt[7] = '1';
		SHA256(legacy_receipt.data(), legacy_receipt.size() - SHA256_DIGEST_LENGTH,
		       legacy_receipt.data() + legacy_receipt.size() - SHA256_DIGEST_LENGTH);
		{
			std::ofstream legacy(sell_file, std::ios::binary | std::ios::trunc);
			legacy.write(reinterpret_cast<const char *>(legacy_receipt.data()),
				     legacy_receipt.size());
		}
		require(!divine_trade_flatfile_restore_validate(root, &error),
			"unbound legacy receipt restore was approved");
		require(apply(command).outcome == critical_apply_outcome::already_applied &&
				divine_trade_flatfile_restore_validate(root, &error),
			"proven legacy retry did not upgrade its receipt identity");
		{
			std::ofstream restored(sell_file, std::ios::binary | std::ios::trunc);
			restored.write(reinterpret_cast<const char *>(current_receipt.data()),
				       current_receipt.size());
		}
		const auto temporary = path / "domains" / "receipt-swap-fixture";
		fs::rename(buy_file, temporary);
		fs::rename(sell_file, buy_file);
		fs::rename(temporary, sell_file);
		require(!divine_trade_flatfile_restore_validate(root, &error) &&
				apply(command).error_code == EEXIST,
			"swapped valid receipts passed filename binding");
		fs::rename(buy_file, temporary);
		fs::rename(sell_file, buy_file);
		fs::rename(temporary, sell_file);
		require(divine_trade_flatfile_restore_validate(root, &error) &&
				apply(command).outcome == critical_apply_outcome::already_applied,
			"correct receipt identities did not restore");

		require(flatfile_player_domain_load(root, 42, "Account-One", 0, &domain, &error) ==
					flatfile_player_domain_result::ok &&
				domain.domains.wallet ==
					(zero_sale ? std::array<uint64_t, 4>{ 1, 3, 3, 15 } :
						     std::array<uint64_t, 4>{ 1, 6, 5, 16 }) &&
				domain.domains.wallet_revision == 9,
			"sale lost or duplicated its payment");
		require(flatfile_ship_list(root, &ships, &error) == flatfile_ship_result::ok &&
				ships[0].slots[0].slot_type == SLOT_EMPTY,
			"sale restored consumed cargo");
		require(flatfile_cargo_load(root, &market, &error) == flat_cargo_result::ok &&
				market.trade_generation == 2 &&
				(contraband ? market.contraband :
					      market.cargo)[4 * NUM_PORTS + 2] ==
					(zero_sale ? 0.0f : .95f),
			"sale market did not commit");
		std::ifstream new_market_input(market_path, std::ios::binary);
		const std::string new_market{ std::istreambuf_iterator<char>(new_market_input),
					      std::istreambuf_iterator<char>() };
		{
			std::ofstream rollback(market_path, std::ios::binary | std::ios::trunc);
			rollback << old_market;
		}
		require(!divine_trade_flatfile_restore_validate(root, &error),
			"valid older market qualified with newer successful receipts");
		{
			std::ofstream restore(market_path, std::ios::binary | std::ios::trunc);
			restore << new_market;
		}
		require(divine_trade_flatfile_restore_validate(root, &error),
			"matching market generation did not qualify");
		require(divine_trade_flatfile_books(root, 17, &books) && books.size() == 1 &&
				books[0].lots.empty() && books[0].consumed == 1 &&
				books[0].first_full_hold == 10,
			"sale lost the fixed spent allowance");
		applied = apply(command);
		require(applied.outcome == critical_apply_outcome::already_applied,
			"sale receipt was not permanent");
		player_snapshot saved;
		require(flatfile_player_snapshot_load(root, 42, &saved, &error) ==
				flatfile_player_load_result::ok,
			error);
		if (sale.has_cargo_effect)
			require(std::any_of(saved.affects.begin(), saved.affects.end(),
					    [](const auto &af)
					    { return af.type == 2110 && af.modifier == 10005; }),
				"financial sale omitted cargo achievement");
		auto captured = opening;
		captured.revision = 10000;
		captured.wallet_revision = 9;
		captured.pending_trade.operation = sell_id.bytes;
		captured.pending_trade.payment = sale.payment;
		captured.pending_trade.wallet_revision = 8;
		captured.pending_trade.has_cargo_effect = sale.has_cargo_effect;
		captured.pending_trade.cargo_effect = sale.cargo_effect;
		std::vector<uint8_t> encoded_command;
		require(critical_command_encode(command, &encoded_command) ==
				critical_command_codec_result::ok,
			"encode pending trade identity");
		SHA256(encoded_command.data(), encoded_command.size(),
		       captured.pending_trade.command_hash.data());
		for (auto &row : captured.status_integers)
		{
			if (row.field >= player_status_field::copper &&
			    row.field <= player_status_field::platinum)
			{
				const unsigned i =
					static_cast<unsigned>(row.field) -
					static_cast<unsigned>(player_status_field::copper);
				row.signed_value = i ? purchase.wallet_after.amount[i] : 21;
			}
			if (row.field == player_status_field::level)
				row.signed_value = 51;
		}
		const auto merged = zero_sale ? std::array<uint64_t, 4>{ 21, 3, 3, 15 } :
						std::array<uint64_t, 4>{ 21, 6, 5, 16 };
		const auto verify = [&]()
		{
			require(flatfile_player_domain_load(root, 42, "Account-One", 0, &domain,
							    &error) ==
						flatfile_player_domain_result::ok &&
					domain.domains.wallet == merged &&
					domain.domains.wallet_revision == 10,
				"pending capture lost/repeated payment");
			require(flatfile_player_snapshot_load(root, 42, &saved, &error) ==
						flatfile_player_load_result::ok &&
					saved.status_integers[0].signed_value == 51 &&
					!player_snapshot_trade_pending(saved),
				"pending capture lost ordinary status or retained tag");
			if (sale.has_cargo_effect)
				require(std::any_of(saved.affects.begin(), saved.affects.end(),
						    [](const auto &af) {
							    return af.type == 2110 &&
								   af.modifier == 10005;
						    }),
					"pending affect capture erased cargo achievement");
		};
		require(flatfile_player_snapshot_apply(root, captured, &error).outcome ==
				player_save_apply_outcome::applied,
			error);
		verify();
		require(flatfile_player_snapshot_apply(root, captured, &error).outcome ==
				player_save_apply_outcome::applied,
			error);
		verify();
		auto corrupt = captured;
		corrupt.pending_trade.command_hash[0] ^= 1;
		corrupt.components |= PLAYER_COMPONENT_TROPHIES;
		corrupt.trophies.push_back({ 123456, 77 });
		player_affect_snapshot unrelated{};
		unrelated.type = 1234;
		unrelated.modifier = 77;
		corrupt.affects.push_back(unrelated);
		require(flatfile_player_snapshot_apply(root, corrupt, &error).outcome ==
				player_save_apply_outcome::applied,
			"unresolved receipt dropped the terminal capture");
		verify();
		require(std::any_of(
				saved.trophies.begin(), saved.trophies.end(), [](const auto &row)
				{ return row.zone_number == 123456 && row.experience == 77; }) &&
				std::any_of(saved.affects.begin(), saved.affects.end(),
					    [](const auto &row)
					    { return row.type == 1234 && row.modifier == 77; }),
			"receipt quarantine lost unrelated trophy or affect state");
		auto unpaid = captured;
		require(player_snapshot_settle_trade(&unpaid, true) ==
				player_snapshot_codec_result::ok,
			"prepare current purse fixture");
		unpaid.pending_trade = captured.pending_trade;
		critical_operation_id absent;
		require(critical_operation_id_generate(&absent), "absent trade id");
		unpaid.pending_trade.operation = absent.bytes;
		require(flatfile_player_snapshot_apply(root, unpaid, &error).outcome ==
				player_save_apply_outcome::applied,
			error);
		verify();
		critical_command rejected;
		require(divine_trade_command_build(&rejected, absent, sale),
			"build rejected trade");
		require(apply(rejected).error_code == ESTALE,
			"stale trade did not retain rejection");
		encoded_command.clear();
		require(critical_command_encode(rejected, &encoded_command) ==
				critical_command_codec_result::ok,
			"encode rejected trade");
		SHA256(encoded_command.data(), encoded_command.size(),
		       unpaid.pending_trade.command_hash.data());
		require(flatfile_player_snapshot_apply(root, unpaid, &error).outcome ==
				player_save_apply_outcome::applied,
			error);
		verify();
	}
	std::cout
		<< "Divine trade purchase/sale recovery passed at journal and all six after-image boundaries\n";
}

int main(int argc, char **argv)
{
	if ((argc == 4 || argc == 5) && std::string(argv[2]) == "artifact-owner")
	{
		std::string error;
		flatfile_artifact_record record;
		require(flatfile_artifact_get(argv[1], std::stoi(argv[3]), &record, &error) ==
				flatfile_artifact_result::ok,
			"inspect artifact: " + error);
		if (argc == 5)
		{
			// Only the isolated journey invokes this, with its server stopped.
			record.location_type = std::stoi(argv[4]);
			record.location = 88;
			record.owned = record.location_type != FLATFILE_ARTIFACT_NOT_IN_GAME;
			require(flatfile_artifact_snapshot_apply(argv[1], { record }, &error) ==
					flatfile_artifact_result::ok,
				"seed stale tracking: " + error);
		}
		std::cout << "{\"uid\":" << record.canonical_item_uid
			  << ",\"identity\":" << static_cast<int>(record.identity_state)
			  << ",\"owned\":" << record.owned << ",\"type\":" << record.location_type
			  << ",\"location\":" << record.location << ",\"timer\":" << record.timer
			  << ",\"soul\":" << record.bind_owner_pid
			  << ",\"bind\":" << record.bind_timer << "}\n";
		return 0;
	}
	if (argc == 3 && std::string(argv[2]) == "seed-creation-bank")
	{
		std::string error;
		flatfile_player_domain_record seed;
		seed.pid = 999;
		seed.account_name = "Journeyacct";
		seed.racewar = 1;
		seed.domains.bank = { 17, 23, 31, 47 };
		require(flatfile_player_domain_establish(argv[1], seed, &error) ==
				flatfile_player_domain_result::ok,
			"seed creation bank: " + error);
		// A deposit lands the way the writer's bank job writes it, at bank revision two.
		flatfile_authority_operation deposit;
		require(flatfile_bank_delta_apply(argv[1], seed.account_name, seed.racewar,
						  { 2, 0, 0, 0 }, &deposit, &error)
					.outcome == player_save_apply_outcome::applied,
			"advance creation bank revision: " + error);
		return 0;
	}
	if (argc == 3 && std::string(argv[2]) == "seed-combat")
	{
		std::string error;
		require(flatfile_boon_establish(argv[1], {}, &error) == flatfile_boon_result::ok,
			"seed empty combat boon catalog: " + error);
		return 0;
	}
	// Offline fixture setup only, against the temporary state owned by the journey.
	// Use the real creation transaction and checkpoint writer so item UID/custody
	// agree when the unmodified server restores the item.
	if (argc == 3 && std::string(argv[2]) == "seed-item-operator")
	{
		std::string error;
		player_snapshot snapshot;
		require(flatfile_player_snapshot_load(argv[1], 1, &snapshot, &error) ==
				flatfile_player_load_result::ok,
			"seed operator: " + error);
		for (auto &field : snapshot.status_integers)
			if (field.field == player_status_field::level)
				field = { player_status_field::level, 61, 0, false };
		++snapshot.revision;
		snapshot.components = PLAYER_CHECKPOINT_COMPONENT_ALL;
		snapshot.encoded_size_bound = PLAYER_SNAPSHOT_MAX_BYTES;
		require(flatfile_player_snapshot_apply(argv[1], snapshot, &error).outcome ==
				player_save_apply_outcome::applied,
			"save operator: " + error);
		return 0;
	}
	if (argc == 4 && std::string(argv[2]) == "seed-item")
	{
		std::string error;
		player_snapshot snapshot;
		require(flatfile_player_snapshot_load(argv[1], 1, &snapshot, &error) ==
				flatfile_player_load_result::ok,
			"seed player: " + error);
		player_item_snapshot item = {};
		item.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
		std::ifstream input(argv[3]);
		int type, material;
		input >> item.vnum >> type >> material >> item.craftsmanship >> item.extra_flags >>
			item.wear_flags >> item.extra2_flags >> item.anti_flags >>
			item.anti2_flags >> item.weight >> item.cost >> item.condition;
		item.type = type;
		item.material = material;
		for (auto &value : item.values)
			input >> value;
		for (auto &value : item.bitvectors)
			input >> value;
		for (auto &affect : item.affects)
			input >> affect[0] >> affect[1];
		require(input.good(), "read fixture prototype");
		item.object_uid = 1000000 + item.vnum;
		item_transfer_payload payload = {};
		payload.from_owner = { item_owner_type::system, 0, 0 };
		payload.to_owner = { item_owner_type::player, 1, 0 };
		std::vector<flatfile_item_ownership_record> owned;
		require(flatfile_item_repository_load_owner(
				argv[1], payload.from_owner, &payload.expected_from_revision,
				&owned, &error) == flatfile_item_repository_result::ok,
			"seed system owner: " + error);
		require(flatfile_item_repository_load_owner(
				argv[1], payload.to_owner, &payload.expected_to_revision, &owned,
				&error) == flatfile_item_repository_result::ok,
			"seed player owner: " + error);
		payload.reason = item_transfer_reason::creation;
		payload.reason_id = 297;
		payload.selected_item_uid = payload.target_root_item_uid = item.object_uid;
		payload.item_count = 1;
		payload.items[0] = { item.object_uid,
				     item.object_uid,
				     0,
				     ITEM_TRANSFER_ABSENT_REVISION,
				     item.vnum,
				     item_custody_state::absent };
		std::vector<uint8_t> blob;
		require(player_item_snapshot_list_encode({ item }, &blob) ==
				player_snapshot_codec_result::ok,
			"encode fixture item");
		payload.item_blob_size = blob.size();
		std::copy(blob.begin(), blob.end(), payload.item_blob.begin());
		critical_operation_id operation;
		critical_command command;
		require(critical_operation_id_generate(&operation) &&
				item_transfer_command_build(&command, operation, payload,
							    critical_source_site::command,
							    critical_deadline_class::interactive),
			"build fixture creation");
		command.accepted_at_usec = static_cast<uint64_t>(time(nullptr)) * 1000000;
		const auto created = flatfile_item_repository_apply(argv[1], command);
		require(created.outcome == critical_apply_outcome::applied,
			"create fixture item: " + std::to_string(created.error_code));
		snapshot.items.push_back(item);
		++snapshot.revision;
		snapshot.components = PLAYER_CHECKPOINT_COMPONENT_ALL;
		snapshot.encoded_size_bound = PLAYER_SNAPSHOT_MAX_BYTES;
		require(flatfile_player_snapshot_apply(argv[1], snapshot, &error).outcome ==
				player_save_apply_outcome::applied,
			"save seeded item: " + error);
		if (item.extra_flags & (1U << 28))
		{
			const flatfile_artifact_record artifact = { item.vnum,
								    true,
								    FLATFILE_ARTIFACT_ON_PLAYER,
								    1,
								    time(nullptr) + 86400,
								    2,
								    time(nullptr),
								    0,
								    0,
								    0 };
			const auto updated =
				flatfile_artifact_snapshot_apply(argv[1], { artifact }, &error);
			require(updated == flatfile_artifact_result::ok,
				"seed artifact catalog: " + error);
		}
		std::cout << item.object_uid << '\n';
		return 0;
	}
	if (argc == 4 && std::string(argv[2]) == "inspect")
	{
		inspect_authority(argv[1], std::stoi(argv[3]));
		return 0;
	}
	if (argc >= 4 && std::string(argv[2]).starts_with("cleric-"))
	{
		// This command is used only against the journey's disposable saved players.
		std::string error;
		player_snapshot snapshot;
		require(flatfile_player_snapshot_load(argv[1], std::stoi(argv[3]), &snapshot,
						      &error) == flatfile_player_load_result::ok,
			"Cleric fixture load: " + error);
		if (std::string(argv[2]) == "cleric-inspect")
		{
			std::cout << '[';
			bool first = true;
			for (const auto &af : snapshot.affects)
			{
				if (!first)
					std::cout << ',';
				first = false;
				std::cout << "[" << af.type << ',' << af.duration << ',' << af.flags
					  << ',' << af.modifier << ',' << int(af.location) << ']';
			}
			std::cout << "]\n";
			return 0;
		}
		if (std::string(argv[2]) == "cleric-expire")
		{
			for (auto &af : snapshot.affects)
				if (af.flags & AFFTYPE_SHORT)
					af.duration = 40;
		}
		else
		{
			require(argc == 6 && std::string(argv[2]) == "cleric-seed",
				"Cleric seed expects PID, specialization, level");
			for (auto &field : snapshot.status_integers)
			{
				int value;
				switch (field.field)
				{
				case player_status_field::class_primary:
					value = CLASS_CLERIC;
					break;
				case player_status_field::class_secondary:
					value = 0;
					break;
				case player_status_field::specialization:
					value = std::stoi(argv[4]);
					break;
				case player_status_field::level:
				case player_status_field::highest_level:
					value = std::stoi(argv[5]);
					break;
				case player_status_field::base_hit:
					value = 2000;
					break;
				case player_status_field::hit_difference:
					value = 500;
					break;
				default:
					continue;
				}
				field.signed_value = field.unsigned_value = value;
			}
			const int spells[] = { SPELL_MIRACLE, SPELL_TRUE_SEEING,
					       SPELL_DIVINE_WARDING, SPELL_VITAL_INTERCESSION };
			snapshot.skills.clear();
			snapshot.affects.clear();
			for (int spell : spells)
			{
				snapshot.skills.push_back({ spell, 100, 100 });
				for (int i = 0; i < ((spell == SPELL_DIVINE_WARDING ||
						      spell == SPELL_MIRACLE) ?
							     2 :
							     1);
				     ++i)
				{
					player_affect_snapshot af{};
					af.type = TAG_MEMORIZE;
					af.flags = AFFTYPE_STORE | AFFTYPE_PERM | MEMTYPE_FULL;
					af.duration = -1;
					af.modifier = spell;
					snapshot.affects.push_back(af);
				}
			}
			for (int skill : { SKILL_SPELL_KNOWLEDGE_CLERICAL, SKILL_QUICK_CHANT,
					   SKILL_CONCENTRATION })
				snapshot.skills.push_back({ skill, 100, 100 });
			player_affect_snapshot pending{};
			pending.type = TAG_MEMORIZE;
			pending.flags = AFFTYPE_STORE | AFFTYPE_PERM;
			pending.duration = -1;
			pending.modifier = SPELL_VITAL_INTERCESSION;
			snapshot.affects.push_back(pending);
			pending.modifier = SPELL_MIRACLE;
			snapshot.affects.push_back(pending);
		}
		++snapshot.revision;
		snapshot.components = PLAYER_CHECKPOINT_COMPONENT_ALL;
		snapshot.encoded_size_bound = PLAYER_SNAPSHOT_MAX_BYTES;
		require(flatfile_player_snapshot_apply(argv[1], snapshot, &error).outcome ==
				player_save_apply_outcome::applied,
			"Cleric fixture save: " + error);
		return 0;
	}
	if (argc >= 4 && std::string(argv[2]) == "inspect-world-items")
	{
		inspect_world_items(argv[1], argc, argv);
		return 0;
	}
	require(argc == 2, "state root argument required");
	const fs::path root = argv[1];
	saved_wallet_matrix(root / "saved-wallet");
	divine_trade_settlement(root / "trade-settlement");
	const fs::path players = root / "players";
	const fs::path identities = root / "identities/names";
	const fs::path domains = root / "domains";
	fs::create_directories(players);
	fs::create_directories(identities);
	fs::create_directories(domains);
	fs::permissions(root, fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(players, fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(root / "identities", fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(identities, fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(domains, fs::perms::owner_all, fs::perm_options::replace);

	std::string error;
	int32_t allocated_pid = 0;
	for (int32_t expected_pid = 1; expected_pid <= 42; ++expected_pid)
		require(flatfile_identity_allocate_pid(root.string(), &allocated_pid, &error) ==
					flatfile_identity_result::ok &&
				allocated_pid == expected_pid,
			"could not allocate player PID: " + error);
	require(flatfile_identity_claim(root.string(), 42, "Player", "Account-One", &error) ==
			flatfile_identity_result::ok,
		"could not claim player identity: " + error);
	player_save_apply_result applied =
		flatfile_player_snapshot_apply(root.string(), make_status(1, 10, 100), &error);
	require(applied.outcome == player_save_apply_outcome::terminal_failure &&
			applied.error_code == ENOENT,
		"partial snapshot created a missing player baseline");
	player_snapshot full = make_full(1);
	std::vector<uint8_t> legacy_bytes;
	require(player_snapshot_encode(full, &legacy_bytes) == player_snapshot_codec_result::ok,
		"could not encode legacy-compatible status fixture");
	legacy_bytes.resize(legacy_bytes.size() - sizeof(uint64_t) - 1);
	legacy_bytes[0] = 9; // Older status has no delivery field or wallet metadata.
	player_snapshot legacy;
	uint64_t legacy_sequence = 99;
	require(player_snapshot_decode(legacy_bytes.data(), legacy_bytes.size(), &legacy) ==
				player_snapshot_codec_result::ok &&
			player_snapshot_divine_delivery_sequence(legacy, &legacy_sequence) &&
			!legacy_sequence,
		"version-9 player status did not upgrade with an empty delivery marker");
	applied = flatfile_player_snapshot_apply(root.string(), full, &error);
	require(applied.outcome == player_save_apply_outcome::applied &&
			applied.durable_revision == 1,
		"full baseline apply failed: " + error);
	player_snapshot loaded;
	require(flatfile_player_snapshot_load(root.string(), 42, &loaded, &error) ==
				flatfile_player_load_result::ok &&
			loaded.components == PLAYER_CHECKPOINT_COMPONENT_ALL &&
			loaded.revision == 1 && loaded.status_integers[0].signed_value == 50 &&
			loaded.languages[0].value == 90 && loaded.items.size() == 2 &&
			loaded.items[1].parent_index == 0 &&
			loaded.items[0].extra_descriptions[0].spell_ids[1] == 12 &&
			loaded.pets[0].items[0].vnum == 501 && loaded.shapes[0].mob_vnum == 800 &&
			loaded.trophies[0].experience == 300 &&
			loaded.output_preferences == full.output_preferences,
		"full player snapshot did not round trip: " + error);
	require(loaded.status_strings.back().value == std::string(64, 'a'),
		"news acknowledgement did not round trip");
	player_load_request load_request = {};
	load_request.request_id = 1;
	load_request.pid = 42;
	load_request.account_name = "account-one";
	load_request.deadline_usec =
		persistence_observability_now_usec() + PLAYER_LOAD_TIMEOUT_USEC;
	player_load_result load_result =
		flatfile_player_load_repository_execute(root.string(), load_request);
	require(load_result.pid == 42 && load_result.snapshot.revision == 1 &&
			load_result.item_owner_revision == 1 &&
			load_result.item_identities.size() == 2 &&
			load_result.item_identities[1].parent_item_uid == 100 &&
			load_result.pet_identities.size() == 1 &&
			load_result.pet_identities[0].item_identities.size() == 1 &&
			load_result.domains.wallet == std::array<uint64_t, 4>{ 11, 12, 13, 14 } &&
			load_result.domains.bank_revision == 1 && load_result.domains.epics == 15 &&
			load_result.domains.frags == 16 && load_result.domains.old_frags == 17 &&
			load_result.domains.base_stat_revision == 1 &&
			load_result.domains.base_stats[0] == 50 &&
			load_result.domains.base_stats[9] == 59 &&
			load_result.read_components == PLAYER_LOAD_SESSION04_READS &&
			load_result.outcome == player_load_outcome::applied &&
			load_result.error_code == 0 && !load_result.failed_component,
		"verified snapshot/domain load was not reported as materializable");
	load_request.request_id = 2;
	load_request.account_name = "wrong-account";
	load_result = flatfile_player_load_repository_execute(root.string(), load_request);
	require(load_result.outcome == player_load_outcome::component_failure &&
			load_result.error_code == EACCES &&
			std::string(load_result.failed_component) == "identity",
		"account/PID mismatch was accepted");
	// An offline load (player_load_offline()) names the character by pid and no account.
	load_request.account_name.clear();
	load_result = flatfile_player_load_repository_execute(root.string(), load_request);
	require(load_result.pid == 42 && load_result.outcome == player_load_outcome::applied,
		"an offline load by pid alone was refused");
	load_request = {};
	load_request.request_id = 3;
	load_request.player_name = "pLaYeR";
	load_request.deadline_usec =
		persistence_observability_now_usec() + PLAYER_LOAD_TIMEOUT_USEC;
	load_result = flatfile_player_load_repository_execute(root.string(), load_request);
	require(load_result.pid == 42 && load_result.account_name == "Account-One" &&
			load_result.outcome == player_load_outcome::applied,
		"canonical name lookup did not resolve the snapshot identity");
	load_request.deadline_usec = persistence_observability_now_usec();
	load_result = flatfile_player_load_repository_execute(root.string(), load_request);
	require(load_result.outcome == player_load_outcome::timed_out &&
			load_result.error_code == ETIMEDOUT,
		"expired flat-file load request was accepted");

	// An unrelated component save leaves the discoveries from the full checkpoint intact.
	player_snapshot language_checkpoint = {};
	language_checkpoint.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
	language_checkpoint.pid = 42;
	language_checkpoint.revision = 2;
	language_checkpoint.components = PLAYER_COMPONENT_LANGUAGES;
	language_checkpoint.encoded_size_bound = 1024;
	language_checkpoint.languages = { { 1, 90, 0 } };
	require(flatfile_player_snapshot_apply(root.string(), language_checkpoint, &error).outcome ==
			player_save_apply_outcome::applied,
		"language checkpoint failed");
	require(flatfile_player_snapshot_load(root.string(), 42, &loaded, &error) ==
			flatfile_player_load_result::ok,
		"language checkpoint could not load");
	bool found_flights = false;
	for (const auto &field : loaded.status_integers)
		if (field.field == player_status_field::learned_flight_stops)
			found_flights = field.is_unsigned &&
					field.unsigned_value == ((uint64_t{ 1 } << 26) | 1);
	require(found_flights, "unrelated component save erased flight discoveries");
	require(loaded.status_strings.back().value == std::string(64, 'a'),
		"unrelated component erased news acknowledgement");
	player_snapshot trophy_checkpoint = make_status(2, 51, 1202);
	trophy_checkpoint.status_integers.push_back(
		{ player_status_field::learned_flight_stops, 0, 7, true });
	trophy_checkpoint.status_integers.push_back(
		{ player_status_field::experience, 12345, 0, false });
	trophy_checkpoint.components |= PLAYER_COMPONENT_TROPHIES;
	trophy_checkpoint.trophies = { { 12, 645 }, { 34, 678 } };
	applied = flatfile_player_snapshot_apply(root.string(), trophy_checkpoint, &error);
	require(applied.outcome == player_save_apply_outcome::applied &&
			applied.durable_revision == 2,
		"partial status merge failed: " + error);
	require(flatfile_player_snapshot_load(root.string(), 42, &loaded, &error) ==
				flatfile_player_load_result::ok &&
			loaded.revision == 2 && loaded.room_vnum == 1202 &&
			loaded.status_integers[0].signed_value == 51 && loaded.items.size() == 2 &&
			loaded.languages[0].value == 90 && loaded.trophies.size() == 2 &&
			loaded.trophies[0].experience == 645 &&
			loaded.trophies[1].experience == 678 && loaded.output_preferences.empty(),
		"partial status merge discarded an untouched component");
	require(loaded.status_strings.back().value == std::string(64, 'b'),
		"status save did not replace news acknowledgement");

	require(loaded.status_integers[1].unsigned_value == 7 &&
			loaded.status_integers[2].signed_value == 12345,
		"status checkpoint did not keep discoveries and EXP together");
	player_snapshot torn_items = {};
	torn_items.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
	torn_items.pid = 42;
	torn_items.revision = 3;
	torn_items.components = PLAYER_COMPONENT_INVENTORY;
	torn_items.encoded_size_bound = 256;
	applied = flatfile_player_snapshot_apply(root.string(), torn_items, &error);
	require(applied.outcome == player_save_apply_outcome::terminal_failure &&
			applied.error_code == EINVAL,
		"one-sided item component replacement was accepted");

	trophy_checkpoint.revision = 3;
	trophy_checkpoint.trophies.clear();
	applied = flatfile_player_snapshot_apply(root.string(), trophy_checkpoint, &error);
	require(applied.outcome == player_save_apply_outcome::applied,
		"empty trophy checkpoint failed");
	require(flatfile_player_snapshot_load(root.string(), 42, &loaded, &error) ==
				flatfile_player_load_result::ok &&
			loaded.trophies.empty(),
		"empty trophy checkpoint did not remove previous totals");

	for (player_revision_t revision : { 4U, 5U })
	{
		const pid_t child_process = fork();
		require(child_process >= 0, "player writer fork failed");
		if (!child_process)
		{
			std::string child_error;
			const player_save_apply_result child_result =
				flatfile_player_snapshot_apply(root.string(),
							       make_status(revision, 50 + revision,
									   1200 + revision),
							       &child_error);
			_exit(child_result.outcome == player_save_apply_outcome::applied ||
					      child_result.outcome ==
						      player_save_apply_outcome::stale_revision ?
				      0 :
				      2);
		}
	}
	for (int child = 0; child < 2; ++child)
	{
		int status = 0;
		require(wait(&status) > 0 && WIFEXITED(status) && WEXITSTATUS(status) == 0,
			"concurrent player writer failed");
	}
	// Saves carry no revision fence any more: the one writer applies them in capture
	// order, so two processes racing leave whichever committed last. The authority lock
	// still makes each write whole: the file holds one snapshot, never a mix of two.
	require(flatfile_player_snapshot_load(root.string(), 42, &loaded, &error) ==
				flatfile_player_load_result::ok &&
			(loaded.revision == 4 || loaded.revision == 5) &&
			loaded.status_integers[0].signed_value ==
				50 + static_cast<int64_t>(loaded.revision),
		"concurrent player writers left a torn player file");

	item_consistency_matrix(root / "consistency");
	source_id_gap_case(root / "source-gap");
	retained_roots_case(root / "retention", true);
	retained_roots_case(root / "retained-child", false);
	require(flatfile_player_snapshot_apply(root.string(), make_full(10), &error).outcome ==
			player_save_apply_outcome::applied,
		"could not save the item fixture: " + error);

	{
		flatfile_player_snapshot_lock snapshot_lock;
		flatfile_authority_lock authority_lock;
		flatfile_authority_operation snapshot_remove, domain_remove;
		require(snapshot_lock.acquire(root.string(), 42, &error) &&
				authority_lock.acquire(root.string(), &error),
			"could not acquire player deletion preparation locks: " + error);
		require(flatfile_player_snapshot_prepare_remove(
				root.string(), snapshot_lock, authority_lock, 42, &snapshot_remove,
				&error) == flatfile_player_load_result::ok &&
				snapshot_remove.store == flatfile_authority_store::players &&
				snapshot_remove.kind == flatfile_authority_operation_kind::remove &&
				snapshot_remove.filename == "42.snapshot",
			"player snapshot removal was not prepared: " + error);
		require(flatfile_player_domain_prepare_remove(root.string(), authority_lock, 42,
							      &domain_remove, &error) ==
					flatfile_player_domain_result::ok &&
				domain_remove.store == flatfile_authority_store::domains &&
				domain_remove.kind == flatfile_authority_operation_kind::remove &&
				domain_remove.filename == "player-42.domain",
			"player domain removal was not prepared: " + error);
	}

	// Prepare an award, load it through the ordinary login reader, then commit
	// the actual full status checkpoint containing its balance and watermark.
	{
		flatfile_player_domain_record opponent;
		opponent.pid = 43;
		opponent.account_name = "divine-victim";
		opponent.racewar = 2;
		require(flatfile_player_domain_establish(root.string(), opponent, &error) ==
				flatfile_player_domain_result::ok,
			"establish Divine opponent");
		combat_outcome_payload event = {};
		event.victim_pid = 43;
		event.participant_count = 2;
		event.prepared_at = 150;
		event.participants[0].pid = 42;
		event.participants[0].role = combat_participant_role::killer;
		event.participants[0].racewar = 1;
		event.participants[0].flags = COMBAT_PARTICIPANT_IN_ROOM |
					      COMBAT_PARTICIPANT_DIVINE_EPIC;
		event.participants[0].frag_delta = 100;
		event.participants[0].epic_delta = 150;
		event.participants[0].epic_boon_id = 7;
		event.participants[0].epic_base = 100;
		event.participants[1].pid = 43;
		event.participants[1].role = combat_participant_role::victim;
		event.participants[1].racewar = 2;
		critical_operation_id identity = {};
		identity.bytes[0] = 223;
		critical_command command;
		require(combat_outcome_command_build(&command, identity, event),
			"build prepared PvP");
		command.accepted_at_usec = 1;
		require(flatfile_player_domain_apply(root.string(), command).outcome ==
				critical_apply_outcome::applied,
			"prepare PvP receipt");
		command.operation_id.bytes[0] = 224;
		require(flatfile_player_domain_apply(root.string(), command).outcome ==
				critical_apply_outcome::applied,
			"prepare second PvP receipt");
		player_load_request recovery = {};
		recovery.request_id = 900;
		recovery.pid = 42;
		recovery.account_name = "account-one";
		recovery.deadline_usec =
			persistence_observability_now_usec() + PLAYER_LOAD_TIMEOUT_USEC;
		const auto owed = flatfile_player_load_repository_execute(root.string(), recovery);
		require(owed.outcome == player_load_outcome::applied &&
				owed.divine_epic_deliveries.size() == 2 &&
				owed.divine_epic_deliveries[0].amount == 150 &&
				owed.divine_epic_deliveries[0].sequence == 1 &&
				owed.divine_epic_deliveries[1].sequence == 2 &&
				owed.divine_epic_deliveries[1].previous == 1,
			"flat login omitted an unpaid prepared receipt");
		auto credited = make_full(11);
		for (auto &field : credited.status_integers)
			if (field.field == player_status_field::epics)
				field.signed_value = owed.domains.epics + 300;
		credited.status_integers.push_back(
			{ player_status_field::divine_boon_delivery_seq, 0, 2, true });
		setenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL", "1", 1);
		require(flatfile_player_snapshot_apply(root.string(), credited, &error).outcome ==
				player_save_apply_outcome::retryable_failure,
			"prepared checkpoint interruption");
		unsetenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL");
		const auto paid_credit =
			flatfile_player_load_repository_execute(root.string(), recovery);
		require(paid_credit.outcome == player_load_outcome::applied &&
				paid_credit.divine_epic_deliveries.empty() &&
				paid_credit.domains.epics == owed.domains.epics + 300,
			"flat checkpoint recovery lost or duplicated the prepared payout: outcome=" +
				std::to_string(static_cast<unsigned>(paid_credit.outcome)) +
				", balance=" + std::to_string(paid_credit.domains.epics) +
				", before=" + std::to_string(owed.domains.epics) + ", pending=" +
				std::to_string(paid_credit.divine_epic_deliveries.size()) +
				", component=" +
				(paid_credit.failed_component ? paid_credit.failed_component :
								"none"));
		zone_touch_payload touch = {};
		touch.zone_number = 18;
		touch.toucher_pid = 42;
		touch.stone_uid = 987654321;
		touch.touched_at = 1200;
		touch.boot_time = 1000;
		touch.group_size = 1;
		touch.participant_pids[0] = 42;
		touch.epic_value = 100;
		touch.alignment_delta = 1;
		touch.prepared_delivery = true;
		touch.awards[0] = { 150, 0, 0, 7, 100 };
		critical_command stone;
		critical_operation_id stone_id;
		stone_id.bytes[0] = 225;
		require(zone_touch_command_build(&stone, stone_id, touch), "build prepared stone");
		stone.accepted_at_usec = 1;
		setenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL", "1", 1);
		require(flatfile_player_domain_apply(root.string(), stone).outcome ==
				critical_apply_outcome::retryable_failure,
			"stone claim journal fault");
		unsetenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL");
		const auto stone_replay = flatfile_player_domain_apply(root.string(), stone);
		require(stone_replay.outcome == critical_apply_outcome::already_applied,
			"stone claim recovery");
		zone_touch_result stone_receipt;
		require(zone_touch_command_decode_result(stone_replay.result_payload.data(),
							 stone_replay.result_size,
							 &stone_receipt) &&
				stone_receipt.revisions[0] == 3 && stone_receipt.previous[0] == 2 &&
				stone_receipt.awards[0].amount == 150,
			"stone receipt lost preparation");
		const auto stone_owed =
			flatfile_player_load_repository_execute(root.string(), recovery);
		require(stone_owed.outcome == player_load_outcome::applied &&
				stone_owed.divine_epic_deliveries.size() == 1 &&
				stone_owed.divine_epic_deliveries[0].zone &&
				stone_owed.divine_epic_deliveries[0].sequence == 3 &&
				stone_owed.domains.epics == paid_credit.domains.epics,
			"unpaid stone reload changed balance");
		require(std::binary_search(stone_owed.completed_epic_zones.begin(),
					   stone_owed.completed_epic_zones.end(), 18),
			"recovered stone claim lost recipient completion history");
		require(flatfile_player_domain_restore_recover(root.string(), &error) ==
				flatfile_player_domain_result::ok,
			"restore qualification rejected valid stone history");
		for (const auto *name : { "stone-987654321.claim", "zone-18.state" })
		{
			std::fstream file(root / "domains" / name,
					  std::ios::in | std::ios::out | std::ios::binary);
			char original;
			file.seekg(-1, std::ios::end);
			file.read(&original, 1);
			require(file.good(), "open stone history corruption fixture");
			const char corrupt = original ^ 1;
			file.seekp(-1, std::ios::end);
			file.write(&corrupt, 1);
			file.flush();
			require(flatfile_player_domain_restore_recover(root.string(), &error) ==
					flatfile_player_domain_result::invalid,
				"restore qualification ignored corrupt stone history");
			file.seekp(-1, std::ios::end);
			file.write(&original, 1);
			file.flush();
			require(flatfile_player_domain_restore_recover(root.string(), &error) ==
					flatfile_player_domain_result::ok,
				"repaired stone history did not qualify");
		}
		flatfile_zone_touch_state zone;
		require(flatfile_zone_touch_load(root.string(), 18, &zone, &error) ==
					flatfile_player_domain_result::ok &&
				zone.alignment == 1 && zone.last_touch == 1200,
			"zone history missing after recovered claim");
		stone_id.bytes[0] = 226;
		touch.awards[0].amount = 999;
		require(zone_touch_command_build(&stone, stone_id, touch), "retouch changed boon");
		stone.accepted_at_usec = 1;
		const auto retouch = flatfile_player_domain_apply(root.string(), stone);
		require(retouch.outcome == critical_apply_outcome::applied &&
				zone_touch_command_decode_result(retouch.result_payload.data(),
								 retouch.result_size,
								 &stone_receipt) &&
				stone_receipt.recovered_claim &&
				stone_receipt.awards[0].amount == 150,
			"retouch paid or recomputed a committed stone");
		command.operation_id.bytes[0] = 227;
		require(flatfile_player_domain_apply(root.string(), command).outcome ==
				critical_apply_outcome::applied,
			"prepare PvP after zone");
		const auto mixed = flatfile_player_load_repository_execute(root.string(), recovery);
		require(mixed.outcome == player_load_outcome::applied &&
				mixed.divine_epic_deliveries.size() == 2 &&
				mixed.divine_epic_deliveries[1].sequence == 4 &&
				mixed.divine_epic_deliveries[1].previous == 3,
			"zone and PvP recipient chain diverged");
		auto combined = credited;
		combined.revision = 12;
		for (auto &field : combined.status_integers)
		{
			if (field.field == player_status_field::epics)
				field.signed_value = paid_credit.domains.epics + 300;
			if (field.field == player_status_field::divine_boon_delivery_seq)
				field.unsigned_value = 4;
		}
		require(flatfile_player_snapshot_apply(root.string(), combined, &error).outcome ==
				player_save_apply_outcome::applied,
			"mixed award checkpoint");
		const auto settled =
			flatfile_player_load_repository_execute(root.string(), recovery);
		require(settled.outcome == player_load_outcome::applied &&
				settled.divine_epic_deliveries.empty() &&
				settled.domains.epics == paid_credit.domains.epics + 300,
			"mixed award checkpoint lost or duplicated credit");
	}

	const fs::path snapshot_path = players / "42.snapshot";
	player_snapshot paid = make_status(13, 51, 1201);
	paid.wallet_revision = 19;
	paid.status_integers.insert(paid.status_integers.end(),
				    { { player_status_field::copper, 11, 0, false },
				      { player_status_field::silver, 12, 0, false },
				      { player_status_field::gold, 13, 0, false },
				      { player_status_field::platinum, 14, 0, false },
				      { player_status_field::frags, 16, 0, false },
				      { player_status_field::old_frags, 17, 0, false } });
	paid.status_integers.push_back({ player_status_field::racewar, 0, 0, false });
	paid.status_integers.push_back({ player_status_field::epics, 450, 0, false });
	paid.status_integers.push_back(
		{ player_status_field::divine_boon_delivery_seq, 0, 5, true });
	setenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL", "1", 1);
	require(flatfile_player_snapshot_apply(root.string(), paid, &error).outcome ==
			player_save_apply_outcome::retryable_failure,
		"delivery fault did not interrupt the authority commit");
	unsetenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL");
	require(flatfile_player_snapshot_apply(root.string(), paid, &error).outcome ==
			player_save_apply_outcome::applied,
		"Divine status checkpoint failed: " + error);
	auto stale_delivery = paid;
	stale_delivery.revision = 14;
	stale_delivery.status_integers[stale_delivery.status_integers.size() - 2].signed_value = 1;
	stale_delivery.status_integers.back().unsigned_value = 2;
	require(flatfile_player_snapshot_apply(root.string(), stale_delivery, &error).outcome ==
			player_save_apply_outcome::stale_revision,
		"stale Divine capture was applied");
	auto mixed_delivery = stale_delivery;
	mixed_delivery.components |= PLAYER_COMPONENT_SKILLS | PLAYER_COMPONENT_LANGUAGES;
	mixed_delivery.skills = { { 9, 73, 2 } };
	mixed_delivery.languages = { { 1, 82, 0 } };
	require(flatfile_player_snapshot_apply(root.string(), mixed_delivery, &error).outcome ==
			player_save_apply_outcome::applied,
		"stale status discarded unrelated components");
	require(flatfile_player_snapshot_load(root.string(), 42, &loaded, &error) ==
			flatfile_player_load_result::ok,
		"paid Divine checkpoint could not reload");
	uint64_t delivered_sequence = 0;
	require(player_snapshot_divine_delivery_sequence(loaded, &delivered_sequence) &&
			delivered_sequence == 5 &&
			loaded.status_integers[loaded.status_integers.size() - 2].signed_value ==
				450,
		"stale save erased the Divine balance or applied marker");
	require(loaded.revision == mixed_delivery.revision && loaded.skills.size() == 1 &&
			loaded.skills[0].learned == 73 && loaded.languages.size() == 1 &&
			loaded.languages[0].value == 82,
		"mixed stale status lost skill/language changes");
	flatfile_identity_record delivery_identity;
	flatfile_player_domain_record delivery_domains;
	require(flatfile_identity_lookup_pid(root.string(), 42, &delivery_identity, &error) ==
				flatfile_identity_result::ok &&
			flatfile_player_domain_load(root.string(), 42, delivery_identity.account,
						    delivery_identity.racewar, &delivery_domains,
						    &error) == flatfile_player_domain_result::ok &&
			delivery_domains.domains.epics == 450,
		"delivery marker advanced without the authoritative epic balance");
	auto incomplete_delivery = make_status(14, 51, 1201);
	incomplete_delivery.status_integers.push_back(
		{ player_status_field::epics, 500, 0, false });
	incomplete_delivery.status_integers.push_back(
		{ player_status_field::divine_boon_delivery_seq, 0, 6, true });
	require(flatfile_player_snapshot_apply(root.string(), incomplete_delivery, &error).outcome ==
			player_save_apply_outcome::terminal_failure,
		"marker advanced without a complete financial checkpoint");
	auto malformed_delivery = paid;
	malformed_delivery.status_integers.back().is_unsigned = false;
	require(flatfile_player_snapshot_apply(root.string(), malformed_delivery, &error).outcome ==
			player_save_apply_outcome::terminal_failure,
		"signed delivery marker was accepted");
	malformed_delivery = paid;
	malformed_delivery.status_integers.push_back(paid.status_integers.back());
	require(flatfile_player_snapshot_apply(root.string(), malformed_delivery, &error).outcome ==
			player_save_apply_outcome::terminal_failure,
		"duplicate delivery marker was accepted");
	// A wallet commit is protected by the existing wallet revision even if an
	// old capture carries a later general save revision and the right epic marker.
	auto stale_wallet = paid;
	stale_wallet.revision = 99999;
	stale_wallet.wallet_revision = 18;
	stale_wallet.status_integers[3].signed_value = 1;
	stale_wallet.components |= PLAYER_COMPONENT_LANGUAGES;
	stale_wallet.languages = { { 1, 97, 0 } };
	const auto wallet_conflict =
		flatfile_player_snapshot_apply(root.string(), stale_wallet, &error);
	require(wallet_conflict.outcome == player_save_apply_outcome::applied,
		"stale wallet dropped unrelated language work after extraction");
	player_snapshot wallet_loaded;
	require(flatfile_player_snapshot_load(root.string(), 42, &wallet_loaded, &error) ==
				flatfile_player_load_result::ok &&
			wallet_loaded.wallet_revision == 19 && !wallet_loaded.languages.empty() &&
			wallet_loaded.languages.front().value == 97,
		"stale wallet save lost unrelated language work");
	// A later current-wallet checkpoint still preserves both components.
	auto refreshed = stale_wallet;
	refreshed.revision = 100000;
	refreshed.wallet_revision = 19;
	refreshed.status_integers[3].signed_value = paid.status_integers[3].signed_value;
	require(flatfile_player_snapshot_apply(root.string(), refreshed, &error).outcome ==
			player_save_apply_outcome::applied,
		"fresh wallet and language recapture failed: " + error);
	require(flatfile_player_snapshot_load(root.string(), 42, &wallet_loaded, &error) ==
				flatfile_player_load_result::ok &&
			wallet_loaded.wallet_revision == 19 && !wallet_loaded.languages.empty() &&
			wallet_loaded.languages.front().value == 97,
		"freshly recaptured language work was dropped");
	auto wallet_request = load_request;
	wallet_request.deadline_usec =
		persistence_observability_now_usec() + PLAYER_LOAD_TIMEOUT_USEC;
	wallet_request.include_items = false;
	wallet_request.include_pets = false;
	auto wallet_domain = flatfile_player_load_repository_execute(root.string(), wallet_request);
	require(wallet_domain.outcome == player_load_outcome::applied &&
			wallet_domain.domains.wallet_revision == 19 &&
			wallet_domain.domains.wallet[0] == 11,
		"stale capture changed the durable wallet or load revision");
	{
		std::fstream file(snapshot_path, std::ios::in | std::ios::out | std::ios::binary);
		require(file.good(), "could not open player snapshot for corruption test");
		file.seekg(-1, std::ios::end);
		char value = 0;
		file.read(&value, 1);
		value ^= 0x5a;
		file.seekp(-1, std::ios::end);
		file.write(&value, 1);
	}
	require(flatfile_player_snapshot_load(root.string(), 42, &loaded, &error) ==
			flatfile_player_load_result::invalid,
		"corrupt player checksum was accepted");
	for (const fs::directory_entry &entry : fs::directory_iterator(players))
		require(entry.path().filename().string().find(".tmp.") == std::string::npos,
			"temporary player file was left behind");

	std::cout << "flat-file player repository passed\n";
	return 0;
}
