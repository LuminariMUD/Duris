#ifndef SQL_ASYNC_H
#define SQL_ASYNC_H

#include "core/structs.h"
#include "persistence/persistence_observability.h"
#include "sql/sql_work.h"

#include <functional>
#include <string>
#include <vector>

/*
 * Game-thread SQL that never waits. A write is built on the game thread and queued on
 * the persistence writer as an `sql` job, in capture order with the saves around it.
 * Each job runs in one transaction. A read is queued the same way, so it sees every
 * write queued before it; its rows come back to the game thread on a later pulse
 * (sql_async_pulse()). Without a database (the flat-file backend) nothing is queued
 * and the calls return false.
 */

// The query, formatted on the game thread.
std::string sql_format(const char *format, ...) __attribute__((format(printf, 1, 2)));

bool sql_queue_at(struct persistence_query_site site, const char *format, ...)
	__attribute__((format(printf, 2, 3)));
// Statements applied in order, in one transaction.
bool sql_queue_statements_at(struct persistence_query_site site,
			     std::vector<std::string> statements);
// Writes that need the database's answer first (a lookup, then an update or an insert).
bool sql_queue_work_at(struct persistence_query_site site, sql_work work);
// done(ok, rows) runs on the game thread; ok is false when the read failed.
bool sql_read_at(struct persistence_query_site site, std::string query,
		 std::function<void(bool ok, const sql_rows &rows)> done);
// For a character: done runs only while ch is still in the game. A failed read tells
// the character and does not call done.
bool sql_read_for_at(struct persistence_query_site site, P_char ch, std::string query,
		     std::function<void(P_char ch, const sql_rows &rows)> done);
// Runs the callbacks of the reads the writer finished. Returns how many ran.
size_t sql_async_pulse(void);

#define sql_queue(...) sql_queue_at(PERSISTENCE_QUERY_SITE, __VA_ARGS__)
#define sql_queue_statements(...) sql_queue_statements_at(PERSISTENCE_QUERY_SITE, __VA_ARGS__)
#define sql_queue_work(...) sql_queue_work_at(PERSISTENCE_QUERY_SITE, __VA_ARGS__)
#define sql_read(...) sql_read_at(PERSISTENCE_QUERY_SITE, __VA_ARGS__)
#define sql_read_for(...) sql_read_for_at(PERSISTENCE_QUERY_SITE, __VA_ARGS__)

#endif
