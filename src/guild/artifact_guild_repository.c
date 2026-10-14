/****************************************************************************
 *
 *  File: artifact_guild_repository.c                           Part of Duris
 *  Usage: SQL artifact guild repository: artifacts and deltas
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "guild/artifact_guild_repository.h"
#include "core/utility.h"
#include "core/files.h"
#include "persistence/persistence_log.h"

#include <algorithm>
#include <cstdio>
#include <cerrno>
#include <cstdlib>
#include <mysql.h>
#include <string>

namespace
{
bool execute(MYSQL *connection, const std::string &sql)
{
	return mysql_real_query(connection, sql.data(), sql.size()) == 0;
}

std::string bytes_hex(const uint8_t *bytes, size_t size)
{
	static const char HEX[] = "0123456789abcdef";
	std::string result(size * 2, '0');
	for (size_t index = 0; index < size; ++index)
	{
		result[index * 2] = HEX[bytes[index] >> 4];
		result[index * 2 + 1] = HEX[bytes[index] & 15];
	}
	return result;
}

// The one writer orders history. These revisions belong to the ledgers, not to
// gameplay snapshots, and continue to work after the live entity is removed.
bool next_revision(MYSQL *connection, const std::string &query, uint64_t *revision)
{
	if (!execute(connection, query))
		return false;
	MYSQL_RES *rows = mysql_store_result(connection);
	MYSQL_ROW row = rows ? mysql_fetch_row(rows) : nullptr;
	char *end = nullptr;
	errno = 0;
	const uint64_t prior = row && row[0] ? strtoull(row[0], &end, 10) : 0;
	const bool valid = row && row[0] && end && !*end && !errno && prior < UINT64_MAX;
	if (rows)
		mysql_free_result(rows);
	if (!valid)
	{
		errno = ERANGE;
		return false;
	}
	*revision = prior + 1;
	return true;
}
} // namespace

std::array<char, 1024> artifact_guild_repository_diagnostic(const critical_command &command,
							    const char *reason, unsigned int error)
{
	char operation[CRITICAL_COMMAND_ID_HEX_SIZE] = {},
	     parent[CRITICAL_COMMAND_ID_HEX_SIZE] = {};
	critical_operation_id_to_hex(command.operation_id, operation, sizeof(operation));
	if (command.payload.size() >= CRITICAL_COMMAND_ID_BYTES)
	{
		critical_operation_id parent_id = {};
		std::copy_n(command.payload.begin(), parent_id.bytes.size(),
			    parent_id.bytes.begin());
		critical_operation_id_to_hex(parent_id, parent, sizeof(parent));
	}
	artifact_guild_payload payload = {};
	const bool decoded = artifact_guild_command_decode_payload(command, &payload);
	std::array<char, 1024> record = {};
	snprintf(
		record.data(), record.size(),
		"domain=artifact_guild action=history outcome=alert detail=reason=%s operation=%s parent=%s version=%u accepted_us=%llu error=%u site=%s:%d decoded=%d actor_pid=%u guild_id=%u artifact_count=%u",
		reason, operation, parent[0] ? parent : "unavailable", command.payload_version,
		static_cast<unsigned long long>(command.accepted_at_usec), error, __FILE__,
		__LINE__, decoded, decoded ? payload.actor_pid : 0, decoded ? payload.guild_id : 0,
		decoded ? payload.artifact_count : 0);
	// This runs on the SQL writer. The record contains only controlled categories,
	// opaque IDs and numbers; never traverse descriptors or use logit's shared clock.
	persistence_log_submit(record.data());
	return record;
}

bool artifact_guild_repository_execute(MYSQL *connection, const critical_command &command,
				       artifact_guild_result *result, unsigned int *result_code,
				       bool *mutation_applied,
				       std::array<char, 1024> *failure_detail)
{
	if (!connection || !result || !result_code || !mutation_applied || !failure_detail)
		return false;
	const auto fail = [&](const char *reason, unsigned int code)
	{
		*failure_detail = artifact_guild_repository_diagnostic(command, reason, code);
		errno = code;
		return false;
	};
	if (!critical_command_valid(command))
		return fail("malformed_command", EINVAL);
	// The generic repository resolves an existing receipt before reaching here.
	// Never execute an old, uncommitted state-changing command after the cutover.
	if (command.payload_version != ARTIFACT_GUILD_PAYLOAD_VERSION)
		return fail("legacy_uncommitted", EPROTONOSUPPORT);
	artifact_guild_payload payload = {};
	if (!artifact_guild_command_decode_payload(command, &payload))
		return fail("malformed_payload", EINVAL);
	*result = {};
	*result_code = 0;
	*mutation_applied = false;
	const auto storage_failure = [&]()
	{
		return fail("storage_failure", mysql_errno(connection) ? mysql_errno(connection) :
									 (errno ? errno : EIO));
	};
	const std::string operation =
		bytes_hex(command.operation_id.bytes.data(), command.operation_id.bytes.size());
	const std::string parent = bytes_hex(payload.parent_operation_id.bytes.data(),
					     payload.parent_operation_id.bytes.size());
	if (!execute(connection,
		     "SELECT status FROM critical_operation_inbox WHERE operation_id=UNHEX('" +
			     parent + "')"))
		return storage_failure();
	MYSQL_RES *parents = mysql_store_result(connection);
	MYSQL_ROW parent_row = parents ? mysql_fetch_row(parents) : nullptr;
	const bool parent_committed = parent_row && parent_row[0] && atoi(parent_row[0]) == 1;
	if (parents)
		mysql_free_result(parents);
	if (!parent_committed)
		return fail("missing_parent", ENOENT);

	uint64_t guild_revision = 0;
	if (payload.guild_id &&
	    !next_revision(
		    connection,
		    "SELECT COALESCE(MAX(guild_revision),0) FROM guild_outcome_ledger WHERE guild_id=" +
			    std::to_string(payload.guild_id),
		    &guild_revision))
		return storage_failure();
	if (!execute(
		    connection,
		    "INSERT INTO artifact_guild_outcome(operation_id,parent_operation_id,actor_pid,"
		    "guild_id,prestige_delta,construction_delta,artifact_count,guild_prestige_after,"
		    "guild_construction_after,guild_revision) VALUES(UNHEX('" +
			    operation + "'),UNHEX('" + parent + "')," +
			    std::to_string(payload.actor_pid) + "," +
			    std::to_string(payload.guild_id) + "," +
			    std::to_string(payload.prestige_delta) + "," +
			    std::to_string(payload.construction_delta) + "," +
			    std::to_string(payload.artifact_count) + "," +
			    std::to_string(payload.prestige_after) + "," +
			    std::to_string(payload.construction_after) + "," +
			    std::to_string(guild_revision) + ")"))
		return fail(mysql_errno(connection) == 1062 ? "identity_conflict" :
							      "storage_failure",
			    mysql_errno(connection));
	result->guild_id = payload.guild_id;
	result->prestige = payload.prestige_after;
	result->construction = payload.construction_after;
	result->guild_revision = guild_revision;
	result->artifact_count = payload.artifact_count;
	for (size_t index = 0; index < payload.artifact_count; ++index)
	{
		const auto &entry = payload.artifacts[index];
		uint64_t revision = 0;
		if (!next_revision(
			    connection,
			    "SELECT GREATEST(COALESCE((SELECT MAX(revision) FROM artifact_delta_ledger WHERE vnum=" +
				    std::to_string(entry.vnum) +
				    "),0),COALESCE((SELECT opening_revision FROM artifact_domain_baseline WHERE vnum=" +
				    std::to_string(entry.vnum) + "),0))",
			    &revision))
			return storage_failure();
		if (!execute(
			    connection,
			    "INSERT INTO artifact_guild_outcome_delta(operation_id,artifact_index,vnum,flags,"
			    "timer_before,timer_after,bind_owner_before,bind_owner_after,bind_timer_before,bind_timer_after,revision) "
			    "VALUES(UNHEX('" +
				    operation + "')," + std::to_string(index) + "," +
				    std::to_string(entry.vnum) + "," + std::to_string(entry.flags) +
				    "," + std::to_string(entry.timer_before) + "," +
				    std::to_string(entry.timer) + "," +
				    std::to_string(entry.bind_owner_before) + "," +
				    std::to_string(entry.bind_owner_pid) + "," +
				    std::to_string(entry.bind_timer_before) + "," +
				    std::to_string(entry.bind_timer) + "," +
				    std::to_string(revision) + ")") ||
		    !execute(connection,
			     "INSERT INTO artifact_delta_ledger(operation_id,artifact_index,vnum,timer_delta,bind_owner_pid,bind_timer_epoch,revision) "
			     "VALUES(UNHEX('" +
				     operation + "')," + std::to_string(index) + "," +
				     std::to_string(entry.vnum) + "," +
				     std::to_string(entry.timer - entry.timer_before) + "," +
				     std::to_string(entry.bind_owner_pid) + "," +
				     std::to_string(entry.bind_timer) + "," +
				     std::to_string(revision) + ")"))
			return storage_failure();
		result->artifacts[index] = { entry.vnum, entry.timer, entry.bind_owner_pid,
					     entry.bind_timer, revision };
	}
	if (payload.guild_id &&
	    !execute(connection,
		     "INSERT INTO guild_outcome_ledger(operation_id,guild_id,prestige_delta,construction_delta,prestige_after,construction_after,guild_revision) "
		     "VALUES(UNHEX('" +
			     operation + "')," + std::to_string(payload.guild_id) + "," +
			     std::to_string(payload.prestige_delta) + "," +
			     std::to_string(payload.construction_delta) + "," +
			     std::to_string(payload.prestige_after) + "," +
			     std::to_string(payload.construction_after) + "," +
			     std::to_string(guild_revision) + ")"))
		return storage_failure();
	*mutation_applied = true; // history/outbox only; gameplay state was already applied
	return true;
}
