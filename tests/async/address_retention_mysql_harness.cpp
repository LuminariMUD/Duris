// The hourly address prune (ADR 0003) on a real database. Runs the maintenance job with
// the given row budget until it reports complete, printing each run's outcome and rows.
// Arguments: host port user password database row-budget.
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
extern "C" void sql_pool_release(MYSQL *) {}
// The prune never reaches the frag cap jobs.
const struct frag_cap_config *frag_cap_config_get(void)
{
	return nullptr;
}
int frag_cap_config_cap_level_from_frags(double)
{
	return 0;
}
int frag_cap_config_timer_days(int)
{
	return 0;
}
int frag_cap_config_boon_duration_minutes(void)
{
	return 0;
}
int frag_cap_config_boon_bonus(void)
{
	return 0;
}

int main(int argc, char **argv)
{
	assert(argc == 7);
	connection = mysql_init(nullptr);
	assert(mysql_real_connect(connection, argv[1], argv[3], argv[4], argv[5], atoi(argv[2]),
				  nullptr, 0));
	for (uint64_t work = 1; work < 100; ++work)
	{
		maintenance_request request = {};
		request.work_id = work;
		request.job_id = maintenance_job_id::address_retention;
		request.row_budget = static_cast<uint32_t>(atoi(argv[6]));
		request.time_budget_usec = MAINTENANCE_TIME_BUDGET_USEC_MAX;
		// A container's first queries can be slow; the budget is not what this tests.
		request.deadline_usec = persistence_observability_now_usec() + 10000000;
		const maintenance_result result = maintenance_repository_execute(request, nullptr);
		printf("%s %u\n",
		       result.outcome == maintenance_outcome::complete ? "complete" :
		       result.outcome == maintenance_outcome::more     ? "more" :
									 "failed",
		       result.rows);
		if (result.outcome != maintenance_outcome::more)
			return result.outcome == maintenance_outcome::complete ? 0 : 1;
	}
	return 1;
}
