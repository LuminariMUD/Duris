/****************************************************************************
 *
 *  File: maintenance_repository.c                              Part of Duris
 *  Usage: SQL maintenance jobs: epic balances, level caps, and timers
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "persistence/maintenance_repository.h"

#include "combat/frag_cap_config.h"
#include "core/defines.h"
#include "persistence/persistence_observability.h"
#include "sql/sql_pool.h"
#ifdef __NO_MYSQL__
#include "ships/ships.h"
#endif

#include <mysql/mysql.h>
#include <mysql/mysqld_error.h>

#include <algorithm>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <ctime>
#include <cstdlib>
#include <fcntl.h>
#include <filesystem>
#include <fstream>
#include <map>
#include <set>
#include <string>
#include <unistd.h>
#include <vector>

namespace
{
struct connection_guard
{
	MYSQL *connection;
	~connection_guard()
	{
		if (connection)
			sql_pool_release(connection);
	}
};

maintenance_result failure(const maintenance_request &request, maintenance_outcome outcome,
			   uint32_t code)
{
	return { request.work_id, request.job_id, outcome, request.cursor, 0, 0, code, 0, {} };
}

bool before_deadline(const maintenance_request &request)
{
	return persistence_observability_now_usec() <= request.deadline_usec;
}

bool parse_positive(const char *text, int64_t *value)
{
	if (!text || !*text || !value)
		return false;
	errno = 0;
	char *end = nullptr;
	const unsigned long long parsed = strtoull(text, &end, 10);
	if (errno || !end || *end || !parsed || parsed > INT64_MAX)
		return false;
	*value = static_cast<int64_t>(parsed);
	return true;
}

bool query_values(MYSQL *connection, const maintenance_request &request, const std::string &sql,
		  maintenance_result *result)
{
	if (!connection || !result || !before_deadline(request) ||
	    mysql_real_query(connection, sql.data(), sql.size()) != 0)
		return false;
	MYSQL_RES *rows = mysql_store_result(connection);
	if (!rows)
		return false;
	MYSQL_ROW row = nullptr;
	while ((row = mysql_fetch_row(rows)))
	{
		int64_t value = 0;
		if (result->value_count >= request.row_budget ||
		    result->value_count >= result->values.size() || !parse_positive(row[0], &value))
		{
			mysql_free_result(rows);
			return false;
		}
		result->values[result->value_count++] = value;
	}
	mysql_free_result(rows);
	result->rows = static_cast<uint32_t>(result->value_count);
	if (result->value_count)
		result->next_cursor =
			static_cast<uint64_t>(result->values[result->value_count - 1]);
	result->outcome = result->value_count == request.row_budget ? maintenance_outcome::more :
								      maintenance_outcome::complete;
	return before_deadline(request);
}

std::string limit_sql(const maintenance_request &request)
{
	return std::to_string(request.row_budget);
}

bool execute_sql(MYSQL *connection, const std::string &sql)
{
	return connection && mysql_real_query(connection, sql.data(), sql.size()) == 0;
}

bool begin_transaction(MYSQL *connection)
{
	return execute_sql(connection, "START TRANSACTION");
}

maintenance_result sql_failure(MYSQL *connection, const maintenance_request &request)
{
	execute_sql(connection, "ROLLBACK");
	return failure(request, maintenance_outcome::retryable_failure,
		       mysql_errno(connection) ? mysql_errno(connection) : EIO);
}

bool timer_value(MYSQL *connection, const std::string &name, int64_t *value)
{
	if (!value || !execute_sql(connection, "SELECT date FROM timers WHERE name='" + name + "'"))
		return false;
	MYSQL_RES *rows = mysql_store_result(connection);
	if (!rows)
		return false;
	MYSQL_ROW row = mysql_fetch_row(rows);
	*value = row && row[0] ? strtoll(row[0], nullptr, 10) : 0;
	mysql_free_result(rows);
	return true;
}

bool marker_matches_and_lock(MYSQL *connection, const char *prefix, uint64_t work_id,
			     uint64_t cursor, bool *matches)
{
	if (!matches)
		return false;
	const std::string base(prefix);
	const std::string names[4] = { base + "_wh", base + "_wl", base + "_ch", base + "_cl" };
	std::string insert = "INSERT IGNORE INTO timers(name,date) VALUES";
	for (size_t index = 0; index < 4; ++index)
	{
		if (index)
			insert += ',';
		insert += "('" + names[index] + "',0)";
	}
	if (!execute_sql(connection, insert))
		return false;
	std::string select = "SELECT name,date FROM timers WHERE name IN ('" + names[0] + "','" +
			     names[1] + "','" + names[2] + "','" + names[3] + "') FOR UPDATE";
	if (!execute_sql(connection, select))
		return false;
	MYSQL_RES *rows = mysql_store_result(connection);
	if (!rows)
		return false;
	int32_t observed[4] = {};
	bool found[4] = {};
	MYSQL_ROW row = nullptr;
	while ((row = mysql_fetch_row(rows)))
		for (size_t index = 0; index < 4; ++index)
			if (row[0] && row[1] && names[index] == row[0])
			{
				observed[index] = static_cast<int32_t>(strtol(row[1], nullptr, 10));
				found[index] = true;
			}
	mysql_free_result(rows);
	const int32_t expected[4] = { static_cast<int32_t>(work_id >> 32),
				      static_cast<int32_t>(work_id),
				      static_cast<int32_t>(cursor >> 32),
				      static_cast<int32_t>(cursor) };
	*matches = true;
	for (size_t index = 0; index < 4; ++index)
		*matches = *matches && found[index] && observed[index] == expected[index];
	if (*matches)
		return true;
	std::string update = "UPDATE timers SET date=CASE name";
	for (size_t index = 0; index < 4; ++index)
		update += " WHEN '" + names[index] + "' THEN " + std::to_string(expected[index]);
	update += " END WHERE name IN ('" + names[0] + "','" + names[1] + "','" + names[2] + "','" +
		  names[3] + "')";
	return execute_sql(connection, update);
}

maintenance_result execute_epic_balance(MYSQL *connection, const maintenance_request &request)
{
	if (request.value_count != 2 || request.values[0] <= 0 || request.values[1] < 0)
		return failure(request, maintenance_outcome::permanent_failure, EINVAL);
	const std::string query =
		"SELECT id,alignment,COALESCE(UNIX_TIMESTAMP(last_touch),0) FROM zones "
		"WHERE epic_type>0 AND id>" +
		std::to_string(request.cursor) + " ORDER BY id LIMIT " + limit_sql(request);
	if (!begin_transaction(connection) || !execute_sql(connection, query))
		return sql_failure(connection, request);
	MYSQL_RES *rows = mysql_store_result(connection);
	if (!rows)
		return sql_failure(connection, request);
	maintenance_result result = failure(request, maintenance_outcome::complete, 0);
	MYSQL_ROW row = nullptr;
	while ((row = mysql_fetch_row(rows)))
	{
		if (!row[0] || !row[1] || !row[2] || result.rows >= request.row_budget)
		{
			mysql_free_result(rows);
			return sql_failure(connection, request);
		}
		const uint64_t id = strtoull(row[0], nullptr, 10);
		const int alignment = atoi(row[1]);
		const int64_t touched = strtoll(row[2], nullptr, 10);
		if (!id)
		{
			mysql_free_result(rows);
			return sql_failure(connection, request);
		}
		result.next_cursor = id;
		++result.rows;
		std::string update;
		if (!touched)
			update = "UPDATE zones SET last_touch=FROM_UNIXTIME(" +
				 std::to_string(request.values[0]) +
				 ") WHERE id=" + std::to_string(id) + " AND last_touch IS NULL";
		else if (alignment && request.values[0] - touched > request.values[1])
			update = "UPDATE zones SET alignment=alignment" +
				 std::string(alignment > 0 ? "-1" : "+1") +
				 ",last_touch=FROM_UNIXTIME(" + std::to_string(request.values[0]) +
				 ") WHERE id=" + std::to_string(id) +
				 " AND alignment=" + std::to_string(alignment) +
				 " AND UNIX_TIMESTAMP(last_touch)=" + std::to_string(touched);
		if (!before_deadline(request) ||
		    (!update.empty() && !execute_sql(connection, update)))
		{
			mysql_free_result(rows);
			return sql_failure(connection, request);
		}
	}
	mysql_free_result(rows);
	if (!before_deadline(request) || !execute_sql(connection, "COMMIT"))
		return sql_failure(connection, request);
	result.outcome = result.rows == request.row_budget ? maintenance_outcome::more :
							     maintenance_outcome::complete;
	return result;
}

maintenance_result execute_epic_modifiers(MYSQL *connection, const maintenance_request &request)
{
	if (request.value_count != 5 || request.values[0] <= 0 || request.values[1] < 0 ||
	    request.values[3] < request.values[4])
		return failure(request, maintenance_outcome::permanent_failure, EINVAL);
	if (!begin_transaction(connection))
		return sql_failure(connection, request);
	if (!request.cursor)
	{
		int64_t last_run = 0;
		if (!timer_value(connection, "epic_zone_mod", &last_run))
			return sql_failure(connection, request);
		if (request.values[0] <= last_run + request.values[1])
		{
			if (!execute_sql(connection, "COMMIT"))
				return sql_failure(connection, request);
			return failure(request, maintenance_outcome::complete, 0);
		}
	}
	const std::string selection = "SELECT id FROM zones WHERE epic_type>0 AND id>" +
				      std::to_string(request.cursor) + " ORDER BY id LIMIT " +
				      limit_sql(request);
	if (!execute_sql(connection, selection))
		return sql_failure(connection, request);
	MYSQL_RES *rows = mysql_store_result(connection);
	if (!rows)
		return sql_failure(connection, request);
	std::string ids;
	uint32_t count = 0;
	uint64_t next_cursor = request.cursor;
	MYSQL_ROW row = nullptr;
	while ((row = mysql_fetch_row(rows)))
	{
		int64_t id = 0;
		if (!parse_positive(row[0], &id) || count >= request.row_budget)
		{
			mysql_free_result(rows);
			return sql_failure(connection, request);
		}
		if (count)
			ids += ',';
		ids += std::to_string(id);
		next_cursor = static_cast<uint64_t>(id);
		++count;
	}
	mysql_free_result(rows);
	bool applied = false;
	if (!marker_matches_and_lock(connection, "maintenance_epic_mod", request.work_id,
				     request.cursor, &applied))
		return sql_failure(connection, request);
	if (!before_deadline(request))
		return sql_failure(connection, request);
	if (count && !applied)
	{
		const double add = request.values[2] / 1000000.0;
		const double maximum = request.values[3] / 1000000.0;
		const double minimum = request.values[4] / 1000000.0;
		const std::string update = "UPDATE zones SET frequency_mod=LEAST(" +
					   std::to_string(maximum) + ",GREATEST(" +
					   std::to_string(minimum) + ",frequency_mod+" +
					   std::to_string(add) + ")) WHERE id IN (" + ids + ')';
		if (!execute_sql(connection, update))
			return sql_failure(connection, request);
	}
	if (count < request.row_budget &&
	    !execute_sql(connection, "REPLACE INTO timers(name,date) VALUES('epic_zone_mod'," +
					     std::to_string(request.values[0]) + ')'))
		return sql_failure(connection, request);
	if (!before_deadline(request) || !execute_sql(connection, "COMMIT"))
		return sql_failure(connection, request);
	maintenance_result result = failure(request,
					    count == request.row_budget ?
						    maintenance_outcome::more :
						    maintenance_outcome::complete,
					    0);
	result.next_cursor = next_cursor;
	result.rows = count;
	return result;
}

// Runs a query and stores its first row in values, left empty when it returns none.
bool query_first_row(MYSQL *connection, const std::string &sql, std::vector<std::string> *values)
{
	if (!execute_sql(connection, sql))
		return false;
	MYSQL_RES *rows = mysql_store_result(connection);
	if (!rows)
		return false;
	values->clear();
	if (MYSQL_ROW row = mysql_fetch_row(rows))
		for (unsigned int index = 0; index < mysql_num_fields(rows); ++index)
			values->push_back(row[index] ? row[index] : "");
	mysql_free_result(rows);
	return true;
}

// Once next_update has passed, the first frag since then by the side with more total frags
// (by either side while the totals are level), of a victim at most unlock_victim_levels_below
// the level open to all, unlocks one more level for that side if the kill's base frag share
// meets the current unlock_minimum_share_points, using the recorded ally count so a
// large group cannot unlock by ganging up on one victim. A level
// that opens a spell circle (see get_max_circle()) or reaches the maximum opens to every
// side instead. The next unlock waits unlock_timer_days from this one.
maintenance_result execute_level_cap(MYSQL *connection, const maintenance_request &request)
{
	if (request.value_count != 1 || request.values[0] <= 0)
		return failure(request, maintenance_outcome::permanent_failure, EINVAL);
	if (!begin_transaction(connection))
		return sql_failure(connection, request);
	bool already_applied = false;
	if (!marker_matches_and_lock(connection, "maintenance_level_cap", request.work_id, 0,
				     &already_applied))
		return sql_failure(connection, request);
	if (already_applied)
	{
		if (!execute_sql(connection, "COMMIT"))
			return sql_failure(connection, request);
		return failure(request, maintenance_outcome::complete, 0);
	}
	std::vector<std::string> row;
	if (!before_deadline(request) ||
	    !query_first_row(connection,
			     "SELECT id,level,level_good,level_evil,UNIX_TIMESTAMP(next_update) "
			     "FROM level_cap ORDER BY id LIMIT 1 FOR UPDATE",
			     &row))
		return sql_failure(connection, request);
	const auto *config = frag_cap_config_get();
	if (row.empty() || atoi(row[1].c_str()) >= config->cap_maximum_level ||
	    request.values[0] < strtoll(row[4].c_str(), nullptr, 10))
	{
		if (!execute_sql(connection, "COMMIT"))
			return sql_failure(connection, request);
		return failure(request, maintenance_outcome::complete, 0);
	}
	const std::string id = row[0];
	const int open_level = atoi(row[1].c_str());
	int good_level = atoi(row[2].c_str());
	int evil_level = atoi(row[3].c_str());
	const int64_t next_update = strtoll(row[4].c_str(), nullptr, 10);

	const std::string good = std::to_string(RACEWAR_GOOD), evil = std::to_string(RACEWAR_EVIL);
	const std::string side_frags =
		"SELECT COALESCE(SUM(total_frags),0) FROM frag_leaderboard WHERE racewar=";
	if (!query_first_row(connection,
			     "SELECT (" + side_frags + good + "),(" + side_frags + evil + ")",
			     &row) ||
	    row.empty())
		return sql_failure(connection, request);
	const int64_t good_frags = strtoll(row[0].c_str(), nullptr, 10);
	const int64_t evil_frags = strtoll(row[1].c_str(), nullptr, 10);
	const std::string leaders = good_frags > evil_frags ? good :
				    evil_frags > good_frags ? evil :
							      good + "," + evil;
	if (!before_deadline(request) ||
	    !query_first_row(
		    connection,
		    "SELECT f.racewar,UNIX_TIMESTAMP(o.created_at) FROM combat_outcome o "
		    "JOIN pkill_info v ON v.event_id=o.pkill_event_id AND v.pid=o.victim_pid "
		    "JOIN combat_outcome_participant p ON p.operation_id=o.operation_id "
		    "AND p.frag_delta>0 JOIN frag_leaderboard f ON f.pid=p.pid "
		    "WHERE o.killer_allies>0 AND o.killer_allies<=" +
			    std::to_string(100 / config->unlock_minimum_share_points) +
			    " AND o.created_at>=FROM_UNIXTIME(" + std::to_string(next_update) +
			    ") AND v.level>=" +
			    std::to_string(open_level - config->unlock_victim_levels_below) +
			    " AND f.racewar IN (" + leaders +
			    ") ORDER BY o.created_at,o.operation_id LIMIT 1",
		    &row))
		return sql_failure(connection, request);
	if (row.empty())
	{
		if (!execute_sql(connection, "COMMIT"))
			return sql_failure(connection, request);
		return failure(request, maintenance_outcome::complete, 0);
	}
	const int side = atoi(row[0].c_str());
	const int64_t frag_time = strtoll(row[1].c_str(), nullptr, 10);
	int &side_level = side == RACEWAR_GOOD ? good_level : evil_level;
	const int level = std::min(std::max(open_level, side_level) + 1, config->cap_maximum_level);
	const bool for_all = level == config->cap_maximum_level || (level - 1) % 5 == 0;
	if (!for_all)
		side_level = level;
	// From the unlock, not an older frag, so frags recorded before the job ran cannot chain
	// unlocks; and at least a second on, so that with no timer the frag cannot unlock again.
	const int64_t next_unlock = std::max(frag_time, request.values[0]) +
				    std::max<int64_t>(1, 86400LL * config->unlock_timer_days);
	if (!execute_sql(connection, "UPDATE level_cap SET level=" +
					     std::to_string(for_all ? level : open_level) +
					     ",level_good=" + std::to_string(good_level) +
					     ",level_evil=" + std::to_string(evil_level) +
					     ",next_update=FROM_UNIXTIME(" +
					     std::to_string(next_unlock) + ") WHERE id=" + id))
		return sql_failure(connection, request);
	const bool level_cap_changed = mysql_affected_rows(connection) == 1;
	if (!before_deadline(request) || !execute_sql(connection, "COMMIT"))
		return sql_failure(connection, request);
	maintenance_result result = failure(request, maintenance_outcome::complete, 0);
	if (level_cap_changed)
	{
		result.rows = 1;
		result.value_count = 3;
		result.values[0] = side;
		result.values[1] = level;
		result.values[2] = for_all;
	}
	return result;
}

struct boon_scan_row
{
	int64_t id;
	int64_t created_at;
	int64_t duration;
	int racewar;
	int option;
	int criteria;
	int pid;
};

maintenance_result execute_boon_scan(MYSQL *connection, const maintenance_request &request)
{
	if (request.value_count < 3 || request.values[0] <= 0 || request.values[1] < 0)
		return failure(request, maintenance_outcome::permanent_failure, EINVAL);
	const size_t epic_records = static_cast<size_t>(request.values[1]);
	const size_t ctf_count_index = 2 + epic_records * 2;
	if (ctf_count_index >= request.value_count || request.values[ctf_count_index] < 0)
		return failure(request, maintenance_outcome::permanent_failure, EINVAL);
	const size_t ctf_records = static_cast<size_t>(request.values[ctf_count_index]);
	if (ctf_count_index + 1 + ctf_records * 3 != request.value_count)
		return failure(request, maintenance_outcome::permanent_failure, EINVAL);
	std::map<int, int> epic_completions;
	for (size_t index = 0; index < epic_records; ++index)
	{
		const int zone = static_cast<int>(request.values[2 + index * 2]);
		if (zone > 0)
			++epic_completions[zone];
	}
	struct ctf_state
	{
		int type;
		int room;
	};
	std::map<int, ctf_state> ctf_states;
	for (size_t index = 0; index < ctf_records; ++index)
	{
		const size_t offset = ctf_count_index + 1 + index * 3;
		ctf_states[static_cast<int>(request.values[offset])] = {
			static_cast<int>(request.values[offset + 1]),
			static_cast<int>(request.values[offset + 2])
		};
	}
	if (!begin_transaction(connection))
		return sql_failure(connection, request);
	const std::string selection =
		"SELECT id,time,duration,racewar,opt,criteria,pid FROM boons WHERE active=1 AND id>" +
		std::to_string(request.cursor) + " ORDER BY id LIMIT " + limit_sql(request);
	if (!execute_sql(connection, selection))
		return sql_failure(connection, request);
	MYSQL_RES *rows = mysql_store_result(connection);
	if (!rows)
		return sql_failure(connection, request);
	std::vector<boon_scan_row> boons;
	std::set<int> zone_ids;
	std::set<int> nexus_ids;
	MYSQL_ROW row = nullptr;
	while ((row = mysql_fetch_row(rows)))
	{
		if (boons.size() >= request.row_budget)
		{
			mysql_free_result(rows);
			return sql_failure(connection, request);
		}
		bool valid = true;
		for (size_t column = 0; column < 7; ++column)
			valid = valid && row[column];
		if (!valid)
		{
			mysql_free_result(rows);
			return sql_failure(connection, request);
		}
		boon_scan_row boon = { strtoll(row[0], nullptr, 10),
				       strtoll(row[1], nullptr, 10),
				       strtoll(row[2], nullptr, 10),
				       atoi(row[3]),
				       atoi(row[4]),
				       static_cast<int>(strtod(row[5], nullptr)),
				       atoi(row[6]) };
		if (boon.id <= 0)
		{
			mysql_free_result(rows);
			return sql_failure(connection, request);
		}
		if (boon.option == 1)
			zone_ids.insert(boon.criteria);
		else if (boon.option == 9)
			nexus_ids.insert(boon.criteria);
		boons.push_back(boon);
	}
	mysql_free_result(rows);
	std::map<int, int> zone_stones;
	if (!zone_ids.empty())
	{
		std::string query = "SELECT number,stonecount FROM zones WHERE number IN (";
		for (auto iterator = zone_ids.begin(); iterator != zone_ids.end(); ++iterator)
		{
			if (iterator != zone_ids.begin())
				query += ',';
			query += std::to_string(*iterator);
		}
		query += ')';
		if (!execute_sql(connection, query))
			return sql_failure(connection, request);
		rows = mysql_store_result(connection);
		if (!rows)
			return sql_failure(connection, request);
		while ((row = mysql_fetch_row(rows)))
			if (row[0] && row[1])
				zone_stones[atoi(row[0])] = atoi(row[1]);
		mysql_free_result(rows);
	}
	std::map<int, int> nexus_alignments;
	if (!nexus_ids.empty())
	{
		std::string query = "SELECT id,align FROM nexus_stones WHERE id IN (";
		for (auto iterator = nexus_ids.begin(); iterator != nexus_ids.end(); ++iterator)
		{
			if (iterator != nexus_ids.begin())
				query += ',';
			query += std::to_string(*iterator);
		}
		query += ')';
		if (!execute_sql(connection, query))
			return sql_failure(connection, request);
		rows = mysql_store_result(connection);
		if (!rows)
			return sql_failure(connection, request);
		while ((row = mysql_fetch_row(rows)))
			if (row[0] && row[1])
				nexus_alignments[atoi(row[0])] = atoi(row[1]);
		mysql_free_result(rows);
	}
	struct expired_boon
	{
		boon_scan_row boon;
		int reason;
	};
	std::vector<expired_boon> expired;
	for (const auto &boon : boons)
	{
		int reason = 0;
		if (boon.duration != -1 && boon.created_at + boon.duration * 60 < request.values[0])
			reason = 7;
		else if (boon.option == 1 && zone_stones.count(boon.criteria) &&
			 epic_completions[boon.criteria] >= zone_stones[boon.criteria])
			reason = 6;
		else if (boon.option == 9 && nexus_alignments.count(boon.criteria) &&
			 ((nexus_alignments[boon.criteria] == 3 && boon.racewar == 1) ||
			  (nexus_alignments[boon.criteria] == -3 && boon.racewar == 2)))
			reason = 6;
		else if (boon.option == 13 && ctf_states.count(boon.criteria) &&
			 ctf_states[boon.criteria].type == 4 && !ctf_states[boon.criteria].room)
			reason = 6;
		if (reason)
			expired.push_back({ boon, reason });
	}
	bool already_applied = false;
	if (!marker_matches_and_lock(connection, "maintenance_boon", request.work_id,
				     request.cursor, &already_applied))
		return sql_failure(connection, request);
	if (!before_deadline(request))
		return sql_failure(connection, request);
	if (!expired.empty() && !already_applied)
	{
		std::string ids;
		for (size_t index = 0; index < expired.size(); ++index)
		{
			if (index)
				ids += ',';
			ids += std::to_string(expired[index].boon.id);
		}
		if (!execute_sql(connection,
				 "UPDATE boons SET active=0,duration=0 WHERE active=1 AND id IN (" +
					 ids + ')'))
			return sql_failure(connection, request);
	}
	if (!before_deadline(request) || !execute_sql(connection, "COMMIT"))
		return sql_failure(connection, request);
	maintenance_result result = failure(request,
					    boons.size() == request.row_budget ?
						    maintenance_outcome::more :
						    maintenance_outcome::complete,
					    0);
	result.rows = static_cast<uint32_t>(boons.size());
	if (!boons.empty())
		result.next_cursor = static_cast<uint64_t>(boons.back().id);
	if (!before_deadline(request))
		return sql_failure(connection, request);
	if (!already_applied)
		for (const auto &entry : expired)
		{
			if (result.value_count + 6 > result.values.size())
				break;
			result.values[result.value_count++] = entry.boon.id;
			result.values[result.value_count++] = entry.boon.racewar;
			result.values[result.value_count++] = entry.boon.pid;
			result.values[result.value_count++] = entry.reason;
			result.values[result.value_count++] = entry.boon.option;
			result.values[result.value_count++] = entry.boon.criteria;
		}
	return result;
}

maintenance_result execute_cargo_market(MYSQL *connection, const maintenance_request &request)
{
	constexpr size_t ports = 10;
	constexpr size_t expected_values = 3 + ports * ports * 4;
	if (request.value_count != expected_values || request.values[0] <= 0 ||
	    (request.values[1] != 0 && request.values[1] != 1) ||
	    (request.values[2] != 0 && request.values[2] != 1) ||
	    (!request.values[1] && !request.values[2]) || request.row_budget < ports * ports)
		return failure(request, maintenance_outcome::permanent_failure, EINVAL);
	if (!begin_transaction(connection))
		return sql_failure(connection, request);
	bool already_applied = false;
	if (!marker_matches_and_lock(connection, "maintenance_cargo", request.work_id, 0,
				     &already_applied))
		return sql_failure(connection, request);
	if (!already_applied)
	{
		if (request.values[1])
		{
			if (!execute_sql(connection, "DELETE FROM ship_cargo_market_mods") ||
			    !execute_sql(connection, "DELETE FROM ship_cargo_prices"))
				return sql_failure(connection, request);
			std::string prices =
				"INSERT INTO ship_cargo_prices(type,port_id,cargo_type,price) VALUES";
			std::string modifiers =
				"INSERT INTO ship_cargo_market_mods(type,port_id,cargo_type,modifier) VALUES";
			bool first = true;
			for (size_t port = 0; port < ports; ++port)
				for (size_t type = 0; type < ports; ++type)
				{
					const size_t offset = 3 + (port * ports + type) * 4;
					if (!first)
					{
						prices += ',';
						modifiers += ',';
					}
					prices += "('CARGO'," + std::to_string(port) + ',' +
						  std::to_string(type) + ',' +
						  std::to_string(request.values[offset]) +
						  "),('CONTRABAND'," + std::to_string(port) + ',' +
						  std::to_string(type) + ',' +
						  std::to_string(request.values[offset + 1]) + ')';
					modifiers += "('CARGO'," + std::to_string(port) + ',' +
						     std::to_string(type) + ',' +
						     std::to_string(request.values[offset + 2] /
								    1000000.0) +
						     "),('CONTRABAND'," + std::to_string(port) +
						     ',' + std::to_string(type) + ',' +
						     std::to_string(request.values[offset + 3] /
								    1000000.0) +
						     ')';
					first = false;
				}
			if (!execute_sql(connection, prices) || !execute_sql(connection, modifiers))
				return sql_failure(connection, request);
		}
		std::string timers = "REPLACE INTO timers(name,date) VALUES";
		if (request.values[1])
			timers += "('update_cargo'," + std::to_string(request.values[0]) + ')';
		if (request.values[2])
		{
			if (request.values[1])
				timers += ',';
			timers += "('update_delayed_cargo_prices'," +
				  std::to_string(request.values[0]) + ')';
		}
		if (!execute_sql(connection, timers))
			return sql_failure(connection, request);
	}
	if (!before_deadline(request) || !execute_sql(connection, "COMMIT"))
		return sql_failure(connection, request);
	maintenance_result result = failure(request, maintenance_outcome::complete, 0);
	result.rows = ports * ports;
	return result;
}

bool write_all(int descriptor, const char *data, size_t size)
{
	while (size)
	{
		const ssize_t written = write(descriptor, data, size);
		if (written < 0 && errno == EINTR)
			continue;
		if (written <= 0)
			return false;
		data += written;
		size -= static_cast<size_t>(written);
	}
	return true;
}

bool atomic_replace(const char *path, const char *data, size_t size)
{
	const std::string temporary = std::string(path) + ".tmp";
	const int descriptor = open(temporary.c_str(),
				    O_WRONLY | O_CREAT | O_TRUNC | O_CLOEXEC | O_NOFOLLOW, 0640);
	if (descriptor < 0)
		return false;
	const bool written = write_all(descriptor, data, size);
	const bool synced = written && fsync(descriptor) == 0;
	const bool closed = close(descriptor) == 0;
	if (!synced || !closed || rename(temporary.c_str(), path) != 0)
	{
		unlink(temporary.c_str());
		return false;
	}
	return true;
}

maintenance_result execute_web_status(const maintenance_request &request)
{
	if (!before_deadline(request) || !request.content_size ||
	    request.content_size >= request.content.size() ||
	    request.content[request.content_size] != '\0')
		return failure(request, maintenance_outcome::permanent_failure, EINVAL);
	if (!atomic_replace("lib/reports/status", request.content.data(), request.content_size))
		return failure(request, maintenance_outcome::retryable_failure,
			       errno ? errno : EIO);
	maintenance_result result = failure(request, maintenance_outcome::complete, 0);
	result.rows = 1;
	return result;
}

bool statistics_marker_matches(MYSQL *connection, int32_t high, int32_t low, bool *matches)
{
	if (!matches)
		return false;
	if (!execute_sql(connection,
			 "SELECT name,date FROM timers WHERE name IN "
			 "('maintenance_statistics_high','maintenance_statistics_low') FOR UPDATE"))
		return false;
	MYSQL_RES *rows = mysql_store_result(connection);
	if (!rows)
		return false;
	bool high_match = false;
	bool low_match = false;
	MYSQL_ROW row = nullptr;
	while ((row = mysql_fetch_row(rows)))
	{
		if (!row[0] || !row[1])
			continue;
		if (!strcmp(row[0], "maintenance_statistics_high"))
			high_match = strtol(row[1], nullptr, 10) == high;
		else if (!strcmp(row[0], "maintenance_statistics_low"))
			low_match = strtol(row[1], nullptr, 10) == low;
	}
	mysql_free_result(rows);
	*matches = high_match && low_match;
	return true;
}

// One statistics request remains pending until both outputs succeed. Its complete
// row (or interrupted prefix) is therefore in the bounded tail of the daily file.
int statistics_file_append(const char *path, uint64_t work_id, const char *line, size_t size)
{
	const int descriptor =
		open(path, O_RDWR | O_CREAT | O_APPEND | O_CLOEXEC | O_NOFOLLOW, 0640);
	if (descriptor < 0)
		return errno;
	const auto append = [&]() -> int
	{
		const off_t end = lseek(descriptor, 0, SEEK_END);
		if (end < 0)
			return errno;
		const off_t start = end > 8192 ? end - 8192 : 0;
		std::string tail(static_cast<size_t>(end - start), '\0');
		size_t offset = 0;
		while (offset < tail.size())
		{
			const ssize_t count = pread(descriptor, tail.data() + offset,
						    tail.size() - offset, start + offset);
			if (count < 0 && errno == EINTR)
				continue;
			if (count <= 0)
				return count < 0 ? errno : EIO;
			offset += static_cast<size_t>(count);
		}
		if (!tail.empty() && tail.back() != '\n')
		{
			const size_t newline = tail.rfind('\n');
			if (newline == std::string::npos && start != 0)
				return EILSEQ;
			const size_t begin = newline == std::string::npos ? 0 : newline + 1;
			const size_t partial = tail.size() - begin;
			// Never erase an unrelated/corrupt row in the guise of recovery.
			if (partial >= size || memcmp(tail.data() + begin, line, partial))
				return EILSEQ;
			if (ftruncate(descriptor, start + begin) != 0)
				return errno;
			tail.resize(begin);
		}
		const std::string marker = " " + std::to_string(work_id) + "\r\n";
		const size_t match = tail.find(marker);
		if (match != std::string::npos)
		{
			const size_t newline = tail.rfind('\n', match);
			const size_t begin = newline == std::string::npos ? 0 : newline + 1;
			if (tail.compare(begin, match + marker.size() - begin, line, size) != 0)
				return EILSEQ;
		}
		else if (!write_all(descriptor, line, size))
			return errno ? errno : EIO;
		// A previous write may have reached the file but failed its fsync.
		return fsync(descriptor) == 0 ? 0 : errno;
	};
	const int error = append();
	const bool closed = close(descriptor) == 0;
	if (error || !closed)
		return error ? error : errno;
	// A new daily file's directory entry must survive before acknowledging it.
	const int directory = open("lib/statistics", O_RDONLY | O_DIRECTORY | O_CLOEXEC);
	if (directory < 0)
		return errno;
	const int sync_error = fsync(directory) == 0 ? 0 : errno;
	const bool directory_closed = close(directory) == 0;
	return sync_error ? sync_error : (directory_closed ? 0 : errno);
}

maintenance_result execute_statistics(MYSQL *connection, const maintenance_request &request)
{
	if (request.value_count != 12 || request.values[0] <= 0)
		return failure(request, maintenance_outcome::permanent_failure, EINVAL);
	const int32_t high = static_cast<int32_t>(request.work_id >> 32);
	const int32_t low = static_cast<int32_t>(request.work_id);
	if (!execute_sql(connection, "START TRANSACTION") ||
	    !execute_sql(connection,
			 "INSERT IGNORE INTO timers(name,date) VALUES"
			 "('maintenance_statistics_high',0),('maintenance_statistics_low',0)"))
		return failure(request, maintenance_outcome::retryable_failure,
			       mysql_errno(connection));
	bool already_applied = false;
	if (!statistics_marker_matches(connection, high, low, &already_applied))
	{
		execute_sql(connection, "ROLLBACK");
		return failure(request, maintenance_outcome::retryable_failure,
			       mysql_errno(connection) ? mysql_errno(connection) : EIO);
	}
	if (!before_deadline(request))
	{
		execute_sql(connection, "ROLLBACK");
		return failure(request, maintenance_outcome::retryable_failure, ETIMEDOUT);
	}
	if (!already_applied)
	{
		std::string insert = "INSERT INTO statistics(date,goods_count,evils_count,"
				     "illithids_count,undeads_count,gods_count,in_guildhall_count,"
				     "sum_goods_levels,sum_evils_levels,sum_undeads_levels,"
				     "sum_illithids_levels,unique_ips_count) VALUES (";
		for (size_t index = 0; index < request.value_count; ++index)
		{
			if (index)
				insert += ',';
			insert += std::to_string(request.values[index]);
		}
		insert += ')';
		const std::string markers =
			"UPDATE timers SET date=CASE name WHEN 'maintenance_statistics_high' THEN " +
			std::to_string(high) + " ELSE " + std::to_string(low) +
			" END WHERE name IN ('maintenance_statistics_high','maintenance_statistics_low')";
		if (!execute_sql(connection, insert) || !execute_sql(connection, markers))
		{
			execute_sql(connection, "ROLLBACK");
			return failure(request, maintenance_outcome::retryable_failure,
				       mysql_errno(connection));
		}
	}
	if (!execute_sql(connection, "COMMIT"))
	{
		execute_sql(connection, "ROLLBACK");
		return failure(request, maintenance_outcome::retryable_failure,
			       mysql_errno(connection));
	}
	time_t captured = static_cast<time_t>(request.values[0]);
	struct tm local = {};
	if (!localtime_r(&captured, &local))
		return failure(request, maintenance_outcome::permanent_failure, EINVAL);
	char date[16] = {};
	char path[128] = {};
	char line[512] = {};
	strftime(date, sizeof(date), "%Y%m%d", &local);
	snprintf(path, sizeof(path), "lib/statistics/statistics_general%s", date);
	const int line_size =
		snprintf(line, sizeof(line),
			 "%02d %lld %lld %lld %lld %lld %lld %lld %lld %lld %lld %lld %llu\r\n",
			 local.tm_hour, (long long)request.values[1], (long long)request.values[2],
			 (long long)request.values[3], (long long)request.values[4],
			 (long long)request.values[5], (long long)request.values[6],
			 (long long)request.values[7], (long long)request.values[8],
			 (long long)request.values[9], (long long)request.values[10],
			 (long long)request.values[11], (unsigned long long)request.work_id);
	if (line_size <= 0 || static_cast<size_t>(line_size) >= sizeof(line))
		return failure(request, maintenance_outcome::permanent_failure, EOVERFLOW);
	if (!before_deadline(request))
		return failure(request, maintenance_outcome::retryable_failure, ETIMEDOUT);
	const int file_error =
		statistics_file_append(path, request.work_id, line, static_cast<size_t>(line_size));
	if (file_error)
		return failure(request,
			       file_error == EILSEQ ? maintenance_outcome::permanent_failure :
						      maintenance_outcome::retryable_failure,
			       file_error);

	maintenance_result result = failure(request, maintenance_outcome::complete, 0);
	result.rows = already_applied ? 0 : 1;
	return result;
}

maintenance_result execute_auction(MYSQL *connection, const maintenance_request &request)
{
	maintenance_result result = failure(request, maintenance_outcome::permanent_failure, 0);
	const std::string sql =
		"SELECT id FROM auctions WHERE id>" + std::to_string(request.cursor) +
		" AND end_time<NOW() AND status=1 AND custody_state=1 ORDER BY id LIMIT " +
		limit_sql(request);
	if (!query_values(connection, request, sql, &result))
		return failure(request, maintenance_outcome::retryable_failure,
			       mysql_errno(connection));
	return result;
}

maintenance_result execute_catalog(MYSQL *connection, const maintenance_request &request)
{
	maintenance_result result = failure(request, maintenance_outcome::permanent_failure, 0);
	const std::string sql = "SELECT number FROM zones WHERE task_zone=1 AND number>" +
				std::to_string(request.cursor) + " ORDER BY number LIMIT " +
				limit_sql(request);
	if (!query_values(connection, request, sql, &result))
		return failure(request, maintenance_outcome::retryable_failure,
			       mysql_errno(connection));
	return result;
}

maintenance_result execute_poll(MYSQL *connection, const maintenance_request &request)
{
	maintenance_result result = failure(request, maintenance_outcome::permanent_failure, 0);
	const std::string selection =
		"SELECT id FROM polls WHERE id>" + std::to_string(request.cursor) +
		" AND is_active=1 AND expires_at<UNIX_TIMESTAMP() ORDER BY id LIMIT " +
		limit_sql(request);
	if (!query_values(connection, request, selection, &result))
		return failure(request, maintenance_outcome::retryable_failure,
			       mysql_errno(connection));
	if (!result.value_count)
		return result;
	std::string update = "UPDATE polls SET is_active=0 WHERE is_active=1 AND id IN (";
	for (size_t index = 0; index < result.value_count; ++index)
	{
		if (index)
			update += ',';
		update += std::to_string(result.values[index]);
	}
	update += ')';
	if (!before_deadline(request) ||
	    mysql_real_query(connection, update.data(), update.size()) != 0)
		return failure(request, maintenance_outcome::retryable_failure,
			       mysql_errno(connection));
	return result;
}

// ADR 0003: a network address is kept 30 days after its last use, everywhere but the ban
// list, which is a file. A run clears at most row_budget addresses per table, so an old
// database is cleared over many short runs.
maintenance_result execute_address_retention(MYSQL *connection, const maintenance_request &request)
{
	static constexpr const char *expired[] = {
		"DELETE FROM account_ips WHERE updated_at < NOW() - INTERVAL 30 DAY",
		"DELETE FROM account_login_history WHERE `timestamp` < NOW() - INTERVAL 30 DAY",
		"UPDATE log_entries SET ip_address='' WHERE date < NOW() - INTERVAL 30 DAY "
		"AND ip_address<>''",
		"UPDATE ip_info SET last_ip='none' WHERE last_connect < NOW() - INTERVAL 30 DAY "
		"AND last_ip<>'none'",
		"UPDATE player_data SET last_ip=0 WHERE last_save < NOW() - INTERVAL 30 DAY "
		"AND last_ip<>0",
		"UPDATE account_characters SET last_ip=NULL WHERE (last_login IS NULL OR "
		"last_login < NOW() - INTERVAL 30 DAY) AND last_ip IS NOT NULL",
	};
	maintenance_result result = failure(request, maintenance_outcome::complete, 0);
	for (const char *statement : expired)
	{
		const std::string sql = std::string(statement) + " LIMIT " + limit_sql(request);
		if (!before_deadline(request))
			return failure(request, maintenance_outcome::retryable_failure, ETIMEDOUT);
		if (!execute_sql(connection, sql))
		{
			// The website keeps account_login_history; a database without it has none.
			if (mysql_errno(connection) == ER_NO_SUCH_TABLE)
				continue;
			return sql_failure(connection, request);
		}
		const uint64_t rows = mysql_affected_rows(connection);
		result.rows += static_cast<uint32_t>(rows);
		if (rows >= request.row_budget)
			result.outcome = maintenance_outcome::more;
	}
	return result;
}

std::vector<std::filesystem::path> list_files(const char *directory)
{
	std::vector<std::filesystem::path> files;
	std::error_code error;
	for (std::filesystem::directory_iterator entry(directory, error), end;
	     !error && entry != end; entry.increment(error))
		files.push_back(entry->path());
	return files;
}

// ADR 0003: no log line is kept past 30 days. The launcher moves the live logs into
// logs/old-logs/<date>/ at each start, but a copyover never goes back to it, so this moves
// them there too once they are a day old: logs/log/.since marks when a live set began (the
// launcher makes it), and a set without one, as after a copyover onto this code, is of
// unknown age and moves at once.
// A file then holds at most about 25 hours of lines (this job runs hourly), so every
// archived file, and every core dump, goes 28 days after its last write, before its first
// line is 30 days old; an archive left empty goes too. The game appends each log line by
// opening its file, so moving a live file loses no line.
void expire_log_files()
{
	namespace fs = std::filesystem;
	std::error_code error;
	const auto now = fs::file_time_type::clock::now();
	const fs::path since = "logs/log/.since";
	if (!fs::exists(since, error) ||
	    now - fs::last_write_time(since, error) > std::chrono::hours(24))
	{
		char stamp[32];
		const time_t clock = time(nullptr);
		struct tm local;
		strftime(stamp, sizeof(stamp), "%Y.%m.%d-%H.%M.%S", localtime_r(&clock, &local));
		const fs::path archive = fs::path("logs/old-logs") / stamp;
		fs::create_directories(archive / "player-log", error);
		for (const fs::path &file : list_files("logs/log"))
			if (file.filename() != ".gitignore")
				fs::rename(file, archive / file.filename(), error);
		for (const fs::path &file : list_files("logs/player-log"))
			if (file.filename() != ".gitignore")
				fs::rename(file, archive / "player-log" / file.filename(), error);
		std::ofstream{ since };
	}

	const auto expired = [&](const fs::path &file)
	{
		return fs::is_regular_file(file, error) &&
		       now - fs::last_write_time(file, error) > std::chrono::hours(24 * 28);
	};
	for (const fs::path &file : list_files("."))
		if (file.filename().string().starts_with("core.") && expired(file))
			fs::remove(file, error);
	for (const fs::path &archive : list_files("logs/old-logs"))
	{
		for (const fs::path &file : list_files(archive.c_str()))
			if (expired(file))
				fs::remove(file, error);
		for (const fs::path &file : list_files((archive / "player-log").c_str()))
			if (expired(file))
				fs::remove(file, error);
		// remove() leaves a directory that still holds files.
		fs::remove(archive / "player-log", error);
		fs::remove(archive, error);
	}
}
} // namespace

maintenance_result maintenance_repository_execute(const maintenance_request &request, void *)
{
	if (!request.work_id || static_cast<size_t>(request.job_id) >= MAINTENANCE_JOB_COUNT ||
	    !request.row_budget || request.row_budget > MAINTENANCE_ROW_BUDGET_MAX ||
	    !request.time_budget_usec ||
	    request.time_budget_usec > MAINTENANCE_TIME_BUDGET_USEC_MAX ||
	    !before_deadline(request))
		return failure(request, maintenance_outcome::permanent_failure, EINVAL);
	// Trophy totals are owned by player checkpoints. Retain the retired job ID
	// as a no-op, without acquiring a database connection on either backend.
	if (request.job_id == maintenance_job_id::zone_trophy)
		return failure(request, maintenance_outcome::complete, 0);
	if (request.job_id == maintenance_job_id::web_status)
		return execute_web_status(request);
	if (request.job_id == maintenance_job_id::address_retention)
		expire_log_files();
#ifdef __NO_MYSQL__
	// Flat-file expires its auctions and boons on the game thread when these are due
	// (maintenance_handle_completions()).
	if (request.job_id == maintenance_job_id::auction_due_scan ||
	    request.job_id == maintenance_job_id::boon_scan)
		return failure(request, maintenance_outcome::complete, 0);
	// Flat-file keeps no address tables, only the log files.
	if (request.job_id == maintenance_job_id::address_retention)
		return failure(request, maintenance_outcome::complete, 0);
	if (request.job_id == maintenance_job_id::cargo_market)
	{
		if (!flatfile_cargo_maintenance_apply(request.values.data(), request.value_count))
			return failure(request, maintenance_outcome::retryable_failure, EIO);
		maintenance_result result = failure(request, maintenance_outcome::complete, 0);
		result.rows = NUM_PORTS * NUM_PORTS;
		return result;
	}
#endif
	MYSQL *connection = sql_pool_acquire();
	if (!connection)
		return failure(request, maintenance_outcome::retryable_failure, EAGAIN);
	connection_guard guard = { connection };
	switch (request.job_id)
	{
	case maintenance_job_id::auction_due_scan:
		return execute_auction(connection, request);
	case maintenance_job_id::poll_expiration:
		return execute_poll(connection, request);
	case maintenance_job_id::epic_task_catalog:
		return execute_catalog(connection, request);
	case maintenance_job_id::epic_zone_balance:
		return execute_epic_balance(connection, request);
	case maintenance_job_id::level_cap:
		return execute_level_cap(connection, request);
	case maintenance_job_id::epic_zone_modifiers:
		return execute_epic_modifiers(connection, request);
	case maintenance_job_id::boon_scan:
		return execute_boon_scan(connection, request);
	case maintenance_job_id::cargo_market:
		return execute_cargo_market(connection, request);
	case maintenance_job_id::operational_statistics:
		return execute_statistics(connection, request);
	case maintenance_job_id::address_retention:
		return execute_address_retention(connection, request);
	default:
		return failure(request, maintenance_outcome::permanent_failure, ENOTSUP);
	}
}
