// The flat-file backend claims exactly as MariaDB does: a player save writes what
// the player holds in memory and makes the ownership catalog agree in the same
// authority transaction. Items other owners held are taken and logged to
// logs/log/item_claims, an auction's included; an item the catalog says was
// destroyed is left out with its contents and logged to logs/log/dupes; nothing
// refuses the save.
#include "flatfile/flatfile_identity_repository.h"
#include "flatfile/flatfile_item_repository.h"
#include "flatfile/flatfile_player_repository.h"
#include "player/player_save_worker.h"
#include "player/player_snapshot_codec.h"

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <unistd.h>
#include <unordered_set>

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
		item(1006, 506, PLAYER_SNAPSHOT_NO_PARENT), // an auction's, by the catalog
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
	require((uids == std::vector<uint64_t>{ 1001, 1003, 1004, 1006, 1007, 1010 }),
		"the player now holds the corpse, room, other player's and auction's items and "
		"the bag");
	for (const auto &record : mine)
		if (record.item_uid == 1003)
			require(record.root_item_uid == 1010 && record.parent_item_uid == 1010,
				"the room item sits in the bag");
	require(held_by(root, corpse).empty() && held_by(root, room).empty() &&
			held_by(root, other).empty() && held_by(root, auction).empty(),
		"the old owners no longer hold the claimed items");
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
	require((uids == std::vector<uint64_t>{ 1010, 1003, 1001, 1004, 1006, 1007 }),
		"the player file holds every claimed item");
	require(stored.items[1].parent_index == 0, "the room item is written inside the bag");

	const std::string claims = text_of(path / "logs/log/item_claims");
	for (const char *line : { "claimed uid=1001 vnum=501 from=corpse:9001:0 to=player:42:0",
				  "claimed uid=1003 vnum=503 from=room:3001:0 to=player:42:0",
				  "claimed uid=1004 vnum=504 from=player:7:0 to=player:42:0",
				  "claimed uid=1006 vnum=506 from=auction:12:0 to=player:42:0",
				  "claimed uid=1007 vnum=507 from=auction:12:0 to=player:42:0" })
		require(claims.find(line) != std::string::npos,
			std::string("claim log is missing: ") + line + "\n" + claims);
	require(text_of(path / "logs/log/dupes").find("uid=1006") == std::string::npos,
		"nothing the save claimed is in the dupe log");

	// No revision fence: an older ordinary save is written.
	player_snapshot older = snapshot_for(1);
	require(flatfile_player_snapshot_apply(root, older, &error).outcome ==
				player_save_apply_outcome::applied &&
			flatfile_player_snapshot_read(root, 42, &stored, &error) ==
				flatfile_player_load_result::ok &&
			stored.items.empty(),
		"an ordinary save is never fenced by revision");
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
	// for the room, joins the room's record and takes a piece out of the corpse record
	// that still lists it; removals leave the catalog (persistence reset step 6).
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
	require(flatfile_corpse_snapshot_apply(root, dead, false, {}, &error).outcome ==
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
	std::vector<flatfile_room_item_record> rooms;
	require(flatfile_world_item_list(root, &corpses, &saved_items, &error) ==
				flatfile_world_item_result::ok &&
			flatfile_world_item_list_rooms(root, &rooms, &error) ==
				flatfile_world_item_result::ok &&
			corpses.size() == 1 && corpses[0].items.size() == 1 &&
			corpses[0].items[0].object_uid == 1001 && rooms.size() == 1 &&
			rooms[0].room_vnum == 3001 && rooms[0].items.size() == 2 &&
			rooms[0].items[1].parent_index == 0,
		"the saved item joins its room's record and leaves the corpse record");
	const auto in_room = held_by(root, room);
	require(std::count_if(in_room.begin(), in_room.end(), [](const auto &record)
			      { return record.item_uid == 1030 || record.item_uid == 1040; }) == 2,
		"the room holds the saved item and its contents");
	require(flatfile_saved_item_snapshot_apply(root, chest, true, &error).outcome ==
				player_save_apply_outcome::applied &&
			flatfile_world_item_list_rooms(root, &rooms, &error) ==
				flatfile_world_item_result::ok &&
			rooms.size() == 1 && rooms[0].items.empty(),
		"a saved item leaving the room leaves its record");
	require(flatfile_corpse_snapshot_apply(root, dead, true, {}, &error).outcome ==
				player_save_apply_outcome::applied &&
			flatfile_world_item_list(root, &corpses, &saved_items, &error) ==
				flatfile_world_item_result::ok &&
			corpses.empty(),
		"a corpse leaving the world is removed");
	// A destroyed item stays destroyed. Player 8's bag and what it holds are destroyed,
	// as a sale for destruction leaves them; a save of player 42 captured before that
	// still holds the bag, and leaves it and its contents out.
	const item_owner_identity seller = { item_owner_type::player, 8, 0 };
	establish(root, seller, { { 1060, 1060, 0, 560 }, { 1061, 1060, 1060, 561 } });
	{
		flatfile_authority_lock lock;
		flatfile_authority_operation operation;
		require(lock.acquire(root, &error) &&
				flatfile_item_repository_prepare_player_remove(
					root, lock, 8, &operation, &error) ==
					flatfile_item_repository_result::ok &&
				flatfile_authority_transaction_commit_operations(
					root, lock, { operation }, &error) ==
					flatfile_authority_transaction_result::ok,
			"destroying the seller's items: " + error);
	}
	player_snapshot stale = snapshot_for(4);
	stale.items = { item(1060, 560, PLAYER_SNAPSHOT_NO_PARENT), item(1061, 561, 0),
			item(1004, 504, PLAYER_SNAPSHOT_NO_PARENT) };
	require(flatfile_player_snapshot_apply(root, stale, &error).outcome ==
			player_save_apply_outcome::applied,
		"a save holding destroyed items still commits: " + error);
	std::vector<flatfile_item_ownership_record> destroyed;
	require(flatfile_item_repository_load_uids(root, { 1060, 1061 }, &destroyed, &error) ==
				flatfile_item_repository_result::ok &&
			destroyed.size() == 2,
		"read the destroyed records: " + error);
	for (const auto &record : destroyed)
		require(record.owner.type == item_owner_type::destruction &&
				record.state == item_custody_state::destroyed,
			"a destroyed item stays destroyed: uid=" + std::to_string(record.item_uid));
	require(flatfile_player_snapshot_read(root, 42, &stored, &error) ==
				flatfile_player_load_result::ok &&
			stored.items.size() == 1 && stored.items[0].object_uid == 1004,
		"the destroyed bag and its contents are left out of the player file");
	const std::string left_out = text_of(path / "logs/log/dupes");
	for (const char *line :
	     { "save_left_out uid=1060 vnum=560 lost_by=player:42:0 held_by=destruction:0:0",
	       "save_left_out uid=1061 vnum=561 lost_by=player:42:0 held_by=destruction:0:0" })
		require(left_out.find(line) != std::string::npos,
			std::string("the dupe log names each destroyed item: ") + line + "\n" +
				left_out);
	// An identity written before it kept the character's own racewar holds the account
	// menu's immortal value (0) for an immortal. The load takes the snapshot's racewar
	// and the wallet and bank stored under it, instead of refusing the character.
	require(flatfile_identity_claim(root, 40, "Elder", "Account-Four", &error) ==
			flatfile_identity_result::ok,
		"elder identity claim: " + error);
	flatfile_identity_record elder;
	require(flatfile_identity_lookup_pid(root, 40, &elder, &error) ==
			flatfile_identity_result::ok,
		"elder identity lookup: " + error);
	elder.racewar = 1;
	elder.level = 62;
	require(flatfile_identity_sync_account(root, "Account-Four", { elder }, &error) ==
			flatfile_identity_result::ok,
		"elder identity racewar: " + error);
	player_snapshot elder_save = snapshot_for(1, 40, "Elder");
	for (auto &field : elder_save.status_integers)
		if (field.field == player_status_field::racewar)
			field.signed_value = 1;
		else if (field.field == player_status_field::copper)
			field.signed_value = field.unsigned_value = 77;
	require(flatfile_player_snapshot_apply(root, elder_save, &error).outcome ==
			player_save_apply_outcome::applied,
		"elder first save: " + error);
	elder.racewar = 0;
	require(flatfile_identity_sync_account(root, "Account-Four", { elder }, &error) ==
			flatfile_identity_result::ok,
		"elder legacy immortal identity: " + error);
	player_load_request elder_request = {};
	elder_request.request_id = 2;
	elder_request.pid = 40;
	elder_request.account_name = "Account-Four";
	const player_load_result elder_loaded =
		flatfile_player_load_repository_execute(root, elder_request);
	require(elder_loaded.outcome == player_load_outcome::applied &&
			elder_loaded.domains.wallet[0] == 77,
		std::string(
			"a legacy immortal identity must load with its own racewar's domains: ") +
			(elder_loaded.failed_component ? elder_loaded.failed_component : "none") +
			" outcome=" + std::to_string(static_cast<int>(elder_loaded.outcome)) +
			" error=" + std::to_string(elder_loaded.error_code) +
			" copper=" + std::to_string(elder_loaded.domains.wallet[0]));
	// The boot reap (work item #11). Player 42's file holds 1004 while its records still
	// name the bag, the room item in it, and the auction's bag with its contents from the
	// first save: nothing released them. Player 39's records name a bag and its contents
	// and a loose item its file never carried, beside the item it holds and the one its
	// legacy pet carries under its own identity. The pet's and the destroyed records are
	// not player 42's.
	const item_owner_identity reaped_player = { item_owner_type::player, 39, 0 };
	establish(root, reaped_player,
		  { { 1070, 1070, 0, 570 }, { 1071, 1070, 1070, 571 }, { 1074, 1074, 0, 574 } });
	require(flatfile_identity_claim(root, 39, "Dropper", "Account-Five", &error) ==
			flatfile_identity_result::ok,
		"dropper identity claim: " + error);
	player_snapshot dropper = snapshot_for(1, 39, "Dropper");
	dropper.items = { item(1072, 572, PLAYER_SNAPSHOT_NO_PARENT) };
	player_pet_snapshot legacy = {};
	legacy.mob_vnum = 700;
	legacy.room_vnum = 3001;
	legacy.items = { item(1073, 573, PLAYER_SNAPSHOT_NO_PARENT) };
	dropper.pets.push_back(legacy);
	require(flatfile_player_snapshot_apply(root, dropper, &error).outcome ==
			player_save_apply_outcome::applied,
		"dropper save: " + error);
	// Player 39 then took what other stores still carry, saved, let it go and saved
	// again: 1075 from the newcomer, whose file still holds it, and 1076, 1077 and 1078
	// from a corpse, a room and a guild locker that still list them (a crash came before
	// their next save). The records name player 39, and only they make each older copy
	// load as stale (MR !13 review, finding 1).
	player_snapshot newcomer_copy = snapshot_for(3, 41, "Newcomer");
	newcomer_copy.items = { item(1075, 575, PLAYER_SNAPSHOT_NO_PARENT) };
	require(flatfile_player_snapshot_apply(root, newcomer_copy, &error).outcome ==
			player_save_apply_outcome::applied,
		"newcomer save holding the hand-over: " + error);
	flatfile_corpse_record looted = dead;
	looted.save_id = 556;
	looted.items = { loose(1076, 576, PLAYER_SNAPSHOT_NO_PARENT) };
	require(flatfile_corpse_snapshot_apply(root, looted, false, {}, &error).outcome ==
			player_save_apply_outcome::applied,
		"looted corpse save: " + error);
	flatfile_saved_world_item_record left = chest;
	left.item_key = "item.uid.1077";
	left.items = { loose(1077, 577, PLAYER_SNAPSHOT_NO_PARENT) };
	require(flatfile_saved_item_snapshot_apply(root, left, false, &error).outcome ==
			player_save_apply_outcome::applied,
		"room item save: " + error);
	flatfile_locker_save guild_locker;
	guild_locker.locker_name = "guild.7.locker";
	guild_locker.owner_assoc_id = 7;
	guild_locker.items = { loose(1078, 578, PLAYER_SNAPSHOT_NO_PARENT) };
	require(flatfile_locker_snapshot_apply(root, guild_locker, &error).outcome ==
			player_save_apply_outcome::applied,
		"guild locker save: " + error);
	player_snapshot taken = snapshot_for(2, 39, "Dropper");
	taken.items = { item(1072, 572, PLAYER_SNAPSHOT_NO_PARENT),
			item(1075, 575, PLAYER_SNAPSHOT_NO_PARENT),
			item(1076, 576, PLAYER_SNAPSHOT_NO_PARENT),
			item(1077, 577, PLAYER_SNAPSHOT_NO_PARENT),
			item(1078, 578, PLAYER_SNAPSHOT_NO_PARENT) };
	taken.pets.push_back(legacy);
	player_snapshot let_go = snapshot_for(3, 39, "Dropper");
	let_go.items = dropper.items;
	let_go.pets.push_back(legacy);
	require(flatfile_player_snapshot_apply(root, taken, &error).outcome ==
				player_save_apply_outcome::applied &&
			flatfile_player_snapshot_apply(root, let_go, &error).outcome ==
				player_save_apply_outcome::applied,
		"dropper saves holding and then without the hand-overs: " + error);
	require(flatfile_world_item_list(root, &corpses, &saved_items, &error) ==
				flatfile_world_item_result::ok &&
			flatfile_world_item_list_rooms(root, &rooms, &error) ==
				flatfile_world_item_result::ok &&
			corpses.size() == 1 && corpses[0].items.size() == 1 &&
			corpses[0].items[0].object_uid == 1076 && rooms.size() == 1 &&
			rooms[0].items.size() == 1 && rooms[0].items[0].object_uid == 1077,
		"the corpse and the room still list what player 39 took");
	// A creation grant committed after player 39's last save: its next load delivers
	// 1079 from the materialization store, which only the record names it in (MR !13
	// review, finding 2).
	player_item_snapshot granted = item(1079, 579, PLAYER_SNAPSHOT_NO_PARENT);
	granted.name = granted.short_description = "a granted ring";
	item_transfer_payload grant = {};
	grant.from_owner = { item_owner_type::system, 0, 0 };
	grant.to_owner = reaped_player;
	std::vector<flatfile_item_ownership_record> ignored;
	require(flatfile_item_repository_load_owner(root, reaped_player,
						    &grant.expected_to_revision, &ignored,
						    &error) == flatfile_item_repository_result::ok,
		"player 39's revision: " + error);
	grant.reason = item_transfer_reason::creation;
	grant.reason_id = 297;
	grant.selected_item_uid = grant.target_root_item_uid = granted.object_uid;
	grant.item_count = 1;
	grant.items[0].item_uid = grant.items[0].root_item_uid = granted.object_uid;
	grant.items[0].expected_item_revision = ITEM_TRANSFER_ABSENT_REVISION;
	grant.items[0].vnum = granted.vnum;
	grant.items[0].expected_state = item_custody_state::absent;
	std::vector<uint8_t> blob;
	require(player_item_snapshot_list_encode({ granted }, &blob) ==
			player_snapshot_codec_result::ok,
		"encode the granted item");
	grant.item_blob_size = static_cast<uint32_t>(blob.size());
	std::copy(blob.begin(), blob.end(), grant.item_blob.begin());
	critical_operation_id operation;
	critical_command command;
	require(critical_operation_id_generate(&operation) &&
			item_transfer_command_build(&command, operation, grant,
						    critical_source_site::command,
						    critical_deadline_class::interactive),
		"build the grant");
	command.accepted_at_usec = 1;
	require(flatfile_item_repository_apply(root, command).outcome ==
			critical_apply_outcome::applied,
		"the grant commits");
	// A player file that cannot be read stops the reap: any record may be what keeps
	// an older copy in it out.
	const item_owner_identity unreadable = { item_owner_type::player, 38, 0 };
	establish(root, unreadable, { { 1080, 1080, 0, 580 } });
	const std::string unreadable_file = flatfile_player_snapshot_file::player_directory(root) +
					    "/" +
					    flatfile_player_snapshot_file::player_filename(38);
	{
		std::ofstream corrupt(unreadable_file);
		corrupt << "not a player file";
	}
	// The reap runs before each check, so the check's message sees its outcome.
	uint64_t reaped = 0;
	auto reap = flatfile_item_repository_reap_unheld_player_items(root, &reaped, &error);
	require(reap == flatfile_item_repository_result::invalid && reaped == 0 &&
			held_by(root, reaped_player).size() == 10 &&
			held_by(root, unreadable).size() == 1,
		"an unreadable player file stops the reap with nothing deleted: result=" +
			std::to_string(static_cast<int>(reap)) + " " + error);
	fs::remove(unreadable_file);
	// Without it, player 38 holds nothing.
	reap = flatfile_item_repository_reap_unheld_player_items(root, &reaped, &error);
	require(reap == flatfile_item_repository_result::ok && reaped == 8,
		"the reap deletes the eight stale records: " + std::to_string(reaped) + " " +
			error);
	const auto remaining = [&](const item_owner_identity &owner)
	{
		std::vector<uint64_t> kept;
		for (const auto &record : held_by(root, owner))
			kept.push_back(record.item_uid);
		std::sort(kept.begin(), kept.end());
		return kept;
	};
	require((remaining(player) == std::vector<uint64_t>{ 1004 }),
		"player 42 keeps the item its file holds");
	require((remaining(reaped_player) ==
		 std::vector<uint64_t>{ 1072, 1073, 1075, 1076, 1077, 1078, 1079 }),
		"player 39 keeps what it and its legacy pet hold, what older copies elsewhere "
		"carry, and the grant still to be delivered");
	require(remaining(unreadable).empty(), "a player without a file holds nothing");
	require(remaining(pet).size() == 1 && remaining(seller).empty() &&
			flatfile_item_repository_load_uids(root, { 1060, 1061 }, &destroyed,
							   &error) ==
				flatfile_item_repository_result::ok &&
			destroyed.size() == 2,
		"the pet's and the destroyed records are not touched");
	// World recovery restores a floor copy unless an owner holds it. A player's record
	// counts only while the player's next load holds the item, as MariaDB asks
	// player_items: 1075's record keeps the newcomer's copy out, but player 39 does not
	// hold it, so the floor copy is the one that comes back.
	std::unordered_set<uint64_t> owned;
	require(flatfile_item_repository_world_recovery_owned(
			root, { 1072, 1075, 1079, 1005, 1004, 1099 }, &owned, &error) ==
				flatfile_item_repository_result::ok &&
			(owned == std::unordered_set<uint64_t>{ 1072, 1079, 1005, 1004 }),
		"world recovery counts what a load holds as owned, and only that: " + error);
	// The kept records do their work at the next loads: the newcomer's copy is skipped
	// and the grant is delivered.
	request.request_id = 3;
	request.pid = 41;
	request.account_name = "Account-Two";
	const player_load_result newcomer_loaded =
		flatfile_player_load_repository_execute(root, request);
	require(newcomer_loaded.outcome == player_load_outcome::applied &&
			newcomer_loaded.snapshot.items.empty() &&
			text_of(path / "logs/log/dupes")
					.find("load_skipped uid=1075 vnum=575 lost_by=player:41:0 "
					      "held_by=player:39:0") != std::string::npos,
		"the newcomer's older copy is skipped");
	request.request_id = 4;
	request.pid = 39;
	request.account_name = "Account-Five";
	const player_load_result dropper_loaded =
		flatfile_player_load_repository_execute(root, request);
	require(dropper_loaded.outcome == player_load_outcome::applied &&
			std::any_of(dropper_loaded.snapshot.items.begin(),
				    dropper_loaded.snapshot.items.end(),
				    [](const player_item_snapshot &held)
				    { return held.object_uid == 1079; }),
		"player 39's load delivers the grant");
	// Once a save has carried the grant (retiring the delivery) and the ring is used up,
	// the next reap takes its record.
	player_snapshot with_ring = snapshot_for(4, 39, "Dropper");
	with_ring.items = { item(1072, 572, PLAYER_SNAPSHOT_NO_PARENT), granted };
	with_ring.pets.push_back(legacy);
	player_snapshot used_up = snapshot_for(5, 39, "Dropper");
	used_up.items = dropper.items;
	used_up.pets.push_back(legacy);
	require(flatfile_player_snapshot_apply(root, with_ring, &error).outcome ==
				player_save_apply_outcome::applied &&
			flatfile_player_snapshot_apply(root, used_up, &error).outcome ==
				player_save_apply_outcome::applied,
		"player 39 saves with the ring and then without it: " + error);
	reap = flatfile_item_repository_reap_unheld_player_items(root, &reaped, &error);
	require(reap == flatfile_item_repository_result::ok && reaped == 1 &&
			(remaining(reaped_player) ==
			 std::vector<uint64_t>{ 1072, 1073, 1075, 1076, 1077, 1078 }),
		"the used-up grant's record goes: " + std::to_string(reaped) + " " + error);
	reap = flatfile_item_repository_reap_unheld_player_items(root, &reaped, &error);
	require(reap == flatfile_item_repository_result::unchanged && reaped == 0,
		"a second reap finds nothing");
	std::cout << "flat-file player save claim passed\n";
	return 0;
}
