// The level cap job on a real database, with the shipped lib/frag_cap.cfg. Runs the job once
// as if at the given time and prints its outcome, rows and, after an unlock, the side, the
// level and whether it opened to every side.
// Arguments: host port user password database now work-id.
#include "combat/frag_cap_config.h"
#include "persistence/maintenance_repository.h"
#include "persistence/persistence_observability.h"
#include "sql/sql_pool.h"

#include <cassert>
#include <cstdio>
#include <cstdlib>

static MYSQL *connection;

extern "C" MYSQL *sql_pool_acquire(void)
{
	return connection;
}

int main(int argc, char **argv)
{
	assert(argc == 8);
	boot_frag_cap_config();
	connection = mysql_init(nullptr);
	assert(mysql_real_connect(connection, argv[1], argv[3], argv[4], argv[5], atoi(argv[2]),
				  nullptr, 0));
	// The runtime's connections are UTC (RUNTIME_DB_TIME_ZONE).
	assert(!mysql_query(connection, "SET time_zone='+00:00'"));
	maintenance_request request = {};
	request.work_id = static_cast<uint64_t>(atoll(argv[7]));
	request.job_id = maintenance_job_id::level_cap;
	request.row_budget = 32;
	request.time_budget_usec = MAINTENANCE_TIME_BUDGET_USEC_MAX;
	request.deadline_usec = persistence_observability_now_usec() + 10000000;
	request.value_count = 1;
	request.values[0] = atoll(argv[6]);
	const maintenance_result result = maintenance_repository_execute(request, nullptr);
	if (result.outcome != maintenance_outcome::complete)
	{
		printf("failed %u\n", result.error_code);
		return 1;
	}
	printf("complete %u", result.rows);
	for (size_t index = 0; index < result.value_count; ++index)
		printf(" %lld", static_cast<long long>(result.values[index]));
	printf("\n");
	return 0;
}
