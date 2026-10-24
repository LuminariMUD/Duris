#include "flatfile/flatfile_shopkeeper_restore.h"
#include "flatfile/flatfile_shopkeeper_capture.h"
#include "flatfile/flatfile_shopkeeper_ownership.h"
#include "flatfile/flatfile_item_repository.h"
#include "economy/shop_trade_runtime.h"
#include "core/prototypes.h"
#include "core/structs.h"
#include <cassert>
#include <filesystem>
#include <fstream>
#include <iostream>

namespace fs = std::filesystem;
shop_data shops[4]{};
shop_data *shop_index = shops;
int number_of_shops = 2, top_of_objt = 3, top_of_world = 3;
index_data mobs[4]{}, objects[4]{};
P_index mob_index = mobs, obj_index = objects;
room_data rooms[4]{};
P_room world = rooms;
char_data keepers[4]{};
uint64_t uids[] = { 100, 101, 102, 103 };
int captures[4]{}, costs[] = { 20, 21, 22, 23 };
int real_mobile(int vnum)
{
	return vnum >= 1000 && vnum < 1004 ? vnum - 1000 : -1;
}
int real_room(int vnum)
{
	return vnum >= 2000 && vnum < 2004 ? vnum - 2000 : -1;
}
std::vector<P_char> live_shopkeepers(int shop)
{
	return { &keepers[shop] };
}
player_snapshot_capture_result flatfile_shopkeeper_capture(P_char keeper, uint32_t id,
							   uint64_t revision, int64_t saved_at,
							   flatfile_shopkeeper_record *out)
{
	assert(keeper == &keepers[id]);
	++captures[id];
	player_item_snapshot item{};
	item.object_uid = uids[id];
	item.vnum = 3000 + id;
	item.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	item.name = "shop stock";
	item.short_description = "shop stock";
	item.cost = costs[id];
	*out = {};
	out->shop_id = id;
	out->mob_vnum = 1000 + id;
	out->room_vnum = 2000 + id;
	out->revision = revision;
	out->saved_at = saved_at;
	out->items = { item };
	return player_snapshot_capture_result::ok;
}
static std::string catalog_bytes(const fs::path &root)
{
	std::ifstream input(root / "domains/shopkeeper_catalog", std::ios::binary);
	return { std::istreambuf_iterator<char>(input), {} };
}
int main(int argc, char **argv)
{
	assert(argc == 2);
	const fs::path root = argv[1];
	fs::create_directories(root / "domains");
	fs::permissions(root, fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(root / "domains", fs::perms::owner_all, fs::perm_options::replace);
	for (int index = 0; index < 4; ++index)
	{
		shops[index].keeper = index;
		shops[index].in_room = 2000 + index;
		shops[index].number_items_produced = 1;
		shops[index].producing[0] = index;
		mobs[index].virtual_number = 1000 + index;
		objects[index].virtual_number = 3000 + index;
		rooms[index].number = 2000 + index;
	}
	std::string error;
	assert(flatfile_shopkeeper_bootstrap_new(root.string(), &error));
	for (uint32_t index = 0; index < 2; ++index)
	{
		uint64_t revision = 0;
		std::vector<flatfile_item_ownership_record> held;
		const auto owner = flatfile_shopkeeper_item_owner(index);
		assert(flatfile_item_repository_load_owner(root.string(), owner, &revision, &held,
							   &error) ==
		       flatfile_item_repository_result::ok);
		assert(revision == 1 && held.size() == 1 && held[0].item_uid == uids[index]);
		item_ownership_runtime_entry live{};
		assert(item_ownership_runtime_lookup(uids[index], &live) &&
		       item_owner_identity_equal(live.owner, owner));
		assert(shop_trade_runtime_revision(index, &revision) && revision == 1);
	}
	const auto initial = catalog_bytes(root);
	costs[0] = 999;
	assert(flatfile_shopkeeper_bootstrap_new(root.string(), &error));
	assert(initial == catalog_bytes(root) && captures[0] == 1 && captures[1] == 1);
	number_of_shops = 3;
	assert(flatfile_shopkeeper_bootstrap_new(root.string(), &error));
	std::vector<flatfile_shopkeeper_record> saved;
	assert(flatfile_shopkeeper_list(root.string(), &saved, &error) ==
	       flatfile_shopkeeper_result::ok);
	assert(saved.size() == 3 && saved[0].items[0].cost == 20 &&
	       saved[2].items[0].object_uid == 102);
	assert(captures[0] == 1 && captures[2] == 1);
	const auto appended = catalog_bytes(root);
	number_of_shops = 4;
	uids[3] = 100;
	assert(!flatfile_shopkeeper_bootstrap_new(root.string(), &error));
	assert(appended == catalog_bytes(root));
	uids[3] = 999;
	const item_owner_identity player = { item_owner_type::player, 42, 0 };
	flatfile_item_ownership_record owned = {
		999, 999, 0, player, 1, 3003, item_custody_state::active
	};
	assert(flatfile_item_repository_establish_owner(root.string(), player, { owned }, &error) ==
	       flatfile_item_baseline_result::applied);
	assert(!flatfile_shopkeeper_bootstrap_new(root.string(), &error));
	assert(appended == catalog_bytes(root));
	uint64_t revision = 0;
	std::vector<flatfile_item_ownership_record> held;
	assert(flatfile_item_repository_load_owner(root.string(), player, &revision, &held,
						   &error) == flatfile_item_repository_result::ok);
	assert(held.size() == 1 && held[0].item_uid == 999 && revision == 1);
	std::cout
		<< "fresh/additive shop bootstrap preserves stock, custody and retry state; collisions leave no partial shop\n";
}
