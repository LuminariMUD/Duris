#include "sql/sql_async.h"

#include "core/prototypes.h"
#include "core/utils.h"
#include "player/player_save_worker.h"
#include "player/player_snapshot_repository.h"
#include "sql/sql.h"

#include <cerrno>
#include <cstdarg>
#include <cstdio>
#include <deque>
#include <mutex>
#include <new>
#include <utility>

extern P_char character_list;

namespace
{
struct finished_read
{
	std::function<void(bool, const sql_rows &)> done;
	bool ok;
	sql_rows rows;
};

// Until the writer has been started nothing can be queued on it: a job is applied at
// once on the game thread's connection, as the rest of boot queries it.
bool booting = true;
// Game thread only: each job is its own owner, so none replaces another.
uint64_t sequence = 0;
std::mutex finished_mutex;
std::deque<finished_read> finished;

std::string vformat(const char *format, va_list args)
{
	va_list measure;
	va_copy(measure, args);
	const int size = vsnprintf(nullptr, 0, format, measure);
	va_end(measure);
	if (size < 0)
		return {};
	std::string text(static_cast<size_t>(size) + 1, '\0');
	vsnprintf(text.data(), text.size(), format, args);
	text.resize(static_cast<size_t>(size));
	return text;
}

bool submit(struct persistence_query_site site, size_t bytes, persistence_job_write_fn write)
{
	const player_save_submit_result submitted = persistence_writer_submit(
		persistence_job_kind::sql, ++sequence, bytes, std::move(write));
	if (submitted == player_save_submit_result::accepted ||
	    submitted == player_save_submit_result::replaced)
		return true;
	logit(LOG_FILE, "sql job not queued: %s:%d %s", site.file, site.line, site.function);
	return false;
}

bool apply_at_boot(struct persistence_query_site site, const sql_work &work)
{
	const player_save_apply_result applied = sql_work_repository_apply(DB, work);
	if (applied.outcome == player_save_apply_outcome::applied)
		return true;
	logit(LOG_FILE, "sql job failed at boot: %s:%d %s error=%u", site.file, site.line,
	      site.function, applied.error_code);
	return false;
}

bool queue(struct persistence_query_site site, size_t bytes, sql_work work)
{
	if (!DB)
		return false;
	if (booting)
		return apply_at_boot(site, work);
	return submit(site, bytes, [work = std::move(work)]()
		      { return sql_work_repository_apply_from_pool(work); });
}

P_char live_character(P_char expected, uint64_t runtime_id)
{
	for (P_char character = character_list; character; character = character->next)
		if (character == expected && character->runtime_id == runtime_id)
			return character;
	return nullptr;
}
} // namespace

std::string sql_format(const char *format, ...)
{
	va_list args;
	va_start(args, format);
	std::string text = vformat(format, args);
	va_end(args);
	return text;
}

bool sql_queue_at(struct persistence_query_site site, const char *format, ...)
{
	va_list args;
	va_start(args, format);
	std::string statement = vformat(format, args);
	va_end(args);
	if (statement.empty())
		return false;
	std::vector<std::string> statements;
	statements.push_back(std::move(statement));
	return sql_queue_statements_at(site, std::move(statements));
}

bool sql_queue_statements_at(struct persistence_query_site site,
			     std::vector<std::string> statements)
{
	if (statements.empty())
		return false;
	size_t bytes = sizeof(statements);
	for (const std::string &statement : statements)
		bytes += statement.size();
	return queue(site, bytes,
		     [statements = std::move(statements)](MYSQL *connection) -> unsigned int
		     {
			     for (const std::string &statement : statements)
				     if (const unsigned int error_code =
						 sql_execute(connection, statement))
					     return error_code;
			     return 0;
		     });
}

bool sql_queue_work_at(struct persistence_query_site site, sql_work work)
{
	return work && queue(site, sizeof(work), std::move(work));
}

bool sql_read_work_at(struct persistence_query_site site, sql_read_work_fn work,
		      std::function<void(bool ok, const sql_rows &rows)> done)
{
	if (!work || !done || !DB)
		return false;
	if (booting)
	{
		sql_rows rows;
		const bool ok = apply_at_boot(site, [&](MYSQL *connection)
					      { return work(connection, &rows); });
		std::lock_guard<std::mutex> lock(finished_mutex);
		finished.push_back({ std::move(done), ok, std::move(rows) });
		return true;
	}
	return submit(
		site, sizeof(work),
		[work = std::move(work), done = std::move(done)]()
		{
			sql_rows rows;
			const player_save_apply_result result = sql_work_repository_apply_from_pool(
				[&](MYSQL *connection)
				{
					rows.clear();
					return work(connection, &rows);
				});
			// A lost connection is retried; any other outcome is final.
			if (result.outcome == player_save_apply_outcome::retryable_failure)
				return result;
			try
			{
				std::lock_guard<std::mutex> lock(finished_mutex);
				finished.push_back(
					{ done,
					  result.outcome == player_save_apply_outcome::applied,
					  std::move(rows) });
			}
			catch (const std::bad_alloc &)
			{
				return player_save_apply_result{
					player_save_apply_outcome::terminal_failure, 0, ENOMEM
				};
			}
			return result;
		});
}

bool sql_read_at(struct persistence_query_site site, std::string query,
		 std::function<void(bool ok, const sql_rows &rows)> done)
{
	return !query.empty() &&
	       sql_read_work_at(
		       site, [query = std::move(query)](MYSQL *connection, sql_rows *rows)
		       { return sql_select(connection, query, rows); }, std::move(done));
}

bool sql_read_work_for_at(struct persistence_query_site site, P_char ch, sql_read_work_fn work,
			  std::function<void(P_char ch, const sql_rows &rows)> done)
{
	if (!ch || !done)
		return false;
	const uint64_t runtime_id = ch->runtime_id;
	return sql_read_work_at(
		site, std::move(work),
		[ch, runtime_id, done = std::move(done)](bool ok, const sql_rows &rows)
		{
			P_char live = live_character(ch, runtime_id);
			if (!live)
				return;
			if (ok)
				done(live, rows);
			else
				send_to_char("That is not available right now.\r\n", live);
		});
}

bool sql_read_for_at(struct persistence_query_site site, P_char ch, std::string query,
		     std::function<void(P_char ch, const sql_rows &rows)> done)
{
	return !query.empty() &&
	       sql_read_work_for_at(
		       site, ch, [query = std::move(query)](MYSQL *connection, sql_rows *rows)
		       { return sql_select(connection, query, rows); }, std::move(done));
}

void sql_async_boot_done(void)
{
	booting = false;
}

size_t sql_async_pulse(void)
{
	std::deque<finished_read> ready;
	{
		std::lock_guard<std::mutex> lock(finished_mutex);
		ready.swap(finished);
	}
	for (finished_read &read : ready)
		read.done(read.ok, read.rows);
	return ready.size();
}
