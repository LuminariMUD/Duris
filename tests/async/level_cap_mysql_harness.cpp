// The level cap job on a real database, with the shipped lib/frag_cap.cfg. Runs the job once
// as if at the given time and prints its outcome, rows and, after an unlock, the side, the
// level and whether it opened to every side.
// Arguments: host port user password database now work-id.
#include "combat/frag_cap_config.h"
#include "combat/frag_cap_repository.h"
#include "persistence/persistence_mode.h"
#include "persistence/maintenance_repository.h"
#include "persistence/persistence_observability.h"
#include "sql/sql_pool.h"

#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>

enum persistence_mode persistence_mode_get(void)
{
	return PERSISTENCE_MODE_MARIADB_PRIMARY;
}
const char *persistence_mode_flatfile_root(void)
{
	return nullptr;
}

static MYSQL *connection;

extern "C" MYSQL *sql_pool_acquire(void)
{
	return connection;
}

int main(int argc, char **argv)
{
	assert(argc >= 8);
	boot_frag_cap_config();
	connection = mysql_init(nullptr);
	assert(mysql_real_connect(connection, argv[1], argv[3], argv[4], argv[5], atoi(argv[2]),
				  nullptr, 0));
	// The runtime's connections are UTC (RUNTIME_DB_TIME_ZONE).
	assert(!mysql_query(connection, "SET time_zone='+00:00'"));
	if (argc >= 9)
	{
		const int64_t now = atoll(argv[6]) * 1000000;
		frag_cap_state state;
		assert(!mysql_query(connection, "START TRANSACTION"));
		const bool adopt = !strcmp(argv[8], "adopt");
		const auto loaded =
			adopt ? frag_cap_sql_adopt(connection,
						   frag_cap_config_get()->cap_floor_level,
						   frag_cap_config_get()->legacy_maximum_level, now,
						   &state, frag_cap_config_policy()) :
				frag_cap_sql_load(connection, &state, true);
		if (loaded != frag_cap_store_result::ok)
		{
			assert(!mysql_query(connection, "ROLLBACK"));
			printf("invalid\n");
			return 2;
		}
		if (!strcmp(argv[8], "credit"))
		{
			assert(argc == 12);
			const frag_cap_award award = { static_cast<frag_cap_side>(atoi(argv[9])),
						       atoll(argv[10]) };
			const uint64_t revision = state.revision;
			assert(frag_cap_apply(&state, atoll(argv[11]) * 1000000, now, &award, 1,
					      frag_cap_config_policy()));
			if (state.revision != revision)
				assert(frag_cap_sql_save(connection, state) ==
				       frag_cap_store_result::ok);
		}
		assert(!mysql_query(connection, "COMMIT"));
		printf("%d %llu %lld %lld %llu %llu %d %d", state.level,
		       static_cast<unsigned long long>(state.revision),
		       static_cast<long long>(state.round_start / 1000000),
		       static_cast<long long>(state.deadline / 1000000),
		       static_cast<unsigned long long>(state.earned[0]),
		       static_cast<unsigned long long>(state.earned[1]),
		       frag_cap_for_side(state, frag_cap_side::good),
		       frag_cap_for_side(state, frag_cap_side::evil));
		printf("\n");
		return 0;
	}
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
