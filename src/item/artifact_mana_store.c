/****************************************************************************
 *
 *  File: artifact_mana_store.c                                 Part of Duris
 *  Usage: artifact mana storage: SQL reads and writes
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "item/artifact_mana_store.h"

#include "sql/sql_pool.h"
#include "sql/sql_thread_init.h"

#include <array>
#include <charconv>
#include <cstring>
#include <vector>

namespace
{
std::array<uint64_t, 8> fields(const artifact_mana_record &r)
{
	return { r.uid,	     r.profile_id,   r.profile_revision, r.version,
		 r.capacity, r.regeneration, r.reserve,		 r.settled_at };
}

artifact_mana_record from_fields(const std::array<uint64_t, 8> &f)
{
	return { f[0], f[1], f[2], f[3], f[4], f[5], f[6], f[7] };
}

struct mysql_thread_scope
{
	const bool ready = sql_worker_thread_init() == 0;
	~mysql_thread_scope()
	{
		if (ready)
			mysql_thread_end();
	}
};

constexpr const char *columns =
	"item_uid,profile_id,profile_revision,version,capacity,regeneration,reserve,settled_at";

artifact_mana_read read_sql(MYSQL *connection, uint64_t uid, artifact_mana_record &record)
{
	const auto query = std::string("SELECT ") + columns +
			   " FROM artifact_mana WHERE item_uid=" + std::to_string(uid);
	if (mysql_real_query(connection, query.data(), query.size()))
		return artifact_mana_read::error;
	MYSQL_RES *result = mysql_store_result(connection);
	if (!result)
		return artifact_mana_read::error;
	if (!mysql_num_rows(result))
	{
		mysql_free_result(result);
		return artifact_mana_read::missing;
	}
	MYSQL_ROW row = mysql_fetch_row(result);
	std::array<uint64_t, 8> values = {};
	bool valid = row && mysql_num_rows(result) == 1 &&
		     mysql_num_fields(result) == values.size();
	for (size_t i = 0; valid && i < values.size(); ++i)
	{
		if (!row[i])
		{
			valid = false;
			break;
		}
		const char *end = row[i] + strlen(row[i]);
		const auto parsed = std::from_chars(row[i], end, values[i]);
		valid = parsed.ec == std::errc() && parsed.ptr == end;
	}
	mysql_free_result(result);
	record = from_fields(values);
	return valid && artifact_mana_valid(record) && record.uid == uid ?
		       artifact_mana_read::found :
		       artifact_mana_read::error;
}

bool write_sql(MYSQL *connection, uint64_t expected, const artifact_mana_record &record)
{
	std::string query;
	if (!expected)
	{
		query = std::string("INSERT IGNORE INTO artifact_mana (") + columns + ") VALUES (";
		for (uint64_t value : fields(record))
			query += std::to_string(value) + ",";
		query.back() = ')';
	}
	else
	{
		query = "UPDATE artifact_mana SET profile_id=" + std::to_string(record.profile_id) +
			",profile_revision=" + std::to_string(record.profile_revision) +
			",version=" + std::to_string(record.version) +
			",capacity=" + std::to_string(record.capacity) +
			",regeneration=" + std::to_string(record.regeneration) +
			",reserve=" + std::to_string(record.reserve) +
			",settled_at=" + std::to_string(record.settled_at) +
			" WHERE item_uid=" + std::to_string(record.uid) +
			" AND version=" + std::to_string(expected);
	}
	if (mysql_real_query(connection, query.data(), query.size()))
		return false;
	artifact_mana_record stored;
	return read_sql(connection, record.uid, stored) == artifact_mana_read::found &&
	       stored == record;
}
} // namespace

artifact_mana_read artifact_mana_store_read(uint64_t uid, artifact_mana_record &record)
{
	if (!uid)
		return artifact_mana_read::error;
	mysql_thread_scope thread;
	if (!thread.ready)
		return artifact_mana_read::error;
	MYSQL *connection = sql_pool_acquire();
	if (!connection)
		return artifact_mana_read::error;
	const auto result = read_sql(connection, uid, record);
	sql_pool_release(connection);
	return result;
}

bool artifact_mana_store_write(uint64_t expected, const artifact_mana_record &record)
{
	if (!artifact_mana_valid(record) || record.version <= expected ||
	    (!expected && (record.version != 1 || record.reserve)))
		return false;
	mysql_thread_scope thread;
	if (!thread.ready)
		return false;
	MYSQL *connection = sql_pool_acquire();
	if (!connection)
		return false;
	const bool result = write_sql(connection, expected, record);
	sql_pool_release(connection);
	return result;
}
