#include "core/defines.h"
#include "flatfile/flatfile_artifact_repository.h"
#include "flatfile/flatfile_item_repository.h"
#include <openssl/sha.h>
#include "flatfile/flatfile_locker_repository.h"
#include "flatfile/flatfile_world_item_repository.h"
#include "flatfile/flatfile_shop_trade_materialization.h"
#include "player/player_snapshot_codec.h"

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <sys/wait.h>
#include <unistd.h>

namespace fs = std::filesystem;

static void require(bool condition, const std::string &message)
{
	if (!condition)
	{
		std::cerr << message << '\n';
		exit(1);
	}
}

static critical_operation_id operation(uint8_t discriminator)
{
	critical_operation_id id = {};
	id.bytes[0] = 0xa5;
	id.bytes.back() = discriminator;
	return id;
}

static critical_command creation(uint8_t discriminator, int64_t reason_id = 7)
{
	item_transfer_payload payload = {};
	payload.from_owner = { item_owner_type::system, 0, 0 };
	payload.to_owner = { item_owner_type::player, 42, 0 };
	payload.reason = item_transfer_reason::creation;
	payload.reason_id = reason_id;
	payload.expected_from_revision = 0;
	payload.expected_to_revision = 0;
	payload.selected_item_uid = 100;
	payload.target_root_item_uid = 100;
	payload.item_count = 2;
	payload.items[0] = { 100, 100,
			     0,	  ITEM_TRANSFER_ABSENT_REVISION,
			     500, item_custody_state::absent };
	payload.items[1] = { 101, 100,
			     100, ITEM_TRANSFER_ABSENT_REVISION,
			     501, item_custody_state::absent };
	critical_command command = {};
	require(item_transfer_command_build(&command, operation(discriminator), payload,
					    critical_source_site::command,
					    critical_deadline_class::interactive),
		"could not build creation command");
	command.accepted_at_usec = 1;
	return command;
}

static critical_command creation_batch(uint8_t discriminator)
{
	item_transfer_payload payload = {};
	payload.from_owner = { item_owner_type::system, 0, 0 };
	payload.to_owner = { item_owner_type::player, 44, 0 };
	payload.reason = item_transfer_reason::creation;
	payload.reason_id = 181;
	payload.expected_from_revision = 0;
	payload.expected_to_revision = 0;
	payload.multi_root = true;
	payload.item_count = 4;
	payload.items[0] = { 200, 200,
			     0,	  ITEM_TRANSFER_ABSENT_REVISION,
			     700, item_custody_state::absent };
	payload.items[1] = { 201, 200,
			     200, ITEM_TRANSFER_ABSENT_REVISION,
			     701, item_custody_state::absent };
	payload.items[2] = { 202, 202,
			     0,	  ITEM_TRANSFER_ABSENT_REVISION,
			     702, item_custody_state::absent };
	payload.items[3] = { 203, 202,
			     202, ITEM_TRANSFER_ABSENT_REVISION,
			     703, item_custody_state::absent };
	critical_command command = {};
	require(item_transfer_command_build(&command, operation(discriminator), payload,
					    critical_source_site::command,
					    critical_deadline_class::interactive),
		"could not build multi-root creation command");
	command.accepted_at_usec = discriminator;
	return command;
}

static critical_command single_creation(uint8_t discriminator, uint64_t item_uid,
					uint64_t player_pid, uint64_t system_revision)
{
	item_transfer_payload payload = {};
	payload.from_owner = { item_owner_type::system, 0, 0 };
	payload.to_owner = { item_owner_type::player, player_pid, 0 };
	payload.reason = item_transfer_reason::creation;
	payload.reason_id = 11;
	payload.expected_from_revision = system_revision;
	payload.expected_to_revision = 0;
	payload.selected_item_uid = item_uid;
	payload.target_root_item_uid = item_uid;
	payload.item_count = 1;
	payload.items[0] = { item_uid, item_uid,
			     0,	       ITEM_TRANSFER_ABSENT_REVISION,
			     600,      item_custody_state::absent };
	critical_command command = {};
	require(item_transfer_command_build(&command, operation(discriminator), payload,
					    critical_source_site::command,
					    critical_deadline_class::interactive),
		"could not build single-item creation command");
	command.accepted_at_usec = 4;
	return command;
}

static critical_command nested_single_creation(uint8_t discriminator, uint64_t item_uid,
					       uint64_t player_pid, uint64_t system_revision,
					       uint64_t player_revision, uint64_t container_uid)
{
	item_transfer_payload payload = {};
	payload.from_owner = { item_owner_type::system, 0, 0 };
	payload.to_owner = { item_owner_type::player, player_pid, 0 };
	payload.reason = item_transfer_reason::creation;
	payload.reason_id = 12;
	payload.expected_from_revision = system_revision;
	payload.expected_to_revision = player_revision;
	payload.selected_item_uid = item_uid;
	payload.target_root_item_uid = container_uid;
	payload.target_parent_item_uid = container_uid;
	payload.expected_target_parent_revision = 1;
	payload.item_count = 1;
	payload.items[0] = { item_uid, item_uid,
			     0,	       ITEM_TRANSFER_ABSENT_REVISION,
			     601,      item_custody_state::absent };
	player_item_snapshot item = {};
	item.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	item.equipment_slot = -1;
	item.object_uid = item_uid;
	item.vnum = 601;
	item.name = "nested created item";
	std::vector<uint8_t> item_blob;
	require(player_item_snapshot_list_encode({ item }, &item_blob) ==
				player_snapshot_codec_result::ok &&
			item_blob.size() <= payload.item_blob.size(),
		"could not encode nested creation snapshot");
	payload.item_blob_size = static_cast<uint32_t>(item_blob.size());
	std::copy(item_blob.begin(), item_blob.end(), payload.item_blob.begin());
	critical_command command = {};
	require(item_transfer_command_build(&command, operation(discriminator), payload,
					    critical_source_site::command,
					    critical_deadline_class::interactive),
		"could not build nested single-item creation command");
	command.accepted_at_usec = 5;
	return command;
}

static item_transfer_result result_of(const critical_apply_result &applied)
{
	item_transfer_result result = {};
	require(item_transfer_command_decode_result(applied.result_payload.data(),
						    applied.result_size, &result),
		"could not decode item repository result");
	return result;
}

static std::vector<player_item_snapshot> movement_items()
{
	player_item_snapshot root = {};
	root.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	root.equipment_slot = -1;
	root.object_uid = 100;
	root.generated_key = 1100;
	root.vnum = 500;
	root.name = "given container";
	root.short_description = "an exact given container";
	player_item_snapshot child = {};
	child.parent_index = 0;
	child.equipment_slot = -1;
	child.object_uid = 101;
	child.generated_key = 1101;
	child.vnum = 501;
	child.name = "nested gift";
	child.short_description = "an exact nested gift";
	return { root, child };
}

/* Construct an account-owned locker for custody-transfer coverage. */
static shop_trade_payload shop_trade(shop_trade_action action, uint64_t item_uid,
				     uint64_t item_revision, int32_t vnum, uint64_t stock_uid = 0,
				     uint64_t stock_revision = 0)
{
	shop_trade_payload payload = {};
	payload.action = action;
	payload.player_pid = 42;
	payload.shop_id = 0;
	payload.racewar = 1;
	strcpy(payload.account_name.data(), "ShopTester");
	payload.price = 100;
	payload.expected_wallet_revision = 1;
	payload.expected_bank_revision = 1;
	payload.expected_shop_revision = 1;
	payload.selected_item_uid = item_uid;
	payload.target_root_item_uid = item_uid;
	payload.stock_item_uid = stock_uid;
	payload.expected_stock_item_revision = stock_revision;
	payload.stock_vnum = stock_uid ? vnum : 0;
	payload.item_count = 1;
	payload.items[0] = { item_uid,
			     item_uid,
			     0,
			     item_revision,
			     vnum,
			     action == shop_trade_action::buy_produced ?
				     item_custody_state::absent :
				     item_custody_state::active };
	payload.item_blob_size = 1;
	payload.item_blob[0] = 0xa5;
	return payload;
}

int main(int argc, char **argv)
{
	require(argc == 2, "state root argument required");
	const fs::path root = argv[1];
	const fs::path domains = root / "domains";
	fs::create_directories(domains);
	fs::permissions(root, fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(domains, fs::perms::owner_all, fs::perm_options::replace);
	const item_owner_identity baseline_owner = { item_owner_type::player, 999, 0 };
	std::vector<flatfile_item_ownership_record> baseline = {
		{ 300, 300, 0, baseline_owner, 1, 700, item_custody_state::active },
		{ 301, 300, 300, baseline_owner, 1, 701, item_custody_state::active },
	};
	std::string error;
	require(flatfile_item_repository_establish_owner(root.string(), baseline_owner, baseline,
							 &error) ==
			flatfile_item_baseline_result::applied,
		"owner baseline did not apply: " + error);
	require(flatfile_item_repository_establish_owner(root.string(), baseline_owner, baseline,
							 &error) ==
			flatfile_item_baseline_result::already_applied,
		"owner baseline retry was not idempotent");
	std::vector<flatfile_item_ownership_record> active_player_items;
	require(flatfile_item_repository_list_active_player_items(root.string(),
								  &active_player_items, &error) ==
				flatfile_item_repository_result::ok &&
			active_player_items.size() == 2 && active_player_items[0].item_uid == 300 &&
			active_player_items[1].item_uid == 301 &&
			active_player_items[0].owner.type == item_owner_type::player &&
			active_player_items[0].owner.id == 999,
		"active player item enumeration did not expose the authoritative baseline");
	baseline[1].vnum = 702;
	require(flatfile_item_repository_establish_owner(root.string(), baseline_owner, baseline,
							 &error) ==
			flatfile_item_baseline_result::conflict,
		"conflicting owner baseline was accepted");
	{
		const fs::path filename = domains / "item_ownership";
		std::ifstream input(filename, std::ios::binary);
		std::vector<uint8_t> bytes((std::istreambuf_iterator<char>(input)), {});
		auto read32 = [&](size_t offset)
		{
			require(offset + 4 <= bytes.size(), "truncated legacy fixture");
			uint32_t value = 0;
			for (size_t i = 0; i < 4; ++i)
				value |= uint32_t(bytes[offset + i]) << (8 * i);
			return value;
		};
		require(read32(56) == 1 && read32(60) == 2 && read32(64) == 0,
			"unexpected baseline fixture counts");
		// Remove v3's empty per-item payload fields to reproduce an actual v1 file.
		std::vector<uint8_t> payload(bytes.begin() + 56, bytes.begin() + 93);
		size_t offset = 93;
		for (size_t i = 0; i < 2; ++i)
		{
			require(read32(offset + 54) == 0,
				"legacy fixture unexpectedly has coin payloads");
			payload.insert(payload.end(), bytes.begin() + offset,
				       bytes.begin() + offset + 54);
			offset += 58;
		}
		require(offset == bytes.size(), "unexpected baseline trailing data");
		bytes.resize(56);
		bytes[8] = 1;
		for (size_t i = 0; i < 4; ++i)
			bytes[12 + i] = static_cast<uint8_t>(payload.size() >> (8 * i));
		SHA256(payload.data(), payload.size(), bytes.data() + 24);
		bytes.insert(bytes.end(), payload.begin(), payload.end());
		std::ofstream output(filename, std::ios::binary | std::ios::trunc);
		output.write(reinterpret_cast<const char *>(bytes.data()), bytes.size());
		output.close();
		uint64_t legacy_revision = 0;
		std::vector<flatfile_item_ownership_record> legacy_items;
		require(flatfile_item_repository_load_owner(
				root.string(), baseline_owner, &legacy_revision, &legacy_items,
				&error) == flatfile_item_repository_result::ok &&
				legacy_revision == 1 && legacy_items.size() == 2,
			"v1 ownership catalog without operation results did not remain readable");
	}
	{
		flatfile_authority_lock lock;
		flatfile_authority_operation operation;
		require(lock.acquire(root.string(), &error) &&
				flatfile_item_repository_prepare_player_remove(
					root.string(), lock, 999, &operation, &error) ==
					flatfile_item_repository_result::ok &&
				operation.filename == "item_ownership" && !operation.bytes.empty(),
			"player item destruction was not prepared: " + error);
		require(flatfile_authority_transaction_commit_operations(root.string(), lock,
									 { operation }, &error) ==
				flatfile_authority_transaction_result::ok,
			"prepared player item destruction did not commit: " + error);
	}
	uint64_t removed_revision = 0;
	std::vector<flatfile_item_ownership_record> removed_items;
	require(flatfile_item_repository_load_owner(root.string(), baseline_owner,
						    &removed_revision, &removed_items, &error) ==
			flatfile_item_repository_result::not_found,
		"deleted player item owner remained authoritative");
	{
		flatfile_authority_lock lock;
		flatfile_authority_operation operation;
		require(lock.acquire(root.string(), &error) &&
				flatfile_item_repository_prepare_player_remove(
					root.string(), lock, 999, &operation, &error) ==
					flatfile_item_repository_result::unchanged,
			"prepared player item destruction was not idempotent");
	}

	const fs::path nested_root = root / "nested-creation";
	fs::create_directories(nested_root / "domains");
	fs::permissions(nested_root, fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(nested_root / "domains", fs::perms::owner_all, fs::perm_options::replace);
	critical_apply_result nested_applied = flatfile_item_repository_apply(
		nested_root.string(), single_creation(14, 110, 43, 0));
	require(nested_applied.outcome == critical_apply_outcome::applied &&
			nested_applied.error_code == 0,
		"nested-creation container did not apply: outcome=" +
			std::to_string(static_cast<unsigned int>(nested_applied.outcome)) +
			" error=" + std::to_string(nested_applied.error_code));
	nested_applied = flatfile_item_repository_apply(
		nested_root.string(), nested_single_creation(15, 111, 43, 1, 1, 110));
	require(nested_applied.outcome == critical_apply_outcome::applied &&
			nested_applied.error_code == 0,
		"nested item creation did not apply: outcome=" +
			std::to_string(static_cast<unsigned int>(nested_applied.outcome)) +
			" error=" + std::to_string(nested_applied.error_code));
	uint64_t nested_owner_revision = 0;
	std::vector<flatfile_item_ownership_record> nested_items;
	require(flatfile_item_repository_load_owner(
			nested_root.string(), { item_owner_type::player, 43, 0 },
			&nested_owner_revision, &nested_items,
			&error) == flatfile_item_repository_result::ok &&
			nested_owner_revision == 2 && nested_items.size() == 2 &&
			nested_items[0].item_uid == 110 && nested_items[0].parent_item_uid == 0 &&
			nested_items[1].item_uid == 111 && nested_items[1].root_item_uid == 110 &&
			nested_items[1].parent_item_uid == 110,
		"nested item creation topology did not round trip: " + error);

	const fs::path creation_batch_root = root / "multi-root-creation";
	fs::create_directories(creation_batch_root / "domains");
	fs::permissions(creation_batch_root, fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(creation_batch_root / "domains", fs::perms::owner_all,
			fs::perm_options::replace);
	const critical_command batch_create = creation_batch(16);
	critical_apply_result batch_applied =
		flatfile_item_repository_apply(creation_batch_root.string(), batch_create);
	require(batch_applied.outcome == critical_apply_outcome::applied &&
			batch_applied.error_code == 0,
		"multi-root item creation did not apply: outcome=" +
			std::to_string(static_cast<unsigned int>(batch_applied.outcome)) +
			" error=" + std::to_string(batch_applied.error_code));
	const item_transfer_result batch_result = result_of(batch_applied);
	require(batch_result.root_item_uid == 200 && batch_result.item_count == 4 &&
			batch_result.from_owner_revision == 1 &&
			batch_result.to_owner_revision == 1 && batch_result.max_item_revision == 1,
		"multi-root item creation returned incorrect revisions");
	uint64_t batch_owner_revision = 0;
	std::vector<flatfile_item_ownership_record> batch_items;
	require(flatfile_item_repository_load_owner(creation_batch_root.string(),
						    { item_owner_type::player, 44, 0 },
						    &batch_owner_revision, &batch_items, &error) ==
				flatfile_item_repository_result::ok &&
			batch_owner_revision == 1 && batch_items.size() == 4 &&
			batch_items[0].item_uid == 200 && batch_items[0].root_item_uid == 200 &&
			batch_items[0].parent_item_uid == 0 && batch_items[1].item_uid == 201 &&
			batch_items[1].root_item_uid == 200 &&
			batch_items[1].parent_item_uid == 200 && batch_items[2].item_uid == 202 &&
			batch_items[2].root_item_uid == 202 &&
			batch_items[2].parent_item_uid == 0 && batch_items[3].item_uid == 203 &&
			batch_items[3].root_item_uid == 202 &&
			batch_items[3].parent_item_uid == 202,
		"multi-root item creation topology did not round trip: " + error);
	batch_applied = flatfile_item_repository_apply(creation_batch_root.string(), batch_create);
	require(batch_applied.outcome == critical_apply_outcome::already_applied &&
			result_of(batch_applied).to_owner_revision == 1,
		"multi-root item creation replay was not idempotent");

	const critical_command create = creation(1);
	critical_apply_result applied = flatfile_item_repository_apply(root.string(), create);
	require(applied.outcome == critical_apply_outcome::applied && applied.error_code == 0,
		"item creation did not apply: outcome=" +
			std::to_string(static_cast<unsigned int>(applied.outcome)) +
			" error=" + std::to_string(applied.error_code));
	item_transfer_result result = result_of(applied);
	require(result.root_item_uid == 100 && result.item_count == 2 &&
			result.from_owner_revision == 1 && result.to_owner_revision == 1 &&
			result.max_item_revision == 1,
		"item creation returned incorrect revisions");

	uint64_t owner_revision = 0;
	std::vector<flatfile_item_ownership_record> items;
	require(flatfile_item_repository_load_owner(
			root.string(), { item_owner_type::player, 42, 0 }, &owner_revision, &items,
			&error) == flatfile_item_repository_result::ok &&
			owner_revision == 1 && items.size() == 2 && items[0].item_uid == 100 &&
			items[0].parent_item_uid == 0 && items[1].parent_item_uid == 100 &&
			items[1].item_revision == 1,
		"created ownership topology did not round trip: " + error);

	applied = flatfile_item_repository_apply(root.string(), create);
	require(applied.outcome == critical_apply_outcome::already_applied &&
			result_of(applied).to_owner_revision == 1,
		"replayed creation was not idempotent");
	applied = flatfile_item_repository_apply(root.string(), creation(1, 8));
	require(applied.outcome == critical_apply_outcome::terminal_failure &&
			applied.error_code == EEXIST,
		"operation ID reuse with different content was accepted");

	item_transfer_payload move = {};
	move.from_owner = { item_owner_type::player, 42, 0 };
	move.to_owner = { item_owner_type::player, 77, 0 };
	move.reason = item_transfer_reason::operator_repair;
	move.reason_id = 9;
	move.expected_from_revision = 1;
	move.expected_to_revision = 0;
	move.selected_item_uid = 100;
	move.target_root_item_uid = 100;
	move.item_count = 2;
	for (size_t index = 0; index < items.size(); ++index)
		move.items[index] = { items[index].item_uid,
				      items[index].root_item_uid,
				      items[index].parent_item_uid,
				      items[index].item_revision,
				      items[index].vnum,
				      items[index].state };
	const std::vector<player_item_snapshot> exact_items = movement_items();
	std::vector<uint8_t> exact_blob;
	require(player_item_snapshot_list_encode(exact_items, &exact_blob) ==
				player_snapshot_codec_result::ok &&
			exact_blob.size() <= move.item_blob.size(),
		"could not encode exact transfer snapshot");
	move.item_blob_size = static_cast<uint32_t>(exact_blob.size());
	std::copy(exact_blob.begin(), exact_blob.end(), move.item_blob.begin());
	critical_command transfer = {};
	require(item_transfer_command_build(&transfer, operation(2), move,
					    critical_source_site::command,
					    critical_deadline_class::interactive),
		"could not build transfer command");
	transfer.accepted_at_usec = 2;
	setenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_IMAGE", "1", 1);
	applied = flatfile_item_repository_apply(root.string(), transfer);
	unsetenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_IMAGE");
	require(applied.outcome == critical_apply_outcome::retryable_failure &&
			applied.error_code == EIO,
		"interrupted transfer did not leave recoverable atomic intent");
	applied = flatfile_item_repository_apply(root.string(), transfer);
	result = result_of(applied);
	require(applied.outcome == critical_apply_outcome::already_applied &&
			result.from_owner_revision == 2 && result.to_owner_revision == 1 &&
			result.max_item_revision == 2,
		"cross-owner transfer did not recover atomically");
	items.clear();
	require(flatfile_item_repository_load_owner(
			root.string(), { item_owner_type::player, 77, 0 }, &owner_revision, &items,
			&error) == flatfile_item_repository_result::ok &&
			owner_revision == 1 && items.size() == 2 && items[0].item_revision == 2,
		"destination owner did not receive the complete topology");
	player_snapshot stale_source = {};
	stale_source.pid = 42;
	stale_source.items = exact_items;
	player_snapshot missing_destination = {};
	missing_destination.pid = 77;
	std::vector<flatfile_item_ownership_record> source_items;
	uint64_t source_revision = 0;
	const auto source_loaded = flatfile_item_repository_load_owner(
		root.string(), { item_owner_type::player, 42, 0 }, &source_revision, &source_items,
		&error);
	require((source_loaded == flatfile_item_repository_result::ok ||
		 source_loaded == flatfile_item_repository_result::not_found) &&
			source_items.empty(),
		"source owner unexpectedly retained transferred items");
	{
		flatfile_authority_lock reconciliation_lock;
		require(reconciliation_lock.acquire(root.string(), &error),
			"could not lock transfer reconciliation: " + error);
		require(flatfile_shop_trade_materialization_reconcile(
				root.string(), reconciliation_lock, 42, source_items, &stale_source,
				&error) == flatfile_shop_trade_materialization_result::ok &&
				stale_source.items.empty(),
			"restart reconciliation retained the stale source transfer: " + error);
		require(flatfile_shop_trade_materialization_reconcile(
				root.string(), reconciliation_lock, 77, items, &missing_destination,
				&error) == flatfile_shop_trade_materialization_result::ok &&
				missing_destination.items.size() == 2 &&
				missing_destination.items[0].object_uid == 100 &&
				missing_destination.items[0].short_description ==
					"an exact given container" &&
				missing_destination.items[1].parent_index == 0,
			"restart reconciliation did not reconstruct the exact destination transfer: " +
				error);
	}
	const fs::path room_root = root / "room-transfer";
	fs::create_directories(room_root / "domains");
	fs::permissions(room_root, fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(room_root / "domains", fs::perms::owner_all, fs::perm_options::replace);
	const item_owner_identity room_owner = { item_owner_type::room, 9001, 0 };
	player_item_snapshot storage_root = {};
	storage_root.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	storage_root.equipment_slot = 0;
	storage_root.object_uid = 300;
	storage_root.generated_key = 1300;
	storage_root.vnum = 700;
	storage_root.type = ITEM_STORAGE;
	storage_root.name = "saved storage";
	storage_root.short_description = "a saved storage container";
	storage_root.weight = 2;
	player_item_snapshot storage_child = storage_root;
	storage_child.parent_index = 0;
	storage_child.object_uid = 301;
	storage_child.generated_key = 1301;
	storage_child.vnum = 701;
	storage_child.type = ITEM_CONTAINER;
	storage_child.name = "stored container";
	storage_child.short_description = "a stored container";
	storage_child.weight = 1;
	std::vector<uint8_t> storage_blob;
	require(player_item_snapshot_list_encode({ storage_root, storage_child }, &storage_blob) ==
			player_snapshot_codec_result::ok,
		"could not encode saved storage subtree");
	// A grant creates a saved storage subtree in a room, with the room's record.
	item_transfer_payload room_create = {};
	room_create.from_owner = { item_owner_type::system, 0, 0 };
	room_create.to_owner = room_owner;
	room_create.reason = item_transfer_reason::creation;
	room_create.reason_id = 9001;
	room_create.expected_from_revision = 0;
	room_create.expected_to_revision = 0;
	room_create.selected_item_uid = 300;
	room_create.target_root_item_uid = 300;
	room_create.item_count = 2;
	room_create.items[0] = { 300, 300,
				 0,   ITEM_TRANSFER_ABSENT_REVISION,
				 700, item_custody_state::absent };
	room_create.items[1] = { 301, 300,
				 300, ITEM_TRANSFER_ABSENT_REVISION,
				 701, item_custody_state::absent };
	room_create.item_blob_size = static_cast<uint32_t>(storage_blob.size());
	std::copy(storage_blob.begin(), storage_blob.end(), room_create.item_blob.begin());
	critical_command room_create_command = {};
	require(item_transfer_command_build(&room_create_command, operation(8), room_create,
					    critical_source_site::operator_repair,
					    critical_deadline_class::interactive),
		"could not build saved storage establishment");
	room_create_command.accepted_at_usec = 8;
	setenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_IMAGE", "1", 1);
	applied = flatfile_item_repository_apply(room_root.string(), room_create_command);
	unsetenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_IMAGE");
	require(applied.outcome == critical_apply_outcome::retryable_failure &&
			applied.error_code == EIO,
		"interrupted room grant did not retain composite intent");
	applied = flatfile_item_repository_apply(room_root.string(), room_create_command);
	require(applied.outcome == critical_apply_outcome::already_applied &&
			result_of(applied).to_owner_revision == 1,
		"room grant did not recover atomically");
	std::vector<flatfile_room_item_record> room_records;
	require(flatfile_world_item_list_rooms(room_root.string(), &room_records, &error) ==
				flatfile_world_item_result::ok &&
			room_records.size() == 1 && room_records[0].revision == 1 &&
			room_records[0].items.size() == 2 &&
			room_records[0].items[0].object_uid == 300 &&
			room_records[0].items[0].type == ITEM_STORAGE &&
			room_records[0].items[0].equipment_slot == -1 &&
			room_records[0].items[1].object_uid == 301 &&
			room_records[0].items[1].parent_index == 0,
		"room grant did not publish the exact detached subtree: " + error);
	uint64_t room_revision = 0;
	std::vector<flatfile_item_ownership_record> owned_room_items;
	require(flatfile_item_repository_load_owner(room_root.string(), room_owner, &room_revision,
						    &owned_room_items, &error) ==
				flatfile_item_repository_result::ok &&
			room_revision == 1 && owned_room_items.size() == 2,
		"room grant did not publish matching ownership custody");

	// An operator repair moves the stored container to the room's floor.
	player_item_snapshot detached_child = storage_child;
	detached_child.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	detached_child.equipment_slot = -1;
	std::vector<uint8_t> detached_child_blob;
	require(player_item_snapshot_list_encode({ detached_child }, &detached_child_blob) ==
			player_snapshot_codec_result::ok,
		"could not encode saved storage child removal");
	item_transfer_payload room_reparent = {};
	room_reparent.from_owner = room_owner;
	room_reparent.to_owner = room_owner;
	room_reparent.reason = item_transfer_reason::operator_repair;
	room_reparent.reason_id = 301;
	room_reparent.expected_from_revision = 1;
	room_reparent.expected_to_revision = 1;
	room_reparent.selected_item_uid = 301;
	room_reparent.target_root_item_uid = 301;
	room_reparent.item_count = 1;
	room_reparent.items[0] = { 301, 300, 300, 1, 701, item_custody_state::active };
	room_reparent.item_blob_size = static_cast<uint32_t>(detached_child_blob.size());
	std::copy(detached_child_blob.begin(), detached_child_blob.end(),
		  room_reparent.item_blob.begin());
	critical_command room_reparent_command = {};
	require(item_transfer_command_build(&room_reparent_command, operation(10), room_reparent,
					    critical_source_site::operator_repair,
					    critical_deadline_class::interactive),
		"could not build saved storage child removal");
	room_reparent_command.accepted_at_usec = 10;
	applied = flatfile_item_repository_apply(room_root.string(), room_reparent_command);
	require(applied.outcome == critical_apply_outcome::applied &&
			result_of(applied).from_owner_revision == 2 &&
			result_of(applied).to_owner_revision == 2,
		"saved storage child removal did not apply");
	room_records.clear();
	require(flatfile_world_item_list_rooms(room_root.string(), &room_records, &error) ==
				flatfile_world_item_result::ok &&
			room_records[0].revision == 2 && room_records[0].items.size() == 2 &&
			room_records[0].items[0].weight == 1 &&
			room_records[0].items[1].object_uid == 301 &&
			room_records[0].items[1].parent_index == PLAYER_SNAPSHOT_NO_PARENT,
		"saved storage child removal did not detach the root or repair ancestor weight");
	{
		const fs::path large_root = root / "large-transfer-materialization";
		fs::create_directories(large_root / "domains");
		fs::permissions(large_root, fs::perms::owner_all, fs::perm_options::replace);
		fs::permissions(large_root / "domains", fs::perms::owner_all,
				fs::perm_options::replace);
		// A starter kit can hold more roots than a shop trade.
		constexpr size_t large_count = SHOP_TRADE_MAX_ITEMS + 1;
		item_transfer_payload large_transfer = {};
		large_transfer.from_owner = { item_owner_type::system, 0, 0 };
		large_transfer.to_owner = { item_owner_type::player, 99, 0 };
		large_transfer.reason = item_transfer_reason::creation;
		large_transfer.multi_root = true;
		large_transfer.item_count = static_cast<uint16_t>(large_count);
		std::vector<player_item_snapshot> large_items;
		large_items.reserve(large_count);
		for (size_t index = 0; index < large_count; ++index)
		{
			const uint64_t uid = 500 + index;
			const int32_t vnum = 900 + static_cast<int32_t>(index);
			player_item_snapshot item = {};
			item.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
			item.equipment_slot = -1;
			item.object_uid = uid;
			item.vnum = vnum;
			item.name = "large batch item";
			large_items.push_back(item);
			large_transfer.items[index] = { uid,  uid,
							0,    ITEM_TRANSFER_ABSENT_REVISION,
							vnum, item_custody_state::absent };
		}
		std::vector<uint8_t> large_blob;
		require(player_item_snapshot_list_encode(large_items, &large_blob) ==
					player_snapshot_codec_result::ok &&
				large_blob.size() <= large_transfer.item_blob.size(),
			"could not encode above-shop-limit batch snapshot");
		large_transfer.item_blob_size = static_cast<uint32_t>(large_blob.size());
		std::copy(large_blob.begin(), large_blob.end(), large_transfer.item_blob.begin());
		flatfile_authority_lock lock;
		flatfile_shop_trade_materialization_mutation mutation;
		require(lock.acquire(large_root.string(), &error) &&
				flatfile_item_transfer_materialization_prepare(
					large_root.string(), lock, operation(55), large_transfer,
					&mutation,
					&error) == flatfile_shop_trade_materialization_result::ok,
			"above-shop-limit batch materialization did not prepare: " + error);
		require(flatfile_authority_transaction_commit(large_root.string(), lock,
							      { mutation.after_image }, &error) ==
				flatfile_authority_transaction_result::ok,
			"above-shop-limit batch materialization did not commit: " + error);
		flatfile_shop_trade_materialization_health health = {};
		require(flatfile_shop_trade_materialization_read_health(large_root.string(), lock,
									&health, &error) ==
					flatfile_shop_trade_materialization_result::ok &&
				health.events == 1,
			"above-shop-limit batch materialization did not remain readable: " + error);
	}
	items.clear();
	require(flatfile_item_repository_load_owner(
			root.string(), { item_owner_type::player, 77, 0 }, &owner_revision, &items,
			&error) == flatfile_item_repository_result::ok &&
			owner_revision == 1 && items.size() == 2,
		"isolated room transfer changed the primary transfer fixture");
	move.expected_from_revision = 1;
	move.expected_to_revision = 0;
	critical_command stale = {};
	require(item_transfer_command_build(&stale, operation(3), move,
					    critical_source_site::command,
					    critical_deadline_class::interactive),
		"could not build stale transfer command");
	stale.accepted_at_usec = 3;
	// Memory is the authority for a player: stale owner revisions no longer refuse the
	// move, and the items are claimed from whatever the catalog still says.
	applied = flatfile_item_repository_apply(root.string(), stale);
	require(applied.outcome == critical_apply_outcome::applied,
		"a player's stale owner revisions refused the move: outcome=" +
			std::to_string(static_cast<int>(applied.outcome)) +
			" error=" + std::to_string(applied.error_code));
	items.clear();
	require(flatfile_item_repository_load_owner(root.string(), move.to_owner, &owner_revision,
						    &items, &error) ==
				flatfile_item_repository_result::ok &&
			std::count_if(items.begin(), items.end(),
				      [](const flatfile_item_ownership_record &item)
				      {
					      return (item.item_uid == 100 ||
						      item.item_uid == 101) &&
						     item.state == item_custody_state::active;
				      }) == 2,
		"the claimed items did not reach the destination");
	applied = flatfile_item_repository_apply(root.string(), stale);
	require(applied.outcome == critical_apply_outcome::already_applied,
		"the claimed move was not durably replayable");

	const critical_command concurrent = single_creation(4, 200, 88, 1);
	for (int child = 0; child < 2; ++child)
	{
		const pid_t pid = fork();
		require(pid >= 0, "ownership writer fork failed");
		if (!pid)
		{
			const critical_apply_result child_result =
				flatfile_item_repository_apply(root.string(), concurrent);
			_exit(child_result.outcome == critical_apply_outcome::applied ||
					      child_result.outcome ==
						      critical_apply_outcome::already_applied ?
				      0 :
				      2);
		}
	}
	for (int child = 0; child < 2; ++child)
	{
		int status = 0;
		require(wait(&status) > 0 && WIFEXITED(status) && WEXITSTATUS(status) == 0,
			"concurrent idempotent ownership writer failed");
	}
	items.clear();
	require(flatfile_item_repository_load_owner(
			root.string(), { item_owner_type::player, 88, 0 }, &owner_revision, &items,
			&error) == flatfile_item_repository_result::ok &&
			owner_revision == 1 && items.size() == 1 && items[0].item_uid == 200,
		"concurrent replay duplicated or lost item creation");

	const fs::path shop_root = fs::path(argv[1]).string() + "-shop";
	fs::create_directories(shop_root / "domains");
	fs::permissions(shop_root, fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(shop_root / "domains", fs::perms::owner_all, fs::perm_options::replace);
	const item_owner_identity shop_player = { item_owner_type::player, 42, 0 };
	const item_owner_identity shop_owner = { item_owner_type::shopkeeper,
						 item_shopkeeper_owner_id(0), 0 };
	require(flatfile_item_repository_establish_owner(
			shop_root.string(), shop_player,
			{ { 100, 100, 0, shop_player, 1, 700, item_custody_state::active },
			  { 101, 101, 0, shop_player, 1, 701, item_custody_state::active } },
			&error) == flatfile_item_baseline_result::applied,
		"shop player custody baseline failed: " + error);
	require(flatfile_item_repository_establish_owner(
			shop_root.string(), shop_owner,
			{ { 200, 200, 0, shop_owner, 1, 800, item_custody_state::active },
			  { 201, 201, 0, shop_owner, 1, 801, item_custody_state::active } },
			&error) == flatfile_item_baseline_result::applied,
		"shop inventory custody baseline failed: " + error);
	flatfile_item_shop_trade_mutation shop_mutation;
	unsigned int shop_result_code = 0;
	auto produced = shop_trade(shop_trade_action::buy_produced, 300,
				   ITEM_TRANSFER_ABSENT_REVISION, 801, 201, 1);
	{
		auto stale_stock = produced;
		stale_stock.expected_stock_item_revision = 2;
		flatfile_authority_lock lock;
		require(lock.acquire(shop_root.string(), &error),
			"could not acquire stale stock lock");
		require(flatfile_item_repository_prepare_shop_trade(
				shop_root.string(), lock, stale_stock, &shop_mutation,
				&shop_result_code, &error) == flatfile_item_repository_result::ok &&
				shop_result_code == ESTALE &&
				shop_mutation.after_image.bytes.empty(),
			"stale produced-stock exemplar was accepted");
	}
	{
		flatfile_authority_lock lock;
		require(lock.acquire(shop_root.string(), &error),
			"could not acquire produced lock");
		require(flatfile_item_repository_prepare_shop_trade(
				shop_root.string(), lock, produced, &shop_mutation,
				&shop_result_code, &error) == flatfile_item_repository_result::ok &&
				shop_result_code == 0 && shop_mutation.player_owner_revision == 2 &&
				shop_mutation.counterparty_owner_revision == 1 &&
				shop_mutation.item_revisions[0] == 1,
			"produced custody mutation did not prepare: " + error);
		require(flatfile_authority_transaction_commit(
				shop_root.string(), lock, { shop_mutation.after_image }, &error) ==
				flatfile_authority_transaction_result::ok,
			"produced custody mutation did not commit: " + error);
	}
	auto purchase = shop_trade(shop_trade_action::buy_existing, 200, 1, 800, 200, 1);
	{
		flatfile_authority_lock lock;
		require(lock.acquire(shop_root.string(), &error),
			"could not acquire purchase lock");
		require(flatfile_item_repository_prepare_shop_trade(
				shop_root.string(), lock, purchase, &shop_mutation,
				&shop_result_code, &error) == flatfile_item_repository_result::ok &&
				shop_result_code == 0 && shop_mutation.player_owner_revision == 3 &&
				shop_mutation.counterparty_owner_revision == 2 &&
				shop_mutation.item_revisions[0] == 2,
			"purchase custody mutation did not prepare: " + error);
		require(flatfile_authority_transaction_commit(
				shop_root.string(), lock, { shop_mutation.after_image }, &error) ==
				flatfile_authority_transaction_result::ok,
			"purchase custody mutation did not commit: " + error);
	}
	auto sale = shop_trade(shop_trade_action::sell_store, 100, 1, 700);
	{
		flatfile_authority_lock lock;
		require(lock.acquire(shop_root.string(), &error), "could not acquire sale lock");
		require(flatfile_item_repository_prepare_shop_trade(
				shop_root.string(), lock, sale, &shop_mutation, &shop_result_code,
				&error) == flatfile_item_repository_result::ok &&
				shop_result_code == 0 && shop_mutation.player_owner_revision == 4 &&
				shop_mutation.counterparty_owner_revision == 3 &&
				shop_mutation.item_revisions[0] == 2,
			"sale custody mutation did not prepare: " + error);
		require(flatfile_authority_transaction_commit(
				shop_root.string(), lock, { shop_mutation.after_image }, &error) ==
				flatfile_authority_transaction_result::ok,
			"sale custody mutation did not commit: " + error);
	}
	auto destruction = shop_trade(shop_trade_action::sell_destroy, 101, 1, 701);
	{
		flatfile_authority_lock lock;
		require(lock.acquire(shop_root.string(), &error),
			"could not acquire destruction lock");
		require(flatfile_item_repository_prepare_shop_trade(
				shop_root.string(), lock, destruction, &shop_mutation,
				&shop_result_code, &error) == flatfile_item_repository_result::ok &&
				shop_result_code == 0 && shop_mutation.player_owner_revision == 5 &&
				shop_mutation.counterparty_owner_revision == 1 &&
				shop_mutation.item_revisions[0] == 2,
			"destruction custody mutation did not prepare: " + error);
		require(flatfile_authority_transaction_commit(
				shop_root.string(), lock, { shop_mutation.after_image }, &error) ==
				flatfile_authority_transaction_result::ok,
			"destruction custody mutation did not commit: " + error);
	}
	items.clear();
	require(flatfile_item_repository_load_owner(shop_root.string(), shop_player,
						    &owner_revision, &items, &error) ==
				flatfile_item_repository_result::ok &&
			owner_revision == 5 && items.size() == 2 && items[0].item_uid == 200 &&
			items[1].item_uid == 300,
		"shop trades did not publish exact player custody");
	items.clear();
	require(flatfile_item_repository_load_owner(shop_root.string(), shop_owner, &owner_revision,
						    &items, &error) ==
				flatfile_item_repository_result::ok &&
			owner_revision == 3 && items.size() == 2 && items[0].item_uid == 100 &&
			items[1].item_uid == 201,
		"shop trades did not preserve exact shop custody");

	const fs::path authority = domains / "item_ownership";
	{
		std::fstream file(authority, std::ios::in | std::ios::out | std::ios::binary);
		require(file.good(), "could not open ownership authority for corruption test");
		file.seekg(-1, std::ios::end);
		char value = 0;
		file.read(&value, 1);
		value ^= 0x5c;
		file.seekp(-1, std::ios::end);
		file.write(&value, 1);
	}
	items.clear();
	require(flatfile_item_repository_load_owner(
			root.string(), { item_owner_type::player, 77, 0 }, &owner_revision, &items,
			&error) == flatfile_item_repository_result::invalid,
		"corrupt ownership checksum was accepted");
	require(flatfile_item_repository_list_active_player_items(root.string(), &items, &error) ==
			flatfile_item_repository_result::invalid,
		"corrupt ownership checksum was exposed through player item enumeration");
	applied = flatfile_item_repository_apply(root.string(), transfer);
	require(applied.outcome == critical_apply_outcome::terminal_failure &&
			applied.error_code == EILSEQ,
		"corrupt ownership authority was overwritten");
	for (const fs::directory_entry &entry : fs::directory_iterator(domains))
		require(entry.path().filename().string().find(".tmp.") == std::string::npos,
			"temporary ownership file was left behind");

	std::cout << "flat-file item ownership repository passed\n";
	return 0;
}
