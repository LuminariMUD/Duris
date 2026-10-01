#!/usr/bin/env python3
"""Runtime regressions for the live item ownership cache."""

from _paths import rel
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

HARNESS = r'''
#include "item/item_ownership_runtime.h"
#include "economy/collector_command.h"

#include <cassert>

int main()
{
	const item_transfer_result extended = { 100, 1, 11, 1, 6, 7, true };
	std::array<uint8_t, ITEM_TRANSFER_RESULT_BYTES> encoded = {};
	assert(item_transfer_command_encode_result(extended, &encoded));
	item_transfer_result decoded = {};
	assert(item_transfer_command_decode_result(encoded.data(), encoded.size(), &decoded));
	assert(decoded.corpse_revision == 7 && decoded.collector_catalog_changed);
	encoded[10] = 2;
	assert(!item_transfer_command_decode_result(encoded.data(), encoded.size(), &decoded));
	item_ownership_runtime_reset();
	{
		const item_owner_identity batch_player = { item_owner_type::player, 900, 0 };
		const item_owner_identity system = { item_owner_type::system, 0, 0 };
		assert(item_ownership_runtime_hydrate_owner(system, 0));
		assert(item_ownership_runtime_hydrate_owner(batch_player, 0));
		item_transfer_payload batch = {};
		batch.from_owner = system;
		batch.to_owner = batch_player;
		batch.reason = item_transfer_reason::creation;
		batch.multi_root = true;
		batch.item_count = 2;
		batch.items[0] = { 603, 603, 0, ITEM_TRANSFER_ABSENT_REVISION, 1603,
					   item_custody_state::absent };
		batch.items[1] = { 604, 604, 0, ITEM_TRANSFER_ABSENT_REVISION, 1604,
					   item_custody_state::absent };
		assert(item_ownership_runtime_apply(batch, { 603, 2, 1, 1, 1, 0 }));

		// The second root conflicts with the already-published 603 root. A failed
		// batch must not leave the new 602 root or advance the owner revision.
		item_transfer_payload conflicting = batch;
		conflicting.items[0] = { 602, 602, 0, ITEM_TRANSFER_ABSENT_REVISION, 1602,
						 item_custody_state::absent };
		conflicting.items[1] = batch.items[0];
		assert(!item_ownership_runtime_apply(conflicting, { 602, 2, 2, 2, 1, 0 }));
		item_ownership_runtime_entry absent = {};
		assert(!item_ownership_runtime_lookup(602, &absent));
		uint64_t owner_revision = 0;
		assert(item_ownership_runtime_owner_revision(batch_player, &owner_revision) &&
		       owner_revision == 1);
	}
	const item_owner_identity player = { item_owner_type::player, 42, 0 };
	const item_owner_identity room = { item_owner_type::room, 1200, 0 };
	const item_ownership_runtime_entry inventory[] = {
		{ 100, 100, 0, player, 5, 10, 7, item_custody_state::active },
		{ 101, 101, 0, player, 3, 10, 8, item_custody_state::active },
	};
	assert(item_ownership_runtime_hydrate_batch(inventory, 2));

	item_transfer_payload move = {};
	move.from_owner = player;
	move.to_owner = room;
	move.selected_item_uid = 100;
	move.target_root_item_uid = 100;
	move.item_count = 1;
	move.items[0] = { 100, 100, 0, 5, 7, item_custody_state::active };
	const item_transfer_result committed = { 100, 1, 11, 1, 6, 0 };
	assert(item_ownership_runtime_apply(move, committed));

	item_ownership_runtime_entry untouched = {};
	assert(item_ownership_runtime_lookup(101, &untouched));
	assert(untouched.item_revision == 3 && untouched.owner_revision == 10);

	const item_ownership_runtime_entry authoritative = {
		101, 101, 0, player, 3, 11, 8, item_custody_state::active
	};
	assert(item_ownership_runtime_hydrate_batch(&authoritative, 1));
	assert(item_ownership_runtime_lookup(101, &untouched));
	assert(untouched.owner_revision == 11);
	item_transfer_payload creation = {};
	creation.from_owner = { item_owner_type::system, 0, 0 };
	creation.to_owner = player;
	creation.selected_item_uid = 200;
	creation.target_root_item_uid = 101;
	creation.target_parent_item_uid = 101;
	creation.expected_target_parent_revision = 3;
	creation.item_count = 1;
	creation.items[0] = { 200, 200, 0, ITEM_TRANSFER_ABSENT_REVISION, 9,
			      item_custody_state::absent };
	assert(item_ownership_runtime_apply(creation, { 200, 1, 1, 12, 1, 0 }));
	item_ownership_runtime_entry created = {};
	assert(item_ownership_runtime_lookup(200, &created));
	assert(created.root_item_uid == 101 && created.parent_item_uid == 101 &&
	       created.owner_revision == 12);
	// A player holds its containers in memory, so a grant into one that the cache
	// last saw at another revision is learned, not refused.
	creation.selected_item_uid = 201;
	creation.items[0].item_uid = 201;
	creation.expected_target_parent_revision = 2;
	assert(item_ownership_runtime_apply(creation, { 201, 1, 2, 12, 1, 0 }));

	const item_ownership_runtime_entry stale = {
		101, 101, 0, player, 3, 10, 8, item_custody_state::active
	};
	assert(!item_ownership_runtime_hydrate_batch(&stale, 1));

	const item_owner_identity locker = { item_owner_type::locker, 77, 0 };
	const item_ownership_runtime_entry rejected_atomic[] = {
		{ 202, 202, 0, room, 1, 1, 9, item_custody_state::active },
		{ 101, 101, 0, player, 3, 10, 8, item_custody_state::active },
	};
	assert(!item_ownership_runtime_hydrate_many_atomic(rejected_atomic, 2));
	item_ownership_runtime_entry absent = {};
	uint64_t owner_revision = 0;
	assert(!item_ownership_runtime_lookup(202, &absent));

	const item_ownership_runtime_entry accepted_atomic[] = {
		{ 202, 202, 0, room, 1, 1, 9, item_custody_state::active },
		{ 203, 203, 0, locker, 2, 4, 10, item_custody_state::active },
	};
	assert(item_ownership_runtime_hydrate_many_atomic(accepted_atomic, 2));
	assert(item_ownership_runtime_lookup(202, &absent));
	assert(absent.owner.type == item_owner_type::room && absent.owner.id == 1200);
	assert(item_ownership_runtime_lookup(203, &absent));
	assert(absent.owner.type == item_owner_type::locker && absent.owner.id == 77);

	const item_ownership_runtime_entry second_inventory = {
		204, 204, 0, player, 4, 12, 11, item_custody_state::active
	};
	assert(item_ownership_runtime_hydrate_batch(&second_inventory, 1));
	item_transfer_payload batch = {};
	batch.from_owner = player;
	batch.to_owner = room;
	batch.reason = item_transfer_reason::operator_repair;
	batch.expected_from_revision = 12;
	batch.expected_to_revision = 1;
	batch.multi_root = true;
	batch.item_count = 2;
	batch.items[0] = { 101, 101, 0, 3, 8, item_custody_state::active };
	batch.items[1] = { 204, 204, 0, 4, 11, item_custody_state::active };
	assert(item_ownership_runtime_apply(batch, { 101, 2, 13, 2, 5, 0 }));
	assert(item_ownership_runtime_lookup(101, &absent) &&
	       item_owner_identity_equal(absent.owner, room) && absent.root_item_uid == 101 &&
	       absent.parent_item_uid == 0 && absent.item_revision == 4);
	assert(item_ownership_runtime_lookup(204, &absent) &&
	       item_owner_identity_equal(absent.owner, room) && absent.root_item_uid == 204 &&
	       absent.parent_item_uid == 0 && absent.item_revision == 5);

	item_ownership_runtime_reset();
	const item_owner_identity collector_corpse = {
		item_owner_type::corpse, item_corpse_owner_id(90, 60), 0
	};
	const item_owner_identity collector = {
		item_owner_type::collector, item_collector_owner_id(77), 0
	};
	const item_ownership_runtime_entry collector_source[] = {
		{ 800, 800, 0, collector_corpse, 1, 9, 70, item_custody_state::active },
		{ 801, 800, 800, collector_corpse, 2, 9, 71, item_custody_state::active },
		{ 802, 800, 801, collector_corpse, 3, 9, 72, item_custody_state::active },
		{ 803, 800, 800, collector_corpse, 4, 9, 73, item_custody_state::active },
	};
	assert(item_ownership_runtime_hydrate_batch(collector_source, 4));
	assert(item_ownership_runtime_hydrate_owner(collector, 0));
	collector_command_payload collect = {};
	collect.action = collector_action::collect;
	collect.listing = 77;
	collect.selected_item_uid = 801;
	collect.from_owner = collector_corpse;
	collect.to_owner = collector;
	collect.expected_from_owner_revision = 9;
	collect.expected_to_owner_revision = 0;
	collect.target_state = item_custody_state::active;
	collect.item_count = 4;
	collect.items[0] = { 800, 800, 0, 1, 70, item_custody_state::active };
	collect.items[1] = { 801, 800, 800, 2, 71, item_custody_state::active };
	collect.items[2] = { 802, 800, 801, 3, 72, item_custody_state::active };
	collect.items[3] = { 803, 800, 800, 4, 73, item_custody_state::active };
	collector_command_result collected = {};
	collected.action = collector_action::collect;
	collected.record_present = true;
	collected.from_owner_revision = 10;
	collected.to_owner_revision = 1;
	collected.entry.listing = 77;
	collected.entry.uid = 801;
	collected.entry.item_revision = 3;
	assert(item_ownership_runtime_apply_collector(collect, collected));
	assert(item_ownership_runtime_apply_collector(collect, collected));
	assert(item_ownership_runtime_lookup(800, &absent) && absent.root_item_uid == 800 &&
	       absent.parent_item_uid == 0 && absent.item_revision == 2 &&
	       item_owner_identity_equal(absent.owner, collector_corpse));
	assert(item_ownership_runtime_lookup(801, &absent) && absent.root_item_uid == 801 &&
	       absent.parent_item_uid == 0 && absent.item_revision == 3 &&
	       item_owner_identity_equal(absent.owner, collector));
	assert(item_ownership_runtime_lookup(802, &absent) && absent.root_item_uid == 800 &&
	       absent.parent_item_uid == 800 && absent.item_revision == 4 &&
	       item_owner_identity_equal(absent.owner, collector_corpse));
	assert(item_ownership_runtime_lookup(803, &absent) && absent.root_item_uid == 800 &&
	       absent.parent_item_uid == 800 && absent.item_revision == 5);

	const item_owner_identity collector_destruction = { item_owner_type::destruction, 0, 0 };
	assert(item_ownership_runtime_hydrate_owner(collector_destruction, 0));
	collector_command_payload expire = {};
	expire.action = collector_action::expire;
	expire.listing = 77;
	expire.selected_item_uid = 801;
	expire.from_owner = collector;
	expire.to_owner = collector_destruction;
	expire.expected_from_owner_revision = 1;
	expire.expected_to_owner_revision = 0;
	expire.target_state = item_custody_state::destroyed;
	expire.item_count = 1;
	expire.items[0] = { 801, 801, 0, 3, 71, item_custody_state::active };
	collector_command_result expired = {};
	expired.action = collector_action::expire;
	expired.record_present = true;
	expired.from_owner_revision = 2;
	expired.to_owner_revision = 1;
	expired.entry.listing = 77;
	expired.entry.uid = 801;
	expired.entry.item_revision = 4;
	assert(item_ownership_runtime_apply_collector(expire, expired));
	assert(item_ownership_runtime_apply_collector(expire, expired));
	assert(item_ownership_runtime_lookup(801, &absent) &&
	       item_owner_identity_equal(absent.owner, collector_destruction) &&
	       absent.state == item_custody_state::destroyed && absent.item_revision == 4);

	// Collecting a root turns each direct child subtree into its own root. The
	// source root does not need to be the smallest UID in the sorted command.
	item_ownership_runtime_reset();
	const item_owner_identity root_corpse = {
		item_owner_type::corpse, item_corpse_owner_id(91, 61), 0
	};
	const item_owner_identity root_collector = {
		item_owner_type::collector, item_collector_owner_id(78), 0
	};
	const item_ownership_runtime_entry root_source[] = {
		{ 901, 905, 905, root_corpse, 5, 12, 81, item_custody_state::active },
		{ 902, 905, 901, root_corpse, 6, 12, 82, item_custody_state::active },
		{ 903, 905, 905, root_corpse, 7, 12, 83, item_custody_state::active },
		{ 905, 905, 0, root_corpse, 8, 12, 85, item_custody_state::active },
	};
	assert(item_ownership_runtime_hydrate_batch(root_source, 4));
	assert(item_ownership_runtime_hydrate_owner(root_collector, 0));
	collector_command_payload collect_root = {};
	collect_root.action = collector_action::collect;
	collect_root.listing = 78;
	collect_root.selected_item_uid = 905;
	collect_root.from_owner = root_corpse;
	collect_root.to_owner = root_collector;
	collect_root.expected_from_owner_revision = 12;
	collect_root.expected_to_owner_revision = 0;
	collect_root.target_state = item_custody_state::active;
	collect_root.item_count = 4;
	collect_root.items[0] = { 901, 905, 905, 5, 81, item_custody_state::active };
	collect_root.items[1] = { 902, 905, 901, 6, 82, item_custody_state::active };
	collect_root.items[2] = { 903, 905, 905, 7, 83, item_custody_state::active };
	collect_root.items[3] = { 905, 905, 0, 8, 85, item_custody_state::active };
	collector_command_result root_collected = {};
	root_collected.action = collector_action::collect;
	root_collected.record_present = true;
	root_collected.from_owner_revision = 13;
	root_collected.to_owner_revision = 1;
	root_collected.entry.listing = 78;
	root_collected.entry.uid = 905;
	root_collected.entry.item_revision = 9;
	assert(item_ownership_runtime_apply_collector(collect_root, root_collected));
	assert(item_ownership_runtime_lookup(901, &absent) && absent.root_item_uid == 901 &&
	       !absent.parent_item_uid && absent.item_revision == 6 &&
	       item_owner_identity_equal(absent.owner, root_corpse));
	assert(item_ownership_runtime_lookup(902, &absent) && absent.root_item_uid == 901 &&
	       absent.parent_item_uid == 901 && absent.item_revision == 7);
	assert(item_ownership_runtime_lookup(903, &absent) && absent.root_item_uid == 903 &&
	       !absent.parent_item_uid && absent.item_revision == 8);
	assert(item_ownership_runtime_lookup(905, &absent) && absent.root_item_uid == 905 &&
	       !absent.parent_item_uid && absent.item_revision == 9 &&
	       item_owner_identity_equal(absent.owner, root_collector));

	// Reconciliation atomically replaces only the collector domain. It removes
	// orphaned prior listings, advances retained authority, and preserves every
	// unrelated owner.
	item_ownership_runtime_reset();
	const item_owner_identity reconcile_player = { item_owner_type::player, 7000, 0 };
	const item_owner_identity old_collector_one = { item_owner_type::collector, 91, 0 };
	const item_owner_identity old_collector_two = { item_owner_type::collector, 92, 0 };
	const item_ownership_runtime_entry before_reconcile[] = {
		{ 800, 800, 0, reconcile_player, 4, 6, 1800, item_custody_state::active },
		{ 801, 801, 0, old_collector_one, 2, 3, 1801, item_custody_state::active },
		{ 802, 802, 0, old_collector_two, 5, 7, 1802, item_custody_state::active },
	};
	assert(item_ownership_runtime_hydrate_many_atomic(before_reconcile, 3));
	const item_ownership_runtime_entry reconciled[] = {
		{ 801, 801, 0, old_collector_one, 3, 4, 1801, item_custody_state::active },
		{ 803, 803, 0, { item_owner_type::collector, 93, 0 }, 1, 1, 1803,
		  item_custody_state::active },
	};
	assert(item_ownership_runtime_reconcile_collector(reconciled, 2));
	assert(item_ownership_runtime_lookup(800, &absent) &&
	       item_owner_identity_equal(absent.owner, reconcile_player));
	assert(item_ownership_runtime_lookup(801, &absent) && absent.item_revision == 3 &&
	       absent.owner_revision == 4);
	assert(!item_ownership_runtime_lookup(802, &absent));
	assert(item_ownership_runtime_lookup(803, &absent) && absent.vnum == 1803);
	const item_ownership_runtime_entry duplicate_owner[] = {
		reconciled[0],
		{ 804, 804, 0, old_collector_one, 1, 4, 1804, item_custody_state::active },
	};
	assert(!item_ownership_runtime_reconcile_collector(duplicate_owner, 2));
	assert(item_ownership_runtime_lookup(803, &absent));
	const item_ownership_runtime_entry stale_collector = {
		801, 801, 0, old_collector_one, 2, 3, 1801, item_custody_state::active
	};
	assert(!item_ownership_runtime_reconcile_collector(&stale_collector, 1));
	assert(item_ownership_runtime_lookup(801, &absent) && absent.item_revision == 3);
	assert(item_ownership_runtime_reconcile_collector(nullptr, 0));
	assert(!item_ownership_runtime_lookup(801, &absent));
	assert(!item_ownership_runtime_lookup(803, &absent));
	assert(item_ownership_runtime_lookup(800, &absent));

	item_ownership_runtime_reset();
	const item_owner_identity deleted_player = { item_owner_type::player, 80, 0 };
	const item_owner_identity deleted_corpse = {
		item_owner_type::corpse, item_corpse_owner_id(80, 50), 0
	};
	const item_owner_identity retained_player = { item_owner_type::player, 81, 0 };
	const item_ownership_runtime_entry deletion_domain[] = {
		{ 700, 700, 0, deleted_player, 1, 2, 60, item_custody_state::active },
		{ 701, 701, 0, deleted_corpse, 1, 3, 61, item_custody_state::active },
		{ 702, 702, 0, retained_player, 1, 4, 62, item_custody_state::active },
	};
	assert(item_ownership_runtime_hydrate_many_atomic(deletion_domain, 3));
	item_ownership_runtime_forget_player_domain(80);
	assert(!item_ownership_runtime_lookup(700, &absent));
	assert(!item_ownership_runtime_lookup(701, &absent));
	/* Missing valid owners are rehydrated at revision zero by the lookup API. */
	assert(item_ownership_runtime_owner_revision(deleted_player, &owner_revision) &&
	       owner_revision == 0);
	assert(item_ownership_runtime_owner_revision(deleted_corpse, &owner_revision) &&
	       owner_revision == 0);
	assert(item_ownership_runtime_lookup(702, &absent) &&
	       item_owner_identity_equal(absent.owner, retained_player));
	assert(item_ownership_runtime_owner_revision(retained_player, &owner_revision) &&
	       owner_revision == 4);
	{
		uint64_t owner_after = 0;
		assert(item_ownership_runtime_owner_revision(player, &owner_after));
		// A move out of a player at a revision the cache did not see is learned too.
		const item_ownership_runtime_entry dropped = {
			150, 150, 0, player, 4, owner_after, 7, item_custody_state::active
		};
		assert(item_ownership_runtime_hydrate(dropped));
		item_transfer_payload learned = move;
		learned.to_owner = { item_owner_type::room, 1300, 0 };
		learned.selected_item_uid = 150;
		learned.target_root_item_uid = 150;
		learned.items[0] = { 150, 150, 0, 99, 7, item_custody_state::active };
		item_ownership_runtime_entry moved = {};
		assert(item_ownership_runtime_apply(learned, { 150, 1, owner_after + 1, 2, 9, 0 }));
		assert(item_ownership_runtime_lookup(150, &moved) && moved.item_revision == 9 &&
		       item_owner_identity_equal(moved.owner, learned.to_owner));
		item_ownership_runtime_forget(150);
	}
	return 0;
}
'''


with tempfile.TemporaryDirectory(prefix="duris-item-ownership-runtime-") as temp_dir:
	source = Path(temp_dir) / "item_ownership_runtime_test.cpp"
	binary = Path(temp_dir) / "item_ownership_runtime_test"
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
			rel("item_ownership_runtime.c"),
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

print("[PASS] authoritative reload and multi-owner hydration are transactional")
