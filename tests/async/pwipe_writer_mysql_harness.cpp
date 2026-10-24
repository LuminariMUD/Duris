// Real shared writer, SQL callback queue, transactional repositories and pool.
// Only the unrelated subsystem drains and connection configuration are controlled.
#include "persistence/critical_command_coordinator.h"
#include "persistence/critical_outbox.h"
#include "persistence/persistence_observability.h"
#include "player/player_snapshot_repository.h"
#include "sql/sql.h"
#include "sql/sql_async.h"
#include "sql/sql_pool.h"

#include <chrono>
#include <condition_variable>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <mutex>
#include <string>

MYSQL *DB = nullptr;

namespace
{
void require(bool condition, const std::string &message)
{
	if (!condition)
	{
		std::cerr << "FAILED: " << message << '\n';
		std::exit(1);
	}
}

std::mutex held_mutex;
std::condition_variable held_changed;
bool held_started = false, held_released = false;
bool timeout_case = false, error_case = false, error_callback = false;
int resumes = 0, callbacks = 0;
std::shared_ptr<sql_write_receipt> dependent_receipt = std::make_shared<sql_write_receipt>();
constexpr int pid = 1001;
const std::string counter = "critical_test_state WHERE entity_type=1 AND entity_id=1001";

MYSQL *open_connection()
{
	MYSQL *connection = mysql_init(nullptr);
	require(connection != nullptr, "allocate SQL connection");
	require(mysql_real_connect(connection, getenv("DB_HOST"), getenv("DB_USER"),
				   getenv("DB_PASSWD"), getenv("DB_NAME"),
				   std::strtoul(getenv("DB_PORT"), nullptr, 10), nullptr, 0),
		"connect to owned SQL fixture");
	return connection;
}

void execute(const std::string &query)
{
	require(mysql_real_query(DB, query.data(), query.size()) == 0,
		query + ": " + mysql_error(DB));
}

std::string scalar(const std::string &query)
{
	execute(query);
	MYSQL_RES *result = mysql_store_result(DB);
	require(result && mysql_num_rows(result) == 1 && mysql_num_fields(result) == 1,
		"one scalar row: " + query);
	MYSQL_ROW row = mysql_fetch_row(result);
	require(row && row[0], "non-NULL scalar");
	const std::string value = row[0];
	mysql_free_result(result);
	return value;
}

void release_held()
{
	std::lock_guard<std::mutex> lock(held_mutex);
	held_released = true;
	held_changed.notify_all();
}

player_snapshot snapshot(player_revision_t revision, int proficiency)
{
	player_snapshot result{};
	result.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
	result.pid = pid;
	result.revision = revision;
	result.components = PLAYER_COMPONENT_LANGUAGES;
	result.encoded_size_bound = 1024;
	result.languages.push_back({ 1, proficiency, 0 });
	return result;
}

void require_saved(const char *revision, const char *proficiency, const char *value)
{
	require(scalar("SELECT save_revision FROM player_data WHERE pid=1001") == revision,
		"accepted player save revision committed");
	require(scalar("SELECT proficiency FROM player_languages WHERE pid=1001 AND tongue_id=1") ==
			proficiency,
		"accepted player save payload committed");
	require(scalar("SELECT value FROM " + counter) == value, "expected committed SQL counter");
}

void drain_callbacks()
{
	// Same contract as the owning preparation: callbacks may enqueue another read.
	for (int pulse = 0; pulse < 8; ++pulse)
	{
		require(persistence_writer_wait_idle(3000), "accepted SQL finishes after release");
		if (!sql_async_pulse())
			return;
	}
	require(false, "finite dependent callback chain");
}
} // namespace

// The owned fixture uses plain loopback connections; runtime credential/exclusion
// validation is qualified separately. Pool ownership/transactions are real here.
MYSQL *sql_open_configured_connection(unsigned long)
{
	return open_connection();
}
// A language-only capture never serializes item descriptions. Refuse accidental
// expansion into the unrelated legacy string-escaping adapter.
char *sql_escape_string(const char *)
{
	std::abort();
}

void logit(const char *, const char *format, ...)
{
	va_list args;
	va_start(args, format);
	vfprintf(stderr, format, args);
	va_end(args);
	fputc('\n', stderr);
}

critical_coordinator_health critical_command_coordinator_health_copy()
{
	return {};
}
critical_outbox_health critical_outbox_health_copy()
{
	return {};
}
void player_save_pipeline_resume()
{
	++resumes;
}
void critical_outbox_resume() {}
void critical_command_coordinator_resume() {}
void maintenance_scheduler_resume() {}
void maintenance_scheduler_quiesce() {}
void critical_command_coordinator_quiesce() {}
void critical_outbox_quiesce() {}
bool artifact_guild_transaction_drain(uint64_t)
{
	return true;
}
bool locker_async_drain(int)
{
	return true;
}
bool maintenance_scheduler_drain(uint64_t)
{
	return true;
}
bool critical_command_coordinator_drain(uint64_t)
{
	return true;
}
bool critical_outbox_drain(uint64_t)
{
	return true;
}
bool persistence_flush_all_character_saves()
{
	return true;
}
bool artifact_save_drain(uint64_t)
{
	if (error_case)
		require(sql_read_work(
				[](MYSQL *connection, sql_rows *rows)
				{
					unsigned int error = sql_execute(
						connection,
						"UPDATE critical_test_state SET value=value+100 WHERE entity_type=1 AND entity_id=1001");
					return error ? error :
						       sql_select(
							       connection,
							       "SELECT missing_pwipe_column FROM critical_test_state",
							       rows);
				},
				[](bool ok, const sql_rows &rows)
				{
					require(!ok && rows.empty(),
						"real failed SQL read callback");
					error_callback = true;
				}),
			"accept real terminal SQL failure after preparation captured health");
	if (!timeout_case)
		release_held();
	return true;
}
bool player_save_pipeline_drain(uint64_t timeout)
{
	return persistence_writer_wait_idle(timeout);
}
bool sql_ship_write_pulse()
{
	return true;
}

// Extracted from comm.c at compile time, rather than maintaining another copy.
#include "pwipe_preparation.inc"

int main(int argc, char **argv)
{
	require(argc == 2, "scenario required");
	const std::string scenario = argv[1];
	timeout_case = scenario == "timeout";
	error_case = scenario == "error";
	require(timeout_case || error_case || scenario == "success", "known scenario");
	require(mysql_library_init(0, nullptr, nullptr) == 0, "initialize SQL client");
	DB = open_connection();
	execute("DELETE FROM player_languages WHERE pid=1001");
	execute("DELETE FROM player_data WHERE pid=1001");
	execute("DELETE FROM " + counter);
	execute("INSERT INTO player_data(pid,name) VALUES (1001,'Writerprobe')");
	execute("INSERT INTO critical_test_state(entity_type,entity_id,value) VALUES (1,1001,0)");
	require(sql_pool_init(1) == 0, "initialize actual SQL pool");
	require(player_save_worker_init(player_snapshot_repository_apply_from_pool, nullptr),
		"initialize real shared writer");
	sql_async_boot_done();
	require(sql_read_work(
			[](MYSQL *connection, sql_rows *rows)
			{
				{
					std::unique_lock<std::mutex> lock(held_mutex);
					held_started = true;
					held_changed.notify_all();
					require(held_changed.wait_for(lock,
								      std::chrono::seconds(12),
								      [] { return held_released; }),
						"bounded held SQL work release");
				}
				return sql_select(
					connection,
					"SELECT value FROM critical_test_state WHERE entity_type=1 AND entity_id=1001",
					rows);
			},
			[](bool ok, const sql_rows &rows)
			{
				require(ok && rows.size() == 1 && rows[0][0] &&
						std::string(rows[0][0]) == "0",
					"held read precedes queued writes");
				++callbacks;
				require(sql_read(
						"SELECT value FROM critical_test_state WHERE entity_type=1 AND entity_id=1001",
						[](bool read_ok, const sql_rows &after)
						{
							require(read_ok && after.size() == 1 &&
									after[0][0] &&
									std::string(after[0][0]) ==
										"1",
								"dependent real read observes player/SQL saves ahead of it");
							++callbacks;
							require(sql_queue_statements(
									{ "UPDATE critical_test_state SET value=value+2 WHERE entity_type=1 AND entity_id=1001" },
									dependent_receipt),
								"callback admits dependent SQL write");
						}),
					"callback admits dependent real read");
			}),
		"accept held SQL read");
	{
		std::unique_lock<std::mutex> lock(held_mutex);
		require(held_changed.wait_for(lock, std::chrono::seconds(3),
					      [] { return held_started; }),
			"real SQL work entered worker");
	}
	require(player_save_worker_submit(snapshot(1, 42)) == player_save_submit_result::accepted,
		"accept player save behind held work");
	require(sql_queue(
			"UPDATE critical_test_state SET value=value+1 WHERE entity_type=1 AND entity_id=1001"),
		"accept SQL write behind held work");
	const auto pending = player_save_worker_health_copy();
	require(pending.inflight_jobs == 1 && pending.queued_jobs == 2,
		"held work and both accepted jobs pending");
	require(scalar("SELECT save_revision FROM player_data WHERE pid=1001") == "0" &&
			scalar("SELECT value FROM " + counter) == "0",
		"independent connection sees no early commit");

	const bool ready = pwipe_quiesce_writers();
	require(ready == (!timeout_case && !error_case), "owning quiescence result");
	if (timeout_case)
	{
		const auto retained = player_save_worker_health_copy();
		require(resumes == 1 && callbacks == 0 && retained.inflight_jobs == 1 &&
				retained.queued_jobs == 2,
			"timeout resumes without discarding accepted work");
		require(scalar("SELECT value FROM " + counter) == "0" &&
				scalar("SELECT save_revision FROM player_data WHERE pid=1001") ==
					"0",
			"timeout leaves SQL/player state untouched");
		release_held();
		drain_callbacks();
	}
	require(callbacks == 2 && dependent_receipt->finished.load(std::memory_order_acquire) &&
			dependent_receipt->ok,
		"both real read callbacks and dependent COMMIT completed");
	require_saved("1", "42", "3");
	require(sql_async_pulse() == 0, "no callbacks left after preparation/recovery");
	if (ready)
	{
		require(resumes == 0, "successful preparation keeps writers quiesced");
		require(!sql_queue(
				"UPDATE critical_test_state SET value=value+8 WHERE entity_type=1 AND entity_id=1001") &&
				player_save_worker_submit(snapshot(2, 43)) ==
					player_save_submit_result::unavailable,
			"closed admission refuses late SQL and player save");
		// The destructive operation is deliberately only this owned fixture's rows.
		// Full epoch reset/command/launcher behavior is qualified by the other journeys.
		execute("DELETE FROM player_languages WHERE pid=1001");
		execute("DELETE FROM " + counter);
		require(persistence_writer_wait_idle(3000) && sql_async_pulse() == 0,
			"no late work after deletion");
		require(scalar("SELECT COUNT(*) FROM player_languages WHERE pid=1001") == "0" &&
				scalar("SELECT COUNT(*) FROM " + counter) == "0",
			"drained work cannot restore deleted rows");
	}
	else
	{
		require(resumes == 1, "failed preparation resumes admission exactly once");
		require(error_callback == error_case &&
				player_save_worker_health_copy().failures == (error_case ? 1U : 0U),
			"SQL failure rolled back and reported through real callback/worker health");
		require(player_save_worker_submit(snapshot(2, 43)) ==
					player_save_submit_result::accepted &&
				sql_queue(
					"UPDATE critical_test_state SET value=value+4 WHERE entity_type=1 AND entity_id=1001"),
			"normal persistence accepts work after refusal");
		drain_callbacks();
		require_saved("2", "43", "7");
	}
	player_save_worker_shutdown();
	sql_pool_shutdown();
	mysql_close(DB);
	DB = nullptr;
	mysql_library_end();
	std::cout << "PASS real pwipe writer/SQL " << scenario << '\n';
}
