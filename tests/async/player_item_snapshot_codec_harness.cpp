#include "player/player_snapshot_codec.h"

#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

static void require(bool condition, const std::string &message)
{
	if (!condition)
	{
		std::cerr << message << '\n';
		exit(1);
	}
}

static std::vector<player_item_snapshot> fixture()
{
	player_item_snapshot parent = {};
	parent.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	parent.equipment_slot = -1;
	parent.object_uid = 100;
	parent.generated_key = 200;
	parent.vnum = 300;
	parent.type = 4;
	parent.string_mask = 15;
	parent.name = "container";
	parent.short_description = "a container";
	parent.description = "A container is here.";
	parent.action_description = "open";
	parent.values[0] = 11;
	parent.timers[0] = 12;
	parent.wear_flags = 13;
	parent.extra_flags = 14;
	parent.anti_flags = 15;
	parent.anti2_flags = 16;
	parent.extra2_flags = 17;
	parent.weight = 18;
	parent.material = 19;
	parent.cost = 20;
	parent.condition = 21;
	parent.craftsmanship = 22;
	parent.bitvectors[0] = 23;
	parent.affects[0] = { 24, 25 };
	parent.dynamic_affects.push_back({ 26, 27, 28 });
	parent.extra_descriptions.push_back({ "runes", "glowing runes", true, { 29, 30 } });
	player_item_snapshot child = {};
	child.parent_index = 0;
	child.equipment_slot = -1;
	child.object_uid = 101;
	child.generated_key = 201;
	child.vnum = 301;
	child.name = "child";
	return { parent, child };
}

int main()
{
	const auto original = fixture();
	std::vector<uint8_t> encoded;
	require(player_item_snapshot_list_encode(original, &encoded) ==
				player_snapshot_codec_result::ok &&
			!encoded.empty(),
		"item list did not encode");
	std::vector<player_item_snapshot> decoded;
	require(player_item_snapshot_list_decode(encoded.data(), encoded.size(), &decoded) ==
				player_snapshot_codec_result::ok &&
			decoded.size() == 2 && decoded[0].object_uid == 100 &&
			decoded[0].name == "container" && decoded[0].values[0] == 11 &&
			decoded[0].timers[0] == 12 && decoded[0].bitvectors[0] == 23 &&
			decoded[0].affects[0][1] == 25 && decoded[0].dynamic_affects.size() == 1 &&
			decoded[0].dynamic_affects[0].extra2 == 28 &&
			decoded[0].extra_descriptions.size() == 1 &&
			decoded[0].extra_descriptions[0].spell_ids ==
				std::vector<int32_t>{ 29, 30 } &&
			decoded[1].parent_index == 0 && decoded[1].object_uid == 101,
		"item list did not round trip every nested field");
	require(player_item_snapshot_list_decode(encoded.data(), encoded.size() - 1, &decoded) ==
			player_snapshot_codec_result::truncated,
		"truncated item list was accepted");
	auto trailing = encoded;
	trailing.push_back(0);
	require(player_item_snapshot_list_decode(trailing.data(), trailing.size(), &decoded) ==
			player_snapshot_codec_result::invalid_value,
		"trailing item-list bytes were accepted");
	auto forest = original;
	auto other_root = original[0];
	other_root.object_uid = 200;
	other_root.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	auto other_child = original[1];
	other_child.object_uid = 201;
	other_child.parent_index = 2;
	forest.push_back(other_root);
	forest.push_back(other_child);
	std::vector<player_item_snapshot> selected, remaining;
	require(player_item_snapshot_extract_subtree(forest, 100, &selected, &remaining) ==
				player_snapshot_codec_result::ok &&
			selected.size() == 2 && selected[0].object_uid == 100 &&
			selected[1].parent_index == 0 && remaining.size() == 2 &&
			remaining[0].object_uid == 200 &&
			remaining[0].parent_index == PLAYER_SNAPSHOT_NO_PARENT &&
			remaining[1].parent_index == 0,
		"subtree extraction did not normalize both resulting forests");
	auto third_root = original[0];
	third_root.object_uid = 300;
	third_root.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	forest.push_back(third_root);
	require(player_item_snapshot_extract_forest(forest, { 100, 300 }, &selected, &remaining) ==
				player_snapshot_codec_result::ok &&
			selected.size() == 3 && selected[0].object_uid == 100 &&
			selected[1].parent_index == 0 && selected[2].object_uid == 300 &&
			selected[2].parent_index == PLAYER_SNAPSHOT_NO_PARENT &&
			remaining.size() == 2 && remaining[0].object_uid == 200 &&
			remaining[0].parent_index == PLAYER_SNAPSHOT_NO_PARENT &&
			remaining[1].parent_index == 0,
		"forest extraction did not normalize selected and remaining roots");
	auto invalid_parent = original;
	invalid_parent[1].parent_index = 1;
	require(player_item_snapshot_list_encode(invalid_parent, &encoded) ==
			player_snapshot_codec_result::invalid_value,
		"self-parented item was encoded");
	std::vector<player_item_snapshot> too_deep;
	for (size_t index = 0; index <= PLAYER_SNAPSHOT_MAX_DEPTH; ++index)
	{
		player_item_snapshot item = {};
		item.parent_index = index ? static_cast<int32_t>(index - 1) :
					    PLAYER_SNAPSHOT_NO_PARENT;
		too_deep.push_back(item);
	}
	require(player_item_snapshot_list_encode(too_deep, &encoded) ==
			player_snapshot_codec_result::invalid_value,
		"over-depth item tree was encoded");
	// The world's longest item description, 8411 bytes, is saved like any other.
	auto described = original;
	described[0].extra_descriptions[0].spellbook = false;
	described[0].extra_descriptions[0].spell_ids.clear();
	described[0].extra_descriptions[0].description.assign(8411, 'x');
	require(player_item_snapshot_list_encode(described, &encoded) ==
				player_snapshot_codec_result::ok &&
			player_item_snapshot_list_decode(encoded.data(), encoded.size(),
							 &decoded) ==
				player_snapshot_codec_result::ok &&
			decoded[0].extra_descriptions[0].description.size() == 8411,
		"an 8411-byte item description did not round trip");
	auto oversized = original;
	oversized[0].name.assign(PLAYER_SNAPSHOT_MAX_STRING_BYTES + 1, 'x');
	require(player_item_snapshot_list_encode(oversized, &encoded) ==
			player_snapshot_codec_result::limit_exceeded,
		"oversized item string was encoded");
	std::vector<player_item_snapshot> empty;
	require(player_item_snapshot_list_encode(empty, &encoded) ==
				player_snapshot_codec_result::ok &&
			player_item_snapshot_list_decode(encoded.data(), encoded.size(),
							 &decoded) ==
				player_snapshot_codec_result::ok &&
			decoded.empty(),
		"empty item list did not round trip");
	// Mutation testing (item 15) found the reader and writer limits and error codes untested.
	// Every proper prefix of a valid list is truncated: a reader that failed may not let the
	// decode go on, call it ok, or turn the truncation into another failure.
	require(player_item_snapshot_list_encode(original, &encoded) ==
			player_snapshot_codec_result::ok,
		"item list did not encode again");
	for (size_t length = 1; length < encoded.size(); ++length)
		require(player_item_snapshot_list_decode(encoded.data(), length, &decoded) ==
				player_snapshot_codec_result::truncated,
			"a " + std::to_string(length) + "-byte prefix was not truncated");
	// A refusal keeps its reason through the reads after it: the first item's name length
	// (after the count and 28 bytes of fixed fields) one over the limit, and a boolean of 2.
	auto long_name = encoded;
	const uint32_t over = PLAYER_SNAPSHOT_MAX_STRING_BYTES + 1;
	for (size_t index = 0; index < 4; ++index)
		long_name[32 + index] = static_cast<uint8_t>(over >> (8 * index));
	require(player_item_snapshot_list_decode(long_name.data(), long_name.size(), &decoded) ==
			player_snapshot_codec_result::limit_exceeded,
		"an over-long name length was not refused as over the limit");
	auto plain = original;
	plain[0].extra_descriptions[0].spellbook = false;
	std::vector<uint8_t> plain_encoded;
	require(player_item_snapshot_list_encode(plain, &plain_encoded) ==
				player_snapshot_codec_result::ok &&
			plain_encoded.size() == encoded.size(),
		"the list without a spellbook did not encode");
	size_t flag = 0;
	while (flag < encoded.size() && encoded[flag] == plain_encoded[flag])
		++flag;
	auto two = encoded;
	two[flag] = 2;
	require(player_item_snapshot_list_decode(two.data(), two.size(), &decoded) ==
			player_snapshot_codec_result::invalid_value,
		"a boolean of 2 was not refused as invalid");
	require(player_item_snapshot_list_encode(original, nullptr) ==
			player_snapshot_codec_result::invalid_value,
		"an item list was encoded with nowhere to put it");
	// Every limit holds at its value: a string, an item list, the rows and the depth.
	auto longest = original;
	longest[0].name.assign(PLAYER_SNAPSHOT_MAX_STRING_BYTES, 'x');
	require(player_item_snapshot_list_encode(longest, &encoded) ==
				player_snapshot_codec_result::ok &&
			player_item_snapshot_list_decode(encoded.data(), encoded.size(),
							 &decoded) ==
				player_snapshot_codec_result::ok &&
			decoded[0].name.size() == PLAYER_SNAPSHOT_MAX_STRING_BYTES,
		"a string at the limit did not round trip");
	player_item_snapshot loose = {};
	loose.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
	loose.equipment_slot = -1;
	std::vector<player_item_snapshot> most(PLAYER_SNAPSHOT_MAX_OBJECTS, loose);
	require(player_item_snapshot_list_encode(most, &encoded) ==
				player_snapshot_codec_result::ok &&
			player_item_snapshot_list_decode(encoded.data(), encoded.size(),
							 &decoded) ==
				player_snapshot_codec_result::ok &&
			decoded.size() == PLAYER_SNAPSHOT_MAX_OBJECTS,
		"an item list at the object limit did not round trip");
	// One more item, written by hand: the count, then the last item's bytes again.
	const size_t item_bytes = (encoded.size() - 4) / PLAYER_SNAPSHOT_MAX_OBJECTS;
	auto too_many = encoded;
	too_many.insert(too_many.end(), encoded.end() - item_bytes, encoded.end());
	const uint32_t count = PLAYER_SNAPSHOT_MAX_OBJECTS + 1;
	for (size_t index = 0; index < 4; ++index)
		too_many[index] = static_cast<uint8_t>(count >> (8 * index));
	require(player_item_snapshot_list_decode(too_many.data(), too_many.size(), &decoded) ==
			player_snapshot_codec_result::limit_exceeded,
		"an item list over the object limit was not refused as over the limit");
	std::vector<player_item_snapshot> full_rows(1, loose);
	full_rows[0].dynamic_affects.resize(PLAYER_SNAPSHOT_MAX_ROWS - 1);
	require(player_item_snapshot_list_encode(full_rows, &encoded) ==
				player_snapshot_codec_result::ok &&
			player_item_snapshot_list_decode(encoded.data(), encoded.size(),
							 &decoded) ==
				player_snapshot_codec_result::ok,
		"an item list at the row limit did not round trip");
	std::vector<player_item_snapshot> deepest;
	for (size_t index = 0; index < PLAYER_SNAPSHOT_MAX_DEPTH; ++index)
	{
		player_item_snapshot item = loose;
		item.parent_index = index ? static_cast<int32_t>(index - 1) :
					    PLAYER_SNAPSHOT_NO_PARENT;
		deepest.push_back(item);
	}
	require(player_item_snapshot_list_encode(deepest, &encoded) ==
			player_snapshot_codec_result::ok,
		"an item tree at the depth limit was not encoded");
	// An encoding of exactly PLAYER_SNAPSHOT_MAX_BYTES: 65 items, their names filled to it.
	std::vector<player_item_snapshot> heavy(65, loose);
	require(player_item_snapshot_list_encode(heavy, &encoded) ==
			player_snapshot_codec_result::ok,
		"65 empty items did not encode");
	size_t room = PLAYER_SNAPSHOT_MAX_BYTES - encoded.size();
	for (auto &item : heavy)
		for (std::string *text : { &item.name, &item.short_description, &item.description,
					   &item.action_description })
		{
			const size_t length = std::min(room, PLAYER_SNAPSHOT_MAX_STRING_BYTES);
			text->assign(length, 'x');
			room -= length;
		}
	require(room == 0 &&
			player_item_snapshot_list_encode(heavy, &encoded) ==
				player_snapshot_codec_result::ok &&
			encoded.size() == PLAYER_SNAPSHOT_MAX_BYTES &&
			player_item_snapshot_list_decode(encoded.data(), encoded.size(),
							 &decoded) ==
				player_snapshot_codec_result::ok,
		"an item list of exactly the byte limit did not round trip");
	// A snapshot's single list may hold every row: 8192 status values and nothing else.
	player_snapshot snapshot = {};
	snapshot.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
	snapshot.pid = 41;
	snapshot.revision = 7;
	snapshot.components = PLAYER_COMPONENT_STATUS;
	snapshot.encoded_size_bound = PLAYER_SNAPSHOT_MAX_BYTES;
	snapshot.status_integers.resize(PLAYER_SNAPSHOT_MAX_ROWS);
	player_snapshot read_back = {};
	require(player_snapshot_encode(snapshot, &encoded) == player_snapshot_codec_result::ok &&
			player_snapshot_decode(encoded.data(), encoded.size(), &read_back) ==
				player_snapshot_codec_result::ok &&
			read_back.status_integers.size() == PLAYER_SNAPSHOT_MAX_ROWS,
		"a snapshot list at the row limit did not round trip");
	snapshot.status_integers.clear();
	snapshot.pid = 0;
	require(player_snapshot_encode(snapshot, &encoded) ==
			player_snapshot_codec_result::invalid_value,
		"a snapshot of pid 0 was encoded");
	std::cout << "player item snapshot codec passed\n";
	return 0;
}
