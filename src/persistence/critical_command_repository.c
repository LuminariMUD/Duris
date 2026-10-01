#include "persistence/critical_command_repository.h"
#include "sql/sql_thread_init.h"

#include "economy/currency_command.h"
#include "persistence/critical_outbox.h"
#include "world/epic_command.h"
#include "economy/auction_command.h"
#include "economy/auction_repository.h"
#include "economy/collector_command.h"
#include "economy/collector_repository.h"
#include "combat/combat_outcome_command.h"
#include "combat/combat_outcome_repository.h"
#include "guild/artifact_guild_command.h"
#include "guild/artifact_guild_repository.h"
#include "economy/boon_reward_command.h"
#include "economy/boon_reward_repository.h"
#include "world/zone_touch_command.h"
#include "world/zone_touch_repository.h"
#include "account/session_audit_command.h"
#include "account/session_audit_repository.h"
#include "item/item_transfer_repository.h"
#include "sql/sql_pool.h"

#include <algorithm>
#include <array>
#include <cerrno>
#include <climits>
#include <cstdint>
#include <cstring>
#include <strings.h>
#include <limits>
#include <mysql.h>
#include <new>
#include <openssl/sha.h>
#include <vector>
#include <type_traits>

namespace
{
static_assert(BOON_REWARD_RESULT_BYTES <= CRITICAL_COMPLETION_RESULT_MAX_BYTES);
constexpr uint8_t INBOX_COMMITTED = 1;
constexpr uint16_t OUTBOX_DESTINATION_TEST = 1;
constexpr uint16_t OUTBOX_EVENT_TEST_MUTATED = 1;
constexpr uint16_t OUTBOX_DESTINATION_EPIC = 2;
constexpr uint16_t OUTBOX_EVENT_EPIC_BALANCE = 1;
constexpr uint16_t OUTBOX_DESTINATION_ITEM_OWNERSHIP = 4;
constexpr uint16_t OUTBOX_EVENT_ITEM_TRANSFERRED = 1;
constexpr uint16_t OUTBOX_DESTINATION_AUCTION = 5;
constexpr uint16_t OUTBOX_EVENT_AUCTION_MUTATED = 1;
constexpr uint16_t OUTBOX_DESTINATION_COMBAT = 6;
constexpr uint16_t OUTBOX_EVENT_COMBAT_OUTCOME = 1;
constexpr uint16_t OUTBOX_DESTINATION_ARTIFACT_GUILD = 7;
constexpr uint16_t OUTBOX_EVENT_ARTIFACT_GUILD_MUTATED = 1;
constexpr uint16_t OUTBOX_DESTINATION_BOON_REWARD = 8;
constexpr uint16_t OUTBOX_EVENT_BOON_REWARD_MUTATED = 1;
constexpr uint16_t OUTBOX_DESTINATION_ZONE_TOUCH = 9;
constexpr uint16_t OUTBOX_EVENT_ZONE_TOUCH_MUTATED = 1;
thread_local unsigned int last_statement_error = 0;

struct stored_operation
{
	std::array<uint8_t, SHA256_DIGEST_LENGTH> command_hash;
	std::array<uint8_t, SHA256_DIGEST_LENGTH> keys_hash;
	uint16_t command_type;
	uint32_t schema_version;
	uint16_t payload_version;
	uint8_t status;
	uint32_t result_code;
	uint64_t durable_revision;
	std::vector<uint8_t> result_payload;
};

bool connection_error(unsigned int error)
{
	return error == 2006 || error == 2013 || error == 2055;
}

bool retryable_error(unsigned int error)
{
	return connection_error(error) || error == EAGAIN || error == ENOMEM || error == 1205 ||
	       error == 1213;
}

critical_apply_result failure(unsigned int error)
{
	return { retryable_error(error) ? critical_apply_outcome::retryable_failure :
					  critical_apply_outcome::terminal_failure,
		 0, error };
}

critical_apply_result stored_result(critical_apply_outcome outcome, const stored_operation &stored)
{
	critical_apply_result result = { outcome, stored.durable_revision, stored.result_code };
	result.result_size = static_cast<uint16_t>(
		std::min(stored.result_payload.size(), result.result_payload.size()));
	std::copy_n(stored.result_payload.begin(), result.result_size,
		    result.result_payload.begin());
	return result;
}

bool execute(MYSQL *connection, const char *sql)
{
	return mysql_real_query(connection, sql, strlen(sql)) == 0;
}

void rollback(MYSQL *connection)
{
	if (connection && !connection_error(mysql_errno(connection)))
		execute(connection, "ROLLBACK");
}

bool prepare(MYSQL_STMT **statement, MYSQL *connection, const char *sql)
{
	last_statement_error = 0;
	*statement = mysql_stmt_init(connection);
	if (!*statement)
		return false;
	if (mysql_stmt_prepare(*statement, sql, strlen(sql)) != 0)
	{
		last_statement_error = mysql_stmt_errno(*statement);
		mysql_stmt_close(*statement);
		*statement = nullptr;
		return false;
	}
	return true;
}

bool statement_failure(MYSQL_STMT *statement)
{
	if (statement)
	{
		last_statement_error = mysql_stmt_errno(statement);
		mysql_stmt_close(statement);
	}
	return false;
}

unsigned int database_error(MYSQL *connection)
{
	return last_statement_error ? last_statement_error : mysql_errno(connection);
}

std::array<uint8_t, SHA256_DIGEST_LENGTH> hash_bytes(const uint8_t *data, size_t size)
{
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
	SHA256(data, size, digest.data());
	return digest;
}

bool command_hashes(const critical_command &command,
		    std::array<uint8_t, SHA256_DIGEST_LENGTH> *command_hash,
		    std::array<uint8_t, SHA256_DIGEST_LENGTH> *keys_hash)
{
	std::vector<uint8_t> encoded;
	if (!command_hash || !keys_hash ||
	    critical_command_encode(command, &encoded) != critical_command_codec_result::ok)
		return false;
	*command_hash = hash_bytes(encoded.data(), encoded.size());
	std::vector<uint8_t> keys;
	try
	{
		keys.reserve(command.keys.size() * 9);
		for (const critical_entity_key &key : command.keys)
		{
			keys.push_back(static_cast<uint8_t>(key.type));
			for (unsigned int byte = 0; byte < 8; ++byte)
				keys.push_back(static_cast<uint8_t>(key.id >> (byte * 8)));
		}
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
	*keys_hash = hash_bytes(keys.data(), keys.size());
	return true;
}

bool read_operation(MYSQL *connection, const critical_operation_id &operation_id, bool for_update,
		    stored_operation *stored, bool *found)
{
	static const char SELECT_SQL[] =
		"SELECT command_hash,keys_hash,command_type,schema_version,payload_version,status,"
		"result_code,durable_revision,result_payload FROM critical_operation_inbox "
		"WHERE operation_id=?";
	static const char SELECT_LOCK_SQL[] =
		"SELECT command_hash,keys_hash,command_type,schema_version,payload_version,status,"
		"result_code,durable_revision,result_payload FROM critical_operation_inbox "
		"WHERE operation_id=? FOR UPDATE";
	if (!stored || !found)
		return false;
	*found = false;
	MYSQL_STMT *statement = nullptr;
	if (!prepare(&statement, connection, for_update ? SELECT_LOCK_SQL : SELECT_SQL))
		return false;
	unsigned long operation_length = operation_id.bytes.size();
	MYSQL_BIND parameter = {};
	parameter.buffer_type = MYSQL_TYPE_BLOB;
	parameter.buffer = const_cast<uint8_t *>(operation_id.bytes.data());
	parameter.buffer_length = operation_length;
	parameter.length = &operation_length;
	if (mysql_stmt_bind_param(statement, &parameter) != 0 ||
	    mysql_stmt_execute(statement) != 0 || mysql_stmt_store_result(statement) != 0)
		return statement_failure(statement);
	std::array<uint8_t, CRITICAL_COMMAND_RESULT_MAX_BYTES> result_payload = {};
	unsigned long command_hash_length = 0, keys_hash_length = 0, result_length = 0;
	MYSQL_BIND results[9] = {};
	results[0].buffer_type = MYSQL_TYPE_BLOB;
	results[0].buffer = stored->command_hash.data();
	results[0].buffer_length = stored->command_hash.size();
	results[0].length = &command_hash_length;
	results[1].buffer_type = MYSQL_TYPE_BLOB;
	results[1].buffer = stored->keys_hash.data();
	results[1].buffer_length = stored->keys_hash.size();
	results[1].length = &keys_hash_length;
	results[2].buffer_type = MYSQL_TYPE_SHORT;
	results[2].buffer = &stored->command_type;
	results[2].is_unsigned = true;
	results[3].buffer_type = MYSQL_TYPE_LONG;
	results[3].buffer = &stored->schema_version;
	results[3].is_unsigned = true;
	results[4].buffer_type = MYSQL_TYPE_SHORT;
	results[4].buffer = &stored->payload_version;
	results[4].is_unsigned = true;
	results[5].buffer_type = MYSQL_TYPE_TINY;
	results[5].buffer = &stored->status;
	results[5].is_unsigned = true;
	results[6].buffer_type = MYSQL_TYPE_LONG;
	results[6].buffer = &stored->result_code;
	results[6].is_unsigned = true;
	results[7].buffer_type = MYSQL_TYPE_LONGLONG;
	results[7].buffer = &stored->durable_revision;
	results[7].is_unsigned = true;
	results[8].buffer_type = MYSQL_TYPE_BLOB;
	results[8].buffer = result_payload.data();
	results[8].buffer_length = result_payload.size();
	results[8].length = &result_length;
	if (mysql_stmt_bind_result(statement, results) != 0)
		return statement_failure(statement);
	const int fetched = mysql_stmt_fetch(statement);
	if (fetched == MYSQL_NO_DATA)
	{
		mysql_stmt_close(statement);
		return true;
	}
	if (fetched != 0 || command_hash_length != stored->command_hash.size() ||
	    keys_hash_length != stored->keys_hash.size() || result_length > result_payload.size())
		return statement_failure(statement);
	try
	{
		stored->result_payload.assign(result_payload.begin(),
					      result_payload.begin() + result_length);
	}
	catch (const std::bad_alloc &)
	{
		mysql_stmt_close(statement);
		last_statement_error = ENOMEM;
		return false;
	}
	*found = true;
	mysql_stmt_close(statement);
	return true;
}

bool identity_matches(const stored_operation &stored, const critical_command &command,
		      const std::array<uint8_t, SHA256_DIGEST_LENGTH> &command_hash,
		      const std::array<uint8_t, SHA256_DIGEST_LENGTH> &keys_hash)
{
	return stored.command_hash == command_hash && stored.keys_hash == keys_hash &&
	       stored.command_type == static_cast<uint16_t>(command.type) &&
	       stored.schema_version == command.schema_version &&
	       stored.payload_version == command.payload_version;
}

bool insert_inbox(MYSQL *connection, const critical_command &command,
		  const std::array<uint8_t, SHA256_DIGEST_LENGTH> &command_hash,
		  const std::array<uint8_t, SHA256_DIGEST_LENGTH> &keys_hash)
{
	static const char SQL[] =
		"INSERT INTO critical_operation_inbox(operation_id,command_hash,keys_hash,"
		"command_type,schema_version,payload_version,status,result_payload) "
		"VALUES(?,?,?,?,?,?,0,'')";
	MYSQL_STMT *statement = nullptr;
	if (!prepare(&statement, connection, SQL))
		return false;
	uint16_t type = static_cast<uint16_t>(command.type);
	uint32_t schema = command.schema_version;
	uint16_t payload_version = command.payload_version;
	unsigned long lengths[3] = { command.operation_id.bytes.size(), command_hash.size(),
				     keys_hash.size() };
	MYSQL_BIND bindings[6] = {};
	for (unsigned int index = 0; index < 3; ++index)
	{
		bindings[index].buffer_type = MYSQL_TYPE_BLOB;
		bindings[index].length = &lengths[index];
	}
	bindings[0].buffer = const_cast<uint8_t *>(command.operation_id.bytes.data());
	bindings[0].buffer_length = lengths[0];
	bindings[1].buffer = const_cast<uint8_t *>(command_hash.data());
	bindings[1].buffer_length = lengths[1];
	bindings[2].buffer = const_cast<uint8_t *>(keys_hash.data());
	bindings[2].buffer_length = lengths[2];
	bindings[3].buffer_type = MYSQL_TYPE_SHORT;
	bindings[3].buffer = &type;
	bindings[3].is_unsigned = true;
	bindings[4].buffer_type = MYSQL_TYPE_LONG;
	bindings[4].buffer = &schema;
	bindings[4].is_unsigned = true;
	bindings[5].buffer_type = MYSQL_TYPE_SHORT;
	bindings[5].buffer = &payload_version;
	bindings[5].is_unsigned = true;
	const bool ok = mysql_stmt_bind_param(statement, bindings) == 0 &&
			mysql_stmt_execute(statement) == 0;
	if (!ok)
		last_statement_error = mysql_stmt_errno(statement);
	mysql_stmt_close(statement);
	return ok;
}

bool execute_entity(MYSQL *connection, const critical_entity_key &key, int64_t delta,
		    int64_t *value, uint64_t *revision)
{
	static const char ENSURE_SQL[] =
		"INSERT IGNORE INTO critical_test_state(entity_type,entity_id) VALUES(?,?)";
	static const char LOCK_SQL[] =
		"SELECT value,revision FROM critical_test_state WHERE entity_type=? AND entity_id=? "
		"FOR UPDATE";
	static const char UPDATE_SQL[] =
		"UPDATE critical_test_state SET value=?,revision=? WHERE entity_type=? AND entity_id=?";
	uint8_t type = static_cast<uint8_t>(key.type);
	uint64_t id = key.id;
	MYSQL_BIND key_bindings[2] = {};
	key_bindings[0].buffer_type = MYSQL_TYPE_TINY;
	key_bindings[0].buffer = &type;
	key_bindings[0].is_unsigned = true;
	key_bindings[1].buffer_type = MYSQL_TYPE_LONGLONG;
	key_bindings[1].buffer = &id;
	key_bindings[1].is_unsigned = true;
	MYSQL_STMT *statement = nullptr;
	if (!prepare(&statement, connection, ENSURE_SQL) ||
	    mysql_stmt_bind_param(statement, key_bindings) != 0 ||
	    mysql_stmt_execute(statement) != 0)
	{
		return statement_failure(statement);
	}
	mysql_stmt_close(statement);
	if (!prepare(&statement, connection, LOCK_SQL) ||
	    mysql_stmt_bind_param(statement, key_bindings) != 0 ||
	    mysql_stmt_execute(statement) != 0 || mysql_stmt_store_result(statement) != 0)
	{
		return statement_failure(statement);
	}
	MYSQL_BIND results[2] = {};
	results[0].buffer_type = MYSQL_TYPE_LONGLONG;
	results[0].buffer = value;
	results[1].buffer_type = MYSQL_TYPE_LONGLONG;
	results[1].buffer = revision;
	results[1].is_unsigned = true;
	const bool read = mysql_stmt_bind_result(statement, results) == 0 &&
			  mysql_stmt_fetch(statement) == 0;
	if (!read)
		last_statement_error = mysql_stmt_errno(statement);
	mysql_stmt_close(statement);
	if (!read)
		return false;
	if ((delta > 0 && *value > std::numeric_limits<int64_t>::max() - delta) ||
	    (delta < 0 && *value < std::numeric_limits<int64_t>::min() - delta) ||
	    *revision == std::numeric_limits<uint64_t>::max())
	{
		errno = ERANGE;
		return false;
	}
	*value += delta;
	++*revision;
	MYSQL_BIND update[4] = {};
	update[0].buffer_type = MYSQL_TYPE_LONGLONG;
	update[0].buffer = value;
	update[1].buffer_type = MYSQL_TYPE_LONGLONG;
	update[1].buffer = revision;
	update[1].is_unsigned = true;
	update[2] = key_bindings[0];
	update[3] = key_bindings[1];
	if (!prepare(&statement, connection, UPDATE_SQL) ||
	    mysql_stmt_bind_param(statement, update) != 0 || mysql_stmt_execute(statement) != 0 ||
	    mysql_stmt_affected_rows(statement) != 1)
	{
		return statement_failure(statement);
	}
	mysql_stmt_close(statement);
	return true;
}

void encode_u64(std::array<uint8_t, 16> *output, size_t offset, uint64_t value)
{
	for (unsigned int byte = 0; byte < 8; ++byte)
		(*output)[offset + byte] = static_cast<uint8_t>(value >> (byte * 8));
}

bool insert_outbox_event(MYSQL *connection, const critical_operation_id &operation_id,
			 uint16_t event_index, uint16_t destination, uint16_t event_type,
			 uint16_t payload_version, const uint8_t *payload, size_t payload_size)
{
	static const char SQL[] =
		"INSERT INTO critical_outbox(operation_id,event_index,destination,event_type,"
		"payload_version,payload) VALUES(?,?,?,?,?,?)";
	if (!event_type || !payload_version || (!payload && payload_size))
	{
		errno = EINVAL;
		return false;
	}
	MYSQL_STMT *statement = nullptr;
	if (!prepare(&statement, connection, SQL))
		return false;
	unsigned long operation_length = operation_id.bytes.size(), payload_length = payload_size;
	MYSQL_BIND bindings[6] = {};
	bindings[0].buffer_type = MYSQL_TYPE_BLOB;
	bindings[0].buffer = const_cast<uint8_t *>(operation_id.bytes.data());
	bindings[0].buffer_length = operation_length;
	bindings[0].length = &operation_length;
	bindings[1].buffer_type = MYSQL_TYPE_SHORT;
	bindings[1].buffer = &event_index;
	bindings[1].is_unsigned = true;
	bindings[2].buffer_type = MYSQL_TYPE_SHORT;
	bindings[2].buffer = &destination;
	bindings[2].is_unsigned = true;
	bindings[3].buffer_type = MYSQL_TYPE_SHORT;
	bindings[3].buffer = &event_type;
	bindings[3].is_unsigned = true;
	bindings[4].buffer_type = MYSQL_TYPE_SHORT;
	bindings[4].buffer = &payload_version;
	bindings[4].is_unsigned = true;
	bindings[5].buffer_type = MYSQL_TYPE_BLOB;
	bindings[5].buffer = const_cast<uint8_t *>(payload);
	bindings[5].buffer_length = payload_length;
	bindings[5].length = &payload_length;
	const bool ok = mysql_stmt_bind_param(statement, bindings) == 0 &&
			mysql_stmt_execute(statement) == 0;
	if (!ok)
		last_statement_error = mysql_stmt_errno(statement);
	mysql_stmt_close(statement);
	return ok;
}

bool insert_outbox(MYSQL *connection, const critical_command &command, const uint8_t *payload,
		   size_t payload_size)
{
	uint16_t destination = OUTBOX_DESTINATION_TEST;
	uint16_t event_type = OUTBOX_EVENT_TEST_MUTATED;
	uint16_t payload_version = 1;
	if (command.type == critical_command_type::epic)
	{
		destination = OUTBOX_DESTINATION_EPIC;
		event_type = OUTBOX_EVENT_EPIC_BALANCE;
	}
	else if (command.type == critical_command_type::item_transfer)
	{
		destination = OUTBOX_DESTINATION_ITEM_OWNERSHIP;
		event_type = OUTBOX_EVENT_ITEM_TRANSFERRED;
	}
	else if (command.type == critical_command_type::auction)
	{
		destination = OUTBOX_DESTINATION_AUCTION;
		event_type = OUTBOX_EVENT_AUCTION_MUTATED;
	}
	else if (command.type == critical_command_type::combat_outcome)
	{
		destination = OUTBOX_DESTINATION_COMBAT;
		event_type = OUTBOX_EVENT_COMBAT_OUTCOME;
	}
	else if (command.type == critical_command_type::artifact)
	{
		destination = OUTBOX_DESTINATION_ARTIFACT_GUILD;
		event_type = OUTBOX_EVENT_ARTIFACT_GUILD_MUTATED;
	}
	else if (command.type == critical_command_type::boon_reward)
	{
		destination = OUTBOX_DESTINATION_BOON_REWARD;
		event_type = OUTBOX_EVENT_BOON_REWARD_MUTATED;
	}
	else if (command.type == critical_command_type::zone)
	{
		destination = OUTBOX_DESTINATION_ZONE_TOUCH;
		event_type = OUTBOX_EVENT_ZONE_TOUCH_MUTATED;
	}
	else if (command.type == critical_command_type::collector)
	{
		destination = COLLECTOR_OUTBOX_DESTINATION;
		event_type = COLLECTOR_OUTBOX_EVENT_MUTATED;
		payload_version = COLLECTOR_COMMAND_RESULT_VERSION;
	}
	return insert_outbox_event(connection, command.operation_id, 0, destination, event_type,
				   payload_version, payload, payload_size);
}

bool finish_inbox(MYSQL *connection, const critical_command &command, uint64_t revision,
		  unsigned int result_code, const uint8_t *payload, size_t payload_size)
{
	static const char SQL[] =
		"UPDATE critical_operation_inbox SET status=1,result_code=?,durable_revision=?,"
		"result_payload=?,committed_at=CURRENT_TIMESTAMP(6) WHERE operation_id=? AND status=0";
	MYSQL_STMT *statement = nullptr;
	if (!prepare(&statement, connection, SQL))
		return false;
	unsigned long payload_length = payload_size,
		      operation_length = command.operation_id.bytes.size();
	MYSQL_BIND bindings[4] = {};
	bindings[0].buffer_type = MYSQL_TYPE_LONG;
	bindings[0].buffer = &result_code;
	bindings[0].is_unsigned = true;
	bindings[1].buffer_type = MYSQL_TYPE_LONGLONG;
	bindings[1].buffer = &revision;
	bindings[1].is_unsigned = true;
	bindings[2].buffer_type = MYSQL_TYPE_BLOB;
	bindings[2].buffer = const_cast<uint8_t *>(payload);
	bindings[2].buffer_length = payload_length;
	bindings[2].length = &payload_length;
	bindings[3].buffer_type = MYSQL_TYPE_BLOB;
	bindings[3].buffer = const_cast<uint8_t *>(command.operation_id.bytes.data());
	bindings[3].buffer_length = operation_length;
	bindings[3].length = &operation_length;
	const bool ok = mysql_stmt_bind_param(statement, bindings) == 0 &&
			mysql_stmt_execute(statement) == 0 &&
			mysql_stmt_affected_rows(statement) == 1;
	if (!ok)
		last_statement_error = mysql_stmt_errno(statement);
	mysql_stmt_close(statement);
	return ok;
}

bool execute_epic_state(MYSQL *connection, const critical_command &command,
			epic_command_result *result, unsigned int *result_code,
			bool *mutation_applied)
{
	static const char BASELINE_SQL[] =
		"INSERT IGNORE INTO epic_balance_baseline(pid,opening_balance,opening_revision) "
		"SELECT pid,epics,epic_revision FROM player_data WHERE pid=?";
	// The balance is memory's and the player's save writes it: the command only records
	// the change, continuing the ledger from its last row (or from the saved balance
	// when the player has none), and advances the revision the rows are keyed on.
	static const char LOCK_SQL[] =
		"SELECT epics,epic_revision FROM player_data WHERE pid=? FOR UPDATE";
	static const char TAIL_SQL[] =
		"SELECT balance_after FROM epic_ledger WHERE pid=? AND epic_revision=?";
	static const char UPDATE_SQL[] =
		"UPDATE player_data SET epic_revision=? WHERE pid=? AND epic_revision=?";
	static const char LEDGER_SQL[] =
		"INSERT INTO epic_ledger(operation_id,pid,delta,balance_after,epic_revision,"
		"reason_type,reason_id,source_site) VALUES(?,?,?,?,?,?,?,?)";
	if (!result || !result_code || !mutation_applied)
		return false;
	epic_command_payload payload = {};
	if (!epic_command_decode_payload(command, &payload))
	{
		errno = EINVAL;
		return false;
	}
	uint32_t pid = payload.pid;
	MYSQL_BIND pid_binding = {};
	pid_binding.buffer_type = MYSQL_TYPE_LONG;
	pid_binding.buffer = &pid;
	pid_binding.is_unsigned = true;
	MYSQL_STMT *statement = nullptr;
	if (!prepare(&statement, connection, BASELINE_SQL) ||
	    mysql_stmt_bind_param(statement, &pid_binding) != 0 ||
	    mysql_stmt_execute(statement) != 0)
		return statement_failure(statement);
	mysql_stmt_close(statement);
	if (!prepare(&statement, connection, LOCK_SQL) ||
	    mysql_stmt_bind_param(statement, &pid_binding) != 0 ||
	    mysql_stmt_execute(statement) != 0 || mysql_stmt_store_result(statement) != 0)
		return statement_failure(statement);
	int64_t balance = 0;
	uint64_t revision = 0;
	MYSQL_BIND state[2] = {};
	state[0].buffer_type = MYSQL_TYPE_LONGLONG;
	state[0].buffer = &balance;
	state[1].buffer_type = MYSQL_TYPE_LONGLONG;
	state[1].buffer = &revision;
	state[1].is_unsigned = true;
	const bool found = mysql_stmt_bind_result(statement, state) == 0 &&
			   mysql_stmt_fetch(statement) == 0;
	if (!found)
		last_statement_error = mysql_stmt_errno(statement) ? mysql_stmt_errno(statement) :
								     ENOENT;
	mysql_stmt_close(statement);
	if (!found)
		return false;
	MYSQL_BIND tail_key[2] = {};
	tail_key[0] = pid_binding;
	tail_key[1] = state[1];
	MYSQL_BIND tail = {};
	tail.buffer_type = MYSQL_TYPE_LONGLONG;
	tail.buffer = &balance;
	if (!prepare(&statement, connection, TAIL_SQL) ||
	    mysql_stmt_bind_param(statement, tail_key) != 0 || mysql_stmt_execute(statement) != 0 ||
	    mysql_stmt_store_result(statement) != 0 ||
	    mysql_stmt_bind_result(statement, &tail) != 0 || mysql_stmt_fetch(statement) == 1)
		return statement_failure(statement);
	mysql_stmt_close(statement);
	*result = { .balance = balance, .revision = revision, .delta = payload.delta };
	if ((payload.delta > 0 && balance > std::numeric_limits<int64_t>::max() - payload.delta) ||
	    (payload.delta < 0 && balance < std::numeric_limits<int64_t>::min() - payload.delta) ||
	    revision == std::numeric_limits<uint64_t>::max())
	{
		*result_code = ERANGE;
		*mutation_applied = false;
		return true;
	}
	uint64_t prior_revision = revision;
	balance += payload.delta;
	++revision;
	MYSQL_BIND update[3] = {};
	update[0].buffer_type = MYSQL_TYPE_LONGLONG;
	update[0].buffer = &revision;
	update[0].is_unsigned = true;
	update[1] = pid_binding;
	update[2].buffer_type = MYSQL_TYPE_LONGLONG;
	update[2].buffer = &prior_revision;
	update[2].is_unsigned = true;
	if (!prepare(&statement, connection, UPDATE_SQL) ||
	    mysql_stmt_bind_param(statement, update) != 0 || mysql_stmt_execute(statement) != 0 ||
	    mysql_stmt_affected_rows(statement) != 1)
		return statement_failure(statement);
	mysql_stmt_close(statement);
	uint16_t reason = static_cast<uint16_t>(payload.reason);
	uint16_t source = static_cast<uint16_t>(command.source_site);
	unsigned long operation_length = command.operation_id.bytes.size();
	MYSQL_BIND ledger[8] = {};
	ledger[0].buffer_type = MYSQL_TYPE_BLOB;
	ledger[0].buffer = const_cast<uint8_t *>(command.operation_id.bytes.data());
	ledger[0].buffer_length = operation_length;
	ledger[0].length = &operation_length;
	ledger[1] = pid_binding;
	ledger[2].buffer_type = MYSQL_TYPE_LONGLONG;
	ledger[2].buffer = &payload.delta;
	ledger[3].buffer_type = MYSQL_TYPE_LONGLONG;
	ledger[3].buffer = &balance;
	ledger[4].buffer_type = MYSQL_TYPE_LONGLONG;
	ledger[4].buffer = &revision;
	ledger[4].is_unsigned = true;
	ledger[5].buffer_type = MYSQL_TYPE_SHORT;
	ledger[5].buffer = &reason;
	ledger[5].is_unsigned = true;
	ledger[6].buffer_type = MYSQL_TYPE_LONGLONG;
	ledger[6].buffer = &payload.reason_id;
	ledger[7].buffer_type = MYSQL_TYPE_SHORT;
	ledger[7].buffer = &source;
	ledger[7].is_unsigned = true;
	if (!prepare(&statement, connection, LEDGER_SQL) ||
	    mysql_stmt_bind_param(statement, ledger) != 0 || mysql_stmt_execute(statement) != 0)
		return statement_failure(statement);
	mysql_stmt_close(statement);
	*result = { .balance = balance, .revision = revision, .delta = payload.delta };
	*result_code = 0;
	*mutation_applied = true;
	return true;
}

} // namespace

critical_apply_result critical_command_repository_apply(MYSQL *connection,
							const critical_command &command)
{
	last_statement_error = 0;
	epic_command_payload epic_payload = {};
	item_transfer_payload item_payload = {};
	auction_command_payload auction_payload = {};
	collector_command_payload collector_payload = {};
	combat_outcome_payload combat_payload = {};
	artifact_guild_payload artifact_payload = {};
	boon_reward_payload boon_payload = {};
	zone_touch_payload zone_payload = {};
	session_audit_payload audit_payload = {};
	const bool test_command = command.type == critical_command_type::test &&
				  command.payload.size() == 8;
	const bool epic_command = epic_command_decode_payload(command, &epic_payload);
	const bool item_command = item_transfer_command_decode_payload(command, &item_payload);
	const bool auction_command = auction_command_decode_payload(command, &auction_payload);
	const bool collector_command =
		collector_command_decode_payload(command, &collector_payload);
	const bool combat_command = combat_outcome_command_decode_payload(command, &combat_payload);
	const bool artifact_guild_command =
		artifact_guild_command_decode_payload(command, &artifact_payload);
	const bool boon_command = boon_reward_command_decode_payload(command, &boon_payload);
	const bool zone_command = zone_touch_command_decode_payload(command, &zone_payload);
	const bool audit_command = session_audit_command_decode_payload(command, &audit_payload);
	if (!connection ||
	    (!test_command && !epic_command && !item_command && !auction_command &&
	     !collector_command && !combat_command && !artifact_guild_command && !boon_command &&
	     !zone_command && !audit_command) ||
	    !critical_command_valid(command))
		return { critical_apply_outcome::terminal_failure, 0, EINVAL };
	std::array<uint8_t, SHA256_DIGEST_LENGTH> command_hash = {}, keys_hash = {};
	if (!command_hashes(command, &command_hash, &keys_hash))
		return { critical_apply_outcome::retryable_failure, 0, ENOMEM };
	if (!execute(connection, "START TRANSACTION"))
		return failure(mysql_errno(connection));
	if (!insert_inbox(connection, command, command_hash, keys_hash))
	{
		const unsigned int error = database_error(connection);
		if (error == 1062)
		{
			stored_operation stored = {};
			bool found = false;
			if (!read_operation(connection, command.operation_id, true, &stored,
					    &found))
			{
				const unsigned int read_error = database_error(connection);
				rollback(connection);
				return failure(read_error);
			}
			if (!found || stored.status != INBOX_COMMITTED)
			{
				rollback(connection);
				return { critical_apply_outcome::retryable_failure, 0, EAGAIN };
			}
			if (!identity_matches(stored, command, command_hash, keys_hash))
			{
				rollback(connection);
				return { critical_apply_outcome::terminal_failure, 0, EEXIST };
			}
			rollback(connection);
			return stored_result(stored.result_code ?
						     critical_apply_outcome::terminal_failure :
						     critical_apply_outcome::already_applied,
					     stored);
		}
		rollback(connection);
		return failure(error);
	}
	if (epic_command)
	{
		epic_command_result epic_result = {};
		unsigned int result_code = 0;
		bool mutation_applied = false;
		if (!execute_epic_state(connection, command, &epic_result, &result_code,
					&mutation_applied))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		std::array<uint8_t, EPIC_RESULT_PAYLOAD_BYTES> result_payload = {};
		if (!epic_command_encode_result(epic_result, &result_payload) ||
		    (mutation_applied && !insert_outbox(connection, command, result_payload.data(),
							result_payload.size())) ||
		    !finish_inbox(connection, command, epic_result.revision, result_code,
				  result_payload.data(), result_payload.size()))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		if (!execute(connection, "COMMIT"))
		{
			const unsigned int error = mysql_errno(connection);
			if (!connection_error(error))
				rollback(connection);
			return { connection_error(error) ?
					 critical_apply_outcome::ambiguous_commit :
					 failure(error).outcome,
				 epic_result.revision, error };
		}
		critical_apply_result applied = { result_code ?
							  critical_apply_outcome::terminal_failure :
							  critical_apply_outcome::applied,
						  epic_result.revision, result_code };
		applied.result_size = result_payload.size();
		std::copy(result_payload.begin(), result_payload.end(),
			  applied.result_payload.begin());
		return applied;
	}
	if (item_command)
	{
		collector_item_boundary_repository_plan boundary;
		item_transfer_result item_result = {
			item_transfer_result_root(item_payload), item_payload.item_count, 0, 0, 0, 0
		};
		std::vector<collector_command_result> collector_events;
		uint64_t collector_revision = 0;
		unsigned int result_code = 0;
		bool mutation_applied = false;
		bool repository_ok = collector_repository_prepare_item_boundary(
			connection, item_payload, &boundary, &result_code);
		if (repository_ok && !result_code)
			repository_ok = item_transfer_repository_execute(
				connection, command, &item_result, &result_code, &mutation_applied);
		if (repository_ok && !result_code && mutation_applied && !boundary.entries.empty())
		{
			repository_ok = collector_repository_apply_item_boundary(
				connection, command, boundary, &collector_revision,
				&collector_events);
			item_result.collector_catalog_changed = repository_ok;
		}
		if (!repository_ok)
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		std::array<uint8_t, ITEM_TRANSFER_RESULT_BYTES> result_payload = {};
		uint64_t durable_revision =
			std::max({ item_result.from_owner_revision, item_result.to_owner_revision,
				   item_result.max_item_revision });
		durable_revision = std::max(durable_revision, collector_revision);
		bool outbox_ok = item_transfer_command_encode_result(item_result, &result_payload);
		if (outbox_ok && mutation_applied)
			outbox_ok = insert_outbox(connection, command, result_payload.data(),
						  result_payload.size());
		for (size_t index = 0; outbox_ok && index < collector_events.size(); ++index)
		{
			std::array<uint8_t, COLLECTOR_COMMAND_RESULT_BYTES> encoded = {};
			outbox_ok = collector_command_encode_result(collector_events[index],
								    &encoded) &&
				    insert_outbox_event(connection, command.operation_id,
							static_cast<uint16_t>(index + 1),
							COLLECTOR_OUTBOX_DESTINATION,
							COLLECTOR_OUTBOX_EVENT_MUTATED,
							COLLECTOR_COMMAND_RESULT_VERSION,
							encoded.data(), encoded.size());
		}
		if (!outbox_ok || !finish_inbox(connection, command, durable_revision, result_code,
						result_payload.data(), result_payload.size()))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		if (!execute(connection, "COMMIT"))
		{
			const unsigned int error = mysql_errno(connection);
			if (!connection_error(error))
				rollback(connection);
			return { connection_error(error) ?
					 critical_apply_outcome::ambiguous_commit :
					 failure(error).outcome,
				 durable_revision, error };
		}
		critical_apply_result applied = { result_code ?
							  critical_apply_outcome::terminal_failure :
							  critical_apply_outcome::applied,
						  durable_revision, result_code };
		applied.result_size = result_payload.size();
		std::copy(result_payload.begin(), result_payload.end(),
			  applied.result_payload.begin());
		return applied;
	}
	if (auction_command)
	{
		auction_command_result auction_result = {};
		unsigned int result_code = 0;
		bool mutation_applied = false;
		if (!auction_repository_execute(connection, command, &auction_result, &result_code,
						&mutation_applied))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		std::array<uint8_t, AUCTION_RESULT_PAYLOAD_BYTES> result_payload = {};
		const uint64_t durable_revision = std::max(
			{ auction_result.auction_revision, auction_result.wallet_revision,
			  auction_result.bank_revision, auction_result.player_owner_revision,
			  auction_result.auction_owner_revision });
		if (!auction_command_encode_result(auction_result, &result_payload) ||
		    (mutation_applied && !insert_outbox(connection, command, result_payload.data(),
							result_payload.size())) ||
		    !finish_inbox(connection, command, durable_revision, result_code,
				  result_payload.data(), result_payload.size()))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		if (!execute(connection, "COMMIT"))
		{
			const unsigned int error = mysql_errno(connection);
			if (!connection_error(error))
				rollback(connection);
			return { connection_error(error) ?
					 critical_apply_outcome::ambiguous_commit :
					 failure(error).outcome,
				 durable_revision, error };
		}
		critical_apply_result applied = { result_code ?
							  critical_apply_outcome::terminal_failure :
							  critical_apply_outcome::applied,
						  durable_revision, result_code };
		applied.result_size = result_payload.size();
		std::copy(result_payload.begin(), result_payload.end(),
			  applied.result_payload.begin());
		return applied;
	}
	if (collector_command)
	{
		collector_command_result collector_result = {};
		unsigned int result_code = 0;
		bool mutation_applied = false;
		if (!collector_repository_execute(connection, command, &collector_result,
						  &result_code, &mutation_applied))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		std::array<uint8_t, COLLECTOR_COMMAND_RESULT_BYTES> result_payload = {};
		const uint64_t durable_revision = std::max(
			{ collector_result.catalog_revision, collector_result.from_owner_revision,
			  collector_result.to_owner_revision, collector_result.wallet_revision,
			  collector_result.bank_revision,
			  collector_result.record_present ? collector_result.entry.item_revision :
							    0 });
		if (!collector_command_encode_result(collector_result, &result_payload) ||
		    (mutation_applied && !insert_outbox(connection, command, result_payload.data(),
							result_payload.size())) ||
		    !finish_inbox(connection, command, durable_revision, result_code,
				  result_payload.data(), result_payload.size()))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		if (!execute(connection, "COMMIT"))
		{
			const unsigned int error = mysql_errno(connection);
			if (!connection_error(error))
				rollback(connection);
			return { connection_error(error) ?
					 critical_apply_outcome::ambiguous_commit :
					 failure(error).outcome,
				 durable_revision, error };
		}
		critical_apply_result applied = { result_code ?
							  critical_apply_outcome::terminal_failure :
							  critical_apply_outcome::applied,
						  durable_revision, result_code };
		applied.result_size = result_payload.size();
		std::copy(result_payload.begin(), result_payload.end(),
			  applied.result_payload.begin());
		return applied;
	}
	if (combat_command)
	{
		combat_outcome_result combat_result = {};
		unsigned int result_code = 0;
		bool mutation_applied = false;
		if (!combat_outcome_repository_execute(connection, command, &combat_result,
						       &result_code, &mutation_applied))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		std::array<uint8_t, COMBAT_OUTCOME_RESULT_BYTES> result_payload = {};
		uint64_t durable_revision = 0;
		for (size_t index = 0; index < combat_result.participant_count; ++index)
			durable_revision = std::max(
				durable_revision,
				std::max({ combat_result.participants[index].frag_revision,
					   combat_result.participants[index].epic_revision,
					   combat_result.participants[index].wallet_revision,
					   combat_result.participants[index].bank_revision }));
		if (!combat_outcome_command_encode_result(combat_result, &result_payload) ||
		    (mutation_applied && !insert_outbox(connection, command, result_payload.data(),
							result_payload.size())) ||
		    !finish_inbox(connection, command, durable_revision, result_code,
				  result_payload.data(), result_payload.size()))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		if (!execute(connection, "COMMIT"))
		{
			const unsigned int error = mysql_errno(connection);
			if (!connection_error(error))
				rollback(connection);
			return { connection_error(error) ?
					 critical_apply_outcome::ambiguous_commit :
					 failure(error).outcome,
				 durable_revision, error };
		}
		critical_apply_result applied = { result_code ?
							  critical_apply_outcome::terminal_failure :
							  critical_apply_outcome::applied,
						  durable_revision, result_code };
		applied.result_size = result_payload.size();
		std::copy(result_payload.begin(), result_payload.end(),
			  applied.result_payload.begin());
		return applied;
	}
	if (artifact_guild_command)
	{
		artifact_guild_result outcome_result = {};
		unsigned int result_code = 0;
		bool mutation_applied = false;
		if (!artifact_guild_repository_execute(connection, command, &outcome_result,
						       &result_code, &mutation_applied))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		std::array<uint8_t, ARTIFACT_GUILD_RESULT_BYTES> result_payload = {};
		uint64_t durable_revision = outcome_result.guild_revision;
		for (size_t index = 0; index < outcome_result.artifact_count; ++index)
			durable_revision = std::max(durable_revision,
						    outcome_result.artifacts[index].revision);
		if (!artifact_guild_command_encode_result(outcome_result, &result_payload) ||
		    (mutation_applied && !insert_outbox(connection, command, result_payload.data(),
							result_payload.size())) ||
		    !finish_inbox(connection, command, durable_revision, result_code,
				  result_payload.data(), result_payload.size()))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		if (!execute(connection, "COMMIT"))
		{
			const unsigned int error = mysql_errno(connection);
			if (!connection_error(error))
				rollback(connection);
			return { connection_error(error) ?
					 critical_apply_outcome::ambiguous_commit :
					 failure(error).outcome,
				 durable_revision, error };
		}
		critical_apply_result applied = { result_code ?
							  critical_apply_outcome::terminal_failure :
							  critical_apply_outcome::applied,
						  durable_revision, result_code };
		applied.result_size = result_payload.size();
		std::copy(result_payload.begin(), result_payload.end(),
			  applied.result_payload.begin());
		return applied;
	}
	if (boon_command)
	{
		boon_reward_result boon_result = {};
		unsigned int result_code = 0;
		bool mutation_applied = false;
		if (!boon_reward_repository_execute(connection, command, &boon_result, &result_code,
						    &mutation_applied))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		std::array<uint8_t, BOON_REWARD_RESULT_BYTES> result_payload = {};
		if (!boon_reward_command_encode_result(boon_result, &result_payload) ||
		    (mutation_applied && !insert_outbox(connection, command, result_payload.data(),
							result_payload.size())) ||
		    !finish_inbox(connection, command, 0, result_code, result_payload.data(),
				  result_payload.size()))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		if (!execute(connection, "COMMIT"))
		{
			const unsigned int error = mysql_errno(connection);
			if (!connection_error(error))
				rollback(connection);
			return { connection_error(error) ?
					 critical_apply_outcome::ambiguous_commit :
					 failure(error).outcome,
				 0, error };
		}
		critical_apply_result applied = { result_code ?
							  critical_apply_outcome::terminal_failure :
							  critical_apply_outcome::applied,
						  0, result_code };
		applied.result_size = result_payload.size();
		std::copy(result_payload.begin(), result_payload.end(),
			  applied.result_payload.begin());
		return applied;
	}
	if (zone_command)
	{
		zone_touch_result zone_result = {};
		unsigned int result_code = 0;
		bool mutation_applied = false;
		static_cast<zone_touch_payload &>(zone_result) = zone_payload;
		if (zone_payload.stone_uid)
		{
			// The claim, every child ledger, and zone history share this transaction.
			// Re-touching a surviving object after a lost callback recovers its receipt.
			if (!execute(connection, "SAVEPOINT stone_awards"))
			{
				const auto error = database_error(connection);
				rollback(connection);
				return failure(error);
			}
			const std::string claim_query =
				"SELECT i.result_payload FROM epic_stone_claim c JOIN critical_operation_inbox i "
				"ON i.operation_id=c.operation_id WHERE c.stone_uid=" +
				std::to_string(zone_payload.stone_uid) + " FOR UPDATE";
			if (!execute(connection, claim_query.c_str()))
			{
				const auto error = database_error(connection);
				rollback(connection);
				return failure(error);
			}
			MYSQL_RES *claims = mysql_store_result(connection);
			MYSQL_ROW claim = claims ? mysql_fetch_row(claims) : nullptr;
			bool recovered = false;
			if (claim)
			{
				unsigned long *lengths = mysql_fetch_lengths(claims);
				recovered = lengths &&
					    zone_touch_command_decode_result(
						    reinterpret_cast<const uint8_t *>(claim[0]),
						    lengths[0], &zone_result) &&
					    zone_result.stone_uid == zone_payload.stone_uid;
				if (!recovered)
					result_code = EBADMSG;
				zone_result.recovered_claim = recovered;
			}
			if (claims)
				mysql_free_result(claims);
			if (!claims)
			{
				const auto error = database_error(connection);
				rollback(connection);
				return failure(error ? error : EIO);
			}
			if (!recovered && !result_code)
			{
				char parent_hex[CRITICAL_COMMAND_ID_HEX_SIZE] = {};
				critical_operation_id_to_hex(command.operation_id, parent_hex,
							     sizeof(parent_hex));
				const std::string claim_insert =
					"INSERT INTO epic_stone_claim(stone_uid,operation_id) VALUES(" +
					std::to_string(zone_payload.stone_uid) + ",UNHEX('" +
					parent_hex + "'))";
				if (!execute(connection, claim_insert.c_str()))
				{
					const auto error = database_error(connection);
					rollback(connection);
					return failure(error);
				}
				// Lock players in canonical order, irrespective of group ordering.
				std::vector<size_t> order;
				for (size_t i = 0; i < zone_payload.group_size; ++i)
					order.push_back(i);
				std::sort(order.begin(), order.end(),
					  [&](size_t a, size_t b) {
						  return zone_payload.participant_pids[a] <
							 zone_payload.participant_pids[b];
					  });
				for (size_t i : order)
				{
					critical_command child = {};
					std::array<uint8_t, SHA256_DIGEST_LENGTH>
						child_hash = {},
						child_keys_hash = {};
					epic_command_result award_result = {};
					bool mutated = false;
					if (!zone_touch_award_command(command, i, &child) ||
					    !command_hashes(child, &child_hash, &child_keys_hash) ||
					    !insert_inbox(connection, child, child_hash,
							  child_keys_hash) ||
					    !execute_epic_state(connection, child, &award_result,
								&result_code, &mutated))
					{
						const auto db_error = database_error(connection);
						const auto error = db_error ? db_error : errno;
						rollback(connection);
						return failure(error ? error : EIO);
					}
					if (result_code)
						break;
					std::array<uint8_t, EPIC_RESULT_PAYLOAD_BYTES>
						award_bytes = {};
					if (!mutated ||
					    !epic_command_encode_result(award_result,
									&award_bytes) ||
					    !insert_outbox(connection, child, award_bytes.data(),
							   award_bytes.size()) ||
					    !finish_inbox(connection, child, award_result.revision,
							  0, award_bytes.data(),
							  award_bytes.size()))
					{
						const auto error = database_error(connection);
						rollback(connection);
						return failure(error ? error : EIO);
					}
					zone_result.balances[i] = award_result.balance;
					zone_result.revisions[i] = award_result.revision;
				}
			}
			if (result_code)
			{
				if (!execute(connection, "ROLLBACK TO SAVEPOINT stone_awards"))
				{
					const auto error = database_error(connection);
					rollback(connection);
					return failure(error);
				}
				zone_result = zone_touch_result(zone_payload);
			}
		}
		if (!result_code && !zone_result.recovered_claim && zone_payload.record_zone &&
		    !zone_touch_repository_execute(connection, command, &zone_result, &result_code,
						   &mutation_applied))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		if (zone_payload.stone_uid && !result_code)
			mutation_applied =
				true; // Successful recovery also needs its own receipt outbox.
		std::array<uint8_t, ZONE_TOUCH_RESULT_BYTES> result_payload = {};
		if (!zone_touch_command_encode_result(zone_result, &result_payload) ||
		    (mutation_applied && !insert_outbox(connection, command, result_payload.data(),
							result_payload.size())) ||
		    !finish_inbox(connection, command, 0, result_code, result_payload.data(),
				  result_payload.size()))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		if (!execute(connection, "COMMIT"))
		{
			const unsigned int error = mysql_errno(connection);
			if (!connection_error(error))
				rollback(connection);
			return { connection_error(error) ?
					 critical_apply_outcome::ambiguous_commit :
					 failure(error).outcome,
				 0, error };
		}
		critical_apply_result applied = { result_code ?
							  critical_apply_outcome::terminal_failure :
							  critical_apply_outcome::applied,
						  0, result_code };
		applied.result_size = result_payload.size();
		std::copy(result_payload.begin(), result_payload.end(),
			  applied.result_payload.begin());
		return applied;
	}
	if (audit_command)
	{
		session_audit_result audit_result = {};
		if (!session_audit_repository_execute(connection, command, &audit_result))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		std::array<uint8_t, SESSION_AUDIT_RESULT_BYTES> result_payload = {};
		if (!session_audit_command_encode_result(audit_result, &result_payload) ||
		    !finish_inbox(connection, command, 0, 0, result_payload.data(),
				  result_payload.size()))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		if (!execute(connection, "COMMIT"))
		{
			const unsigned int error = mysql_errno(connection);
			if (!connection_error(error))
				rollback(connection);
			return { connection_error(error) ?
					 critical_apply_outcome::ambiguous_commit :
					 failure(error).outcome,
				 0, error };
		}
		critical_apply_result applied = { critical_apply_outcome::applied, 0, 0 };
		applied.result_size = result_payload.size();
		std::copy(result_payload.begin(), result_payload.end(),
			  applied.result_payload.begin());
		return applied;
	}
	uint64_t delta_bits = 0;
	for (unsigned int byte = 0; byte < 8; ++byte)
		delta_bits |= static_cast<uint64_t>(command.payload[byte]) << (byte * 8);
	const int64_t delta = static_cast<int64_t>(delta_bits);
	if (!delta)
	{
		rollback(connection);
		return { critical_apply_outcome::terminal_failure, 0, EINVAL };
	}
	int64_t aggregate = 0;
	uint64_t durable_revision = 0;
	for (const critical_entity_key &key : command.keys)
	{
		int64_t value = 0;
		uint64_t revision = 0;
		if (!execute_entity(connection, key, delta, &value, &revision))
		{
			const unsigned int database_failure = database_error(connection);
			const unsigned int error = database_failure ? database_failure : errno;
			rollback(connection);
			return failure(error);
		}
		aggregate ^= value;
		durable_revision = std::max(durable_revision, revision);
	}
	std::array<uint8_t, 16> result_payload = {};
	encode_u64(&result_payload, 0, static_cast<uint64_t>(aggregate));
	encode_u64(&result_payload, 8, durable_revision);
	if (!insert_outbox(connection, command, result_payload.data(), result_payload.size()) ||
	    !finish_inbox(connection, command, durable_revision, 0, result_payload.data(),
			  result_payload.size()))
	{
		const unsigned int error = database_error(connection);
		rollback(connection);
		return failure(error);
	}
	if (!execute(connection, "COMMIT"))
	{
		const unsigned int error = mysql_errno(connection);
		if (!connection_error(error))
			rollback(connection);
		return { connection_error(error) ? critical_apply_outcome::ambiguous_commit :
						   failure(error).outcome,
			 durable_revision, error };
	}
	critical_apply_result applied = { critical_apply_outcome::applied, durable_revision, 0 };
	applied.result_size = result_payload.size();
	std::copy(result_payload.begin(), result_payload.end(), applied.result_payload.begin());
	return applied;
}

bool critical_command_repository_begin_inbox_in_transaction(MYSQL *connection,
							    const critical_command &command)
{
	std::array<uint8_t, SHA256_DIGEST_LENGTH> command_hash = {}, keys_hash = {};
	if (!connection || !critical_command_valid(command) ||
	    !command_hashes(command, &command_hash, &keys_hash))
	{
		errno = EINVAL;
		return false;
	}
	return insert_inbox(connection, command, command_hash, keys_hash);
}

bool critical_command_repository_finish_item_transfer_in_transaction(
	MYSQL *connection, const critical_command &command, const item_transfer_result &result)
{
	std::array<uint8_t, ITEM_TRANSFER_RESULT_BYTES> encoded = {};
	const uint64_t durable_revision = std::max(
		{ result.from_owner_revision, result.to_owner_revision, result.max_item_revision });
	return connection && item_transfer_command_encode_result(result, &encoded) &&
	       insert_outbox(connection, command, encoded.data(), encoded.size()) &&
	       finish_inbox(connection, command, durable_revision, 0, encoded.data(),
			    encoded.size());
}

critical_apply_result critical_command_repository_apply_from_pool(const critical_command &command,
								  void *context)
{
	if (!critical_command_valid(command))
		return { critical_apply_outcome::retryable_failure, 0, EPROTONOSUPPORT };

	(void)context;
	if (sql_worker_thread_init() != 0)
		return { critical_apply_outcome::retryable_failure, 0, EIO };
	MYSQL *connection = sql_pool_acquire();
	if (!connection)
	{
		mysql_thread_end();
		return { critical_apply_outcome::retryable_failure, 0, ETIMEDOUT };
	}
	critical_apply_result applied = critical_command_repository_apply(connection, command);
	if (applied.outcome == critical_apply_outcome::ambiguous_commit ||
	    connection_error(applied.error_code))
	{
		MYSQL *replacement = sql_pool_replace_connection(connection);
		connection = replacement;
	}
	if (applied.outcome == critical_apply_outcome::ambiguous_commit && connection)
		applied = critical_command_repository_reconcile(connection, command);
	sql_pool_release(connection);
	mysql_thread_end();
	return applied;
}

critical_apply_result critical_command_repository_reconcile(MYSQL *connection,
							    const critical_command &command)
{
	last_statement_error = 0;
	if (!connection || !critical_command_valid(command))
		return { critical_apply_outcome::terminal_failure, 0, EINVAL };
	std::array<uint8_t, SHA256_DIGEST_LENGTH> command_hash = {}, keys_hash = {};
	stored_operation stored = {};
	bool found = false;
	if (!command_hashes(command, &command_hash, &keys_hash))
		return { critical_apply_outcome::retryable_failure, 0, ENOMEM };
	if (!read_operation(connection, command.operation_id, false, &stored, &found))
		return failure(database_error(connection));
	if (!found || stored.status != INBOX_COMMITTED)
		return { critical_apply_outcome::retryable_failure, 0, EAGAIN };
	if (!identity_matches(stored, command, command_hash, keys_hash))
		return { critical_apply_outcome::terminal_failure, 0, EEXIST };
	return stored_result(stored.result_code ? critical_apply_outcome::terminal_failure :
						  critical_apply_outcome::already_applied,
			     stored);
}
