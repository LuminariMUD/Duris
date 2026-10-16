#include "guild/artifact_population_flatfile.c"
#include "flatfile/flatfile_store.h"
#include "flatfile/flatfile_player_domain_repository.h"
#include "player/player_snapshot_codec.h"
#include "core/files.h"

#include <cassert>
#include <fstream>
#include <iostream>
#include <openssl/sha.h>

namespace fs = std::filesystem;

static void prepare(const fs::path &root)
{
	for (const auto &name : { "", "domains", "players", "identities", "identities/names" })
	{
		fs::create_directories(root / name);
		fs::permissions(root / name, fs::perms::owner_all, fs::perm_options::replace);
	}
}

static player_item_snapshot item(uint64_t uid, int parent = PLAYER_SNAPSHOT_NO_PARENT,
				 bool artifact = true)
{
	player_item_snapshot object = {};
	object.object_uid = uid;
	object.vnum = artifact ? 900 : 901;
	object.extra_flags = artifact ? 1U << 28 : 0;
	object.equipment_slot = -1;
	object.parent_index = parent;
	return object;
}

// Publish valid player-file fixtures through the public snapshot codec and file
// envelope contract, without performing claims that would hide conflicting input.
static void player_file(const fs::path &root, const player_snapshot &snapshot)
{
	std::vector<uint8_t> payload;
	assert(player_snapshot_encode(snapshot, &payload) == player_snapshot_codec_result::ok);
	std::vector<uint8_t> bytes(flatfile_player_snapshot_file::player_magic.begin(),
				   flatfile_player_snapshot_file::player_magic.end());
	const auto append = [&bytes]<typename T>(T value)
	{
		for (size_t byte = 0; byte < sizeof(T); ++byte)
			bytes.push_back(
				static_cast<uint8_t>(static_cast<uint64_t>(value) >> (8 * byte)));
	};
	append(flatfile_player_snapshot_file::player_file_version);
	append(static_cast<uint32_t>(payload.size()));
	append(snapshot.pid);
	append(snapshot.revision);
	append(snapshot.components);
	unsigned char digest[SHA256_DIGEST_LENGTH];
	SHA256(payload.data(), payload.size(), digest);
	bytes.insert(bytes.end(), digest, digest + sizeof(digest));
	bytes.insert(bytes.end(), payload.begin(), payload.end());
	std::string error;
	assert(flatfile_atomic_write((root / "players").string(),
				     flatfile_player_snapshot_file::player_filename(snapshot.pid),
				     bytes, &error));
}

static const artifact_payload_projection &find(const std::vector<artifact_payload_projection> &rows,
					       uint64_t uid, artifact_payload_domain domain,
					       int64_t owner_reference)
{
	const auto found = std::find_if(rows.begin(), rows.end(),
					[&](const auto &row) {
						return row.item_uid == uid &&
						       row.domain == domain &&
						       row.owner_reference == owner_reference;
					});
	assert(found != rows.end());
	return *found;
}

static critical_operation_id operation(uint8_t tag)
{
	critical_operation_id id = {};
	id.bytes[0] = 0xab;
	id.bytes.back() = tag;
	return id;
}

static auction_command_result auction_apply(const std::string &root,
					    const auction_command_payload &payload, uint8_t tag)
{
	critical_command command = {};
	assert(auction_command_build(&command, operation(tag), payload,
				     critical_source_site::command,
				     critical_deadline_class::interactive));
	command.accepted_at_usec = tag;
	const auto applied = flatfile_auction_repository_apply(root, command);
	assert(applied.outcome == critical_apply_outcome::applied);
	auction_command_result result;
	assert(auction_command_decode_result(applied.result_payload.data(), applied.result_size,
					     &result));
	return result;
}

static collector_command_result
collector_apply(const std::string &root, const collector_command_payload &payload, uint8_t tag)
{
	critical_command command = {};
	assert(collector_command_build(&command, operation(tag), payload,
				       critical_source_site::zone_event,
				       critical_deadline_class::background));
	command.accepted_at_usec = tag;
	const auto applied = flatfile_collector_repository_apply(root, command);
	assert(applied.outcome == critical_apply_outcome::applied);
	collector_command_result result;
	assert(collector_command_decode_result(applied.result_payload.data(), applied.result_size,
					       &result));
	return result;
}

static std::vector<uint8_t> encode_items(std::vector<player_item_snapshot> objects)
{
	std::vector<uint8_t> bytes;
	assert(player_item_snapshot_list_encode(objects, &bytes) ==
	       player_snapshot_codec_result::ok);
	return bytes;
}

static void seed_blobs(const std::string &root, std::string *error)
{
	flatfile_player_domain_record player;
	player.pid = 99;
	player.account_name = "auction-fixture";
	player.racewar = 1;
	assert(flatfile_player_domain_establish(root, player, error) ==
	       flatfile_player_domain_result::ok);
	const item_owner_identity seller = { item_owner_type::player, 99, 0 };
	assert(flatfile_item_repository_establish_owner(
		       root, seller,
		       { { 701, 701, 0, seller, 1, 900, item_custody_state::active },
			 { 702, 702, 0, seller, 1, 900, item_custody_state::active } },
		       error) == flatfile_item_baseline_result::applied);
	std::vector<uint8_t> blob;
	const auto native = [&blob]<typename T>(T value)
	{
		const auto *data = reinterpret_cast<const uint8_t *>(&value);
		blob.insert(blob.end(), data, data + sizeof(value));
	};
	native(static_cast<uint8_t>(SAV_ITEMVERS));
	native(uint32_t{ 1 });
	native(static_cast<uint8_t>(O_F_UNIQUE));
	native(int32_t{ 900 });
	native(uint16_t{ 0 });
	native(uint16_t{ 100 });
	native(static_cast<uint32_t>(O_U_EXTRA));
	native(uint32_t{ 1U << 28 });
	native(static_cast<uint8_t>(O_F_EOL));
	native(uint8_t{ 0 });
	auction_command_payload listing = {};
	listing.action = auction_action::list;
	listing.actor_pid = 99;
	listing.racewar = 1;
	listing.expected_bank_revision = 1;
	strcpy(listing.account_name.data(), "auction-fixture");
	strcpy(listing.actor_name.data(), "AuctionFixture");
	strcpy(listing.object_short.data(), "legacy artifact");
	strcpy(listing.id_keywords.data(), "legacy artifact");
	listing.start_price = 1;
	listing.end_time = static_cast<uint64_t>(time(nullptr)) + 3600;
	listing.item_count = 2;
	listing.items[0] = { 701, 1, 900 };
	listing.items[1] = { 702, 1, 900 };
	listing.object_blob_size = blob.size();
	std::copy(blob.begin(), blob.end(), listing.object_blob.begin());
	const auto listed = auction_apply(root, listing, 1);
	auction_command_payload remove = {};
	remove.action = auction_action::remove;
	remove.auction_id = listed.auction_id;
	auction_apply(root, remove, 2);
	auction_command_payload claim = listing;
	claim.action = auction_action::claim_item;
	claim.auction_id = listed.auction_id;
	claim.item_count = 1;
	claim.items[0].expected_item_revision = listed.item_revisions[0];
	auction_apply(root, claim, 3);
	std::vector<flatfile_auction_listing_projection> retained;
	assert(flatfile_auction_list_retained(root, &retained, error) ==
	       flatfile_auction_query_result::ok);
	assert(retained.size() == 1 && retained[0].status == 3 && retained[0].items.size() == 2 &&
	       retained[0].items[0].claimed && !retained[0].items[1].claimed);

	for (unsigned int index = 0; index < 2; ++index)
	{
		const uint32_t pid = 55 + index;
		const uint64_t uid = 901 + index;
		const item_owner_identity owner = { item_owner_type::player, pid, 0 };
		if (!index)
			assert(flatfile_item_repository_establish_owner(
				       root, owner,
				       { { uid, uid, 0, owner, 1, 900,
					   item_custody_state::active } },
				       error) == flatfile_item_baseline_result::applied);
		shop_trade_payload delivery = {};
		delivery.action = index ? shop_trade_action::sell_store :
					  shop_trade_action::buy_produced;
		delivery.player_pid = pid;
		delivery.selected_item_uid = uid;
		delivery.item_count = 1;
		delivery.items[0] = { uid, uid, 0, 0, 900, item_custody_state::absent };
		const auto bytes = encode_items({ item(uid) });
		delivery.item_blob_size = bytes.size();
		std::copy(bytes.begin(), bytes.end(), delivery.item_blob.begin());
		flatfile_authority_lock lock;
		assert(lock.acquire(root, error));
		flatfile_shop_trade_materialization_mutation mutation;
		assert(flatfile_shop_trade_materialization_prepare(
			       root, lock, operation(10 + index), delivery, &mutation, error) ==
		       flatfile_shop_trade_materialization_result::ok);
		assert(flatfile_authority_transaction_commit(root, lock, { mutation.after_image },
							     error) ==
		       flatfile_authority_transaction_result::ok);
	}
	const item_owner_identity raised_owner = { item_owner_type::pet, 7777, 57 };
	assert(flatfile_item_repository_establish_owner(
		       root, raised_owner,
		       { { 903, 903, 0, raised_owner, 1, 900, item_custody_state::active },
			 { 904, 904, 0, raised_owner, 1, 900, item_custody_state::active } },
		       error) == flatfile_item_baseline_result::applied);
	for (unsigned int index = 0; index < 2; ++index)
	{
		const uint64_t uid = 903 + index;
		const auto objects = encode_items({ item(uid) });
		std::vector<uint8_t> bytes;
		if (!index)
		{
			bytes = { 'P', 'E', 'T', '1' };
			const auto append = [&bytes]<typename T>(T value)
			{
				for (size_t byte = 0; byte < sizeof(T); ++byte)
					bytes.push_back(static_cast<uint8_t>(
						static_cast<uint64_t>(value) >> (8 * byte)));
			};
			append(uint64_t{ 7777 });
			for (int32_t value : { 100, 1, 10, 0, 5, 0, 5, 10, 2300 })
				append(value);
			append(uint32_t{ 0 }); // empty retained pet-state text
			append(static_cast<uint32_t>(objects.size()));
			bytes.insert(bytes.end(), objects.begin(), objects.end());
		}
		else
			bytes = objects;
		shop_trade_payload delivery = {};
		// Native receipt actions 6/7 are raised-pet and pet-receive envelopes.
		delivery.action = static_cast<shop_trade_action>(6 + index);
		delivery.player_pid = 57;
		delivery.selected_item_uid = uid;
		delivery.item_count = 1;
		delivery.items[0] = { uid, uid, 0, 1, 900, item_custody_state::active };
		delivery.item_blob_size = bytes.size();
		std::copy(bytes.begin(), bytes.end(), delivery.item_blob.begin());
		flatfile_authority_lock lock;
		assert(lock.acquire(root, error));
		flatfile_shop_trade_materialization_mutation mutation;
		assert(flatfile_shop_trade_materialization_prepare(
			       root, lock, operation(15 + index), delivery, &mutation, error) ==
		       flatfile_shop_trade_materialization_result::ok);
		assert(flatfile_authority_transaction_commit(root, lock, { mutation.after_image },
							     error) ==
		       flatfile_authority_transaction_result::ok);
	}

	for (unsigned int index = 0; index < 2; ++index)
	{
		const item_owner_identity owner = { item_owner_type::player, 60 + index, 0 };
		auto coin = item(905 + index);
		coin.vnum = 3;
		coin.type = ITEM_MONEY;
		flatfile_item_ownership_record legacy = { coin.object_uid,
							  coin.object_uid,
							  0,
							  owner,
							  1,
							  coin.vnum,
							  item_custody_state::active,
							  encode_items({ coin }) };
		assert(flatfile_item_repository_establish_owner(root, owner, { legacy }, error) ==
		       flatfile_item_baseline_result::applied);
		if (index)
		{
			flatfile_authority_lock lock;
			assert(lock.acquire(root, error));
			flatfile_authority_operation removal;
			assert(flatfile_item_repository_prepare_player_remove(root, lock, 61,
									      &removal, error) ==
			       flatfile_item_repository_result::ok);
			assert(flatfile_authority_transaction_commit_operations(
				       root, lock, { removal }, error) ==
			       flatfile_authority_transaction_result::ok);
		}
	}
	const item_owner_identity dead = { item_owner_type::corpse, item_corpse_owner_id(66, 10),
					   0 };
	assert(flatfile_item_repository_establish_owner(
		       root, dead, { { 801, 801, 0, dead, 1, 900, item_custody_state::active } },
		       error) == flatfile_item_baseline_result::applied);
	flatfile_corpse_record corpse;
	corpse.owner_pid = 66;
	corpse.owner_name = "collector-fixture";
	corpse.save_id = 10;
	corpse.room_vnum = 2300;
	corpse.revision = 1;
	auto antique = item(801);
	antique.extra_flags = 0;
	antique.type = ITEM_WEAPON;
	antique.wear_flags = ITEM_TAKE;
	antique.weight = 1;
	antique.cost = 1000;
	antique.condition = 100;
	corpse.items = { antique };
	{
		flatfile_authority_lock lock;
		assert(lock.acquire(root, error));
		flatfile_authority_operation body;
		assert(flatfile_world_item_prepare_corpse_snapshot(root, lock, corpse, false, &body,
								   error) ==
		       flatfile_world_item_result::ok);
		collector_death_snapshot death;
		death.operation_id = operation(20);
		death.beneficiary_pid = 66;
		death.death_time = 1000;
		death.policy = { true, 10, 20, 100, 200, 100 };
		flatfile_collector_enrollment_mutation mutation;
		unsigned int result_code = 0;
		assert(flatfile_collector_prepare_death_enrollment(
			       root, lock, death, { 801 }, &mutation, &result_code, error) ==
			       flatfile_collector_repository_result::ok &&
		       !result_code);
		assert(flatfile_authority_transaction_commit_operations(
			       root, lock,
			       { body,
				 { flatfile_authority_store::domains,
				   flatfile_authority_operation_kind::write,
				   mutation.after_image.filename, mutation.after_image.bytes } },
			       error) == flatfile_authority_transaction_result::ok);
	}
	collector_listing_detail detail;
	bool found = false;
	assert(flatfile_collector_repository_read_listing(root, 1, &detail, &found, error) ==
		       flatfile_collector_repository_result::ok &&
	       found);
	collector_command_payload collect = {};
	collect.action = collector_action::collect;
	collect.target_state = item_custody_state::active;
	collect.listing = 1;
	collect.expected_listing_revision = detail.entry.revision;
	collect.observed_at = 1010;
	collect.from_owner = dead;
	collect.to_owner = { item_owner_type::collector, 1, 0 };
	collect.expected_from_owner_revision = 1;
	collect.selected_item_uid = 801;
	collect.item_count = 1;
	collect.items[0] = { 801, 801, 0, 1, 900, item_custody_state::active };
	antique.equipment_slot = 0;
	const auto bytes = encode_items({ antique });
	collect.item_blob_size = bytes.size();
	std::copy(bytes.begin(), bytes.end(), collect.item_blob.begin());
	collector_apply(root, collect, 21);
	std::vector<artifact_payload_projection> rows;
	assert(!artifact_population_read_flat_payloads(root, &rows, error));
	for (const auto &row : rows)
		assert(row.custody_examined);
	assert(find(rows, 801, artifact_payload_domain::collector, 66).role ==
	       artifact_payload_role::stored);
	assert(find(rows, 801, artifact_payload_domain::collector, 66).source_operation.bytes ==
	       operation(20).bytes);
	collector_command_payload activate = {};
	activate.action = collector_action::activate;
	activate.listing = 1;
	activate.expected_listing_revision = 2;
	activate.observed_at = 1020;
	const auto available = collector_apply(root, activate, 22);
	assert(available.entry.expires_at > 0);
	assert(flatfile_collector_repository_read_listing(root, 1, &detail, &found, error) ==
		       flatfile_collector_repository_result::ok &&
	       found);
	collector_command_payload expire = {};
	expire.action = collector_action::expire;
	expire.listing = 1;
	expire.expected_listing_revision = detail.entry.revision;
	expire.observed_at = available.entry.expires_at;
	expire.from_owner = { item_owner_type::collector, 1, 0 };
	expire.to_owner = { item_owner_type::destruction, 0, 0 };
	expire.target_state = item_custody_state::destroyed;
	std::vector<flatfile_item_ownership_record> held, destroyed;
	assert(flatfile_item_repository_load_owner(root, expire.from_owner,
						   &expire.expected_from_owner_revision, &held,
						   error) == flatfile_item_repository_result::ok);
	assert(flatfile_item_repository_load_owner(root, expire.to_owner,
						   &expire.expected_to_owner_revision, &destroyed,
						   error) == flatfile_item_repository_result::ok);
	assert(held.size() == 1);
	expire.selected_item_uid = 801;
	expire.item_count = 1;
	expire.items[0] = { held[0].item_uid,	   held[0].root_item_uid, held[0].parent_item_uid,
			    held[0].item_revision, held[0].vnum,	  held[0].state };
	expire.item_blob_size = detail.item_blob.size();
	std::copy(detail.item_blob.begin(), detail.item_blob.end(), expire.item_blob.begin());
	collector_apply(root, expire, 23);

	// A valid catalog can still hold an opaque malformed legacy blob. Refuse its
	// aggregate scan after other stores were staged, without publishing that prefix.
	const fs::path catalog = fs::path(root) / "domains/auction_catalog";
	std::ifstream input(catalog, std::ios::binary);
	const std::vector<uint8_t> healthy{ std::istreambuf_iterator<char>(input), {} };
	assert(!healthy.empty());
	player.pid = 100;
	player.account_name = "malformed-fixture";
	assert(flatfile_player_domain_establish(root, player, error) ==
	       flatfile_player_domain_result::ok);
	const item_owner_identity malformed_owner = { item_owner_type::player, 100, 0 };
	assert(flatfile_item_repository_establish_owner(
		       root, malformed_owner,
		       { { 703, 703, 0, malformed_owner, 1, 900, item_custody_state::active } },
		       error) == flatfile_item_baseline_result::applied);
	auction_command_payload malformed = listing;
	malformed.actor_pid = 100;
	strcpy(malformed.account_name.data(), "malformed-fixture");
	strcpy(malformed.actor_name.data(), "MalformedFixture");
	malformed.item_count = 1;
	malformed.items[0] = { 703, 1, 900 };
	malformed.object_blob[0] = SAV_ITEMVERS + 1;
	auction_apply(root, malformed, 60);
	assert(!rows.empty());
	const auto *retained_rows = rows.data();
	const auto retained_count = rows.size();
	assert(artifact_population_read_flat_payloads(root, &rows, error) == EINVAL);
	assert(rows.data() == retained_rows && rows.size() == retained_count);
	assert(flatfile_atomic_write(catalog.parent_path().string(), catalog.filename().string(),
				     healthy, error));
}

int main(int argc, char **argv)
{
	assert(argc == 2);
	const fs::path root = argv[1];
	prepare(root);
	std::string error;
	std::vector<artifact_payload_projection> rows;
	assert(!artifact_population_read_flat_payloads(root.string(), &rows, &error) &&
	       rows.empty());
	player_snapshot player = {};
	player.pid = 42;
	player.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
	player.revision = 1;
	player.components = PLAYER_CHECKPOINT_COMPONENT_ALL;
	player.encoded_size_bound = PLAYER_SNAPSHOT_MAX_BYTES;
	player.items = { item(101, -1, false), item(102, 0) };
	player_pet_snapshot pet = {};
	pet.pet_uid = 700;
	pet.mob_vnum = 100;
	pet.items = { item(103) };
	player.pets.push_back(pet);
	pet.pet_uid = 0;
	pet.order = 1;
	pet.items = { item(0), item(104, 0) };
	player.pets.push_back(pet);
	player_file(root, player);
	player.pid = 43;
	player.items = { item(102) };
	player.pets.clear();
	player_file(root, player);

	flatfile_locker_chest_record chest;
	chest.chest_id = 11;
	chest.chest_name = "public";
	chest.is_public = true;
	chest.revision = 1;
	chest.items = { item(201) };
	flatfile_locker_record locker;
	locker.locker_id = 1;
	locker.locker_name = "fixture";
	locker.owner_pid = 42;
	locker.revision = 1;
	locker.chests.push_back(chest);
	chest.chest_id = 12;
	chest.chest_name = "private";
	chest.is_public = false;
	chest.items = { item(202) };
	locker.chests.push_back(chest);
	flatfile_locker_record account = locker;
	account.locker_id = 2;
	account.locker_name = "account.fixture.1.locker";
	account.owner_pid = 0;
	account.racewar = 1;
	account.account_owner = flatfile_account_locker_identity{ "fixture", 1 };
	chest.chest_id = 21;
	chest.chest_name = "public";
	chest.is_public = true;
	chest.items = { item(203) };
	account.chests = { chest };
	assert(flatfile_locker_establish(root.string(), { locker, account }, {}, &error) ==
	       flatfile_locker_result::ok);
	flatfile_corpse_record corpse;
	corpse.owner_pid = 42;
	corpse.owner_name = "fixture";
	corpse.save_id = 9;
	corpse.room_vnum = 2300;
	corpse.revision = 1;
	corpse.items = { item(301, -1, false), item(302, 0) };
	flatfile_saved_world_item_record saved;
	saved.item_key = "saved.fixture";
	saved.room_vnum = 2400;
	saved.revision = 1;
	saved.items = { item(401) };
	assert(flatfile_world_item_establish(root.string(), { corpse }, { saved }, &error) ==
	       flatfile_world_item_result::ok);
	{
		flatfile_authority_lock lock;
		assert(lock.acquire(root.string(), &error));
		flatfile_authority_operation operation;
		assert(flatfile_world_item_prepare_room_item_snapshot(
			       root.string(), lock, 2300, { item(501) }, false, &operation,
			       &error) == flatfile_world_item_result::ok);
		assert(flatfile_authority_transaction_commit_operations(root.string(), lock,
									{ operation }, &error) ==
		       flatfile_authority_transaction_result::ok);
	}
	flatfile_shopkeeper_record shop;
	shop.shop_id = 3;
	shop.mob_vnum = 100;
	shop.room_vnum = 2300;
	shop.revision = 1;
	shop.items = { item(601) };
	shop.items.front().equipment_slot = 0;
	assert(flatfile_shopkeeper_establish(root.string(), { shop }, &error) ==
	       flatfile_shopkeeper_result::ok);
	const item_owner_identity foreign = { item_owner_type::player, 77, 0 };
	assert(flatfile_item_repository_establish_owner(
		       root.string(), foreign,
		       { { 102, 102, 0, foreign, 1, 999, item_custody_state::active },
			 { 999999, 999999, 0, foreign, 1, 900, item_custody_state::active } },
		       &error) == flatfile_item_baseline_result::applied);
	const item_owner_identity retired = { item_owner_type::player, 88, 0 };
	assert(flatfile_item_repository_establish_owner(
		       root.string(), retired,
		       { { 601, 601, 0, retired, 1, 900, item_custody_state::active } },
		       &error) == flatfile_item_baseline_result::applied);
	{
		flatfile_authority_lock lock;
		assert(lock.acquire(root.string(), &error));
		flatfile_authority_operation operation;
		assert(flatfile_item_repository_prepare_player_remove(root.string(), lock, 88,
								      &operation, &error) ==
		       flatfile_item_repository_result::ok);
		assert(flatfile_authority_transaction_commit_operations(root.string(), lock,
									{ operation }, &error) ==
		       flatfile_authority_transaction_result::ok);
	}
	assert(!artifact_population_read_flat_payloads(root.string(), &rows, &error));
	assert(rows.size() == 14);
	const auto &ancestor = find(rows, 101, artifact_payload_domain::player, 42);
	assert(!ancestor.extra_flags && ancestor.extra_flags_present);
	const auto &nested = find(rows, 102, artifact_payload_domain::player, 42);
	assert(nested.parent_row_id == 1 && nested.parent_item_uid == 101 &&
	       nested.extra_flags == (1U << 28));
	for (const auto &row : rows)
	{
		assert(row.item_uid != 999999);
		if (row.item_uid == 102)
			assert(row.custody_found && row.custody.owner.id == 77 &&
			       row.custody.vnum == 999);
	}
	assert(std::count_if(rows.begin(), rows.end(),
			     [](const auto &row) { return row.item_uid == 102; }) == 2);
	const auto &pet_row = find(rows, 103, artifact_payload_domain::pet, 42);
	assert(pet_row.payload_owner.type == item_owner_type::pet &&
	       pet_row.payload_owner.id == 700 && pet_row.payload_owner.context_id == 42);
	const auto &legacy_pet = find(rows, 104, artifact_payload_domain::pet, 42);
	assert(legacy_pet.parent_missing && legacy_pet.parent_row_id == 1 &&
	       legacy_pet.payload_owner.type == item_owner_type::player &&
	       legacy_pet.owner_context == 2);
	assert(find(rows, 202, artifact_payload_domain::locker, 1).payload_owner.context_id == 12);
	assert(find(rows, 203, artifact_payload_domain::locker, 2).payload_owner.context_id == 21);
	assert(find(rows, 302, artifact_payload_domain::corpse, 42).payload_owner.id ==
	       ((42ULL << 32) | 9));
	assert(find(rows, 401, artifact_payload_domain::room, 2400).owner_context == 401);
	assert(find(rows, 501, artifact_payload_domain::room, 2300).owner_context == 0);
	const auto &stock = find(rows, 601, artifact_payload_domain::shopkeeper, 3);
	assert(stock.payload_owner.id == 4 && stock.custody_found &&
	       stock.custody.state == item_custody_state::destroyed);
	seed_blobs(root.string(), &error);
	assert(!artifact_population_read_flat_payloads(root.string(), &rows, &error));
	assert(rows.size() == 23);
	const auto retained_auction = std::find_if(
		rows.begin(), rows.end(), [](const auto &row)
		{ return row.domain == artifact_payload_domain::auction && row.item_uid == 701; });
	assert(retained_auction != rows.end() &&
	       retained_auction->role == artifact_payload_role::history &&
	       retained_auction->payload_owner.id == 99 &&
	       retained_auction->extra_flags == (1U << 28));
	assert(std::count_if(rows.begin(), rows.end(),
			     [](const auto &row)
			     {
				     return row.domain == artifact_payload_domain::auction &&
					    row.role == artifact_payload_role::stored;
			     }) == 1);
	const auto &pending = find(rows, 901, artifact_payload_domain::delivery, 55);
	assert(pending.role == artifact_payload_role::delivery && pending.custody_found &&
	       pending.source_operation.bytes == operation(10).bytes &&
	       pending.delivery_ordinal == 1 && pending.payload_owner.id == 55);
	assert(find(rows, 902, artifact_payload_domain::delivery, 56).role ==
	       artifact_payload_role::history);
	const auto &raised = find(rows, 903, artifact_payload_domain::delivery, 57);
	assert(raised.role == artifact_payload_role::delivery &&
	       raised.payload_owner.type == item_owner_type::pet &&
	       raised.payload_owner.id == 7777 && raised.payload_owner.context_id == 57);
	const auto &received = find(rows, 904, artifact_payload_domain::delivery, 57);
	assert(received.role == artifact_payload_role::delivery &&
	       received.payload_owner.type == item_owner_type::unknown &&
	       received.payload_owner.id == 0 && received.payload_owner.context_id == 57 &&
	       received.custody.owner.id == 7777);
	const auto &expired = find(rows, 801, artifact_payload_domain::collector, 66);
	assert(expired.role == artifact_payload_role::history &&
	       expired.custody.state == item_custody_state::destroyed);
	const auto &embedded = find(rows, 905, artifact_payload_domain::embedded, 0);
	assert(embedded.role == artifact_payload_role::history && embedded.owner_context == 905 &&
	       embedded.payload_owner.type == item_owner_type::unknown &&
	       embedded.custody.owner.id == 60 &&
	       embedded.custody.state == item_custody_state::active && embedded.vnum == 3 &&
	       embedded.extra_flags == (1U << 28));
	assert(find(rows, 906, artifact_payload_domain::embedded, 0).role ==
	       artifact_payload_role::history);
	const size_t expected = rows.size();
	for (const auto &path :
	     { root / "players/42.snapshot", root / "domains/locker_catalog",
	       root / "domains/world_item_catalog", root / "domains/shopkeeper_catalog",
	       root / "domains/item_ownership", root / "domains/auction_catalog",
	       root / "domains/collector_catalog", root / "domains/shop_trade_materializations" })
	{
		std::ifstream input(path, std::ios::binary);
		std::vector<uint8_t> healthy{ std::istreambuf_iterator<char>(input), {} };
		assert(!healthy.empty());
		auto corrupt = healthy;
		corrupt.back() ^= 0x5a;
		assert(flatfile_atomic_write(path.parent_path().string(), path.filename().string(),
					     corrupt, &error));
		const auto *before = rows.data();
		assert(artifact_population_read_flat_payloads(root.string(), &rows, &error) ==
		       EINVAL);
		assert(rows.data() == before && rows.size() == expected);
		assert(flatfile_atomic_write(path.parent_path().string(), path.filename().string(),
					     healthy, &error));
	}
	fs::copy_file(root / "players/42.snapshot", root / "players/042.snapshot");
	const auto *before = rows.data();
	assert(artifact_population_read_flat_payloads(root.string(), &rows, &error) == EINVAL);
	assert(rows.data() == before && rows.size() == expected);
	fs::remove(root / "players/042.snapshot");
	fs::permissions(root / "domains", fs::perms::owner_read, fs::perm_options::replace);
	const auto unavailable =
		artifact_population_read_flat_payloads(root.string(), &rows, &error);
	fs::permissions(root / "domains", fs::perms::owner_all, fs::perm_options::replace);
	assert(unavailable == EIO && rows.data() == before && rows.size() == expected);
	assert(!artifact_population_read_flat_payloads(root.string(), &rows, &error) &&
	       rows.size() == expected);
	{
		std::vector<artifact_payload_projection> full(ARTIFACT_IDENTITY_MAX_RECORDS);
		assert(append_items(artifact_payload_domain::player, 42, 0,
				    { item_owner_type::player, 42, 0 }, { item(1) },
				    &full) == E2BIG);
		assert(full.size() == ARTIFACT_IDENTITY_MAX_RECORDS);
	}
	std::cout
		<< "flat payload evidence retains numeric graphs, auction/collector history and player/pet "
		   "deliveries; conflicts, missing UID and failed-read atomicity remain visible\n";
}
