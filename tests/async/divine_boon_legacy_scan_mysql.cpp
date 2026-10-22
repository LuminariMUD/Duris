// Exercise the actual restored-job handler without starting unrelated jobs.
#include "persistence/maintenance_repository.c"
#include "sql/sql_thread_init.h"

#include <cassert>
#include <iostream>
#include <future>

int main()
{
	MYSQL *connection = mysql_init(nullptr);
	assert(connection &&
	       mysql_real_connect(connection, getenv("DB_HOST"), getenv("DB_USER"),
				  getenv("DB_PASSWD"), getenv("DB_NAME"),
				  static_cast<unsigned>(atoi(getenv("DB_PORT"))), nullptr, 0));
	assert(mysql_query(connection, "DELETE FROM divine_boon_state") == 0);
	assert(mysql_query(
		       connection,
		       "INSERT INTO boons(time,duration,racewar,type,opt,criteria,bonus,author,active) VALUES(1,0,1,1,2,55,7,'divine-cutover-test',1)") ==
	       0);
	const auto boon_id = mysql_insert_id(connection);
	divine_boon_state state;
	assert(divine_boon_sql_save(connection, 0, state) == divine_boon_store_result::ok);
	maintenance_request live = {};
	live.work_id = 42;
	live.job_id = maintenance_job_id::boon_scan;
	live.row_budget = 64;
	live.deadline_usec = UINT64_MAX;
	live.value_count = 3;
	live.values[0] = 1000;
	const auto scanned = execute_boon_scan(connection, live);
	assert(scanned.outcome == maintenance_outcome::complete && scanned.rows == 1);
	assert(mysql_query(connection,
			   "UPDATE boons SET active=1 WHERE author='divine-cutover-test'") == 0);
	assert(mysql_query(connection, "START TRANSACTION") == 0);
	divine_boon_state locked;
	assert(divine_boon_sql_load(connection, &locked, true) == divine_boon_store_result::ok);
	assert(divine_boon_set_mode(&state, divine_boon_mode::draining, 100));
	std::promise<void> started;
	auto changed = std::async(
		std::launch::async,
		[&]
		{
			assert(sql_worker_thread_init() == 0);
			MYSQL *writer = mysql_init(nullptr);
			assert(writer &&
			       mysql_real_connect(writer, getenv("DB_HOST"), getenv("DB_USER"),
						  getenv("DB_PASSWD"), getenv("DB_NAME"),
						  static_cast<unsigned>(atoi(getenv("DB_PORT"))),
						  nullptr, 0));
			started.set_value();
			const auto saved = divine_boon_sql_save(writer, 1, state);
			mysql_close(writer);
			mysql_thread_end();
			return saved;
		});
	started.get_future().wait();
	assert(changed.wait_for(std::chrono::milliseconds(100)) == std::future_status::timeout);
	assert(mysql_query(connection, "COMMIT") == 0);
	assert(changed.get() == divine_boon_store_result::ok);
	maintenance_request restored = {};
	restored.work_id = 1;
	restored.job_id = maintenance_job_id::boon_scan;
	// A retired/restored request does not need today's payload shape and cannot
	// expire or reactivate history even if its old definition is overdue.
	for (const auto mode : { divine_boon_mode::draining, divine_boon_mode::divine })
	{
		if (state.mode != mode)
		{
			const auto revision = state.revision;
			assert(divine_boon_set_mode(&state, mode, 100));
			assert(divine_boon_sql_save(connection, revision, state) ==
			       divine_boon_store_result::ok);
		}
		const auto result = execute_boon_scan(connection, restored);
		assert(result.outcome == maintenance_outcome::complete && result.rows == 0);
	}
	const std::string query = "SELECT active FROM boons WHERE id=" + std::to_string(boon_id);
	assert(mysql_real_query(connection, query.data(), query.size()) == 0);
	MYSQL_RES *rows = mysql_store_result(connection);
	assert(rows);
	MYSQL_ROW row = mysql_fetch_row(rows);
	assert(row && row[0] && std::string(row[0]) == "1");
	mysql_free_result(rows);
	assert(mysql_query(connection, "UPDATE divine_boon_state SET snapshot=UNHEX('00')") == 0);
	assert(execute_boon_scan(connection, restored).outcome ==
	       maintenance_outcome::permanent_failure);
	assert(mysql_query(connection, "DELETE FROM divine_boon_state") == 0);
	assert(execute_boon_scan(connection, restored).error_code == EAGAIN);
	mysql_close(connection);
	std::cout
		<< "Divine legacy scans: restored jobs retire without mutation; corrupt state fails closed\n";
}
