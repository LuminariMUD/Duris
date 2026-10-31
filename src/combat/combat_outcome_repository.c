/****************************************************************************
 *
 *  File: combat_outcome_repository.c                           Part of Duris
 *  Usage: SQL combat outcome repository: ledger and player state
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "combat/combat_outcome_repository.h"
#include "combat/frag_cap_repository.h"
#include "combat/frag_cap_config.h"

#include "world/epic_command.h"
#include "guild/artifact_guild_repository.h"

#include <algorithm>
#include <array>
#include <cerrno>
#include <chrono>
#include <climits>
#include <cstring>
#include <limits>
#include <mysql.h>
#include <openssl/sha.h>
#include <string>
#include <vector>

namespace
{
// Frags, epic points and the wallet are memory's: the submit changed them and the
// player's save writes them. The outcome records the kill and continues the frag and
// epic ledgers from their last rows, advancing only the revisions the rows are keyed on.
struct player_state
{
	size_t payload_index;
	uint32_t pid;
	int64_t frags;
	int64_t epics;
	uint64_t frag_revision;
	uint64_t epic_revision;
	uint64_t delivery_previous = 0;
};

bool execute(MYSQL *connection, const std::string &sql)
{
	return mysql_real_query(connection, sql.data(), sql.size()) == 0;
}

bool parse_i64(const char *text, int64_t *value)
{
	if (!text || !value)
		return false;
	char *end = nullptr;
	errno = 0;
	const long long parsed = strtoll(text, &end, 10);
	if (errno || !end || *end)
		return false;
	*value = parsed;
	return true;
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

std::string escape(MYSQL *connection, const char *value, size_t size)
{
	std::string escaped(size * 2 + 1, '\0');
	const unsigned long length = mysql_real_escape_string(connection, escaped.data(),
							      value ? value : "", value ? size : 0);
	escaped.resize(length);
	return escaped;
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

critical_operation_id child_operation(const critical_operation_id &parent, uint8_t domain,
				      uint16_t index)
{
	std::array<uint8_t, CRITICAL_COMMAND_ID_BYTES + 3> input = {};
	std::copy(parent.bytes.begin(), parent.bytes.end(), input.begin());
	input[CRITICAL_COMMAND_ID_BYTES] = domain;
	input[CRITICAL_COMMAND_ID_BYTES + 1] = static_cast<uint8_t>(index);
	input[CRITICAL_COMMAND_ID_BYTES + 2] = static_cast<uint8_t>(index >> 8);
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
	SHA256(input.data(), input.size(), digest.data());
	critical_operation_id result = {};
	std::copy_n(digest.begin(), result.bytes.size(), result.bytes.begin());
	return result;
}

bool insert_child_inbox(MYSQL *connection, const critical_operation_id &child,
			critical_command_type type, uint64_t revision)
{
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
	SHA256(child.bytes.data(), child.bytes.size(), digest.data());
	const std::string operation = bytes_hex(child.bytes.data(), child.bytes.size());
	const std::string hash = bytes_hex(digest.data(), digest.size());
	const std::string sql =
		"INSERT INTO critical_operation_inbox(operation_id,command_hash,keys_hash,"
		"command_type,schema_version,payload_version,status,result_code,durable_revision,"
		"result_payload,committed_at,expected_outbox_events) VALUES(UNHEX('" +
		operation + "'),UNHEX('" + hash + "'),UNHEX('" + hash + "')," +
		std::to_string(static_cast<uint16_t>(type)) + ",1,1,1,0," +
		std::to_string(revision) + ",'',CURRENT_TIMESTAMP(6),0)";
	return execute(connection, sql);
}

// The value of a ledger's last row for the player, when the player has one.
bool ledger_tail(MYSQL *connection, const std::string &sql, int64_t *value)
{
	if (!execute(connection, sql))
		return false;
	MYSQL_RES *result = mysql_store_result(connection);
	if (!result)
		return false;
	MYSQL_ROW row = mysql_fetch_row(result);
	const bool ok = !row || parse_i64(row[0], value);
	mysql_free_result(result);
	return ok;
}

bool load_player(MYSQL *connection, uint32_t pid, size_t payload_index, player_state *state)
{
	const std::string sql = "SELECT frags,frag_revision,epics,epic_revision FROM player_data "
				"WHERE pid=" +
				std::to_string(pid) + " FOR UPDATE";
	if (!execute(connection, sql))
		return false;
	MYSQL_RES *result = mysql_store_result(connection);
	MYSQL_ROW row = result ? mysql_fetch_row(result) : nullptr;
	const bool ok = row && parse_i64(row[0], &state->frags) &&
			parse_u64(row[1], &state->frag_revision) &&
			parse_i64(row[2], &state->epics) &&
			parse_u64(row[3], &state->epic_revision);
	if (result)
		mysql_free_result(result);
	state->payload_index = payload_index;
	state->pid = pid;
	return ok &&
	       ledger_tail(connection,
			   "SELECT frags_after FROM combat_frag_ledger WHERE pid=" +
				   std::to_string(pid) + " AND frag_revision=" +
				   std::to_string(state->frag_revision) + " FOR UPDATE",
			   &state->frags) &&
	       ledger_tail(connection,
			   "SELECT balance_after FROM epic_ledger WHERE pid=" +
				   std::to_string(pid) + " AND epic_revision=" +
				   std::to_string(state->epic_revision) + " FOR UPDATE",
			   &state->epics);
}
} // namespace

bool combat_outcome_repository_execute(MYSQL *connection, const critical_command &command,
				       combat_outcome_result *result, unsigned int *result_code,
				       bool *mutation_applied)
{
	if (!critical_command_valid(command))
	{
		errno = EPROTONOSUPPORT;
		return false;
	}

	if (!connection || !result || !result_code || !mutation_applied)
		return false;
	combat_outcome_payload payload = {};
	if (!combat_outcome_command_decode_payload(command, &payload))
	{
		errno = EINVAL;
		return false;
	}
	*result = {};
	*result_code = 0;
	*mutation_applied = false;
	std::vector<size_t> order(payload.participant_count);
	for (size_t index = 0; index < order.size(); ++index)
		order[index] = index;
	std::sort(order.begin(), order.end(), [&](size_t left, size_t right)
		  { return payload.participants[left].pid < payload.participants[right].pid; });
	std::vector<player_state> players;
	players.reserve(order.size());
	for (size_t index : order)
	{
		player_state state = {};
		const auto &entry = payload.participants[index];
		if (!load_player(connection, entry.pid, index, &state))
		{
			*result_code = ENOENT;
			return true;
		}
		if (entry.flags & COMBAT_PARTICIPANT_DIVINE_EPIC)
		{
			if (!execute(connection,
				     "SELECT epic_revision FROM epic_ledger WHERE pid=" +
					     std::to_string(entry.pid) + " AND reason_type IN (" +
					     std::to_string(static_cast<uint16_t>(
						     epic_reason_type::divine_pvp_award)) +
					     "," +
					     std::to_string(static_cast<uint16_t>(
						     epic_reason_type::divine_zone_award)) +
					     ") ORDER BY epic_revision DESC LIMIT 1 FOR UPDATE"))
				return false;
			MYSQL_RES *rows = mysql_store_result(connection);
			MYSQL_ROW row = rows ? mysql_fetch_row(rows) : nullptr;
			const bool valid = rows &&
					   (!row || parse_u64(row[0], &state.delivery_previous));
			if (rows)
				mysql_free_result(rows);
			if (!valid || state.delivery_previous > state.epic_revision)
				return false;
		}
		players.push_back(std::move(state));
	}
	const std::string operation =
		bytes_hex(command.operation_id.bytes.data(), command.operation_id.bytes.size());
	const std::string room =
		escape(connection, payload.room_name.data(),
		       strnlen(payload.room_name.data(), payload.room_name.size()));
	if (!execute(connection, "INSERT INTO pkill_event(stamp,room_vnum,room_name) VALUES("
				 "NOW()," +
					 std::to_string(payload.room_vnum) + ",'" + room + "')"))
		return false;
	const uint64_t event_id = mysql_insert_id(connection);
	if (!execute(connection,
		     "INSERT INTO combat_outcome(operation_id,pkill_event_id,victim_pid,room_vnum,"
		     "participant_count,killer_allies) VALUES(UNHEX('" +
			     operation + "')," + std::to_string(event_id) + "," +
			     std::to_string(payload.victim_pid) + "," +
			     std::to_string(payload.room_vnum) + "," +
			     std::to_string(payload.participant_count) + "," +
			     std::to_string(payload.killer_allies) + ")"))
		return false;

	result->event_id = event_id;
	result->victim_pid = payload.victim_pid;
	result->prepared_at = payload.prepared_at;
	result->artifact_intents = payload.artifact_intents;
	result->participant_count = payload.participant_count;
	for (player_state &state : players)
	{
		const size_t index = state.payload_index;
		const auto &entry = payload.participants[index];
		if ((entry.frag_delta > 0 && state.frags > INT64_MAX - entry.frag_delta) ||
		    (entry.frag_delta < 0 && state.frags < INT64_MIN - entry.frag_delta) ||
		    (entry.epic_delta > 0 && state.epics > INT64_MAX - entry.epic_delta) ||
		    state.frag_revision == UINT64_MAX || state.epic_revision == UINT64_MAX)
		{
			errno = ERANGE;
			return false;
		}
		if (entry.frag_delta)
		{
			if (!execute(connection,
				     "INSERT IGNORE INTO combat_frag_baseline(pid,opening_frags,"
				     "opening_revision) VALUES(" +
					     std::to_string(entry.pid) + "," +
					     std::to_string(state.frags) + "," +
					     std::to_string(state.frag_revision) + ")"))
				return false;
			state.frags += entry.frag_delta;
			++state.frag_revision;
			if (!execute(connection, "UPDATE player_data SET frag_revision=" +
							 std::to_string(state.frag_revision) +
							 " WHERE pid=" + std::to_string(entry.pid) +
							 " AND frag_revision=" +
							 std::to_string(state.frag_revision - 1)) ||
			    mysql_affected_rows(connection) != 1 ||
			    !execute(connection,
				     "INSERT INTO combat_frag_ledger(operation_id,participant_index,pid,"
				     "delta,frags_after,frag_revision) VALUES(UNHEX('" +
					     operation + "')," + std::to_string(index) + "," +
					     std::to_string(entry.pid) + "," +
					     std::to_string(entry.frag_delta) + "," +
					     std::to_string(state.frags) + "," +
					     std::to_string(state.frag_revision) + ")") ||
			    !execute(connection, "UPDATE frag_leaderboard SET total_frags=" +
							 std::to_string(state.frags) +
							 ",last_updated=NOW() WHERE pid=" +
							 std::to_string(entry.pid) +
							 " AND deleted_at IS NULL") ||
			    !execute(connection, "INSERT INTO progress VALUES(0," +
							 std::to_string(entry.pid) + ",1,NOW()," +
							 std::to_string(entry.frag_delta) + ")"))
				return false;
		}
		if (entry.epic_delta)
		{
			if (!execute(connection,
				     "INSERT IGNORE INTO epic_balance_baseline(pid,opening_balance,"
				     "opening_revision) VALUES(" +
					     std::to_string(entry.pid) + "," +
					     std::to_string(state.epics) + "," +
					     std::to_string(state.epic_revision) + ")"))
				return false;
			state.epics += entry.epic_delta;
			++state.epic_revision;
			const critical_operation_id child =
				child_operation(command.operation_id, 1, index);
			const std::string child_hex =
				bytes_hex(child.bytes.data(), child.bytes.size());
			if (!insert_child_inbox(connection, child, critical_command_type::epic,
						state.epic_revision) ||
			    !execute(connection, "UPDATE player_data SET epic_revision=" +
							 std::to_string(state.epic_revision) +
							 " WHERE pid=" + std::to_string(entry.pid) +
							 " AND epic_revision=" +
							 std::to_string(state.epic_revision - 1)) ||
			    mysql_affected_rows(connection) != 1 ||
			    !execute(
				    connection,
				    "INSERT INTO epic_ledger(operation_id,pid,delta,balance_after,"
				    "epic_revision,reason_type,reason_id,source_site) VALUES(UNHEX('" +
					    child_hex + "')," + std::to_string(entry.pid) + "," +
					    std::to_string(entry.epic_delta) + "," +
					    std::to_string(state.epics) + "," +
					    std::to_string(state.epic_revision) + "," +
					    std::to_string(static_cast<uint16_t>(
						    (entry.flags & COMBAT_PARTICIPANT_DIVINE_EPIC) ?
							    epic_reason_type::divine_pvp_award :
							    epic_reason_type::pvp_award)) +
					    "," + std::to_string(payload.victim_pid) + "," +
					    std::to_string(static_cast<uint16_t>(
						    critical_source_site::combat)) +
					    ")"))
				return false;
		}
		const char *role = entry.role == combat_participant_role::victim ? "VICTIM" :
				   entry.role == combat_participant_role::victim_group ?
										   "VICTIM-GROUP" :
										   "KILLER";
		const std::string description =
			escape(connection, entry.description.data(),
			       strnlen(entry.description.data(), entry.description.size()));
		const std::string equipment =
			escape(connection, entry.equipment.data(), entry.equipment.size());
		const std::string log = escape(connection, entry.log.data(), entry.log.size());
		if (!execute(connection,
			     "INSERT INTO pkill_info(event_id,pid,level,pk_type,player_description,"
			     "equip,log,inroom,leader,webinfo_at_capture) VALUES(" +
				     std::to_string(event_id) + "," + std::to_string(entry.pid) +
				     "," + std::to_string(entry.level) + ",'" + role + "','" +
				     description + "','" + equipment + "','" + log + "'," +
				     std::to_string((entry.flags & COMBAT_PARTICIPANT_IN_ROOM) !=
						    0) +
				     "," +
				     std::to_string((entry.flags & COMBAT_PARTICIPANT_LEADER) != 0) +
				     "," +
				     (entry.webinfo_at_capture == combat_webinfo::unknown ? "NULL" :
				      entry.webinfo_at_capture == combat_webinfo::on	  ? "1" :
											    "0") +
				     ")"))
			return false;
		if (!execute(
			    connection,
			    "INSERT INTO combat_outcome_participant(operation_id,participant_index,pid,"
			    "role,flags,frag_delta,epic_delta,wallet_delta_copper,frag_after,"
			    "frag_revision,epic_revision,wallet_revision,bank_revision) VALUES(UNHEX('" +
				    operation + "')," + std::to_string(index) + "," +
				    std::to_string(entry.pid) + "," +
				    std::to_string(static_cast<uint8_t>(entry.role)) + "," +
				    std::to_string(entry.flags) + "," +
				    std::to_string(entry.frag_delta) + "," +
				    std::to_string(entry.epic_delta) + "," +
				    std::to_string(entry.wallet_delta_copper) + "," +
				    std::to_string(state.frags) + "," +
				    std::to_string(state.frag_revision) + "," +
				    std::to_string(state.epic_revision) + ",0,0)"))
			return false;
		result->participants[index] = { .pid = entry.pid,
						.frags = state.frags,
						.epics = state.epics,
						.wallet_value = -1,
						.bank = {},
						.frag_revision = state.frag_revision,
						.epic_revision = state.epic_revision,
						.wallet_revision = 0,
						.bank_revision = 0 };
		if (entry.flags & COMBAT_PARTICIPANT_DIVINE_EPIC)
		{
			auto &delivered = result->participants[index];
			delivered.epic_delivery_previous = state.delivery_previous;
			delivered.epic_delivery_delta = entry.epic_delta;
			delivered.epic_boon_id = entry.epic_boon_id;
			delivered.epic_base = entry.epic_base;
			delivered.epic_spill_blood = entry.epic_spill_blood;
			delivered.epic_delivery_flags =
				entry.flags &
				(COMBAT_PARTICIPANT_DIVINE_EPIC | COMBAT_PARTICIPANT_SPILL_BLOOD);
		}
	}
	for (const auto &child : payload.artifact_deliveries)
		if (!artifact_guild_repository_prepare_delivery(connection, child))
			return false;
	frag_cap_state cap;
	const auto loaded = frag_cap_sql_load(connection, &cap, true);
	const uint64_t before = cap.revision;
	const int64_t now = std::chrono::duration_cast<std::chrono::microseconds>(
				    std::chrono::system_clock::now().time_since_epoch())
				    .count();
	if (loaded != frag_cap_store_result::ok ||
	    !frag_cap_apply_combat(&cap, command, payload, now, frag_cap_config_policy()) ||
	    (cap.revision != before &&
	     frag_cap_sql_save(connection, cap) != frag_cap_store_result::ok))
	{
		errno = loaded == frag_cap_store_result::io_error ? EIO : EILSEQ;
		return false;
	}
	*mutation_applied = true;
	return true;
}
