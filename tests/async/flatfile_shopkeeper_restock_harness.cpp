#include "flatfile/flatfile_shopkeeper_restore.h"
#include "flatfile/flatfile_shopkeeper_materialize.h"
#include "flatfile/flatfile_shopkeeper_ownership.h"
#include "player/player_snapshot_capture.h"
#include "item/item_ownership_runtime.h"
#include "core/utils.h"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <iostream>

namespace fs = std::filesystem;
shop_data shops[1]{};
shop_data *shop_index = shops;
index_data mobs[1]{};
P_index mob_index = mobs;
char_data fresh{}, restored{};
npc_only_data npc{};

std::vector<P_char> live_shopkeepers(int shop)
{
	assert(shop == 0);
	return { &fresh };
}
int shop_producing(P_obj object, int)
{
	return object->R_num == 0;
}
void obj_to_char(P_obj object, P_char keeper)
{
	object->next_content = keeper->carrying;
	keeper->carrying = object;
	object->loc_p = LOC_CARRIED;
	object->loc.carrying = keeper;
}
void obj_from_char(P_obj object)
{
	P_obj *link = &object->loc.carrying->carrying;
	while (*link != object)
	{
		assert(*link);
		link = &(*link)->next_content;
	}
	*link = object->next_content;
	object->next_content = nullptr;
	object->loc_p = LOC_NOWHERE;
}
player_item_snapshot snapshot(P_obj object, int32_t parent)
{
	player_item_snapshot item{};
	item.object_uid = object->obj_uid;
	item.vnum = 3000 + object->R_num;
	item.cost = object->cost;
	item.parent_index = parent;
	return item;
}
player_snapshot_capture_result
player_item_snapshot_tree_capture(P_obj object, std::vector<player_item_snapshot> *out, size_t *)
{
	out->push_back(snapshot(object, PLAYER_SNAPSHOT_NO_PARENT));
	if (object->contains)
		out->push_back(snapshot(object->contains, 0));
	return player_snapshot_capture_result::ok;
}
std::string bytes(const fs::path &file)
{
	std::ifstream input(file, std::ios::binary);
	return { std::istreambuf_iterator<char>(input), {} };
}
void discard(P_obj object)
{
	while (object)
	{
		auto *next = object->next_content;
		discard(object->contains);
		delete object;
		object = next;
	}
}
P_obj add(P_char owner, int rnum, uint64_t uid)
{
	P_obj object = new obj_data{};
	object->R_num = rnum;
	object->obj_uid = uid;
	object->cost = 777;
	obj_to_char(object, owner);
	return object;
}
void boot_stock(uint64_t first_uid)
{
	add(&fresh, 0, first_uid);
	add(&fresh, 2, first_uid + 1);
	add(&fresh, 2, first_uid + 2);
	P_obj bag = add(&fresh, 1, first_uid + 3);
	bag->contains = new obj_data{};
	bag->contains->obj_uid = first_uid + 4;
	bag->contains->R_num = 3;
	bag->contains->loc_p = LOC_INSIDE;
	bag->contains->loc.inside = bag;
}
int main(int argc, char **argv)
{
	assert(argc == 3);
	const std::string mode = argv[2];
	const fs::path root = argv[1];
	fs::create_directories(root / "domains");
	fs::permissions(root, fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(root / "domains", fs::perms::owner_all, fs::perm_options::replace);
	fresh.specials.act = ACT_ISNPC;
	fresh.only.npc = &npc;
	fresh.in_room = 0;
	mobs[0].virtual_number = 1000;
	shops[0].in_room = 2000;
	flatfile_shopkeeper_record record{};
	record.mob_vnum = 1000;
	record.room_vnum = 2000;
	record.revision = 1;
	for (int rnum : { 0, 2, 3 })
		record.items.push_back(
			snapshot(add(&restored, rnum, 100 + rnum), PLAYER_SNAPSHOT_NO_PARENT));
	// Equipped bags are retained but are not loose stock.
	obj_data equipment{};
	equipment.obj_uid = 104;
	equipment.R_num = 1;
	record.items.push_back(snapshot(&equipment, PLAYER_SNAPSHOT_NO_PARENT));
	record.items.back().equipment_slot = 1;
	std::string error;
	assert(flatfile_shopkeeper_establish(root.string(), { record }, &error) ==
	       flatfile_shopkeeper_result::ok);
	const auto owner = flatfile_shopkeeper_item_owner(0);
	{
		flatfile_authority_lock lock;
		assert(lock.acquire(root.string(), &error));
		std::vector<flatfile_item_claim> claims = { { owner, &record.items, {}, true } };
		flatfile_authority_operation custody;
		std::vector<flatfile_item_claim_audit> audits;
		assert(flatfile_item_repository_prepare_claim(root.string(), lock, &claims,
							      &custody, &audits, &error) ==
		       flatfile_item_repository_result::ok);
		assert(flatfile_authority_transaction_commit_operations(root.string(), lock,
									{ custody }, &error) ==
		       flatfile_authority_transaction_result::ok);
	}
	boot_stock(200);
	if (mode == "collision")
		fresh.carrying->obj_uid = 100;
	std::vector<flatfile_shopkeeper_record> records{ record };
	if (mode == "stale")
		++records[0].revision;
	flatfile_materialized_shopkeeper staged{};
	staged.character = &restored;
	staged.room_rnum = 0;
	staged.owner_revision = 1;
	const auto before = bytes(root / "domains/shopkeeper_catalog");
	const auto custody_before = bytes(root / "domains/item_ownership");
	if (mode == "storage-failure")
		fs::permissions(root / "domains", fs::perms::owner_read | fs::perms::owner_exec,
				fs::perm_options::replace);
	if (mode == "publication-failure")
		assert(item_ownership_runtime_hydrate_owner(owner, 100));
	const bool good = flatfile_shopkeeper_restock(root.string(), &records, { staged }, &error);
	fs::permissions(root / "domains", fs::perms::owner_all, fs::perm_options::replace);
	if (mode == "collision" || mode == "stale" || mode == "storage-failure")
	{
		assert(!good && bytes(root / "domains/shopkeeper_catalog") == before);
		assert(bytes(root / "domains/item_ownership") == custody_before);
		assert(fresh.carrying->R_num == 1 && fresh.carrying->contains);
	}
	else
	{
		assert(good == (mode != "publication-failure"));
		assert(records[0].revision == 2 && records[0].items.size() == 7);
		std::vector<flatfile_shopkeeper_record> saved;
		assert(flatfile_shopkeeper_list(root.string(), &saved, &error) ==
		       flatfile_shopkeeper_result::ok);
		assert(saved[0].revision == 2 && saved[0].items.size() == 7);
		assert(saved[0].items[0].object_uid == 100 && saved[0].items[0].cost == 777);
		uint64_t revision = 0;
		std::vector<player_load_item_identity> identities;
		assert(flatfile_shopkeeper_load_item_ownership(root.string(), saved[0], &revision,
							       &identities, &error) ==
		       flatfile_shopkeeper_ownership_result::ok);
		assert(revision == 2 && identities.size() == 7);
		if (mode == "publication-failure")
		{
			// A retry after process restart reads the committed stock and custody.
			item_ownership_runtime_reset();
			assert(flatfile_shopkeeper_publish_ownership(root.string(), saved[0],
								     &error));
		}
		item_ownership_runtime_entry entry{};
		assert(item_ownership_runtime_lookup(204, &entry) && entry.parent_item_uid == 203 &&
		       entry.root_item_uid == 203);
		discard(fresh.carrying);
		fresh.carrying = nullptr;
		boot_stock(300);
		staged.owner_revision = revision;
		const auto after = bytes(root / "domains/shopkeeper_catalog");
		assert(flatfile_shopkeeper_restock(root.string(), &saved, { staged }, &error));
		assert(bytes(root / "domains/shopkeeper_catalog") == after);
	}
	discard(fresh.carrying);
	discard(restored.carrying);
	std::cout << "flat-file shop stock/custody: " << mode << " passed\n";
}
