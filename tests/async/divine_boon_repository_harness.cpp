#include "economy/divine_boon_repository.h"

#include <cassert>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>

using result = divine_boon_store_result;

namespace
{
#ifdef __NO_MYSQL__
std::string root;
result load(divine_boon_state *state)
{
	return divine_boon_flatfile_load(root, state);
}
result save(uint64_t expected, const divine_boon_state &state)
{
	return divine_boon_flatfile_save(root, expected, state);
}
#else
MYSQL *connection;
result load(divine_boon_state *state)
{
	return divine_boon_sql_load(connection, state);
}
result save(uint64_t expected, const divine_boon_state &state)
{
	return divine_boon_sql_save(connection, expected, state);
}
#endif
}

int main(int argc, char **argv)
{
#ifdef __NO_MYSQL__
	assert(argc == 2);
	root = argv[1];
	std::filesystem::create_directories(root + "/domains");
	for (const auto &directory : { root, root + "/domains" })
		std::filesystem::permissions(directory, std::filesystem::perms::owner_all,
					     std::filesystem::perm_options::replace);
#else
	(void)argc;
	(void)argv;
	connection = mysql_init(nullptr);
	assert(connection);
	assert(mysql_real_connect(connection, getenv("DB_HOST"), getenv("DB_USER"),
				  getenv("DB_PASSWD"), getenv("DB_NAME"),
				  static_cast<unsigned>(atoi(getenv("DB_PORT"))), nullptr, 0));
#endif
	divine_boon_state state, restored;
#ifndef __NO_MYSQL__
	assert(mysql_query(connection, "INSERT INTO divine_boon_state VALUES(2,1,UNHEX('00'))") !=
	       0);
	assert(mysql_query(connection, "INSERT INTO divine_boon_state VALUES(1,0,UNHEX('00'))") !=
	       0);
#endif
	assert(load(&restored) == result::not_found);
	assert(save(0, state) == result::ok);
	assert(save(0, state) == result::already_applied);
	assert(load(&restored) == result::ok && restored == state);
	assert(divine_boon_set_mode(&state, divine_boon_mode::draining, 100));
	assert(save(1, state) == result::ok);
	assert(divine_boon_set_mode(&state, divine_boon_mode::divine, 100));
	assert(save(2, state) == result::ok);
	divine_boon_slot choice;
	choice.category = divine_boon_category::experience;
	choice.zones = { 10, 20 };
	const uint64_t previous_revision = state.revision;
	assert(divine_boon_rotate(&state, DIVINE_BOON_HOUR, &choice));
	assert(save(previous_revision, state) == result::ok);
	assert(save(previous_revision, state) == result::already_applied);
	assert(load(&restored) == result::ok && restored == state);
	assert(!divine_boon_rotate(&restored, DIVINE_BOON_HOUR + 1, &choice));
	auto rerolled = state;
	rerolled.slots[0].zones = { 30, 40 };
	assert(save(previous_revision, rerolled) == result::conflict);
	assert(save(state.revision, state) == result::invalid);
	assert(load(&restored) == result::ok && restored == state);
	const auto stale = state;
	assert(divine_boon_set_paused(&state, true, DIVINE_BOON_HOUR + 1));
	assert(save(stale.revision, state) == result::ok);
	assert(save(previous_revision, stale) == result::conflict);

#ifdef __NO_MYSQL__
	// Before commit nothing changes; once journaled, reopening recovers the result.
	for (const char *fault : { "DURIS_FLATFILE_TEST_FAIL_BEFORE_AUTHORITY_COMMIT",
				   "DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL",
				   "DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_IMAGE" })
	{
		auto next = state;
		assert(divine_boon_set_paused(&next, !state.paused, DIVINE_BOON_HOUR + 2));
		assert(setenv(fault, "1", 1) == 0);
		assert(save(state.revision, next) == result::io_error);
		assert(unsetenv(fault) == 0);
		assert(load(&restored) == result::ok);
		const bool before_commit = std::string(fault).find("FAIL_BEFORE") !=
					   std::string::npos;
		assert(restored == (before_commit ? state : next));
		assert(save(state.revision, next) ==
		       (before_commit ? result::ok : result::already_applied));
		state = next;
	}
	std::ofstream(root + "/domains/divine-boons.state", std::ios::binary | std::ios::trunc)
		<< "bad";
#else
	assert(mysql_query(connection,
			   "UPDATE divine_boon_state SET snapshot=UNHEX('00') WHERE state_id=1") ==
	       0);
#endif
	const auto before = restored;
	assert(load(&restored) == result::invalid && restored == before);
	auto next = state;
	assert(divine_boon_set_paused(&next, !state.paused, DIVINE_BOON_HOUR + 3));
	assert(save(state.revision, next) == result::invalid); // Never overwrite corrupt evidence.
#ifndef __NO_MYSQL__
	mysql_close(connection);
#endif
	std::cout
		<< "Divine Boon repository: create, CAS, replay, stale/reroll and corruption contracts passed\n";
}
