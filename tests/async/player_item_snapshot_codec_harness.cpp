#include "flatfile/flatfile_player_snapshot_file.h"
#include "flatfile/flatfile_store.h"
#include <openssl/sha.h>
#include "net/output_preference_state.h"
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

static size_t first_difference(const std::vector<uint8_t> &left, const std::vector<uint8_t> &right)
{
	size_t index = 0;
	while (index < left.size() && index < right.size() && left[index] == right[index])
		++index;
	return index;
}

// A snapshot with a row of every kind the old wire versions differ in: a pet (its uid is new
// in version 7, its restore state in 3) and the output preferences (new in 5).
static player_snapshot snapshot_fixture()
{
	player_snapshot snapshot = {};
	snapshot.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
	snapshot.pid = 41;
	snapshot.revision = 7;
	snapshot.components = PLAYER_CHECKPOINT_COMPONENT_ALL;
	snapshot.encoded_size_bound = PLAYER_SNAPSHOT_MAX_BYTES;
	snapshot.status_integers.push_back({ player_status_field::last_ip, -1, 2, true });
	snapshot.status_strings.push_back({ player_status_string_field::poof_out, "poof" });
	player_pet_snapshot pet = {};
	pet.pet_uid = 0x0101010101010101;
	pet.mob_vnum = 5;
	pet.restore_state = "a";
	snapshot.pets.push_back(pet);
	snapshot.recipes_are_external = true;
	snapshot.output_preferences = "preferences";
	return snapshot;
}

static void put32(std::vector<uint8_t> &bytes, size_t at, uint32_t value)
{
	for (size_t index = 0; index < 4; ++index)
		bytes[at + index] = static_cast<uint8_t>(value >> (8 * index));
}

int main(int argc, char **argv)
{
	require(argc == 2, "temporary file directory required");
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
	// A logout snapshot observes ordinary money changes while a trade waits.
	// The receipt selects committed or refused; settlement is absolute and once.
	player_snapshot pending{};
	pending.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
	pending.pid = 41;
	pending.revision = 100;
	pending.components = PLAYER_COMPONENT_STATUS | PLAYER_COMPONENT_AFFECTS;
	pending.encoded_size_bound = 4096;
	pending.wallet_revision = 6;
	for (unsigned i = 0; i < 4; ++i)
		pending.status_integers.push_back(
			{ static_cast<player_status_field>(
				  static_cast<unsigned>(player_status_field::copper) + i),
			  0,
			  i == 0 ? 50u :
			  i == 3 ? 10u :
				   0u,
			  true });
	pending.pending_trade.operation[0] = 1;
	pending.pending_trade.command_hash[0] = 2;
	pending.pending_trade.payment = -100;
	pending.pending_trade.wallet_revision = 5;
	pending.pending_trade.has_cargo_effect = true;
	pending.pending_trade.cargo_effect.type = PLAYER_TRADE_CARGO_AFFECT;
	pending.pending_trade.cargo_effect.modifier = 10005;
	std::vector<uint8_t> tagged;
	require(player_snapshot_encode(pending, &tagged) == player_snapshot_codec_result::ok &&
			player_snapshot_decode(tagged.data(), tagged.size(), &read_back) ==
				player_snapshot_codec_result::ok &&
			player_snapshot_trade_pending(read_back),
		"pending trade snapshot did not round trip");
	auto crowded = pending;
	crowded.components |= PLAYER_COMPONENT_LANGUAGES;
	crowded.encoded_size_bound = PLAYER_SNAPSHOT_MAX_BYTES;
	crowded.languages.resize(PLAYER_SNAPSHOT_MAX_ROWS - crowded.status_integers.size());
	require(player_snapshot_encode(crowded, &tagged) == player_snapshot_codec_result::ok &&
			player_snapshot_settle_trade(&crowded, true) ==
				player_snapshot_codec_result::ok &&
			crowded.affects.size() == 1 && crowded.wallet_revision == 7 &&
			player_snapshot_encode(crowded, &tagged) ==
				player_snapshot_codec_result::ok,
		"committed cargo projection lost a full ordinary capture");
	crowded.languages.push_back({});
	require(player_snapshot_encode(crowded, &tagged) ==
			player_snapshot_codec_result::limit_exceeded,
		"protected cargo row allowed a second excess ordinary row");
	auto tight = pending;
	tight.components |= PLAYER_COMPONENT_INVENTORY;
	tight.items = heavy;
	tight.items[0].name.resize(tight.items[0].name.size() - 2048);
	tight.pending_trade = {};
	tight.affects.push_back(pending.pending_trade.cargo_effect);
	require(player_snapshot_encode(tight, &tagged) == player_snapshot_codec_result::ok,
		"tight settled image");
	const auto extra = PLAYER_SNAPSHOT_MAX_BYTES - tagged.size() - 128;
	// Spread the padding_left bytes without crossing any individual string bound.
	size_t padding_left = extra;
	for (auto &item : tight.items)
		for (std::string *value : { &item.name, &item.short_description, &item.description,
					    &item.action_description })
		{
			const auto added = std::min(padding_left, PLAYER_SNAPSHOT_MAX_STRING_BYTES -
									  value->size());
			value->append(added, 'x');
			padding_left -= added;
		}
	require(!padding_left, "tight image padding");
	tight.affects.clear();
	tight.pending_trade = pending.pending_trade;
	require(player_snapshot_encode(tight, &tagged) == player_snapshot_codec_result::ok &&
			player_snapshot_settle_trade(&tight, true) ==
				player_snapshot_codec_result::ok &&
			!player_snapshot_trade_pending(tight) &&
			player_snapshot_encode(tight, &tagged) == player_snapshot_codec_result::ok,
		"settlement validated a transient duplicate tag instead of its final image");
	auto refused = read_back;
	require(player_snapshot_settle_trade(&refused, false) == player_snapshot_codec_result::ok &&
			refused.wallet_revision == 6 &&
			refused.status_integers[0].unsigned_value == 50 &&
			!player_snapshot_trade_pending(refused),
		"refused trade altered captured money");
	require(player_snapshot_settle_trade(&read_back, true) ==
				player_snapshot_codec_result::ok &&
			read_back.wallet_revision == 7 &&
			read_back.status_integers[0].unsigned_value == 0 &&
			read_back.status_integers[1].unsigned_value == 5 &&
			read_back.status_integers[2].unsigned_value == 9 &&
			read_back.status_integers[3].unsigned_value == 9 &&
			read_back.affects.size() == 1 && read_back.affects[0].modifier == 10005,
		"committed trade lost intervening money or progress");
	require(player_snapshot_settle_trade(&read_back, true) ==
				player_snapshot_codec_result::ok &&
			read_back.wallet_revision == 7,
		"snapshot settlement applied a payment twice");
	pending.pending_trade.payment = 0;
	require(player_snapshot_settle_trade(&pending, true) == player_snapshot_codec_result::ok &&
			pending.wallet_revision == 7 &&
			pending.status_integers[0].unsigned_value == 50,
		"zero sale did not advance its snapshot watermark");
	// Every proper prefix of a whole snapshot is truncated too.
	auto full = snapshot_fixture();
	full.wallet_revision = 42;
	std::vector<uint8_t> current, other;
	require(player_snapshot_encode(full, &current) == player_snapshot_codec_result::ok,
		"the snapshot fixture did not encode");
	require(player_snapshot_decode(current.data(), current.size(), &read_back) ==
				player_snapshot_codec_result::ok &&
			read_back.wallet_revision == 42,
		"current snapshot lost its captured wallet revision");
	for (size_t length = 1; length < current.size(); ++length)
		require(player_snapshot_decode(current.data(), length, &read_back) ==
				player_snapshot_codec_result::truncated,
			"a " + std::to_string(length) + "-byte snapshot prefix was not truncated");
	// The old wire versions still decode: 5 without the pet uid, 3 without the output
	// preferences as well, 1 without the pet's restore state and hold reason as well.
	auto changed = full;
	changed.pets[0].pet_uid = 0x0202020202020202;
	require(player_snapshot_encode(changed, &other) == player_snapshot_codec_result::ok,
		"the snapshot with another pet uid did not encode");
	const size_t uid_at = first_difference(current, other);
	changed = full;
	changed.pets[0].restore_state = "b";
	require(player_snapshot_encode(changed, &other) == player_snapshot_codec_result::ok,
		"the snapshot with another restore state did not encode");
	const size_t state_at = first_difference(current, other) - 4; // its length comes first
	const auto wire = [&](uint32_t version)
	{
		auto bytes = current;
		if (version < 12)
			bytes.resize(bytes.size() - 1);
		if (version < 11)
			bytes.resize(bytes.size() - sizeof(uint64_t));
		if (version < 3) // the restore state's length, its one byte, the hold reason
			bytes.erase(bytes.begin() + state_at, bytes.begin() + state_at + 9);
		if (version < 5)
			bytes.resize(bytes.size() - 4 - full.output_preferences.size());
		if (version < 7)
			bytes.erase(bytes.begin() + uid_at, bytes.begin() + uid_at + 8);
		put32(bytes, 0, version);
		return bytes;
	};
	for (uint32_t version : { 1u, 3u, 5u, 7u })
	{
		const auto bytes = wire(version);
		require(player_snapshot_decode(bytes.data(), bytes.size(), &read_back) ==
					player_snapshot_codec_result::ok &&
				read_back.wallet_revision == 0 && read_back.pets.size() == 1 &&
				read_back.pets[0].pet_uid ==
					(version >= 7 ? full.pets[0].pet_uid : 0) &&
				std::any_of(read_back.status_integers.begin(),
					    read_back.status_integers.end(),
					    [](const auto &row)
					    {
						    return row.field ==
								   player_status_field::
									   learned_flight_stops &&
							   row.is_unsigned &&
							   row.unsigned_value == 0;
					    }) &&
				std::any_of(
					read_back.status_integers.begin(),
					read_back.status_integers.end(),
					[](const auto &row)
					{
						return row.field ==
							       player_status_field::
								       divine_boon_delivery_seq &&
						       row.is_unsigned && row.unsigned_value == 0;
					}) &&
				read_back.pets[0].mob_vnum == 5 &&
				read_back.pets[0].restore_state == (version >= 3 ? "a" : "") &&
				read_back.output_preferences ==
					(version >= 5 ? full.output_preferences : "") &&
				read_back.recipes_are_external,
			"a version-" + std::to_string(version) + " snapshot did not decode");
		require(read_back.status_strings.back().field ==
					player_status_string_field::last_read_news_hash &&
				read_back.status_strings.back().value.empty(),
			"old snapshot did not default to unread news");

		// Read the old payload through the real checksummed player-file envelope too.
		using namespace flatfile_player_snapshot_file;
		std::vector<uint8_t> file(player_magic.begin(), player_magic.end());
		const auto append = [&file]<typename T>(T number)
		{
			for (size_t i = 0; i < sizeof(T); ++i)
				file.push_back(static_cast<uint8_t>(number >> (8 * i)));
		};
		append(player_file_version);
		append(static_cast<uint32_t>(bytes.size()));
		append(full.pid);
		append(full.revision);
		append(full.components);
		unsigned char digest[SHA256_DIGEST_LENGTH];
		SHA256(bytes.data(), bytes.size(), digest);
		file.insert(file.end(), digest, digest + sizeof(digest));
		file.insert(file.end(), bytes.begin(), bytes.end());
		std::string error;
		const std::string filename = "legacy-" + std::to_string(version) + ".snapshot";
		require(flatfile_atomic_write(argv[1], filename, file, &error), error);
		require(flatfile_player_snapshot_read_file(argv[1], filename, full.pid, &read_back,
							   &error) ==
					flatfile_player_load_result::ok &&
				read_back.schema_version == PLAYER_SNAPSHOT_SCHEMA_VERSION &&
				std::any_of(read_back.status_integers.begin(),
					    read_back.status_integers.end(),
					    [](const auto &row)
					    {
						    return row.field ==
								   player_status_field::
									   learned_flight_stops &&
							   row.is_unsigned &&
							   row.unsigned_value == 0;
					    }) &&
				std::any_of(
					read_back.status_integers.begin(),
					read_back.status_integers.end(),
					[](const auto &row)
					{
						return row.field ==
							       player_status_field::
								       divine_boon_delivery_seq &&
						       row.is_unsigned && row.unsigned_value == 0;
					}),
			"old player file did not load with empty flight discoveries: " + error);
	}
	for (uint32_t version : { 9u, 10u, 11u, 12u })
	{
		const auto bytes = wire(version);
		require(player_snapshot_decode(bytes.data(), bytes.size(), &read_back) ==
					player_snapshot_codec_result::ok &&
				read_back.wallet_revision == (version >= 11 ? 42u : 0u) &&
				read_back.schema_version == PLAYER_SNAPSHOT_SCHEMA_VERSION,
			"old snapshot did not default its absent wallet revision");
	}
	for (uint32_t version : { 1u, 3u, 5u, 7u, 8u, 9u, 10u, 11u, 12u })
	{
		const auto bytes = wire(version);
		require(player_snapshot_decode(bytes.data(), bytes.size(), &read_back) ==
				player_snapshot_codec_result::ok,
			"legacy quest fixture did not decode");
		for (auto field : { player_status_field::quest_origin_room,
				    player_status_field::quest_replacement_due })
			require(std::count_if(read_back.status_integers.begin(),
					      read_back.status_integers.end(),
					      [field](const auto &row) {
						      return row.field == field &&
							     !row.is_unsigned &&
							     row.signed_value == 0;
					      }) == 1,
				"legacy quest recovery state did not default exactly once");
	}
	changed = full;
	changed.quest_values = { 0, 23501, 1, 0, 123, 234, 16553, 11, 0, 2, 4, 7, 12345, 1 };
	changed.status_integers.push_back(
		{ player_status_field::quest_origin_room, 16633, 0, false });
	changed.status_integers.push_back(
		{ player_status_field::quest_replacement_due, 1, 0, false });
	require(player_snapshot_encode(changed, &other) == player_snapshot_codec_result::ok &&
			player_snapshot_decode(other.data(), other.size(), &read_back) ==
				player_snapshot_codec_result::ok &&
			read_back.wallet_revision == full.wallet_revision &&
			read_back.quest_values == changed.quest_values &&
			read_back.status_integers[1].signed_value == 16633 &&
			read_back.status_integers[2].signed_value == 1,
		"quest recovery state, progress or wallet revision lost in round trip");
	put32(other, 0, 12);
	require(player_snapshot_decode(other.data(), other.size(), &read_back) ==
			player_snapshot_codec_result::invalid_value,
		"version 12 accepted status fields introduced in version 13");
	const auto version8 = wire(8);
	require(player_snapshot_decode(version8.data(), version8.size(), &read_back) ==
				player_snapshot_codec_result::ok &&
			read_back.status_strings.back().field ==
				player_status_string_field::last_read_news_hash &&
			read_back.status_strings.back().value.empty(),
		"version 8 news default failed");
	const auto version9 = wire(9);
	uint64_t sequence = UINT64_MAX;
	require(player_snapshot_decode(version9.data(), version9.size(), &read_back) ==
				player_snapshot_codec_result::ok &&
			player_snapshot_divine_delivery_sequence(read_back, &sequence) &&
			sequence == 0,
		"version 9 delivery marker default failed");
	changed = full;
	changed.status_strings.push_back(
		{ player_status_string_field::last_read_news_hash, std::string(64, 'a') });
	require(player_snapshot_encode(changed, &other) == player_snapshot_codec_result::ok &&
			player_snapshot_decode(other.data(), other.size(), &read_back) ==
				player_snapshot_codec_result::ok &&
			read_back.status_strings.back().value == std::string(64, 'a'),
		"news acknowledgement round trip failed");
	put32(other, 0, 8);
	require(player_snapshot_decode(other.data(), other.size(), &read_back) ==
			player_snapshot_codec_result::invalid_value,
		"old wire version accepted a new status string ID");
	put32(other, 0, PLAYER_SNAPSHOT_SCHEMA_VERSION);
	const std::string hash_bytes(64, 'a');
	const auto hash_at =
		std::search(other.begin(), other.end(), hash_bytes.begin(), hash_bytes.end());
	require(hash_at != other.end(), "encoded news fingerprint missing");
	*(hash_at - 5) = static_cast<uint8_t>(player_status_string_field::poof_out);
	require(player_snapshot_decode(other.data(), other.size(), &read_back) ==
			player_snapshot_codec_result::invalid_value,
		"duplicate status ID in wire data was accepted");
	changed.status_strings.push_back(changed.status_strings.back());
	require(player_snapshot_encode(changed, &other) ==
			player_snapshot_codec_result::invalid_value,
		"duplicate news acknowledgement was accepted");
	changed = full;
	changed.status_integers.push_back(
		{ player_status_field::learned_flight_stops, 0, UINT64_MAX, true });
	require(player_snapshot_encode(changed, &other) == player_snapshot_codec_result::ok &&
			player_snapshot_decode(other.data(), other.size(), &read_back) ==
				player_snapshot_codec_result::ok &&
			read_back.status_integers.back().unsigned_value == UINT64_MAX &&
			read_back.status_integers.back().is_unsigned,
		"flight discoveries lost unsigned bits in the snapshot round trip");
	// Old partial saves must not supply status and clear discoveries during merging.
	changed = full;
	changed.components = PLAYER_COMPONENT_LANGUAGES;
	changed.status_integers.clear();
	require(player_snapshot_encode(changed, &other) == player_snapshot_codec_result::ok,
		"partial legacy fixture did not encode");
	other.resize(other.size() - sizeof(uint64_t) - 1);
	put32(other, 0, 7);
	require(player_snapshot_decode(other.data(), other.size(), &read_back) ==
				player_snapshot_codec_result::ok &&
			read_back.status_integers.empty(),
		"old non-status save invented discovery state");
	require(std::none_of(read_back.status_strings.begin(), read_back.status_strings.end(),
			     [](const auto &entry) {
				     return entry.field ==
					    player_status_string_field::last_read_news_hash;
			     }),
		"old non-status save invented acknowledgement state");
	// Version 3 ends in a boolean: every proper prefix of it is truncated as well.
	const auto three = wire(3);
	for (size_t length = 1; length < three.size(); ++length)
		require(player_snapshot_decode(three.data(), length, &read_back) ==
				player_snapshot_codec_result::truncated,
			"a " + std::to_string(length) + "-byte version-3 prefix was not truncated");
	for (uint32_t version : { 2u, 4u, 6u, PLAYER_SNAPSHOT_SCHEMA_VERSION + 1 })
	{
		auto bytes = current;
		put32(bytes, 0, version);
		require(player_snapshot_decode(bytes.data(), bytes.size(), &read_back) ==
				player_snapshot_codec_result::unsupported_version,
			"a snapshot of version " + std::to_string(version) + " was read");
	}
	// A field number past the last is refused, and a restore state over its limit keeps
	// that reason.
	changed = full;
	changed.status_integers[0].field = static_cast<player_status_field>(0);
	require(player_snapshot_encode(changed, &other) == player_snapshot_codec_result::ok,
		"the snapshot with status field 0 did not encode");
	auto bad = current;
	const size_t integer_at = first_difference(current, other);
	const uint16_t past_integer = static_cast<uint16_t>(PLAYER_STATUS_INTEGER_COUNT);
	bad[integer_at] = static_cast<uint8_t>(past_integer);
	bad[integer_at + 1] = static_cast<uint8_t>(past_integer >> 8);
	require(player_snapshot_decode(bad.data(), bad.size(), &read_back) ==
			player_snapshot_codec_result::invalid_value,
		"a status field past the last was read");
	changed = full;
	changed.status_strings[0].field = static_cast<player_status_string_field>(0);
	require(player_snapshot_encode(changed, &other) == player_snapshot_codec_result::ok,
		"the snapshot with status string field 0 did not encode");
	bad = current;
	bad[first_difference(current, other)] =
		static_cast<uint8_t>(player_status_string_field::last_read_news_hash) + 1;
	require(player_snapshot_decode(bad.data(), bad.size(), &read_back) ==
			player_snapshot_codec_result::invalid_value,
		"a status string field past the last was read");
	bad = current;
	put32(bad, state_at, PET_RESTORE_STATE_MAX_BYTES + 1);
	require(player_snapshot_decode(bad.data(), bad.size(), &read_back) ==
			player_snapshot_codec_result::limit_exceeded,
		"an over-long restore state was not refused as over the limit");
	changed = full;
	changed.output_preferences.assign(OUTPUT_PREFERENCE_MAX_BYTES + 1, 'p');
	require(player_snapshot_encode(changed, &other) ==
			player_snapshot_codec_result::limit_exceeded,
		"over-long output preferences were not refused as over the limit");
	// A whole snapshot of exactly PLAYER_SNAPSHOT_MAX_BYTES.
	changed = full;
	changed.items.assign(65, loose);
	require(player_snapshot_encode(changed, &other) == player_snapshot_codec_result::ok,
		"a snapshot of 65 empty items did not encode");
	room = PLAYER_SNAPSHOT_MAX_BYTES - other.size();
	for (auto &item : changed.items)
		for (std::string *text : { &item.name, &item.short_description, &item.description,
					   &item.action_description })
		{
			const size_t length = std::min(room, PLAYER_SNAPSHOT_MAX_STRING_BYTES);
			text->assign(length, 'x');
			room -= length;
		}
	require(room == 0 &&
			player_snapshot_encode(changed, &other) ==
				player_snapshot_codec_result::ok &&
			other.size() == PLAYER_SNAPSHOT_MAX_BYTES &&
			player_snapshot_decode(other.data(), other.size(), &read_back) ==
				player_snapshot_codec_result::ok,
		"a snapshot of exactly the byte limit did not round trip");
	// An item no list holds is not extracted, and a root named twice is refused.
	require(player_item_snapshot_extract_subtree(original, 999, &selected, &remaining) ==
			player_snapshot_codec_result::invalid_value,
		"an absent item was extracted");
	require(player_item_snapshot_extract_forest(forest, { 100, 100 }, &selected, &remaining) ==
			player_snapshot_codec_result::invalid_value,
		"a root named twice was extracted");
	std::cout << "player item snapshot codec passed\n";
	return 0;
}
