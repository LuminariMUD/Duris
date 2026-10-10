#include "economy/collector_collection_preparation.h"

#include "classes/necromancy.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "item/item_ownership_runtime.h"
#include "player/player_snapshot_capture.h"
#include "player/player_snapshot_codec.h"

#include <algorithm>
#include <cassert>
#include <cstdarg>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>

extern P_obj object_list;

namespace
{
index_data indexes[8] = {};
room_data rooms[1] = {};
obj_data root = {}, selected = {}, child = {}, sibling = {}, corpse = {};
bool extracted = false;

void link_inside(P_obj object, P_obj parent, P_obj next = nullptr)
{
	object->loc_p = LOC_INSIDE;
	object->loc.inside = parent;
	object->next_content = next;
}

collector::record candidate_record()
{
	collector::rules rules;
	rules.enabled = true;
	collector::record entry;
	// Player 42 died at 12, the save id of the corpse below.
	assert(collector::enroll(77, "123456789abcdef0123456789abcdef0", 42, selected.obj_uid, 2,
				 12, rules, &entry) == collector::outcome::applied);
	return entry;
}

// A player's corpse on the floor holds root, which holds selected (with child) and sibling.
void seed_corpse_tree()
{
	extracted = false;
	root = {};
	selected = {};
	child = {};
	sibling = {};
	corpse = {};
	for (int index = 0; index < 8; ++index)
		indexes[index].virtual_number = 500 + index;
	corpse.obj_uid = 200;
	corpse.R_num = 4;
	corpse.type = ITEM_CORPSE;
	corpse.value[CORPSE_FLAGS] = PC_CORPSE;
	corpse.value[CORPSE_PID] = 42;
	corpse.value[CORPSE_SAVEID] = 12;
	corpse.loc_p = LOC_ROOM;
	corpse.loc.room = 0;
	corpse.contains = &root;
	root.obj_uid = 100;
	root.R_num = 0;
	root.type = ITEM_CONTAINER;
	root.weight = 20;
	link_inside(&root, &corpse);
	selected.obj_uid = 101;
	selected.R_num = 1;
	selected.type = ITEM_CONTAINER;
	selected.wear_flags = ITEM_TAKE;
	selected.weight = 7;
	selected.cost = 75;
	selected.condition = 83;
	selected.name = const_cast<char *>("blade collector");
	child.obj_uid = 102;
	child.R_num = 2;
	child.type = ITEM_WEAPON;
	child.wear_flags = ITEM_TAKE;
	child.weight = 2;
	child.name = const_cast<char *>("gem");
	sibling.obj_uid = 103;
	sibling.R_num = 3;
	sibling.type = ITEM_WEAPON;
	sibling.wear_flags = ITEM_TAKE;
	sibling.weight = 3;
	sibling.name = const_cast<char *>("sibling");
	root.contains = &selected;
	link_inside(&selected, &root, &sibling);
	selected.contains = &child;
	link_inside(&child, &selected);
	link_inside(&sibling, &root);
	corpse.next = &root;
	root.prev = &corpse;
	root.next = &selected;
	selected.prev = &root;
	selected.next = &child;
	child.prev = &selected;
	child.next = &sibling;
	sibling.prev = &child;
	object_list = &corpse;
	rooms[0].number = 900;
	rooms[0].contents = &corpse;
}
}

P_index obj_index = indexes;
P_obj object_list = nullptr;
P_room world = rooms;
extern const int top_of_world = 0;
int top_of_objt = 7;

bool isname(const char *needle, const char *haystack)
{
	return needle && haystack && strstr(haystack, needle);
}

bool item_owner_identity_equal(const item_owner_identity &left, const item_owner_identity &right)
{
	return left.type == right.type && left.id == right.id &&
	       left.context_id == right.context_id;
}

uint64_t item_corpse_owner_id(uint32_t player_pid, uint32_t save_id)
{
	return (static_cast<uint64_t>(player_pid) << 32) | save_id;
}

uint64_t item_collector_owner_id(uint64_t listing_id)
{
	return listing_id;
}

bool item_ownership_runtime_owner_revision(const item_owner_identity &owner, uint64_t *revision)
{
	if (!revision || owner.type != item_owner_type::collector)
		return false;
	*revision = 0;
	return true;
}

player_snapshot_capture_result
player_item_snapshot_tree_capture(P_obj object, std::vector<player_item_snapshot> *items, size_t *)
{
	if (!object || !items)
		return player_snapshot_capture_result::invalid_identity;
	player_item_snapshot item = {};
	item.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	item.object_uid = object->obj_uid;
	item.vnum = OBJ_VNUM(object);
	item.type = object->type;
	item.wear_flags = object->wear_flags;
	item.extra_flags = object->extra_flags;
	item.extra2_flags = object->extra2_flags;
	item.weight = object->weight;
	item.cost = object->cost;
	item.condition = object->condition;
	items->assign(1, item);
	return player_snapshot_capture_result::ok;
}

player_snapshot_codec_result
player_item_snapshot_list_encode(const std::vector<player_item_snapshot> &items,
				 std::vector<uint8_t> *encoded)
{
	if (!encoded || items.size() != 1 || items[0].weight < 0)
		return player_snapshot_codec_result::invalid_value;
	encoded->resize(32);
	memcpy(encoded->data(), &items[0].object_uid, sizeof(items[0].object_uid));
	memcpy(encoded->data() + 8, &items[0].vnum, sizeof(items[0].vnum));
	memcpy(encoded->data() + 12, &items[0].weight, sizeof(items[0].weight));
	memcpy(encoded->data() + 16, &items[0].cost, sizeof(items[0].cost));
	memcpy(encoded->data() + 20, &items[0].condition, sizeof(items[0].condition));
	memcpy(encoded->data() + 24, &items[0].extra_flags, sizeof(items[0].extra_flags));
	memcpy(encoded->data() + 28, &items[0].extra2_flags, sizeof(items[0].extra2_flags));
	return player_snapshot_codec_result::ok;
}

void obj_from_obj(P_obj object)
{
	assert(object && OBJ_INSIDE(object) && object->loc.inside);
	P_obj parent = object->loc.inside;
	P_obj *cursor = &parent->contains;
	while (*cursor && *cursor != object)
		cursor = &(*cursor)->next_content;
	assert(*cursor == object);
	*cursor = object->next_content;
	object->next_content = nullptr;
	object->loc_p = LOC_NOWHERE;
	object->loc.inside = nullptr;
}

void obj_to_obj(P_obj object, P_obj parent)
{
	assert(object && parent && OBJ_NOWHERE(object));
	object->loc_p = LOC_INSIDE;
	object->loc.inside = parent;
	object->next_content = parent->contains;
	parent->contains = object;
}

void obj_to_room(P_obj object, int room)
{
	assert(object && OBJ_NOWHERE(object) && room == 0);
	object->loc_p = LOC_ROOM;
	object->loc.room = room;
	object->next_content = world[room].contents;
	world[room].contents = object;
}

void obj_from_room(P_obj object)
{
	assert(object && OBJ_ROOM(object));
	P_obj *cursor = &world[object->loc.room].contents;
	while (*cursor && *cursor != object)
		cursor = &(*cursor)->next_content;
	assert(*cursor == object);
	*cursor = object->next_content;
	object->next_content = nullptr;
	object->loc_p = LOC_NOWHERE;
}

void extract_obj(P_obj object, int)
{
	assert(object && !object->contains);
	if (OBJ_INSIDE(object))
		obj_from_obj(object);
	else if (OBJ_ROOM(object))
	{
		P_obj *cursor = &world[object->loc.room].contents;
		while (*cursor && *cursor != object)
			cursor = &(*cursor)->next_content;
		assert(*cursor == object);
		*cursor = object->next_content;
		object->next_content = nullptr;
		object->loc_p = LOC_NOWHERE;
	}
	P_obj *cursor = &object_list;
	while (*cursor && *cursor != object)
		cursor = &(*cursor)->next;
	assert(*cursor == object);
	*cursor = object->next;
	object->next = nullptr;
	extracted = true;
}

int main()
{
	seed_corpse_tree();
	const collector::record entry = candidate_record();
	std::unique_ptr<collector_command_payload> payload;
	assert(collector_collection_prepare(entry, entry.collect_at, &payload) ==
	       collector_collection_prepare_outcome::prepared);
	// The corpse's root and its whole tree go, each with the enrolled revision floor.
	const item_owner_identity corpse_owner = { item_owner_type::corpse,
						   item_corpse_owner_id(42, 12), 0 };
	assert(payload && payload->action == collector_action::collect &&
	       payload->listing == entry.listing &&
	       payload->selected_item_uid == selected.obj_uid &&
	       item_owner_identity_equal(payload->from_owner, corpse_owner) &&
	       payload->expected_to_owner_revision == 0 && payload->item_count == 4 &&
	       payload->items[0].item_uid == 100 && payload->items[1].item_uid == 101 &&
	       payload->items[2].item_uid == 102 && payload->items[3].item_uid == 103 &&
	       payload->items[2].parent_item_uid == 101 &&
	       payload->items[3].expected_item_revision == 1 && payload->item_blob_size == 32);
	int32_t encoded_weight = 0;
	memcpy(&encoded_weight, payload->item_blob.data() + 12, sizeof(encoded_weight));
	assert(encoded_weight == 5);
	P_obj live = nullptr;
	assert(collector_collection_live_matches(*payload, &live) && live == &selected);
	selected.cost++;
	assert(!collector_collection_live_matches(*payload, &live));
	selected.cost--;
	payload->items[2].parent_item_uid = 100;
	assert(!collector_collection_live_matches(*payload, &live));
	payload->items[2].parent_item_uid = 101;
	assert(collector_collection_live_matches(*payload, &live));
	// Detaching leaves the item out of the world; the transaction extracts it once the
	// collection commits.
	assert(collector_collection_detach_live(live));
	assert(!extracted && root.contains == &child && child.loc.inside == &root &&
	       child.next_content == &sibling && sibling.loc.inside == &root &&
	       !selected.contains && OBJ_NOWHERE(&selected));

	// Out of the corpse, the antiquity was claimed.
	seed_corpse_tree();
	auto claimed = candidate_record();
	corpse.contains = nullptr;
	rooms[0].contents = &root;
	root.loc_p = LOC_ROOM;
	root.loc.room = 0;
	root.next_content = &corpse;
	assert(collector_collection_prepare(claimed, claimed.collect_at, &payload) ==
	       collector_collection_prepare_outcome::claimed);
	// In another death's corpse (another player who looted it, or the beneficiary's
	// own later corpse) it left the listed one: claimed, and nothing of that corpse goes.
	seed_corpse_tree();
	corpse.value[CORPSE_PID] = 77;
	assert(collector_collection_prepare(claimed, claimed.collect_at, &payload) ==
	       collector_collection_prepare_outcome::claimed);
	seed_corpse_tree();
	corpse.value[CORPSE_SAVEID] = 99;
	assert(collector_collection_prepare(claimed, claimed.collect_at, &payload) ==
	       collector_collection_prepare_outcome::claimed);
	seed_corpse_tree();
	selected.extra_flags = ITEM_NOSELL;
	assert(collector_collection_prepare(claimed, claimed.collect_at, &payload) ==
	       collector_collection_prepare_outcome::excluded);
	selected.extra_flags = 0;
	root.next = nullptr;
	assert(collector_collection_prepare(claimed, claimed.collect_at, &payload) ==
	       collector_collection_prepare_outcome::missing_item);
}
