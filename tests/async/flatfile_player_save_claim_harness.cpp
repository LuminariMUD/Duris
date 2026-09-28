// The flat-file backend claims exactly as MariaDB does: a player save writes what
// the player holds in memory and makes the ownership catalog agree in the same
// authority transaction. Items other owners held are taken and logged to
// logs/log/item_claims; an item an auction holds is left out with its contents
// and logged to logs/log/dupes; nothing refuses the save.
#include "flatfile/flatfile_identity_repository.h"
#include "flatfile/flatfile_item_repository.h"
#include "flatfile/flatfile_player_repository.h"
#include "player/player_save_worker.h"

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <unistd.h>

namespace fs = std::filesystem;

bool player_load_request_valid(const player_load_request &, uint64_t)
{
	return true;
}

namespace
{
void require(bool condition, const std::string &message)
{
	if (!condition)
	{
		std::cerr << "FAILED: " << message << '\n';
		exit(1);
	}
}

player_item_snapshot item(uint64_t uid, int32_t vnum, int32_t parent)
{
	player_item_snapshot snapshot = {};
	snapshot.parent_index = parent;
	snapshot.object_uid = uid;
	snapshot.vnum = vnum;
	return snapshot;
}

player_snapshot snapshot_for(player_revision_t revision, int32_t pid = 42,
			     const char *name = "Player")
{
	player_snapshot snapshot = {};
	snapshot.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
	snapshot.pid = pid;
	snapshot.revision = revision;
	snapshot.components = PLAYER_CHECKPOINT_COMPONENT_ALL;
	snapshot.save_intent = 1;
	snapshot.room_vnum = 3001;
	snapshot.encoded_size_bound = 8192;
	snapshot.status_integers.push_back({ player_status_field::level, 20, 0, false });
	snapshot.status_integers.push_back({ player_status_field::racewar, 0, 0, false });
	for (const player_status_field field :
	     { player_status_field::copper, player_status_field::silver, player_status_field::gold,
	       player_status_field::platinum, player_status_field::epics,
	       player_status_field::frags, player_status_field::old_frags })
		snapshot.status_integers.push_back({ field, 0, 0, false });
	for (int index = 0; index < 10; ++index)
		snapshot.status_integers.push_back(
			{ static_cast<player_status_field>(
				  static_cast<unsigned int>(player_status_field::base_strength) +
				  index),
			  50, 0, false });
	snapshot.status_strings.push_back({ player_status_string_field::name, name });
	snapshot.recipes_are_external = true;
	return snapshot;
}

struct fixture_item
{
	uint64_t uid;
	uint64_t root;
	uint64_t parent;
	int32_t vnum;
};

void establish(const std::string &root, const item_owner_identity &owner,
	       const std::vector<fixture_item> &items)
{
	std::string error;
	std::vector<flatfile_item_ownership_record> records;
	for (const fixture_item &entry : items)
		records.push_back({ entry.uid, entry.root, entry.parent, owner, 1, entry.vnum,
				    item_custody_state::active });
	require(flatfile_item_repository_establish_owner(root, owner, records, &error) ==
			flatfile_item_baseline_result::applied,
		"fixture owner: " + error);
}

std::vector<flatfile_item_ownership_record> held_by(const std::string &root,
						    const item_owner_identity &owner)
{
	uint64_t revision = 0;
	std::vector<flatfile_item_ownership_record> items;
	std::string error;
	const auto loaded =
		flatfile_item_repository_load_owner(root, owner, &revision, &items, &error);
	require(loaded == flatfile_item_repository_result::ok ||
			loaded == flatfile_item_repository_result::not_found,
		"load owner: " + error);
	return items;
}

std::string text_of(const fs::path &path)
{
	std::ifstream file(path);
	std::stringstream lines;
	lines << file.rdbuf();
	return lines.str();
}
} // namespace

int main(int argc, char **argv)
{
	require(argc == 2, "usage: harness <root>");
	const fs::path path = argv[1];
	const std::string root = path.string();
	for (const auto &directory : { path, path / "players", path / "domains",
				       path / "identities", path / "identities/names" })
	{
		fs::create_directories(directory);
		fs::permissions(directory, fs::perms::owner_all, fs::perm_options::replace);
	}
	// The logs go under the working directory, as they do for the server.
	require(chdir(root.c_str()) == 0, "chdir");
	std::string error;
	int32_t pid = 0;
	for (int32_t i = 1; i <= 42; ++i)
		require(flatfile_identity_allocate_pid(root, &pid, &error) ==
				flatfile_identity_result::ok,
			"identity allocation");
	require(flatfile_identity_claim(root, 42, "Player", "Account-One", &error) ==
			flatfile_identity_result::ok,
		"identity claim");

	const item_owner_identity player = { item_owner_type::player, 42, 0 };
	const item_owner_identity corpse = { item_owner_type::corpse, 9001, 0 };
	const item_owner_identity room = { item_owner_type::room, 3001, 0 };
	const item_owner_identity other = { item_owner_type::player, 7, 0 };
	const item_owner_identity auction = { item_owner_type::auction, 12, 0 };
	const item_owner_identity pet = { item_owner_type::pet, 88, 42 };
	establish(root, corpse, { { 1001, 1001, 0, 501 } });
	establish(root, room, { { 1003, 1003, 0, 503 } });
	establish(root, other, { { 1004, 1004, 0, 504 } });
	establish(root, auction, { { 1006, 1006, 0, 506 }, { 1007, 1006, 1006, 507 } });

	player_snapshot save = snapshot_for(1);
	save.items = {
		item(1010, 510, PLAYER_SNAPSHOT_NO_PARENT), // a bag nobody has recorded
		item(1003, 503, 0), // the room item, in the bag
		item(1001, 501, PLAYER_SNAPSHOT_NO_PARENT),
		item(1004, 504, PLAYER_SNAPSHOT_NO_PARENT),
		item(1006, 506, PLAYER_SNAPSHOT_NO_PARENT), // held by an auction
		item(1007, 507, 4),
	};
	player_pet_snapshot follower = {};
	follower.pet_uid = 88;
	follower.mob_vnum = 700;
	follower.room_vnum = 3001;
	follower.items = { item(1005, 505, PLAYER_SNAPSHOT_NO_PARENT) };
	save.pets.push_back(follower);
	player_save_apply_result applied = flatfile_player_snapshot_apply(root, save, &error);
	require(applied.outcome == player_save_apply_outcome::applied,
		"a save whose items other owners hold must commit: outcome=" +
			std::to_string(static_cast<int>(applied.outcome)) +
			" error=" + std::to_string(applied.error_code) + " " + error);

	const auto mine = held_by(root, player);
	std::vector<uint64_t> uids;
	for (const auto &record : mine)
		uids.push_back(record.item_uid);
	require((uids == std::vector<uint64_t>{ 1001, 1003, 1004, 1010 }),
		"the player now holds the corpse, room and other player's items and the bag");
	for (const auto &record : mine)
		if (record.item_uid == 1003)
			require(record.root_item_uid == 1010 && record.parent_item_uid == 1010,
				"the room item sits in the bag");
	require(held_by(root, corpse).empty() && held_by(root, room).empty() &&
			held_by(root, other).empty(),
		"the old owners no longer hold the claimed items");
	require(held_by(root, auction).size() == 2, "the auction keeps what it holds");
	const auto pet_items = held_by(root, pet);
	require(pet_items.size() == 1 && pet_items[0].item_uid == 1005,
		"the pet holds its own item");

	player_snapshot stored = {};
	require(flatfile_player_snapshot_read(root, 42, &stored, &error) ==
			flatfile_player_load_result::ok,
		"read back: " + error);
	uids.clear();
	for (const auto &entry : stored.items)
		uids.push_back(entry.object_uid);
	require((uids == std::vector<uint64_t>{ 1010, 1003, 1001, 1004 }),
		"the auction's container and its contents are left out of the player file");
	require(stored.items[1].parent_index == 0, "the room item is written inside the bag");

	const std::string claims = text_of(path / "logs/log/item_claims");
	for (const char *line : { "claimed uid=1001 vnum=501 from=corpse:9001:0 to=player:42:0",
				  "claimed uid=1003 vnum=503 from=room:3001:0 to=player:42:0",
				  "claimed uid=1004 vnum=504 from=player:7:0 to=player:42:0" })
		require(claims.find(line) != std::string::npos,
			std::string("claim log is missing: ") + line + "\n" + claims);
	const std::string dupes = text_of(path / "logs/log/dupes");
	require(dupes.find("save_left_out uid=1006 vnum=506 lost_by=player:42:0 "
			   "held_by=auction:12:0") != std::string::npos &&
			dupes.find("save_left_out uid=1007 vnum=507 lost_by=player:42:0 "
				   "held_by=auction:12:0") != std::string::npos,
		"the dupe log names both left-out items: " + dupes);

	// No revision fence: an older ordinary save is written; a legacy replay is not.
	player_snapshot older = snapshot_for(1);
	require(flatfile_player_snapshot_apply(root, older, &error).outcome ==
				player_save_apply_outcome::applied &&
			flatfile_player_snapshot_read(root, 42, &stored, &error) ==
				flatfile_player_load_result::ok &&
			stored.items.empty(),
		"an ordinary save is never fenced by revision");
	player_snapshot replay = snapshot_for(1);
	replay.items = { item(1001, 501, PLAYER_SNAPSHOT_NO_PARENT) };
	require(flatfile_player_snapshot_apply(root, replay, &error, true).outcome ==
			player_save_apply_outcome::already_applied,
		"a legacy replay the file already has is skipped");
	replay.revision = 2;
	require(flatfile_player_snapshot_apply(root, replay, &error, true).outcome ==
			player_save_apply_outcome::applied,
		"a newer legacy replay is applied");
	// A new player's first save records its owner even when it holds nothing, so the
	// game can hydrate the owner revision straight after creation.
	require(flatfile_identity_claim(root, 41, "Newcomer", "Account-Two", &error) ==
			flatfile_identity_result::ok,
		"second identity claim");
	require(flatfile_player_snapshot_apply(root, snapshot_for(1, 41, "Newcomer"), &error)
				.outcome == player_save_apply_outcome::applied,
		"empty-handed new player save: " + error);
	uint64_t newcomer_revision = 0;
	std::vector<flatfile_item_ownership_record> newcomer_items;
	require(flatfile_item_repository_load_owner(root, { item_owner_type::player, 41, 0 },
						    &newcomer_revision, &newcomer_items, &error) ==
				flatfile_item_repository_result::ok &&
			newcomer_revision == 1 && newcomer_items.empty(),
		"a new player without items has no owner record");
	// A load takes only what the catalog gives the player. The newcomer's save claims
	// the corpse's old item; the player's file still lists it, and its next load
	// leaves it behind and logs it.
	player_snapshot player_save = snapshot_for(3);
	player_save.items = { item(1001, 501, PLAYER_SNAPSHOT_NO_PARENT),
			      item(1004, 504, PLAYER_SNAPSHOT_NO_PARENT) };
	require(flatfile_player_snapshot_apply(root, player_save, &error).outcome ==
			player_save_apply_outcome::applied,
		"player save before the hand-over: " + error);
	player_snapshot newcomer_save = snapshot_for(2, 41, "Newcomer");
	newcomer_save.items = { item(1001, 501, PLAYER_SNAPSHOT_NO_PARENT) };
	require(flatfile_player_snapshot_apply(root, newcomer_save, &error).outcome ==
			player_save_apply_outcome::applied,
		"newcomer save: " + error);
	player_load_request request = {};
	request.request_id = 1;
	request.pid = 42;
	request.account_name = "Account-One";
	request.include_items = true;
	request.include_pets = true;
	const player_load_result loaded = flatfile_player_load_repository_execute(root, request);
	require(loaded.outcome == player_load_outcome::applied,
		"the player's load must succeed: component=" +
			std::string(loaded.failed_component ? loaded.failed_component : "none"));
	require(loaded.snapshot.items.size() == 1 && loaded.snapshot.items[0].object_uid == 1004 &&
			loaded.stale_item_rows == 1,
		"the player loads what it still holds and skips what the newcomer took");
	require(text_of(path / "logs/log/dupes")
				.find("load_skipped uid=1001 vnum=501 lost_by=player:42:0 "
				      "held_by=player:41:0") != std::string::npos,
		"the dupe log names the skipped item");
	// A corpse save claims what the corpse holds; a saved room item claims its graph
	// for the room and takes a piece out of the corpse record that still lists it; a
	// removed corpse leaves the catalog (persistence reset step 6).
	const auto loose = [](uint64_t uid, int32_t vnum, int32_t parent)
	{
		player_item_snapshot entry = item(uid, vnum, parent);
		entry.equipment_slot = -1;
		return entry;
	};
	flatfile_corpse_record dead;
	dead.owner_pid = 41;
	dead.owner_name = "Newcomer";
	dead.save_id = 555;
	dead.room_vnum = 3001;
	dead.short_description = "the corpse of Newcomer";
	dead.description = "The corpse of Newcomer is lying here.";
	dead.keywords = "newcomer corpse _pcorpse_";
	dead.items = { loose(1001, 501, PLAYER_SNAPSHOT_NO_PARENT), loose(1030, 530, 0) };
	require(flatfile_corpse_snapshot_apply(root, dead, false, &error).outcome ==
			player_save_apply_outcome::applied,
		"corpse save: " + error);
	const item_owner_identity dead_corpse = { item_owner_type::corpse,
						  (static_cast<uint64_t>(41) << 32) | 555, 0 };
	require(held_by(root, dead_corpse).size() == 2, "the corpse claims its items");
	flatfile_saved_world_item_record chest;
	chest.item_key = "item.uid.1040";
	chest.room_vnum = 3001;
	chest.items = { loose(1040, 540, PLAYER_SNAPSHOT_NO_PARENT), loose(1030, 530, 0) };
	require(flatfile_saved_item_snapshot_apply(root, chest, false, &error).outcome ==
			player_save_apply_outcome::applied,
		"saved item save: " + error);
	std::vector<flatfile_corpse_record> corpses;
	std::vector<flatfile_saved_world_item_record> saved_items;
	require(flatfile_world_item_list(root, &corpses, &saved_items, &error) ==
				flatfile_world_item_result::ok &&
			corpses.size() == 1 && corpses[0].items.size() == 1 &&
			corpses[0].items[0].object_uid == 1001 && saved_items.size() == 1 &&
			saved_items[0].items.size() == 2,
		"the saved item takes its piece out of the corpse record");
	const auto in_room = held_by(root, room);
	require(std::count_if(in_room.begin(), in_room.end(), [](const auto &record)
			      { return record.item_uid == 1030 || record.item_uid == 1040; }) == 2,
		"the room holds the saved item and its contents");
	require(flatfile_corpse_snapshot_apply(root, dead, true, &error).outcome ==
				player_save_apply_outcome::applied &&
			flatfile_world_item_list(root, &corpses, &saved_items, &error) ==
				flatfile_world_item_result::ok &&
			corpses.empty(),
		"a corpse leaving the world is removed");
	std::cout << "flat-file player save claim passed\n";
	return 0;
}
