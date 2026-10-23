#include "persistence/critical_outbox.h"

#include <cassert>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <mysql.h>
#include <future>
#include <mutex>
#include <string>
#include <thread>

static MYSQL *database_connection = nullptr;
static MYSQL *worker_connection = nullptr;
static std::atomic<bool> pool_available = true;
static std::atomic<bool> fail_counts = false, fail_audit = false, fail_observation = false;
static std::atomic<bool> disconnect_counts = false;
static std::atomic<bool> lose_commit_ack = false;
static std::atomic<unsigned int> audits = 0, fetches = 0, observations = 0, replacements = 0;
static std::mutex query_mutex;
static std::string counts_sql;

static MYSQL *connect_database()
{
	MYSQL *connection = mysql_init(nullptr);
	assert(connection);
	const char *port = getenv("DB_PORT");
	assert(mysql_real_connect(
		connection, getenv("DB_HOST"), getenv("DB_USER"), getenv("DB_PASSWD"),
		getenv("CRITICAL_TEST_DB_NAME"),
		static_cast<unsigned int>(strtoul(port ? port : "3306", nullptr, 10)), nullptr, 0));
	return connection;
}

extern "C" int __real_mysql_real_query(MYSQL *, const char *, unsigned long);
extern "C" int __wrap_mysql_real_query(MYSQL *connection, const char *sql, unsigned long length)
{
	const std::string query(sql, length);
	bool fail = false;
	if (query == "COMMIT" && lose_commit_ack.exchange(false))
	{
		assert(__real_mysql_real_query(connection, sql, length) == 0);
		MYSQL *killer = connect_database();
		const std::string kill = "KILL " + std::to_string(mysql_thread_id(connection));
		assert(__real_mysql_real_query(killer, kill.data(), kill.size()) == 0);
		mysql_close(killer);
		// The durable commit happened, but its caller sees a lost connection.
		return __real_mysql_real_query(connection, "SELECT 1", 8);
	}
	if (query.find("SELECT (SELECT COUNT(*) FROM critical_outbox") == 0)
	{
		{
			std::lock_guard<std::mutex> lock(query_mutex);
			counts_sql = query;
		}
		fail = fail_counts;
		if (disconnect_counts.exchange(false))
		{
			MYSQL *killer = connect_database();
			const std::string kill =
				"KILL " + std::to_string(mysql_thread_id(connection));
			assert(__real_mysql_real_query(killer, kill.data(), kill.size()) == 0);
			mysql_close(killer);
		}
	}
	else if (query.find("SELECT COUNT(*) FROM critical_operation_inbox i") == 0)
	{
		++audits;
		fail = fail_audit;
	}
	else if (query.find("SELECT EXISTS(SELECT 1 FROM critical_outbox") == 0)
	{
		++observations;
		fail = fail_observation;
	}
	else if (query.find("SELECT outbox_id,operation_id,destination") == 0)
		++fetches;
	// A genuine server SQL error leaves the connection usable. Connection-loss
	// coverage above actually kills the connection and exercises replacement.
	if (fail)
	{
		static const char invalid[] = "SELECT * FROM outbox_deliberately_missing_table";
		return __real_mysql_real_query(connection, invalid, sizeof(invalid) - 1);
	}
	return __real_mysql_real_query(connection, sql, length);
}

extern "C" MYSQL *sql_pool_acquire(void)
{
	return pool_available ? worker_connection : nullptr;
}
extern "C" MYSQL *sql_pool_replace_connection(MYSQL *)
{
	mysql_close(worker_connection);
	worker_connection = connect_database();
	++replacements;
	return worker_connection;
}

static void execute(const char *sql)
{
	const int result = mysql_real_query(database_connection, sql, strlen(sql));
	if (result != 0)
		fprintf(stderr, "critical outbox query failed: %s\n",
			mysql_error(database_connection));
	assert(result == 0);
}

static unsigned long long scalar(const char *sql)
{
	execute(sql);
	MYSQL_RES *result = mysql_store_result(database_connection);
	assert(result);
	MYSQL_ROW row = mysql_fetch_row(result);
	assert(row && row[0]);
	const unsigned long long value = strtoull(row[0], nullptr, 10);
	mysql_free_result(result);
	return value;
}

static void clear_rows()
{
	execute("DELETE d FROM critical_outbox_delivery_dedupe d JOIN critical_outbox o ON "
		"o.outbox_id=d.outbox_id WHERE o.operation_id IN "
		"(UNHEX('00000000000000000000000000000001'),"
		"UNHEX('00000000000000000000000000000002'),"
		"UNHEX('00000000000000000000000000000003'))");
	execute("DELETE FROM critical_outbox WHERE operation_id IN "
		"(UNHEX('00000000000000000000000000000001'),"
		"UNHEX('00000000000000000000000000000002'),"
		"UNHEX('00000000000000000000000000000003'))");
	execute("DELETE FROM critical_operation_inbox WHERE operation_id IN "
		"(UNHEX('00000000000000000000000000000001'),"
		"UNHEX('00000000000000000000000000000002'),"
		"UNHEX('00000000000000000000000000000003'))");
	execute("DELETE FROM critical_test_state");
}

static void insert_record(unsigned int suffix)
{
	const char digit = static_cast<char>('0' + suffix);
	char sql[2048] = {};
	snprintf(
		sql, sizeof(sql),
		"INSERT INTO critical_operation_inbox(operation_id,command_hash,keys_hash,"
		"command_type,schema_version,payload_version,status,result_payload,committed_at) "
		"VALUES(UNHEX('0000000000000000000000000000000%c'),UNHEX(REPEAT('11',32)),"
		"UNHEX(REPEAT('22',32)),1,1,1,1,'',CURRENT_TIMESTAMP(6));"
		"INSERT INTO critical_outbox(operation_id,event_index,destination,event_type,"
		"payload_version,payload) VALUES(UNHEX('0000000000000000000000000000000%c'),0,1,1,1,"
		"UNHEX(REPEAT('33',16)))",
		digit, digit);
	const char *separator = strchr(sql, ';');
	assert(separator);
	std::string first(sql, static_cast<size_t>(separator - sql));
	execute(first.c_str());
	execute(separator + 1);
}

struct delivery_state
{
	unsigned int calls;
	bool retry_first;
	bool terminal;
};
static std::atomic<bool> block_delivery = false, delivery_entered = false;
static std::atomic<bool> publication_queued = false, publication_ready = false;
static bool needs_publication = false;
static bool duplicate_delivery = false;
static std::thread::id game_thread;

static void publish()
{
	assert(std::this_thread::get_id() == game_thread);
	if (publication_queued && !publication_ready)
	{
		publication_ready = true;
		critical_outbox_resume();
	}
}

static critical_outbox_delivery_result deliver(const critical_outbox_record &record, void *raw)
{
	auto &state = *static_cast<delivery_state *>(raw);
	assert(record.outbox_id && record.destination == 1 && record.event_type == 1 &&
	       record.payload_version == 1 && record.payload.size() == 16 &&
	       record.operation_id.bytes[15] >= 1 && record.operation_id.bytes[15] <= 3);
	++state.calls;
	delivery_entered = true;
	while (block_delivery)
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	if (needs_publication && !publication_ready)
	{
		publication_queued = true;
		return critical_outbox_delivery_result::retryable_failure;
	}
	if (state.terminal)
		return critical_outbox_delivery_result::terminal_failure;
	if (state.retry_first && state.calls == 1)
		return critical_outbox_delivery_result::retryable_failure;
	if (duplicate_delivery)
		return critical_outbox_delivery_result::already_delivered;
	return critical_outbox_delivery_result::delivered;
}

template <typename Predicate> static void wait_until(Predicate predicate)
{
	const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
	while (!predicate())
	{
		assert(std::chrono::steady_clock::now() < deadline);
		std::this_thread::sleep_for(std::chrono::milliseconds(10));
	}
}

int main()
{
	assert(mysql_library_init(0, nullptr, nullptr) == 0);
	database_connection = connect_database();
	worker_connection = connect_database();
	game_thread = std::this_thread::get_id();
	assert(!critical_outbox_drain(0));
	// The wrapper owns an isolated database with ordinary production-shaped tables.
	clear_rows();

	insert_record(1);
	delivery_state state = {};
	assert(critical_outbox_init(deliver, &state));
	// Startup health is zero before the first poll; only a new worker observation
	// can establish emptiness after the committed record is delivered.
	assert(!critical_outbox_health_copy().counts_available);
	assert(critical_outbox_drain(1000));
	wait_until([&] { return critical_outbox_health_copy().delivered == 1; });
	critical_outbox_shutdown();
	assert(scalar("SELECT COUNT(*) FROM critical_outbox WHERE status=1 AND operation_id="
		      "UNHEX('00000000000000000000000000000001')") == 1);
	assert(scalar("SELECT COUNT(*) FROM critical_outbox_delivery_dedupe d JOIN "
		      "critical_outbox o ON o.outbox_id=d.outbox_id WHERE o.operation_id="
		      "UNHEX('00000000000000000000000000000001')") == 1);

	clear_rows();
	insert_record(2);
	state = { .calls = 0, .retry_first = true, .terminal = false };
	assert(critical_outbox_init(deliver, &state));
	wait_until([&] { return critical_outbox_health_copy().retries == 1; });
	critical_outbox_shutdown();
	execute("UPDATE critical_outbox SET next_attempt_at=CURRENT_TIMESTAMP(6) WHERE "
		"operation_id=UNHEX('00000000000000000000000000000002')");
	state.retry_first = false;
	assert(critical_outbox_init(deliver, &state));
	wait_until([&] { return critical_outbox_health_copy().delivered == 1; });
	critical_outbox_shutdown();
	assert(state.calls == 2);
	assert(scalar("SELECT COUNT(*) FROM critical_outbox WHERE status=1 AND attempt_count=1 "
		      "AND operation_id=UNHEX('00000000000000000000000000000002')") == 1);

	clear_rows();
	insert_record(3);
	state = { .calls = 0, .retry_first = false, .terminal = true };
	assert(critical_outbox_init(deliver, &state));
	wait_until([&] { return critical_outbox_health_copy().terminal_failures == 1; });
	critical_outbox_shutdown();
	assert(scalar("SELECT COUNT(*) FROM critical_outbox WHERE status=2 AND operation_id="
		      "UNHEX('00000000000000000000000000000003')") == 1);
	puts("outbox delivery, fresh startup drain, retry/restart and terminal failure passed");
	clear_rows();
	insert_record(1);
	state = {};
	lose_commit_ack = true;
	assert(critical_outbox_init(deliver, &state));
	assert(critical_outbox_drain(1000));
	critical_outbox_shutdown();
	assert(state.calls == 1);
	assert(scalar("SELECT COUNT(*) FROM critical_outbox_delivery_dedupe") == 1);
	clear_rows();
	insert_record(2);
	state = {};
	duplicate_delivery = true;
	assert(critical_outbox_init(deliver, &state));
	assert(critical_outbox_drain(1000));
	assert(critical_outbox_health_copy().duplicates == 1);
	critical_outbox_shutdown();
	duplicate_delivery = false;
	puts("outbox ambiguous commit reconciliation and duplicate callback passed");

	clear_rows();
	state = {};
	assert(critical_outbox_init(deliver, &state));
	assert(critical_outbox_drain(1000));
	wait_until([] { return critical_outbox_health_copy().counts_available; });
	// A new commit after an observed zero must not reuse that old observation.
	insert_record(1);
	execute("UPDATE critical_outbox SET next_attempt_at=TIMESTAMPADD(HOUR,1,CURRENT_TIMESTAMP(6))");
	assert(!critical_outbox_drain(80));
	wait_until([] { return critical_outbox_health_copy().pending == 1; });
	critical_outbox_quiesce();
	assert(!critical_outbox_health_copy().accepting);
	// Preserve a last-good positive count when diagnostics fail, but let delivery
	// and the independent empty check complete.
	fail_counts = true;
	execute("UPDATE critical_outbox SET next_attempt_at=CURRENT_TIMESTAMP(6)");
	assert(critical_outbox_drain(1000));
	wait_until([] { return critical_outbox_health_copy().counts_stale; });
	assert(critical_outbox_health_copy().pending == 1);
	fail_counts = false;
	critical_outbox_resume();
	wait_until([] { return !critical_outbox_health_copy().counts_stale; });
	assert(critical_outbox_health_copy().pending == 0);
	assert(critical_outbox_health_copy().accepting);
	// SQL failure and pool outage cannot reuse an earlier successful drain.
	fail_observation = true;
	assert(!critical_outbox_drain(80));
	fail_observation = false;
	pool_available = false;
	assert(!critical_outbox_drain(80));
	pool_available = true;
	assert(critical_outbox_drain(1000));
	const unsigned int replaced_before = replacements;
	disconnect_counts = true;
	critical_outbox_resume();
	wait_until([&] { return replacements > replaced_before; });
	assert(critical_outbox_drain(1000));
	critical_outbox_shutdown();
	assert(!critical_outbox_drain(0));

	clear_rows();
	insert_record(1);
	state = {};
	block_delivery = true;
	delivery_entered = false;
	assert(critical_outbox_init(deliver, &state));
	wait_until([] { return delivery_entered.load(); });
	auto in_flight = std::async(std::launch::async, [] { return critical_outbox_drain(1000); });
	assert(in_flight.wait_for(std::chrono::milliseconds(50)) == std::future_status::timeout);
	block_delivery = false;
	assert(in_flight.get());
	critical_outbox_shutdown();
	clear_rows();
	insert_record(1);
	execute("UPDATE critical_outbox SET next_attempt_at=TIMESTAMPADD(HOUR,1,CURRENT_TIMESTAMP(6))");
	assert(critical_outbox_init(deliver, &state));
	auto stopping = std::async(std::launch::async, [] { return critical_outbox_drain(1000); });
	assert(stopping.wait_for(std::chrono::milliseconds(30)) == std::future_status::timeout);
	critical_outbox_shutdown();
	assert(!stopping.get());

	clear_rows();
	insert_record(2);
	state = {};
	needs_publication = true;
	publication_queued = publication_ready = false;
	assert(critical_outbox_init(deliver, &state, publish));
	assert(critical_outbox_drain(3000));
	assert(publication_ready && critical_outbox_health_copy().retries == 1);
	critical_outbox_shutdown();
	needs_publication = false;
	puts("outbox commit/in-flight/future-retry/failure drains and game-thread publication passed");

	// Compare actual operational SQL row work before/after retained history.
	clear_rows();
	insert_record(1);
	insert_record(2);
	insert_record(3);
	execute("UPDATE critical_outbox SET next_attempt_at=TIMESTAMPADD(HOUR,1,CURRENT_TIMESTAMP(6))");
	execute("UPDATE critical_outbox SET status=2 WHERE operation_id=UNHEX('00000000000000000000000000000002')");
	execute("DELETE FROM critical_outbox WHERE operation_id=UNHEX('00000000000000000000000000000003')");
	execute("UPDATE critical_operation_inbox SET status=0 WHERE operation_id=UNHEX('00000000000000000000000000000003')");
	assert(critical_outbox_init(deliver, &state));
	wait_until([] { return critical_outbox_health_copy().counts_available; });
	auto mixed = critical_outbox_health_copy();
	assert(mixed.pending == 1 && mixed.dead_letter == 1 && mixed.incomplete_inbox == 1);
	critical_outbox_shutdown();
	std::string operational;
	{
		std::lock_guard<std::mutex> lock(query_mutex);
		operational = counts_sql;
	}
	auto row_work = [&]
	{
		const auto before = scalar(
			"SELECT VARIABLE_VALUE FROM information_schema.SESSION_STATUS WHERE VARIABLE_NAME='Handler_read_next'");
		execute(operational.c_str());
		MYSQL_RES *result = mysql_store_result(database_connection);
		assert(result);
		MYSQL_ROW row = mysql_fetch_row(result);
		assert(row && strtoull(row[0], nullptr, 10) == 1 &&
		       strtoull(row[1], nullptr, 10) == 1 && strtoull(row[3], nullptr, 10) == 1);
		mysql_free_result(result);
		return scalar("SELECT VARIABLE_VALUE FROM information_schema.SESSION_STATUS WHERE VARIABLE_NAME='Handler_read_next'") -
		       before;
	};
	const auto before_history = row_work();
	std::string digits =
		"(SELECT 0 n UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9)";
	std::string numbers = "SELECT 1000+a.n+10*b.n+100*c.n+1000*d.n+10000*e.n n FROM " + digits +
			      " a CROSS JOIN " + digits + " b CROSS JOIN " + digits +
			      " c CROSS JOIN " + digits + " d CROSS JOIN " + digits + " e";
	execute(("INSERT INTO critical_operation_inbox(operation_id,command_hash,keys_hash,command_type,schema_version,payload_version,status,result_payload,committed_at) SELECT UNHEX(LPAD(HEX(n),32,'0')),UNHEX(REPEAT('11',32)),UNHEX(REPEAT('22',32)),1,1,1,1,'',CURRENT_TIMESTAMP(6) FROM (" +
		 numbers + ") numbers")
			.c_str());
	execute("INSERT INTO critical_outbox(operation_id,event_index,destination,event_type,payload_version,payload,status) SELECT operation_id,0,1,1,1,UNHEX(REPEAT('33',16)),1 FROM critical_operation_inbox WHERE operation_id>=UNHEX('000000000000000000000000000003e8')");
	assert(row_work() == before_history);
	assert(before_history < 20);
	execute(("EXPLAIN FORMAT=JSON " + operational).c_str());
	MYSQL_RES *plan_result = mysql_store_result(database_connection);
	assert(plan_result);
	MYSQL_ROW plan_row = mysql_fetch_row(plan_result);
	assert(plan_row && plan_row[0]);
	const std::string plan = plan_row[0];
	assert(plan.find("\"access_type\": \"ALL\"") == std::string::npos);
	assert(plan.find("\"access_type\": \"index\"") == std::string::npos);
	mysql_free_result(plan_result);
	// A large *active* backlog is counted exactly and remains ineligible for fetch.
	execute("UPDATE critical_outbox SET status=0,next_attempt_at=TIMESTAMPADD(HOUR,1,CURRENT_TIMESTAMP(6)) WHERE operation_id>=UNHEX('000000000000000000000000000003e8') LIMIT 10000");
	assert(critical_outbox_init(deliver, &state));
	wait_until([] { return critical_outbox_health_copy().counts_available; });
	assert(critical_outbox_health_copy().pending == 10001);
	assert(!critical_outbox_drain(80));
	critical_outbox_shutdown();
	execute("DELETE FROM critical_outbox WHERE operation_id>=UNHEX('000000000000000000000000000003e8')");
	execute("DELETE FROM critical_operation_inbox WHERE operation_id>=UNHEX('000000000000000000000000000003e8')");
	printf("outbox mixed counters and 100k delivered-history scaling passed (%llu indexed next reads)\n",
	       before_history);

	// One real minute proves the production deadline; do not add a test-only
	// scheduler/configuration surface to the worker.
	clear_rows();
	state = {};
	const unsigned int audits_before = audits;
	assert(critical_outbox_init(deliver, &state));
	wait_until(
		[&] {
			return audits > audits_before &&
			       critical_outbox_health_copy().audit_available;
		});
	const auto first_audit = std::chrono::steady_clock::now();
	const unsigned int fetches_before = fetches;
	fail_audit = true;
	insert_record(1);
	assert(critical_outbox_drain(1000));
	for (unsigned int i = 0; i < 10; ++i)
	{
		critical_outbox_resume();
		std::this_thread::sleep_for(std::chrono::milliseconds(10));
	}
	assert(audits == audits_before + 1);
	assert(fetches > fetches_before);
	puts("checking independent 60-second audit deadline and failure backoff...");
	fflush(stdout);
	while (audits == audits_before + 1)
	{
		assert(std::chrono::steady_clock::now() - first_audit < std::chrono::seconds(63));
		std::this_thread::sleep_for(std::chrono::milliseconds(20));
	}
	assert(std::chrono::steady_clock::now() - first_audit >= std::chrono::milliseconds(59500));
	wait_until([] { return critical_outbox_health_copy().audit_stale; });
	assert(critical_outbox_health_copy().audit_available);
	assert(critical_outbox_health_copy().committed_without_outbox == 0);
	assert(critical_outbox_health_copy().audit_age_msec >= 59500);
	fail_audit = false;
	critical_outbox_resume();
	std::this_thread::sleep_for(std::chrono::milliseconds(800));
	assert(audits == audits_before + 2); // No catch-up burst after a failed attempt/resume.
	insert_record(2);
	assert(critical_outbox_drain(1000));
	critical_outbox_shutdown();
	puts("outbox independent audit cadence, stale last-good values and continued delivery passed");
	clear_rows();
	insert_record(1);
	state = {};
	fail_counts = fail_audit = true;
	const unsigned int unavailable_audits = audits;
	assert(critical_outbox_init(deliver, &state));
	assert(critical_outbox_drain(1000));
	wait_until([&] { return audits > unavailable_audits; });
	assert(!critical_outbox_health_copy().counts_available);
	assert(!critical_outbox_health_copy().audit_available);
	std::this_thread::sleep_for(std::chrono::milliseconds(800));
	assert(audits == unavailable_audits + 1);
	critical_outbox_shutdown();
	fail_counts = fail_audit = false;
	puts("outbox unavailable diagnostics do not block delivery or retry audits rapidly");

	clear_rows();
	mysql_close(worker_connection);
	mysql_close(database_connection);
	database_connection = nullptr;
	return 0;
}
