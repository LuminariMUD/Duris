#!/usr/bin/env python3
"""Restored world items load through the ownership filter (persistence reset step 6)."""

from _paths import rel
import pathlib
import subprocess
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]

HARNESS = r'''
#include "flatfile/flatfile_corpse_ownership.h"

#include <cassert>

uint64_t item_corpse_owner_id(uint32_t player_pid, uint32_t corpse_save_id)
{
	return player_pid && corpse_save_id ?
		       (static_cast<uint64_t>(player_pid) << 32) | corpse_save_id :
		       0;
}

bool item_owner_identity_valid(const item_owner_identity &owner)
{
	return owner.type != item_owner_type::unknown && owner.id != 0;
}

bool item_owner_identity_equal(const item_owner_identity &left,
			       const item_owner_identity &right)
{
	return left.type == right.type && left.id == right.id &&
	       left.context_id == right.context_id;
}

static item_owner_identity repository_owner = {};
static uint64_t repository_revision = 0;
static std::vector<flatfile_item_ownership_record> repository_custody;
static int skipped = 0;

flatfile_item_repository_result flatfile_item_repository_load_owner(
	const std::string &, const item_owner_identity &owner, uint64_t *revision,
	std::vector<flatfile_item_ownership_record> *custody, std::string *)
{
	assert(item_owner_identity_equal(owner, repository_owner));
	*revision = repository_revision;
	*custody = repository_custody;
	return flatfile_item_repository_result::ok;
}

flatfile_item_repository_result flatfile_item_repository_load_uids(
	const std::string &, const std::vector<uint64_t> &,
	std::vector<flatfile_item_ownership_record> *records, std::string *)
{
	*records = repository_custody;
	return flatfile_item_repository_result::ok;
}

void dupe_log_item(const char *event, uint64_t, int32_t, const item_owner_identity &,
		   const item_owner_identity &)
{
	assert(std::string(event) == "load_skipped");
	++skipped;
}

int main()
{
	player_item_snapshot root = {};
	root.object_uid = 10;
	root.vnum = 100;
	root.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	root.equipment_slot = -1;
	player_item_snapshot child = {};
	child.object_uid = 11;
	child.vnum = 101;
	child.parent_index = 0;
	child.equipment_slot = -1;
	player_item_snapshot grandchild = child;
	grandchild.object_uid = 12;
	grandchild.vnum = 102;
	grandchild.parent_index = 1;

	// A corpse record whose items the catalog gives to the corpse loads whole.
	flatfile_corpse_record record = {};
	record.owner_pid = 42;
	record.save_id = 20;
	record.revision = 3;
	record.items = { root, child };
	repository_owner = flatfile_corpse_item_owner(42, 20);
	repository_revision = 8;
	repository_custody = {
		{ 10, 10, 0, repository_owner, 4, 100, item_custody_state::active },
		{ 11, 10, 10, repository_owner, 6, 101, item_custody_state::active },
	};
	std::vector<player_item_snapshot> items;
	std::vector<player_load_item_identity> identities;
	uint64_t owner_revision = 0;
	assert(flatfile_corpse_load_item_ownership("unused", record, &items, &owner_revision,
						  &identities, nullptr) ==
	       flatfile_corpse_ownership_result::ok);
	assert(owner_revision == 8 && items.size() == 2 && identities.size() == 2 &&
	       identities[0].database_id == 1 && identities[1].serialized_parent_id == 1 &&
	       identities[1].parent_item_uid == 10 && identities[1].root_item_uid == 10 &&
	       identities[1].item_revision == 6 && identities[1].owner_revision == 8 &&
	       identities[1].override_mask == PLAYER_LOAD_ITEM_OVERRIDE_ALL);

	// A room record loads through the same filter.
	flatfile_room_item_record room = {};
	room.room_vnum = 500;
	room.revision = 2;
	room.items = record.items;
	repository_owner = { item_owner_type::room, 500, 0 };
	repository_revision = 9;
	repository_custody = {
		{ 10, 10, 0, repository_owner, 4, 100, item_custody_state::active },
		{ 11, 10, 10, repository_owner, 6, 101, item_custody_state::active },
	};
	assert(flatfile_room_load_item_ownership("unused", room, &items, &owner_revision,
						&identities, nullptr) ==
	       flatfile_corpse_ownership_result::ok);
	assert(owner_revision == 9 && identities.size() == 2 &&
	       identities[1].parent_item_uid == 10 && identities[1].owner_revision == 9);

	// A stale copy another owner holds is skipped and logged, and what it held moves to
	// the top level; an item nobody has recorded is taken.
	record.items = { root, child, grandchild };
	repository_owner = flatfile_corpse_item_owner(42, 20);
	repository_custody = {
		{ 10, 10, 0, repository_owner, 4, 100, item_custody_state::active },
		{ 11, 11, 0, { item_owner_type::player, 42, 0 }, 7, 101, item_custody_state::active },
	};
	assert(flatfile_corpse_load_item_ownership("unused", record, &items, &owner_revision,
						  &identities, nullptr) ==
	       flatfile_corpse_ownership_result::ok);
	assert(skipped == 1 && items.size() == 2 && items[1].object_uid == 12 &&
	       items[1].parent_index == PLAYER_SNAPSHOT_NO_PARENT &&
	       identities[1].root_item_uid == 12 && identities[1].parent_item_uid == 0 &&
	       identities[1].item_revision == 0);

	// A malformed record still refuses.
	record.items = { root, child };
	record.items[1].equipment_slot = 0;
	assert(flatfile_corpse_load_item_ownership("unused", record, &items, &owner_revision,
						  &identities, nullptr) ==
	       flatfile_corpse_ownership_result::invalid);
	return 0;
}
'''

with tempfile.TemporaryDirectory(prefix="duris-flatfile-corpse-ownership-") as temporary:
    temporary_path = pathlib.Path(temporary)
    source = temporary_path / "harness.cpp"
    binary = temporary_path / "harness"
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
            rel("flatfile_corpse_ownership.c"),
            "-o",
            str(binary),
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run([str(binary)], check=True)

print("[PASS] world restore takes what the catalog gives the corpse or room and skips stale copies")
