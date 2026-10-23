/****************************************************************************
 *
 *  File: critical_outbox.c                                     Part of Duris
 *  Usage: the critical outbox worker: fetches and delivers results
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "persistence/critical_outbox.h"

#include "economy/collector_command.h"
#include "sql/sql_thread_init.h"

#include "sql/sql_pool.h"

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <cstring>
#include <future>
#include <mysql.h>
#include <mutex>
#include <new>
#include <string>
#include <system_error>
#include <thread>

namespace
{
constexpr uint16_t OUTBOX_DESTINATION_TEST = 1;
constexpr uint16_t OUTBOX_EVENT_TEST_MUTATED = 1;
constexpr uint16_t OUTBOX_DESTINATION_EPIC = 2;
constexpr uint16_t OUTBOX_EVENT_EPIC_BALANCE = 1;
std::mutex outbox_mutex;
std::condition_variable outbox_changed;
std::thread outbox_worker;
critical_outbox_deliver_fn deliver_callback = nullptr;
void *deliver_context = nullptr;
critical_outbox_progress_fn drain_progress = nullptr;
critical_outbox_health health = {};
bool stop_requested = false;
bool work_requested = false;
uint64_t drain_requested = 0;
uint64_t drain_completed = 0;
std::chrono::steady_clock::time_point counts_refreshed, audit_refreshed;

bool execute(MYSQL *connection, const std::string &sql)
{
	return mysql_real_query(connection, sql.data(), sql.size()) == 0;
}

bool is_connection_error(unsigned int error)
{
	return error == 2006 || error == 2013 || error == 2055;
}

void release_after_query(MYSQL *connection, bool succeeded)
{
	if (!connection)
		return;
	if (!succeeded && is_connection_error(mysql_errno(connection)))
	{
		MYSQL *replacement = sql_pool_replace_connection(connection);
		if (replacement)
			sql_pool_release(replacement);
		return;
	}
	sql_pool_release(connection);
}

bool parse_u64(const char *text, uint64_t *value)
{
	if (!text || !value)
		return false;
	char *end = nullptr;
	errno = 0;
	const unsigned long long parsed = strtoull(text, &end, 10);
	if (errno || !end || *end)
		return false;
	*value = parsed;
	return true;
}

bool delivery_is_recorded(MYSQL *connection, uint64_t outbox_id)
{
	const std::string sql =
		"SELECT status FROM critical_outbox WHERE outbox_id=" + std::to_string(outbox_id);
	if (!execute(connection, sql))
		return false;
	MYSQL_RES *result = mysql_store_result(connection);
	MYSQL_ROW row = result ? mysql_fetch_row(result) : nullptr;
	const bool delivered = row && row[0] && strcmp(row[0], "1") == 0;
	if (result)
		mysql_free_result(result);
	return delivered;
}

bool refresh_counts(MYSQL *connection)
{
	static const char SQL[] =
		"SELECT (SELECT COUNT(*) FROM critical_outbox WHERE status=0),"
		"(SELECT COUNT(*) FROM critical_outbox WHERE status=2),"
		"(SELECT COALESCE(TIMESTAMPDIFF(MICROSECOND,MIN(created_at),"
		"CURRENT_TIMESTAMP(6)) DIV 1000,0) FROM critical_outbox WHERE status=0),"
		"(SELECT COUNT(*) FROM critical_operation_inbox WHERE status<>1)";
	if (!execute(connection, SQL))
		return false;
	MYSQL_RES *result = mysql_store_result(connection);
	if (!result)
		return false;
	MYSQL_ROW row = mysql_fetch_row(result);
	uint64_t pending = 0, dead = 0, oldest = 0, incomplete = 0;
	const bool ok = row && parse_u64(row[0], &pending) && parse_u64(row[1], &dead) &&
			parse_u64(row[2], &oldest) && parse_u64(row[3], &incomplete);
	mysql_free_result(result);
	if (!ok)
		return false;
	std::lock_guard<std::mutex> lock(outbox_mutex);
	health.pending = pending;
	health.dead_letter = dead;
	health.oldest_age_msec = oldest;
	health.incomplete_inbox = incomplete;
	health.counts_available = true;
	health.counts_stale = false;
	counts_refreshed = std::chrono::steady_clock::now();
	return true;
}

bool refresh_audit(MYSQL *connection)
{
	static const char SQL[] =
		"SELECT COUNT(*) FROM critical_operation_inbox i WHERE status=1 AND result_code=0 "
		"AND NOT EXISTS (SELECT 1 FROM critical_outbox o WHERE o.operation_id=i.operation_id)";
	if (!execute(connection, SQL))
		return false;
	MYSQL_RES *result = mysql_store_result(connection);
	MYSQL_ROW row = result ? mysql_fetch_row(result) : nullptr;
	uint64_t missing = 0;
	const bool ok = row && parse_u64(row[0], &missing);
	if (result)
		mysql_free_result(result);
	if (!ok)
		return false;
	std::lock_guard<std::mutex> lock(outbox_mutex);
	health.committed_without_outbox = missing;
	health.audit_available = true;
	health.audit_stale = false;
	audit_refreshed = std::chrono::steady_clock::now();
	return true;
}

bool observe_drain(MYSQL *connection, uint64_t requested)
{
	if (!execute(connection, "SELECT EXISTS(SELECT 1 FROM critical_outbox WHERE status=0)"))
		return false;
	MYSQL_RES *result = mysql_store_result(connection);
	MYSQL_ROW row = result ? mysql_fetch_row(result) : nullptr;
	uint64_t pending = 0;
	const bool ok = row && parse_u64(row[0], &pending);
	if (result)
		mysql_free_result(result);
	if (ok && !pending)
	{
		std::lock_guard<std::mutex> lock(outbox_mutex);
		drain_completed = requested;
		outbox_changed.notify_all();
	}
	return ok;
}

bool fetch_batch(MYSQL *connection, std::vector<critical_outbox_record> *records)
{
	static const char SQL[] =
		"SELECT outbox_id,operation_id,destination,event_type,payload_version,attempt_count,payload "
		"FROM critical_outbox WHERE status=0 AND next_attempt_at<=CURRENT_TIMESTAMP(6) "
		"ORDER BY next_attempt_at,outbox_id LIMIT 64";
	if (!records || !execute(connection, SQL))
		return false;
	MYSQL_RES *result = mysql_store_result(connection);
	if (!result)
		return false;
	size_t bytes = 0;
	MYSQL_ROW row = nullptr;
	try
	{
		while ((row = mysql_fetch_row(result)) != nullptr)
		{
			unsigned long *lengths = mysql_fetch_lengths(result);
			uint64_t id = 0, destination = 0, event_type = 0, payload_version = 0,
				 attempt = 0;
			if (!lengths || !parse_u64(row[0], &id) || !row[1] ||
			    lengths[1] != CRITICAL_COMMAND_ID_BYTES ||
			    !parse_u64(row[2], &destination) || !parse_u64(row[3], &event_type) ||
			    !parse_u64(row[4], &payload_version) || !parse_u64(row[5], &attempt) ||
			    !row[6] || lengths[6] > CRITICAL_OUTBOX_RECORD_MAX_BYTES ||
			    lengths[6] > CRITICAL_OUTBOX_QUEUE_MAX_BYTES - bytes)
			{
				mysql_free_result(result);
				return false;
			}
			critical_outbox_record record = {
				.outbox_id = id,
				.operation_id = {},
				.destination = static_cast<uint16_t>(destination),
				.event_type = static_cast<uint16_t>(event_type),
				.payload_version = static_cast<uint16_t>(payload_version),
				.attempt = static_cast<unsigned int>(attempt),
				.payload = {}
			};
			memcpy(record.operation_id.bytes.data(), row[1], CRITICAL_COMMAND_ID_BYTES);
			record.payload.assign(reinterpret_cast<uint8_t *>(row[6]),
					      reinterpret_cast<uint8_t *>(row[6]) + lengths[6]);
			bytes += lengths[6];
			records->push_back(std::move(record));
		}
	}
	catch (const std::bad_alloc &)
	{
		mysql_free_result(result);
		return false;
	}
	mysql_free_result(result);
	std::lock_guard<std::mutex> lock(outbox_mutex);
	health.fetched += records->size();
	health.high_water_records = std::max<uint64_t>(health.high_water_records, records->size());
	health.high_water_bytes = std::max<uint64_t>(health.high_water_bytes, bytes);
	return true;
}

bool record_delivery(const critical_outbox_record &record,
		     critical_outbox_delivery_result delivered)
{
	MYSQL *connection = sql_pool_acquire();
	if (!connection)
		return false;
	bool ok = false;
	if (delivered == critical_outbox_delivery_result::delivered ||
	    delivered == critical_outbox_delivery_result::already_delivered)
	{
		const bool updated =
			execute(connection, "START TRANSACTION") &&
			execute(connection,
				"INSERT IGNORE INTO critical_outbox_delivery_dedupe(consumer_id,"
				"outbox_id) VALUES(" +
					std::to_string(record.destination) + "," +
					std::to_string(record.outbox_id) + ")") &&
			execute(connection,
				"UPDATE critical_outbox SET status=1,delivered_at=CURRENT_TIMESTAMP(6),"
				"last_error_code=0 WHERE status=0 AND outbox_id=" +
					std::to_string(record.outbox_id));
		if (updated && mysql_affected_rows(connection) == 1)
		{
			ok = execute(connection, "COMMIT");
			if (!ok && is_connection_error(mysql_errno(connection)))
			{
				connection = sql_pool_replace_connection(connection);
				ok = connection &&
				     delivery_is_recorded(connection, record.outbox_id);
			}
		}
		else if (updated)
		{
			execute(connection, "ROLLBACK");
			ok = delivery_is_recorded(connection, record.outbox_id);
		}
		if (!ok && connection && !is_connection_error(mysql_errno(connection)))
			execute(connection, "ROLLBACK");
	}
	else
	{
		const unsigned int next_attempt = record.attempt + 1;
		const bool dead = delivered == critical_outbox_delivery_result::terminal_failure ||
				  next_attempt >= CRITICAL_OUTBOX_MAX_ATTEMPTS;
		const unsigned int shift = std::min(next_attempt, 8U);
		const unsigned int delay = std::min(1U << shift, 300U);
		const std::string sql =
			dead ? "UPDATE critical_outbox SET status=2,attempt_count=" +
					std::to_string(next_attempt) +
					",dead_lettered_at=CURRENT_TIMESTAMP(6),last_error_code=1 "
					"WHERE status=0 AND outbox_id=" +
					std::to_string(record.outbox_id) :
			       "UPDATE critical_outbox SET attempt_count=" +
					std::to_string(next_attempt) +
					",next_attempt_at=TIMESTAMPADD(SECOND," +
					std::to_string(delay) +
					",CURRENT_TIMESTAMP(6)),last_error_code=1 WHERE status=0 AND outbox_id=" +
					std::to_string(record.outbox_id);
		ok = execute(connection, sql) && mysql_affected_rows(connection) == 1;
	}
	release_after_query(connection, ok);
	if (ok)
	{
		std::lock_guard<std::mutex> lock(outbox_mutex);
		if (delivered == critical_outbox_delivery_result::delivered)
			++health.delivered;
		else if (delivered == critical_outbox_delivery_result::already_delivered)
			++health.duplicates;
		else if (delivered == critical_outbox_delivery_result::retryable_failure &&
			 record.attempt + 1 < CRITICAL_OUTBOX_MAX_ATTEMPTS)
			++health.retries;
		else
			++health.terminal_failures;
	}
	return ok;
}

void worker_main(std::promise<bool> startup)
{
	if (sql_worker_thread_init() != 0)
	{
		startup.set_value(false);
		return;
	}
	startup.set_value(true);
	auto next_audit = std::chrono::steady_clock::now();
	for (;;)
	{
		{
			std::unique_lock<std::mutex> lock(outbox_mutex);
			outbox_changed.wait_for(lock, std::chrono::milliseconds(250),
						[] { return stop_requested || work_requested; });
			if (stop_requested)
				break;
			work_requested = false;
		}
		MYSQL *connection = sql_pool_acquire();
		if (!connection)
		{
			std::lock_guard<std::mutex> lock(outbox_mutex);
			++health.db_failures;
			health.counts_stale = true;
			continue;
		}
		std::vector<critical_outbox_record> records;
		const bool fetched = fetch_batch(connection, &records);
		release_after_query(connection, fetched);
		if (!fetched)
		{
			std::lock_guard<std::mutex> lock(outbox_mutex);
			++health.db_failures;
			records.clear();
		}
		for (const critical_outbox_record &record : records)
		{
			critical_outbox_delivery_result delivered = {};
			try
			{
				delivered = deliver_callback(record, deliver_context);
			}
			catch (...)
			{
				delivered = critical_outbox_delivery_result::retryable_failure;
			}
			if (!record_delivery(record, delivered))
			{
				std::lock_guard<std::mutex> lock(outbox_mutex);
				++health.db_failures;
			}
		}

		// Delivery and its transaction never depend on diagnostic success. A new
		// borrow retains the pool's ownership guard after callbacks have run.
		connection = sql_pool_acquire();
		uint64_t requested = 0;
		{
			std::lock_guard<std::mutex> lock(outbox_mutex);
			if (drain_requested != drain_completed)
				requested = drain_requested;
		}
		bool ok = connection != nullptr;
		if (requested && connection)
		{
			ok = observe_drain(connection, requested);
			if (!ok)
			{
				std::lock_guard<std::mutex> lock(outbox_mutex);
				++health.db_failures;
			}
		}
		// Never issue another query on a handle known to have lost its connection.
		if (connection && (ok || !is_connection_error(mysql_errno(connection))))
		{
			const bool counted = refresh_counts(connection);
			if (!counted)
			{
				std::lock_guard<std::mutex> lock(outbox_mutex);
				health.counts_stale = true;
				++health.db_failures;
			}
			ok = counted;
		}
		else
		{
			std::lock_guard<std::mutex> lock(outbox_mutex);
			health.counts_stale = true;
			if (!connection)
				++health.db_failures;
		}
		if (std::chrono::steady_clock::now() >= next_audit)
		{
			const bool audited =
				connection &&
				(ok || !is_connection_error(mysql_errno(connection))) &&
				refresh_audit(connection);
			next_audit = std::chrono::steady_clock::now() + std::chrono::seconds(60);
			if (!audited)
			{
				std::lock_guard<std::mutex> lock(outbox_mutex);
				health.audit_stale = true;
				++health.db_failures;
			}
			ok = audited;
		}
		release_after_query(connection, ok);
	}
	mysql_thread_end();
}
} // namespace

bool critical_outbox_init(critical_outbox_deliver_fn deliver, void *context,
			  critical_outbox_progress_fn progress)
{
	if (!deliver)
		return false;
	std::lock_guard<std::mutex> lock(outbox_mutex);
	if (health.initialized)
		return false;
	health = {};
	health.initialized = true;
	health.accepting = true;
	health.running = true;
	deliver_callback = deliver;
	deliver_context = context;
	drain_progress = progress;
	stop_requested = false;
	work_requested = false;
	drain_requested = drain_completed = 0;
	std::promise<bool> startup;
	std::future<bool> started = startup.get_future();
	try
	{
		outbox_worker = std::thread(worker_main, std::move(startup));
	}
	catch (const std::system_error &)
	{
		health = {};
		return false;
	}
	if (!started.get())
	{
		outbox_worker.join();
		health = {};
		deliver_callback = nullptr;
		deliver_context = nullptr;
		return false;
	}
	return true;
}

void critical_outbox_shutdown(void)
{
	{
		std::lock_guard<std::mutex> lock(outbox_mutex);
		stop_requested = true;
		health.accepting = false;
		outbox_changed.notify_all();
	}
	if (outbox_worker.joinable())
		outbox_worker.join();
	std::lock_guard<std::mutex> lock(outbox_mutex);
	health = {};
	deliver_callback = nullptr;
	deliver_context = nullptr;
	drain_progress = nullptr;
}

void critical_outbox_quiesce(void)
{
	std::lock_guard<std::mutex> lock(outbox_mutex);
	health.accepting = false;
}

void critical_outbox_resume(void)
{
	std::lock_guard<std::mutex> lock(outbox_mutex);
	if (health.initialized && !stop_requested)
	{
		health.accepting = true;
		work_requested = true;
	}
	outbox_changed.notify_all();
}

bool critical_outbox_drain(uint64_t timeout_msec)
{
#ifdef __NO_MYSQL__
	(void)timeout_msec;
	return true; // This backend intentionally has no SQL outbox worker.
#else
	const auto deadline =
		std::chrono::steady_clock::now() + std::chrono::milliseconds(timeout_msec);
	std::unique_lock<std::mutex> lock(outbox_mutex);
	if (!health.initialized || stop_requested)
		return false;
	const uint64_t requested = ++drain_requested;
	work_requested = true;
	outbox_changed.notify_all();
	for (;;)
	{
		if (!health.initialized || stop_requested)
			return false;
		if (drain_completed >= requested)
			return true;
		if (std::chrono::steady_clock::now() >= deadline)
			return false;
		const critical_outbox_progress_fn progress = drain_progress;
		lock.unlock();
		if (progress)
			progress();
		lock.lock();
		outbox_changed.wait_until(lock,
					  std::min(deadline, std::chrono::steady_clock::now() +
								     std::chrono::milliseconds(5)));
	}
#endif
}

critical_outbox_health critical_outbox_health_copy(void)
{
	std::lock_guard<std::mutex> lock(outbox_mutex);
	critical_outbox_health snapshot = health;
	const auto now = std::chrono::steady_clock::now();
	if (snapshot.counts_available)
		snapshot.counts_age_msec = std::chrono::duration_cast<std::chrono::milliseconds>(
						   now - counts_refreshed)
						   .count();
	if (snapshot.audit_available)
		snapshot.audit_age_msec =
			std::chrono::duration_cast<std::chrono::milliseconds>(now - audit_refreshed)
				.count();
	snapshot.counts_stale = !snapshot.counts_available || snapshot.counts_stale ||
				snapshot.counts_age_msec > 1000;
	snapshot.audit_stale = !snapshot.audit_available || snapshot.audit_stale ||
			       snapshot.audit_age_msec > 61000;
	return snapshot;
}

critical_outbox_delivery_result
critical_outbox_test_destination(const critical_outbox_record &record, void *context)
{
	(void)context;
	const bool test_record = record.destination == OUTBOX_DESTINATION_TEST &&
				 record.event_type == OUTBOX_EVENT_TEST_MUTATED &&
				 record.payload_version == 1 && record.payload.size() == 16;
	const bool epic_record = record.destination == OUTBOX_DESTINATION_EPIC &&
				 record.event_type == OUTBOX_EVENT_EPIC_BALANCE &&
				 record.payload_version == 1 && record.payload.size() == 24;
	const bool item_record = record.destination == 4 && record.event_type == 1 &&
				 record.payload_version == 1 && !record.payload.empty();
	const bool auction_record = record.destination == 5 && record.event_type == 1 &&
				    record.payload_version == 1 && !record.payload.empty();
	const bool collector_record = record.destination == COLLECTOR_OUTBOX_DESTINATION &&
				      record.event_type == COLLECTOR_OUTBOX_EVENT_MUTATED &&
				      record.payload_version == COLLECTOR_COMMAND_RESULT_VERSION &&
				      record.payload.size() == COLLECTOR_COMMAND_RESULT_BYTES;
	return test_record || epic_record || item_record || auction_record || collector_record ?
		       critical_outbox_delivery_result::delivered :
		       critical_outbox_delivery_result::terminal_failure;
}
