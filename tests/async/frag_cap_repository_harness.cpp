#include "combat/frag_cap_repository.h"

#include <cassert>
#include <cstdlib>
#include <iostream>

using result = frag_cap_store_result;
constexpr int64_t start = INT64_C(1800000000000000);
constexpr int64_t hour = FRAG_CAP_HOUR;

namespace
{
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
	const frag_cap_award award = { frag_cap_side::good, points };
	assert(frag_cap_apply(&state, admitted_at, now, &award, 1));
	assert(frag_cap_sql_save(connection, state) == result::ok);
	sql(rollback ? "ROLLBACK" : "COMMIT");
	return true;
}
}

int main()
{
	frag_cap_state state, restored;
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
	assert(frag_cap_sql_adopt(connection, 25, 56, start, &state) == result::ok);
	sql("ROLLBACK");
	assert(load(&restored) == result::not_found);
	sql("START TRANSACTION");
	assert(frag_cap_sql_adopt(connection, 25, 56, start, &state) == result::ok);
	sql("COMMIT");
	sql("START TRANSACTION");
	assert(frag_cap_sql_adopt(connection, 56, 56, start + hour, &restored) == result::ok);
	sql("COMMIT");
	assert(restored == state);
	// An unchanged singleton is still a successful save.
	sql("START TRANSACTION");
	assert(frag_cap_sql_save(connection, state) == result::ok);
	sql("COMMIT");
	assert(load(&restored) == result::ok && restored == state);
	assert(parent(100, start, start, 5, true));
	assert(load(&restored) == result::ok && restored == state);
	auto captured = state;
	critical_command command{};
	command.accepted_at_usec = start;
	combat_outcome_payload payload{};
	payload.participant_count = 4;
	for (size_t i = 0; i < 4; ++i)
	{
		payload.participants[i].pid = static_cast<uint32_t>(400 + i);
		payload.participants[i].frag_delta = 5;
	}
	payload.participants[0].racewar = 1;
	payload.participants[1].racewar = 1;
	payload.participants[2].racewar = 2;
	payload.participants[3].racewar = 3;
	assert(frag_cap_apply_combat(&captured, command, payload, start));
	assert(captured.earned[0] == 10 && captured.earned[1] == 5);
	assert(state.level == 31);
	assert(parent(1, start + hour, start + hour, 5));
	assert(load(&restored) == result::ok && restored.earned[0] == 5);
	state = restored;
	assert(parent(1, start + hour, start + 2 * hour, 5));
	assert(load(&restored) == result::ok && restored == state);
	assert(parent(2, start + 2 * hour, start + 2 * hour, 5));
	assert(load(&restored) == result::ok && restored.earned[0] == 10);
	state = restored;
	assert(parent(3, start + 4 * hour, start + 4 * hour, 10));
	assert(load(&restored) == result::ok && restored.earned[0] >= 20 && restored.level == 31);
	state = restored;
	assert(parent(3, start + 4 * hour, start + 60 * hour, 10));
	assert(load(&restored) == result::ok && restored == state);
	sql("START TRANSACTION");
	assert(frag_cap_sql_load(connection, &state, true) == result::ok);
	assert(frag_cap_settle(&state, start + 72 * hour));
	assert(frag_cap_sql_save(connection, state) == result::ok);
	sql("COMMIT");
	assert(load(&restored) == result::ok && restored.level == 32 &&
	       restored.earned == (std::array<uint64_t, 2>{}));
	// The maximum cap has no clock but must retain a valid legacy projection.
	assert(frag_cap_adopt(&state, 56, 0, start + 72 * hour));
	sql("START TRANSACTION");
	assert(frag_cap_sql_save(connection, state) == result::ok);
	sql("COMMIT");
	assert(load(&restored) == result::ok && restored.level == 56 && !restored.deadline);
	const int64_t reset_started = start + 73 * hour;
	sql("START TRANSACTION");
	assert(frag_cap_sql_reset_season(connection, reset_started) == result::ok);
	sql("COMMIT");
	assert(load(&state) == result::ok && state.level == 31 &&
	       state.credit_cutoff == reset_started);
	const auto reset_state = state;
	sql("START TRANSACTION");
	assert(frag_cap_sql_reset_season(connection, reset_started) == result::ok);
	sql("COMMIT");
	assert(load(&restored) == result::ok && restored == reset_state);
	const frag_cap_award old_award = { frag_cap_side::good, 100 };
	assert(frag_cap_apply(&restored, reset_started - 1, reset_started, &old_award, 1));
	assert(restored == reset_state);
	// A distinct old parent event records its receipt while leaving the cap unchanged.
	assert(parent(4, reset_started - 1, reset_started, 100));
	assert(load(&restored) == result::ok && restored == reset_state);
	sql("UPDATE level_cap SET snapshot=NULL,level=56,level_good=55,level_evil=54,next_update=FROM_UNIXTIME(1800003600)");
	sql("START TRANSACTION");
	assert(frag_cap_sql_adopt(connection, 25, 40, start, &state) == result::ok &&
	       state.level == 40);
	sql("COMMIT");
	state.earned[1] = 1;
	assert(frag_cap_settle(&state, state.deadline));
	sql("START TRANSACTION");
	assert(frag_cap_sql_save(connection, state) == result::ok);
	sql("COMMIT");
	sql("SELECT level,level_good,level_evil FROM level_cap");
	MYSQL_RES *projections = mysql_store_result(connection);
	auto projection = mysql_fetch_row(projections);
	assert(projection && std::string(projection[0]) == "41" &&
	       std::string(projection[1]) == "41" && std::string(projection[2]) == "41");
	mysql_free_result(projections);
	state.earned[1] = 1;
	assert(frag_cap_settle(&state, state.deadline));
	sql("START TRANSACTION");
	assert(frag_cap_sql_save(connection, state) == result::ok);
	sql("COMMIT");
	sql("SELECT level,level_good,level_evil FROM level_cap");
	projections = mysql_store_result(connection);
	projection = mysql_fetch_row(projections);
	assert(projection && std::string(projection[0]) == "41" &&
	       std::string(projection[1]) == "41" && std::string(projection[2]) == "42");
	mysql_free_result(projections);
	sql("UPDATE level_cap SET snapshot=UNHEX('00')");
	const auto before = restored;
	assert(frag_cap_sql_adopt(connection, 25, 56, start + 60 * hour, &restored) ==
	       result::invalid);
	assert(restored == before);
	sql("UPDATE level_cap SET snapshot=NULL,level=31,level_good=40,level_evil=36,next_update=FROM_UNIXTIME(1800003600)");
	sql("START TRANSACTION");
	assert(frag_cap_sql_adopt(connection, 25, 56, start, &state) == result::ok);
	assert(state.level == 40 && state.deadline == start + hour);
	sql("COMMIT");
	sql("UPDATE level_cap SET snapshot=NULL,level_good=57");
	assert(frag_cap_sql_adopt(connection, 25, 56, start, &restored) == result::invalid);
	sql("DELETE FROM level_cap");
	assert(load(&restored) == result::invalid);
	assert(frag_cap_sql_save(connection, state) == result::invalid);
	mysql_close(connection);
	std::cout
		<< "PASS shared cap storage: adoption, reopen, parent receipt replay, rollback/recovery, timer, corruption\n";
}
