// Real scheduler -> durable capture -> SQL/file outputs. Faults affect only I/O;
// the production scheduler, identity, retry, marker, and append logic are linked.
#include "persistence/maintenance_repository.h"
#include "persistence/maintenance_scheduler.h"
#include "sql/sql_pool.h"

#include <cassert>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <unistd.h>

static std::string mode;
static int64_t captured;
static size_t captures = 0;
static size_t attempts = 0;
static bool injected = false;
static bool partial = false;
static size_t syncs = 0;
static maintenance_request first = {};

extern "C" MYSQL *sql_pool_acquire(void)
{
	MYSQL *db = mysql_init(nullptr);
	assert(mysql_real_connect(db, getenv("TEST_DB_HOST"), getenv("TEST_DB_USER"),
				  getenv("TEST_DB_PASSWORD"), getenv("STATISTICS_TEST_DB"),
				  atoi(getenv("TEST_DB_PORT")), nullptr, 0));
	assert(mysql_query(db, "SET time_zone='+00:00'") == 0);
	return db;
}

extern "C" void sql_pool_release(MYSQL *db)
{
	mysql_close(db);
}

static bool statistics_file(int fd)
{
	char link[64], path[4096] = {};
	snprintf(link, sizeof(link), "/proc/self/fd/%d", fd);
	const ssize_t size = readlink(link, path, sizeof(path) - 1);
	return size > 0 && strstr(path, "/statistics_general");
}

extern "C" ssize_t __real_write(int, const void *, size_t);
extern "C" ssize_t __wrap_write(int fd, const void *data, size_t size)
{
	if (!injected && statistics_file(fd))
	{
		if (mode == "partial" || mode == "crash_partial")
		{
			if (!partial)
			{
				partial = true;
				return __real_write(fd, data, size / 2);
			}
			injected = true;
			errno = EIO;
			return -1;
		}
		if (mode == "file" || mode == "crash_file")
		{
			injected = true;
			errno = EIO;
			return -1;
		}
	}
	return __real_write(fd, data, size);
}

extern "C" int __real_fsync(int);
extern "C" int __wrap_fsync(int fd)
{
	if (!injected && mode == "slow_state")
	{
		injected = true;
		std::this_thread::sleep_for(std::chrono::milliseconds(100));
	}
	if (statistics_file(fd))
	{
		++syncs;
		if (!injected && mode == "fsync")
		{
			injected = true;
			errno = EIO;
			return -1;
		}
	}
	return __real_fsync(fd);
}

extern "C" int __real_mysql_real_query(MYSQL *, const char *, unsigned long);
extern "C" int __wrap_mysql_real_query(MYSQL *db, const char *query, unsigned long size)
{
	const std::string sql(query, size);
	if (!injected && mode == "sql" && sql.starts_with("INSERT INTO statistics"))
	{
		injected = true;
		return 1;
	}
	const int result = __real_mysql_real_query(db, query, size);
	if (!injected && mode == "commit_ack" && sql == "COMMIT")
	{
		assert(result == 0);
		injected = true;
		return 1;
	}
	return result;
}

static bool prepare(maintenance_request &request, void *)
{
	if (request.job_id != maintenance_job_id::operational_statistics)
		return false;
	++captures;
	request.value_count = 12;
	// A recapture crosses midnight and changes every counter: both are observable.
	request.values[0] = captured + (captures - 1) * 86400;
	for (size_t i = 1; i < 12; ++i)
		request.values[i] = i * captures;
	return true;
}

static maintenance_result execute(const maintenance_request &request, void *)
{
	if (++attempts == 1)
		first = request;
	else
	{
		assert(request.work_id == first.work_id);
		assert(request.value_count == first.value_count && request.values == first.values);
		assert(request.scheduled_tick == first.scheduled_tick);
	}
	if (mode == "file" && attempts <= 3)
		injected = false;
	const auto result = maintenance_repository_execute(request, nullptr);
	if (mode.starts_with("crash_"))
	{
		if (mode == "crash_complete")
			assert(result.outcome == maintenance_outcome::complete);
		else
			assert(injected &&
			       result.outcome == maintenance_outcome::retryable_failure);
		// The scheduler's request is durable; its completion has not been saved.
		_exit(42);
	}
	return result;
}

int main(int argc, char **argv)
{
	assert(argc == 3);
	mode = argv[1];
	captured = atoll(argv[2]);
	assert(maintenance_scheduler_set_state_path("scheduler.state"));
	if (mode == "invalid")
	{
		assert(!maintenance_scheduler_init(9, execute, nullptr, prepare));
		return 0;
	}
	assert(maintenance_scheduler_init(9, execute, nullptr, prepare));
	if (mode.ends_with("resume"))
		maintenance_scheduler_quiesce();
	const auto end = std::chrono::steady_clock::now() + std::chrono::seconds(15);
	const size_t statistics = static_cast<size_t>(maintenance_job_id::operational_statistics);
	bool complete = false;
	for (uint64_t tick = 0; !complete; ++tick)
	{
		assert(std::chrono::steady_clock::now() < end);
		if (mode == "unacked" && maintenance_scheduler_health_copy(tick).completions)
			break;
		maintenance_result results[MAINTENANCE_COMPLETION_MAX] = {};
		const size_t count =
			maintenance_scheduler_pulse(tick, results, MAINTENANCE_COMPLETION_MAX);
		for (size_t i = 0; i < count; ++i)
		{
			assert(results[i].job_id == maintenance_job_id::operational_statistics);
			if (mode == "corrupt" || mode == "conflict_resume")
			{
				assert(results[i].outcome ==
				       maintenance_outcome::permanent_failure);
				assert(results[i].error_code == EILSEQ);
				complete = true;
				continue;
			}
			assert(results[i].outcome == maintenance_outcome::complete ||
			       results[i].outcome == maintenance_outcome::retryable_failure);
			complete = results[i].outcome == maintenance_outcome::complete;
			if (!complete)
				maintenance_scheduler_resume();
		}
		if (maintenance_scheduler_health_copy(tick).jobs[statistics].active)
		{
			// Do not advance game time while a bounded worker call is in flight.
			while (!maintenance_scheduler_health_copy(tick).completions)
			{
				assert(std::chrono::steady_clock::now() < end);
				std::this_thread::sleep_for(std::chrono::milliseconds(1));
			}
		}
	}
	maintenance_scheduler_shutdown();
	assert(captures == (mode.ends_with("resume") ? 0 : 1));
	if (mode == "sql" || mode == "commit_ack" || mode == "file" || mode == "partial" ||
	    mode == "fsync")
		assert(injected && attempts >= 2);
	if (mode == "file")
		assert(attempts >= 4);
	if (mode == "fsync")
		assert(syncs >= 2);
	printf("%s: captures=%zu attempts=%zu work_id=%llu\n", mode.c_str(), captures, attempts,
	       static_cast<unsigned long long>(first.work_id));
}
