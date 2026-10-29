#include "economy/divine_boon_repository.h"
#include <cassert>
#include <cstdlib>
#include <ctime>
#include <string>

int main(int argc, char **argv)
{
	assert(argc == 5);
	const bool flat = std::string(argv[1]) == "flatfile";
	MYSQL *db = nullptr;
	if (!flat)
	{
		db = mysql_init(nullptr);
		assert(db && mysql_real_connect(db, getenv("DB_HOST"), getenv("DB_USER"),
						getenv("DB_PASSWD"), getenv("DB_NAME"),
						std::strtoul(getenv("DB_PORT"), nullptr, 10),
						nullptr, 0));
	}
	divine_boon_state state;
	assert((flat ? divine_boon_flatfile_load(argv[2], &state) :
		       divine_boon_sql_load(db, &state)) == divine_boon_store_result::ok);
	auto save = [&](uint64_t expected)
	{
		assert((flat ? divine_boon_flatfile_save(argv[2], expected, state) :
			       divine_boon_sql_save(db, expected, state)) ==
		       divine_boon_store_result::ok);
	};
	const int64_t now = time(nullptr);
	for (auto mode : { divine_boon_mode::draining, divine_boon_mode::divine })
	{
		const auto expected = state.revision;
		if (state.mode < mode)
		{
			assert(divine_boon_set_mode(&state, mode, now));
			save(expected);
		}
	}
	const auto expected = state.revision++;
	state.paused = true;
	state.last_opportunity = now - now % DIVINE_BOON_HOUR;
	// Natural selection is proved before this fixture. Replace its Epic with
	// the known payment target, retaining the real cargo objective.
	for (auto &slot : state.slots)
		if (slot.category == divine_boon_category::epic)
			slot = {};
	size_t index = 0;
	while (index < state.slots.size() && state.slots[index].id)
		++index;
	assert(index < state.slots.size());
	auto &slot = state.slots[index];
	slot.id = state.next_id++;
	slot.category = divine_boon_category::epic;
	slot.starts_at = state.last_opportunity - (index ? DIVINE_BOON_HOUR : 0);
	slot.expires_at = slot.starts_at + 8 * DIVINE_BOON_HOUR;
	slot.zones = { -1, -1 };
	slot.zones[std::atoi(argv[4])] = std::atoi(argv[3]);
	assert(divine_boon_state_valid(state));
	save(expected);
	if (db)
		mysql_close(db);
}
