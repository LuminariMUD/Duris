// The zone-story state is one shared row that grows as quests are completed. Its save
// went through qry(), which formats into a 64 KiB buffer and refuses anything longer, so
// once the state passed 64 KiB no completion was recorded. The save is now queued on the
// writer (sql_queue()), formatted at its real length. This stores a state above 64 KiB
// through sql_zone_story_quest_state_save() on a real server and reads it back with the
// boot load.
#include "player/player_save_worker.h"
#include "player/player_snapshot_repository.h"
#include "sql/sql.h"
#include "sql/sql_async.h"
#include "sql/sql_pool.h"
#include "sql/zone_story_quest_state_repository.h"

#include <cstdarg>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <mysql/mysql.h>
#include <string>

MYSQL *DB = nullptr;
P_char character_list = nullptr;

namespace
{
void require(bool condition, const std::string &message)
{
	if (!condition)
	{
		std::cerr << "FAILED: " << message << '\n';
		exit(1);
	}
}

std::string environment(const char *name, const char *fallback)
{
	const char *value = getenv(name);
	return value && *value ? value : fallback;
}
} // namespace

void logit(const char *, const char *, ...) {}
void send_to_char(const char *, P_char) {}

// The writer runs each job at once, on the harness's connection.
player_save_submit_result persistence_writer_submit(persistence_job_kind, uint64_t, size_t,
						    persistence_job_write_fn write)
{
	const player_save_apply_result applied = write();
	require(applied.outcome == player_save_apply_outcome::applied,
		"the writer's job failed: error " + std::to_string(applied.error_code) + ": " +
			mysql_error(DB));
	return player_save_submit_result::accepted;
}
MYSQL *sql_pool_acquire(void)
{
	return DB;
}
void sql_pool_release(MYSQL *) {}
MYSQL *sql_pool_replace_connection(MYSQL *)
{
	return nullptr;
}
// As sql_player.c and sql.c do them, on the harness's connection.
char *sql_escape_string(const char *text)
{
	const size_t length = strlen(text);
	char *escaped = static_cast<char *>(malloc(length * 2 + 1));
	mysql_real_escape_string(DB, escaped, text, length);
	return escaped;
}
MYSQL_RES *db_query_at(struct persistence_query_site, const char *format, ...)
{
	va_list args;
	va_start(args, format);
	const int needed = vsnprintf(nullptr, 0, format, args);
	va_end(args);
	std::string query(static_cast<size_t>(needed) + 1, '\0');
	va_start(args, format);
	vsnprintf(query.data(), query.size(), format, args);
	va_end(args);
	query.resize(static_cast<size_t>(needed));
	require(!mysql_real_query(DB, query.data(), query.size()),
		std::string("the load failed: ") + mysql_error(DB));
	return mysql_store_result(DB);
}

int main()
{
	require(!mysql_library_init(0, nullptr, nullptr), "could not initialize the MySQL client");
	DB = mysql_init(nullptr);
	require(DB != nullptr, "could not allocate a MySQL connection");
	const unsigned int port = static_cast<unsigned int>(
		std::strtoul(environment("DB_PORT", "3306").c_str(), nullptr, 10));
	require(mysql_real_connect(DB, environment("DB_HOST", "127.0.0.1").c_str(),
				   environment("DB_USER", "root").c_str(),
				   environment("DB_PASSWD", "").c_str(),
				   environment("DB_NAME", "player_save_claim_test").c_str(), port,
				   nullptr, 0) != nullptr,
		std::string("could not connect: ") + mysql_error(DB));
	require(!mysql_query(DB, "SET SESSION sql_mode='STRICT_TRANS_TABLES,"
				 "ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION'"),
		mysql_error(DB));

	sql_async_boot_done();
	// 96 KiB, with quotes, backslashes and newlines that escaping lengthens.
	std::string state;
	while (state.size() < 96 * 1024)
		state += "pid=" + std::to_string(state.size()) + " quest='done'\\\n";
	std::string error;
	require(sql_zone_story_quest_state_save(7, state, &error) ==
			sql_zone_story_quest_state_result::ok,
		"the save was refused: " + error);
	std::string loaded;
	require(sql_zone_story_quest_state_load(7, &loaded, &error) ==
			sql_zone_story_quest_state_result::ok,
		"the load failed: " + error);
	require(loaded == state, "the state read back is " + std::to_string(loaded.size()) +
					 " bytes, not " + std::to_string(state.size()));
	std::cout << "zone-story state above 64 KiB stored and read back\n";
	return 0;
}
