#include "flatfile/flatfile_artifact_repository.h"
#include "flatfile/flatfile_store.h"
#include "player/player_snapshot_codec.h"

#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <openssl/sha.h>
#include <string>
#include <vector>

namespace fs = std::filesystem;

static void require(bool condition, const std::string &message)
{
	if (!condition)
	{
		std::cerr << message << '\n';
		exit(1);
	}
}

static void prepare_root(const fs::path &root)
{
	fs::create_directories(root / "domains");
	fs::create_directories(root / "players");
	fs::create_directories(root / "identities/names");
	fs::permissions(root, fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(root / "domains", fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(root / "players", fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(root / "identities", fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(root / "identities/names", fs::perms::owner_all, fs::perm_options::replace);
}

static void set_transfer_item(item_transfer_payload *payload, int32_t vnum, bool artifact)
{
	require(payload != nullptr, "transfer payload is required");
	player_item_snapshot item = {};
	item.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	item.equipment_slot = -1;
	item.object_uid = 123;
	item.vnum = vnum;
	item.extra_flags = artifact ? 1U << 28 : 0;
	std::vector<uint8_t> encoded;
	require(player_item_snapshot_list_encode({ item }, &encoded) ==
				player_snapshot_codec_result::ok &&
			encoded.size() <= payload->item_blob.size(),
		"could not encode transfer item");
	payload->selected_item_uid = item.object_uid;
	payload->item_count = 1;
	payload->items[0].item_uid = item.object_uid;
	payload->items[0].vnum = item.vnum;
	payload->item_blob_size = static_cast<uint32_t>(encoded.size());
	std::copy(encoded.begin(), encoded.end(), payload->item_blob.begin());
}

static void identity_storage(const fs::path &root)
{
	prepare_root(root);
	std::string error;
	flatfile_artifact_record present = { 100,  false, FLATFILE_ARTIFACT_ON_NPC,
					     81,   0,	  1,
					     1000, -1,	  0,
					     1,	   123,	  artifact_identity_state::present };
	require(flatfile_artifact_establish(root.string(), { present }, &error) ==
			flatfile_artifact_result::ok,
		"unclaimed canonical artifact did not persist without a custody row");
	flatfile_artifact_record loaded;
	require(flatfile_artifact_get(root.string(), 100, &loaded, &error) ==
				flatfile_artifact_result::ok &&
			loaded == present,
		"canonical UID/state did not round trip");
	present.owned = true;
	present.location_type = FLATFILE_ARTIFACT_ON_PLAYER;
	present.location = 42;
	present.timer = 9000;
	present.last_update = 1001;
	present.bind_owner_pid = 42;
	present.bind_timer = 1002;
	require(flatfile_artifact_snapshot_apply(root.string(), { present }, &error) ==
				flatfile_artifact_result::ok &&
			flatfile_artifact_get(root.string(), 100, &loaded, &error) ==
				flatfile_artifact_result::ok &&
			loaded.canonical_item_uid == 123 &&
			loaded.identity_state == present.identity_state,
		"complete gameplay/soul capture erased canonical identity");

	const fs::path invalid_root = root.parent_path() / "invalid-identity";
	prepare_root(invalid_root);
	for (const auto state :
	     { artifact_identity_state::unresolved, artifact_identity_state::absent,
	       static_cast<artifact_identity_state>(4) })
	{
		auto invalid = present;
		invalid.identity_state = state;
		require(flatfile_artifact_establish(invalid_root.string(), { invalid }, &error) ==
				flatfile_artifact_result::invalid,
			"inconsistent UID/state was accepted");
	}
	auto duplicate = present;
	duplicate.vnum = 200;
	duplicate.identity_state = artifact_identity_state::retired;
	require(flatfile_artifact_establish(invalid_root.string(), { present, duplicate },
					    &error) == flatfile_artifact_result::invalid,
		"one physical UID became canonical for two artifact vnums");
	present.canonical_item_uid = 0;
	require(flatfile_artifact_establish(invalid_root.string(), { present }, &error) ==
			flatfile_artifact_result::invalid,
		"present artifact without a canonical UID was accepted");
	std::vector<flatfile_artifact_record> states;
	for (const auto state :
	     { artifact_identity_state::unresolved, artifact_identity_state::present,
	       artifact_identity_state::retired, artifact_identity_state::absent })
	{
		auto record = present;
		record.vnum += static_cast<int>(states.size());
		record.identity_state = state;
		record.canonical_item_uid =
			state == artifact_identity_state::present ||
					state == artifact_identity_state::retired ?
				record.vnum :
				0;
		record.identity_only = true;
		states.push_back(record);
		// Identical legacy metadata must remain distinguishable from the reservation.
		record.vnum += 1;
		if (record.canonical_item_uid)
			record.canonical_item_uid += 1;
		record.identity_only = false;
		states.push_back(record);
	}
	require(flatfile_artifact_establish(invalid_root.string(), states, &error) ==
			flatfile_artifact_result::ok,
		"valid unresolved/present/retired/absent states did not persist");
	std::vector<flatfile_artifact_record> roundtrip;
	require(flatfile_artifact_list(invalid_root.string(), &roundtrip, &error) ==
				flatfile_artifact_result::ok &&
			roundtrip == states,
		"identity states changed on reload");

	// Materialize the actual v1 wire shape: v2 added UID/state, v3 the marker.
	// Legacy bytes have no identity evidence and must never decode as absent.
	std::ifstream input(root / "domains/artifact_catalog", std::ios::binary);
	std::vector<uint8_t> legacy{ std::istreambuf_iterator<char>(input), {} };
	require(legacy.size() == 56 + 4 + 63 && legacy[8] == 3,
		"unexpected single-record artifact catalog wire shape");
	auto version_two = legacy;
	version_two.pop_back();
	version_two[8] = 2;
	const uint32_t v2_size = version_two.size() - 56;
	for (size_t byte = 0; byte < sizeof(v2_size); ++byte)
		version_two[12 + byte] = static_cast<uint8_t>(v2_size >> (byte * 8));
	SHA256(version_two.data() + 56, v2_size, version_two.data() + 24);
	const fs::path v2_root = root.parent_path() / "version-two-identity";
	prepare_root(v2_root);
	require(flatfile_atomic_write((v2_root / "domains").string(), "artifact_catalog",
				      version_two, &error),
		"could not write v2 artifact fixture");
	flatfile_artifact_record v2_record;
	require(flatfile_artifact_get(v2_root.string(), 100, &v2_record, &error) ==
				flatfile_artifact_result::ok &&
			v2_record == loaded && !v2_record.identity_only,
		"v2 identity or gameplay state changed");
	legacy.resize(legacy.size() - 10);
	legacy[8] = 1;
	const uint32_t payload_size = legacy.size() - 56;
	for (size_t byte = 0; byte < sizeof(payload_size); ++byte)
		legacy[12 + byte] = static_cast<uint8_t>(payload_size >> (byte * 8));
	SHA256(legacy.data() + 56, payload_size, legacy.data() + 24);
	const fs::path legacy_root = root.parent_path() / "legacy-identity";
	prepare_root(legacy_root);
	const fs::path filename = legacy_root / "domains/artifact_catalog";
	{
		std::ofstream output(filename, std::ios::binary);
		output.write(reinterpret_cast<const char *>(legacy.data()), legacy.size());
		require(output.good(), "could not write v1 artifact fixture");
	}
	fs::permissions(filename, fs::perms::owner_read | fs::perms::owner_write,
			fs::perm_options::replace);
	require(flatfile_artifact_get(legacy_root.string(), 100, &present, &error) ==
				flatfile_artifact_result::ok &&
			!present.canonical_item_uid &&
			present.identity_state == artifact_identity_state::unresolved &&
			present.timer == loaded.timer &&
			present.bind_owner_pid == loaded.bind_owner_pid,
		"v1 catalog invented identity or lost timer/soul evidence");
	present.timer = 9100;
	require(flatfile_artifact_snapshot_apply(legacy_root.string(), { present }, &error) ==
				flatfile_artifact_result::ok &&
			flatfile_artifact_get(legacy_root.string(), 100, &present, &error) ==
				flatfile_artifact_result::ok &&
			present.timer == 9100 && !present.canonical_item_uid &&
			present.identity_state == artifact_identity_state::unresolved,
		"v1 rewrite lost state or promoted unresolved identity");
}

static void snapshot_captures(const fs::path &root)
{
	prepare_root(root);
	std::string error;
	const flatfile_artifact_record first = { 100, true, FLATFILE_ARTIFACT_ON_PLAYER,
						 42,  1000, 1,
						 100, 42,   50,
						 99,  111,  artifact_identity_state::present };
	const flatfile_artifact_record other = { 300, true, FLATFILE_ARTIFACT_ON_PLAYER,
						 77,  2000, 2,
						 100, 77,   50,
						 7,   222,  artifact_identity_state::present };
	require(flatfile_artifact_snapshot_apply(root.string(), { first }, &error) ==
			flatfile_artifact_result::not_found,
		"capture synthesized a missing artifact catalog");
	require(flatfile_artifact_establish(root.string(), { first, other }, &error) ==
			flatfile_artifact_result::ok,
		"capture fixture establishment failed");
	auto changed = first;
	changed.timer = 1600;
	changed.location = changed.bind_owner_pid = 88;
	changed.bind_timer = 90;
	changed.revision = 0;
	auto conflict = other;
	conflict.vnum = 200;
	require(flatfile_artifact_snapshot_apply(root.string(), { changed, conflict }, &error) ==
			flatfile_artifact_result::conflict,
		"capture reassigned an unchanged artifact's canonical UID");
	flatfile_artifact_record stored;
	require(flatfile_artifact_get(root.string(), 100, &stored, &error) ==
				flatfile_artifact_result::ok &&
			stored == first &&
			flatfile_artifact_get(root.string(), 200, &stored, &error) ==
				flatfile_artifact_result::not_found,
		"refused multi-artifact capture partially changed the catalog");
	require(flatfile_artifact_snapshot_apply(root.string(), { first, changed }, &error) ==
			flatfile_artifact_result::invalid,
		"capture chose between repeated vnum entries");
	auto second = other;
	second.timer = 2600;
	require(flatfile_artifact_snapshot_apply(root.string(), { second, changed }, &error) ==
			flatfile_artifact_result::ok,
		"complete multi-artifact capture failed");
	changed.revision = first.revision + 1;
	second.revision = other.revision + 1;
	std::vector<flatfile_artifact_record> records;
	require(flatfile_artifact_list(root.string(), &records, &error) ==
				flatfile_artifact_result::ok &&
			records == std::vector<flatfile_artifact_record>{ changed, second },
		"capture lost UID/timer/soul data or record revision ordering");
	require(flatfile_artifact_snapshot_apply(root.string(), { changed, second }, &error) ==
				flatfile_artifact_result::unchanged &&
			flatfile_artifact_list(root.string(), &records, &error) ==
				flatfile_artifact_result::ok &&
			records[0] == changed && records[1] == second,
		"capture replay changed stored state or revisions");
	changed.owned = false;
	changed.location_type = FLATFILE_ARTIFACT_NOT_IN_GAME;
	changed.identity_state = artifact_identity_state::retired;
	require(flatfile_artifact_snapshot_apply(root.string(), { changed }, &error) ==
				flatfile_artifact_result::ok &&
			flatfile_artifact_get(root.string(), 100, &stored, &error) ==
				flatfile_artifact_result::ok &&
			stored.canonical_item_uid == 111 &&
			stored.identity_state == artifact_identity_state::retired,
		"capture lost a retired UID tombstone");
}

int main(int argc, char **argv)
{
	require(argc == 2, "state root argument required");
	identity_storage(fs::path(argv[1]) / "identity");
	snapshot_captures(fs::path(argv[1]) / "captures");
	const fs::path root = fs::path(argv[1]) / "release";
	prepare_root(root);
	std::string error;
	std::vector<flatfile_artifact_record> records;
	require(flatfile_artifact_list(root.string(), &records, &error) ==
			flatfile_artifact_result::not_found,
		"missing artifact authority did not fail closed");
	const fs::path ensure_root = fs::path(argv[1]) / "ensure";
	prepare_root(ensure_root);
	require(flatfile_artifact_ensure(ensure_root.string(), &error) ==
			flatfile_artifact_result::ok,
		"fresh artifact catalog ensure failed: " + error);
	require(flatfile_artifact_list(ensure_root.string(), &records, &error) ==
				flatfile_artifact_result::ok &&
			records.empty(),
		"fresh artifact catalog was not established empty");
	require(flatfile_artifact_snapshot_apply(
			ensure_root.string(),
			{ { 99, true, FLATFILE_ARTIFACT_ON_GROUND, 1200, 5000, 1, 1000, 0, 0, 0 } },
			&error) == flatfile_artifact_result::ok,
		"ensured catalog did not accept its first artifact capture");
	require(flatfile_artifact_ensure(ensure_root.string(), &error) ==
			flatfile_artifact_result::already_exists,
		"existing artifact catalog was not recognized by ensure");
	require(flatfile_artifact_list(ensure_root.string(), &records, &error) ==
				flatfile_artifact_result::ok &&
			records.size() == 1 && records[0].vnum == 99,
		"artifact ensure replaced an existing nonempty catalog");
	const flatfile_artifact_record held = {
		100, true, FLATFILE_ARTIFACT_ON_PLAYER, 42, 9000, 1, 1000, 42, 8000, 5
	};
	const flatfile_artifact_record bound = {
		200, false, FLATFILE_ARTIFACT_ON_GROUND, 1201, 0, 2, 1001, 42, 7000, 7
	};
	const flatfile_artifact_record untouched = {
		300, true, FLATFILE_ARTIFACT_ON_NPC, 81, 6000, 3, 1002, -1, 0, 2
	};
	require(flatfile_artifact_establish(root.string(), { untouched, held, bound }, &error) ==
			flatfile_artifact_result::ok,
		"artifact establishment failed: " + error);
	require(flatfile_artifact_establish(root.string(), { bound, untouched, held }, &error) ==
			flatfile_artifact_result::already_exists,
		"exact artifact establishment retry was not idempotent");
	auto conflicting = held;
	conflicting.timer++;
	require(flatfile_artifact_establish(root.string(), { conflicting }, &error) ==
			flatfile_artifact_result::invalid,
		"conflicting artifact establishment was accepted");
	require(flatfile_artifact_list(root.string(), &records, &error) ==
				flatfile_artifact_result::ok &&
			records == std::vector<flatfile_artifact_record>{ held, bound, untouched },
		"artifact catalog was not canonical or did not round trip");
	{
		flatfile_authority_lock lock;
		require(lock.acquire(root.string(), &error),
			"could not acquire artifact authority");
		flatfile_authority_operation operation;
		require(flatfile_artifact_prepare_player_release(root.string(), lock, 99,
								 &operation, &error) ==
				flatfile_artifact_result::unchanged,
			"unreferenced player did not produce an unchanged artifact result");
		require(flatfile_artifact_prepare_player_release(root.string(), lock, 42,
								 &operation, &error) ==
					flatfile_artifact_result::ok &&
				operation.store == flatfile_authority_store::domains &&
				operation.kind == flatfile_authority_operation_kind::write &&
				operation.filename == "artifact_catalog",
			"player artifact release did not prepare a catalog image");
		require(flatfile_authority_transaction_commit_operations(root.string(), lock,
									 { operation }, &error) ==
				flatfile_authority_transaction_result::ok,
			"artifact release transaction failed: " + error);
	}
	require(flatfile_artifact_list(root.string(), &records, &error) ==
				flatfile_artifact_result::ok &&
			records.size() == 3 && !records[0].owned &&
			records[0].location_type == FLATFILE_ARTIFACT_NOT_IN_GAME &&
			records[0].location == 0 && records[0].timer == 0 &&
			records[0].bind_owner_pid == -1 && records[0].bind_timer == 0 &&
			records[0].revision == 6 &&
			records[1].location_type == FLATFILE_ARTIFACT_ON_GROUND &&
			records[1].location == 1201 && records[1].bind_owner_pid == -1 &&
			records[1].bind_timer == 0 && records[1].revision == 8 &&
			records[2] == untouched,
		"artifact release did not preserve and rewrite the expected fields");
	{
		flatfile_authority_lock lock;
		require(lock.acquire(root.string(), &error),
			"could not reacquire artifact authority");
		flatfile_authority_operation operation;
		require(flatfile_artifact_prepare_player_release(root.string(), lock, 42,
								 &operation, &error) ==
				flatfile_artifact_result::unchanged,
			"artifact release retry was not idempotent");
	}

	const flatfile_artifact_record corpse = {
		400, true, FLATFILE_ARTIFACT_ON_CORPSE, 42, 5000, 1, 1003, 42, 4000, 1
	};
	// A grant cannot create an artifact in a room; a repair within one changes nothing.
	item_transfer_payload room_grant = {};
	room_grant.from_owner = { item_owner_type::system, 0, 0 };
	room_grant.to_owner = { item_owner_type::room, 9001, 0 };
	room_grant.reason = item_transfer_reason::creation;
	set_transfer_item(&room_grant, 500, false);
	require(flatfile_artifact_room_transfer_allowed(room_grant),
		"an ordinary room grant was refused");
	set_transfer_item(&room_grant, 500, true);
	require(!flatfile_artifact_room_transfer_allowed(room_grant),
		"a room grant created an artifact");
	item_transfer_payload room_repair = room_grant;
	room_repair.from_owner = room_grant.to_owner;
	room_repair.reason = item_transfer_reason::operator_repair;
	require(flatfile_artifact_room_transfer_allowed(room_repair),
		"a same-room artifact repair was refused");

	const fs::path corpse_root = fs::path(argv[1]) / "corpse";
	prepare_root(corpse_root);
	require(flatfile_artifact_establish(corpse_root.string(), { corpse }, &error) ==
			flatfile_artifact_result::ok,
		"corpse artifact establishment failed");
	{
		flatfile_authority_lock lock;
		require(lock.acquire(corpse_root.string(), &error),
			"could not acquire corpse artifact authority");
		flatfile_authority_operation operation;
		require(flatfile_artifact_prepare_player_release(corpse_root.string(), lock, 42,
								 &operation, &error) ==
					flatfile_artifact_result::ok &&
				operation.filename == "artifact_catalog",
			"corpse-held artifact release was not prepared");
		require(flatfile_authority_transaction_commit_operations(corpse_root.string(), lock,
									 { operation }, &error) ==
				flatfile_authority_transaction_result::ok,
			"corpse-held artifact release failed: " + error);
	}
	require(flatfile_artifact_list(corpse_root.string(), &records, &error) ==
				flatfile_artifact_result::ok &&
			records.size() == 1 && !records[0].owned &&
			records[0].location_type == FLATFILE_ARTIFACT_NOT_IN_GAME &&
			records[0].location == 0 && records[0].timer == 0 &&
			records[0].bind_owner_pid == -1 && records[0].bind_timer == 0 &&
			records[0].revision == 2,
		"corpse-held artifact was not released with player deletion semantics");

	const fs::path catalog = root / "domains/artifact_catalog";
	{
		std::fstream file(catalog, std::ios::in | std::ios::out | std::ios::binary);
		require(file.good(), "could not open artifact catalog for corruption");
		file.seekg(-1, std::ios::end);
		char byte = 0;
		file.read(&byte, 1);
		byte ^= 0x5a;
		file.seekp(-1, std::ios::end);
		file.write(&byte, 1);
	}
	require(flatfile_artifact_list(root.string(), &records, &error) ==
			flatfile_artifact_result::invalid,
		"corrupt artifact authority was exposed");
	flatfile_artifact_record corrupt_record;
	require(flatfile_artifact_get(root.string(), 100, &corrupt_record, &error) ==
			flatfile_artifact_result::invalid,
		"corrupt artifact authority was exposed through lookup");
	require(flatfile_artifact_snapshot_apply(root.string(), { held }, &error) ==
			flatfile_artifact_result::invalid,
		"corrupt artifact authority was overwritten through capture");
	require(flatfile_artifact_ensure(root.string(), &error) ==
			flatfile_artifact_result::invalid,
		"artifact ensure accepted or overwrote corrupt authority");

	{
		flatfile_authority_lock lock;
		require(lock.acquire(root.string(), &error),
			"could not acquire corrupt artifact authority");
		flatfile_authority_operation operation;
		require(flatfile_artifact_prepare_player_release(root.string(), lock, 42,
								 &operation, &error) ==
				flatfile_artifact_result::invalid,
			"corrupt artifact authority was accepted for deletion");
	}
	std::cout << "flat-file artifact repository passed\n";
	return 0;
}
