#include "combat/frag_cap_repository.h"
#include "flatfile/flatfile_store.h"

#include <cassert>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>

using result = frag_cap_store_result;
constexpr int64_t start = INT64_C(1800000000000000);
constexpr int64_t hour = FRAG_CAP_HOUR;

namespace
{
#ifdef __NO_MYSQL__
std::string root;
result load(frag_cap_state *state)
{
	return frag_cap_flatfile_load(root, state);
}

bool parent(int event, int64_t admitted_at, int64_t now, int points)
{
	flatfile_authority_lock lock;
	assert(lock.acquire(root, nullptr));
	assert(flatfile_authority_transaction_recover(root, lock, nullptr) ==
	       flatfile_authority_transaction_result::ok);
	const std::string filename = "cap-test-receipt-" + std::to_string(event);
	std::vector<uint8_t> bytes;
	if (flatfile_read(root + "/domains", filename, 1, &bytes, nullptr) ==
	    flatfile_read_result::ok)
		return true;
	frag_cap_state state;
	assert(frag_cap_flatfile_load_locked(root, lock, &state) == result::ok);
	const frag_cap_award award = { 1, points };
	assert(frag_cap_apply(&state, admitted_at, now, &award, 1));
	std::vector<flatfile_authority_operation> operations;
	assert(frag_cap_flatfile_prepare(root, lock, state, &operations) == result::ok);
	flatfile_authority_operation receipt;
	receipt.filename = filename;
	receipt.bytes = { 1 };
	operations.push_back(receipt);
	return flatfile_authority_transaction_commit_operations(root, lock, operations, nullptr) ==
	       flatfile_authority_transaction_result::ok;
}
#else
MYSQL *connection;
void sql(const char *query)
{
	if (mysql_query(connection, query))
	{
		std::cerr << mysql_error(connection) << '\n';
		std::abort();
	}
}

result load(frag_cap_state *state)
{
	return frag_cap_sql_load(connection, state);
}

bool parent(int event, int64_t admitted_at, int64_t now, int points, bool rollback = false)
{
	sql("START TRANSACTION");
	const std::string insert =
		"INSERT IGNORE INTO cap_test_receipts VALUES(" + std::to_string(event) + ")";
	sql(insert.c_str());
	if (!mysql_affected_rows(connection))
	{
		sql("COMMIT");
		return true;
	}
	frag_cap_state state;
	assert(frag_cap_sql_load(connection, &state, true) == result::ok);
	const frag_cap_award award = { 1, points };
	assert(frag_cap_apply(&state, admitted_at, now, &award, 1));
	assert(frag_cap_sql_save(connection, state) == result::ok);
	sql(rollback ? "ROLLBACK" : "COMMIT");
	return true;
}
#endif
}

int main(int argc, char **argv)
{
	frag_cap_state state, restored;
#ifdef __NO_MYSQL__
	assert(argc == 2);
	root = argv[1];
	std::filesystem::create_directories(root + "/domains");
	for (const auto &directory : { root, root + "/domains" })
		std::filesystem::permissions(directory, std::filesystem::perms::owner_all,
					     std::filesystem::perm_options::replace);
	assert(load(&restored) == result::not_found);
	assert(frag_cap_flatfile_adopt(root, 25, start, &state) == result::ok);
	assert(frag_cap_flatfile_adopt(root, 56, start + hour, &restored) == result::ok);
	assert(restored == state); // Repeated activation never resets the round.
	flatfile_authority_lock unowned;
	std::vector<flatfile_authority_operation> operations;
	assert(frag_cap_flatfile_prepare(root, unowned, state, &operations) == result::invalid);
#else
	(void)argc;
	(void)argv;
	connection = mysql_init(nullptr);
	assert(connection &&
	       mysql_real_connect(connection, getenv("DB_HOST"), getenv("DB_USER"),
				  getenv("DB_PASSWD"), getenv("DB_NAME"),
				  static_cast<unsigned>(atoi(getenv("DB_PORT"))), nullptr, 0));
	sql("SET time_zone='+00:00'");
	sql("CREATE TABLE cap_test_receipts(id INT PRIMARY KEY) ENGINE=InnoDB");
	sql("UPDATE level_cap SET snapshot=NULL,level=30,level_good=0,level_evil=0");
	assert(load(&restored) == result::not_found);
	sql("START TRANSACTION");
	assert(frag_cap_sql_adopt(connection, 25, start, &state) == result::ok);
	sql("ROLLBACK");
	assert(load(&restored) == result::not_found);
	sql("START TRANSACTION");
	assert(frag_cap_sql_adopt(connection, 25, start, &state) == result::ok);
	sql("COMMIT");
	sql("START TRANSACTION");
	assert(frag_cap_sql_adopt(connection, 56, start + hour, &restored) == result::ok);
	sql("COMMIT");
	assert(restored == state);
	// Saving an unchanged after-image is a valid parent operation, not a missing row.
	sql("START TRANSACTION");
	assert(frag_cap_sql_save(connection, state) == result::ok);
	sql("COMMIT");
	assert(load(&restored) == result::ok && restored == state);
	assert(parent(100, start, start, 5, true));
	assert(load(&restored) == result::ok && restored == state);
#endif
	assert(state.level == 31);
	assert(parent(1, start + hour, start + hour, 5));
	assert(load(&restored) == result::ok && restored.earned.at(1) == 5);
	state = restored;
	assert(parent(1, start + hour, start + 2 * hour, 5));
	assert(load(&restored) == result::ok && restored == state);
	assert(parent(2, start + 2 * hour, start + 2 * hour, 5));
	assert(load(&restored) == result::ok && restored.earned.at(1) == 10);
	state = restored;
#ifdef __NO_MYSQL__
	int event = 10;
	for (const char *fault : { "DURIS_FLATFILE_TEST_FAIL_BEFORE_AUTHORITY_COMMIT",
				   "DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL",
				   "DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_IMAGE" })
	{
		assert(setenv(fault, "1", 1) == 0);
		assert(!parent(event, start + 3 * hour, start + 3 * hour, 1));
		assert(unsetenv(fault) == 0);
		assert(load(&restored) == result::ok);
		const bool before_commit = std::string(fault).find("FAIL_BEFORE") !=
					   std::string::npos;
		assert(restored.earned.at(1) == state.earned.at(1) + (before_commit ? 0 : 1));
		assert(parent(event, start + 3 * hour, start + 3 * hour, 1));
		assert(load(&restored) == result::ok &&
		       restored.earned.at(1) == state.earned.at(1) + 1);
		state = restored;
		++event;
	}
#endif
	assert(parent(3, start + 4 * hour, start + 4 * hour, 10));
	assert(load(&restored) == result::ok && restored.qualified_at == start + 4 * hour);
	state = restored;
	assert(parent(3, start + 4 * hour, start + 60 * hour, 10));
	assert(load(&restored) == result::ok && restored == state);
	// A distinct parent event after qualification has no cap mutation but still commits.
	assert(parent(4, start + 5 * hour, start + 5 * hour, 10));
	assert(load(&restored) == result::ok && restored == state);
#ifdef __NO_MYSQL__
	assert(frag_cap_flatfile_tick(root, start + 48 * hour) == result::ok);
	assert(load(&restored) == result::ok && restored.level == 32 && restored.earned.empty());
	assert(frag_cap_flatfile_tick(root, start + 48 * hour) == result::ok);
	std::ofstream(root + "/domains/frag-cap.state", std::ios::binary | std::ios::trunc)
		<< "bad";
	const auto before = restored;
	assert(frag_cap_flatfile_adopt(root, 25, start + 60 * hour, &restored) == result::invalid);
	assert(restored == before);
#else
	sql("START TRANSACTION");
	assert(frag_cap_sql_load(connection, &state, true) == result::ok);
	assert(frag_cap_settle(&state, start + 48 * hour));
	assert(frag_cap_sql_save(connection, state) == result::ok);
	sql("COMMIT");
	assert(load(&restored) == result::ok && restored.level == 32 && restored.earned.empty());
	// The maximum cap has no clock but must retain a valid legacy projection.
	assert(frag_cap_adopt(&state, 56, 0, start + 48 * hour));
	sql("START TRANSACTION");
	assert(frag_cap_sql_save(connection, state) == result::ok);
	sql("COMMIT");
	assert(load(&restored) == result::ok && restored.level == 56 && !restored.automatic_at);
	sql("UPDATE level_cap SET snapshot=UNHEX('00')");
	const auto before = restored;
	assert(frag_cap_sql_adopt(connection, 25, start + 60 * hour, &restored) == result::invalid);
	assert(restored == before);
	sql("UPDATE level_cap SET snapshot=NULL,level=31,level_good=40,level_evil=36,next_update=FROM_UNIXTIME(1800003600)");
	sql("START TRANSACTION");
	assert(frag_cap_sql_adopt(connection, 25, start, &state) == result::ok);
	assert(state.level == 40 && state.automatic_at == start + hour &&
	       state.earliest_at == start);
	sql("COMMIT");
	sql("UPDATE level_cap SET snapshot=NULL,level_good=57");
	assert(frag_cap_sql_adopt(connection, 25, start, &restored) == result::invalid);
	sql("DELETE FROM level_cap");
	assert(load(&restored) == result::invalid);
	assert(frag_cap_sql_save(connection, state) == result::invalid);
	mysql_close(connection);
#endif
	std::cout
		<< "PASS shared cap storage: adoption, reopen, parent receipt replay, rollback/recovery, timer, corruption\n";
}
