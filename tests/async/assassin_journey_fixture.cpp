#include "flatfile/flatfile_player_snapshot_file.h"
#include "flatfile/flatfile_store.h"
#include "player/player_snapshot_codec.h"
#include "magic/spells.h"
#include "core/defines.h"
#include "core/structs.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <openssl/sha.h>

template <class T> void append_number(std::vector<uint8_t> &out, T value)
{
	for (size_t i = 0; i < sizeof(T); ++i)
		out.push_back(static_cast<uint64_t>(value) >> (i * 8));
}

int main(int argc, char **argv)
{
	assert(argc == 2 || argc == 3);
	const std::string root = argv[1];
	const bool inspect = argc == 3 && !strcmp(argv[2], "inspect");
	const bool audit = argc == 3 && !strcmp(argv[2], "audit");
	const int level = argc == 3 && !inspect && !audit ? std::atoi(argv[2]) : 56;
	assert(level >= 30 && level <= 56);
	for (int pid = 1; pid <= 3; ++pid)
	{
		player_snapshot snapshot;
		std::string error;
		assert(flatfile_player_snapshot_read(root, pid, &snapshot, &error) ==
		       flatfile_player_load_result::ok);
		if (inspect)
		{
			for (const auto &affect : snapshot.affects)
				if (affect.type >= FIRST_POISON && affect.type <= LAST_POISON)
					std::printf("affect %d %d %u %d\n", pid, affect.type,
						    affect.level, affect.modifier);
			for (const auto &item : snapshot.items)
				if (item.vnum == 22810)
					std::printf("coating %d %d\n", pid, item.values[4]);
			continue;
		}
		snapshot.room_vnum = 22800;
		if (argc == 3)
			snapshot.affects.clear();
		for (auto &field : snapshot.status_integers)
		{
			int value;
			switch (field.field)
			{
			case player_status_field::level:
			case player_status_field::highest_level:
				value = pid == 1 ? 62 : level;
				break;
			case player_status_field::class_primary:
				value = CLASS_WARRIOR;
				if (pid == 2)
					value = CLASS_ROGUE;
				else if (pid == 3 && audit)
					value = CLASS_CLERIC;
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
			for (int skill : { SKILL_BACKSTAB, SKILL_1H_PIERCING, SKILL_APPLY_POISON,
					   SKILL_MIXPOISON, SKILL_CONTROL_FLEE, SKILL_CRITICAL_STAB,
					   SKILL_RANGE_WEAPONS, SKILL_DARTS })
			{
				if ((skill == SKILL_CONTROL_FLEE && level < 45) ||
				    (skill == SKILL_CRITICAL_STAB && level < 51))
					continue;
				snapshot.skills.push_back({ skill, 100, 100 });
			}
			snapshot.skills.push_back({ SKILL_DUAL_WIELD, 90, 90 });
			snapshot.skills.push_back({ SKILL_AWARENESS, 70, 70 });
		}
		if (pid == 3 && audit)
		{
			for (int spell : { SPELL_REMOVE_POISON, SPELL_SLOW_POISON })
			{
				snapshot.skills.push_back({ spell, 100, 100 });
				for (int i = 0; i < (spell == SPELL_REMOVE_POISON ? 4 : 2); ++i)
				{
					player_affect_snapshot memorized = {};
					memorized.type = TAG_MEMORIZE;
					memorized.duration = -1;
					memorized.flags = AFFTYPE_NOAPPLY | AFFTYPE_NODISPEL |
							  AFFTYPE_NOSHOW | AFFTYPE_PERM |
							  MEMTYPE_FULL;
					memorized.modifier = spell;
					snapshot.affects.push_back(memorized);
				}
			}
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
