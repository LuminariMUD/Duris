#!/usr/bin/env python3
"""Executable round trip of the item transfer command: grants, repairs and destruction."""

from _paths import rel
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

HARNESS = r'''
#include "item/item_transfer_command.h"

#include <cassert>
namespace
{
critical_operation_id operation()
{
	critical_operation_id id = {};
	id.bytes[0] = 0xa5;
	id.bytes.back() = 0x67;
	return id;
}

bool build(critical_command *command, const item_transfer_payload &payload)
{
	if (!item_transfer_command_build(command, operation(), payload,
					 critical_source_site::command,
					 critical_deadline_class::interactive))
		return false;
	command->accepted_at_usec = 1;
	return critical_command_valid(*command);
}
} // namespace

int main()
{
	const item_owner_identity collector = { item_owner_type::collector,
						  item_collector_owner_id(987), 0 };
	assert(item_collector_owner_id(0) == 0);
	assert(item_owner_identity_valid(collector));
	assert(!item_owner_identity_valid({ item_owner_type::collector, 0, 0 }));
	assert(!item_owner_identity_valid({ item_owner_type::collector, 987, 1 }));
	critical_entity_key collector_key = {};
	assert(item_owner_key(collector, &collector_key));
	assert(collector_key.type == critical_entity_type::collector && collector_key.id == 987);

	// A grant creates a detached root for a player.
	item_transfer_payload grant = {};
	grant.from_owner = { item_owner_type::system, 0, 0 };
	grant.to_owner = { item_owner_type::player, 42, 0 };
	grant.reason = item_transfer_reason::creation;
	grant.reason_id = 500;
	grant.expected_from_revision = 3;
	grant.expected_to_revision = 9;
	grant.selected_item_uid = 100;
	grant.target_root_item_uid = 100;
	grant.item_count = 1;
	grant.items[0] = { 100, 100, 0, ITEM_TRANSFER_ABSENT_REVISION, 500,
			   item_custody_state::absent };
	grant.item_blob_size = 3;
	grant.item_blob[0] = 0x12;
	grant.item_blob[1] = 0x34;
	grant.item_blob[2] = 0x56;
	critical_command command = {};
	assert(build(&command, grant));
	assert(command.payload_version == ITEM_TRANSFER_PAYLOAD_VERSION);
	item_transfer_payload decoded = {};
	assert(item_transfer_command_decode_payload(command, &decoded));
	assert(decoded.reason == item_transfer_reason::creation && !decoded.multi_root);
	assert(item_owner_identity_equal(decoded.to_owner, grant.to_owner));
	assert(decoded.item_blob_size == 3 && decoded.item_blob[2] == 0x56);
	auto truncated = command;
	truncated.payload.resize(ITEM_TRANSFER_HEADER_BYTES + ITEM_TRANSFER_ENTRY_BYTES);
	assert(!item_transfer_command_decode_payload(truncated, &decoded));
	auto trailing = command;
	trailing.payload.push_back(0);
	assert(!item_transfer_command_decode_payload(trailing, &decoded));

	// Only grants, repairs and destruction travel as item transfers, never to or from
	// the collector.
	for (item_transfer_reason reason :
	     { item_transfer_reason::shop_buy, item_transfer_reason::player_give,
	       item_transfer_reason::corpse_loot, item_transfer_reason::pet_give,
	       item_transfer_reason::collector_buyback })
	{
		auto refused = grant;
		refused.reason = reason;
		assert(!build(&command, refused));
	}
	auto collector_repair = grant;
	collector_repair.from_owner = collector;
	collector_repair.reason = item_transfer_reason::operator_repair;
	collector_repair.items[0] = { 100, 100, 0, 5, 500, item_custody_state::active };
	assert(!build(&command, collector_repair));

	// A grant into a container the player carries.
	auto into_bag = grant;
	into_bag.target_root_item_uid = 700;
	into_bag.target_parent_item_uid = 700;
	into_bag.expected_target_parent_revision = 4;
	assert(build(&command, into_bag));
	assert(item_transfer_command_decode_payload(command, &decoded));
	assert(decoded.target_root_item_uid == 700 && decoded.target_parent_item_uid == 700 &&
	       decoded.expected_target_parent_revision == 4);

	// A starter kit's roots are created in one batch.
	item_transfer_payload kit = {};
	kit.from_owner = { item_owner_type::system, 0, 0 };
	kit.to_owner = { item_owner_type::player, 42, 0 };
	kit.reason = item_transfer_reason::creation;
	kit.expected_from_revision = 3;
	kit.expected_to_revision = 9;
	kit.multi_root = true;
	kit.item_count = 2;
	kit.items[0] = { 100, 100, 0, ITEM_TRANSFER_ABSENT_REVISION, 500,
			 item_custody_state::absent };
	kit.items[1] = { 200, 200, 0, ITEM_TRANSFER_ABSENT_REVISION, 501,
			 item_custody_state::absent };
	assert(build(&command, kit));
	assert(item_transfer_command_decode_payload(command, &decoded));
	assert(decoded.multi_root && decoded.selected_item_uid == 0 &&
	       item_transfer_result_root(decoded) == 100 &&
	       item_transfer_selected_root(decoded, 200) == 200);
	std::vector<uint64_t> selected_roots;
	assert(item_transfer_selected_roots(decoded, &selected_roots));
	assert((selected_roots == std::vector<uint64_t>{ 100, 200 }));
	uint64_t target_root = 0, target_parent = 1;
	assert(item_transfer_target_topology(decoded, 200, &target_root, &target_parent));
	assert(target_root == 200 && target_parent == 0);

	// An operator repair moves a container into another without flattening its contents.
	item_transfer_payload repair = {};
	repair.from_owner = { item_owner_type::player, 42, 0 };
	repair.to_owner = repair.from_owner;
	repair.reason = item_transfer_reason::operator_repair;
	repair.reason_id = 100;
	repair.expected_from_revision = 9;
	repair.expected_to_revision = 9;
	repair.selected_item_uid = 100;
	repair.target_root_item_uid = 900;
	repair.target_parent_item_uid = 900;
	repair.expected_target_parent_revision = 3;
	repair.item_count = 2;
	repair.items[0] = { 100, 100, 0, 5, 500, item_custody_state::active };
	repair.items[1] = { 101, 100, 100, 6, 501, item_custody_state::active };
	assert(build(&command, repair));
	assert(item_transfer_command_decode_payload(command, &decoded));
	assert(item_transfer_target_topology(decoded, 100, &target_root, &target_parent));
	assert(target_root == 900 && target_parent == 900);
	assert(item_transfer_target_topology(decoded, 101, &target_root, &target_parent));
	assert(target_root == 900 && target_parent == 100);

	// A deleted character's items are destroyed in one batch.
	item_transfer_payload deletion = {};
	deletion.from_owner = { item_owner_type::player, 42, 0 };
	deletion.to_owner = { item_owner_type::destruction, 0, 0 };
	deletion.reason = item_transfer_reason::destruction;
	deletion.expected_from_revision = 9;
	deletion.multi_root = true;
	deletion.item_count = 2;
	deletion.items[0] = { 100, 100, 0, 5, 500, item_custody_state::active };
	deletion.items[1] = { 200, 200, 0, 6, 501, item_custody_state::active };
	assert(build(&command, deletion));
	assert(command.keys.size() == 4 && command.expected_revisions.size() == 4);
	assert(item_transfer_command_decode_payload(command, &decoded));
	assert(decoded.multi_root && decoded.item_count == 2);
	return 0;
}
'''


with tempfile.TemporaryDirectory(prefix="duris-item-transfer-codec-") as temp_dir:
    source = Path(temp_dir) / "item_transfer_codec_test.cpp"
    binary = Path(temp_dir) / "item_transfer_codec_test"
    source.write_text(HARNESS)
    subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            "-Isrc",
            str(source),
            rel("item_transfer_command.c"),
            rel("player_snapshot_codec.c"),
            rel("critical_command.c"),
            "-lcrypto",
            "-o",
            str(binary),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run([str(binary)], check=True)

print("[PASS] item transfer commands carry grants, repairs and destruction")
