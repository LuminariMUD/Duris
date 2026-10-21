#include "flatfile/flatfile_player_snapshot_file.h"
#include "flatfile/flatfile_store.h"
#include "player/player_snapshot_codec.h"
#include "magic/spells.h"
#include "core/defines.h"
#include "core/structs.h"
#include <cassert>
#include <openssl/sha.h>

template <class T> void append_number(std::vector<uint8_t> &out, T value)
{
	for (size_t i = 0; i < sizeof(T); ++i)
		out.push_back(static_cast<uint64_t>(value) >> (i * 8));
}

int main(int argc, char **argv)
{
	assert(argc == 2);
	const std::string root = argv[1];
	for (int pid = 1; pid <= 3; ++pid)
	{
		player_snapshot snapshot;
		std::string error;
		assert(flatfile_player_snapshot_read(root, pid, &snapshot, &error) ==
		       flatfile_player_load_result::ok);
		snapshot.room_vnum = 22800;
		for (auto &field : snapshot.status_integers)
		{
			int value;
			switch (field.field)
			{
			case player_status_field::level:
			case player_status_field::highest_level:
				value = pid == 1 ? 62 : 56;
				break;
			case player_status_field::class_primary:
				value = pid == 2 ? CLASS_ROGUE : CLASS_WARRIOR;
				break;
			case player_status_field::specialization:
				value = pid == 2 ? SPEC_ASSASSIN : 0;
				break;
			case player_status_field::base_hit:
				value = 10000; // Reachability fixture; damage balance is measured separately.
				break;
			case player_status_field::hit_difference:
				value = 0;
				break;
			case player_status_field::base_strength:
			case player_status_field::base_dexterity:
			case player_status_field::base_agility:
			case player_status_field::base_constitution:
			case player_status_field::base_power:
			case player_status_field::base_intelligence:
			case player_status_field::base_wisdom:
			case player_status_field::base_luck:
				value = 100;
				break;
			default:
				continue;
			}
			field.signed_value = field.unsigned_value = value;
		}
		if (pid == 2)
		{
			snapshot.skills.clear();
			for (int skill :
			     { SKILL_BACKSTAB, SKILL_1H_PIERCING, SKILL_APPLY_POISON,
			       SKILL_MIXPOISON, SKILL_CONTROL_FLEE, SKILL_CRITICAL_STAB })
				snapshot.skills.push_back({ skill, 100, 100 });
			snapshot.skills.push_back({ SKILL_DUAL_WIELD, 90, 90 });
			snapshot.skills.push_back({ SKILL_AWARENESS, 80, 80 });
		}
		std::vector<uint8_t> payload, bytes;
		snapshot.encoded_size_bound = PLAYER_SNAPSHOT_MAX_BYTES;
		assert(player_snapshot_encode(snapshot, &payload) ==
		       player_snapshot_codec_result::ok);
		using namespace flatfile_player_snapshot_file;
		bytes.insert(bytes.end(), player_magic.begin(), player_magic.end());
		append_number(bytes, player_file_version);
		append_number<uint32_t>(bytes, payload.size());
		append_number(bytes, snapshot.pid);
		append_number(bytes, snapshot.revision);
		append_number(bytes, snapshot.components);
		unsigned char digest[SHA256_DIGEST_LENGTH];
		SHA256(payload.data(), payload.size(), digest);
		bytes.insert(bytes.end(), digest, digest + sizeof(digest));
		bytes.insert(bytes.end(), payload.begin(), payload.end());
		assert(flatfile_atomic_write(player_directory(root), player_filename(pid), bytes,
					     &error));
	}
}
