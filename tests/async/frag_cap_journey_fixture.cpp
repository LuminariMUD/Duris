// Offline fixtures/inspection for the isolated loaded-world cap journey only.
#include "combat/frag_cap_repository.h"

#include <cassert>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>

int main(int argc, char **argv)
{
	assert(argc >= 5);
	const std::string action = argv[3], name = argv[4];
	MYSQL *db = mysql_init(nullptr);
	assert(db &&
	       mysql_real_connect(db, getenv("DB_HOST"), getenv("DB_USER"), getenv("DB_PASSWD"),
				  getenv("DB_NAME"), static_cast<unsigned>(atoi(getenv("DB_PORT"))),
				  nullptr, 0));
	assert(!mysql_query(db, "SET time_zone='+00:00'"));
	auto query = [&](const std::string &text) { assert(db && !mysql_query(db, text.c_str())); };
	if (action == "actor")
	{
		const int hit = name == "Capvictim" ? 1 : 10000;
		query("UPDATE player_data SET level=31,highest_level=31,base_hit=" +
		      std::to_string(hit) + ",hit_diff=0,exp=10000000 WHERE name='" + name + "'");
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
		query("START TRANSACTION");
		frag_cap_state previous;
		assert(frag_cap_sql_load(db, &previous, true) == frag_cap_store_result::ok);
		state.revision = previous.revision + 1;
		assert(frag_cap_sql_save(db, state) == frag_cap_store_result::ok);
		query("COMMIT");
	}
	else
	{
		assert(action == "inspect");
		assert(frag_cap_sql_load(db, &state) == frag_cap_store_result::ok);
	}
	std::cout << "LEVEL " << state.level << " REV " << state.revision << " DEADLINE "
		  << state.deadline << " GOOD " << frag_cap_for_side(state, frag_cap_side::good)
		  << " EVIL " << frag_cap_for_side(state, frag_cap_side::evil) << " SCORES "
		  << state.earned[0] << ':' << state.earned[1] << '\n';
	if (db)
		mysql_close(db);
}
