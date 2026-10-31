// Offline fixtures/inspection for the isolated loaded-world cap journey only.
#include "combat/frag_cap_repository.h"
#include "flatfile/flatfile_identity_repository.h"
#include "flatfile/flatfile_player_snapshot_file.h"
#include "flatfile/flatfile_store.h"

#include <cassert>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>

int main(int argc, char **argv)
{
	assert(argc >= 5);
	const bool flat = std::string(argv[1]) == "flatfile";
	const std::string root = argv[2], action = argv[3], name = argv[4];
	MYSQL *db = nullptr;
	if (!flat)
	{
		db = mysql_init(nullptr);
		assert(db && mysql_real_connect(db, getenv("DB_HOST"), getenv("DB_USER"),
						getenv("DB_PASSWD"), getenv("DB_NAME"),
						static_cast<unsigned>(atoi(getenv("DB_PORT"))),
						nullptr, 0));
		assert(!mysql_query(db, "SET time_zone='+00:00'"));
	}
	auto query = [&](const std::string &text) { assert(db && !mysql_query(db, text.c_str())); };
	auto pid = [&](const std::string &owner) -> uint32_t
	{
		if (flat)
		{
			flatfile_identity_record identity;
			assert(flatfile_identity_lookup_name(root, owner, &identity, nullptr) ==
			       flatfile_identity_result::ok);
			return identity.pid;
		}
		query("SELECT pid FROM player_data WHERE name='" + owner + "'");
		auto *rows = mysql_store_result(db);
		assert(rows);
		auto row = mysql_fetch_row(rows);
		assert(row && row[0]);
		const uint32_t value = strtoul(row[0], nullptr, 10);
		mysql_free_result(rows);
		return value;
	};
	if (action == "actor")
	{
		const int hit = name == "Capvictim" ? 1 : 10000;
		if (flat)
		{
			player_snapshot player;
			assert(flatfile_player_snapshot_read(root, pid(name), &player, nullptr) ==
			       flatfile_player_load_result::ok);
			for (auto &field : player.status_integers)
			{
				if (field.field == player_status_field::level ||
				    field.field == player_status_field::highest_level)
					field.signed_value = field.unsigned_value = 31;
				if (field.field == player_status_field::base_hit)
					field.signed_value = field.unsigned_value = hit;
				if (field.field == player_status_field::hit_difference)
					field.signed_value = field.unsigned_value = 0;
				if (field.field == player_status_field::experience)
					field.signed_value = field.unsigned_value = 10000000;
			}
			std::vector<uint8_t> bytes;
			assert(flatfile_player_snapshot_encode_file(&player, &bytes));
			using namespace flatfile_player_snapshot_file;
			assert(flatfile_atomic_write(player_directory(root),
						     player_filename(player.pid), bytes, nullptr));
		}
		else
			query("UPDATE player_data SET level=31,highest_level=31,base_hit=" +
			      std::to_string(hit) + ",hit_diff=0,exp=10000000 WHERE name='" + name +
			      "'");
		return 0;
	}
	frag_cap_state state;
	if (action == "seed" || action == "quiet" || action == "circle")
	{
		assert(argc == 6);
		const int64_t earliest = atoll(argv[5]) * 1000000;
		assert(frag_cap_adopt(&state, 30, 0, earliest - 72 * FRAG_CAP_HOUR));
		if (action == "seed")
			state.earned = { 5, 10 };
		else
		{
			state.level = action == "quiet" ? 32 : 35;
			state.advantage = action == "quiet" ? frag_cap_side::good :
							      frag_cap_side::evil;
		}
		if (flat)
		{
			flatfile_authority_lock lock;
			assert(lock.acquire(root, nullptr));
			frag_cap_state previous;
			assert(frag_cap_flatfile_load_locked(root, lock, &previous) ==
			       frag_cap_store_result::ok);
			state.revision = previous.revision + 1;
			std::vector<flatfile_authority_operation> operations;
			assert(frag_cap_flatfile_prepare(root, lock, state, &operations) ==
			       frag_cap_store_result::ok);
			assert(flatfile_authority_transaction_commit_operations(
				       root, lock, operations, nullptr) ==
			       flatfile_authority_transaction_result::ok);
		}
		else
		{
			query("START TRANSACTION");
			frag_cap_state previous;
			assert(frag_cap_sql_load(db, &previous, true) == frag_cap_store_result::ok);
			state.revision = previous.revision + 1;
			assert(frag_cap_sql_save(db, state) == frag_cap_store_result::ok);
			query("COMMIT");
		}
	}
	else
	{
		assert(action == "inspect");
		assert((flat ? frag_cap_flatfile_load(root, &state) :
			       frag_cap_sql_load(db, &state)) == frag_cap_store_result::ok);
	}
	std::cout << "LEVEL " << state.level << " REV " << state.revision << " DEADLINE "
		  << state.deadline << " GOOD " << frag_cap_for_side(state, frag_cap_side::good)
		  << " EVIL " << frag_cap_for_side(state, frag_cap_side::evil) << " SCORES "
		  << state.earned[0] << ':' << state.earned[1] << '\n';
	if (db)
		mysql_close(db);
}
