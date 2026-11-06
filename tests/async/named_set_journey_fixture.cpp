// Synthetic, isolated named-set journeys only. Never point this at live state.
// Generated item content and UIDs are retained; preparation changes the tester.
#include "flatfile/flatfile_player_snapshot_file.h"
#include "flatfile/flatfile_store.h"
#include "player/player_snapshot_codec.h"
#include "core/defines.h"
#include <cassert>
#include <cstdio>
#include <openssl/sha.h>

template <class T> void number(std::vector<uint8_t> &out, T value)
{
	for (size_t i = 0; i < sizeof(T); ++i)
		out.push_back(static_cast<uint64_t>(value) >> (i * 8));
}

int main(int argc, char **argv)
{
	assert(argc == 3 || argc == 4);
	const std::string root = argv[1], mode = argv[2];
	const int pid = argc == 4 ? std::stoi(argv[3]) : 1;
	assert(pid == 1 || pid == 2);
	player_snapshot snapshot;
	std::string error;
	assert(flatfile_player_snapshot_read(root, pid, &snapshot, &error) ==
	       flatfile_player_load_result::ok);
	bool synthetic = false;
	for (const auto &field : snapshot.status_strings)
		if (field.field == player_status_string_field::name &&
		    field.value == (pid == 1 ? "Taverek" : "Meranen"))
			synthetic = true;
	assert(synthetic && root.find("/bin/tests/") != std::string::npos);
	if (mode == "mortal")
	{
		for (auto &field : snapshot.status_integers)
		{
			if (field.field == player_status_field::level ||
			    field.field == player_status_field::highest_level)
				field.signed_value = field.unsigned_value = 56;
			if (field.field == player_status_field::base_hit)
				field.signed_value = field.unsigned_value = 1000;
		}
		// Remove unrelated welcome/rest buffs to isolate equipment application.
		snapshot.affects.clear();
		std::vector<uint8_t> payload, bytes;
		snapshot.encoded_size_bound = PLAYER_SNAPSHOT_MAX_BYTES;
		assert(player_snapshot_encode(snapshot, &payload) ==
		       player_snapshot_codec_result::ok);
		using namespace flatfile_player_snapshot_file;
		bytes.insert(bytes.end(), player_magic.begin(), player_magic.end());
		number(bytes, player_file_version);
		number<uint32_t>(bytes, payload.size());
		number(bytes, snapshot.pid);
		number(bytes, snapshot.revision);
		number(bytes, snapshot.components);
		unsigned char digest[SHA256_DIGEST_LENGTH];
		SHA256(payload.data(), payload.size(), digest);
		bytes.insert(bytes.end(), digest, digest + sizeof(digest));
		bytes.insert(bytes.end(), payload.begin(), payload.end());
		assert(flatfile_atomic_write(player_directory(root), player_filename(pid), bytes,
					     &error));
		return 0;
	}
	if (mode == "affects")
	{
		for (const auto &affect : snapshot.affects)
			std::printf("%d|%d|%u|%d\n", affect.type, affect.duration, affect.flags,
				    affect.modifier);
		return 0;
	}
	if (mode == "inventory")
	{
		for (const auto &item : snapshot.items)
			std::printf("%llu|%d|%d|%d\n",
				    static_cast<unsigned long long>(item.object_uid), item.vnum,
				    item.parent_index, item.equipment_slot);
		return 0;
	}
	assert(mode == "inspect");
	for (const auto &item : snapshot.items)
	{
		int zone = 0;
		for (const auto &description : item.extra_descriptions)
			if (description.keyword == "DURIS_NAMED_SET_ORIGIN_V1")
				zone = std::stoi(description.description);
		if (!zone)
			continue;
		bool clean = item.dynamic_affects.empty();
		for (const auto &affect : item.affects)
			if (affect[0] == APPLY_HIT || affect[0] == APPLY_CON ||
			    affect[0] == APPLY_CON_MAX || affect[0] == APPLY_CON_RACE)
				clean = false;
		// Ordinary vision/protection bits do not enter calculate_hitpoints2().
		// Exclude built-in effects that would prevent observing the set grant.
		clean = clean && !(item.bitvectors[0] & (AFF_ARMOR | AFF_HASTE)) &&
			!(item.bitvectors[3] & (AFF4_MAGE_FLAME | AFF4_GLOBE_OF_DARKNESS));
		std::printf("%llu|%d|%d|%u|%d|%d|%s\n",
			    static_cast<unsigned long long>(item.object_uid), zone,
			    item.equipment_slot, item.wear_flags, clean, item.parent_index,
			    item.short_description.c_str());
	}
}
